# Why island parsing, and no grammar for Python

The obvious way to implement a syntactic extension is to write a grammar of the
extended language, generated with ANTLR or a GLR/PEG tool. The first ldpy
release (2023) did exactly that, and its limitations motivated the present
design:

- a grammar of 800+ lines to maintain against a host language that changes
  every year;
- throughput around **170 lines per second** — unusable at import time, and
  hopeless for a language server that re-parses on every keystroke;
- lexical priority that silently stole valid Python: `a<b>c`, a chained
  comparison, was lexed as an IRI.

## The inversion

The v2 transpiler follows Moonen's *island grammars*: there is **no grammar for
Python at all**. A single-pass scanner copies the "water" verbatim and hands
control to a recursive-descent parser only on island triggers.

```text
source .ldpy
  → Scanner
      · Python lexical awareness only: strings in every form, comments,
        bracket depth, logical lines, and the operand-context bit
      · copies non-island text verbatim
      · on an island trigger → island parser
  → Island parsers (recursive descent)
      · declarations, terms, graphs, patterns, queries, expressions
      · a nested Python expression ({expr}) is re-scanned by the Scanner
        — mutual recursion between the two
  → Emission: one Python expression per island, plus a segment-level
    language map
```

The scanner still needs *lexical* knowledge of Python — and one crucial bit
beyond it: the **operand-context flag**, "may the next token begin an
operand?". This is the same device JavaScript engines use to tell division from
a regex literal, and it is what disambiguates `<` as comparison versus IRI
without parsing expressions at all.

## Three consequences

**Throughput is linear and dominated by copying.** 56 000–110 000 source
lines/s depending on island density; a full parse of the host is never paid.
The cost of an island is amortised by its size: files made only of graph
expressions run from 35 000 lines/s at one triple per graph to 51 000 at a
hundred — large graphs are proportionally cheaper than many small ones. For the
editing loop, a 2 000-line module re-transpiles in about 24 ms.

**Host transparency is true by construction.** Text without island triggers is
copied byte for byte. That turns [R3](why.md#r3-host-language-transparency)
from an aspiration into something a test can assert over the entire CPython
standard library, which it does — see
[how this is tested](how-it-is-tested.md#transparency).

**Zero parsing dependency.** The transpiler is pure Python with no parser
generator, no binary, no runtime library, which keeps the door open to running
it *on* MicroPython. rdflib is a dependency of the runtime, and — since the
SPARQL island — an *oracle* at transpile time; it is never a parser of the
language.

## What it costs

Every ambiguity between the two syntaxes must be found, decided and documented
by hand. A grammar would have surfaced them mechanically, as conflicts. The
[lexical reference](../reference/language/lexical.md) lists the rules and the
residual cases; each one has a test in both directions, and that discipline is
the price of the approach.

The alternatives were weighed and are recorded in `ldpy/001`:
tree-sitter (fast and incremental, but a native binary, and it excludes
MicroPython — kept as a possible *complement* for editors), ANTLR targeting
C++ (a real speed-up, but a binary dependency and still paying to re-parse all
of Python), and the Python-parsing libraries (`lark`, `parso`, `libcst`), where
INDENT/DEDENT and contextual islands would have required a deep fork.
