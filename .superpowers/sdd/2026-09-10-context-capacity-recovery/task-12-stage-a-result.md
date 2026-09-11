# Task12 — A1 abgeschlossen: kein Stage-A-Produktumbau

Stand: 12. September 2026, nach Nutzerfreigabe des Plans05f7e6f.
Entscheidung: **A1 STOP.** Der begrenzte Ansatz erreicht keine belegbar
ausreichende Reserve. Damit folgt die im Plan vorgesehene Stufe-B-Spezifikation,
nicht ein weiterer spekulativer Cachepatch. Produktbytes bleiben72421d3.

## Unabhängige Rechnung aus dem vorherigen G1-Lauf

`task-12-stage-a-feasibility.md` ist vollständig gelesen. 13 abgeschlossene
Wiederholungen kosten21,713CPU-/21,717Wandsekunden einschließlich des zwingend
verbleibenden Dekodierens. Selbst deren vollständige Entfernung lässt im selben
instrumentierten Trace nach erst27/31 Analysen250,620Wandsekunden übrig.
Diese optimistische Rechnung ist kein exakter nativer Kandidaten-Laufzeitbeweis:
Instrumentation und Variation bleiben ausdrücklich unbekannt. Es gibt aber
keinen gemessenen Anhaltspunkt, dass sie den verbleibenden Abstand plus die
noch nicht erledigte Arbeit erklären. Reserveziel ist240CPU und240Wandsekunden.

## Ergänzende neue Paardiagnose

Vor Ausführung: unabhängiges Helperreview, AST-Prüfung, exakter lokaler Hash.
Remote erneuter Stat-/Hashabgleich der sechs Kernmodule: root-eigene Quelle,
keine Symlinks oder nicht-root-eigenen/schreibbaren Einträge im Sourcebaum.
Die Quelle stammt aus dem zuvor vollständig geprüften Gitarchiv72421d3;
dieser Teilabgleich ersetzt nicht dessen ursprüngliche vollständige Versiegelung.

- Quelle: `/var/lib/betboy-capacity-code-5es6n672/source`, Produkt72421d3.
- G1: `/var/lib/betboy-task10-growth-0cguwnz6/generation-1/context.db`.
- G1-SHA256: `04e7db378a84fb90fb115db4aed6508ae295d0b99adb9f5626eba03a1f43b94b`.
- Helper: `.pytest_tmp/measure_stage_a_prefix_cost.py`, SHA256
  `9b0d84cfca526ff2d720d13ed3ed54d9de2422783d12358874c8fe690664ae54`.
- UID997, tatsächliches Appvenv, isoliert/ohne Bytecode, AS2GiB/CPU300,
  interne Diagnosefenster265CPU/285Wandsekunden, außen305Sekunden plus10Kill.
  stdout+stderr auf1MiB begrenzt, kein paralleler schwerer QA-Lauf.
- Exit0;12 von12 Messpaaren vollständig;184,453215CPU-/183,117809Wandsekunden,
  Spitzen-RAM469032KiB. Gesamteingabe danach identisch, keine Begleitdateien.
- Echte physische/Quellenprüfung und alle31 Originale abgeschlossen. Danach
  absichtlicher Diagnoseabbruch, **keine vollständige Snapshot-/D4-Prüfung**.

CPU-Mittelwerte der jeweils drei Paare, Sekunden:

| Zeitraum (UTC) | Historienzeilen | Unveränderter Aufruf | Optimistisch nur frisch dekodiert |
| --- | ---: | ---: | ---: |
| 10.09.10:00:10 |20501|1,619|0,574|
| 11.09.04:37:07 |20501|1,619|0,541|
| 11.09.18:37:34 |42099|3,607|1,319|
| 11.09.19:35:00, exakte größte Basis |42100|1,574|1,405|

