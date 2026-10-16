"""Frozen Chronos-Bolt forecast cache (proposal 5.3). Inference only, no scoring.

For each dataset, area, issue t (first warm-up issue .. last test issue) and
delay d in {0, 2, 4}, the context is ``timing.available_context(series, t, d,
104)`` and one 8-step request to amazon/chronos-bolt-small (pinned revision,
CPU, float32, eval mode, no grad) returns the native 0.1..0.9 quantiles. The
step-(h + d) row serves horizon h. Raw quantiles are stored unclipped; the
sorted copy sorts each 9-vector ascending. Negatives are never clipped here.

Run: python -m daqa.cache   (writes cache/*.npz and cache/MANIFEST.md)
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from daqa.data import load_ilinet, load_srilanka, make_splits, to_grid
from daqa.timing import CONTEXT_LENGTH, DELAYS, MAX_STEP, available_context

MODEL_ID = "amazon/chronos-bolt-small"
MODEL_REVISION = "772f3d25d38aec6d914c8949dab4462e2d46f5d8"
QUANTILE_LEVELS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
N_STEPS = MAX_STEP  # 8: step h + d for h in {1, 4}, d in {0, 2, 4}
CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"
DATASETS = ("srilanka", "ilinet")


def load_grid(dataset: str) -> pd.DataFrame:
    if dataset == "srilanka":
        return to_grid(load_srilanka())
    if dataset == "ilinet":
        return load_ilinet()
    raise ValueError(f"unknown dataset {dataset!r}")


def cache_issues(n_weeks: int) -> range:
    """First warm-up issue .. last test issue, from make_splits on the grid."""
    s = make_splits(n_weeks)
    return range(s.warmup.start, s.test.stop)


def load_pipeline():
    """Frozen Chronos-Bolt at the pinned revision, CPU, float32, eval mode."""
    from chronos import BaseChronosPipeline

    pipe = BaseChronosPipeline.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, device_map="cpu", torch_dtype=torch.float32
    )
    pipe.model.eval()
    for p in pipe.model.parameters():
        p.requires_grad_(False)
    if list(pipe.quantiles) != QUANTILE_LEVELS:
        raise RuntimeError(f"model quantiles {pipe.quantiles} != {QUANTILE_LEVELS}")
    return pipe


def issue_contexts(grid: pd.DataFrame, t: int, d: int, L: int = CONTEXT_LENGTH) -> np.ndarray:
    """(n_areas, L) float32 contexts at issue t, delay d, areas in grid column order; NaN kept.

    Every context must be full length L (true from the warm-up onward); a
    shorter one raises rather than being padded.
    """
    ctx = available_context(grid.to_numpy(dtype=np.float64), t, d, L)  # rows <= t - d
    if len(ctx) != L:
        raise ValueError(f"t={t} d={d}: context length {len(ctx)} < {L}")
    return np.ascontiguousarray(ctx.T, dtype=np.float32)


def forecast(pipe, contexts: np.ndarray) -> np.ndarray:
    """One batched request: (B, L) contexts -> (B, N_STEPS, 9) raw native quantiles, float32."""
    if pipe.model.training:
        raise RuntimeError("model must be in eval mode")
    batch = torch.from_numpy(np.array(contexts, dtype=np.float32, copy=True))
    with torch.no_grad():
        q, _ = pipe.predict_quantiles(batch, prediction_length=N_STEPS, quantile_levels=QUANTILE_LEVELS)
    return q.numpy().astype(np.float32, copy=False)


def forecast_issue(pipe, grid: pd.DataFrame, t: int, d: int) -> np.ndarray:
    """(n_areas, N_STEPS, 9) raw quantiles for issue t, delay d.

    The batch is always all areas at one (t, d). CPU float32 outputs depend on
    batch composition at the ~1e-5 level, so fixing the batch makes any
    recomputation bitwise reproducible.
    """
    return forecast(pipe, issue_contexts(grid, t, d))


@dataclass
class Cache:
    dataset: str
    raw: np.ndarray  # (n_issues, n_areas, n_delays, N_STEPS, 9), unclipped
    sorted: np.ndarray  # same shape, each 9-vector sorted ascending
    needed_sort: np.ndarray  # (n_issues, n_areas, n_delays, N_STEPS) bool
    context_nan: np.ndarray  # (n_issues, n_areas, n_delays) NaN count per context
    issue_idx: np.ndarray  # (n_issues,) grid positions
    issue_dates: np.ndarray  # (n_issues,) datetime64[ns]
    grid_dates: np.ndarray  # (n_weeks,) full grid index; target of step k at issue t, delay d is t - d + k
    areas: np.ndarray
    delays: np.ndarray
    steps: np.ndarray
    quantile_levels: np.ndarray

    def path(self, cache_dir: Path = CACHE_DIR) -> Path:
        return Path(cache_dir) / f"{self.dataset}_chronos_bolt_small.npz"

    def entry(self, area: str, t: int, d: int, sorted_: bool = False) -> np.ndarray:
        """(N_STEPS, 9) quantiles for one area, issue position t and delay d."""
        i = int(np.flatnonzero(self.issue_idx == t)[0])
        j = int(np.flatnonzero(self.areas == area)[0])
        k = int(np.flatnonzero(self.delays == d)[0])
        return (self.sorted if sorted_ else self.raw)[i, j, k]


def build_cache(dataset: str, pipe) -> Cache:
    grid = load_grid(dataset)
    issues = cache_issues(len(grid))
    shape = (len(issues), grid.shape[1], len(DELAYS))
    raw = np.empty(shape + (N_STEPS, len(QUANTILE_LEVELS)), dtype=np.float32)
    context_nan = np.empty(shape, dtype=np.int16)
    for i, t in enumerate(issues):
        for k, d in enumerate(DELAYS):
            ctx = issue_contexts(grid, t, d)
            context_nan[i, :, k] = np.isnan(ctx).sum(axis=1)
            raw[i, :, k] = forecast(pipe, ctx)
    srt = np.sort(raw, axis=-1)
    return Cache(
        dataset=dataset,
        raw=raw,
        sorted=srt,
        needed_sort=(np.diff(raw, axis=-1) < 0).any(axis=-1),
        context_nan=context_nan,
        issue_idx=np.arange(issues.start, issues.stop),
        issue_dates=grid.index[issues.start : issues.stop].to_numpy(),
        grid_dates=grid.index.to_numpy(),
        areas=np.asarray(grid.columns, dtype=str),
        delays=np.asarray(DELAYS),
        steps=np.arange(1, N_STEPS + 1),
        quantile_levels=np.asarray(QUANTILE_LEVELS),
    )


_FIELDS = ("raw", "sorted", "needed_sort", "context_nan", "issue_idx", "issue_dates", "grid_dates",
           "areas", "delays", "steps", "quantile_levels")


def save_cache(cache: Cache, cache_dir: Path = CACHE_DIR) -> Path:
    path = cache.path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **{f: getattr(cache, f) for f in _FIELDS})
    return path


def load_cache(dataset: str, cache_dir: Path = CACHE_DIR) -> Cache:
    path = Path(cache_dir) / f"{dataset}_chronos_bolt_small.npz"
    with np.load(path, allow_pickle=False) as z:
        return Cache(dataset=dataset, **{f: z[f] for f in _FIELDS})


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _model_file_sha() -> str:
    from huggingface_hub import hf_hub_download

    return sha256_file(hf_hub_download(MODEL_ID, "model.safetensors", revision=MODEL_REVISION))


def write_manifest(caches: dict[str, Cache], paths: dict[str, Path], runtime: dict[str, float],
                   started: str, cache_dir: Path = CACHE_DIR) -> Path:
    import transformers

    lines = [
        "# cache/ — frozen Chronos-Bolt forecast cache",
        "",
        "Generated by `python -m daqa.cache` (src/daqa/cache.py). Inference only: no accuracy",
        "or score was computed. Raw quantiles are **unclipped**; clipping at 0 happens at issue",
        "time for every method. The frozen base vector b for horizon h and delay d is",
        "`sorted[issue, area, delay, step index h + d - 1 (0-based)]`.",
        "",
        "## Model and software",
        "",
        f"- Model: `{MODEL_ID}`, revision `{MODEL_REVISION}` (Hugging Face cache snapshot folder name)",
        f"- model.safetensors SHA-256: `{_model_file_sha()}`",
        f"- chronos-forecasting {_pkg_version('chronos-forecasting')}, "
        f"torch {torch.__version__}, transformers {transformers.__version__}, numpy {np.__version__}",
        f"- CPU, float32, eval mode, `torch.no_grad`, all parameters `requires_grad=False`; "
        f"torch threads {torch.get_num_threads()}",
        f"- Request: context = `available_context(series, t, d, {CONTEXT_LENGTH})`, prediction_length {N_STEPS}, "
        f"quantile_levels {QUANTILE_LEVELS} (exactly the model's native levels, so no interpolation)",
        "- Batching: one request per (issue, delay) containing all areas in grid column order. "
        "Measured before the build: re-running an identical batch is bitwise identical, while "
        "forecasting a context inside a different batch moves outputs by float32 noise "
        "(max 3.8e-5 absolute, 6.5e-6 relative, 20 Sri Lankan contexts); the fixed batch "
        "makes every recomputation exact (`forecast_issue`).",
        f"- Run started {started}; runtime (inference + context building) "
        + ", ".join(f"{k} {v:.1f} s" for k, v in runtime.items()),
        "",
        "## Files",
        "",
        "| file | SHA-256 | bytes |",
        "|---|---|---|",
    ]
    for ds, p in paths.items():
        lines.append(f"| `{p.name}` | `{sha256_file(p)}` | {p.stat().st_size:,} |")
    lines += [
        "",
        "Arrays in each file: `raw`, `sorted` (n_issues, n_areas, n_delays, 8, 9) float32; "
        "`needed_sort` (n_issues, n_areas, n_delays, 8) bool; `context_nan` (n_issues, n_areas, n_delays); "
        "`issue_idx`, `issue_dates` (n_issues,); `grid_dates` (n_weeks,) — the target of step k at issue t "
        "and delay d is grid row t − d + k; `areas`; `delays` = [0, 2, 4]; `steps` = 1..8; `quantile_levels`.",
    ]
    for ds, c in caches.items():
        s = make_splits(len(c.grid_dates))
        n_vec = int(np.prod(c.needed_sort.shape))
        lines += [
            "",
            f"## {ds}",
            "",
            f"- Shapes: raw {c.raw.shape}, sorted {c.sorted.shape}, needed_sort {c.needed_sort.shape}, "
            f"context_nan {c.context_nan.shape}, grid_dates {c.grid_dates.shape}",
            f"- Issues: grid rows {c.issue_idx[0]}–{c.issue_idx[-1]} ({len(c.issue_idx)} issues; "
            f"warm-up {s.warmup.start}–{s.warmup.stop - 1}, validation {s.validation.start}–{s.validation.stop - 1}, "
            f"test {s.test.start}–{s.test.stop - 1}); dates "
            f"{pd.Timestamp(c.issue_dates[0]).date()} → {pd.Timestamp(c.issue_dates[-1]).date()}",
            f"- Contexts: {int(np.prod(c.context_nan.shape)):,} (all length {CONTEXT_LENGTH}); "
            f"containing NaN: **{int((c.context_nan > 0).sum())}**"
            + _nan_detail(c),
            f"- 9-vectors needing sorting: **{int(c.needed_sort.sum())}** of {n_vec:,}",
            f"- NaN in outputs: {int(np.isnan(c.raw).sum())}",
            f"- SHA-256 of `raw` array bytes (content check, independent of zip metadata): "
            f"`{hashlib.sha256(np.ascontiguousarray(c.raw).tobytes()).hexdigest()}`",
            "",
            "Negative raw quantiles per area (before any clipping), out of "
            f"{int(np.prod(c.raw.shape[:1] + c.raw.shape[2:])):,} values per area:",
            "",
            "| area | negative raw quantiles |",
            "|---|---|",
        ]
        neg = (c.raw < 0).sum(axis=(0, 2, 3, 4))
        lines += [f"| {a} | {int(n)} |" for a, n in zip(c.areas, neg)]
        lines.append(f"| **total** | **{int(neg.sum())}** |")
    path = Path(cache_dir) / "MANIFEST.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def _nan_detail(c: Cache) -> str:
    if not (c.context_nan > 0).any():
        return ""
    per_area = (c.context_nan > 0).sum(axis=(0, 2))
    return " (" + ", ".join(f"{a}: {int(n)}" for a, n in zip(c.areas, per_area) if n) + ")"


def _pkg_version(name: str) -> str:
    from importlib.metadata import version

    return version(name)


def main() -> None:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pipe = load_pipeline()
    caches, paths, runtime = {}, {}, {}
    for ds in DATASETS:
        t0 = time.perf_counter()
        caches[ds] = build_cache(ds, pipe)
        runtime[ds] = time.perf_counter() - t0
        paths[ds] = save_cache(caches[ds])
        print(f"{ds}: raw {caches[ds].raw.shape} in {runtime[ds]:.1f} s -> {paths[ds]}")
    print(f"manifest -> {write_manifest(caches, paths, runtime, started)}")


if __name__ == "__main__":
    main()
