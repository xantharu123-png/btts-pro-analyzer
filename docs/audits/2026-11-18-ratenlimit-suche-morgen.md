# Ratenlimit: Die Suche für morgen verlor 34 Ligen

Stand 18.11.2026. Owner: „Ja, reparieren“.

## Anlass

Die erste Nacht mit der Reihenfolge „heute zuerst“ (Lauf am 18.11.2026 um 03:35) lief wie entworfen und endete mit
Exit 0. „Heute“ stand um 03:41:30 in der Datei statt um 03:49:15 wie in der Nacht davor. Die Suche nach Fussball für
morgen meldete aber `sources.football.next_day.status = scanned_partial` mit 34 Betriebsfehlern und 0 Spielen für den
19.11.

## Befund

Quelle ist das Abrufprotokoll der Produktion (`runtime_state/api_budget.db`, Tabelle `api_budget_events`), nur
gelesen. Zeiten in UTC.

- **18.11., 02:41:24 bis 02:41:25:** Die Preisauffrischung für Teamsport schickt 11 Abrufe in 1,26 s: 2 Eishockey
  „games“, 8 Eishockey „odds“, 1 Basketball „games“. Alle kommen mit HTTP 200 zurück.
- **02:41:28 bis 02:41:47:** 40 Fussball-Abrufe kommen mit HTTP 429 zurück. Zuerst der Sammelabruf
  „Fixture-Details“ der Abrechnung und fünf Einzelabrufe, danach 34 Abrufe „Fixtures Liga …“ der Suche für morgen.
  Die ersten betroffenen Ligen sind 78, 39, 140, 135, 61 und 88.
- **Ab 02:41:48** laufen die Abrufe wieder, obwohl weiter zwei je Sekunde gesendet werden.
- Das Minutenlimit des Fussball-Tarifs war nicht erreicht: 76 Abrufe in dieser Minute.

Der Zusammenhang über alle Tage seit dem 08.11.2026 (34 Folgen von Teamsport-Abrufen mit mindestens acht Abrufen):

| Eishockey-Abrufe in der Minute davor | Folgen | davon 429 beim nächsten Fussball-Abruf |
|---|---|---|
| 10 oder mehr | 19 | 12 |
| 9 oder weniger | 15 | 0 |

- Die Dichte entscheidet nicht: Neun Abrufe innerhalb einer Sekunde blieben dreimal folgenlos.
- Abgelehnt wurden immer nur Fussball-Abrufe, nie die Teamsport-Abrufe selbst. Der erste abgelehnte Abruf lag 1,3 bis
  3,0 s nach der Folge.
- In allen zwölf Sperren (11.11. bis 18.11., zusammen 109 abgelehnte Abrufe) wurde kein einziger der 63
  Einzelabrufe „Fixture-Details <Spiel>“ beantwortet, die dem abgelehnten Sammelabruf folgten.
- Der Eishockey-Zugang hat ein Tageslimit von 100. Das ist der Gratis-Tarif von API-Sports mit zehn Abrufen je
  Minute. Dieses Minutenlimit ist hier nicht aus einer Antwort des Anbieters belegt, weil der Code nur die Köpfe zum
  Tageskontingent liest. Es passt aber genau zur beobachteten Schwelle.

## Ursache

1. `team_sport_prices.refresh_team_sport_prices` schickt je Sportart bis zu acht „odds“-Abrufe und ein bis drei
   „games“-Abrufe ohne Pause. Nach dem zehnten Eishockey-Abruf in einer Minute lehnte der Anbieter in 12 von 19
   Fällen die nächsten Abrufe desselben Schlüssels ab, auch die für Fussball. Gemessen ist die Dauer nur für den
   18.11.: rund 20 Sekunden.
2. Ein 429 wurde nirgends wiederholt. Im Scanner fiel die Liga ganz weg, und die Liste für morgen wird bis zum
   nächsten Nachtlauf nicht neu gesucht.
3. Vom 11. bis 15.11. traf es elfmal nur die Ergebnis-Abrufe der Abrechnung, je sechs bis acht Abrufe. Danach lief
   in diesen Läufen kein Fussball-Abruf mehr. Seit „heute zuerst“ beginnt im Nachtlauf wenige Sekunden nach der
   Abrechnung die Suche für morgen.
