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

## Anbieterabnahme: API-SPORTS

- [API-Sports Handball](https://api-sports.io/sports/handball) ist für diesen
  Pilot die einzige Quelle. Der echte Zugang gibt für 2026 alle fünf Saisons
  frei. Elf HTTP 200, kein 429; Anbieterheader 7.500/Tag und 300/Minute.
- Der Ligaabruf `/odds?league=…&season=2026&bet=1` liefert Rohzeilen für
  alle fünf Ligen. Die native Spiel-ID steht in `game.id`, der Anbieterzeitpunkt
  in `update`. Fremde Liga, falscher Spielbezug, ältere bzw. bereits begonnene
  Spiele und unvollständige Buchmacher-1X2-Sätze zählen nicht als Preisbeleg.
- Isolierter Echtlauf am 25.11.2026: 450 FT-Ergebnisse, drei Prognosen
  innerhalb von 36 Stunden, ein passender Vorab-1X2-Satz (Dänemark).
  Bundesliga: eine Prognose ohne passendes Angebot. In Spanien, Frankreich
  und Ungarn lag kein Spiel im 36-Stunden-Modellfenster.
- Der Bericht unterscheidet bestätigte Quoten-Spiele über sieben Tage,
  neu bepreiste Modellprognosen, noch offene Modellpreise und Anbieterfehler.
- Null vollständige zeitgebundene Markt-/Ergebnispaare stammen aus diesem Test.
  Die Verbesserung gegenüber Ligahäufigkeiten ist kein Nachweis gegen den
  Buchmachermarkt. Dänemark unterschätzt Remis besonders; zuerst in einem
  separaten Zeitraum prüfen, keine Anpassung auf diese Testspiele.
Pilot im Code standardmässig aus, maximal elf Abrufe je Zürcher Tag. Kein
neuer Timer, keine Buchung, kein weiterer Datenanbieter. Vergleich und
TOP-Aufnahme erst nach echten gepaarten Vorabpreisen und Endständen prüfen.
Die Vollsuite wurde für diese Änderung nicht ausgeführt.

## Warum im Wettfinder nichts erschien

Die Produktion auf `8dfa800` speichert nur die internen Handball-Belege.
Die App hatte weder einen Handballfilter noch einen lesenden Anzeigepfad.
Die Anschlussprüfung am 25.11. gegen den bestehenden Schlüssel klärt,
welche der Rohquoten zu den bestätigten anstehenden Spielen passte:

| Liga | 1X2-Rohzeilen | Anstehend in 7 Tagen | Passende aktuelle Zeile |
| --- | ---: | ---: | ---: |
| Bundesliga | 9 | 9 | 0 |
| ASOBAL | 7 | 8 | 0 |
| Herreligaen | 8 | 7 | 1 |
| Starligue | 7 | 8 | 0 |
| NB I | 6 | 8 | 0 |

36 Zeilen gehörten nicht zum anstehenden Spielplan; eine zu
Nordsjælland–Kolding. Weder für Balingen–Lemgo noch für Ribe-Esbjerg–Ringsted
gab es im Direktabruf nach Spiel-ID einen 1X2-Satz. Das ist kein 429,
Saisonfehler oder vom Parser aussortiertes aktuelles Angebot.

Der [neue Anzeigepfad](../superpowers/specs/2026-11-25-handball-wettfinder-design.md)
nutzt nur den jeweiligen Lauf, liefert bei passender Datenlage eine
Modell-Auswahl je Spiel und liest sie ohne weiteren Anbieterzugriff.

## Folgeaudit und Reparatur

- Quotenzeit nach Empfang: Updates während des Abrufs sind gültig, sofern
  Quelle nicht in der Zukunft, jünger als 36 Stunden und Empfang vor Anwurf.
  Bei neuer Spielidentität bleibt die alte Prognose unverändert abgelegt;
  ein passender neuer Termin wird neu modelliert. Bei unveränderter Anbieter-ID
  wird eine Preisquelle vor der bestätigten Verlegung nicht übernommen.
- Marktvergleich: keine Buchmacherquote im Modell. Pro Prognose derselbe
  verifizierte Endstand und ein vollständiger 1X2-Markt, Anbieterstand und
  Abruf jeweils höchstens eine Stunde von der Modellentscheidung entfernt.
  Ältere oder nicht belegte Uhrzeiten werden getrennt gezählt. Brier und
  Log Loss werden auf dem gepaarten Bestand ausgewiesen. Live-Stand nach
  #173: null abgerechnete Marktpaare.
- Produktionsbeispiel Nordsjælland–Kolding: 63,0 % Modellchance, Median
  1,45, implizite Gewinnschwelle rund 69,0 %, modellseitiger Erwartungswert
  an diesem Referenzpreis −8,6 %. Der 1,20-Filter ist kein Value-Nachweis.
- Form mit festem 90-Tage-Zeitgewicht und separat erlernte Remis-Anpassung
  sind reine Studienvarianten. Testfenster 01.02.–30.06.2027, Kalibrierung
  endet am 31.01.2027. Ab ausreichendem Bestand zeigt der Bericht gepaarte
  97,5-%-Intervalle über ISO-Wochen (5.000 feste Bootstrap-Ziehungen).
  Ohne echten zeitlich getrennten Qualitätsnachweis
  bleibt das bisherige 1X2-Modell maßgeblich. Die gezählte Quote entscheidet
  nicht darüber, welche Partien in die Modellstudie eingehen.
