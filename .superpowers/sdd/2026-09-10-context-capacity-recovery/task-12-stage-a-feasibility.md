# Task12: Stage A feasibility against 240 seconds

Date: 2026-09-12. Independent, bounded read-only analysis. The controller reports
user approval of the plan, including the 240 CPU/wall target and seven-day
planning objective; the plan's older planning-only status text is not a new
performance result. Only this report is authored. No product, helper, test,
index, SSH, native execution or subagent work.

## Decision

**Stage A does not presently have a plausible demonstrated path to the agreed
240-second target. Apply the plan's A1 STOP before building the prefix-view
implementation.** The completed G1 trace contains only 21.713 CPU / 21.717 wall
seconds of completed repeated history calls. Even deleting those calls
entirely would leave approximately **250.620 wall seconds after just 27 of 31
snapshots**, before four snapshots are complete or final verification finishes.
Real Stage A must retain fresh decoding, allocation and proof boundaries, so
its saving is smaller than this deliberately impossible zero-cost ceiling.

This is a same-trace feasibility calculation, not a certified lower bound on
an uninstrumented new implementation. Wrapper/output overhead and run variation
were not measured independently. They would have to explain more than 10.620
seconds already at snapshot 27, plus retained repeat decoding and all remaining
mandatory work, to reverse this result. The observed helper wraps phases, not
every row; no evidence currently establishes that large an overhead correction.
Do not turn that unmeasured possibility into an A implementation justification.

A bounded late-prefix measurement can sharpen the ceiling and close the
diagnostic uncertainty. It cannot justify subtracting complete feature calls
or first derivations. If it confirms this attribution, the next deliverable is
the separate Stage B architecture decision specified by the plan, not another
micro-optimization cycle. This report does not authorize Stage B product code.

## Evidence and reproducibility

Read the complete plan
`docs/superpowers/plans/2026-09-11-pruefarchitektur-kapazitaet.md`, especially
sections 5/A1-A3, 6, 7 and 8; and the complete previous
`task-11-growth-analysis.md` (SHA256
`25ecbb5172a5422375cc038b9f6ec4e58d8d6585120514c2578720904b54443d`).

Retained trace: `.pytest_tmp/task10-g1-native-phase-capture-72421d3.jsonl`, SHA256
`bd1771ff03a93dff67d1156ba8a81f48c2caad2b14b5a50fcd4e823def8e99a1`.
It identifies source `72421d3bdbec4ab15a3d2953cb153e867e7e340a` and G1 input
`04e7db378a84fb90fb115db4aed6508ae295d0b99adb9f5626eba03a1f43b94b`.
Input remained unchanged. Read the existing trace helper to establish timing
scope; no helper was executed or changed. Its retained capture omits initial
phase messages but preserves elapsed offsets and final aggregate accounting.

PowerShell read-only JSON parsing joined start/end records by `(phase, call)`,
then grouped `_replay_history` by exact `(cutoff, tour)` in call order. Dates were
kept as strings (`ConvertFrom-Json -DateKind String`) to avoid local-time display
conversion. All observed histories are ATP. Values below are printed rounded
phase measurements, not additional server observations.

## Exact cutoff attribution

All cutoffs below are UTC; full fractional precision remains in the trace.
Each row has two calls; the first completed derivation is mandatory in A.

| Cutoff UTC | Calls | First CPU | Repeat CPU | Repeat wall | Repeat status |
| --- | --- | ---: | ---: | ---: | --- |
| 2026-09-10 10:00:10.922492 | 1/2 | 1.266 | 1.128 | 1.128 | complete |
| 2026-09-10 12:07:13.973931 | 3/4 | 1.215 | 1.360 | 1.361 | complete |
| 2026-09-10 14:07:22.413064 | 5/6 | 1.181 | 1.106 | 1.107 | complete |
| 2026-09-10 16:37:17.606959 | 7/8 | 1.116 | 1.140 | 1.140 | complete |
| 2026-09-10 19:07:36.898266 | 9/10 | 1.243 | 1.545 | 1.545 | complete |
| 2026-09-10 21:37:11.328361 | 11/12 | 1.234 | 1.411 | 1.411 | complete |
| 2026-09-10 23:37:30.375880 | 13/14 | 1.340 | 1.372 | 1.371 | complete |
| 2026-09-11 02:07:23.736658 | 15/16 | 1.068 | 1.177 | 1.177 | complete |
| 2026-09-11 04:37:07.428194 | 17/18 | 1.196 | 1.047 | 1.047 | complete |
| 2026-09-11 06:37:36.595160 | 19/20 | 2.591 | 2.336 | 2.337 | complete |
| 2026-09-11 09:07:06.630691 | 21/22 | 2.721 | 2.584 | 2.585 | complete |
| 2026-09-11 11:07:23.384481 | 23/24 | 2.497 | 2.422 | 2.422 | complete |
| 2026-09-11 13:37:47.102511 | 25/26 | 2.728 | 3.085 | 3.086 | complete |
| 2026-09-11 16:07:21.862129 | 27/28 | 2.842 | 2.063 | 2.063 | interrupted |

- Thirteen completed repeats: **21.713 CPU / 21.717 wall**.
- Including only the executed portion of repeat 28: **23.776 CPU / 23.780 wall**.
- Fourteen first derivations: **24.238 CPU / 24.242 wall**, all retained.
- All 28 replay records: **48.014 CPU / 48.022 wall**, including partial 28.
  The narrower `_lookup_covering` aggregate is **48.002107 CPU** including
  partial 28; its difference from replay totals is wrapper/outer work and
  rounding. Do not mix them as identical measurements or add them together.

