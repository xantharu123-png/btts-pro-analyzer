# Vertragsänderung 28.10.2026: Shadow-Schlussquote ist der letzte Marktstand vor Anpfiff

Owner-Entscheidung vom 28.10.2026, analog zur Öffnungsquote vom 23.10.2026
(`docs/audits/2026-10-23-oeffnungsquote-frischeregel.md`). Betroffen sind nur der Shadow-Pfad und der
CLV-Tracker (`clv_tracker.CLVTracker`, `shadow_clv_automation.step_closing` und die Auswertungen); kein
Modell, keine Freigabe und keine Veröffentlichung ändern sich.

## Befund

Bis zum 27.10. musste die Schlussquote selbst einen Anbieter-Zeitstempel aus den letzten 15 Minuten vor
Anpfiff tragen. API-Football aktualisiert die Vorspielquoten je Spiel nur etwa alle drei Stunden: Alle zehn
Öffnungsquoten der Shadow-Tipps vom 25. bis 27.10. waren beim Protokollieren 22 bis 178 Minuten alt, keine
älter als drei Stunden. Der neueste Bet365-Stand ist bei Anpfiff also 0 bis 180 Minuten alt; das
15-Minuten-Fenster traf ihn nur zufällig. Ergebnis: in 119 Shadow-Läufen seit dem 25.10. keine einzige
Schlussquote, alle zehn Tipps ohne CLV. Die Evidenz für die Hybrid-Aktivierung und die Edge-Kappung
(je 300 abgerechnete Tipps mit gültigem Closing) wuchs dadurch nicht.

## Neue Regel (Policy `shadow-model-first-v7`)

1. **Abruf unverändert:** Die Schlussquote wird in den letzten 15 Minuten vor Anpfiff abgerufen
   (`CLOSING_WINDOW`).
2. **Letzter Marktstand:** Gültig ist der Bet365-Stand mit Anbieter-Zeitstempel vor Anpfiff, der beim Abruf
   höchstens drei Stunden alt ist (`CLOSING_QUOTE_MAX_AGE`), also dieselbe Grenze wie bei der Öffnungsquote.
   Ein älterer Stand wird nicht gespeichert und als Datenstatus gemeldet
   („…-Quote/Zeitstempel … älter als drei Stunden“, kein Alarm).
3. **Alter mitprotokolliert:** Gespeichert werden zusätzlich die Abrufzeit (`closing_captured_at`) und das
   Alter des Stands beim Abruf (`closing_quote_age_seconds`); die Statistik prüft beides gegen die eigenen
   Uhren der Zeile.
4. **Kein neuer Marktstand:** Trägt die Schlussquote denselben Anbieter-Zeitstempel wie die Öffnungsquote,
   ist sie gültig, enthält aber keine Marktinformation (CLV null per Konstruktion). Solche Zeilen zählen in
   `total_bets`, nicht aber in `clv_bets`, `independent_clv_fixtures` und den CLV-Mittelwerten; sie stehen
   gesondert als `closing_without_new_market_state`. Edge-Cap-Gruppen führen sie als
   `closed_without_new_market_state`, die Hybrid-Paarung als `pairs_without_new_market_state` (ein Paar
   zählt nur, wenn beide Kohorten einen neuen Stand haben). Das Prüfkriterium (300 Paare, HAC-Grenze) zählt
   nur Zeilen mit neuem Marktstand.
5. **Altzeilen:** Zeilen ohne Abrufzeit wurden nach der alten Regel erfasst und werden wie bisher geprüft.
   `update_closing_odds` ohne `captured_at` behält die alte Regel.

Die Policy springt auf v7, damit die Shadow-Evidenz unter einer einheitlichen Regel entsteht. Die zehn Zeilen
unter v6 hatten keine Schlussquote und behalten ihre Kohorte.

## Erwartete Wirkung

Bei den zehn Shadow-Tipps vom 25. bis 27.10. hätte die neue Regel zehn Schlussquoten geliefert, nach einem
Drei-Stunden-Takt geschätzt etwa fünf mit neuem Marktstand (die Spiele um 16:00 und 19:45; bei den Spielen um
12:00, 13:30, 14:30 und 18:15 kam der nächste Stand erst nach Anpfiff). Direkt belegen lässt sich das nicht:
Die Schlussabrufe des Shadow wurden nicht gespeichert, und die Schlussquoten der App stammen nur aus Eishockey.

## Grenzen

- Die Schlussquote ist ein bis zu drei Stunden alter Stand, keine Quote im Moment des Anpfiffs; der CLV misst
  die Marktbewegung zwischen zwei API-Football-Ständen.
- Die Hybrid-Paarung bleibt langsam: Unter den zehn Tipps war kein Spiel, das beide Kohorten getippt haben.
- Eine echte Schlussquote bräuchte eine zweite Quelle mit minütlichen Stand-Updates (etwa The Odds API);
  das ist eine eigene Entscheidung.

## Umsetzung und Tests

`clv_tracker` (`CLOSING_QUOTE_MAX_AGE`, Spalten `closing_captured_at`/`closing_quote_age_seconds`,
`update_closing_odds(..., captured_at=)`, `_valid_closing_timing`, `_new_market_state`,
`get_clv_statistics`, `get_recent_predictions`), `shadow_clv_automation` (`SHADOW_POLICY_VERSION` v7,
`step_closing`, `_new_market_state`, `_edge_cap_statistics`, `_paired_cohort_statistics`). Tests:
`tests/test_shadow_closing_rule.py` neu (Speichern mit Abrufzeit und Alter, zu alter Stand, Abruf ausserhalb
des Fensters, alte Regel ohne Abrufzeit, Statistik mit und ohne neuen Stand, widersprüchliches Alter,
Shadow-Abruf, wiederholter und zu alter Stand als Datenstatus, Edge-Cap und Paarung);
`test_opening_quote_age`, `test_shadow_edge_cap`, `test_shadow_hybrid_cohort` angepasst.
