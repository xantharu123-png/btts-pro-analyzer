# Tennis-Spielerindex Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Den vorhandenen Tennis-Batch mit einer vollständigen abgeleiteten Spieler-Spiel-Zuordnung innerhalb des unveränderten echten Vier-Fall-/45-Sekunden-Gates nutzbar machen.

**Architecture:** Zwei optionale Tabellen in derselben Datenbank; Quellen und Index werden atomar gepflegt. Ein expliziter, fortsetzbarer Aufbau ersetzt die globale JSON-Suche. Private v2-Kopien bleiben hinsichtlich des Index ausdrücklich ungültig; kein zusätzliches allgemeines Änderungsledger.

**Tech Stack:** Vorhandenes Python, SQLite, pytest, bestehende physische/native Validatoren; keine neue Bibliothek oder API.

**Spec:** `docs/superpowers/specs/2026-10-15-tennis-spielerindex-design.md`, vom Nutzer am 15.10.2026 schriftlich freigegeben.

## Global Constraints

- Nur Planung freigegeben; Umsetzung erst nach Prüfung dieses Plans. Bereits gewählte Methode: Unteragenten mit Review je Aufgabe.
- Kanonisch `C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013`, Arbeitsbranch `codex/audit-repairs-20261013`, Planungsbasis `e1e898a`. Root-WIP und `output/audit-repairs/` erhalten.
- „höchstens 512 Quellzeilen und 2 MiB Tennisinhalte je Chunk“, „bestehende 256-MiB-Retentionsgrenze“, „2-Sekunden-Budget“ pro Aufbau-Schreibtransaktion einschließlich Lock/SQLite, „höchstens 45 Sekunden“ je Aufbauaufruf, „64 MiB logische Werte“ zusätzlich. Keine RAM-/Dateigrößengarantie daraus.
- Echter Leser: **4/4 innerhalb insgesamt 45 Sekunden inklusive Vorbereitung**, dieselben Fälle/Stichtage; 512 Belege/2 MiB je Fall, 8 MiB insgesamt, CPU 50 s, AS 2 GiB, gemessener RSS unter 1 GiB.
- Alle Revisionen und Originalstichtage erhalten; keine Ergebnislabels beim Indexaufbau, kein stiller Fallback und keine verkürzte erfolgreiche Historie.
- Beide Writer und exakte optionale Schemakataloge einbinden. Alte `user_version`-/`application_id`-Verträge, C-Eingangsgrenzen und Originalzeilen-Unverändertheit erhalten.
- Keine neuen Backups, Produktionsdatenbankkopien, APIs, Dienste oder Zeitpläne; kein VACUUM/Originaldatenlöschen. Cricket, Wettformeln, Tickets, Geldbewegungen und POINT-Effektvertrag bleiben unverändert.
- Produktcode erst nach realer Freigabe veröffentlichen. Der für die Migration notwendige schemafähige Vorbereitungsstand ist **kein abgeschlossener Index-Release**; nach Migration nicht auf schemaunverträgliche alte Binaries zurückrollen.

## Review Focus

- RF1: Gültige NBA-Belege zwischen Tenniszeilen dürfen weder den Aufbau blockieren noch widersprüchliche Tennisidentitäten verdecken → Task 1.
- RF2: Negative Rowids, Legacy-Einfügung hinter dem Cursor und abgebrochene Chunks dürfen keine Vollständigkeit vortäuschen → Task 2.
- RF3: Ein volles Zusatzverzeichnis darf neue gültige Fußball-/Tennisquellen nicht verlieren; echte SQL-/Quellfehler müssen weiterhin zurückrollen → Task 3.
- RF4: Eine Kopie mit leerem Iterator oder ausschließlich Duplikaten darf ihren kopierten `ready`-Stand nicht verwenden → Task 4.
- RF5: Zwischen zwei Stichtagen erst bekannt gewordene Beteiligung darf nicht in den früheren Fall gelangen; alle später zugelassenen Revisionen bleiben erhalten → Task 5.

## Dateien und gemeinsame Schnittstellen

