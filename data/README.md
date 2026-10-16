# data/

## srilanka_weekly_data.rda

- **Source**: `srilanka_weekly_data` table from the `denguedatahub` package repository.
- **URL**: https://raw.githubusercontent.com/thiyangt/denguedatahub/86d8070/data/srilanka_weekly_data.rda
- **Pinned commit**: `86d8070`
- **Downloaded**: 2026-10-16
- **SHA-256**: `685bc277d8ed8c317c4c2390ec12033a9a5005b8a68147905c349d5cc273d7b1`

This file is never modified. Verification is performed read-only by `src/check_data.py`.

### Verified figures (from `src/check_data.py`, run 2026-10-16)

- Shape: 26,311 rows x 6 columns
- Columns: `year`, `week`, `start.date`, `end.date`, `district`, `cases`
- First row (by actual calendar date): year=2006, week=52, date=2006-12-23
- Last row (by actual calendar date): year=2026, week=20, date=2026-05-11
- Number of districts: 26
- Rows per year:
  - 2023: 1,326
  - 2024: 1,352
  - 2025: 1,352
  - 2026: 545
- Most common row count per district: 1,012
- District with a differing row count: **Puttalam — 1,011** (one fewer than the most common count)

### Known data quirk — year-end "week 53" rows

Four rows carry `week=53` with a `year` value that does not match their actual
calendar date, e.g. the row with `year=2026, week=53` has `start.date=2025-12-20`,
which chronologically precedes `year=2026, week=1`. Sorting by `(year, week)`
therefore misorders rows at year boundaries; `check_data.py` sorts by the parsed
`start.date` instead to find the true first/last rows. This matches the
proposal's note (Section 5.2) that irregular week boundaries at year ends need
verification. **Status: verified against the pinned commit; not yet reconciled
against the Epidemiology Unit's own week-53 convention.**

## ilinet_snapshot_20261016.json (+ .csv)

One declared snapshot of U.S. ILINet weighted ILI (wILI) for the 10 HHS
regions, used only for the minimal transfer validation (proposal 5.2). This is
the only ILINet download; the file is never modified or re-fetched.

- **Source**: Delphi Epidata `fluview` endpoint (legacy v3 API, documented at
  https://cmu-delphi.github.io/delphi-epidata/api/fluview.html). Neither
  `issues` nor `lag` was passed, so each row is the *current* (most recent)
  value — no historical vintages.
- **Exact URL**:
  `https://api.delphi.cmu.edu/epidata/fluview/?regions=hhs1,hhs2,hhs3,hhs4,hhs5,hhs6,hhs7,hhs8,hhs9,hhs10&epiweeks=201040-202652`
  (single GET with curl, no auth; the upper bound 202652 is just past "today"
  so the response ends at the latest available epiweek)
- **Downloaded (UTC)**: 2026-10-16T07:47:50Z – 07:47:56Z (server `Date`
  header: Fri, 16 Oct 2026 07:47:55 GMT); HTTP 200, 2,248,205 bytes,
  `"result": 1, "message": "success"` (not truncated)
- **SHA-256 (JSON, byte-identical to the response body)**:
  `4d860a6139851af203739cabdf7e50d69ca79de2cb31c95cbaf712b939b6991d`
- **Tidy CSV**: `ilinet_snapshot_20261016.csv`, derived from the JSON by
  `src/check_ilinet.py`; columns `region, epiweek, wili, num_ili,
  num_patients, release_date, issue, lag`; 8,350 rows, ordered by
  (epiweek, region). The JSON is the source of truth.

### Verified figures (from `src/check_ilinet.py`, run 2026-10-16)

- Epiweeks 201040 .. 202639 (week starts 2010-10-03 .. 2026-09-27; CDC/MMWR
  weeks run Sunday to Saturday)
- **Latest epiweek: 202639; its issue: 202639** (lag 0), release_date
  2026-10-09. Max issue in the file: 202639.
- Rows per region: **835** for each of hhs1 .. hhs10 (8,350 total)
- Missing epiweeks per region: **0** for each of hhs1 .. hhs10 (checked
  against every Sunday from 2010-10-03 to 2026-09-27, including the 53-week
  years 2014 and 2020); null `wili`: 0 in every region
- wILI range: 0.0474986 .. 13.5865

### Note — `issue`/`lag` here are the latest revision, not first release

Because no vintages were requested, `issue` is the issue of each value's most
recent revision. The snapshot holds only 10 distinct issues: 201740 (covers
201040–201639, lag up to 365), then one issue per season at about week 39 of
the following year (201839, 201939, …, 202538), and 202639 for 202440–202639.
These columns therefore do **not** give the release that *first* reported week
`t`, which proposal 5.2 uses to align issue `t`. Consistent with 5.2, the
snapshot tests delayed availability only and supports no revision claim.
**Status: verified (counts above); how first-release timing is aligned is
for the timing layer to settle.**
