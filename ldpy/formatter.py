"""Formateur (pretty printer) des fichiers .ldpy — fiche ldpy/024.

Le principe est celui du surligneur (fiche 023) : **le formateur est le
transpileur**. On transpile pour obtenir la language map, qui dit exactement
où sont les îlots dans le SOURCE ; on remplace chacun par un substitut valide
en Python à sa place ; on donne le résultat à `black`, qui est le formateur de
Python ; on réinjecte les îlots là où les substituts ont atterri.

Deux conséquences tiennent lieu de contrat, et sont testées :

- **transparence de l'hôte** — un fichier sans îlot est formaté *exactement*
  comme `black` le formaterait. Le formateur n'a pas d'avis sur Python ;
- **le sens ne bouge pas** — l'AST du Python transpilé est identique avant et
  après formatage. Un formateur qui change ce que fait le programme n'est pas
  un formateur.

Ce que le formateur fait AUX ÎLOTS est délibérément modeste (le corps est
recopié tel quel, seules les bordures sont normalisées) : voir la fiche 024,
section « ce que le formateur ne fait pas ».

`black` est une dépendance OPTIONNELLE (extra `[format]`) : rien dans ldpy ne
l'importe hors de ce module, et son absence donne un message actionnable.
"""

import argparse
import os
import re
import sys

from ldpy.transpiler import transpile

DEFAULT_LINE_LENGTH = 88


class FormatterUnavailable(RuntimeError):
    """`black` n'est pas installé dans cet interpréteur."""


def _black():
    """Le moteur Python, chargé à la demande.

    Le seul point de couplage : en changer (ruff format, par exemple) ne
    touche que cette fonction et `_format_python`."""
    try:
        import black
    except ImportError as e:                                # pragma: no cover
        raise FormatterUnavailable(
            "le formateur ldpy délègue le Python à black, qui n'est pas "
            "installé — `pip install linked-data-python[format]`") from e
    return black


def _format_python(text, line_length):
    black = _black()
    return black.format_str(text, mode=black.Mode(line_length=line_length))


# ---------------------------------------------------------------------------
# Décalages : la map parle en (ligne, colonne), le texte en offsets
# ---------------------------------------------------------------------------

def _line_starts(text):
    starts = [0]
    for i, c in enumerate(text):
        if c == "\n":
            starts.append(i + 1)
    return starts


def _offset(starts, line, col):
    return starts[line] + col


# ---------------------------------------------------------------------------
# Masquage : un substitut valide en Python à la place de chaque îlot
# ---------------------------------------------------------------------------

#: Les îlots occupent une position d'expression ou d'instruction, sauf deux
#: cas où le substitut doit porter la forme syntaxique de l'original pour que
#: `black` le traite pareil (un import a droit à sa ligne vide, pas un nom nu).
def _substitute(kind, name):
    if kind == "for-bindings":
        # `for @bindings [as b] in` -> l'en-tête de boucle correspondante
        return "for %s in" % name
    if kind == "import":
        # `from m import a, ex:, unit: as u:` -> une VRAIE instruction
        # d'import, pour que black gère les lignes vides du bloc d'imports
        return "import %s" % name
    return name


def _padded(name, text, line_length):
    """Rallonge `name` pour que le substitut PÈSE ce que pèse l'îlot.

    C'est la doctrine du masquage de la fiche 023 : un substitut de même
    longueur laisse le moteur délégué décider comme il aurait décidé sur le
    vrai texte. Ici l'enjeu est la coupure de ligne — un substitut court
    ferait croire à black que tout tient sur une ligne, et l'îlot réinjecté
    déborderait.

    Un îlot MULTILIGNE ne peut par construction pas tenir sur une ligne : on
    lui donne un poids qui dépasse la limite, ce qui garde la coupure que
    l'auteur a écrite."""
    width = max(len(l) for l in text.split("\n"))
    if "\n" in text:
        width = max(width, line_length + 1)
    return name + "_" * max(0, width - len(name))


