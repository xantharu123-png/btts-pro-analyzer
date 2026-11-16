# Plan: Länderspiel-Modell bis März 2027

Stand 16.11.2026. Owner: „Bis März planen“.

## Ausgangslage

- **Fehler bestätigt** (vorab festgelegt): Gegen Kleinstaaten gibt das Länderspiel-Modell dem Favoriten zu wenige
  Tore. „Favorit höchstens 2 Tore“ kam zu 58,4 % vor, das Modell rechnete mit 78,1 % (n 197;
  `docs/audits/2026-11-16-laenderspiele-kleinstaaten-ergebnis.md`).
- **Sperre live seit 16.11.2026 09:15:** keine Unter-Tor-Tipps in Länderspielen gegen Kleinstaaten
  (`docs/audits/2026-11-16-kleinstaaten-sperre.md`). Zwischen den Fenstern wirkt sie nicht; sie bleibt bis zu einer
  bestandenen Prüfung.
- **Kandidaten 1 bis 3, alle nicht erfüllt:**
  - **Kandidat 1 und 2:** Dixon-Coles, nicht rechenbar, weil die Engine es bei Länderspielen ausschliesst.
  - **Kandidat 3** (multiplikativ statt additiv):
    - Insgesamt besser: Brier im Zeitraum A 0,2002 → 0,1970, im getrennten Zeitraum B 0,1901 → 0,1876.
    - Die Kleinstaaten-Lücke schliesst er nur von −19,7 auf −16,3 Punkte.
    - Berichte: `docs/audits/2026-11-16-laenderspiele-reparatur-*.md`.

## Ziel

Ein Länderspiel-Modell, das die Tore des Favoriten gegen Kleinstaaten richtig einschätzt, ohne Länderspiele insgesamt
schlechter vorherzusagen. Entscheidung und Release vor dem Länderspielfenster im März 2027.

## Lehre aus dieser Runde

Kandidat 3 und alle Diagnosen haben den Zeitraum 2024 bis 2026 schon gesehen. Für den nächsten Kandidaten werden die
Daten deshalb strikt getrennt, bevor irgendetwas angesehen wird:

- **Entwurfsdaten:** Länderspiele bis 30.06.2025. Nur hier sind Diagnosen erlaubt: Kalibrierung, Schrumpfung,
  Gegnerstärke, Wahl der Bauweise.
- **Prüfdaten:** 01.07.2025 bis 18.11.2026. Sie werden genau einmal angesehen, nach der Vorab-Regel.
- Gibt es zu wenige Kleinstaaten-Spiele in den Prüfdaten (Grenze vorab, zum Beispiel 60), ist das Ergebnis
  „nicht prüfbar“.

## Schritte

1. **Daten neu holen:** 13 API-Abrufe wie am 16.11.2026, mit Owner-OK. Die Rohdaten in `/tmp` überleben keinen
   Neustart des Servers.
2. **Diagnose nur auf Entwurfsdaten:** Wo geht die Information verloren?
   - in der Paarung (additiv)
   - in der Schrumpfung (Gewicht 6 zum Gesamtschnitt)
   - in der fehlenden Gegnerbereinigung (eine Torquote gegen San Marino zählt wie eine gegen Spanien)
   - in der täglichen Kalibrierung, die extreme Werte zurückzieht
3. **Kandidat 4 festlegen.** Ein Kandidat, als Vorab-Regel mit Commit vor der Prüfung. Naheliegend ist die
   multiplikative Paarung aus Kandidat 3 mit gegnerbereinigten Stärken: einige Iterationen „Tore im Verhältnis zur
   Abwehrstärke des jeweiligen Gegners“ innerhalb von `_senior_national_fixture_model`. Mannschaften mit zu wenigen
   Spielen bekommen keine Vorhersage. Die genaue Bauweise folgt aus Schritt 2.
4. **Prüfung auf den Prüfdaten** mit den Kriterien K0 bis K4 wie bisher. Die Grenzen werden in der Vorab-Regel neu
   gesetzt, bevor die Prüfdaten angesehen werden.
5. **Owner-Entscheid:** Besteht Kandidat 4, wird er in der Produktion mit eigener Prognose-Version umgestellt, und die
   Sperre fällt im selben Release. Besteht er nicht, bleibt die Sperre über den März.

## Zeitplan

| Bis | Was |
|---|---|
| Mitte Dezember 2026 | Daten, Diagnose auf Entwurfsdaten, Vorab-Regel Kandidat 4 committet |
| Ende Januar 2027 | Prüfung, Bericht, Owner-Entscheid |
| Ende Februar 2027 | Release, falls bestanden, mit Aufheben der Sperre |

## Grenzen

- **Kleine Stichprobe:** Die Prüfdaten enthalten nur rund 1,5 Jahre Länderspiele, also wenige Kleinstaaten-Spiele je
  Fenster.
- **Kein Marktvergleich:** Für alte Spiele fehlen Marktquoten. Ab dem März-Fenster lassen sich Modell und Markt
  vergleichen, die Evidenz speichert die Einstiegsquoten.