- Neu `context_tennis_index.py`: geschlossenes Schema, reine Projektion, Status-/Append-Owner und indizierter Leser. Keine Verbindungseröffnung/Migration beim Import.
- Neu `context_tennis_index_build.py`: explizite Migration und begrenzter Aufbau; nutzt bestehende Dateivertrauensprüfungen, `mode=rw`, niemals implizite Dateierzeugung.
- Neu `scripts/tennis_player_index.py`: CLI `init|build|status|disable`, kein Timer.
- Änderungen nur an den in den Tasks genannten bestehenden Ownern. Keine allgemeine Speicherframework-Reorganisation.
- `Membership = tuple[str,str,str,str,str]`: `(tour, player_id, event_key, first_observed_at, first_receipt_digest)`.
- `IndexState` ist unveränderlich: `schema_version: int`, `projector_sha256: str`, `db_identity: tuple[int,int]` (Gerät/Inode, kanonisch als TEXT gespeichert); `source_generation`, `index_generation`, `rewrite_generation`, `verified_source_generation`, `verified_index_generation`, `verified_rewrite_generation`, `logical_bytes` jeweils `int`; `covered_rowid: int|None`; `status: str` aus `building|ready|invalid`. Genau eine Zustandszeile `id=1`. SQL-Speichertypen strikt prüfen, nicht konvertieren.
- `logical_bytes = 4096 + sum(len(canonical_bytes(entry)) for entry in memberships)`; 4096 reserviert die begrenzte Zustandszeile. Physische SQLite-/Index-/WAL-Größe gesondert messen.
- `TennisIndexUnavailable(ContextContractError)` signalisiert fehlenden verwendbaren Index, **nicht** eine leere Historie. `IndexBudgetExceeded` ist nur der erwartete Zusatzbudgetfall, kein Sammelfang für SQL-/Quellfehler.

## Verifikation und Arbeitsregel

Alle pytest-Befehle über `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe -B C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py` aus dem kanonischen Checkout. Im Folgenden heißt dieser vollständige Aufruf `QA`. Je Lauf frisches TEMP/TMP/`--basetemp` unter `C:/Projekt/BetBoy/output/tennis-player-index-20261015`; `DJANGO_SETTINGS_MODULE=siteconfig.qa_settings`, `PYTHONPATH=<Checkout>/portal`.

Vor Produktänderung: aktuellen Bestand sammeln, alle QA04-14.133-IDs und sämtliche Task-23-IDs festhalten. Alte Tests/Fehlerbelege nicht löschen oder abschwächen. Jede Aufgabe endet mit eigenem RED/GREEN-Nachweis, geprüftem Commit auf dem Arbeitsbranch und begrenztem Review; noch kein Zwischenstand nach `main`.

### Task 1: Geschlossenes Schema und tatsächliche Mitgliedschaftsprojektion

**Files:** Create `context_tennis_index.py`, `tests/test_tennis_player_index_schema.py`; Modify `context_runtime.py:244–261`.

**Interfaces:** Produces `INDEX_SCHEMA: dict[str,str]`, `IndexState`, die obigen Fehlerklassen; `project_memberships(receipt: dict) -> tuple[Membership,...]`; `check_index_schema(connection) -> bool` (fehlend `False`, exakt vollständig `True`, Drift/Teilfamilie `ArtifactIntegrityError`); `read_index_state(connection) -> IndexState`. In `context_runtime.py`: `verify_context_schema_objects(connection) -> set[str]`, rein strukturell; `_verify_schema` behält danach seine bisherigen Integritäts-/FK-Prüfungen.

- [ ] **1. RED schreiben:** echte SQLite-Tests `test_legacy_and_complete_optional_schema_only`, `test_missing_or_modified_trigger_is_unavailable`, `test_projection_keeps_unknown_and_removed_participants`, `test_nba_is_not_tennis_but_cross_tour_corruption_fails`. Assert: genau zwei optionale Tabellen, alte `_SCHEMA` unverändert, keine Teilfamilie/zusätzlichen Objekte zulässig; NBA-Projektion `()`, native Teilstatus behalten jeden bekannten Spieler. REAL statt Integer muss scheitern.

  ```python
  assert check_index_schema(legacy_connection) is False
  assert "WITHOUT ROWID" in INDEX_SCHEMA["tennis_player_events"]
  assert project_memberships(physically_decoded_nba_receipt) == ()
  ```
