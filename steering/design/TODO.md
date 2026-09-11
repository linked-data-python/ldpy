bugs identifiés:

* F5 ouvre launch.json, systématiquement.
  → **traité le 2026-09-02**, fiche vscode/109 (dépôt de pilotage, resté privé).
  Le fournisseur de configuration rendait `null` pour annuler la session
  `ldpy` après avoir démarré la session debugpy équivalente ; l'API réserve
  `null` à « annuler ET ouvrir launch.json ». C'est `undefined` qu'il faut
  rendre. Test de non-régression dans `vscode-ldpy/test/journeys.js`.

* où est-ce que le py est materialisé ? permettre la configuration qu'il soit
  materialisé dans le workspace ?
  → **traité le 2026-09-02**, même fiche. Réponse : le débogage ne matérialise
  RIEN (fiche 011) ; seuls « Show Transpiled Python » et `ldpy.build` écrivent.
  `ldpy.buildDirectory` relatif pend désormais du dossier d'espace de travail
  et non du fichier — donc `.ldpy-build/` à la racine du projet — avec
  l'arborescence reflétée (`ldpy.debug --root`) pour que `a/m.ldpy` et
  `b/m.ldpy` ne se disputent pas `m.py`. Un chemin absolu reste tel quel.

* vérifier que les snippets de la doc peuvent aussi être exécutés dans la
  console interactive. actuellement le @graph ne fonctionne pas.
  → **traité le 2026-09-02**, fiche [ldpy/025](025-console-etat-des-declarations.md).
  `@graph as g` FIGEAIT la console (`"" in " \t"` est vrai en Python : boucle
  de saut de blancs infinie en fin de tampon), et le graphe courant ne
  survivait pas à l'entrée qui le déclarait. Trois autres défauts levés au
  passage. `tests/test_docs.py` rejoue maintenant tous les blocs ldpy de la
  documentation dans la console, en plus de les exécuter comme fichiers.
