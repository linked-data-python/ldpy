#
# The MIT License (MIT)
#
# Copyright (c) 2022 by Maxime Lefrançois
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# Project      : ldpython-parser; Linked-Data Python to Python/Micropython Rewriter
#                https://gitlab.com/coswot/linked-data-python/ldpy
# Developed by : Maxime Lefrançois, maxime.lefrancois@emse.fr
#
"""ldpy extends the Python syntax with primitives from the Semantic Web such as namespaces, RDF terms, and RDF graphs.

If no source is given, ldpy will start an interactive console.
"""
import os
import sys
import platform
import argparse
import ldpy
from importlib import import_module
import types
from code import InteractiveConsole
import readline

# include a subset of the arguments from https://github.com/aroberge/ideas/blob/master/ideas/__main__.py
parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=__doc__,
)

parser.add_argument(
    "-v",
    "--version",
    help="only displays the current version.",
    action="store_true",
)

parser.add_argument(
    "-l",
    '--debug-lexer',
    dest='lexer',
    action='store_true',
    default=False,
    help='print the lexer output'
)

parser.add_argument(
    '-p',
    '--debug-parser',
    dest='parser',
    action='store_true',
    default=False,
    help='print the parser output'
)

parser.add_argument(
    "-s",
    "--show_changes",
    action="store_true",
    help="""shows the transformed code before it is executed.""",
)

parser.add_argument(
    "-i", 
    action="store_true",
    help="""starts the interactive console after executing a source"""
)

group = parser.add_mutually_exclusive_group(required=False)

group.add_argument(
    "-m",
    "--module",
    dest="module",
    type=str,
    help="""Run library module as a script. The module may be a .ldpy or a .py file.""",
)  

group.add_argument(
    "source",
    nargs="?",
    help="""Program read from script file. The file extension may be .ldpy or .py.""",
)

class LdpyConsole(InteractiveConsole):
    
    def __init__(self, show_changes=False, locals=None):
        sys.ps1 = "ldpy> "
        sys.ps2 ="  ... "
        if locals is None:
            locals={"__name__": "__console__", 
                    "__doc__": None, 
                    "__base__": None, 
                    "__namespaces__": dict()}
        locals["__debug_ldpy__"] = show_changes
        InteractiveConsole.__init__(self, locals, filename="<ldpy console>")
        self.resetldpybuffer()
        self.push("import rdflib")

    def resetldpybuffer(self):
        self.ldpybuffer = []

    def push(self, line):
        """Push a ldpy line to the interpreter.

        The line should not have a trailing newline; it may have
        internal newlines.  The line is appended to a buffer and the
        interpreter's runsource() method is called with the
        concatenated contents of the buffer as source.  If this
        indicates that the command was executed or invalid, the buffer
        is reset; otherwise, the command is incomplete, and the buffer
        is left as it was after the line was appended.  The return
        value is 1 if more input is required, 0 if the line was dealt
        with in some way (this is the same as runsource()).

        """
        self.ldpybuffer.append(line)
        ldpysource = "\n".join(self.ldpybuffer)
        
        try:
            namespaces = self.locals.get("__namespaces__", dict())
            transformed_source, namespaces, linemap = ldpy.transform_source(ldpysource, self.filename, namespaces)
            self.locals["__namespaces__"] = namespaces
        except SyntaxError as ex:
            if "mismatched input '<EOF>' expecting" in ex.msg:
                return True
            self.write(ex.msg + "\n")
            self.resetldpybuffer()
            return False
        self.resetldpybuffer()

        if self.locals["__debug_ldpy__"]:
            print("", file=sys.stderr)
            for transformed_line in transformed_source.split("\n"):
                print("ldpy>>> " + transformed_line, file=sys.stderr)

        for line in transformed_source.split("\n"):
            self.buffer.append(line)
            source = "\n".join(self.buffer)
            more = self.runsource(source, self.filename)
            if not more:
                self.resetbuffer()
        return more
    
    def interact(self):
        from rdflib import __version__ as rdflib_version
        BANNER = (
            f">>> ldpy interactive console version {ldpy.__version__}. "
            + f"[rdflib version {rdflib_version}, "
            + f"Python version: {platform.python_version()}]"
        )
        InteractiveConsole.interact(self, banner=BANNER)

