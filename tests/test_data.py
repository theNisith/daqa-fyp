import numpy as np
import pandas as pd
import pytest

from daqa.data import (
    MISSING_AREA_WEEK,
    N_AREAS,
    N_WEEKS,
    area_scale,
    load_srilanka,
    make_splits,
    to_grid,
    validate,
)


@pytest.fixture(scope="module")
def df():
    return load_srilanka()


@pytest.fixture(scope="module")
def grid(df):
    return to_grid(df)


@pytest.fixture(scope="module")
def splits(grid):
    return make_splits(len(grid), max_h=4, dates=grid.index)


def _toy(rows):
    return pd.DataFrame(rows, columns=["area", "start_date", "cases"]).assign(
        start_date=lambda d: pd.to_datetime(d["start_date"])
    )


# ---------- load_srilanka ----------

def test_load_shape_and_types(df):
    assert len(df) == 26_311
    assert list(df.columns) == ["area", "start_date", "end_date", "year", "week", "cases"]
    assert pd.api.types.is_datetime64_any_dtype(df["start_date"])
    assert pd.api.types.is_datetime64_any_dtype(df["end_date"])
    assert df["cases"].dtype == float
    assert df["area"].nunique() == N_AREAS


def test_load_orders_by_start_date_not_year_week(df):
    assert df["start_date"].is_monotonic_increasing
    weeks = df.drop_duplicates("start_date").set_index("start_date")
    # 2026 week-53 row is dated 2025-12-20 and must precede 2026 week 1 (2025-12-29).
    assert weeks.loc["2025-12-20", ["year", "week"]].tolist() == [2026, 53]
    assert weeks.loc["2025-12-29", ["year", "week"]].tolist() == [2026, 1]
    pos = weeks.index.get_indexer(pd.to_datetime(["2025-12-20", "2025-12-29"]))
    assert pos[0] + 1 == pos[1]


def test_load_parses_dates_month_first(df):
    first = df.iloc[0]
    assert first["start_date"] == pd.Timestamp("2006-12-23")
    assert first["end_date"] == pd.Timestamp("2006-12-29")
    assert df["start_date"].max() == pd.Timestamp("2026-05-11")


# ---------- to_grid ----------

def test_grid_shape_dtype_index(grid):
    assert grid.shape == (N_WEEKS, N_AREAS)
    assert (grid.dtypes == float).all()
    assert grid.index.is_monotonic_increasing and grid.index.is_unique
    assert list(grid.columns) == sorted(grid.columns)


def test_grid_values_match_long_frame(df, grid):
    long = df.set_index(["start_date", "area"])["cases"]
    stacked = grid.stack()  # drops the single NaN
    assert len(stacked) == len(long)
    pd.testing.assert_series_equal(
        stacked.sort_index(), long.sort_index(), check_names=False
    )


def test_nan_survives_to_grid(grid):
    area, date = MISSING_AREA_WEEK
    assert np.isnan(grid.loc[date, area])
    assert int(grid.isna().sum().sum()) == 1


def test_toy_missing_area_week_is_nan_not_zero():
    toy = _toy([("A", "2020-01-04", 3.0), ("B", "2020-01-04", 0.0), ("A", "2020-01-11", 5.0)])
    g = to_grid(toy)
    assert np.isnan(g.loc["2020-01-11", "B"])
    assert g.loc["2020-01-04", "B"] == 0.0


def test_toy_duplicate_rejected():
    toy = _toy([("A", "2020-01-04", 3.0), ("A", "2020-01-04", 4.0)])
    with pytest.raises(ValueError, match="duplicate"):
        to_grid(toy)


# ---------- validate ----------

def test_validate_passes_on_pinned_data(df, grid):
    validate(df, grid)


def test_validate_rejects_negative(df, grid):
    bad = grid.copy()
    bad.iloc[10, 3] = -1.0
    with pytest.raises(AssertionError, match="negative"):
        validate(df, bad)


def test_validate_rejects_extra_nan(df, grid):
    bad = grid.copy()
    bad.iloc[10, 3] = np.nan
    with pytest.raises(AssertionError, match="NaN"):
        validate(df, bad)


def test_validate_rejects_nan_filled_with_zero(df, grid):
    with pytest.raises(AssertionError, match="NaN"):
        validate(df, grid.fillna(0.0))


