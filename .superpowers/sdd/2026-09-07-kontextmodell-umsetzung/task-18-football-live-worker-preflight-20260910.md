# P5b: tatsächlicher Fußball-Anschluss – lesender Preflight

10. September 2026. Ziel: Root-Worktree `kontextmodell-20260907`, zunächst
`98dc5cbd9b17b2e4e0259039065d11fac0f404d9`. Während des Reviews integrierte der
Controller separat P6a/Dokumentation; letzter kontrollierter HEAD ist
`898652bbd2343cef6d67e8573f32c14b891f1057`. Der explizite Git-Diff für sämtliche
nachstehend geprüften Fußball-/B3-/D4-/Consumer-Quellen gegen 98dc5cb ist leer.
Unabhängige Source-Hashes stehen unten. Die fremde Änderung in
`scripts/stage_runtime_databases.py` und vorhandene ungetrackte Outputdateien
wurden nicht geändert oder als Bestandteil dieser Prüfung behandelt.

## Ergebnis

**Der heutige finale Fußballscanner hat noch keinen P5b-Anschluss.** Die
Funktionsprobe führt eine wirkliche finale Modellrechnung mit 90 Marktdefinitionen
aus und speichert native XI-/Bench- und Ausfallbeobachtungen in einer echten
temporären B1-Datenbank. Trotzdem wird die vorhandene P5a-Aufnahmefunktion nie
aufgerufen und kein gemeinsamer B3-Rechenstand veröffentlicht.

Das ist ein reproduzierbarer fehlender Anschluss, keine Erklärung über fehlende
Quoten und kein Nachweis, dass die vorhandene Basisauswahl abgeschaltet werden
müsste. Die Module für native Beobachtungen, Originalaufnahme, B5-Mechanik und
B3 existieren; die tatsächliche Worker-Verbindung ist offen.

Ein bloßes Durchreichen der P5a-Marginalen an den bisherigen B5-Raw-Vergleich
wäre fachlich falsch: Schon mit exakt null Ratenänderung würde eine alte
Marktkalibrierung verschwinden. Der neue Live-Original-Vertrag und der geprüfte
Vergleich müssen deshalb explizit getrennt bleiben. Eine Raw-D1-Freigabe darf
nicht auf das kalibrierte Legacy-Original übertragen werden.

Keine Produktivdatei, Modellregel, Quote, 15K-Regel, Datenquelle oder bestehende
historische Zeile wurde geändert. Keine neue Anfrage, kein SSH/VPS, Commit,
Push, Paketinstallation oder vollständiger Repositorytest. Eigene Dateien
liegen ausschließlich unter `.pytest_tmp`.

## Gelesene maßgebliche Unterlagen und Quellen

Die vollständige freigegebene Spezifikation
`docs/superpowers/specs/2026-09-07-kontextmodell-design.md`, der D1–D5-Plan,
Task8/Task9, `context-contract-decisions.md`,
`validation-contract-decisions.md` und der vollständige Task18-Controllervertrag
wurden gelesen. Trunkierte Ausgaben wurden an ihren fehlenden Abschnitten
nachgelesen; die veralteten kurzen Trainingssignaturen werden nicht als zweite
schwächere Assembly-Schnittstelle wieder eingeführt.

Vollständig gelesene aktuelle Audits:

- `2026-09-09-b4-quellen-kader.md`
- `2026-09-09-b5-torraten-mechanik.md`
- `2026-09-09-d3-football-existing-receipts.md`
- `2026-09-09-d3-football-capture-ns-korrektur.md`
- `2026-09-09-football-ergebnis-capture.md`, einschließlich Watch-/Indexkorrektur
- `2026-09-09-p5a-football-original-capture.md`
- `2026-09-10-p5a-sample-metadata-correction.md`
- `2026-09-09-c1-wetter-belastung-mechanik.md` und `2026-09-09-c1-recovery-cutoff.md`

