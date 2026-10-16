# DAQA

Final-year dissertation project. Full spec is `docs/Supervisor Proposal Final 10.docx` — **the proposal is the spec**. If anything here and the proposal disagree, the proposal wins; flag the conflict instead of silently picking one.

## Project

DAQA: a shared, context-conditioned, affine online correction of a frozen foundation forecaster's complete native quantile vector, for district-level dengue forecasting in Sri Lanka, with a minimal transfer check on U.S. ILINet.

- Base forecaster: **amazon/chronos-bolt-small**, frozen. Native quantiles 0.1–0.9 (nine levels, step 0.1).
- Horizon `h ∈ {1, 4}`, additional reporting delay `d ∈ {0, 2, 4}` → 6 cells per dataset.
- Primary endpoint: paired DAQA − MultiQT difference in native WIS (weighted interval score).
- Mandatory baseline: **MultiQT** (Ding, Gibbs and Tibshirani, 2025): [PENDING SUPERVISOR] proposal says authors' implementation; research notes say no LICENSE, so plan is own implementation with exact parity against authors' multiQT() at a pinned commit. Do not copy authors' code into this repo.
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
