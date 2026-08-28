"""Language map segment-level entre un source .ldpy et le Python généré.

Voir docs/reference/language-map.md.

Positions 0-based, fins exclusives. Trois sortes de segments :
- "copy"      : texte recopié verbatim -> traduction exacte des positions ;
- "island:*"  : îlot RDF réécrit -> traduction à la granularité de la région ;
- "synthetic" : texte généré sans origine (prélude d'import du runtime).
"""

import json


class Segment:
    """Un segment de correspondance source/généré (copy, island:*, synthetic)."""

    __slots__ = ("kind", "src", "gen")

    def __init__(self, kind, src, gen):
        self.kind = kind
        self.src = src  # (line0, col0, line1, col1) ou None pour synthetic
        self.gen = gen  # (line0, col0, line1, col1)

    def __repr__(self):
        return "Segment(%r, src=%r, gen=%r)" % (self.kind, self.src, self.gen)

    def to_dict(self):
        """Forme JSON du segment."""
        d = {"kind": self.kind, "gen": list(self.gen)}
        if self.src is not None:
            d["src"] = list(self.src)
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
    """Correspondance bidirectionnelle .ldpy <-> Python généré
    (liste ordonnée de Segments ; voir docs/reference/language-map.md)."""

    def __init__(self, source_name="<ldpy>", generated_name=None):
        self.source_name = source_name
        self.generated_name = generated_name
        self.segments = []  # ordonnés en positions gen ET src croissantes

    def add(self, kind, src, gen):
        """Ajoute un segment (ignore les segments vides des deux côtés)."""
        # ignore les segments vides des deux côtés
        if src is not None and src[:2] == src[2:] and gen[:2] == gen[2:]:
            return
        self.segments.append(Segment(kind, src, gen))

    # -- traduction ---------------------------------------------------------

    def to_src(self, line, col):
        """Position générée -> position source (None si synthétique)."""
        for seg in self.segments:
            if _pos_in(seg.gen, line, col):
                if seg.src is None:
                    return None
                if seg.kind == "copy":
                    return _translate_copy(seg.gen, seg.src, line, col)
                return (seg.src[0], seg.src[1])
        return None

    def to_gen(self, line, col):
        """Position source -> position générée."""
        for seg in self.segments:
            if seg.src is not None and _pos_in(seg.src, line, col):
                if seg.kind == "copy":
                    return _translate_copy(seg.src, seg.gen, line, col)
                return (seg.gen[0], seg.gen[1])
        return None

    def src_line_for_gen_line(self, line):
        """Ligne source correspondant à une ligne générée (pour tracebacks)."""
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

    # -- sérialisation ------------------------------------------------------

    def to_dict(self):
        """Forme JSON (version 1, format maison)."""
        return {
            "version": 1,
            "source": self.source_name,
            "generated": self.generated_name,
            "segments": [s.to_dict() for s in self.segments],
        }

    def to_json(self, **kw):
        """Sérialise en JSON (kwargs passés à json.dumps)."""
        return json.dumps(self.to_dict(), **kw)

    @classmethod
    def from_dict(cls, d):
        """Reconstruit une map depuis sa forme JSON."""
        m = cls(d.get("source", "<ldpy>"), d.get("generated"))
        for sd in d.get("segments", []):
            src = tuple(sd["src"]) if "src" in sd else None
            m.segments.append(Segment(sd["kind"], src, tuple(sd["gen"])))
        return m

    @classmethod
    def from_json(cls, s):
        """Reconstruit une map depuis une chaîne JSON."""
        return cls.from_dict(json.loads(s))


def snap_breakpoint_line(lmap, line_1based):
    """Ligne .ldpy où un point d'arrêt posé sur `line_1based` se liera VRAIMENT.

    Un îlot multiligne s'effondre en une instruction dont le code object porte
    la ligne de DÉBUT (fiche ldpy/011) : aucune ligne intérieure n'est
    exécutable. Or pydevd répond `verified: true` à un point d'arrêt posé là,
    et ne s'y arrête jamais — un mensonge silencieux (mesuré, fiche
    vscode/103). On rabat donc la ligne sur le début de l'îlot, et
    l'outillage peut DÉPLACER la pastille pour le dire.

    Rend la même ligne quand il n'y a rien à rabattre."""
    line0 = line_1based - 1
    for seg in lmap.segments:
        if seg.src is None or seg.kind == "copy":
            continue
        if seg.src[0] < line0 <= seg.src[2]:
            return seg.src[0] + 1
    return line_1based


def snap_breakpoint_lines(lmap, lines_1based):
    """`snap_breakpoint_line` sur une liste (ordre conservé)."""
    return [snap_breakpoint_line(lmap, l) for l in lines_1based]


# ---------------------------------------------------------------------------
# Compilation « remappée » : le code généré est compilé avec les numéros de
# ligne DU SOURCE .ldpy (via la map), si bien que tracebacks, pdb et debugpy
# parlent directement en coordonnées .ldpy (fiche DESIGN_CHOICES/ldpy/011).
# ---------------------------------------------------------------------------


def remap_ast_lines(tree, lmap):
    """Réécrit lineno/end_lineno de chaque nœud de l'AST du code GÉNÉRÉ vers
    les lignes du source .ldpy. Une ligne générée sans origine (prélude
    synthétique) est rabattue sur la ligne 1 ; l'intérieur d'un îlot replié
    est rabattu sur la ligne de début de l'îlot. Les colonnes sont conservées
    telles quelles (co_positions approximatives sur les lignes réécrites)."""
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
    """Compile le code Python généré avec `filename` (le .ldpy) et les numéros
    de ligne du source, via `remap_ast_lines`. En cas d'échec inattendu de
    l'analyse AST, retombe sur une compilation ordinaire (lignes générées)."""
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
# de l'outillage JavaScript, pour interopérer avec les outils qui le lisent.
# https://tc39.es/ecma426/ — champs [genCol, srcIdx, srcLine, srcCol] en
# base64-VLQ, en deltas ; une entrée « ; » par ligne générée.
# ---------------------------------------------------------------------------

_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _vlq(value):
    """Encode un entier signé en base64-VLQ (zigzag + groupes de 5 bits)."""
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
    """Points (gen_line, gen_col, src_line, src_col), triés, dédoublonnés.

    Un point par début d'îlot ; pour un segment copy, un point par ligne
    générée couverte (granularité standard des débogueurs)."""
    points = {}
    for seg in lmap.segments:
        if seg.src is None:
            continue
        gl0, gc0, gl1, gc1 = seg.gen
        sl0, sc0, _, _ = seg.src
        if seg.kind == "copy":
            # fin exclusive : si le segment finit colonne 0, sa dernière
            # « ligne » est vide et ne porte aucun point
            last = gl1 if gc1 > 0 else gl1 - 1
            for l in range(gl0, last + 1):
                gcol = gc0 if l == gl0 else 0
                scol = sc0 if l == gl0 else 0
                points.setdefault((l, gcol), (sl0 + (l - gl0), scol))
        else:
            points.setdefault((gl0, gc0), (sl0, sc0))
    return sorted((g[0], g[1], s[0], s[1]) for g, s in points.items())


def _to_sourcemap_v3(self):
    """Retourne le dict Source Map v3 équivalent à cette map."""
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
