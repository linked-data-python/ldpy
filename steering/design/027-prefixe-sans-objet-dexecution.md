# 027 — `@prefix` sans objet d'exécution : les issues possibles

**Date** : 2026-09-11 · **Statut** : implémenté — livré en ldpy 0.6.3, portée et STRLANG/STRDT depuis

## Contexte

L'étude du corpus a fait remonter, de loin, le manque le plus attesté du
langage — et le seul qui traverse plusieurs strates. Le détail des cas est en
fiche [012](012-limites-revelees-par-le-corpus.md) ; on n'en garde ici que ce
qui commande la décision.

**La cause est unique.** `@prefix` est purement lexical (fiche
[004](004-semantique-prefix-base.md)) : il pose une entrée dans une table de
transpilation et ne produit **aucune valeur Python**. Tout code qui a besoin
que le `Namespace` *survive comme objet* est donc hors d'atteinte.

**Les formes rencontrées sur du code réel sont quatre**, et elles n'appellent
pas les mêmes réponses :

| # | forme | ce que le code fait | vu sur |
|---|---|---|---|
| 1 | `class NS(DefinedNamespace)` | rdflib relit `cls._NS` à **chaque** accès d'attribut, potentiellement dans un module tiers | `IBM/kif` (×2) |
| 2 | `Namespace` rangé dans un dict / registre exporté | le mapping est la valeur publique du module | `IBM/kif` |
| 3 | `g.bind(prefix, NS)` | la liaison prend **l'objet**, souvent avec `global` | `BONSAMURAIS/arborist` (19/19), `bloodbee/jrt`, `MaxBerktoldRWTH/BRICKbuilder` |
| 4 | `initNs=` alimenté par un dict d'exécution | les préfixes ne sont connus qu'à l'exécution | `IndustryFusion/DigitalTwin`, `interior-night/kglab` (strate `bind_initbindings`) |

**Ce qui n'est PAS bloqué**, et qu'il faut redire pour ne pas surestimer le
manque : un `Namespace` qui ne fait que *produire des `URIRef`* n'est pas
concerné, les `URIRef` voyageant comme des variables ordinaires ; et un
`initNs` dont tous les préfixes sont déjà pré-liés par rdflib est inerte.
Deux régions sur trois d'un lot de `ns_def_local` étaient directement
exprimables pour cette raison.

Le préfixe dynamique existe déjà pour une valeur (`@prefix dyn: f<http://{host}/ns#> .`) :
ce qui manque en (4) n'est donc pas « un préfixe calculé » mais « un
**ensemble** de préfixes de taille inconnue ».

## Décision

**B — le graphe désigné hérite des préfixes en portée.** `@graph mine` lie
sur `mine` les préfixes déclarés au moment de la désignation, exactement
comme `g{ }` le fait déjà sur le graphe qu'il crée. Cela supprime la raison
d'être de la plupart des `g.bind(prefix, NS)` — ils sont là pour que la
**sérialisation** soit lisible, pas pour manipuler un objet. Sur `arborist`,
les dix-neuf `bind()` sont exactement de cette espèce ; ils deviennent
inutiles.

