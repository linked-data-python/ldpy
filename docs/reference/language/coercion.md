# Python → RDF coercion

A plain Python value entering an island has to become an RDF term. By default
it becomes a `Literal` with rdflib's own datatype inference — `42` an
`xsd:integer`, `"a"` a plain literal, an `rdflib` term itself passes through
unchanged. `ldpy.Coercion` is how you change that, for a region of code, when
the default is not what your data means.

The motivating case is tabular input: every cell of a CSV file is a `str`, but
the `id` column holds IRIs and the `age` column holds integers.

## The default

One function, `node()`, is the single entry point — for interpolations, for
`f{ }`, for the values of a `@bindings` mapping, for `+{ }`.

```ldpy
from rdflib import URIRef
assert f{42}.datatype is not None            # xsd:integer
assert f{"a"}.datatype is None               # plain literal
assert type(f{URIRef("http://e/a")}).__name__ == "URIRef"   # passes through
```

One position is outside all of this: after `^^`, a value is a **datatype**,
and a datatype is an IRI by the definition of RDF, not by anyone's choice.
`{expr}^^{dt}` reads `dt` as an IRI even when it is a `str`.

## A policy is a value

`Coercion` is a class you instantiate, name, reuse and pass around. Its
dictionary holds two kinds of key, which cannot be confused:

| Key | Matches | Example |
|---|---|---|
| a **tuple of field names** | a mapping key or a pattern variable | `("age",): XSD.integer` |
| a **Python type** | the value's type, by MRO | `datetime.date: XSD.date` |

Resolution order is: field name, then type, then `Literal`. `URIRef` in value
position means "this is an IRI".

```python
import io, csv
import ldpy
from ldpy.transpiler import transpile
from rdflib import URIRef
from rdflib.namespace import XSD

src = (
    '@prefix ex: <http://e/> .\n'
    '@graph as g\n'
    'with pol:\n'
    '    for @bindings in csv.DictReader(f):\n'
    '        +{ ?id ex:age ?age }\n')
ns = {"csv": csv, "f": io.StringIO("id,age\nhttp://e/a,30\n"),
      "pol": ldpy.Coercion({("id",): URIRef, ("age",): XSD.integer}),
      "__name__": "doc"}
exec(compile(transpile(src).code, "<doc>", "exec"), ns)
triple = list(ns["g"])[0]
assert type(triple[0]).__name__ == "URIRef"
assert triple[2].datatype == XSD.integer
```

## Scope is Python's

Policies **stack**, and the stack is walked from the top down, so an inner
`with` *refines* the outer one instead of replacing it:

- `with policy:` pushes for the block and pops on exit, exceptions included;
- `policy.install()` pushes without popping — for a whole module, where
  wrapping the file in a `with` would be absurd.

```python
import ldpy
from ldpy.transpiler import transpile
from rdflib.namespace import XSD

outer = ldpy.Coercion({("v",): XSD.integer})
inner = ldpy.Coercion({("w",): XSD.double})
src = ('@prefix ex: <http://e/> .\n'
       '@graph as g\n'
       'for @bindings in [{"v": "1", "w": "2"}]:\n'
       '    +{ ex:s ex:a ?v ; ex:b ?w }\n')
ns = {"__name__": "doc"}
with outer:
    with inner:                       # refines: ("v",) is still in force
        exec(compile(transpile(src).code, "<doc>", "exec"), ns)
kinds = {str(o.datatype) for s, p, o in ns["g"]}
assert kinds == {str(XSD.integer), str(XSD.double)}
```

## Why `with` and not a declaration

`@prefix`, `@graph` and `@bindings` are lexical declarations because they feed
the **transpiler**. A conversion policy does not: it is run-time state, and
Python already has the construct that gives run-time state a scope. Making it
an island would have bought nothing and cost a fifth sigil.

Two limits, stated rather than hidden: the stack is process state (a library
should use `with`, an application may `install()`), and it is not
thread-local — `threading.local` would fix it but does not exist in
MicroPython.
