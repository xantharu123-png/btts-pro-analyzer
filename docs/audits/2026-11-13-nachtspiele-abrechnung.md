# Nachtspiele: Fussballspiele nach Mitternacht werden abgerechnet

Stand 13.11.2026. Owner-Auftrag „alles erledigen“ vom selben Abend, nach der Frage „wie waren die Spiele gestern“.

## Anlass

Von 74 Tipps mit Anstoss am 12.11. waren am Abend des 13.11. noch 34 offen. Alle gehörten zu 9 Spielen der
kolumbianischen Liga um 22:00 Uhr.

- **Diese 9 Spiele wurden verschoben.** Im Tagesdokument vom 13.11. stehen 8 davon mit derselben `fixture_id` und
  neuem Anstoss: 7 am 14.11. um 21:30 Uhr, Internacional de Bogotá gegen Santa Fe am 14.11. um 02:30 Uhr. Llaneros
  gegen Chico steht in keiner Liste mehr. Die Tipps sind also zu Recht offen. Ergebnisse hängen an Ereignis, Markt
  und Auswahl; ist das Spiel gespielt, bekommen auch die Tipps vom 11.11. ihr Ergebnis.
- **Dabei kam eine Lücke zum Vorschein:** Fussballspiele mit Anstoss nach Mitternacht werden nie abgerechnet.

## Befund

Nur gelesen, auf dem Server, Tipps mit Anstoss vom 01.11. bis 13.11.2026:

| Sportart | Anstoss (Zürich) | Spiele mit Tipp | mit Prognose | mit Ergebnis |
|---|---|---:|---:|---:|
| Fussball | 00:00 bis 04:00 | 4 | 0 | 0 |
| Fussball | 04:00 bis 24:00 | 363 | 353 | 348 |
| Eishockey | 00:00 bis 04:00 | 53 | 53 | 50 (3 vom 13.11. noch offen) |
| übrige | 00:00 bis 04:00 | 0 | – | – |

- Die vier Fussballspiele: 04.11. um 00:20 und 01:30, 06.11. um 00:00 und 01:30. Alle wurden am Vortag als
  „morgen“ gezeigt und bekamen nie ein Ergebnis.
- Die 10 Fussballspiele ab 04:00 ohne Prognose sind die 9 verschobenen Spiele aus Kolumbien und ein Spiel vom 06.11.
  (`football:1570006`), das nicht weiter untersucht ist.
- Eishockey ist nicht betroffen: Seit dem Oktober zählt ein NHL-Spiel innerhalb von 24 Stunden zum laufenden Tag
  (`team_sport_forecasts.automatic_team_sport_day`).

## Ursache

1. Ein Ergebnis wird nur zu einer Prognose gespeichert, die vor dem Anstoss gespeichert wurde
   (`forecast_evidence.append_result`: „result has no matching prospective forecast“). So ist es gewollt.
2. Der Nachtlauf speichert seine Prognosen zwischen 03:43 und 04:10 Uhr (Läufe vom 25.10. bis 13.11.). Ein Spiel um
   02:30 hat dann schon begonnen, und `record_forecast_run` weist es ab („forecast was not recorded prospectively
   before start“).
3. Am Vortag ist dasselbe Spiel eine Zeile für morgen. Diese Zeilen waren nach Regel nie Evidenz.

Ein Nachtspiel hatte also nie einen Lauf, der es vor dem Anstoss speichern durfte.

## Änderung

`wettfinder_automation.py`:

- `NIGHT_GAME_KICKOFF_BEFORE = (4, 30)` und `_night_game_rows`: Fussballzeilen des Folgetags mit Anstoss zwischen
  00:00 und 04:30 Uhr Zürcher Zeit.
- `_record_night_game_evidence`: Der Lauf speichert diese Zeilen als eigene Evidenz-Runde, mit seiner eigenen
  Entscheidungszeit und Policy, getrennt von der Runde des Spieltags.
- Das Tagesdokument meldet das Ergebnis unter `forecast_evidence_night_games` (`kickoff_before`, `recorded`,
  `rejected_count`, `status`). Scheitert das Speichern, gilt der Lauf als `degraded`, wie bei der Evidenz des
  Spieltags.
- Gespeichert wird nur, wenn der Lauf auch sonst Evidenz speichert (Produktion oder ein übergebener Evidenzpfad).

**Unverändert:** Die Nachtspiele bleiben am Vortag eine reine Vorschau. Sie werden nie Tipp, 15K-Zeile,
Doublebet-Wahl, Shadow oder Archiv. Andere Folgetagszeilen bleiben ohne Evidenz.

**Warum 04:30:** Der späteste beobachtete Speicherzeitpunkt war 04:10 Uhr (05.11.). Spiele zwischen 04:00 und 04:30
kann deshalb auch der Lauf des Spieltags noch speichern. Sie haben dann zwei Prognosen aus zwei Läufen, wie nach
einem Lauf von Hand. Die Abrechnung nimmt je Auswahl die erste Prognose mit vollständigen Modellzeiten.

## Folgen

