"""Transpileur Linked-Data Python v2 — « island parsing ».

Un seul passage sur le source : le Python est recopié verbatim, seuls les îlots
RDF sont parsés (descente récursive) et réécrits en UNE expression Python
s'appuyant sur le runtime ldpy (importé sous l'alias réservé `_ldpy_`).

Spécification : DESIGN_CHOICES/ldpy/001..005 (racine du projet de recherche).

Limitations assumées (documentées) :
- le contenu des chaînes Python est opaque (pas d'îlot dans une f-string) ;
- f-strings « PEP 701 » (guillemets identiques imbriqués) non supportées, comme
  dans MicroPython.
"""

import re

from ldpy.transpiler.errors import LdpySyntaxError, LdpyWarning
from ldpy.transpiler.linemap import LanguageMap

try:
    from urllib.parse import urljoin as _urljoin
except ImportError:  # MicroPython : résolution naïve
    def _urljoin(base, rel):
        return base + rel

RUNTIME_ALIAS = "_ldpy_"
PRELUDE = "import ldpy.runtime as _ldpy_; __namespaces__ = {}; __base__ = None"

KEYWORDS = frozenset((
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
))
# mots-clés « valeurs » : terminent un opérande
VALUE_KEYWORDS = frozenset(("False", "None", "True"))

STRING_PREFIXES = frozenset((
    "", "r", "b", "u", "f", "rb", "br", "rf", "fr",
    "R", "B", "U", "F", "Rb", "rB", "RB", "bR", "Br", "BR",
    "Rf", "rF", "RF", "fR", "Fr", "FR",
))

_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
_LANGTAG_RE = re.compile(r"@([A-Za-z]+(?:-[A-Za-z0-9]+)*)")
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _is_iri_char(c):
    return ord(c) > 0x20 and c not in '<>"{}|^`\\'


def _name_start(c):
    return c.isalpha() or c == "_"


def _name_char(c):
    return c.isalnum() or c == "_"


class TranspileResult:
    def __init__(self, code, lmap, prefixes, base, warnings):
        self.code = code            # source Python généré
        self.map = lmap             # LanguageMap
        self.prefixes = prefixes    # dict prefix -> IRI (str), état final lexical
        self.base = base            # IRI de base finale (str ou None)
        self.warnings = warnings    # list[LdpyWarning]


