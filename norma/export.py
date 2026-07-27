"""Export discovered constraints to the data-quality ecosystem (headless: no Qt, no torch).

NORMA's differentiator is that it *discovers* the constraints other tools make you write by
hand. This module turns a fitted model's constraints into artifacts those tools consume, so
NORMA sits upstream of any existing pipeline:

    great_expectations  -> an Expectation Suite (JSON)
    pandera             -> a DataFrameSchema (Python module)
    dbt                 -> schema.yml + one singular test (SQL) per dependency
    sql_check           -> ANSI SQL: UNIQUE/CHECK constraints + violation-monitor views
    json_schema         -> a per-record JSON Schema (types/required; cross-row FDs noted)
    frictionless        -> a Frictionless Table Schema (types + primaryKey/uniqueKeys)
    metanome            -> FD/DC lines in Metanome result syntax
    shacl               -> SHACL shapes with sh:sparql (knowledge-graph stack)

Every exporter returns ``dict[filename -> content]`` so a single format can emit several files
(e.g. dbt). Message: *NORMA discovers the rules, your pipeline enforces them.*
"""
from __future__ import annotations
import json
import re

from norma.core.table import NUMERIC

FORMATS = ("great_expectations", "pandera", "dbt", "sql_check",
           "json_schema", "frictionless", "metanome", "shacl")


# -- helpers -----------------------------------------------------------------
def _classify(rules):
    """Split a mixed rule list into (FDs, linear constraints, order/other DCs)."""
    fds, linears, orders = [], [], []
    for c in rules:
        if hasattr(c, "rhs"):            # FunctionalDependency (simple or composite)
            fds.append(c)
        elif hasattr(c, "coefficients"):  # LinearConstraint
            linears.append(c)
        else:                             # DenialConstraint (order/comparison)
            orders.append(c)
    return fds, linears, orders


