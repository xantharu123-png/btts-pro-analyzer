# Task 10 final P2: optional POINT finish limits

Status: narrow local implementation and focused verification complete; parent
owns independent review, final whole-package QA, index/checkpoint and release.
No full-suite, commit, API, VPS, backup, fit, activation or release was performed.

Canonical checkout: C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013.
Base remains 242093feda28a31bb8729e31529032ee059b570a.
Evidence: C:/Projekt/BetBoy/output/context-completion-20261014/point-finish-limit.

## Root cause and exact scope

After normal Shadow prediction writes, LiveWorker.finish passed every distinct
native key in capture.pending to point_scores_as_of. The helper rejects more
than 500 before its absent-database return. Thus a valid 501-event collection
aborted after public writes without finished=True or complete progress.

Changed production owners only:

- tennis/live_context.py: preserve the entire forecast finish, but decline the
  whole optional read when the captured distinct-key count exceeds 500. No
  helper/database call, truncated subset or uncapped loop in that branch.
  point_outcomes remains empty. Internal point_scores_decline records explicit
  reason/event_count/limit; existing progress receives point_scores_declined.
- context_models/tennis_point_original.py: name the unchanged 500 bound
  MAX_SCORE_EVENT_KEYS, and narrowly type existing 2048-original/128MiB admission
  exhaustion as PointScoreAdmissionLimit, a ContextContractError subclass.
  Only this explicit typed exhaustion is nonfatal in the optional worker.
  Direct helper calls still reject all the same finite limits.

The parent additionally requested consideration of valid finite admission
exhaustion below 500 keys. Repeated original revisions can exceed 2048, so this
was included with real valid POINT artifacts and small test-only lowered
budgets. Count metadata is original_count_at_least, because the strict query
reads only limit+1 headers; it never claims a complete original count. Byte
metadata is the measured original_bytes from the bounded admitted header set.
The current 128MiB limit cannot be reached under 2048 compact publication bodies
(maximum 69,206,016 bytes), but it remains enforced and explicitly tested with
a lowered test-only byte budget. No production cap was raised or removed.

No generic ContextContractError/ContextIntegrityError/RuntimeError catch was
added. Real corrupt admission headers, native scope and clock validation,
source/replay validation and unexpected helper failures remain rejecting.
Double finish still rejects. No model, quote, stake, source identity, receipt
clock, public forecast, original schema or activation change.

New tests only: tests/test_tennis_point_finish_limit.py. No existing test was
removed, modified, deselected from the neighbor command or forcibly skipped.
Frozen football and restored context_models/tennis_training.py were not edited.
The diagnostic candidate selector tests were not touched or selected.

## Actual RED/GREEN results

Common command prefix (workdir exactly canonical):

    C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe -B C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py

All commands set:

    DJANGO_SETTINGS_MODULE=siteconfig.qa_settings
    PYTHONPATH=C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013/portal
    TMP=TEMP=<evidence>/<dedicated tmp directory>

Each command used -q -p no:cacheprovider --tb=short, a fresh absolute basetemp
and actual pytest --junitxml; console was redirected to its evidence .txt.
The supplied launcher disables external network; no source/provider request.

1. Before any production fix:

       <prefix> tests/test_tennis_point_finish_limit.py ... --junitxml=<evidence>/red-finish.xml --basetemp=<evidence>/pytest-red-finish

   TMP/TEMP=<evidence>/tmp-red. Exit 1: 4 failed, 3 passed in 9.14s.
   Console red-finish.txt; actual JUnit red-finish.xml.
   Exact failures:
   - test_real_finish_keeps_optional_event_limit_nonfatal_without_a_database[500]:
     missing new observable point_scores_decline property (AttributeError).
   - test_real_finish_keeps_optional_event_limit_nonfatal_without_a_database[501]:
     real helper ContextContractError: requires explicit native event scopes.
   - test_oversized_captured_backlog_finishes_queued_forecast_exactly[legacy]:
     same real helper ContextContractError after valid forecast writes.
   - test_oversized_captured_backlog_finishes_queued_forecast_exactly[linked-public]:
     same real helper ContextContractError after valid forecast writes.

2. Additional parent-authorized finite admission RED, still before production fix:

       <prefix> tests/test_tennis_point_finish_limit.py -k finite_admission ... --junitxml=<evidence>/red-budget.xml --basetemp=<evidence>/pytest-red-budget

   TMP/TEMP=<evidence>/tmp-red-budget. Exit 1: 2 failed, 7 deselected in 6.83s.
   Both test_optional_finish_declines_only_explicit_finite_admission_exhaustion
   [count] and [bytes] raised the real helper's generic finite-admission
   ContextContractError. Fixtures contained a real replay-verified POINT
   original; no error-return stub stood in for production admission.
   Console red-budget.txt; actual JUnit red-budget.xml.

