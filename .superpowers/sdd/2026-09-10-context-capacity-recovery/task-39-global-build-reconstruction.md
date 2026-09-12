# Task 39 — konkreter noch fehlender C-Gesamtaufbau

Stand: 12. September 2026. Reine lokale Code-/Evidenzrekonstruktion. Dieser Task
ändert ausschließlich diesen Bericht: keine Produktdatei, kein Owner-Test,
kein Git, kein Serverzugriff und kein nativer Korpuslauf. Die C-Entscheidung ist
laut Root durch das ausdrückliche Nutzer-„ja“ freigegeben; die ältere
„noch nicht freigegeben“-Formulierung im Spec ist kein neuer Freigabeblocker.

## Ergebnis

Die Bausteine bilden **noch keinen ausführbaren globalen 590.553-Beleg-/
199-Original-/199-Snapshot-/114-Stichtag-Aufbau**. Vier konkrete Anschlüsse
fehlen, nicht nur weitere Ressourcenchecks:

1. Ein wirklicher vollständiger Beleg-Corpusowner: unveränderte komplette
   Baseline plus genau 490.000 neu erzeugte und gespeicherte source-valid
   Receipts in einer für den derzeitigen C3-Owner tatsächlich lesbaren Form.
2. Ein verbindlicher Worker-/Reopen-Lifecycle. `HistoryView` und
   `StreamingTennisFeatures` sind laufzeitgebundene Objekte, keine nach einem
   Workerexit aus einem Dateinamen wieder herstellbaren Fähigkeiten.
3. Ein echter C-nativer Consumerproducer für die 168 neuen Originale/Snapshots.
   Der reale alte Producer existiert, benutzt aber Volltuples/Refsets und eigene
   Legacy-Schreiber. `put_snapshot_parts()` ersetzt diesen Producer nicht.
4. Die geschlossene vollständige Generation aus alter Raw-Coverage und neuen
   Ownerprodukten, mit tatsächlicher globaler Slot-/Kostenbilanz und danach B.

Task35 hat die beiden **einzelnen** neuen Builder korrekt auf begrenzte frische
Main-DBs umgestellt. Er hat diese vier Anschlüsse nicht behauptet oder gebaut.
Die kleinste sinnvolle Fortsetzung nach der kleinen Nativeprobe ist deshalb
eine **echte kleine Corpus→History→Consumer-Integration mit festen Pfaden**, an
deren tatsächlichen offenen Übergängen die unten bezeichneten APIs entstehen.
Noch ein allgemeiner Guard ohne diesen Datenfluss würde das Korpus nicht bauen.

## 1. Welche Größenbelege tatsächlich vorhanden sind

Der freigegebene Gesamtintegrationsplan bindet die Zielmenge in
`docs/superpowers/plans/2026-09-12-kontextspeicher-gesamtintegration.md:29`.

| Gegenstand | Tatsächlicher Stand | Konsequenz |
| --- | --- | --- |
| Task13 | Metadatenaufnahme der damals lebenden DB: 99.776 Receipts, 31 Originale/Snapshots, 16 Cutoff/Tour-Schlüssel | Die dortige Rechnung 589.776 ist historisch; kein heutiger Zielzähler. |
| Task14/B0 | Gesondert versiegelte Baseline: 100.553 Receipts/Contents, 31 Originale/Snapshots, 16 ATP-Cutoffs, zwei Tourstates; 270.233.600 DB-Bytes | Ausgangspunkt des genehmigten C-Profils. Ihre tatsächliche heutige native Verfügbarkeit wird hier nicht behauptet. |
| Task14-Wachstum | 70.000 + 70.000 + 6.782 tatsächlich normalisierte, physisch dekodierte und ausgewählte ATP-Statusreceipts | Nur Bytezählung bis zur alten 256-MiB-Historiengrenze; keine gespeicherte Wachstumsdatenbank. |
| Noch zu erzeugen | Je vollständigem vereinbartem Profil +490.000 Receipts, +168 Originale und separat +168 Snapshots, +98 Cutoff/Tour-Schlüssel | Tatsächliche Endmenge je Profil: 590.553 / 199 / 199 / 114, nicht bloß eine Mengenhochrechnung. |

Belegstellen: Task13-Bericht `task-13-growth-sizing.md:81`, Task14-Bericht
`task-14-sizing-result.md:47` und `:81`. Das archivierte ausgeführte Instrument
`evidence/task14-instrument/probe_task14_growth_size.py:310` erzeugt echte
normalisierte Statusinhalte, ihre kanonischen Bytes, Content-/Receiptidentitäten
und die reale physische Neun-Feld-Zeile. `:331` selektiert und zählt diese Zeilen.
`:372` erklärt ausdrücklich `snapshots_generated: 0` und
`growth_database_written: False`. Deshalb darf dieses Instrument nicht als
existierender 490.000-Zeilen-Writer oder Consumerproducer bezeichnet werden.

Die Task14-CPU-Zahlen sind abgeschlossene historische Instrumentenmessungen
(`task-14-sizing-result.md:114`), keine Laufzeitfreigabe der neuen C-Builder.
Weder Hochrechnen noch Übertragen dieser alten Kosten ersetzt die neue
1800-CPU-/3600-Gesamtsekundenrechnung einschließlich aller Versuche.

### Exakter Generatorplan ohne zusätzliche versteckte Receipts

Die vorhandene Tagesstruktur aus Task13 ist konkret verwendbar: sieben Tage,
je 70.000 neue Receipts, je 24 Consumer auf 14 Cutoff/Tour-Schlüsseln; zehn
Zweiergruppen plus vier Einzelconsumer. Die 168 nativen Statusreceipts, an die
die 168 neuen Prognosen gebunden werden, müssen **innerhalb** dieser 490.000
liegen. Wer zusätzlich 490.000 Größenzeilen erzeugt und anschließend je
Consumer einen neuen Capture persistiert, baut 490.168 statt 490.000.

