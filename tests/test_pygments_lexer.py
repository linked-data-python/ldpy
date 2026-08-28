"""Le surligneur EST le transpileur : le lexer Pygments lit la language map,
donc il colore exactement là où le transpileur voit un îlot.

Trois propriétés le tiennent : round-trip (la concaténation des valeurs de
tokens redonne la source), transparence (du Python pur donne exactement les
tokens de PythonLexer), et absence de Token.Error sur tous les extraits de la
documentation."""

import glob
import os

import pytest

from pygments.lexers.python import PythonLexer
from pygments.token import Error, Keyword, Name, Number, Punctuation, String

from ldpy.pygments_lexer import LdpyLexer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LEXER = LdpyLexer()
PY_LEXER = PythonLexer()


def toks(src):
    return list(LEXER.get_tokens_unprocessed(src))


def kinds(src):
    return [(t, v) for _, t, v in toks(src) if not v.isspace()]


SOURCES = [
    "",
    "x = 1\n",
    "@prefix ex: <http://e/> .\nt = ex:Thing\n",
    "@base <http://e/> .\nu = <rel>\n",
    '@prefix ex: <http://e/> .\ng = g{ ex:s a ex:C ; ex:p 1, "x"@en }\n',
    '@prefix ex: <http://e/> .\ng = g{ [] ex:p ( 1 "two"@en ) ; ex:q [ ex:r 2 ] }\n',
    '@prefix ex: <http://e/> .\nv = 1\ng = g{ ex:{v} ex:p {v} ; ex:q {v}^^ex:t }\n',
    '@prefix ex: <http://e/> .\ng = g{ ex:s ex:p _:{(1, 2)} ; ex:q _:b }\n',
    "x = 2\ni = f<http://e/{x}/y>\nn = f{x}\nm = ?{x + 1}\n",
    'lit = f"v{x}"@en\n',
    "v = ?name\nw = $name\n",
    "adult = e{ ?age >= 18 && BOUND(?n) }\ni = e<http://e/p/{?n}>\n",
    "@prefix ex: <http://e/> .\n@graph as g\n+{ ex:s ex:p 1 }\n-{ ex:s ?p ?o }\n",
    "@prefix ex: <http://e/> .\n@graph <http://e/g1> as named\n",
    "@prefix ex: <http://e/> .\nr = m{ ?s a ex:C ; ex:v ?v }\n",
    "@prefix ex: <http://e/> .\nq = s{ SELECT ?x WHERE { ?x a ex:C } ORDER BY ?x }\n",
    "@prefix ex: <http://e/> .\nc = ex:C\nq = s{ SELECT ?x WHERE { ?x a {c} } }\n",
    "@prefix ex: <http://e/> .\n@graph as g\nfor @bindings in rows:\n"
    "    +{ ?s ex:p e{ ?v * 2 } }\n",
    "from m import brick:, unit: as u:\n",
    "@prefix p: <http://o/> .\ndef f():\n    global @prefix p: <http://i/> .\n",
    "@prefix ex: <http://e/> .\nr = m{ ?s ex:p ?v }(g, b)\n",
]

PURE_PYTHON = [
    "a = b < c\n",
    "if a<b>c:\n    pass\n",
    "r = d[i:j]\n",
    "m = {k: v for k, v in items}\n",
    "y = x @ w + b\n",
    "@decorator\ndef f():\n    pass\n",
    "s = 'g{ pas un graphe }'\n",
    's = "@prefix ex: <http://e/> ."\n',
    's = f"val {x!r:>{w}} fin"\n',
    "keys = a - {'x'}\n",
    "async def f():\n    await g()\n",
    "n = 0x1f + 1e-5 + 1_000j + .5\n",
]


# ------------------------------------------------------- propriété de round-trip

@pytest.mark.parametrize("src", SOURCES + PURE_PYTHON)
def test_round_trip(src):
    """La concaténation des valeurs redonne la source, positions croissantes."""
    out = toks(src)
    assert "".join(v for _, _, v in out) == src
    positions = [p for p, _, _ in out]
    assert positions == sorted(positions)
    for pos, _, value in out:
        assert src[pos:pos + len(value)] == value


@pytest.mark.parametrize("src", SOURCES)
def test_no_error_token(src):
    assert [(p, v) for p, t, v in toks(src) if t is Error] == []


# ------------------------------------------------------------- transparence

