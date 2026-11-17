# Nachtlauf: heute zuerst veröffentlichen

Stand: 16.11.2026. Owner-Auftrag «Ja, reparieren» zum Gesamtaudit vom 16.11.2026
(`AUDIT_BERICHT_2026-11-16_CLAUDE.md`, Befund H5, Massnahme 1). Nur Code und Tests, keine
Änderung an den systemd-Einheiten, keine neuen API-Abrufe. **Nicht live**, Release braucht «live stellen».
Die Änderung wurde am selben Tag von fünf unabhängigen Prüfern gegengeprüft, siehe unten.

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
Hintergrundschritt. Der Status bleibt dann `pending`. Die Quotenläufe holen morgen nicht nach; erst der
nächste Start des Tageslaufs sucht morgen neu (das kostet den Scan für morgen, also API-Abrufe).

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
   Die Zeilen von heute sind schon vorher zur Uhr `generated_at` gespeichert. `decision_at` gibt es
   nur, wenn Fussballzeilen für morgen gelistet sind (Status `listed` oder `listed_partial`). Nach
   einer fehlgeschlagenen Suche oder ohne Spiele für morgen fehlt der Schlüssel zu Recht.

Folge für die Quotenläufe: Ein Spiel von heute, das zwischen `generated_at` und `decision_at` anfängt
(in Produktion etwa 03:55 bis 04:20, zum Beispiel NHL oder Liga MX), liegt vor der Entscheidungsuhr des
Dokuments. Ohne Korrektur zählte jeder Quotenlauf des Tages ein solches Spiel als «abgelehnt».
`record_current_closing_quotes` überspringt deshalb Spiele, die schon laufen, statt sie zu zählen. Eine
Schlussquote können sie ohnehin nicht mehr bekommen. `rejected` heisst damit weiter «unerwartet».

Mit fester Uhr (Tests mit `now=`) entstehen weder `decision_at` noch die Preisuhr; alle bisherigen
Erwartungen bleiben gleich.

## Was gleich bleibt

- Der Teil von heute im Dokument ist derselbe wie vorher. Test: zweites Dokument ohne die Zusätze für
  morgen ist gleich dem ersten.
- Reihenfolge der gespeicherten Zeilen: heute, Fussball morgen, andere Sportarten morgen.
- Ein Anbieterfehler in der Suche für morgen wird wie bisher abgefangen (Status `failed`) und bekommt
  sein zweites Schreiben. Ein Programmierfehler bleibt laut (Exit 1), heute ist dann schon öffentlich.
- Tipp-Belege laufen einmal je Lauf, direkt nach dem ersten Schreiben. Ein Fehler, den sie nicht selbst
  abfangen, endete bisher nach dem letzten Schreiben mit Exit 1. Das bleibt so: Der Fehler wird
  aufgehoben, morgen, Nachtspiel-Evidenz und Hintergrundschritt laufen noch, danach Exit 1 und Alarm.
  Ein Abbruch (Kill) wird nie aufgehoben. Im Journal nennen zwei Zeilen der Stufe `tip_receipts` den
  Schritt und den Fehlertyp (Phasen `failed_held` und `failed_raised`). Die zweite steht direkt vor der
  Fehlermeldung, weil der Alarm nur die letzten Journalzeilen zitiert.
- Ein Lauf ohne Folgetag schreibt wie bisher einmal (in Produktion zweimal, wegen des Hintergrundberichts).
- Sperre gegen den Quotenlauf, Exit-Code aus dem letzten Dokument, systemd-Einheiten: unverändert.

## Tests

Neu in `tests/test_wettfinder_next_day.py` (27), `tests/test_wettfinder_next_day_other_sports.py` (1),
`tests/test_forecast_evidence.py` (2), umgestellt in `tests/test_wettfinder_stage_diagnostics.py` (der
Reihenfolge-Test war seit dem Folgetag rot):

- Abbruch in der Suche für morgen, in der Preisprüfung für morgen und ein Programmierfehler: Die Datei
  auf der Platte ist der Lauf ohne Folgetag, der Leser nimmt sie an, die Evidenz von heute ist gespeichert.
- Reihenfolge: Suche heute, Schreiben, Suche morgen, Schreiben; im Produktionspfad zusätzlich
  Hintergrundschritt und drittes Schreiben, Tipp-Belege genau einmal.
- Laufende Uhr: Nachtspiel als Evidenz gespeichert (1, abgelehnt 0), Leser listet beide Zeilen von
  morgen, Schlussquote des Nachtspiels in einem späteren Quotenlauf gespeichert.
