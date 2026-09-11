# 017 — `@bindings` et gabarits de graphes : `e{ … }` dans `g{ … }`

**Date** : 2026-09-11 · **Statut** : implémenté

**Origine** : décision D4 de la fiche `corpus/402` (mesures) ; phase 3 « graphes-gabarits »
laissée hors périmètre par la fiche 007 ; manque structurel 3 de la fiche 012.

## Contexte

Trois fils convergent vers la même pièce manquante.

1. **La fiche 007** a implémenté `e{ … }` (expressions SPARQL différées,
   évaluées contre un *solution mapping*) mais a explicitement laissé dehors
   « `e{}`/`e<>` comme TERMES dans `g{…}` », c'est-à-dire les graphes-gabarits
   de `dev-sparql`.
2. **Le runtime porte déjà la moitié de la réponse** : `instantiateBGP(input,
   solutionMappings)` (`ldpy/runtime.py`) instancie un graphe à variables contre
   une liste de mappings. Il n'a simplement aucune syntaxe.
3. **Le corpus** (fiche `corpus/402`, Q4) montre que le binding est une pratique
   répandue et *dangereuse* : 123 `initBindings` dans 39 dépôts, mais surtout
   **238 injections de terme dans du texte de requête** dans 50 dépôts, souvent
   par `.n3()` — un binding fait à la main, par concaténation de chaînes.

Ce qui manque n'est pas un opérateur de binding : c'est le **binding comme
contexte**, au même titre que `@prefix` et `@graph`.

Option écartée : l'opérateur `g @ {?v: term}` proposé initialement (D4).
`__matmul__` n'existe pas sur `Graph` ; l'opération n'a aucun sens pour qui
n'écrit pas ldpy (lier des variables n'est pas une opération sur un graphe, il
n'y a pas de requête en attente) ; et un monkey-patch depuis le runtime
modifierait la classe pour tout le processus, y compris pour du code qui ne
nous connaît pas.

## Fonctionnement

### 1. `@bindings` : le binding courant

Une déclaration d'îlot, de **portée lexicale par bloc**, exactement comme
`@prefix` (fiche 004) et `@graph` (fiche 014) :

```python
@bindings sol                 # désigne un mapping existant (n'importe quelle expression)
@bindings as b                # crée : b = _ldpy_.Bindings()

for @bindings in solutions:        # itère : chaque élément devient le binding du corps
    ...
for @bindings as b in solutions:   # idem, et le nomme `b` dans le corps
    ...
```

Les deux premières formes calquent `@graph`. La troisième est la **bascule
entre le monde des graphes et celui des liaisons** : la cible du `for` est une
déclaration d'îlot et non un nom Python (`for` suivi de `@` est illégal en
Python, donc la règle de la fiche 002 est respectée), et le binding courant est
celui du tour de boucle, avec la portée du corps.

Le `as` a le même sens que dans `@graph as g` : il donne un nom Python à ce que
la déclaration lie. Sans lui, le binding courant existe sans nom — c'est le cas
fréquent, où l'on ne fait que réécrire des motifs. Avec lui, on peut le lire,
le compléter (`b[?total] = …`) ou le passer à une fonction, sans cesser d'en
faire le binding par défaut du corps de la boucle : `for @bindings as b in …`
nomme le binding *et* il reste le binding par défaut du corps — les deux
besoins à la fois, sans ligne supplémentaire. `b` suit la portée Python d'une
cible de `for` (il survit à la boucle, comme n'importe quelle variable de
boucle).

La forme accepte **tout itérable de mappings**, ce qui la rend utile bien au-delà
de ldpy — un `csv.DictReader` est à une ligne d'un graphe :

```python
@graph sortie
for @bindings in csv.DictReader(f):
    +{ ex:{?id} a ex:Sensor ; rdfs:label ?name }
```

C'est aussi ce qui remplace toute méthode `.mappings()` sur le résultat d'un
`m{ … }` (fiche 016) : la bascule est une forme de boucle, pas un accesseur.
Il n'y a pas non plus de forme prenant une **liste** de mappings en argument de
`@bindings` : un binding est *un* mapping, l'union se demande explicitement,
par une boucle ou par `update`.

