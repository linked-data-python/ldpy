# How to set up Visual Studio Code

The `vscode-ldpy` extension provides syntax highlighting (TextMate + LSP
semantic tokens), diagnostics as you type, completion/hover/definition
through the language server, and run/debug commands.

## Install

1. Install the extension (from the marketplace, or from source:
   `npm install && npx tsc -p .` in `vscode-ldpy`, then F5 / `vsce package`).
2. Make sure the Python that VS Code uses has ldpy available, plus the
   optional backends: `pip install python-lsp-server pyflakes debugpy`.
3. The interpreter is taken from `ldpy.pythonPath` if you set it, otherwise
   from the Python extension's active interpreter, otherwise `python3`.

## Settings

| Setting | Default | Effect |
|---|---|---|
| `ldpy.pythonPath` | *(unset)* | interpreter carrying ldpy, the LSP, debugpy |
| `ldpy.backend` | `pylsp` | Python language server for delegation, or `none` |
| `ldpy.buildDirectory` | `.ldpy-build` | where shadow `.py` files are built |

## Highlighting

Pure Python receives exactly the same TextMate scopes as in a `.py` file
(the grammar is generated from VS Code's own MagicPython — `npm test`
checks character-level parity); RDF islands get `.ldpy` scopes, refined by
the language server's semantic tokens.

## Debugging (F5)

`.ldpy` is a first-class debug type: press F5 (or pick **Linked-Data
Python** in the debugger list, or use the `ldpy : fichier courant`
configuration). The session runs `python -m ldpy.debug --run` under
debugpy; the program is compiled with the source file name and SOURCE line
numbers, so breakpoints set in the `.ldpy` bind directly and the debugger
steps through your `.ldpy` file. Requires the Python Debugger extension
(`ms-python.debugpy`).

## Commands (palette, on a `.ldpy` file)

- **ldpy: Run current file** — runs `python -m ldpy` in the integrated terminal.
- **ldpy: Debug current file** — same as F5.
- **ldpy: Show transpiled Python (shadow)** — opens the generated code
  side by side.
- **ldpy: Restart language server**.
