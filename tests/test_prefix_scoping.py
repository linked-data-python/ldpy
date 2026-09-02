"""Portée par bloc de @prefix/@base (portée par bloc, révision du 2026-08-27).

La portée d'une déclaration est le bloc englobant
(suite d'un if/for/while/try, corps de fonction, corps de classe) ; au
top-level, le reste du fichier. Les blocs plus profonds voient les
déclarations englobantes ; la sortie du bloc restaure l'état antérieur.
"""

import pytest
from rdflib import URIRef

from ldpy.transpiler import transpile, LdpySyntaxError


A = "http://a/"
B = "http://b/"


# ---------------------------------------------------------------- fonctions

def test_function_local_prefix_visible_inside(run):
    src = """\
def f():
    @prefix ex: <http://a/> .
    return ex:t
r = f()
"""
    g, _ = run(src)
    assert g["r"] == URIRef(A + "t")


def test_function_local_prefix_invisible_after():
    """Hors de portée, le texte reste du Python intact (R3) et un warning
    « hors de portée » est émis — pas une transformation silencieuse."""
    src = """\
def f():
    @prefix ex: <http://a/> .
    return ex:t
x = ex:t
"""
    r = transpile(src)
    assert "x = ex:t" in r.code                      # non transformé
    assert any("hors de portée" in str(w) for w in r.warnings)


def test_shadowing_in_function_restored_after(run):
    src = """\
@prefix ex: <http://a/> .
def f():
    @prefix ex: <http://b/> .
    return ex:t
inner = f()
outer = ex:t
"""
    g, _ = run(src)
    assert g["inner"] == URIRef(B + "t")
    assert g["outer"] == URIRef(A + "t")


def test_outer_prefix_visible_in_nested_blocks(run):
    src = """\
@prefix ex: <http://a/> .
def f(flag):
    if flag:
        for _ in range(1):
            return ex:deep
    return ex:shallow
r = f(True)
"""
    g, _ = run(src)
    assert g["r"] == URIRef(A + "deep")


# ---------------------------------------------------------------- blocs if

def test_sibling_if_blocks_are_isolated():
    src = """\
if a:
    @prefix p: <http://a/> .
    x = p:t
if b:
    y = p:t
"""
    r = transpile(src)
    assert "x = _ldpy_.URIRef" in r.code             # dans le bloc : transformé
    assert "y = p:t" in r.code                       # bloc frère : intact
    assert any("hors de portée" in str(w) for w in r.warnings)


def test_else_clause_is_a_different_block():
    src = """\
if a:
    @prefix p: <http://a/> .
    x = p:t
else:
    y = p:t
"""
    r = transpile(src)
    assert "y = p:t" in r.code
    assert any("hors de portée" in str(w) for w in r.warnings)


def test_deeper_declaration_pops_before_shallower_one(run):
    src = """\
@prefix p: <http://a/> .
def f():
    @prefix p: <http://b/> .
    if True:
        @prefix p: <http://c/> .
        deep = p:t
    mid = p:t
    return deep, mid
deep, mid = f()
top = p:t
"""
    g, _ = run(src)
    assert g["deep"] == URIRef("http://c/t")
    assert g["mid"] == URIRef(B + "t")
    assert g["top"] == URIRef(A + "t")


# ----------------------------------------------------- classes, try, while

def test_class_body_scope(run):
    src = """\
class C:
    @prefix ex: <http://a/> .
    TERM = ex:t
after_exists = True
"""
    g, _ = run(src)
    assert g["C"].TERM == URIRef(A + "t")
    r = transpile("class C:\n    @prefix e: <http://a/> .\nx = e:t\n")
    assert "x = e:t" in r.code
    assert any("hors de portée" in str(w) for w in r.warnings)


def test_try_except_blocks_isolated():
    src = """\
try:
    @prefix p: <http://a/> .
    x = p:t
except Exception:
    y = p:t
"""
    r = transpile(src)
    assert "y = p:t" in r.code
    assert any("hors de portée" in str(w) for w in r.warnings)


def test_while_body_scope(run):
    src = """\
n = 2
acc = []
while n:
    @prefix w: <http://a/> .
    acc.append(w:t)
    n -= 1
"""
    g, _ = run(src)
    assert g["acc"] == [URIRef(A + "t")] * 2


# ------------------------------------------------------------------- @base

def test_base_scoped_to_block(run):
    src = """\
@base <http://outer/> .
def f():
    @base <http://inner/> .
    return <rel>
inner = f()
outer = <rel>
"""
    g, _ = run(src)
    assert g["inner"] == URIRef("http://inner/rel")
    assert g["outer"] == URIRef("http://outer/rel")


def test_base_relative_to_outer_base_then_restored(run):
    src = """\
@base <http://h/d/> .
def f():
    @base <sub/> .
    return <x>
a = f()
b = <x>
"""
    g, _ = run(src)
    assert g["a"] == URIRef("http://h/d/sub/x")
    assert g["b"] == URIRef("http://h/d/x")


