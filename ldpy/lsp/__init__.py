"""Language server Linked-Data Python (architecture : docs/explanation/tooling.md).

Milestone 2 (implemented): native transpiler diagnostics AND the backend's
Python diagnostics re-projected, hover (islands natively, the rest delegated),
semantic tokens for the islands, request forwarding to pylsp for completion,
definition, references and signatureHelp — positions translated both ways
through the LanguageMap.

Lancement : python -m ldpy.lsp [--backend pylsp|none]
(the server has no dependency; pylsp is optional, for delegation)
"""
