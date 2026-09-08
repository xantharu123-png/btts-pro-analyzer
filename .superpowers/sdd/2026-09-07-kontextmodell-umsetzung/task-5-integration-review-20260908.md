# B1 / released UI / A3–A4 — bounded integration review

Date: 2026-09-08.

Verdict: **No integration findings in exact
`0c50c5ab2a30c1ffd1f35a62be9c4dda863306b3`.**

This accepts the checked integration of previously reviewed bytes, not a new
source certification, empirical/model approval, production activation or
completion of the wider context-model plan. The separate B2 worktree was not
inspected and is outside this review.

## Exact Git identity checks

Compared `git ls-tree -r` entries, including path, file mode, object type and
full Git blob identity. This is an exact Git-content comparison, not an
inference from clean merge messages or working-copy timestamps.

| Group | Reviewed reference | Files | Result |
| --- | --- | ---: | --- |
| B1 source and tests | `22164fdf577190fa17f9aeddebd1b810ca4c59a1` | 5 | Exact blob/mode match |
| Released card-analysis source and tests | `4f3ecd5db75cb6f4f466270a568ede742d4ed767` | 10 | Exact blob/mode match |
| Tennis, A1 foundations, A3/A4 entry points and relevant tests | `2436dd411987ba0b543fd73212da6cbb72d65e99` | 30 | Exact blob/mode match |

B1's exact five entries:

```text
a24dcc06b6c2e8fea839996001bf33b31c6016a6 context_models/__init__.py
df50878290d824c0b36ca88e1296bbd4d39365ba context_models/contracts.py
6c76b20faec358118de34f2d30b0f36a846a1ce2 context_observations.py
0f58e3442e621c943ba1a34fc9c68101b1ca08e3 tests/test_context_contracts.py
b4663eb59087a978a523b2228e306e648d9db3e4 tests/test_context_observations.py
```

The ten UI paths are `app.py`, `ev_signal_sources.py`, `forecast_analysis.py`,
`wettfinder_automation.py`, `wettfinder_surface.py`, and their five affected
tests: `test_ev_signal_sources.py`, `test_forecast_analysis.py`,
`test_wettfinder_automation.py`, `test_wettfinder_surface.py`,
`test_workflow_integrity.py` under `tests/`.

The 30 A1–A4 comparison paths comprise all 14 Python modules under `tennis/`,
`model_artifacts.py`, `runtime_paths.py`, `scripts/rebuild_state.py`,
`scripts/run_daily_pipeline.py`, `scripts/tennis_daily.py`, plus the 11 tests
`test_model_artifacts`, `test_scan_jobs`, `test_serve_admission`,
`test_tennis_fixture_metadata`, `test_tennis_pending_refresh`,
`test_tennis_pipeline`, `test_tennis_prediction_revisions`,
`test_tennis_state_codec`, `test_tennis_tour_readers`, `test_tennis_tour_state`,
and `test_tennis_training_refresh` under `tests/` with `.py` extension.

The final merge has parents
`c8f2270c5e5701675addaf47391a63571104474c` and
`4f3ecd5db75cb6f4f466270a568ede742d4ed767`. Its first-parent diff contains only
the released UI source/tests and associated documentation. The preceding B1
merge adds only the five reviewed B1 files and its six preserved review/report
files. No reviewed source was silently replaced by the other branch.

## Generated data and pinned helper

Both actual merge diffs were inspected by path/status and the UI merge by
numstat. Neither merge introduces a generated database, model artifact, cache,
archive, downloaded dataset or binary. No merge change appears under
`output`, `data`, `state`, `models`, `.pytest_tmp` or `.playwright-cli`.

The two tracked Python proof scripts under `output/context-evaluation/`
(`tour_build_on_vps_probe.py` and `tour_restore_probe.py`) already belong to the
controller's pre-merge `92c947e` history; they were not imported by these merges
and were not executed by this review. Four local untracked controller artifacts
were observed and left untouched: the two `tour-restore-source` tar variants,
`tour_atp_diagnose.py`, and `tour_offline_probe.py`. They are not part of the
reviewed Git commit.

