# Mechanically normalized SDD execution view

## Task 1: A1 — Unveränderliche Artefakte und atomare Slots

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

## Task 2: A2 — Expliziter Tour-State-Codec ohne neue Pickles

**Files:** Create `tennis/state_codec.py`, `tests/test_tennis_state_codec.py`; modify `tennis/elo.py`, `tennis/serve_model.py`, `tennis/model_state.py`.

**Interfaces:**

- `SurfaceElo.to_payload() -> dict`, `SurfaceElo.from_payload(payload: dict) -> SurfaceElo`.
- `ServeReturnModel.to_payload() -> dict`, `ServeReturnModel.from_payload(payload: dict) -> ServeReturnModel`.
- `encode_state(state: ModelState, *, tour: str) -> dict`, `decode_state(payload: dict) -> ModelState`.
- `ModelState` adds defaulted `tour_scope: str = "legacy-combined"`, `stats_through_kind: str = "tournament_start_proxy"`, `artifact_hash: str | None = None`. Artifact hash is assigned after decoding; it is not included in its own hash.

- [ ] **RED – prove numerical parity and reject crossed tours.**

```python
from tennis.elo import SurfaceElo
from tennis.serve_model import ServeReturnModel
from tennis.model_state import ModelState
from tennis.state_codec import encode_state, decode_state
import pytest

def test_tour_codec_preserves_ratings_and_calibration():
    elo = SurfaceElo()
    elo.update("player-a", "player-b", "Clay")
    state = ModelState(elo, ServeReturnModel(), 1.1, 0.03, 2000,
                       1788739200.0, "2026-09-01", 0.3, tour_scope="ATP")
    result = decode_state(encode_state(state, tour="ATP"))
    assert result.tour_scope == "ATP"
    assert result.elo.win_probability("player-a", "player-b", "Clay") == \
        state.elo.win_probability("player-a", "player-b", "Clay")
    assert result.calibrate_match(.7, "a", "b", "ATP") == \
        state.calibrate_match(.7, "a", "b", "ATP")
    with pytest.raises(ValueError):
        encode_state(state, tour="WTA")
```

- [ ] Run `.codex_test_venv/quality/Scripts/python.exe -m pytest tests/test_tennis_state_codec.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a2-red`; expected missing codec.
- [ ] **Implement rating serialization.** Export only `overall` and four `by_surface` maps, each player to `[finite_rating, nonnegative_integer_matches]`. Rehydrate through new `_RatingTable` objects; never `setattr` arbitrary payload keys. No player creation merely from querying an unknown name.

```python
def to_payload(self):
    return {"overall": dict(self.overall._table),
            "by_surface": {s: dict(t._table) for s, t in self.by_surface.items()}}
```

- [ ] **Implement serve serialization.** Fixed keys: `hold_avg`, `break_avg`, `half_life_days`, `split_indoor`, and sorted `rows`. Each row has `player`, `bucket`, `sv_gms`, `sv_held`, `ret_gms`, `ret_breaks`, `sv_opp_break_sum`, `ret_opp_hold_sum`, `last_date`. Preserve full numeric precision; reject negative counts, successes above games, unknown buckets, duplicate `(player,bucket)`, invalid dates, bool-as-number and non-finite values. Constructor parameters and every `_Accum` slot are explicit.

```python
slots = ("sv_gms", "sv_held", "ret_gms", "ret_breaks",
         "sv_opp_break_sum", "ret_opp_hold_sum", "last_date")
row = {"player": player, "bucket": bucket}
for name in slots:
    value = getattr(accumulator, name)
    row[name] = value.isoformat() if name == "last_date" and value is not None else value
```

- [ ] **Implement model envelope.** Keys: `schema=1`, `tour`, `elo`, `serve`, `cal_a`, `cal_b`, `cal_samples`, `cal_wta_a`, `cal_wta_b`, `cal_wta_samples`, `built_at`, `stats_through`, `stats_through_kind`, `serve_weight`. Reject missing/unexpected keys, unsupported tours/schema and future/non-finite build times when selected for a decision cutoff. A legacy-combined state cannot be encoded as tour-specific. Existing `load_state` applies legacy defaults via `getattr`; no rewrite of legacy artifacts.
- [ ] Add roundtrips with populated serve accumulators, dates/decay, indoor split, WTA constants, reversed players and bad schemas. Compare all stored fields, not only one prediction.
- [ ] Run codec plus `tests/test_tennis_model.py`, `tests/test_tennis_predict.py`, `tests/test_runtime_paths.py`, with `a2-green`; expected parity with legacy calculations.
- [ ] Commit exact A2 files with message `feat: encode isolated tennis states as typed runtime artifacts`.

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

## Task 3: A3 — Pro Tour bauen und teilweise veröffentlichen

**Files:** Create `tennis/tour_state.py`, `tests/test_tennis_tour_state.py`; modify `tennis/model_state.py`, `scripts/rebuild_state.py`, `tests/test_tennis_training_refresh.py`.

**Interfaces:**

- `training_years(as_of: datetime) -> tuple[int, ...]`.
- `build_tour_state(tour: str, *, as_of: datetime, refresh_training_data: bool = True) -> ModelState`.
- `load_tour_state(tour: str, *, path: Path = CONTEXT_MODEL_DB_PATH, allow_legacy: bool = False) -> ModelState`; missing tour raises `TourUnavailable`; wrong tour raises `ValueError`.
- `refresh_tours(*, path: Path, as_of: datetime, builder: Callable[[str], ModelState]) -> dict`. Result: `status` (`complete`, `partial`, `failed`), `tours` with per-tour `status`, `artifact_hash`, `built_at`, `stats_through`, `stats_through_kind`, `error_type`. Do not persist secret-containing exception strings.

- [ ] **RED – failed WTA must not cancel ATP publication.**

```python
from datetime import datetime, timezone
from tennis.elo import SurfaceElo
from tennis.serve_model import ServeReturnModel
from tennis.model_state import ModelState
from tennis.tour_state import refresh_tours, load_tour_state, training_years

def test_atp_publishes_even_when_wta_fails(tmp_path):
    now = datetime(2027, 1, 2, tzinfo=timezone.utc)
    def builder(tour):
        if tour == "WTA":
            raise OSError("source unavailable")
        elo = SurfaceElo()
        elo.update("a", "b", "Hard")
        return ModelState(elo, ServeReturnModel(), 1., 0., 2000,
                          now.timestamp(), "2026-12-28", .3, tour_scope="ATP")
    result = refresh_tours(path=tmp_path / "models.db", as_of=now, builder=builder)
    assert result["status"] == "partial"
    assert load_tour_state("ATP", path=tmp_path / "models.db").tour_scope == "ATP"
    assert training_years(now)[-1] == 2027
```

- [ ] Run the new file with `a3-red`; expected missing tour module.
- [ ] **Extract ATP build from `model_state.build_state`.** Only ATP stats/ATP calibration in this path. Filter input by cutoff; retain causal ordering, retired-match exclusion, tour-level serve restriction, indoor handling and calibration orientation. The backtest already isolates `tours=("atp",)`; pass exactly that. Keep calibration-year selection explicit and bounded by `as_of.year`; do not opportunistically retune calibration policy during separation.

```python
def training_years(as_of):
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("aware UTC cutoff required")
    return tuple(range(2010, as_of.astimezone(timezone.utc).year + 1))
```

- [ ] **Extract WTA build independently.** WTA results feed only WTA Elo. Use the existing WTA result path and WTA-only backtest; never invoke `load_atp_stats`. Copy only an allowlist of sport/result columns out of odds-bearing files before updating ratings/calibration. Existing WTA serve behavior stays Elo-only until independently covered; instantiate WTA serve constants but do not fabricate boxscores. WTA coverage is `result_date`, not ATP tournament-start coverage. Add mocks that fail immediately if the other tour's loader is called.
- [ ] **Implement validated publication.** Encode/decode, check predictions finite and all input coverage no later than `as_of`, then `put_artifact`. Load manifest and CAS-update one tour slot. On conflict reload and retry at most three times; never publish an incoming tour with older actual coverage than its current slot merely because its build timestamp is newer. A failed fetch does not call `put_artifact` or alter that tour's metadata.

```python
statuses = [record["status"] for record in result["tours"].values()]
healthy = {"published", "retained_fresh"}
result["status"] = ("complete" if all(s in healthy for s in statuses)
                    else "partial" if any(s in healthy for s in statuses) else "failed")
```

- [ ] Adapt rebuild CLI: each stale tour is attempted separately; fresh tours have `retained_fresh` status and count as healthy, not failed. `--force` rebuilds both, data refresh remains default, partial/failed return nonzero with per-tour diagnostics. `--if-stale-days` evaluates each tour independently. Preserve old `build_state` only for callers explicitly requesting the legacy combined path; replace its fixed 2026 end with UTC current year as well.
- [ ] Add WTA-success/ATP-failure, retained old WTA, first-install missing WTA, both failures, all-fresh skip, refresh-current coverage regression, simultaneous writers, 2026→2027 and unavailable new-season tests. Check `status` computation handles `retained_fresh` without claiming a new publication.
- [ ] Run new and existing training-refresh/cache tests with `a3-green`; expected no seed changes and correct partial exit code.
- [ ] Commit exact A3 files with message `fix: publish ATP and WTA refreshes independently`.

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

## Task 4: A4 — Leser, laufende Prognosen und Betriebsnachweis umstellen

**Files:** Modify `scripts/tennis_daily.py`, `tennis/predict.py`, `scripts/run_daily_pipeline.py`; tests `tests/test_tennis_pending_refresh.py`, `tests/test_tennis_pipeline.py`, `tests/test_tennis_predict.py`, new `tests/test_tennis_tour_readers.py`.

**Interfaces:** Consume `load_tour_state`; `predict_match` continues receiving `ModelState`. It validates `getattr(state, "tour_scope", "legacy-combined")` against requested tour and adds the actual `artifact_hash`, build time and named coverage kind to `context_evidence`. No price is included in identity.

- [ ] **RED – prevent a valid ATP object from silently powering WTA.**

```python
from datetime import datetime, timezone
import pytest
from tennis.elo import SurfaceElo
from tennis.serve_model import ServeReturnModel
from tennis.model_state import ModelState
from tennis.predict import predict_match

def test_prediction_rejects_cross_tour_state():
    state = ModelState(SurfaceElo(), ServeReturnModel(), 1., 0., 0,
                       1., "1970-01-01", .3, tour_scope="ATP")
    with pytest.raises(ValueError, match="tour"):
        predict_match(state, "a", "b", "Hard", tour="WTA",
                      as_of=datetime(2026, 9, 7, tzinfo=timezone.utc))
```

- [ ] Run tour-readers tests with `a4-red`; current predictor should accept crossed state, exposing the bug.
- [ ] **Implement explicit selection in initial and pending scans.** Load each tour once into a local per-run dictionary; selection occurs using fixture `tour`, never a shared mutable default. A missing tour adds a per-tour data error while the healthy tour continues. Legacy fallback is allowed only explicitly during migration and keeps `tour_scope=legacy-combined`, old coverage and legacy model identity. Hash exactly the legacy bytes read through the existing trusted pickle handle and assign that hash as identity; do not claim two new tour artifacts by re-encoding the combined state. It never populates an isolated slot. Reader/UI does not train a replacement implicitly.

```python
scope = getattr(state, "tour_scope", "legacy-combined")
if scope != "legacy-combined" and scope != tour:
    raise ValueError("model tour differs from fixture tour")
```

- [ ] Pending refresh must create a new prediction revision when tour artifact changes; preserve original forecasts and reject events started/cancelled during refresh. Store per-tour model status, not one `model_stats_through` that makes both fresh. Keep `run_daily_pipeline` scanning after a partial rebuild while its aggregate status remains partial/error. Existing tennis tab reads snapshots rather than loading/training models.
- [ ] Tests use two states with identical player spellings and deliberately different Elo/calibration values; assert each fixture uses its own state. Add no-implicit-build, legacy-labelled fallback, stale WTA plus fresh ATP and model-revision/no-quote-revision tests.
- [ ] Run A1–A4 files and tennis regression modules with `a4-green`; expected no change to settlement or quote-visible forecast rules.
- [ ] Commit exact changed reader/test files with message `fix: consume tour-specific model identities in tennis scans`.
- [ ] Before independently deploying A, execute D4 backup/restore and D5 technical-release checks for A's exact commit. Real source probes must show ATP progress separately from WTA failure/success; fixture/unit tests cannot prove a fresh live model. Record the result in `docs/audits/2026-09-07-kontext-daten.md` and the handoff.

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

## Task 5: B1 — Beobachtungen, Korrekturen und Frische

