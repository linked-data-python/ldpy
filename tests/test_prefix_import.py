"""Import et export de préfixes entre modules (fiche 013).

Tout @prefix de niveau module est exporté ; `from m import brick:` importe un
préfixe, en régime unique : dynamique, résolu à l'exécution — le transpileur
ne lit jamais le module importé.
"""

import sys
import textwrap

import pytest
from rdflib import URIRef

import ldpy
from ldpy.transpiler import transpile, LdpySyntaxError


BRICK = "https://brickschema.org/schema/Brick#"
UNIT = "http://qudt.org/vocab/unit/"


@pytest.fixture
def module_dir(tmp_path):
    sys.path.insert(0, str(tmp_path))
    ldpy.install()
    (tmp_path / "ldpypfx_vocab.ldpy").write_text(textwrap.dedent("""\
        @prefix brick: <https://brickschema.org/schema/Brick#> .
        @prefix unit: <http://qudt.org/vocab/unit/> .
        something = 42
        """))
    yield tmp_path
    sys.path.remove(str(tmp_path))
    for name in list(sys.modules):
        if name.startswith("ldpypfx_"):
            del sys.modules[name]


def run_in(module_dir, src, name="ldpypfx_main"):
    (module_dir / (name + ".ldpy")).write_text(src)
    __import__(name)
    return sys.modules[name]


# ------------------------------------------------------------- forme de base

def test_imported_prefix_is_writable(module_dir):
    m = run_in(module_dir, textwrap.dedent("""\
        from ldpypfx_vocab import something, brick:
        x = brick:Class
        """))
    assert m.x == URIRef(BRICK + "Class")
    assert m.something == 42


def test_alias_form(module_dir):
    m = run_in(module_dir, textwrap.dedent("""\
        from ldpypfx_vocab import unit: as u:
        y = u:DEG_C
        """))
    assert m.y == URIRef(UNIT + "DEG_C")


def test_alias_without_colon_is_error():
    with pytest.raises(LdpySyntaxError):
        transpile("from m import unit: as u\n")


def test_interpolated_local_part(module_dir):
    m = run_in(module_dir, textwrap.dedent("""\
        from ldpypfx_vocab import brick:
        z = brick:{"Cl" + "ass"}
        """))
    assert m.z == URIRef(BRICK + "Class")


def test_parenthesized_multiline_import(module_dir):
    m = run_in(module_dir, textwrap.dedent("""\
        from ldpypfx_vocab import (
            something,
            brick:,      # commentaire dans la liste
            unit: as u:,
        )
        w = brick:Zone
        v = u:M
        """))
    assert m.w == URIRef(BRICK + "Zone")
    assert m.v == URIRef(UNIT + "M")
    assert m.something == 42


def test_serialization_binding_updated(module_dir):
    m = run_in(module_dir, textwrap.dedent("""\
        from ldpypfx_vocab import brick:
        g = g{ brick:s brick:p 1 }
        """))
    assert "brick" in m.__namespaces__
    assert str(m.__namespaces__["brick"]) == BRICK


# --------------------------------------------- ce qui n'importe PAS

def test_plain_import_imports_no_prefix():
    r = transpile("import ldpypfx_vocab\nx = 1\n")
    assert "import ldpypfx_vocab" in r.code
    assert r.prefixes == {}


def test_star_import_imports_no_prefix():
    r = transpile("from ldpypfx_vocab import *\nx = 1\n")
    assert "import *" in r.code
    assert r.prefixes == {}


# ------------------------------------------------------------------- portée

def test_import_in_function_is_block_scoped(module_dir):
    m = run_in(module_dir, textwrap.dedent("""\
        def f():
            from ldpypfx_vocab import brick:
            return brick:Inside
        r = f()
        """))
    assert m.r == URIRef(BRICK + "Inside")
    # hors du bloc, brick: n'est plus déclaré
    r = transpile(textwrap.dedent("""\
        def f():
            from ldpypfx_vocab import brick:
            return brick:Inside
        x = brick:Out
        """))
    assert "pname" not in r.code.split("\n")[-2]


def test_import_shadows_and_restores(module_dir):
    m = run_in(module_dir, textwrap.dedent("""\
        @prefix brick: <http://autre/> .
        def f():
            from ldpypfx_vocab import brick:
            return brick:In
        a = f()
        b = brick:Out
        """))
    assert m.a == URIRef(BRICK + "In")
    assert m.b == URIRef("http://autre/Out")


