"""ldpy v2 — exécution en ligne de commande.

Usage :
    python -m ldpy source.ldpy       # transpile et exécute
    python -m ldpy -s source.ldpy    # affiche aussi le code transformé
    python -m ldpy -t source.ldpy    # transpile seulement (stdout)
"""

import sys
import argparse

import ldpy
from ldpy.transpiler import transpile, LdpySyntaxError


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ldpy",
        description="ldpy étend la syntaxe Python avec les primitives du Web "
                    "des données (IRIs, littéraux RDF, graphes).")
    parser.add_argument("-v", "--version", action="store_true",
                        help="affiche la version et sort.")
    parser.add_argument("-s", "--show-changes", action="store_true",
                        help="affiche le code transformé avant exécution.")
    parser.add_argument("-t", "--transpile-only", action="store_true",
                        help="écrit le code transformé sur stdout, sans exécuter.")
    parser.add_argument("-m", "--map", action="store_true",
                        help="écrit aussi le language map (<source>.map).")
    parser.add_argument("source", nargs="?",
                        help="fichier .ldpy (ou .py) à exécuter.")
    args = parser.parse_args(argv)

    if args.version:
        print("ldpy " + ldpy.__version__)
        return 0
    if not args.source:
        parser.print_help()
        return 1

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
        print("ldpy>>> ======== code transformé ========", file=sys.stderr)
        for lineno, line in enumerate(result.code.split("\n"), 1):
            print("ldpy>>> %3d: %s" % (lineno, line), file=sys.stderr)
        print("ldpy>>> =================================", file=sys.stderr)

    ldpy.install()
    from ldpy.importer import MAPS
    MAPS[args.source] = result.map
    code = compile(result.code, args.source, "exec", dont_inherit=True)
    g = {"__name__": "__main__", "__file__": args.source}
    exec(code, g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
