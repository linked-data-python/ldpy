"""Import hook v2 (importlib, sans `ideas`)."""

import os
import sys
import textwrap

import pytest
from rdflib import URIRef

import ldpy
from ldpy.importer import MAPS


@pytest.fixture
def module_dir(tmp_path):
    sys.path.insert(0, str(tmp_path))
    ldpy.install()
    yield tmp_path
    sys.path.remove(str(tmp_path))
    for name in list(sys.modules):
        if name.startswith("ldpymod_"):
            del sys.modules[name]


def test_import_ldpy_module(module_dir):
    (module_dir / "ldpymod_a.ldpy").write_text(textwrap.dedent("""\
        @prefix ex: <http://example.org/ns#> .
        TERM = ex:Thing
        GRAPH = g{ ex:s ex:p 1 }
        def hello():
            return ex:hello
        """))
    import ldpymod_a
    assert ldpymod_a.TERM == URIRef("http://example.org/ns#Thing")
    assert len(ldpymod_a.GRAPH) == 1
    assert ldpymod_a.hello() == URIRef("http://example.org/ns#hello")


def test_map_registered_for_imported_module(module_dir):
    (module_dir / "ldpymod_b.ldpy").write_text("X = <http://e/a>\n")
    import ldpymod_b
    path = os.path.join(str(module_dir), "ldpymod_b.ldpy")
    assert path in MAPS
    assert ldpymod_b.X == URIRef("http://e/a")


def test_no_leak_between_imported_modules(module_dir):
    (module_dir / "ldpymod_c.ldpy").write_text(
        "@prefix c: <http://c/> .\nX = c:x\n")
    (module_dir / "ldpymod_d.ldpy").write_text("Y = 1\n")
    import ldpymod_c
    import ldpymod_d
    assert ldpymod_c.X == URIRef("http://c/x")
    assert not hasattr(ldpymod_d, "__namespaces__") or \
        "c" not in ldpymod_d.__namespaces__
