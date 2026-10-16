"""Read-only audit of the ILINet snapshot JSON; writes the tidy CSV next to it.

The JSON is never modified. Run: python src/check_ilinet.py
"""

import hashlib

import pandas as pd

from daqa.data import HHS_REGIONS, ILINET_COLUMNS, ILINET_PATH, load_ilinet, load_ilinet_long

CSV_PATH = ILINET_PATH.with_suffix(".csv")


def main() -> None:
    digest = hashlib.sha256(ILINET_PATH.read_bytes()).hexdigest()
    print(f"SHA-256: {digest}")

    df = load_ilinet_long()
    out = df[ILINET_COLUMNS].assign(release_date=df["release_date"].dt.strftime("%Y-%m-%d"))
    out.to_csv(CSV_PATH, index=False, lineterminator="\n")
    print(f"Wrote {CSV_PATH.name}: {len(out)} rows x {out.shape[1]} columns")

    print(f"Epiweeks: {df['epiweek'].min()} .. {df['epiweek'].max()}")
    print(f"Start dates: {df['start_date'].min().date()} .. {df['start_date'].max().date()}")
    latest = df[df["epiweek"] == df["epiweek"].max()]
    print(f"Latest epiweek rows: issue={sorted(latest['issue'].unique())}, "
          f"release_date={sorted(latest['release_date'].dt.date.astype(str).unique())}")
    print(f"Max issue: {df['issue'].max()}, max release_date: {df['release_date'].max().date()}")
    print(f"Distinct issues: {df['issue'].nunique()}; lag range {df['lag'].min()}..{df['lag'].max()}")
    print(f"Null release_date rows: {int(df['release_date'].isna().sum())}")

    grid = load_ilinet()
    print(f"Grid: {grid.shape[0]} weeks x {grid.shape[1]} regions")
    absent = grid.index.difference(pd.DatetimeIndex(df["start_date"].unique()))
    print(f"Weeks absent for every region: {len(absent)}")
    print("region  rows  null_wili  missing_epiweeks")
    for r in HHS_REGIONS:
        sub = df[df["region"] == r]
        missing = grid.index[grid[r].isna()]
        print(f"{r:6s}  {len(sub):4d}  {int(sub['wili'].isna().sum()):9d}  {len(missing)}"
              + (f"  {[d.date().isoformat() for d in missing]}" if len(missing) else ""))
    print(f"Grid NaN cells total: {int(grid.isna().sum().sum())}")
    print(f"wili min/max: {df['wili'].min()} / {df['wili'].max()}")


if __name__ == "__main__":
    main()
