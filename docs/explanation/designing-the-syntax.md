# Designing the syntax

Every form in ldpy had to clear the same bar: it must occupy syntax that Python
leaves illegal, or resolve in Python's favour. That constraint —
[R3, host transparency](why.md#r3-host-language-transparency) — is what makes
the design interesting, because it removes most of the obvious answers.

This page collects the reasoning. The formal rules are in the
[lexical reference](../reference/language/lexical.md); the decisions themselves
are recorded one per file in `pilotage/design/ldpy/`.

## The doctrine: extend only where Python is illegal

Four kinds of collision had to be settled: `<` (comparison vs IRI), `:` (slice,
dict, annotation vs prefixed name), `@` (decorator, matrix multiplication vs
`@prefix` and language tags), `{` (dict, set vs the island sigils).

The first release (2023) settled them with lexical priorities in an ANTLR
grammar — which meant *silently*. `a<b>c`, a perfectly ordinary chained
comparison, was lexed as an IRI. That failure is why the current design states
its rules and tests each one in both directions.

The three rules are [in the reference](../reference/language/lexical.md). What
is worth explaining here is why they are rules and not a grammar.

**Operand context** is borrowed, deliberately, from JavaScript engines, which
use exactly this bit to tell division from a regular-expression literal. It is
the smallest amount of syntactic knowledge that settles `<`, and it needs no
expression parser.

**Strict adjacency** exploits a fact about Python rather than a convention:
`NAME{` is never valid Python. Claiming it costs no real program, and the space
character becomes the escape hatch in both directions.

**Declared prefixes** make the prefixed name a *contextual* token. This is the
one rule that leaves residual ambiguities — `{ex:b}`, `arr[ex:b]` — and they
are listed rather than argued away. A grammar would have surfaced them
mechanically, as conflicts; by hand they must be found, decided and documented.
That is the honest cost of the approach.

## The closed list of sigils, and the refusal of long aliases

`sparql{ … }` would read better than `s{ … }`. It was refused, and the reason
generalises: adjacency is safe *because* the rule is "a one-letter identifier
glued to `{`". Turn it into "any identifier glued to `{`" and the ambiguity
surface spreads over every call site in every program, for a cosmetic gain.

So the list of island letters is closed, enumerated in one place, and short:
`g`, `f`, `e`, `?`, `m`, `s`.

Two forms sit outside the rule, and each pays for itself:

- **`+{ … }` / `-{ … }`** are admitted only at the start of a logical line at
  bracket depth zero. The lexical argument is precise: `keys - {'a'}` is a very
  common set difference, so the form cannot be claimed generally — but in
  statement position `+{…}` is legal Python that is always *dead* (unary plus
  on a set raises `TypeError`). The scanner already tracks both bits.
- **`@graph` and `@bindings`** are told from decorators exactly as `@prefix`
  is: the line is an island only if the rest of it matches the declaration
  form.

And three forms extend syntax Python *rejects*, so nothing is repurposed at
all: a prefixed name in an import list, a declaration as a `for` target, and a
scope modifier before a declaration.

## Why the emitted graph is one expression

The tempting implementation is to hoist graph construction into statements
before the current one. It is wrong three times over, and the reasons are
semantic, not stylistic — [emission and semantics](emission-and-semantics.md)
has the detail. The consequence for the *syntax* is what matters here: because
an island is an expression, it may appear in a lambda, a comprehension, a
default argument. Had emission been statement-based, the language would have
had to forbid islands exactly where they are most useful.

## Why `m{ }` and `g{ }` are different letters

`m{ P }` **is** `g{ P }`: same parser, same term rules, same interpolation.
What `m{` adds is not syntax but an *operator*. Three arguments settled it:

1. `g{ … }` already has an iteration semantics — walking its triples. If a
   `g{}` containing variables also meant "match this", then `for x in g{ … }`
   would change meaning depending on whether a `?` appears inside the braces.
   The reader would have to re-read the contents to know whether the loop walks
   three triples or launches a join against a graph not named on the line.
2. The two forms go in **opposite directions**: `g{}` builds without reading;
   `m{}` reads an ambient graph and produces bindings. Instantiation and
   matching are the two directions of one relation — pattern × graph ×
   bindings — and the [call suffix](../reference/language/bindings.md#the-call-suffix-explicit-context)
   gives each the operand it consumes.
3. It is the convention already established: `f{}` and `e{}` hold the same
   content and differ by evaluation regime. ldpy chose a letter to say so
   rather than an inference.

An earlier draft argued that `m{ }` existed because rdflib's SPARQL engine is
out of reach on MicroPython. That argument was wrong and has been withdrawn: it
would justify forbidding `s{ }` on a device, not adding an island. What
MicroPython does justify is `m{ }`'s *implementation* — nested-loop join over
`triples()`, no optimiser.

## Why the call suffix is one rule and not six

An early draft had `+{ P }(b)` passing bindings and `m{ P }(g)` passing a
graph: two notations identical in appearance and opposite in meaning. The
replacement is a single rule — **an island followed by a parenthesis receives
the context it would have read around it, graph first, bindings second** — and
it covers all six islands. For `e{ }` it was already true: `expr(sm)` is that
call.

The suffix is not a lexical extension. On islands that are expressions it is an
ordinary Python call on the island's value, which is why it needed no rule in
the scanner at all.

## Why `@bindings` is a declaration and `Coercion` is not

Both add context that islands read. They are not the same kind of thing.

`@prefix`, `@base`, `@graph` and `@bindings` are lexical declarations because
they feed the **transpiler**: it must know, at transpile time, which IRI a
prefixed name denotes and which variable holds the current graph. A conversion
policy feeds nothing at transpile time — it is run-time state. Python already
has the construct that gives run-time state a scope, and it is `with`.

Making `Coercion` a value rather than a global setting bought one thing a
setting cannot give: policies **stack**, and an inner `with` *refines* the
outer one instead of replacing it.

## Why scope is Python's block, not Turtle's document

`@prefix` in Turtle holds to the end of the document. In ldpy it holds to the
end of the enclosing suite. The reason is that the enclosing construct is
Python's: a declaration that outlived its `def` would be the only thing in the
file that did, and the reader would have to track it by hand.

That choice also makes prefix *export* natural — a module-level declaration is
exported, one inside a function is private, and no new rule is needed to say
so. And it made `global` / `nonlocal` free, because the four declarations
already carry their binding in an emitted Python variable: `global @graph` has
only to emit `global _ldpy_g_3`, and Python's scope does the work.

The rule for what those modifiers do is one line: **whatever Python does.**
There is no warning on `global @prefix`, for the same reason there is none on
`global x; x = 1`.

## Where the second wave came from

Everything above concerns forms chosen from first principles. The constructs
added in 2026 — prefix import/export, the current graph, `m{ }`, `s{ }`,
`@bindings` — were not: each was derived from a measured need in a corpus of
376 repositories, and two of the six ideas we had proposed a priori turned out
to be aimed at patterns the corpus does not contain. That story is
[here](what-real-code-does.md).
