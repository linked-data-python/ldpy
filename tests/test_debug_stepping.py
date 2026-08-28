"""L'invariant de pas à pas de la fiche DESIGN_CHOICES/vscode/103.

> Chaque événement `stopped` du débogueur sélectionne une région du fichier
> `.ldpy`, et cette région change à chaque geste — jamais d'arrêt invisible
> sur du code généré sans antécédent source, jamais de sélection qui reste en
> place alors qu'un pas a eu lieu.

Ces tests le mesurent pour de vrai : ils lancent `-m ldpy.debug --run` sous
debugpy, exactement comme l'extension VS Code, pilotent le débogueur par le
Debug Adapter Protocol (`tests/dapclient.py`) et regardent où il s'arrête.

Le prix est celui d'un vrai processus par programme de référence : les traces
sont donc calculées UNE fois pour la session (fixture `traces`) et les tests
raisonnent dessus.
"""

import os
import subprocess
import sys

import pytest

from ldpy.debug import stepping_rules, probe, package_dir

from dapclient import DapSession, DapError

HAS_DEBUGPY = subprocess.run(
    [sys.executable, "-c", "import debugpy"],
    capture_output=True).returncode == 0

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not HAS_DEBUGPY, reason="debugpy non installé"),
]

VOCAB = """\
@prefix ex: <http://example.org/> .
@prefix unit: <http://qudt.org/vocab/unit/> .
CONST = 1
"""

#: nom -> (source, ligne de point d'arrêt, gestes). Un cas par construction
#: que la fiche 103 désigne comme à risque.
PROGRAMS = {
    "boucle_plus": ("""\
@prefix ex: <http://example.org/> .
@graph as out
for i in range(3):
    +{ ex:s ex:v {i} }
print(len(out))
""", 3, ["over"] * 8),

    "ilot_multiligne": ("""\
@prefix ex: <http://example.org/> .
valeur = 21.5
gr = g{ ex:s a ex:Obs ;
        ex:v {valeur} }
print(len(gr))
""", 2, ["over", "over", "over"]),

    "for_bindings": ("""\
@prefix ex: <http://example.org/> .
@graph as out
rows = [{"id": "a", "v": 1}, {"id": "b", "v": 2}]
for @bindings in rows:
    +{ ex:s ex:value ?v }
print(len(out))
""", 3, ["over"] * 7),

    "import_prefixes": ("""\
from vocab import CONST, ex:, unit: as u:
x = ex:Thing
y = u:DEG_C
print(x, y)
""", 1, ["over"] * 4),

    "global_graph": ("""\
@prefix ex: <http://example.org/> .
for cand in range(3):
    if cand == 1:
        global @graph as chosen
        break
+{ ex:s ex:p {cand} }
print(len(chosen))
""", 2, ["over"] * 8),

    "match_et_expression": ("""\
@prefix ex: <http://example.org/> .
@graph as src
+{ ex:c1 ex:reading 10 . ex:c2 ex:reading 25 }
@graph as out
for @bindings in m{ ?s ex:reading ?v }(src):
    +{ ?s ex:hasValue e{ ?v * 2 } }
print(len(out))
""", 2, ["over"] * 9),

    "requete_sparql": ("""\
@prefix ex: <http://example.org/> .
@graph as g
+{ ex:a ex:p 1 . ex:b ex:p 2 }
q = s{ SELECT ?s WHERE { ?s ex:p ?v } }
n = len(list(q(g)))
print(n)
""", 2, ["over"] * 5),

    "fonction": ("""\
@prefix ex: <http://example.org/> .
def build(v):
    return g{ ex:s ex:v {v} }
gr = build(3)
print(len(gr))
""", 4, ["in", "over", "out", "over"]),
}


def write_program(tmpdir, source):
    """Écrit le programme (et le vocabulaire qu'un cas importe) et rend son
    chemin."""
    path = os.path.join(tmpdir, "prog.ldpy")
    with open(path, "w", encoding="utf-8") as f:
        f.write(source)
    with open(os.path.join(tmpdir, "vocab.ldpy"), "w", encoding="utf-8") as f:
        f.write(VOCAB)
    return path


def trace(tmpdir, source, breakpoint_line, gestures, just_my_code=True,
          rules=None):
    """Déroule les gestes et rend la liste des arrêts observés."""
    path = write_program(tmpdir, source)
    if rules is None:
        rules = stepping_rules(just_my_code)
    with DapSession(path, breakpoints=[breakpoint_line], rules=rules,
                    just_my_code=just_my_code, timeout=30) as s:
        return s.walk(gestures)


@pytest.fixture(scope="session")
def traces(tmp_path_factory):
    """Une trace par programme de référence, calculée une seule fois."""
    out = {}
    for name, (source, bp, gestures) in PROGRAMS.items():
        d = str(tmp_path_factory.mktemp(name))
        out[name] = trace(d, source, bp, gestures)
    return out


# --------------------------------------------------------------- l'invariant

