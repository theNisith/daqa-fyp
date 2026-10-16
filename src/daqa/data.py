"""Sri Lankan dengue data layer: load, weekly grid, validation, splits, area scale.

Chronology is taken from ``start.date`` only. The ``year``/``week`` columns are
kept for auditing but never used for ordering (2024-25 labels are shifted by
one, the 2026 week-53 row is dated 2025-12-20, and weeks start on Monday from
2026; see data/AUDIT.md). No imputation, transforms, smoothing or outlier
removal happens here: a missing area-week stays NaN.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadr

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "srilanka_weekly_data.rda"
DATE_FORMAT = "%m/%d/%Y"

N_WEEKS = 1012
N_AREAS = 26
MISSING_AREA_WEEK = ("Puttalam", pd.Timestamp("2026-02-09"))

N_TEST = 104
N_VALIDATION = 52
N_WARMUP = 52
MIN_SCALING = 104


def load_srilanka(path: str | Path = DATA_PATH) -> pd.DataFrame:
    """Long frame with columns area, start_date, end_date, year, week, cases.

    Rows are ordered by (start_date, area), never by (year, week).
    """
    result = pyreadr.read_r(str(path))
    (raw,) = result.values()
    df = pd.DataFrame(
        {
            "area": raw["district"].astype(str),
            "start_date": pd.to_datetime(raw["start.date"], format=DATE_FORMAT),
            "end_date": pd.to_datetime(raw["end.date"], format=DATE_FORMAT),
            "year": raw["year"],
            "week": raw["week"],
            "cases": raw["cases"].astype(float),
        }
    )
    return df.sort_values(["start_date", "area"], kind="mergesort").reset_index(drop=True)


def to_grid(df: pd.DataFrame) -> pd.DataFrame:
    """Week x area matrix of float counts; an absent area-week is NaN, never 0.

    Index is the sorted unique start_date; columns are the areas, sorted.
    """
    dup = df.duplicated(["area", "start_date"])
    if dup.any():
        raise ValueError(f"{int(dup.sum())} duplicate (area, start_date) rows")
    grid = df.pivot(index="start_date", columns="area", values="cases")
    grid = grid.sort_index().sort_index(axis=1).astype(float)
    grid.columns.name = "area"
    return grid


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def validate(df: pd.DataFrame, grid: pd.DataFrame) -> None:
    """Raise AssertionError unless the pinned Sri Lankan data look as audited."""
    _check(not df.duplicated(["area", "start_date"]).any(), "duplicate (area, start_date) rows")
    _check(df["cases"].notna().all(), "raw cases column contains NaN")
    _check(grid.shape == (N_WEEKS, N_AREAS), f"grid shape {grid.shape} != {(N_WEEKS, N_AREAS)}")
    _check(grid.index.is_monotonic_increasing and grid.index.is_unique, "grid index not strictly increasing")
    _check(bool((grid.fillna(0) >= 0).all().all()), "negative counts")
    rows, cols = np.where(grid.isna().to_numpy())
    nan_cells = [(grid.columns[c], grid.index[r]) for r, c in zip(rows, cols)]
    _check(nan_cells == [MISSING_AREA_WEEK], f"expected only NaN at {MISSING_AREA_WEEK}, got {nan_cells}")


@dataclass(frozen=True)
class Splits:
    """Issue-week index ranges, earliest to latest. Shared by all six (h, d) cells."""

    scaling: range
    warmup: range
    validation: range
    test: range
    dates: dict[str, tuple[pd.Timestamp, pd.Timestamp]] | None = None

    def segments(self) -> dict[str, range]:
        return {
            "scaling": self.scaling,
            "warmup": self.warmup,
            "validation": self.validation,
            "test": self.test,
        }


def make_splits(
    n_weeks: int, max_h: int = 4, dates: pd.DatetimeIndex | None = None
) -> Splits:
    """Chronological splits counting back from the final week (proposal 5.2).

    The last test issue is n_weeks - 1 - max_h, so every h <= max_h target of
    every test issue exists in the data. Test = 104 issues, validation = 52
    before it, warm-up = 52 before that, scaling = every earlier week.
    """
    test_end = n_weeks - max_h  # exclusive
    test = range(test_end - N_TEST, test_end)
    validation = range(test.start - N_VALIDATION, test.start)
    warmup = range(validation.start - N_WARMUP, validation.start)
    scaling = range(0, warmup.start)
    if len(scaling) < MIN_SCALING:
        raise ValueError(f"scaling segment has {len(scaling)} weeks, need >= {MIN_SCALING}")

    splits = Splits(scaling=scaling, warmup=warmup, validation=validation, test=test)
    if dates is None:
        return splits
    if len(dates) != n_weeks:
        raise ValueError(f"len(dates)={len(dates)} != n_weeks={n_weeks}")
    seg_dates = {name: (dates[r[0]], dates[r[-1]]) for name, r in splits.segments().items()}
    return Splits(scaling=scaling, warmup=warmup, validation=validation, test=test, dates=seg_dates)


def area_scale(grid: pd.DataFrame, scaling_idx: range) -> pd.Series:
    """s(i) = max(1, nanmean of area i over the scaling segment only).

    COVID weeks (2020-21) are not excluded. Raises if an area has no observed
    week in the segment.
    """
    seg = grid.iloc[list(scaling_idx)]
    empty = seg.columns[seg.notna().sum() == 0]
    if len(empty):
        raise ValueError(f"no observed weeks in scaling segment for {list(empty)}")
    return np.maximum(1.0, seg.mean(skipna=True)).rename("scale")
