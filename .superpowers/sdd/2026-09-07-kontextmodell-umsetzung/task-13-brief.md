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
