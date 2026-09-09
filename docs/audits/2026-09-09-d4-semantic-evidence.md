# D4: gespeicherte D1/D2-Nachweise im unverändernden Restore-Prüfer

9. September 2026. Eigener Branch `codex/kontext-d4-semantic-20260909`,
Basis `0840c35947c035b0efa306a986a8d775acf2528c`. Ausschließlich lokale,
temporäre SQLite-Dateien. Kein Providerabruf, keine produktive Datenbank,
kein Push, Deployment oder Aktivieren eines Modells.

## Ergebnis und Grenzen

Der bestehende D4-Prüfer kann nun die tatsächlich implementierten D1/D2-
Artefakte auflösen und gespeicherte Berechnungsberichte durch deren originale
Quellen-, Fall-, Fit-, Opening- und Evaluatorpfade erneut prüfen. Er untersucht
auch nicht aktive Artefakte. Freie Ergebnisarrays, Hashwerte oder gespeicherte
Freigabe-Flags ersetzen diesen Replay nicht.

Dieses neue Paket wurde lokal unter Windows geprüft. Der frühere Linux-
Nachweis des unveränderten D4-Dateirahmens ist kein frischer Linux-Nachweis
dieser neuen D1/D2-Replays. Plattform-/Integrationsabnahme und spätere
Produktivfreigabe bleiben ausdrücklich getrennt.

Das ist keine neue empirische Abnahme. Die ausführbaren positiven Datenfälle
verwenden synthetische Sportdaten mit dem tatsächlichen A1/B1/D1/D2-
Datenbankpfad. Drei synthetische Finalspiele reichen ausdrücklich nicht für
eine Freigabe; in sämtlichen solchen positiven Fällen entstehen **0 Approvals**.
Ein zusätzlich gespeicherter, formal passender Approval-Versuch wird vom
tatsächlichen `verify_approval` abgelehnt. Eine positive Abnahme eines echten
ausreichenden empirischen Korpus wurde in diesem Paket nicht behauptet.

`empirical_approval_verified` bleibt immer `false`. Die additiven Listen unter
`d2_verified` benennen tatsächlich wiedergeprüfte Experiment-, Dataset-, Fit-,
Fall-, Evaluations- und gegebenenfalls Approval-Identitäten. Eine verifizierte
Experiment-/Trainingsphase behauptet nicht, dass ein ungeöffnetes Finalinventar
bereits geprüft wurde. Jede verbleibende Begrenzung hält den Gesamtstatus auf
`transport_only` und den vorhandenen CLI-Exitcode auf 2. `structural` heißt
bekannte Speicher-/Berechnungskonsistenz, nicht profitable Wetten oder Livefreigabe.

## Vorab genehmigte Controllerentscheidungen

1. Tatsächliche bekannte schema/version-Ansprüche müssen geprüft werden;
   widersprüchliche Claims sind typisierte Fehler. Wirklich unbekannte
   Legacy-/Zukunftstransporte bleiben unvollständig und können einen
   verknüpften Approval nicht zertifizieren. Fehlende Pflichtreferenzen werden
   nicht in harmlose Unvollständigkeit umetikettiert.
2. Verwaiste oder vor dem Freeze erzeugte Artefakte dürfen nicht mit einer
   erfundenen Konfiguration oder einem geratenen Quellenpool ergänzt werden.
   Ohne ihren originalen auflösbaren Kontext bleibt der owning Replay offen.
   Bekannte, konfigurationsunabhängige Typ-/Partitions-/Selektionswidersprüche
   bleiben gleichwohl Fehler.
3. Vor einem tatsächlichen passenden Whole-Inventory-Opening werden finale
   Ergebnisquellkörper nicht durch einen generischen B1-Vorschritt geöffnet.
   Die Schutzmenge folgt ausschließlich aus validierten eingefrorenen
   Experimentinventaren und tatsächlichen Opening-Artefakten, nicht aus
   freien event/status-Flags. Physische Bytes, SHA256, SQLite-Typen und die
   vorhandenen äußeren Receipt-Indizes bleiben vorher vollständig geprüft.
4. Sobald das tatsächliche Opening legitim aufgelöst ist, werden genau diese
   Quellkörper durch die owning Fall-/Outcome-Validatoren geprüft. Bei
   ungeklärter Openingfähigkeit bleibt `d2-final-source-replay-not-opened`;
   keine pauschale Ausnahme anderer B1-Dekoder.
