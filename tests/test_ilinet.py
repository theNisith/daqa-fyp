import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from daqa.data import (
    HHS_REGIONS,
    ILINET_COLUMNS,
    ILINET_PATH,
    ILINET_SHA256,
    epiweek_start,
    load_ilinet,
    load_ilinet_long,
)


@pytest.fixture(scope="module")
def grid():
    return load_ilinet()


def _row(region, epiweek, wili):
    return {"release_date": "2020-01-10", "region": region, "issue": epiweek, "epiweek": epiweek,
            "lag": 0, "num_ili": 1, "num_patients": 100, "wili": wili}


def _write(tmp_path, rows, result=1):
    path = tmp_path / "toy.json"
    path.write_text(json.dumps({"epidata": rows, "result": result, "message": "success"}))
    return path


# ---------- epiweek_start ----------

@pytest.mark.parametrize(
    "epiweek, start",
    [
        (201040, "2010-10-03"),
        (201453, "2014-12-28"),  # 2014 has 53 MMWR weeks
        (201501, "2015-01-04"),
        (201601, "2016-01-03"),
        (202053, "2020-12-27"),  # 2020 has 53 MMWR weeks
        (202101, "2021-01-03"),
        (202639, "2026-09-27"),
    ],
)
def test_epiweek_start_known_dates(epiweek, start):
    got = epiweek_start(epiweek)
    assert got == pd.Timestamp(start)
    assert got.day_name() == "Sunday"


@pytest.mark.parametrize("epiweek", [201553, 202100, 202154])
def test_epiweek_start_rejects_invalid(epiweek):
    with pytest.raises(ValueError):
        epiweek_start(epiweek)


# ---------- pinned snapshot ----------

def test_snapshot_hash():
    assert hashlib.sha256(ILINET_PATH.read_bytes()).hexdigest() == ILINET_SHA256


def test_grid_shape_and_index(grid):
    assert grid.shape == (835, 10)
    assert list(grid.columns) == list(HHS_REGIONS)
    assert grid.index[0] == pd.Timestamp("2010-10-03")
    assert grid.index[-1] == pd.Timestamp("2026-09-27")
    assert (grid.index.dayofweek == 6).all()  # Sunday
    assert (np.diff(grid.index.values) == np.timedelta64(7, "D")).all()
    assert grid.dtypes.eq(float).all()


def test_grid_complete_and_positive(grid):
    # Verified for this snapshot: no absent epiweek and no null wili in any region.
    assert not grid.isna().any().any()
    assert (grid > 0).all().all()


def test_grid_matches_raw_values(grid):
    df = load_ilinet_long()
    assert len(df) == 8350
    assert grid.loc["2010-10-03", "hhs1"] == 0.415796
    assert grid.loc["2026-09-27", "hhs9"] == 2.58545
    back = grid.stack().rename("wili").reset_index()
    merged = df.merge(back, left_on=["start_date", "region"], right_on=["start_date", "region"])
    assert len(merged) == len(df)
    assert (merged["wili_x"] == merged["wili_y"]).all()


def test_csv_matches_json():
    csv = pd.read_csv(ILINET_PATH.with_suffix(".csv"))
    df = load_ilinet_long()
    assert list(csv.columns) == ILINET_COLUMNS
    assert len(csv) == len(df)
    assert (csv["wili"].to_numpy() == df["wili"].to_numpy()).all()
    assert (csv["epiweek"].to_numpy() == df["epiweek"].to_numpy()).all()


# ---------- missing weeks stay NaN ----------

def test_missing_epiweek_and_null_wili_are_nan_not_filled(tmp_path):
    rows = [_row(r, ew, 1.0) for r in HHS_REGIONS for ew in (201452, 201453, 201501, 201502)]
    rows = [x for x in rows if not (x["region"] == "hhs3" and x["epiweek"] == 201453)]
    rows = [{**x, "wili": None} if (x["region"] == "hhs7" and x["epiweek"] == 201501) else x for x in rows]
    rows = [x for x in rows if not (x["region"] == "hhs10" and x["epiweek"] == 201501)]
    g = load_ilinet(_write(tmp_path, rows))
    assert list(g.index) == list(pd.date_range("2014-12-21", periods=4, freq="7D"))
    nan = {(c, d.date().isoformat()) for c in g.columns for d in g.index[g[c].isna()]}
    assert nan == {("hhs3", "2014-12-28"), ("hhs7", "2015-01-04"), ("hhs10", "2015-01-04")}
    assert int(g.notna().sum().sum()) == 40 - 3


def test_week_absent_for_all_regions_is_a_nan_row(tmp_path):
    rows = [_row(r, ew, 2.0) for r in HHS_REGIONS for ew in (202001, 202003)]
    g = load_ilinet(_write(tmp_path, rows))
    assert list(g.index) == list(pd.to_datetime(["2019-12-29", "2020-01-05", "2020-01-12"]))
    assert g.loc["2020-01-05"].isna().all()  # epiweek 202002, absent everywhere
    assert g.drop(pd.Timestamp("2020-01-05")).notna().all().all()


def test_duplicate_rows_raise(tmp_path):
    rows = [_row(r, 202001, 1.0) for r in HHS_REGIONS] + [_row("hhs1", 202001, 2.0)]
    with pytest.raises(ValueError, match="duplicate"):
        load_ilinet(_write(tmp_path, rows))


def test_failed_result_raises(tmp_path):
    with pytest.raises(ValueError, match="result"):
        load_ilinet(_write(tmp_path, [], result=2))
