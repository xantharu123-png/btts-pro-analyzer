## Task 17: D2 — Gepaarte Abnahme, Multiplizität und eng gebundene Aktivierung

**Files:** Create `model_loss_statistics.py`, `context_models/validation.py`, `context_models/activation.py`, `scripts/evaluate_context_models.py`, `tests/test_context_validation.py`, `tests/test_context_activation.py`, `tests/test_model_loss_statistics.py`; modify `challenge_engine.py` only for mathematically identical shared-statistic delegation.

**Interfaces:**

- `paired_advantage_statistics(advantages: list[float]) -> tuple[float | None, float | None, float | None, float | None]`: mean, HAC standard error, lower bound, one-sided p.
- `benjamini_hochberg_q_values(p_values: dict[str, float]) -> dict[str, float]`.
- `aggregate_event_losses(rows: tuple[dict, ...], *, target_markets: tuple[str, ...]) -> tuple[dict, ...]`: each row has `event_key`, `market_key`, `decision_at`, `block`, `p_base`, `p_context`, `outcome`; result has event, block, mean `base_brier`, `context_brier`, `advantage`.
- `evaluate_experiment(path: Path, experiment_hash: str, *, results: dict[str, tuple[dict, ...]], distribution_losses: dict[str, tuple[dict, ...]], evaluated_at: datetime) -> dict`.
- `approved_effect(path: Path, *, effect_hash: str, event: dict, features: dict, base: dict) -> dict | None`: D2-verified approval bound to matching scope and exact model; no approval returns `None`, not a forecast ban.

- [ ] **RED – average losses within events, not probabilities, and count each event once.**

```python
import pytest
from context_models.validation import aggregate_event_losses

def test_event_loss_is_not_loss_of_mean_probability():
    rows = tuple({"event_key": "football:1", "market_key": key,
                  "decision_at": "2026-09-07T12:00:00+00:00", "block": "one",
                  "p_base": .5, "p_context": probability, "outcome": 0}
                 for key, probability in (("m1", .1), ("m2", .9)))
    result = aggregate_event_losses(rows, target_markets=("m1", "m2"))
    assert len(result) == 1
    assert result[0]["base_brier"] == .25
    assert result[0]["context_brier"] == pytest.approx(.41)
    assert result[0]["advantage"] == pytest.approx(-.16)
```

- [ ] Run D2 files with `d2-red`; expected missing APIs.
- [ ] **Extract unchanged loss statistics.** Move the advantage→Newey-West calculation currently inside `challenge_engine._paired_loss_statistics` to `model_loss_statistics.py`; keep the old wrapper constructing its exact current advantages and return tuple. Move BH calculation unchanged behind its old wrapper. Preserve `PAIRED_LOSS_CONFIDENCE_Z=1.6448536269514722`, bandwidth rule, Bartlett weights, zero-variance handling and invalid-input behavior. Regression fixtures compare old reference values bit-for-bit or at the existing test tolerance; do not change 15K calibration/release policy in this extraction.
- [ ] **Aggregate fixed targets before inference.**

```python
base_loss = sum((row["p_base"] - row["outcome"]) ** 2 for row in event_rows) / len(event_rows)
context_loss = sum((row["p_context"] - row["outcome"]) ** 2 for row in event_rows) / len(event_rows)
advantage = base_loss - context_loss
```

