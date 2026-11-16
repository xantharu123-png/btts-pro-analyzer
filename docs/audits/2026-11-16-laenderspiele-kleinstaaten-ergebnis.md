# Länderspiele gegen Kleinstaaten: Ergebnis

Stand 16.11.2026. Die Prüfung folgt der Vorab-Regel in `docs/audits/2026-11-16-laenderspiele-kleinstaaten-vorab.md`
(Commit `d8aa9d5`, gepusht vor dem Datenabruf).

## Ergebnis

**H1 ist bestätigt.** In Länderspielen gegen einen Kleinstaat gibt das Modell dem Favoriten deutlich zu wenige Tore.

| Gruppe | Spiele | „höchstens 2 Tore“ eingetroffen | Modell | Lücke | 95-%-Intervall |
|---|---:|---:|---:|---:|---:|
| Favorit gegen Kleinstaat (H1) | 197 | 58,4 % | 78,1 % | −19,7 Punkte | −26,5 bis −13,0 |
| gegen die vier kleinsten (H1b) | 41 | 34,1 % | 76,9 % | −42,8 Punkte | −56,6 bis −28,1 |
| gegen die übrigen Kleinstaaten (H1b) | 156 | 64,7 % | 78,4 % | −13,7 Punkte | −21,2 bis −6,3 |
| Kontrolle ohne Kleinstaat (Heimteam) | 426 | 75,8 % | 78,6 % | −2,8 Punkte | −6,8 bis +1,1 |

- **H1:** Die Lücke beträgt mindestens −10 Punkte, das ganze Intervall liegt unter null, und die Gruppe hat 197 statt
  der verlangten 40 Spiele. Damit ist die Hypothese nach der Regel bestätigt.
- **H1b:** Gegen San Marino, Liechtenstein, Gibraltar und Andorra ist die Lücke etwa dreimal so gross wie gegen die
  übrigen Kleinstaaten. Die beiden Intervalle überschneiden sich nicht.
- **Kontrolle:** Ohne Kleinstaat stimmt das Modell. Das Intervall enthält null.
- **Was das heisst:** Das Modell gibt fast unabhängig vom Gegner rund 78 % für „höchstens 2 Tore“. Gegen die vier
  kleinsten traf das nur in 14 von 41 Spielen ein.

## Wie gerechnet wurde

- **Daten:** 13 Abrufe bei API-Football mit Owner-OK („Ja, abrufen“), über die Budgetzählung. Abgerufen wurden die
  Wettbewerbe 5, 32, 10 und 1 in den Saisons 2022 bis 2026, insgesamt 3394 Spiele. Nach dem Filter der Produktion
  (A-Teams, mindestens ein Nations-League-Team) blieben 1243 Spiele.
- **Rechnung:** Kausal, Tag für Tag, mit der Produktionsbasis und der Kalibrierung nur aus früheren Tagen. Das ergab
  894 Vorhersagen, davon 706 im Prüfzeitraum vom 01.01.2024 bis 03.10.2026.
- **Abgleich:** Die mitgeschriebenen Zahlen sind identisch mit `challenge_engine._walk_forward_market_records` für die
  Märkte `HOME_UNDER_2_5`, `AWAY_UNDER_2_5` und `TOTAL_UNDER_3_5`.
- **Abweichung von der Produktion:** Das Fenster wächst. Die Produktion begrenzt die Historie auf 730 Tage.
- **Bootstrap:** 10 000 Ziehungen über Spiele, Startwert 20261116.

## Folgen nach der Vorab-Regel

- Ein Modellvorschlag zur Gegnerstärke in Länderspielen wird ein eigener Owner-Entscheid mit eigener Validierung. An
  diesen Daten wird keine Schwelle eingestellt.
- **Betroffen in der App** sind vor allem Tipps auf „Favorit unter 2,5 Tore“, auf „Gesamt unter 3,5“ und auf
  Kombinationen mit „unter“ in Spielen gegen Kleinstaaten. Die Gegenrichtung („Favorit über …“) unterschätzt das
  Modell ebenso. Sie ist aber selten Tipp, weil das Modell sie unter 50 % sieht.
- Das laufende Länderspielfenster endet am 18.11.2026, das nächste beginnt im März 2027.

## Grenzen

- **Liste der Kleinstaaten:** Sie ist vorab festgelegt, aber grob. Unter den Favoriten sind auch Teams wie
  Nordmazedonien.
- **Nur ein Markt geprüft:** „Favorit höchstens 2 Tore“. Andere Märkte (Gesamttore, Kombis) sind nicht gegen eine
  Vorab-Regel geprüft.
- **Keine Marktquoten:** Für die alten Spiele gibt es sie nicht, ein Vergleich mit dem Markt fehlt hier.
