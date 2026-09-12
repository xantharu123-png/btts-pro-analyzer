# Task 46 — zweiter nativer Diagnoseversuch, Pollplanung noch RED

12. September 2026, Root. Enger isolierter Test, keine C-Gesamtgeneration,
B-Freigabe oder Appänderung. Die laufende Anwendung und alle bestehenden
Produktionsdaten, Services, Rechte und Schlüssel bleiben unverändert.

## Exakter versionierter und frisch bestätigter Stand

Reparaturbranch `codex/context-capacity-recovery-20260910` lokal und remote:
`5a3a3af6e065c1ef49da6ff2a176e011e2cf837f`. GitHub main unverändert
`2dd1116b68f3d94e9c24338c6c9dff9b01799221`. Das neue aus diesem Commit erzeugte
fünf-Dateien-Archiv wurde mit dem tatsächlichen geschlossenen Sealerdecoder
lokal geprüft: 133120 Bytes, SHA256
`de033829a573755573d689e80c8206822bd795266c1ef3ee17407a6617933ace`.
Upload ausschließlich in den zuvor nicht existierenden autorisierten QA-Pfad
`/tmp/betboy-context-qa.9xr68INa/native-preparation-5a3a3af6-02.tar`.

## Neue isolierte Versiegelung

Exakte Sealerbytes `3fb5481024e73f4d45d2fe39d57f4469c537f932b73d16b129ac4c5352b2ec3e`
über SSH-stdin, frisches env-i / Python -I -S -B; kein Rootimport eines
unversiegelten serverseitigen Scripts. Neuer Rootpfad:
`/var/lib/betboy-native-probe-ncx37y3f`. Die erste Kopie bleibt unangetastet.

3729 vollständig gebundene und neu kopierte numerische Dateien, 207288087
logische Bytes, unveränderter Gesamtdigest
`eb6679f2264b26bf998b7efdae0f3ad57c0a18dd1597a8201ed6054cbebfd55c`.
Physische Beobachtung vor Manifest: 217739264 Bytes; Reservation pro Versuch
512 MiB Kopie + 64 MiB Output + 1 MiB Archiv + 2 MiB Metadaten, keine Quota.
Manifest SHA256
`78b6a98aeb3bc8d66b15f635bad2448a121ea44a7dd478c4790e517ffaf2d0e7`.

Äußere terminale GNU-time-Messung: **Exit0, 9,56s Wall, 5,28s User + 1,53s
System, 99604 KiB MaxRSS**. Die lebende Vor-Exit-Messung 9,489883616s /
6,79942072 CPU-s bleibt getrennt. Konservative Sealerbelastung weiterhin30CPU-s.

Unmittelbarer RO-Preflight: neuer Output leer/root0711, kein aktueller
UID65534-Konflikt, 14363484160 Bytes frei. Dies ist eine Beobachtung und keine
atomare Zusicherung gegen spätere Fremdstarts.

## Tatsächlicher zweiter Probeaufruf

Parent `1437ceb08267a782450558d87ed7fbfa15772e4eb062f837d8c5bdfd2ef7c81d`,
Supervisor `ae9fec1f9a7798455f21f5ac4588f714bc31803602ed51128686e3f9c17ea16d`,
Worker unverändert `22cfd8f16f8c047f298206e2f249d53fc3ef420dfbfff36f35a68c44ecc27d0e`.
Genau ein neuer Versuch, kein Retry im gleichen Verzeichnis.

Äußere terminale GNU-time-Messung: **Exit1, 1,40s Wall, 1,15s User + 0,14s
System, 61296 KiB MaxRSS**. Vollständiger Rootreport 7261 Bytes, SHA256
`a0a60f177a0dcce6a5a0acbeaf15d24b601f148d3ec426fbb63a31554e2619c1`, zusätzlich
lokal bytegleich `evidence/task46-native-run2.json`.

Anders als Versuch1 liegt diesmal ein wirklich terminales Resultat desselben
positiven Workers vor: Exit0, 1090847000 ns CPU, 62951424 Bytes maximaler RSS,
400 beobachtete stdout-Bytes, keine stderr-Bytes, beobachtetes Freiraumminimum
14363435008 Bytes. Dennoch **accepted=false**, `rss_observation_lost`;
maximaler Sampleabstand 52799507 ns. Kein weiterer Modus wurde gestartet.
Dieser ganze Versuch ist weiterhin RED; Berechnungsoutput/SQLite-Datei allein
wird nicht als vollständiger Numerik-/Guard-Abnahmepass ausgegeben.

