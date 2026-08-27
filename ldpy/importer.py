"""Import hook v2 pour les modules .ldpy (importlib standard, sans `ideas`).

Usage :
    import ldpy ; ldpy.install()
    import monmodule        # trouve monmodule.ldpy sur sys.path

Les LanguageMap des modules importés sont conservées dans MAPS (clé : chemin du
fichier .ldpy) pour la traduction des tracebacks (install_excepthook)."""

import sys
import os
import importlib.abc
import importlib.machinery
import importlib.util

from ldpy.transpiler import transpile

MAPS = {}   # chemin .ldpy -> LanguageMap
CODES = {}  # chemin .ldpy -> source Python généré


class LdpyLoader(importlib.abc.SourceLoader):
    """Chargeur de modules .ldpy : transpile puis compile la source."""

    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def get_filename(self, fullname):
        """Chemin du fichier .ldpy (API importlib)."""
        return self.path

    def get_data(self, path):
        """Octets bruts du fichier source (API importlib)."""
        with open(path, "rb") as f:
            return f.read()

    def source_to_code(self, data, path, *, _optimize=-1):
        """Transpile la source ldpy puis compile le Python obtenu ;
        enregistre la LanguageMap dans MAPS pour les tracebacks."""
        source = data.decode("utf-8") if isinstance(data, bytes) else data
        result = transpile(source, path)
        for w in result.warnings:
            print(str(w), file=sys.stderr)
        MAPS[path] = result.map
        CODES[path] = result.code
        return compile(result.code, path, "exec",
                       dont_inherit=True, optimize=_optimize)


class LdpyFinder(importlib.abc.MetaPathFinder):
    """Finder sys.meta_path : résout `import mod` vers `mod.ldpy`."""

    def find_spec(self, fullname, path=None, target=None):
        """Cherche <nom>.ldpy sur sys.path (ou le path du paquet)."""
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
    """Retire le finder .ldpy de sys.meta_path."""
    global _finder
    if _finder is not None:
        try:
            sys.meta_path.remove(_finder)
        except ValueError:
            pass
        _finder = None


def translate_lineno(path, gen_line_1based):
    """Ligne générée (1-based) -> ligne source .ldpy (1-based), ou None."""
    lmap = MAPS.get(path)
    if lmap is None:
        return None
    src = lmap.src_line_for_gen_line(gen_line_1based - 1)
    return None if src is None else src + 1


def install_excepthook():
    """Traduit les numéros de ligne des frames .ldpy dans les tracebacks."""
    prev = sys.excepthook

    def hook(etype, value, tb):
        import traceback
        entries = traceback.extract_tb(tb)
        rewritten = []
        for fr in entries:
            src_line = translate_lineno(fr.filename, fr.lineno or 0)
            if src_line is not None:
                fr = traceback.FrameSummary(fr.filename, src_line, fr.name)
            rewritten.append(fr)
        print("Traceback (most recent call last):", file=sys.stderr)
        for line in traceback.format_list(rewritten):
            sys.stderr.write(line)
        for line in traceback.format_exception_only(etype, value):
            sys.stderr.write(line)

    sys.excepthook = hook
    return prev