**Files:** Create `context_observations.py`, `context_models/contracts.py`, package `__init__.py` files, `tests/test_context_observations.py`.

**Interfaces:**

- `append_observation(path: Path, record: dict, *, observed_at: datetime) -> str`.
- `observations_as_of(path: Path, event_key: str, *, cutoff: datetime, schedule_revision: str, mode: str = "prospective") -> tuple[dict, ...]`.
- `factor_state(rows: tuple[dict, ...], *, cutoff: datetime, scheduled_start: datetime, policy: dict) -> dict` returns `state`, `refs`, `coverage`, `fresh_until`, `policy_version`.
- Record keys: `event_key`, `sport`, `competition`, `format`, `subject_id`, `kind`, `source`, `source_schema`, `source_revision`, `schedule_revision`, `published_at`, `publication_proof`, `valid_from`, `valid_until`, `complete`, `payload`. `observed_at` is assigned by ingestion clock, never copied from provider data.

- [ ] **RED – a late correction must not enter an earlier prediction.**

```python
from datetime import datetime, timedelta, timezone
from context_observations import append_observation, observations_as_of

def test_late_injury_correction_is_not_backdated(tmp_path):
    path = tmp_path / "models.db"
    cutoff = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
    row = dict(event_key="api-football:football:1", sport="football",
               competition="39", format="90min", subject_id="player:7",
               kind="availability", source="api-football", source_schema="injuries-v3",
               source_revision="r1", schedule_revision="s1", published_at=None,
               publication_proof=None, valid_from=cutoff.isoformat(),
               valid_until=None, complete=False, payload={"status": "out"})
    first = append_observation(path, row, observed_at=cutoff)
    corrected = {**row, "source_revision": "r2", "payload": {"status": "available"}}
    append_observation(path, corrected, observed_at=cutoff + timedelta(hours=1))
    rows = observations_as_of(path, row["event_key"], cutoff=cutoff,
                              schedule_revision="s1")
    assert [r["digest"] for r in rows] == [first]
    assert rows[0]["payload"]["status"] == "out"
```

- [ ] Run `.codex_test_venv/quality/Scripts/python.exe -m pytest tests/test_context_observations.py -q -p no:cacheprovider --basetemp=.pytest_tmp/b1-red`; expected missing module.
- [ ] **Implement append-only observation tables in A1's DB.** Separate content identity from receipt identity: canonical source/content digest plus an immutable receipt row for each actual fetch. Exact duplicate ingestion of one receipt is idempotent; a later genuine recheck of unchanged content gets a new receipt and can refresh freshness without rewriting first-observed time. Hash includes actual observation time and source revision, not just status text.

```sql
CREATE TABLE IF NOT EXISTS context_observations (
  digest TEXT PRIMARY KEY,
  event_key TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  schedule_revision TEXT NOT NULL,
  source TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  payload BLOB NOT NULL
);
```

- [ ] **Implement time selection.** Canonical timestamps are UTC with fixed precision before comparison. Prospective query requires `observed_at <= cutoff`; then choose the newest qualifying source/subject/kind revision. Conflicting simultaneous sources remain conflicting unless an explicit source-precedence policy resolves them. `mode="historical"` may include verifiable earlier publication only through a recognized archived-publication proof; it labels such rows `archival_verified` and everything else `retrospective`. A provider's bare `verified` flag is not proof. Strict D2 cohorts accept only prospective or separately verified prior publication, never a fabricated observation time.
- [ ] **Implement versioned freshness policy.** Initial operational policy `context-freshness-v1`: availability/expected lineup receipts expire after 6 hours, and after 30 minutes when kickoff is within 2 hours; confirmed lineups are tied to exact schedule revision and expire at kickoff; weather receipt expires after 3 hours and forecast-valid interval must include kickoff; immutable completed workload facts have no wall-clock expiry, but coverage freshness and corrections are evaluated separately. These are configurable operational expiry periods, not effect sizes or claims of provider completeness. Copy existing stricter source limits when present. Empty `complete=False` list is missing, not healthy. Event reschedule/cancellation invalidates event-bound observations.

```python
if not rows or not any(row["complete"] for row in rows):
    return {"state": "missing", "refs": [r["digest"] for r in rows],
            "coverage": "incomplete", "fresh_until": None,
            "policy_version": policy["version"]}
```

This branch applies to factors that require a complete collection; a single confirmed absence can be available as a reported-player fact while the team's overall absence coverage remains incomplete. Represent those as separate factors, not one misleading state.

- [ ] Add tests for later unchanged recheck, missing vs empty-complete, partial player fact, stale, source conflict, future publication, naive timestamps, moved fixture, identical names/different native IDs, walkover and genuine retrospective history. Write the normalized record fixture for each test explicitly.
- [ ] Run B1 and context-coverage regression files with `b1-green`; commit exact files with message `feat: persist causal context observations and coverage revisions`.

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

#### Kontextkern, Fußballausfälle und Tennisbelastung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tatsächliche Spieler- und Belastungsmerkmale erzeugen numerisch nachvollziehbare Vergleichsprognosen; nur empirisch freigegebene Varianten verändern die Nutzerprognose.

**Architecture:** Append-only Beobachtungen liefern versionierte Merkmale zum Entscheidungszeitpunkt. Regularisierte Modelle lernen Änderungen gegenüber eingefrorenen Basisparametern. Ein gemeinsamer Snapshot speichert Basis, experimentelle Vergleichsrechnung und tatsächlich verwendete Verteilung getrennt.

**Tech Stack:** Python, SQLite, NumPy/SciPy, bestehende Fußballverteilungen und Tennissimulator, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), insbesondere Abschnitte 4–7, 9 und 11.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Quote verändert weder Modell noch Reihenfolge; keine neue Marktverbotsliste.
- `available/missing/stale/conflicting/not_applicable` und `not_applied/experimental/applied` bleiben getrennt.
- Keine rückdatierten Beobachtungen, kein frei erfundener Star- oder Fünfsatzabschlag.
- Spielerreferenz ist die tatsächlich in der Basis enthaltene Besetzung; kein fiktiv immer gesunder Kader.
- Neue Torwirkung wird nicht ungeprüft auf Ecken, Karten oder Halbzeit übertragen.
- Die B-Aufgaben liefern implementierte Vergleichsmodelle. Produktive Anwendung erfordert D1/D2; ein leeres `applied=False`-Gerüst ist keine abgeschlossene Integration.

## Dateigrenzen und gemeinsame Datenverträge

Neue kleine Module: `context_observations.py`, `context_snapshots.py`, `context_models/__init__.py`, `context_models/contracts.py`, `context_models/offset.py`, `context_models/football.py`, `context_models/tennis.py`, `context_sources/__init__.py`, `context_sources/football.py`, `context_sources/tennis.py`. Bestehende Provider normalisieren in diese Module; sie lernen keine Effekte.

Die folgenden Dict-Verträge sind feste Schnittstellen, nicht beliebige Durchreichbehälter. `context_models/contracts.py` prüft erlaubte Schlüssel, echte Typen, endliche Zahlen und zeitzonenbehaftete ISO-Zeitpunkte.

- **Event:** `event_key`, `sport`, `competition`, `format`, `home_id`, `away_id`, `scheduled_start`, `schedule_revision`, `status`. Native IDs mit Quellennamensraum; `status` ist `scheduled`, `cancelled`, `started` oder `completed`.
- **FeatureVector:** `version`, `event_key`, `cutoff`, `values` (Name zu Zahl oder `None`), `states` (Name zu Datenstatus), `refs` (Name zu Beobachtungshashes), `coverage` (versionierter Abdeckungsfall), `reference_hash`.
- **BaseDistribution:** `version`, `model_hash`, `event_key`, `cutoff`, `family`, `params`, `markets`, `history_refs`, `reference_weights`. `markets` enthält marktvertragstreue Wahrscheinlichkeiten; `reference_weights` dokumentiert die wirklich für die Basis verwendeten historischen Gewichte getrennt nach Team und Modellkomponente (Angriff/Abwehr, Heim-/Auswärtsanteil), nicht ein erfundenes gemeinsames Durchschnittsfenster. Jeder Komponentenwert enthält native Eventreferenzen und normalisierte Gewichte.
- **EffectArtifact:** `schema=1`, `sport`, `family`, `feature_version`, `feature_names`, `heads`, `preprocessing_artifacts`, `joint_calibration`, `training_end`, `training_refs_hash`, `population`, `coverage`, `model_variant`. `heads` enthält benannte B2-Fits mit `link`, `scale`, `coef`, `alpha`, `n_rows`: `home/away` für Tor-/Hockeyraten, `hold_a/hold_b` für Tennisaufschlag, `winner` für binäre Sieger, `margin` für Basketball. Listen sind JSON-Zahlenlisten, keine NumPy-Objekte. `preprocessing_artifacts` bindet die Hashes trainierter Teilnahme-/Referenzmodelle; erste gemeinsame Parameterkalibrierung ist explizit `{"kind":"identity"}`. Kein `approved=True` im Modellpayload; die Freigabe liegt in einem separaten D2-Abnahmeartefakt und muss Hash/Population treffen.
- **ContextResult:** `event_key`, `base_hash`, `effect_hash`, `role`, `factor_roles`, `factor_states`, `feature_refs`, `base_params`, `comparison_params`, `used_params`, `base_markets`, `comparison_markets`, `used_markets`, `delta_pp`, `limitations`. Experimentelle Vergleichsrechnung ist nicht automatisch die verwendete Zahl. Die Kartenprojektion ergänzt `selected_market`, ohne den gespeicherten Eventstand zu ändern.
- **TrainingRow:** `event_key`, `decision_at`, `result_observed_at`, `block`, `population`, `coverage`, `feature_names`, `x`, `offset`, `target`, `trials`, `base_hash`, `feature_refs`, `evidence_class`. Alle Zeilen eines Events bleiben im selben Split; `target` ist nur für Training/Auswertung, niemals ein Prognosemerkmal.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

## Task 6: B2 — Reale regularisierte Offset-Schätzung

**Files:** Create `context_models/offset.py`, `tests/test_context_offset.py`; extend `context_models/contracts.py`.

**Interfaces:**

- `fit_offset(x: np.ndarray, offset: np.ndarray, target: np.ndarray, *, link: str, alpha: float, trials: np.ndarray | None = None) -> dict` returns `link`, `scale`, `coef`, `alpha`, `n_rows`.
- `offset_delta(model: dict, x: np.ndarray) -> np.ndarray`.
- `adjust_parameters(base: np.ndarray, delta: np.ndarray, *, link: str) -> np.ndarray`.
- `link` is `log_rate`, `logit`, or `identity`; offsets are already in link space. Binomial targets are successes and `trials` counts; default trials is one. No intercept is fitted in this residual layer, preserving the defined zero-difference roster reference. Any joint calibration has its own D1-trained, versioned model variant.

- [ ] **RED – learn a nonzero effect from data, not a constant.**

```python
import numpy as np
from context_models.offset import fit_offset, offset_delta, adjust_parameters

def test_learned_count_effect_and_zero_reference():
    x = np.array([[-1.], [0.], [1.]] * 40)
    target = np.array([1., 2., 4.] * 40)
    model = fit_offset(x, np.full(120, np.log(2.)), target,
                       link="log_rate", alpha=.1)
    delta = offset_delta(model, np.array([[0.], [1.]]))
    assert delta[0] == 0.
    assert delta[1] > 0.
    adjusted = adjust_parameters(np.array([2., 2.]), delta, link="log_rate")
    assert adjusted[0] == 2.
    assert adjusted[1] > adjusted[0]
```

- [ ] Run `tests/test_context_offset.py` with `b2-red`; expected missing estimator.
- [ ] **Implement standardization and objective.** Use training-only feature scale `max(std, 1e-8)` without subtracting a mean from the reference-difference vector. Validate aligned finite arrays, nonnegative alpha, legal targets/trials; all-zero columns receive zero coefficient. Poisson and binomial use SciPy stable functions, with exact gradient. Gaussian keeps the baseline scale in this first variant.

```python
def objective(beta):
    eta = offset + z @ beta
    if link == "log_rate":
        mu = np.exp(eta)
        loss = np.mean(mu - target * eta)
        residual = mu - target
    elif link == "logit":
        loss = np.mean(trials * np.logaddexp(0., eta) - target * eta)
        residual = trials * scipy.special.expit(eta) - target
    else:
        residual = eta - target
        loss = .5 * np.mean(residual ** 2)
    return (float(loss + .5 * alpha * np.dot(beta, beta)),
            z.T @ residual / len(z) + alpha * beta)
```

