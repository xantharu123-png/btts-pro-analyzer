# Task 44 — echte Receipt-Append-Operation in gehaltener C-Transaktion

Stand: 12. September 2026. Begrenzter Implementierungsauftrag von Root innerhalb
des ausdrücklich freigegebenen C. Geändert wurden ausschließlich die neue
`context_storage_v2/receipt_append.py`, die neue
`tests/test_context_storage_receipt_append.py` und dieser Bericht. Keine alten
Owner-/Produktdateien, kein Git, SSH, Server oder nativer Root-Prozess.

## Ergebnis und API

`append_observation_in_connection(connection, record, *, observed_at) -> str`
ist implementiert. Sie übernimmt die tatsächliche unveränderte fachliche
Append-Semantik, nicht nur das Berechnen eines plausiblen Receipthashs:

1. Echte `normalize_observation`-Prüfung und UTC-Mikrosekunden-Normalisierung.
2. Dieselben tatsächlichen kanonischen Contentbytes, Content- und Receipthashes.
3. `INSERT OR IGNORE` in `main.context_contents`; tatsächlicher BLOB-Readback
   und exakter Bytevergleich, keine Reparatur einer vorhandenen Kollision.
4. `INSERT OR IGNORE` in `main.context_observations`; tatsächliche physische
   Neun-Feld-Zeile aus Main lesen und durch den bestehenden `_decode_receipt`
   gegen den vollständig erwarteten Inhalt einschließlich aller Indizes prüfen.
5. Erst nach unveränderter Transaktion und geschlossenem eigenen Cursor den
   gewöhnlichen Receiptdigest zurückgeben. Der Caller entscheidet über den
   späteren einzigen Build-Commit; diese Operation committet nicht.

Exakt `TrackedConnection`, eine bereits aktive explizite Transaktion,
`isolation_level=None`, Legacy-Transaktionssteuerung und normale
`row_factory=None`/`text_factory=str` sind erforderlich. Generation und diese
Eigenschaften werden vor/nach Normalisierung, SQL, Lesen, Release und dem
abschließenden Cursor-Close geprüft. Der bestehende Fresh-Writer registriert
auch den von dieser API normal erzeugten Cursor; nach einem erfolgreichen
Append bleibt kein eigener nativer Cursorhandle zurück.

## Atomizität und Grenzen

Ein eigener zufällig benannter Savepoint umfasst beide Inserts und sämtliche
Kollisionsprüfungen. Gewöhnliche Fehler rollen nur diesen Savepoint zurück;
frühere noch nicht committete Callerzeilen und äußere Savepoints bleiben erhalten.
Die API öffnet weder DBs noch Dateien, legt kein Schema an und besitzt keinen
Connection-Close, äußeren Commit, Callbackparameter oder Datei-Cleanup.

Tatsächlich beobachtetes `SQLITE_FULL` wird mit originaler Ursache als
`StorageLimitError` berichtet. SQLite kann dabei selbst den ganzen Build
zurückrollen. Die inzwischen verlorene Transaktion wird nicht durch einen
neuen Savepoint/BEGIN ersetzt. Bei `SQLITE_TOOBIG` bleibt die tatsächlich noch
gehaltene Transaktion erhalten, und die fehlgeschlagene Operation ist rückgerollt.

Wenn Rollback/Close nicht verlässlich gelingt, folgt ein ausdrücklicher
`StorageIntegrityError` mit der Pflicht, den ganzen Build aufzugeben. Es wird
kein erfolgreicher Rollback behauptet und kein Receipthash zurückgegeben.
Die API schließt in diesem Fall nicht eigenmächtig die Callerconnection;
der äußere Owner muss den gemeldeten STOP tatsächlich übernehmen. Insbesondere
ist dies kein Mechanismus, der einen Caller nach ignoriertem STOP oder bereits
unerlaubtem Commit technisch am Publizieren hindert.

Bei beobachtetem Commit plus neuer Transaktion wird die fremde neue Generation
nicht als die alte zurückgerollt. Ein solcher unerlaubter Commit lässt sich
nicht nachträglich ungeschehen machen. Callbacks, parallele Caller, Rawbaseclass-
Aufrufe, beliebige Pythonmutationen, Converter/Adapter und Namespace-/ABA-
Freiheit bleiben Teil des vollständigen äußeren Writerkatalogs, nicht einer
hier erfundenen Python-Sandbox. Die API nimmt keinen solchen Callback entgegen.

