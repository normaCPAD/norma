"""Command-line interface.

    norma analyze data.csv [--learner routed|discrete|gated] [--cap 300]
                           [--top 10] [--json model.json]

Given a tabular file, learns the functional dependencies / denial constraints that
govern it and prints a data model: constraints, candidate keys, current normal form,
a proposed 3NF/BCNF decomposition, and the worst constraint-violating cells.
"""
from __future__ import annotations
import argparse
import json
import os
import sys

from norma.core.table import Table
from norma.models import DiscreteCPAD, EnsembleCPAD, RoutedCPAD
from norma.modeling.report import build_model


def _make_learner(kind: str, tau: float = 0.90, max_lhs: int = 2):
    if kind == "discrete":
        return DiscreteCPAD(tau=tau, max_lhs=max_lhs)
    if kind == "gated":
        from norma.models.gated import GatedCPAD
        return GatedCPAD()                                # lambda/tau auto-selected (self-supervised)
    if kind == "ensemble":
        from norma.models.gated import GatedCPAD
        return EnsembleCPAD([DiscreteCPAD(tau=tau, max_lhs=max_lhs), GatedCPAD()])
    if kind == "routed":
        return RoutedCPAD()                               # discrete FD + order DC + null-space + marginal
    raise SystemExit(f"unknown learner {kind!r}")


def _learner_from_args(args):
    return _make_learner(args.learner, getattr(args, "tau", 0.90),
                         getattr(args, "max_lhs", 2))


def _add_learner_opts(sp):
    sp.add_argument("--learner", default="routed",
                    choices=["routed", "discrete", "gated", "ensemble"])
    sp.add_argument("--tau", type=float, default=0.90,
                    help="min FD confidence for the discrete learner (routed/gated auto-select)")
    sp.add_argument("--max-lhs", dest="max_lhs", type=int, default=2,
                    help="max LHS size for composite FDs (discrete/ensemble)")


def _add_maxrows(sp):
    sp.add_argument("--max-rows", dest="max_rows", type=int, default=None, metavar="N",
                    help="read at most N rows (bounds memory/time on very large files)")


def cmd_analyze(args) -> int:
    table = Table.from_any(args.path, id_cardinality=args.cap, nrows=getattr(args, "max_rows", None))
    model = _learner_from_args(args)
    model.fit(table)
    report = build_model(table, model, top_anomalies=args.top)
    print(report.to_text())
    if args.json:
        with open(args.json, "w") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\n[written] {args.json}", file=sys.stderr)
    return 0


def cmd_export(args) -> int:
    from norma.export import export, FORMATS
    if args.to not in FORMATS:
        raise SystemExit(f"unknown format {args.to!r}; choose from {', '.join(FORMATS)}")
    table = Table.from_any(args.path, id_cardinality=args.cap, nrows=getattr(args, "max_rows", None))
    model = _learner_from_args(args)
    model.fit(table)
    report = build_model(table, model, top_anomalies=0)
    files = export(report, args.to, kinds=table.kinds)
    os.makedirs(args.out, exist_ok=True)
    for fname, content in files.items():
        dest = os.path.join(args.out, fname)
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "w") as f:
            f.write(content)
        print(f"[written] {dest}", file=sys.stderr)
    print(f"{len(report.rules)} constraint(s) exported to {args.to} in {args.out}/")
    return 0


def cmd_freeze(args) -> int:
    from norma import contract as ct
    table = Table.from_any(args.path, id_cardinality=args.cap, nrows=getattr(args, "max_rows", None))
    model = _learner_from_args(args)
    model.fit(table)
    report = build_model(table, model, top_anomalies=0)
    c = ct.freeze(report)
    with open(args.out, "w") as f:
        f.write(ct.dump(c))
    print(f"[written] {args.out}  ({len(c['constraints'])} constraints)", file=sys.stderr)
    return 0


def cmd_check(args) -> int:
    from norma import contract as ct
    table = Table.from_any(args.path, id_cardinality=args.cap, nrows=getattr(args, "max_rows", None))
    results = ct.check(table, ct.load(args.contract))
    bad = [r for r in results if not r.ok]
    for r in results:
        mark = "ok " if r.ok else ("ERR" if r.violations < 0 else "FAIL")
        print(f"  [{mark}] {r.id:32} {r.detail}")
    n_viol = sum(r.violations for r in results if r.violations > 0)
    print(f"\n{len(results) - len(bad)}/{len(results)} constraints satisfied; "
          f"{n_viol} total violations.")
    if bad and args.fail_on_violations:
        return 1
    return 0


