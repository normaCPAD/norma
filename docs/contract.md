# Constraint contracts & CI

A **contract** turns a one-shot discovery into a maintained, versioned artifact that lives in
git and gates your pipeline.

## Freeze

```bash
norma freeze data.csv -o norma.yml
```

`norma.yml` is human-readable and reviewable:

```yaml
norma_contract: 1
table: hospital
constraints:
  - id: key_address1
    kind: key
    columns: [address1]
  - id: fd_country_continent
    kind: fd
    lhs: [country]
    rhs: continent
    confidence: 0.991
  - id: lin_price_qty_total
    kind: linear
    terms: {qty: 1.0, price: 1.0, total: -1.0}
    offset: 0.0
    tolerance: 0.0
```

Review it, drop constraints you don't trust, commit it.

## Check (in CI)

```bash
norma check data.csv -c norma.yml --fail-on-violations
```

```
  [ok ] key_address1            [address1] determines all columns (0 disagreeing cells)
  [FAIL] fd_country_continent   3 cells break ['country']->continent across 2 group(s)

1/2 constraints satisfied; 3 total violations.
```

Non-zero exit on violations, so it slots straight into a GitHub Action:

```yaml
- run: pip install -e .
- run: norma check data.csv -c norma.yml --fail-on-violations
```

!!! note "Key semantics"
    A discovered candidate key **determines** every other column (a super-FD). On a flat
    table it is unique only at the right grain, so `check` validates the robust *determinant*
    property rather than flat-table row uniqueness — no false CI failures on multiset tables.
