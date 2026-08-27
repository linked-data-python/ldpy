# How to debug a `.ldpy` program

Debugging works on the *shadow* Python files that `ldpy.build` materialises:
they are real files on disk, so any Python debugger runs on them unchanged.
The language map translates positions between the two.

## From the command line

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

Use **ldpy: Debug current file (shadow)** — it does the above for you.
