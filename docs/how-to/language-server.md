# How to use the language server

The server speaks LSP over stdio and has no dependency; the Python-delegation
backend is optional.

```text
python -m ldpy.lsp                     # with pylsp delegation if installed
python -m ldpy.lsp --backend none      # native layer only
```

## What is native and what is delegated

| Capability | Source |
|---|---|
| Diagnostics: ldpy syntax errors, prefix-scope warnings | native (the transpiler) |
| Diagnostics: Python errors (pyflakes...) | backend, re-projected onto `.ldpy` lines |
| Hover on an island | native (see [below](#the-hover-panel)) |
| Hover elsewhere, completion, definition, references, signature help | backend, positions translated both ways |
| Semantic tokens for islands | native |

The delegation backend is `python -m pylsp` in a subprocess: install it with
`pip install python-lsp-server pyflakes`. Without it, the server degrades to
the native layer and answers delegated requests with `null`.

## The hover panel

Hovering inside an island answers on the **smallest element** the server can
name — hovering `sosa:Platform` inside a forty-line `g{ }` explains that
prefixed name, not the whole block. The notation itself, a `[ ... ]`, and a
`{python}` hole fall back to the island; a `{python}` hole is Python, so a
hover *on the expression inside it* is the backend's answer as usual.

Three blocks come back, separated by rules:

1. a signature line — `(term) ex:local -> URIRef`, `(expression) g{ ... } ->
   Graph`;
2. what that kind of island does, in a couple of sentences, with a link into
   this documentation;
3. the Python it was translated to, formatted by `black` when it is
   installed.

`black` is only asked for a fragment, and a fragment is not always a module:
the head of a `for @bindings in` is not one. When it refuses, the generated
text is shown as it stands. And because `black` normalises what it accepts —
quotes above all — the third block is the translation *formatted*, not a
byte-for-byte extract. Use `ldpy -t` to read the generated file itself.

### Turning the translation off

Send `hover.showTranslation: false`, either in `initializationOptions` at
startup or in a `workspace/didChangeConfiguration` notification at any time;
under `settings`, both `{"ldpy": {"hover": ...}}` and `{"hover": ...}` are
understood. The signature and the description stay: they are what says what
you are looking at. In VS Code the setting is
**`ldpy.hover.showTranslation`**.

## Wiring another editor

Any LSP client works: launch command `python -m ldpy.lsp`, language id
`ldpy`, file pattern `*.ldpy`, full text synchronisation. The server never
writes shadow files for the LSP (documents live in memory under
`<uri>.shadow.py` on the backend side).
