# Zweiter freigegebener QA-Lauf: tatsächlicher Abbruch und lokale Korrektur

Fortsetzung vom 13./14. September 2026. Der Nutzer hat genau einen weiteren
900-CPU-/900-Wandsekunden-Auftrag mit der Aufteilung A400/B300/C200 freigegeben.
Der Auftrag wurde ausgeführt. **Kein vollständiger QA-Pass und kein Deployment.**

## Erste Ursache nachgewiesen und korrigiert

Der frühere A2-Abbruch ließ sich durch einen kleinen, ausdrücklich nicht als
Qualifikation zählenden Nur-Lese-Vorcheck reproduzieren: `protected()` verlangte
auch für die eingefrorene Datenbasis die Gruppe root. Die tatsächliche Datei
`/var/lib/betboy-live-backup-ssfvf5xs/context-current.db` ist jedoch absichtlich
root:betboy 0440, ihr direktes Verzeichnis root:betboy 0750. Kein Gruppenmitglied
hat Schreibrechte. Größe 270233600, unveränderter SHA256
`73ec16911c7d66e894a0f92c6600e3486e34b57c4176b30938638d3669146ffa`.

Commit `9d92ed862d16d08596fd8f5c33c7e033462b0326` akzeptiert diesen bestehenden
Nur-Lese-Gruppenbesitz ausschließlich für diese beiden Datenpfade. Kontrollen,
ausführbarer Code und andere Vorfahren bleiben root:root. Fremder Eigentümer,
Schreibrecht, Hardlink oder ungeeigneter Typ bleiben abgewiesen. Auf dem Server
wurden keine Rechte oder ursprünglichen Daten verändert.

Vorcheck nach Korrektur: äußerer Exit 0, 6,72 s Wandzeit, gemessene innere CPU
6,390055111 s. Die historischen Inhalte wurden dabei ausdrücklich nicht erneut
vollständig beobachtet; dies ersetzt keinen der vier Pflichtscans.

## Zweiter Gesamtauftrag: beide ersten Scans bestanden, danach SIGKILL

Quelle `9d92ed862d16d08596fd8f5c33c7e033462b0326`, Archiv-SHA256
`3caae917899698ebc526ce86427844d70c657d709dd030189aba0066267f9f5f`.
101 historische Wurzeln vollständig im Auftrag gebunden. Alte Reservierungen
einschließlich der 900 s des ersten Fehlversuchs bleiben erhalten; keine Gutschrift.

| Tatsächlicher Abschnitt | Ergebnis |
| --- | --- |
| A1 | beendet, 133686437001 ns gemessene Kind-CPU |
| A2 | beendet, 140158398000 ns gemessene Kind-CPU |
| Steuerprozess zuletzt im Journal | 4717129255 ns CPU am Ende von A2 |
| Vorbereitung danach | 469 Code-Dateien, 4540 Abhängigkeitsdateien, zwei Zeitzonendateien und Basiskopie vorhanden |
| Äußerer Prozessabschluss | SIGKILL / SSH-Exit 137, 385,60 s Wandzeit |
| GNU-time-Summen | user 262,19 s, system 71,78 s, Max-RSS 106428 KiB |
| A3 / B / C | nicht erreicht; keine fachliche Workerfreigabe |

Die Differenz der gerundeten Gesamtkosten zur exakt gemessenen Kind-CPU liegt
bei rund 60,13 CPU-s. Zusammen mit dem unveränderten harten Parent-Limit von
60 s entspricht das einem Abbruch des Steuerprozesses an seiner CPU-Grenze.
Kein Erfolg aus dem irreführenden `exit=0`-Feld der GNU-time-Signalzeile ableiten:
Signal 9 und tatsächlicher SSH-Exit 137 sind maßgeblich.

Das erhaltene Journal enthält reserve, begin/finish A1 und begin/finish A2,
aber keinen A3-Start und keinen Abschluss. Da SIGKILL nicht abgefangen werden
kann, wurde auch kein erfolgreicher Abschlussbericht erzeugt. Die komplette
900-s-Reservierung bleibt belastet. Die folgenden drei Bereiche bleiben erhalten:

```text
/var/lib/betboy-context-qa-v2-inputs-02
/var/lib/betboy-context-qa-v2-registry-02
/var/lib/betboy-context-qa-v2-job-02
```

Lokale Ausgabe und exaktes Quellarchiv:
`.pytest_tmp/qav2-unit-9d92ed8-qualification/`. Ein anschließender Nur-Lese-Abgleich
fand keinen verbleibenden Prüfprozess. Die Produktions-App war weiterhin aktiv.

## Korrektur der wiederholten Kontrollarbeit

