"""Oracle des jeux de caractères (option C de la décision charsets).

Transcrit INDÉPENDAMMENT les productions des specs (Turtle PN_CHARS_BASE /
PN_CHARS ; identifiants Python via str.isidentifier) et sert :

- à VÉRIFIER les tables du transpileur (verify_against_transpiler, appelé
  par tests/test_charsets.py) ;
- à produire comptes et caractères témoins pour la documentation :
  ``python tools/charsets.py`` ;
- optionnellement, si `greenery` est installé (dépendance de développement,
  jamais du runtime), à faire l'algèbre d'automates sur les regex complètes.
"""

import sys


def pn_chars_base(c):
    """PN_CHARS_BASE — transcription directe de la grammaire Turtle."""
    o = ord(c)
    return ("A" <= c <= "Z" or "a" <= c <= "z" or 0xC0 <= o <= 0xD6
            or 0xD8 <= o <= 0xF6 or 0xF8 <= o <= 0x2FF
            or 0x370 <= o <= 0x37D or 0x37F <= o <= 0x1FFF
            or 0x200C <= o <= 0x200D or 0x2070 <= o <= 0x218F
            or 0x2C00 <= o <= 0x2FEF or 0x3001 <= o <= 0xD7FF
            or 0xF900 <= o <= 0xFDCF or 0xFDF0 <= o <= 0xFFFD
            or 0x10000 <= o <= 0xEFFFF)


def pn_chars(c):
    """PN_CHARS — transcription directe."""
    o = ord(c)
    return (pn_chars_base(c) or c == "_" or c == "-"
            or "0" <= c <= "9" or o == 0xB7
            or 0x300 <= o <= 0x36F or 0x203F <= o <= 0x2040)


def py_id_continue(c):
    return ("a" + c).isidentifier()


def py_id_start(c):
    return c.isidentifier()


def verify_against_transpiler(limit=0x10000):
    """Compare les prédicats du transpileur aux transcriptions ci-dessus ;
    retourne la liste des points de code divergents (attendue vide)."""
    from ldpy.transpiler.core import _pn_base, _pn_char, _ix_char, _ix_start
    bad = []
    for o in range(0x21, limit):
        c = chr(o)
        if _pn_base(c) != pn_chars_base(c):
            bad.append(("pn_base", hex(o)))
        if _pn_char(c) != pn_chars(c):
            bad.append(("pn_char", hex(o)))
        if _ix_char(c) != (py_id_continue(c) and pn_chars(c)):
            bad.append(("ix_char", hex(o)))
        if _ix_start(c) != (py_id_start(c) and (pn_chars_base(c) or c == "_")):
            bad.append(("ix_start", hex(o)))
    return bad


def report(limit=0x10000):
    """Comptes et témoins pour la documentation."""
    both = t_only = p_only = 0
    w_t, w_p = [], []
    for o in range(0x21, limit):
        c = chr(o)
        t, p = pn_chars(c), py_id_continue(c)
        if t and p:
            both += 1
        elif t:
            t_only += 1
            if len(w_t) < 10:
                w_t.append(c)
        elif p:
            p_only += 1
            if len(w_p) < 10:
                w_p.append(c)
    print("communs: %d | Turtle seulement: %d (%s…) | Python seulement: %d (%s)"
          % (both, t_only, " ".join(w_t), p_only, " ".join(w_p)))
    try:
        import greenery  # noqa: F401
        print("greenery disponible : algèbre de regex possible (dev)")
    except ImportError:
        pass


if __name__ == "__main__":
    report()
    bad = verify_against_transpiler()
    print("tables du transpileur : %s" %
          ("OK" if not bad else "DIVERGENCES %s" % bad[:5]))
    sys.exit(1 if bad else 0)
