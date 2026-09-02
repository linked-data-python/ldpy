"""Evaluation semantics of SPARQL expression nodes.

`e{ <SPARQL expression> }` transpiles to a DEFERRED ``Expression`` object:
where ``f{...}``/``?{...}`` evaluate immediately, an Expression evaluates
later, against a *solution mapping*:

    majeur = e{ ?age >= 18 && BOUND(?nom) }
    majeur({"age": 20, "nom": "Ana"})          # -> Literal(True)
    adult.ebv({"age": 20, "name": "Ana"})      # -> True (a Python bool)

The semantics follow SPARQL 1.1: numeric promotion (integer < decimal <
float < double, integer division -> decimal), errors PROPAGATED (unbound
variable, incomparable types) and absorbed by ``||``/``&&``/``IF``/
``COALESCE`` per SPARQL's three-valued truth table. No parser of any RDF
library is used: the terms come from ``ldpy.backend`` — rdflib or urdflib —
so these expressions run on a device as well as on the host.
"""

import re as _re

from ldpy.backend import BNode, Literal, URIRef, Variable, XSD, Node

from ldpy.runtime import node as _node

__all__ = ["SparqlError", "Expression", "expr"]


class SparqlError(Exception):
    """A SPARQL evaluation error (unbound variable, incomparable types…).

    It propagates through the operators and is absorbed only where SPARQL
    SPARQL l'absorbe : ||, &&, IF, COALESCE."""


class Expression:
    """A compiled SPARQL expression, to evaluate against a solution mapping.

    The mapping accepts str or Variable keys, and Python or RDF values
    termes RDF (coercition par ldpy.runtime.node)."""

    __slots__ = ("_fn", "src")

    def __init__(self, fn, src=""):
        self._fn = fn
        self.src = src

    def _mapping(self, sm, kw):
        out = {}
        for k, v in list((sm or {}).items()) + list(kw.items()):
            name = str(k) if isinstance(k, Variable) else k
            out[name] = v if isinstance(v, Node) else _node(v)
        return out

    def __call__(self, sm=None, **kw):
        """Evaluate; returns an RDF term, or raises SparqlError."""
        return self._fn(self._mapping(sm, kw))

    def evaluate(self, sm=None, **kw):
        """Alias explicite de __call__."""
        return self(sm, **kw)

    def ebv(self, sm=None, **kw):
        """Effective boolean value (a Python bool); raises SparqlError otherwise."""
        return ebv(self(sm, **kw))

    def __repr__(self):
        return "e{ %s }" % self.src if self.src else "Expression(...)"


def expr(fn, src=""):
    """Build an Expression (called by the emitted code)."""
    return Expression(fn, src)


# ---------------------------------------------------------------- valeurs

_NUM_TYPES = {XSD.integer: 0, XSD.decimal: 1, XSD.float: 2, XSD.double: 3}
_INT_TYPES = {XSD.integer, XSD.int, XSD.long, XSD.short, XSD.byte,
              XSD.nonNegativeInteger, XSD.positiveInteger,
              XSD.negativeInteger, XSD.nonPositiveInteger,
              XSD.unsignedInt, XSD.unsignedLong}


def var(sm, name):
    """A variable's value; unbound -> SparqlError."""
    try:
        v = sm[name]
    except KeyError:
        raise SparqlError("unbound variable: ?%s" % name)
    if v is None:
        raise SparqlError("unbound variable: ?%s" % name)
    return v


def bound(sm, name):
    """BOUND(?v)."""
    return Literal(name in sm and sm[name] is not None)


def py(value):
    """Python interpolation {expr}: coerced to a term, at EVERY evaluation."""
    return _node(value)


def number(lexical):
    """A SPARQL numeric literal (integer / decimal / double)."""
    if _re.search(r"[eE]", lexical):
        return Literal(lexical, datatype=XSD.double)
    if "." in lexical:
        return Literal(lexical, datatype=XSD.decimal)
    return Literal(lexical, datatype=XSD.integer)