`Bindings` est un **sous-type de `dict`** — « manipulé comme un dict » : clés
`Variable` ou `str` (normalisées), valeurs coercées en termes RDF à
l'affectation. Tout ce que Python sait faire sur un dict marche : `b[?x] = v`,
`b.update(…)`, `del b[?x]`, `**b`, itération sur les clés. Le parallèle avec
`@graph` est complet : `@graph` désigne *où* l'on écrit, `@bindings` désigne
*avec quoi* on instancie.

Un mapping quelconque (un `dict` nu, une ligne de CSV) est accepté partout où
un binding est attendu ; c'est `Bindings` qui est produit par le langage —
notamment par `for @bindings in m{ … }` — et lui seul garantit la coercition
des clés et des valeurs (la politique complète de coercition est en fiche 020 :
elle décide qu'une colonne `age` est un `xsd:integer` et une colonne `uri` un
`URIRef`, et rend une erreur lisible quand un élément de l'itérable n'est pas
un mapping).

Une **ligne de type namedtuple** est acceptée au même titre qu'un mapping :
tout objet exposant `_fields` (une séquence de noms, dans l'ordre des valeurs)
devient un binding par appariement positionnel — sans exiger `_asdict()`, que
`collections.namedtuple` a mais que rien ne garantit ailleurs. Ce test couvre
d'un coup trois origines : `collections.namedtuple` (la demande initiale,
`pandas.DataFrame.itertuples()` en amont), et la propre `Row` du langage — ce
qu'itère un `m{ … }` d'arité ≥ 2 (fiche 016) porte déjà `_fields`, donc
`for @bindings in list(m{ … })` fonctionne sans code séparé. `_fields` a été
préféré à `_asdict` précisément pour cette raison : c'est l'attribut que
`Row`/`_RowSeq` portent déjà (ci-dessous), pas une méthode qu'il aurait fallu
leur ajouter.

Sur `ucollections.namedtuple` (MicroPython), à vérifier avant de déclarer le
chemin fermé : sa mémoire est réduite — pas de `_asdict`, pas de `_replace` —
et ce n'était pas gênant puisque `_fields` seul est utilisé ici, mais son
exposition sur les instances n'est pas encore confirmée sur cible ; le lot
d'appareil (fiche 026) exécute déjà le même `runtime.py`, donc la même
fonction, mais aucun test `test_target_micropython.py` n'exerce ce chemin
pour l'instant.

Un `dataclasses.dataclass` n'est **pas** couvert : il n'a ni `.items()` ni
`_fields`, et le couvrir demanderait `dataclasses.fields()` ou `vars(item)` —
une deuxième voie de duck-typing, asymétrique entre les deux backends
puisque `dataclasses` n'existe pas sur MicroPython. Hors périmètre tant
qu'aucun dépôt du corpus ne le demande.

La désambiguïsation décorateur suit la fiche 004, décision 5 : `@bindings` seul
sur sa ligne, suivi de `(` ou de `.attr`, reste un décorateur Python.

`global @bindings` et `nonlocal @bindings` sont acceptés (fiche 018).

### 2. `g{ … }` devient un gabarit

Dans un îlot de graphe, deux formes de terme s'ajoutent (c'est la phase 3 de la
fiche 007) :

- `?x` — déjà accepté aujourd'hui, produit un terme `Variable` ;
- `e{ … }` et `e<…>` — expressions différées, en position de terme.

La règle d'instanciation est unique et gouvernée par la portée :

> **sans `@bindings` en portée**, un `g{…}` à variables ou à `e{…}` reste un
> **gabarit** : les variables restent des termes, les expressions restent
> différées — c'est le comportement actuel, inchangé ;
> **avec `@bindings` en portée**, il est **instancié** contre le binding courant
> au moment où l'îlot est évalué.

