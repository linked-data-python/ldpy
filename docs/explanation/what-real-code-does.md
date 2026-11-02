# What real RDF code does, and how it shaped the language

The first wave of ldpy was designed the way syntax usually is: from
requirements set a priori and from what Turtle already offers. That produced
the terms, the graph island and the interpolation rule. Then it was measured
against real code, and the measurement said the notation was addressing about
a third of what RDF programs actually do.

This page is the summary of that measurement and of what was built from it. It
is an *explanation*: the numbers are here to justify the language's shape, not
to be looked up. The full record, with method, thresholds and threats to
validity, is design record `corpus/402`; the measuring tool is
`python -m rdfeval surface`, itself covered by 41 tests.

## How the corpus was built

**5 157 RDF-relevant files, 377 repositories measured**, out of a pinned
manifest of 444 — 38 574 Python files analysed, 191 426 RDF operations
detected. A graph is recognised by how it is called, not only by its name:
an unannotated `graph` parameter is one as soon as the code calls
`graph.value(s, p)` on it.

Selection is expressed as **criteria, never as a list of names**: alive, not a
fork, at least 10 kB of Python and 10 commits, a commit after 2020, a licence
permitting republication of excerpts, and neither course material nor the
library itself. A list of hand-picked exclusions does not survive 400
repositories.

Two of those exclusions are not method detail. Course repositories would count
the same idiom once per student who handed in the same assignment. And
repositories that *are* the library measure rdflib's implementation, not
application code written against it.

The corpus is not concentrated: the largest contributor accounts for 11 % of
`.add` calls, 13 % of selections, 11 % of SPARQL calls, for a median of 25
`.add` per repository. Every ratio below is published twice — pooled and as a
median per repository — because a pooled figure always follows the biggest
contributor.

## The finding that reordered everything

| Family | Occurrences | Files | Repositories |
|---|---:|---:|---:|
| Namespace terms (`NS.term`) | 48 673 | — | — |
| Namespace definitions | 3 627 | 1 160 | 250 |
| Triple addition (`.add`) | 16 892 | 1 292 | 246 |
| Selection / traversal | 12 201 | 1 549 | 239 |
| SPARQL (query/update/prepare) | 1 958 | 486 | 159 |
| Namespace imports within a project | 1 279 | 567 | 63 |
| `initBindings` | 170 | 79 | 46 |

### Reading is as big as writing

