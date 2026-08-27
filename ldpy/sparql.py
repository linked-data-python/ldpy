"""Sémantique d'évaluation des nœuds expression SPARQL (fiche 007, phase 2).

`e{ <expression SPARQL> }` transpile vers un objet ``Expression`` DIFFÉRÉ :
là où ``f{...}``/``?{...}`` s'évaluent immédiatement, une Expression s'évalue
plus tard, contre un *solution mapping* :

    majeur = e{ ?age >= 18 && BOUND(?nom) }
    majeur({"age": 20, "nom": "Ana"})          # -> Literal(True)
    majeur.ebv({"age": 20, "nom": "Ana"})      # -> True (booléen Python)

La sémantique suit SPARQL 1.1 : promotion numérique (integer < decimal <
float < double, division entière -> decimal), erreurs PROPAGÉES (variable non
liée, types incomparables) et absorbées par ``||``/``&&``/``IF``/``COALESCE``
selon la table de vérité à trois valeurs de SPARQL. Aucun parser de rdflib
n'est utilisé ; rdflib ne sert que de modèle de données.
"""

import re as _re

from rdflib import BNode, Literal, URIRef, Variable, XSD
from rdflib.term import Node

from ldpy.runtime import node as _node

__all__ = ["SparqlError", "Expression", "expr"]


class SparqlError(Exception):
    """Erreur d'évaluation SPARQL (variable non liée, types incomparables…).

    Elle se propage à travers les opérateurs et n'est absorbée que là où
    SPARQL l'absorbe : ||, &&, IF, COALESCE."""


class Expression:
    """Une expression SPARQL compilée, à évaluer contre un solution mapping.

    Le mapping accepte des clés str ou Variable, et des valeurs Python ou
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
        """Évalue ; retourne un terme RDF, ou lève SparqlError."""
        return self._fn(self._mapping(sm, kw))

    def evaluate(self, sm=None, **kw):
        """Alias explicite de __call__."""
        return self(sm, **kw)

    def ebv(self, sm=None, **kw):
        """Effective boolean value (bool Python) ; lève SparqlError sinon."""
        return ebv(self(sm, **kw))

    def __repr__(self):
        return "e{ %s }" % self.src if self.src else "Expression(...)"


def expr(fn, src=""):
    """Construit une Expression (appelé par le code émis)."""
    return Expression(fn, src)


# ---------------------------------------------------------------- valeurs

_NUM_TYPES = {XSD.integer: 0, XSD.decimal: 1, XSD.float: 2, XSD.double: 3}
_INT_TYPES = {XSD.integer, XSD.int, XSD.long, XSD.short, XSD.byte,
              XSD.nonNegativeInteger, XSD.positiveInteger,
              XSD.negativeInteger, XSD.nonPositiveInteger,
              XSD.unsignedInt, XSD.unsignedLong}


def var(sm, name):
    """Valeur d'une variable ; non liée -> SparqlError."""
    try:
        v = sm[name]
    except KeyError:
        raise SparqlError("variable non liée : ?%s" % name)
    if v is None:
        raise SparqlError("variable non liée : ?%s" % name)
    return v


def bound(sm, name):
    """BOUND(?v)."""
    return Literal(name in sm and sm[name] is not None)


def py(value):
    """Interpolation Python {expr} : coercition en terme, à CHAQUE évaluation."""
    return _node(value)


def number(lexical):
    """Littéral numérique SPARQL (integer / decimal / double)."""
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
    raise SparqlError("valeur non numérique : %r" % (term,))


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


def _arith(a, b, op, div=False):
    va, vb = _numeric(a), _numeric(b)
    rank = max(_num_rank(a), _num_rank(b))
    if div and rank == 0:
        rank = 1                      # SPARQL : integer / integer -> decimal
    try:
        return _num_result(op(va, vb), rank)
    except ZeroDivisionError:
        raise SparqlError("division par zéro")


def add(a, b):
    """Opérateur +."""
    return _arith(a, b, lambda x, y: x + y)


def sub(a, b):
    """Opérateur -."""
    return _arith(a, b, lambda x, y: x - y)


def mul(a, b):
    """Opérateur *."""
    return _arith(a, b, lambda x, y: x * y)


def div(a, b):
    """Opérateur / (integer/integer -> decimal)."""
    from decimal import Decimal
    def _d(x, y):
        if isinstance(x, int) and isinstance(y, int):
            return Decimal(x) / Decimal(y)
        return x / y
    return _arith(a, b, _d, div=True)


def neg(a):
    """Moins unaire."""
    return _arith(a, number("0"), lambda x, y: -x)


# ------------------------------------------------------------- comparaisons

