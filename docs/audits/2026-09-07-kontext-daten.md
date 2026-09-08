# Kontextdaten: belegter Ausgangsstand am 7. September 2026

Dieser Bericht trennt vorhandene Rohfelder, implementierte Verarbeitung,
zeitkorrekte Modellabnahme und produktive Aktivierung. Er ist kein Nachweis,
dass Verletzungen oder Belastung bereits die Nutzerwahrscheinlichkeit verändern.
Cricket ist ausdrücklich nicht Bestandteil dieser Umsetzung.

## Prüfgrenzen

- Referenz der Codeprüfung: Entwicklungszweig `codex/kontextmodell-20260907`,
  zuletzt abgeschlossener Aufgabenstand `16d9c4e88435017c5841e613b9cd91670313813a`.
- Die Quellenprüfungen waren begrenzte Lesezugriffe. Nur die beiden Fußballabrufe
  reservierten ihr Kontingent im vorhandenen produktiven Budgetbuch.
- Keine Zugangsdaten, Auth-Header, neuen Verträge oder bezahlten Tarife wurden gespeichert
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

Die ersten WTA-Quellenprüfungen um `14:14Z` waren nur HEAD-Zugriffe:
HTTPS ergab einen TLS-Fehler, der bestehende HTTP-Pfad HTTP 503. Ein späterer
HTTPS-Indexaufruf endete mit Timeout.

Eine zusätzliche, auf genau drei GETs begrenzte Prüfung vom VPS um `17:27Z`
benutzte die vorhandenen Quelladressen und Produktionsvalidatoren, ausschließlich
im Speicher und ohne Cache-, Modell- oder Datenbankschreibzugriff:

- ATP-Turnierdatei: HTTP 200, 1.858.008 Bytes, 229 gültige 2026-Turniere bis
  zum Turnierstart-Proxy `2026-09-07`. SHA-256
  `1483ae267c77bddefb35025f730dc54e63e81a27efdf315b8ae2d484b574ae36`.
- ATP-Matchdatei 2026: HTTP 200, 4.182.140 Bytes, 11.680 gültig zugeordnete
  Saison-Resultatzeilen bis zu demselben Turnierstart-Proxy. Das sind weder
  heutige Spiele noch ausschließlich Tour-Level-Trainingsfälle. SHA-256
  `7a0cdeaa42ada513f4dbbfaadd35ff24d96b70047c0e63171dabb2c56b952c54`.
- WTA-Datei `2026w/2026.xlsx`: HTTP 503, daher nicht als Tabelle geparst oder
  zwischengespeichert. Keine Wiederholung, Umleitung oder TLS-Abschaltung.

Empfangszeiten waren `17:27:31.162784Z`, `17:27:33.212927Z` und
`17:27:33.292200Z`. Diese Probe bestätigt aktuelle ATP-Quellabdeckung und einen
konkreten WTA-GET-Fehler, aber keinen neuen Modellbuild oder Produktivrefresh.
Insbesondere ersetzt der Turnierstart-Proxy kein genaues Matchende. Ein echter
tourgetrennter Build einschließlich Kalibration bleibt ein eigener
A4/Release-Nachweis; die zukünftige WTA-Verfügbarkeit folgt nicht aus dieser Probe.

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

## Tatsächlich gespeicherte Prognosen und Kontextnachweise

Eine zusätzliche rein lesende VPS-Prüfung um `17:58Z` untersuchte den gemeinsamen
Prognosenachweis und den Tennisbestand. Im gemeinsamen Speicher standen 5.878
Fußballzeilen aus nur 19 gespeicherten Spielkennungen, 116 Tenniszeilen aus fünf
Kennungen und 84 E-Sport-Zeilen aus acht Kennungen. Für Basketball und Eishockey
gab es dort keine Zeilen. Nur vier Spielkennungen der fünf untersuchten Sportarten
hatten bereits gespeicherte Ergebnisse. Die Kennungen sind hier noch keine
quellenübergreifend verifizierten, eindeutigen Spiele; wiederholte Läufe und Märkte
dürfen die statistische Stichprobe nicht vergrößern.

