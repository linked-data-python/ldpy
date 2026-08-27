# Command-line reference

## `python -m ldpy`

```text
python -m ldpy [-s] [-t] [-i] [-m] [source]
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

## `python -m ldpy.build`

```text
python -m ldpy.build SOURCE [-o OUT]      # file or directory (default OUT: .ldpy-build)
```

For each `module.ldpy`: writes `module.py` (shadow), `module.ldpy.map`
(language map, JSON v1) and `module.py.map` (Source Map v3). Plain `.py`
files in a tree are copied so mixed packages stay importable.

## `python -m ldpy.debug`

```text
python -m ldpy.debug SOURCE [-o OUT] [--listen H:P] [--wait-for-client]
                     [--breakpoints L1,L2,...] [-- args...]
```

Builds the shadow then runs it — under debugpy when `--listen` is given.
`--breakpoints` prints the `.ldpy`→shadow line table (JSON) and exits.

## `python -m ldpy.lsp`

```text
python -m ldpy.lsp [--backend pylsp|none]
```

LSP server on stdio. See [the language server guide](../how-to/language-server.md).

## `python -m bench.run`

```text
python -m bench.run [--quick] [--out bench/results]
```

Reproducible throughput campaigns (island density, file size, graph size,
v1 comparison, transparency); writes `results.json` and CSV files.
