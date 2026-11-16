# Doublebet: Vermutung vorab

Stand 16.11.2026, geschrieben **vor** der Auswertung. Owner: „Ja, untersuchen“.

## Anlass

Doublebet hat vom 01. bis 15.11.2026 nur 6 von 20 Tipps gewonnen (30 %). Das Modell rechnete im Schnitt mit rund
66 %. Die Quote lag jeweils um 2,0, was einer Marktchance von rund 50 % entspricht.

Doublebet wählt seit dem 03.11.2026 so aus (`daily3_selection`, `DOUBLEBET_ODDS_MIN/MAX`):

- Zugelassen sind Tipps mit einer Median-Quote zwischen 1,80 und 2,20.
- Daraus nimmt Doublebet die mit der höchsten Modellchance.

## Vermutung

**D1:** Innerhalb des Quotenbands 1,80 bis 2,20 steigt die Trefferquote mit der Modellchance nicht so, wie das Modell
sagt. Wo das Modell 65 % oder mehr sieht, liegt die tatsächliche Trefferquote näher an der Marktchance (1/Quote) als
an der Modellchance.

Doublebet wählt damit die Fälle, in denen Modell und Markt am weitesten auseinanderliegen. Nach dem Marktbenchmark
schlägt das Modell den Markt nirgends (0 von 112 Zellen). Diese Auswahl trifft deshalb vor allem die Fehler des
Modells.

## Daten

- Alle gespeicherten Prognosezeilen mit Ergebnis (`forecast_rows`, `forecast_results`), alle Sportarten.
- Die früheste gespeicherte Quote je Prognose (`forecast_quotes`), wenn sie zwischen 1,80 und 2,20 liegt.
- Die 20 Doublebet-Tipps vom 01. bis 15.11. sind ausgeschlossen, weil sie die Vermutung erzeugt haben.

## Rechnung und Regel

- **Gruppen nach Modellchance:** unter 55 %, 55 bis 65 %, 65 % und mehr. Je Gruppe:
  - Anzahl
  - Trefferquote
  - mittlere Modellchance
  - mittlere Marktchance (1/Quote; enthält die Buchmachermarge und liegt deshalb leicht zu hoch)
- **D1 bestätigt,** wenn in der Gruppe ab 65 % mindestens 100 Zeilen liegen und die Trefferquote näher an der
  Marktchance als an der Modellchance liegt. Das heisst: |Treffer − Markt| < |Treffer − Modell|.
- **Weniger als 100 Zeilen:** nicht prüfbar.
- **Bestätigt:** Ich lege dem Owner Optionen für eine andere Doublebet-Auswahl vor. Jede Änderung ist ein eigener
  Owner-Entscheid. An diesen Daten wird keine Schwelle eingestellt.
- Diese Regeln werden nach dem Blick auf die Zahlen nicht geändert.
