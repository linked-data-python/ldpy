# Tutorial: getting started with Linked-Data Python

In this tutorial you will write and run your first `.ldpy` program, build an
RDF graph in Turtle notation inside Python, and use it from ordinary Python
code. It assumes you know some Python and have seen RDF/Turtle before.

## 1. Install

```text
pip install rdflib          # the default runtime backend
git clone git@gitlab.emse.fr:maxime.lefrancois/linked-data-python.git
cd linked-data-python
```

(Until the 0.1.0 PyPI release, run from the repository with `PYTHONPATH=.`)

## 2. A first expression

Linked-Data Python is Python plus RDF *islands*. Open the interactive console
with `python -m ldpy`, and type:

```ldpy
@prefix schema: <https://schema.org/> .
term = schema:Person
```

`schema:Person` is not a syntax error: it is a *prefixed name*, and `term` now
holds the IRI `https://schema.org/Person` as an `rdflib.URIRef`. The
declaration line is Turtle's own syntax, ending with a dot.

## 3. Your first graph

Islands go up to full RDF graphs, written in Turtle notation inside `g{ ... }`:

```ldpy
@prefix schema: <https://schema.org/> .

alice_age = 33
g = g{ [] a schema:Person ;
          schema:name "Alice"@en ;
          schema:age {alice_age} }

assert len(g) == 3
```

Three things happened here. `[]` created a fresh blank node. `"Alice"@en` is a
language-tagged literal. And `{alice_age}` *interpolated* a Python variable
into the graph — the braces switch back from Turtle to Python, exactly like an
f-string. The result `g` is a plain `rdflib.Graph`.

## 4. Graphs are expressions

A graph literal is an ordinary Python expression: it can sit in a function,
a comprehension, a default argument — anywhere.

```ldpy
@prefix sosa: <http://www.w3.org/ns/sosa/> .

def observation(sensor_id, value):
    return g{ f<http://example.org/sensor/{sensor_id}> a sosa:Sensor ;
                  sosa:madeObservation [ sosa:hasSimpleResult {value} ] }

graphs = [observation(i, 20 + i) for i in range(3)]
assert [len(x) for x in graphs] == [3, 3, 3]
```

`f<...>` is a *formatted IRI* — the counterpart of Python's f-string for IRIs.
Each call produces fresh blank nodes, like re-parsing a Turtle document.

## 5. Save and run a file

Put the previous snippet in `obs.ldpy` and run it:

```text
$ python -m ldpy obs.ldpy
```

Or import it from plain Python — modules transpile on import:

```text
>>> import ldpy; ldpy.install()
>>> import obs
>>> obs.observation("s1", 21.5).serialize(format="turtle")
```

## Where to next

- Doing something specific: the [how-to guides](../how-to/run-and-import.md).
- The complete island syntax: [language reference](../reference/language.md).
- Why it works this way: [explanations](../explanation/island-parsing.md).
