"""Matérialisation .ldpy-build (ldpy/build.py)."""

import json
import os
import subprocess
import sys

from ldpy.build import build_file, build_tree


def test_build_file(tmp_path):
    src = tmp_path / "mod.ldpy"
    src.write_text("@prefix ex: <http://e/ns#> .\nX = ex:a\n")
    out = tmp_path / "build"
    py_path, map_path, result = build_file(str(src), str(out))
    assert os.path.isfile(py_path) and py_path.endswith("mod.py")
    assert os.path.isfile(map_path)
    m = json.load(open(map_path))
    assert m["version"] == 1
    assert m["generated"] == py_path
    # le .py fantôme est exécutable
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, PYTHONPATH=repo)
    proc = subprocess.run([sys.executable, py_path], capture_output=True,
                          cwd=repo, env=env)
    assert proc.returncode == 0, proc.stderr


def test_build_tree_mixed(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.ldpy").write_text("X = <http://e/a>\n")
    (tmp_path / "pkg" / "b.py").write_text("Y = 1\n")
    out = tmp_path / "out"
    built, errors = build_tree(str(tmp_path), str(out))
    assert not errors
    assert (out / "pkg" / "a.py").is_file()
    assert (out / "pkg" / "a.ldpy.map").is_file()
    assert (out / "pkg" / "b.py").read_text() == "Y = 1\n"


def test_build_reports_syntax_error(tmp_path):
    (tmp_path / "bad.ldpy").write_text("g = g{ foo:bar a foo:C }\n")
    out = tmp_path / "out"
    built, errors = build_tree(str(tmp_path), str(out))
    assert len(errors) == 1 and "foo" in str(errors[0])