Die tatsächliche final-Scan-, Quellen-, B4/B5-, Replay-, B3- und D4-Quellkette
wurde selbst untersucht. Der normale Fußball-ModelSignalpfad verwendet heute
die aus Kandidaten serialisierten Werte; `football_signals()` ist zusätzlich
ein anderer älterer Scannerpfad und darf nicht mit dem hier zuständigen
Wettfinder-Kandidatenpfad verwechselt werden.

## Tatsächliche Aufruf- und Zeitgrenzen

| Stelle | Tatsächliche Aufgabe / P5b-Grenze |
| --- | --- |
| `wettfinder_automation._default_football_scan`, 2105 | Eigentlicher automatischer Finder, optiert bereits in `capture_football_worker` ein. |
| `alternative_markets_tab_extended._run_market_scan_worker`, 443 | Manueller Finder; derselbe Scan und Capture-Scope; Preise kommen erst nach Scopeabschluss. |
| `scan_daily_challenge`, 2187 | Bestehende Daten-/Budget-/Rankingreihenfolge. Profile `challenge` und `wettfinder` bleiben verschieden. |
| `fixture_market_probabilities` an 2377/2421 und `build_fixture_candidates` an 2442 | UEFA-Berechenbarkeits- und Transferproben, keine finale Auswahl. Hier keinen neuen Shared-Original-Callback anbringen. |
| `build_fixture_candidates` an **2551** | Finale Liga-/UEFA-Rechnung nach echten Validierungs-/Kalibrierungsauflösungen. **Hier fehlt `original_capture`.** |
| `fixture_market_probabilities`, Engine1642 | Eine bestehende Raten-/Zählrechnung mit finalen Markt-Kalibrierungen. P5a erhält vor Kandidatenrundung ungerundete aktive/Saison-/Formtripel. |
| `scan_daily_challenge` nach finalem Pool, ca.2656 | Bereits begrenzte `injuries_by_fixture`, `details_by_fixture`, H2H/Wetter. Fakten kommen **nach** der Originalrechnung. Keine zusätzliche Abfrage für P5b notwendig oder hier autorisiert. |
| `_reconcile_candidate_fixture`, 292 | Bindet tatsächliche Detailantwort an Teilnehmer/Termin/Status; verwirft gestartete/abgesagte oder fremde Kandidaten. Diesen Legacy-Schutz behalten. |
| `capture_football_worker`, `finally` | Erst hier werden bereits empfangene gültige Receipts in B1 publiziert. Die später erzeugte Reportzeit darf die einzelnen Receiptzeiten nicht ersetzen. |
| `_default_football_context_refresh` / `refresh_discovered_candidates`, 2130/2888 | Aktualisiert gespeicherte, bereits gerundete Kandidaten; hat die ursprünglichen ungerundeten Raten, Kalibratorrezepte und Historien nicht. Daraus kein neues Original rekonstruieren. |
| `_football_candidate_record`, 331; `football_risk_bundle`, 773 | Normale Finder- bzw. RisikoBet-Projektion; beide besitzen noch keinen zu dieser Fußballrechnung aufgelösten gemeinsamen Kontextref. |

Die finale Auswahl wird heute vor den neu geladenen Ausfall-/XI-Fakten berechnet.
Ein späterer P5b-Worker muss deshalb mindestens drei Uhren getrennt erhalten:

1. `FootballOriginal.captured_at`: tatsächliche einmalige Originalrechnung;
2. tatsächliches `observed_at` jeder vor und nach dieser Rechnung empfangenen Quelle;
3. tatsächlicher neuer Kontextentscheid nach erfolgreichem Capture-Abschluss,
   weiterhin strikt vor dem aktuellen Anpfiff.

Vorschlag zur Controllerentscheidung: Die neue Live-Base bekommt den tatsächlichen
Kontextentscheid als `cutoff`, während ihre Referenz separat das unveränderte
Original samt ursprünglichem `captured_at` und logischem Kickoff-Historienstichtag
bindet. Alle Basisinputs müssen tatsächlich spätestens zur Originalrechnung
verfügbar gewesen sein; alle verwendeten Kontextquellen spätestens zum neuen
Entscheid. Nicht den Kickoff als Receiptzeit nehmen, keinen frühen
Original-Cutoff um spätere Fakten ergänzen, keinen zweiten Modelllauf ausführen.
Ein veränderter Event darf nicht nur mit neuem Hash auf alte Eingaben passen.