Vor Beginn ist eine vollständige Baselineabfrage für die tatsächlichen
Zeitgrenzen, Tourstates und schon vorhandenen synthetischen Schlüssel nötig.
Neue Native-IDs müssen nachweislich kollisionsfrei sein; die feste Task14-
Präfixidee ist kein Ersatz für diesen Check. Zeitpunkte werden relativ zur
gebundenen Baseline festgelegt, mit `observed_at <= cutoff < scheduled_start`;
die alten absoluten September-11-Uhren des Task10-Helpers dürfen nicht kopiert
werden. Bestehende Baselineuhren und historische Codehashes bleiben unverändert.

Für ATP-heavy gehen die neuen 490.000 relevanten Statuszeilen nach ATP. Für den
gemischten Fall ist die bereits beschriebene neue Verteilung 35.000 ATP und
35.000 WTA pro Tag, zwölf Consumer und sieben neue Schlüssel je Tour/Tag
konkret. Alle 98 neuen Clockwerte können global verschieden angelegt werden,
damit 114 Cutoff/Tour-Schlüssel nicht versehentlich als 114 verschiedene
Timestampwerte ausgegeben werden, obwohl zwei Touren dieselbe Uhr benutzen.
Das zusätzliche `(event, cutoff, tour)`-Keyset muss separat vollständig geprüft
werden. Baseline-WTA-Historie bleibt auch im ATP-heavy-Fall vollständig erhalten.

Bursty-Ingestion benötigt eine explizite, vorab gebundene Empfangs-/
Einfügereihenfolge, ebenfalls mit eindeutigen Native-IDs und exakt denselben
Sollzählern. Gleiche Empfangsuhren sind zulässig, aber keine doppelten Receipts
zum Erreichen des Counts. Zeitgleichheit, Rückdatierungen und andere C6-
Negativfälle müssen mit tatsächlichen Ownerfolgen geprüft werden; ihre bloße
Aufnahme in eine Profilbezeichnung ist kein Differentialtest.

## 2. Tatsächlich vorhandene echte Erzeugungsowner

Der lokale alte Helper `.pytest_tmp/build_task10_consumer_growth.py:314` ist ein
brauchbarer **kleiner Referenzablauf**, kein neuer C-Worker. Er legt künstliche
native Fixtureantworten in den echten Capture-/Daily-/Predictorpfad und prüft
danach die tatsächlich gespeicherten Originale/Snapshots. Seine historischen
Baselines, Hashpins und G1/G2/G3-Inkremente gehören zu einem anderen Versuch;
sie erzeugen nicht die neuen drei vollständigen Sieben-Tage-Profile.

Der echte Pfad ist:

```text
normalize_tennis_status / capture_tennis_worker
  -> tatsächliches natives Fixture-Binding
  -> daily.scan_fixtures -> predict_match(original_capture=...)
  -> Capture.persist -> append_observation
  -> LiveWorker.finish:
       echte A1-State-/Native-Receipt-/Code-/Cutoff-Bindung
       -> Features + reale Effect-/Approval-Auswahl
       -> put_artifact(Original)
       -> compute_once(calculate_context_payload)
       -> erst danach Shadow-Referenz
```

Die besonders wichtigen Eigentumsstellen:

| Aufgabe | Bestehender Owner / Codezeile | Für C verwendbarer Anteil und Grenze |
| --- | --- | --- |
| Native Statusbytes | `context_sources/tennis_status.py:119` | Tatsächliche Normalisierung, keine selbst erfundene Hashhülle. Anschließend physischer Decoder und kalter Sourcevalidator `:246`. |
| Physische Speicherung | `context_observations.py:80`, `:102` | Exakte Neun-Feld-Dekodierung und bestehende Insert-/Collision-Semantik als Differentialreferenz; die Path-API öffnet eigene Legacy-Schreiber. |
| Wirkliche Prognose | `tennis/predict.py:113`, `:208` | `original_capture` liefert in demselben tatsächlichen Predictoraufruf Inputs und ungerundete Werte. `original_base()` allein ist kein Predictor. |
| Richtiger A1-State | `tennis/tour_state.py:156`, `tennis/live_context.py:218` | Pure Wrapperdekodierung plus Vergleich des tatsächlich benutzten State mit dem gespeicherten Artifact. Pathloader `load_tour_state()` hat zusätzliche Legacy-I/O. |
| Origin/Native-Bindung | `tennis/live_context.py:218` | Aktuellster eindeutiger Status, tatsächlicher Native-Receipt, State, Codebytes, Uhren und Same-call-Capture; nicht durch syntaktisch gültige Origin-JSON ersetzbar. |
| Originalpublikation | `tennis/live_context.py:287`, `model_artifacts.py:179` | Echte kanonische Envelope-/Created-at-/Collision-Semantik. Ein C-Schreiberadapter auf derselben Connection fehlt. |
| Fachlicher Snapshot | `context_transport.py:201`, `:233`, `:285` | Vorhandene Berechnung, Eingabebindung und Replay als unveränderte kleine Referenz; aktuell ganze `observation_refs`-Listen und Sets. |
| Tatsächliche Speicherung | `context_snapshots.py:117`, `tennis/live_context.py:299` | `compute_once` prüft die gespeicherten Bytes gegen die tatsächlichen aufgelösten Inputs; eigener Writer und Vollpayload. |

