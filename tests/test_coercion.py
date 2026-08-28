"""Coercition Python -> RDF : une politique, configurable (fiche 020)."""

import datetime
import io
import textwrap

import pytest
from rdflib import URIRef, Literal
from rdflib.namespace import XSD

from ldpy.runtime import (Coercion, Bindings, node, dtype,
                          _COERCION_STACK)


@pytest.fixture(autouse=True)
def clean_stack():
    del _COERCION_STACK[:]
    yield
    del _COERCION_STACK[:]


# ------------------------------------------------------ sans politique

def test_default_unchanged():
    assert node("x") == Literal("x")
    assert node(3) == Literal(3)
    assert node(URIRef("http://e/a")) == URIRef("http://e/a")


def test_term_never_reconverted():
    with Coercion({("u",): XSD.integer}):
        assert node(URIRef("http://e/a"), field="u") == URIRef("http://e/a")
        assert node(Literal("x"), field="u") == Literal("x")


def test_dtype_stays_out_of_policy():
    with Coercion({(str,): XSD.integer, str: XSD.integer}):
        assert dtype("http://t/") == URIRef("http://t/")


# ------------------------------------------------------ règles par champ

def test_field_rules():
    pol = Coercion({
        ("age", "count"): XSD.integer,
        ("uri",): URIRef,
        ("born",): lambda v: Literal(datetime.date.fromisoformat(v)),
    })
    with pol:
        assert node("42", field="age") == Literal("42", datatype=XSD.integer)
        assert node("http://e/x", field="uri") == URIRef("http://e/x")
        assert node("2020-01-02", field="born") == \
            Literal(datetime.date(2020, 1, 2))
        assert node("libre", field="autre") == Literal("libre")


def test_type_rules_after_field():
    with Coercion({("n",): XSD.string, int: XSD.byte}):
        assert node(3, field="n") == Literal(3, datatype=XSD.string)
        assert node(3, field="autre") == Literal("3", datatype=XSD.byte)
        assert node(3) == Literal("3", datatype=XSD.byte)


def test_type_rule_walks_mro():
    class MonInt(int):
        pass
    with Coercion({int: XSD.integer}):
        assert node(MonInt(5)).datatype == XSD.integer


def test_bad_key_rejected():
    with pytest.raises(TypeError):
        Coercion({"champ_nu": XSD.integer})


# ----------------------------------------------------------- pile, with

def test_with_pops_on_exception():
    try:
        with Coercion({("a",): XSD.integer}):
            raise RuntimeError()
    except RuntimeError:
        pass
    assert not _COERCION_STACK


def test_inner_with_refines_outer():
    with Coercion({("a",): XSD.integer, ("b",): XSD.integer}):
        with Coercion({("a",): URIRef}):
            assert node("http://x/", field="a") == URIRef("http://x/")
            assert node("2", field="b") == Literal("2", datatype=XSD.integer)
        assert node("2", field="a") == Literal("2", datatype=XSD.integer)


def test_install_stays():
    Coercion({("a",): XSD.integer}).install()
    assert node("2", field="a") == Literal("2", datatype=XSD.integer)


# ----------------------------------------------------- de bout en bout

def test_bindings_coerce_by_field():
    with Coercion({("age",): XSD.integer, ("id",): URIRef}):
        b = Bindings({"id": "http://e/a", "age": "30"})
    assert b["id"] == URIRef("http://e/a")
    assert b["age"] == Literal("30", datatype=XSD.integer)


def test_csv_end_to_end(run):
    src = textwrap.dedent("""\
        import csv, io
        from rdflib.namespace import XSD
        from rdflib import URIRef
        import ldpy
        @prefix ex: <http://e/> .
        @graph as g
        f = io.StringIO("id,age\\nhttp://e/a,30\\nhttp://e/b,31\\n")
        with ldpy.Coercion({("id",): URIRef, ("age",): XSD.integer}):
            for @bindings in csv.DictReader(f):
                +{ ?id ex:age ?age }
        rows = sorted(g)
        """)
    g, _ = run(src)
    assert g["rows"][0] == (URIRef("http://e/a"), URIRef("http://e/age"),
                            Literal("30", datatype=XSD.integer))
    assert len(g["rows"]) == 2


def test_variable_field_in_islands(run):
    """Le nom d'une variable de motif est son champ : ?age suit la règle."""
    src = textwrap.dedent("""\
        from rdflib.namespace import XSD
        import ldpy
        @prefix ex: <http://e/> .
        with ldpy.Coercion({("age",): XSD.integer}):
            @bindings {"age": "30"}
            g = g{ ex:s ex:age ?age }
        o = next(iter(g))[2]
        """)
    g, _ = run(src)
    assert g["o"] == Literal("30", datatype=XSD.integer)
