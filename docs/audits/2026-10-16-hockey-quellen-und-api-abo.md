# Hockey-Quellen: Jahresabo und fehlende Personaldaten

## Verifizierter Anbieterumfang

API-Hockey v1.0.1 dokumentiert diese 15 GET-Pfade:

`/timezone`, `/seasons`, `/countries`, `/leagues`, `/teams`,
`/teams/statistics`, `/standings`, `/standings/stages`, `/standings/groups`,
`/games`, `/games/h2h`, `/games/events`, `/odds`, `/odds/bets`, `/odds/bookmakers`.

NHL, Schweizer National League, SHL, Liiga und DEL sind im öffentlichen Katalog
aufgeführt. Bezahlpläne öffnen vorhandene Endpunkte/Wettbewerbe, erzeugen jedoch
keine zusätzlichen Verletzungs- oder Spieler-Endpunkte. Nutzer plant zwölf
Monate API-Zugang und bestätigt, dass das Abo **noch nicht aktiviert** ist.
Empfehlung: Jahresbindung zunächst abwarten, weil damit die fehlenden
Personalendpunkte nicht nachgewiesen werden. Die begrenzte Quellenkorrektur
braucht diese Aktivierung nicht. Keine Bestellung oder Änderung am
Anbieter-Konto durch diese Arbeit.

| Benötigte Information | Was dieser Anschluss tatsächlich liefert |
| --- | --- |
| Gegnerstärke | Historische Team-Ergebnisse, Tore, Tabellen |
| Form | Team-Ergebnisse und Aggregate; zeitkorrektes eigenes Modell nötig |
| Spielplanbelastung | Daten/Startzeiten früherer Spiele; keine gemessene körperliche Müdigkeit |
| Torhüterqualität/Starts | Kein dokumentierter individueller Statistik-/Starter-Endpunkt |
| Akute Ausfälle | Kein dokumentierter Verletzungs-Endpunkt |
| Individuelle Einsatzbelastung | Keine dokumentierten Spieler-Eiszeiten |

`games/events` enthält Spielernamen und Assists in Tor-/Strafereignissen. Das
belegt weder stabile Spieler-IDs noch vollständige Kader, Torhüterstarts,
Verletzungen oder Time-on-Ice. Ausbleibende Torereignisse sind keine Ausfallmeldung.

