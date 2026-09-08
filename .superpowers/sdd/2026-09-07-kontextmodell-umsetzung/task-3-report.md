# Task 3 (A3) implementation evidence

## Current status

DONE. The four initial integration questions were resolved by the controller's
recorded rulings before their implementation. The approved specification, task
brief, exact rulings, implementer template and required TDD references were read.

A3 commit: `8f960fcc0da714930bba206a6c2e3e2bb7c99d69`
(`fix: publish ATP and WTA refreshes independently`).

Separately authorized test-only follow-up:
`d4ece5917cfd099fdcbe66dc0d03fcc3fe5cf598`
(`test: make scan inactivity progress timing deterministic`).

Final committed-state full regression: **1851 passed, 15 skipped,
97 subtests passed in 65.07s**, exit 0, no warnings.

## Initial integration questions, subsequently resolved by controller

1. Keep logical `as_of` training cutoff separate from actual completion time and
   actual publication receipt time. Proposed optional injected publication clock
   for deterministic synthetic tests; production defaults to actual UTC time.
   Explicit A2 decision-cutoff validation must use the publication decision time,
   not a run-start time that necessarily precedes completion of a real build.
2. Retain durable training cutoff in an immutable outer tour-artifact envelope
   around the unchanged strict A2 state payload, and expose it on loaded states.
3. Extend backtest with an end cutoff and skip the unused WTA Tennis Abstract
   serve loader for Elo-only calibration. Loader refresh validation currently
   derives its own wallclock despite accepting current_year; a bounded explicit
   coverage cutoff is needed for honest year-end synthetic tests.
4. Existing backtest excludes invalid/missing bookmaker prices before emitting
   calibration observations. That conflicts with the explicit price-blind
   calibration allowlist while changing sample eligibility without approval
   would violate the no-retuning constraint. An explicit price-independent
   calibration mode preserving legacy evaluation defaults was proposed for a
   controller ruling, then implemented exactly as authorized below.

## TDD evidence