5. D3 verwendet eine explizite Liste geprüfter `(family, feature_version)`-
   Fähigkeiten. Unbekannte vollständige Transporte behalten Hash-/Referenz-
   und Eingabeschlüsselprüfung, aber erhalten keine numerische Prüfbehauptung.
   Eine bekannte fehlerhafte Fähigkeit fällt nicht still in unbekannt zurück.
   Auch ein bekannter numerisch wiederholter D3-Transport ist **noch kein**
   owning Receipt-/Feature-Replay.

## Implementierung

`context_runtime_semantics.py` ist ein ausschließlich lesender Zusatz zum
vorhandenen caller-held SQLite-Transaktionspfad. Verwendet werden die echten
unveränderten owning Validatoren und Resolver, unter anderem:

- `_load_experiment` und `_openings`: ursprüngliche A1-Erstellzeiten, ganze
  kanonische Hypothesen-/Eventinventare, native Map, originale Öffnung und
  Überschneidungsregeln. Jede A1-Identität wurde vor dem Kinddispatch geprüft.
- `_physical_receipt_preflight`: tatsächliche BLOB-Hashes und äußere
  SQLite-/JSON-Indizes vor jedem notwendigen Quellenkörper-Dekoder.
- `validate_identity_map` / `resolve_identity_map`, `_recipe`, `case_header`,
  `validate_dataset`, `validate_fit_result`, `resolve_case`,
  `validate_resolved_case` und `_prepare`: echte native Bindungen, originale
  Basisreplays und Quellrevisionen, vollständige Train-/Tune-Fits mit allen
  fünf Alphas, originale Casepartition und Cutoffs.
- `verify_evaluation` und `verify_approval`: gespeicherter Bericht wird neu aus
  denselben owning Quellen und dem eingefrorenen Inventar berechnet; keine
  verkleinerte BH-Familie und keine freigegebenen freien Testarrays.

Ein nicht ausgewählter zusätzlicher Fit wird ebenfalls erneut gerechnet,
wenn seine ursprüngliche Konfiguration und ein eindeutig zugeordneter
Receiptpool vorliegen. Ohne diese Belege bleibt eine konkrete
`d1-fit-owning-replay-unavailable`-Begrenzung. Die eng getrennten
Orphan-Headerprüfungen übernehmen nur unabhängig von der fehlenden Config
bekannte v1-Invarianten; weder Feature-Scope noch Alpha-Grid werden geraten.

Bei einer zusätzlichen unbekannten Openingversion autorisiert der Prüfer
keine finale Auswertung. Dennoch werden bekannte v1-Opening-Claims auf ihre
Originalinventare, Maps und Uhren geprüft: die unbekannte Fähigkeit darf
einen bereits erkennbar beschädigten bekannten Claim nicht verdecken.

Eine tatsächlich bekannte Evaluation prüft auch dann ihre geschlossene
Kopfstruktur, Implementation-Hashes und Referenzen, wenn die finale vollständige
Openingfähigkeit fehlt. Der fehlende Replay wird weiterhin ausdrücklich
ausgegeben und niemals als erfolgreich zertifiziert.

In `context_runtime.py` bleiben die bisherigen OS-/SQLite-/Rollbackgrenzen
unverändert: reine Lesedeskriptoren, maximal 64 MiB, vollständiges DELETE-
Datenbankbild, ausschließlich `:memory:`/`deserialize`, `query_only`,
`temp_store=MEMORY`, erneute Identitäts-/Metadaten-/Companionprüfung,
keine SQLite-Verbindung auf den Quellpfad. A1-Manifeste, atomarer CAS-Rollback,
Geld-/Ticketdaten und Tourcodec wurden nicht verändert.
Zusätzlich wurden die ASTs von 14 bestehenden Pfad-/Deskriptor-/SQLite-/
Manifest-/Rollback-/Verifikationsrahmenfunktionen direkt gegen das Git-Original
`0840c359...` verglichen: `UNCHANGED_OS_SQLITE_ROLLBACK_FUNCTIONS=14`.

### Genau bekannte D3-Transportfähigkeiten dieser Basis