4. Der Rückfall auf Einzelabrufe in `details_by_fixture` schickte nach einem abgelehnten Sammelabruf weitere Abrufe
   in die Sperre.

## Reparatur

- **A, Ursache: unter dem Minutenlimit bleiben.** Die Preisauffrischung fragt vor jedem Abruf das Abrufprotokoll,
  wie viele Abrufe diese Sportart in den letzten 60 Sekunden hatte (`APIBudgetGovernor.recent_request_count`). Sie
  schickt einen Abruf nur, wenn danach höchstens neun in der Minute stehen
  (`team_sport_prices.SIDE_REQUESTS_PER_MINUTE`, `_minute_allowance`).
  - Die Spielliste eines neuen UTC-Tags holt sie nur, wenn auch der Quotenabruf des Spiels noch in die Minute passt
    (zwei Abrufe frei).
  - Das Protokoll sieht alle Prozesse und auch den Eishockey-Scanner desselben Laufs.
  - Ein Spiel, das nicht mehr in die Minute passt, bekommt keinen Versuchsstempel und behält seine ältere Quote. In
    der Zusammenfassung steht es als Datenstatus `budget_deferred` mit dem Eintrag „<Sportart>:minute_limit“, nicht
    als Betriebsfehler.
  - Im nächsten Lauf kommt dieses Spiel innerhalb seiner Klasse zuerst dran (Liste `minute_deferred` in
    `team_sport_quotes.json`). Grund: Timer und Auffrischfrist sind beide drei Stunden, die früheren Spiele sind
    deshalb oft wieder fällig und hätten dasselbe späte Spiel Lauf für Lauf verdrängt. Modellzeilen bleiben vor
    reinen Preiszeilen.
  - Warten mehrere Spiele, kommt zuerst dran, wer am längsten wartet; die Liste hält diese Reihenfolge. Ein
    wartendes Spiel, das ein Lauf wegen der Obergrenze von acht nicht erreicht, behält seinen Platz. Ein
    ausgelassenes Spiel verbraucht keinen der acht Plätze.
  - Die Prüfung steht direkt vor den Abrufen. Ein Spiel, das keinen Abruf braucht (mehrdeutige Herkunft, NHL-Namen
    nicht auflösbar), verliert seine alte Quote wie bisher und steht als Identitätslücke in der Zusammenfassung,
    auch wenn die Minute voll ist.
- **B, Sicherung: einmal warten und erneut fragen.** Ein Fussball-Provider eines Hintergrundlaufs wartet nach einem
  429 einmal 30 Sekunden und stellt den Abruf erneut (`challenge_15k.RATE_LIMIT_RETRY_DELAY_SECONDS`,
  `ChallengeDataProvider.enable_rate_limit_retry`).
  - Eingeschaltet an fünf Stellen. Vier über `wettfinder_automation._worker_football_provider`: Suche für heute und
    morgen, Kontext, Einsatzhistorie, Abrechnung der Prognose-Ergebnisse (Nachtlauf und Quotenlauf). Die fünfte ist
    der Standard-Provider der RisikoBet-Ergebnisse (`riskobet_settlement_automation._default_loader`), den nur die
    Stufe `riskobet_results` des Nachtlaufs baut.
  - Höchstens eine Wartezeit je Provider-Instanz. Ein dauerhafter 429, etwa bei leerem Tageskontingent, verlängert
    damit nicht jeden Abruf um eine halbe Minute.
  - Gelingt der zweite Versuch, steht kein Betriebsfehler in der Zusammenfassung.
  - Jeder Versuch wird einzeln im Protokoll verbucht, wie bei der bestehenden Wiederholung nach Zeitüberschreitung.
- **C: nicht in die Sperre nachschiessen.** Nach einem 429 auf den Sammelabruf „Fixture-Details“ folgen keine
  Einzelabrufe mehr. Bei anderen Fehlern bleibt der Rückfall. Die Spiele kommen ohne Daten zurück, genau wie nach
  abgelehnten Einzelabrufen: Eine Abrechnung lässt sie für den nächsten Lauf offen, die Kontextauffrischung
  behandelt sie wie jedes fehlende Detail.

## Folgen im Betrieb

