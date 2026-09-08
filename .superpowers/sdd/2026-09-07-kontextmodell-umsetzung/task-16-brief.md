## Task 16: D1 — Zeitkorrekte Datensätze, echte Trainingsläufe und eingefrorener Versuch

**Files:** Create `context_models/replay.py`, `context_models/training.py`, `scripts/train_context_models.py`, `tests/test_context_training.py`, `tests/test_context_replay.py`.

**Interfaces:**

- `replay_base_distribution(sport: str, event: dict, history: tuple[dict, ...], *, decision_at: datetime, reconstructed_at: datetime) -> dict`: B BaseDistribution, inklusive tatsächlicher Rekonstruktionszeit und logischem Trainingsstichtag.
- `split_rows(rows: tuple[dict, ...], *, train_end: datetime, tune_end: datetime, test_blocks: tuple[tuple[datetime, datetime], ...]) -> dict[str, tuple[dict, ...]]`.
- `train_family(rows: tuple[dict, ...], config: dict) -> dict`: B EffectArtifact; config binds sport, family, population, coverage, feature names/version, named head links, reference logic, preprocessing artifact hashes and candidate regularization values. Output uses `heads` and `preprocessing_artifacts` exactly as defined in B.
- `freeze_experiment(path: Path, plan: dict, *, created_at: datetime) -> str`: immutable artifact kind `context-experiment-v1`.
- Plan schema: `schema=1`, `dataset_hash`, `code_revision`, `base_versions`, `family_configs`, `train_end`, `tune_end`, `test_blocks`, `target_markets`, `outcome_contracts`, `candidate_artifacts`, `policy_version`, `availability_classes`, `created_at`. Candidate models, market lists and policy are fixed before test labels are opened.

- [ ] **RED – no part of one event may cross a split and late result cannot train early.**

```python
from datetime import datetime, timezone
import pytest
from context_models.training import split_rows

def test_late_result_is_not_training_data():
    def date(day):
        return datetime(2026, 9, day, tzinfo=timezone.utc)
    row = {"event_key": "tennis:ATP:1", "decision_at": date(1).isoformat(),
           "result_observed_at": date(4).isoformat(), "target": 1.}
    result = split_rows((row,), train_end=date(2), tune_end=date(5),
                        test_blocks=((date(5), date(6)), (date(6), date(7)), (date(7), date(8))))
    assert result["train"] == ()
    assert result["late_results"] == (row,)
    with pytest.raises(ValueError, match="overlap"):
        split_rows((row,), train_end=date(2), tune_end=date(5),
                    test_blocks=((date(5), date(7)), (date(6), date(8))))
```

- [ ] Run `.codex_test_venv/quality/Scripts/python.exe -m pytest tests/test_context_training.py tests/test_context_replay.py -q -p no:cacheprovider --basetemp=.pytest_tmp/d1-red`; expected missing modules.
- [ ] **Implement price-free dataset assembly.** Use B5/B7/C2/C4 training-row builders and B1 time selection. Raw source columns enter through sport-specific allowlists; reject odds/bookmaker/minimum-price input columns in modeling frames rather than trusting a source filename. For each predicted event, past outcomes and appearance/performance rows must be known before that decision. Store actual observed/imported time; backtests record `reconstructed_at` now and `logical_training_cutoff` then. Never backdate stored `built_at`/receipts to pass a live-state check.
- [ ] **Implement pure historical base replay.** Reuse the existing causal football rate helpers, tennis rating/serve updates and `sports_prematch`/e-sport fit logic on historical slices. Separate pure distribution calculation from production age/receipt guards where needed; do not add a general `ignore_freshness` switch to public prediction. Legacy baseline probabilities remain unchanged, including its original calibration where applicable; preserve pre-market parameters for distribution scoring. Exact model/provenance fingerprints distinguish reconstructed bases from genuinely prospective snapshots. Check replay against stored known base fixtures before using any context label.
- [ ] **Implement event-level split and source classification.**

