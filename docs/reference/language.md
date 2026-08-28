# Language reference

A `.ldpy` file is a Python file in which RDF **islands** may appear. Every
valid Python program is a valid ldpy program with unchanged meaning.

## Islands

| Island | Example | Value |
|---|---|---|
| Prefix declaration | `@prefix ex: <http://e/> .` | *(statement)* binds `ex` |
| Base declaration | `@base <http://e/> .` | *(statement)* sets the base IRI |
| IRI | `<http://e/a>`, `<rel>` | `URIRef`, resolved against the base |
| Prefixed name | `ex:Thing`, `ex:{expr}` | `URIRef`, resolved at transpile time |
| RDF literal | `"a"@en`, `"1"^^xsd:int`, `f"v{x}"@en` | `Literal` |
| Variable | `?name`, `$name` | `Variable` |
| Formatted IRI | `f<http://e/{expr}/y>` | `URIRef` built by interpolation |
| Formatted node | `f{expr}`, `?{expr}` | any value, coerced to an RDF term |
| Graph | `g{ ex:s a ex:C ; ex:p 1, "x" }` | `rdflib.Graph` |
| Data-keyed blank node | `_:{expr}` *(in graphs)* | `BNode` with deterministic identity |
| SPARQL expression | `e{ ?age >= 18 && BOUND(?n) }` | a **deferred** `Expression` |
| Deferred IRI | `e<http://e/p/{?n}>` | a deferred `Expression` yielding a `URIRef` |
| SPARQL query | `s{ SELECT ?x WHERE { ?x a {cls} } }` | a lazy prepared query |
| Match (BGP) | `m{ ?s a ex:C ; ex:v ?v }` | lazy solutions over the current graph |
| Add / remove *(statements)* | `+{ ex:s ex:p 1 }`, `-{ ex:s ?p ?o }` | write to the current graph |
| Current graph | `@graph g`, `@graph as g`, `@graph ex:g1 as g` | *(declaration)* |
| Current bindings | `@bindings b`, `@bindings as b`, `for @bindings in it:` | *(declaration)* |
| Prefix import | `from vocab import brick:, unit: as u:` | *(declaration)* imports prefixes |

Inside `g{ ... }` the notation is Turtle's: `a` for `rdf:type`, `;` and `,`
lists, `[ ... ]` blank-node property lists, `( ... )` collections, `_:b`
labels (scoped to the island), `#` comments — plus `{expr}` interpolations in
any term position. An interpolation may carry a glued RDF suffix —
`{expr}@en` (language tag) or `{expr}^^xsd:integer` (datatype) — and the
datatype may itself be interpolated, `{expr}^^{dt}`, for the generic case
where the type is computed at run time (a datatype is always an IRI, so a
string there is read as an IRI, not as a literal); and
`_:{expr}` denotes a blank node whose identity derives from the value:
equal values give the same node, across graphs and across sources (the
R2RML deduplication/join idiom). A tuple key is canonically encoded and
hashed, so `_:{(fname, lname)}` cannot collide with `_:{fname + lname}`;
unlike `_:b` labels, which stay fresh at each evaluation.

```ldpy
@prefix ex:  <http://example.org/ns#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@base <http://example.org/data/> .

v = 21.5
g = g{ <sensor/1> a ex:Sensor ;              # relative IRI, resolved
          ex:reading [ ex:value {v} ;        # nested blank node
                       ex:unit ex:celsius ] ;
          ex:tags ( 1 "two"@en ?{v + 0.5} ) }
assert len(g) == 11
```

## Disambiguation rules

Three rules keep the extension unambiguous with Python (design record 002):

1. **Operand context.** `<` opens an IRI only where an operand may begin
   (after `=`, `(`, `,`, `return`, ...). `a<b>c` stays a chained comparison.
2. **Strict adjacency.** `g{`, `f{`, `f<`, `?{`, `"x"@en`, `"x"^^t` require
   no intervening space. `'a' @ en` stays matrix multiplication.
3. **Declared prefixes.** `p:local` is a prefixed name only if `p` was
   declared by an in-scope `@prefix` and the local part starts with a letter,
   `_`, or `{`. `arr[i:j]` and `{k: v}` are untouched.

Residual collisions, documented and testable: with `ex` a *declared* prefix,
`arr[ex:b]` and `{ex:b}` read as prefixed names — write spaces (`arr[ex : b]`)
to force the Python reading.

## Deferred SPARQL expressions: `e{ ... }` and `e<...>`

Where `f{...}`/`?{...}` evaluate immediately, `e{...}` builds a **deferred**
expression, evaluated later against a *solution mapping* — the natural tool
for filters and templates over `instantiateBGP`-style bindings:

```ldpy
adult = e{ ?age >= 18 && BOUND(?name) }
rows = [{"age": 12}, {"age": 30, "name": "Ana"}]
kept = [r for r in rows if adult.ebv(r) ]
assert len(kept) == 1
iri = e<http://example.org/person/{?name}>
assert str(iri(name="Ana Lu")) == "http://example.org/person/Ana%20Lu"
```

