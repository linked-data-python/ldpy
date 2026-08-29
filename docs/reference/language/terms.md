# Terms

An RDF term written in ldpy evaluates to the corresponding `rdflib` object,
immediately, wherever a Python expression may appear. Terms are the smallest
islands: they need no delimiter beyond their own syntax.

## IRIs — `<...>`

An IRI reference between angle brackets, in Turtle's syntax. A relative IRI is
resolved against the `@base` in scope; without a base it is kept as written.

```ldpy
@base <http://example.org/data/> .
absolute = <http://example.org/a>
relative = <sensor/1>
assert str(relative) == "http://example.org/data/sensor/1"
assert type(absolute).__name__ == "URIRef"
```

`<` opens an IRI **only where an operand may begin** — this is what keeps
`a<b>c` a chained comparison ([rule 1](lexical.md#rule-1-operand-context)).
An IRI may not span a line and may not contain a space; for a computed IRI use
the [formatted IRI](#formatted-iris-f) below.

## Prefixed names — `ex:local`

The namespace is resolved at transpile time against the `@prefix`
declarations [in scope](declarations.md). On an ordinary local part the whole
name is emitted as a constant `URIRef`.

```ldpy
@prefix ex:  <http://example.org/ns#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
assert str(ex:Thing) == "http://example.org/ns#Thing"
assert str(xsd:integer) == "http://www.w3.org/2001/XMLSchema#integer"
```

The local part may itself be interpolated, which is the form to use when the
name is computed but the namespace is not:

```ldpy
@prefix ex: <http://example.org/ns#> .
name = "Sensor"
assert str(ex:{name}) == "http://example.org/ns#Sensor"
assert str(ex:{name.lower()}) == "http://example.org/ns#sensor"
```

When the local part holds a [`Variable`](#variables-name-name) or a
[deferred expression](../sparql-expressions.md) instead of an ordinary value,
the whole prefixed name becomes deferred too, and is resolved against the
[current bindings](bindings.md#for-bindings-in-iter-the-loop-that-carries-them)
— see [`ex:{?id}` joins, `e<…{?id}>` encodes](bindings.md#for-bindings-in-iter-the-loop-that-carries-them)
for how that differs from a deferred IRI.

Three conditions make `p:local` a prefixed name rather than Python: the prefix
must be **declared**, there must be **no space** around the `:`, and the local
part must start with a letter, `_` or `{`. That is what leaves `arr[i:j]` and
`{k: v}` untouched — with the [residual cases](lexical.md#residual-ambiguities)
documented.

Outside an island the local part is mandatory: bare `ex:` is too close to a
dict display to be captured. Inside `g{ }` and its siblings, Turtle's full
rules apply and `ex:` alone is a valid name.

## RDF literals — `"..."@lang`, `"..."^^dt`

A Python string literal carrying a **glued** RDF suffix. Both suffixes must
touch the closing quote: `"a" @ en` stays Python's matrix multiplication.

```ldpy
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
plain = "hello"@en
typed = "42"^^xsd:integer
assert plain.language == "en"
assert typed.datatype == xsd:integer and int(typed) == 42
```

The string may be an f-string, and the language tag is part of the term:

```ldpy
value = 21.5
label = f"{value} degrés"@fr
assert str(label) == "21.5 degrés" and label.language == "fr"
```

A literal *without* a suffix has no notation of its own outside an island: a
bare Python string stays a Python string. Inside a graph it becomes a literal
by position; elsewhere use `f{expr}` or `Literal(...)`. This is a deliberate
scope limit — see [what the notation does not reach](../../explanation/what-real-code-does.md#what-the-notation-still-does-not-reach).

## Variables — `?name`, `$name`

SPARQL's variables. Neither `?` nor `$` can begin a Python expression, so they
are always an island — which also makes their error messages precise.

```ldpy
v = ?name
assert type(v).__name__ == "Variable" and str(v) == "name"
assert ?name == $name
```

A variable is an ordinary value here. What it *means* depends on where it is
used: a term in a [graph template](bindings.md), a projection in a
[match island](querying.md), a hole in a [deferred expression](../sparql-expressions.md).

## Formatted IRIs — `f<...>`

The counterpart of Python's f-string for IRIs: literal text with `{expr}`
holes, joined and resolved against `@base`. This is the form for a computed
IRI — string interpolation inside `<...>` is *not* supported, and the error
message says so.

```ldpy
@base <http://example.org/data/> .
sensor_id, kind = 7, "temp"
iri = f<sensor/{kind}/{sensor_id}>
assert str(iri) == "http://example.org/data/sensor/temp/7"
```

Each hole is converted with `str()` and joined verbatim — no percent-encoding
is applied, because the surrounding text is yours to control. (The
[deferred](../sparql-expressions.md#deferred-iris-e) form `e<...>` *does*
percent-encode, because there the value comes from a solution mapping.)

## Formatted nodes — `f{expr}`, `?{expr}`

An arbitrary Python value coerced to an RDF term. The two spellings are
synonyms; `?{ }` reads better next to variables, `f{ }` next to f-strings.

```ldpy
from rdflib import URIRef
n = f{21.5}
same = ?{21.5}
passthrough = f{URIRef("http://example.org/a")}
assert n.datatype is not None and n == same
assert type(passthrough).__name__ == "URIRef"       # terms pass through
```

The conversion is `node()`, and it is configurable —
see [Python → RDF coercion](coercion.md).

## Adjacency, in one line

`f{`, `?{`, `f<`, `e{`, `e<`, `g{`, `m{`, `s{` and the literal suffixes
`@lang` / `^^` all require **no intervening space**. `NAME{` is never valid
Python, so nothing is lost — and a space is the escape hatch when you want the
Python reading. See [rule 2](lexical.md#rule-2-strict-adjacency).
