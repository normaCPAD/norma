# Export to your data-quality stack

> **NORMA discovers the rules; your pipeline enforces them.**

NORMA learns constraints from data and emits them in the format your existing stack consumes,
so it sits *upstream* of any pipeline.

```bash
norma export data.csv --to great_expectations --out ./expectations
norma export data.csv --to pandera     --out ./schemas
norma export data.csv --to dbt         --out ./models
norma export data.csv --to sql_check   --out ./sql
```

| `--to`               | Output                                                              |
|----------------------|--------------------------------------------------------------------|
| `great_expectations` | Expectation Suite (keys → compound-unique; FDs → `UnexpectedRows`) |
| `pandera`            | `DataFrameSchema` with group-wise FD and linear checks             |
| `dbt`                | `schema.yml` + one singular test (SQL) per dependency              |
| `sql_check`          | ANSI `UNIQUE`/`CHECK` + violation-monitor views                    |
| `json_schema`        | per-record JSON Schema (types/required)                            |
| `frictionless`       | Table Schema (types + `primaryKey`/`uniqueKeys`)                   |
| `metanome`           | FD/DC lines in Metanome result syntax                             |
| `shacl`              | SHACL shapes with `sh:sparql` (knowledge-graph stack)             |

## What maps to what

A functional dependency `X → A` is a *cross-row* constraint, so each target expresses it with
its closest native idiom:

- **Great Expectations / dbt / SQL** — a violation query: `GROUP BY X HAVING COUNT(DISTINCT A) > 1`.
- **pandera** — a dataframe check: `df.groupby(X)[A].transform('nunique') <= 1`.
- **JSON Schema** — *not expressible* (per-record only); only column types/required are emitted.
- **Frictionless** — candidate keys become `primaryKey` / `uniqueKeys`.

Linear constraints (`a·x = c`) and order DCs map to `CHECK` / monitor views and, where
possible, native expectations (e.g. `expect_multicolumn_sum_to_equal`).

## From Python

```python
from norma.core.table import Table
from norma.models import RoutedCPAD
from norma.modeling.report import build_model
from norma.export import export

t = Table.from_csv("data.csv")
report = build_model(t, RoutedCPAD().fit(t))
files = export(report, "great_expectations")     # {filename: content}
```
