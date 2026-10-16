# Sri Lankan dengue data audit

All figures below are **verified**: produced on 2026-10-16 by running `daqa.data`
(`load_srilanka`, `to_grid`, `validate`, `make_splits`, `area_scale`) on
`data/srilanka_weekly_data.rda` (denguedatahub commit `86d8070`,
SHA-256 `685bc277d8ed8c317c4c2390ec12033a9a5005b8a68147905c349d5cc273d7b1`).
`validate()` passes on this file. Chronology comes from `start.date` only.

## Shape and coverage

| Item | Value |
|---|---|
| Raw rows | 26,311 (columns `year, week, start.date, end.date, district, cases`) |
| Grid | 1,012 weeks × 26 areas, float |
| First week | start 2006-12-23 (end 2006-12-29) |
| Last week | start 2026-05-11 (end 2026-05-17) |
| Duplicate (area, start.date) | 0 |
| Missing `cases` values in raw rows | 0 |
| Negative counts | 0 |
| Non-integer counts | 0 |
| Area-weeks absent from raw table | 1: **Puttalam, 2026-02-09** (grid index 998), kept as NaN |
| Zero counts, whole series | 3,636 (matches the proposal's preliminary figure) |

Every start date carries exactly one (`year`, `week`, `end.date`) triple across areas.

## Areas (26)

Ampara, Anuradhapura, Badulla, Batticaloa, Colombo, Galle, Gampaha, Hambanthota,
Jaffna, Kalmune, Kalutara, Kandy, Kegalle, Kilinochchi, Kurunegala, Mannar,
Matale, Matara, Monaragala, Mullaitivu, NuwaraEliya, Polonnaruwa, Puttalam,
Ratnapura, Trincomalee, Vavuniya.

The 25 districts plus Kalmunai, which the source spells "Kalmune". Other source
spellings are "Hambanthota" and "NuwaraEliya". There are no case or whitespace
variants, and each name maps to a single series.

## Week-label irregularities (all verified)

The `year`/`week` columns are not a reliable clock. The pipeline never uses
them for ordering or features.

1. **2026 week 53 is dated 2025-12-20** (to 2025-12-26). It precedes 2026 week 1
   (2025-12-29), so sorting by (year, week) misorders it.
2. **2024 and 2025 labels are shifted by one.** Label-year 2023 has only 51
   weeks (last: w51 = 2023-12-16). As a result, 2024 w1 = 2023-12-23 and
   2025 w1 = 2024-12-21, one week earlier than the Saturday-start convention of
   2007–2023, where w1 is the week containing 1 January. The one earlier
   exception is 2010: its 1 January falls in the row labelled 2009 w53
   (2009-12-26 to 2010-01-01), and 2010 w1 starts 2010-01-02.
3. **Weeks start on Monday from 2026.** Through 2025-12-20 every week starts on
   Saturday, apart from 2009 (below). From 2025-12-29 every week starts on
   Monday (19 weeks in 2026 plus 2025-12-29). The switch leaves a 9-day
   start-to-start gap, so **2025-12-27 and 2025-12-28 belong to no week**.
4. **2009 irregular boundaries.** No week is missing; the boundaries are odd:
   - 2009 w17: 2009-04-18 to 04-25 (8 days)
   - 2009 w18–w22: start on Sunday (04-26 to 05-24), the first gap being 8 days
   - 2009 w22: 2009-05-24 to 05-29 (6 days)
   - 2009 w23 (05-30) is back to Saturday, after a 6-day gap
5. The other week-53 rows (2009-12-26, 2016-12-24, 2021-12-25) start in their
   label year.

Start-to-start gaps: 1,008 × 7 days, one each of 6, 8 and 9 days. Week lengths
(end − start): 1,010 × 6 days, one 7 (2009 w17), one 5 (2009 w22).

*Assumed / not yet checked:* whether `cases` means report week or onset week,
and how the Epidemiology Unit itself defines week 53. Implication for later
work: the grid has one row per reporting week, so a "52-week lag" taken as 52
rows back is not always exactly 364 days across the irregular weeks above.

## Splits (`make_splits(1012, max_h=4)`)

The splits count back from the final week. The last test issue is n−1−4 = 1007,
so every h = 4 target exists. All six (h, d) cells use the same origins.

| Segment | Index range | Weeks | Issue dates (start.date) |
|---|---|---|---|
| Scaling | 0–799 | 800 | 2006-12-23 → 2022-04-16 |
| Warm-up | 800–851 | 52 | 2022-04-23 → 2023-04-15 |
| Validation | 852–903 | 52 | 2023-04-22 → 2024-04-13 |
| Test | 904–1007 | 104 | 2024-04-20 → 2026-04-13 |

- Test targets: h=1 2024-04-27 → 2026-04-20; h=4 2024-05-18 → 2026-05-11.
- Indices 1008–1011 serve only as targets, never as issues.
- Weeks after the Chronos-Bolt release (2024-11-26): 72 test issues, 73 h=1
  targets and 76 h=4 targets. This is consistent with the proposal's "about 76
  of 104".
- The Puttalam NaN (2026-02-09) falls in the test window. It is excluded from
  scoring and updating for every method.
- All 104 COVID weeks (2020–21) are in the scaling segment and are included in s(i).

## Zero counts and scale in the test window (issue weeks 904–1007)

Zero % = zeros / observed weeks. Puttalam has 103 observed weeks because of the NaN.
s(i) = max(1, mean over the scaling segment); no area hits the floor of 1.

| Area | Zeros | Observed | Zero % | Zeros (whole series) | s(i) |
|---|---|---|---|---|---|
| Mullaitivu | 27 | 104 | 26.0 | 539 | 1.48 |
| Kilinochchi | 27 | 104 | 26.0 | 485 | 2.06 |
| Vavuniya | 24 | 104 | 23.1 | 330 | 6.28 |
| Mannar | 9 | 104 | 8.7 | 411 | 3.54 |
| Ampara | 8 | 104 | 7.7 | 335 | 3.36 |
| NuwaraEliya | 1 | 104 | 1.0 | 149 | 4.78 |
| Kalmune | 1 | 104 | 1.0 | 200 | 14.90 |
| Anuradhapura | 1 | 104 | 1.0 | 69 | 11.19 |
| Badulla | 0 | 104 | 0.0 | 61 | 15.22 |
| Batticaloa | 0 | 104 | 0.0 | 74 | 32.85 |
| Colombo | 0 | 104 | 0.0 | 5 | 170.96 |
| Galle | 0 | 104 | 0.0 | 64 | 27.84 |
| Gampaha | 0 | 104 | 0.0 | 17 | 98.45 |
| Hambanthota | 0 | 104 | 0.0 | 61 | 14.61 |
| Jaffna | 0 | 104 | 0.0 | 145 | 39.27 |
| Kalutara | 0 | 104 | 0.0 | 16 | 45.54 |
| Kandy | 0 | 104 | 0.0 | 14 | 59.02 |
| Kegalle | 0 | 104 | 0.0 | 14 | 32.73 |
| Kurunegala | 0 | 104 | 0.0 | 7 | 41.81 |
| Matale | 0 | 104 | 0.0 | 55 | 15.38 |
| Matara | 0 | 104 | 0.0 | 37 | 25.08 |
| Monaragala | 0 | 104 | 0.0 | 173 | 8.93 |
| Polonnaruwa | 0 | 104 | 0.0 | 157 | 5.86 |
| Puttalam | 0 | 103 | 0.0 | 58 | 24.17 |
| Ratnapura | 0 | 104 | 0.0 | 12 | 35.53 |
| Trincomalee | 0 | 104 | 0.0 | 148 | 17.72 |

Test-window total: 98 zeros out of 2,703 observed area-weeks (3.6%). The zeros
concentrate in three Northern Province areas (Mullaitivu, Kilinochchi,
Vavuniya). Mannar (Northern) and Ampara (Eastern) are smaller pockets.
