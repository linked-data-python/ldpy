"""Pygments lexer for Linked-Data Python.

Two ideas, and almost no third one.

**The highlighter is the transpiler.** Rather than re-specify the island
triggers in a third grammar (after the transpiler's scanner and the TextMate
grammar of the VS Code extension), this lexer transpiles the source and reads
the resulting :class:`~ldpy.transpiler.linemap.LanguageMap` — an ordered
partition of the file into ``copy`` and ``island:KIND`` segments. Islands
therefore highlight exactly where the transpiler sees them: a disambiguation
rule that changes in ``DESIGN_CHOICES/ldpy/002`` changes the colouring with no
edit here.

**The tokenising is Pygments'.** Nothing here re-describes Python, Turtle or
SPARQL:

* ``copy`` segments and every ``{expr}`` interpolation go to ``PythonLexer``;
* ``@prefix`` / ``@base`` are Turtle's own directives, and go to
  ``TurtleLexer``;
* island bodies go to ``SparqlLexer``. A ``g{ }``, ``m{ }``, ``+{ }`` or
  ``-{ }`` body is Turtle *with variables*, which is precisely SPARQL's
  triples block — ``TurtleLexer`` rejects ``?s``, ``SparqlLexer`` does not.

What is written here is only what no existing lexer can know: where the
islands are (the map answers that), the ldpy-only declarations (``@graph``,
``@bindings``, prefix imports), and the *masking* that lets a delegated lexer
see a well-formed document — each ldpy-specific region is replaced by a
placeholder of the same length that is a valid term where it stands, then the
real text is lexed back in at that position.

When the source does not transpile — an editor buffer mid-keystroke, an
illustrative snippet — the lexer degrades to plain Python rather than guessing.

Pygments is an optional dependency: ``pip install linked-data-python[highlight]``
(and it comes with the ``docs`` extra). Nothing else in ldpy imports this
module; Pygments loads it through an entry point when it is installed.
"""

try:
    from pygments.lexer import Lexer
    from pygments.lexers.python import PythonLexer
    from pygments.lexers.rdf import SparqlLexer, TurtleLexer
    from pygments.token import (Comment, Error, Generic, Keyword, Name, Number,
                                Operator, Punctuation, String, Text)
except ImportError as exc:                                   # pragma: no cover
    raise ImportError(
        "the ldpy Pygments lexer needs Pygments: "
        "pip install linked-data-python[highlight]") from exc

__all__ = ["LdpyLexer"]


# --------------------------------------------------------------- token choices
#
# Only STANDARD Pygments token types, so that every style colours ldpy with no
# extra stylesheet — but not always the ones pygments.lexers.rdf picks:
# mkdocs-material collapses Name.Label, Name.Tag, Keyword and Keyword.Pseudo
# onto ONE colour, which would make IRIs and local names indistinguishable from
# keywords. The delegated lexers' tokens are remapped (see _REMAP_*) so that
# these eight roles land on eight colours:
#
#   keyword     sigils, declarations, `a`, SPARQL keywords
#   string      IRIs, blank-node labels, RDF literals
#   function    prefixed names
#   variable    ?v $v
#   constant    SPARQL built-ins and language tags
#   number / operator / punctuation / comment as usual

T_SIGIL = Keyword.Pseudo        # g{ f< e{ ?{ m{ s{ +{ -{ and their closers
T_DECL = Keyword.Declaration    # @prefix @base @graph @bindings
T_KW = Keyword                  # a, as, in, for, global, SELECT, WHERE...
T_IRI = String.Symbol           # <http://...> and _:label
T_PREFIX = Name.Namespace       # the prefix part of a prefixed name
T_LOCAL = Name.Class            # its local part
T_VAR = Name.Variable           # ?v $v
T_LANG = Name.Builtin           # the language tag of "x"@en
T_CONST = Keyword.Constant      # true false

