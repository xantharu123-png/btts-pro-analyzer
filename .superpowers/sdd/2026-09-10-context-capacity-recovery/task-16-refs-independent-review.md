# Task 16 — unabhängiges C2-Referenzreview

12. September 2026. Reviewer `c_tennis`, nicht Autor von `refs.py` oder dessen
Testdatei. Nur read-only Quellprüfung und eigene isolierte lokale SQL-Fixtures;
keine Änderungen der geprüften Produkt-/Testdateien, keine Git-/Serveraktion.

**Aktualisierung nach unabhängigem Root-Nachprüfauftrag:** Der unten historisch
noch offene Instanzcallback-Befund ist nun am finalen C2-Hash
`e80492be96ea0aacd5bb2038018c90bf8201d3e4a616d2574c456d5f9899cb2b`
mit vier direkten unabhängigen Fällen geschlossen. Der ergänzende Reviewer
`c_snapshot_review` dokumentiert die genaue Wiederholung am Ende dieses
Berichts; die ursprünglichen Beobachtungen von `c_tennis` bleiben erhalten.

## Vollständig gelesener Ausgangsstand

- `context_storage_v2/refs.py` SHA-256
  `fb1ca3ff5c282d5ca932125495208b5a27fa1481750bb53882afcc6cd59d7221`
- `tests/test_context_storage_refs.py` SHA-256
  `8feaed2cf082b09e821094c5d4308d78a50e210f5cb80429bcd208b236dec45e`
- Gemeinsame `StorageLimits` sowie die tatsächliche `TrackedConnection`-
  Transaktionsgeneration wurden ebenfalls gelesen.

Der C2-Autor hat beide Ausgangshashes ausdrücklich als eingefroren bestätigt.

## Erstes Finding P2: Ressourcenbindung endet am Iteratorstart — Fix gegengeprüft

Der Iterator prüft seine Ressourcen bei Eintritt, bindet nach dem ersten
ausgegebenen Referenzwert aber nur Transaktion, Daten-/Schemaänderungen und
Factories. Änderungen des angenommenen Cache-/Datei-/mmap-Vertrags sowie
nachträglich gefälschte `StorageLimits` werden am nächsten `next()` noch
akzeptiert. Damit ist die initial geprüfte feste Ressourcenhülle während der
fortgesetzten Verarbeitung nicht vollständig gebunden.

Eigene konkrete Reproduktion je Fall in einer frischen privaten Datenbank:

1. Echte `TrackedConnection`, page_size 4096, cache_size -4096, mmap 0,
   max_page_count innerhalb 4 GiB, gehaltene Transaktion.
2. Über den tatsächlichen C2-Owner vier eindeutige Hexreferenzen in zwei
   64-Byte-Blöcken speichern; committen; neue Transaktion; Iterator beginnen.
3. Nach dem ersten Wert genau eine folgende Änderung vornehmen und den
   nächsten Wert abfragen.

| Änderung | Tatsächlicher nächster Schritt im Ausgangsstand |
| --- | --- |
| `PRAGMA cache_size=-4194304` | zweiter Referenzwert akzeptiert |
| `PRAGMA max_page_count=2147483646` | zweiter Referenzwert akzeptiert |
| `PRAGMA mmap_size=1073741824` | zweiter Referenzwert akzeptiert |
| `object.__setattr__(limits, 'block_bytes', 2**30)` | zweiter Referenzwert akzeptiert |
| `object.__setattr__(limits, 'min_free_bytes', 0)` | zweiter Referenzwert akzeptiert |
| `CREATE TABLE unexpected(x TEXT)` | korrekt `StorageIntegrityError` |
| `CREATE TEMP VIEW v2_ref_blocks AS SELECT * FROM main.v2_ref_blocks WHERE 0` | korrekt `StorageIntegrityError` |

