# NORMA

**Learn the denial constraints that govern a table, detect data-quality errors, and propose its normalized relational model — without writing a single rule or label.**

NORMA profiles a tabular file, discovers the functional dependencies (FD) and denial
constraints (DC) it satisfies, scores per-cell errors by their degree of violation (the
**CPAD** engine), and derives candidate keys, the current normal form, and a 3NF/BCNF
decomposition. Then it exports those constraints to the tools you already use.

## Why NORMA is different

Other data-quality tools make you *write* constraints by hand. NORMA **learns** them from
the data, and crucially separates a **relational error** (a value that breaks a constraint)
from a **rare-but-valid** value (statistically unusual but consistent) — the failure mode of
classical anomaly detectors.

## Install

```bash
pip install -e .                     # core (import stays: import norma)
pip install -e ".[gated]"            # + torch for the differentiable variant
pip install -e ".[studio]"           # + the PySide6 desktop app
```

## 60-second tour

```bash
norma analyze data.csv                       # constraints, keys, normal form, top errors
norma export  data.csv --to great_expectations --out ./expectations
norma freeze  data.csv -o norma.yml          # write a versioned constraint contract
norma check   data.csv -c norma.yml --fail-on-violations   # gate CI
norma bench   --data ./datasets              # AUROC/AUPRC vs an IForest baseline
```

```python
from norma.core.table import Table
Table.from_csv("data.csv").profile()          # renders inline in a notebook
```

See **[Export to your stack](export.md)**, **[Contracts & CI](contract.md)**,
**[Benchmark](bench.md)**, and the **[Python API](library.md)**.
