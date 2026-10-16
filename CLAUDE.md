# DAQA

Final-year dissertation project. Full spec is `docs/Supervisor Proposal Final 10.docx` — **the proposal is the spec**. If anything here and the proposal disagree, the proposal wins; flag the conflict instead of silently picking one.

## Project

DAQA: a shared, context-conditioned, affine online correction of a frozen foundation forecaster's complete native quantile vector, for district-level dengue forecasting in Sri Lanka, with a minimal transfer check on U.S. ILINet.

- Base forecaster: **amazon/chronos-bolt-small**, frozen. Native quantiles 0.1–0.9 (nine levels, step 0.1).
- Horizon `h ∈ {1, 4}`, additional reporting delay `d ∈ {0, 2, 4}` → 6 cells per dataset.
- Primary endpoint: paired DAQA − MultiQT difference in native WIS (weighted interval score).
- Mandatory baseline: MultiQT (Ding, Gibbs and Tibshirani, 2025). DECIDED: own implementation with exact parity against the authors' multiQT() at a pinned commit (implementation deviation, method unchanged; supervisor to be informed by email). Do not copy authors' code into this repo.
- Other comparators: seasonal naive, frozen Chronos-Bolt, frozen + calibration, MultiQT + calibration, shared centre-only correction (+ calibration), DAQA (+ calibration).
- Primary data: `srilanka_weekly_data` from the `denguedatahub` repo, pinned commit `86d8070`.
- Secondary data: US ILINet (HHS regional wILI), minimal-depth transfer validation only.

## Rules

- **Never fine-tune Chronos.** It stays frozen throughout; all learning happens in the adapter/correction layer around it.
- **No future-label leakage, ever.** A label for target week `s+h` is legally usable only from issue `s+h+d` onward. Nothing at issue `t` may use information from after `t − d`. The future-label perturbation test (Section 5.6 of the proposal) must pass after every code change touching chronology, features, or state updates.
- **Chronological splits only.** No shuffled train/val/test splits, no k-fold over time, no random holdout. Splits count backward from the final week (test / validation / warm-up / scaling history) per Section 5.2.
- **The proposal is the spec.** Don't invent methodology, metrics, or comparators not in it.
- **Never change scope without asking.** If a change seems to require touching anything in the "never reduced" list (Sri Lankan primary endpoint, MultiQT, centre-only ablation, shared DAQA, chronology/perturbation tests, bootstrap, downside analysis, dissertation) or adding methods/analyses not in the proposal, stop and ask first. Pre-declared contingency reductions (Section 5.11) are the only pre-approved scope cuts, applied in their stated order.
- **Label all work as verified / assumed / done.** Every claim about data, results, or code behavior gets one of these tags so it's clear what's been checked versus what's presumed.
- **Never claim code works without test output.** Don't say something passes, works, or is correct unless you've actually run it and can show the output. Paste or summarize real output, not expected output.
- **Time features from `start.date` only.** Index, 52-week lag, and seasonal phase are built only from `start.date`, never from the `year`/`week` columns (verified: 2024-2025 week labels are shifted by one; 2026 weeks start Monday).
- **Missing weeks stay NaN, never 0.** A missing target is excluded from scoring and updating for every method alike (proposal 5.2).
- **No test-period score before the protocol is committed and hashed.** All tuning uses pre-test data only (5.6).
- **Area scale `s(i)` uses pre-test data only.** The issued forecast is the rearranged (sorted) quantile vector (5.4).
- **MultiQT delay `D = h - 1 + d`**, built from the same release queue as DAQA (5.5).
- Issued quantiles are clipped at 0 after rearrangement, for every method.
- Test origins end at T-4 (every h=4 target exists); the same 104 origins are used for all six cells.
- COVID weeks (2020-21) are included in s(i).
- Seasonal naive = value 52 grid rows earlier (verified: 364 or 366 days in the test window); seasonal phase = sin/cos of target start.date day-of-year / 365.25.
- ILINet issue t = the FluView release that first reports epiweek t (proposal 5.2); the snapshot holds final revised values, so revision effects are a disclosed limitation. The timing layer treats both datasets identically on their own weekly grids.
- Update the Status section at the end of every task.

## Layout

```
data/       pinned raw datasets + their README/provenance notes
src/        pipeline code (data loading, caching, DAQA, comparators, metrics)
tests/      chronology / leakage / parity / unit tests
protocol/   the pre-registered, hashed protocol file and any protocol-adjacent artifacts
docs/       proposal, write-ups, generated figures/tables
```

## Environment

- Windows. Python virtual environment lives in `.venv` (created with the system Python, not conda).
- Install/run via the venv's `python`/`pip`, not a global interpreter.
- Remote: `origin` → https://github.com/theNisith/daqa-fyp.git, default branch `main`, pushed and up to date.

## Status (update this section as work progresses)

