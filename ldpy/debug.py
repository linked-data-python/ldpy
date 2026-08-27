"""Débogage des fichiers .ldpy (docs/explanation/tooling.md).

Principe : PAS d'adaptateur DAP à écrire. Deux modes :

- **direct** (`--run`, fiche DESIGN_CHOICES/ldpy/011) : le .ldpy est compilé
  en coordonnées source (compile_mapped) et exécuté DANS ce processus. Lancé
  sous debugpy (par l'extension VS Code : `python -m debugpy ... -m
  ldpy.debug --run f.ldpy`), les breakpoints posés dans le .ldpy se lient
  directement — pas de fantôme, pas de traduction ;
- **fantôme** : `ldpy.build` matérialise un vrai fichier Python + ses maps ;
  debugpy (ou tout outil Python) s'exécute dessus tel quel
  (`python -m ldpy.debug fichier.ldpy [--listen H:P] [-- args]`), et
  `--breakpoints` traduit lignes .ldpy <-> lignes fantôme pour l'outillage.
"""

import argparse
import json
import os
import subprocess
import sys

from ldpy.build import build_file, DEFAULT_OUT
from ldpy.transpiler import LdpySyntaxError, transpile
from ldpy.transpiler.linemap import LanguageMap, compile_mapped


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
    parser.add_argument("source", help="fichier .ldpy")
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
