# Linked-Data Python

**Python, with the Semantic Web in its syntax.** IRIs, prefixed names, RDF
literals, SPARQL variables and whole graphs written in Turtle's notation are
expressions of the language — interpolated with arbitrary Python, transpiled to
plain Python, and running on `rdflib`.

```ldpy
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#>.
@base <http://example.org/building/> .

def observation(sensor, value, timestamp):
    return g{ f<sensor/{sensor}> a sosa:Sensor ;
                  sosa:madeObservation
                      [ a sosa:Observation ;
                        sosa:resultTime {timestamp}^^xsd:dateTime ;
                        sosa:hasResult
                            [ qudt:numericValue {value} ;
                              qudt:unit qudt:DEG_C ] ] }

assert len(observation("s1", 21.5, "2026-08-28")) == 7
```

The same seven triples in plain rdflib take nine `add` calls whose order no
longer carries meaning, and in which the nesting of blank nodes has
disappeared. That comparison, side by side, is
[the first page of the rationale](explanation/why.md).

## What you can write

| | | |
|---|---|---|
| **Terms** | `ex:Sensor` · `<http://e/a>` · `"21.5"^^xsd:double` · `?v` · `f<sensor/{id}>` | [reference](reference/language/terms.md) |
| **Graphs** | `g{ ex:s a ex:C ; ex:p {value} }` — a Turtle graph as an expression | [reference](reference/language/graphs.md) |
| **A current graph** | `@graph as g` then `+{ … }` / `-{ … }` to write to it | [reference](reference/language/current-graph.md) |
| **Reading** | `m{ ?s a ex:C ; ex:v ?v }` — a graph pattern, no engine | [reference](reference/language/querying.md) |
| **Querying** | `s{ SELECT … }` — all of SPARQL, checked when you save | [reference](reference/language/querying.md#s-a-sparql-query) |
| **Deferred** | `e{ ?age >= 18 && BOUND(?n) }` — evaluated later, against bindings | [reference](reference/sparql-expressions.md) |
| **Bindings** | `for @bindings in rows:` — any iterable of mappings drives a template | [reference](reference/language/bindings.md) |

Put together, a CSV file becomes a graph, and a graph becomes another graph,
with no mapping language and no query engine:

```ldpy
@prefix ex: <http://example.org/> .
@graph as src
+{ ex:c1 ex:reading 10 . ex:c2 ex:reading 25 }

@graph as out
for @bindings in m{ ?s ex:reading ?v }(src):
    +{ ?s ex:hasValue e{ ?v * 2 } }

assert sorted(int(o) for s, o in m{ ?s ex:hasValue ?o }(out)) == [20, 50]
```

## What it guarantees

| Property | Where it stands |
|---|---|
| **Every valid Python program is a valid ldpy program**, byte for byte | tested on the CPython standard library — 464 files, ~260 000 lines |
| **Speed** — transpilation is on the import path and the keystroke path | 56 000–110 000 lines/s; a 2 000-line module in ~24 ms |
| **Your debugger works** | breakpoints, `pdb` and `debugpy` bind on `.ldpy` lines directly |
| **Your editor works** | LSP server that forwards to an unmodified Python language server |
| **No parsing dependency** | pure Python, no parser generator; emitted code stays in a MicroPython-compatible subset |
| **It runs on a device** | the same programme, transpiled on the host, runs on MicroPython with [urdflib](https://github.com/linked-data-python/urdflib) — `s{ }` excepted, and refused at build time |

Each of these is a design decision with a cost, and each cost is written down —
start with [why island parsing](explanation/island-parsing.md).

## Get started

```text
pip install -e .           # from a clone; add [lsp,debug] for tooling
ldpy program.ldpy          # run a file
ldpy                       # interactive console, islands included
```

Then follow the [tutorial](tutorials/getting-started.md) — twenty minutes, from
your first prefixed name to a graph you query.

## Find your way

This documentation is organised by what you came for.

| I want to… | Go to |
|---|---|
| **Learn** ldpy from zero, hands on | [Tutorial: first steps](tutorials/getting-started.md), then [build a knowledge graph](tutorials/build-a-knowledge-graph.md) |
| **Get something done** | How-to guides: [run & import](how-to/run-and-import.md) · [build from tables](how-to/build-graphs-from-tables.md) · [query](how-to/query-a-graph.md) · [migrate from rdflib](how-to/migrate-from-rdflib.md) · [VS Code](how-to/use-vscode.md) · [debug](how-to/debug.md) · [build for MicroPython](how-to/build-for-micropython.md) |
| **Look something up** | Reference: [the language](reference/language/index.md) · [SPARQL expressions](reference/sparql-expressions.md) · [command line](reference/cli.md) · [Python API](reference/api.md) |
| **Understand why** | Explanation: [why ldpy](explanation/why.md) · [what real code does](explanation/what-real-code-does.md) · [designing the syntax](explanation/designing-the-syntax.md) · [island parsing](explanation/island-parsing.md) · [running on a device](explanation/running-on-a-device.md) |

## Status, honestly

ldpy is a research resource under active development, at version 0.6. The
language is stable enough to write real programs in — the corpus study
translated 140 of them — and the tooling is real. What is *not* settled:

- a plain literal still has no notation outside an island, and neither does a
  variable language tag;
- `@prefix` is lexical, so it does not give you a `Namespace` **object**;
- the MicroPython claim is now proved by execution on the Unix port of
  MicroPython; the ESP32 measurements — flash, RAM, time — are next;
- there has been **no user study**: the claim that this is easier to read is
  examined on found code, not on measured developer performance.

The complete list is in the
[limitations section of the reference](reference/language/lexical.md#known-limitations),
and what the measurements do and do not establish is in
[how this is tested](explanation/how-it-is-tested.md).

Every `ldpy` and `python` block on this site is executed by the test suite, and
its assertions are the test. That is the only promise this documentation makes
about itself.
