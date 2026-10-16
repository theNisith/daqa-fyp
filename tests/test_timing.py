import numpy as np
import pandas as pd
import pytest

from daqa.timing import (
    CELLS,
    CONTEXT_LENGTH,
    MAX_STEP,
    available_context,
    first_usable_issue,
    last_available,
    matured_at,
    matured_up_to,
    multiqt_delay,
    step_index,
)

N = 300


def _series(n=N):
    """Value at grid position i is i, so any leaked future value is visible."""
    return pd.Series(np.arange(n, dtype=float), index=pd.date_range("2010-01-03", periods=n, freq="7D"))


# ---------- cells, step and delays ----------

def test_six_cells():
    assert CELLS == ((1, 0), (1, 2), (1, 4), (4, 0), (4, 2), (4, 4))
    assert CONTEXT_LENGTH == 104
    assert MAX_STEP == 8


@pytest.mark.parametrize(
    "h, d, step, D",
    [(1, 0, 1, 0), (1, 2, 3, 2), (1, 4, 5, 4), (4, 0, 4, 3), (4, 2, 6, 5), (4, 4, 8, 7)],
)
def test_step_and_multiqt_delay_hand_computed(h, d, step, D):
    assert step_index(h, d) == step
    assert multiqt_delay(h, d) == D
    # MultiQT reveals s's outcome after the forecast at s + D and first uses it at s + D + 1.
    for s in (0, 7, 100):
        assert s + D + 1 == first_usable_issue(s, h, d) == s + h + d


@pytest.mark.parametrize("h, d", CELLS)
def test_context_end_plus_step_is_target(h, d):
    for t in (8, 50, 200):
        ctx = available_context(_series(), t, d)
        assert ctx.iloc[-1] + step_index(h, d) == t + h


@pytest.mark.parametrize("h, d", [(2, 0), (1, 1), (4, 3), (0, 0), (1, 8)])
def test_non_study_cells_rejected(h, d):
    for fn in (step_index, multiqt_delay):
        with pytest.raises(ValueError):
            fn(h, d)
    with pytest.raises(ValueError):
        matured_at(10, h, d, range(10))


# ---------- proposal example and edges ----------

def test_proposal_example_issue_11_h1_d2():
    s = _series()
    ctx = available_context(s, 11, 2)
    assert last_available(11, 2) == 9
    assert ctx.tolist() == [float(i) for i in range(10)]  # data through index 9
    assert step_index(1, 2) == 3  # 3-step request reaches target 12
    assert first_usable_issue(11, 1, 2) == 14
    issues = range(30)
    assert matured_at(14, 1, 2, issues) == [11]
    assert 11 not in matured_up_to(13, 1, 2, issues)
    assert 11 in matured_up_to(14, 1, 2, issues)


def test_edge_h_plus_d_equals_1():
    s = _series()
    ctx = available_context(s, 20, 0)
    assert ctx.iloc[-1] == 20  # d = 0: issue week itself is available
    assert step_index(1, 0) == 1
    assert matured_at(21, 1, 0, range(30)) == [20]
    assert matured_up_to(20, 1, 0, range(30)) == list(range(20))


def test_edge_h_plus_d_equals_8():
    s = _series()
    ctx = available_context(s, 20, 4)
    assert ctx.iloc[-1] == 16
    assert step_index(4, 4) == 8  # 16 + 8 = target 24 = 20 + 4
    assert matured_at(28, 4, 4, range(30)) == [20]
    assert matured_up_to(27, 4, 4, range(30)) == list(range(20))
    assert matured_at(7, 4, 4, range(30)) == []  # nothing matures before issue 8


# ---------- available_context ----------

def test_context_full_length_and_exact_values():
    s = _series()
    ctx = available_context(s, 150, 2)
    assert len(ctx) == 104
    assert ctx.tolist() == [float(i) for i in range(148 - 103, 149)]
    assert ctx.index[-1] == s.index[148]


@pytest.mark.parametrize("t, d, expected_len", [(0, 0, 1), (5, 2, 4), (103, 0, 104), (50, 4, 47)])
def test_context_short_history_not_padded(t, d, expected_len):
    ctx = available_context(_series(), t, d)
    assert len(ctx) == expected_len
    assert ctx.tolist() == [float(i) for i in range(expected_len)]


