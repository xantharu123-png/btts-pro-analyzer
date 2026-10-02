# BetBoy – Scanner-Reparaturen, 02.10.2026

## Verifizierter Umfang

Reparaturauftrag: alle 16 Befunde aus dem
[Tiefenaudit](2026-10-02-scanner-tiefenaudit.md). Ausgangsstand
`4df3e1d58f976b8f87d3b6dde5ad950d333ed883`; eingefrorener Reparaturcode
`34c146fa2ff9a72fc06975b575ea1dc7376a965f`. Abschließender Codefreeze
mit Perioden-/Replay-/Trainingsnachprüfung und Kontexteffekt-Versionsgrenze:
`ce6e07e3881df61696dd15e54cbb38ec8fda175f`. Anschließend Testhelfer-Uhrvertrag
in `61f3627` und ausdrücklicher Fixture-Formattransport in `7e8ba91` korrigiert.
Aktueller Code-/Testfreeze: `7e8ba9149269a909a08a802a7bddd1a8009191c0`.

Alle 16 Fehler sind im Code korrigiert, mit regressionsfähigen Offline-Fällen
und unabhängigen Gegenprüfungen. Veröffentlichung und Vollsuite werden unten
erst nach ihrem tatsächlichen Abschluss belegt. Dieser Bericht behauptet keine
Verbesserung von Rendite, Trefferquote oder Verletzungs-/Wettereffekten.

## Änderungen je Befund

| ID | Korrektur | Grenze |
|---|---|---|
| T1 | Regulärer Tennislauf entdeckt den heutigen Zürcher Kalendertag. | Kein zusätzlicher täglicher Vollscan. |
| T2 | WTA Bo3; explizite Qualifikation Bo3, ATP-Slam-Hauptfeld Bo5. Tatsächlich vorhandene Fixture-Formatmetadaten durch beide Parser bis zur Berechnung erhalten. Ablehnungen der Abrechnung sichtbar. | Historische falsche Formatbelege nicht massenhaft überschrieben. Keine nicht belegten Providerfeldnamen oder Drawregeln erfunden. |
| T3 | ESPN/SofaScore unterscheiden gültig leere Antworten von HTTP-/JSON-Ausfall; auch Ergebnisabrufe. Teilantworten bleiben nutzbar, Fehler führen zu Exit 1. | Eine echte leere Antwort bleibt erfolgreich. |
| S1 | Entdeckungsabschluss an vollständigen Ligaumfang gebunden; erfolgreiche Ligen wiederverwendet, nur fehlgeschlagene wiederholt. | Maximal drei Versuche/Liga/Tag, 20 Minuten Abstand; erschöpfter Abruf bleibt unvollständig, ohne weitere Abfrage. |
| L1 | Nur belegte Regulationsphasen; kein pauschaler Endpunkt Minute 93. In laufender Nachspielzeit keine erfundene sichere Nullrestzeit. | Unbekannter Abpfiff wird nicht als bekanntes Spielende gerechnet; Verlängerung separat ausgeschlossen. |
| B1 | Native neutrale Spielorte für kommende NBA-/EuroLeague-Spiele übernommen. | Kein erfundener neutraler Spielort bei fehlendem Flag. |
| H1 | Explizite native Rücknahme eines Finals entwertet aktuelle Historienansicht; frühere Revision bleibt für frühere Stichtage verfügbar. | Fehlen auf einer anderen Seite ist keine Löschung. Keine SQL-Migration. |
| R1 | Erfolgreicher vollständiger Torabruf und Abgleich mit Regulations-/Snapshotstand erforderlich; HTTP-Fehler und unvollständige Torliste bleiben offen. | Keine pauschale Neuabrechnung abgeschlossener Altzeilen. Statistik nach neuer Policy v2 getrennt. |
| F1 | Frische von Ecken-/Kartenmärkten aus tatsächlich verwendeten Count-Belegen. | Neue Tordaten machen alte Ecken-/Kartendaten nicht frisch. |
| F2 | Projektionserfolg pro Fußballfamilie; Eckenfehler sperrt nicht erfolgreich kalibrierte Tor-/Kartenfamilien. | Kohärenz innerhalb einer Familie weiter strikt; keine behauptete statistische Unabhängigkeit. |
| F3 | Saison-/Formcache im langlebigen Analyzer hat 24 Stunden TTL, fehlgeschlagene Aktualisierung 15 Minuten Rückoff. | Kein veralteter Cache als frisch, kein Refresh auf jedem Render. |
| J1 | Generationsprüfung und atomare Dateiveröffentlichung unter derselben kurzen Sperre; done erst nach Persistierung. | Alte abgebrochene Generation überschreibt keinen neueren Job. |
| E1 | Eindeutige native abgeschlossene Serien vor Stichprobengrenze, Form und Elo; Konflikte auch zwischen beiden Teamhistorien ausgeschlossen. | Korrekt gespiegeltes direktes Duell zählt im Elo einmal; Duplikate füllen keine 20er-Stichprobe. |
| T4 | Neue Version invertiert Halte- zu Aufschlagpunktchancen und rechnet alternierende Tiebreak-Aufschläge; entscheidender ATP-Bo5-Tiebreak bis zehn. | Legacy bleibt exakt replaybar; neue Kalibrierung beim regulären Rebuild. |
| T5 | Kalibrierter Siegeranker gewichtet gemeinsam dieselbe terminale Tennisverteilung; Satz-/Spiel-/Handicap-/Tiebreakmargen kohärent. | Versionsgebundene Umstellung, keine nachträgliche Umschreibung alter Prognosen. |
| R2 | Zusammenhängende Expositionsintervalle ohne Minutenlücken; jedes ganzzahlige Tor genau einer Phase zugeordnet. | Berichtsraten sind keine automatisch nachgewiesenen Live-Koeffizienten. |