Use `scipy.optimize.minimize(objective, np.zeros(z.shape[1]), jac=True, method="L-BFGS-B")`; reject non-convergence and non-finite objective/parameters instead of publishing. Stable Poisson evaluation must detect overflow and return an invalid fit, not silently clip rates to manufacture a better test loss. Training bounds, if needed, become a declared model variant fitted/selected in D1, not a live-only repair. Serialize fitted scales/coefficients with `.tolist()` and convert back with `np.asarray` only inside numerical functions.

- [ ] **Implement inverse links without percentage-point fudge.**

```python
if link == "log_rate":
    result = base * np.exp(delta)
elif link == "logit":
    result = scipy.special.expit(scipy.special.logit(base) + delta)
else:
    result = base + delta
```

Require positive rate, strictly interior probability, finite margin; impossible parameters return a typed model error and preserve the baseline via B3. A missing feature is not converted to zero: only a trained missingness variant may consume that coverage and its explicit mask. `alpha` selection is D1's inner-window job, not a hardcoded empirical effect.
- [ ] Add binomial, Gaussian, side reversal, zero coefficients, finite differences for gradients, single-row rejection, mismatched shapes, bool/NaN, unsupported link and convergence-error tests. Synthetic data tests prove mechanics only.
- [ ] Run B2 with `b2-green`; commit exact files with message `feat: learn regularized context offsets against frozen base models`.

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

#### Kontextkern, Fußballausfälle und Tennisbelastung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tatsächliche Spieler- und Belastungsmerkmale erzeugen numerisch nachvollziehbare Vergleichsprognosen; nur empirisch freigegebene Varianten verändern die Nutzerprognose.

**Architecture:** Append-only Beobachtungen liefern versionierte Merkmale zum Entscheidungszeitpunkt. Regularisierte Modelle lernen Änderungen gegenüber eingefrorenen Basisparametern. Ein gemeinsamer Snapshot speichert Basis, experimentelle Vergleichsrechnung und tatsächlich verwendete Verteilung getrennt.

**Tech Stack:** Python, SQLite, NumPy/SciPy, bestehende Fußballverteilungen und Tennissimulator, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), insbesondere Abschnitte 4–7, 9 und 11.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Quote verändert weder Modell noch Reihenfolge; keine neue Marktverbotsliste.
- `available/missing/stale/conflicting/not_applicable` und `not_applied/experimental/applied` bleiben getrennt.
- Keine rückdatierten Beobachtungen, kein frei erfundener Star- oder Fünfsatzabschlag.
- Spielerreferenz ist die tatsächlich in der Basis enthaltene Besetzung; kein fiktiv immer gesunder Kader.
- Neue Torwirkung wird nicht ungeprüft auf Ecken, Karten oder Halbzeit übertragen.
- Die B-Aufgaben liefern implementierte Vergleichsmodelle. Produktive Anwendung erfordert D1/D2; ein leeres `applied=False`-Gerüst ist keine abgeschlossene Integration.

## Dateigrenzen und gemeinsame Datenverträge

Neue kleine Module: `context_observations.py`, `context_snapshots.py`, `context_models/__init__.py`, `context_models/contracts.py`, `context_models/offset.py`, `context_models/football.py`, `context_models/tennis.py`, `context_sources/__init__.py`, `context_sources/football.py`, `context_sources/tennis.py`. Bestehende Provider normalisieren in diese Module; sie lernen keine Effekte.

Die folgenden Dict-Verträge sind feste Schnittstellen, nicht beliebige Durchreichbehälter. `context_models/contracts.py` prüft erlaubte Schlüssel, echte Typen, endliche Zahlen und zeitzonenbehaftete ISO-Zeitpunkte.

- **Event:** `event_key`, `sport`, `competition`, `format`, `home_id`, `away_id`, `scheduled_start`, `schedule_revision`, `status`. Native IDs mit Quellennamensraum; `status` ist `scheduled`, `cancelled`, `started` oder `completed`.
- **FeatureVector:** `version`, `event_key`, `cutoff`, `values` (Name zu Zahl oder `None`), `states` (Name zu Datenstatus), `refs` (Name zu Beobachtungshashes), `coverage` (versionierter Abdeckungsfall), `reference_hash`.
- **BaseDistribution:** `version`, `model_hash`, `event_key`, `cutoff`, `family`, `params`, `markets`, `history_refs`, `reference_weights`. `markets` enthält marktvertragstreue Wahrscheinlichkeiten; `reference_weights` dokumentiert die wirklich für die Basis verwendeten historischen Gewichte getrennt nach Team und Modellkomponente (Angriff/Abwehr, Heim-/Auswärtsanteil), nicht ein erfundenes gemeinsames Durchschnittsfenster. Jeder Komponentenwert enthält native Eventreferenzen und normalisierte Gewichte.
- **EffectArtifact:** `schema=1`, `sport`, `family`, `feature_version`, `feature_names`, `heads`, `preprocessing_artifacts`, `joint_calibration`, `training_end`, `training_refs_hash`, `population`, `coverage`, `model_variant`. `heads` enthält benannte B2-Fits mit `link`, `scale`, `coef`, `alpha`, `n_rows`: `home/away` für Tor-/Hockeyraten, `hold_a/hold_b` für Tennisaufschlag, `winner` für binäre Sieger, `margin` für Basketball. Listen sind JSON-Zahlenlisten, keine NumPy-Objekte. `preprocessing_artifacts` bindet die Hashes trainierter Teilnahme-/Referenzmodelle; erste gemeinsame Parameterkalibrierung ist explizit `{"kind":"identity"}`. Kein `approved=True` im Modellpayload; die Freigabe liegt in einem separaten D2-Abnahmeartefakt und muss Hash/Population treffen.
- **ContextResult:** `event_key`, `base_hash`, `effect_hash`, `role`, `factor_roles`, `factor_states`, `feature_refs`, `base_params`, `comparison_params`, `used_params`, `base_markets`, `comparison_markets`, `used_markets`, `delta_pp`, `limitations`. Experimentelle Vergleichsrechnung ist nicht automatisch die verwendete Zahl. Die Kartenprojektion ergänzt `selected_market`, ohne den gespeicherten Eventstand zu ändern.
- **TrainingRow:** `event_key`, `decision_at`, `result_observed_at`, `block`, `population`, `coverage`, `feature_names`, `x`, `offset`, `target`, `trials`, `base_hash`, `feature_refs`, `evidence_class`. Alle Zeilen eines Events bleiben im selben Split; `target` ist nur für Training/Auswertung, niemals ein Prognosemerkmal.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

## Task 7: B3 — Eine gemeinsame Rechenrevision und unveränderte Basis bei Experimenten

**Files:** Create `context_snapshots.py`, `tests/test_context_snapshots.py`; extend contracts.

**Interfaces:**

- `snapshot_key(event: dict, *, base_hash: str, context_refs: tuple[str, ...], feature_version: str, effect_hash: str | None, decision_at: datetime, approval_hash: str | None) -> str`.
- `compute_once(path: Path, key: str, compute: Callable[[], dict]) -> dict`; callback is deterministic, CPU-only, no provider/DB calls.
- `select_context_result(base: dict, comparison: dict | None, *, effect_hash: str | None, approval: dict | None, factor_roles: dict, factor_states: dict, limitations: list[str]) -> dict` returns ContextResult. Approval input is a verified D2 decision, never arbitrary provider JSON.

- [ ] **RED – identical reads compute once.**

```python
from context_snapshots import compute_once

def test_shared_snapshot_computes_once(tmp_path):
    calls = []
    def calculate():
        calls.append(1)
        return {"used_markets": {"home": .6}}
    first = compute_once(tmp_path / "models.db", "a" * 64, calculate)
    second = compute_once(tmp_path / "models.db", "a" * 64, calculate)
    assert first == second
    assert len(calls) == 1
```

- [ ] Run B3 test file with `b3-red`; expected missing module.
- [ ] **Implement snapshot identity and atomic materialization.** Hash a fixed allowlist of Event identity, kickoff/schedule, base, sorted context references, feature/effect/approval identity and shared worker decision cutoff. Unknown keys including odds/price are rejected from model input; UI readers receive the persisted cutoff and do not manufacture a new one on each rerun. An approval transition changes which distribution is used, hence is part of identity.

```python
connection.execute("BEGIN IMMEDIATE")
row = connection.execute("SELECT payload FROM context_snapshots WHERE key=?", (key,)).fetchone()
if row is not None:
    connection.commit()
    return json.loads(row[0])
result = compute()
payload = canonical_bytes(result)
connection.execute("INSERT INTO context_snapshots(key,payload) VALUES (?,?)", (key, payload))
connection.commit()
return result
```

Initialize table before transaction; on callback error roll back. Existing key with corrupted bytes fails integrity check instead of recomputing and silently replacing history. Include payload digest. Use A1 connection/path rules. A transaction keeps two concurrent workers from doing the same CPU computation; never hold it across network/training. A process crash may require recomputation but cannot publish half a snapshot.
- [ ] **Implement role/used value selection.**

```python
role = "applied" if approval is not None and comparison is not None else (
    "experimental" if comparison is not None else "not_applied")
used = comparison if role == "applied" else base
delta_pp = {k: 100. * (used["markets"][k] - base["markets"][k])
            for k in used["markets"] if k in base["markets"]}
```

Approval must bind effect hash, population, family, feature version, coverage and model variant (D2). Recompute from `base.params`, never `prior.used_params`. An accepted zero-coefficient effect still has `role=applied`. Keep experimental comparisons out of ordinary probability/15K fields.
- [ ] Add tests for price/Tab invariance, changed schedule/context/model/approval creates new key, stale feature returning to base, repeated adjustment not compounded, accepted zero effect, unknown approval, callback failure, concurrent workers and historical snapshot immutability.
- [ ] Run B3 with `b3-green`; commit exact files with message `feat: share immutable context calculations across forecast surfaces`.

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

#### Kontextkern, Fußballausfälle und Tennisbelastung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tatsächliche Spieler- und Belastungsmerkmale erzeugen numerisch nachvollziehbare Vergleichsprognosen; nur empirisch freigegebene Varianten verändern die Nutzerprognose.

**Architecture:** Append-only Beobachtungen liefern versionierte Merkmale zum Entscheidungszeitpunkt. Regularisierte Modelle lernen Änderungen gegenüber eingefrorenen Basisparametern. Ein gemeinsamer Snapshot speichert Basis, experimentelle Vergleichsrechnung und tatsächlich verwendete Verteilung getrennt.

**Tech Stack:** Python, SQLite, NumPy/SciPy, bestehende Fußballverteilungen und Tennissimulator, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), insbesondere Abschnitte 4–7, 9 und 11.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Quote verändert weder Modell noch Reihenfolge; keine neue Marktverbotsliste.
- `available/missing/stale/conflicting/not_applicable` und `not_applied/experimental/applied` bleiben getrennt.
- Keine rückdatierten Beobachtungen, kein frei erfundener Star- oder Fünfsatzabschlag.
- Spielerreferenz ist die tatsächlich in der Basis enthaltene Besetzung; kein fiktiv immer gesunder Kader.
- Neue Torwirkung wird nicht ungeprüft auf Ecken, Karten oder Halbzeit übertragen.
- Die B-Aufgaben liefern implementierte Vergleichsmodelle. Produktive Anwendung erfordert D1/D2; ein leeres `applied=False`-Gerüst ist keine abgeschlossene Integration.

## Dateigrenzen und gemeinsame Datenverträge

Neue kleine Module: `context_observations.py`, `context_snapshots.py`, `context_models/__init__.py`, `context_models/contracts.py`, `context_models/offset.py`, `context_models/football.py`, `context_models/tennis.py`, `context_sources/__init__.py`, `context_sources/football.py`, `context_sources/tennis.py`. Bestehende Provider normalisieren in diese Module; sie lernen keine Effekte.

Die folgenden Dict-Verträge sind feste Schnittstellen, nicht beliebige Durchreichbehälter. `context_models/contracts.py` prüft erlaubte Schlüssel, echte Typen, endliche Zahlen und zeitzonenbehaftete ISO-Zeitpunkte.

