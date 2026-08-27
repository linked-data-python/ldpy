"""Export Source Map v3 (fiche 005, révision) — vérifié par un décodeur
indépendant écrit dans ce fichier de test."""

import json

from ldpy.transpiler import transpile
from ldpy.transpiler.linemap import _vlq

B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def vlq_decode(s):
    """Décodeur base64-VLQ indépendant de l'implémentation testée."""
    values, shift, value = [], 0, 0
    for c in s:
        digit = B64.index(c)
        value |= (digit & 0x1F) << shift
        if digit & 0x20:
            shift += 5
        else:
            values.append((-(value >> 1)) if value & 1 else (value >> 1))
            shift, value = 0, 0
    return values


def decode_mappings(mappings):
    """mappings -> liste de (gen_line, gen_col, src_line, src_col)."""
    out = []
    sline = scol = 0
    for gline, line in enumerate(mappings.split(";")):
        gcol = 0
        for seg in filter(None, line.split(",")):
            f = vlq_decode(seg)
            gcol += f[0]
            sline += f[2]
            scol += f[3]
            out.append((gline, gcol, sline, scol))
    return out


# --------------------------------------------------------------- VLQ seul

def test_vlq_known_vectors():
    assert _vlq(0) == "A"
    assert _vlq(1) == "C"
    assert _vlq(-1) == "D"
    assert _vlq(16) == "gB"


def test_vlq_roundtrip_range():
    for v in list(range(-300, 300)) + [12345, -12345, 1 << 20]:
        assert vlq_decode(_vlq(v)) == [v], v


# ---------------------------------------------------------- maps complètes

def test_identity_file_maps_line_to_line():
    src = "a = 1\nb = 2\nc = 3\n"
    sm = transpile(src).map.to_sourcemap_v3()
    assert sm["version"] == 3
    pts = decode_mappings(sm["mappings"])
    for line in range(3):
        assert (line, 0, line, 0) in pts


def test_prelude_shifts_generated_lines():
    src = "x = <http://e/a>\ny = 2\n"
    result = transpile(src, "m.ldpy")
    sm = result.map.to_sourcemap_v3()
    assert sm["sources"] == ["m.ldpy"]
    pts = decode_mappings(sm["mappings"])
    # le prélude (ligne générée 0) n'est mappé sur rien
    assert not any(g == 0 for g, _, _, _ in pts)
    # la ligne source 0 est mappée sur la ligne générée 1, la 1 sur la 2
    assert any(g == 1 and s == 0 for g, _, s, _ in pts)
    assert (2, 0, 1, 0) in pts


def test_island_start_is_a_mapping_point():
    src = "y = 1\nx = <http://e/a> + z\n"
    result = transpile(src)
    sm = result.map.to_sourcemap_v3()
    pts = decode_mappings(sm["mappings"])
    # l'îlot commence colonne 4 de la ligne source 1 (ligne générée 2)
    island_pts = [p for p in pts if p[0] == 2 and p[3] == 4]
    assert island_pts and island_pts[0][2] == 1


def test_multiline_graph_collapse_consistent_with_json_map():
    src = ("@prefix ex: <http://e/> .\n"
           "gr = g{ ex:s ex:p 1 ;\n"
           "        ex:q 2 }\n"
           "after = 3\n")
    result = transpile(src)
    pts = decode_mappings(result.map.to_sourcemap_v3()["mappings"])
    # chaque point du sourcemap doit coïncider avec map.to_src
    for gline, gcol, sline, scol in pts:
        assert result.map.to_src(gline, gcol) == (sline, scol), (gline, gcol)


def test_every_point_agrees_with_to_src_on_dense_file():
    src = ("@prefix ex: <http://e/> .\n"
           "def f(s, v):\n"
           "    return g{ ex:{s} a ex:Sensor ; ex:val {v} }\n"
           "x = f('a', 1)\n"
           "lit = '21'^^ex:cel\n")
    result = transpile(src)
    pts = decode_mappings(result.map.to_sourcemap_v3()["mappings"])
    assert len(pts) >= 5
    for gline, gcol, sline, scol in pts:
        assert result.map.to_src(gline, gcol) == (sline, scol)


def test_json_serialization_fields():
    result = transpile("x = <http://e/a>\n", "mod.ldpy")
    result.map.generated_name = "mod.py"
    d = json.loads(result.map.to_sourcemap_v3_json())
    assert d["file"] == "mod.py"
    assert d["sources"] == ["mod.ldpy"]
    assert d["names"] == []
