"""Linked-Data Python (ldpy) v2.

Transpileur « island parsing » : le Python est recopié tel quel, les îlots RDF
(@prefix, @base, IRIs, noms préfixés, littéraux RDF, variables, graphes g{...})
sont réécrits en expressions Python s'appuyant sur ldpy.runtime.

La chaîne historique ANTLR (v1) reste accessible via le paquet ldpy.rewriter
mais n'est plus importée par défaut.
"""

from ldpy.transpiler import transpile, LdpySyntaxError, LdpyWarning
from ldpy.importer import install, uninstall, install_excepthook

__version__ = "0.1.0.dev0"
__date__ = "2026-08-26"


def transform_source(source, filename="<ldpy>"):
    """Compat v1 simplifiée : retourne (code_python, prefixes, map)."""
    result = transpile(source, filename)
    return result.code, result.prefixes, result.map


def Coercion(rules):
    """Politique de conversion Python -> RDF (fiche 020) — voir
    ldpy.runtime.Coercion ; exposée ici comme API publique."""
    from ldpy.runtime import Coercion as _C
    return _C(rules)


def instantiateBGP(input, solutionMappings, initialGraph=None):
    """Instancie un patron de graphe avec des solution mappings
    (réexport de ldpy.runtime.instantiateBGP, compat v1)."""
    from ldpy.runtime import instantiateBGP as _f
    return _f(input, solutionMappings, initialGraph)
