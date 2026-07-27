"""Large-data guard: readers honour nrows, and the studio caps its working set so a huge
file neither exhausts memory nor freezes the UI."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pandas as pd, pytest
from norma.core.table import Table


def test_reader_nrows_bounds_rows(tmp_path):
    p = tmp_path / "big.csv"
    pd.DataFrame({"a": range(1000), "b": range(1000)}).to_csv(p, index=False)
    assert Table.from_any(str(p), nrows=50).n == 50
    assert Table.from_csv(str(p), nrows=10).n == 10
    assert Table.from_any(str(p)).n == 1000          # no cap by default


def test_studio_caps_large_file(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from norma.studio import session as S
    monkeypatch.setattr(S, "MAX_ROWS", 200)          # tiny cap for the test
    p = tmp_path / "big.csv"
    pd.DataFrame({"country": [str(i % 30) for i in range(5000)],
                  "continent": [f"c{i % 30}" for i in range(5000)]}).to_csv(p, index=False)
    s = S.NormaSession(); s.load_path(str(p))
    assert s.table.n == 200                          # working set bounded, not 5000
    s.analyze()                                      # runs on the bounded sample
    assert s.model is not None