`scripts/tennis_daily.py:668` lädt Modelle, `:889` scannt Fixtures, `:961`
bindet den Originalcapture. Ein neuer geschlossener QA-Worker darf hier weder
den echten HTTP-Default benutzen noch einen fehlenden WTA-State, ein fehlendes
Effect oder eine Approval durch erfundene Werte ersetzen. Er muss die wirklich
vorhandenen Ownerbedingungen prüfen und die tatsächliche Ablehnung bewahren.
Aus „synthetische Größenfixture“ folgt keine native-to-state-Auflösung oder
fachliche Modellfreigabe; `native_state_identity='unresolved'` bleibt erhalten.

## 3. Vollständiges I/O-Inventar des betrachteten Pfads

| Pfad | Tatsächliche Schreib-/Temp-/Connectionwirkung | Aufnahme im neuen Workerplan |
| --- | --- | --- |
| `copying.copy_legacy`, `context_storage_v2/copying.py:122` | Bytekopie mit gehaltenen Source-/Output-FDs; **kein** SQLite-Backup. `:195` erzeugt zufälliges `context-copy-*`; `:252` öffnet eine zweite echte RO-SQLite-Verbindung ohne MEMORY-/Cache-/mmap-Profil. | Fester optionaler/erforderlicher Allocationpfad fehlt; der interne RO-Reader muss vor SQL konfiguriert werden. Kein C1-„kopiert“-Receipt berechtigt zu späterem unkontrolliertem Append. |
| `inventory_raw`, `inventory.py:204` | Keine Dateianlage, kein Commit, keine eigene Connection. Schema-, FK-, vollständige Typ-/Key-/Byteprüfung auf exakt gehaltenem Reader; `:146` geordnete SQL-Abfragen, `:162` BLOB-Streaming. | Jeder Caller muss seinen Reader vor der gehaltenen Transaktion mit effektivem MEMORY und den gebundenen Limits öffnen. `mode=ro` allein ist kein Ausschluss von TEMP-Speicherung. |
| `build_history`, `history.py:505` | Neuer `history.sqlite`-Main plus normales `-journal`; echte Main-Tabellen/Indizes. Freshwriter `:537`; nach Commit eigener RO-Reader `:627`. Fallback `:104` benutzt `mkdtemp`. | Global zwingend `owned_directory` verwenden. Main M und Journal M vorab reservieren. Aufbau-Writer und veröffentlichter RO-Reader sind unterschiedliche Connections; Quelle bleibt zusätzlich gehalten. |
| `tennis_features_streaming`, `tennis.py:628` | Neuer `features.sqlite`-Main plus Journal; Main-Staging-/Projektions-/Ref-Tabellen. Freshwriter `:685`; nach Commit neuer exakter RO-TrackedReader `:729`. | Feste Directory pro tatsächlich erzeugtem Ergebnis. Kein Löschen bei Close oder Fehler; Quelle und History müssen während aller Resultatiterationen leben. |
| Ref-/Snapshotparts, `refs.py:251`, `:429`; `snapshots.py:123`, `:285` | Caller-Main; gewöhnliche Main-Staging-Tabelle mit Sortierung und anschließendem SQL-DELETE (`refs.py:501`), Savepoints (`:163`). Keine eigene Connection, kein Commit oder Dateiunlink. | Nicht als externe TEMP-Datei missverstehen. B-Tree-/Sort-/Statement-/Rollbackbedarf gehört trotzdem in den gebundenen Writer/MEMORY-/AS-Pfad. |
| Sourceadapter, `snapshot_source.py:524` | Eine held RO-Source plus separater Calleroutput; vollständige Inventuren, readonly `blobopen`, äußeres Savepoint einschließlich Ledger-DDL und innere Rollbacks. | Output frisch und geschlossen vollständig. Unknown/oversized Header bleiben mit Rawabhängigkeit erfasst; bekanntes kaputtes Material stoppt den Batch. Kein File-Cleanup oder eigener Commit. |
| Legacy Receiptowner, `context_observations.py:38`, `:102`, `:169` | `_connect` delegiert zunächst an Artifact-Schemawriter und committet weiteres Schema. `append_observation` schreibt/committet erneut; selbst `observations_as_of` benutzt `_connect`. | Nicht direkt aus neuem Single-Main-Worker auf versiegelte Inputs aufrufen. Source-/Insertsemantik braucht einen expliziten C-Anschluss oder unveränderten kleinen Referenzlauf. |
| Legacy Artifacts/Models, `model_artifacts.py:131`, `:179`, `:240`, `:302`; `tennis/tour_state.py:175` | Allgemeines `sqlite3.connect`, Schema- und Transaktionscommits. Auch lesend benannte Artifact-/Manifest-/Tourloader laufen über `_connect`. | Echte vorhandene RO-in-connection-Funktionen `_load_artifact`/`_load_active` und pure Stateprüfung verwenden; ihre Auswahl/Berechtigung muss der neue Owner vollständig binden. |
| Live Datasetreader, `context_models/dataset.py:66` | Weitere plain RO-Verbindung, bewusst Live-WAL/SHM-fähig, ohne MEMORY; kein unveränderlicher Main-Image-Vertrag. | Nicht als already-profiled C-Inputreader ausgeben. Neue geschlossene Sourceverbindung benötigt passenden Readowner. |
| Capture/LiveWorker, `tennis_capture.py:21`, `:60`, `:81`; `live_context.py:250` | Pending-Liste/Refset, Persist im Contextmanager-`finally`; pro Receipt Legacywriter. Ganze Tourtuples pro Cutoff (`live_context.py:266`), ganze Refsets `:274`; Original-/Snapshot-Writer danach. | Große 490.000-Capture-Pendingliste und Vollhistorykopien dürfen nicht übernommen werden. Keine impliziten Persist-Writes aus einem abgebrochenen C-Batch. |
| Legacy Snapshotowner, `context_snapshots.py:62`, `:117` | Schema-Commit und weiterer Compute-Commit, Vollpayload; Compute-Callback ausdrücklich CPU-only. | Weder einen C-Feature-Builder noch Source-I/O in den Callback schmuggeln. |
| Shadow, `tennis/shadow.py:682`, `:749`, `:903` | Zusätzliche DB, `executescript`-Schema/Migrations-/Triggerpfad und eigene Commit-Lifetimes; bei vollständigem Dailyablauf zusätzliche Preis-/Statusdaten. | Echter alter Consumerhelper benötigt diesen zweiten Writer. Ein C-only-Original/Snapshot-Test darf ihn explizit auslassen, behauptet dann aber keine gesamte Daily-/Shadowintegration. |
| Task10-Referenzhelper, `.pytest_tmp/build_task10_consumer_growth.py:160`, `:228`, `:356` | Zusätzliche RO-Reader; `ATTACH baseline` mit `EXCEPT`-Abgleichen; zufällige `TemporaryDirectory` für `shadow.db`, automatische Löschung am Ende. | Nicht im neuen Worker unverändert starten. Feste Slots, neue begrenzte Vergleichsowner und erhaltene Fehl-/Shadowdateien erforderlich, falls dieser gesamte Pfad gewählt wird. |
| Alte Staging-/Sealerhelper, `.pytest_tmp/prepare_task10_growth.py:1`, `.pytest_tmp/seal_task10_growth_profile.py:1` | Root-Bytekopien, alte feste Quellen/Hashpins, zufälliges Stageverzeichnis beziehungsweise weitere vollständige Generationkopie; alte eigene Ressourcenannahmen. | Nur historische Referenz. Neue Raw-/Seal-/Archivkopien werden vollständig vorab reserviert; nicht unter aktuellem Guard laufen lassen, der Limitsetter ausschließt. |

