"""Debugging .ldpy files (docs/explanation/tooling.md).

Principle: NO DAP adapter to write. Two modes:

- **direct** (`--run`, record ldpy/011): the .ldpy is compiled in source
  coordinates (compile_mapped) and run IN this process. Started under
  debugpy (by the VS Code extension: `python -m debugpy … -m ldpy.debug
  --run f.ldpy`), breakpoints set in the .ldpy bind directly — no shadow,
  no translation;
- **shadow**: `ldpy.build` materialises a real Python file and its maps;
  debugpy (or any Python tool) runs on it as it is
  (`python -m ldpy.debug file.ldpy [--listen H:P] [-- args]`), and
  `--breakpoints` translates .ldpy lines <-> shadow lines for tooling.

The direct mode leaves three frames of THIS module below the user's own.
`stepping_rules()` tells the debugger to ignore them (record vscode/103);
`--probe` publishes them so the VS Code extension need not restate them.
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
# Stepping filters (record vscode/103)
#
# The invariant: every debugger stop selects a region of the .ldpy file.
# Two things break it — the LAUNCHER frames (this module, below the user's)
# and, when nobody asked for them, the RUNTIME ones (stepping into
# `_ldpy_.graph(...)` lands in runtime.py). Both are settled by the protocol's
# `rules`: pydevd reads them from the DAP `launch`/`attach` request (the
# PYDEVD_FILTERS environment variable, on the other hand, is overwritten by
# that request — measured, do not rely on it).
#
# The policy, in two tiers:
#   - the launcher is ALWAYS hidden: it is plumbing, never code anyone
#     wants to look at;
#   - the rest of the package only under `justMyCode` (the default).
#     `justMyCode: false` is the explicit request to see everything: a step
#     in then descends into the runtime, which is the intended behaviour.
# ---------------------------------------------------------------------------

#: Modules that are only the launcher: never visible, whatever the mode.
LAUNCHER_FILES = ("debug.py", "__main__.py")


def package_dir():
    """Directory of the installed ldpy package (the one running this code)."""
    return os.path.dirname(os.path.abspath(__file__))


def stepping_rules(just_my_code=True, package=None):
    """The DAP `rules` that hold the invariant of record vscode/103.

    Shape debugpy expects: a list of {"path": glob, "include": bool}, first
    premier motif qui matche gagnant."""
    pkg = package or package_dir()
    rules = [{"path": os.path.join(pkg, name), "include": False}
             for name in LAUNCHER_FILES]
    if just_my_code:
        rules.append({"path": os.path.join(pkg, "**"), "include": False})
    return rules


def probe():
    """What a debug client needs in order to launch ldpy correctly.

    The VS Code extension calls `python -m ldpy.debug --probe`: a single
    process gives it proof that the package is importable, its version, and
    the stepping rules — which thus stay described in ONE place."""
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


#: re-exported: debug tooling looks for them here (pure functions, defined
#: alongside the map in ldpy/transpiler/linemap.py)
__all__ = ["stepping_rules", "probe", "package_dir", "load_map",
           "translate_breakpoints", "translate_frames",
           "snap_breakpoint_line", "snap_breakpoint_lines",
           "run_direct", "main"]


def load_map(map_path):
    """Load a LanguageMap from a .ldpy.map file (JSON)."""
    with open(map_path, "r", encoding="utf-8") as f:
        return LanguageMap.from_json(f.read())


def translate_breakpoints(lmap, lines_1based):
    """.ldpy breakpoint lines (1-based) -> shadow lines (1-based).

    A line with no counterpart (a comment inside a collapsed island…) snaps
    to the generated line of the region containing it, else None."""
    out = []
    for line in lines_1based:
        pos = lmap.to_gen(line - 1, 0)
        if pos is None:
            # inside a multi-line island: snap to its start
            for seg in lmap.segments:
                if seg.src and seg.src[0] <= line - 1 <= seg.src[2]:
                    pos = (seg.gen[0], seg.gen[1])
                    break
        out.append(pos[0] + 1 if pos else None)
    return out


def translate_frames(lmap, lines_1based):
    """Shadow lines (1-based) -> .ldpy lines (1-based), for stack frames."""
    out = []
    for line in lines_1based:
        src = lmap.src_line_for_gen_line(line - 1)
        out.append(src + 1 if src is not None else None)
    return out


def run_direct(source_path, script_args):
    """Direct mode: compile the .ldpy in source coordinates and run it right
    here. Under debugpy, .ldpy breakpoints bind with no translation."""
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
        description="Run a .ldpy in debuggable mode: --run (direct, source "
                    "coordinates) or through its Python shadow, "
                    "under debugpy when --listen is given.")
    parser.add_argument("source", nargs="?", help="fichier .ldpy")
    parser.add_argument("--run", action="store_true",
                        help="run directly in this process, code compiled "
                             "in .ldpy coordinates (for debugpy: breakpoints "
                             "straight in the .ldpy)")
    parser.add_argument("-o", "--out", default=DEFAULT_OUT,
                        help="shadow directory (default: %(default)s)")
    parser.add_argument("--listen", metavar="HOTE:PORT",
                        help="start debugpy listening (e.g. 127.0.0.1:5678)")
    parser.add_argument("--wait-for-client", action="store_true",
                        help="wait for the debugger to attach before starting")
    parser.add_argument("--probe", action="store_true",
                        help="print {package, version, rules} as JSON and "
                             "exit — for the VS Code extension")
    parser.add_argument("--breakpoints", metavar="L1,L2,...",
                        help=".ldpy lines: print their shadow lines "
                             "(JSON) and exit — for tooling")
    parser.add_argument("args", nargs="*",
                        help="arguments passed to the script (after `--`)")
    # argparse handles "--" poorly before a nargs="*": split it by hand
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
        parser.error("a .ldpy file is required")

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
        # ABSOLUTE paths: this output crosses a process boundary, and a
        # relative path means nothing to a reader that does not share our
        # working directory. An editor turning ".ldpy-build/x.py" into a URI
        # gets "/.ldpy-build/x.py", rooted at the filesystem root.
        print(json.dumps({
            "shadow": os.path.abspath(py_path),
            "map": os.path.abspath(map_path),
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
