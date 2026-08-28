# Tooling architecture: reuse, do not reimplement

The requirement behind the tooling is economic. A language that needs its own
debugger and its own IDE analysis engine will not be maintained by one team —
so ldpy reuses Python's, through three mechanisms.

## Mapped compilation

`.ldpy` code is compiled to code objects that carry the **source** file name
and **source** line numbers. Tracebacks, `pdb` and `debugpy` therefore speak
`.ldpy` coordinates natively: a breakpoint set on line 7 of the `.ldpy` file
binds on line 7, with no translation layer and no debug adapter to write.

The only visible limit is a consequence of
[one-expression emission](emission-and-semantics.md): a breakpoint aimed
*inside* a multi-line `g{ ... }` binds on the island's first line, because the
graph is a single expression.

## Shadow files

`ldpy.build` also materialises, for each `.ldpy` module, a real `.py` file plus
its maps. Real files are what an unmodified `debugpy` runs, what an inspection
tool reads, and what makes "show me the generated code" a one-command
operation. The editor-side work then reduces to *translating positions* —
breakpoints in, stack frames out — through the language map.

## Request forwarding

The language server is thin. It transpiles on every change, publishes the
transpiler's own diagnostics, answers hover on islands and semantic tokens
natively — and **forwards everything else** (completion, definition,
references, hover on plain Python) to an unmodified Python language server
running as a subprocess, translating positions on the way in and URIs and
ranges on the way out. Backend diagnostics (pyflakes) are re-projected onto
`.ldpy` lines; those pointing at the synthetic prelude are dropped. With no
backend installed, the server degrades to its native layer instead of failing.

## Three implementation choices

**No pygls, no LSP framework.** The JSON-RPC framing is about 90 lines and is
used twice — once towards the editor, once towards the backend. During
development the framework's major version broke its API; the framing did not.

**The map, not the AST, is the interface.** `copy` segments give exact position
translation over roughly 95 % of a real file; island segments give
region-granular translation. That is enough for diagnostics, breakpoints,
semantic tokens and highlighting, with no coupling between the tools and the
transpiler's internals. The same maps are exported as standard Source Map v3
for tools of the JavaScript lineage.

**One specification, several consumers.** The disambiguation rules are stated
once and consumed three times: by the scanner, by the TextMate grammar of the
VS Code extension — itself *generated* from VS Code's own MagicPython, with
character-level parity on pure Python checked by a test — and by the
[Pygments lexer](../how-to/highlight-ldpy.md), which reads the language map
directly and so cannot drift at all.