- **Event:** `event_key`, `sport`, `competition`, `format`, `home_id`, `away_id`, `scheduled_start`, `schedule_revision`, `status`. Native IDs mit Quellennamensraum; `status` ist `scheduled`, `cancelled`, `started` oder `completed`.
- **FeatureVector:** `version`, `event_key`, `cutoff`, `values` (Name zu Zahl oder `None`), `states` (Name zu Datenstatus), `refs` (Name zu Beobachtungshashes), `coverage` (versionierter Abdeckungsfall), `reference_hash`.
- **BaseDistribution:** `version`, `model_hash`, `event_key`, `cutoff`, `family`, `params`, `markets`, `history_refs`, `reference_weights`. `markets` enthält marktvertragstreue Wahrscheinlichkeiten; `reference_weights` dokumentiert die wirklich für die Basis verwendeten historischen Gewichte getrennt nach Team und Modellkomponente (Angriff/Abwehr, Heim-/Auswärtsanteil), nicht ein erfundenes gemeinsames Durchschnittsfenster. Jeder Komponentenwert enthält native Eventreferenzen und normalisierte Gewichte.
- **EffectArtifact:** `schema=1`, `sport`, `family`, `feature_version`, `feature_names`, `heads`, `preprocessing_artifacts`, `joint_calibration`, `training_end`, `training_refs_hash`, `population`, `coverage`, `model_variant`. `heads` enthält benannte B2-Fits mit `link`, `scale`, `coef`, `alpha`, `n_rows`: `home/away` für Tor-/Hockeyraten, `hold_a/hold_b` für Tennisaufschlag, `winner` für binäre Sieger, `margin` für Basketball. Listen sind JSON-Zahlenlisten, keine NumPy-Objekte. `preprocessing_artifacts` bindet die Hashes trainierter Teilnahme-/Referenzmodelle; erste gemeinsame Parameterkalibrierung ist explizit `{"kind":"identity"}`. Kein `approved=True` im Modellpayload; die Freigabe liegt in einem separaten D2-Abnahmeartefakt und muss Hash/Population treffen.
- **ContextResult:** `event_key`, `base_hash`, `effect_hash`, `role`, `factor_roles`, `factor_states`, `feature_refs`, `base_params`, `comparison_params`, `used_params`, `base_markets`, `comparison_markets`, `used_markets`, `delta_pp`, `limitations`. Experimentelle Vergleichsrechnung ist nicht automatisch die verwendete Zahl. Die Kartenprojektion ergänzt `selected_market`, ohne den gespeicherten Eventstand zu ändern.
- **TrainingRow:** `event_key`, `decision_at`, `result_observed_at`, `block`, `population`, `coverage`, `feature_names`, `x`, `offset`, `target`, `trials`, `base_hash`, `feature_refs`, `evidence_class`. Alle Zeilen eines Events bleiben im selben Split; `target` ist nur für Training/Auswertung, niemals ein Prognosemerkmal.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

## Task 8: B4 — Fußballquellen, Besetzungsreferenz und fragliche Einsätze

**Files:** Create `context_sources/football.py`, `tests/test_football_context_sources.py`, `tests/test_football_context_features.py`; create `context_models/football.py`; modify `challenge_15k.py` provider helpers and `challenge_engine.py` base provenance.

**Interfaces:**

- `normalize_football_context(event: dict, *, injuries: list[dict], lineups: list[dict], appearances: list[dict], observed_at: datetime) -> tuple[dict, ...]`: B1 records.
- `roster_delta(reference_minutes: dict[str, float], expected_minutes: dict[str, float]) -> dict[str, float]`: expected-minus-reference, each divided by 90; inputs require complete aligned identities.
- `football_features(event: dict, observations: tuple[dict, ...], base: dict, *, cutoff: datetime, preprocessing: dict | None = None) -> dict`: FeatureVector. Reference exposure uses the same historical events/weights as `base.reference_weights`. `preprocessing` maps artifact hashes to already verified payloads; no hidden I/O inside feature generation.
- `expected_roster(appearances: tuple[dict, ...], availability: tuple[dict, ...], *, cutoff: datetime, participation: dict | None = None) -> dict`: `central_minutes` (mapping or `None`), `scenarios` (named minute mappings), `coverage`, `refs`. No participation artifact means no probabilistic mixture for doubtful players.
- Normalized appearance payload: `player_id`, `team_id`, `fixture_id`, `minutes`, `started`, `role`, `result_observed_at`, `event_start`, `event_end`, `performance`; nullable fields remain null. No current season aggregate may masquerade as an old match row.

- [ ] **RED – long-term absence already inside the base must not be deducted again.**

```python
from context_models.football import roster_delta

def test_reference_roster_prevents_double_absence_deduction():
    reference = {"starter": 0., "replacement": 90.}
    same = {"starter": 0., "replacement": 90.}
    returned = {"starter": 60., "replacement": 30.}
    assert roster_delta(reference, same) == {"starter": 0., "replacement": 0.}
    assert roster_delta(reference, returned) == {"starter": 2/3, "replacement": -2/3}
```

- [ ] Run football-context feature tests with `b4-red`; expected missing function.
- [ ] **Probe allowed real data before writing provider field assumptions.** Reuse `ChallengeDataProvider` injuries/lineups and football quota helpers. Limit probe to one future fixture and at most two completed fixtures plus existing caches; count every request in the existing budget. Inspect official current endpoint documentation for player appearances and compare native response IDs, minutes/start/role fields, status, timestamps and response completeness. Save sanitized structural samples under `tests/fixtures/context/football/` and aggregate coverage in `docs/audits/2026-09-07-kontext-daten.md`. Never save credentials, request headers or personal account data. If historical minutes are not available, mark that source unavailable and continue independent B6 work; do not manufacture samples and claim live coverage.
- [ ] **Implement source normalization/identity joins.** Split confirmed absent, suspended, doubtful and available; use fixture/team/player IDs. A complete verified lineup overrides uncertain expected participation, not immutable prior observations. Expected minutes for a confirmed starter still come from historical starter minutes; starting does not imply 90 minutes. Missing player minutes/performance remain unknown. Ignore any free `material_impact` field for estimating coefficients.

```python
def roster_delta(reference_minutes, expected_minutes):
    if set(reference_minutes) != set(expected_minutes):
        raise ValueError("incomplete roster identity coverage")
    return {player: (expected_minutes[player] - reference_minutes[player]) / 90.
            for player in sorted(reference_minutes)}
```

- [ ] **Implement expected participation and reference features.** Reference minutes are the component-specific weighted average appearances over exactly the baseline's contributing matches, with existing recency/home-away weighting exposed in base provenance. If attack/defence components have different reference exposure, emit separately named reference-difference columns for each. A 90-minute goal family needs regulation exposure; total minutes from an extra-time fixture cannot be silently treated as regulation minutes or clamped without period/substitution evidence. Total observed minutes may still enter the separate workload timeline. Unknown regulation exposure is a coverage gap. Confirmed out/suspended means expected zero; confirmed lineup uses starter/bench history. Unknown completeness is not healthy. Probabilities for doubtful statuses require a separately trained participation model from earlier announced-status→actual-appearance pairs, fitted inside D1 windows using B2 binomial loss. Without it, produce named present/absent scenario vectors and no central mixture. Global squad coverage remains distinct from individually confirmed facts.
- [ ] Player coefficients and role/team shrinkage are trained, not assigned by names. Add opponent/base strength and competition identifiers already known at cutoff to the fitting design. Fixed effect regularization and pooled role terms are explicit feature groups; unobserved players get only a separately tested pooled variant, not fabricated individual weight. Permanently absent players with no role variation cannot get an identified individual effect.
- [ ] Add source tests using real sanitized shapes, native collisions, corrected lineup, exact roster reference, replacement, questionable/no-probability, known attendance model, future season totals rejection and confirmed-absence/partial-list coverage. Test `roster_delta` numeric validation: finite 0–match-duration minutes, bool rejected.
- [ ] Run B4 tests and `tests/test_context_coverage.py` with `b4-green`; commit exact source/model/provider/provenance/test/sample/report files with message `feat: derive football availability against the actual base roster`.

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

#### Kontextkern, Fußballausfälle und Tennisbelastung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tatsächliche Spieler- und Belastungsmerkmale erzeugen numerisch nachvollziehbare Vergleichsprognosen; nur empirisch freigegebene Varianten verändern die Nutzerprognose.

**Architecture:** Append-only Beobachtungen liefern versionierte Merkmale zum Entscheidungszeitpunkt. Regularisierte Modelle lernen Änderungen gegenüber eingefrorenen Basisparametern. Ein gemeinsamer Snapshot speichert Basis, experimentelle Vergleichsrechnung und tatsächlich verwendete Verteilung getrennt.

**Tech Stack:** Python, SQLite, NumPy/SciPy, bestehende Fußballverteilungen und Tennissimulator, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), insbesondere Abschnitte 4–7, 9 und 11.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Quote verändert weder Modell noch Reihenfolge; keine neue Marktverbotsliste.
- `available/missing/stale/conflicting/not_applicable` und `not_applied/experimental/applied` bleiben getrennt.
- Keine rückdatierten Beobachtungen, kein frei erfundener Star- oder Fünfsatzabschlag.
- Spielerreferenz ist die tatsächlich in der Basis enthaltene Besetzung; kein fiktiv immer gesunder Kader.
- Neue Torwirkung wird nicht ungeprüft auf Ecken, Karten oder Halbzeit übertragen.
- Die B-Aufgaben liefern implementierte Vergleichsmodelle. Produktive Anwendung erfordert D1/D2; ein leeres `applied=False`-Gerüst ist keine abgeschlossene Integration.

## Dateigrenzen und gemeinsame Datenverträge

Neue kleine Module: `context_observations.py`, `context_snapshots.py`, `context_models/__init__.py`, `context_models/contracts.py`, `context_models/offset.py`, `context_models/football.py`, `context_models/tennis.py`, `context_sources/__init__.py`, `context_sources/football.py`, `context_sources/tennis.py`. Bestehende Provider normalisieren in diese Module; sie lernen keine Effekte.

Die folgenden Dict-Verträge sind feste Schnittstellen, nicht beliebige Durchreichbehälter. `context_models/contracts.py` prüft erlaubte Schlüssel, echte Typen, endliche Zahlen und zeitzonenbehaftete ISO-Zeitpunkte.

- **Event:** `event_key`, `sport`, `competition`, `format`, `home_id`, `away_id`, `scheduled_start`, `schedule_revision`, `status`. Native IDs mit Quellennamensraum; `status` ist `scheduled`, `cancelled`, `started` oder `completed`.
- **FeatureVector:** `version`, `event_key`, `cutoff`, `values` (Name zu Zahl oder `None`), `states` (Name zu Datenstatus), `refs` (Name zu Beobachtungshashes), `coverage` (versionierter Abdeckungsfall), `reference_hash`.
- **BaseDistribution:** `version`, `model_hash`, `event_key`, `cutoff`, `family`, `params`, `markets`, `history_refs`, `reference_weights`. `markets` enthält marktvertragstreue Wahrscheinlichkeiten; `reference_weights` dokumentiert die wirklich für die Basis verwendeten historischen Gewichte getrennt nach Team und Modellkomponente (Angriff/Abwehr, Heim-/Auswärtsanteil), nicht ein erfundenes gemeinsames Durchschnittsfenster. Jeder Komponentenwert enthält native Eventreferenzen und normalisierte Gewichte.
- **EffectArtifact:** `schema=1`, `sport`, `family`, `feature_version`, `feature_names`, `heads`, `preprocessing_artifacts`, `joint_calibration`, `training_end`, `training_refs_hash`, `population`, `coverage`, `model_variant`. `heads` enthält benannte B2-Fits mit `link`, `scale`, `coef`, `alpha`, `n_rows`: `home/away` für Tor-/Hockeyraten, `hold_a/hold_b` für Tennisaufschlag, `winner` für binäre Sieger, `margin` für Basketball. Listen sind JSON-Zahlenlisten, keine NumPy-Objekte. `preprocessing_artifacts` bindet die Hashes trainierter Teilnahme-/Referenzmodelle; erste gemeinsame Parameterkalibrierung ist explizit `{"kind":"identity"}`. Kein `approved=True` im Modellpayload; die Freigabe liegt in einem separaten D2-Abnahmeartefakt und muss Hash/Population treffen.
- **ContextResult:** `event_key`, `base_hash`, `effect_hash`, `role`, `factor_roles`, `factor_states`, `feature_refs`, `base_params`, `comparison_params`, `used_params`, `base_markets`, `comparison_markets`, `used_markets`, `delta_pp`, `limitations`. Experimentelle Vergleichsrechnung ist nicht automatisch die verwendete Zahl. Die Kartenprojektion ergänzt `selected_market`, ohne den gespeicherten Eventstand zu ändern.
- **TrainingRow:** `event_key`, `decision_at`, `result_observed_at`, `block`, `population`, `coverage`, `feature_names`, `x`, `offset`, `target`, `trials`, `base_hash`, `feature_refs`, `evidence_class`. Alle Zeilen eines Events bleiben im selben Split; `target` ist nur für Training/Auswertung, niemals ein Prognosemerkmal.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

## Task 9: B5 — Geschätzte Spielerwirkung auf eine gemeinsame Torverteilung

**Files:** Extend `context_models/football.py`, `challenge_engine.py`; create `tests/test_football_context_model.py`.

**Interfaces:**