L'instanciation est celle d'`instantiateBGP`, déjà écrite et testée : un triplet
dont un terme reste non lié est **écarté** ; les nœuds anonymes sont frais par
mapping. Les `e{…}` sont évaluées contre le même mapping ; une expression en
erreur SPARQL laisse son terme non lié, donc écarte le triplet — la règle
d'`instantiateBGP` s'applique sans exception nouvelle. Quand une interpolation
`{expr}` est écrite directement dans l'îlot, elle **l'emporte** sur une liaison
homonyme du binding courant.

**Nom préfixé à partie locale variable ou différée** (`ex:{?id}`, `ex:{expr}`) :
`pname()` teste le type EXACT des parties (`Variable` est une sous-classe de
`str`, ce qui rendrait une simple concaténation silencieusement fausse — elle
produirait `ex:id` au lieu d'instancier). Une `Variable` ou une `Expression`
fait basculer le nom entier sur une résolution différée, traitée par le
matérialiseur comme n'importe quel terme `Expression` (non lié → triplet
écarté) ; sinon la `URIRef` est construite tout de suite. `ex:{"hello"}` reste
donc valide **sans binding** : le régime différé ne s'active que si une partie
est effectivement `Variable` ou `Expression`, et n'échoue qu'à l'évaluation
(non lié, ou erreur SPARQL), comme les autres expressions différées. Il n'y a
pas d'encodage pour-cent ici, comme pour toute valeur ordinaire : `ex:{…}`
concatène, `e<…{?id}>` encode — c'est la forme à préférer quand l'encodage
pour-cent est voulu.

### 3. Ce que cela donne à l'écriture

Le pendant en lecture est la fiche 016 ; les deux fiches se referment l'une sur
l'autre — un mini-CONSTRUCT s'écrit dans le flot de contrôle de Python :

```python
@prefix ex: <http://example.org/> .
@graph sortie

for @bindings in m{ ?s ex:reading ?v }:           # fiche 016
    +{ ?s ex:hasValue e{ ?v * 2 } ;               # fiche 014
          ex:label e{ CONCAT("capteur ", STR(?s)) } }
```

Quatre lignes pour un CONSTRUCT, dans le flot de contrôle de Python, sans
moteur de requête et sans texte de requête. La lecture (`m{ }`), la bascule
(`for @bindings in`), l'instanciation (`e{ }` dans le motif) et l'écriture
(`+{ }`) se composent sans qu'aucune ne connaisse les autres.

Sans déclarer le binding, la forme d'appel le fournit :

```python
for b in solutions:
    +{ ?s a ex:Sensor ; ex:value ?v }(bindings=b)    # fiche 019
```

### 4. `@bindings` alimente aussi `s{ … }`

L'îlot SPARQL (fiche 015) émet un `prepareQuery` avec des `initBindings` construits
depuis ses interpolations. Quand un `@bindings` est en portée, il **fournit les
liaisons initiales** de la requête : c'est littéralement ce que les 123
`initBindings` mesurés font à la main, et cela ferme la boucle avec les 238
injections par concaténation, qui n'ont plus de raison d'être.

## Code émis

```python
@bindings as b
```
```python
b = _ldpy_.Bindings(); __bindings__ = b
```

```python
+{ ?s ex:hasValue e{ ?v * 2 } }
```
```python
_ldpy_.add_to(sortie, *_ldpy_.instantiate(((_ldpy_.Variable('s'), _ldpy_.URIRef('http://example.org/hasValue'), _ldpy_.expr(...)),), b))
```

`instantiate(patterns, bindings)` est `instantiateBGP` généralisé aux termes
`Expression` : même règle d'écartement, même fraîcheur des nœuds anonymes. Le
nom `__bindings__` suit la convention de `__namespaces__` / `__base__`
(fiche 004, décision 4) : il sert à l'introspection et au débogage, la
résolution passant, elle, par la variable Python — ce qui donne la portée par
bloc gratuitement (même mécanique que les préfixes dynamiques de la fiche 013).
La portée du corps de `for @bindings in` est portée par une entrée de pile à
`col + 1` — la mécanique d'indentation de la fiche 004, inchangée.
`as_bindings_iter` filtre les variables anonymes (`__bn*`) des solutions d'un
`m{ }`.

