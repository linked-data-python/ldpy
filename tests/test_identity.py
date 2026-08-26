"""Propriété d'identité : tout source Python pur ressort byte-identique
(aucun îlot -> aucun prélude, aucune réécriture)."""

import glob
import os

import pytest

from ldpy.transpiler import transpile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SNIPPETS = [
    "",
    "\n",
    "x = 1\n",
    "x = 1",                                   # sans newline final
    "a = b < c\n",
    "if a<b>c:\n    pass\n",                   # comparaison chaînée collée
    "r = d[i:j]\n",
    "r = d[i:j:k]\n",
    "m = {k: v for k, v in items}\n",
    "m = {a:1, b:2}\n",                        # dict collé, préfixes non déclarés
    "y = x @ w + b\n",                         # matmul
    "@decorator\ndef f():\n    pass\n",
    "@app.route('/x')\ndef h():\n    pass\n",
    "s = 'g{ pas un graphe }'\n",              # îlot dans une chaîne
    "s = \"@prefix ex: <http://e/> .\"\n",
    "s = f\"val {x!r:>{w}} fin\"\n",           # f-string avec format spec
    "s = f'{a}{b}' + rb'\\x00'\n",
    "t = '''multi\nligne <http://pas.un/iri>\n'''\n",
    "def f(x: int, *, y: str = 'a') -> bool:\n    return x < 2\n",
    "z = a if b else c\n",
    "l = [x for x in range(10) if x < 5]\n",
    "async def f():\n    await g()\n",
    "class A(B, metaclass=M):\n    pass\n",
    "n = 0x1f + 1e-5 + 1_000j + .5\n",
    "# commentaire avec <http://example.org/> et g{ }\n",
    "x = 1 \\\n    + 2\n",                     # continuation de ligne
    "s = 'a' 'b' 'c'\n",                       # concaténation implicite
    "print(a <= b, a >= b, a << 2, a != b)\n",
    "é = 1\nprint(é)\n",                       # identifiant unicode
    "x = y\nif x:\n    x -= 1\nelse:\n    x = None\n",
]


@pytest.mark.parametrize("src", SNIPPETS)
def test_snippet_identity(src):
    result = transpile(src, "<snippet>")
    assert result.code == src
    assert result.warnings == []


def _py_corpus():
    files = []
    for pattern in ("ldpy/transpiler/*.py", "ldpy/*.py", "tests/*.py"):
        files.extend(glob.glob(os.path.join(REPO, pattern)))
    return sorted(files)


@pytest.mark.parametrize("path", _py_corpus(), ids=os.path.basename)
def test_own_sources_identity(path):
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    result = transpile(src, path)
    assert result.code == src


def test_identity_single_copy_segment():
    src = "x = 1\ny = x + 2\n"
    result = transpile(src)
    kinds = [s.kind for s in result.map.segments]
    assert kinds == ["copy"]
    assert result.map.to_src(1, 4) == (1, 4)
    assert result.map.to_gen(0, 2) == (0, 2)
