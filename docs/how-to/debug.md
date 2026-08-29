# How to debug a `.ldpy` program

Since the mapped compilation (ldpy/011), `.ldpy` code objects
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

Breakpoints are set on `.ldpy` lines. This is what the VS Code extension
launches on F5.

## What stepping guarantees

One invariant governs every debugging gesture, and it is
[measured, not asserted](../explanation/how-it-is-tested.md): **every stop
selects a region of the `.ldpy` file, and every gesture changes it.** No stop
lands on generated code with no source counterpart; no click leaves the
highlight where it was.

Two things would break it, and both are switched off by default:

| | what it is | when you see it |
|---|---|---|
| the launcher | the frames of `ldpy/debug.py` that start your program | never — it is plumbing, hidden in both modes |
| the runtime | `ldpy/runtime.py`, where `g{ ... }` actually builds the graph | only with `"justMyCode": false` |

So `step in` on a line whose only call is an island behaves like `step over`,
and stepping past the last line of your program **ends it** instead of
revealing the launcher. Set `"justMyCode": false` in the launch configuration
when you do want to walk into the runtime; the launcher stays hidden even
then. The rules are computed by the package itself:

```text
$ python -m ldpy.debug --probe
{"package": "/…/ldpy", "version": "…", "rules": {"justMyCode": […], "all": […]}}
```

Any DAP client can use them — pass them as `rules` in the `launch`/`attach`
request. The VS Code extension does exactly that. (The `PYDEVD_FILTERS`
environment variable looks like it would work and does not: the DAP request
overwrites it.)

## Breakpoints inside a multi-line island

A multi-line `g{ ... }` is **one** expression, whose code carries the line
where the island *starts*: no interior line is executable. A breakpoint
placed there can never fire — and debugpy reports it as verified anyway, so
the dot looks armed and stays silent.

The VS Code extension therefore **moves the dot**, as soon as you place it, to
the island's first line. Outside VS Code, do the same translation yourself:

```python
from ldpy.transpiler import transpile
from ldpy.transpiler.linemap import snap_breakpoint_lines
r = transpile("@prefix ex: <http://e/> .\ng = g{ ex:s ex:p 1 ;\n       ex:q 2 }\n", "m.ldpy")
assert snap_breakpoint_lines(r.map, [2, 3]) == [2, 2]   # line 3 is interior
```

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

Frames pointing at the synthetic prelude translate to `None`.

## In VS Code

Press **F5** (debug type "Linked-Data Python"): the extension starts a debugpy
session on `python -m ldpy.debug --run` — breakpoints set in the `.ldpy` bind
directly, no translation involved — with the stepping rules above applied and
unplaceable breakpoints moved.

Debugging goes through the **direct mode only**. The shadow is an inspection
tool ("ldpy: Show transpiled Python"), not a debugging target: you would be
stepping through a generated file instead of the one you wrote.
