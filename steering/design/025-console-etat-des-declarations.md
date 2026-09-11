# 025 — La console garde l'état des déclarations d'une entrée à l'autre

**Date** : 2026-09-03 · **Statut** : implémenté — trois bogues levés au passage

## Contexte

La console (`python -m ldpy`) transpile **une entrée à la fois** : chaque
ligne rendue à l'interpréteur devient un `Transpiler` neuf. Un fichier, lui,
est transpilé d'un seul tenant. Tout ce que le transpileur porte comme état
lexical doit donc être explicitement transporté d'une entrée à la suivante,
sans quoi la console n'est pas le même langage que le fichier.

Elle ne transportait que `@prefix` et `@base`. `@graph as g` posé dans une
entrée était perdu dans la suivante : le `+{ ... }` qui suit ne voyait aucun
graphe courant. C'est le symptôme rapporté.

Trois autres défauts se cachaient derrière celui-là, tous révélés parce que
la console est le seul appelant qui transpile un texte **sans passage à la
ligne final** :

1. `_graph_ws_inline` (et le saut de blancs après `global`/`nonlocal`) testait
   `self._peek() in " \t"`. En fin de tampon `_peek()` rend `""`, et
   `"" in " \t"` est **vrai** en Python : la boucle consommait zéro caractère,
   indéfiniment. `@graph as g` figeait la console — c'est bien « le `@graph`
   ne fonctionne pas », mais la cause n'était pas la portée ;
2. `_error` marquait `at_eof` sur la seule position du curseur. L'erreur
   « `+{ }` sans graphe courant » est levée après l'îlot, donc en fin de
   tampon : la console la prenait pour une entrée inachevée et attendait une
   suite qui ne pouvait rien réparer ;
3. `BOUND(` en fin de tampon passait le test `self._peek() not in "?$"` pour
   la même raison, et plantait ensuite sur un `AttributeError` au lieu de
   rendre une erreur de syntaxe.

## Choix

**Ce qui est une déclaration lexicale dans un fichier est une déclaration
lexicale dans la console.** `LdpyConsole` transporte donc, en plus des
préfixes et de la base : le graphe courant, les liaisons courantes, et le
compteur de variables fraîches (pour que deux entrées ne fabriquent pas deux
fois le même `_ldpy_g1`). Les déclarations faites **dans un bloc** meurent
toujours avec l'entrée : `_unwind_scopes(0)` s'en charge déjà, et c'est la
sémantique de la fiche 018.

Corollaires :

- appartenance à une chaîne testée en `in (" ", "\t")`, jamais `in " \t"` —
  la chaîne vide n'est pas un blanc ;
- `_error(..., incomplete=False)` pour les erreurs **sémantiques**, celles
  qui portent sur ce qui a déjà été lu : une suite d'entrée ne les répare
  pas, la console doit les afficher tout de suite ;
- `add_to` / `remove_from` ne rendent plus le graphe. `+{ }` et `-{ }` sont
  des **instructions** (fiche 014) ; en rendant le graphe, la console
  affichait son `repr` après chaque ajout.

## Conséquences

`tests/test_docs.py` repasse tous les blocs ``` ldpy ``` de la documentation
une seconde fois, **tapés ligne à ligne dans la console**. Les blocs qui
dépendent du collage (ligne blanche à l'intérieur d'un bloc indenté, chaîne
triple) sont sautés : `code.InteractiveConsole` ne les accepte pas davantage
pour du Python pur, ce n'est pas une dette de ldpy. Tout le reste tourne.

C'est ce test qui a la vraie valeur : il dit que la console et le fichier
exécutent le même langage, et il le redira à chaque snippet ajouté.
