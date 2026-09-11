# 014 — Graphe courant : `@graph`, `+{ … }` et `-{ … }`

**Date** : 2026-09-03 · **Statut** : implémenté

**Origine** : décisions D2 et D6 de la fiche `corpus/402` ; défaut 4 de la
fiche 012 (« mutation seulement par `+=` »).

## Contexte

Écrire dans un graphe passe par `G += g{…}` : une cible assignable, et un
îlot qui doit contenir assez de triplets pour amortir ses accolades. L'étude
de surface montre que ce n'est pas la forme dominante du code réel.

Sur 13 680 ajouts de triplets :

- **37 % des triplets sont ajoutés seuls** (5 053 séquences de longueur 1 ;
  médiane par dépôt 40 %) — un îlot n'amortit rien ;
- **44 % des ajouts sont dans une boucle**, un triplet par tour ;
- 31 % partagent un sujet avec leur voisin immédiat : le `;` de Turtle a bien un
  référent, mais il ne couvre qu'un tiers des cas ;
- le receveur est long dans 40 % des cas seulement, **pour une moyenne de
  4,0 caractères** — le coût du nom de graphe est faible, contrairement à
  l'intuition de départ.

Et sur les graphes eux-mêmes :

- **73 % des fichiers** qui manipulent un graphe n'en manipulent qu'un ;
  **88 % des fonctions** de même ;
- `Graph(identifier=…)` : 198 occurrences dans 40 dépôts ;
- `Dataset` / `ConjunctiveGraph` : 533 constructions, soit **6,8 %** ; accès à
  un graphe nommé (`get_context`, `contexts`) : 370 dans 36 dépôts.

Ce qui justifie un graphe courant, ce n'est donc pas la longueur du receveur :
c'est le **triplet isolé** et la **boucle**, dans des fonctions qui n'ont
presque jamais qu'un seul graphe.

## Fonctionnement

### 1. `+{ … }` et `-{ … }`, en position d'instruction

```python
@graph self.graph               # déclare le graphe courant, portée par bloc
+{ :s :p :o ; :q {v} }          # ajoute au graphe courant
-{ :s :p :o }                   # retire du graphe courant
```

Les deux formes sont **des instructions**, admises uniquement en **début de
ligne logique et à profondeur crochets nulle** — le scanner tient déjà les deux
bits (`stmt_start`, `depth`).

Hors de cette position, `+` et `-` gardent strictement leur sens Python :
`keys - {'a'}` reste une différence d'ensembles, et c'est la raison pour
laquelle la restriction à la position d'instruction n'est pas négociable.

Le coût est nul : en tête d'instruction, `+{…}` et `-{…}` sont du Python
syntaxiquement légal mais sémantiquement mort — plus ou moins unaire sur un
ensemble ou un dictionnaire, toujours un `TypeError`. Aucun code réel ne s'écrit
ainsi.

Le contenu est celui de `g{ … }` : syntaxe Turtle, interpolations `{expr}` en
toute position de terme, multiligne — **variables comprises**. Les deux îlots
sont instanciés contre le binding courant (fiche 017), et c'est la direction qui
décide du sort d'une variable restée non liée : `+{ }` **écarte** le triplet (on
ne peut pas écrire un terme inconnu), `-{ }` la traite en **joker** (c'est le
`remove((s, p, None))` de rdflib, et `DELETE WHERE` à plusieurs motifs — voir
la fiche 016). La forme suffixe d'appel fournit le contexte quand on ne veut
pas le déclarer — `+{ P }(g)`, `+{ P }(g, b)`, `+{ P }(bindings=b)` — selon la
règle unique de la fiche 019 : un îlot suivi d'une parenthèse reçoit
explicitement le contexte qu'il aurait lu autour de lui, graphe d'abord,
binding ensuite.

Code émis : `_ldpy_.add_to(<graphe courant>, …)` et `_ldpy_.remove_from(…)` —
pas de `+=`, car celui-ci exige une cible assignable, ce qui interdirait une
propriété en lecture seule (`self.assertion` de nanopub) et imposerait un
`global` pour un graphe de module (PySOSA), deux motifs répandus (défaut 4 de
la fiche 012).

### 2. `@graph` : désigner, et créer

```python
@graph self.graph                    # désigne un graphe existant
@graph self.graphs[0]                # n'importe quelle expression Python
@graph as g                          # crée : g = _ldpy_.Graph()
@graph <http://ex.org/g1> as g       # crée : Graph(identifier=URIRef('http://ex.org/g1'))
@graph ex:g1 as g                    # idem, nom préfixé
@graph f<http://ex.org/{k}> as g     # idem, IRI calculée
```

Le `as` porte la création : sans lui, `@graph` ne crée jamais rien. C'est ce qui
évite le piège d'un `@graph g` qui créerait un graphe quand `g` est un nom nu et
en désignerait un quand c'est un attribut — deux sémantiques distinguées par la
seule forme du nom, alors que le transpileur est *flow-insensitive*.

