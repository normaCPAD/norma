"""Build a clean SQLite database from the discovered model.

Given the session (normalized schema + per-cell anomaly scores), this:
  * creates one table per BCNF relation (typed columns, primary key);
  * populates them with the DISTINCT projection of the ANOMALY-FREE rows
    (rows whose maximum violation score is below a threshold);
  * creates a reconstruction view `v_full` (lossless natural join);
  * creates VIEWS that surface the CPAD constraints that are NOT keys -- order
    dependencies, linear constraints and approximate FDs -- as violation monitors;
  * creates TRIGGERS that enforce the constraints whose attributes all live in a single
    relation (exact linear / order constraints), rejecting violating inserts.

`build_script` returns the DDL as text; `create_sqlite` also executes it and inserts the
clean data with Python's sqlite3.
"""
from __future__ import annotations
import sqlite3
import numpy as np

from norma.core.table import NUMERIC
from norma.core.constraint import FunctionalDependency, DenialConstraint, LinearConstraint


def q(name: str) -> str:
    return '"' + str(name).replace('"', '') + '"'


def _sqlite_type(session, col: str) -> str:
    return "REAL" if session.table is not None and session.table.kinds.get(col) == NUMERIC else "TEXT"


def clean_mask(session, threshold: float) -> np.ndarray:
    n = session.table.n
    if session.scores is None:
        return np.ones(n, dtype=bool)
    return session.scores.max(axis=1) <= threshold


def _relation_of(attrs, relations):
    s = set(attrs)
    for r in relations:
        if s <= set(r.attributes):
            return r
    return None


def _resolve_new(attr, R, relations):
    """SQL expression for the NEW row's value of `attr`. If `attr` is not in the trigger
    relation R, fetch it from the relation that holds it, joined on the shared key with R
    (so a cross-relation constraint can be checked from a single base-table trigger)."""
    if attr in R.attributes:
        return f"NEW.{q(attr)}"
    for r2 in relations:
        if r2 is not R and attr in r2.attributes:
            shared = set(R.attributes) & set(r2.attributes)
            if shared:
                cond = " AND ".join(f"{q(k)}=NEW.{q(k)}" for k in sorted(shared))
                return f"(SELECT {q(attr)} FROM {r2.name} WHERE {cond})"
    return None


def _constraint_views_and_triggers(session, relations, include_views, include_triggers):
    views, triggers = [], []
    for i, item in enumerate(r for r in session.rules if r.enabled):
        o = item.obj
        if isinstance(o, DenialConstraint):                      # order DC (cross-relation)
            preds = o.predicates
            cond = " AND ".join(f"a.{q(p.left)} {p.op} b.{q(p.right)}" for p in preds)
            if include_views:
                views.append(f"CREATE VIEW v_viol_order_{i} AS\n"
                             f"  SELECT DISTINCT a.* FROM v_full a JOIN v_full b ON {cond};")
            if include_triggers:
                y = preds[-1].left                               # the dependent attribute
                R = next((r for r in relations if y in r.attributes), None)
                resolved = [(_resolve_new(p.left, R, relations), p.op, p.right) for p in preds] if R else []
                if R is not None and all(expr for expr, _, _ in resolved):
                    cond_b = " AND ".join(f"{expr} {op} b.{q(right)}" for expr, op, right in resolved)
                    triggers.append(
                        f"-- order DC enforced across relations via v_full\n"
                        f"CREATE TRIGGER trg_order_{i} BEFORE INSERT ON {R.name}\n"
                        f"BEGIN SELECT RAISE(ABORT, 'order constraint violated')\n"
                        f"  WHERE EXISTS (SELECT 1 FROM v_full b WHERE {cond_b}); END;")
        elif isinstance(o, LinearConstraint):
            expr = " ".join(f"{'+' if c >= 0 else '-'} {abs(c):g}*{q(col)}" for col, c in o.coefficients).lstrip("+ ")
            tol = max(o.tolerance, 1e-6)
            if include_views:
                views.append(f"CREATE VIEW v_viol_linear_{i} AS\n"
                             f"  SELECT * FROM v_full WHERE ABS(({expr}) - {o.offset:g}) > {tol:g};")
            rel = _relation_of(o.attributes, relations)
            if include_triggers and rel is not None:
                nexpr = " ".join(f"{'+' if c >= 0 else '-'} {abs(c):g}*NEW.{q(col)}" for col, c in o.coefficients).lstrip("+ ")
                triggers.append(
                    f"CREATE TRIGGER trg_linear_{i} BEFORE INSERT ON {rel.name}\n"
                    f"BEGIN SELECT RAISE(ABORT, 'linear constraint violated')\n"
                    f"  WHERE ABS(({nexpr}) - {o.offset:g}) > {tol:g}; END;")
        elif isinstance(o, FunctionalDependency) and o.confidence < 0.999 and include_views:
            cond = " AND ".join(f"s.{q(a)}=t.{q(a)}" for a in o.lhs)
            views.append(
                f"-- approximate FD ({o.confidence:.2f}) {', '.join(o.lhs)} -> {o.rhs} : quality monitor\n"
                f"CREATE VIEW v_quality_{i} AS\n"
                f"  SELECT t.* FROM v_full t WHERE t.{q(o.rhs)} <> (\n"
                f"    SELECT {q(o.rhs)} FROM v_full s WHERE {cond}\n"
                f"    GROUP BY {q(o.rhs)} ORDER BY COUNT(*) DESC LIMIT 1);")
    return views, triggers