def _numeric(term):
    if isinstance(term, Literal):
        dt = term.datatype
        if dt in _NUM_TYPES or dt in _INT_TYPES:
            try:
                return term.toPython()
            except Exception:
                pass
    raise SparqlError("not a numeric value: %r" % (term,))


def _num_rank(term):
    dt = term.datatype
    if dt in _INT_TYPES:
        return 0
    return _NUM_TYPES.get(dt, 1)


def _num_result(value, rank):
    dt = (XSD.integer, XSD.decimal, XSD.float, XSD.double)[rank]
    if dt == XSD.integer:
        value = int(value)
    return Literal(value, datatype=dt)


def _promote(value, rank):
    """Bring a value to the Python type of the target rank — SPARQL 1.1
    numeric promotion applies to the OPERANDS, not only to the result:
    without it, xsd:double * xsd:decimal would be a float times a Decimal,
    refuse."""
    if rank == 0:
        return int(value)
    if rank == 1:
        from decimal import Decimal
        return value if isinstance(value, Decimal) else Decimal(str(value))
    return float(value)


def _arith(a, b, op, div=False):
    va, vb = _numeric(a), _numeric(b)
    rank = max(_num_rank(a), _num_rank(b))
    if div and rank == 0:
        rank = 1                      # SPARQL : integer / integer -> decimal
    va, vb = _promote(va, rank), _promote(vb, rank)
    try:
        return _num_result(op(va, vb), rank)
    except ZeroDivisionError:
        raise SparqlError("division by zero")


def add(a, b):
    """The + operator."""
    return _arith(a, b, lambda x, y: x + y)


def sub(a, b):
    """The - operator."""
    return _arith(a, b, lambda x, y: x - y)


def mul(a, b):
    """The * operator."""
    return _arith(a, b, lambda x, y: x * y)


def div(a, b):
    """The / operator (integer/integer -> decimal). Operands are promoted to
    the rank of the result, so never two ints here."""
    return _arith(a, b, lambda x, y: x / y, div=True)


def neg(a):
    """Moins unaire."""
    return _arith(a, number("0"), lambda x, y: -x)


# ------------------------------------------------------------- comparaisons

def _cmp(a, b):
    """-1/0/1, or SparqlError if the terms are not comparable."""
    if isinstance(a, Literal) and isinstance(b, Literal):
        try:
            va, vb = _numeric(a), _numeric(b)
            return (va > vb) - (va < vb)
        except SparqlError:
            pass
        if (a.datatype in (None, XSD.string)
                and b.datatype in (None, XSD.string)
                and a.language is None and b.language is None):
            return (str(a) > str(b)) - (str(a) < str(b))
        if a.datatype == XSD.boolean and b.datatype == XSD.boolean:
            va, vb = a.toPython(), b.toPython()
            return (va > vb) - (va < vb)
        if a.datatype == b.datatype and a.datatype in (
                XSD.dateTime, XSD.date):
            va, vb = a.toPython(), b.toPython()
            return (va > vb) - (va < vb)
        if a.language and b.language and a.language == b.language:
            return (str(a) > str(b)) - (str(a) < str(b))
    raise SparqlError("termes non comparables : %r / %r" % (a, b))


def eq(a, b):
    """The = operator (value equality, then term identity)."""
    try:
        return Literal(_cmp(a, b) == 0)
    except SparqlError:
        if a == b:
            return Literal(True)
        if isinstance(a, Literal) and isinstance(b, Literal):
            raise
        return Literal(False)


def ne(a, b):
    """The != operator."""
    return Literal(not ebv(eq(a, b)))


def lt(a, b):
    """The < operator."""
    return Literal(_cmp(a, b) < 0)


def gt(a, b):
    """The > operator."""
    return Literal(_cmp(a, b) > 0)


def le(a, b):
    """The <= operator."""
    return Literal(_cmp(a, b) <= 0)


def ge(a, b):
    """The >= operator."""
    return Literal(_cmp(a, b) >= 0)


