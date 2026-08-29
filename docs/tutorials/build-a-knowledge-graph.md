# Tutorial: a knowledge graph from tabular data

In this tutorial you turn two CSV files into an RDF graph, join them on a
shared key, derive a second graph from the first, and query the result — using
only ldpy and rdflib, with no mapping language and no query engine in between.

It follows [the first tutorial](getting-started.md). Everything here runs as
written.

## The data

Two tables, as they come out of a real system: one row per sensor, one row per
reading, joined by the sensor's identifier. Every value is a string, because
that is what CSV gives you.

```ldpy
import csv, io

SENSORS = """id,label,room
s1,Thermometer A,R101
s2,Thermometer B,R102
"""

READINGS = """sensor,celsius
s1,21.5
s1,22.0
s2,19.0
"""

assert len(list(csv.DictReader(io.StringIO(SENSORS)))) == 2
```

## Step 1 — rows become triples

`for @bindings in ITER:` makes each element of any iterable of mappings the
**current bindings** of the loop body. A `csv.DictReader` yields exactly that,
so it drives the loop directly — the variables in the pattern are the column
names.

```ldpy
@prefix ex:   <http://example.org/> .
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@base <http://example.org/data/> .
import csv, io

SENSORS = "id,label,room\ns1,Thermometer A,R101\ns2,Thermometer B,R102\n"

@graph as kg
for @bindings in csv.DictReader(io.StringIO(SENSORS)):
    +{ e<http://example.org/{?id}> a sosa:Sensor ;
           ex:label ?label ;
           ex:room e<http://example.org/{?room}> }

assert len(kg) == 6
assert bool(m{ ex:s1 a sosa:Sensor })
```

