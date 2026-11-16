# Nachtlauf: heute zuerst veröffentlichen

Stand: 16.11.2026. Owner-Auftrag «Ja, reparieren» zum Gesamtaudit vom 16.11.2026
(`AUDIT_BERICHT_2026-11-16_CLAUDE.md`, Befund H5, Massnahme 1). Nur Code und Tests, keine
Änderung an den systemd-Einheiten, keine neuen API-Abrufe. **Nicht live**, Release braucht «live stellen».

## Das Problem

Der Nachtlauf startet um 03:35 und wird nach 60 Minuten abgebrochen, ohne Neustart. Bisher schrieb er
das Tagesdokument genau einmal, ganz am Schluss. Davor liefen die Suche für morgen und ein reiner
Hintergrundschritt (`football_appearances`). Ein langsamer Scan für morgen verzögerte deshalb heute,
und ein Abbruch kostete den ganzen Tag: keine Liste, kein Doublebet, kein 15K, keine Evidenz.

Gemessen (lokale Journal-Auszüge): Am 03.11. brauchten die Suche für morgen 336 s und der
Hintergrundschritt 291 s, zusammen 32 % der Zeit bis zur Veröffentlichung. Am 05.11. brauchte die Suche
für morgen 841 s; zusammen mit dem Hintergrundschritt rund die Hälfte der Zeit.

## Was sich ändert

| | vorher | jetzt |
|---|---|---|
| 1 | Fussball heute suchen | Fussball heute suchen |
| 2 | **Fussball morgen suchen** | Tennis, Quoten heute, RisikoBet, Evidenz heute |
| 3 | Tennis, Quoten heute, **Quoten morgen**, RisikoBet, Evidenz heute | **heute veröffentlichen** (`forecast_publication`), Tipp-Belege (`tip_receipts`) |
| 4 | **Hintergrundschritt** | Fussball morgen suchen, Quoten morgen, Nachtspiel-Evidenz |
| 5 | Nachtspiel-Evidenz | **zweites Schreiben** mit morgen (`forecast_publication_next_day`) |
| 6 | veröffentlichen, Tipp-Belege | Hintergrundschritt, drittes Schreiben mit seinem Bericht (`forecast_publication_final`) |

Die anderen Sportarten für morgen (Eishockey, Basketball, E-Sport) bleiben vor dem ersten Schreiben. Sie
sind dann schon geladen und stehen bereits in der ersten Datei.

Zwischen dem ersten und dem zweiten Schreiben steht in der Datei `sources.football.next_day.status`
= `pending`. Die App liest diesen Status nicht; sie zeigt in dieser Zeit heute ohne die Fussballspiele von morgen.

**Stirbt der Lauf nach dem ersten Schreiben** (Abbruch nach 60 Minuten, Fehler im Code für morgen), bleibt
die Datei von heute stehen: vollständig, mit Tipp-Belegen und Evidenz. Der Lauf endet dann mit Exit 1
und Alarm. Es fehlen in dieser Nacht die Fussballspiele von morgen, die Nachtspiel-Evidenz und der
Hintergrundschritt.

Wirkung auf die Uhrzeit, aus den Messungen hergeleitet (keine neue Messung): Am 03.11. wäre heute nach
rund 23 statt 33 Minuten öffentlich gewesen, am 05.11. nach rund 21 statt 42 Minuten.

## Drei Regeln für die Uhren

Die Zeilen von morgen entstehen jetzt nach dem Veröffentlichungszeitpunkt `generated_at`. Drei Stellen
vergleichen gegen diese Uhr:

1. **`generated_at` bleibt.** Es wird beim zweiten Schreiben nicht vorgestellt. Die Zeilen von heute
   tragen ihre Preisprüfung zu genau dieser Uhr; der Leser verwirft sonst das ganze Dokument.
2. **Eigene Preisuhr für morgen.** Die Fussballzeilen von morgen tragen `reference_price_evaluated_at`
   (Zeitpunkt ihrer Preisprüfung). Ohne sie prüft der Leser die Quote zur Uhr `generated_at`, sieht
   einen Stempel «aus der Zukunft» und hält die Zeile zurück. Gegenprobe: ohne die Preisuhr listet die
   App 0 von 2 Zeilen, mit ihr 2 von 2, unter beiden Preisregeln.
3. **`decision_at` im Dokument.** Mit dem zweiten Schreiben bekommt das Dokument den Schlüssel
   `decision_at` (neu). Die Evidenz nimmt ihn vor `generated_at` (`forecast_evidence.py`,
   `record_forecast_run` und `record_current_closing_quotes`). Ohne ihn würden die Nachtspiele als
   «Modell aus der Zukunft» abgelehnt, und ein späterer Quotenlauf verlöre ihre Schlussquoten.
   Die Zeilen von heute sind schon vorher zur Uhr `generated_at` gespeichert.

