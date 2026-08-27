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

Inside `g{ ... }` the notation is Turtle's: `a` for `rdf:type`, `;` and `,`
lists, `[ ... ]` blank-node property lists, `( ... )` collections, `_:b`
labels (scoped to the island), `#` comments — plus `{expr}` interpolations in
any term position.

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
- Character sets: island trigger names (prefixes, `?vars`) are ASCII
  identifiers; local parts follow Python's Unicode identifier rule (plus `-`
  and `.` inside islands). Turtle's full `PN_CHARS` is wider in places (3 400
  BMP characters, `-` and `·` included) and narrower in others (µ, ª): the
  two sets are incomparable, and reconciling them exactly is an open design
  question (design record 010). A declaration with a non-ASCII prefix is a
  clear error, not a silent mangling.