- Produktionspfad (private Datei): Ein Lauf ohne Folgetag (nicht verlangt, Suche heute fehlgeschlagen,
  Suche heute unvollständig) ist mit Belegen öffentlich, bevor der Hintergrundschritt läuft. Ein Lauf
  mit laufender Uhr schreibt drei Dateien mit derselben Uhr `generated_at`; der Leser nimmt jede an und
  listet für morgen 0, 2 und 2 Zeilen.
- Fehlerpfade: Ein Fehler in den Tipp-Belegen kostet morgen nicht und bleibt laut: Genau dieser Fehler
  kommt am Schluss an, auch nach einem Fehler im Hintergrundschritt und auch, wenn schon der Import
  scheitert. Ein Kill in den Belegen beendet den Lauf sofort. Ein Fehler im Hintergrundschritt stuft nur
  die letzte Datei herab. Scheitert das erste Schreiben, wird für morgen nichts mehr gesucht.
- Uhren ohne Zeilen für morgen: kein `decision_at`, dieselbe Uhr `generated_at`. Morgen ohne
  Preisprüfung: `decision_at` liegt trotzdem hinter den Modelluhren, das Nachtspiel ist Evidenz. Nach
  einer langsamen Veröffentlichung trägt die Suche für morgen die Uhr nach dem Schreiben.
- Ein Spiel von heute im Fenster zwischen den beiden Uhren: im späteren Quotenlauf `rejected` 0. Ein
  unlesbarer Anstoss zählt weiter als `rejected`; massgebend ist die Uhr des Quotenlaufs, nicht die des
  Dokuments.
- Gegenproben: 54 gezielt eingebaute Fehler im Schlussteil des Laufs (Reihenfolge, Schreiben, Belege,
  Uhren, Fehlerpfade) lassen unter beiden Preisregeln je mindestens einen Test fehlschlagen. Mit den
  Tests vor der Gegenprüfung überlebten 16 davon. Nach der zweiten Prüfrunde kamen 18 weitere dazu
  (Schutz der Tipp-Belege, Überspringen in `forecast_evidence.py`); auch sie werden alle gefangen.

Die drei Dateien zum Nachtlauf laufen neu auch in der CI unter beiden Preisregeln,
`tests/test_forecast_evidence.py` in der schnellen Teilmenge (`.github/workflows/tests.yml`).

## Gegenprüfung (16.11.2026)

Fünf unabhängige Prüfer (Verschiebung der Blöcke, Uhren, Leser, Fehlerpfade, Tests), jeder Befund von
einem zweiten Prüfer nachgebaut. Kein Befund gefährdet heute. Die verschobenen Blöcke sind bis auf die
oben beschriebenen Zusätze Zeile für Zeile gleich. In zehn Szenarien mit fester Uhr waren Dokument und
Datei Byte für Byte gleich wie auf dem Hauptstand.

Behoben:

- Ein unerwarteter Fehler in den Tipp-Belegen hätte neu die Suche für morgen, die Nachtspiel-Evidenz und
  den Hintergrundschritt gekostet (vorher nur den Exit-Code). Jetzt wie oben unter «Was gleich bleibt».
- Der Zähler `rejected` der Quotenläufe hätte Spiele im Fenster zwischen den beiden Uhren gezählt.
- Testlücken: Produktionspfad ohne Folgetag, Produktionspfad mit laufender Uhr, drittes Schreiben,
  Grenzen von `decision_at` und Preisuhr, beide Neulesungen der Uhr.