Das entspricht dem sachlichen Unterschied zwischen eingefrorener Basis und
neuer Kontextrevision, benötigt aber den ausdrücklich versionierten owning
Live-Origin-Vertrag; es ist hier **noch nicht implementiert**.

## Funktionale REDs und Kontrollen

Alle Fälle laufen mit dem echten finalen `scan_daily_challenge`, echten
`build_fixture_candidates`/`_fixture_model`, echter P5a-Mathematik und echten
temporären SQLite-B1-Tabellen. Nur Netzwerkantworten, vorhandene Cache-/Historien-
Eingaben und Uhr sind synthetisch; die Canned-HTTP-Antworten werden über den
tatsächlichen `ChallengeDataProvider._football_get` und Capture-Observer geführt.
Kein Netzwerkpfad wird erreicht. `_fixture_model` und Capture werden über ihre
tatsächlichen Python-Codeobjekte mit `sys.setprofile` gezählt, nicht nur über
einen möglicherweise umgangenen Importalias.

Vor jeder erwarteten Anschluss-Assertion sind erfolgreich nachgewiesen:

- ein gefundenes und modelliertes Spiel, **90** Marktberechnungen;
- genau **ein** tatsächlicher `_fixture_model`-Aufruf (Liga ohne UEFA-Probe);
- genau **fünf** vorhandene Requests: Discovery, Coverage, Ausfälle, Details, H2H;
- 24 XI-/Bench-Records und der konkret gemeldete fehlende Spieler112 in B1;
- getrennte originale Receiptzeiten, keine Veröffentlichung/Archivbehauptung;
- Capture-Status `captured` und keine Source-/Speicherfehler.

Danach scheitern genau die beabsichtigten zwei Assertions:

1. Capture-Codecallzahl ist **0 statt1**.
2. `context_snapshots` fehlt vollständig; die tatsächlich vorhandenen Tabellen
   sind A1/B1, nicht eine B3-Publikation.

Die erste eigene Harnessfassung lieferte zusätzlich lokale `challenge_stats`
im angeblich nativen HTTP-Detail. Der geschlossene native Parser lehnte das
korrekt ab. Dieser erste Lauf ist deshalb **kein qualifizierter P5b-RED**.
Originaldatei und XML bleiben unverändert. Die separate qualifizierte Datei
entfernt ausschließlich diese falschen lokalen Top-Level-Felder aus der
synthetischen HTTP-Antwort und ruft sämtliche ursprünglichen Assertions
unverändert auf. Keine Quelländerung oder umgedeutete Erwartung.

### Kalibrierungs-Gegenprobe

Bewusst unsichere, ausdrücklich synthetische Substitution einer kalibrierten
P5a-Basis in B5, mit Nullkoeffizienten und genau unveränderten Raten:

```text
Original Heimsieg      0.3694976939366661
B5-Raw-Vergleich       0.39683557226159566
Differenz             +2.7337878324929568 Prozentpunkte
Raten verändert       nein
```

Die Differenz stammt allein vom Weglassen der alten Kurve, nicht von einem
Spielerausfall. Die 50 Nichttor-Märkte bleiben unverändert. Das ist kein
beobachteter Produktionsfehler: Der unsichere Anschluss existiert noch nicht;
die Probe belegt, warum er nicht auf diese Weise gebaut werden darf.

Im selben synthetischen Fall erhält `calculate_context_payload` **ohne Effekt**
alle90 finalen Marginalen und Originalparameter exakt, mit `not_applied` und
keiner neuen Marktfreigabe. Diese CPU-Kontrolle ist ausdrücklich keine
Quellen-/D2-/Live-Autorisierung der handgebauten Probe.

## Reale verbleibende Quellengrenzen

### Native Basis und vollständige Historie

