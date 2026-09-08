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
