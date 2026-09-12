# Task 49 — unabhängiger Review des In-Connection-Receipt-Appends

Stand: 12. September 2026. Geprüfter Task44-Freeze:
`context_storage_v2/receipt_append.py`
`e96b807b2b003b00b740b0b64ba48d86ac3fd5c930ce11bdf2a40b5436fa06e9`.

## Ergebnis und Umfang

**Kein konkretes verbliebenes Finding im begrenzten Task44-Vertrag.**
Die eigens neu geschriebenen **81 Gegenproben sind grün**. Abschließend
gemeinsam mit den 55 neuen Append-Ownertests, 87 bestehenden Observationtests
und 93 Writerprofiltests: **316 passed, 0 skipped, 0 errors**, 7,05 s;
JUnit misst 7,034 s. Produkt-/Ownertest-/Legacy-Abhängigkeitshashes nach dem
Lauf unverändert bestätigt.

Geändert wurden ausschließlich die neue normale Testdatei
`tests/test_context_storage_receipt_append_review.py`, dieser Bericht und
neue ignorierte QA-Artefakte. Keine Produkt-/Ownertestdatei, keine Server-,
Git-, Netzwerk- oder native Linuxaktion. Der getrennte noch entstehende
Task48-Corpusowner wurde weder gelesen noch geändert oder mitgeprüft.

Vollständig gelesen wurden das neue Modul, alle 55 zugehörigen Ownerfälle und
Task44. Für die tatsächliche Semantik wurden zusätzlich die konkreten
unveränderten Legacy-Append-/Schema-/Receiptdecoder-, Normalisierungs- und
Kanonisierungsfunktionen gelesen; ebenso die benötigte TrackedConnection-
Lebensdauer und die tatsächliche Cursorregistrierung/Eröffnung des
FreshSQLiteWriter. Task39s Grenzen wurden nicht erweitert.

## Semantik und echte Differentials

`receipt_append.py:92` benutzt die wirkliche unveränderte Normalisierung und
UTC-Mikrosekundenzeit, nicht nachgeahmte gültig aussehende Hashhüllen. Content-
und Receiptdigest, kanonischer BLOB und sämtliche Receipt-Indexfelder stammen
aus demselben normalisierten Inhalt. Der bestehende physische Decoder wird
nach beiden tatsächlichen Inserts/Readbacks erneut ausgeführt.

Die eigenen positiven Tests verwenden zusätzlich ein kleines unabhängiges
Orakel für diese konkreten gültigen Fixturewerte: UTC-Konvertierung,
kanonische JSON-Bytes, Content- und Receipthash werden ohne Aufruf der
Produkt-Normalisierung/-Digesthelfer berechnet. Danach vergleichen sie zugleich
mit einem echten `legacy.append_observation` über dessen alte Path-API.

15 Kombinationen aus allen fünf bisherigen Sports und UTF-8/UTF-16le/UTF-16be
stimmen in allen acht physischen Indexfeldern, dem zugehörigen Contentdigest
und dem vollständigen BLOB mit beiden Referenzen überein. Expliziter Commit
durch den Fixtureowner plus unabhängiger kalter RO-Reopen bewahrt dieselben
Werte. Eingabedicts werden nicht mutiert; die gehaltene Transaktion bleibt
während des Appends dieselbe. UTF-16-Tests sind bewusst SQL-Transportfixtures,
kein neuer kopierter-Main-Writer und keine Änderung am UTF-8-Freshprofil.

Weitere echte Differentials erhalten die Unterschiede zwischen None, False,
Integer 0, Float 0.0, -0.0, großem Integer, NUL-String und verschachteltem JSON.
Alle acht liefern unterschiedliche echte Identitäten. Zeitzonenalias derselben
Empfangszeit ist idempotent; ein Mikrosekunden späterer Empfang erzeugt
das erwartete neue Receipt bei gleichem Content. Alle Werte und Counts werden
mit den Legacytabellen verglichen. Unicode/NUL im JSON wird nicht zu einem
ASCII-Index oder zu einem anderen Encoding umgedeutet.

Sieben zusätzliche Ablehnungen für NUL-/Unicode-Indexcodes, verschachtelte
Preis-/Release-Felder, zu späte Veröffentlichung, ungültiges Intervall und
unendliche Zahlen entsprechen der echten Legacy-Ausnahme. Kein Append-SQL
wird dabei ausgeführt. Die alten fachlichen Regeln, Preisfreiheit und fehlende
Source-/Publication-Proof-Autorität wurden nicht verändert.

## Kollisionen und die genaue Materialisierungsgrenze

`receipt_append.py:49` und `:139` begrenzen alle gespeicherten Receiptfelder
vor Python-Readback mit tatsächlichem Typ und
`length(CAST(... AS BLOB))`, nicht mit dem bei NUL verkürzenden TEXT-length.
Der BLOB muss genau die Länge des tatsächlich normalisierten Eingabepayloads
haben; danach folgt weiterhin der echte Byte-/Decodervergleich. Die doppelte
Indexlänge erlaubt die physische UTF-16-Darstellung der normalisierten
ASCII-Felder und ist keine Lockerung der Inhaltsidentität.

