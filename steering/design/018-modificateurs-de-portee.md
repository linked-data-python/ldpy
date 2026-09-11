# 018 — `global` et `nonlocal` sur les déclarations d'îlot

**Date** : 2026-09-03 · **Statut** : implémenté

**Origine** : les fiches 004, 013, 014 et 017 posent la même question de portée ;
elle appelle une réponse unique, qui est ici plutôt que répétée quatre fois.

## Contexte

Quatre déclarations d'îlot ont une **portée lexicale par bloc** : `@prefix` et
`@base` (fiche 004), `@graph` (fiche 014), `@bindings` (fiche 017). Une
déclaration prend effet de sa position à la fin de la suite qui la contient, et
la sortie du bloc restaure la liaison antérieure.

C'est le bon défaut, et c'est celui de Python. Mais Python ne s'en tient pas là :
il donne `global` et `nonlocal` pour écrire *délibérément* dans une portée
englobante. Le motif est courant et légitime — préparer une valeur dans une
boucle, puis sortir par un `break` en la laissant établie :

```python
for cand in candidats:
    if convient(cand):
        graphe_choisi = cand          # en Python, la boucle ne crée pas de portée
        break
```

Avec une portée par bloc, l'équivalent en déclaration d'îlot ne survivrait pas à
la sortie de la boucle. Il manque le moyen de dire « cette déclaration-là vise
plus haut ».

## Fonctionnement

Les modificateurs `global` et `nonlocal` de Python s'appliquent aux quatre
déclarations, avec exactement leur sens Python : **la déclaration s'installe
dans la portée désignée au lieu du bloc courant**, et survit donc à la fermeture
des blocs qui la contiennent.

```python
global @prefix ex: <http://example.org/v2#> .
global @base <http://example.org/> .
global @graph as g
global @graph <http://ex.org/g1> as g
global @bindings b
nonlocal @graph self.graphes[i]
```

La forme est **illégale en Python** (`global` ou `nonlocal` doit être suivi d'une
liste de noms, jamais d'un `@`), donc la doctrine de la fiche 002 — n'étendre
que là où Python est illégal — est respectée sans mot-clé nouveau.

### Portée visée

- `global @…` : la portée **module**. La déclaration y prend effet, lexicalement,
  de sa position jusqu'à la fin du fichier, et n'est pas restaurée à la sortie
  des blocs englobants.
- `nonlocal @…` : la **portée englobante la plus proche** qui déclare déjà cette
  entité (ce préfixe, ce graphe courant, ce binding courant). Comme en Python,
  l'absence d'une telle portée est une **erreur de transpilation**, et non une
  création silencieuse au niveau module.

Une déclaration modifiée reste une déclaration : elle produit la même liaison,
émet le même code, et suit les mêmes règles de désambiguïsation décorateur
(fiche 004, décision 5).

La règle qui gouverne les cas limites est unique : **faire ce que Python
fait**. Si la construction équivalente est du Python valide, elle passe sans
erreur ni avertissement.

- **`global @prefix` au niveau module** est accepté sans rien dire : `global x`
  au niveau module est du Python valide et sans effet.
- **`global @graph EXPR`** (désignation, sans `as`) est autorisé : la liaison
  visée est celle du graphe courant, rien ne distingue ce cas du précédent.
- **Pas d'avertissement de redéclaration** sur une déclaration modifiée : c'est
  l'équivalent exact de `global x; x = 1`, qui ne provoque rien en Python. Le
  modificateur *dit* que l'on écrit ailleurs — c'est une intention explicite,
  pas une maladresse. L'avertissement de la fiche 004, décision 3, reste réservé
  aux redéclarations non modifiées, au même niveau.

## Pourquoi c'est presque gratuit

Les fiches 013, 014 et 017 émettent toutes la liaison dans une **variable Python
fraîche** — c'est ce qui leur donne la portée par bloc sans pile d'exécution.
Le modificateur se transmet donc tel quel à cette variable :

```python
global @graph as g
```
```python
global _ldpy_g_3; _ldpy_g_3 = g = _ldpy_.Graph()
```

La portée Python fait le travail à l'exécution ; côté transpileur, il suffit
d'installer la liaison dans la portée visée de la table lexicale au lieu du bloc
courant. Aucune mécanique nouvelle, ni à la compilation ni à l'exécution.

Le cas de `@prefix` et `@base` est plus simple encore quand l'IRI est littérale :
la résolution étant entièrement lexicale (fiche 004), `global @prefix` ne touche
que la table du transpileur — et l'entrée `__namespaces__` correspondante, qui
est déjà un dictionnaire de module.

`nonlocal @graph as g2` ne peut pas émettre `nonlocal g2` : Python exige que le
nom existe déjà dans la portée englobante. L'émission **réutilise la variable
de la liaison englobante** — le principe déjà retenu pour les préfixes
dynamiques (fiche 013) : `nonlocal g; g2 = g = ...`. C'est cette variable-là que
le code du dehors lit ; `g2` reste un alias local.

## Options écartées

1. **Ne rien faire** et demander de déclarer au niveau module : impossible quand
   la valeur n'existe qu'à l'intérieur du bloc (le graphe choisi par la boucle,
   la ligne de CSV en cours).
2. **Rendre la portée dynamique** (la déclaration survit toujours à son bloc) :
   rejetée par la fiche 004, qui rend le masquage impossible et fait dépendre
   la résolution du flot d'exécution.
3. **Un mot-clé propre à ldpy** (`@prefix! `, `@global prefix`) : Python a déjà
   les deux mots-clés, ils sont connus, et leur sémantique est exactement celle
   voulue.

## Conséquences

- Les quatre déclarations gagnent la même capacité, avec la même orthographe :
  une seule règle à documenter et à enseigner.
- La correspondance « portée d'îlot = portée Python » devient complète, et c'est
  un argument de plus pour l'avoir bâtie sur des variables émises plutôt que sur
  une table d'exécution.
- Un `global @prefix` dans un bloc non exécuté conserve son effet **lexical**
  (la résolution des termes est faite à la transpilation) alors que la liaison
  runtime `__namespaces__` manquera — c'est la nuance déjà documentée par la
  fiche 004, décision 4.

## Tests imposés

1. `global @prefix` dans une fonction : le préfixe est visible après la fonction,
   au niveau module ; sans `global`, il ne l'est pas (non-régression fiche 004).
2. `global @graph as g` dans une boucle suivie d'un `break` : le graphe courant
   reste établi après la boucle.
3. `nonlocal @graph` dans une fonction imbriquée : modifie la liaison de la
   fonction englobante, pas celle du module.
4. `nonlocal @bindings` sans portée englobante déclarante → **erreur de
   transpilation**, message vérifié.
5. `global` / `nonlocal` sur `@base`, avec résolution relative correcte des IRIs
   qui suivent.
6. Interaction avec `for @bindings in …` (fiche 017) : un `global @bindings` dans
   le corps de la boucle survit à la boucle, la forme `for @bindings in` non.
7. Non-régression Python : `global x`, `nonlocal x`, `global x, y` intacts ;
   `global` en fin de ligne suivi d'un `@décorateur` à la ligne suivante.
8. Golden + identité + exécution (fiche 006) ; language map exacte.

Implémentation : commit `7564b65`, 15 tests (`tests/test_scope_modifiers.py`).

## Voir aussi

- Fiche 004 (portée par bloc de `@prefix` / `@base` — la base), fiche 013
  (préfixes importés, portés par une variable émise), fiche 014 (`@graph`),
  fiche 017 (`@bindings`), fiche 002 (n'étendre que là où Python est illégal).