Die Probe lief erfolgreich mit Exit 0 und gab nur diese Metadaten aus; alle
sieben Resultate wurden tatsächlich beobachtet. Keine echte große Allokation
oder RAM-Erschöpfung wurde ausgelöst oder behauptet.

Root und C2-Autor wurden mit dem reproduzierten Finding informiert. Gefordert:
die konkrete Limits-Identität und relevanten Ressourcen-PRAGMAs an die gesamte
Iteratorlebensdauer binden, nachträgliche Änderungen vor dem nächsten Wert
ablehnen und entsprechende Negativtests hinzufügen.

Der Fix `425ed58af440105ed012e191203cfbe44d8ae6e2183724dbcaf5d1d417679a40`
bindet diese Ressourcen-PRAGMAs und die Limits-Feldwerte. Das **eigene identische
Sieben-Fälle-Instrument wurde erneut ausgeführt**: alle sieben Änderungen
wurden jetzt mit `StorageIntegrityError` beziehungsweise `StorageLimitError`
vor dem nächsten Wert zurückgewiesen. Die 89 C2-Autorregressionen wurden vom
Reviewer ebenfalls ausgeführt und bestanden; zusammen mit einem separaten
Tennis-Negativtest waren das 90 Tests in 16,65 s. Dieser erste Befund ist damit
auf dieser Version geschlossen.

## Zweites Finding P2: Instanzcallback kann die Limitsprüfung ersetzen — ursprünglich offen

Weitere eigene tatsächliche Reproduktion auf demselben Fix:

```python
forged = dataclasses.replace(DEFAULT_LIMITS)
object.__setattr__(forged, "block_bytes", 2**30)
object.__setattr__(forged, "__post_init__", lambda: None)
descriptor = put_refset(connection, ["1" * 64], limits=forged)
list(iter_refset(connection, descriptor, limits=forged))
```

Beide Operationen akzeptierten das behauptete 1-GiB-Blocklimit. Der Typ bleibt
exakt `StorageLimits`, aber die Boundary ruft `limits.__post_init__()` dynamisch
über die manipulierbare Instanz auf. Die feste Klassenfunktion muss stattdessen
als `StorageLimits.__post_init__(limits)` aufgerufen werden. Root und C2-Autor
sind informiert. Noch keine abschließende Freigabe, solange dieser reproduzierte
Vertragsbypass nicht korrigiert und unabhängig erneut geprüft ist. Die Probe
hat nur eine normale 32-Byte-Referenz gespeichert, keine große Allokation.

## Bereits belegte Eigenschaften und genaue Claimgrenzen

- Die vollständige kanonische Referenzliste und das vollständige geordnete
  Blockverzeichnis werden getrennt gehasht. Count allein reicht nirgends.
- Quellen werden auf einer normalen diskgestützten Staging-Tabelle sortiert;
  nicht die vollständige Referenzmenge, sondern nur begrenzte Blockbytes und
  höchstens die erlaubte Zahl an Manifestteilen werden im Python-RAM gehalten.
- Fehlende/zusätzliche/vertauschte Blöcke, gleiche Counts bei anderer
  Mitgliedschaft, doppelte Referenzen und Typkanten wie `N+0,5` sind im
  tatsächlichen vollständigen Reader überprüft und in den Autorregressionen
  berücksichtigt. Ein nicht vollständig konsumierter Iterator ist keine
  erfolgreiche vollständige Prüfung.
- Die initiale Typ-/Schema-/Ressourcenaufnahme, blockweise Blobgrößenprüfung
  vor dem Laden und die explizite SQL-Transaktionsgeneration sind vorhanden.
- Main- und TEMP-DDL nach dem ersten Wert wurden im unabhängigen Repro
  tatsächlich abgewehrt, nicht nur aus einer grünen Autorregression abgeleitet.
