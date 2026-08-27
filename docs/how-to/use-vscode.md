# How to set up Visual Studio Code

The `vscode-ldpy` extension provides syntax highlighting (TextMate + LSP
semantic tokens), diagnostics as you type, completion/hover/definition
through the language server, and run/debug commands.

## Install

1. Install the extension (from the marketplace, or from source:
   `npm install && npx tsc -p .` in `vscode-ldpy`, then F5 / `vsce package`).
2. Make sure the Python that VS Code uses has ldpy available, plus the
   optional backends: `pip install python-lsp-server pyflakes debugpy`.
3. Set `ldpy.pythonPath` in the settings if it is not `python3`.

## Settings

| Setting | Default | Effect |
|---|---|---|
| `ldpy.pythonPath` | `python3` | interpreter carrying ldpy, the LSP, debugpy |
| `ldpy.backend` | `pylsp` | Python language server for delegation, or `none` |
| `ldpy.buildDirectory` | `.ldpy-build` | where shadow `.py` files are built |

## Commands (palette, on a `.ldpy` file)

- **ldpy: Run current file** — runs `python -m ldpy` in the integrated terminal.
- **ldpy: Debug current file (shadow)** — builds the Python shadow, re-poses
  your `.ldpy` breakpoints on it at translated lines, starts a standard
  Python debug session (requires the Python extension).
- **ldpy: Show transpiled Python (shadow)** — opens the generated code
  side by side.
- **ldpy: Restart language server**.
