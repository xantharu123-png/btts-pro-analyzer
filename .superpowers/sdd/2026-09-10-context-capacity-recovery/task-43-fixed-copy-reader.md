# Task 43 — fester C1-Kopieplatz und neuer begrenzter RO-Reader

Stand: 12. September 2026. Enger erster Implementierungsschritt aus Task39,
nicht der dort noch fehlende Corpus-/Consumer-/Gesamtowner.

## Ergebnis und Umfang

`copy_legacy` akzeptiert jetzt einen vorher reservierten festen
`owned_directory`-Pfad und konfiguriert seine **intern neu geöffnete** RO-
TrackedConnection vor SQL-Workload mit effektivem MEMORY TEMP und begrenzter
Lesepolicy. Der bisherige lokale Conveniencepfad bleibt erhalten. Quellreader,
Rohbytekopie, Schema, Seitengröße, Encoding, vollständige Raw-Inventur und
historische CopyReceipt-Semantik bleiben unverändert.

Gelesen wurden Task39 vollständig, copying.py und seine tatsächliche
Owner-Testdatei vollständig, außerdem RawInventory/_HeldRead, die verwendete
Pfadprüfung und beide historischen unabhängigen C1-Proben. Das alte ungefixte
RED-Instrument wurde nur gelesen; ausgeführt wurden die unveränderten
Postfix-FD-Probes mit dem heute erforderlichen ursprünglichen Sourcehash.

Geändert wurden ausschließlich `context_storage_v2/copying.py`,
`tests/test_context_storage_copying.py` und dieser Bericht. Kein Shared Helper,
History, Tennis, SQLite-Profilowner, Nativeprobe, Supervisor, Guard, Budget,
Quellowner oder Originaldatenbestand wurde geändert. Kein Git-, SSH-, Server-
oder nativer Korpusaufruf fand statt.

## Enge Schnittstelle

```python
receipt = copy_legacy(
    held_source,
    directory=whole_job_workspace,
    owned_directory=whole_job_workspace / "baseline",
    expected_source_sha256=actually_sealed_source_sha256,
    limits=limits,
)
# receipt.path == whole_job_workspace / "baseline" / "legacy-copy.sqlite"
```

Native Caller **müssen** den bereits reservierten, privaten, exklusiven leeren
Ordner übergeben. Er muss absolut und ein exakter direkter Child des gesamten
angegebenen Workspace auf demselben Device sein. Keine `..`-Umdeutung,
Symlink-/Junction-/Reparse-Adoption, kein vorhandener Main, Journal, WAL/SHM
oder unbekannter Eintrag. Das bestehende EXCL-Open bleibt bestehen; ein
beobachteter Wechsel der gewählten Verzeichnisidentität wird zusätzlich während
des Kopier-/Verifikationsablaufs zurückgewiesen.

Ohne diesen Parameter entsteht weiterhin ein neues `context-copy-*`-Verzeichnis
als ausschließlich lokale Conveniencefunktion. Sie ist keine native globale
Reservation. Alle entstandenen neuen Main-Dateien bleiben auf Erfolg und Fehler
erhalten. Auch Eröffnungsfehler nach Directoryanlage tragen deren Pfad in einer
Exception-Note. Das ist keine vollständige Inventur oder Budgetentlastung.
Ein nichtleerer Ownedordner kann nicht für einen Folgeversuch übernommen werden.

Die Bytekopie wird **nicht** durch SQLite-Backup, SQL-Reassembly oder einen
FreshSQLiteWriter ersetzt. Deshalb wurde kein SQLiteWriterPlan importiert:
dessen zusätzlicher Journal-M-Slot wäre eine neue falsche Writerreservation für
diesen reinen Rawcopy-/RO-Pfad. Die bisherigen Source-plus-Copy-Inputkosten,
ganzer Workspace, Metadatenreserve und Freiraumbedingungen bleiben bestehen.
Ein zusätzlicher Test zeigt eine zulässige reine Kopiehülle unter `2 * copy_size`;
der getrennte Source-plus-Copy-Eingabedeckel gilt dabei weiterhin unverändert.

## Internes Readerprofil und Lebensdauer

Die neue RO-Verbindung bleibt **exakt TrackedConnection**, `mode=ro`, timeout=0,
kein Statementcache und explizite manuelle Transaktionsführung. Der Ablauf ist:

1. Erste SQL ist `PRAGMA temp_store=MEMORY`; tatsächlicher Readback muss genau
   der native Integer 2 sein.
