# Running on a device: the façade, the backend, and what SPARQL costs

The oldest requirement of this project — [R6](why.md#r6-applicability-to-constrained-devices),
manipulating RDF on constrained devices — was for a long time argued and not
shown. It is shown now: the same `.ldpy` programme, transpiled on a laptop,
runs on a MicroPython built with [urdflib](https://github.com/linked-data-python/urdflib)
and gives the laptop's answer. This page explains what made that possible,
and what it settles about the shape of the language.

## One façade, chosen underneath

The generated code never names an RDF library. Every island compiles to a call
on `_ldpy_`, the alias of `ldpy.runtime`, and that module takes its terms and
graphs from `ldpy.backend`. The backend is not something a programme chooses:
it is what the interpreter can import — rdflib on CPython, urdflib on a
device, where there is no `pip` and the backend *is* the firmware.

That makes the contract between the language and an RDF library **finite and
measurable**: it is the list of names `ldpy.backend` exports, twenty-two of
them. The `urdflib` repository carries an instrument, `tools/api_gap.py`, that
reads that list from the façade's own source and checks it against the
`MP_QSTR_` tables of the C module. When the port started, fifteen names were
missing; the one that mattered was `graph.triples((s, p, o))`, the general
accessor of which rdflib's six shortcuts are special cases, and the one
`m{ }` is built on.

## What the C backend does, and does not do

urdflib does not implement RDF: it binds [sord](https://github.com/drobilla/sord)
and [serd](https://github.com/drobilla/serd), a C store and a C syntax library,
in about a thousand lines. So a term compares and hashes like its string, as
rdflib's `str` subclasses do; a graph adds, removes, iterates, answers `in`
and `triples()` with wildcards, and serialises to Turtle — all at C speed.
What it leaves to Python is deliberately small: `Namespace`, `RDF` and `XSD`
objects, which the backend module provides in a dozen lines.

Two rules of MicroPython shape how the façade uses it. A Python subclass of a
C type keeps its methods, `len`, `in` and iteration, but an *operator* the
subclass does not define falls through to the C type and returns the C
object — so the façade's graph class defines its own `+=`. And `tuple` cannot
be subclassed with `__new__`, so the row of an `m{ }` is a small sequence of
its own on a device. Neither rule reaches the programme you write.

## SPARQL is two capabilities, not one

The tempting design was "SPARQL as an optional extra you leave out on a
device". The measurement says something more precise.

`e{ }` **expressions** are 550 lines of pure Python over the terms — datatype,
language, `toPython()` — with no parser. They run on both backends; a filter
such as `e{ ?v >= 1.5 }` gives the same answer on an ESP32 as on the laptop.

`s{ }` **queries** are rdflib's engine and its parser. Nothing on a device
answers them, and the C store has no engine. So the only constraint is an
implication — `s{ }` needs the rdflib backend — and the right place to state
it is not the device, at the first query, but the host, at build time:
`--target micropython` refuses an `s{ }` island with a message that names
`m{ }` and `e{ }` as what to write instead. Everything else compiles to the
same text it would on the host.

## The two deployment modes

The transpiler stays on the host. `ldpy.build --target micropython` emits the
Python and copies, next to it, exactly what a device needs at run time — the
façade, its backend and the expressions, and a minimal `ldpy/__init__.py`
that imports neither the transpiler nor the import hook. Freezing the emitted
Python into `.mpy` is then MicroPython's ordinary path.

Transpiling *on* the device is the other mode. The transpiler is 2 700 lines
of Python that use only `re` and strings, so it is not excluded; what it
costs in flash and in time on a microcontroller is an open measurement, and
the reason the first mode comes first.

## Where to read on

- [How to build for MicroPython](../how-to/build-for-micropython.md) — the
  commands.
- [Tutorial: run a programme on MicroPython](../tutorials/run-on-micropython.md)
  — from a `.ldpy` file to the device's answer, on the Unix port.
- [Emission and semantics](emission-and-semantics.md) — why the emitted code
  was already in the MicroPython subset.
