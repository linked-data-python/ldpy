# 021 — Coloration syntaxique : réutiliser l'existant, couvrir les frameworks communs

**Date** : 2026-09-03 · **Statut** : chantier ouvert — cinq moteurs faits, Rouge et tree-sitter restent

## La forme retenue : un dépôt, une spécification

Un huitième projet, `highlight-ldpy/` (paquet npm `linked-data-python-highlight`,
Apache-2.0), porte les moteurs JavaScript. Le cœur est `src/islands.js` : les
règles de la fiche 002 — déclencheurs, gardes de contexte (`OPERAND`, `STRICT`,
`ARGS`), gabarits d'IRI, suffixes de littéral, mots-clés SPARQL — écrites
**une fois**, en regex du sous-ensemble commun à V8, Oniguruma et Prism.
Chaque générateur les assemble dans le modèle de règles de son moteur.

**Ce qui n'est PAS partagé** : la forme des règles — pile `begin`/`end` de
TextMate, arbre de modes de highlight.js, table ordonnée de Prism. Une
représentation intermédiaire capable d'engendrer fidèlement les trois
coûterait plus cher que ce qu'elle rapporte ; la garantie est reportée sur les
tests de conformité (voir plus bas).

Pygments (`ldpy/pygments_lexer.py`) et TextMate (`vscode-ldpy/syntaxes/`)
restent dans leurs dépôts respectifs — voir fiche 023 et fiche vscode/102.

Doctrine commune à tous les moteurs : **jamais de troisième (ou quatrième…)
spécification de la lexique** — soit générer depuis une source unique, soit
déléguer aux grammaires existantes du framework avec une mince couche
d'îlots, dont les règles sont celles de la fiche 002 (liste fermée des
déclencheurs, adjacence stricte, contexte opérande).

## État par moteur

| moteur | Python | Turtle / SPARQL des îlots | état |
|---|---|---|---|
| Pygments | `PythonLexer` | `TurtleLexer`, `SparqlLexer` | fait (fiche 023) |
| Prism | `Prism.languages.python` | `Prism.languages.sparql` (Turtle écrit à la main, Prism ne le fournit pas) | fait |
| highlight.js | `getLanguage('python').rawDefinition()` | écrit à la main (highlight.js n'a aucun langage RDF sur ses 193) | fait |
| TextMate | MagicPython vendoré | écrit à la main | fait |
| CodeMirror 6 | `@codemirror/legacy-modes/mode/python` (`StreamParser`) | écrit à la main | fait |
| Rouge (Ruby, Jekyll) | — | — | au plan |
| tree-sitter | — | — | au plan, le plus lourd — n'envisager que si la demande existe |

Vendorer une grammaire TextMate Turtle/SPARQL éprouvée reste une option
ouverte plutôt qu'une nécessité : le test de conformité (ci-dessous) tient
déjà les descripteurs cohérents entre eux, ce qui en était l'objectif réel.
Référence si le vendoring redevient d'actualité : les grammaires TextMate
Turtle/SPARQL de stardog-vsc (Apache-2.0,
https://github.com/stardog-union/stardog-vsc/tree/master/stardog-rdf-grammars/syntaxes).

CodeMirror 6 s'écarte du modèle déclaratif des quatre autres : un
`StreamParser` **tient une pile de contextes** (sorte de crochet, groupe
SPARQL vs interpolation Python) plutôt que de deviner par lookbehind
(`SUBSCRIPT_OPEN`, `NOT_IN_DEF_PARAMS`, `ARGS_FLAT` chez les autres). C'est le
même mécanisme que la pile de sortes de crochets du transpileur pour `_:`
(fiche 002) — la doctrine « ne pas redécrire la lexique » n'interdit pas de
partager un mécanisme quand deux moteurs peuvent le porter.

## Vérification : le transpileur est l'arbitre

Sur une fixture qui transpile (`test/fixtures/conformance.ldpy`), la
`LanguageMap` du transpileur dit où sont les îlots ; aucun moteur ne doit en
colorer ailleurs, ni en manquer un. C'est la doctrine de la fiche 023 (« le
surligneur est le transpileur ») étendue aux moteurs qui, eux, ne peuvent pas
l'appeler.

S'y ajoutent, par moteur : la **parité Python pur** (un `.py` reçoit
exactement les mêmes jetons en `ldpy` qu'en `python`), un **golden**, et la
compilation de chaque regex partagée **sous V8 et sous Oniguruma**. La liste
des divergences tolérées (`DIVERGENCES` dans `test/run.js`) est **vide** — le
test échoue si une exemption cesse d'être observée, ce qui interdit de la
laisser traîner sans la retirer.

## Défauts trouvés par la conformité entre moteurs, tous corrigés

Aucun n'était visible avant qu'un deuxième moteur ne soit écrit sur les mêmes
règles — pointeurs vers les commits dans l'historique de `highlight-ldpy` et
de `ldpy` :

1. Un préfixe **dynamique** (`@prefix dyn: f<http://{host}/ns#> .`, fiche 013)
   se colorait en décorateur Python (garde de directive trop stricte, `#` du
   fragment lu comme commentaire).
2. `e{ … }` recevait des jetons Python au lieu de jetons d'expression SPARQL
   (fiche 007).
3. Les fonctions intégrées SPARQL n'étaient reconnues que par Prism ; la
   liste est maintenant partagée entre moteurs.
4. En moteur **plat** (sans point d'injection), trois gardes de la fiche 002
   étaient insuffisantes et du Python pur se colorait en RDF : `^` en début de
   *fragment* confondu avec un début de ligne, `=` de `ARGS` confondu avec
   `==`, une annotation de paramètre confondue avec un nom préfixé. Les
   variantes `ARGS_FLAT`, `NOT_COMPARISON` et `NOT_IN_DEF_PARAMS` sont dans la
   spécification partagée.

## Ce que la conformité a trouvé dans le transpileur

Deux défauts du **transpileur** lui-même sont sortis de ce chantier, tous deux
corrigés (détail en fiche 002) :

1. `_:label` en position de terme, hors îlot, était accepté par la coloration
   des quatre moteurs mais transpilé en `bn = _:station`, du Python invalide,
   sans erreur ldpy. La correction retenue n'est pas de le transpiler mais de
   le **refuser** : une étiquette de nœud anonyme n'a de sens que dans la
   portée d'un îlot (fiche 003) ; hors îlot, ni « fraîche à chaque occurrence »
   ni « stable dans le module » ne sont de bonnes inventions, et `_:{expr}`
   reste la forme valide partout où un terme peut tenir. `_:label` hors îlot
   lève donc une erreur qui nomme les deux formes correctes.
2. `f = lambda ex:ex` et `def g(ex:int = 0)` — du Python valide — étaient lus
   comme des noms préfixés par le transpileur (la garde `NOT_IN_DEF_PARAMS`
   existait déjà côté coloration, pas côté transpileur). Corrigé, avec
   l'exception qui va bien : après un `=`, on est dans une valeur par défaut,
   donc dans une expression (`def h(x = ex:Thing)`).

La spécification d'îlots partagée entre moteurs de coloration n'est donc plus
seulement dérivée du transpileur : dans ces deux cas, elle l'a contrôlé.

## Prochaine action concrète

Rouge (Jekyll / GitHub Pages) si le besoin apparaît — sinon, brancher le
langage CodeMirror sur l'éditeur de `user_study`, qui est la raison pour
laquelle il a été écrit.
