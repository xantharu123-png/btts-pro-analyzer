# Greece–Germany: unabhängiger Nachweis der tatsächlich gerechneten Auswahl

Prüfung am 04.10.2026 ab 09:23 Europe/Zurich. Ausschließlich vorhandene
VPS-Belege gelesen; keine API-Abfrage, kein Sportscan, keine Datenbankkopie,
keine Modelländerung und keine Änderung an Wetten oder Geldbuchungen.

## Ergebnis

Die eingefrorene Auswahl ist tatsächlich aus dem vorhandenen Tormodell
berechnet. Native API-Football-Spielnummer **1528939**, Greece **1117**,
Germany **25**, UEFA Nations League **5**, Saison **2026**, League A – 4,
Toumba Stadium, Thessaloniki, Anpfiff **04.10.2026 18:45 UTC / 20:45 Zürich**.
Ein vorhandener nativer Detailbeleg vor Modellberechnung bestätigt diese
Identität. Es wurden keine Vereins-, Jugend- oder Frauenteam-Ergebnisse in
den rekonstruierten nationalen Modellumfang aufgenommen.

Alle zehn angezeigten Ergebnisse je Seite stimmen mit vorhandenen nativen
FT-Belegen überein. Das gemeinsame Spiel vom 27.09.2026, Nummer 1528899,
war **Germany 0:1 Greece**. Greece zeigt daher korrekt 1:0/Sieg und Germany
0:1/Niederlage. Das ist kein vertauschtes Ergebnis. Alle Spiele und ihre
erforderlichen Belege liegen vor dem eingefrorenen Modellzeitpunkt.

## Exakter Inputpool und Rechnung

Aus 4.347 Referenzen des vorhandenen Fußball-Captures wurden 2.150
Base-Fixture-Belege gelesen. Nach den bestehenden Wettbewerbs-, Zeit- und
UEFA-Zugehörigkeitsfiltern ergeben sich **652 eindeutige A-Länderspiele**:
61 WM-Spiele, 209 Nations-League-Spiele, 182 Freundschaftsspiele und 200
europäische WM-Qualifikationsspiele; 54 UEFA-Mannschaftsidentitäten.
Es wurden keine widersprüchlichen nativen Revisionen in diesem Pool gefunden.

Der vollständig rekonstruierte Rohhistorien-Hash stimmt **exakt** mit dem
Owning-Cache des tatsächlich verwendeten Modells überein:

`17122df6b4d692eda23c6b1f4afc8415e4b6cb70b4a27f0e922c58b75217a41e`

Das Modell `challenge-engine:coherent-joint-calibration-v14` nutzt je Team
12 letzte A-Länderspiele und die letzten 6 davon als jüngere Form. Der
Tore-Prior ist **1,459355828220859** je Mannschaft. Die 12er-Mittel werden
mit sechs Priorbeobachtungen, die 6er-Mittel mit vier Priorbeobachtungen
geschrumpft. Der kleine geschätzte Gastgeberfaktor beträgt
**1,0559077702956587**. Die aktive Verteilung mischt 75 % des 12er-Modells
und 25 % des 6er-Modells. xG-Abdeckung ist hier **0**; diese konkrete
Rechnung verwendet Tore, nicht beobachtete xG.

| Stufe | Greece erwartete Tore | Germany erwartete Tore |
|---|---:|---:|
| 12er-Teil, vor Kalibrierung | 1,188256128348225 | 1,802353068084793 |
| 6er-Form, vor Kalibrierung | 1,302718114150043 | 1,452534373204668 |
| 75/25 aktiv, vor Kalibrierung | 1,216871624798679 | 1,714898394364761 |
| Aktiv, nach gemeinsamer Kalibrierung | 1,134402241085424 | 1,857088535178216 |

Die unverändert gespeicherten Kalibrationskurven erzeugen mit der bestehenden
gemeinsamen Ergebnisverteilung **0,7197334285999141** für Germany Unter 2,5.
Die angezeigten **72,0 %** und **1,86 erwarteten Tore** stimmen nach Rundung
exakt. Saison- und Formvarianten für diesen Markt sind **0,695072655441934**
und **0,8017818889763132**. Die gemeinsame Projektion war erfolgreich, mit
9 Iterationen, 38 Atomen und 676 Ergebniszellen. Eine bloße Poisson-Rechnung
mit der nachkalibrierten mittleren Torzahl ist nicht das verwendete Modell.

