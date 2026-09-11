# 011 — Compilation remappée : code objects en coordonnées source

**Date** : 2026-09-03 · **Statut** : acté

## Contexte

Le jalon « fantômes » (fiche 101, extension vscode/102) matérialisait un .py
pour le débogage : debugpy voyait un vrai fichier Python, mais l'utilisateur
déboguait le FANTÔME (pas son .ldpy), les breakpoints devaient être traduits
par l'outillage, et les tracebacks de `python -m ldpy` pointaient les lignes
GÉNÉRÉES (un excepthook les réécrivait après coup, seulement si installé).
Constat déclencheur (Maxime, 2026-08-27) : VS Code ne sait pas déboguer un
.ldpy, et « le py transpilé n'est jamais généré ».

## Options envisagées

1. **Adaptateur DAP dédié** qui traduit positions/breakpoints à la volée via
   la LanguageMap — puissant mais un vrai serveur DAP à écrire et maintenir.
2. **Fantômes + traduction de breakpoints côté extension** (jalon 1) — marche,
   mais UX : on débogue un fichier généré, pas son source.
3. **Compilation remappée** : compiler le Python généré en donnant au
   code object le NOM DU .ldpy et les numéros de ligne du SOURCE (réécriture
   de l'AST via la LanguageMap avant `compile()`, à la manière de la
   réécriture d'assertions de pytest). Debugpy/pdb/traceback fonctionnent
   alors nativement en coordonnées .ldpy — aucun adaptateur.

## Choix : option 3, partout

`ldpy.transpiler.linemap.remap_ast_lines` + `compile_mapped` ; adoptés par
`python -m ldpy`, l'import hook (`LdpyLoader.source_to_code`) et le nouveau
mode `python -m ldpy.debug --run` (exécution dans le processus courant, que
l'extension VS Code lance sous debugpy). Détails :

- ligne générée synthétique (prélude) → rabattue sur la ligne 1 ;
- intérieur d'un îlot multiligne replié → ligne de début de l'îlot
  (breakpoint au cœur d'un g{...} : lié à l'expression graphe) ;
- `end_lineno` borné à `>= lineno` ; colonnes conservées telles quelles
  (co_positions approximatives sur les lignes réécrites — assumé) ;
- échec d'`ast.parse` (imprévu) → repli compilation ordinaire.

## Conséquences

- Les tracebacks de `-m ldpy` et des modules importés sont justes SANS
  excepthook : `install_excepthook` devient un no-op de compatibilité.
- Le débogage VS Code n'a plus besoin ni du fantôme ni de la traduction de
  breakpoints (extension : type de débogage `ldpy` → session debugpy sur
  `-m ldpy.debug --run`). Le fantôme reste pour l'outillage et l'aperçu
  (`ldpy build`, commande « Show transpiled Python »).
- Un breakpoint sur une ligne intérieure d'îlot multiligne reste non lié
  (aucune ligne exécutable) — debugpy l'affiche gris, comportement assumé.
- Tests : test_debug.py (co_lines en coordonnées source, --run, argv,
  tracebacks de --run et de -m ldpy), suite verte.
- `inspect.getsource` sur une fonction de .ldpy rend le source ldpy (le
  fichier pointé est le .ldpy) — honnête, mais pas du Python valide ; à
  documenter si un outil s'en plaint.
