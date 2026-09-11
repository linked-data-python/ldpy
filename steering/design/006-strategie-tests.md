# 006 — Stratégie de tests

**Date** : 2026-09-03 · **Statut** : acté

## Contexte

v1 : aucun test exécutable (5 paires golden non branchées sur `dev-sparql`).
La refonte impose un filet dense. rdflib est INTERDIT dans le transpileur mais
AUTORISÉ comme oracle dans les tests (comparaison de graphes, parsing de .ttl
attendus).

## Décision — pyramide en 6 couches (tests/ dans le dépôt ldpy, pytest)

1. **test_scanner.py** — unités du scanner : chaînes (toutes formes, préfixes,
   f-strings imbriquées), commentaires, contexte opérande, lignes logiques.
2. **test_identity.py** — tout .py pur ressort byte-identique. Corpus : sources du
   dépôt lui-même + snippets adverses (`a<b>c`, slices, dicts collés, matmul,
   f-strings avec `{{`, chaînes contenant `g{`, `@prefix` dans une chaîne…) +
   (marqué slow) un balayage de la stdlib CPython/MicroPython locale.
3. **test_islands_*.py** — par type d'îlot : golden inline (source ldpy → py généré
   attendu, déterministe grâce à la fiche 003) + exécution (le py généré est
   exécuté, le terme/graphe produit est comparé via rdflib : égalité de termes,
   `rdflib.compare.isomorphic` pour les graphes).
4. **test_disambiguation.py** — chaque règle et chaque ambiguïté résiduelle de la
   fiche 002, dans les deux sens (transformé / non transformé).
5. **test_semantics.py** — fiche 004 (@prefix dans blocs, redéclaration, fuite
   inter-modules), ordre d'évaluation paresseux (fiche 003 : `cond or g{...}` ne
   doit PAS évaluer les interpolations), îlots dans lambda/comprehension/défauts.
6. **test_linemap.py**, **test_import_hook.py**, **test_examples.py** (les
   examples/ historiques passent), **test_bench.py** (marqué slow, mesure
   lignes/s, garde-fou ×20 minimum vs les 170 lignes/s de v1).

Golden files : `tests/golden/NNN-nom.ldpy` + `.expected.py` (+ `.expected.ttl` si
exécutable). Générateur combinatoire `tests/gen_golden.py` (constructions îlots ×
positions syntaxiques Python) pour atteindre plusieurs centaines de cas — les cas
générés sont commités (lisibles, diffables).

Plus tard : hypothesis (fuzzing léger : le transpileur ne lève jamais autre chose
que LdpySyntaxError ; idempotence sur .py purs).

## Règles

- Une fonctionnalité = ses tests dans le même commit ; suite verte à chaque commit.
- Les bugs découverts deviennent des cas golden numérotés avant correction.
