"""ldpy — command-line execution.

Usage :
    python -m ldpy source.ldpy       # transpile and run
    python -m ldpy -s source.ldpy    # also print the transformed code
    python -m ldpy -t source.ldpy    # transpile seulement (stdout)
"""

import argparse
import os
import sys

import ldpy
from ldpy.transpiler import transpile, LdpySyntaxError
from ldpy.transpiler.linemap import compile_mapped


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ldpy",
        description="ldpy extends Python syntax with Semantic Web "
                    "primitives (IRIs, RDF literals, graphs).")
    parser.add_argument("-v", "--version", action="store_true",
                        help="print the version and exit.")
    parser.add_argument("-s", "--show-changes", action="store_true",
                        help="print the transformed code before running it.")
    parser.add_argument("-t", "--transpile-only", action="store_true",
                        help="write the transformed code to stdout, do not run.")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="open the interactive console after the script.")
    parser.add_argument("-m", "--map", action="store_true",
                        help="also write the language map (<source>.map).")
    parser.add_argument("source", nargs="?",
                        help=".ldpy (or .py) file to run.")
    args = parser.parse_args(argv)

    if args.version:
        print("ldpy " + ldpy.__version__)
        return 0
    if not args.source:
        from ldpy.console import interact
        interact()
        return 0

    with open(args.source, "r", encoding="utf-8") as f:
        source = f.read()
    try:
        result = transpile(source, args.source)
    except LdpySyntaxError as e:
        print(str(e), file=sys.stderr)
        return 1
    for w in result.warnings:
        print(str(w), file=sys.stderr)
    if args.map:
        with open(args.source + ".map", "w", encoding="utf-8") as f:
            f.write(result.map.to_json(indent=1))
    if args.transpile_only:
        sys.stdout.write(result.code)
        return 0
    if args.show_changes:
        print("ldpy>>> ======== transformed code ========", file=sys.stderr)
        for lineno, line in enumerate(result.code.split("\n"), 1):
            print("ldpy>>> %3d: %s" % (lineno, line), file=sys.stderr)
        print("ldpy>>> =================================", file=sys.stderr)

    ldpy.install()
    from ldpy.importer import MAPS
    src_path = os.path.abspath(args.source)
    MAPS[args.source] = MAPS[src_path] = result.map
    # remapped compilation: tracebacks, pdb and debugpy all speak in
    # .ldpy coordinates (record ldpy/011)
    code = compile_mapped(result.code, result.map, src_path)
    g = {"__name__": "__main__", "__file__": src_path}
    exec(code, g)
    if args.interactive:
        from ldpy.console import interact
        interact(locals=g, prefixes=result.prefixes, base=result.base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
