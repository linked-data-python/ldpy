"""Débogage (ldpy/debug.py) : traduction de breakpoints et lanceur debugpy."""

import json
import os
import subprocess
import sys

import pytest

from ldpy.transpiler import transpile
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


@pytest.mark.skipif(not HAS_DEBUGPY, reason="debugpy non installé")
def test_cli_under_real_debugpy(tmp_path):
    """Intégration réelle : le fantôme s'exécute SOUS debugpy (port éphémère,
    sans attente de client) et produit sa sortie normale."""
    p = run_debug(tmp_path, ["--listen", "127.0.0.1:0"])
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip().endswith("2")