#: SparqlLexer → the palette above. Everything absent passes through.
_REMAP_SPARQL = {
    Name.Label: T_IRI,              # IRIREF and BLANK_NODE_LABEL
    Name.Tag: T_LOCAL,              # local part of a prefixed name
    Name.Function: T_LANG,          # language tags *and* built-in functions
    Keyword.Type: T_KW,
}

#: TurtleLexer → the same palette (it spells IRIREF Name.Variable).
_REMAP_TURTLE = {
    Name.Variable: T_IRI,
    Name.Label: T_IRI,
    Name.Tag: T_LOCAL,
    Generic.Emph: T_LANG,           # language tag
    Keyword.Type: T_KW,
    Keyword: T_DECL,                # @prefix / @base
}


# ------------------------------------------------------------------- utilities

import re                                                       # noqa: E402

_STRING_START = re.compile(r"""[rRbBuUfF]{0,3}('''|\"\"\"|'|")""")
_PNAME_TAIL = re.compile(r"[\wÀ-￿][-\w.·À-￿]*:"
                         r"[\w·À-￿%\\][-\w.·À-￿%\\]*$")
_PNAME_COLON = re.compile(r"[\wÀ-￿][-\w.·À-￿]*:$")


def _skip_string(text, i):
    """Index just past the string literal starting at *i*, or None."""
    m = _STRING_START.match(text, i)
    if not m:
        return None
    quote, j = m.group(1), m.end()
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
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c in "\"'":
            nxt = _skip_string(text, j)
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
    """The transpiler's oracle for `{...}` inside s{ } (fiche 015): balanced
    content is a Python interpolation iff it transpiles and compiles as an
    expression. A SPARQL group never does."""
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


# ----------------------------------------------------------------- delegation

def _delegate(sub, remap, text, offset, regions):
    """Lex *text* with the *sub* Pygments lexer, remapping its token types and
    splicing the ldpy *regions* back in.

    ``regions`` is a list of ``(start, end, emit)``; ``emit(offset)`` yields the
    tokens of that region. The text handed to *sub* has each region replaced by
    a same-length placeholder, so positions are preserved exactly."""
    masked = list(text)
    for start, end, _ in regions:
        masked[start:end] = _placeholder(text, start, end)
    masked = "".join(masked)
    assert len(masked) == len(text)

    spans = [(s, e) for s, e, _ in regions]
    pieces = []
    for start, end, emit in regions:
        pieces.extend(emit(offset))
    for idx, ttype, value in sub.get_tokens_unprocessed(masked):
        ttype = remap.get(ttype, ttype)
        s, e = idx, idx + len(value)
        while s < e:
            covering = next(((a, b) for a, b in spans if a <= s < b), None)
            if covering:
                s = covering[1]
                continue
            nxt = min([a for a, b in spans if a > s] + [e])
            pieces.append((offset + s, ttype, text[s:min(e, nxt)]))
            s = min(e, nxt)
    pieces.sort(key=lambda p: p[0])
    return pieces


def _placeholder(text, start, end):
    """A same-length stand-in that the delegated lexer accepts as a term where
    the real region stands."""
    n = end - start
    glued = text[:start]                     # NO rstrip: adjacency matters
    if _PNAME_COLON.search(glued[-64:]):
        return "x" * n                       # ex:{expr} -> ex:xxxxx
    if text.startswith("_:", start):
        return "_:" + "x" * (n - 2)          # _:{expr}  -> _:xxxxx
    if glued.endswith("^^") or (text[start] in "fe" and n > 2
                                and text[start + 1] == "<"):
        return "<" + "x" * (n - 2) + ">"     # an IRI where an IRI fits
    return '"' + "x" * (n - 2) + '"' if n >= 2 else "x" * n


# ------------------------------------------------------------- island scanning

_DELIMITED = {                       # kind -> (opener length, closer, flavour)
    "graph": (2, "}", "sparql"),
    "match": (2, "}", "sparql"),
    "addto": (2, "}", "sparql"),
    "removefrom": (2, "}", "sparql"),
    "sparql": (2, "}", "sparql"),
    "enode": (2, "}", "sparql"),
    "fnode": (2, "}", "python"),     # f{ or ?{
}