- [ ] **2. RED ausführen:** `QA tests/test_tennis_player_index_schema.py -q`; erwartetes Scheitern wegen fehlendem Owner dokumentieren.
- [ ] **3. Minimal implementieren:** `tennis_player_events` exakt als `WITHOUT ROWID` mit dem spezifizierten Schlüssel. Kontrollzeile und feste SQL-Invalidierungstrigger: Quelleninsert erhöht Quellgeneration; Quellenänderung/-löschung und Insert unter/gleich Cursor erhöhen zusätzlich Rewritegeneration; Zuordnungs-DML erhöht Indexgeneration. Nur eigener vollständig geprüfter Abschluss darf `ready` setzen. Keine UDFs, keine automatische Migration; Bibliotheksimporte ohne Zyklus zu `context_observations`/`context_runtime`. Physisch/nativ geprüfte Tennisbelege projizieren, eindeutige Nicht-Tennis-Belege ohne Zuordnung verarbeiten; unverständliche Tennisfälle nicht still überspringen.
- [ ] **4. GREEN/Nachbarn:** `QA tests/test_tennis_player_index_schema.py tests/test_context_runtime_transport.py tests/test_context_runtime_semantics.py -q`; null Fehler. Tatsächlichen Tabellen-/Triggerentzug testen, nicht nur eine Mock-Statusflagge.
- [ ] **5. Commit/Review:** nur diese Dateien, `feat: define closed tennis membership schema and projection`. Noch kein DDL auf dem VPS.

### Task 2: Fortsetzbarer, kurz gesperrter Aufbau und Operator-CLI

**Files:** Create `context_tennis_index_build.py`, `scripts/tennis_player_index.py`, `tests/test_tennis_player_index_build.py`.

**Interfaces:** Consumes Task 1. Produces `initialize_index(path: Path) -> None`; `build_index(path: Path, *, seconds: float = 45) -> IndexBuildResult`; `disable_index(path: Path) -> None`. `IndexBuildResult`: `status: str`, `covered_rowid: int|None`, `source_tail_rowid: int|None`, `scanned_rows: int`, `logical_bytes: int`, `elapsed_seconds: float`, `stop_reason: str|None`. `status` CLI liest ausschließlich; `build` Exit 0 nur bei `ready`, Exit 3 bei begrenztem/unvollständigem Aufruf, Exit 2 bei ungültigem Stand/Integritätsfehler. `disable` auf vorhandener Datei ohne Index ist ein No-op ohne DDL; fehlende Datei wird nicht erzeugt.

- [ ] **1. RED schreiben:** `test_chunk_rollback_does_not_advance_cursor`, `test_resume_drains_concurrent_insert_without_gap`, `test_negative_rowid_and_legacy_insert_before_cursor`, `test_late_receipt_moves_minimum_and_tie_is_digest_ordered`, `test_size_and_lock_deadlines_abort_before_ready`, `test_missing_database_is_not_created`. Assertions: uninitialisierter Cursor `None` statt `0`; auch negative Quell-Rowids werden besucht; Einfügung unter Cursor oder Quellenrewrite verlangt vollständigen Neuaufbau; Status nie wegen `MAX(rowid)` allein `ready`.

  ```python
  with pytest.raises(FileNotFoundError):
      initialize_index(tmp_path / "absent.sqlite")
  assert not (tmp_path / "absent.sqlite").exists()
  assert interrupted_result.covered_rowid == last_committed_rowid
  assert completed_result.logical_bytes <= 64 * 1024**2
  ```
