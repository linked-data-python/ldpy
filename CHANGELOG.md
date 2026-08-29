## Release Notes

### [0.4.0] — 2026-08-29

Les suites de l'étude de corpus (fiche 012), arbitrées par Maxime le
2026-08-29 : quatre points où la notation coûtait plus qu'elle ne rapportait,
ou se trompait en silence.

- **`ex:{?id}` s'instancie** (fiche 017, piste 1). La partie locale d'un nom
  préfixé était la seule position de terme où une variable ne s'instanciait
  pas : `ex:{?id}` rendait `ex:id` — la même IRI à chaque ligne, sans erreur,
  juste au moment où l'on forge une IRI depuis une colonne. `pname()` rend
  désormais une expression différée dès qu'une partie est une `Variable` ou
  une `Expression`, et le matérialiseur la résout comme les autres : non
  liée, le triplet est écarté au lieu d'être écrit faux. Sur une valeur
  ordinaire, `ex:{expr}` reste **immédiat** et ne demande aucun binding.
  Comme avant, `ex:{…}` concatène sans encoder ; c'est `e<…{?id}>` qui
  encode.
- **`+{ }` et `-{ }` en suite d'instruction composée** (fiche 012, point 12) :
  `if cond: +{ … }` sur une ligne. La règle « tête de ligne logique »
  obligeait à ouvrir un bloc pour chaque `if cond: g.add(…)`, et la
  traduction sortait *plus longue* que l'original — 5 lignes pour 13 sur un
  dépôt écrit en one-liners. Le cas était de surcroît **silencieux** : le
  transpileur émettait du Python invalide sans lever. Les positions que
  Python revendique (annotation `x: int`, `lambda ex: ex`, dict, différence
  d'ensembles) sont inchangées.
- **`b.raw`** (fiche 012, point 22) : la ligne telle qu'elle est arrivée, à
  côté des termes. La coercition à l'entrée de `@bindings` casse l'égalité —
  `Literal("") != ""` — et `if row[col] != "":` est le garde le plus courant
  d'un script CSV → RDF. `b[key]` reste le terme, `b.raw[key]` rend la valeur
  Python ; en lecture seule, on écrit par `b[key]`.
- **Avertissement « préfixe déclaré = nom Python »** (fiche 002) : annoncé
  par la fiche depuis l'origine, jamais implémenté. L'heuristique retenue —
  le nom en tête d'instruction suivi de `=` ou `,` — attrape la façon dont le
  cas se présente réellement, et le message donne l'échappatoire (`{ex: x}`
  avec une espace).
- **Documentation** : traduire `set(g.subjects())`, garder `list(g)` pour le
  parcours complet, les receveurs du suffixe d'appel (`+{ }(self.store)`,
  attribut, indice, appel de méthode), la mise en garde « une chaîne qui
  ressemble à une IRI reste un littéral », et une explication des deux jeux
  de caractères. Suite : 1 391 → 1 421 tests.

### [0.3.0] — 2026-08-29

- **Le LSP ne relaie plus le style du code généré** : pylsp jugeait l'ombre
  Python (lignes longues, indentation de continuation, points-virgules…) et
  ses remontées, reprojetées sur le `.ldpy`, soulignaient des îlots entiers —
  les « pâtés rouges » sur chaque îlot multi-lignes. Le serveur désactive
  désormais les greffons de style du backend (pycodestyle, mccabe, flake8,
  pylint, pydocstyle, autopep8, yapf) et filtre par défense ce qu'un backend
  enverrait quand même ; les analyses sémantiques (pyflakes : noms non
  définis, imports inutilisés) restent (fiche vscode/107).
- **`serverInfo` du LSP annonce la version installée** au lieu d'une copie
  écrite en dur — même règle que 0.2.1, appliquée au dernier endroit oublié.

### [0.2.1] — 2026-08-29

- **Le chemin du fantôme est absolu** : `ldpy.debug --breakpoints` rendait un
  chemin relatif, que VS Code enracinait à `/` — « Show transpiled Python »
  échouait sur `/.ldpy-build/x.py`. Une sortie qui traverse un processus ne
  peut pas être relative.
- **La version n'est plus écrite en double** : elle vient de la distribution
  installée. Les deux copies avaient dérivé, et un paquet 0.2.0 s'annonçait
  `0.1.0.dev0` dans la barre d'état de l'éditeur.
- **Documentation** : les liens du README pointent vers le site publié. En
  relatif, ils ne menaient nulle part une fois la page rendue par PyPI.

### [0.2.0] — 2026-08-29

**Le langage conçu depuis le corpus** : huit constructions nouvelles, chacune
dérivée d'une mesure sur 5 190 fichiers de 376 dépôts publics utilisant
rdflib (fiches ldpy/013 à 020).

- **Préfixes entre modules** : tout `@prefix` de niveau module est exporté ;
  `from vocab import brick:, unit: as u:` importe des préfixes, en régime
  unique dynamique (le transpileur ne lit jamais le module importé) ;
  `@prefix ex: f<http://{host}/ns#> .` — IRI calculée, même chemin.
- **Graphe courant** : `@graph expr` désigne, `@graph as g` crée,
  `@graph <iri> as g` crée un graphe nommé ; `+{ ... }` / `-{ ... }`
  ajoutent/retirent en tête de ligne — sans `+=`, donc les propriétés en
  lecture seule et les globaux de module s'écrivent sans contorsion ;
  variable non liée : triplet écarté à l'ajout, joker au retrait
  (`DELETE WHERE` à plusieurs motifs).
