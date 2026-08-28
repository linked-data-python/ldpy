# The language: overview

A `.ldpy` file is a Python file in which RDF **islands** may appear. Every
valid Python program is a valid ldpy program with unchanged meaning
([why that matters](../../explanation/why.md#r3-host-language-transparency)),
and everything that is not an island is copied to the output byte for byte.

An island is introduced by a **sigil** — a one-character prefix glued to a
delimiter — or by a declaration keyword. There are no new statements, no new
keywords, and no configuration: the sigils below are the whole extension.

## The islands, at a glance

Each row links to the section that describes it in full.

### Terms — [details](terms.md)

| Form | Example | Value |
|---|---|---|
| IRI | `<http://e/a>`, `<rel>` | `URIRef`, resolved against `@base` |
| Prefixed name | `ex:Thing`, `ex:{expr}` | `URIRef` |
| RDF literal | `"a"@en`, `"1"^^xsd:int`, `f"v{x}"@en` | `Literal` |
| Variable | `?name`, `$name` | `Variable` |
| Formatted IRI | `f<http://e/{expr}/y>` | `URIRef` built by interpolation |
| Formatted node | `f{expr}`, `?{expr}` | any value, coerced to an RDF term |

### Declarations — [details](declarations.md)

| Form | Example | Effect |
|---|---|---|
| Prefix | `@prefix ex: <http://e/> .` | binds `ex:` for the enclosing block |
| Base | `@base <http://e/> .` | sets the base IRI for relative IRIs |
| Prefix import | `from vocab import brick:, unit: as u:` | imports prefixes from a module |
| Scope modifier | `global @prefix …`, `nonlocal @graph …` | Python's own scope rules |

### Graphs and the current graph — [graphs](graphs.md) · [current graph](current-graph.md)

| Form | Example | Value |
|---|---|---|
| Graph | `g{ ex:s a ex:C ; ex:p 1, "x" }` | an `rdflib.Graph` |
| Data-keyed blank node | `_:{expr}` *(anywhere a term may stand)* | `BNode` with value-derived identity |
| Current graph | `@graph g`, `@graph as g`, `@graph <iri> as g` | *(declaration)* |
| Add / remove | `+{ ex:s ex:p 1 }`, `-{ ex:s ?p ?o }` | *(statements)* write to the current graph |

### Reading — [details](querying.md)

| Form | Example | Value |
|---|---|---|
| Match (BGP) | `m{ ?s a ex:C ; ex:v ?v }` | lazy solutions over the current graph |
| SPARQL query | `s{ SELECT ?x WHERE { ?x a {cls} } }` | a lazy prepared query |

### Deferred evaluation and bindings — [bindings](bindings.md) · [expressions](../sparql-expressions.md)

| Form | Example | Value |
|---|---|---|
| SPARQL expression | `e{ ?age >= 18 && BOUND(?n) }` | a **deferred** `Expression` |
| Deferred IRI | `e<http://e/p/{?n}>` | a deferred `Expression` yielding a `URIRef` |
| Current bindings | `@bindings b`, `@bindings as b`, `for @bindings in it:` | *(declaration)* |
| Call suffix | `m{ P }(g)`, `s{ Q }(g, b)`, `g{ P }(b)` | pass the context explicitly |

### Everything else

- [Python → RDF coercion](coercion.md) — how a plain Python value entering an
  island becomes an RDF term, and how to change that.
- [Lexical rules](lexical.md) — the three disambiguation rules, the character
  sets, the residual ambiguities and the known limitations.

## How to read the examples

Every `ldpy` block on this site is transpiled, executed and its assertions
checked by the test suite ([how](../../explanation/how-it-is-tested.md)), so
each one is complete: it declares the prefixes it uses and asserts what it
claims. Read the `assert` lines as the specification.

```ldpy
@prefix ex: <http://example.org/> .
assert str(ex:Thing) == "http://example.org/Thing"
```

## Two rules that run through everything

**Islands are expressions.** With the exception of the declarations and of
`+{ }` / `-{ }`, every island is a Python *expression* and may appear wherever
an expression may — in a lambda, a comprehension, a default argument, a
`return`. This is a design commitment, not an accident of implementation:
see [emission and semantics](../../explanation/emission-and-semantics.md).

**`{expr}` switches back to Python.** In any term position inside any island,
braces return to the host language, exactly as in an f-string. The boundary is
always explicit in the text; nothing is inferred.

```ldpy
@prefix ex: <http://example.org/> .
readings = [21.5, 22.0]
graphs = [g{ ex:s ex:v {v} } for v in readings]
assert [len(g) for g in graphs] == [1, 1]
```
