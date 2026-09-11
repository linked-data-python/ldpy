# 024 — Formateur (pretty printer) des fichiers .ldpy

**Date** : 2026-09-03 · **Statut** : implémenté

## Contexte

Un langage sans formateur n'est pas outillé : « Format Document » et
`editor.formatOnSave` sont des gestes que tout le monde a dans les doigts, et
leur absence se remarque dès la première minute. Restait à décider **de quoi**
un formateur ldpy a un avis.

Un fichier `.ldpy` est du Python avec des îlots. Deux langages, donc deux
questions distinctes — et c'est en les séparant que la décision devient
simple.

## Options envisagées

1. **Écrire un formateur complet** (Python + RDF) à la main. Refusé sans
   hésiter : reformater du Python correctement est un projet à part entière,
   `black` y a passé des années, et le pilier R3 (transparence de l'hôte)
   exige que l'on ne diverge pas de lui d'un espace.
2. **Ne formater que les îlots**, en laissant le Python intact. Cohérent,
   mais inutilisable : l'utilisateur ne peut alors PAS formater son Python,
   puisque `black` ne sait pas lire un `.ldpy`. Le seul outil qui puisse le
   faire pour lui, c'est le nôtre.
3. **Déléguer le Python à `black`, masquer les îlots** — le principe du
   surligneur de la fiche 023 (« le surligneur est le transpileur »),
   appliqué au formatage. Retenu.

## Choix : le formateur est le transpileur (option 3)

`ldpy/formatter.py` : transpiler donne la **language map**, qui dit exactement
où sont les îlots dans le SOURCE. On remplace chacun par un substitut valide
en Python à sa place, `black` formate, on réinjecte les îlots là où les
substituts ont atterri.

### Trois propriétés qui tiennent lieu de spécification

Elles sont vérifiées sur tout le ldpy du dépôt — les exemples et les 102 blocs
de la documentation (`tests/test_formatter.py`, 372 tests) :

1. **Transparence de l'hôte.** Sans îlot, `format_source(s)` est *exactement*
   `black.format_str(s)`. Mesuré sur les modules de ldpy lui-même et sur un
   échantillon de la bibliothèque standard : 80 fichiers, zéro divergence.
   Le formateur n'a aucun avis sur Python — c'est la même discipline que R3.
2. **Idempotence.** Formater deux fois donne le même texte.
3. **Le sens ne bouge pas.** L'AST du Python transpilé est identique avant et
   après formatage. Un formateur qui change ce que fait le programme n'est pas
   un formateur.

Le point 3 admet **un relâchement, un seul, explicite** : le blanc à
l'intérieur du texte d'une requête `s{ }`, que le code émis embarque tel quel
et que SPARQL ignore par définition. Le test le formule ainsi (normalisation
des constantes chaîne) et vérifie *en plus* l'invariant **sans relâchement**
sur tous les extraits qui ne contiennent pas de `s{ }`.

### Le masquage, et le poids des substituts

Un substitut doit être valide **à la place** de l'îlot. Deux îlots portent une
forme syntaxique et non une expression, et leur substitut la porte aussi :

| îlot | substitut | pourquoi |
|---|---|---|
| `for @bindings [as b] in` | `for _L3 in` | sinon la boucle n'est plus une boucle |
| `from m import a, ex:, u: as v:` | `import _L4` | pour que black lui donne les lignes vides d'un **bloc d'imports**, pas celles d'une expression |
| tout le reste | `_L7` | un nom est valide partout où un îlot l'est |

Et surtout : **le substitut pèse ce que pèse l'îlot** (rallongé par des `_`).
C'est la doctrine du masquage de la fiche 023 — un substitut de même longueur
laisse le moteur délégué décider comme il aurait décidé sur le vrai texte.
Sans cela, black croit que tout tient sur une ligne, joint une compréhension,
et l'îlot réinjecté déborde de 30 colonnes. Un îlot **multiligne** ne peut par
construction pas tenir sur une ligne : son substitut reçoit un poids qui
dépasse la limite, ce qui préserve la coupure écrite par l'auteur.

Les noms de substitut sont choisis absents du source (`_L0`, `_L1`, … et un
`_` de plus tant qu'il y a collision) : le masquage doit être réversible.

## Ce que le formateur ne fait PAS aux îlots — et pourquoi

**Le corps d'un `g{ }`, `m{ }`, `s{ }` est recopié caractère pour caractère.**
Seules les **bordures** sont normalisées :

- les espaces de fin de ligne ;
- le rembourrage juste après `{` et juste avant `}` (`g{ex:s ex:p 1}` devient
  `g{ ex:s ex:p 1 }`, un îlot vide devient `g{ }`) ;
- les déclarations dont la grammaire est **close**, où aucun blanc ne peut
  être signifiant : `@prefix`, `@base`, `@graph`, `@bindings`, import de
  préfixes ;
- l'**indentation des lignes de continuation**, décalée avec l'instruction
  quand black change son niveau, de façon à préserver l'alignement voulu.

Trois raisons de s'arrêter là, dans l'ordre de leur poids :

1. **Turtle n'a pas de mise en page canonique.** Un graphe est souvent aligné
   à la main pour montrer sa structure — sujets en colonne, prédicats
   alignés. Reformater cela, c'est détruire de l'information que l'auteur a
   mise là exprès. Les formateurs sérieux laissent les DSL embarqués
   tranquilles (le SQL dans une chaîne, une expression régulière) pour la
   même raison.
2. **Le risque est asymétrique.** Normaliser les blancs autour de la
   ponctuation RDF demande de retokeniser le corps — et `.` est à la fois le
   séparateur de triplets et le point décimal de `1.5`. Une erreur ne donne
   pas une vilaine mise en page, elle donne un programme faux. Le bénéfice ne
   paie pas ce risque-là.
3. **Le chemin propre existe et reste ouvert** : le transpileur sait tokeniser
   un îlot (c'est son métier) et le lexer Pygments de la fiche 023 en produit
   déjà un flux de jetons sans erreur sur toute la documentation. Un
   re-formatage RDF complet serait « rejoindre ce flux avec l'espacement
   voulu », sans retokeniser quoi que ce soit. C'est le volet suivant, décidé
   *pas maintenant* plutôt que bâclé.

## Dépendance : black, optionnelle

Extra `[format] = ["black>=24"]`, comme Pygments l'est pour la coloration :
**rien dans ldpy n'importe black** hors de `ldpy/formatter.py`, et seulement
à l'appel. Son absence donne un message actionnable, le serveur LSP
**n'annonce alors pas** la capacité de formatage (plutôt que de l'annoncer et
d'échouer), et la suite de tests s'ignore (`importorskip`).

`ruff format` a été examiné : plus rapide, mais piloté par sous-processus (pas
d'API Python stable), là où le serveur LSP tient déjà un interpréteur Python
en main et appelle `black.format_str` en direct. Le point de couplage est
**une fonction** (`_format_python`) : en changer plus tard coûte trois lignes.

## Conséquences

- Trois portes d'entrée, un seul moteur : `ldpy-format` (CLI, avec `--check`
  et `--diff` pour l'intégration continue), `textDocument/formatting` (donc
  « Format Document » et `formatOnSave` dans **tout** éditeur LSP, pas
  seulement VS Code), et le réglage `ldpy.lineLength` de l'extension.
- Un document fautif **ne se formate pas** : ni edit ni texte inventé. Les
  diagnostics disent déjà pourquoi, et un formateur qui devine est un
  formateur qui perd du travail.
- La longueur de ligne du serveur est passée à son démarrage ; l'extension
  redémarre le serveur quand le réglage change, au lieu de demander à
  l'utilisateur de le faire.
- Le formateur devient un **test de la language map** : si un jour un îlot
  était mal borné, l'invariant d'AST le dirait immédiatement.

## À reconsidérer

- Le re-formatage complet des corps d'îlots par le flux de jetons (ci-dessus).
- `--check` en intégration continue sur `examples/` et les blocs de `docs/` :
  la documentation deviendrait formatée par construction.
- Le tri des imports (isort) n'est pas fait — black ne le fait pas non plus,
  et un import de préfixes n'a pas d'ordre canonique évident.