- **Îlot SPARQL `s{ ... }`** : tout SPARQL, validé à la transpilation
  (rdflib en oracle) ; interpolations en position de terme uniquement,
  compilées en `initBindings` — l'injection de chaîne disparaît par
  construction ; requête préparée paresseuse, cache borné.
- **Îlot de motif `m{ ... }`** : un BGP Turtle à variables contre le graphe
  courant, jointure par boucles imbriquées dans l'ordre écrit — aucun
  moteur, rien que `triples()` ; arité 1 → termes, sinon lignes nommées ;
  `first()`, `one()`, `count()`, valeur de vérité paresseuse (ASK) ; nœud
  anonyme = variable non distinguée.
- **`@bindings` et gabarits** : binding courant à portée par bloc ;
  `for @bindings [as b] in ...` fait de chaque mapping d'un itérable (les
  solutions d'un `m{ }`, un `csv.DictReader`) le binding du corps ; sans
  binding un `g{ }` à variables reste un gabarit, avec il s'instancie ;
  `e{ ... }`/`e<...>` acceptés en position de terme (phase 3 de la fiche 007).
- **Suffixe d'appel** : un îlot suivi d'une parenthèse reçoit son contexte —
  graphe d'abord, binding ensuite : `m{P}(g, b)`, `s{Q}(g, b)`, `+{P}(g)`,
  `g{P}(b)` (gabarit instancié), `e{E}(b)`.
- **`global` / `nonlocal`** devant les quatre déclarations d'îlot, avec la
  sémantique exacte de Python.
- **Coercition configurable** : `ldpy.Coercion({("age",): XSD.integer,
  ("uri",): URIRef, date: XSD.date})` — par champ puis par type, empilable
  par `with`, `install()` pour le module ; `node()` reste le point d'entrée
  unique, au coût inchangé sans politique.
- **Formateur** : `ldpy-format` (CLI, `--check`/`--diff`) et
  `textDocument/formatting` côté serveur — donc « Format Document » et
  `formatOnSave` dans tout éditeur LSP. Le Python est délégué à **black**
  (extra `[format]`, îlots masqués par des substituts de même poids) ; les
  îlots ne voient normaliser que leurs bordures, leur corps est recopié tel
  quel. Trois propriétés testées sur toute la documentation : sans îlot, le
  résultat est **exactement** celui de black ; formater est idempotent ;
  l'AST du Python transpilé ne bouge pas (fiche 024).
- **Débogage : un pas ne ment plus** (fiche vscode/103). Un harnais DAP
  (`tests/dapclient.py`) pilote un vrai debugpy et mesure où le débogueur
  s'arrête. Il a montré que le **lanceur** (`-m ldpy.debug`) apparaissait dans
  la pile d'appels et attrapait le pas suivant la dernière ligne, et qu'un
  point d'arrêt posé dans un îlot multiligne était annoncé « vérifié » sans
  jamais se déclencher. `stepping_rules()` masque le lanceur toujours et le
  runtime sous `justMyCode` ; `--probe` les publie pour l'outillage ;
  `snap_breakpoint_lines()` rabat un point d'arrêt intenable, que l'extension
  déplace visiblement.
- **Coloration HTML** : le paquet enregistre un lexer Pygments
  (`ldpy.pygments_lexer`) construit **sur la language map** — MkDocs, Sphinx et
  `pygmentize` colorent `.ldpy` dès l'installation, et la coloration ne peut
  pas diverger du transpileur (fiche 023).
- **Documentation refondue** : page d'accueil qui montre le langage plutôt que
  son plan ; référence du langage éclatée en huit pages, une par famille
  d'îlots ; trois pages d'explication nouvelles — pourquoi ldpy, ce que fait le
  vrai code RDF (l'étude de corpus, chiffres à l'appui), comment la syntaxe a
  été conçue — et une page « comment tout cela est testé » qui dit aussi ce qui
  ne l'est pas ; deux tutoriels, quatre guides pratiques nouveaux
  (données tabulaires, lecture et requêtes, migration depuis rdflib,
  coloration).

**Corrections** (toutes trouvées en écrivant cette documentation, toutes avec
tests de régression) :

- **Transparence de l'hôte** : un `:` dans un *commentaire* de liste d'import
  parenthésée déclenchait l'îlot d'import de préfixes, réécrivait l'instruction
  et produisait du code non compilable. Le test d'identité tourne désormais sur
  la bibliothèque standard de CPython (464 fichiers, ~260 000 lignes), qui est
  ce qui l'a trouvé.
- **Graphes paresseux** : une liste en attente **vide** n'éteignait pas le mode
  paresseux, si bien que `g = g{ }` suivi de `g += g{…}` ou de `g.add(…)`
  laissait le graphe vide. `__iadd__` devient paresseux au passage.
- **Promotion numérique SPARQL** : la promotion portait sur le type du résultat
  mais pas sur les opérandes — `xsd:double * xsd:decimal` levait un `TypeError`
  Python, avalé en « terme non lié ».
- **Expression différée en sujet partagé** : `+{ e<http://e/{?id}> ex:p 1 ;
  ex:q 2 }` produisait un littéral portant le texte source de l'îlot ; le cas à
  un seul triplet fonctionnait, ce qui rendait le défaut discret.
- `PreparedQuery.execute()` : forme publique pour exécuter un îlot `s{ }`, ce
  qu'exige un UPDATE (il n'a pas de solutions à itérer).
- Suite : 425 → 867 tests ; débit inchangé (~60 000 lignes/s).

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
