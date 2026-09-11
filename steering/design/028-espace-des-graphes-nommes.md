# 028 — L'espace des graphes nommés : ce que les îlots ne couvrent pas

**Date** : 2026-09-11 · **Statut** : tranché — pas de forme quadruplet, la mesure ne la justifie pas
**Origine** : campagne de traduction du 2026-09-03 (fiche `corpus/403`),
régions `RDFLib/pyLODE`, `ktbs/rdfrest`, `jupyter-naas/abi`. Détache de la
fiche [012](012-limites-revelees-par-le-corpus.md) un manque qui n'avait pas
de fiche à lui.

## Contexte

Tous les îlots de ldpy sont **portés par un graphe** : `@graph` en désigne un
(fiche 014), le suffixe d'appel en impose un autre (fiche 019), et `+{ }`,
`-{ }`, `m{ }` opèrent dedans. Cette unité est celle de rdflib `Graph`.

rdflib a un second espace, que le corpus emploie : `Dataset` /
`ConjunctiveGraph`, ses quadruplets, ses `contexts()`, et la clause `GRAPH ?g`
côté SPARQL. Le graphe n'y est plus un contexte ambiant mais **une valeur que
le code manipule** — on itère sur les graphes, on les filtre, on lit le nom du
graphe où une solution a été trouvée.

## Ce que la campagne a montré

Trois situations, trois issues différentes, et c'est la frontière qui compte.

1. **Désigner un graphe nommé pour y écrire : couvert.** `@graph` accepte une
   expression (fiche 014), donc `@graph ds.graph(URIRef(iri))` fonctionne et la
   région redevient ordinaire — un seul site d'écriture, un `+{ }` dedans
   (`jupyter-naas/abi`, `_add_version`).
2. **Interroger l'espace des graphes : couvert par `s{ }` seul.** `GRAPH ?g
   { … }` est du SPARQL, donc l'îlot SPARQL le porte sans rien de spécial. La
   région `ktbs/PrefixConjunctiveView.contexts` en relève — ce qui l'a rendue
   `not-expressible` est une autre cause (le texte de requête n'est pas
   littéral, fiche 015), pas l'espace des graphes.
3. **Lire un quadruplet hors SPARQL : découvert.** `db.value(iri, SH.order)`
   sur un `Dataset` (`RDFLib/pyLODE`, `Query.load_component_model`) n'a aucune
   forme d'îlot : `m{ }` lit un `Graph`. La traduction fidèle garde
   `.value()` en rdflib natif, avec seulement le terme réécrit en `sh:order`.

## Le constat

**Ce n'est pas une lacune uniforme, c'est un espace couvert par un seul îlot.**
L'écriture s'en sort par `@graph expr`, l'interrogation par `s{ }` ; seul le
chemin sans requête — les sélecteurs rdflib appliqués à un `Dataset` — reste
en rdflib. La documentation le dit déjà ; ce que la campagne ajoute, c'est
qu'une région peut être **correctement traduite en gardant du rdflib**, et que
ce n'est alors ni un échec ni une dégradation.

## La mesure

`surface.py` compte désormais les sélecteurs appliqués à un `Dataset`
séparément (`trav_on_dataset`, strate de `corpus/403`). Sur les 444 dépôts du
corpus :

| | sites | dépôts |
|---|---|---|
| sélecteurs, tous receveurs | 7 870 | 1 033 fichiers |
| **dont sur un `Dataset`** | **270** | **23** |

**3,4 % des lectures, dans 5 % des dépôts** — et concentrées : `triplify_csv`
et `shapes-of-you` en portent 132 à eux deux, soit la moitié.

La ventilation par sélecteur est ce qui tranche :

| sélecteur | sites |
|---|---|
| `triples` | 96 |
| `objects` | 56 |
| `subjects` | 51 |
| **`quads`** | **32** |
| `value` | 30 |
| autres (`subject_objects`, `predicates`, `predicate_objects`) | 5 |

**Seuls 32 sites sur 270 lisent réellement un quadruplet.** Les 238 autres
sont des sélecteurs de triplets ordinaires, appelés sur un `Dataset` parce
que c'est l'objet que le code a sous la main — ils lisent l'union ou le
graphe par défaut, sans jamais nommer de graphe. Ils ne demandent aucune
position de graphe : ils demandent que `@graph` accepte un `Dataset`, ce
qu'il fait déjà, puisqu'il accepte une expression (fiche 014).

## Décision : pas de forme de lecture quadruplet

La frontière actuelle est la bonne. L'argument « pour » reposait sur la
fiche 016 — ce qui coûte dans le corpus est la lecture simple, pas la requête
— et il tombe : la lecture simple *sur un Dataset* est de la lecture de
triplets, déjà couverte. Le besoin proprement quadruplet est de 32 sites dans
le corpus entier, et `s{ }` avec `GRAPH ?g { … }` le porte dès qu'on accepte
d'écrire une requête.

Ajouter une position de graphe à `m{ }` coûterait une syntaxe de plus dans
l'îlot le plus utilisé du langage, pour 0,4 % des lectures. **On attend que
la demande vienne de la communauté** : c'est un ajout qu'on pourra toujours
faire, alors qu'une syntaxe posée trop tôt ne se retire pas.