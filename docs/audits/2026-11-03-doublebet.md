# Doublebet: bis zu drei Wetten am Tag um Quote 2,00, die wahrscheinlichsten laut Modell

Datum: 03.11.2026. Owner-Entscheid im Chat: „3 a day“ wird zu „Doublebet“. Statt der defensiven Auswahl
(mindestens 70 % Modellwahrscheinlichkeit, dreifacher Vergleich) nimmt die Tagesauswahl Wetten mit Quote um 2,00
und wählt daraus die wahrscheinlichsten. Die Frage des Owners „ist 1,70 wirklich wahrscheinlicher als 3,20?“ war der
Anlass: Bei fester Quote sagt der Buchmacher zu allen Kandidaten dasselbe, und die Rangfolge im Band kommt allein
vom Modell. Das ist auch messbar: Liegt die Trefferquote über Monate bei rund 50 %, bringt das Modell nichts; liegt sie
darüber, sieht man es, weil die Quote immer gleich ist.

## Regel (Policy `doublebet-odds-around-2-most-probable-v14`)

- Kandidaten sind alle Prognosen des Wettfinder-Pools mit aktueller Preisprüfung und zugelassener Quote
  (`publication_quote`: innerhalb 24 Stunden beobachtet, Median ab 1,20), deren **Median zwischen 1,80 und 2,20**
  liegt (`DOUBLEBET_ODDS_MIN`, `DOUBLEBET_ODDS_MAX`). „Um 2,00“ ist damit ±0,20; eine Setzung dieser Umsetzung.
- Alle Sportarten und Wettarten des Wettfinders, eine Auswahl je Spiel, keine Wettartenverbote. Kontext-Vetos
  (`_explanation`) gelten weiter; Spiele müssen heute und nach dem Planungsstand beginnen und mit ihrem
  Planungsabstand vor Mitternacht Zürich enden (`fits_daily3_window`).
- Gewählt wird die **Tagesfolge von bis zu drei Wetten mit der höchsten Summe der Modellwahrscheinlichkeiten**
  (`_best_sequence`). Eine Folge heisst: die nächste Wette beginnt erst nach dem Planungsabstand der vorherigen
  (3 Stunden Fussball/Basketball/Eishockey, 4 Stunden Tennis/E-Sport) und überschneidet sich nicht mit ihr. Weil
  Wahrscheinlichkeiten positiv sind, schlägt eine längere machbare Folge immer eine kürzere. Gleichstand: frühere
  erste Wette, dann feste Schlüssel.
- Die 70-%-Grenze (`MIN_MODEL_PROBABILITY`) und der Pflicht-Vergleich sind entfernt. Form- (Fussball) und
  Belagvergleich (ATP) werden weiter berechnet und an der Karte als Hinweis gezeigt, wenn sie belegt sind; ein
  falscher oder fehlender Vergleich blendet nichts aus und erfindet nichts.
- Unverändert: CHF 50 Tagesbudget, manuelle Erfassung, Mindestquote 1,20 für die Vormerkung, Rückzahlungen erst nach
  endgültiger Abrechnung, Ziel +CHF 150 ohne Garantie.

## Umbenennung

- Anzeige: Reiter „Doublebet“ statt „3 a day“, Kopf „Doublebet“, Kachel „DOUBLEBET“, Knöpfe und Hinweise.
- Intern bleiben die Namen (`daily3_*`-Module, Feature `daily3`, Datenbank `daily3.db`, Archive `daily3_rail` und
  `daily3_default_plan`), damit gespeicherte Wetten, Berechtigungen und Auswertungen weiterlaufen. Die Policy-Version
  in den Aufzeichnungen wechselt auf v14; ältere Tage sind nicht vergleichbar.

## Folgen

- Es gibt öfter drei Wetten als bisher, jede trifft aber nur in rund 45–56 % der Fälle. Zwei oder drei Verlierer am
  Tag sind normal; die erwartete Rendite bleibt bei einem Modell auf Marktniveau etwa bei minus Marge, mit grösserer
  Schwankung als bei Favoriten zu 1,20–1,45.
- Die Auswertung (`consumer_tip_performance`, Aufzeichnungen unter `daily3_default_plan`) misst die Trefferquote
  gegen 50 %; das ist der Massstab, ob das Modell im Band etwas erkennt.
- Tests: Die Daily3-Suiten prüfen jetzt das Band und die Folge; Tests, die einen falschen Vergleich über den
  Ausschluss aus der Auswahl prüften, prüfen ihn jetzt über `choice.comparison is None`.

## Korrektur 05.11.2026: Tageskontext gilt 24 Stunden, nicht 75 Minuten

Befund aus dem Doublebet-Audit vom 5.11. (`output/check-20261104/doublebet_why.log`): Um 09:02 war AZ Alkmaar – Juventus
gewählt, um 10:27 gab es keine Doublebet-Auswahl mehr. Der App-Lader markiert einen Fussball-Kontext 75 Minuten nach
der Prüfung als veraltet (`context_stale`, `FOOTBALL_CONTEXT_MAX_AGE`). `football_context_highlight_reason` verwarf
dann jede Auswahl, obwohl Doublebet für automatische Tagesprognosen eine Lebensdauer von 24 Stunden übergibt
(`DAILY_MODEL_HIGHLIGHT_MAX_AGE`) und jede einzelne Prüfung innerhalb dieser Zeit lag. Die Kontextprüfung läuft nur im
Tageslauf (03:35); Fussball-Auswahlen waren deshalb ab etwa 05:30 verschwunden, tagsüber blieben nur Tennis und E-Sport.

Owner-Entscheid „Ja, beheben“: Bei einer Tageslebensdauer prüft die Kontextregel die Uhrzeit jeder einzelnen Prüfung
gegen diese Lebensdauer und ignoriert das 75-Minuten-Flag. Widersprüchliche Prüfungen blockieren weiter, ebenso
gesperrte Aufstellungen und Vetos. Aufrufer mit dem 75-Minuten-Fenster (Top-Hervorhebung im Wettfinder, RisikoBet)
bleiben unverändert. Test: `test_daily_choice_survives_the_75_minute_stale_flag_but_top_window_does_not`.
