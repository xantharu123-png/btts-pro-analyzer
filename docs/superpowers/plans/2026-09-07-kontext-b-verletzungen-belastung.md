# Kontextkern, Fußballausfälle und Tennisbelastung Implementation Plan

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

## B1: Beobachtungen, Korrekturen und Frische

**Files:** Create `context_observations.py`, `context_models/contracts.py`, package `__init__.py` files, `tests/test_context_observations.py`.

**Interfaces:**

- `append_observation(path: Path, record: dict, *, observed_at: datetime) -> str`.
- `observations_as_of(path: Path, event_key: str, *, cutoff: datetime, schedule_revision: str, mode: str = "prospective") -> tuple[dict, ...]`.
- `factor_state(rows: tuple[dict, ...], *, cutoff: datetime, scheduled_start: datetime, policy: dict) -> dict` returns `state`, `refs`, `coverage`, `fresh_until`, `policy_version`.
- Record keys: `event_key`, `sport`, `competition`, `format`, `subject_id`, `kind`, `source`, `source_schema`, `source_revision`, `schedule_revision`, `published_at`, `publication_proof`, `valid_from`, `valid_until`, `complete`, `payload`. `observed_at` is assigned by ingestion clock, never copied from provider data.

- [ ] **RED – a late correction must not enter an earlier prediction.**

```python
from datetime import datetime, timedelta, timezone
from context_observations import append_observation, observations_as_of

def test_late_injury_correction_is_not_backdated(tmp_path):
    path = tmp_path / "models.db"
    cutoff = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
    row = dict(event_key="api-football:football:1", sport="football",
               competition="39", format="90min", subject_id="player:7",
               kind="availability", source="api-football", source_schema="injuries-v3",
               source_revision="r1", schedule_revision="s1", published_at=None,
               publication_proof=None, valid_from=cutoff.isoformat(),
               valid_until=None, complete=False, payload={"status": "out"})
    first = append_observation(path, row, observed_at=cutoff)
    corrected = {**row, "source_revision": "r2", "payload": {"status": "available"}}
    append_observation(path, corrected, observed_at=cutoff + timedelta(hours=1))
    rows = observations_as_of(path, row["event_key"], cutoff=cutoff,
                              schedule_revision="s1")
    assert [r["digest"] for r in rows] == [first]
    assert rows[0]["payload"]["status"] == "out"
```

- [ ] Run `.codex_test_venv/quality/Scripts/python.exe -m pytest tests/test_context_observations.py -q -p no:cacheprovider --basetemp=.pytest_tmp/b1-red`; expected missing module.
- [ ] **Implement append-only observation tables in A1's DB.** Separate content identity from receipt identity: canonical source/content digest plus an immutable receipt row for each actual fetch. Exact duplicate ingestion of one receipt is idempotent; a later genuine recheck of unchanged content gets a new receipt and can refresh freshness without rewriting first-observed time. Hash includes actual observation time and source revision, not just status text.

```sql
CREATE TABLE IF NOT EXISTS context_observations (
  digest TEXT PRIMARY KEY,
  event_key TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  schedule_revision TEXT NOT NULL,
  source TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  payload BLOB NOT NULL
);
```

- [ ] **Implement time selection.** Canonical timestamps are UTC with fixed precision before comparison. Prospective query requires `observed_at <= cutoff`; then choose the newest qualifying source/subject/kind revision. Conflicting simultaneous sources remain conflicting unless an explicit source-precedence policy resolves them. `mode="historical"` may include verifiable earlier publication only through a recognized archived-publication proof; it labels such rows `archival_verified` and everything else `retrospective`. A provider's bare `verified` flag is not proof. Strict D2 cohorts accept only prospective or separately verified prior publication, never a fabricated observation time.
- [ ] **Implement versioned freshness policy.** Initial operational policy `context-freshness-v1`: availability/expected lineup receipts expire after 6 hours, and after 30 minutes when kickoff is within 2 hours; confirmed lineups are tied to exact schedule revision and expire at kickoff; weather receipt expires after 3 hours and forecast-valid interval must include kickoff; immutable completed workload facts have no wall-clock expiry, but coverage freshness and corrections are evaluated separately. These are configurable operational expiry periods, not effect sizes or claims of provider completeness. Copy existing stricter source limits when present. Empty `complete=False` list is missing, not healthy. Event reschedule/cancellation invalidates event-bound observations.