def in_(a, items):
    """The IN operator (semantics of "= chained by ||")."""
    err = None
    for it in items:
        try:
            if ebv(eq(a, it)):
                return Literal(True)
        except SparqlError as e:
            err = e
    if err is not None:
        raise err
    return Literal(False)


def not_in(a, items):
    """The NOT IN operator."""
    return Literal(not ebv(in_(a, items)))


# ------------------------------------------------------------------ logique

def ebv(term):
    """Effective boolean value (SPARQL 17.2.2)."""
    if isinstance(term, Literal):
        if term.datatype == XSD.boolean:
            v = term.toPython()
            if isinstance(v, bool):
                return v
            return str(term) in ("true", "1")
        if term.datatype in _NUM_TYPES or term.datatype in _INT_TYPES:
            try:
                return bool(term.toPython())
            except Exception:
                return False
        if term.datatype in (None, XSD.string):
            return len(str(term)) > 0
    raise SparqlError("no EBV for %r" % (term,))


def and_(la, lb):
    """&& — SPARQL's three-valued table (F && err = F)."""
    try:
        a = ebv(la())
    except SparqlError:
        if ebv(lb()) is False:
            return Literal(False)
        raise
    if not a:
        return Literal(False)
    return Literal(ebv(lb()))


def or_(la, lb):
    """|| — SPARQL's three-valued table (T || err = T)."""
    try:
        a = ebv(la())
    except SparqlError:
        if ebv(lb()) is True:
            return Literal(True)
        raise
    if a:
        return Literal(True)
    return Literal(ebv(lb()))


def not_(a):
    """The ! operator."""
    return Literal(not ebv(a))


def if_(cond, lt_, lf_):
    """IF(cond, alors, sinon) — branches paresseuses."""
    return lt_() if ebv(cond) else lf_()


def coalesce(*lams):
    """COALESCE — premier argument sans erreur."""
    for lam in lams:
        try:
            return lam()
        except SparqlError:
            continue
    raise SparqlError("COALESCE: no argument could be evaluated")


# ------------------------------------------------------------- built-ins

def STR(t):
    """STR(term)."""
    if isinstance(t, BNode):
        raise SparqlError("STR of a blank node")
    return Literal(str(t))


def LANG(t):
    """LANG(literal)."""
    if not isinstance(t, Literal):
        raise SparqlError("LANG wants a literal")
    return Literal(t.language or "")


def DATATYPE(t):
    """DATATYPE(literal)."""
    if not isinstance(t, Literal):
        raise SparqlError("DATATYPE wants a literal")
    if t.language:
        return URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#langString")
    return t.datatype or XSD.string


def IRI(t, base=None):
    """IRI(str) — resolved against the lexical base of the call site."""
    s = str(t)
    if base and not _re.match(r"^[A-Za-z][A-Za-z0-9+.\-]*:", s):
        from ldpy.runtime import firi
        return firi(s, base=base)
    return URIRef(s)


def BNODE(t=None):
    """BNODE() / BNODE(str)."""
    return BNode() if t is None else BNode(str(t))


def CONCAT(*ts):
    """CONCAT(...)."""
    return Literal("".join(str(t) for t in ts))


def UCASE(t):
    """UCASE(str)."""
    return Literal(str(t).upper(), lang=getattr(t, "language", None))


def LCASE(t):
    """LCASE(str)."""
    return Literal(str(t).lower(), lang=getattr(t, "language", None))


def STRLEN(t):
    """STRLEN(str)."""
    return Literal(len(str(t)), datatype=XSD.integer)


def SUBSTR(t, start, length=None):
    """SUBSTR(str, start-1-based[, length])."""
    s = str(t)
    i = int(_numeric(start)) - 1
    if length is None:
        return Literal(s[i:], lang=getattr(t, "language", None))
    return Literal(s[i:i + int(_numeric(length))],
                   lang=getattr(t, "language", None))


def STRSTARTS(a, b):
    """STRSTARTS(str, prefix)."""
    return Literal(str(a).startswith(str(b)))


