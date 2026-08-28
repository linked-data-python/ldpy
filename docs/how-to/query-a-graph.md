# How to read and query a graph

Two islands read a graph. Pick by what you need, not by size of query:
[`m{ }`](../reference/language/querying.md) is a graph pattern matched by
nested loops over `graph.triples()`;
[`s{ }`](../reference/language/querying.md#s-a-sparql-query) is all of
SPARQL, run by rdflib.

All the examples below assume a current graph:

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a a ex:Sensor ; ex:room ex:R1 ; ex:v 21 .
   ex:b a ex:Sensor ; ex:room ex:R1 ; ex:v 25 .
   ex:c a ex:Other  ; ex:room ex:R2 }
assert len(g) == 8
```

## Get all the subjects of a type

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a a ex:Sensor . ex:b a ex:Sensor . ex:c a ex:Other }
sensors = sorted(str(s) for s in m{ ?s a ex:Sensor })
assert sensors == ["http://example.org/a", "http://example.org/b"]
```

One variable yields terms, not one-element tuples.

## Get the one value you expect

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a ex:v 21 }
v = m{ ex:a ex:v ?v }.one()          # raises if there is not exactly one
maybe = m{ ex:zz ex:v ?v }.first()   # None if there is none
assert int(v) == 21 and maybe is None
```

## Test existence

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a a ex:Sensor }
if m{ ex:a a ex:Sensor }:
    found = True
assert found and not m{ ex:zz a ex:Sensor }
```

The match is lazy: truth-testing stops at the first solution.

## Join two patterns

Shared variables join; the order you write is the order evaluated.

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a ex:room ex:R1 ; ex:v 21 . ex:b ex:room ex:R1 ; ex:v 25 }
rows = sorted((str(s), int(v)) for s, r, v in m{ ?s ex:room ?r ; ex:v ?v })
assert rows == [("http://example.org/a", 21), ("http://example.org/b", 25)]
```

## Ignore an intermediate node

A blank node in a pattern is a **non-distinguished variable**: matched, not
projected. It removes the throwaway names.

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a ex:reading [ ex:value 21 ] . ex:b ex:reading [ ex:value 25 ] }
values = sorted(int(v) for s, v in m{ ?s ex:reading [ ex:value ?v ] })
assert values == [21, 25]
```

## Filter

`m{ }` has no `FILTER`. Use Python's `if`, or a
[deferred expression](../reference/sparql-expressions.md) when the condition is
worth naming and reusing:

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a ex:v 21 . ex:b ex:v 25 }
hot = e{ ?v > 23 }
warm = [str(s) for s, v in m{ ?s ex:v ?v } if int(v) > 20]
hotter = [str(b[?s]) for b in m{ ?s ex:v ?v }.solutions() if hot.ebv(b)]
assert len(warm) == 2 and hotter == ["http://example.org/b"]
```

## Read a graph that is not the current one

The [call suffix](../reference/language/bindings.md#the-call-suffix-explicit-context)
gives the receiver explicitly:

```ldpy
@prefix ex: <http://example.org/> .
from rdflib import Graph
other = Graph()
+{ ex:a ex:v 21 }(other)
assert m{ ?s ex:v ?v }(other).count() == 1
```

## Use SPARQL when you need SPARQL

Ordering, aggregates, `OPTIONAL`, `UNION`, property paths, updates — anything
`m{ }` deliberately does not have:

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a ex:room ex:R1 ; ex:v 21 . ex:b ex:room ex:R1 ; ex:v 25 .
   ex:c ex:room ex:R2 ; ex:v 30 }
rows = [(str(r[0]), int(r[1])) for r in
        s{ SELECT ?room (MAX(?v) AS ?top) WHERE { ?s ex:room ?room ; ex:v ?v }
           GROUP BY ?room ORDER BY ?room }]
assert rows == [("http://example.org/R1", 25), ("http://example.org/R2", 30)]
```

The prefixes come from the declarations in scope — no `PREFIX` line inside the
island — and the query's syntax was checked when the file was transpiled.

### Bind a term into a query, safely

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a ex:room ex:R1 . ex:b ex:room ex:R2 }
wanted = ex:R1
here = [str(r[0]) for r in s{ SELECT ?s WHERE { ?s ex:room {wanted} } }]
assert here == ["http://example.org/a"]
```

`{wanted}` becomes an `initBindings` entry. The query text is never
concatenated, so there is nothing to inject into.

### Run an update

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a a ex:Sensor }
s{ INSERT { ?s ex:checked true } WHERE { ?s a ex:Sensor } }.execute()
assert len(g) == 2
```

An update has no solutions to iterate, so `execute()` is what runs it.

## Turn solutions into another graph

See [building graphs](build-graphs-from-tables.md#derive-a-graph-from-a-graph)
— `for @bindings in m{ … }:` makes each solution current, and `+{ … }`
instantiates a pattern against it.
