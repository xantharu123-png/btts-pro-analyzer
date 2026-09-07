# Kontext-Abnahme, gemeinsame Oberfläche und Release Implementation Plan

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

## D1: Zeitkorrekte Datensätze, echte Trainingsläufe und eingefrorener Versuch

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

## D2: Gepaarte Abnahme, Multiplizität und eng gebundene Aktivierung

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

## D3: Ein gemeinsamer Workerpfad und verständliche flache Karten

**Files:** Create `context_copy.py`, `tests/test_context_copy.py`, `tests/test_context_workflow.py`; modify `wettfinder_automation.py`, `ev_signal_sources.py`, `riskobet_candidates.py`, `wettfinder_surface.py`, `riskobet_surface.py`, `riskobet_ui.py`, `app.py`, plus focused existing workflow/UI tests.

**Interfaces:**

- `public_context_summary(result: dict) -> dict` returns `summary`, `base_probability`, `used_probability`, `delta_pp`, `missing`, `admin_details`. This display projection is per selected market; it never rounds before a decision or recomputes probabilities.
- Worker uses B1→sport features→D2 approval→B3 one snapshot; both ModelSignal/RiskBet EventModelSnapshot receive its immutable ID and used parameters.
- Existing source budgets/caches govern fetches; no new timer and no direct provider calls from a Streamlit render.

- [ ] **RED – known absence with no validated effect must not say it was numerically included.**

```python
from context_copy import public_context_summary

def test_known_absence_is_not_advertised_as_applied():
    result = {"role": "experimental", "factor_roles": {"injuries": "experimental"},
              "selected_market": "home", "base_markets": {"home": .6},
              "used_markets": {"home": .6}, "comparison_markets": {"home": .54},
              "delta_pp": {"home": 0.}, "limitations": [],
              "factor_states": {"injuries": "available"}}
    card = public_context_summary(result)
    assert card["used_probability"] == .6
    assert "Wirkung offen" in card["summary"]
    assert "eingerechnet" not in card["summary"]
```

- [ ] Run D3 files with `d3-red`; expected missing display/workflow API.
- [ ] **Integrate event pipeline once.** Existing worker cutoff and event/schedule IDs feed context before final market selection, retaining alternate markets and price-blind diversity logic already fixed in prior releases. Collect bounded context once per native event; reuse receipts/cached source responses within the existing quota reservation. Compute B3 snapshot once, then build both tabs from it. Event cancellation/start/reschedule invalidates live display based on schedule state; old snapshots remain history. Price-only refresh never calls a context predictor or changes ranking/model identity.
- [ ] Replace old unconditional “Fitness noch nicht numerisch validiert” wording only where actual role supports it; do not globally replace it with “berücksichtigt”. Internal experiments remain admin-only. Missing required context uses unchanged base and a short data caveat, no arbitrary hiding of the event. Ordinary forecasts and the 15K candidate path must retain their distinct release contracts; new probabilities cannot inherit old 15K validation.
- [ ] **Implement copy and card fields.**

```python
labels = {
    ("injuries", "applied"): "Ausfälle eingerechnet",
    ("injuries", "experimental"): "Ausfälle bekannt; Wirkung offen",
    ("workload", "applied"): "Belastung eingerechnet",
    ("workload", "experimental"): "Belastung bekannt; Wirkung offen",
}
```

Use factor data status too: unavailable factor says `Ausfalldaten fehlen`/`Belastungsdaten unvollständig`, not known. Applied zero effect says “eingerechnet; keine relevante Änderung” only at display precision while retaining exact stored delta. Immediately visible card: used forecast, one/two short applied factors, main limitation, separate price. Base and total effect remain traceable with compact values; no new nested tip container. Technical hashes, provider errors, experiment metrics and causal caveats stay in admin detail.
- [ ] Add card fields as backwards-compatible defaults; render server-provided labels with the existing HTML escaping. Tests with `<script>`/HTML-like team and factor text must stay escaped. Changing manual quote must update only price overlay and preserve context ID.
- [ ] **Regression matrix.** All five sports, data missing/partial/available, experimental/applied/zero-applied, stale/rescheduled, duplicate native events, quote absent/low/new, tab switch, shared run in parallel, expired context and old immutable prediction/ticket. Assert forecast counts/order do not change solely due to price. Use spy callbacks to prove one calculation, not just matching rounded percentages.
- [ ] Run new D3 tests plus `tests/test_workflow_integrity.py`, `tests/test_wettfinder_automation.py`, `tests/test_market_scope.py`, `tests/test_tennis_prediction_revisions.py` with `d3-green`.
- [ ] Render actual local app in browser using the applicable frontend testing/browser skill; inspect both tabs at 1440, 1024, 761, 760, 390 and 320 pixels. Check no horizontal overflow, no hidden primary forecast, price separated, no admin internals, no console/page/request errors and functioning filter/rerun. Save current screenshots locally; do not claim visual approval from unit tests. Commit exact source/tests with message `feat: display one evidence-backed context forecast across both tabs`.