```python
if not rows or not any(row["complete"] for row in rows):
    return {"state": "missing", "refs": [r["digest"] for r in rows],
            "coverage": "incomplete", "fresh_until": None,
            "policy_version": policy["version"]}
```

This branch applies to factors that require a complete collection; a single confirmed absence can be available as a reported-player fact while the team's overall absence coverage remains incomplete. Represent those as separate factors, not one misleading state.

- [ ] Add tests for later unchanged recheck, missing vs empty-complete, partial player fact, stale, source conflict, future publication, naive timestamps, moved fixture, identical names/different native IDs, walkover and genuine retrospective history. Write the normalized record fixture for each test explicitly.
- [ ] Run B1 and context-coverage regression files with `b1-green`; commit exact files with message `feat: persist causal context observations and coverage revisions`.

## B2: Reale regularisierte Offset-Schätzung

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

## B3: Eine gemeinsame Rechenrevision und unveränderte Basis bei Experimenten

**Files:** Create `context_snapshots.py`, `tests/test_context_snapshots.py`; extend contracts.

**Interfaces:**

- `snapshot_key(event: dict, *, base_hash: str, context_refs: tuple[str, ...], feature_version: str, effect_hash: str | None, decision_at: datetime, approval_hash: str | None) -> str`.
- `compute_once(path: Path, key: str, compute: Callable[[], dict]) -> dict`; callback is deterministic, CPU-only, no provider/DB calls.
- `select_context_result(base: dict, comparison: dict | None, *, effect_hash: str | None, approval: dict | None, factor_roles: dict, factor_states: dict, limitations: list[str]) -> dict` returns ContextResult. Approval input is a verified D2 decision, never arbitrary provider JSON.

- [ ] **RED – identical reads compute once.**

```python
from context_snapshots import compute_once

def test_shared_snapshot_computes_once(tmp_path):
    calls = []
    def calculate():
        calls.append(1)
        return {"used_markets": {"home": .6}}
    first = compute_once(tmp_path / "models.db", "a" * 64, calculate)
    second = compute_once(tmp_path / "models.db", "a" * 64, calculate)
    assert first == second
    assert len(calls) == 1
```

- [ ] Run B3 test file with `b3-red`; expected missing module.
- [ ] **Implement snapshot identity and atomic materialization.** Hash a fixed allowlist of Event identity, kickoff/schedule, base, sorted context references, feature/effect/approval identity and shared worker decision cutoff. Unknown keys including odds/price are rejected from model input; UI readers receive the persisted cutoff and do not manufacture a new one on each rerun. An approval transition changes which distribution is used, hence is part of identity.

```python
connection.execute("BEGIN IMMEDIATE")
row = connection.execute("SELECT payload FROM context_snapshots WHERE key=?", (key,)).fetchone()
if row is not None:
    connection.commit()
    return json.loads(row[0])
result = compute()
payload = canonical_bytes(result)
connection.execute("INSERT INTO context_snapshots(key,payload) VALUES (?,?)", (key, payload))
connection.commit()
return result
```

Initialize table before transaction; on callback error roll back. Existing key with corrupted bytes fails integrity check instead of recomputing and silently replacing history. Include payload digest. Use A1 connection/path rules. A transaction keeps two concurrent workers from doing the same CPU computation; never hold it across network/training. A process crash may require recomputation but cannot publish half a snapshot.
- [ ] **Implement role/used value selection.**

```python
role = "applied" if approval is not None and comparison is not None else (
    "experimental" if comparison is not None else "not_applied")
used = comparison if role == "applied" else base
delta_pp = {k: 100. * (used["markets"][k] - base["markets"][k])
            for k in used["markets"] if k in base["markets"]}
```

Approval must bind effect hash, population, family, feature version, coverage and model variant (D2). Recompute from `base.params`, never `prior.used_params`. An accepted zero-coefficient effect still has `role=applied`. Keep experimental comparisons out of ordinary probability/15K fields.
- [ ] Add tests for price/Tab invariance, changed schedule/context/model/approval creates new key, stale feature returning to base, repeated adjustment not compounded, accepted zero effect, unknown approval, callback failure, concurrent workers and historical snapshot immutability.
- [ ] Run B3 with `b3-green`; commit exact files with message `feat: share immutable context calculations across forecast surfaces`.

## B4: Fußballquellen, Besetzungsreferenz und fragliche Einsätze

**Files:** Create `context_sources/football.py`, `tests/test_football_context_sources.py`, `tests/test_football_context_features.py`; create `context_models/football.py`; modify `challenge_15k.py` provider helpers and `challenge_engine.py` base provenance.

