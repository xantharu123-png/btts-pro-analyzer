# Tennis: bestätigte Ergebnisse in der Modellbasis

## Auftrag und Status

Freigegebene begrenzte Reparatur nach Hurkacz–Davidovich (13.10.2026):
bereits bestätigte, zum Trainingsstichtag bekannte Ergebnisse dürfen nicht nur
im Belastungs-/Ergebnisbeleg stehen, während sie in der Elo-Modellbasis fehlen.
Keine erfundene Verletzungs-/Müdigkeitskorrektur oder neue Tipp-/Preisfreigabe.

Arbeitskopie: `.worktrees/audit-repairs-20261013`; Ausgangscommit `dd704ade`.
Code umgesetzt; gezielte Prüfung und unabhängiges Review bestanden.
Vollprüfung nach Unterbrechung in zwei vollständigen Dateigruppen laufend.
Commit/Push/VPS-Veröffentlichung noch ausstehend.

## Konkreter Datenbruch

- Vor dem Hurkacz-Spiel war ESPN-Spiel `184936` (Davidovich–Tiafoe) bereits
  als normal beendet gespeichert: Davidovich gewann 7:6, 4:6, 7:6.
- Native IDs: Tiafoe `2708` → vorhandener Modellschlüssel `tiafoe f`,
  Davidovich `3212` → `fokina a`. Vier unveränderliche Originalbelege bestätigen
  dieselbe Zuordnung. Der Belag Hard stammt aus dem ausgeführten Modellinput,
  nicht aus einem neuen nativen ESPN-Belagbeweis.
- Erster tatsächlicher Ergebniseingang: **11.10.2026 22:05:49.627593 UTC**.
  Die Shadow-Abrechnung hat einen getrennten, etwas späteren Eingangsstempel.
  Tatsächlicher Spielbeginn, Spielende und Minuten bleiben unbekannt.
- Im aktiven ATP-2026-CSV fehlt das Paar Davidovich/Tiafoe vollständig.
  Der bisherige Tour-Build las ausschließlich die CSV-Ergebnisse.
- Der verlorene Hurkacz-Tipp war keine sichere Auswahl: zuletzt 55,03 % für
  Hurkacz. Daraus folgt weder, dass dieser Datenbruch allein den Verlust
  verursachte, noch, dass die Reparatur dieses einzelne Ergebnis vorhersagt.

## Reparaturvertrag

`tennis/result_training.py` liest ausschließlich vorhandene, physisch geprüfte
Original-/Status-/Siegerbelege in einem read-only Snapshot. Keine neue Quelle,
Datenbanktabelle, Migration, Netzwerkanfrage oder permanente Historienkopie.

1. Nur ATP/WTA-Einzelspiele mit vorhandener, konsistenter Originalbindung und
   bereits bekannten Modellspielern. Modellzustand und tatsächliche
   Veröffentlichung müssen vor dem Original-Entscheidungszeitpunkt liegen.
2. Neueste **ganze** native Revision am Trainingsstichtag entscheidet.
   Spätere fehlende Siegerflags, Rücknahmen, Ersatzteilnehmer, Doppelspiele,
   Retirement oder Konflikte dürfen keinen älteren Sieger wiederbeleben.
   Siegerbeleg und Status müssen aus derselben tatsächlichen Rezeption stammen.
3. Global widersprüchliche native Spieler-/Modellschlüssel sowie abweichende
   Belag-/Namensbindungen schließen den betroffenen Ergänzungsfall aus.
   Veröffentlichung muss vor ursprünglichem und gemeldetem Start liegen.
4. Mehrere Prognosen, ursprüngliche Ansetzungen und wiederholte Rezeptionen
   desselben nativen Ereignisses zählen einmal. Unveränderte Wiederholungen
   behalten den ersten bekannten Zeitpunkt; echte Korrekturen ihren neuen.
