"""Read-only audit of data/srilanka_weekly_data.rda. Never modifies the file."""

import hashlib
from collections import Counter
from pathlib import Path

import pandas as pd
import pyreadr

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "srilanka_weekly_data.rda"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    digest = sha256_of(DATA_PATH)
    print(f"SHA-256: {digest}")

    result = pyreadr.read_r(str(DATA_PATH))
    (df_name,) = result.keys()
    df = result[df_name]

    print(f"Object name: {df_name}")
    print(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    print(f"Columns: {list(df.columns)}")

    # Some year-end weeks (e.g. "week 53") carry a `year` value that does not
    # match their actual calendar date (a row labelled year=2026, week=53 has
    # start.date=2025-12-20). Sorting by (year, week) misorders those rows, so
    # chronology is derived from the parsed start.date instead.
    dates = pd.to_datetime(df["start.date"], format="%m/%d/%Y")
    df_sorted = df.assign(_start_date=dates).sort_values("_start_date")
    first = df_sorted.iloc[0]
    last = df_sorted.iloc[-1]
    print(f"First row: year={first['year']}, week={first['week']}, date={first['_start_date'].date()}")
    print(f"Last row: year={last['year']}, week={last['week']}, date={last['_start_date'].date()}")

    n_districts = df["district"].nunique()
    print(f"Number of districts: {n_districts}")

    print("Rows per year (2023-2026):")
    for yr in range(2023, 2027):
        count = (df["year"] == yr).sum()
        print(f"  {yr}: {count}")

    district_counts = Counter(df["district"])
    most_common_count = district_counts.most_common(1)[0][1]
    print(f"Most common row count per district: {most_common_count}")
    diffs = {d: c for d, c in district_counts.items() if c != most_common_count}
    if diffs:
        print("Districts with differing row counts:")
        for d, c in sorted(diffs.items()):
            print(f"  {d}: {c}")
    else:
        print("No district has a row count differing from the most common count.")


if __name__ == "__main__":
    main()
