"""Jeux de caractères Python vs Turtle/SPARQL (fiche DESIGN_CHOICES/ldpy/010).

Les deux ensembles sont INCOMPARABLES (mesuré sur le BMP : 3 400 caractères
Turtle-seulement dont '-', 4 Python-seulement : ª µ º ⁔). Ces tests figent le
choix courant de v2 pour que tout changement soit délibéré :

- déclencheurs (préfixe, ?var) : identifiants ASCII ;
- partie locale : continuation Unicode-alphanumérique (règle Python), plus
  '-' et '.' à l'intérieur des îlots ;
- une déclaration @prefix au préfixe non ASCII est une ERREUR claire, pas un
  massacre silencieux."""

import pytest

from ldpy.transpiler import transpile, LdpySyntaxError

P = "@prefix ex: <http://e/> .\n"


def test_unicode_local_continue_outside_island(run):
    g, _ = run(P + "t = ex:café\n")
    assert str(g["t"]) == "http://e/café"


def test_unicode_local_in_island(run):
    g, _ = run(P + "gr = g{ ex:café ex:p 1 }\n")
    assert any(str(s).endswith("café") for s, _, _ in g["gr"])


def test_hyphen_local_inside_island_only(run):
    g, _ = run(P + "gr = g{ ex:a-b ex:p 1 }\n")
    assert any(str(s).endswith("a-b") for s, _, _ in g["gr"])
    # hors îlot, '-' reste une soustraction : ex:a-b == (ex:a) - b
    r = transpile(P + "t = ex:a-b\n")
    assert "URIRef('http://e/a') -" in r.code.replace("  ", " ") or \
        "URIRef('http://e/a')-" in r.code or "- b" in r.code


def test_non_ascii_prefix_declaration_is_clear_error():
    with pytest.raises(LdpySyntaxError) as e:
        transpile("@prefix é: <http://e/> .\nx = 1\n")
    assert "ASCII" in str(e.value)


def test_decorator_named_prefix_still_untouched():
    src = "@prefix\ndef f():\n    pass\n"
    assert transpile(src).code == src


def test_turtle_only_char_rejected_in_island():
    # U+02C2 est dans PN_CHARS_BASE (Turtle) mais pas un identifiant Python :
    # v2 le refuse — choix documenté (fiche 010), pas un accident
    with pytest.raises(LdpySyntaxError):
        transpile(P + "gr = g{ ex:a˂b ex:p 1 }\n")


def test_python_only_chars_do_not_leak_into_pnames(run):
    # µ (U+00B5) est un identifiant Python mais PAS dans PN_CHARS :
    # v2 l'accepte en continuation locale (règle Python assumée, fiche 010)
    g, _ = run(P + "t = ex:aµb\n")
    assert str(g["t"]) == "http://e/aµb"
