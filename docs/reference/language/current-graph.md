# The current graph — `@graph`, `+{ }`, `-{ }`

Almost all RDF code works on one graph at a time: in a corpus of 376 real
repositories, [88 % of functions that touch a graph touch exactly one](../../explanation/what-real-code-does.md#one-graph-at-a-time),
and its name is repeated at every operation. `@graph` names that graph once,
for a block; `+{ }` and `-{ }` write to it.

## `@graph` — designate or create

```ldpy
@prefix ex: <http://example.org/> .
@graph as g                          # create: g = a fresh Graph
+{ ex:s ex:p 1 }
assert len(g) == 1
```

Three forms, all with the same [block scope](declarations.md#block-scope) as
`@prefix`:

| Form | Effect |
|---|---|
| `@graph g` | designate the existing Python variable `g` as current |
| `@graph as g` | create a fresh graph, bind it to `g`, make it current |
| `@graph <iri> as g` | same, with `Graph(identifier=<iri>)` |

```ldpy
@prefix ex: <http://example.org/> .
from rdflib import Graph
mine = Graph()
@graph mine                          # designate: no new graph
+{ ex:s ex:p 1 }
assert len(mine) == 1

@graph <http://example.org/g1> as named
assert str(named.identifier) == "http://example.org/g1"
```

Either form gives the graph the **prefixes in scope**, so it serialises with
them and you never have to `bind()` them by hand:

```ldpy
@prefix ex: <http://example.org/ns#> .
from rdflib import Graph
mine = Graph()
@graph mine
+{ ex:a ex:p 1 }
assert "@prefix ex:" in mine.serialize(format="turtle")
```

For a designated graph the prefixes are *added* to the bindings it already
carries — it belongs to its caller, and nothing it had is discarded. Until
0.6.3 only a *created* graph inherited them, so the same block filling two
graphs the same way serialised them differently; that was an inconsistency
rather than a decision (record ldpy/027).

The identifier is nothing more than rdflib's `Graph(identifier=…)`
constructor parameter. `@graph` designates *a* graph, possibly named — never
a dataset or a space of graphs; that usage was measured at 6.8 % of graph
constructions and is left to rdflib's own API.

## `+{ ... }` and `-{ ... }` — write to it

Both take a Turtle-notation pattern, exactly like [`g{ }`](graphs.md), and are
**statements**: they produce no value.

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:s ex:p 1 ; ex:q 2 }            # add two triples
-{ ex:s ex:q 2 }                     # remove one
for i in range(3):
    +{ ex:s ex:n {i} }               # one triple per iteration
assert len(g) == 4
```

They are accepted in **statement position** at bracket depth zero: at the
start of a logical line, after a `;`, and as the suite of a compound
statement (`if cond: +{ … }` on one line). Everywhere else `+` and `-` keep
their Python meaning — `keys - {'a'}` stays a set difference. In statement
position, `+{…}` *is* legal Python but always dead (unary plus on a set or
dict raises `TypeError`), so capturing it costs no real code. The full rule is
[in the lexical reference](lexical.md#two-forms-outside-the-sigil-rule).

The emitted code calls `add_to` / `remove_from`, never `+=`. That is what
makes a read-only property or a module global writable with no `global`
declaration and no `__iadd__` dance — a limitation the corpus study ran into
repeatedly.

### Variables in `+{ }` and `-{ }`

Both accept variables, both instantiate them against the
[current bindings](bindings.md), and the *direction* decides what an unbound
variable means:

| Island | Unbound variable |
|---|---|
| `+{ }` | the triple is **dropped** — an unknown term cannot be written |
| `-{ }` | a **wildcard** — as in rdflib's `remove((s, p, None))` |

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:s ex:p 1 ; ex:q 2 ; ex:r 3 }
-{ ex:s ?p ?o }                      # wildcards: removes everything
assert len(g) == 0
```

A multi-pattern `-{ }` whose patterns share variables removes by matching,
like SPARQL's `DELETE WHERE`:

```ldpy
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a a ex:Draft ; ex:body "x" . ex:b a ex:Final ; ex:body "y" }
-{ ?s a ex:Draft ; ex:body ?b }      # only the draft and its body
assert len(g) == 2
```

## Which graph does an island use?

`+{ }`, `-{ }`, `m{ }` and `s{ }` all read the current graph. If none is
declared in scope, they raise at run time — unless the graph is given by the
[call suffix](bindings.md#the-call-suffix-explicit-context):

```ldpy
@prefix ex: <http://example.org/> .
from rdflib import Graph
other = Graph()
+{ ex:s ex:p 1 }(other)              # explicit receiver, no @graph needed
assert len(other) == 1
```

The receiver is not limited to a bare name: the parenthesis takes any Python
expression that evaluates to a graph — an attribute, a subscript, a method
call. That is what lets the island work unmodified inside object-oriented
code, including against a **read-only property**, where `g += g{ }` cannot:
`+=` needs to assign the result back through the property, and a
property with no setter refuses it, while `+{ }(...)` never assigns to its
receiver at all — it calls `add_to` on whatever the expression returns.

```ldpy
@prefix ex: <http://example.org/> .
from rdflib import Graph

class Store:
    def __init__(self):
        self._graph = Graph()

    @property
    def graph(self):                 # read-only: no setter
        return self._graph

    def get_graph(self):
        return self._graph

store = Store()
graphs = [Graph(), Graph()]
+{ ex:s ex:p 1 }(store.graph)        # attribute
+{ ex:s ex:p 2 }(graphs[1])          # subscript
+{ ex:s ex:p 3 }(store.get_graph())  # method call
assert len(store.graph) == 2 and len(graphs[1]) == 1
```

## Scope, and escaping it

`@graph` follows the block-scope rule, so a graph created inside an `if` or a
`for` disappears with it. `global` and `nonlocal`
[work as in Python](declarations.md#scope-modifiers-global-and-nonlocal) and
are how you keep it:

```ldpy
@prefix ex: <http://example.org/> .
def collect(rows):
    @graph as out
    for r in rows:
        +{ ex:s ex:p {r} }
    return out
assert len(collect([1, 2, 3])) == 3
```
