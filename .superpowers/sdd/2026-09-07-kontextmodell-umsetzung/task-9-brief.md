## Task 9: B5 — Geschätzte Spielerwirkung auf eine gemeinsame Torverteilung

**Files:** Extend `context_models/football.py`, `challenge_engine.py`; create `tests/test_football_context_model.py`.

**Interfaces:**

- `apply_football_effect(base: dict, features: dict, artifact: dict) -> dict`: comparison BaseDistribution, family `football:goals:90min` only in this task.
- `build_football_training_rows(observations: tuple[dict, ...], baselines: tuple[dict, ...], *, training_cutoff: datetime) -> list[dict]`: TrainingRows; fit-time history and per-event feature cutoffs are separate.
- `football_factor_comparisons(base: dict, features: dict, artifact: dict) -> dict[str, dict]`: full vs leave-one-factor-group-out recomputations, explicitly non-additive if interactions exist.
- Existing `score_matrix` and `market_probability` remain authoritative goal-market contract functions. Expose pre-market-calibration base rates plus history references without changing the legacy branch.

- [ ] **RED – learned rate movement must change all related markets coherently.**

```python
import numpy as np
from context_models.offset import fit_offset, offset_delta, adjust_parameters
from challenge_engine import score_matrix

def test_fitted_absence_changes_rate_not_individual_market_percentages():
    x = np.array([[0.], [1.]] * 100)
    model = fit_offset(x, np.full(200, np.log(2.)), np.array([2., 1.] * 100),
                       link="log_rate", alpha=.1)
    delta = offset_delta(model, np.array([[1.]]))
    rate = float(adjust_parameters(np.array([2.]), delta, link="log_rate")[0])
    before = score_matrix(2., 1.)
    after = score_matrix(rate, 1.)
    p_before = sum(p for (h, a), p in before.items() if h > 0)
    p_after = sum(p for (h, a), p in after.items() if h > 0)
    assert rate < 2. and p_after < p_before
    assert abs(sum(after.values()) - 1.) < 1e-8
```

- [ ] Run with `b5-red`; dependent B2 alone may make this numerical test pass, so also add an integration assertion on `apply_football_effect` before implementation that checks returned home/away rates, markets, `model_hash`, family and the unchanged corner/card base entries. Require this integration test to fail on the missing B5 function.
- [ ] **Implement two-target rate design.** `artifact["heads"]` contains two B2 fitted heads, `home` and `away`, using aligned feature names; home-attacking/away-defending and reciprocal groups are separate. Apply log deltas to original positive lambdas. Rebuild exactly one score matrix and derive winner/draw, totals, BTTS and team goals from it using existing `MarketSpec` contracts.

```python
new_home = base["params"]["home_lambda"] * math.exp(home_delta)
new_away = base["params"]["away_lambda"] * math.exp(away_delta)
matrix = score_matrix(new_home, new_away)
markets = {spec.key: market_probability(matrix, spec) for spec in goal_specs}
```

`goal_specs` is the existing catalog filtered by explicit 90-minute goal-family contract, not string guesses. New family model hash binds both heads and distribution-calibration variant. Do **not** pass the resulting probabilities through old independent `MarketCalibration` curves. Corner/card/half-time branches retain their unchanged legacy distribution/version.
- [ ] **Implement training rows.** For each causal baseline event, derive roster deltas from observations available before its decision, then attach actual home/away goals only when result observed before the outer training cutoff. Emit two heads grouped under one event. Fit role/player shrinkage in the training window; retain feature/row references. Compare base and effect using the same unmodified base inputs. If baseline provenance cannot reconstruct its actual roster reference, this row is excluded from that player-effect family and coverage is recorded.
- [ ] **Implement factor explanation and checks.** Zero each group's difference relative to its recorded reference and recompute against the same original base. When interactions are present, keep each counterfactual as a separate contrast; no claim their sum is total. Add property tests for probability sums, complements, monotone nested goal lines, side swap with home advantage accounted for, extreme valid rates and unsupported family rejection. Failed distribution validation keeps basis, never a partially modified set of markets.
- [ ] Integrate B3 internally with a **new** future prediction version, not the immutable 15K contract signature. Do not inherit old validation metrics onto changed probabilities. Runtime user activation stays through D2/D3.
- [ ] Run football-context and challenge/provenance regression tests with `b5-green`; commit exact files with message `feat: calculate coherent football context distributions from learned player effects`.

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

#### Kontextkern, Fußballausfälle und Tennisbelastung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tatsächliche Spieler- und Belastungsmerkmale erzeugen numerisch nachvollziehbare Vergleichsprognosen; nur empirisch freigegebene Varianten verändern die Nutzerprognose.

