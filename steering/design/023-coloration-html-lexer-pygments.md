# 023 — Coloration HTML : un lexer Pygments qui lit la language map

**Date** : 2026-09-03 · **Statut** : implémenté

## Contexte

La documentation part sur readthedocs (mkdocs-material). Les blocs ` ```ldpy `
y étaient rendus sans coloration : mkdocs demande à Pygments un lexer nommé
`ldpy`, qui n'existait pas, et retombe sur du texte brut. La grammaire TextMate
de `vscode-ldpy` ne sert à rien ici — Pygments ne lit pas TextMate.

Le langage a donc besoin d'un **troisième** consommateur des règles de la
fiche 002, après le scanner du transpileur et la grammaire TextMate. La fiche
002 le disait déjà : « ces règles sont LA spécification pour la coloration
TextMate et le LSP — les garder synchronisées ». Un troisième descripteur écrit
à la main, c'est une troisième occasion de diverger.

## Options envisagées

1. **Un `RegexLexer` Pygments écrit à la main** (la façon habituelle). Rapide à
   écrire, mais c'est exactement la troisième réécriture des règles : chaque
   révision de la fiche 002 devrait être répercutée ici, sans test qui le
   force.
2. **Vendorer / adapter les lexers Turtle et SPARQL de Pygments.** Ils existent
   (`pygments.lexers.rdf`) mais ne connaissent ni les îlots, ni les
   interpolations, ni le contexte opérande. Il faudrait de toute façon écrire
   la couche ldpy, et découper le texte à leur donner — c'est-à-dire déjà
   savoir où sont les îlots.
3. **Un dépôt à part** (`pygments-ldpy`). C'est la forme suggérée dans la
   demande. Écartée : le lexer doit suivre le scanner version par version ; un
   dépôt séparé signifie soit dupliquer les règles, soit dépendre de `ldpy`,
   auquel cas autant vivre dedans. Et il resterait à le tester contre la doc,
   qui est dans ce dépôt.
4. **Un lexer qui lit la language map.** Retenu.

## Décision

`ldpy/pygments_lexer.py` — `LdpyLexer(Lexer)`, enregistré comme plugin Pygments
par un entry point `pygments.lexers` dans `pyproject.toml`.

Il ne redécrit pas le langage : il **transpile** la source et lit la
`LanguageMap`, qui est une partition ordonnée du fichier en segments `copy` et
`island:KIND` (fiche 005). **Rien dans ce fichier ne redécrit Python, Turtle
ni SPARQL** — tout le texte est délégué à un lexer existant :

| texte | lexer |
|---|---|
| segments `copy`, interpolations `{expr}` | `PythonLexer` |
| `@prefix` / `@base` | `TurtleLexer` (ce SONT des directives Turtle) |
| corps de `g{ }`, `m{ }`, `+{ }`, `-{ }`, `s{ }`, `e{ }` | `SparqlLexer` |

Le choix de `SparqlLexer` pour les corps de graphes n'est pas un pis-aller : un
corps de `g{ }` ou de `m{ }` est du **Turtle à variables**, c'est-à-dire
exactement le bloc de triplets de SPARQL. Vérifié : `TurtleLexer` produit des
`Token.Error` sur `?s` et découpe `^^` en deux ponctuations ; `SparqlLexer` lit
le même bloc sans erreur et connaît `^^`, `a`, `@lang`, les collections et les
nœuds anonymes.

Une interpolation qui contient elle-même un îlot (`ex:{?id}`) est re-passée au
découpeur d'îlots — le transpileur re-scanne bien ces expressions (fiche 001,
récursion mutuelle), donc le lexer fait de même.

Ce qui reste écrit à la main est ce qu'aucun lexer existant ne peut savoir :
où sont les îlots (la map répond), les déclarations propres à ldpy (`@graph`,
`@bindings`, `for @bindings`, imports de préfixes), et le **masquage** — chaque
région spécifique à ldpy est remplacée par un substitut *de même longueur*,
valide comme terme à sa place (`ex:{e}` → `ex:xxxx`, `_:{e}` → `_:xxx`,
`f<…>` → `<xxx>`, sinon `"xx"`), le lexer délégué voit un document bien formé,
et le texte réel est réinjecté à sa position. Les types de tokens des lexers
délégués sont retablés (`_REMAP_*`) vers la palette décidée plus bas.

**Pygments est optionnel** : extra `[highlight]` (et `[docs]` l'apporte aussi).
Aucun module de `ldpy` n'importe `pygments` — seul `pygments_lexer.py` le fait,
et c'est Pygments qui le charge, par entry point, s'il est installé. Le module
de tests commence par un `pytest.importorskip("pygments")`.

**Le surligneur est le transpileur.** Une règle de désambiguïsation qui change
change la coloration sans qu'une ligne de ce fichier bouge : `a<b>c` est coloré
comme une comparaison chaînée parce que le transpileur le lit ainsi.

Trois points de conception méritent d'être notés.

**1. L'oracle de `s{ }` est réutilisé tel quel.** Dans un îlot SPARQL, `{` est
ambigu entre un groupe et une interpolation. La fiche 015 tranche par un oracle
— le contenu équilibré est une interpolation ssi il transpile puis compile en
expression. Le lexer pose *la même* question. Aucune heuristique parallèle,
contrairement à la grammaire TextMate qui, faute de pouvoir compiler, en emploie
une (fiche vscode/102).

**2. Repli, jamais d'échec.** Une source qui ne transpile pas — tampon
d'éditeur en cours de frappe, extrait illustratif — retombe sur le
`PythonLexer`. La coloration se dégrade ; elle ne casse pas.

**3. Uniquement des types de tokens standard**, pour que tout thème colore ldpy
sans feuille de style dédiée. Le choix des types n'est cependant pas celui de
`pygments.lexers.rdf` : mkdocs-material rabat `Name.Label`, `Name.Tag`,
`Keyword` et `Keyword.Pseudo` sur **la même** couleur, ce qui rendrait les IRIs
et les noms locaux indistinguables des mots-clés. La table vise huit rôles sur
huit couleurs — mots-clés (sigles, déclarations, `a`, mots SPARQL), chaînes
(IRIs, littéraux), fonction (noms préfixés), variable (`?v`, tags de langue),
constante (fonctions SPARQL), nombre, opérateur, ponctuation. Un test le
vérifie sur la table de material.

## Conséquences

- `pyproject.toml` gagne un entry point ; readthedocs installe déjà le paquet,
  donc la coloration arrive sans configuration supplémentaire. `pygmentize -l
  ldpy` et Sphinx en profitent aussi, gratuitement.
- Trois propriétés testées (`tests/test_pygments_lexer.py`, 98 tests) :
  **round-trip** (la concaténation des valeurs de tokens redonne la source, aux
  positions croissantes), **transparence** (du Python pur donne exactement les
  tokens du `PythonLexer`, vérifié sur les sources du paquet), et **aucun
  `Token.Error`** sur tous les extraits ` ```ldpy ` de `docs/`. Cette dernière
  fait de la documentation le corpus de test du surligneur.
- Le coût est une transpilation par bloc de code au moment de construire le
  site : à 60 000 lignes/s, négligeable.
- La grammaire TextMate reste nécessaire (VS Code ne lit pas Pygments) et reste
  générée depuis MagicPython. Il y a donc deux descripteurs, mais un seul écrit
  à la main.
- `LdpyLexer` fait ~520 lignes, dont la moitié est le découpeur d'îlots
  (termes, Turtle, SPARQL, expressions différées) (commit `e4f409e`).

Note pour qui cite ce numéro dans du code ou une autre fiche : cette fiche a
porté le numéro 021 avant de devenir 023 (collision avec la fiche
[021-coloration-multi-frameworks.md](021-coloration-multi-frameworks.md),
écrite le même jour par une session parallèle) ; le contenu n'a pas changé.
