"""Reproducible error-detection benchmark on aligned clean/dirty table pairs (the Raha/Baran
layout: ``<name>/clean.csv`` + ``<name>/dirty.csv``, or ``<name>_clean.csv`` + ``<name>_dirty.csv``).

For each dataset it fits a CPAD learner on the *dirty* table (unsupervised) and reports
cell- and tuple-level AUROC/AUPRC against the ground-truth error mask (dirty != clean),
next to an Isolation-Forest baseline. One command, comparable numbers:

    norma bench --data ./datasets --learner routed
"""
from __future__ import annotations
import os
from dataclasses import dataclass, asdict

import numpy as np

from norma.core.table import Table


# -- dataset discovery -------------------------------------------------------
def discover_datasets(root: str) -> dict:
    """Map dataset name -> (clean_path, dirty_path) for both common layouts."""
    out: dict[str, list] = {}
    for dirpath, _dirs, files in os.walk(root):
        fset = {f.lower(): f for f in files}
        # layout A: a folder named <name> holding clean.* and dirty.*
        clean = next((fset[k] for k in fset if k.startswith("clean.")), None)
        dirty = next((fset[k] for k in fset if k.startswith("dirty.")), None)
        if clean and dirty:
            out[os.path.basename(dirpath)] = (os.path.join(dirpath, clean),
                                              os.path.join(dirpath, dirty))
        # layout B: <name>_clean.* and <name>_dirty.* side by side
        for k, f in fset.items():
            if "_clean." in k:
                base = f[: k.index("_clean.")]
                dk = k.replace("_clean.", "_dirty.")
                if dk in fset:
                    out[base] = (os.path.join(dirpath, f),
                                 os.path.join(dirpath, fset[dk]))
    return dict(sorted(out.items()))


# -- metrics -----------------------------------------------------------------
def _auc(y, s):
    from sklearn.metrics import roc_auc_score, average_precision_score
    y = np.asarray(y); s = np.asarray(s, float)
    if y.min() == y.max() or not np.isfinite(s).all():
        return float("nan"), float("nan")
    return float(roc_auc_score(y, s)), float(average_precision_score(y, s))


def _align(clean: Table, dirty: Table):
    common = [c for c in dirty.columns if c in clean.columns]
    n = min(clean.n, dirty.n)
    c = Table.from_pandas(clean.df[common].iloc[:n].reset_index(drop=True))
    d = Table.from_pandas(dirty.df[common].iloc[:n].reset_index(drop=True))
    return c, d


@dataclass
class BenchRow:
    dataset: str
    n: int
    d: int
    error_rate: float
    cell_auroc: float
    cell_auprc: float
    tuple_auroc: float
    tuple_auprc: float
    iforest_tuple_auroc: float


def _iforest_tuple(dirty: Table, yt) -> float:
    try:
        from sklearn.preprocessing import OneHotEncoder
        from pyod.models.iforest import IForest
        X = OneHotEncoder(handle_unknown="ignore", max_categories=50).fit_transform(dirty.df).toarray()
        s = IForest(random_state=0).fit(X).decision_scores_
        return _auc(yt, s)[0]
    except Exception:
        return float("nan")


def evaluate(clean_path: str, dirty_path: str, make_model, name: str = "") -> BenchRow:
    clean, dirty = _align(Table.from_any(clean_path), Table.from_any(dirty_path))
    mask = dirty.df.values != clean.df.values                 # (n, d) ground-truth errors
    model = make_model().fit(dirty)
    S = np.asarray(model.score(dirty), float)
    yc, sc = mask.ravel().astype(int), S.ravel()
    yt, st = mask.any(1).astype(int), S.max(1)
    ca, cp = _auc(yc, sc)
    ta, tp = _auc(yt, st)
    return BenchRow(name or os.path.basename(os.path.dirname(dirty_path)) or "data",
                    dirty.n, len(dirty.columns), float(yc.mean()),
                    ca, cp, ta, tp, _iforest_tuple(dirty, yt))


def run(root: str, make_model, datasets=None) -> list:
    found = discover_datasets(root)
    if datasets:
        found = {k: v for k, v in found.items() if k in datasets}
    rows = []
    for name, (cp, dp) in found.items():
        try:
            rows.append(evaluate(cp, dp, make_model, name=name))
        except Exception as exc:
            print(f"  [skip] {name}: {type(exc).__name__}: {exc}")
    return rows


def format_table(rows: list) -> str:
    head = (f"{'dataset':14} {'n':>6} {'d':>4} {'err%':>6} "
            f"{'cAUROC':>7} {'cAUPRC':>7} {'tAUROC':>7} {'tAUPRC':>7} {'IF tAUROC':>9}")
    lines = [head, "-" * len(head)]
    for r in rows:
        lines.append(f"{r.dataset:14} {r.n:>6} {r.d:>4} {100*r.error_rate:>5.1f}% "
                     f"{r.cell_auroc:>7.3f} {r.cell_auprc:>7.3f} "
                     f"{r.tuple_auroc:>7.3f} {r.tuple_auprc:>7.3f} {r.iforest_tuple_auroc:>9.3f}")
    return "\n".join(lines)


def rows_to_dicts(rows: list) -> list:
    return [asdict(r) for r in rows]