Der Steuerprozess hat bei jedem der ungefähr 5000 Dateikopiervorgänge zweimal
seine Zulassung geprüft und dabei unveränderte Journale mehrfach vollständig
semantisch nachgespielt. Ein lokales Profil bestätigt diese wiederholte
JSON-/Protokollverarbeitung. Commit
`b9da5a3b9d183a7359b69056936eeeafe03a81f2` beseitigt ausschließlich diese Redundanz:

- Bei jeder Prüfung werden die gesamten gehaltenen Journalbytes weiter frisch
  gelesen und mit dem exakt akzeptierten Inhalt verglichen. Keine reine
  Größe-/Zeitstempelprüfung und kein ausgelassener historischer Scan.
- Jede neue Buchung bleibt nach fsync und tatsächlichem Readback vollständig
  nachgespielt. Abbruch, offene Kosten und verbrauchte Konten bleiben unverändert.
- Der akzeptierte Zustand im Speicher wird ebenfalls gegen eine getrennte
  Momentaufnahme geprüft; fremde Änderungen sind keine neue Autorität.
- Die aktuelle Uhr-, Prozess-, Gesamtfrist- und 60-CPU-Grenzprüfung läuft weiter
  bei jedem Aufruf. Auch das alte Fehlerjournal wird jedes Mal vollständig gelesen.

Gezielte Regression des finalen Patches: **124 bestanden, 15 Plattform-Skips**,
88,61 s, äußerer Exit 0; XML `.pytest_tmp/qav2-control-final-01.xml`.
Zusätzliche echte Linux-Gegenprobe als UID1000: **81 bestanden, 6 Root-Skips**,
2,26 s, äußerer SSH-Exit 0. Archiv-SHA256
`f5d721be6d7e61116fab9910b804b5d0c33e7680338ffca12d9faaf3ec6d8332`;
erhalten unter `/tmp/betboy-context-qav2-unit-b9da5a3-portable-native-01`.
Dieser kleine Lauf kostete zusätzlich 2,5296 Kind-CPU-s plus 0,202977983 Parent-CPU-s;
er ist kein dritter Gesamtauftrag und keine C/B-Abnahme.

Die Tests greifen gleich lange Inhaltsänderung trotz zurückgesetzter mtime,
Kürzung, Anhang, Zustandstausch, fsync-Fehler, fremde Prozessidentität, abgelaufene
Frist sowie falsche Altreservierungen an. Unveränderte Kontrollen verursachen
keinen erneuten Protokoll-Replay; komplette frische Lesezugriffe bleiben belegt.

Lokaler synthetischer Vergleich des finalen Codes: 10000 aktuelle Kontrollen
benötigten 250000000 ns statt 4078125000 ns CPU im vorherigen Code. Dabei wurde
der vollständige 2899-Byte-Fixtureinhalt weiterhin bei jedem Kontrollaufruf
gelesen. Das misst ausschließlich den Kontrollalgorithmus mit einem Speicher-
Journal, nicht den nativen Dateikopierlauf oder ausreichende Gesamtkapazität.

Zwischenstand des Code-Pushs frisch bestätigt: GitHub-Reparaturbranch exakt
`b9da5a3b9d183a7359b69056936eeeafe03a81f2`, GitHub main unverändert
`f84d9a6c81a4a8cb95ecc128a0fc26bb17f414dc`. Der Dokumentationsabschluss folgt
separat. Ein Reparaturbranch-Push deployt keine Produktion.

## Grenzen: weiterhin keine Freigabe für einen Produktivwechsel

Es wurde **kein dritter großer Lauf** gestartet, kein Konto fortgesetzt,
kein Limit erhöht und kein historischer Prüfordner bereinigt. Die belegten
273,844835001 A-CPU-s lassen im zweiten Profil nur 126,155164999 s übrig. Ein
weiterer ähnlich teurer Historienvergleich könnte auch daran scheitern; das ist
eine Prognose, kein tatsächlich ausgeführter A3-Test. Die Parent-Optimierung
allein ist daher kein Nachweis, dass das ganze Paket jetzt passt.

Vollständige C/B-Wachstums-, Verbraucher-, Runtime-, Restore- und passende
Updaterprüfungen bleiben offen. Eine 1024-Belege-Diagnose ersetzt nicht das
490000-Belege-Pflichtwachstum oder den vollständigen Release-Nachweis.

Letzter frischer VPS-Abgleich dieser Fortsetzung: HEAD
`2dd1116b68f3d94e9c24338c6c9dff9b01799221`, App und Caddy aktiv, lokaler
Healthcheck `ok`. Kein normaler Updateraufruf, kein direkter Git-Pull am
defekten installierten Updater vorbei, keine Änderungen an Produktionsdaten
oder Timern. Daily3 bleibt lokal implementiert, nicht live.

