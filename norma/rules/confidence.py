"""Vectorized confidence/support measures for candidate functional dependencies.

confidence(X -> A) = fraction of tuples whose A-value equals the most frequent A-value
within their X-group (i.e. the share kept if every group adopted its majority value).
A deterministic FD has confidence 1; the measure is robust to a minority of errors
(majority vote per group).
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def single_source_confidences(df: pd.DataFrame, columns) -> dict:
    """All single-source confidences ``conf(A -> B)`` for ``A, B in columns`` at once.

    Each column is integer-encoded once with :func:`pandas.factorize`; every ordered pair is
    then scored with pure NumPy counting (``np.unique`` + ``np.maximum.at``) instead of a
    ``pandas.groupby`` per pair. The result equals ``fd_confidence(df, [A], B)`` but is one to
    two orders of magnitude faster on wide or large tables, which is what lets the discrete
    miner scale to the million-row / thousand-column regime. Returns ``conf[A][B]``.
    """
    cols = list(columns)
    n = len(df)
    if n == 0:
        return {a: {b: 0.0 for b in cols if b != a} for a in cols}
    DENSE_CAP = 4_000_000                                  # bincount when card_a*card_b fits this
    codes, cards, has_na = {}, {}, {}
    for c in cols:
        code, uniq = pd.factorize(df[c], sort=False)      # NaN -> -1
        codes[c] = code.astype(np.int64)
        cards[c] = len(uniq)
        has_na[c] = bool((code < 0).any())
    conf = {a: {} for a in cols}
    for a in cols:
        ca, card_a = codes[a], cards[a]
        for b in cols:
            if a == b:
                continue
            cb, card_b = codes[b], cards[b]
            if card_a == 0 or card_b == 0:
                conf[a][b] = 0.0
                continue
            if has_na[a] or has_na[b]:                     # drop NaN rows from the count (as groupby does)
                m = (ca >= 0) & (cb >= 0)
                if not m.any():
                    conf[a][b] = 0.0
                    continue
                xa, xb = ca[m], cb[m]
            else:
                xa, xb = ca, cb
            key = xa * card_b + xb                         # unique id of each (A, B) pair
            if card_a * card_b <= DENSE_CAP:               # dense fast path: pure bincount, no sort
                counts = np.bincount(key, minlength=card_a * card_b).reshape(card_a, card_b)
                conf[a][b] = float(counts.max(axis=1).sum() / n)
            else:                                          # sparse fallback: memory-safe for high cardinality
                uk, uc = np.unique(key, return_counts=True)
                maxper = np.zeros(card_a)
                np.maximum.at(maxper, uk // card_b, uc)    # majority B-count within each A-group
                conf[a][b] = float(maxper.sum() / n)
    return conf


def fd_confidence(df: pd.DataFrame, lhs, rhs: str) -> float:
    lhs = list(lhs)
    if not lhs:
        return float((df[rhs].value_counts() / len(df)).max())
    grp = df.groupby(lhs + [rhs]).size()
    return float(grp.groupby(level=list(range(len(lhs)))).max().sum() / len(df))


def base_rate(df: pd.DataFrame, col: str) -> float:
    """Confidence of the empty LHS: how predictable the column is on its own."""
    return float((df[col].value_counts() / len(df)).max())


def avg_group_size(df: pd.DataFrame, cols) -> float:
    """Mean tuples per LHS group; guards against confidence inflated by singleton groups."""
    cols = list(cols)
    if not cols:
        return float(len(df))
    return float(len(df) / max(1, df.groupby(cols).ngroups))
