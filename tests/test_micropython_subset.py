"""Compatibilité MicroPython du code ÉMIS (voir docs/explanation/).

Contrat : on peut se passer de MicroPython dans le cas général, mais le code
généré par la transpilation doit rester compatible MicroPython.

Vérification à deux niveaux :
1. les remplacements d'îlots et le prélude ne produisent que des nœuds AST
   d'une liste blanche (constructions Python 3.4, toutes dans MicroPython) ;
2. le fichier généré entier parse avec `ast.parse(feature_version=...)` :
   (3, 4) quand la source n'utilise rien de plus récent, la version de la
   source sinon — la transpilation n'introduit JAMAIS de construction plus
   récente que ce que la source contenait déjà.
"""

import ast

import pytest

from ldpy.transpiler import transpile

P = "@prefix ex: <http://example.org/ns#> .\n"

# ce que les émissions d'îlots + prélude ont le droit de produire
EMISSION_WHITELIST = {
    "Module", "Import", "alias", "Assign", "Expr", "Call", "Attribute",
    "Name", "Constant", "Tuple", "keyword", "Subscript", "Dict",
    "Load", "Store",
}

ISLAND_ONLY_SOURCES = [
    P + "x = ex:Sensor\n",
    P + "x = <http://e/a>\n",
    "x = ?var\n",
    'x = "a"@en\n',
    P + 'x = "1"^^ex:t\n',
    "i = 0\nx = f<http://e/{ i }>\n",
    "x = ?{ 40 + 2 }\n",
    P + "x = g{ ex:s a ex:C ; ex:p 1, 2 ; ex:q [ ex:r ( 1 2 ) ] }\n",
    P + "s = 'a'\nx = g{ ex:{s} ex:p {s} ; ex:q {s} }\n",   # slots partagés
    "@base <http://e/> .\nx = <rel>\n",
]


@pytest.mark.parametrize("src", ISLAND_ONLY_SOURCES)
def test_emitted_nodes_stay_in_whitelist(src):
    code = transpile(src).code
    seen = set()
    for node in ast.walk(ast.parse(code)):
        name = type(node).__name__
        # les nœuds venant du Python hôte de ces snippets minimaux
        if name in ("BinOp", "Add"):        # le 40 + 2 de ?{...}
            continue
        seen.add(name)
    assert seen <= EMISSION_WHITELIST, seen - EMISSION_WHITELIST


@pytest.mark.parametrize("src", ISLAND_ONLY_SOURCES)
def test_emitted_code_parses_as_python_34(src):
    code = transpile(src).code
    ast.parse(code, feature_version=(3, 4))   # lève SyntaxError si trop récent


def test_no_walrus_no_fstring_introduced():
    src = P + "gr = g{ ex:{'a'} ex:p 1 ; ex:q 2 . [ ex:r 3 ] ex:s ( 4 5 ) }\n"
    code = transpile(src).code
    tree = ast.parse(code)
    kinds = {type(n).__name__ for n in ast.walk(tree)}
    assert "NamedExpr" not in kinds     # pas d'opérateur morse
    assert "JoinedStr" not in kinds     # pas de f-string introduite
    assert "Lambda" not in kinds        # pas de fermeture cachée


def test_source_fstring_passes_through_not_amplified():
    """Une f-string ÉCRITE par l'utilisateur reste une f-string, à
    l'identique (MicroPython >= 1.17 les accepte) ; la transpilation n'en
    fabrique pas autour. NB : ast.parse(feature_version=...) est best-effort
    en CPython et ne rejette pas les f-strings — la garantie forte est la
    liste blanche de nœuds du test ci-dessus."""
    src = 'w = "x"\nlit = f"v {w}"@en\n'
    code = transpile(src).code
    assert code.count("f\"v {w}\"") == 1
    joined = [n for n in ast.walk(ast.parse(code))
              if type(n).__name__ == "JoinedStr"]
    assert len(joined) == 1               # celle de la source, aucune de plus


def test_dense_file_parses_as_python_34():
    from tests.test_bench import CHUNK
    src = CHUNK.replace('f"', '"').replace("{valeur}", "{v2}")  # sans f-string
    # CHUNK contient des f-IRI et graphes mais aussi des f-strings ; on vérifie
    # ici un gros fichier réaliste SANS f-string source
    code = transpile(P + "v2 = 1\n" + src.replace("{ nom }", "{ 'n' }")).code
    ast.parse(code, feature_version=(3, 4))
