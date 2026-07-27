"""Score an *entire* dataset against rules learned on a sample, with bounded memory.

NORMA discovers its constraints on a bounded sample (fast), but error detection must cover
*every* row. This module applies the learned rules to the full file in two streaming passes:

  pass 1 -- accumulate exact full-data group statistics for each FD (bounded by the number
            of groups, which is small for governed columns);
  pass 2 -- score every row from those statistics and emit per-row violation scores.

So a file far larger than memory is scored chunk by chunk; the sample only decided *which*
rules to apply, while the conditional frequencies are exact over the whole dataset.
"""
from __future__ import annotations
import heapq
import os
from collections import Counter

import numpy as np
import pandas as pd

from norma.core.table import Table

_KSEP = "\x1f"     # multi-column key separator (control chars: absent from real data)
_PSEP = "\x1e"     # group-key / rhs-value separator


def _fd_rules(model):
    return [r for r in model.rules() if hasattr(r, "rhs")]


def _linear_rules(model):
    return [r for r in model.rules() if hasattr(r, "coefficients")]


def _key_series(df: pd.DataFrame, cols) -> pd.Series:
    cols = list(cols)
    if len(cols) == 1:
        return df[cols[0]].astype(str)
    return df[cols].astype(str).agg(_KSEP.join, axis=1)


