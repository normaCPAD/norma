"""Freeze a contract from discovery, then check catches a re-introduced violation."""
import pandas as pd
from norma.core.table import Table
from norma.models import DiscreteCPAD
from norma.modeling.report import build_model
from norma import contract as ct


def _clean():
    # country -> continent is a clean FD; (country) is not unique (repeated), continent follows country
    return pd.DataFrame({"country": ["Japan", "Japan", "Kenya", "Kenya", "Brazil", "Brazil"],
                         "continent": ["Asia", "Asia", "Africa", "Africa", "SouthAmerica", "SouthAmerica"]})


def test_freeze_then_check_clean_passes():
    t = Table.from_pandas(_clean())
    model = DiscreteCPAD(max_lhs=1).fit(t)
    contract = ct.freeze(build_model(t, model, top_anomalies=0))
    assert any(c["kind"] == "fd" for c in contract["constraints"])
    results = ct.check(t, contract)
    assert all(r.ok for r in results), [(r.id, r.detail) for r in results if not r.ok]


def test_check_catches_violation():
    df = _clean()
    t = Table.from_pandas(df)
    contract = ct.freeze(build_model(t, DiscreteCPAD(max_lhs=1).fit(t), top_anomalies=0))
    dirty = df.copy(); dirty.loc[0, "continent"] = "Europe"     # break country->continent in group Japan
    res = ct.check(Table.from_pandas(dirty), contract)
    fd = [r for r in res if r.kind == "fd"]
    assert fd and any(r.violations >= 1 for r in fd)


def test_yaml_roundtrip(tmp_path):
    t = Table.from_pandas(_clean())
    c = ct.freeze(build_model(t, DiscreteCPAD(max_lhs=1).fit(t), top_anomalies=0))
    p = tmp_path / "norma.yml"; p.write_text(ct.dump(c))
    assert ct.load(str(p))["constraints"] == c["constraints"]
