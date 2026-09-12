# Task 33: versionierte native Integrationsdiagnose, noch nicht ausgeführt

Stand: 2026-09-12. Owner: `c_snapshot_review`. Besitz ausschließlich der zwei
neuen Probe-Skripte, dieses Berichts und eigener ignorierter Strukturprüfungen.
Kein alter Produktcode, Kostenbuch, Guard, Supervisor, Git, Server oder Live-
Datenbestand wurde durch diesen Task verändert. Root übernimmt Transfer,
geschützte Seals, unabhängigen Review und einen eventuellen späteren VPS-Aufruf.

## Ergebnis und eingefrorene Bytes

Die Version-1-Diagnose ist als Code vorbereitet. **Sie wurde weder importiert
noch ausgeführt**, auch nicht auf diesem Windows-Host. Nur AST-Parsing, Compile-
ohne-Exec und 23 statische Strukturprüfungen liefen. Das ist keine native Linux-,
CPU-, SQLite-, NumPy-/SciPy-, Ressourcen-, Kosten- oder C/B-Abnahme.

| Datei | SHA256 |
| --- | --- |
| `tests/native_preparation_probe.py` | `3abe69fc4abb9e86eee003e2f56768de9af38cd780dc9d925056a304fd3b47e2` |
| `tests/native_preparation_worker.py` | `22cfd8f16f8c047f298206e2f249d53fc3ef420dfbfff36f35a68c44ecc27d0e` |
| `.pytest_tmp/task33-static-source-20260912-1/test_task33_static.py` | `6b78a0cf583154ade171333587e9a38aacda179dc824ed0239e5db4970f49cdc` |
| `.pytest_tmp/task33-static-run-20260912-3.xml` | `c8e9d3a1786ced802ae527b53eb3804ed3feff8eb18b29e8e07e1c9037e54b5a` |

Der Parent pinnt den Worker sowie diese drei vollständig gelesenen Helper:

| Helper-Modulname | SHA256 |
| --- | --- |
| `context_preparation_process_guard` | `62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4` |
| `context_preparation_budget` | `fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478` |
| `context_preparation_supervisor` | `21c63e0cdf47000c2d3c66e24851635b844a1feb30091d55521ed6dd311f31de` |

Keine neue Codevariante wird anhand eines beliebigen Manifest-Digests nachgeladen.
Eine Änderung dieser Pins braucht neue Codebytes und erneuten Review.
`c_copy_review` erhielt diese exakten finalen Skript-SHAs für Task 37.

## Schnittstelle und Manifest

Nur nach abgeschlossenen äußeren Gates, **kein in diesem Task ausgeführter
Befehl**:

```text
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -S -B /SEAL/native_preparation_probe.py --manifest /SEAL/manifest.json --manifest-sha256 LOWERCASE_SHA256 --directory /SEAL/OUTPUT_EMPTY_0711
```

Die drei Optionen sind in genau dieser Reihenfolge erforderlich. Es gibt keine
Resume-, Repair-, Retry-, beliebige Worker-, Plattform-Fallback- oder Assurance-
Boolean-Option. Die Child-Identität ist für diese Diagnose fest UID/GID 65534.
Der Parent setzt eine bereits vorhandene Umgebung nicht nachträglich sauber.
Aktuell muss sie exakt aus PATH=/usr/bin:/bin und LANG=C.UTF-8 bestehen.

Der frische ursprüngliche `env -i`-Aufruf ist trotzdem eine äußere Pflicht:
bereits gelöschte Umgebungs-/Heap-Secrets sind nicht nachträglich ausschließbar.
Der Parent darf niemals B-Proofkey, andere Secrets oder Produktimporte gehalten
haben. Fork ohne Exec kopiert den bisherigen Heap. Er ist **kein B-Publisher**.

