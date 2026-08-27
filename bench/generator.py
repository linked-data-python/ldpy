"""Génération aléatoire de sources Linked-Data Python, déterministe et valide.

Approche héritée de la génération différentielle de programmes (Csmith) et du
property-based testing (QuickCheck, Hypothesis) : chaque fichier généré est
syntaxiquement valide, EXÉCUTABLE de bout en bout (les noms sont définis avant
usage), et paramétré par :

- ``n_lines``        : taille visée (lignes) ;
- ``island_density`` : fraction des instructions qui sont des îlots (0..1) ;
- ``graph_triples``  : nombre moyen de triplets par graphe g{...} ;
- ``nest_depth``     : profondeur max des nœuds anonymes imbriqués ;
- ``mix``            : poids relatifs des sortes d'îlots ;
- ``v1_compat``      : n'émettre que la syntaxe acceptée par la v1 ANTLR
  (espace après ``g{``, pas d'interpolation nue ``{x}`` ni ``?{...}``) ;
- ``seed``           : même graine -> même fichier, octet pour octet.

Le générateur sert le banc de débit (bench.run) ET les tests de robustesse
(tests/test_generator.py : validité, identité à densité 0, exécution)."""

import random

PREFIX_IRIS = [
    "http://example.org/ns%d#",
    "http://vocab.example.com/v%d/",
    "http://data.example.net/g%d#",
]

DEFAULT_MIX = {
    "pname": 2, "iri": 2, "literal": 2, "var": 1,
    "firi": 1, "fnode": 1, "graph": 3,
}


