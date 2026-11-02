"""Layout of island bodies for the formatter — record ldpy/024.

The formatter hands the Python to black and the islands to this module. An
island body is tokenised, parsed just enough to know its structure, and
printed again; the original whitespace is never consulted, which is what
makes the result canonical and the formatter idempotent.

- Turtle islands (`g{ }`, `+{ }`, `-{ }`, `m{ }`) follow black's rule: on one
  line when the line still fits, else exploded with a hanging indent in steps
  of four — subject on the first line, one predicate per line, a blank node
  `[ … ]` opened at the end of its line and closed on a line of its own.
- SPARQL islands (`s{ }`) always take the canonical layout: one clause per
  line, one triple pattern per line, braces in hanging indent.

Every function here may decline by returning None — a comment inside the
body, a token it does not know. The formatter then copies the body as it
was. Nothing here decides alone that the meaning is kept: `ldpy.formatter`
transpiles the result again and compares (`_same_meaning`).
"""

import re

INDENT = 4

# ---------------------------------------------------------------------------
# Turtle tokens
# ---------------------------------------------------------------------------

_SUFFIX = re.compile(r"@[A-Za-z]+(?:-[A-Za-z0-9]+)*|\^\^")
_IRI = re.compile(r"<[^<>\"{}|^`\\\s]*>")
_NUMBER = re.compile(
    r"[+-]?(?:[0-9]+\.[0-9]*[eE][+-]?[0-9]+|\.[0-9]+[eE][+-]?[0-9]+"
    r"|[0-9]+[eE][+-]?[0-9]+|[0-9]*\.[0-9]+|[0-9]+)")
_NAME_CHARS = re.compile(r"[\w\-.:%·À-￿]")
_PUNCT = "[](),;."


class _Decline(Exception):
    """The body holds something this module does not lay out."""


def _string_end(text, i):
    q = text[i]
    if text.startswith(q * 3, i):
        j = text.find(q * 3, i + 3)
        while j != -1 and text[j - 1] == "\\":
            j = text.find(q * 3, j + 1)
        if j == -1:
            raise _Decline
        return j + 3
    j = i + 1
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == q:
            return j + 1
        if text[j] == "\n":
            raise _Decline
        j += 1
    raise _Decline


def _brace_end(text, i):
    """End of the balanced `{…}` starting at i, strings skipped."""
    depth = 0
    j = i
    while j < len(text):
        c = text[j]
        if c in "\"'":
            j = _string_end(text, j)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise _Decline


def _term_end(text, i):
    """End of one RDF term starting at i (no punctuation, no whitespace)."""
    c = text[i]
    if c in "\"'":
        j = _string_end(text, i)
        return _suffix_end(text, j)
    if c == "{":
        return _suffix_end(text, _brace_end(text, i))
    if c == "<":
        m = _IRI.match(text, i)
        if not m:
            raise _Decline
        return m.end()
    if text.startswith(("f<", "e<"), i):
        j = i + 2
        while j < len(text) and text[j] != ">":
            j = _brace_end(text, j) if text[j] == "{" else j + 1
        if j >= len(text):
            raise _Decline
        return j + 1
    if text.startswith(("e{", "?{", "_:{"), i):
        return _suffix_end(text, _brace_end(text, text.index("{", i)))
    m = _NUMBER.match(text, i)
    if m and (c.isdigit() or c in "+-" or text[i + 1:i + 2].isdigit()):
        return m.end()
    # names: prefixed names (with `{…}` pieces), variables, `a`, booleans,
    # blank node labels
    j = i + (1 if c in "?$" else 0)
    while j < len(text):
        if text[j] == "{":
            j = _brace_end(text, j)
        elif _NAME_CHARS.match(text, j):
            j += 1
        else:
            break
    while j > i and text[j - 1] == ".":      # a name never ends with '.'
        j -= 1
    if j == i:
        raise _Decline
    return j


def _suffix_end(text, j):
    if text.startswith("@{", j):                # computed tag (ldpy/020)
        return _brace_end(text, j + 1)
    m = _SUFFIX.match(text, j)
    if not m:
        return j
    if m.group(0) != "^^":
        return m.end()
    return _term_end(text, m.end())


def turtle_tokens(body):
    """[(kind, text)] — kind is 'term' or the punctuation itself."""
    out = []
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c.isspace():
            i += 1
        elif c == "#":
            raise _Decline                     # comments are kept verbatim
        elif c in _PUNCT and not (c == "." and body[i + 1:i + 2].isdigit()):
            out.append((c, c))
            i += 1
        else:
            j = _term_end(body, i)
            out.append(("term", body[i:j]))
            i = j
    return out