Read the pattern once more. `e<…{?id}…>` mints an IRI from a column — a
[deferred IRI](../reference/sparql-expressions.md#deferred-iris-e), evaluated
against the current bindings and percent-encoded, which is what data-derived
IRIs need. `?label` is the column's value as a literal. And `e<…{?room}…>`
mints another IRI, so two rows in the same room point at the same node:
minting *is* the join.

!!! note "`ex:{?id}` mints too, but does not encode"
    The local part of a prefixed name instantiates against the current
    bindings, like any other term position: `ex:{?id}` is `ex:a` on the row
    where `?id` is `"a"`. It **concatenates**, though, rather than
    percent-encoding — the namespace and the shape of the local part stay
    yours to control. When a column may hold a space or a slash, `e<…{?id}>`
    is the safer choice, because it percent-encodes what it interpolates.
    See [`ex:{?id}` joins, `e<…{?id}>` encodes](../reference/language/bindings.md#for-bindings-in-iter-the-loop-that-carries-them).

## Step 2 — the second table joins on the first

The readings table refers to sensors by the same identifier, so minting the
same IRI is the whole join. Nothing needs to be looked up.

```ldpy
@prefix ex:   <http://example.org/> .
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
import csv, io

READINGS = "sensor,celsius\ns1,21.5\ns1,22.0\ns2,19.0\n"

@graph as kg
+{ ex:s1 a sosa:Sensor . ex:s2 a sosa:Sensor }
for @bindings in csv.DictReader(io.StringIO(READINGS)):
    +{ e<http://example.org/{?sensor}> sosa:madeObservation
           [ sosa:hasSimpleResult ?celsius ] }

assert m{ ex:s1 sosa:madeObservation ?o }.count() == 2
assert len(kg) == 8
```

Two things to notice. Minting the same IRI from the same identifier *is* the
join — nothing was looked up. And the blank node inside `[ ... ]` is fresh at
every iteration, so the three observations are three distinct nodes.

One thing is wrong, though: `?celsius` came from a CSV file, so it is the
string `"21.5"`, not a number. That is the next step.

## Step 2b — say once what the columns mean

Every cell of a CSV file is a `str`; only you know that `celsius` is a double.
A [coercion policy](../reference/language/coercion.md) says it once, for a
region of code, instead of at every term:

```python
import csv, io, ldpy
from ldpy.transpiler import transpile
from rdflib.namespace import XSD

policy = ldpy.Coercion({("celsius",): XSD.double})
src = ('@prefix ex: <http://example.org/> .\n'
       '@graph as kg\n'
       'for @bindings in csv.DictReader(io.StringIO(READINGS)):\n'
       '    +{ e<http://example.org/{?sensor}> ex:value ?celsius }\n')
ns = {"csv": csv, "io": io, "__name__": "doc",
      "READINGS": "sensor,celsius\ns1,21.5\ns2,19.0\n"}
with policy:
    exec(compile(transpile(src).code, "<doc>", "exec"), ns)
assert {str(o.datatype) for s, p, o in ns["kg"]} == {str(XSD.double)}
```

## Step 3 — derive a graph from a graph

Reading and writing compose. `m{ }` yields solutions; the loop makes each one
current; `+{ }` instantiates a pattern against it; `e{ }` computes a term from
it. That is a CONSTRUCT, written in Python's control flow.

```ldpy
@prefix ex:  <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

@graph as celsius
+{ ex:s1 ex:value "21.5"^^xsd:double . ex:s2 ex:value "19.0"^^xsd:double }

@graph as fahrenheit
for @bindings in m{ ?s ex:value ?c }(celsius):
    +{ ?s ex:fahrenheit e{ ?c * 1.8 + 32 } }

values = sorted(round(float(v), 1) for s, v in m{ ?s ex:fahrenheit ?v })
assert values == [66.2, 70.7]
```

The `(celsius)` after the pattern is the
[call suffix](../reference/language/bindings.md#the-call-suffix-explicit-context):
it says which graph to read, because two graphs are in scope and the last
`@graph` declared is `fahrenheit`.

## Step 4 — filter, before you assert

A deferred expression evaluates to an *error* on missing or impossible data,
and a triple with an unbound term is dropped rather than filled with something
wrong. So a filter is just an expression:

```ldpy
@prefix ex:  <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

@graph as src
+{ ex:s1 ex:value "21.5"^^xsd:double .
   ex:s2 ex:value "19.0"^^xsd:double .
   ex:s3 ex:value "35.0"^^xsd:double }

warm = e{ ?v > 20 }
@graph as flagged
for @bindings as b in m{ ?s ex:value ?v }(src):
    if warm.ebv(b):
        +{ ?s a ex:Warm }
assert m{ ?s a ex:Warm }.count() == 2
```

`for @bindings as b in …` names the current bindings so ordinary Python can
look at them — the `as` of `@graph as g`, applied to bindings.

## Step 5 — query it

`m{ }` covers selection. When you need what SPARQL has and a graph pattern does
not — ordering, aggregates, unions, paths — `s{ }` gives you all of it, checked
at transpile time:

```ldpy
@prefix ex:  <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

@graph as kg
+{ ex:s1 ex:room ex:R101 ; ex:value "21.5"^^xsd:double .
   ex:s2 ex:room ex:R101 ; ex:value "19.0"^^xsd:double .
   ex:s3 ex:room ex:R102 ; ex:value "35.0"^^xsd:double }

rows = [(str(r[0]), round(float(r[1]), 2)) for r in
        s{ SELECT ?room (AVG(?v) AS ?mean)
           WHERE { ?s ex:room ?room ; ex:value ?v }
           GROUP BY ?room ORDER BY ?room }]
assert rows == [("http://example.org/R101", 20.25),
                ("http://example.org/R102", 35.0)]
```

A prefix is not repeated inside the query: the prologue comes from the
`@prefix` declarations in scope. And a typo in that query would have been
reported when you saved the file, not when execution first reached it.

## Step 6 — serialise

The result is an `rdflib.Graph`, so everything rdflib can do, it can do:

```ldpy
@prefix ex: <http://example.org/> .
@graph as kg
+{ ex:s1 a ex:Sensor ; ex:room ex:R101 }
turtle = kg.serialize(format="turtle")
assert "ex:s1" in turtle          # the @prefix declarations are bound for you
```

## What you built

Six steps, no mapping file, no query engine between you and the data — and the
whole thing is a Python program you can put a breakpoint in.

Next:

- [Building graphs from tables](../how-to/build-graphs-from-tables.md), as a
  reference for the patterns above.
- [Migrating rdflib code](../how-to/migrate-from-rdflib.md), including the two
  traps that bite.
- [What real RDF code does](../explanation/what-real-code-does.md) — why the
  language has exactly these constructs.
