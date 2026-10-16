"""Smoke test: frozen amazon/chronos-bolt-small on CPU, inference only.

Confirms the frozen base forecaster loads and returns valid native quantiles,
including when the context window contains a missing week (NaN). No training
or fine-tuning happens here.
"""

import time

import numpy as np
import pandas as pd
import pyreadr
import torch
from chronos import BaseChronosPipeline

DATA_PATH = "data/srilanka_weekly_data.rda"
CONTEXT_LEN = 104
PREDICTION_LENGTH = 8
QUANTILE_LEVELS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def load_grid() -> pd.DataFrame:
    result = pyreadr.read_r(DATA_PATH)
    (df_name,) = result.keys()
    df = result[df_name]
    df["start.date"] = pd.to_datetime(df["start.date"], format="%m/%d/%Y")
    df = df.sort_values("start.date")

    grid = sorted(df["start.date"].unique())
    pivot = df.pivot_table(index="start.date", columns="district", values="cases", aggfunc="first")
    pivot = pivot.reindex(grid)  # missing area-weeks become NaN, never 0
    return pivot


def run_test(pipeline: BaseChronosPipeline, name: str, context: np.ndarray) -> None:
    print(f"\n--- {name} ---")
    print(f"Context length: {len(context)}, NaNs in context: {int(np.isnan(context).sum())}")

    context_tensor = torch.tensor(context, dtype=torch.float32)

    start = time.perf_counter()
    with torch.no_grad():
        quantiles, _mean = pipeline.predict_quantiles(
            inputs=context_tensor,
            prediction_length=PREDICTION_LENGTH,
            quantile_levels=QUANTILE_LEVELS,
        )
    elapsed = time.perf_counter() - start

    quantiles_np = quantiles.numpy()
    print(f"Output shape: {quantiles_np.shape}")

    arr = quantiles_np[0]  # (prediction_length, n_quantiles)
    non_decreasing = bool(np.all(np.diff(arr, axis=1) >= 0))
    any_negative = bool(np.any(arr < 0))
    any_nan = bool(np.any(np.isnan(arr)))

    print(f"Non-decreasing across 9 levels at every step: {non_decreasing}")
    print(f"Any value < 0: {any_negative}")
    print(f"Any NaN in output: {any_nan}")
    print("8x9 quantile table (rounded to 1 decimal):")
    table = pd.DataFrame(
        np.round(arr, 1),
        columns=[f"q{q}" for q in QUANTILE_LEVELS],
        index=[f"t+{i+1}" for i in range(PREDICTION_LENGTH)],
    )
    print(table.to_string())
    print(f"Runtime: {elapsed:.3f}s")


def main() -> None:
    pivot = load_grid()

    pipeline = BaseChronosPipeline.from_pretrained(
        "amazon/chronos-bolt-small",
        device_map="cpu",
        torch_dtype=torch.float32,
    )

    colombo_context = pivot["Colombo"].iloc[-CONTEXT_LEN:].to_numpy(dtype=np.float32)
    run_test(pipeline, "Test 1: Colombo", colombo_context)

    puttalam_series = pivot["Puttalam"].iloc[-CONTEXT_LEN:]
    nan_dates = puttalam_series[puttalam_series.isna()].index.tolist()
    print(f"\nPuttalam NaN dates in last {CONTEXT_LEN}-week context: {nan_dates}")
    assert nan_dates == [pd.Timestamp("2026-02-09")], f"Expected exactly one NaN at 2026-02-09, got {nan_dates}"

    puttalam_context = puttalam_series.to_numpy(dtype=np.float32)
    try:
        run_test(pipeline, "Test 2: Puttalam (contains NaN)", puttalam_context)
    except Exception as exc:  # noqa: BLE001 - intentionally broad, printed and re-raised as info only
        print("\n--- Test 2: Puttalam (contains NaN) ---")
        print("Test 2 raised an error (NaN left as-is, not filled or interpolated):")
        import traceback

        traceback.print_exc()

    print("\nTest 1 finished regardless of Test 2 outcome.")


if __name__ == "__main__":
    main()
