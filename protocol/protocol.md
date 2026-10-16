# DAQA pre-registered protocol — DRAFT (NOT FROZEN)

> **Status: DRAFT, not frozen, not hashed.** This file is not yet the pre-registered protocol of
> proposal 5.6. It becomes that only when every OPEN DECISION below is resolved and the file is
> committed together with its SHA-256 and a timestamp. **No test-period score exists**: nothing in
> this draft was computed from any forecast's accuracy on any segment. All data facts were produced
> by `python src/protocol_facts.py` (data only, no forecasts, no scores) and the existing test suite.
>
> Tags: **[verified]** = checked by running code in this repo (output quoted or summarised);
> **[assumed]** = a reading of the proposal not yet confirmed; **[DECIDED]** = fixed by the user;
> **[OPEN]** = must be decided before freezing; **[TODO]** = the proposal is silent and a value must
> be supplied. The proposal (`docs/Supervisor Proposal Final 10.docx`) is the spec; section numbers
> below refer to it.

## 0. OPEN DECISIONS (all must be closed before freezing)

| # | Decision | Proposal | Draft default (not binding) |
|---|---|---|---|
| O1 | The **two fixed MultiQT learning rates** on the scaled series | 5.6 | none |
| O2 | DAQA: the three (learning rate η, λ) pairs besides the identity η = 0 | 5.6 | none |
| O3 | Centre-only: the three (η, λ) pairs besides η = 0 (5.5 says its tuning protocol is identical to DAQA; same grid as O2?) | 5.5, 5.6 | same grid as DAQA |
| O4 | Tracker step γ: the three candidates shared by all methods | 5.6, 5.7 | none |
| O5 | Feature clipping bounds and transforms (5.4: "fixed in the protocol") | 5.4 | none — see §9 |
| O6 | Feature rule when a legal observation used by x₂–x₄ is NaN (only Puttalam row 998 in the Sri Lankan data) | 5.2, 5.4 | none — see §9 |
| O7 | Exact reading of the "3-week legal change" (y_ℓ − y_ℓ₋₃ assumed) and of the phase formula (day-of-year convention) | 5.4 | see §9 |
| O8 | Eligibility rule for areas | 5.4, 5.6, 5.9 | all 26 Sri Lankan areas and all 10 HHS regions eligible at every issue; a record leaves an update or score only when its target is NaN |
| O9 | Selection granularity: one candidate per method per dataset (pooled over the six cells), or one per method per cell | 5.6 | one per method per dataset, criterion pooled exactly like the primary endpoint |
| O10 | Which validation records are scored for selection: "targets released before the first test issue" read as s + h + d ≤ test.start − 1 | 5.6 | as stated (51/49/47 issues for h=1, d=0/2/4; 48/46/44 for h=4) |
| O11 | Tie-break in selection | 5.6 | identity first, then the smaller learning rate, then the smaller λ |
| O12 | How one shared γ is selected from four calibrated methods (pooled validation 95 % interval score across Frozen, MultiQT, Centre, DAQA?) | 5.6, 5.7 | pooled mean over the four methods |
| O13 | Tracker start and r₀: when the tracker starts, which warm-up scores enter r₀, and the percentile definition | 5.7 | start at the first validation issue; r₀ from warm-up records matured by then; percentile method TODO |
| O14 | Seasonal naive: residual window, per-cell legality and quantile definition | 5.5 | residuals y_r − y_{r−52} for every pre-test target r legal before the first test issue; quantile method TODO |
| O15 | Bootstrap confidence-interval construction (percentile 95 % assumed) | 5.8 | percentile 2.5 / 97.5 % |
| O16 | Within-endpoint averaging order (mean over issues within area → areas → cells, as written in §13) | 5.8 | as written |
| O17 | Shock start: "first week of the second test year" read as test week 53 (row 956) | 5.9 | as written in §16 |
| O18 | Protocol hash procedure (which file bytes are hashed, where the hash is recorded) | 5.6 | SHA-256 of this file's committed bytes, recorded in `protocol/PROTOCOL.sha256` in the freezing commit |

Pre-existing items carried as disclosed unknowns, not protocol decisions: report-week vs onset-week
meaning of `cases`, and the Epidemiology Unit's own week-53 convention [assumed / unchecked,
`data/AUDIT.md`].

