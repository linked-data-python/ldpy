# 022 — Nommage : le langage reste `linked-data-python` / ldpy

**Date** : 2026-09-03 · **Statut** : tranché
**Question** : avec du recul, `ldpy` et `linked-data-python` sont-ils encore
de bons noms ? Rien n'étant public (pas de push, pas de marketplace, PyPI ne
porte que la préversion 2023), le coût d'un renommage était à son minimum
historique — c'était le moment d'examiner la question, pas de la subir.

## Griefs contre le nom actuel

1. `ldpy` se lit naturellement « LDP-y » — collision sémantique avec la
   Linked Data Platform (W3C), dans la communauté même qui nous lira.
2. « Linked Data » est une étiquette vieillissante (la communauté dit RDF ou
   knowledge graphs) ; le nom long est descriptif mais terne, il sonne
   paquet plutôt que langage.

## Options examinées, et pourquoi elles tombent

| candidat | forme | verdict |
|---|---|---|
| **Atoll** (métaphore île) | nom propre + `.ldpy` conservable | joli et auto-illustratif (island parsing), mais perd tout lien RDF/Python ; homonyme logiciel (planification radio) ; non retenu par Maxime, qui préfère un sigle du domaine |
| **Pyrtle** (Python+Turtle) | portmanteau | décodable et mémorisable, mais laisse SPARQL dehors ; ton joueur |
| **rdfpy** / RDF-Python | patron numpy/scipy | la meilleure sémantique de la famille py+sigle, mais **pris sur PyPI** (calcul de *radial distribution functions*) ; et sonne bibliothèque, pas langage — confusion avec rdflib garantie |
| **pyrdf**, **kgpy**, **pykg** | variantes | pyrdf sonne module maison ; « kg » dit le buzzword, pas le contenu (et se lit kilogramme hors communauté) |
| **RDFx** (famille multi-hôte : RDFx-Python/RDFxPy, RDFx-JavaScript/RDFxJS) | proposition la plus aboutie (Maxime) | **`rdfx` pris sur PyPI** par un outil RDF actif de notre communauté exacte (SURROUND Australia / D. Habgood, conversion-persistance RDF) — `pip install rdfx` installera toujours le leur ; **collision phonétique à une lettre de RDFox** (raisonneur commercial d'Oxford) ; `rdfxpy`/npm `rdfx` libres, mais le nom de famille et le nom de paquet divergeraient |
| extension **`.rdf.py`** / `.rdf.js` | suffixe composé | séduisant sur le papier (les outils voient `.py`), mais c'est le piège : pylint, mypy, black et l'extension Python **parseraient chaque îlot comme du Python pur** et cracheraient des erreurs — R3 garantit Python ⊂ ldpy, jamais l'inverse ; TypeScript a choisi `.ts`, pas `.type.js`, pour cette raison ; et `mod.rdf.py` met un point dans le nom de module |

Vérifications de disponibilité du 2026-08-28 : PyPI `rdfx` 200 (pris),
`rdfxpy`/`rdfx-py`/`rdfx-python` 404 (libres) ; npm `rdfx`/`rdfxjs`/
`@rdfx/core` 404 (libres) ; « RDFx » sans usage établi comme *terme* dans
l'écosystème (la collision est le paquet, pas le concept).

## Décision

**On garde `linked-data-python` (nom long) et `ldpy` (sigle, extension
`.ldpy`).**

## Justification

- Le paysage des noms courts autour de RDF est **saturé** : chaque
  alternative sérieuse bute sur une collision plus grave que celle qu'elle
  corrige.
- Le seul vrai grief contre l'actuel — la lecture « LDP-y » — vise un
  standard qui n'a jamais décollé et décline : la confusion théorique existe,
  les occasions réelles de la rencontrer sont rares et décroissantes.
- Le nom long est **unique, cherchable et auto-descriptif** dans une liste de
  dépendances — qualité qu'aucun sigle examiné n'offre.
- L'idée de famille multi-hôte de RDFx **survit sans renommage** :
  `linked-data-javascript` se décline tout seul le jour venu.
- Après cet examen, ldpy n'est plus un nom par défaut mais un **choix
  documenté** — ce que la question d'un relecteur demandera.

## Conséquences

- Aucun renommage ; article, dépôts, paquet, extension inchangés.
- La question ne se rouvre pas sans élément nouveau (une collision réelle
  constatée, ou un changement de portée du projet — p. ex. la déclinaison
  JavaScript effective, qui remettrait « python » du nom long en cause).
- Si un jour l'extension éditeur rencontre la confusion LDP en pratique,
  la première réponse est documentaire (README, marketplace), pas un
  renommage.