**Architecture:** Append-only Beobachtungen liefern versionierte Merkmale zum Entscheidungszeitpunkt. Regularisierte Modelle lernen Änderungen gegenüber eingefrorenen Basisparametern. Ein gemeinsamer Snapshot speichert Basis, experimentelle Vergleichsrechnung und tatsächlich verwendete Verteilung getrennt.

**Tech Stack:** Python, SQLite, NumPy/SciPy, bestehende Fußballverteilungen und Tennissimulator, pytest.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), insbesondere Abschnitte 4–7, 9 und 11.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Quote verändert weder Modell noch Reihenfolge; keine neue Marktverbotsliste.
- `available/missing/stale/conflicting/not_applicable` und `not_applied/experimental/applied` bleiben getrennt.
- Keine rückdatierten Beobachtungen, kein frei erfundener Star- oder Fünfsatzabschlag.
- Spielerreferenz ist die tatsächlich in der Basis enthaltene Besetzung; kein fiktiv immer gesunder Kader.
- Neue Torwirkung wird nicht ungeprüft auf Ecken, Karten oder Halbzeit übertragen.
- Die B-Aufgaben liefern implementierte Vergleichsmodelle. Produktive Anwendung erfordert D1/D2; ein leeres `applied=False`-Gerüst ist keine abgeschlossene Integration.

## Dateigrenzen und gemeinsame Datenverträge

Neue kleine Module: `context_observations.py`, `context_snapshots.py`, `context_models/__init__.py`, `context_models/contracts.py`, `context_models/offset.py`, `context_models/football.py`, `context_models/tennis.py`, `context_sources/__init__.py`, `context_sources/football.py`, `context_sources/tennis.py`. Bestehende Provider normalisieren in diese Module; sie lernen keine Effekte.

Die folgenden Dict-Verträge sind feste Schnittstellen, nicht beliebige Durchreichbehälter. `context_models/contracts.py` prüft erlaubte Schlüssel, echte Typen, endliche Zahlen und zeitzonenbehaftete ISO-Zeitpunkte.

- **Event:** `event_key`, `sport`, `competition`, `format`, `home_id`, `away_id`, `scheduled_start`, `schedule_revision`, `status`. Native IDs mit Quellennamensraum; `status` ist `scheduled`, `cancelled`, `started` oder `completed`.
- **FeatureVector:** `version`, `event_key`, `cutoff`, `values` (Name zu Zahl oder `None`), `states` (Name zu Datenstatus), `refs` (Name zu Beobachtungshashes), `coverage` (versionierter Abdeckungsfall), `reference_hash`.
- **BaseDistribution:** `version`, `model_hash`, `event_key`, `cutoff`, `family`, `params`, `markets`, `history_refs`, `reference_weights`. `markets` enthält marktvertragstreue Wahrscheinlichkeiten; `reference_weights` dokumentiert die wirklich für die Basis verwendeten historischen Gewichte getrennt nach Team und Modellkomponente (Angriff/Abwehr, Heim-/Auswärtsanteil), nicht ein erfundenes gemeinsames Durchschnittsfenster. Jeder Komponentenwert enthält native Eventreferenzen und normalisierte Gewichte.
- **EffectArtifact:** `schema=1`, `sport`, `family`, `feature_version`, `feature_names`, `heads`, `preprocessing_artifacts`, `joint_calibration`, `training_end`, `training_refs_hash`, `population`, `coverage`, `model_variant`. `heads` enthält benannte B2-Fits mit `link`, `scale`, `coef`, `alpha`, `n_rows`: `home/away` für Tor-/Hockeyraten, `hold_a/hold_b` für Tennisaufschlag, `winner` für binäre Sieger, `margin` für Basketball. Listen sind JSON-Zahlenlisten, keine NumPy-Objekte. `preprocessing_artifacts` bindet die Hashes trainierter Teilnahme-/Referenzmodelle; erste gemeinsame Parameterkalibrierung ist explizit `{"kind":"identity"}`. Kein `approved=True` im Modellpayload; die Freigabe liegt in einem separaten D2-Abnahmeartefakt und muss Hash/Population treffen.
- **ContextResult:** `event_key`, `base_hash`, `effect_hash`, `role`, `factor_roles`, `factor_states`, `feature_refs`, `base_params`, `comparison_params`, `used_params`, `base_markets`, `comparison_markets`, `used_markets`, `delta_pp`, `limitations`. Experimentelle Vergleichsrechnung ist nicht automatisch die verwendete Zahl. Die Kartenprojektion ergänzt `selected_market`, ohne den gespeicherten Eventstand zu ändern.
- **TrainingRow:** `event_key`, `decision_at`, `result_observed_at`, `block`, `population`, `coverage`, `feature_names`, `x`, `offset`, `target`, `trials`, `base_hash`, `feature_refs`, `evidence_class`. Alle Zeilen eines Events bleiben im selben Split; `target` ist nur für Training/Auswertung, niemals ein Prognosemerkmal.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