21 eigene Fälle beschädigen jedes der sieben Nicht-PK-Indexfelder mit einem
NUL plus 32-KiB-Suffix in allen drei Encodings. Instrumentierte tatsächliche
TrackedCursor-Rückgaben zeigen: diese langen Fremdwerte gelangen nicht nach
Python; der abschließende Ergebniswert ist None. Vorhandene/pending Rows
bleiben unverändert. 14 weitere Fälle mit exakt gleich langem falschem TEXT
oder physischem BLOB statt TEXT in jedem Feld scheitern ebenfalls.

Vier echte Contentkollisionen mit gleich großem falschem BLOB, leerem BLOB,
64-KiB-BLOB oder TEXT statt BLOB werden nicht repariert. Bereits gültige
frühere Pendingbelege und die absichtlich kollidierenden alten Bytes bleiben
erhalten. Es entsteht kein zusätzliches erfolgreiches Receipt.

Die Instrumentierung beweist nur die begrenzte **Python-Rückgabe** relativ
zum echten Eingaberecord. Sie misst nicht SQLite-interne CAST-/Pager-
Allokationen, AS/RSS-Peaks oder ein festes globales Einzelrecordbudget.
Normalisierung und kanonischer BLOB materialisieren genau diesen einen
Eingaberecord. Seine Admission, die SQLite-Policy und native Speicher-/CPU-
Grenzen bleiben ausdrücklich beim äußeren Owner. Es wurde dafür kein
Ressourcendeckel erhöht oder ein RSS-/Allocatorbeweis behauptet.

Ein zusätzlicher tatsächlicher NUL-PK-Fall ist absichtlich **kein**
Vollvalidierungsfall: ein vorhandener Schlüssel `expected + NUL + suffix`
ist eine andere physische Identität. Das wirkliche neue Receipt wird separat
eingefügt; beide alten ungültigen Rawzeilen bleiben erhalten. Erfolg dieser
Einzeloperation validiert damit gerade nicht den übrigen Datenbestand.
Ein späterer vollständiger Raw-/Source-/Mapping-Owner muss weiterhin sämtliche
Altzeilen prüfen; aus dem zurückgegebenen String entsteht keine
VerifiedReceiptMapping- oder Coverage-Fähigkeit.

## Savepoints, echte SQLite-Fehler und Lebensdauer

`receipt_append.py:55` bindet den exakten TrackedConnection-Typ, gehaltene
Generation, normale Factories und manuelle Legacy-Transaktionssteuerung.
`:123` beginnt nur den eigenen Savepoint. Beide Inserts, die Kollisionschecks,
Release und Cursor-Close liegen unter erneuten Lebensdauerprüfungen. Die API
öffnet/erzeugt keine Connection/Datei/Schema, beginnt keine äußere Transaktion
und besitzt keinen äußeren Commit/Close. Sie erzeugt keine neue Produktschnitt-
Callsite außerhalb dieses Bausteins.

Acht eigene reale Trigger-Faults erzeugen an Content- bzw. Receipt-Insert
SQLite IGNORE, FAIL, ABORT oder ROLLBACK. Die Trigger sind isolierte Fehler-
Fixtures, **kein** zugelassener C-Writerkatalog. IGNORE/FAIL/ABORT werden nicht
zu partiellem Erfolg: der eigene Savepoint entfernt auch einen zuvor erfolgten
Audit-Teilschreibvorgang und bewahrt früheren Callerinhalt. ROLLBACK beendet
tatsächlich die gesamte Transaktion einschließlich der noch nicht committeten
Schemaanlage; der Baustein erfindet keine wiederhergestellte Leseepoche.

Zwei echte Progresshandler-Unterbrechungen während Content- bzw. Receipt-Insert
liefern SQLite-Fehlercode SQLITE_INTERRUPT. Die ganze Schreibtransaktion wird
von SQLite beendet; es kommt kein Digest zurück und keine Ersatztransaktion
wird gestartet. Die tatsächlichen ersten noch uncommitteten Zeilen/Schema
sind entsprechend nicht mehr vorhanden, statt als erfolgreich gerettet
ausgegeben zu werden.

Eigene kleine FULL-/TOOBIG-Differentials unterscheiden ebenfalls korrekt:
ein 32-KiB-Mainplan mit 96-KiB-Record führt zu echtem SQLITE_FULL und verlorener
Transaktion; ein tatsächliches SQLITE_LIMIT_LENGTH von 1024 mit 4-KiB-Record
führt zu SQLITE_TOOBIG bei weiterhin gehaltenem Build und unverändertem
vorherigem Inhalt. Beide werden als StorageLimitError mit wirklicher SQLite-
Ursache gemeldet, nicht als kleinere erfolgreiche Appendmenge.

