# Shadow-Altersgrenze 24 Stunden (Policy `shadow-model-first-v10`)

Datum: 30.10.2026. Owner-Entscheid im Chat nach dem Befund unten.

## Befund (nur lesend, `output/release-20261030-2/verify-02-coverage.log`, `verify-03-missed.log`)

- Am 30.10. meldete der Shadow bei 8 Spielen mit glaubwürdigem Kandidaten „keine aktuelle Bet365-Quote mit
  Providerzeit“. Bei 6 davon führt die App für dieselben Spiele Bet365-Quoten (`forecast_evidence.db`), aber mit
  dem nächtlichen Anbieterstempel um 00:00–00:34 UTC. Beim Bewerten 20–75 Minuten vor den Abendspielen war dieser
  Stand 16 bis 18,5 Stunden alt und fiel unter die 12-Stunden-Grenze von v8/v9.
- Ein anderer Buchmacher hilft dabei nicht: Der Stempel `update` gilt bei API-Football je Spiel für alle
  Buchmacher (`docs/audits/2026-10-29-bet365-zeitstempel.md`). Von 725 Spielen mit Quoten in den App-Daten hatten
  nur 12 (rund 2 %) gar keinen Bet365-Markt.

## Regel ab v10

- `CLVTracker.OPENING_QUOTE_MAX_AGE` und `CLOSING_QUOTE_MAX_AGE` von 12 auf **24 Stunden**; ein älterer Stand bleibt
  Datenstatus („…älter als 24 Stunden“). Abruf, Mindestquote 1,30 und modellgeführte Reihenfolge bleiben.
- Das Alter jeder Öffnung wird weiter gespeichert (`opening_quote_age_seconds`); `results.by_opening_age` trennt
  abgerechnete Tipps nach „bis 12 Stunden“, „über 12 Stunden“ und „unbekannt“ (Anzahl, Trefferquote, mittlere
  Rendite).
- Der Tracker ist derselbe für den öffentlichen CLV-Pfad (`advanced_analyzer`, `btts_data_clv.db`); auch dort gilt
  die 24-Stunden-Grenze.

## Risiko und Prüfung

Bei einem Stand, der 18 Stunden alt ist, ist nicht belegt, dass genau diese Quote beim Tipp noch angeboten wurde;
die gemessene Rendite kann deshalb um einige Prozent von einer echten Wette abweichen. Vor der ersten v10-Zeile
festgelegt: Die Prüfstufe bleibt bei 1000 abgerechneten Tipps derselben Policy (Zählung beginnt unter v10 neu);
liegt die Rendite der Tipps über 12 Stunden später deutlich unter der der jüngeren, wird die Grenze neu entschieden.