- Die Abrechnung kann Nachtspiele abrechnen, sobald das Spiel beendet ist (Nachtlauf und jeder Quotenlauf).
- Tipps vom Vorabend werden an diese Prognosen gebunden (`tip_publication.bind_forecast_ids`), weil die Prognose vor
  der Veröffentlichung gespeichert ist.
- Einstiegsquoten der Nachtspiele werden mitgespeichert, wenn die Zeile eine Quote trägt.
- **Fallenfilter:** Die Regel bleibt unverändert. Nachtspiele bekommen ab dem Release Ergebnisse und können damit
  mitzählen. Im Bericht vom 30.11. nennen.

## Prüfung

- **Tests** in `tests/test_wettfinder_next_day.py`:
  - Ein Nachtspiel wird als Evidenz gespeichert, ein Tagesspiel des Folgetags nicht. Das Nachtspiel bleibt Vorschau
    ohne Tipp, 15K-Zeile und Archiv.
  - Ohne Evidenzspeicher wird nichts gespeichert.
  - Grenzen: 00:00 Uhr gehört dazu, 04:29:59 gehört dazu, 04:30 nicht, auch in der Sommerzeit.
  - Nur Fussball; eine unlesbare Anstosszeit fällt weg.
- **Trockenlauf auf den echten Daten vom 13.11.** (nur gelesen, nichts geschrieben): Das Tagesdokument enthält
  6 Nachtzeilen, alle von Internacional de Bogotá gegen Santa Fe (14.11. um 02:30). Die Prüfung von
  `forecast_evidence._normalize_row` nimmt alle 6 an; 5 davon tragen eine Quote.

## Grenzen

- **Wirkt erst nach dem Release.** Internacional de Bogotá gegen Santa Fe am 14.11. um 02:30 hätte der Lauf vom
  13.11. speichern müssen. Das ist vorbei; dieses Spiel bleibt offen.
- Die vier Spiele vom 04. und 06.11. bleiben offen. Nachträglich darf keine Prognose entstehen.
- Ein Spiel, das auf die Nacht verschoben wird, nachdem der Vortageslauf gelaufen ist, bleibt weiter offen.
- Ein Spiel, das nach dem Vortageslauf in die Nacht vorgezogen wird, bekommt ebenfalls keine Prognose.

## Zurücknehmen

Den Block nach `next_day_summary["status"] = …` in `run_wettfinder` entfernen, der `_night_game_rows` aufruft.
Gespeicherte Prognosen bleiben gültig.

## Release 20261113-1

Owner „Ja, live stellen“ am 13.11.2026.

- **Merge:** PR #125 um 22:04 CET, `origin/main` = `7efa8f556d74fb9542441d747be571fec6dadcd1`. Die CI war grün
  (ruff und schnelle Teilmenge; Lader, Publikation, Daily3 und 15K unter `floor` und `gate`).
- **Dateien:** 14, alle von `9aee28d` bis `7efa8f5`. Darunter liegt neben dieser Änderung das berichtigte
  Fallenfilter-Skript aus PR #123; sonst nur Doku und Tests. Keine Einheit, kein `.sh`, keine Requirements.
- **Generator:** `output/release-20261113-1/gen_deploy52.py`, abgeleitet von `gen_deploy51.py` über `make_gen.py`.
  Neue Asserts: `NIGHT_GAME_KICKOFF_BEFORE == (4, 30)`, `_night_game_rows` und `_record_night_game_evidence`
  vorhanden, Aufruf in `run_wettfinder`, `forecast_evidence_night_games`, `selection_entry_quotes` im Messskript.
- **Offline-Prüfung lokal** gegen einen Worktree von `7efa8f5`: `OFFLINE_RELEASE_IMPORTS=ok`.
- **Hochladen:** sha256 auf dem Server gleich (`deploy-20261113-1.sh` `db0883a7…`, `run_release-20261113-1.sh`
  `fa98a879…`).
- **Ausrollen:** Fenster um 22:12:50 (Abstand zum nächsten Shadow-Lauf 550 s). Ergebnis `HEAD=7efa8f5…`,
  `APP_PID=1600156->1621055`, `NO_NEW_BACKUP=yes`, `UNITS_UNCHANGED=yes`, `DEPLOY_EXIT=0`. Log
  `output/release-20261113-1/deploy-01.log`.
- **Danach (22:13):** Health lokal und öffentlich 200, alle Timer aktiv, keine neue fehlgeschlagene Einheit, die
  Live-Seite lädt. Der normale Fallenfilter-Befehl auf dem Server zählt jetzt nach der berichtigten Zuordnung
  (60 abgerechnete Tipps, 3 Fallen, 4 übrige mit Quote, 53 ohne).
- **Offen:** Der Nachtlauf am 14.11. um 03:35 ist der erste mit der neuen Regel. Er speichert die Nachtspiele vom
  15.11.; im Tagesdokument steht das Ergebnis unter `forecast_evidence_night_games`. Ob dann ein Ergebnis kommt,
  zeigt sich nach dem ersten Nachtspiel.