#: Îlot dont le texte est déjà du Python valide et n'a rien à masquer : le
#: « : » qui ferme un `for @bindings in ... :`.
_TRANSPARENT = ("for-bindings-close",)


class _Island:
    __slots__ = ("kind", "text", "column", "name", "substitute")

    def __init__(self, kind, text, column, name, line_length):
        self.kind = kind
        self.text = text
        self.column = column          # colonne de départ dans le SOURCE
        self.name = name
        self.substitute = _substitute(kind, _padded(name, text, line_length))


def _fresh_names(source, count):
    """`count` identifiants uniques absents du source.

    On préfixe par `_L` et on rallonge tant qu'un nom apparaît dans le texte :
    le masquage doit être réversible, donc les substituts ne doivent jamais
    entrer en collision avec un nom de l'utilisateur."""
    prefix = "_L"
    while any(("%s%d" % (prefix, i)) in source for i in range(count)):
        prefix += "_"
    return ["%s%d" % (prefix, i) for i in range(count)]


def _mask(source, lmap, line_length=DEFAULT_LINE_LENGTH):
    """Rend (texte masqué, liste d'îlots) — le texte masqué est du Python."""
    starts = _line_starts(source)
    segments = [s for s in lmap.segments
                if s.kind.startswith("island:") and s.src is not None
                and s.kind[len("island:"):] not in _TRANSPARENT]
    names = _fresh_names(source, len(segments))
    out = []
    islands = []
    cursor = 0
    for seg, name in zip(segments, names):
        kind = seg.kind[len("island:"):]
        a = _offset(starts, seg.src[0], seg.src[1])
        b = _offset(starts, seg.src[2], seg.src[3])
        if a < cursor:                       # îlot imbriqué : déjà couvert
            continue
        island = _Island(kind, source[a:b], seg.src[1], name, line_length)
        out.append(source[cursor:a])
        out.append(island.substitute)
        islands.append(island)
        cursor = b
    out.append(source[cursor:])
    return "".join(out), islands


# ---------------------------------------------------------------------------
# Normalisation des îlots : les BORDURES seulement (fiche 024)
# ---------------------------------------------------------------------------

_OPENER = re.compile(r"^[a-zA-Z+\-]?\{")
#: `@prefix ex: <...> .` / `@base <...> .` — grammaire close, sans espace
#: possible dans les termes, donc normalisable sans risque.
_DECL = re.compile(r"^@(prefix|base)\s+((?:\S+:)\s+)?(<[^>\s]*>)\s*\.$")


def _normalize_island(text):
    """Normalise les bordures d'un îlot, sans toucher à son corps.

    Ce qui est repris : les espaces de fin de ligne, le rembourrage juste
    après `{` et juste avant `}`, et les déclarations dont la grammaire est
    close (`@prefix`, `@base`, `@graph`, `@bindings`, import de préfixes).
    Le corps d'un graphe ou d'une requête est recopié CARACTÈRE POUR
    CARACTÈRE : voir la fiche 024."""
    text = "\n".join(l.rstrip() for l in text.split("\n"))

    m = _DECL.match(text)
    if m:
        pieces = ["@" + m.group(1)]
        if m.group(2):
            pieces.append(m.group(2).strip())
        pieces += [m.group(3), "."]
        return " ".join(pieces)

    if text.startswith(("@graph", "@bindings", "from ")) \
            and not re.search(r"[{}'\"]", text):
        # pas d'interpolation ni de littéral : les blancs n'y sont que du
        # rembourrage, et la virgule d'une liste d'imports se normalise
        text = re.sub(r"\s+", " ", text).strip()
        return re.sub(r"\s*,\s*", ", ", text)

    m = _OPENER.match(text)
    if m and text.endswith("}") and len(text) > len(m.group(0)):
        open_, body = m.group(0), text[len(m.group(0)):-1]
        if not body.strip():
            return open_ + " }"
        first, *rest = body.split("\n")
        if rest:
            rest[-1] = rest[-1].rstrip()
            body = "\n".join([" " + first.strip() if first.strip() else first]
                             + rest)
            return open_ + body + (" }" if rest[-1] else "}")
        return open_ + " " + body.strip() + " }"
    return text


