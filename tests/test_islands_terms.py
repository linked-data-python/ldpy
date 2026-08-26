"""Îlots au niveau terme : IRIs, pnames, littéraux RDF, variables, f-IRI, f{}."""

from rdflib import URIRef, Literal, Variable, XSD

from ldpy.transpiler import transpile


def test_absolute_iri(run):
    g, _ = run("x = <http://example.org/a>\n")
    assert g["x"] == URIRef("http://example.org/a")


def test_relative_iri_resolved_against_base(run):
    g, _ = run("@base <http://example.org/data/> .\nx = <hello>\n")
    assert g["x"] == URIRef("http://example.org/data/hello")


def test_relative_iri_without_base(run):
    g, _ = run("x = <hello>\n")
    assert g["x"] == URIRef("hello")


def test_fragment_iri(run):
    g, _ = run("@base <http://example.org/data> .\nx = <#f>\n")
    assert g["x"] == URIRef("http://example.org/data#f")


def test_pname(run, prefixes):
    g, _ = run(prefixes + "x = ex:SomeClass\n")
    assert g["x"] == URIRef("http://example.org/ns#SomeClass")


def test_pname_in_call_and_dict(run, prefixes):
    g, _ = run(prefixes + "d = {ex:a, ex:b}\nl = sorted([ex:b, ex:a])\n")
    assert g["d"] == {URIRef("http://example.org/ns#a"),
                     URIRef("http://example.org/ns#b")}
    assert g["l"][0] == URIRef("http://example.org/ns#a")


def test_pname_interpolated(run, prefixes):
    g, _ = run(prefixes + "capteur = 'c1'\nx = ex:{capteur}\n")
    assert g["x"] == URIRef("http://example.org/ns#c1")


def test_variable(run):
    g, _ = run("v = ?var\nw = $autre\n")
    assert g["v"] == Variable("var")
    assert g["w"] == Variable("autre")


def test_variable_in_dict_key(run):
    g, _ = run("m = { ?var: <http://e/a>, ?r: 12 }\n")
    assert g["m"][Variable("var")] == URIRef("http://e/a")
    assert g["m"][Variable("r")] == 12


def test_lang_literal(run):
    g, _ = run('x = "hello"@en\n')
    assert g["x"] == Literal("hello", lang="en")


def test_lang_literal_with_subtag(run):
    g, _ = run('x = "salut"@fr-CA\n')
    assert g["x"] == Literal("salut", lang="fr-CA")


def test_datatype_literal_pname(run, prefixes):
    g, _ = run(prefixes + 'x = "12"^^xsd:integer\n')
    assert g["x"] == Literal("12", datatype=XSD.integer)


def test_datatype_literal_iri(run):
    g, _ = run('x = "12"^^<http://www.w3.org/2001/XMLSchema#int>\n')
    assert g["x"] == Literal("12", datatype=XSD.int)


def test_fstring_lang_literal(run):
    g, _ = run('w = "monde"\nx = f"salut { w }"@fr\n')
    assert g["x"] == Literal("salut monde", lang="fr")


def test_firi(run):
    g, _ = run("i = 42\nx = f<http://example.org/{ i }/z>\n")
    assert g["x"] == URIRef("http://example.org/42/z")


def test_firi_static(run):
    g, _ = run("x = f<http://example.org/a>\n")
    assert g["x"] == URIRef("http://example.org/a")


def test_firi_relative_with_base(run):
    g, _ = run("@base <http://example.org/data/> .\nn = 3\nx = f<room/{ n }>\n")
    assert g["x"] == URIRef("http://example.org/data/room/3")


def test_firi_expression_with_spaces_and_calls(run):
    g, _ = run("t = True\nx = f<http://e/{ str(t).lower() }/y/{ 2*3 }>\n")
    assert g["x"] == URIRef("http://e/true/y/6")


def test_fnode_passthrough_term(run, prefixes):
    g, _ = run(prefixes + "t = False\nx = f{ <http://e/a> if t else ex:b }\n")
    assert g["x"] == URIRef("http://example.org/ns#b")


def test_fnode_coerces_python_value(run):
    g, _ = run("x = f{ 40 + 2 }\n")
    assert g["x"] == Literal(42)


def test_qmark_node(run):
    g, _ = run("age = 33\nx = ?{ age }\n")
    assert g["x"] == Literal(33)


def test_datatype_literal_fnode(run, prefixes):
    g, _ = run(prefixes +
               't = True\nx = "hello"^^f{ <http://e/dt> if t else ex:dt }\n')
    assert g["x"] == Literal("hello", datatype=URIRef("http://e/dt"))


def test_datatype_literal_firi(run):
    g, _ = run('p = "num"\nx = "5"^^f<http://e/{ p }>\n')
    assert g["x"] == Literal("5", datatype=URIRef("http://e/num"))


def test_islands_in_default_args(run, prefixes):
    src = prefixes + """\
def f(t=ex:hello):
    return t
r1 = f()
r2 = f(ex:autre)
"""
    g, _ = run(src)
    assert g["r1"] == URIRef("http://example.org/ns#hello")
    assert g["r2"] == URIRef("http://example.org/ns#autre")


def test_no_prelude_duplicated_lines():
    result = transpile("x = <http://e/a>\n")
    assert result.code.count("import ldpy.runtime") == 1
