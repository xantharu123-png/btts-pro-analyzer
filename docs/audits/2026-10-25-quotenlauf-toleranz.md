# Betriebsänderung 25.10.2026: Fälligkeitstoleranz im Quotenlauf

Owner-Entscheidung vom 25.10.2026 abends (Gesamtaudit `AUDIT_BERICHT_2026-10-25_CLAUDE.md`, Befund D2,
erster Teil von Massnahme 3). Betroffen ist nur der Zeitplan des Quotenlaufs (`betboy-quotes.timer`,
`wettfinder_automation._refresh_price_document` und der Team-/E-Sport-Zweig in
`_refresh_scheduled_prices`); keine Preisregel, kein Modell, keine Veröffentlichung ändert sich.

## Befund

Der Timer feuert alle drei Stunden (`OnCalendar=*-*-* 00,03,…,21:15:00 Europe/Zurich`). Der Quotenlauf
prüft eine Zeile nur, wenn ihr letzter Versuchsstempel mindestens `SCHEDULED_PRICE_MIN_GAP` (drei
Stunden) zurückliegt. Der Stempel trägt aber die Uhr beim Start des jeweiligen Sportzweigs, also rund
30 Sekunden nach dem Timer (Laden des 22-MB-Dokuments, Importe). Der Folgelauf startet drei Stunden nach
dem Timer und misst damit 2 h 59 min 30 s seit dem Stempel: nichts fällig. Erst der übernächste Lauf
prüft wieder. Am 25.10.2026 geprüfte Fussballzeilen je Lauf: 06:15 154, 09:15 464, 12:15 0, 15:15 270,
18:15 0. Für die öffentlichen Tipps hiess das Quoten von bis zu sechs Stunden Alter, für die neue
dreistufige Preisprüfung (`docs/audits/2026-10-25-preispruefung-dreistufig.md`) verspätete Schranken.

## Änderung

- `SCHEDULED_PRICE_DUE_TOLERANCE = 15 min`, `SCHEDULED_PRICE_DUE_GAP = 3 h − 15 min = 2 h 45 min`.
- Fällig ist eine Zeile, sobald `SCHEDULED_PRICE_DUE_GAP` seit ihrem Stempel vergangen ist. Das gilt
  für Fussball und Tennis (`_refresh_price_document`, `_tennis_price_check_candidates` über
  `min_gap`) und für den Team-/E-Sport-Zweig (`prices:<sport>`-Stempel).
- `SCHEDULED_PRICE_MIN_GAP` bleibt als nominale Taktung erhalten. Manuelle Läufe (`scheduled=False`)
  waren und sind nicht gedrosselt.

## Was das bedeutet

- Jeder Lauf prüft, nicht jeder zweite: Quoten der öffentlichen Tipps sind höchstens drei statt sechs
  Stunden alt, und die 15-Minuten-Toleranz kann den Dreistundentakt nie auf zwei Läufe binnen 2 h 45 min
  verkürzen, weil der Timer fest steht.
- Kosten: etwa doppelt so viele Quotenabrufe am Tag. Nach den Läufen vom 25.10. grob 400 bis 500
  zusätzliche API-Football-Aufrufe bei 7 500 im Pro-Kontingent; der Budgetwächter (`api_budget`)
  bleibt unverändert davor.
- Offen aus D2: Budgetschutz als eigener Status `budget_deferred` statt Exit 1, `OnFailure=`-Alarm
  und `Persistent=true` für die Timer, Tennis-Fallausschluss (Codex).

## Umsetzung und Tests

`wettfinder_automation` (Konstanten, drei Vergleichsstellen). Tests in
`tests/test_price_refresh_schedule.py`: Drosselung bis 2 h 44 min, fällig ab 2 h 46 min; neuer Test mit
dem Muster vom 25.10. (Stempel 31 s nach dem Timer, Folgelauf drei Stunden nach dem Timer) für Fussball,
Tennis, Teamsport und E-Sport.