def _slug(*parts: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", "_".join(parts)).strip("_").lower()


def _q(ident: str) -> str:
    """Double-quote a SQL identifier, escaping embedded quotes."""
    return '"' + str(ident).replace('"', '""') + '"'


def _kinds_of(report, kinds):
    """Return a {column -> 'numeric'|'string'} map, defaulting to string."""
    cols = list(report.attributes)
    k = {c: "string" for c in cols}
    if kinds:
        for c in cols:
            if kinds.get(c) == NUMERIC:
                k[c] = "number"
    return k


# -- SQL ---------------------------------------------------------------------
def to_sql_check(report, kinds=None) -> dict:
    t = _q(report.table_name)
    out = ["-- norma: SQL constraints and violation monitors for "
           f"'{report.table_name}'.",
           "-- Single-tuple constraints become CHECK/UNIQUE; multi-tuple FDs/DCs, which "
           "standard\n-- SQL cannot phrase as a row CHECK, become monitor views (a "
           "non-empty view = a violation).", ""]
    for k in report.keys:
        cols = ", ".join(_q(c) for c in sorted(k))
        out.append(f"ALTER TABLE {t} ADD CONSTRAINT {_slug('uq', *sorted(k))} UNIQUE ({cols});")
    out.append("")
    fds, linears, orders = _classify(report.rules)
    for fd in fds:
        lhs = ", ".join(_q(a) for a in fd.lhs)
        v = _slug("v_viol_fd", *fd.lhs, fd.rhs)
        out.append(f"-- FD {fd}  (conf {fd.confidence:.3f})")
        out.append(f"CREATE VIEW {_q(v)} AS\n  SELECT {lhs}, COUNT(DISTINCT {_q(fd.rhs)}) "
                   f"AS n_distinct\n  FROM {t}\n  GROUP BY {lhs}\n  HAVING COUNT(DISTINCT "
                   f"{_q(fd.rhs)}) > 1;")
    for lin in linears:
        expr = " + ".join(f"({co:g} * {_q(c)})" for c, co in lin.coefficients)
        if lin.tolerance > 0:
            cond = f"ABS(({expr}) - {lin.offset:g}) <= {lin.tolerance:g}"
        else:
            cond = f"({expr}) = {lin.offset:g}"
        out.append(f"-- linear {lin}")
        out.append(f"ALTER TABLE {t} ADD CONSTRAINT {_slug('chk_lin', *sorted(lin.attributes))} "
                   f"CHECK ({cond});")
    for i, dc in enumerate(orders):
        out.append(f"-- order/comparison DC: {dc}")
        conj = " AND ".join(f"a.{_q(p.left)} {p.op} b.{_q(p.right)}" for p in dc.predicates)
        v = _slug("v_viol_dc", str(i))
        out.append(f"CREATE VIEW {_q(v)} AS\n  SELECT a.* FROM {t} a JOIN {t} b ON {conj};")
    return {"norma_constraints.sql": "\n".join(out) + "\n"}


# -- Great Expectations ------------------------------------------------------
def to_great_expectations(report, kinds=None) -> dict:
    exps = []
    for c in sorted({a for a in report.attributes}):
        exps.append({"expectation_type": "expect_column_to_exist",
                     "kwargs": {"column": c}})
    for k in report.keys:
        exps.append({"expectation_type": "expect_compound_columns_to_be_unique",
                     "kwargs": {"column_list": sorted(k)},
                     "meta": {"norma": "candidate key"}})
    fds, linears, orders = _classify(report.rules)
    for fd in fds:
        lhs = ", ".join(_q(a) for a in fd.lhs)
        query = (f"SELECT {lhs} FROM {{batch}} GROUP BY {lhs} "
                 f"HAVING COUNT(DISTINCT {_q(fd.rhs)}) > 1")
        exps.append({"expectation_type": "unexpected_rows_expectation",
                     "kwargs": {"unexpected_rows_query": query,
                                "description": f"FD {fd} (conf {fd.confidence:.3f})"},
                     "meta": {"norma": "functional dependency", "confidence": fd.confidence}})
    for lin in linears:
        cols = [c for c, _ in lin.coefficients]
        if all(abs(co - 1.0) < 1e-9 for _, co in lin.coefficients) and lin.tolerance == 0:
            exps.append({"expectation_type": "expect_multicolumn_sum_to_equal",
                         "kwargs": {"column_list": cols, "sum_total": lin.offset},
                         "meta": {"norma": "linear constraint"}})
        else:
            expr = " + ".join(f"{co:g}*{_q(c)}" for c, co in lin.coefficients)
            exps.append({"expectation_type": "unexpected_rows_expectation",
                         "kwargs": {"unexpected_rows_query":
                                    f"SELECT * FROM {{batch}} WHERE ABS(({expr}) - "
                                    f"{lin.offset:g}) > {lin.tolerance:g}",
                                    "description": f"linear {lin}"},
                         "meta": {"norma": "linear constraint"}})
    suite = {"expectation_suite_name": f"norma_{_slug(report.table_name)}",
             "meta": {"generated_by": "norma",
                      "note": "FDs/order DCs use UnexpectedRowsExpectation (GX >= 1.0, SQL "
                              "datasource). Keys map to expect_compound_columns_to_be_unique."},
             "expectations": exps}
    return {"norma_suite.json": json.dumps(suite, indent=2, ensure_ascii=False) + "\n"}


# -- pandera -----------------------------------------------------------------
def to_pandera(report, kinds=None) -> dict:
    k = _kinds_of(report, kinds)
    dtype = {"number": "float", "string": "str"}
    lines = ['"""Pandera schema generated by norma -- the constraints discovered in your data.',
             'Run: schema.validate(df, lazy=True) to collect every violation at once."""',
             "import pandas as pd", "import pandera.pandas as pa", "",
             "schema = pa.DataFrameSchema(", "    columns={"]
    for c in report.attributes:
        lines.append(f"        {c!r}: pa.Column({dtype[k[c]]}, nullable=True, "
                     f"coerce=True, required=True),")
    lines.append("    },")
    lines.append("    checks=[")
    fds, linears, orders = _classify(report.rules)
    for fd in fds:
        lhs = list(fd.lhs)
        lines.append(f"        pa.Check(lambda df: df.groupby({lhs!r})[{fd.rhs!r}]"
                     f".transform('nunique').le(1).all(),")
        lines.append(f"                 error={f'FD {fd} violated'!r}),")
    for lin in linears:
        expr = " + ".join(f"df[{c!r}].astype(float)*({co:g})" for c, co in lin.coefficients)
        lines.append(f"        pa.Check(lambda df: (({expr}) - ({lin.offset:g})).abs()"
                     f".le({max(lin.tolerance, 1e-9):g}).all(),")
        lines.append(f"                 error={f'linear {lin} violated'!r}),")
    lines += ["    ],", "    name=%r," % f"norma_{report.table_name}", ")"]
    return {"norma_schema.py": "\n".join(lines) + "\n"}


# -- dbt ---------------------------------------------------------------------
def to_dbt(report, kinds=None) -> dict:
    name = _slug(report.table_name) or "model"
    y = ["version: 2", "", "models:", f"  - name: {name}",
         "    description: \"Constraints discovered by norma.\"", "    columns:"]
    for c in report.attributes:
        y.append(f"      - name: {c}")
    if report.keys:
        y.append("    tests:")
        for k in report.keys:
            y.append("      - dbt_utils.unique_combination_of_columns:")
            y.append(f"          combination_of_columns: [{', '.join(sorted(k))}]")
    files = {"schema.yml": "\n".join(y) + "\n"}
    fds, linears, orders = _classify(report.rules)
    for fd in fds:                                        # one singular test per FD
        lhs = ", ".join(fd.lhs)
        fn = f"tests/{_slug('fd', *fd.lhs, fd.rhs)}.sql"
        files[fn] = (f"-- FD {fd} (conf {fd.confidence:.3f}); passes when no group breaks it\n"
                     f"select {lhs}\nfrom {{{{ ref('{name}') }}}}\n"
                     f"group by {lhs}\nhaving count(distinct {fd.rhs}) > 1\n")
    for lin in linears:
        expr = " + ".join(f"{co:g}*{c}" for c, co in lin.coefficients)
        fn = f"tests/{_slug('lin', *sorted(lin.attributes))}.sql"
        files[fn] = (f"-- linear {lin}\nselect *\nfrom {{{{ ref('{name}') }}}}\n"
                     f"where abs(({expr}) - {lin.offset:g}) > {lin.tolerance:g}\n")
    return files


# -- JSON Schema -------------------------------------------------------------
def to_json_schema(report, kinds=None) -> dict:
    k = _kinds_of(report, kinds)
    props = {c: {"type": ["number", "null"] if k[c] == "number" else ["string", "null"]}
             for c in report.attributes}
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema",
              "title": f"norma_{report.table_name}", "type": "object",
              "properties": props, "required": list(report.attributes),
              "$comment": "Per-record schema. Functional/denial dependencies are cross-row "
                          "and cannot be expressed in JSON Schema; use the SQL or Great "
                          "Expectations export for those."}
    return {"norma.schema.json": json.dumps(schema, indent=2, ensure_ascii=False) + "\n"}


