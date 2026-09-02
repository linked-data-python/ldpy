"""Transpileur Linked-Data Python v2 — « island parsing ».

Un seul passage sur le source : le Python est recopié verbatim, seuls les îlots
RDF sont parsés (descente récursive) et réécrits en UNE expression Python
s'appuyant sur le runtime ldpy (importé sous l'alias réservé `_ldpy_`).

La conception est expliquée dans docs/explanation/ ; la référence du
langage dans docs/reference/language.md.

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
# mots-clés qui ouvrent une instruction composée : leur ':' de profondeur 0
# ouvre une SUITE, position d'instruction (fiche 012, point 12). `match` et
# `case` sont des mots-clés SOUPLES — un `match: int = 0` reste une annotation,
# mais rien n'y suit un ':' qu'un îlot pourrait revendiquer.
COMPOUND_KEYWORDS = frozenset((
    "async", "case", "class", "def", "elif", "else", "except", "finally",
    "for", "if", "match", "try", "while", "with",
))

STRING_PREFIXES = frozenset((
    "", "r", "b", "u", "f", "rb", "br", "rf", "fr",
    "R", "B", "U", "F", "Rb", "rB", "RB", "bR", "Br", "BR",
    "Rf", "rF", "RF", "fR", "Fr", "FR",
))

_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
_LANGTAG_RE = re.compile(r"@([A-Za-z]+(?:-[A-Za-z0-9]+)*)")
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
#: commentaire Python jusqu'à la fin de ligne (fiche 013, détection d'import)
_COMMENT_RE = re.compile(r"#[^\n]*")

_PYNAME_RE = re.compile(r"[^\W\d]\w*")      # identifiant Python (unicode)

# --- Jeux de caractères Turtle (décision charsets, vérifiée par
# --- tools/charsets.py contre une transcription indépendante des specs) :
# --- tables EXACTES dans les îlots ; hors îlots, l'INTERSECTION avec les
# --- identifiants Python (on ne peut pas capturer du Python valide).
import bisect

_PN_BASE_RANGES = (
    (0x41, 0x5A), (0x61, 0x7A), (0xC0, 0xD6), (0xD8, 0xF6), (0xF8, 0x2FF),
    (0x370, 0x37D), (0x37F, 0x1FFF), (0x200C, 0x200D), (0x2070, 0x218F),
    (0x2C00, 0x2FEF), (0x3001, 0xD7FF), (0xF900, 0xFDCF), (0xFDF0, 0xFFFD),
    (0x10000, 0xEFFFF),
)
_PN_EXTRA_RANGES = (          # PN_CHARS \ (PN_CHARS_BASE + '_' + chiffres)
    (0x2D, 0x2D), (0xB7, 0xB7), (0x300, 0x36F), (0x203F, 0x2040),
)


def _in_ranges(c, ranges, _starts_cache={}):
    key = id(ranges)
    starts = _starts_cache.get(key)
    if starts is None:
        starts = _starts_cache[key] = [r[0] for r in ranges]
    cp = ord(c)
    i = bisect.bisect_right(starts, cp) - 1
    return i >= 0 and cp <= ranges[i][1]


def _pn_base(c):
    """PN_CHARS_BASE de Turtle/SPARQL."""
    return _in_ranges(c, _PN_BASE_RANGES)


def _pn_char(c):
    """PN_CHARS de Turtle/SPARQL."""
    return (_pn_base(c) or c == "_" or c.isdigit() and c.isascii()
            or _in_ranges(c, _PN_EXTRA_RANGES))


def _py_id_continue(c):
    return ("a" + c).isidentifier()


def _ix_start(c):
    """Début de nom HORS îlots : identifiant Python ∩ PN_CHARS_BASE|_."""
    return c.isidentifier() and (_pn_base(c) or c == "_")


def _ix_char(c):
    """Continuation HORS îlots : identifiant Python ∩ PN_CHARS."""
    return _py_id_continue(c) and _pn_char(c)


def _scan_pn_prefix(text, i, n):
    """PN_PREFIX exact de Turtle (points intérieurs, tirets…) ; retourne la
    fin, ou i si pas de préfixe à cette position."""
    if i >= n or not _pn_base(text[i]):
        return i
    j = i + 1
    while j < n and (_pn_char(text[j]) or text[j] == "."):
        j += 1
    while j > i + 1 and text[j - 1] == ".":
        j -= 1
    return j


def _scan_pn_local_island(text, i, n):
    """PN_LOCAL de Turtle (sans ':' intérieur ni échappements PLX,
    limitation documentée) ; points intérieurs, chiffres en tête."""
    if i >= n or not (_pn_char(text[i]) or text[i] == "_"):
        return i
    j = i + 1
    while j < n and (_pn_char(text[j]) or text[j] == "."):
        j += 1
    while j > i and text[j - 1] == ".":
        j -= 1
    return j


def _is_iri_char(c):
    return ord(c) > 0x20 and c not in '<>"{}|^`\\'


def _name_start(c):
    return c.isalpha() or c == "_"


def _name_char(c):
    return c.isalnum() or c == "_"


class DynPrefix:
    """Préfixe dynamique (importé, ou à IRI calculée) : la résolution passe
    à l'exécution par la variable Python émise `var` (fiche 013). La table
    lexicale ne connaît pas son IRI."""

    __slots__ = ("var",)

    def __init__(self, var):
        self.var = var

    def __repr__(self):
        return "DynPrefix(%r)" % self.var


class TranspileResult:
    """Résultat de transpile() : code généré, map, préfixes, warnings."""

    def __init__(self, code, lmap, prefixes, base, warnings):
        self.code = code            # source Python généré
        self.map = lmap             # LanguageMap
        self.prefixes = prefixes    # dict prefix -> IRI (str) ou DynPrefix
        self.base = base            # IRI de base finale (str ou None)
        self.warnings = warnings    # list[LdpyWarning]


_BOOL_RE = re.compile(r"(?:true|false|True|False)\s*$")
_STRING_START_RE = re.compile(r"[rbfuRBFU]{0,2}[\"']")


def _term_kind(text):
    """The island kind of a term, from the source it was written as.

    `_g_node` dispatches on exactly these leading characters, so the two stay
    in step, and `tests/test_hover_parts.py` pins each form against the kind
    the SAME term gets outside an island, where the transpiler labels it
    itself. None means "no hover of its own": a `[ ]` or `( )` whose contents
    are recorded one by one anyway, a `{python}` hole, a labelled blank node
    — for those the island's own hover is the honest answer.

    Order matters twice over: `f"x"@en` is a literal and not a formatted
    node, and `foo:bar` is a prefixed name and not anything beginning with f.
    """
    t = text.lstrip()
    if t.startswith("_:{"):
        return "bnode"
    if t.startswith("_:"):
        return None                     # labelled: no island kind of its own
    if t[:1] == "<":
        return "iri"
    if t[:1] in "[({":
        return None
    if _STRING_START_RE.match(t):
        return "literal"                # incl. f"..."@en, r"...", b"..."
    if t[:1] in "?$":
        return "fnode" if t[1:2] == "{" else "var"
    if t[:1] == "f" and t[1:2] in "<{":
        return "firi" if t[1:2] == "<" else "fnode"
    if t[:1] == "e" and t[1:2] in "{<":
        return "enode" if t[1:2] == "{" else "eiri"
    if t[:1].isdigit() or (t[:1] in "+-." and t[1:2].isdigit()):
        return "literal"
    if _BOOL_RE.match(t):
        return "literal"                # Turtle's true/false: a Literal
    return "pname"


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
        # sorte de chaque crochet ouvert : "(", "[" (liste), "s" (indice),
        # "{" (dict/ensemble). Sert au nœud anonyme hors îlot, qui ne doit
        # pas se confondre avec `{_: v}` ni avec la tranche `a[_:v]`.
        self.brackets = []
        # `lambda` ouvre une liste de paramètres qui se ferme sur ':' — un ':'
        # que Python possède, et où aucun terme RDF ne peut vivre.
        self._lambda_depth = None
        self._after_def = False     # on vient de lire 'def' : le '(' suivant
        # la ligne logique a commencé par un mot-clé d'instruction composée :
        # son ':' de profondeur 0 ouvre une SUITE, donc une position
        # d'instruction (fiche 012, point 12).
        self._compound_header = False
        self.operand = True         # un opérande peut commencer ici
        self.stmt_start = True      # début de ligne logique (hors espaces)
        self.after_dot = False
        # portée par bloc des @prefix/@base  :
        # chaque déclaration empile (indent, kind, nom, avait_prev, prev) ;
        # une instruction moins indentée dépile et restaure.
        self._scope_stack = []
        self._retired = {}          # préfixe sorti de portée -> ligne de décl.
        self._shadowed = set()      # préfixe aussi nom Python : averti une fois
        self._prefix_col = {}       # préfixe -> indentation de sa déclaration
        # préfixes dynamiques (fiche 013)
        self._ns_counter = 0        # variables fraîches _ldpy_ns*
        self._import_lines = []     # (ligne 0-based, module) des imports de préfixes
        # graphe courant (fiche 014)
        self._graph_var = None      # variable Python du graphe courant, ou None
        # îlot de motif (fiche 016) : collecte des variables projetées
        self._match_vars = None
        # terms of the island being parsed, and the finished list waiting
        # for the `_end_island` that closes it (record vscode/108)
        self._parts = None
        self._pending_parts = None
        # binding courant (fiche 017)
        self._bindings_var = None

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
                         (gl, gc, self.gen_line, self.gen_col),
                         self._pending_parts)
        self._pending_parts = None
        self.uses_runtime = True
        self.operand = False
        self.stmt_start = False

    def _error(self, msg, line=None, col=None, incomplete=True):
        exc = LdpySyntaxError(msg, self.filename,
                              self.src_line if line is None else line,
                              self.src_col if col is None else col)
        # la console s'en sert pour distinguer « entrée incomplète » (îlot
        # non fermé en fin de tampon) d'une vraie erreur de syntaxe.
        # `incomplete=False` : erreur qu'une suite d'entrée ne répare pas
        # (elle porte sur ce qui a déjà été lu), même si le curseur est en
        # fin de tampon — sinon la console attendrait indéfiniment.
        exc.at_eof = incomplete and self.i >= self.n
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
        """Transpile le fichier entier ; retourne un TranspileResult."""
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
                    self._compound_header = False
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
            elif c in "+-" and self._peek(1) == "{" and self.stmt_start \
                    and self.depth == 0 and not self._sub:
                # +{ ... } / -{ ... } : ajout/retrait sur le graphe courant
                # (fiche 014) — position d'instruction uniquement ; ailleurs,
                # + et - gardent leur sens Python.
                self._addremove_island(c)
            elif c in "?$":
                self._var_island()
            elif c == "<" and self.operand:
                if not self._try_iri_island():
                    self._copy(1)
                    self.operand = True
                self.stmt_start = False
            elif c in "([{":
                self.depth += 1
                # un '[' qui suit un opérande complet est un INDICE, pas une
                # liste : `a[i:j]` est une tranche, `[i:j]` n'existe pas
                if c == "(" and self._after_def:
                    self.brackets.append("p")   # paramètres d'un def
                else:
                    self.brackets.append("s" if c == "[" and not self.operand
                                         else c)
                self._after_def = False
                self._copy(1)
                self.operand = True
                self.stmt_start = False
                self.after_dot = False
            elif c in ")]}":
                self.depth -= 1
                if self.brackets:
                    self.brackets.pop()
                if self._lambda_depth is not None \
                        and self.depth < self._lambda_depth:
                    self._lambda_depth = None
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
            elif c == ":":
                lam = self._lambda_depth == self.depth
                if lam:
                    self._lambda_depth = None       # fin des paramètres
                self._copy(1)
                self.operand = True
                # `if c: +{ ... }` — le ':' d'une instruction composée ouvre
                # une suite, qui est une position d'instruction au même titre
                # qu'un début de ligne (fiche 012, point 12). Pas celui d'une
                # annotation (`x: int`) ni d'un lambda, qui n'ouvrent rien.
                self.stmt_start = (self._compound_header and self.depth == 0
                                   and not lam)
                self._compound_header = False
                self.after_dot = False
            elif c == ";":
                self._copy(1)
                self.operand = True
                if self.depth == 0:
                    self.stmt_start = True
                    self._compound_header = False
            else:
                # opérateurs, ponctuation, identifiants unicode
                if c.isidentifier():
                    j = self.i + 1
                    while j < self.n and (t[j].isalnum() or t[j] == "_"):
                        j += 1
                    self._copy(j - self.i)
                    self.operand = False
                else:
                    # dans une liste de paramètres, le ':' est une annotation
                    # (Python) mais après un '=' on est dans une VALEUR par
                    # défaut, où un terme RDF a tout à fait sa place :
                    # `def f(x=ex:Thing)`. 'p' -> 'P' le note.
                    if self.brackets and self.brackets[-1] in "pP":
                        if c == "=" and self._peek(1) != "=" \
                                and (self.i == 0
                                     or t[self.i - 1] not in "=!<>+-*/%&|^~:@"):
                            self.brackets[-1] = "P"
                        elif c == ",":
                            self.brackets[-1] = "p"
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
        """Terme datatype juste après '^^' (collé) : iri, pname, firi,
        interpolation {expr} (ou f{expr}, sa forme historique).

        Un datatype est toujours un IRI : l'interpolation passe donc par
        dtype() et non par node(), qui ferait un littéral d'une chaîne."""
        c = self._peek()
        if c == "<":
            iri = self._take_iriref()
            return "%s.URIRef(%r)" % (RUNTIME_ALIAS, self._resolve(iri))
        if c == "f" and self._peek(1) == "<":
            return self._take_firi()
        if c == "{" or (c == "f" and self._peek(1) == "{"):
            if c == "f":
                self._take(1)
            self._take(1)  # consomme '{'
            expr = self._scan_embedded_expr("}")
            if self._peek() != "}":
                self._error("'}' attendu pour fermer l'interpolation de "
                            "type de donnée")
            self._take(1)
            return "%s.dtype((%s))" % (RUNTIME_ALIAS, expr.strip())
        if _name_start(c) or c == ":":
            return self._take_pname(in_island=True)
        self._error("type de donnée attendu après '^^'")

    # ------------------------------------------------------------------
    # NAME et déclencheurs d'îlots nominaux
    # ------------------------------------------------------------------

    def _handle_name(self):
        t = self.text
        m = _PYNAME_RE.match(t, self.i)
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

        # import de préfixes (fiche 013) : from m import a, brick:, u: as v:
        if name == "from" and self.stmt_start and not self._sub \
                and self._import_has_prefix_item():
            self._take_prefix_import()
            return

        # modificateurs de portée sur les déclarations d'îlot (fiche 018)
        if name in ("global", "nonlocal") and self.stmt_start \
                and not self._sub:
            j = m.end()
            while j < self.n and t[j] in " \t":
                j += 1
            if re.match(r"@(prefix|base|graph|bindings)\b", t[j:j + 10]):
                self._close_copy()
                self._take(m.end() - self.i)        # le mot-clé
                while self._peek() in (" ", "\t"):
                    self._take(1)
                if not self._try_prefix_or_base(scope_mode=name):
                    self._error("déclaration d'îlot attendue après "
                                "'%s @'" % name)
                return

        # bascule liaisons (fiche 017) : for @bindings [as b] in ...
        if name == "for" and self.stmt_start and not self._sub:
            j = m.end()
            while j < self.n and t[j] in " \t":
                j += 1
            if t.startswith("@bindings", j) and (
                    j + 9 >= self.n or not _name_char(t[j + 9])):
                self._for_bindings_island()
                return

        # __namespaces__ dans __all__ : casserait la sérialisation de
        # l'importateur (fiche 013) — refusé explicitement.
        if name == "__all__" and self.stmt_start and not self._sub:
            stmt = self._stmt_text_ahead(m.end())
            if "'__namespaces__'" in stmt or '"__namespaces__"' in stmt:
                self._error("'__namespaces__' ne doit pas figurer dans "
                            "__all__ : il écraserait la table de préfixes "
                            "du module importateur (fiche 013)")

        # îlots à délimiteur collé
        if nxt == "{" and name in ("g", "f", "e", "s", "m"):
            if name == "g":
                self._graph_island()
                return
            if name == "s":
                self._sparql_island()
                return
            if name == "m":
                self._match_island()
                return
            if name == "f":
                mark = self._begin_island()
                gen = self._take_fnode()
                self._end_island("fnode", mark, gen)
                return
            mark = self._begin_island()
            gen = self._take_enode()
            self._end_island("enode", mark, gen)
            return
        if nxt == "<" and name in ("f", "e") and operand_here:
            if name == "e":
                mark = self._begin_island()
                gen = self._take_eiri()
                self._end_island("eiri", mark, gen)
                return
            saved = (self.i, self.src_line, self.src_col)
            mark = self._begin_island()
            gen = self._try_take_firi()
            if gen is not None:
                self._end_island("firi", mark, gen)
                return
            self.i, self.src_line, self.src_col = saved  # repli : comparaison

        # nœud anonyme hors îlot (fiches 002 et 021) : `_:{expr}` a un sens
        # partout — son identité vient de la valeur ; `_:label` n'en a pas,
        # car un label ne dit la CO-RÉFÉRENCE que dans une portée, et la
        # seule portée de labels du langage est l'îlot. Jusqu'ici les deux
        # étaient recopiés tels quels et le module émis ne compilait pas,
        # sans qu'aucune erreur ne soit levée.
        if name == "_" and nxt == ":" and operand_here \
                and self._bnode_free() and self._bnode_position():
            after = t[m.end() + 1] if m.end() + 1 < self.n else ""
            if after == "{":
                mark = self._begin_island()
                self._take(m.end() + 2 - self.i)     # '_:' puis '{'
                expr = self._scan_embedded_expr("}")
                if self._peek() != "}":
                    self._error("'}' attendu pour fermer _:{...}")
                self._take(1)
                self._end_island("bnode", mark, "%s.bnode((%s))"
                                 % (RUNTIME_ALIAS, expr.strip()))
                self.operand = False
                return
            if _ix_start(after):
                label = t[m.end() + 1:
                          _scan_pn_local_island(t, m.end() + 1, self.n)]
                self._error(
                    "nœud anonyme '_:%s' hors d'un îlot : une étiquette ne "
                    "désigne la co-référence qu'à l'intérieur d'un g{ … }. "
                    "Écrire _:{%r} pour un nœud dont l'identité vient de la "
                    "valeur, ou %s.BNode() pour un nœud frais."
                    % (label, label, "ldpy"))

        # pname hors îlot : préfixe déclaré, ':' collé, partie locale
        if operand_here and nxt == ":" and name in self.prefixes \
                and self._annotation_free():
            after = t[m.end() + 1] if m.end() + 1 < self.n else ""
            if _ix_start(after) or after == "{":
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
        # un préfixe déclaré qui sert AUSSI de nom Python : `{ex:b}` devient
        # alors un ensemble d'IRI là où Python lisait un dict (fiche 002).
        # Savoir où Python affecte un nom demanderait de le parser ; on s'en
        # tient à l'approximation retenue le 2026-08-29 — le nom en tête
        # d'instruction, suivi de '=' (hors '==') ou de ','.
        if self.stmt_start and self.depth == 0 and not self._sub \
                and name in self.prefixes and name not in self._shadowed:
            j = self._skip_ws_ahead(m.end())
            nx, nx2 = (t[j:j + 1], t[j + 1:j + 2])
            if (nx == "=" and nx2 != "=") or nx == ",":
                self._shadowed.add(name)
                self._warn("'%s' est à la fois un préfixe déclaré et un nom "
                           "Python : dans `{%s:x}` et `a[%s:x]`, le nom "
                           "préfixé l'emporte sur la lecture Python. Écrire "
                           "`{%s: x}` avec une espace force le dict."
                           % (name, name, name, name))

        if name == "lambda":
            self._lambda_depth = self.depth
        elif name == "def":
            self._after_def = True
        if self.stmt_start and self.depth == 0 \
                and name in COMPOUND_KEYWORDS:
            self._compound_header = True
        self._copy(len(name))
        if name in KEYWORDS:
            self.operand = name not in VALUE_KEYWORDS
        else:
            self.operand = False
        self.stmt_start = False

    def _annotation_free(self):
        """Sommes-nous ailleurs que dans une liste de paramètres ?

        `lambda ex:ex` et `def f(ex:int = 0)` sont du Python parfaitement
        valide, où le `:` appartient à Python. Ils ne figurent pas dans les
        ambiguïtés assumées de la fiche 002 — et jusqu'ici le transpileur y
        émettait du Python INVALIDE, sans lever d'erreur."""
        return self._lambda_depth is None \
            and (not self.brackets or self.brackets[-1] != "p")

    def _bnode_free(self):
        """Idem, mais un nœud anonyme n'a rien à faire non plus dans une
        valeur par défaut annotée — inutile de distinguer 'p' de 'P'."""
        return self._lambda_depth is None \
            and (not self.brackets or self.brackets[-1] not in "pP")

    def _bnode_position(self):
        """Un `_:` peut-il être un nœud anonyme ICI ?

        Non dans un dict/ensemble (`{_: v}`) ni dans un indice (`a[_:v]`) :
        `_` est le nom jetable de Python, personne n'a « déclaré » ce
        préfixe-là, et ces deux positions sont du Python parfaitement valide
        que R3 oblige à laisser passer. C'est aussi ce que colorent les
        grammaires (fiche 002 : pname/bnode absents des indices et des
        dict/set)."""
        return not self.brackets or self.brackets[-1] not in "{s"

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

    def _take_firi_parts(self):
        """Sur 'f<'. Consomme et retourne la liste de morceaux
        (True, texte statique) | (False, expr transpilée)."""
        self._take(2)
        parts = []
        static = []
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
        return parts

    def _firi_args(self, parts):
        args = ", ".join(repr(p[1]) if p[0] else "(%s)" % p[1] for p in parts)
        if self.base:
            return "%s, base=%r" % (args, self.base)
        return args

    def _take_firi(self):
        """Sur 'f<'. Consomme et retourne l'expression générée."""
        parts = self._take_firi_parts()
        if all(p[0] for p in parts):  # aucune interpolation : statique
            iri = "".join(p[1] for p in parts)
            return "%s.URIRef(%r)" % (RUNTIME_ALIAS, self._resolve(iri))
        return "%s.firi(%s)" % (RUNTIME_ALIAS, self._firi_args(parts))

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
        if in_island:
            end = _scan_pn_prefix(t, self.i, self.n)
        else:
            m = _PYNAME_RE.match(t, self.i)
            end = m.end() if m else self.i
        prefix = self._take(end - self.i) if end > self.i else ""
        if self._peek() != ":":
            self._error("':' attendu dans le nom préfixé")
        self._take(1)
        if prefix not in self.prefixes:
            self._undeclared_prefix(prefix)
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
                # PN_LOCAL exact (chiffres en tête, tirets, points intérieurs)
                ok = c != "" and (_pn_char(c) or c == "_")
                if not ok and c == ".":
                    # '.' intérieur seulement (pas la ponctuation Turtle)
                    nc = self._peek(1)
                    ok = nc != "" and (_pn_char(nc) or nc in ".{")
            else:
                # intersection identifiant Python ∩ PN_CHARS
                ok = c != "" and _ix_char(c)
            if not ok:
                break
            static.append(self._take(1))
        if static:
            parts.append((True, "".join(static)))
        if not parts and not in_island:
            self._error("partie locale attendue après '%s:'" % prefix)
        if isinstance(ns, DynPrefix):
            # préfixe dynamique : résolution à l'exécution (fiche 013)
            args = [ns.var]
            for is_static, val in parts:
                args.append(repr(val) if is_static else "(%s)" % val)
            return "%s.pname(%s)" % (RUNTIME_ALIAS, ", ".join(args))
        if all(p[0] for p in parts):
            local = "".join(p[1] for p in parts)
            return "%s.URIRef(%r)" % (RUNTIME_ALIAS, ns + local)
        # `ex:{expr}` EST un nom préfixé, pas une IRI formatée : même
        # concaténation, mais `pname` diffère l'évaluation quand la partie
        # locale porte une variable (fiche 017).
        args = [repr(ns)]
        for is_static, val in parts:
            args.append(repr(val) if is_static else "(%s)" % val)
        return "%s.pname(%s)" % (RUNTIME_ALIAS, ", ".join(args))

    # ------------------------------------------------------------------
    # import de préfixes (fiche 013)
    # ------------------------------------------------------------------

    def _stmt_text_ahead(self, j):
        """Texte de l'instruction logique à partir de j (sans consommer)."""
        t = self.text
        depth = 0
        k = j
        while k < self.n:
            c = t[k]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
            elif c == "\\" and k + 1 < self.n and t[k + 1] == "\n":
                k += 2
                continue
            elif depth <= 0 and c in "\n;#":
                break
            k += 1
        return t[j:k]

    def _import_has_prefix_item(self):
        """Sur 'from' en début d'instruction : la liste d'import
        contient-elle un nom préfixé (un ':' après le mot-clé import) ?

        Les commentaires sont retirés d'abord : une liste parenthésée les
        admet, et `# noqa: F401` porte un ':' sans qu'aucun préfixe ne soit
        importé. Une liste d'import ne peut pas contenir de littéral chaîne,
        donc retirer `#`→fin de ligne suffit. Hors commentaire, un ':' dans
        une liste d'import n'est jamais du Python légal."""
        stmt = _COMMENT_RE.sub("", self._stmt_text_ahead(self.i))
        m = re.search(r"\bimport\b", stmt)
        return m is not None and ":" in stmt[m.end():]

    def _take_prefix_import(self):
        """Consomme toute l'instruction from-import (self.i sur 'from') et
        émet l'import Python + la liaison des préfixes (fiche 013)."""
        decl_col = self.src_col
        decl_line = self.src_line
        mark = self._begin_island()
        t = self.text
        start_i = self.i
        self._take(4)                                    # 'from'
        self._g_ws()
        mod_start = self.i
        while self.i < self.n and not t.startswith("import", self.i):
            if t[self.i] == "\n":
                self._error("mot-clé 'import' attendu dans l'instruction from")
            self._take(1)
        module = t[mod_start:self.i].strip()
        if not module:
            self._error("nom de module attendu après 'from'")
        self._take(6)                                    # 'import'
        self._imp_ws(paren=False)
        paren = False
        if self._peek() == "(":
            self._take(1)
            paren = True
            self._imp_ws(paren)
        py_items = []
        prefix_items = []                                # (source, cible)
        while True:
            c = self._peek()
            if c == "":
                self._error("liste d'import non terminée")
            if c == "*":
                self._take(1)
                py_items.append("*")
            else:
                start = self.i
                pn_end = _scan_pn_prefix(t, self.i, self.n)
                pym = _PYNAME_RE.match(t, self.i)
                if pn_end > self.i and pn_end < self.n and t[pn_end] == ":":
                    name = self._take(pn_end - self.i)
                    self._take(1)                        # ':'
                    alias = None
                    save = (self.i, self.src_line, self.src_col)
                    self._imp_ws(paren)
                    if t.startswith("as", self.i) and not _name_char(
                            self._peek(2)):
                        self._take(2)
                        self._imp_ws(paren)
                        a_end = _scan_pn_prefix(t, self.i, self.n)
                        if a_end == self.i:
                            self._error("nom de préfixe attendu après 'as'")
                        alias = self._take(a_end - self.i)
                        if self._peek() != ":":
                            self._error("l'alias d'un préfixe s'écrit "
                                        "'%s:' — avec le ':'" % alias)
                        self._take(1)
                    else:
                        self.i, self.src_line, self.src_col = save
                    prefix_items.append((name, alias or name))
                elif pym:
                    name = self._take(pym.end() - self.i)
                    item = name
                    save = (self.i, self.src_line, self.src_col)
                    self._imp_ws(paren)
                    if t.startswith("as", self.i) and not _name_char(
                            self._peek(2)):
                        self._take(2)
                        self._imp_ws(paren)
                        am = _PYNAME_RE.match(t, self.i)
                        if not am:
                            self._error("nom attendu après 'as'")
                        item += " as " + self._take(am.end() - self.i)
                    else:
                        self.i, self.src_line, self.src_col = save
                    py_items.append(item)
                else:
                    self._error("élément d'import attendu")
            self._imp_ws(paren)
            if self._peek() == ",":
                self._take(1)
                self._imp_ws(paren)
                if paren and self._peek() == ")":
                    self._take(1)
                    break
                continue
            if paren:
                if self._peek() != ")":
                    self._error("')' attendu dans la liste d'import")
                self._take(1)
            break
        # liaison lexicale des préfixes importés (portée par bloc)
        self._ns_counter += 1
        nsvar = "_ldpy_nsi%d" % self._ns_counter
        binds = []
        updates = []
        for source, target in prefix_items:
            if target in self.prefixes and target in self._prefix_used \
                    and decl_col <= self._prefix_col.get(target, 0):
                self._warn("redéclaration du préfixe '%s:' après usage "
                           "(import de %s)" % (target, module))
            if decl_col > 0:
                self._scope_stack.append((decl_col, "prefix", target,
                                          target in self.prefixes,
                                          (self.prefixes.get(target),
                                           self._prefix_col.get(target))))
            var = self._fresh_ns_var(target)
            self.prefixes[target] = DynPrefix(var)
            self._prefix_col[target] = decl_col
            binds.append("%s = %s[%r]" % (var, nsvar, source))
            updates.append("%r: %s" % (target, var))
        if not prefix_items:
            # aucun préfixe finalement : l'instruction est du Python ordinaire
            # et doit ressortir telle quelle (transparence de l'hôte, R3).
            self._put(t[start_i:self.i])
            if not self._sub:
                sl, sc, gl, gc = mark
                self.map.add("copy", (sl, sc, self.src_line, self.src_col),
                             (gl, gc, self.gen_line, self.gen_col))
            self.operand = False
            self.stmt_start = False
            return
        self._import_lines.append((decl_line, module))
        items = py_items + ["__namespaces__ as %s" % nsvar]
        gen = "; ".join(["from %s import %s" % (module, ", ".join(items))]
                        + binds
                        + ["__namespaces__.update({%s})" % ", ".join(updates)])
        self._end_island("import", mark, gen)

    def _imp_ws(self, paren):
        """Blancs dans une liste d'import : continuations '\\'-newline
        partout, newlines et commentaires seulement entre parenthèses."""
        t = self.text
        while self.i < self.n:
            c = t[self.i]
            if c in " \t\r":
                self._take(1)
            elif c == "\\" and self._peek(1) == "\n":
                self._take(2)
            elif paren and c == "\n":
                self._take(1)
            elif paren and c == "#":
                j = t.find("\n", self.i)
                self._take((j if j != -1 else self.n) - self.i)
            else:
                break

    # ------------------------------------------------------------------
    # @prefix / @base
    # ------------------------------------------------------------------

    def _try_prefix_or_base(self, scope_mode=None):
        """Sur '@' en début d'instruction. Tente l'îlot déclaration.
        Retourne True si consommé (sinon rien n'est consommé).
        scope_mode : None, 'global' ou 'nonlocal' (fiche 018)."""
        t = self.text
        m = re.match(r"@(prefix|base|graph|bindings)\b", t[self.i:self.i + 10])
        if not m:
            return False
        kind = m.group(1)
        if kind == "graph":
            return self._try_graph_decl(scope_mode)
        if kind == "bindings":
            return self._try_bindings_decl(scope_mode)
        # une « déclaration ratée » (préfixe non ASCII, ponctuation absente…)
        # ne doit PAS retomber silencieusement sur le cas décorateur : la fin
        # de ligne déclencherait des îlots et produirait du code massacré.
        eol = t.find("\n", self.i)
        line_rest = t[self.i:eol if eol != -1 else self.n]
        looks_like_decl = re.search(r"<[^<>\s]*>\s*\.\s*$", line_rest)
        # validation en avant (sans consommer)
        j = self.i + 1 + len(kind)
        j = self._skip_ws_ahead(j)
        prefix = None
        if kind == "prefix":
            jend = _scan_pn_prefix(t, j, self.n)
            prefix = t[j:jend]
            j = jend
            if j >= self.n or t[j] != ":":
                if looks_like_decl:
                    self._error("déclaration @prefix invalide — le nom de "
                                "préfixe doit suivre PN_PREFIX de Turtle "
                                "(docs/reference/language.md)")
                return False  # décorateur nommé prefix
            j = self._skip_ws_ahead(j + 1)
        if kind == "prefix" and t[j:j + 2] == "f<":
            # IRI calculée : préfixe dynamique (fiche 013). `@prefix ex: f<`
            # n'est jamais un début de ligne Python valide : on s'engage.
            return self._prefix_firi_decl(j, prefix, scope_mode)
        if j >= self.n or t[j] != "<":
            if looks_like_decl:
                self._error("déclaration @%s invalide — IRI '<...>' attendue"
                            % kind)
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
            self._scope_install("base", None, resolved, decl_col, scope_mode)
            gen = "__base__ = %r" % resolved
            if scope_mode:
                gen = "%s __base__; %s" % (scope_mode, gen)
        else:
            # redéclaration au même niveau après usage : warning ;
            # shadowing dans un bloc plus profond : légitime, silencieux.
            if scope_mode is None and prefix in self.prefixes \
                    and prefix in self._prefix_used \
                    and self.prefixes[prefix] != resolved \
                    and decl_col <= self._prefix_col.get(prefix, 0):
                # un global/nonlocal est une réassignation voulue : pas
                # d'avertissement (fiche 018, « comme global x; x = 1 »)
                self._warn("redéclaration du préfixe '%s:' après usage "
                           "(nouvelle IRI : %s)" % (prefix, resolved))
            self._scope_install("prefix", prefix, resolved, decl_col,
                                scope_mode)
            gen = "__namespaces__[%r] = %s.Namespace(%r)" % (
                prefix, RUNTIME_ALIAS, resolved)
        self._end_island(kind, mark, gen)
        return True

    def _prefix_firi_decl(self, j, prefix, scope_mode=None):
        """Consomme `@prefix p: f<...> .` (self.i sur '@', j sur 'f').
        Sans interpolation : déclaration statique ordinaire. Avec : préfixe
        dynamique, résolu à l'exécution par une variable fraîche."""
        decl_col = self.src_col
        mark = self._begin_island()
        self._take(j - self.i)              # '@prefix p:' + blancs
        parts = self._take_firi_parts()
        self._g_ws()
        if self._peek() != ".":
            self._error("'.' attendu pour clore la déclaration @prefix")
        self._take(1)
        if scope_mode is None and prefix in self.prefixes \
                and prefix in self._prefix_used \
                and decl_col <= self._prefix_col.get(prefix, 0):
            prev = self.prefixes[prefix]
            static_same = (all(p[0] for p in parts) and isinstance(prev, str)
                           and prev == self._resolve(
                               "".join(p[1] for p in parts)))
            if not static_same:
                self._warn("redéclaration du préfixe '%s:' après usage"
                           % prefix)
        if all(p[0] for p in parts):        # aucune interpolation : statique
            resolved = self._resolve("".join(p[1] for p in parts))
            self._scope_install("prefix", prefix, resolved, decl_col,
                                scope_mode)
            gen = "__namespaces__[%r] = %s.Namespace(%r)" % (
                prefix, RUNTIME_ALIAS, resolved)
        else:
            # global/nonlocal : réutiliser la variable de la liaison cible si
            # elle est dynamique — c'est elle que les usages du dehors lisent
            prev = self.prefixes.get(prefix)
            if scope_mode and isinstance(prev, DynPrefix):
                var = prev.var
            else:
                var = self._fresh_ns_var(prefix)
            self._scope_install("prefix", prefix, DynPrefix(var), decl_col,
                                scope_mode)
            gen = "%s = %s.Namespace(%s.firi(%s)); __namespaces__[%r] = %s" % (
                var, RUNTIME_ALIAS, RUNTIME_ALIAS,
                self._firi_args(parts), prefix, var)
            if scope_mode:
                gen = "%s %s; %s" % (scope_mode, var, gen)
        self._end_island("prefix", mark, gen)
        return True

    def _scope_install(self, kind, name, value, decl_col, mode):
        """Installe une liaison de déclaration d'îlot (fiches 004/018).

        mode None : portée par bloc (pile) ; 'global' : portée module, les
        entrées de pile restaureront la nouvelle valeur ; 'nonlocal' : la
        portée englobante déclarante la plus proche, erreur s'il n'y en a
        pas — la sémantique de Python, appliquée aux déclarations."""
        def setval(v):
            if kind == "prefix":
                self.prefixes[name] = v
            elif kind == "base":
                self.base = v
            elif kind == "graph":
                self._graph_var = v
            else:
                self._bindings_var = v

        if mode is None:
            if decl_col > 0:
                if kind == "prefix":
                    self._scope_stack.append(
                        (decl_col, kind, name, name in self.prefixes,
                         (self.prefixes.get(name),
                          self._prefix_col.get(name))))
                elif kind == "base":
                    self._scope_stack.append((decl_col, kind, None,
                                              True, self.base))
                elif kind == "graph":
                    self._scope_stack.append((decl_col, kind, None,
                                              True, self._graph_var))
                else:
                    self._scope_stack.append((decl_col, kind, None,
                                              True, self._bindings_var))
            setval(value)
            if kind == "prefix":
                self._prefix_col[name] = decl_col
            return
        matches = [i for i, e in enumerate(self._scope_stack)
                   if e[1] == kind and (kind != "prefix" or e[2] == name)]
        if mode == "nonlocal":
            encl = [i for i in matches
                    if self._scope_stack[i][0] < decl_col]
            if not encl:
                what = "prefix %s:" % name if kind == "prefix" else kind
                self._error("nonlocal @%s : aucune déclaration englobante "
                            "(comme le nonlocal de Python)" % what,
                            incomplete=False)
            keep = encl[-1]
            target_col = self._scope_stack[keep][0]
            touched = [i for i in matches if i > keep]
        else:                                       # global
            keep = None
            target_col = 0
            touched = matches
        for i in touched:
            col, k, n, _, _ = self._scope_stack[i]
            newprev = ((value, target_col) if kind == "prefix" else value)
            self._scope_stack[i] = (col, k, n, True, newprev)
        setval(value)
        if kind == "prefix":
            self._prefix_col[name] = target_col

    def _enclosing_value(self, kind, name, decl_col):
        """Valeur (variable émise) visible dans la portée englobante
        déclarante la plus proche — la cible d'un nonlocal (fiche 018).
        None si aucune déclaration englobante."""
        matches = [i for i, e in enumerate(self._scope_stack)
                   if e[1] == kind and (kind != "prefix" or e[2] == name)]
        encl = [i for i in matches if self._scope_stack[i][0] < decl_col]
        if not encl:
            return None
        above = [i for i in matches if i > encl[-1]]
        if above:
            prev = self._scope_stack[above[0]][4]
            return prev[0] if kind == "prefix" else prev
        if kind == "prefix":
            return self.prefixes.get(name)
        if kind == "graph":
            return self._graph_var
        return self._bindings_var

    def _unwind_scopes(self, col):
        """Ferme les portées des déclarations plus indentées que l'instruction
        qui commence à la colonne `col` (fin de leur bloc)."""
        while self._scope_stack and col < self._scope_stack[-1][0]:
            _, kind, name, had, prev = self._scope_stack.pop()
            if kind == "base":
                self.base = prev
            elif kind == "graph":
                self._graph_var = prev
            elif kind == "bindings":
                self._bindings_var = prev
            elif had:
                self.prefixes[name], self._prefix_col[name] = prev
            else:
                self.prefixes.pop(name, None)
                self._prefix_col.pop(name, None)
                self._retired.setdefault(name, self.src_line)

    def _fresh_ns_var(self, name):
        """Variable Python fraîche portant un namespace dynamique."""
        self._ns_counter += 1
        safe = "".join(c if c.isascii() and (c.isalnum() or c == "_") else "_"
                       for c in name)
        return "_ldpy_ns_%s_%d" % (safe, self._ns_counter)

    def _undeclared_prefix(self, prefix):
        msg = "préfixe non déclaré : '%s:'" % prefix
        if self._import_lines:
            hints = ", ".join("ligne %d (from %s import ...)" % (ln + 1, mod)
                              for ln, mod in self._import_lines)
            msg += (" — peut-être manque-t-il à une liste d'import de "
                    "préfixes : %s" % hints)
        self._error(msg)

    def _skip_ws_ahead(self, j):
        t = self.text
        while j < self.n and t[j] in " \t\r\n":
            j += 1
        return j

    # ------------------------------------------------------------------
    # graphe courant : @graph, +{ }, -{ } (fiche 014)
    # ------------------------------------------------------------------

    def _fresh_var(self, stem):
        self._ns_counter += 1
        return "_ldpy_%s%d" % (stem, self._ns_counter)

    def _try_graph_decl(self, scope_mode=None):
        """Sur '@' devant 'graph' en début d'instruction. Désigne ou crée le
        graphe courant. Un décorateur reste un décorateur : '@graph' suivi de
        '(', '.', '[', d'une fin de ligne — ou d'une parenthèse après blancs —
        n'est pas un îlot."""
        t = self.text
        j = self.i + 6                              # après '@graph'
        if j < self.n and t[j] not in " \t":
            return False                            # @graph( . [ … décorateur
        while j < self.n and t[j] in " \t":
            j += 1
        if j >= self.n or t[j] in "\n\r#(":
            return False                            # décorateur nu (ou appel)
        decl_col = self.src_col
        mark = self._begin_island()
        self._take(j - self.i)                      # '@graph' + blancs
        user_name = None                            # nom écrit après 'as'
        if t.startswith("as", self.i) and not _name_char(self._peek(2)):
            self._take(2)
            user_name = self._graph_decl_as_name()
            rhs = "%s.new_graph(__namespaces__, %s)" % (
                RUNTIME_ALIAS, repr(self.base) if self.base else "None")
        else:
            ident = None
            c = self._peek()
            if c == "<" and self._iriref_end(self.i) is not None:
                iri = self._take_iriref()
                ident = "%s.URIRef(%r)" % (RUNTIME_ALIAS, self._resolve(iri))
            elif c == "f" and self._peek(1) == "<":
                ident = self._take_firi()
            else:
                m2 = _PYNAME_RE.match(t, self.i)
                if m2 and m2.group(0) in self.prefixes \
                        and t[m2.end():m2.end() + 1] == ":":
                    ident = self._take_pname(in_island=False)
            if ident is not None:
                self._graph_ws_inline()
                if not (t.startswith("as", self.i)
                        and not _name_char(self._peek(2))):
                    self._error("'as' attendu : '@graph <iri> as g' crée un "
                                "graphe nommé ; pour désigner un graphe "
                                "existant, écrire '@graph expression'")
                self._take(2)
                user_name = self._graph_decl_as_name()
                rhs = "%s.new_graph(__namespaces__, %s, identifier=%s)" % (
                    RUNTIME_ALIAS,
                    repr(self.base) if self.base else "None", ident)
            else:
                expr = self._scan_embedded_expr("\n#").strip()
                if not expr:
                    self._error("expression attendue après '@graph'")
                if "\n" in expr:
                    self._error("l'expression de '@graph' tient sur sa ligne")
                rhs = "(%s)" % expr
        self._graph_ws_inline()
        if self._peek() not in "\n\r#;" and self._peek() != "":
            self._error("fin de ligne attendue après la déclaration @graph")
        gvar, gen = self._compose_decl("graph", None, user_name, rhs,
                                       decl_col, scope_mode, "g")
        self._scope_install("graph", None, gvar, decl_col, scope_mode)
        self._end_island("graph-decl", mark, gen)
        return True

    def _compose_decl(self, kind, name, user_name, rhs, decl_col, mode, stem):
        """Compose l'émission d'une déclaration @graph/@bindings selon la
        portée visée (fiche 018) : nonlocal réutilise la variable de la
        liaison englobante — c'est elle que le code du dehors lit."""
        if mode == "nonlocal":
            target = self._enclosing_value(kind, name, decl_col)
            if target is None:
                # _scope_install produira l'erreur avec le bon message
                self._scope_install(kind, name, None, decl_col, mode)
            lhs = ([user_name, target] if user_name and user_name != target
                   else [target])
            return target, "nonlocal %s; %s = %s" % (
                target, " = ".join(lhs), rhs)
        var = user_name if user_name else self._fresh_var(stem)
        gen = "%s = %s" % (var, rhs)
        if mode == "global":
            gen = "global %s; %s" % (var, gen)
        return var, gen

    def _graph_decl_as_name(self):
        """Après 'as' : le nom Python créé par la déclaration."""
        self._graph_ws_inline()
        m = _PYNAME_RE.match(self.text, self.i)
        if not m:
            self._error("nom attendu après 'as'")
        return self._take(m.end() - self.i)

    def _graph_ws_inline(self):
        while self._peek() in (" ", "\t"):
            self._take(1)

    def _addremove_island(self, sign):
        """Sur '+{' ou '-{' en position d'instruction : ajout ou retrait
        sur le graphe courant (fiche 014), ou sur le contexte donné par le
        suffixe d'appel — graphe d'abord, binding ensuite (fiche 019)."""
        mark = self._begin_island()
        self._take(2)                               # signe + '{'
        triples, gctx = self._g_parse_triples()
        triples = _share_impure(triples, gctx)
        sfx_graph = sfx_bindings = None
        if self._peek() == "(":                     # adjacence stricte (R2)
            sfx_graph, sfx_bindings = self._call_suffix()
        gvar = sfx_graph if sfx_graph else self._graph_var
        if gvar is None:
            self._error("'%s{ ... }' sans graphe courant : déclarez-le avec "
                        "'@graph <expression>' ou '@graph as g' (fiche 014), "
                        "ou donnez-le en suffixe — %s{ ... }(g)"
                        % (sign, sign), incomplete=False)
        bvar = sfx_bindings if sfx_bindings else self._bindings_var
        fn = "add_to" if sign == "+" else "remove_from"
        args = [gvar]
        args += ["(%s, %s, %s)" % tr for tr in triples]
        gen = "%s.%s(%s%s)" % (RUNTIME_ALIAS, fn, ", ".join(args),
                               ", bindings=%s" % bvar if bvar else "")
        self._end_island("addto" if sign == "+" else "removefrom", mark, gen)

    def _call_suffix(self):
        """Sur '(' collé après un îlot-instruction : la liste d'opérandes
        de contexte — (graphe), (graphe, binding), (bindings=binding)."""
        self._take(1)
        self._g_ws()
        graph_expr = bindings_expr = None
        if self._peek() == ")":
            self._take(1)
            return None, None
        if self._suffix_bindings_kw():
            bindings_expr = "(%s)" % self._scan_embedded_expr(")").strip()
        else:
            graph_expr = "(%s)" % self._scan_embedded_expr(",)").strip()
            if self._peek() == ",":
                self._take(1)
                self._g_ws()
                self._suffix_bindings_kw()          # 'bindings=' optionnel
                bindings_expr = "(%s)" % self._scan_embedded_expr(")").strip()
        if self._peek() != ")":
            self._error("')' attendu pour clore le suffixe d'appel")
        self._take(1)
        return graph_expr, bindings_expr

    def _suffix_bindings_kw(self):
        """Consomme 'bindings=' s'il est là (et pas 'bindings==')."""
        t = self.text
        j = self.i
        if not t.startswith("bindings", j):
            return False
        j += 8
        while j < self.n and t[j] in " \t":
            j += 1
        if j >= self.n or t[j] != "=" or t[j + 1:j + 2] == "=":
            return False
        self._take(j + 1 - self.i)
        self._g_ws()
        return True

    # ------------------------------------------------------------------
    # binding courant : @bindings, for @bindings in (fiche 017)
    # ------------------------------------------------------------------

    def _bkw(self):
        """Suffixe d'argument bindings= pour les îlots consommateurs."""
        if self._bindings_var:
            return ", bindings=%s" % self._bindings_var
        return ""

    def _try_bindings_decl(self, scope_mode=None):
        """Sur '@' devant 'bindings' en début d'instruction. Désigne ou
        crée le binding courant — le parallèle exact de @graph."""
        t = self.text
        j = self.i + 9                              # après '@bindings'
        if j < self.n and t[j] not in " \t":
            return False
        while j < self.n and t[j] in " \t":
            j += 1
        if j >= self.n or t[j] in "\n\r#(":
            return False
        decl_col = self.src_col
        mark = self._begin_island()
        self._take(j - self.i)
        user_name = None
        if t.startswith("as", self.i) and not _name_char(self._peek(2)):
            self._take(2)
            user_name = self._graph_decl_as_name()
            rhs = "%s.Bindings()" % RUNTIME_ALIAS
        else:
            expr = self._scan_embedded_expr("\n#").strip()
            if not expr:
                self._error("expression attendue après '@bindings'")
            if "\n" in expr:
                self._error("l'expression de '@bindings' tient sur sa ligne")
            rhs = "(%s)" % expr
        self._graph_ws_inline()
        if self._peek() not in "\n\r#;" and self._peek() != "":
            self._error("fin de ligne attendue après la déclaration "
                        "@bindings")
        bvar, gen = self._compose_decl("bindings", None, user_name, rhs,
                                       decl_col, scope_mode, "b")
        self._scope_install("bindings", None, bvar, decl_col, scope_mode)
        self._end_island("bindings-decl", mark, gen)
        return True

    def _for_bindings_island(self):
        """Sur 'for' suivi de '@bindings' : la bascule graphes -> liaisons.
        `for @bindings [as b] in ITER:` — chaque élément de l'itérable
        devient le binding courant du corps de la boucle (fiche 017)."""
        decl_col = self.src_col
        mark = self._begin_island()
        t = self.text
        self._take(3)                               # 'for'
        self._graph_ws_inline()
        self._take(9)                               # '@bindings'
        self._graph_ws_inline()
        if t.startswith("as", self.i) and not _name_char(self._peek(2)):
            self._take(2)
            bvar = self._graph_decl_as_name()
            self._graph_ws_inline()
        else:
            bvar = self._fresh_var("b")
        if not (t.startswith("in", self.i) and not _name_char(self._peek(2))):
            self._error("'in' attendu dans 'for @bindings [as b] in ...'")
        self._take(2)
        self._end_island("for-bindings", mark,
                         "for %s in %s.as_bindings_iter(" % (
                             bvar, RUNTIME_ALIAS))
        # l'itérable : scan normal (îlots inclus), jusqu'au ':' du for
        self._scan(stops=":", entry_depth=self.depth)
        if self._peek() != ":":
            self._error("':' attendu pour clore l'en-tête du for")
        self._close_copy()
        mark2 = self._begin_island()
        self._take(1)
        self._end_island("for-bindings-close", mark2, "):")
        # portée : le corps de la boucle
        self._scope_stack.append((decl_col + 1, "bindings", None,
                                  True, self._bindings_var))
        self._bindings_var = bvar

    # ------------------------------------------------------------------
    # graphes g{ ... }
    # ------------------------------------------------------------------

    def _g_parse_triples(self):
        """Collects the island's terms as `parts` while parsing it.

        Saved and restored around the call, because an interpolation can
        hold another island: `g{ ex:p f{ g{ ... } } }` runs a whole inner
        island — `_end_island` included — in the middle of the outer one.
        The finished list waits in `_pending_parts` for the `_end_island`
        that closes THIS island; an inner island finds it None and attaches
        nothing, which is what keeps the two from stealing each other's
        terms.
        """
        saved = self._parts
        self._parts = []
        try:
            return self._g_parse_triples_inner()
        finally:
            self._pending_parts, self._parts = self._parts, saved

    def _g_parse_triples_inner(self):
        """Corps d'îlot de graphe : self.i juste après le '{' ouvrant.
        Consomme jusqu'au '}' fermant inclus ; retourne (triples, gctx)."""
        gctx = _GraphCtx()
        triples = []
        self._g_ws()
        while self._peek() != "}":
            if self._peek() == "":
                self._error("'}' attendu pour fermer l'îlot de graphe")
            self._g_triples(triples, gctx)
            self._g_ws()
            if self._peek() == ".":
                self._take(1)
                self._g_ws()
                continue
            break
        if self._peek() != "}":
            self._error("'}' attendu pour fermer l'îlot de graphe")
        self._take(1)
        return triples, gctx

    def _graph_island(self):
        mark = self._begin_island()
        self._take(2)  # g{
        triples, gctx = self._g_parse_triples()
        triples = _share_impure(triples, gctx)
        base_repr = repr(self.base) if self.base else "None"
        args = ["__namespaces__", base_repr]
        args += ["(%s, %s, %s)" % tr for tr in triples]
        gen = "%s.graph(%s%s)" % (RUNTIME_ALIAS, ", ".join(args),
                                  self._bkw())
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
                # Turtle 1.1 : predicateObjectList autorise des ';'
                # surnuméraires, aussi bien entre deux paires prédicat-objet
                # qu'en fin de liste — y compris devant le ']' d'un nœud
                # anonyme, qui manquait aux terminateurs (fiche ldpy/012).
                while self._peek() == ";":
                    self._take(1)
                    self._g_ws()
                if self._peek() in "}.]" or self._peek() == "":
                    return
                continue
            return

    def _g_verb(self, triples, gctx):
        """Records the predicate as a `part`, then parses it — the sibling
        of the wrapper on `_g_node`, for the position `_g_node` never sees."""
        if self._parts is None or self._sub:
            return self._g_verb_inner(triples, gctx)
        sl, sc, i0 = self.src_line, self.src_col, self.i
        gen = self._g_verb_inner(triples, gctx)
        # `a` is Turtle's rdf:type shorthand, not a prefixed name: no kind
        # of its own, so the island's hover answers for it
        kind = (None if self.text[i0:self.i].strip() == "a"
                else _term_kind(self.text[i0:self.i]))
        if kind is not None:
            self._parts.append(
                (kind, (sl, sc, self.src_line, self.src_col), gen))
        return gen

    def _g_verb_inner(self, triples, gctx):
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
        if c == "e" and self._peek(1) in "{<":
            if self._match_vars is not None:
                self._error("e{ } dans m{ } : les filtres d'appariement sont "
                            "hors périmètre (fiche 017)")
            taker = (self._take_enode if self._peek(1) == "{"
                     else self._take_eiri)
            return _impure(taker(), gctx)
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
            return _impure(self._interp_with_suffix(expr), gctx)
        m = _NAME_RE.match(self.text, self.i)
        if not m:
            self._error("nom de variable attendu après '%s'" % sigil)
        name = self._take(len(m.group(0)))
        if self._match_vars is not None and name not in self._match_vars:
            self._match_vars.append(name)
        return "%s.Variable(%r)" % (RUNTIME_ALIAS, name)

    def _g_node(self, triples, gctx):
        """Records the term as a `part` of the island, then parses it.

        `_g_parse_triples` opens the list; everything a composite island
        contains comes through here, so this one wrapper gives `g{ }`,
        `m{ }`, `+{ }` and `-{ }` a hover per term (record vscode/108)
        without touching the flat language map."""
        if self._parts is None or self._sub:
            return self._g_node_inner(triples, gctx)
        sl, sc, i0 = self.src_line, self.src_col, self.i
        gen, composite = self._g_node_inner(triples, gctx)
        kind = _term_kind(self.text[i0:self.i])
        if kind is not None:
            self._parts.append(
                (kind, (sl, sc, self.src_line, self.src_col), gen))
        return gen, composite

    def _g_node_inner(self, triples, gctx):
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
            if self._peek() == "{":
                # _:{expr} : bnode à identité déterministe issue des données
                self._take(1)
                expr = self._scan_embedded_expr("}")
                if self._peek() != "}":
                    self._error("'}' attendu pour fermer _:{...}")
                self._take(1)
                return _impure("%s.bnode((%s))" % (RUNTIME_ALIAS,
                                                   expr.strip()), gctx), False
            end = _scan_pn_local_island(t, self.i, self.n)
            if end == self.i:
                self._error("étiquette de nœud anonyme attendue après '_:'")
            label = self._take(end - self.i)
            return gctx.labeled_bnode(label), False
        if c == "{":
            self._take(1)
            expr = self._scan_embedded_expr("}")
            if self._peek() != "}":
                self._error("'}' attendu")
            self._take(1)
            return _impure(self._interp_with_suffix(expr), gctx), False
        if c in "?$":
            term = self._g_var(gctx)
            return term, False
        if c == "<":
            iri = self._take_iriref()
            return "%s.URIRef(%r)" % (RUNTIME_ALIAS, self._resolve(iri)), False
        if c == "f" and self._peek(1) == "<":
            return _maybe_impure(self._take_firi(), gctx), False
        if c == "f" and self._peek(1) == "{":
            return _impure(self._take_fnode(), gctx), False
        if c == "e" and self._peek(1) in "{<":
            # expression différée en position de terme (fiches 007/017)
            if self._match_vars is not None:
                self._error("e{ } dans m{ } : les filtres d'appariement sont "
                            "hors périmètre (fiche 017)")
            taker = (self._take_enode if self._peek(1) == "{"
                     else self._take_eiri)
            return _impure(taker(), gctx), False
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

    def _interp_with_suffix(self, expr):
        """Terme interpolé de graphe, avec suffixe RDF optionnel COLLÉ :
        {expr}@lang -> Literal(expr, lang=...) ; {expr}^^dt -> Literal(expr,
        datatype=dt) ; sinon node(expr).."""
        expr = expr.strip()
        if self._peek() == "@":
            m = _LANGTAG_RE.match(self.text, self.i)
            if m:
                self._take(m.end() - self.i)
                return "%s.Literal((%s), lang=%r)" % (
                    RUNTIME_ALIAS, expr, m.group(1))
        if self.text[self.i:self.i + 2] == "^^":
            self._take(2)
            dt = self._parse_term_after_hats()
            return "%s.Literal((%s), datatype=%s)" % (RUNTIME_ALIAS, expr, dt)
        return "%s.node((%s))" % (RUNTIME_ALIAS, expr)

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
    # îlot de motif m{ ... } (fiche 016)
    # ------------------------------------------------------------------

    def _match_island(self):
        """Sur 'm{'. Un BGP en syntaxe Turtle, à variables, évalué contre
        le graphe courant : rend des termes (arité 1) ou des lignes
        (arité >= 2). Projection = ordre de première apparition ; un nœud
        anonyme est une variable non distinguée."""
        mark = self._begin_island()
        saved_vars, self._match_vars = self._match_vars, []
        try:
            self._take(2)                           # m{
            triples, gctx = self._g_parse_triples()
            projected = list(self._match_vars)
        finally:
            self._match_vars = saved_vars
        triples = _share_impure(triples, gctx)
        gvar = self._graph_var if self._graph_var else "None"
        pats = ", ".join("(%s, %s, %s)" % tr for tr in triples)
        proj = ", ".join(repr(v) for v in projected)
        gen = "%s.match(%s, (%s,), (%s%s)%s)" % (
            RUNTIME_ALIAS, gvar, pats,
            proj, "," if projected else "", self._bkw())
        self._end_island("match", mark, gen)

    # ------------------------------------------------------------------
    # îlot SPARQL s{ ... } (fiche 015)
    # ------------------------------------------------------------------

    _S_UPDATE_RE = re.compile(
        r"\s*(?:INSERT|DELETE|CLEAR|DROP|CREATE|LOAD|COPY|MOVE|ADD|WITH)\b",
        re.I)

    def _sparql_island(self):
        """Sur 's{'. Tout SPARQL : l'îlot ne lexe que les interpolations,
        les chaînes et l'équilibre des accolades ; rdflib valide à la
        transpilation (l'oracle, fiche 015)."""
        mark = self._begin_island()
        isl_line, isl_col = self.src_line, self.src_col
        self._take(2)                                   # s{
        t = self.text
        pieces = []
        interps = []                                    # exprs transpilées
        depth = 0
        while True:
            c = self._peek()
            if c == "":
                self._error("'}' attendu pour fermer s{...}")
            if c == "}":
                if depth == 0:
                    self._take(1)
                    break
                depth -= 1
                pieces.append(self._take(1))
            elif c in "\"'":
                end = self._string_end(self.i)
                pieces.append(self._take(end - self.i))
            elif c == "#":
                j = t.find("\n", self.i)
                pieces.append(self._take((j if j != -1 else self.n) - self.i))
            elif c == "{":
                inner = self._sparql_brace_content(self.i)
                if inner is not None and self._is_ldpy_expression(inner):
                    # interpolation en position de terme
                    self._take(1)
                    expr = self._scan_embedded_expr("}")
                    if self._peek() != "}":
                        self._error("'}' attendu pour fermer l'interpolation")
                    self._take(1)
                    name = "__i%d" % len(interps)
                    interps.append(expr.strip())
                    pieces.append(" ?%s " % name)
                else:
                    depth += 1
                    pieces.append(self._take(1))
            else:
                pieces.append(self._take(1))
        text = "".join(pieces).strip()
        if not text:
            self._error("requête vide dans s{ }", isl_line, isl_col)
        is_update = bool(self._S_UPDATE_RE.match(text))
        self._validate_sparql(text, is_update, isl_line, isl_col)
        gvar = self._graph_var if self._graph_var else "None"
        iargs = ", ".join("(%r, (%s))" % ("__i%d" % k, e)
                          for k, e in enumerate(interps))
        gen = ("%s.prepared(%r, (%s), __namespaces__, %s, graph=%s%s, "
               "update=%r)" % (RUNTIME_ALIAS, text,
                               iargs + "," if iargs else "",
                               repr(self.base) if self.base else "None",
                               gvar, self._bkw(), is_update))
        self._end_island("sparql", mark, gen)

    def _sparql_brace_content(self, i):
        """Contenu du bloc {...} équilibré commençant en i (sans consommer),
        ou None si non fermé."""
        t = self.text
        depth = 0
        j = i
        while j < self.n:
            c = t[j]
            if c in "\"'":
                saved = (self.src_line, self.src_col)
                try:
                    j = self._string_end(j)
                except LdpySyntaxError:
                    return None
                self.src_line, self.src_col = saved
                continue
            if c == "#":
                k = t.find("\n", j)
                j = k if k != -1 else self.n
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return t[i + 1:j]
            j += 1
        return None

    def _is_ldpy_expression(self, text):
        """L'oracle interpolation/groupe : le texte est-il une expression
        ldpy (transpilable puis compilable en 'eval') ? Un groupe SPARQL ne
        l'est jamais ; une interpolation l'est par définition."""
        if not text.strip():
            return False
        sub = Transpiler(text, self.filename, emit_prelude=False)
        sub.prefixes = dict(self.prefixes)
        sub.base = self.base
        try:
            code = sub.run().code.strip()
            compile("(%s)" % code, "<interp>", "eval")
            return True
        except (LdpySyntaxError, SyntaxError, ValueError):
            return False

    def _validate_sparql(self, text, is_update, line, col):
        """Valide la requête à la transpilation, rdflib en oracle. Les
        préfixes dynamiques reçoivent une IRI synthétique — une IRI en vaut
        une autre pour vérifier une syntaxe. rdflib absent : avertir et
        émettre sans valider."""
        try:
            from rdflib.plugins.sparql import prepareQuery, prepareUpdate
        except ImportError:
            self._warn("rdflib indisponible à la transpilation : "
                       "s{ } émis sans validation syntaxique")
            return
        init_ns = {}
        for pfx, val in self.prefixes.items():
            init_ns[pfx] = (val if isinstance(val, str)
                            else "urn:x-ldpy:dyn:%s/" % pfx)
        full = ("BASE <%s>\n" % self.base if self.base else "") + text
        try:
            (prepareUpdate if is_update else prepareQuery)(full,
                                                           initNs=init_ns)
        except Exception as e:
            msg = str(e).split("\n")[0][:200]
            self._error("requête SPARQL invalide : %s" % msg, line, col)

    # ------------------------------------------------------------------
    # nœuds expression SPARQL : e{ ... } et e<...> 
    # ------------------------------------------------------------------

    _E_BUILTINS = frozenset((
        "STR", "LANG", "DATATYPE", "IRI", "URI", "BNODE", "CONCAT", "UCASE",
        "LCASE", "STRLEN", "SUBSTR", "STRSTARTS", "STRENDS", "CONTAINS",
        "STRBEFORE", "STRAFTER", "REPLACE", "REGEX", "ABS", "ROUND", "CEIL",
        "FLOOR", "SAMETERM", "ISIRI", "ISURI", "ISBLANK", "ISLITERAL",
        "ISNUMERIC", "LANGMATCHES", "ENCODE_FOR_IRI",
    ))

    def _take_enode(self):
        """Sur 'e{'. Émet _ldpy_.sparql.expr(lambda __sm__: <corps>, src)."""
        start = self.i
        self._take(2)
        self._e_ws()
        body = self._e_expr()
        self._e_ws()
        if self._peek() != "}":
            self._error("'}' attendu pour fermer e{...}")
        self._take(1)
        src_text = self.text[start + 2:self.i - 1].strip()
        return "%s.sparql.expr(lambda __sm__: %s, src=%r)" % (
            RUNTIME_ALIAS, body, src_text)

    def _take_eiri(self):
        """Sur 'e<'. IRI différée : gabarit dont les trous sont des
        expressions SPARQL (STR + encodage IRI-safe à l'évaluation)."""
        start = self.i
        self._take(2)
        parts = []
        static = []
        while True:
            c = self._peek()
            if c == "":
                self._error("e-IRI non terminée")
            if c == ">":
                self._take(1)
                break
            if c == "{":
                self._take(1)
                if static:
                    parts.append(repr("".join(static)))
                    static = []
                self._e_ws()
                parts.append(self._e_expr())
                self._e_ws()
                if self._peek() != "}":
                    self._error("'}' attendu dans la e-IRI")
                self._take(1)
                continue
            if not _is_iri_char(c):
                self._error("caractère %r interdit dans une e-IRI" % c)
            static.append(self._take(1))
        if static:
            parts.append(repr("".join(static)))
        src_text = self.text[start:self.i]
        base = ", base=%r" % self.base if self.base else ""
        return ("%s.sparql.expr(lambda __sm__: %s.sparql.build_iri((%s,)%s), "
                "src=%r)" % (RUNTIME_ALIAS, RUNTIME_ALIAS,
                             ", ".join(parts), base, src_text))

    def _e_ws(self):
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

    def _e_kw(self, word):
        """Consomme le mot-clé s'il est là (frontière de mot), sinon False."""
        t = self.text
        if t.startswith(word, self.i) and not _name_char(
                self._peek(len(word))):
            self._take(len(word))
            self._e_ws()
            return True
        return False

    def _e_expr(self):
        """expression := or ('if' or 'else' expression)?  (style dev-sparql)."""
        val = self._e_or()
        self._e_ws()
        if self._e_kw("if"):
            cond = self._e_or()
            self._e_ws()
            if not self._e_kw("else"):
                self._error("'else' attendu dans l'expression conditionnelle")
            other = self._e_expr()
            return "%s.sparql.if_(%s, lambda: %s, lambda: %s)" % (
                RUNTIME_ALIAS, cond, val, other)
        return val

    def _e_or(self):
        val = self._e_and()
        while True:
            self._e_ws()
            if self.text.startswith("||", self.i):
                self._take(2)
                self._e_ws()
                val = "%s.sparql.or_(lambda: %s, lambda: %s)" % (
                    RUNTIME_ALIAS, val, self._e_and())
            else:
                return val

    def _e_and(self):
        val = self._e_rel()
        while True:
            self._e_ws()
            if self.text.startswith("&&", self.i):
                self._take(2)
                self._e_ws()
                val = "%s.sparql.and_(lambda: %s, lambda: %s)" % (
                    RUNTIME_ALIAS, val, self._e_rel())
            else:
                return val

    _E_RELOPS = (("!=", "ne"), ("<=", "le"), (">=", "ge"),
                 ("=", "eq"), ("<", "lt"), (">", "gt"))

    def _e_rel(self):
        val = self._e_add()
        self._e_ws()
        t = self.text
        if self._e_kw("NOT"):
            if not self._e_kw("IN"):
                self._error("'IN' attendu après 'NOT'")
            return "%s.sparql.not_in(%s, %s)" % (
                RUNTIME_ALIAS, val, self._e_list())
        if self._e_kw("IN"):
            return "%s.sparql.in_(%s, %s)" % (
                RUNTIME_ALIAS, val, self._e_list())
        for op, fn in self._E_RELOPS:
            if t.startswith(op, self.i):
                self._take(len(op))
                self._e_ws()
                return "%s.sparql.%s(%s, %s)" % (
                    RUNTIME_ALIAS, fn, val, self._e_add())
        return val

    def _e_list(self):
        if self._peek() != "(":
            self._error("'(' attendu après IN")
        self._take(1)
        items = []
        self._e_ws()
        while self._peek() != ")":
            items.append(self._e_expr())
            self._e_ws()
            if self._peek() == ",":
                self._take(1)
                self._e_ws()
        self._take(1)
        return "(%s,)" % ", ".join(items) if items else "()"

    def _e_add(self):
        val = self._e_mul()
        while True:
            self._e_ws()
            c = self._peek()
            if c == "+" :
                self._take(1)
                self._e_ws()
                val = "%s.sparql.add(%s, %s)" % (RUNTIME_ALIAS, val,
                                                 self._e_mul())
            elif c == "-":
                self._take(1)
                self._e_ws()
                val = "%s.sparql.sub(%s, %s)" % (RUNTIME_ALIAS, val,
                                                 self._e_mul())
            else:
                return val

    def _e_mul(self):
        val = self._e_unary()
        while True:
            self._e_ws()
            c = self._peek()
            if c == "*":
                self._take(1)
                self._e_ws()
                val = "%s.sparql.mul(%s, %s)" % (RUNTIME_ALIAS, val,
                                                 self._e_unary())
            elif c == "/":
                self._take(1)
                self._e_ws()
                val = "%s.sparql.div(%s, %s)" % (RUNTIME_ALIAS, val,
                                                 self._e_unary())
            else:
                return val

    def _e_unary(self):
        c = self._peek()
        if c == "!":
            self._take(1)
            self._e_ws()
            return "%s.sparql.not_(%s)" % (RUNTIME_ALIAS, self._e_unary())
        if c == "-":
            self._take(1)
            self._e_ws()
            return "%s.sparql.neg(%s)" % (RUNTIME_ALIAS, self._e_unary())
        if c == "+":
            self._take(1)
            self._e_ws()
        return self._e_primary()

    def _e_primary(self):
        t = self.text
        c = self._peek()
        if c == "(":
            self._take(1)
            self._e_ws()
            val = self._e_expr()
            self._e_ws()
            if self._peek() != ")":
                self._error("')' attendu")
            self._take(1)
            return val
        if c in "?$":
            self._take(1)
            m = _NAME_RE.match(t, self.i)
            if not m:
                self._error("nom de variable attendu")
            return "%s.sparql.var(__sm__, %r)" % (
                RUNTIME_ALIAS, self._take(len(m.group(0))))
        if c == "{":
            self._take(1)
            expr = self._scan_embedded_expr("}")
            if self._peek() != "}":
                self._error("'}' attendu")
            self._take(1)
            return "%s.sparql.py((%s))" % (RUNTIME_ALIAS, expr.strip())
        if c == "e" and self._peek(1) == "<":
            inner = self._take_eiri()
            return "(%s)(__sm__)" % inner       # e-IRI imbriquée : évaluée là
        if c == "<":
            iri = self._take_iriref()
            return "%s.URIRef(%r)" % (RUNTIME_ALIAS, self._resolve(iri))
        if c in "\"'":
            start = self.i
            end = self._string_end(self.i)
            text = t[start:end]
            self._take(end - self.i)
            if self._peek() == "@":
                m = _LANGTAG_RE.match(t, self.i)
                if m:
                    self._take(m.end() - self.i)
                    return "%s.Literal(%s, lang=%r)" % (
                        RUNTIME_ALIAS, text, m.group(1))
            if t.startswith("^^", self.i):
                self._take(2)
                dt = self._parse_term_after_hats()
                return "%s.Literal(%s, datatype=%s)" % (
                    RUNTIME_ALIAS, text, dt)
            return "%s.Literal(%s)" % (RUNTIME_ALIAS, text)
        if c.isdigit() or (c == "." and self._peek(1).isdigit()):
            j = self.i
            while j < self.n and (t[j].isdigit() or t[j] in ".eE" or
                                  (t[j] in "+-" and t[j-1] in "eE")):
                j += 1
            lex = self._take(j - self.i)
            return "%s.sparql.number(%r)" % (RUNTIME_ALIAS, lex)
        m = _NAME_RE.match(t, self.i)
        if m:
            word = m.group(0)
            after = t[m.end()] if m.end() < self.n else ""
            if word.upper() == "BOUND" and after == "(":
                self._take(len(word) + 1)
                self._e_ws()
                if self._peek() not in ("?", "$"):
                    self._error("BOUND attend une variable ?v")
                self._take(1)
                vm = _NAME_RE.match(t, self.i)
                name = self._take(len(vm.group(0)))
                self._e_ws()
                if self._peek() != ")":
                    self._error("')' attendu")
                self._take(1)
                return "%s.sparql.bound(__sm__, %r)" % (RUNTIME_ALIAS, name)
            if word.upper() in ("IF", "COALESCE") and after == "(":
                fn = word.upper()
                self._take(len(word) + 1)
                self._e_ws()
                args = []
                while self._peek() != ")":
                    args.append(self._e_expr())
                    self._e_ws()
                    if self._peek() == ",":
                        self._take(1)
                        self._e_ws()
                self._take(1)
                if fn == "IF":
                    if len(args) != 3:
                        self._error("IF attend 3 arguments")
                    return ("%s.sparql.if_(%s, lambda: %s, lambda: %s)"
                            % (RUNTIME_ALIAS, *args))
                return "%s.sparql.coalesce(%s)" % (
                    RUNTIME_ALIAS,
                    ", ".join("lambda: %s" % a for a in args))
            if word.upper() in self._E_BUILTINS and after == "(":
                fn = "ISIRI" if word.upper() == "ISURI" else word.upper()
                if fn == "URI":
                    fn = "IRI"
                self._take(len(word) + 1)
                self._e_ws()
                args = []
                while self._peek() != ")":
                    args.append(self._e_expr())
                    self._e_ws()
                    if self._peek() == ",":
                        self._take(1)
                        self._e_ws()
                self._take(1)
                if fn == "IRI" and self.base:
                    args.append("base=%r" % self.base)
                return "%s.sparql.%s(%s)" % (RUNTIME_ALIAS, fn,
                                             ", ".join(args))
            if after == ":":
                return self._take_pname(in_island=True)
            if word in ("true", "false"):
                self._take(len(word))
                return "%s.Literal(%s)" % (RUNTIME_ALIAS,
                                           word == "true")
        self._error("expression SPARQL attendue")

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
    if expr.startswith(RUNTIME_ALIAS + ".firi(") \
            or expr.startswith(RUNTIME_ALIAS + ".pname("):
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
    produirait deux sujets differents. Voir docs/explanation/emission-and-semantics.md."""
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
