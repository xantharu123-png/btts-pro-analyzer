# Task 36 — getrennte Installation der kleinen nativen Diagnose

Stand 12. September 2026. Root hat einen engen stdlib-Sealer und 17 portable
Parserprüfungen erstellt. **Noch nicht auf dem VPS ausgeführt**, keine Probe,
Produktivdatenbank oder App gestartet/geändert. Task37 prüft ihn zusätzlich
zur getrennten Task33-Probe unabhängig. Das ist weder B-Installer noch eine
vollständige transitive Runtime-/Sandbox-/Quota-Abnahme.

## Tatsächliche reine Vorprüfung

Native existierende QA-Laufzeit unter
`/tmp/betboy-context-qa.9xr68INa/venv/lib/python3.12/site-packages`:

| Paket | Dateien | Logische Bytes |
| --- | --- | --- |
| numpy | 1311 | 40512963 |
| numpy.libs | 3 | 28266427 |
| scipy | 2410 | 107342596 |
| scipy.libs | 5 | 31166101 |
| Gesamt | 3729 | 207288087 |

Vollständige geordnete Pfad/NUL/Größe/NUL/Datei-SHA-Bytes-Inventur:
`eb6679f2264b26bf998b7efdae0f3ad57c0a18dd1597a8201ed6054cbebfd55c`.
Gemessene reine Inventur-CPU 2,413276041 Sekunden. Kein Download, keine Kopie.
Ein erster lesender Inventurversuch verglich irrtümlich das ganze stat_result
einschließlich Zugriffszeit und stoppte mit „source changed“. Die Wiederholung
bindet Gerät/Inode/Typ/UID/GID/Links/Größe/mtime/ctime und vollständige Bytes;
atime ist bewusst nicht als Inhaltsidentität ausgegeben. Keine nachgewiesene
inhaltliche Quellenänderung aus dem ersten Fehler behauptet.

VPS-Python3.12.3, tatsächliches Ziel `/usr/bin/python3.12`. Rein lesend bestätigt:
frischer `env -i PATH=/usr/bin:/bin LANG=C.UTF-8 ... -I -S -B`-Start besitzt
exakt diese zwei Python-Environmentfelder. Benutzer nobody UID/GID65534 existiert.
Die bestehenden App-/QA-Pfade sind für ihn nicht durchsuchbar und nicht
rootversiegelt. Ihre Rechte werden nicht verändert; stattdessen neue getrennte
Kopie ausschließlich der vier genannten bestehenden Pakete.

## Neue enge Installation

- Reviewed/versioned Sealer wird aus dem lokalen Original an einen frischen
  root-Python-stdin-Prozess geschickt; kein Import/Exec eines user-writable
  hochgeladenen Skripts als Root.
- Ein unverändert gehashtes Git-Tar mit genau drei Helpers und den zwei
  Task33-Skripten, maximal1MiB, wird nur in gehashte Bytes dekodiert. Kein
  allgemeines extractall, kein Symlink-/Pfad-/Extra-Datei-Akzeptanzpfad.
- Nur neue rootprivate `betboy-native-probe-*`-Allokation unter `/var/lib`.
  Copy-Slot512MiB, Probeoutput64MiB, Archiv-/Metadaten separat reserviert;
  zusätzlich mindestens4GiB tatsächlich frei. Alle Fehler bleiben erhalten.
- Vorher vollständiger Paketmanifest-Abgleich; danach ausschließlich exakt
  diese festgehaltenen Pfade kopieren, mit erneuter File-ID und Bytehashprüfung.
  Finale vollständige Kopie erneut hashen, reale physische Endallokation lesen.
- Rootdir bleibt0700 bis alle Prüfungen passen. Erst dann neue Code-/Paketpfade
  rootgeschützt und für nobody les-/durchsuchbar; neuer Ausgabecontainer0711,
  darin Journalordner root0700, Workerordner nobody0700 und Reports root0600.
  Fremde können den Container nicht auflisten/beschreiben oder Journale lesen.
  Keine bestehende Datei/Berechtigung verändert, nichts gelöscht.
- Frischer Sealer CPU30/AS512MiB/FSIZE128MiB/CORE0, eigene Dumpable0-Rücklesung
  wegen bekanntem piped-Core-Host, danach weder Exec noch Credentialänderung.
  Deadlineprüfungen sind beobachtet, kein universelles Kernel-I/O-Timeout.
- Noch keine Probeausführung durch diesen Helfer. Die tatsächliche Diagnose
  benötigt unabhängig freigegebene Bytes, frische Hashes und äußere terminale
  Exit-/Zeitaufnahme. Kein Gesamtkosten-Refund aus lebender Selbstmessung.

## Lokale Evidenz / konkreter Reviewfehler

17 Parsertests bestanden (`.pytest_tmp/task36-seal-unit-02.xml`,0,18s).
Erster Lauf16grün/1falsch plattformspezifischer Pfadseparator-Assert;
nur Testdarstellung auf `.as_posix()` korrigiert, ursprüngliches XML erhalten.
Kein Linux-/Root-Start daraus abgeleitet.

Task37 reproduzierte einen echten Fehler im ursprünglichen Sealer: Ein
Regular→FIFO-Tausch zwischen lstat/open konnte vor fstat blockieren. Der
Sealer öffnet jetzt zusätzlich mit O_NONBLOCK, prüft anschließend weiter
die exakte FD-/Pfadidentität, bevor irgendein Inhalt gelesen wird. Originale
RED-Bytes und unabhängige Probe bleiben in Task37 erhalten. Nicht als native
FIFO-Ausführung ausgeben; der unabhängige Windows-Test besitzt einen echten
Pipe-FD bei modellierter Open-Grenze.

Root fand vor der nativen Ausführung außerdem einen echten Layoutfehler: Ein
root0700-Container blockiert Sqlites absoluten Dateipfad auch nach chdir ins
Workerverzeichnis. Die ursprünglichen Instanzen wurden nie installiert.
Der neue Container bekommt ausschließlich Traversal0711; alle Inhalte bleiben
durch eigene Dateirechte geschützt. Quellenableitung, noch kein nativer Pass:
[SQLite3.45.1 unixFullPathname/appendOnePathElement](https://raw.githubusercontent.com/sqlite/sqlite/version-3.45.1/src/os_unix.c).

Sealer `tests/native_preparation_seal.py`, endgültiger geprüfter SHA256:
`10fbfee476904229c9fd74a6ea9e630c9164bc08615fc02cd3d2180bf81186fb`.
Tests `tests/test_native_preparation_seal.py`:
`8152134340f9f46b69a6e37a28d5351f3f64ca536ee52b5e3324760716160f7d`.
Task37-Schlussreview abgeschlossen: 134 portable Prüfungen bestanden, keine
verbleibenden konkreten Fehler im engen Diagnosevertrag. Bericht
`task-37-native-preparation-probe-independent-review.md`, SHA256
`902b630662174e64e5da4e9e6cf33575db8d445cb90e2aef1a03feafe8e3e731`.
Root wiederholte auf dem finalen Stand 17 Parsertests in0,18s; XML
`.pytest_tmp/task36-seal-unit-03.xml`, SHA256
`61270b6039cacac22ab60d36e29dea3d4cd65fcc442ed50a1da73cc610a1ee6f`.
Frisch rein lesend keine Prozesse mit UID65534 und14804054016freie Bytes
beobachtet. Das ist keine atomare Zusage gegen spätere fremde Prozesse.
Transfer, tatsächliches Sealing und native Diagnose bleiben getrennte spätere
Schritte; noch kein Linux-Ergebnis aus diesen lokalen Prüfungen.
