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
