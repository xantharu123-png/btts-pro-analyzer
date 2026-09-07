# Kontextdaten: belegter Ausgangsstand am 7. September 2026

Dieser Bericht trennt vorhandene Rohfelder, implementierte Verarbeitung,
zeitkorrekte Modellabnahme und produktive Aktivierung. Er ist kein Nachweis,
dass Verletzungen oder Belastung bereits die Nutzerwahrscheinlichkeit verändern.
Cricket ist ausdrücklich nicht Bestandteil dieser Umsetzung.

## Prüfgrenzen

- Referenz der Codeprüfung: Entwicklungszweig `codex/kontextmodell-20260907`,
  zuletzt abgeschlossener Aufgabenstand `e08b48cae799c6cc22fdf6921c6c336c1f0a57df`.
- Die Quellenprüfungen waren begrenzte Lesezugriffe. Nur die beiden Fußballabrufe
  reservierten ihr Kontingent im vorhandenen produktiven Budgetbuch.
- Keine Zugangsdaten, Header, neuen Verträge oder bezahlten Tarife wurden gespeichert
  oder eingerichtet. Keine Prognose, Abrechnung oder Modellaktivierung wurde durch
  die Probes verändert.
- Ein Feldname im Code oder ein synthetischer Test beweist keine Live-Abdeckung.
  Eine nachträglich geladene historische Meldung beweist nicht, dass sie vor dem
  damaligen Spiel bekannt war. Alle Zeiten unten sind tatsächliche UTC-Abrufzeiten.

## Fußball: echte Spielerdaten nachgewiesen, zeitliche Historie noch nicht

Genau zwei budgetierte API-Football-GETs am 07.09.2026:

1. `fixtures`, gebündelt für native IDs `1593305` und `1570343`, Empfang
   `14:46:05.939454Z`, HTTP 200, eine vollständige Antwortseite.
2. `injuries`, dieselben IDs, Empfang `14:47:03.758708Z`, HTTP 200,
   zehn Datensätze, eine Antwortseite.

Das abgeschlossene Spiel `1570343` (22.08.2026, Athletic Club/Sevilla,
native Team-IDs `531`/`536`) enthielt je Team 11 Startspieler, 12 Ersatzspieler
und 23 Spielerstatistiken. Je Team hatten 16 Spieler einen nichtleeren Minutenwert.
Die realen Strukturen enthalten `player.id`, `statistics[].games.minutes`,
`position`, `substitute` und Leistungsfelder. Der Detailabruf enthält diese Daten
bereits im verschachtelten `players`-Block; ein zusätzlicher Spieler-Endpunkt
ist für diesen Strukturnachweis nicht erforderlich.

Das beim Abruf noch nicht gestartete Spiel `1593305` hatte keine Aufstellung
und keine Spielerstatistik. Das ist keine Bestätigung eines vollständigen Kaders.
Die konservierten Struktursamples enthalten ausgewählte Spieler, nicht den ganzen
Kader; daraus darf kein positiver Vollständigkeitstest gebaut werden.

`Missing Fixture` umfasst im gemessenen Verletzungsfeed neben medizinischen
Begründungen auch `Coach's decision` und `Inactive`. Nicht jeder Ausfall ist eine
Verletzung. Die Antwort liefert das Spiel-Datum, aber keinen belegten historischen
Veröffentlichungszeitpunkt der Meldung. Der September-Abruf darf daher nicht auf
den August-Spieltermin zurückdatiert werden.

Die bestehende Basishistorie enthält außerdem CSV-Zeilen mit internen, negativen
Pseudo-Spielkennungen. Der API-Tail kann Teamkennungen umordnen und behält bei
Duplikaten die CSV-Zeile. Ein Spielerabgleich braucht einen verifizierten nativen
Join; ein bloßer gleicher Name oder eine negative Kennung genügt nicht.
Die aktuelle Torbasis nutzt 12 Venue- und 6 Formspiele, eine 75/25-Mischung,
getrennte Tor-/xG-Stichproben und Liga-Priors mit Gewicht 4 beziehungsweise 3.
Es existiert dort kein zusätzlicher zeitlicher Zerfallsfaktor, der nachträglich
als vermeintliche Basiseigenschaft angesetzt werden dürfte.

