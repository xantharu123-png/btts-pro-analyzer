# Task 10: actual POINT originals and owning verification

Status: DONE (local unpublished prerequisite package; no fit/activation/release).

Final correctly configured focused QA: 472 passed, zero failures/skips in
91.15s. Separate unchanged cache/shadow verification: 44 passed, 3 existing
platform skips in 5.80s. The earlier expanded run and its diagnosed environment
failures remain preserved below; this is not a whole-suite or production claim.

Canonical checkout: C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013.
Base remains 242093feda28a31bb8729e31529032ee059b570a.
Inherited read-only source: C:/Projekt/BetBoy/betboy-app, HEAD c5a6264.
Evidence: C:/Projekt/BetBoy/output/context-completion-20261014/point.

## Implemented scope

Only the approved original POINT hunks were adopted from root-vs-c5a6264 in
tennis/predict.py, tennis/live_context.py and scripts/tennis_daily.py, through
apply_patch. No whole old file replaced a canonical owner. The two genuinely
new inherited files were also adopted through apply_patch; root was not edited.

Production files changed:

- tennis/predict.py: opt-in same-call POINT capture after the existing actual
  joint simulation; no new model calculation or output adjustment.
- tennis/live_context.py: same-call market equality checks, immutable
  publication, and bounded score reads of only native events already received
  by this batch.
- scripts/tennis_daily.py: owning scan and pending-refresh callback plumbing.
- context_models/tennis_point_original.py: adopted finite joint distributions,
  actual post-preparation publication clock, source/state/native binding and
  existing bilateral native final-score reads. Completed full Winner replay,
  closed capture-source admission and D4 inventory ownership.
- context_runtime_tennis.py: two explicit capture-only source families and
  directional predecessor compatibility; shared complete Winner numerical
  replay under all six source owners and the sealed causal state.
- context_runtime.py: recognized POINT kind and same-held-transaction owning
  validation after physical receipts and Winner inventory, regardless of
  slots, snapshots or activation.

Tests changed:

- tests/test_tennis_point_original.py: inherited offline tests adopted unchanged
  apart from line endings.
- tests/test_tennis_point_completion.py: new independently failing SQLite
  regressions for missing capture, ATP/WTA source identity, direct full Winner
  replay, closed/directional/mixed families, physical clocks, self-hashed
  corruption, inactive/orphan artifacts, and no retrospective POINT label.
- tests/test_context_runtime_tennis_live.py: predecessor tests retain literal
  old predict identities rather than assuming the current capture source is
  byte-identical. Test graph helper rehashes linked POINT artifacts so a dangling
  reference cannot mask the intended Winner semantic test. Historical
  Winner-only fixtures explicitly have no fictional POINT original.

## Source-family and integrity boundaries

All nine existing definitions remain literally unchanged: locator,
pre-duration, duration, reconciled-duration, results-placeholder,
recent-training, POINT-joint, causal-availability and cached-training.

The inherited root loader is the older POINT-joint/results-loader owner, not
the causal loader. Its actual SHA-256 is
bf2abc8cdade308363f477b37fb15a6d16554fcf12d4b218bd0f033116ca32c4.
The new predict LF/CRLF identities are independently pinned as
1bcfd397dabda9a0cf075894d2d3c1dc4a191fe9ce880652e050b6e3257dfebe and
5c730696f81b621ef02a461d32d91cddf118dbb40d65264c9699b4bff28a7a2d.

Added _REVIEWED_POINT_CAPTURE_MANIFEST for that actual inherited combination,
and _REVIEWED_CACHED_POINT_CAPTURE_MANIFEST for canonical adoption with the
current cache-only loader. No unsupported causal-loader/capture hybrid is
blessed. Arbitrary running bytes cannot self-certify by equality; unknown and
mixed full families fail closed. Reverse replay of future capture originals
under prior executors remains rejected. Loader acquisition changes do not
change any numerical model.

The publisher and both readers reject a POINT artifact whose Winner owner was
produced by a prior Winner-only source generation. No old Winner original is
relabelled. The direct reader now replays every unrounded Winner input/value
with the same owning calculation used by D4, verifies the actual market sheet
exists, and compares its entire POINT projection. It still binds the physical
predecision state and latest native input receipt, not names or a stored scalar.

D4 checks every POINT artifact, including inactive, orphaned and future physical
entries. Missing/wrong Winner owners, altered events/joint mass and impossible
publication chronology fail even when the bodies and references are rehashed.

## RED / GREEN commands and results

All commands used workdir exactly the canonical checkout and this common
offline prefix:

    C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe -B C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py

Every basetemp below is new and absolute under the evidence directory. Its
parent was created by apply_patch sentinel, not reuse or deletion.