Validate outcome exactly integer 0/1, probabilities finite `[0,1]`, exact target-market set per event, no duplicate market rows, same decision/block. Missing required target excludes that event from the paired primary set with a reported coverage reason; never let each variant choose a different favorable event set. Intersect declared eligible sets before comparing variants and also report coverage lost by each variant.
- [ ] **Implement frozen policy checks.** Per family: at least 200 distinct eligible events, all three or more predeclared consecutive blocks represented, relative improvement `(mean_base - mean_context)/mean_base >= .02` with positive finite denominator, positive paired lower bound and BH q-value `<= .05`. Feed HAC chronologically ordered **event advantages**, not market rows. Include every registered family/ablation in BH with p=1 when unevaluable; no winners-only table.
- [ ] **Score an actual declared distribution outcome.** Football: joint regulation goal score; hockey: regulation goal score with separate inclusive winner checks; tennis serve: exact set-score distribution, winner-only tennis/e-sport: Bernoulli winner; basketball: score-margin density. Use stable log PMF/PDF, not a product of overlapping market marginals. Declare outcome contract in D1. Handle truncated simulator/count tails explicitly and consistently between base and context, not a post-hoc `epsilon` that hides impossible outcomes. Require paired mean context logloss ≤ base and report differences by block.
- [ ] **Retain market calibration rules.** Use `_calibration_diagnostics` and `adaptive_bin_threshold` with existing constants: minimum 3 supported bins, minimum 20 per bin, ECE ≤ .08, worst supported-bin deviation ≤ adaptive threshold (base floor .12, z=2.5). Report every predeclared target market and its real scope. No fitting a fresh isotonic/Platt curve on final test labels. A sparse calibration set cannot certify an unseen family.
- [ ] **Persist decision and scoped approval.** Approval payload binds experiment hash, effect artifact hash, dataset/code/policy versions, population (sport, competition, format, tour/surface where applicable), coverage case, feature version, tested market family and all paired statistics. Store as immutable A1 artifact. Publish its slot only when all required checks pass. `approved_effect` loads and validates this artifact, checks exact identity/scope and returns it; there is no provider-controlled override or `force=True`. A new effect hash has no inherited old approval.
- [ ] **Report ablations/cohorts including bad results.** Injury-present, high-load (threshold fixed on training distribution), missing-context, confirmed vs uncertain lineup, exact vs bounded recovery and every block. For each: counts, source availability, base/context Brier, distribution logloss, calibration, effect sizes and limitations. Report interactions as joint/non-additive contrasts, not causal attribution. ROI may be a separate read-only appendix but is never a training/activation argument.
- [ ] CLI: `scripts/evaluate_context_models.py --model-db PATH --experiment HASH --results PATH --distribution-losses PATH --output-dir PATH`. Reject unknown/missing registered families, mutable/reused test definitions and corrupted model hashes. Write report before any optional manifest publication; publication is a separate reviewed execution step with explicit exact approval hash.
- [ ] Tests: 199 events with 900 markets still fails; 200 events in one block fails; 1.99% fails; worse logloss fails; missing calibration fails; omitted loser-family fails; duplicate/native-alias events fail; future observation fails; unseen competition/format/coverage no approval; exact legitimate zero-effect status remains distinct from missing. Run D2 plus existing challenge validation/integrity tests with `d2-green`.
- [ ] Run the real frozen evaluation and document exact pass/fail/insufficient-data states in `docs/audits/2026-09-07-kontext-abnahme.md`. Commit exact D2 files/report with message `feat: enforce event-level context validation and scoped model activation`.

### Binding inherited context (verbatim)

- Keine Quote, Buchmacheridentität, Mindestquote oder Preisfreigabe als Modell- oder Rankingmerkmal.
- Kein pauschales Wettartenverbot. Ein nicht aktivierbarer Kontextteil entfernt keine berechenbare Basisprognose.
- Cricket-Code, Konfiguration, Zugangsdaten und bestehendes Verhalten bleiben unverändert.
- Keine neue Echtgeldfunktion; 15K-Konto-, Einsatz-, Ticket- und Abrechnungsregeln bleiben unverändert.
- Alte Prognosen, authentisierte Tickets und Abrechnungen werden nicht umgeschrieben.
- Keine kostenpflichtige Quelle, neuer Vertrag oder Tarifwechsel ohne gesonderte Zustimmung.
- Nur der VPS schreibt produktive Daten; lokale Tests/Forschung verwenden isolierte Dateien.
- Mindestens 200 eindeutige Testevents über mindestens drei aufeinanderfolgende Zeitblöcke.
- Mindestens 2 % relative Verbesserung des innerhalb eines Events gemittelten primären Brier-Verlusts; Newey-West/HAC und Benjamini-Hochberg, FDR 5 %, über alle untersuchten Familien.
- Mittlerer Verteilungs-Logloss darf nicht steigen; bestehende marktspezifische Kalibrierungsprüfungen bleiben erforderlich.
- Frische Daten, funktionierende Software, empirische Freigabe, Push und VPS-Aktivierung sind unterschiedliche Nachweise.