- Braucht eine Sportart zehn Abrufe, zum Beispiel acht Spiele an zwei UTC-Tagen, wartet ein Spiel auf den nächsten
  Lauf und kommt dort zuerst dran. Sind dann wieder alle fällig, wartet ein anderes: Reihum fehlt je Lauf ein Spiel.
  Sein Preis ist bis dahin der ältere; Leser nehmen eine Quote bis 24 Stunden an.
- Wird ein wartendes Spiel in dieser Zeit verschoben oder abgesagt, bleibt seine alte Quote einen Lauf länger
  sichtbar als bisher, also rund drei Stunden, höchstens bis zum Anstoss. Das gilt nur, wenn im selben Lauf kein
  anderes fälliges Spiel desselben UTC-Tags abgefragt wird; sonst fällt die Quote wie bisher sofort weg.
- Liegen Eishockey-Abrufe des Scanners weniger als eine Minute zurück, bepreist der Lauf entsprechend weniger
  Eishockey-Spiele (in der Zusammenfassung „ice_hockey:minute_limit“). Im Nachtlauf laufen beide Scanner-Aufrufe
  vor der Preisauffrischung; wie oft sie in dieselbe Minute fallen, zeigen erst die Stufenzeiten nach dem Release.
- Ein Lauf kann je Provider-Instanz einmal 30 Sekunden warten. Die Zeitgrenzen der Einheiten (Quotenlauf 12 Minuten,
  Nachtlauf 60 Minuten) sind davon weit entfernt. Die Stufe `riskobet_results` liegt vor dem ersten Schreiben; eine
  Wartezeit dort verschiebt „heute“ um höchstens 30 Sekunden.

## Unverändert

- Die Obergrenze von acht Spielen je Sportart und Lauf, die Reihenfolge „Modellzeilen zuerst“, Auswahl, Tipps,
  Evidenz und Abrechnung.
- App-Seiten, manuelle Suchen und Preispfade warten nie. Dort bleibt ein 429 ein Fehler wie bisher.
- Der Eishockey-Scanner (`scanners/api_hockey.py`) wird nicht begrenzt; seine Abrufe zählen im Protokoll aber mit.
  Er schickt einen Abruf für die Ligen, einen je Tag und bis zu vier für die Historie: im Nachtlauf rund sechs für
  heute und bis zu sieben beim ersten Aufruf für morgen.
- Der Rückfall auf Einzelabrufe bei den Verletzungen (`injuries_by_fixture`) bleibt. Er war nie Teil eines
  beobachteten Vorfalls.
- Der Shadow-Lauf und die direkten Kontext-Abrufe (`_context_football_response`) warten nicht.
- Die Minutenköpfe des Anbieters werden weiter nicht gespeichert.

## Prüfung

- **Neu:** `tests/test_api_rate_limit.py` mit 28 Tests.
  - A, Zählung: je Anbieter und Konto, mit der Grenze bei genau 60 Sekunden; gesperrte Reservierungen zählen nicht,
    fehlgeschlagene Abrufe zählen.
  - A, Auffrischung: Sie bleibt bei neun Abrufen. Sieben Spiele an einem Tag und eines am nächsten ergeben acht
    Abrufe statt zehn. Abrufe von anderem Code derselben Minute zählen mit, jede Sportart hat ihre eigene Minute.
  - A, Warteliste: Das ausgelassene Spiel kommt im nächsten fälligen Lauf zuerst dran, aber nie vor einer
    Modellzeile. Wer am längsten wartet, kommt zuerst. Ein wartendes Spiel behält seinen Platz, wenn die Obergrenze
    es nicht erreichen lässt, und verschwindet aus der Liste, wenn es nicht mehr ansteht. Ausgelassene Spiele
    verbrauchen keinen der acht Plätze.
  - A, Grenzfälle: Eine volle Minute verdeckt keine Identitätslücke (mehrdeutige Herkunft, NHL-Spiel nicht mehr im
    Spielplan). Ohne Protokoll, bei unlesbarem und bei beschädigtem Protokoll bleibt das Verhalten wie vorher.
  - B: einmal warten und wiederholen; ohne Schalter nie warten; bei Dauer-429 nur eine Wartezeit je Instanz; nur 429
    wird wiederholt; die vier Stellen im Lauf benutzen den Helfer; der Standard-Provider der RisikoBet-Ergebnisse
    wartet, ein übergebener Provider bleibt, wie er ist.
  - C: keine Einzelabrufe nach einem 429; der Rückfall bei anderen Fehlern bleibt, auch wenn ein früherer Abruf
    desselben Providers abgelehnt wurde.
