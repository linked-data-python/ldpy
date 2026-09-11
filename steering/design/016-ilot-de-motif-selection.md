# 016 — Îlot de motif `m{ … }` : lire le graphe

**Date** : 2026-09-03 · **Statut** : implémenté

**Origine** : décision D5 de la fiche `corpus/402` (mesures) ; manque
structurel 5 de la fiche 012 (« aucun îlot de *filtrage* »).

## Contexte

ldpy sait **écrire** des structures RDF dans le texte d'un programme ; il ne
sait pas les **lire**. Les régions en lecture seule d'un code traduit gardent
intégralement leur forme rdflib (fiche 012), et l'étude de surface montre que
cette moitié manquante est aussi grosse que celle qui est couverte : la
sélection de triplets apparaît dans 1 033 fichiers de 214 dépôts, contre
1 049 fichiers et 233 dépôts pour la construction.

La question n'est donc pas *s'il* faut une notation de lecture, mais
**laquelle** — et la mesure est ici plus instructive que l'intuition.

## Ce que le corpus impose

Sur 7 870 appels de sélecteurs (`corpus-study/results/summary/surface.json`) :

| Fait mesuré | Chiffre | Ce qu'il impose |
|---|---:|---|
| Sélecteurs de terme (`objects`, `value`, `subjects`, `predicates`) | 6 139 | la forme normale rend **un terme**, pas un triplet |
| Sélecteurs de tuple (`triples`, `subject_objects`, …) | 1 731 | la forme à plusieurs variables existe, minoritaire |
| Contexte `for` / compréhension | 2 185 + 1 054 | le résultat est d'abord **itéré** |
| `list(…)` / `set(…)` | 1 275 + 576 | … puis matérialisé |
| « valeur unique attendue » (`value` 1 840, `next(…)` 412) | 2 252 | il faut une forme dédiée, pas un `next(iter(…))` |
| Contexte `test` / `any(…)` | 156 + 105 | l'existence (ASK) est un usage à part entière |
| Navigation à plusieurs pas | 1 039 (13 %) | elle existe, mais **uniquement** en boucles imbriquées |
| dont profondeur ≥ 3 | 79 (1 %) | la navigation profonde est négligeable |

Deux conclusions, dont une contre-intuitive.

1. **Une syntaxe de navigation chaînée (Gremlin, Cypher, chemins de propriété)
   viserait à côté.** Le chaînage d'expressions (`g.value(g.value(…))`) est
   *absent* du corpus — 0 occurrence. La navigation réelle, ce sont des boucles
   imbriquées dont la variable externe alimente le sélecteur interne.
2. Ce qu'il faut alléger, c'est la **sélection elle-même** : le passage de motif
   `(s, p, None)`, l'itération qui suit, et le « je n'en attends qu'un ».

Le motif canonique, celui qui coûte le plus cher aujourd'hui (extrait réel,
`AAtley/triplify_csv`, quatre niveaux) :

```python
for tm, p, o in self.g.triples((None, RDF.type, URIRef(rr('TriplesMap')))):
    for tmap, p, bn in self.g.triples((tm, URIRef(rr('predicateObjectMap')), None)):
        for bnk, pompred, pomobj in self.g.triples((bn, None, None)):
            ...
```

Trois boucles, trois variables jetables (`p`, `tmap`, `bnk`), une jointure
écrite à la main — pour ce qui est, en Turtle, **un seul motif**.

## Options écartées

1. **Navigation chaînée** (`?s / ex:p / ex:q`) : 1 % de l'usage.
2. **Sucre sur les sélecteurs rdflib** (accepter des pnames dans
   `g.objects(...)`) : les noms préfixés y sont *déjà* écrivables, le gain est
   nul.
3. **S'en tenir à l'îlot SPARQL (fiche 015)** : une requête SPARQL de trois
   lignes pour ce qui était un `g.value` est un recul.
4. **Reprendre `?{ … }`** pour le motif : `?{expr}` est déjà la coercition
   immédiate, synonyme de `f{expr}` — la réutiliser casserait des sources.
