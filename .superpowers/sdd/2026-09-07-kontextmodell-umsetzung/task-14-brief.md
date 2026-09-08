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