Normaler DELETE-Journalabschluss kann die **eigene Journaldatei** durch SQLite
entfernen. Diese erwartete Dateiunlinkwirkung hebt keine Slotreservation auf.
Im aktuellen C-History-/Tenniscode gibt es keinen Produktpfad, der gescheiterte
Main-Artefakte oder ganze Arbeitsverzeichnisse entsorgt. Die großen Unterschiede
zum alten Task10-Helper dürfen in der globalen Bilanz nicht verschwinden.

## 4. Feste Dateiplätze und vorhandene Aufrufe

Folgende Namen sind ein **konkreter neuer Planvorschlag**, keine bereits
angelegten Dateien. `P` wird vor Admission vollständig zu `atp-heavy`, `mixed`
und `burst` expandiert; die Nummern werden zu einzelnen `FileSlot`-Instanzen
expandiert. `WorkspaceBudget` akzeptiert keine Wildcardreservation.

| Exakter relativer Planname / vorab expandierte Familie | Verwendung |
| --- | --- |
| `accounting/<identity-sha256>.jsonl` | Exakt vor Admission aus der gebundenen BudgetIdentity bestimmter Basename; `_native_file` bildet ihn mit `_hash(_identity(identity)) + ".jsonl"` (`context_preparation_budget.py:450`). Kein frei wählbares `preparation.jsonl`. |
| `baseline/legacy-copy.sqlite` | Vollständige unveränderte C1-Kopie der gebundenen Baseline; COPY-API braucht dafür noch den festen Pfadanschluss. |
| `baseline/snapshot-parts.sqlite`, `baseline/snapshot-parts.sqlite-journal` | C2-Transport und vollständige Source-Coverage für alle 31 alten Snapshotzeilen; Raw-only-Fälle weiter mit Rawquelle. |
| `profiles/P/receipts/receipts.sqlite`, `profiles/P/receipts/receipts.sqlite-journal` | Vorgeschlagener vollständiger Beleg-Corpus: unveränderte alte Rawobjekte plus 490.000 echte zusätzliche Receipts; Producer-/Writeranschluss fehlt. |
| `profiles/P/history-atp/history.sqlite`, `profiles/P/history-atp/history.sqlite-journal` | Eine maximale ATP-History innerhalb eines tatsächlich gehaltenen Lifecycles. |
| `profiles/P/history-wta/history.sqlite`, `profiles/P/history-wta/history.sqlite-journal` | Entsprechende WTA-History, wenn das Profil sie konsumiert; vollständige Raw-WTA-Coverage ist auch ohne diesen abgeleiteten Spool Pflicht. |
| `profiles/P/features-000/features.sqlite` bis `features-198/features.sqlite`, jeweils mit `-journal` | Feste Einzelresultatplätze für tatsächliche Consumer-Replays. Der vorhandene Builder unterstützt keinen neuen Batchwriter oder durch Dateinamen wiederbelebtes Ergebnis. |
| `profiles/P/consumer-inputs/000.json` bis `198.json` | Nur falls der gewählte Producer bounded Zwischenpakete benötigt: tatsächlich erzeugte/gebundene Inputs, ausdrücklich keine selbstautorisierenden Hashbeweise. Jeder Header muss in den bestehenden engen Adapterrahmen passen. |
| `profiles/P/new-consumers.sqlite`, `profiles/P/new-consumers.sqlite-journal` | Vorgeschlagener gemeinsamer C-nativer Original-/Snapshot-/Refstore für die 168 neuen Consumer, um identische Referenzblöcke wirklich innerhalb eines Stores teilen zu können. Owner fehlt. |
| `profiles/P/generation.json`, `reports/P.json` | Bounded vollständiges Verzeichnis und tatsächliche Mess-/Fehlerdaten, keine B-Freigabe. |
| `archives/atp-heavy.zip`, `archives/mixed.zip`, `archives/burst.zip` | Nur die tatsächlich im Restoreplan erforderlichen vollständigen Archive; eventuelle Restore-/Seal-Zieldateien müssen zusätzlich einzeln im Plan stehen. Ein Archivslot deckt keine entpackte zweite Kopie ab. |

