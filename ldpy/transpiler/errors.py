"""Errors and warnings of the Linked-Data Python transpiler."""


class LdpySyntaxError(SyntaxError):
    """A syntax error in a .ldpy source.

    line and col are 0-based internally; SyntaxError.lineno/offset are filled
    in 1-based, as Python requires.
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
    """A non-blocking warning emitted during transpilation."""

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