3. After the narrow implementation:

       <prefix> tests/test_tennis_point_finish_limit.py ... --junitxml=<evidence>/green-finish.xml --basetemp=<evidence>/pytest-green-finish

   TMP/TEMP=<evidence>/tmp-green. Exit 0: 9 passed in 5.53s.
   Console green-finish.txt; actual JUnit green-finish.xml.
   Includes real finish at 500/501, no DB/API access on oversize, complete and
   finished state, empty scores, exact decline metadata, direct-helper strict
   rejection of 501 valid native keys, double finish, real corrupt admission
   failure and unexpected helper failure propagation.
   Actual legacy and linked-public forecasts are queued and stored with 500
   completed native historical backlog events plus their current event. Their
   customer-visible numbers, markets/gates bytes and non-link context exactly
   equal a valid single-current-event baseline. Decline metadata never enters
   the customer's stored context_json.

4. Minimal owning neighbors (exact file selector):

       <prefix> tests/test_tennis_point_finish_limit.py tests/test_tennis_live_worker.py tests/test_tennis_point_original.py tests/test_tennis_point_completion.py tests/test_tennis_training_cache.py ... --junitxml=<evidence>/green-owning-neighbors.xml --basetemp=<evidence>/pytest-green-owning-neighbors

   TMP/TEMP=<evidence>/tmp-neighbors. Scoped require_escalated execution avoids
   the previously diagnosed AppContainer hardlink restriction; still offline
   with only private fixture databases/cache directories.
   Exit 0: 131 passed, 3 existing platform skips in 30.31s, zero failures.
   Console green-owning-neighbors.txt; actual JUnit green-owning-neighbors.xml.
   Exact existing skips (Windows lacks symlink privilege, WinError 1314):
   - test_default_seed_transfer_rejects_symlinks[seed]
   - test_default_seed_transfer_rejects_symlinks[runtime_file]
   - test_default_seed_transfer_rejects_symlinks[runtime_parent]

git diff --check is clean. The prior combined final sessions 85970/22709 were
parent-stopped with exit 1/no final JUnit before this P2 fix; neither those
partial runs nor these focused runs establish whole-package PASS.

## Final source SHA-256

Changed by this task:

- tennis/live_context.py:
  e5a3ae90e05190e5415e4161867ffacc8d132ee61ec8bf36a31cf44351e5727d
- context_models/tennis_point_original.py:
  80f0305e8023ac504d35ff8be98d64c2adc48d25e3f20d2b6ee103beef28ea53
- tests/test_tennis_point_finish_limit.py:
  2d60501e19458fcf85260ee74447f94cde3d499826edc6d7adc550e27a8c3836

Observed unchanged neighbors at handoff (not edited by this task):

- context_models/tennis_training.py:
  28a94651d30d1a226c14a349255b498fa2fd0c006af05925bc52e0e9fbb9cceb
- tennis/predict.py:
  5c730696f81b621ef02a461d32d91cddf118dbb40d65264c9699b4bff28a7a2d
- context_runtime_tennis.py:
  8c0a1c64815e6f96bba0c078ef2e15490abeda9d5636afc7a1604af9d85303c5
- football_joint_worker.py:
  30eebba2c9675927fa60e8c84b9c86e9b298442f73ce6b7ef34bf8412c7e3dc5
- context_models/football_training.py:
  86be1ff53206d2b7feef18c1db6c044ff60f8af6d41dc92b791b4d5d9b7c1f44
- context_models/football_readiness.py:
  db8f26ef80f0906aa6ab052a785df854f48393f4cccdc3431e37a92fde7a84ff
- context_models/dataset.py:
  097be149cf1038ecead064543af126d64a0e7ec31b879023de113e7f5ac6e051
- context_runtime.py:
  97958e81a912efc8aab401b37a093789f057158a0dad8032d6d36f4f658e57f6
- context_runtime_semantics.py:
  e44972dee05c86c900d9c8dfa80e011534a3f3ddb40c1030c67e7416a3fed3c8
- scripts/tennis_daily.py:
  c55a5ae14a29041c627a0dcaf8dafe9def4816dac8e20752888ff30f02db5f9b

No source changed between own GREEN and neighbor GREEN. This implementer did
not capture independent pre-P2 source hashes; the parent owns its frozen
pre-P2 manifest and comparison. No pre-edit hashes are invented here.

Next gate: parent independent review, then one fresh whole-final QA against
the complete final source freeze. This fix is not production/release approval.