- [ ] **2. RED:** `QA tests/test_tennis_player_index_build.py -q`; fehlender Builder muss scheitern.
- [ ] **3. Implementieren:** ausschließlich eigene vorhandene vertrauenswürdige Datei öffnen; explizite optionale DDL atomar installieren. Chunks in vollständiger Rowid-Reihenfolge, Längen vor Körpern prüfen, nur ESPN-Status/Workload-Kandidaten dekodieren. Fortschritt/Zuordnung im selben Chunk committen; keine globalen JSON-Listen. 2-s-Uhr vor Lock, Busy-Timeout höchstens Restbudget, SQLite-Progresshandler und Python-Prüfungen teilen die Frist. 45-s-Aufrufgrenze umfasst Vorbereitung/Abschluss. Vor `ready` im gehaltenen Writer fehlende Delta-Zeilen und Rewrite-/Datei-/Projektorwechsel ausschließen. Nur abgeleitete Daten bei ausdrücklich notwendigem Neuaufbau ersetzen, niemals Quellen löschen. CLI ohne unbeschränkte Wiederholungsschleife.
- [ ] **4. GREEN:** `QA tests/test_tennis_player_index_schema.py tests/test_tennis_player_index_build.py -q`; reale zweite Verbindung für Konkurrenz/Lock-Test, echte Savepoint-/Rollback- und Unterbrechungsfälle; kein bloßes Uhr-Mock als einziger Nachweis.
- [ ] **5. Commit/Review:** `feat: build resumable bounded tennis player index`. Produktionsaufbau bleibt für Task 6 gesperrt.

### Task 3: Atomare Pflege im bestehenden Live-Append

**Files:** Modify `context_tennis_index.py`, `context_observations.py:131–177`; Create `tests/test_tennis_player_index_append.py`.

**Interfaces:** Produces `begin_index_append(connection) -> IndexAppendContext|None`, `observe_index_append(connection, receipt: dict, *, context: IndexAppendContext) -> None`, `finish_index_append(connection, *, context: IndexAppendContext|None) -> None`. Privater `IndexAppendContext` enthält `connection`, `before: IndexState`, `expected_source_delta: int`, `expected_index_delta: int` und `invalid: bool`; kein vom Aufrufer übernommenes „verified“-Flag. Abwesende Indexfamilie: `None`, altes Verhalten ohne DDL. Bereits `building|invalid`: keine neuen Zuordnungs-DML und keine Bereitschaftsbescheinigung; der Builder holt die Quellen nach.

- [ ] **1. RED schreiben:** `test_receipt_and_membership_commit_or_rollback_together`, `test_duplicate_new_clock_and_older_clock`, `test_budget_invalidates_index_but_keeps_valid_sports_receipt`, `test_sql_and_source_errors_still_rollback_batch`, `test_append_never_certifies_an_unprocessed_gap`. Assert: physische Quelldigests/Bytes unverändert, Duplikat kein neuer Indexeintrag, früherer Empfang korrigiert Minimum, Zusatzbudgetfehler bewahrt gültige Fußball-/Tennisbelege und setzt Index `invalid`.

  ```python
  assert read_index_state(connection).status == "invalid"
  assert connection.execute(
      "SELECT digest FROM context_observations WHERE digest=?", (receipt_ref,)
  ).fetchone() == (receipt_ref,)
  assert original_receipts_after == original_receipts_before
  ```
- [ ] **2. RED:** `QA tests/test_tennis_player_index_append.py -q` vor Hook-Einbau; fehlende atomare Pflege/Invalidierung reproduzieren.
- [ ] **3. Hook einbauen:** `begin` nach `BEGIN IMMEDIATE`, `observe` nach bestehender physischer Kollisionsprüfung, `finish` vor Commit. Keine zusätzliche Verbindung/Normierungsregel. Erwartete logische Zusatzbudgetfehler nur im abgeleiteten Savepoint zurücknehmen und `invalid` setzen; Datenbank-/Quellfehler nicht abfangen. Vorher schon unvollständigen Index niemals durch einen späteren normalen Append für vollständig erklären. Quellaufbewahrungsbudget und Zusatzindexbudget separat berücksichtigen.
- [ ] **4. GREEN/Nachbarn:** `QA tests/test_tennis_player_index_append.py tests/test_context_observations.py tests/test_tennis_player_index_build.py tests/test_team_sports_status.py -q`; kein API-Aufruf, alle Originalassertionen erhalten.
- [ ] **5. Commit/Review:** `feat: maintain tennis lookup with live receipt writes`.

### Task 4: v2-Inventur und privater Append ohne neues Ledgerframework

**Files:** Modify `context_storage_v2/inventory.py`, `context_storage_v2/receipt_append.py:92–179`, `context_storage_v2/receipt_corpus.py:445–564`, `context_tennis_index.py`; Create `tests/test_tennis_player_index_v2.py`.

