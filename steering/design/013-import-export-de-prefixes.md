# 013 — Import et export de préfixes entre modules

**Date** : 2026-09-03 · **Statut** : implémenté — extension aux `Namespace` rdflib ordinaires à trancher

**Origine** : décision D1 de la fiche `corpus/402` (analyse de surface) ;
manque structurel 3 de la fiche 012.

## Contexte

`@prefix` est une déclaration **lexicale**, consommée par le transpileur
(fiche 004). Elle ne franchit pas la frontière du fichier : un module ldpy qui
veut écrire `brick:Class` doit redéclarer `@prefix brick:` même si le module
voisin l'a déjà fait.

L'étude de surface montre que c'est exactement le défaut que le code rdflib réel
contourne à la main, et à grande échelle :

- **1 271 imports d'un namespace depuis un autre module du même dépôt**, dans
  563 fichiers de **65 dépôts**. Le motif canonique est `bricksrc/namespaces.py`
  chez BrickSchema : un module dont le seul rôle est d'exporter des préfixes.
- 3 672 définitions de namespace, dont **1 061 (29 %) à l'intérieur d'une
  fonction** — donc redéclarées à chaque appel, faute d'un endroit naturel.
- **431 couples (IRI, dépôt) déclarés dans plusieurs fichiers du même dépôt**
  (667 fichiers) : la même déclaration recopiée.
- 560 définitions (15 %) construisent leur IRI par **calcul** (concaténation,
  variable d'environnement, `urljoin`).

Le besoin est donc massif, et déjà résolu à la main par un module Python de
préfixes. Un `Namespace` importé n'est qu'un objet — il ne rend pas
`brick:Class` **écrivable**. Sans export, ldpy hérite du défaut au lieu de le
corriger.

## Fonctionnement

### 1. Tout `@prefix` de niveau module est exporté

Pas de mot-clé nouveau, pas de forme `export @prefix`. Un `@prefix` déclaré
dans une fonction reste privé — sa portée est déjà celle du bloc (fiche 004),
c'est la seule façon de garder un préfixe pour soi, et elle suffit.

### 2. Un nom préfixé dans la liste d'import désigne un préfixe

```python
from myproject.vocab import something, brick:, unit:
from myproject.vocab import unit: as u:            # forme alias
```

`brick:` et `unit: as u:` sont des erreurs de syntaxe en Python : la doctrine de
la fiche 002 — n'étendre que là où Python est illégal — est respectée sans
mot-clé. Le `:` de l'alias est nécessaire : `as u` sans lui suggérerait un nom
Python lié à un objet `Namespace`, alors que préfixes et noms Python restent
deux espaces distincts.

`import myproject.vocab` et `from myproject.vocab import *` n'importent aucun
préfixe ; `@base` ne s'exporte pas.

### 3. Un seul régime : l'import est dynamique

Le point dur apparent — le transpileur a besoin de l'IRI au moment où il
compile, alors qu'un import est un objet d'exécution — se dissout si l'on
renonce à connaître l'IRI d'un préfixe importé. **La règle est unique** :

> le transpileur inline l'IRI quand il la tient dans le fichier qu'il compile ;
> sinon il résout à l'exécution, à travers la liaison de namespace.

Un préfixe importé n'est donc jamais inliné, quelle que soit la forme de sa
déclaration dans le module d'origine. L'instruction d'import **déclare
lexicalement le nom du préfixe** — c'est tout ce dont le transpileur a besoin
pour savoir que `brick:Class` est un nom préfixé et non du Python. Le
transpileur ne lit jamais le module importé.

Les préfixes à IRI calculée (15 % des définitions) cessent du même coup d'être
un cas particulier : ils empruntent exactement le même chemin.

```python
@prefix ex: f<http://{base}/ns#> .        # IRI calculée, résolue à l'exécution
```

Contre-parties assumées de la règle unique : `brick:Class` n'est plus une
constante de compilation (un appel de plus, aucune vérification possible sur
l'IRI elle-même — seule reste l'erreur « préfixe non déclaré », détectée
statiquement) ; l'ordre des imports compte, comme pour n'importe quel import
Python ; le prologue SPARQL de la fiche 015 ne peut plus être construit à la
transpilation pour ces préfixes, il se construit à l'exécution depuis les
liaisons en portée (validation syntaxique avec un prologue synthétique) ; un
module ré-exporte ce qu'il a importé, ce qui rend l'ensemble exporté moins
évident à lire.

Option écartée : inliner l'IRI d'un préfixe importé en lisant la source du
module importé à la transpilation (l'import se comportant comme un
`#include`) — écartée pour la machinerie que cela demande (suivi des chaînes
de ré-exportation, détection de cycle, ordre de construction) et surtout le
piège du `const` inliné : une IRI qui change dans `vocab.ldpy` et des
importateurs qui gardent l'ancienne jusqu'à leur retranspilation.

## Code émis

Une ligne source reste une ligne émise (language map préservée). Pour

```python
from myproject.vocab import something, brick:, unit: as u:
```

le transpileur émet

```python
from myproject.vocab import something, __namespaces__ as _ldpy_ns0; _ldpy_ns_brick = _ldpy_ns0['brick']; _ldpy_ns_u = _ldpy_ns0['unit']; __namespaces__.update(brick=_ldpy_ns_brick, u=_ldpy_ns_u)
```

Deux liaisons distinctes, comme la fiche 004 le fait déjà pour une déclaration
locale :

- une **variable Python fraîche** par préfixe dynamique, qui porte la
  résolution — nommée `_ldpy_ns_<préfixe>_<n>` (`n` : compteur par fichier ;
  la table du module importé est reçue sous `_ldpy_nsi<n>`, une par
  instruction d'import) ; un nom de préfixe pouvant contenir `-` (interdit en
  kwarg), `__namespaces__.update({...})` s'écrit par dict littéral ;
- l'entrée dans `__namespaces__`, qui ne sert qu'à la sérialisation (`nm.bind`),
  mise à jour **une fois par ligne d'import** (pas groupée en fin de module :
  la correspondance ligne source → ligne émise est structurante, fiche 005).

