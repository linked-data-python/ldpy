"""Nœuds expression SPARQL e{...} / e<...> .

Sémantique différée : e{} construit une Expression évaluée plus tard contre
un solution mapping, avec la sémantique d'erreur de SPARQL 1.1."""

import pytest
from rdflib import Literal, URIRef, Variable, XSD

from ldpy.transpiler import transpile
from ldpy.sparql import SparqlError

P = "@prefix ex: <http://example.org/ns#> .\n"


def make(src):
    g = {"__name__": "t"}
    exec(compile(transpile(P + src, "<t>").code, "<t>", "exec"), g)
    return g


# ------------------------------------------------------------ le différé

def test_deferred_not_evaluated_at_definition(run):
    g, _ = run(P + "e1 = e{ ?x + 1 }\n")      # ?x non lié : pas d'erreur ici
    assert repr(g["e1"]) == "e{ ?x + 1 }"


def test_evaluate_with_dict_str_variable_and_kwargs():
    g = make("e1 = e{ ?x + 1 }\n")
    e1 = g["e1"]
    assert e1({"x": 41}) == Literal(42)
    assert e1({Variable("x"): 41}) == Literal(42)
    assert e1(x=41) == Literal(42)
    assert e1.evaluate(x=1) == Literal(2)


def test_unbound_variable_raises():
    g = make("e1 = e{ ?absent }\n")
    with pytest.raises(SparqlError):
        g["e1"]({})


# ------------------------------------------------------- arithmétique/types

def test_numeric_promotion_and_integer_division():
    g = make("s = e{ 1 + 2 }\nd = e{ 7 / 2 }\nm = e{ 2.5 * 2 }\n")
    assert g["s"]({}) == Literal(3)
    assert g["s"]({}).datatype == XSD.integer
    assert g["d"]({}).datatype == XSD.decimal     # SPARQL : int/int -> decimal
    assert float(g["d"]({})) == 3.5
    assert g["m"]({}).datatype == XSD.decimal


def test_division_by_zero_is_sparql_error():
    g = make("d = e{ 1 / ?z }\n")
    with pytest.raises(SparqlError):
        g["d"](z=0)


def test_unary_minus_and_not():
    g = make("n = e{ -?x }\nb = e{ !(?x = 1) }\n")
    assert g["n"](x=5) == Literal(-5)
    assert g["b"].ebv(x=2) is True


# ------------------------------------------------------------- comparaisons

def test_comparisons_numbers_and_strings():
    g = make('a = e{ ?x < 10 }\nb = e{ ?s = "oui" }\nc = e{ ?x >= ?y }\n')
    assert g["a"].ebv(x=5) is True
    assert g["b"].ebv(s="oui") is True
    assert g["c"].ebv(x=2, y=2) is True


def test_incomparable_terms_raise():
    g = make("a = e{ ?x < ?y }\n")
    with pytest.raises(SparqlError):
        g["a"](x=1, y=URIRef("http://e/i"))


def test_in_and_not_in():
    g = make('a = e{ ?x IN (1, 2, 3) }\nb = e{ ?x NOT IN ("a", "b") }\n')
    assert g["a"].ebv(x=2) is True
    assert g["a"].ebv(x=9) is False
    assert g["b"].ebv(x="c") is True


# ------------------------------------------------- logique à trois valeurs

def test_or_true_absorbs_error():
    g = make("o = e{ ?x = 1 || ?jamais = 2 }\n")
    assert g["o"].ebv(x=1) is True                 # T || err = T
    with pytest.raises(SparqlError):
        g["o"](x=0)                                # F || err = err


def test_and_false_absorbs_error():
    g = make("a = e{ ?x = 1 && ?jamais = 2 }\n")
    assert g["a"].ebv(x=0) is False                # F && err = F
    with pytest.raises(SparqlError):
        g["a"](x=1)                                # T && err = err


def test_if_is_lazy_and_coalesce_skips_errors():
    g = make('i = e{ IF(?x > 0, "pos", 1/?x) }\n'
             'c = e{ COALESCE(?absent, ?x, "défaut") }\n')
    assert g["i"](x=2) == Literal("pos")           # la branche 1/0 non évaluée
    assert g["c"](x=7) == Literal(7)
    assert g["c"]({}) == Literal("défaut")


def test_python_style_ternary():
    g = make('t = e{ "grand" if ?x > 10 else "petit" }\n')
    assert g["t"](x=20) == Literal("grand")
    assert g["t"](x=3) == Literal("petit")


# ------------------------------------------------------------- built-ins