class Transpiler:
    """Une instance par fichier. Usage : Transpiler(src, filename).run()."""

    def __init__(self, text, filename="<ldpy>", emit_prelude=True):
        self.text = text
        self.emit_prelude = emit_prelude
        self.n = len(text)
        self.filename = filename
        self.i = 0
        # positions 0-based
        self.src_line = 0
        self.src_col = 0
        self.gen_line = 0
        self.gen_col = 0
        self.out = []
        self.map = LanguageMap(filename)
        self._copy_anchor = None    # (sl, sc, gl, gc) début du segment copy ouvert
        self._sub = False           # True pendant le scan d'une expression imbriquée
        # état langage
        self.prefixes = {}          # prefix -> IRI str ('' = préfixe par défaut)
        self._prefix_used = set()
        self.base = None
        self.warnings = []
        self.uses_runtime = False
        # état lexical Python
        self.depth = 0
        self.operand = True         # un opérande peut commencer ici
        self.stmt_start = True      # début de ligne logique (hors espaces)
        self.after_dot = False
        # portée par bloc des @prefix/@base (fiche 004, révision 2026-08-27) :
        # chaque déclaration empile (indent, kind, nom, avait_prev, prev) ;
        # une instruction moins indentée dépile et restaure.
        self._scope_stack = []
        self._retired = {}          # préfixe sorti de portée -> ligne de décl.
        self._prefix_col = {}       # préfixe -> indentation de sa déclaration

    # ------------------------------------------------------------------
    # primitives de position / émission
    # ------------------------------------------------------------------

    def _advance_src(self, s):
        nl = s.count("\n")
        if nl:
            self.src_line += nl
            self.src_col = len(s) - s.rfind("\n") - 1
        else:
            self.src_col += len(s)

    def _advance_gen(self, s):
        nl = s.count("\n")
        if nl:
            self.gen_line += nl
            self.gen_col = len(s) - s.rfind("\n") - 1
        else:
            self.gen_col += len(s)

    def _take(self, k):
        """Consomme k caractères du source sans les émettre."""
        s = self.text[self.i:self.i + k]
        self.i += k
        self._advance_src(s)
        return s

    def _put(self, s):
        """Émet du texte généré."""
        self.out.append(s)
        if not self._sub:
            self._advance_gen(s)

    def _copy(self, k):
        """Recopie k caractères du source vers la sortie (segment copy)."""
        if k <= 0:
            return
        if self._copy_anchor is None and not self._sub:
            self._copy_anchor = (self.src_line, self.src_col,
                                 self.gen_line, self.gen_col)
        s = self.text[self.i:self.i + k]
        self.i += k
        self._advance_src(s)
        self._put(s)

    def _close_copy(self):
        if self._copy_anchor is not None:
            sl, sc, gl, gc = self._copy_anchor
            self.map.add("copy", (sl, sc, self.src_line, self.src_col),
                         (gl, gc, self.gen_line, self.gen_col))
            self._copy_anchor = None

    def _begin_island(self):
        self._close_copy()
        return (self.src_line, self.src_col, self.gen_line, self.gen_col)

    def _end_island(self, kind, mark, gen_text):
        self._put(gen_text)
        if not self._sub:
            sl, sc, gl, gc = mark
            self.map.add("island:" + kind,
                         (sl, sc, self.src_line, self.src_col),
                         (gl, gc, self.gen_line, self.gen_col))
        self.uses_runtime = True
        self.operand = False
        self.stmt_start = False

    def _error(self, msg, line=None, col=None):
        exc = LdpySyntaxError(msg, self.filename,
                              self.src_line if line is None else line,
                              self.src_col if col is None else col)
        # la console s'en sert pour distinguer « entrée incomplète » (îlot
        # non fermé en fin de tampon) d'une vraie erreur de syntaxe
        exc.at_eof = self.i >= self.n
        raise exc

    def _warn(self, msg):
        self.warnings.append(LdpyWarning(msg, self.filename,
                                         self.src_line, self.src_col))

    def _peek(self, off=0):
        j = self.i + off
        return self.text[j] if j < self.n else ""

    # ------------------------------------------------------------------
    # chaînes Python (lexique, fonction pure sur self.text)
    # ------------------------------------------------------------------

    def _string_end(self, i):
        """i pointe sur le 1er guillemet. Retourne l'indice après la chaîne."""
        t = self.text
        q = t[i]
        if t[i:i + 3] == q * 3:
            quote, j = q * 3, i + 3
        else:
            quote, j = q, i + 1
        lq = len(quote)
        while j < self.n:
            c = t[j]
            if c == "\\":
                j += 2
                continue
            if t[j:j + lq] == quote:
                return j + lq
            if c == "\n" and lq == 1:
                self._error("chaîne non terminée", self.src_line, self.src_col)
            j += 1
        self._error("chaîne non terminée", self.src_line, self.src_col)

    # ------------------------------------------------------------------
    # boucle principale
    # ------------------------------------------------------------------

    def run(self):
        self._scan()
        self._close_copy()
        code = "".join(self.out)
        if self.uses_runtime and self.emit_prelude:
            code = self._insert_prelude(code)
        return TranspileResult(code, self.map, dict(self.prefixes),
                               self.base, self.warnings)

    def _scan(self, stops=None, entry_depth=None):
        """Scanne du Python. Si stops est fourni, s'arrête (sans consommer)
        sur un de ces caractères à la profondeur entry_depth."""
        t = self.text
        while self.i < self.n:
            c = t[self.i]
            if stops is not None and self.depth == entry_depth and c in stops:
                return
            if self.stmt_start and self.depth == 0 and not self._sub \
                    and c not in " \t\r\n\\#":
                self._unwind_scopes(self.src_col)
            if c == "\n":
                self._copy(1)
                if self.depth == 0:
                    self.stmt_start = True
                    self.operand = True
                self.after_dot = False
            elif c in " \t\r":
                self._copy(1)
            elif c == "\\" and self._peek(1) == "\n":
                self._copy(2)
            elif c == "#":
                j = t.find("\n", self.i)
                self._copy((j if j != -1 else self.n) - self.i)
            elif c in "\"'":
                self._handle_string(self.i)
            elif _name_start(c):
                self._handle_name()
            elif c.isdigit() or (c == "." and self._peek(1).isdigit()):
                self._copy(self._number_end(self.i) - self.i)
                self.operand = False
                self.stmt_start = False
            elif c == "@":
                if self.stmt_start and not self._sub \
                        and self._try_prefix_or_base():
                    continue
                self._copy(1)
                self.operand = True
                self.stmt_start = False
            elif c in "?$":
                self._var_island()
            elif c == "<" and self.operand:
                if not self._try_iri_island():
                    self._copy(1)
                    self.operand = True
                self.stmt_start = False
            elif c in "([{":
                self.depth += 1
                self._copy(1)
                self.operand = True
                self.stmt_start = False
                self.after_dot = False
            elif c in ")]}":
                self.depth -= 1
                self._copy(1)
                self.operand = False
                self.stmt_start = False
            elif c == ".":
                if t[self.i:self.i + 3] == "...":
                    self._copy(3)
                    self.operand = False
                else:
                    if not self.operand:
                        self.after_dot = True
                    self._copy(1)
                self.stmt_start = False
            elif c == ";":
                self._copy(1)
                self.operand = True
                if self.depth == 0:
                    self.stmt_start = True
            else:
                # opérateurs, ponctuation, identifiants unicode
                if c.isidentifier():
                    j = self.i + 1
                    while j < self.n and (t[j].isalnum() or t[j] == "_"):
                        j += 1
                    self._copy(j - self.i)
                    self.operand = False
                else:
                    self._copy(1)
                    self.operand = True
                self.stmt_start = False
                self.after_dot = False

    def _scan_embedded_expr(self, stops):
        """Scanne une expression Python imbriquée dans un îlot ; retourne son
        texte transpilé. S'arrête sur `stops` à la profondeur d'entrée."""
        saved_out, self.out = self.out, []
        saved_sub, self._sub = self._sub, True
        saved_anchor, self._copy_anchor = self._copy_anchor, None
        saved_ctx = (self.operand, self.stmt_start, self.after_dot)
        self.operand = True
        self.after_dot = False
        try:
            self._scan(stops=stops, entry_depth=self.depth)
            return "".join(self.out)
        finally:
            self.out = saved_out
            self._sub = saved_sub
            self._copy_anchor = saved_anchor
            self.operand, self.stmt_start, self.after_dot = saved_ctx

    # ------------------------------------------------------------------
    # nombres
    # ------------------------------------------------------------------

    def _number_end(self, i):
        t = self.text
        j = i
        while j < self.n:
            c = t[j]
            if c.isalnum() or c in "._":
                j += 1
            elif c in "+-" and t[j - 1] in "eE" and j > i and \
                    t[i:j].lower().lstrip("0").startswith(("x",)) is False:
                # exposant signé : 1e-5 (pas dans les hexas)
                if not t[i:i + 2].lower() in ("0x", "0o", "0b"):
                    j += 1
                else:
                    break
            else:
                break
        # un nom collé derrière un nombre (ex. `1if`) n'existe plus en py3 ;
        # on recopie tel quel, le compilateur Python tranchera.
        return j

    # ------------------------------------------------------------------
    # chaînes et littéraux RDF
    # ------------------------------------------------------------------

    def _handle_string(self, start, prefix_start=None):
        """start : indice du guillemet. prefix_start : indice du préfixe de
        chaîne (r/b/f/u) déjà repéré, sinon None."""
        tok_start = prefix_start if prefix_start is not None else start
        end = self._string_end(start)
        # suffixe RDF ?
        t = self.text
        suffix = None
        if end < self.n and t[end] == "@":
            m = _LANGTAG_RE.match(t, end)
            if m:
                suffix = ("lang", m.group(1), m.end())
        if suffix is None and t[end:end + 2] == "^^":
            suffix = ("datatype", None, end + 2)
        if suffix is None:
            self._copy(end - self.i)
            self.operand = False
            self.stmt_start = False
            return
        # îlot littéral RDF
        mark = self._begin_island()
        string_text = t[tok_start:end]
        self._take(end - self.i)  # consomme la chaîne
        kind, lang, after = suffix
        if kind == "lang":
            self._take(after - self.i)  # consomme @lang
            gen = "%s.Literal(%s, lang=%r)" % (RUNTIME_ALIAS, string_text, lang)
        else:
            self._take(2)  # consomme ^^
            dt = self._parse_term_after_hats()
            gen = "%s.Literal(%s, datatype=%s)" % (RUNTIME_ALIAS, string_text, dt)
        self._end_island("literal", mark, gen)

    def _parse_term_after_hats(self):
        """Terme datatype juste après '^^' (collé) : iri, pname, firi, fnode."""
        c = self._peek()
        if c == "<":
            iri = self._take_iriref()
            return "%s.URIRef(%r)" % (RUNTIME_ALIAS, self._resolve(iri))
        if c == "f" and self._peek(1) == "<":
            return self._take_firi()
        if c == "f" and self._peek(1) == "{":
            return self._take_fnode()
        if _name_start(c) or c == ":":
            return self._take_pname(in_island=True)
        self._error("type de donnée attendu après '^^'")

    # ------------------------------------------------------------------
    # NAME et déclencheurs d'îlots nominaux
    # ------------------------------------------------------------------

    def _handle_name(self):
        t = self.text
        m = _NAME_RE.match(t, self.i)
        if m is None:  # identifiant non-ASCII : jamais un déclencheur d'îlot
            j = self.i + 1
            while j < self.n and _name_char(t[j]):
                j += 1
            self._copy(j - self.i)
            self.operand = False
            self.stmt_start = False
            self.after_dot = False
            return
        name = m.group(0)
        nxt = t[m.end()] if m.end() < self.n else ""
        operand_here = self.operand

        # préfixe de chaîne ?
        if name in STRING_PREFIXES and nxt in "\"'":
            self._handle_string(m.end(), prefix_start=self.i)
            return

        if self.after_dot:
            self._copy(len(name))
            self.after_dot = False
            self.operand = False
            self.stmt_start = False
            return

        # îlots à délimiteur collé
        if nxt == "{" and name in ("g", "f", "e"):
            if name == "g":
                self._graph_island()
                return
            if name == "f":
                mark = self._begin_island()
                gen = self._take_fnode()
                self._end_island("fnode", mark, gen)
                return
            self._error("e{...} (nœuds expression SPARQL) : "
                        "réservé, prévu en phase 2")
        if nxt == "<" and name in ("f", "e") and operand_here:
            if name == "e":
                self._error("e<...> (e-IRI SPARQL) : réservé, prévu en phase 2")
            saved = (self.i, self.src_line, self.src_col)
            mark = self._begin_island()
            gen = self._try_take_firi()
            if gen is not None:
                self._end_island("firi", mark, gen)
                return
            self.i, self.src_line, self.src_col = saved  # repli : comparaison

        # pname hors îlot : préfixe déclaré, ':' collé, partie locale
        if operand_here and nxt == ":" and name in self.prefixes:
            after = t[m.end() + 1] if m.end() + 1 < self.n else ""
            if _name_start(after) or after == "{":
                mark = self._begin_island()
                gen = self._take_pname(in_island=False)
                self._end_island("pname", mark, gen)
                return
        # préfixe sorti de portée : le texte reste du Python (R3), on avertit
        if operand_here and nxt == ":" and name not in self.prefixes \
                and name in self._retired:
            after = t[m.end() + 1] if m.end() + 1 < self.n else ""
            if _name_start(after) or after == "{":
                self._warn("le préfixe '%s:' est hors de portée ici (sa "
                           "déclaration est dans un bloc terminé) ; le texte "
                           "est laissé tel quel" % name)

        self._copy(len(name))
        if name in KEYWORDS:
            self.operand = name not in VALUE_KEYWORDS
        else:
            self.operand = False
        self.stmt_start = False

    # ------------------------------------------------------------------
    # IRIs, pnames, f-IRIs, variables, fnodes (émission de termes)
    # ------------------------------------------------------------------

    def _resolve(self, iri):
        if self.base and not _SCHEME_RE.match(iri):
            return _urljoin(self.base, iri)
        return iri

    def _iriref_end(self, i):
        """i sur '<'. Retourne l'indice après '>' ou None."""
        t = self.text
        j = i + 1
        while j < self.n and _is_iri_char(t[j]):
            j += 1
        if j < self.n and t[j] == ">":
            return j + 1
        return None

    def _take_iriref(self):
        end = self._iriref_end(self.i)
        if end is None:
            j = self.i + 1
            while j < self.n and self.text[j] not in "\n>":
                j += 1
            if "{" in self.text[self.i:j]:
                self._error("interpolation dans une IRI : écrire f<...{expr}...> "
                            "(IRI formatée) et non <...{expr}...>")
            self._error("IRI '<...>' non terminée")
        return self._take(end - self.i)[1:-1]

    def _try_iri_island(self):
        end = self._iriref_end(self.i)
        if end is None:
            return False
        mark = self._begin_island()
        iri = self._take(end - self.i)[1:-1]
        self._end_island("iri", mark,
                         "%s.URIRef(%r)" % (RUNTIME_ALIAS, self._resolve(iri)))
        return True

    def _try_take_firi(self):
        """Sur 'f<'. Retourne l'expression générée ou None (repli)."""
        t = self.text
        # validation en avant : f< statiques* ( { ... } statiques* )* >
        j = self.i + 2
        while j < self.n and _is_iri_char(t[j]) and t[j] != "{":
            j += 1
        if j >= self.n or t[j] not in "{>":
            return None
        return self._take_firi()

    def _take_firi(self):
        """Sur 'f<'. Consomme et retourne l'expression générée."""
        self._take(2)
        parts = []       # (True, texte statique) | (False, expr)
        static = []
        t = self.text
        while True:
            c = self._peek()
            if c == "":
                self._error("f-IRI non terminée")
            if c == ">":
                self._take(1)
                break
            if c == "{":
                self._take(1)
                if static:
                    parts.append((True, "".join(static)))
                    static = []
                expr = self._scan_embedded_expr("}")
                if self._peek() != "}":
                    self._error("'}' attendu dans la f-IRI")
                self._take(1)
                parts.append((False, expr))
                continue
            if not _is_iri_char(c):
                self._error("caractère %r interdit dans une f-IRI" % c)
            static.append(self._take(1))
        if static:
            parts.append((True, "".join(static)))
        if all(p[0] for p in parts):  # aucune interpolation : statique
            iri = "".join(p[1] for p in parts)
            return "%s.URIRef(%r)" % (RUNTIME_ALIAS, self._resolve(iri))
        args = ", ".join(repr(p[1]) if p[0] else "(%s)" % p[1] for p in parts)
        if self.base:
            return "%s.firi(%s, base=%r)" % (RUNTIME_ALIAS, args, self.base)
        return "%s.firi(%s)" % (RUNTIME_ALIAS, args)

    def _take_fnode(self):
        """Sur 'f{'. Consomme et retourne l'expression générée."""
        self._take(2)
        expr = self._scan_embedded_expr("}")
        if self._peek() != "}":
            self._error("'}' attendu pour fermer f{...}")
        self._take(1)
        return "%s.node((%s))" % (RUNTIME_ALIAS, expr.strip())

    def _var_island(self):
        mark = self._begin_island()
        sigil = self._take(1)  # ? ou $
        if self._peek() == "{":
            self._take(1)
            expr = self._scan_embedded_expr("}")
            if self._peek() != "}":
                self._error("'}' attendu pour fermer ?{...}")
            self._take(1)
            self._end_island("fnode", mark,
                             "%s.node((%s))" % (RUNTIME_ALIAS, expr.strip()))
            return
        m = _NAME_RE.match(self.text, self.i)
        if not m:
            self._error("nom de variable attendu après '%s'" % sigil)
        name = self._take(len(m.group(0)))
        self._end_island("var", mark,
                         "%s.Variable(%r)" % (RUNTIME_ALIAS, name))

    def _take_pname(self, in_island):
        """Sur le début du préfixe (ou sur ':' si préfixe vide, en îlot).
        Consomme `prefix:local` et retourne l'expression générée.
        Hors îlot : partie locale = identifiant (+ interpolations {expr}).
        En îlot : partie locale Turtle-like ([A-Za-z0-9_\\-.], sans '.' final)."""
        t = self.text
        m = _NAME_RE.match(t, self.i)
        prefix = self._take(len(m.group(0))) if m else ""
        if self._peek() != ":":
            self._error("':' attendu dans le nom préfixé")
        self._take(1)
        if prefix not in self.prefixes:
            self._error("préfixe non déclaré : '%s:'" % prefix)
        self._prefix_used.add(prefix)
        ns = self.prefixes[prefix]
        parts = []
        static = []
        while True:
            c = self._peek()
            if c == "{":
                self._take(1)
                if static:
                    parts.append((True, "".join(static)))
                    static = []
                expr = self._scan_embedded_expr("}")
                if self._peek() != "}":
                    self._error("'}' attendu dans le nom préfixé interpolé")
                self._take(1)
                parts.append((False, expr))
                continue
            if in_island:
                ok = c != "" and (c.isalnum() or c in "_-.")
                if ok and c == "." :
                    # '.' final = ponctuation Turtle, pas partie locale
                    nc = self._peek(1)
                    ok = nc != "" and (nc.isalnum() or nc in "_-.{")
            else:
                ok = c != "" and (c.isalnum() or c == "_")
            if not ok:
                break
            static.append(self._take(1))
        if static:
            parts.append((True, "".join(static)))
        if not parts and not in_island:
            self._error("partie locale attendue après '%s:'" % prefix)
        if all(p[0] for p in parts):
            local = "".join(p[1] for p in parts)
            return "%s.URIRef(%r)" % (RUNTIME_ALIAS, ns + local)
        args = [repr(ns)]
        for is_static, val in parts:
            args.append(repr(val) if is_static else "(%s)" % val)
        return "%s.firi(%s)" % (RUNTIME_ALIAS, ", ".join(args))

    # ------------------------------------------------------------------
    # @prefix / @base
    # ------------------------------------------------------------------

    def _try_prefix_or_base(self):
        """Sur '@' en début d'instruction. Tente l'îlot déclaration.
        Retourne True si consommé (sinon rien n'est consommé)."""
        t = self.text
        m = re.match(r"@(prefix|base)\b", t[self.i:self.i + 8])
        if not m:
            return False
        kind = m.group(1)
        # validation en avant (sans consommer)
        j = self.i + 1 + len(kind)
        j = self._skip_ws_ahead(j)
        prefix = None
        if kind == "prefix":
            nm = _NAME_RE.match(t, j)
            prefix = nm.group(0) if nm else ""
            j = nm.end() if nm else j
            if j >= self.n or t[j] != ":":
                return False  # décorateur nommé prefix
            j = self._skip_ws_ahead(j + 1)
        if j >= self.n or t[j] != "<":
            return False
        end = self._iriref_end(j)
        if end is None:
            return False
        k = self._skip_ws_ahead(end)
        if k >= self.n or t[k] != ".":
            return False
        # consommation effective
        decl_col = self.src_col          # indentation de la déclaration
        mark = self._begin_island()
        iri = t[j + 1:end - 1]
        self._take(k + 1 - self.i)
        resolved = self._resolve(iri)
        if kind == "base":
            if decl_col > 0:
                self._scope_stack.append((decl_col, "base", None,
                                          True, self.base))
            self.base = resolved
            gen = "__base__ = %r" % resolved
        else:
            # redéclaration au même niveau après usage : warning ;
            # shadowing dans un bloc plus profond : légitime, silencieux.
            if prefix in self.prefixes and prefix in self._prefix_used \
                    and self.prefixes[prefix] != resolved \
                    and decl_col <= self._prefix_col.get(prefix, 0):
                self._warn("redéclaration du préfixe '%s:' après usage "
                           "(nouvelle IRI : %s)" % (prefix, resolved))
            if decl_col > 0:
                self._scope_stack.append((decl_col, "prefix", prefix,
                                          prefix in self.prefixes,
                                          (self.prefixes.get(prefix),
                                           self._prefix_col.get(prefix))))
            self.prefixes[prefix] = resolved
            self._prefix_col[prefix] = decl_col
            gen = "__namespaces__[%r] = %s.Namespace(%r)" % (
                prefix, RUNTIME_ALIAS, resolved)
        self._end_island(kind, mark, gen)
        return True

    def _unwind_scopes(self, col):
        """Ferme les portées des déclarations plus indentées que l'instruction
        qui commence à la colonne `col` (fin de leur bloc)."""
        while self._scope_stack and col < self._scope_stack[-1][0]:
            _, kind, name, had, prev = self._scope_stack.pop()
            if kind == "base":
                self.base = prev
            elif had:
                self.prefixes[name], self._prefix_col[name] = prev
            else:
                self.prefixes.pop(name, None)
                self._prefix_col.pop(name, None)
                self._retired.setdefault(name, self.src_line)

    def _skip_ws_ahead(self, j):
        t = self.text
        while j < self.n and t[j] in " \t\r\n":
            j += 1
        return j

    # ------------------------------------------------------------------
    # graphes g{ ... }
    # ------------------------------------------------------------------

    def _graph_island(self):
        mark = self._begin_island()
        self._take(2)  # g{
        gctx = _GraphCtx()
        triples = []
        self._g_ws()
        while self._peek() != "}":
            if self._peek() == "":
                self._error("'}' attendu pour fermer g{...}")
            self._g_triples(triples, gctx)
            self._g_ws()
            if self._peek() == ".":
                self._take(1)
                self._g_ws()
                continue
            break
        if self._peek() != "}":
            self._error("'}' attendu pour fermer g{...}")
        self._take(1)
        triples = _share_impure(triples, gctx)
        base_repr = repr(self.base) if self.base else "None"
        args = ["__namespaces__", base_repr]
        args += ["(%s, %s, %s)" % tr for tr in triples]
        gen = "%s.graph(%s)" % (RUNTIME_ALIAS, ", ".join(args))
        self._end_island("graph", mark, gen)

    def _g_ws(self):
        t = self.text
        while self.i < self.n:
            c = t[self.i]
            if c in " \t\r\n":
                self._take(1)
            elif c == "#":
                j = t.find("\n", self.i)
                self._take((j if j != -1 else self.n) - self.i)
            else:
                break

    def _g_triples(self, triples, gctx):
        subj, is_composite = self._g_node(triples, gctx)
        self._g_ws()
        if self._peek() in "}.;," or self._peek() == "":
            if not is_composite:
                self._error("liste de propriétés attendue après le sujet")
            return
        self._g_props(subj, triples, gctx)

    def _g_props(self, subj, triples, gctx):
        while True:
            verb = self._g_verb(triples, gctx)
            self._g_ws()
            while True:
                obj, _ = self._g_node(triples, gctx)
                triples.append((subj, verb, obj))
                self._g_ws()
                if self._peek() == ",":
                    self._take(1)
                    self._g_ws()
                    continue
                break
            if self._peek() == ";":
                self._take(1)
                self._g_ws()
                if self._peek() in "}." or self._peek() in ";" or self._peek() == "":
                    # point-virgule final toléré
                    if self._peek() == ";":
                        continue
                    return
                continue
            return

    def _g_verb(self, triples, gctx):
        t = self.text
        c = self._peek()
        if c == "a" and not (_name_char(self._peek(1)) or self._peek(1) == ":"):
            self._take(1)
            return RUNTIME_ALIAS + ".RDF.type"
        if c == "{":
            self._take(1)
            expr = self._scan_embedded_expr("}")
            if self._peek() != "}":
                self._error("'}' attendu")
            self._take(1)
            return _impure("%s.node((%s))" % (RUNTIME_ALIAS, expr.strip()), gctx)
        if c in "?$":
            return self._g_var(gctx)
        if c == "<":
            iri = self._take_iriref()
            return "%s.URIRef(%r)" % (RUNTIME_ALIAS, self._resolve(iri))
        if c == "f" and self._peek(1) == "<":
            return _maybe_impure(self._take_firi(), gctx)
        if c == "f" and self._peek(1) == "{":
            return _impure(self._take_fnode(), gctx)
        if _name_start(c) or c == ":":
            return _maybe_impure(self._take_pname(in_island=True), gctx)
        self._error("prédicat attendu (IRI, nom préfixé, 'a', variable ou "
                    "interpolation)")

    def _g_var(self, gctx):
        sigil = self._take(1)
        if self._peek() == "{":
            self._take(1)
            expr = self._scan_embedded_expr("}")
            if self._peek() != "}":
                self._error("'}' attendu pour fermer ?{...}")
            self._take(1)
            return _impure("%s.node((%s))" % (RUNTIME_ALIAS, expr.strip()), gctx)
        m = _NAME_RE.match(self.text, self.i)
        if not m:
            self._error("nom de variable attendu après '%s'" % sigil)
        return "%s.Variable(%r)" % (RUNTIME_ALIAS, self._take(len(m.group(0))))

    def _g_node(self, triples, gctx):
        """Parse un nœud de graphe. Retourne (expr, is_composite) ;
        is_composite vrai pour [..], (..) qui peuvent être sujets sans props."""
        t = self.text
        c = self._peek()
        if c == "[":
            self._take(1)
            self._g_ws()
            bn = gctx.new_bnode()
            if self._peek() == "]":
                self._take(1)
                return bn, True
            self._g_props(bn, triples, gctx)
            self._g_ws()
            if self._peek() != "]":
                self._error("']' attendu")
            self._take(1)
            return bn, True
        if c == "(":
            self._take(1)
            self._g_ws()
            items = []
            while self._peek() != ")":
                if self._peek() == "":
                    self._error("')' attendu")
                node, _ = self._g_node(triples, gctx)
                items.append(node)
                self._g_ws()
            self._take(1)
            if not items:
                return RUNTIME_ALIAS + ".RDF.nil", True
            head = None
            prev = None
            for it in items:
                cell = gctx.new_bnode()
                if head is None:
                    head = cell
                else:
                    triples.append((prev, RUNTIME_ALIAS + ".RDF.rest", cell))
                triples.append((cell, RUNTIME_ALIAS + ".RDF.first", it))
                prev = cell
            triples.append((prev, RUNTIME_ALIAS + ".RDF.rest",
                            RUNTIME_ALIAS + ".RDF.nil"))
            return head, True
        if c == "_" and self._peek(1) == ":":
            self._take(2)
            m = _NAME_RE.match(t, self.i)
            if not m:
                self._error("étiquette de nœud anonyme attendue après '_:'")
            label = self._take(len(m.group(0)))
            return gctx.labeled_bnode(label), False
        if c == "{":
            self._take(1)
            expr = self._scan_embedded_expr("}")
            if self._peek() != "}":
                self._error("'}' attendu")
            self._take(1)
            return _impure("%s.node((%s))" % (RUNTIME_ALIAS, expr.strip()), gctx), False
        if c in "?$":
            return self._g_var(gctx), False
        if c == "<":
            iri = self._take_iriref()
            return "%s.URIRef(%r)" % (RUNTIME_ALIAS, self._resolve(iri)), False
        if c == "f" and self._peek(1) == "<":
            return _maybe_impure(self._take_firi(), gctx), False
        if c == "f" and self._peek(1) == "{":
            return _impure(self._take_fnode(), gctx), False
        if c in "\"'" or (c and c in "rbfuRBFU" and self._peek(1) in "\"'"):
            return self._g_literal(), False
        if c.isdigit() or c in "+-" or (c == "." and self._peek(1).isdigit()):
            start = self.i
            if c in "+-":
                self._take(1)
            end = self._number_end(self.i)
            if end == self.i:
                self._error("nombre attendu")
            self._take(end - self.i)
            return "%s.node(%s)" % (RUNTIME_ALIAS, t[start:self.i]), False
        if _name_start(c) or c == ":":
            m = _NAME_RE.match(t, self.i)
            word = m.group(0) if m else ""
            if word in ("True", "true"):
                self._take(len(word))
                return RUNTIME_ALIAS + ".node(True)", False
            if word in ("False", "false"):
                self._take(len(word))
                return RUNTIME_ALIAS + ".node(False)", False
            return _maybe_impure(self._take_pname(in_island=True), gctx), False
        self._error("terme RDF attendu")

    def _g_literal(self):
        """Chaîne (± préfixe f/r/b) ± @lang / ^^type, dans un graphe."""
        t = self.text
        start = self.i
        qpos = self.i
        m = _NAME_RE.match(t, self.i)
        if m and m.group(0) in STRING_PREFIXES and \
                m.end() < self.n and t[m.end()] in "\"'":
            qpos = m.end()
        end = self._string_end(qpos)
        string_text = t[start:end]
        self._take(end - self.i)
        if self._peek() == "@":
            lm = _LANGTAG_RE.match(t, self.i)
            if lm:
                self._take(lm.end() - self.i)
                return "%s.Literal(%s, lang=%r)" % (
                    RUNTIME_ALIAS, string_text, lm.group(1))
        if t[self.i:self.i + 2] == "^^":
            self._take(2)
            dt = self._parse_term_after_hats()
            return "%s.Literal(%s, datatype=%s)" % (
                RUNTIME_ALIAS, string_text, dt)
        return "%s.Literal(%s)" % (RUNTIME_ALIAS, string_text)

    # ------------------------------------------------------------------
    # prélude
    # ------------------------------------------------------------------

    def _prelude_insert_line(self, code):
        """Ligne (0-based) où insérer le prélude : après commentaires de tête,
        docstring de module et imports __future__."""
        lines = code.split("\n")
        offsets = []
        off = 0
        for ln in lines:
            offsets.append(off)
            off += len(ln) + 1
        li = 0
        # commentaires / lignes vides
        while li < len(lines) and (not lines[li].strip()
                                   or lines[li].lstrip().startswith("#")):
            li += 1
        if li >= len(lines):
            return li
        stripped = lines[li].lstrip()
        m = _NAME_RE.match(stripped)
        pfx = m.group(0) if m else ""
        rest = stripped[len(pfx):] if pfx in STRING_PREFIXES else stripped
        if rest[:1] in "\"'":
            # docstring : trouver sa fin dans le texte généré
            qidx = offsets[li] + len(lines[li]) - len(rest)
            saved = (self.text, self.n)
            self.text, self.n = code, len(code)
            try:
                send = self._string_end(qidx)
            finally:
                self.text, self.n = saved
            eol = code.find("\n", send)
            li = (code.count("\n", 0, eol) + 1) if eol != -1 \
                else code.count("\n") + 1
        while li < len(lines) and re.match(r"\s*from\s+__future__\s+import",
                                           lines[li]):
            li += 1
        return li

    def _insert_prelude(self, code):
        li = self._prelude_insert_line(code)
        lines = code.split("\n")
        lines.insert(li, PRELUDE)
        # découpe des segments copy chevauchant la frontière, puis décalage
        new_segments = []
        for seg in self.map.segments:
            if seg.kind == "copy" and seg.gen[0] < li <= seg.gen[2]:
                gl0, gc0, gl1, gc1 = seg.gen
                sl0, sc0, sl1, sc1 = seg.src
                dsl = li - gl0
                cut_src = (sl0 + dsl, 0)
                a = type(seg)("copy", (sl0, sc0) + cut_src, (gl0, gc0, li, 0))
                b = type(seg)("copy", cut_src + (sl1, sc1),
                              (li + 1, 0, gl1 + 1, gc1))
                new_segments.extend([a, b])
            elif seg.gen[0] >= li:
                seg.gen = (seg.gen[0] + 1, seg.gen[1],
                           seg.gen[2] + 1, seg.gen[3])
                new_segments.append(seg)
            else:
                new_segments.append(seg)
        from ldpy.transpiler.linemap import Segment
        new_segments.append(Segment("synthetic", None,
                                    (li, 0, li, len(PRELUDE))))
        new_segments.sort(key=lambda s: s.gen[:2])
        self.map.segments = new_segments
        return "\n".join(lines)


