# Auswärtssiege und Gäste-Tore im Fußballarchiv

**Ergebnis:** Das Modell erwartete rund 53 Auswärtssiege, tatsächlich waren es 45. Die 123 Fälle reichen nicht aus, um einen systematischen Fehler festzustellen oder eine gezielte Korrektur freizugeben. Der Soll-Ist-Abstand war in der jüngeren Teilperiode größer. „Bester je Wettart“ ist bereits produktiv und ändert den Haupttipp nicht.

**Zeitraum:** 08.–27.11.2026, abgeschlossene Schweizer Spieltage. Produktionsbelege gelesen am 28.11. um 12:37 Uhr, VPS `2bb67ff`. Ausschließlich die aktive Fußball-Prognoseversion `challenge-engine:legacy-form-strength-joint-calibration-v1` und Modellumfang `same_competition`; keine Vermischung mit Nationalteam-/Transfermodellen. Je Spiel und Markt zählt der früheste gültige, vor Anpfiff gespeicherte Beleg. Die Prognosen stammen aus Evidenzkandidaten, nicht aus der Wettausführung oder aus der Grundgesamtheit aller Spiele.

## Auswärtssieg

| Zeitraum | Spiele | Gast gewann | Summe der Modellchancen | Ist minus Modell |
|---|---:|---:|---:|---:|
| 08.–20.11. | 67 | 26 (38,8 %) | 27,9 (41,6 %) | -2,8 Pp. |
| 21.–27.11. | 56 | 19 (33,9 %) | 24,8 (44,3 %) | -10,4 Pp. |
| Gesamt | 123 | 45 (36,6 %) | 52,7 (42,8 %) | -6,3 Pp. |

Für den Gesamtabstand ergibt ein nach Zürcher Spieltag gruppierter Bootstrap (15 Spieltage, 20.000 Wiederholungen, 95 %) **−15,1 bis +2,7 Prozentpunkte**. Der jüngere Teil wurde separat ausgewiesen, nicht zum nachträglichen Einstellen des Modells genutzt. Der Archivtest ist beschreibend, nicht als Freigabe einer Korrektur angelegt.

## Gäste-Tore

62 Spiele aus 18 Ligen hatten alle drei erforderlichen Torgrenzen aus derselben unveränderten Vorab-Prognose. Die vier Klassen sind exakt aus diesen Grenzen gebildet, nicht aus einem Tor-Mittelwert geschätzt.

| Tore des Gasts | Tatsächlich | Erwartet | 95-%-Intervall Ist minus Modell |
|---|---:|---:|---:|
| 0 | 18 (29,0 %) | 16,3 (26,3 %) | -15,4 bis 11,0 Pp. |
| 1 | 25 (40,3 %) | 20,4 (32,9 %) | -0,1 bis 22,4 Pp. |
| 2 | 12 (19,4 %) | 14,1 (22,7 %) | -12,0 bis 6,9 Pp. |
| 3+ | 7 (11,3 %) | 11,2 (18,1 %) | -12,3 bis 5,6 Pp. |

Die 62 Spiele hatten häufiger exakt ein und seltener drei oder mehr Gästetore als erwartet. Der Spieltags-Bootstrap gruppiert die 62 Spiele in elf Spieltage; jedes Intervall umfasst null. In größeren, je Torlinie unterschiedlichen Stichproben: 0 Tore 42/133 statt 35,3; höchstens 1 Tor 101/163 statt 101,0; höchstens 2 Tore 174/199 statt 168,0. Diese drei Mengen dürfen nicht zu einer gemeinsamen Verteilung verrechnet werden.

## Ist die Formmischung die Ursache?

Für 52 Spiele am 27.11. waren beide 1X2-Varianten gespeichert, für 34 davon ein bestätigter Endstand. In genau diesen 34 Spielen gewann der Gast achtmal. Prognosesumme mit Form: 11,07; ohne Form: 10,52. Der Auswärtssieg-Brierfehler lag mit Form bei 0,22495, ohne bei 0,22387 (kleiner ist besser). Das ist ein einzelner Spieltag und ein kleiner Unterschied. Auch ohne Form erwartete das Modell mehr Auswärtssiege, als tatsächlich eintrafen. Damit ist die Formmischung nicht als alleinige Ursache belegt.

## Ligaübersicht

35 Ligen mit 1–22 archivierten Auswärtssieg-Prognosen. Kleinste Gruppen sind reine Bestandsangaben. Auffällig ist die schwedische Allsvenskan mit 0 statt 3,08 erwarteten Auswärtssiegen in sechs Spielen; die größte Gruppe, Eerste Divisie, lag mit 7 statt 7,74 nahe an der Prognose. Keine der Gruppen rechtfertigt für sich eine Ligaregel.

