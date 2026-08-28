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
