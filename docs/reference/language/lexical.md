# Lexical rules, character sets and limits

This page is the part of the reference you consult when something did *not*
happen: a prefixed name that stayed Python, an IRI that was read as a
comparison, an accented local name. The rules are few and closed; the reasoning
behind them is in
[designing the syntax](../../explanation/designing-the-syntax.md).

## The rule that governs all the others

**Every valid Python program is a valid ldpy program with unchanged meaning.**
The extension may therefore only occupy syntax that Python leaves illegal, and
every ambiguity is resolved *in Python's favour*. Where that is impossible, the
case is listed below and there is a spelling that forces the Python reading.

## Rule 1: operand context

The scanner tracks one bit — may the next token begin an operand? — the same
device JavaScript engines use to tell division from a regular expression.

- `<` opens an IRI **only** in operand context: after `=`, `(`, `[`, `,`,
  `return`, an operator, a keyword. After a name, a number, a string, `)` or
  `]` it is the comparison operator.
- `f<` and `e<` follow the same restriction.
- `?` and `$` are never valid Python, so they are always islands, whatever the
  context — which is also why their error messages can be precise.

```ldpy
a, b, c = 3, 2, 1
assert (a < b > c) is False          # chained comparison, untouched
t = <http://example.org/x>           # operand position: an IRI
assert str(t) == "http://example.org/x"
```

## Rule 2: strict adjacency

The sigil and its delimiter must touch, and so must a literal and its RDF
suffix:

| Island | Requires | Otherwise |
|---|---|---|
| `g{` `f{` `e{` `?{` `m{` `s{` | no space before `{` | `g {` stays Python |
| `f<` `e<` | no space before `<` | comparison |
| `"x"@en` | no space around `@` | `'a' @ en` is matrix multiplication |
| `"x"^^t` | no space around `^^` | — (`^^` is never adjacent-valid Python) |
| `p:local` | no space around `:` | slice, dict, annotation |
| `_:{expr}` | no space around `:` | annotation of the name `_` |

`NAME{` is never valid Python, so nothing is lost by claiming it — and the
space is the escape hatch when you want the Python reading back.

## Rule 3: declared prefixes, and backtracking

`p:local` is a prefixed name **only if** `p` was declared by a lexically
earlier `@prefix` in scope, and the local part starts with a letter, `_` or
`{`. An IRI attempt that does not close on the same line backtracks and `<`
is re-emitted as an operator.

This is why `arr[i:j]` and `{k: v}` are untouched: `i`, `j` and `k` are not
declared prefixes.

Two positions are Python's even when the name *is* a declared prefix, because
the `:` there belongs to Python and nothing else could be meant:

```ldpy
@prefix ex: <http://example.org/ns#> .
f = lambda ex:ex                    # a lambda parameter named ex
def g(ex:int = 0): return ex        # a parameter annotation
def h(x = ex:Thing): return x       # but after "=" it is a value: a term
assert str(h()) == "http://example.org/ns#Thing"
```

## The closed list of island letters

The sigil rule applies to a **closed list**, enumerated here and nowhere else:

| Form | Island |
|---|---|
| `g{` | [graph](graphs.md) |
| `f{`, `?{`, `f<` | [formatted node / IRI](terms.md), evaluated immediately |
| `e{`, `e<` | [deferred expression / IRI](../sparql-expressions.md) |
| `m{` | [match pattern](querying.md) |
| `s{` | [SPARQL query](querying.md) |

There is no long alias (`sparql{`, `graph{`): it would turn the rule into "any
identifier glued to `{`" and spread the ambiguity surface over all code, for a
cosmetic gain.

### Two forms outside the sigil rule

- **`+{ … }` and `-{ … }`** are accepted in **statement position** at bracket
  depth zero: at the start of a logical line, after a `;`, and as the suite of
  a compound statement — `if cond: +{ … }` on one line. The sigil and the
  brace must still touch, as in rule 2: `+ { … }`, with a space, stays
  Python. Elsewhere `+` and `-` keep their Python meaning (`keys - {'a'}` is a
  set difference). In statement position `+{…}` *is* legal Python but always
  dead — unary plus on a set or a dict raises `TypeError` — so the capture
  costs no real program.
- **`@graph` and `@bindings`** are told from a decorator the same way
  `@prefix` and `@base` are: the line is an island only if the rest of it
  matches the declaration form. `@graph` alone on its line, or followed by `(`
  or `.attr`, remains a decorator.