1 549 files select triples; 1 292 files add them. The imbalance in ldpy was
right there: the notation served *construction*, and more code reads graphs
than writes them. That single row is the origin of
[`m{ }`](../reference/language/querying.md) and
[`s{ }`](../reference/language/querying.md#s-a-sparql-query).

## Interpolation is the normal regime

Of the triples added in the corpus, **91 % have at least one computed term**;
only 9 % could be written in purely static Turtle, with a median per
repository of **0 %**.

This validated the most debatable decision in the language. A static Turtle
block embedded in Python — the obvious design, and the one several other
projects chose — would be nearly useless. `{expr}` in term position is not a
convenience: it is the normal case, and everything else is the exception.

Three more numbers from the same measurement shaped
[`@graph`, `+{ }` and `-{ }`](../reference/language/current-graph.md):

- **38 % of triples are added alone** (a lone `.add`, no neighbour),
- **43 % of additions are inside a loop** — one triple per iteration,
- **30 % share a subject** with an immediate neighbour, which is what Turtle's
  `;` is for.

And one number that killed an argument we had been making: the receiver name
is long in only 42 % of cases, for a mean of 4.2 characters. `@graph` is not
justified by saving keystrokes on `self.graph`. It is justified by the lone
triple and by the loop, where a multi-triple island amortises nothing.

## One graph at a time

- **67 % of files that manipulate a graph manipulate exactly one**; **87 % of
  functions** likewise.
- `Dataset` / `ConjunctiveGraph`: 520 constructions, **6.7 %** of graph
  constructions.
- Explicitly named graph (`Graph(identifier=…)`): 189, in 38 repositories.

So `@graph` designates *one* current graph, optionally named — the `identifier`
constructor parameter, which costs nothing — and never a space of graphs.

## Namespaces are shared by hand

- 3 627 namespace definitions, **1 025 of them (28 %) inside a function** —
  redefined at every call, for want of a natural place to put them.
- **1 279 imports of a namespace from another module of the same project**, in
  567 files across **63 repositories**. The canonical pattern is a module whose
  only job is to export prefixes, imported everywhere.
- 428 (IRI, repository) pairs are declared in several files of the same
  repository; 149 distinct IRIs are redeclared across repositories.

The need is massive and projects already solve it — with a Python module of
`Namespace` constants. So the question was never whether ldpy should carry
prefix export, but whether its version does better than
`from .namespaces import BRICK`. It does on one precise point: in ldpy
`@prefix` is a *lexical declaration the transpiler consumes*, whereas an
imported `Namespace` is only an object — it does not make `brick:Class`
writable. Without export, ldpy would have **inherited** the duplication instead
of fixing it. Hence
[prefix import/export](../reference/language/declarations.md#prefixes-across-modules).

## SPARQL is not a niche

- **1 958 calls** (1 547 `query`, 149 `update`, 262 `prepareQuery`) in 486
  files across **159 repositories — 42 % of those measured**.
- **58 % of calls carry a literal query text** (median per repository 67 %);
  794 distinct queries occupying **5 834 source lines**.
- SELECT dominates (934), then INSERT (45), ASK (43), CONSTRUCT (33), DELETE (23).
- 273 `for row in g.query(...)`, 212 hand-offs to a function, 112
  comprehensions: iterating solutions is the consumption pattern.
- 178 queries are built by interpolation, and **223 inject an RDF term into the
  query text**, often via `.n3()`, in 85 files across 48 repositories.

Two out of five repositories write SPARQL, and each such file holds static,
multi-line query text — exactly what an island accepts, and exactly where
transpile-time validation pays, since today a typo in a query surfaces only
when execution reaches it.

The last line is a security finding as much as an ergonomic one. When
developers want to bind a variable, they do it by **string concatenation**.
A safe binding is therefore worth having *as a replacement for a dangerous
practice* — and it comes for free once the island accepts interpolation in
term position.

Two reservations, measured too: 42 % of calls pass text the analysis cannot
see, and those will stay strings; and everything said about query *shapes*
holds for the other 58 %.

## Traversal is frequent, and flat

- 12 201 selector calls: `objects` 3 743, `value` 3 048, `triples` 2 229,
  `subjects` 2 141; the rest is marginal.
- **38 % of selections feed a loop or a comprehension directly.**
- Multi-step navigation: **1 385 occurrences, 11 % of calls**, and shallow —
  178 at depth 2, 54 at depth 3, 29 at depth 4.
- "The single expected value" weighs **3 549 occurrences** (3 048 `value`,
  501 `next(...)`).

This is the result that most contradicted our prior. A *graph traversal* syntax
in the manner of Gremlin or Cypher would have answered a rare pattern. Real
code selects **one step at a time** and composes with Python's loops. What
needed lightening was the selection itself and the "single expected value" —
which is why `m{ }` has `.first()` and `.one()`, and why arity 1 yields terms
rather than one-element tuples.

## What the numbers changed about our plans

Six extensions had been proposed a priori. Confronting them with the corpus
changed two and reduced a third:

| Proposed | Became | Because |
|---|---|---|
| chained graph navigation | a [match island](../reference/language/querying.md) (a join, not a chain) | deep navigation is under 1 % of selections, and always in nested loops |
| a binding operator `g @ {…}` | [`@bindings`, a lexical context](../reference/language/bindings.md) | binding is a context, not an operation |
| named graphs in a dataset | `Graph(identifier=…)` only | datasets are 6.7 % of constructions |

The methodological reversal itself paid off: two of the six a-priori ideas
would have missed, and one dismissed as secondary — reading — turned out to be
as large as writing.

## What the notation still does not reach

A separate, manual review of 40 translated programs (design record `ldpy/012`)
found what the notation does not address. Some of it has since been built; the
rest is deliberate scope, stated rather than hidden:

- **A plain literal has no notation outside an island.** `Literal("x")` stays
  as it is, and a *variable* language tag has no form at all.
- **Prefixes are not objects.** `@prefix` is lexical; it does not give you a
  `Namespace` value to pass around. Export
  ([record 013](../reference/language/declarations.md#prefixes-across-modules))
  answered the sharing half of this, not the reification half.
- **Strings stay opaque** — deliberately. CURIEs carried by *data*
  (`method="qb:CodedProperty"`, query text, INI files) are never captured. The
  same review confirmed this at scale, and it is a feature.

And two traps for anyone translating rdflib code by hand, both verified:
`Literal(40, datatype=XSD.double)` is **not** the same term as
`"40"^^xsd:double` (rdflib normalises the lexical form to `40.0`), and
rewriting `URIRef(x)` as `f<{x}>` is only exact when no `@base` is in scope.
Both are in the [migration guide](../how-to/migrate-from-rdflib.md).

## What comes next

Each implemented decision has to be **re-measured on the same corpus**:
`rdfeval surface` is reproducible and its counters are tested one by one, so
the before/after comparison is direct. That second evaluation — re-translating
the corpus against the extended language, measuring coverage of the regions
that were previously out of reach — is planned and not yet run.

## Threats to validity

Stated here because they bound every number above.

- 377 repositories is enough for solid orders of magnitude and per-repository
  medians, not for a probabilistic sample of "all RDF code". The corpus is
  purposive: four discovery channels, then explicit quality criteria.
- **The selection criteria are themselves a bias.** Requiring a licence that
  permits extraction excludes 460 candidates with no declared licence;
  requiring a commit after 2020 excludes 196 more. The corpus describes RDF
  code that is *alive and publishable*.
- The analysis is syntactic: a receiver is a graph when it is built, typed
  or bound as one, or when it is called the way only an rdflib graph is
  (`triples((…))`, `objects(s, …)`, `value(s, p)`, `add((…, ns.term, …))`).
  An `.add` on a receiver that is none of these is not counted. **All counts
  are lower bounds** — the first analyser, which recognised a graph only by
  its name, undercounted selections by a third.
- "Static term" is approximated by syntactic form, so the true share of static
  triples is slightly above 9 %.
- All thresholds are a judgement call. They live in a configuration file, not
  in the code, and are versioned.
