# Task13: provisional seven-day growth and storage sizing

Date: 2026-09-12. Independent read-only calculation, not acceptance or a forecast
of actual future writing. Only this report is authored; no code, test, helper,
index, SSH, native execution or subagents. Existing input/history/cache caps
remain unchanged.

## Decision

The proposed probe of **+70,000 receipts, +24 originals and snapshots, and
+14 distinct cutoff/tour keys per day** is a sensible explicitly provisional
stress-sizing choice above the currently observed partial-day counts. Seven
days yields **589,776 receipts, 199 originals/snapshots and 114 distinct keys**.
It is not yet evidence that this is a conservative seven-day operating envelope:
the source has only two partial calendar days, one tour and bursty ingestion.

**Do not label this probe a supported seven-day profile yet. Storage is a
separate likely blocker, even if Stage B solves repeated verification CPU.**
At current average payload sizes, a simple anchored input estimate is about
**1,152,584,353 bytes**, already above the fixed **1,073,741,824-byte (1 GiB)**
input cap. A same-mix ATP-history scenario reaches about **345,159,123 bytes**,
above **268,435,456 bytes (256 MiB)**. These are conditional sizing calculations,
not measured future database/history sizes. Snapshot payload growth with the
entire causal reference list makes the fixed-average snapshot estimate
potentially optimistic, not a defensible upper bound.

Therefore Stage B's design must explicitly confront input and full-history
admission, not merely amortize verification. No history pruning, cap increase,
schema migration or storage split follows from this report. A profile genuinely
outside the frozen limits requires the separate capacity/storage decision
already called out in plan section 7; do not silently shrink the probe to claim
seven days, or exempt a new/current full history from admission.

## Measured facts and distinct evidence identities

Live metadata: `.pytest_tmp/task13-live-growth-20260912.json`, SHA256
`5d4a488155607b773062cbc9807a5330de8424b03bc58d4cf7b45b03827628bf`.
Read transaction measured at `2026-09-11T22:12:37.262269+00:00`. Its own note
explicitly allows concurrent existing worker changes: this is **not a sealed
input or file-unchanged claim**, nor D4 verification.

| Live measurement | Value |
| --- | ---: |
| Receipts / content rows | 99,776 / 99,776 |
| Originals / snapshots / tour states | 31 / 31 / 2 |
| Distinct cutoffs, all ATP | 16 |
| Cutoff multiplicities | 15 pairs and 1 singleton |
| Logical database bytes / main file bytes before | 268,824,576 / 268,824,576 |
| Content payload bytes | 106,653,805 |
| Snapshot payload bytes | 66,373,102 |
| Original / tour-state payload bytes | 52,309 / 2,953,017 |
| Receipts on September 10 / 11 | 48,556 / 51,220 |
| Originals on September 10 / 11 | 14 / 17 |
| Distinct ATP cutoffs on September 10 / 11 | 7 / 9 |

The receipt clocks span September 10 09:59:08.864565Z through September 11
19:37:12.401006Z; original cutoffs extend through September 11 21:07:24.424169Z.
Neither calendar day is a full observed 24-hour operating day. September 11
contains 27,498 event-status and 22,322 workload receipts: 49,820 of 51,220
receipts, but kind alone does not establish ATP membership or selected-history
count. Bulk workloads can create bursts; receipt clocks are not a measured
continuous arrival-rate schedule.

Separate pair diagnostic: `.pytest_tmp/task12-stage-a-pairs-72421d3.jsonl`, SHA256
`1c578cb7f241d055b930b5df15dc3efc05bf79729a9302de9db97a87a3900f13`.
This uses exact72421d3 and sealed **synthetic G1**, input SHA04e7db...94b,
not the above live database. It completed 12 diagnostic pairs, not D4:
184.453215 CPU / 183.117809 wall, unchanged input. Its full maximum ATP encoding
is **58,392,186 bytes / 42,100 selected rows**; total charged cache is
58,401,081 bytes. Do not transfer that exact history size to the differently
timed live 31-snapshot input without measuring it.

