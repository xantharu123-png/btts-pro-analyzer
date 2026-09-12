# Task 19 — unabhängiges Review des Snapshot-Quelladapters

12. September 2026. Reviewer `c_snapshot_review`, nicht Autor des Quelladapters.
Enger Rootauftrag nach Abschluss der C2/C2b-Findings; C-Nutzerfreigabe wie im
Umsetzungsplan dokumentiert. Keine Änderungen an Produktdateien oder den
vorhandenen Owner-Tests, keine Git-, SSH- oder Deploymentaktion.

## Ergebnis und Grenzen

**Keine konkreten verbleibenden Findings innerhalb des geprüften
Snapshot-Source-/Raw-Coverage-Transportvertrags.** Die vollständige neue
`snapshot_source.py`, deren vollständige 83-Fälle-Testdatei, der Task-19-Bericht
und die benötigten kompletten Raw-Inventar-/C2-/C2b-Schnittstellen wurden gelesen.
Die alte Schema-, kanonische JSON- und Snapshot-Persistenzzuständigkeit wurde
gegen die tatsächlichen bestehenden Owner abgeglichen.

**23 eigene unabhängige Gegenproben bestanden**, einschließlich eines echten
SQLite-FULL. Dies ist ein enger lokaler Reviewabschluss an den unten benannten
Hashes; keine allgemeine C-/B-, Quellenautoritäts-, D2-/Modell-, Ressourcenprofil-
oder Deploymentfreigabe. Root besitzt die separate Source→Copy→Parts→Reopen-
Gesamtintegration und die vollständigen Ownerregressionen.

## Unabhängig geprüfte Eigenschaften

### Vollständige rohe Mitgliedschaft statt bloßer Zahlen

- Echte `calculate_context_payload`-/`compute_once`-Ownerfixtures wurden unter
  UTF-8, UTF-16le und UTF-16be gespeichert. Alle drei tatsächlichen Feldbytes
  wurden unabhängig zu den originalen getypten T-/B-/uint64-Frames zusammengefügt.
  Key-Felddigest, Payload-Digest-Felddigest, Raw-Row-Digest und vollständiger
  Tabellen-Digest einschließlich Zeilenzahl stimmen exakt mit dem Ledger und
  dem frisch ermittelten RawInventory überein. Der Payload bleibt als UTF-8-
  BLOB byteidentisch, unabhängig von der SQLite-TEXT-Kodierung.
- Eine selbst vollständig neu gehashte Inventarvorlage, die eine vorhandene
  Nicht-Snapshot-Tabelle mit unselektierten Originalbytes auslässt, wird vor
  allen Adapterausgaben zurückgewiesen. Die vollständige Quelle ist erforderlich,
  nicht nur die Snapshot-Teilmenge.
- Fehlende Ledgerzeilen, zusätzliche Zeilen, gleichzählige fremde
  Raw-Key-Felddigests und vertauschte Parts-Key-/Deskriptordigest-Zuordnungen
  werden bei vollständiger Prüfung zurückgewiesen.
- Ein gefälschtes, vollständig konsistent neu gehashtes Coverage-Manifest kann
  einen wirklichen bekannten Snapshot nicht als `unknown-header`/raw-only
  ausweisen. Auch nachdem seine Parts und Header entfernt wurden und der
  verbleibende reine C2b-Store intrinsisch gültig ist, scheitert die tatsächliche
  erneute Quellklassifikation. Gespeicherte Raw-only-Gründe sind kein Freibrief.

### Bekannte beschädigte Header werden nicht still als unbekannt ausgegeben

Fünf zusätzliche In-envelope-Negative: INTEGER-Schema durch Boolean ersetzen,
`result` entfernen, zusätzliches Top-Level-Feld, nichtfinite Zahl nach dem
bekannten `kind` sowie ein nach dem bekannten `kind` abgeschnittener Header.
Alle fünf brechen den gesamten Aufbau mit `StorageIntegrityError` ab.

Ein vorheriges gültiges Batchobjekt führt dabei nicht zu einer Teilfreigabe.
Vorhandene, ausdrücklich fremde C2-Referenzdaten bleiben exakt erhalten und
weiter vollständig lesbar; die private Aufrufertransaktion bleibt aktiv.

Die bewusst anders behandelten Kategorien bleiben getrennt:

- Physisch falsch gespeicherte BLOB-Keys, TEXT-Payloads und BLOB-Digestfelder
  scheitern schon an der vollständigen typisierten Raw-Aufnahme vor dem ersten
  Adapteroutput.
- Physisch als TEXT gespeicherte ungültige UTF-8-Keybytes werden dagegen
  tatsächlich bytegenau als `invalid-key`/raw-only erfasst. Der unabhängige
  Test bindet das originale einzelne Byte `ff` samt TEXT-Frame; es wird nicht
  als neuer Unicodewert umkodiert oder als adaptierter Snapshot ausgegeben.
- Unbekannte Header und übergroße Nichtreferenzstrukturen bleiben bewusst
  außerhalb des schmalen Adapters. Das ist keine semantische Validierung und
  kein zusätzlicher Reviewbefund; diese Originalquellen dürfen nicht entfallen.

### Lebensdauer und tatsächlicher Fehlerpfad