def _reindent(text, from_column, to_column):
    """Décale les lignes de continuation d'un îlot multiligne.

    Le décalage préserve l'alignement voulu par l'auteur ; on ne le laisse
    jamais passer sous la colonne 0."""
    if "\n" not in text or from_column == to_column:
        return text
    delta = to_column - from_column
    first, *rest = text.split("\n")
    if delta > 0:
        rest = [(" " * delta + l) if l.strip() else l for l in rest]
    else:
        keep = min([len(l) - len(l.lstrip()) for l in rest if l.strip()],
                   default=0)
        cut = min(-delta, keep)
        rest = [l[cut:] if l.strip() else l for l in rest]
    return "\n".join([first] + rest)


def _unmask(formatted, islands):
    """Réinjecte chaque îlot à la place de son substitut."""
    for island in islands:
        idx = formatted.find(island.substitute)
        if idx < 0:                                        # pragma: no cover
            raise RuntimeError(
                "substitut %r introuvable après formatage — signaler ce "
                "fichier comme un défaut du formateur" % island.substitute)
        column = idx - formatted.rfind("\n", 0, idx) - 1
        text = _reindent(_normalize_island(island.text),
                         island.column, column)
        formatted = (formatted[:idx] + text
                     + formatted[idx + len(island.substitute):])
    return formatted


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def format_source(source, filename="<ldpy>",
                  line_length=DEFAULT_LINE_LENGTH):
    """Formate un source .ldpy et rend le texte formaté.

    Lève `LdpySyntaxError` si le source ne transpile pas (on ne formate pas
    ce qu'on ne comprend pas) et `FormatterUnavailable` si black manque."""
    result = transpile(source, filename)
    masked, islands = _mask(source, result.map, line_length)
    return _unmask(_format_python(masked, line_length), islands)


def format_file(path, line_length=DEFAULT_LINE_LENGTH, write=False):
    """Formate un fichier ; rend (texte formaté, a_changé)."""
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    formatted = format_source(source, path, line_length)
    changed = formatted != source
    if write and changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(formatted)
    return formatted, changed


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ldpy-format",
        description="Formate des fichiers .ldpy : black pour le Python, "
                    "bordures normalisées pour les îlots (fiche ldpy/024).")
    parser.add_argument("paths", nargs="+",
                        help="fichiers .ldpy ou répertoires à parcourir")
    parser.add_argument("-l", "--line-length", type=int,
                        default=DEFAULT_LINE_LENGTH,
                        help="longueur de ligne (défaut : %(default)s)")
    parser.add_argument("--check", action="store_true",
                        help="n'écrit rien ; sort en 1 si un fichier "
                             "n'est pas formaté")
    parser.add_argument("--diff", action="store_true",
                        help="affiche le diff au lieu d'écrire")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    files = []
    for p in args.paths:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                files += [os.path.join(root, n) for n in sorted(names)
                          if n.endswith(".ldpy")]
        else:
            files.append(p)

    from ldpy.transpiler import LdpySyntaxError
    changed_any = False
    status = 0
    for path in files:
        try:
            formatted, changed = format_file(
                path, args.line_length,
                write=not (args.check or args.diff))
        except (LdpySyntaxError, FormatterUnavailable) as e:
            print("%s : %s" % (path, e), file=sys.stderr)
            status = 2
            continue
        changed_any = changed_any or changed
        if args.diff and changed:
            import difflib
            with open(path, encoding="utf-8") as f:
                before = f.read()
            sys.stdout.writelines(difflib.unified_diff(
                before.splitlines(True), formatted.splitlines(True),
                path, path + " (formaté)"))
        elif changed:
            print("reformaté %s" % path)
    if args.check and changed_any:
        return 1
    return status


if __name__ == "__main__":                                 # pragma: no cover
    sys.exit(main())