**Interfaces:** In `inventory.py` add `_derived_rows(connection, table, *, max_value_bytes) -> Iterator[tuple]` und `_derived_row_hash(row: tuple) -> str` ausschließlich für die zwei festen neuen Tabellen. In Index-Owner: `invalidate_relocated_index(connection) -> None`. In Corpus: `_Build.verify_derived_delta() -> None`. Bestehende öffentliche APIs, `_Ledger`-Originalzugangstags und Größenreservierungen bleiben unverändert.

- [ ] **1. RED schreiben:** `test_without_rowid_inventory_is_complete_and_typed`, `test_copy_empty_or_duplicate_iterator_is_index_invalid`, `test_corpus_checks_only_expected_control_delta`, `test_wrong_player_row_or_original_mutation_is_rejected`. Neue Tabellen vollständig in der typisierten Inventur erfassen; keine `rowid`-/`blobopen`-Annahme für die Zuordnung. Uneingetragene Fremdänderungen auch dann ablehnen, wenn das erwartete Kontrollzeilen-Delta stimmt.

  ```python
  assert copied_state.status == "invalid"  # auch bei leerem Iterator
  assert copied_memberships == original_memberships
  assert source_path.read_bytes() == source_bytes_before
  ```
- [ ] **2. RED:** `QA tests/test_tennis_player_index_v2.py -q`; bestehende Inventur/Corpus müssen neue Familie beziehungsweise erwartete Zustandsänderung zunächst zurückweisen.
- [ ] **3. Minimal einbinden:** Nach Öffnen des privaten kopierten Writers den fremden Datei-Ready-Stand ausdrücklich invalidieren, **vor erstem Iteratorzugriff, auch ohne neue Eingaben**. Hook vor dem vorhandenen Receipt-Savepoint-Release; keine PRAGMA-/Commit-/Verbindungsänderung. Solange Kopie invalid ist, keine Spielerzuordnungen umschreiben/neu zertifizieren. Alle kopierten Zuordnungszeilen vollständig unverändert vergleichen; genau eine Kontrollzeile separat gegen alten Zustand + Invalidierung + durch das bestehende Originalledger belegte neue Receiptanzahl prüfen, nicht gegen `submitted`/`total_changes`. Keine vom Hook zurückgemeldete Selbstfreigabe, keine allgemeine Altzeilen-Ausnahme. Alte Originaltabellen und Zugangsledger vollständig wie bisher prüfen. Neuer optionaler Tabellen-Codec nur für feste skalare Schlüssel/Felder, BINARY-Schlüsselordnung, Längen vor Materialisierung; alles in bestehenden C-/Main-/Ledger-/Journal-/Workspace-Grenzen.
- [ ] **4. GREEN/Nachbarn:** `QA tests/test_tennis_player_index_v2.py tests/test_context_storage_inventory.py tests/test_context_storage_copying.py tests/test_context_storage_receipt_append.py tests/test_context_storage_receipt_append_review.py tests/test_context_storage_receipt_corpus.py -q`; alte Schemafälle und Manipulationsfälle unverändert bestehen.
- [ ] **5. Commit/Review:** `feat: account for invalid tennis lookups in private corpus copies`. Das ist keine C-Zulassung der großen Produktionsdatei.

### Task 5: Den tatsächlichen Batch-/Readiness-Leser umstellen

**Files:** Modify `context_tennis_index.py`, `context_models/tennis_training.py`, `context_models/readiness.py`, `context_models/evaluator.py`; Create `tests/test_tennis_player_index_consumers.py`; Adapt nur nötige Fixtures/Legacy-Aufrufe in `tests/test_tennis_training_batch.py`, `tests/test_tennis_readiness_batch.py`, `tests/test_context_readiness.py`.

**Interfaces:** Produces `player_event_keys(connection, *, tour: str, player_ids: tuple[str,...], cutoff: str) -> tuple[str,...]`. Ergänze `membership_mode: str = "indexed"` an `iter_live_tennis_features`, `build_live_training_cases` und `audit_tennis_readiness`; nur `indexed|legacy` zulässig. `relevant_receipts` und `build_live_training_case` bleiben unveränderte Einzelreferenz. Bestehende öffentliche Datenformate/Case-Digests unverändert.