For context, the new diagnostic confirms mandatory fresh-decode cost:
20,501-row samples use about 0.510-0.610 CPU seconds for optimistic decode,
versus 1.534-1.693 real covering; 42,099-row late samples use 1.220-1.379 versus
3.487-3.743 CPU seconds. Paired late differences are 2.232-2.364 CPU seconds,
before adding the proposed proof/accounting cost. The exact maximum already
uses the exact path and is not an additional Stage A repeated-covering saving.
These measurements do not produce a full-run speed or supported growth count.

## Probe arithmetic and why it remains provisional

| Dimension | Baseline | Seven-day addition | Probe total |
| --- | ---: | ---: | ---: |
| Receipts | 99,776 | 7 x 70,000 = 490,000 | 589,776 |
| Originals and separately snapshots | 31 | 7 x 24 = 168 | 199 each |
| Distinct cutoff/tour keys | 16 | 7 x 14 = 98 | 114 |

The proposed daily amounts are respectively 36.7%, 41.2% and 55.6% above the
September 11 **partial-day totals**, not that far above a validated full-day
peak. No statistical confidence, seven-day upper bound or acceptance follows.
Exact new `(event, cutoff, tour)` query keys must also be counted; distinct
cutoffs and originals are different dimensions.

A concrete 24-consumer / 14-cutoff daily pattern can be ten two-event cutoffs
plus four singletons. With the preserved baseline this gives 85 pairs and
29 singletons, hence 199 consumers across 114 cutoffs. Do not obtain these
counts by replaying duplicate keys or replacing the old rows. Include a
distinct-cutoff/no-repeat counterprofile to expose the unavoidable work.

The ATP-only probe should preserve the existing ATP baseline and concentrate
all new relevant history in ATP. A mixed-tour probe should also preserve that
baseline, then deliberately distribute **new** producer-valid receipts,
originals and cutoff keys across ATP/WTA. Equal new consumer allocation would
give 115 ATP / 84 WTA consumers and, with seven new cutoff keys per tour/day,
65 ATP / 49 WTA cutoffs. This is a test design, not a measured future tour mix.
Retain both tour states and actual owner-produced snapshot/transport data.

## Input-size scenarios: bytes, not counts alone

Observed means are **1,068.932459 content bytes per receipt** and
**2,141,067.806452 payload bytes per snapshot**.

Assuming unchanged means and unchanged existing rows:

- Added content payload: `490000 * 106653805 / 99776` = **523,776,905 bytes**.
- Added snapshot payload: `168 * 66373102 / 31` = **359,699,391 bytes**.
- Added original payload at its current mean: **283,481 bytes**.
- Current DB plus these additions: **1,152,584,353 bytes** (about 1,099.19 MiB),
  **78,842,529 bytes above 1 GiB**. This assumes existing file occupancy stays
  and ignores additional indexes/receipt metadata/page overhead. It is a
  scenario, not a guaranteed floor: existing reusable free pages and actual
  future encoding/layout have not been measured.
- All projected content/snapshot/original payloads plus fixed current state
  payloads alone sum to **1,059,792,010 bytes**, leaving only **13,949,814 bytes**
  below 1 GiB for every SQLite record, receipt-clock/digest column, key, index,
  manifest, free page and additional state. No compression/layout change is
  assumed. The current DB has 92,792,343 bytes beyond the listed payloads.

Blindly scaling the entire current DB by receipt count would instead give
1,589,022,241 bytes, but wrongly assumes snapshots, fixed state and all overhead
grow in that same ratio. It is not the recommended estimate. These divergent
scenarios show why actual byte distributions and storage layout must be measured.

