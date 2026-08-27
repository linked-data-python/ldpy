"""Règles de désambiguïsation (docs/reference/language.md) : chaque règle est
testée dans les deux sens (transformé / laissé intact)."""

import pytest
from rdflib import URIRef, Literal

from ldpy.transpiler import transpile, LdpySyntaxError

P = "@prefix ex: <http://example.org/ns#> .\n"


# --- R1 : contexte opérande -------------------------------------------------

def test_chained_comparison_not_iri():
    src = "r = a<b>c\n"
    assert transpile(src).code == src


def test_iri_after_assign(run):
    g, _ = run("t = <p>\n")
    assert g["t"] == URIRef("p")


def test_iri_in_call_args(run):
    g, _ = run("t = [<http://e/a>, <http://e/b>]\n")
    assert g["t"] == [URIRef("http://e/a"), URIRef("http://e/b")]


def test_lt_after_name_is_operator():
    src = "if x<y:\n    pass\n"
    assert transpile(src).code == src


def test_lt_after_paren_close_is_operator():
    src = "if f(x)<y:\n    pass\n"
    assert transpile(src).code == src


def test_shift_and_le_operators_untouched():
    src = "a = b << 2\nc = d <= e\n"
    assert transpile(src).code == src


def test_second_lt_starts_iri(run):
    g, _ = run("r = 1 < 2 < 3\ns = <http://e/a>\n")
    assert g["r"] is True


# --- R2 : adjacence stricte -------------------------------------------------

def test_g_space_brace_not_graph():
    # `g {1}` : reste du Python (set après un nom - erreur Python à l'exécution,
    # mais la transpilation n'y touche pas)
    src = "x = g ,{1}\n"
    assert transpile(src).code == src


def test_matmul_with_spaces_not_langtag():
    src = "y = 'a' @ en\n"
    assert transpile(src).code == "y = 'a' @ en\n"


def test_langtag_glued(run):
    g, _ = run("y = 'a'@en\n")
    assert g["y"] == Literal("a", lang="en")


def test_pname_with_spaces_untouched():
    src = P + "d = {ex: 1}\n"
    code = transpile(src).code
    assert "d = {ex: 1}\n" in code


# --- R3 : préfixes déclarés / backtracking ----------------------------------

def test_undeclared_prefix_untouched():
    src = "d = {foo:bar}\n"
    assert transpile(src).code == src


def test_declared_prefix_in_set_is_pname(run):
    g, _ = run(P + "d = {ex:bar}\n")
    assert g["d"] == {URIRef("http://example.org/ns#bar")}


def test_slice_with_declared_prefix_and_spaces_untouched():
    src = P + "r = arr[ex : b]\n"
    code = transpile(src).code
    assert "arr[ex : b]" in code


def test_slice_with_undeclared_names_untouched():
    src = "r = arr[i:j]\n"
    assert transpile(src).code == src


def test_pname_digit_local_not_matched_outside_islands():
    # hors îlot, la partie locale commence par une lettre ou '_'
    src = P + "d = {ex:1}\n"
    code = transpile(src).code
    assert "{ex:1}" in code


def test_failed_iri_backtracks_to_operator():
    src = "r = x <emoji et espaces> y\n" .replace("emoji et espaces", "a b")
    # '<a b>' n'est pas une IRI (espace) : reste deux comparaisons
    assert "x <a b> y" in transpile(src).code


def test_firi_backtrack_comparison():
    src = "r = f<3\n"
    assert transpile(src).code == src


def test_attribute_g_brace_untouched_is_error():
    # obj.g{ : jamais un îlot (accès d'attribut) -> Python tranchera
    src = "x = obj.g\n"
    assert transpile(src).code == src


# --- @prefix vs décorateur ---------------------------------------------------

def test_decorator_named_prefix_untouched():
    src = "@prefix\ndef f():\n    pass\n"
    assert transpile(src).code == src


def test_decorator_call_named_prefix_untouched():
    src = "@prefix('x')\ndef f():\n    pass\n"
    assert transpile(src).code == src


def test_prefix_stmt_consumed(run):
    g, result = run(P + "x = ex:a\n")
    assert "__namespaces__['ex']" in result.code
    assert g["x"] == URIRef("http://example.org/ns#a")


# --- erreurs claires ---------------------------------------------------------

def test_question_mark_alone_is_error():
    with pytest.raises(LdpySyntaxError):
        transpile("x = ? + 1\n")


def test_unclosed_graph_is_error():
    with pytest.raises(LdpySyntaxError):
        transpile(P + "gr = g{ ex:s ex:p 1\n")


def test_undeclared_prefix_in_graph_is_error():
    with pytest.raises(LdpySyntaxError) as e:
        transpile("gr = g{ foo:bar a foo:C }\n")
    assert "foo" in str(e.value)


def test_error_position_is_reported():
    try:
        transpile("x = 1\ngr = g{ foo:bar a foo:C }\n", "f.ldpy")
    except LdpySyntaxError as e:
        assert e.lineno == 2
        assert e.filename == "f.ldpy"
    else:
        raise AssertionError("LdpySyntaxError attendue")


def test_interpolation_in_plain_iri_suggests_firi():
    """Diagnostic : <.../{x}> est une erreur fréquente ; le message doit
    orienter vers la forme f<...> plutôt que dire « IRI non terminée »."""
    with pytest.raises(LdpySyntaxError) as e:
        transpile(P + "gr = g{ <sensor/{s}> ex:p 1 }\n")
    assert "f<" in str(e.value)
