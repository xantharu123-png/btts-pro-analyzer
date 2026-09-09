# Tennis live publication/append clock correction — 2026-09-09

This is a narrow follow-up to source commit
`32ac1d8ac739a51f84654c2c41fc27017c95cedd` and evidence-only
`bdf123c173f3b882fe7c0075bda10a7b669c8270`. The previous 5,249-test full
run remains valid pre-correction evidence, not acceptance of this later fix.

## Confirmed defect and authorized boundary

The owning worker validated actual A1 original creation against decision time,
but did not also bind it to the later Shadow append. A publication at 12:30
could be linked by a Shadow revision with append time 12:00:02 and decision
12:00. The parent's two unchanged witnesses reproduced this as two genuine
`DID NOT RAISE ContextContractError` failures, using explicit batch and actual
daily-main routes respectively. No real source or production action was used.

The controller authorized one internal `context_original_published_at` argument:

- It comes from the **actual stored** A1 `created_at` read after `put_artifact`,
  not the requested put time. A content-idempotent put must preserve and use the
  earlier writer's real stored timestamp, even when the new requested time differs.
- The argument is mandatory with a new context/original pair and must be an exact
  canonical UTC ISO string. It cannot precede the original decision. Missing,
  invalid, naive or noncanonical time cannot silently enter the legacy path.
- A new-context preflight checks the append clock before Shadow creation. The
  unchanged actual final append clock is then read **again after BEGIN IMMEDIATE**
  and checked in both initial and later-revision branches. The preflight does
  not become the final clock. A backward clock raises; it is never moved forward.
- No new schema field, persistent payload, prediction ID, quote or money field
  is added. The internal clock is not serialized. Without all three optional
  context arguments the old single-clock/legacy path stays unchanged.
- Cross-database publication is still not a global transaction: an unlinked A1
  original/B3 snapshot may remain after rejection. No invalid Shadow link is written.

## Original witness qualification — not a source fix

The unchanged explicit `run_batch` witness now passes in full, including no Shadow
file creation. The actual-main witness reaches its expected ContextContractError,
then exposes a previously unreachable **review-harness mistake** in its final
`assert not predictions.exists()` assertion. The existing real sequence is:

`_run_daily -> fetch_fixtures(observe_status=shadow.record_fixture_status) -> _connect`.

It legitimately stores a fixture-status observation before prediction publication.
The controller independently confirmed this. That observation must not be deleted
or its capture suppressed to satisfy the invalid no-file assertion. The original
witness is retained byte-identically, not changed or reported as wholly green.

The new permanent actual-main successor verifies the valid contract instead:
ContextContractError, zero `predictions`, zero `prediction_revisions`, and the exact
already-recorded real-path fixture-status rows unchanged before/after the failed
append. A final-clock reversal test additionally traces SQLite and proves the
second clock is read only after BEGIN IMMEDIATE; initial/revision rows stay intact.

## RED/GREEN and frozen run evidence

- Parent original witness source SHA-256:
  `25399d669f97c0833484c712acb0afccd4cf40cfab09e54ecc41619ceedb938b`.
  Copied byte-identically into this worktree's ignored review directory.
- Original pre-fix reproduction: **2 failed**, 1.63 s. JUnit
  `.pytest_tmp/tennis-live-clockfix-root-red-01.xml`, SHA-256
  `bf324f90360949b57d8a802a32175c98c6bfb90423c22023e2a2821c45b0fece`.
- Initial 24 owning cases: **22 failed / 2 passed** before implementation. These
  include the new internal API/type and two-phase read contract, not 22 distinct
  product chronology defects. JUnit `.pytest_tmp/tennis-live-clockfix-owned-red-01.xml`,
  SHA-256 `f2e92472999977561eb08517f234183857505108d11f78f0a356b6b99ae11e92`.
- First combined post-fix run: 25 passed / one failed at the invalid actual-main
  no-file assertion described above. This is not hidden as a fully green run.
- **252 passed / zero skipped**, 12.50 s in the owning-clock, live-integrity,
  live-worker, origin, exact legacy parity, immutable revisions, pending-refresh
  and daily pipeline run. JUnit `.pytest_tmp/tennis-live-clockfix-focused-01.xml`,
  SHA-256 `d4805cd77e3e1b4c8f9310301d0545aa664f8b6800d23f70074b650c67791184`.
- A final SQL transaction-trace strengthening then passed **26 tests**, zero
  skipped, 3.42 s: all **25 new permanent tests** plus the unchanged explicit
  parent witness. No production source changed after the 252-test run; only the
  test gained an additional real BEGIN IMMEDIATE assertion.

New cases cover ±1-microsecond/equality publication boundaries, implicit/explicit
append clocks, actual idempotent older/later publication metadata, a final clock
reversal for both new and existing rows, malformed/missing publication metadata,
orphan metadata, the legacy null path and legitimate status retention.

Python: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`,
always `-B -m pytest -q -p no:cacheprovider`, unique local `.pytest_tmp` basetemps.
The full `tests` suite is started on the source bytes below with
`--basetemp=.pytest_tmp/tennis-live-clockfix-full-01`
`--junitxml=.pytest_tmp/tennis-live-clockfix-full-01.xml`.
**At this source freeze, its final result and independent rereview remain pending.**

## Frozen raw local source identities

```text
tennis/live_context.py 91416948aed90bbd503f83a2ecd330f22be6985562aea9a42f3b2f081f6bc8fd
tennis/shadow.py 9c445cc226ed3b4765177cb54bd1488fde073087d8f176b3cb9409e24eab0ce7
tests/test_tennis_live_publication_clock.py f7f57711abe229a2a5658e833f943cb8fb12fbb1650b808abad0429d43b2d6ca
```

No predictor, calibration, context feature/approval contract, Cricket path, source
capture, consumer/UI, stage helper, historical receipt, server or deployment code
was edited. Local tests cannot grant the still-missing native historical tennis
alias or new-base empirical approval. No merge, push or VPS action was performed.

## Full-suite completion after the source freeze

The full run on source freeze `b566da3b5abc5bf7403baf65fbec45c5717fb8a8`
completed with **5,274 passed, 19 skipped and 97 subtests passed**, exit code 0,
in **862.27 seconds**. JUnit `.pytest_tmp/tennis-live-clockfix-full-01.xml` has
SHA-256 `83488c51a2dfd7a776f6ecbb729fd8f0352969350718736ebce3bedc12f50775`.

All three source/test SHA-256 values above were checked again after completion
and are unchanged. This addition records evidence only; it does not modify the
frozen code, tests or the retained original negative witnesses. The independent
review, later integration and any production deployment remain separate claims.
