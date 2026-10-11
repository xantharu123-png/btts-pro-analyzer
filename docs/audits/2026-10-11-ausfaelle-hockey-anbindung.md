# Verletzungs-/Belastungsprüfung und zusätzliche Hockeyligen

11.10.2026. Ausgang lokal/GitHub/VPS `4bd5da446c8e19ebc9151e9df7b2cf68fef7134a`.
Keine neue Sicherung, kein zusätzlicher Sport-/Provider-Scan, keine Bereinigung
oder Änderung gespeicherter Ergebnisse/Prognosen/Geldbuchungen.

## Reale Fußballreparatur

Der Kontextbestand enthält historische Spieler der gesamten geladenen Liga.
`football_features` nahm deren unbekannten aktuellen Kaderstatus in die
Erwartung des Zielkaders auf. Dadurch verschwand ein belegter Ausfall-Eingang
des Zielspiels, sobald eine vollständig gültige fremde Teamappearance hinzukam.
Die reine CPU-Reproduktion ergab für denselben ausgefallenen Spieler vorher
`-0.078125`, nach Hinzufügen fremder Teams `missing/null`.

Jetzt werden weiterhin sämtliche ausgewählten Quellen vollständig geprüft;
erst anschließend werden die Appearance-Eingänge für die Zielkadererwartung
auf die zwei nativen Zielteam-IDs begrenzt. Fremde fehlerhafte Quellen werden
nicht durch den Filter verborgen. Fehlende Daten eigener Zielspieler bleiben
fehlend; aus einer Ausfallliste entsteht weiterhin kein erfundener Gesundstatus.
Eigene Regression rot/grün: 22 bestanden/ein reproduzierter Fehler, danach
23 bestanden. Dreizehn ganze Nachbarmodule: 490 bestanden, Exit 0. Unabhängiger
Review bestätigte Quellen-/Transfer-/Kaderbindung ohne neuen Befund.

## Hockey: echte zusätzliche Quelle statt NHL-Umbenennung

`scanners/api_hockey.py` besitzt einen eigenen nativen Schedule-/Historien-
Vertrag. `scanners/hockey_scanner.py` verbindet ihn mit dem unveränderten
kostenlosen NHL-Feed; automatischer Tageslauf und manuelle Suche benutzen
denselben Einstieg. Keine zusätzliche Zeitplanung.

Zwanzig ausdrücklich konfigurierte Name/Land-Kandidaten insgesamt:
National League, Swiss League, NHL, AHL, ECHL, SHL, Hockey Allsvenskan, Liiga,
Mestis, DEL, DEL 2, tschechische und slowakische Extraliga, ICE Hockey League,
Metal Ligaen, Fjordkraft-ligaen, Ligue Magnus, Elite League, KHL und VHL.
Das ist keine objektive Weltrangliste. Die beiden Schweizer Ligen haben zuerst
Priorität. Native IDs/Saisons werden aus dem echten Kontokatalog aufgelöst,
nicht geraten; NHL wird dort nicht nochmals geladen.

