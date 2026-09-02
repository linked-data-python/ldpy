# Command-line reference

Every entry point exists twice: as a console script installed with the package
(`ldpy`, `ldpy-build`, `ldpy-debug`, `ldpy-lsp`) and as `python -m …`. They are
the same programs; the module form is spelled out below because it works
without the scripts being on `PATH`.

## `python -m ldpy` — run, transpile, or open a console

```text
python -m ldpy [-s] [-t] [-i] [-m] [--target micropython] [source]
```

| Flag | Effect |
|---|---|
| *(none, no source)* | interactive console |
| `source` | transpile and execute the file |
| `-s, --show-changes` | print the generated Python before executing |
| `-t, --transpile-only` | write the generated Python to stdout and stop |
| `-i, --interactive` | open the console after the script, with its globals and prefixes |
| `-m, --map` | also write `<source>.map` (language map JSON) |
| `-v, --version` | print the version |
| `--target micropython` | build for a device: `s{ }` is refused here, at build time — see [build for MicroPython](../how-to/build-for-micropython.md) |

## `python -m ldpy.build` — shadow files and maps

```text
python -m ldpy.build SOURCE [-o OUT] [--target micropython]   # file or directory (default OUT: .ldpy-build)
```

For each `module.ldpy`: writes `module.py` (shadow), `module.ldpy.map`
(language map, JSON v1) and `module.py.map` (Source Map v3). Plain `.py`
files in a tree are copied so mixed packages stay importable.

`--target micropython` refuses `s{ }` and copies the device runtime
(`runtime.py`, `backend.py`, `sparql.py`, a minimal `__init__.py`) into
`OUT/ldpy/`, so that the emitted files and what they import travel together.

## `python -m ldpy.debug` — run under a debugger

```text
python -m ldpy.debug --run SOURCE [-- args...]
python -m ldpy.debug SOURCE [-o OUT] [--root DIR] [--listen H:P]
                     [--wait-for-client] [--breakpoints L1,L2,...]
                     [-- args...]
```

`--root DIR` says the shadow mirrors the tree under DIR: the `.py` goes to
`OUT/<path of SOURCE relative to DIR>` instead of `OUT/<basename>`, which is
what lets one build directory hold a whole workspace without `a/m.ldpy` and
`b/m.ldpy` claiming the same `m.py`.

`--run` executes SOURCE in-process, compiled in `.ldpy` coordinates
(mapped compilation, fiche 011) — under pdb/debugpy, breakpoints bind on
the `.ldpy` lines directly. Without `--run`: builds the shadow then runs
it — under debugpy when `--listen` is given. `--breakpoints` prints the
`.ldpy`→shadow line table (JSON) and exits.

## `python -m ldpy.lsp` — the language server

```text
python -m ldpy.lsp [--backend pylsp|none]
```

LSP server on stdio. See [the language server guide](../how-to/language-server.md).

## `pygmentize -l ldpy` — highlight

The package registers a Pygments lexer, so any Pygments consumer can colour
`.ldpy` once it is installed:

```text
pygmentize -l ldpy program.ldpy
pygmentize -l ldpy -f html -O full -o out.html program.ldpy
```

See [how to highlight ldpy code](../how-to/highlight-ldpy.md).

## `python -m bench.run` — throughput campaigns

```text
python -m bench.run [--quick] [--out bench/results]
```

Reproducible throughput campaigns (island density, file size, graph size,
v1 comparison, transparency); writes `results.json` and CSV files.