Die optionale Zwischenpaketfamilie ist keine Pflicht zu 199 JSON-Ausgaben.
Wenn der kleine echte Integrationspfad ohne sie auskommt, werden diese Slots
vor der ersten Admission weggelassen, nicht nachträglich budgetbefreiend
gelöscht. Ebenso ist ein noch nicht geplanter Retry **nicht** durch obige
Familien abgedeckt: Jeder zugelassene weitere Versuch benötigt von Anfang an
separate vollständige Dateiplätze; sonst endet der Job beim ersten Fehler.

Keine großen Main-Caps sind hier erfunden. Je festem Builder heißt dessen
expliziter Cap `M`; der Plan reserviert Main `M` und Journal `M`, plus begründete
physische Rundungs-/Metadatenbelegung. Das vorhandene `SQLiteWriterPlan(M)`
liefert nur den logischen lokalen Teil. Ein einziger 4-GiB-Maincap für jeden
dieser Pfade wäre offensichtlich kein zulässiger 8-GiB-Gesamtplan.

Vorhandene Budgetanschlüsse:

```python
space = WorkspaceBudget(job_root, explicit_slots,
    external_inputs=(ExternalInput(sealed_baseline_path),),
    directory_metadata_bytes=explicit_metadata, limits=limits)
space.check_quiescent()
ticket = budget.reserve(portion_digest, reserved_cpu_ns)
# Native Owner bindet hier Closure, feste Schreibpfade und konkrete FSIZE.
result = run_single_process((sealed_worker, *fixed_args), uid=uid, gid=gid,
    cwd=owned_worker_directory, workspace_fd=held_directory_fd,
    file_size_bytes=explicit_file_cap, cpu_seconds=portion_cpu,
    wall_seconds=portion_wall)
# Erst tatsächliches terminales Ergebnis + vollständige Ownerkosten buchen.
space.check_quiescent()
```

Das ist Schnittstellenzusammensetzung, kein lauffähiger vorhandener globaler
Owner. `WorkspaceBudget` hat derzeit ein **festes** `active_input`-Flag je Slot
(`workspace_budget.py:35`, `:111`): keine API, die später durch Close/Delete
aktive Kapazität neu verteilt. Ein konservativer Plan darf alle möglichen
aktiven Slots zusammen reservieren. Passt diese Obermenge nicht, ist damit
noch kein kleinster tatsächlicher Spitzenbedarf bewiesen; ein phasenbezogener
vollständig gebundener Active-Set-Owner wäre zusätzliche fehlende Integration,
kein impliziter Gratiswechsel des existierenden Plans. Alle Archive,
Fehlversuche, Runtime-/Helperkopien und Restoreziele bleiben Q-Kosten.

Der identity-abgeleitete konkrete Journalname muss bereits vor `FileSlot`-
Admission vollständig feststehen. Die 4096-Dateislotgrenze
(`workspace_budget.py:29`) reicht für obige endliche Namensfamilien allein;
das beweist weder ihre Bytes noch einen vollständigen Gesamtplan aller übrigen
QA-/B-Artefakte. Der globale Owner muss vor jedem Start `remaining_reserved`
zusätzlich zu mindestens 4 GiB tatsächlich freiem Raum decken und während des
Laufs erneut beobachten. Keine Garantie gegen beliebige Fremdschreiber in
unbeobachteten Zeitabständen wird daraus abgeleitet.

## 5. Exakte Datenflussreihenfolge und die fehlenden Übergänge

### A. Baseline aufnehmen und alte Source-Coverage erzeugen

Root bindet die tatsächlich vorhandene vollständige Baseline, alle bisherigen
QA-/Backup-/Rollbackbelegungen sowie Code-/Runtimeidentitäten. Der native
Sourceowner öffnet **exakt** `TrackedConnection`, mit effektivem MEMORY vor
SQL-Workload, query-only/trusted-schema-off und gehaltenem Readtransaction.
`inventory_raw(source)` inventarisiert alle sieben zugelassenen Alt-Tabellen,
nicht nur die 31 sichtbaren Originale. Kein Vollpayload- oder NUL-Key-Cutoff
darf zum Verwerfen alter Rawobjekte führen.

Danach vollständige Bytekopie und `compare_raw` nach C1. Der aktuelle
`copy_legacy(...)` kann den Schritt semantisch, aber noch nicht mit dem
oben fest reservierten Pfad und seinem passend konfigurierten internen Reader.
Diese enge Lücke ist konkret vor globalem Einsatz zu schließen.

In einem separaten frischen Parts-Writer:

```python
writer = open_fresh_writer(parts_path, plan=SQLiteWriterPlan(parts_cap), limits=limits)
refs.create_schema(writer.connection)
snapshots.create_schema(writer.connection)
coverage = snapshot_source.adapt_source_snapshots(source, writer.connection,
    raw_inventory, limits=limits)
snapshot_source.validate_source_coverage(source, writer.connection, coverage, limits=limits)
writer.check_profile()
writer.commit_build()  # schließt den Writer wirklich
```

Die 31 alten Zeilen sind damit entweder transportiert oder ausdrücklich
Raw-abhängig erfasst; nicht alle sind ohne native vollständige Probe als
adaptierbar zu behaupten. `adapt_source_snapshots` verlangt frischen Output
und prüft das gesamte Source-/Output-Keyset (`snapshot_source.py:524`, `:582`).
Nachher einfach 168 neue Einträge in diesen Store zu schreiben, bricht diese
exakte Source-Coverage. Alter Source-Store und neue Consumerprodukte brauchen
getrennte Ownersets und ein zusätzliches vollständiges Generationsverzeichnis.

