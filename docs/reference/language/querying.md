# Reading a graph — `m{ ... }` and `s{ ... }`

Reading is as common as writing in real RDF code: the corpus study found
[1 033 files that select triples against 1 049 that add them](../../explanation/what-real-code-does.md#reading-is-as-big-as-writing).
Two islands cover it, and the choice between them is the choice between a
graph pattern and a query engine.

| | `m{ ... }` | `s{ ... }` |
|---|---|---|
| Language | Turtle-notation BGP with variables | all of SPARQL |
| Engine | none — nested-loop join over `graph.triples()` | rdflib's |
| Validated | at transpile time (island syntax) | at transpile time, by rdflib |
| Use it for | selection, traversal, existence | filters, unions, aggregates, paths, updates |

## `m{ ... }` — match a basic graph pattern

The same notation as [`g{ }`](graphs.md), read in the other direction: instead
of building triples it matches them against the
[current graph](current-graph.md), in written order, and yields solutions
lazily.

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a a ex:Sensor ; ex:v 1 . ex:b a ex:Sensor ; ex:v 2 }

sensors = sorted(m{ ?s a ex:Sensor })                   # arity 1: terms
pairs = sorted((s, v) for s, v in m{ ?s a ex:Sensor ; ex:v ?v })
assert len(sensors) == 2 and len(pairs) == 2
```

### Arity decides the shape

- **One variable** → the solutions are the terms themselves. This is the
  common case (measured 6 139 term selectors against 1 731 tuple selectors),
  and it keeps `sorted(m{ ?s a ex:C })` free of one-element tuples.
- **Two or more** → unpackable rows, also reachable by name.

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a a ex:Sensor ; ex:v 1 }
row = m{ ?s a ex:Sensor ; ex:v ?v }.one()
assert row.s == ex:a and int(row.v) == 1
assert tuple(row) == (ex:a, row.v)
```

### The single expected value, and existence

Two thousand two hundred and fifty-two occurrences of "the one value I expect"
were counted in the corpus (`value`, `next(...)`). They have a spelling:

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a ex:v 1 . ex:b a ex:Sensor }
one = m{ ex:a ex:v ?v }.one()             # exactly one solution, or raises
none = m{ ex:zzz ex:v ?v }.first()        # None when there is none
assert int(one) == 1 and none is None
assert bool(m{ ex:b a ex:Sensor })        # ASK, evaluated lazily
assert m{ ?s ex:v ?v }.count() == 1       # consumes the generator
```

`count()` consumes; `len()` deliberately fails, because a lazy match has no
length until it is walked.

### Blank nodes are non-distinguished variables

A blank node in a pattern is matched but not projected — which removes the
throwaway variables (`p`, `tmp`, `bnk`) that the same query needs in rdflib:

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a ex:reading [ ex:value 21 ] . ex:b ex:reading [ ex:value 22 ] }
rows = sorted((str(s), int(v)) for s, v in m{ ?s ex:reading [ ex:value ?v ] })
assert rows == [("http://example.org/a", 21), ("http://example.org/b", 22)]
```

### Joins, in written order

Several patterns are joined by shared variables, evaluated as nested loops in
the order you wrote them — no optimiser, no reordering. The order is therefore
visible and controllable, which is the point: an optimiser could be added
later without changing a single program.

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a ex:parent ex:b . ex:b ex:parent ex:c . ex:b ex:name "B" }
rows = [(a, c) for a, b, c in m{ ?a ex:parent ?b . ?b ex:parent ?c }]
assert rows == [(ex:a, ex:c)]
```

### What `m{ }` does not have

No `FILTER`, `OPTIONAL`, `UNION`, property paths or aggregates. Python's `if`
covers the measured usage of the first, and `s{ }` covers the rest. The
argument for keeping the island small is
[in the design record](../../explanation/designing-the-syntax.md#why-m-and-g-are-different-letters).

### Keep list(g) for a full scan

`m{ }` is for a pattern that selects. A traversal with no selection to make
does not get shorter inside one: `list(g)` becomes
`list(m{ ?s ?p ?o }(g))`, three variables the original code never had to
name, for the same rows in the same order.

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a ex:p 1 ; ex:q 2 . ex:b ex:p 3 }
assert sorted(list(g)) == sorted(list(m{ ?s ?p ?o }(g)))
```

Keep `list(g)` for the whole graph, and reach for `m{ }` once the pattern
narrows what comes back — it pays for itself from the first triple it
excludes.

## `s{ ... }` — a SPARQL query

All of SPARQL, in the language's own syntax, **validated at transpile time**
with rdflib as an oracle: a syntax error in a query surfaces when you save the
file, not on the first execution that reaches it.

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a a ex:Sensor ; ex:v 1 . ex:b a ex:Sensor ; ex:v 2 }
rows = [tuple(r) for r in s{ SELECT ?s ?v WHERE { ?s a ex:Sensor ; ex:v ?v }
                             ORDER BY ?v }]
assert len(rows) == 2
assert bool(s{ ASK { ex:a a ex:Sensor } })
```

The island's value is a **lazy prepared query**. Iterating it — or testing its
truth — executes it against the current graph; calling it rebinds it (see the
[call suffix](bindings.md#the-call-suffix-explicit-context)). Prepared queries
are cached in a small hand-written LRU.

### The prologue is the block's

`PREFIX` and `BASE` lines are not written inside the island: the prologue is
built from the [`@prefix` and `@base` declarations in scope](declarations.md),
so a vocabulary is declared once per file.

### Interpolation in term position only

`{expr}` is allowed where a *term* may stand, and becomes an `initBindings`
entry — never a string substitution. Query text is never concatenated, so the
injection that 238 corpus occurrences perform by hand cannot happen here.

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a a ex:Sensor . ex:b a ex:Other }
cls = ex:Sensor
rows = [r for r in s{ SELECT ?s WHERE { ?s a {cls} } }]
assert len(rows) == 1
```

Inside `s{ }`, `{` is ambiguous between a SPARQL group and an interpolation.
The transpiler settles it with an oracle: balanced content is an interpolation
**iff** it transpiles and then compiles as a Python expression. A SPARQL group
never does, and an interpolation outside term position makes the query invalid
— so rdflib enforces the restriction on its own. (The
[syntax highlighter asks the same oracle](../../how-to/highlight-ldpy.md).)

### Updates

`INSERT`, `DELETE` and the rest go through `graph.update`. An update has no
solutions to iterate, so it is `execute()` that runs it — the island stays
lazy like every other:

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a a ex:Sensor }
s{ INSERT { ?s ex:seen 1 } WHERE { ?s a ex:Sensor } }.execute()
assert len(g) == 2
```

### When rdflib is missing

Validation needs rdflib at transpile time. Without it the island is emitted
anyway, with a warning: the transpiler never *depends* on rdflib to parse the
language — it only uses it as an oracle.

### On a device

`s{ }` is the one island that needs rdflib at **run** time — its engine. A
build with `--target micropython` therefore refuses it, on the host, with a
message that names `m{ }` and `e{ }`; those two run on
[urdflib](https://github.com/linked-data-python/urdflib) as they do here. See
[running on a device](../../explanation/running-on-a-device.md).
