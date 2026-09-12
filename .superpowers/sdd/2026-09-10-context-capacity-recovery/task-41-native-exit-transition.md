# Task 41 — erste echte native Diagnose, beobachteter Exit-Messfehler

12. September 2026, Root. Dies ist ein isolierter Diagnose-/Reparaturschritt,
kein C-Korpus, B-Nachweis oder Appdeployment. Cricket, Spielmodelle, bestehende
Produktionsdaten und Dienste bleiben unverändert.

## Tatsächlich versioniert, gepusht und übertragen

Reparaturbranch frisch auf GitHub bestätigt:
`c79bb101b1cda166dc60ab74b378e265e1d2d742`.
GitHub main bleibt `2dd1116b68f3d94e9c24338c6c9dff9b01799221`.
Aus genau diesem Commit erzeugtes Git-Tar mit fünf geschlossenen Codepfaden,
133120Bytes, SHA256
`5d281411e07b9a7afb89d873ee24abacbe7443872a905f3bb4a564a9f16bb8c9`.
Der echte Sealerdecoder prüfte auch dieses tatsächlich erzeugte Archiv lokal.
Upload in den vorher nachweislich neuen freigegebenen QA-Pfad
`/tmp/betboy-context-qa.9xr68INa/native-preparation-c79bb101-01.tar`.
Keine zusätzlichen lokalen Secrets, Pakete oder Datenbanken übertragen.

Task36-Sealer `10fbfee476904229c9fd74a6ea9e630c9164bc08615fc02cd3d2180bf81186fb`
wurde bytegenau über SSH-stdin in einem frischen env-i / Python-I-S-B-Prozess
ausgeführt. Es wurde keine user-writable Serverdatei als Rootscript geöffnet.

## Wirklich durchgeführtes neues Sealing

Neuer Rootpfad `/var/lib/betboy-native-probe-2gcraxxf`; bestehende Pfade/Rechte
unverändert. Vollständige Kopie der vorher gebundenen3729 numerischen Dateien,
207288087logische Bytes, vollständiger Dependencydigest unverändert
`eb6679f2264b26bf998b7efdae0f3ad57c0a18dd1597a8201ed6054cbebfd55c`.
Beobachtete Allokation vor Manifest217739264Bytes. Feste Reservation:
512MiB Kopie +64MiB Output +1MiB Archiv +2MiB Metadaten; dies ist keine Quota.
Manifest-SHA256
`e16814a98e1bfb82f994e1bb8e24a8e555b308fc6c3a1dec5e073b4c0a50ba45`.

Äußere GNU-time-Terminalmessung: **Exit0,12,54s Wall,7,10s User+1,98s System,
99600KiB Peak**. Lebende Vor-Exit-Sealermessung12,456185083s und9,05911249CPU
ist zusätzlich vorhanden, wird aber nicht mit der terminalen Messung verwechselt.
Sealer-HardlimitsCPU30/AS512MiB/FSIZE128MiB/CORE0 und eigener Dumpable0.
Für die enge äußere Versuchsbilanz werden konservativ30CPU-Sekunden belastet,
kein aus Selbstmessung erfundener Refund.

## Echter erster Diagnoseaufruf: RED

Vor dem einzigen Aufruf nochmals rein lesend bestätigt: neuer Output leer,
root0711; keine aktuellen UID65534-Prozesse;14584963072Bytes frei. Keine
atomare Garantie gegen spätere Fremdstarts. Frischer env-i Parent-I-S-B, exakte
Manifestbindung, sechs feste Prüfmodi ohne Netzwerk-/Crashprobe geplant.

Tatsächliches Ergebnis: **Exit1,1,59s Wall,1,36s User+0,15s System,
61884KiB Peak** in der äußeren GNU-time-Terminalmessung.
`NativeSupervisorError: missing kernel RSS high-water mark` beim ersten Modus
`positive`. Es gibt **kein zurückgegebenes terminales Fallresultat** und damit
keinen bestandenen Numerik-/SQLite-/Limitfall. Tatsächlich liegt die neue eigene
SQLite-Datei mit8192Bytes vor; das allein ist keine erfolgreiche Fallabnahme.

Unverändertes vollständiges5988Byte-Rootreport, zusätzlich lokal bytegleich:
`evidence/task41-native-run1.json`, SHA256
`6f22075bd2a1cc4068c62d32f17197df3cd5b827deecf9908b1119759186e977`.
Der Report bindet Kernel6.8.0-138-generic, Python3.12.3, tatsächlichen Binärhash,
seine Eingabepfade und alle Journale. `cases=[]`, aktive Fallkosten unbekannt;
volle60CPU-Sekunden dauerhaft STOP behalten. Keine Wiederaufnahme dieses
Verzeichnisses, keine automatische Wiederholung oder Bereinigung. Der erste
Diagnose-/Sealversuch bleibt damit konservativ90CPU-Sekunden belastet.

Die echten Journalfixture-Aufrufe create/settle/reopen/recovered-pending liefen
vor diesem Fehler. Ihre Claims bleiben ausdrücklich synthetische Testwerte,
keine Messautorität oder B-Authentifizierung. Das globale Diagnosejournal ist
davon getrennt und behält seine volle tatsächliche Reservation.

## Konkrete Ursache und enger Fix