# ---------------------------------------------------------------------------
# Turtle structure
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self):
        return self.t[self.i][0] if self.i < len(self.t) else None

    def take(self, kind=None):
        if self.peek() is None or (kind and self.peek() != kind):
            raise _Decline
        tok = self.t[self.i]
        self.i += 1
        return tok

    def body(self):
        statements, final_dot = [], False
        while self.peek() is not None:
            statements.append(self.statement())
            final_dot = False
            while self.peek() == ".":
                self.take(".")
                final_dot = True
            if self.peek() is not None and not final_dot:
                raise _Decline
        return statements, final_dot

    def statement(self):
        subject = self.node()
        pol = self.pol() if self.peek() not in (".", None) else []
        if not pol and subject[0] != "bnode":
            raise _Decline
        return subject, pol

    def pol(self):
        """Predicate-object list: [(verb, [object…])]."""
        out = []
        while True:
            verb = self.take("term")[1]
            objects = [self.node()]
            while self.peek() == ",":
                self.take(",")
                objects.append(self.node())
            out.append((verb, objects))
            if self.peek() != ";":
                return out
            while self.peek() == ";":
                self.take(";")
            if self.peek() in ("]", ".", None):
                return out

    def node(self):
        k = self.peek()
        if k == "term":
            return ("term", self.take()[1])
        if k == "[":
            self.take("[")
            pol = self.pol() if self.peek() != "]" else []
            self.take("]")
            return ("bnode", pol)
        if k == "(":
            self.take("(")
            items = []
            while self.peek() != ")":
                items.append(self.node())
            self.take(")")
            return ("list", items)
        raise _Decline


# ---------------------------------------------------------------------------
# Turtle printing
# ---------------------------------------------------------------------------

def _flat_node(node):
    kind, value = node
    if kind == "term":
        return value
    if kind == "bnode":
        return "[ %s ]" % _flat_pol(value) if value else "[]"
    return "( %s )" % " ".join(_flat_node(x) for x in value) if value else "()"


def _flat_pol(pol):
    return " ; ".join("%s %s" % (verb, ", ".join(_flat_node(o) for o in objs))
                      for verb, objs in pol)


def _flat_statement(statement):
    subject, pol = statement
    s = _flat_node(subject)
    return "%s %s" % (s, _flat_pol(pol)) if pol else s


def _flat_body(statements, final_dot):
    text = " . ".join(_flat_statement(s) for s in statements)
    return text + " ." if final_dot else text


def _object_lines(node, indent, room):
    """Lines of one object whose first line starts after its verb. `indent`
    is the column of the verb's line; `room` what is left on the first line."""
    flat = _flat_node(node)
    if len(flat) <= room or node[0] != "bnode" or not node[1]:
        return [flat]
    lines = ["["]
    lines += _pol_lines(node[1], indent + INDENT)
    lines.append(" " * indent + "]")
    return lines


def _pol_lines(pol, indent):
    """One predicate per line, each at `indent`."""
    out = []
    for k, (verb, objects) in enumerate(pol):
        line = " " * indent + verb + " "
        group = []
        for m, obj in enumerate(objects):
            if m == 0:
                room = _width - len(line)
                lines = _object_lines(obj, indent, room)
                lines[0] = line + lines[0]
            else:
                pad = " " * (indent + INDENT)
                lines = _object_lines(obj, indent + INDENT,
                                      _width - len(pad))
                lines[0] = pad + lines[0]
            if m < len(objects) - 1:
                lines[-1] += ","
            group += lines
        if _flat_fits(group, objects, line):
            group = [line + ", ".join(_flat_node(o) for o in objects)]
        if k < len(pol) - 1:
            group[-1] += " ;"
        out += group
    return out


def _flat_fits(group, objects, line):
    flat = line + ", ".join(_flat_node(o) for o in objects)
    return len(group) > 1 and len(flat) + 2 <= _width and "\n" not in flat


def _statement_lines(statement, indent):
    flat = " " * indent + _flat_statement(statement)
    if len(flat) <= _width - 2:
        return [flat]
    subject, pol = statement
    head = " " * indent + _flat_node(subject)
    if not pol:
        return [head]
    rest = _pol_lines(pol, indent + INDENT)
    first = rest[0].lstrip()
    lines = [head + " " + first] + rest[1:]
    return lines


#: shared with the helpers above during one layout; a module global keeps
#: their signatures short, and layout is not re-entrant
_width = 88


def graph_layout(opener, body):
    """Parse a Turtle island body. Returns a `Layout`, or None to decline."""
    try:
        statements, final_dot = _Parser(turtle_tokens(body)).body()
    except _Decline:
        return None
    if not statements:
        return Layout(opener + " }", None)
    flat = "%s %s }" % (opener, _flat_body(statements, final_dot))

    def exploded(indent, width):
        global _width
        _width = width
        lines = [opener]
        for k, statement in enumerate(statements):
            block = _statement_lines(statement, indent + INDENT)
            if k < len(statements) - 1 or final_dot:
                block[-1] += " ."
            lines += block
        lines.append(" " * indent + "}")
        return "\n".join(lines)
    return Layout(flat, exploded)


