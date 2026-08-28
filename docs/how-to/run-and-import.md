# How to run and import `.ldpy` code

## Run a file

```text
ldpy program.ldpy                      # transpile + execute
ldpy -s program.ldpy                   # also print the generated Python
ldpy -t program.ldpy                   # transpile only, to stdout
ldpy -i program.ldpy                   # then drop into the console
```

`ldpy` and `python -m ldpy` are the same command; the console script comes with
the package.

## Import `.ldpy` modules from Python

Install the import hook once, then import as usual — `mymod.ldpy` found on
`sys.path` is transpiled at import time:

```python
import ldpy
ldpy.install()
# import mymod   (any mymod.ldpy on sys.path)
```

Tracebacks need no translation: `.ldpy` code is compiled with the SOURCE
file name and line numbers (mapped compilation — see the design note
DESIGN_CHOICES/ldpy/011), so frames, `pdb` and `debugpy` speak `.ldpy`
coordinates natively. The hook still keeps the language maps for tooling:

```python
from ldpy.importer import MAPS, translate_lineno
```

(`ldpy.install_excepthook()` is kept as a no-op for compatibility.)

## Use the interactive console

`python -m ldpy` with no argument opens a console in which islands work,
multi-line graphs included; top-level `@prefix`/`@base` persist between
entries. Line editing, Tab completion and a persistent history
(`~/.ldpy_history`) are available. Ctrl-D exits.

## Transpile programmatically

```python
from ldpy.transpiler import transpile
result = transpile('@prefix ex: <http://e/> .\nx = ex:a\n', "mem.ldpy")
assert "URIRef" in result.code
assert result.prefixes == {"ex": "http://e/"}
```

See the [API reference](../reference/api.md) for `TranspileResult`.
