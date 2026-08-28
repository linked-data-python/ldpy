# Python API reference

## `ldpy.transpiler`

```python
from ldpy.transpiler import transpile, LdpySyntaxError, LdpyWarning, LanguageMap
```

### `transpile(source, filename="<ldpy>") -> TranspileResult`

Transpiles a Linked-Data Python source string. Raises `LdpySyntaxError`
(a `SyntaxError` subclass with 1-based `lineno`/`offset` and 0-based
`line`/`col`) on invalid island syntax. Never executes anything.

### `TranspileResult`

| Attribute | Meaning |
|---|---|
| `code` | the generated Python source |
| `map` | the `LanguageMap` |
| `prefixes` | `dict` prefix → IRI, final lexical state |
| `base` | final base IRI or `None` |
| `warnings` | list of `LdpyWarning` (scope issues, redeclarations) |

```python
from ldpy.transpiler import transpile
r = transpile("x = 1\n")
assert r.code == "x = 1\n" and r.warnings == []   # pure Python: identity
```

### `LanguageMap`

Bidirectional position mapping (0-based lines/columns, exclusive ends).

| Method | Meaning |
|---|---|
| `to_gen(line, col)` / `to_src(line, col)` | translate a position (or `None`) |
| `src_line_for_gen_line(line)` | for tracebacks |
| `to_json()` / `from_json(s)` | JSON v1 (segments) |
| `to_sourcemap_v3()` / `to_sourcemap_v3_json()` | standard Source Map v3 |

## `ldpy.runtime`

The façade the generated code calls (imported as `_ldpy_`); also usable
directly: `URIRef, Literal, Variable, Namespace, RDF` re-exports, plus

- `node(value, field=None)` — coerce a Python value to an RDF term (terms
  pass through); `field` feeds the coercion policy (fiche 020);
- `firi(*parts, base=None)` — join parts, resolve against `base` if relative;
- `pname(ns, *parts)` — dynamic prefixed name (imported or computed prefix);
- `dtype(value)` — coerce a value to a datatype IRI (`{expr}` after `^^`);
  unlike `node`, a `str` becomes a `URIRef`, never a `Literal`;
- `graph(namespaces, base, *triples, bindings=None)` — build an
  `rdflib.Graph` from flattened triples with `bn(i)`/`slot(i, expr)`
  placeholders; with `bindings`, templates are instantiated;
- `new_graph(namespaces, base, identifier=None)` — the graph created by
  `@graph as g`, serialization prefixes bound;
- `add_to(graph, *triples, bindings=None)` / `remove_from(graph, *patterns,
  bindings=None)` — the `+{ }` / `-{ }` statements (unbound variable:
  dropped triple / joker, `DELETE WHERE` on shared variables);
- `match(graph, patterns, project, bindings=None)` → `Match` — the `m{ }`
  island (lazy nested-loop join; `first()`, `one()`, `count()`);
- `prepared(text, interps, namespaces, base, graph=None, bindings=None,
  update=False)` → `PreparedQuery` — the `s{ }` island (lazy, cached).
  Iterating or truth-testing runs it; `execute()` runs it and returns rdflib's
  result, which is what an `INSERT`/`DELETE` needs since it has no solutions
  to iterate;
- `Bindings` — mapping with str/Variable keys and RDF-coerced values;
  `as_bindings_iter(iterable)` — the `for @bindings in …` adapter;
- `Coercion(rules)` — the Python → RDF coercion policy (also exported as
  `ldpy.Coercion`);
- `instantiateBGP(graph, solution_mappings, initial=None)`.

```python
from ldpy.runtime import node, firi, Literal
assert node(42) == Literal(42)
assert str(firi("http://e/", 7, "/x")) == "http://e/7/x"
```

## `ldpy.pygments_lexer`

```python
from ldpy.pygments_lexer import LdpyLexer
```

A Pygments lexer for `.ldpy`, built on the language map: `copy` segments go to
Pygments' `PythonLexer`, island segments are tokenised by kind. Registered as a
Pygments plugin (entry point `pygments.lexers`), so `get_lexer_by_name("ldpy")`
finds it once the package is installed — see
[how to highlight ldpy code](../how-to/highlight-ldpy.md).

```python
from pygments.lexers import get_lexer_by_name
lexer = get_lexer_by_name("ldpy")
tokens = list(lexer.get_tokens_unprocessed("g = g{ }\n"))
assert "".join(v for _, _, v in tokens) == "g = g{ }\n"
```

## Top level `ldpy`

```python
import ldpy
```

- `ldpy.install()` / `ldpy.uninstall()` — the `.ldpy` import hook;
- `ldpy.install_excepthook()` — no-op kept for compatibility (tracebacks are
  already in `.ldpy` coordinates since the mapped compilation, fiche 011);
- `ldpy.transform_source(source, filename)` — v1-compatible shim returning
  `(code, prefixes, map)`;
- `ldpy.transpile` — re-export of the above;
- `ldpy.Coercion(rules)` — Python → RDF coercion policy (fiche 020).

## `ldpy.sparql`

Deferred SPARQL expressions (the `e{...}` / `e<...>` islands compile to
these). `Expression(sm)` / `.evaluate(sm)` return an RDF term or raise
`SparqlError`; `.ebv(sm)` returns a Python bool. Mappings accept `str` or
`Variable` keys and Python or RDF values.

```python
import sys
from ldpy.transpiler import transpile
code = transpile("adult = e{ ?age >= 18 }\n").code
ns = {}
exec(code, ns)
assert ns["adult"].ebv(age=21) is True
```

## `ldpy.debug`

- `translate_breakpoints(map, lines_1based)` — `.ldpy` → shadow lines;
- `translate_frames(map, lines_1based)` — shadow → `.ldpy` lines;
- `load_map(path)` — read a `.ldpy.map` file.

## `bench.generator`

```python
from bench.generator import generate
src, stats = generate(n_lines=100, island_density=0.5, seed=1)
assert stats["islands"] > 0
```

Deterministic random generation of valid, executable ldpy sources
(parameters: `n_lines`, `island_density`, `graph_triples`, `nest_depth`,
`mix`, `v1_compat`, `seed`).