Die Eingabe ist genau ein tatsächlich normalisierter Datensatz, keine große
Pendingliste. Ihr Speicherbedarf und ihre Admission gehören zum Callerbudget.
Vor dem Python-Readback werden gespeicherte Kollisionswerte begrenzt: BLOB-Typ
und tatsächliche Payloadlänge sowie NUL-feste Indexbytegrenzen mittels
`length(CAST(... AS BLOB))`. Die ASCII-Indizes erlauben auch ihre doppelt
breite physische UTF-16-Darstellung; die Inhalts-BLOBs werden nicht umcodiert.
Das begrenzt fremde gespeicherte Kollisionswerte relativ zum realen Eingaberecord,
ist aber kein zusätzlicher globaler Speicher-/Dateiquotabeweis.

## Tatsächliche Tests und RED → GREEN

Alle Läufe lokal auf Windows mit Python 3.12.14, SQLite 3.53.1 und pytest 9.1.1,
`-B`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `-p no:cacheprovider`. Jeder Lauf hatte
seine eigene vorher nicht existierende Basetemp und XML-Datei. Kein alter
Testbeleg wurde überschrieben.

| Lauf | Tatsächliches Ergebnis |
| --- | --- |
| `task44-receipt-ccr01-red.xml` | 1 Collection-ImportError in 0,33 s: Tests vor Implementierung, Modul noch nicht vorhanden. Kein semantischer Testpass. |
| `task44-receipt-ccr01-green1.xml` | 45 bestandene Tests, 1 Teardownfehler in 1,38 s: der absichtlich fremd geschlossene Writer meldete erwartbar ebenfalls einen Closefehler, den die erste Fixture noch nicht ausdrücklich erwartete. |
| `task44-receipt-ccr01-green2.xml` | 45 bestanden, 0 Fehler/Skips in 1,30 s; ausschließlich Fixture-Erwartung und überflüssiges leeres Error-Matching korrigiert, Produkt unverändert. |
| `task44-receipt-ccr01-green3.xml` | 55 bestanden, 0 Fehler/Skips in 1,54 s nach den zusätzlichen echten Terminal-/Encoding-/Limitfällen. |
| `task44-receipt-ccr01-owner.xml` | **235 bestanden**, 0 Fehler/Skips in 5,80 s: 55 neue Appendtests, 87 bestehende Observationtests und 93 bestehende Writerprofiltests. |

Die XMLs liegen jeweils unter `.pytest_tmp/`; die Basetemps tragen denselben
Namen mit `-base` statt `.xml`. Diese Zeitwerte sind lokale Suitewerte, kein
nativer Benchmark oder extrapolierter 490.000-Receipt-Nachweis.

Die neuen Tests binden insbesondere:

- Echte Path-Legacy-Appends gegen den neuen exakt gehaltenen Fresh-Writer:
  sämtliche neun physische SQL-Felder, kanonische BLOBs, Identitäten, bool/int/
  float/null, große exakte Integer, Unicode und NUL im JSON-Inhalt.
- Exakte Reingestion, Zeitzonenalias und tatsächlich anderer Empfangszeitpunkt;
  eine gemeinsame Contentzeile bei zwei echten Receipts.
- Alte fachliche Ablehnungen vor jeder Append-SQL-Ausführung: Typen, unbekannte
  Felder, unzulässige JSON-Werte/Preisfelder, native IDs/Sport, kausale/naive
  Zeitpunkte und ungültiges Gültigkeitsintervall. Keine Änderung an Cricket,
  Modell-/Sourcewahrheit oder an der untrusted Publication-Proof-Semantik.
- Tatsächlich beschädigte Contentbytes/-typen, Zeit-/Indexfelder und fremde
  Contentidentität; Receiptkollision nach bereits neu eingefügtem Content:
  Fehler und unveränderte alte/pending Zeilen, keine Reparatur.
- Unterbrochener Decoder, echtes SQL-`RAISE(FAIL)` mit bereits ausgeführtem
  Trigger-Teilschreibvorgang, Savepoint-BEGIN-/RELEASE-Autorisierungsfehler und
  ausdrücklich verweigerter Savepoint-Rollback. Die Trigger sind isolierte
  SQL-Fehlerfixtures, keine Zulassung beliebiger Trigger im C-Writerkatalog.