Pour un préfixe déclaré statiquement, `ex:{expr}` émet `pname()` ; `f<…>` garde
`firi()`, et son pendant différé reste `e<…>` — les deux formes ne se
confondent pas.

## Ce qui reste dehors

- **Pas de FILTER dans `m{ … }`** pour l'instant (fiche 016) : `e{…}` en
  position de filtre à l'intérieur d'un motif est la suite logique, mais elle
  demande une sémantique d'évaluation *pendant* la jointure, pas après.
- Pas de forme d'agrégation ni de `GROUP BY` : c'est `s{ … }` (fiche 015).
- Pas de conversion automatique des termes en valeurs Python.

## Tests imposés

1. `@bindings` : portée par bloc, masquage, restauration à la sortie (mêmes cas
   que `tests/test_prefix_scoping.py`).
2. `Bindings` est un dict : clés `str` et `Variable` équivalentes, valeurs
   coercées, `update`, suppression, déballage `**b`.
3. `for @bindings in …` : sur un `m{ … }`, sur une liste de dicts, sur un
   générateur, sur un `csv.DictReader` ; portée refermée à la sortie de la
   boucle ; `break` et `continue` ; boucles imbriquées (masquage) ; aucun nom
   Python créé.
3 bis. `for @bindings as b in …` : `b` est lisible et modifiable dans le corps,
   et reste le binding par défaut ; `b` suit la portée Python d'une cible de
   `for`.
4. `g{ ?x … }` **sans** `@bindings` en portée : comportement actuel strictement
   inchangé (non-régression sur les golden existants).
5. `g{ ?x … }` **avec** `@bindings` : instanciation ; triplet à variable non
   liée écarté ; nœuds anonymes frais par mapping.
6. `e{…}` en position de terme : sujet, prédicat, objet ; `e<…>` en position
   d'IRI ; erreur SPARQL → terme non lié → triplet écarté.
7. `+{ }` sous `@bindings` : instanciation puis ajout, sans passer par `+=` ;
   forme d'appel `+{ P }(b)`.
8. `s{ … }` sous `@bindings` : les liaisons arrivent bien en `initBindings`, et
   une interpolation de l'îlot l'emporte sur une liaison de même nom.
9. Un mapping non `Bindings` (dict nu) est accepté partout où un binding est
   attendu.
10. `ex:{?id}` : différé par ligne, immédiat sans binding (`ex:{"hello"}`),
    non lié → triplet écarté, régime gabarit hors binding.
11. Golden + identité + exécution (fiche 006) ; language map exacte.
12. `for @bindings in …` sur une ligne namedtuple (`collections.namedtuple`) ;
    sur une liste de `Row` issue d'un `m{ … }` d'arité ≥ 2 collectée hors de
    la boucle ; non-régression sur le refus d'un élément qui n'est ni un
    mapping ni une ligne à `_fields` (un entier, par exemple).

Implémentation : commit `374a282`, 23 tests (`tests/test_bindings.py`) pour le
cœur de la fiche ; commit `90d8b9d` (ldpy 0.4.0), 5 tests supplémentaires, pour
`ex:{?id}` ; lignes namedtuple ajoutées en réponse à l'issue GitHub #1
(Erdem Onal), 2 tests supplémentaires.

## Voir aussi

- `corpus/402` (la mesure Q4), fiche 007 (`e{…}` différées, phase 3 annoncée
  ici), fiche 004 (portée par bloc — modèle de `@bindings`), fiche 014
  (`@graph` et `+{ }` — le patron et le consommateur), fiche 015
  (`initBindings` de l'îlot SPARQL), fiche 016 (le pendant en lecture),
  fiche 012 (manque structurel 3), fiche 018 (`global` / `nonlocal` sur
  `@bindings`), fiche 019 (suffixe d'appel), fiche 020 (coercition Python → RDF),
  `ldpy/runtime.py` (`instantiateBGP`, déjà en place).
