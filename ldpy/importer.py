"""Import hook for .ldpy modules (standard importlib, no `ideas` package).

Usage :
    import ldpy ; ldpy.install()
    import monmodule        # trouve monmodule.ldpy sur sys.path

The .ldpy modules are compiled in SOURCE coordinates (compile_mapped,
fiche ldpy/011) : tracebacks, pdb et debugpy pointent
straight at the .ldpy lines. The LanguageMap of each imported module is
kept in MAPS (key: path of the .ldpy file) for tooling."""

import sys
import os
import importlib.abc
import importlib.machinery
import importlib.util

from ldpy.transpiler import transpile

MAPS = {}   # chemin .ldpy -> LanguageMap
CODES = {}  # .ldpy path -> generated Python source


class LdpyLoader(importlib.abc.SourceLoader):
    """Loader for .ldpy modules: transpile, then compile the source."""

    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def get_filename(self, fullname):
        """Path of the .ldpy file (importlib API)."""
        return self.path

    def get_data(self, path):
        """Raw bytes of the source file (importlib API)."""
        with open(path, "rb") as f:
            return f.read()

    def source_to_code(self, data, path, *, _optimize=-1):
        """Transpile the ldpy source, then compile it in SOURCE
        coordinates (compile_mapped, record ldpy/011): tracebacks, pdb and
        debugpy point straight at the .ldpy lines. The LanguageMap is kept
        for tooling."""
        source = data.decode("utf-8") if isinstance(data, bytes) else data
        result = transpile(source, path)
        for w in result.warnings:
            print(str(w), file=sys.stderr)
        MAPS[path] = result.map
        CODES[path] = result.code
        from ldpy.transpiler.linemap import compile_mapped
        return compile_mapped(result.code, result.map, path,
                              dont_inherit=True, optimize=_optimize)


class LdpyFinder(importlib.abc.MetaPathFinder):
    """sys.meta_path finder: resolves `import mod` to `mod.ldpy`."""

    def find_spec(self, fullname, path=None, target=None):
        """Look for <name>.ldpy on sys.path (or on the package path)."""
        name = fullname.rpartition(".")[2]
        for entry in (path if path is not None else sys.path):
            if not isinstance(entry, str):
                continue
            base = entry or "."
            candidate = os.path.join(base, name + ".ldpy")
            if os.path.isfile(candidate):
                loader = LdpyLoader(fullname, candidate)
                return importlib.util.spec_from_file_location(
                    fullname, candidate, loader=loader)
        return None


_finder = None


def install():
    """Installe le finder .ldpy (idempotent)."""
    global _finder
    if _finder is None:
        _finder = LdpyFinder()
        sys.meta_path.append(_finder)
    return _finder


def uninstall():
    """Remove the .ldpy finder from sys.meta_path."""
    global _finder
    if _finder is not None:
        try:
            sys.meta_path.remove(_finder)
        except ValueError:
            pass
        _finder = None


def translate_lineno(path, gen_line_1based):
    """Generated line (1-based) -> .ldpy source line (1-based), or None."""
    lmap = MAPS.get(path)
    if lmap is None:
        return None
    src = lmap.src_line_for_gen_line(gen_line_1based - 1)
    return None if src is None else src + 1


def install_excepthook():
    """OBSOLETE (kept for compatibility): since the remapped compilation
    (record ldpy/011), code objects already carry the .ldpy line numbers —
    tracebacks are right without rewriting. Does nothing."""
    return sys.excepthook
