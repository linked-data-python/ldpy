# How to filter and template with deferred expressions

`e{...}` shines wherever bindings arrive as data: filtering solution
mappings, instantiating templates, validating rows.

## Filter solution mappings

```ldpy
@prefix ex: <http://example.org/ns#> .

pattern = g{ ?s a ex:Obs ; ex:val ?v }
keep = e{ ?v >= 10 && ?v < 20 }

solutions = [{"s": ex:o1, "v": 12}, {"s": ex:o2, "v": 42}]
selected = [sm for sm in solutions if keep.ebv(sm)]
assert len(selected) == 1
```

Combined with `instantiateBGP`, this reproduces the
template-plus-filter workflow of SPARQL `CONSTRUCT ... WHERE ... FILTER`:

```ldpy
@prefix ex: <http://example.org/ns#> .
from ldpy.runtime import instantiateBGP

template = g{ ?s ex:level ?v }
keep = e{ ?v > 10 }
solutions = [{?s: ex:a, ?v: 5}, {?s: ex:b, ?v: 15}]
out = instantiateBGP(template, [sm for sm in solutions if keep.ebv(sm)])
assert len(out) == 1
```

## Build IRIs from bindings

```ldpy
mint = e<http://example.org/reading/{?sensor}/{?day}>
iri = mint(sensor="s 1", day="2026-08-27")
assert "s%201" in str(iri)
```

## Validate before you assert

An expression evaluates to an error on missing data — use `ebv` in a guard,
or `COALESCE` to give defaults:

```ldpy
complete = e{ BOUND(?name) && BOUND(?age) }
label = e{ COALESCE(?name, "(anonyme)") }
assert complete.ebv({}) is False
assert str(label({})) == "(anonyme)"
```
