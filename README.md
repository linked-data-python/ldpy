# Linked-Data Python

Linked-Data Python (**ldpy**) extends the syntax of Python with the
primitives of the Semantic Web: prefix and base declarations, IRIs, prefixed
names, RDF literals, SPARQL-style variables, and RDF graphs written in
Turtle's own notation — interpolated with arbitrary Python expressions.

![](ldpyIcon.png)

```text
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@base <http://example.org/building/> .

def observation(sensor, value):
    return g{ f<sensor/{sensor}> a sosa:Sensor ;
                  sosa:madeObservation [ sosa:hasSimpleResult {value} ] }
```

`.ldpy` files are **transpiled to plain Python** by an *island parser*: the
Python is copied verbatim (every valid Python file is a valid ldpy file,
returned byte-identical), only the RDF islands are parsed and rewritten. The
transpiler is ~1 500 lines with no parsing dependency and sustains
56 000–110 000 source lines/s depending on island density.

## Quick start

```text
git clone git@gitlab.emse.fr:maxime.lefrancois/linked-data-python.git
cd linked-data-python
pip install rdflib                      # runtime backend
python -m ldpy program.ldpy             # run a file
python -m ldpy                          # interactive console
python -m ldpy.lsp                      # language server (LSP, stdio)
python -m ldpy.debug program.ldpy       # debug via the shadow .py + debugpy
```

From Python: `import ldpy; ldpy.install()` then `import yourmodule` finds
`yourmodule.ldpy` on `sys.path`.

## Documentation

The documentation lives in [`docs/`](docs/README.md), organised by the
[Diátaxis](https://diataxis.fr/) framework:

- **[Tutorial](docs/tutorials/getting-started.md)** — first steps, hands on.
- **How-to guides** — [run & import](docs/how-to/run-and-import.md),
  [VS Code](docs/how-to/use-vscode.md), [debugging](docs/how-to/debug.md),
  [language server](docs/how-to/language-server.md).
- **Reference** — [the language](docs/reference/language.md) (islands,
  disambiguation, scoping), [CLI](docs/reference/cli.md),
  [Python API](docs/reference/api.md),
  [language map formats](docs/reference/language-map.md).
- **Explanation** — [island parsing](docs/explanation/island-parsing.md),
  [emission & semantics](docs/explanation/emission-and-semantics.md),
  [tooling architecture](docs/explanation/tooling.md).

Every code block in the documentation is executed by the test suite.

## Tooling

- **VS Code extension** (`vscode-ldpy`): highlighting (TextMate + LSP
  semantic tokens), diagnostics as you type, completion/hover/definition,
  run and debug commands.
- **Language server**: dependency-free, LSP over stdio ; delegates Python
  intelligence to an unmodified `pylsp` through the language map.
- **Debugging**: `ldpy.build` materialises real `.py` shadow files (+ language
  maps, JSON and Source Map v3) ; `debugpy` runs on them unchanged.
- **Benchmark harness** (`bench/`): seeded random program generator and
  reproducible throughput campaigns.

## Project

- Tests: `python -m pytest tests/ -q` (330+ tests: byte-identity over the
  CPython stdlib, golden transpilation, RDF isomorphism against RDFLib as an
  oracle, LSP end-to-end, executable documentation).
- Licence: MIT. Author: Maxime Lefrançois (Mines Saint-Étienne).
- The 2023 ANTLR-based release (v1, PyPI 0.0.4) is preliminary work,
  superseded by this island-parsing rewrite (the `main` branch of this
  repository; the 2023 code remains on the legacy gitlab.com/coswot/ldpy).