| Liga | Auswärtssieg: Spiele | Auswärtssiege tatsächlich | Auswärtssiege erwartet | Spiele mit vollständiger Gäste-Torverteilung |
|---|---:|---:|---:|---:|
| Belgium / Challenger Pro League | 2 | 1 | 0,88 | 0 |
| Brazil / Serie A | 3 | 2 | 1,56 | 5 |
| Bulgaria / First League | 1 | 0 | 0,43 | 0 |
| Chile / Primera Division | 1 | 0 | 0,39 | 0 |
| Colombia / Primera A | 4 | 1 | 1,15 | 0 |
| Cyprus / 1. Division | 3 | 2 | 1,43 | 5 |
| Czech Republic / Czech Liga | 4 | 2 | 1,79 | 0 |
| Denmark / Superliga | 1 | 1 | 0,40 | 1 |
| Ecuador / Liga Pro | 4 | 2 | 1,20 | 0 |
| England / Championship | 8 | 4 | 3,16 | 0 |
| England / League Two | 3 | 1 | 1,33 | 0 |
| England / Premier League | 2 | 1 | 0,98 | 0 |
| Finland / Veikkausliiga | 1 | 1 | 0,38 | 0 |
| France / Ligue 2 | 3 | 0 | 1,32 | 0 |
| Germany / 3. Liga | 1 | 1 | 0,58 | 0 |
| Germany / Bundesliga | 2 | 1 | 0,80 | 0 |
| Greece / Super League 1 | 1 | 0 | 0,40 | 1 |
| Indonesia / Liga 1 | 2 | 0 | 1,00 | 7 |
| Italy / Serie A | 8 | 2 | 3,91 | 3 |
| Italy / Serie B | 3 | 1 | 0,80 | 3 |
| Mexico / Liga MX | 3 | 1 | 1,32 | 0 |
| Netherlands / Eerste Divisie | 22 | 7 | 7,74 | 0 |
| Netherlands / Eredivisie | 1 | 0 | 0,51 | 1 |
| Norway / 1. Division | 4 | 1 | 1,86 | 6 |
| Norway / Eliteserien | 5 | 1 | 2,60 | 6 |
| Portugal / Primeira Liga | 1 | 1 | 0,67 | 1 |
| Romania / Liga I | 1 | 1 | 0,50 | 1 |
| Serbia / Super Liga | 2 | 2 | 1,14 | 1 |
| Slovakia / Super Liga | 1 | 1 | 0,56 | 2 |
| Spain / La Liga | 0 | – | – | 1 |
| Spain / Segunda División | 10 | 2 | 3,61 | 0 |
| Sweden / Allsvenskan | 6 | 0 | 3,08 | 6 |
| Switzerland / Super League | 2 | 0 | 0,99 | 1 |
| Turkey / 1. Lig | 4 | 2 | 1,95 | 11 |
| Turkey / Super Lig | 2 | 2 | 1,10 | 0 |
| Ukraine / Premier League | 2 | 1 | 1,15 | 0 |

## Quellen und Entscheidung

- `forecast_evidence.db`: validierte unveränderliche Vorabzeile und kausale Zeitstempel. Markt-Resultate über native Spiel-ID, Auswahl, 90-Minuten-FT-Regel und unveränderten Anstoß gebunden. `context_models.db`: geprüftes FT mit Liga, Teamrollen, Anstoß und Endstand; mit gespeicherten Marktresultaten abgeglichen. Verlegungen und uneindeutige Fälle nicht gewertet.
- Gäste-Torverteilung: exakt 0, 1, 2 und 3+ aus den kumulativen Unter-Linien für 0,5/1,5/2,5 Tore oder dem Komplement einer passenden Über-Linie. Gruppiert über dieselbe Modellrevision, Quellenzeit und Projektionsentscheidung; keine Mischung von Spielständen oder Modellständen. Alle 62 Fälle erhielten eine Liga-ID.
- `football_form_comparison.db`: separates gepaartes Register vor Marktauswahl. Die noch nicht abgerechneten Fälle bleiben offen. Der restliche Archivtest ist durch die damals erfasste Auswahl beschränkt; er misst weder alle Spiele noch die Rendite.
- Ansicht: App- und Git-Beleg bestätigen, dass PR #167 (Release `7940bbd`) im laufenden Stand enthalten ist. Je 108 gezielte Tests unter `floor` und `gate` bestanden. Beide Produktions-Healthchecks waren `ok`. Kein neuer Softwarestand, Neustart, Backup oder Sportscan.
- Entscheidung: keine Formel, Gewichtung oder Sperre aus diesen Stichproben ändern. Dieselben Messgrößen auf neuen regulären, abgeschlossenen Spieltagen weiter vergleichen. Nur bei wiederkehrendem Muster ein gezieltes Gegenmodell auf getrennten Spieltagen testen.