- Source-Close während des Payloadlesens, nachträglich unzulässiger
  Output-Cache und gefälschtes Blocklimit mit überschriebenem
  Instanz-`__post_init__` liefern keinen erfolgreichen CoverageDescriptor.
  Die neuen Source-Ledgertabellen und Snapshotteile bleiben nach dem Fehler
  nicht als scheinbar erfolgreicher Aufbau stehen.
- Ein tatsächlich verkleinertes SQLite-`max_page_count` erzeugt beim Aufbau
  **SQLITE_FULL**. Geprüft wurden der originale SQLite-Fehlercode als Ursache
  des `StorageLimitError`, das Ausbleiben aller neuen Source-Ledgertabellen
  und die exakte Erhaltung des vorher committeten Refbestands. Die Quelle bleibt
  dabei in derselben unveränderten Lesetransaktion ohne eigene Writes.
- Ein von SQLite beendeter uncommitteter Aufbau wurde nur für die nachfolgende
  read-only Erhaltungsprüfung neu betreten, nicht durch den Adapter fortgesetzt
  oder freigegeben. Ein fremder expliziter Caller-Commit bleibt außerhalb einer
  technisch möglichen rückwirkenden Rücknahme; der Vertrag verspricht dafür
  keine Wiederherstellung eines nie wiederherstellbaren Savepoints.

### Begrenzte Rohdatenverarbeitung ohne Ersatz der Quelle

Ein unbekannter Quellpayload mit einem 4-MiB-Inhalt wurde vollständig über
seinen tatsächlichen BLOB gestreamt. Das Ledger bindet exakt dessen vollständigen
SHA256 und Bytecount; es enthält `unadapted`, `unknown-header`, keinen Parts-Key
und keine erzeugte Referenzmenge. Der aktuelle gehaltene Quellinput ist für die
erneute Coverageprüfung notwendig; nach Source-Close schlägt sie fehl.

Während dieser Adaptierung mit 64-KiB-Blöcken wurden **240.442 zusätzliche
Python-Allocatorbytes** gemessen. Der Probeaufbau liegt ausdrücklich vor der
`tracemalloc`-Messung. Dies ist lokale zusätzliche Pythonallokationsevidenz,
kein gesamter Prozess-RSS-/AS-/CPU-/VPS-Nachweis und kein 4-/8-GiB-Stresstest.

## Tatsächlich ausgeführte unabhängige Suite

Eigenes, endgültiges Reviewmodul:
`.pytest_tmp/test_c19_independent_source_review_20260912_1.py`
SHA256 `9aba24bd0b204cb5bcbf6b5de63b971ef234c17936776c6fdd5bfc454dc08186`.

Letzter Lauf: **23 Tests bestanden, 0 Fehler, 3,594 s, Exit 0**.
JUnit `.pytest_tmp/c19-independent-source-run-20260912-2.xml`.
Neuer Basetemp `.pytest_tmp/c19-independent-source-run-20260912-2`.
Der vorangehende 22-Fälle-Lauf war ebenfalls grün; die endgültige Suite ergänzt
die unabhängig erzeugte echte SQLite-FULL-Probe. Keine roten Produktbefunde
wurden dabei kaschiert oder durch schwächere Erwartungen entfernt.

Gebündelter Python:
`C:/Users/miros/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`,
`PYTHONPATH=C:/Projekt/BetBoy/betboy-app/.venv/Lib/site-packages`,
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTHONDONTWRITEBYTECODE=1`,
`-p no:cacheprovider -o junit_family=xunit1`. Alle eigenen Ausgabe-/Basetemppfade
waren vorher nicht vorhanden; kein Alt-QA-Verzeichnis wurde gelöscht.

Die vom Autor gemeldeten 83 Ownerfälle beziehungsweise 315 kombinierten Fälle
wurden als vorhandene Owner-Evidenz gelesen, aber nicht als eigene Ausführung
dieses Reviews ausgegeben.

## Vor und nach den Gegenproben bestätigte Produkthashes

- `context_storage_v2/snapshot_source.py`:
  `f080d605dbbaf45baae197f9f948539d8ff832a2b294327cdc845d4d6df31753`
- `tests/test_context_storage_snapshot_source.py`:
  `67662d8b7965620d18ef6b6a9e30fb006314b345b377805990da5f9c48379f34`
- `context_storage_v2/inventory.py`:
  `7e099cd9ed5e5b336519a23cc891e85c2136dda9fa6324c6f433f61bb37e967b`
- `context_storage_v2/refs.py`:
  `e80492be96ea0aacd5bb2038018c90bf8201d3e4a616d2574c456d5f9899cb2b`
- `context_storage_v2/snapshots.py`:
  `75bfe759505d7b9a0719844ab397f2a86f0d05cf059d4a93a261f6a961539909`

Keine Originalquelle, Produktdatei, Produktregel oder bestehende Owner-Testdatei
wurde von diesem Reviewer verändert. Public Raw-/Coverage-Digests bleiben
Byteidentitäten ohne eigene Publikations- oder Empirieautorität. Die offene
native Ressourcenabnahme, kompletten Wachstumsbestände, Backup-/Restore- und
verlustfreien Umstellungs-/Rollbackpfade bleiben ausdrücklich bei C/B und Root.
