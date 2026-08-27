"""Sémantique @prefix/@base (fiche 004) et ordre d'évaluation (fiche 003)."""

import pytest
from rdflib import URIRef

from ldpy.transpiler import transpile, LdpySyntaxError


P = "@prefix ex: <http://example.org/ns#> .\n"


def test_prefix_lexical_scope_from_declaration(run):
    src = "@prefix a: <http://a/> .\nx = a:t\n@prefix a: <http://b/> .\ny = a:t\n"
    g, result = run(src)
    assert g["x"] == URIRef("http://a/t")
    assert g["y"] == URIRef("http://b/t")
    assert [str(w) for w in result.warnings] == \
        [w for w in map(str, result.warnings) if "redéclaration" in w]
    assert any("redéclaration" in str(w) for w in result.warnings)


def test_prefix_in_if_false_scoped_to_block(run):
    """Fiche 004 (révision) : la portée est le bloc — un préfixe déclaré dans
    un if ne s'applique qu'au corps du if ; après le bloc, il est inconnu."""
    src = """\
if False:
    @prefix cond: <http://cond/> .
    y = cond:in_scope
z = 1
"""
    g, result = run(src)
    assert "cond" not in g["__namespaces__"]   # la branche n'a pas tourné
    r2 = transpile("if False:\n    @prefix c: <http://c/> .\nx = c:y\n")
    assert "x = c:y" in r2.code                # hors de portée : intact
    assert any("hors de portée" in str(w) for w in r2.warnings)


def test_prefix_in_loop_scoped_to_block(run):
    src = """\
results = []
for i in range(3):
    @prefix loop: <http://loop/> .
    results.append(loop:item)
"""
    g, result = run(src)
    assert g["results"] == [URIRef("http://loop/item")] * 3
    assert result.warnings == []               # plus de warning « dans un bloc »


def test_base_applies_lexically(run):
    src = """\
x = <rel>
@base <http://example.org/d/> .
y = <rel>
@base <sub/> .
z = <rel>
"""
    g, _ = run(src)
    assert g["x"] == URIRef("rel")
    assert g["y"] == URIRef("http://example.org/d/rel")
    assert g["z"] == URIRef("http://example.org/d/sub/rel")


def test_no_leak_between_files(run):
    run(P + "x = ex:a\n")
    result2 = transpile("y = 1\n")   # nouveau fichier : table vierge
    assert result2.code == "y = 1\n"
    try:
        transpile("y = g{ ex:a ex:b 1 }\n")
    except Exception as e:
        assert "ex" in str(e)
    else:
        raise AssertionError("le préfixe ne doit pas fuiter entre fichiers")


def test_namespaces_dict_at_runtime(run):
    g, _ = run(P + "x = ex:a\n")
    assert str(g["__namespaces__"]["ex"]) == "http://example.org/ns#"


def test_lazy_evaluation_short_circuit(run):
    """fiche 003 : cond or g{...} ne doit PAS évaluer les interpolations."""
    src = P + """\
calls = []
def side_effect():
    calls.append(1)
    return 5
r = True or g{ ex:s ex:p {side_effect()} }
n = len(calls)
"""
    g, _ = run(src)
    assert g["n"] == 0
    assert g["r"] is True


def test_evaluation_order_left_to_right(run):
    src = P + """\
order = []
def t(v):
    order.append(v)
    return v
gr = g{ ex:s ex:p {t(1)} ; ex:q {t(2)} . ex:r ex:u {t(3)} }
"""
    g, _ = run(src)
    assert g["order"] == [1, 2, 3]


def test_conditional_islands(run):
    src = P + "flag = False\nx = ex:a if flag else ex:b\n"
    g, _ = run(src)
    assert g["x"] == URIRef("http://example.org/ns#b")


def test_islands_in_comprehension(run):
    src = P + "l = [ g{ ex:s ex:p {i} } for i in range(3) ]\n"
    g, _ = run(src)
    assert [len(x) for x in g["l"]] == [1, 1, 1]


def test_prelude_after_docstring(run):
    src = '"""Docstring du module."""\nx = <http://e/a>\n'
    g, result = run(src)
    assert g["__doc__"] == "Docstring du module."
    first_line = result.code.split("\n")[0]
    assert first_line == '"""Docstring du module."""'


def test_prelude_after_future_import():
    src = 'from __future__ import annotations\nx = <http://e/a>\n'
    code = transpile(src).code
    lines = code.split("\n")
    assert lines[0].startswith("from __future__")
    assert lines[1].startswith("import ldpy.runtime")


def test_prelude_absent_without_islands():
    src = "x = 1\n"
    assert "ldpy.runtime" not in transpile(src).code


def test_shared_interpolated_subject_evaluated_once(run):
    """Un sujet interpolé partagé par une liste de propriétés ne doit être
    évalué qu'une fois (sinon chaque triplet aurait un sujet différent)."""
    src = P + """\
calls = []
def sid():
    calls.append(1)
    return "s%d" % len(calls)
gr = g{ ex:{sid()} ex:p 1 ; ex:q 2 ; ex:r 3 }
subjects = {str(s) for s, _, _ in gr}
"""
    g, _ = run(src)
    assert len(g["calls"]) == 1
    assert len(g["subjects"]) == 1
    assert len(g["gr"]) == 3


def test_shared_fnode_object_evaluated_once(run):
    src = P + """\
n = []
def v():
    n.append(1)
    return len(n)
gr = g{ ex:a ex:p ?{ v() } . ex:b ex:q ?{ v() } }
"""
    g, _ = run(src)
    assert len(g["n"]) == 2   # deux occurrences distinctes : deux évaluations


def test_repeated_subject_still_one_bnode(run):
    src = P + """\
sensor = "t1"
gr = g{ f<http://e/{sensor}> ex:p 1 ; ex:q 2 }
subjects = {str(s) for s, _, _ in gr}
"""
    g, _ = run(src)
    assert g["subjects"] == {"http://e/t1"}
