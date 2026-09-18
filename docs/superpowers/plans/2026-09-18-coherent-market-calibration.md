# Coherent market calibration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Repair audit F3 at the probability generator and its identical walk-forward validation, not by altering displayed numbers.
**Architecture:** Existing fitted scalar curves provide targets to one joint-distribution projection per count family and model variant. Every published market is a marginal of that distribution. Version this numerical law and ORIGINAL capture; preserve the unchanged financial contract and old data.
**Tech Stack:** Python, NumPy/SciPy already installed, pytest, existing immutable artifact storage.
**Spec:** `docs/audits/2026-09-18-produktqualitaet.md`, F3 and accepted consistent-distribution requirement. This is a versioned mathematical repair, not a claim of empirically improved prediction quality.

## Global Constraints

- No quote, bookmaker or payout target enters model probabilities or calibration.
- Keep all numeric HAC/FDR, sample, calibration, value, Fréchet, staking and settlement acceptance rules unchanged.
- Keep CHALLENGE_MODEL_CONTRACT_SIGNATURE and existing ticket/ledger versions unchanged: they are used to read historical authenticated tickets. Never rewrite historical tickets, predictions, backups or ORIGINALs.
- Bump probability-law and shadow cache versions; old/unversioned qualification cannot qualify newly computed predictions.
- Use the identical probability law in current prediction and walk-forward evaluation. Fit calibration only from prior days' raw probabilities/outcomes, never today's label.
- ORIGINAL v1 bytes remain readable and unchanged. New v2 is explicit and closed-schema; no v1 fields silently redefined.
- No production/VPS writes, source downloads, network, pruning or empirical activation in this task. Cricket unchanged.
- TDD first; apply_patch edits; focused testing during iteration. Root coordinates broad suite and push.

### Task 1: Joint law, matched validation and backward-compatible provenance

**Files:** Create `football_joint_calibration.py`, `tests/test_football_joint_calibration.py`. Modify `challenge_engine.py`, `challenge_15k.py` only for validation aggregation/provenance propagation, `shadow_clv_automation.py` version boundary, `football_original.py`, `context_models/football_original_storage.py`, and exact row/validation serializers discovered in `wettfinder_automation.py` / `ev_signal_sources.py`. Extend relevant calibration, original-capture/storage and release tests. No financial store schema change.

**Interfaces:**
- `calibrate_joint_distribution(raw_matrix, specs, calibration)` returns effective matrix plus explicit law/solver diagnostics. Matrix keys remain native `(home,away)` cells; no circular import of challenge_engine at module import. Supply settlement evaluation by local lazy import or a typed callable argument if required.
- `ValidationMetrics.prediction_version: str | None = None` and `ChallengeCandidate.prediction_version: str | None = None`; None stays unversioned. Current constructors set the new prediction-law token explicitly. New release requires a matching current candidate/validation version; passive history reads do not.
- ORIGINAL v2 adds exact `distribution_capture` with law version, raw/effective family/variant cells, full projection recipe and diagnostics. Owning class remains FootballOriginal. Storage envelope/chunk versions remain unchanged if the fixed chunk paths remain unchanged.

- [ ] RED: use 101 probabilities `.1+.8*i/100` and labels `int(i>=50)` with exactly complementary labels/maps. Through real `fixture_market_probabilities`, demonstrate `P(AWAY)+P(1X)` and `P(HOME)+P(X2)` must each equal 1 within `1e-10`, but fail under scalar calibration. Add partition, BTTS, total/team-total, subset, union and monotone-line tests for goal, corner and yellow families.

```python
assert p['RESULT_AWAY'][0] + p['DC_1X'][0] == pytest.approx(1.0, abs=1e-10)
assert p['RESULT_HOME'][0] + p['RESULT_DRAW'][0] + p['RESULT_AWAY'][0] == pytest.approx(1.0, abs=1e-10)
assert p['HOME_OVER_1_5'][0] <= p['HOME_OVER_0_5'][0]
```

- [ ] Implement the declared projection law over positive-support raw cells, grouped by identical full settlement vectors. Let `r` be normalized prior atom masses, `A` target-market incidence, `t` finite scalar-calibrated targets. Minimize `0.5*mean((A@q-t)**2) + 0.5*sum((q-r)**2)` subject to `q>=0`, `sum(q)=1`. The prior anchor is exactly 1.0; it is an explicit numerical design choice, not a proven optimum. Use deterministic ordering, analytic gradient and existing SciPy SLSQP with `ftol=1e-12`, `maxiter=200`. Split each fitted atom back into cells in raw proportions. Validate finite masses/nonnegativity/unit mass after solve. Empty or identity calibration is exact raw identity.
- [ ] Invalid targets fail explicitly before publication. Solver failure must return a documented raw-distribution fallback with failure diagnostics (never partially calibrated independent marginals); new-release qualification must not silently treat that failed projection as a successful calibrated prediction. Cover zero support, sparse/contradictory/extreme targets, deterministic reordered input, identity and solver failure.
- [ ] Integrate projection for active/season/form goal matrices and available corner/yellow matrices. Preserve separate raw probabilities for fitting and capture. Derive every final market via `_market_probabilities(effective_matrix,specs)`. Derive public expected-count fields from the effective matrix, while preserving named raw inputs for reproducibility; no explanation may silently describe pre-calibration means as final means.
- [ ] In `_walk_forward_market_records`, construct prior-day maps once per day, call the identical joint path, store raw probabilities for future scalar-map fit and effective probabilities for validation. Do not repeat the old scalar curve evaluation afterward. Test production/walk-forward equivalence, same-day label isolation, future-label perturbations and untouched thresholds.
- [ ] Set `CHALLENGE_PREDICTION_VERSION` and `SHADOW_MODEL_VERSION` to explicit new coherent-law tokens. Propagate candidate/validation versions through conservative cross-league aggregation and persisted records. Require version agreement at new-release admission; legacy forecasts may stay descriptive. Test stale caches/unversioned validation cannot qualify new predictions. Keep financial signature unchanged and prove an existing signed ticket remains readable/settleable without changing its definition hash.
- [ ] Version ORIGINAL capture to schema2/kind `football-original-market-calculation-v2`, carrying exact effective distributions and recipe. Version-dispatch strict payload fields in `_packet` and `_expand`; v1 stays byte-identical/readable and never receives invented distributions. Keep fixed transport paths and byte-budget guards. Test new roundtrip plus unchanged real v1 fixture bytes, unknown versions, wrong kind/schema combinations, missing/extra v2 fields, capture-on/off exact equality within the new law.
- [ ] Preserve frozen legacy mathematical tests as historical evidence, not claims that new mathematics equals old mathematics. Replace only assertions explicitly superseded by this authorized law transition with new law/capture parity tests and document the transition. Do not merely repin an AST hash or weaken outcome assertions.
- [ ] Run focused RED/GREEN, all calibration/engine/original/storage/version/forecast release tests affected, and a bounded synthetic timing comparison for repeated projections. Report operation counts/timing; do not claim real empirical qualification. Self-review, commit owned files and write precise report with remaining data-dependent qualification work. Root runs broad suite once and independent review before push.