2. Der Compilekatalog wird vor jeder Schema-/Inventurarbeit bounded gelesen:
   höchstens 256 einspaltige Optionen, höchstens 256 Zeichen je Option und genau
   ein TEMP_STORE=1/2/3. TEMP_STORE=0, fehlende, doppelte oder fehlerhafte Werte
   sind Fehler, kein FILE-Fallback. Profilcursor werden explizit geschlossen.
3. Maincache 4096 KiB, mmap=0, threads=0, ATTACHED=0, WORKER_THREADS=0,
   Extensions aus, Defensive an, Trusted Schema aus, query_only an.
4. max_page_count ist die **tatsächlich gebundene Quellseitenzahl**. Die
   tatsächliche Seitengröße/-anzahl werden gelesen, nicht auf neue 4096-Byte-
   Seiten umgestellt. Encoding, Schema und Journalmodus werden nicht gesetzt.
5. BEGIN und ein tatsächlicher _HeldRead binden die interne Leseepoche. Vor und
   nach dem vollständigen Compare sowie während der nachfolgenden begrenzten
   Hash-/Abschlusschecks bleiben Policy und Readergeneration geprüft.
6. Der Reader wird vor Funktionsrückkehr geschlossen. Verschachtelte finally-
   Pfade schließen die beiden eigenen Source-/Output-FDs auch dann, wenn der
   Readerabschluss seinerseits fehlschlägt. Es entsteht kein wiederverwendbarer
   Live-Reader oder eine durch Pfadnamen reaktivierbare Proof-Fähigkeit.

Der übergebene Quellreader wird nie umkonfiguriert. Ein nativer Quellowner muss
seine eigene passende MEMORY-/Ressourcenpolicy vor seinem Pinning herstellen.
Die internen Grenzreadbacks sind keine Garantie gegen bösartige Pythoncallbacks,
Namespace-ABA oder fremde Schreiber. Die schon bestehende äußere private,
quieszente, exklusive Namespacebedingung wird nicht durch ein Bool oder eine
Hashhülle ersetzt.

## Tests: RED, Umsetzung, vollständige lokale Regression

Runtime: `.pytest_tmp/qa-python312-c-01/Scripts/python.exe`, Windows,
Python 3.12.14 / SQLite 3.53.1. `-B`, Plugin-Autoload aus, pytest-Cache aus;
jede Basetemp/XML war vor Start neu. Keine ältere Evidenz wurde überschrieben
oder entfernt. Alle 17 bisherigen Ownerfälle bleiben erhalten; die Fixture
hat nur ausdrücklich wählbare Seitengröße/NUL-Schlüssel für zusätzliche Fälle.

- Vor Produktänderung: **4 erwartete rote Tests**, 17 nicht ausgewählt.
  UTF8/UTF16le/UTF16be wurden wegen fehlendem owned_directory-Argument abgewiesen;
  der tatsächliche erste Reader-SQL-Trace war query_only statt MEMORY.
- Erster grüner Ownerlauf: **21 bestanden**, 6,74 s.
- Erweiterter Ownerlauf: **66 bestanden**, 10,77 s.
- Erster Kombilauf: **130 bestanden, 1 Skip**, 20,70 s.
- Finaler Kombilauf: **140 bestanden, 1 Skip**, 21,20 s (JUnit 21,199 s).
  Tatsächlich Copy 76, RawInventory 42, Root-Integration 6 und unveränderte
  unabhängige FD-Probes 17. Alle 76 finalen Copyfälle bestanden.

Der eine Skip betrifft ausschließlich
`test_actual_source_replacement_binds_original_expected_hash`: Windows verweigert
die Ersetzung dieser offen gehaltenen SQLite-Quelldatei. Das ersetzt keine
entsprechende Linuxprobe. Die getrennten Destination-Swap-Probes beobachten
ebenfalls ehrlich entweder tatsächliche Zurückweisung oder die konkrete
Verweigerung der Dateiersetzung durch das lokale OS.

Zusätzliche echte lokale Fälle umfassen feste Pfade/Nichtübernahme, UTF8/
UTF16be/le, Seiten 512/8192/65536, opaque/unkanonische Rawpayloads, NUL in Werten
und NUL-plus-Unicode in vollständigen alten Schlüsseln. C1 erzwingt gerade nicht
die neue C2-Digestgrammatik für alte Rawschlüssel. Verglichen werden ganze
Dateibytes und vollständige typisierte Inventuren, nicht nur Counts oder
umgeschriebene JSON-Werte.