The one-line suite matters because the code being translated is full of
`if cond: g.add(…)`. Without it every such line had to be opened into a block,
and the translation came out longer than the original it replaced.

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
for i in range(3):
    if i: +{ ex:s ex:p {i} }
    else: -{ ex:s ex:p 0 }
assert len(g) == 2
```

### Three forms that extend illegal Python

All three occupy syntax Python rejects, so nothing is repurposed:

- `from m import brick:, unit: as u:` — a prefixed name in an import list;
- `for @bindings in it:` — a declaration as a `for` target;
- `global @prefix …` / `nonlocal @graph …` — a modifier before a declaration.

The [call suffix](bindings.md#the-call-suffix-explicit-context) is *not* a
lexical extension: on islands that are expressions, it is an ordinary Python
call.

## Residual ambiguities

Two cases where a declared prefix wins over the Python reading. Both are
documented, tested, and have an escape:

```ldpy
@prefix ex: <http://example.org/> .
ex, b = "key", "value"               # two ordinary Python names
d = {ex:b}                           # in Python: the dict {"key": "value"}
assert d == {<http://example.org/b>}      # in ldpy: a set with one IRI
assert {ex: b} == {"key": "value"}        # spaces give Python back
```

| Written | Read as | To force the Python reading |
|---|---|---|
| `{ex:b}` | a set containing the prefixed name | `{ex: b}` |
| `arr[ex:b]` | indexing by the prefixed name | `arr[ex : b]` |

Both need `ex` to be a **declared prefix** *and* a Python name in the same
file, which is the situation to avoid — and the transpiler warns when it sees
you enter it, naming the prefix and pointing at the spelling that gives the
Python reading back.

!!! note "Diagnostics are currently emitted in French"

    Transpiler errors and warnings are the one part of the toolchain still
    written in French; translating them is planned and does not change what
    they detect.

The detection is deliberately an **approximation**: knowing where Python binds
a name would mean parsing Python, which the island parser does not do. It
fires on the declared prefix used as the target of an assignment at the start
of a statement — `ex = …`, `ex, other = …` — which covers the way the case
actually arises, and stays silent elsewhere. A prefix shadowed by a `for`
target or a function parameter is not caught; design record `ldpy/002` records
the reasoning.

## Character sets

**Inside islands, Turtle's exact `PN_CHARS` tables apply.** Prefixed names
accept hyphenated and dotted prefixes (`o-pizza:Named`), digit-initial local
parts (`ex:1a`), interior dots, `·` and combining marks.

**Outside islands, the intersection** of Python identifiers and `PN_CHARS`
applies — which is what guarantees that a valid Python program can never be
captured:

```ldpy
@prefix ex: <http://example.org/> .
assert str(ex:café) == "http://example.org/café"
```

- `-` stays subtraction outside an island, so `o-pizza:Named` is declarable and
  usable inside islands only.
- Python-only identifier characters (`µ`, `ª`) end a local part — Turtle could
  not write them either.
- Local parts support neither an interior `:` nor `%`/`\` escapes.

These rules are verified against an independent transcription of both
specifications by `tools/charsets.py`. The final decision on the residual
divergence is still open; the current state is frozen by tests, and
[why the seam falls where it does](../../explanation/designing-the-syntax.md#two-character-sets-that-do-not-coincide)
is explained separately.

## Known limitations

- **Python string contents are opaque.** No island inside an f-string; write
  `f<...>` rather than `<...{x}...>` (the error message says so). This is the
  behaviour that keeps CURIEs carried by *data* — `method="qb:CodedProperty"`,
  SPARQL text, INI files — from ever being captured.
- **PEP 701 f-strings** (same-quote nesting) are unsupported, as in
  MicroPython.
- **Emitted code stays in a Python-3.4-level subset**; f-strings written in
  your source pass through unchanged.
- **`e{ }` may not be used inside `s{ }`**, and custom SPARQL functions called
  by IRI are not supported — use a `{python}` interpolation.
- **`s{ }` does not run on a device**: `--target micropython` refuses it at
  build time; `m{ }` and `e{ }` do run there.
- **A plain literal has no notation outside an island**: a bare Python string
  stays a string. So does a *variable* language tag.
- **A breakpoint inside a multi-line `g{ }`** binds on the island's first line:
  the graph is one expression.

The reasoning that puts these where they are, and what the corpus study says
about how much they cost, is in
[what real RDF code does](../../explanation/what-real-code-does.md#what-the-notation-still-does-not-reach).
