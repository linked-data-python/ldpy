"""The hover answers on the smallest element — record vscode/108.

A composite island records the terms written inside it, so that hovering a
prefixed name in a forty-line `g{ }` explains that name instead of dumping
the whole translated block.

The first test is the one that matters: the kind a term gets INSIDE an island
is pinned against the kind the transpiler itself gives the SAME term written
outside one, where it labels the segment with no help from us. Nothing else
keeps `_term_kind` and `_g_node` from drifting apart, and drifting quietly is
what a classifier does.
"""

import pytest

from ldpy.lsp import hover as hv
from ldpy.lsp import translate as tr
from ldpy.transpiler import transpile

PROLOGUE = ("@prefix ex: <http://example.org/ns#> .\n"
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
            "v = 1\n")

# term source -> the standalone island the transpiler makes of it
SAME_OUTSIDE = [
    "ex:local",
    "<http://example.org/x>",
    '"hi"@en',
    '"42"^^xsd:integer',
    "?who",
    "f<path/{v}>",
    "f{v}",
    "_:{v}",
    "e{ ?a + 1 }",
    "e<path/{?a}>",
]


def _segments(src):
    return transpile(PROLOGUE + src, "t.ldpy").map.segments


def _island_kinds(src):
    return [s.kind for s in _segments(src) if s.kind.startswith("island:")]


def _graph_parts(src):
    for s in _segments(src):
        if s.kind == "island:graph":
            return s.parts
    raise AssertionError("no graph island in %r" % src)


@pytest.mark.parametrize("term", SAME_OUTSIDE)
def test_term_kind_matches_what_the_transpiler_says_outside(term):
    """Inside an island and outside it, the same term is the same kind."""
    outside = _island_kinds("x = %s\n" % term)[-1]
    inside = [k for k, _, _ in _graph_parts("g1 = g{ ex:s ex:p %s }\n" % term)]
    assert inside[-1] == outside[len("island:"):]


@pytest.mark.parametrize("term,kind", [
    ("42", "literal"), ("2.5", "literal"), ("-7", "literal"),
    ("true", "literal"), ("false", "literal"),
    ('f"{v} deg"@en', "literal"),      # an f-string literal, not f{ }
    ("ex:café", "pname"), ("o-pizza:x", "pname"),
])
def test_forms_with_no_standalone_island(term, kind):
    """Turtle numbers, booleans and Turtle-only names exist only inside an
    island, so they are pinned by hand rather than against a twin."""
    src = "@prefix o-pizza: <http://example.org/p#> .\n"
    parts = _graph_parts(src + "g1 = g{ ex:s ex:p %s }\n" % term)
    assert parts[-1][0] == kind


def test_a_and_composites_have_no_hover_of_their_own():
    """`a`, `[ ]`, `( )` and a `{python}` hole are not terms we describe;
    they fall back to the island, which is the honest answer."""
    parts = _graph_parts("g1 = g{ ex:s a [ ex:p {v} ] }\n")
    assert [k for k, _, _ in parts] == ["pname", "pname"]     # ex:s, ex:p


def test_match_and_addto_record_their_terms_too():
    """One wrapper serves the four islands that share the node parser."""
    src = "@graph as store\n" \
          "m1 = m{ ?s ex:p ?o }\n+{ ex:a ex:b \"c\" }\n-{ ex:a ?p ?o }\n"
    kinds = {s.kind: [k for k, _, _ in s.parts]
             for s in _segments(src) if s.parts}
    assert kinds["island:match"] == ["var", "pname", "var"]
    assert kinds["island:addto"] == ["pname", "pname", "literal"]
    assert kinds["island:removefrom"] == ["pname", "var", "var"]


# --------------------------------------------------------------- selection

def _seg(src, kind="island:graph"):
    return [s for s in _segments(src) if s.kind == kind][0]


def test_the_innermost_element_wins():
    src = "g1 = g{ ex:subject ex:pred <http://example.org/o> }\n"
    seg = _seg(src)
    line = 3                                    # after the 3-line prologue
    # on `ex:subject`
    kind, _, gen = tr.island_target(seg, line, 10)
    assert kind == "pname" and "ns#subject" in gen
    # on the IRI
    kind, _, gen = tr.island_target(seg, line, 30)
    assert kind == "iri" and "example.org/o" in gen
    # on the braces themselves: the island answers
    kind, _, gen = tr.island_target(seg, line, 18)   # the space
    assert kind == "island:graph" and gen is None


def test_a_nested_blank_node_gives_the_inner_term():
    src = "g1 = g{ ex:s ex:p [ ex:q ex:deep ] }\n"
    seg = _seg(src)
    kind, _, gen = tr.island_target(seg, 3, 27)   # inside `ex:deep`
    assert kind == "pname" and "ns#deep" in gen


def test_hover_renders_the_term_not_the_island():
    seg = _seg("g1 = g{ ex:s ex:p <http://example.org/o> }\n")
    kind, _, gen = tr.island_target(seg, 3, 20)
    text = hv.render(kind, gen)
    assert text.startswith("```ldpy\n(term) <IRI> -> URIRef")
    assert "_ldpy_.URIRef" in text
    assert "_ldpy_.graph(" not in text            # not the whole island


def test_an_island_without_parts_still_hovers():
    """`s{ }` has no parts (its terms are the SPARQL parser's), and a hover
    on it must still say what it is."""
    seg = _seg("q = s{ SELECT ?s WHERE { ?s ex:p ?o } }\n", "island:sparql")
    assert seg.parts == []
    kind, _, gen = tr.island_target(seg, 3, 10)
    assert kind == "island:sparql" and gen is None