### B. Tatsächlichen Wachstumscorpus herstellen

Jede neue Zeile muss wirklich durch den Statusnormalizer, den realen physischen
Receiptdecoder und den kalten Sourcevertrag gehen. Anschließend tatsächlich
speichern, wieder vollständig lesen und Source-/Key-/Byteidentität prüfen.
Der Task14-Generator ist hierfür ein guter eng umrissener inhaltlicher Kern;
sein ByteCounter und seine extern übernommenen Lineagezahlen sind kein Writer.

Der aktuelle C3-Eingang verlangt **genau eine** vollständig validierte
`VerifiedReceiptMapping` auf genau einer `TrackedConnection`
(`history.py:224`, `context_runtime_inventory.py:61`, `:123`). Er akzeptiert
keine Baseline-plus-Growth-Pythonunion. Hier bestehen zwei reale technische
Möglichkeiten, von denen noch keine implementiert ist:

- Enger neuer privater Copy-and-append-Corpusowner: ausschließlich die in
  diesem Job neu exklusiv erzeugte vollständige Kopie beschreiben, alle alten
  Zeilen bytegleich erhalten und neue Receipts nur mit realer Insert-/
  Collision-Semantik ergänzen. Der kontrollierte Writerlifecycle für diese
  bereits gefüllte private Kopie muss eigens implementiert/geprüft werden.
  `open_fresh_writer` verweigert vorhandene Dateien und nichtleere Main-/
  Schema-Zustände (`sqlite_profile.py:417`, `:478`); ihn zu umgehen wäre falsch.
- Echte Fresh-Assembly oder ein neuer vollständiger Mehrquellen-Receiptowner:
  ersteres braucht eine **verlustfreie** begrenzte Übernahme sämtlicher alter
  SQL-Typen/Bytes, letzteres einen explizit neuen C3-Eingang. Beides ist mehr
  als eine `UNION`-Abfrage oder ein gefälschtes `VerifiedReceiptMapping`-Objekt.

Für den nächsten kleinen ausführbaren Producer ist die erste Variante der
engere Datenfluss: unveränderte Raw-Bytekopie plus klar katalogisierte Inserts,
kein generischer Altformat-Umschreiber. Sie ist eine neue Implementierungsarbeit
innerhalb C, **nicht** eine bereits vorhandene Fähigkeit des Freshprofils.
Normales DELETE/FULL bleibt erhalten. Zusätzliche Commit-/Wiederöffnungsphasen
sind nicht automatisch zugelassen: Falls 490.000 tatsächliche Normalisierungen
nicht in einen 300-CPU-Worker passen, braucht die Portionierung einen expliziten
kontrollierten Übergang oder einen wirklich vollständigen neuen Multi-Input-
Owner. Keine halbe DB als fertigen Corpus markieren oder für den nächsten
Prozess eine frühere Sourcevalidierung einfach behaupten.

Vor der ersten fachlichen Einschränkung müssen der fertige komplette Corpus,
alle Rawzeilen und die real zuständigen geschützten D2-Identitäten neu gebunden
sein. `protected_receipts=()` ist kein allgemeiner Ersatz für diesen Owner;
ungeöffnete Finals dürfen nicht für die Größenprobe geöffnet werden.

### C. Ganze Histories und 114 echte Prefixe

Nach abgeschlossenem Sourcebuild: Writer schließen, Source tatsächlich
versiegeln, vollständige neue `RawInventory` und tatsächliche vollständige
`VerifiedReceiptMapping.validate_all()` im gehaltenen Reader. Eine veränderte
Corpusdatei darf nicht die frühere komplette Baseline-Inventur weitertragen.

Vorhandener tatsächlicher Aufruf je benötigter Tour:

```python
maximum = build_history(receipts, directory=profile_root,
    owned_directory=profile_root / "history-atp", cutoff=maximum_atp_cutoff,
    tour="ATP", input_identity=sealed_corpus_sha256,
    main_cap_bytes=history_main_cap, limits=limits)
prefix = maximum.as_of(actual_cutoff)
```

`as_of` ist ein vollständig erneut geprüfter früherer Blick auf denselben
Spool, keine neue Datenbank (`history.py:387`). Tour, Cutoff, geordnete
Mitgliedschaft, kanonische Bytes und Inputidentität werden tatsächlich
gebunden. ATP und WTA werden nicht auf einen Tourteilfilter des Rawinventars
reduziert. Die 114 Cutoff/Tour-Schlüssel sind explizit zu enumerieren; ein
präparierter End-of-week-Blick ersetzt die 114 tatsächlichen Abfragen nicht.

**Konkreter Lifecycleblocker:** Task22 `task-22-global-budget-review.md:100`
schreibt einen neuen Mainpfad pro Worker, finalen Commit/Close und terminales
Reaping vor. `build_history` gibt aber nur eine laufzeitgebundene HistoryView
zurück (`history.py:299`); `tennis_features_streaming` verlangt exakt dieses
Objekt (`tennis.py:648`). Es existiert kein geprüfter `open_history`-Owner.
Ein Worker kann daher nicht einfach den Pfad drucken, enden und dem nächsten
Worker eine gültige HistoryView hinterlassen.

