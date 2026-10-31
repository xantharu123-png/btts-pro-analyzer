# Shadow-Modellgrenze 70 % für Tipps ohne Quote (Policy `shadow-model-first-v12`)

Datum: 31.10.2026. Owner-Entscheid im Chat („Ja, 70 %“) nach dem Befund unten. Ergänzt
`docs/audits/2026-10-31-shadow-tipps-ohne-quote.md` (v11).

## Befund

- v11 übernahm die Modellgrenze der App (65 %, `market_consensus.FLOOR_UNPRICED_MAX_PROBABILITY`). Diese Grenze
  gehört zur 1,20-Regel der App. Shadow-Kandidaten brauchen ohnehin mindestens 55 % konservative
  Wahrscheinlichkeit (Abschlag eingerechnet), für Tipps ohne Quote blieb so nur ein schmales Band unter 65 %.
- Erster v11-Lauf (31.10. 08:42, `output/release-20261031-1/verify-01.log`): 2 Spiele ohne Bet365-Quote,
  8 bzw. 11 glaubwürdige Kandidaten, alle bei 65 % oder höher, also kein Tipp.
- Messung (`output/release-20261031-1/price_by_probability.sh`, nur lesend): 9589 Fussballprognosen der App mit
  Bet365-Quote (`forecast_evidence.db`, letzte Quote je Zeile).

| Modellwahrscheinlichkeit | n | Anteil Quote ≥ 1,30 | Median-Quote | 10-%-Quantil |
|---|---:|---:|---:|---:|
| 55–60 % | 718 | 93,3 % | 1,62 | 1,36 |
| 60–65 % | 666 | 88,4 % | 1,50 | 1,28 |
| 65–70 % | 698 | 74,6 % | 1,36 | 1,18 |
| 70–75 % | 776 | 46,3 % | 1,28 | 1,17 |
| 75–80 % | 894 | 30,9 % | 1,25 | 1,11 |
| 80–85 % | 815 | 7,2 % | 1,14 | 1,08 |
| 85–93 % | 631 | 2,1 % | 1,07 | 1,03 |

Bis 70 % liegt die übliche Bet365-Quote bei 1,30 oder darüber, danach darunter.

## Regel ab v12

- `SHADOW_UNPRICED_MAX_PROBABILITY = 0.70`: Ein Kandidat ohne frische Bet365-Quote wird nur unter 70 %
  Modellwahrscheinlichkeit Tipp. Alles andere aus v11 bleibt (46 Tormärkte, Bet365-Tipp ab 1,30 zuerst,
  `shadow_unpriced`, Bewertung nur nach Treffern).
- Die App behält ihre 65 % für die 1,20-Regel.

## Risiko und Prüfung

Im Band 65–70 % hätte rund ein Viertel der Bet365-Quoten unter 1,30 gelegen; unter den Tipps ohne Quote stecken
also einige, die mit Quote ausgeschlossen worden wären. Die Grenze kommt aus dem Marktpreis, nicht aus dem
Ergebnis. Vor der ersten v12-Zeile festgelegt: Die Zählung beginnt unter v12 neu (unter v11 gab es keinen Tipp).
Liegt die Trefferquote der Tipps ohne Quote nach 200 abgerechneten deutlich unter der mittleren
Modellwahrscheinlichkeit (`expected_hit_rate`), wird die Grenze neu entschieden.