Nicht behoben, weil selten oder schon vorher so: siehe die Punkte zum Wiederholungslauf und zum ersten
Schreiben im nächsten Abschnitt. Rein rechnerisch gilt die Obergrenze der gespeicherten Zeilen (112'800)
nicht mehr für Fussball morgen und die anderen Sportarten morgen zusammen. Überschritten würde sie erst
mit über 108'000 Fussballzeilen für heute und morgen zusammen; ab dieser Zahl verwirft der Leser das
Dokument ohnehin, wie schon auf dem Hauptstand.

Zweite Runde (17.11.2026) auf dem Korrektur-Commit, drei Prüfer mit Nachprüfern: wieder kein Befund am
Verhalten. Eine Zufallsprobe mit 34'688 Läufen gegen den alten und den neuen Stand von
`record_current_closing_quotes` ergab dieselbe Datenbank und denselben Bericht bis auf `rejected`. In
434 Läufen brach nur der alte Stand ab: Dokumente mit unmöglichen Werten (Jahr 1 mit Zeitzone, Zahl mit
400 Stellen) bei einem Spiel, das schon läuft. Nachgezogen: die zwei Journalzeilen zum aufgehobenen
Fehler, fünf Testfälle zu den Grenzen des Schutzes und des Überspringens, Korrekturen an dieser Doku
(Prüfpunkt 6, Zahl der überlebenden Fehler, Zeilengrenze).

## Was damit nicht gelöst ist

- Die Gesamtdauer sinkt nicht. An einem vollen Samstag kann der Abbruch nach 60 Minuten weiterhin die
  Suche für morgen oder den Hintergrundschritt treffen. Dann fehlen morgen und die Nachtspiel-Evidenz
  dieser Nacht (Anstösse 00:00 bis 04:30 werden dann nicht abgerechnet). Heute bleibt.
- Vor dem ersten Schreiben stehen weiter die eigenen langsamen Schritte von heute: Tennis (Deckel
  30 Minuten), RisikoBet-Ergebnisse, die anderen Sportarten für morgen, die Quotenabfrage von heute ohne
  Zeitgrenze. Ein Hänger dort kostet weiterhin heute.
- Der Hintergrundschritt wird jetzt am ehesten abgeschnitten. Seine bis zu 20 Spiele warten dann einen Tag.
- Tagsüber von Hand gestartet: Zwischen dem ersten und dem zweiten Schreiben fehlen die Fussballspiele
  von morgen kurz in der Liste. Stirbt ein solcher Lauf genau dazwischen, sind sie bis zum nächsten
  gelungenen Lauf weg, der gespeicherte Stand für morgen auch: Der nächste Lauf sucht morgen neu
  (API-Abrufe), und die Quotenläufe der Nacht haben für die Nachtspiele keine Zeilen. Vorher blieb in
  diesem Fall die alte Datei stehen.
- Scheitert schon das erste Schreiben (Platte, Rechte), endet der Lauf dort. Vorher waren
  Nachtspiel-Evidenz und Hintergrundschritt dann schon erledigt; heute ging in beiden Fällen verloren.
- Der Standard-Scan für morgen nach Abschluss des Mitschnitt-Budgets von heute ist nur durch Lesen des
  Codes belegt (alle Tests speisen den Scanner ein). Erster echter Beleg ist die erste Nacht nach dem Release.
- Arbeitsspeicher: Die Suche für morgen läuft jetzt, während das Dokument von heute im Speicher liegt.
  Der Spitzenwert ist unbekannt (früher gemessen: 2,6 GB bei 3,8 GB).

## Nach dem Release prüfen (erste Nacht, nur lesen)

1. Stufenfolge im Journal: `forecast_publication`, `tip_receipts`, `football_discovery_next_day`,
   `forecast_publication_next_day`, `football_appearances`, `forecast_publication_final`. Vor
   `forecast_publication_next_day` können wie bisher `football_context_next_day` und
   `forecast_recording_night_games` stehen.
2. Uhrzeit des ersten `forecast_publication` und Gesamtdauer.
3. Im Dokument: `sources.football.next_day.status` ist `listed` oder `listed_partial` (nicht
   `pending`). Dann liegt `decision_at` nach `generated_at`; gibt es Anstösse vor 04:30, ist
   `forecast_evidence_night_games.rejected_count` 0. Bei jedem anderen Status (zum Beispiel `failed`)
   fehlen `decision_at` und der Nachtspiel-Block zu Recht.
4. Die App zeigt die Fussballspiele von morgen.
5. `MemoryPeak` der Einheit.
6. `closing_evidence` der Quotenläufe, erst **nach** dem ersten neuen Nachtlauf (tagsüber ab 06:15; für
   die Nachtspiele die Läufe 00:15 und 03:15 der Nacht danach, die Läufe davor lesen noch das alte
   Dokument): `rejected` 0. `recorded` ist nur über 0, wenn ein Spiel mit Referenzquote in der Stunde
   nach dem Quotenlauf beginnt (Anstoss etwa 00:16 bis 01:15 oder 03:16 bis 04:15). Ein Nachtspiel um
   01:30, 02:00 oder 02:30 bekommt aus diesen Läufen keine Schlussquote; `recorded` 0 ist dann kein
   Fehler, das war schon vorher so. Spiele, die schon laufen, werden übersprungen und nicht gezählt.

Release am besten bis Donnerstag, 19.11. abends: Dann ist die Nacht auf Freitag die Probe vor dem
ersten vollen Liga-Wochenende.
