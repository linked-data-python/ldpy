"""Pygments lexer for Linked-Data Python.

The highlighter is the transpiler. Rather than re-specify the island triggers
in a third grammar (after the transpiler's scanner and the TextMate grammar of
the VS Code extension), this lexer transpiles the source, reads the resulting
:class:`~ldpy.transpiler.linemap.LanguageMap` — an ordered partition of the
source into ``copy`` and ``island:KIND`` segments — and colours each part:

* ``copy`` segments are handed to Pygments' own ``PythonLexer``;
* ``island:*`` segments are tokenised here, by kind, with ``{...}``
  interpolations handed back to ``PythonLexer`` in turn.

Islands therefore highlight exactly where the transpiler sees them: a
disambiguation rule that changes in ``DESIGN_CHOICES/ldpy/002`` changes the
colouring with no edit here. When the source does not transpile (an editor
buffer mid-keystroke, an illustrative snippet), the lexer degrades to plain
Python rather than guessing.

Only standard Pygments token types are emitted, following the conventions of
``pygments.lexers.rdf``, so that every Pygments style colours ldpy without a
custom stylesheet.
"""

import re

from pygments.lexer import Lexer
from pygments.lexers.python import PythonLexer
from pygments.token import (Comment, Keyword, Name, Number, Operator,
                            Punctuation, String, Text)

__all__ = ["LdpyLexer"]


# --------------------------------------------------------------- token choices
#
# Aligned with pygments.lexers.rdf (SparqlLexer) so that an ldpy island and a
# Turtle document look alike in the same page.

T_SIGIL = Keyword.Pseudo        # g{ f< e{ ?{ m{ s{ +{ -{ and their closers
T_DECL = Keyword.Declaration    # @prefix @base @graph @bindings
T_KW = Keyword                  # a, as, in, for, global, SELECT, WHERE...
T_IRI = Name.Label              # <http://...> and _:label
T_PREFIX = Name.Namespace       # the prefix part of a prefixed name
T_LOCAL = Name.Tag              # its local part
T_VAR = Name.Variable           # ?v $v
T_LANG = Name.Function          # the language tag of "x"@en
T_CONST = Keyword.Constant      # true false


# ------------------------------------------------------------------- utilities

_STRING_START = re.compile(r"""[rRbBuUfF]{0,3}('''|\"\"\"|'|")""")


def _skip_python_string(text, i):
    """Return the index just past the Python string literal starting at *i*."""
    m = _STRING_START.match(text, i)
    if not m:
        return None
    quote = m.group(1)
    j = m.end()
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text.startswith(quote, j):
            return j + len(quote)
        j += 1
    return len(text)


def _match_brace(text, i):
    """Index just past the ``}`` closing the ``{`` at *i*, brackets and Python
    strings respected. Returns ``len(text)`` if unterminated."""
    depth = 0
    j = i
    while j < len(text):
        c = text[j]
        if c in "\"'":
            nxt = _skip_python_string(text, j)
            j = nxt if nxt is not None else j + 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return len(text)


def _is_interpolation(body):
    """The transpiler's oracle for `{...}` inside s{ }: balanced content is a
    Python interpolation iff it transpiles and compiles as an expression. A
    SPARQL group never does."""
    body = body.strip()
    if not body:
        return False
    try:
        from ldpy.transpiler import transpile
        compile(transpile(body, "<pygments>").code, "<pygments>", "eval")
        return True
    except Exception:
        return False


def _line_offsets(text):
    offs, pos = [0], 0
    for line in text.splitlines(True):
        pos += len(line)
        offs.append(pos)
    return offs


# ------------------------------------------------------------- island scanning
#
# One tokeniser, three flavours. The term rules are shared because the term
# syntax is shared: g{ } and m{ } hold the same text and differ by operator
# (DESIGN_CHOICES/ldpy/016), and s{ } adds SPARQL keywords on top.

_SPARQL_KEYWORDS = frozenset("""
select construct describe ask where from named order by group having limit
offset distinct reduced optional union minus filter bind values service graph
as insert delete data with using clear drop create load into silent to copy
move add default all undef exists not in prefix base
""".split())

_EXPR_FUNCTIONS = frozenset("""
str lang datatype iri uri bnode strdt strlang uuid struuid bound coalesce if
sameterm isiri isuri isblank isliteral isnumeric regex substr replace strlen
ucase lcase strstarts strends contains strbefore strafter encode_for_iri
concat langmatches abs round ceil floor rand now year month day hours minutes
seconds timezone tz md5 sha1 sha256 sha384 sha512 count sum min max avg
group_concat sample separator
""".split())

