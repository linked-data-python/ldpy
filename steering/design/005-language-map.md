# 005 — Language map (source map .ldpy ⇄ .py)

**Date** : 2026-09-03 · **Statut** : acté

## Contexte

v1 avait un `linemap` {ligne générée → ligne source}, unidirectionnel, granularité
ligne, utilisé seulement pour réécrire les erreurs. Le language server et le
debugging exigent : bidirectionnel, granularité colonne, format sérialisable.

## Options

- **Source Map v3** (JS, mappings VLQ base64) : standard outillé mais illisible et
  pénible à générer/consommer à la main. Produit en plus du format maison (voir
  Matérialisation).
- **JSON maison segment-level** : trivial des deux côtés. Retenu comme format de
  travail principal.

## Décision

Le transpileur retourne (source_py, LanguageMap). `LanguageMap` :

```json
{ "version": 1, "source": "module.ldpy", "generated": "module.py",
  "segments": [
    {"kind": "copy",        "src": [l0,c0,l1,c1], "gen": [l0,c0,l1,c1]},
    {"kind": "island:graph","src": [l0,c0,l1,c1], "gen": [l0,c0,l1,c1]},
    {"kind": "synthetic",   "gen": [l0,c0,l1,c1]}
  ] }
```

- `kind: copy` : recopie verbatim → traduction de position EXACTE (offset constant
  dans le segment). C'est ~95 % d'un fichier réel, bénéfice direct de l'island
  parsing.
- `kind: island:*` (`graph`, `iri`, `pname`, `literal`, `var`, `firi`, `fnode`,
  `prefix`, `base`, `enode`) : région source ↔ région générée, traduction à la
  granularité de la région (une position intérieure se projette sur le début de la
  région de l'autre côté).
- `kind: synthetic` : texte généré sans origine (prélude d'import du runtime).
- Positions 0-based, fin exclusive, cohérentes avec LSP.

Les termes écrits **à l'intérieur** d'un îlot composite (`g{...}`) sont, en plus,
adressables individuellement pour le hover (fiche vscode/108) : ils vivent dans
`Segment.parts`, une liste de `(kind, src, gen_text)` où `gen_text` est le code
produit (pas une position — à la construction de l'îlot, les positions générées ne
sont pas encore connues). Le JSON gagne une clé `parts`, **écrite seulement quand
elle est non vide** : un fichier sans îlot composite sérialise exactement comme un
fichier sans cette clé.

```json
{ "kind": "island:graph", "src": [1, 4, 1, 41], "gen": [3, 4, 3, 210],
  "parts": [ { "kind": "pname", "src": [1, 8, 1, 12],
               "gen": "_ldpy_.URIRef('http://example.org/ns#s')" } ] }
```

`parts` n'a pas été ajoutée à la liste des segments elle-même : la liste est
ordonnée, non imbriquée, et quatre consommateurs en dépendent (`to_src`/`to_gen`
qui rendent la première correspondance, `snap_breakpoint_line`, la génération du
Source Map v3, la coloration sémantique) — trois en auraient été affectés, dont le
placement des points d'arrêt. Rien d'autre que le hover ne lit `parts`.

API en mémoire : `map.to_src(line, col)`, `map.to_gen(line, col)`,
`map.src_range_for_gen_line(line)` (pour les tracebacks), `map.to_json()` /
`from_json()`, `map.to_sourcemap_v3()` (format standard ECMA-426, base64-VLQ,
deltas). Recherche par bissection sur les segments triés.

## Matérialisation

- Mode import hook : map gardée en mémoire (+ réécriture des tracebacks).
- Mode build (`ldpy build`, prérequis LSP/debug) : écrit `module.py` +
  `module.ldpy.map` (format maison) et `module.py.map` (Source Map v3) dans un
  répertoire fantôme (`.ldpy-build/` par défaut, arborescence miroir). Le
  debugging DAP (fiche 101) traduit chemins et positions via ces fichiers ; le
  JSON maison reste le format de travail du LSP et du debug (plus riche : régions,
  kinds).

## Cas de test imposés

- Fichier sans îlot : un seul segment copy, to_src == identité.
- Îlot en milieu de ligne : positions avant/dans/après l'îlot.
- g{} multiligne remplacé par une expression sur une ligne (décalage de lignes en
  aval + projection des lignes intérieures sur la région).
- Round-trip JSON. Traceback d'une exception levée dans un .py généré → position
  .ldpy correcte.
- Source Map v3 vérifié par un **décodeur indépendant** (`tests/test_sourcemap_v3.py` :
  vecteurs connus, round-trip, cohérence de chaque point décodé avec `map.to_src`).
