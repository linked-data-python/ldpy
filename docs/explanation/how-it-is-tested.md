# How this is tested

The claims made on this site are meant to be checkable, and most of them are
checked automatically. This page says exactly which, and by what — including
where the checking stops.

## The documentation runs

Every `ldpy` and every `python` block on this site is extracted by
`tests/test_docs.py`, transpiled where applicable, compiled and **executed**;
its `assert` statements are the test. A snippet that does not run cannot stay
on the site, and a number in an assertion cannot drift from the code.

Two limits worth stating. Blocks marked `text` are *not* executed — they show
shell commands and forms that are deliberately illegal Python. And running a
snippet proves it works, not that it is the best way to write what it shows.

Since the [syntax highlighter is built on the transpiler](../how-to/highlight-ldpy.md),
the same blocks are also lexed by `tests/test_pygments_lexer.py`, which checks
that none produces an error token and that the tokens reconstruct the source
exactly.

## Transparency

[R3](why.md#r3-host-language-transparency) — every valid Python program is a
valid ldpy program, unchanged — is the strongest claim in the project, so it is
tested three ways:

1. **The CPython standard library**, first two directory levels: every `.py`
   file is transpiled and compared with its input byte for byte. On CPython
   3.12 that is 464 files and about 260 000 lines. The standard library
   exercises comparison operators, slices, dictionary displays, decorators,
   matrix multiplication, nested f-strings and every string form — exactly the
   constructs the islands might collide with.
2. **The project's own sources**, on every run.
3. **Adversarial snippets**, one per known collision, each asserting that the
   Python reading survives: `a<b>c`, `d[i:j]`, `{k: v}`, `x @ w`, `keys - {'a'}`,
   `f"val {x!r:>{w}} fin"`, and the rest.

This is not a formality. The stdlib check was added while writing this
documentation and immediately found a violation — a `:` inside a comment in a
parenthesised import list was making the transpiler rewrite the statement as a
prefix import. That is what the test is for.

The same property is what the 2023 ANTLR-based version fails: its lexer rejects
15 of 20 such pure-Python files, invariably on chained comparisons lexed as
IRIs.

## Correctness of the transformation

The suite is layered, and each layer answers a different question.

| Layer | Question |
|---|---|
| Scanner unit tests | does it know Python's lexical forms — every string form, comments, bracket depth? |
| Identity tests | is pure Python returned unchanged? |
| Golden tests | is the generated code exactly what we decided, for each island in each syntactic position? |
| Execution tests | does the generated code build the graph we mean? Compared with an expected Turtle document by **RDF isomorphism**, with rdflib as an oracle — never as a parser of the language |
| Disambiguation tests | each rule, in both directions |
| Semantic tests | block scope, evaluation order, the single-evaluation property |
| Map tests | the language map, and its Source Map v3 export against an independent decoder |
| Tooling tests | import hook, interactive console, and the language server end to end — a minimal LSP client in the tests drives the real server with a real Python language server behind it |
| MicroPython subset | an AST whitelist over everything the emissions produce |

Two of these are only possible because of a design decision. Golden tests
require the emitted code to be **deterministic**, which the
[single-expression emission](emission-and-semantics.md) makes true (the 2023
version used `secrets` and could not be golden-tested). And a reproducible
benchmark requires a **deterministic generator**, which is what `bench/` is.

## Performance

Throughput is measured by `python -m bench.run`, a campaign harness over
seeded random ldpy programs with controlled island density, file size and graph
size. The headline numbers — roughly 84 000 lines/s on pure Python down to
38 000 in the worst case where every statement holds an island; linear in file
size from 200 to 50 000 lines (measured 2026-11-02) — are reproducible from
the repository.

They come from **one machine and one CPython version**. Treat them as orders of
magnitude.

## What is not tested

Stated plainly, because a page like this is worth nothing if it only lists
successes.

- **That the language is easier to use.** A user study is running; it has no
  result yet. The parity claim is examined on found code — 325 of 333
  translated regions proved equivalent to the original by execution (graph
  isomorphism, or equality of the values read), none yet approved by human
  review — not on measured developer performance.
- **R6, on a device.** The generated code is proved to stay within a
  Python-3.4-level subset by an AST whitelist, and runs on the Unix port of
  MicroPython over urdflib; flash, RAM and time on a microcontroller (ESP32)
  are not measured yet.
- **The benchmark's realism.** The generator's output is adversarial and
  executable, but follows a synthetic distribution no human corpus follows. The
  standard library and the corpus study mitigate that bias; they do not remove
  it.
- **The corpus study's generality.** Its
  [threats to validity](what-real-code-does.md#threats-to-validity) are part of
  its findings.

## Running it yourself

```text
pip install -e .[dev]
python -m pytest tests -q
```
