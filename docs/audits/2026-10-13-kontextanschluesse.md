# Kontextanschlüsse – 13.10.2026

Fortsetzung des freigegebenen September-Plans; kein neuer Modellvertrag.
Ausgang lokal/main/VPS: `6f86b3146b54052b7b30d34f5505533cbc6522c0`.
Codecommit5f175889c4058e65995ca358709b7499d3582fd7 committed,pushed und
13.10.,14:13CEST ohneBackup/API-Zusatzscan per FF auf demVPS veröffentlicht.

## Korrekturen

1. Die bereits vorhandenen gemeinsamen Kaderkoordinaten v2 werden jetzt im
   tatsächlichen Worker und Transport erkannt. v1/v2/v3, Population, Coverage
   und Quellenbindung bleiben getrennt; unklare Mehrfachfits werden abgelehnt.
2. Wirklich empfangene Kontextquellen bekommen eine eigene tatsächliche
   Entscheidung nach der ORIGINAL-Erfassung. Die Veröffentlichung erfolgt erst
   nach allen ORIGINAL-Batches, maximal32/32KiB aus dem vorhandenen Restbudget.
   Gleiche Quellenrevision behält ihre erste Entscheidung. Keine API-Abfrage.
3. Der gemeinsame Resolver verlangt zusätzlich, dass die physische ORIGINAL-
   Veröffentlichung nicht nach der Beweisentscheidung liegt. Das schützt auch
   Wiederverwendung und transaktionales Insert-Readback, nicht nur Training.
4. Readiness zählt physische ORIGINAL-/Quellenbytes pro Digest einmal, einschließlich
   Code, Manifest, Chunks, Entscheidung und Ergebnisrevisionen. Finalfälle werden
   einzeln gebaut und als Referenzen behalten. Train/Tune bleibt beim bisherigen
   Fitter mit separater64MiB-Admission; Evaluation zählt alle eindeutigen
   physischen Inhalte einschließlich verwaister Inhalte bei unveränderten128MiB.

Keine Prognose-, Quoten-, Geld-, Provider-, Aktivierungs- oder Cricket-Änderung.
Enrichment und andere ältere WIP bleiben unveröffentlicht. Keine Sicherung,
Produktionsdatenbankkopie, Zusatzabfrage oder erhöhte Erfassungsgrenze.

## Nachweise und Grenzen

- Native Ausgangstests52 bestanden; neue v2-Tests19 bestanden,164,68s.
  Echte RED-Fehler für fehlende v2-Verbindung und falsche Coverage dokumentiert.
- Zeitfehler:3 erwartete RED-Fehler,6 neue GREEN,48 gemeinsame Nachbarn GREEN.
- D1:8 neue negative/Accounting-Checks GREEN. Read-only, Quellen-/Uhr-/Hash-/
  Expansionsgrenzen, fehlende Inhalte und ehrliche Kohortenverweigerung erhalten.
- Unabhängige v2-, Zeit-, D1- und Paketprüfung PASS. Kein empirisches Gütesiegel.
- Große synthetische Mechanik:203 unterschiedliche Ziele/128 unterschiedliche
  historische Fixtures,2Train/1Tune/200Final in67/67/66 Blöcken. Physische
  Quellen44.576.281B; frühere Mehrfachzählung140.424.440B; expandierte ORIGINALs
  60.936.542B. Teilweise gemeldete Spielerstatistik bleibt teilweise.
- Erst gewähltes Spielermerkmal war wirklich nicht verfügbar: Fit unsupported,
  0/0. Testkonfiguration auf tatsächlich belegte `schedule.gap_hours_home`
  korrigiert; Einzelprobe26h,1 kausaler Fall/2 Zeilen,keine Ausschlüsse. Nur
  die neue Testkonfiguration geändert, nicht Modellwerte/Validatoren/Caps.
- Vollständige203-Fit-/Evaluator-/Verifikationsrunde im korrigierten gefrorenen
  Bestand bestanden:2Train/1Tune/200Final,203gespeicherte Fälle,gleiches Ergebnis
  wie bisheriger Fitter,keine Aktivierung. Testdauer1820,03s;
  vollständige25-Modul-Runde663/663 bestanden,0 Fehler/Skips,3136,79s.
  Der Retained-Cap-Verweigerungstest bestand in118,99s.
  Der erste eingefrorene37-Modul-Lauf wurde wegen dieses bekannten
  Testaufbaus unterbrochen; kein JUnit/PASS. Neue25-Modul-Runde am korrigierten
  Indexstand `af0d4d4b007d2a3a90ea9cfdb66e48a9d09959fb` abgeschlossen.
- Ganze22-Spieler-/128-Fixture-Pools überschreiten weiterhin die unveränderte
  4MiB-Quellengrenze:3225 Receipts/4.486.538B; echte Owner-Ablehnung. Physische
  Deduplizierung umgeht keine Einzel-/Expansionsgrenze und garantiert kein RSS.
