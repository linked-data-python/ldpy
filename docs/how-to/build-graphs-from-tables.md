# How to build a graph from tabular data

The knowledge-graph construction case: rows in, triples out. This is a
reference for the patterns; the
[tutorial](../tutorials/build-a-knowledge-graph.md) walks through one complete
example.

## Rows drive the loop

`for @bindings in ITER:` accepts **any iterable of mappings** — a
`csv.DictReader`, a list of dicts, a database cursor's rows, the solutions of a
[`m{ }`](../reference/language/querying.md). Each element becomes the current
bindings of the body, and the variables in the pattern are the keys.

```ldpy
@prefix ex: <http://example.org/> .
import csv, io

@graph as kg
for @bindings in csv.DictReader(io.StringIO("id,name\na,Ana\nb,Bo\n")):
    +{ e<http://example.org/{?id}> ex:name ?name }
assert len(kg) == 2
```

## Mint an IRI from a column

Use a [deferred IRI](../reference/sparql-expressions.md#deferred-iris-e). Its
holes are SPARQL expressions over the current bindings, and their values are
percent-encoded — which is what data-derived IRIs need.

```ldpy
@prefix ex: <http://example.org/> .
@graph as kg
for @bindings in [{"id": "a b"}]:
    +{ e<http://example.org/thing/{?id}> a ex:Thing }
assert bool(m{ <http://example.org/thing/a%20b> a ex:Thing })
```

!!! warning "`ex:{?id}` is not this"
    Inside `{ }` you are in Python, so `{?id}` is the `Variable` *object*, and
    `ex:{?id}` gives you `ex:id` on every row. The local part of a prefixed
    name is built before bindings are applied; every other term position
    instantiates `?id` as expected.

## Join two tables

Minting the same IRI from the same key **is** the join. Nothing is looked up.

```ldpy
@prefix ex: <http://example.org/> .
@graph as kg
for @bindings in [{"id": "a", "name": "Ana"}]:
    +{ e<http://example.org/{?id}> ex:name ?name }
for @bindings in [{"person": "a", "score": 10}, {"person": "a", "score": 20}]:
    +{ e<http://example.org/{?person}> ex:score ?score }
assert m{ <http://example.org/a> ?p ?o }.count() == 3
```

For a join on a *compound* key with no natural IRI, use a
[data-keyed blank node](../reference/language/graphs.md#data-keyed-blank-nodes-_expr):
equal values give the same node, across graphs and across sources.

```ldpy
@prefix ex: <http://example.org/> .
@graph as kg
rows = [("Ana", "Lu", "green"), ("Ana", "Lu", "blue")]
for first, last, colour in rows:
    +{ _:{(first, last)} ex:name {first} ; ex:likes {colour} }
assert len({s for s, p, o in kg}) == 1 and len(kg) == 3
```

## Say once what the columns mean

Every cell of a CSV file is a `str`. A
[coercion policy](../reference/language/coercion.md) declares the meaning of a
column once, for a region, instead of converting at each use.

```python
import csv, io, ldpy
from ldpy.transpiler import transpile
from rdflib import URIRef
from rdflib.namespace import XSD

policy = ldpy.Coercion({("uri",): URIRef, ("age",): XSD.integer})
src = ('@prefix ex: <http://e/> .\n'
       '@graph as kg\n'
       'for @bindings in csv.DictReader(io.StringIO(DATA)):\n'
       '    +{ ?uri ex:age ?age }\n')
ns = {"csv": csv, "io": io, "__name__": "doc",
      "DATA": "uri,age\nhttp://e/a,30\n"}
with policy:
    exec(compile(transpile(src).code, "<doc>", "exec"), ns)
s, p, o = list(ns["kg"])[0]
assert type(s).__name__ == "URIRef" and o.datatype == XSD.integer
```

Policies stack, so an inner `with` refines an outer one; `policy.install()`
keeps a policy for a whole module.

## Skip a row without an `if`

A triple whose term is unbound is **dropped**. A missing column therefore costs
nothing, and neither does a
[deferred expression](../reference/language/bindings.md#e-in-term-position)
that fails:

```ldpy
@prefix ex: <http://example.org/> .
@graph as kg
for @bindings in [{"id": "a", "v": 2}, {"id": "b"}]:
    +{ e<http://example.org/{?id}> ex:double e{ ?v * 2 } }
assert len(kg) == 1
```

## Derive a graph from a graph

Reading and writing compose: a match yields solutions, the loop makes each one
current, a pattern is instantiated against it. That is a CONSTRUCT, in Python's
control flow.

```ldpy
@prefix ex: <http://example.org/> .
@graph as src
+{ ex:c1 ex:reading 10 . ex:c2 ex:reading 25 }

@graph as out
for @bindings in m{ ?s ex:reading ?v }(src):
    +{ ?s ex:hasValue e{ ?v * 2 } }

assert sorted(int(o) for s, o in m{ ?s ex:hasValue ?o }(out)) == [20, 50]
```

## Write into a graph you do not own

`+{ }` emits `add_to(...)`, never `+=`, so a read-only property or a module
global needs no `global` declaration and no `__iadd__` dance:

```ldpy
@prefix ex: <http://example.org/> .
from rdflib import Graph

class Store:
    def __init__(self):
        self._g = Graph()
    @property
    def graph(self):
        return self._g

store = Store()
+{ ex:s ex:p 1 }(store.graph)
assert len(store.graph) == 1
```

## Serialise

The result is an `rdflib.Graph`, and the prefixes you declared are bound on it:

```ldpy
@prefix ex: <http://example.org/> .
@graph as kg
+{ ex:s a ex:Thing }
assert "ex:s" in kg.serialize(format="turtle")
```

## Performance notes

- A `g{ ... }` materialises its triples **lazily**, so `target += g{ ... }`
  performs a single store insertion. Accumulating in a loop is O(total).
- Prefixed names and constant IRIs are resolved at transpile time and emitted
  as constants — they cost nothing at run time.
- Measurements for the construction workload, and the three rounds of
  optimisation they drove, are in `OPTIMIZATION.md`.
