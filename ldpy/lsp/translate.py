"""Translating positions, ranges and URIs between a .ldpy document and its
Python shadow, through the LanguageMap — on raw LSP structures (dicts).

The functions are pure and unit-tested (tests/test_lsp_translate.py).
"""


def shadow_uri(uri):
    """URI of the Python shadow document of a .ldpy (in-memory convention)."""
    return uri + ".shadow.py"


def unshadow_uri(uri):
    """Original .ldpy URI of a shadow URI (inverse of shadow_uri)."""
    if uri.endswith(".shadow.py"):
        return uri[:-len(".shadow.py")]
    return uri


def pos_to_py(lmap, pos):
    """Position LSP .ldpy -> .py (dict {'line','character'})."""
    r = lmap.to_gen(pos["line"], pos["character"])
    if r is None:
        return None
    return {"line": r[0], "character": r[1]}


def pos_to_ldpy(lmap, pos):
    """Position LSP .py -> .ldpy (None si synthétique)."""
    r = lmap.to_src(pos["line"], pos["character"])
    if r is None:
        return None
    return {"line": r[0], "character": r[1]}


def _is_pos(d):
    return isinstance(d, dict) and set(d) >= {"line", "character"} \
        and isinstance(d.get("line"), int)


def _is_range(d):
    return isinstance(d, dict) and _is_pos(d.get("start", None) or {}) \
        and _is_pos(d.get("end", None) or {})


def translate_result(obj, lmap, maps_by_uri=None):
    """Recursively translate a backend RESULT (.py -> .ldpy):

    - every range {'start','end'} is translated through the map;
    - every 'uri'/'targetUri' field pointing at a shadow is un-shadowed, and
      the ranges of an object carrying that uri use THAT document's map
      document (maps_by_uri : uri .ldpy -> LanguageMap).

    An untranslatable range (a synthetic position) is left as it is rather
    than breaking the structure."""
    maps_by_uri = maps_by_uri or {}

    def walk(node, cur_map):
        if isinstance(node, list):
            return [walk(x, cur_map) for x in node]
        if not isinstance(node, dict):
            return node
        out = {}
        # this node's uri may change which map applies to ITS ranges
        for key in ("uri", "targetUri"):
            u = node.get(key)
            if isinstance(u, str) and u.endswith(".shadow.py"):
                ldpy_uri = unshadow_uri(u)
                cur_map = maps_by_uri.get(ldpy_uri, cur_map)
        for k, v in node.items():
            if k in ("uri", "targetUri") and isinstance(v, str):
                out[k] = unshadow_uri(v)
            elif _is_range(v):
                out[k] = _range_to_ldpy(cur_map, v)
            elif _is_pos(v) and k == "position":
                out[k] = pos_to_ldpy(cur_map, v) or v
            else:
                out[k] = walk(v, cur_map)
        return out

    return walk(obj, lmap)


def _range_to_ldpy(lmap, rng):
    s = pos_to_ldpy(lmap, rng["start"])
    e = pos_to_ldpy(lmap, rng["end"])
    if s is None or e is None:
        return rng
    return {"start": s, "end": e}


def island_at(lmap, line, character):
    """The island segment covering a source position, or None."""
    for seg in lmap.segments:
        if seg.src is None or not seg.kind.startswith("island:"):
            continue
        sl0, sc0, sl1, sc1 = seg.src
        if (sl0, sc0) <= (line, character) < (sl1, sc1):
            return seg
    return None


# ---------------------------------------------------------- semantic tokens

TOKEN_TYPES = ["namespace", "string", "type", "variable", "macro", "keyword"]
_KIND_TO_TYPE = {
    "island:prefix": 5, "island:base": 5,       # keyword
    "island:iri": 1, "island:literal": 1,       # string
    "island:pname": 2,                          # type
    "island:var": 3,                            # variable
    "island:firi": 4, "island:fnode": 4,        # macro
    "island:graph": 4,                          # macro (région entière)
    # fiches 013-019
    "island:import": 5,                         # keyword (prefix import)
    "island:graph-decl": 5, "island:bindings-decl": 5,
    "island:for-bindings": 5, "island:for-bindings-close": 5,
    "island:match": 4, "island:sparql": 4,      # macro (région entière)
    "island:addto": 4, "island:removefrom": 4,
    "island:enode": 4, "island:eiri": 4,
}


def semantic_tokens(lmap):
    """LSP encoding (deltas) of the SINGLE-LINE islands of the source doc."""
    toks = []
    for seg in lmap.segments:
        if seg.src is None or seg.kind not in _KIND_TO_TYPE:
            continue
        sl0, sc0, sl1, sc1 = seg.src
        if sl0 != sl1:
            continue                       # multiligne : laissé à TextMate
        toks.append((sl0, sc0, sc1 - sc0, _KIND_TO_TYPE[seg.kind]))
    toks.sort()
    data, prev_line, prev_col = [], 0, 0
    for line, col, length, ttype in toks:
        dline = line - prev_line
        dcol = col - prev_col if dline == 0 else col
        data.extend([dline, dcol, length, ttype, 0])
        prev_line, prev_col = line, col
    return data