class Layout:
    """An island laid out two ways: `flat` (one line) and `exploded(indent,
    width)` — the formatter picks the first if the line still fits."""

    __slots__ = ("flat", "exploded", "always_explode")

    def __init__(self, flat, exploded, always_explode=False):
        self.flat = flat
        self.exploded = exploded
        self.always_explode = always_explode

    def text(self, column, indent, rest, width):
        """The island placed at `column` on a line indented by `indent`,
        followed on that line by `rest`."""
        if self.exploded is None:
            return self.flat
        if not self.always_explode and "\n" not in self.flat \
                and column + len(self.flat) + len(rest) <= width:
            return self.flat
        return self.exploded(indent, width)


# ---------------------------------------------------------------------------
# SPARQL
# ---------------------------------------------------------------------------

_KEYWORDS = {
    "SELECT", "CONSTRUCT", "ASK", "DESCRIBE", "WHERE", "FROM", "NAMED",
    "DISTINCT", "REDUCED", "AS", "ORDER", "GROUP", "BY", "ASC", "DESC",
    "HAVING", "LIMIT", "OFFSET", "VALUES", "OPTIONAL", "UNION", "MINUS",
    "GRAPH", "SERVICE", "SILENT", "FILTER", "BIND", "EXISTS", "NOT", "IN",
    "INSERT", "DELETE", "DATA", "WITH", "USING", "DEFAULT", "ALL", "CLEAR",
    "DROP", "CREATE", "LOAD", "COPY", "MOVE", "ADD", "INTO", "TO", "UNDEF",
    "PREFIX", "BASE", "COUNT", "SUM", "MIN", "MAX", "AVG", "SAMPLE",
    "GROUP_CONCAT", "SEPARATOR", "STR", "LANG", "LANGMATCHES", "DATATYPE",
    "BOUND", "IRI", "URI", "BNODE", "RAND", "ABS", "CEIL", "FLOOR", "ROUND",
    "CONCAT", "STRLEN", "UCASE", "LCASE", "ENCODE_FOR_URI", "CONTAINS",
    "STRSTARTS", "STRENDS", "STRBEFORE", "STRAFTER", "YEAR", "MONTH", "DAY",
    "HOURS", "MINUTES", "SECONDS", "TIMEZONE", "TZ", "NOW", "UUID",
    "STRUUID", "MD5", "SHA1", "SHA256", "SHA384", "SHA512", "COALESCE", "IF",
    "STRLANG", "STRDT", "SAMETERM", "ISIRI", "ISURI", "ISBLANK",
    "ISLITERAL", "ISNUMERIC", "REGEX", "SUBSTR", "REPLACE",
}
#: clauses that start a line of their own
_CLAUSES = {"SELECT", "CONSTRUCT", "ASK", "DESCRIBE", "WHERE", "FROM",
            "ORDER", "GROUP", "HAVING", "LIMIT", "OFFSET", "INSERT", "DELETE",
            "WITH", "USING", "PREFIX", "BASE", "FILTER", "OPTIONAL", "BIND",
            "MINUS", "GRAPH", "SERVICE", "VALUES"}
#: built-in functions: no space before their `(`, as in a call
_FUNCTIONS = {
    "COUNT", "SUM", "MIN", "MAX", "AVG", "SAMPLE", "GROUP_CONCAT", "STR",
    "LANG", "LANGMATCHES", "DATATYPE", "BOUND", "IRI", "URI", "BNODE", "RAND",
    "ABS", "CEIL", "FLOOR", "ROUND", "CONCAT", "STRLEN", "UCASE", "LCASE",
    "ENCODE_FOR_URI", "CONTAINS", "STRSTARTS", "STRENDS", "STRBEFORE",
    "STRAFTER", "YEAR", "MONTH", "DAY", "HOURS", "MINUTES", "SECONDS",
    "TIMEZONE", "TZ", "NOW", "UUID", "STRUUID", "MD5", "SHA1", "SHA256",
    "SHA384", "SHA512", "COALESCE", "IF", "STRLANG", "STRDT", "SAMETERM",
    "ISIRI", "ISURI", "ISBLANK", "ISLITERAL", "ISNUMERIC", "REGEX", "SUBSTR",
    "REPLACE"}
_OPERATORS = ("&&", "||", "!=", "<=", ">=", "^^", "=", "<", ">", "!", "+",
              "-", "*", "/", "|", "^")


