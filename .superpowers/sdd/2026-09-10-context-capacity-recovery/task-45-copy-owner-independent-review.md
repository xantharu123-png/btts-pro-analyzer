# Task 45 — unabhängiger Review des festen C1-Copy-Owners

Stand: 12. September 2026. Geprüfter Task43-Freeze: `copying.py`
`15c031ad5727c69b218d3487bc981ad3126e9e285d254822e94597ade09f0b23`.

## Ergebnis

**Kein konkretes verbliebenes Finding im ausdrücklich begrenzten C1-Copy-
Vertrag.** Das Delta mit festem `owned_directory` und neuem MEMORY-RO-Reader
kann in dieser lokalen Grenze weiter integriert werden. Das ist weder eine
native Gesamt-C-Abnahme noch B-, Corpus-, Append- oder Publikationsfreigabe.

Eigene neue normale Regressionen: **57 passed, 1 skipped**, 58 Cases, 9,07 s.
Abschließend zusammen mit unveränderten Copy-Ownertests, RawInventory,
Root-Integration und den älteren unabhängigen FD-Probes: **197 passed,
2 skipped**, 199 Cases, 30,33 s; JUnit misst 30,318 s. Alle Produkt-/Ownertest-
Hashes wurden nach dem Lauf erneut bestätigt. Die zwei Skips werden unten
nicht als erfolgreiche Dateiaustauschproben ausgegeben.

Es wurden ausschließlich die neue eigene Datei
`tests/test_context_storage_copy_owner_review.py`, dieser Bericht und neue
ignorierte lokale QA-Artefakte angelegt. Keine Produktdatei, bestehende
Owner-Testdatei, `receipt_append.py`, Server-, Native-Guard-/Supervisordatei oder
Git-State wurde geändert. Keine SSH-, Netzwerk-, Mount-, Dienst- oder
Linux-Nativeausführung durch diesen Reviewer.

## Gelesener Vertrag und genaue Prüfgrenze

Task39 und Task43 wurden vollständig gelesen, ebenso `copying.py` und seine
Ownertests. Die konkreten Abhängigkeiten wurden mitgelesen: vollständige
`inventory.py`/`TrackedConnection`, geschlossene Legacy-Schema-Prüfung und
Symlink-/Junction-Pfadprüfung. Die genehmigten C1–C4-Regeln bleiben unverändert.

Task39s erster fehlender Baustein war ein vorher benannter Copy-Slot samt
MEMORY-Profil seines **zusätzlichen Readers**, nicht die Neuerstellung der
alten DB durch einen SQLite-Writer. Task43 löst genau diesen Schritt:

```python
receipt = copy_legacy(
    held_source,
    directory=whole_job_workspace,
    owned_directory=whole_job_workspace / "input-copy",
    expected_source_sha256=separately_sealed_original_sha256,
    limits=limits,
)
# Historischer Nachweis für input-copy/legacy-copy.sqlite, kein Live-Seal.
```

Die Funktion erzeugt über einen exklusiven Raw-FD eine bytegleiche Main-Datei.
Sie startet keinen SQLite-Write-Commit, keine Backup-/VACUUM-Neukonstruktion
und keine zweite schreibende Main-Verbindung. Deshalb ist hier eine zusätzliche
Writer-Journal-M-Reservation falsch; der vorhandene Source-plus-Copy-
Inputdeckel bleibt trotzdem erforderlich. Diese Entscheidung ist mit dem
bereits geprüften FreshSQLiteWriter kompatibel, setzt diesen aber nicht für
einen nicht existierenden SQL-Write-Workload ein.

## Konkrete Befunde und Gegenproben

### Feste Pfade, neue Dateien und erhaltene Artefakte

`copying.py:122` verlangt bei explizitem Ownedpfad einen absoluten leeren
direkten Unterordner des Workspace. Leaf-Reparse-/Device-Prüfung und die
gemeinsame Symlink-/Junction-Prüfung werden nicht durch einen Besitz-Boolean
ersetzt. `copying.py:316` hält die für den Kopierablauf verwendete
Verzeichnisidentität; `:317` öffnet das neue Main ausschließlich mit EXCL.

Eigene echte Tests prüfen bereits vorhandenen Main, Journal, WAL, SHM,
verstecktes Fehlerartefakt und fremden Unterordner. Alle verweigern die
Übernahme ohne Änderung an Bytes, Inode, Größe oder mtime des vorhandenen
Eintrags. Echte Hardlinks auf Source bzw. einen anderen Workspace-Eintrag
werden abgewiesen. Die Ownertests ergänzen fehlende, relative, verschachtelte,
äußere und `..`-Pfade. Erfolgreiche Wiederholung mit demselben Ownedordner ist
weiterhin ein Fehler, kein Resume oder Budgetreset.

