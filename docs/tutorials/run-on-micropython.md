# Tutorial: run a programme on MicroPython

In this tutorial you write a small SOSA/SSN programme, run it on your
machine, build it for a device, and run the *same* file on MicroPython — on
the Unix port, which needs no hardware — and check that both give the same
answer. Thirty minutes, from a clone to a device run.

It assumes the [first tutorial](getting-started.md) and a C compiler.

## 1. The programme

A sensor makes observations; each becomes a `sosa:Observation` with its
result and its time. Everything the device would do differently — read the
sensor, read the clock — is behind two small functions, so that the file
stays the same on every target.

```ldpy
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix ex:   <http://example.org/device/> .

def read_temperature():
    return 21.5                      # the device: the real sensor

def now_iso():
    return "2026-09-02T10:00:00"     # the device: the RTC

@graph as g
+{ ex:thermometer a sosa:Sensor ; sosa:observes ex:AirTemperature }
for i in range(3):
    +{ f<http://example.org/device/obs/{i}> a sosa:Observation ;
           sosa:madeBySensor ex:thermometer ;
           sosa:resultTime {now_iso()}^^xsd:dateTime ;
           sosa:hasSimpleResult {read_temperature() + i}^^xsd:double }

warm = e{ ?t > 22 }
hot = sorted(str(s) for s, t in m{ ?s sosa:hasSimpleResult ?t } if warm({"t": t}))
assert len(g) == 2 + 3 * 4
assert hot == ["http://example.org/device/obs/1", "http://example.org/device/obs/2"]
```

Save it as `sensor.ldpy` and run it: `ldpy sensor.ldpy`. Silence means the
two assertions held.

## 2. Build it for the device

```text
python -m ldpy.build sensor.ldpy -o build --target micropython
```

Look at what appeared:

```text
build/sensor.py          the emitted Python — the same text a plain build emits
build/ldpy/__init__.py   a docstring: the transpiler is not shipped
build/ldpy/runtime.py    the façade the emitted code calls
build/ldpy/backend.py    rdflib on your machine, urdflib on the device
build/ldpy/sparql.py     the e{ } expressions, pure Python
```

Now add one line to `sensor.ldpy` — `q = s{ SELECT ?s WHERE { ?s ?p ?o } }` —
and build again. The build stops on that line and says why: a SPARQL query
needs rdflib's engine, and the device has none. Remove the line. The message
is the whole point of the target: the device never sees a programme it cannot
run.

## 3. A MicroPython that speaks RDF

MicroPython does not ship an RDF library; urdflib is one, as a C module. Its
repository builds the Unix port with it in one command:

```text
git clone https://github.com/linked-data-python/urdflib.git
cd urdflib && ./build_unix.sh
```

Five minutes later `../micropython/ports/unix/build-standard/micropython`
exists. Its contract test tells you it is the right one:

```text
../micropython/ports/unix/build-standard/micropython tests/test_urdflib.py
```

## 4. Run the same programme there

```text
MICROPYPATH=build ../micropython/ports/unix/build-standard/micropython build/sensor.py
```

Silence again: the same two assertions, held by a different RDF library, in a
different Python. Make the programme talk to see it happen — add
`print(g.serialize(format="turtle"))` at the end, rebuild, and run on both
sides. The prefixes, the triples and the language tags are the same; only the
line breaks differ, because serd and rdflib do not indent alike.

## 5. What you just did

- The `.ldpy` file was transpiled **once, on the host**; the device ran plain
  Python.
- `+{ }`, `m{ }` and `e{ }` ran on urdflib — the C store answered the pattern,
  the expression evaluated in Python over its terms.
- The one construct that cannot run there, `s{ }`, was refused **before**
  anything was shipped.

On a real board the steps are the same, with `mpy-cross` to freeze the files
and the board's own `target` module for the sensor and the clock — the
[how-to guide](../how-to/build-for-micropython.md) has the commands, and
[running on a device](../explanation/running-on-a-device.md) has the reasons.
