# How to run and import `.ldpy` code

## Run a file

```text
python -m ldpy program.ldpy            # transpile + execute
python -m ldpy -s program.ldpy         # also print the generated Python
python -m ldpy -t program.ldpy         # transpile only, to stdout
python -m ldpy -i program.ldpy         # then drop into the console
```

## Import `.ldpy` modules from Python

Install the import hook once, then import as usual — `mymod.ldpy` found on
`sys.path` is transpiled at import time:

```python
import ldpy
ldpy.install()
# import mymod   (any mymod.ldpy on sys.path)
```

To translate a traceback line number back to the `.ldpy` source, the hook
keeps the language maps:

```python
from ldpy.importer import MAPS, translate_lineno, install_excepthook
```

`install_excepthook()` rewrites `.ldpy` frames automatically.

## Use the interactive console

`python -m ldpy` with no argument opens a console in which islands work,
multi-line graphs included; top-level `@prefix`/`@base` persist between
entries. Ctrl-D exits.

## Transpile programmatically

```python
from ldpy.transpiler import transpile
result = transpile('@prefix ex: <http://e/> .\nx = ex:a\n', "mem.ldpy")
assert "URIRef" in result.code
assert result.prefixes == {"ex": "http://e/"}
```

See the [API reference](../reference/api.md) for `TranspileResult`.
