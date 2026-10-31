# Shadow-Tipps ohne Quote (Policy `shadow-model-first-v11`)

Datum: 31.10.2026. Owner-Auftrag im Chat: Tipps unter der Mindestquote ausschliessen, Tipps ohne auffindbare
Quote aber trotzdem zulassen („es gibt Wettarten, die Bet365 überhaupt nicht anbietet“).

## Befund (nur lesend, `output/release-20261030-3/why_no_tips.sh`)

- Freitag 30.10.: 42 Spiele im Shadow, alle bewertet, nur 3 mit Tipp (2 Legacy unter v9, 1 Hybrid unter v10).
  Seit 30.10. 00:00 meldete der Shadow 57-mal „keine aktuelle Bet365-Quote mit Providerzeit“ (je Lauf gezählt).
- Der Shadow prüfte nur die 18 Tormärkte mit Bet365-Zuordnung (`_QUOTE_BETS`). Die App kennt 46 Tormärkte, die
  sich über den Endstand abrechnen lassen; Teamtore, Torbereiche, Ergebnis-plus-Tore und Oder-Märkte fielen weg.
- Was andere Buchmacher anbieten und Bet365 nicht, sind in den App-Daten fast nur Eckenmärkte (z. B. 31.10.:
  24-mal `HOME_CORNERS_OVER_4_5`); Ecken lassen sich ohne Statistikabruf nicht abrechnen.

## Regel ab v11

1. **Kandidaten:** alle 46 Tormärkte (`_shadow_market`: Marktarten aus `_GOAL_SETTLED_KINDS`), Reihenfolge
   unverändert modellgeführt.
2. **Mit Quote wie bisher:** Der bestplatzierte Kandidat mit frischer Bet365-Quote (bis 24 Stunden) ab **1,30**
   wird Tipp im Ledger `predictions` und zählt für Gewinn/Verlust und die 1000er-Prüfstufe. Ein Kandidat mit
   frischer Quote unter 1,30 bleibt draussen.
3. **Ohne Quote:** Gibt es keinen solchen Tipp, wird der bestplatzierte Kandidat ohne frische Bet365-Quote Tipp,
   wenn seine Modellwahrscheinlichkeit **unter 65 %** liegt. Das ist die Modellgrenze der App
   (`market_consensus.FLOOR_UNPRICED_MAX_PROBABILITY`, 25.10.2026): ab 65 % ist ein Preis über der Mindestquote
   ohne Quote nicht plausibel. Grund je Tipp: `no_bet365_market` (Markt ohne Bet365-Zuordnung) oder
   `no_fresh_bet365_quote`. Ein Abruf entfällt, wenn kein Kandidat eine Bet365-Zuordnung hat.
4. **Ein Tipp je Spiel und Kohorte:** Ein Tipp ohne Quote schliesst das Spiel für diese Kohorte; eine später
   eintreffende Quote erzeugt keinen zweiten Tipp.
5. **Bewertung:** Tipps ohne Quote stehen in `shadow_unpriced`, werden täglich nach 09:00 über den Endstand
   abgerechnet (`step_settle_unpriced`) und im Artefakt als `unpriced_results` geführt: Anzahl, Treffer,
   Fehlschläge, Trefferquote gegen die mittlere Modellwahrscheinlichkeit (`expected_hit_rate`). Ohne Preis gibt es
   keinen Gewinn: Sie zählen nicht zur Rendite und nicht zur 1000er-Prüfstufe; erfundene Quoten gibt es nicht.

## Nicht umgesetzt

- Mittelwert anderer Buchmacher als Ersatzquote: Ohne Bet365-Filter liefert API-Football die Buchmacher
  seitenweise (`tests/test_shadow_markets.py`), das kostet je Spiel weitere Abrufe. Der Nutzen ist klein, weil nur
  rund 2 % der Spiele gar keinen Bet365-Markt haben und die Lücken sonst Eckenmärkte sind.

## Zählung und Prüfung

Die Auswahl ändert sich (ein Tipp ohne Quote verdrängt eine spätere Bet365-Quote), deshalb Policy v11; die
Zählung der 1000 Tipps beginnt unter v11 neu (unter v10 gab es einen Tipp). Vor der ersten v11-Zeile festgelegt:
Liegt die Trefferquote der Tipps ohne Quote nach 200 abgerechneten deutlich unter der mittleren
Modellwahrscheinlichkeit, wird die Modellgrenze neu entschieden.
