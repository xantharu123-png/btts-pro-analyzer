# Task10 P2 correction — independent scoped rereview

Date: 2026-09-11. Verdict: **Approved for this corrected Task10 delta.**
The sole P2 in `task-10-review.md` is resolved. This is not release approval.

## Immutable identity and scope

Reviewed correction:
`4a27fb98f2379866a90abf3031082ab9a0fd4bf4` ->
`72421d3bdbec4ab15a3d2953cb153e867e7e340a`.
Verified package `.pytest_tmp/review-4a27fb9..72421d3.diff` SHA256:
`5e09177f885b49b813bb94da424fe0d3d683375cfbc067234b1998f77f467153`.

Read the complete correction diff including author-report append and four new
test cases. Each production change adds only the exact connection-type check
to its after-main schema guard. All previous 117 dispatch cases remain
textually unchanged; the new parametrized test adds four cases. No unrelated
product/test change appears. Working files match this candidate and immutable
`git diff --check` succeeds.

Verified working-byte hashes:

```text
context_runtime_history_cache.py 2f13f3064222a5ee9e7fa5a432ff47b36e611322ccede3e31217c2400e8178cc
context_runtime_inventory.py 2425653f02b1ff4b11fd6ec39f13bb9a3ca5061b3185af65cc41c44a816e36de
tests/test_context_runtime_check_dispatch.py 56f4f697b6a4e89b692afc9364f79539f2bc17ce73618c9d74bf690f5bae4848
```

Original review preserved, SHA256 still
`987e9633286070970aaee160cb6459f8aaa93649829dadcefb04ec2d07cef75c`.

## Resolution and independent verification

`context_runtime_inventory.py:91-98` and
`context_runtime_history_cache.py:129-136` now reject cursor reuse when the
actual connection becomes a subclass during main PRAGMA. The second read then
uses the original `connection.execute` dispatch, preserving both a delegating
override and an exception-producing override. The initial tracked cursor still
closes in either outcome. The exact unchanged connection route still allocates
one cursor. No checking boundary, SQL statement, cookie, cap or error-cleanup
clause was removed.

The new tests exercise actual SQLite trace callbacks and actual cursor
allocations, not mocked schema answers. They assert the dynamic subclass,
single temp override call, actual SQL order, exception propagation, expected
cursor allocation count and initial cursor closure. Their four outcomes cover
inventory/cache times delegation/veto. No new actionable finding remains.

Independent command, cwd
`C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
$env:VECLIB_MAXIMUM_THREADS='1'
$env:BLIS_NUM_THREADS='1'
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_check_dispatch.py -k 'trace_callback_connection_class_transition or cleanup or local_cursor_closed or exact_schema_boundary' --basetemp=.pytest_tmp/task10-review-p2-fix-1
```

Result: **24 passed, 97 deselected in 1.69s**, exit 0. This includes the four
new transition cases and focused success/failure cleanup, primary-error
preservation and ordinary exact-route allocation controls. Process completed;
no broad cohort or fullsuite was run by this rereviewer.

Independently reran the exact executable `-B -c` reproducer printed in the
original review, unchanged, against the original pre-Task10 base
`40d40147c9468bbe874f3b1cc90873c20911f7c6` and corrected current modules.
Original modules were read by `git show` into ephemeral namespaces; the test
used real in-memory SQLite connections and wrote no helper or product file.
The former return-versus-error divergence is gone. Actual output, exit 0:

```text
inventory base OperationalError second dispatch veto override_calls ['PRAGMA temp.schema_version']
inventory candidate OperationalError second dispatch veto override_calls ['PRAGMA temp.schema_version']
cache base OperationalError second dispatch veto override_calls ['PRAGMA temp.schema_version']
cache candidate OperationalError second dispatch veto override_calls ['PRAGMA temp.schema_version']
```

The author's reported 4 RED, 239 dispatch/witness GREEN and 56 inventory GREEN
are supporting author evidence, not mislabeled as rereviewer executions.
The earlier review's 235-test execution remains attached to the earlier bytes.

## Handoff boundary

Only this named rereview report is authored. Original review and controller
WIP are preserved; no source/test/helper/index edits, SSH/network, deployment,
fullsuite or subagents. Manual immutable-review workflow; no claim that
unavailable skill tooling ran.

Root may proceed to its exact corrected current-input native FIRST gate.
Current/growth resource acceptance, platform/DAC/race checks, final fullsuite,
fresh backup/actual restore/HMAC, latest-data recheck and publication/deployment
remain separate root gates. This correction grants no capacity claim, changes
no limits/source/predictor/feature contracts, and closes none of the unrelated
Cricket/A0/P4b3/five-sport or daily Tennis HTTP error work.
