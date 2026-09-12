# Task 50 — dritte isolierte native Prozessdiagnose bestanden

12. September 2026, Root. Die sechs eng vorab festgelegten Diagnosefälle sind
jetzt tatsächlich auf dem VPS bestanden. Das ist ausdrücklich **kein** kompletter
C-Korpus-/DELETE-FULL-Writer-/B-/Restore-/Produktfreigabenachweis.

## Versionierte Eingaben und neue Installation

Lokal und frisch auf GitHub bestätigt: Reparaturbranch
`codex/context-capacity-recovery-20260910` auf
`6d7e2017e2d9d0f2fe29e385af3de83f4dae6dbe`.
main bleibt `2dd1116b68f3d94e9c24338c6c9dff9b01799221`.
Der unmittelbar davor separat gesicherte vollständige Copybaustein ist
`ce057a5d5f62395199113e8f9a9ffa0db5dc5f74`.

Fünf-Dateien-Gitarchiv aus exakt6d7e201, 133120 Bytes, SHA256
`79ea8d5f298d190446a9bc74fd2aa0ca25aa08a17f383ad01cdf6718733a366a`.
Der wirkliche geschlossene Sealerdecoder prüfte dieses Archiv lokal vor
Übertragung. Neuer, zuvor nicht existierender autorisierter Upload:
`/tmp/betboy-context-qa.9xr68INa/native-preparation-6d7e2017-03.tar`.

| Code | SHA256 |
| --- | --- |
| Supervisor | `c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8` |
| Parent | `0cf2d78695f496be6343e88f3a24d135cc97e3abd2474e51f908815187cc1ca1` |
| Worker, unverändert | `22cfd8f16f8c047f298206e2f249d53fc3ef420dfbfff36f35a68c44ecc27d0e` |
| Root-Sealer | `b3aafd23e5cfd4862091937a482091ff8375498a7ed5313f5690083436076635` |

Vorherige Task47-Reviewgrenze plus finaler Rootlauf:437 portable Prüfungen
bestanden in4,97s, keine Skips; XML-SHA
`96d81349be490016c28b78d5f58c9a27a742a51aac2b7566ffec4ee76de1d23e`.
Das ersetzt den folgenden nativen Versuch nicht.

Sealer bytegenau über SSH-stdin in frischem env-i / Python-I-S-B, kein
Rootimport einer unversiegelten Serverdatei. Neuer privater Rootpfad:
`/var/lib/betboy-native-probe-wu61odle`. Keine frühere Kopie wiederverwendet.
Manifest SHA256
`f2c49cda4994dedf989f5c075ba79acb101e92adb6573b2ff8692b0b3180cfcf`.

Erneut tatsächliche vollständige Kopie der3729 zuvor gebundenen Dateien aus
den vier vorhandenen numerischen QA-Paketen:207288087 logische Bytes,
Gesamtdigest `eb6679f2264b26bf998b7efdae0f3ad57c0a18dd1597a8201ed6054cbebfd55c`.
Beobachtete Allokation vor Manifest217739264 Bytes. Keine Downloads oder
zusätzlichen lokalen Secrets, Datenbanken oder Abhängigkeiten übertragen.

Sealer außen terminal: **Exit0,9,82s Wall,5,22s User+1,69s System,
99476KiB MaxRSS**. Lebende Vor-Exit-Werte9,750007268s/6,895639247CPU-s bleiben
separat. Konservativ30CPU-s weiter belastet. Vor der Probe: Output leer/root0711,
keine aktuellen UID65534-Konflikte,14143434752 Bytes frei. Keine atomare
Zusicherung gegen spätere andere Prozesse.

## Tatsächlicher Prozesslauf und Ergebnisse

Ein einziger neuer Aufruf mit exakt gepinntem Manifest, frischem env-i /
Python-I-S-B und äußerer GNU-time-Messung:
**Exit0,2,61s Wall,2,09s User+0,19s System,60152KiB MaxRSS**.
Die äußere terminale Wallzeit liegt unter der unveränderten120s-Diagnosefrist.
Keine unbekannte terminale Kindkostenposition, keine offene pidfd-Custody.

Vollständiger Rootreport15789 Bytes, SHA256
`b27bbcde0f6d946a314160b2943ab80e07149af42f0640cace1342f1bfa7c412`.
Nach begrenztem NOFOLLOW-FD-Read zusätzlich lokal exakt identisch gespeichert:
`evidence/task50-native-run3.json`. Root hat den vollständigen Report gelesen.

