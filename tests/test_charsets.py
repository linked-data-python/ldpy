"""Jeux de caractères Python vs Turtle/SPARQL — décision ACTÉE (option B+C) :

- DANS les îlots : tables PN_CHARS EXACTES de Turtle (préfixes PN_PREFIX avec
  tirets et points intérieurs, locals à chiffre initial, U+02C2…) ;
- HORS îlots : INTERSECTION identifiant Python ∩ PN_CHARS (on ne peut pas
  capturer du Python valide ; µ/ª, Python-seulement, sont exclus) ;
- l'oracle tools/charsets.py vérifie les tables du transpileur contre une
  transcription indépendante des specs (test dédié en bas de ce fichier).

Limitation documentée : pas de ':' intérieur ni d'échappements PLX dans les
parties locales."""

import pytest

from ldpy.transpiler import transpile, LdpySyntaxError

P = "@prefix ex: <http://e/> .\n"


# ------------------------------------------------- hors îlots : intersection

def test_unicode_local_continue_outside_island(run):
    g, _ = run(P + "t = ex:café\n")            # é ∈ Python ∩ PN_CHARS
    assert str(g["t"]) == "http://e/café"


def test_python_only_char_stops_local_outside(run):
    # µ est un identifiant Python mais PAS un PN_CHARS : la partie locale
    # s'arrête avant (alignement Turtle ; Turtle ne sait pas écrire ex:aµb)
    r = transpile(P + "t = ex:a\nµb = 1\n")
    assert "URIRef('http://e/a')" in r.code


def test_hyphen_still_subtraction_outside(run):
    r = transpile(P + "t = ex:a-b\n")
    assert "URIRef('http://e/a')" in r.code and "- b" in r.code.replace("-b", "- b")


# ------------------------------------------------------- déclarations

def test_unicode_prefix_declaration_now_valid(run):
    g, _ = run("@prefix é: <http://e/> .\nx = é:y\n")
    assert str(g["x"]) == "http://e/y"


def test_hyphenated_prefix_declarable_island_only(run):
    """o-pizza: (préfixe réel de tpl.ottr.xyz) : déclarable, utilisable DANS
    les îlots ; hors îlot, o-pizza n'est pas un identifiant Python -> jamais
    déclenché (o - pizza reste une soustraction)."""
    src = "@prefix o-pizza: <http://t/p/> .\ngr = g{ o-pizza:Named ex:p 1 }\n"
    g, _ = run(P + src)
    assert any(str(s) == "http://t/p/Named" for s, _, _ in g["gr"])
    r = transpile(P + src + "o = 1\npizza = 2\nx = o-pizza\n")
    assert "x = o-pizza" in r.code             # hors îlot : du Python intact


def test_dotted_prefix_declaration(run):
    g, _ = run("@prefix a.b: <http://d/> .\ngr = g{ a.b:x <http://p> 1 }\n")
    assert any(str(s) == "http://d/x" for s, _, _ in g["gr"])


def test_invalid_prefix_declaration_still_clear_error():
    with pytest.raises(LdpySyntaxError) as e:
        transpile("@prefix 1x: <http://e/> .\ny = 1\n")
    assert "PN_PREFIX" in str(e.value)


# ------------------------------------------------- dans les îlots : exact

def test_turtle_only_char_accepted_in_island(run):
    # U+02C2 ∈ PN_CHARS_BASE : accepté en îlot (c'était refusé avant B)
    g, _ = run(P + "gr = g{ ex:a˂b ex:p 1 }\n")
    assert any(str(s) == "http://e/a˂b" for s, _, _ in g["gr"])


def test_digit_start_local_in_island(run):
    g, _ = run(P + "gr = g{ ex:1a ex:p 1 }\n")   # PN_LOCAL : chiffre en tête
    assert any(str(s) == "http://e/1a" for s, _, _ in g["gr"])


def test_hyphen_and_inner_dots_in_island(run):
    g, _ = run(P + "gr = g{ ex:Li-ion.v2 ex:p 1 . ex:x ex:q ex:fin. }\n")
    subs = {str(s) for s, _, _ in g["gr"]}
    assert "http://e/Li-ion.v2" in subs
    objs = {str(o) for _, _, o in g["gr"]}
    assert "http://e/fin" in objs               # '.' final = ponctuation


def test_blank_label_digit_start_in_island(run):
    g, _ = run(P + "gr = g{ _:1b ex:p 1 . _:1b ex:q 2 }\n")
    assert len({s for s, _, _ in g["gr"]}) == 1


def test_middle_dot_and_combining_marks_in_island(run):
    g, _ = run(P + "gr = g{ ex:a·b ex:p 1 }\n")  # U+00B7 ∈ PN_CHARS
    assert any(str(s) == "http://e/a·b" for s, _, _ in g["gr"])


# ---------------------------------------------- l'oracle vérifie les tables

def test_tables_match_independent_transcription():
    """Option C : tools/charsets.py transcrit les specs indépendamment ;
    les tables du transpileur doivent coïncider sur tout le BMP."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from tools.charsets import verify_against_transpiler
    mismatches = verify_against_transpiler(limit=0x10000)
    assert mismatches == [], mismatches[:10]
