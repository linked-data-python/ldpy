# 015 — Îlot SPARQL `s{ … }`

**Date** : 2026-09-03 · **Statut** : implémenté

**Origine** : décision D3 de la fiche `corpus/402`. Prolonge la fiche 007
(expressions SPARQL différées `e{ … }`, implémentées) vers la requête complète.

## Contexte

L'étude de surface a démenti l'idée que SPARQL serait une niche dans le code
rdflib applicatif :

- **1 523 appels** (1 177 `query`, 83 `update`, 263 `prepareQuery`) dans
  400 fichiers de **146 dépôts**, soit **39 % des dépôts mesurés** ;
- **58 % des appels portent un texte littéral** (médiane par dépôt 71 %) :
  constante inline, ou constante de module réutilisée (549 cas) ;
- 613 requêtes distinctes occupant **4 953 lignes de source** — du texte
  statique et multiligne, exactement ce qu'un îlot sait accueillir ;
- formes lisibles : SELECT écrase tout (767), puis ASK (37), INSERT (25),
  CONSTRUCT (9), DELETE (8) ;
- consommation : 228 `for row in g.query(…)`, 158 passages à une fonction
  native, 99 compréhensions ;
- **140 requêtes assemblées par interpolation** (f-string, `%`, `.format`) et
  **238 injections d'un terme RDF dans le texte**, souvent via `.n3()`, dans
  87 fichiers de 50 dépôts.

Deux conséquences. D'abord, une requête écrite en chaîne n'est vérifiée qu'à
l'exécution : une faute de syntaxe dort jusqu'au premier appel. Ensuite, les
238 injections de terme sont un problème de **sécurité** autant que
d'ergonomie — c'est une substitution de variable faite à la main dans du texte.

## Fonctionnement

### 1. Tout SPARQL, pas un sous-ensemble

Une grammaire partielle refuserait du SPARQL légal, ce qui est pire qu'une
chaîne : l'utilisateur perdrait la notation au moment précis où sa requête
devient intéressante.

### 2. rdflib comme oracle à la transpilation

Écrire cette grammaire serait déraisonnable — SPARQL 1.1 compte environ
180 productions, et `ldpy/sparql.py` ne couvre aujourd'hui que les *expressions*
de `e{}`. L'îlot ne lexe donc que ce dont il a besoin — les points
d'interpolation et les noms préfixés —, remplace chaque interpolation par une
variable fraîche, et passe le texte à `prepareQuery` **au moment de transpiler**
pour le valider. rdflib est déjà une dépendance d'exécution ; elle devient aussi
une dépendance de transpilation.

```python
q = s{ SELECT ?x WHERE { ?x a {cls} } }
```

se valide avec `?__i0` à la place de `{cls}`, et s'émet en `prepareQuery` avec
le prologue construit depuis les `@prefix` en portée et
`initBindings={'__i0': cls}`.

Trois gains d'un coup : SPARQL entier, la faute de syntaxe détectée à la
transpilation et non à l'exécution, et **l'injection de chaîne éliminée par
construction**.

La validation passe par `prepareQuery`/`prepareUpdate` avec `initNs` — le
parseur seul (`parseQuery`) ne résout pas les préfixes et laisserait passer un
préfixe non déclaré. Elle est **conservée à la transpilation** malgré la
lenteur connue de `prepareQuery` : elle est payée une fois, pas à chaque
exécution ; son coût est quantifié par le banc de la fiche 009, et un drapeau
permet de la couper. L'extension VS Code (fiche 102) reste le bon endroit pour
signaler une faute de requête pendant la frappe — la validation du
transpileur est un filet, pas le seul. Si rdflib est **absent** au moment de
transpiler, l'îlot émet **sans valider**, avec un avertissement : la
transpilation ne doit jamais être bloquée par l'absence d'un oracle facultatif.

Mémoïsation des requêtes préparées, dans le runtime, avec un cache **borné en
nombre** (dictionnaire borné écrit à la main, 64 entrées — pas
`functools.lru_cache`, le runtime doit rester dans le sous-ensemble
MicroPython, fiche 008). Une requête interpolée en position de terme garde un
texte constant, qui est la clé du cache ; les liaisons ne le changent pas.

L'ambiguïté interpolation/groupe sur `{` est tranchée par un oracle : le
contenu équilibré est une interpolation ssi il se transpile puis se compile en
expression (`eval`) — un groupe SPARQL ne le fait jamais, une sous-requête non
plus.

### 3. L'interpolation n'est permise qu'en position de terme

