# NHL-Quoten: Spielplan ab dem Vortag nachschlagen

Stand 10.11.2026. Owner-Frage „wie kann das sein, heute kein Doublebet?“, danach „Ja, prüfen“ und „Ja, beheben“.

## Befund

- **Die Zuordnung:** Um ein NHL-Spiel einer Quote von API-Sports (Hockey) zuzuordnen, schlägt
  `team_sport_prices.refresh_team_sport_prices` die vollen Teamnamen im offiziellen NHL-Spielplan nach
  (`api-web.nhle.com/v1/schedule/{datum}`, `_nhl_names`).
- **Der Fehler:** Als Datum diente der Anstoss in UTC. Der NHL-Endpunkt liefert aber die Woche ab diesem Datum, und
  zwar mit den Spielen unter ihrem nordamerikanischen Datum. Ein Abendspiel beginnt nach Mitternacht UTC und fehlt
  deshalb in dieser Woche. Ergebnis: `native_identity_unbound`, keine Quote.
- **Beleg vom 10.11.2026:**
  - Alle 6 NHL-Spiele der Nacht hatten diese Lücke (`team_sport_quotes.json`).
  - Spiel 2026020288 Ottawa gegen Washington, Anstoss 11.11. 00:00 UTC, steht im NHL-Spielplan unter dem 10.11.
    (`/v1/schedule/2026-11-10`). In der Woche ab 11.11. fehlt es (`/v1/schedule/2026-11-11`).
- **Folge:**
  - Keiner der 83 abgerechneten Eishockey-Tipps vom 07.10. bis 09.11. hatte eine Einstiegsquote
    (`output/quotenluecke-20261110/`).
  - Eishockey konnte deshalb nie in den Doublebet kommen, der eine Quote von 1,80 bis 2,20 braucht.

## Änderung

- **Spielplan ab dem Vortag:** Die App fragt den NHL-Spielplan ab dem Vortag (UTC) ab. Diese Woche enthält beide
  möglichen Daten des Spiels.
- **Unverändert:**
  - Die Abfrage bei API-Sports bleibt beim UTC-Datum.
  - Die Zuordnung bleibt exakt: Spielnummer, Anstoss und Kürzel müssen übereinstimmen.
- **Neuer Test** `test_nhl_game_is_found_under_its_north_american_date`, zuerst rot, dann grün:
  - Nachmittagsspiel und Spiel nach Mitternacht UTC.
  - Der Test bildet den echten Wochen-Endpunkt nach.

## Offen

- **Ob API-Sports Hockey Quoten liefert:** Ob unser Zugang für die laufende NHL-Saison Quoten liefert, zeigt erst der
  erste Quotenlauf nach dem Release. Für Hockey gilt eine eigene Grenze von 100 Abrufen pro Tag (`daily_limit=100`).
- **Zwei Fehlschläge, die schon vorher bestanden:** Sie scheitern auch auf dem unveränderten `main` `09a45bd`.
  - `test_forecast_consumer_reuses_exact_cached_price_without_network`
  - `test_native_conflicting_role_ids_fail_before_any_request`
- **Tennis:** Die heutigen Stockholm-Spiele fanden bei The Odds API kein passendes Ereignis (`IDENTITY_MISMATCH`). Die
  genaue Ursache braucht einen Abruf der Ereignisliste. Dafür ist ein Owner-OK nötig.

## Release 20261110-3

- **Auftrag:** Owner „Ja, live stellen“, PR #111 gemergt (`bae99ee`).
- **Ausrollen:** No-Backup-Fast-forward `fa7205f` → `bae99ee` am 10.11.2026 um 16:32 CET (`output/release-20261110-3/`).
  - Offline-Importprüfung ok, Health ok.
  - Snapshots unverändert, keine Einheit geändert, kein Backup.
- **Quotenlauf 18:15 CET:** Die NHL-Spiele wurden noch nicht neu geprüft. Der letzte Versuch lag 2 Stunden und 59
  Minuten zurück, unter der Sperre von 3 Stunden (`REFRESH_AFTER`).
- **Quotenlauf 21:15 CET:** Exit 0.
  - `team_sports`: 6 Spiele geprüft, 6 zugeordnet, 12 Quoten, keine Lücke, kein Fehler.
  - Beispiel: Ottawa gegen Washington, beste Quote 1,81 und 2,15, je 9 Buchmacher.
  - API-Sports Hockey liefert also Quoten für die laufende Saison.