Die [offizielle Anbieterabdeckung](https://api-sports.io/sports/hockey) und
[native Dokumentation](https://api-sports.io/documentation/hockey/v1) wurden
geprüft. Getrennte Finalstatus `FT/AOT/AP` und die drei Periodenscores bestimmen
60-Minuten-Tore und Endergebnis; der NHL-Abzug eines Siegtores wird nicht auf
andere Ligen übertragen. Ligamodell, Saison, Quellen- und Team-IDs bleiben
getrennt, mit eigener Modellversion. Weder NHL-Kontexteffekte noch eine
Kalibrierungsfreigabe werden übertragen.

Ergebnisdaten werden aus bestehenden beobachteten Cache-Revisionen gelesen,
mit Hash-, Start-, Event-, Team- und Quellenprüfung. Keine Ergebnis-API beim
Abrechnen. Ein neuerer fehlgeschlagener/pending Ligaabruf blockiert die Verwendung
des alten Finalergebnisses. Erkennbare native Rücknahmen werden dauerhaft als
Revision gespeichert, nicht nach einer späteren leeren Antwort zurückgeholt.
Die bisherigen finanziellen Settlement-Stage-Grenzen bleiben unverändert;
Forschungsprognosen werden nicht stillschweigend zu buchbaren Tickets.

Preise sind an native Event-/Team-IDs und den exakten Start gebunden. Alte NHL-
und Basketball-Cache-Identitäten bleiben bytegleich. Der bestehende Preisabruf
bleibt bei acht Events je Sport und 35 Sekunden; kein Versprechen vollständiger
Quoten für zwanzig Ligen. Der Anbieter hat nicht für jede dieser Ligen Quoten.

Eine Tages-Schedule-Abfrage liefert alle angebotenen Ligen zusammen. Höchstens
acht saisonweise Historienabfragen pro Lauf; faire Reihenfolge verhindert
dauerhafte Verdrängung späterer Ligen. Kein 365-facher Tagesabruf pro Liga.
Gemeinsamer bestehender Budget-Governor, kleiner begrenzter Antwortcache
(höchstens 16 Einträge, je höchstens 2 MB), echte erste Empfangszeiten und
as-of-Zugriff. Die Swiss-IDs `8001/8002` in Tests sind synthetisch und kein
Nachweis tatsächlicher Kontofreischaltung.

Der reale Tagesablauf benutzt für Hockey die Uhr nach dem Schedule-Empfang
und nach dem Historienabruf; ein inzwischen gestartetes Spiel wird nicht neu
als Pre-Match prognostiziert. Der Historienstichtag bleibt konservativ vor
dem Abruf: neu empfangene Ergebnisse werden nicht rückdatiert. Der tatsächliche
RisikoBet-Abschluss und der Wettfinder-Veröffentlichungsstand folgen den
Modellzeiten. Rückwärtslaufende Abschlusszeiten werden vor Speicherung
abgelehnt. Ein Anbieterausfall verwirft keine gültigen NHL-Daten; reparierte
Quellen behalten keine alten Wrapperfehler.
Lange Ladezeiten dürfen auch keinen alten Fußball-Preisstatus erhalten:
bereits gestartete Spiele fallen aus dem Katalog, vorhandene exakte Quotes
werden zum wirklichen Publikationszeitpunkt nur neu bewertet. Veraltete
Strict-/Challenge-Overlays fallen weg, die weiterhin gültige Modellprognose
bleibt sichtbar. Keine neue Providerabfrage oder Erneuerung von Quote-,
Empfangs-, Modell- oder Trainingszeiten. Die ursprünglichen Wahrscheinlichkeiten
und Reihenfolge bleiben unverändert.
Dasselbe gilt für die 24h-Anzeigegrenze einer E-Sport-Beobachtungsquote:
Beobachtungen werden dadurch niemals zu ausführbaren Strict-Tipps. Ursprüngliche
Preisabruf-/Statuszähler beschreiben den ursprünglichen Abruf; nur veröffentlichte
Modell-/Empfehlungszahlen werden nach dem finalen Zeitfilter aktualisiert.

## Was damit ausdrücklich nicht erledigt ist

Es gibt weiterhin kein aktiv abgenommenes Verletzungs-/Wetter-/Müdigkeits-
Effektartefakt. Acht vollständig gebundene Fußballspiele und der bislang
erfasste Wetterbestand reichen nicht für den freigegebenen unabhängigen
200-Testspiel-Nachweis zusätzlich zu Training/Abstimmung.

Tennis: zwölf physisch/hash-/quellengeprüfte Produktionsbelege, darunter sechs
jüngste ATP/WTA-Matches, enthalten echte Sätze und Games. Tatsächlicher Anfang,
tatsächliches Ende und Minuten sind dort null; die jüngsten Historien besitzen
nur angesetzte und abgeschlossene, keine laufenden Beobachtungen. Empfangszeit
ist keine körperliche Erholung. Der erhaltene echte ESPN-Rohbeleg enthält
ebenfalls keine entsprechende Dauer. Kein nachgewiesener Satzparserfehler.
Für Tennis fehlt außerdem eine belegte akute Verletzungsquelle. Aufgabe ist
keine Diagnose. Alte Winner-Offsets passen nicht zum aktuellen Point-Modell.

Der Joint-Worker beendet sich ohne vorhandenen Fit vor der Merkmalsberechnung.
Fehlende Feature-Zähler bedeuten dort **nicht gemessene Nullabdeckung**.
Keine neuen pauschalen Prozentabschläge, keine aufgeweichte Abnahme.

## QA und nächster Produktionsnachweis

- Erste gemeinsame Integrationsrunde: 470 bestanden (acht komplette Module).
- Weitere Quellen-/Preis-/Roster-/UI-Runde: 169 bestanden.
- Separate native Quellen-/Historien-/Preisrunde nach Rücknahmefix: 222 bestanden.
- Native Preis-/Publikationsrunde: 176 bestanden, alte Byte-Pins erhalten.
- Die Runden überschneiden sich; die Zahlen nicht zu einer Vollsuite addieren.
- Finale gemeinsame Abschlussrunde in 26 ganzen Modulen: **1.088 bestanden,
  ein vorhandener Skip**, 68,12 s, Exit 0. JUnit:
  `C:/Projekt/BetBoy/output/hockey-context-20261011/release-05.xml`.
  Enthält echten vollständigen Tageslauf/Kundenleser/Prognosenachweis sowie
  drei ganze Owner-Gegenfälle: frische Kontrolle, Anpfiff während Ladezeit,
  Quote während Ladezeit veraltet; zusätzlich zwei ganze E-Sport-Quote-
  Ownerfälle an der 24h-Anzeigegrenze. Keine neue Vollsuite behauptet.
- Schlussprüfung nach der letzten Rücknahme-Korrektur abgeschlossen;
  drei unabhängige Reviewpfade ohne verbleibenden Befund. Eine neue Vollsuite
  ist damit nicht behauptet.
- Tatsächliche Katalogfreischaltung/Spiel-/Historienabdeckung erst beim nächsten
  regulären Tageslauf prüfen. Kein eigener zusätzlicher API-Scan durchgeführt.
- Cricket bleibt unverändert.

## Veröffentlichung, 11.10.2026 14:23 CEST

Codecommit `090cf93a03cdf329774e6caac2458cd69b1d28f9` auf GitHub-main gepusht,
auf dem VPS per geprüftem Fast-forward veröffentlicht. Lokaler/GitHub-/VPS-
Codehash identisch, getrackter Stand sauber. Offlineimports erfolgreich;
App/Caddy und sieben reguläre Timer aktiv, interner und öffentlicher Healthcheck
`ok`. Nur die App im natürlichen Leerlauf nach dem regulären Shadowjob neu
gestartet; kein Sportjob/Timer gestoppt, kein Zusatzscan/Backup/Datenumbau.
Vorprüfung bei zu kurzem Timerfenster zunächst ohne Mutation abgebrochen.
Der danach korrigierte und unabhängig geprüfte Helfer begrenzt sämtliche
Mutation-/Nachprüfungs- und Fehler-Recoveryschritte zusammen auf höchstens
336 s innerhalb eines geprüften 360-s-Fensters; kein alter Code-/Datenrollback
damit behauptet.

Beide veröffentlichten Datenartefakte bytegleich vor/nach dem Deploy:
Wettfinder SHA256 `a51c9d865ab14db2d7d17971e469cbb029045a7107dd7417f2ff9da17af4298e`,
RisikoBet SHA256 `acf24df6d14786a744b8fdf30a690bada1b34f84d54e32eb1e3915cdc3350ede`.
Der nächste reguläre Hockeylauf am 12.10.03:35 CEST ist der erste reale
Account-/Katalog-/Abdeckungsnachweis. Keine synthetischen Tests als Livebeleg.

Separater alter Dienststatus 14:23:21 CEST: Tageslauf noch `timeout`/Status 15,
Shadow-Abschluss 14:22:42 Status 1; Vorläufe hatten fehlende frische Bet365-
Preise und zwei alte ungültige Belege. Tennis letzter regulärer Abschluss
00:32:29 erfolgreich/Status 0. Diese Status wurden nicht durch Neustart oder
Löschen überschrieben. Numerische Kontexteffektabnahme und bessere Wettqualität
bleiben trotz des erfolgreichen Code-Deploys offen.
