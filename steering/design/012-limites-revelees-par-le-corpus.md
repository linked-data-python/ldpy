# 012 — Catalogue des limites révélées par l'étude de corpus

**Date** : 2026-11-03 · **Statut** : constats établis — catalogue, chaque point traité dans sa fiche

**Source** : revue humaine des 40 traductions de `github/examples/`
(fiche 401), et les campagnes de traduction stratifiée (fiche `corpus/403`).
Chaque point vient d'un exemple réel, validé par exécution.

## Ce qu'est cette fiche

Un **catalogue** : ce qui a été constaté sur du code réel, dans quel état
c'est, et **où c'est traité**. Le raisonnement, les options et les décisions
sont dans les fiches pointées ; cette fiche ne les redit pas.

## Catalogue

### Défauts du transpileur

| Constat | État |
|---|---|
| `;` final avant `]` refusé | corrigé (vérifié) |
| datatype interpolé sur f-string (`f"{v}"^^{dt}`) | corrigé (vérifié) |
| `+{ }` / `-{ }` non capturés après un mot-clé composé (`if x: +{ … }`) — Python invalide émis, sans lever | corrigé, ldpy 0.4.0, commit `90d8b9d` |
| `for @bindings in` coerce à l'entrée et casse la logique Python qui suit (`b["col"] != ""` devient toujours vrai) | corrigé, ldpy 0.4.0, commit `90d8b9d` : `Bindings` garde une face brute, exposée par `b.raw` |
| un îlot dans un trou d'f-string (`f"{m{ ?s ex:p ?o }.first()}"`) est recopié verbatim dans le Python émis, qui ne compile plus ; le message d'erreur vient du parseur d'f-string et ne nomme pas la cause | refusé avec un message qui nomme la cause et le contournement, ldpy 0.6.2, commit `750304e` ; descendre dans le trou reste possible |
| interpolation d'un identifiant nu qui est aussi un préfixe de chaîne Python (`{r}`, `{b}`, `{f}`, `{u}`) : `IndexError` dans le lexer | ouvert — TODO ldpy |
| `@graph NAME .` : le point final est recopié dans le Python émis, l'erreur surgit en aval | ouvert — TODO ldpy |

### Manques structurels, par fiche qui les porte

