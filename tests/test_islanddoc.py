"""The hover documentation table is complete, and its links are alive.

Two guards, and they matter for different reasons. The first stops the table
from falling behind the language: a new island kind in the transpiler has to
be described before the suite goes green again. The second stops the links
from rotting: a hover that points at an anchor `docs/` no longer has is worse
than a hover with no link, because a user follows it and lands nowhere while
nothing reports the breakage.
"""

import re
from pathlib import Path

import pytest

from ldpy.lsp.islanddoc import ISLANDS, get
from ldpy.lsp.translate import _KIND_TO_TYPE

CORE = Path(__file__).resolve().parent.parent / "ldpy" / "transpiler" / "core.py"
DOCS = Path(__file__).resolve().parent.parent / "docs"


def transpiler_kinds():
    """Every island kind the transpiler can emit, read off its source.

    Read rather than declared: a list maintained by hand would drift, and
    drifting silently is exactly what this test exists to prevent."""
    text = CORE.read_text(encoding="utf-8")
    kinds = set()
    # the kind argument is sometimes a conditional expression, so collect
    # every literal between `_end_island(` and the `mark` that follows it
    for arg in re.findall(r"_end_island\((.{0,140}?)mark", text, re.S):
        kinds.update(re.findall(r'"([a-z-]+)"', arg))
    # `@prefix`/`@base` share one call site, on a `kind` variable
    kinds |= {"prefix", "base"}
    return kinds


def test_every_island_kind_is_documented():
    missing = sorted(transpiler_kinds() - set(ISLANDS))
    assert not missing, "island kinds with no hover documentation: %s" % missing


def test_no_documentation_for_a_kind_that_does_not_exist():
    extra = sorted(set(ISLANDS) - transpiler_kinds())
    assert not extra, "documented kinds the transpiler never emits: %s" % extra


def test_semantic_tokens_cover_the_same_kinds():
    """The two tables name the same islands: one colours them, one explains
    them, and a kind in neither is a kind the tooling forgot."""
    tokens = {k[len("island:"):] for k in _KIND_TO_TYPE}
    assert tokens == set(ISLANDS)


def test_get_accepts_both_spellings_and_never_raises():
    assert get("pname") is get("island:pname")
    assert get("no-such-island") is None


@pytest.mark.parametrize("kind", sorted(ISLANDS))
def test_signature_and_summary_are_reasonable(kind):
    doc = ISLANDS[kind]
    assert doc.signature.startswith("("), doc.signature
    assert "\n" not in doc.signature
    # as verbose as a builtin's docstring, and no more (record vscode/108)
    assert 60 <= len(doc.summary) <= 460, len(doc.summary)


def _slugs(md):
    """The anchors mkdocs generates for a page, by its own slugifier."""
    from markdown.extensions.toc import slugify
    out = set()
    for line in md.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#{1,6}\s+(.*?)\s*$", line)
        if m:
            out.add(slugify(re.sub(r"`([^`]*)`", r"\1", m.group(1)), "-"))
    return out


@pytest.mark.parametrize("kind", sorted(ISLANDS))
def test_documentation_link_resolves(kind):
    pytest.importorskip("markdown")
    doc = ISLANDS[kind]
    page = DOCS / doc.page
    assert page.exists(), "%s: no such page %s" % (kind, doc.page)
    slugs = _slugs(page)
    assert doc.anchor in slugs, (
        "%s: %s has no anchor '%s' (has %s)"
        % (kind, doc.page, doc.anchor, sorted(slugs)))