```python
if decision_at < train_end:
    destination = "train" if result_observed_at <= train_end else "late_results"
elif decision_at < tune_end:
    destination = "tune" if result_observed_at <= tune_end else "late_results"
else:
    destination = next((f"test:{i}" for i, (start, end) in enumerate(test_blocks)
                        if start <= decision_at < end), "outside")
```

All market/head rows of one native event use one decision/split. Validate contiguous increasing half-open test blocks, no overlap with tuning, and no duplicate native event represented under different aliases. Feature scaler, player effects, participation model and calibration fit only earlier windows. Historical rows without verifiable pre-decision feature availability are descriptive/retrospective only; strict activation excludes them and reports excluded counts.
- [ ] **Fit actual effects.** Inner tuning considers the declared alpha grid `(0.01, 0.1, 1.0, 10.0, 100.0)` on training/tuning windows, never final test. Train-only scale and coefficients use B2. Select alpha by event-mean Brier on the fixed target markets, ties prefer larger regularization; save all tuning results. Football/hockey produce home/away heads; tennis serve produces A/B hold heads from successes/trials; winner-only variants produce one antisymmetric head; basketball one margin head. The first distribution calibration variant is explicit identity in parameter space (`joint_calibration={"kind":"identity"}`); it still must pass D2 market calibration checks and must not reuse old market calibrators or certification. A failed check remains failed, not repaired on test data.
- [ ] **Freeze experiment before final labels.** Caller supplies UTC cutoffs and target markets derived from unlabeled date/coverage inventory, not best ROI periods. Require at least three consecutive final blocks in config; insufficient eligible events produces an incomplete report, not smaller thresholds. Persist dataset content hash, coefficient artifacts, feature/variant lists, exact code revision and chosen policy as A1 artifact. `freeze_experiment` rejects updates to an existing experiment and prevents adding an artifact after the experiment has been evaluated. Exact reruns with the same bytes are allowed for reproducibility; a changed model/policy requires new untouched test data.
- [ ] **Add CLI with explicit paths and no implicit production writes.** `scripts/train_context_models.py --observations-db PATH --baselines PATH --config PATH --model-db PATH --output-dir PATH`. All five are required; refuse the production runtime DB in a local/default research run. Read-only observation source, atomic outputs, bounded memory batches. Print per-family real event/feature coverage and failure reason; never tokens or raw credentials.
- [ ] **Run the real available corpus.** Prepare config from the observed coverage report; enumerate tested injury/load/weather/interaction variants before evaluating them. Add a no-context baseline, individual-factor ablations and joint model. Record unsupported feeds/temporal evidence and continue supported families. Save actual training logs and hashes; an empty dataset is an unfinished data dependency, not a successful model build.
- [ ] Add tests for price-column rejection, train-only standardization, late corrections, identical-event aliases, player/participation fitting on prior rows, future season aggregates, target leakage, ambiguous IDs, failed optimization, frozen-config mutation and exact reproducibility. Run with `d1-green`; commit exact source/tests and compact data/training report with message `feat: train context families on causal frozen experiment datasets`.

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

Read `corpus-inventory-20260907.md` for the controller's limited three-database read-only inventory. Thousands of stored forecast rows represented only a few event keys and the common archive had four result-bearing keys. This is not an exhaustive legacy-source inventory and does not prove canonical identity or final-test eligibility. D1 must verify the actual causal corpus, distinguish repeated revisions from independent events, and report exclusions/source boundaries without fabricating an eligible 200-event set or promoting newly imported retrospective context.

Read both `context-contract-decisions.md` and `validation-contract-decisions.md` in this SDD directory completely. The latter closes train-only selection (no train+tune refit), the full hypothesis registry, canonical native identity inventory, ordered paired losses, exact approval/report kinds and opened-test reuse protection. Original thresholds/math remain unchanged.

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-d-validierung-release.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
