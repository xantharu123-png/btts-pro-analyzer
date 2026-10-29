# Befund 29.10.2026: Was der Bet365-Zeitstempel von API-Football bedeutet

Auftrag des Owners am 29.10.2026: nur lesend klären, warum der Bet365-Stand von Spiel 1638113 nach 12:04 UTC
nicht mehr erneuert wurde und ob der Zeitstempel die letzte Abfrage oder die letzte Preisänderung ist. Keine
Änderung an Code, Datenbanken oder Einheiten, kein API-Aufruf; Prüfskripte und Ausgaben in
`output/release-20261028-3/` (`trace_1638113.sh`, `stamp_semantics2.sh`, `stamp_paths.sh`, `stamp_compare.sh`,
`stamp_pairs.sh`, `opening_ages.sh`, Protokoll `verify-04-zeitstempel.log`).

## Herkunft des Zeitstempels

`shadow_clv_automation._market_quote_observation` liest das Feld `update` des Eintrags aus der Antwort von
`/odds?fixture=…&bookmaker=8`. `ShadowProvider.odds` ruft API-Football bei jedem Lauf direkt auf
(`api_football_get`, ohne Zwischenspeicher). Der Wettfinder übernimmt dasselbe Feld als `observed_at` der
API-Football-Punkte (`market_consensus`).

## Spiel 1638113 (AC Oulu–VPS, Liga 244, Anpfiff 28.10. 16:00 UTC)

- Bet365-Stand 12:04:18 UTC; Öffnung protokolliert 14:52:27 UTC, Alter 2 h 48 min (`opening_quote_age_seconds`
  10 089).
- Einziger Schlussversuch im 15-Minuten-Fenster: Shadow-Lauf 15:52 UTC (16:52 CET), Meldung „Bet365-Quote/
  Zeitstempel TOTAL_OVER_1_5 älter als drei Stunden“. Bis zu diesem Abruf gab es für das Spiel also keinen
  Bet365-Stand nach 12:52 UTC; sehr wahrscheinlich galt noch der Stand von 12:04 UTC (Alter 3 h 48 min).
- Der Tipp ist inzwischen abgerechnet (0:0, verloren).

## Was der Zeitstempel ist

1. **Ein Stempel je Spiel, gesetzt im Sammellauf.** Im Wettfinder-Dokument des Quotenlaufs 09:15 CET tragen 572
   API-Football-Quoten von 8 Spielen genau einen Stempel je Spiel; 429 Quoten aller Buchmacher und mehrerer Spiele
   teilen sich dieselbe Sekunde (06:00:21 UTC). Sammelläufe am 29.10.: 00:00:31, 04:01:16, 06:00:21,
   08:00:17–08:21:18 UTC, also 2 bis 4 Stunden auseinander. Stempel früherer Shadow-Tipps: 09:01, 12:00–12:07,
   13:53, 14:55, 16:03, 16:21, 18:00 UTC.
2. **Der Stempel wandert mit Preisänderungen.** Vergleich der Quotenläufe 09:15 und 12:15 CET (dieselben
   Quoten-Identitäten): 7 von 8 Spielen bekamen einen neuen Stempel, bei allen 7 hatten sich Quoten geändert
   (1 bis 31 von 50 bis 97 verglichenen Preisen). Das achte Spiel (1550952) behielt seinen Stempel von 00:00:31 UTC,
   keiner seiner 42 Preise hatte sich geändert. Die einzige je erfasste Shadow-Schlussquote (1570343, 22.08.) hatte
   einen neuen Stempel bei gleichem Preis im Tippmarkt, passend zu einem Stempel je Spiel.
3. **Nicht beweisbar von aussen:** ob API-Football ein Spiel ohne Preisänderung trotzdem neu abfragt und nur den
   Stempel stehen lässt, oder ob es das Spiel in einem Sammellauf auslässt. Verglichen wurden nur die Märkte im
   Wettfinder-Dokument; eine Änderung in einem anderen Markt kann den Stempel ebenfalls bewegen. Die offizielle
   Dokumentation war nicht abrufbar (HTTP 403); die Angabe „etwa alle drei Stunden“ im Code ist eine eigene Annahme.

