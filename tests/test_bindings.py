"""@bindings et gabarits de graphes : e{ ... } dans g{ ... } (fiche 017)."""

import textwrap

import pytest
from rdflib import URIRef, Literal, Variable

from ldpy.transpiler import transpile, LdpySyntaxError
from ldpy.runtime import Bindings


E = "http://e/"


# ------------------------------------------------------------- Bindings

def test_bindings_is_a_dict():
    b = Bindings()
    b[Variable("x")] = 1
    assert b["x"] == Literal(1)
    assert b[Variable("x")] == Literal(1)
    assert "x" in b and Variable("x") in b
    b.update({"y": "deux"})
    assert b["y"] == Literal("deux")
    del b[Variable("x")]
    assert "x" not in b
    assert dict(**b) == {"y": Literal("deux")}


def test_bindings_coerces_values():
    b = Bindings({"n": 3, "s": "txt", "u": URIRef(E + "a")})
    assert b["n"] == Literal(3)
    assert b["s"] == Literal("txt")
    assert b["u"] == URIRef(E + "a")


def test_bindings_rejects_non_mapping():
    with pytest.raises(TypeError):
        Bindings([1, 2])


# ------------------------------------------------------- déclarations

def test_bindings_as_creates(run):
    g, _ = run("@bindings as b\nb[?x] = 1\nv = b['x']\n")
    assert g["v"] == Literal(1)


def test_bindings_designates(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        sol = {"x": ex:a}
        @bindings sol
        g = g{ ?x ex:p 1 }
        """))
    assert (URIRef(E + "a"), URIRef(E + "p"), Literal(1)) in g["g"]


def test_decorator_named_bindings_untouched():
    r = transpile("def bindings(f):\n    return f\n@bindings\ndef f():\n    pass\n")
    assert "@bindings\n" in r.code


def test_bindings_scope_is_block(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        def f():
            @bindings {"x": ex:a}
            return g{ ?x ex:p 1 }
        inner = f()
        outer = g{ ?x ex:p 1 }
        """))
    assert len(g["inner"]) == 1
    # hors du bloc : gabarit (la variable reste un terme)
    assert next(iter(g["outer"]))[0] == Variable("x")


# --------------------------------------------------- gabarit / instancié

def test_template_without_bindings_unchanged(run):
    g, _ = run("@prefix ex: <http://e/> .\ntpl = g{ ?s ex:p ?o }\n")
    s, p, o = next(iter(g["tpl"]))
    assert s == Variable("s") and o == Variable("o")


def test_instantiated_with_bindings_discards_unbound(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @bindings {"x": ex:a, "v": 3}
        g = g{ ?x ex:val ?v . ?x ex:autre ?absent }
        """))
    assert len(g["g"]) == 1
    assert (URIRef(E + "a"), URIRef(E + "val"), Literal(3)) in g["g"]


def test_bnodes_fresh_per_graph(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @bindings {"v": 1}
        g1 = g{ [ ex:p ?v ] }
        g2 = g{ [ ex:p ?v ] }
        b1 = next(iter(g1))[0]
        b2 = next(iter(g2))[0]
        """))
    assert g["b1"] != g["b2"]


# ------------------------------------------------- e{ } en position de terme

def test_expression_term_evaluated(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @bindings {"v": 10}
        g = g{ ex:s ex:double e{ ?v * 2 } }
        """))
    assert next(iter(g["g"]))[2] == Literal(20)


def test_expression_term_stays_deferred_in_template(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        tpl = g{ ex:s ex:p e{ ?v + 1 } }
        """))
    from ldpy.sparql import Expression
    assert isinstance(next(iter(g["tpl"]))[2], Expression)


def test_expression_error_discards_triple(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @bindings {"v": "pas-un-nombre"}
        g = g{ ex:s ex:p e{ ?v * 2 } . ex:s ex:q 1 }
        """))
    assert len(g["g"]) == 1


def test_eiri_term(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @bindings {"n": "Ana Lu"}
        g = g{ ex:s ex:p e<http://e/p/{?n}> }
        """))
    assert next(iter(g["g"]))[2] == URIRef("http://e/p/Ana%20Lu")


def test_expression_in_match_refused():
    with pytest.raises(LdpySyntaxError):
        transpile("x = m{ ?s ?p e{ ?v + 1 } }\n")


# ------------------------------------------------------ for @bindings in

def test_for_bindings_over_match(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://ex/> .
        @graph as src
        +{ ex:c1 ex:reading 10 . ex:c2 ex:reading 25 }
        @graph as out
        for @bindings in m{ ?s ex:reading ?v }(src):
            +{ ?s ex:hasValue e{ ?v * 2 } }
        vals = sorted(int(o) for s, o in m{ ?s ex:hasValue ?o }(out))
        """))
    assert g["vals"] == [20, 50]


def test_for_bindings_over_dicts(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        rows = [{"id": "a"}, {"id": "b"}]
        for @bindings in rows:
            +{ ex:{"x"} ex:n ?id }
        n = len(g)
        """))
    assert g["n"] == 2


def test_for_bindings_as_named(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        for @bindings as b in [{"id": "a", "nom": "Alpha"}]:
            b[?extra] = 1
            +{ ex:{str(b["id"])} ex:nom ?nom ; ex:extra ?extra }
        survit = b["nom"]
        """))
    assert g["survit"] == Literal("Alpha")
    assert len(g["g"]) == 2


def test_for_bindings_scope_closes_after_loop(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        for @bindings in [{"v": 1}]:
            pass
        tpl = g{ ex:s ex:p ?v }
        """))
    # après la boucle : gabarit, la variable reste un terme
    assert next(iter(g["tpl"]))[2] == Variable("v")


def test_for_bindings_nested_masking(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        out = []
        for @bindings in [{"v": 1}]:
            for @bindings in [{"v": 2}]:
                out.append(g{ ex:s ex:p ?v })
            out.append(g{ ex:s ex:p ?v })
        a = next(iter(out[0]))[2]
        b = next(iter(out[1]))[2]
        """))
    assert g["a"] == Literal(2) and g["b"] == Literal(1)


def test_for_bindings_non_mapping_raises(run):
    g, r = run("collected = []\n")
    src = "for @bindings in [1]:\n    pass\n"
    code = transpile(src).code
    with pytest.raises(TypeError):
        exec(compile(code, "<t>", "exec"), {"__name__": "t"})


def test_for_bindings_break_continue(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        for @bindings in [{"v": 1}, {"v": 2}, {"v": 3}]:
            +{ ex:s ex:p ?v }
            break
        n = len(g)
        """))
    assert g["n"] == 1


# ------------------------------------------------------------ s{ } liaisons

def test_sparql_receives_current_bindings(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        +{ ex:a ex:v 1 . ex:b ex:v 2 }
        @bindings {"s": ex:a}
        rows = list(s{ SELECT ?v WHERE { ?s ex:v ?v } })
        """))
    assert [tuple(r) for r in g["rows"]] == [(Literal(1),)]
