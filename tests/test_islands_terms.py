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


# --- datatype interpolé {expr} ----------------------------------------------
# Relevé par l'étude de corpus (fiche ldpy/012) : le code de sérialisation
# générique calcule son datatype à l'exécution. `f{expr}` existait déjà ;
# `{expr}`, la forme naturelle, manquait. Un datatype étant TOUJOURS un IRI,
# l'interpolation passe par dtype() et non par node().

def test_datatype_literal_interpolation(run, prefixes):
    g, _ = run(prefixes + "dt = xsd:date\nx = \"2026-01-01\"^^{dt}\n")
    assert g["x"] == Literal("2026-01-01", datatype=XSD.date)


def test_datatype_interpolation_accepts_a_plain_string(run):
    """Une chaîne est lue comme un IRI, pas comme un littéral (≠ node())."""
    g, _ = run("dt = 'http://www.w3.org/2001/XMLSchema#integer'\n"
               "x = \"7\"^^{dt}\n")
    assert g["x"] == Literal("7", datatype=XSD.integer)
    assert isinstance(g["x"].datatype, URIRef)


def test_datatype_interpolation_on_fstring_and_in_graph(run, prefixes):
    g, _ = run(prefixes +
               "v = '2026-01-01'\ndt = xsd:date\n"
               "x = f\"{v}\"^^{dt}\n"
               "gr = g{ ex:s ex:p {v}^^{dt} }\n")
    assert g["x"] == Literal("2026-01-01", datatype=XSD.date)
    obj = list(g["gr"])[0][2]
    assert obj == Literal("2026-01-01", datatype=XSD.date)


def test_datatype_interpolation_expression(run, prefixes):
    g, _ = run(prefixes + "t = False\n"
               "x = \"1\"^^{xsd:integer if t else xsd:byte}\n")
    assert g["x"].datatype == XSD.byte


def test_datatype_interpolation_unclosed_is_an_error(run, prefixes):
    import pytest
    from ldpy.transpiler import LdpySyntaxError
    with pytest.raises(LdpySyntaxError):
        run(prefixes + "dt = xsd:date\nx = \"1\"^^{dt\n")


# --------------------------------------------------------------- record 027
# `{expr}@en` is meaningful — the Python value is the lexical form and the
# suffix says how to read it.  `?v@en` is not: a variable is already bound to
# a complete term.  Maxime closed the question on 2026-09-03 (refuse, do not
# coerce); what this checks is that the refusal names itself, since before it
# the parser only complained about a missing closing brace.

def test_language_suffix_on_a_variable_is_refused(prefixes):
    import pytest
    from ldpy.transpiler import LdpySyntaxError
    with pytest.raises(LdpySyntaxError) as exc:
        transpile(prefixes + "@graph as g\n+{ ex:s ex:p ?v@fr-BE }\n")
    assert "?v@fr-BE" in str(exc.value)
    assert "{expr}@en" in str(exc.value)


def test_datatype_suffix_on_a_variable_is_refused(prefixes):
    import pytest
    from ldpy.transpiler import LdpySyntaxError
    with pytest.raises(LdpySyntaxError) as exc:
        transpile(prefixes + "@graph as g\n+{ ex:s ex:p ?v^^xsd:integer }\n")
    assert "suffixe de type" in str(exc.value)


def test_the_refusal_reaches_every_island_that_binds_variables(prefixes):
    import pytest
    from ldpy.transpiler import LdpySyntaxError
    for island in ("+{ ex:s ex:p ?v@en }", "-{ ex:s ex:p ?v@en }",
                   "for b in m{ ?s ex:p ?v@en }: pass"):
        with pytest.raises(LdpySyntaxError):
            transpile(prefixes + "@graph as g\n" + island + "\n")


def test_a_bare_variable_and_a_suffixed_interpolation_still_work(run, prefixes):
    g, _ = run(prefixes + "@graph as g\nv = 'x'\n"
               "+{ ex:s ex:p {v}@en }\n"
               "-{ ex:s ex:q ?any }\n")
    assert list(g["g"])[0][2] == Literal("x", lang="en")