Interpreter in all commands:
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
Working directory:
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`.

RED command:
`python -m pytest tests/test_tennis_tour_state.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a3-red`

Expected output observed before implementation:
`ModuleNotFoundError: No module named 'tennis.tour_state'`; 1 collection error
in 0.71s. This is the task brief's required initial missing-module RED.

Partial GREEN command:
`python -m pytest tests/test_tennis_tour_state.py -k training_years -q -p no:cacheprovider --basetemp=.pytest_tmp/a3-years-green`

Observed result: `3 passed, 1 deselected in 0.61s`. Covers 2026/2027 season
boundaries and naive-cutoff rejection. Publication test intentionally remains
pending the integration decision and implementation.

## Initial increment before the rulings

- `tennis/tour_state.py`: aware-cutoff validation and dynamic UTC year range.
- `tests/test_tennis_tour_state.py`: mandatory independent ATP publication RED
  case plus the pure training-year tests.
- This implementation report (local SDD evidence).

## Boundaries

No provider requests, network probes, VPS operations, push, other-agent dispatch,
private plan workspace reads, price-policy edits, Cricket changes or money-path
changes were performed. The full baseline supplied by controller was
1798 passed, 15 skipped, 97 subtests. Final verification below supersedes the
initial partial status.

## Completed A3 behavior

- `training_years` derives 2010 through the logical cutoff's UTC year, inclusive.
  Production builds reject a future cutoff before source I/O; actual completion
  time comes from the real clock, never from logical `as_of`.
- ATP and WTA use separate rating objects and independent source/build paths.
  ATP retains chronological Elo, retired-result exclusion, tour-level-only
  serve data, 365-day decay and the indoor split. WTA copies an explicit
  sport/result allowlist, uses only WTA Elo results and WTA serve constants,
  with serve weight zero and no fabricated boxscores or unused TA dependency.
- Calibration is one explicitly selected tour and uses an inclusive end cutoff
  on stats and results before causal pointer traversal. The fixed 2022/2023/2024
  calibration-year policy is clipped to `as_of.year`; min_samples=1500,
  refit_every=250, four-decimal raw rounding, alphabetical outcome orientation
  and calibration mathematics remain unchanged.
- Authorized population change: separated-model `calibration_only` observations
  no longer depend on bookmaker price availability/validity. They have their
  own sport-only `CalibrationReport`, without fabricated prices. Default legacy
  backtest reporting and price eligibility remain unchanged. Tests cover both
  default parity and price changes all the way through immutable model hashes.
  No improved calibration, edge or empirical acceptance is claimed.
- Strict immutable wrapper: exactly `{schema: 1, training_cutoff: canonical UTC
  ISO, state: exact A2 payload}`, kind `tennis-tour-state`, slots `tennis:ATP`
  and `tennis:WTA`. The shared digest binds both layers. Loaded states expose
  the original training cutoff and digest. Invalid kinds/scopes/envelopes fail
  closed; missing tours raise `TourUnavailable`. Legacy fallback is explicit.
- `training_cutoff <= built_at <= publication_time` is enforced. Coverage and
  individual serve observation dates are bounded by the training cutoff; A2
  decision eligibility is explicitly checked against actual publication time.
  The clock is sampled after build and again after artifact I/O for CAS; clock
  reversal, including on a retry, is rejected. Fresh-retained models also undergo
  explicit decision-time and finite-prediction validation.
- Publication validates codec structure, scoped coverage and finite Elo,
  calibrated and serve probabilities. It retries CAS at most three times after
  the initial attempt, reloads current metadata on every attempt, and refuses
  a coverage regression even when another writer improves the same slot during
  a conflict. Real overlapping SQLite writer tests preserve both tour slots.
  Failed fetches never call `put_artifact`; failed tours retain current hashes,
  build times and coverage. Exception class names, never secret-bearing exception
  strings, are returned. Unreferenced immutable candidates may remain after a
  CAS failure, but are never selected by the active manifest and are not pruned.
- `refresh_tours(..., if_stale_days=None)` attempts both tours. A finite,
  nonnegative threshold independently retains sufficiently fresh valid tours;
  `published` and `retained_fresh` count healthy. Overall status is complete,
  partial or failed, with per-tour original metadata and error type.
- CLI default now publishes independent JSON tours. `--force` attempts both;
  `--if-stale-days` checks each tour independently; refresh remains the default;
  partial/failed runs return 1. **Compatibility choice:** combined pickle writing
  is now only `--legacy-combined`, never an error fallback of the new default.
  Existing legacy regression cases explicitly opt into that pathway; new CLI
  tests verify the old pickle remains byte-for-byte untouched. Legacy combined
  `build_state` remains available and its default final year is now dynamic UTC.

## Additional RED/GREEN evidence

All pytest commands below use the absolute interpreter and working directory
listed above, plus `-q -p no:cacheprovider`. Every basetemp is unique.

1. `-m pytest tests/test_tennis_tour_state.py --basetemp=.pytest_tmp/a3-contract-red`:
   **20 failed, 3 passed in 0.84s**, expected missing tour publication/build APIs
   and missing backtest `end_cutoff` argument.
2. First implementation iteration, `a3-contract-green01`: **3 failed, 20 passed**.
   Three fixture assumptions were corrected after checking unchanged source:
   first-update Elo uses K=250/5**0.4, giving raw .6805; trailing single-letter
   initials keep keys `alpha a` and `beta b`. No rating math was changed.
3. CLI RED: `-m pytest tests/test_tennis_training_refresh.py -k 'cli or recent_pickle or wta_refresh_failure or failed_atomic_model' --basetemp=.pytest_tmp/a3-cli-red`:
   **10 failed, 35 deselected in 1.67s**, expected absent explicit legacy flag and
   absent default independent-tour path. An accidental legacy loader branch was
   stopped by the test's forbidden-network guard; no external request occurred.
4. CLI/build GREEN: `-m pytest tests/test_tennis_tour_state.py tests/test_tennis_training_refresh.py --basetemp=.pytest_tmp/a3-green02`:
   **68 passed in 4.06s**.
5. Expanded edges, same test files with `--basetemp=.pytest_tmp/a3-edge-red`:
   **1 failed, 85 passed in 9.75s**. The deterministic retry-reversal test proved
   that comparing every retry against the initial completion time was too weak.
   The fix advances the clock baseline to the preceding attempted publication.
6. `-m pytest tests/test_tennis_tour_state.py -k 'clock or fresh_skip or atp_calibration' --basetemp=.pytest_tmp/a3-boundary-red`:
   **2 failed, 4 passed, 34 deselected in 1.89s**. Confirmed missing post-storage
   clock sampling and missing finite-prediction validation on fresh skips.
7. `-m pytest tests/test_tennis_tour_state.py -k 'clock or fresh_skip or overflowing or nonfinite_serve' --basetemp=.pytest_tmp/a3-numeric-red`:
   **1 failed, 7 passed, 34 deselected in 1.17s**. Earlier fixes passed; injected
   nonfinite serve prediction exposed the remaining boundary check. The final
   validation now covers serve predictions and all serialized rating keys.
8. A mistyped verification path `tests/test_tennis_cache_paths.py` produced no
   tests; `rg --files tests` identified the actual `test_tennis_training_cache.py`.
   This invocation is not counted as verification.
9. Final focused command:
   `-m pytest tests/test_tennis_tour_state.py tests/test_tennis_training_refresh.py tests/test_tennis_training_cache.py tests/test_tennis_state_codec.py tests/test_tennis_model.py tests/test_tennis_backtest_policy.py --basetemp=.pytest_tmp/a3-final-focused02`:
   **194 passed, 3 skipped in 6.27s**, exit 0, no warnings.

Tests include independent opposite-tour failures, first installation, both
failures, retained old metadata, all-fresh skip, one-fresh/one-failed CLI behavior,
force/cache switches, actual two-writer CAS, same-slot concurrent improvement,
bounded retries, strict wrappers, future/nonfinite/scoped inputs, ATP serve-level
and indoor behavior, exact training/calibration cutoffs, price-independent hashes
and real loader validation under coherently frozen 2027 source/completion clocks.
New-season files present or unavailable are both tested without changing the
source loader's validation-clock API or loosening its future-date protection.

## Separate, controller-authorized deterministic ScanJob test correction

Initial full run, `-m pytest --basetemp=.pytest_tmp/a3-full-final`:
**1 failed, 1850 passed, 15 skipped, 97 subtests passed in 64.02s**.
Only failure: `ScanJobTests.test_progress_extends_inactivity_timeout`, an unchanged
test using 20-ms real sleeps against a 35-ms inactivity deadline. This red full
run is retained as evidence, not counted as a passing run.

Read-only diagnosis confirmed `start_job` starts its monotonic inactivity clock
before thread startup and `get_job` expires it when the actual gap exceeds the
deadline. The original fixture leaves only 15 ms for scheduling jitter.
`-m pytest tests/test_scan_jobs.py --basetemp=.pytest_tmp/a3-scan-diagnostic` gave
**15 passed in 1.99s**. A fresh isolated process with a unittest suite containing
20 instances of that exact test gave **1 failure followed by 19 passes in 1.807s**,
without running A3 tests. A separate 30-run instrumented scheduling harness did
not reproduce the failure; no exact offending scheduler delay was captured.
The defect was intermittent test timing, not evidence of an A3 source change.

The unchanged full confirmation run, `-m pytest --basetemp=.pytest_tmp/a3-full-confirmation`,
gave **1851 passed, 15 skipped, 97 subtests passed in 65.14s**. A3 was then committed
alone as `8f960fc` with exactly its six files.

Controller subsequently authorized changing **only this test in
`tests/test_scan_jobs.py` in a separate commit**. The test now uses an injected
monotonic clock and per-step Event handshakes. It explicitly requires the job to
remain running at 40/60/80 ms, after the original 35-ms total deadline but only
20 ms after the last progress callback. Omitting the inactivity reset would fail
those intermediate assertions. The 5-second Event waits are deadlock watchdogs,
not changed semantic timeout thresholds. Worker release/drain is in `finally`.

`-m pytest tests/test_scan_jobs.py --basetemp=.pytest_tmp/a3-scan-deterministic`:
**15 passed in 1.90s**, exit 0. Only this test file was staged for `d4ece59`.
No ScanJob production code or timeout policy was changed.

**Final full command after both commits:**
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/a3-final-committed`