_DECL_KEYWORDS = frozenset(("global", "nonlocal", "as", "in", "for", "from",
                            "import"))
_RE_WS = re.compile(r"[ \t\r\n]+")
_RE_NAME = re.compile(r"[A-Za-z_]\w*")
_RE_IRIREF = re.compile(r"<[^<>\"{}|^`\\\x00-\x20]*>")
_RE_PNAME = re.compile(r"([\wÀ-￿][-\w.·À-￿]*)?(:)"
                       r"([\w·À-￿%\\][-\w.·À-￿%\\]*)?")
_RE_PUNCT = re.compile(r"[;,.\[\]():]")


#: A snippet is rarely a whole module. Documentation and papers show
#: `g{ ex:s ex:p 1 }` without the `@prefix` line that makes it legal, and the
#: transpiler — rightly — refuses it. Rather than fall back to plain Python
#: (which paints `ex:` and `?s` bright red), the lexer DECLARES what the
#: fragment is missing and tries again: the snippet then colours exactly as
#: the same lines would inside a complete file.
_UNDECLARED = re.compile(
    r"préfixe non déclaré\s*:\s*'([^':]*):'"
    r"|[Uu]nknown namespace prefix\s*:\s*(\S*)")

#: The declaration a fragment is missing, read off the error it raised. Only
#: errors that a DECLARATION can repair are listed: a snippet that is actually
#: ill-formed must keep failing, and fall through to plain Python.
_NO_CURRENT_GRAPH = re.compile(r"sans graphe courant")

#: Enough for any realistic snippet; the bound is what keeps a pathological
#: input from looping.
_MAX_SYNTHETIC = 24

#: Namespace of the synthetic prefixes. Never resolved — the map is thrown
#: away after the tokens are read — but it has to be a legal IRI.
_SYNTHETIC_NS = "urn:x-ldpy-highlight:"


def _synthetic_declaration(exc):
    """The declaration line that would let *exc* go away, or None."""
    m = _UNDECLARED.search(str(exc))
    if m is not None:
        prefix = (m.group(1) if m.group(1) is not None else m.group(2)).strip()
        return f"@prefix {prefix}: <{_SYNTHETIC_NS}{prefix or 'default'}#> ."
    if _NO_CURRENT_GRAPH.search(str(exc)):
        return "@graph as _ldpy_highlight_graph"
    return None


def _transpile_for_display(text):
    """``(segments, preamble)`` — the language map of *text*, possibly read
    under a synthetic preamble that declares the prefixes it never declared.

    The preamble is prepended, so every coordinate it produces is shifted by
    ``len(preamble)``; the caller subtracts it. Raises whatever the transpiler
    raises when no preamble can help."""
    from ldpy.transpiler import transpile
    preamble = ""
    seen = set()
    while True:
        try:
            return transpile(preamble + text, "<pygments>").map.segments, preamble
        except Exception as exc:
            line = _synthetic_declaration(exc)
            if line is None or line in seen or len(seen) >= _MAX_SYNTHETIC:
                raise
            seen.add(line)
            preamble += line + "\n"


