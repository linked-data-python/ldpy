"""An rdflib property path in an island (record ldpy/012).

It used to become Literal('Path(...)') and match nothing, without a word.
It is now read in the predicate position of m{ }, where graph.triples()
evaluates it, and refused everywhere else."""

import textwrap

import pytest
from rdflib import Namespace

from ldpy.runtime import node, pnode

EX = Namespace("http://e/")

DATA = """\
from rdflib import Namespace
EX = Namespace("http://e/")
@prefix ex: <http://e/> .
@graph as g
+{ ex:a ex:p ex:b . ex:b ex:q ex:c . ex:d ex:p ex:b . ex:c ex:p ex:e }
"""


def src(body):
    return DATA + textwrap.dedent(body)


def test_a_path_in_predicate_position_reads_as_g_value_does(run):
    env, _ = run(src("""\
        path = EX.p / EX.q
        got = m{ ex:a {path} ?o }.first()
        want = g.value(EX.a, path)
        subjects = sorted(m{ ?s {path} ex:c })
        """))
    assert env["got"] == env["want"] == EX.c
    assert env["subjects"] == [EX.a, EX.d]


def test_a_path_joins_and_counts_like_any_predicate(run):
    env, _ = run(src("""\
        one_or_more = EX.p * "+"
        n = m{ ?s {one_or_more} ?o }.count()
        want = len(list(g.triples((None, one_or_more, None))))
        hop = [(s, o) for s, x, o in m{ ?s {EX.p / EX.q} ?x . ?x ex:p ?o }]
        absent = bool(m{ ex:d {EX.q / EX.p} ?o })
        """))
    assert env["n"] == env["want"] == 3
    assert env["hop"] == [(EX.a, EX.e), (EX.d, EX.e)]
    assert env["absent"] is False


@pytest.mark.parametrize("body", [
    "m{ {EX.p / EX.q} ex:p ?o }.first()",          # subject
    "m{ ex:a ex:p {EX.p / EX.q} }.first()",        # object
    "+{ ex:a {EX.p / EX.q} ex:c }",
    "-{ ex:a {EX.p / EX.q} ex:c }",
    "x = g{ ex:a {EX.p / EX.q} ex:c }",
])
def test_a_path_anywhere_else_raises(run, body):
    with pytest.raises(TypeError, match="property path"):
        run(src(body + "\n"))


def test_node_refuses_a_path_and_pnode_keeps_it():
    path = EX.p / EX.q
    with pytest.raises(TypeError, match="property path"):
        node(path)
    assert pnode(path) is path
    assert pnode("x") == node("x")
