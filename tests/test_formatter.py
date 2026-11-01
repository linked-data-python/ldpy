"""Formateur .ldpy (ldpy/formatter.py, fiche ldpy/024).

Trois propriétés tiennent lieu de spécification, et sont vérifiées sur tout
ce que le dépôt contient d'ldpy (exemples + blocs de la documentation) :

1. **transparence de l'hôte** — sans îlot, le formateur EST black ;
2. **idempotence** — formater deux fois donne le même texte ;
3. **le sens ne bouge pas** — l'AST du Python transpilé est inchangé, le
   texte d'une requête `s{ }` comparé jeton par jeton (son blanc et la casse
   de ses mots-clés n'ont, par définition de SPARQL, aucun sens).
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
    DEFAULT_LINE_LENGTH, _canonical, format_source, format_file, main)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def transpiled_ast(source, filename="<t>", exact=False):
    """Le programme transpilé. Une seule chose du code émis porte la mise en
    page : le TEXTE d'une requête `s{ }`, embarqué tel quel ; il est comparé
    jeton par jeton (`_canonical`, la garde du formateur lui-même), et rien
    d'autre n'est relâché."""
    code = transpile(source, filename).code
    return ast.dump(ast.parse(code)) if exact else _canonical(code)


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

def test_un_ilot_qui_tient_sur_une_ligne_y_est_mis():
    """Règle de black : sur une ligne tant que la ligne tient."""
    source = ("@prefix ex: <http://e/> .\n"
              "if True:\n"
              "        gr = g{ ex:s ex:p 1 ;\n"
              "                ex:q 2 }\n")
    assert format_source(source) == (
        "@prefix ex: <http://e/> .\n"
        "if True:\n"
        "    gr = g{ ex:s ex:p 1 ; ex:q 2 }\n")


def test_fmt_skip_garde_lalignement_de_lauteur():
    """`# fmt: skip` : le corps est recopié, et se décale AVEC son
    instruction en gardant l'alignement voulu."""
    source = ("@prefix ex: <http://e/> .\n"
              "if True:\n"
              "        gr = g{ ex:s ex:p 1 ;\n"
              "                ex:q 2 }  # fmt: skip\n")
    assert format_source(source) == (
        "@prefix ex: <http://e/> .\n"
        "if True:\n"
        "    gr = g{ ex:s ex:p 1 ;\n"
        "            ex:q 2 }  # fmt: skip\n")


def test_fmt_off_garde_le_corps():
    source = ("@prefix ex: <http://e/> .\n"
              "# fmt: off\n"
              "a = g{ ex:s   ex:p    1 }\n"
              "# fmt: on\n")
    assert "ex:s   ex:p    1" in format_source(source)


def test_un_ilot_trop_long_seclate_en_retrait_suspendu():
    source = ("@prefix ex: <http://e/> .\n"
              "@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n"
              "@graph as g\n"
              "def f(person):\n"
              "    +{ {person} a foaf:Person ; foaf:name \"Alice Liddell\" ; "
              "foaf:knows [ a foaf:Person ; foaf:name \"The White Rabbit\" ] }\n")
    assert format_source(source).split("\n")[6:-1] == [
        "    +{",
        "        {person} a foaf:Person ;",
        "            foaf:name \"Alice Liddell\" ;",
        "            foaf:knows [ a foaf:Person ; foaf:name \"The White Rabbit\" ]",
        "    }"]


def test_un_noeud_anonyme_trop_long_souvre_en_fin_de_ligne():
    knows = " ; ".join('ex:p%d "%s"' % (i, "v" * 20) for i in range(4))
    source = ("@prefix ex: <http://e/> .\n@graph as g\n"
              "+{ ex:s ex:knows [ %s ] }\n" % knows)
    lines = format_source(source).split("\n")[2:-1]
    assert lines[0] == "+{"
    assert lines[1] == "    ex:s ex:knows ["
    assert lines[2] == '            ex:p0 "%s" ;' % ("v" * 20)
    assert lines[-2] == "        ]"
    assert lines[-1] == "}"
    # des paliers de quatre : rien que l'extension indent-rainbow signale
    for line in lines:
        assert (len(line) - len(line.lstrip(" "))) % 4 == 0, line


def test_une_requete_sparql_prend_sa_mise_en_page_canonique():
    source = ("@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n"
              "min_age = 30\n"
              "rows = s{ select ?name where { ?p foaf:name ?name ; foaf:age ?age .\n"
              "           FILTER(?age >= {min_age}) } ORDER BY ?name }\n")
    assert format_source(source).split("\n")[2:-1] == [
        "rows = s{",
        "    SELECT ?name",
        "    WHERE {",
        "        ?p foaf:name ?name ;",
        "            foaf:age ?age .",
        "        FILTER (?age >= {min_age})",
        "    }",
        "    ORDER BY ?name",
        "}"]


def test_sparql_une_accolade_reste_groupe_ou_interpolation():
    """La décision groupe / interpolation est celle du transpileur."""
    source = ("@prefix ex: <http://e/> .\n"
              "x = 1\n"
              "r = s{ SELECT ?s WHERE { GRAPH ?g { ?s ex:p {x} } } }\n")
    out = format_source(source)
    assert "            ?s ex:p {x}\n" in out
    assert "        GRAPH ?g {\n" in out
    assert transpiled_ast(out) == transpiled_ast(source)


def test_les_bordures_dun_ilot_sont_normalisees():
    source = "@prefix ex: <http://e/> .\na = g{ex:s ex:p 1}\nb = g{}\n"
    assert format_source(source) == (
        "@prefix ex: <http://e/> .\n"
        "a = g{ ex:s ex:p 1 }\n"
        "b = g{ }\n")


def test_le_corps_dun_ilot_est_reecrit():
    """Fiche 024 : le formateur a une mise en page RDF, l'espacement de
    l'auteur ne compte pas."""
    source = "@prefix ex: <http://e/> .\na = g{ ex:s   ex:p    1 }\n"
    assert "a = g{ ex:s ex:p 1 }" in format_source(source)


def test_un_commentaire_dans_un_ilot_garde_le_corps():
    source = ("@prefix ex: <http://e/> .\n"
              "a = g{ ex:s   ex:p 1 ;  # le premier\n"
              "       ex:q 2 }\n")
    assert "ex:s   ex:p 1 ;  # le premier" in format_source(source)


def test_si_le_sens_bougeait_le_corps_est_recopie(monkeypatch):
    """La garde : une mise en page qui changerait le programme est refusée,
    le fichier repart corps recopiés."""
    from ldpy import formatter_islands
    real = formatter_islands.graph_layout

    def wrong(opener, body):
        layout = real(opener, body)
        layout.flat = layout.flat.replace("1", "2")
        return layout
    monkeypatch.setattr(formatter_islands, "graph_layout", wrong)
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
