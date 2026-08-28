# Tutorial: first steps

In this tutorial you write and run your first `.ldpy` program: an RDF term, a
graph, a function that returns one, and a deferred expression. It assumes you
know some Python and have seen Turtle before. Twenty minutes.

When you are done, the [second tutorial](build-a-knowledge-graph.md) builds a
knowledge graph from tabular data and queries it.

## 1. Install

```text
git clone git@gitlab.emse.fr:maxime.lefrancois/linked-data-python.git
cd linked-data-python
pip install -e .            # rdflib comes with it; add [lsp,debug] for tooling
```

## 2. A first term

Linked-Data Python is Python plus RDF *islands*. Open the interactive console
with `ldpy` (or `python -m ldpy`) and type:

```ldpy
@prefix schema: <https://schema.org/> .
term = schema:Person
assert str(term) == "https://schema.org/Person"
```

`schema:Person` is not a syntax error: it is a *prefixed name*, and `term` now
holds an `rdflib.URIRef`. The declaration line is Turtle's own syntax, dot
included — and it holds until the end of the enclosing block.

Try the other terms while you are in the console:

```ldpy
@prefix schema: <https://schema.org/> .
iri = <http://example.org/alice>
name = "Alice"@en
age = "33"^^<http://www.w3.org/2001/XMLSchema#integer>
who = ?person
assert name.language == "en" and int(age) == 33
assert str(who) == "person"
```

## 3. Your first graph

Islands go all the way up to graphs, written in Turtle notation inside
`g{ ... }`:

```ldpy
@prefix schema: <https://schema.org/> .

alice_age = 33
g = g{ [] a schema:Person ;
          schema:name "Alice"@en ;
          schema:age {alice_age} }

assert len(g) == 3
```

Three things happened. `[]` created a fresh blank node. `"Alice"@en` is a
language-tagged literal. And `{alice_age}` **interpolated** a Python variable
into the graph — the braces switch back from Turtle to Python, exactly like an
f-string. The result is a plain `rdflib.Graph`; serialise it if you want to see
it:

```ldpy
@prefix schema: <https://schema.org/> .
g = g{ [] a schema:Person ; schema:name "Alice"@en }
turtle = g.serialize(format="turtle")
assert "schema:Person" in turtle or "Person" in turtle
```

## 4. Graphs are expressions

A graph literal is an ordinary Python expression: it can sit in a function, a
comprehension, a default argument — anywhere.

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
$ ldpy obs.ldpy
$ ldpy -s obs.ldpy          # ... and show the generated Python
```

Or import it from plain Python — modules transpile on import:

```text
>>> import ldpy; ldpy.install()
>>> import obs
>>> obs.observation("s1", 21.5).serialize(format="turtle")
```

If something goes wrong, the traceback points at `obs.ldpy`, at the line you
wrote. That is not a courtesy: it is
[mapped compilation](../explanation/tooling.md#mapped-compilation), and it is
why `pdb` and your IDE debugger work too.

## 6. One graph, and writing into it

Naming a graph once and adding to it is the shape most RDF code takes:

```ldpy
@prefix ex: <http://example.org/> .

@graph as g                          # create it, make it current
+{ ex:alice a ex:Person }            # add
for i in range(3):
    +{ ex:alice ex:score {i} }       # one triple per iteration
assert len(g) == 4
```

`+{ ... }` and `-{ ... }` are statements, allowed at the start of a line. They
write to the current graph — the one `@graph` declared.

## 7. Reading it back

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:alice a ex:Person ; ex:score 1, 2 . ex:bob a ex:Person }

people = sorted(str(s) for s in m{ ?s a ex:Person })
scores = sorted(int(v) for v in m{ ex:alice ex:score ?v })
assert people == ["http://example.org/alice", "http://example.org/bob"]
assert scores == [1, 2]
assert bool(m{ ex:bob a ex:Person })          # an ASK, lazily
```

`m{ ... }` is a graph pattern in the same Turtle notation, matched against the
current graph. With one variable it yields terms; with several it yields rows.

## 8. Deferred expressions

Everything so far evaluates immediately. `e{ ... }` builds a **deferred**
SPARQL expression instead, evaluated later against variable bindings — the tool
for filters over solution mappings:

```ldpy
adult = e{ ?age >= 18 && BOUND(?name) }
people = [{"age": 12}, {"age": 30, "name": "Ana"}]
grown = [p for p in people if adult.ebv(p)]
assert grown == [{"age": 30, "name": "Ana"}]
```

## Where to next

- Build something: [tutorial 2 — a knowledge graph from tabular data](build-a-knowledge-graph.md).
- Do something specific: the [how-to guides](../how-to/run-and-import.md).
- Look something up: the [language reference](../reference/language/index.md).
- Understand why it works this way: [the explanations](../explanation/why.md).
