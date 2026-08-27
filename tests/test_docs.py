"""La documentation est exécutable : chaque bloc ``ldpy`` des pages de docs/
est transpilé PUIS EXÉCUTÉ ; chaque bloc ``python`` est exécuté. Un snippet
qui ne tourne pas ne peut pas rester dans la doc."""

import glob
import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = sorted(glob.glob(os.path.join(REPO, "docs", "**", "*.md"),
                        recursive=True))

FENCE = re.compile(r"^```(\w+)\n(.*?)^```", re.M | re.S)


def blocks(lang):
    out = []
    for path in DOCS:
        text = open(path, encoding="utf-8").read()
        for i, m in enumerate(FENCE.finditer(text)):
            if m.group(1) == lang:
                out.append(pytest.param(
                    m.group(2),
                    id="%s#%d" % (os.path.relpath(path, REPO), i)))
    return out


def test_docs_exist_and_cover_diataxis():
    rels = {os.path.relpath(p, os.path.join(REPO, "docs")) for p in DOCS}
    assert "README.md" in rels
    for quadrant in ("tutorials", "how-to", "reference", "explanation"):
        assert any(r.startswith(quadrant + os.sep) for r in rels), quadrant


@pytest.mark.parametrize("code", blocks("ldpy"))
def test_ldpy_snippets_run(code):
    from ldpy.transpiler import transpile
    result = transpile(code, "<docs>")
    exec(compile(result.code, "<docs>", "exec"), {"__name__": "docs"})


@pytest.mark.parametrize("code", blocks("python"))
def test_python_snippets_run(code):
    exec(compile(code, "<docs>", "exec"), {"__name__": "docs"})