@pytest.mark.parametrize("src", PURE_PYTHON)
def test_pure_python_is_lexed_as_python(src):
    """Aucun îlot : la sortie est celle de PythonLexer, token pour token."""
    assert toks(src) == list(PY_LEXER.get_tokens_unprocessed(src))


def test_own_sources_lex_as_python():
    for path in sorted(glob.glob(os.path.join(REPO, "ldpy", "*.py"))):
        with open(path, encoding="utf-8") as f:
            src = f.read()
        assert toks(src) == list(PY_LEXER.get_tokens_unprocessed(src)), path


def test_invalid_source_degrades_to_python():
    """Un tampon d'éditeur invalide reste lisible (repli Python, pas d'échec)."""
    src = "g = g{ ex:s ex:p\n"          # îlot non terminé
    out = toks(src)
    assert "".join(v for _, _, v in out) == src


# ------------------------------------------------------------ choix de tokens

def test_prefix_declaration_tokens():
    assert kinds("@prefix ex: <http://e/> .\n") == [
        (Keyword.Declaration, "@prefix"), (Name.Namespace, "ex"),
        (Punctuation, ":"), (Name.Label, "<http://e/>"), (Punctuation, ".")]


def test_graph_island_tokens():
    got = kinds('@prefix ex: <http://e/> .\ng = g{ ex:s a ex:C ; ex:p 1 }\n')
    assert (Keyword.Pseudo, "g{") in got          # le sigil d'îlot
    assert (Keyword, "a") in got                  # le a de Turtle
    assert (Name.Namespace, "ex") in got and (Name.Tag, "C") in got
    assert (Number, "1") in got


def test_variables_and_language_tags():
    got = kinds('@prefix ex: <http://e/> .\ng = g{ ?s ex:p "x"@en }\n')
    assert (Name.Variable, "?s") in got
    assert (String, '"x"') in got
    assert (Name.Function, "en") in got


def test_interpolation_returns_to_python():
    """{expr} dans un îlot est coloré comme du Python."""
    src = '@prefix ex: <http://e/> .\ng = g{ ex:s ex:p {len(rows)} }\n'
    got = kinds(src)
    assert (Name.Builtin, "len") in got           # PythonLexer a repris la main


def test_sparql_group_is_not_an_interpolation():
    """L'oracle de la fiche 015 vaut aussi pour la coloration."""
    src = "@prefix ex: <http://e/> .\nq = s{ SELECT ?x WHERE { ?x a ex:C } }\n"
    got = kinds(src)
    assert (Keyword, "SELECT") in got and (Keyword, "WHERE") in got
    assert (Name.Variable, "?x") in got           # pas passé au lexer Python
    assert (Name.Tag, "C") in got


def test_sparql_interpolation_is_python():
    src = "@prefix ex: <http://e/> .\nc = 1\nq = s{ SELECT ?x WHERE { ?x a {c} } }\n"
    assert [(p, v) for p, t, v in toks(src) if t is Error] == []


def test_deferred_expression_builtins():
    got = kinds("a = e{ ?age >= 18 && BOUND(?n) }\n")
    assert (Keyword.Pseudo, "e{") in got
    assert (Name.Builtin, "BOUND") in got
    assert (Name.Variable, "?age") in got


def test_lexer_is_registered_in_pygments():
    """L'entry point rend `ldpy` disponible partout (mkdocs, sphinx, CLI)."""
    from pygments.lexers import get_lexer_by_name
    assert isinstance(get_lexer_by_name("ldpy"), LdpyLexer)


# ------------------------------------------------- tous les extraits de la doc

FENCE_DOCS = sorted(glob.glob(os.path.join(REPO, "docs", "**", "*.md"),
                              recursive=True))


def _doc_blocks():
    import re
    fence = re.compile(r"^```(\w+)\n(.*?)^```", re.M | re.S)
    out = []
    for path in FENCE_DOCS:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for i, m in enumerate(fence.finditer(text)):
            if m.group(1) == "ldpy":
                out.append(pytest.param(m.group(2), id="%s#%d" % (
                    os.path.relpath(path, REPO), i)))
    return out


@pytest.mark.parametrize("code", _doc_blocks())
def test_documentation_snippets_highlight(code):
    out = toks(code)
    assert "".join(v for _, _, v in out) == code
    assert [(p, v) for p, t, v in out if t is Error] == []
