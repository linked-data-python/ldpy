"""global et nonlocal sur les déclarations d'îlot (fiche 018).

Règle unique : faire ce que Python fait. La déclaration s'installe dans la
portée visée ; nonlocal réutilise la variable de la liaison englobante.
"""

import textwrap

import pytest
from rdflib import URIRef, Literal, Variable

from ldpy.transpiler import transpile, LdpySyntaxError


def T(src):
    return transpile(textwrap.dedent(src))


# --------------------------------------------------------------- @prefix

def test_global_prefix_in_function_visible_after(run):
    g, _ = run(textwrap.dedent("""\
        def declare():
            global @prefix ex: <http://g/> .
        declare()
        def use():
            return ex:t
        x = use()
        """))
    assert g["x"] == URIRef("http://g/t")


def test_global_prefix_at_module_level_no_warning(run):
    g, r = run("global @prefix ex: <http://e/> .\nx = ex:a\n")
    assert g["x"] == URIRef("http://e/a")
    assert not r.warnings


def test_global_prefix_reassignment_no_warning(run):
    """Équivalent de `global x; x = 1` : réassignation voulue, silencieuse."""
    g, r = run(textwrap.dedent("""\
        @prefix ex: <http://a/> .
        y = ex:t
        def f():
            global @prefix ex: <http://b/> .
        f()
        z = ex:t
        """))
    assert not r.warnings
    assert g["y"] == URIRef("http://a/t")
    assert g["z"] == URIRef("http://b/t")


def test_global_computed_prefix(run):
    g, _ = run(textwrap.dedent("""\
        def declare(host):
            global @prefix ex: f<http://{host}/> .
        declare("dyn.org")
        def use():
            return ex:t
        x = use()
        """))
    assert g["x"] == URIRef("http://dyn.org/t")


def test_global_base(run):
    g, _ = run(textwrap.dedent("""\
        def declare():
            global @base <http://base.org/> .
        declare()
        x = <rel>
        """))
    assert g["x"] == URIRef("http://base.org/rel")


# ---------------------------------------------------------------- @graph

def test_global_graph_in_loop_survives_break(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        for cand in range(3):
            if cand == 1:
                global @graph as chosen
                break
        +{ ex:s ex:p {cand} }
        n = len(chosen)
        """))
    assert g["n"] == 1


def test_nonlocal_graph_rebinds_enclosing(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        def outer():
            @graph as g
            def inner():
                nonlocal @graph as g2
                +{ ex:i ex:p 1 }
            inner()
            +{ ex:o ex:q 2 }
            return g
        res = outer()
        """))
    # après inner(), le graphe courant d'outer est le nouveau graphe
    assert len(g["res"]) == 2


def test_nonlocal_graph_designation(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        import rdflib
        def outer():
            @graph as g
            autre = rdflib.Graph()
            def sel():
                nonlocal @graph autre
            sel()
            +{ ex:o ex:q 2 }
            return autre
        res = outer()
        """))
    assert len(g["res"]) == 1


def test_nonlocal_without_enclosing_is_error():
    with pytest.raises(LdpySyntaxError) as exc:
        T("""\
            def f():
                nonlocal @graph as g
            """)
    assert "englobante" in str(exc.value)


def test_nonlocal_prefix_without_enclosing_is_error():
    """Une déclaration au niveau module ne compte pas (comme en Python)."""
    with pytest.raises(LdpySyntaxError):
        T("""\
            @prefix ex: <http://e/> .
            def f():
                nonlocal @prefix ex: <http://f/> .
            """)


# -------------------------------------------------------------- @bindings

def test_global_bindings(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        def setup():
            global @bindings as b
            b[?v] = 5
        setup()
        g = g{ ex:s ex:p ?v }
        """))
    assert next(iter(g["g"]))[2] == Literal(5)


def test_for_bindings_scope_vs_global(run):
    """for @bindings est local au corps ; global @bindings dans le corps
    survit à la boucle."""
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        for @bindings in [{"v": 1}]:
            global @bindings {"v": 99}
        g = g{ ex:s ex:p ?v }
        """))
    assert next(iter(g["g"]))[2] == Literal(99)


# -------------------------------------------------------- Python intact

def test_plain_global_nonlocal_untouched(run):
    g, r = run(textwrap.dedent("""\
        c = 0
        def f():
            global c
            c = 1
        def g_():
            x = 0
            def h():
                nonlocal x
                x = 2
            h()
            return x
        f()
        r = g_()
        """))
    assert g["c"] == 1 and g["r"] == 2
    assert "global c" in r.code and "nonlocal x" in r.code


def test_global_two_names_untouched(run):
    g, _ = run(textwrap.dedent("""\
        a = b = 0
        def f():
            global a, b
            a, b = 1, 2
        f()
        """))
    assert g["a"] == 1 and g["b"] == 2
