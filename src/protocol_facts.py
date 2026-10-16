"""Data facts written into protocol/protocol.md (proposal 5.2, 5.8, 5.9). Reads data only; no forecast, no score.

Run: python src/protocol_facts.py   (exits non-zero if the Sri Lankan test window or
post-release counts differ from the values the protocol expects).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from daqa.cache import DATASETS, load_grid  # noqa: E402
from daqa.data import DATA_PATH, ILINET_PATH, make_splits  # noqa: E402
from daqa.timing import HORIZONS  # noqa: E402

RELEASE = pd.Timestamp("2024-11-26")  # amazon/chronos-bolt-small release date (proposal 5.2, 5.9)
CASE_WEEKS = 13
SHOCK_WEEKS = 3
EXPECTED_SL = {"n_test": 104, "first": "2024-04-20", "last": "2026-04-13", "post_issues": 72, "post_h1": 73, "post_h4": 76}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def day(ts) -> str:
    return str(pd.Timestamp(ts).date())


def splits_and_post_release(ds: str, g: pd.DataFrame) -> dict:
    s = make_splits(len(g))
    dates = g.index
    print(f"\n## {ds}: {len(g)} weeks x {g.shape[1]} areas")
    for name, r in [("scaling", s.scaling), ("gap (history only)", range(s.scaling.stop, s.warmup.start)),
                    ("warm-up", s.warmup), ("validation", s.validation), ("test", s.test)]:
        print(f"  {name:20s} rows {r[0]}-{r[-1]} ({len(r)}): {day(dates[r[0]])} -> {day(dates[r[-1]])}")
    test = np.array(s.test)
    out = {"n_test": len(test), "first": day(dates[test[0]]), "last": day(dates[test[-1]]),
           "post_issues": int((dates[test] > RELEASE).sum())}
    print(f"  test issue weeks: {out['n_test']}, {out['first']} -> {out['last']}; "
          f"issue start > {day(RELEASE)}: {out['post_issues']}")
    for h in HORIZONS:
        tgt = dates[test + h]
        out[f"post_h{h}"] = int((tgt > RELEASE).sum())
        print(f"  h={h}: target weeks {day(tgt[0])} -> {day(tgt[-1])}; target start > {day(RELEASE)}: "
              f"{out[f'post_h{h}']} (first post-release target {day(tgt[tgt > RELEASE][0])})")
    return out


def shock(g: pd.DataFrame) -> None:
    """5.9: eligible area with the median pre-test mean count (lower of the two middle areas);
    x3 for three consecutive weeks from the first week of the second test year."""
    s = make_splits(len(g))
    for label, rows in [("scaling segment", s.scaling), ("all pre-test rows", range(0, s.test.start))]:
        m = g.iloc[list(rows)].mean(skipna=True).sort_values(kind="mergesort")
        n = len(m)
        lower_mid = m.index[(n - 1) // 2]  # n = 26: 13th of 26 (0-based 12), the lower of the two middle areas
        print(f"  shock area by {label} (rows {rows[0]}-{rows[-1]}): {lower_mid} (mean {m[lower_mid]:.4f}); "
              f"middle pair {m.index[n // 2 - 1]} {m.iloc[n // 2 - 1]:.4f} / {m.index[n // 2]} {m.iloc[n // 2]:.4f}")
    start = s.test.start + 52
    rows = range(start, start + SHOCK_WEEKS)
    print(f"  shock rows {rows[0]}-{rows[-1]} (test week 53-55): "
          + ", ".join(day(g.index[r]) for r in rows))


def case_study(g: pd.DataFrame) -> None:
    """5.9: the 13-week period with the highest aggregate count inside the test window (issue weeks)."""
    s = make_splits(len(g))
    seg = g.iloc[list(s.test)]
    variants = {
        "nansum over 26 areas": seg.sum(axis=1, skipna=True),
        "excluding Puttalam (the only area with a NaN)": seg.drop(columns="Puttalam").sum(axis=1),
    }
    nan_rows = [int(g.index.get_loc(i)) for i in seg.index[seg.isna().any(axis=1)]]
    print(f"  NaN rows in test window: {nan_rows}")
    for label, tot in variants.items():
        roll = tot.rolling(CASE_WEEKS).sum().dropna()
        end = roll.idxmax()
        end_row = int(g.index.get_loc(end))
        start_row = end_row - CASE_WEEKS + 1
        runner = roll.drop(end).max()
        print(f"  case study ({label}): rows {start_row}-{end_row}, {day(g.index[start_row])} -> {day(end)} "
              f"(week of {day(end)} ends {day(end + pd.Timedelta(days=6))}); total {roll.max():.0f}; "
              f"next-best window total {runner:.0f}")
        # Windows that contain a NaN cell, for transparency.
        contains = [r for r in nan_rows if start_row <= r <= end_row]
        print(f"    window contains NaN rows: {contains}")


def main() -> int:
    print(f"Sri Lanka data SHA-256 {sha256(DATA_PATH)}")
    print(f"ILINet snapshot SHA-256 {sha256(ILINET_PATH)}")
    facts = {}
    for ds in DATASETS:
        g = load_grid(ds)
        facts[ds] = splits_and_post_release(ds, g)
        if ds == "srilanka":
            print("\n  Shock (Sri Lanka only):")
            shock(g)
            print("\n  Case study (Sri Lanka only):")
            case_study(g)
    bad = {k: (facts["srilanka"][k], v) for k, v in EXPECTED_SL.items() if facts["srilanka"][k] != v}
    if bad:
        print(f"\nSTOP: Sri Lankan facts differ from expected (got, expected): {bad}")
        return 1
    print("\nSri Lankan test window and post-release counts match the expected values.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
