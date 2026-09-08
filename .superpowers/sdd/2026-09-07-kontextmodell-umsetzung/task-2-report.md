# Task 2 Report: A2 explicit tour-state codec

Status: DONE

Commit: `e08b48c feat: encode isolated tennis states as typed runtime artifacts`

## Implemented

- Added `SurfaceElo.to_payload()` / `from_payload()` with exact `overall` and
  four-surface maps, finite ratings, nonnegative integer match counts, fresh
  `_RatingTable` instances, and copied nested rating entries.
- Added `ServeReturnModel.to_payload()` / `from_payload()` with the fixed
  constructor fields and sorted accumulator rows. Every `_Accum` slot is
  encoded explicitly; invalid keys, buckets, duplicates, dates, booleans,
  non-finite/negative values, and successes above games are rejected.
- Added `encode_state()` / `decode_state()` with exact schema-1 keys and strict
  ATP/WTA scope checking. `artifact_hash` is intentionally absent from the
  payload and is initialized to `None` after decode.
- Applied the controller-approved cutoff ruling:
  `decode_state(payload, *, decision_cutoff=None)` performs structural decode
  without wall-clock eligibility claims. A supplied finite, non-boolean cutoff
  additionally enforces inclusive `built_at <= decision_cutoff`. The docstring
  states that omission does not establish decision readiness.
- Added defaulted `ModelState.tour_scope`, `stats_through_kind`, and
  `artifact_hash`; legacy pickle loading assigns these defaults in memory via
  `getattr` without rewriting an artifact.
- Kept rating, serve/return, calibration, reversed-player, and WTA math
  unchanged. WTA `hold_avg=0.706` and its complementary break constant survive
  roundtrip exactly.

## Field parity and isolation checks

- Compared every stored ModelState scalar, the complete Elo payload, and the
  complete ServeReturnModel payload after roundtrip.
- Exercised populated overall, Clay, and Hard-indoor accumulators with decay,
  microsecond dates, indoor splitting, and non-rounded floating-point values.
- Compared Elo probability, ATP/WTA calibration, reversed-player calibration,
  and serve matchup probabilities before and after roundtrip.
- Mutated emitted payload entries and model tables independently to prove no
  shallow list sharing. Unknown Elo lookups were checked not to create state.
- Rejected missing/unexpected envelope and nested keys, crossed/legacy tours,
  unsupported schema/tours, invalid counts/dates/buckets, duplicate rows,
  non-finite values, booleans masquerading as numbers, and non-JSON rating
  tuples.

## TDD evidence

### Initial RED

Command:

`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -m pytest tests/test_tennis_state_codec.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a2-red`

Result: collection failed with
`ModuleNotFoundError: No module named 'tennis.state_codec'` (1 error in 0.81s).
This was expected because the codec had not yet been implemented.

### First GREEN

Command used focused child `.pytest_tmp/a2-green-focused-1`.

Result: `47 passed in 0.74s`.

### Self-review RED/GREEN

Strict JSON review added two tests before their fixes. Command used child
`.pytest_tmp/a2-red-strict-json`.

Result before fix: `2 failed, 47 passed in 0.75s`; rating tuples and float
`schema=1.0` were incorrectly accepted. After requiring a real JSON list and
an integer schema, child `.pytest_tmp/a2-green-focused-2` produced
`49 passed in 0.68s`.

### Required A2 regression GREEN

Command:

`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -m pytest tests/test_tennis_state_codec.py tests/test_tennis_model.py tests/test_tennis_predict.py tests/test_runtime_paths.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a2-green`

Result: `107 passed in 0.81s`; no skips or warnings.

### Full-suite GREEN

Command:

`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/a2-full`

Result: `1798 passed, 15 skipped, 97 subtests passed in 64.76s`; no warnings or
failures. The skips are existing platform/optional-environment skips.

## Files changed in commit

- `tennis/state_codec.py`
- `tests/test_tennis_state_codec.py`
- `tennis/elo.py`
- `tennis/serve_model.py`
- `tennis/model_state.py`

The known LF-normalized `scripts/stage_runtime_databases.py` worktree status was
preserved and never staged. No A1 file, Cricket code, pricing/ranking behavior,
money/15K rule, provider, server, deployment, or remote state was changed.

## Self-review and concerns

`git diff --cached --check` passed before commit. The self-review found and
fixed the two strict-JSON gaps documented above. No remaining A2 correctness
concern is known. Decision-selection callers in A3/A4 still must provide their
actual cutoff; this was explicitly left outside A2 scope as directed.