- Echte Commit-/Rollback-/Restart-/Close- und Factorydrift nach physischem
  Decode; Generationwechsel bereits während Normalisierung. Eine neue fremde
  Pendingtabelle bleibt beim Restart-Gegenfall unangetastet.
- Echter Main-FULL mit 32-KiB-Plan und 128-KiB-Record sowie tatsächliches
  `SQLITE_LIMIT_LENGTH`/`SQLITE_TOOBIG`, ohne Limits für Erfolg zu erhöhen.
- Kein implizites Schema/Open/Commit; intakter äußerer Savepoint; ausdrücklicher
  Callercommit und unabhängiger kalter RO-Reopen mit vollständigem Legacyvergleich.
- Wirkliche 128-KiB-BLOB-/NUL-TEXT-Kollisionen: instrumentierte reale
  `TrackedCursor.fetchone`-Rückgaben zeigen die Ablehnung vor Übertragung dieser
  großen Fremdwerte nach Python.
- Tatsächliche UTF-16le-/UTF-16be-Mains mit vollständigem Legacyvergleich und
  unveränderter DB-Encoding. Diese zwei SQL-Transportfixtures sind ausdrücklich
  kein neuer kopierter-Main-Writer; `FreshSQLiteWriter` bleibt unverändert UTF-8.

## Bytebindung

Neues Produkt, unverändert seit dem ersten Implementierungslauf:

- `context_storage_v2/receipt_append.py`:
  `e96b807b2b003b00b740b0b64ba48d86ac3fd5c930ce11bdf2a40b5436fa06e9`
- `tests/test_context_storage_receipt_append.py`:
  `cd238f9ac9db6244ff7879e8884ea7f2d0baf24d398afef533c99cf2b46c7977`

Die vor RED und nach dem Ownerlauf gelesenen folgenden Ownerbytes sind identisch:

| Datei | SHA-256 |
| --- | --- |
| `context_observations.py` | `9fb1ec38ac12dd3b142ab1b23e9c49cf605e77cd931e38c503f69026d0cec226` |
| `context_models/contracts.py` | `7b3c2a909fee790879d446ef2b95bc944d24951af4261c3296c36e6338518fa8` |
| `model_artifacts.py` | `6cd072f4cf77a9405091fbdc166580cd403ba15e232c915414be493de9fd6d16` |
| `context_runtime_transaction.py` | `ecec258d9b67964da29b9da91859c5d80ed24100765b04e14db5269b8d4e8e5b` |
| `context_storage_v2/contracts.py` | `d0c8d94c89a608fc7b3c59755cbe97c76ec79d66e53d2bb235608f341364fcf3` |
| `context_storage_v2/sqlite_profile.py` | `05898adf9782ff06e2edcf33d45c94dd6ecce232ddba1f81ffcfaf65fca3d8bc` |

XML-SHA-256:

- RED: `6f3001d4aec94f36d7bbb4865d35cf0c5449cd7361ca238bb62252ddbd48134c`
- Green1: `2404b3f6bec4f17d604b8bc5b122fa59ff1a194ed59c70a697523a366995e4a7`
- Green2: `1aa7723de6a7b549ef0b0a54827a08e67d9ae231c721a05b8a93c17b5dcb4a44`
- Green3: `bfe201adbf7b209fd90f89ef7d6a429693159027e81af6bbe4e9d54ffcaae3eb`
- Ownerlauf: `a1c18276b7491d46d48050b97b13006326440ed9b53dfa9548f9823be00b9e81`

## Einordnung in Task 39

Dies schließt ausschließlich den dort fehlenden **in-connection Receipt-Insert-
Baustein**. Ein vollständig kontrollierter beschreibbarer bereits gefüllter
privater Copy-Main, tatsächliches Copy-/Close-/Seal-Reopen, vollständiges
Altzeilen-plus-exakte-Neuzugänge-Inventar, `VerifiedReceiptMapping`-Owner,
490.000 neue Receipts, History-/Consumerproducer und Gesamtmanifest werden hier
weder hergestellt noch autorisiert. Es gibt keine neue Produkt-Callsite.

Keine 4-GiB-Aktiv-/8-GiB-ALL-/4-GiB-Reserve-Abnahme, keine gesamte CPU-/Deadline-
Bilanz, keine Windows-/Linux-Nativzulassung und kein B-/Rollout-Claim. Root kann
den bytegebundenen Baustein jetzt unabhängig prüfen und erst danach in den
tatsächlich begrenzten kleinen Corpusowner integrieren.
