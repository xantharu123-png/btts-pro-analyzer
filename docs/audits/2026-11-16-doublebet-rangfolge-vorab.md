# Doublebet: Rangfolge bei gleicher Quote, vorab

Stand 16.11.2026, geschrieben **vor** der Auswertung. Owner: „Ja, umstellen. Versuch es noch einmal.“

## Richtige Frage

Doublebet behauptet keinen Vorteil gegenüber dem Markt. Unter Wetten mit derselben Quote wählt es die, die nach
unserer Rechnung (Form, Historie, Statistik) wahrscheinlicher ist. Zu prüfen ist deshalb die Rangfolge: Gewinnen bei
gleicher Quote die Wetten, die das Modell höher einstuft, öfter als die tiefer eingestuften? Die erste Vorab-Regel
(`docs/audits/2026-11-16-doublebet-pruefung-vorab.md`) fragte nach Modell gegen Markt. Diese Frage ersetzt sie.

## Vermutung

**D2:** Bei gleicher Quote gewinnt die obere Hälfte der Modellchancen öfter als die untere Hälfte.

## Daten (noch nicht angesehen)

- Alle gespeicherten Prognosen mit Ergebnis und gespeicherter Quote (früheste Quote je Prognose), alle Sportarten.
- **Quotenbereiche:** 1,40 bis 1,79 und 2,21 bis 3,00. Das Band 1,80 bis 2,20 ist ausgeschlossen, weil es schon
  angesehen wurde (`docs/audits/2026-11-16-doublebet-pruefung-ergebnis.md`).
- Die Doublebet-Tipps sind ausgeschlossen.

## Rechnung

- **Quotenstufen:** Die Quoten werden in Stufen von 0,10 eingeteilt, zum Beispiel 1,40 bis 1,49.
- **Hälften je Stufe:** In jeder Stufe teilt der Median der Modellchance die Wetten in eine obere und eine untere
  Hälfte. Wetten genau auf dem Median zählen zur unteren Hälfte. Stufen mit weniger als 10 Wetten fallen weg.
- **Kennzahl:** Trefferquote der oberen Hälften minus Trefferquote der unteren Hälften, über alle Stufen gezählt.
- **Unsicherheit:** 95-%-Bootstrap-Intervall mit 10 000 Ziehungen und Startwert 20261116. Gezogen werden ganze Spiele,
  weil mehrere Wetten desselben Spiels zusammenhängen.
- **Information,** ohne Einfluss auf den Entscheid: dieselbe Rechnung getrennt für die beiden Quotenbereiche.

## Regel

- **D2 bestätigt,** wenn die Kennzahl über null liegt, die untere Grenze des Intervalls über null liegt und mindestens
  400 Wetten in die Rechnung eingehen.
- **D2 nicht bestätigt,** wenn das Intervall null enthält oder ganz unter null liegt.
- **Nicht prüfbar** bei weniger als 400 Wetten.
- Dieselbe Regel gilt in rund 5 Wochen erneut für das Doublebet-Band 1,80 bis 2,20. Dann zählen nur Prognosen ab dem
  16.11.2026.
- An diesen Daten wird keine Schwelle eingestellt. Die Regeln werden nach dem Blick auf die Zahlen nicht geändert.
