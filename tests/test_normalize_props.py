"""Property tests for the normalization core -- the correctness argument of the product.

No Hypothesis dependency: we generate seeded random FD schemas with FD-consistent data and
check the textbook guarantees on the implementation's own output:

  * candidate keys determine every attribute (closure correctness);
  * the minimal cover implies every original FD (equivalence);
  * the BCNF decomposition is a lossless join (reconstructs the data exactly);
  * 3NF synthesis is dependency-preserving (every FD lives inside some relation).
"""
from functools import reduce

import numpy as np
import pandas as pd
import pytest

from norma.modeling.closure import attribute_closure, minimal_cover, candidate_keys
from norma.modeling.normalize import synthesize_3nf, decompose_bcnf

SEEDS = list(range(12))


def _schema(seed: int):
    """A random star schema: two independent sources, each determining a few columns."""
    rng = np.random.default_rng(seed)
    k = int(rng.integers(4, 7))
    attrs = [f"A{i}" for i in range(k)]
    sources, derived = attrs[:2], attrs[2:]
    n = 40
    df = pd.DataFrame({s: rng.integers(0, 4, n).astype(str) for s in sources})
    pairs = []
    for j, a in enumerate(derived):
        src = sources[j % len(sources)]
        df[a] = df[src].map(lambda v, a=a: f"{a}_{v}")     # FD  src -> a, by construction
        pairs.append((frozenset([src]), a))
    return df[attrs], frozenset(attrs), pairs


def _natural_join(frames):
    """Iteratively natural-join frames on shared columns (greedy, requires connectivity)."""
    frames = list(frames)
    acc = frames.pop(0)
    while frames:
        for i, f in enumerate(frames):
            common = list(set(acc.columns) & set(f.columns))
            if common:
                acc = acc.merge(f, on=common, how="inner")
                frames.pop(i)
                break
        else:
            raise AssertionError("decomposition is disconnected (would be a lossy cross join)")
    return acc


def _rows(df, cols):
    return {tuple(r) for r in df[sorted(cols)].itertuples(index=False, name=None)}


@pytest.mark.parametrize("seed", SEEDS)
def test_candidate_keys_determine_everything(seed):
    df, attrs, pairs = _schema(seed)
    cover = minimal_cover(pairs)
    keys = candidate_keys(attrs, cover)
    assert keys, "at least one candidate key expected"
    for k in keys:
        assert attribute_closure(k, cover) >= set(attrs), f"{k} is not a superkey"


@pytest.mark.parametrize("seed", SEEDS)
def test_minimal_cover_is_equivalent(seed):
    _, attrs, pairs = _schema(seed)
    cover = minimal_cover(pairs)
    for lhs, rhs in pairs:                                  # every original FD is still implied
        assert rhs in attribute_closure(lhs, cover)


@pytest.mark.parametrize("seed", SEEDS)
def test_bcnf_decomposition_is_lossless(seed):
    df, attrs, pairs = _schema(seed)
    rels = decompose_bcnf(attrs, pairs)
    assert set().union(*[r.attributes for r in rels]) == set(attrs)   # covers all attributes
    projections = [df[sorted(r.attributes)].drop_duplicates() for r in rels]
    recon = _natural_join(projections)
    assert _rows(recon, attrs) == _rows(df, attrs)         # exact reconstruction, no spurious tuples


@pytest.mark.parametrize("seed", SEEDS)
def test_3nf_is_dependency_preserving(seed):
    _, attrs, pairs = _schema(seed)
    cover = minimal_cover(pairs)
    rels = synthesize_3nf(attrs, cover)
    for lhs, rhs in cover:
        assert any(set(lhs) | {rhs} <= set(r.attributes) for r in rels), \
            f"FD {sorted(lhs)} -> {rhs} not preserved in any relation"