- Gegen unverändertes `main` (eigener Checkout, Testdatei hineinkopiert) schlagen 23 der 28 Tests fehl. Die fünf
  übrigen halten fest, was gleich bleiben muss: die beiden Identitätslücken bei voller Minute, die Auffrischung
  ohne Protokoll und mit unlesbarem Protokoll, der Rückfall auf Einzelabrufe bei anderen Fehlern.
- 44 Mutationsproben am geänderten Code, nur im Speicher (zum Beispiel Grenze zehn statt neun, Fenster 30 statt 60
  Sekunden, Warteliste nicht gelesen, Wartezeit ohne Schalter): Jede wird von mindestens einem Test gefangen.
- Zwei unabhängige Prüfrunden, jeder Befund gegengeprüft. Kein Befund über „niedrig“. Bestätigt und eingearbeitet:
  - Runde 1 (Wiederholung, Minutengrenze, Betrieb, Tests und Doku): das wiederholte Verdrängen desselben Spiels,
    die verdeckte Identitätslücke, drei Testlücken, die falsche Zahl zum Scanner, die fehlende Folge im Betrieb,
    die RisikoBet-Ergebnisse ohne Wartezeit.
  - Runde 2 (Nachbesserungen, Mutationsproben, Notiz gegen Code): die Warteliste war nach Anstoss statt nach
    Wartezeit geordnet, sechs Testlücken, vier ungenaue Sätze in Notiz, STATUS und Kommentar, die Folge für ein
    verschobenes wartendes Spiel.
- Die neue Testdatei läuft in der CI im Job `price-policy` unter beiden Preisregeln (Linux).
- Lokal mit dem Endstand: 32 betroffene Testdateien unter der alten Preisregel (1380 bestanden, 3 Fehlschläge),
  zehn betroffene Dateien unter der Produktionsregel, darunter acht aus dem CI-Job (559 bestanden), Ruff sauber.
- Die Fehlschläge bestehen genau so auf unverändertem `main` und haben nichts mit dieser Änderung zu tun
  (gegengeprüft in einem eigenen Checkout von `main`):
  - Unter der alten Preisregel drei: `test_forecast_consumer_reuses_exact_cached_price_without_network`
    (`tests/test_team_sport_prices.py`), `test_native_conflicting_role_ids_fail_before_any_request`
    (`tests/test_api_hockey_prices.py`) und
    `test_active_15k_model_surface_obeys_bound_floor_before_slot_selection[1.2-True]`
    (`tests/test_shared_quote_observations.py`).
  - Unter der Produktionsregel 25 in denselben drei Dateien (6, 1 und 18), auf `main` und auf dem Zweig gleich
    viele.
  - Keine dieser Dateien läuft in den automatischen CI-Jobs (`quick`, `price-policy`); die manuelle Vollsuite
    enthält sie.

## Offen

- Nach dem Release die nächste Nacht lesen: `sources.football.next_day.status` ohne `partial_operational_errors`,
  kein 429 im Abrufprotokoll nach der Preisauffrischung. Wie viele Spiele warten, zeigt die Länge von
  `minute_deferred` in `team_sport_quotes.json` (und `checked` je Lauf); der Eintrag „minute_limit“ steht je
  Sportart und Lauf nur einmal.
- Die manuelle Eishockey-Suche in der App schickt einen Abruf je Tag ohne Pause: 9 bei sieben Tagen, 16 bei 14
  Tagen. Mit 14 Tagen kann sie die Sperre weiter auslösen. Hintergrundläufe fangen das mit ihrer einen Wartezeit
  ab, der Shadow-Lauf nicht. Nicht Teil dieser Reparatur.
- Owner-Entscheid: Ein bezahlter Tarif für Eishockey und Basketball würde die Grenze von zehn Abrufen je Minute
  heben. Nötig ist er für die Reparatur nicht.
