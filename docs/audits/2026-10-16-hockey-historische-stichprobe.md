# Hockey: historische Stichprobe der Saison 2023/24

## Ergebnis

**62 von 100 Siegerprognosen richtig (62 %).** Derselbe Spielbestand hätte mit
„immer Heimsieg“ 51 richtige Ergebnisse geliefert. Das ist eine explorative
rückblickende Stichprobe des vorhandenen Grundmodells, kein nachgewiesener
Wettgewinn und keine Abnahme der noch fehlenden Kontexteffekte.

| Liga | Geprüft | Richtig | Trefferquote | Immer Heimsieg, gleiche Spiele |
| --- | ---: | ---: | ---: | ---: |
| NHL | 20 | 15 | 75 % | 7/20 |
| Schweizer National League | 20 | 13 | 65 % | 10/20 |
| SHL | 20 | 11 | 55 % | 11/20 |
| Liiga | 20 | 13 | 65 % | 11/20 |
| DEL | 20 | 10 | 50 % | 12/20 |
| Gesamt | 100 | 62 | 62 % | 51/100 |

Die DEL schneidet in dieser Stichprobe schlechter ab als „immer Heimsieg“;
das darf im Gesamtwert nicht untergehen. Aus nur 20 Fällen je Liga lässt sich
keine verlässliche Rangliste der Ligen ableiten.

Vorab im Analysecode festgelegte Wahrscheinlichkeitsklassen:

| Geschätzte Chance der gewählten Seite | Anzahl | Richtig | Trefferquote |
| --- | ---: | ---: | ---: |
| Mindestens 60 % | 52 | 35 | 67,3 % |
| Mindestens 70 % | 23 | 18 | 78,3 % |

Die Klassen überlappen. Die Schwellen wurden nicht nach diesem Ergebnis
optimiert und sind keine neue öffentliche Tippregel.

Zusätzliche Wahrscheinlichkeitsprüfung über alle 100 Fälle:

- Brier-Fehler Modell: **0,229629**; aus jeweils früheren Spielen geschätzte
  Heimquote als Vergleichswahrscheinlichkeit: **0,251900**. Kleiner ist besser.
- Logarithmischer Fehler: **0,651193**, Vergleich **0,696997**.
- Durchschnittliche geschätzte Chance der gewählten Seite: **62,51 %**.
- Rein beschreibendes Wilson-95-%-Intervall für 62/100: **52,2–70,9 %**.
  Wiederholte Teams, überlappende Trainingssätze und systematische Auswahl
  verletzen einfache unabhängige Zufallsstichprobenannahmen. Das Intervall ist
  daher kein belastbarer Signifikanz- oder Freigabenachweis.

## Was genau gerechnet wurde

1. Nutzer hat historische Daten aus 2022/2023 ausdrücklich für diese
   Stichprobe freigegeben. Das ersetzt nicht die weiterhin notwendige
   aktuelle Datenanbindung für den produktiven Fünf-Ligen-Ausbau.
2. Ein Katalogabruf und fünf Saisonabrufe über den vorhandenen API-Hockey-
   Zugang, mit bestehender Kontingentsteuerung: insgesamt **sechs Anfragen**.
   Kein anderer Anbieter, kein Abokauf. 3.239 Saisonzeilen, lokale Sportdaten
   **2.066.388 Bytes**. Bild-URLs sind Text; keine Bilder heruntergeladen.
3. Nativer Saisonparameter **2023 bedeutet hier Saison 2023/24**, nicht
   Kalenderjahr 2023. Testfenster vor der Ergebnisbewertung festgelegt:
   **1.–31. Januar 2024**. Pro Liga 20 gleichmäßig über Startzeit/native ID
   verteilte Termine, ohne Blick auf Sieger, Tore oder Modellwahrscheinlichkeit.
   Ziel-IDs und Modellhash vor dem ersten Ergebnislauf eingefroren.
4. Für jeden Termin eigener Fit ausschließlich auf passenden früheren
   Ligaspielen seit **1. November 2023**. Fester Abstand: Spielbeginn des
   jüngsten Trainingsspiels mindestens **48 Stunden** vor dem Zielspiel. Mindesthistorie,
   acht Spiele je Zielteam, verbundener Gegnergraph, mindestens acht passende
   OT/SO-Ergebnisse, 1.200-Historienlimit, Regularisierung, Optimierer und
   Wahrscheinlichkeitsformel unverändert aus `sports_prematch._fit/_predict`.
5. Markt: **Sieger einschließlich Verlängerung und Shootout**. Gewählt wird die
   Seite mit höherer Modellwahrscheinlichkeit. Ergebnis des Zielspiels geht
   nicht in dessen Fit ein. Heim-/Gast-ID und Regulation/OT/SO bleiben durch den
   vorhandenen nativen Ergebnisparser getrennt.
