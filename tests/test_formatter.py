"""Formateur .ldpy (ldpy/formatter.py, fiche DESIGN_CHOICES/ldpy/024).

Trois propriétés tiennent lieu de spécification, et sont vérifiées sur tout
ce que le dépôt contient d'ldpy (exemples + blocs de la documentation) :

1. **transparence de l'hôte** — sans îlot, le formateur EST black ;
2. **idempotence** — formater deux fois donne le même texte ;
3. **le sens ne bouge pas** — l'AST du Python transpilé est inchangé, au
   blanc près à l'intérieur du texte d'une requête `s{ }` (où il n'a, par
   définition de SPARQL, aucun sens).
"""

import ast
import glob
import os
import re
import subprocess
import sys

import pytest

from ldpy.transpiler import transpile, LdpySyntaxError

black = pytest.importorskip("black", reason="extra [format] non installé")

from ldpy.formatter import (                                       # noqa: E402
    DEFAULT_LINE_LENGTH, format_source, format_file, main)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _NormalizeStrings(ast.NodeTransformer):
    """Réduit le blanc dans les constantes chaîne.

    Une seule chose du code émis porte du blanc venu de la mise en page : le
    TEXTE d'une requête `s{ }`, embarqué tel quel. SPARQL ignore ce blanc ;
    l'invariant le fait donc aussi, et rien d'autre n'est relâché."""

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            node.value = " ".join(node.value.split())
        return node


def transpiled_ast(source, filename="<t>", exact=False):
    tree = ast.parse(transpile(source, filename).code)
    return ast.dump(tree if exact else _NormalizeStrings().visit(tree))


def corpus():
    """Tout le ldpy du dépôt : les exemples, et les blocs de la doc."""
    items = []
    for p in sorted(glob.glob(os.path.join(REPO, "examples", "**", "*.ldpy"),
                              recursive=True)):
        with open(p, encoding="utf-8") as f:
            items.append((os.path.relpath(p, REPO), f.read()))
    for md in sorted(glob.glob(os.path.join(REPO, "docs", "**", "*.md"),
                               recursive=True)):
        with open(md, encoding="utf-8") as f:
            text = f.read()
        for i, m in enumerate(re.finditer(r"```ldpy\n(.*?)```", text, re.S)):
            items.append(("%s#%d" % (os.path.relpath(md, REPO), i),
                          m.group(1)))
    return items


CORPUS = corpus()
CORPUS_IDS = [name for name, _ in CORPUS]


def formattable(source, name):
    """Le corpus contient des extraits volontairement fautifs (pages
    d'erreurs) : ils ne se formatent pas, et c'est le comportement voulu."""
    try:
        return format_source(source, name)
    except LdpySyntaxError:
        pytest.skip("extrait non transpilable (attendu pour les pages "
                    "d'erreurs)")


# ------------------------------------------------ 1. transparence de l'hôte

PUR_PYTHON = [
    "x=1\ndef f( a,b ):\n    return  a+b\n",
    "import os,sys\nd={ 'a':1,'b':2 }\nl=[i for i in range(10) if i%2==0]\n",
    "class A :\n  def m( self )  ->  int :\n        return 1\n",
    "async def g():\n    async with open('x') as f: pass\n",
    "match x:\n    case 1 : pass\n    case _ : pass\n",
]


@pytest.mark.parametrize("source", PUR_PYTHON)
def test_sans_ilot_le_formateur_est_black(source):
    assert format_source(source) == black.format_str(source,
                                                     mode=black.Mode())


def test_transparence_sur_les_sources_du_paquet():
    """Le vrai banc d'essai : les modules de ldpy lui-même, qui sont du
    Python pur et que le transpileur laisse passer à l'identique."""
    files = sorted(glob.glob(os.path.join(REPO, "ldpy", "**", "*.py"),
                             recursive=True))
    assert len(files) > 5
    for p in files:
        with open(p, encoding="utf-8") as f:
            source = f.read()
        assert format_source(source, p) == \
            black.format_str(source, mode=black.Mode()), p


def test_la_longueur_de_ligne_est_celle_quon_demande():
    source = "x = [111111111, 222222222, 333333333, 444444444, 555555555]\n"
    assert format_source(source, line_length=40) == \
        black.format_str(source, mode=black.Mode(line_length=40))


# ------------------------------------------------------- 2 et 3. le corpus

@pytest.mark.parametrize("name,source", CORPUS, ids=CORPUS_IDS)
def test_corpus_idempotent(name, source):
    once = formattable(source, name)
    assert format_source(once, name) == once


@pytest.mark.parametrize("name,source", CORPUS, ids=CORPUS_IDS)
def test_corpus_conserve_le_sens(name, source):
    once = formattable(source, name)
    assert transpiled_ast(once, name) == transpiled_ast(source, name)


@pytest.mark.parametrize("name,source", CORPUS, ids=CORPUS_IDS)
def test_corpus_tient_dans_la_marge(name, source):
    """Une ligne trop longue signalerait un substitut mal pesé (le piège :
    black décide sur le substitut, pas sur l'îlot)."""
    once = formattable(source, name)
    trop = [l for l in once.split("\n") if len(l) > DEFAULT_LINE_LENGTH]
    # une ligne d'îlot peut légitimement dépasser : l'auteur l'a écrite ainsi
    trop = [l for l in trop if not re.search(r"[a-z+\-]\{|\}", l)]
    assert not trop, trop


