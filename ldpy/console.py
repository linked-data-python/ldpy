"""Console interactive Linked-Data Python .

L'intérêt du paquet `ideas` en v1 était d'entrer dans l'interpréteur et d'y écrire directement du ldpy.
Cette console le permet sans `ideas` : chaque entrée est transpilée puis
compilée ; l'état des @prefix/@base de niveau zéro persiste d'une entrée à
l'autre (les déclarations faites dans un bloc meurent avec l'entrée, portée
par bloc oblige, portée par bloc).

    $ python -m ldpy                      # console
    $ python -m ldpy -i script.ldpy       # exécute puis ouvre la console
"""

import code
import codeop
import sys

import ldpy
from ldpy.transpiler import LdpySyntaxError
from ldpy.transpiler.core import Transpiler, PRELUDE

BANNER = ("ldpy %s — console Linked-Data Python (Python %s)\n"
          "Les îlots RDF sont acceptés : @prefix, <iri>, ex:nom, g{ ... }, ?v")


class LdpyConsole(code.InteractiveConsole):
    """Console interactive : transpile chaque entrée avant compilation ;
    les @prefix/@base de niveau zéro persistent entre les entrées."""

    def __init__(self, locals=None, filename="<console>",
                 prefixes=None, base=None):
        if locals is None:
            locals = {"__name__": "__console__", "__doc__": None}
        super().__init__(locals=locals, filename=filename)
        # le prélude du runtime est installé une fois pour toutes
        if "__namespaces__" not in self.locals:
            exec(PRELUDE, self.locals)
        self._prefixes = dict(prefixes or {})
        self._prefix_cols = {k: 0 for k in self._prefixes}
        self._base = base

    def runsource(self, source, filename=None, symbol="single"):
        """Transpile puis compile une entrée ; True = entrée incomplète
        (îlot ou bloc Python non terminé), False = traitée."""
        filename = filename or self.filename
        t = Transpiler(source, filename, emit_prelude=False)
        t.prefixes = dict(self._prefixes)
        t._prefix_col = dict(self._prefix_cols)
        t.base = self._base
        try:
            result = t.run()
        except LdpySyntaxError as e:
            if getattr(e, "at_eof", False):
                return True          # îlot non fermé : attendre la suite
            self.write(str(e) + "\n")
            return False
        try:
            code_obj = codeop.compile_command(result.code, filename, symbol)
        except (SyntaxError, ValueError, OverflowError):
            self.showsyntaxerror(filename)
            return False
        if code_obj is None:
            return True              # Python incomplet (def, if, ...)
        # l'entrée est complète : les déclarations de niveau zéro persistent
        t._unwind_scopes(0)
        self._prefixes = dict(t.prefixes)
        self._prefix_cols = dict(t._prefix_col)
        self._base = t.base
        for w in result.warnings:
            self.write(str(w) + "\n")
        self.runcode(code_obj)
        return False


def interact(locals=None, prefixes=None, base=None):
    """Ouvre la console ldpy (bannière, Ctrl-D pour sortir)."""
    console = LdpyConsole(locals=locals, prefixes=prefixes, base=base)
    banner = BANNER % (ldpy.__version__, sys.version.split()[0])
    try:
        console.interact(banner=banner, exitmsg="")
    except SystemExit:
        pass
    return console
