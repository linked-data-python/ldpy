# 009 — Artefact d'évaluation : banc de débit par génération aléatoire

**Date** : 2026-09-03 · **Statut** : implémenté — `bench/`

## Contexte

`ROADMAP-artefact-evaluation.md` (fusionné dans `ROADMAP.md` §B) demandait un 4ᵉ artefact : mesurer le débit
« dans des conditions variées », les corpus fixes ne disant rien de la forme de
la courbe. Recherche d'existant faite (OpenAlex) : la lignée retenue est
Csmith (génération différentielle), QuickCheck/Hypothesis (property-based),
Grammarinator (fuzzing de grammaires) — 4 références ajoutées à Zotero.
hypothesmith a été écarté pour le cœur : il génère du Python pur (pas d'îlots)
et son biais de distribution est incontrôlable ; un générateur maison de
~300 lignes donne le contrôle paramétrique voulu.

## Décision

`bench/generator.py` : génération **déterministe** (graine) de sources ldpy
**valides et exécutables** (noms définis avant usage), paramètres : taille,
densité d'îlots, mix des sortes, triplets/graphe, imbrication, mode
v1-compatible. La « mer » embarque les pièges de la fiche 002. 21 tests
(déterminisme, validité, identité à densité 0, exécutabilité).

`bench/run.py` : cinq campagnes — densité (0→100 %), taille (200→50 000
lignes), taille des graphes, v1 vs v2 sur fichiers identiques, transparence
(fichiers Python purs que v1 rejette). Sorties JSON + CSV, consommées par la
figure pgfplots et la table de l'article.

## Résultats (CPython 3.12, dans l'article §Evaluation)

- 109 687 l/s à 0 % d'îlots → 56 052 l/s à 100 % (courbe régulière) ;
- débit constant ~80 000 l/s de 200 à 50 000 lignes (linéarité) ;
- graphes : 35 315 l/s (1 triplet/graphe) → 51 280 (100) — coût par îlot amorti ;
- v1 : 116 l/s (×911) et **15/20 fichiers Python purs rejetés** (`a<b>c` lexé
  comme IRI) — la mesure de transparence a confirmé la limitation v1 citée.
- Métrique clarifiée (question de Maxime) : lignes/s = lignes du SOURCE ldpy.

## Conséquences

- Double usage prévu (fiche 006) : les mêmes générateurs alimenteront le
  fuzzing de robustesse (propriété « ne lève que LdpySyntaxError »).
- Biais assumé, dit dans l'article : distribution synthétique ≠ code humain ;
  corpus manuels + stdlib en contrepoids.
