"""Language server Linked-Data Python (fiche DESIGN_CHOICES/lsp/101).

Jalon 1 (implémenté) : diagnostics natifs du transpileur (erreurs de syntaxe
ldpy + warnings @prefix), matérialisation continue des .py fantômes.
Jalon 2 (à venir) : request-forwarding vers pylsp/pyright via le language map.

Lancement : python -m ldpy.lsp   (requiert `pip install linked-data-python[lsp]`)
"""