5. Konservative CSV-Überlappung: gleiches ungeordnetes Paar in einem möglichen
   ATP-Turnierfenster von 30 Tagen beziehungsweise WTA-Ergebnistag ±2 Tagen
   bleibt CSV-eigen. Kein geratenes ESPN↔ATP-Turnier-ID-/Namensmatching.
6. Zugelassene fehlende Sieger aktualisieren **nur Elo**. Keine erfundenen
   Aufschlag-/Returnpunkte, Spieldauer, Genesung oder numerische Kontexteffekte.
   CSV-Zeilen behalten ihre bisherige Proxy-Reihenfolge; Ergänzungen werden
   anhand ihres bekannten Ergebniseingangs einsortiert. Das ist keine Behauptung
   exakter Matchende-Chronologie für die CSV.
7. CSV-Abdeckungsdatum und `tournament_start_proxy`/`result_date` bleiben erhalten.
   Ergänzungszahlen erscheinen getrennt im technischen Refreshbericht.
   Ursprüngliche Prognosen, Abrechnungen, Geld und Wettpreise bleiben unverändert.
8. Bestehender täglicher Pipelineaufruf: frische Tourmodelle werden an einem
   neuen UTC-Trainingstag aus ausschließlich vorhandenen Cachedateien aufgebaut,
   statt bis zu sieben Tage an lokal bekannten Ergebnissen vorbeizulaufen.
   Kein zusätzlicher Timer, Sportscan oder Source-Fetch. Die vorhandene
   Sieben-Tage-Quellenprüfung bleibt für stale/force/version-upgrade erhalten.
   Cachemisses schlagen begrenzt fehl und erhalten das alte Tourartefakt;
   auch Kalibrierungsloader dürfen in diesem Pfad nicht nachladen oder seeden.
9. Gleicher CSV-Abdeckungsproxy erlaubt keinen Zeitrücksprung: Beim CAS-Neulesen
   wird zusätzlich der volle Trainingsstichtag verglichen. Ein älterer paralleler
   Aufbau darf einen bereits neueren Zustand nicht überschreiben.
10. Die additive Cache-only-Ergänzung hat eine neue exakt gepinnte LF/CRLF-
    Quellenfamilie. Bestehende Pins bleiben unverändert; alte Originale werden
    nur in Richtung des neuen Executors zugelassen. POINT-Zustände benötigen
    weiterhin eine vollständige bekannte Quellenfamilie. Unbekannte oder
    gemischte Inferenzquellen bleiben gesperrt. D2-Evaluationsberichte werden
    dadurch ausdrücklich nicht neu qualifiziert oder aktiviert.

## Verifikation

- RED: ATP und WTA jeweils nur eine statt zwei Elo-Beobachtungen; Datenbruch
  reproduziert. WTA-Testfixture anschließend an dessen tatsächliche native
  Event-ID gebunden (kein Produktivverhalten angepasst).
- Neuer Regressionstestbestand: **25 Fälle**; ursprüngliche 20 PASS in 9,75 s,
  anschließend tägliche Cache-Anbindung und die zwei Source-/CAS-Schutzfälle
  separat RED nachgewiesen. Finale betroffene Vier-Modul-Runde **151 PASS**,
  29,88 s, `cache-safety-green.xml`.
- Unabhängiger Abschlussreview: **145 PASS**, 29,52 s; keine offenen P1/P2-Befunde.
  Diese Prüfung überlappt mit eigenen Testmodulen; Zahlen nicht addieren.
- Echte VPS-Probe, nur lesend und Code nur im SSH-stdin-Speicher: Stichtag
  13.10.2026 01:39:34 UTC. 268 ATP-Ereigniskandidaten, 265 qualifiziert,
  3 verworfen. Prüfung gegen ausschließlich aktuellen 2026-CSV: 183 mögliche
  Überlappungen ausgeschlossen, 82 fehlende Ergebnisse übrig. Dies ist kein
  Beleg vollständiger Tour- oder Dreijahresabdeckung.
