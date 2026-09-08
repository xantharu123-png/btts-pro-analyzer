## Task 19: D4 — Backup, konsistente Wiederherstellung und Modellrollback

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

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-d-validierung-release.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