def _without_errors(python, text):
    """*text* through PythonLexer, with ``Token.Error`` flattened to text.

    Last resort: the fragment is not ldpy the transpiler can read, even with a
    preamble. Whatever it is, painting it in error red is a worse answer than
    painting it plainly — the highlighter is not the place where a syntax
    error gets reported."""
    for idx, ttype, value in python.get_tokens_unprocessed(text):
        yield idx, (Text if ttype is Error else ttype), value


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
        self.turtle = TurtleLexer(**options)
        self.sparql = SparqlLexer(**options)

    # -- entry point ---------------------------------------------------------

    def get_tokens_unprocessed(self, text):
        try:
            segments, preamble = _transpile_for_display(text)
        except Exception:            # not ldpy, or not yet valid: plain Python
            yield from _without_errors(self.python, text)
            return

        shift = len(preamble)
        offs = _line_offsets(preamble + text)
        limit = shift + len(text)

        def abs_pos(line, col):
            at = min(offs[line] + col, limit) if line < len(offs) else limit
            return at - shift

        pos = 0
        for seg in segments:
            if seg.src is None:                     # synthetic prelude
                continue
            end = abs_pos(seg.src[2], seg.src[3])
            if end <= pos:                          # inside the preamble
                continue
            start = max(abs_pos(seg.src[0], seg.src[1]), pos)
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
        elif kind in ("prefix", "base"):
            # Turtle's own directives, lexed by Turtle's own lexer
            yield from _delegate(self.turtle, _REMAP_TURTLE, text, offset,
                                 self._regions(text, "turtle"))
        elif kind in ("firi", "eiri"):
            yield offset, T_SIGIL, text[:2]
            yield from self._firi_body(text, 2, len(text) - 1, offset)
            yield offset + len(text) - 1, T_SIGIL, text[-1:]
        elif kind in ("iri", "var", "pname", "literal"):
            yield from _delegate(self.sparql, _REMAP_SPARQL, text, offset,
                                 self._regions(text, "sparql"))
        else:                        # @graph, @bindings, for @bindings, import
            yield from self._declaration(text, offset)

    def _delimited(self, kind, text, offset):
        head, closer, flavour = _DELIMITED[kind]
        yield offset, T_SIGIL, text[:head]
        # the island ends at the brace matching its opener; a call suffix
        # (fiche 019) may follow, and that is ordinary Python
        close = _match_brace(text, head - 1) - 1
        body_end = close if 0 <= close < len(text) and text[close] == closer \
            else (len(text) - len(closer) if text.endswith(closer)
                  else len(text))
        if flavour == "python":
            yield from self._python_chunk(text, head, body_end, offset)
        else:
            body = text[head:body_end]
            yield from _delegate(self.sparql, _REMAP_SPARQL, body,
                                 offset + head,
                                 self._regions(body, "sparql", is_query=(
                                     kind == "sparql")))
        if body_end < len(text):
            yield offset + body_end, T_SIGIL, text[body_end:body_end + 1]
            if body_end + 1 < len(text):              # the call suffix
                for idx, ttype, value in self.python.get_tokens_unprocessed(
                        text[body_end + 1:]):
                    yield offset + body_end + 1 + idx, ttype, value

    # -- the ldpy-specific regions of an island body -------------------------

    def _regions(self, text, flavour, is_query=False):
        """Locate what no Turtle or SPARQL lexer can read: interpolations and
        nested islands. Each becomes a (start, end, emit) region."""
        regions = []
        i, n = 0, len(text)
        while i < n:
            c = text[i]
            if c == "#":                                  # comment: sub-lexer
                i = text.find("\n", i)
                if i < 0:
                    break
                continue
            if c in "\"'" or (c in "fFrRbB" and i + 1 < n
                              and text[i + 1] in "\"'"):
                end = _skip_string(text, i)
                if end is None:
                    i += 1
                    continue
                if text[i] in "fF":                       # f-string: has holes
                    regions.append((i, end, self._emit_fstring(text, i, end)))
                i = end
                continue
            if text.startswith("_:{", i):
                end = _match_brace(text, i + 2)
                regions.append((i, end, self._emit_bnode(text, i, end)))
                i = end
                continue
            if (text.startswith("e{", i) or text.startswith("f{", i)
                    or text.startswith("?{", i)) and i + 2 <= n:
                end = _match_brace(text, i + 1)
                regions.append((i, end, self._emit_nested(text, i, end)))
                i = end
                continue
            if text.startswith("e<", i) or text.startswith("f<", i):
                end = text.find(">", i)
                end = n if end < 0 else end + 1
                regions.append((i, end, self._emit_firi(text, i, end)))
                i = end
                continue
            if c == "{":
                end = _match_brace(text, i)
                if is_query and not _is_interpolation(text[i + 1:end - 1]):
                    i += 1                                # a SPARQL group
                    continue
                regions.append((i, end, self._emit_interp(text, i, end)))
                i = end
                continue
            i += 1
        return regions

    # -- region emitters -----------------------------------------------------

    def _python_chunk(self, text, start, end, offset):
        """The Python expression text[start:end], through PythonLexer.

        An interpolation is re-scanned by the transpiler's own scanner, so it
        may itself hold an island — ``ex:{?id}``, ``{f<http://e/{x}>}``.
        PythonLexer would mark those an error; when it does, the chunk goes to
        the SPARQL lexer instead."""
        chunk = text[start:end]
        out = list(self.python.get_tokens_unprocessed(chunk))
        if any(ttype is Error for _, ttype, _ in out):
            return _delegate(self.sparql, _REMAP_SPARQL, chunk, offset + start,
                             self._regions(chunk, "sparql"))
        return [(offset + start + idx, ttype, value)
                for idx, ttype, value in out]

    def _emit_interp(self, text, start, end):
        def emit(offset):
            out = [(offset + start, Punctuation, "{")]
            out.extend(self._python_chunk(text, start + 1, end - 1, offset))
            out.append((offset + end - 1, Punctuation, "}"))
            return out
        return emit

    def _emit_nested(self, text, start, end):
        """e{ … } / f{ … } / ?{ … } in term position."""
        def emit(offset):
            out = [(offset + start, T_SIGIL, text[start:start + 2])]
            body = text[start + 2:end - 1]
            if text[start] == "e":
                out.extend(_delegate(self.sparql, _REMAP_SPARQL, body,
                                     offset + start + 2,
                                     self._regions(body, "sparql")))
            else:
                out.extend(self._python_chunk(text, start + 2, end - 1, offset))
            out.append((offset + end - 1, T_SIGIL, text[end - 1:end]))
            return out
        return emit

    def _emit_firi(self, text, start, end):
        def emit(offset):
            out = [(offset + start, T_SIGIL, text[start:start + 2])]
            out.extend(self._firi_body(text, start + 2, end - 1, offset))
            out.append((offset + end - 1, T_SIGIL, text[end - 1:end]))
            return out
        return emit

    def _emit_bnode(self, text, start, end):
        def emit(offset):
            out = [(offset + start, T_IRI, "_:"),
                   (offset + start + 2, Punctuation, "{")]
            out.extend(self._python_chunk(text, start + 3, end - 1, offset))
            out.append((offset + end - 1, Punctuation, "}"))
            return out
        return emit

    def _emit_fstring(self, text, start, end):
        def emit(offset):
            return list(self._fstring(text, start, end, offset))
        return emit

    def _fstring(self, text, start, end, offset):
        """An f-string in term position: its holes are Python."""
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
            for tok in self._python_chunk(text, j + 1, k - 1, offset):
                yield tok
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
                for tok in _delegate(self.sparql, _REMAP_SPARQL, body,
                                     offset + j + 1,
                                     self._regions(body, "sparql")):
                    yield tok
            else:
                for tok in self._python_chunk(text, j + 1, k - 1, offset):
                    yield tok
            yield offset + k - 1, Punctuation, "}"
            i = k

    # -- ldpy-only declarations ----------------------------------------------

    def _declaration(self, text, offset):
        """@graph, @bindings, `for @bindings in`, prefix imports: forms that
        exist in no other language, so no lexer to delegate to."""
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
                yield from self._firi_body(text, i + 2, end - 1, offset)
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
                yield offset + i, T_KW if word in _DECL_KEYWORDS else Name, word
                i = m.end()
                continue
            m = _RE_PUNCT.match(text, i)
            if m:
                yield offset + i, Punctuation, m.group(0)
                i = m.end()
                continue
            yield offset + i, Text, c
            i += 1