The expression language is SPARQL 1.1's: `||`, `&&`, `!`, comparisons,
`IN`/`NOT IN`, arithmetic with numeric promotion (`7/2` is an `xsd:decimal`),
a Python-style ternary (`v if cond else w`), and the core built-ins (`STR`,
`LANG`, `DATATYPE`, `IRI`, `BOUND`, `CONCAT`, `UCASE`, `LCASE`, `STRLEN`,
`SUBSTR`, `STRSTARTS`, `STRENDS`, `CONTAINS`, `STRBEFORE`, `STRAFTER`,
`REPLACE`, `REGEX`, `ABS`, `ROUND`, `CEIL`, `FLOOR`, `IF`, `COALESCE`,
`SAMETERM`, `ISIRI`, `ISBLANK`, `ISLITERAL`, `ISNUMERIC`, `LANGMATCHES`).
Errors follow SPARQL's three-valued logic: an unbound variable is an error,
absorbed only by `||`/`&&`/`IF`/`COALESCE`. `{expr}` interpolations inside
`e{}` are re-evaluated at each evaluation. Mappings accept `str` or
`Variable` keys, plain Python or RDF values. `e{...}` islands are not (yet)
valid inside `g{...}` graphs.

## Scope of `@prefix` and `@base`

Declarations have **lexical block scope**: from the declaration to the end of
the enclosing suite (body of `if`/`for`/`def`/`class`; the rest of the file at
top level). Leaving the block restores the previous binding.

```ldpy
@prefix p: <http://outer/> .
def f():
    @prefix p: <http://inner/> .
    return p:x                       # http://inner/x
inner, outer = f(), p:x              # outer = http://outer/x
assert str(outer) == "http://outer/x" and str(inner) == "http://inner/x"
```

Resolution happens at transpile time; runtime control flow does not change
it. Warnings: using a prefix after its block ended (the text is left as
Python); redeclaring a used prefix at the same level with a different IRI.

## Prefixes across modules

Every module-level `@prefix` is **exported**; a prefix declared inside a
function stays private (block scope). On the importing side, a prefixed name
in the import list imports a prefix — illegal Python, so nothing is captured:

```text
from myproject.vocab import something, brick:, unit: as u:
```

The regime is uniform and **dynamic**: the transpiler never reads the
imported module — the import declares the prefix lexically, and `brick:Class`
resolves at run time through the imported namespace binding. A computed IRI
takes the same path:

```ldpy
host = "example.org"
@prefix dyn: f<http://{host}/ns#> .
assert str(dyn:x) == "http://example.org/ns#x"
```

`import m` and `from m import *` import no prefixes; `@base` is not
exported; `__namespaces__` in `__all__` is refused at transpile time.

## The current graph: `@graph`, `+{ }`, `-{ }`

`@graph` declares the **current graph** — the graph that `+{ }`, `-{ }`,
`m{ }` and `s{ }` read or write when not given one explicitly. Same block
scope as `@prefix`. `as` creates; without `as`, `@graph` only designates:

```ldpy
@prefix ex: <http://e/> .
@graph as g                          # creates: g = a fresh Graph
+{ ex:s ex:p 1 ; ex:q 2 }            # add to the current graph
-{ ex:s ex:q 2 }                     # remove (unbound variables are jokers)
for i in range(3):
    +{ ex:s ex:n {i} }               # one triple per iteration
assert len(g) == 4
@graph <http://e/g1> as named        # creates Graph(identifier=...)
assert str(named.identifier) == "http://e/g1"
```

`+{ … }` / `-{ … }` are **statements**, accepted only at the start of a
logical line at bracket depth zero — elsewhere `+` and `-` keep their Python
meaning (`keys - {'a'}` stays a set difference). The emitted code calls
`add_to`/`remove_from`, never `+=`: read-only properties and module globals
are writable without `global` or `__iadd__`. A multi-pattern `-{ }` sharing
variables removes by matching (`DELETE WHERE`).

## Reading the graph: `m{ ... }`

A `m{ … }` island is a Turtle-syntax **basic graph pattern** with variables,
matched against the current graph by nested-loop join in written order — no
engine, nothing but `graph.triples()`. Arity 1 yields terms; arity ≥ 2
yields unpackable rows with named access. A blank node is a
**non-distinguished variable**: matched, not projected.

```ldpy
@prefix ex: <http://e/> .
@graph as g
+{ ex:a a ex:Sensor ; ex:v 1 . ex:b a ex:Sensor ; ex:v 2 }
names = sorted(m{ ?s a ex:Sensor })              # arity 1: terms
pairs = sorted((s, v) for s, v in m{ ?s a ex:Sensor ; ex:v ?v })
one = m{ ex:a ex:v ?v }.one()                    # exactly one, or raises
none = m{ ex:zzz ex:v ?v }.first()               # None when absent
assert bool(m{ ex:a a ex:Sensor })               # ASK, lazily
assert m{ ?s a ex:Sensor }.count() == 2          # consumes; len() fails
assert len(pairs) == 2 and none is None
```

No FILTER, OPTIONAL, UNION, paths or aggregates: Python's `if` covers the
measured usage, and `s{ … }` covers the rest.