Die eigene echte Verzeichnisumbenennung nach EXCL-Open ist unter diesem
Windows nicht möglich; sie wird explizit übersprungen. Ein **getrennter
modellierter** Inodewechsel nach Allokation aktiviert dagegen wirklich den
Abbruchzweig vor dem ersten Write. Weitere explizite Statmodelle prüfen ein
anderes Device und einen Reparse-Flag. Diese Modelle sind keine ausgeführten
Linux-Mount- oder Windows-Junction-Tests.

Echte Fehler an Raw-Read, Raw-Write, fsync sowie ein nach tatsächlichem
Reader-Close ausgelöster Fehler verhindern das Receipt. Beide eigenen
Raw-FDs sind danach durch echte `os.fstat`-Fehler als geschlossen beobachtet;
der fremde Sourcehandle bleibt bis zum äußeren Ende offen. Der feste Main-Slot
bleibt leer oder vollständig erhalten, entsprechend dem tatsächlich erreichten
Schritt. Ein vor Reader-Open hinzugekommenes WAL/SHM/Journal wird erkannt und
zusammen mit dem Main behalten. Ownertests decken zusätzlich RO-Open-Fehler,
SQLite-AUTH beim ersten MEMORY-Setzen und tatsächliche Reader-Schließung ab.

Exception-Notes über den erhaltenen Ordner sind **keine** vollständige
Artefaktinventur und keine Entlastung. Der globale Owner muss Main, frühere
Fehlversuche und sämtliche übrigen reservierten Slots weiter bilanzieren.

### Vollständige typisierte Raw-Coverage, nicht nur derselbe Validator zweimal

Das eigene Orakel in `test_context_storage_copy_owner_review.py:112`
berechnet Row-, Table-, Schema- und vollständigen Logical-Digest aus den
unabhängig aufgebauten Fixturewerten. Es ruft weder `inventory_raw` noch dessen
Framing-/Hashhelfer auf. Geschlossenes Schema wird über die existierenden
unveränderten Legacy-DDLs hergestellt; die erwarteten Wertbytes und Framing-
Schritte entstehen im Reviewer-Orakel.

Alle sieben physischen Tabellen sind absichtlich gefüllt: Integer-ID,
NULL-Predecessor, leerer und nichtleerer BLOB, Fremdtour-/Future-Observation,
unreferenzierter Content, Rollback, Original-/Snapshot-Payloads. Schlüssel und
Werte enthalten NUL plus Unicode, darunter ein Zeichen außerhalb der BMP.
Textwerte und indizierte Schlüssel überschreiten den jeweils zugelassenen
kleinen Verarbeitungsblock. Positive Fixtures enthalten bewusst opaque bzw.
unkanonische JSON-Bytes und keine gültige C2-Digestgrammatik: C1 muss sie
verlustfrei erhalten, ohne sie fachlich zu akzeptieren.

Neun echte Kombinationen aus UTF-8, UTF-16le, UTF-16be und 512-, 4096-,
65536-Byte-Seiten stimmen in allen Tabellenwerten, Gesamtwertbytes und
Schema-/Logical-Digests mit dem Orakel überein. Zusätzlich stimmen ganze
Dateibytes und Source-/Copy-SHA. Zwei echte leere Varianten unterscheiden
korrekt Core-only mit fehlenden optionalen Tabellen von allen sieben leeren
Tabellen. Der größte eigene Original-Fixturefile ist 1.376.256 Bytes; es wurden
keine großen Corpus- oder Hochrechnungsdaten erzeugt.

Fünf echte zusätzliche SQLite-Mutationen **nur am neu erzeugten Test-Copy**
erfolgen nach dessen Rawcopy-fsync und vor seinem internen Reader-Open:
gleiche Zeilenanzahl/anderer Schlüssel, gleiche Payloadlänge/andere Bytes,
fehlender unreferenzierter Content, zusätzliche Zeile und TEXT statt BLOB.
Jede erreicht den tatsächlichen vollständigen `compare_raw` und scheitert;
keine erlangt ein Receipt. Ungültige physische Typen in vier tatsächlichen
Sourcevarianten werden schon vor Ausgabeallokation abgewiesen.

`copying.py:304–309` erfasst die vollständige erste Inventur und den originalen
Dateihash vor Anlage. `:375` vergleicht die vollständigen Inventuren erneut;
`:378–383` rehasht Copy und Source und prüft abschließend Lebensdauer/Budget.
Count-only, Cutoff-/Tour-Auswahl, Source-Typkoercion, große NUL-Schlüssel
abschneiden oder JSON neu kodieren wurden nicht eingeführt.

### FIRSTSQL, Page-/UTF-Identität und Connection-Lebensdauer