Interpoler un motif entier, une clause ou un chemin de propriété redeviendrait
de la substitution textuelle, avec les risques que l'on venait de supprimer :
c'est une erreur de transpilation.

### 4. Le prologue est hérité

Il ne s'écrit pas dans l'îlot : il vient du `@prefix` ambiant — ce que `initNs`
fait aujourd'hui à la main, 210 fois. Les préfixes dynamiques de la fiche 013
(importés, ou à IRI calculée) n'étant pas connus à la transpilation, **le
prologue réel se construit à l'exécution** ; la validation par `prepareQuery`,
elle, se fait avec un **prologue synthétique**, qui suffit à vérifier une
syntaxe — une IRI en vaut une autre pour cela.

### 5. Forme lexicale

`s{ … }` suit la règle R2 de la fiche 002 : un identificateur d'une lettre collé
à `{`, jamais du Python valide.

### 6. Exécution par suffixe d'appel, et `execute()`

`s{ Q }(g)` exécute la requête sur `g`, `s{ Q }(g, b)` avec `b` en liaisons
initiales, et sans suffixe la requête s'exécute sur le graphe et le binding
courants (règle générale : fiche 019). L'îlot rend un objet requête **préparé
et paresseux** : itérer ou tester sa valeur de vérité suffit pour SELECT, ASK
et CONSTRUCT, mais un `s{ INSERT … }` en position d'instruction ne fait rien
tant que rien ne l'itère. `PreparedQuery.execute()` (alias public de
`_execute()`) est la forme à utiliser pour déclencher un UPDATE, qui n'a pas de
solutions à itérer. Un `s{ }` en position d'instruction n'est délibérément pas
auto-exécuté : cela ferait dépendre le régime d'évaluation de la position
syntaxique, alors que les six îlots ont la même règle.

## Options écartées

1. **Une grammaire SPARQL écrite à la main** dans `islands.py` : environ
   180 productions à porter et à maintenir, pour un résultat forcément en
   retard sur rdflib. L'oracle donne la couverture complète pour une fraction
   du travail.
2. **Un sous-ensemble (SELECT + itération)** : couvrirait l'écrasante majorité
   mesurée, mais échouerait précisément sur les requêtes intéressantes.
3. **Un alias long `sparql{ … }`** : étendrait la règle « un identificateur
   d'une lettre collé à `{` » à « n'importe quel identificateur collé à `{` »,
   pour un gain cosmétique.
4. **Un opérateur de binding séparé** (`g @ {?v: term}`) : voir fiche 017 ;
   l'interpolation en position de terme couvre déjà les 123 `initBindings` et
   les 238 injections textuelles mesurées.

## Conséquences

- rdflib est une **dépendance de transpilation**, et non plus seulement
  d'exécution.
- La frontière avec la fiche 016 est nette : `m{ }` est un BGP **sans moteur**
  (disponible en MicroPython), `s{ }` est SPARQL **avec** le moteur de rdflib.
  Une lecture à un pas ne doit pas coûter une requête.
- Avec `@bindings` en portée (fiche 017), les liaisons courantes alimentent
  les `initBindings` de la requête — ce que les 123 `initBindings` mesurés font
  à la main.

### Ce qui reste hors de portée est plus petit qu'il n'y paraît

Sur les 1 523 appels : 335 littéraux inline, 549 constantes de module résolues,
457 variables non résolues, 140 requêtes assemblées, et **2 seulement** lues
depuis une source externe. Les 884 premiers sont lisibles statiquement, les
140 assemblés sont exactement ce que l'interpolation couvre. Restent les
457 variables non résolues — souvent un littéral défini ailleurs, que
l'analyseur ne suit pas. La fraction réellement hors d'atteinte est **au plus
30 %**, et vraisemblablement bien moins.

## Limites révélées par le corpus

Les strates `sparql_literal`, `sparql_interpolated` et `bind_initbindings`
(fiche `corpus/403`) ont produit 21 régions `not-expressible` à elles trois,
soit les quatre cinquièmes de tout ce que la campagne compte sous ce
classement. Elles relèvent de deux frontières de cet îlot, ni l'une ni l'autre
n'étant un défaut.

