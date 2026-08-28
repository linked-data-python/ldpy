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
