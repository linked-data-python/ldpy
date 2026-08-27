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
