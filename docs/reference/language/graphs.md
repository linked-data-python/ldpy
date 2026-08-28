# Graphs — `g{ ... }`

`g{ ... }` is an RDF graph written in Turtle's notation, as a Python
**expression**. It evaluates to a fresh `rdflib.Graph` every time it is
evaluated — like re-parsing a Turtle document.

```ldpy
@prefix ex: <http://example.org/ns#> .
from rdflib import Graph
g = g{ ex:s a ex:C ; ex:p 1, "x" }
assert isinstance(g, Graph) and len(g) == 3
```

Being an expression is the point: a graph may sit in a `return`, a
comprehension, a default argument, a lambda — anywhere a value may.

```ldpy
@prefix sosa: <http://www.w3.org/ns/sosa/> .

def observation(sensor, value):
    return g{ f<http://example.org/sensor/{sensor}> a sosa:Sensor ;
                  sosa:madeObservation [ sosa:hasSimpleResult {value} ] }

graphs = [observation(i, 20 + i) for i in range(3)]
assert [len(x) for x in graphs] == [3, 3, 3]
```

The alternative — hoisting graph construction into statements before the
current one — was rejected, and the three reasons are worth knowing before you
rely on evaluation order: see
[emission and semantics](../../explanation/emission-and-semantics.md).

## Turtle inside the braces

Everything Turtle offers in a triples block works, with Turtle's meaning:

| Notation | Meaning |
|---|---|
| `a` | `rdf:type` |
| `;` | repeat the subject |
| `,` | repeat the subject and predicate |
| `.` | end the statement, start a new subject |
| `[ ... ]` | blank node with a property list |
| `( ... )` | RDF collection (`rdf:first`/`rdf:rest`) |
| `_:label` | labelled blank node, scoped to the island |
| `#` to end of line | comment |

```ldpy
@prefix ex: <http://example.org/ns#> .
g = g{ ex:a a ex:C ;                       # subject repeated by ';'
           ex:p 1, 2 ;                     # predicate repeated by ','
           ex:child [ ex:name "leaf" ] ;   # nested blank node
           ex:items ( 1 "two" ) .          # a collection
       ex:b ex:p 3 }
assert len(g) == 11
```

A prologue is not written inside the island: `@prefix` and `@base` are
[declarations of the enclosing block](declarations.md), shared by every island
in scope.

## Interpolation — `{expr}`

In any term position, braces switch back to Python. This is not a convenience
feature but the normal regime: in real RDF code
[91 % of triples have at least one computed term](../../explanation/what-real-code-does.md#interpolation-is-the-normal-regime).

```ldpy
@prefix ex: <http://example.org/ns#> .
sensor, value, tags = "s1", 21.5, ["hot", "outdoor"]
g = g{ ex:{sensor} ex:value {value} ;
           ex:tag {tags[0]}, {tags[1]} ;
           ex:label {"sensor " + sensor} }
assert len(g) == 4
```

An interpolation may carry a **glued RDF suffix**, which is how a computed
value becomes a tagged or typed literal:

```ldpy
@prefix ex:  <http://example.org/ns#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
name, age, dt = "Ana", "30", xsd:integer
g = g{ ex:p ex:name {name}@en ;
              ex:age {age}^^xsd:integer ;
              ex:other {age}^^{dt} }        # datatype computed too
ages = sorted(str(o.datatype or "") for s, p, o in g)
assert ages.count(str(xsd:integer)) == 2
```

`{expr}^^{dt}` covers the generic case, where the datatype is decided at run
time. Because a datatype is an IRI by definition, a `str` in that position is
read as an IRI, never as a literal — the one place where the
[coercion policy](coercion.md) does not apply.

### Each occurrence evaluates once

The subject of a predicate-object list appears in several triples. If it is an
interpolation, it is evaluated **once**, at its first occurrence, and reused:

```ldpy
@prefix ex: <http://example.org/ns#> .
calls = []
def next_id():
    calls.append(1)
    return "id%d" % len(calls)
g = g{ ex:{next_id()} ex:p 1 ; ex:q 2 ; ex:r 3 }
assert len(calls) == 1 and len(g) == 3      # one subject, not three
```

Identity is per *source occurrence*: two textually identical interpolations
written in two places are two expressions and evaluate twice.

## Blank nodes

A syntactic `[ ]`, a collection cell or a `_:label` denotes a blank node that
is **fresh at every evaluation** of the island. Labels are shared within one
`g{ ... }` and nowhere else.

```ldpy
@prefix ex: <http://example.org/ns#> .
def make():
    return g{ _:x ex:p 1 ; ex:q _:x }       # same node twice, inside
a, b = make(), make()
subjects = {s for s, p, o in a} | {s for s, p, o in b}
assert len(subjects) == 2                   # but a fresh one per evaluation
```

### Data-keyed blank nodes — `_:{expr}`

`_:{expr}` denotes a blank node whose identity **derives from the value**:
equal values give the same node, across graphs and across sources. This is the
deduplication/join idiom of R2RML, available without a mapping engine.

```ldpy
@prefix ex: <http://example.org/ns#> .
rows = [("Ana", "Lu", "green"), ("Ana", "Lu", "blue")]
g = g{ }
for first, last, colour in rows:
    g += g{ _:{(first, last)} ex:name {first} ; ex:likes {colour} }
people = {s for s, p, o in g}
assert len(people) == 1 and len(g) == 3     # one person, one name, two colours
```

A tuple key is canonically encoded before hashing, so `_:{(fname, lname)}`
cannot collide with `_:{fname + lname}`.

## Templates

A `g{ ... }` containing [variables](terms.md#variables-name-name) and with no
`@bindings` in scope is a **template**: the variables stay `Variable` terms.

```ldpy
@prefix ex: <http://example.org/ns#> .
template = g{ ?s ex:level ?v }
terms = {type(o).__name__ for s, p, o in template}
assert terms == {"Variable"}
```

With bindings in scope — or given by the [call suffix](bindings.md#the-call-suffix-explicit-context)
— the same island is *instantiated*: bound variables become terms, a triple
with an unbound term is dropped, blank nodes are fresh. That is the subject of
[bindings and templates](bindings.md).

## Adding a graph to another

`g1 += g2` is rdflib's own operation and works as usual. Note that ldpy
materialises emitted graphs lazily, so `target += g{ ... }` performs a single
store insertion rather than one per triple. To write into a graph without an
assignable target, use [`+{ ... }`](current-graph.md).
