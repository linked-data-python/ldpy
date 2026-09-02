"""Console interactive Linked-Data Python .

The point of the `ideas` package in v1 was to enter the interpreter and type
ldpy directly. This console does it without `ideas`: every entry is
transpiled then compiled; the state of top-level @prefix/@base persists from
one entry to the next (declarations made inside a block die with the entry —
block scope obliges).

    $ python -m ldpy                      # console
    $ python -m ldpy -i script.ldpy       # run, then open the console
"""

import atexit
import code
import codeop
import os
import sys

import ldpy
from ldpy.transpiler import LdpySyntaxError
from ldpy.transpiler.core import Transpiler, PRELUDE

HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".ldpy_history")
HISTORY_LENGTH = 1000


def _setup_readline(locals):
    """Line editing (arrows, Ctrl-A/E…), persistent history and Tab
    completion on console names. A no-op if the readline module is missing
    (Windows without pyreadline)."""
    try:
        import readline
        import rlcompleter
    except ImportError:
        return
    readline.set_completer(rlcompleter.Completer(locals).complete)
    if "libedit" in (getattr(readline, "__doc__", "") or ""):
        readline.parse_and_bind("bind ^I rl_complete")   # macOS libedit
    else:
        readline.parse_and_bind("tab: complete")
    try:
        readline.read_history_file(HISTORY_FILE)
    except OSError:
        pass
    readline.set_history_length(HISTORY_LENGTH)

    def _save():
        try:
            readline.write_history_file(HISTORY_FILE)
        except OSError:
            pass
    atexit.register(_save)

BANNER = ("ldpy %s — console Linked-Data Python (Python %s)\n"
          "RDF islands are accepted: @prefix, <iri>, ex:name, g{ ... }, ?v")


class LdpyConsole(code.InteractiveConsole):
    """Interactive console: transpile every entry before compiling it;
    top-level @prefix/@base persist between entries."""

    def __init__(self, locals=None, filename="<console>",
                 prefixes=None, base=None):
        if locals is None:
            locals = {"__name__": "__console__", "__doc__": None}
        super().__init__(locals=locals, filename=filename)
        # the runtime prelude is installed once and for all
        if "__namespaces__" not in self.locals:
            exec(PRELUDE, self.locals)
        self._prefixes = dict(prefixes or {})
        self._prefix_cols = {k: 0 for k in self._prefixes}
        self._base = base
        # The current graph and the current bindings are declarations too:
        # like @prefix, a top-level @graph must survive to the next entry
        # (otherwise `+{ ... }` after `@graph as g` sees no graph at all).
        self._graph_var = None
        self._bindings_var = None
        self._counter = 0

    def runsource(self, source, filename=None, symbol="single"):
        """Transpile then compile one entry; True = incomplete entry
        (unclosed island or Python block), False = handled."""
        filename = filename or self.filename
        t = Transpiler(source, filename, emit_prelude=False)
        t.prefixes = dict(self._prefixes)
        t._prefix_col = dict(self._prefix_cols)
        t.base = self._base
        t._graph_var = self._graph_var
        t._bindings_var = self._bindings_var
        # fresh names must not collide with those of the previous entries
        t._ns_counter = self._counter
        try:
            result = t.run()
        except LdpySyntaxError as e:
            if getattr(e, "at_eof", False):
                return True          # unclosed island: wait for more
            self.write(str(e) + "\n")
            return False
        try:
            code_obj = codeop.compile_command(result.code, filename, symbol)
        except (SyntaxError, ValueError, OverflowError):
            self.showsyntaxerror(filename)
            return False
        if code_obj is None:
            return True              # Python incomplet (def, if, ...)
        # the entry is complete: top-level declarations persist
        t._unwind_scopes(0)
        self._prefixes = dict(t.prefixes)
        self._prefix_cols = dict(t._prefix_col)
        self._base = t.base
        self._graph_var = t._graph_var
        self._bindings_var = t._bindings_var
        self._counter = t._ns_counter
        for w in result.warnings:
            self.write(str(w) + "\n")
        self.runcode(code_obj)
        return False


def interact(locals=None, prefixes=None, base=None):
    """Open the ldpy console (banner, Ctrl-D to leave)."""
    console = LdpyConsole(locals=locals, prefixes=prefixes, base=base)
    _setup_readline(console.locals)
    banner = BANNER % (ldpy.__version__, sys.version.split()[0])
    try:
        console.interact(banner=banner, exitmsg="")
    except SystemExit:
        pass
    return console
