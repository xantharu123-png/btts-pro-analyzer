# 28.10.2026 – Massnahme 7 (Teil): Manuelle Suche ohne Quoten, Zürcher Zeit in der Multi-Sport-Suche

Massnahme 7 des Gesamtaudits `AUDIT_BERICHT_2026-10-25_CLAUDE.md`, Owner-Auftrag vom 28.10.2026.
Umgesetzt sind die zwei Punkte, die eine bestehende Owner-Regel verletzten oder falsche Werte
zeigten. Die übrigen Punkte sind Gestaltungsfragen und stehen unten zur Entscheidung.

## Umgesetzt

1. **U2 – Manuelle Suche zeigte Buchmacherquoten und einen Quotenfilter.** Owner-Entscheid vom
   23.10.2026: Unter der Preisregel 1,20 zeigt die App keine Buchmacherquoten. Die Manuelle Suche
   schrieb unter jeder Auswahl „Quote 2.20“ (`alternative_markets_tab_extended.py`) und bot „Nach
   Quote filtern / Quote von / Quote bis“ an (`manual_search_filters.render_search_filters`). Unter
   `floor` entfallen beide; die Hintergrundprüfung gegen 1,20 bleibt. Unter `gate` unverändert.
   Tests: `test_floor_cards_name_no_bookmaker_quote`, `test_floor_offers_no_quote_filter`.
2. **U3 – Falsche Zeitzone.** `app._multi_sport_event_label` (Basketball, Eishockey, Cricket,
   E-Sport) und `alternative_markets_tab_extended._format_snapshot_time` nutzten die Zeitzone des
   Servers (UTC); Anpfiffe erschienen eine Stunde (Winter) bzw. zwei Stunden (Sommer) zu früh. Beide
   zeigen jetzt Zürcher Zeit wie der Rest der App; eine Zeit ohne Zeitzone gilt als „Termin offen“
   bzw. „n/a“. Tests: `test_multi_sport_kickoff_is_zurich_not_the_server_zone`,
   `test_manual_market_scan_clock_is_zurich_not_the_server_zone` (simulierter UTC-Server).

## Geprüft, kein Fehler

- „Gegenargument“ im Kurzcheck zeigt eine Überschrift („Spielvergleich“, „Gegenseite“) und den
  Inhalt beim Aufklappen, wie alle Fakten der Karte (`forecast_compact._fact_html`). Das ist das
  Bausteinmuster der Karte, kein verlorener Inhalt.

## Offen zur Entscheidung (Gestaltung)

| Punkt | Frage |
|---|---|
| U4 Zahlenformat | Karte „65.8 %“ (Punkt), Kurzcheck und Preisregel „65,8 %“ / „1,20“ (Komma). Ein Format für alles: Punkt (Schweizer Schreibweise) oder Komma (wie in den bisherigen Texten)? |
| U7 Begriffe | „Sicherheitswert“ (15K) klingt nach Sicherheit; „Planungsabstand“, „Gate“, „Roll-over“; drei Namen für Daily3; Leerzustände in roter Grossschrift. Umbenennen nach einer Liste, die der Owner freigibt. |
| U8 Raster und Hinweise | Leerspalten auf der Karte seit dem Wegfall der Quoten, Live ohne Hinweis „experimentell“, Daily3-Fehlermeldung weit vom Formular, Platzhalter in den Rechtstexten. |
| U5/U6 | 15K in Euro statt CHF; Daily3-Slogan „keeps the job away“ und „Ziel +CHF 150“ (Audit-Frage 5 und 6). |
