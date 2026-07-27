"""Multi-format ingestion: CSV/Parquet/Excel/JSON reduce to the same normalized Table."""
import pandas as pd, pytest
from norma.core.table import Table

DF = pd.DataFrame({"country": ["Japan", "Japan", "Kenya"], "continent": ["Asia", "Asia", "Africa"],
                   "qty": [2, 3, 1]})


def _check(t: Table):
    assert t.n == 3 and t.columns == ["country", "continent", "qty"]
    assert t.df["qty"].tolist() == ["2", "3", "1"]          # everything is stripped string
    assert t.kinds["qty"] == "numeric"


def test_from_pandas():
    _check(Table.from_pandas(DF, name="t"))


def test_from_csv(tmp_path):
    p = tmp_path / "t.csv"; DF.to_csv(p, index=False)
    _check(Table.from_any(str(p)))


def test_from_parquet(tmp_path):
    pytest.importorskip("pyarrow")
    p = tmp_path / "t.parquet"; DF.to_parquet(p, index=False)
    _check(Table.from_any(str(p)))


def test_from_excel(tmp_path):
    pytest.importorskip("openpyxl")
    p = tmp_path / "t.xlsx"; DF.to_excel(p, index=False)
    _check(Table.from_any(str(p)))


def test_from_json(tmp_path):
    p = tmp_path / "t.json"; DF.to_json(p, orient="records")
    _check(Table.from_any(str(p)))


def test_unknown_extension(tmp_path):
    p = tmp_path / "t.weird"; p.write_text("x")
    with pytest.raises(ValueError):
        Table.from_any(str(p))