Der ursprüngliche fehlende VmHWM-Wert wird jetzt korrekt durch ein terminales
wait4 ersetzt. Die neue konkrete Anschlusslücke ist die eigene Pollplanung:
auch bei ausstehender RSS-Auflösung und bereits geschlossenen Logpipes wartet
`selector.select(POLL_SECONDS)` die gesamten50ms. Dadurch kann die eigene
Warteentscheidung den nächsten Terminalcheck bis an/über die unveränderte
strikte50ms-Frist verschieben. Aus dem Bericht allein wird keine nanosekundengenaue
Kerneltrace abgeleitet. Task47 reproduziert den Kontrollfluss unabhängig mit
einem zeitgetreuen Selektormodell, bevor Root die enge Warteplanung korrigiert.

Geplanter enger Fix: nur bei ausstehendem Terminalreadback auf kurze5ms-Polls
wechseln. Keine Ausweitung der ursprünglichen50ms-Pendingfrist, Workerwallzeit,
RSS-/AS-/CPU-/Outputgrenzen. Schedulerverzögerung über der Frist bleibt STOP.

Volle60CPU-s dieses Probejournals bleiben dauerhaft STOP ohne Refund.
Mit30CPU-s Sealing wird auch Versuch2 konservativ90CPU-s belastet; beide
abgeschlossenen Versuche zusammen180CPU-s und beide vollständigen Artefakt-
reservationen bleiben erhalten. Das ist die enge Diagnosebilanz, kein Ersatz
für den noch ausstehenden globalen, geschützten C/B-Kostenowner.
Kein dritter Start, kein main-Push, VPS-Pull oder Produktdeployment in Task46.

## Enger lokaler Fix nach tatsächlicher Reproduktion

Task47 reproduzierte zunächst mit echtem `run_single_process` und einem
zeitgetreuen Selektormodell vier rote Fälle: EOF bereits vor oder erst nach
Pending, jeweils ohne zusätzliche Verzögerung und mit2799507ns modellierter
Verzögerung. Die angeforderten50ms werden vollständig auf die Modelluhr
gebucht; keine Linuxausführung wird damit behauptet. Tatsächlich4RED/0Error,
JUnit0,201s, XML `task47-red-20260912-1.xml`, SHA
`fd5f0ab9329fda4f8b15d97c46461f36339877f1193faea083ec32eab5544663`.

Root ändert ausschließlich den Selecttimeout im Pendingzustand von50 auf5ms.
Alle bisherigen strikten Terminal-/Originalfrist-/Ressourcenprüfungen bleiben.
Supervisor jetzt
`c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8`.

Erster kombinierter Rootlauf:270GREEN und4 alte Testassertionsrot. Ausschließlich
die hartkodierte Erwartung der Pollparameter `[0.05,0.05]` in den Task42-
Positivfällen wurde auf `[0.005,0.005]` geändert. Weder deren gemessene Werte
noch irgendeine Deadline-/Negativfallbehauptung wurden abgeschwächt. Die erste
rote Ausführung mit vier record_property/xunit2-Warnungen bleibt erhalten.
Danach **274GREEN in3,13s**, `task46-poll-root-02.xml`, ohne Skip/Warnung mit
xunit1 für diese Propertyfixtures. Task42-Testdatei jetzt
`a8ad7be1458c61ead3df29699b86065445fe0ec70c6b26e72389faeaa349142a`.

Parent und Sealer ändern nur ihren Supervisorpin, neue SHA256:
Parent `0cf2d78695f496be6343e88f3a24d135cc97e3abd2474e51f908815187cc1ca1`,
Sealer `b3aafd23e5cfd4862091937a482091ff8375498a7ed5313f5690083436076635`.
Die123 echten portablen Protokoll-/Parserfälle danach erneut bestanden in1,68s,
`task46-pin-protocol-01.xml`. Worker weiterhin unverändert22cfd8f1.
Task47 erweitert den unabhängigen Gegencheck; erst danach versionieren,
neues Archiv und eine weitere getrennte native Diagnose. Kein positiver
Gesamtclaim aus diesem lokalen Zwischenstand.

Task47 ist anschließend abgeschlossen:44 eigene und240 kombinierte Fälle,
kein konkretes verbleibendes Finding im engen Pollscope. Bericht-SHA
`fb8b3e7648c9c9d0984061a6e4c5a9d97c3e3024c43673ecd3891f443d902c3b`.
Root wiederholt danach alle44 neuen,60 Boundary-,16 Race-,120 Owner-,74
früheren Review- und123 Protokollfälle zusammen: **437GREEN,0Skip,4,97s**,
XML `task46-final-native-03.xml`. Dies bindet dieselben c6c1-/0cf2-/b3aa-Bytes;
vor einem nativen dritten Start folgt die genaue Versionierung/Übertragung.
