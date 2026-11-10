# Ergebnisse auch im Quotenlauf abrechnen, neueste Spiele zuerst

Stand 10.11.2026. Owner-Frage: „die Fussballspiele waren gestern, also Montag, wir haben Dienstag, die sollten doch
abgerechnet sein?“ Danach Owner „Ja, beheben“.

## Befund

- **Nur einmal pro Nacht:** `run_forecast_evidence_settlements` lief nur im Nachtlauf
  (`run_wettfinder`, Stufe `forecast_results`), mit höchstens 40 Spielen je Sportart (`MAX_EVENTS_PER_SPORT`).
- **Rotation für den falschen Takt:** Die Auswahl rotierte für einen Takt von 30 Minuten (`ROTATION_SECONDS`). Bei
  nur einem Lauf pro Tag blieben nach einem grossen Spieltag neue Spiele liegen.
- **Lauf vom 10.11.2026, 03:43:**
  - Die Grenze war erreicht (`football:event_budget_reached`).
  - Abgerechnet wurden Spiele vom 7. und 8.11., die vier Fussballspiele vom 9.11. nicht.
  - Danach blieben 24 Fussballspiele offen, 11 davon vom 1. bis 8.11. Dazu kamen 26 Tennisspiele, die meisten aus
    dem September.

## Änderung

- **Neueste Spiele zuerst:**
  - Spiele mit Anstoss in den letzten 72 Stunden (`RECENT_KICKOFF_WINDOW`) kommen zuerst dran.
  - Sind es allein mehr als 40, rotieren sie wie bisher.
  - Ältere offene Spiele (verschoben, abgebrochen, Identität ungeklärt) bekommen nur noch die übrigen Plätze, rotierend.
- **Auch im Quotenlauf:**
  - Jeder Quotenlauf (`refresh_prices_only`, alle drei Stunden) rechnet zusätzlich ab, mit demselben Anbieter und
    demselben Capture-Worker wie der Nachtlauf (`_settle_forecast_evidence`).
  - Die Abrechnung läuft unter der Publikationssperre und kann sich deshalb nicht mit dem Nachtlauf überschneiden.
  - Die Zusammenfassung erscheint kompakt im Protokoll des Quotenlaufs (`evidence_settlement`), nicht im Snapshot.
  - Offene Ergebnisse sind Datenstatus. Nur ein Absturz der Abrechnung zählt als Betriebsfehler des Quotenlaufs.
- **Kosten:** je Quotenlauf ein bis zwei Detailabrufe für bis zu 40 Spiele. Statistikabrufe für Ecken und Karten
  braucht es nur einmal je beendetem Spiel, wie bisher.

## Prüfung

- **Neue Tests:**
  - `test_recent_kickoffs_are_checked_before_long_unresolved_events`
  - `test_long_unresolved_events_still_use_the_remaining_budget`
  - `test_every_quotes_run_also_collects_results` (abgeschlossen und abgestürzt)
  - `test_test_snapshot_without_injected_runner_collects_no_results`
- **Lokale Läufe:** Alle 17 Testdateien, die Abrechnung oder Quotenlauf berühren, laufen grün (632 Tests).
- **Zwei Fehlschläge, die schon vorher bestanden:** Sie scheitern auch auf dem unveränderten `main` `5b14359`.
  - `test_active_15k_model_surface_obeys_bound_floor_before_slot_selection[1.2-True]`
  - `test_production_stages_preserve_document_order_and_private_callbacks` (Folgetag-Suche in der erwarteten
    Reihenfolge)
