"""Débogage (ldpy/debug.py) : traduction de breakpoints et lanceur debugpy."""

import json
import os
import subprocess
import sys

import pytest

from ldpy.transpiler import transpile
from ldpy.transpiler.linemap import compile_mapped
from ldpy.debug import translate_breakpoints, translate_frames

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAS_DEBUGPY = subprocess.run(
    [sys.executable, "-c", "import debugpy"], capture_output=True).returncode == 0

SRC = """\
@prefix ex: <http://example.org/ns#> .
valeur = 21.5
gr = g{ ex:s a ex:Obs ;
        ex:v {valeur} }
print(len(gr))
"""


def run_debug(tmp_path, extra, src=SRC, name="prog.ldpy"):
    f = tmp_path / name
    f.write_text(src)
    env = dict(os.environ, PYTHONPATH=REPO)
    return subprocess.run(
        [sys.executable, "-m", "ldpy.debug", str(f),
         "-o", str(tmp_path / "build"), *extra],
        capture_output=True, text=True, cwd=REPO, env=env, timeout=120)


# ----------------------------------------------------- traduction (unités)

def test_breakpoints_shifted_by_prelude():
    r = transpile(SRC, "p.ldpy")
    # ligne 2 : +1 (prélude). ligne 5 : +1 (prélude) mais -1 (le g{...} de
    # deux lignes s'est effondré en une) -> 5.
    assert translate_breakpoints(r.map, [2, 5]) == [3, 5]


def test_breakpoint_inside_multiline_island_snaps_to_expression():
    r = transpile(SRC, "p.ldpy")
    # ligne 4 = l'intérieur du g{...} multiligne : rabattue sur la ligne
    # générée qui contient l'expression graphe
    [line] = translate_breakpoints(r.map, [4])
    assert line is not None
    assert "_ldpy_.graph" in r.code.split("\n")[line - 1]


def test_frames_translated_back():
    r = transpile(SRC, "p.ldpy")
    gen_print = next(i for i, l in enumerate(r.code.split("\n"), 1)
                     if l.startswith("print("))
    assert translate_frames(r.map, [gen_print]) == [5]


def test_frames_on_prelude_is_none():
    r = transpile(SRC, "p.ldpy")
    assert translate_frames(r.map, [1]) == [None]


def test_roundtrip_breakpoint_frame():
    r = transpile(SRC, "p.ldpy")
    for src_line in (2, 5):
        [gen] = translate_breakpoints(r.map, [src_line])
        assert translate_frames(r.map, [gen]) == [src_line]


# ------------------------------------------------------------ CLI --breakpoints

def test_cli_breakpoints_mode(tmp_path):
    p = run_debug(tmp_path, ["--breakpoints", "2,4,5"])
    assert p.returncode == 0, p.stderr
    d = json.loads(p.stdout)
    assert d["shadow"].endswith("prog.py")
    assert os.path.isfile(d["map"])
    # absolute, because this output crosses a process boundary: an editor
    # that turned a relative path into a URI would root it at "/"
    assert os.path.isabs(d["shadow"]) and os.path.isabs(d["map"])
    assert os.path.isfile(d["shadow"])
    assert d["breakpoints"]["2"] == 3
    assert d["breakpoints"]["5"] == 5    # prélude +1, effondrement du g{} -1


# ------------------------------------------------------------------ lanceur

def test_cli_runs_shadow(tmp_path):
    p = run_debug(tmp_path, [])
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "2"        # les 2 triplets du graphe


def test_cli_passes_argv(tmp_path):
    src = "import sys\nprint(sys.argv[1])\n"
    p = run_debug(tmp_path, ["--", "bonjour"], src=src)
    assert "bonjour" in p.stdout


def test_cli_reports_ldpy_error(tmp_path):
    p = run_debug(tmp_path, [], src="g = g{ foo:b a foo:C }\n")
    assert p.returncode == 1
    assert "foo" in p.stderr


def test_runtime_error_positions_are_in_shadow(tmp_path):
    """Le traceback pointe le fantôme : c'est LE contrat du jalon (debugpy
    voit de vrais .py) ; la re-projection est le rôle de la map/outillage."""
    p = run_debug(tmp_path, [], src="@prefix e: <http://e/> .\nboom()\n")
    assert p.returncode != 0
    assert "prog.py" in p.stderr and "boom" in p.stderr


# ------------------------------------------------- mode direct (fiche 011)

def test_compile_mapped_filename_and_lines():
    """Le code object porte le nom du .ldpy et les numéros de ligne SOURCE :
    l'intérieur de l'îlot multiligne (ligne générée 4) est rabattu sur la
    ligne source 3 (début du g{...}), la ligne 4 source n'est exécutable
    nulle part."""
    r = transpile(SRC, "p.ldpy")
    code = compile_mapped(r.code, r.map, "p.ldpy")
    assert code.co_filename == "p.ldpy"
    lines = {l for (_, _, l) in code.co_lines() if l is not None}
    assert {2, 3, 5} <= lines
    assert 4 not in lines


def test_run_direct_output(tmp_path):
    p = run_debug(tmp_path, ["--run"])
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "2"


def test_run_direct_passes_argv(tmp_path):
    p = run_debug(tmp_path, ["--run", "--", "bonjour"],
                  src="import sys\nprint(sys.argv[1])\n")
    assert "bonjour" in p.stdout


def test_run_direct_traceback_points_to_ldpy(tmp_path):
    """LE contrat du mode direct : le traceback nomme le .ldpy et SES lignes
    (le boom() en ligne source 3, pas la ligne générée 4)."""
    p = run_debug(tmp_path, ["--run"],
                  src="@prefix e: <http://e/> .\n\nboom()\n")
    assert p.returncode != 0
    assert 'prog.ldpy", line 3' in p.stderr
    assert "prog.py" not in p.stderr


def test_main_module_traceback_is_source_mapped(tmp_path):
    """`python -m ldpy` compile aussi en coordonnées source (fiche 011)."""
    f = tmp_path / "prog.ldpy"
    f.write_text("@prefix e: <http://e/> .\n\nboom()\n")
    env = dict(os.environ, PYTHONPATH=REPO)
    p = subprocess.run([sys.executable, "-m", "ldpy", str(f)],
                       capture_output=True, text=True, env=env, timeout=120)
    assert p.returncode != 0
    assert 'prog.ldpy", line 3' in p.stderr


@pytest.mark.skipif(not HAS_DEBUGPY, reason="debugpy non installé")
def test_cli_under_real_debugpy(tmp_path):
    """Intégration réelle : le fantôme s'exécute SOUS debugpy (port éphémère,
    sans attente de client) et produit sa sortie normale."""
    p = run_debug(tmp_path, ["--listen", "127.0.0.1:0"])
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip().endswith("2")
