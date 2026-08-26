import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from ldpy.transpiler import transpile  # noqa: E402


@pytest.fixture
def run():
    """Transpile puis exécute ; retourne (globals, TranspileResult)."""
    def _run(source, filename="<test>"):
        result = transpile(source, filename)
        g = {"__name__": "test_module"}
        exec(compile(result.code, filename, "exec"), g)
        return g, result
    return _run


PREFIXES = """\
@prefix ex: <http://example.org/ns#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
"""


@pytest.fixture
def prefixes():
    return PREFIXES
