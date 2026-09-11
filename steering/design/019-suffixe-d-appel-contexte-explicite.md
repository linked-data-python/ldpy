# 019 — Le suffixe d'appel : donner explicitement son contexte à un îlot

**Date** : 2026-09-03 · **Statut** : implémenté

**Origine** : les fiches 014, 015, 016 et 017 introduisaient chacune leur propre
forme d'opérande explicite. Elles disent en fait toutes la même chose, et c'est
une règle unique.

## Contexte

Les îlots de ldpy lisent un **contexte ambiant** déclaré autour d'eux :

- le **graphe courant**, déclaré par `@graph` (fiche 014) — ce sur quoi on écrit
  et ce qu'on interroge ;
- le **binding courant**, déclaré par `@bindings` (fiche 017) — ce avec quoi on
  instancie et ce qui préalimente une requête.

C'est le bon défaut : 88 % des fonctions n'ont qu'un graphe, et une déclaration
par fonction suffit presque toujours. Mais il faut pouvoir y déroger sur une
ligne, sans ouvrir un bloc : écrire dans un autre graphe que le courant, lire
dans un graphe reçu en argument, instancier un gabarit avec un mapping calculé.

Chaque fiche avait inventé sa réponse dans son coin — `m{ P }(g)` ici,
`+{ P }(b)` là. Deux notations identiques d'aspect et de sens opposé : c'était
un défaut, pas une symétrie.

## Fonctionnement

> **Un îlot suivi d'une parenthèse reçoit explicitement le contexte qu'il aurait
> lu autour de lui.** L'ordre est toujours le même : le **graphe** d'abord, le
> **binding** ensuite, tous deux facultatifs.

```python
e{ ?x + 1 }(b)                  # binding : un terme évalué contre b
g{ ?s a ex:C }(b)               # binding : le gabarit instancié par b
m{ ?s a ex:C }(g)               # graphe : apparier dans g
m{ ?s a ex:C }(g, b)            # graphe + liaisons initiales
+{ ?s a ex:C }(g)               # graphe : écrire dans g
+{ ?s a ex:C }(g, b)            # graphe + binding d'instanciation
-{ ?s a ex:C }(g)
s{ SELECT ?x WHERE { … } }(g)   # graphe : exécuter sur g
s{ SELECT ?x WHERE { … } }(g, b) # graphe + initBindings
```

Un îlot qui ne touche aucun graphe — `e{ … }`, `g{ … }` — n'a qu'un opérande,
le binding ; sa parenthèse ne peut donc rien vouloir dire d'autre. Les quatre
autres prennent le graphe en premier. Pour ne donner que le binding à l'un de
ceux-là, on le nomme :

```python
+{ ?s a ex:C }(bindings=b)
```

Ce qui n'est pas donné est lu dans le contexte ambiant ; ce qui n'est ni donné
ni déclaré fait une erreur — de transpilation quand elle est décidable
(`+{ }` sans graphe, fiche 014), d'exécution sinon, avec un message qui nomme la
déclaration manquante.

**Pas de troisième opérande, pas de `base=`.** La base est lexicale (fiche
004) et doit le rester : elle nourrit le transpileur, pas l'exécution.

**Les liaisons initiales sont projetées.** `m{ P }(g, b)` rend des solutions
qui contiennent `b`, comme le fait `initBindings` en SPARQL — c'est aussi ce
qui garantit qu'un binding sorti d'un `for @bindings in` est complet et
réutilisable tel quel en écriture.

### Ce n'est pas une extension de syntaxe

Pour les quatre îlots qui sont des **expressions** (`e{}`, `g{}`, `m{}`, `s{}`),
le suffixe est un appel Python ordinaire sur la valeur de l'îlot : rien à
ajouter au scanner, et `__call__` sur l'objet du runtime suffit. Le cas de
`e{ … }` était déjà implémenté — `expr(sm)` et `expr.ebv(sm)` sont exactement
cette forme (fiche 007) ; la présente fiche ne fait que la nommer et
l'étendre aux autres.

Pour les deux îlots qui sont des **instructions** (`+{}`, `-{}`), il n'y a pas
de valeur à appeler : le transpileur lit la parenthèse qui suit l'accolade
fermante comme la liste des opérandes, et l'émet en arguments de
`_ldpy_.add_to` / `remove_from`. L'asymétrie est réelle, elle est invisible à
la lecture, et elle est le prix d'avoir fait de l'ajout une instruction.

## Conséquences

- Une seule règle à apprendre pour six îlots, au lieu d'une convention par
  fiche.
- Le receveur explicite de `+{ }` / `-{ }` existe : `G += g{…}` n'est plus la
  seule façon d'écrire ailleurs que dans le graphe courant.
- `s{ Q }(g, b)` remplace avantageusement le couple `prepareQuery` +
  `g.query(q, initBindings=…)` : l'îlot rend un objet requête préparé, et
  l'appeler l'exécute (fiche 015).
- La lecture d'une ligne reste locale : le contexte est soit déclaré au-dessus,
  soit écrit entre parenthèses, jamais deviné.

## Tests imposés

1. Les six îlots avec zéro, un et deux opérandes ; `bindings=` nommé.
2. Le suffixe l'emporte sur la déclaration ambiante, et ne la modifie pas (la
   ligne suivante retrouve le contexte déclaré).
3. `e{ E }(b)` : non-régression stricte avec `expr(sm)` de la fiche 007.
4. `+{ P }(g)` sur un graphe non assignable (propriété en lecture seule) et sur
   un graphe global de module : aucun `global`, aucun `__iadd__`.
5. Contexte ni donné ni déclaré : erreur de transpilation pour `+{ }` / `-{ }`,
   erreur d'exécution nommant la déclaration manquante pour les autres.
6. Un îlot **sans** suffixe suivi d'une parenthèse sur la ligne suivante
   (continuation) : le comportement doit rester celui de Python.
7. Golden + identité + exécution (fiche 006) ; language map exacte.

Implémentation : commit `b32f7fa`, 13 tests (`tests/test_call_suffix.py`). Les
quatre îlots-expressions passent par `__call__` (celui de `e{ }` existait,
fiche 007) ; `g{ }(b)` instancie avec nœuds anonymes frais par appel ;
`+{ }`/`-{ }` lisent la parenthèse collée (R2).

## Voir aussi

- Fiches 014 (`@graph`, `+{ }` / `-{ }`), 015 (`s{ }`), 016 (`m{ }`),
  017 (`@bindings`, `g{ }` gabarit), 007 (`e{ }` — la forme d'appel existante),
  020 (coercition des opérandes reçus).