5. **Rendre un graphe** (comme `g{}`) : ce que le corpus consomme, ce sont des
   solutions, pas un sous-graphe (le CONSTRUCT relève des fiches 015 et 017).

## Pourquoi un îlot distinct, et non un `g{ … }` plus puissant

Un BGP **est** un graphe : SPARQL le définit comme un ensemble de motifs de
triplets, et `g{ ?s a ex:C }` produit déjà aujourd'hui un graphe à termes
`Variable`. La tentation de n'avoir qu'une syntaxe est donc légitime — et elle
est en partie satisfaite : `m{ P }` **est** `g{ P }`, même analyseur, mêmes
règles de termes, même interpolation. Ce que `m{` ajoute n'est pas une syntaxe,
c'est un **opérateur**.

Trois raisons de le rendre visible plutôt que de le déduire.

1. **`g{ … }` a déjà une sémantique d'itération, et ce n'est pas celle-là.**
   Itérer un `Graph` rdflib, c'est parcourir ses triplets : `for s, p, o in G`.
   Si `g{ ?s a ex:C }` devait aussi vouloir dire « apparie ce motif contre un
   graphe ambiant », alors `for x in g{ … }` signifierait une chose ou l'autre
   **selon qu'un `?` apparaît dans l'îlot**. Un lecteur devrait relire le
   contenu de l'accolade pour savoir si la boucle parcourt trois triplets
   littéraux ou lance une jointure sur un graphe qui n'est pas nommé sur la
   ligne. C'est exactement le genre d'ambiguïté silencieuse que la fiche 002
   s'interdit.
2. **Les deux formes vont dans des sens opposés.** `g{ … }` *construit* : il
   évalue ses interpolations et rend une valeur autonome, sans rien lire.
   `m{ … }` *interroge* : il lit un graphe ambiant et rend des liaisons. Motif
   et graphe sont les deux opérandes d'une même relation, et l'instanciation
   (fiche 017) comme l'appariement en sont les deux directions :

   | direction | forme | consomme | produit |
   |---|---|---|---|
   | écriture | `+{ P }` | motif × bindings | triplets ajoutés au graphe |
   | lecture | `m{ P }` | motif × graphe | bindings |

   Le suffixe d'appel donne à chacun l'opérande qu'il consomme et qui n'est pas
   déclaré : `m{ P }(g)` fournit le graphe, `+{ P }(b)` fournit les liaisons.
   La symétrie est réelle, pas cosmétique.
3. **C'est la convention déjà établie de ldpy.** `f{ … }` et `e{ … }` ont le
   même contenu et diffèrent par le régime d'évaluation (immédiat / différé) —
   et ldpy a choisi une lettre pour le dire, plutôt qu'une inférence. `g{` /
   `m{` est le même arbitrage, appliqué à la même question.

Que le moteur SPARQL de rdflib soit hors d'atteinte sur cible embarquée ne
justifie pas l'existence de l'îlot : il suffirait d'y interdire `s{ … }` (et le
portage de `e{ … }`), contrainte de cible traitée en fiche 008. Ce que
MicroPython justifie, c'est le **choix d'implémentation** de `m{ … }` : une
jointure par boucles imbriquées sur `triples()`, sans moteur ni optimiseur,
donc portable.

## Fonctionnement

Un **îlot de motif** : un BGP écrit en syntaxe Turtle, à variables, évalué
contre le graphe courant, et qui rend une suite de solutions.