| Fall | Tatsächlicher Befund | Kind-CPU ns | Kind-Wall ns | Peak-RSS Bytes |
| --- | --- | ---: | ---: | ---: |
| positive | Exit0; NumPy/SciPy lösen[2,2]; SQLite8192Bytes/Summe10 | 905420000 | 956331539 | 61595648 |
| denials | fork/pthread_create/clone3/execve/execveat/Dumpable-Set alle EPERM | 39605000 | 82383782 | 19394560 |
| fsize | Eigene Datei exakt4096Bytes, weitere Erweiterung EFBIG27 | 39708000 | 85011323 | 19263488 |
| address_space | 3GiB virtuelles mmap unter2GiB-Limit: ENOMEM12,0Bytes berührt | 27610000 | 75096640 | 19525632 |
| cpu | Harte1s-CPU-Fixture tatsächlich per SIGKILL beendet, terminal gemessen | 999478000 | 1096472159 | 19501056 |
| output | 1MiB+1Byte beobachtet, nur1MiB behalten, output_limit/SIGKILL | 30448000 | 97165033 | 19501056 |

Alle sechs `accepted=true`. Die negativen CPU-/Outputfälle sind **erwartete
STOP-Erfolge des Prüfers**, keine normal beendeten Berechnungsjobs.
Die Rollen-/Limit-/Einthread-/Seccompwerte wurden beim gestoppten selben Kind
durch den gepinnten Supervisor gelesen. Die zusätzlichen Worker-JSON-Werte
sind als Workerbeobachtung getrennt; kein JSON ersetzt Kernelreadback.

Tatsächliche Runtime: Linux6.8.0-138-generic/x86_64, Python3.12.3,
Pythonbinär-SHA `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f`,
NumPy2.5.1, SciPy1.18.0, SQLite3.45.1. Die lokale QA-Runtime ist davon getrennt.
Das Numerik-Dependencyinventar wurde durch den Sealer vollständig geprüft;
dies ist trotzdem keine vollständige native/Stdlib/B-Runtimeclosure.

Alle terminalen Kinder zusammen2042269000CPU-ns; der getrennte lebende
Parent-Vorreportwert239058599CPU-ns ist keine eigene terminale Kostenmessung.
Tatsächliches Freiraumminimum14143369216Bytes. Output-/Readreihenfolge-Digests
sind begrenzte kanalgerahmte Prefixbelege, keine deterministischen Volllogs.
Vor Reports waren24576 allokierte Datei-Bytes und17596 logische Datei-Bytes
in den bekannten Diagnoseoutputs beobachtet. Kein physischer Quotaclaim.

## Unverändert erhaltene Fehler, Kosten und Reichweite

Task41 Versuch1 und Task46 Versuch2 bleiben RED mit allen originalen
Rootkopien/Reports/Journals erhalten. Auch Versuch3 behält planmäßig volle60
CPU-s im Diagnosejournal dauerhaft STOP: der lebende Parent kann seine eigenen
abschließenden Report-/Exitkosten nicht terminal selbst messen. Keine neue
Freigabe durch umgedeuteten Budgetrefund. Drei Sealer-/Probeversuche zusammen
konservativ270CPU-s sowie sämtliche drei Artefaktreservationen bleiben in der
engen Diagnosebilanz. Kein durch wiederholten Start gelöschter alter Versuch.

Die Roundtrip-/Recovery-Journalfixtures wurden real mit Linux-FD/flock/fsync
ausgeführt. Ihre Zahlenclaims bleiben ausdrücklich synthetisch; kein
Leistungs-, Authentifizierungs- oder Powerlossbeweis daraus.
Ebenso bedeutet der erfolgreiche 2,61s-Minilauf nicht,590553 echte Belege,
199 Originale/Snapshots und114 Cutoffs seien in240s überprüfbar.

Die positive SQLiteprobe verwendet absichtlich MEMORY-Journaling. Der neue
DELETE/FULL-Writer, komplette Copy/Append/History/Consumer-Aufbau, alle
Größenprofile, geschützte globale Kosten-/Closure-/B-Publikation und Restore
benötigen weiterhin ihre tatsächlichen eigenen Integrations-/Nativprüfungen.
Task48 baut jetzt den kleinen echten Corpusowner, Task51 den echten Consumer.

Frischer abschließender rein lesender VPS-Check: keine UID65534-Prozesse,
Apprevision weiterhin `2dd1116b68f3d94e9c24338c6c9dff9b01799221`,
`betboy-app.service` und `caddy.service` aktiv, interner Healthcheck `ok`.
Keine Produktivdaten, vorhandenen Rechte, Timer, Services oder Schlüssel
verändert. Kein main-Push, kein VPS-App-Pull oder C-Produktdeployment.
