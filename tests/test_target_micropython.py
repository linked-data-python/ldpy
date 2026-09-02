"""The micropython target and the backend behind the façade.

Two optionals, on two axes (record ldpy/026):

* the BACKEND — rdflib on the host, urdflib on a device — is chosen by
  `ldpy.backend` from what is importable, and the generated code is the
  same on both;
* SPARQL QUERIES (`s{ }`) are a capability of the rdflib backend only.
  `--target micropython` refuses them at build time, on the host, where the
  message can be read; `e{ }` and `m{ }` are pure Python over the terms and
  stay.

The last test runs the emitted code on a real MicroPython, when one built
with urdflib is at hand (LDPY_MICROPYTHON, or `micropython` on the PATH).
"""

import os
import shutil
import subprocess
import sys

import pytest

from ldpy import backend
from ldpy.transpiler import transpile, LdpySyntaxError
from ldpy.build import bundle_device_runtime, DEVICE_RUNTIME

P = "@prefix ex: <http://example.org/> .\n"


def test_backend_is_rdflib_on_the_host():
    assert backend.NAME == "rdflib" and backend.HAS_SPARQL
    from ldpy import runtime
    assert runtime.URIRef("http://x") == backend.URIRef("http://x")
    assert isinstance(runtime.new_graph({}, None), backend.Graph)


def test_target_refuses_a_sparql_query_at_build_time():
    src = P + "@graph as g\nq = s{ SELECT ?s WHERE { ?s ?p ?o } }\n"
    transpile(src)                                    # the host accepts it
    with pytest.raises(LdpySyntaxError) as e:
        transpile(src, target="micropython")
    assert "s{ } is not available on the micropython target" in str(e.value)
    assert "m{ }" in str(e.value)                     # and says what to use


def test_target_keeps_expressions_patterns_and_graphs():
    src = (P + "@graph as g\n+{ ex:a ex:p 1 }\n"
           "adult = e{ ?age >= 18 }\n"
           "rows = m{ ?s ex:p ?o }\n"
           "h = g{ ex:b ex:q 2 }\n")
    assert transpile(src, target="micropython").code == transpile(src).code, \
        "the target changes what is refused, not what is emitted"


def test_unknown_target_is_an_error():
    with pytest.raises(ValueError):
        transpile("x = 1\n", target="esp8266")


def test_device_bundle_is_the_runtime_without_the_transpiler(tmp_path):
    written = bundle_device_runtime(str(tmp_path))
    names = sorted(os.path.basename(p) for p in written)
    assert names == sorted(("__init__.py",) + DEVICE_RUNTIME)
    init = (tmp_path / "ldpy" / "__init__.py").read_text()
    assert "transpiler" not in init.replace("the transpiler is not here", "")
    for name in DEVICE_RUNTIME:
        assert (tmp_path / "ldpy" / name).read_bytes() == \
            open(os.path.join(os.path.dirname(backend.__file__), name),
                 "rb").read()


def test_device_runtime_imports_no_rdflib_module_by_name():
    """What ships to the device must reach rdflib only through the backend."""
    here = os.path.dirname(backend.__file__)
    for name in ("runtime.py", "sparql.py"):
        text = open(os.path.join(here, name), encoding="utf-8").read()
        code = "\n".join(l for l in text.splitlines()
                         if not l.strip().startswith("#"))
        assert "import rdflib" not in code and "from rdflib" not in code, name


# ---------------------------------------------------------------- device

def _micropython():
    exe = os.environ.get("LDPY_MICROPYTHON") or shutil.which("micropython")
    if not exe:
        return None
    probe = subprocess.run([exe, "-c", "import urdflib"], capture_output=True)
    return exe if probe.returncode == 0 else None


DEVICE_PROGRAM = P + '''\
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

@graph as g
for i in range(3):
    +{ f<http://example.org/obs/{i}> a ex:Observation ;
           ex:value {i * 1.5}^^xsd:double ;
           ex:label {"n%d" % i}@en }
big = e{ ?v >= 1.5 }
kept = sorted(str(s) for s, v in m{ ?s ex:value ?v } if big({"v": v}))
print(len(g), kept)
print(sorted(str(o) + "@" + str(o.language) for s, o in m{ ?s ex:label ?o }))
print(sorted(row.s.n3() for row in m{ ?s ex:value ?v } if row.v.toPython() > 1))
ttl = g.serialize(format="turtle")
print("@prefix ex:" in ttl, "ex:Observation" in ttl)
'''


@pytest.mark.skipif(_micropython() is None,
                    reason="no MicroPython with urdflib (LDPY_MICROPYTHON)")
def test_the_same_program_runs_on_micropython(tmp_path):
    """Transpile on the host, run on the device — mode 1 of record
    micropython/304 — and get the answer the host gets."""
    out = tmp_path / "build"
    out.mkdir()
    bundle_device_runtime(str(out))
    result = transpile(DEVICE_PROGRAM, "device.ldpy", target="micropython")
    (out / "device.py").write_text(result.code)

    host = subprocess.run([sys.executable, "-c", result.code],
                          capture_output=True, text=True, check=True)
    env = dict(os.environ, MICROPYPATH=str(out))
    device = subprocess.run([_micropython(), str(out / "device.py")],
                            capture_output=True, text=True, env=env)
    assert device.returncode == 0, device.stderr
    assert device.stdout == host.stdout
    assert host.stdout.splitlines() == [
        "9 ['http://example.org/obs/1', 'http://example.org/obs/2']",
        "['n0@en', 'n1@en', 'n2@en']",
        "['<http://example.org/obs/1>', '<http://example.org/obs/2>']",
        "True True",
    ]
