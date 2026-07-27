"""Notebook repr + the 'error != rare' per-cell surfacing."""
import pandas as pd
from norma.core.table import Table
from norma.models import DiscreteCPAD


def _report():
    country = ["Japan"] * 20 + ["Kenya"] * 20
    continent = ["Asia"] * 19 + ["Europe"] + ["Africa"] * 20   # one violation of country->continent
    t = Table.from_pandas(pd.DataFrame({"country": country, "continent": continent}))
    return t.profile(model=DiscreteCPAD(max_lhs=1), top=5)


def test_profile_finds_fd_and_flags_violation():
    rep = _report()
    assert any(getattr(c, "rhs", None) == "continent" for c in rep.rules)
    assert rep.anomalies and "reason" in rep.anomalies[0]
    assert any(a["reason"].startswith("violates") for a in rep.anomalies)


def test_repr_html_renders():
    html = _report()._repr_html_()
    assert "NORMA data model" in html
    assert "violates a constraint" in html
    assert "<table>" in html
