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


# ------------------------- expression différée en sujet d'une liste ; ou ,
# Régression : le sujet PARTAGÉ d'une liste prédicat-objet passe par slot(),
# qui appliquait node() à la valeur brute — une expression différée devenait
# donc un Literal portant son propre texte source.

def test_expression_differee_en_sujet_partage(run):
    g, _ = run("@prefix ex: <http://e/> .\n"
               "@graph as out\n"
               "for @bindings in [{'id': 's1'}, {'id': 's2'}]:\n"
               "    +{ e<http://e/{?id}> ex:p 1 ; ex:q 2 }\n")
    out = g["out"]
    subjects = {str(s) for s, p, o in out}
    assert subjects == {"http://e/s1", "http://e/s2"}
    assert len(out) == 4


def test_iri_differee_en_sujet_d_un_graphe(run):
    g, _ = run("@prefix ex: <http://e/> .\n"
               "@bindings as b\n"
               "b['id'] = 'x'\n"
               "gr = g{ e<http://e/{?id}> ex:p 1 ; ex:q 2 }\n")
    assert {str(s) for s, p, o in g["gr"]} == {"http://e/x"}


# ------------------------------------------- la ligne brute (fiche 012, pt 22)

def test_raw_keeps_the_uncoerced_value():
    """`b["v"]` est un terme, `b.raw["v"]` la valeur telle qu'elle est
    arrivée. C'est l'égalité qui rend la coercition dangereuse : le garde le
    plus courant d'un script CSV -> RDF est `if row[col] != "":`."""
    b = Bindings({"note": "", "n": 3})
    assert b["note"] == Literal("") and b["note"] != ""
    assert b.raw["note"] == "" and isinstance(b.raw["note"], str)
    assert b.raw["n"] == 3 and b.raw["n"] is not b["n"]


def test_raw_follows_assignment_and_deletion():
    b = Bindings()
    b[Variable("x")] = "5"
    assert b.raw["x"] == "5" and b["x"] == Literal("5")
    del b["x"]
    assert "x" not in b.raw


def test_raw_is_read_only():
    """On écrit par b[key], qui coerce ET enregistre les deux faces."""
    b = Bindings({"a": 1})
    with pytest.raises(TypeError):
        b.raw["a"] = 2


def test_raw_in_a_for_bindings_loop(run):
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as out
        rows = [{"id": "a", "note": ""}, {"id": "b", "note": "x"}]
        for @bindings as b in rows:
            if b.raw["note"] != "":
                +{ ex:{?id} ex:note ?note }
        """))
    assert len(g["out"]) == 1


def test_raw_of_a_match_solution_is_the_term(run):
    """Une solution de m{ } n'a pas de face « brute » : ses valeurs SONT des
    termes, et raw les rend tels quels plutôt que d'inventer une origine."""
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as g
        +{ ex:a ex:v 1 }
        seen = []
        for @bindings as b in m{ ?s ex:v ?v }:
            seen.append((b["v"], b.raw["v"]))
        """))
    (term, raw), = g["seen"]
    assert term == Literal(1) and raw == term


# --------------------------- nom préfixé à partie locale variable (fiche 017)

def test_pname_with_a_variable_is_deferred(run):
    """`ex:{?id}` rendait `ex:id` — la même IRI à chaque ligne, sans erreur.
    Il s'instancie désormais comme tout autre terme différé."""
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as out
        for @bindings in [{"id": "a"}, {"id": "b"}]:
            +{ ex:{?id} ex:seen true }
        """))
    assert sorted(str(s) for s, p, o in g["out"]) == [E + "a", E + "b"]


def test_pname_with_a_plain_value_stays_immediate(run):
    """Sans variable, aucun binding n'est requis : la décision de Maxime du
    2026-08-29 sur la fiche 017."""
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        x = ex:{"hello"}
        y = ex:{"Sensor".lower()}
        """))
    assert g["x"] == URIRef(E + "hello")
    assert g["y"] == URIRef(E + "sensor")


def test_pname_with_an_unbound_variable_drops_the_triple(run):
    """Erreur seulement à l'évaluation, et la sémantique SPARQL s'applique :
    non lié, le terme manque et le triplet n'est pas écrit."""
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as out
        for @bindings in [{"id": "a"}, {}]:
            +{ ex:{?id} ex:seen true }
        """))
    assert len(g["out"]) == 1


def test_pname_with_a_variable_is_a_template_without_bindings(run):
    """Hors binding, le nom reste différé — comme e{ } en position de terme."""
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        t = g{ ex:{?id} ex:p 1 }
        """))
    assert len(g["t"]) == 1
