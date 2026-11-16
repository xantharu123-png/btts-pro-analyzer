# Doublebet: Ergebnis der Prüfung

Stand 16.11.2026. Die Prüfung folgt der Vorab-Regel in `docs/audits/2026-11-16-doublebet-pruefung-vorab.md`
(Commit `c8c4d82`, gepusht vor der Auswertung).

## Ergebnis

**Nicht prüfbar.** In der Gruppe ab 65 % Modellchance liegen nur 54 Zeilen, die Regel verlangt 100. D1 ist damit
weder bestätigt noch widerlegt.

Quotenband 1,80 bis 2,20, alle gespeicherten Prognosen mit Ergebnis, ohne die 21 Doublebet-Tipps vom 01. bis 15.11.:

| Modellchance | Zeilen | Treffer | Modell | Markt (1/Quote) |
|---|---:|---:|---:|---:|
| unter 55 % | 434 | 43,1 % | 46,8 % | 50,9 % |
| 55 bis 65 % | 192 | 44,8 % | 58,9 % | 51,6 % |
| ab 65 % | 54 | 57,4 % | 70,4 % | 52,2 % |

Fast alle Zeilen sind Fussball (632 von 680). Eishockey hat 33 Zeilen unter 55 %.

## Was die Zahlen zeigen (Information, kein Prüfergebnis)

- **Das Modell ist zu optimistisch.** In allen drei Gruppen liegt die Trefferquote unter der Modellchance, am
  deutlichsten zwischen 55 und 65 %: 44,8 % statt 58,9 %.
- **Die Treffer bleiben unter dem Markt.** Wo das Modell mehr sieht als der Markt (ab 55 %), liegt die Trefferquote
  ungefähr auf Marktniveau oder darunter. Die Marktchance 1/Quote enthält die Buchmachermarge, die faire Marktchance
  liegt also noch ein bis zwei Punkte tiefer.
- **Gegenüber dem Markt findet das Modell hier keinen Vorteil.** Das passt zum Marktbenchmark: 0 von 112 Zellen
  schlagen den Markt. Doublebet wählt im Band die höchste Modellchance, also die grösste Abweichung vom Markt. Damit
  wählt es eher Modellfehler als Vorteile. Die 6 von 20 gewonnenen Doublebet-Tipps passen dazu.

## Folgen

- Nach der Vorab-Regel ist **nichts entschieden.**
- **Abwarten:** Bei etwa 9 neuen Zeilen pro Woche ab 65 % ist die Gruppe in rund 5 Wochen gross genug. Dann gilt
  dieselbe Regel, auf den neuen Zeilen ab dem 16.11.2026.
- **Owner-Entscheid jederzeit möglich:** zum Beispiel die Doublebet-Auswahl ändern oder pausieren. Das wäre eine
  bewusste Produktentscheidung ohne bestätigte Prüfung.
