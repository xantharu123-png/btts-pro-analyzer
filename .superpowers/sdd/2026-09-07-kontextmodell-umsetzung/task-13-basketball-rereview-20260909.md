# C2-Nachreview — Teilnehmerrevisionen, Zeitgrenzen und B1-Anschluss

9. September 2026. Disposition: **Änderungen erforderlich**.

Eingefrorener Prüfstand: `0d6accca7d3273d125ae080b3a1254ee506dea57`,
Vergleich gegen `8cffd12da3c4db530e76fcd94aea3eb58e1c533a`, im owning Worktree
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-c2-basketball-20260909`.
Der gesamte Fünf-Dateien-Diff sowie der vollständige neue Fix-Audit wurden
gelesen. Keine geprüfte Datei wurde verändert. Alle ursprünglichen 52 Probes
und der ursprüngliche Bericht bleiben bytegleich.

## Ergebnis der gezielten Korrekturen

Die ursprünglichen F1/F2/F3-Reproduktionen sind unverändert geschlossen:
**250 Tests bestanden**, einschließlich 166 ursprünglicher C2-Tests, der 32
neuen permanenten Fälle und aller 52 unabhängigen Originalprobes.

Der Source-Subject bindet nun die tatsächliche gemeinsame Teilnehmeridentität;
der interne C2-Selector nimmt weiterhin nur die jüngste Event/Kind-Revision.
Bei gleichbleibender Terminrevision bleiben frühere Teilnehmer durch B1
sichtbar, ohne deren alte Minuten wiederzuverwenden. Die volle kausale
Case-Schreibweisenprüfung ist ebenfalls wirksam. Die zeitweise Ausschließbarkeit
eines alten Konflikts wird pro Fenster und gegen das bewiesene letzte Ende
geprüft; verwendete Ausschlussbelege bleiben gebunden.

Die zusätzlichen **47** eigenen Nachreviewfälle ergeben jedoch **4 rote / 43
grüne** Fälle. Zwei weitere präzise Rand-/Anschlussfehler verhindern die
abschließende technische Freigabe. Das sind keine wieder geänderten alten
Erwartungen, sondern separat eingefrorene neue Repros.

## F4 — P1: Ein bei Cutoff beendetes Spiel verschwindet aus der Erholungshistorie

Fundstelle: `context_models/team_sports.py:500–503`.

Eine vollständig gemessene, abgeschlossene native Partie hat
`actual_end == result_observed_at == observed_at == cutoff`. Das ist nach den
öffentlichen Source-/B1-Zeitregeln am Stichtag bekannt. Die Normalisierung,
Append-Persistenz und `observations_as_of` nehmen den Beleg rechtmäßig auf.
Der gemeinsame C2-`load`-Filter verlangt aber `actual_end < stamp` und entfernt
ihn vollständig. Dadurch wird eine andere, vor 30 Stunden beendete Partie
fälschlich zum letzten beobachteten Spiel.

Die End-to-end-Repros für beide Seiten erhalten **36 Stunden exakt** statt
der tatsächlich belegten **6 Stunden** bis zum bevorstehenden Anpfiff.
Ein um 1 µs früheres Ende funktioniert; eine erst um 1 µs später empfangene
Partie wird richtig noch nicht berücksichtigt. Nur der exakt kausale
Gleichheitsfall ist falsch.

Unveränderte Reprodatei: `test_c2_rereview.py`.
Test: `test_actual_completed_end_at_decision_cannot_make_older_game_look_most_recent`
mit `[0-home]` und `[0-away]`.

Root hat F4 und die enge Korrekturgrenze bestätigt: In der beobachteten
Gesamt-/Erholungshistorie sind rechtzeitig bekannte Enden `<= cutoff` zulässig.
Die vorab festgelegten 1/3/7-Tage-Lastfenster bleiben dagegen halboffen und
behalten rechts `< cutoff`. Kein Modellparameter, keine Mindestquote und keine
allgemeine Zeit- oder Datenregel muss dafür gelockert werden.

## F5 — P1 / F1-Anschluss: Gleichzeitige Terminrevision verliert Teilnehmerlineage

Fundstellen: neuer Source-Subject in `context_sources/basketball.py:141–148`
zusammen mit dem noch nicht vorhandenen C2-owning Mehrtermin-Lineage-Lesevertrag.
Die relevante unveränderte allgemeine B1-Grenze ist
`context_observations.py:198`, die frühere `schedule_revision` absichtlich
aus der angefragten aktuellen Terminrevision ausschließt.

Das Gegenbeispiel korrigiert ein jüngeres historisches Event gleichzeitig in
Teilnehmer, Termin und `schedule_revision`. Die neue gemeinsame Spielerprojektion
ist ausdrücklich unvollständig und beide tatsächlichen Spielzeiten unbekannt.
Die exakt normalisierten Receipts ergeben bei direkter vollständiger Übergabe
an C2 korrekt unbekannte Ruhe und kein vollständiges beobachtetes Fenster.

Nach echter SQLite-Persistenz liest der Repro dieselben Daten über den normalen
öffentlichen B1-Aufruf mit der korrigierten aktuellen `schedule_revision`, so
wie die End-to-end-Tests dieses Pakets. Der ältere native Teilnehmerbeleg liegt
weiter unverändert in der Datenbank, wird aber durch den Terminscope nicht
zurückgegeben. Der neue Teilnehmer-Subject allein verhindert diesen Verlust
nicht. C2 behauptet danach für den ehemaligen Teilnehmer erneut **36 Stunden
exakt** und ein vollständiges Drei-Tage-Fenster.

Zwei unveränderte Repros in `test_c2_schedule_lineage_rereview.py`, Test
`test_partial_participant_and_schedule_correction_retains_former_teams_unknown_load`
für `[home]` und `[away]`.

**Genaue Scope-Einordnung:** Dies ist kein Defekt der allgemeinen
terminstrengen B1-Auswahl und kein Beweis, dass deren Filter gelockert werden
sollte. Es ist eine noch ungeschlossene owning C2-Lese-/Transportgrenze für
historische Teilnehmerlineage über mehrere Terminrevisionen. Der heutige
Produktivworker/Provider ist ohnehin noch nicht angeschlossen; der Fehler ist
am bereits vorhandenen öffentlichen Source→SQLite→Feature-Pfad reproduziert,
nicht als Behauptung über einen tatsächlichen Livebasketballlauf.

Eine zulässige Lösung braucht einen ausdrücklich owning historischen Reader
oder Transport, der kausale Identitäts-/Revisionsbelege vollständig beibehält,
oder eine nachweisbar unvollständige Lineage darf keine `exact`/`complete`-Werte
zertifizieren. Alte Terminwerte, Minuten und Besetzungen werden dadurch nicht
zu aktuellen Tatsachen. Keine pauschale Änderung des B1-Filters und keine
ungefragte Änderung des allgemeinen Datenvertrags. Der Befund samt dieser
Minimalgrenze wurde Root vor Abschluss zur Einordnung gesendet.

## Weitere unabhängige positive und negative Belege

Die 45 Fälle in `test_c2_rereview.py` enthalten neben F4:

- **24** tatsächliche SQLite-Reihenfolge-/Teilnehmerfälle: Home/Away verlässt
  das Event und kehrt zurück, vollständige oder unvollständige letzte Revision,
  alle sechs Insertreihenfolgen dreier zeitlich klarer Änderungen. B1 behält zwei
  Subjects; C2 zählt keinen alten Minutenblock doppelt. Vollständige Rückkehr
  gibt 18 Stunden/530 beobachtete Minuten korrekt, unvollständige Rückkehr bleibt
  unbekannt. Der tatsächlich gefittete B2→C2/B3-Vergleich ist nur im gültigen
  Fall experimentell, sonst `not_applied`; ohne Approval bleiben Originalbytes
  verwendet.
- **6** tatsächliche Source-/B1-Unknown-Refreshfälle für beide Seiten bei
  Cutoff −1/0/+1 µs. Neueste unbekannte Enden/Minuten ersetzen bekannte Werte,
  zukünftige Belege werden nicht vorweggenommen.
- **4** echte SQLite-Simultankonflikte: gleiche oder verschiedene Teilnehmer,
  beide Insertreihenfolgen. Beide konkurrierenden Belege bleiben erhalten und
  lassen keine exakte Ruhe/Completeness entstehen.
- **3** native EuroLeague-Case-Kollisionen bei −1/0/+1 µs. Rechtzeitig bekannte
  Kollisionen erhalten die Originalzahlen, aber keine native Kontextreferenz;
  künftige Schreibweisen verändern keine frühere Provenienzentscheidung.
- Eine alte, tatsächlich für die Basis benötigte Referenzrotation wird durch
  unvollständigen Teilnehmerwechsel nach SQLite nicht aus alten vollen Minuten
  geheilt. Eine vollständige Teilnehmerkorrektur entfernt umgekehrt die alten
  Minuten rechtmäßig, statt sie aus dem behaltenen Identitätsbeleg zu reaktivieren.

Die ursprünglichen Null-/Ridge-/Preis-/Cricket-/Mutationstests wurden im
250er-Lauf unverändert mitausgeführt. Die Ausnahme bei der vorhandenen
Subject-Assertion ist die vollständig gelesene, genehmigte präzise neue
Identitätsformel; die Assertion wurde nicht abgeschwächt oder entfernt.

## Eigene Laufnachweise

Interpreter unverändert:
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
Jeder Aufruf mit `-B -m pytest -q -p no:cacheprovider` und frischem Basetemp.

| Basetemp | Umfang | Tatsächliches Ergebnis |
| --- | --- | --- |
| `c2-rereview-original-01` | 166 Original + 32 neue permanente + 52 ursprüngliche Reviewerfälle | **250 bestanden**, 47.81 s |
| `c2-rereview-attacks-01` | neue eigene 45 Source/B1/Feature/Effect-Fälle | **2 fehlgeschlagen / 43 bestanden**, 52.43 s |
| `c2-rereview-schedule-01` | zusätzliche neue Termin-Lineage-Gegenfälle | **2 fehlgeschlagen**, 3.46 s |

Diese Summen ergeben 297 ausgeführte Fälle, davon 293 grün und vier rot; dies
war kein zusätzlicher gemeinsamer 297er-Einzelaufruf. Beim letzten Shellaufruf
folgte auf pytest noch die read-only Hashausgabe, daher ist dessen äußerer
Shell-Exitcode nicht der pytest-Status; die beiden tatsächlichen roten
pytest-Ergebnisse sind oben unverändert erfasst.

Die komplette Suite dieses Fixstands wurde im Nachreview wegen der konkreten
offenen Befunde nicht zusätzlich ausgeführt. Der vollständig gelesene
Controller-Audit dokumentiert **3.771 bestanden / 15 erwartete Plattformskips /
97 Untertests**, 117.63 s. Das ist Controller-Evidenz, nicht ein eigener neuer
Fullsuite-Lauf und kein Gegenbeweis zu den vier neuen REDs.

## Geprüfte SHA-256-Bindungen

```text
9613030dce16c193e0eec8c215c68a33992bdb10532606692d08e8bef7d64505  context_models/team_sports.py
7e75bdfee94b68616665be7a27d23bba15566cda962082521c2e82c4b197a696  context_sources/basketball.py
f6d90d61f143754591efae950ffe93e2655a3476e59fd7dcf40dbed1193a88cd  tests/test_basketball_context.py
c400d38941b8ee31831ff38e28ab22148d71b7fe29259699e0650feb7f142b20  tests/test_basketball_revision_recovery.py
07da2ab16c0eebb1b9ad8b5221401f58fdad06d15249756312dfd9e36b933238  docs/audits/2026-09-09-c2-revision-recovery-fix.md
9fb1ec38ac12dd3b142ab1b23e9c49cf605e77cd931e38c503f69026d0cec226  context_observations.py
fc1253fbeb0888870715c21238d4da78de2c0cbe19fee910da67ebfd35b756d7  sports_prematch.py
763b105a712418c8963b6f620ecea75eb8b42fec54b3775f9587c6e235737b9d  context_models/contracts.py
6caa81aa7ac7f188cfef689b688cc0deb452515b8ba8f7fad2f8e5b2f27d6dac  context_snapshots.py
```

Neue Reviewerdateien in diesem Ordner, jetzt eingefroren:

```text
8680ccfcf7282feeb64b5a54d9f4a6e156f937906b74c3083e1d620b79b98cba  test_c2_rereview.py
b1328ac79ee457e7fd101d378bfd36122a9fb46421c0a50eb70410d07e4da429  test_c2_schedule_lineage_rereview.py
```

Unveränderte ursprüngliche Repros und Bericht:

```text
4d21d7b3930dd64f4f965e05e6e776bf6fe1382576a528afd800db807ef9563d  test_c2_independent.py
1d1f0e054e523a29816bf9c602f63e24982e5cf2a6970707d217097efe920b94  test_c2_receipts_and_effects.py
f2bf5075611553425b4d65ecfa52c9bc3592c7804f52ab1bf1b021ec62be27c3  test_c2_conflict_negative_controls.py
5b2af671ff6523a70c1d51aa8c442b04592d67803f070a21edfb2b742454c738  review-c2.md
```

Alle Freezehashes wurden nach den Läufen erneut geprüft; Worktree sauber und
`git diff --check` ohne Befund. Keine Source-/Git-/Provider-/VPS-Änderungen.
Eigene Tests/Reports und deren temporäre lokale Datenbanken liegen ausschließlich
im Reviewer-QA-Bereich.

## Abschlussgrenze

Erst nach gezielter Korrektur von F4 und des F5-Anschlusses folgt erneutes
unabhängiges PASS/Reject. Eine erfolgreiche technische Korrektur wäre weiterhin
keine reale Feed-, Datensatz-, D1-/D2-, empirische oder Produktivfreigabe. Die
entsprechenden offenen Grenzen bleiben unverändert.
