"""Formateur (pretty printer) des fichiers .ldpy — fiche ldpy/024.

The principle is the highlighter's (record ldpy/023): **the formatter is the
transpiler**. We transpile to get the language map, which says exactly where
the islands are in the SOURCE; we replace each one with a stand-in that is
valid Python in its place; we hand the result to `black`, which is the Python
formatter; we put the islands back where the stand-ins landed.

Two consequences serve as the contract, and are tested:

- **host transparency** — a file with no island is formatted *exactly* as
  `black` would format it. The formatter has no opinion about Python;
- **the meaning does not move** — the AST of the transpiled Python is the
  same before and after formatting. A formatter that changes what the
  un formateur.

What the formatter does TO THE ISLANDS is deliberately modest (the body is
copied verbatim, only the edges are normalised): see record ldpy/024, section
"what the formatter does not do".

`black` is an OPTIONAL dependency (extra `[format]`): nothing in ldpy imports
it outside this module, and its absence gives an actionable message.
"""

import argparse
import os
import re
import sys

from ldpy.transpiler import transpile

DEFAULT_LINE_LENGTH = 88


class FormatterUnavailable(RuntimeError):
    """`black` is not installed in this interpreter."""


def _black():
    """The Python engine, loaded on demand.

    The single coupling point: changing it (for ruff format, say) touches
    this function and `_format_python`, nothing else."""
    try:
        import black
    except ImportError as e:                                # pragma: no cover
        raise FormatterUnavailable(
            "the ldpy formatter delegates Python to black, which is not "
            "installed — `pip install linked-data-python[format]`") from e
    return black


def _format_python(text, line_length):
    black = _black()
    return black.format_str(text, mode=black.Mode(line_length=line_length))


# ---------------------------------------------------------------------------
# Offsets: the map speaks in (line, column), text speaks in offsets
# ---------------------------------------------------------------------------

def _line_starts(text):
    starts = [0]
    for i, c in enumerate(text):
        if c == "\n":
            starts.append(i + 1)
    return starts


def _offset(starts, line, col):
    return starts[line] + col


# ---------------------------------------------------------------------------
# Masking: a stand-in that is valid Python in place of each island
# ---------------------------------------------------------------------------

#: Islands sit in an expression or a statement position, except in two cases
#: where the stand-in must carry the syntactic shape of the original so that
#: `black` treats it the same (an import earns its blank line, a bare name
def _substitute(kind, name):
    if kind == "for-bindings":
        # `for @bindings [as b] in` -> the matching loop header
        return "for %s in" % name
    if kind == "import":
        # `from m import a, ex:, unit: as u:` -> une VRAIE instruction
        # so that black handles the blank lines of the import block
        return "import %s" % name
    return name


def _padded(name, text, line_length):
    """Pad `name` so that the stand-in WEIGHS what the island weighs.

    This is the masking doctrine of record ldpy/023: a stand-in of the same
    length lets the delegated engine decide as it would have decided on the
    real text. Here what is at stake is line breaking — a short stand-in
    would make black believe everything fits on one line, and the island put
    back would overflow.

    A MULTI-LINE island cannot, by construction, fit on one line: we give it
    a weight beyond the limit, which keeps the break the author wrote.
    """
    width = max(len(l) for l in text.split("\n"))
    if "\n" in text:
        width = max(width, line_length + 1)
    return name + "_" * max(0, width - len(name))


#: An island whose text is already valid Python and has nothing to mask: the
#: ":" closing a `for @bindings in ... :`.
_TRANSPARENT = ("for-bindings-close",)


class _Island:
    __slots__ = ("kind", "text", "column", "name", "substitute")

    def __init__(self, kind, text, column, name, line_length):
        self.kind = kind
        self.text = text
        self.column = column          # start column in the SOURCE
        self.name = name
        self.substitute = _substitute(kind, _padded(name, text, line_length))


def _fresh_names(source, count):
    """`count` identifiants uniques absents du source.

    We prefix with `_L` and lengthen as long as a name appears in the text:
    masking has to be reversible, so stand-ins must never collide with a name
    of the user's."""
    prefix = "_L"
    while any(("%s%d" % (prefix, i)) in source for i in range(count)):
        prefix += "_"
    return ["%s%d" % (prefix, i) for i in range(count)]


def _mask(source, lmap, line_length=DEFAULT_LINE_LENGTH):
    """Returns (masked text, island list) — the masked text is Python."""
    starts = _line_starts(source)
    segments = [s for s in lmap.segments
                if s.kind.startswith("island:") and s.src is not None
                and s.kind[len("island:"):] not in _TRANSPARENT]
    names = _fresh_names(source, len(segments))
    out = []
    islands = []
    cursor = 0
    for seg, name in zip(segments, names):
        kind = seg.kind[len("island:"):]
        a = _offset(starts, seg.src[0], seg.src[1])
        b = _offset(starts, seg.src[2], seg.src[3])
        if a < cursor:                       # nested island: already covered
            continue
        island = _Island(kind, source[a:b], seg.src[1], name, line_length)
        out.append(source[cursor:a])
        out.append(island.substitute)
        islands.append(island)
        cursor = b
    out.append(source[cursor:])
    return "".join(out), islands


# ---------------------------------------------------------------------------
# Island normalisation: the EDGES only (record ldpy/024)
# ---------------------------------------------------------------------------

