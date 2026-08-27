# OPTIMIZATION — le débit de matérialisation, piste par piste

Ce document consigne les optimisations du **runtime** (`ldpy/runtime.py`)
explorées pour la scalabilité de la matérialisation de graphes — le scénario
« construction de graphes de connaissances » où un `g{...}` s'évalue à chaque
ligne d'une source. Déclencheur : une étude compagne de construction de graphes de
connaissances, qui compare ldpy à Morph-KGC sur une jointure RML mise à l'échelle
(N = lignes de CSV ; « ×k » = avance de ldpy, meilleur-de-3, CPython 3.12).

## État des courbes successives

| Étape | N=200 | N=2 000 | N=20 000 | N=100 000 |
|---|---|---|---|---|
| v2 initiale | ×7,0 | ×0,8 | — | — |
| + NM partagé (1) | ×30,3 | ×2,8 | ×0,9 | ×0,7 |
| + caches (2) | ×39,0 | ×4,5 | ×1,0 | ×0,9 |
| + graphe paresseux (3) | **×60,1** | **×7,0** | **×1,7** | **×1,1** |

Micro-repère (`graph()` 1 triplet × 2000) : 0,262 s → 0,040 → 0,032 s.

## Pistes retenues

### 1. NamespaceManager cosmétique partagé (commit `d7d2428`)

La liaison des préfixes coûtait ~100× la création du graphe et était payée à
chaque évaluation. Un manager par ÉTAT de `__namespaces__`, mis en cache et
rattaché aux graphes produits ; invalidation par instantané du contenu
(portée par bloc, portée par bloc). ×6,5 sur `graph()`.

### 2. Caches de termes (commit de ce jour)

- **`URIRef` mémoïsé** : les IRI émises par le transpileur sont des
  constantes du programme, reconstruites sinon à chaque tour de boucle.
  Cache borné (garde-fou 1M) — les clés sont bornées par le texte des
  programmes. `firi` n'est PAS cachée (résultats uniques par ligne).
- **`bnode()` mémoïsé** (réutilisation d'objet) : réutilisation de l'objet
  BNode pour une étiquette déjà vue — les charges de déduplication repassent
  sans cesse sur les mêmes clés. Borné (1M).
- **Pool d'instances `bn(i)`** (immuables, une par indice).
- **Dispatch par type exact** dans `node()`/`_term()` : le chemin
  `isinstance`/ABC de rdflib dominait le profil (1,2 M d'appels à 20 k lignes).
- **Identifiant de graphe par compteur** : `Graph()` tirait un uuid4 par
  évaluation (41 000 appels à 20 k lignes).

### 3. Matérialisation paresseuse des graphes émis (`_EmittedGraph`)

Le goulot restant : `cible += g{...}` payait DEUX insertions de store
(le graphe temporaire, puis la cible). Le graphe émis garde ses triplets en
liste ; l'unique point de passage de rdflib vers le stockage (l'attribut
privé `_Graph__store`, intercepté par une propriété du même nom) matérialise
au premier accès réel — mais `__iter__` sert la liste dédupliquée SANS
matérialiser, donc `+=` transfère directement. Invisible sémantiquement
(itération/len ensemblistes, requêtes SPARQL, mutation après lecture —
testés) ; le couplage au nom privé de rdflib est assumé et gardé par la
suite de tests.

### 4. Addition paresseuse de graphes émis (`__add__`/`__radd__`)

Motivé par l'étude OTTR (style compositionnel : des patrons-fonctions qui
retournent des SOMMES de `g{...}`). `g1 + g2` payait la création d'un graphe
rdflib + deux insertions de store complètes ; `sum(gs, Graph())` était
quadratique (chaque étape re-matérialisait l'accumulé). Désormais, tant que
les opérandes sont en attente, `+` concatène les listes de triplets (nouveau
graphe paresseux, O(n)) ; `__radd__` couvre `Graph() + g{...}` — donc
`sum()` — car Python essaie d'abord l'opérande de la sous-classe. La
sémantique d'union (déduplication) reste assurée au flush/itération ;
repli rdflib dès qu'un opérande est matérialisé. Mesure (banc OTTR,
5 000 instances NamedPizza, processus froid) : 49,2 s → 4,3 s (×11,4),
à parité avec Lutra (3,9 s) pour 6,3× moins de mémoire.

## Pistes explorées non retenues (à ce stade)

- **Cache de `Literal`** : les valeurs viennent des données (illimitées) —
  un cache exploserait la mémoire pour un taux de succès quasi nul.
- **Pooling de constantes au transpileur** (hisser `_ldpy_.URIRef('…')` en
  tête de module) : rendu marginal par le cache URIRef (le reste du coût est
  un accès dict) ; l'architecture d'émission « une expression » reste intacte.
- **Vectorisation par lots** (style pandas, comme Morph-KGC) : changerait la
  nature du langage (le g{...} par ligne est le POINT du langage) ; la
  paresse de `_EmittedGraph` en capture l'essentiel sans changer l'idiome.
- **Lecture CSV** : hors runtime (côté programme utilisateur) ; noté pour
  le banc de matérialisation (kgclib).

## Reproduire

Micro : `python - <<'EOF' …` (voir tests) ; courbes : `python -m harness.perf`
du banc compagnon (garde d'équivalence par isomorphisme incluse).
