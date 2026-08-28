# Bindings, templates and the call suffix

A **solution mapping** — variables bound to terms — is the value that flows
between reading and writing. `m{ }` produces them, `s{ }` consumes and
produces them, a `csv.DictReader` produces them for free, and a graph template
consumes them. `@bindings` names the current one; `e{ }` computes over it.

## `@bindings` — the current bindings

To bindings what [`@graph`](current-graph.md) is to graphs: a declaration with
[block scope](declarations.md#block-scope) whose value is a mapping.

| Form | Effect |
|---|---|
| `@bindings b` | designate the existing mapping `b` as current |
| `@bindings as b` | create a fresh empty `Bindings`, bind it to `b` |
| `for @bindings in ITER:` | each element of `ITER` is the current bindings of the body |
| `for @bindings as b in ITER:` | same, and name it `b` |

Keys may be `str` or `Variable`; values may be RDF terms or plain Python
values, [coerced on the way in](coercion.md).

## Templates: a graph with variables

Without bindings in scope, a `g{ ... }` containing variables is a
**template** — the variables stay `Variable` terms, and the graph is data
about a pattern:

```ldpy
@prefix ex: <http://example.org/> .
template = g{ ?s ex:level ?v }
assert {type(t).__name__ for t in list(template)[0]} == {"Variable", "URIRef"}
```

With bindings in scope, the same island is **instantiated**: bound variables
become terms, blank nodes are fresh, and a triple that still holds an unbound
term is dropped.

```ldpy
@prefix ex: <http://example.org/> .
@bindings as b
b["s"], b["v"] = ex:a, 3
filled = g{ ?s ex:level ?v ; ex:missing ?nothing }
assert len(filled) == 1                       # the unbound triple is gone
assert (ex:a, ex:level, None) in [(s, p, None) for s, p, o in filled]
```

## `for @bindings in ITER:` — the loop that carries them

The loop target is a *declaration*, not a Python name: there is no loop
variable to invent and no `@bindings b` line to write. It accepts **any
iterable of mappings**, which puts a CSV reader one line away from a graph.

```ldpy
@prefix ex: <http://example.org/> .
@graph as out
rows = [{"id": "a", "v": 1}, {"id": "b", "v": 2}]
for @bindings in rows:
    +{ ex:{?id} ex:value ?v }
assert len(out) == 2
```

Chained with a match island, it is a CONSTRUCT with no query engine and no
query text:

```ldpy
@prefix ex: <http://example.org/> .
@graph as src
+{ ex:c1 ex:reading 10 . ex:c2 ex:reading 25 }
@graph as out
for @bindings in m{ ?s ex:reading ?v }(src):
    +{ ?s ex:hasValue e{ ?v * 2 } }
assert sorted(int(o) for s, o in m{ ?s ex:hasValue ?o }(out)) == [20, 50]
```

Read that last block twice: `m{ }` yields solutions, the loop makes each one
current, `+{ }` instantiates its pattern against it, and `e{ ?v * 2 }` computes
a term from it. Four islands, one control flow — Python's.

## `e{ ... }` in term position

Inside `g{ }`, `+{ }` and `-{ }`, a
[deferred expression](../sparql-expressions.md) may stand where a term may. It
is evaluated against the same bindings, with SPARQL's semantics: an error —
an unbound variable, an impossible operation — leaves the term unbound, and
the triple is dropped rather than filled with something wrong.

```ldpy
@prefix ex: <http://example.org/> .
@graph as out
for @bindings in [{"s": ex:a, "v": 10}, {"s": ex:b}]:
    +{ ?s ex:doubled e{ ?v * 2 } }            # second row has no ?v
assert len(out) == 1
```

## The call suffix: explicit context

An island followed by a parenthesis receives the context it would otherwise
have read around it — **graph first, bindings second**, both optional,
`bindings=` to give only the second. One rule, six islands:

| Written | Means |
|---|---|
| `m{ P }(g)` | match `P` against `g` |
| `m{ P }(g, b)` | …with `b` as initial bindings (projected in, like `initBindings`) |
| `s{ Q }(g, b)` | run `Q` on `g` with `b` |
| `+{ P }(g)` / `-{ P }(g)` | write to `g` |
| `+{ P }(bindings=b)` | instantiate against `b`, write to the current graph |
| `e{ E }(b)` | evaluate `E` against `b` |
| `g{ P }(b)` | the template instantiated against `b` |

```ldpy
@prefix ex: <http://example.org/> .
from rdflib import Graph
src, out = Graph(), Graph()
+{ ex:a ex:v 1 . ex:b ex:v 2 }(src)
template = g{ ?s ex:copied ?v }
for sm in m{ ?s ex:v ?v }(src).solutions():
    out += template(sm)
assert len(out) == 2
```

The suffix overrides the declared context for that island only, and nothing
else changes: for islands that are expressions, this is an ordinary Python
call on the island's value — not a lexical extension.

`e{ E }(b)` is not a new rule either: it is the
[`expr(sm)`](../sparql-expressions.md) call that deferred expressions have
always had.
