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

## Release 20261116-2

Owner „Ja, live stellen“ am 16.11.2026.

- **Merge:** PR #133 um 09:08 CET, `origin/main` = `fb38329378de11e96bfa7990ce2e7f8d8c91d5c6`. Die CI war grün. Der
  Baum ist gleich dem PR-Stand `68660fc`.
- **Dateien:** 7 von `2b572e0` bis `fb38329`. Code ist nur `ev_signal_sources.py`; dazu der Tennis-Testfix aus PR #131,
  Tests und Doku. Keine Einheit, kein `.sh`, keine Requirements.
- **Generator:** `output/release-20261116-2/gen_deploy56.py`, abgeleitet von `gen_deploy55.py` über `make_gen.py`.
  Neue Asserts: `small_nation_under_blocked` vorhanden, 15 Kleinstaaten, die Sperre am Rückgabepunkt des Laders,
  Kazakhstan–Slovakia „AWAY_UNDER_2_5“ gesperrt, ein Vereinsspiel nicht.
- **Offline-Prüfung lokal** gegen einen Worktree von `68660fc` (gleicher Baum): `OFFLINE_RELEASE_IMPORTS=ok`.
- **Hochladen:** sha256 auf dem Server gleich (`deploy-20261116-2.sh` `31b707f6…`, `run_release-20261116-2.sh`
  `aaa94a60…`).
- **Erster Versuch** um 09:12:43: abgebrochen mit `TIMER_TOO_CLOSE=betboy-quotes`, weil der Quotenlauf um 09:15
  anstand. Der Server blieb auf `2b572e0`. Log `output/release-20261116-2/deploy-01.log`.
- **Zweiter Versuch:** Fenster um 09:15:37 (Abstand zum nächsten Shadow-Lauf 383 s). Ergebnis `HEAD=fb38329…`,
  `APP_PID=1644442->1650913`, `NO_NEW_BACKUP=yes`, `UNITS_UNCHANGED=yes`, `DEPLOY_EXIT=0`. Log `deploy-02.log`.
- **Danach:** Health lokal und öffentlich `ok`, App, Caddy und alle 7 Timer aktiv, keine neue fehlgeschlagene
  Einheit. Der Lader liefert mit dem Live-Code 158 statt 160 Prognosen, es bleibt keine gesperrte Zeile.
  Kazakhstan–Slovakia und Estonia–Bulgaria haben keinen „AWAY_UNDER_2_5“ mehr; die übrigen Märkte bleiben.