@pytest.mark.parametrize("name", list(PROGRAMS))
def test_chaque_arret_est_dans_le_ldpy(traces, name):
    """Aucun arrêt sur du code généré, du lanceur ou du runtime."""
    stops = traces[name]
    assert stops, "aucun arrêt observé"
    faux = [st for st in stops if st.file != "prog.ldpy"]
    assert not faux, "arrêts hors du .ldpy : %r" % (faux,)


@pytest.mark.parametrize("name", list(PROGRAMS))
def test_chaque_geste_deplace_la_region(traces, name):
    """Deux arrêts consécutifs ne sont jamais à la même place.

    C'est la consigne littérale : « jamais un clic sur un bouton ne fait que
    la région sélectionnée dans le ldpy ne change pas »."""
    stops = traces[name]
    immobiles = [(a, b) for a, b in zip(stops, stops[1:])
                 if a.where == b.where]
    assert not immobiles, "geste sans effet visible : %r" % (immobiles,)


@pytest.mark.parametrize("name", list(PROGRAMS))
def test_la_pile_ne_montre_pas_le_lanceur(traces, name):
    """Le panneau « pile d'appels » ne contient que des trames de
    l'utilisateur : `-m ldpy.debug` est de la plomberie."""
    for st in traces[name]:
        assert set(st.files) == {"prog.ldpy"}, \
            "trames étrangères dans la pile : %r" % (st.files,)


@pytest.mark.parametrize("name", list(PROGRAMS))
def test_chaque_arret_designe_une_ligne_du_fichier(traces, name):
    """La ligne rapportée existe, et n'est pas vide."""
    source = PROGRAMS[name][0].split("\n")
    for st in traces[name]:
        assert 1 <= st.line <= len(source)
        assert source[st.line - 1].strip(), \
            "arrêt sur une ligne vide (%d)" % st.line


# ------------------------------------------------- ce que chaque cas montre

def test_ilot_multiligne_ne_sarrete_quau_debut(traces):
    """Un `g{ }` sur deux lignes est UNE instruction : le pas passe de sa
    première ligne à la suivante du programme, sans arrêt intermédiaire."""
    lignes = [st.line for st in traces["ilot_multiligne"]]
    assert lignes[:3] == [2, 3, 5]           # 4 = l'intérieur de l'îlot


def test_import_de_prefixes_est_un_seul_pas(traces):
    """L'import de préfixes émet plusieurs instructions sur une ligne ; le
    remappage les ramène toutes à la ligne source, donc un seul arrêt."""
    lignes = [st.line for st in traces["import_prefixes"]]
    assert lignes == [1, 2, 3, 4]


def test_declaration_de_graphe_globale_est_un_seul_pas(traces):
    """Même chose pour `global @graph as ...` (émis avec un `global`)."""
    lignes = [st.line for st in traces["global_graph"]]
    assert lignes[:6] == [2, 3, 2, 3, 4, 5]


def test_boucle_repasse_par_len_tete(traces):
    """Une boucle revient sur sa ligne d'en-tête : la région bouge à chaque
    tour, ce qui est exactement ce qu'on veut voir."""
    lignes = [st.line for st in traces["boucle_plus"]]
    assert lignes[:5] == [3, 4, 3, 4, 3]


def test_pas_entrant_dans_une_fonction_ldpy(traces):
    """`step in` sur `build(3)` entre dans le corps ldpy de la fonction, et
    `step out` en ressort — le tout en coordonnées .ldpy."""
    stops = traces["fonction"]
    assert [st.line for st in stops][:3] == [4, 3, 4]
    assert stops[1].depth == stops[0].depth + 1
    assert stops[2].depth == stops[0].depth


# ------------------------------------------- la politique justMyCode (103.3)

def test_pas_entrant_sur_un_ilot_ne_descend_pas_dans_le_runtime(tmp_path):
    """Par défaut, `step in` sur un îlot se comporte comme `step over` : le
    runtime ldpy est du code de bibliothèque."""
    source, _, _ = PROGRAMS["ilot_multiligne"]
    stops = trace(str(tmp_path), source, 3, ["in", "in"])
    assert [st.file for st in stops] == ["prog.ldpy"] * len(stops)
    assert [st.line for st in stops][:2] == [3, 5]


def test_just_my_code_false_ouvre_le_runtime_mais_pas_le_lanceur(tmp_path):
    """`justMyCode: false` est la demande explicite de tout voir : le pas
    entrant descend dans le runtime — mais le LANCEUR reste masqué, lui
    n'appartient à personne."""
    source, _, _ = PROGRAMS["ilot_multiligne"]
    stops = trace(str(tmp_path), source, 3, ["in", "in"], just_my_code=False)
    assert any(st.file == "runtime.py" for st in stops), \
        "le runtime devrait être accessible : %r" % (stops,)
    for st in stops:
        assert "debug.py" not in st.files, \
            "le lanceur ne doit jamais apparaître : %r" % (st.files,)


def test_sans_regles_le_lanceur_fuit(tmp_path):
    """Le témoin de la fiche 103 : SANS `rules`, le pas sort du programme et
    atterrit dans `ldpy/debug.py`. C'est la violation que l'on corrige — ce
    test garde la mesure, et échouerait si debugpy changeait d'avis."""
    source, _, _ = PROGRAMS["ilot_multiligne"]
    stops = trace(str(tmp_path), source, 2, ["over"] * 4, rules=[])
    assert any(st.file == "debug.py" for st in stops), \
        "témoin caduc : le lanceur ne fuit plus, revoir la fiche 103"