## Folge für die 3-Stunden-Grenze

Die Grenze (`OPENING_QUOTE_MAX_AGE`, `CLOSING_QUOTE_MAX_AGE`, je 3 h) ist so lang wie der Abstand der Sammelläufe
selbst und hat keinen Puffer. Beim Abruf 11:15 UTC am 29.10. waren 7 von 8 Stempeln älter als drei Stunden, obwohl
sich die Preise von 6 dieser Spiele erst um 08:00–08:04 UTC geändert hatten. Ein Spiel, dessen Preis im letzten
Sammellauf gleich blieb oder dessen Sammellauf sich verspätet, fällt beim Öffnen (Hybrid: 49 Meldungen ohne
Bet365-Quote ≤ 3 h, 0 Tipps) wie beim Schluss heraus. Die Annahme aus `2026-10-28-schlussquote-letzter-marktstand.md`
(„neuester Bet365-Stand bei Anpfiff 0 bis 180 Minuten alt“) trifft nicht zu.

Liest man den Stempel als Zeit der letzten Änderung, ist ein alter Stempel bei frischem Abruf der aktuelle Preis.
Dann wäre auch ein Schlussstand mit dem Öffnungsstempel echte Information (der Markt hat sich nicht bewegt) und
nicht bloss „kein neuer Marktstand“.

## Optionen

- **A – so lassen:** kaum Tipps und praktisch keine Schlussquoten; der Hybrid-Prüfplan (300 Paare) bleibt
  unerreichbar.
- **B – Grenze anheben, z. B. 12 h für Öffnung und Schluss:** Abruf bleibt frisch (Schluss in den letzten
  15 Minuten), Alter wird weiter je Zeile gespeichert, die Grenze schützt nur noch gegen einen stehengebliebenen
  Anbieter. Auswertung zusätzlich nach Altersklassen.
- **C – Schluss ohne Altersgrenze:** letzter Bet365-Stand vor Anpfiff, frisch abgerufen, Alter gespeichert.
- Bei B oder C prüfen, ob ein unveränderter Stand weiterhin aus der CLV-Evidenz fällt.

Jede Änderung braucht eine neue Policy-Version (v8), damit die Evidenz unter einer einheitlichen Regel entsteht.
Empfehlung Claude: B, weil sie die meisten Paare bringt und einen Schutz gegen tote Daten behält.

## Owner-Entscheid 29.10.2026: Option B (Policy `shadow-model-first-v8`)

- `CLVTracker.OPENING_QUOTE_MAX_AGE` und `CLVTracker.CLOSING_QUOTE_MAX_AGE` von 3 h auf **12 h**. Der Abruf bleibt
  wie bisher: Öffnung beim Bewerten 20 bis 75 Minuten vor Anpfiff, Schluss in den letzten 15 Minuten
  (`CLOSING_WINDOW`). Das Alter wird je Zeile gespeichert (`opening_quote_age_seconds`,
  `closing_quote_age_seconds`), das Run-Artefakt nennt beide Grenzen (`opening_quote_max_age_seconds`,
  `closing_quote_max_age_seconds`).
- Ein älterer Stand bleibt Datenstatus („…-Quote/Zeitstempel … älter als zwölf Stunden“, kein Alarm).
- Unverändert: Ein Schlussstand mit dem Stempel der Öffnung zählt nicht als CLV-Evidenz
  (`closing_without_new_market_state`, `pairs_without_new_market_state`). Unter v8 werden solche Zeilen
  häufiger; ob sie als „Markt unverändert“ in die Evidenz gehören, ist eine spätere Owner-Frage, sobald genug
  v8-Zeilen vorliegen.
- Zeilen unter v5 bis v7 behalten ihre Kohorte; sie erfüllen die gelockerte Prüfung ebenfalls. Der Tracker ist
  derselbe für den öffentlichen CLV-Pfad (`advanced_analyzer`, `btts_data_clv.db`, derzeit 0 Zeilen); auch dort
  gilt die 12-Stunden-Grenze.
- Regressionstest für den Fall vom 28.10. (`tests/test_shadow_closing_rule.py::
  test_v8_keeps_the_28_october_closing_older_than_three_hours`).