## 1. Data (5.2)

**Sri Lanka (primary)** [verified]
- Source: `srilanka_weekly_data` from the `denguedatahub` repository, pinned commit `86d8070`,
  file `data/srilanka_weekly_data.rda`.
- SHA-256 `685bc277d8ed8c317c4c2390ec12033a9a5005b8a68147905c349d5cc273d7b1`.
- 26,311 raw rows; grid 1,012 weeks × 26 areas (25 districts + Kalmunai, spelled "Kalmune");
  2006-12-23 → 2026-05-11 (week starts). One absent area-week: Puttalam 2026-02-09 (row 998), kept
  as NaN. Full audit: `data/AUDIT.md`.

**ILINet (minimal transfer validation)** [verified]
- One declared snapshot `data/ilinet_snapshot_20261016.json`: Delphi Epidata `fluview`, HHS regions
  hhs1–hhs10, epiweeks 201040–202639, downloaded 2026-10-16T07:47Z.
- SHA-256 `4d860a6139851af203739cabdf7e50d69ca79de2cb31c95cbaf712b939b6991d`.
- Grid 835 weeks × 10 regions (Sunday epiweek starts), 0 missing epiweeks, 0 null wILI.
- Issue t = the FluView release that first reports epiweek t (5.2). The snapshot holds revised
  values, so ILINet tests delayed availability only; revision effects are a disclosed limitation.

## 2. Date and missing-data rules (5.2)

- **Chronology from `start.date` only** [DECIDED, verified]. Grid order, index, 52-row lag and
  seasonal phase are built from `start.date` (ILINet: MMWR epiweek Sunday start), never from the
  `year`/`week` columns (2024–25 labels are shifted by one; 2026 weeks start on Monday; 2025-12-27/28
  belong to no week; see `data/AUDIT.md`).
- **A missing week stays NaN, never 0** [DECIDED]. It enters Chronos-Bolt contexts as NaN (§6).
- **A missing target is excluded from scoring and from updating, for every method alike** (5.2).
  Verified for MultiQT: Puttalam has exactly 1 skipped update per cell (6 cells), every other area
  and every ILINet region 0.

## 3. Splits (5.2)

Counting back from the final week; the last test issue is T − 4 so every h = 4 target exists.
Identical for all six (h, d) cells [verified, `python src/protocol_facts.py`]:

| Segment | Sri Lanka rows | Sri Lanka dates (week start) | ILINet rows | ILINet dates (epiweek start) |
|---|---|---|---|---|
| Scaling | 0–795 (796) | 2006-12-23 → 2022-03-19 | 0–618 (619) | 2010-10-03 → 2022-08-07 |
| Gap (history only, no segment) | 796–799 (4) | 2022-03-26 → 2022-04-16 | 619–622 (4) | 2022-08-14 → 2022-09-04 |
| Warm-up | 800–851 (52) | 2022-04-23 → 2023-04-15 | 623–674 (52) | 2022-09-11 → 2023-09-03 |
| Validation | 852–903 (52) | 2023-04-22 → 2024-04-13 | 675–726 (52) | 2023-09-10 → 2024-09-01 |
| Test | 904–1007 (104) | 2024-04-20 → 2026-04-13 | 727–830 (104) | 2024-09-08 → 2026-08-30 |

Rows 1008–1011 (Sri Lanka) and 831–834 (ILINet) serve only as targets.

**Scaling-segment correction** [DECIDED]: the scaling segment ends max(d) = 4 rows before the first
warm-up issue. Reason: the future-label perturbation test (5.6) found that, with scaling rows
0..warmup.start − 1, s(i) used rows later than t − d at the first warm-up issues when d > 0
(Sri Lanka issue 800, d = 4: rows 797–799; ILINet issue 623: rows 620–622). This was a pre-test
correction; no score of any kind existed. The cut is **one row more conservative than strictly
needed**: at issue 800 with d = 4 the latest legal row is 796, so ending at 796 would already have
been legal; the protocol ends at 795 (warmup.start − 1 − max(d)). Proposal 5.2 requires "at least
104 earlier weeks for scaling and history", which 796 / 619 rows meet, so this is likely not a
formal deviation; the 4-row gap is nevertheless disclosed as a deviation from the proposal's split
description. Implemented once in `make_splits` (`SCALING_GAP = max(DELAYS)`); tested by
`test_scale_unchanged_by_future_perturbation_at_first_warmup_issue` (2 datasets × 3 delays).