**D — `@prefix … as NOM` lie aussi un nom Python.** `@prefix ex: <…> as EX .`
est à la fois la déclaration lexicale et la liaison d'un nom Python à
l'objet `Namespace`. La forme s'étend au préfixe **dynamique** : `@prefix
ifcInst: f<{base_inst}ifcInst:> as ifc_inst_ns .` (cas réel,
`MaxBerktoldRWTH/BRICKbuilder`, dont toutes les IRI sont calculées à
l'exécution).

Comportements à connaître :

- **La position de la déclaration ne compte pas** : tant qu'un graphe est le
  graphe courant, un `@prefix` déclaré *après* le `@graph` lie sur lui comme
  ceux qui l'étaient au moment de la désignation. Les deux ordres d'écriture
  sérialisent donc pareil. C'était un piège tant que la position décidait, et
  un piège silencieux : rien ne signalait le préfixe manquant, la
  sérialisation était seulement moins lisible.
- **rdflib ne remplace pas un préfixe existant** : si le graphe désigné porte
  déjà `ex:` pour une AUTRE IRI, `bind()` crée `ex1:` plutôt que d'écraser —
  on ne vole pas le préfixe de l'appelant.

`as` lève la limite là où l'objet doit survivre ET où le préfixe sert aussi
lexicalement, pas partout où un `Namespace` est construit : une région où le
code redeviendrait syntaxiquement traduisible mais sans qu'un seul nom
préfixé soit écrit (`IndustryFusion/…/Entity.__init__`) reste volontairement
`not-expressible` plutôt que forcée.

## Le suffixe RDF sur une variable : refusé

`?v@lang` et `?v^^dt` sont refusés — le langage ne coerce pas. `{expr}@en` a
un sens parce que la valeur Python est la **forme lexicale** et que le
suffixe dit comment la lire ; une variable, elle, est déjà liée à un **terme
complet**, il n'y a rien à interpréter. Autoriser le suffixe demanderait de
décider, à l'exécution, quoi faire d'une variable liée à une IRI — inventer
une sémantique là où le programme n'en exprime aucune.

`_g_var` refuse `?v@lang` et `?v^^dt` sur place, avec un message qui nomme la
règle et le contournement (`{b.raw["v"]}@en`) — l'échec existait déjà mais ne
nommait rien avant (« `'}'` attendu pour fermer l'îlot de graphe », seize
colonnes après le vrai fautif). Le refus atteint `+{ }`, `-{ }` et `m{ }`,
les trois îlots qui lient des variables ; `?v` nu et `{expr}@en` continuent
de fonctionner.

### Ce que le refus laisse ouvert

Un refus n'est défendable que si dire la chose explicitement reste possible.
`STRLANG(?v, "en")` et `STRDT(?v, dt)` sont ce chemin : du SPARQL 1.1
standard, qui dit ce que le suffixe ne dit pas — prendre la **forme lexicale**
de la variable et la relire comme littéral étiqueté ou typé.

Les deux fonctions manquaient à `e{ }` ; elles y sont. Périmètre exact :

- **`+{ }` et `-{ }` : oui**, à la condition ordinaire de tout `e{ }` en
  position de terme dans ces îlots — un `@bindings` en portée. Sans lui, il
  n'y a aucune solution à instancier et le triplet n'est pas produit ; c'est
  la sémantique des gabarits (fiche 017), et elle vaut pour `CONCAT` comme
  pour `STRLANG`.
- **`m{ }` : non**, et par décision, pas par omission : `e{ }` comme filtre
  d'appariement est hors périmètre (fiche 017). Les deux nouvelles fonctions
  n'ouvrent pas cette porte, et un test le tient.

Elles refusent un argument qui porte déjà une étiquette ou un type — SPARQL
1.1 n'y donne aucun résultat, ici c'est une erreur nommée, comme partout
ailleurs dans le module.

## Frontières assumées

- **Les préfixes connus seulement à l'exécution restent hors du langage**
  (option E écartée) : les autoriser romprait la vérification des noms
  préfixés à la transpilation, que la fiche 004 tient pour centrale, et qui
  permet aujourd'hui l'avertissement « préfixe non déclaré ». Une requête
  dont les préfixes ne sont connus qu'à l'exécution est de la même famille
  que celle dont la structure est assemblée à l'exécution — hors du domaine
  du langage, ce qui est un résultat, pas un trou.
- **Interopérer avec `DefinedNamespace` reste écarté** (option F) : le
  reproduire lierait le langage à un détail d'implémentation rdflib
  (métaclasse, `_NS` relu à chaque accès), contre la règle « zéro dépendance
  au parsing de rdflib » (fiche 001). Un module qui définit un
  `DefinedNamespace` est un module de vocabulaire ; sa migration vers ldpy
  n'a pas d'intérêt.

## Ce que le rejugement des paires a donné

Sept régions passent de `not-expressible` à `directly-expressible`. Le cas
emblématique, `BONSAMURAIS/arborist`, perd ses **dix-neuf** `g.bind()` et voit
ses dix-neuf `global` servis par `global @prefix … as EX .`.

**Deux verts creux découverts au passage**, antérieurs à ce chantier :
`arborist` et `JustlyAI` comparaient un graphe dont aucun triplet ne dépend
des préfixes, si bien qu'une traduction cassée restait verte. Leurs pilotes
rendent maintenant les liaisons du graphe et les globals exportés.

## Voir aussi

Fiche 012 (constat initial du corpus), fiche 014 (graphe courant), fiche 004
(sémantique de `@prefix`/`@base`), fiche 001 (zéro dépendance au parsing de
rdflib).