class _Term(str):
    """Expression de terme RDF, portant l'identite de son occurrence source.

    Deux `?{ v() }` ecrits a deux endroits differents sont deux occurrences
    distinctes (donc deux evaluations), meme si leur texte est identique ;
    le meme sujet reutilise par une liste de proprietes est UNE occurrence."""

    __slots__ = ("occ",)

    def __new__(cls, text, occ=None):
        t = str.__new__(cls, text)
        t.occ = occ
        return t


def _maybe_impure(expr, gctx):
    """f-IRI et nom prefixe : impurs seulement s'ils portent une interpolation
    (sinon le transpileur a deja produit une URIRef constante)."""
    if expr.startswith(RUNTIME_ALIAS + ".firi("):
        return _impure(expr, gctx)
    return expr


def _impure(expr, gctx):
    """Marque une expression de terme qui embarque du Python interpole : son
    evaluation peut avoir des effets de bord, elle doit n'avoir lieu qu'une
    fois par occurrence source."""
    gctx.occ += 1
    return _Term(expr, gctx.occ)


def _share_impure(triples, gctx):
    """Un terme interpole partage par plusieurs triplets (typiquement le sujet
    d'une liste de proprietes) ne doit etre evalue qu'une fois : on l'emet a sa
    premiere occurrence dans `slot(i, expr)` et on le rappelle par `slot(i)`.

    Sans cela, `g{ ex:{f()} ex:p 1 ; ex:q 2 }` appellerait f() deux fois et
    produirait deux sujets differents. Voir DESIGN_CHOICES/ldpy/003."""
    counts = {}
    for tr in triples:
        for expr in tr:
            occ = getattr(expr, "occ", None)
            if occ is not None:
                counts[occ] = counts.get(occ, 0) + 1
    shared = {o for o, n in counts.items() if n > 1}
    if not shared:
        return triples
    seen = {}
    out = []
    for tr in triples:
        new_tr = []
        for expr in tr:
            occ = getattr(expr, "occ", None)
            if occ in shared:
                if occ not in seen:
                    seen[occ] = len(seen)
                    new_tr.append("%s.slot(%d, %s)" % (RUNTIME_ALIAS, seen[occ], expr))
                else:
                    new_tr.append("%s.slot(%d)" % (RUNTIME_ALIAS, seen[occ]))
            else:
                new_tr.append(str(expr))
        out.append(tuple(new_tr))
    return out


class _GraphCtx:
    def __init__(self):
        self.counter = 0
        self.occ = 0
        self.labels = {}

    def new_bnode(self):
        expr = "%s.bn(%d)" % (RUNTIME_ALIAS, self.counter)
        self.counter += 1
        return expr

    def labeled_bnode(self, label):
        if label not in self.labels:
            self.labels[label] = self.counter
            self.counter += 1
        return "%s.bn(%d)" % (RUNTIME_ALIAS, self.labels[label])


def transpile(source, filename="<ldpy>"):
    """Transpile un source Linked-Data Python en Python.

    Retourne un TranspileResult(code, map, prefixes, base, warnings).
    """
    return Transpiler(source, filename).run()
