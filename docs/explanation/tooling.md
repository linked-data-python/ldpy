# Tooling architecture: reuse, do not reimplement

The requirement behind the tooling is economic: a language that needs its own
debugger and its own IDE analysis engine will not be maintained. ldpy instead
reuses Python's tooling through two mechanisms.

**Shadow files.** `ldpy.build` materialises, for each `.ldpy` module, a real
`.py` file plus its maps. Real files mean `debugpy` runs on them unchanged —
no debug adapter to write. The editor-side work reduces to *translating
positions* (breakpoints in, stack frames out) through the language map.

**Request forwarding.** The language server is thin: it transpiles on every
change, publishes the transpiler's own diagnostics, answers hover on islands
and semantic tokens natively — and forwards everything else (completion,
definition, references, hover on plain Python) to an unmodified Python
language server running as a subprocess, translating positions on the way in
and URIs/ranges on the way out. Backend diagnostics (pyflakes) are
re-projected onto `.ldpy` lines; those pointing at the synthetic prelude are
dropped. Without a backend, the server degrades to its native layer.

Two deliberate implementation choices:

- **No pygls, no LSP framework**: the JSON-RPC framing is ~90 lines and is
  used twice (editor side, backend side). During development the framework's
  major version broke its API; the framing did not.
- **The map, not the AST, is the interface**: `copy` segments give exact
  translation on ~95% of a real file, island segments give region-granular
  translation — enough for diagnostics, breakpoints and tokens, with no
  coupling between the tools and the transpiler internals.

The same maps are exported as standard Source Map v3 for tools of the
JavaScript lineage.
