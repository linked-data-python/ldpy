# How to format `.ldpy` code

`ldpy` ships a formatter. It has **no opinion about Python** — it delegates to
[`black`](https://black.readthedocs.io/) — and a deliberately small opinion
about islands: it normalises their edges and copies their bodies verbatim.

```text
pip install "linked-data-python[format]"
```

## In an editor

The [language server](language-server.md) implements
`textDocument/formatting`, so **Format Document** and *format on save* work in
any LSP editor with no extra setup. In VS Code:

```json
{
  "[ldpy]": { "editor.formatOnSave": true },
  "ldpy.lineLength": 88
}
```

If `black` is not installed in the interpreter running the server, the server
does not advertise the capability at all — the editor will say the language
has no formatter, rather than failing on every save.

## On the command line

```text
ldpy-format src/                  # format every .ldpy under src/, in place
ldpy-format --check src/          # exit 1 if something is not formatted (CI)
ldpy-format --diff app.ldpy       # show what would change
ldpy-format -l 100 app.ldpy       # another line length
```

`python -m ldpy.formatter` is the same entry point.

## From Python

```python
from ldpy.formatter import format_source
assert format_source("@prefix ex: <http://e/> .\nx=1\ng=g{ex:s ex:p 1}\n") == (
    "@prefix ex: <http://e/> .\n" "x = 1\n" "g = g{ ex:s ex:p 1 }\n"
)
```

`format_file(path, write=True)` does the same on a file and returns
`(text, changed)`.

A file that does not transpile is **not** formatted: `format_source` raises
`LdpySyntaxError` and the editor gets no edit. A formatter that guesses is a
formatter that loses work.

## What it does, exactly

Python is formatted by black, to the byte. Then, for each island:

| | before | after |
|---|---|---|
| padding inside the braces | `g{ex:s ex:p 1}` | `g{ ex:s ex:p 1 }` |
| an empty island | `g{}` | `g{ }` |
| closed-grammar declarations | `@prefix  ex:   <http://e/>  .` | `@prefix ex: <http://e/> .` |
| trailing spaces | `ex:v 1 ;␣␣` | `ex:v 1 ;` |
| continuation lines | follow their statement's indentation, keeping the author's alignment |

**The body of a graph or a query is not rewritten.** Turtle has no canonical
layout, and a graph is often aligned by hand to show its structure — subjects
in a column, predicates lined up. That alignment is information, and the
formatter leaves it alone:

```ldpy
@prefix ex: <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@graph as kg
+{ ex:s1 ex:room ex:R101 ; ex:value "21.5"^^xsd:double .
   ex:s2 ex:room ex:R101 ; ex:value "19.0"^^xsd:double }
assert len(kg) == 4
```

The reasoning, and what would be needed to go further, is in the design record
`DESIGN_CHOICES/ldpy/024`.

## What it guarantees

Three properties, checked on every `.ldpy` example and every code block in
this documentation:

1. **A file with no islands is formatted exactly as `black` would.** The
   formatter never diverges from the host — the same discipline as
   [R3](../explanation/why.md).
2. **Formatting twice changes nothing more than formatting once.**
3. **The meaning does not move**: the transpiled Python has the same AST
   before and after, to the byte — with one stated exception, whitespace
   inside the text of an `s{ }` query, which SPARQL ignores by definition.
