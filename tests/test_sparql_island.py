"""Îlot SPARQL s{ ... } (fiche 015) : tout SPARQL, rdflib comme oracle."""

import textwrap

import pytest
from rdflib import URIRef, Literal

from ldpy.transpiler import transpile, LdpySyntaxError


DATA = """\
@prefix ex: <http://e/> .
@graph as g
+{ ex:a a ex:Sensor ; ex:v 1 .
   ex:b a ex:Sensor ; ex:v 2 .
   ex:c a ex:Autre ; ex:v 3 }
"""


def T(src):
    return transpile(textwrap.dedent(src))


# ------------------------------------------------------------------- formes

def test_select_iterates_rows(run):
    g, _ = run(DATA + "rows = [tuple(r) for r in "
               "s{ SELECT ?s ?v WHERE { ?s a ex:Sensor ; ex:v ?v } ORDER BY ?v }]\n")
    assert g["rows"] == [(URIRef("http://e/a"), Literal(1)),
                         (URIRef("http://e/b"), Literal(2))]


def test_ask_bool(run):
    g, _ = run(DATA + "ok = bool(s{ ASK { ex:a a ex:Sensor } })\n"
                      "ko = bool(s{ ASK { ex:zzz a ex:Sensor } })\n")
    assert g["ok"] is True and g["ko"] is False


def test_construct(run):
    g, _ = run(DATA + "out = s{ CONSTRUCT { ?s ex:w ?v } "
                      "WHERE { ?s ex:v ?v } }._execute().graph\n")
    assert len(g["out"]) == 3


def test_insert_data_update(run):
    g, _ = run(DATA + "s{ INSERT DATA { ex:new a ex:T } }._execute()\n")
    assert (URIRef("http://e/new"), None, None) in g["g"]


def test_multiline_query_with_comment(run):
    g, _ = run(DATA + textwrap.dedent("""\
        n = len(list(s{
            SELECT ?s          # les capteurs
            WHERE {
                ?s a ex:Sensor .
            }
        }))
        """))
    assert g["n"] == 2


# ------------------------------------------------------------- interpolation

def test_interpolation_in_term_position(run):
    g, _ = run(DATA + "cls = ex:Autre\n"
               "n = len(list(s{ SELECT ?s WHERE { ?s a {cls} } }))\n")
    assert g["n"] == 1


def test_interpolation_pname_island(run):
    """L'interpolation peut contenir un îlot ldpy (nom préfixé)."""
    g, _ = run(DATA + "n = len(list(s{ SELECT ?s WHERE "
                      "{ ?s a {ex:Sensor} } }))\n")
    assert g["n"] == 2


def test_interpolation_evaluated_once(run):
    g, _ = run(DATA + textwrap.dedent("""\
        calls = []
        def f():
            calls.append(1)
            return ex:Sensor
        q = s{ SELECT ?s WHERE { ?s a {f()} } }
        list(q)
        list(q)
        """))
    assert len(g["calls"]) == 1


def test_interpolation_outside_term_position_is_error():
    with pytest.raises(LdpySyntaxError):
        T("""\
            @prefix ex: <http://e/> .
            @graph as g
            c = "?s a ex:T"
            q = s{ SELECT ?s WHERE { {c} } }
            """)


# --------------------------------------------------------------- validation

def test_syntax_error_at_transpile_time():
    with pytest.raises(LdpySyntaxError) as exc:
        T("@graph as g\nq = s{ SELEKT ?x WHERE { ?x a ?y } }\n")
    assert "SPARQL" in str(exc.value)


def test_prologue_from_scope_prefixes():
    """Un préfixe en portée valide ; un préfixe inconnu fait échouer la
    validation à la transpilation."""
    T("@prefix ex: <http://e/> .\n@graph as g\n"
      "q = s{ SELECT ?s WHERE { ?s a ex:T } }\n")
    with pytest.raises(LdpySyntaxError):
        T("@graph as g\nq = s{ SELECT ?s WHERE { ?s a inconnu:T } }\n")