- `apply_football_effect(base: dict, features: dict, artifact: dict) -> dict`: comparison BaseDistribution, family `football:goals:90min` only in this task.
- `build_football_training_rows(observations: tuple[dict, ...], baselines: tuple[dict, ...], *, training_cutoff: datetime) -> list[dict]`: TrainingRows; fit-time history and per-event feature cutoffs are separate.
- `football_factor_comparisons(base: dict, features: dict, artifact: dict) -> dict[str, dict]`: full vs leave-one-factor-group-out recomputations, explicitly non-additive if interactions exist.
- Existing `score_matrix` and `market_probability` remain authoritative goal-market contract functions. Expose pre-market-calibration base rates plus history references without changing the legacy branch.

- [ ] **RED – learned rate movement must change all related markets coherently.**

```python
import numpy as np
from context_models.offset import fit_offset, offset_delta, adjust_parameters
from challenge_engine import score_matrix

def test_fitted_absence_changes_rate_not_individual_market_percentages():
    x = np.array([[0.], [1.]] * 100)
    model = fit_offset(x, np.full(200, np.log(2.)), np.array([2., 1.] * 100),
                       link="log_rate", alpha=.1)
    delta = offset_delta(model, np.array([[1.]]))
    rate = float(adjust_parameters(np.array([2.]), delta, link="log_rate")[0])
    before = score_matrix(2., 1.)
    after = score_matrix(rate, 1.)
    p_before = sum(p for (h, a), p in before.items() if h > 0)
    p_after = sum(p for (h, a), p in after.items() if h > 0)
    assert rate < 2. and p_after < p_before
    assert abs(sum(after.values()) - 1.) < 1e-8
```

- [ ] Run with `b5-red`; dependent B2 alone may make this numerical test pass, so also add an integration assertion on `apply_football_effect` before implementation that checks returned home/away rates, markets, `model_hash`, family and the unchanged corner/card base entries. Require this integration test to fail on the missing B5 function.
- [ ] **Implement two-target rate design.** `artifact["heads"]` contains two B2 fitted heads, `home` and `away`, using aligned feature names; home-attacking/away-defending and reciprocal groups are separate. Apply log deltas to original positive lambdas. Rebuild exactly one score matrix and derive winner/draw, totals, BTTS and team goals from it using existing `MarketSpec` contracts.

```python
new_home = base["params"]["home_lambda"] * math.exp(home_delta)
new_away = base["params"]["away_lambda"] * math.exp(away_delta)
matrix = score_matrix(new_home, new_away)
markets = {spec.key: market_probability(matrix, spec) for spec in goal_specs}
```

`goal_specs` is the existing catalog filtered by explicit 90-minute goal-family contract, not string guesses. New family model hash binds both heads and distribution-calibration variant. Do **not** pass the resulting probabilities through old independent `MarketCalibration` curves. Corner/card/half-time branches retain their unchanged legacy distribution/version.
- [ ] **Implement training rows.** For each causal baseline event, derive roster deltas from observations available before its decision, then attach actual home/away goals only when result observed before the outer training cutoff. Emit two heads grouped under one event. Fit role/player shrinkage in the training window; retain feature/row references. Compare base and effect using the same unmodified base inputs. If baseline provenance cannot reconstruct its actual roster reference, this row is excluded from that player-effect family and coverage is recorded.
- [ ] **Implement factor explanation and checks.** Zero each group's difference relative to its recorded reference and recompute against the same original base. When interactions are present, keep each counterfactual as a separate contrast; no claim their sum is total. Add property tests for probability sums, complements, monotone nested goal lines, side swap with home advantage accounted for, extreme valid rates and unsupported family rejection. Failed distribution validation keeps basis, never a partially modified set of markets.
- [ ] Integrate B3 internally with a **new** future prediction version, not the immutable 15K contract signature. Do not inherit old validation metrics onto changed probabilities. Runtime user activation stays through D2/D3.
- [ ] Run football-context and challenge/provenance regression tests with `b5-green`; commit exact files with message `feat: calculate coherent football context distributions from learned player effects`.

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

#### Kontextkern, Fußballausfälle und Tennisbelastung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tatsächliche Spieler- und Belastungsmerkmale erzeugen numerisch nachvollziehbare Vergleichsprognosen; nur empirisch freigegebene Varianten verändern die Nutzerprognose.

**Architecture:** Append-only Beobachtungen liefern versionierte Merkmale zum Entscheidungszeitpunkt. Regularisierte Modelle lernen Änderungen gegenüber eingefrorenen Basisparametern. Ein gemeinsamer Snapshot speichert Basis, experimentelle Vergleichsrechnung und tatsächlich verwendete Verteilung getrennt.

**Tech Stack:** Python, SQLite, NumPy/SciPy, bestehende Fußballverteilungen und Tennissimulator, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), insbesondere Abschnitte 4–7, 9 und 11.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Quote verändert weder Modell noch Reihenfolge; keine neue Marktverbotsliste.
- `available/missing/stale/conflicting/not_applicable` und `not_applied/experimental/applied` bleiben getrennt.
- Keine rückdatierten Beobachtungen, kein frei erfundener Star- oder Fünfsatzabschlag.
- Spielerreferenz ist die tatsächlich in der Basis enthaltene Besetzung; kein fiktiv immer gesunder Kader.
- Neue Torwirkung wird nicht ungeprüft auf Ecken, Karten oder Halbzeit übertragen.
- Die B-Aufgaben liefern implementierte Vergleichsmodelle. Produktive Anwendung erfordert D1/D2; ein leeres `applied=False`-Gerüst ist keine abgeschlossene Integration.

## Dateigrenzen und gemeinsame Datenverträge

Neue kleine Module: `context_observations.py`, `context_snapshots.py`, `context_models/__init__.py`, `context_models/contracts.py`, `context_models/offset.py`, `context_models/football.py`, `context_models/tennis.py`, `context_sources/__init__.py`, `context_sources/football.py`, `context_sources/tennis.py`. Bestehende Provider normalisieren in diese Module; sie lernen keine Effekte.

Die folgenden Dict-Verträge sind feste Schnittstellen, nicht beliebige Durchreichbehälter. `context_models/contracts.py` prüft erlaubte Schlüssel, echte Typen, endliche Zahlen und zeitzonenbehaftete ISO-Zeitpunkte.

- **Event:** `event_key`, `sport`, `competition`, `format`, `home_id`, `away_id`, `scheduled_start`, `schedule_revision`, `status`. Native IDs mit Quellennamensraum; `status` ist `scheduled`, `cancelled`, `started` oder `completed`.
- **FeatureVector:** `version`, `event_key`, `cutoff`, `values` (Name zu Zahl oder `None`), `states` (Name zu Datenstatus), `refs` (Name zu Beobachtungshashes), `coverage` (versionierter Abdeckungsfall), `reference_hash`.
- **BaseDistribution:** `version`, `model_hash`, `event_key`, `cutoff`, `family`, `params`, `markets`, `history_refs`, `reference_weights`. `markets` enthält marktvertragstreue Wahrscheinlichkeiten; `reference_weights` dokumentiert die wirklich für die Basis verwendeten historischen Gewichte getrennt nach Team und Modellkomponente (Angriff/Abwehr, Heim-/Auswärtsanteil), nicht ein erfundenes gemeinsames Durchschnittsfenster. Jeder Komponentenwert enthält native Eventreferenzen und normalisierte Gewichte.
- **EffectArtifact:** `schema=1`, `sport`, `family`, `feature_version`, `feature_names`, `heads`, `preprocessing_artifacts`, `joint_calibration`, `training_end`, `training_refs_hash`, `population`, `coverage`, `model_variant`. `heads` enthält benannte B2-Fits mit `link`, `scale`, `coef`, `alpha`, `n_rows`: `home/away` für Tor-/Hockeyraten, `hold_a/hold_b` für Tennisaufschlag, `winner` für binäre Sieger, `margin` für Basketball. Listen sind JSON-Zahlenlisten, keine NumPy-Objekte. `preprocessing_artifacts` bindet die Hashes trainierter Teilnahme-/Referenzmodelle; erste gemeinsame Parameterkalibrierung ist explizit `{"kind":"identity"}`. Kein `approved=True` im Modellpayload; die Freigabe liegt in einem separaten D2-Abnahmeartefakt und muss Hash/Population treffen.
- **ContextResult:** `event_key`, `base_hash`, `effect_hash`, `role`, `factor_roles`, `factor_states`, `feature_refs`, `base_params`, `comparison_params`, `used_params`, `base_markets`, `comparison_markets`, `used_markets`, `delta_pp`, `limitations`. Experimentelle Vergleichsrechnung ist nicht automatisch die verwendete Zahl. Die Kartenprojektion ergänzt `selected_market`, ohne den gespeicherten Eventstand zu ändern.
- **TrainingRow:** `event_key`, `decision_at`, `result_observed_at`, `block`, `population`, `coverage`, `feature_names`, `x`, `offset`, `target`, `trials`, `base_hash`, `feature_refs`, `evidence_class`. Alle Zeilen eines Events bleiben im selben Split; `target` ist nur für Training/Auswertung, niemals ein Prognosemerkmal.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

## Task 10: B6 — Tatsächliche Tennisbelastung und zeitlich belegte Erholung

**Files:** Create `context_sources/tennis.py`, `context_models/tennis.py`, `tests/test_tennis_context_features.py`; extend `tennis/workload.py` and its existing tests.

**Interfaces:**

- `normalize_tennis_workload(rows: tuple[dict, ...], *, observed_at: datetime) -> tuple[dict, ...]`: B1 records from real completed-history/shadow sources.
- `recovery_bounds(*, next_start: datetime, result_observed_at: datetime, ended_at: datetime | None) -> dict` gives `minimum_hours`, `exact_hours`.
- `tennis_features(event: dict, observations: tuple[dict, ...], base: dict, *, cutoff: datetime) -> dict`: FeatureVector with signed A-minus-B load and separate coverage flags.

- [ ] **RED – observed result gives only a lower recovery bound.**

```python
from datetime import datetime, timezone
from context_models.tennis import recovery_bounds

def test_result_observation_is_not_match_end():
    next_start = datetime(2026, 9, 7, 18, tzinfo=timezone.utc)
    observed = datetime(2026, 9, 6, 18, tzinfo=timezone.utc)
    result = recovery_bounds(next_start=next_start, result_observed_at=observed, ended_at=None)
    assert result == {"minimum_hours": 24., "exact_hours": None}
```

- [ ] Run with `b6-red`; expected missing function.
- [ ] **Probe existing tennis response/history fields.** Reuse current fixture and result source and `tennis/workload.py` provenance. Probe no more than two known completed matches. Record whether sets, games, duration, real start/end, retirement side and availability are actually supplied. Preserve native source/event/player/tour IDs. Do not infer time from `tourney_date`, winner label or scrape an unapproved health source. Capture sanitized response-shape fixtures and the data report.
- [ ] **Implement timestamps and coverage.**

```python
minimum = (next_start - result_observed_at).total_seconds() / 3600.
exact = None if ended_at is None else (next_start - ended_at).total_seconds() / 3600.
if minimum < 0 or (ended_at is not None and ended_at > result_observed_at):
    raise ValueError("inconsistent completed-match chronology")
return {"minimum_hours": minimum, "exact_hours": exact}
```

This is a bound on the interval to the **scheduled next start**, not a measured future physiological state. Validate aware times and previous match start ≤ end ≤ observation ≤ decision < next start. If actual end is unknown, use bound and an explicit bound-kind feature; never feed it into a coefficient trained on exact rest without a tested coverage variant.
- [ ] Build 1-, 3- and 7-day observed sets/games/minutes totals with independent completeness flags; windows are declared feature definitions, and usefulness is learned/validated. Prior future-scheduled fixtures never count. Retirement contributes only observed completed workload, with incomplete-match flag; walkover supplies no fictitious games/minutes. Absence of duration stays null. Deduplicate native events across feeds, do not sum both. Surface/indoor are already base features; only learned interactions with load may be new columns.
- [ ] Verified availability/return reports use B1 records. Retirement alone provides no diagnosis and cannot identify the injured side unless the source explicitly does. Actual travel is a separate evidenced input; tournament location difference alone is not travel duration/jetlag. No report leaves those factors missing, not available.
- [ ] Add tests for five-set vs three-set actual counts, incomplete duration, exact vs bounded recovery, both participants swapped, near-midnight/UTC, duplicate sources, late correction, WTA namespace, walkover, retirement, future schedule, conflicting timing and fake injury inference.
- [ ] Run B6/workload/pending-refresh tests with `b6-green`; commit exact files with message `feat: derive causal tennis load and recovery features with explicit coverage`.

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