- `184936` bleibt nach Überlappungsprüfung **genau einmal** mit Sieger `fokina a`
  übrig, einschließlich des tatsächlichen ersten Eingangsstempels.
- Vorher/nachher-Signaturen identisch: 23 native Rezeptionen, 4 Originalartefakte,
  1 Shadow-Prognose und 4 unveränderliche Modellrevisionen für dieses Spiel.
- Keine neuen Backups, API-/Sportscans, Produktivkopien oder historischen Writes.
- Die Vollrunde `full3` fand historische Replay-Fehler nach dem Loader-Zusatz.
  Ursache reproduziert: fehlende neue Quellenfamilie, nicht geänderte historische
  Modellzahlen. Neuer Übergangstest zuerst RED (1 Fehler / 6 PASS), anschließend
  drei Schutzfälle gegen bekannte gemischte Legacy-Inferenzquellen ergänzt.
  Alte Pins und historische Belege unverändert. Der unabhängige AST-Vergleich
  bestätigt 26 unveränderte bestehende Loaderfunktionen; nur die beiden
  Erwerbsfunktionen enthalten den expliziten Cache-only-Guard.
- Read-only Produktionsprüfung: **0 aktive Kontextfreigaben**, aktive Slots
  ausschließlich `tennis:ATP` und `tennis:WTA`, keine Kontextartefakte. Bestehende
  D2-Evaluations-/Aktivierungsprüfung bleibt exakt und fail-closed.
- Neue gemeinsame Abschlussrunde einschließlich historischer Runtime-/D1-Replays:
  **364 PASS**, 316,65 s, `source-family-green.xml`. Zehn Quellenübergangs-
  Schutzfälle plus 25 Brücken-/Cache-/CAS-Fälle enthalten; keine überlappenden
  Zahlen addieren.
- Unabhängiger Quellenfamilien-Review ohne offenen Befund; eigene Runtime-/D1-
  Ausführung **213 PASS**, 308,02 s. Belegordner
  `guard-source-green-df478e09291f4d7c9558eb1c16f88b4b`. Überlappende Tests nicht
  als zusätzliche Vollsuite zählen. Acht historische Pin-Definitionen unverändert.
- Frische vollständige Collection: **13.922 Haupttest-Items**, `collection4.log`.
  Die acht geänderten Code-/Testdateien sind für den laufenden Volllauf per SHA256
  festgehalten (`code-and-tests-sources.json`). Nach Abschluss werden diese
  Dateihashes und die exakte JUnit-Abdeckung vor dem Commit erneut verglichen.

## Grenzen und nächste Abnahme

- Nur originalgebundene Ereignisse werden ergänzt; kein neues ganzes Tourarchiv.
- Konservative Überlappung kann getrennte echte Begegnungen vorsorglich auslassen.
- Identischer Eingangsstempel in getrennten Quellbatches mit identischen
  Status-/Workloadbytes, aber später fehlenden Siegerflags kann im bestehenden
  Quellenvertrag ununterscheidbar sein. Keine vollständige Konflikterkennung
  für nicht gespeicherte Informationen behaupten.
- Die ersten beiden begonnenen Vollrunden wurden für die nachträglich
  vervollständigte Tages-/Cache-/CAS-Anbindung kontrolliert abgebrochen. Nicht als
  PASS zählen. `full3` nach reproduzierten Quellenidentitätsfehlern ebenfalls
  beendet, kein PASS. Autoritative vollständige Abschlussrunde auf korrigierten
  Quellen: `full4` wurde durch die Unterbrechung bei 81 % ohne Fehlerbericht,
  aber auch ohne Abschluss-JUnit beendet. Kein Vollsuite-PASS daraus ableiten.
  Seit 14.10.2026 werden alle 13.922 Hauptitems in zwei gewöhnlichen pytest-
  Dateigruppen geprüft: `partition5.json`, `full5-A.xml` und `full5-B.xml`.
  Getrennte TMP-/Basetemp-Verzeichnisse, alle Moduldateien disjunkt und vollständig.
  Die Abschlussprüfung verwirft fehlende, doppelte oder unerwartete Haupt-IDs
  sowie jeden Fehler; Untertest-Zähler werden nicht als zusätzliche Haupttests
  ausgegeben. Acht Code-/Testdateihashes nach der Unterbrechung unverändert.