**1851 passed, 15 skipped, 97 subtests passed in 65.07s; exit 0; no warnings.**

## Final files, self-review and boundaries

A3 commit contains exactly:
- `tennis/tour_state.py`
- `tennis/model_state.py`
- `tennis/backtest.py` (explicitly authorized scope adjustment)
- `scripts/rebuild_state.py`
- `tests/test_tennis_tour_state.py`
- `tests/test_tennis_training_refresh.py`

Second commit contains only `tests/test_scan_jobs.py`.
This SDD report is local ignored workflow evidence, not a staged product file.

Self-review read the production diff and final publication loop, checked the
test diff, and fixed the three validation-boundary findings through observed
RED/GREEN cycles. `git diff --check` and staged checks passed. Separate stage
inventories were verified before both commits. No pending correctness concern
remains within A3's agreed contract; independent review is still the controller's
next gate, not something this implementer self-certifies.

`git diff e08b48c -- scan_jobs.py tennis/data_loader.py tennis/state_codec.py
tennis/elo.py tennis/serve_model.py model_artifacts.py runtime_paths.py` was empty.
No Cricket, price policy, money/15K, credentials, provider configuration,
historical tickets or production data were changed. Rating/calibration math and
A2's strict inner codec envelope remain unchanged.

Inherited `scripts/stage_runtime_databases.py` remains unstaged with no content
diff; SHA256 remains
`1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.
The controller-owned untracked `docs/audits/2026-09-07-kontext-daten.md` was
explicitly excluded from both commits. No blanket stage, reset or cleanup occurred.

No provider GET/HEAD or other network probe, VPS operation, push or deployment
was performed by this implementer. All source exercises used isolated mocked
responses and caches. Nothing here establishes present live WTA GET availability
or unavailability; the controller's source probes are a separate record. A4
forecast consumption, live source execution, release backup/restore, empirical
acceptance and productive activation remain their own gates. Structural loads
alone are not decision-ready assertions; A4 must supply its forecast decision
cutoff and preserve both wrapper and state identity checks.

## A3 independent review fix, round 1 — DONE

Base: `bf4bff83541f2e6954c56404cc51bfd4c940b3b1` (controller audit documentation
followed the original A3 and deterministic ScanJob test commits).
Fix commit: `16d9c4e88435017c5841e613b9cd91670313813a`
(`fix: validate eligible surface rating extrema before publication`).

The independent reviewer identified one Important finding in `_check_predictions`:
surface extrema were selected over all players, but `win_probability` uses the
overall fallback if either player has fewer than eight surface matches. Thus
inexperienced outer extrema could conceal an overflowing experienced inner pair.
The exact supplied example was reproduced: overall a/b/c/d each `[1500,20]`,
surface a=`[-1e300,0]`, b=`[1e300,0]`, c=`[-1e200,10]`, d=`[1e200,10]`.
The a/b prediction is 0.5 while c/d raises `OverflowError`.

Following Receiving Code Review and TDD, the regression was written and run
before the production change. It covers Hard, Clay, Grass and Carpet, at both
the exact eight-match eligibility boundary and the supplied ten-match example.
A `put_artifact` failure guard proves rejection happens before artifact storage;
the final assertions require both tours to fail with `OverflowError` and leave
the manifest empty. The minimal correction selects surface extrema only among
players meeting the existing predictor's eight-match default. The overall
extrema check and both matchup orientations remain unchanged. The pass stays
linear in player count. No Elo formula, threshold, blend, serialization API,
calibration policy, or other production code changed.

All commands below used workdir
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907` and interpreter
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.

