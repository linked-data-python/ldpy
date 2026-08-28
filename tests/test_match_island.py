"""Îlot de motif m{ ... } (fiche 016) : lire le graphe, sans moteur."""

import textwrap

import pytest
from rdflib import URIRef, Literal

from ldpy.transpiler import transpile, LdpySyntaxError


E = "http://e/"

DATA = """\
@prefix ex: <http://e/> .
@graph as g
+{ ex:a a ex:Sensor ; ex:v 1 ; rdfs:label "capteur a" .
   ex:b a ex:Sensor ; ex:v 2 .
   ex:c a ex:Autre ; ex:v 3 }
""".replace("rdfs:", "ex:")


def run_src(run, tail):
    return run(textwrap.dedent(DATA + tail))


# ---------------------------------------------------------------- arités

def test_arity_one_yields_terms(run):
    g, _ = run_src(run, "xs = sorted(m{ ?s a ex:Sensor })\n")
    assert g["xs"] == [URIRef(E + "a"), URIRef(E + "b")]


def test_arity_two_yields_unpackable_rows(run):
    g, _ = run_src(run, "xs = sorted((s, v) for s, v in "
                        "m{ ?s a ex:Sensor ; ex:v ?v })\n")
    assert g["xs"] == [(URIRef(E + "a"), Literal(1)),
                       (URIRef(E + "b"), Literal(2))]


def test_row_named_and_variable_access(run):
    g, _ = run_src(run, "row = m{ ?s ex:v ?v . ?s a ex:Autre }.first()\n"
                        "a = row.s\nb = row[?v]\nc = row['v']\n")
    assert g["a"] == URIRef(E + "c")
    assert g["b"] == g["c"] == Literal(3)


def test_projection_order_is_first_appearance(run):
    g, _ = run_src(run, "row = m{ ?x ex:v ?y } .first()\n"
                        "" )
    # ordre : x (sujet) puis y (objet)
    assert g["row"]._fields == ["x", "y"]


# ------------------------------------------------------- jointure, bn

def test_join_is_nested_loop_equivalent(run):
    g, _ = run_src(run, textwrap.dedent("""\
        attendu = sorted((s, v) for s, _, _ in g.triples((None, None, ex:Sensor))
                         for _, _, v in g.triples((s, ex:v, None)))
        obtenu = sorted((s, v) for s, v in m{ ?s a ex:Sensor ; ex:v ?v })
        """))
    assert g["obtenu"] == g["attendu"]


def test_anonymous_node_is_nondistinguished_variable(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        +{ ex:tm ex:pom [ ex:pred ex:name ] }
        ps = list(m{ ex:tm ex:pom [ ex:pred ?p ] })
        """))
    # le nœud anonyme est apparié mais non projeté : arité 1, des termes
    assert g["ps"] == [URIRef(E + "name")]


def test_shared_variable_joins(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        +{ ex:a ex:knows ex:b . ex:b ex:knows ex:c }
        chaine = [(x, z) for x, y, z in m{ ?x ex:knows ?y . ?y ex:knows ?z }]
        """))
    assert g["chaine"] == [(URIRef(E + "a"), URIRef(E + "c"))]


def test_interpolation_evaluated_once(run):
    g, _ = run_src(run, textwrap.dedent("""\
        calls = []
        def f():
            calls.append(1)
            return ex:Sensor
        mm = m{ ?s a {f()} }
        list(mm)
        list(mm)
        """))
    assert len(g["calls"]) == 1


# --------------------------------------------------------- first / one / ask

def test_first_none_when_empty(run):
    g, _ = run_src(run, "x = m{ ex:zzz ex:p ?o }.first()\n")
    assert g["x"] is None


def test_one_raises_on_zero_and_many(run):
    g, _ = run_src(run, "mm0 = m{ ex:zzz ex:p ?o }\n"
                        "mm2 = m{ ?s a ex:Sensor }\n"
                        "mm1 = m{ ?s a ex:Autre }\n")
    with pytest.raises(ValueError):
        g["mm0"].one()
    with pytest.raises(ValueError):
        g["mm2"].one()
    assert g["mm1"].one() == URIRef(E + "c")


def test_ask_truth_value_is_lazy(run):
    g, _ = run_src(run, "oui = bool(m{ ex:a a ex:Sensor })\n"
                        "non = bool(m{ ex:a a ex:Zzz })\n")
    assert g["oui"] is True and g["non"] is False


def test_count_consumes_len_fails(run):
    g, _ = run_src(run, "n = m{ ?s a ex:Sensor }.count()\nmm = m{ ?s ?p ?o }\n")
    assert g["n"] == 2
    with pytest.raises(TypeError):
        len(g["mm"])


# ------------------------------------------------------------------ contexte

def test_without_graph_lazy_error(run):
    g, _ = run("mm = m{ ?s ?p ?o }\n")
    with pytest.raises(RuntimeError):
        list(g["mm"])


def test_suffix_applies_to_other_graph(run):
    g, _ = run_src(run, "import rdflib\nvide = rdflib.Graph()\n"
                        "n = m{ ?s ?p ?o }(vide).count()\n")
    assert g["n"] == 0


def test_graph_block_scope(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as outer
        +{ ex:x ex:p 1 }
        def f():
            @graph as inner
            +{ ex:y ex:q 2 }
            return m{ ?s ex:q ?o }.count()
        n_inner = f()
        n_outer = m{ ?s ex:p ?o }.count()
        """))
    assert g["n_inner"] == 1 and g["n_outer"] == 1


# --------------------------------------------------- -{ } à variables (D016)

def test_remove_single_pattern_joker(run):
    g, _ = run_src(run, "-{ ?s a ex:Sensor }\nn = len(g)\n")
    assert g["n"] == 5          # 7 triplets - 2 'a ex:Sensor'


def test_remove_delete_where_join(run):
    g, _ = run_src(run, "-{ ?s a ex:Sensor ; ex:v ?v }\nn = len(g)\n")
    # retire les 2 'a' et les 2 'v' des Sensors ; ex:c intact, label intact
    assert g["n"] == 3


# -------------------------------------------------------------- lexical

def test_m_space_brace_stays_python(run):
    g, r = run("m = {1: 2}\nx = m [1]\n")
    assert g["x"] == 2
    assert "match" not in r.code


def test_m_as_variable_name_untouched(run):
    g, _ = run("m = 5\ny = m + 1\n")
    assert g["y"] == 6