- [ ] **1. RED schreiben:** `test_indexed_batch_matches_single_case_bytes_and_digests`, `test_two_cutoffs_admit_exactly_7_and_13_receipts`, `test_readiness_uses_index_in_its_held_snapshot`, `test_missing_dirty_or_replaced_index_never_returns_empty_success`, `test_inventory_only_never_needs_index`, `test_index_owner_hash_is_bound_to_real_evaluation`. Tatsächlicher SQL-Trace: normale Suche ohne globale JSON-/Content-Discovery, keine Ergebnisabfrage im Feature-Owner; frischer Reader nach Legacy-Write verweigert Verwendung.

  ```python
  assert canonical_bytes(indexed_cases) == canonical_bytes(single_cases)
  assert admitted_counts == [7, 13]
  assert connection.in_transaction
  ```
- [ ] **2. RED:** `QA tests/test_tennis_player_index_consumers.py -q`; es muss der echte aufgerufene Reader scheitern, kein unbenutztes Hilfsobjekt.
- [ ] **3. Umstellen:** exaktes Schema/Trigger, Version, Projektor-/Dateiidentität, Status und Generationen im selben Snapshot prüfen; Beleg jeder ausgewählten Zuordnung physisch/nativ bestätigen. Frühestes `observed_at <= cutoff` je Fall, Ziel immer dazu, danach bisherige vollständige Revisionen/Validierung/Ordnung und `PreparedTennisHistory`. Bestehende gemeinsame Zeit-/Bytebudgets erhalten. `legacy` nur ausdrücklich; alte globale Query-Tests dorthin routen, übrige Fixtures wirklich migrieren/aufbauen, keine Test-IDs/Assertions löschen. Evaluator bindet exakt `context_tennis_index.py`, `context_tennis_index_build.py`, `context_observations.py` und den genutzten Schemaowner `context_runtime.py` zusätzlich zu bisherigen Abhängigkeiten. Keine Altbericht-Umetikettierung, POINT-Guard- oder Quellenfamilien-Lockerung.
- [ ] **4. GREEN/Nachbarn:** `QA tests/test_tennis_player_index_consumers.py tests/test_tennis_training_batch.py tests/test_tennis_readiness_batch.py tests/test_context_readiness.py tests/test_tennis_live_training.py tests/test_tennis_status_v4.py -q`; nach Sourcefreeze Hashes protokollieren.
- [ ] **5. Commit/Review:** `feat: use verified tennis membership in batch and readiness`.

### Task 6: Vollständiger Nachweis und koordinierte Produktionsumstellung

**Files:** Update `TODO_AKTUELL.md`, `PC_WECHSEL_UEBERGABE.md`, `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/progress.md`; Create `docs/audits/2026-10-15-tennis-spielerindex-abnahme.md`. Prüf-/Deploymentartefakte nur unter `C:/Projekt/BetBoy/output/tennis-player-index-20261015/`, nicht pauschal ins Git.

**Interfaces:** Consumes Tasks 1–5 und vorhandenen echten Probe-Owner `C:/Projekt/BetBoy/output/tennis-batch-20261015/frozen_feature_probe.py` (SHA256 `58e031c070cda241575edd344505e4b08429fa3c873b0c9c288869a14fae0db1`). Kein Austausch der vier Ereignisse zur Erfolgsoptimierung.

- [ ] **1. Lokale Gesamtabnahme ergänzen/ausführen:** echte alte Schemafixture → kompatibler Code → explizite Migration → unterbrochener/fortgesetzter Aufbau → echter Consumer. Test `test_release_order_and_disable_keep_originals_usable` belegt: kein Ready vor Abschluss, keine automatische Migration, Deaktivierung ohne Originalverlust, neuer Reader schreibt nicht. `QA tests/test_tennis_player_index_consumers.py -q`, erwartet PASS; bei Fehler an zuständige Aufgabe zurückgeben statt ein RED künstlich herzustellen.

  ```python
  disable_index(db)
  assert disabled_state.status == "invalid"
  assert original_rows_after == original_rows_before
  assert reader_total_changes == 0
  ```
