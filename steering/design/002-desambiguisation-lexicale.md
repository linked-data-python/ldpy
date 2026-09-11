# 002 — Désambiguïsation lexicale îlots RDF / Python

**Date** : 2026-09-03 · **Statut** : acté

## Contexte

Les îlots RDF entrent en collision avec la syntaxe Python : `<` (comparaison vs
IRI), `:` (slice/dict/annotation vs pname), `@` (décorateur/matmul vs @prefix/langtag),
`{` (dict/set vs g{/f{/e{). v1 « résolvait » cela par priorités lexicales ANTLR, avec
des ambiguïtés silencieuses : `a<b>c` (Python valide, comparaison chaînée) était lexé
comme IRI `<b>` ; `d[ex:b]` était fragile ; espace obligatoire après `g{`.

## Décision : trois règles composables

### R1 — Contexte opérande (l'astuce « regex de JavaScript »)

Le scanner maintient un bit `operand_expected` : vrai en début d'expression (début
de ligne logique, après un opérateur, `(`, `[`, `{`, `,`, `=`, `:`, `return`,
mot-clé, etc.), faux après un token terminant un opérande (NAME, NUMBER, STRING,
`)`, `]`, `}`, `...`, True/False/None).

- `<` en contexte opérande → tentative d'IRI (avec repli R3) ; sinon → opérateur.
  Ainsi `t = <p>` est une IRI, `a<b>c` reste une comparaison chaînée.
- Idem pour `f<`/`e<` (f-IRI) : seulement en contexte opérande.
- `?` et `$` ne sont JAMAIS valides en Python → toujours un îlot (`?var`, `?{...}`),
  quel que soit le contexte. Meilleur diagnostic d'erreur au passage.

### R2 — Adjacence stricte (pas d'espace)

- Un délimiteur d'îlot suit son introducteur (NAME ou `?`) sans espace, sur une
  **liste fermée** de formes — énumérée ici et nulle part ailleurs :

  | forme | sens | fiche | état |
  |---|---|---|---|
  | `g{` | graphe | 003 | implémenté |
  | `f{`, `f<` | nœud / IRI formatés, évaluation immédiate | 002 | implémenté |
  | `e{`, `e<` | expression / IRI SPARQL différées | 007 | implémenté |
  | `?{` | nœud formaté (synonyme de `f{`) | 002 | implémenté |
  | `s{` | requête SPARQL complète | 015 | spécifié |
  | `m{` | motif (BGP) de lecture | 016 | spécifié |

  `g {` reste du Python (erroné ou dict après nom — l'erreur Python surgira à
  l'exécution comme pour tout .py). `NAME{` n'est jamais du Python valide → aucune
  perte. Aucun **alias long** (`sparql{`, `graph{`) : il transformerait R2 en
  « n'importe quel identificateur collé à `{` » et étendrait la surface
  d'ambiguïté à tout le code (fiche 015).

  Deux formes s'ajoutent hors de la règle « une lettre » :
  - `+{ … }` et `-{ … }` — ajout et retrait sur le graphe courant (fiche 014),
    admis **uniquement en début de ligne logique et à profondeur crochets
    nulle**. Ailleurs, `+` et `-` gardent leur sens Python :
    `keys - {'a'}` reste une différence d'ensembles. En tête d'instruction, en
    revanche, `+{…}` et `-{…}` sont du Python légal mais sémantiquement mort
    (plus/moins unaire sur un ensemble ou un dictionnaire → `TypeError`) : la
    capture ne coûte aucun code réel.
  - `@graph` (fiche 014) et `@bindings` (fiche 017) — déclarations d'îlot,
    désambiguïsées du décorateur par la même règle que `@prefix` / `@base`
    (fiche 004, décision 5) : îlot seulement si la suite de la ligne matche la
    forme attendue ; `@graph` seul sur sa ligne, suivi de `(` ou de `.attr`,
    reste un décorateur.

  Deux formes étendent enfin des constructions Python existantes, toutes deux
  illégales en Python et donc conformes à la doctrine « n'étendre que là où
  Python est illégal », sans mot-clé nouveau :
  - `from m import brick:, unit: as u:` — un nom préfixé dans une liste
    d'import (fiche 013) ;
  - `for @bindings in <itérable> :` et `for @bindings as b in <itérable> :` —
    une déclaration d'îlot en cible de `for` (fiche 017), et `global @prefix` /
    `nonlocal @graph` — un modificateur de portée devant une déclaration
    (fiche 018).

  Le **suffixe d'appel** de la fiche 019 (`m{ P }(g)`, `s{ Q }(g, b)`) n'est en
  revanche pas une extension lexicale : pour les îlots qui sont des expressions,
  c'est un appel Python ordinaire sur la valeur de l'îlot.

  Littéraux RDF : `@lang` et `^^` collés à la chaîne (`"a"@en`, `"a"^^xsd:int`).
  `"a" @ en` reste un matmul Python. `^^` n'est jamais du Python adjacent valide.
  pname : `préfixe:local` sans espace autour du `:`, sauf dans une **liste de
  paramètres** (`lambda … :`, ou les parenthèses d'un `def`) : `f = lambda ex:ex`
  et `def g(ex:int = 0)` sont du Python valide, donc un `NAME:` y appartient
  toujours à Python, **sauf après un `=`** (`def h(x = ex:Thing)` est une valeur
  par défaut, donc une expression, où un terme a toute sa place — le scanner
  suit cet état sur sa pile de crochets, `p` = paramètres, `P` = valeur par
  défaut). Les parenthèses d'un `class` ne sont pas concernées : elles ne
  peuvent pas contenir d'annotation.

### R3 — Repli par backtracking + connaissance des préfixes déclarés

- Tentative d'IRI : `<` puis caractères IRIREF (pas d'espace, pas de `<>"{}|^\``,
  pas de contrôle) jusqu'à `>` sur la même ligne. Échec → on ré-émet `<` comme
  opérateur Python. Idem `f<...>` (les interpolations `{...}` peuvent contenir des
  espaces, elles sont scannées comme expressions Python).
- pname : reconnu SEULEMENT si la partie préfixe est un préfixe déjà déclaré par un
  `@prefix` lexicalement antérieur (le transpileur les connaît statiquement,
  fiche 004). Hors îlot, la partie locale est obligatoire (`ex:` seul interdit hors
  îlot — trop conflictuel avec les dicts `{ex: v}`). Dans un îlot g{...}, règles
  Turtle pleines (`ex:` autorisé, `a` = rdf:type, etc.).
- `_:` hors d'un îlot : voir la fiche 021 pour la décision et son raisonnement. En
  résumé : `_:{expr}` est transpilé partout où un terme peut tenir ; `_:label`
  hors d'un îlot est une **erreur** nommant les deux formes correctes ; et comme
  `_` est le nom jetable de Python et que personne ne l'a « déclaré » comme
  préfixe, le nœud anonyme est en outre exclu des dict/set (`{_:x}`) et des
  indices (`a[_:i]`) — là où le nom préfixé, lui, est accepté parce que sa
  déclaration vaut opt-in.

## Ambiguïtés résiduelles assumées (documentées + testées)

1. `a[ex:b]` avec `ex` préfixe déclaré ET collé : lu comme indexation par la pname
   `ex:b` (et non slice de variables `ex` à `b`). Échappatoire : écrire `a[ex : b]`.
   Un **warning** est émis quand un préfixe déclaré est aussi utilisé comme nom de
   variable Python dans le fichier — heuristique (sans parser Python, cf. fiche
   001) : le nom est un préfixe déclaré, il ouvre une instruction (profondeur de
   crochets nulle, hors îlot) et il est suivi de `=` (`==` exclu) ou de `,`. Cela
   couvre `ex = …` et `ex, autre = …`, la façon dont le cas se présente
   réellement ; un préfixe masqué par une cible de `for` ou un paramètre de
   fonction n'est pas vu. L'avertissement ne se répète pas (un par nom), et son
   message donne l'échappatoire plutôt que de constater : « Écrire `{ex: x}` avec
   une espace force le dict. » Documenté dans `docs/reference/language/lexical.md`.
2. `{ex:b}` (dict/set collé) : lu comme un set contenant la pname. Échappatoire :
   espaces `{ex: b}`.
3. IRI relative `<b>` : nécessite le contexte opérande ; `x = y <b> z` (comparaison
   voulue) serait lu… non : `<` après NAME `y` → opérateur. Cas réellement piégeux :
   `x = -1 <b> 2`?? `<` suit NUMBER → opérateur. RAS connu ; fuzzing prévu.

## Conséquences

- Chaque règle et chaque ambiguïté résiduelle a ses tests dédiés
  (tests/test_disambiguation.py).
- Ces règles sont LA spécification pour la coloration TextMate et le LSP (fiches
  101/102) — les garder synchronisées.
