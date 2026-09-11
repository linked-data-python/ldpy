# 004 — Sémantique de @prefix et @base (le problème « @prefix dans une boucle »)

**Date** : 2026-09-03 · **Statut** : acté

## Contexte — problèmes que v1 n'avait pas traités

v1 mélangeait deux mondes : le visiteur enregistrait les préfixes dans un dict *à la
transpilation* (`self.namespaces`) ET émettait `__namespaces__['ex'] = ...` *à
l'exécution*. Conséquences non maîtrisées :

1. **@prefix dans une boucle / un if / une fonction** : la résolution statique des
   pnames l'appliquait dès sa position lexicale, même si le flot d'exécution ne
   passait jamais par la déclaration. Sémantique incohérente et non documentée.
2. **Fuite inter-modules** : `config.namespaces` était un état GLOBAL partagé — les
   préfixes d'un module importé fuyaient dans le suivant.
3. **Redéclaration** d'un préfixe : silencieuse, dernier gagnant, y compris à
   l'intérieur d'un bloc.
4. `@prefix` vs décorateur : un décorateur nommé `prefix` ou `base` est
   syntaxiquement possible en Python (`@prefix` seul sur sa ligne).

## Décision

1. **Portée lexicale, par bloc englobant.** Une déclaration `@prefix ex: <iri> .`
   / `@base <iri> .` prend effet de sa position jusqu'à la **fin de la suite qui
   la contient** (corps de if/else/for/while/try/except, de fonction, de classe).
   Au top-level : jusqu'à la fin du fichier (comportement Turtle). La sortie du
   bloc **restaure** la liaison antérieure — le shadowing fonctionne, y compris
   pour `@base` (résolution relative contre la base externe, puis restauration).
   La résolution des pnames, IRIs relatives et f-IRIs est faite À LA
   TRANSPILATION avec la table lexicalement visible à ce point, indépendamment du
   flot d'exécution ; aucune fuite entre fichiers (la table est un état du
   transpileur par fichier, pas un global). La portée reste *lexicale* (elle suit
   le texte, pas le flot d'exécution) — nuance à garder : ce n'est pas une portée
   dynamique au sens PL.
2. **Mécanique** : pile de portées indexée sur l'indentation de la déclaration ;
   toute instruction de profondeur crochets 0 dont l'indentation est strictement
   inférieure dépile et restaure. Lignes blanches, commentaires en colonne 0,
   continuations entre crochets et g{...} multilignes ne ferment pas un bloc. La
   résolution reste entièrement **à la transpilation** (aucun coût runtime).
3. **Hors de portée** : le texte `p:t` redevient du Python intact (exigence R3 —
   impossible d'en faire une erreur sans casser dicts et slices) ; un **warning
   « préfixe hors de portée »** est émis si le préfixe a été déclaré plus haut
   dans le fichier. Un nom jamais déclaré ne déclenche rien.
4. **Redéclaration au même niveau d'indentation : autorisée** (fidèle à Turtle,
   dernier gagnant lexical). Warning si elle change l'IRI d'un préfixe déjà
   utilisé plus haut. Le shadowing dans un bloc plus profond est silencieux.
5. **Émission runtime conservée** : chaque déclaration émet aussi
   `__namespaces__['ex'] = _ldpy_.Namespace('...')` (resp. `__base__ = '...'`) à sa
   place — pour l'introspection, `instantiateBGP`, et la liaison des préfixes de
   sérialisation des graphes (dynamique, fiche 003). Si la déclaration est dans un
   bloc non exécuté, seule la *liaison cosmétique* manque à l'exécution — la
   résolution des termes, elle, est déjà faite. `__namespaces__` à l'exécution
   suit donc le flot, contrairement à la résolution statique des termes.
6. **Désambiguïsation décorateur** : `@prefix`/`@base` n'est un îlot que si la suite
   de la ligne matche `NAME? ':' … '<…>' … '.'` / `'<…>' … '.'`. Sinon c'est un
   décorateur Python ordinaire (`@prefix` suivi d'un saut de ligne, de `(` ou de `.attr`).
7. **Sortir de la portée par bloc** : les modificateurs Python `global` et
   `nonlocal` permettent d'y déroger explicitement — `global @prefix`,
   `global @base` — avec exactement leur sémantique Python. Ils s'appliquent de la
   même façon aux déclarations d'îlot `@graph` (fiche 014) et `@bindings`
   (fiche 017). Spécification unique en fiche 018.

## Cas de test imposés

- @prefix au top-level, utilisé avant/après déclaration (avant → erreur de
  transpilation claire « préfixe non déclaré »).
- @prefix dans `if False:` → pnames résolues quand même ; `__namespaces__` sans
  l'entrée à l'exécution.
- @prefix dans une boucle, dans une fonction, dans une classe, dans un bloc
  try/except, imbrication à 3 niveaux, blocs frères : shadowing correct, warning
  hors de portée après la fin du bloc.
- Non-fermeture de bloc par lignes blanches, continuations entre crochets,
  g{...} multiligne.
- Redéclaration au même niveau : la 2ᵉ IRI s'applique aux usages situés après elle
  (warning si elle change l'IRI d'un préfixe déjà utilisé).
- Deux modules important des tables différentes → pas de fuite.
- Décorateur nommé `prefix` → non transformé.
- @base relative à la @base précédente (résolution RFC 3986 à la transpilation),
  y compris à travers une sortie de bloc (restauration).

Couvert par `tests/test_prefix_scoping.py` (22 cas).

⚠ Répercussion à faire sur l'article (`article/tex/main.tex`, §4.6 « Prefix and
base scoping ») : le texte décrit encore la portée fichier.