## D4: Backup, konsistente Wiederherstellung und Modellrollback

**Files:** Create `scripts/verify_context_runtime.py`, `tests/test_context_runtime_backup.py`; extend `model_artifacts.py`; modify `scripts/stage_runtime_databases.py`, `scripts/backup_runtime_databases.py`, `tests/test_server_jobs.py` only where failing discovery/restore tests require it.

**Interfaces:**

- `verify_context_database(path: Path) -> dict`: returns artifact/manifest/observation/snapshot counts and active slots after SQLite integrity, JSON/hash/reference/schema checks.
- `rollback_model_slots(path: Path, previous_manifest_hash: str, *, expected_manifest: str, published_at: datetime) -> str`: new manifest revision pointing at previously verified model/approval artifacts; never restore the whole DB over newer facts.
- Existing `stage_databases(live_root: Path, current_stage: Path, *, expected_stage_identity: tuple[int, int] | None = None, expected_uid: int | None = None, expected_gid: int | None = None) -> dict`, `create_archive(output_dir: Path, *, root: Path = ROOT, logical_root: Path | None = None, stage_manifest_path: Path | None = None, now: datetime | None = None, integrity_key_path: Path | None = None, migration_marker_path: Path | None = None) -> tuple[Path, int]`, and `verify_archive(archive_path: Path, *, recovery_mode: bool = False) -> int` remain authoritative backup contracts. `ROOT` is the existing constant from `scripts.backup_runtime_databases`, not a new path.

- [ ] **RED – restoring model references must leave newer forecasts/observations intact.**

```python
from datetime import datetime, timedelta, timezone
from model_artifacts import put_artifact, publish_slots, load_manifest, rollback_model_slots
from context_snapshots import compute_once

def test_model_rollback_is_not_history_rollback(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    one = put_artifact(path, kind="test", payload={"v": 1}, created_at=now)
    two = put_artifact(path, kind="test", payload={"v": 2}, created_at=now)
    old = publish_slots(path, {"tennis:ATP": one}, expected_manifest=None, published_at=now)
    new = publish_slots(path, {"tennis:ATP": two}, expected_manifest=old, published_at=now)
    compute_once(path, "a" * 64, lambda: {"used_markets": {"home": .6}})
    rollback_model_slots(path, old, expected_manifest=new, published_at=now + timedelta(seconds=1))
    assert load_manifest(path)[1]["tennis:ATP"] == one
    result = compute_once(path, "a" * 64, lambda: (_ for _ in ()).throw(AssertionError("recomputed")))
    assert result["used_markets"]["home"] == .6
```

- [ ] Run D4 file with `d4-red`; expected missing rollback function.
- [ ] **Implement non-destructive rollback publication.** Read previous manifest, resolve/hash-check every referenced artifact, CAS-publish those slots in one new manifest with rollback reason and actual publication time. Do not delete later artifacts, observations, prediction revisions or financial records. Couple effect and approval slots: a rollback cannot leave a new model paired with an old approval. Readers capture one manifest identity per calculation.
- [ ] **Verify new DB backup explicitly.** Build a temporary application tree with `runtime_state/context_models.db` containing tour states, context models/approvals, observations and snapshots. Use existing sealed staging and SQLite backup path; archive/verify into a separate temporary directory. Extract only verified expected members into a fresh validated restore tree, then run `verify_context_database` and decode both tour states. Compare exact artifact and active manifest hashes, row counts and forecast outputs. Do not overwrite a real runtime DB during this test.
- [ ] Test transactions concurrent with backup: one manifest plus all its artifacts is present, or the preceding complete state; never mixed references. Reject missing artifact, hash mismatch, malformed JSON/type, unexpected path, symlink and invalid legacy/tour schema. Because all new context/tour state is one DB, SQLite backup supplies its transaction snapshot; do not copy the live `.db` file with an ordinary file copy ignoring WAL.
- [ ] Production discovery must cover the **actual configured** runtime path. If it lies outside existing allowed backup roots, report that before activation and add only an explicitly validated runtime-root mapping with tests; do not broadly grant read access to `/etc/betboy` or other secrets. Existing HMAC key, migration marker, backup group restrictions and 15K archive verification must remain byte-for-byte behaviorally unchanged.
- [ ] `scripts/verify_context_runtime.py --database PATH` is read-only and exits nonzero on invalid references; print counts/hashes/status, no secrets. Register its verification in the deployment preflight/restore checks only after the existing trusted update path and tests accept the addition. No separate ad-hoc privileged installer.
- [ ] Run D4 and all server-job/15K integrity tests with `d4-green`; run Linux-only ownership/symlink/restore smoke tests in temporary paths using existing Python, not new prod packages. Commit exact files with message `feat: verify context artifacts in backup and non-destructive model rollback`.

