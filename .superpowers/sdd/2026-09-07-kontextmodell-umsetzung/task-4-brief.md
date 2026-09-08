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

Controller legacy opt-in clarification: `allow_legacy=True` hard-wired in every ordinary reader is not an explicit migration boundary. Normal initial/pending scans default to separated tour artifacts only. `scan_fixtures` and `refresh_pending_predictions` may expose keyword-only `allow_legacy_model=False`; initial CLI may offer the explicit `--allow-legacy-model` operator flag. The unchanged Wettfinder caller does not opt in. A missing tour reports a data/partial error while the other tour continues and prior forecasts remain intact. An explicitly enabled bridge retains exact legacy-byte identity, old coverage and legacy-combined scope, never writes isolated slots or claims a fresh tour build. Add a failing default-no-opt-in regression and a distinct positive explicit-migration regression. This follows spec section8 and the original migration-only clause, not a new price/market restriction. Keep top-level errors compatible with wettfinder_automation.py:3188-3234 as well as per-tour diagnostics.

Controller cancellation-race ruling: A4 may minimally extend `tennis/shadow.py` and focused tests with observed fixture status/native identity/actual aware receipt time, and a guard inside the prediction-write transaction alongside settled/start checks. Existing rows without an observation remain unknown. Older status observations cannot replace newer ones. Wire status observations already obtained by existing source fetches, including cancellations, without additional fetch loops or an invented provider_checked flag. The network-free pending refresh uses only actually stored observations. Reject a cancellation observed during calculation before append, leaving old forecasts/revisions and all money/settlement policy untouched. A preflight-only read is insufficient because of the race; scope beyond this small producer/status/write seam must be raised explicitly.

Controller causal-read ruling: a build timestamp alone does not establish that its manifest was published before a forecast. A4 may minimally extend `model_artifacts.load_manifest` and `tennis.tour_state.load_tour_state` with optional keyword-only `decision_cutoff: datetime | None = None`. An explicit cutoff must be aware UTC-compatible time; verify the selected, hash-checked manifest's `published_at <= decision_cutoff` in the same read transaction, and validate the selected tour wrapper/state against that cutoff. Omitted cutoff remains structural for existing A1/A3 callers. Do not invent a historical manifest-selection service: if the current manifest is later than an explicitly fixed decision cutoff, decline that refresh and preserve the previous forecast. Production captures its actual forecast decision time, never a future kickoff. Add regressions for an earlier-built artifact published after the decision, malformed/naive cutoff, and current eligible manifest, plus existing independent-tour behavior. This adds only the owning registry/loader seam and focused tests, not a registry redesign or source backdating.

Controller file-ownership clarification: A4 also owns the minimal `tennis/model_state.py:load_state` extension required to attach the digest of the exact bytes read through `open_trusted_pickle`. Keep the existing trust/type checks and legacy bytes; do not re-open the path for hashing, synthesize isolated identities, or duplicate the trusted legacy loader in a reader. Add focused legacy identity coverage to the planned reader/model tests. This is the implementation seam required by the explicit legacy-byte identity contract above.

Controller integration note from A3 rulings: the isolated tour slot uses artifact kind `tennis-tour-state`, slot `tennis:ATP` or `tennis:WTA`, with strict payload `{schema:1, training_cutoff:<aware UTC ISO>, state:<exact A2 payload>}`. A3 separates logical training cutoff, actual build completion and actual publication time. A4 must validate both wrapper and typed state plus `training_cutoff <= built_at <= actual decision cutoff`; never use a future scheduled kickoff as proof that a model was already available at an earlier decision. Retain the A3-verified outer artifact hash as identity; do not substitute a re-encoded inner-state hash. This is a dependency clarification, not permission to change legacy bytes or expand migration fallback.

Controller clarification (A2 cutoff ruling): decode_state(payload, *, decision_cutoff: float | None = None) separates structural decoding from decision eligibility. No implicit wallclock check. This task must supply its actual as_of/decision cutoff when selecting or publishing a model and add a regression rejecting built_at later than that cutoff. Structural loads of synthetic future artifacts remain possible; omitted cutoff is not a decision-ready assertion. A4 must also validate explicitly supplied/legacy ModelState instances at predict_match's as_of boundary.


Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-a-modelle-tennisrefresh.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
