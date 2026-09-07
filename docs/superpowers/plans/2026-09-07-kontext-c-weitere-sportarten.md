# Wetter und weitere Sportarten Implementation Plan

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

## C1: Fußballwetter und gesamte Spielbelastung

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

## C2: Basketballbesetzung, Ausfälle und Erholung

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

## C3: Eishockeybesetzung und Torhüter mit korrekter Spielzeit

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

## C4: E-Sport-Kader und Serienbelastung

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
