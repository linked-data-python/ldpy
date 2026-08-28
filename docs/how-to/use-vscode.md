# How to set up Visual Studio Code

The `vscode-ldpy` extension provides syntax highlighting (TextMate + LSP
semantic tokens), diagnostics as you type, completion/hover/definition
through the language server, and run/debug commands.

## Install

1. Install the extension (from the marketplace, or from source:
   `npm ci && npm run compile` in `vscode-ldpy`, then F5 / `npm run package`).
2. Give the Python that VS Code uses everything the editor needs:

   ```text
   pip install "linked-data-python[lsp,debug,format]"
   ```

3. The interpreter is taken from `ldpy.pythonPath` if you set it, otherwise
   from the Python extension's active interpreter, otherwise `python3`
   (`python` on Windows). **The status bar shows which one was found and
   which version of the package it carries** — click it to change.

## Settings

| Setting | Default | Effect |
|---|---|---|
| `ldpy.pythonPath` | *(empty)* | interpreter carrying ldpy, the LSP, debugpy, black |
| `ldpy.backend` | `pylsp` | Python language server for delegation, or `none` |
| `ldpy.buildDirectory` | `.ldpy-build` | where shadow `.py` files are built |
| `ldpy.lineLength` | `88` | line length used by the formatter |
| `ldpy.trace.server` | `off` | log the LSP traffic, for bug reports |

Changing the first three restarts the language server.

## Highlighting

Pure Python receives exactly the same TextMate scopes as in a `.py` file
(the grammar is generated from VS Code's own MagicPython — `npm test`
checks character-level parity); RDF islands get `.ldpy` scopes, refined by
the language server's semantic tokens.

## Formatting

The server provides `textDocument/formatting`, so **Format Document**
(Shift+Alt+F) and format-on-save work with no extra setup — see
[how to format](format.md).

```json
{ "[ldpy]": { "editor.formatOnSave": true } }
```

## Debugging (F5)

`.ldpy` is a first-class debug type: press F5 (or pick **Linked-Data
Python** in the debugger list). The session runs `python -m ldpy.debug --run`
under debugpy; the program is compiled with the source file name and SOURCE
line numbers, so breakpoints set in the `.ldpy` bind directly and the debugger
steps through your `.ldpy` file. Requires the Python Debugger extension
(`ms-python.debugpy`).

Stepping obeys the invariant described in [how to debug](debug.md): the
launcher never shows in the call stack, and a breakpoint dropped inside a
multi-line island is **moved** to the island's first line rather than left
armed and silent.

## Commands and keys

Everything is under the **ldpy** category in the palette; Run, Debug and Show
Transpiled Python are also in the ▷ button and the icons of the editor title
bar, and in the right-click menu.

| Command | |
|---|---|
| Run File | `python -m ldpy` in the integrated terminal |
| Debug File | same as F5 |
| Show Transpiled Python | the generated code, side by side |
| Format All .ldpy Files in Workspace | what Format Document cannot do |
| Restart Language Server | after changing the Python package |
| Show Language Server Log | attach this to a bug report |
| Select Python Interpreter · Open Documentation | |

The extension **binds no keys of its own** — F5 debugs, Ctrl+F5 runs and
Shift+Alt+F formats, all of them for free. Add your own, scoped to the
language:

```json
{ "key": "ctrl+alt+t", "command": "ldpy.showTranspiled",
  "when": "editorLangId == ldpy" }
```
