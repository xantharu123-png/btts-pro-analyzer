# Länderspiel-Modell reparieren: Kandidat 2 vorab

Stand 16.11.2026, geschrieben **vor** jeder Rechnung mit Kandidat 2. Owner: „Ja, Kandidat 2“.

## Ausgangslage

Kandidat 1 (`dixon_coles_hl365`) war nicht rechenbar
(`docs/audits/2026-11-16-laenderspiele-reparatur-ergebnis.md`):

- Der Dixon-Coles-Fit erlaubt höchstens 64 Mannschaften mit je mindestens 4 Spielen.
- Der Länderspiel-Pool hat im Fenster 109 Mannschaften, 42 davon mit weniger als 4 Spielen.
- Kandidat 1 lieferte deshalb keine einzige Vorhersage. Es gibt also keine Ergebnisdaten, die Kandidat 2 beeinflussen
  könnten.

## Kandidat 2 (einer, fest)

Kandidat 2 ist `dixon_coles_hl365` mit zwei Anpassungen an die Daten von Länderspielen. Halbwertszeit 365 Tage, kein
Niveau-Prior, Heimvorteil wie bisher, ausser bei unbekanntem Spielort. Gilt nur für Länderspiele
(`senior_national_pooled`).

1. **Teamfilter:** Der Fit nutzt nur Spiele in seinem 730-Tage-Fenster, in denen beide Mannschaften mindestens 4 Spiele
   haben (`MIN_TEAM_MATCHES`). Der Filter wird wiederholt, bis sich nichts mehr ändert, weil ein entferntes Spiel einer
   anderen Mannschaft Spiele nehmen kann.
2. **Grenze der Mannschaftszahl** 160 statt 64 (`MAX_TEAMS`). Das ist eine Rechengrenze, kein Modellparameter.

Steht eine Mannschaft des Spiels nach dem Filter nicht im Fit, gibt es keine Vorhersage. Das ist geschlossenes
Scheitern wie beim bisherigen Dixon-Coles-Pfad.

Kein Modellparameter wird neu eingestellt. Halbwertszeit, Mindestspiele und Kalibrierung bleiben wie in der
Produktion beziehungsweise wie bei Kandidat 1.

## Daten, Rechnung, Kriterien

Unverändert wie in `docs/audits/2026-11-16-laenderspiele-reparatur-vorab.md`:

- derselbe Pool von 1243 Spielen
- dieselbe kausale Rechnung wie `_walk_forward_market_records`
- Zeitraum A vom 01.01.2024 bis 03.10.2026 und Zeitraum B ab dem 04.10.2026
- dieselben vier Kriterien K1 bis K4:
  - **K1:** Lücke für „Favorit gegen Kleinstaat höchstens 2 Tore“ zwischen −5 und +5 Punkten, das
    95-%-Intervall enthält null
  - **K2:** Kontrolle höchstens 0,002 Brier schlechter
  - **K3:** Gesamt-Brier in A nicht schlechter
  - **K4:** Brier in B höchstens 0,005 schlechter
- K1 bis K4 werden auf den Spiel-Markt-Paaren gerechnet, für die beide Modelle eine Vorhersage haben.

**Zusatzbedingung K0:** Kandidat 2 muss für mindestens 90 % der Kleinstaaten-Spiele in Zeitraum A eine Vorhersage
liefern. Sonst gilt er als nicht anwendbar.

## Entscheidung

- **Alle Kriterien erfüllt:** Ich schlage vor, Länderspiele auf Kandidat 2 umzustellen und die Sperre im selben Release
  aufzuheben. Das ist ein eigener Owner-Entscheid.
- **Ein Kriterium verfehlt:** Keine Umstellung, die Sperre bleibt. Ein weiterer Kandidat braucht wieder eine eigene
  Vorab-Regel.
- Diese Regeln werden nach dem Blick auf die Zahlen nicht geändert.