Primärdokumentation: [API-Football-Einstieg und Endpunkte](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide),
[Kontingent- und Abrufoptimierung](https://www.api-football.com/news/post/how-to-optimize-api-sports-calls-and-quota-usage).

## Tennis: Games und native Teilnehmerkennungen, keine bewiesene exakte Erholung

- Ein SofaScore-Abruf für den 06.09.2026 lieferte am 07.09. um `14:39:47Z`
  HTTP 403. Er wurde nicht wiederholt oder umgangen.
- Nach einem verworfenen Diagnoseparser wurde genau ein korrigierter ESPN-ATP-Abruf
  um `14:41:09Z` ausgewertet: HTTP 200, ein Turnier, 239 Einzel-Begegnungen,
  davon 228 abgeschlossen. Die Antwort enthält auch ältere Turniermatches;
  diese Zahlen sind ausdrücklich keine Zahl heutiger Spiele.
- Der reale Pfad ist `events[].groupings[].competitions[]`. Zwei auf den
  24.08.2026 datierte Beispiele belegen `competition.id`, `competitors[].id`,
  Satz-Games und optionale Tiebreak-Werte. `athlete.id` war kein Ersatz für die
  tatsächlich vorhandene Teilnehmerkennung.
- Die untersuchten `statistics`-Listen waren leer. Es gab keinen gemessenen
  Matchende- oder Dauerwert. Das Turnier-`endDate` ist kein Matchende;
  `date/startDate` belegt keinen tatsächlichen Beginn. `format.regulation.periods`
  war selbst bei 2:0-Qualifikationsmatches 5 und beweist daher kein Best-of-Format.

Die bisherige automatische Verarbeitung verwirft Teilnehmerkennungen und Games
und speichert überwiegend Satzsiege. `result_observed_at` ist ein echter Empfangs-
zeitpunkt, kein Endzeitpunkt. Er kann nur eine entsprechend benannte Untergrenze
der Erholung begründen. Historische ATP-Trainingsfelder enthalten zwar native
Spielerkennungen und optionale Dauerwerte; ihr Turnierstartdatum ersetzt ebenfalls
keinen Matchbeginn oder eine prospektiv belegte Verfügbarkeit.

Separate WTA-Quellenprüfungen um `14:14Z` waren nur HEAD-Zugriffe:
HTTPS ergab einen TLS-Fehler, der bestehende HTTP-Pfad HTTP 503. Ein späterer
HTTPS-Indexaufruf endete mit Timeout. Das ist weder ein erfolgreicher WTA-Refresh
noch der Beweis, dass ein regulärer GET-Build generell unmöglich ist.
Ein echter tourgetrennter Build bleibt ein eigener A4/Release-Nachweis.

## Basketball, Eishockey und E-Sport

| Sport | Gemessene oder im bestehenden Code belegte Grundlage | Noch nicht belegt |
| --- | --- | --- |
| Basketball | Bestehender Event-/Team-/Ergebnispfad; ein NBA-ESPN-Scoreboard-GET am 07.09. um `15:23Z` für 01.01.2026 ergab HTTP 403, ohne Wiederholung. | Tatsächliche Spieler-Minuten, Rotation und zeitgestempelte Einsatzmeldungen dieses Pfads. |
| Eishockey | Ein offizieller NHL-Schedule-GET um `15:23Z` für 01.01.2026 ergab HTTP 200 mit 50 Ereignissen im gelieferten Zeitraum; zwei abgeschlossene Beispiele wurden untersucht. Native IDs und Perioden-/Ergebnisinformationen waren vorhanden. | Eiszeiten und vor Spielbeginn bestätigte Torhüter. `winningGoalie.playerId` ist ein nachträgliches Ergebnisfeld, keine vorzeitige Starterbestätigung. Ein gesonderter Boxscore-Dokumentationsaufruf wurde vom Webwerkzeug nicht geöffnet; daraus ist keine NHL-HTTP-Antwort abzuleiten. |
| E-Sport | Bestehender Code führt native Match-/Teamkennungen, Serienformat und Serienhistorie. Kein zusätzlicher Providerabruf. | Gemessene Spieler-/Roster-/Patch-/Map-Zeitlinien und persistente kontoweite Tageskontingentierung für diesen Kontextpfad. |

## Wetter und vollständige Belastungshistorie

Der bisherige OpenWeather-Pfad sucht nach Stadt/Land, nimmt den ersten
Geokodierungstreffer und einen nahe gelegenen 3-Stunden-Vorhersagepunkt.
`forecast_at` benennt dort die Gültigkeitszeit, nicht die Ausgabe- oder
Empfangszeit. Die vorhandene Kontextprojektion trennt diese Uhren noch nicht
zuverlässig. Exakte Stadionzuordnung, Dach-/Indoor-Beleg, persistente
Vorhersagerevisionen und eine vollständige wettbewerbsübergreifende
Belastungszeitlinie sind damit nicht nachgewiesen.

Es wurden keine Wetterarchivdaten abgerufen. Die private/nichtkommerzielle oder
kommerzielle Nutzung von BetBoy ist für eine mögliche zusätzliche Archivquelle
noch ungeklärt; es wurde kein Tarif gebucht. Eine Modellinitialisierung allein
beweist außerdem nicht, wann der einzelne Vorhersagelauf tatsächlich verfügbar war.

Primärdokumentation: [OpenWeather-Vorhersagefelder](https://openweathermap.org/api/forecast5),
[Open-Meteo Previous Runs](https://open-meteo.com/en/docs/previous-runs-api),
[Single Runs](https://open-meteo.com/en/docs/single-runs-api),
[Nutzungsbedingungen](https://open-meteo.com/en/terms).

## Nachweise und offene Abnahme

Die datierten, bereinigten Diagnoseartefakte liegen im lokalen SDD-Arbeitsbereich
`2026-09-07-kontextmodell-umsetzung`: `football-source-probe-20260907.json`,
`football-injuries-probe-20260907.json`, `espn-source-probe-20260907.json`,
`basketball-nhl-schedule-probe-20260907.json` und die zugehörigen Source-Readiness-
Berichte. Die owning B/C-Aufgaben übernehmen ausschließlich belegte strukturelle
Samples in ihre versionierten Testfixtures und aktualisieren diesen Bericht.

Noch offen sind die jeweiligen Normalisierer, tatsächlichen Referenz-/Merkmals-
rechnungen, empirischen Modellvergleiche und Produktionsnachweise. Ein späteres
leeres oder zeitlich ungeeignetes Trainingsset bleibt eine Datenabhängigkeit;
es darf nicht als erfolgreicher Modellbuild oder als eingerechnete Wirkung gelten.
