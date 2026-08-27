"""Débogage des fichiers .ldpy via debugpy sur les .py fantômes (docs/explanation/tooling.md).

Principe : PAS d'adaptateur DAP à écrire. `ldpy.build` matérialise un vrai
fichier Python + ses maps ; debugpy s'exécute dessus tel quel. Ce module
fournit :

- le lanceur : `python -m ldpy.debug fichier.ldpy [--listen H:P] [-- args]`
  (build du fichier puis exécution du fantôme, sous debugpy si demandé) ;
- la traduction de breakpoints pour l'outillage (extension VS Code) :
  lignes .ldpy <-> lignes du fantôme, via le LanguageMap.
"""

import argparse
import json
import os
import subprocess
import sys

from ldpy.build import build_file, DEFAULT_OUT
from ldpy.transpiler import LdpySyntaxError
from ldpy.transpiler.linemap import LanguageMap


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


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ldpy.debug",
        description="Transpile un .ldpy et exécute son fantôme Python, "
                    "sous debugpy si --listen est fourni.")
    parser.add_argument("source", help="fichier .ldpy")
    parser.add_argument("-o", "--out", default=DEFAULT_OUT,
                        help="répertoire fantôme (défaut : %(default)s)")
    parser.add_argument("--listen", metavar="HOTE:PORT",
                        help="démarre debugpy en écoute (ex. 127.0.0.1:5678)")
    parser.add_argument("--wait-for-client", action="store_true",
                        help="attend l'attachement du débogueur avant de lancer")
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
