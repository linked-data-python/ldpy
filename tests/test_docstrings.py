"""La documentation du code est un invariant testé : tout module, classe,
méthode ou fonction PUBLIC des paquets v2 porte une docstring.

(La chaîne v1 héritée — ldpy/rewriter, ldpy/grun, ldpy/ldpy.py, ldpy/sparql —
est exclue : elle est conservée comme archive.)"""

import ast
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODULES = [
    "ldpy/__init__.py", "ldpy/__main__.py", "ldpy/runtime.py",
    "ldpy/importer.py", "ldpy/build.py", "ldpy/debug.py", "ldpy/console.py",
    "ldpy/transpiler/__init__.py", "ldpy/transpiler/core.py",
    "ldpy/transpiler/errors.py", "ldpy/transpiler/linemap.py",
    "ldpy/lsp/__init__.py", "ldpy/lsp/server.py", "ldpy/lsp/backend.py",
    "ldpy/lsp/rpc.py", "ldpy/lsp/translate.py",
    "bench/__init__.py", "bench/generator.py", "bench/run.py",
]

# dunder/protocole : la docstring de la classe suffit
EXEMPT_NAMES = {"__init__", "__new__", "__repr__", "__str__", "main"}


def _missing(path):
    with open(os.path.join(REPO, path), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    gaps = []
    if not ast.get_docstring(tree):
        gaps.append("(module)")

    def visit(node, prefix, public):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                name = child.name
                pub = public and not name.startswith("_")
                qual = prefix + name
                if isinstance(child, ast.ClassDef):
                    if pub and not ast.get_docstring(child):
                        gaps.append(qual)
                    visit(child, qual + ".", pub)
                else:
                    if pub and name not in EXEMPT_NAMES \
                            and not ast.get_docstring(child):
                        gaps.append(qual)
    visit(tree, "", True)
    return gaps


@pytest.mark.parametrize("path", MODULES)
def test_public_api_documented(path):
    gaps = _missing(path)
    assert not gaps, "docstrings manquantes dans %s : %s" % (path, gaps)


def test_version_comes_from_the_installed_distribution():
    """Two copies of a version number drift, and this one did: a 0.2.0
    install announced itself as 0.1.0.dev0 in the editor status bar."""
    import ldpy
    from importlib.metadata import version
    assert ldpy.__version__ == version("linked-data-python")


def test_probe_reports_that_same_version():
    """`--probe` is what the VS Code status bar shows."""
    from ldpy.debug import probe
    import ldpy
    assert probe()["version"] == ldpy.__version__