La forme à IRI nomme le graphe **par le paramètre `identifier` de `Graph`** :
elle ne coûte rien, elle est déjà dans rdflib, et elle n'entraîne aucun
`Dataset` (voir « Ce qui reste dehors »).

Dans une classe, `@graph as g` lie `g` comme attribut de classe — la
déclaration lie un nom Python dans la portée où elle est écrite, sans
exception.

**Portée** : celle de `@prefix`, lexicale et par bloc (fiche 004). Un `+{ }` ou
`-{ }` sans `@graph` en portée est une erreur de transpilation, avec ce message.
88 % des fonctions n'ayant qu'un graphe, une déclaration par fonction suffit
presque toujours. `global @graph` et `nonlocal @graph` sont acceptés (fiche
018) — un graphe courant préparé dans une boucle survit ainsi au `break`.

**Désambiguïsation décorateur** : même règle que `@prefix` / `@base` (fiche 004,
décision 5). `@graph` seul sur sa ligne, suivi de `(` — y compris après des
blancs, `@graph (x)` étant du Python légal — ou de `.attr`, reste un décorateur
Python ; une désignation ne se parenthèse pas.

Le runtime partage un matérialiseur unique (`_materializer`) entre `graph()`,
`add_to` et `remove_from`.

## Options écartées

1. **`g+{ }` / `g-{ }`** (receveur explicite collé) : ambigu — `g` suivi d'un
   `+` unaire, et `g - {x}` reste une différence d'ensembles légitime.
2. **`a{ }` / `d{ }`** : `a` est le mot-clé `rdf:type` de Turtle, source de
   confusion ; `+{` / `-{` sont symétriques du `+=` déjà en usage.
3. **`@graph <x>` désignant un graphe nommé dans un dataset implicite** : quel
   dataset, créé où ? Coût en sémantique sans rapport avec les 6,8 % mesurés
   — c'est le `Dataset` qui est refusé, pas le nommage, qui lui est gratuit.

## Conséquences

- Le défaut 4 de la fiche 012 disparaît : `+{ }` n'assigne pas, donc les
  propriétés en lecture seule et les graphes globaux de module deviennent
  écrivables sans contorsion.
- `@graph` est la troisième déclaration d'îlot de portée lexicale, après
  `@prefix` et `@base` — et le modèle de la quatrième, `@bindings` (fiche 017).
  La mécanique de portée de la fiche 004 est réutilisée telle quelle.
- L'îlot de motif (fiche 016) lit lui aussi le graphe courant : `@graph` est la
  déclaration commune à l'écriture et à la lecture.
- `-{ }` à variables prend le sens de `DELETE WHERE` par composition avec la
  fiche 016 (apparier, puis retirer les triplets instanciés) ; le cas à un motif
  redonne exactement `g.remove((s, p, None))`.

### Ce qui reste dehors

Le **Dataset** et l'espace de graphes : `get_context`, `contexts`, `quads`
restent des appels rdflib ordinaires (370 occurrences dans 36 dépôts).
`@graph` désigne toujours *un* graphe courant, éventuellement nommé, jamais un
espace de graphes.

## Tests imposés

1. `+{ }` / `-{ }` en tête d'instruction : ajout et retrait effectifs, en
   dehors et à l'intérieur d'une boucle.
2. Non-régression Python : `a - {x}`, `a + {x}`, `x = -{1}` en position
   d'opérande, `return -{1}`, continuation de ligne, îlot après un `:` de bloc.
3. `+{ }` multiligne ; `+{ }` dans un `if` / `for` / `with` indenté.
4. `+{ }` sans `@graph` en portée → erreur de transpilation, message vérifié.
5. `@graph` sous ses six formes ; `as` absent → aucune création.
6. Portée par bloc : masquage, restauration, blocs frères, imbrication à trois
   niveaux (mêmes cas que `tests/test_prefix_scoping.py`).
7. Décorateur nommé `graph` → non transformé ; `@graph` suivi de `(`, de
   `.attr`, ou d'un saut de ligne.
8. Cible non assignable : propriété en lecture seule et graphe global de module
   (les deux cas de la fiche 012) fonctionnent sans `global` ni `__iadd__`.
9. Golden + identité + exécution (fiche 006) ; language map exacte.

Implémentation : commit `6dd5d77`, 22 tests (`tests/test_current_graph.py`).

## Voir aussi

- `corpus/402` (mesures Q5 et Q6), fiche 004 (portée par bloc — modèle de
  `@graph`), fiche 002 (position d'instruction pour `+{` / `-{`),
  fiche 012 (défaut 4), fiche 016 (l'îlot de motif lit le graphe courant, et
  fixe le sort des variables dans `+{ }` / `-{ }`), fiche 017 (`@bindings`,
  même patron de déclaration), fiche 018 (`global` / `nonlocal`),
  fiche 019 (suffixe d'appel : le receveur explicite).