def _table_ddls(session, relations):
    ddls = []
    for r in relations:
        cols = sorted(r.attributes)
        lines = [f"  {q(c)} {_sqlite_type(session, c)}" for c in cols]
        pk = ", ".join(q(c) for c in sorted(r.key))
        ddls.append(f"CREATE TABLE {r.name} (\n" + ",\n".join(lines) + f",\n  PRIMARY KEY ({pk})\n);")
    return ddls


def _full_view(relations) -> str:
    if not relations:
        return ""
    chain = " NATURAL JOIN ".join(r.name for r in relations)
    return f"CREATE VIEW v_full AS SELECT * FROM {chain};"


def build_script(session, threshold=0.7, include_triggers=True, include_views=True) -> str:
    relations = session.schema.relations_bcnf
    if not relations:
        return "-- Run the analysis to obtain a schema."
    mask = clean_mask(session, threshold)
    n_clean = int(mask.sum())
    out = ["-- Clean database generated by norma",
           f"-- {n_clean}/{session.table.n} rows without anomalies (threshold {threshold:.2f})",
           "PRAGMA foreign_keys = ON;", ""]
    out += _table_ddls(session, relations)
    out.append("")
    out += [f"-- {n_clean} clean rows inserted (distinct projection per relation)"]
    out.append(_full_view(relations)); out.append("")
    views, triggers = _constraint_views_and_triggers(session, relations, include_views, include_triggers)
    if views:
        out.append("-- Views over non-structural CPAD constraints (non-keys):")
        out += views; out.append("")
    if triggers:
        out.append("-- Enforcement triggers (intra-relation constraints):")
        out += triggers
    return "\n".join(out)


def create_sqlite(session, path, threshold=0.7, include_triggers=True, include_views=True):
    relations = session.schema.relations_bcnf
    if not relations:
        raise RuntimeError("Aucun schema : lancez l'analyse.")
    mask = clean_mask(session, threshold)
    clean = session.table.df[mask]
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    for ddl in _table_ddls(session, relations):
        cur.execute(ddl)
    # clean data : distinct projection per relation
    for r in relations:
        cols = sorted(r.attributes)
        sub = clean[cols].drop_duplicates()
        ph = ", ".join("?" * len(cols))
        cur.executemany(f"INSERT OR IGNORE INTO {r.name} ({', '.join(q(c) for c in cols)}) VALUES ({ph})",
                        sub.itertuples(index=False, name=None))
    conn.commit()
    cur.execute(_full_view(relations))
    views, triggers = _constraint_views_and_triggers(session, relations, include_views, include_triggers)
    for stmt in (views if include_views else []) + (triggers if include_triggers else []):
        body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--"))
        try:
            cur.executescript(body)
        except sqlite3.Error:
            pass
    conn.commit()
    counts = {r.name: cur.execute(f"SELECT COUNT(*) FROM {r.name}").fetchone()[0] for r in relations}
    conn.close()
    return int(mask.sum()), session.table.n, counts