```python
@prefix ex: <http://example.org/> .
@graph g

# 1. arité 1 → l'îlot rend directement des termes  (≈ g.subjects / g.objects)
for s in m{ ?s a ex:Sensor }: ...

# 2. arité ≥ 2 → des lignes : tuple déballable, et accès nommé
for s, v in m{ ?s ex:value ?v }: ...
for row in m{ ?s ex:value ?v }: row.s, row[?v]

# 3. la boucle imbriquée devient un motif                (les 1 039 cas)
for tm, pomobj in m{ ?tm a ex:TriplesMap ;
                         ex:predicateObjectMap [ ?p ?pomobj ] }: ...

# 4. valeur unique attendue                                (les 2 252 cas)
label = m{ {res} rdfs:label ?l }.first()      # None si absente   (≈ g.value)
label = m{ {res} rdfs:label ?l }.one()        # erreur si 0 ou > 1

# 5. existence : un motif sans variable est un ASK           (les 261 cas)
if m{ {res} a ex:Sensor }: ...

# 6. matérialisation
noms   = set(m{ ?s rdfs:label ?l })
combien = m{ ?s a ex:Sensor }.count()

# 7. un autre graphe que le graphe courant
for s in m{ ?s a ex:Sensor }(autre_graphe): ...

# 8. les solutions comme liaisons, pour réécrire (fiche 017)
for @bindings in m{ ?s ex:reading ?v }:
    +{ ?s ex:hasValue e{ ?v * 2 } }
```

Les formes 1 à 7 consomment les solutions **en Python** (des termes, des
lignes) ; la forme 8 les consomme **en RDF** (des liaisons). C'est la bascule
entre les deux mondes, et elle est syntaxique : voir « Deux façons de consommer
une solution » ci-dessous.

### Syntaxe

`m{` suit la règle R2 de la fiche 002 — un identificateur d'une lettre collé à
`{`, jamais du Python valide, figé dans la liste fermée de la fiche 002 (contre
`w{`, écarté : l'îlot n'est pas une clause de requête et `w` évoque une
machinerie SPARQL absente). `m {` reste du Python. Le contenu est celui de
`g{ … }` : `a`, `;`, `,`, `[ … ]`, `( … )`, `#`, interpolations `{expr}` en
toute position de terme — **plus** les variables `?x` / `$x`, qui y sont la
raison d'être de l'îlot. L'analyseur d'îlots est le même (`_g_*` de
`transpiler/core.py`), sous un drapeau « variables autorisées ».

### Sémantique

- **Projection** : les variables, dans leur ordre de première apparition. Un
  nœud anonyme (`[ … ]`, `_:b`) est une **variable non distinguée** : apparié,
  mais non projeté. C'est la façon Turtle-native de ne pas projeter — d'où
  l'absence des variables jetables (`p`, `tmap`, `bnk`) de l'exemple ci-dessus.
  Il n'y a **pas** de projection explicite (`.project()` écarté) : le nœud
  anonyme suffit à ne pas projeter, et Python sait réordonner ce qu'il reçoit
  — une méthode de plus pour un besoin déjà servi deux fois ne se justifie pas.
- **Arité 1 → termes, arité ≥ 2 → lignes.** L'irrégularité est assumée : elle
  suit l'usage (6 139 sélecteurs de terme contre 1 731 de tuple) et le
  précédent de rdflib (`g.objects` rend des termes, `g.triples` des tuples).
  Une ligne est un tuple à accès nommé, comme `ResultRow` — `row.s`, `row[?v]`,
  `s, v = row`.
- **Paresse** : l'itération est un générateur ; `.first()` s'arrête au premier
  résultat et rend `None` sur zéro solution, la valeur de vérité aussi.
  `.one()` lève sur 0 et sur ≥ 2 solutions. L'ordre des solutions est celui du
  magasin, non spécifié.
- **Doublons** : une variable non distinguée peut produire deux solutions
  identiques après projection. Elles ne sont pas éliminées — `set(…)` est
  l'idiome, et le coût d'un `DISTINCT` implicite ne se justifie pas.
