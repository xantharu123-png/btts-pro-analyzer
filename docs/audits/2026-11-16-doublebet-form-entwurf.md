# Doublebet: Form der letzten 10 Spiele bei gleicher Quote (Entwurf)

Stand 16.11.2026. Owner-Auftrag: Doublebet soll unter Wetten mit gleicher Quote die wahrscheinlichere finden, etwa
über die Form. Diese Prüfung fragt, ob die Form im Kurzcheck („x von 10“) dafür taugt. Sie ist ein Entwurf auf den
älteren Daten. Eine Vorab-Regel für die neueren Daten wurde nicht festgelegt, weil der Entwurf keine Trennung zeigt.

## Daten und Methode

- **Abruf:** Owner „Ja, abrufen“: 66 API-Abrufe für die beendeten Spiele aller Katalogligen der Saison 2026
  (8863 Spiele), dazu die Länderspiele aus der Kleinstaaten-Prüfung (13 Abrufe, 3394 Spiele). Nur Lesen, keine Produktionsänderung.
- **Form-Zahl je Wette:** Für jedes Team nimmt die Prüfung die letzten 10 beendeten Spiele vor dem Anstoss, wie im
  Kurzcheck über alle Spielorte und mindestens 5. Jedes Spiel wird mit der Rolle im kommenden Spiel gelesen, also das
  Heimteam als Heim und das Gastteam als Gast. Abgerechnet wird mit der Marktregel der Engine
  (`_fixture_market_outcome`). Die Form-Zahl ist der Mittelwert der Trefferanteile beider Teams.
  - Beispiel „Heimteam über 1,5 Tore“: Wie oft schoss das Heimteam mehr als 1 Tor, und wie oft kassierte das
    Gastteam mehr als 1?
- **Wetten:** Fussball-Tormärkte mit Anstoss vor 01.11.2026 und gespeicherter Quote 1,40–3,00 (früheste Quote).
  Doublebet-Tipps sind ausgeschlossen. Ecken und Karten fehlen (341), weil die Abrufdaten keine Statistik tragen.
  76 Wetten hatten weniger als 5 Vorspiele.
- **Vergleich:** Je 0,10-Quotenstufe die obere gegen die untere Hälfte der Form-Zahl. Stufen unter 10 Wetten und
  Gleichstände am Median fallen weg. Bootstrap über Spiele, 4000 Ziehungen.

## Ergebnis

**Die Form trennt nicht.** Bei gleicher Quote gewinnt die Hälfte mit der besseren Form nicht öfter.

| Gruppe | Wetten | Spiele | obere Hälfte gewonnen (Form) | untere Hälfte gewonnen (Form) | Unterschied [95 %] |
|---|---:|---:|---|---|---:|
| alle Tormärkte | 1235 | 622 | 50,5 % (66 %) | 53,5 % (43 %) | −3,0 [−9,6; +3,7] |
| Teamtore | 736 | 473 | 53,8 % (68 %) | 52,6 % (46 %) | +1,2 [−6,1; +8,6] |
| Ergebnis | 198 | 196 | 53,5 % (53 %) | 49,5 % (33 %) | +4,0 [−9,3; +17,8] |
| Doppelte Chance | 125 | 115 | 56,5 % (72 %) | 55,6 % (53 %) | +0,9 [−17,2; +18,3] |
| Modellchance zum Vergleich | 1298 | 640 | 51,3 % | 51,9 % | −0,6 [−7,0; +5,7] |

Nach Form-Stufen, verglichen mit dem Schnitt gleicher Quote:

| Form | Wetten | gewonnen | Schnitt gleicher Quote | Abstand |
|---|---:|---:|---:|---:|
| unter 40 % | 218 | 39,4 % | 39,6 % | −0,2 |
| 40–59 % | 537 | 52,1 % | 50,3 % | +1,8 |
| 60–79 % | 465 | 55,9 % | 57,0 % | −1,1 |
| ab 80 % | 88 | 56,8 % | 61,6 % | −4,7 |

## Einordnung

- **Die Form zählt, aber die Quote enthält sie schon.** Wetten mit guter Form gewinnen viel öfter (39 % gegen 57 %),
  sie haben aber auch die tieferen Quoten. Bei gleicher Quote bleibt kein Unterschied übrig.
- **Teamtore und Ergebnis liegen leicht im Plus,** aber weit innerhalb des Zufalls. Eine Regel daraus wäre
  nachträglich ausgesucht. Deshalb gibt es keinen Prüfschritt auf den Daten ab 01.11.
- **Damit sind geprüft:** Modellchance (D2), Richtung, Direktvergleich, Ausfälle, Märkte und jetzt die Form. Keines
  trennt bei gleicher Quote. Doublebet bleibt unverändert und wählt weiter die höchste Modellchance um 2,00.
- **Nächster Prüfpunkt:** die Bandprüfung auf Daten ab 16.11. (etwa Ende Dezember).
