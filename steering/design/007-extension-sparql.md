# 007 — Réintégration de l'extension SPARQL (dev-sparql)

**Date** : 2026-09-03 · **Statut** : implémenté — phase 2 faite ; la phase 3 est en fiche 017

## Ce que contenait dev-sparql (mai 2022, jamais fusionnée — sert de spécification)

- **Nœuds expression `e{ <expression SPARQL> }`** : grammaire d'expression SPARQL
  (`||`, `&&`, `=`, `!=`, `<`, `>`, `IN`, arithmétique, appels de built-ins et de
  fonctions par IRI) — règles `expression…` du .g4 de dev-sparql.
- **e-IRIs `e<...{...}...>`** et **e-strings** (chaînes avec interpolations à
  évaluer dans le contexte d'une solution mapping, pas immédiatement).
- **Graphes expression** (`construct_expression`) : g{} dont les termes peuvent être
  des expressions SPARQL.
- `ldpy/sparql/builtin.py` (déjà sur master) : wrappers des `op.Builtin_*` de
  rdflib.plugins.sparql.operators.

Sémantique visée : là où `f{...}`/f-IRI s'évaluent IMMÉDIATEMENT, les `e{...}`
construisent des expressions DIFFÉRÉES, évaluées plus tard contre des solution
mappings (usage type : templates de BGP + `instantiateBGP`, filtres).

## Décision

`e{...}` et `e<...>` sont transpilés vers un objet Python appelable via
`ldpy/sparql.py` (~540 lignes) et un parseur `_e_*` dans core.py. Pas de parser
rdflib ; `rdflib.plugins.sparql.operators` est réutilisé comme bibliothèque de
sémantique d'évaluation (ce ne sont pas des parsers), comme le faisait
builtin.py. Le parser d'îlot `e{` réutilise le parser de termes de islands.py +
une couche d'expressions en descente récursive (précédences SPARQL).

- **Sémantique différée** : `e{}` construit une `Expression` évaluée contre un
  solution mapping (`expr(sm)` / `expr.ebv(sm)` ; clés str ou Variable, valeurs
  Python coercées). `repr()` montre la source. `e<...>` : IRI différée (STR +
  ENCODE_FOR_IRI sur les trous, résolution contre la base lexicale).
- **Langage** : précédences SPARQL (`||` < `&&` < relationnels < additifs <
  multiplicatifs < unaires), ternaire style Python, IN/NOT IN, nombres typés
  SPARQL (integer/decimal/double, division entière → decimal), pnames résolues
  statiquement, `{py}` ré-évalué à chaque évaluation, commentaires/multilignes.
- **Erreurs SPARQL** : SparqlError propagée, absorbée exactement par
  ||/&&/IF/COALESCE (tables à trois valeurs testées).
- **Built-ins** : 30 fonctions cœur, implémentation directe sur le modèle rdflib
  (aucun parser rdflib) ; BOUND(?v) syntaxiquement contraint.

26 tests dédiés (tests/test_sparql_expr.py).

## Hors périmètre (phase 3, fiche 017)

`e{}`/`e<>` comme TERMES dans `g{...}` (graphes-gabarits de dev-sparql, l'ancien
`construct_expression`) — documenté dans la référence, pas implémenté.

## Étapes prévues (phase 3)

1. Porter les golden de dev-sparql concernés (test/*.ldpy) comme cas cibles.
2. Étendre le parser de graphes de islands.py pour accepter des expressions
   comme termes.
3. Documenter la frontière f{} (immédiat) / e{} (différé) dans le README.
