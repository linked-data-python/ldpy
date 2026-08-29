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
git clone https://github.com/linked-data-python/ldpy.git
cd linked-data-python && pip install -e .       # or: pip install -e .[lsp,debug]

ldpy program.ldpy             # run a file
ldpy                          # interactive console
ldpy-lsp                      # language server (LSP, stdio)
ldpy-debug program.ldpy       # debug via the shadow .py + debugpy
```

From Python: `import ldpy; ldpy.install()` then `import yourmodule` finds
`yourmodule.ldpy` on `sys.path`.

## Documentation

Read it at **<https://linked-data-python.readthedocs.io/>** — start with the
home page for an overview, then:

- **Tutorials** — [first steps](https://linked-data-python.readthedocs.io/en/latest/tutorials/getting-started/), then
  [build a knowledge graph](https://linked-data-python.readthedocs.io/en/latest/tutorials/build-a-knowledge-graph/) from
  tabular data.
- **How-to guides** — [run & import](https://linked-data-python.readthedocs.io/en/latest/how-to/run-and-import/),
  [build graphs from tables](https://linked-data-python.readthedocs.io/en/latest/how-to/build-graphs-from-tables/),
  [read and query](https://linked-data-python.readthedocs.io/en/latest/how-to/query-a-graph/),
  [migrate from rdflib](https://linked-data-python.readthedocs.io/en/latest/how-to/migrate-from-rdflib/),
  [VS Code](https://linked-data-python.readthedocs.io/en/latest/how-to/use-vscode/), [debugging](https://linked-data-python.readthedocs.io/en/latest/how-to/debug/),
  [language server](https://linked-data-python.readthedocs.io/en/latest/how-to/language-server/),
  [highlighting](https://linked-data-python.readthedocs.io/en/latest/how-to/highlight-ldpy/).
- **Reference** — [the language](https://linked-data-python.readthedocs.io/en/latest/reference/language/), one page
  per island family; [SPARQL expressions](https://linked-data-python.readthedocs.io/en/latest/reference/sparql-expressions/);
  [CLI](https://linked-data-python.readthedocs.io/en/latest/reference/cli/); [Python API](https://linked-data-python.readthedocs.io/en/latest/reference/api/);
  [language map formats](https://linked-data-python.readthedocs.io/en/latest/reference/language-map/).
- **Explanation** — [why](https://linked-data-python.readthedocs.io/en/latest/explanation/why/),
  [what real RDF code does](https://linked-data-python.readthedocs.io/en/latest/explanation/what-real-code-does/) (the
  corpus study that drove the language's second wave),
  [designing the syntax](https://linked-data-python.readthedocs.io/en/latest/explanation/designing-the-syntax/),
  [island parsing](https://linked-data-python.readthedocs.io/en/latest/explanation/island-parsing/),
  [emission & semantics](https://linked-data-python.readthedocs.io/en/latest/explanation/emission-and-semantics/),
  [tooling](https://linked-data-python.readthedocs.io/en/latest/explanation/tooling/),
  [how this is tested](https://linked-data-python.readthedocs.io/en/latest/explanation/how-it-is-tested/).

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

## Design records

Every non-trivial choice in this repository is written down, one file per
decision, in the [`pilotage`](https://github.com/linked-data-python/pilotage) repository. Comments and docs
cite them by identifier — `ldpy/024`, `vscode/103` — which resolves to
[`design/`](https://github.com/linked-data-python/pilotage/tree/main/design).
