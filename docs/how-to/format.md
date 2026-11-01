# How to format `.ldpy` code

`ldpy` ships a formatter. It has **no opinion about Python** — it delegates to
[`black`](https://black.readthedocs.io/) — and lays out the islands the way
black lays out Python: on one line while the line fits, else in hanging
indent, in steps of four.

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

Python is formatted by black, to the byte. Then each island is laid out
again from its tokens — the author's spacing does not count.

**A Turtle island** (`g{ }`, `+{ }`, `-{ }`, `m{ }`) stays on one line if the
line fits:

```ldpy
@prefix ex: <http://example.org/> .
@graph as kg
+{ ex:s1 ex:room ex:R101 ; ex:value 21.5 }
```

and is exploded otherwise — subject on the first line, one predicate per
line, a blank node opened at the end of its line and closed on its own:

```ldpy
@prefix ex: <http://example.org/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@graph as kg
+{
    ex:alice a foaf:Person ;
        foaf:name "Alice Liddell" ;
        foaf:knows [
            a foaf:Person ;
            foaf:name "The White Rabbit" ;
            foaf:mbox <mailto:white.rabbit@wonderland.example>
        ]
}
```

**A SPARQL island** (`s{ }`) always takes the canonical layout: one clause
per line, one triple pattern per line, keywords in capitals, braces in
hanging indent.

```ldpy
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@graph as kg
min_age = 30
rows = s{
    SELECT ?name
    WHERE {
        ?p foaf:name ?name ;
            foaf:age ?age .
        FILTER (?age >= {min_age})
    }
    ORDER BY ?name
}
```

Declarations (`@prefix`, `@base`, `@graph`, `@bindings`) are normalised to
single spaces.

**Keeping a layout of your own.** A graph aligned by hand to show its
structure keeps it with `# fmt: skip` at the end of its last line, or inside
a `# fmt: off` / `# fmt: on` region — black's own markers. Its body is then
copied as written, and shifted with its statement:

```ldpy
@prefix ex: <http://example.org/> .
@graph as kg
+{ ex:s1 ex:room ex:R101 ; ex:value 21.5 .
   ex:s2 ex:room ex:R101 ; ex:value 19.0 }  # fmt: skip
assert len(kg) == 4
```

An island holding a comment is copied as written too: a comment has no
place in a layout rebuilt from tokens.

The reasoning is in design record `ldpy/024`, in this repository's
`steering/design/`.

## What it guarantees

Three properties, checked on every `.ldpy` example and every code block in
this documentation:

1. **A file with no islands is formatted exactly as `black` would.** The
   formatter never diverges from the host — the same discipline as
   [R3](../explanation/why.md).
2. **Formatting twice changes nothing more than formatting once.**
3. **The meaning does not move**: the transpiled Python has the same AST
   before and after, to the byte — with one stated exception, the text of
   an `s{ }` query, compared token by token, since SPARQL ignores its
   whitespace and the case of its keywords.

The third is also checked at every run: the formatter transpiles its own
result and compares it with the same file formatted with every island body
copied as written. If they differ, the file is returned that second way —
a layout bug can cost you a pretty island, never a correct program.