P5a erfasst die tatsächlich konsumierten Eingaben, aber noch keinen nativen
Receiptbeweis: `source_evidence=unresolved-receipts-not-in-this-capture`.
Die echte `include_provenance`-Aufnahme übergibt noch kein `native_provenance`;
`history_refs` und Spieler-/Teamjoins bleiben im Kontrollfall korrekt unresolved.
Ein positiver Test auf `football_features` bestätigt ausschließlich fehlende
Referenzmerkmale, keine erfundenen Nullen.

`football_native_provenance` kann exakte lokale Basiseingaben mit tatsächlich
gesicherten Detailreceipts binden. Sie wählt aktuelle native Revisionen vor dem
Matching; CSV-PseudoIDs/Namen sind kein Ersatz. Ihre Ausgabe muss vom Worker aus
wirklich aufgelösten B1-Bytes kommen, nicht aus frei übergebenen verified-Flags.
Die vorhandene mathematische Auswahlprovenienz darf separat um nachgewiesene
Identitätsbelege ergänzt werden; keine zweite `_fixture_model`-Rechnung, keine
nachträgliche Veränderung der bereits gespeicherten P5a-Originalbytes.

Heute begrenzt der Capture die gespeicherten Detail-/DiscoveryIDs auf bereits
explizit angefragte Kontextfixtures. FT-Leagueantworten werden nur für vorher
wirklich vor Anpfiff gespeicherte Watches übernommen. Der erste Lauf erzeugt
damit keine vollständige historische Modellbasis. Der vorhandene UEFA-Request
`fixtures?team=...&last=...&status=FT` ist auch kein in diesem Capture freigegebener
Requestscope. `football_context_batch` ist nur eine optionale, separat begrenzte
Quellenseam und wird im heutigen Scanner nicht aufgerufen; sie jetzt zusätzlich
aufzurufen würde gerade **neue Requests** verursachen und ist kein P5b-Shortcut.

Viele tatsächliche Basiseingaben kommen aus `football_data_history`-CSV und
`xg_backfill`-Cache. `fetch_history` gibt geparste Rows ohne dauerhaft gebundenen
Empfang/Rawinputref zurück; die XG-Cachetabellen besitzen zwar `fetched_at`, die
Annotation transportiert diese Receipt-/Joinbelege aber nicht mit den konsumierten
Rows. Namen/Datum-Matches in der Legacyannotation dürfen nicht als Native-Alias-
Beweis für Spielerwirkung ausgegeben werden. P5a kann deren unveränderte
Originalwerte bewahren, nicht dadurch rückwirkend B4-/D1-Quellenhistorie erzeugen.
Der bestehende Kalibrierungs-Cache gibt Kurven und Samples zurück, keinen A1-
Trainings-/Zeitbeweis. Auch dies ist kein Grund, eine berechenbare Legacybasis
auszublenden, sondern eine getrennte Grenze für neue empirische Freigaben.

### Statuskorrekturen

Die zusätzliche echte Temp-DB-Kontrolle empfängt erst NS, danach bei derselben
nativen Fixture CANC bzw.1H. Der Provider liefert den aktuellen Status korrekt;
der heutige Capture speichert aber **keinen** neuen Status-/Rücknahmerecord und
meldet `no_receipts`. Ein neuer NS-Termin dagegen wird als neue B1-Basisrevision
gespeichert. Grund: `normalize_football_base_input` unterstützt nur FT/NS/TBD/PST;
der Capture ruft bei anderen Status keine eigenständige native Statusprojektion auf.

Das ist eine **P5b-Quellenfähigkeitsgrenze**, keine Behauptung eines heutigen
falschen Settlements oder unverändert sichtbarer abgesagter Karte. Die heutige
`_reconcile_candidate_fixture` arbeitet separat mit dem tatsächlichen Detail.
Vor einem vollständigen B1-only-Worker-/D4-Replay benötigt P5b eine eng besessene
native Eventstatus-/Schedule-/Teilnehmerlinie aus genau den vorhandenen Antworten.
Fehlende/partielle neue Identität darf alte Belege nicht still wiederbeleben.
Keine generische B1-Selectoränderung und keine alte Datenmigration vorschlagen.

