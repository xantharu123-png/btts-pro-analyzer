## Task 8: B4 — Fußballquellen, Besetzungsreferenz und fragliche Einsätze

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

Completed source preparation is in this SDD directory: `source-readiness-football-tennis.md`, `source-probe-evidence.md`, `football-source-probe-20260907.json`, and `football-injuries-probe-20260907.json`. Exactly two governed VPS GET requests were made at actual 2026-09-07 receipt times, for fixtures 1593305 and 1570343. Completed 1570343 exposed native fixture/team/player IDs and per-match minutes/roles, with 11 starters and 12 substitutes per team; sanitized files retain only selected player rows and are not complete-roster positive fixtures. Preserve real schema examples and label separately constructed test expansions as synthetic. No further probe is needed merely to rediscover fields already evidenced. The existing fixture response already contains nested players; do not automatically double-fetch `/fixtures/players`. Injury fixture.date is the match date, not injury publication/receipt. Missing Fixture also includes Coach's decision and Inactive, not only medical injury. No historical prematch injury evidence was established by these probes.

Baseline provenance preflight: `challenge_engine._team_observations` currently drops fixture identity. `_fixture_model` uses last 12 venue matches and last 6 overall matches; existing season/form blend is 0.75/0.25, separate scored/conceded goal and xG subsets, prior weights 4/3. There is no recency decay to invent. `football_data_history.py` uses negative pseudo fixture IDs for CSV rows; `merge_api_tail` keeps matching CSV rows and may remap API team IDs. Do not pass CSV IDs to API-Football or use name-only fuzzy joins as verified native identity. Preserve exactly the baseline math and source reference; if a native appearance join cannot be verified, report coverage missing rather than silently substitute another reference window. Component/prior provenance design questions should be surfaced before changing the shared BaseDistribution contract.

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
