# Linked-Data Python

**Python, with the Semantic Web in its syntax.** IRIs, prefixed names, RDF
literals, SPARQL variables and whole graphs written in Turtle's notation are
expressions of the language — interpolated with arbitrary Python, transpiled to
plain Python, running on rdflib.

![](ldpyIcon.png)

```text
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@base <http://example.org/building/> .

def observation(sensor, value):
    return g{ f<sensor/{sensor}> a sosa:Sensor ;
                  sosa:madeObservation [ sosa:hasSimpleResult {value} ] }
```

The language also reads and queries, writes into a current graph, and turns
rows into triples:

```text
@prefix ex: <http://example.org/> .
@graph as kg
for @bindings in csv.DictReader(f):             # any iterable of mappings
    +{ e<http://example.org/{?id}> ex:value ?v }

for s, v in m{ ?s ex:value ?v }:                # a graph pattern, no engine
    ...
rows = s{ SELECT ?s WHERE { ?s ex:value ?v } }  # all of SPARQL, checked early
adult = e{ ?age >= 18 && BOUND(?name) }         # deferred, over bindings
```

`.ldpy` files are **transpiled to plain Python** by an *island parser*: the
Python is copied verbatim — every valid Python file is a valid ldpy file,
returned byte-identical — and only the RDF islands are parsed and rewritten.
The transpiler is ~1 500 lines with no parsing dependency and sustains
56 000–110 000 source lines/s depending on island density.

## Quick start

```text
git clone git@gitlab.emse.fr:maxime.lefrancois/linked-data-python.git
cd linked-data-python && pip install -e .       # or: pip install -e .[lsp,debug]

ldpy program.ldpy             # run a file
ldpy                          # interactive console
ldpy-lsp                      # language server (LSP, stdio)
ldpy-debug program.ldpy       # debug via the shadow .py + debugpy
```

From Python: `import ldpy; ldpy.install()` then `import yourmodule` finds
`yourmodule.ldpy` on `sys.path`.

## Documentation

Read it at [`docs/`](docs/README.md) — start with the
[home page](docs/README.md) for an overview, then:

- **Tutorials** — [first steps](docs/tutorials/getting-started.md), then
  [build a knowledge graph](docs/tutorials/build-a-knowledge-graph.md) from
  tabular data.
- **How-to guides** — [run & import](docs/how-to/run-and-import.md),
  [build graphs from tables](docs/how-to/build-graphs-from-tables.md),
  [read and query](docs/how-to/query-a-graph.md),
  [migrate from rdflib](docs/how-to/migrate-from-rdflib.md),
  [VS Code](docs/how-to/use-vscode.md), [debugging](docs/how-to/debug.md),
  [language server](docs/how-to/language-server.md),
  [highlighting](docs/how-to/highlight-ldpy.md).
- **Reference** — [the language](docs/reference/language/index.md), one page
  per island family; [SPARQL expressions](docs/reference/sparql-expressions.md);
  [CLI](docs/reference/cli.md); [Python API](docs/reference/api.md);
  [language map formats](docs/reference/language-map.md).
- **Explanation** — [why](docs/explanation/why.md),
  [what real RDF code does](docs/explanation/what-real-code-does.md) (the
  corpus study that drove the language's second wave),
  [designing the syntax](docs/explanation/designing-the-syntax.md),
  [island parsing](docs/explanation/island-parsing.md),
  [emission & semantics](docs/explanation/emission-and-semantics.md),
  [tooling](docs/explanation/tooling.md),
  [how this is tested](docs/explanation/how-it-is-tested.md).

Every `ldpy` and `python` block in the documentation is executed by the test
suite, and its assertions are the test.

## Tooling

- **VS Code extension** (`vscode-ldpy`): highlighting (TextMate + LSP semantic
  tokens), diagnostics as you type, completion/hover/definition, run and debug.
- **Language server**: dependency-free, LSP over stdio; delegates Python
  intelligence to an unmodified `pylsp` through the language map.
- **Debugging**: `.ldpy` code compiles in `.ldpy` coordinates, so `pdb` and
  `debugpy` work directly; `ldpy.build` also materialises real `.py` shadow
  files with JSON and Source Map v3 maps.
- **Highlighting anywhere else**: the package registers a Pygments lexer built
  on the language map — MkDocs, Sphinx and `pygmentize` colour `.ldpy` with no
  further setup.
- **Benchmark harness** (`bench/`): seeded random program generator and
  reproducible throughput campaigns.

## Project

- Tests: `python -m pytest tests/ -q` — byte-identity over the CPython standard
  library, golden transpilation, RDF isomorphism against rdflib as an oracle,
  LSP end to end, executable documentation.
- Licence: MIT. Author: Maxime Lefrançois (Mines Saint-Étienne).
- The 2023 ANTLR-based release (v1, PyPI 0.0.4) is preliminary work, superseded
  by this island-parsing rewrite (the `main` branch of this repository; the 2023
  code remains on the legacy gitlab.com/coswot/ldpy).