def cmd_bench(args) -> int:
    from norma import bench
    rows = bench.run(args.data, lambda: _make_learner(args.learner),
                     datasets=args.only.split(",") if args.only else None)
    if not rows:
        print(f"no clean/dirty pairs found under {args.data!r}", file=sys.stderr)
        return 1
    print(bench.format_table(rows))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(bench.rows_to_dicts(rows), f, indent=2)
        print(f"\n[written] {args.json}", file=sys.stderr)
    return 0


def cmd_score(args) -> int:
    from norma import scoring
    if args.max_rows is None:
        # no sample: discover FDs by streaming the ENTIRE file, then score every row
        model = scoring.learn_fds_streaming(args.path, id_cardinality=args.cap,
                                            tau=args.tau, lift=getattr(args, "lift", 0.10),
                                            chunksize=args.chunksize)
        learned = " (FDs learned on the FULL file, streaming, no sample)"
    else:
        table = Table.from_any(args.path, id_cardinality=args.cap, nrows=args.max_rows)
        model = _learner_from_args(args).fit(table)
        learned = f" (rules learned on a {table.n}-row sample)"
    res = scoring.score_file(model, args.path, out_path=args.out,
                             chunksize=args.chunksize, threshold=args.threshold)
    print(f"scored {res['rows']} rows{learned}; {res['flagged']} flagged "
          f"(score >= {res['threshold']}).")
    for v in res["top"][:args.top]:
        print(f"  row {v['row']:>9}  score {v['score']:.3f}  {v['rule']}")
    if args.out:
        print(f"[written] {args.out}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="norma", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="discover constraints and propose a data model")
    a.add_argument("path", help="path to a data file (csv/parquet/xlsx/json)")
    _add_learner_opts(a)
    a.add_argument("--cap", type=int, default=300,
                   help="max column cardinality to treat as modeling column (default 300)")
    a.add_argument("--top", type=int, default=10, help="number of violating cells to show")
    a.add_argument("--json", metavar="FILE", help="also write the model as JSON")
    _add_maxrows(a)
    a.set_defaults(func=cmd_analyze)

    e = sub.add_parser("export", help="export discovered constraints to a DQ-ecosystem format")
    e.add_argument("path", help="path to a CSV file")
    e.add_argument("--to", required=True, metavar="FORMAT",
                   help="great_expectations | pandera | dbt | sql_check | json_schema | "
                        "frictionless | metanome | shacl")
    e.add_argument("--out", default=".", metavar="DIR", help="output directory (default: .)")
    _add_learner_opts(e)
    e.add_argument("--cap", type=int, default=300)
    _add_maxrows(e)
    e.set_defaults(func=cmd_export)

    f = sub.add_parser("freeze", help="discover constraints and write a versioned contract")
    f.add_argument("path", help="path to a data file (csv/parquet/xlsx/json)")
    f.add_argument("--out", "-o", default="norma.yml", help="contract file (default norma.yml)")
    _add_learner_opts(f)
    f.add_argument("--cap", type=int, default=300)
    _add_maxrows(f)
    f.set_defaults(func=cmd_freeze)

    k = sub.add_parser("check", help="re-validate a table against a frozen contract")
    k.add_argument("path", help="path to a data file (csv/parquet/xlsx/json)")
    k.add_argument("--contract", "-c", required=True, help="path to norma.yml")
    k.add_argument("--fail-on-violations", action="store_true",
                   help="exit with status 1 if any constraint is violated (for CI)")
    k.add_argument("--cap", type=int, default=300)
    _add_maxrows(k)
    k.set_defaults(func=cmd_check)

    sc = sub.add_parser("score",
                        help="score EVERY row of a (possibly huge) file against learned rules")
    sc.add_argument("path", help="path to a data file (csv/parquet/xlsx/json)")
    sc.add_argument("--out", metavar="FILE",
                    help="write the data back with norma_score / norma_rule columns")
    sc.add_argument("--threshold", type=float, default=0.5,
                    help="flag rows whose violation score is >= this (default 0.5)")
    sc.add_argument("--chunksize", type=int, default=200000, help="rows per streaming chunk")
    sc.add_argument("--top", type=int, default=10, help="number of top violations to print")
    _add_learner_opts(sc)
    sc.add_argument("--cap", type=int, default=300)
    _add_maxrows(sc)        # --max-rows = sample used to LEARN the rules (full file is scored)
    sc.set_defaults(func=cmd_score)

    b = sub.add_parser("bench", help="AUROC/AUPRC on clean/dirty pairs vs an IForest baseline")
    b.add_argument("--data", required=True, help="root dir of clean/dirty dataset pairs")
    b.add_argument("--learner", default="routed",
                   choices=["routed", "discrete", "gated", "ensemble"])
    b.add_argument("--only", help="comma-separated dataset names to restrict to")
    b.add_argument("--json", metavar="FILE", help="also write results as JSON")
    b.set_defaults(func=cmd_bench)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
