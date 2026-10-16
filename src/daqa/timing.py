"""Information timing on a weekly grid (proposal 5.3, 5.4, 5.5).

All indices are integer positions on a dataset's own weekly grid (rows of the
Sri Lankan or ILINet grid); both datasets are treated identically.

- At issue t with delay d, the latest available observation is t - d.
- The target is t + h, requested from that context as step h + d.
- A forecast issued at s first becomes usable for any update at issue s + h + d.
- MultiQT delay D = h - 1 + d, so its first use s + D + 1 equals s + h + d.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

HORIZONS = (1, 4)
DELAYS = (0, 2, 4)
CELLS = tuple((h, d) for h in HORIZONS for d in DELAYS)
CONTEXT_LENGTH = 104
MAX_STEP = max(HORIZONS) + max(DELAYS)  # 8: one request per area/issue/delay serves both horizons


def _check_cell(h: int, d: int) -> None:
    if h not in HORIZONS or d not in DELAYS:
        raise ValueError(f"(h, d) = ({h}, {d}) is not a study cell; h in {HORIZONS}, d in {DELAYS}")


def last_available(t: int, d: int) -> int:
    """Index of the latest observation available at issue t under delay d."""
    if d not in DELAYS:
        raise ValueError(f"d = {d} not in {DELAYS}")
    return t - d


def available_context(series, t: int, d: int, L: int = CONTEXT_LENGTH):
    """The last L values with grid index <= t - d, as a copy.

    NaN is kept. If fewer than L legal values exist the context is shorter
    (empty when t - d < 0); it is never padded, least of all with values after
    t - d. Works positionally on a Series, DataFrame (rows) or ndarray (axis 0).
    """
    if L < 1:
        raise ValueError(f"L = {L} must be >= 1")
    end = last_available(t, d) + 1  # exclusive
    if end > len(series):
        raise IndexError(f"issue {t} with d={d} needs index {end - 1}, grid has {len(series)} rows")
    start = max(0, end - L)
    if end <= 0:
        start = end = 0
    if isinstance(series, (pd.Series, pd.DataFrame)):
        return series.iloc[start:end].copy()
    return np.array(series[start:end], copy=True)


def step_index(h: int, d: int) -> int:
    """Forecast step that reaches target t + h from a context ending at t - d."""
    _check_cell(h, d)
    return h + d


def first_usable_issue(s: int, h: int, d: int) -> int:
    """First issue at which the forecast issued at s (and its label) may update any method."""
    _check_cell(h, d)
    return s + h + d


def multiqt_delay(h: int, d: int) -> int:
    """MultiQT delay D = h - 1 + d (proposal 5.1; D = h - 1 when d = 0)."""
    _check_cell(h, d)
    return h - 1 + d


def matured_at(t: int, h: int, d: int, issues: Iterable[int]) -> list[int]:
    """Issues s with s + h + d == t: the records that first mature at issue t, ascending."""
    _check_cell(h, d)
    return sorted(s for s in set(issues) if s + h + d == t)


def matured_up_to(t: int, h: int, d: int, issues: Iterable[int]) -> list[int]:
    """Issues s with s + h + d <= t: every record legally usable by issue t, ascending."""
    _check_cell(h, d)
    return sorted(s for s in set(issues) if s + h + d <= t)
