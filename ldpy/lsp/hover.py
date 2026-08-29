"""Rendering the hover panel — record vscode/108.

Three blocks separated by rules, in the shape Python tooling has taught
people to read: a signature line, the description with a link to the
documentation, and the Python the transpiler produced. The translation can
be turned off (`ldpy.hover.showTranslation`); the first two blocks are what
tells you *what you are looking at*, so they always show.

Kept apart from `server.py`: rendering is a function of strings, and it is
tested as one.
"""

from ldpy.lsp import islanddoc

RULE = "\n\n---\n\n"


def format_python(code, line_length=88):
    """`code` through black, or unchanged when black cannot take it.

    What a hover shows is a FRAGMENT: the expression one term became, or the
    head of a statement the source splits in two (`for @bindings in`). Those
    are not modules, and black rightly refuses them. Showing the generated
    text as it stands beats showing nothing, so a refusal is silent.

    black normalises what it accepts — quotes above all — so the block is the
    translation *formatted*, not a byte-for-byte extract of the generated
    file. `ldpy -t` remains the place to read that.
    """
    code = code.strip()
    if not code:
        return code
    try:
        import black
    except ImportError:                                   # pragma: no cover
        return code
    try:
        return black.format_str(
            code, mode=black.Mode(line_length=line_length)).rstrip("\n")
    except Exception:
        return code


def render(kind, code, line_length=88, show_translation=True):
    """The markdown of a hover over an island element.

    `kind` is an island kind (with or without the `island:` prefix), `code`
    the Python it became. An unknown kind still renders: the table can lag
    the transpiler by a commit, and a hover must degrade rather than vanish.
    """
    doc = islanddoc.get(kind)
    blocks = []
    if doc is None:
        short = kind[len("island:"):] if kind.startswith("island:") else kind
        blocks.append("```ldpy\n(%s island)\n```" % short)
    else:
        blocks.append("```ldpy\n%s\n```" % doc.signature)
        blocks.append("%s [Documentation](%s)" % (doc.summary, doc.url))
    if show_translation and code and code.strip():
        blocks.append("```python\n%s\n```"
                      % format_python(code, line_length))
    return RULE.join(blocks)
