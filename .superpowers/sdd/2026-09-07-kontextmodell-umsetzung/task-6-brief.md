## Task 6: B2 — Reale regularisierte Offset-Schätzung

**Files:** Create `context_models/offset.py`, `tests/test_context_offset.py`; extend `context_models/contracts.py`.

**Interfaces:**

- `fit_offset(x: np.ndarray, offset: np.ndarray, target: np.ndarray, *, link: str, alpha: float, trials: np.ndarray | None = None) -> dict` returns `link`, `scale`, `coef`, `alpha`, `n_rows`.
- `offset_delta(model: dict, x: np.ndarray) -> np.ndarray`.
- `adjust_parameters(base: np.ndarray, delta: np.ndarray, *, link: str) -> np.ndarray`.
- `link` is `log_rate`, `logit`, or `identity`; offsets are already in link space. Binomial targets are successes and `trials` counts; default trials is one. No intercept is fitted in this residual layer, preserving the defined zero-difference roster reference. Any joint calibration has its own D1-trained, versioned model variant.

- [ ] **RED – learn a nonzero effect from data, not a constant.**

```python
import numpy as np
from context_models.offset import fit_offset, offset_delta, adjust_parameters

def test_learned_count_effect_and_zero_reference():
    x = np.array([[-1.], [0.], [1.]] * 40)
    target = np.array([1., 2., 4.] * 40)
    model = fit_offset(x, np.full(120, np.log(2.)), target,
                       link="log_rate", alpha=.1)
    delta = offset_delta(model, np.array([[0.], [1.]]))
    assert delta[0] == 0.
    assert delta[1] > 0.
    adjusted = adjust_parameters(np.array([2., 2.]), delta, link="log_rate")
    assert adjusted[0] == 2.
    assert adjusted[1] > adjusted[0]
```

- [ ] Run `tests/test_context_offset.py` with `b2-red`; expected missing estimator.
- [ ] **Implement standardization and objective.** Use training-only feature scale `max(std, 1e-8)` without subtracting a mean from the reference-difference vector. Validate aligned finite arrays, nonnegative alpha, legal targets/trials; all-zero columns receive zero coefficient. Poisson and binomial use SciPy stable functions, with exact gradient. Gaussian keeps the baseline scale in this first variant.

```python
def objective(beta):
    eta = offset + z @ beta
    if link == "log_rate":
        mu = np.exp(eta)
        loss = np.mean(mu - target * eta)
        residual = mu - target
    elif link == "logit":
        loss = np.mean(trials * np.logaddexp(0., eta) - target * eta)
        residual = trials * scipy.special.expit(eta) - target
    else:
        residual = eta - target
        loss = .5 * np.mean(residual ** 2)
    return (float(loss + .5 * alpha * np.dot(beta, beta)),
            z.T @ residual / len(z) + alpha * beta)
```

Use `scipy.optimize.minimize(objective, np.zeros(z.shape[1]), jac=True, method="L-BFGS-B")`; reject non-convergence and non-finite objective/parameters instead of publishing. Stable Poisson evaluation must detect overflow and return an invalid fit, not silently clip rates to manufacture a better test loss. Training bounds, if needed, become a declared model variant fitted/selected in D1, not a live-only repair. Serialize fitted scales/coefficients with `.tolist()` and convert back with `np.asarray` only inside numerical functions.

- [ ] **Implement inverse links without percentage-point fudge.**

```python
if link == "log_rate":
    result = base * np.exp(delta)
elif link == "logit":
    result = scipy.special.expit(scipy.special.logit(base) + delta)
else:
    result = base + delta
```

Require positive rate, strictly interior probability, finite margin; impossible parameters return a typed model error and preserve the baseline via B3. A missing feature is not converted to zero: only a trained missingness variant may consume that coverage and its explicit mask. `alpha` selection is D1's inner-window job, not a hardcoded empirical effect.
- [ ] Add binomial, Gaussian, side reversal, zero coefficients, finite differences for gradients, single-row rejection, mismatched shapes, bool/NaN, unsupported link and convergence-error tests. Synthetic data tests prove mechanics only.
- [ ] Run B2 with `b2-green`; commit exact files with message `feat: learn regularized context offsets against frozen base models`.

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

Read `context-contract-decisions.md` in this SDD directory completely. In particular feature order is exact and shared between all heads; scale is training-only population standard deviation (ddof=0), without centering. Preserve the specified objectives and D1-only tuning policy.

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
