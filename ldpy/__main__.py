"""ldpy v2 — exécution en ligne de commande.

Usage :
    python -m ldpy source.ldpy       # transpile et exécute
    python -m ldpy -s source.ldpy    # affiche aussi le code transformé
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
        description="ldpy étend la syntaxe Python avec les primitives du Web "
                    "des données (IRIs, littéraux RDF, graphes).")
    parser.add_argument("-v", "--version", action="store_true",
                        help="affiche la version et sort.")
    parser.add_argument("-s", "--show-changes", action="store_true",
                        help="affiche le code transformé avant exécution.")
    parser.add_argument("-t", "--transpile-only", action="store_true",
                        help="écrit le code transformé sur stdout, sans exécuter.")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="ouvre la console interactive après le script.")
    parser.add_argument("-m", "--map", action="store_true",
                        help="écrit aussi le language map (<source>.map).")
    parser.add_argument("source", nargs="?",
                        help="fichier .ldpy (ou .py) à exécuter.")
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
        print("ldpy>>> ======== code transformé ========", file=sys.stderr)
        for lineno, line in enumerate(result.code.split("\n"), 1):
            print("ldpy>>> %3d: %s" % (lineno, line), file=sys.stderr)
        print("ldpy>>> =================================", file=sys.stderr)

    ldpy.install()
    from ldpy.importer import MAPS
    src_path = os.path.abspath(args.source)
    MAPS[args.source] = MAPS[src_path] = result.map
    # compilation remappée : tracebacks, pdb et debugpy parlent en
    # coordonnées .ldpy (fiche DESIGN_CHOICES/ldpy/011)
    code = compile_mapped(result.code, result.map, src_path)
    g = {"__name__": "__main__", "__file__": src_path}
    exec(code, g)
    if args.interactive:
        from ldpy.console import interact
        interact(locals=g, prefixes=result.prefixes, base=result.base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