RED command:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -m pytest tests/test_tennis_tour_state.py -k inexperienced_surface_extrema -q -p no:cacheprovider --basetemp=.pytest_tmp/a3-review1-red
```

Observed output: `8 failed, 44 deselected in 0.99s`, exit 1. All eight cases
failed at the `put_artifact` guard with
`Failed: invalid surface model reached artifact storage`, reached from
`tennis/tour_state.py:272`. This is the expected behavioral failure, not a
collection/import error. The returned repetitive traceback was output-truncated;
the failure summary and all eight failing test IDs were present.

GREEN command, after the five-line validator change:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -m pytest tests/test_tennis_tour_state.py -k inexperienced_surface_extrema -q -p no:cacheprovider --basetemp=.pytest_tmp/a3-review1-green
```

Observed output: `8 passed, 44 deselected in 0.72s`, exit 0.

Focused affected regression command:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -m pytest tests/test_tennis_tour_state.py tests/test_tennis_training_refresh.py tests/test_tennis_training_cache.py tests/test_tennis_state_codec.py tests/test_tennis_model.py tests/test_tennis_backtest_policy.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a3-review1-focused
```

Observed output: `202 passed, 3 skipped in 6.33s`, exit 0, no test warnings.
Per the controller's explicit scope, no new full-suite run was performed for
this review round; the earlier 1851-pass full-suite evidence remains tied to
the earlier committed state, not this new fix commit.

Verification Before Completion required fresh results and scope inspection
before committing. `git diff --check` and `git diff --cached --check` passed.
Self-review compared the eligibility condition against `SurfaceElo.win_probability`
(default `min_surface_matches=8`) and inspected the complete 34-line addition.
The staged inventory and resulting commit contain exactly:

- `tennis/tour_state.py` — five validator lines.
- `tests/test_tennis_tour_state.py` — 29 lines, eight parameterized regressions.

This appended local SDD evidence remains ignored and unstaged. The inherited
`scripts/stage_runtime_databases.py` remains the only tracked working-tree M;
its SHA256 is unchanged at
`1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.
Git emitted only its existing LF-to-CRLF working-copy notices. Controller audit
documentation and all other files were untouched. No subagents, network/provider
calls, push, VPS or deployment occurred. No additional concern is introduced by
this narrowly scoped fix; independent reviewer confirmation remains the next gate.
