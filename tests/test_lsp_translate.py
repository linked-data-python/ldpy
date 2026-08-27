"""Traduction LSP (ldpy/lsp/translate.py) : fonctions pures, testées seules."""

from ldpy.transpiler import transpile
from ldpy.lsp import translate as tr

P = "@prefix ex: <http://example.org/ns#> .\n"


def make(src="y = 1\nx = <http://e/a> + z\n", name="doc.ldpy"):
    return transpile(src, name)


# ------------------------------------------------------------- positions

def test_pos_roundtrip_on_copy_text():
    r = make()
    py = tr.pos_to_py(r.map, {"line": 0, "character": 2})
    assert py == {"line": 1, "character": 2}          # décalé par le prélude
    back = tr.pos_to_ldpy(r.map, py)
    assert back == {"line": 0, "character": 2}


def test_pos_in_prelude_is_none():
    r = make()
    assert tr.pos_to_ldpy(r.map, {"line": 0, "character": 3}) is None


def test_pos_after_island_shifts_columns():
    src = "x = <http://e/a> + zvar\n"
    r = transpile(src)
    src_col = src.index("zvar")
    gen_line = r.code.split("\n")[1]
    gen_col = gen_line.index("zvar")
    assert tr.pos_to_py(r.map, {"line": 0, "character": src_col}) == \
        {"line": 1, "character": gen_col}


# ------------------------------------------------------------------ uris

def test_shadow_uri_roundtrip():
    u = "file:///w/mod.ldpy"
    assert tr.shadow_uri(u) == "file:///w/mod.ldpy.shadow.py"
    assert tr.unshadow_uri(tr.shadow_uri(u)) == u
    assert tr.unshadow_uri("file:///autre.py") == "file:///autre.py"


# ------------------------------------------------- structures de résultats

def test_translate_location_result():
    r = make()
    raw = {"uri": "file:///w/doc.ldpy.shadow.py",
           "range": {"start": {"line": 1, "character": 0},
                     "end": {"line": 1, "character": 1}}}
    out = tr.translate_result(raw, r.map,
                              {"file:///w/doc.ldpy": r.map})
    assert out["uri"] == "file:///w/doc.ldpy"
    assert out["range"]["start"] == {"line": 0, "character": 0}


def test_translate_list_of_locations():
    r = make()
    raw = [{"uri": "file:///w/doc.ldpy.shadow.py",
            "range": {"start": {"line": 2, "character": 4},
                      "end": {"line": 2, "character": 5}}}]
    out = tr.translate_result(raw, r.map, {"file:///w/doc.ldpy": r.map})
    assert out[0]["range"]["start"]["line"] == 1


def test_translate_completion_textedit():
    r = make()
    raw = {"isIncomplete": False, "items": [
        {"label": "zvar", "textEdit": {
            "range": {"start": {"line": 2, "character": 0},
                      "end": {"line": 2, "character": 2}},
            "newText": "zvar"}}]}
    out = tr.translate_result(raw, r.map, {})
    assert out["items"][0]["textEdit"]["range"]["start"]["line"] == 1
    assert out["items"][0]["textEdit"]["newText"] == "zvar"   # intact


def test_untranslatable_range_left_intact():
    r = make()
    raw = {"range": {"start": {"line": 0, "character": 0},
                     "end": {"line": 0, "character": 5}}}   # prélude
    out = tr.translate_result(raw, r.map, {})
    assert out["range"] == raw["range"]


def test_foreign_python_file_uri_untouched_ranges():
    """Un résultat pointant vers un vrai .py (stdlib) ne doit PAS être
    traduit par la map du document ldpy."""
    r = make()
    raw = {"uri": "file:///usr/lib/python3.12/os.py",
           "range": {"start": {"line": 100, "character": 0},
                     "end": {"line": 100, "character": 3}}}
    out = tr.translate_result(raw, r.map, {"file:///w/doc.ldpy": r.map})
    # la range est « traduite » avec la map courante... position (100,0)
    # est hors de la carte -> laissée telle quelle
    assert out["range"]["start"]["line"] == 100
    assert out["uri"].endswith("os.py")


# ------------------------------------------------------- île sous le curseur

def test_island_at_positions():
    r = make()
    seg = tr.island_at(r.map, 1, 5)          # dans <http://e/a>
    assert seg is not None and seg.kind == "island:iri"
    assert tr.island_at(r.map, 0, 2) is None     # y = 1
    assert tr.island_at(r.map, 1, 0) is None     # 'x' avant l'îlot


# --------------------------------------------------------- semantic tokens

def test_semantic_tokens_encoding():
    src = P + "a = ex:T\nb = <http://e/i>\nv = ?x\n"
    r = transpile(src)
    data = tr.semantic_tokens(r.map)
    assert len(data) % 5 == 0
    toks = [data[i:i + 5] for i in range(0, len(data), 5)]
    # premier token : la déclaration @prefix, ligne 0 colonne 0
    assert toks[0][:2] == [0, 0]
    assert toks[0][3] == tr.TOKEN_TYPES.index("keyword")
    kinds = {t[3] for t in toks}
    assert tr.TOKEN_TYPES.index("type") in kinds        # pname
    assert tr.TOKEN_TYPES.index("string") in kinds      # iri
    assert tr.TOKEN_TYPES.index("variable") in kinds    # ?x


def test_semantic_tokens_deltas_are_relative():
    src = "a = <http://e/1>\nb = <http://e/2>\n"
    r = transpile(src)
    data = tr.semantic_tokens(r.map)
    toks = [data[i:i + 5] for i in range(0, len(data), 5)]
    assert toks[0][0] == 0          # ligne absolue du premier
    assert toks[1][0] == 1          # delta d'une ligne
    assert toks[1][1] == 4          # colonne absolue (nouvelle ligne)


def test_semantic_tokens_skip_multiline_islands():
    src = P + "gr = g{ ex:s ex:p 1 ;\n        ex:q 2 }\n"
    r = transpile(src)
    data = tr.semantic_tokens(r.map)
    toks = [data[i:i + 5] for i in range(0, len(data), 5)]
    # le g{...} multiligne n'émet pas de token ; le @prefix si
    assert all(t[2] < 100 for t in toks)
    assert len(toks) == 1