- Bekannter Gesamtapp-Konflikt frisch reproduziert: eingefrorener Cricket-
  Vergleich ist numerisch gleich, scheitert danach am vorbestehenden Hockey-
  `_variant`-AST-Freeze.1 Failure/3,97s; kein Vollsuite-PASS, kein Test gelöscht.

Reale Inventur vor diesem Paket:101 ORIGINAL-Bindings,8captured/93partial,
keine Fits/Effekte/Approvals.588 Fußball-SHADOW-Spiele mit Ergebnis enthalten
nicht automatisch die volle alte Torverteilung und komplette vorzeitige
Kontextquellen.200 synthetische Tests ersetzen keine200 echten Testspiele.

Zusätzliche bounded Binding-only-Serverprüfung:8 captured zu8 eindeutigen
nativen Spielen. Alte Labels83Bindings/29.947Refs Budget-Sammelgrund,
9/528Refs fehlende native Referenz,1/777Refs ungültige Provenienz;49partiellen
Bindings fehlt bereits die native Zielidentität. ALLE101 wurden vor der heutigen
Capture-Reparatur veröffentlicht (spätester partiellerBeleg13.10.,01:38:59UTC).
Die83 Sammellabels sind nach bekanntem früheren Zuordnungsfehler KEIN Nachweis
83 echter Budgetausschlüsse. CSV-/nicht-native konsumierte Grundreihen bleiben
eine eigene verifizierte Identitätsverbindung; ihre Anzahl innerhalb93 wurde
nicht über Rohdatendecodierung ermittelt. Budget/Quelle sauber erst im neuen
regulären14.10.,03:35-Lauf unterscheiden, keine alten Bindings umdeuten.

Arbeitsberichte und XML außerhalb Git:
`C:/Projekt/BetBoy/output/context-integration-20261013`.

## Produktion und noch offene Abnahme

Gefrorene Release-QA und Veröffentlichung abgeschlossen. Linux-Offline-Import
ok,App/Caddy aktiv,7Timer enabled,beideHealthchecksok nach normalem Start-Retry.
WettfinderJSON vorher/nachher SHA256
`f20422a802fd61461d8f8ab548f85228a1d083bdba92c51a0615bf9364a81bd4`,
RisikoBet `6f0c5f3158fb2bbe08bc8b7692636a0f16847e90c32742a7f7497346b644e8f1`.
Backupdienst/-timer inactive,21GiBfrei. Keine alten Prognosen/Geldbuchungen verändert.

Echte RO-Readiness nachDeploy:8captured native ORIGINAL-Spiele explizit geprüft,
aber7davon `joint_source_byte_bound_exceeded`. Nur1Quellenpool/Ergebnis auflösbar;
die drei ausdrücklich geprüften Spalten (v2gemeldeterRosterverlust,
v3gemeldete7dMinuten,Temperatur)jeweils0vollständig.0Fits/Effekte/Approvals,
keine Aktivierung. Das ist KEIN umfassender Test allerdenkbaren Kontextspalten.
NeuePriorität: tatsächliche4MiB-Poolursache aufteilen und ohneBudgetanhebung,
willkürlicheQuellenkürzung oder historischeUmdeutung lösen. Mehr Rohspiele allein
beseitigen dieseSoftware-/Admissiongrenze nicht.

Die anschließende ausschließlichHeader-basierte Produktionsdiagnose ergab,
Reihenfolge `created_at,digest`,jeweils eindeutigem nativenSpiel:

| Fall | Native IDs | Receipts = verschiedene Inhalte | Physische Bytes |
| --- | ---: | ---: | ---: |
| 1 |420|36111|97110896|
| 2 |420|36105|97105011|
| 3 |420|36105|97105044|
| 4 |423|36182|97260618|
| 5 |480|3046|4533002|
| 6 |130|130|197155|
| 7 |425|37037|99521485|
| 8 |429|37092|99654909|

Raw-ID-Pool = Goal-/Prior-/Binding-Closure,unverbrauchteIDs0;wiederholte
Content-Digests0. Sechs großeFälle zusätzlichüber4096Receipts. AlleinBaseline
34,39–35,34MB plusAppearances62,07–63,64MB. UnterschiedlicheHashwerte beweisen
keine unterschiedlichen sportlichenWerte;Body/Rollen/Revisions-Semantik wurde
hierNICHTdekodiert. DedupoderEntfernenunverbrauchterRaw-IDs ist kein bewiesener
Fix. Vollständige branch-/rollenbezogene Quellenauflösung mit Streaming/
Projektion muss vor Implementierung ihre kausalen/hash-/Revisionsinvarianten
belegen;keine willkürlichelatest-only-Auswahl oderBudgeterhöhung.

Nächster regulärer
Lauf muss die neuen tatsächlichen Entscheidungsbelege zeigen. Numerische
Kontextqualifizierung bleibt ein eigenständiger Nachweis, kein Software-PASS.
