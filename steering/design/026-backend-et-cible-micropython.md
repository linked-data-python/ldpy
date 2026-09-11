# 026 — Deux axes, pas deux exclusifs : le backend, et SPARQL

**Date** : 2026-09-03 · **Statut** : implémenté — mode 1 de la fiche 304 vérifié sur le portage Unix

## Deux axes, avec une implication

1. **Le backend** — rdflib sur l'hôte, urdflib sur l'appareil — n'est pas un
   choix de l'utilisateur mais **du contexte** : sur CPython, rdflib est là ;
   sur MicroPython, il n'y a pas de pip, le backend est le firmware. Le code
   engendré est **le même** sur les deux ; c'est `ldpy.backend` qui choisit,
   par ce qui s'importe. Il n'y a donc pas d'extra pip `[urdflib]` : ce
   serait un extra qu'on ne peut installer nulle part.
2. **SPARQL n'est pas une capacité, c'en est deux**, et elles n'ont pas le
   même coût :
   - `e{ }`, les expressions — `ldpy/sparql.py`, 551 lignes de Python pur
     sur les termes (`.datatype`, `.language`, `.toPython()`, `XSD`). Elles
     tournent sur les deux backends. **Vérifié** : `e{ ?v >= 1.5 }` filtre
     sur MicroPython avec urdflib comme sur l'hôte ;
   - `s{ }`, les requêtes — `rdflib.plugins.sparql.prepareQuery`, c'est-à-dire
     le moteur de rdflib et pyparsing. Aucun équivalent sur l'appareil, et sord
     n'a pas de moteur.

D'où l'implication, et elle est la seule contrainte : **`s{ }` ⇒ backend
rdflib**. Ni exclusion ni symétrie. Et l'endroit où cette contrainte doit se
dire n'est pas l'exécution sur l'appareil — c'est la **transpilation sur
l'hôte**, où le message se lit.

## Ce qui est implémenté

- **`ldpy/backend.py`** : rdflib si `import rdflib` réussit, sinon urdflib ;
  `Namespace`, `RDF`, `XSD` en Python là où le module C n'en a pas ;
  `new_graph`, `bind_namespaces`, `prepare_sparql` (qui dit quel backend
  manque de moteur). Le contrat qu'un backend doit remplir est **la liste
  des noms publics de ce module** — c'est ce que `urdflib/tools/api_gap.py`
  mesure.
- **`ldpy/runtime.py`** ne nomme plus rdflib : termes et graphes viennent du
  backend. Le graphe émis reste paresseux sur rdflib (l'accroche privée
  `_Graph__store`) et devient **direct** sur urdflib, dont les graphes
  ajoutent en place à la vitesse du C ; la `Row` d'un `m{ }` se passe de
  `tuple.__new__`, que MicroPython n'a pas ; `itertools.count` remplacé.
  `ldpy/sparql.py` prend ses termes au backend.
- **`--target micropython`** (`ldpy`, `ldpy.build`, `transpile(target=)`) :
  `s{ }` est refusé à la construction avec un message qui dit quoi écrire
  (`m{ }` et `e{ }`) ; `ldpy.build` copie le **runtime d'appareil** —
  `runtime.py`, `backend.py`, `sparql.py`, un `__init__.py` minimal sans le
  transpileur — à côté des fichiers émis : ce qu'on embarque et ce qu'il
  importe voyagent ensemble.
- **`tests/test_target_micropython.py`** : la cible refuse `s{ }` et garde
  `e{ }`, `m{ }`, `g{ }` (même code émis) ; le lot d'appareil ne contient pas
  le transpileur ; `runtime.py` et `sparql.py` ne nomment plus rdflib ; et
  **le même programme** (`+{ }`, `m{ }` avec `Row`, `e{ }`, `serialize`)
  transpilé sur l'hôte tourne sur un MicroPython construit avec urdflib
  (`LDPY_MICROPYTHON`) et **donne la réponse de l'hôte**.

Suite ldpy : 1 625 tests verts. La démonstration de la fiche 304 tourne en
mode 1 : `sensor.ldpy` construit avec `--target micropython` donne ses 52
triplets et leur Turtle sur MicroPython, en 10 ms de bout en bout sur le
portage Unix.

## Ce qui reste, et pourquoi ce n'est pas ici

- **Pas d'extra pip nouveau.** Sur CPython rdflib reste la dépendance, et
  son moteur SPARQL vient avec : un extra `[sparql]` ne retirerait rien.
  L'« optionnel » que demandait la question est la cible de transpilation.
- `e{ }` dépend encore de `decimal` pour les décimaux exacts, importé
  paresseusement : sur MicroPython le chemin `xsd:decimal` retombe sur le
  flottant. Pas rencontré dans la démonstration ; à traiter quand un
  programme le rencontrera.
- Le mode 2 (transpiler sur l'appareil) demande d'embarquer le transpileur
  — 2 700 lignes qui utilisent `re` et des chaînes : à essayer, c'est la
  fiche 304.