Der zweite Aufruf profitiert von warmer Ausführung; er lässt absichtlich
Produktprüfungen weg und liefert niemals Daten an die Modellprüfung zurück.
Mittelwerte dienen nur der Einordnung. Sie dürfen nicht als strikte Untergrenze,
gewichtete Gesamtersparnis oder Abnahme eines neuen Vertrags ausgegeben werden.
Der maximale Zeitraum ist eine Kontrollmessung des bereits exakten Cachepfads,
keine zusätzliche wiederholte frühere Ableitung. Pflichtdekodierung und alle
Feature-/Transportprüfungen bleiben reale Kosten. Die neuen Daten widersprechen
der unabhängigen A1-STOP-Empfehlung nicht. Kein A-Kandidat wurde geschrieben.

Vollständige Metadatenaufnahme `.pytest_tmp/task12-stage-a-pairs-72421d3.jsonl`:
SHA256 `1c578cb7f241d055b930b5df15dc3efc05bf79729a9302de9db97a87a3900f13`.

## Echte Wachstumssichtung, getrennt von G1

Anschließend alleinige, unabhängig geprüfte Aggregatabfrage der Live-Datenbank
`/opt/betboy/app/runtime_state/context_models.db`: mode=ro/query_only,
gehaltene Lesetransaktion, keine DML/DDL/Checkpoint-/Reparaturoperation.
Normale SQLite-WAL-Lesekoordination ist möglich; keine Behauptung unveränderter
Live-Dateien. Produktionsworker liefen unverändert weiter.

- Beobachtungsbeginn:2026-09-11T22:12:37.262269+00:00.
-99776Belege/Contents,33Artefakte,31Originale und31Snapshots,2Manifeste.
-16unterschiedliche Originalzeitpunkte, alle ATP;15Paare und1Einzelzeitpunkt.
-268824576logische Datenbankbytes;106653805Content-Payloadbytes;
  66373102Snapshot-Payloadbytes; zwei Tourzustände mit zusammen2953017Bytes.
-10.September:48556Belege/14Originale/7Zeitpunkte, nur Teil des Tages.
-11.September:51220Belege/17Originale/9Zeitpunkte, noch kein vollständiger Tag.
- Originalzeitraum endet21:07:24UTC; Beobachtungsmetadaten enden19:37:12UTC.
  Unterschiedliche Uhren sind hier aggregiert, nicht semantisch validiert.
- Exit0;1,169431CPU-/2,241291Wandsekunden;28860KiB Spitzen-RAM.

Diese echte31er-Datenbank ist **nicht** die synthetische G1-Datei, auch wenn
Dateigröße und Anzahl der Analysen gleich sind. Keine Übertragung ihrer SHA
oder eines Testergebnisses. Kein frischer D4- oder Backup/Restore-Nachweis.

Metadatenhelper-SHA256:
`383c0eba1f02e6643e9fb86608377353ee5f9a092a2eb7ba49d510904c5bda25`.
`.pytest_tmp/task13-live-growth-20260912.json` SHA256:
`5d4a488155607b773062cbc9807a5330de8424b03bc58d4cf7b45b03827628bf`.
Beide Helper unterliegen `task-12-diagnostic-review.md`; keine Schlüssel,
Kontodaten, Spielernamen oder Quellpayloads wurden ausgegeben.

## Weiterarbeit / keine Freigaben erfinden

StufeB konkretisiert Daten-/Versionsbindung, Abschlussnachweise außerhalb der
Appdatenbank, getrennte begrenzte Vorprüfung und Restoreverhalten. Wachstum
muss zusätzlich gegen1GiB Eingabe und256MiB kanonische Historie geprüft werden.
Zwei angebrochene Tage sind keine belastbare Sieben-Tage-Betriebsstatistik.
Ein vorläufiges Belastungsprofil darf nur als solches bezeichnet werden.

Keine neuen Produkt-/Testbytes, keine Installation/Schlüsselerzeugung, kein
main-Push/Updateraustausch/Deployment. Vollsuite und neue Releaseabnahme
bleiben zurückgestellt, bis überhaupt ein tragfähiger Kandidat vorliegt.
Abgeschlossene Messprozesse sind beendet; kein Hintergrundlauf bleibt offen.
