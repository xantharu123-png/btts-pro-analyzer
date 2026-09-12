# Task 37 — unabhängiger Review der kleinen nativen Diagnose und ihres Sealers

Stand: 12. September 2026. Reviewer: `c_copy_review`. Auftrag von Root: Task33
Parent/Worker und zusätzlich Task36-Sealer unabhängig prüfen; ausschließlich
eigene ignorierte Probes und diesen Bericht schreiben. Keine Produktänderung,
keine Änderung vorhandener Tests, kein Git, SSH, Upload, Root-Start, Deployment
oder native Linux-Ausführung durch diesen Reviewer.

## Urteil

Der lokale unabhängige Review des unten gehashten gemeinsamen Endstands ist
abgeschlossen. **Kein verbleibender konkreter Fehler im eng erklärten
Diagnosevertrag gefunden. 134 Prüfungen bestanden in 1,73 s, 0 Skips.**
Die Zahl bedeutet nicht, dass native Linux-Pfade ausgeführt wurden: sämtliche
Prozess-/Privilege-/Kernel-Limit-/pidfd-Operationen dieser Prüfungen sind Modelle.
Echte Windows-Dateideskriptoren, Pipe-FDs und eine kleine SQLite-Datei wurden
gesondert tatsächlich verwendet. Autor- und Root-Berichte wurden vollständig
gelesen; deren VPS-Beobachtungen werden hier nicht als eigene Messung ausgegeben.

Damit ist nur der Code-/lokale Protokollreview abgeschlossen. Der spätere kleine
Linux-Diagnoselauf bleibt gesonderte Root-Arbeit mit äußerer Terminalzeit,
Exitstatus und übernommener Custody. Keine C-Korpus-, B-Proof-, transitive
Runtime-, Installer-, Quota- oder Publisher-Freigabe.

## Exakte geprüfte Bytes

Alle folgenden Werte wurden nach dem letzten erfolgreichen Lauf frisch gelesen:

| Datei | SHA256 |
| --- | --- |
| `tests/native_preparation_probe.py` | `3abe69fc4abb9e86eee003e2f56768de9af38cd780dc9d925056a304fd3b47e2` |
| `tests/native_preparation_worker.py` | `22cfd8f16f8c047f298206e2f249d53fc3ef420dfbfff36f35a68c44ecc27d0e` |
| `tests/native_preparation_seal.py` | `10fbfee476904229c9fd74a6ea9e630c9164bc08615fc02cd3d2180bf81186fb` |
| `tests/test_native_preparation_seal.py` | `8152134340f9f46b69a6e37a28d5351f3f64ca536ee52b5e3324760716160f7d` |

Die tatsächlichen drei Helper-Hashes und der Workerhash entsprechen den
Parent-Pins; dies ist zusätzlich eine laufende Assertion, keine Übernahme aus
historischer Prosa. Helpers unverändert:

- Guard `62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4`.
- Kostenbuch `fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478`.
- Supervisor `21c63e0cdf47000c2d3c66e24851635b844a1feb30091d55521ed6dd311f31de`.

## Konkrete Befunde und Abschluss

### 1. Sealer-Quellöffnung konnte vor der Typbindung blockieren — korrigiert

