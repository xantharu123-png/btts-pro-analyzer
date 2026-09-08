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

Additional controller scope after the full A3 run: the unchanged `tests/test_scan_jobs.py::ScanJobTests::test_progress_extends_inactivity_timeout` failed intermittently with 20-ms sleeps and a 35-ms inactivity limit, including in isolation without A3 tests. A test-only deterministic clock/event repair is authorized in a separate commit after the A3 implementation commit. No ScanJob production code or semantic timeout change. The repaired test must observe a running intermediate state beyond the original overall deadline and still detect an omitted progress-time reset; generous deadlock watchdogs are not the contract timeout. Record the red/isolated evidence, both commit boundaries and a final full-suite result. The review scope includes exactly this test-only file in addition to the original A3/calibration changes.

The four A3 rulings in this workspace's progress.md resolve publication-clock, wrapper, calibration-only and source-clock questions. Read those exact four rulings before these parts. They authorize tennis/backtest.py and narrowly focused cutoff/calibration test changes in addition to the original file list, but not a new data_loader.as_of API. No new provider/network or production authority is implied.


Controller clarification (A2 cutoff ruling, refined by A3 clock ruling): decode_state(payload, *, decision_cutoff: float | None = None) separates structural decoding from decision eligibility. Publication validates against actual publication time, not the earlier logical training cutoff; forecast selection in A4 validates against actual decision as_of. Structural loads of synthetic future artifacts remain possible; omitted cutoff is not a decision-ready assertion. A4 must also validate explicitly supplied/legacy ModelState instances at predict_match's as_of boundary.


Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-a-modelle-tennisrefresh.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