6. Keine Ziel-Fälle nachträglich ersetzt. Alle 100 festgelegten Termine waren
   auswertbar; keine Abstention, fehlenden Ziele oder Ergebnisnachfüllung.

### Datenqualität

| Liga | Saisonzeilen | Verwertbare Finals | Zurückgewiesen |
| --- | ---: | ---: | --- |
| NHL | 1.514 | 1.507 | 7 native Ergebnis-/Periodenkonflikte |
| National League | 415 | 408 | 3 Ergebnis-/Periodenkonflikte, 4 nicht verwertbare Endstatus |
| SHL | 411 | 411 | 0 |
| Liiga | 495 | 495 | 0 |
| DEL | 404 | 404 | 0 |

Ungültige Quellzeilen wurden nicht repariert oder in vermeintlich gültige
historische Ergebnisse umgedeutet. Keine der 100 ausgewählten Zielzeilen war
davon betroffen.

## Wichtige Grenzen

- Die Ergebnisse wurden **2026** empfangen. Ihre echten Empfangszeiten bleiben
  erhalten. Der isolierte Offline-Vergleich verwendet ausdrücklich eine
  rückblickende Verfügbarkeitsannahme; keine rückdatierten Produktionsbelege.
  48 Stunden seit Spielbeginn beweisen nicht den damaligen Veröffentlichungszeitpunkt.
- Archive können spätere Ergebniskorrekturen enthalten. Keine ursprünglichen
  Vorab-Snapshots und keine damalige Tippveröffentlichung sind damit bewiesen.
- Kalenderfenster in der Saisonmitte; native Phasen- und Neutralfeldinformationen
  fehlen im API-Vertrag. Heimbezeichnung wird wie im bestehenden Grundmodell
  verarbeitet, nicht durch neu erfundene Spielortinformationen ersetzt.
- Getestet wird derselbe numerische API-Hockey-Fit. NHL wird in diesem Vergleich
  ebenfalls über dessen native API-Hockey-Perioden versorgt, nicht als Reproduktion
  eines konkreten alten NHL-Feed-Snapshots ausgegeben.
- **Keine historischen Quoten**: keine Rendite, keine Einsätze, keine Prüfung
  der tatsächlichen damaligen Quote>=1,20 und keine Gleichsetzung mit dem
  heutigen gefilterten öffentlichen Tippbestand.
- **Torhüter, Verletzungen und gemessene Müdigkeit nicht enthalten.** Deren
  Wirkung oder Verbesserung ist durch diese Stichprobe nicht nachgewiesen.
- Kein Train/Tune/Test-Freigabelauf, keine Änderung oder Aktivierung eines Modells.
  Schwellen und Gewichte nach Betrachtung dieser Fälle würden neue unberührte
  Testspiele erfordern.

## Prüfung und Wiederholung

Acht Offline-Schutztests bestanden, darunter identische Prognose bei veränderten
Ziel-/Zukunftsergebnissen, echte Empfangszeit, 48-Stunden-Grenze, unveränderte
Zielauswahl bei fehlenden Ergebnissen, Konflikt-Deduplikation und Handrechnung
von Treffer-/Brier-Statistik. Die unabhängige Gegenprüfung bestätigte alle
100 Zielbindungen, fünf Quellhashes, Modellhash, native Regulation-/OT-/SO-
Ergebnisse, frühere Trainingssätze und sämtliche Kennzahlen ohne kritischen
Befund. Keine doppelten IDs/Spielpaarungsaliase. Mindestens 13 frühere Spiele
pro Zielteam und mindestens 19 frühere OT/SO-Fälle pro Fit; keine Mindestgrenze
umgangen. Die Gegenprüfung wiederholte nicht sämtliche 100 Optimierungen.

Artefakte außerhalb Git:
`C:/Projekt/BetBoy/output/hockey-top5-20261016/`:
`fetch_2023_sample.py`, `source-2023-01.json`, `sample_analysis.py`,
`test_sample_analysis.py`, `targets-2023-01.json`, `result-2023-01.json`,
`analysis-2023-01.log`, `analysis-tests-final.log`.

SHA-256:

| Artefakt | Hash |
| --- | --- |
| Quelldatei | `775c0a01368bfc84d80e8cc38c070bdb187afaf1f236b3b9f323507aa5491234` |
| Eingefrorene Zielauswahl | `2dc6925cbd834e71cd62b754fa5ed027312c5dc97e0c10bffd13ebc306895c28` |
| Ergebnisdatei | `77412e96d7be61af56b6898df29b689d48cb91c6b806b1c33dc2890f9763d61e` |
| Analyseskript | `a6516e3cd8d06f8aec8ae16dd86a1ed4078987aeeb3b02f16e2041ff7be69b9e` |

Keine Produktivmodelle, Historienbelege oder Geldbuchungen geändert. Nur die
bestehende Kontingentdatenbank erfasste die normalen sechs API-Reservierungen.
Kein zusätzlicher automatischer Sportlauf, kein Deploy und kein Backup.