def iter_chunks(path: str, chunksize: int):
    """Yield normalized chunks. CSV/TSV stream natively; other formats yield a single frame."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv", ".tsv"):
        for ch in pd.read_csv(path, dtype=str, chunksize=chunksize):
            yield Table._normalize(ch)
    else:
        yield Table.from_any(path).df


class _FDSet:
    """A minimal model exposing learned FDs to :func:`score_file` (``.rules()``)."""
    def __init__(self, fds):
        self.rules_ = list(fds)

    def rules(self):
        return list(self.rules_)


def learn_fds_streaming(path: str, id_cardinality: int = 300, tau: float = 0.90,
                        lift: float = 0.10, chunksize: int = 200_000,
                        max_pair_entries: int | None = None) -> _FDSet:
    """Discover single-source FDs over the ENTIRE file, no sampling, bounded memory.

    Two streaming passes: (1) per-column value counts -- identifies modeling columns and
    the base rate of each target; (2) ordered-pair co-occurrence counts, from which the
    exact confidence ``conf(A->B)=sum_a max_b count(a,b)/N`` is reconstructed. Pairs that
    accumulate too many distinct ``(a,b)`` combinations cannot be a near-FD and are dropped,
    so memory is bounded by cardinality, not by the number of rows.
    """
    from norma.core.constraint import FunctionalDependency
    if max_pair_entries is None:
        max_pair_entries = 20 * id_cardinality
    # ---- pass 1: column value counts (capped) -> modeling columns + base rates ----
    cols = None
    col_counts: dict[str, Counter | None] = {}
    n_rows = 0
    for ch in iter_chunks(path, chunksize):
        if cols is None:
            cols = list(ch.columns)
            col_counts = {c: Counter() for c in cols}
        n_rows += len(ch)
        for c in cols:
            cc = col_counts[c]
            if cc is None:
                continue
            cc.update(ch[c].value_counts().to_dict())
            if len(cc) > id_cardinality:          # identifier / free text -> not a modeling column
                col_counts[c] = None
    if not n_rows or cols is None:
        return _FDSet([])
    modeling = [c for c in cols if col_counts[c] is not None and 1 < len(col_counts[c])]
    base = {c: max(col_counts[c].values()) / n_rows for c in modeling}
    # ---- pass 2: ordered-pair co-occurrence counts ----
    pair: dict[tuple, Counter | None] = {(a, b): Counter()
                                         for a in modeling for b in modeling if a != b}
    for ch in iter_chunks(path, chunksize):
        for (a, b), cnt in pair.items():
            if cnt is None:
                continue
            k = ch[a].astype(str).str.cat(ch[b].astype(str), sep=_PSEP)
            cnt.update(k.value_counts().to_dict())
            if len(cnt) > max_pair_entries:        # too many (a,b) combos -> cannot be an FD
                pair[(a, b)] = None
    # ---- reconstruct conf(A->B) and emit one FD per target ----
    fds = []
    for b in modeling:
        best_a, best_c = None, -1.0
        for a in modeling:
            if a == b or pair[(a, b)] is None:
                continue
            grp: dict[str, int] = {}               # a-value -> max_b count(a,b)
            for key, c in pair[(a, b)].items():
                av = key.split(_PSEP, 1)[0]
                if c > grp.get(av, 0):
                    grp[av] = c
            conf = sum(grp.values()) / n_rows
            if conf > best_c:
                best_a, best_c = a, conf
        if best_a is not None and best_c >= tau and best_c - base[b] >= lift:
            fds.append(FunctionalDependency((best_a,), b, confidence=round(best_c, 4)))
    return _FDSet(fds)


def score_file(model, path: str, out_path: str | None = None,
               chunksize: int = 200_000, threshold: float = 0.5, top_k: int = 50) -> dict:
    """Stream ``path``, scoring every row against ``model``'s learned FD and linear rules.

    Returns a summary ``{rows, flagged, threshold, top}``. If ``out_path`` is given, writes
    the data back with two extra columns: ``norma_score`` and ``norma_rule``.
    """
    fds = _fd_rules(model)
    linears = _linear_rules(model)

    # ---- pass 1: exact full-data group statistics for each FD -------------------------
    size = [Counter() for _ in fds]     # lhs-key -> #rows
    pair = [Counter() for _ in fds]     # (lhs-key, rhs-value) -> #rows
    for ch in iter_chunks(path, chunksize):
        for i, fd in enumerate(fds):
            k = _key_series(ch, fd.lhs)
            size[i].update(k.value_counts().to_dict())
            pk = k.str.cat(ch[fd.rhs].astype(str), sep=_PSEP)
            pair[i].update(pk.value_counts().to_dict())

    # ---- pass 2: score every row ------------------------------------------------------
    n_rows = n_flagged = 0
    top: list[tuple] = []               # min-heap of (score, global_row, rule)
    out_f = None
    header_written = False
    if out_path:
        out_f = open(out_path, "w", encoding="utf-8")
    try:
        for ch in iter_chunks(path, chunksize):
            m = len(ch)
            s = np.zeros(m)
            rule = np.empty(m, dtype=object); rule[:] = ""
            for i, fd in enumerate(fds):
                k = _key_series(ch, fd.lhs)
                sz = k.map(size[i]).to_numpy(dtype=float)
                pk = k.str.cat(ch[fd.rhs].astype(str), sep=_PSEP)
                own = pk.map(pair[i]).to_numpy(dtype=float)
                with np.errstate(invalid="ignore", divide="ignore"):
                    viol = np.where(sz > 0, 1.0 - own / sz, 0.0)
                upd = viol > s
                s = np.where(upd, viol, s)
                rule = np.where(upd, str(fd), rule)
            for lin in linears:
                resid = np.zeros(m)
                for c, co in lin.coefficients:
                    x = pd.to_numeric(ch[c], errors="coerce").to_numpy(dtype=float)
                    resid = resid + co * np.nan_to_num(x)
                viol = (np.abs(resid - lin.offset) > lin.tolerance).astype(float)
                upd = viol > s
                s = np.where(upd, viol, s)
                rule = np.where(upd, str(lin), rule)

            base = n_rows
            n_rows += m
            n_flagged += int((s >= threshold).sum())
            for idx in np.argsort(s)[::-1][:top_k]:
                if s[idx] <= 0:
                    break
                heapq.heappush(top, (float(s[idx]), base + int(idx), str(rule[idx])))
                if len(top) > top_k:
                    heapq.heappop(top)
            if out_f is not None:
                ch = ch.copy()
                ch["norma_score"] = np.round(s, 4)
                ch["norma_rule"] = rule
                ch.to_csv(out_f, index=False, header=not header_written)
                header_written = True
    finally:
        if out_f is not None:
            out_f.close()

    top_sorted = sorted(top, reverse=True)
    return {"rows": n_rows, "flagged": n_flagged, "threshold": threshold,
            "top": [{"row": r, "score": round(sc, 4), "rule": rl} for sc, r, rl in top_sorted]}
