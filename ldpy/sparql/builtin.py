"""
This contains those op.Builtin functions from SPARQL that may be of interest to ldpy developers.

```
# They can be all imported for use in expression nodes as follows:

from ldpy.sparql.op.Builtin import *
e{ STRSTARTS( ?var , "test" ) }


# or individually, for example: 
from ldpy.sparql.op.Builtin import STRSTARTS
e{ STRSTARTS( ?var , "test" ) }
```
"""

from rdflib.plugins.sparql import operators as op

def IRI(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_IRI(expr, ctx)

def isBLANK(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_isBLANK(expr,ctx)


def isLITERAL(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_isLITERAL(expr, ctx)


def isIRI(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_isIRI(expr, ctx)


def isNUMERIC(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_isNUMERIC(expr, ctx)


def BNODE(expr, ctx):
    if len(expr.expr) > 0:
        expr.arg = expr.expr[0]
        del expr["expr"]
    return op.Builtin_BNODE(expr, ctx)


def ABS(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_ABS(expr, ctx)


def IF(expr, ctx):
    expr.arg1 = expr.expr[0]
    expr.arg2 = expr.expr[1]
    expr.arg3 = expr.expr[2]
    del expr["expr"]
    return op.Builtin_IF(expr, ctx)


def RAND(expr, ctx):
    return op.Builtin_RAND(expr, ctx)


def UUID(expr, ctx):
    return op.Builtin_UUID(expr, ctx)


def STRUUID(expr, ctx):
    return op.Builtin_STRUUID(expr, ctx)

def MD5(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_MD5(expr, ctx)

def SHA1(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_SHA1(expr, ctx)

def SHA256(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_SHA256(expr, ctx)


def SHA384(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_SHA384(expr, ctx)


def SHA512(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_SHA512(expr, ctx)


def COALESCE(expr, ctx):
    expr.arg = expr.expr
    del expr["expr"]
    return op.Builtin_COALESCE(expr, ctx)


def CEIL(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_CEIL(expr, ctx)


def FLOOR(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_FLOOR(expr, ctx)


def ROUND(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_ROUND(expr, ctx)


def REGEX(expr, ctx):
    expr.text = expr.expr[0]
    expr.pattern = expr.expr[1]
    if len(expr.expr) > 2:
        expr.flags = expr.expr[2]
    del expr["expr"]
    return op.Builtin_REGEX(expr, ctx)


def REPLACE(expr, ctx):
    expr.arg = expr.expr[0]
    expr.pattern = expr.expr[1]
    expr.replacement = expr.expr[2]
    expr.flags = expr.expr[3]
    del expr["expr"]
    return op.Builtin_REPLACE(expr, ctx)


def STRDT(expr, ctx):
    expr.arg1 = expr.expr[0]
    expr.arg2 = expr.expr[1]
    del expr["expr"]
    return op.Builtin_STRDT(expr, ctx)


def STRLANG(expr, ctx):
    expr.arg1 = expr.expr[0]
    expr.arg2 = expr.expr[1]
    del expr["expr"]
    return op.Builtin_STRLANG(expr, ctx)


def CONCAT(expr, ctx):
    expr.arg = expr.expr
    del expr["expr"]
    return op.Builtin_CONCAT(expr, ctx)


def STRSTARTS(expr, ctx):
    expr.arg1 = expr.expr[0]
    expr.arg2 = expr.expr[1]
    del expr["expr"]
    return op.Builtin_STRSTARTS(expr, ctx)


def STRENDS(expr, ctx):
    expr.arg1 = expr.expr[0]
    expr.arg2 = expr.expr[1]
    del expr["expr"]
    return op.Builtin_STRENDS(expr, ctx)


def STRBEFORE(expr, ctx):
    expr.arg1 = expr.expr[0]
    expr.arg2 = expr.expr[1]
    del expr["expr"]
    return op.Builtin_STRBEFORE(expr, ctx)


def STRAFTER(expr, ctx):
    expr.arg1 = expr.expr[0]
    expr.arg2 = expr.expr[1]
    del expr["expr"]
    return op.Builtin_STRAFTER(expr, ctx)


def CONTAINS(expr, ctx):
    expr.arg1 = expr.expr[0]
    expr.arg2 = expr.expr[1]
    del expr["expr"]
    return op.Builtin_CONTAINS(expr, ctx)


def ENCODE_FOR_URI(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_ENCODE_FOR_URI(expr, ctx)


def SUBSTR(expr, ctx):
    expr.arg = expr.expr[0]
    expr.start = expr.expr[1]
    if len(expr.expr) > 2:
        expr.length = expr.expr[2]
    del expr["expr"]
    return op.Builtin_SUBSTR(expr, ctx)


def STRLEN(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_STRLEN(expr, ctx)


def STR(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_STR(expr, ctx)


def LCASE(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_LCASE(expr, ctx)


def LANGMATCHES(expr, ctx):
    expr.arg1 = expr.expr[0]
    expr.arg2 = expr.expr[0]
    del expr["expr"]
    return op.Builtin_LANGMATCHES(expr, ctx)


def NOW(expr, ctx):
    return op.Builtin_NOW(expr, ctx)


def YEAR(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_YEAR(expr, ctx)


def MONTH(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_MONTH(expr, ctx)


def DAY(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_DAY(expr, ctx)


def HOURS(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_HOURS(expr, ctx)


def MINUTES(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_MINUTES(expr, ctx)


def SECONDS(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_SECONDS(expr, ctx)


def TIMEZONE(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_TIMEZONE(expr, ctx)


def TZ(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_TZ(expr, ctx)


def UCASE(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_UCASE(expr, ctx)


def LANG(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_LANG(expr, ctx)


def DATATYPE(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_DATATYPE(expr, ctx)


def sameTerm(expr, ctx):
    expr.arg1 = expr.expr[0]
    expr.arg2 = expr.expr[0]
    del expr["expr"]
    return op.Builtin_sameTerm(expr, ctx)


def BOUND(expr, ctx):
    expr.arg = expr.expr[0]
    del expr["expr"]
    return op.Builtin_BOUND(expr, ctx)

