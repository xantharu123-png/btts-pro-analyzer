# Task 50 — unabhängiger Ergebnisabgleich der dritten nativen Diagnose

12. September 2026. Reiner Review vorhandener Evidenz gemäß
`task-50-result-review-brief.md`; keine neue Nativeausführung oder Testsuite.

## Getrennte Urteile

**Evidenzkonsistenz: bestätigt innerhalb der gelieferten Quellen.**
Alle sechs Ergebniszeilen, Codepins des ausgeführten Supervisors/Parents/
Workers, Kindkosten, Outputgrößen, RSS, Freiraumminimum, Manifest und
konservative Diagnosebuchung stimmen mit dem vollständigen originalen JSON
überein. Keine materielle Tatsachenabweichung gefunden.

**Genauigkeit der Freigabegrenze: bestätigt.** Der Rootbericht erklärt den
sechsten Diagnoseerfolg nicht zu DELETE/FULL-, Corpus-, Quota-, Closure-,
B-, Modell-, Restore- oder Deploymentabnahme. CPU-/Output-Abbrüche bleiben
erwartete STOP-Erfolge des Prüfers, keine normal beendeten Rechenjobs.
Keine materielle Überbehauptung gefunden.

Die äußeren Terminal-/Sealer-/Serverbeobachtungen sind ausdrücklich Roots
aufgezeichnete SSH-Evidenz, nicht heimlich aus dem Vor-Exit-JSON gewonnen.
Sie wurden hier nicht neu auf dem VPS gemessen. Dieses Urteil bestätigt die
Konsistenz des Ergebnisberichts, nicht eine neue unabhängige Durchführung.

## Eingabeidentität und Methode

Vollständig gelesen:

- `task-50-native-diagnostic-passed.md`, SHA256
  `2ebd7d12ac8e320a277bdac4768c5e26c7c64b0af7fc3aff09d71f78127fbe08`.
- `evidence/task50-native-run3.json`, tatsächlich **15789 Bytes**, SHA256
  `b27bbcde0f6d946a314160b2943ab80e07149af42f0640cace1342f1bfa7c412`.

Die Originaldatei ist eine einzige JSON-Zeile; die folgenden JSON-Pfade beziehen
sich deshalb sämtlich auf `evidence/task50-native-run3.json:1`. Read-only
PowerShell-Hashchecks und lokale JSON-Parsing-/Arithmetik-/Digestprüfungen
wurden frisch ausgeführt. Das waren keine erneuten Tests unveränderter Module.
Die Skill `verification-before-completion` wurde auf diese frischen
Artefaktprüfungen angewandt, nicht als Anlass für zusätzliche Nativearbeit.

Die in Rootbericht Zeile 11 angegebene Native-Eingabe
`6d7e2017e2d9d0f2fe29e385af3de83f4dae6dbe` entspricht exakt dem Reviewbrief.
Commit, GitHub-/main-Stand, Archivgröße/-hash und tatsächlicher SSH-Upload sind
Roots dokumentierte Installationsbelege, keine eigenen JSON-Felder und keine
hier neu ausgeführte Git-/Serverkontrolle.

## Sechs Fallzeilen und Messwerte

Rootbericht Zeilen 65–78 stimmen exakt mit `cases` überein:

| Modus | Exit / Stop | Kind-CPU ns | Kind-Wall ns | Peak-RSS Bytes |
| --- | --- | ---: | ---: | ---: |
| positive | 0 / null | 905420000 | 956331539 | 61595648 |
| denials | 0 / null | 39605000 | 82383782 | 19394560 |
| fsize | 0 / null | 39708000 | 85011323 | 19263488 |
| address_space | 0 / null | 27610000 | 75096640 | 19525632 |
| cpu | -9 / signal_exit | 999478000 | 1096472159 | 19501056 |
| output | -9 / output_limit | 30448000 | 97165033 | 19501056 |

Alle sechs `accepted` sind tatsächlich boolesch true. Die `worker_observation`
enthält für positive NumPy 2.5.1, SciPy 1.18.0, Lösung [2.0,2.0], SQLite 3.45.1,
8192 Dateibytes und Summe 10; für denials alle sechs angegebenen Errno-/Error-
Werte 1; für fsize 4096 Bytes und EFBIG 27; für address_space den tatsächlichen
Anforderungswert 3221225472, ENOMEM 12 und 0 berührte Bytes. CPU/output bleiben
in Phase armed und sind kein erfolgreicher Complete-Workeroutput.

