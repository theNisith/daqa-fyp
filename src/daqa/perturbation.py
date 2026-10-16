"""Future-label perturbation harness (proposal 5.6). Computes no score.

At a pre-declared issue t with delay d, every grid value with index > t - d
is legally unavailable. ``perturb_after`` alters exactly those values;
``take_snapshot`` reruns the pipeline from the first warm-up issue up to t
(contexts, Chronos-Bolt recomputed — never read from the cache — matured
queues with their label values, Frozen issued forecasts, MultiQT states and
outputs) for the two cells (h, d), h in {1, 4}; ``compare`` lists every
difference between two snapshots. Deterministic logic must match exactly;
Chronos outputs (and the Frozen forecasts derived from them) within 1e-6.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from daqa.cache import cache_issues, forecast, issue_contexts
from daqa.methods.multiqt import MultiQTResult, run_multiqt
from daqa.timing import HORIZONS, matured_up_to, step_index

PERTURB_SCALE = 10.0
PERTURB_SHIFT = 1000.0
CHRONOS_TOL = 1e-6


def perturb_after(grid: pd.DataFrame, cutoff: int) -> pd.DataFrame:
    """Copy of grid with every value at row index > cutoff set to value * 10 + 1000.

    NaN stays NaN: missing weeks are never filled, not even in a perturbation.
    """
    out = grid.copy()
    out.iloc[cutoff + 1 :] = out.iloc[cutoff + 1 :] * PERTURB_SCALE + PERTURB_SHIFT
    return out


def perturb_cell(grid: pd.DataFrame, row: int, area: str) -> pd.DataFrame:
    """Copy of grid with the single value (row, area) set to value * 10 + 1000."""
    out = grid.copy()
    j = out.columns.get_loc(area)
    out.iloc[row, j] = out.iloc[row, j] * PERTURB_SCALE + PERTURB_SHIFT
    return out


@dataclass
class Snapshot:
    dataset: str
    t: int
    d: int
    issues: np.ndarray  # first warm-up issue .. t
    contexts: np.ndarray  # (P, n_areas, 104)
    chronos: np.ndarray  # (P, n_areas, 8, 9) raw, recomputed
    frozen: dict[int, np.ndarray] = field(default_factory=dict)  # h -> (P, n_areas, 9) issued Frozen
    queue_issues: dict[int, np.ndarray] = field(default_factory=dict)  # h -> matured issues s (s + h + d <= t)
    queue_labels: dict[int, np.ndarray] = field(default_factory=dict)  # h -> (n_matured, n_areas) labels y[s + h]
    multiqt: dict[tuple, MultiQTResult] = field(default_factory=dict)  # (h, lr) -> result up to t


def take_snapshot(dataset: str, grid: pd.DataFrame, t: int, d: int, pipe, lrs) -> Snapshot:
    """Rerun the pipeline for cells (1, d) and (4, d) from the first warm-up issue up to issue t."""
    issues = np.arange(cache_issues(len(grid)).start, t + 1)
    contexts = np.stack([issue_contexts(grid, int(s), d) for s in issues])
    chronos = np.stack([forecast(pipe, c) for c in contexts])  # one batch per (issue, delay), as in the cache
    srt = np.sort(chronos, axis=-1)
    values = grid.to_numpy(dtype=np.float64)
    snap = Snapshot(dataset, t, d, issues, contexts, chronos)
    for h in HORIZONS:
        base = srt[:, :, step_index(h, d) - 1]
        snap.frozen[h] = np.maximum(0.0, base.astype(np.float64))
        matured = np.asarray(matured_up_to(t, h, d, issues), dtype=int)
        snap.queue_issues[h] = matured
        snap.queue_labels[h] = values[matured + h] if len(matured) else np.empty((0, grid.shape[1]))
        for lr in lrs:
            snap.multiqt[(h, lr)] = run_multiqt(dataset, h, d, lr, grid=grid, base=base, issues=issues)
    return snap


def compare(ref: Snapshot, other: Snapshot, chronos_tol: float = CHRONOS_TOL) -> list[str]:
    """Differences between ``other`` (up to its issue t) and the same prefix of ``ref``; [] if none."""
    if ref.dataset != other.dataset or ref.d != other.d or other.t > ref.t:
        raise ValueError("snapshots are not comparable")
    P = len(other.issues)
    if not np.array_equal(ref.issues[:P], other.issues):
        raise ValueError("issue ranges differ")
    out: list[str] = []

    def exact(name, a, b):
        if a.shape != b.shape or not np.array_equal(a, b, equal_nan=True):
            out.append(name)

    def close(name, a, b):
        diff = float(np.max(np.abs(a.astype(np.float64) - b.astype(np.float64)), initial=0.0))
        if not diff <= chronos_tol:
            out.append(f"{name} (max |diff| {diff:.3g})")

    exact("contexts", ref.contexts[:P], other.contexts)
    close("chronos", ref.chronos[:P], other.chronos)
    for h in HORIZONS:
        close(f"frozen issued h={h}", ref.frozen[h][:P], other.frozen[h])
        keep = ref.queue_issues[h] + h + ref.d <= other.t
        exact(f"queue issues h={h}", ref.queue_issues[h][keep], other.queue_issues[h])
        exact(f"queue labels h={h}", ref.queue_labels[h][keep], other.queue_labels[h])
    for key, res in other.multiqt.items():
        r = ref.multiqt[key]
        for name in ("theta", "q_scaled", "issued", "eta"):
            exact(f"multiqt {name} h={key[0]} lr={key[1]}", getattr(r, name)[:P], getattr(res, name))
        exact(f"multiqt scale h={key[0]} lr={key[1]}", r.scale, res.scale)
    return out