- [ ] **2. Finalfreeze und ganze Offline-Suite:** aktuelle Collection mit vorherigem Bestand vergleichen, bestehende Zwei-Shard-Verifikation aus `output/tennis-batch-20261015/qa-final-01/partition_qa.py` auf den neuen Lauf anwenden. Alle vorherigen IDs genau einmal, sämtliche bisherigen 98 Skipidentitäten unverändert, keine fehlenden/duplizierten/neuen stillen Skips; neue Tests zusätzlich. Erwartet: null Fehler in beiden JUnits und unveränderte Quell-/Root-WIP-Hashes. Vollständiger unabhängiger Abschlussreview; kein Sourcewechsel während des Laufs.
- [ ] **3. Kompatibilitätsstand bereitstellen:** erst nach lokaler Vollprüfung Main/VPS frisch abgleichen, nur Fast-Forward und nur erlaubte Dateien. Schemafähigen Code ohne neuen Sportscan/Backup deployen; aktive Writer für die kurze explizite DDL-Migration abwarten. Keine Schemaänderung unter alten Binaries. Normale App/Timer/Quellen bleiben funktionsfähig; alle weiteren Aufbauaufrufe begrenzt und fortsetzbar. Diesen notwendigen vorbereitenden Deploy ausdrücklich **nicht als fertige Reparatur** melden.
- [ ] **4. Aufbau und Originalschutz messen:** `python -B scripts/tennis_player_index.py init --db /opt/betboy/app/runtime_state/context_models.db`, dann begrenzte `build --seconds 45`-Einzelaufrufe mit demselben `--db`; Exit 3 nie als Erfolg. Fortschritt, längste Locks, tatsächliche logische/Tabellen-/Index-/WAL-Größe, CPU/RSS dokumentieren. Keine DB-Kopie und keine unbeschränkte Wiederholungsschleife; bei Integritäts-/Speicherfehler stoppen. Bereits indexierte Originalbelege nicht verändern.
- [ ] **5. Unveränderten nativen Gate ausführen:** erst nach `ready`, tatsächlicher neuer Consumer, vier gefrorene Originale und Originalstichtage aus dem bestehenden Probe-Owner, inklusive Vorbereitung insgesamt ≤45 s und sämtliche globalen Grenzen oben. Reale Belegreferenzen/Reihenfolge/Merkmale/Hashherkunft und CPU/RSS vollständig protokollieren. Kein Label/Fit/API. Bei FAIL Index mit kompatiblem Code deaktivieren, `main`/VPS-Zustand exakt berichten, Aufgabe offen lassen; nicht blind alte schemaunverträgliche Binaries zurückspielen.
- [ ] **6. Abschluss nur bei PASS:** lokaler/GitHub-/VPS-Hash, App/Caddy, sieben geplante Timer, abgeschaltetes Backup und beide Healthchecks nachprüfen; keine Zusatzscans. Erhaltene Originalbytes, Tickets und Geldbewegungen belegen. Audit/To-do/Übergabe mit tatsächlichem Ergebnis und Restarbeit committen/pushen; gegebenenfalls nur Dokumentation nachziehen, kein zweiter unnötiger Neustart. Index-PASS ist kein Nachweis besserer Wetter-/Verletzungs-/Müdigkeitsmodelle.

## Selbstprüfung und nächste Freigabe

Spec §1/2 → Tasks 1/5; §3 → Tasks 2/3/4; §4 → Tasks 1/2/4/5/6; §5 → Tasks 5/6. Alle fünf Review-Focus-Punkte haben konkrete owning Tests. Keine unbenannte Nachbar-API, kein neuer allgemeiner Ledger, keine C-Grenzerhöhung und kein stiller Quellenfilter. Zwei-Phasen-Umstellung trennt notwendigen schemafähigen Vorbereitungsdeploy von abschließendem Leistungs-/Nutzungsnachweis.

Dieser Plan wurde noch nicht ausgeführt. Nächster Schritt: Nutzer prüft/freigibt den Plan; anschließend Umsetzung wie zuvor gewählt mit Unteragenten und Review je Aufgabe.