def sparql_tokens(body, interpolations=()):
    """[(kind, text)]: 'kw' (upper-cased), 'term', 'interp', 'op', or the
    punctuation itself. `interpolations`: offsets in `body` of the `{` the
    transpiler read as an interpolation.

    A property path keeps its glue: a `*`, `+` or `?` written against the
    IRI or `)` before it (`rdfs:subClassOf*`), and a `^` against the term
    after it, stay part of that token — rdflib reads `rdfs:subClassOf *`
    differently, or not at all."""
    out = []
    i, n = 0, len(body)
    end = -1                            # where the previous token ended

    def glued_to_path():
        if not out or i != end:
            return False
        kind, text = out[-1]
        return text == ")" or (kind == "term" and text[0] not in "?$\"'"
                               and not text[0].isdigit())

    while i < n:
        c = body[i]
        if c.isspace():
            i += 1
            continue
        if c == "#":
            raise _Decline
        if c in "*+?" and glued_to_path() \
                and not body[i + 1:i + 2].isalnum():
            out[-1] = ("term", out[-1][1] + c)
            i += 1
        elif c == "{" and i in interpolations:
            j = _suffix_end(body, _brace_end(body, i))
            out.append(("interp", body[i:j]))
            i = j
        elif c in "{}()[];,.":
            if c == "." and body[i + 1:i + 2].isdigit():
                j = _term_end(body, i)
                out.append(("term", body[i:j]))
                i = j
            else:
                out.append((c, c))
                i += 1
        elif c == "^" and not body.startswith("^^", i) \
                and i + 1 < n and not body[i + 1].isspace():
            j = (i + 2 if body[i + 1] == "(" else _term_end(body, i + 1))
            out.append(("term", body[i:j]))
            i = j
        elif c == "<" and _IRI.match(body, i):
            j = _IRI.match(body, i).end()
            out.append(("term", body[i:j]))
            i = j
        elif c in "\"'":
            j = _suffix_end(body, _string_end(body, i))
            out.append(("term", body[i:j]))
            i = j
        elif any(body.startswith(op, i) for op in _OPERATORS) \
                and not (c in "+-" and body[i + 1:i + 2].isdigit()
                         and (not out or out[-1][0] not in ("term", ")"))):
            op = next(op for op in _OPERATORS if body.startswith(op, i))
            out.append(("op", op))
            i += len(op)
        else:
            j = _term_end(body, i)
            word = body[i:j]
            if word.upper() in _KEYWORDS and ":" not in word \
                    and word[0] not in "?$":
                out.append(("kw", word.upper()))
            else:
                out.append(("term", word))
            i = j
        end = i
    return out


def _sparql_lines(tokens, indent):
    """One clause per line, one triple pattern per line, braces in hanging
    indent; a `;` continuation is indented one step further."""
    lines, line = [], []
    state = {"depth": 0, "cont": 0}

    def flush():
        if line:
            pad = INDENT * (state["depth"] + 1 + state["cont"])
            lines.append(" " * (indent + pad) + _join(line))
            line.clear()

    for k, (kind, text) in enumerate(tokens):
        prev = tokens[k - 1][1] if k else None
        nxt = tokens[k + 1][1] if k + 1 < len(tokens) else None
        if kind == "kw" and text in _CLAUSES and line \
                and not (text == "WHERE" and prev in ("DELETE", "INSERT")):
            flush()
            state["cont"] = 0
        if kind == "{":
            line.append(text)
            flush()
            state["depth"] += 1
            state["cont"] = 0
        elif kind == "}":
            flush()
            state["depth"] -= 1
            state["cont"] = 0
            line.append(text)
            if nxt not in (".", "UNION"):
                flush()
        else:
            line.append(text)
            if kind in (".", ";") and _paren_depth(line) == 0:
                flush()
                state["cont"] = 1 if kind == ";" else 0
    flush()
    return lines


def _paren_depth(line):
    return line.count("(") - line.count(")")


def _join(words):
    out = ""
    for k, w in enumerate(words):
        if k and _space_before(words[k - 1], w):
            out += " "
        out += w
    return out


def _space_before(prev, word):
    if prev == "(" or word in (")", ","):
        return False
    if word == "(":
        # a call: a built-in, or a function named by an IRI
        function = prev.upper() in _FUNCTIONS or (
            ":" in prev and prev[0] not in "?$<\"'") or prev.startswith("<")
        return not function
    return True


def sparql_layout(opener, body, interpolations=()):
    """Parse a SPARQL island body. Returns a `Layout` that always explodes,
    or None to decline."""
    try:
        tokens = sparql_tokens(body, interpolations)
    except _Decline:
        return None
    if not tokens or [t for t in tokens if t[0] == "{"].__len__() != \
            [t for t in tokens if t[0] == "}"].__len__():
        return None

    def exploded(indent, width):
        return "\n".join([opener] + _sparql_lines(tokens, indent)
                         + [" " * indent + "}"])
    return Layout(opener + " " + _join([t[1] for t in tokens]) + " }",
                  exploded, always_explode=True)
