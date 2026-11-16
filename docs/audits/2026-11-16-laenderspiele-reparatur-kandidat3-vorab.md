# Länderspiel-Modell reparieren: Kandidat 3 vorab

Stand 16.11.2026, geschrieben **vor** jeder Rechnung mit Kandidat 3. Owner: „Ja, Kandidat 3“.

## Ausgangslage

Kandidat 1 und Kandidat 2 waren nicht rechenbar, weil die Engine Dixon-Coles bei Länderspielen ausschliesst
(`docs/audits/2026-11-16-laenderspiele-reparatur-kandidat2-ergebnis.md`). Beide haben keine Ergebnisdaten erzeugt.

Länderspiele laufen über `challenge_engine._senior_national_fixture_model`. Dort rechnet `pair_rates` die
Torerwartung **additiv**:

- Heim: (Angriff Heim + Abwehr Gast) / 2 × Heimfaktor
- Gast: (Angriff Gast + Abwehr Heim) / 2 / Heimfaktor

Angriff und Abwehr sind geschrumpfte Tor- beziehungsweise Gegentorquoten der letzten 12 (Saison) und 6 (Form) Spiele.
Ein Mittelwert dämpft extreme Paarungen. Ein Favorit, der im Schnitt 1,5 Tore schiesst, bekommt gegen eine Abwehr mit
2,8 Gegentoren nur etwa 2,1 erwartete Tore.

## Kandidat 3 (einer, fest)

Kandidat 3 ändert genau eine Rechenregel in `pair_rates`, **multiplikativ statt additiv**, bezogen auf den
Gesamtschnitt des Pools (`prior_goal_mean`):

- Heim: Angriff Heim × Abwehr Gast / Gesamtschnitt × Heimfaktor
- Gast: Angriff Gast × Abwehr Heim / Gesamtschnitt / Heimfaktor

Unverändert bleiben:

- Fenster (12 und 6 Spiele), Schrumpfung (Gewicht 6 und 4) und Heimfaktor
- Mischung 0,75 Saison / 0,25 Form
- Grenzen 0,05 bis 6,0 Tore
- Kalibrierung und alle übrigen Märkte

Ist der Gesamtschnitt nicht positiv, gibt es keine Vorhersage. Es wird kein Parameter neu eingestellt.

## Daten, Rechnung, Kriterien

Unverändert wie bei Kandidat 2 (`docs/audits/2026-11-16-laenderspiele-reparatur-kandidat2-vorab.md`):

- derselbe Pool von 1243 Spielen und dieselbe kausale Rechnung
- Zeitraum A vom 01.01.2024 bis 03.10.2026, Zeitraum B ab dem 04.10.2026
- die Kriterien:
  - **K0:** Abdeckung der Kleinstaaten-Spiele mindestens 90 %
  - **K1:** Lücke für „Favorit gegen Kleinstaat höchstens 2 Tore“ zwischen −5 und +5 Punkten, das
    95-%-Intervall enthält null
  - **K2:** Kontrolle höchstens 0,002 Brier schlechter
  - **K3:** Gesamt-Brier in A nicht schlechter
  - **K4:** Brier in B höchstens 0,005 schlechter

Die Produktionsbasis und Kandidat 3 laufen mit derselben Produktionsbasis (`PRODUCTION_GOAL_MODEL`). Sie
unterscheiden sich nur in dieser einen Regel.

## Entscheidung

- **Alle Kriterien erfüllt:** Ich schlage vor, das Länderspiel-Modell auf Kandidat 3 umzustellen und die Sperre im
  selben Release aufzuheben. Das ist ein eigener Owner-Entscheid. Die Umstellung braucht eine neue Prognose-Version
  für Länderspiele.
- **Ein Kriterium verfehlt:** Keine Umstellung, die Sperre bleibt.
- Diese Regeln werden nach dem Blick auf die Zahlen nicht geändert.