**Interfaces:**

- `normalize_football_context(event: dict, *, injuries: list[dict], lineups: list[dict], appearances: list[dict], observed_at: datetime) -> tuple[dict, ...]`: B1 records.
- `roster_delta(reference_minutes: dict[str, float], expected_minutes: dict[str, float]) -> dict[str, float]`: expected-minus-reference, each divided by 90; inputs require complete aligned identities.
- `football_features(event: dict, observations: tuple[dict, ...], base: dict, *, cutoff: datetime, preprocessing: dict | None = None) -> dict`: FeatureVector. Reference exposure uses the same historical events/weights as `base.reference_weights`. `preprocessing` maps artifact hashes to already verified payloads; no hidden I/O inside feature generation.
- `expected_roster(appearances: tuple[dict, ...], availability: tuple[dict, ...], *, cutoff: datetime, participation: dict | None = None) -> dict`: `central_minutes` (mapping or `None`), `scenarios` (named minute mappings), `coverage`, `refs`. No participation artifact means no probabilistic mixture for doubtful players.
- Normalized appearance payload: `player_id`, `team_id`, `fixture_id`, `minutes`, `started`, `role`, `result_observed_at`, `event_start`, `event_end`, `performance`; nullable fields remain null. No current season aggregate may masquerade as an old match row.

- [ ] **RED – long-term absence already inside the base must not be deducted again.**

```python
from context_models.football import roster_delta

def test_reference_roster_prevents_double_absence_deduction():
    reference = {"starter": 0., "replacement": 90.}
    same = {"starter": 0., "replacement": 90.}
    returned = {"starter": 60., "replacement": 30.}
    assert roster_delta(reference, same) == {"starter": 0., "replacement": 0.}
    assert roster_delta(reference, returned) == {"starter": 2/3, "replacement": -2/3}
```

- [ ] Run football-context feature tests with `b4-red`; expected missing function.
- [ ] **Probe allowed real data before writing provider field assumptions.** Reuse `ChallengeDataProvider` injuries/lineups and football quota helpers. Limit probe to one future fixture and at most two completed fixtures plus existing caches; count every request in the existing budget. Inspect official current endpoint documentation for player appearances and compare native response IDs, minutes/start/role fields, status, timestamps and response completeness. Save sanitized structural samples under `tests/fixtures/context/football/` and aggregate coverage in `docs/audits/2026-09-07-kontext-daten.md`. Never save credentials, request headers or personal account data. If historical minutes are not available, mark that source unavailable and continue independent B6 work; do not manufacture samples and claim live coverage.
- [ ] **Implement source normalization/identity joins.** Split confirmed absent, suspended, doubtful and available; use fixture/team/player IDs. A complete verified lineup overrides uncertain expected participation, not immutable prior observations. Expected minutes for a confirmed starter still come from historical starter minutes; starting does not imply 90 minutes. Missing player minutes/performance remain unknown. Ignore any free `material_impact` field for estimating coefficients.

```python
def roster_delta(reference_minutes, expected_minutes):
    if set(reference_minutes) != set(expected_minutes):
        raise ValueError("incomplete roster identity coverage")
    return {player: (expected_minutes[player] - reference_minutes[player]) / 90.
            for player in sorted(reference_minutes)}
```

- [ ] **Implement expected participation and reference features.** Reference minutes are the component-specific weighted average appearances over exactly the baseline's contributing matches, with existing recency/home-away weighting exposed in base provenance. If attack/defence components have different reference exposure, emit separately named reference-difference columns for each. A 90-minute goal family needs regulation exposure; total minutes from an extra-time fixture cannot be silently treated as regulation minutes or clamped without period/substitution evidence. Total observed minutes may still enter the separate workload timeline. Unknown regulation exposure is a coverage gap. Confirmed out/suspended means expected zero; confirmed lineup uses starter/bench history. Unknown completeness is not healthy. Probabilities for doubtful statuses require a separately trained participation model from earlier announced-status→actual-appearance pairs, fitted inside D1 windows using B2 binomial loss. Without it, produce named present/absent scenario vectors and no central mixture. Global squad coverage remains distinct from individually confirmed facts.
- [ ] Player coefficients and role/team shrinkage are trained, not assigned by names. Add opponent/base strength and competition identifiers already known at cutoff to the fitting design. Fixed effect regularization and pooled role terms are explicit feature groups; unobserved players get only a separately tested pooled variant, not fabricated individual weight. Permanently absent players with no role variation cannot get an identified individual effect.
- [ ] Add source tests using real sanitized shapes, native collisions, corrected lineup, exact roster reference, replacement, questionable/no-probability, known attendance model, future season totals rejection and confirmed-absence/partial-list coverage. Test `roster_delta` numeric validation: finite 0–match-duration minutes, bool rejected.
- [ ] Run B4 tests and `tests/test_context_coverage.py` with `b4-green`; commit exact source/model/provider/provenance/test/sample/report files with message `feat: derive football availability against the actual base roster`.

