"""Garde-fou de performance : la raison d'être de v2.

Référence v1 (ANTLR, mesurée le 2026-08-26) : ~170 lignes/s.
Exigence minimale ici : > 3 400 lignes/s (x20) ; objectif affiché : > 10 000."""

import time

import pytest

from ldpy.transpiler import transpile

CHUNK = """\
@prefix ex: <http://example.org/ns#> .
@base <http://example.org/data/> .

def observation(capteur, valeur):
    unite = "cel"
    return g{ ex:{capteur} a ex:Sensor ;
                 ex:madeObservation [ ex:hasSimpleResult {valeur} ;
                                      ex:unit ex:{unite} ] }

class Station:
    def __init__(self, nom):
        self.nom = nom
        self.iri = f<station/{ nom }>
        self.graphe = g{ ?s a ex:Station ; ex:label "station"@fr }

    def mesure(self, v):
        if v < 0:
            return None
        return observation(self.nom, v)

for i in range(3):
    s = Station("st" + str(i))
    o = s.mesure(i * 2.5)
"""


@pytest.mark.slow
def test_throughput():
    src = CHUNK * 40   # ~1080 lignes
    nlines = src.count("\n")
    t0 = time.perf_counter()
    transpile(src, "<bench>")
    dt = time.perf_counter() - t0
    rate = nlines / dt
    print("\nldpy v2 : %d lignes en %.3fs -> %d lignes/s" % (nlines, dt, rate))
    assert rate > 3400, "objectif minimal x20 vs v1 non atteint : %d l/s" % rate


@pytest.mark.slow
def test_throughput_pure_python():
    src = ("def f(a, b):\n    return {k: v for k, v in zip(a, b) if v < 3}\n"
           "x = f(range(10), range(10))\n") * 400
    nlines = src.count("\n")
    t0 = time.perf_counter()
    result = transpile(src, "<bench-py>")
    dt = time.perf_counter() - t0
    assert result.code == src
    rate = nlines / dt
    print("\nldpy v2 (py pur) : %d lignes/s" % rate)
    assert rate > 10000
