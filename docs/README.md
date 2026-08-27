# Linked-Data Python — documentation

This documentation follows the [Diátaxis](https://diataxis.fr/) framework:
four kinds of documents for four kinds of needs.

| I want to… | Go to |
|---|---|
| **Learn** ldpy from zero, hands on | [Tutorial: getting started](tutorials/getting-started.md) |
| **Get something done** | How-to guides: [run & import](how-to/run-and-import.md) · [VS Code](how-to/use-vscode.md) · [debug](how-to/debug.md) · [language server](how-to/language-server.md) |
| **Look something up** | Reference: [the language](reference/language.md) · [SPARQL expressions](reference/sparql-expressions.md) · [command line](reference/cli.md) · [Python API](reference/api.md) · [language map](reference/language-map.md) |
| **Understand the design** | Explanation: [island parsing](explanation/island-parsing.md) · [emission & semantics](explanation/emission-and-semantics.md) · [tooling architecture](explanation/tooling.md) |

The [explanation pages](explanation/island-parsing.md) give the design
rationale; a companion academic article gives the full account.

**Contract with the reader**: every `ldpy` and `python` code block in these
pages is extracted and executed by the test suite (`tests/test_docs.py`).
If a snippet is on this site, it runs.
