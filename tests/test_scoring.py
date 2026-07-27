"""Streaming full-data scorer: every row is scored against rules learned on a sample,
chunk by chunk, with exact full-data group statistics."""
import numpy as np, pandas as pd
from norma.core.table import Table
from norma.models import DiscreteCPAD
from norma.scoring import score_file


def _make(tmp_path, n=1000, bad=30):
    rng = np.random.default_rng(0)
    country = [str(i % 10) for i in range(n)]
    continent = [f"c{z}" for z in country]
    badidx = rng.choice(n, bad, replace=False)
    for j in badidx:
        continent[j] = "WRONG"                 # violates country -> continent
    p = tmp_path / "data.csv"
    pd.DataFrame({"country": country, "continent": continent}).to_csv(p, index=False)
    return p, set(int(x) for x in badidx)


def test_scores_every_row_streaming(tmp_path):
    p, bad = _make(tmp_path)
    sample = Table.from_csv(str(p), nrows=300)         # learn on the first 300 rows only
    model = DiscreteCPAD(max_lhs=1, tau=0.9).fit(sample)
    assert any(getattr(r, "rhs", None) == "continent" for r in model.rules())
    res = score_file(model, str(p), chunksize=200)     # full 1000 rows, 5 chunks
    assert res["rows"] == 1000                         # ALL rows scored, not just the sample
    assert res["flagged"] == len(bad)                  # every planted violation caught
    assert res["top"][0]["score"] > 0.9


def test_writes_scored_file(tmp_path):
    p, bad = _make(tmp_path)
    model = DiscreteCPAD(max_lhs=1, tau=0.9).fit(Table.from_csv(str(p)))
    out = tmp_path / "scored.csv"
    score_file(model, str(p), out_path=str(out), chunksize=200)
    df = pd.read_csv(out)
    assert len(df) == 1000
    assert "norma_score" in df.columns and "norma_rule" in df.columns
    assert int((df["norma_score"] >= 0.5).sum()) == len(bad)


def test_streaming_learn_matches_inmemory_and_covers_all(tmp_path):
    from norma.scoring import learn_fds_streaming
    p, bad = _make(tmp_path, n=1000, bad=30)
    sm = learn_fds_streaming(str(p), id_cardinality=300, tau=0.9, chunksize=200)  # FULL file, no sample
    dm = DiscreteCPAD(max_lhs=1, tau=0.9).fit(Table.from_csv(str(p)))             # in-memory full
    assert {(r.lhs, r.rhs) for r in sm.rules()} == {(r.lhs, r.rhs) for r in dm.rules()}
    assert sm.rules()                                                            # non-empty
    res = score_file(sm, str(p), chunksize=200)
    assert res["rows"] == 1000 and res["flagged"] == len(bad)
