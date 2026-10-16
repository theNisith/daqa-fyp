"""Future-label perturbation test (proposal 5.6) for Frozen and MultiQT on both datasets.

For each pre-declared issue t (tests/perturbation_weeks.json) and each d, every
value with index > t - d is altered (value * 10 + 1000) and the pipeline is
rerun up to t for the cells (1, d) and (4, d) — the cells for which exactly
those values are illegal. Together the three d cover all six cells. Chronos is
recomputed in both the reference and the perturbed run (never read from the
cache). No score is computed.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from daqa.cache import DATASETS, issue_contexts, load_grid, load_pipeline
from daqa.data import area_scale, make_splits
from daqa.methods.multiqt import ADAPTIVE, IDENTITY
from daqa.perturbation import compare, perturb_after, perturb_cell, take_snapshot
from daqa.timing import DELAYS

WEEKS = json.loads((Path(__file__).parent / "perturbation_weeks.json").read_text(encoding="utf-8"))
SEGMENTS = ("warmup", "validation", "test")
# Fixed MultiQT rates here are test inputs only; the protocol's two rates are still an open decision.
LRS = (IDENTITY, 0.05, 0.5, ADAPTIVE)


@pytest.fixture(scope="module")
def pipe():
    return load_pipeline()


@pytest.fixture(scope="module")
def grids():
    return {ds: load_grid(ds) for ds in DATASETS}


def issue_row(grid, ds, seg):
    return int(grid.index.get_loc(pd.Timestamp(WEEKS[ds][seg])))


@pytest.fixture(scope="module")
def references(pipe, grids):
    """Unperturbed reruns up to the latest perturbation week, per (dataset, d); computed lazily."""
    store = {}

    def get(ds, d):
        if (ds, d) not in store:
            g = grids[ds]
            t_max = max(issue_row(g, ds, seg) for seg in SEGMENTS)
            store[(ds, d)] = take_snapshot(ds, g, t_max, d, pipe, LRS)
        return store[(ds, d)]

    return get


@pytest.mark.parametrize("ds", DATASETS)
def test_weeks_are_predeclared_by_date(ds, grids):
    g = grids[ds]
    segs = make_splits(len(g)).segments()
    for seg in SEGMENTS:
        t = issue_row(g, ds, seg)  # raises if the date is not a grid week
        assert t in segs[seg]
        jan1 = pd.Timestamp(year=g.index[t].year, month=1, day=1)
        assert g.index[t] >= jan1 > g.index[t - 1]  # first issue on or after 1 January


@pytest.mark.parametrize("d", DELAYS)
@pytest.mark.parametrize("seg", SEGMENTS)
@pytest.mark.parametrize("ds", DATASETS)
def test_future_perturbation_changes_nothing(ds, seg, d, pipe, grids, references):
    g = grids[ds]
    t = issue_row(g, ds, seg)
    pert = perturb_after(g, t - d)
    # The perturbation really alters every observed illegal value and nothing legal.
    after, before = g.iloc[t - d + 1 :], pert.iloc[t - d + 1 :]
    assert (before[after.notna()] != after[after.notna()]).all().all()
    pd.testing.assert_frame_equal(pert.iloc[: t - d + 1], g.iloc[: t - d + 1])
    # Positive control: contexts with a shorter delay d' < d legally see the altered rows.
    for d_short in [x for x in DELAYS if x < d]:
        assert not np.array_equal(issue_contexts(pert, t, d_short), issue_contexts(g, t, d_short), equal_nan=True)

    snap = take_snapshot(ds, pert, t, d, pipe, LRS)
    assert snap.issues[-1] == t and len(snap.queue_issues[1]) > 0
    assert compare(references(ds, d), snap) == []


@pytest.mark.parametrize("ds", DATASETS)
def test_negative_control_legal_change_is_detected(ds, pipe, grids, references):
    g = grids[ds]
    t, d = issue_row(g, ds, "test"), 2
    row = t - d  # legally available at issue t
    area = str(g.columns[0])
    assert np.isfinite(g.iloc[row][area])
    snap = take_snapshot(ds, perturb_cell(g, row, area), t, d, pipe, LRS)
    diffs = compare(references(ds, d), snap)
    print(f"\n{ds} negative control (row {row}, {area}, t={t}, d={d}) detected: {diffs}")
    assert "contexts" in diffs
    assert any(x.startswith("chronos") for x in diffs)
    assert any(x.startswith("frozen issued") for x in diffs)
    assert "queue labels h=1" in diffs and "queue labels h=4" in diffs  # row t-d is the label of s = t-d-h
    assert any(x.startswith("multiqt") for x in diffs)


@pytest.mark.xfail(strict=True, reason="OPEN: s(i) uses scaling rows up to warm-up start - 1, which are not yet "
                                       "available at the first d-1 warm-up issues when d > 0 (see CLAUDE.md)")
@pytest.mark.parametrize("ds", DATASETS)
def test_scale_legal_at_first_warmup_issue(ds, grids):
    g = grids[ds]
    s = make_splits(len(g))
    t, d = s.warmup.start, 4
    pd.testing.assert_series_equal(area_scale(perturb_after(g, t - d), s.scaling), area_scale(g, s.scaling))
