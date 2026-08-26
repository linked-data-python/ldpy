"""Les exemples historiques v1 (examples/*.ldpy) passent sous v2."""

import glob
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = sorted(glob.glob(os.path.join(REPO, "examples", "*.ldpy")))


@pytest.mark.parametrize("path", EXAMPLES, ids=os.path.basename)
def test_example_runs(path):
    proc = subprocess.run(
        [sys.executable, "-m", "ldpy", path],
        cwd=REPO, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, \
        "stdout:\n%s\nstderr:\n%s" % (proc.stdout, proc.stderr)


ERROR_EXAMPLES = sorted(glob.glob(os.path.join(REPO, "examples", "errors",
                                               "*.ldpy")))


@pytest.mark.parametrize("path", ERROR_EXAMPLES, ids=os.path.basename)
def test_error_example_fails_at_runtime(path):
    """Ces exemples testent le mapping d'erreurs : la transpilation réussit,
    l'exécution échoue (NameError, TypeError...)."""
    proc = subprocess.run(
        [sys.executable, "-m", "ldpy", path],
        cwd=REPO, capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0