# --------------------------------------------------------- IRI calculée

def test_computed_prefix_same_path(run):
    g, r = run(textwrap.dedent("""\
        host = "example.org"
        @prefix ex: f<http://{host}/ns#> .
        t = ex:foo
        """))
    assert g["t"] == URIRef("http://example.org/ns#foo")
    assert "pname" in r.code


def test_computed_prefix_value_at_declaration(run):
    """La déclaration s'évalue à sa position : changer la variable ensuite
    ne change pas le namespace déjà lié."""
    g, _ = run(textwrap.dedent("""\
        host = "a.org"
        @prefix ex: f<http://{host}/> .
        host = "b.org"
        t = ex:x
        """))
    assert g["t"] == URIRef("http://a.org/x")


def test_computed_prefix_without_interpolation_stays_static(run):
    g, r = run("@prefix ex: f<http://e/> .\nt = ex:x\n")
    assert g["t"] == URIRef("http://e/x")
    assert "pname" not in r.code            # inliné : régime statique


# ------------------------------------------------------- ré-export transitif

def test_transitive_reexport(module_dir):
    (module_dir / "ldpypfx_b.ldpy").write_text(textwrap.dedent("""\
        from ldpypfx_vocab import brick:
        """))
    m = run_in(module_dir, textwrap.dedent("""\
        from ldpypfx_b import brick:
        x = brick:Deep
        """), name="ldpypfx_c")
    assert m.x == URIRef(BRICK + "Deep")


# ------------------------------------------------------------------- gardes

def test_namespaces_in_all_refused():
    with pytest.raises(LdpySyntaxError):
        transpile("__all__ = ['a', '__namespaces__']\n")
    with pytest.raises(LdpySyntaxError):
        transpile('__all__ = ["__namespaces__"]\n')


def test_all_without_namespaces_ok():
    r = transpile("__all__ = ['a', 'b']\n")
    assert "__all__ = ['a', 'b']" in r.code


def test_undeclared_prefix_hint_names_import_line(module_dir):
    """En îlot, un préfixe non déclaré nomme les lignes d'import candidates
    (hors îlot, le texte reste du Python — règle R3, non testée ici)."""
    with pytest.raises(LdpySyntaxError) as exc:
        transpile(textwrap.dedent("""\
            from ldpypfx_vocab import brick:
            x = g{ unit:M brick:p 1 }
            """))
    assert "ligne 1" in str(exc.value)
    assert "ldpypfx_vocab" in str(exc.value)


def test_redeclaration_after_use_warns(module_dir):
    r = transpile(textwrap.dedent("""\
        @prefix brick: <http://autre/> .
        x = brick:a
        from ldpypfx_vocab import brick:
        """))
    assert any("brick" in str(w) for w in r.warnings)


# --------------------------------------------------------------- language map

def test_one_source_line_one_emitted_line():
    src = "from ldpypfx_vocab import something, brick:\nx = brick:a\n"
    r = transpile(src)
    lines = [l for l in r.code.split("\n") if "from ldpypfx_vocab" in l]
    assert len(lines) == 1


# --------------------------------------------------------- transparence (R3)
# Régression trouvée par le test d'identité sur la bibliothèque standard :
# zipfile/__init__.py était réécrit à cause d'un ':' DANS UN COMMENTAIRE de
# liste d'import parenthésée (`# noqa: E402`).

IMPORTS_SANS_PREFIXE = [
    "from ._path import (  # noqa: E402\n    Path,\n)\n",
    "from ._path import (\n    Path,\n\n    # used privately for tests\n"
    "    CompleteDirs,  # noqa: F401\n)\n",
    "from m import (a, b)  # type: ignore\n",
    "from m import x  # see http://e/ : rien à importer\n",
]


@pytest.mark.parametrize("src", IMPORTS_SANS_PREFIXE)
def test_import_sans_prefixe_est_identique(src):
    """Un ':' de commentaire ne déclenche pas l'îlot d'import."""
    result = transpile(src, "<t>")
    assert result.code == src
    assert result.warnings == []


def test_import_avec_prefixe_et_commentaire():
    """Le commentaire n'empêche pas de voir un vrai préfixe, et le code émis
    reste compilable (jamais de ';' vide)."""
    src = "from vocab import (  # noqa: E402\n    Path,\n    brick:,\n)\n"
    result = transpile(src, "<t>")
    assert "__namespaces__.update({'brick'" in result.code
    compile(result.code, "<t>", "exec")
