"""Matérialisation : transpile des fichiers .ldpy vers un répertoire fantôme.

`python -m ldpy.build src/ -o .ldpy-build` écrit, en miroir de l'arborescence :
  - <module>.py        (code généré)
  - <module>.ldpy.map  (language map JSON)

C'est le socle du debugging (debugpy s'exécute sur les .py fantômes) et du
language server (fiches DESIGN_CHOICES lsp/101 et ldpy/005)."""

import os
import sys
import argparse

from ldpy.transpiler import transpile, LdpySyntaxError

DEFAULT_OUT = ".ldpy-build"


def build_file(src_path, out_dir, rel=None):
    """Transpile un fichier ; retourne (py_path, map_path, result)."""
    with open(src_path, "r", encoding="utf-8") as f:
        source = f.read()
    rel = rel or os.path.basename(src_path)
    stem = rel[:-5] if rel.endswith(".ldpy") else rel
    py_path = os.path.join(out_dir, stem + ".py")
    map_path = os.path.join(out_dir, stem + ".ldpy.map")
    result = transpile(source, src_path)
    result.map.generated_name = py_path
    os.makedirs(os.path.dirname(py_path) or ".", exist_ok=True)
    with open(py_path, "w", encoding="utf-8") as f:
        f.write(result.code)
    with open(map_path, "w", encoding="utf-8") as f:
        f.write(result.map.to_json(indent=1))
    # Source Map v3 (fiche 005, révision) : pour l'outillage standard
    with open(py_path + ".map", "w", encoding="utf-8") as f:
        f.write(result.map.to_sourcemap_v3_json())
    return py_path, map_path, result


def build_tree(root, out_dir):
    """Transpile récursivement tous les .ldpy sous root. Les .py purs sont
    copiés tels quels (un paquet mixte doit rester importable)."""
    built, errors = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in (DEFAULT_OUT, "__pycache__", ".git")]
        for name in filenames:
            src = os.path.join(dirpath, name)
            rel = os.path.relpath(src, root)
            if name.endswith(".ldpy"):
                try:
                    built.append(build_file(src, out_dir, rel))
                except LdpySyntaxError as e:
                    errors.append(e)
            elif name.endswith(".py"):
                dst = os.path.join(out_dir, rel)
                os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                with open(src, "rb") as fi, open(dst, "wb") as fo:
                    fo.write(fi.read())
    return built, errors


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ldpy.build",
        description="Transpile des fichiers .ldpy vers un répertoire fantôme "
                    "(.py + .ldpy.map).")
    parser.add_argument("source", help="fichier .ldpy ou répertoire")
    parser.add_argument("-o", "--out", default=DEFAULT_OUT,
                        help="répertoire de sortie (défaut : %(default)s)")
    args = parser.parse_args(argv)

    if os.path.isdir(args.source):
        built, errors = build_tree(args.source, args.out)
        for e in errors:
            print(str(e), file=sys.stderr)
        print("%d fichier(s) transpilé(s) vers %s" % (len(built), args.out))
        return 1 if errors else 0
    try:
        py_path, _, result = build_file(args.source, args.out)
    except LdpySyntaxError as e:
        print(str(e), file=sys.stderr)
        return 1
    for w in result.warnings:
        print(str(w), file=sys.stderr)
    print(py_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
