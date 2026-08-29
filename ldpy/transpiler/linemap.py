"""Segment-level language map between a .ldpy source and the generated Python.

Voir docs/reference/language-map.md.

Positions 0-based, fins exclusives. Trois sortes de segments :
- "copy"      : text copied verbatim -> exact position translation;
- "island:*"  : rewritten RDF island -> translation at region granularity;
- "synthetic" : generated text with no origin (the runtime import prelude).
"""

import json


class Segment:
    """One source/generated correspondence segment (copy, island:*, synthetic).

    A composite island (`g{ }`, `m{ }`, `+{ }`, `-{ }`) also carries `parts`:
    the terms written inside it, as `(kind, src, gen_text)` (record
    vscode/108). They are deliberately NOT segments of their own — the map is
    a flat, ordered list that breakpoint snapping, the source map and request
    forwarding all walk, and nesting spans inside it would change what those
    three answer. Parts are read by the hover and by nothing else.
    """

    __slots__ = ("kind", "src", "gen", "parts")

    def __init__(self, kind, src, gen, parts=None):
        self.kind = kind
        self.src = src  # (line0, col0, line1, col1), or None for synthetic
        self.gen = gen  # (line0, col0, line1, col1)
        self.parts = parts or []

    def __repr__(self):
        return "Segment(%r, src=%r, gen=%r)" % (self.kind, self.src, self.gen)

    def to_dict(self):
        """Forme JSON du segment."""
        d = {"kind": self.kind, "gen": list(self.gen)}
        if self.src is not None:
            d["src"] = list(self.src)
        if self.parts:
            d["parts"] = [{"kind": k, "src": list(s), "gen": g}
                          for k, s, g in self.parts]
        return d


def _pos_in(range4, line, col):
    l0, c0, l1, c1 = range4
    if line < l0 or line > l1:
        return False
    if line == l0 and col < c0:
        return False
    if line == l1 and col >= c1 and not (l0 == l1 and c0 == c1):
        return False
    return True


def _translate_copy(range_from, range_to, line, col):
    fl0, fc0, _, _ = range_from
    tl0, tc0, _, _ = range_to
    if line == fl0:
        return (tl0, col - fc0 + tc0)
    return (line - fl0 + tl0, col)


class LanguageMap:
    """Bidirectional .ldpy <-> generated Python correspondence
    (an ordered list of Segments; see docs/reference/language-map.md)."""

    def __init__(self, source_name="<ldpy>", generated_name=None):
        self.source_name = source_name
        self.generated_name = generated_name
        self.segments = []  # ordered by increasing gen AND src positions

    def add(self, kind, src, gen, parts=None):
        """Add a segment (segments empty on both sides are ignored)."""
        # ignore segments that are empty on both sides
        if src is not None and src[:2] == src[2:] and gen[:2] == gen[2:]:
            return
        self.segments.append(Segment(kind, src, gen, parts))

    # -- traduction ---------------------------------------------------------

    def to_src(self, line, col):
        """Generated position -> source position (None if synthetic)."""
        for seg in self.segments:
            if _pos_in(seg.gen, line, col):
                if seg.src is None:
                    return None
                if seg.kind == "copy":
                    return _translate_copy(seg.gen, seg.src, line, col)
                return (seg.src[0], seg.src[1])
        return None

    def to_gen(self, line, col):
        """Source position -> generated position."""
        for seg in self.segments:
            if seg.src is not None and _pos_in(seg.src, line, col):
                if seg.kind == "copy":
                    return _translate_copy(seg.src, seg.gen, line, col)
                return (seg.gen[0], seg.gen[1])
        return None

    def src_line_for_gen_line(self, line):
        """Source line matching a generated line (for tracebacks)."""
        best = None
        for seg in self.segments:
            if seg.src is None:
                continue
            if seg.gen[0] <= line <= seg.gen[2]:
                if seg.kind == "copy":
                    return _translate_copy(seg.gen, seg.src, line,
                                           seg.gen[1] if line == seg.gen[0] else 0)[0]
                best = seg.src[0]
        return best

    # -- serialisation ------------------------------------------------------

    def to_dict(self):
        """Forme JSON (version 1, format maison)."""
        return {
            "version": 1,
            "source": self.source_name,
            "generated": self.generated_name,
            "segments": [s.to_dict() for s in self.segments],
        }

    def to_json(self, **kw):
        """Serialise to JSON (kwargs passed to json.dumps)."""
        return json.dumps(self.to_dict(), **kw)

    @classmethod
    def from_dict(cls, d):
        """Reconstruit une map depuis sa forme JSON."""
        m = cls(d.get("source", "<ldpy>"), d.get("generated"))
        for sd in d.get("segments", []):
            src = tuple(sd["src"]) if "src" in sd else None
            parts = [(pd["kind"], tuple(pd["src"]), pd["gen"])
                     for pd in sd.get("parts", ())]
            m.segments.append(
                Segment(sd["kind"], src, tuple(sd["gen"]), parts))
        return m

    @classmethod
    def from_json(cls, s):
        """Rebuild a map from a JSON string."""
        return cls.from_dict(json.loads(s))


