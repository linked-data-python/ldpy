# 028 — L'espace des graphes nommés : ce que les îlots ne couvrent pas

**Date** : 2026-09-03 · **Statut** : constats établis — arbitrage à ouvrir
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

## Ce qui reste à trancher

Faut-il une forme de lecture quadruplet — `m{ }` sur un `Dataset`, avec une
position de graphe — ou la frontière actuelle est-elle la bonne ?

Deux éléments pour l'arbitrage, et ils ne vont pas dans le même sens. Contre :
une seule région de la campagne l'a demandé, et `s{ }` couvre déjà le besoin
dès qu'on accepte d'écrire une requête. Pour : la fiche 016 a montré que ce
qui coûte dans le corpus n'est pas la requête mais la **lecture simple**, et
il n'y a pas de raison que ce soit différent d'un cran plus haut. Le chiffre
manque : `surface.py` ne compte pas les sélecteurs appliqués à un `Dataset`
séparément de ceux appliqués à un `Graph`. **Le mesurer d'abord**, décider
ensuite.

TODO Claude: mesurer d'abord. à priori je préfère ne pas ajouter de forme de lecture quadruplet, et voir si la demande vient de la communauté.