There is a stronger reason not to hold snapshot means constant:
`context_runtime_tennis.py:232` requires the entire sorted causal history's
receipt digests in `observation_refs`; `context_snapshots.py:142` stores canonical
payload bytes, and `model_artifacts.py:24` uses compact UTF-8 JSON. One 64-character
digest contributes approximately 67 bytes including JSON quotes/separator.
For a conditional ATP scenario with the sealed G1's 42,100-row prefix retained,
168 new snapshots need approximately **473,877,600 bytes for that one reference
array alone**, even with no additional selected-history growth. That exceeds
the 359,699,391-byte fixed-average estimate for their entire payloads. This
scenario uses the measured sealed G1 history as a proxy, not a claimed exact
live-history lower bound. More selected rows add references again in every
later snapshot; full snapshot storage can grow faster than receipt count.

## Full-history and cache risks

Exact source caps: `context_runtime.py:39-41` has 64-MiB image, 1-GiB sealed-input
and 256-MiB full-Tennis-history limits; `:562-563` applies the latter two in
sealed-file mode. `context_runtime_history_cache.py:20` sets the separate
64-MiB shared cache. A larger sealed input allowance is not a larger cache or
history allowance.

The sealed G1 encoding averages **1,386.987791 canonical bytes per selected
row**. If future selected rows have that same average:

- The 256-MiB history cap has **210,043,270 bytes** of headroom: approximately
  **151,438 additional selected rows**, not 151,438 arbitrary receipts.
- Using G1's selected/all-receipt fraction `42100/99775` only as a scenario,
  +490,000 total receipts adds approximately 206,755 selected ATP rows and
  286,766,937 encoded bytes. Final history is **345,159,123 bytes (329.17 MiB)**,
  above 256 MiB by approximately 76,723,667 bytes.
- In that same conditional scenario the crossing occurs after about +358,902
  total receipts, or 5.13 units of the proposed +70,000/day probe. This is **not
  a predicted calendar failure date**. Tour/source mix, bytes per row, selection
  eligibility and event timing can all change the result.
- The existing charged cache has only **8,707,783 bytes** free. Even ignoring
  metadata, the 64-MiB pool permits about **6,285 further same-size encoded rows**
  beyond the current basis. Crossing the cache budget is normally a full
  fallback/performance transition, not automatically a 256-MiB history failure.
  Stage B cannot assume the present owned encoding always stays resident.

Mixing tours can reduce the largest individual history but does not make bytes
disappear. For illustration only, dividing the above **new** selected bytes
equally would leave the existing ATP base plus half the increment at about
201.776 MB, and a new WTA base at about 143.383 MB. Both fit individually under
256 MiB in that scenario but both exceed the entire shared 64-MiB cache, and
their combined encoding remains about 345.159 MB. Baseline WTA selected-history
bytes are not measured by the ATP-only pair trace and must not be assumed zero
for an actual acceptance input. Tour distribution also changes reference-list
storage and original-query fallback costs.

## Required sizing evidence before declaring the seven-day scope supported

1. More complete operating-day metadata or explicit burst assumptions: per-day
   receipts, actual insertion cadence, originals/snapshots and exact query and
   cutoff/tour multiplicities. Preserve the observed partial-day qualification.
2. Current exact maximum **selected canonical history rows/bytes per tour** on
   a sealed input; separate all receipt bytes from source-selected encodings.
   Obtain row-size distributions and selected fractions rather than treating
   status/workload kind counts as tour membership.
3. SQLite page count, page size and freelist; receipt/index/manifest and artifact
   byte components; actual snapshot bytes against their complete reference
   counts and cutoffs. Reconcile summed payload bytes with actual file size.
4. Project actual owner-produced new histories and snapshots by daily cutoff,
   including all baseline rows. Record input bytes, maximum history bytes per
   tour, cache pressure and per-snapshot reference bytes at every day boundary.
   Run ATP-only concentration and mixed-tour controls separately. Counts alone
   do not settle either admission cap.
5. If the planned seven-day input cannot remain within frozen admission limits,
   stop before claiming a CPU-only Stage B repair satisfies the approved goal.
   Present a separate explicit capacity/storage architecture decision. A
   persisted verification certificate does not itself reduce stored input,
   supply a valid smaller causal history or waive a newly required full replay.

No new performance guarantee or seven-day acceptance is established here.
