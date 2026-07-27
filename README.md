<p align="center">
  <img src="docs/assets/logo.svg" alt="norma" height="104">
</p>

# norma

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Learn the denial constraints that govern a table, then propose its normalized
relational model. Install from source with `pip install -e .` (import stays `import norma`).

`norma` profiles a tabular file, discovers the functional dependencies (FD) and
composite denial constraints (DC) it satisfies, and from them derives candidate keys,
the current normal form, and a 3NF / BCNF decomposition. The same constraints give a
per-cell violation score, so it also flags the dirty cells.

The discovery engine is **[CPAD](https://github.com/normaCPAD/cpad)** (Constrained Predicates
for Anomaly Detection): a base model with interchangeable variants. The [cpad
repository](https://github.com/normaCPAD/cpad) holds the engine and the scripts that
reproduce every experiment in the paper.

```
CPADModel (abstract)          fit / score / rules / explain
├── DiscreteCPAD              mode/frequency FD miner (simple + composite FDs)
├── GatedCPAD                 differentiable gated model (torch)  [optional]
├── OrderCPAD                 order dependencies (<, >), context-conditioned
├── LinearCPAD                contrastive sparse linear constraints (no PCA)
├── EnsembleCPAD              rank-mean of sub-models
└── RoutedCPAD                complete system: priority routing across learners
```

`LinearCPAD` finds numeric constraints `a . x = 0` contrastively -- directions that are
tight on the data but broken by the value-swap corrupter -- with an L1 penalty for
sparse, readable constraints (e.g. `total = qty + price`). Unlike PCA minor components
it is robust to contamination and interpretable.

## Install

```bash
pip install -e .            # core
pip install -e ".[gated]"   # + torch for the differentiable variant
```

## Desktop app (norma studio)

A full PySide6/Qt desktop application for interactive normalization:

```bash
pip install -e ".[studio]"     # installs PySide6
python -m norma.studio          # or: norma-studio
```

Features: load a CSV or connect to an RDBMS (SQLite / PostgreSQL / MySQL / ODBC);
discover FD, composite, order and linear constraints; enable/disable them and add expert
constraints (the schema re-synthesizes live); interactive **FD graph** and **relational
schema** diagrams (exportable as vector PDF/SVG); bidirectional **visual <-> SQL**; an
**anomaly heatmap**; **constraint-guided repair** (propose and apply the consistent value
per violating cell, with before/after preview and undo); a shareable **data-quality
report** (HTML/PDF: conformance, normal form, keys, redundancy, constraints, anomalies);
and a **clean-database builder** (SQLite with the schema, anomaly-free data, constraint
views and triggers). Themeable (light/dark + accent), bilingual (FR/EN).

## CLI

```bash
norma analyze data.csv --learner routed --top 10 --json model.json
```

Output: discovered constraints (with confidence), candidate keys, current normal form,
proposed 3NF/BCNF tables, and the worst constraint-violating cells.

## Export to your data-quality stack

**NORMA discovers the rules; your pipeline enforces them.** Other tools make you *write*
constraints by hand — NORMA learns them from the data and exports them where you already work:

```bash
norma export data.csv --to great_expectations --out ./expectations
norma export data.csv --to pandera|dbt|sql_check|json_schema|frictionless|metanome|shacl
```

| `--to`               | Output                                                        |
|----------------------|---------------------------------------------------------------|
| `great_expectations` | Expectation Suite (keys → compound-unique; FDs → row checks)  |
| `pandera`            | `DataFrameSchema` with group-wise FD and linear checks        |
| `dbt`                | `schema.yml` + one singular test (SQL) per dependency         |
| `sql_check`          | ANSI `UNIQUE`/`CHECK` + violation-monitor views               |
| `json_schema`        | per-record JSON Schema (types/required)                       |
| `frictionless`       | Table Schema (types + `primaryKey`/`uniqueKeys`)              |
| `metanome`           | FD/DC lines in Metanome result syntax                         |
| `shacl`              | SHACL shapes with `sh:sparql` (knowledge-graph stack)         |

```python
from norma.export import export
files = export(report, "great_expectations")     # {filename: content}
```

## Library

```python
from norma import Table
from norma.models import RoutedCPAD
from norma.modeling import build_model

table = Table.from_csv("data.csv")
model = RoutedCPAD().fit(table)
report = build_model(table, model)
print(report.to_text())
for fd in model.rules():
    print(fd, fd.to_dc())          # FD and its denial-constraint form
```

## Layout

```
norma/core       Table, constraint vocabulary (Predicate, FD, DenialConstraint, LinearConstraint)
norma/models     CPADModel base + variants (discrete, gated, order, linear, ensemble, routed)
norma/detect     marginal surprise detector (ungoverned columns)
norma/rules      confidence measures + minimal-rule extraction
norma/modeling   attribute closure, candidate keys, 3NF/BCNF, report
norma/cli        command-line entry point
```