There are **27 completed snapshots**, an interrupted 28th, and **three snapshot
calls not entered**. Thus four snapshots have not completed. The original phase
records two further original cutoffs at `2026-09-11T18:37:34.898105+00:00` and one
at `2026-09-11T19:35:00+00:00`. Those original records establish the remaining
cutoff demand, not measured snapshot timings. The earlier pair would offer at
most one additional repeated-prefix opportunity; the new unique maximum offers
none. Missing costs must remain unknown, not assigned a late-call average.

## What the ceiling means

On the observed 27-snapshot prefix, the most generous deletion is:

`272.337 elapsed wall - 21.717 complete repeat replay wall = 250.620 seconds`.

The snapshot-27 finish is its recorded start plus 8.431 wall seconds. This
calculation removes whole repeated history calls, including decoding that A
cannot remove. All future savings occur alongside future work and cannot
retroactively reduce this prefix below 240. It does not assume a completion
time for killed G1. Rounding is millisecond-scale, not the 10.620-second gap.

The 27 completed feature calls total **67.041 CPU** and remain. They include
selected-receipt validation, not merely model arithmetic. The snapshot-worker
aggregate **162.075564 CPU includes interrupted 28**, and encloses history and
feature work; it is not another independent cost to add. The diagnostic total
277.179 CPU / 276.087 wall includes different startup/final accounting than the
phase-clock prefix, so subtracting repeat work from that process total is not
a native completion estimate. There is no recorded cumulative CPU checkpoint
at snapshot 27; the wall calculation alone addresses a required target.

Current uninstrumented actual30 was 288.095 CPU / 288.261 wall; this G1 sample
cannot be subtracted from that different input to claim an actual30 result.
G1's uninstrumented 299.975 CPU / 300.165 wall kill is censored, not its full
runtime. Neither establishes a 240-second pass.

## Why the remaining work is really outside A

Current cache/Tennis/runtime source has no diff against exact72421d3 in the
inspected modules. `context_runtime_history_cache.py:613` still performs first
covering derivation with before/after row checks, fresh `json.loads`, cutoff and
complete-byte admission, then final validation. `:595` demonstrates the existing
exact-key fresh-decode/edge-check route. `context_runtime_tennis.py:92` currently
returns covering results without storing a duplicate encoding. These are A's
bounded derivation/memoization seams, not permission to change other work.

`context_runtime_tennis.py:212` retains each original/reference comparison,
full causal receipt list, actual feature invocation within the selected scope,
feature comparison and transport replay. Cache `_matches` at `:52` still checks
current proof before/after canonical row comparison. A changes neither those
feature checks nor source/physical/cold basis validation.

The one overflow original uses the complete owned prefix at cache `:562` and
cost 1.360743 CPU; rolling batches still require their first full scan. Thirty
successful projections among 31 lookups cost 0.006216 CPU across **all 31**.
Neither is the missing reserve. No decoded/result cache, additional truth seal,
larger caps or weaker first-derivation validation is inferred from plan approval.

## Exact additional measurements and growth decision

1. **Complete the late-prefix cost split, not the whole censored old run.** On
   exact source/input/app venv, within one bounded diagnostic, measure the same
   late prefix at `16:07:21.862129`, the unentered `18:37:34.898105` pair, and the
   unique `19:35:00` maximum: row count, canonical byte count, first full owning
   derivation, full repeated covering cost, and fresh decode/allocation cost.
   The maximum's existing exact hit is a useful decode control, not a substitute
   for timing an identical earlier prefix. Every required returned row must be
   included. Releasing each result before the next sample avoids accidental
   doubled retention. Record CPU and wall separately.
2. **Only a diagnostic lower-cost envelope:** any isolated decode-only timing
   is not an authorized accepting verifier. It bounds retained work but omits
   the planned parent-serial/provenance/final checks and metadata bookkeeping.
   Real A saving is strictly below complete repeat covering minus fresh decode,
   further reduced by those checks, admission/accounting and pressure misses.
   First derivation must not be excluded from a total-cost claim.
3. **Calibrate timing uncertainty if attempting to overturn A1 STOP.** Measure
   identical bounded phase calls with and without the existing outer wrappers
   and output, leaving validators untouched. Preserve exact input/source pins.
   No need to weaken guards, raise limits or run a complete expensive suite.
   A claim that trace overhead bridges the deficit needs measured evidence;
   native acceptance would still require three separate full CLI runs <=240
   CPU and wall for every agreed mandatory profile.
4. **Seven-day input sizing belongs to live metadata, not this partial trace.**
   Obtain actual per-day snapshot/original and distinct `(cutoff,tour)` growth,
   cutoff multiplicities/order, causal rows and encoded bytes by tour/cutoff,
   and database size growth across representative operating days. Include
   bursts and both tours, not just an average receipt count. Root owns this
   read-only collection. The trace contains only ATP and roughly a short
   historical window; it cannot establish seven days of supported growth.
5. **Growth cannot rescue A's economics.** For `r` consumers at one cutoff,
   only `r-1` repeated derivations are candidates. New unique cutoffs add full
   first derivation plus all features; a no-repeat 60/120-cutoff stress profile
   has zero A repeat savings. More repeat snapshots still retain their complete
   features and fresh history. The shared 32-slot / 64-MiB envelope remains;
   views beyond capacity fall back fully. No absolute supported day/count
   ceiling can be derived without root's growth metadata, but a presently
   unsupported 240-second G1 target cannot certify seven more operating days.

Recommendation: finish only the already bounded missing measurement needed
to confirm or falsify the optimistic ceiling; do not begin Stage A product
work unless genuinely new measured evidence reverses it. Keep capacity/release
HOLD and move to a separately reviewable Stage B design if confirmed.