Vor Großausführung ist **konkret** entweder ein vollständiger Reopen-Owner zu
bauen oder ein endlicher sequenzieller Multi-Main-Worker gegenüber dem bisherigen
Task22-Katalog ausdrücklich zu implementieren und nativ zu messen. Bei letzterem
bleibt maximal ein beschreibbarer Main gleichzeitig offen; alle Main-/Journal-
Slots müssen vorab feststehen und das gesamte unveränderte 300-CPU-/AS-/RSS-
Budget des einen Workers gilt über sämtliche Builder. Das ist kein stiller
Profile-default. Die vorhandenen lokalen Integrationstests beweisen den
Liveobjektpfad innerhalb eines Pythonprozesses, nicht diesen nativen Übergang.

### D. Echte neue Originale und Snapshots statt Hashattrappen

Pro neuem Consumer: natives Fixture aus einer der reservierten neuen Receipts
binden; den richtigen tatsächlich gespeicherten Tourstate über den gehaltenen
RO-Owner laden; `predict_match(..., original_capture=...)` wirklich ausführen;
Origin mit den tatsächlich verwendeten Inputs, ungerundeten Werten, Native-
Receipt, State- und aktuellen echten Codeidentitäten bilden. Mit genau diesem
Base und diesem Cutoff den bestehenden C-Tennis-Builder ausführen:

```python
features = tennis_features_streaming(event, prefix, actual_base,
    cutoff=actual_cutoff, work_directory=profile_root,
    owned_directory=profile_root / "features-031",
    main_cap_bytes=feature_main_cap, limits=limits)
```

Der neue C-Consumerowner muss danach dieselbe Effect-/Approval-Auswahl und
fachliche Snapshotberechnung wie der echte alte Owner ausführen und dabei
observation refs blockweise in ihrer vollständigen kanonischen Reihenfolge
verarbeiten. Der vorhandene Legacy-Keypfad benutzt volle Listen/Sets
(`context_transport.py:111`, `:151`; `context_snapshots.py:26`). Für einen
großen C-Consumer ist daher ein äquivalenter **wirklicher** Streaming-Key-/
Payloadproducer erforderlich, mit byteexakten alten Differentials auf kleinen
zulässigen Daten. Es genügt nicht, frei erfundene erwartete Hashes an
`snapshots.put_snapshot_parts` zu übergeben; dessen Docstring bindet diese
Identitäten an einen gesonderten tatsächlichen vollständigen Sourceowner.

Die vorhandenen `features.iter_canonical_chunks()` und `iter_refs()` sind
nutzbar, solange Resultat, Prefix, Maximum und Sourcetransaktion leben.
`materialize(max_bytes=...)` hat weiterhin seine explizite höchstens 64-MiB-
Grenze (`tennis.py:556`). Der bekannte Snapshotadapter erlaubt außerdem nur
höchstens 1 MiB verbleibenden Nicht-Observation-Header (`snapshots.py:145`).
Ein übergroßer Featureheader darf nicht durch größere Blöcke still legitimiert
werden. Falls bounded Zwischenpakete benutzt werden, brauchen sie ihre echten
vollständigen Inputbindungen und Grenzen; ein JSON-Digest erzeugt keine
Provenienz oder B-Autorität.

Auch hier besteht eine echte Schreibreihenfolge: Während der Feature-Builder
seinen Main erstellt, darf nicht bereits der gemeinsame Consumerparts-Writer
offen sein. Alle Featureergebnisse unbesehen offen zu halten wäre wiederum
eine ungedeckte Summe von Readercaches/FDs. Entweder begrenzt vorbereiten,
schließen und über einen echten geprüften Reopen-/Stagingowner erneut binden,
oder den endlichen kontrollierten Ablauf entsprechend strukturieren. Ein
`StreamingTennisFeatures`-Objekt nach `close()` wird nicht durch einen noch
vorhandenen Dateipfad gültig (`tennis.py:440`, `:613`).

Ein ausgeschriebener Legacy-Gesamtbestand mit 199 großen Referenzarrays wäre
ein anderer konkret zu reservierender Pfad. Er ist keine kostenlose notwendige
Zwischenform der C2-Speicherung und darf nicht ungemessen zusätzlich angelegt
werden. Der engere C-Zielpfad behält die 31 originalen Raw-Snapshotbytes und
erzeugt 168 neue echte Consumerprodukte unmittelbar in der neuen begrenzten
Darstellung, mit vollständig rekonstruierbaren tatsächlichen kanonischen Bytes.
Genau dieser native Producer und seine Semantikdifferentials fehlen derzeit.

### E. Vollständige Generation abschließen, dann erst B

Das neue Gesamtverzeichnis muss die 31 vollständigen alten Sourcezeilen und
genau 168 neue echte Ownerprodukte **disjunkt** binden: nicht nur Count, sondern
Originalhash, Snapshotkey/-bytes, Source-/History-/Featurebindung, Tour/Cutoff,
alle erreichbaren Refblöcke und den vollständigen Rawbestand. Baseline-
Preservation ist ein alter Zeilen-Bytebeweis; `compare_raw(source, grown)`
allein kann nicht passen, weil die neue DB zusätzliche legitime Zeilen hat.
Ein ausdrücklicher vollständiger Altzeilen-plus-exakte-Neuzugänge-Vergleich
ist noch zu bauen. Gleiche Counts bei anderer Mitgliedschaft müssen scheitern.

Alle Writer schließen; alle betreffenden Worker tatsächlich reapen; vollständige
quieszente Slotreconciliation, echte Input-/Dateiseals und komplette Coverage
prüfen. Erst danach folgen der bereits freigegebene B-Closure-/Publisherpfad,
drei unabhängige vollständige finale Prüfungen mit jeweils höchstens 240 CPU-
und Wandsekunden, gesamter Restore einschließlich später neuer Receipts,
Produktvollsuite/Review und kontrollierter Rollout. Diese Schritte sind keine
Nebenwirkung von `RawInventory`, `CoverageDescriptor` oder dem nativen Guard.