- Das Modul nimmt eine eigene private Connection des Aufrufers an. Der
  übergeordnete geschützte Owner muss deren Herkunft, verbotene ausführbare
  Callbacks, gesamten Mehrdateibestand und Veröffentlichungsautorität binden.
  Ein öffentlicher Digest ist weder HMAC-Berechtigung noch ein Root-/VM-Anker.

Die Komponente beweist für sich weder die gesamte 8-GiB-QA-Bilanz noch native
RSS-/CPU-Grenzen, den vollständigen Wachstumsbestand, Backup-/Restorefähigkeit
oder Deployment-/empirische Modellfreigabe. Diese bleiben bei der C/B-
Gesamtintegration und dürfen nicht aus diesem Code-/Fixture-Review abgeleitet
werden.

## Finale unabhängige Nachprüfung des Instanzcallback-Befunds

12. September 2026. Ergänzung durch `c_snapshot_review` auf ausdrücklichen
Rootauftrag; keine Änderung der Produktdateien oder vorhandenen Owner-Tests.
Das ursprüngliche Finding wurde von `c_tennis` erhoben. Hier wurde das im
Bericht gezeigte Reproduktionsmuster direkt mit dem tatsächlichen finalen
Refowner erneut ausgeführt, nicht nur aus dessen inzwischen grünen Tests
abgeleitet.

Vor und nach dem Lauf bestätigter `context_storage_v2/refs.py`-SHA256:
`e80492be96ea0aacd5bb2038018c90bf8201d3e4a616d2574c456d5f9899cb2b`.

Der konkrete feste Owner `StorageLimits.__post_init__(limits)` steht sowohl
an der Eingangsgrenze als auch bei der gebundenen Generation. Eigene frische
SQL-Fixtures setzten jeweils am exakt typisierten `StorageLimits`-Objekt
`block_bytes=2**30` und `__post_init__=lambda: None`:

1. Vor `put_refset(connection, ["1" * 64], limits=forged)`:
   `StorageLimitError`, keine neue Referenzmenge.
2. Vor `iter_refset(..., limits=forged)` mit gültigem vorhandenem Deskriptor:
   `StorageLimitError` vor dem ersten Wert.
3. Nach dem ersten normalen Iteratorwert: `StorageLimitError` vor dem nächsten
   Wert.
4. Vor `validate_all(..., limits=forged)`: `StorageLimitError`.

In allen vier Fällen blieben die vollständigen kleinen Ref-, Manifest- und
Stagingtabellen exakt erhalten, die Aufrufertransaktion aktiv und das
ursprüngliche Refset mit unveränderten gültigen Limits wieder vollständig
lesbar. Der überschattete Instanzcallback bewirkt keine Zulassung.

Eigene Reproduktionsdatei:
`.pytest_tmp/test_c2_limits_callback_closeout_20260912_1.py`, SHA256
`60335cf563e7670a5916a29cb64c974390388afbc4f2da1e74f104fb0d94089c`.

**4 Tests bestanden, 0 Fehler, 0,818 s, Exit 0.**
JUnit `.pytest_tmp/c2-limits-callback-closeout-20260912-1.xml`, neuer separater
Basetemp `.pytest_tmp/c2-limits-callback-closeout-20260912-1`.
Gebündelter Python aus
`C:/Users/miros/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`,
`PYTHONPATH=C:/Projekt/BetBoy/betboy-app/.venv/Lib/site-packages`,
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTHONDONTWRITEBYTECODE=1`,
`-p no:cacheprovider -o junit_family=xunit1`.

**Der zweite P2-Befund ist damit geschlossen.** Der zusätzlich in Task 17
erkannte und von Root behobene NUL-Metadatenbefund ist an genau diesem finalen
Refhash ebenfalls unabhängig gegengeprüft; siehe
`task-17-snapshot-independent-review.md` für die unveränderten Gegenproben und
die tatsächlichen Allokationsmessungen. Keine allgemeine C-/B-, Ressourcen-,
Quellcoverage-, Backup-/Restore- oder Deploymentfreigabe aus diesem Nachtrag.