- Produktionsstatus 14.10.2026 07:01 CEST: weiterhin `dd704ade`, App/Caddy und
  sieben Timer gesund, beide Healthchecks ok. Regulärer Tennisjob meldet Erfolg;
  dieser alte-Code-Lauf bestätigt die noch unveröffentlichte Brücke nicht.
  Nächster regulärer Tennisaufbau: **15.10.2026 00:05 Europe/Zurich**.
- Der reguläre Lauf vom 14.10. ist tatsächlich vollständig beendet:
  00:05:22–00:31:17 CEST, Exitstatus 0, 45 Veröffentlichungen verarbeitet,
  35 neue Prognosen. `unresolved_outcome_events=[]`; Kontextaufnahme bleibt
  teilweise wegen 14 Teilnehmer-/Identitätskonflikten und einem nativ nicht
  verfügbaren Ergebnis. Diesen Konflikten wird kein Sieger erfunden.
  ATP/WTA wurden vom alten Code nur als frisch beibehalten (Trainingsstichtage
  12.10. 22:05 bzw. 11.10. 22:05 UTC): direkter Produktionsbeleg für den bislang
  übersprungenen täglichen Cache-Neuaufbau, kein Nachweis der neuen Reparatur.
- Frische Collection vom 14.10.: ebenfalls 13.922 IDs, keine geänderten IDs
  gegenüber `collection4.log`; `collection5-comparison.log`.
  Unabhängiges Review der Dateiaufteilung und strikten JUnit-Vereinigung bestanden.
- Vollsuite am 14.10.2026 08:12 CEST beendet: **13.825 PASS, 97 bestehende
  Plattform-Skips, 147 Untertests, null Fehler**, beide Prozesse Exit 0.
  A: 6.419 PASS/66 Skips/79 Untertests in 3.811,57 s;
  B: 7.406/31/68 in 3.598,25 s. `complete-qa5-check.log` bestätigt sämtliche
  13.922 Hauptitems genau einmal, keine fehlenden/doppelten/unerwarteten IDs
  oder Fehler. Alle acht eingefrorenen Code-/Testhashes unverändert; zusätzlich
  sind die 97 Skip-IDs exakt gleich zum vorherigen vollständigen A4/B4-Testbestand.
  Überlappende gezielte Läufe werden hierzu nicht addiert.
- Der unabhängige Deploy-Helper-Review korrigierte die Timerreserve: mindestens
  360 Sekunden bis zum nächsten Job, 300-Sekunden-Deadline nach letzter
  Idleprüfung, begrenzte PID-Abfragen und ein vollständig aufgeräumter einzelner
  Watchdog ohne vererbte Deploy-Lock-/SSH-Ausgabekanäle. Keine weiteren
  konkreten Freigabeblocker; Produktiv-/Testquellen dadurch nicht verändert.
- Commit/Push und source-only VPS-FF folgen jetzt nach den Abschlussgates.
  Ein begrenzter App-Neustart übernimmt alle Module deterministisch; Caddy,
  Timer, Berechnungsjobs, Modelle und Datenbanken bleiben unangetastet.
  Der nächste reguläre Modellaufbau übernimmt die Ergänzungen. Alte Modellartefakte
  werden nicht umgeschrieben; kein zusätzlicher Scan zur Beschleunigung.
- Software-/Datenweg-PASS beweist keine bessere Kalibrierung, Trefferquote oder
  Rendite und keine aktivierte Verletzungs-/Wetter-/Müdigkeitswirkung.