### Ausfälle, Spieler-Minuten und Müdigkeit

Die vorhandene **reale** sanitierte Antwort vom 09.09.2026 enthält für das
FT-Spiel1570343 genau46 Spielerzeilen: **32 bekannte und14 unbekannte Minuten**.
Alle tatsächlichen Beginn-/Endzeiten sind unbekannt. Die neue Kontrolle lädt die
existierende Fixture unverändert, nicht eine nacherfundene Quote oder Statistik.
Die Septemberantwort ist kein August-Prematchbeweis.

B4 benötigt für jede tatsächlich konsumierte Spieler-/Komponentenreihe die
belegte Regulationsexposition aller relevanten Basissamples sowie eine
belegte erwartete Besetzung. Eine fehlende Spielerzeile ist nicht0; ein
bestätigter Starter nicht automatisch90Minuten; ein dauerhaft fehlender Spieler
nicht nochmals ein voller Abschlag. Fraglich ohne kausales Teilnahmemodell bleibt
Szenario/unknown, kein50/50. Vorhandene gemeldete Ausfälle beweisen noch keine
vollständige gesunde Restmannschaft.

C1 besitzt eine **separate** native Schedule-/Belastungsmechanik. Die reale
API-Projektion liefert keine genaue Dauer/Endzeit; auch `elapsed=90` oder
`periods.second` ergeben keine tatsächliche Enduhr. Receipt erlaubt höchstens
die deklarierte beobachtete Erholungsuntergrenze, keine exakte individuelle
Müdigkeit. Aktuell gibt es außerhalb von Tests keinen Workeraufruf von
`normalize_football_schedule`/`football_schedule_features`. B5-roster-v2
akzeptiert bewusst weder `football-observed-load-v1` noch Wetter-v1. Eine spätere
gemeinsame Verletzungs-/Belastungsfamilie benötigt einen eigenen geschlossenen
Feature-/Fit-/D1-/D2-Vertrag; nicht per substring oder bestehendem Koeffizienten
umdeuten. Wetter hat zusätzlich die im C1-Audit belegten Orts-/Ausgabe-/Budgetlücken.

## Kleinste sichere Implementierungsgrenze – konkreter Vorschlag

Diese Abschnitte sind **Vorschläge für Controller-Rulings**, keine schon
genehmigten öffentlichen Schemas oder neuen Source-/Wirkungsfähigkeiten.

### P5b-A: Finale Originalaufnahme plus owning Live-Original

1. Ein optionaler keyword-only Original-Sink an `scan_daily_challenge`, ausschließlich
   an der letzten finalen `build_fixture_candidates`-Stelle. Default bleibt aus;
   UEFA-Proben, 15K-Scanner und alte IDs/Mathematik bleiben unverändert. Finder-
   Worker sammeln die echten `FootballOriginal`-Objekte je nativer Fixture einmal.
2. Nach bestehendem Capture-Finally: reine owning Vorbereitung aus genau diesem
   Original und aufgelösten B1-Receipts. Kein zweiter Fit/Predict, kein neuer GET.
3. Neuer expliziter Live-Original-Vertrag, z.B. `football-live-calibrated-original-v1`
   als A1-Art, eigene Baseversion und klarer Reference-Tag. Er bindet den gesamten
   P5a-Payload, aktuelle volle Eventidentität, echten Kontextentscheid, getrennte
   Originalzeit, genaue Eingabereihenfolge, Kalibrierrezepte und ausgeführte
   Codebytes. Base behält exakt die vorhandenen aktiven finalen Marginalen;
   Saison-/Formwerte und Countfamilien bleiben im Original erhalten. Keine
   Behauptung einer kohärenten gemeinsamen Verteilung aus den alten Marginalen.
4. Kein neues Pflichtfeld in alte `ChallengeCandidate`-Tickets einschleusen.
   Neue Kontextrefs als optionaler getrennter Finder-/Risk-Domänentransport;
   genuin fehlende Legacyrefs bleiben absent. Unbekannte native/Recipebindung
   lässt den bestehenden Kandidaten bestehen und publiziert keine Scheinevidenz.

