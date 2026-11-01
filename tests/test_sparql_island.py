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


# INSERT DATA / DELETE DATA admit no variables: an interpolated term bound as
# initBindings left the block holding a Variable, and nothing was written,
# without an error.  Found by the corpus study.

def test_insert_data_takes_an_interpolated_term(run):
    g, _ = run(DATA + "who = ex:new\nlabel = 'x y'\n"
                      "s{ INSERT DATA { {who} a ex:T ; ex:label {label} } }"
                      ".execute()\n")
    assert (URIRef("http://e/new"), URIRef("http://e/label"),
            Literal("x y")) in g["g"]


def test_delete_data_takes_an_interpolated_term(run):
    g, _ = run(DATA + "v = 2\ns{ DELETE DATA { ex:b ex:v {v} } }.execute()\n")
    assert (URIRef("http://e/b"), URIRef("http://e/v"), Literal(2)) \
        not in g["g"]
    assert (URIRef("http://e/a"), URIRef("http://e/v"), Literal(1)) in g["g"]


def test_an_interpolated_name_is_not_a_prefix_of_another(run):
    g, _ = run(DATA + "s{ INSERT DATA { ex:z ex:v {1} , {10} } }.execute()\n")
    assert {o for o in g["g"].objects(URIRef("http://e/z"),
                                       URIRef("http://e/v"))} \
        == {Literal(1), Literal(10)}


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


# ------------------------------------------- handed over to graph.query()

def test_graph_query_accepts_an_island(run):
    """A function that runs `graph.query(q)` can receive an s{ }."""
    g, _ = run(DATA + textwrap.dedent("""\
        def run_it(graph, q):
            return sorted(str(r[0]) for r in graph.query(q))
        q = s{ SELECT ?s WHERE { ?s a ex:Sensor } }
        found = run_it(g, q)
        """))
    assert g["found"] == ["http://e/a", "http://e/b"]


def test_graph_query_keeps_the_interpolated_terms(run):
    g, _ = run(DATA + textwrap.dedent("""\
        cls, v = ex:Sensor, 2
        q = s{ SELECT ?s WHERE { ?s a {cls} ; ex:v {v} } }
        found = [str(r[0]) for r in g.query(q)]
        also = [str(r[0]) for r in g.query(q, initBindings={"s": ex:a})]
        """))
    assert g["found"] == ["http://e/b"]
    assert g["also"] == []


def test_graph_query_refuses_an_interpolated_blank_node(run):
    g, _ = run(DATA + textwrap.dedent("""\
        from rdflib import BNode
        blank = BNode()
        q = s{ SELECT ?p WHERE { {blank} ?p ?o } }
        """))
    with pytest.raises(TypeError) as exc:
        g["g"].query(g["q"])
    assert "blank node" in str(exc.value)


def test_graph_query_refuses_carried_bindings_it_would_lose(run):
    g, _ = run(DATA + textwrap.dedent("""\
        q = s{ SELECT ?v WHERE { ?s ex:v ?v } }(None, {"s": ex:a})
        """))
    with pytest.raises(TypeError) as exc:
        g["g"].query(g["q"])
    assert "initBindings" in str(exc.value)


def test_graph_update_accepts_an_island(run):
    g, _ = run(DATA + textwrap.dedent("""\
        t = ex:Gauge
        g.update(s{ INSERT { ?s a {t} } WHERE { ?s a ex:Sensor } })
        g.update(s{ INSERT DATA { ex:z a {t} } })
        n = len(list(g.subjects(None, t)))
        """))
    assert g["n"] == 3


# -------------------------------------- initBindings only when there are

class _NoInitBindings:
    """A graph-like object whose query() takes the query alone (kglab)."""

    def __init__(self, graph):
        self.graph = graph
        self.calls = []

    def query(self, q):
        self.calls.append(q)
        return self.graph.query(q)


class _TextOnly:
    """A receiver that refuses rdflib's prepared form (a remote store)."""

    def __init__(self, graph):
        self.graph = graph
        self.calls = []

    def query(self, q, initBindings=None):
        if not isinstance(q, str):
            raise TypeError("expected a query string")
        self.calls.append(q)
        return self.graph.query(q, initBindings=initBindings)

    def update(self, q, initBindings=None):
        if not isinstance(q, str):
            raise RuntimeError("store failed half-way")
        self.graph.update(q, initBindings=initBindings)


def test_no_init_bindings_passed_when_there_are_none(run):
    g, _ = run(DATA + "q = s{ SELECT ?s WHERE { ?s a ex:Sensor } }\n")
    other = _NoInitBindings(g["g"])
    assert len(list(g["q"](other))) == 2
    assert len(other.calls) == 1 and not isinstance(other.calls[0], str)


def test_the_text_is_a_second_attempt(run):
    g, _ = run(DATA + textwrap.dedent("""\
        cls = ex:Sensor
        q = s{ SELECT ?s WHERE { ?s a {cls} } }
        """))
    other = _TextOnly(g["g"])
    assert len(list(g["q"](other))) == 2
    text = other.calls[0]
    assert "PREFIX ex: <http://e/>" in text and "?__i0" in text


def test_an_update_is_not_retried_after_a_failure(run):
    g, _ = run(DATA + "u = s{ INSERT { ?s a ex:Gauge } WHERE { ?s a ex:Sensor } }\n")
    with pytest.raises(RuntimeError):
        g["u"](_TextOnly(g["g"])).execute()


# ------------------------------------------------------ f<…> inside s{ }

def test_formatted_iri_in_sparql_is_bound(run):
    g, r = run(DATA + textwrap.dedent("""\
        name = "a"
        n = len(list(s{ SELECT ?v WHERE { f<http://e/{name}> ex:v ?v } }))
        """))
    assert g["n"] == 1
    assert "firi(" in r.code and "?__i0" in r.code


def test_formatted_iri_without_hole_is_an_iri(run):
    g, r = run(DATA + "n = len(list(s{ SELECT ?v WHERE { f<http://e/a> ex:v ?v } }))\n")
    assert g["n"] == 1
    assert "<http://e/a>" in r.code


def test_formatted_iri_resolves_against_base(run):
    g, _ = run(textwrap.dedent("""\
        @base <http://e/> .
        @prefix ex: <http://e/> .
        @graph as g
        +{ ex:a ex:v 1 }
        name = "a"
        n = len(list(s{ SELECT ?v WHERE { f<{name}> ex:v ?v } }))
        """))
    assert g["n"] == 1


def test_a_variable_named_f_before_less_than_is_a_comparison(run):
    g, _ = run(DATA + "n = len(list(s{ SELECT ?s WHERE { ?s ex:v ?f FILTER(?f<3) } }))\n")
    assert g["n"] == 2


def test_base_applies_to_relative_iris(run):
    g, _ = run(textwrap.dedent("""\
        @base <http://e/> .
        @prefix ex: <http://e/> .
        @graph as g
        +{ ex:a a ex:T }
        n = len(list(s{ SELECT ?s WHERE { ?s a <T> } }))
        """))
    assert g["n"] == 1