#### Kontext-Abnahme, gemeinsame Oberfläche und Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jede aktivierte Kontextwirkung durch unverfälschten Modellvergleich belegen und dieselbe verständliche Prognose in beiden Tabs sicher betreiben.

**Architecture:** Ein eingefrorener Versuchsplan bindet Daten, Splits, Modelle und Zielmärkte. Gepaarte Eventverluste und Mehrfachtestkorrektur erzeugen hashgebundene Abnahmeentscheidungen. Worker veröffentlichen gemeinsame Snapshots, während Preise und Geldhistorien getrennt bleiben.

**Tech Stack:** Python, NumPy/SciPy, SQLite, pytest, bestehendes Streamlit-UI, systemd und revisionsgebundener VPS-Updater.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), insbesondere Abschnitte 9–12.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Mindestens 200 eindeutige Testevents über mindestens drei aufeinanderfolgende Zeitblöcke.
- Mindestens 2 % relative Verbesserung des pro Event gemittelten primären Brier-Verlusts; Newey-West/HAC und Benjamini-Hochberg, FDR 5 %, über alle untersuchten Familien.
- Mittlerer Verteilungs-Logloss darf nicht steigen; bestehende marktspezifische Kalibrierungsprüfungen bleiben erforderlich.
- Finale Testfenster bleiben unangetastet durch Tuning; keine Freigabeübertragung auf ungetestete Populationen/Abdeckung.
- Basisprognosen bleiben sichtbar, wenn ein neues Kontextmodell nicht freigegeben ist.
- Alte Prognosen/Tickets/Abrechnungen bleiben unverändert; keine Quote als Trainings- oder Rankingmerkmal.
- Commit/Push, VPS-Code, Modellaktivierung, realer Worker-Lauf und empirische Qualität werden separat nachgewiesen.

## Dateigrenzen

Neu: `context_models/replay.py`, `context_models/training.py`, `context_models/validation.py`, `context_models/activation.py`, `model_loss_statistics.py`, `context_copy.py`, `scripts/train_context_models.py`, `scripts/evaluate_context_models.py`, `scripts/verify_context_runtime.py`. Bestehende Sportmodelle erhalten nur die in B/C beschriebenen reinen Modell-/Provenanzschnittstellen. UI-Änderungen betreffen Karten-/Signaladapter, keinen erneuten UX-Neubau.

Ausführliche Rohberichte liegen unter `runtime_paths.RUNTIME_REPORT_DIR`, konfiguriert durch `BETBOY_REPORT_DIR`; keinen zweiten Reports-Root erfinden. Die kompakten, überprüften Ergebnisse kommen nach `docs/audits/2026-09-07-kontext-abnahme.md`. Dieser Plan verwendet für lokale CLI-Ausgaben den ausdrücklich angegebenen Ordner `output/context-evaluation/`, nicht Produktionsdaten.

### Execution context

Read both `context-contract-decisions.md` and `validation-contract-decisions.md` in this SDD directory completely. The latter closes the complete hypothesis registry, paired/distribution event set and ordering, exact approval transport/provenance, and immutable opened-test history. Original thresholds/math remain unchanged; failed hypotheses never disappear from BH.

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-d-validierung-release.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
