"""Headless tests for norma.export: every ecosystem format emits well-formed artifacts."""
import json

from norma.core.constraint import (
    FunctionalDependency, LinearConstraint, DenialConstraint, Predicate)
from norma.modeling.report import DataModelReport
from norma.export import export, FORMATS


def _report() -> DataModelReport:
    fds = [
        FunctionalDependency(("country",), "continent", confidence=0.99),
        FunctionalDependency(("state", "salary"), "rate", confidence=0.97),
    ]
    lin = LinearConstraint(coefficients=(("qty", 1.0), ("price", 1.0), ("total", -1.0)),
                           offset=0.0, tolerance=0.0)
    order = DenialConstraint((Predicate("state", "=", "state"),
                              Predicate("salary", ">", "salary"),
                              Predicate("rate", "<", "rate")), confidence=0.99)
    return DataModelReport(
        table_name="sales",
        attributes=["country", "continent", "state", "salary", "rate", "qty", "price", "total"],
        rules=[*fds, lin, order],
        keys=[frozenset({"country", "state"})],
        normal_form="lower than 3NF",
        relations_3nf=[], relations_bcnf=[], anomalies=[])


def test_all_formats_emit_nonempty_files():
    rep = _report()
    for fmt in FORMATS:
        files = export(rep, fmt)
        assert files, fmt
        assert all(isinstance(v, str) and v.strip() for v in files.values()), fmt


def test_unknown_format_raises():
    try:
        export(_report(), "nope")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown format")


def test_great_expectations_valid_json_and_fd():
    suite = json.loads(export(_report(), "great_expectations")["norma_suite.json"])
    types = {e["expectation_type"] for e in suite["expectations"]}
    assert "expect_compound_columns_to_be_unique" in types        # candidate key
    assert "unexpected_rows_expectation" in types                 # FD as SQL row check
    assert any("continent" in e["kwargs"].get("unexpected_rows_query", "")
               for e in suite["expectations"])                    # FD on the rhs
    # mixed-sign linear (qty+price-total=0) is not a pure sum -> row check, not sum check
    assert any(e["expectation_type"] == "unexpected_rows_expectation"
               and "linear" in e["kwargs"].get("description", "")
               for e in suite["expectations"])


def test_json_schema_is_per_record():
    sch = json.loads(export(_report(), "json_schema")["norma.schema.json"])
    assert sch["type"] == "object" and "country" in sch["properties"]
    assert set(sch["required"]) >= {"country", "continent"}


def test_frictionless_primary_key():
    sch = json.loads(export(_report(), "frictionless")["norma.tableschema.json"])
    assert set(sch["primaryKey"]) == {"country", "state"}
    assert {f["name"] for f in sch["fields"]} >= {"country", "rate"}


def test_dbt_emits_schema_and_singular_tests():
    files = export(_report(), "dbt")
    assert "schema.yml" in files
    assert any(k.startswith("tests/") and k.endswith(".sql") for k in files)
    assert "count(distinct rate)" in "".join(files.values())


def test_pandera_code_is_valid_python():
    code = export(_report(), "pandera")["norma_schema.py"]
    compile(code, "norma_schema.py", "exec")
    assert "groupby" in code and "DataFrameSchema" in code


def test_metanome_fd_syntax():
    txt = export(_report(), "metanome")["norma_fds.txt"]
    assert "country->continent" in txt
    assert "state,salary->rate" in txt
    assert "¬{" in txt                                            # order DC


def test_sql_check_has_view_unique_and_check():
    sql = export(_report(), "sql_check")["norma_constraints.sql"]
    assert "CREATE VIEW" in sql and "UNIQUE" in sql and "CHECK" in sql
    assert "COUNT(DISTINCT" in sql


def test_shacl_turtle_well_formed():
    ttl = export(_report(), "shacl")["norma.shapes.ttl"]
    assert "sh:NodeShape" in ttl and "sh:sparql" in ttl and "sh:targetClass" in ttl