La variable fraîche est ce qui donne gratuitement la **portée par bloc** : un
import dans une fonction lie une variable locale, un import au niveau module lie
un global — la portée lexicale du transpileur et la portée Python coïncident, et
le masquage fonctionne sans pile d'exécution. C'est aussi ce qui rend
gratuits `global @prefix` et `nonlocal @prefix` (fiche 018).

Un usage de préfixe compile alors selon ce que le transpileur tient :

| déclaration en portée | `brick:Class` compilé en |
|---|---|
| `@prefix brick: <https://…>` (locale, littérale) | `_ldpy_.URIRef('https://…Class')` — inliné |
| importée, ou locale à IRI calculée | `_ldpy_.pname(_ldpy_ns_brick, 'Class')` |

`_ldpy_.pname(ns, local)` concatène et coerce ; la partie locale interpolée
(`brick:{x}`) passe par le même appel, avec l'échappement de `firi()`.

`__namespaces__` commençant par un souligné, `from m import *` l'ignore déjà —
mais le transpileur **refuse `__namespaces__` dans `__all__`**, qui écraserait
la table de l'importateur par celle de l'importé et casserait silencieusement sa
sérialisation.

La détection d'un import de préfixes est un simple « un `:` après le mot-clé
`import` » — jamais du Python valide à cette position.

Le message d'erreur « préfixe non déclaré » nomme la ligne d'import quand le
préfixe *aurait pu* venir d'un import du fichier (nom présent dans un module
importé mais non listé), et la déclaration manquante sinon — il cite la
ligne, pas le module, c'est ce que l'utilisateur peut corriger.

## Tests imposés

1. `from m import brick:` : `brick:Class` écrivable, résolu à l'exécution ;
   `brick:` hors de la portée de l'import → comportement de la fiche 004
   (texte laissé en Python, warning si déclaré plus haut).
