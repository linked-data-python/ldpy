# design — index des décisions de conception de ldpy

Un fichier par décision. Une fiche dit **l'état d'aujourd'hui** : la décision
en vigueur, les défauts non encore résolus, les questions ouvertes — pas
l'historique, qui est dans `git log` et dans `../steps/`.

Ces fiches vivaient dans le dépôt de pilotage commun aux neuf dépôts de
l'espace de travail ; elles sont ici depuis le 2026-09-11, pour que les
décisions voyagent avec le code qu'elles décident. Le carnet d'avant cette
date est resté là-bas : il mêle ldpy aux autres projets et un document daté
ne se réécrit pas.

| # | Fiche | Décision en une ligne | Statut |
|---|---|---|---|
| 001 | [001-architecture-globale.md](001-architecture-globale.md) | Island parsing écrit à la main, zéro dépendance au parsing | acté |
| 002 | [002-desambiguisation-lexicale.md](002-desambiguisation-lexicale.md) | Règle du « contexte opérande » + absence d'espace + préfixes déclarés | acté |
| 003 | [003-emission-sans-hoisting.md](003-emission-sans-hoisting.md) | Les graphes deviennent UNE expression (helper runtime), plus de hoisting | acté |
| 004 | [004-semantique-prefix-base.md](004-semantique-prefix-base.md) | @prefix/@base : portée lexicale PAR BLOC (révisé) ; dérogation par `global`/`nonlocal` en fiche 018 | acté |
| 005 | [005-language-map.md](005-language-map.md) | Map segment-level bidirectionnelle, JSON `.ldpy.map` + export Source Map v3 ; les termes d'un îlot vivent SUR son segment (`parts`), hors de la liste plate | acté |
| 006 | [006-strategie-tests.md](006-strategie-tests.md) | Golden + identité + exécution (rdflib oracle) + edge cases | acté |
| 007 | [007-extension-sparql.md](007-extension-sparql.md) | e{...}/e<...> : PHASE 2 IMPLÉMENTÉE (sémantique SPARQL autonome, différée) ; graphes-gabarits = phase 3 | implémenté — phase 2 faite ; la phase 3 est en fiche 017 |
| 008 | [008-runtime-et-compat-micropython.md](008-runtime-et-compat-micropython.md) | Runtime minimal, code émis garanti sous-ensemble MicroPython, console interactive | acté |
| 009 | [009-artefact-evaluation.md](009-artefact-evaluation.md) | Banc de débit par génération aléatoire seedée (lignée Csmith/QuickCheck) | implémenté — `bench/` |
| 010 | [010-jeux-de-caracteres.md](010-jeux-de-caracteres.md) | Python ID vs PN_CHARS incomparables ; état figé par tests, décision finale ouverte | implémenté — divergence résiduelle documentée côté explanation |
| 011 | [011-compilation-remappee.md](011-compilation-remappee.md) | Code objects en coordonnées .ldpy (AST remappé) : tracebacks/pdb/debugpy natifs | acté |
| 012 | [012-limites-revelees-par-le-corpus.md](012-limites-revelees-par-le-corpus.md) | **Catalogue** des limites constatées sur code réel : chaque point renvoie à la fiche qui le traite ; historique des vagues conservé | constats établis — catalogue, chaque point traité dans sa fiche |
| 013 | [013-import-export-de-prefixes.md](013-import-export-de-prefixes.md) | Tout `@prefix` de module est exporté ; `from m import brick:` ; régime unique, dynamique. Condition d'applicabilité mesurée : l'écosystème n'exporte quasiment jamais `__namespaces__` | implémenté — extension aux `Namespace` rdflib ordinaires à trancher |
| 014 | [014-graphe-courant-ajout-retrait.md](014-graphe-courant-ajout-retrait.md) | `@graph` (désigner ou créer, `<iri> as g` inclus) ; `+{ … }` / `-{ … }` en position d'instruction | implémenté |
| 015 | [015-ilot-sparql.md](015-ilot-sparql.md) | Îlot `s{ … }` : tout SPARQL, validé à la transpilation par rdflib comme oracle ; deux frontières mesurées (texte littéral exigé, interpolation ≠ épissure) | implémenté |
| 016 | [016-ilot-de-motif-selection.md](016-ilot-de-motif-selection.md) | Lecture par îlot de motif `m{ … }` (BGP sans moteur) ; distinct de `g{ }` par l'opérateur, pas par la syntaxe ; règle de jointure (chaîne obligatoire vs prédicats optionnels) | implémenté |
| 017 | [017-bindings-et-gabarits.md](017-bindings-et-gabarits.md) | `@bindings` (désigner / créer / `for @bindings in …`) et `e{ … }` en position de terme dans `g{ … }` | implémenté |
| 018 | [018-modificateurs-de-portee.md](018-modificateurs-de-portee.md) | `global` / `nonlocal` devant `@prefix`, `@base`, `@graph`, `@bindings` | implémenté |
| 019 | [019-suffixe-d-appel-contexte-explicite.md](019-suffixe-d-appel-contexte-explicite.md) | Un îlot suivi d'une parenthèse reçoit son contexte : graphe d'abord, binding ensuite | implémenté |
| 020 | [020-coercition-python-rdf.md](020-coercition-python-rdf.md) | Coercition Python → RDF centralisée dans `node()` ; politique `Coercion` (champ ou type), empilable par `with` ; piège de la chaîne-qui-est-une-IRI mesuré sur trois dépôts | implémenté |
| 021 | [021-coloration-multi-frameworks.md](021-coloration-multi-frameworks.md) | Une spécification des îlots (`highlight-ldpy`), cinq moteurs : Pygments, TextMate, highlight.js, Prism, CodeMirror 6 ; le transpileur arbitre | chantier ouvert — cinq moteurs faits, Rouge et tree-sitter restent |
| 022 | [022-nommage.md](022-nommage.md) | Le nom reste `linked-data-python` / ldpy : alternatives examinées (Atoll, rdfpy, RDFx, `.rdf.py`), toutes en collision plus grave | tranché |
| 023 | [023-coloration-html-lexer-pygments.md](023-coloration-html-lexer-pygments.md) | Coloration HTML : un lexer Pygments qui LIT la language map — le surligneur est le transpileur | implémenté |
| 024 | [024-formateur.md](024-formateur.md) | Formateur : black pour le Python (îlots masqués), bordures seules normalisées ; transparence, idempotence, AST inchangé | implémenté |
| 025 | [025-console-etat-des-declarations.md](025-console-etat-des-declarations.md) | La console transporte graphe et liaisons courants comme elle transportait les préfixes ; `""` n'est pas un blanc, une erreur sémantique n'est pas une entrée inachevée ; tous les snippets de la doc rejoués à la console | implémenté — trois bogues levés au passage |
| 026 | [026-backend-et-cible-micropython.md](026-backend-et-cible-micropython.md) | Backend (rdflib/urdflib, choisi par le contexte) et SPARQL (`e{ }` pur Python, `s{ }` ⇒ rdflib) sont deux axes, pas deux exclusifs ; `--target micropython` refuse `s{ }` à la construction et embarque le runtime ; le même programme tourne sur MicroPython | implémenté — mode 1 de la fiche 304 vérifié sur le portage Unix |
| 027 | [027-prefixe-sans-objet-dexecution.md](027-prefixe-sans-objet-dexecution.md) | Les issues au manque le plus attesté de l'étude : `@prefix` ne produit aucune valeur Python. Héritage des préfixes par un graphe DÉSIGNÉ + `@prefix ex: <…> as EX .` pour garder l'objet ; préfixes connus à l'exécution et `DefinedNamespace` écartés et documentés comme frontières | implémenté — livré en ldpy 0.6.3 |
| 028 | [028-espace-des-graphes-nommes.md](028-espace-des-graphes-nommes.md) | `Dataset` / graphes nommés : l'écriture passe par `@graph expr`, l'interrogation par `s{ … }`, la lecture sans requête reste rdflib — mesurer avant de décider | constats établis — arbitrage à ouvrir |
