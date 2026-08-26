"""Erreurs et avertissements du transpileur Linked-Data Python v2."""


class LdpySyntaxError(SyntaxError):
    """Erreur de syntaxe dans un source .ldpy.

    line et col sont 0-based en interne ; SyntaxError.lineno/offset sont
    renseignés en 1-based comme l'exige Python.
    """

    def __init__(self, message, filename="<ldpy>", line=0, col=0):
        super().__init__(message)
        self.msg = message
        self.filename = filename
        self.lineno = line + 1
        self.offset = col + 1
        self.line = line
        self.col = col

    def __str__(self):
        return "%s (%s, ligne %d:%d)" % (self.msg, self.filename, self.lineno, self.offset)


class LdpyWarning:
    """Avertissement non bloquant émis pendant la transpilation."""

    def __init__(self, message, filename="<ldpy>", line=0, col=0):
        self.message = message
        self.filename = filename
        self.line = line
        self.col = col

    def __str__(self):
        return "LdpyWarning: %s (%s, ligne %d:%d)" % (
            self.message, self.filename, self.line + 1, self.col + 1)

    def __repr__(self):
        return "LdpyWarning(%r)" % (self.message,)