#### Kontextkern, Fußballausfälle und Tennisbelastung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tatsächliche Spieler- und Belastungsmerkmale erzeugen numerisch nachvollziehbare Vergleichsprognosen; nur empirisch freigegebene Varianten verändern die Nutzerprognose.

**Architecture:** Append-only Beobachtungen liefern versionierte Merkmale zum Entscheidungszeitpunkt. Regularisierte Modelle lernen Änderungen gegenüber eingefrorenen Basisparametern. Ein gemeinsamer Snapshot speichert Basis, experimentelle Vergleichsrechnung und tatsächlich verwendete Verteilung getrennt.

**Tech Stack:** Python, SQLite, NumPy/SciPy, bestehende Fußballverteilungen und Tennissimulator, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), insbesondere Abschnitte 4–7, 9 und 11.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Quote verändert weder Modell noch Reihenfolge; keine neue Marktverbotsliste.
- `available/missing/stale/conflicting/not_applicable` und `not_applied/experimental/applied` bleiben getrennt.
- Keine rückdatierten Beobachtungen, kein frei erfundener Star- oder Fünfsatzabschlag.
- Spielerreferenz ist die tatsächlich in der Basis enthaltene Besetzung; kein fiktiv immer gesunder Kader.
- Neue Torwirkung wird nicht ungeprüft auf Ecken, Karten oder Halbzeit übertragen.
- Die B-Aufgaben liefern implementierte Vergleichsmodelle. Produktive Anwendung erfordert D1/D2; ein leeres `applied=False`-Gerüst ist keine abgeschlossene Integration.

## Dateigrenzen und gemeinsame Datenverträge

Neue kleine Module: `context_observations.py`, `context_snapshots.py`, `context_models/__init__.py`, `context_models/contracts.py`, `context_models/offset.py`, `context_models/football.py`, `context_models/tennis.py`, `context_sources/__init__.py`, `context_sources/football.py`, `context_sources/tennis.py`. Bestehende Provider normalisieren in diese Module; sie lernen keine Effekte.

Die folgenden Dict-Verträge sind feste Schnittstellen, nicht beliebige Durchreichbehälter. `context_models/contracts.py` prüft erlaubte Schlüssel, echte Typen, endliche Zahlen und zeitzonenbehaftete ISO-Zeitpunkte.

- **Event:** `event_key`, `sport`, `competition`, `format`, `home_id`, `away_id`, `scheduled_start`, `schedule_revision`, `status`. Native IDs mit Quellennamensraum; `status` ist `scheduled`, `cancelled`, `started` oder `completed`.
- **FeatureVector:** `version`, `event_key`, `cutoff`, `values` (Name zu Zahl oder `None`), `states` (Name zu Datenstatus), `refs` (Name zu Beobachtungshashes), `coverage` (versionierter Abdeckungsfall), `reference_hash`.
- **BaseDistribution:** `version`, `model_hash`, `event_key`, `cutoff`, `family`, `params`, `markets`, `history_refs`, `reference_weights`. `markets` enthält marktvertragstreue Wahrscheinlichkeiten; `reference_weights` dokumentiert die wirklich für die Basis verwendeten historischen Gewichte getrennt nach Team und Modellkomponente (Angriff/Abwehr, Heim-/Auswärtsanteil), nicht ein erfundenes gemeinsames Durchschnittsfenster. Jeder Komponentenwert enthält native Eventreferenzen und normalisierte Gewichte.
- **EffectArtifact:** `schema=1`, `sport`, `family`, `feature_version`, `feature_names`, `heads`, `preprocessing_artifacts`, `joint_calibration`, `training_end`, `training_refs_hash`, `population`, `coverage`, `model_variant`. `heads` enthält benannte B2-Fits mit `link`, `scale`, `coef`, `alpha`, `n_rows`: `home/away` für Tor-/Hockeyraten, `hold_a/hold_b` für Tennisaufschlag, `winner` für binäre Sieger, `margin` für Basketball. Listen sind JSON-Zahlenlisten, keine NumPy-Objekte. `preprocessing_artifacts` bindet die Hashes trainierter Teilnahme-/Referenzmodelle; erste gemeinsame Parameterkalibrierung ist explizit `{"kind":"identity"}`. Kein `approved=True` im Modellpayload; die Freigabe liegt in einem separaten D2-Abnahmeartefakt und muss Hash/Population treffen.
- **ContextResult:** `event_key`, `base_hash`, `effect_hash`, `role`, `factor_roles`, `factor_states`, `feature_refs`, `base_params`, `comparison_params`, `used_params`, `base_markets`, `comparison_markets`, `used_markets`, `delta_pp`, `limitations`. Experimentelle Vergleichsrechnung ist nicht automatisch die verwendete Zahl. Die Kartenprojektion ergänzt `selected_market`, ohne den gespeicherten Eventstand zu ändern.
- **TrainingRow:** `event_key`, `decision_at`, `result_observed_at`, `block`, `population`, `coverage`, `feature_names`, `x`, `offset`, `target`, `trials`, `base_hash`, `feature_refs`, `evidence_class`. Alle Zeilen eines Events bleiben im selben Split; `target` ist nur für Training/Auswertung, niemals ein Prognosemerkmal.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

## Task 11: B7 — Tenniswirkung auf identifizierbarer Modellstufe

**Files:** Extend `context_models/tennis.py`, `tennis/predict.py`; create `tests/test_tennis_context_model.py`.

**Interfaces:**

- `apply_tennis_effect(base: dict, features: dict, artifact: dict) -> dict`: comparison BaseDistribution for `tennis:serve` or `tennis:winner`, never silently crossing families.
- `build_tennis_training_rows(observations: tuple[dict, ...], baselines: tuple[dict, ...], *, training_cutoff: datetime) -> list[dict]`.
- `tennis_factor_comparisons(base: dict, features: dict, artifact: dict) -> dict[str, dict]`.

- [ ] **RED – Elo-only cannot acquire invented serve/side markets.**

```python
import pytest
from context_models.tennis import apply_tennis_effect

def test_elo_only_rejects_serve_effect_without_hold_parameters():
    base = {"family": "tennis:winner", "params": {"p_a": .6},
            "markets": {"winner_a": .6, "winner_b": .4}}
    features = {"version": "tennis-load-v1", "values": {}, "coverage": "winner-only"}
    artifact = {"family": "tennis:serve", "feature_version": "tennis-load-v1"}
    with pytest.raises(ValueError, match="family"):
        apply_tennis_effect(base, features, artifact)
```

- [ ] Run with `b7-red`; expected missing integration.
- [ ] **Implement winner-only variant.** Canonical A/B orientation plus a signed, antisymmetric feature vector. B2 logit offset on baseline winner probability; swapping both players and all signed features yields the complementary probability. A source-qualified availability flag may enter its own trained variant. Winner-only output contains exactly winner A/B; existing side-market bases stay separately labelled, not falsely adjusted.

```python
delta = float(offset_delta(artifact["heads"]["winner"], x)[0])
p_a = float(adjust_parameters(np.array([base["params"]["p_a"]]),
                             np.array([delta]), link="logit")[0])
markets = {"winner_a": p_a, "winner_b": 1. - p_a}
```

- [ ] **Implement serve-identified variant.** Fit `artifact["heads"]["hold_a"]` and `artifact["heads"]["hold_b"]` changes from actual successes/trials with B2 binomial objective, not only winner outcomes. Apply to both hold logits, then call existing `tennis.simulator.simulate_match(p_hold_a, p_hold_b, best_of)` with actual best-of and existing tiebreak rules. Use the returned distribution for winner, sets, games and related supported markets. No subsequent independent winner Platt correction or winner-only Elo blend may break coherence: this first new variant has explicit identity parameter calibration and must pass its own D2 comparison/calibration checks; keep legacy blend in the legacy branch. The simulator's `hold_to_point_prob` already provides its inversion; do not add a second approximation. Verify clipping/rounding in the existing simulator does not hide an invalid new parameter or unsupported rule format.
- [ ] **Implement strict activation identity.** Model variant binds tour, surface/environment coverage, best-of, actual duration/rest coverage, serve sufficiency and training provenance. Artifact schema rejects inherited calibration metrics from old probability versions. D1 trains/fits every scaler/interaction on earlier data; sparse/unsupported populations remain base, not auto-transferred from ATP Hard to WTA/Clay.
- [ ] Add synthetic fitted-load test with observed successes/trials and expected nonzero change, counterpart/side-swap tests, sum/monotonicity checks across sets/games, exact/bound-rest variant mismatch, zero learned effect, double adjustment, surface no-double-count, no injury-by-retirement and quote-invariance tests. The artificial fatigue signal tests code, not real tennis validity.
- [ ] Wire internal comparison through B3, preserving original predictions and available baseline side markets. Test `p_a_cal`, `p_b_cal` and public market summary all reference the same **used** version and no experimental number reaches 15K fields.
- [ ] Run B7, tennis predictor/side-bet/revision/workflow regression tests with `b7-green`; commit exact files with message `feat: compute learned tennis workload effects at the supported model level`.
- [ ] Execute D1/D2 for the first data-supported football/tennis families; publish software/data/empirical status separately before moving to broader C work. No synthetic fixture can satisfy the 200-real-event activation requirement.

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

#### Kontextkern, Fußballausfälle und Tennisbelastung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tatsächliche Spieler- und Belastungsmerkmale erzeugen numerisch nachvollziehbare Vergleichsprognosen; nur empirisch freigegebene Varianten verändern die Nutzerprognose.

**Architecture:** Append-only Beobachtungen liefern versionierte Merkmale zum Entscheidungszeitpunkt. Regularisierte Modelle lernen Änderungen gegenüber eingefrorenen Basisparametern. Ein gemeinsamer Snapshot speichert Basis, experimentelle Vergleichsrechnung und tatsächlich verwendete Verteilung getrennt.

**Tech Stack:** Python, SQLite, NumPy/SciPy, bestehende Fußballverteilungen und Tennissimulator, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), insbesondere Abschnitte 4–7, 9 und 11.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Quote verändert weder Modell noch Reihenfolge; keine neue Marktverbotsliste.
- `available/missing/stale/conflicting/not_applicable` und `not_applied/experimental/applied` bleiben getrennt.
- Keine rückdatierten Beobachtungen, kein frei erfundener Star- oder Fünfsatzabschlag.
- Spielerreferenz ist die tatsächlich in der Basis enthaltene Besetzung; kein fiktiv immer gesunder Kader.
- Neue Torwirkung wird nicht ungeprüft auf Ecken, Karten oder Halbzeit übertragen.
- Die B-Aufgaben liefern implementierte Vergleichsmodelle. Produktive Anwendung erfordert D1/D2; ein leeres `applied=False`-Gerüst ist keine abgeschlossene Integration.

## Dateigrenzen und gemeinsame Datenverträge

Neue kleine Module: `context_observations.py`, `context_snapshots.py`, `context_models/__init__.py`, `context_models/contracts.py`, `context_models/offset.py`, `context_models/football.py`, `context_models/tennis.py`, `context_sources/__init__.py`, `context_sources/football.py`, `context_sources/tennis.py`. Bestehende Provider normalisieren in diese Module; sie lernen keine Effekte.

Die folgenden Dict-Verträge sind feste Schnittstellen, nicht beliebige Durchreichbehälter. `context_models/contracts.py` prüft erlaubte Schlüssel, echte Typen, endliche Zahlen und zeitzonenbehaftete ISO-Zeitpunkte.

