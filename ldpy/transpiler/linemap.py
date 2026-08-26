"""Language map segment-level entre un source .ldpy et le Python généré.

Voir DESIGN_CHOICES/ldpy/005-language-map.md.

Positions 0-based, fins exclusives. Trois sortes de segments :
- "copy"      : texte recopié verbatim -> traduction exacte des positions ;
- "island:*"  : îlot RDF réécrit -> traduction à la granularité de la région ;
- "synthetic" : texte généré sans origine (prélude d'import du runtime).
"""

import json


class Segment:
    __slots__ = ("kind", "src", "gen")

    def __init__(self, kind, src, gen):
        self.kind = kind
        self.src = src  # (line0, col0, line1, col1) ou None pour synthetic
        self.gen = gen  # (line0, col0, line1, col1)

    def __repr__(self):
        return "Segment(%r, src=%r, gen=%r)" % (self.kind, self.src, self.gen)

    def to_dict(self):
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
    def __init__(self, source_name="<ldpy>", generated_name=None):
        self.source_name = source_name
        self.generated_name = generated_name
        self.segments = []  # ordonnés en positions gen ET src croissantes

    def add(self, kind, src, gen):
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
        return {
            "version": 1,
            "source": self.source_name,
            "generated": self.generated_name,
            "segments": [s.to_dict() for s in self.segments],
        }

    def to_json(self, **kw):
        return json.dumps(self.to_dict(), **kw)

    @classmethod
    def from_dict(cls, d):
        m = cls(d.get("source", "<ldpy>"), d.get("generated"))
        for sd in d.get("segments", []):
            src = tuple(sd["src"]) if "src" in sd else None
            m.segments.append(Segment(sd["kind"], src, tuple(sd["gen"])))
        return m

    @classmethod
    def from_json(cls, s):
        return cls.from_dict(json.loads(s))