| Familie | Featureversion |
| --- | --- |
| `football:goals:90min` | `football-roster-components-v2` |
| `tennis:winner` | `tennis-performed-load-v2` |
| `tennis:serve` | `tennis-performed-load-v2` |
| `basketball:margin:including_ot` | `basketball-rotation-observed-load-v1` |

Die gespeicherten äußeren Inputs und alle tatsächlichen A1-Artefaktumschläge
werden exakt gebunden. Das echte `replay_context_payload` prüft die bekannten
numerischen Ergebnisse; danach bleibt stets
`d3-owning-source-feature-replay-unavailable`. Eine unbekannte Familie/Version
meldet stattdessen `d3-owning-family-replay-unavailable` und durchläuft keine
unpassende Rechenformel. Manipulierte Keys, fehlende Receipts, falsche
Artefaktbytes und unzulässige Versionstypen bleiben davor Fehler.

Die positiven eigenen D3-Proben benutzen native-shaped synthetische Tennis-
Inputs und ausdrücklich **nicht qualifizierte** lokale Workload-Receipts.
Sie belegen Rechen-/Transportkonsistenz und gerade keine Quellenqualität.
Spätere C3-/C4-/v3-Routen dieser Familien gehören nicht automatisch zu dieser
Liste. Deren Erweiterung und die vollständige D3-Quellen-/Feature-Bindung
bleiben getrennte Controller-/Integrationsaufgaben.

## TDD und tatsächlich ausgeführte Nachweise