- **Event:** `event_key`, `sport`, `competition`, `format`, `home_id`, `away_id`, `scheduled_start`, `schedule_revision`, `status`. Native IDs mit Quellennamensraum; `status` ist `scheduled`, `cancelled`, `started` oder `completed`.
- **FeatureVector:** `version`, `event_key`, `cutoff`, `values` (Name zu Zahl oder `None`), `states` (Name zu Datenstatus), `refs` (Name zu Beobachtungshashes), `coverage` (versionierter Abdeckungsfall), `reference_hash`.
- **BaseDistribution:** `version`, `model_hash`, `event_key`, `cutoff`, `family`, `params`, `markets`, `history_refs`, `reference_weights`. `markets` enthält marktvertragstreue Wahrscheinlichkeiten; `reference_weights` dokumentiert die wirklich für die Basis verwendeten historischen Gewichte getrennt nach Team und Modellkomponente (Angriff/Abwehr, Heim-/Auswärtsanteil), nicht ein erfundenes gemeinsames Durchschnittsfenster. Jeder Komponentenwert enthält native Eventreferenzen und normalisierte Gewichte.
- **EffectArtifact:** `schema=1`, `sport`, `family`, `feature_version`, `feature_names`, `heads`, `preprocessing_artifacts`, `joint_calibration`, `training_end`, `training_refs_hash`, `population`, `coverage`, `model_variant`. `heads` enthält benannte B2-Fits mit `link`, `scale`, `coef`, `alpha`, `n_rows`: `home/away` für Tor-/Hockeyraten, `hold_a/hold_b` für Tennisaufschlag, `winner` für binäre Sieger, `margin` für Basketball. Listen sind JSON-Zahlenlisten, keine NumPy-Objekte. `preprocessing_artifacts` bindet die Hashes trainierter Teilnahme-/Referenzmodelle; erste gemeinsame Parameterkalibrierung ist explizit `{"kind":"identity"}`. Kein `approved=True` im Modellpayload; die Freigabe liegt in einem separaten D2-Abnahmeartefakt und muss Hash/Population treffen.
- **ContextResult:** `event_key`, `base_hash`, `effect_hash`, `role`, `factor_roles`, `factor_states`, `feature_refs`, `base_params`, `comparison_params`, `used_params`, `base_markets`, `comparison_markets`, `used_markets`, `delta_pp`, `limitations`. Experimentelle Vergleichsrechnung ist nicht automatisch die verwendete Zahl. Die Kartenprojektion ergänzt `selected_market`, ohne den gespeicherten Eventstand zu ändern.
- **TrainingRow:** `event_key`, `decision_at`, `result_observed_at`, `block`, `population`, `coverage`, `feature_names`, `x`, `offset`, `target`, `trials`, `base_hash`, `feature_refs`, `evidence_class`. Alle Zeilen eines Events bleiben im selben Split; `target` ist nur für Training/Auswertung, niemals ein Prognosemerkmal.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

## Task 12: C1 — Fußballwetter und gesamte Spielbelastung

**Files:** Create `context_sources/weather.py`, `tests/test_football_weather_features.py`; extend `context_models/football.py`, `context_sources/football.py`; modify provider integration in `challenge_15k.py`.

**Interfaces:**

- `normalize_weather(event: dict, response: dict, *, observed_at: datetime, source_kind: str) -> tuple[dict, ...]`; source kinds `forecast`, `forecast_archive`, `actual`, `reanalysis` remain distinct.
- `weather_window(*, issued_at: datetime, valid_from: datetime, valid_until: datetime, decision_at: datetime, kickoff: datetime) -> bool`.
- `football_schedule_features(event: dict, completed: tuple[dict, ...], *, cutoff: datetime) -> dict`; de-duplicate by native fixture; returns workload values/states/references to merge into B4 FeatureVector.
- B5 `apply_football_effect` consumes a separately identified artifact containing these groups, not the injury-only approval.

- [ ] **RED – reject forecasts issued after the decision, even when they describe the right kickoff.**

```python
from datetime import datetime, timedelta, timezone
from context_sources.weather import weather_window

def test_later_forecast_is_not_prior_evidence():
    decision = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
    kickoff = decision + timedelta(hours=6)
    assert not weather_window(issued_at=decision + timedelta(hours=1),
                              valid_from=kickoff - timedelta(hours=1),
                              valid_until=kickoff + timedelta(hours=2),
                              decision_at=decision, kickoff=kickoff)
```

- [ ] Run `.codex_test_venv/quality/Scripts/python.exe -m pytest tests/test_football_weather_features.py -q -p no:cacheprovider --basetemp=.pytest_tmp/c1-red`; expected missing function.
- [ ] **Probe weather and schedule coverage.** Use the existing stadium/forecast source for one known fixture. Verify stadium identity, coordinates, unit system, forecast-valid interval, actual fetch time and whether issue time is genuinely present. Existing forecast-valid time is not automatically issue time. Check one team with a domestic plus international completed fixture for a shared native timeline. Add sanitized fixtures and report exact supported fields.
- [ ] Before an archive request, read that archive's official current terms, price/quota and timestamp semantics; record the source links and evidence. The spec's Open-Meteo link is an option to assess, not an authorization for a subscription. If no allowed, verifiably prior forecast archive is available, collect current forecasts prospectively and keep historical weather activation open. Do not convert postevent reanalysis into preevent forecast evidence.
- [ ] **Implement forecast eligibility and normalized features.**

```python
def weather_window(*, issued_at, valid_from, valid_until, decision_at, kickoff):
    times = (issued_at, valid_from, valid_until, decision_at, kickoff)
    if any(t.tzinfo is None or t.utcoffset() is None for t in times):
        raise ValueError("aware weather timestamps required")
    return issued_at <= decision_at < kickoff and valid_from <= kickoff < valid_until
```

Keep measured/forecast temperature, rain/snow, wind and forecast horizon as separate features. Do not hand-code “rain reduces goals 10 %”. Exact venue revision and forecast coverage are required. Unknown roof/venue or forecast horizon gets its own coverage; `not_applicable` only when the factor is genuinely inapplicable, not missing. No aggregation of mixed unit systems.
- [ ] **Implement completed-load timeline.** Join domestic and international fixtures by native team/event IDs; before-cutoff finished games only. Actual player minutes may augment team schedule facts, but inferred full 90 minutes is prohibited when appearances are missing. Report minimum/exact recovery boundaries like B6. Same fixture returned from two league queries counts once; rescheduled/not-played entries do not add load.
- [ ] **Train using B2/B5/D1.** Add weather and load columns as named groups to the log-rate artifact; include optional roster×load interaction as a distinct inner-selected variant. Fit against the original goal base and evaluate injury-only, load-only, weather-only and joint variants. D2 includes **all** tried variants in multiplicity correction. Other goal-family calibration and corner/card separation remain unchanged.
- [ ] Add tests for forecast issue vs valid time, actual/reanalysis rejection in strict forecast cohort, missing location, units, stale/rescheduled weather, domestic/international double count, late result and future match. Verify new numeric coefficients are fitted from rows, never source flags.
- [ ] Run C1/B4/B5 tests with `c1-green`; commit exact files, sanitized samples and coverage report with message `feat: model source-qualified football weather and complete observed load`.

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

#### Wetter und weitere Sportarten Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fußballwetter/-Erholung, Basketball, Eishockey und E-Sport mit belegten kontextspezifischen Daten und trainierbaren Wirkungsmodellen ergänzen.

**Architecture:** Dieselben B1-Beobachtungen, B2-Schätzer und B3-Snapshots werden wiederverwendet. Eigene Sportmodule definieren Merkmale und zulässige Verteilungsparameter; keine Übertragung von Fußballkoeffizienten oder Settlementannahmen auf andere Sportarten.

**Tech Stack:** Bestehende Python-Provider und Historienloader, NumPy/SciPy, SQLite, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), Abschnitte 5–7 und 9–12.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Cricket-Code, Konfiguration, Zugangsdaten und bestehendes Verhalten bleiben unverändert.
- Fehlende Kader-/Verletzungsfeeds bleiben ausgewiesene Datenabhängigkeiten; Ergebnisdaten sind kein Ersatz dafür.
- Bestätigter Spielplan ist keine medizinische Müdigkeitsmessung. Turnierorte allein beweisen weder Reisezeit noch Jetlag.
- Quellenproben verwenden vorhandene Budgets; keine neuen kostenpflichtigen Quellen oder Verträge.
- Eine C-Familie wird erst durch D1/D2 numerisch produktiv. Die Implementierung enthält trotzdem die tatsächliche Schätzung und Verteilungsänderung, keine reine Hinweishülle.

## Dateigrenzen

Neu: `context_sources/weather.py`, `context_sources/basketball.py`, `context_sources/ice_hockey.py`, `context_sources/esports.py`, `context_models/team_sports.py`, `context_models/esports.py`. Ergänzungen: `context_models/football.py`, `sports_prematch.py`, `multi_sport_recommendations.py` und existierende Scanner nur an ihren Quellennormalisierungs-/Provenanzgrenzen. Keine zweite parallele Ergebnisdatenbank.

Alle Merkmals-/Trainings-/Vergleichsrückgaben verwenden die festen B-Verträge. Native Identität, Modellfamilie und Marktregel gehören zur Identität. Die Quellenadapter konsumieren beobachtete Providerantworten plus tatsächliches `observed_at`, geben B1-Records aus und besitzen selbst keine Wirkungskonstanten.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-c-weitere-sportarten.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

## Task 13: C2 — Basketballbesetzung, Ausfälle und Erholung

**Files:** Create `context_sources/basketball.py`, `context_models/team_sports.py`, `tests/test_basketball_context.py`; modify `sports_prematch.py` only at the non-Cricket context hook and base provenance.

**Interfaces:**

- `normalize_basketball_context(event: dict, responses: tuple[dict, ...], *, observed_at: datetime) -> tuple[dict, ...]`.
- `team_sport_features(sport: str, event: dict, observations: tuple[dict, ...], base: dict, *, cutoff: datetime, preprocessing: dict | None = None) -> dict`; supports exactly `basketball`, `ice_hockey`. Preprocessing maps validated participation/reference artifact hashes to payloads; no implicit provider/model load.
- `margin_distribution(mean: float, scale: float) -> dict` returns `expected_margin`, `residual_scale`, `home_win`, `away_win`.
- `apply_team_sport_effect(sport: str, base: dict, features: dict, artifact: dict) -> dict`.
- `build_team_sport_training_rows(sport: str, observations: tuple[dict, ...], baselines: tuple[dict, ...], *, training_cutoff: datetime) -> list[dict]`.

- [ ] **RED – both winner sides use one margin distribution.**

```python
import pytest
from context_models.team_sports import margin_distribution

def test_margin_distribution_is_complementary_and_symmetric():
    home = margin_distribution(3., 12.)
    reverse = margin_distribution(-3., 12.)
    assert home["home_win"] + home["away_win"] == pytest.approx(1.)
    assert home["home_win"] == pytest.approx(reverse["away_win"])
    assert home["home_win"] > .5
```

- [ ] Run new C2 file with `c2-red`; expected missing module.
- [ ] **Probe real player coverage.** Read current basketball scanner/client before using it. With its existing budget, request at most two completed games and one upcoming event. Determine native roster/player IDs, actual boxscore minutes, availability, expected/confirmed lineup and status timestamps. Save sanitized shapes and coverage. If the current provider exposes results only, write an explicit unavailable capability record, preserve baseline and continue hockey/e-sport work; do not imply an injury adapter exists because a key is configured.
- [ ] **Implement roster/load normalization.** Use earlier actual minutes to form baseline reference and expected rotation; distinguish availability from expected playing time. Minutes limits derive from league/game format and actual OT status, not football's 90. Full squad coverage is required for a complete rotation vector; uncertain players use a learned participation variant or explicit scenarios. Rest/repeated days are schedule features; actual travel requires evidenced movement. Preserve native competition/season identities.
- [ ] **Implement margin offset and distribution.**

```python
def margin_distribution(mean, scale):
    if not math.isfinite(mean) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("invalid margin parameters")
    p_home = float(scipy.special.ndtr(mean / scale))
    return {"expected_margin": mean, "residual_scale": scale,
            "home_win": p_home, "away_win": 1. - p_home}
```

Fit B2 `identity` offset to actual score margin on frozen base mean; preserve base residual scale in this first variant. A variance change would require its own jointly trained variant and D2 report. A spread supported by existing settlement contracts derives from the same distribution; do not add total-points markets when only margin is identified. Match the existing `sports_prematch` overtime contract exactly.
- [ ] **Protect Cricket explicitly.** Optional context integration is entered only for supported non-Cricket sports; the existing Cricket fixtures in `tests/test_sports_prematch.py` must preserve their exact inputs, outputs, limitations, model hash and settlement contract. Capture the baseline fixture output before editing the shared module; test original vs context-disabled/default path, not only a mocked hook.
- [ ] Add trained-offset effect, long-term absence/double-count, unknown minutes, back-to-back fact vs individual fatigue label, native-name collision, minutes beyond regulation with actual OT, unsupported total market and temporal-leakage tests. All actual feature columns must exist in a frozen training artifact before they can affect a public value.
- [ ] Run C2 and `tests/test_sports_prematch.py`, `tests/test_completed_sports_history.py` with `c2-green`; commit exact files/samples/report with message `feat: extend basketball margin forecasts with learned roster context`.

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

#### Wetter und weitere Sportarten Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fußballwetter/-Erholung, Basketball, Eishockey und E-Sport mit belegten kontextspezifischen Daten und trainierbaren Wirkungsmodellen ergänzen.

**Architecture:** Dieselben B1-Beobachtungen, B2-Schätzer und B3-Snapshots werden wiederverwendet. Eigene Sportmodule definieren Merkmale und zulässige Verteilungsparameter; keine Übertragung von Fußballkoeffizienten oder Settlementannahmen auf andere Sportarten.

