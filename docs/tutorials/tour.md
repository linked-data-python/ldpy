# Tutorial: the whole language, in one file

The two other tutorials build something with you, step by step. This one is a
different shape: **a single `.ldpy` file you run**, whose comments introduce the
notation as it goes. Each section builds something, prints it, and asserts what
it should be — so if the file runs to the end, everything its comments claim is
true on your machine.

```text
pip install linked-data-python
ldpy tour.ldpy
```

It prints one line per section:

```text
1-2. terms   http://example.org/thermometer | http://example.org/building/room/R101 | "Thermometer A"@en | "21.5"^^<http://www.w3.org/2001/XMLSchema#double>
3.   built   http://example.org/building/room/R101 | http://example.org/R101
4.   graph   6 triples, blank node included
5.   current 10 triples after three loops and one removal
6.   matched 3 observations, 2 with a result
7.   filter  2 observations above 21 °C
8.   mapped  6 triples from 2 CSV rows
9.   queried [22.0, 21.5]
10.  serialised 19 lines of Turtle
```

Take it as a reference card that compiles: read it once through, then keep it
open and change things — the assertions will tell you when you have understood
something differently from the language.

[Download `tour.ldpy`](tour.ldpy){ download="tour.ldpy" }

--8<-- "tutorials/tour.ldpy"

## Where each notation is explained in full

| Section | Notation | Reference |
|---|---|---|
| 1 | `@prefix`, `@base` | [declarations and scope](../reference/language/declarations.md) |
| 2–3 | IRIs, prefixed names, literals, `f<…>` | [terms](../reference/language/terms.md) |
| 4 | `g{ … }` | [graphs](../reference/language/graphs.md) |
| 5 | `@graph`, `+{ }`, `-{ }` | [the current graph](../reference/language/current-graph.md) |
| 6 | `m{ … }` | [reading a graph](../reference/language/querying.md) |
| 7 | `e{ … }` | [SPARQL expressions](../reference/sparql-expressions.md) |
| 8 | `for @bindings in …` | [bindings and templates](../reference/language/bindings.md) |
| 9 | `s{ … }` | [SPARQL queries](../reference/language/querying.md#s-a-sparql-query) |