Der tatsächlich beobachtete neue Reader ist genau `TrackedConnection`, wird
einmal per `mode=ro`, `timeout=0`, `isolation_level=None`, Legacy-autocommit
und `cached_statements=0` geöffnet (`copying.py:368`). Seine erste tatsächlich
getracete SQL ist `PRAGMA temp_store=MEMORY`, nicht ein Schema- oder
Page-Read. Kein CREATE/INSERT/UPDATE/ATTACH/VACUUM/COMMIT wird im Copy-Pfad
ausgeführt. Genau ein BEGIN hält den Verifikationsreader; vor Rückkehr ist
dieser tatsächlich geschlossen.

`copying.py:189` prüft wirklichen Integer-2-Readback und den begrenzten
Compilekatalog. `:158` bindet MEMORY, 4096-KiB-Cache, mmap=0, Threads=0,
Attachment-/Workerlimits=0, Extensions aus, Defensive an, Trusted Schema aus,
query_only sowie die **wirkliche** Quellseitengröße/-anzahl und den darauf
gesetzten max_page_count. Encoding, Page-Format und Journalmodus werden nicht
umgeschrieben. Die Ownerfälle testen zusätzlich tatsächliches SQLITE_READONLY
bei probeweise ausgeschaltetem query_only sowie die einzelnen Profil-Drifts.

Die Source startet im eigenen Test mit bewusst unterschiedlichem Cacheprofil.
Alle abgefragten Source-Pragmas, die Leseepoche und die gesamten Sourcebytes
bleiben nach der erfolgreichen Kopie identisch. Sie wird nicht nachträglich
auf das neue Readerprofil umkonfiguriert.

Zehn eigene reale Lifecyclefälle beenden/wechseln nach dem vollständigen Compare
die Source- bzw. Copy-Leseepoche: commit/re-BEGIN, rollback/re-BEGIN,
executescript/re-BEGIN, autocommit-Wechsel und TEMP-DDL. Alle scheitern, auch
wenn dieselbe Connection danach wieder in einer Transaktion steht. Vier weitere
Reader-Shape-/Policyänderungen nach der Inventur verhindern das Receipt.
Der Quell-/Copy-Payload bleibt in diesen Fällen unverändert; erkannt wird
tatsächlich die verlorene Generation bzw. Policy, kein beiläufiger Bytefehler.

### Begrenzte Ressourcenbeobachtung bleibt ehrlich begrenzt

`copying.py:279` fixiert die unverbreiterten StorageLimits, Leseepoche,
Dateiversion und Verzeichnisidentitäten. `:297` zählt den vorhandenen gesamten
benannten Workspace plus restliche Copybytes und Metadaten und liest freie
Kapazität erneut. Eigene konkrete Probes ändern nach der Inventur die
Limitsinstanz, den beobachteten Free-Space-Wert oder erzeugen einen zusätzlichen
echten früheren Fehlerfile im Workspace. Kein Fall liefert Erfolg.

Das bleibt ein lokaler quieszenter Accounting-/Readback-Pfad. Er beweist weder
physische Allocation mit fremden Devices und offenen/unverlinkten Dateien noch
AS/RSS/CPU/FSIZE/Allwriter-Quota. Der zukünftige globale/native Owner muss den
gesamten Dateibaum, vorreservierte Slots, Source-Seals, die Source-Readerpolicy
vor Pinning und Prozessressourcen selbst halten. Copy prüft das Device des
Ownedordners; die stärkere Prüfung **aller** Workspace-Devices bleibt beim
separaten globalen WorkspaceOwner.

Die Namespacequieszenz ist eine echte Vorbedingung. Die stdlib-Pfadöffnungen
und die späteren Identitätsreadbacks sind keine atomare FD-gebundene
Namespace-/ABA-Sperre. Insbesondere werden frühere Verzeichnisprüfungen nicht
zu einem beliebig dauerhaften Filesystem-Seal. Ein nach dem überprüften
Zeitpunkt von außen erzeugter Pfad/Companion oder ein später verändertes
Copyfile wird durch ein historisches Receipt nicht automatisch verhindert.
Die eigene Receiptprobe ändert nach Rückkehr allein den neuen Test-Copy und
zeigt genau diese Grenze: das historische Receipt bleibt unverändert und ist
keine neue Live-Validierung. Das ist ausdrücklich dokumentierter Vertrag,
kein verdecktes Quota-/Sandboxversprechen.

## Echte Läufe, eigener Harnessfehler und Windows-Skips

Interpreter: `.pytest_tmp/qa-python312-c-01/Scripts/python.exe`, tatsächlich
Python 3.12.14, SQLite 3.53.1. Alle Läufe verwendeten neue zuvor nicht vorhandene
Workspace-Basetemps, deaktivierte Pytest-Plugin-Autoloads und eigene XMLs.
Es wurden keine früheren Probes, XMLs oder Artefakte entfernt.