Owning Dateien: enger Scanner-Sink in `challenge_15k.py`, neues
`context_models/football_live.py`, separates `football_context_worker.py`,
neue fokussierte Tests. Allgemeines B1-Schema nicht aufbrechen; falls ein neuer
getaggter Referenztyp nötig ist, nur seine owning Validatordispatch-Erweiterung
plus B4-Referenzprojektion nach explizitem Controllerentscheid.

### P5b-B: Tatsächlicher Quellresolver und einmaliger B3-Stand

1. Ein read-only Resolver unter `context_sources` lädt vollständige causal
   Receiptpools mit tatsächlichem SQLite-/Content-/Indexcheck, vor Status-/ID-
   Filterung. Er löst neueste native Korrekturen vor Basishistorienmatching auf.
   Der notwendige Status-Capture oben ist Teil dieser Quellenfähigkeit; kein
   Auftrag zur unbeschränkten historischen Erfassung.
2. B4-Referenzbindung basiert auf den wirklich konsumierten P5a-Historyrecords
   und Gewichten. Keine Rundungsinversion, keine Namensaliaserfindung. Fehlende
   native Basissamples bleiben missing/unsupported; gesunde Basis bleibt.
3. B4 `football_features` einmal aus dem ganzen gültigen Pool; notwendige
   A1-Teilnahme-/Effektmodelle außerhalb des B3-CPUcallbacks auflösen. Echte D2-
   Prüfung an exakte Baseversion/Featurecoverage/Population/Clock binden und
   innerhalb des Workerbatches wiederverwenden, nicht als dauerndes passed-Flag.
4. Die kalibrierte Live-Base bleibt ohne qualifizierte Effektpipeline exakt.
   B5-Raw-Vergleich darf allenfalls als getrennt versionierter interner Versuch
   erscheinen; Kalibrierungswechsel ist kein Spielerbeitrag. Eine Raw-D2-
   Freigabe reicht ausdrücklich nicht. Vor einer applied-Variante ist der
   unveränderte Live-Basevergleich samt definierter Distributionsbewertung und
   marktspezifischer Kalibrierung tatsächlich zu evaluieren. Hier nichts
   pauschal freischalten oder still alte Kalibratoren auf neue Märkte anwenden.
5. `context_snapshots.compute_once` publiziert einen genau gebundenen B3-Stand;
   beide Verbraucher erhalten denselben immutable Ref. Inputaufbereitung und
   B3-CPUcount getrennt messen. Der volle Quelle→Original→FV→A1→B3→zweiReader-
   Test ist erforderlich, nicht nur zwei gleich gerundete Kartenwerte.

### P5b-C: D4 und Verbraucher vor einer Fertigmeldung

Heute prüft D4 für generischen Football-B3 echte physische Referenzen plus
mathematischen Transport und meldet anschließend ausdrücklich
`d3-owning-source-feature-replay-unavailable`. Nur Tennis hat bereits einen
separaten owning Live-Replayzweig. P5b benötigt den entsprechenden **wirklichen**
Original-/Status-/Feature-Replay aus A1/B1, nicht das Entfernen dieser Limitation.
Eine normale Karte liest dagegen nur den bereits veröffentlichten Rechenstand;
kein Refit/Provider/D4-Vollreplay beim Rendern.

`_football_candidate_record`, persistierte normale ModelSignals und
`football_risk_bundle` müssen den gemeinsamen Ref einschließlich konkreter
Marktorientierung prüfen. Aktualisierte Prognosen erben keine alten
15K-/RELEASED-/Validierungsfelder. Ein Kontextrefresh aus alter gerundeter
Karte darf nur die Legacyfakten aktualisieren; erst ein gespeichertes echtes
Original ermöglicht später eine neue Kontextrevision ohne neue Basisrechnung.
Bei verändertem Anpfiff/Teilnehmer-/Modellinput bleibt das alte Original
Historie, nicht Grundlage einer rückdatierten neuen Freigabe.

