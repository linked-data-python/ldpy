# 020 — Coercition Python → RDF : une politique, configurable

**Date** : 2026-09-03 · **Statut** : implémenté

## Contexte

Partout où une valeur Python entre dans une structure RDF, quelqu'un décide de
quel terme il s'agit. Cela reste dispersé sur plusieurs points d'entrée :

- `_ldpy_.node(value)` — les interpolations `{expr}` dans un îlot : tout ce qui
  n'est pas déjà un terme devient `Literal(value)` (`ldpy/runtime.py`) ;
- `_ldpy_.dtype(value)` — après `^^`, où une chaîne est lue comme un **IRI** et
  non comme un littéral, parce qu'un type de donnée est toujours un IRI ;
- `instantiateBGP` — les valeurs d'un solution mapping : `Literal(value)` si ce
  n'est pas déjà un `Node` ;
- `@bindings` et `for @bindings in …` (fiche 017), qui font entrer des
  mappings entiers venus de n'importe où.

Le défaut brut est trop grossier dès qu'on sort des cas simples : une colonne
de CSV nommée `age` doit devenir un `xsd:integer`, une colonne `uri` un
`URIRef`, une colonne `date` un `xsd:date` — sans politique, les trois
deviennent des littéraux de chaîne, et l'utilisateur doit convertir à la main
**avant** d'entrer dans l'îlot, ce qui annule le bénéfice de la notation.

## Décision

### 1. Une fonction de coercition unique

Tous les points d'entrée passent par **une** fonction du runtime,
`_ldpy_.node(value, field=None)`, où `field` est le nom du champ ou de la
variable d'où vient la valeur quand il est connu (clé de mapping, nom de
variable). Comportement par défaut :

| entrée | défaut |
|---|---|
| déjà un terme RDF (`URIRef`, `Literal`, `BNode`, `Variable`) | rendu tel quel |
| toute autre valeur | `Literal(value)` — rdflib choisit le datatype |

`dtype()` (position de datatype, après `^^`) reste distinct et n'est **pas**
configurable : un datatype est un IRI par définition, ce n'est pas une politique
mais une règle de la spécification RDF.

### 2. Une politique est un objet : `Coercion`

La politique n'est pas un réglage global posé quelque part, c'est une **valeur**
que l'on construit, que l'on nomme, que l'on passe et que l'on réutilise :

```python
csv_capteurs = _ldpy_.Coercion({
    ("id", "homepage"): URIRef,                 # ces champs sont des IRIs
    ("age", "count"): XSD.integer,              # littéral typé
    ("born",): lambda v: Literal(date.fromisoformat(v)),   # conversion libre
    date: XSD.date,                             # par type Python
    Decimal: XSD.decimal,
})
```

Une clé est **soit un tuple de noms de champs, soit un type Python** — les deux
critères que l'on possède au moment de convertir, et ils ne peuvent pas être
confondus (`isinstance(clé, tuple)` contre `isinstance(clé, type)`). Le tuple
est la forme du cas dominant, où plusieurs colonnes partagent une conversion.

Une conversion est un **datatype** (IRI XSD ou autre), `URIRef`, ou n'importe
quelle **fonction** rendant un terme. `URIRef` suffit à demander un IRI : c'est
déjà un appelable, et cela évite un nom de plus dans le runtime.

**Ordre de résolution**, du plus spécifique au plus général : le champ, puis le
type Python, puis le défaut `Literal(value)`. Une valeur qui est déjà un terme
RDF n'est jamais reconvertie, quelle que soit la politique.

### 3. Une pile, et `with`

Les politiques s'empilent, et la portée est celle de Python :

```python
with csv_capteurs:
    for @bindings in csv.DictReader(f):
        +{ ?id a ex:Sensor ; ex:age ?age ; rdfs:label ?name }
```

`Coercion` est un gestionnaire de contexte : entrer empile, sortir dépile — y
compris par une exception. La résolution parcourt la pile **du sommet vers la
base**, et la première politique qui connaît le champ (puis le type) l'emporte :
un `with` intérieur **raffine** l'extérieur au lieu de le remplacer, sans avoir
à le recopier. C'est ce que la pile achète, et c'est ce qu'un réglage unique ne
saurait pas faire.

Pour une politique valable sur tout un module, où envelopper le fichier dans un
`with` n'aurait pas de sens, la même instance s'installe sans dépilage :

```python
csv_capteurs.install()          # empile définitivement
```

**Il n'y a pas de `@coercion` et pas de portée par bloc à écrire**, et c'est
délibéré : une politique de conversion est un réglage d'exécution, pas une
déclaration de langage. Python a déjà l'outil qui donne une portée à un état
d'exécution — c'est `with`, et il fait exactement ce qu'il faut. Les
déclarations d'îlot (`@prefix`, `@graph`, `@bindings`) sont lexicales parce
qu'elles nourrissent le **transpileur** ; celle-ci ne le nourrit pas.

## Le piège de la chaîne qui est une IRI

La politique de coercition fait exactement ce qu'elle doit faire : une `str`
nue devient un `Literal`. Le problème mesuré par la campagne (fiche
`corpus/403`, trois dépôts sans rapport — `RDFLib/VocPrez`, `morph-kgc`,
`kumagallium/asterism`) est ailleurs : **le code rdflib d'origine range
couramment une IRI complète dans une `str`**, et la relire comme un littéral
produit un résultat vide **sans erreur**.