**`s{ }` exige un texte littéral à la transpilation.** C'est la conséquence
directe de la décision 2 : rdflib est l'oracle de validation au moment de
transpiler ; dès que le texte de la requête n'est pas là, l'îlot n'a rien à
valider et ne s'applique pas. Trois formes rencontrées, par ordre de
fréquence : la requête **lue à l'exécution**, d'une variable ou d'un fichier
(`semanticarts/ontology-toolkit`) ; un **enrobage générique** de `Graph.query`
qui reçoit la requête en paramètre (`ktbs/rdfrest`, `ProxyStore.query`), sans
texte présent dans la région ; une requête **assemblée** à partir d'un
fragment opaque, par exemple une clause `FILTER` rangée dans un attribut
(`ktbs/PrefixConjunctiveView.contexts`). Rien à corriger : un îlot validé à la
transpilation ne peut pas couvrir ce qui n'existe qu'à l'exécution — c'est le
prix, assumé, de l'erreur à l'écriture plutôt qu'à l'exécution. Ces régions ne
mesurent pas une lacune d'expressivité mais la part du code qui construit ses
requêtes ; à compter séparément dans l'article.

**L'interpolation lie une variable, elle n'épisse jamais du texte** —
distinction coûteuse parce qu'invisible à l'œil. `s{ … {expr} … }` descend
vers `initBindings` : `expr` devient la **valeur** d'une variable de la
requête. Le code d'origine, lui, fait très souvent de l'épissure textuelle, et
ce qu'il épisse est déjà de la syntaxe : une IRI **entre chevrons** dans une
f-string (`f"… <{uri}> …"`), un **motif de triplet entier** produit par
`i.n3()`, une **clause** `FILTER` ou `GRAPH` complète. Aucun des trois n'est
une valeur de terme, donc aucun ne passe par `initBindings`. La traduction
fidèle consiste soit à écrire la syntaxe directement dans l'îlot quand le
fragment est une constante de transpilation — au prix de l'indirection que le
code d'origine partageait entre appels, d'où un classement `awkward`
(`hidden-graph/rdflib-starlight`) — soit à constater qu'il n'y a pas de forme
(`not-expressible`). Le cas de `ktbs/PrefixConjunctiveView` est le plus
parlant : le commentaire du code source montre que ses auteurs avaient
**essayé `initBindings` et l'avaient rejeté** pour Virtuoso — la limite
préexiste donc à ldpy, l'îlot en hérite, il ne la crée pas. Conséquence pour
la strate `sparql_interpolated` : 12 de ses 25 régions sont `not-expressible`
parce qu'elles emploient une interpolation textuelle là où l'îlot n'offre que
du binding sémantique ; l'article doit le dire plutôt que de compter ces
régions comme des échecs de langage.

**Ce qui ne pose aucun problème** : quand le texte est littéral, l'îlot est un
remplacement mécanique, y compris avec `UNION`, `FILTER`, les agrégats et un
prologue `PREFIX` concaténé qui se réduit à des `@prefix`. La coupure annoncée
pour `initBindings` se vérifie telle quelle : variable **projetée** → liaison
en suffixe d'appel ; variable **non projetée** → interpolation en position de
terme. Et un `initNs` dont tous les préfixes sont déjà pré-liés par rdflib est
inerte.

## Tests imposés

1. SELECT, ASK, CONSTRUCT, INSERT/DELETE, DESCRIBE : chacun transpile et
   s'exécute ; requêtes multilignes avec commentaires `#`.
2. Faute de syntaxe → **erreur de transpilation**, avec la position dans le
   fichier `.ldpy` (language map), pas une erreur d'exécution.
3. Interpolation en position de terme (sujet, prédicat, objet, valeur de
   `VALUES`) → `initBindings` ; interpolations multiples ; interpolation
   évaluée une seule fois.
4. Interpolation hors position de terme (motif, clause, chemin de propriété)
   → erreur de transpilation, message vérifié.
5. Prologue hérité : préfixe littéral en portée (résolu à la transpilation) et
   préfixe importé (résolu à l'exécution) donnent la même requête effective.
6. Une variable de l'îlot homonyme d'une variable fraîche `?__i0` ne collisionne
   pas.
7. Non-régression `e{ … }` (fiche 007) : les deux îlots coexistent.
8. Golden + identité + exécution (fiche 006) ; language map exacte sur des
   requêtes multilignes.

Implémentation : commit `7d7cf91`, 15 tests (`tests/test_sparql_island.py`).

## Voir aussi

- `corpus/402` (mesure Q2), fiche 007 (`e{…}` : les expressions différées,
  déjà implémentées), fiche 013 (préfixes dynamiques → prologue à l'exécution),
  fiche 016 (l'îlot de motif, sans moteur — la frontière), fiche 017
  (`@bindings` → `initBindings`), fiche 002 (règle R2), fiche 019 (suffixe
  d'appel : `s{ Q }(g, b)`), fiche 102 (l'extension VS Code, autre lieu naturel
  de la validation).
