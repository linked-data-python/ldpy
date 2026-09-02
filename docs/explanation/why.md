# Why Linked-Data Python

## The problem

Turtle is a deliberately concise notation, and the shape of the text follows
the shape of the graph. Yet almost no application is written in Turtle:
applications are written in general-purpose languages, and there the notation
is lost. Every RDF library — rdflib in Python, the OWL API in Java, RDF/JS in
JavaScript — exposes RDF's *abstract* syntax as a hierarchy of objects and
constructor calls. A developer who wants to build the graph must translate it,
by hand, into a sequence of statements that no longer resembles it.

That translation is not merely verbose. It is where errors accumulate, and
where a reviewer loses the ability to check the data against the ontology.

Here is the same function twice. Seven triples, both times.

```ldpy
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#>.
@base <http://example.org/building/> .

def observation(sensor, value, timestamp):
    return g{ f<sensor/{sensor}> a sosa:Sensor ;
                  sosa:madeObservation
                      [ a sosa:Observation ;
                        sosa:resultTime {timestamp}^^xsd:dateTime ;
                        sosa:hasResult
                            [ qudt:numericValue {value} ;
                              qudt:unit qudt:DEG_C ] ] }

assert len(observation("s1", 21.5, "2026-08-28")) == 7
```

```python
from rdflib import Graph, BNode, Literal, Namespace, URIRef, RDF, XSD
SOSA = Namespace("http://www.w3.org/ns/sosa/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
BASE = "http://example.org/building/"

def observation(sensor, value, timestamp):
    g = Graph()
    s = URIRef(BASE + "sensor/" + str(sensor))
    obs, result = BNode(), BNode()
    g.add((s, RDF.type, SOSA.Sensor))
    g.add((s, SOSA.madeObservation, obs))
    g.add((obs, RDF.type, SOSA.Observation))
    g.add((obs, SOSA.resultTime, Literal(timestamp, datatype=XSD.dateTime)))
    g.add((obs, SOSA.hasResult, result))
    g.add((result, QUDT.numericValue, Literal(value)))
    g.add((result, QUDT.unit, QUDT.DEG_C))
    return g

assert len(observation("s1", 21.5, "2026-08-28")) == 7
```

In the first, the nesting of blank nodes is visible. In the second it has been
flattened into a sequence of `add` calls whose order no longer carries meaning.

## The position

The usual answer to this problem is to substitute a dedicated language for the
general-purpose one — and to discard the host ecosystem in the process. ldpy
takes the opposite position: rather than replace Python, it **extends** it. The
primitives of the Semantic Web become primitives of the language, and
everything else about Python — its libraries, its debuggers, its editors —
continues to apply.

Embedding a domain notation in a host language is not a new idea, and its
trade-offs are well documented. What is specific to this case is the cost of
*implementing* such an extension well enough to be usable. A syntactic
extension of a general-purpose language normally requires re-specifying that
language's grammar — a large and perpetual undertaking — and it normally breaks
the host's tooling, because the debugger and the language server no longer
recognise the files. Both obstacles shaped every decision that follows.

## The six requirements

They were set a priori. The
[corpus study](what-real-code-does.md) later confronted them with a
measurement of how real RDF code is actually written, which validated the most
debatable of them and drove a second wave of constructs.

### R1 — Notational parity with Turtle

An RDF term or graph should be written as it is written in Turtle: prefixed
names, the `a` shorthand, predicate-object lists, blank-node property lists,
collections. A developer who knows Turtle should not have to learn a second
notation for the same thing, and a graph copied from an ontology's
documentation should be usable with minimal edits.

### R2 — Interpolation of the host language

Static graphs are of limited use; the value of embedding RDF in a programming
language is that the data can depend on the program's state. Any Python
expression must be usable in term position, and **the boundary between the two
languages must be explicit in the syntax rather than inferred**.

The corpus study later measured this to be the normal case, not the exception:
[91 % of triples in real code have at least one computed term](what-real-code-does.md#interpolation-is-the-normal-regime).

### R3 — Host-language transparency

Every valid Python program must be a valid ldpy program with unchanged
meaning. This is a strong requirement: it forbids repurposing any syntax Python
already gives a meaning to, and it makes the extension safe to adopt
incrementally, one file at a time.

It is also a **testable property** — and it is tested, on the CPython standard
library, [byte for byte](how-it-is-tested.md#transparency).

### R4 — Reuse of the host ecosystem

The reason to extend a general-purpose language instead of designing a new one
is to keep its ecosystem, and that must extend to *tooling*: a developer must
be able to set a breakpoint, step through a function, get completion and see
diagnostics, without a bespoke debugger or a fork of an existing language
server. Errors must be reported at positions in the `.ldpy` source, not in
generated code nobody wrote. How that is achieved is
[the tooling architecture](tooling.md).

### R5 — Interactive-speed transpilation

Transpilation sits on the critical path twice: at import time, since modules
are transpiled when loaded, and at every keystroke, since a language server
re-transpiles the buffer to produce diagnostics. A transpiler that processes a
few hundred lines per second is usable in neither role. The target was set at
10 000 lines/s; the [island-parsing design](island-parsing.md) exceeds it by
five to ten times.

### R6 — Applicability to constrained devices

The original motivation for this line of work is manipulating RDF on
constrained devices, where MicroPython is a realistic runtime. The generated
code should stay within the subset of Python that MicroPython accepts, and the
transpiler itself should depend on nothing that could not run there. This
constrains [emission](emission-and-semantics.md) more than it constrains the
surface language — and it costs, as it turns out, nothing at all: ldpy works
with the newest Python, and a file that stays within the MicroPython subset
stays there after transpilation.

The runtime followed: the façade takes its terms and graphs from a backend
that is rdflib on the host and [urdflib](https://github.com/linked-data-python/urdflib)
on MicroPython, and the same programme — `+{ }`, `m{ }`, `e{ }` and
`serialize()` — transpiled on the host gives the host's answer on a
MicroPython built with urdflib. What R6 costs, and the one construct it
refuses, is [running on a device](running-on-a-device.md).

## Where to read on

- [What real RDF code does](what-real-code-does.md) — the measurement, and the
  second wave of constructs it drove.
- [Designing the syntax](designing-the-syntax.md) — how each form was chosen,
  and what was refused.
- [Why island parsing](island-parsing.md) — the implementation strategy that
  makes R3 and R5 possible at once.
