# SPARQL expressions reference

`e{ <expression> }` compiles to a **deferred** `ldpy.sparql.Expression`;
`e<...{expr}...>` to a deferred IRI template. Both evaluate against a
*solution mapping* — a dict with `str` or `rdflib.Variable` keys and Python
or RDF values (Python values are coerced with `node()`).

```ldpy
price_ok = e{ ?price * (1 + ?vat) <= 100 }
assert price_ok.ebv(price=80, vat=0.2) is True
assert str(price_ok({"price": 90, "vat": 0.2})) == "false"
```

| API | Meaning |
|---|---|
| `expr(sm)` / `expr.evaluate(sm)` | RDF term result, or raises `SparqlError` |
| `expr.ebv(sm)` | effective boolean value, as a Python `bool` |
| `expr(**kwargs)` | bindings as keyword arguments |
| `repr(expr)` | the island's source text |

## Expression language

Operators, by increasing precedence: the Python-style ternary
`value if cond else other`; `||`; `&&`; comparisons
`= != < > <= >=` and `IN (…)` / `NOT IN (…)`; `+ -`; `* /`; unary `! - +`.
Terms: `?var` / `$var`, IRIs `<…>`, prefixed names (declared prefixes,
resolved statically), strings with optional `@lang` / `^^datatype`, numbers
(`xsd:integer`, `xsd:decimal`, `xsd:double` following the SPARQL lexical
rules), `true` / `false`, nested `e<...>`, and `{python}` interpolations —
re-evaluated at **each** evaluation of the expression:

```ldpy
threshold = [10]
over = e{ ?x > {threshold[0]} }
assert over.ebv(x=50) is True
threshold[0] = 100
assert over.ebv(x=50) is False
```

## Errors and three-valued logic

An unbound variable, incomparable terms, or a failing built-in raise
`ldpy.sparql.SparqlError`. Errors propagate, and are absorbed exactly where
SPARQL absorbs them:

| Expression | Result |
|---|---|
| `true \|\| error` | `true` |
| `false \|\| error` | error |
| `false && error` | `false` |
| `true && error` | error |
| `IF(cond, a, b)` | only the chosen branch is evaluated |
| `COALESCE(a, b, …)` | first argument that evaluates without error |

Arithmetic follows SPARQL's numeric promotion; in particular
`xsd:integer / xsd:integer` yields an `xsd:decimal`.

## Built-in functions

| Category | Functions |
|---|---|
| Terms | `STR`, `LANG`, `DATATYPE`, `IRI`/`URI` (resolved against the lexical `@base`), `BNODE`, `SAMETERM`, `ISIRI`/`ISURI`, `ISBLANK`, `ISLITERAL`, `ISNUMERIC` |
| Strings | `CONCAT`, `UCASE`, `LCASE`, `STRLEN`, `SUBSTR`, `STRSTARTS`, `STRENDS`, `CONTAINS`, `STRBEFORE`, `STRAFTER`, `REPLACE`, `REGEX`, `ENCODE_FOR_IRI` |
| Numbers | `ABS`, `ROUND`, `CEIL`, `FLOOR` |
| Logic | `BOUND(?v)` (argument must be a variable), `IF`, `COALESCE` |
| Languages | `LANGMATCHES` |

```ldpy
label = e{ CONCAT(UCASE(SUBSTR(?name, 1, 1)), SUBSTR(?name, 2)) }
assert str(label(name="ana")) == "Ana"
guard = e{ IF(BOUND(?nick), ?nick, ?name) }
assert str(guard(name="Ana")) == "Ana"
assert str(guard(name="Ana", nick="An")) == "An"
```

## Deferred IRIs: `e<...>`

Static parts are kept verbatim; each `{…}` hole is a SPARQL expression whose
value goes through `STR` then IRI-safe percent-encoding, and the result is
resolved against the lexical `@base` of the definition site:

```ldpy
person = e<http://example.org/person/{?name}/{?age + 1}>
assert str(person(name="Ana Lu", age=20)) == "http://example.org/person/Ana%20Lu/21"
```

## Limits

- `e{...}` / `e<...>` are not (yet) valid as terms *inside* `g{...}` graphs.
- Custom functions called by IRI are not supported; use a `{python}`
  interpolation instead.
