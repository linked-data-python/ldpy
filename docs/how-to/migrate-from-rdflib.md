# How to migrate rdflib code to ldpy

Adoption is file by file: `.ldpy` is a superset of Python, so renaming a
`.py` to `.ldpy` changes nothing until you write your first island. This guide
gives the mechanical rewrites, then the two traps that silently change meaning.

## Rename, then rewrite what pays

```text
mv mymodule.py mymodule.ldpy
```

Nothing else. The file transpiles to itself, byte for byte, and imports the
same way once the hook is installed:

```python
import ldpy
ldpy.install()
# import mymodule   (finds mymodule.ldpy on sys.path)
```

## The mechanical rewrites

| rdflib | ldpy |
|---|---|
| `EX = Namespace("http://e/")` then `EX.Thing` | `@prefix ex: <http://e/> .` then `ex:Thing` |
| `URIRef("http://e/a")` | `<http://e/a>` |
| `URIRef(BASE + path)` | `f<{path}>` with `@base <…> .` — see the trap below |
| `Literal("x", lang="en")` | `"x"@en` |
| `Literal("1", datatype=XSD.integer)` | `"1"^^xsd:integer` |
| `Variable("v")` | `?v` |
| `g.add((s, RDF.type, EX.C))` | `+{ {s} a ex:C }` with `@graph g` |
| a run of `g.add(...)` on one subject | one `+{ … ; … ; … }` |
| `g += other` | unchanged |
| `for o in g.objects(s, EX.p)` | `for o in m{ {s} ex:p ?o }` |
| `g.value(s, EX.p)` | `m{ {s} ex:p ?v }.first()` |
| `next(g.subjects(RDF.type, EX.C))` | `m{ ?s a ex:C }.first()` |
| `(s, p, o) in g` | `bool(m{ … })` |
| `g.query(TEXT)` | `s{ … }` — checked at transpile time |
| `g.query(q, initBindings={"s": t})` | `s{ … ?s … }` with `{t}` in term position |
| `from .namespaces import BRICK` | `from .namespaces import brick:` |

Here is the shape most code takes, before and after:

```python
from rdflib import Graph, Literal, Namespace, RDF, URIRef
EX = Namespace("http://example.org/")
g = Graph()
for row in [{"id": "a", "v": 1}, {"id": "b", "v": 2}]:
    s = URIRef("http://example.org/" + row["id"])
    g.add((s, RDF.type, EX.Thing))
    g.add((s, EX.value, Literal(row["v"])))
assert len(g) == 4
```

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
for @bindings in [{"id": "a", "v": 1}, {"id": "b", "v": 2}]:
    +{ e<http://example.org/{?id}> a ex:Thing ; ex:value ?v }
assert len(g) == 4
```

## Trap 1: `Literal(n, datatype=…)` is not `"n"^^dt`

rdflib **normalises the lexical form** of a typed literal built from a Python
value. `Literal(40, datatype=XSD.double)` has lexical form `"40.0"`, while
`"40"^^xsd:double` has lexical form `"40"`. They are different RDF terms, and
`==` says so.

```ldpy
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
from rdflib import Literal
from rdflib.namespace import XSD
written = "40"^^xsd:double
built = Literal(40, datatype=XSD.double)
assert written != built                      # same value, different term
assert float(written) == float(built)
```

So a mechanical rule `Literal(n, dt)` → `"n"^^dt` is **wrong**. Rewrite it as
`{n}^^dt`, which goes through the same conversion rdflib does:

```ldpy
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
from rdflib import Literal
from rdflib.namespace import XSD
n = 40
assert f{Literal(n, datatype=XSD.double)} == Literal(40, datatype=XSD.double)
```

## Trap 2: `URIRef(x)` is not `f<{x}>` when a base is in scope

`f<...>` resolves against the `@base` in scope; `URIRef(x)` does not resolve
anything. The two agree only when there is no base, or when `x` is already
absolute.

```ldpy
@base <http://example.org/data/> .
from rdflib import URIRef
x = "sensor/1"
assert str(f<{x}>) == "http://example.org/data/sensor/1"
assert str(URIRef(x)) == "sensor/1"          # not the same term
```

## What not to rewrite

Some rdflib code has no better form in ldpy, and the notation is honest about
it:

- **A plain literal**: `Literal("x")` has no island spelling outside a graph.
  Inside one, position makes it a literal; outside, keep `Literal`.
- **A variable language tag**: `Literal(x, lang=code)` has no form at all.
- **A `Namespace` as an object**: `@prefix` is a lexical declaration, not a
  value. If you need to *pass a namespace around*, keep the `Namespace`
  constant — and note that ldpy binds your declared prefixes on the graphs it
  creates, so serialisation already looks right.
- **A `Dataset` or a `ConjunctiveGraph`**: `@graph` designates one graph, and
  named-graph *spaces* stay rdflib's API.
- **String-embedded RDF**: a CURIE inside a data string
  (`method="qb:CodedProperty"`), a query in a config file — these are strings,
  and ldpy never looks inside strings. That is a guarantee, not a gap.

## Check the translation

The corpus study translated 140 programs and proved each pair equivalent by
**RDF isomorphism**, using rdflib as the oracle. Do the same for anything
non-trivial:

```python
from rdflib import Graph
from rdflib.compare import isomorphic
before = Graph().parse(data="<http://e/a> <http://e/p> 1 .", format="turtle")
after = Graph().parse(data="<http://e/a> <http://e/p> 1 .", format="turtle")
assert isomorphic(before, after)
```

What that study found about the limits of the notation, at scale, is in
[what real RDF code does](../explanation/what-real-code-does.md#what-the-notation-still-does-not-reach).