## D5: Volle Regression, empirische Entscheidung und belegtes VPS-Release

**Files:** Update `docs/audits/2026-09-07-kontext-abnahme.md`, `docs/audits/2026-09-07-kontext-daten.md`, `PC_WECHSEL_UEBERGABE.md` and plan checkboxes with verified results only. No blanket staging of screenshots, caches or unrelated reports.

**Interfaces:** Existing trusted updater `/usr/local/sbin/betboy-update <40-character-main-commit>`, SSH alias `betboy-vps`, app `/opt/betboy/app`, venv `/opt/betboy/venv`, services from `deploy/systemd/`.

- [ ] **Verify exactly the release candidate.** Read Git status, diff/check and upstream; prove changed paths match completed A/B/C/D tasks. Request code review using the applicable review skill before claiming completion. Do not dispatch agents unless execution mode/skill/user allows them. All P1/P2 correctness findings affecting this release require fix plus new targeted regression; unchanged empirical failure must not be “fixed” by weakening policy.
- [ ] **Run full local regression.**

```powershell
& .\.codex_test_venv\quality\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/context-release-final
if ($LASTEXITCODE -ne 0) { throw 'Context release tests failed' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Diff check failed' }
```

Use a new suffix if that basetemp already exists. Report actual pass/skip/subtest counts, never the historical 1,724 figure as a current run. Compare Cricket fixtures exactly. Existing account/ticket/HMAC tests and ordinary quote-independent visibility must pass. Validate all Python imports and configured worker commands using current local dependencies.
- [ ] **Evaluate the real frozen experiment before effect activation.** Attach D1/D2 artifact hashes, real events, blocks, coverage, paired statistics, calibration and each family outcome. Technical deployment can include unactivated experimental software and independent tour refresh; document precisely which effects remain unvalidated/unavailable. Do not use fabricated data or a successful source call to satisfy empirical criteria.
- [ ] **Commit/push exact reviewed files.**

```powershell
git diff --cached --name-only
git remote get-url origin
git branch --show-current
```

Verify trusted remote and `main`, stage only the explicit files of completed tasks, inspect staged diff, commit. `git push origin main`; then `git ls-remote origin refs/heads/main` must match local full HEAD. Use managed approval for Git/network operations when required; no force-push and no secret in command output. A documentation-only commit is not described as a functional deployment.
- [ ] **Deploy through the existing trusted updater with an exact hash.**

```powershell
$contextReleaseHead = (git rev-parse HEAD).Trim()
if ($contextReleaseHead -notmatch '^[0-9a-f]{40}$') { throw 'Invalid release revision' }
ssh betboy-vps "sudo /usr/local/sbin/betboy-update $contextReleaseHead"
if ($LASTEXITCODE -ne 0) { throw 'VPS deployment failed' }
```

Immediately before calling, verify upstream equality, clean relevant worktree, available backup and expected previous server revision. Do not bypass updater migration/backup checks or manually reset server files. No application data collection/settlement on the local PC.
- [ ] **Verify production identity and health separately.**

```powershell
ssh betboy-vps 'sudo -u betboy git -C /opt/betboy/app rev-parse HEAD'
ssh betboy-vps 'sudo systemctl is-active betboy-app caddy'
ssh betboy-vps 'sudo systemctl list-timers --all "betboy-*" --no-pager'
ssh betboy-vps 'sudo systemctl --failed --no-pager'
```

Read exact service/timer state, not merely process existence. Check local and public health endpoints used by the current deployment. Verify the backup archive includes and restores the context DB; seven timers are still enabled/scheduled and **do not pull/deploy code**.
- [ ] **Observe one real relevant worker cycle.** Use the existing `betboy-tennis.service`/`betboy-wettfinder.service` and scheduler; if a manual execution is necessary, first check it is not already running and use systemd's single service rather than a duplicate Python process. Record start/end, exit status, actual tour artifact identities/coverage, event/context snapshot counts and data gaps. Timer ACTIVE alone is not evidence of a completed calculation. Respect API budget limits; no forced all-source rescan on repeated UI reloads.
- [ ] **Reload the production UI in a real browser.** Verify used probabilities/roles match persisted snapshot and both tabs show the same event revision; missing and low quotes only affect price copy. Inspect desktop/mobile rendering and console/page/request errors. Check source/schema text and training diagnostics are not leaked into normal cards. Read-only observation only; place no bets.
- [ ] **Finish the handoff with evidence, not a blanket claim.** Record local/GitHub/VPS exact hashes, tests, backup/restore, actual worker result, independently refreshed tours and per-family data/software/empirical/activation status. Include unresolved external data dependencies and the next actionable packet. “Alles erledigt” requires all five sports and the agreed empirical acceptance, not just deployed code. Commit/push the compact final report separately if it was generated after the code commit; identify that documentation-only difference honestly.
