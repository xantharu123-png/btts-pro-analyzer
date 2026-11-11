# Doublebet: Eishockey zugelassen (11.11.2026)

Owner-Entscheid am 11.11.2026: „Ja, Eishockey zulassen“. Policy `doublebet-odds-around-2-most-probable-v15`.

## Anlass

Am 11.11.2026 (Länderspielpause) war das Doublebet leer. Heute lief in den 66 Ligen kein Fussballspiel.
Die drei Tennisspiele (Stockholm) hatten keine Quote, weil die Quotenquelle das Turnier nicht abdeckt.
Die zwei Basketballspiele (EuroLeague) hatten ebenfalls keine Quote.

Beim Prüfen der Basketball-Quoten zeigte sich: Basketball und Eishockey kommen nie ins Doublebet, auch mit
Quote nicht. Beide laufen als Forschungsmodell (`team_sport_research`). `forecast_highlight_reason` gibt
für sie immer „Modell noch nicht unabhängig bestätigt“ zurück, und `daily3_selection._explanation`
schliesst damit jede solche Zeile aus. Die NHL-Reparatur vom 10.11.2026 (PR #111) brachte der NHL Quoten,
aber kein Doublebet.

## Befund (abgerechnete Evidenz, Favorit je Spiel, Stand 11.11.2026)

| Modell | Spiele | Favorit gewonnen | Modell sagte |
|---|---|---|---|
| Eishockey (NHL), alle | 164 | 57,9 % | 60,3 % |
| Eishockey, Modell ab 60 % | 75 | 66,7 % | 66,9 % |
| Eishockey, Modell ab 70 % | 17 | 82,4 % | 74,9 % |
| Basketball (EuroLeague), alle | 29 | 51,7 % | 67,6 % |
| Basketball, Modell ab 60 % | 20 | 60,0 % | 73,1 % |

Quelle: `forecast_rows`/`forecast_results` in `forecast_evidence.db`, je Spiel die Seite mit der höheren
Modellchance. Das Eishockey-Modell trifft ungefähr, was es verspricht. Das Basketball-Modell liegt deutlich
zu hoch. Alle 418 Eishockey-Zeilen stammen aus der NHL; ein Modell für europäisches Eishockey gibt es nicht.

## Änderung

- `forecast_analysis.forecast_highlight_reason(..., admit_research_sports=frozenset())`: Ein Aufrufer kann
  Forschungsmodelle einzelner Sportarten zulassen. Eine zugelassene Zeile behält wie die automatischen
  Tageszeilen die Tageslebensdauer ihres Spieltags (24 Stunden, `DAILY_MODEL_HIGHLIGHT_MAX_AGE`). Ohne
  Angabe gilt der alte Ausschluss.
- `daily3_selection.DOUBLEBET_RESEARCH_SPORTS = {'eishockey', 'ice_hockey'}`; `_explanation` übergibt sie.
  Nur das Doublebet (heute und die Vorschau für morgen) nimmt damit Eishockey auf.
- Alle übrigen Regeln bleiben: zugelassene Quote mit Median 1,80–2,20, Spiel muss vor Mitternacht fertig
  sein (3 Stunden Planungsabstand), höchstens drei Wetten, keine zwei Seiten desselben Spiels.
- Basketball bleibt draussen. Wettfinder-Karte, Tipps, 15K und Hervorhebungen behalten den Ausschluss.
- `team_sport_prices.refresh_team_sport_prices` prüft Spiele mit Modellzeile zuerst, danach reine Preiszeilen aus
  den Snapshots, je nach Anstoss. Beleg vom 11.11.2026 (`team_sport_quotes.json`): Der Quotenlauf um 09:15 vergab
  alle 8 Eishockey-Plätze (`MAX_EVENTS_PER_SPORT`) an europäische Spiele ohne Modell (API-Hockey); die 4 NHL-Spiele
  mit Modell kamen erst um 12:15 dran. An Wochenenden mit frühen NHL-Spielen hätte das die Zulassung ausgehebelt.
  Budget und Abrufzahl bleiben gleich.

## Trockenlauf mit Live-Daten (11.11.2026, 14:00)

Branch-Code gegen den Live-Snapshot, nur lesend: Die 8 NHL-Zeilen gelten jetzt als zugelassenes Modell. Sie haben
aber noch keine Quote. Der Lauf um 12:15 hat sie geprüft und ohne Lücke und ohne Fehler keine Quote gefunden;
vermutlich bietet API-Sports so lange vor Spielbeginn noch keine NHL-Quoten an (am 10.11. klappte es um 21:15).
Die Spiele beginnen ab 01:00 und zählen zum 12.11. Doublebet heute und Vorschau morgen bleiben leer.

## Wirkung, ehrlich

Die NHL spielt meist nach Mitternacht Schweizer Zeit. Von 418 Eishockey-Zeilen begannen 30 zwischen 06:00
und 21:00, an 9 von 32 Tagen, fast nur am Wochenende. Nur diese passen ins Doublebet des Tages. An einem
Wochentag wie dem 11.11.2026 hilft die Änderung nicht.

## Tests

`tests/test_doublebet_eishockey.py`: Eishockey im Band kommt ins Doublebet, beide Seiten eines Spiels nie
zusammen, Basketball bleibt draussen, Eishockey ausserhalb des Bands bleibt draussen, andere Flächen
behalten den Ausschluss, die Tageslebensdauer gilt nur am Spieltag.
`tests/test_team_sport_prices.py::test_model_rows_are_priced_before_price_only_snapshot_rows`: Modellzeile vor acht
früheren Preiszeilen. Alle neuen Tests sind auf `main` rot und auf dem Branch grün.

Lokal grün: Doublebet-, Hervorhebungs-, Vorschau-, Teamsport-, Hockey- und Preis-Suiten (723 + 139 Tests), dazu
die Doublebet-Suiten unter dem Produktionsvertrag `BETBOY_TEST_PRICE_POLICY=floor` (141). Nicht grün:
`test_forecast_consumer_reuses_exact_cached_price_without_network`, scheitert schon auf `main` (bekannt seit 10.11.).

## Rückweg

`DOUBLEBET_RESEARCH_SPORTS = frozenset()` stellt den alten Zustand her.
