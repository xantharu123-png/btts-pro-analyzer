## Task 5: B1 — Beobachtungen, Korrekturen und Frische

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

Read `context-contract-decisions.md` in this SDD directory completely before implementation. It resolves receipt/content identity, canonical clock/proof trust, reference-weight shape, population scope and downstream binding contracts. No archive provider is currently recognized. Implement these fixed shapes and validators as B1 dependencies; do not invent reference data or certify an archive source. Existing TrainingRow family/head ruling remains in force.

Controller clarification (existing preflight ruling): TrainingRow includes explicit family and head string fields in addition to the listed contract. Validate family/head against the EffectArtifact family and allowed named heads at the producer/consumer boundary; these fields prevent home/away or serve-head routing ambiguity. Do not encode head identity by list order.


Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