@pytest.mark.parametrize("t, d", [(0, 2), (1, 2), (3, 4)])
def test_context_empty_when_no_legal_data(t, d):
    assert len(available_context(_series(), t, d)) == 0


def test_context_keeps_nan():
    s = _series()
    s.iloc[[40, 97]] = np.nan
    s.iloc[99] = np.nan  # after t - d below: must not appear
    ctx = available_context(s, 100, 2)
    assert ctx.index[-1] == s.index[98]
    assert ctx.isna().sum() == 2
    assert np.isnan(ctx.loc[s.index[40]]) and np.isnan(ctx.loc[s.index[97]])


def test_context_custom_length_and_bad_length():
    s = _series()
    assert available_context(s, 30, 0, L=5).tolist() == [26.0, 27.0, 28.0, 29.0, 30.0]
    with pytest.raises(ValueError):
        available_context(s, 30, 0, L=0)


def test_context_beyond_grid_raises():
    s = _series(50)
    assert available_context(s, 51, 2).iloc[-1] == 49  # issue past grid end is fine if t - d exists
    with pytest.raises(IndexError):
        available_context(s, 50, 0)


def test_context_ndarray_and_dataframe_and_copy():
    arr = np.arange(N, dtype=float)
    ctx = available_context(arr, 10, 4)
    assert ctx.tolist() == [float(i) for i in range(7)]
    ctx[:] = -1
    assert arr[0] == 0  # returned context is a copy

    df = pd.DataFrame({"a": np.arange(N, dtype=float), "b": -np.arange(N, dtype=float)})
    ctx_df = available_context(df, 12, 2, L=3)
    assert ctx_df.index.tolist() == [8, 9, 10]
    assert ctx_df["b"].tolist() == [-8.0, -9.0, -10.0]


# ---------- maturity ----------

@pytest.mark.parametrize("h, d", CELLS)
def test_each_record_matures_exactly_once_never_early(h, d):
    issues = range(60)
    ts = range(-5, 80)
    seen = {s: [t for t in ts if s in matured_at(t, h, d, issues)] for s in issues}
    for s in issues:
        assert seen[s] == [s + h + d]
        for t in ts:
            assert (s in matured_up_to(t, h, d, issues)) == (t >= s + h + d)


@pytest.mark.parametrize("h, d", CELLS)
def test_matured_up_to_is_union_of_matured_at(h, d):
    issues = range(0, 60, 3)  # sparse, unordered input is fine
    for t in range(0, 80):
        union = sorted(s for u in range(-10, t + 1) for s in matured_at(u, h, d, issues))
        assert matured_up_to(t, h, d, issues) == union


@pytest.mark.parametrize("h, d", CELLS)
def test_matured_record_label_is_legally_available(h, d):
    # The label of s is target s + h; at issue t it must be <= t - d.
    for t in range(0, 80):
        for s in matured_up_to(t, h, d, range(80)):
            assert s + h <= last_available(t, d)


def test_matured_order_and_duplicates():
    assert matured_up_to(20, 1, 0, [9, 3, 3, 15]) == [3, 9, 15]
    assert matured_at(10, 1, 0, [9, 9]) == [9]


# ---------- property test: no context reaches past t - d ----------

def test_property_no_context_index_beyond_t_minus_d():
    rng = np.random.default_rng(20261016)
    s = _series()
    for _ in range(500):
        h, d = CELLS[rng.integers(len(CELLS))]
        t = int(rng.integers(0, N))
        L = int(rng.integers(1, 200))
        ctx = available_context(s, t, d, L=L)
        assert len(ctx) == min(L, max(0, t - d + 1))
        if len(ctx):
            pos = s.index.get_indexer(ctx.index)
            assert pos.max() == t - d
            assert (ctx.to_numpy() == pos).all()  # values are the positions: nothing from after t - d
        # Perturb every value after t - d: the context must not change.
        future = s.copy()
        future.iloc[max(0, t - d + 1):] = rng.normal(size=N - max(0, t - d + 1)) * 1e6
        pd.testing.assert_series_equal(available_context(future, t, d, L=L), ctx)