2. Forme alias `unit: as u:` ; mélange de noms Python et de préfixes sur la
   même ligne d'import ; import parenthésé multiligne.
3. `import m` et `from m import *` n'importent aucun préfixe.
4. Import dans une fonction : portée limitée au bloc, masquage d'un préfixe
   homonyme du module, restauration à la sortie.
5. Préfixe à IRI calculée (`f<…{x}…>`) : même chemin de résolution qu'un
   préfixe importé ; changement de la valeur entre deux évaluations.
6. Ré-exportation transitive (a importe de b qui importe de c).
7. `__namespaces__` dans `__all__` → erreur de transpilation avec le motif.
8. Deux modules aux tables différentes : pas de fuite (non-régression fiche 004).
9. Language map et golden (fiche 006) sur la ligne d'import émise.

Implémentation : commit `0191c78`, 20 tests (`tests/test_prefix_import.py`).

## Limite révélée par le corpus : une condition d'applicabilité

`from m import brick:` ne fonctionne que si le module `m` **est un module
ldpy**, c'est-à-dire s'il expose `__namespaces__`. Sur les quatre régions
étudiées par la strate `ns_import_project` (fiche `corpus/403`) :

- `umd-lib/plastron` — une douzaine de namespaces de projet employés
  massivement **en position de terme** (`owl.sameAs`, `edm.Agent`,
  `bibo.Letter`…). `plastron.namespaces` n'exporte rien de tel : aucun ne
  qualifie ;
- `pyiron/semantikon` — même situation, `semantikon.ontology` non plus ;
- `statnett/KGraphPy` — le seul cas créditable, et seulement parce que le
  module de namespaces était assez petit pour être reproduit dans le contexte
  de la région ; le namespace effectivement importé s'est en outre révélé
  **inutilisé comme terme**, donc rien n'a été crédité.

**La densité d'usage ne suffit pas.** Trois régions sur quatre emploient
vraiment un namespace de projet en position de terme et n'ont pourtant pas
droit à la construction, parce qu'un paquet tiers déjà publié ne s'édite pas.
Ce n'est pas une limite d'expressivité mais une condition d'applicabilité :
`ns_import_project` mesure d'abord la rareté de `__namespaces__` dans la
nature, ensuite seulement le gain de la notation — à énoncer tel quel dans
l'article.

## Question ouverte : reconnaître un `Namespace` rdflib ordinaire

Deux suites possibles, à arbitrer, qui rejoignent la fiche
[027](027-prefixe-sans-objet-dexecution.md) :

1. **reconnaître un `Namespace` rdflib ordinaire** à l'import — `from
   plastron.namespaces import edm:` irait chercher l'objet `Namespace` exporté
   et en dériverait la liaison. C'est la voie qui débloque du code existant
   sans rien demander à l'amont, et la seule qui fasse une différence
   mesurable sur le corpus ;
2. **déclarer côté consommateur** — l'utilisateur écrit lui-même le `@prefix`
   correspondant, ce qui est la situation actuelle et n'a rien de scandaleux :
   une ligne par namespace, une fois par fichier.

## Cas voisin : une partie locale qui n'est pas un PN_LOCAL

Rencontré sur `mhrimaz/aasbrain` : les prédicats du modèle AAS s'écrivent
`AAS["Referable/category"]`. La partie locale contient une barre oblique,
**illégale dans un nom préfixé Turtle** — la voie `@prefix` est donc fermée,
quel que soit l'import. La sortie est `@base` plus des IRI relatives
`<Referable/category>`, qui transpile et se lit bien. C'est la réponse
générale au « ma partie locale n'est pas un `PN_LOCAL` », à documenter.

## Voir aussi

- `corpus/402` (les mesures et la méthode), fiche 004 (portée par bloc de
  `@prefix` — la base), fiche 002 (n'étendre que là où Python est illégal),
  fiche 012 (manque structurel 3), fiche 015 (l'îlot SPARQL, dont le prologue
  dépend de cette décision), fiche 018 (`global` / `nonlocal` sur `@prefix`).