_RE_WS = re.compile(r"[ \t\r\n]+")
_RE_COMMENT = re.compile(r"#[^\n]*")
_RE_IRIREF = re.compile(r"<[^<>\"{}|^`\\\x00-\x20]*>")
_RE_BNODE = re.compile(r"_:[^\s;,.\]\)}]*")
_RE_VAR = re.compile(r"[?$][A-Za-z_·À-￿][\w·À-￿]*")
_RE_PNAME = re.compile(r"([\wÀ-￿][-\w.·À-￿]*)?(:)"
                       r"([\w·À-￿%\\][-\w.·À-￿%\\]*)?")
_RE_NUMBER = re.compile(r"[+-]?(\d+\.\d*[eE][+-]?\d+|\.\d+[eE][+-]?\d+"
                        r"|\d+[eE][+-]?\d+|\d+\.\d*|\.\d+|\d+)")
_RE_NAME = re.compile(r"[A-Za-z_]\w*")
_RE_STRING = re.compile(r"[frbFRB]{0,2}('''|\"\"\"|'|\")")
_RE_LANG = re.compile(r"@[A-Za-z]+(-[A-Za-z0-9]+)*")
_RE_OP = re.compile(r"\|\||&&|<=|>=|!=|\^\^|[=<>+\-*/!]")
_RE_PUNCT = re.compile(r"[;,.\[\]()]")


def _string_end(text, i):
    m = _RE_STRING.match(text, i)
    quote = m.group(1)
    j = m.end()
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text.startswith(quote, j):
            return j + len(quote)
        j += 1
    return len(text)