## Tatsächlich noch nötige Controllerentscheidungen

- Name/geschlossene Felder des kalibrierten Live-Original-A1-/Base-Referenztyps;
  getrennte Original-/Kontextentscheidung gemäß der oben realen Reihenfolge.
- Exakte neue Live-Familien-/Versionsgrenze und Distributionsbewertung gegen
  kalibrierte Legacy-Marginalen. Bisheriger Raw-D1/B5-Vertrag alleine reicht nicht.
- Enge native Status-/Participant-Correction-Aufnahme aus bestehenden GETs;
  welche vorhandenen History-/XG-/Kalibratorquellen tatsächlich kausal gebunden
  werden können, welche ausdrücklich unresolved bleiben. Keine Quelle erfinden.
- Roster-only zuerst; separate C1-Load-/Weather-Anbindung und spätere kombinierte
  Feature-/Fitfamilie sind nicht implizit Teil eines B5-v2-Effekts.

Dies sind fachliche Schnittstellenentscheidungen innerhalb des genehmigten
Auftrags, keine neue Rückfrage nach der bereits erteilten Nutzerspezifikation.
Die real fehlende native Kader-/Zeit-/Fit-/200Event-Evidenz kann durch Software
nicht erzeugt werden; unabhängige Implementierung kann trotzdem fortgesetzt
werden. Ein erneutes `not_applied`-Gerüst ist nicht als fertige numerische
Verletzungs-/Müdigkeitsintegration auszugeben.

## Eigene Tests und unveränderte Originalbelege

```text
p5b-preflight-red-01: 3 failed / 2 passed, 3.22s
  Nicht qualifizierter erster HTTP-Harness: lokales challenge_stats im Nativeblob.
p5b-preflight-red-02: 2 failed / 3 passed, 3.60s
  Qualifizierte endgültige Capture-/Shared-Snapshot-Lücken, unveränderte Assertions.
p5b-preflight-focus-03: 298 passed / 0 skipped, 56.66s
  7 zusätzliche Source-/Legacykontrollen plus bestehende P5a, Capture/FTwatch,
  Nativeprovenienz, B4-Features, B5-Mathematik und D1-Replay. Keine volle Suite.
```

Gemeinsamer Befehl: vorhandene Quality-Pythonumgebung, `-B -m pytest -q`
`-p no:cacheprovider -o 'pythonpath=. tests'`, jeweils neue `.pytest_tmp`
Basistemps und JUnit-Dateien. Eine kurze ergänzende reine CPU-Ausgabe oben
protokolliert die exakten Kalibrierungszahlen. Ein read-only Diagnoselauf
prüfte den ersten falschen Nativeblob mit owning Normalisierern in einer neuen
temporären DB; er bestätigte den Harnessfehler, nicht einen Produktfehler.
Einige vorgelagerte `rg`-Befehle trafen vermutete nicht existierende Dateinamen
oder Windows-Globs; nach `rg --files` wurde gezielt gelesen. Diese Fehler
änderten keine Dateien und zählen nicht als Befunde oder Testnachweise.

```text
10b6b99278bac5cf00d72fcce6463896253f626d939a926304f42e1c3cdb0c58 test_p5b_missing_connection.py
8632728a677ca13a85c109b33b0eb3a3ea81bfd4df304892286fdfd4b1fec737 test_p5b_qualified_connection.py
72f8eef13df36f552111a5a7cae0d84da1129070f258b3eb9bef530576b1b97b test_p5b_source_boundaries.py
b99b6c5f6e460964612f51e0aa5323b989d7e25c8e16b6352e4a11aeca9bc84c ../p5b-preflight-red-01.xml
cd5ea3216b5f991e3dbb700104b5d56322920a8acbc4bab56ebde2844f0ff519 ../p5b-preflight-red-02.xml
22d58b5714cec38407c7b48d35a287dc9357ba76681e1738c7ebc16dba1e5b0f ../p5b-preflight-focus-03.xml
```

## Eingefrorene relevante Raw-SHA256