def snap_breakpoint_line(lmap, line_1based):
    """The .ldpy line where a breakpoint set on `line_1based` will REALLY bind.

    A multi-line island collapses into one statement whose code object carries
    the START line (record ldpy/011): no interior line is executable. Yet
    pydevd answers `verified: true` to a breakpoint set there, and never stops
    on it — a silent lie (measured, record vscode/103). So we snap the line to
    the island's start, and tooling can MOVE the dot to say so.
    l'outillage peut DÉPLACER la pastille pour le dire.

    Returns the same line when there is nothing to snap."""
    line0 = line_1based - 1
    for seg in lmap.segments:
        if seg.src is None or seg.kind == "copy":
            continue
        if seg.src[0] < line0 <= seg.src[2]:
            return seg.src[0] + 1
    return line_1based


def snap_breakpoint_lines(lmap, lines_1based):
    """`snap_breakpoint_line` over a list (order preserved)."""
    return [snap_breakpoint_line(lmap, l) for l in lines_1based]


# ---------------------------------------------------------------------------
# "Remapped" compilation: the generated code is compiled with the line numbers
# OF THE .ldpy SOURCE (through the map), so that tracebacks, pdb and debugpy
# all speak directly in .ldpy coordinates (record ldpy/011).
# ---------------------------------------------------------------------------


def remap_ast_lines(tree, lmap):
    """Rewrite lineno/end_lineno of every node of the GENERATED code's AST to
    the .ldpy source lines. A generated line with no origin (the synthetic
    prelude) snaps to line 1; the inside of a collapsed island snaps to the
    island's start line. Columns are kept as they are (co_positions are
    approximate on rewritten lines)."""
    import ast
    cache = {}

    def src_line(gen_1based):
        if gen_1based not in cache:
            s = lmap.src_line_for_gen_line(gen_1based - 1)
            cache[gen_1based] = (s + 1) if s is not None else None
        return cache[gen_1based]

    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", None)
        if lineno is None:
            continue
        new_lineno = src_line(lineno) or 1
        node.lineno = new_lineno
        end = getattr(node, "end_lineno", None)
        if end is not None:
            new_end = src_line(end) or new_lineno
            node.end_lineno = max(new_end, new_lineno)
    return tree


def compile_mapped(gen_code, lmap, filename, mode="exec",
                   dont_inherit=True, optimize=-1):
    """Compile the generated Python code with `filename` (the .ldpy) and the
    source line numbers, through `remap_ast_lines`. On an unexpected AST
    parse failure, fall back to an ordinary compilation (generated lines)."""
    import ast
    try:
        tree = ast.parse(gen_code, filename, mode)
    except SyntaxError:
        return compile(gen_code, filename, mode,
                       dont_inherit=dont_inherit, optimize=optimize)
    remap_ast_lines(tree, lmap)
    return compile(tree, filename, mode,
                   dont_inherit=dont_inherit, optimize=optimize)


# ---------------------------------------------------------------------------
# Export Source Map v3  : le format standard
# JavaScript tooling, to interoperate with the tools that read it.
# https://tc39.es/ecma426/ — champs [genCol, srcIdx, srcLine, srcCol] en
# base64-VLQ, as deltas; one ";" entry per generated line.
# ---------------------------------------------------------------------------

_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _vlq(value):
    """Encode a signed integer in base64-VLQ (zigzag + groups of 5 bits)."""
    v = (value << 1) if value >= 0 else ((-value << 1) | 1)
    out = []
    while True:
        digit = v & 0x1F
        v >>= 5
        if v:
            digit |= 0x20
        out.append(_B64[digit])
        if not v:
            return "".join(out)


def _mapping_points(lmap):
    """Points (gen_line, gen_col, src_line, src_col), sorted, deduplicated.

    One point per island start; for a copy segment, one point per generated
    line covered (the standard debugger granularity)."""
    points = {}
    for seg in lmap.segments:
        if seg.src is None:
            continue
        gl0, gc0, gl1, gc1 = seg.gen
        sl0, sc0, _, _ = seg.src
        if seg.kind == "copy":
            # exclusive end: if the segment ends at column 0, its last
            # "line" is empty and carries no point
            last = gl1 if gc1 > 0 else gl1 - 1
            for l in range(gl0, last + 1):
                gcol = gc0 if l == gl0 else 0
                scol = sc0 if l == gl0 else 0
                points.setdefault((l, gcol), (sl0 + (l - gl0), scol))
        else:
            points.setdefault((gl0, gc0), (sl0, sc0))
    return sorted((g[0], g[1], s[0], s[1]) for g, s in points.items())


def _to_sourcemap_v3(self):
    """Return the Source Map v3 dict equivalent to this map."""
    points = _mapping_points(self)
    lines = []
    prev_gcol = prev_sline = prev_scol = 0
    cur_line = 0
    buf = []
    for gline, gcol, sline, scol in points:
        while cur_line < gline:
            lines.append(",".join(buf))
            buf = []
            prev_gcol = 0
            cur_line += 1
        seg = (_vlq(gcol - prev_gcol) + _vlq(0) +
               _vlq(sline - prev_sline) + _vlq(scol - prev_scol))
        buf.append(seg)
        prev_gcol, prev_sline, prev_scol = gcol, sline, scol
    lines.append(",".join(buf))
    return {
        "version": 3,
        "file": self.generated_name or "",
        "sources": [self.source_name],
        "names": [],
        "mappings": ";".join(lines),
    }


def _to_sourcemap_v3_json(self, **kw):
    import json as _json
    return _json.dumps(self.to_sourcemap_v3(), **kw)


LanguageMap.to_sourcemap_v3 = _to_sourcemap_v3
LanguageMap.to_sourcemap_v3_json = _to_sourcemap_v3_json