| Constat | Fiche qui le traite |
|---|---|
| `@prefix` est purement lexical : aucun objet `Namespace` ne survit — quatre formes rencontrées (`DefinedNamespace`, namespace rangé dans un dict/registre exporté, `g.bind(prefix, NS)`, `initNs=` alimenté à l'exécution) | [027](027-prefixe-sans-objet-dexecution.md) |
| `from … import p:` ne s'applique jamais à un fichier entier ; et il suppose un `__namespaces__` que l'écosystème n'exporte quasiment jamais | [013](013-import-export-de-prefixes.md) |
| un `DefinedNamespace` à alias (attribut lisible sans rapport lexical avec l'IRI, ex. `CPO.has_causal_pathway` → `obo:cpo_0000056`) n'a pas d'écriture `@prefix` fidèle | [027](027-prefixe-sans-objet-dexecution.md) |
| mutation seulement par `+=`, qui exige une cible assignable (propriété en lecture seule, graphe global de module) | [014](014-graphe-courant-ajout-retrait.md) |
| `graph.set()` (remplacer, pas accumuler) n'a pas d'îlot, et `+{ }` n'en est pas l'équivalent | [014](014-graphe-courant-ajout-retrait.md) |
| `+{ … ; … }` se factorise sur le sujet **et le chemin de contrôle**, pas sur le sujet seul (un `.add` derrière un `if` ne fusionne pas avec les précédents) | [014](014-graphe-courant-ajout-retrait.md) |
| aucun îlot de *filtrage* (lecture) | résolu : îlot `m{ }`, fiche [016](016-ilot-de-motif-selection.md) |
| `m{ }` projette toutes ses variables : ni projection explicite, ni `DISTINCT` — le nœud anonyme ne remplace la projection qu'en position d'objet, refusé en position de prédicat | [016](016-ilot-de-motif-selection.md) |
| `m{ }` ne paie pas sur un parcours complet (`list(g)` vs `list(m{ ?s ?p ?o }(g))`) | [016](016-ilot-de-motif-selection.md) — recommandation : `list(g)` pour le parcours complet, `m{ }` pour les motifs sélectifs |
| la jointure implicite de `m{ }` change la cardinalité quand les prédicats sont indépendamment optionnels | [016](016-ilot-de-motif-selection.md) |
| `.first()` ne rendait pas un `g.value(…, default)` non-`None` ; `.one()` n'égale pas `next(iter)` (qui ignore le surplus) | résolu : `.first(default=…)`, et `next(iter(m{ … }))` pour `next` sans défaut, fiche [016](016-ilot-de-motif-selection.md) |
| une lecture à plus d'une position libre (`g.subjects()` sans prédicat ni objet) n'a pas de forme brève | [016](016-ilot-de-motif-selection.md) ; `m{ ?s {ANY} {ANY} }` l'écrit depuis `ldpy.ANY` (ci-dessous) |
| `s{ }` exige un texte de requête littéral à la transpilation | [015](015-ilot-sparql.md) |
| `str()` d'une valeur `s{ }` rend le texte de l'îlot, `s{ … }`, sans prologue : une bibliothèque qui lit le texte de la requête plutôt que son algèbre (`vital-ai/vital-graph`, `OptimizedVitalGraph.query` cherche des motifs par expressions régulières dans `str(query)`) peut prendre une autre branche | [015](015-ilot-sparql.md) |
| `s{ }` est validé par la grammaire SPARQL 1.1 de rdflib, sans échappatoire : une requête SPARQL 1.2 (`TRIPLE`, `isTRIPLE`) destinée à un moteur plus récent (Fuseki 5.5, `hidden-graph/rdflib-starlight`) n'a pas d'îlot | [015](015-ilot-sparql.md) |
| l'interpolation de `s{ }` lie une variable, elle n'épisse jamais du texte (une IRI entre chevrons, un motif entier, une clause `FILTER`/`GRAPH` n'ont pas de forme) | [015](015-ilot-sparql.md) |
| hors îlot, un nom préfixé dont la partie locale commence par un chiffre (`brdftime:2011`) n'est pas reconnu (erreur de syntaxe Python) ; dans un îlot, il l'est (`BONSAMURAIS/arborist`) | à instruire : la grammaire Turtle l'admet, la reconnaissance hors îlot évite `x[a:1]` |
| hors îlot, un nom préfixé s'arrête au point : `fhir:Extension.url` se lit `fhir:Extension` suivi de l'attribut `.url` (AttributeError), et `\.` est refusé ; une IRI complète `<…>` est obligatoire (`BD2KOnFHIR/fhirtordf`, campagne d'optimisation du 2026-11-03) | à instruire : la grammaire Turtle admet le point au milieu de la partie locale, Python y voit un accès d'attribut |
| `Literal(expr)` nu hors îlot n'a pas de notation ; un tag de langue variable s'écrit `{v}@{k}` depuis 2026-11-02 | [020](020-coercition-python-rdf.md) |
| une chaîne qui *ressemble* à une IRI se coerce en littéral, sans erreur — vu en interpolation de `m{ }`/`s{ }` (l'`ASK` s'évalue `False` sans erreur sur `RDFLib/VocPrez`) | [020](020-coercition-python-rdf.md) |
| `^^` et `@lang` n'existent qu'en position de terme ; hors îlot, `f{ }` ne gagne que sur la coercition non typée | [020](020-coercition-python-rdf.md) |
| l'espace `Dataset` / graphes nommés hors SPARQL n'a pas d'îlot | [028](028-espace-des-graphes-nommes.md) |

### Points à part

| Constat | État |
|---|---|
| un motif reçu en DONNÉE (un `(s, p, o)` avec `None`, API `Store`, helper `delete(pattern)`) interpolé dans `-{ }`/`m{ }` faisait passer `None` par `node()`, qui en faisait `Literal('None')` : `-{ }` **ne retirait rien sans lever**, le pire mode d'échec possible | décidé par Maxime le 2026-11-01, implémenté : voir « `None` et `ldpy.ANY` » ci-dessous |
| un `Path` de rdflib (`EX.p / EX.q`) interpolé dans `m{ }` passait par `node()`, qui en faisait `Literal('Path(…)')` : le motif ne trouvait rien, sans lever — le mode d'échec que la décision sur `None` a fermé. La lecture `g.value(s, A / B)` restait donc `g.value` (`comp-rob2b/kindyngen`, `inertial_wrench`, classée `awkward`) | décidé par Maxime le 2026-11-02, implémenté : voir « Un chemin de propriété rdflib » ci-dessous |
| le coût de `None` qui lève, mesuré par la reprise : rdflib propage `None` le long d'une chaîne `g.value(g.value(…))` et `(None, p, o) in g` est un joker, alors qu'un `{x}` nul lève. Il faut une garde par pas (`… if x is not None else None`, `BD2KOnFHIR/fhirtordf`, classée `awkward`) ou `.first() or ANY` (`ArangoDB-Community/ArangoRDF`). Remplacer la chaîne par une jointure change la cardinalité (premier par pas contre n'importe quel chemin) | acté : c'est le prix voulu de la décision du 2026-11-01, que les deux régions rendent visible |
| `-{ }` multi-motifs joint (`DELETE WHERE`) : si un seul motif ne trouve pas de solution, rien n'est effacé — silencieux, alors que trois `remove()` rdflib indépendants retireraient partiellement | acté : pas d'avertissement dans la documentation — la différence entre un `-{ }` à trois motifs et trois `remove()` est évidente pour un humain qui lit le code |

## Confirmations (comportements voulus, vérifiés sur du code réel)

- **Transparence exacte** : sur les régions où aucune structure RDF n'apparaît
  dans la source, la traduction est identique au caractère près. La notation
  ne coûte rien là où elle ne sert pas.
- **Les chaînes restent opaques** : les CURIE portées par des *données*
  (`method="qb:CodedProperty"`, requêtes SPARQL, configurations INI) ne sont
  jamais capturées.
- **Le `:` d'un pname s'arrête avant celui d'un dict** :
  `{ qudt:hasDimensionVector: qudtdv:A0E0... }` fonctionne (BrickSchema).
- **Piège de fidélité** : `Literal(40, datatype=XSD.double)` n'est PAS le même
  terme que `"40"^^xsd:double` (rdflib normalise la forme lexicale en `40.0`).
  Une règle mécanique `Literal(n, dt)` → `"n"^^dt` est donc **incorrecte** ; le
  traducteur ne l'applique pas.
- **Piège `@base`** : réécrire `URIRef(x)` en `f<{x}>` n'est exact que si aucun
  `@base` n'est en portée (sinon `firi()` résout le relatif) — documenté dans
  le guide de migration.
- **L'import de préfixes marche depuis un module Python ordinaire** : le
  `__namespaces__` d'un module `.ldpy`, ou un attribut `p` / `P` qui est un
  `Namespace`, une IRI ou un `DefinedNamespace` (fiche
  [013](013-import-export-de-prefixes.md)). Dans la reprise du 2026-11-02, des
  paires importent leurs préfixes du module de namespaces du dépôt lui-même
  (`apysource.namespaces`, `kindynsyn.namespaces`, `plastron.namespaces`,
  `nanopub.namespaces`). Le gain se **compose** avec celui du `;` : un
  îlot multi-triplets qui écrit plusieurs termes du même vocabulaire paie
  deux fois.
- **`@graph` accepte une expression d'attribut** (`@graph self.graph`,
  `@graph result.graph`), ce qui rend `+{ }` / `-{ }` utilisables tels quels
  dans du code orienté objet là où `g += g{ }` échouait sur une propriété en
  lecture seule.
- **Le suffixe d'appel porte le code multi-graphes** : une fonction qui
  manipule six graphes vivants n'en désigne qu'un par `@graph`, et c'est
  `-{ … }(g)` / `m{ … }(g)` qui traduit le reste. Quand un graphe n'est touché
  qu'une fois, le suffixe coûte même une ligne de moins que la déclaration.
- **Le joker fait exactement ce que la référence promet**, sur les trois
  positions, y compris l'effacement multi-valeurs d'un coup.

## `None` et `ldpy.ANY`

Décision de Maxime du 2026-11-01, sur proposition :

- **`node(None)` lève `TypeError`**, donc toute interpolation `{x}` qui
  vaut `None`, dans les six îlots : `-{ }`, `m{ }`, `+{ }`, `g{ }`, et
  `s{ }` à l'exécution. Le message nomme les deux écritures voulues : une
  variable (`?any` dans `-{ }`, `[]` non projeté dans `m{ }`) et
  `ldpy.ANY`.
- **`ldpy.ANY`** (`ldpy.runtime.ANY`, exporté au niveau du paquet) est le
  joker de rdflib sous un nom qui ne se confond pas avec une valeur
  manquante. `node()` le laisse passer. Dans `-{ }`, il devient le `None`
  de `remove()` ; dans `m{ }`, une variable fraîche par occurrence, jamais
  projetée ni partagée — deux `ANY` sont deux jokers ; dans `s{ }`, il
  laisse la variable non liée. `+{ }` et `g{ }` le refusent : un joker ne
  s'écrit pas. Il tient aussi la place que `[]` ne peut pas tenir, en
  position de prédicat : `m{ ?s {ANY} {ANY} }` est le `g.subjects()` sans
  argument du catalogue.
- **Dans des liaisons, `None` reste « non lié »** — la convention que
  `instantiateBGP` et `_bind_get` appliquaient déjà : une cellule vide
  d'une ligne CSV dans `for @bindings in …` fait tomber les triplets qui en
  ont besoin, au lieu d'écrire le littéral `"None"` ou de lever au milieu
  de la boucle. Seule l'**interpolation** de `None` lève — y compris
  comme type de données calculé : `{v}^^{dt}` avec `dt` nul typait le
  littéral `<None>`, il lève (`dtype()`, trouvé par l'étude d'optimisation
  du corpus, `tableau/altimeter`) ; et comme partie locale calculée :
  `ex:{x}` avec `x` nul nommait `ex:None`, il lève (`pname()`,
  `d3fend/d3fend-ontology`).

Documentation : `querying.md` (`m{ }` et `s{ }`), `current-graph.md`
(table de `-{ }`), `bindings.md`, `migrate-from-rdflib.md` (table et
piège 5), `api.md`, info-bulle de `-{ }`. Tests :
`tests/test_none_and_any.py`.

## Un chemin de propriété rdflib

Décision de Maxime du 2026-11-02, sur proposition :

- **En position de prédicat de `m{ }`, un `Path` est passé tel quel à
  `graph.triples()`**, qui l'évalue : `m{ {s} {A / B} ?o }.first()` vaut
  `g.value(s, A / B)`, sans moteur nouveau. `m{ }` ne gagne pas de syntaxe
  de chemin : le chemin s'écrit en Python, avec les opérateurs de rdflib,
  et s'interpole. Le transpileur émet `pnode()` au lieu de `node()` pour
  cette seule position.
- **Partout ailleurs, `node()` lève `TypeError`** sur un `Path` : sujet ou
  objet de `m{ }`, toute position de `+{ }`, `-{ }`, `g{ }`, `s{ }`. Un
  chemin n'est pas un terme, ne s'écrit pas, ne se retire pas.
- Sous MicroPython, urdflib n'a pas de chemins (`backend.Path` vaut
  `None`) : rien ne change.

Documentation : `querying.md` (« What `m{ }` does not have »), `api.md`.
Tests : `tests/test_match_path.py`.

## Ce qui reste

- Les deux défauts ouverts du catalogue : `{r}` et ses pareils, `@graph NAME .`.
- Constat d'un agent de la campagne d'optimisation, non vérifié : dans
  `m{ {tm} r2rml:predicateObjectMap [ r2rml:objectMap ?om ] }`, le triple
  intérieur du `[ ]` serait évalué d'abord, ce qui balaie tous les
  `rr:objectMap` du graphe à chaque appel (`kumagallium/asterism`) ;
  l'ordre des motifs écrits devrait gouverner la jointure. À vérifier sur
  le code engendré.
- `docs/reference/language/current-graph.md` dit encore « designate the
  existing Python variable `g` » : `@graph g` capture la **valeur** de `g`,
  pas le nom, et une réaffectation ultérieure envoie les écritures dans un
  graphe que plus rien n'atteint.
- Une chaîne qui ressemble à une IRI, interpolée dans `s{ }`, devient un
  littéral sans erreur (catalogue, renvoi 020) : à verser aux pièges de
  `migrate-from-rdflib.md` et à la référence de `s{ }`.
- `ex:{expr}` est refusé dans `s{ }` avec le message du parseur SPARQL de
  rdflib (« Expected SelectQuery, found '?' »), qui ne nomme pas la cause ;
  le contournement `@prefix … as S .` puis `{S[term]}` existe. Remède
  prévu : un refus qui se nomme, comme pour `?v@en` (fiche 027) ; depuis
  que `f<…{expr}…>` se lie dans `s{ }` (fiche 015), lier `ex:{expr}` de
  la même façon serait le remède cohérent.
- Verser au catalogue les constats de la campagne du 2026-09-03 restés
  hors fiche : `_:label` n'est pas `BNode("label")`, les lectures sans îlot,
  la dérive de lignes.

## Ce que le catalogue dit d'ensemble

Les manques structurels ne sont pas des bugs : ils délimitent honnêtement ce
que la notation adresse — l'**écriture** et la **lecture** de structures RDF
dans le texte du programme — et ce qu'elle n'adresse pas : les namespaces
comme objets, le SPARQL construit à l'exécution, l'espace des graphes nommés
hors requête. L'article les énonce tels quels en §Corpus Study, « What the
notation does not reach ».

Un fait ressort du catalogue relu d'un bloc : **les défauts les plus coûteux
sont silencieux.** Le mot-clé composé émettant du Python invalide sans lever,
la chaîne coercée en littéral, la jointure implicite de `m{ }` — trois fois,
le programme tourne et personne n'est prévenu. C'est le meilleur argument pour
l'oracle d'exécution de l'étude : une relecture les aurait tous validés.
