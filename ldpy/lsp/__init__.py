"""Language server Linked-Data Python (architecture : docs/explanation/tooling.md).

Jalon 2 (implémenté) : diagnostics natifs du transpileur ET diagnostics
Python du backend re-projetés, hover (îlots en natif, le reste délégué),
semantic tokens des îlots, request-forwarding vers pylsp pour completion,
definition, references et signatureHelp — positions traduites dans les deux
sens par le LanguageMap.

Lancement : python -m ldpy.lsp [--backend pylsp|none]
(le serveur n'a aucune dépendance ; pylsp est optionnel, pour la délégation)
"""