def test_corpus_sans_sparql_conserve_lAST_exactement():
    """Hors `s{ }`, l'invariant est SANS relâchement : aucun octet du code
    émis ne dépend de la mise en page."""
    vus = 0
    for name, source in CORPUS:
        if "s{" in source:
            continue
        try:
            once = format_source(source, name)
        except LdpySyntaxError:
            continue
        assert transpiled_ast(once, name, exact=True) == \
            transpiled_ast(source, name, exact=True), name
        vus += 1
    assert vus > 50


# --------------------------------------------------- ce qu'il fait vraiment

def test_indentation_python_et_alignement_dilot_suivent():
    """Le corps d'un îlot multiligne se décale AVEC son instruction, en
    gardant l'alignement voulu par l'auteur."""
    source = ("@prefix ex: <http://e/> .\n"
              "if True:\n"
              "        gr = g{ ex:s ex:p 1 ;\n"
              "                ex:q 2 }\n")
    assert format_source(source) == (
        "@prefix ex: <http://e/> .\n"
        "if True:\n"
        "    gr = g{ ex:s ex:p 1 ;\n"
        "            ex:q 2 }\n")


def test_les_bordures_dun_ilot_sont_normalisees():
    source = "@prefix ex: <http://e/> .\na = g{ex:s ex:p 1}\nb = g{}\n"
    assert format_source(source) == (
        "@prefix ex: <http://e/> .\n"
        "a = g{ ex:s ex:p 1 }\n"
        "b = g{ }\n")


def test_le_corps_dun_ilot_nest_pas_reecrit():
    """Décision de la fiche 024 : la mise en page RDF appartient à l'auteur.
    Les espaces internes, eux, sont laissés tels quels."""
    source = "@prefix ex: <http://e/> .\na = g{ ex:s   ex:p    1 }\n"
    assert "ex:s   ex:p    1" in format_source(source)


def test_les_declarations_sont_normalisees():
    source = ("@prefix   ex:    <http://e/>   .\n"
              "@base   <http://e/d/>  .\n"
              "@graph    as    out\n")
    assert format_source(source) == (
        "@prefix ex: <http://e/> .\n"
        "@base <http://e/d/> .\n"
        "@graph as out\n")


def test_limport_de_prefixes_reste_un_import_pour_black():
    """Le substitut d'un import EST un import : black lui donne les lignes
    vides du bloc d'imports, pas celles d'une expression."""
    source = ("import os\n"
              "from vocab import  CONST ,  ex: ,  unit: as u:\n"
              "x = 1\n")
    assert format_source(source) == (
        "import os\n"
        "from vocab import CONST, ex:, unit: as u:\n"
        "\n"
        "x = 1\n")


def test_le_for_bindings_reste_une_boucle():
    source = "@prefix ex: <http://e/> .\n@graph as o\nfor @bindings in []:\n        +{ ex:s ex:p ?v }\n"
    assert format_source(source) == (
        "@prefix ex: <http://e/> .\n"
        "@graph as o\n"
        "for @bindings in []:\n"
        "    +{ ex:s ex:p ?v }\n")


def test_les_substituts_ne_collisionnent_pas_avec_le_code():
    """Un fichier qui contient déjà `_L0` ne doit pas être corrompu."""
    source = "@prefix ex: <http://e/> .\n_L0 = 1\n_L1 = g{ ex:s ex:p 1 }\n"
    out = format_source(source)
    assert "_L0 = 1" in out and "_L1 = g{ ex:s ex:p 1 }" in out


def test_un_source_fautif_est_refuse():
    with pytest.raises(LdpySyntaxError):
        format_source("a = g{ foo:b a foo:C }\n")


# ------------------------------------------------------------ fichiers, CLI

def test_format_file_ecrit_et_signale(tmp_path):
    p = tmp_path / "a.ldpy"
    p.write_text("@prefix ex: <http://e/> .\nx=1\n", encoding="utf-8")
    out, changed = format_file(str(p), write=True)
    assert changed and p.read_text(encoding="utf-8") == out
    assert format_file(str(p), write=True)[1] is False


def test_cli_check_sort_en_erreur_si_non_formate(tmp_path):
    p = tmp_path / "a.ldpy"
    p.write_text("x=1\n", encoding="utf-8")
    assert main([str(p), "--check"]) == 1
    assert p.read_text(encoding="utf-8") == "x=1\n"      # rien écrit
    assert main([str(p)]) == 0
    assert p.read_text(encoding="utf-8") == "x = 1\n"
    assert main([str(p), "--check"]) == 0


def test_cli_parcourt_un_repertoire(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.ldpy").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("y=1\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 0
    assert (tmp_path / "sub" / "a.ldpy").read_text(encoding="utf-8") == "x = 1\n"
    assert (tmp_path / "b.py").read_text(encoding="utf-8") == "y=1\n"


def test_cli_signale_un_fichier_fautif(tmp_path, capsys):
    p = tmp_path / "a.ldpy"
    p.write_text("a = g{ foo:b a foo:C }\n", encoding="utf-8")
    assert main([str(p)]) == 2
    assert "foo" in capsys.readouterr().err


def test_point_dentree_installe():
    r = subprocess.run([sys.executable, "-m", "ldpy.formatter", "--help"],
                       capture_output=True, text=True, cwd=REPO, timeout=60,
                       env=dict(os.environ, PYTHONPATH=REPO))
    assert r.returncode == 0 and "ldpy-format" in r.stdout
