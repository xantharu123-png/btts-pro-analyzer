# Länderspiele gegen Kleinstaaten: Hypothese vorab

Stand 16.11.2026, geschrieben **vor** jedem Blick auf die Prüfdaten. Owner: „Ja, festhalten und prüfen“.

## Anlass

Am 15.11. trafen die Fussballtipps nur 47 % bei 58 % Erwartung. Finnland gegen San Marino ging 0 von 4 aus:
Finnland schoss mindestens 5 Tore, das Modell gab „Finnland höchstens 2 Tore“ 60 %.

Der Befund, auf dem die Hypothese beruht, war nur gelesen, auf den Länderspiel-Prognosen vom 04.10. bis 15.11.2026:

- Über 75 Spiele und 381 Prognosen ist das Modell insgesamt kalibriert: 65,6 % Treffer bei 65,0 % Erwartung.
- Gegen San Marino gibt es dem Favoriten deutlich weniger Tore als der Markt. Für „Favorit höchstens 2 Tore“
  rechnete es bei Albanien 58 % (Markt etwa 27 %) und bei Finnland 60 % (Markt etwa 33 %).
- Für „Heimteam höchstens 2 Tore“ liegt die Modellchance in diesen 75 Spielen nie unter 50 %.

Diese Daten erzeugen die Hypothese. Sie dürfen sie nicht prüfen.

## Hypothese

**H1:** In A-Länderspielen gegen einen Kleinstaat unterschätzt das Modell die Tore des Favoriten. Gemessen am
Markt „Favorit höchstens 2 Tore“ ist die beobachtete Häufigkeit mindestens 10 Prozentpunkte niedriger als die
mittlere Modellchance.

**H1b (zweitrangig):** Gegen die vier kleinsten (San Marino, Liechtenstein, Gibraltar, Andorra) ist die Lücke
grösser als gegen die übrigen Kleinstaaten.

**Kontrolle:** In Länderspielen ohne Kleinstaat ist die Lücke für „Heimteam höchstens 2 Tore“ nahe null.

**Kleinstaaten (fest):** San Marino, Liechtenstein, Gibraltar, Andorra, Malta, Moldova, Faroe Islands, Luxembourg,
Kazakhstan, Latvia, Lithuania, Estonia, Armenia, Azerbaijan, Cyprus (Namen wie bei API-Football). Ein Spiel zählt,
wenn genau eine Seite auf der Liste steht. Der Favorit ist die andere Seite.

## Prüfdaten

- **Quelle:** A-Länderspiele aus den Wettbewerben, aus denen das Modell lernt (`NATIONAL_HISTORY_LEAGUES`:
  Nations League 5, WM-Qualifikation Europa 32, Freundschaftsspiele 10, WM 1). Abgeschlossene Spiele (`FT`),
  gefiltert wie in der Produktion: nur A-Teams (`_senior_national_result`), nur Spiele mit einem Nations-League-Team.
- **Abruf:** einmalig über API-Football, je Wettbewerb und Saison 2022 bis 2026. Das sind höchstens 15 Abrufe über
  die Budgetzählung (`api_budget.api_football_get`), nur nach Owner-OK.
- **Prüfzeitraum:** Anstoss vom 01.01.2024 bis 03.10.2026. Spiele ab dem 04.10.2026 sind ausgeschlossen, weil sie die
  Hypothese erzeugt haben.

## Rechnung

Das Modell wird so nachgerechnet, wie es sich selbst validiert (`challenge_engine._walk_forward_market_records`):

- Die Spiele laufen chronologisch durch. Jedes Spiel wird nur aus den Spielen davor vorhergesagt (wachsendes Fenster).
- Die Kalibrierkarte des Tages kennt nur frühere Tage.
- Basis ist die Produktionsbasis `PRODUCTION_GOAL_MODEL`.
- Die einzige Abweichung von der eingebauten Funktion: Je Spiel werden Spiel-ID und Mannschaften mitgeschrieben,
  damit die Kleinstaat-Spiele auswählbar sind. Rechenweg und Zahlen bleiben unverändert.
- Ausgewertet wird die kalibrierte Modellchance, so wie die Produktion sie zeigt.

## Entscheidungsregel

- **Kennzahl:** beobachtete Häufigkeit minus mittlere Modellchance für „Favorit höchstens 2 Tore“, mit einem
  95-%-Bootstrap-Intervall über Spiele (10 000 Ziehungen, fester Startwert 20261116).
- **H1 bestätigt,** wenn die Lücke mindestens −10 Punkte beträgt und das ganze Intervall unter null liegt, bei
  mindestens 40 Kleinstaat-Spielen.
- **Bei weniger als 40 Spielen** lautet das Ergebnis „nicht prüfbar“, unabhängig von der Lücke.
- **Bestätigt:** Ein Modellvorschlag (Gegnerstärke in Länderspielen) wird ein eigener Owner-Entscheid mit eigener
  Validierung. An diesen Daten wird keine Schwelle eingestellt.
- **Nicht bestätigt oder nicht prüfbar:** Das Modell bleibt, wie es ist. Finnland gegen San Marino gilt als Ausreisser.
- Diese Regeln werden nach dem Blick auf die Daten nicht geändert.
