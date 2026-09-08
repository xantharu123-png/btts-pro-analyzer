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