_OPENER = re.compile(r"^[a-zA-Z+\-]?\{")
#: `@prefix ex: <...> .` / `@base <...> .` — grammaire close, sans espace
#: possible inside the terms, so it normalises without risk.
_DECL = re.compile(r"^@(prefix|base)\s+((?:\S+:)\s+)?(<[^>\s]*>)\s*\.$")


def _normalize_island(text):
    """Normalise an island's edges, without touching its body.

    What is taken in hand: trailing whitespace, the padding right after `{`
    and right before `}`, and the declarations whose grammar is closed
    (`@prefix`, `@base`, `@graph`, `@bindings`, prefix imports). The body of a
    graph or a query is copied CHARACTER FOR CHARACTER: see record ldpy/024.
    """
    text = "\n".join(l.rstrip() for l in text.split("\n"))

    m = _DECL.match(text)
    if m:
        pieces = ["@" + m.group(1)]
        if m.group(2):
            pieces.append(m.group(2).strip())
        pieces += [m.group(3), "."]
        return " ".join(pieces)

    if text.startswith(("@graph", "@bindings", "from ")) \
            and not re.search(r"[{}'\"]", text):
        # no interpolation and no literal: the blanks there are only padding,
        # and the comma of an import list normalises
        text = re.sub(r"\s+", " ", text).strip()
        return re.sub(r"\s*,\s*", ", ", text)

    m = _OPENER.match(text)
    if m and text.endswith("}") and len(text) > len(m.group(0)):
        open_, body = m.group(0), text[len(m.group(0)):-1]
        if not body.strip():
            return open_ + " }"
        first, *rest = body.split("\n")
        if rest:
            rest[-1] = rest[-1].rstrip()
            body = "\n".join([" " + first.strip() if first.strip() else first]
                             + rest)
            return open_ + body + (" }" if rest[-1] else "}")
        return open_ + " " + body.strip() + " }"
    return text


def _reindent(text, from_column, to_column):
    """Shift the continuation lines of a multi-line island.

    The shift preserves the alignment the author wanted; we never let it
    jamais passer sous la colonne 0."""
    if "\n" not in text or from_column == to_column:
        return text
    delta = to_column - from_column
    first, *rest = text.split("\n")
    if delta > 0:
        rest = [(" " * delta + l) if l.strip() else l for l in rest]
    else:
        keep = min([len(l) - len(l.lstrip()) for l in rest if l.strip()],
                   default=0)
        cut = min(-delta, keep)
        rest = [l[cut:] if l.strip() else l for l in rest]
    return "\n".join([first] + rest)


def _unmask(formatted, islands):
    """Put each island back in place of its stand-in."""
    for island in islands:
        idx = formatted.find(island.substitute)
        if idx < 0:                                        # pragma: no cover
            raise RuntimeError(
                "stand-in %r not found after formatting — please report this "
                "file as a formatter defect" % island.substitute)
        column = idx - formatted.rfind("\n", 0, idx) - 1
        text = _reindent(_normalize_island(island.text),
                         island.column, column)
        formatted = (formatted[:idx] + text
                     + formatted[idx + len(island.substitute):])
    return formatted


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def format_source(source, filename="<ldpy>",
                  line_length=DEFAULT_LINE_LENGTH):
    """Format a .ldpy source and return the formatted text.

    Raises `LdpySyntaxError` if the source does not transpile (we do not
    format what we do not understand) and `FormatterUnavailable` if black is missing."""
    result = transpile(source, filename)
    masked, islands = _mask(source, result.map, line_length)
    return _unmask(_format_python(masked, line_length), islands)


def format_file(path, line_length=DEFAULT_LINE_LENGTH, write=False):
    """Format one file; returns (formatted text, changed)."""
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    formatted = format_source(source, path, line_length)
    changed = formatted != source
    if write and changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(formatted)
    return formatted, changed


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ldpy-format",
        description="Format .ldpy files: black for the Python, edges "
                    "normalised for the islands (record ldpy/024).")
    parser.add_argument("paths", nargs="+",
                        help=".ldpy files or directories to walk")
    parser.add_argument("-l", "--line-length", type=int,
                        default=DEFAULT_LINE_LENGTH,
                        help="line length (default: %(default)s)")
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 if a file is not "
                             "formatted")
    parser.add_argument("--diff", action="store_true",
                        help="print the diff instead of writing")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    files = []
    for p in args.paths:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                files += [os.path.join(root, n) for n in sorted(names)
                          if n.endswith(".ldpy")]
        else:
            files.append(p)

    from ldpy.transpiler import LdpySyntaxError
    changed_any = False
    status = 0
    for path in files:
        try:
            formatted, changed = format_file(
                path, args.line_length,
                write=not (args.check or args.diff))
        except (LdpySyntaxError, FormatterUnavailable) as e:
            print("%s : %s" % (path, e), file=sys.stderr)
            status = 2
            continue
        changed_any = changed_any or changed
        if args.diff and changed:
            import difflib
            with open(path, encoding="utf-8") as f:
                before = f.read()
            sys.stdout.writelines(difflib.unified_diff(
                before.splitlines(True), formatted.splitlines(True),
                path, path + " (formatted)"))
        elif changed:
            print("reformatted %s" % path)
    if args.check and changed_any:
        return 1
    return status


if __name__ == "__main__":                                 # pragma: no cover
    sys.exit(main())