def STRENDS(a, b):
    """STRENDS(str, suffixe)."""
    return Literal(str(a).endswith(str(b)))


def CONTAINS(a, b):
    """CONTAINS(str, aiguille)."""
    return Literal(str(b) in str(a))


def STRBEFORE(a, b):
    """STRBEFORE(str, separator)."""
    s, sep = str(a), str(b)
    i = s.find(sep)
    return Literal("" if i < 0 else s[:i])


def STRAFTER(a, b):
    """STRAFTER(str, separator)."""
    s, sep = str(a), str(b)
    i = s.find(sep)
    return Literal("" if i < 0 else s[i + len(sep):])


def REPLACE(t, pat, repl, flags=None):
    """REPLACE(str, motif, remplacement[, drapeaux]) — regex XPath ~ Python."""
    f = _re_flags(flags)
    return Literal(_re.sub(str(pat), str(repl), str(t), flags=f))


def REGEX(t, pat, flags=None):
    """REGEX(str, motif[, drapeaux])."""
    return Literal(bool(_re.search(str(pat), str(t), _re_flags(flags))))


def _re_flags(flags):
    f = 0
    for c in str(flags or ""):
        f |= {"i": _re.I, "s": _re.S, "m": _re.M, "x": _re.X}.get(c, 0)
    return f


def ABS(t):
    """ABS(num)."""
    return _arith(t, number("0"), lambda x, y: abs(x))


def ROUND(t):
    """ROUND(num)."""
    import math
    return _arith(t, number("0"), lambda x, y: math.floor(x + 0.5))


def CEIL(t):
    """CEIL(num)."""
    import math
    return _arith(t, number("0"), lambda x, y: math.ceil(x))


def FLOOR(t):
    """FLOOR(num)."""
    import math
    return _arith(t, number("0"), lambda x, y: math.floor(x))


def SAMETERM(a, b):
    """SAMETERM(a, b)."""
    return Literal(a == b)


def ISIRI(t):
    """isIRI / isURI."""
    return Literal(isinstance(t, URIRef))


ISURI = ISIRI


def ISBLANK(t):
    """isBLANK."""
    return Literal(isinstance(t, BNode))


def ISLITERAL(t):
    """isLITERAL."""
    return Literal(isinstance(t, Literal))


def ISNUMERIC(t):
    """isNUMERIC."""
    try:
        _numeric(t)
        return Literal(True)
    except SparqlError:
        return Literal(False)


def LANGMATCHES(tag, rng):
    """LANGMATCHES(tag, range) — '*' and range prefixes."""
    t, r = str(tag).lower(), str(rng).lower()
    if not t:
        return Literal(False)
    if r == "*":
        return Literal(True)
    return Literal(t == r or t.startswith(r + "-"))


def build_iri(parts, base=None):
    """e<...>: concatenate the parts — statics as they are, values through
    STR() then IRI-safe encoding (the IRI(CONCAT(ENCODE_FOR_IRI…)) semantics
    of the dev-sparql specification) — then resolve against the lexical base."""
    from ldpy.runtime import firi
    out = []
    for p in parts:
        if type(p) is str:          # partie statique du gabarit
            out.append(p)
        else:                       # a value (Literal IS a str: exact type)
            out.append(_iri_safe(str(STR(p))))
    iri = "".join(out)
    if base:
        return firi(iri, base=base)
    return URIRef(iri)


_IUNRESERVED = "-._~"


def _iri_safe(value):
    """ENCODE_FOR_IRI (aligned on the R2RML harness: iunreserved preserved)."""
    out = []
    for ch in value:
        if ch.isalnum() and ch.isascii() or ch in _IUNRESERVED \
                or not ch.isascii():
            out.append(ch)
        else:
            out.append("".join("%%%02X" % b for b in ch.encode("utf-8")))
    return "".join(out)


ENCODE_FOR_IRI = lambda t: Literal(_iri_safe(str(t)))    # noqa: E731
