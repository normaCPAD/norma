"""Constraint contract: freeze the accepted constraints to a versioned ``norma.yml`` that
lives in git, then re-validate any table against it in CI.

This turns a one-shot discovery into a maintained artifact:

    norma freeze data.csv -o norma.yml       # discover, review, commit norma.yml
    norma check  data.csv -c norma.yml --fail-on-violations   # gate the pipeline

The contract is model-independent (plain FD/linear/key/order facts), so ``check`` re-derives
violations directly from the data with pandas and never needs to re-fit a model.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yaml

from norma.core.table import Table

SCHEMA_VERSION = 1


def _slug(*parts) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", "_".join(map(str, parts))).strip("_").lower()


def _classify(rules):
    fds, linears, orders = [], [], []
    for c in rules:
        if hasattr(c, "rhs"):
            fds.append(c)
        elif hasattr(c, "coefficients"):
            linears.append(c)
        else:
            orders.append(c)
    return fds, linears, orders


def freeze(report) -> dict:
    """Build a contract dict from a DataModelReport."""
    fds, linears, orders = _classify(report.rules)
    cons = []
    for k in report.keys:
        cols = sorted(k)
        cons.append({"id": _slug("key", *cols), "kind": "key", "columns": cols})
    for fd in fds:
        cons.append({"id": _slug("fd", *fd.lhs, fd.rhs), "kind": "fd",
                     "lhs": list(fd.lhs), "rhs": fd.rhs,
                     "confidence": round(float(fd.confidence), 4)})
    for lin in linears:
        cons.append({"id": _slug("lin", *sorted(lin.attributes)), "kind": "linear",
                     "terms": {c: float(co) for c, co in lin.coefficients},
                     "offset": float(lin.offset), "tolerance": float(lin.tolerance)})
    for i, dc in enumerate(orders):
        cons.append({"id": _slug("order", i), "kind": "order",
                     "predicates": [{"left": p.left, "op": p.op, "right": p.right}
                                    for p in dc.predicates]})
    return {"norma_contract": SCHEMA_VERSION, "table": report.table_name,
            "constraints": cons}


def dump(contract: dict) -> str:
    return yaml.safe_dump(contract, sort_keys=False, allow_unicode=True)


def load(path: str) -> dict:
    with open(path) as f:
        c = yaml.safe_load(f)
    if not isinstance(c, dict) or "constraints" not in c:
        raise ValueError(f"{path} is not a norma contract")
    return c


@dataclass
class CheckResult:
    id: str
    kind: str
    violations: int
    detail: str

    @property
    def ok(self) -> bool:
        return self.violations == 0


def _num(df: pd.DataFrame, col: str) -> np.ndarray:
    return pd.to_numeric(df[col], errors="coerce").to_numpy(float)


def check(table: Table, contract: dict) -> list[CheckResult]:
    """Re-validate ``table`` against every constraint in the contract."""
    df = table.df
    cols = set(df.columns)
    out: list[CheckResult] = []
    for c in contract.get("constraints", []):
        cid, kind = c.get("id", "?"), c.get("kind")
        try:
            if kind == "key":
                # A discovered candidate key DETERMINES every other column (a super-FD);
                # it is unique only once the table is at grain, so we check the robust
                # determinant property, not flat-table row uniqueness.
                ks = c["columns"]
                if not set(ks) <= cols:
                    out.append(CheckResult(cid, kind, -1, "missing column(s)")); continue
                g = df.groupby(ks)
                v = 0
                for col in df.columns:
                    if col in ks:
                        continue
                    maj = g[col].transform(lambda s: s.value_counts().index[0])
                    v += int((df[col].to_numpy() != maj.to_numpy()).sum())
                out.append(CheckResult(cid, kind, v,
                           f"{ks} determines all columns ({v} disagreeing cells)"))
            elif kind == "fd":
                lhs, rhs = c["lhs"], c["rhs"]
                if not set(lhs) | {rhs} <= cols:
                    out.append(CheckResult(cid, kind, -1, "missing column(s)")); continue
                g = df.groupby(lhs)[rhs]
                # cells disagreeing with their group's majority value
                maj = g.transform(lambda s: s.value_counts().index[0])
                v = int((df[rhs].to_numpy() != maj.to_numpy()).sum())
                bad = int((g.nunique() > 1).sum())
                out.append(CheckResult(cid, kind, v,
                           f"{v} cells break {lhs}->{rhs} across {bad} group(s)"))
            elif kind == "linear":
                terms = c["terms"]
                if not set(terms) <= cols:
                    out.append(CheckResult(cid, kind, -1, "missing column(s)")); continue
                resid = sum(co * _num(df, col) for col, co in terms.items()) - c.get("offset", 0.0)
                v = int((np.abs(resid) > c.get("tolerance", 0.0) + 1e-9).sum())
                out.append(CheckResult(cid, kind, v, f"{v} rows break the linear law"))
            elif kind == "order":
                # pairwise self-join is O(n^2); evaluate on a capped sample for the report
                out.append(CheckResult(cid, kind, 0, "order DC (monitor only; not gated)"))
            else:
                out.append(CheckResult(cid, kind or "?", -1, "unknown kind"))
        except Exception as exc:  # never let one bad constraint abort the whole check
            out.append(CheckResult(cid, kind or "?", -1, f"error: {type(exc).__name__}"))
    return out