Die breite Repository-Suite ist beendet: **9630 bestanden, 2 fehlgeschlagen,
91 übersprungen, 97 Untertests bestanden**, 1992,61 s, äußerer Exit 1. Ihr Beginn
lag auf `9d92ed8`; während dieses Laufs wurden nur QA-Steuerdateien/Tests geändert
und separat nachgeprüft. Ein finaler Vollsuiten-Pass wird daraus nicht behauptet.
Die separat wiederholten Domain-/Evaluator-/CLI-Dateien bestanden 93 Tests in
403,56 s. Dieser isolierte Erfolg beseitigt keinen Fehler des Gesamtprozesses.

## Vollsuitenfehler: beide reproduziert und behoben

Fix-Commit `dfe6068c6fc69bd9b2e8da17c8bc748d0fece583`:

1. `test_frozen_reviewed_preflight_algorithms_are_copied_without_drift` hielt
   noch den alten Updater-Digest `4b814c...` vor Daily3 fest. Der tatsächliche
   Diff seit `aca7256d^` zeigt in beiden Updatern ausschließlich den Wechsel
   des Backup-Verifier-Pins b37d11... → 65f288.... Die korrigierte Regression
   bindet den neuen gesamten Digest `bb34a71932ce58cb875d64af5e3738b02f82d96bf2a8f64ea5159f0e88a02762`,
   den tatsächlichen Verifierinhalt und weiterhin den alten Digest durch die
   exakt einmalige Rücksubstitution. Alle gemeinsamen Funktionen bleiben
   bytegleich geprüft. Kein pauschales Entfernen eines Pins, keine Änderung
   des erwarteten installierten Produktions-Updaters.
2. `test_cli_real_offline_dataset_exports_report_but_never_activates` scheiterte
   mit FileNotFoundError. Der exportierte Zielpfad war gültig (248 Zeichen),
   aber `atomic_write_bytes` verlängerte den temporären Pfad auf 262 Zeichen,
   weil es den vollständigen 64-Zeichen-Berichtshash noch einmal in den
   temporären Namen übernahm. Der reale Windows-Gegentest reproduzierte genau
   diesen Fehler. Jetzt benutzt mkstemp den kurzen Präfix `.betboy-` im selben
   Zielverzeichnis. O_EXCL, fsync, Atomizität, Ersetzen/nicht Überschreiben,
   Symlinkgrenzen und Aufräumen bleiben erhalten. Drei neue Tests waren vor
   dem Fix rot und sind danach grün; die Fehlerbereinigung prüft jetzt den
   kompletten verbleibenden Verzeichnisinhalt statt nur das alte Namensmuster.

Nachtests auf dem finalen Code:

- Runtimepfade, tatsächlicher Offline-CLI, Daily3-Backup, Archiv-Staging und
  Updater-Reparatur: **141 bestanden, 2 Plattform-Skips**, 73,39 s, Exit 0.
- RisikoBet-Speicher, Tennis-Training-Cache, Workflow und Daily3-Kern/UI/Auswahl:
  **223 bestanden, 3 Plattform-Skips**, 8,07 s, Exit 0.
- Die vollständige 33-Minuten-Suite wurde nicht nachträglich als grün erklärt
  und auf dem nachfolgenden Ein-Zeilen-Runtime-Fix nicht nochmals komplett gestartet.

| Lokaler XML-Beleg | SHA256 |
| --- | --- |
| `final-release-suite-87e3c4e1a0cf4a328364381bd3c4864a.xml` | `db75ad7a8906d150819afdf316f909c5d02f64524fdec90ad9b4c645f948e9c7` |
| `qav2-control-final-01.xml` | `e06bd923ba1cf531d34b45d3de7c9ee08910a039c731da5da01a51733abe2f13` |
| `final-runtime-fixes-01.xml` | `fd24e6d3b09104cdd2e3c95cb495c184a2c182bca42478d3843279c700e971e5` |
| `final-write-consumers-01.xml` | `92e0f0d0686f734d6b60a011ac7635439c014b3e520b883bac85a7ac85056a97` |

Alle Belege liegen in `.pytest_tmp/`. Der erste XML enthält die 97 Untertests
zusätzlich im tests-Zähler; diesen nicht als 9820 eigenständige Haupttests ausgeben.
Alle eigenen lokalen Testprozesse sind beendet. Alte Prüfdaten bleiben erhalten.

Letzter frischer SSH-Abgleich am 14.09. um etwa 00:05 Europe/Zurich: unverändert
HEAD2dd1116 und Updater74b1c4..., App/Caddy aktiv, interner Healthcheck ok,
sieben Timer mit geplantem nächstem Termin. **Tennis und Wettfinder melden
weiterhin Result=exit-code / ExecMainStatus=1.** Erreichbare App und geplante
Timer sind also ausdrücklich keine Behauptung erfolgreicher automatischer Analysen.
Kein Dienst zurückgesetzt, kein Ersatz des Updaters und kein Produktiv-Pull.
