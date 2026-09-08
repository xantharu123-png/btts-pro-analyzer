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