def test_base_without_prior_base_restored_to_none(run):
    src = """\
def f():
    @base <http://in/> .
    return <r>
a = f()
b = <r>
"""
    g, _ = run(src)
    assert g["a"] == URIRef("http://in/r")
    assert g["b"] == URIRef("r")


# ------------------------------------------------- ce qui ne ferme PAS un bloc

def test_blank_lines_and_comments_do_not_close_scope(run):
    src = """\
def f():
    @prefix p: <http://a/> .

# commentaire en colonne zéro

    return p:t
r = f()
"""
    g, _ = run(src)
    assert g["r"] == URIRef(A + "t")


def test_bracket_continuation_at_column_zero_does_not_close_scope(run):
    src = """\
def f():
    @prefix p: <http://a/> .
    x = [
p:t,
    ]
    return x[0]
r = f()
"""
    g, _ = run(src)
    assert g["r"] == URIRef(A + "t")


def test_multiline_graph_does_not_close_scope(run):
    src = """\
def f():
    @prefix p: <http://a/> .
    gr = g{ p:s p:q 1 ;
p:r 2 }
    return gr, p:t
gr, t = f()
"""
    g, _ = run(src)
    assert len(g["gr"]) == 2
    assert g["t"] == URIRef(A + "t")


# ------------------------------------------------------- runtime + top-level

def test_top_level_scope_reaches_end_of_file(run):
    src = "@prefix p: <http://a/> .\n" + "x0 = 0\n" * 5 + "r = p:t\n"
    g, _ = run(src)
    assert g["r"] == URIRef(A + "t")


def test_runtime_namespaces_follow_control_flow(run):
    src = """\
if True:
    @prefix yes: <http://a/> .
    _ = yes:t
if False:
    @prefix no: <http://b/> .
    _ = no:t
"""
    g, _ = run(src)
    assert "yes" in g["__namespaces__"]
    assert "no" not in g["__namespaces__"]


def test_redeclaration_after_use_still_warns(run):
    src = "@prefix p: <http://a/> .\nx = p:t\n@prefix p: <http://b/> .\ny = p:t\n"
    g, result = run(src)
    assert g["x"] == URIRef(A + "t") and g["y"] == URIRef(B + "t")
    assert any("redéclaration" in str(w) for w in result.warnings)


def test_shadowing_in_block_is_silent(run):
    """Le shadowing dans un bloc plus profond est légitime : aucun warning.
    (Le warning de redéclaration est réservé au même niveau, règle établie :
    « oui ok » sur la portée par bloc.)"""
    src = """\
@prefix p: <http://a/> .
x = p:t
def f():
    @prefix p: <http://b/> .
    return p:t
y = f()
"""
    g, result = run(src)
    assert g["y"] == URIRef(B + "t")
    assert result.warnings == []


def test_never_declared_prefix_gives_no_warning():
    """Différenciation : un nom jamais déclaré comme préfixe ne déclenche NI
    transformation NI warning — c'est du Python ordinaire (slices, dicts)."""
    r = transpile("d = {foo:bar}\nx = arr[i:j]\n")
    assert r.warnings == []
    assert r.code == "d = {foo:bar}\nx = arr[i:j]\n"

# --------------------------------------------------------------- record 027
# `@prefix` is lexical and yields no Python value, which the corpus study
# showed to be its most attested limit: code that must keep the Namespace as
# an OBJECT — to `g.bind()` it, to export it, to put it in a registry — had
# no translation at all. `as EX` binds that object. A bare `ex:` is still
# never a value (records ldpy/002 and 004).

def test_as_binds_the_namespace_object(run):
    ns, _ = run("@prefix ex: <http://example.org/ns#> as EX .\n"
                "iri = EX.Thing\n"
                "prefixed = ex:Thing\n")
    assert str(ns["EX"]) == "http://example.org/ns#"
    assert ns["iri"] == ns["prefixed"]


def test_as_serves_the_three_forms_the_corpus_needed(run):
    ns, _ = run("from rdflib import Graph\n"
                "@prefix ex: <http://example.org/ns#> as EX .\n"
                "g = Graph()\n"
                "g.bind('ex', EX)\n"
                "registry = {'ex': EX}\n"
                "exported = EX\n")
    assert ("ex", URIRef("http://example.org/ns#")) in list(
        ns["g"].namespaces())
    assert ns["registry"]["ex"] is ns["exported"]


def test_the_prefix_still_works_without_as(run):
    ns, _ = run("@prefix ex: <http://example.org/ns#> .\n"
                "t = ex:Thing\n")
    assert str(ns["t"]) == "http://example.org/ns#Thing"
    assert "EX" not in ns


def test_as_needs_a_name():
    with pytest.raises(LdpySyntaxError) as e:
        transpile("@prefix ex: <http://example.org/> as .\n", "t.ldpy")
    assert "as" in e.value.msg


def test_a_prefix_named_as_something_is_not_an_as_clause(run):
    """`as` must be a whole word: a declaration is not broken by an IRI
    followed by nothing, nor by a name that merely starts with 'as'."""
    ns, _ = run("@prefix ex: <http://example.org/ns#> as assets .\n"
                "t = ex:Thing\n")
    assert str(ns["assets"]) == "http://example.org/ns#"
