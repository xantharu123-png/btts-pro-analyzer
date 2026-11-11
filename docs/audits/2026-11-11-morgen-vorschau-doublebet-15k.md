# Doublebet und 15K zeigen morgen als Vorschau (Schritt 2)

Stand 11.11.2026. Owner-Wunsch vom 10.11.2026: „bei allen Tipps heute und morgen anschauen können“. Schritt 2 hat
der Owner freigegeben („alles machen“). Schritt 1 (Wettfinder listet immer morgen) steht in
`2026-11-10-folgetag-immer.md`.

## Änderung

- **Doublebet-Seite:** Unter der heutigen Auswahl steht der Abschnitt „Morgen (Vorschau)“ mit bis zu drei Karten.
  Gleiche Regel wie heute (Quote um 2,00, höchste Summe der Modellchancen), aber für den Folgetag und ohne
  gebuchte Wetten. Ohne passende Auswahl erscheint der Abschnitt nicht.
- **Doublebet-Spalte im Wettfinder:** Unter „Deine Tagesauswahl“ stehen die Auswahlen von morgen als Liste mit dem
  Hinweis „Vormerken erst am Spieltag.“
- **15K-Seite, Spieltag „Morgen“ mit allen Ligen:** Die Karten von morgen kommen aus dem Tageslauf
  (`football_next_day`, Modellzeilen des Folgetags, Quoten aus jedem Quotenlauf). Kein Scan im Browser, keine
  automatische Nachprüfung, keine Ticketauswahl. Fehlt ein gültiger Folgetag im Artefakt, steht dort ein Hinweis.
- **15K mit eigener Ligaauswahl für morgen:** Die manuelle Suche bleibt. Die Karten erscheinen, die Ticketauswahl
  nicht mehr. Ein 15K-Ticket gibt es damit nur noch am Spieltag.

## Technik

- `daily3_selection.daily3_choices(..., target_day=...)` ersetzt nur den Plantag (heute oder morgen, sonst
  `ValueError`). Preisprüfung, zugelassene Quote und Modellalter laufen weiter mit der echten Uhrzeit.
  `doublebet_preview_choices` ruft das für morgen auf, ohne gebuchte Wetten.
- `forecast_analysis.forecast_highlight_reason(..., match_day=...)`: Die Tageslebensdauer des Modells (24 Stunden)
  gilt für den genannten Tag. Ohne Angabe bleibt es heute. Sonst fiele jede Zeile von morgen nach 150 Minuten aus der
  Vorschau, weil der Tageslauf um 03:35 rechnet.
- `wettfinder_automation.build_next_day_challenge_preview` baut den 15K-Stand aus demselben Artefakt nach, nur mit
  dem Folgetag, nur mit Anpfiff an diesem Tag und ohne Ticketpool (`shortlist`, `price_candidates` leer).
- `challenge_15k._render_model_challenge(..., preview=True)` zeigt nur die Karten.

## Was ausgeschlossen bleibt

- Vormerken (Doublebet) und Ticket (15K) nur am Spieltag.
- Morgen wird vor dem eigenen Spieltag nie als Tipp oder Veröffentlichung erfasst (`record_selected_tips`,
  `record_signal_catalog`), nie Evidenz, Archiv (`daily3_default_plan`, `daily3_rail`, `daily3_plan`) oder Shadow.
- Keine neuen Felder in gespeicherten Ständen, keine neuen Abrufe bei Anbietern.
- Die Vorschau ist keine Zusage: Bis zum Spieltag ändern sich Quoten, Kontext und Modellstand.

## Prüfung

- **Neue Tests** in `tests/test_morgen_vorschau.py` (14, zuerst rot, dann grün):
  - Doublebet wählt mit `target_day` morgen eine Zeile, die der Spieltag nicht wählt; heute bleibt gleich.
  - Ein anderer Tag als heute oder morgen und ein Datum mit Uhrzeit scheitern (4 Fälle).
  - Die Tageslebensdauer gilt nur in der Vorschau für morgen, ein manuelles Modell behält 150 Minuten.
  - Doublebet-Seite: Karte von morgen sichtbar, ein einziges Vormerk-Formular (heute), erfasst wird nur heute.
  - Die Vorschau ruft weder Speicher noch Formular noch Erfassung auf (diese Funktionen werfen im Test).
  - Wettfinder-Spalte: Liste von morgen, erfasst wird nur `daily3_rail` von heute.
  - 15K: Vorschau aus dem Artefakt, nur mit gültigem Folgetag und passendem Datum; heute ohne das Spiel von morgen.
  - 15K-Seite „Morgen“: Karten ohne Scan, Nachprüfung, Ticketauswahl und Einsatz; manuelle Suche für morgen
    ohne Ticketauswahl.
- **Lokale Läufe (Windows, Vertrag `gate`):**
  - Neue Tests, Doublebet, 15K, Folgetag, Mindestchance, Navigation und Sportkarten: 367 Tests grün.
  - 23 benachbarte Dateien (Tageslauf, Preisprüfung, Kontext, Abläufe): 1031 grün, 2 rot.
- **Unter `BETBOY_TEST_PRICE_POLICY=floor`:** 12 Dateien, 392 grün, 2 rot.
- **Rot schon vorher:** Alle vier Fehlschläge scheitern genauso auf dem unveränderten `main` (`c835ec4`).
  - `test_active_15k_model_surface_obeys_bound_floor_before_slot_selection[1.2-True]`
  - `test_normal_wettfinder_does_not_inherit_daily3_probability_floor` (erwartet noch die alte 70-%-Grenze)
  - unter `floor`: `test_second_market_stays_visible_without_repeating_the_whole_match` und
    `test_card_first_level_shows_minimum_odds_and_price_status`
- `ruff` auf den geänderten Dateien: ohne Befund.

## Offen

- **Schritt 3:** Tennis, Eishockey, E-Sport und RisikoBet mit morgen.
- **Beobachten:** Wie oft die Doublebet-Vorschau leer bleibt. Morgen braucht dieselben Kontextprüfungen wie heute
  (24 Stunden alt, ohne Veto), und der Folgetag bekommt nur die Kontrollen, die heute übrig lässt.