Der Supervisor übersprang fehlende RSS-Felder bisher nur bei bereits sichtbarem
Zombie-State. Linux kann `mm` jedoch vor der finalen Exit-Benachrichtigung
entfernen. `proc_pid_status` liest Taskstate und speicherabhängige Felder
getrennt; letztere werden nur bei vorhandenem `mm` geschrieben. Das erklärt
den beobachteten Übergang; es ist keine neue App-Speicherüberlastung.
Primärquellen: [Linux6.8 proc_pid_status](https://raw.githubusercontent.com/torvalds/linux/v6.8/fs/proc/array.c)
und [Linux6.8 do_exit/exit_mm vor exit_notify](https://github.com/torvalds/linux/blob/v6.8/kernel/exit.c).

Der neue enge Zustand akzeptiert nach bestätigtem Start ausschließlich das
**fehlende** VmHWM als möglichen Exitübergang. Er wartet höchstens ein normales
50ms-Pollfenster innerhalb der unveränderten ursprünglichen Frist auf genau
dieses tatsächlich terminale wait4-Ergebnis. Kein später gesunder proc-Sample
löscht den offenen Messzustand. Bleibt das Kind nichtterminal, folgt gemessener
STOP `rss_observation_lost`; unbekanntes Reaping bleibt Custody-STOP.
Vorhandene kaputte RSS-Werte bleiben Fehler. Abschließend sind weiterhin
echte strikt typisierte ru_maxrss, CPUkosten, Exitstatus, gesamter RSS-Peak,
Freiraum, Ausgabelimit und originale Zeitgrenze erforderlich.

Supervisorfix-SHA256
`8554f91216448b60c91979c0e2d1c768f5909f2277b68b5ed5d2c05d4f9ca87d`.
Regressionstest `tests/test_context_preparation_terminal_race.py`, SHA256
`8e6515dd0d96a1a6c73bd1bbd18bbaa7b5aeebb3ad927211850674842a79eb72`.
Gleiche deterministische Syscallmodelle gegen echte alte Funktion:
**12RED/4GREEN** in0,43s, XML `task41-terminal-race-red-01.xml`, SHA256
`b80711a57aa978fdc562d96b1eab31eb919f82fa25dafcbeba6618ac5aaf3335`.
Nach Fix gemeinsam mit120Owner- und74früheren Reviewfällen:
**210grün** in2,66s, XML `task41-terminal-race-green-01.xml`, SHA256
`1876c64273548357c4dc587348bbd705073de3842509ea4528b2f3e397c9aced`.
Diese Modelle ersetzen die spätere echte native Wiederprüfung nicht.

Parent und Sealer ändern ausschließlich den Supervisor-Hashpin:
Parent`8192c45575af5cbcc5d6c9443376035ecee1abb04f35a31a57f1e008dba2df8e`,
Sealer`50b41cb0104a06f3cb57c58793ef30d75a2236cde48d618b78652cb52494c2b0`.
Worker`22cfd8f16f8c047f298206e2f249d53fc3ef420dfbfff36f35a68c44ecc27d0e`
bleibt bytegleich. Task42 prüft den Fix unabhängig. Erst nach Abschluss:
versionieren/pushen, neues vollständiges Archiv, neuer eigener Seal/Output und
erneute äußere Terminalmessung. Alter RED-Stand und alle Kosten bleiben bestehen.

Globaler C-Datenfluss und dessen offene konkrete Producer-/Lifetimeübergänge
stehen in Task39; dieser kleine Diagnosefix schließt sie nicht. Keine C-/B-/
240s-/Restorefreigabe und weiterhin kein main-/Approllout.

## Unabhängiger enger Gegencheck und endgültiger Fix

Task42 reproduzierte zwei zusätzliche konkrete Fehler im obigen lokalen
8554-Zwischenstand: Ein erst nach50ms zurückkehrender terminaler wait4-Pfad
übersprang den Pending-Fristvergleich; zugleich wurden bekannte Threads2/999
beim fehlenden VmHWM nicht als bestehende Threadverletzung behalten.
Fünf echte eigene RED-Fälle sind erhalten. Kein nativer Lauf mit8554.

Jetzt wird die Bootzeit direkt nach dem tatsächlich terminalen wait4 geprüft;
>=50ms oder Rücklauf stoppt. Bekannte Threads!=1 bleiben auch ohne VmHWM
`kernel_task_count`. Vollständige terminale RSS-/CPUprüfung bleibt bestehen.
Finaler Supervisor:
`ae9fec1f9a7798455f21f5ac4588f714bc31803602ed51128686e3f9c17ea16d`.
Die Root-Racefixture tickt jetzt5 statt10ms, damit ihre kurzen Positivfälle
auch mit dem zusätzlichen Terminalzeitsample ausdrücklich unter50ms liegen;
Test-SHA`d34e2ff4eb65f11eb9b73a8862b7840c2492f909aa9528a9404e8e6bbaa3b810`.
Dies ändert keine der bewahrten ursprünglichen RED-Ausführungen.

Task42:60 eigene unabhängige Cases plus16Root-,120Owner- und74frühere Review-
Cases = **270grün,0Skip,3,04s**. XML `task42-terminal-combined-04.xml`, SHA
`2c2aeeb9fbe7b79767ce63ef00a986733bf89e7f9817419cc72b92ab14ad6ced`.
Die60 eigenen Fälle sind zusätzlich normale dauerhafte Tests:
`tests/test_context_preparation_terminal_boundaries.py`, SHA
`d9a3ebc946e103c6852ed94653c6cea3112fe6c6bd795e45be85c0f6763281e8`.
Originale8554-Bytes sowie die erste rote Probe bleiben in Task42 dokumentiert.

Finale reine Pin-Anpassungen: Parent
`1437ceb08267a782450558d87ed7fbfa15772e4eb062f837d8c5bdfd2ef7c81d`,
Sealer`3fb5481024e73f4d45d2fe39d57f4469c537f932b73d16b129ac4c5352b2ec3e`.
Worker unverändert22cfd8f1. Normale Task40-Parent-/Sealer-/Worker-Protokolltests
plus bestehende Parser danach erneut123grün in1,61s
(`task41-pin-protocol-green-01.xml`). Zweiter nativer Start noch nicht erfolgt.
