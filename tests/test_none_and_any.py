"""An interpolated None raises; ldpy.ANY is the wildcard (record ldpy/012).

None used to become Literal('None'): a pattern received as data,
`(s, p, None)`, then removed nothing and matched nothing, without a word."""

import textwrap

import pytest
from rdflib import Graph, Literal, URIRef

import ldpy
from ldpy.runtime import ANY, node


EX = "http://e/"
DATA = """\
import ldpy
@prefix ex: <http://e/> .
@graph as g
+{ ex:a ex:p 1 , 2 ; ex:q 3 . ex:b ex:p 4 }
"""


def src(body):
    return DATA + textwrap.dedent(body)


def test_node_of_none_raises_and_names_both_spellings():
    with pytest.raises(TypeError) as exc:
        node(None)
    msg = str(exc.value)
    assert "?any" in msg and "[]" in msg and "ldpy.ANY" in msg


def test_any_is_exported_and_passes_through_node():
    assert ldpy.ANY is ANY
    assert node(ANY) is ANY
    assert repr(ANY) == "ldpy.ANY"
    from ldpy import ANY as again
    assert again is ANY


def test_remove_with_an_interpolated_none_raises_and_removes_nothing(run):
    with pytest.raises(TypeError):
        run(src("""\
            s, o = ex:a, None
            -{ {s} ex:p {o} }
            """))


def test_remove_with_any_is_rdflib_wildcard(run):
    g, _ = run(src("""\
        o = ldpy.ANY
        -{ ex:a ex:p {o} }
        left = sorted(str(t[2]) for t in g)
        """))
    assert g["left"] == ["3", "4"]


def test_a_pattern_received_as_data_removes(run):
    """The corpus case: a helper that receives `(s, p, None)`."""
    g, _ = run(src("""\
        def delete(pattern):
            s, p, o = (ldpy.ANY if t is None else t for t in pattern)
            -{ {s} {p} {o} }
        delete((ex:a, None, None))
        left = len(g)
        """))
    assert g["left"] == 1


def test_match_with_an_interpolated_none_raises(run):
    with pytest.raises(TypeError):
        run(src("""\
            x = None
            found = list(m{ ?s ex:p {x} })
            """))


def test_match_with_any_matches_anything_and_is_not_projected(run):
    g, _ = run(src("""\
        w = ldpy.ANY
        subjects = sorted(str(s) for s in m{ ?s ex:p {w} })
        rows = list(m{ ?s {w} {w} })
        """))
    assert g["subjects"] == [EX + "a", EX + "a", EX + "b"]
    # two ANY are two wildcards, not one shared variable
    assert len(g["rows"]) == 4
    assert all(not hasattr(r, "_fields") or r._fields == ["s"]
               for r in g["rows"])


def test_delete_where_with_any(run):
    """Several patterns sharing a variable: DELETE WHERE, ANY a fresh
    wildcard in each place — every ex:p of a subject that has an ex:q."""
    g, _ = run(src("""\
        w = ldpy.ANY
        -{ ?s ex:q {w} . ?s ex:p {w} }
        left = sorted(str(t[2]) for t in g)
        """))
    assert g["left"] == ["4"]


@pytest.mark.parametrize("island", [
    "+{ ex:a ex:r {w} }",
    "h = g{ ex:a ex:r {w} }",
])
def test_any_cannot_be_written(run, island):
    with pytest.raises(TypeError) as exc:
        run(src("w = ldpy.ANY\n" + island + "\n"))
    assert "wildcard" in str(exc.value)


def test_add_with_none_raises_and_writes_nothing(run):
    g, _ = run(src(textwrap.dedent("""\
        x = None
        try:
            +{ ex:c ex:p 1 ; ex:p {x} }
        except TypeError:
            raised = True
        """)))
    assert g["raised"] and len(g["g"]) == 4


def test_none_in_bindings_is_unbound(run):
    """A CSV row with an empty cell: the triple that needs it is dropped,
    as an unbound variable's triple is."""
    g, _ = run(textwrap.dedent("""\
        @prefix ex: <http://e/> .
        @graph as out
        rows = [{"s": ex:a, "v": 1}, {"s": ex:b, "v": None}]
        for @bindings in rows:
            +{ ?s ex:v ?v ; ex:seen true }
        values = sorted(str(t[2]) for t in out.triples((None, ex:v, None)))
        seen = len(list(out.triples((None, ex:seen, None))))
        """))
    assert g["values"] == ["1"]
    assert g["seen"] == 2


def test_none_in_call_suffix_bindings_is_unbound(run):
    g, _ = run(src("""\
        found = list(m{ ex:a ex:p ?o }(g, {"o": None}))
        """))
    assert sorted(g["found"]) == [Literal(1), Literal(2)]


def test_sparql_interpolated_none_raises_any_leaves_unbound(run):
    g, _ = run(src("""\
        w = ldpy.ANY
        n = len(list(s{ SELECT ?s WHERE { ?s ex:p {w} } }))
        """))
    assert g["n"] == 3
    g, _ = run(src("""\
        x = None
        q = s{ SELECT ?s WHERE { ?s ex:p {x} } }
        """))
    with pytest.raises(TypeError):
        list(g["q"])
