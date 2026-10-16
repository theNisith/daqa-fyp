"""MultiQT (Ding, Gibbs and Tibshirani, 2025): own implementation (proposal 5.5).

Natural per-series form: every area (or ILINet region) keeps its own offset
vector theta in R^9 per (h, d) cell, on the scaled series y / s(i). At issue t:

1. Records that legally mature at t (``timing.matured_at``: the one issued at
   s = t - h - d) update theta, per level alpha:
       theta <- theta - eta * (1{y_s <= q_s} - alpha)
   where q_s is the *played* (isotonic-projected, scaled, unclipped) vector
   issued at s. A matured record whose label is NaN is skipped (state
   unchanged) and counted.
2. q_t = isotonic projection of (b_t / s(i) + theta); the issued forecast is
   max(0, s(i) * q_t).

So an outcome revealed after the forecast at s + D is first used at
s + D + 1 = s + h + d, with D = h - 1 + d. Conventions follow the authors'
``multiQT()`` at commit 3300f75 (see docs/refs.md), which this module matches
exactly on NaN-free streams (tests/test_multiqt.py):

- coverage is non-strict, 1{y <= q}, evaluated at the played q;
- adaptive+ rate: eta = max(0.1, 0.1 * Quantile_0.9(|y - b|)), pooled over all
  levels and the observed residuals at positions [max(0, p - W), p) of the
  list of observed records (W = 50, p = stream position of the issue); under
  delay D this is the last min(n_observed, W - D) residuals;
- the isotonic projection is scipy's PAVA, the kernel behind sklearn's
  IsotonicRegression used by the authors.

The base vector b is the cached sorted Chronos-Bolt vector at step h + d; it
is read from the cache, never recomputed. No score is computed here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy.optimize import isotonic_regression

from daqa.cache import QUANTILE_LEVELS, load_cache, load_grid
from daqa.data import area_scale, make_splits
from daqa.timing import matured_at, multiqt_delay, step_index

log = logging.getLogger(__name__)

IDENTITY = "identity"
ADAPTIVE = "adaptive+"
LR_WINDOW = 50
ADAPTIVE_SCALE = 0.1  # eta = max(ADAPTIVE_FLOOR, ADAPTIVE_SCALE * Quantile_ADAPTIVE_Q(|residuals|))
ADAPTIVE_FLOOR = 0.1
ADAPTIVE_Q = 0.9


def lr_candidates(fixed_rates: tuple[float, float]) -> tuple:
    """The four pre-declared candidates (proposal 5.6): identity, two fixed rates, adaptive+.

    The two fixed rates (on the scaled series) are protocol choices, not set here.
    """
    a, b = fixed_rates
    if not (a > 0 and b > 0 and a != b):
        raise ValueError(f"need two distinct positive fixed rates, got {fixed_rates}")
    return (IDENTITY, float(a), float(b), ADAPTIVE)


def isotonic(v: np.ndarray) -> np.ndarray:
    """L2 projection onto non-decreasing vectors."""
    return isotonic_regression(np.asarray(v, dtype=np.float64)).x


def _check_lr(lr) -> None:
    if lr in (IDENTITY, ADAPTIVE):
        return
    if isinstance(lr, (int, float)) and not isinstance(lr, bool) and lr > 0:
        return
    raise ValueError(f"lr must be {IDENTITY!r}, {ADAPTIVE!r} or a positive number, got {lr!r}")


@dataclass
class StreamResult:
    q: np.ndarray  # (T, L) played vectors, scaled, unclipped
    theta: np.ndarray  # (T, L) hidden offsets used at each issue
    eta: np.ndarray  # (T,) rate applied in the update made before each issue; NaN if none
    n_nan_skips: int


def run_stream(y, base, issues, h: int, d: int, lr, levels=QUANTILE_LEVELS,
               lr_window: int = LR_WINDOW) -> StreamResult:
    """MultiQT on one scaled series for one (h, d) cell.

    y[p] is the scaled label of the record issued at issues[p] (target
    issues[p] + h); it is read only once that record has matured. base[p] is
    the scaled base vector at issues[p]. ``issues`` must be consecutive.
    """
    _check_lr(lr)
    issues = list(issues)
    if issues != list(range(issues[0], issues[0] + len(issues))):
        raise ValueError("issues must be consecutive grid positions")
    base = np.asarray(base, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    alpha = np.asarray(levels, dtype=np.float64)
    T, L = base.shape
    if len(y) != T or len(issues) != T or L != len(alpha):
        raise ValueError("y, base, issues and levels have inconsistent shapes")
    D = multiqt_delay(h, d)

    q = np.empty((T, L))
    theta_hist = np.empty((T, L))
    eta_hist = np.full(T, np.nan)
    theta = np.zeros(L)
    observed: list[np.ndarray] = []  # residual rows y_s - b_s, in order of maturity
    skips = 0
    for p, t in enumerate(issues):
        records = [s - issues[0] for s in matured_at(t, h, d, issues[:p])]
        assert all(r == p - 1 - D for r in records)  # revealed after forecast r + D, used from r + D + 1
        usable = []
        for r in records:
            if np.isnan(y[r]):
                skips += 1
            else:
                usable.append(r)
                observed.append(y[r] - base[r])
        if usable and lr != IDENTITY:
            if lr == ADAPTIVE:
                window = np.abs(np.array(observed[max(0, p - lr_window) : p])).T
                eta = max(ADAPTIVE_FLOOR, ADAPTIVE_SCALE * np.quantile(window, ADAPTIVE_Q))
            else:
                eta = float(lr)
            for r in usable:
                theta = theta - eta * ((y[r] <= q[r]) - alpha)
            eta_hist[p] = eta
        theta_hist[p] = theta
        q[p] = isotonic(base[p] + theta)
    return StreamResult(q=q, theta=theta_hist, eta=eta_hist, n_nan_skips=skips)


@dataclass
class MultiQTResult:
    dataset: str
    h: int
    d: int
    lr: object
    issued: np.ndarray  # (n_issues, n_areas, 9) = max(0, s(i) * q), case/wILI units
    q_scaled: np.ndarray  # (n_issues, n_areas, 9) played, scaled, unclipped
    theta: np.ndarray  # (n_issues, n_areas, 9)
    eta: np.ndarray  # (n_issues, n_areas)
    nan_skips: dict[str, int]  # per area
    issue_idx: np.ndarray
    areas: np.ndarray
    scale: np.ndarray  # (n_areas,) s(i)


def run_multiqt(dataset: str, h: int, d: int, lr, cache=None, grid=None, base=None, issues=None) -> MultiQTResult:
    """MultiQT for every area of a dataset in one (h, d) cell.

    By default the base vectors and issues come from the forecast cache. Passing
    ``base`` ((n_issues, n_areas, 9) sorted, unscaled) with consecutive
    ``issues`` runs on recomputed base vectors instead (perturbation test).
    """
    grid = load_grid(dataset) if grid is None else grid
    scale = area_scale(grid, make_splits(len(grid)).scaling).to_numpy()
    if base is None:
        cache = load_cache(dataset) if cache is None else cache
        if list(cache.areas) != list(grid.columns) or len(cache.grid_dates) != len(grid):
            raise ValueError("cache and grid do not match")
        k = list(cache.delays).index(d)
        base = cache.sorted[:, :, k, step_index(h, d) - 1, :]
        issues = cache.issue_idx
    issues = np.asarray(issues)
    if base.shape != (len(issues), grid.shape[1], len(QUANTILE_LEVELS)):
        raise ValueError(f"base shape {base.shape} does not match issues/areas")
    base = np.asarray(base, dtype=np.float64) / scale[None, :, None]
    values = grid.to_numpy(dtype=np.float64)
    targets = issues + h
    labels = np.full((len(issues), grid.shape[1]), np.nan)
    inside = targets < len(grid)
    labels[inside] = values[targets[inside]]
    labels /= scale[None, :]

    shape = (len(issues), grid.shape[1], len(QUANTILE_LEVELS))
    q, theta = np.empty(shape), np.empty(shape)
    eta = np.empty(shape[:2])
    skips = {}
    for j, area in enumerate(grid.columns):
        res = run_stream(labels[:, j], base[:, j], issues, h, d, lr)
        q[:, j], theta[:, j], eta[:, j] = res.q, res.theta, res.eta
        skips[area] = res.n_nan_skips
        if res.n_nan_skips:
            log.info("MultiQT %s h=%d d=%d lr=%s: %s skipped %d matured NaN label(s)",
                     dataset, h, d, lr, area, res.n_nan_skips)
    issued = np.maximum(0.0, q * scale[None, :, None])
    return MultiQTResult(dataset=dataset, h=h, d=d, lr=lr, issued=issued, q_scaled=q, theta=theta,
                         eta=eta, nan_skips=skips, issue_idx=issues, areas=np.asarray(grid.columns, dtype=str),
                         scale=scale)
