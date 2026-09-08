## Task 1: A1 — Unveränderliche Artefakte und atomare Slots

Controller clarification: Test duplicate encoded JSON keys/slots using a raw JSON payload; a Python dict cannot represent duplicate keys. Limit production ownership to the three files listed below. Existing runtime trust helpers may be reused without changing financial integrity contracts. Worktree setup requires an existing .pytest_tmp parent; use unique child names. The hash-pinned scripts/stage_runtime_databases.py has been restored to its original LF bytes locally; do not change it or its pins in this task.

**Files:** Create `model_artifacts.py`, `tests/test_model_artifacts.py`; modify `runtime_paths.py`.

**Interfaces:**

- `canonical_bytes(value: object) -> bytes`: sortierte UTF-8-JSON-Darstellung, `allow_nan=False`, keine implizite Stringkonvertierung unbekannter Typen.
- `put_artifact(path: Path, *, kind: str, payload: dict, created_at: datetime) -> str`: SHA-256 über `{"kind": kind, "payload": payload}`; gleiche Bytes idempotent.
- `load_artifact(path: Path, digest: str) -> dict`: liefert `kind`, `payload`; Hash und JSON-Schema prüfen.
- `load_manifest(path: Path) -> tuple[str | None, dict[str, str]]`: Manifestidentität und Slot-zu-Artefakthash.
- `publish_slots(path: Path, updates: dict[str, str], *, expected_manifest: str | None, published_at: datetime) -> str`: Compare-and-swap; bei veraltetem Vorgänger `ManifestConflict`, niemals unbeteiligte Tour überschreiben.
- Neuer Pfad `runtime_paths.CONTEXT_MODEL_DB_PATH`.

- [ ] **RED – neue Datei mit diesem Roundtrip- und Parallelitätsfall anlegen.**

```python
from datetime import datetime, timezone
import pytest
from model_artifacts import (
    ManifestConflict, load_artifact, load_manifest, put_artifact, publish_slots,
)

def test_publish_keeps_other_tour_and_rejects_stale_writer(tmp_path):
    path = tmp_path / "models.db"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    atp = put_artifact(path, kind="test", payload={"tour": "ATP"}, created_at=now)
    wta = put_artifact(path, kind="test", payload={"tour": "WTA"}, created_at=now)
    first = publish_slots(path, {"tennis:ATP": atp}, expected_manifest=None, published_at=now)
    with pytest.raises(ManifestConflict):
        publish_slots(path, {"tennis:WTA": wta}, expected_manifest=None, published_at=now)
    publish_slots(path, {"tennis:WTA": wta}, expected_manifest=first, published_at=now)
    assert load_manifest(path)[1] == {"tennis:ATP": atp, "tennis:WTA": wta}
    assert load_artifact(path, atp)["payload"] == {"tour": "ATP"}
```

- [ ] Run `.codex_test_venv/quality/Scripts/python.exe -m pytest tests/test_model_artifacts.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a1-red`; expected missing module/API.
- [ ] **Implement canonical storage and schema initialization.** Canonical code:

```python
def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
```

Schema: `artifacts(digest TEXT PRIMARY KEY, kind TEXT NOT NULL, payload BLOB NOT NULL, created_at TEXT NOT NULL)`, `manifests(digest TEXT PRIMARY KEY, predecessor TEXT, payload BLOB NOT NULL, published_at TEXT NOT NULL)`, `active_manifest(id INTEGER PRIMARY KEY CHECK(id=1), digest TEXT NOT NULL REFERENCES manifests(digest))`. Digest includes envelope, not arbitrary filesystem paths. Set `foreign_keys=ON`, `busy_timeout=5000`, and SQLite transaction boundaries explicitly. Reject non-aware timestamps, malformed hashes, changed payload for existing hash and non-finite numbers.

- [ ] **Implement publication in one write transaction.** The core operation is:

```python
connection.execute("BEGIN IMMEDIATE")
if current_digest != expected_manifest:
    connection.rollback()
    raise ManifestConflict("manifest changed")
next_slots = {**current_slots, **updates}
```

Read `current_digest/current_slots` **inside** that transaction, resolve every referenced artifact there, hash `{predecessor, slots, published_at}`, insert manifest and replace only `active_manifest` row. Commit once. Missing artifacts roll back the whole operation. No destructive pruning. For all runtime DB opens, reject symlink/junction components and unsafe ownership/write permissions using the runtime path trust rules; SQLite receives only the configured, validated path, never a path from an artifact. Hashes detect corruption, not an adversary who controls both DB and application.

- [ ] Add failing/passing tests for unchanged artifact id, distinct payload id, rollback on missing artifact, corrupted JSON/hash, concurrent CAS, duplicate slots, real SQLite types, NaN, unsafe path, missing first-install DB and historical manifest availability. Test Linux path/ownership cases separately when Windows cannot supply them.
- [ ] Run the A1 command with `a1-green`, plus `tests/test_runtime_paths.py`; expected all pass.
- [ ] Commit exact files: `git add model_artifacts.py runtime_paths.py tests/test_model_artifacts.py` then `git commit -m "feat: add immutable runtime model artifact registry"`.

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

#### Modellablage und unabhängiger ATP/WTA-Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine WTA-Störung darf einen validen ATP-Stand nicht mehr zurückhalten und umgekehrt.

**Architecture:** Typisierte, unveränderliche JSON-Artefakte und ein transaktionales Manifest liegen im Runtime-SQLite-Speicher. Neue Tour-Modelle werden aus getrennten Daten gebaut; der alte gemeinsame Pickle bleibt ein ausdrücklich gekennzeichneter Übergangslesepfad, keine Quelle vermeintlich getrennter Modelle.

**Tech Stack:** Python, SQLite, pandas, bestehendes SurfaceElo/ServeReturnModel, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), insbesondere Abschnitte 4, 8, 10 und 11.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Keine Spielerzuordnung nach vermutetem Geschlecht aus Namen; kein gemischter Ratingraum.
- Fehlerhafte Tour behält Artefakt, Bauzeit und Abdeckungsdatum; ein Gesamtlauf meldet Fehler/Teilergebnis ehrlich.
- Jahre ab 2010 bis einschließlich aktuellem UTC-Jahr; fehlende neue Saisondatei darf keinen Erfolg mit scheinbar neuer Abdeckung erzeugen.
- Laufzeitdownloads bleiben im Runtime-Cache, nicht unter `tennis/data`.

## Dateigrenzen

Neu: `model_artifacts.py`, `tennis/state_codec.py`, `tennis/tour_state.py`, Tests entsprechend A1–A4. Ergänzungen: `runtime_paths.py`, `tennis/model_state.py`, `scripts/rebuild_state.py`, `scripts/tennis_daily.py`, `tennis/predict.py`, `scripts/run_daily_pipeline.py`. `tennis/elo.py` und `tennis/serve_model.py` erhalten nur explizite Zustands-Export-/Importmethoden, keine veränderte Ratingmathematik.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-a-modelle-tennisrefresh.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