**COVID weeks (2020–21)** are inside the scaling segment and are included in s(i) [DECIDED, verified].

## 4. Test window and post-release subset (5.2, 5.8, 5.9)

- **Test window = the 104 test ISSUE weeks** [DECIDED for this draft by the user's instruction;
  verified]: Sri Lanka 2024-04-20 → 2026-04-13 (rows 904–1007); ILINet 2024-09-08 → 2026-08-30
  (rows 727–830). The same 104 origins are used for all six cells [DECIDED].
- **Post-release** = TARGET week start date after 2024-11-26 (the chronos-bolt-small release, 5.9)
  [verified]:

| | Sri Lanka | ILINet |
|---|---|---|
| Issue weeks after 2024-11-26 | 72 | 92 |
| h = 1 targets after 2024-11-26 | 73 (from target 2024-11-30) | 93 (from 2024-12-01) |
| h = 4 targets after 2024-11-26 | 76 (from target 2024-11-30) | 96 (from 2024-12-01) |

The Sri Lankan counts match the expected 72 / 73 / 76 (the script stops otherwise). The pre/post
split of the primary contrast is descriptive only (5.8).

## 5. Area scale (5.2, 5.4)

s(i) = max(1, mean of area i's observed counts over the scaling segment), NaN skipped, computed once
from pre-test data only (`daqa.data.area_scale`). No area or region is at the floor of 1 [verified]:
Sri Lanka min 1.4824 (Mullaitivu), max 171.7399 (Colombo); ILINet min 1.1644 (hhs10), max 3.0163
(hhs6). Per-area values: `data/AUDIT.md`. Every method uses this same s(i), and every scaled update
signal and the primary endpoint divide by it.

## 6. Base forecaster, context and cache (5.3)

- Model `amazon/chronos-bolt-small`, **frozen**, inference only, never fine-tuned; Hugging Face
  revision `772f3d25d38aec6d914c8949dab4462e2d46f5d8`; `model.safetensors` SHA-256
  `06a6a19bbe74bc10a9cd193bd4bf2bf638ae07f7e0d51653ae7ab8ea968a21dd`. CPU, float32, eval mode,
  `torch.no_grad`, all `requires_grad=False` [verified, `cache/MANIFEST.md`].
- **Context rule**: at issue t with delay d, the last ≤ 104 grid values with index ≤ t − d, never
  padded, NaN kept (`timing.available_context`). A NaN enters Chronos-Bolt as missing: in
  chronos-forecasting **v2.3.2** `src/chronos/chronos_bolt.py`, lines 111–112 compute the instance
  normalisation with `nanmean`, and lines 284–307 build the observed-mask from `isnan`, zero the
  masked values and pass the mask and attention mask to the model [verified by reading the installed
  source]. All warm-up…test contexts have the full 104 values; 24 Sri Lankan contexts contain a NaN
  (all Puttalam), ILINet 0.
- One request of 8 steps × native quantiles 0.1–0.9 per (area, issue, delay) serves both horizons;
  b ∈ ℝ⁹ is the step-(h + d) vector, **sorted once** before any method sees it (5.3). 65 of 129,792
  Sri Lankan and 17 of 49,920 ILINet vectors needed sorting.
- **Cache**: `cache/srilanka_chronos_bolt_small.npz` SHA-256
  `353d26c84b8486508776c6c1457915eaedad3abcca27be1f79e62415996dfbbc`;
  `cache/ilinet_chronos_bolt_small.npz` SHA-256
  `01f2860edaced5a995f66e42d28a318db5a7ca8232b6f8aadf74a333efadc8a0`. Issues = first warm-up … last
  test (208 per dataset) × d ∈ {0, 2, 4}. Raw quantiles are stored unclipped.
- **Fixed batch per (issue, delay)**: each request contains all areas in grid column order. Reason:
  on CPU, the same context forecast inside a different batch moves outputs by float32 noise (measured
  max 3.8e-5 absolute), while an identical batch is bitwise reproducible; fixing the batch makes every
  recomputation exact (a full rebuild reproduced identical file and array hashes) [verified].

## 7. Timing definitions (5.1)

On each dataset's own grid, identically [verified, `tests/test_timing.py`, 53 tests]:
- At issue t the latest legal observation is ℓ = t − d; the target is t + h, requested as step h + d.
- A label for target s + h is usable from issue s + h + d onward; the record issued at s matures at
  exactly s + h + d (`matured_at`), never earlier.
- MultiQT delay D = h − 1 + d [DECIDED]; its first use s + D + 1 equals s + h + d. The MultiQT delay
  schedule is built from the same release queue as DAQA (5.5).
- At every issue the order is: (1) apply updates from records maturing at t, (2) issue the forecast
  for t from the updated state [verified for MultiQT; same rule for every online method].
- All online methods start from their identity state at the first warm-up issue and run continuously
  through validation and test, with no reset and no retuning [assumed from 5.6; part of O8/O9 review].

| h | d | distance h + d | MultiQT D | first update from issue s |
|---|---|---|---|---|
| 1 | 0 | 1 | 0 | s + 1 |
| 1 | 2 | 3 | 2 | s + 3 |
| 1 | 4 | 5 | 4 | s + 5 |
| 4 | 0 | 4 | 3 | s + 4 |
| 4 | 2 | 6 | 5 | s + 6 |
| 4 | 4 | 8 | 7 | s + 8 |

## 8. Methods (5.4, 5.5, 5.7)

Complexity ladder order (5.8): seasonal naive, frozen, frozen + tracker, MultiQT, centre-only, DAQA;
plus MultiQT + calibration, centre-only + calibration, DAQA + calibration (nine comparators).
No other model, baseline or analysis is added.

- **Seasonal naive** (5.5): centre m = y_{t+h−52} (52 grid rows before the target [DECIDED]; legal
  since h + d ≤ 52; 364 or 366 days in the Sri Lankan test window [verified]), plus fixed per-area
  residual quantiles from pre-test matured residuals. [OPEN O14: residual window and quantile rule.]
- **Frozen**: issued = max(0, b) (b already sorted).
- **MultiQT** (5.5) [DECIDED: own implementation with exact parity against the authors' `multiQT()`
  at commit `3300f75c5cedb7f888af4058032a94940b682ccb`; an implementation deviation, method
  unchanged; the authors' repo has no licence and nothing is copied]. Per series and cell, θ ∈ ℝ⁹ on
  y/s(i); played q = isotonic projection of (b/s + θ); update θ_k ← θ_k − η(1{y/s ≤ q_k} − τ_k) when the
  record matures. Exact parity (`assert_array_equal`) verified on 3 random streams × D ∈ {0, 3, 7} ×
  η ∈ {0.05, 0.5, adaptive+}. **Adaptive+ window** [DECIDED]: the authors' code, i.e. the last
  min(n_obs, 50 − D) observed residuals, η = max(0.1, 0.1·Q₀.₉(|y − b|)) on the scaled series; the
  paper ("50 time steps") is silent on delay, which is disclosed.
- **Shared centre-only correction** (5.5): z = b/s + (wᵀx)·1₉, w ∈ ℝ⁸, one w per cell shared across
  eligible areas, w₀ = 0. Scaling, context, matured records, per-cell sharing, batched update,
  nine-level pinball loss and tuning protocol identical to DAQA.
- **Shared DAQA** (5.4): z(i,t) = b(i,t)/s(i) + W_{(h,d)} x(i,t), W ∈ ℝ^{9×8}, one W per cell (six,
  432 coefficients), W₀ = 0 (reproduces Frozen exactly). Order-invariant delayed update over the
  matured set M_t (one record per eligible area, issued at t − h − d, NaN targets removed):
  L_t(W) = (1/|M_t|) Σ_{r∈M_t} (1/9) Σ_k ρ_{τ_k}(y_r/s_r − z_{r,k}(W)) + λ‖W‖²_F, ρ_τ(u) = u(τ − 1{u<0}),
  τ_k = k/10, using the cached issue-time x_r and b_r. One subgradient step W ← W − η G_t with
  G_t = (1/|M_t|) Σ_r (1/9) g_r x_rᵀ + 2λW, g_{r,k} = 1{y_r/s_r < z_{r,k}} − τ_k (the subgradient implied
  by the indicator in ρ). If M_t has no observed record, W is unchanged. Centre-only uses the same
  step with the gradient summed over k into the scalar shift.
- **Calibration / tracker** (5.7): l = q₀.₁, u = q₀.₉ of the issued vector; a = max(l − y, y − u, 0)/s(i);
  C = [l − s(i) r, u + s(i) r]; r ← max(0, r + γ(e − 0.05)) only when the archived interval's outcome
  legally matures; separate state per method, area and cell; γ shared by all methods. r₀ = empirical
  95th percentile of the pre-test warm-up conformity scores per state, legal data only. [OPEN O4, O12,
  O13.] Native 0.025/0.975 quantiles are never invented.

## 9. Context features x(i,t) ∈ ℝ⁸ (5.4)

With ℓ = t − d, y the raw series of area i, s = s(i), and b the sorted step-(h + d) base vector
(b₁ = q₀.₁, b₅ = q₀.₅, b₉ = q₀.₉). All values are legal at issue t (indices ≤ ℓ; b depends only on the
context ≤ ℓ). Case-valued features are divided by s(i) (5.4).

| k | Feature | Formula | Clipping / transform |
|---|---|---|---|
| 1 | intercept | 1 | none |
| 2 | latest legal observation | y_ℓ / s | **TODO (O5)** |
| 3 | 4-week legal mean | (y_ℓ + y_{ℓ−1} + y_{ℓ−2} + y_{ℓ−3}) / (4 s) | **TODO (O5)** |
| 4 | 3-week legal change | (y_ℓ − y_{ℓ−3}) / s  [assumed reading, O7] | **TODO (O5)** |
| 5 | base median | b₅ / s | **TODO (O5)** |
| 6 | base outer width | (b₉ − b₁) / s | **TODO (O5)** |
| 7 | sin of target annual phase | sin(2π · doy(target start.date) / 365.25), target = row t + h | none (bounded) |
| 8 | cos of target annual phase | cos(2π · doy(target start.date) / 365.25) | none (bounded) |

doy = day of year of the target week's start date, 1..366 (pandas `dayofyear`) [assumed, O7].
Proposal silent → **TODO (O5)**: the clipping bounds for features 2–6, and whether any transform
(e.g. none vs log1p) is used. **TODO (O6)**: the rule when y_ℓ, y_{ℓ−1}, y_{ℓ−2} or y_{ℓ−3} is NaN.
In the Sri Lankan data this happens only through Puttalam row 998, i.e. at Puttalam issues with
ℓ ∈ {998, …, 1001}, all in the test window; ILINet has no NaN.

## 10. Issued forecast

For every method the issued vector is the ascending rearrangement of its raw output, scaled back by
s(i), then **clipped at 0 after rearrangement** [DECIDED]: q = max(0, s(i)·Rearrange(z)) for DAQA and
centre-only; MultiQT uses its isotonic projection (authors' method) before clipping. The issued
(sorted, clipped) vector is what is archived, scored and calibrated. Raw crossing frequency is a
diagnostic (5.4, 5.8).

## 11. Update signals [DECIDED]

- MultiQT updates on its **projected (played) vector**, as in the authors' code.
- Centre-only and DAQA pinball loss uses the **raw, unsorted z** (proposal 5.4: affine in W, so L_t is
  convex in W; no convexity is claimed for the rearranged pipeline).
- All update signals are **unclipped and on the scaled series** (y/s(i)); clipping at 0 applies only
  to issued forecasts. The tracker's conformity score a = max(l − y, y − u, 0)/s(i) uses the issued
  interval (5.7) and is on the scaled series. Clipping cannot change it: y ≥ 0 in both datasets, so
  when l < 0 both l − y and the clipped 0 − y are ≤ 0, and neither lower bound can exclude y
  [derived algebraically, not a code check].

## 12. Tuning and selection (5.6)

All choices use pre-test data only (targets released before the first test issue) and are then
frozen. At most four pre-declared candidates per learned method, always including identity:

| Method | Candidates |
|---|---|
| DAQA | η = 0 (identity); (η, λ) pairs **TODO (O2)** ×3 |
| Centre-only | η = 0 (identity); (η, λ) pairs **TODO (O3)** ×3 |
| MultiQT | identity (η = 0); fixed rates **TODO (O1)** ×2; authors' adaptive+ |
| Tracker γ | three candidates **TODO (O4)**, shared by all methods |

**Selection rule**: the candidate with the lowest validation native WIS (calibrated rows: the
validation 95 % interval score), with the same scaling and averaging as the primary endpoint over the
validation records legal before the first test issue [O9, O10, O11, O12]. An identity winner is used
as is. Nothing switches after test results are seen; online test updates follow the pre-specified
rule rather than retuning. Fixed MultiQT rates used in the tests (0.05, 0.5) are test inputs only and
are **not** protocol choices.

## 13. Metrics and primary endpoint (5.8)

**WIS** (Bracher et al., 2021) on the nine native quantiles, i.e. the median plus central
20/40/60/80 % intervals (α ∈ {0.8, 0.6, 0.4, 0.2}, K = 4):

WIS(q, y) = (1/(K + ½)) [ ½|y − q₀.₅| + Σ_{k=1}^{4} (α_k/2) IS_{α_k}(l_k, u_k; y) ],
IS_α(l, u; y) = (u − l) + (2/α)(l − y)1{y < l} + (2/α)(y − u)1{y > u},

which equals 2 × the mean pinball loss over the nine levels (so mean pinball is not independent
evidence). Endpoints inclusive; quantiles never rounded before scoring.

**Primary endpoint (pre-declared)**: with cells c ∈ {(1,0),(1,2),(1,4),(4,0),(4,2),(4,4)}, eligible
areas A, and T_{i,c} the 104 test issues t whose target y_{i,t+h} is observed:

Δ = (1/6) Σ_c (1/|A|) Σ_{i∈A} (1/|T_{i,c}|) Σ_{t∈T_{i,c}} [ WIS(q^DAQA_{i,t,c}, y_{i,t+h}) − WIS(q^MultiQT_{i,t,c}, y_{i,t+h}) ] / s(i)

using the native (uncalibrated) issued vectors of the selected DAQA and MultiQT configurations on the
Sri Lankan data. Negative = DAQA better. [O16: averaging order.] Secondary metrics, the complexity
ladder, the pre/post-release split (§4) and the downside analysis Δ(i) = [WIS_adapted(i) −
WIS_frozen(i)] / WIS_frozen(i) (undefined, never epsilon-repaired, when the denominator is 0) follow
5.8 unchanged.

## 14. Bootstrap (5.8)

- Paired **stationary bootstrap** (Politis and Romano, 1994) over the 104 test issue weeks: each
  resample is a sequence of blocks with geometric lengths, **mean block length 13** (> max h + d = 8),
  wrapping circularly; every resampled week carries its complete vector (all areas, methods and
  cells together) so temporal dependence, spatial correlation and pairing are preserved.
- **2,000 resamples**, Δ recomputed on each; interval construction **[OPEN O15]** (draft: percentile
  2.5 / 97.5 %).
- **Seed**: `numpy.random.default_rng(20261016)` (PCG64), one generator per (dataset, block length).
- Sensitivity: mean block lengths **8 and 26**, same seed and resample count.
- Districts are never treated as independent samples; cell-level contrasts are descriptive; no
  cross-district Wilcoxon test is primary evidence. ILINet: same procedure (contingency 3 of 5.11
  may reduce it to a table without an interval).

## 15. Downside analysis (5.8)

As in 5.8 for DAQA, MultiQT and centre-only: mean, median, worst area, fraction of areas worsened and
largest deterioration of Δ(i). No no-harm guarantee is claimed.

## 16. Synthetic delayed shock (5.9) [verified computation; O17]

- Rule: the eligible area with the median pre-test mean count, taking the lower of the two middle
  areas; its observed values × 3 for three consecutive weeks from the first week of the second test
  year. Sri Lanka only.
- **Area: Matale.** With 26 areas the middle pair (13th/14th) is Matale / Trincomalee; the lower is
  Matale. This is the same whether the "pre-test mean" is taken over the scaling segment (Matale
  15.43, Trincomalee 17.55) or over all pre-test rows 0–903 (17.35 / 18.93) [verified].
- **Weeks: rows 956–958 = 2025-04-19, 2025-04-26, 2025-05-03** (test issue weeks 53–55) [verified].
- The shock changes Matale's labels and later contexts, so Chronos-Bolt is recomputed for affected
  shocked issues (the clean cache is not reused for them). It is not tuned and is excluded from the
  primary endpoint.

## 17. Outbreak case study (5.9) [verified computation]

- Rule: the 13-consecutive-week period with the highest aggregate count over the retained areas,
  inside the test window (§4), from counts alone, independent of any method's performance.
- **Window: rows 990–1002, weeks starting 2025-12-13 → 2026-03-09 (through 2026-03-15)**; aggregate
  19,885 cases; next-best window 19,831. It contains Puttalam's NaN (row 998); the aggregate uses the
  observed values only (no imputation). The same window wins when Puttalam is excluded entirely
  (19,567 vs 19,520), and when the window is searched over target rows 905–1011 or 904–1011 [verified].
- It spans 93 calendar days because the Monday switch leaves 2025-12-27/28 in no week. It matches the
  proposal's provisional "December 2025 to March 2026".

## 18. Future-label perturbation test (5.6)

- Pre-declared weeks (`tests/perturbation_weeks.json`; rule: the first issue on or after 1 January in
  each segment, by date): Sri Lanka 2023-01-07 / 2024-01-06 / 2025-01-04 (rows 837 / 889 / 941);
  ILINet 2023-01-01 / 2024-01-07 / 2025-01-05 (rows 639 / 692 / 744).
- For each week and each d, every value with index > t − d is set to value·10 + 1000 (NaN stays NaN)
  and the pipeline is rerun up to t for cells (1, d) and (4, d), recomputing Chronos. Exact equality
  for contexts, release queues and MultiQT states; |diff| ≤ 1e-6 (pre-declared tolerance) for
  Chronos-Bolt and Frozen. Positive and negative controls built in. The scale test checks s(i) at the
  first warm-up issue for every d.
- **Result** (current code, Frozen and MultiQT only) [verified, 2026-10-16]:
  `tests/test_perturbation.py` 30 passed, 0 failed, 0 xfailed; full suite `170 passed in 125.92s`. Centre-only, DAQA,
  calibration and selection states must be added before the end-of-Week-2 gate (5.11).

## 19. Software, versions and seeds

- Python 3.11.9 (`.venv`, system Python), Windows 11, CPU only.
- chronos-forecasting 2.3.2, torch 2.14.1 (+cpu), transformers 5.20.0, huggingface_hub 2.2.0,
  numpy 2.4.6, pandas 2.3.3, scipy 1.17.1, scikit-learn 1.9.1, pyreadr 0.5.7, pytest 9.1.1; the full
  pin list is `requirements.txt`.
- Seeds: Chronos-Bolt is deterministic (quantile head, no sampling; fixed batch, §6). Bootstrap
  `default_rng(20261016)`. Test-suite random inputs use fixed seeds (`tests/test_timing.py` and
  `tests/test_cache.py`: 20261016; `tests/test_multiqt.py`: 1, 7, 11–13).

## 20. DECIDED (consolidated)

1. MultiQT: own implementation with exact parity against the authors' `multiQT()` at commit
   `3300f75c…` — implementation deviation, method unchanged; supervisor to be informed.
2. MultiQT adaptive+ window = the authors' code (last min(n_obs, 50 − D) residuals); the paper is
   silent on delay; disclosed.
3. COVID weeks (2020–21) are included in s(i).
4. Issued quantiles are clipped at 0 after rearrangement, for every method.
5. Test origins end at T − 4; the same 104 origins are used for all six cells.
6. Scaling segment ends max(d) = 4 rows before the first warm-up issue (§3); pre-test correction
   found by the perturbation test, no scores existed; one row more conservative than needed;
   disclosed.
7. Update signals as in §11.
8. Chronology from `start.date` only; NaN never 0; seasonal naive = 52 grid rows back.
9. Test window defined by issue weeks; post-release defined by target week after 2024-11-26.

## 21. Deviations log

- Scaling segment shortened by 4 rows (§3), pre-test.
- MultiQT implemented in-house with exact parity instead of calling the authors' function directly
  (5.5 / 5.11 said "used unchanged"); method unchanged.
