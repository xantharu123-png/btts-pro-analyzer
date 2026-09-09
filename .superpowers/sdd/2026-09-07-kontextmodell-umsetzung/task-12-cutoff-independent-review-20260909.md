# C1 exact-cutoff recovery — independent bounded review, 2026-09-09

Disposition: **PASS for this narrow mechanics correction.** No actionable
finding in the two frozen source/test files. This report is separate from C2;
it grants no provider, training, empirical-effect, worker, UI or live approval.

## Scope and frozen state

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`.
Reviewed only controller's `context_models/football_load.py` correction and
`tests/test_context_recovery_cutoff.py`, plus their unchanged dependencies and
independent QA probes. Read the complete two-hunk source diff, complete new
12-case permanent test, entire owning football-load source, and corresponding
Tennis recovery/window code. Production delta is 9 additions / 2 removals,
including explanatory comments and a separate strict historical count.

Root HEAD advanced from `30e7c84d47b6b9273ddacbb17d1db4cc639e5a63` to
`b9087124161f3f22d61a163edc082c43dc8429e6` during independent review of unrelated
work. Both pinned review files kept their exact initial SHA256 values. Other
pre-existing/parallel WIP was not touched or reviewed as part of this task.
Reviewer edits are limited to its `.pytest_tmp/c1-cutoff-independent-20260909`
test/report files; no Source/Git/provider/VPS or financial operation.

## Independent verification

Interpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`,
`-B -m pytest -q -p no:cacheprovider`, fresh basetemp each execution.

- `c1-final-controller-regression-20260909-01`: **255 passed, 8.61 s**.
  Actual independent execution of the 12 new cross-sport permanent tests and
  existing football-weather/load and Tennis-feature suites, not a copied count.
- `c1-final-independent-20260909-01`: **27 passed, 1.24 s**, first independent
  probe version. Added one genuine-parent reproduction check afterwards.
- `c1-final-independent-combined-20260909-01`: **283 passed, 9.65 s** in ONE
  final combined run: the same 255 plus all 28 final independent checks.
- Scoped whitespace check passed. Both frozen source/test hashes and the
  unchanged Tennis source were freshly verified after execution.

Controller's reported pre-fix permanent reproduction (2 failed / 10 passed)
was not rerun as that exact historical pytest invocation by this reviewer.
Instead, an independent test loads the actual pre-fix Git source at
`30e7c84d47b6b9273ddacbb17d1db4cc639e5a63:context_models/football_load.py`
(Git blob `736e73a16df6be5056bbedc7ca183a8dcf33d25e`) without writing a source
fixture. On identical actual SQLite receipts, that original code reports
34 hours exact recovery while the fixed code correctly reports 4 hours for
both teams. Historical count, three-day match count and minutes are equal.
This is a synthetic clock example proving software behavior, not a live game.

## Additional independent boundary and parity evidence

- Six separate-receipt cases: the old completed game is genuinely received
  before cutoff; only the new completion varies by -1/equal/+1 microsecond,
  with both native home/away orientations. A future new receipt cannot erase
  the still-known older game. Retrospective receipt hashes never enter features.
- Nine 1/3/7-day lower-bound cases (-1/equal/+1 microsecond): a completion
  exactly at decision contributes to recovery, never to the half-open
  performed-minute/count window. Lower bounds remain inclusive. Strict total
  count provenance excludes the new endpoint; recovery provenance includes it.
- Three unknown-duration/terminal-bound cases at -1/equal/+1 microsecond:
  unknown minutes remain null, observed complete-window status is not
  manufactured, and an unknown actual end never adds performed minutes.
- Seven non-endpoint historical windows retain full feature JSON bytes equal
  to the genuine original Git implementation. Empty/unknown-end input has an
  additional exact-byte parity check. Inputs are not mutated.
- The genuine-parent endpoint reproduction above closes the original error
  without allowing changed historical counts. All histories remain explicitly
  observed-only; no test upgrades the source to complete team coverage.
- Tennis source is exactly byte-equal to its committed parent object, in
  addition to its six permanent endpoint tests and the full existing feature
  tests. No Tennis timing or load rule was changed to make C1 pass.

## Remaining boundaries

This changes eligible end-time mechanics only. It neither supplies missing
actual end/minute measurements nor constructs a fatigue coefficient or weather
probability adjustment. Unknown source facts, provider readiness, sufficient
causal training data, effect evaluation/approval, and actual D3 integration are
separate tasks. No source request, activation, Cricket or monetary change.

## SHA256 manifest

```text
761b000057c41f2cb692304b7dfa839fcf067126e22a94d687c037027bbe4f1b context_models/football_load.py
17eefff17758cb4677548dd80bd5f20ab20f7519d7175eb88fba1cf49e21ca4e tests/test_context_recovery_cutoff.py
313ffafacc367e7370312f478327d6453860ac0bf17bbcaf8102acdda49e4bab context_models/tennis.py
ab8a53fc6b06ba83d66f96584c5d2c3354de130fe800bbf7395a3dc56677e513 tests/test_football_weather_features.py
9f9874ee40a67754154f4b1ba4ff7db067d27c40cd254302a0f180dbb51dcfce tests/test_tennis_context_features.py
dd204c3863dcd6712531213c05aeeb3a9551f6b0f8ec9a160e1375182958e033 context_observations.py
8ed2194852f01cd1ac548de4b2ef82e2b2f652561229fd251ec2bb649e885a3b .pytest_tmp/c1-cutoff-independent-20260909/test_c1_cutoff_independent.py
```
