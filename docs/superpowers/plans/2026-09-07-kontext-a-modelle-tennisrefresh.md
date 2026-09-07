# Modellablage und unabhängiger ATP/WTA-Refresh Implementation Plan

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

## A1: Unveränderliche Artefakte und atomare Slots

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

## A2: Expliziter Tour-State-Codec ohne neue Pickles

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

## A3: Pro Tour bauen und teilweise veröffentlichen

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

## A4: Leser, laufende Prognosen und Betriebsnachweis umstellen

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