Nach Roots Konsistenzprüfung zum tatsächlich vorhandenen Apport-Pipe-Host
verengt auch der Parent seine eigene Dumpability: gültiges PR_GET_DUMPABLE vor
dem SET, genau ein PR_SET_DUMPABLE=0 und bestätigtes GET=0 vor Probe-/Manifest-/
Journal-I/O. Nach sämtlicher Final-I/O wird GET=0 nochmals verlangt. Der rein
stdlib Parent hat keinen späteren Exec- oder Credential-Transition-Pfad. Das
ändert nur diesen frischen Prozess, keine globale Hostkonfiguration und keine
zusätzliche Filterpolicy. CORE0 allein wäre bei Pipe-Handlern nicht ausreichend,
wie [core(5)](https://man7.org/linux/man-pages/man5/core.5.html) beschreibt.
Die Operation und das Rücklesen folgen
[PR_SET_DUMPABLE(2)](https://man7.org/linux/man-pages/man2/PR_SET_DUMPABLE.2const.html)
und [PR_GET_DUMPABLE(2)](https://man7.org/linux/man-pages/man2/PR_GET_DUMPABLE.2const.html).
Keine allgemeine Audit-/Logfreiheit oder native Hostbeobachtung dieses Agenten
wird daraus abgeleitet. Linux x86_64 LP64/Little-Endian wird auch am Parent
aus realer Plattform-, Pointer- und Long-Breite geprüft.

Das höchstens 16-KiB-Manifest hat ausschließlich diese Schlüssel:

| Schlüssel | Vorgabe |
| --- | --- |
| `format` | `betboy-native-preparation-probe-v1` |
| `version` | echter Integer `1` |
| `helper_directory` | absoluter separater rootgeschützter Helperpfad |
| `helper_sha256` | exakt die drei Modulnamen/Pins aus obiger Tabelle, ohne `.py` in den Keys |
| `probe_path`, `probe_sha256` | absoluter tatsächlich gestarteter Probe-Pfad und seine SHA256 |
| `worker_path`, `worker_sha256` | absoluter Worker-Pfad und oben gepinnte SHA256 |
| `dependency_directory` | separater, expliziter rootgeschützter NumPy-/SciPy-Pfad |
| `dependency_closure_sha256` | vom äußeren Root-Sealer gebundener vollständiger Baumdigest |
| `python_executable`, `python_sha256` | tatsächliches `/proc/self/exe`-Ziel und dessen SHA256 |
| `worker_uid`, `worker_gid` | echte Integer `65534`, `65534` |

Alle SHA256-Werte sind 64 Kleinbuchstaben-Hexzeichen. Doppelte/fehlende/fremde
JSON-Keys sowie Bool/Float statt Manifest-Integer werden verworfen. Dateipfade
sind absolute kanonische Einzel-Slash-Pfade ohne Symlinks, `..` oder NUL. Der
CLI-Aufruf darf den üblichen Systemlink `/usr/bin/python3` verwenden; im Manifest
steht dagegen beispielsweise dessen tatsächlich beobachtetes Ziel
`/usr/bin/python3.12`. Der entsprechende Binärhash muss von Root frisch ermittelt
werden. Eine Python-Binärdatei über 64 MiB wird von dieser kleinen Probe abgewiesen.

Die Manifest-SHA auf der Kommandozeile und die eigenen Dateihashes ersetzen
keine Authentifizierung des ursprünglichen Root-Aufrufs. Die geschützte äußere
Closure bleibt die Vertrauenswurzel; die Probe baut dafür keine neue Autorität.

## Verzeichnisse, Laden und Schreibgrenzen

Beispielstruktur des von Root separat angelegten neuen Seals, nicht vorhandene
App-Pfade umchmodden:

```text
/SEAL/                         root-owned, für nobody traversierbar
  native_preparation_probe.py  root-owned, readonly
  native_preparation_worker.py root-owned, readonly und nobody-lesbar
  manifest.json               root-owned, readonly
  helpers/                    getrennt, rootgeschützt
    context_preparation_process_guard.py
    context_preparation_budget.py
    context_preparation_supervisor.py
  deps/                       getrennte rootgeschützte Dependency-Kopie
  OUTPUT_EMPTY_0711/           vorher neu, leer, root; nur Suchrecht für andere
    journal-diagnostic/       neu, root 0700
    journal-roundtrip/        neu, root 0700
    journal-recovery/         neu, root 0700
    positive/                 neu, nobody 0700
    denials/                  neu, nobody 0700
    fsize/                    neu, nobody 0700
    address_space/            neu, nobody 0700
    cpu/                      neu, nobody 0700
    output/                   neu, nobody 0700
    report.json               neu, root 0600, höchstens 64 KiB
```

Die Probe hält tatsächliche Directory-/File-FDs, verwirft symlinkende oder
group/world-writable Eingabepfade und verlangt Root-Ownership bis zur Wurzel.
Eingabedateien sind regulär, einzeln verlinkt und bounded. Source-Lesen ist auf
128 KiB pro Skript/Helper begrenzt. Vor jeder Ausführung werden gehaltene Inodes,
Dateimetadaten und zugehörige Verzeichniseinträge erneut abgeglichen. Root-
Dateimutationen, globale Namespace- oder VM-Rollbacks werden damit nicht als
unmöglich behauptet. Verzeichnis-Linkcounts dürfen sich durch eigene neue
Output-Unterverzeichnisse ändern; nur Dateien müssen unverlinkt bleiben.

Nur die exakt gehashten Helperbytes werden unter den drei erlaubten Modulnamen
im Parent kompiliert/geladen. Der Parent verändert seinen Importpfad nicht und
importiert keine App-Pakete, `site` oder `.pth`-Dateien. Der separate Worker wird
im bereits vollständig gedroppten, bewachten, gestoppt geprüften Kind via runpy
geladen. Erst dessen tatsächlicher UID-/Cap-/Dumpable-/Thread-Check geht dem
Einfügen des expliziten Dependency-Pfads und den NumPy-/SciPy-Imports voraus.

Worker, Dependency- und sämtliche Output-Ancestors brauchen Suchrecht für
nobody, der Worker selbst Leserecht. Der Supervisor wechselt vor UID-Drop in
das neue Child-CWD. Ein root0700-Outputancestor genügte dennoch nicht: SQLite
3.45.1 `unixFullPathname` bildet auch aus relativen Eingaben einen absoluten
Pfad und `appendOnePathElement` führt lstat auf den absoluten Zwischenpfaden
aus; EACCES ergibt CANTOPEN. Root fand diese konkrete Layoutabweichung, und
dieser Agent las die betreffenden Routinen anschließend selbst in der
[offiziellen SQLite-3.45.1-Quelle](https://raw.githubusercontent.com/sqlite/sqlite/version-3.45.1/src/os_unix.c).
Die [VFS-Spezifikation](https://www.sqlite.org/c3ref/vfs.html) bindet xOpen an
den von xFullPathname zurückgegebenen Namen.

Darum verlangt die korrigierte Probe ein **frisches root0711-Outputverzeichnis**:
für andere nur durchsuchbar, nicht list- oder schreibbar. Die neu erzeugten
Journaldirectories bleiben root0700, die Child-CWDs nobody0700 und die
Kontrollberichte root0600. Alle Output-Vorfahren werden vor Admission ebenfalls
auf nobody-Suchrecht geprüft. Kein existierender Pfad wird umchmoddet. Andere
bereits laufende Schreiber derselben UID65534 werden dadurch nicht ausgesperrt;
die äußere geschlossene/quieszente Namespace-Aufnahme bleibt erforderlich.
Der Worker verwendet eigene relative Schreibnamen und TMPDIR=`.`. SQLite- und
FSIZE-Dateiname werden vor erstem Schreiben mit O_EXCL angelegt. Es wird nicht
auf eine In-Memory-Datenbank als Ersatz zurückgefallen. Keine vorhandene
Datenbank und kein App-/Live-Pfad wird geöffnet.

Root meldete separat eine readonly Inventur der vier vorhandenen Pakete
`numpy`, `numpy.libs`, `scipy`, `scipy.libs`: 3729 Dateien, 207288087 Bytes,
Inventar-SHA256
`eb6679f2264b26bf998b7efdae0f3ad57c0a18dd1597a8201ed6054cbebfd55c`.
Diese Hostinventur wurde von diesem Agenten nicht selbst ausgeführt. Root bindet
und vergleicht die neue vollständig rootgeschützte Kopie separat; ihr geplanter
512-MiB-Slot gehört **nicht** zum 64-MiB-Probeoutput. Die Probe trägt den
Dependency-Closure-Digest im Identitäts-/Kontrollbericht, behauptet aber selbst
keinen vollständigen Dependency-Dateibaumhash oder transitive Runtime-Abnahme.

Das Outputverzeichnis muss vor jeder ersten Mutation tatsächlich leer und
root-owned0711 sein. Bei fehlgeschlagener Leerprüfung wird auch kein Fehlerbericht dort
angelegt. Alle Berichtdateien und Verzeichnisse sind exklusiv neu; kein Löschen,
Truncaten, Überschreiben, Aufräumen oder Weiterbenutzen eines alten Verzeichnisses.
Eine partielle/corrupte Ausgabe bleibt zur Untersuchung liegen.

## Genau sechs native Teilproben

Alle Calls verwenden die öffentliche Schnittstelle:

```text
run_single_process((ABSOLUTE_WORKER, MODE, ABSOLUTE_DEPS, "65534", "65534"),
                   uid=65534, gid=65534, cwd=NEW_CHILD_DIRECTORY,
                   workspace_fd=HELD_CHILD_DIRECTORY_FD,
                   file_size_bytes=FIXED_LIMIT,
                   cpu_seconds=FIXED_CPU, wall_seconds=FIXED_WALL)
```

| Modus | CPU / Wall | FSIZE | Erwartung |
| --- | --- | --- | --- |
| `positive` | 15 / 25 s | 512 KiB | NumPy/SciPy lösen 2x2-System zu `[2,2]`; eigene SQLite berechnet Summe 10 |
| `denials` | 3 / 10 s | 4096 B | tatsächliches EPERM für fork, pthread_create, clone3, execve/execveat, Dumpable-Setter |
| `fsize` | 3 / 10 s | 4096 B | erste 4096 B erfolgreich, nächste Erweiterung EFBIG, Datei bleibt 4096 B |
| `address_space` | 3 / 10 s | 4096 B | 3-GiB-Anonymous-mmap bei AS=2 GiB liefert ENOMEM; kein großer physischer Touch |
| `cpu` | 1 / 8 s | 4096 B | echtes CPU1-Hardlimit führt zu SIGKILL, mit terminaler wait4-CPU-Messung |
| `output` | 3 / 8 s | 4096 B | echte Überschreitung des 1-MiB-Ausgabelimits; exakt 1 MiB+1 beobachtet |

Die positive SQLite-Probe setzt MEMORY-Journaling, MEMORY-Tempstore und maximal
64 Seiten zu 4096 B. Sie ist nur minimale SQLite-/Numerik-Kompatibilität und
**kein Task-27-DELETE/FULL-Writerprofil, C-Korpus, Modell-/Semantiktest oder
fresh-single-main-v1-Nachweis**. Es gibt keinen Netzfall.

`pthread_create` liefert seinen Fehlerwert direkt; er wird nicht mit libc errno
verwechselt. Der konkrete Rückgabewert muss EPERM sein, EAGAIN aus NPROC allein
reicht nicht. Die API-Rückgabesemantik ist in
[pthread_create(3)](https://man7.org/linux/man-pages/man3/pthread_create.3.html)
dokumentiert. Ein unerwartet entstandenes Fork-Kind exitet sofort und wird
lokal reapend verworfen; dieser ganze Probeversuch ist dann fehlgeschlagen,
voll verrechnet und keine Einprozess-/vollständige Kostenfreigabe.

Die Exec-Negativproben haben ausschließlich ungültige Nullargumente, damit auch
eine defekte Freigabe keinen gewollten Programmwechsel auslöst. Es gibt weder
vfork-Shared-Stack-Experimente noch native ARCH/x32/SIGSYS-, Abort-, Segfault-
oder andere absichtliche Core-Crashproben. Die AS-Probe benutzt weder
MAP_POPULATE noch Lesen/Schreiben des angefragten großen Bereichs; ein
unerwarteter Mapping-Erfolg wird sofort ohne Touch unmapped und als Fehler
behandelt. FSIZE fängt SIGXFSZ ab; CPU1 ignoriert SIGXCPU und verlangt SIGKILL.
FSIZE/AS/CPU haben die unterschiedlichen Bedeutungen aus
[getrlimit(2)](https://man7.org/linux/man-pages/man2/getrlimit.2.html), keine
globale physische Speicher- oder Platten-Quota.

## Native Messung, Kosten und gemeinsame Deadline

Die tatsächlichen Parent-Readbacks, pidfd-Bindung, SIGSTOP/Resume und wait4-
Messungen kommen ausschließlich aus dem gepinnten Supervisor. Der Bericht
speichert jedes zurückgegebene NativeRunResult vor seiner Ergebnisprüfung,
einschließlich Stopgrund, Exitcode, CPU, Eltern-CPUfenster, Elapsed, RSS,
Free-Space-Minimum, maximaler Messlücke und gestopptem Kernel-Readback.
RSS ist das Maximum aus beobachtetem VmHWM **und** terminalem wait4 ru_maxrss;
der aktuelle Supervisor exponiert diese beiden Quellen nicht als getrennte
Zahlen. Worker-Dumpable0-Beobachtungen werden getrennt als Workerbeobachtung
bezeichnet, nicht als zusätzlich erfundenes Parent-/proc-Dumpable-Feld.

Stdout und Stderr werden nicht als große neue Dateien gespeichert. Der Bericht
enthält ihre behaltenen Prefix-Längen, je einen SHA256 und 128 Bytes Hexvorschau.
Der Supervisor-Outputdigest bindet seinen tatsächlich beobachteten,
kanalgerahmten Readorder-Prefix, **kein vollständiges/deterministisches
Anwendungslog**. Ein fehlgeschlagener Call ohne zurückgegebenes Terminalresultat
wird ausdrücklich als Call ohne vollständige zurückgegebene Kosten markiert.

Vor dem ersten Kind wird eine echte ganze 60-CPU-Sekunden-Reservation im
Diagnosejournal geschrieben. Die sechs Kinderlimits summieren sich auf 28 s;
der Parent setzt ein eigenes 15-s-Hardlimit, also 43 s konfigurierte Summe mit
weiterem Abstand zur 60-s-Reservation. Parent AS=2 GiB, CORE=0 und FSIZE=1 MiB
werden ebenfalls real gesetzt und rückgelesen. Diese Sekundensumme ist keine
erfundene nanosekundengenaue Kernel-Messung. Die tatsächlichen verfügbaren
Kinderkosten plus vollständige beobachtete Parent-process_time werden gegen
die 60-s-Grenze geprüft; Parentkosten aus den Supervisorfenstern werden dabei
nicht nochmals doppelt addiert.

Der Parent kann seine eigene nach dem letzten Sample verbleibende Reporting- /
Exit-CPU nicht terminal selbst messen. Darum wird **auch bei sechs erfolgreichen
Teilproben kein Refund gebucht**: das echte Diagnosejournal bleibt mit voller
60-s-Reservation dauerhaft STOP. Dies ist konservative Buchung, keine native
Mess-/Refundautorität und kein B-Proof. Der gesamte Testjournal-Aufwand läuft
innerhalb dieses selben voll verrechneten Diagnoselaufs.

Die gemeinsame 120-s-Frist beginnt konservativ beim auf Kernel-Ticks
abgerundeten tatsächlichen Prozessstart. Quelle des Startticks ist Feld 22 von
`/proc/self/stat`; dessen Einheit beschreibt
[proc_pid_stat(5)](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html).
CLOCK_BOOTTIME berücksichtigt Unterbrechung/Suspend. Die Frist wird nie für einen
neuen Modus neu gestartet. Vor einem Start müssen der gesamte feste Modus-Wall-
Slot plus zehn Sekunden Rest passen; Clock-Rollback und jede bekannte
Überschreitung stoppen. Nach Bericht-fsync, kleinem stdout-Record und FD-Close
folgt nochmals derselbe globale Frist-/CPU-Check, danach ohne weitere I/O
direkter `os._exit`. Ein verspätet zurückkehrender Final-I/O-Pfad darf daher
keinen Exit-0-Erfolg ergeben.

Der unveränderliche Bericht ist ausdrücklich eine **Vor-Exit-Beobachtung**.
Ein guter Status darin allein genügt nie: Root muss zusätzlich den wirklichen
Exitcode 0 und die äußere terminale Wall-Messung festhalten. Ein Prozess kann
seinen eigenen nachfolgenden Terminalzeitpunkt nicht aus einem JSON-Feld
beweisen. Dauerhaft blockierendes Kernel-I/O ist nicht durch einen Python-
Deadlinevergleich magisch terminierbar; die äußere Operator-/Custody-Grenze
bleibt vor nativer Ausführung zu binden.

## Separate echte Linux-Testjournale

Die beiden zusätzlich klar benannten Journale prüfen öffentliche Kostenbuch-
APIs mit realem Linux-FD/flock/fsync-I/O, aber ausdrücklich synthetischen
Buchungsclaims. Sie berechtigen zu keinem zusätzlichen Workerstart.

- Roundtrip: Create, 1-s-Reservation, synthetischer 1-ns-Claim, abgewiesene zweite
  identische Settlement, Close und frisches Open mit unverändertem ursprünglichem
  Deadline-/Charged-Zustand.
- Recovery: Create, 1-s-Reservation, Close ohne Settlement; zwei frische Opens
  müssen den vollen Charge und dieselbe Deadline behalten. Sowohl Reserve als
  auch ein Nullkosten-Refund des alten Tickets müssen jeweils BudgetStopped
  liefern. Kein weiterer Job wird daraus gestartet.

Es gibt keinen simulierten Crash/Powerloss als Ersatz für echte Hardware-
Durability. Diese Closed/Open-Protokollprobe beweist weder physische
Stromausfallsicherheit noch Authentifizierung, Root-Namespace-Schutz oder eine
globale Registry. Ein privilegiertes Löschen oder neues Verzeichnis mit gleicher
Identität kann dieses Skript nicht autoritativ verhindern; Root muss über
sämtliche expliziten Diagnoseversuche hinweg die äußere persistente Zulassung
und Kostenrechnung behalten. Es gibt hier keine automatische Retry-Schleife.

## Artefakt- und Custody-Grenzen

Der feste neue Artefaktplan liegt unter 64 MiB: drei maximal 1-MiB-Journale,
höchstens zwei 64-KiB-Kontrollberichte, ein maximal 256-KiB-SQLitefile, ein
4096-B-FSIZEfile sowie ein konservativer 16-MiB-Verzeichnisaufschlag. Es entstehen
keine Roh-Outputlogs. Nach jedem bekannten Teilresultat und beim Abschluss
werden ausschließlich bekannte eigene Verzeichnisse bounded inventarisiert;
fremde/fehlende Namen, Symlinks, Zusatzlinks, Eigentümerwechsel oder Größenfehler
stoppen. Logische Größen und reale st_blocks der regulären Dateien werden
ausgewiesen. Das ist kein universeller Beweis über Dateisystem-Metadaten,
fremde Allokationen oder eine globale physische Quota. Insbesondere gibt es
keine native 8-GiB-Physikfreigabe aus diesem kleinen Lauf.

Bei `UnreapedChild` bleibt die ganze Reservation erhalten. Der Probe-Parent
publiziert begrenzte Custody-Daten mit seiner PID, direkter Child-PID und dem
tatsächlich gehaltenen pidfd (gegebenenfalls noch None bei frühem Acquisition-
Fehler) und hält sich per SIGSTOP an, ohne diese Custody zu schließen. Die
Ausgabe heißt ausdrücklich `operator-custody-required-NOT-complete`.

Nur ein späteres explizites Operator-Resume erlaubt einen erneuten Kill-/
nichtblockierenden wait4-Versuch. Unbekannte Signal-/wait4-Fehler halten diesen
Parent weiter an; kein stiller Exit verwirft den pidfd. Erst bestätigtes
terminales Reaping dieses eigenen Kindes schließt die Custody. Dies ist **kein
garantiert in 120 s vollständig beendeter Diagnoselauf** und darf keinen
automatischen Wiederholungsjob oder Refund auslösen. Root muss vor dem echten
Aufruf diese seltene Kernel-/Operator-Ausnahme ausdrücklich übernehmen.

## Lokale Prüfung und offene Gates

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -m pytest .pytest_tmp/task33-static-source-20260912-1/test_task33_static.py -q -p no:cacheprovider --confcutdir=.pytest_tmp/task33-static-source-20260912-1 -o junit_family=xunit1 --basetemp=.pytest_tmp/task33-static-run-20260912-3 --junitxml=.pytest_tmp/task33-static-run-20260912-3.xml
```

**23 passed in 0,23 s.** Die Testdatei liest nur Sourcebytes und ASTs. Kein Probe-
Import, kein Helperimport, kein Probe-main, kein Worker und kein nativer Call
wurde ausgeführt. Geprüft wurden unter anderem Hashpins, stdlib-/Child-Import-
Trennung, genau sechs feste Slots, geschlossene Manifestkeys, exklusives
Erzeugen ohne Destruktion, Reservation vor Launch ohne Diagnose-Refund, finaler
Fristcheck nach I/O, breite Custody-Exception-Verwahrung und Ausschluss
absichtlicher Core-/ARCH-Crashproben. Das ist strukturelle, keine native oder
vollständige dynamische Fehlpfad-Evidenz.

Erhaltene Vorentwurf-Evidenz, keine Freigabe der später veränderten Bytes:

- Vor Parent-Dumpable-Verengung: Parent-SHA
  `9aaf50df333466ee7290d789c2b7d6d34ad508de1e70b31541d0bf2d31696eb6`,
  21 AST-Checks in 0,20 s, XML `task33-static-run-20260912-1.xml`, SHA
  `b76d50229b81f9ed93aa38dff09ccfe5a01d0d76e528a6d0d4647aa96232a7f4`.
- Nach Dumpable0, vor korrigiertem SQLite-VFS-Layout: Parent-SHA
  `476e68b381748a5de11510b24921f79f4dd54d0d86f809066b75937a85b49308`,
  22 AST-Checks in 0,22 s, XML `task33-static-run-20260912-2.xml`, SHA
  `7b367252d44b6c488dfe5cf66ab899a52159ca10b62e570c5bc40e4705ca49ce`.
- Beide Vorentwürfe hatten Worker-SHA
  `cc78feba37fcb55df45b80fe22e55d189cba3e9885d434cb7c2c43f12d97deaa`.
  Seine Rechen-/Syscall-Pfade sind unverändert; nur der falsche Kommentar zur
  Output-0700-Traversierung wurde beim finalen VFS-Fix berichtigt.

Keine dieser Versionen wurde durch diesen Agenten nativ gestartet. Die beiden
konkreten Ergänzungen wurden nicht aus grünen AST-Zahlen heraus wegargumentiert.

Offen vor einem ersten echten Lauf: vollständiger unabhängiger Review von genau
diesen Bytes (Task 37), Root-Sealer-/Helper-/Runtime-/Dependency-Closure, frischer
geheimnisfreier Parent, tatsächliches Outer-Elapsed/Exit-/Operator-Custody-
Verfahren und natives kompatibles Kernel-/Ressourcenprofil. Erst ein späterer
kleiner Root-Lauf kann die sechs nativen Erwartungen bestätigen. Keine der
statischen Zahlen autorisiert einen C-Korpus, B-Proof, Publisher, Deployment
oder bestehende Modelländerung.

Verwendeter Skill: `security-best-practices`. Seine Python-Referenzen sind
Webframework-spezifisch; für diese stdlib-/Kernel-Grenze wurden stattdessen
Primärquellen herangezogen. Der Skill beeinflusste insbesondere den geheimnis-
freien Parent, unveränderliche Defaults, explizite Grenzen und fail-closed
Behandlung unbekannter Kosten/Custody, nicht die bestehenden Produktregeln.
