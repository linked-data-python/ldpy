# 010 — Jeux de caractères : identifiants Python vs PN_CHARS de Turtle/SPARQL

**Date** : 2026-09-03 · **Statut** : implémenté — divergence résiduelle documentée côté explanation

## Contexte

L'ensemble des caractères acceptés par Python (PEP 3131, `ID_CONTINUE`) et
celui de Turtle/SPARQL (`PN_CHARS`) sont **incomparables** : aucun n'inclut
l'autre. Mesure sur le BMP (script reproductible, voir `tests/test_charsets.py`) :

- **50 727 caractères communs** ;
- **3 400 caractères Turtle-seulement** — dont `-`, `·` (U+00B7), les
  diacritiques combinants U+0300–036F, des symboles modificateurs (˂ U+02C2…),
  et des pans entiers de U+3001–D7FF que Python n'admet pas ;
- **4 caractères Python-seulement** : ª µ º ⁔.

Toute simplification par sous-ensemble perd donc des noms légaux d'un côté ou
de l'autre. (S'y ajoutent, hors caractères : PN_LOCAL de Turtle admet chiffres
en tête, `%`-échappements et `\`-échappements, points intérieurs.)

## État courant (figé par tests/test_charsets.py, 13 témoins)

1. **Déclencheurs** (nom de préfixe, `?var`) hors îlots : identifiants Python
   **∩** PN_CHARS (intersection) — R3 préservé par construction ; µ/ª exclus
   (Turtle ne sait pas les écrire non plus). Un préfixe non-identifiant n'est
   utilisable QUE dans les îlots.
2. **DANS les îlots** : tables PN_CHARS **exactes**, transcrites directement
   des specs (transcription à la main, pas de dépendance de parsing) —
   préfixes PN_PREFIX complets (tirets, points intérieurs — `o-pizza:` de
   tpl.ottr.xyz passe), parties locales à chiffre initial, `·`, marques
   combinantes, U+02C2…, déclarations `@prefix` au nom PN_PREFIX (é:, a.b:,
   o-pizza:).
3. **Déclaration au préfixe non ASCII** (`@prefix é: <…> .`) : acceptée
   (PN_PREFIX complet, voir point 2).

Restes documentés : pas de `:` intérieur ni d'échappements PLX dans les
parties locales.

## Oracle de développement

`tools/charsets.py` : transcription **indépendante** des specs Python et
Turtle/SPARQL, vérifiée contre les tables du transpileur sur tout le BMP par
`tests/test_charsets.py`. Un outil d'algèbre de regex façon greenery resterait
pertinent si le besoin d'une algèbre complète (au-delà de comparaisons
d'ensembles) se présentait — non retenu pour l'instant, l'oracle par ensembles
suffit aux classes de caractères actuelles.

## Question ouverte

La divergence résiduelle entre les deux lexiques (Turtle-seulement DANS les
îlots vs intersection hors îlots) est assumée et documentée côté
« explanation » plutôt que résolue davantage — aucune demande n'en justifie
le coût à ce jour.