Mit fester Uhr (Tests mit `now=`) entstehen weder `decision_at` noch die Preisuhr; alle bisherigen
Erwartungen bleiben gleich.

## Was gleich bleibt

- Der Teil von heute im Dokument ist derselbe wie vorher. Test: zweites Dokument ohne die Zusätze für
  morgen ist gleich dem ersten.
- Reihenfolge der gespeicherten Zeilen: heute, Fussball morgen, andere Sportarten morgen.
- Ein Anbieterfehler in der Suche für morgen wird wie bisher abgefangen (Status `failed`) und bekommt
  sein zweites Schreiben. Ein Programmierfehler bleibt laut (Exit 1), heute ist dann schon öffentlich.
- Tipp-Belege laufen einmal je Lauf, direkt nach dem ersten Schreiben.
- Ein Lauf ohne Folgetag schreibt wie bisher einmal (in Produktion zweimal, wegen des Hintergrundberichts).
- Sperre gegen den Quotenlauf, Exit-Code aus dem letzten Dokument, systemd-Einheiten: unverändert.

## Tests

Neu in `tests/test_wettfinder_next_day.py` (10), `tests/test_wettfinder_next_day_other_sports.py` (1),
umgestellt in `tests/test_wettfinder_stage_diagnostics.py` (der Reihenfolge-Test war seit dem Folgetag rot):

- Abbruch in der Suche für morgen, in der Preisprüfung für morgen und ein Programmierfehler: Die Datei
  auf der Platte ist der Lauf ohne Folgetag, der Leser nimmt sie an, die Evidenz von heute ist gespeichert.
- Reihenfolge: Suche heute, Schreiben, Suche morgen, Schreiben; im Produktionspfad zusätzlich
  Hintergrundschritt und drittes Schreiben, Tipp-Belege genau einmal.
- Laufende Uhr: Nachtspiel als Evidenz gespeichert (1, abgelehnt 0), Leser listet beide Zeilen von
  morgen, Schlussquote des Nachtspiels in einem späteren Quotenlauf gespeichert.
- Gegenproben: Ohne die Preisuhr und ohne `decision_at` schlagen genau diese Tests fehl.

Die drei Dateien laufen neu auch in der CI unter beiden Preisregeln (`.github/workflows/tests.yml`).

## Was damit nicht gelöst ist

- Die Gesamtdauer sinkt nicht. An einem vollen Samstag kann der Abbruch nach 60 Minuten weiterhin die
  Suche für morgen oder den Hintergrundschritt treffen. Dann fehlen morgen und die Nachtspiel-Evidenz
  dieser Nacht (Anstösse 00:00 bis 04:30 werden dann nicht abgerechnet). Heute bleibt.
- Vor dem ersten Schreiben stehen weiter die eigenen langsamen Schritte von heute: Tennis (Deckel
  30 Minuten), RisikoBet-Ergebnisse, die anderen Sportarten für morgen, die Quotenabfrage von heute ohne
  Zeitgrenze. Ein Hänger dort kostet weiterhin heute.
- Der Hintergrundschritt wird jetzt am ehesten abgeschnitten. Seine bis zu 20 Spiele warten dann einen Tag.
- Tagsüber von Hand gestartet: Zwischen dem ersten und dem zweiten Schreiben fehlen die Fussballspiele
  von morgen kurz in der Liste.
- Der Standard-Scan für morgen nach Abschluss des Mitschnitt-Budgets von heute ist nur durch Lesen des
  Codes belegt (alle Tests speisen den Scanner ein). Erster echter Beleg ist die erste Nacht nach dem Release.
- Arbeitsspeicher: Die Suche für morgen läuft jetzt, während das Dokument von heute im Speicher liegt.
  Der Spitzenwert ist unbekannt (früher gemessen: 2,6 GB bei 3,8 GB).

## Nach dem Release prüfen (erste Nacht, nur lesen)

1. Stufenfolge im Journal: `forecast_publication`, `tip_receipts`, `football_discovery_next_day`,
   `forecast_publication_next_day`, `football_appearances`, `forecast_publication_final`.
2. Uhrzeit des ersten `forecast_publication` und Gesamtdauer.
3. Im Dokument: `sources.football.next_day.status` ist `listed` (nicht `pending`), `decision_at` liegt
   nach `generated_at`, `forecast_evidence_night_games.rejected_count` ist 0.
4. Die App zeigt die Fussballspiele von morgen.
5. `MemoryPeak` der Einheit.
6. `closing_evidence` der Quotenläufe um 00:15 und 03:15: Nachtspiele gespeichert, nichts abgelehnt.

Release am besten bis Donnerstag, 19.11. abends: Dann ist die Nacht auf Freitag die Probe vor dem
ersten vollen Liga-Wochenende.
