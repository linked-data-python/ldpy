# Why island parsing (and no Python grammar)

The obvious way to implement a syntactic extension is a full grammar of the
extended language, generated with ANTLR or a GLR/PEG tool. The first ldpy
release (2023) did exactly that, and its limitations motivated the present
design: a grammar of 800+ lines to maintain against a host language that
changes yearly, throughput around a hundred lines per second, and lexical
priority that stole valid Python (`a<b>c` read as an IRI).

The v2 transpiler inverts the approach, following Moonen's *island grammars*:
there is **no grammar for Python at all**. A single-pass scanner copies the
"water" verbatim and hands control to a recursive-descent parser only on
island triggers. The scanner still needs *lexical* knowledge of Python —
strings in all their forms, comments, bracket depth, and one crucial bit: the
**operand-context flag** (may the next token begin an operand?), the same
device JavaScript engines use to tell division from regex literals. This is
what disambiguates `<` as comparison vs IRI without parsing expressions.

Three consequences:

1. **Throughput** is linear and dominated by copying: 56k–110k source
   lines/s depending on island density; a full parse of the host is never paid.
2. **Host transparency is true by construction**: text without island
   triggers is copied byte-for-byte. The 468 files of the CPython stdlib
   round-trip identically; that is a test, not a hope.
3. **Zero parsing dependency**, which keeps the door open to running the
   transpiler itself on MicroPython.

The trade: every ambiguity between the two syntaxes must be found, decided
and documented by hand (design record 002 lists the rules and the residual
cases). A grammar would have surfaced them mechanically — as conflicts.
