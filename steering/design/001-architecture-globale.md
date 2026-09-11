# 001 — Architecture globale du transpileur v2

**Date** : 2026-09-03 · **Statut** : acté

## Contexte

Le transpileur v1 (branches `master`/`dev-sparql`) repose sur ANTLR4 + runtime
Python : grammaire complète de Python/MicroPython 1.18 (807 lignes de .g4) avec des
îlots RDF greffés, canaux de tokens dynamiques, visiteur de réécriture. Mesuré à
**~170 lignes/s** — rédhibitoire pour l'import à la volée et pour un language server.
Contrainte utilisateur : ne pas se reposer sur les parsers Turtle/SPARQL de rdflib.

## Options envisagées

- **A. Island parsing manuel** : scanner à états conscient du lexique Python
  (chaînes, commentaires, crochets), qui recopie le Python tel quel et ne parse en
  descente récursive que les îlots RDF. Retenue.
- **B. tree-sitter** : rapide et incrémental, mais binaire natif, grammaire GLR
  moins adaptée aux modes imbriqués, et exclut MicroPython. Gardé en option
  *complémentaire* future pour l'éditeur.
- **C. ANTLR cible C++** : gain réel mais dépendance binaire et on garde le coût de
  re-parser tout Python. Rejetée.
- **D. Lark/parso/libcst** : INDENT/DEDENT et îlots contextuels pénibles, ou fork
  profond nécessaire. Rejetée.

## Décision

Option A. Architecture en un seul passage, flux de caractères :

```
source .ldpy
  → Scanner (ldpy/transpiler/scanner.py)
      · conscience lexicale Python : chaînes (toutes formes : ', ", ''', """,
        préfixes r/b/f/u, f-strings), commentaires, profondeur de crochets,
        lignes logiques, contexte opérande (fiche 002)
      · recopie verbatim les segments Python
      · sur déclencheur d'îlot → parser d'îlot
  → Parsers d'îlots (ldpy/transpiler/islands.py, descente récursive)
      · @prefix/@base (îlots-instructions)
      · <IRI>, pname, ?var, "lit"@lang, "lit"^^dt, f<...>, f{...}, ?{...}, g{...}
      · les expressions Python imbriquées ({expr} dans un graphe, corps de f{})
        sont re-scannées par le Scanner → récursion mutuelle Scanner ⇄ îlots
  → Émission : remplacement inline par UNE expression Python (fiche 003)
      + language map segment-level (fiche 005)
  → runtime minimal ldpy/runtime.py (fiche 008)
```

L'ancienne chaîne ANTLR reste dans le dépôt (`ldpy/rewriter/`) comme référence de
comparaison pendant la transition, puis sera supprimée.

## Justification

- Complexité O(n) sur la partie Python (~95 % d'un fichier réel) ; objectif
  > 10 000 lignes/s (×60).
- Zéro dépendance de parsing → transpileur exécutable en pur Python, potentiellement
  sous MicroPython (cohérence du projet, fiche 008).
- « Un fichier .py pur ressort byte-identique » devient vrai par construction →
  test de non-régression massif et gratuit (fiche 006).
- Les mini-grammaires d'îlots de v1 (LDPython.g4 règles ~350-410 et l'extension
  dev-sparql) servent de spécification.

## Conséquences

- Il faut réimplémenter à la main la reconnaissance lexicale Python (chaînes,
  commentaires) — surface réduite mais à tester sévèrement.
- La désambiguïsation îlot/Python n'est plus cachée dans ANTLR : elle est explicitée
  et documentée (fiche 002) — c'est un progrès (v1 avait des ambiguïtés non
  documentées, ex. `a<b>c` lexé comme IRI).