| Lauf | Tatsächliches Ergebnis | XML |
| --- | --- | --- |
| independent-01 | 56 passed, 1 failed, 8,48 s | `.pytest_tmp/task45-independent-20260912-01.xml` |
| independent-02 | 57 passed, 1 skipped, 9,07 s | `.pytest_tmp/task45-independent-20260912-02.xml` |
| combined-03 | 197 passed, 2 skipped, 30,33 s | `.pytest_tmp/task45-combined-20260912-03.xml` |

Der erste rote Fall war **kein Produktfinding**: mein Harness nahm fälschlich
an, Windows könne den Parent eines neu geöffneten Child-FDs umbenennen. Der
tatsächliche `Path.rename` scheiterte mit WinError 5 vor dem intendierten
Austausch. Die unveränderten ersten Testbytes wurden vor Korrektur als
`.pytest_tmp/task45-independent-first-harness-20260912.py` bewahrt. Danach
wurde ausschließlich dieser eigene Harness als ehrlicher Plattform-Skip
behandelt und ein separater expliziter Inode-Statmodellfall ergänzt. Die
Produktbytes blieben durchgehend identisch.

Der zweite Skip im kombinierten Lauf ist der unveränderte ältere FD-Test
`test_actual_source_replacement_binds_original_expected_hash`: auch hier
verhindert Windows das Ersetzen der offenen Source. Weder dieser noch der
neue Directory-Skip ersetzt eine entsprechende Linuxprobe. Es gibt keinen
übersprungenen Vollinventur-, UTF-, Schema-, Lifecycle- oder Copy-Profiltest.

Tatsächlich ausgeführter abschließender Befehl:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -o junit_family=xunit1 tests/test_context_storage_copy_owner_review.py tests/test_context_storage_copying.py tests/test_context_storage_inventory.py tests/test_context_storage_integration.py .pytest_tmp/copy-independent-review-20260912-ccr01/test_copy_review_fd.py --basetemp=.pytest_tmp/task45-combined-bt-20260912-03 --junitxml=.pytest_tmp/task45-combined-20260912-03.xml
```

## Identitäten

| Gegenstand | SHA256 |
| --- | --- |
| `context_storage_v2/copying.py` | `15c031ad5727c69b218d3487bc981ad3126e9e285d254822e94597ade09f0b23` |
| `tests/test_context_storage_copying.py` | `efeded8cf3f42dc1aea212c0608d04e1d95b9dfec20844f23b55a3541909332a` |
| Eigene neue `tests/test_context_storage_copy_owner_review.py` | `255eb2f16220790b6e3811fbbe9449a126fbc684fb41c864848db87a989eaf87` |
| `context_storage_v2/inventory.py` | `7e099cd9ed5e5b336519a23cc891e85c2136dda9fa6324c6f433f61bb37e967b` |
| `tests/test_context_storage_inventory.py` | `a5d4a78069b52eb3c4a402b7e90c2d6559b50de62fd00301cef89d9db9de1871` |
| `tests/test_context_storage_integration.py` | `eefe446d224ae3c0b8ba1fcb11f8ad22c0ed82b1f35276cf2c60135cd1862072` |
| Ältere unabhängige FD-Probes | `b084d74d17279e6eff2178ba30c6f0b63cfb4c34bec4c9808701b1a69de83855` |
| Task39-Bericht | `511b868184f0195cf9610e26a96712efaba40385ce90637a3ebe361c4e7ab81a` |
| Task43-Bericht | `ebd1e426ecd210750e3df28b5a2d0e4b080e366bc071d208abfd1d7e882bb81c` |
| Unverändertes erstes eigenes Harness | `9c5b6d89faa629dafa765f2ced2682c89aa58826653d8752d0388306c022fa92` |
| independent-01 XML | `586ec99da50a3aae14a6e5539139d17accbaf91e5a7d915b13dfed4243740f7b` |
| independent-02 XML | `c2d13d261c2a113b6a4d42653e1008fe5f1c866f909ef2410da2bf79c01c000f` |
| combined-03 XML | `ad5a6a770b52ad8e6ae6c281bd202be80ac24928a0d0f946b09b707b26f7f221` |

Die Raw-/Copy-/Reader-Grenze ist damit unabhängig lokal regressionsgeprüft.
Die in Task39 genannten vollständigen zusätzlichen 490.000 source-valid
Belege, 199 Originals, 199 Snapshots, 114 Cutoffs sowie die native Gesamthülle
und B sind aus dieser Evidenz ausdrücklich **nicht** abgeleitet. Der parallele
Task44-Receiptappend-Baustein wurde weder gelesen noch verändert; er benötigt
seinen gesondert zugewiesenen unabhängigen Review.
