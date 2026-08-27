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
| Hover on an island | native (shows the generated expression) |
| Hover elsewhere, completion, definition, references, signature help | backend, positions translated both ways |
| Semantic tokens for islands | native |

The delegation backend is `python -m pylsp` in a subprocess: install it with
`pip install python-lsp-server pyflakes`. Without it, the server degrades to
the native layer and answers delegated requests with `null`.

## Wiring another editor

Any LSP client works: launch command `python -m ldpy.lsp`, language id
`ldpy`, file pattern `*.ldpy`, full text synchronisation. The server never
writes shadow files for the LSP (documents live in memory under
`<uri>.shadow.py` on the backend side).
