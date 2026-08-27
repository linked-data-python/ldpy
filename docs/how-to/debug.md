# How to debug a `.ldpy` program

Since the mapped compilation (DESIGN_CHOICES/ldpy/011), `.ldpy` code objects
carry the source file name and SOURCE line numbers: tracebacks, `pdb` and
`debugpy` work on the `.ldpy` file directly. The *shadow* mode (a real
generated `.py` on disk) remains for tooling and inspection.

## Direct mode (recommended)

```text
python -m ldpy.debug --run program.ldpy [-- args]   # run, .ldpy coordinates
python -m pdb -m ldpy.debug --run program.ldpy      # break program.ldpy:7 works
python -m debugpy --listen 127.0.0.1:5678 --wait-for-client \
       -m ldpy.debug --run program.ldpy
```

Breakpoints are set on `.ldpy` lines; a breakpoint aimed *inside* a
multi-line `g{ ... }` island only binds on the island's first line (the
graph is one expression). This is what the VS Code extension launches on F5.

## Shadow mode

```text
python -m ldpy.debug program.ldpy                       # build + run shadow
python -m ldpy.debug program.ldpy --listen 127.0.0.1:5678 --wait-for-client
```

Then attach any DAP client (VS Code "attach", PyCharm, ...) to the port.
Arguments after `--` go to the program.

## Translate breakpoints

Editors set breakpoints in the `.ldpy` file; the shadow needs them at the
generated lines. `--breakpoints` prints the translation table and exits:

```text
$ python -m ldpy.debug program.ldpy --breakpoints 2,5
{"shadow": ".ldpy-build/program.py", "map": "...", "breakpoints": {"2": 3, "5": 5}}
```

Programmatically:

```python
from ldpy.transpiler import transpile
from ldpy.debug import translate_breakpoints, translate_frames
r = transpile("@prefix ex: <http://e/> .\nx = ex:a\ny = 1\n", "m.ldpy")
assert translate_breakpoints(r.map, [3]) == [4]   # +1: the runtime prelude
assert translate_frames(r.map, [4]) == [3]        # and back, for stack frames
```

A breakpoint aimed *inside* a multi-line `g{ ... }` snaps to the line of the
generated graph expression. Frames pointing at the synthetic prelude
translate to `None`.

## In VS Code

Press **F5** (debug type « Linked-Data Python ») : the extension starts a
debugpy session on `python -m ldpy.debug --run` — breakpoints set in the
`.ldpy` bind directly, no translation involved.