**Tech Stack:** Bestehende Python-Provider und Historienloader, NumPy/SciPy, SQLite, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), Abschnitte 5–7 und 9–12.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Cricket-Code, Konfiguration, Zugangsdaten und bestehendes Verhalten bleiben unverändert.
- Fehlende Kader-/Verletzungsfeeds bleiben ausgewiesene Datenabhängigkeiten; Ergebnisdaten sind kein Ersatz dafür.
- Bestätigter Spielplan ist keine medizinische Müdigkeitsmessung. Turnierorte allein beweisen weder Reisezeit noch Jetlag.
- Quellenproben verwenden vorhandene Budgets; keine neuen kostenpflichtigen Quellen oder Verträge.
- Eine C-Familie wird erst durch D1/D2 numerisch produktiv. Die Implementierung enthält trotzdem die tatsächliche Schätzung und Verteilungsänderung, keine reine Hinweishülle.

## Dateigrenzen

Neu: `context_sources/weather.py`, `context_sources/basketball.py`, `context_sources/ice_hockey.py`, `context_sources/esports.py`, `context_models/team_sports.py`, `context_models/esports.py`. Ergänzungen: `context_models/football.py`, `sports_prematch.py`, `multi_sport_recommendations.py` und existierende Scanner nur an ihren Quellennormalisierungs-/Provenanzgrenzen. Keine zweite parallele Ergebnisdatenbank.

Alle Merkmals-/Trainings-/Vergleichsrückgaben verwenden die festen B-Verträge. Native Identität, Modellfamilie und Marktregel gehören zur Identität. Die Quellenadapter konsumieren beobachtete Providerantworten plus tatsächliches `observed_at`, geben B1-Records aus und besitzen selbst keine Wirkungskonstanten.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-c-weitere-sportarten.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

## Task 14: C3 — Eishockeybesetzung und Torhüter mit korrekter Spielzeit

**Files:** Create `context_sources/ice_hockey.py`, `tests/test_ice_hockey_context.py`; extend `context_models/team_sports.py`, `sports_prematch.py` at hockey hook.

**Interfaces:**

- `normalize_ice_hockey_context(event: dict, responses: tuple[dict, ...], *, observed_at: datetime) -> tuple[dict, ...]`.
- `hockey_distribution(home_rate: float, away_rate: float, overtime_home_rate: float) -> dict` returns regulation home/draw/away and inclusive home/away.
- C2 feature/apply/train signatures support `ice_hockey` with separate family `ice_hockey:regulation_goals` and explicitly versioned OT rule.

- [ ] **RED – probability of an OT win must not turn into a regulation home win.**

```python
import pytest
from context_models.team_sports import hockey_distribution

def test_hockey_separates_regulation_from_inclusive_winner():
    result = hockey_distribution(2.5, 2.5, .6)
    assert sum(result[k] for k in ("home_reg", "draw_reg", "away_reg")) == pytest.approx(1.)
    assert result["home_inclusive"] == pytest.approx(result["home_reg"] + .6 * result["draw_reg"])
    assert result["home_inclusive"] + result["away_inclusive"] == pytest.approx(1.)
```

- [ ] Run with `c3-red`; expected missing distribution.
- [ ] **Probe hockey-specific fields.** Existing client/budget, maximum two completed games plus one upcoming event. Verify skater/goalie IDs, time on ice, starter confirmation and regulation/OT/SO scores. An unconfirmed goalie must not be labelled confirmed from the team's roster. Record unsupported fields and use sanitized fixtures matching real responses.
- [ ] **Implement separate features.** Baseline-reference skater exposures plus distinct goalie terms. Unknown starter: learned participation mixture only when that model is supported; otherwise separate candidate-goalie scenarios and unchanged central base. Repeated games/rest remain observed schedule facts. No basketball-minute or football-goalkeeper coefficient reuse.
- [ ] **Implement regulation-rate offsets and existing OT conversion.**

```python
home_reg = float(scipy.stats.skellam.sf(0, home_rate, away_rate))
draw_reg = float(scipy.stats.skellam.pmf(0, home_rate, away_rate))
away_reg = float(scipy.stats.skellam.cdf(-1, home_rate, away_rate))
home_inclusive = home_reg + draw_reg * overtime_home_rate
```

Validate positive finite rates and OT probability in `[0,1]`; away-inclusive is complement. The existing base OT estimate stays unchanged unless its own context model is separately trained/validated. Scores for training regulation lambdas exclude shootout deciders and OT goals. Use actual source labels; unavailable regulation scores exclude rate-training rows rather than subtracting a guessed goal.
- [ ] Add goalie confirmation/revision, uncertain starter, same player/team IDs across seasons, regulation vs shootout score, complement, fitted rate movement, no goal-history future leakage and C2 Cricket parity regressions.
- [ ] Run C3/C2/shared prematch tests with `c3-green`; commit exact files/samples/report with message `feat: model hockey roster context without crossing settlement boundaries`.

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

#### Wetter und weitere Sportarten Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fußballwetter/-Erholung, Basketball, Eishockey und E-Sport mit belegten kontextspezifischen Daten und trainierbaren Wirkungsmodellen ergänzen.

**Architecture:** Dieselben B1-Beobachtungen, B2-Schätzer und B3-Snapshots werden wiederverwendet. Eigene Sportmodule definieren Merkmale und zulässige Verteilungsparameter; keine Übertragung von Fußballkoeffizienten oder Settlementannahmen auf andere Sportarten.

**Tech Stack:** Bestehende Python-Provider und Historienloader, NumPy/SciPy, SQLite, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), Abschnitte 5–7 und 9–12.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Cricket-Code, Konfiguration, Zugangsdaten und bestehendes Verhalten bleiben unverändert.
- Fehlende Kader-/Verletzungsfeeds bleiben ausgewiesene Datenabhängigkeiten; Ergebnisdaten sind kein Ersatz dafür.
- Bestätigter Spielplan ist keine medizinische Müdigkeitsmessung. Turnierorte allein beweisen weder Reisezeit noch Jetlag.
- Quellenproben verwenden vorhandene Budgets; keine neuen kostenpflichtigen Quellen oder Verträge.
- Eine C-Familie wird erst durch D1/D2 numerisch produktiv. Die Implementierung enthält trotzdem die tatsächliche Schätzung und Verteilungsänderung, keine reine Hinweishülle.

## Dateigrenzen

Neu: `context_sources/weather.py`, `context_sources/basketball.py`, `context_sources/ice_hockey.py`, `context_sources/esports.py`, `context_models/team_sports.py`, `context_models/esports.py`. Ergänzungen: `context_models/football.py`, `sports_prematch.py`, `multi_sport_recommendations.py` und existierende Scanner nur an ihren Quellennormalisierungs-/Provenanzgrenzen. Keine zweite parallele Ergebnisdatenbank.

Alle Merkmals-/Trainings-/Vergleichsrückgaben verwenden die festen B-Verträge. Native Identität, Modellfamilie und Marktregel gehören zur Identität. Die Quellenadapter konsumieren beobachtete Providerantworten plus tatsächliches `observed_at`, geben B1-Records aus und besitzen selbst keine Wirkungskonstanten.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-c-weitere-sportarten.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

## Task 15: C4 — E-Sport-Kader und Serienbelastung

**Files:** Create `context_sources/esports.py`, `context_models/esports.py`, `tests/test_esports_context.py`; modify `multi_sport_recommendations.py` e-sport base/context hook.

**Interfaces:**

- `normalize_esports_context(event: dict, responses: tuple[dict, ...], *, observed_at: datetime) -> tuple[dict, ...]`.
- `esports_features(event: dict, observations: tuple[dict, ...], base: dict, *, cutoff: datetime) -> dict`.
- `series_probability(base_probability: float, signed_delta: float) -> float`.
- `apply_esports_effect(base: dict, features: dict, artifact: dict) -> dict` and `build_esports_training_rows(observations: tuple[dict, ...], baselines: tuple[dict, ...], *, training_cutoff: datetime) -> list[dict]`.

- [ ] **RED – side reversal must complement series probability.**

```python
import pytest
from context_models.esports import series_probability

def test_series_offset_is_antisymmetric():
    p = series_probability(.6, -.3)
    reverse = series_probability(.4, .3)
    assert p + reverse == pytest.approx(1.)
    assert p < .6
```

- [ ] Run with `c4-red`; expected missing module.
- [ ] **Probe existing e-sport source.** Read scanner/native history integration first; bounded sample of one upcoming and two completed series. Verify game title, native series/team/player/stand-in IDs, patch where available, best-of and individual map timestamps/results. Record roster-history availability separately from match-result availability. Never infer a physical illness from a substitute or a late match.
- [ ] **Implement causal roster/load features.** Team-title-season scoped identities, confirmed stand-in vs uncertain lineup, roster reference based on baseline contributing series, observed recent maps/series and exact/bounded rest. Missing patch is explicit coverage, not silently assigned latest patch. Best-of is a model/settlement identity; unknown format cannot inherit a BO3/BO5 variant.
- [ ] **Implement trained antisymmetric series offset.**

```python
def series_probability(base_probability, signed_delta):
    if not 0. < base_probability < 1. or not math.isfinite(signed_delta):
        raise ValueError("invalid series parameters")
    return float(scipy.special.expit(scipy.special.logit(base_probability) + signed_delta))
```

Use B2 binomial fit on one row per completed series, with signed A-minus-B features and baseline Elo probability offset. Series load is a sport-specific observed feature, not a diagnosed fatigue coefficient. First variant emits series winner only. Do not derive exact map scores by silently assuming independent maps; map-dependent models require their own identified distribution and D2 validation, not this winner-only artifact.
- [ ] Add same-spelling players, roster revision, stand-in absence, missing patch, BO mismatch, series/map double-count, future maps, no invented injury and price-invariance tests. Fit on a synthetic roster signal to prove actual coefficient application; D1 uses real series only for effect claims.
- [ ] Run C4 and `tests/test_esports_shadow.py` plus relevant recommendation tests with `c4-green`; commit exact files/samples/report with message `feat: learn source-qualified esports roster and series-load effects`.
- [ ] Execute D1/D2 per data-supported population. Close C only when each sport's real data, software and empirical status is explicitly reported; a missing feed remains an unfinished data dependency.

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

#### Wetter und weitere Sportarten Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fußballwetter/-Erholung, Basketball, Eishockey und E-Sport mit belegten kontextspezifischen Daten und trainierbaren Wirkungsmodellen ergänzen.

**Architecture:** Dieselben B1-Beobachtungen, B2-Schätzer und B3-Snapshots werden wiederverwendet. Eigene Sportmodule definieren Merkmale und zulässige Verteilungsparameter; keine Übertragung von Fußballkoeffizienten oder Settlementannahmen auf andere Sportarten.

**Tech Stack:** Bestehende Python-Provider und Historienloader, NumPy/SciPy, SQLite, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), Abschnitte 5–7 und 9–12.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Cricket-Code, Konfiguration, Zugangsdaten und bestehendes Verhalten bleiben unverändert.
- Fehlende Kader-/Verletzungsfeeds bleiben ausgewiesene Datenabhängigkeiten; Ergebnisdaten sind kein Ersatz dafür.
- Bestätigter Spielplan ist keine medizinische Müdigkeitsmessung. Turnierorte allein beweisen weder Reisezeit noch Jetlag.
- Quellenproben verwenden vorhandene Budgets; keine neuen kostenpflichtigen Quellen oder Verträge.
- Eine C-Familie wird erst durch D1/D2 numerisch produktiv. Die Implementierung enthält trotzdem die tatsächliche Schätzung und Verteilungsänderung, keine reine Hinweishülle.

## Dateigrenzen

Neu: `context_sources/weather.py`, `context_sources/basketball.py`, `context_sources/ice_hockey.py`, `context_sources/esports.py`, `context_models/team_sports.py`, `context_models/esports.py`. Ergänzungen: `context_models/football.py`, `sports_prematch.py`, `multi_sport_recommendations.py` und existierende Scanner nur an ihren Quellennormalisierungs-/Provenanzgrenzen. Keine zweite parallele Ergebnisdatenbank.

Alle Merkmals-/Trainings-/Vergleichsrückgaben verwenden die festen B-Verträge. Native Identität, Modellfamilie und Marktregel gehören zur Identität. Die Quellenadapter konsumieren beobachtete Providerantworten plus tatsächliches `observed_at`, geben B1-Records aus und besitzen selbst keine Wirkungskonstanten.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-c-weitere-sportarten.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

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

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-d-validierung-release.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

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

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-d-validierung-release.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.

## Task 18: D3 — Ein gemeinsamer Workerpfad und verständliche flache Karten

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

## Task 20: D5 — Volle Regression, empirische Entscheidung und belegtes VPS-Release

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
