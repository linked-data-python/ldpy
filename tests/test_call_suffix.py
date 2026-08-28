"""Le suffixe d'appel : donner explicitement son contexte à un îlot
(fiche 019). Une seule règle pour six îlots : graphe d'abord, binding
ensuite, tous deux facultatifs, bindings= pour ne donner que le second."""

import textwrap

import pytest
from rdflib import URIRef, Literal, Variable

from ldpy.transpiler import transpile


E = "http://e/"


def X(run, src):
    return run("@prefix ex: <http://e/> .\n" + textwrap.dedent(src))


# ------------------------------------------------------- îlots-instructions

def test_add_with_explicit_graph(run):
    g, _ = X(run, """\
        import rdflib
        cible = rdflib.Graph()
        +{ ex:s ex:p 1 }(cible)
        """)
    assert len(g["cible"]) == 1


def test_add_with_graph_and_bindings(run):
    g, _ = X(run, """\
        import rdflib
        cible = rdflib.Graph()
        +{ ex:s ex:p ?v }(cible, {"v": 7})
        """)
    assert next(iter(g["cible"]))[2] == Literal(7)


def test_add_with_bindings_keyword_only(run):
    g, _ = X(run, """\
        @graph as g
        +{ ex:s ex:p ?v }(bindings={"v": 3})
        """)
    assert next(iter(g["g"]))[2] == Literal(3)


def test_remove_with_explicit_graph(run):
    g, _ = X(run, """\
        import rdflib
        cible = rdflib.Graph()
        +{ ex:s ex:p 1 ; ex:q 2 }(cible)
        -{ ex:s ex:p ?any }(cible)
        """)
    assert len(g["cible"]) == 1


def test_suffix_does_not_change_declared_context(run):
    g, _ = X(run, """\
        import rdflib
        autre = rdflib.Graph()
        @graph as g
        +{ ex:a ex:p 1 }(autre)
        +{ ex:b ex:q 2 }
        """)
    assert len(g["autre"]) == 1 and len(g["g"]) == 1


def test_suffix_beats_declared_context(run):
    g, _ = X(run, """\
        @graph as g
        @bindings {"v": 1}
        import rdflib
        autre = rdflib.Graph()
        +{ ex:s ex:p ?v }(autre, {"v": 2})
        """)
    assert len(g["g"]) == 0
    assert next(iter(g["autre"]))[2] == Literal(2)


def test_plus_call_without_suffix_position_is_python(run):
    """'(' non collé : pas un suffixe — le Python reste du Python."""
    g, _ = run("d = {1: 2}\nx = +{1: 3}[1]\n")
    assert g["x"] == 3


# ------------------------------------------------------ îlots-expressions

def test_template_graph_called_with_bindings(run):
    g, _ = X(run, """\
        tpl = g{ ?s ex:p ?v }
        g1 = tpl({"s": ex:a, "v": 1})
        g2 = tpl({"s": ex:b, "v": 2})
        """)
    assert (URIRef(E + "a"), URIRef(E + "p"), Literal(1)) in g["g1"]
    assert (URIRef(E + "b"), URIRef(E + "p"), Literal(2)) in g["g2"]
    assert len(g["g1"]) == 1


def test_template_bnodes_fresh_per_call(run):
    g, _ = X(run, """\
        tpl = g{ [ ex:p ?v ] }
        b1 = next(iter(tpl({"v": 1})))[0]
        b2 = next(iter(tpl({"v": 1})))[0]
        """)
    assert g["b1"] != g["b2"]


def test_template_unbound_discarded_on_call(run):
    g, _ = X(run, """\
        tpl = g{ ex:s ex:p ?v . ex:s ex:q 1 }
        inst = tpl({})
        """)
    assert len(g["inst"]) == 1


def test_expression_call_form_unchanged(run):
    """e{ E }(b) : la forme d'appel de la fiche 007, inchangée."""
    g, _ = run("adult = e{ ?age >= 18 }\nr = adult.ebv({'age': 20})\n")
    assert g["r"] is True


def test_match_and_sparql_suffix(run):
    g, _ = X(run, """\
        @graph as g
        +{ ex:a a ex:T }
        import rdflib
        vide = rdflib.Graph()
        n1 = m{ ?s a ex:T }(vide).count()
        n2 = len(list(s{ SELECT ?s WHERE { ?s a ex:T } }(vide)))
        n3 = m{ ?s a ex:T }.count()
        """)
    assert g["n1"] == 0 and g["n2"] == 0 and g["n3"] == 1


def test_match_initial_bindings_are_projected(run):
    """m{ P }(g, b) : les liaisons initiales contraignent ET se retrouvent
    dans les solutions (comme initBindings)."""
    g, _ = X(run, """\
        @graph as g
        +{ ex:a ex:v 1 . ex:b ex:v 2 }
        rows = list(m{ ?s ex:v ?v }(g, {"s": ex:a}))
        """)
    assert g["rows"] == [(URIRef(E + "a"), Literal(1))]