1. RED before production adoption:

       <prefix> tests/test_tennis_point_completion.py -q --basetemp=<evidence>/pytest-red-initial

   Exit 1: 3 failed in 6.22s. Missing actual artifact: 0 != 1; ATP and WTA:
   point joint Tennis state lacks its reviewed versioned code identity.
   Evidence: red-initial.md and physical SQLite fixtures.

2. RED exact inherited/current source families:

       <prefix> tests/test_tennis_point_completion.py -q --tb=short --basetemp=<evidence>/pytest-red-families

   Exit 1: 4 failed, 1 passed in 6.71s. Both actual capture-source combinations
   fail ATP/WTA state binding. Evidence: red-source-families.txt. A first
   diagnostic hypothesis used causal-loader/capture; read-only root SHA checks
   corrected it to the actual older root family before this retained RED.

3. RED complete integrity regressions:

       <prefix> tests/test_tennis_point_completion.py -q --tb=short --basetemp=<evidence>/pytest-red-integrity

   Exit 1: 21 failed, 3 passed in 23.88s. Rehashed D4 corruption was admitted,
   direct reads ignored altered p_a_raw and four other source owners, complete
   newline-equivalent source families failed, and unknown running source
   equality self-certified. Evidence: red-integrity.txt.

4. Initial owning GREEN after implementation:

       <prefix> tests/test_tennis_point_completion.py tests/test_tennis_point_original.py tests/test_context_runtime_tennis_live.py -q --tb=short --basetemp=<evidence>/pytest-green-owning

   Exit 0: 230 passed in 111.38s. Evidence: green-owning-initial.txt.

5. RED no retrospective label:

       <prefix> tests/test_tennis_point_completion.py -k 'relabelled or synthesized' -q --tb=short --basetemp=<evidence>/pytest-red-no-relabel

   Exit 1: 2 failed, 1 passed, 26 deselected in 7.88s. Direct POINT and D4
   wrongly accepted a retrofitted prior Winner-only source; synthesized
   Elo-only WTA markets already failed. Evidence: red-no-relabel.txt.

6. GREEN after no-relabel reader gates:

       <prefix> tests/test_tennis_point_completion.py tests/test_tennis_point_original.py -q --tb=short --basetemp=<evidence>/pytest-green-no-relabel

   Exit 0: 63 passed in 36.00s. Evidence: green-no-relabel.txt.

7. RED publisher gate:

       <prefix> tests/test_tennis_point_completion.py -k 'publisher or inactive or transitions or executor or full_family or causal_loader' -q --tb=short --basetemp=<evidence>/pytest-red-publisher

   Exit 1: 1 failed, 17 passed, 29 deselected in 7.52s. Publisher accepted the
   prior Winner-only family before insert. Source gate is now shared by
   publication and read paths. Evidence: red-publisher.txt.

8. Extended integration command selected exactly these 16 files:

       <prefix> tests/test_tennis_point_completion.py tests/test_tennis_point_original.py tests/test_context_runtime_tennis_live.py tests/test_tennis_live_worker.py tests/test_tennis_live_legacy_parity.py tests/test_context_tennis_outcome_capture.py tests/test_tennis_result_training.py tests/test_tennis_training_cache.py tests/test_tennis_training_refresh.py tests/test_tennis_prediction_revisions.py tests/test_tennis_predict.py tests/test_tennis_completion_scaling.py tests/test_shadow_markets.py tests/test_context_runtime_coordinated_tennis.py tests/test_context_runtime_shared_history.py tests/test_context_runtime_original_projection.py -q --tb=short --basetemp=<evidence>/pytest-green-integration

   Exit 1: 19 failed, 743 passed, 3 skipped in 468.59s. This was NOT a full
   suite or a clean all-green run. All failures were traced and retained in
   integration-complete.txt; no source correction was made to those modules.
   This first command did not request JUnit; no retrospective JUnit is invented.

9. Isolated environment diagnosis, using canonical QA settings and scoped TEMP:

       <prefix> tests/test_tennis_training_cache.py tests/test_shadow_markets.py -q --tb=short --junitxml=<evidence>/isolated-default.xml --basetemp=<evidence>/pytest-isolated-default

   Exit 1: 10 failed, 34 passed, 3 skipped in 10.91s. The workspace TEMP
   fixed all Shadow failures; all ten remaining failures reproduce os.link's
   AppContainer PermissionError [WinError 5]. Evidence: isolated-default.txt
   and the actual pytest JUnit isolated-default.xml.

10. Same unchanged isolated modules outside AppContainer, scoped offline QA:

        <prefix> tests/test_tennis_training_cache.py tests/test_shadow_markets.py -q --tb=short --junitxml=<evidence>/isolated-unsandboxed.xml --basetemp=<evidence>/pytest-isolated-unsandboxed

    Exit 0: 44 passed, 3 skipped in 5.80s. Evidence: isolated-unsandboxed.txt/.xml.
    The hardlink operation succeeds without weakening its no-overwrite semantics.
    Source hashes are unchanged before/after this execution-environment test.

