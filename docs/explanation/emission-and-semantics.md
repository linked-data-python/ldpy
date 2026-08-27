# Emission and semantics: islands are single expressions

Every island compiles to **one Python expression** calling a small runtime
façade (`import ldpy.runtime as _ldpy_`). The tempting alternative — hoisting
graph construction into statements before the current one — is semantically
wrong three times over: it breaks evaluation order (`cond or g{...{f()}...}`
would call `f()` even when `cond` is true), it forbids islands exactly where
they are useful (lambdas, comprehensions, default arguments), and it smears
one source line over many generated lines, ruining the language map.

A graph is therefore flattened at transpile time into `_ldpy_.graph(ns, base,
(s, p, o), ...)` with two kinds of placeholders:

- `bn(i)` — the *i*-th blank node of the island, instantiated fresh at each
  evaluation (like re-parsing a Turtle document);
- `slot(i, expr)` / `slot(i)` — a **shared interpolated term**: the subject of
  a predicate-object list appears in several triples, and if it is an
  interpolation, repeating its expression would evaluate it once per triple
  (`g{ ex:{next_id()} ex:p 1 ; ex:q 2 }` would create two different
  subjects). The expression is emitted at its first occurrence and referenced
  afterwards; identity is per *source occurrence*, so two textually equal
  interpolations written in two places still evaluate twice.

Other choices that follow from "one expression":

- **Determinism**: no random names in the output (v1 used `secrets`), so
  golden tests and reproducible builds are possible.
- **Static resolution**: prefixed names and relative IRIs resolve at
  transpile time against the lexically scoped tables; `@prefix` has *block*
  scope (declaration to end of enclosing suite, restored on exit). Runtime
  `__namespaces__` bindings exist only for serialisation and introspection.
- **MicroPython subset**: emissions only use assignments, calls, attributes,
  tuples and constants (an AST whitelist test enforces it); the generated
  code never introduces f-strings, walrus or lambdas.