## 6. Engster ausführbarer nächster Implementierungsschritt

**Ein kleines reales C-Corpus-/Consumer-Differential bauen, nicht den großen
Job sofort starten.** Vorhandene echte Testowner erzeugen eine vollständige
kleine Baseline; der neue eng begrenzte Corpusanschluss ergänzt z. B. zwei
gewöhnliche Statuszeilen plus das tatsächliche Fixture eines neuen Consumers
(insgesamt genau drei neue Receipts). Feste Main-/Journalpfade und echte
Same-call-Prediction; kein zusätzliches verstecktes Capture-Receipt.

Die konkrete Implementierungsreihenfolge dafür:

1. `copy_legacy` an festen `owned_directory`-Pfad und zuerst konfigurierten
   internen RO-TrackedReader anschließen. Bestehende vollständige C1-Byte-/
   Inode-/Inventoryprüfungen unverändert behalten.
2. Neuen kleinen private-copy-plus-receipt-Corpusowner mit explizitem Maincap,
   realer Normalisierung/Insert-/Collision-Semantik und vollständig geprüftem
   Close/Seal-Übergang implementieren. Keine vorhandene gefüllte DB durch
   `open_fresh_writer` einschleusen. Im selben engen Task festlegen, ob der
   spätere große Producer in eine Portion passt oder welchen tatsächlich
   geprüften Portionierungsanschluss er benötigt.
3. Den **einen** History→Tennis-Lifecycle für diese Probe ausführbar machen:
   echter Reopen-Owner oder explizit fester sequenzieller Zwei-Builderkatalog.
   Dabei die vorhandenen exakten Typ-/Source-/Lifetimetests unverändert halten.
4. Für diesen einen wirklichen Consumer die C-native Ownerbrücke schreiben
   und gegen den unveränderten kleinen Legacy-Owner vollständig vergleichen:
   ausgewählte Reihenfolge, Featurebytes/-refs, tatsächliches Original,
   Snapshotkey, Rohbytes, Payload-Digest und tatsächliche Ablehnungen.

Notwendige kleine Gegenfälle sind Missing/Extra/Same-count-other-member,
Sourcewechsel zwischen Phasen, Abbruch nach Corpus-Commit vor Gesamtmanifest,
SQLITE_FULL im neuen Main oder Journalpfad, Snapshotfehler nach tatsächlicher
Prediction und zusätzliche Native-ID-Kollision. Jede entstandene Datei bleibt
im festen Gesamtplan; kein nachträgliches „Cleanup bestanden“.

Erst die tatsächlich instrumentierte Durchführung dieser **echten** kleinen
Kette unter dem nativen Guard ist die Grundlage für begrenzte Mengenportionen.
Die weitergehenden 490.000/199/114-Profile behalten exakt ihren Umfang; diese
kleine Vorprobe wird nicht als verkleinerte Abnahme ausgegeben. Eine gemessene
Grenzüberschreitung beendet den betreffenden Job innerhalb der freigegebenen
Hülle, ohne neue Nutzerfreigabe oder Ressourcenerhöhung zu erfinden.

## 7. Reichweite der kleinen Nativeprobe

Die hier lokal gelesenen Berichte Task33 und Task36 beschreiben vorbereitete
separate Native-Diagnose-/Sealerbytes und zu ihrem Berichtsstand noch keinen
ausgeführten Korpus. Kurz vor Abschluss meldete Root inzwischen einen echten
ersten nativen Diagnoselauf: Der positive Worker erzeugte eine 8192-Byte-SQLite-
Datei; der Supervisor traf anschließend eine terminale `/proc`-Race mit
fehlendem VmHWM bei noch nicht als Z gelesenem Status. Root korrigiert diesen
engen Übergang. Dies ist eine Root-Mitteilung, keine eigene VPS-Prüfung und
kein erfolgreicher vollständiger Nativeprobeabschluss dieses Tasks. Die neue
native Evidenz gehört in Roots Bericht und ersetzt die oben beschriebenen
Producerübergänge nicht.

Besonders wichtig: Die positive Task33-SQLite-Miniprobe benutzt
MEMORY-Journaling und ist ausdrücklich **kein** nativer DELETE/FULL-
FreshSQLiteWriter-Test. Ihre erfolgreiche Numerik-/SQLite-/Guardkompatibilität
würde das native Task27-/Task35-Profil und den vollständigen C-Datenfluss nicht
mitmessen (`task-33-native-preparation-probe.md`, Abschnitt „Genau sechs native
Teilproben“). Das ist ein klarer nächster echter Messgegenstand, keine neue
abstrakte Isolationsforderung.

## 8. Lesestand und Abschluss

Vollständig beziehungsweise für diesen Pfad gezielt gelesen: freigegebener
C-Spec/Gesamtintegrationsplan, Task13/14 samt Originalinstrument, Task22/27/32
und Task35, aktuelle C-Builder und Raw-/Ref-/Snapshot-/Sourceadapter, Budget-
APIs, Task33/36, tatsächlicher alter Consumerhelper und die oben bezeichneten
Produktowner. Die Codezeilen gelten für den lokal vorliegenden Stand; spätere
Owneränderungen benötigen neue Bindung. Keine historischen grünen Tests werden
als Testausführung dieses reinen Read-only-Tasks ausgegeben.

Abschluss: **Konkreter Implementierungsrückstand rekonstruiert, keine globale
C- oder B-Kapazitätsabnahme.** Kein fehlendes Nutzer-„ja“, kein behaupteter
490.000-Zeilen-Writer und kein vermeintlich schon fertiger Consumerproducer.