`returned_children_terminal_cpu_ns` ist arithmetisch exakt die Summe
**2042269000**. `native_call_without_returned_terminal_cost` ist null; alle
sechs Fälle haben tatsächlich terminale Ergebnisfelder. Der globale
Vorreport-Parentwert **239058599 ns** wird in Rootbericht Zeilen 86–87 korrekt
getrennt und nicht in eine terminale Eigenmessung umgedeutet. Auch die Summe
der sechs jeweiligen Supervisor-Parentfenster, 36417914 ns, ist eine andere
Messgröße und wird nicht als gesamte Parentlaufzeit ausgegeben.

Der höchste ausgewiesene RSS beträgt **61595648 Bytes**. Alle Peaks liegen
unter 1 GiB. Die deklarierte RSS-Semantik ist ausdrücklich Maximum aus
gesampeltem VmHWM und terminalem wait4-ru_maxrss, keine kontinuierliche
eigenständige RSS-Quota für einen beliebigen Prozessbaum.

Die `kernel_readback`-PIDs stimmen für alle Fälle mit den Worker-PIDs überein;
UID/GID sind 65534, CPU-Hardlimits 15/3/3/3/1/3 s und FSIZE 524288/4096/... .
Nicht jedes geprüfte Kernelfeld wird im kompakten Ergebnis erneut exportiert.
Für die Berichtsaussage zu AS/Einthread/Cap-/Seccomp-Readback wurden deshalb
ausschließlich die erforderlichen Stellen des bytegleichen gepinnten
Supervisors gelesen (`context_preparation_supervisor.py:159`, AS-Konstante
`:40`), nicht dessen unveränderte Gesamtimplementierung erneut geprüft.
Die vorgeschriebenen 2 GiB AS stammen aus diesem Readbackpfad, nicht aus
einem erfundenen zusätzlichen JSON-Feld. Die erfolgreiche normale Rückgabe
und die eng gelesene FD-finally-Stelle `:510` sind mit fehlender offener
Custody konsistent; das JSON enthält keinen neuen externen pidfd-Inventurscan.

## Output, Platz und Manifest

`cases[*].native.stdout_retained` nennt 400, 377, 298, 338, 243 und 1048576
Bytes. Alle stderr-Prefixe sind leer und haben den leeren SHA256. Die ersten
fünf stdout-Hashes wurden unabhängig aus der jeweiligen kanonischen
`worker_observation` plus LF exakt reproduziert. Für output wurde anhand
des unveränderten gepinnten Workers (`tests/native_preparation_worker.py:221`)
der 246-Byte-Armedrecord plus x-Füllung bis 1048576 Bytes rekonstruiert; auch
dessen SHA256 stimmt exakt. Beobachtet sind im Outputfall **1048577** Bytes,
behalten nur **1048576**. Das belegt die berichtete Prefixgrenze, nicht einen
vollständigen oder deterministischen kanalübergreifenden Logdigest.

Das Minimum aller sechs `minimum_free_bytes` ist exakt **14143369216**,
wie Rootbericht Zeile 88. Die Summe der fünf erfassten Artefaktdateien ergibt
exakt **24576 allokierte** und **17596 logische** Bytes vor Reports:
8192 SQLite, 4096 FSIZE und drei Journaldateien. Das 64-MiB-
`admitted_ceiling_bytes` und `planned_artifact_bytes=20320256` sind
verschiedene Planwerte, nicht verwechselte tatsächliche Belegung.
`physical_quota_claim` ist false; Report Zeilen 90–91 bewahren diese Grenze.

Die SHA256 der kanonischen `bound_manifest`-Bytes **einschließlich LF** wurde
frisch berechnet und entspricht exakt `manifest_sha256` und Rootbericht
Zeile 38:
`f2c49cda4994dedf989f5c075ba79acb101e92adb6573b2ff8692b0b3180cfcf`.
Auch privater Pfad `wu61odle`, Pythonhash und der numerische Dependencydigest
stimmen. Folgende Pins stimmen sowohl mit JSON/Rootbericht als auch mit den
hier eng gelesenen unveränderten lokalen Quelldateien überein:

- Supervisor `c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8`.
- Parent `0cf2d78695f496be6343e88f3a24d135cc97e3abd2474e51f908815187cc1ca1`.
- Worker `22cfd8f16f8c047f298206e2f249d53fc3ef420dfbfff36f35a68c44ecc27d0e`.

