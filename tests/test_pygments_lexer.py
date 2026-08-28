"""Le surligneur EST le transpileur : le lexer Pygments lit la language map,
donc il colore exactement là où le transpileur voit un îlot.

Trois propriétés le tiennent : round-trip (la concaténation des valeurs de
tokens redonne la source), transparence (du Python pur donne exactement les
tokens de PythonLexer), et absence de Token.Error sur tous les extraits de la
documentation."""

import glob
import os

import pytest

pytest.importorskip("pygments", reason="extra optionnel [highlight]")

from pygments.lexers.python import PythonLexer
from pygments.token import (Error, Keyword, Name, Number, Punctuation,
                            String)

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
    """Délégué à TurtleLexer : @prefix EST une directive Turtle."""
    assert kinds("@prefix ex: <http://e/> .\n") == [
        (Keyword.Declaration, "@prefix"), (Name.Namespace, "ex:"),
        (String.Symbol, "<http://e/>"), (Punctuation, ".")]


def test_graph_island_tokens():
    got = kinds('@prefix ex: <http://e/> .\ng = g{ ex:s a ex:C ; ex:p 1 }\n')
    assert (Keyword.Pseudo, "g{") in got          # le sigil d'îlot
    assert (Keyword, "a") in got                  # le a de Turtle
    assert (Name.Namespace, "ex") in got and (Name.Class, "C") in got
    assert (Number.Integer, "1") in got


def test_variables_and_language_tags():
    got = kinds('@prefix ex: <http://e/> .\ng = g{ ?s ex:p "x"@en }\n')
    assert (Name.Variable, "?s") in got
    assert (String, '"') in got and (String, "x") in got
    assert (Name.Builtin, "en") in got


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
    assert (Name.Class, "C") in got


def test_sparql_interpolation_is_python():
    src = "@prefix ex: <http://e/> .\nc = 1\nq = s{ SELECT ?x WHERE { ?x a {c} } }\n"
    assert [(p, v) for p, t, v in toks(src) if t is Error] == []


def test_island_nested_in_an_interpolation():
    """ex:{?id} — l'interpolation est re-scannée par le transpileur, elle peut
    donc contenir un îlot ; PythonLexer seul y verrait une erreur."""
    src = ("@prefix ex: <http://e/> .\n@graph as g\n"
           "for @bindings in rows:\n    +{ ex:{?id} ex:value ?v }\n")
    out = toks(src)
    assert [(p, v) for p, t, v in out if t is Error] == []
    assert (Name.Variable, "?id") in [(t, v) for _, t, v in out]


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


# ------------------------------------- huit rôles, huit couleurs (mkdocs-material)
# mkdocs-material rabat plusieurs Name.* sur la même couleur ; le choix des
# tokens vise huit classes CSS distinctes, sinon les IRIs, les noms locaux et
# les mots-clés seraient de la même couleur.

_MATERIAL_GROUPS = {                       # classe Pygments -> rôle coloré
    "kp": "keyword", "kd": "keyword", "k": "keyword",
    "ss": "string", "s": "string", "s1": "string", "s2": "string",
    "nn": "function", "nc": "function",
    "nv": "variable", "na": "variable",
    "nb": "constant",
    "mi": "number", "m": "number",
    "o": "operator", "p": "punctuation", "c1": "comment",
}


