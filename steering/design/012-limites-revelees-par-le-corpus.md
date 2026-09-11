# 012 — Catalogue des limites révélées par l'étude de corpus

**Date** : 2026-09-03 · **Statut** : constats établis — catalogue, chaque point traité dans sa fiche

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
| un îlot dans un trou d'f-string (`f"{m{ ?s ex:p ?o }.first()}"`) est recopié verbatim dans le Python émis, qui ne compile plus ; le message d'erreur vient du parseur d'f-string et ne nomme pas la cause | ouvert — TODO ldpy. Deux réponses possibles : descendre dans les trous d'f-string comme dans le reste (le trou est un contexte d'expression, R1 s'y appliquerait naturellement), ou refuser explicitement avec un message qui le dise — moins cher, supprime l'essentiel du mal |
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
| `.first()` ne rend pas un `g.value(…, default)` non-`None` ; `.one()` n'égale pas `next(iter)` (qui ignore le surplus) | [016](016-ilot-de-motif-selection.md) |
| une lecture à plus d'une position libre (`g.subjects()` sans prédicat ni objet) n'a pas de forme brève | [016](016-ilot-de-motif-selection.md) |
| `s{ }` exige un texte de requête littéral à la transpilation | [015](015-ilot-sparql.md) |
| l'interpolation de `s{ }` lie une variable, elle n'épisse jamais du texte (une IRI entre chevrons, un motif entier, une clause `FILTER`/`GRAPH` n'ont pas de forme) | [015](015-ilot-sparql.md) |
| `Literal(expr)` nu hors îlot n'a pas de notation ; un tag de langue variable non plus | [020](020-coercition-python-rdf.md) |
| une chaîne qui *ressemble* à une IRI se coerce en littéral, sans erreur — vu en interpolation de `m{ }`/`s{ }` (l'`ASK` s'évalue `False` sans erreur sur `RDFLib/VocPrez`) | [020](020-coercition-python-rdf.md) |
| `^^` et `@lang` n'existent qu'en position de terme ; hors îlot, `f{ }` ne gagne que sur la coercition non typée | [020](020-coercition-python-rdf.md) |
| l'espace `Dataset` / graphes nommés hors SPARQL n'a pas d'îlot | [028](028-espace-des-graphes-nommes.md) |

### Points à part

| Constat | État |
|---|---|
| un motif reçu en DONNÉE (un `(s, p, o)` avec `None`, API `Store`, helper `delete(pattern)`) interpolé dans `-{ }`/`m{ }` fait passer `None` par `node()`, qui en fait `Literal('None')` : `-{ }` **ne retire rien sans lever**, le pire mode d'échec possible | **en attente d'arbitrage**. Proposition rédigée : `node(None)` lève `TypeError`, le message nommant les deux écritures intentionnelles — la variable (`?any` en joker dans `-{ }`, nœud anonyme `[]` non projeté dans `m{ }`) et un alias exporté `ldpy.ANY` (le joker `triples()`/`remove()` de rdflib), que `node()` laisserait passer tel quel. Même règle proposée pour les interpolations de `m{ }` : `{x}` avec `x is None` lèverait au lieu de matcher un littéral |
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
- **L'import de préfixes marche depuis un module Python ordinaire**, à
  condition qu'il exporte `__namespaces__` — un module `.ldpy` le fait
  automatiquement, un `.py` peut le faire à la main
  (`__namespaces__ = {"aorc": AORC}`) ; c'est le protocole qu'exige la forme,
  pas l'extension du fichier. Le gain se **compose** avec celui du `;` : un
  îlot multi-triplets qui écrit plusieurs termes du même vocabulaire paie deux
  fois.
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
