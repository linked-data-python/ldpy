# Emission and semantics: an island is one expression

Every island compiles to **one Python expression** calling a small runtime
façade (`import ldpy.runtime as _ldpy_`). The alternative — hoisting graph
construction into statements before the current one — is not a style choice; it
is semantically wrong three times over.

1. **It breaks evaluation order.** `cond or g{ ... {f()} ... }` would call
   `f()` even when `cond` is true.
2. **It forbids islands exactly where they are useful** — lambdas,
   comprehensions, default arguments — because there is no "before" to hoist
   to.
3. **It smears one source line over many generated lines**, which ruins the
   language map and therefore the [tooling](tooling.md).

```ldpy
@prefix ex: <http://example.org/> .
calls = []
def f():
    calls.append(1)
    return 1
cond = True
result = cond or g{ ex:s ex:p {f()} }
assert calls == []                    # f() was never called
```

## How a graph becomes an expression

A graph is flattened at transpile time into
`_ldpy_.graph(ns, base, (s, p, o), ...)` with two kinds of placeholder.

**`bn(i)` — the *i*-th blank node of the island**, instantiated fresh at each
evaluation, exactly as re-parsing a Turtle document would.

**`slot(i, expr)` / `slot(i)` — a shared interpolated term.** The subject of a
predicate-object list appears in several triples; if it is an interpolation,
repeating its expression would evaluate it once per triple. The expression is
emitted at its first occurrence and referenced afterwards:

```ldpy
@prefix ex: <http://example.org/> .
n = [0]
def next_id():
    n[0] += 1
    return "id%d" % n[0]
g = g{ ex:{next_id()} ex:p 1 ; ex:q 2 ; ex:r 3 }
assert n[0] == 1 and len(g) == 3      # one subject, evaluated once
```

Identity is per **source occurrence**: two textually equal interpolations
written in two places are two expressions, and evaluate twice. That is the
rule a reader can apply without knowing the implementation.

## What follows from "one expression"

**Determinism.** No random names in the output — the 2023 version used
`secrets` — so golden tests and reproducible builds are possible at all.

**Static resolution.** Prefixed names and relative IRIs resolve at transpile
time against lexically scoped tables. `@prefix` has *block* scope: from the
declaration to the end of the enclosing suite, restored on exit. The run-time
`__namespaces__` mapping exists for serialisation and introspection, and for
[prefixes imported from another module](../reference/language/declarations.md#prefixes-across-modules),
which by construction cannot be known at transpile time.

**A MicroPython-compatible subset.** Emissions use only assignments, calls,
attributes, subscripts, tuples and constants — an AST whitelist test enforces
it. The generated code never introduces an f-string, a walrus or a lambda;
f-strings written in your source pass through unchanged. The practical
consequence is worth stating: ldpy runs on the newest Python, and a file that
stays within the MicroPython subset stays there after transpilation.

**A statement where a statement is meant.** `+{ }` and `-{ }` emit
`add_to(...)` / `remove_from(...)`, never `+=`. That is what makes a read-only
property or a module global writable with no `global` declaration and no
`__iadd__` dance — a limitation the corpus study ran into repeatedly.

## Lazy materialisation

Graphs emitted by `g{ }` keep their triples in a pending list and populate the
rdflib store only at first real access. `target += g{ ... }` therefore performs
a **single** store insertion instead of one per triple, and a sum of templates
is O(total) rather than O(n²). Union semantics is preserved: duplicates are
removed at the flush.

This is invisible except in one respect — the value is an `rdflib.Graph`
subclass, not a `Graph` — and it is where the largest runtime speed-ups came
from. The measurements are in `OPTIMIZATION.md`.