def test_dynamic_prefix_validates_with_synthetic_prologue(run):
    """Un préfixe dynamique (IRI calculée) valide à la transpilation avec
    une IRI synthétique, et s'exécute avec la vraie."""
    g, _ = run(textwrap.dedent("""\
        host = "e"
        @prefix ex: f<http://{host}/> .
        @graph as g
        +{ ex:a a ex:T }
        n = len(list(s{ SELECT ?s WHERE { ?s a ex:T } }))
        """))
    assert g["n"] == 1


# ------------------------------------------------------------------ liaison

def test_rebind_to_other_graph(run):
    g, _ = run(DATA + textwrap.dedent("""\
        import rdflib
        vide = rdflib.Graph()
        q = s{ SELECT ?s WHERE { ?s a ex:Sensor } }
        n_g = len(list(q))
        n_vide = len(list(q(vide)))
        """))
    assert g["n_g"] == 2 and g["n_vide"] == 0


def test_without_graph_in_scope_lazy_error(run):
    g, _ = run("q = s{ SELECT ?s WHERE { ?s ?p ?o } }\n")
    with pytest.raises(RuntimeError):
        list(g["q"])


def test_subquery_braces_are_groups(run):
    g, _ = run(DATA + textwrap.dedent("""\
        n = len(list(s{ SELECT ?s WHERE {
            { SELECT ?s WHERE { ?s a ex:Sensor } } } }))
        """))
    assert g["n"] == 2


def test_update_par_execute_public(run):
    """`execute()` est la forme publique : un UPDATE ne s'itère pas."""
    g, _ = run(DATA + "s{ INSERT { ?s ex:seen 1 } WHERE { ?s a ex:Sensor } }"
                      ".execute()\n")
    assert len(g["g"]) > 2


# --------------------------------------------------------------- record 012
# A '#' inside a full IRI was read as the start of a comment, so the rest of
# the line — closing brace included — was swallowed. The most ordinary shape
# an IRI takes in RDF, and only `s{ }` had the defect: `m{ }` and `g{ }`
# parse IRIs as terms and never saw it. Found by the corpus study.

def test_a_hash_inside_a_full_iri_is_not_a_comment():
    src = ("@graph as g\n"
           "q = s{ SELECT ?s WHERE { ?s <http://example.org/ns#X> ?o } }\n")
    code = transpile(src, "t.ldpy").code
    assert "http://example.org/ns#X" in code


def test_the_same_iri_in_the_other_islands_never_broke():
    """The regression guard is on `s{ }`, but pin the siblings too: the fix
    must not have been needed there, and must not change them."""
    src = ("@graph as g\n"
           "m1 = m{ ?s <http://example.org/ns#X> ?o }\n"
           "g1 = g{ <http://example.org/ns#A> <http://example.org/ns#p> 1 }\n")
    code = transpile(src, "t.ldpy").code
    assert code.count("http://example.org/ns#") == 3


def test_a_real_comment_is_still_a_comment():
    src = ("@prefix ex: <http://example.org/ns#> .\n"
           "@graph as g\n"
           "q = s{ SELECT ?s WHERE { ?s ex:v ?v }  # a real comment\n"
           "     }\n")
    assert "a real comment" in transpile(src, "t.ldpy").code


def test_less_than_is_still_an_operator():
    """`<` that does not open an IRI is SPARQL's less-than. The fix keys on
    `_iriref_end`, so it must leave FILTER(?v < 5) alone."""
    src = ("@prefix ex: <http://example.org/ns#> .\n"
           "@graph as g\n"
           "q = s{ SELECT ?s WHERE { ?s ex:v ?v . FILTER(?v < 5 && ?v > 1) } }\n")
    code = transpile(src, "t.ldpy").code
    assert "?v < 5 && ?v > 1" in code


def test_a_hash_inside_a_string_is_not_a_comment_either():
    src = ("@prefix ex: <http://example.org/ns#> .\n"
           "@graph as g\n"
           'q = s{ SELECT ?s WHERE { ?s ex:v "a#b" } }\n')
    assert 'a#b' in transpile(src, "t.ldpy").code