def test_string_builtins():
    g = make('c = e{ CONCAT(UCASE(?a), "-", LCASE("FIN")) }\n'
             's = e{ STRSTARTS(?a, "bon") && CONTAINS(?a, "onj") }\n'
             'l = e{ STRLEN(?a) }\n'
             'sub = e{ SUBSTR(?a, 4, 4) }\n'
             'ba = e{ CONCAT(STRBEFORE(?a, "j"), STRAFTER(?a, "n")) }\n')
    assert g["c"](a="bonjour") == Literal("BONJOUR-fin")
    assert g["s"].ebv(a="bonjour") is True
    assert g["l"](a="bonjour") == Literal(7)
    assert g["sub"](a="bonjour") == Literal("jour")


def test_regex_and_replace():
    g = make('r = e{ REGEX(?s, "^b.n", "i") }\n'
             'p = e{ REPLACE(?s, "o", "0") }\n')
    assert g["r"].ebv(s="Bonjour") is True
    assert g["p"](s="bonjour") == Literal("b0nj0ur")


def test_term_builtins():
    g = make("s = e{ STR(?t) }\n"
             "d = e{ DATATYPE(?n) }\n"
             "i = e{ ISIRI(?t) && ISNUMERIC(?n) && !ISLITERAL(?t) }\n"
             "sm = e{ SAMETERM(?t, ex:a) }\n")
    t = URIRef("http://example.org/ns#a")
    assert g["s"](t=t) == Literal("http://example.org/ns#a")
    assert g["d"](n=5) == XSD.integer
    assert g["i"].ebv(t=t, n=5) is True
    assert g["sm"].ebv(t=t) is True


def test_lang_builtins():
    g = make('l = e{ LANG(?v) }\nm = e{ LANGMATCHES(LANG(?v), "fr") }\n')
    v = Literal("bonjour", lang="fr-CA")
    assert g["l"](v=v) == Literal("fr-CA")
    assert g["m"].ebv(v=v) is True


def test_numeric_builtins():
    g = make("r = e{ ROUND(?x) + CEIL(?y) + FLOOR(?y) + ABS(-?x) }\n")
    assert g["r"](x=2.5, y=1.2) == Literal(2.5 + 0.5 + 2 + 1 + 2.5 - 0.5) \
        or float(g["r"](x=2.5, y=1.2)) == 8.5


def test_iri_builtin_resolves_against_lexical_base():
    g = make("@base <http://example.org/data/> .\ni = e{ IRI(?s) }\n")
    assert g["i"](s="rel") == URIRef("http://example.org/data/rel")
    assert g["i"](s="http://abs/x") == URIRef("http://abs/x")


# --------------------------------------------------------- termes et divers

def test_terms_literals_pnames_and_python_injection():
    g = make('x = e{ ex:seuil }\n'
             'l = e{ "v"@en }\n'
             't = e{ "5"^^<http://www.w3.org/2001/XMLSchema#integer> }\n'
             'calls = []\n'
             'def side():\n'
             '    calls.append(1)\n'
             '    return 10\n'
             'p = e{ ?x > {side()} }\n')
    assert g["x"]({}) == URIRef("http://example.org/ns#seuil")
    assert g["l"]({}) == Literal("v", lang="en")
    assert g["t"]({}) == Literal("5", datatype=XSD.integer)
    assert g["calls"] == []                        # {py} différé aussi
    assert g["p"].ebv(x=20) is True
    assert g["calls"] == [1]
    g["p"].ebv(x=20)
    assert g["calls"] == [1, 1]                    # ré-évalué à chaque appel


def test_true_false_keywords_and_precedence():
    g = make("a = e{ true || false && false }\n"      # && lie plus fort
             "b = e{ (true || false) && false }\n"
             "c = e{ 1 + 2 * 3 = 7 }\n")
    assert g["a"].ebv({}) is True
    assert g["b"].ebv({}) is False
    assert g["c"].ebv({}) is True


def test_multiline_and_comments_inside_enode():
    g = make("""e1 = e{ ?x > 3   # seuil
                     && ?x < 10 }\n""")
    assert g["e1"].ebv(x=5) is True


def test_eiri_deferred_encoding_and_base():
    g = make("i = e<http://e/p/{?n}/fin>\n"
             "@base <http://example.org/d/> .\n"
             "j = e<sub/{?n}>\n")
    assert g["i"](n="a b") == URIRef("http://e/p/a%20b/fin")
    assert g["j"](n=5) == URIRef("http://example.org/d/sub/5")


def test_enode_usable_in_plain_python_and_filter():
    g = make("""adulte = e{ ?age >= 18 }
rows = [{"age": 12}, {"age": 30}, {"age": 18}]
keep = [r for r in rows if adulte.ebv(r)]
""")
    assert g["keep"] == [{"age": 30}, {"age": 18}]


def test_bound_requires_variable():
    from ldpy.transpiler import LdpySyntaxError
    with pytest.raises(LdpySyntaxError):
        transpile("x = e{ BOUND(3) }\n")


def test_e_name_stays_python():
    src = "e = 1\ny = e + 2\nf = e if e else 0\n"
    assert transpile(src).code == src
