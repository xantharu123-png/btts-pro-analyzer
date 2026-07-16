# Smart Bet Finder

Der Smart Bet Finder trennt Modell und Marktpreis strikt voneinander.

## Begriffe

- **Modell-Signal:** Eine Modellwahrscheinlichkeit ohne Aussage zu Quote, EV oder Einsatz.
- **Modellpreis:** `1 / Modellwahrscheinlichkeit`; weder Buchmacherquote noch Nachweis eines fairen Preises.
- **Verifizierte Quote:** Eine valide, frische Dezimalquote mit Bookmaker, Quelle, Zeitstempel und exakter Fixture-Zuordnung.
- **Value Bet:** Nur ein kalibrierter Markt mit verifizierter Quote und positivem Mindest-Edge.

## Harte Gates

`find_value_bets()` liefert nur dann ein Ergebnis, wenn alle Bedingungen erfüllt sind:

1. `market_validation` dokumentiert einen chronologischen Out-of-sample-Test mit Start, Ende, Modellversion und Liga-Scope.
2. Die Modellwahrscheinlichkeit liegt zwischen 0 und 100 Prozent.
3. Eine externe Quote ist vorhanden, endlich und größer als `1.0`.
4. Die Quote ist höchstens zehn Minuten alt und einem Bookmaker, einer Quelle und dem richtigen Match zugeordnet.
5. Alle Seiten desselben Marktes sind beim gewählten Bookmaker vorhanden und der Overround liegt zwischen `0.98` und `1.25`.
6. Die maximale historische Kalibrierungsabweichung wird von der Modellwahrscheinlichkeit abgezogen.
7. Erst der risikoadjustierte Edge überschreitet den konfigurierten Mindestwert und sein EV sowie Kelly sind positiv.

Fehlt eine Bedingung, gibt es kein Value-Bet, keinen EV und keinen Einsatz.

## Mathematik

```text
Implied Probability = 1 / Decimal Odds
Edge (Prozentpunkte) = Model Probability - Implied Probability
Expected ROI = Model Probability * Decimal Odds - 1
Staking Probability = Model Probability - Max Calibration Error
Risk-adjusted EV = Staking Probability * Decimal Odds - 1
Full Kelly = (b*p - q) / b
```

Das System nutzt Viertel-Kelly und begrenzt den Einsatz auf maximal 2 Prozent
der Bankroll. Kelly verwendet die risikoadjustierte Wahrscheinlichkeit, nicht
die optimistischere Punktschätzung. Ein nicht-positiver Kelly-Wert führt zu
`NO BET`.

## Kalibrierung

Eine hohe Einzelwahrscheinlichkeit ist noch kein Beleg für ein gutes Modell.
Ein Markt ist nur zugelassen, wenn sein Eintrag in `market_validation`
mindestens 200 Out-of-sample-Beobachtungen, `ECE < 0.05`, maximale
Bin-Abweichung `< 0.10`, mindestens drei Bins mit je mindestens 20
Beobachtungen, Methode und Modellversion dokumentiert. Das Validierungsende
muss vor dem neuen Fixture liegen und dessen Liga muss im getesteten Scope
enthalten sein. Zusätzlich soll der chronologische Test Folgendes dokumentieren:

- Stichprobengröße und Zeitraum
- Brier Score gegen eine naive Baseline
- Kalibrierung nach Wahrscheinlichkeits-Bins
- Marktdefinition und Settlement-Regeln
- Historische Quote zum Vorhersagezeitpunkt
- CLV und ROI ohne Survivorship- oder Look-ahead-Bias

Die maximale Bin-Abweichung ist ein empirischer Haircut und ausdrücklich kein
formales Konfidenzintervall.

## Kombis

Same-Match-Combos sind deaktiviert. Marginale Wahrscheinlichkeiten dürfen nur
multipliziert werden, wenn Unabhängigkeit belegt ist. Fußballmärkte wie Ergebnis,
Tore, Karten und Ecken sind regelmäßig abhängig.

Auch Einzelwetten desselben Fixtures sind korreliert. Deshalb erhält nur der
risikoadjustiert beste Markt eines Fixtures eine Einsatzempfehlung.

## Konfiguration

Die Schlüssel werden über Umgebungsvariablen, Streamlit Secrets oder
`config.ini` geladen:

```ini
[api]
api_football_key =

[odds]
api_key =
```

Secrets gehören nicht ins Repository. Bei einem früher veröffentlichten
Schlüssel muss der Schlüssel beim Anbieter rotiert werden.
