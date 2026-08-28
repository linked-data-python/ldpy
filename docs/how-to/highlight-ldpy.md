# How to highlight `.ldpy` code

ldpy ships two highlighters, for two worlds. Both are generated from, or driven
by, the transpiler's own view of the language, so neither can drift from it.

| Where | What | Kept in sync by |
|---|---|---|
| VS Code, and anything reading TextMate grammars | `vscode-ldpy/syntaxes/ldpy.tmLanguage.json` | **generated** from VS Code's MagicPython; a test checks character-level parity on pure Python |
| HTML: MkDocs, Sphinx, `pygmentize`, any Pygments consumer | `ldpy.pygments_lexer.LdpyLexer` | **reads the language map** — it colours exactly where the transpiler sees an island |

Pygments is an **optional** dependency: `pip install linked-data-python[highlight]`
(the `docs` extra brings it too). Nothing in ldpy imports it; Pygments loads
the lexer through an entry point when it is installed.

## In MkDocs (this site)

Install the package with its highlighting extra in the docs environment; the
lexer registers itself as a Pygments plugin through an entry point, so nothing
else is needed:

```text
pip install linked-data-python[highlight]      # or: pip install -e .[docs]
```

Then fence your code with `ldpy` and highlight it as usual:

````text
```ldpy
@prefix ex: <http://example.org/> .
g = g{ ex:s ex:p 1 }
```
````

With `mkdocs-material`, that is the whole configuration:

```text
markdown_extensions:
  - pymdownx.highlight
  - pymdownx.superfences
```

## In Sphinx

```text
.. code-block:: ldpy

   @prefix ex: <http://example.org/> .
   g = g{ ex:s ex:p 1 }
```

`highlight_language = "ldpy"` makes it the default for a whole document.

## On the command line

```text
pygmentize -l ldpy program.ldpy                 # to the terminal
pygmentize -l ldpy -f html -O full -o out.html program.ldpy
```

## From Python

```python
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name

html = highlight("@prefix ex: <http://e/> .\ng = g{ ex:s ex:p 1 }\n",
                 get_lexer_by_name("ldpy"), HtmlFormatter())
assert "class=" in html
```

## How it works, and what that buys

The lexer transpiles the source and reads the resulting **language map** — an
ordered partition of the file into `copy` and `island:KIND` segments — and then
delegates all the actual tokenising to Pygments' own lexers:

| Text | Lexer |
|---|---|
| `copy` segments, and every `{expr}` interpolation | `PythonLexer` |
| `@prefix` / `@base` — Turtle's own directives | `TurtleLexer` |
| `g{ }`, `m{ }`, `+{ }`, `-{ }`, `s{ }`, `e{ }` bodies | `SparqlLexer` |

A graph or pattern body is Turtle *with variables*, which is exactly SPARQL's
triples block — `TurtleLexer` rejects `?s`, `SparqlLexer` does not. What is
written in ldpy is only what no existing lexer can know: where the islands are,
the ldpy-only declarations (`@graph`, `@bindings`, prefix imports), and the
*masking* that lets a delegated lexer see a well-formed document — each
ldpy-specific region is replaced by a same-length placeholder that is a valid
term where it stands, and the real text is lexed back in at that position.

Three consequences:

- **It cannot disagree with the transpiler.** A change to a disambiguation rule
  changes the colouring with no edit to the lexer. `a<b>c` is coloured as a
  chained comparison because the transpiler treats it as one.
- **`s{ }` groups and interpolations are told apart correctly**, by asking the
  transpiler's own oracle: balanced content is an interpolation *iff* it
  transpiles and then compiles as a Python expression.
- **Pure Python is coloured exactly as Python** — token for token, which is a
  test.

Only standard Pygments token types are emitted, following the conventions of
`pygments.lexers.rdf`, so every Pygments style works with no extra stylesheet.

When the source does not transpile — an editor buffer mid-keystroke, an
illustrative snippet — the lexer falls back to plain Python rather than
guessing. Highlighting degrades; it never fails.