Echte Fehler-/Lebensdauerfälle: kurze/ausbleibende Raw-FD-Writes, tatsächliche
gehaltene Sourcewechsel, WAL-Header-Rejektion vor Seitendateien, abgewiesener
interner RO-Open und durch SQLite selbst verweigerte MEMORY-Einstellung,
vollständig erhaltene fehlgeschlagene Main-Dateien und tatsächlich geschlossene
eigene FDs/Reader. Cache-, Seiten-, Thread-, Attachment-, Extension-, Defensive-
und Trusted-Schema-Drift nach einer vollständigen Inventur verhindert das
Receipt. Das echte mode=ro verhindert ein UPDATE auch nach query_only=OFF;
die erfolgreiche Copy bleibt nach dem erwarteten SQLITE_READONLY bytegleich.

Die absichtlich defekten Compile-/MEMORY-Readbacks und der 257-Zeilen-
Overflowcursor sind **ausdrücklich modellierte Protokolltests**, keine Behauptung
über eine tatsächlich lokal installierte TEMP_STORE=0-Buildvariante. Der
erfolgreiche Compile-/Policy-Readback und die SQLite-Fehlerpfade verwenden
dagegen die echte lokale SQLite-Verbindung.

Tatsächlich ausgeführter finaler Befehl:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -o junit_family=xunit1 tests/test_context_storage_copying.py tests/test_context_storage_inventory.py tests/test_context_storage_integration.py .pytest_tmp/copy-independent-review-20260912-ccr01/test_copy_review_fd.py --basetemp=.pytest_tmp/task43-final-bt-20260912-1 --junitxml=.pytest_tmp/task43-final-20260912-1.xml
```

## Eingefrorene Bytes und Evidenz

| Gegenstand | SHA256 |
| --- | --- |
| copying.py vor Task43 | `27d4c8887756aeeb8f8041744814b6c9d09e576427e8f62ef9ef09c64ba129be` |
| Copy-Ownertests vor Task43 | `3dff14fcc23364cb9b04adfa853df77162ff2cb7c2dd6b4f71ded10032a1a6de` |
| copying.py final | `15c031ad5727c69b218d3487bc981ad3126e9e285d254822e94597ade09f0b23` |
| Copy-Ownertests final | `efeded8cf3f42dc1aea212c0608d04e1d95b9dfec20844f23b55a3541909332a` |
| Task39 gelesener Bericht | `511b868184f0195cf9610e26a96712efaba40385ce90637a3ebe361c4e7ab81a` |
| Unveränderte FD-Probes | `b084d74d17279e6eff2178ba30c6f0b63cfb4c34bec4c9808701b1a69de83855` |
| task43-red-20260912-1.xml | `08f7c93f6cb6a3a6bb8aed6d3584a6883a87db4360133642260d402bd84cc0a5` |
| task43-green-20260912-1.xml | `ff86556a08ec26cb22260ef0e2fe2cf023636939c8496897b1da217a470d679d` |
| task43-extended-20260912-1.xml | `c2ccd2633330bdeaa35bea0619420df632cee77decde37289ceaa4b275a38e16` |
| task43-combined-20260912-1.xml | `d7f94acf99c4076f5c102bed5304b9270a94119814408790ae2a532d3e48d421` |
| task43-final-20260912-1.xml | `f3264484ca38807213db89893641e33694cca79530620b6e6c0abe4dc7ebb12f` |

Nach dem finalen Lauf neu geprüft unverändert: History
`287ae422bdbd7925e0c09899d870a4ef953c5c11024c0dc7f98a11183a5158b8`,
Tennis `da51aab436387021e2d2022bea71f6045c0b0e5f6a4f8efce64fa52a6f029698`,
SQLite-Profil `05898adf9782ff06e2edcf33d45c94dd6ecce232ddba1f81ffcfaf65fca3d8bc`.

Abschluss: Task39 Schritt 1 ist lokal implementiert und regressionsgeprüft;
unabhängiger Review vor nativer Verwendung bleibt erforderlich. Private
Copy-and-append-/Corpusowner, tatsächlicher Consumerproducer, Worker-/Reopen-
Lifecycle, vollständige 590.553/199/199/114-Generationen, native AS/RSS/CPU/
Deadline/FSIZE/physische Gesamtbilanz und B bleiben gesonderte offene Arbeit.
Kein Recht zum Append, Löschen, Resume oder zur B-Publikation wird aus diesem
CopyReceipt abgeleitet.