def _cmp(a, b):
    """-1/0/1, ou SparqlError si les termes ne sont pas comparables."""
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
    """Opérateur = (égalité de valeur, puis identité de terme)."""
    try:
        return Literal(_cmp(a, b) == 0)
    except SparqlError:
        if a == b:
            return Literal(True)
        if isinstance(a, Literal) and isinstance(b, Literal):
            raise
        return Literal(False)


def ne(a, b):
    """Opérateur !=."""
    return Literal(not ebv(eq(a, b)))


def lt(a, b):
    """Opérateur <."""
    return Literal(_cmp(a, b) < 0)


def gt(a, b):
    """Opérateur >."""
    return Literal(_cmp(a, b) > 0)


def le(a, b):
    """Opérateur <=."""
    return Literal(_cmp(a, b) <= 0)


def ge(a, b):
    """Opérateur >=."""
    return Literal(_cmp(a, b) >= 0)


def in_(a, items):
    """Opérateur IN (sémantique « = enchaînés par || »)."""
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
    """Opérateur NOT IN."""
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
    raise SparqlError("pas d'EBV pour %r" % (term,))


def and_(la, lb):
    """&& — table à trois valeurs de SPARQL (F && err = F)."""
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
    """|| — table à trois valeurs de SPARQL (T || err = T)."""
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
    """Opérateur !."""
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
    raise SparqlError("COALESCE : aucun argument évaluable")


# ------------------------------------------------------------- built-ins

def STR(t):
    """STR(term)."""
    if isinstance(t, BNode):
        raise SparqlError("STR d'un nœud anonyme")
    return Literal(str(t))


def LANG(t):
    """LANG(literal)."""
    if not isinstance(t, Literal):
        raise SparqlError("LANG demande un littéral")
    return Literal(t.language or "")


def DATATYPE(t):
    """DATATYPE(literal)."""
    if not isinstance(t, Literal):
        raise SparqlError("DATATYPE demande un littéral")
    if t.language:
        return URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#langString")
    return t.datatype or XSD.string


def IRI(t, base=None):
    """IRI(str) — résolution contre la base lexicale du site d'appel."""
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
    """SUBSTR(str, début-1-based[, longueur])."""
    s = str(t)
    i = int(_numeric(start)) - 1
    if length is None:
        return Literal(s[i:], lang=getattr(t, "language", None))
    return Literal(s[i:i + int(_numeric(length))],
                   lang=getattr(t, "language", None))


def STRSTARTS(a, b):
    """STRSTARTS(str, préfixe)."""
    return Literal(str(a).startswith(str(b)))


def STRENDS(a, b):
    """STRENDS(str, suffixe)."""
    return Literal(str(a).endswith(str(b)))


def CONTAINS(a, b):
    """CONTAINS(str, aiguille)."""
    return Literal(str(b) in str(a))


def STRBEFORE(a, b):
    """STRBEFORE(str, séparateur)."""
    s, sep = str(a), str(b)
    i = s.find(sep)
    return Literal("" if i < 0 else s[:i])


def STRAFTER(a, b):
    """STRAFTER(str, séparateur)."""
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
    """LANGMATCHES(tag, gamme) — '*' et préfixes de gamme."""
    t, r = str(tag).lower(), str(rng).lower()
    if not t:
        return Literal(False)
    if r == "*":
        return Literal(True)
    return Literal(t == r or t.startswith(r + "-"))


def build_iri(parts, base=None):
    """e<...> : concatène les parts — statiques telles quelles, valeurs par
    STR() puis encodage IRI-safe (sémantique IRI(CONCAT(ENCODE_FOR_IRI…)) de
    la spécification dev-sparql) — puis résout contre la base lexicale."""
    from ldpy.runtime import firi
    out = []
    for p in parts:
        if type(p) is str:          # partie statique du gabarit
            out.append(p)
        else:                       # valeur (Literal EST une str : type exact)
            out.append(_iri_safe(str(STR(p))))
    iri = "".join(out)
    if base:
        return firi(iri, base=base)
    return URIRef(iri)


_IUNRESERVED = "-._~"


def _iri_safe(value):
    """ENCODE_FOR_IRI (aligné sur harness R2RML : iunreserved préservé)."""
    out = []
    for ch in value:
        if ch.isalnum() and ch.isascii() or ch in _IUNRESERVED \
                or not ch.isascii():
            out.append(ch)
        else:
            out.append("".join("%%%02X" % b for b in ch.encode("utf-8")))
    return "".join(out)


ENCODE_FOR_IRI = lambda t: Literal(_iri_safe(str(t)))    # noqa: E731
