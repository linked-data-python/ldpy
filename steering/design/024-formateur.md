# 024 — Formateur (pretty printer) des fichiers .ldpy

**Date** : 2026-11-01 · **Statut** : implémenté

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

Le point 3 admet **un relâchement, un seul, explicite** : le texte d'une
requête `s{ }`, que le code émis embarque tel quel, est comparé jeton par
jeton — SPARQL ignore son blanc et la casse de ses mots-clés. Le test le
formule ainsi (`_canonical`) et vérifie *en plus* l'invariant **sans
relâchement** sur tous les extraits qui ne contiennent pas de `s{ }`.

Le point 3 est aussi tenu **à chaque exécution**, pas seulement par les
tests : le formateur retranspile son résultat et le compare au même fichier
formaté corps recopiés. S'ils diffèrent, c'est la seconde version qui sort.
La comparaison se fait contre ce fichier-là, et non contre l'original, parce
que black lui-même change parfois l'AST (un docstring tabulé réindenté, un
préfixe `u''` retiré) : la garde ne doit juger que la mise en page des îlots.

### Le masquage, et le poids des substituts

Un substitut doit être valide **à la place** de l'îlot. Deux îlots portent une
forme syntaxique et non une expression, et leur substitut la porte aussi :

| îlot | substitut | pourquoi |
|---|---|---|
| `for @bindings [as b] in` | `for _L3 in` | sinon la boucle n'est plus une boucle |
| `from m import a, ex:, u: as v:` | `import _L4` | pour que black lui donne les lignes vides d'un **bloc d'imports**, pas celles d'une expression |
| tout le reste | `_L7` | un nom est valide partout où un îlot l'est |

Et surtout : **le substitut pèse ce que pèsera l'îlot** (rallongé par des
`_`) — sa forme sur une ligne, ou sa première ligne `s{` pour une requête,
qui s'éclate toujours.
C'est la doctrine du masquage de la fiche 023 — un substitut de même longueur
laisse le moteur délégué décider comme il aurait décidé sur le vrai texte.
Sans cela, black croit que tout tient sur une ligne, joint une compréhension,
et l'îlot réinjecté déborde de 30 colonnes. Un îlot recopié tel quel (voir
plus bas) garde l'ancienne règle : s'il est **multiligne**, son substitut
reçoit un poids qui dépasse la limite, ce qui préserve la coupure écrite par
l'auteur.

Les noms de substitut sont choisis absents du source (`_L0`, `_L1`, … et un
`_` de plus tant qu'il y a collision) : le masquage doit être réversible.

## La mise en page des îlots : celle de black

Décision de Maxime (2026-11-01), sur un cas concret : un `m{ }` aligné à la
main dans un `return`, dont les lignes de continuation, à une colonne qui
n'est pas un multiple de quatre, s'affichaient en rouge dans l'éditeur
(extension *indent-rainbow*), et des corps d'îlots qu'aucun outil ne mettait
en forme. `ldpy/formatter_islands.py` reconstruit chaque corps **à partir de
ses jetons** — l'espacement de l'auteur ne compte pas, d'où l'idempotence :

- **Turtle** (`g{ }`, `+{ }`, `-{ }`, `m{ }`) — la règle de black : sur une
  ligne tant que la ligne tient (colonne de l'îlot, plus sa forme à plat,
  plus ce qui le suit sur la ligne) ; sinon éclaté en retrait suspendu, par
  paliers de quatre à partir de l'indentation de la ligne : le sujet en
  tête, un prédicat par ligne (`;` en fin de ligne), un nœud anonyme `[`
  ouvert en fin de ligne et fermé seul sur la sienne s'il ne tient pas, des
  objets `,` sur la ligne du prédicat tant qu'ils tiennent. Une collection
  `( … )` reste sur une ligne. Le point final du dernier énoncé est gardé
  s'il était écrit.
- **SPARQL** (`s{ }`) — toujours la mise en page canonique : une clause par
  ligne (`SELECT`, `WHERE`, `FILTER`, `OPTIONAL`, `ORDER BY`, `LIMIT`…), un
  motif de triplet par ligne, la suite d'un `;` un palier plus loin,
  accolades en retrait suspendu, `} UNION {` sur une ligne, mots-clés en
  capitales (`true` et `false` restent en minuscules), pas d'espace avant la
  parenthèse d'une fonction (`STR(?x)`), une après `FILTER`. Un chemin de
  propriété garde sa colle : `rdfs:subClassOf*`, `^ex:p` — rdflib lit
  `rdfs:subClassOf *` autrement, ou pas du tout.
- **Accolade de requête : groupe ou interpolation**, c'est le transpileur
  qui tranche (`_is_ldpy_expression`, fiche 015), et le formateur l'écoute
  par une sous-classe (`_Recording`) plutôt que de redécider : un `{x}` lu
  autrement changerait la requête.

**Ce qui reste recopié tel quel**, bordures seules normalisées comme
avant : un îlot qui contient un **commentaire** (une mise en page
reconstruite des jetons n'a pas où le mettre), un îlot dont la ligne porte
`# fmt: skip` ou qui est dans une région `# fmt: off` — les marqueurs de
black, pour l'auteur qui a aligné un graphe à dessein —, et tout ce que le
découpage ne reconnaît pas. Le risque de la version précédente (`.` à la
fois fin d'énoncé et point décimal) est levé par le découpage même : un
nombre est lu selon les productions de Turtle (fiche 020).

Mesure, sur les 392 fichiers `.ldpy` de l'espace de travail (exemples, 365
traductions du corpus, matériel de l'étude utilisateur) : 391 mis en page,
aucun renvoyé à la recopie par la garde, tous idempotents ; le dernier est
un extrait que black ne sait pas lire.

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

- `--check` en intégration continue sur `examples/` et les blocs de `docs/` :
  la documentation deviendrait formatée par construction.
- Le tri des imports (isort) n'est pas fait — black ne le fait pas non plus,
  et un import de préfixes n'a pas d'ordre canonique évident.
