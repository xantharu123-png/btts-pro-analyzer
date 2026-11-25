# Handball-Europa: Modelltest und Kaufentscheidung

Stand: 25.11.2026. Scope: nur fünf nationale Herrenligen, reguläre Spielzeit,
1X2. Auswahl nach der jüngsten veröffentlichten
[EHF-Verbandswertung für die Champions-League-Plätze 2027/28](https://ehfcl.eurohandball.com/media/2zgeniux/ehf_cc_men_placedistribution_final_2027_28.pdf)
(Klubergebnisse 2023/24–2025/26), nicht nach Gewinnquote oder Ligatiefe. Die
vorige Platzvergabe (2026/27) hatte Polen vor Ungarn. Keine Pokale/Europapokal-
spiele in der jeweiligen Ligahistorie.

## Historische Ergebnisse, ohne Anbieterabo

Reguläre Saison 2024/25, 1.150 Endstände. Jede Heim-/Auswärtspaarung genau
einmal. Das unveränderte `handball_pilot_model.predict_1x2` erhält je Spiel nur
Endstände derselben Liga von Tagen **vor** dem Anwurf, keine Ergebnisse
vom selben Tag, keine Preise, keine anderen Ligen. Erst bei mindestens 40
verbundenen Ligaspielen und acht Spielen je Team entsteht eine Prognose.
Bewertet wurden 834 solcher Prognosen. Vergleich auf denselben Spielen mit
den bis zum Vortag beobachteten Heim-/Remis-/Auswärtshäufigkeiten derselben Liga.

| Liga / Quelle | Endstände / Prognosen | Brier Modell / Basis (kleiner besser) | Basis minus Modell, 95%-Intervall | Remis Ist / Modell |
|---|---:|---:|---:|---:|
| [HBL](https://www.sportal.de/handball/bundesliga/spielplan/spielplan-chronologisch-saison-2024-2025) | 306 / 232 | 0,396 / 0,554 | +0,158 [0,118; 0,202] | 7,8 % / 6,8 % |
| [Starligue](https://www.lnh.fr/matchs/calendrier) | 240 / 176 | 0,420 / 0,563 | +0,143 [0,095; 0,191] | 7,4 % / 7,2 % |
| [Herreligaen](https://danskhaandbold.dk/puljer/105089) | 182 / 126 | 0,528 / 0,618 | +0,090 [0,043; 0,131] | 15,9 % / 7,1 % |
| [ASOBAL](https://as.com/resultados/balonmano/asobal/2024_2025/calendario/) | 240 / 175 | 0,491 / 0,570 | +0,079 [0,033; 0,121] | 11,4 % / 7,9 % |
| [NB I](https://www.nemzetisport.hu/kezilabda/2024/08/ferfi-kezilabda-nb-i-2024-2025) | 182 / 125 | 0,393 / 0,558 | +0,165 [0,113; 0,215] | 8,8 % / 5,8 % |

Brier = Summe der drei quadrierten Wahrscheinlichkeitsfehler. Explorative
Intervalle: 5.000 gepaarte Ziehungen mit Ersatz über ISO-Kalenderwochen,
Seed `20261125`, keine Korrektur für fünf Vergleiche. Alle Vorhersagen des
gleichen Tages aus einem eingefrorenen Stand; Training danach aktualisiert.
Bewertungszeitraum: DE 31.10.24–08.06.25, FR 31.10.24–07.06.25,
DK 23.10.24–12.04.25, ES 15.11.24–01.06.25, HU 15.11.24–25.05.25.

Quellenprüfung: DE chronologischer Spielplan (ein fälschliches „n. V.“ am
24.11. per [Original-Spielbericht](https://hamburg-handball.de/2024/11/24/robin-haug-sichert-heimsieg-hsvh-gewinnt-gegen-hc-erlangen-mit-2827/)
als reguläres 28:27 bestätigt); FR LNH Saison 2024/25, alle Spieltage, nur
abgeschlossene Starligue-Karten; DK `Grundspil`, veröffentlichter iCal-Kalender
der Gruppe mit Endständen; ES AS/Opta Runden 1–30, tatsächliches Spieldatum je
Karte; HU `ALAPSZAKASZ`, nur Hauptrunde, ein fehlender Leerraum vor Torzahl und
die Namensvariante ETO/Győr normalisiert. Keine Rohdaten in Git.

Zusatzprobe aktuelle ASOBAL-Saison 2026/27: 80 reguläre Partien Runden 1–10 aus
den offiziellen Liga-Ergebnisseiten, Runden 7/8 über deren Kalender. 16 Prognosen
vom 13.–22.11. (sechs Spieltage, Runden
[9](https://asobal.es/liga/resultados/9/)/[10](https://asobal.es/liga/resultados/10/));
Brier 0,409 gegen 0,523, Vorteil 0,114, illustratives 95%-Tagesblockintervall
[-0,139; 0,250]. Neun Heim-, sieben Auswärtssiege, kein Remis. Die enge
Stichprobe bestätigt keinen aktuellen Vorteil. Keine Modellformel geändert.

## Anbieter und Entscheidung

- [API-Sports Handball](https://api-sports.io/sports/handball) listet die fünf
  Ligen mit Quoten. Offen: aktueller Saisonzugriff im konkreten Tarif und Anteil
  von Spielen mit gültigen, zeitgestempelten Heim/Remis/Auswärts-Quoten je Liga.
- Null vollständige zeitgebundene Markt-/Ergebnispaare stammen aus diesem Test.
  Die Verbesserung gegenüber Ligahäufigkeiten ist kein Nachweis gegen den
  Buchmachermarkt. Dänemark unterschätzt Remis besonders; zuerst in einem
  separaten Zeitraum prüfen, keine Anpassung auf diese Testspiele.
- [The Odds API](https://the-odds-api.com/sports/handball-bundesliga-odds.html)
  dokumentiert aktuelle deutsche Bundesliga-Quoten im freien Tarif; nur für
  Deutschland verifiziertes Angebot auf der Produktseite, keine gemessene
  Abdeckung mit dem BetBoy-Schlüssel. Für einen reinen Bundesliga-Test führt
  diese Quelle zuerst zum Ziel. Historische Quoten dort nur im Bezahlplan.
- Für fünf Ligen erst API-Sports-Gratiszugang oder Anbieterprobe mit aktuellen
  Endständen und vollständigen 1X2-Preisen prüfen. Falls die aktuelle Saison
  im Gratisplan gesperrt ist: höchstens ein Monat Handball-PRO zum Datencheck,
  kein Mehrmonats- oder All-Sports-Paket allein wegen Handball. Zu Beginn pro Liga
  verfügbare aktuelle Spiele, exakt bindenbare Preise, Buchmacher und Zeitstempel
  dokumentieren. Erst nach dem gepaarten Marktvergleich eine Tippfreigabe prüfen.

Pilot standardmässig aus, neun Abrufe je Zürcher Tag maximal, kein neuer Timer,
keine Nutzung eines Kontos, kein Kauf und keine Produktionsänderung.
Gezielte Regression: 364 Tests unter `gate`, 217 unter `floor` bestanden;
Ruff und unabhängige Prüfung des Tageslimits und der Ligabindung grün. Die
Vollsuite wurde nicht ausgeführt.
