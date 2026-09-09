# Independent review: Tennis native capture/status v3

## Disposition and exact scope

**PASS for the bounded capture, status-lineage and explicit CPU v3 adapter.**
No actionable new correctness finding was reproduced in this review. This is
not empirical approval, completed D3 worker/UI wiring, D4 replay acceptance, or
a production/deployment claim.

Reviewed worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-tennis-capture-20260909`.
Frozen commit: `f45c7eb93b85fb88bc4602b5663746f2d9b0c88e`.
Parent: `ecf92007f46c5e8b85cb24b6f7208cb71240cac4`.
The six changed/new Python sources, four owning test files and final owning
audit were read completely, including the full tracked diff. Source/test bytes
were confirmed against the owner's freeze before execution. Git status remained
clean and `git -c core.autocrlf=false diff --check` succeeded.

Read contracts: complete approved `2026-09-07-kontextmodell-design.md`, complete
Task 10/B6, Task 11/B7 and Task 18/D3 briefs, `context-contract-decisions.md`,
`validation-contract-decisions.md`, `task-18-controller-rulings-20260909.md` and
the final owning audit `docs/audits/2026-09-09-tennis-capture-status-v3.md`.
The source-specific v3 rulings in that audit were checked against implementation.
Relevant complete legacy source/feature/B7 code, actual B1 decoder/reader and
daily caller/callee boundaries were inspected, not inferred from test names.

## Independent execution

Interpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
All runs used `-B -m pytest -q -p no:cacheprovider`, unique temporary basetemps,
and JUnit output below. No provider calls, production data, real source clocks,
new subscriptions, or actual fitted sporting effects were used.

1. `test_independent_tennis_capture_v3.py` plus the four new owning test files:
   **129 passed, 0 skips, 5.76 seconds**. This is 37 independent tests and the
   92 new owning cases, on the final source bytes.
2. Unchanged focused regression: **841 passed, 0 skips, 18.79 seconds**.
   Exact files: `test_tennis_context_features.py`, `test_tennis_context_model.py`,
   `test_context_observations.py`, `test_context_snapshots.py`,
   `test_context_transport.py`, `test_tennis_pending_refresh.py`,
   `test_tennis_fixture_metadata.py`, `test_tennis_predict.py`,
   `test_tennis_prediction_revisions.py`, `test_tennis_side_bets.py`,
   `test_tennis_tour_readers.py`, `test_tennis_pipeline.py`,
   `test_workflow_integrity.py`, `test_market_scope.py`.
3. `test_independent_tennis_v3_math.py`: **8 passed, 0 skips, 1.62 seconds**.

Total independent execution: **978 passed, 0 skipped**, including 45 new
independent adversarial/control cases. No application or harness failure was
produced in these runs. Neither probe file nor assertions were changed after
its first execution. This review did NOT independently rerun the full repository
suite; the owner's 4,541/18/97 result remains owning evidence only.

## Source and lineage evidence

- Existing `_fetch_espn_events` keeps the identical one-GET URL, headers and
  timeout. The spy establishes ordering `HTTP success -> JSON -> receipt clock`
  before downstream fixture filtering. A native started competition lacking
  display names still produces its status receipt. Outside an explicit scope,
  no capture clock/storage is touched. Network/JSON failure does not create a
  capture receipt, extra request or database.
- Scope exit, not receipt normalization, writes B1. Native status is first;
  partial delivery cannot borrow an earlier opposing-player receipt. This is
  correctly NOT described as one multi-row transaction. Finally/reset behavior,
  worker failure and storage-error propagation are covered by the owning tests
  re-executed here. No same-run live coordinator is implied.
- Whole native history is resolved before player/schedule projection. Actual
  SQLite tests cover cancellation, started status, missing native participants
  and missing dates at cutoff minus one microsecond, exactly cutoff, and plus
  one microsecond. Eligible revisions remove prior available workload/exact
  rest even when another older valid match exists; future revisions do not.
- A changed complete participant pair removes only that event's old player's
  claim and permits the independent older event to remain. Status plus zero or
  one current workload receipt remains unknown for both old/new relevant players.
  Complete own bilateral delivery alone restores the new player's receipt bound.
- Substituting a valid opponent from another same-time native revision is
  conflicting, even with the same event and player IDs. Provider order reversal
  preserves both genuine native players and binds exactly the current status
  plus the two current workload hashes. Equality of totals or clocks is not a
  replacement for those hashes.
- A schedule recheck has a distinct revision and its own weaker receipt-based
  rest bound. It does not invent an exact end or place sets in an actual-end
  load window. The historical earlier cutoff remains unchanged. Reusing the
  strongest potentially recoverable old bound is explicitly not promised here.
- Unrelated match IDs and the other actual tour namespace do not alter current
  coverage. Target-event status/schedule/participant withdrawal controls from
  the owning suite were also re-executed. Missing identities are not repaired
  with names or former payload values.
- Actual cancellation is bound to `STATUS_CANCELED`/`STATUS_CANCELLED`.
  Incidental cancellation prose cannot override native `STATUS_FINAL`; adding
  that prose leaves the normalized sporting projection exactly identical.
  Existing retirement/walkover workload classification stays an observed match
  terminal classification, not an injury diagnosis or measured fatigue effect.

## Integrity, math and transport evidence

- The worker reader decodes the actual B1 inventory before cutoff/tour pruning.
  Seven independent outer-index/SQLite-type corruptions fail closed even when
  querying an earlier cutoff and another tour. Missing joined content and TEXT
  instead of the stored BLOB also fail. Existing rehashed-source-envelope,
  source-clock, simultaneous-conflict and partial-store tests remain unchanged.
  The reader is NOT a D2 label-free pre-opening reader: it can decode outcome
  content in this inventory and cannot be repurposed as such a preflight.
- The old v2 winner and serve algorithms were loaded read-only directly from
  the exact parent Git blob. Both complete synthetic comparison outputs match
  canonical bytes from the current implementation, including identities.
  This checks the actual before/after law, not just version strings.
- New v3 winner/serve fitted comparisons use artificial B2 training data and
  actual local B1 source receipt resolution. Without approval, original used
  parameters/markets remain exact and certification stays empty. No real
  statistical advantage or source qualification is inferred from these fits.
- Zero coefficient heads preserve every original market/parameter byte for
  both families. Old variant or coverage relabeling is rejected; a one-ULP
  forged signed feature is rejected instead of accepted with tolerance.
  The unchanged B7/strict-simulator regression validates counterpart, full
  Event/Base, completeness, supported format and no winner-to-serve promotion.
- A real `compute_once` callback calculates the actual v3 payload once for two
  subsequent consumers; both read the same immutable payload and complementary
  original used probabilities. A separate key-setup calculation in that probe
  is disclosed and not counted as once-only upstream work. This proves the
  existing B3 callback boundary, not a completed concurrent daily coordinator.
- Pure D3 still has only identity/replay responsibilities, not source or D2
  approval authority. The parent separately owns its previously accepted
  transport byte fix `1a9fffa`, absent from this worktree; this packet is only
  the new explicit v3 adapter and does not claim to replace that integration.

## Remaining boundaries / integration obligations

Only the two already sanitized September 7 ESPN examples are real, dated source
shape evidence. They do not establish current availability, true end/duration,
verified availability/injury, complete player history or a native Tennis-state
resolver. All other replies/receipts here are controlled synthetic local facts.

This packet captures existing responses and provides a worker reader plus CPU
v3 feature/model/transport mechanics. It does not finish B1-backed publication
to both real worker consumers or D4 source replay. In particular, `_run_daily`
finishes before the observer drains; a later same-run assembly must explicitly
run after persistence. New learned effects still need causal data, native state
replay, D1/D2 evaluation and an actual population/coverage-matching approval.
The conservative unresolved-revision coverage is an explicit first variant;
it does not claim to find every temporally irrelevant defect.

Source/B1 schemas, v2 feature law, predictor, simulator, calibrated original
forecasts, Cricket, ticket/account/15K history were not changed by this review.
No new 15K release, browser/UI acceptance, production job health, push, merge,
VPS pull, deployment or empirical >=200-event acceptance is claimed.

## Frozen raw SHA-256 identities

These are actual Windows bytes, not a portable line-ending-normalized recipe.

| File | SHA-256 |
| --- | --- |
| `context_sources/tennis_status.py` | `021ee5c234bf7a01166ee82dd21025154af1c48b81e5303c0963d2760166424f` |
| `context_sources/tennis_capture.py` | `918839283fd4bb446f01fbe34e32ef1e25fb690aa7d1e8f2627650506eef5fdc` |
| `context_models/tennis_v3.py` | `ec6461b87656ecc5731992cc26f0ae69d20e878982706ebe3f1fd0599c43305c` |
| `context_models/tennis_effect.py` | `ab556ac6bc5258332ab3e7b7faf5406d960f426541a7afef3974b4baf8fcb675` |
| `context_transport.py` | `e6969923e0b5bb81055cec7e33febe4224ce7d9c086676e26b53f5ab87c2195f` |
| `scripts/tennis_daily.py` | `96099d53717f1a5b869826dadf4b3d5818ff89b9e8b372e069f693c0c3c50280` |
| `tests/test_context_tennis_capture.py` | `9bb53101f6731724453f3a1dd546d55108bd373ca9a478477d23507eb348f67d` |
| `tests/test_tennis_status_v3.py` | `cf8533ff8d3bc68c016f270478776acc321cf9b5c46a80376d4f4297b036fdfd` |
| `tests/test_tennis_v3_model_transport.py` | `45c344840170f002c9f5d01745608532677be80dc8b5a1cab358630a277891aa` |
| `tests/test_tennis_native_status_codes.py` | `612c9f953dfd57e576cb158df09399ded71853ec3570d45675af221421589e6c` |
| Owning final audit | `7e368c59697c84fd5dc6f74ff96db511ee635d6630458d4235f1a69e1a929d4e` |
| `context_sources/tennis.py` (unchanged) | `80f1621f60e0b3daecef8abb5e44efeebd2c2bc6bc0df8161032daab78ceb739` |
| `context_models/tennis.py` (unchanged) | `313ffafacc367e7370312f478327d6453860ac0bf17bbcaf8102acdda49e4bab` |
| `tennis/predict.py` (unchanged) | `f92d9451d3e7c0612832101ab1d6298cb99baeeaaa4f2d7c89cb8e9fe0526c7c` |
| `tennis/simulator.py` (unchanged) | `6f326fc84de6b705b762b9d9efaa2932daf0f4546c419d56f30e8c3f4644e29f` |
| `sports_prematch.py` (unchanged) | `fc1253fbeb0888870715c21238d4da78de2c0cbe19fee910da67ebfd35b756d7` |
| Dated real fixture (unchanged) | `17c3140266883b4bd561f1432b698d66df7f07a09b50b344cf922123e65812bb` |
| `test_independent_tennis_capture_v3.py` | `48b7fc5c85a37fb75d1bd785bd7295e0d4471f5b2e0bb5b6f64a35e2b9763e3a` |
| `test_independent_tennis_v3_math.py` | `d4d53367d5406ba512aa482bf34ad206d578f97df9a72dbd8249c0f4631d5e71` |
| `probes-01.xml` | `3c7e62ea418d4a8ce6ff72657a5e66443cc5931af5d297aead1f2c41d7198bf7` |
| `focus-01.xml` | `e1cd829db8c880e7d3c745b2cfd51d2f69d8b449da90bd5b7093a1105a7f377d` |
| `math-01.xml` | `3d8b1a3bcb7c8cfbc8b86f51234766d88fc2cf2791b88bb3b44449173f637544` |

The only retained reviewer files are this report, two independent probe files,
JUnit and their ignored temporary databases. No source/original test/Git was
edited. An accidental new five-character scratch file `b6dummy` was briefly
created in the main checkout during report preparation and immediately removed
with an exact `apply_patch` deletion; it was not code, imported, staged or tested.
No pre-existing file was affected. This execution mistake is disclosed rather
than counted as an allowed review artifact.