Im ursprünglichen `regular()` konnte ein Austausch Regular→FIFO zwischen
`lstat()` und `open()` schon die Öffnung blockieren, bevor die FD-/Pfadidentität
überhaupt geprüft wurde. CPU30 und spätere Deadlinevergleiche lösen diesen
Wartezustand nicht. Die Linux-Semantik ist in
[fifo(7)](https://man7.org/linux/man-pages/man7/fifo.7.html) dokumentiert.

Original bytegenau erhalten unter
`.pytest_tmp/task37-sealer-baseline-ccr01.py`, SHA
`a1143ee86e5440f38a598cd7cc4e99869bac3c1b8c0bb1e44b93579ed1b469c3`.
Die eigene gleiche Regression war dort RED: **1 failed, 17 deselected**, fehlendes
O_NONBLOCK vor fstat. Root ergänzte genau diese Flagbindung. Auf dem Endstand
prüft dieselbe Regression O_NONBLOCK/NOFOLLOW/CLOEXEC und reicht einen echten
Windows-Pipe-FD an die anschließende echte fstat-Typbindung: Fehler vor jedem
read, FD geschlossen. Eine zweite Probe verwendet einen anderen echten
Regular-FD und bestätigt ebenfalls Nichtlesen sowie unveränderte Ersatzbytes.
Dies ist kein nativ ausgeführter Linux-FIFO-Race.

### 2. Unklare Reap-Custody und verspätete Finalisierung — im Freeze geschlossen

Vor dem Freeze wurden die Signal-/wait4-Ausnahmegrenze und die letzte
Wall-Messung nach Bericht-I/O angesprochen. Der Autor änderte seinen Entwurf
vor Abschluss; hierfür wird kein erfundener ursprünglicher dynamischer RED
beansprucht. Die jetzigen tatsächlichen Controlflow-Tests bestätigen:

- Signalfehler, wait4-Fehler, ECHILD, falsche PID und nichtterminaler Zustand
  führen erneut in modelliertes SIGSTOP, ohne pidfd-Close oder Erfolg.
- Erst genau dieses terminal gereapte Kind schließt die übernommene pidfd
  genau einmal. Der Status bleibt Operator-Custody, nicht Diagnose-Erfolg.
- Eine erst nach 121 s zurückkehrende Report-, stdout-, Directory-Close- oder
  Seals-Close-Phase kann trotz vorher gutem Bericht keinen Exit-0 liefern.
- Danach folgt kein neues Report-I/O; der CLI-Entry benutzt direkt os._exit.
  Der Bericht verlangt ausdrücklich Exit-0 **und äußere terminale Wall-Messung**.

Ununterbrechbares Kernel-I/O und ein wirklich unreapbares Kind bleiben
Operator-/Custody-Ausnahmen, kein behauptetes 120-s-Rückkehrversprechen.

### 3. SQLite-Pfadtraversierung — Root-Befund unabhängig bestätigt, Layout korrigiert

Root fand, dass ein root0700-Outputancestor trotz vorherigem chdir die spätere
SQLite-Öffnung blockiert. Unabhängig gelesen: SQLite benutzt auch bei relativer
Eingabe einen absoluten VFS-Namen; der Pager öffnet diesen anschließend.
Siehe [SQLite-Filename-Vertrag](https://sqlite.org/c3ref/db_filename.html),
[offizieller Pager](https://raw.githubusercontent.com/sqlite/sqlite/master/src/pager.c)
und [Linux-Pfadauflösung](https://man7.org/linux/man-pages/man7/path_resolution.7.html).
Das ist eine Quellenableitung, kein lokaler Linux-Rechteversuch.

Der gemeinsame Endstand erstellt ausschließlich einen **neuen root0711**
Outputcontainer. Parent prüft exakt 0711 und sämtliche Vorfahren mit
child_search=True; root0700/0710/0755/0777 werden vor Start und Bericht abgewiesen.
Journale bleiben root0700, Worker-CWDs nobody0700 und Berichte root0600.
Der Sealer ändert keine existierende Berechtigung. SQLite bleibt eine echte
eigene Datei, kein Ersatz durch eine In-Memory-Datenbank.

Eine echte zusätzliche Windows-SQLite-Probe mit relativer Eingabe bestätigte
den absoluten database_list-Namen und unabhängig nach Close/reopen `(3, 10)`.
Datei 8192 Bytes, SHA
`a187da0a962a5c9335badae67fd31b0bbbec8c0ae662a2436cf5ea4ba37cd073`,
unter `.pytest_tmp/task37-independent-ccr01-final2-base/test_real_windows_sqlite_relat0/probe.sqlite3`.
Die Unix-Traversierungsrechte sind damit nicht nativ geprüft.

### 4. Parent-/Sealer-Dumpable0-Enddiff — geprüft, kein Crash ausgelöst

Parent GET/SET0/GET0 vor Probe-I/O, abschließendes GET0 nach Final-I/O sowie
Sealer SET0/GET0 vor Input-I/O und final GET0 vor Veröffentlichung sind gelesen
und mit modellierten libc-Rückgaben geprüft. Fehlendes/fehlerhaftes SET oder
GET stoppt vor Quell-I/O bzw. verhindert abschließenden Erfolg. Parent prüft
zusätzlich Linux x86_64, Little-Endian und LP64. Die Windows-Prüfung modelliert
LP64 ausdrücklich; sie ersetzt keine echte Linux-ABI-Prüfung.

Beide Root-Prozesse haben anschließend keinen eigenen Exec-/Credentialwechsel.
Die Bedeutung und möglichen Resets des Prozessattributs folgen
[PR_SET_DUMPABLE](https://man7.org/linux/man-pages/man2/PR_SET_DUMPABLE.2const.html).
Keine absichtliche Apport-, SIGSYS-, ARCH-, Segfault- oder Abort-Probe und keine
allgemeine Audit-/Logfreiheit werden behauptet.

## Weitere geprüfte Vertragsbindungen

Der echte Parent-Python-Controlflow wurde gegen feste Modelle ausgeführt:
ein einziges 60-s-Ticket vor jedem Kind, kein Refund, kein per-case Neustart
von Deadline oder Kosten. Die sechs Fälle verwenden exakt ihre festen argv,
CPU-/Wall-/FSIZE-Parameter und UID/GID65534. Parentkosten vor und zwischen Calls
bleiben enthalten; die zurückgegebenen Kinderkosten werden kumuliert und nicht
mit Parent-Supervisorfenstern doppelt gezählt. Bei nicht zurückgegebenen Kosten
bleibt active_native_call ausdrücklich unbekannt und die ganze Reservation
belastet. Reserve-, native-, Stop- und Closefehler ergeben keinen Erfolg.

Decoderprüfungen verwerfen fehlenden Kernelreadback, negative/nichtganzzahlige
CPU, RSS0/RSS>=1GiB, freie Bytes unter4GiB, stderr, falschen Exit/Stopgrund sowie
überlange/mehrzeilige Kontrollausgabe. Die CPU1-/Output-Fälle behalten ihre
getrennten erwarteten Stopsemantiken. Die Worker-Protokollmodelle kontrollieren
EPERM statt beliebigem Fehler, ausschließlich ungültige Exec-Nullargumente,
virtuelles 3GiB-mmap ohne Touch, Unmap bei unerwartetem Erfolg, 4096-B-FSIZE,
kurze/fehlerhafte Writes und exakt begrenztes JSON. Kein Worker-main lief.

Sealer: vollständiger fester Fünf-Dateien-Archivsatz, gehashte Helper,
geschlossene vier Paketnamen, eingefrorene geordnete Inventarliste statt neuer
Copy-Namenssuche, erneute Dateiidentität/Bytes vor Kopie und kompletter
Nachhash vor Publikation. Read-shortcuts, alle neun Identitätsfelder,
atime-Ausnahme, Größenüberlauf, Zero-Write, fsync-Fehler, FD-Close und reales
O_EXCL-Nichtüberschreiben wurden separat geprüft. Kein echtes Root-Sealing.

## Ausgeführte lokale Evidenz

Windows Python3.12.14, SQLite3.53.1; `-B`, Plugin-Autoload aus, Cacheprovider aus,
für jeden Lauf neue Basetemps und XML-Dateien. Laufzeit ist lokale QA und kein
nativer Benchmark. Schlusslauf:

| Teil | Anzahl |
| --- | ---: |
| Eigener Parent-Controlflow/Decoder | 57 |
| Eigener Worker-Protokoll-/Windows-SQLite-Teil | 15 |
| Eigener Sealer-I/O/Protokollteil | 22 |
| Autoren-AST Parent/Worker | 23 |
| Root-Sealer-Parser | 17 |
| Gesamt | 134 |

Eigene Probes und unveränderte Schlussartefakte:

| Artefakt | SHA256 |
| --- | --- |
| `.pytest_tmp/test_task37_probe_review_ccr01.py` | `a608e2503a752ee2cb43c12d8cca6408db9efd930806d86b1d1c490f56f68b83` |
| `.pytest_tmp/test_task37_worker_review_ccr01.py` | `4cfc2ea3a0e66c46a8349a7fc6adcceb331c8b4da2af9e03102e1336dd51cc47` |
| `.pytest_tmp/test_task37_sealer_review_ccr01.py` | `98952d68851c3c8e63c2115c63feae197d065bdab07feec25f2dacf56e9e4412` |
| `.pytest_tmp/task37-independent-ccr01-final2.xml` | `ab380984bf2d62ef1b0dd6c6b0242f11e70077fcd13d6653b0e8d20ae0d0262c` |
| `.pytest_tmp/task33-static-source-20260912-1/test_task33_static.py` | `6b78a0cf583154ade171333587e9a38aacda179dc824ed0239e5db4970f49cdc` |

Erhaltene Vorläufe, nicht als späteres Produktergebnis ausgegeben:

- FIFO-RED XML `task37-sealer-review-ccr01-red.xml`, SHA
  `49cfbd579db2e1198956ef1d0da5231b34825fef6e43c8f1dc164e937cebdac6`.
- Erste Sealer-Gegenprobe 35 passed/0,48s, XML
  `task37-sealer-review-ccr01-green.xml`, SHA
  `4041d8255a4a4744b4951e59144f267aa87f6b59f466856016147715cdf1aa28`.
- Parent/Worker+AST erster Endstandlauf 94 passed/1,31s, XML
  `task37-probe-review-ccr01-run1.xml`, SHA
  `e8ae417319b4b349435a0f960f6e4118f68c976d34efd994dc8d418c5d99881a`.
- Vor Schlusslauf 133 passed/1 eigener AST-Testfehler: Die Assertion suchte
  direkte `root / 'output'`-Argumente statt die tatsächlich gebundene lokale
  Variable `output`. Auflösung plus exakter Binding-Assert ergänzt, kein
  Produktfehler, keine Lockerung auf beliebige Pfade. XML
  `task37-independent-ccr01-final.xml`, SHA
  `5b801ac67a6aa9810a8a28e1c8cdc537ccd77553564a2208085de88cb29a27e5`.

## Grenzen vor dem tatsächlichen Root-Lauf

Root muss frischen geheimnisfreien env-i-Parent, exakte Transfer-/Sealerbytes,
Inputkopie, äußere Kosten über alle Versuche, Terminalzeit/Exit und Operator-
Custody binden. Root berichtete rein lesend keine aktuellen UID65534-Prozesse;
das wurde hier nicht selbst erhoben und garantiert keine späteren fremden
Starts. Durch 0711 bleiben gleichberechtigte nobody-Schreiber eine reale
äußere Namespace-Vorbedingung, keine durch chmod bewiesene Exklusivität.

512MiB Copy-Slot, 64MiB Diagnoseoutput, FSIZE, AS und beobachtete freie Reserve
sind die engen Diagnosegrenzen. Ein periodischer Walk bzw. terminale st_blocks
ist keine globale Allokationssperre, insbesondere nicht für offene unbenannte
Dateien, andere Prozesse oder alle Metadaten. Die endgültigen C-Grenzen
4GiB aktive Inputs inklusive Indizes/Blöcken, 8GiB sämtliche neuen QA-/Build-/
Outputbytes und4GiB Reserve sind hier nicht nativ freigegeben. Positive
MEMORY-journal-SQLite ist zudem ausdrücklich nicht Task27 DELETE/FULL.