Done / verified:
- `data/srilanka_weekly_data.rda` downloaded and pinned at commit `86d8070`; SHA-256, shape, and per-year/per-district counts verified by `src/check_data.py` (dates parsed with `format="%m/%d/%Y"` from `start.date`, never from `year`/`week` — see the known week-53 quirk noted in `data/README.md`).
- `amazon/chronos-bolt-small` smoke-tested on CPU, frozen, inference-only (`src/smoke_chronos.py`): returns valid shape `(1, 8, 9)` native quantiles, non-decreasing, no negatives, no NaNs in output — for both a clean context (Colombo) and a context containing one real missing week (Puttalam, NaN at 2026-02-09). "No negatives" was only checked for Colombo and Puttalam; low-count areas are untested. Chronos-Bolt accepted the NaN context without raising. Verified from chronos-forecasting v2.3.2 source (src/chronos/chronos_bolt.py lines 111-112, 284-307): NaN is masked out of the context, scaling uses nanmean, and the observed-mask is passed to the model. Policy: missing weeks enter the context as NaN.
- `requirements.txt` pinned via `pip freeze` (pandas, pyreadr, pytest, chronos-forecasting, torch, transformers, etc.).
- Data layer `src/daqa/data.py`: `load_srilanka`, `to_grid` (1012 × 26, float, Puttalam 2026-02-09 stays NaN), `validate`, `make_splits` (scaling 0–799 / warm-up 800–851 / validation 852–903 / test 904–1007; test issues 2024-04-20 → 2026-04-13), `area_scale` (no area hits the floor of 1). `tests/test_data.py`: 26 passed (`python -m pytest`, `pytest.ini` sets `pythonpath = src`). Full audit, including week-label irregularities and test-window zero counts, in `data/AUDIT.md`.
- ILINet snapshot `data/ilinet_snapshot_20261016.json` (one declared snapshot, current values only, no vintages): Delphi `fluview`, hhs1..hhs10, epiweeks 201040–202639, downloaded 2026-10-16T07:47Z, SHA-256 `4d860a61…991d`. 835 rows per region, 0 missing epiweeks, 0 null wILI; latest epiweek 202639 = issue 202639 (released 2026-10-09). Tidy CSV + audit via `src/check_ilinet.py`; URL, hash and counts in `data/README.md`. `load_ilinet()` returns the 835 × 10 (Sunday epiweek start × region) wILI grid, NaN for missing weeks (never filled); `epiweek_start()` implements MMWR weeks. `tests/test_ilinet.py`: 19 passed; full suite 45 passed.
- Seasonal-naive 52-row lag checked on the Sri Lankan grid: rows 904–1011 span 364 days (88 rows) or 366 days (20 rows, all 2026 Monday-start weeks).
- Timing layer `src/daqa/timing.py` (grid-position indices, identical for both datasets): `available_context` (last ≤104 values with index ≤ t−d, NaN kept, shorter if history is short, never padded, returns a copy), `step_index` = h+d, `first_usable_issue` = s+h+d, `multiqt_delay` D = h−1+d, `matured_at` (s+h+d == t), `matured_up_to` (s+h+d ≤ t); non-study (h, d) cells raise. `tests/test_timing.py`: 53 passed — all six cells, the issue-11/h=1/d=2 example (data through 9, step 3, usable at 14), edges h+d=1 and h+d=8, each record matures exactly once and never before s+h+d, 500-case random property test (no context index > t−d; perturbing every value after t−d leaves the context unchanged). Mutation-checked: leaking one future week fails 21 tests; maturing one issue early fails 16. Full suite: 98 passed.
- `.gitattributes` (`*.json`/`*.csv -text`, `*.rda`/`*.npz`/`*.parquet binary`) committed; SHA-256 of both data files unchanged in working tree and committed blobs.
- Frozen Chronos-Bolt forecast cache (5.3), `src/daqa/cache.py` → `cache/{srilanka,ilinet}_chronos_bolt_small.npz` + `cache/MANIFEST.md` (9.3 MB, committed). Inference only, no scores. Model revision `772f3d25…46f5d8` pinned in code; CPU, float32, eval, no_grad. Issues = first warm-up … last test (Sri Lanka rows 800–1007, ILINet 623–830; 208 each) × d ∈ {0,2,4}, context `available_context(…, 104)` (all full length), 8 steps × native 0.1–0.9. Arrays (issue, area, delay, step, 9): `raw` (unclipped) and `sorted`. One request per (issue, delay) with all areas: CPU outputs depend on batch composition at ~1e-5 (measured: 3.8e-5 abs), so the fixed batch makes recomputation exact; a full rebuild reproduced identical file and array hashes. Counts: Sri Lanka 24 NaN contexts (all Puttalam), 65 of 129,792 vectors needed sorting, 21,120 negative raw quantiles (mostly Northern Province areas: Kilinochchi 5,099, Vavuniya 4,627, Mullaitivu 4,176); ILINet 0 NaN contexts, 17 of 49,920 needed sorting, 0 negatives. `tests/test_cache.py`: 13 passed (shapes/sorted non-decreasing, determinism on 20 random entries within 1e-6, future values after t−d set to 1e9 at 3 issues × 3 delays per dataset leave forecasts unchanged within 1e-6, plus a power check that a one-week leak changes them by > 1e3). Full suite: 111 passed.
- Git repo initialized and pushed to `origin/main`.

Open / not started:
- Release queue built on the timing layer + future-label perturbation test (5.6) — not written yet (timing primitives and their unit tests are done).
- MultiQT baseline implementation — not started; decided: own implementation + parity.
- Centre-only correction and DAQA adapter code (5.4) — not started.
- Interval calibration tracker (5.7), seasonal naive comparator, protocol file (not yet drafted, hashed, or committed) — not started.
- ILINet transfer validation (5.2) — snapshot in hand, no modelling yet. The snapshot's `issue`/`lag` columns (latest revision, not first release) are not needed: issue t is aligned with the release that first reports epiweek t by definition, so ILINet runs through the same timing layer on its own grid.
- Everything in Weeks 2–4 of the proposal's work plan (metrics, bootstrap, shock test, case study, offline demo, dissertation) — not started.

Assumed / open from the audit: report-week vs onset-week meaning of `cases`, and the Epidemiology Unit's own week-53 convention, are unchecked. Irregular weeks (2009 boundaries, 2025-12-27/28 uncovered by the Monday switch) mean a 52-row lag is not always exactly 364 days; decide how to handle this when building features.

Next: Step 6, MultiQT.
