"""Débogage des fichiers .ldpy (docs/explanation/tooling.md).

Principe : PAS d'adaptateur DAP à écrire. Deux modes :

- **direct** (`--run`, fiche ldpy/011) : le .ldpy est compilé
  en coordonnées source (compile_mapped) et exécuté DANS ce processus. Lancé
  sous debugpy (par l'extension VS Code : `python -m debugpy ... -m
  ldpy.debug --run f.ldpy`), les breakpoints posés dans le .ldpy se lient
  directement — pas de fantôme, pas de traduction ;
- **fantôme** : `ldpy.build` matérialise un vrai fichier Python + ses maps ;
  debugpy (ou tout outil Python) s'exécute dessus tel quel
  (`python -m ldpy.debug fichier.ldpy [--listen H:P] [-- args]`), et
  `--breakpoints` traduit lignes .ldpy <-> lignes fantôme pour l'outillage.

Le mode direct laisse trois trames de CE module sous celle de l'utilisateur.
`stepping_rules()` dit au débogueur de les ignorer (fiche vscode/103) ;
`--probe` les publie pour que l'extension VS Code n'ait pas à les redécrire.
"""

import argparse
import json
import os
import subprocess
import sys

from ldpy.build import build_file, DEFAULT_OUT
from ldpy.transpiler import LdpySyntaxError, transpile
from ldpy.transpiler.linemap import (LanguageMap, compile_mapped,
                                     snap_breakpoint_line,
                                     snap_breakpoint_lines)


# ---------------------------------------------------------------------------
# Filtres de pas (fiche vscode/103)
#
# L'invariant : chaque arrêt du débogueur sélectionne une région du .ldpy.
# Deux choses le violent — les trames du LANCEUR (ce module, sous celle de
# l'utilisateur) et, quand on ne l'a pas demandé, celles du RUNTIME (entrer
# dans `_ldpy_.graph(...)` mène dans runtime.py). Les deux se règlent par les
# `rules` du protocole : pydevd les lit dans la requête DAP `launch`/`attach`
# (la variable d'environnement PYDEVD_FILTERS, elle, est écrasée par cette
# requête — mesuré, ne pas s'en servir).
#
# Politique, en deux étages :
#   - le lanceur est TOUJOURS masqué : c'est de la plomberie, jamais du code
#     que l'on souhaite voir ;
#   - le reste du paquet l'est seulement sous `justMyCode` (le défaut).
#     `justMyCode: false` est la demande explicite de tout voir : le pas
#     entrant descend alors dans le runtime, ce qui est le comportement voulu.
# ---------------------------------------------------------------------------

#: Modules qui ne sont que le lanceur : jamais visibles, quel que soit le mode.
LAUNCHER_FILES = ("debug.py", "__main__.py")


def package_dir():
    """Répertoire du paquet ldpy installé (celui qui exécute ce code)."""
    return os.path.dirname(os.path.abspath(__file__))


def stepping_rules(just_my_code=True, package=None):
    """Règles `rules` du DAP qui garantissent l'invariant de la fiche 103.

    Forme attendue par debugpy : une liste de {"path": glob, "include": bool},
    premier motif qui matche gagnant."""
    pkg = package or package_dir()
    rules = [{"path": os.path.join(pkg, name), "include": False}
             for name in LAUNCHER_FILES]
    if just_my_code:
        rules.append({"path": os.path.join(pkg, "**"), "include": False})
    return rules


def probe():
    """Ce dont un client de débogage a besoin pour lancer ldpy correctement.

    L'extension VS Code appelle `python -m ldpy.debug --probe` : un seul
    processus lui donne la preuve que le paquet est importable, sa version, et
    les règles de pas — qui restent ainsi décrites À UN SEUL endroit."""
    import ldpy
    return {
        "package": package_dir(),
        "version": getattr(ldpy, "__version__", None),
        "python": sys.executable,
        "rules": {
            "justMyCode": stepping_rules(True),
            "all": stepping_rules(False),
        },
    }


#: réexportés : l'outillage de débogage les cherche ici (fonctions pures,
#: définies avec la map dans ldpy/transpiler/linemap.py)
__all__ = ["stepping_rules", "probe", "package_dir", "load_map",
           "translate_breakpoints", "translate_frames",
           "snap_breakpoint_line", "snap_breakpoint_lines",
           "run_direct", "main"]


def load_map(map_path):
    """Charge une LanguageMap depuis un fichier .ldpy.map (JSON)."""
    with open(map_path, "r", encoding="utf-8") as f:
        return LanguageMap.from_json(f.read())


