# Python API

## Profile a table

```python
from norma.core.table import Table

t = Table.from_csv("data.csv")     # or from_parquet / from_excel / from_json / from_any
report = t.profile()               # fits the routed CPAD; renders inline in a notebook
print(report.to_text())
```

In Jupyter/Colab, `t.profile()` renders an HTML report whose **top violations are colour-coded**:
<span style="color:#b00020">constraint violation</span> vs
<span style="color:#8a6d00">rare-but-valid</span> — NORMA's core distinction.

## Choose a learner

```python
from norma.models import DiscreteCPAD, GatedCPAD, OrderCPAD, LinearCPAD, EnsembleCPAD, RoutedCPAD

model = RoutedCPAD().fit(t)        # complete system (FD + order + linear + marginal routing)
for rule in model.rules():
    print(rule, "  ->  ", rule.to_dc() if hasattr(rule, "to_dc") else rule)

scores = model.score(t)            # (n, d) per-cell violation scores in [0, 1]
worst  = model.explain(t, k=10)    # the 10 most-violating cells, with the responsible rule
```

## Reach data-lake files

```python
Table.from_parquet("s3_dump.parquet")
Table.from_duckdb("lake/*.parquet")              # scan globs via DuckDB (optional dep)
Table.from_duckdb("db.duckdb", query="SELECT * FROM sales")
```

## Build artifacts

```python
from norma.modeling.report import build_model
from norma.export import export
from norma import contract as ct

report = build_model(t, model)
export(report, "pandera")                        # {filename: content}
ct.dump(ct.freeze(report))                        # the norma.yml contract as text
ct.check(t, ct.load("norma.yml"))                 # list[CheckResult]
```