# -- Frictionless Table Schema ----------------------------------------------
def to_frictionless(report, kinds=None) -> dict:
    k = _kinds_of(report, kinds)
    fields = [{"name": c, "type": "number" if k[c] == "number" else "string"}
              for c in report.attributes]
    schema = {"fields": fields}
    keys = [sorted(key) for key in report.keys]
    if keys:
        schema["primaryKey"] = keys[0]
        if len(keys) > 1:
            schema["uniqueKeys"] = keys[1:]
    schema["x-norma-dependencies"] = [str(c) for c in report.rules]   # FDs are not native
    return {"norma.tableschema.json": json.dumps(schema, indent=2, ensure_ascii=False) + "\n"}


# -- Metanome result syntax --------------------------------------------------
def to_metanome(report, kinds=None) -> dict:
    fds, linears, orders = _classify(report.rules)
    lines = []
    for fd in fds:
        lines.append(f"{','.join(fd.lhs)}->{fd.rhs}")
    for dc in orders:
        body = " ^ ".join(f"t1.{p.left}{p.op}t2.{p.right}" for p in dc.predicates)
        lines.append("¬{" + body + "}")
    return {"norma_fds.txt": "\n".join(lines) + "\n"}


# -- SHACL (knowledge-graph stack) ------------------------------------------
def to_shacl(report, kinds=None) -> dict:
    cls = _slug(report.table_name).title() or "Row"
    pre = ["@prefix sh: <http://www.w3.org/ns/shacl#> .",
           "@prefix ex: <http://norma.example/> .", "",
           f"# SHACL shapes for class ex:{cls}, one row = one node. FDs use SPARQL "
           "constraints\n# (experimental: assumes a row-per-node RDF model).", ""]
    fds, linears, orders = _classify(report.rules)
    body = []
    for i, fd in enumerate(fds):
        same = " ".join(f"?a ex:{a} ?v{j} . ?b ex:{a} ?v{j} ."
                        for j, a in enumerate(fd.lhs))
        sel = (f"SELECT $this WHERE {{ ?a a ex:{cls} . ?b a ex:{cls} . {same} "
               f"?a ex:{fd.rhs} ?x . ?b ex:{fd.rhs} ?y . FILTER(?x != ?y) }}")
        body.append(
            f"ex:Shape_{_slug(*fd.lhs, fd.rhs)} a sh:NodeShape ;\n"
            f"    sh:targetClass ex:{cls} ;\n"
            f"    sh:sparql [ a sh:SPARQLConstraint ;\n"
            f"        sh:message \"FD {fd} violated\" ;\n"
            f"        sh:select \"\"\"{sel}\"\"\" ] .")
    return {"norma.shapes.ttl": "\n".join(pre + body) + "\n"}


_EXPORTERS = {
    "great_expectations": to_great_expectations,
    "pandera": to_pandera,
    "dbt": to_dbt,
    "sql_check": to_sql_check,
    "json_schema": to_json_schema,
    "frictionless": to_frictionless,
    "metanome": to_metanome,
    "shacl": to_shacl,
}


def export(report, fmt: str, kinds=None) -> dict:
    """Export a DataModelReport to ``fmt``. Returns ``dict[filename -> file content]``."""
    if fmt not in _EXPORTERS:
        raise ValueError(f"unknown export format {fmt!r}; choose from {', '.join(FORMATS)}")
    return _EXPORTERS[fmt](report, kinds)
