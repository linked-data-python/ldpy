"""Campagnes de mesure du débit de transpilation (4e artefact).

    python -m bench.run [--quick] [--out bench/results]

Trois campagnes, sur des fichiers issus de bench.generator (graines fixées,
reproductibles) :

- ``density``   : débit en fonction de la densité d'îlots (0 -> 100 %) ;
- ``size``      : débit en fonction de la taille du fichier (linéarité) ;
- ``graphsize`` : débit en fonction de la taille des graphes g{...} ;
Sorties : results.json + un CSV par campagne (consommés par l'article).
Le chronométrage est un meilleur-de-N sur transpile() seul (pas d'E/S).
"""

import argparse
import json
import os
import sys
import time
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.generator import generate                      # noqa: E402
from ldpy.transpiler import transpile                     # noqa: E402


def best_of(fn, reps):
    """Meilleur temps (secondes) de ``reps`` exécutions de ``fn``."""
    best = None
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        dt = time.perf_counter() - t0
        best = dt if best is None or dt < best else best
    return best


def v2_lps(src, reps=3):
    """Débit v2 (lignes source/s), meilleur de ``reps``."""
    dt = best_of(lambda: transpile(src, "<bench>"), reps)
    return src.count("\n") / dt


_V1 = None


def v1_transform():
    """Charge la chaîne v1 (ANTLR) une seule fois ; None si indisponible."""
    global _V1
    if _V1 is None:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from ldpy.ldpy import transform_source
            _V1 = transform_source
        except Exception as e:
            print("v1 indisponible :", e, file=sys.stderr)
            _V1 = False
    return _V1 or None


def v1_lps(src, reps=1):
    """Débit v1 ANTLR (lignes source/s), ou None si indisponible/rejeté."""
    tf = v1_transform()
    if tf is None:
        return None
    try:
        dt = best_of(lambda: tf(src, "<bench>"), reps)
    except Exception as e:
        print("v1 : échec de parse (%s)" % e, file=sys.stderr)
        return None
    return src.count("\n") / dt


# ------------------------------------------------------------------ campagnes

def campaign_density(quick):
    """Débit en fonction de la densité d'îlots (0 -> 100 %)."""
    size = 500 if quick else 2000
    densities = [0.0, 0.25, 1.0] if quick else \
        [0.0, 0.05, 0.10, 0.25, 0.50, 0.75, 1.0]
    seeds = [0] if quick else [0, 1, 2]
    rows = []
    for d in densities:
        rates, ratio = [], 0.0
        for s in seeds:
            src, st = generate(n_lines=size, island_density=d, seed=s)
            rates.append(v2_lps(src))
            ratio += st["island_stmt_ratio"]
        rows.append({"density": d, "lps": sum(rates) / len(rates),
                     "island_stmt_ratio": ratio / len(seeds)})
        print("  densité %.2f : %7.0f l/s" % (d, rows[-1]["lps"]))
    return rows


def campaign_size(quick):
    """Débit en fonction de la taille du fichier (linéarité attendue)."""
    sizes = [200, 2000] if quick else [200, 1000, 5000, 20000, 50000]
    rows = []
    for n in sizes:
        src, _ = generate(n_lines=n, island_density=0.25, seed=0)
        dt = best_of(lambda: transpile(src, "<bench>"), 2 if n > 20000 else 3)
        rows.append({"lines": src.count("\n"), "ms": dt * 1000,
                     "lps": src.count("\n") / dt})
        print("  %6d lignes : %8.1f ms, %7.0f l/s" % (
            rows[-1]["lines"], rows[-1]["ms"], rows[-1]["lps"]))
    return rows


def campaign_graphsize(quick):
    """Débit en fonction du nombre de triplets par graphe (amortissement)."""
    triples = [1, 20] if quick else [1, 5, 20, 100]
    rows = []
    for t in triples:
        src, _ = generate(n_lines=500 if quick else 2000, island_density=1.0,
                          graph_triples=t, mix={"graph": 1}, seed=0)
        rows.append({"triples": t, "lps": v2_lps(src)})
        print("  %3d triplets/graphe : %7.0f l/s" % (t, rows[-1]["lps"]))
    return rows


def write_csv(path, rows, cols):
    """Écrit ``rows`` (dicts) en CSV, colonnes ``cols``."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join("" if r.get(c) is None else "%.6g" % r[c]
                             for c in cols) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bench.run", description=__doc__)
    parser.add_argument("--quick", action="store_true",
                        help="campagnes réduites (tests / fumée)")
    parser.add_argument("--out", default="bench/results")
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    import platform
    results = {"quick": args.quick,
               "python": platform.python_version(),
               "machine": platform.machine()}
    print("— densité d'îlots —")
    results["density"] = campaign_density(args.quick)
    print("— taille de fichier —")
    results["size"] = campaign_size(args.quick)
    print("— taille des graphes —")
    results["graphsize"] = campaign_graphsize(args.quick)

    with open(os.path.join(args.out, "results.json"), "w") as f:
        json.dump(results, f, indent=1)
    write_csv(os.path.join(args.out, "density.csv"), results["density"],
              ["density", "lps"])
    write_csv(os.path.join(args.out, "size.csv"), results["size"],
              ["lines", "ms", "lps"])
    write_csv(os.path.join(args.out, "graphsize.csv"), results["graphsize"],
              ["triples", "lps"])
    print("résultats écrits dans", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
