"""Linked-Data Python (ldpy) v2.

An "island parsing" transpiler: Python is copied through untouched, the RDF
islands (@prefix, @base, IRIs, prefixed names, RDF literals, variables,
graphs g{...}) are rewritten into Python expressions built on ldpy.runtime.

The historical ANTLR chain (v1) is still reachable through the ldpy.rewriter
package but is no longer imported by default.
"""

from ldpy.transpiler import transpile, LdpySyntaxError, LdpyWarning
from ldpy.importer import install, uninstall, install_excepthook

__version__ = "0.1.0.dev0"
__date__ = "2026-08-26"


def transform_source(source, filename="<ldpy>"):
    """Simplified v1 compatibility: returns (python_code, prefixes, map)."""
    result = transpile(source, filename)
    return result.code, result.prefixes, result.map


def Coercion(rules):
    """Politique de conversion Python -> RDF (fiche 020) — voir
    ldpy.runtime.Coercion; exposed here as public API."""
    from ldpy.runtime import Coercion as _C
    return _C(rules)


def instantiateBGP(input, solutionMappings, initialGraph=None):
    """Instantiate a graph template with solution mappings
    (re-export of ldpy.runtime.instantiateBGP, v1 compatibility)."""
    from ldpy.runtime import instantiateBGP as _f
    return _f(input, solutionMappings, initialGraph)