def test_token_classes_are_distinguishable():
    from pygments.formatters.html import _get_ttype_class
    from ldpy.pygments_lexer import (T_SIGIL, T_DECL, T_KW, T_IRI, T_PREFIX,
                                     T_LOCAL, T_VAR, T_LANG, T_CONST)
    roles = {}
    for name, ttype in [("sigil", T_SIGIL), ("decl", T_DECL), ("kw", T_KW),
                        ("iri", T_IRI), ("prefix", T_PREFIX),
                        ("local", T_LOCAL), ("var", T_VAR), ("lang", T_LANG)]:
        cls = _get_ttype_class(ttype)
        assert cls in _MATERIAL_GROUPS, (name, ttype, cls)
        roles[name] = _MATERIAL_GROUPS[cls]
    # les rôles qui DOIVENT se distinguer les uns des autres
    assert roles["iri"] != roles["kw"]
    assert roles["prefix"] != roles["kw"] and roles["local"] != roles["kw"]
    assert roles["var"] != roles["prefix"] and roles["var"] != roles["iri"]
    assert roles["sigil"] == roles["decl"] == roles["kw"]   # ce sont des mots
    assert _get_ttype_class(T_CONST)                        # stylé, quel qu'il soit


# --------------------------------------------------- fragments incomplets
#
# La documentation et l'article montrent des EXTRAITS : `g{ ex:s ex:p 1 }`
# sans la ligne `@prefix` qui le rendrait légal. Le transpileur les refuse, à
# raison. Le surligneur, lui, déclare ce qui manque et recommence — sinon
# l'extrait retombe en Python pur et se couvre de rouge.

FRAGMENTS = [
    "g = g{ ex:s ex:p 1 }",
    "lit = \"x\"^^xsd:integer",
    "+{ ex:s ex:p 1 }",                       # ni préfixe ni graphe courant
    "-{ ex:s ex:p ?x }",
    "s{ SELECT ?s WHERE { ?s a ex:T } }",     # préfixe inconnu de rdflib
    "for @bindings as r in m{ ?s ex:p ?v }:",
    "lus = list(m{ ?s a ex:Sensor ; ex:v ?v })",
]


@pytest.mark.parametrize("src", FRAGMENTS)
def test_fragment_incomplet_sans_erreur(src):
    assert not [v for _, t, v in toks(src) if t is Error], src


@pytest.mark.parametrize("src", FRAGMENTS)
def test_fragment_incomplet_round_trip(src):
    assert "".join(v for _, _, v in toks(src)) == src


@pytest.mark.parametrize("src", FRAGMENTS)
def test_fragment_incomplet_colore_comme_un_fichier_complet(src):
    """Le préambule synthétique ne doit rien changer d'autre : les mêmes
    caractères reçoivent les mêmes tokens qu'avec les déclarations écrites."""
    complet = ("@prefix ex: <http://e/> .\n"
               "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
               "@graph as g\n")
    decale = len(complet)
    attendu = [(i - decale, t, v)
               for i, t, v in toks(complet + src) if i >= decale]
    assert attendu == toks(src)


def test_le_preambule_ne_fuit_pas_dans_les_positions():
    """Les positions rendues sont celles de la SOURCE, pas du texte augmenté."""
    src = "g = g{ ex:s ex:p 1 }"
    for i, _, v in toks(src):
        assert src[i:i + len(v)] == v, (i, v)


def test_ce_qui_nest_pas_reparable_reste_du_python_sans_erreur():
    """Un fragment qu'aucune déclaration ne sauve retombe en Python — mais
    sans Token.Error : le surligneur n'est pas le lieu où l'on signale une
    faute de syntaxe."""
    src = "def f(:\n"
    assert not [v for _, t, v in toks(src) if t is Error]
    assert "".join(v for _, _, v in toks(src)) == src


def test_les_declarations_synthetiques_sont_bornees():
    from ldpy.pygments_lexer import _MAX_SYNTHETIC, _synthetic_declaration
    assert _MAX_SYNTHETIC > 0
    assert _synthetic_declaration(Exception("préfixe non déclaré : 'ex:'")) \
        .startswith("@prefix ex: <")
    assert _synthetic_declaration(Exception("Unknown namespace prefix : brick")) \
        .startswith("@prefix brick: <")
    assert "graph" in _synthetic_declaration(
        Exception("'+{ ... }' sans graphe courant : ..."))
    assert _synthetic_declaration(Exception("autre chose")) is None