class _IslandScanner:
    """Tokenise the body of an island. ``flavour`` is ``turtle`` (g/m/+/-),
    ``sparql`` (s{ }) or ``expr`` (e{ } and the holes of e< >)."""

    def __init__(self, python_lexer):
        self.python = python_lexer

    def python_chunk(self, text, start, end, offset):
        """Yield the Python expression ``text[start:end]`` through PythonLexer."""
        for idx, ttype, value in self.python.get_tokens_unprocessed(
                text[start:end]):
            yield offset + start + idx, ttype, value

    def scan(self, text, offset=0, flavour="turtle"):
        i, n = 0, len(text)
        while i < n:
            c = text[i]

            m = _RE_WS.match(text, i)
            if m:
                yield offset + i, Text, m.group(0)
                i = m.end()
                continue

            if c == "#":
                m = _RE_COMMENT.match(text, i)
                yield offset + i, Comment.Single, m.group(0)
                i = m.end()
                continue

            # a nested island: e{ ... } in term position (fiche 017)
            if text.startswith("e{", i) or text.startswith("f{", i) \
                    or text.startswith("?{", i):
                end = _match_brace(text, i + 1)
                yield offset + i, T_SIGIL, text[i:i + 2]
                if text[i] == "e":
                    yield from self.scan(text[i + 2:end - 1],
                                         offset + i + 2, "expr")
                else:
                    yield from self.python_chunk(text, i + 2, end - 1, offset)
                yield offset + end - 1, T_SIGIL, text[end - 1:end]
                i = end
                continue

            if text.startswith("e<", i) or text.startswith("f<", i):
                end = text.find(">", i)
                end = n if end < 0 else end + 1
                yield offset + i, T_SIGIL, text[i:i + 2]
                yield from self._firi_body(text, i + 2, end - 1, offset)
                yield offset + end - 1, T_SIGIL, text[end - 1:end]
                i = end
                continue

            # a Python interpolation, in any term position. In s{ }, `{` is
            # ambiguous with a SPARQL group; the transpiler settles it with an
            # oracle (fiche 015) — balanced content is an interpolation iff it
            # transpiles then compiles as an expression. We ask the same.
            if c == "{":
                end = _match_brace(text, i)
                if flavour == "sparql" and not _is_interpolation(
                        text[i + 1:end - 1]):
                    yield offset + i, Punctuation, "{"
                    i += 1
                    continue
                yield offset + i, Punctuation, "{"
                yield from self.python_chunk(text, i + 1, end - 1, offset)
                yield offset + end - 1, Punctuation, "}"
                i = end
                continue

            if c == "}":            # a SPARQL group, in s{ } bodies
                yield offset + i, Punctuation, "}"
                i += 1
                continue

            m = _RE_IRIREF.match(text, i)
            if m:
                yield offset + i, T_IRI, m.group(0)
                i = m.end()
                continue

            if text.startswith("_:{", i):        # data-keyed blank node
                end = _match_brace(text, i + 2)
                yield offset + i, T_IRI, "_:"
                yield offset + i + 2, Punctuation, "{"
                yield from self.python_chunk(text, i + 3, end - 1, offset)
                yield offset + end - 1, Punctuation, "}"
                i = end
                continue

            m = _RE_BNODE.match(text, i)
            if m:
                yield offset + i, T_IRI, m.group(0)
                i = m.end()
                continue

            m = _RE_VAR.match(text, i)
            if m:
                yield offset + i, T_VAR, m.group(0)
                i = m.end()
                continue

            m = _RE_STRING.match(text, i)
            if m:
                end = _string_end(text, i)
                if m.group(0)[:-len(m.group(1))].lower().find("f") >= 0:
                    yield from self._fstring(text, i, end, offset)
                else:
                    yield offset + i, String, text[i:end]
                i = end
                continue

            m = _RE_NUMBER.match(text, i)
            if m and (c.isdigit() or (c in "+-." and flavour != "expr")
                      or (c == "." and text[i:i + 2] != "..")):
                if c not in "+-" or flavour == "turtle":
                    yield offset + i, Number, m.group(0)
                    i = m.end()
                    continue

            m = _RE_PNAME.match(text, i)
            if m and m.group(2) and (m.group(1) or m.group(3)
                                     or flavour == "turtle"):
                if m.group(1):
                    yield offset + i, T_PREFIX, m.group(1)
                yield offset + m.start(2), Punctuation, ":"
                if m.group(3):
                    yield offset + m.start(3), T_LOCAL, m.group(3)
                i = m.end()
                # ex:{expr} — an interpolated local part
                if i < n and text[i] == "{":
                    end = _match_brace(text, i)
                    yield offset + i, Punctuation, "{"
                    yield from self.python_chunk(text, i + 1, end - 1, offset)
                    yield offset + end - 1, Punctuation, "}"
                    i = end
                continue

            m = _RE_LANG.match(text, i)
            if m:
                yield offset + i, Operator, "@"
                yield offset + i + 1, T_LANG, m.group(0)[1:]
                i = m.end()
                continue

            m = _RE_NAME.match(text, i)
            if m:
                word, low = m.group(0), m.group(0).lower()
                if word == "a" and flavour != "expr":
                    tok = T_KW
                elif low in ("true", "false"):
                    tok = T_CONST
                elif flavour == "sparql" and low in _SPARQL_KEYWORDS:
                    tok = T_KW
                elif low in _EXPR_FUNCTIONS and text[m.end():m.end() + 1] == "(":
                    tok = Name.Builtin
                elif flavour == "expr" and low in ("if", "else"):
                    tok = T_KW
                else:
                    tok = Name
                yield offset + i, tok, word
                i = m.end()
                continue

            m = _RE_OP.match(text, i)
            if m:
                yield offset + i, Operator, m.group(0)
                i = m.end()
                continue

            m = _RE_PUNCT.match(text, i)
            if m:
                yield offset + i, Punctuation, m.group(0)
                i = m.end()
                continue

            yield offset + i, Text, c
            i += 1

    def _fstring(self, text, start, end, offset):
        """An f-string in term position: colour its holes as Python."""
        i = start
        while i < end:
            j = text.find("{", i, end)
            if j < 0:
                yield offset + i, String, text[i:end]
                return
            if text.startswith("{{", j):
                yield offset + i, String, text[i:j + 2]
                i = j + 2
                continue
            if j > i:
                yield offset + i, String, text[i:j]
            k = min(_match_brace(text, j), end)
            yield offset + j, String.Interpol, "{"
            yield from self.python_chunk(text, j + 1, k - 1, offset)
            yield offset + k - 1, String.Interpol, "}"
            i = k

    def _firi_body(self, text, start, end, offset):
        """The body of f<...> / e<...>: literal IRI text with {holes}."""
        i = start
        while i < end:
            j = text.find("{", i, end)
            if j < 0:
                yield offset + i, T_IRI, text[i:end]
                return
            if j > i:
                yield offset + i, T_IRI, text[i:j]
            k = min(_match_brace(text, j), end)
            yield offset + j, Punctuation, "{"
            body = text[j + 1:k - 1]
            if body.lstrip()[:1] in ("?", "$"):          # e< > holds SPARQL
                yield from self.scan(body, offset + j + 1, "expr")
            else:
                yield from self.python_chunk(text, j + 1, k - 1, offset)
            yield offset + k - 1, Punctuation, "}"
            i = k


# --------------------------------------------------------------- island kinds

#: Island kinds whose text is delimited by a sigil, with the flavour of their
#: body. Kinds absent from this table are lexed as declarations.
_DELIMITED = {
    "graph": ("g{", "}", "turtle"),
    "match": ("m{", "}", "turtle"),
    "addto": ("+{", "}", "turtle"),
    "removefrom": ("-{", "}", "turtle"),
    "sparql": ("s{", "}", "sparql"),
    "enode": ("e{", "}", "expr"),
    "fnode": (None, "}", "python"),        # f{ or ?{
}

_DECL_KEYWORDS = frozenset(("global", "nonlocal", "as", "in", "for", "from",
                            "import"))


