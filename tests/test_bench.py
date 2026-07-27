"""Bench harness: discovery + metrics on a tiny synthetic clean/dirty pair."""
import numpy as np, pandas as pd
from norma.bench import discover_datasets, evaluate
from norma.models import DiscreteCPAD


def _pair(tmp_path):
    rng = np.random.default_rng(0); n = 200
    country = rng.integers(0, 20, n).astype(str)
    continent = pd.Series(country).map(lambda v: f"continent_{v}")   # clean FD country -> continent
    clean = pd.DataFrame({"country": country, "continent": continent})
    dirty = clean.copy()
    idx = rng.choice(n, 20, replace=False)                     # corrupt 10% of continent cells
    dirty.loc[idx, "continent"] = "WRONG"
    d = tmp_path / "toy"; d.mkdir()
    clean.to_csv(d / "clean.csv", index=False); dirty.to_csv(d / "dirty.csv", index=False)
    return tmp_path


def test_discovery_both_layouts(tmp_path):
    root = _pair(tmp_path)
    found = discover_datasets(str(root))
    assert "toy" in found and all(p.endswith(".csv") for p in found["toy"])


def test_metrics_beat_chance(tmp_path):
    root = _pair(tmp_path)
    cp, dp = discover_datasets(str(root))["toy"]
    row = evaluate(cp, dp, lambda: DiscreteCPAD(max_lhs=1), name="toy")
    assert 0.0 <= row.error_rate <= 0.2
    assert row.tuple_auroc > 0.8        # CPAD finds the relational errors
    assert row.cell_auroc > 0.8
