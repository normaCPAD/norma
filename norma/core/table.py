"""The Table abstraction: a tabular dataset with inferred column kinds and the
encodings the CPAD models consume.

Column kinds
------------
NUMERIC      : >95% of values parse as numbers and cardinality <= id_cardinality
IDENTIFIER   : cardinality > id_cardinality (keys, names, free text) -- skipped for
               FD/DC discovery, as such columns are not governed by constraints
CATEGORICAL  : everything else

`modeling_columns()` returns the columns usable for constraint discovery (more than
one value, not identifier-like).
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd

CATEGORICAL, NUMERIC, IDENTIFIER = "categorical", "numeric", "identifier"


def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


class Table:
    def __init__(self, df: pd.DataFrame, name: str = "table", id_cardinality: int = 300):
        self.df = df.reset_index(drop=True)
        self.name = name
        self.columns = list(self.df.columns)
        self.n = len(self.df)
        self.id_cardinality = id_cardinality
        self.kinds = {c: self._infer_kind(c) for c in self.columns}

    @staticmethod
    def _normalize(df: pd.DataFrame) -> pd.DataFrame:
        """Coerce every column to a stripped string (the form the CPAD models consume).

        Constraint discovery is value-based, so all backends are reduced to the same
        textual representation; numeric/order learners re-parse the strings on demand.
        """
        df = df.where(df.notna(), "").astype(str)
        return df.apply(lambda s: s.str.strip())

    @classmethod
    def from_pandas(cls, df: pd.DataFrame, name: str = "table", **kwargs) -> "Table":
        return cls(cls._normalize(df), name=name, **kwargs)

    @classmethod
    def from_csv(cls, path: str, name: str | None = None, nrows: int | None = None,
                 **kwargs) -> "Table":
        # nrows bounds memory/time on very large files: pandas stops after nrows rows
        # without scanning the rest, so a multi-GB CSV never loads in full.
        df = pd.read_csv(path, dtype=str, nrows=nrows)
        return cls.from_pandas(df, name=name or _stem(path), **kwargs)

    @classmethod
    def from_parquet(cls, path: str, name: str | None = None, nrows: int | None = None,
                     **kwargs) -> "Table":
        df = pd.read_parquet(path)
        if nrows is not None:
            df = df.head(nrows)
        return cls.from_pandas(df, name=name or _stem(path), **kwargs)

    @classmethod
    def from_excel(cls, path: str, name: str | None = None, sheet=0,
                   nrows: int | None = None, **kwargs) -> "Table":
        return cls.from_pandas(pd.read_excel(path, sheet_name=sheet, dtype=str, nrows=nrows),
                               name=name or _stem(path), **kwargs)

    @classmethod
    def from_json(cls, path: str, name: str | None = None, nrows: int | None = None,
                  **kwargs) -> "Table":
        # newline-delimited JSON or a JSON array of records
        try:
            df = pd.read_json(path, lines=path.endswith((".jsonl", ".ndjson")),
                              nrows=nrows if path.endswith((".jsonl", ".ndjson")) else None)
        except ValueError:
            df = pd.read_json(path)
        if nrows is not None:
            df = df.head(nrows)
        return cls.from_pandas(df, name=name or _stem(path), **kwargs)

    @classmethod
    def from_duckdb(cls, source: str, query: str | None = None,
                    name: str | None = None, nrows: int | None = None, **kwargs) -> "Table":
        """Read via DuckDB: a file it can scan (Parquet/CSV/JSON, incl. globs) or an
        explicit SQL ``query``. Lets NORMA reach data-lake files without loading them
        fully into pandas first. Requires the optional ``duckdb`` dependency."""
        import duckdb
        sql = query or f"SELECT * FROM '{source}'"
        if nrows is not None and query is None:
            sql += f" LIMIT {int(nrows)}"
        df = duckdb.sql(sql).df()
        if nrows is not None:
            df = df.head(nrows)
        return cls.from_pandas(df, name=name or _stem(source), **kwargs)

    _READERS = {".csv": "from_csv", ".tsv": "from_csv", ".parquet": "from_parquet",
                ".pq": "from_parquet", ".xlsx": "from_excel", ".xls": "from_excel",
                ".json": "from_json", ".jsonl": "from_json", ".ndjson": "from_json"}

    @classmethod
    def from_any(cls, path: str, name: str | None = None, nrows: int | None = None,
                 **kwargs) -> "Table":
        """Dispatch on file extension to the right reader (CSV/Parquet/Excel/JSON).

        ``nrows`` caps how many rows are read, bounding memory and latency on large files.
        """
        ext = os.path.splitext(path)[1].lower()
        reader = cls._READERS.get(ext)
        if reader is None:
            raise ValueError(f"unsupported extension {ext!r}; supported: "
                             f"{', '.join(sorted(cls._READERS))} (or use from_duckdb)")
        return getattr(cls, reader)(path, name=name, nrows=nrows, **kwargs)

    # -- column typing -------------------------------------------------------
    def numeric_fraction(self, col: str) -> float:
        return float(pd.to_numeric(self.df[col], errors="coerce").notna().mean())

    def cardinality(self, col: str) -> int:
        return int(self.df[col].nunique())

    def _infer_kind(self, col: str) -> str:
        card = self.cardinality(col)
        if card > self.id_cardinality:
            return IDENTIFIER
        if self.numeric_fraction(col) > 0.95:
            return NUMERIC
        return CATEGORICAL

    def modeling_columns(self) -> list[str]:
        """Columns eligible for FD/DC discovery: constant columns and identifiers excluded."""
        return [c for c in self.columns if 1 < self.cardinality(c) <= self.id_cardinality]

    def numeric_columns(self) -> list[str]:
        return [c for c in self.modeling_columns() if self.kinds[c] == NUMERIC]

    def profile(self, model=None, top: int = 10):
        """Discover constraints and return a data-model report (renders inline in notebooks)."""
        from norma.modeling.report import profile
        return profile(self, model=model, top=top)

    # -- encodings -----------------------------------------------------------
    def codes(self, cols: list[str] | None = None):
        """Integer-encode the given columns. Returns (codes[n, k], cardinalities[k])."""
        cols = cols or self.columns
        mats, cards = [], []
        for c in cols:
            code, uniq = pd.factorize(self.df[c])
            mats.append(code); cards.append(len(uniq))
        return np.stack(mats, axis=1), cards

    def numeric_matrix(self, cols: list[str] | None = None):
        cols = cols if cols is not None else self.numeric_columns()
        if not cols:
            return np.zeros((self.n, 0)), []
        X = np.column_stack([pd.to_numeric(self.df[c], errors="coerce").to_numpy(float) for c in cols])
        return X, cols

    def error_mask_vs(self, clean: "Table") -> np.ndarray:
        """Cell-level ground-truth mask (dirty != clean) for aligned clean/dirty tables."""
        if list(clean.columns) != self.columns or clean.n != self.n:
            raise ValueError("clean table must be row- and column-aligned")
        return self.df.values != clean.df.values

    def __repr__(self) -> str:
        return f"Table({self.name!r}, n={self.n}, cols={len(self.columns)})"
