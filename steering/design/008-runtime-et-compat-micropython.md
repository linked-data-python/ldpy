# 008 — Runtime minimal et compatibilité MicroPython

**Date** : 2026-09-03 · **Statut** : acté

## Contexte

La raison d'être du projet (cf. section.tex de l'HDR) : une grammaire bornée par
MicroPython 1.18, pour des objets contraints. v1 dépendait d'ANTLR runtime +
rdflib + ideas — rien de tout cela ne tourne sous MicroPython.

## Décision

1. **Le transpileur** (`ldpy/transpiler/`) : pur Python, zéro dépendance, style
   compatible MicroPython autant que raisonnable (pas de dataclasses exotiques, pas
   de typing runtime obligatoire). Objectif à terme : transpiler SUR la cible.
2. **Le runtime** (`ldpy/runtime.py`, alias généré `_ldpy_`) : une petite façade qui
   fournit `URIRef, Literal, Variable, Namespace, node, bn, graph, firi`.
   - Backend par défaut : **rdflib** (import dans runtime.py, seul point de contact).
   - La façade permet un backend alternatif futur (urdflib/micro-implémentation)
     sans toucher au code généré. Le code généré ne mentionne JAMAIS rdflib
     directement (contrairement à v1).
3. **Prélude généré** (une ligne, kind `synthetic` dans la map) :
   `import ldpy.runtime as _ldpy_` + init `__base__`/`__namespaces__` si le fichier
   utilise ces primitives.
4. **Import hook** : un MetaPathFinder/Loader standard (importlib) d'environ 60
   lignes, sans dépendance sur `ideas` — de toute façon nécessaire pour maîtriser
   la matérialisation .py + map (fiche 005).
5. **Aucune limitation MicroPython importante** dans le cas général : le
   transpileur accepte n'importe quel Python hôte (il ne le parse pas — le
   Python récent passe tel quel), et ce que les ÎLOTS émettent reste dans un
   sous-ensemble Python 3.4 : imports, affectations, appels, attributs, tuples,
   constantes, souscriptions — aucune f-string/walrus/lambda introduite par
   l'émission ; les f-strings de la SOURCE passent à l'identique (MicroPython
   ≥ 1.17 les accepte). Garanti par `tests/test_micropython_subset.py` (23 tests,
   liste blanche des nœuds AST produits). Autrement dit : ldpy fonctionne avec le
   Python le plus récent, et un fichier qui se limite au sous-ensemble
   MicroPython reste MicroPython après transpilation. La vraie frontière reste le
   runtime (rdflib) — backend micro à faire.
6. **Console interactive** : `python -m ldpy` ouvre une console interactive (`-i`
   après un script, comme v1), pour écrire directement du ldpy sans passer par
   `ideas`. Îlots multilignes attendus comme un `def`, préfixes/base de niveau
   zéro persistants entre les entrées, erreurs non fatales. 10 tests en
   sous-processus réels (`tests/test_console.py`).

## Conséquences

- requirements v2 : `rdflib` uniquement (runtime) ; dev : pytest.
- `ideas` et `antlr4-python3-runtime` sortent des dépendances à la bascule ;
  `ideas` n'a plus aucun rôle dans le projet.
- Publier plus tard sous le même nom PyPI `linked-data-python` en 0.1.0 (rupture
  assumée du code généré, compat du langage source).