- **Interpolations** : `{expr}` est évaluée **une fois**, à la construction du
  motif (à l'évaluation de l'expression d'îlot), pas à chaque solution.
- **Termes** : les variables se lient à des termes RDF (`URIRef`, `BNode`,
  `Literal`), sans conversion en valeurs Python — comme rdflib.
- **Graphe** : le graphe courant déclaré par `@graph` (fiche 014).
  Sans `@graph` en portée, le motif est **non lié** : il doit être appliqué à un
  graphe (`m{…}(g)`) avant toute itération, sinon l'erreur est levée à
  l'exécution avec ce message. Le suffixe d'appel obéit à la règle commune de la
  fiche 019 — graphe d'abord, binding ensuite : `m{ P }(g)` lit un autre graphe
  que le courant, `m{ P }(g, b)` y ajoute des liaisons initiales.
- **`count()` consomme le générateur ; `len()` échoue.** Un objet paresseux qui
  répondrait à `len()` mentirait sur son coût, et `len()` sur un générateur est
  déjà une erreur familière en Python.

### Deux façons de consommer une solution

Une solution est la même chose vue de deux côtés : une **ligne** pour Python
(des valeurs positionnelles, à déballer), un **binding** pour RDF (une table
variable → terme, à réinjecter dans un motif). Les deux vues existent, et le
choix se fait par la **forme du `for`**, sans méthode intermédiaire :

```python
for s, v in m{ ?s ex:reading ?v }:      # vue Python : lignes
    print(s, v)

for @bindings in m{ ?s ex:reading ?v }: # vue RDF : liaisons
    +{ ?s ex:hasValue ?v }
```

`for @bindings in …` déclare le **binding courant** pour le corps de la boucle,
comme `@bindings b` le ferait, mais sans nommer une variable dont on n'a que
faire. La cible est une déclaration d'îlot, pas un nom Python — `for` suivi de
`@` étant illégal en Python, la règle de la fiche 002 est respectée. La forme
est spécifiée dans la fiche 017, avec le reste de `@bindings`, et elle n'est pas
propre à `m{ … }` : elle accepte **tout itérable de mappings**, ce qui met un
`csv.DictReader` à une ligne d'un graphe. Aucune méthode `.mappings()` n'est
donc nécessaire.

### Code émis

```python
for s in m{ ?s a ex:Sensor }: ...
```

```python
for s in _ldpy_.match(g, ((_ldpy_.Variable('s'), _ldpy_.RDF.type, _ldpy_.URIRef('http://example.org/Sensor')),), ('s',)): ...
```

`_ldpy_.match(graph, patterns, project)` rend un objet `Match` :
`__iter__`, `__bool__`, `__call__(graph, bindings)`, `first()`, `one()`,
`count()`. L'implémentation est une jointure par boucles imbriquées sur
`graph.triples()`, avec substitution des variables déjà liées. Le
`DELETE WHERE` de `-{ }` multi-motifs réutilise `Match.solutions()` avec
collecte avant retrait.

**Aucune heuristique d'ordre de jointure : les motifs sont appariés dans
l'ordre où ils sont écrits.** C'est le choix le plus simple, et il a une
vertu — l'ordre est visible dans la source, donc contrôlable par qui écrit, au
lieu d'être décidé par un optimiseur absent. Le runtime reste une boucle : rien
de plus que `triples()`, donc portable sur cible embarquée (fiche 008), ce qui
est une conséquence heureuse du choix d'implémentation et non sa
justification. Une heuristique resterait ajoutable plus tard sans toucher au
langage — raison de plus de ne pas en mettre aujourd'hui.

Honnêteté sur les performances : à un motif, `match` est une enveloppe mince
sur `triples()` — coût identique. À plusieurs motifs, c'est une jointure naïve
dans l'ordre d'écriture ; un ordre malheureux est bien plus lent qu'un code
rdflib écrit à la main. Deux échappatoires assumées : réordonner les motifs
soi-même, ou passer à l'îlot SPARQL (fiche 015) et au moteur de rdflib.

### Ce qui reste dehors

- **Pas de FILTER, OPTIONAL, UNION, MINUS, chemins de propriété, agrégats, ni
  tri.** Le `if` de Python couvre le filtrage tel que le corpus le pratique, et
  `s{ … }` couvre tout le reste. La frontière est nette : `m{}` est un BGP sans
  moteur, `s{}` est SPARQL avec moteur.
- L'ajout de filtres `e{ … }` à l'intérieur de `m{ … }` est la généralisation
  naturelle ; elle est instruite avec les gabarits dans la **fiche 017**.
- Pas de lecture inter-graphes (`get_context`, quads) : hors périmètre, comme
  les Datasets (fiche 014).

### Conséquence sur `+{ … }` et `-{ … }`

Les deux îlots d'écriture (fiche 014) **acceptent les variables**, et tous deux
sont évalués contre le binding courant. La règle est unique — *instancier, puis
opérer* — et c'est la direction qui décide du sort d'une variable restée non
liée :

| | variable liée | variable non liée |
|---|---|---|
| `+{ P }` | terme écrit | **triplet écarté** (on ne peut pas écrire un terme inconnu) |
| `-{ P }` | terme apparié | **joker** : retire tout ce qui correspond |

L'asymétrie n'est pas une exception ad hoc : c'est celle de rdflib lui-même,
où `add` exige des termes et `remove((s, p, None))` accepte des jokers, et
c'est la seule lecture utile dans chaque sens. À plusieurs motifs, `-{ P }` se
définit par composition — apparier `P` avec `m{ P }`, puis retirer les triplets
instanciés, c'est-à-dire `DELETE WHERE`.

Le suffixe d'appel fournit le contexte quand on ne veut pas le déclarer :
`+{ P }(g)`, `+{ P }(g, b)`, `+{ P }(bindings=b)` — une seule règle pour les six
îlots, spécifiée dans la fiche 019.

## Limites révélées par le corpus

Les strates `trav_*` de la campagne (fiche `corpus/403`) portent toutes sur
`m{ }`. Quatre constats, trois sur la sémantique et un sur le périmètre —
aucun ne remet la conception en cause, ils la **délimitent**.

### La jointure implicite est un piège de cardinalité, et sa règle est nette

C'est le résultat le plus important de la campagne pour cet îlot. Le motif de
surface ne suffit pas à décider si plusieurs lectures d'un même sujet se
fusionnent en un `m{ }` à plusieurs motifs : deux codes syntaxiquement
identiques appellent des traductions opposées.

**Fusionner est correct** quand la même variable partagée alimente réellement
les deux motifs *et* que les données garantissent l'unicité sur la clé jointe
— une chaîne obligatoire à deux pas. Cas type :
`predicateObjectMap` → `objectMap` (`kumagallium/asterism`), chaque pas requis,
un seul `m{ }` à deux motifs, gain réel.

**Fusionner est faux** quand un sujet partagé alimente des prédicats
*indépendamment optionnels*. Le Python d'origine s'appuie alors sur la
sémantique de variable rémanente d'une boucle `for` : prédicat absent, la
valeur précédente reste. La jointure transforme silencieusement cela en
« prédicat absent, la ligne entière disparaît », par produit cartésien vide.
Vu sur `chin-rcip/CRITERIA` (quatre lectures `sh:path`/`name`/`description`/
`defaultValue`) et sur `aigora-de/rdf-construct`. Même piège avec une chaîne
`elif` de dispatch sur `rdf:type` : joindre le triplet de type force les
quatre types disjoints sur une même ligne au lieu de dispatcher
(`danilipp17/thesis_code`).

La conséquence dépasse la traduction : **l'intitulé de la strate
`trav_navigation` décrit l'exception, pas la règle.** Sur les régions vues, ce
qui ressemble à de la navigation est le plus souvent un motif externe unique
alimentant des lectures indépendantes. La construction qui porte réellement la
strate est le `m{ }` / `.first()` / `bool(m{ })` **répété à chaque site**, pas
une grande jointure. À dire tel quel dans l'article, sous peine de vendre un
gain que le code réel n'offre pas.

### `.first()` couvre `g.value(…)`, sauf le défaut non-`None`

`g.value(s, p)` et `next(iter, None)` tombent exactement sur `m{ }.first()` :
le `None`-sur-zéro-solution de rdflib coïncide avec la sémantique de
`.first()`, rien ne se dégrade. Deux écarts, tous deux rencontrés :

- **un défaut non-`None`** (`next(iter, column)`, ou le quatrième argument
  positionnel `default` de `g.value`) n'a pas de forme : `.first()` n'a pas de
  `default=`. La bonne réponse est de **garder le `g.value` natif**, pas de
  dégrader. Un cas est instructif : `anuzzolese/pyrml` passe `True` en
  quatrième position en croyant à un drapeau — c'est un vrai bug amont, et le
  conserver à l'identique des deux côtés est ce que l'étude doit faire ;
- **un `next(iter)` nu** n'est qu'*approximé* par `.one()` : `next` lève sur
  zéro et ignore le surplus, `.one()` lève sur zéro **et** sur plusieurs.

### Une lecture à plus d'une position libre n'a pas de forme brève

`g.subjects()` sans prédicat ni objet a **deux** positions libres. Il faut
écrire `m{ ?s ?p ?o }` puis déstructurer et jeter deux variables
(`synaptixs/ontomesh`, `_declared_local_names`, classée `awkward` pour cette
seule raison). La lacune ne porte donc pas sur « le prédicat non contraint »
mais sur **toute lecture à un pas dont plus d'une position est libre**.

### `m{ }` n'a ni `OPTIONAL` ni `FILTER` — et c'est la frontière avec `s{ }`

Un `SELECT … OPTIONAL … FILTER(!bound(…))` impose `s{ }`
(`morph-kgc`, `_complete_termtypes`). La frontière annoncée par la fiche tient,
et le corpus la franchit assez souvent pour qu'elle mérite d'être documentée
comme un choix de l'auteur, pas comme un repli.

Le rappel de coercition qui vaut ici — un prédicat qui est une chaîne Python
contenant une IRI se coerce en littéral et ne matche rien — est en fiche
[020](020-coercition-python-rdf.md).

## Tests imposés

1. Arité 1 : `for o in m{ {s} ex:p ?o }` rend des termes ; arité 2 : des lignes
   déballables et à accès nommé (`row.s`, `row[?v]`).
2. Ordre de projection = ordre de première apparition, y compris quand la
   variable apparaît d'abord en position d'objet.
3. Nœud anonyme = variable non distinguée : apparié, non projeté ; `_:b` partagé
   dans le même îlot.
4. Jointure : un motif à trois patrons rend exactement les solutions des trois
   boucles imbriquées équivalentes (test d'équivalence avec le code rdflib).
5. `first()` sur zéro solution rend `None` ; `one()` lève sur 0 et sur ≥ 2.
6. Motif sans variable : valeur de vérité vraie/fausse, sans énumération
   complète (test de paresse : générateur instrumenté).
7. Paresse : `first()` sur un graphe géant ne parcourt pas tout.
8. Interpolation évaluée une seule fois (compteur d'effets de bord).
9. Sans `@graph` en portée : erreur claire à l'itération ; `m{…}(g)` fonctionne.
10. `@graph` dans un bloc : le motif d'un bloc plus profond voit le bon graphe
    (mêmes cas que `tests/test_prefix_scoping.py`).
11. Désambiguïsation : `m {x}`, `m = {1}`, `m` variable, `m(x)` restent du
    Python intact ; `m{` en position d'opérande et en position d'instruction.
12. `for @bindings in m{ … }` : le corps voit le binding courant, la portée se
    referme à la sortie de la boucle, et la forme accepte un itérable de dicts
    quelconque (un `csv.DictReader`).
13. `+{ P }` à variable non liée : triplet écarté ; `-{ P }` à variable non
    liée : joker ; formes d'appel `+{ P }(b)` / `-{ P }(b)`.
14. Golden + identité + exécution (fiche 006), et language map exacte sur des
    motifs multilignes.

Implémentation : commit `08b91e0`, 19 tests (`tests/test_match_island.py`).

## Voir aussi

- `corpus/402` (les mesures Q3), `corpus/401` (l'étude de corpus).
- Fiche 002 (règles lexicales — `m{` relève de R2), 004 (portée par bloc),
  006 (stratégie de tests), 007 (`e{…}` différées),
  008 (compatibilité MicroPython — contrainte de cible, non d'existence),
  012 (manque structurel 5), 014 (`@graph`, dont l'îlot lit le graphe courant),
  015 (l'îlot SPARQL — la frontière), 017 (bindings et gabarits : le pendant en
  écriture), 019 (suffixe d'appel), 020 (coercition des valeurs).
