# Doublebet: Märkte suchen, in denen die Rangfolge trennt (vorab)

Stand 16.11.2026, geschrieben **vor** der Auswertung. Owner: „Märkte suchen, wo es trennt“.

## Ausgangslage

Über alle Märkte gewinnt bei gleicher Quote die obere Hälfte der Modellchance nicht öfter als die untere
(−1,5 Punkte, `docs/audits/2026-11-16-doublebet-rangfolge-ergebnis.md`). Gesucht sind einzelne Marktarten und
Sportarten, in denen die Rangfolge doch trennt. Nur solche Märkte soll Doublebet künftig nehmen. Weil viele Gruppen
geprüft werden, gibt es zwei Stufen.

## Gruppen (fest)

Sportart × Marktart. Die Marktart ergibt sich aus `market_key`:

| Marktart | Erkennung |
|---|---|
| Ergebnis | `RESULT_HOME`, `RESULT_AWAY`, `RESULT_DRAW` |
| Doppelte Chance | `DC_…` |
| Gesamttore | `TOTAL_OVER_…`, `TOTAL_UNDER_…` |
| Teamtore | `HOME_OVER_…`, `HOME_UNDER_…`, `AWAY_OVER_…`, `AWAY_UNDER_…` |
| Torbereich | enthält `_RANGE_` |
| Ecken | enthält `CORNERS` |
| Karten | enthält `YELLOW` oder `CARD` |
| Kombi | `RESULT_TOTAL_…`, `MIXED_…` |
| Beide treffen | enthält `BTTS` |
| Sieger | `H2H` |
| andere | alles Übrige |

Die Erkennung läuft in dieser Reihenfolge. Ecken, Karten, Torbereich und Kombi werden vor den Tor-Märkten geprüft.

## Stufe 1: Suchen (jetzt, auf vorhandenen Daten)

- **Daten:** alle gespeicherten Prognosen mit Ergebnis und frühester Quote zwischen 1,40 und 3,00, ohne
  Doublebet-Tipps.
- **Rechnung je Gruppe:** wie in der Rangfolge-Prüfung. Je Quotenstufe von 0,10 wird am Median der Modellchance
  geteilt, Stufen unter 10 Wetten fallen weg. Kennzahl ist die Trefferquote der oberen minus der unteren Hälfte.
- **Einseitiger p-Wert:** der Anteil der Bootstrap-Ziehungen mit Unterschied ≤ 0. Es gibt 10 000 Ziehungen über
  Spiele, Startwert 20261116.
- **Geprüft** werden nur Gruppen mit mindestens 200 Wetten. Über diese Gruppen gilt die Benjamini-Hochberg-Korrektur.
- **Kandidat** ist eine Gruppe mit Unterschied über 0 und korrigiertem q unter 0,10.

## Stufe 2: Bestätigen (in rund 5 Wochen, auf neuen Daten)

- **Daten:** nur Prognosen ab dem 16.11.2026, gleiche Quoten und gleiche Rechnung.
- **Bestätigt** ist ein Kandidat aus Stufe 1, wenn er mindestens 100 Wetten hat, der Unterschied über 0 liegt und der
  einseitige p-Wert unter 0,05 liegt.
- Nur bestätigte Gruppen kommen für eine neue Doublebet-Auswahl in Frage. Die Umstellung ist ein eigener
  Owner-Entscheid.
- **Ohne Kandidaten in Stufe 1** oder ohne Bestätigung in Stufe 2 gibt es keine Gruppe mit nachgewiesener Trennung.
  Dann entscheidet der Owner neu.

## Grenzen

- **Stufe 1 ist eine Suche, kein Beleg.** Erst Stufe 2 zählt.
- **Kein Neueinstellen:** An den Daten werden keine Schwellen, Gruppen oder Quotenbereiche nachträglich angepasst.
- **Unverändert bis zum Entscheid:** Doublebet läuft weiter wie bisher.