def test_le_pas_au_dela_de_la_derniere_ligne_termine(tmp_path):
    """Avec les règles, sortir du programme le TERMINE au lieu de révéler la
    plomberie : plus aucun arrêt après la dernière ligne."""
    source, _, _ = PROGRAMS["ilot_multiligne"]
    path = write_program(str(tmp_path), source)
    with DapSession(path, breakpoints=[5], rules=stepping_rules(),
                    timeout=30) as s:
        premier = s.wait_stopped()
        assert premier.line == 5
        s.step_over()
        with pytest.raises(DapError):
            s.wait_stopped(timeout=5)
        assert "2" in s.output


# ---------------------------------------------------------- les points fixés

def test_lambda_dune_expression_differee_porte_la_ligne_de_lilot(tmp_path):
    """Point laissé ouvert par la fiche 103 : le code object de la lambda de
    `e{ }` porte-t-il la position de l'îlot ? Oui — un point d'arrêt sur la
    ligne du `+{ ... e{ } }` s'y lie et s'y arrête."""
    source, _, _ = PROGRAMS["match_et_expression"]
    path = write_program(str(tmp_path), source)
    with DapSession(path, breakpoints=[6], rules=stepping_rules(False),
                    just_my_code=False, timeout=30) as s:
        stops = s.walk(["continue"] * 2)
    profond = [st for st in stops if st.depth > 1]
    assert profond, "la lambda de e{ } ne s'arrête jamais : %r" % (stops,)
    assert all(st.line == 6 for st in stops), \
        "la lambda ne porte pas la ligne de l'îlot : %r" % (stops,)


# --------------------------------------------------------- la règle elle-même

def test_stepping_rules_masque_toujours_le_lanceur():
    chemins = [r["path"] for r in stepping_rules(just_my_code=False)]
    assert any(p.endswith("debug.py") for p in chemins)
    assert any(p.endswith("__main__.py") for p in chemins)
    assert not any(p.endswith("**") for p in chemins)


def test_stepping_rules_masque_tout_le_paquet_sous_just_my_code():
    regles = stepping_rules(just_my_code=True)
    assert regles[-1]["path"].endswith("**")
    assert all(r["include"] is False for r in regles)
    # le lanceur reste devant : premier motif qui matche gagnant chez pydevd
    assert regles[0]["path"].endswith("debug.py")


def test_probe_donne_ce_quil_faut_a_lextension():
    d = probe()
    assert os.path.isdir(d["package"]) and d["package"] == package_dir()
    assert d["rules"]["justMyCode"] == stepping_rules(True)
    assert d["rules"]["all"] == stepping_rules(False)


def test_probe_en_ligne_de_commande():
    """Le chemin exact que suit l'extension : un processus, du JSON, rien
    d'autre sur la sortie standard.

    `cwd` compte : depuis l'espace de travail, le répertoire `ldpy/build/`
    éclipserait le module `ldpy.build` (paquet-espace-de-noms)."""
    import json
    from dapclient import REPO
    p = subprocess.run([sys.executable, "-m", "ldpy.debug", "--probe"],
                       capture_output=True, text=True, timeout=60, cwd=REPO,
                       env=dict(os.environ, PYTHONPATH=REPO))
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["package"] == package_dir()


# ------------------------- points d'arrêt intenables (rabattus, fiche 103)

MULTILIGNE = """\
@prefix ex: <http://example.org/> .
valeur = 21.5
gr = g{ ex:s a ex:Obs ;
        ex:v {valeur} ;
        ex:w 2 }
print(len(gr))
"""


def test_un_point_darret_dans_un_ilot_ne_se_declenche_jamais(tmp_path):
    """Le constat qui justifie le rabattement : debugpy VÉRIFIE un point
    d'arrêt posé au cœur d'un îlot multiligne, et ne s'y arrête jamais."""
    path = write_program(str(tmp_path), MULTILIGNE)
    with DapSession(path, breakpoints=[4, 5], rules=stepping_rules(),
                    timeout=30) as s:
        with pytest.raises(DapError):
            s.wait_stopped(timeout=6)
        assert "3" in s.output          # le programme est allé jusqu'au bout


def test_le_point_darret_rabattu_se_declenche(tmp_path):
    """Rabattu sur la ligne de début de l'îlot, il s'arrête — et à la bonne
    place. C'est ce que l'extension fait faire à la pastille."""
    from ldpy.transpiler import transpile
    from ldpy.transpiler.linemap import snap_breakpoint_lines
    lignes = snap_breakpoint_lines(
        transpile(MULTILIGNE, "prog.ldpy").map, [4, 5])
    assert lignes == [3, 3]
    path = write_program(str(tmp_path), MULTILIGNE)
    with DapSession(path, breakpoints=lignes, rules=stepping_rules(),
                    timeout=30) as s:
        stop = s.wait_stopped()
    assert stop.where[:2] == ("prog.ldpy", 3)