## B5: Geschätzte Spielerwirkung auf eine gemeinsame Torverteilung

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

## B6: Tatsächliche Tennisbelastung und zeitlich belegte Erholung

**Files:** Create `context_sources/tennis.py`, `context_models/tennis.py`, `tests/test_tennis_context_features.py`; extend `tennis/workload.py` and its existing tests.

**Interfaces:**

- `normalize_tennis_workload(rows: tuple[dict, ...], *, observed_at: datetime) -> tuple[dict, ...]`: B1 records from real completed-history/shadow sources.
- `recovery_bounds(*, next_start: datetime, result_observed_at: datetime, ended_at: datetime | None) -> dict` gives `minimum_hours`, `exact_hours`.
- `tennis_features(event: dict, observations: tuple[dict, ...], base: dict, *, cutoff: datetime) -> dict`: FeatureVector with signed A-minus-B load and separate coverage flags.

- [ ] **RED – observed result gives only a lower recovery bound.**

```python
from datetime import datetime, timezone
from context_models.tennis import recovery_bounds

def test_result_observation_is_not_match_end():
    next_start = datetime(2026, 9, 7, 18, tzinfo=timezone.utc)
    observed = datetime(2026, 9, 6, 18, tzinfo=timezone.utc)
    result = recovery_bounds(next_start=next_start, result_observed_at=observed, ended_at=None)
    assert result == {"minimum_hours": 24., "exact_hours": None}
```

- [ ] Run with `b6-red`; expected missing function.
- [ ] **Probe existing tennis response/history fields.** Reuse current fixture and result source and `tennis/workload.py` provenance. Probe no more than two known completed matches. Record whether sets, games, duration, real start/end, retirement side and availability are actually supplied. Preserve native source/event/player/tour IDs. Do not infer time from `tourney_date`, winner label or scrape an unapproved health source. Capture sanitized response-shape fixtures and the data report.
- [ ] **Implement timestamps and coverage.**

```python
minimum = (next_start - result_observed_at).total_seconds() / 3600.
exact = None if ended_at is None else (next_start - ended_at).total_seconds() / 3600.
if minimum < 0 or (ended_at is not None and ended_at > result_observed_at):
    raise ValueError("inconsistent completed-match chronology")
return {"minimum_hours": minimum, "exact_hours": exact}
```

This is a bound on the interval to the **scheduled next start**, not a measured future physiological state. Validate aware times and previous match start ≤ end ≤ observation ≤ decision < next start. If actual end is unknown, use bound and an explicit bound-kind feature; never feed it into a coefficient trained on exact rest without a tested coverage variant.
- [ ] Build 1-, 3- and 7-day observed sets/games/minutes totals with independent completeness flags; windows are declared feature definitions, and usefulness is learned/validated. Prior future-scheduled fixtures never count. Retirement contributes only observed completed workload, with incomplete-match flag; walkover supplies no fictitious games/minutes. Absence of duration stays null. Deduplicate native events across feeds, do not sum both. Surface/indoor are already base features; only learned interactions with load may be new columns.
- [ ] Verified availability/return reports use B1 records. Retirement alone provides no diagnosis and cannot identify the injured side unless the source explicitly does. Actual travel is a separate evidenced input; tournament location difference alone is not travel duration/jetlag. No report leaves those factors missing, not available.
- [ ] Add tests for five-set vs three-set actual counts, incomplete duration, exact vs bounded recovery, both participants swapped, near-midnight/UTC, duplicate sources, late correction, WTA namespace, walkover, retirement, future schedule, conflicting timing and fake injury inference.
- [ ] Run B6/workload/pending-refresh tests with `b6-green`; commit exact files with message `feat: derive causal tennis load and recovery features with explicit coverage`.

## B7: Tenniswirkung auf identifizierbarer Modellstufe

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
