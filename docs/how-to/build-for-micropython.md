# How to build a programme for MicroPython

The transpiler runs on your machine; the device runs the emitted Python with
the ldpy runtime and [urdflib](https://github.com/linked-data-python/urdflib),
the RDF backend for MicroPython. This guide gives the commands; the reasoning
is in [running on a device](../explanation/running-on-a-device.md).

## Build with the device target

```text
python -m ldpy.build program.ldpy -o build --target micropython
```

This does two things a plain build does not:

- it **refuses `s{ }`** at build time — a SPARQL query needs rdflib's engine,
  which the device does not have — and tells you to write the pattern with
  `m{ }` and the filter with `e{ }`;
- it **copies the device runtime** into `build/ldpy/`: `runtime.py`,
  `backend.py`, `sparql.py` and a minimal `__init__.py`. That is everything
  `import ldpy.runtime as _ldpy_` needs, and nothing else.

A whole tree builds the same way: `python -m ldpy.build src/ -o build
--target micropython`. `ldpy -t --target micropython program.ldpy` prints the
emitted Python instead of writing it.

## Run on the Unix port, before touching hardware

A MicroPython built with urdflib is the same programme on a laptop and on a
board. `urdflib/build_unix.sh` builds one:

```text
git clone https://github.com/linked-data-python/urdflib.git
cd urdflib && ./build_unix.sh          # MicroPython v1.21.0, mpy-cross, the Unix port
../micropython/ports/unix/build-standard/micropython tests/test_urdflib.py
```

Then run your build with the runtime on the module path:

```text
MICROPYPATH=build ../micropython/ports/unix/build-standard/micropython build/program.py
```

## Freeze into `.mpy`

`mpy-cross` turns the emitted `.py` into bytecode the device loads without
compiling:

```text
mpy-cross build/program.py             # -> build/program.mpy
mpy-cross build/ldpy/runtime.py        # the runtime freezes the same way
```

## Keep the seam between programme and device explicit

Everything a target provides differently — a sensor, a clock, a network —
belongs in one module the programme imports, with one implementation per
target. The demonstration in the `ldpy-micropython` repository does exactly
that with `demo/target.py` (host) and `demo/target_micropython.py` (device),
so that the `.ldpy` file is the same text everywhere.

## Check the same answer on both sides

`python program.ldpy` on the host and the device run should print the same
thing. The repository's own test does this comparison on a programme with
`+{ }`, `m{ }`, `e{ }` and `serialize()`; point `LDPY_MICROPYTHON` at a
MicroPython built with urdflib and it runs:

```text
LDPY_MICROPYTHON=../micropython/ports/unix/build-standard/micropython \
    python -m pytest tests/test_target_micropython.py
```

## What does not work on a device

- `s{ }` — refused at build time, as above;
- exact decimals in `e{ }` (`xsd:decimal` arithmetic falls back to floats:
  MicroPython has no `decimal` module);
- the import hook — modules are transpiled on the host, so `ldpy.install()`
  has no meaning there, and the device `ldpy/__init__.py` does not offer it.