Die tatsächlichen Germany-Tore aus den letzten 12 Modellspielen sind
`2, 0, 1, 1, 2, 7, 2, 4, 2, 4, 6, 2` (33 Tore).
Greece ließ in seinen letzten 12 Spielen
`2, 0, 1, 1, 2, 0, 1, 0, 2, 3, 3, 3` zu (18 Gegentore).
Die 5-Spiele-Ansicht blendet unter anderem Germanys sechstes Spiel,
das 7:1 gegen Curaçao, aus; die Modellrechnung enthält es weiterhin.

## Was diese Auswahl begründet – und was nicht

Germany blieb in seinen letzten fünf Spielen jeweils unter drei Toren;
Greece ließ in den letzten fünf jeweils höchstens zwei Gegentore zu.
Über die letzten zehn gilt diese Bedingung für Germany in **7/10** und
für Griechenlands Gegner in **9/10** Spielen. Das sind beobachtete
Marktbedingungen, **keine zweite Modellwahrscheinlichkeit**. Das gemeinsame
direkte Duell ist in beiden Mannschaftslisten enthalten; die beiden
Häufigkeiten sind also nicht vollständig unabhängige Belege.

Eine Sieg-/Remis-/Niederlagenbilanz allein beschreibt einen Teamtor-Untermarkt
schlecht. Die ausgewählte Torbedingung und Gegenbeispiele sind hierfür die
passenderen kurzen Kundeninformationen. Die neue Darstellung soll weder
die Prognose nachträglich ändern noch aus 5/5 einen sicheren Tipp machen.

Der gespeicherte letzte Preis **1,33** stammt tatsächlich aus sieben
Buchmacherpunkten; alle wurden am 04.10.2026 00:28:19 UTC beobachtet.
Der spätere Abruf um 01:56 erneuert nicht diesen Beobachtungszeitpunkt.
Die Darstellung als **letzte** Quote, nicht als frisch bestätigtes Angebot,
ist daher korrekt. Das Modell behauptet damit keinen nachgewiesenen Value.

Offen bleiben explizite Gegnerstärke-Anpassung und empirisch bestätigte
Verletzungs-/Müdigkeits-/Wettereffekte. Das nationale Modell mittelt
Tor-/Gegentorleistungen mit einem Pool-Prior; Gegnerstärke wird nicht
individuell als eigener Eingang gewichtet. Wetter liegt als echter Beleg vor,
ist hier aber nur Veto-Kontext; Ausfälle werden nicht abgedeckt, Startelf ist
noch nicht bestätigt. Keine dieser Informationen verändert in diesem Beleg
die ausgewiesene Wahrscheinlichkeit.

Die gemeinsame Kalibrierung und der exakte Replay beweisen technische und
mathematische Nachvollziehbarkeit, **nicht** eine profitable Auswahlregel.
Eine Formänderung von mindestens zwei Prozentpunkten ist eine Produktregel
für Sichtbarkeit, keine empirisch bestätigte Qualitätssteigerung.

## Reproduktion und unabhängige Prüfung

Der schlanke, netzgesperrte Reproduktionscode liegt lokal in
`output/playwright/greece-germany-readonly-replay-20261004.py`. Er liest
`wettfinder_latest.json`, die bezeichneten vorhandenen Base-Fixture-Belege
und den zugehörigen Kalibrationscache. SQLite wird mit `mode=ro` und
`query_only=ON` geöffnet; Netzwerkzugriffe sind explizit gesperrt. Ein anderer
Inputpool-Hash oder eine vom gespeicherten Modell abweichende Rechnung
bricht ab, statt Daten nachzuladen. Ausgabe enthält nur kompakte Kennzahlen.

Nachweispunkte im Quellcode: `challenge_engine.py` Funktionen
`_senior_national_fixture_model`, `_team_observations`, `_hybrid_strength` und
`fixture_market_probabilities`; `challenge_15k.py` Funktionen
`_senior_national_result`, `_bounded_completed_history`, `completed_history`;
`football_customer_facts.py` Funktionen `build_football_recent_results` und
`validated_football_recent_results`.

Unabhängige lokale Prüfungen des Darstellungs-Patches: **151 Tests bestanden**;
zusätzlich **56** Markt-/Seiten-Zählungen unabhängig gegen die bestehenden
Abrechnungsbedingungen nachgerechnet. Unabhängige Historiengrenzen-Prüfung:
**28 Tests bestanden**. Diese Zahlen sind Teilmengen, kein Vollsuite-Nachweis.
