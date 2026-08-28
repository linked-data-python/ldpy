"""Graphe courant : @graph, +{ ... }, -{ ... } (fiche 014)."""

import textwrap

import pytest
from rdflib import Graph, URIRef, Literal

from ldpy.transpiler import transpile, LdpySyntaxError


E = "http://e/"


def T(src):
    return transpile(textwrap.dedent(src))


@pytest.fixture
def run(run):
    return run


# ------------------------------------------------------------ formes @graph

def test_graph_as_creates(run):
    g, _ = run("@graph as g\n")
    assert isinstance(g["g"], Graph)
    assert len(g["g"]) == 0


def test_graph_iri_as_creates_named(run):
    g, _ = run("@graph <http://e/g1> as g\n")
    assert g["g"].identifier == URIRef(E + "g1")


def test_graph_pname_as(run):
    g, _ = run("@prefix ex: <http://e/> .\n@graph ex:g1 as g\n")
    assert g["g"].identifier == URIRef(E + "g1")


def test_graph_firi_as(run):
    g, _ = run('k = "g9"\n@graph f<http://e/{k}> as g\n')
    assert g["g"].identifier == URIRef(E + "g9")


def test_graph_designates_expression(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        import rdflib
        G = rdflib.Graph()
        @graph G
        +{ ex:s ex:p 1 }
        """))
    assert len(g["G"]) == 1


def test_graph_designation_never_creates(run):
    """Sans 'as', @graph ne crée jamais rien : l'expression est évaluée."""
    g, r = run("import rdflib\nG = rdflib.Graph()\n@graph G\n")
    assert "new_graph" not in [l for l in r.code.split("\n") if "(G)" in l][0]


def test_decorator_named_graph_untouched():
    r = T("""\
        def graph(f):
            return f
        @graph
        def f():
            pass
        """)
    assert "@graph\n" in r.code


def test_decorator_call_untouched():
    r = T("""\
        def graph(x):
            return lambda f: f
        @graph(1)
        def f():
            pass
        """)
    assert "@graph(1)" in r.code


# ----------------------------------------------------------------- +{ } -{ }

def test_add_and_remove(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        +{ ex:s ex:p 1 ; ex:q 2 }
        -{ ex:s ex:q 2 }
        """))
    assert len(g["g"]) == 1
    assert (URIRef(E + "s"), URIRef(E + "p"), Literal(1)) in g["g"]


def test_add_in_loop(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        for i in range(3):
            +{ ex:s ex:n {i} }
        """))
    assert len(g["g"]) == 3


def test_add_multiline_island(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        +{ ex:s ex:p 1 ;
              ex:q "deux"@fr ;
              ex:r [ ex:v 3 ] }
        """))
    assert len(g["g"]) == 4


def test_remove_with_joker_variable(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        +{ ex:s ex:p 1 ; ex:p 2 ; ex:q 3 }
        -{ ex:s ex:p ?any }
        """))
    assert len(g["g"]) == 1


def test_add_unbound_variable_discards_triple(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        +{ ex:s ex:p 1 . ?x ex:q 2 }
        """))
    assert len(g["g"]) == 1


def test_python_minus_set_untouched(run):
    g, r = run("keys = {1, 2} - {2}\nx = -{1}.pop()\n")
    assert g["keys"] == {1}
    assert g["x"] == -1


def test_plus_brace_in_operand_position_untouched():
    """'+{' hors position d'instruction reste du Python."""
    r = T("x = +{1: 2}[1]\n")
    assert "add_to" not in r.code


def test_add_without_graph_is_error():
    with pytest.raises(LdpySyntaxError) as exc:
        T("@prefix ex: <http://e/> .\n+{ ex:s ex:p 1 }\n")
    assert "@graph" in str(exc.value)


def test_readonly_property_target(run):
    """Défaut 4 de la fiche 012 : une propriété en lecture seule est
    écrivable, add_to n'assigne pas."""
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        import rdflib
        class N:
            def __init__(self):
                self._g = rdflib.Graph()
            @property
            def assertion(self):
                return self._g
        n = N()
        @graph n.assertion
        +{ ex:s ex:p 1 }
        """))
    assert len(g["n"].assertion) == 1


def test_module_global_graph_in_function(run):
    """Défaut 4 : un graphe global de module s'écrit sans 'global'."""
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as obs
        def record(v):
            +{ ex:s ex:v {v} }
        record(1)
        record(2)
        """))
    assert len(g["obs"]) == 2


# ---------------------------------------------------------------- portée

def test_graph_scope_is_block(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as outer
        def f():
            @graph as inner
            +{ ex:a ex:b 1 }
            return inner
        r = f()
        +{ ex:c ex:d 2 }
        """))
    assert len(g["r"]) == 1
    assert len(g["outer"]) == 1


def test_add_after_block_end_is_error():
    with pytest.raises(LdpySyntaxError):
        T("""\
            @prefix ex: <http://e/> .
            def f():
                @graph as g
                +{ ex:a ex:b 1 }
            +{ ex:c ex:d 2 }
            """)


def test_class_attribute_graph(run):
    """@graph as g dans une classe : g devient un attribut de classe —
    comportement voulu (fiche 014, points tranchés)."""
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        class C:
            @graph as store
            +{ ex:s ex:p 1 }
        """))
    assert len(g["C"].store) == 1


# --------------------------------------------------------------- serialisation

def test_new_graph_binds_prefixes(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        +{ ex:s ex:p 1 }
        ttl = g.serialize(format="turtle")
        """))
    assert "@prefix ex:" in g["ttl"]
