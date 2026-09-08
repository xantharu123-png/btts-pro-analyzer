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
