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
            if m.group(1) == lang and not _is_snippet(m.group(2)):
                out.append(pytest.param(
                    m.group(2),
                    id="%s#%d" % (os.path.relpath(path, REPO), i)))
    return out


def _is_snippet(code):
    """A block that only includes a file (``--8<-- "..."``) has no code of its
    own: mkdocs substitutes the file at build time, and that file is tested
    where it lives — see ``test_the_tour_runs``."""
    return all(line.strip().startswith("--8<--") or not line.strip()
               for line in code.split("\n"))


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


def test_the_tour_runs():
    """``docs/tutorials/tour.ldpy`` is a tutorial in the shape of a program:
    its comments teach, and each section asserts what it claims. Running it is
    therefore the whole check — and the page that shows it includes this very
    file, so the two cannot drift."""
    from ldpy.transpiler import transpile
    path = os.path.join(REPO, "docs", "tutorials", "tour.ldpy")
    source = open(path, encoding="utf-8").read()
    exec(compile(transpile(source, path).code, path, "exec"),
         {"__name__": "tour"})


# --------------------------------------------------------------------------
# The same snippets, typed into the interactive console.
#
# The console transpiles ONE ENTRY AT A TIME: what a file keeps in a single
# pass (the current @prefix, @graph, @bindings) has to survive from one entry
# to the next. A doc snippet that runs as a file but not in the console is a
# console bug, not a doc bug — hence this second pass over the same blocks.
# --------------------------------------------------------------------------

def _pasteable(code):
    """A basic Python console (`code.InteractiveConsole`, what we build on)
    ends a block on a blank line and has no bracketed paste. Blocks that
    depend on either are out of scope here — CPython's own REPL is no
    better."""
    if '"""' in code or "'''" in code:
        return False
    lines = code.splitlines()
    for i, line in enumerate(lines):
        if line.strip():
            continue
        following = next((x for x in lines[i + 1:] if x.strip()), "")
        if following.startswith((" ", "\t")):
            return False            # blank line inside a block
    return True


def _console_output(code):
    """Feed a snippet line by line, as one would type it; return everything
    the console reported (errors and warnings)."""
    import contextlib
    import io
    from ldpy.console import LdpyConsole

    console = LdpyConsole()
    reported = io.StringIO()
    console.write = reported.write
    lines = code.splitlines() + [""]
    for line in lines:
        # dedenting to column 0 closes the block above, as typing does
        if console.buffer and line[:1] not in (" ", "\t", ""):
            console.push("")
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(reported):
            console.push(line)
    return reported.getvalue()


@pytest.mark.parametrize("code", blocks("ldpy"))
def test_ldpy_snippets_run_in_the_console(code):
    if not _pasteable(code):
        pytest.skip("block relies on paste, not on typing")
    reported = _console_output(code)
    errors = [ligne for ligne in reported.splitlines()
              if ligne.strip() and "LdpyWarning" not in ligne]
    assert not errors, "\n".join(errors)