class LdpyLexer(Lexer):
    """Lexer for Linked-Data Python (``.ldpy``) sources."""

    name = "Linked-Data Python"
    aliases = ["ldpy", "linked-data-python"]
    filenames = ["*.ldpy"]
    mimetypes = ["text/x-ldpy"]
    url = "https://linked-data-python.readthedocs.io/"

    def __init__(self, **options):
        Lexer.__init__(self, **options)
        self.python = PythonLexer(**options)
        self.scanner = _IslandScanner(self.python)

    # -- entry point ---------------------------------------------------------

    def get_tokens_unprocessed(self, text):
        try:
            from ldpy.transpiler import transpile
            segments = transpile(text, "<pygments>").map.segments
        except Exception:               # not ldpy, or not yet valid: plain Python
            yield from self.python.get_tokens_unprocessed(text)
            return

        offs = _line_offsets(text)

        def abs_pos(line, col):
            return min(offs[line] + col, len(text)) if line < len(offs) \
                else len(text)

        pos = 0
        for seg in segments:
            if seg.src is None:                     # synthetic prelude
                continue
            start, end = abs_pos(seg.src[0], seg.src[1]), \
                abs_pos(seg.src[2], seg.src[3])
            if end <= pos:
                continue
            start = max(start, pos)
            if start > pos:                         # never lose a character
                yield pos, Text, text[pos:start]
            chunk = text[start:end]
            if seg.kind == "copy":
                for idx, ttype, value in \
                        self.python.get_tokens_unprocessed(chunk):
                    yield start + idx, ttype, value
            else:
                yield from self._island(seg.kind[len("island:"):], chunk, start)
            pos = end
        if pos < len(text):
            yield pos, Text, text[pos:]

    # -- islands -------------------------------------------------------------

    def _island(self, kind, text, offset):
        if kind in _DELIMITED:
            yield from self._delimited(kind, text, offset)
        elif kind in ("firi", "eiri"):
            yield offset, T_SIGIL, text[:2]
            yield from self.scanner._firi_body(text, 2, len(text) - 1, offset)
            yield offset + len(text) - 1, T_SIGIL, text[-1:]
        elif kind == "iri":
            yield offset, T_IRI, text
        elif kind == "var":
            yield offset, T_VAR, text
        elif kind in ("pname", "literal"):
            yield from self.scanner.scan(text, offset, "turtle")
        else:
            yield from self._declaration(text, offset)

    def _delimited(self, kind, text, offset):
        opener, closer, flavour = _DELIMITED[kind]
        head = len(opener) if opener else 2         # f{ / ?{ are two characters
        yield offset, T_SIGIL, text[:head]
        body_end = len(text) - len(closer) if text.endswith(closer) \
            else len(text)
        if flavour == "python":
            yield from self.scanner.python_chunk(text, head, body_end, offset)
        else:
            yield from self.scanner.scan(text[head:body_end],
                                         offset + head, flavour)
        if body_end < len(text):
            yield offset + body_end, T_SIGIL, text[body_end:]

    def _declaration(self, text, offset):
        """@prefix / @base / @graph / @bindings / for @bindings / prefix
        imports: Python-ish words plus RDF terms."""
        i, n = 0, len(text)
        while i < n:
            c = text[i]
            m = _RE_WS.match(text, i)
            if m:
                yield offset + i, Text, m.group(0)
                i = m.end()
                continue
            if c == "@":
                m = _RE_NAME.match(text, i + 1)
                if m:
                    yield offset + i, T_DECL, text[i:m.end()]
                    i = m.end()
                    continue
            if text.startswith("f<", i) or text.startswith("e<", i):
                end = text.find(">", i)
                end = n if end < 0 else end + 1
                yield offset + i, T_SIGIL, text[i:i + 2]
                yield from self.scanner._firi_body(text, i + 2, end - 1, offset)
                yield offset + end - 1, T_SIGIL, text[end - 1:end]
                i = end
                continue
            m = _RE_IRIREF.match(text, i)
            if m:
                yield offset + i, T_IRI, m.group(0)
                i = m.end()
                continue
            m = _RE_PNAME.match(text, i)
            if m and m.group(2) and (m.group(1) or m.group(3)):
                if m.group(1):
                    yield offset + i, T_PREFIX, m.group(1)
                yield offset + m.start(2), Punctuation, ":"
                if m.group(3):
                    yield offset + m.start(3), T_LOCAL, m.group(3)
                i = m.end()
                continue
            m = _RE_NAME.match(text, i)
            if m:
                word = m.group(0)
                tok = T_KW if word in _DECL_KEYWORDS else Name
                yield offset + i, tok, word
                i = m.end()
                continue
            m = _RE_PUNCT.match(text, i)
            if m or c == ":":
                yield offset + i, Punctuation, m.group(0) if m else c
                i = m.end() if m else i + 1
                continue
            yield offset + i, Text, c
            i += 1