11. Final correctly configured focused integration:

        <prefix> tests/test_tennis_point_completion.py tests/test_tennis_point_original.py tests/test_context_runtime_tennis_live.py tests/test_tennis_live_worker.py tests/test_tennis_live_legacy_parity.py tests/test_tennis_result_training.py tests/test_tennis_training_refresh.py tests/test_tennis_prediction_revisions.py tests/test_tennis_predict.py -q --tb=short --junitxml=<evidence>/final-focused.xml --basetemp=<evidence>/pytest-final-focused

    Exit 0: 472 passed, zero failures/skips in 91.15s. Actual pytest JUnit:
    final-focused.xml; complete console: final-focused.txt. No production
    source changed between the failed sandbox diagnosis and these successful
    reruns; the before-rerun hashes remain the final code hashes.

Corrected QA environment for commands 9-11:

    DJANGO_SETTINGS_MODULE=siteconfig.qa_settings
    PYTHONPATH=C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013/portal
    TMP=TEMP=<evidence>/tmp-diagnostic (9) or <evidence>/tmp-final (10-11)

Commands 10-11 used require_escalated for the diagnosed AppContainer hardlink
restriction. Tests still use the offline launcher; no provider request,
production path or production write was authorized or performed.

## Exact unexpected failures and causal separation

Training-cache failures (all PermissionError at runtime_paths.py:326 os.link):

- test_missing_default_cache_seeds_atp_without_http
- test_refresh_changes_only_mutable_cache_and_uses_seed_baseline
- test_seeded_completed_history_is_checked_before_metadata_refresh
- test_seed_publication_never_overwrites_a_concurrent_fresh_cache
- test_market_calibration_sources_seed_without_http[atp]
- test_market_calibration_sources_seed_without_http[wta]
- test_wta_refresh_preserves_packaged_workbook
- test_tennis_abstract_sources_seed_without_http
- test_daily_surface_lookup_reads_seed_with_cold_runtime_cache
- test_configured_runtime_root_controls_omitted_default_cache

Shadow failures (AppContainer default TEMP SQLite open or cleanup permissions):

- ModelFirstShadowTest::test_closing_requires_provider_update_inside_final_window
- ShadowConditionTest::test_artifact_counts_only_current_model_and_policy
- ShadowConditionTest::test_legacy_schedule_marker_does_not_hide_new_model_run
- ShadowConditionTest::test_missing_tomorrow_schedule_is_due_only_after_nine_zurich
- ShadowConditionTest::test_settlement_retry_is_not_due_every_ten_minutes
- ShadowConditionTest::test_stays_idle_without_due_work
- ShadowConditionTest::test_uses_production_evaluation_window
- ShadowVersionLifecycleTest::test_cache_path_changes_with_model_version
- ShadowVersionLifecycleTest::test_legacy_prediction_does_not_block_current_model

These were not labelled pre-existing source regressions: baseline full QA was
already green according to the controller. Reproduction without the new POINT
test modules, the scoped TEMP change and the isolated unsandboxed success
establish execution-environment causes rather than monkeypatch/cache leaks.
No tests were skipped or altered to suppress these failures.

## Unchanged contracts / remaining gates

- Forecasts and all simulator markets are byte/float exact with capture on/off,
  including Bo3/Bo5, legacy/default paths and separate ATP/WTA states.
- WTA Elo-only states do not simulate serve markets: preserve their real Winner
  original, never fabricate POINT parameters just to populate a family.
- Existing a3f465c cached-result bridge, known-time result chronology, CAS/date
  and acquisition guards stay unchanged and are included in the focused QA.
- Native results require both existing workload receipts, actual winner flags,
  mirrored complete legal sets and newest received revision. No invented exact
  duration/end, best-of evidence, injury, service success/trial or coefficient.
- No extra outcomes are published, no old forecast/money row is rewritten,
  no quote/ranking/stake change, no POINT fit or effect activation, no evaluator,
  training, approval or Cricket change.
- No provider/API scan, backup, migration, commit, push or deployment. Controller
  owns shared index, one final complete suite and all publication/release gates.
- The unchanged empirical gate remains 200 untouched events, three time blocks,
  paired Brier improvement, logloss/calibration and multiplicity checks.
- git diff --check is clean. Scoped code/test evidence is implementation.patch;
  source-hashes-before-environment-rerun.txt records all changed owners plus the
  unchanged loader/runtime/shadow modules.

Next gate: controller's final complete QA and scoped integration checkpoint.
This prerequisite package does not certify an empirical POINT effect.