def test_validate_rejects_wrong_shape(df, grid):
    with pytest.raises(AssertionError, match="shape"):
        validate(df, grid.iloc[:-1])


def test_validate_rejects_duplicate_rows(df, grid):
    with pytest.raises(AssertionError, match="duplicate"):
        validate(pd.concat([df, df.iloc[[0]]]), grid)


# ---------- make_splits ----------

def test_splits_exact_indices(splits):
    n = N_WEEKS
    assert splits.test == range(n - 4 - 104, n - 4)
    assert splits.test[-1] == n - 1 - 4
    assert splits.validation == range(splits.test.start - 52, splits.test.start)
    assert splits.warmup == range(splits.validation.start - 52, splits.validation.start)
    assert splits.scaling == range(0, splits.warmup.start)
    assert len(splits.scaling) >= 104


def test_splits_disjoint_contiguous_and_in_time_order(splits, grid):
    segs = list(splits.segments().values())
    idx = [i for r in segs for i in r]
    assert len(idx) == len(set(idx))  # disjoint
    assert idx == list(range(len(idx)))  # contiguous from 0, earliest segment first
    for earlier, later in zip(segs, segs[1:]):
        assert earlier[-1] < later[0]
        assert grid.index[earlier[-1]] < grid.index[later[0]]


def test_every_test_target_exists_for_all_cells(splits):
    # Same 104 origins for all six (h, d) cells; t + h is in range for h <= 4,
    # and the latest legal observation t - d is in range for d <= 4.
    for h in (1, 4):
        for d in (0, 2, 4):
            assert max(splits.test) + h <= N_WEEKS - 1
            assert min(splits.test) - d >= 0
    assert len(splits.test) == 104


def test_splits_dates(splits, grid):
    for name, r in splits.segments().items():
        assert splits.dates[name] == (grid.index[r[0]], grid.index[r[-1]])


def test_splits_require_scaling_history():
    with pytest.raises(ValueError, match="scaling"):
        make_splits(4 + 104 + 52 + 52 + 103)
    make_splits(4 + 104 + 52 + 52 + 104)


def test_splits_reject_mismatched_dates(grid):
    with pytest.raises(ValueError, match="len"):
        make_splits(len(grid) - 1, dates=grid.index)


# ---------- area_scale ----------

def test_scale_definition(grid, splits):
    s = area_scale(grid, splits.scaling)
    expected = np.maximum(1.0, grid.iloc[: splits.scaling.stop].mean())
    pd.testing.assert_series_equal(s, expected, check_names=False)
    assert (s >= 1.0).all()
    assert list(s.index) == list(grid.columns)


def test_scale_unchanged_when_test_period_multiplied_by_100(grid, splits):
    s = area_scale(grid, splits.scaling)
    bumped = grid.copy()
    bumped.iloc[list(splits.test)] *= 100
    pd.testing.assert_series_equal(area_scale(bumped, splits.scaling), s)


def test_scale_unchanged_when_all_post_scaling_weeks_change(grid, splits):
    s = area_scale(grid, splits.scaling)
    bumped = grid.copy()
    bumped.iloc[splits.scaling.stop :] = 1e6
    pd.testing.assert_series_equal(area_scale(bumped, splits.scaling), s)


def test_scale_includes_covid_weeks(grid, splits):
    covid = (grid.index >= "2020-01-01") & (grid.index <= "2021-12-31")
    pos = np.flatnonzero(covid)
    assert len(pos) > 0 and pos.max() < splits.scaling.stop
    s = area_scale(grid, splits.scaling)
    bumped = grid.copy()
    bumped.iloc[pos] += 1000
    assert (area_scale(bumped, splits.scaling) > s).all()


def test_scale_floor_and_nan_handling():
    idx = pd.date_range("2020-01-04", periods=4, freq="7D")
    g = pd.DataFrame({"low": [0.0, 0.0, 1.0, 0.0], "gap": [10.0, np.nan, 20.0, 999.0]}, index=idx)
    s = area_scale(g, range(0, 3))
    assert s["low"] == 1.0  # mean 1/3 floored to 1
    assert s["gap"] == 15.0  # NaN skipped, week 3 outside segment


def test_scale_rejects_all_nan_area():
    idx = pd.date_range("2020-01-04", periods=3, freq="7D")
    g = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [np.nan, np.nan, 3.0]}, index=idx)
    with pytest.raises(ValueError, match="b"):
        area_scale(g, range(0, 2))
