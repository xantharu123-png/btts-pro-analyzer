## Task 10: B6 — Tatsächliche Tennisbelastung und zeitlich belegte Erholung

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

Read `corpus-inventory-20260907.md` in this directory as bounded live evidence, not a training acceptance. The live tennis predictions table has the actual column `match_duration_minutes`, but all 1239 inspected rows are NULL; no exact ended_at or native participant-ID columns exist there. 104 result receipts and 73 set-score rows are not proof of exact duration, complete cross-competition load or 104 unique native matches. Preserve the measured source IDs/Games in the owning ingestion path; never substitute receipt time as exact end or infer identity from names. No additional provider calls were authorized by this evidence note.

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
