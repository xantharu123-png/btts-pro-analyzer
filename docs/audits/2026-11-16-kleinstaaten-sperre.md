# Sperre: keine Unter-Tipps in Länderspielen gegen Kleinstaaten

Stand 16.11.2026. Owner „Beides“: jetzt sperren, das Modell reparieren.

## Anlass

Die Vorab-Prüfung hat bestätigt, dass das Modell in A-Länderspielen gegen einen Kleinstaat dem Favoriten zu wenige
Tore gibt. In 197 Spielen kam „Favorit höchstens 2 Tore“ zu 58,4 % vor, das Modell rechnete mit 78,1 %; gegen San
Marino, Liechtenstein, Gibraltar und Andorra kam es nur zu 34,1 % vor. Belege:
`docs/audits/2026-11-16-laenderspiele-kleinstaaten-vorab.md` und `docs/audits/2026-11-16-laenderspiele-kleinstaaten-ergebnis.md`.

Eine saubere Reparatur braucht eine eigene Prüfung auf getrennten Daten. Sie wird nicht fertig, bevor das
Länderspielfenster am 18.11.2026 endet. Die Sperre überbrückt diese Zeit.

## Regel

`ev_signal_sources.small_nation_under_blocked` gilt für eine Prognose, wenn alle drei Bedingungen erfüllt sind:

- Sie gehört zum Länderspiel-Modell (`model_scope = senior_national_pooled`).
- Genau eine Mannschaft steht auf der vorab festgelegten Kleinstaaten-Liste (`SMALL_NATIONS`, gleiche Liste wie in
  der Prüfung).
- Der Markt ist ein Unter-Tor-Markt: Gesamttore unter (`TOTAL_UNDER_…`), eine Kombination mit unter
  (`RESULT_TOTAL_…_UNDER_…`) oder unter für die Tore des Favoriten (`HOME_UNDER_…` oder `AWAY_UNDER_…`).

Der Lader `automated_wettfinder_forecasts` lässt diese Prognosen weg (`without_small_nation_unders`). Dadurch zeigen
Wettfinder, Doublebet und die Tipp-Archive sie nicht.

## Unverändert

- Die Prognosen selbst, die Evidenz und die Abrechnung. Der Nachtlauf speichert jede Zeile weiter, so läuft die
  Messung weiter.
- Shadow, RisikoBet und alle Vereinsspiele.
- Tore des Kleinstaats, Über-Märkte, Tor-Bereiche, Ergebnisse und Ecken.
- Spiele zwischen zwei Kleinstaaten und Spiele ohne Kleinstaat.

## Wirkung am 16.11.2026

Trockenlauf auf dem Live-Dokument, nur gelesen. Von 160 Prognosen sind 126 aus Länderspielen. Gesperrt würden 2:

- Kazakhstan gegen Slovakia: „Slovakia unter 2.5 Tore“, 76 %
- Estonia gegen Bulgaria: „Bulgaria unter 2.5 Tore“, 95 %

## Prüfung

`tests/test_small_nation_block.py`:

- Gesperrt sind die Unter-Märkte des Favoriten, Gesamt-unter und Kombinationen mit unter, auch bei auswärts
  spielendem Favoriten.
- Erlaubt bleiben die Tore des Kleinstaats, Über-Märkte, Bereiche, Kombinationen ohne unter und Ecken.
- Nicht betroffen sind Spiele zwischen zwei Kleinstaaten, Spiele ohne Kleinstaat und Vereinsspiele.
- Die Liste ist dieselbe wie in der Vorab-Prüfung.
- Der Lader wendet die Sperre an seinem einzigen Rückgabepunkt an.

## Aufheben

Wenn das reparierte Länderspiel-Modell seine eigene Prüfung besteht, wird die Sperre in demselben Schritt entfernt:
den Aufruf in `automated_wettfinder_forecasts` und die Hilfsfunktionen löschen.
