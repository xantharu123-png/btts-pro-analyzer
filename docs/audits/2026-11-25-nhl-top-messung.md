# NHL im Wettfinder: Was für eine gleichberechtigte Auswahl fehlt

**Befund: noch keine Top-Freigabe.** Der eingefrorene Abdeckungslauf für
12.–24.11.2026, Spielbeginn Zürich, verwendet `forecast_evidence.db` zum
Stichtag 25.11.2026 10:31 CET (Produktionsbasis `9d8f945`). Die
[Vorab-Regel](../superpowers/plans/2026-11-25-nhl-top-vorab.md) wurde als
`d8bfda6` gepusht, bevor der neue Preisvergleich geöffnet wurde.

| NHL-Abdeckung | Spiele |
| --- | ---: |
| Erstes vollständiges kausales H2H-Modell | 84 |
| Davon Modellfavorit ab 60 % | 34 |
| Davon Modellfavorit ab angezeigten 70,0 % | 8 |
| Vollständiger Einstiegspreis aus derselben ersten Modellrevision | 0 |
| Spiele mit archivierten späteren Preiszeilen | 25 |

Die Null ist eine **Preisdatenlücke**, keine Null-Trefferquote. Der
Pilotbericht hat weder Ergebniszeilen gelesen noch einen Sportabruf gestartet;
die 25 späteren Fälle wurden nicht als ursprünglicher Preis umgedeutet.
Damit lässt sich nicht beurteilen, ob das Modell den Markt schlägt. Für
die Freigabefrage ist die Stichprobe selbst ohne Preisproblem zu klein.

## Ursache und Korrektur

Der reguläre Tageslauf vom 25.11. hatte die Teamquoten vor der
Evidenzspeicherung bereits in `team_sport_quotes.json` abgelegt, die
NHL-Modellzeilen aber ohne diese Belege archiviert. Der Quotenlauf speichert
ausdrücklich nur spätere Preise im passenden Schlussfenster und darf sie
nicht nachträglich als Einstieg zur ersten Prognose eintragen.

Der Korrekturpfad nutzt ausschliesslich bereits vorhandene, exakt gebundene
Cachepreise beider Seiten desselben Abrufs. Archiviert wird ein separater
NHL-Evidenzlauf mit seiner tatsächlichen Zeit **vor Spielbeginn**, ohne
Änderung von Modellzeit, Trainingsstichtag oder Wahrscheinlichkeit. Andere
Sportarten und der veröffentlichte Wettfinder behalten ihre bisherige
Zeit und Darstellung. Fehlende oder mehrdeutige Preispaare bleiben fehlend.
Der technische Abrufzeitpunkt ist kein Nachweis für ein aktuelles
ausführbares Angebot; aus diesen Preisen keine hypothetische Rendite in
der allgemeinen Prognosebilanz berechnen.

## Wiederholung

```bash
python -B nhl_top_review.py --db runtime_state/forecast_evidence.db --phase pilot
python -B nhl_top_review.py --db runtime_state/forecast_evidence.db --phase forward-coverage
```

`forward-coverage` beginnt nach dem ersten abgeschlossenen Tag der
festgeschriebenen Zukunftsperiode (26.11.–31.03.). `--phase open` ist erst
ab 03.04.2027 zulässig, auf genau diesen Zeitraum und Stichtag begrenzt
und bricht vor Lesen der Ergebnisse ab, falls die Preisabdeckung keine
hinreichende Stichprobe zulässt. Auch danach nur eine Prüfung anhand der
Vorab-Regel, keine Änderung am Ranking durch den Bericht.

## Technische Abnahme

37 neue Tests unter `floor`; breiter Regressionstest: 406 bestanden und
ein bereits an der Basis reproduzierter Fehler im alten Test
`test_forecast_consumer_reuses_exact_cached_price_without_network`.
Vollsuite als Kurzprobe: 99 bestanden, Stopp am bereits bekannten
`test_native_conflicting_role_ids_fail_before_any_request`. Unter erzwungenem
`floor` reproduzieren Vertragsfremdtests die 13 bekannten Baselinefehler.
Einschliesslich zweitem Archivschreibfehler geprüft: Reguläre Abrechnung
läuft weiter; optionaler NHL-Archivfehler separat gemeldet. Die
netzwerkisolierte Endfassung bestätigt die vier Abdeckungszahlen im
VPS-Archiv. Kein Deploy, keine neue Datensicherung, kein API-Lauf.
