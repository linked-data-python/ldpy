# 003 — Émission : les îlots deviennent UNE expression, plus de hoisting

**Date** : 2026-09-03 · **Statut** : acté

## Contexte

v1 émettait pour chaque `g{...}` une série d'INSTRUCTIONS hissées avant
l'instruction courante :

```python
graph_ab12 = rdflib.Graph(base=__base__)
graph_ab12.namespace_manager.bind('ex', '...')
bn_cd34 = rdflib.BNode()
graph_ab12.add((bn_cd34, rdflib.RDF.type, ...))
x = graph_ab12          # l'instruction d'origine
```

Problèmes identifiés (jamais documentés dans v1) :

1. **Ordre d'évaluation faux** : `cond or g{...{f(x)}...}` évalue `f(x)` même si
   `cond` est vrai (le graphe est construit avant l'instruction).
2. **Impossible dans lambda / comprehensions / valeurs par défaut** sans acrobaties
   (or les exemples v1 utilisent `def f(g=g{...})` !).
3. Line map illisible : une ligne source explose en N lignes générées AVANT elle.
4. Noms aléatoires `secrets.token_hex` → sortie non déterministe, tests golden
   impossibles, diffs de code généré bruités.

## Décision

Tout îlot est transpilé en **une expression Python unique**, via un runtime minimal
`ldpy/runtime.py` importé sous un alias réservé :

| Îlot | Émission (schéma) |
|---|---|
| `<abs://iri>` | `_ldpy_.URIRef('abs://iri')` (résolution @base **à la transpilation**, fiche 004) |
| `ex:Person` | `_ldpy_.URIRef('http://…#Person')` (résolution statique) |
| `?var` | `_ldpy_.Variable('var')` |
| `"x"@en` / `f"x{i}"@en` | `_ldpy_.Literal("x", lang='en')` — la f-string reste une f-string |
| `"x"^^dt` | `_ldpy_.Literal("x", datatype=<expr dt>)` |
| `f<a{expr}b>` | `_ldpy_.URIRef(f'a{expr}b', base='<base lexicale>')` |
| `f{ expr }` / `?{ expr }` | `_ldpy_.node(expr)` (coercition valeur Python → terme RDF) |
| `g{ triples }` | `_ldpy_.graph(ns, base, (s,p,o), (s,p,o), …)` |

Pour `g{...}` : les nœuds anonymes `[...]`, collections `(...)` et labels `_:b`
sont aplatis À LA TRANSPILATION en triplets avec placeholders `_ldpy_.bn(i)`
(indice déterministe par position syntaxique) ; `_ldpy_.graph` crée un BNode frais
par indice **à chaque évaluation**. Les interpolations `{expr}` s'insèrent
directement dans le tuple (évaluation gauche→droite, paresseuse car l'expression
entière est évaluée à sa place d'origine).

`ns` = référence au dict module `__namespaces__` (liaison des préfixes pour la
sérialisation, dynamique) ; `base` = chaîne statique lexicale.

Une expression interpolée **partagée** entre plusieurs triplets d'un même graphe
(ex. un sujet répété : `g{ ex:{next_id()} ex:p 1 ; ex:q 2 }`) n'est évaluée
**qu'une fois** : un placeholder runtime `slot(i, expr)` / `slot(i)`, résolu par
`graph()` comme `bn(i)`, émet l'expression à sa **première occurrence** et la
rappelle ensuite. Le partage est indexé sur **l'identité de l'occurrence source**
(`_Term.occ`), pas sur le texte : deux `?{ v() }` écrits à deux endroits différents
restent deux évaluations distinctes, comme la source le demande. Ordre
d'évaluation préservé (liste plate, gauche→droite).

Les interpolations dans un graphe portent en outre des suffixes RDF : `{expr}@en`
→ `Literal(expr, lang="en")`, `{expr}^^dt` → `Literal(expr, datatype=dt)` (aussi
sur `?{expr}`/`f{expr}`) ; adjacence stricte (R2, fiche 002), un `@` DANS
l'expression reste un matmul Python. `_:{expr}` construit un bnode à **identité
déterministe** issue de la valeur : `_ldpy_.bnode(valeur)` garde l'étiquette telle
quelle si elle est sûre, sinon (tuples compris) encode canoniquement puis hache
(md5) — pas de collision entre `("Bob","bySmith")` et `("Bobby","Smith")` —,
étiquette toujours sérialisable. Sémantique : identité STABLE partout où la valeur
est égale (idiome de déduplication/jointure R2RML), alors que `_:label` reste
frais par évaluation et scopé à l'îlot ; `_:{expr}` est marqué occurrence-impur
(évaluation unique en sujet partagé, comme les autres interpolations partagées).

## Justification

- Corrige 1–4 d'un coup : ordre d'évaluation exact, îlots valides partout où une
  expression Python est valide, map quasi triviale, sortie déterministe.
- Le code généré reste lisible et débogable (on step-pe dans `_ldpy_.graph`).

## Conséquences

- Nouveau module runtime obligatoire à l'exécution (fiche 008) — remplace la
  dépendance implicite `import rdflib` de v1.
- L'alias `_ldpy_` est un nom réservé du langage (documenté ; collision improbable,
  vérification simple possible plus tard).
- Une seule ligne générée peut être très longue (gros graphe) : acceptable, le
  language map segment-level (fiche 005) garde les positions exactes.
- L'aplatissement d'une structure arborescente en liste plate duplique les nœuds
  internes ; toute duplication d'expression hôte est un bug de sémantique en
  puissance (leçon tirée du partage de sujet ci-dessus) — à revérifier si
  d'autres constructions viennent partager des termes.
