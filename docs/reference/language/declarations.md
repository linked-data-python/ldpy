# Declarations and scope

Four declarations set the context that the surrounding islands read:
`@prefix` and `@base` (resolved by the transpiler), `@graph` and `@bindings`
(runtime values with lexical scope). All four share one scoping rule and
accept Python's scope modifiers.

## `@prefix` — bind a prefix

Turtle's own syntax, dot included. The declaration is a *statement*; it
produces no value.

```ldpy
@prefix ex: <http://example.org/ns#> .
@prefix schema: <https://schema.org/> .
assert str(ex:Thing) == "http://example.org/ns#Thing"
assert str(schema:Person) == "https://schema.org/Person"
```

The IRI may itself be computed, with a [formatted IRI](terms.md#formatted-iris-f).
The prefix is then resolved at run time rather than inlined — the only
observable difference is that it cannot be a compile-time constant:

```ldpy
host = "example.org"
@prefix dyn: f<http://{host}/ns#> .
assert str(dyn:x) == "http://example.org/ns#x"
```

### `as NAME` — when the namespace must survive as an object

A prefix is lexical: it has no run-time object, and `ex:` on its own is never
a value. That is deliberate — it keeps prefixed names checkable when the file
is transpiled — but some code genuinely needs the `Namespace` *object*: to
bind it on a graph it manages, to export it, to put it in a registry. `as`
binds that object to a Python name, without changing what `ex:` means:

```ldpy
from rdflib import Graph
@prefix ex: <http://example.org/ns#> as EX .
registry = {"ex": EX}
assert str(EX) == "http://example.org/ns#"
assert EX.Thing == ex:Thing
g = Graph()
g.bind("ex", EX)
```

The name is an ordinary Python binding, so it follows Python's scope, and
`global` / `nonlocal` in front of the declaration widen it like any other
(see [scope modifiers](#scope-modifiers-global-and-nonlocal)). Choosing a
name that differs from the prefix — `EX` for `ex:` — is the usual convention
and avoids the warning the transpiler raises when a declared prefix and a
Python name coincide.

It works on a computed prefix as well, which is the case the corpus met
first:

```ldpy
host = "example.org"
@prefix dyn: f<http://{host}/ns#> as DYN .
assert str(DYN) == "http://example.org/ns#"
assert DYN["x"] == dyn:x
```

You rarely need it. Reach for `as` only when the object itself must travel:
a `Namespace` that merely *produces* IRIs needs nothing, since the `URIRef`s
it produces are ordinary values (record ldpy/027).

## `@base` — set the base IRI

```ldpy
@base <http://example.org/data/> .
assert str(<sensor/1>) == "http://example.org/data/sensor/1"
```

`@base` affects relative IRIs and `f<...>`, at transpile time when it can and
at run time when the base is itself computed. Unlike prefixes, it is **not**
exported to importing modules.

## Block scope

A declaration holds **from its line to the end of the enclosing suite** — the
body of an `if`, `for`, `def` or `class`; the rest of the file at top level.
Leaving the block restores the previous binding. This is lexical, and
resolution happens at transpile time: run-time control flow does not change
which IRI a prefixed name denotes.

```ldpy
@prefix p: <http://outer/> .
def f():
    @prefix p: <http://inner/> .
    return p:x                       # http://inner/x
inner, outer = f(), p:x              # outer = http://outer/x
assert str(outer) == "http://outer/x" and str(inner) == "http://inner/x"
```

Two situations raise a transpiler **warning** rather than an error: using a
prefix after the block that declared it has ended (the text is then left as
Python, and Python will complain in its own way), and redeclaring an
already-used prefix at the same level with a different IRI.

Why block scope, and not file scope as in Turtle? Because the enclosing
construct is Python's, and a declaration that outlived its suite would be the
only thing in the file that did — see
[the design record `ldpy/004`](https://github.com/linked-data-python/pilotage/blob/main/design/ldpy/004-semantique-prefix-base.md).

## Prefixes across modules

Every **module-level** `@prefix` is exported; a prefix declared inside a
function stays private, because block scope says so. On the importing side, a
prefixed name in the import list imports a prefix. The form is illegal Python,
so no name is captured and nothing else changes:

```text
from myproject.vocab import something, brick:, unit: as u:
```

The regime is uniform and **dynamic**: the transpiler never reads the imported
module. The import statement declares the prefix *lexically*, which is all the
transpiler needs; `brick:Class` then resolves at run time through the imported
namespace binding. One consequence worth knowing: an IRI that changes in
`vocab.ldpy` changes for every importer, with no stale inlined copy.

`import m` and `from m import *` import no prefixes. `@base` is not exported.
Declaring `__namespaces__` in `__all__` is refused at transpile time.

The measured need behind this feature — 1 271 namespace imports across
65 independent repositories — is in
[what real RDF code does](../../explanation/what-real-code-does.md#namespaces-are-shared-by-hand).

## `@graph` and `@bindings`

Both declare a *runtime* context with the same block scope as `@prefix`, and
both are described where they are used:

- [`@graph`](current-graph.md) — the graph that `+{ }`, `-{ }`, `m{ }` and
  `s{ }` read or write when not given one.
- [`@bindings`](bindings.md) — the solution mapping that a graph template and
  a deferred expression are instantiated against.

## Scope modifiers: `global` and `nonlocal`

The four declarations accept Python's scope modifiers, with Python's exact
semantics: `global` installs at module scope, `nonlocal` rebinds the nearest
enclosing declaration and is an error if there is none. The form is illegal
Python (`global` must be followed by names), so nothing is repurposed.

```ldpy
@prefix ex: <http://example.org/> .
for cand in range(3):
    if cand == 1:
        global @graph as chosen      # survives the break, and the loop body
        break
+{ ex:s ex:p {cand} }
assert len(chosen) == 1
```

The rule for what these do is short: **whatever Python does**. There is no
warning on `global @prefix`, for the same reason there is none on
`global x; x = 1`.
