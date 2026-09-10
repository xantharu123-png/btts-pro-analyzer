# Independent Task 1 review: covering completed Tennis histories

Verdict: **APPROVED** for the third refinement's scoped local correctness. This is not native capacity, release, updater or deployment approval.

## Exact reviewed state

- Base: `8f429959dac3d6f3bee1f6125051c6f549ed22a1`.
- Code: `4db611853d76a98937c7221ad2d85dec38232797`.
- Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.
- Observed HEAD: `b389b2caaabfd0ba5d4584432f97eaab5f537e36`, including the implementation-report appendix. The three reviewed code/test files have no difference from the exact code commit.
- The supplied `task-1-covering-8f42995-4db6118.diff` body exactly equals the immutable Git diff with ten context lines. Its complete scope is `context_runtime_history_cache.py`, `context_runtime_tennis.py` and `tests/test_context_runtime_capacity.py`: 180 insertions, 2 deletions.
- Read the entire recovery plan and Task 1 implementation report, including the third-refinement appendix; read the final native capacity/observational evidence sections. Applied the code-review, TDD evidence and verification-before-completion skills. Task 2 files and its active work were not reviewed or changed.

## Strengths and requirement checks

1. **Full physical validation still precedes production replay.** `context_runtime.py:382-387,524-529` finishes `receipts.validate_all()` before original/snapshot replay. The unchanged inventory implementation checks every content, every receipt and orphan contents before publishing its stamp (`context_runtime_inventory.py:89-127`). Future, inactive and unreferenced rows therefore do not acquire a new validation exemption. Protected content bodies remain opaque (`context_runtime_inventory.py:97-108,150-155`).
2. **The prefix proof matches the actual owner, not measured row-count similarity.** The unchanged owner excludes only future/irrelevant-schema rows, adds fields derived from each receipt's own clock, validates eligible receipts before its tour filter, then sorts by `(observed_at,digest)` (`context_sources/tennis_status.py:279-298`). It enforces canonical receipt clocks and evidence fields (`context_sources/tennis_status.py:228-251`); canonical timestamps are fixed UTC microseconds (`context_models/contracts.py:46-54`). Consequently a successful same-tour later selection covers exactly the earlier inclusive prefix. No competition, participant, native revision, event or model pruning is introduced.
3. **Exact hits remain first, with unchanged typed arguments.** `context_runtime_tennis.py:85-98` invokes the owning empty-tuple validation, returns exact hits first, attempts covering only after a miss, and falls back cold only on `None`. A valid empty covering tuple does not accidentally trigger cold reconstruction.
4. **Covering reuse requires the completed capability and all lifetime pins.** `context_runtime_history_cache.py:83-110` checks the exact cache lifetime and mapping validation before choosing the nearest strictly later same-tour key. A never-validated mapping cannot use covering; failed validation rejects through the mapping's permanent failure check. Existing mapping identity, transaction generation, `total_changes`, main schema and temp schema pins remain enforced (`context_runtime_history_cache.py:20-63`; `context_runtime_inventory.py:67-87`). Checks run before reconstruction, before/after every decoded row and at completion, including an empty parent or empty result.
5. **Fresh ownership and selected-only admission are preserved.** The new loop decodes one immutable canonical row at a time, stops at the first excluded future row, charges only retained canonical bytes and returns a real tuple (`context_runtime_history_cache.py:95-110`). It does not construct a second whole later decoded history. A parent larger than the earlier request's admission ceiling can be used if the complete earlier prefix fits; an oversized prefix rejects without publication.
6. **Children are independently stored, not aliases.** The unchanged store freshly encodes the completed child under the existing aggregate byte and entry ceilings (`context_runtime_history_cache.py:117-144`). Pending encoding is never published before completion and always clears its pending charge. Parent eviction cannot truncate or invalidate an admitted child. Cache pressure may evict/bypass but does not grant partial causal history.
7. **The tests exercise the new behavior and its boundaries.** Later-first parity compares against the unchanged full owning selector and mutates consumer payloads (`tests/test_context_runtime_capacity.py:329-352`). Selected-byte admission and empty results are checked at `355-372`; four cold-fallback controls at `375-393`; real write/DDL/temp/transaction/closure operations during covering decode at `396-422`; interruption/nonpublication/retry at `425-447`; independent child reuse after parent eviction at `450-470`. Existing adjacent corruption and failed-validation tests were read at `556-589,645-760`; they were not claimed as freshly rerun by this reviewer.
8. **Actual unopened-final protection was inspected without repeating the expensive fixture.** `tests/test_context_runtime_capacity.py:211-253` guards the real receipt decoder, validates the full inventory, retains opaque finals at an earlier clock, exercises exact and covering empty histories, performs complete D4 verification, then rejects unrelated ordinary corruption. The author's latest recorded run includes this amended test once; this review does not relabel that historical run as independent fresh execution.

## Issues

- Critical: none found in the reviewed change.
- Important: none found in the reviewed change.
- Minor: none requiring a change.

## Fresh independent verification

Executed in the exact worktree with the quality Python and `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` each set to `1`:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest tests/test_context_runtime_capacity.py -k covering_history -q -p no:cacheprovider --tb=short --basetemp=.pytest_tmp/capacity-covering-independent-review-4db6118 --durations=3
```

Result: **21 passed, 92 deselected in 6.63s**, exit 0. No warnings or errors appeared. No full suite, adjacent suite or redundant protected-final run was executed.

Additional read-only verification:

- Supplied diff equals immutable Git diff: `True`.
- Exact change-range whitespace check: exit 0.
- No change in the exact range to `model_artifacts.py`, `context_models`, `context_sources`, `tennis`, `context_runtime_inventory.py`, `context_runtime.py`, `scripts` or `deploy`.
- Protected `scripts/stage_runtime_databases.py` SHA-256 remains `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

The implementation report records clean pre-implementation RED **17 failed / 4 controls passed**, then GREEN **21 passed**, and adjacent **234 passed / 12 skipped**, including the actual protected-final case at 71.23s (`task-1-implementation.md:246-255`). These are explicitly author-recorded evidence, not additional reviewer executions.

## Assessment and remaining gates

The refinement implements the approved covering-later algorithm without changing the owning selector, numerical replay, source hashes, public report, physical-validation contract or resource ceilings. It is suitable for continued integration and exact-revision native verification.

The last completed native largest-generation result supplied to this review is still the `8249c28` CPU HOLD: 299.949 CPU seconds, no report. The controller's fresh `4db6118` native run is separate and no result is inferred here. Current data, the largest profile, multiple growth generations and final integrated Linux capacity/release evidence remain required. No network/VPS operation, Git mutation, production/test edit, delegation or deployment was performed; only this review report was added.