Sechs zusätzlich instrumentierte finale Grenzfälle führen **wirkliche**
commit/re-BEGIN-, rollback/re-BEGIN- bzw. autocommit/re-BEGIN-Wechsel direkt
nach dem eigenen RELEASE oder beim Cursor-Close durch. Jeder verhindert den
Receiptdigest. Eine anschließend wirklich angelegte Tabelle mit einem
Pending-Sentinel in der neuen Generation bleibt unangetastet. Das bestätigt
die Zuständigkeit von `:72`/`:153`: keine fremde neue Transaktion als alte
zurückrollen. Es ist kein Schutz gegen beliebige Pythoncallbacks; solche
Mutationen sind ausdrücklich außerhalb des späteren geschlossenen Owners.
Bereits unerlaubt committete Daten können nicht nachträglich zurückgerollt
werden; der erforderliche STOP muss vom äußeren Owner übernommen werden.

Ein eigener TEMP-Schattenfall bestätigt die durchgehende `main.`-Qualifikation:
identisch benannte TEMPtabellen bleiben leer, während die Mainzeilen stimmen.
Auch dies ist nur ein Namespace-Gegenfall, keine Freigabe fremder TEMP-DDLs.
Bestehende Ownerfälle ergänzen Savepoint-BEGIN-/RELEASE-Denial, verweigerten
Rollback, Decoderunterbrechung, frühe Generationdrift, Connection-Close,
Factories und intakte äußere Caller-Savepoints. Fehlgeschlagene Cleanup bleibt
ein ausdrücklicher Whole-Build-Abandon, keine garantierte Wiederverwendung.

## Läufe und unveränderte Bytebindungen

Lokaler tatsächlicher QA-Interpreter: Python 3.12.14 / SQLite 3.53.1,
`.pytest_tmp/qa-python312-c-01/Scripts/python.exe`. Beide Läufe verwenden neue
vorher nicht vorhandene Workspace-Basetemps/XMLs. Kein Daten-/Artefaktcleanup.

| Lauf | Ergebnis | XML |
| --- | --- | --- |
| independent-01 | 81 passed, 0 skipped, 1,50 s | `.pytest_tmp/task49-independent-20260912-01.xml` |
| combined-02 | 316 passed, 0 skipped, 7,05 s | `.pytest_tmp/task49-combined-20260912-02.xml` |

Es gab keine roten Produkt- oder Harnessfälle. Vor dem kombinierten Lauf
wurden ausschließlich ein unbenutzter Clockliteral und ein unbenutzter
Keyword-Parameter aus dem eigenen Fixturehelper entfernt; der zweite Lauf
prüft die unten endgültig gehashten Testbytes vollständig.

Tatsächlicher abschließender Befehl:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -o junit_family=xunit1 tests/test_context_storage_receipt_append_review.py tests/test_context_storage_receipt_append.py tests/test_context_observations.py tests/test_context_storage_sqlite_profile.py --basetemp=.pytest_tmp/task49-combined-bt-20260912-02 --junitxml=.pytest_tmp/task49-combined-20260912-02.xml
```

| Gegenstand | SHA256 |
| --- | --- |
| `context_storage_v2/receipt_append.py` | `e96b807b2b003b00b740b0b64ba48d86ac3fd5c930ce11bdf2a40b5436fa06e9` |
| `tests/test_context_storage_receipt_append.py` | `cd238f9ac9db6244ff7879e8884ea7f2d0baf24d398afef533c99cf2b46c7977` |
| Eigene `tests/test_context_storage_receipt_append_review.py` | `498888fac6f72fb8f35910a894423c5ff67f6579b7a4122ce40734f3da831927` |
| Task44-Bericht | `e846287c2f4b1e25fd79d3423c2d111971a1dae2496dd1808e3190c18f2efbff` |
| `context_observations.py` | `9fb1ec38ac12dd3b142ab1b23e9c49cf605e77cd931e38c503f69026d0cec226` |
| `context_models/contracts.py` | `7b3c2a909fee790879d446ef2b95bc944d24951af4261c3296c36e6338518fa8` |
| `context_storage_v2/sqlite_profile.py` | `05898adf9782ff06e2edcf33d45c94dd6ecce232ddba1f81ffcfaf65fca3d8bc` |
| `tests/test_context_observations.py` | `5699044e9073a428376163f3433ef9b2d2d76dd549df0593fde27c550e849352` |
| `tests/test_context_storage_sqlite_profile.py` | `7cf07bfa2ae418b676e8a53bb074994c022c50fa65d364429903a37e5e159292` |
| independent-01 XML | `e9ef920bd060a02472bd3351a2acfded02a706c94fc3ee041635934e782059e4` |
| combined-02 XML | `8fe458e030e54fbabdd487c8a44749bdba6fb10fbeceea5d228b73cf5df4a62f` |

Abschluss: Der bytegebundene einzelne Appendbaustein ist lokal unabhängig
geprüft. Die vollständige Copy-and-append-Lebensdauer, Quellen-/Receiptmapping,
vollständige Alt-/Neuzeilenabdeckung, 490.000 zusätzliche echte Receipts,
Corpus-/Consumerowner, native Ressourcenhülle und B bleiben getrennte Arbeit.
Aus diesem Review folgt kein Gesamt-C-, Native-, Sourcewahrheits- oder B-Pass.