def rewrite_traceback(tb, linemap):
    if not tb:
        return None
    tb_frame = tb.tb_frame
    if "__name__" in tb_frame.f_globals:
        name = tb_frame.f_globals["__name__"]
        if name == 'importlib' or name == 'importlib._bootstrap' or name == 'ideas.import_hook':
            return rewrite_traceback(tb.tb_next, linemap)
    tb_lineno = tb.tb_lineno
    tb_lasti = tb.tb_lasti
    if "__file__" in tb_frame.f_locals and tb_frame.f_locals["__file__"].endswith(".ldpy"):
        file = tb_frame.f_locals["__file__"]
        if file in linemap:
            linemap_for_file = linemap[file]
            tb_lineno = linemap_for_file[tb_lineno-4] # -4 because hook source_init contains three lines, and index starts at 0
        ## it would be nice to have a second tb with the transformed .py source, but it's not possible to instantiate the builtin Frame type
        # one could update the __file__ local attribute as follows
        # tb_frame.f_locals["__file__"] = tb_frame.f_locals["__file__"][:-5] + ".py"
        # and add the the traceback without changing the lineno
    return types.TracebackType(rewrite_traceback(tb.tb_next, linemap), tb_frame, tb_lasti, tb_lineno)

def main() -> None:
    args = parser.parse_args()
    if args.version:
        print(f"\nldpy version {ldpy.__version__}")
        return
    if args.source is None and args.module is None:
        """Starts a special console that works with ldpy."""
        c = LdpyConsole(show_changes=args.show_changes)
        c.interact()

    ldpy.config.debug_ldpy = args.show_changes
    ldpy.config.debug_lexer = args.lexer
    ldpy.config.debug_parser = args.parser

    if args.source is not None:
        filename = args.source
        if not (filename.endswith(".py") or filename.endswith(".ldpy")):
            raise ValueError("ldpy file argument must end with .py or .ldpy")
        with open(args.source) as f:
            source = f.read()
        if filename.endswith(".ldpy"):
            source, namespaces, linemap = ldpy.transform_source(source, filename)
            source = "import rdflib\n__base__ = None\n__namespaces__ = dict()\n" + source
            directory = os.path.dirname(filename)
            ldpyname = os.path.basename(filename)
            pyname = os.path.splitext(ldpyname)[0] + ".py" 
            os.makedirs(os.path.join(directory, "__ldpycache__"), exist_ok=True)
            with open(os.path.join(directory, "__ldpycache__", pyname), 'w') as f:
                f.write(source)
            ldpy.config.linemap[filename] = linemap
        try:
            code = compile(source, filename, "exec")
            _locals = dict(__file__=filename)
            exec(code, _locals)
        except Exception as exc:
            linemap = ldpy.config.linemap
            tb = exc.__traceback__
            tb = rewrite_traceback(tb, linemap)
            raise exc.with_traceback(tb)            
        
        
    if args.module is not None:
        name = args.module
        if "/" in name or name.endswith(".py") or name.endswith(".ldpy"):
            raise ValueError(f"ldpy argument --module must be a valid module name (path.to.my_script). got '{args.module}'")
        try:
            module = import_module(name)
            _locals = module.__dict__
        except ModuleNotFoundError as exc:
            print(f"{exc.__class__.__name__}: {exc.msg}", file=sys.stderr)
            _locals = dict()
        except Exception as exc:
            linemap = ldpy.config.linemap
            tb = exc.__traceback__
            tb = rewrite_traceback(tb, linemap)
            raise exc.with_traceback(tb)
        
    if sys.flags.interactive or args.i:
        """Starts a special console that works with ldpy."""
        c = LdpyConsole(show_changes=args.show_changes, locals=_locals)
        c.interact()

main()