`time.extra` wird nicht als angekündigter Endpunkt interpretiert: Die Quelle
beschreibt die verstrichene Nachspielzeit, nicht die verbleibende Zeit
([API-Football-Dokumentation](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide)).
Grand-Slam-Format nach [ITF-Regeln 2026, I.L](https://www.itftennis.com/media/5986/grand-slam-rulebook-2026-f2.pdf).

## Tests und unabhängige Gegenprüfung

Gruppen überschneiden sich; Zahlen nicht addieren:

- Root-Abschlussgruppe: 97 bestanden (Frische, Familien, Cache, Jobs, Shadow).
- Tennis: 372 bestanden; Restpfad SofaScore red-first reproduziert und repariert.
- Live/Rotkarten: 204 bestanden; zusätzlich plausible Halbzeitphase abgesichert.
- E-Sport-/Context-Abschlussgruppe: 225 bestanden. 34 separate B1/H1/E1-Regressionsfälle erhalten.
- Unabhängig: 329 Sport-/Live-Integrationsfälle und 197 E-Sport-Context-/Replayfälle bestanden.
- Unabhängiger Tennisgegenlauf: 30 Reparaturfälle, 24 exakte Legacy-Replays,
  36 separate Tiebreak-Gegenrechnungen (maximale Abweichung 8,44e-15),
  90 gemeinsame Marginalprüfungen bestanden.
- S1-Abschlussreview: 40 Tests plus 12 separate Wrapper-/Exitfälle bestanden.
  Das Review fand zuvor den erschöpften-Abruf-Fehler; Redtest bestätigte ihn,
  danach kein falscher Erfolg und kein vierter Providerabruf.
- R1-Perioden-Nachprüfung: 309 Tests bestanden; unabhängig 71 Tests plus
  12 direkte Fälle. Snapshotphase und Nachspielzeit sind in den bestehenden
  Kontextdaten gebunden. `1H 45+4` liegt vor `2H 46`, Halbzeit hinter allen
  Ersthalbzeittoren. Ungültige/mehrdeutige Legacy-Clocks bleiben offen.
- Die breite Runde auf `34c146f` fand historische Tennis-Replays, deren
  genaue Quellidentität den neuen Executor noch nicht zuließ. Korrigiert durch
  eine gerichtete Freigabe ausschließlich bekannter LF-/CRLF-Quellhashes,
  nicht durch eine pauschale Abschaltung der Integritätsprüfung. Schema-2-State
  darf keine Legacy-Quellidentität tragen. 149 Kontexttests und 196 angrenzende
  Versionsprüfungen bestanden; unabhängig erneut 149 Kontexttests sowie alle
  acht Alt-/Neu-Kombinationen und unbekannte/rückwärts inkompatible Quellen geprüft.
  Neue ATP-Serve- und WTA-Originale über den echten Livepfad erzeugt und ohne
  Datenbankänderung nachgespielt; kein Training/API-Abruf beim Replay.
- Derselbe State-/Source-Vertrag gilt nun ausdrücklich auch im Training.
  450 überlappende Tests bestanden, unabhängig 254. Die vier weiteren Fehler
  der breiten Runde waren veraltete CLI-Mockzustände: Der reguläre Builder
  muss nun V2 liefern. Neue Regressionen prüfen frische Legacy-Upgrades und
  V1-Builder-Ablehnung mit unveränderten Originalartefakten.
- Eine zusätzliche Policy-Reproduktion zeigte, dass ein altes Kontextmodell
  sonst trotz neuem Winner-Core übernommen werden könnte. Der owning Worker
  verzweigt bei POINT vor dem alten Effektselector: Grundprognose und echte
  Kontextdaten werden normal veröffentlicht, alte Effekte weder angewandt noch
  verglichen. 29 Worker-Tests am Endstand bestanden; die finale Vereinfachung
  unabhängig statisch geprüft. Ein vorheriger Guardstand hatte unabhängig 208
  Worker-/Runtime-/Auditfälle bestanden. Der Approval-Verifier im Policytest ist
  ausdrücklich ein Stand-in, **kein realer empirischer Freigabenachweis**.

Die erste breite Runde wurde während letzter Reviewkorrekturen bewusst beendet.
Sie ist weder ein PASS noch ein fachlicher Fehlbeleg. Die folgende breite Runde
auf `34c146f` ist wegen der genannten Replayintegration nicht der finale PASS:

```text
.codex_test_venv\quality\Scripts\python.exe -B -m pytest -q
-p no:cacheprovider --basetemp .pytest_tmp/oct2-frozen-34c146f
--junitxml=output/playwright/full-frozen-34c146f-20261002.xml tests
```

Diese Runde endete mit 62 Fehlern / 11.981 bestanden / 97 Skips / 111 bestandenen
Untertests (40:08 Minuten). Alle Fehler gehören den genannten drei Gruppen:
45 Runtime-Replay, 13 Training-Replay, vier CLI-Testverträge. JUnit SHA-256:
`cee34a7cf5c3372837e1c236dcc256128ac58760dabdd0eed016bd16f7c3aac1`.

Die Vollsuite auf `ce6e07e` wurde bei ungefähr 37 % unterbrochen, nachdem
Setupfehler konkret reproduziert waren. Ursache war ausschließlich eine neue
Testhelfer-Regression: `run_batch` setzte den Append-Zeitpunkt auf
`decision+2`, während bestehende historische Fixtures tatsächlich erst später
publizieren. Dadurch wäre ein Shadowbeleg vor seiner Originalveröffentlichung
entstanden; der Produktionsvertrag lehnte dies korrekt ab. Kein Speicher- oder
Tempfehler. Die bisherigen Defaults `NOW+2/+3` sind wiederhergestellt; nur die
vier neuen Policyfälle erhalten einen expliziten späteren Append-Zeitpunkt.
133 betroffene Coordinator-/Shared-History-/Worker-Tests und 843 weitere direkte
Helferverbraucher bestanden danach (976 insgesamt, neun Windows-Skips).
Unabhängig der gesamte Importgraph mit 1.120 bestandenen Tests/neun Skips.
Diese unterbrochene Runde ist kein PASS.

Die folgende Runde auf `61f3627` wurde ohne beobachteten Fehler bei ungefähr
18 % unterbrochen, um die im letzten Review erkannte T2-Transportlücke zuerst
zu korrigieren. Beide Parser verwarfen die vom Formatvertrag ausgewerteten
expliziten Felder. Der schmale Patch reicht nur tatsächlich vorhandene
`best_of`-/`qualifying`-Angaben durch; keine neuen Aliase oder Drawregeln.
18 echte Parser→Scan-Matrixfälle, zuerst 14 rot/vier Namensfälle grün, danach
121 betroffene Tests grün; unabhängig 98 Pipeline-/Metadatenprüfungen sowie
sechs echte Worker→Original→Speicherfälle inklusive Konfliktabwehr bestanden.
Die zusätzlichen Metadaten in den Testantworten sind
synthetisch: Damit ist keine tatsächliche Providerfeldabdeckung oder heutige
Produktionsbetroffenheit bewiesen. Fehlende Metadaten behalten die Namensregel;
Widersprüche werden vor einer Veröffentlichung abgelehnt.

Der Lauf seit 13:10 CEST auf `7e8ba91` erreichte ohne beobachteten Fehler ca.
34 %, wurde aber bei einem Verlust der Tool-/Prozessverbindung beendet.
Kein JUnit-Abschluss vorhanden und kein entsprechender Pythonprozess mehr
aktiv; ebenfalls kein PASS. Derselbe unveränderte Freeze lief ab 13:37 CEST
über einen versteckten lokalen Runner mit dauerhaftem stdout/stderr-Protokoll
und eigenem Exitstatus. Der Runner startet ausschließlich die Offline-Suite.
Keine weiteren Codeänderungen oder Anbieterabfragen.

```text
.codex_test_venv\quality\Scripts\python.exe -B -m pytest -q --tb=short --maxfail=1
-p no:cacheprovider --basetemp .pytest_tmp/oct2-durable-7e8ba91
--junitxml=output/playwright/full-durable-7e8ba91-20261002.xml tests
```

Dieser Lauf endete 14:12 CEST mit Exit 1: 4.884 bestanden, 26 Skips, ein
Fehler, 85 bestandene Untertests. Der konkrete Fehler war die lokale
Testumgebung: Der WindowsApps-WSL-Alias wurde statt Git-Bash aufgerufen.
Mit prozesslokal vorangestelltem `C:\Program Files\Git\bin` bestehen beide
echten Shell-Hook-Tests. Kein Skip, kein Produktions- oder Testcodepatch.
Die JUnit-Datei enthält 4.911 primäre Testzeilen; ihr Header zählt zusätzlich
85 Untertests, diese dürfen nicht als zusätzliche Primär-IDs addiert werden.
JUnit SHA-256:
`4f27370b152d531ff32bbcac4033305c0db55aba58a0cb5cbdd36378ba1dc0d7`.

Die Fortsetzung verwendet konservativ nur **vollständig belegte Dateien**:
12.183 exakt gesammelte, groß-/kleinschreibungs-sensitive Primär-IDs aus 303
Dateien. 105 vollständig fehlerfreie Dateien mit 4.844 IDs sind übernommen;
198 Dateien mit 7.339 IDs werden vollständig neu geprüft, einschließlich aller
351 Fälle der fehlgeschlagenen/unvollständigen Hook-Datei. Alle 67 ersten
Hook-Ergebnisse werden verworfen. Sammlung, pytest-JUnit-Namensabbildung,
Manifest und unveränderte Nicht-Markdown-Eingaben unabhängig geprüft.
Manifest SHA-256:
`fc976972dd73a88c68cc7aef6fe9f70ea13260b294c411573abe383a1f3158c5`.

Ein erster versteckter Fortsetzungslauncher um 14:30 CEST endete vor einem
Test-/Statusbeleg, kein PASS. Der geprüfte Runner läuft seit 14:32:55 CEST
ausdrücklich mit der vorhandenen PowerShell 7.6.5 und Git-Bash-PATH.
Eigene stdout/stderr-/Runner-/Exitdateien unter `output/playwright/`.
Der Restlauf endete **14:45:23 CEST mit Exit 0**: 7.268 bestanden, 71 Skips,
26 bestandene Untertests (12:25 Minuten). Der anschließende Aggregator belegte
**alle 12.183 gesammelten Primär-IDs exakt einmal**: **12.086 bestanden,
97 Skips, null Fehler/Errors**, 303 vollständig belegte Dateien. Code-/Testfreeze
und Nicht-Markdown-Fingerprint sind unverändert:
`3da0e7d8459ff7e57b2a2341d9f63db9e6ab3e646f7fa42155e848647aad7ede`.
Zusätzlich 111 bestandene Untertests über beide Gruppen; nicht als weitere
Primärtests gezählt. Das ist vollständige Testabdeckung in zwei disjunkten
Dateigruppen, **kein einzelner erfolgreicher Vollsuite-Aufruf**.
Ein unabhängiger reiner Lesevalidator bestätigte anschließend Sammlung,
JUnit-Namensabbildung, beide disjunkten Gruppen und kombinierten Bericht:
jede ID genau einmal, keine unbekannten/fehlenden/doppelten Fälle, keine
Failures/Errors; der ursprünglich fehlgeschlagene Shellfall ist jetzt PASS.
Auch Exit 0, unveränderte Quellidentität und 85+26 separate Untertests bestätigt.

- Rest-JUnit SHA-256:
  `f11490761412912bed2152a3f0489a5c3e66dc7ef84a0831be8e17d760beb35e`.
- Kombinierter, ausschließlich ausgewählter JUnit SHA-256:
  `e2f0fcb4816aa8e2e410b5a2bb93ba137e0bb14f68b9865523abd93e5e68b9f8`.
- Coverage-JSON SHA-256:
  `ad850c56853abebdc72df5be1a6e4cd0ed8a22d687e5c79a7500773c69951e6e`.
- Exit-/Freeze-Status SHA-256:
  `24a9e514222ec70564d1b9ca1f46228e54935174f8c92e974e1d661df73078b5`.

## Veröffentlichung

Noch nicht veröffentlicht. Lokaler Reparaturcommit vorhanden; GitHub/VPS bleiben
bis zum Abschluss der Prüfung auf `4df3e1d`.

Read-only VPS-Preflight 11:08 CEST: 18 GB frei, ungefähr 3,3 GB verfügbarer RAM;
App aktiv, geprüfte Sportdienste inaktiv, sieben Timer geplant. Keine neue
Sicherung oder Bereinigung erforderlich. Kein neues Paket, SQL-Schema oder
systemd-Unit nötig. Produktionsvenv enthält kein pytest; daher dort nur reine
Linux-Funktions-/Syntaxprüfungen mit ausdrücklich verbotenem Netzwerkzugriff.

Deployment nur ff-only nach exaktem Remote-/Commit-/Dateiumfangabgleich,
unter bestehender Deploysperre und mit inaktiven Schreibern. Vor Pull nur App
kontrolliert stoppen, Linux-QA auf 45 Sekunden plus Killreserve begrenzen; erst
bei Erfolg wieder starten. Mindestens 300 Sekunden Timerreserve, keine
behauptete harte Gesamtlaufzeitgarantie. Fehlerphase und Appzustand ausdrücklich
melden statt gemischten Zustand als Erfolg auszugeben. App-Stop/Pull/Start
zusätzlich auf 35/25/95 Sekunden mit je fünf Sekunden Killreserve begrenzt;
Timerreserve auf **300 Sekunden** erhöht. Der exakte Helfer unabhängig erneut
unter Linux per `bash -n` geprüft (SHA-256
`b34220ea154c17f93ef153e85d1be788672ae08d333fbe0c58c13f09a84c1886`).
Keine Sportdienste
zusätzlich starten. Bestehende Wettfinder-/RisikoBet-Snapshots
vorher/nachher per SHA-256 vergleichen. Healthchecks und exakte Commitgleichheit
erst nach Ausführung dokumentieren.

## Aktivierung und verbleibende Nachweisgrenzen

- Der nächste reguläre Tennislauf am **03.10.2026, 00:05 Europe/Zurich** erzwingt
  den Aufbau von `serve-points-joint-v2`, auch bei noch frischem Legacy-Artefakt.
  ATP/WTA werden getrennt und mit passender kausaler Kalibrierung veröffentlicht.
  Bis dahin bleiben bestehende `hold-proxy-v1`-Artefakte unverändert verwendbar.
  Aufbaufehler behalten den alten Stand und führen zu Pipeline-Exit 1.
- Neue Tennis-State-Payloads haben Schema 2. Nach deren Veröffentlichung ist
  ein reiner Rücksprung auf Code vor dieser Reparatur nicht schemafähig.
  Alte Artefakte bleiben in der vorhandenen unveränderlichen Historie, kein
  zusätzliches Backup erstellt und kein automatischer Manifestrücksprung.
- Neue Shadow-Abschlussmarker prüfen den Ligaumfang. Der nächste **reguläre**
  Timer kann einen noch nicht vollständig belegten Spielplan nachholen; nicht
  mit einem manuell ausgelösten Sportscan verwechseln.
- Fünf im Audit dokumentierte ungeklärte Tennis-Ergebnisse bleiben ungeklärt,
  bis passende native Ergebnisbelege vorliegen. Neue Fehlerbehandlung ist
  kein erfundener Endstand und keine Erlaubnis, alte Prognosen zu löschen.
- Verletzungs-/Müdigkeits-/Wetterwirkung samt unabhängigem Qualitätsnachweis
  sowie WTA-/weitere Sport-Daily3-Vergleiche bleiben offen. POINT-Kontexteffekte
  brauchen einen eigenen Algorithmus-/Qualifizierungsvertrag; neue Basis-
  prognosen sind deshalb nicht gesperrt. Diese 16 technischen
  Reparaturen ersetzen fehlende Daten und eine zeitlich unabhängige Messung nicht.
- Cricket-Anbindung, Timerhäufigkeit, Echtgeldledger und Schwellen unverändert.
  Inherited WIP-/Audit-/Browserdateien nicht bereinigt oder in den Codecommit gepackt.