class _Gen:
    """Un tirage : instancié par generate(), un appel = un fichier."""

    def __init__(self, n_lines, island_density, graph_triples, nest_depth,
                 mix, v1_compat, seed):
        self.rng = random.Random(seed)
        self.n_lines = n_lines
        self.density = island_density
        self.graph_triples = max(1, graph_triples)
        self.nest_depth = nest_depth
        self.mix = mix or DEFAULT_MIX
        self.v1 = v1_compat
        self.lines = []
        self.nvar = 0          # variables int définies : x0..x{nvar-1}
        self.nname = 0         # compteur générique de noms frais
        self.islands = 0
        self.statements = 0
        self.prefixes = []

    # ------------------------------------------------------------ helpers

    def fresh(self, kind="n"):
        """Un nom jamais utilisé (préfixé par sa sorte)."""
        self.nname += 1
        return "%s%d" % (kind, self.nname)

    def xvar(self):
        """Une variable entière déjà définie, au hasard."""
        return "x%d" % self.rng.randrange(self.nvar)

    def emit(self, text):
        self.lines.extend(text.split("\n"))

    def pname(self):
        p = self.rng.choice(self.prefixes)
        return "%s:term%d" % (p, self.rng.randrange(50))

    # ------------------------------------------------------- îlots (expr)

    def island_expr(self):
        """Une expression-îlot, tirée selon les poids de ``mix``."""
        kinds, weights = zip(*sorted(self.mix.items()))
        kind = self.rng.choices(kinds, weights=weights)[0]
        return getattr(self, "_i_" + kind)()

    def _i_pname(self):
        return self.pname()

    def _i_iri(self):
        return "<http://example.org/res/%d>" % self.rng.randrange(1000)

    def _i_literal(self):
        n = self.rng.randrange(100)
        return self.rng.choice([
            '"libell\u00e9 %d"@en' % n,
            '"%d"^^xsd:integer' % n,
            '"texte %d"@fr-CA' % n,
        ])

    def _i_var(self):
        sig = "?" if self.v1 or self.rng.random() < 0.8 else "$"
        return "%sv%d" % (sig, self.rng.randrange(30))

    def _i_firi(self):
        return "f<http://example.org/%s{ %s }/item>" % (
            self.rng.choice(["a/", "b/", ""]), self.xvar())

    def _i_fnode(self):
        if self.v1:
            return "f{ %s }" % self.xvar()
        return self.rng.choice(["?{ %s + %d }", "f{ %s * %d }"]) % (
            self.xvar(), self.rng.randrange(1, 9))

    # ------------------------------------------------------------ graphes

    def _g_object(self, depth):
        r = self.rng.random()
        if depth > 0 and r < 0.15:
            return "[ %s %s ]" % (self.pname(), self._g_object(depth - 1))
        if r < 0.30:
            return "( %s )" % " ".join(
                str(self.rng.randrange(9))
                for _ in range(self.rng.randrange(1, 4)))
        if not self.v1 and r < 0.42:
            return "{%s}" % self.xvar()          # interpolation nue (v2)
        if r < 0.55:
            return self._i_literal()
        if r < 0.65:
            return self._i_fnode()
        if r < 0.72:
            return self._i_var()
        if r < 0.85:
            return self.pname()
        return str(self.rng.randrange(100))

    def _g_subject(self, depth):
        r = self.rng.random()
        if r < 0.5:
            return self.pname()
        if r < 0.75:
            return "<http://example.org/s/%d>" % self.rng.randrange(200)
        return "_:b%d" % self.rng.randrange(20)

    def _i_graph(self):
        parts = []
        remaining = max(1, int(self.rng.gauss(self.graph_triples,
                                              self.graph_triples / 3)))
        while remaining > 0:
            subj = self._g_subject(self.nest_depth)
            npred = min(remaining, self.rng.randrange(1, 4))
            preds = []
            for _ in range(npred):
                verb = "a" if self.rng.random() < 0.2 else self.pname()
                nobj = 1 + (remaining > 2 and self.rng.random() < 0.3)
                objs = ", ".join(self._g_object(self.nest_depth)
                                 for _ in range(nobj))
                preds.append("%s %s" % (verb, objs))
                remaining -= nobj
            parts.append("%s %s" % (subj, " ;\n        ".join(preds)))
        body = " .\n        ".join(parts)
        return "g{ " + body + " }"          # espace après g{ : accepté v1 ET v2

    # -------------------------------------------------------- instructions

    def stmt_island(self):
        t = self.fresh("t")
        self.emit("%s = %s" % (t, self.island_expr()))
        self.islands += 1

    WATER = ("assign", "cond", "func", "loop", "clazz", "compr", "decoys",
             "strings", "dictset")

    def stmt_water(self):
        getattr(self, "_w_" + self.rng.choice(self.WATER))()

    def _w_assign(self):
        # tirer les opérandes AVANT d'allouer la nouvelle variable, sinon
        # x5 = x5 * ... (NameError à l'exécution)
        src = self.xvar() if self.nvar > 0 else "1"
        self.nvar += 1
        self.emit("x%d = %s * %d + %d" % (
            self.nvar - 1, src,
            self.rng.randrange(1, 9), self.rng.randrange(100)))

    def _w_cond(self):
        ops = [self.xvar() for _ in range(4)]
        self.nvar += 1
        self.emit("x%d = %s if %s > %s else %s" % (self.nvar - 1, *ops))

    def _w_func(self):
        f = self.fresh("f")
        body_island = self.rng.random() < self.density
        if body_island:
            inner = ("    r = g{ %s a %s }\n    return len(r) + a"
                     % (self.pname(), self.pname()))
            self.islands += 1
        else:
            inner = "    return a * %d + b" % self.rng.randrange(1, 9)
        self.emit("def %s(a, b=%d):\n%s" % (f, self.rng.randrange(9), inner))
        arg = self.xvar()
        self.nvar += 1
        self.emit("x%d = %s(%s)" % (self.nvar - 1, f, arg))

    def _w_loop(self):
        acc = self.fresh("acc")
        self.emit("%s = 0\nfor i in range(%d):\n    %s += i * %d" % (
            acc, self.rng.randrange(2, 8), acc, self.rng.randrange(1, 5)))

    def _w_clazz(self):
        c = self.fresh("C")
        self.emit("class %s:\n    attr = %d\n"
                  "    def m(self, v):\n        return v + self.attr" % (
                      c, self.rng.randrange(50)))
        arg = self.xvar()
        self.nvar += 1
        self.emit("x%d = %s().m(%s)" % (self.nvar - 1, c, arg))

    def _w_compr(self):
        l = self.fresh("l")
        self.emit("%s = [v * v for v in range(%d) if v != %d]" % (
            l, self.rng.randrange(3, 10), self.rng.randrange(3)))

    def _w_decoys(self):
        # les pièges de la fiche 002 : comparaisons chaînées, slices, dicts.
        # En mode v1_compat, pas de « a<b>c » : la v1 (ANTLR) le lexe comme
        # une IRI et REJETTE ce Python valide — mesuré par la campagne de
        # transparence de bench.run.
        b = self.fresh("b")
        choices = [
            "%s = list(range(9))[%d:%d]" % (b, self.rng.randrange(3),
                                            self.rng.randrange(4, 8)),
            "%s = {%s: %s}" % (b, self.xvar(), self.xvar()),
            "%s = %s <= %s <= %s" % (b, self.xvar(), self.xvar(), self.xvar()),
        ]
        if not self.v1:
            choices.append("%s = %s<%s>%s" % (b, self.xvar(), self.xvar(),
                                              self.xvar()))
        self.emit(self.rng.choice(choices))

    def _w_strings(self):
        s = self.fresh("s")
        self.emit(self.rng.choice([
            "%s = 'g{ leurre } <http://pas/un/ilot> @prefix rien'" % s,
            '%s = f"v={%s} {{accolades}}"' % (s, self.xvar()),
            '%s = """multi\nligne <http://leurre> ?pas_une_var\n"""' % s,
        ]))

    def _w_dictset(self):
        d = self.fresh("d")
        self.emit('%s = {"k%d": %s, "k%d": %s}' % (
            d, self.rng.randrange(9), self.xvar(),
            self.rng.randrange(9, 19), self.xvar()))

    # -------------------------------------------------------------- pilote

    def run(self):
        nprefix = self.rng.randrange(2, 4)
        self.prefixes = ["p%d" % i for i in range(nprefix)] + ["xsd"]
        for i, p in enumerate(self.prefixes[:-1]):
            self.emit("@prefix %s: <%s> ." % (
                p, self.rng.choice(PREFIX_IRIS) % i))
        self.emit("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .")
        self.emit("x0 = %d" % self.rng.randrange(100))
        self.nvar = 1
        while len(self.lines) < self.n_lines:
            self.statements += 1
            if self.rng.random() < self.density:
                self.stmt_island()
            else:
                self.stmt_water()
        src = "\n".join(self.lines) + "\n"
        return src, {
            "lines": len(self.lines) + 1,
            "statements": self.statements,
            "islands": self.islands,
            "island_stmt_ratio": self.islands / max(1, self.statements),
        }


def generate(n_lines=1000, island_density=0.25, graph_triples=4,
             nest_depth=2, mix=None, v1_compat=False, seed=0):
    """Génère un source ldpy ; retourne (source, stats). Déterministe."""
    return _Gen(n_lines, island_density, graph_triples, nest_depth,
                mix, v1_compat, seed).run()