Der Tennisbestand enthielt 1.239 Prognosezeilen, davon 104 mit Ergebnis-Empfangszeit
und 73 mit erfassten Satzständen. Eine gezielte Schema-Nachprüfung um `18:05Z`
bestätigte: Die Spalte `match_duration_minutes` existiert, ist aber in sämtlichen
Zeilen leer. Exaktes Matchende und native Teilnehmerkennungen werden in dieser
Tabelle nicht geführt. 375 Modellrevisionen gehören zu 63 Prognose-IDs; auch sie
sind keine 375 unabhängigen Testspiele. Der zusätzlich geprüfte ältere
`shadow_clv.db` enthielt genau ein Spiel mit Ergebnis und kein Kontextarchiv.

Diese begrenzte Inventur umfasst drei Datenbanken, nicht sämtliche historischen
Quellen. Sie belegt noch keinen zeitkorrekten 200-Spiel-Test. Die Datenaufbereitung
muss weitere geeignete Historien, native Zuordnungen und die damalige Verfügbarkeit
prüfen. Fehlende Nachweise dürfen weder zurückdatiert noch durch synthetische
Testfälle ersetzt werden. Rohwerte zu Quoten oder Benutzerkonten wurden für diese
Inventur nicht gelesen.

## Nachweise und offene Abnahme

### Ergänzung 8. September: tatsächlicher Offline-Tourbuild

Mit Quellstand `c8935c22af0d4a5e5e03a575be8eb1b5d3f1dc40` wurde der echte getrennte Rebuild mit `--force --no-refresh-data` in einem neuen lokalen Runtime-Verzeichnis ausgeführt. HTTP-Zugriffe waren technisch verboten; die versionierten Dateien blieben unverändert. Ausgangs-SHA-256: ATP-Matches 2026 `975150fe578c8a83f027e06de0709e126331337be51b3ed9c2d2b0ea825c8a9b`, ATP-Turniere `8ebfb9697b648217639b712dfc9acc8121d4f77bfc3cf995402c495700c1bf3e`, WTA 2026 `f6f913da3dabb54add6e9edd167a1d33d669c9ede9741e63e9069f18b3977ba`.

WTA wurde separat als Artefakt `9baf129c88fb6f5ac5b546a64f6b919d9d3a1bc124f6f2b30216a0379e3430cd` veröffentlicht, tatsächlicher Buildzeitpunkt 8. September 16:49:28 UTC, Datenabdeckung `result_date=2026-07-26`. Das ist ein echter Build alter Daten, keine aktuelle WTA-Quelle. ATP scheiterte mit `ValueError`; der anschließende gezielte Stacktrace lokalisiert den Fehler auf den Integritätscheck `serve breaks cannot exceed return games` in `tennis/serve_model.py`. Es wurde keine Prüfung gelockert oder Zahl gekappt. Die Ursachenanalyse muss zwischen Quellfehler, Aggregation und Rundung unterscheiden, bevor eine Korrektur erfolgen darf.

Der Gesamtlauf meldete korrekt `REFRESH_PARTIAL`, Exit 1, und bewies damit unabhängige WTA-Fortsetzung, aber noch keinen erfolgreichen Zwei-Tour-Build. Isolierter Zustand: `.pytest_tmp/tour-offline-realdata-20260908-01`; Controller-Harness und Diagnose unter `output/context-evaluation/`. Keine Produktivdatei oder Quelle wurde dafür verändert. Backup/Restore und echte aktuelle Tour-Aktivierung bleiben gesondert erforderlich.

### Vorherige Quellen- und Korpusnachweise

Die datierten, bereinigten Diagnoseartefakte liegen im lokalen SDD-Arbeitsbereich
`2026-09-07-kontextmodell-umsetzung`: `football-source-probe-20260907.json`,
`football-injuries-probe-20260907.json`, `espn-source-probe-20260907.json`,
`basketball-nhl-schedule-probe-20260907.json` und die zugehörigen Source-Readiness-
Berichte. `corpus-inventory-20260907.md` hält die begrenzte Bestandsprüfung mit
Prüfzeiten und Ausschlussgrenzen fest. Die owning B/C-Aufgaben übernehmen ausschließlich belegte strukturelle
Samples in ihre versionierten Testfixtures und aktualisieren diesen Bericht.

Noch offen sind die jeweiligen Normalisierer, tatsächlichen Referenz-/Merkmals-
rechnungen, empirischen Modellvergleiche und Produktionsnachweise. Ein späteres
leeres oder zeitlich ungeeignetes Trainingsset bleibt eine Datenabhängigkeit;
es darf nicht als erfolgreicher Modellbuild oder als eingerechnete Wirkung gelten.
