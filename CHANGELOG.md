## Release Notes

### [0.1.0] — en préparation

Réécriture complète (« v2 ») : l'implémentation ANTLR historique est
remplacée par un **island parser** écrit à la main — le Python est recopié
verbatim, seuls les îlots RDF sont parsés.

- **Langage** : @prefix/@base à portée par bloc ; IRIs, noms préfixés
  (préfixes déclarés), littéraux RDF (`"x"@en`, `"1"^^xsd:int`), variables
  `?v`/`$v`, IRIs formatées `f<...{expr}...>`, nœuds formatés `f{expr}` /
  `?{expr}`, graphes `g{ ... }` en notation Turtle avec interpolations
  `{expr}` (et suffixes `@lang` / `^^dt`), nœuds anonymes à identité
  déterministe `_:{expr}`, **expressions SPARQL différées** `e{ ... }` et
  IRIs différées `e<...>`.
- **Sûreté** : tout fichier Python pur ressort **byte-identique** (vérifié
  sur la stdlib CPython) ; règles de désambiguïsation documentées et testées.
- **Performance** : 56 000–110 000 lignes source/s selon la densité d'îlots
  (~×500 vs l'implémentation historique) ; runtime de matérialisation
  optimisé (voir OPTIMIZATION.md).
- **Outillage** : language map bidirectionnel (JSON + Source Map v3),
  import hook sans dépendance, console interactive, `ldpy-build`
  (fichiers fantômes), `ldpy-debug` (debugpy), serveur LSP `ldpy-lsp`
  (diagnostics natifs + request forwarding vers pylsp), extension VS Code.
- **Packaging** : `pyproject.toml`, dépendance unique `rdflib` ;
  extras `[lsp]`, `[debug]`, `[dev]`, `[docs]`.

### [0.0.4] / [0.0.3] — 2023 (implémentation historique, ANTLR)

Voir l'archive : https://gitlab.com/coswot/ldpy
