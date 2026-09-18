# Task 1 implementation report — coherent football calibration

Base: `94671485b9659aa3f047491cb7c34f4ddfb03229`.
Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.
Scope: local mathematical/provenance repair only. No source fetch, empirical activation, VPS, financial schema change, historical rewrite, or push.

## Implementation

- `football_joint_calibration.py`: deterministic sorted positive-support settlement atoms, declared unit prior anchor, exact specified quadratic objective, analytic gradient, SLSQP ftol=1e-12/maxiter=200. Raw identity, finite typed target checks, validated atom/cell laws and diagnosed coherent raw fallback.
- Production derives every active/season/form goal/corner/yellow marginal and expected count from its effective law; explicit raw means/marginals remain available. Capture-on/off has identical calculations and outputs.
- Walk-forward uses prior-day maps once per day, the identical central projection, raw probabilities for future fitting and effective probabilities for validation; baseline/history also stay prior-day-only. Active-only internal mode uses one-element tuples plus explicit variant metadata; it cannot emit an ORIGINAL. The full production default still calculates all nine distributions.
- Candidate, validation, shadow cache and persisted release records carry the new prediction token. Current-release readers/writers reject absent/mismatched tokens; aggregation retains a version only when every source agrees. Failed projection blocks release without independently calibrated marginal fallback.
- ORIGINAL schema2/kind v2 has strict version-dispatched transport, fixed unchanged chunk paths/envelopes/budgets, exact raw/effective cells, full numerical recipe and solver diagnostics. Original v1 byte roundtrip remains unchanged without invented distributions.
- Financial contract signature, ticket definitions/settlement code unchanged. A ticket issued using immutable old-engine types/admission functions is reopened and settled under current code while its stored legs JSON and definition hash remain byte-identical; ledger integrity passes. Absent optional version fields are omitted from historical candidate serialization.

## TDD and verification

Runtime: `C:/Projekt/BetBoy/betboy-app/.venv/Scripts/python.exe`.
All pytest invocations used `-B -m pytest ... -q -p no:cacheprovider --tb=short` (early RED calls omitted only `--tb=short`).

- Initial real fitted-map RED: 101 p=.1+.8*i/100, y=int(i>=50), complementary maps produced P(AWAY)+P(1X)=1.0046122909282649. Projection tests initially failed because the module was absent. Integration schema, prior-day map use, current admission, persisted writer/reader admission, invalid bool raw mass, nested malformed v2 and active-only-mode REDs were observed before their fixes.
- Core current-law suite covers objective optimum by hand (two atoms: x=1.9/3), within-atom proportions, sparse/extreme/contradictory/identity/reordered inputs, zero support, target failures, all-family market partitions/complements/subsets/unions/monotone lines, exact moments, capture parity, prior-day/same-day/future-label isolation, raw fallback, version aggregation/cache isolation, v1/v2 transport and historical financial settlement.
- Unchanged historical assertions now execute verified local pretransition sources, not the new law. Existing scalar golden hashes were not repinned. Historical parity group: 26 passed.
- First affected run before active-only optimization: 705 passed, 97 subtests passed, 57.21s.
- A later affected run while the bounded benchmark was running had 707 passed, 97 subtests, and one timing-sensitive existing financial concurrency failure (`test_concurrent_ticket_attempts_commit_one_atomic_price_and_ticket`, financial precheck). No financial code/gate was changed; isolated rerun plus current-law suite: 34 passed, 7.25s. This observation is retained, not hidden.
- Final affected suite after all changes, without concurrent benchmark load: **709 passed, 97 subtests passed in 46.24s**. `git diff --check` clean. The unchanged financial concurrency case also passed this complete run.

The observed concurrency stack was `tests/test_challenge_integrity.py:1807` (executor.map) -> `:1795` (place) -> `challenge_store.py:3744` (place_ticket precheck) -> `:1709` (_require_financial_ledger), raising `RuntimeError: Challenge financial ledger integrity check failed`. Isolated retry command was `python -B -m pytest tests/test_challenge_integrity.py::WholeDatabaseCheckpointTests::test_concurrent_ticket_attempts_commit_one_atomic_price_and_ticket tests/test_football_joint_calibration.py -q -p no:cacheprovider --tb=short`, using the runtime above:34 passed in7.25s. A green retry does NOT disprove a race. Root will investigate independently; this task changed no financial implementation or gate.

Final affected command:

```powershell
& C:/Projekt/BetBoy/betboy-app/.venv/Scripts/python.exe -B -m pytest tests/test_football_joint_calibration.py tests/test_calibration.py tests/test_football_original_parity.py tests/test_football_original_capture.py tests/test_football_original_storage.py tests/test_football_original_samples.py tests/test_challenge_model_cache.py tests/test_challenge_15k.py tests/test_challenge_integrity.py tests/test_challenge_market_eligibility.py tests/test_wettfinder_automation.py tests/test_ev_signal_sources.py tests/test_football_base_provenance.py tests/test_football_recommendations.py tests/test_forecast_selection.py tests/test_shadow_markets.py -q -p no:cacheprovider --tb=short
```

Existing optional-analysis presentation equality test was updated per root's F1/F4 contract: exclude only explanation/highlight fields from card equality, explicitly assert valid analysis may highlight and absent/future analysis cannot. Probability, haircut, prices, evidence/release flags, complete catalogue identities, artifact bytes and shared-clock/no-I/O assertions remain.

## Performance — bounded synthetic, not empirical quality evidence

Early three-repetition isolated SLSQP probe: goals676 cells/38 atoms ~4.26ms, corners676/55 ~1.80ms, yellow169/22 ~0.62ms; all successful,6–10 iterations.

End-to-end probes executed `_walk_forward_market_records(league_history(cycles=N))` with the current and SHA-verified frozen engine, instrumenting actual `football_joint_calibration.minimize` invocation/iteration counts. No thresholds were changed.

| Synthetic fixtures | Goal/total market records | Old seconds | New seconds | Actual solves/iterations | Result |
| --- | --- | --- | --- | --- | --- |
| 192, initial full-variant validation | 152 / 13,680 | 1.1023 | 4.3064 | 468 / 4,134 | all success;3.91x material overhead |
| 192, final active-only validation | 152 / 13,680 | 1.1567 | 1.9785 | 156 / 1,371 | all success;1.71x |
| 1200, maximum-history-sized synthetic | 1160 / 104,400 | 30.5058 | 46.6251 | 3180 / 27,629 | all success;1.528x |

Active-only production-equivalence test verifies exact active/raw equality and precisely three rather than nine solver calls for a nonidentity all-family fixture. Bounded grouping cache stores settlement topology only (maxsize32), not predictions/live matrices.

Operational caveat raised to root:51 independent maximum-sized synthetic cold leagues would linearly suggest~39.6min numerical work versus~25.9min legacy, before providers/other sports. This is NOT measured production capacity. The existing45min service limit and per-league reusable cache progress were not changed. Actual cold-cache orchestration/VPS qualification remains open.

## Immutable legacy fixture provenance

All paths below are under `tests/fixtures/football_pre_joint/`. Verified each with `git hash-object` against `git rev-parse REV:path`; the loader additionally checks fixed SHA-256 and `.gitattributes` preserves exact bytes.

| Fixture | Source commit | Original path | Git blob |
| --- | --- | --- | --- |
| challenge_engine.py.txt | 94671485b9659aa3f047491cb7c34f4ddfb03229 | challenge_engine.py | 2ec5d40e1429470477db7330832d1cb205fdc11e |
| football_original.py.txt | 94671485b9659aa3f047491cb7c34f4ddfb03229 | football_original.py | f4f20e2de10c423f44a0468937c9e548af629e8f |
| challenge_15k.py.txt | 94671485b9659aa3f047491cb7c34f4ddfb03229 | challenge_15k.py | 5c48f4c3f58c58124339beaa42031fc5ab2fe4b5 |
| parent_engine.py.txt | bb297bbd34ca80eb83129e87cf1559cc44ae20df | challenge_engine.py | 00a4b32eec249c4664b013c1c02ca78233114f45 |
| parent_challenge.py.txt | bb297bbd34ca80eb83129e87cf1559cc44ae20df | challenge_15k.py | 7d2ed4eeae0de7c949877111c90a9d3fe8b2928b |

The challenge_15k snapshot is also byte-identical to approved historical daily-refresh commit a1d15b6972f01ba617a62381bacf7bf08a168b1f. These old source copies are test-only; no production import/path uses them.

## Remaining gates

Root owns independent review, broad 10k+ suite, any confirmed regression follow-up, and verified-upstream push. Fresh real league walk-forward qualification is mandatory under the new law/version; old qualification cannot release new candidates. Unit prior anchor 1.0 is a specified numerical design choice, not an empirically proven optimum. No prediction-quality, source-provenance, activation, deployment or money-state claim is made.
