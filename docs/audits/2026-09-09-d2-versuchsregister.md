# D2: unveränderliche Versuchsdefinition und erstes Öffnen des Tests

9. September 2026. Implementiert und unabhängig geprüft ist ausschließlich
die lokale Freeze-/Öffnungsmechanik, nicht die empirische Modellabnahme.

`context_models/experiments.py` prüft die vollständige geschlossene
Versuchsdefinition mit globaler nativer Eventidentität, Familienkonfigurationen,
unverändertem Zielmarktkatalog, festem Split, allen Hypothesen und ungelabeltem
Testinventar. Fehlgeschlagene oder nicht verfügbare Kandidaten verschwinden
nicht aus dem Register. Die freigegebene Statistik-/Preisregel bleibt unverändert.

Ein bereits geöffnetes kanonisches Event kann nicht durch neue Daten-/Code-/
Zeit-/Map-/Versuchshashes wieder zu einem unberührten Testfall werden. Zwei
vorab eingefrorene Versuche dürfen dieselben Events referenzieren; nur einer
kann sie erstmals öffnen. Exakte Wiederholungen bewahren den ursprünglichen
Öffnungszeitpunkt. Prüfung und INSERT laufen in derselben A1-IMMEDIATE-
Transaktion. Keine neue Tabelle, kein Force-Schalter und keine Event-Teilmenge.

## Nachreview und tatsächliche Gegenbeispiele

Das unabhängige Erstreview fand zwei P2-Fehler, reproduzierbar mit sechs roten
Tests: unvollständige Bindung der tatsächlichen A1-Erstellungszeiten sowie
ein beschädigter Artefakttyp, der die vorhandene Erstöffnung vor der Hashprüfung
aus der SQL-Auswahl verschwinden ließ. Root bestätigte6 rot/19 grün unverändert.

Die Korrektur bindet tatsächliche und behauptete Zeitpunkte auch bei bereits
vorhandenen INSERT-OR-IGNORE-Zeilen. Ein Effekt muss nach seinem Trainingsende
und spätestens beim Freeze existiert haben; die konkrete Identitymap spätestens
beim Freeze. Experiment und Erstöffnung müssen mit ihren normalisierten
tatsächlichen A1-Erstellungszeiten übereinstimmen. Vor Typdispatch wird das
gesamte A1-Byte-/Typ-/Hashinventar geprüft, ohne Case-/Ergebnisinterpretation.

20 zusätzliche permanente Tests ergaben zunächst18 rot/42 grün; nach der
Korrektur sind60 permanente und25 unveränderte Originalgegenproben grün.
Das unabhängige Nachreview ergänzte51 weitere Grenz-/Ersteinfügungs-/Zeitzonen-/
Korruptions-/Parallelitäts-/SQLite-Sperrfälle: insgesamt136 grün. Root wiederholte
den vollständigen136er-Gegenlauf selbst:4.88s, Exit0, kein Skip.

## Exakter geprüfter Stand

| Datei | SHA256 |
| --- | --- |
| `context_models/experiments.py` | `080bcf30cf48b14dafdb045611414cf9d82ce975d93ea951022fb99c3bd17ce1` |
| `tests/test_context_experiments.py` | `b071f2e5e70f14ca20b2f82a75d47e67da7ff3b3fcdb376ec66449bab8c66202` |
| unveränderte Originalgegenproben | `a180f183bb2178afe3cc20bb86b938d71392e8ed17f4f74e31a3449c1740e734` |
|51 neue unabhängige Gegenproben | `ef34a52a8eb6042275b0794d8299d6649547ed44d8450b932aa5856b9a3011e8` |
| vollständiger Nachreviewbericht | `6ecda1fd526c9ac91c6cd31940b3381d87a0eb6e36e1323d64c2cb759d99970d` |

Der Nachreviewbericht liegt byteidentisch unter
`.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-17-registry-final-review-20260909.md`.
Originalgegenproben und Erstbericht bleiben in
`.pytest_tmp/d2-registry-independent-20260909/` erhalten.

Die Globalmap wird hier nur strukturell geprüft; tatsächliche native Belege
müssen weiterhin durch D1 aufgelöst werden. Ein passender Alpha-Wert beweist
noch keinen richtigen Trainings-/Tuninglauf. Der Registercode stellt weder
`evaluate_experiment` noch BH-Ergebnis, `approved_effect` oder eine reale
200-Event-Abnahme bereit. Diese Integrationen folgen gesondert. Das Register
beweist nicht, dass jemand außerhalb des lokalen Ablaufs keine Resultate sah,
und schützt nicht gegen vollständiges Löschen/Neuschreiben der Datenbank samt
öffentlichen Hashes. Keine solchen weitergehenden Aussagen sind freigegeben.