## SPARQL queries: `s{ ... }`

All of SPARQL, validated **at transpile time** with rdflib as the oracle — a
syntax error surfaces when transpiling, not on first execution.
Interpolations are allowed **in term position only** and become
`initBindings` (no string injection, by construction); the prologue is
inherited from the `@prefix` declarations in scope. The island value is a
lazy prepared query: iterating (or truth-testing) executes it on the current
graph; calling rebinds it.

```ldpy
@prefix ex: <http://e/> .
@graph as g
+{ ex:a a ex:Sensor ; ex:v 1 . ex:b a ex:Sensor ; ex:v 2 }
cls = ex:Sensor
rows = [tuple(r) for r in s{ SELECT ?s ?v WHERE { ?s a {cls} ; ex:v ?v }
                             ORDER BY ?v }]
assert len(rows) == 2
assert bool(s{ ASK { ex:a a ex:Sensor } })
```

Updates (`INSERT`/`DELETE`) run through `graph.update`. Prepared queries are
cached (bounded, hand-written — no `functools.lru_cache`).

## Bindings and graph templates: `@bindings`, `e{ }` as a term

`@bindings` declares the **current bindings** — a mapping from variables to
values — with the same block scope as `@graph`. Without bindings in scope, a
`g{ }` with variables stays a **template** (variables remain `Variable`
terms); with bindings in scope it is **instantiated**: bound variables become
terms, a triple with an unbound term is dropped, blank nodes are fresh.
`e{ … }` and `e<…>` are accepted in term position and evaluate against the
same bindings (a SPARQL error leaves the term unbound, dropping the triple).

`for @bindings in ITER:` makes each element of an iterable of mappings the
current bindings of the loop body — a `m{ … }` yields its solutions, and a
`csv.DictReader` is one line away from a graph. `for @bindings as b in …`
also names it. A four-line CONSTRUCT, with no query engine and no query
text:

```ldpy
@prefix ex: <http://e/> .
@graph as src
+{ ex:c1 ex:reading 10 . ex:c2 ex:reading 25 }
@graph as out
for @bindings in m{ ?s ex:reading ?v }(src):
    +{ ?s ex:hasValue e{ ?v * 2 } }
assert sorted(int(o) for s, o in m{ ?s ex:hasValue ?o }(out)) == [20, 50]
```

## The call suffix: explicit context

An island followed by a parenthesis receives the context it would have read
around it — **graph first, bindings second**, both optional, `bindings=` to
give only the second. One rule for six islands: `m{ P }(g)`, `m{ P }(g, b)`,
`s{ Q }(g, b)`, `+{ P }(g)`, `+{ P }(bindings=b)`, `-{ P }(g)`, `e{ E }(b)`,
and `g{ P }(b)` — the template instantiated against `b`. The suffix
overrides the declared context for that island only.

## Scope modifiers: `global` and `nonlocal`

The four island declarations accept Python's scope modifiers, with Python's
exact semantics — `global` installs at module scope, `nonlocal` rebinds the
nearest enclosing declaration (an error if there is none):

```ldpy
@prefix ex: <http://e/> .
for cand in range(3):
    if cand == 1:
        global @graph as chosen      # survives the break
        break
+{ ex:s ex:p {cand} }
assert len(chosen) == 1
```

## Python → RDF coercion

`ldpy.Coercion` declares how plain Python values entering islands become RDF
terms — by **field name** (mapping key or pattern variable) first, then by
**Python type** (MRO), defaulting to `Literal`. Policies are values: `with
policy:` stacks one for a region (an inner `with` refines the outer),
`policy.install()` keeps it for the module. A datatype position (`^^`) stays
out of policy — a datatype is an IRI by definition.

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
assert list(ns["g"])[0][2].datatype == XSD.integer
```

## Blank node semantics

Each syntactic `[ ]`, collection cell, or `_:label` denotes a blank node
**fresh at every evaluation** of its graph expression; labels are shared
within one `g{ ... }` island only.

## Known limitations

- Python string contents are opaque: no islands inside f-strings; write
  `f<...>` (not `<...{x}...>` — the error message points to the right form).
- PEP 701 f-strings (same-quote nesting) are unsupported, as in MicroPython.
- The emitted code stays within a Python-3.4-level subset; source f-strings
  pass through unchanged.
- Character sets — **inside islands, Turtle's exact `PN_CHARS` tables**:
  prefixed names accept hyphenated and dotted prefixes (`o-pizza:Named`),
  digit-initial locals (`ex:1a`), interior dots, `·` and combining marks;
  **outside islands, the intersection** of Python identifiers and `PN_CHARS`
  applies (a valid Python program can never be captured): `ex:café` works,
  `-` stays subtraction, and Python-only identifier characters (µ, ª) end a
  local part — Turtle could not write them either. A prefix that is not a
  Python identifier (like `o-pizza`) is declarable and usable inside islands
  only. Local parts do not support interior `:` or `%`/`\` escapes. These
  rules are verified against an independent transcription of the specs by
  `tools/charsets.py`.