Interpreter in allen Läufen:
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`;
immer `-B -m pytest -q -p no:cacheprovider` mit neuer eigener `--basetemp`.

| Lauf / eigene temporäre Kennung | Ergebnis |
| --- | --- |
| `d4-semantic-red-01`, ursprünglicher Runtime-Code | 7 fehlgeschlagen; echte D2-Semantik fehlte, rehashte inaktive Claims wurden nicht abgelehnt |
| `d4-transport-red-01` | 1 fehlgeschlagen, 6 bestanden; eigener Adapter hatte einen zusätzlichen `digest` im B3-Effektumschlag |
| `d4-transport-green-01` | 7 bestanden nach exakt passendem owning Effektumschlag |
| `d4-semantic-green-01` | 100 bestanden, 3 erwartete Plattformskips; einschließlich aller ursprünglichen 96 D4-Fälle |
| `d4-semantic-shape-01` | 15 bestanden; bekannte/ungültige und wirklich unbekannte Schemata |
| `d4-transport-all-02` | 14 bestanden; bekannte Replays und unbekannte Fähigkeitsgrenzen |
| `d4-semantic-all-02` | 38 bestanden, 1 Test-Harnessfehler; zusätzliches legales Memory-`temp`-Schema war im Test zu eng ausgeschlossen |
| `d4-unknown-opening-red-01` | 3 fehlgeschlagen; unbekannte Zusatzversion verdeckte beschädigte bekannte Inventory-/Map-/Clock-Claims |
| `d4-semantic-own-green-03` | 55 bestanden; einschließlich gezielter Korrektur und korrigiertem reinen Memory-Connection-Test |
| `d4-semantic-archive-01` | 2 bestanden; gültiges bekanntes plus unbekanntes Opening sowie wirklicher Zwei-Hypothesen-WAL-Stage-/ZIP-/Restore |
| `d4-orphan-fit-red-01` | 7 fehlgeschlagen; bekannte interne Widersprüche bei fehlender ursprünglicher Config |
| `d4-semantic-regression-final-01`, finale breite Regression | 675 bestanden, 8 erwartete Skips, 32 Untertests; 340,08 s |
| `d4-semantic-full-final-01`, vollständige Suite | 4.533 bestanden, 18 erwartete Skips, 97 Untertests; 1.080,69 s |

Finale breite Regression (`--basetemp=.pytest_tmp/d4-semantic-regression-final-01`):

```text
tests/test_context_runtime_semantics.py tests/test_context_runtime_transport.py
tests/test_context_runtime_backup.py tests/test_model_artifacts.py
tests/test_context_observations.py tests/test_context_snapshots.py
tests/test_tennis_state_codec.py tests/test_runtime_paths.py
tests/test_challenge_15k.py tests/test_backup_stage.py
tests/test_backup_stage_e2e.py tests/test_backup_stage_archive.py
```

Vollsuite: `pytest -q -p no:cacheprovider
--basetemp=.pytest_tmp/d4-semantic-full-final-01
--junitxml=.pytest_tmp/d4-semantic-full-final-01.xml`.
Beide Läufe benutzen identische eingefrorene vier Code-/Testdateien.
Der tatsächliche JUnit-Nachweis enthält 4.648 Einträge einschließlich
18 Skips und 97 Untertests, **0 Fehler und 0 Fehlschläge**. SHA256:
`f44704715461a80614b3b03caf4635dfe212d9e0760be88eebef9ec32ee31a97`.

Der Memory-Connection-Test verlangt weiterhin eine aktive Transaktion,
`query_only=1`, `temp_store=2`, ausschließlich `main`/`temp` mit leeren
Dateinamen und eine tatsächlich abgelehnte DELETE-Anweisung. Es wurde keine
produktive SQLite-Grenze für das Testfixture aufgeweicht.

Beim ersten RED-Lauf war der eigene spätere Decoder-Guard noch falsch
indiziert. Das wird nicht rückwirkend als Beweis für diesen Guard ausgegeben.
Ein separater historischer Gegenlauf gegen die unveränderten Bytes von
`0840c359...:context_runtime.py` bestätigte anschließend exakt einen
ungeöffneten Finalkörper-Dekoderaufruf bei unveränderter Quelldatenbank:
`.pytest_tmp/d4-semantic-baseline-body-probe.py`. Der tatsächliche B1-SELECT
ist Receipt/Content/Event/Clock/Revision/Source/Subject/Kind/BLOB; die
permanenten Guards prüfen Event an Index 2 und Kind an Index 7.
SHA256 der unverändert erhaltenen historischen Diagnose:
`910d18fa4f7bcb9463ff0c70815edff847b528cdbd20b29006007f65dc0f7a9b`.

### Echter Backup-/Restore-Gegenlauf

`test_actual_two_hypothesis_d2_wal_stage_archive_restore_preserves_losers`
friert in einem eigenen lokalen Fixture zwei Hypothesen vor dem Öffnen ein,
darunter die ausdrücklich im BH-Inventar erhaltene Baselinekontrolle mit
`q=1`. Die tatsächliche Evaluation läuft unter einem gehaltenen älteren
SQLite-Read-Snapshot in WAL; ungecheckpointete Frames und unveränderte
Hauptdatei werden direkt nachgewiesen. Der unveränderte Stagehelper sichert
über den Online-Backup-Pfad, der unveränderte Backuphelper erstellt und
prüft das ZIP. Nur das eine zuvor geprüfte feste Member wird in einen neuen
privaten 0700/0600-Restorepfad gelesen, kein `extractall` und kein Überschreiben.

Nach Restore stimmen alle A1-Artefakt- und B1-Content-/Receiptzeilen exakt.
Der Bericht wird durch den echten Evaluator wiedergeprüft; Quelldateibytes
und companionfreie Verzeichnisbelegung bleiben unverändert. Ein zusätzlich
rehashter inaktiver Bericht ohne die Kontrollhypothese wird abgelehnt.
Vorhandene Tour-/B3-/Rollback-/15K-Regressionen bleiben unverändert separat
ausgeführt. Der Stagehelper selbst wurde nicht editiert.

## Eingefrorene Quellidentitäten

SHA256 der vier Code-/Testdateien des Pakets:

```text
a1d8723479d35294d4acef2e7858ae36645085afd331a5317d7dab5836383bc4  context_runtime.py
ea4f5b1960c8e9b009aa65494944a07617fbdd68a3369d7d417b04edb905adc1  context_runtime_semantics.py
ef4e0a00784e854e0acd007ff796a924b668fb2f93387a4859d0fa2a290fb5f2  tests/test_context_runtime_semantics.py
b6fbfe4a2b61cd7fb6f6735ebddd630c4201793f2de6ed59af1b2e4bf729297c  tests/test_context_runtime_transport.py
```

Unveränderte wichtige Abhängigkeiten:

```text
1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026  scripts/stage_runtime_databases.py
71dc37951bed4e6fc576e842829f7b0af08b692243bd6c353423237c9cddef62  tests/test_context_runtime_backup.py
3b87304d86684bb0cae8e72b9cae6fe7f3fc5610e770b84b3a0568bb2b3e59e7  context_models/dataset.py
080bcf30cf48b14dafdb045611414cf9d82ce975d93ea951022fb99c3bd17ce1  context_models/experiments.py
fb7e0d581f45144c1f1b0456f828e58a7cb16ac124c1ec9683dc4f2b43fae32d  context_models/replay.py
fcf953d738b7f1249c68b65532f55142c8ad77e3b4a6de861c15bcab87efca6a  context_models/training.py
38e876e0e82f03290e3fbd76a72239893237ed70865987a63c86f639ac6f89ce  context_models/training_contracts.py
b9fbb815f2cbccbb14055a23fa3da97d32dbec198053fca98fbb805a3607baa1  context_models/evaluator.py
887090c03a7107eb16946dd214a5ae7235b4e6cc3ea714a462c5c0e2f1ffd0c3  context_models/activation.py
e61943527fd764d1017f3c78ae09cd5d1d8bc67db44e19961517bc4b329e6786  context_sources/outcomes.py
feff952c7f8a7d769d7a20e25b9d164f9dd0d9470446b9d647e9aebb52e187ce  context_transport.py
```

Der historische Ausgangs-Hash von `context_runtime.py` ist
`c470d35fd60e413c8371aa22baa9097dedc2385a5eee5644ca56e0930b6c10c2`.
Die übrigen owning D1/D2-/Transportdateien bleiben auf der angegebenen Basis.
Die unabhängige Prüfung dieses neuen D4-Pakets und seine Zusammenführung mit
späteren Root-Erweiterungen stehen nach dem eigenen Freeze noch aus.

## F1: unabhängige Nachprüfung und enge physische Referenzkorrektur

Der vorstehende ursprüngliche Freeze wurde als `b56da33d7b4c447e6a50ff7ec600efc3b7b49f5f`
committed. Roots vollständiger unabhängiger Bericht wurde gelesen und sein
P2-Befund vor der Korrektur selbst auf genau diesen Sourcebytes reproduziert.
Die beiden Fehler waren echte fehlende `ArtifactIntegrityError`-Ablehnungen,
keine Fixture-/Importfehler. Ohne ursprüngliche Experimentkonfiguration blieb
ein sonst gültiger bekannter D1-Fall zu Recht unvollständig; dabei wurden aber
explizite FeatureVector-Receiptverweise nicht auf tatsächliches Vorhandensein
und rechtzeitigen Empfang geprüft. Sowohl ein nicht existierender Hash als
auch ein real gespeicherter erst nach der Entscheidung empfangener Datensatz
wurden fälschlich lediglich als `transport_only` behandelt.

Das war keine empirische Freigabeumgehung: der bisherige Gesamtbericht war
bereits unvollständig und ohne verifizierte Approvals. Es war gleichwohl eine
konkrete Verletzung der versprochenen Referenzintegrität. Root hat ausschließlich
die folgende Korrektur freigegeben:

- `_case_shape` prüft nun **alle** expliziten eindeutigen FeatureVector-Refs
  mit dem bestehenden `_physical_ref` gegen `features.cutoff`. Die bereits
  validierte ursprüngliche Basis besitzt exakt denselben Cutoff; die spätere
  Fall-/Artefakterstellzeit darf ihn nicht ersetzen.
- Der Zustand `available`, `missing`, `stale`, `conflicting` oder
  `not_applicable` erlaubt niemals einen unmöglichen expliziten Quellenverweis.
  Das ist keine Änderung an der Auswahl oder Bewertung dieser Zustände.
- Der bestehende physische äußere Receiptcheck benötigt weder eine erratene
  Konfiguration noch Zugriff auf finale Quellkörper. Es wird kein Quellenkind,
  Eventgleichheit historischer Inputs, Archivbeweis oder Modellreplay erfunden.
  Die tatsächliche unterstützte D1-Datenklasse bleibt `prospective`.
- Tatsächlich rechtzeitig empfangene verwaiste Daten bleiben ausdrücklich
  unvollständig. `received_at == cutoff` ist zulässig, `cutoff + 1µs` nicht.
  Fehlende owning Konfiguration bleibt ein offener Replay, kein neu verifizierter
  Fall und keine neue Fähigkeit/Freigabe.

Die einzige semantisch geänderte Funktion ist `_case_shape`, per AST-Vergleich
gegen b56da33 belegt. Der Produktionsdiff besteht aus zwei Rechenzeilen und
drei begrenzenden Kommentarzeilen. `context_runtime.py`, Dataset/Evaluator,
Training-Case-/B1-Verträge und insbesondere der gepinnte Stagehelper sind
roh bytegleich. Die bestehende readonly Deskriptor-/64MiB-/DELETE-/Memory-/CAS-
Grenze wurde nicht geändert.

### Unveränderte unabhängige Beweise

Beide Dateien bleiben exakt auf den ursprünglich abgelehnten Reviewbytes:

```text
c2972259269e8e119e7021ce7307ced0e5bc110fede03c609705bd8c22ddb0bf  .pytest_tmp/d4-root-independent-20260909/test_independent_d4.py
7dae71f5c3bfb83a88b16ea3164bdcbc7968056a2f11a6f3d61625ce81a64342  .pytest_tmp/d4-root-independent-20260909/REVIEW.md
```

Der negative Originalbericht wurde nicht überschrieben oder nachträglich als
grün bezeichnet. Neue permanente Tests ergänzen ihn: je fünf Featurezustände
mit fehlendem beziehungsweise vorhandenem zukünftigem Receipt; mehr als ein
Ref und nicht nur die erste Featureposition; erster/letzter Fall mit tatsächlichen
neuen B1-Receipts an `cutoff - 1µs`, `cutoff`, `cutoff + 1µs`; ein realer noch
ungeöffneter Final-Outcome-Receipt darf durch den Guard nicht dekodiert werden.
Alle DBs sind lokale synthetische native-shaped SQLite-Mechanikfixtures.

### F1-Testbelege

| Lauf | Ergebnis |
| --- | --- |
| `d4-f1-original-red-20260909-01` | 2 fehlgeschlagen, 11 bestanden, 87,55s; unveränderte 13 Rootproben |
| `d4-f1-permanent-red-20260909-01` | 13 fehlgeschlagen, 4 bestanden, 50 abgewählt, 91,74s; alle 17 neuen permanenten Fälle vor Sourceänderung |
| `d4-f1-regression-green-20260909-01` | 705 bestanden, 8 erwartete Plattform-Skips, 32 Untertests bestanden, 451,72s; alle 17 neuen und 13 unveränderten Rootfälle grün |

RED-JUnit-Hashes:

```text
0f1bad9bb69bfcfebff0edcebf956d5b5ac6350513796c6a5de4170eccc2a9ea  .pytest_tmp/d4-f1-original-red-20260909-01.xml
806185141ad186dfa46d7225825e0b329162c12a6e99520da45f5a76473bfd09  .pytest_tmp/d4-f1-permanent-red-20260909-01.xml
```

GREEN-JUnit: `.pytest_tmp/d4-f1-regression-green-20260909-01.xml`, SHA256
`a983b788a1a4f75467664f4128ba1070f14eb0274663ae821322fd569491c224`.
Die XML-Auswertung bestätigt 713 Testcaseeinträge, 8 Skips, 0 Fehler und
0 Fehlschläge; die 13 unabhängigen und 17 neuen permanenten Fälle sind darin
jeweils ausdrücklich ohne Fehlschlag/Skip vorhanden. Die Untertests sind
zusätzlich durch das oben genannte tatsächliche pytest-Abschlussresultat belegt.

Fokus-/Regression benutzt die oben genannten zwölf D4/A1/B1/B3/Tour/15K/
Stage-Testdateien plus die unveränderte unabhängige Reprodatei, identischen
Qualitäts-Python, `-B -m pytest -q --tb=short -p no:cacheprovider`, jeweils einen
neuen `--basetemp` und eigenen JUnit-Nachweis. Keine Quelländerung während
dieses GREEN-Laufs. Der frühere 4.533er-Gesamtlauf gilt ausdrücklich für b56da33
vor F1; er wird nicht als neuer vollständiger Suite-Nachweis umetikettiert.
Unabhängige erneute Abnahme, neuere Familienintegration, frische Linux-QA und
der separat nur entworfene vertrauenswürdige Updater-Hook bleiben Rootaufgaben.

Neue eingefrorene Code-/Testbytes:

```text
4964cc4882ce86a3c49f927b2877f3abfca461adcc73103cd60300c38d6eae29  context_runtime_semantics.py
caea6593694f07a1c20a50a81b2a9feecdad8defde8b178f34caa101c72bbca5  tests/test_context_runtime_semantics.py
```
