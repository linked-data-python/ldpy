"""Language map : traductions de positions, sérialisation, tracebacks."""

from ldpy.transpiler import transpile, LanguageMap


P = "@prefix ex: <http://example.org/ns#> .\n"


def test_map_roundtrip_json():
    result = transpile(P + "x = ex:a\n", "m.ldpy")
    m2 = LanguageMap.from_json(result.map.to_json())
    assert [s.kind for s in m2.segments] == \
        [s.kind for s in result.map.segments]


def test_copy_positions_before_and_after_island():
    src = "y = 1\nx = <http://e/a> + z\n"
    result = transpile(src)
    code = result.code
    # le prélude est en ligne 0 ; 'y = 1' en ligne 1
    assert code.split("\n")[1] == "y = 1"
    assert result.map.to_gen(0, 0) == (1, 0)          # src y -> gen ligne 1
    assert result.map.to_src(1, 0) == (0, 0)
    # position APRES l'îlot sur la même ligne : ' + z'
    gen_line = code.split("\n")[2]
    z_gen_col = gen_line.index("+ z") + 2
    z_src_col = src.split("\n")[1].index("+ z") + 2
    assert result.map.to_src(2, z_gen_col) == (1, z_src_col)
    assert result.map.to_gen(1, z_src_col) == (2, z_gen_col)


def test_island_region_mapping():
    src = "x = <http://e/a>\n"
    result = transpile(src)
    seg = [s for s in result.map.segments if s.kind == "island:iri"][0]
    assert seg.src[0] == 0 and seg.src[1] == 4
    # une position à l'intérieur de l'îlot se projette sur le début de région
    inside = result.map.to_src(seg.gen[0], seg.gen[1] + 3)
    assert inside == (0, 4)


def test_multiline_graph_collapses_lines():
    src = P + "gr = g{ ex:s ex:p 1 ;\n        ex:q 2 }\nafter = 3\n"
    result = transpile(src)
    lines = result.code.split("\n")
    # 'after = 3' doit être mappé correctement malgré l'effondrement du g{}
    gen_after_line = next(i for i, l in enumerate(lines) if l == "after = 3")
    assert result.map.to_src(gen_after_line, 0) == (3, 0)
    assert result.map.to_gen(3, 0) == (gen_after_line, 0)


def test_synthetic_prelude_segment():
    result = transpile("x = <http://e/a>\n")
    kinds = [s.kind for s in result.map.segments]
    assert "synthetic" in kinds
    syn = [s for s in result.map.segments if s.kind == "synthetic"][0]
    assert result.map.to_src(syn.gen[0], 0) is None


def test_src_line_for_gen_line_traceback(run):
    src = P + "x = 1\ndef boom():\n    raise ValueError(x)\n"
    g, result = run(src)
    code_lines = result.code.split("\n")
    raise_gen_line = next(i for i, l in enumerate(code_lines)
                          if "raise ValueError" in l)
    assert result.map.src_line_for_gen_line(raise_gen_line) == 3


def test_docstring_split_segment_mapping():
    src = '"""Doc."""\ny = 1\nx = <http://e/a>\n'
    result = transpile(src)
    lines = result.code.split("\n")
    assert lines[0] == '"""Doc."""'
    assert lines[1].startswith("import ldpy.runtime")
    assert lines[2] == "y = 1"
    assert result.map.to_gen(1, 0) == (2, 0)   # y = 1
    assert result.map.to_src(2, 0) == (1, 0)
    assert result.map.to_src(0, 0) == (0, 0)   # docstring inchangée


# ----------------------------- rabattement des points d'arrêt (fiche vscode/103)

MULTILIGNE = """\
@prefix ex: <http://example.org/> .
valeur = 21.5
gr = g{ ex:s a ex:Obs ;
        ex:v {valeur} ;
        ex:w 2 }
print(len(gr))
"""


def _map(src=MULTILIGNE):
    from ldpy.transpiler import transpile
    return transpile(src, "p.ldpy").map


def test_snap_laisse_les_lignes_liables_en_place():
    from ldpy.transpiler.linemap import snap_breakpoint_lines
    assert snap_breakpoint_lines(_map(), [1, 2, 3, 6]) == [1, 2, 3, 6]


def test_snap_rabat_linterieur_dun_ilot_sur_son_debut():
    from ldpy.transpiler.linemap import snap_breakpoint_lines
    assert snap_breakpoint_lines(_map(), [4, 5]) == [3, 3]


def test_snap_est_idempotent():
    from ldpy.transpiler.linemap import snap_breakpoint_lines
    m = _map()
    une = snap_breakpoint_lines(m, [1, 2, 3, 4, 5, 6])
    assert snap_breakpoint_lines(m, une) == une


def test_snap_ne_touche_pas_un_ilot_dune_seule_ligne():
    from ldpy.transpiler.linemap import snap_breakpoint_lines
    m = _map("@prefix ex: <http://e/> .\ng = g{ ex:s ex:p 1 }\nprint(g)\n")
    assert snap_breakpoint_lines(m, [1, 2, 3]) == [1, 2, 3]
