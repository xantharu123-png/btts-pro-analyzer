# Shadow-Bewertung nach Gewinn und Verlust zur geholten Quote

Datum: 30.10.2026. Owner-Entscheid im Chat: Die Quote wird einmal geholt; man muss nicht bis zum Anpfiff warten,
eine Quote von 1,40 fällt nicht plötzlich auf 1,20. Bewertet wird, ob der Tipp zu dieser Quote gewinnt.

## Befund

- Unter v8 und v9 hatten alle drei Tipps eine erfasste Schlussquote mit demselben Bet365-Stempel wie die
  Öffnung (Fixtures 1638114, 1638115, 1565519; Stempel 12:00/12:04 UTC, Anpfiff 16:00/17:00 UTC). API-Football
  liefert in den letzten Stunden vor Anpfiff offenbar keinen neuen Bet365-Stand, damit gab es keine einzige
  gültige CLV-Messung (`output/release-20261030-1/verify-02-1920.log`).
- `CLVTracker.get_clv_statistics` zählt eine abgerechnete Zeile nur mit gültiger Schlussquote; eine Zeile ohne
  Schlussquote sperrt die ganze Statistik.

## Regel

- Massgeblich ist `results` im Run-Artefakt (`_result_statistics` je Kohorte): abgerechnete Tipps der aktuellen
  Modell- und Policy-Version, gewonnen/verloren/Push, Trefferquote, mittlere Quote, Gewinn in Einsätzen und die
  Rendite je Tipp in % des Einsatzes mit HAC-Intervall (`roi.mean`, `roi.lower_bound`, chronologisch). Eine
  Schlussquote ist dafür nicht nötig.
- Jede Zeile muss zu Endstand und Quote passen (Ergebnis aus dem gespeicherten Endstand, Gewinn = Quote − 1 bzw.
  −1); eine widersprüchliche Zeile zählt als `invalid_rows` und sperrt das Urteil.
- Vergleich mit dem Markt: `market.hit_rate` gegen `market.market_hit_rate`, die mittlere No-Vig-Wahrscheinlichkeit
  der getippten Seite zur Öffnung aus dem Edge-Cap-Protokoll.
- Hybrid gegen Legacy: `hybrid_cohort.results` und `hybrid_cohort.paired_results` (Rendite-Differenz je Spiel,
  hybrid minus legacy, HAC).
- `verdict` folgt den Ergebnissen (`_result_verdict`); das bisherige CLV-Urteil steht als `clv_verdict` daneben.
  Schlussquote, CLV und No-Vig-CLV werden weiter mitgeschrieben, entscheiden aber nichts.
- Tipp-Auswahl, Öffnungsregel und Policy-Version (`shadow-model-first-v9`) bleiben unverändert; die Zählung
  beginnt mit den v9-Zeilen vom 30.10.2026.

## Hypothese und Prüfung

Vor der ersten abgerechneten v9-Zeile festgelegt (Bibel §3.5): Eine Freigabediskussion gibt es erst nach
**1000 abgerechneten Tipps** derselben Modell- und Policy-Version (`SHADOW_REVIEW_MIN_SETTLED`); als Beleg gilt nur
eine untere Grenze der Rendite je Tipp über 0. Begründung der Zahl: Bei Quoten um 1,6 streut die Rendite je Tipp
um etwa 78 % des Einsatzes; um einen Vorteil von rund 4 % von Zufall zu trennen (einseitig 95 %), braucht es
grob 1000 Tipps, für 3 % fast 2000. Ergebnisse streuen stärker als CLV, deshalb mehr als die bisherigen 300
CLV-Paare. Bei heute 1 bis 3 Tipps pro Tag dauert das lange; mehr Tipps je Tag sind der eigentliche Hebel.
