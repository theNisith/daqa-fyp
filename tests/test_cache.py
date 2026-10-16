import re

import numpy as np
import pandas as pd
import pytest

from daqa.cache import (
    CACHE_DIR,
    DATASETS,
    N_STEPS,
    QUANTILE_LEVELS,
    cache_issues,
    forecast,
    forecast_issue,
    issue_contexts,
    load_cache,
    load_grid,
    load_pipeline,
    sha256_file,
)
from daqa.data import make_splits
from daqa.timing import DELAYS

TOL = 1e-6
N_AREAS = {"srilanka": 26, "ilinet": 10}


@pytest.fixture(scope="module")
def pipe():
    return load_pipeline()


@pytest.fixture(scope="module")
def grids():
    return {ds: load_grid(ds) for ds in DATASETS}


@pytest.fixture(scope="module")
def caches():
    return {ds: load_cache(ds) for ds in DATASETS}


# ---------- (c) shapes, sorting, metadata ----------

@pytest.mark.parametrize("ds", DATASETS)
def test_shapes_and_index(ds, caches, grids):
    c, g = caches[ds], grids[ds]
    issues = cache_issues(len(g))
    s = make_splits(len(g))
    assert issues.start == s.warmup.start and issues.stop - 1 == s.test[-1]
    shape = (len(issues), N_AREAS[ds], len(DELAYS), N_STEPS, len(QUANTILE_LEVELS))
    assert c.raw.shape == c.sorted.shape == shape == (208,) + shape[1:]
    assert c.raw.dtype == c.sorted.dtype == np.float32
    assert c.needed_sort.shape == c.context_nan.shape + (N_STEPS,) == shape[:4]
    assert c.issue_idx.tolist() == list(issues)
    assert (c.issue_dates == g.index[issues.start : issues.stop].to_numpy()).all()
    assert (c.grid_dates == g.index.to_numpy()).all()
    assert c.areas.tolist() == list(g.columns)
    assert c.delays.tolist() == list(DELAYS)
    assert c.steps.tolist() == list(range(1, 9))
    assert c.quantile_levels.tolist() == QUANTILE_LEVELS


@pytest.mark.parametrize("ds", DATASETS)
def test_sorted_is_non_decreasing_sort_of_raw(ds, caches):
    c = caches[ds]
    assert not np.isnan(c.raw).any()
    assert (np.diff(c.sorted, axis=-1) >= 0).all()
    assert np.array_equal(c.sorted, np.sort(c.raw, axis=-1))
    assert np.array_equal(c.needed_sort, (np.diff(c.raw, axis=-1) < 0).any(axis=-1))
    assert np.array_equal(c.raw[~c.needed_sort], c.sorted[~c.needed_sort])


def test_negatives_not_clipped(caches):
    assert (caches["srilanka"].raw < 0).any()  # raw quantiles stored unclipped


@pytest.mark.parametrize("ds", DATASETS)
def test_context_nan_counts(ds, caches, grids):
    c, g = caches[ds], grids[ds]
    expected = np.stack(
        [np.stack([np.isnan(issue_contexts(g, t, d)).sum(axis=1) for d in DELAYS], axis=1) for t in c.issue_idx]
    )
    assert np.array_equal(c.context_nan, expected)
    if ds == "srilanka":
        r = g.index.get_loc(pd.Timestamp("2026-02-09"))
        # Puttalam's one missing week sits in contexts with t - d >= r: 10 + 8 + 6.
        assert int((c.context_nan > 0).sum()) == 24
        assert set(c.areas[np.nonzero(c.context_nan)[1]]) == {"Puttalam"}
        assert r == 998
    else:
        assert c.context_nan.sum() == 0


def test_manifest_hashes_match_files():
    text = (CACHE_DIR / "MANIFEST.md").read_text(encoding="utf-8")
    for ds in DATASETS:
        c = load_cache(ds)
        name = c.path().name
        m = re.search(rf"\| `{re.escape(name)}` \| `([0-9a-f]{{64}})` \|", text)
        assert m, f"{name} missing from MANIFEST.md"
        assert m.group(1) == sha256_file(c.path())


def test_pipeline_frozen_and_native_levels(pipe):
    assert not pipe.model.training
    assert not any(p.requires_grad for p in pipe.model.parameters())
    assert list(pipe.quantiles) == QUANTILE_LEVELS


# ---------- (a) determinism ----------

def test_determinism_20_random_entries(pipe, caches, grids):
    rng = np.random.default_rng(20261016)
    for _ in range(20):
        ds = DATASETS[rng.integers(2)]
        c, g = caches[ds], grids[ds]
        t = int(rng.choice(c.issue_idx))
        d = int(rng.choice(DELAYS))
        area = str(rng.choice(c.areas))
        j = list(g.columns).index(area)
        again = forecast_issue(pipe, g, t, d)[j]
        np.testing.assert_allclose(again, c.entry(area, t, d), rtol=0, atol=TOL)


# ---------- (b) leakage: values after t - d set to 1e9 ----------

def leak_issues(n_weeks):
    """Three issues: first warm-up, first test, last test."""
    s = make_splits(n_weeks)
    return s.warmup.start, s.test.start, s.test[-1]


@pytest.mark.parametrize("ds", DATASETS)
def test_future_values_do_not_change_forecasts(ds, pipe, caches, grids):
    c, g = caches[ds], grids[ds]
    for t in leak_issues(len(g)):
        for d in DELAYS:
            perturbed = g.copy()
            perturbed.iloc[t - d + 1 :] = 1e9
            assert (perturbed.iloc[t - d + 1 :] == 1e9).all().all()
            got = forecast_issue(pipe, perturbed, t, d)
            i, k = int(np.flatnonzero(c.issue_idx == t)[0]), DELAYS.index(d)
            np.testing.assert_allclose(got, c.raw[i, :, k], rtol=0, atol=TOL)


def test_leakage_check_has_power(pipe, caches, grids):
    """A context that wrongly reaches one week past t - d sees the 1e9 values."""
    g = grids["srilanka"]
    t, d = make_splits(len(g)).test.start, 2
    perturbed = g.copy()
    perturbed.iloc[t - d + 1 :] = 1e9
    leaky = issue_contexts(perturbed, t + 1, d)  # ends at t - d + 1
    assert (leaky[:, -1] == 1e9).all()
    cached = caches["srilanka"].raw[int(np.flatnonzero(caches["srilanka"].issue_idx == t)[0]), :, 1]
    assert np.abs(forecast(pipe, leaky) - cached).max() > 1e3