C'est le pire profil de défaut : la traduction est fausse, le programme
tourne, et rien ne le signale. Une politique de coercition qui *devinerait* —
« cette chaîne ressemble à une IRI, donc c'en est une » — reste écartée
(fiche 002) : le transpileur ne devine pas le type d'un terme depuis une
chaîne.

Les parades sont connues et suffisantes — `f<{expr}>` en position de terme,
`{URIRef(expr)}` sinon, ou une `Coercion(field=…)` explicite pour un code qui
range ses IRI dans des `str`. Ce qui manque encore est un **avertissement au
bon endroit** dans la documentation : le piège est couvert dans
`migrate-from-rdflib.md` pour `URIRef(x)` vs `f<{x}>`, mais pas pour
l'interpolation d'un `m{ }` ni d'un `s{ }`, qui sont les deux positions où la
campagne l'a effectivement rencontré.

## Le suffixe `^^` n'existe qu'en position de terme

`{v}^^dt` et `{v}@lang` ne s'analysent qu'**à l'intérieur d'un îlot** (`g{}`,
`m{}`, `+{}`, `-{}`), là où il y a une position de terme. Hors îlot, la seule
forme est `f{Literal(v, datatype=dt)}`.

Ce n'est pas une lacune d'expressivité — la forme existe et transpile — mais
il faut en tirer la bonne conclusion pour l'article : **hors îlot, `f{ }` ne
gagne que sur la coercition non typée.** `f{elem.text}` remplace élégamment
`Literal(elem.text)` ; `f{Literal(v, datatype=dt)}` ne fait que réemballer
l'appel rdflib, à longueur et structure égales. Sur les quatre sites de
`jupyter-naas/abi` (`Oxigraph_query`), trois sont dans ce cas, et la région est
classée `awkward` pour cette seule raison.

Conséquence chiffrée : tout gain annoncé pour cette strate doit distinguer les
sites à datatype **fixé au site d'appel** (vrai gain : `{x}^^cim:Voltage`) de
ceux dont le datatype est **calculé** (gain nul hors îlot). Les confondre
surestime le bénéfice.

## Options écartées

1. **Deviner le type depuis la valeur** (`"42"` → entier) : irrécupérable dès
   qu'un identifiant est numérique ou qu'une colonne est vide, et silencieux
   quand ça se trompe. rdflib fait déjà le bon travail sur les types Python
   *natifs* ; c'est le passage par la chaîne qui perd l'information, et seule
   une déclaration peut la rendre.
2. **Une politique par îlot** (un argument de plus dans le suffixe d'appel,
   fiche 019) : la conversion serait redite à chaque ligne, alors qu'elle est
   par nature une propriété de la **source** de données. `with` la pose une fois
   sur la région qui lit cette source, ce qui est la bonne granularité.
3. **Un réglage global unique** (`_ldpy_.coerce({…})`) : impossible à raffiner
   localement, impossible à défaire, et deux bibliothèques s'écrasent l'une
   l'autre sans le dire. La pile d'objets règle les trois d'un coup.
4. **Déclarer les types dans le motif** (`?age^^xsd:integer` dans un `g{ }`) :
   séduisant, mais cela mélange la structure du graphe et le typage de l'entrée,
   et il faudrait le répéter à chaque usage de la variable. À reconsidérer si la
   politique par champ se révèle trop grossière.

## Conséquences

- Un point d'entrée unique à tester, à documenter et à optimiser — `node()` est
  sur le chemin chaud de la matérialisation (`OPTIMIZATION.md`) ; le banc de
  débit ne bouge pas sans politique installée (~60 000 lignes/s, objectif
  > 10 000 tenu).
- `for @bindings in <itérable>` (fiche 017) sur un élément qui n'est pas un
  mapping devient une **erreur de coercition** avec un message qui nomme
  l'élément fautif, plutôt qu'un `TypeError` opaque plus loin.
- La pile reste un état de processus : une bibliothèque qui appellerait
  `install()` l'imposerait à son appelant. La règle à documenter est simple —
  **une bibliothèque utilise `with`, une application peut `install()`**.
- La pile n'est pas propre à un fil d'exécution. Deux fils qui entrent dans des
  `with` différents se voient l'un l'autre. Une pile par fil (`threading.local`)
  réglerait le cas, mais `threading` n'existe pas en MicroPython (fiche 008) :
  la pile reste simple, et la limitation est documentée.

## Tests imposés

1. Aucune politique installée : comportement identique au défaut, sur les
   interpolations, `instantiateBGP` et les bindings (non-régression golden).
2. Politique par champ : datatype XSD, `IRI`, fonction Python ; champ non
   mentionné → défaut.
3. Un terme RDF déjà construit n'est **jamais** reconverti, politique ou non.
4. `dtype()` (après `^^`) reste insensible à la politique.
5. CSV de bout en bout : `for @bindings in csv.DictReader(f)` produit les termes
   typés attendus.
6. Élément non-mapping dans `for @bindings in …` → erreur nommant l'élément.
7. Performance : le banc de matérialisation (fiche 009) ne régresse pas
   mesurablement sans politique installée.

## Questions ouvertes

- L'ergonomie réelle du dictionnaire à clés hétérogènes (tuples et types) sur du
  code de conversion long : à revoir après le premier vrai jeu de règles écrit
  pour l'étude KGC.

## Voir aussi

- Fiche 017 (`@bindings` et `for @bindings in …`), fiche 003 (émission et
  coercition des interpolations), fiche 009 (banc de performance — `node()`
  est sur le chemin chaud), `ldpy/runtime.py` (`node`, `dtype`,
  `instantiateBGP`), `kgc/201` (l'étude KGC, premier bénéficiaire).
