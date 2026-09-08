## Task 11: B7 — Tenniswirkung auf identifizierbarer Modellstufe

**Files:** Extend `context_models/tennis.py`, `tennis/predict.py`; create `tests/test_tennis_context_model.py`.

**Interfaces:**

- `apply_tennis_effect(base: dict, features: dict, artifact: dict) -> dict`: comparison BaseDistribution for `tennis:serve` or `tennis:winner`, never silently crossing families.
- `build_tennis_training_rows(observations: tuple[dict, ...], baselines: tuple[dict, ...], *, training_cutoff: datetime) -> list[dict]`.
- `tennis_factor_comparisons(base: dict, features: dict, artifact: dict) -> dict[str, dict]`.

- [ ] **RED – Elo-only cannot acquire invented serve/side markets.**

```python
import pytest
from context_models.tennis import apply_tennis_effect

def test_elo_only_rejects_serve_effect_without_hold_parameters():
    base = {"family": "tennis:winner", "params": {"p_a": .6},
            "markets": {"winner_a": .6, "winner_b": .4}}
    features = {"version": "tennis-load-v1", "values": {}, "coverage": "winner-only"}
    artifact = {"family": "tennis:serve", "feature_version": "tennis-load-v1"}
    with pytest.raises(ValueError, match="family"):
        apply_tennis_effect(base, features, artifact)
```

- [ ] Run with `b7-red`; expected missing integration.
- [ ] **Implement winner-only variant.** Canonical A/B orientation plus a signed, antisymmetric feature vector. B2 logit offset on baseline winner probability; swapping both players and all signed features yields the complementary probability. A source-qualified availability flag may enter its own trained variant. Winner-only output contains exactly winner A/B; existing side-market bases stay separately labelled, not falsely adjusted.

```python
delta = float(offset_delta(artifact["heads"]["winner"], x)[0])
p_a = float(adjust_parameters(np.array([base["params"]["p_a"]]),
                             np.array([delta]), link="logit")[0])
markets = {"winner_a": p_a, "winner_b": 1. - p_a}
```

- [ ] **Implement serve-identified variant.** Fit `artifact["heads"]["hold_a"]` and `artifact["heads"]["hold_b"]` changes from actual successes/trials with B2 binomial objective, not only winner outcomes. Apply to both hold logits, then call existing `tennis.simulator.simulate_match(p_hold_a, p_hold_b, best_of)` with actual best-of and existing tiebreak rules. Use the returned distribution for winner, sets, games and related supported markets. No subsequent independent winner Platt correction or winner-only Elo blend may break coherence: this first new variant has explicit identity parameter calibration and must pass its own D2 comparison/calibration checks; keep legacy blend in the legacy branch. The simulator's `hold_to_point_prob` already provides its inversion; do not add a second approximation. Verify clipping/rounding in the existing simulator does not hide an invalid new parameter or unsupported rule format.
- [ ] **Implement strict activation identity.** Model variant binds tour, surface/environment coverage, best-of, actual duration/rest coverage, serve sufficiency and training provenance. Artifact schema rejects inherited calibration metrics from old probability versions. D1 trains/fits every scaler/interaction on earlier data; sparse/unsupported populations remain base, not auto-transferred from ATP Hard to WTA/Clay.
- [ ] Add synthetic fitted-load test with observed successes/trials and expected nonzero change, counterpart/side-swap tests, sum/monotonicity checks across sets/games, exact/bound-rest variant mismatch, zero learned effect, double adjustment, surface no-double-count, no injury-by-retirement and quote-invariance tests. The artificial fatigue signal tests code, not real tennis validity.
- [ ] Wire internal comparison through B3, preserving original predictions and available baseline side markets. Test `p_a_cal`, `p_b_cal` and public market summary all reference the same **used** version and no experimental number reaches 15K fields.
- [ ] Run B7, tennis predictor/side-bet/revision/workflow regression tests with `b7-green`; commit exact files with message `feat: compute learned tennis workload effects at the supported model level`.
- [ ] Execute D1/D2 for the first data-supported football/tennis families; publish software/data/empirical status separately before moving to broader C work. No synthetic fixture can satisfy the 200-real-event activation requirement.

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
