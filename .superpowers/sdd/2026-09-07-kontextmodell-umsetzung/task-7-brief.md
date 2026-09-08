## Task 7: B3 — Eine gemeinsame Rechenrevision und unveränderte Basis bei Experimenten

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

Read `validation-contract-decisions.md` in this SDD directory completely, especially the exact verified approval transport/kinds/payload and its trusted D2 resolver boundary. It closes the downstream format before B3 is implemented; do not invent a competing approval shape or a non-None bypass.

Read `context-contract-decisions.md` in this SDD directory completely. It resolves the full FeatureVector hash in snapshot identity and explicit event/features/effect-envelope inputs for pure role selection, exact population/approval bindings, and factor-role bounds. Do not implement the original non-None approval pseudocode as a bypass.

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
