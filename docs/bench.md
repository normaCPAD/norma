# Reproducible benchmark

`norma bench` runs CPAD on aligned clean/dirty table pairs and reports cell- and tuple-level
AUROC/AUPRC against the ground-truth error mask, next to an Isolation-Forest baseline.

## Layout

Either layout is discovered automatically under `--data`:

```
datasets/
  hospital/clean.csv   hospital/dirty.csv
  beers/clean.csv      beers/dirty.csv
# or
  flights_clean.csv    flights_dirty.csv
```

## Run

```bash
norma bench --data ./datasets --learner routed --json results.json
```

```
dataset             n    d   err%  cAUROC  cAUPRC  tAUROC  tAUPRC IF tAUROC
---------------------------------------------------------------------------
hospital         1000   20    4.9%   0.94 …  …       0.96 …  …          0.53
```

- **cAUROC / cAUPRC** — cell level; **tAUROC / tAUPRC** — tuple level.
- **IF tAUROC** — Isolation Forest baseline (tuple level).
- `--learner routed` is the complete CPAD (strong numbers); `discrete` is faster but weaker.

The metric code is in `norma.bench` (`discover_datasets`, `evaluate`, `run`) and is reusable
from Python for custom dataset suites.
