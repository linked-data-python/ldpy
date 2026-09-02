"""Console interactive (docs/explanation/micropython, révision) : écrire du ldpy directement
dans l'interpréteur, sans le paquet `ideas`."""

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def console(stdin_text, args=()):
    env = dict(os.environ, PYTHONPATH=REPO)
    return subprocess.run([sys.executable, "-m", "ldpy", *args],
                          input=stdin_text, capture_output=True, text=True,
                          cwd=REPO, env=env, timeout=90)


def results(p):
    """Lignes de sortie, débarrassées des invites >>> et ... (hors tty,
    les invites partent sur stdout, mêlées aux résultats)."""
    out = []
    for line in p.stdout.splitlines():
        cleaned = line
        while cleaned.startswith((">>> ", "... ", ">>>", "...")):
            cleaned = cleaned[4:] if cleaned[3:4] == " " else cleaned[3:]
        if cleaned.strip():
            out.append(cleaned.strip())
    return out


def test_expression_island_prints_repr():
    p = console("<http://e/a>\n")
    assert p.returncode == 0
    assert "rdflib.term.URIRef('http://e/a')" in p.stdout


def test_prefix_persists_across_entries():
    p = console("@prefix ex: <http://e/ns#> .\nex:hello\n")
    assert "URIRef('http://e/ns#hello')" in p.stdout


def test_base_persists_across_entries():
    p = console("@base <http://e/d/> .\n<rel>\n")
    assert "URIRef('http://e/d/rel')" in p.stdout


def test_multiline_graph_completes():
    p = console("@prefix ex: <http://e/> .\n"
                "len(g{ ex:s ex:p 1 ;\n"
                "ex:q 2 })\n")
    assert p.returncode == 0
    assert "2" in results(p)


def test_multiline_python_still_works():
    p = console("def f(x):\n    return x + 1\n\nf(41)\n")
    assert "42" in p.stdout


def test_error_does_not_kill_console():
    p = console("g{ foo:bar a foo:C }\n'survivant'\n")
    assert p.returncode == 0
    assert "foo" in p.stderr          # l'erreur ldpy est signalée
    assert "survivant" in p.stdout    # et la console continue


def test_python_error_does_not_kill_console():
    p = console("1/0\n'encore la'\n")
    assert "ZeroDivisionError" in p.stderr
    assert "encore la" in p.stdout


def test_variable_island():
    p = console("?v\n")
    assert "Variable('v')" in p.stdout


def test_block_declaration_dies_with_entry():
    src = ("if True:\n"
           "    @prefix tmp: <http://t/> .\n"
           "    x = tmp:in_block\n"
           "\n"
           "x\n"
           "tmp = 5\n"       # tmp redevient un nom Python ordinaire
           "tmp\n")
    p = console(src)
    assert "URIRef('http://t/in_block')" in p.stdout
    assert "5" in results(p)


def test_interactive_after_script(tmp_path):
    script = tmp_path / "s.ldpy"
    script.write_text("@prefix ex: <http://e/> .\nX = ex:a\n")
    p = console("X\nex:b\n", args=("-i", str(script)))
    assert "URIRef('http://e/a')" in p.stdout   # les globals du script
    assert "URIRef('http://e/b')" in p.stdout   # et ses préfixes


def test_current_graph_persists_across_entries():
    """`@graph as g` then `+{ }` on the next line: the current graph is a
    declaration like @prefix, it must survive the entry that declares it."""
    p = console("@prefix ex: <http://e/> .\n"
                "@graph as g\n"
                "+{ ex:alice a ex:Person }\n"
                "len(g)\n")
    assert p.returncode == 0
    assert "1" in results(p)


def test_add_island_prints_nothing():
    """`+{ }` is a statement: the console must not echo the graph."""
    p = console("@prefix ex: <http://e/> .\n"
                "@graph as g\n"
                "+{ ex:alice a ex:Person }\n")
    assert "Graph" not in p.stdout


def test_current_bindings_persist_across_entries():
    """`for @bindings as b in ...` names the bindings; the entries that
    follow must still see the current graph declared before them."""
    p = console("@prefix ex: <http://e/> .\n"
                "@graph as g\n"
                "for @bindings as b in [{\"n\": \"ana\"}]:\n"
                "    +{ ex:p ex:name ?n }\n"
                "\n"
                "len(g)\n")
    assert "1" in results(p)


def test_add_without_current_graph_reports_at_once():
    """An island that is complete but has no current graph is an error, not
    an entry waiting to be finished: the console used to hang on it."""
    p = console("@prefix ex: <http://e/> .\n"
                "+{ ex:a ex:b ex:c }\n"
                "'survivant'\n")
    assert p.returncode == 0
    assert "graphe courant" in p.stderr
    assert "survivant" in p.stdout


def test_graph_declaration_at_end_of_buffer():
    """`@graph as g` with no trailing newline: the inline-whitespace scan
    used to loop for ever on the empty string returned at end of text."""
    from ldpy.transpiler.core import Transpiler
    t = Transpiler("@graph as g", "<c>", emit_prelude=False)
    assert t.run().code.startswith("g = ")


def test_bound_at_end_of_buffer_is_an_error_not_a_crash():
    from ldpy.transpiler import LdpySyntaxError
    from ldpy.transpiler.core import Transpiler
    import pytest
    with pytest.raises(LdpySyntaxError):
        Transpiler("e{ BOUND(", "<c>", emit_prelude=False).run()