`scripts/stage_runtime_databases.py` has the identical Git blob
`ff16f8a6639a0c166b1eec2a04656c6518bab2b8` at all four compared references.
Its integration working-copy raw SHA-256 is still the pinned
`1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.
Its inherited false modified status was not repaired, staged or otherwise
touched.

## Preserved B1 evidence and line endings

The original report/reproduction Git blobs match preserved commit
`250c8c0bfc3c63e231a40e5f3356a4054040558d` exactly:

- `task-5-independent-review.md`: Git blob
  `13288ee0b53f23a818f7da2d5cbae109ef13b788`.
- `task-5-review-repros.py`: Git blob
  `fcd288691d2508c7f0d6d4748cf45bac15206923`.

Important working-copy distinction: `git ls-files --eol` reports `i/lf w/crlf`
for these two files. Their raw Windows working-copy hashes therefore differ
from the original LF hashes; this is not a changed Git blob. An in-memory
CRLF-to-LF comparison independently reproduces the original immutable SHA-256
values exactly:

```text
3cb7f832d93695b40794017eeffa7254024ddb038f9af1ec3619ed885a5b1b8e task-5-independent-review.md
bdc4c2a31bf9338e770f5e20e92126f8051b2bbb41d12fb994698296712d7ac7 task-5-review-repros.py
```

No file was rewritten to normalize these line endings. The adapted
`task-5-rereview-repros-20260908.py` was also compared against reconstruction
of the exact approved owned transformation of the original. Its executable
content matches; only trailing newline hygiene is disregarded in that
comparison. The controller's rerun of all 18 adapted cases remains separate
reported evidence, not claimed as an additional run by this reviewer.

## Import and contract interaction

The B1 observation layer still imports the exact reviewed A1 `_connect`, strict
decoder and canonical serializer. Its contracts still use the same canonical
serializer. No released UI module imports B1 or promotes audit `refs` into
numeric context provenance; the approved `usable_refs` boundary remains for
the future feature producers.

The released signal layer imports its card-analysis projection and the
integrated `tennis.predict` / `tennis.shadow` modules. Its public automatic
readers and football context-refresh projection were therefore selected for a
small combined regression together with the B1/A1 receipt and typed-contract
paths. Tests use synthetic files and fixed clocks; the automatic-reader cases
explicitly forbid provider requests.

Executed from the integration checkout with a previously absent basetemp:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider tests/test_ev_signal_sources.py::test_both_automated_builders_retain_exact_analysis_and_original_model_clocks tests/test_ev_signal_sources.py::test_both_real_automatic_readers_reject_only_future_analysis_using_one_shared_clock tests/test_wettfinder_automation.py::test_football_projection_persists_price_free_analysis_and_context_refresh_backfills_legacy tests/test_wettfinder_automation.py::test_context_refresh_preserves_original_basis_catalog_clocks_for_analysis tests/test_context_observations.py::test_unchanged_recheck_has_new_receipt_not_rewritten_first_observation tests/test_context_contracts.py::test_closed_contracts_roundtrip_without_promoting_missingness --basetemp=.pytest_tmp/b1-integration-focus-20260908-01
```

Result: **9 passed in 2.54s**, exit 0. No import/contract interaction failure
was observed. The combined full suite belongs to the controller's parallel
run; it was not rerun here and its result is not inferred from these nine
checks. No fresh rendered-UI review is claimed.

## Limits and mutation boundary

This review wrote only this report and the isolated test outputs. It performed
no source edit, Git mutation, provider/network call, VPS operation, production
data write or subagent delegation. Controller documentation may subsequently
advance without changing the reviewed source. Data freshness, real source
coverage, empirical effect validation, complete-plan delivery and production
activation remain distinct, unapproved-by-this-review outcomes.