Der Sealerpin in Report Zeile 27 ist Installations-/SSH-Evidenz, kein
verschwiegenes Feld im `bound_manifest`. Ebenso stammen 3729 Dateien,
207288087 Dependencybytes, 217739264 vorherige Allokationsbytes und die
äußeren Sealertimings aus Roots Sealing-Aufnahme. Das Worker-JSON bestätigt
deren Manifestbindung/Digest, zählt diesen separaten Sealinglauf nicht neu.

## Äußere Messungen und bewahrte Fehlversuche

Report Zeilen 46–50 trennen den äußeren Sealerabschluss
Exit0/9,82 s/5,22+1,69 CPU-s/99476 KiB von dessen lebender Vormessung.
Zeilen 54–57 geben den äußeren Probeabschluss
Exit0/2,61 s/2,09+0,19 CPU-s/60152 KiB an. Diese terminalen Angaben sind
**Roots aufgezeichnete SSH-/GNU-time-Beobachtungen**, nicht das Vor-Exit-JSON.
Dessen `report_phase` verlangt selbst Exit0 und die äußere Terminalwallzeit.
`elapsed_through_pre_report_ns=2614918085` ist mit der auf zwei Nachkommastellen
ausgegebenen äußeren 2,61-s-Zeit konsistent, ersetzt sie aber nicht.
`deadline_boot_ns-parent_start_boot_ns` beträgt exakt 120000000000 ns.
Auch abschließende Apprevision/Service-/Health-/UID-Kontrolle in Zeilen
115–119 bleibt Root-SSH-Evidenz, keine Aussage eines Diagnose-Workerfelds.

Nur für die ausdrücklich beibehaltene Fehler-/Kostenhistorie wurden die
vorhandenen Task41-/Task46-Berichte und betreffenden alten JSON-Felder
herangezogen. Die tatsächlich vorhandene erste Berichtdatei heißt
`task-41-native-exit-transition.md` (abweichend vom Verweis im Reviewbrief).
Die früheren Original-JSON-Hashes stimmen weiterhin:

- Versuch1: `6f22075bd2a1cc4068c62d32f17197df3cd5b827deecf9908b1119759186e977`;
  failed, keine zurückgegebenen Kindkosten, aktiver Modus positive unbekannt.
- Versuch2: `a0a60f177a0dcce6a5a0acbeaf15d24b601f148d3ec426fbb63a31554e2619c1`;
  failed trotz zurückgegebenem terminalem Kind, 1090847000 Kind-CPU-ns.

Alle drei Diagnosejournale behalten **60000000000 ns charged**, 0 settled,
Status stopped und keinen Refund. Versuch3s Pendingreservation entspricht
exakt `durable_reservation_before_any_child`. Zusammen mit den in den drei
Rootberichten separat weiter belasteten je 30 Sealer-CPU-s ist die angegebene
enge konservative Bilanz **3 × (60+30) = 270 CPU-s** konsistent. Daraus folgt
kein bereits vorhandener geschützter globaler C/B-Kostenowner. Dass alte
Serverpfade/Reservationen physisch unverändert erhalten sind, bleibt Roots
berichtete Serverbeobachtung; hier wurden die lokalen Originale geprüft und
kein Serverbestand neu inventarisiert.

`accounting_fixtures.scope`, `diagnostic_refund`,
`native_dependency_closure_verified_here=false`,
`no_corpus_or_B_authority=true` und `sqlite_scope` stimmen mit den
Scopeeinschränkungen in Report Zeilen 83–112 überein. Reale Linux-FD/flock/
fsync-Fixtures bleiben synthetische Accountingclaims, nicht Leistungs-,
Authentifizierungs- oder Powerlossnachweis. Die positive SQLiteprobe ist
ausdrücklich MEMORY-Journaling und kein DELETE/FULL-Profiltest. Keine
Hochrechnung auf 590553 Belege, 199 Originals/Snapshots, 114 Cutoffs oder
240-s-Gesamtfreigabe wird aus dem Minilauf abgeleitet.

## Abschluss

Keine materiellen Findings und keine Änderung am Rootbericht erforderlich.
Nur dieser Reviewbericht wurde neu geschrieben; keine Code-/Test-/Git-/
Serveränderung, keine Agentendelegation, keine unveränderte Suite wiederholt.
Die beiden Urteile gelten ausschließlich für Quellenkonsistenz und zutreffende
Reichweite der bereits ausgeführten dritten Diagnose.
