# Entscheidungswahrscheinlichkeit als Mischung von Modell und Markt

Grundlage: Zeilen des Marktbenchmarks (walk-forward kalibrierte Modell-p, No-Vig-Pinnacle-Closing, Ergebnis, bester Closing-Preis). Mischung im Log-Odds-Raum, `logit(p) = w·logit(Modell) + (1−w)·logit(Markt)`. Das Gewicht w wird auf den chronologisch ersten 70 % der Zeilen per Log-Loss-Raster (Schritt 0,05) gewählt und auf den letzten 30 % bewertet. Die gespeicherte Modell-p bleibt unverändert; die Mischung ist eine getrennte Entscheidungsgrösse (Audit K3).

## Gewicht und Out-of-sample-Güte

| Markt | Zeilen Train/Test | w* (Modellanteil) | LogLoss Modell | LogLoss Markt | LogLoss Mischung | Brier Modell | Brier Markt | Brier Mischung |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| alle Märkte | 116365/49872 | 0.00 | 0.6346 | 0.6158 | 0.6158 | 0.2222 | 0.2140 | 0.2140 |
| RESULT_HOME | 23292/9983 | 0.00 | 0.6465 | 0.6135 | 0.6135 | 0.2276 | 0.2130 | 0.2130 |
| RESULT_DRAW | 23292/9983 | 0.00 | 0.5700 | 0.5647 | 0.5647 | 0.1911 | 0.1893 | 0.1893 |
| RESULT_AWAY | 23292/9983 | 0.00 | 0.5816 | 0.5525 | 0.5525 | 0.1979 | 0.1864 | 0.1864 |
| TOTAL_OVER_2_5 | 23244/9962 | 0.00 | 0.6875 | 0.6742 | 0.6742 | 0.2472 | 0.2408 | 0.2408 |
| TOTAL_UNDER_2_5 | 23244/9962 | 0.00 | 0.6875 | 0.6742 | 0.6742 | 0.2472 | 0.2408 | 0.2408 |

Lesart: w* ist der Anteil, mit dem das Modell über den Markt hinaus Information beiträgt. Ein w* nahe 0 bedeutet, dass die Entscheidung fast vollständig dem Markt folgen sollte.

## Replay der Preisgate-Policy (Haircut 5 pp, 3 % Risiko-ROI, Boden 1,20, bester Closing-Preis)

| Variante | Wetten | Trefferquote | ROI | ROI 90 %-Bootstrap | CLV | CLV 90 %-Bootstrap | Ø Modell−Markt (pp) |
|---|---:|---:|---:|---|---:|---|---:|
| heutige Policy (w = 1, kein Cap) | 34420 | +26.3 % | -5.5 % | [-7.2 %, -3.8 %] | -1.0 % | [-1.2 %, -0.8 %] | +11.0 |
| Policy + Edge-Cap 8 pp | 8380 | +29.4 % | +0.8 % | [-2.5 %, +3.9 %] | +1.5 % | [+1.0 %, +2.3 %] | +6.7 |
| Policy mit Mischung w* je Markt | 236 | +53.8 % | +31.6 % | [+17.6 %, +46.1 %] | +44.1 % | [+26.7 %, +72.7 %] | -6.4 |
| Mischung w* + Edge-Cap 8 pp | 213 | +55.4 % | +32.4 % | [+17.3 %, +48.4 %] | +43.9 % | [+24.6 %, +75.5 %] | -8.4 |
| Mischung w* ohne Haircut | 17389 | +37.5 % | +5.1 % | [+3.0 %, +7.2 %] | +6.4 % | [+6.1 %, +6.8 %] | -0.5 |

Hinweise: Wetten desselben Spiels auf mehreren Märkten sind korreliert (Intervalle zu schmal); der beste Closing-Preis ist für die Ausführung optimistisch; die Mischung mit Markt-p verlangt in der Produktion den vollständigen No-Vig-Markt (alle Seiten), den der heutige Quotenabruf nicht liefert.