Primärquellen: [API-Hockey Dokumentation](https://api-sports.io/documentation/hockey/v1),
[Coverage und Pläne](https://api-sports.io/sports/hockey),
[offizielles Endpunktdiagramm](https://api-sports.io/public/img/architectures/archi-hockey.webp).

## Begrenzter Alternativenvergleich, keine Kaufempfehlung

| Anbieter | Belegt | Nicht als vollständig belegt behandeln |
| --- | --- | --- |
| Sportradar Global Ice Hockey | Spieler, Lineups und je Abdeckung Goalie-Minuten/Saves/Gegentore | Match-/Saisonabdeckung je Liga prüfen; Global-FAQ unterscheidet `starter` derzeit nicht von `played`; kein eigener Global-Injury-Feed dokumentiert |
| Sportradar NHL / SportsDataIO NHL | Separate NHL-Injury-/Goalie-Angebote dokumentiert | Kein Nachweis derselben Tiefe für die vier Europaligen |
| Goalserve | Coverage für NHL, SHL und Liiga mit Live Stats/Lineups; NHL-Goalie-Sample | DEL/Schweiz in Coverage ohne diese Statistik-/Lineup-Tiefe; NHL-Injury-Sample beweist keine Europa-Abdeckung |

Quellen:

- [Sportradar Global Übersicht](https://developer.sportradar.com/ice-hockey/reference/global-ice-hockey-overview)
- [Global Statistikfelder](https://developer.sportradar.com/ice-hockey/reference/global-ice-hockey-statistics-summary)
- [Global FAQ einschließlich Starter-Semantik](https://developer.sportradar.com/ice-hockey/reference/global-ice-hockey-faqs)
- [Sportradar NHL Übersicht](https://developer.sportradar.com/ice-hockey/reference/nhl-overview)
- [Sportradar Account/Trial](https://developer.sportradar.com/getting-started/docs/your-account)
- [Goalserve Coverage](https://www.goalserve.com/en/sport-data-feeds/ice-hockey-api/coverage)
- [Goalserve NHL-Goalie-Sample](https://www.goalserve.com/en/sport-data-feeds/ice-hockey-api/sample/18)
- [Goalserve Injury-Sample](https://www.goalserve.com/en/sport-data-feeds/ice-hockey-api/sample/71)
- [SportsDataIO NHL Endpunkte](https://sportsdata.io/developers/api-documentation/nhl)

Keiner dieser drei geprüften Anbieter ist dadurch als vollständige Lösung für
alle fünf Ligen mit bestätigten Vorab-Startern und Verletzungen verifiziert.
Ein möglicher kostenloser Trial ist erst durch tatsächliche Liga-/Spielantworten
zu prüfen; kein Konto/Trial beantragt, kein Anbieter kontaktiert und kein Vertrag
geschlossen. Keine Schätzung von Gebühren oder Kaufempfehlung aus Marketingtabellen.

## Software und externe Abhängigkeit getrennt

Die bereits autorisierte Quellenintegration kann unabhängig von Personaldaten
auf fünf Ligen und tatsächlich benötigte native Liga/Saison-Paare begrenzt werden.
Quellenfehler müssen im internen Quellenbericht sichtbar bleiben und dürfen nicht
mit `operational_error_count=0` als fehlerfreie Datendeckung gelten.

Das vervollständigt nicht die numerischen Torhüter-/Ausfall-/Müdigkeitseffekte.
Die alte historische Stichprobe von62/100 bleibt ein Grundmodelltest; ihre
Ergebnisse dürfen nicht als Validierung neuer Personaleffekte wiederverwendet
werden. Der volle C3-Trainings-/Outcome-/Replay-/Evaluationspfad sowie reale
geeignete Beobachtungen bleiben getrennte Aufgaben.

Vor einer Jahresbindung insbesondere schriftlich oder per zulässigem Trial
prüfen: fünf aktuelle Ligen, konkrete vergangene Goalie-Einsatzzeilen, stabile
Spieleridentitäten, dokumentierte Vorab-Starter-/Ausfallzeitpunkte und tatsächliche
Rechte für den gewünschten persönlichen/öffentlichen Betrieb. Ein API-Key allein
beweist diese Informationen nicht.

## Erneuter Vergleich auf ausdrücklichen Nutzerauftrag

Am 16.10.2026 aktuelle Primärdokumentation erneut geprüft. Keine Registrierung,
Kontaktaufnahme, Zahlung oder automatische Probephase gestartet.

| Kandidat | Tatsächlich dokumentierter Vorteil | Einschränkung / Preis |
| --- | --- | --- |
| **SportsDataIO NHL** | Verletzungen, individuelle Einsatzminuten, Goalie-Statistik und eigener Starttorhüter mit `Confirmed`-Kennzeichen | NHL; keine gleichwertige Abdeckung aller vier Europaligen belegt. Passender aktueller Livepreis nicht öffentlich verifiziert. |
| **BALLDONTLIE NHL GOAT** | Aktuelle Verletzungen, Boxscore-Spielzeit, Goalie-Statistiken | NHL, kein bestätigter Vorab-Starter dokumentiert. USD39,99/Monat oder383,90/Jahr; historische Vollständigkeit/Aktualität noch nicht praktisch geprüft. |
| **Enetpulse Premium** | Spieler-Eiszeiten und Goalie-Statistik für NHL, SHL, Liiga und DEL im Hockey-PDF aufgeführt | Schweizer National League nur LiveExtra, nicht Premium. Verletzungen und bestätigte Vorab-Starter nicht nachgewiesen; individuelles Angebot. |

**Entscheidung:** Kein All-5-Jahresabo als vermeintliche Komplettlösung empfehlen.
SportsDataIO ist der fachlich klarste NHL-Kandidat, BALLDONTLIE ein konkreter
günstiger bepreister NHL-Kandidat ohne bestätigten Starterfeed. Enetpulse ist
für vier tiefer abgedeckte Ligen interessant, löst die Schweizer Lücke aber nicht.
Sportradar und Goalserve bleiben Kandidaten mit den oben festgehaltenen Lücken.

Kostenlose NHL-Teams/Spieler bei BALLDONTLIE enthalten **keine** Verletzungen.
Der48h-GOAT-Test verlangt ein Zahlungsmittel und wandelt sich anschließend in
ein bezahltes Abo; daher weder kostenloses Dauermodell noch freigegebene Buchung.
Eine aktuelle Verletzungsliste allein liefert auch keine nachweislich vor einem
historischen Testspiel bekannte Verletzung. Dafür braucht es datierte Archivstände.

SportsDataIO trennt erwartete und bestätigte Starter ausdrücklich. Gemessene
Einsatzminuten sind nutzbar, beweisen aber keine medizinisch gemessene Ermüdung.
Der veröffentlichte Entwickler-Testumfang ist widersprüchlich beschrieben
(allgemeiner verfremdeter Test vs UEFA-Hinweis auf NHL-Endpunktseiten); kein
echter aktueller NHL-Testzugang wurde deshalb als verifiziert angenommen.
Discovery-Lab-Archivangebote nicht als aktuellen Live-/Veröffentlichungstarif
ausgeben.

Neue direkt geprüfte Quellen:

- [SportsDataIO NHL-Workflow](https://sportsdata.io/developers/workflow-guide/nhl)
- [SportsDataIO Goaltender.Confirmed und Spielzeitfelder](https://sportsdata.io/developers/data-dictionary/nhl)
- [BALLDONTLIE NHL: Tarife, Verletzungen und Statistikfelder](https://nhl.balldontlie.io/)
- [Enetpulse Hockey-PDF: Player Stats S.5, LiveExtra S.8, Premium S.9](https://enetpulse.com/wp-content/uploads/Ice-Hockey-Packages.pdf)

BetsAPI ist kein belegter Ersatz für diesen Kontextumfang: sein dokumentierter
Lineup-Endpunkt gilt für Fußball, nicht Hockey. Sportmonks dokumentiert keinen
Hockey-Anschluss. Keine günstige Liga-Ergebnisliste mit feldvollständiger
Personaldatenabdeckung gleichsetzen.

- [BetsAPI Lineup-Dokumentation](https://betsapi.com/docs/events/lineup.html)
- [Sportmonks Produktübersicht](https://www.sportmonks.com/)

Auch ein scheinbar kostenloser NHL-Verletzungsersatz wurde geprüft:
[Big Balls Sports Data](https://bigballsdata.com/injuries-api) wirbt im Kopf
mit Live-NBA/NHL, erklärt in der eigenen FAQ aber ausdrücklich, dass deren
Zulieferung pausiert und diese Verletzungsstände alt sind. Deshalb kein Ersatz
für aktuelle Ausfälle und keine Registrierung ausgelöst. Ein öffentliches
`supported=true` oder die Bezeichnung „Live“ würde hier nicht als aktuelle
Spielerinformation genügen. Anbietertext und tatsächlicher Datenzeitpunkt
müssen zusammen geprüft werden.
