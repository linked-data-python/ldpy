"""Le 4e artefact (bench/) est lui-même testé : déterminisme, validité,
propriété d'identité à densité nulle, exécutabilité."""

import pytest

from bench.generator import generate
from ldpy.transpiler import transpile


def test_deterministic_same_seed():
    a, _ = generate(n_lines=200, island_density=0.4, seed=7)
    b, _ = generate(n_lines=200, island_density=0.4, seed=7)
    assert a == b


def test_different_seeds_differ():
    a, _ = generate(n_lines=200, island_density=0.4, seed=1)
    b, _ = generate(n_lines=200, island_density=0.4, seed=2)
    assert a != b


@pytest.mark.parametrize("density", [0.0, 0.1, 0.5, 1.0])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_generated_files_transpile(density, seed):
    src, _ = generate(n_lines=300, island_density=density, seed=seed)
    transpile(src, "<gen>")          # ne doit pas lever


def test_density_zero_below_prefixes_is_identity():
    """À densité 0, tout SAUF les @prefix d'en-tête est du Python pur :
    la partie après l'en-tête ressort byte-identique."""
    src, stats = generate(n_lines=400, island_density=0.0, seed=3)
    assert stats["islands"] == 0
    body = "\n".join(l for l in src.split("\n")
                     if not l.startswith("@prefix"))
    r = transpile(body, "<gen>")
    assert r.code == body


@pytest.mark.parametrize("seed", [0, 5])
def test_generated_files_execute(seed):
    src, _ = generate(n_lines=250, island_density=0.5, seed=seed)
    r = transpile(src, "<gen>")
    g = {}
    exec(compile(r.code, "<gen>", "exec"), g)     # ne doit pas lever
    assert any(k.startswith("t") for k in g)      # des termes ont été produits


def test_island_ratio_tracks_density():
    _, low = generate(n_lines=800, island_density=0.1, seed=0)
    _, high = generate(n_lines=800, island_density=0.9, seed=0)
    assert low["island_stmt_ratio"] < 0.25
    assert high["island_stmt_ratio"] > 0.7


def test_graph_only_mix():
    src, stats = generate(n_lines=200, island_density=1.0,
                          mix={"graph": 1}, graph_triples=10, seed=1)
    assert src.count("g{") >= 5
    transpile(src, "<gen>")


def test_v1_compat_mode_avoids_v2_only_syntax():
    import re
    src, _ = generate(n_lines=400, island_density=0.6, v1_compat=True, seed=4)
    assert "?{" not in src and "$" not in src
    # pas d'interpolation nue « {xN} » en position de terme (les f-strings
    # Python de la « mer », elles, ont le droit de contenir {x9})
    assert re.search(r" \{x\d+\}", src) is None
    transpile(src, "<gen>")                       # et v2 l'accepte aussi


def test_quick_campaign_runs(tmp_path):
    from bench.run import main
    assert main(["--quick", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "results.json").is_file()
    assert (tmp_path / "density.csv").read_text().startswith("density,lps")