```text
289b3a2a2b4676666cf7c87f95af8c77260d0d4e812735f46854d6b2e5ec3c73 challenge_15k.py
9e3b35cc9c0aba5f611d334336beaccfd4e885b280d9173dd98dcd7c6740922e challenge_engine.py
138fbe5a6570995e7274741dde84e2d4ea1a9cedb7efbaecb2856d91be88af1d football_original.py
ef8af37ab0b2959cdb28c3e74f13f0783d6d39a60e969b4914913bf9155a06b7 context_sources/football.py
fa4adf76c31fb1fa84f2296f8ba735ca0877fc3d181ff7c62ce53e51a3faccec context_sources/football_capture.py
880817e335480a463b912931065714ef8244764855ec4e4c497b65950883f127 context_sources/football_native.py
6b2da088c60f08359b0e20150e660ecebcb4fb98c47561721c7bdf628f748b83 context_sources/football_provider.py
e61943527fd764d1017f3c78ae09cd5d1d8bc67db44e19961517bc4b329e6786 context_sources/outcomes.py
0f38c93c3a4c38c21112aa22d7b04f7f61f1369dbdba71f319df81c191fbe1dc context_models/football.py
76f6db32ccbde0d582bb988a431e384cb1f71eb814c255e3ef311e33047e7789 context_models/football_effect.py
761b000057c41f2cb692304b7dfa839fcf067126e22a94d687c037027bbe4f1b context_models/football_load.py
fb7e0d581f45144c1f1b0456f828e58a7cb16ac124c1ec9683dc4f2b43fae32d context_models/replay.py
a47d980a4e528ef12917db39e47d025c4670070737901f6e8c9688dfe84a1a9e context_transport.py
974917709b8e292b9621c6bef17112794a0724c4885f04f97052bde3799eab3e context_runtime.py
360e4515f6b3a14e3ee523e3b6ac4988a8bd8ba12009dc291af1ce9670fc6367 wettfinder_automation.py
a28bbd628d6f410259b293f6675c87db698305c3a6dc09f0a9c80efca82ebb2c riskobet_candidates.py
```

Die Rawbytes sind keine plattformübergreifende Gittext-Paritätsbehauptung.
Originalreports/Assertions/XML werden für die anschließende Implementation
und unabhängige Wiederprüfung unverändert eingefroren. Keine Live-/D2-/UI-/
Deploymentfreigabe wird aus diesem Preflight abgeleitet.

## Abschlussverifikation nach Accountfortsetzung

Der unveränderte qualifizierte Anschluss-Test und alle sieben Sourcekontrollen
wurden unter `p5b-preflight-final-04` erneut vollständig ausgeführt:
**2 qualifizierte Anschlussfehler / 10 bestandene Kontrollen, 4,63s, Exit1**.
Es fehlen weiterhin genau Original-Capture und gemeinsamer B3-Snapshot;
die NS-/CANC-/1H-Kontrollen und die übrigen belegten Grenzen bleiben bestätigt.
Das ist die erwartete Diagnose des noch nicht implementierten P5b, kein grüner
Umsetzungsabschluss. Kein ursprünglicher Test und kein früheres XML wurden geändert.

JUnit-SHA256:
`e05b31c276b3c6ec9e6b1146179723e4aa9c52b2a7c75c682cc8a5e0042f452a`
für `../p5b-preflight-final-04.xml`.

Alle16 oben aufgeführten Raw-Quellhashes wurden erneut direkt vom Dateisystem
verglichen: **16 identisch / 0 Abweichungen**. Der gezielte Git-Diff gegen
98dc5cb bleibt leer; HEAD ist weiterhin898652bbd2343cef6d67e8573f32c14b891f1057.
Der bereits vorhandene fremde Working-Tree-Status ist unverändert. Ausschließlich
dieser neue Abschlussabschnitt und das neue Testergebnis ergänzen die eigene
ignorierte Belegsammlung. Bericht und Proben sind damit für den Controller
eingefroren; weitere Änderungen erfordern einen getrennten Auftrag.
