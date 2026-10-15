# Task 23: actual bounded B1 Tennis training batch

## Approved intent and scope

User approved the short in-chat batch design on 15 October 2026: read the
training discovery inputs once per evaluation, preserve each original cutoff
and every revision, avoid new DB copies, then run the same four-event probe
within 45 seconds including preparation. This is an equivalent internal B1
engineering optimization, not a new model family or empirical approval.

Base `4ece002b69eb5c96897d3471cc7320654608a903`, authoritative linked worktree
`C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013`.
Existing approved September context plan/spec remain binding; Cricket untouched.

## Deliverable

1. Implement a real batch entry point in `context_models/tennis_training.py`
   for an explicit frozen list/tuple of case requests. Hold one actual existing
   `dataset._reader` transaction, not an escaped owner/cache from the daily job.
   Existing single-case behavior/signature remains usable and equivalent.
2. Discover participant/event membership once for the requested tours/players
   using only ESPN event_status/workload context candidates. Retain the earliest
   actual matching receipt time per (tour, player, event_key). Per-case membership
   is restricted to that case's cutoff. Preserve target event and **all** revisions
   of admitted keys up to its cutoff, even if a later correction removes a player.
   Do not copy the full DB or spool the full source inventory.
3. Use the existing physical/native validation and `PreparedTennisHistory` where
   appropriate. Do not substitute an unverified proof/flag, mutable cross-case
   owner, newest-only selection, global max-cutoff selection, or incomplete
   receipt pool. Exact observation order, feature values and case digests must
   match the original single-case implementation on valid inputs.
4. Connect the same discovery owner to the actual feature path of
   `context_models/readiness.py` so it is reachable outside tests. Inventory-only
   remains inventory-only, without feature construction or outcome scoring.
   Existing coarse readiness content lookup must not promote future participant
   association into an earlier case.
5. Bounds are shared over the complete call, including discovery/preparation.
   Reuse existing 1..600-second diagnostic admission, default 45 seconds for the
   new batch; at most 100 explicit requests. Bound combined lookup metadata and
   one-at-a-time encoded selected-history retention by the existing 256-MiB
   `MAX_TENNIS_HISTORY_BYTES`, never renew a whole budget per case. Stream SQL
   results, avoid fetchall of the source inventory. Exceeding admission aborts
   the complete unpublished operation, never returns a truncated successful pool.
   This is a Python retention/admission limit, not proof of total process RSS;
   actual CPU/wall/RSS are measured separately by the controller's native probe.
6. Discovery/features exclude `match_outcome`. Keep existing original, state,
   identity, cutoff and outcome owners; no new winner/ROI selection or label
   opening path, no fitting, empirical approval, activation or coefficient change.
7. No schema/index installation, new service/provider/dependency, source fetch,
   production DB copy, backup, deletion or runtime limit increase. Actual
   ordinary B1 training does not call C; do not claim C admission of 7.35 GB under
   its unchanged 4-GiB input contract.

## File ownership

Implementer owns only `context_models/tennis_training.py`,
`context_models/readiness.py`, new `tests/test_tennis_training_batch.py`,
new `tests/test_tennis_readiness_batch.py`, and the sibling task report.
Controller-approved closure extension: `context_models/evaluator.py` solely
adds existing `tennis/history_projection.py` to exact source-proof hashes;
test the binding in the new task test file, no grandfathered report acceptance.
If a small focused helper module is actually necessary, ask the controller
before creating it; do not split into an unrequested framework.
Controller owns ledger, current TODO/handoff, full regression, real VPS probe,
independent review, scoped commit/push/deploy. No implementer Git mutations,
VPS/network calls or additional subagents. Preserve all inherited files/tests.

## TDD and acceptance

Read TDD and writing-good-tests. Write real-SQLite failing tests first. Cases:
different cutoffs; association only after an earlier decision; later participant
removal; simultaneous conflicting revisions; ATP/WTA player-ID collisions;
status/workload revisions; missing content; wrong outer identity; untouched
outcome decoding; input/budget/timeout boundaries; aborted/later use; exact byte
and case-digest equivalence to existing single path; actual discovery performed
once, not a mock-only helper test. Hand-checked receipt fixtures supplement
differential equality. Test real readiness use and inventory-only exclusion.

Use `.codex_test_venv/Scripts/python.exe -B` via the existing offline launcher
at `C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py`.
Fresh test directories/logs under `C:/Projekt/BetBoy/output/tennis-batch-20261015`.
Read existing `tests/test_tennis_live_training.py` packet fixture and status-v4 /
readiness tests. Do not weaken or change existing tests. Run covering tests
during iteration; controller runs the whole suite once on final frozen source.

Report exact RED/GREEN commands/results, files/hashes, retained assumptions and
all failures to sibling `task-23-tennis-batch-20261015-report.md`, then return
short status/summary/concerns. No synthetic local test is real-production speed
proof; if real 45-second probe fails, this optimization is not shipped as solved.