def translate_breakpoints(lmap, lines_1based):
    """Lignes de breakpoints .ldpy (1-based) -> lignes fantôme (1-based).

    Une ligne sans correspondance (commentaire dans un îlot replié...) est
    rabattue sur la ligne générée de la région qui la contient, sinon None."""
    out = []
    for line in lines_1based:
        pos = lmap.to_gen(line - 1, 0)
        if pos is None:
            # au coeur d'un îlot multiligne : rabattre sur son début
            for seg in lmap.segments:
                if seg.src and seg.src[0] <= line - 1 <= seg.src[2]:
                    pos = (seg.gen[0], seg.gen[1])
                    break
        out.append(pos[0] + 1 if pos else None)
    return out


def translate_frames(lmap, lines_1based):
    """Lignes fantôme (1-based) -> lignes .ldpy (1-based), pour les piles."""
    out = []
    for line in lines_1based:
        src = lmap.src_line_for_gen_line(line - 1)
        out.append(src + 1 if src is not None else None)
    return out


def run_direct(source_path, script_args):
    """Mode direct : compile le .ldpy en coordonnées source et l'exécute ici
    même. Sous debugpy, les breakpoints du .ldpy se lient sans traduction."""
    import ldpy
    src_path = os.path.abspath(source_path)
    with open(src_path, "r", encoding="utf-8") as f:
        source = f.read()
    try:
        result = transpile(source, src_path)
    except LdpySyntaxError as e:
        print(str(e), file=sys.stderr)
        return 1
    for w in result.warnings:
        print(str(w), file=sys.stderr)
    ldpy.install()
    from ldpy.importer import MAPS
    MAPS[src_path] = result.map
    code = compile_mapped(result.code, result.map, src_path)
    sys.argv = [src_path] + list(script_args)
    g = {"__name__": "__main__", "__file__": src_path}
    exec(code, g)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ldpy.debug",
        description="Exécute un .ldpy en mode déboguable : --run (direct, "
                    "coordonnées source) ou via son fantôme Python, "
                    "sous debugpy si --listen est fourni.")
    parser.add_argument("source", nargs="?", help="fichier .ldpy")
    parser.add_argument("--run", action="store_true",
                        help="exécution directe dans ce processus, code "
                             "compilé en coordonnées .ldpy (pour debugpy : "
                             "breakpoints directement dans le .ldpy)")
    parser.add_argument("-o", "--out", default=DEFAULT_OUT,
                        help="répertoire fantôme (défaut : %(default)s)")
    parser.add_argument("--listen", metavar="HOTE:PORT",
                        help="démarre debugpy en écoute (ex. 127.0.0.1:5678)")
    parser.add_argument("--wait-for-client", action="store_true",
                        help="attend l'attachement du débogueur avant de lancer")
    parser.add_argument("--probe", action="store_true",
                        help="affiche en JSON {package, version, rules} et "
                             "sort — pour l'extension VS Code")
    parser.add_argument("--breakpoints", metavar="L1,L2,...",
                        help="lignes .ldpy : affiche leurs lignes fantôme "
                             "(JSON) et sort — pour l'outillage")
    parser.add_argument("args", nargs="*",
                        help="arguments passés au script (après « -- »)")
    # argparse gère mal « -- » devant un nargs="*" : découpe manuelle
    if argv is None:
        argv = sys.argv[1:]
    script_args = []
    if "--" in argv:
        cut = argv.index("--")
        script_args = argv[cut + 1:]
        argv = argv[:cut]
    args = parser.parse_args(argv)
    args.args = args.args + script_args

    if args.probe:
        print(json.dumps(probe()))
        return 0
    if not args.source:
        parser.error("un fichier .ldpy est requis")

    if args.run:
        return run_direct(args.source, args.args)

    try:
        py_path, map_path, result = build_file(
            args.source, args.out,
            rel=os.path.basename(args.source))
    except LdpySyntaxError as e:
        print(str(e), file=sys.stderr)
        return 1
    for w in result.warnings:
        print(str(w), file=sys.stderr)

    if args.breakpoints:
        lines = [int(x) for x in args.breakpoints.split(",") if x.strip()]
        print(json.dumps({
            "shadow": py_path,
            "map": map_path,
            "breakpoints": dict(zip(
                lines, translate_breakpoints(result.map, lines)))}))
        return 0

    cmd = [sys.executable]
    if args.listen:
        cmd += ["-m", "debugpy", "--listen", args.listen]
        if args.wait_for_client:
            cmd += ["--wait-for-client"]
    cmd += [py_path] + args.args

    env = dict(os.environ)
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env["PYTHONPATH"] = repo + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    sys.exit(main())
