"""The studio surfaces the headless capabilities (offscreen; skipped without PySide6)."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
pytest.importorskip("PySide6")
import pandas as pd
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def test_studio_exposes_export_and_contract(tmp_path):
    from norma.studio.session import NormaSession
    from norma.studio.app import MainWindow
    from norma.export import FORMATS, export
    from norma import contract as ct

    csv = tmp_path / "t.csv"
    pd.DataFrame({"country": ["Japan"]*20 + ["Kenya"]*20,
                  "continent": ["Asia"]*19 + ["Europe"] + ["Africa"]*20}).to_csv(csv, index=False)

    s = NormaSession(); w = MainWindow(s)
    assert all(hasattr(w, a) for a in ("a_export_dq", "a_freeze", "a_check"))

    s.load_path(str(csv)); s.analyze(); w._update_actions()
    assert w.a_export_dq.isEnabled() and w.a_freeze.isEnabled() and w.a_check.isEnabled()

    report = s.build_report()
    assert report.rules
    assert any(a.get("reason", "").startswith("violates") for a in report.anomalies)
    assert all(export(report, fmt, kinds=s.table.kinds) for fmt in FORMATS)
    assert len(ct.check(s.table, ct.freeze(report))) >= 1


def test_studio_opens_parquet(tmp_path):
    from norma.studio.session import NormaSession
    pq = tmp_path / "t.parquet"
    pd.DataFrame({"a": ["1", "2"], "b": ["x", "y"]}).to_parquet(pq)
    s = NormaSession(); s.load_path(str(pq))
    assert s.table is not None and s.table.n == 2
