# D1: geschlossene Trainingsmechanik — 9. September 2026

## Umfang und Ergebnisgrenze

Isoliertes Paket auf `codex/kontext-d1-training-20260909`, Basis
`a97d0cf9521945b169e069ed8e2daea9d93db314`. Die vorab gelesenen D1/B5/B7- und
B1/A1-Verträge sowie die Controllerentscheidungen in
`validation-contract-decisions.md` bleiben maßgeblich. Dieser Bericht belegt
Implementierung und synthetische Regressionsmechanik, **keinen echten kausalen
Trainingslauf, keine empirische Freigabe und keine Produktionsaktivierung**.

Keine Providerabfrage, kein VPS-Zugriff, kein produktiver Datenbankzugriff,
kein Push/Deployment; Cricket, Geld-/Ticket-/Abrechnungsregeln, bestehende
Sportmodelle und B1/A1-Schemas unverändert. Datenbanktests verwenden neue lokale
TEMP-Dateien. Die Quellen-/Modellmathematik bleibt preisfrei.

## Geschlossene Eingaben und gemeinsame D2-Schnittstellen

- `validate_family_config` in `context_models.training_contracts` validiert
  Sport/Familie, Population, Coverage, tatsächliche Featureversion/-reihenfolge,
  ursprüngliche Basisversion, Referenzversion, Head-Gesetz, explizite Gruppen,
  Vorverarbeitungsreferenzen, Zielmärkte/Outcomevertrag, UTC-Schnitte und die
  unveränderten fünf Alphas. Der Config-Hash ist `digest(canonical_config)`,
  nicht ein A1-Kind-Hash. Fehlertypen bleiben auch bei malformed JSON geschlossen.
- A1 `context-native-identity-map-v1` bindet **die ganze native Dataset-Map**.
  `validate_identity_map` prüft die Form; `resolve_identity_map` löst echte
  B1-Receipts auf. Ein ausdrücklich angeforderter Teil behält den globalen Hash,
  ohne andere/finale Eventreceipts zu öffnen oder ihre Auflösung zu behaupten.
- `context_sources.outcomes` liefert separate native Resultate: Football nur
  tatsächliches FT-Regulationsergebnis; Tennis nur native abgeschlossene
  Gewinneridentität. AET/PEN, Aufgabe/Walkover und unklare Gewinnerdaten werden
  nicht umgedeutet. Der separate Servevertrag verlangt gemessene Holds/Trials
  plus vollständigen Satzverlauf; derzeit gibt es dafür keinen echten Adapter.
- Die Replay-Recipe `context-base-replay-recipe-v1` bindet aktuelle Codebytes,
  native Inputreceipts, genaue Basisversion/Zielmärkte und explizite fehlende
  State-/Calibratorreferenzen. `context-base-replay-v1` enthält die unveränderte
  B1-Basis, gesamten Event-/Identitätsbezug, logischen Cutoff und tatsächliche
  Rekonstruktionszeit. Eine Rekonstruktion ist kein damaliger Liveforecast.
- A1 `context-training-case-v1` bindet vollständigen Event, ursprüngliche
  Basis/Features, Replay-, Outcome-, globale Identitäts-, Config- und
  Preprocessingreferenzen. `validate_resolved_case` ist der gemeinsame D1/D2-
  Belegresolver, kein freier `row.x`- oder Hash-Passthrough.
- `fit_family(rows, config, *, cases)` liefert einen separaten geschlossenen
  FitResult. `train_family(..., *, cases)` projiziert ausschließlich bei Erfolg
  auf den unveränderten B1 EffectArtifact; sonst folgt `TrainingUnavailable` mit
  dem vollständigen Report. Ein FitResult ist keine Approval.

## Ersetzter Assemblyvertrag und tatsächliche Aufruferprüfung

Der Controller hat ausdrücklich bestätigt: **einziger belegauflösender
Assemblypfad ist `assemble_training_cases(cases, config)`**. Die früheren
Planentwürfe `build_football_training_rows(observations, baselines, *,
training_cutoff)` und `build_tennis_training_rows(...)` sind durch diesen
geschlossenen EventCase-/Config-Vertrag ersetzt. Sie erhalten weder einen
schwächeren Parallelpfad noch einen Adapter, der unbewiesene Rows akzeptiert.

`rg --no-ignore` über sämtliche Pythondateien dieses Worktrees (ohne TEMP,
Umgebung und andere Worktrees) fand **keine Implementierung und keinen Aufrufer**
der beiden alten Funktionen. Nur der neue Assemblypfad, `fit_family` und die
zugehörigen Tests existieren. Die alten Namen stehen ausschließlich in
Plan-/Tasktexten bzw. dem früheren B5-Offenbericht. Es war kein vorhandener
Produktionsaufrufer umzustellen. B5/B7 sind damit bezüglich dieser
Assemblymechanik abgedeckt, nicht bezüglich eines real kausalen Fits.

## Tatsächlich implementierter Beleg- und Rechenpfad

Football replayt die ursprüngliche reine Torrechnung über vorhandene native
Detailreceipts und deren tatsächliche Uhren. Die ausdrücklich neue Version
`football-goals-raw-reference-v1` behauptet **keine** Parität mit historisch
marktweise kalibrierten Ausgaben. Ohne früh belegtes Kalibratorartefakt wird
keine alte Kurve übernommen und kein `challenge_stats`/xG aus freien Feldern
erfunden. Fehlende ursprüngliche Historie ergibt keinen Standardwert.

Der vollständige deklarierte native Receiptpool wird vor Recipe-Matching nach
Eventrevision ausgewählt. Eine bekannte neuere Korrektur lässt sich nicht durch
die explizite Auswahl älterer Recipe-IDs verstecken. Gleichzeitiger materieller
Konflikt bleibt unbekannt. Mitgelieferte native Player-/XI-Kollektionen müssen
ihre B4-Projektionen mit genau derselben tatsächlichen Receiptzeit auflösen;
neuere native Daten mit alten Minuten sind kein stimmiges Trainingscase.
Explizit leere Kollektionen bleiben Rücknahmen; ein **nicht mitgeliefertes**
Feld ist dagegen kein Beleg einer leeren Mannschaft.

Features werden vollständig mit B4 aus den ursprünglichen Receiptbytes gegen
genau die Basis und den Event neu berechnet. Die frei angelieferte FeatureVector
muss exakt übereinstimmen. Fehlende Spielerspalten werden nicht mit null
aufgefüllt. Zielresultate gehen nicht in die Featurehistorie ein. Unbekannte
Aliasse, retrospektiv importierte Quellen ohne owning Archivbeleg und nicht
aufgelöste Vorverarbeitung bleiben explizite Ausschlüsse.

Alle Kandidatencutoffs werden geprüft, **bevor** die Fitfunktion Assembly,
Resultatreceipts oder Row-Targets öffnet. Finale Cases führen zu einem Fehler;
sie werden nicht nach dem Lesen aussortiert. Native Events sind einmalig,
mehrere Heads zählen nicht als unabhängige Events. Die gelieferten scalar Rows
müssen mit der echten Assembly exakt übereinstimmen. Verspätete Outcomes gehen
nicht in den früheren Fit ein und wandern nicht in einen bequemeren Split.

Für jedes Alpha werden Skalen und Koeffizienten nur auf Train geschätzt. Tune bewertet alle
vorab benannten Märkte pro Event, dann Events ungewichtet. Ein fehlgeschlagener
Vergleich verwirft den **gesamten Alpha-Kandidaten**, nicht nur ein ungünstiges
Event. Alle fünf Ergebnisse bleiben sichtbar. Exakte Brier-Gleichstände wählen
das größere Alpha. Es gibt kein Train+Tune-Refit, keinen neuen Intercept, keine
feste Prozentkorrektur und keine nachträgliche numerische Glättung.

Tennis-Serve rechnet in den ausdrücklich synthetischen Tests einen gemeinsamen
spiegeltransformierten A/B-Fit je Alpha und leitet den gegenüberliegenden Head
exakt ab. Vier echte Eventeinheiten bleiben vier, auch bei acht Headbeobachtungen.
Unexakt darstellbare JSON-Ganzzahlen werden vor Float64-Konversion abgelehnt.
Hold-/Break-Zielzahlen müssen die beobachteten Nicht-Tiebreak-Games reproduzieren
und bei einer möglichen tatsächlichen Aufschlagreihenfolge entstehen können.

FitResult bindet alle Alpha-Artefakte, ausgewähltes Alpha, Config/Map/Cases/Rows,
train-only Herkunft sowie Ausschlüsse. Jeder angeforderte Case muss genau einmal
Train, Tune oder einem benannten Ausschluss zugeordnet sein; Doppelzählung,
verwaiste Ausschlüsse und still verschwundene Cases werden abgelehnt.

## Ehrlich offene Daten- und Folgearbeiten

1. **Echter Tennis-Replay:** Kein owning Quellenresolver belegt bislang native
   ESPN-Spieler-IDs gegen die namensbasierten ursprünglichen Tour-State-Keys.
   Eine frei angegebene `verified`-/Authority-Zeichenfolge ersetzt das nicht.
   Der öffentliche Case-/Fitpfad bleibt deshalb `unsupported`. Reine Winner-
   und Serve-Rechentests sind sichtbar synthetisch und öffnen diesen Pfad nicht.
2. **Frühere Participationfits:** Der B4-Transport besitzt nur einen
   `training_refs_hash`, nicht die aufgelösten früheren Trainingsreceipts und
   Teilnahme-Outcomes. Selbst ein früheres `training_end` ist kein Nachweis.
   Dieser Pfad meldet `participation_training_receipts_unresolved`. Ein eigener
   belegauflösender Vorverarbeitungsvertrag fehlt weiterhin.
3. **Echte Football-/weitere Sport-Corpora:** Keine neue Vollinventur und kein
   echter Fit in diesem Paket. Der vorhandene eingeschränkte Inventarbericht
   und reale Quellenproben sind kein historischer Prematch-Datensatz. Fehlende
   kausale Uhrzeiten, native Bindungen oder Featurevokabulare werden nicht erfunden.
4. **D1/D2-Integration:** Registry/Freeze/Opening führt der Controller separat
   aus. CLI mit expliziten lokalen Pfaden, echte Datenauswertung und deren
   Reports folgen erst nach unabhängigem Review dieser Schnittstellen.
5. **Empirische Aktivierung:** Die unveränderten 200 eindeutigen Testevents,
   drei aufeinanderfolgenden Blöcke, Verbesserung/Unsicherheit/FDR,
   Verteilungsverlust und Marktkalibrierung sind nicht nachgewiesen.
   Teilweise Mechanik darf nicht als vollständig erledigte Task 16 gelten.

## RED/GREEN und Reproduktion

Interpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
Alle Läufe `-B -m pytest -q -p no:cacheprovider`, jeweils neues
`--basetemp=.pytest_tmp/<eindeutiger-name>` in diesem Worktree.

- Config: echte fehlende neue Funktion/Modul RED, dann 27 grün; die vom
  Controller gefundenen JSON-Typkanten anschließend 2 RED, danach 51 grün.
- Native Outcome/Identity-Checkpoint: 92 grün. Zwei unabhängige Serve-
  Inkonsistenzen danach selbst RED reproduziert und behoben; 95 grün.
- Neue Replayfunktion: 10 RED, anschließend 10 grün (40,72 s).
- Neue Caseassembly: 10 RED, anschließend 10 grün. Eigene bekannte-Revision-
  und vermischte-Minuten-Gegenfälle: 2 zusätzliche echte RED; anschließend
  12 grün. Positive Omission-Grenze zuerst 1 RED, nun 13 grün (15,33 s).
- Neue Fitfunktion: 6 RED. Der erste Nachlauf hatte 5 grün und einen fehlerhaften
  Testvergleich (`None` eines ehrlich fehlgeschlagenen Alphas in `min`). Dieser
  Test zählt fehlgeschlagene Kandidaten nun ausdrücklich mit und wählt nur
  vollständig gescorte; keine Produktionsformel wurde dafür geändert.
- Separater FitResult: 13 RED auf fehlenden Validator, dann grün. Fünf zusätzliche
  vollständige-Inventar-Gegenfälle RED; nach Korrektur 24 Report-/Tennismathtests
  grün (0,81 s), inklusive positiver benannter Ausschlüsse.
- Gesamter D1-Fokus vor diesen letzten sechs Reporttests: **176 grün**,
  90,94 s, `d1-focus-complete-01`. Enthält die unveränderten 34 Splitregressionen.
- Vollsuite mit den letzten Reportregressionen: **3.463 bestanden, 15 erwartete
  Windows-Skips, 97 Untertests bestanden**, 166,80 s, `d1-full-suite-01`.
  Der finale D1-Umfang umfasst 148 neue Tests plus die unveränderten 34 Splittests.

Die Modelltests erzeugen ausdrücklich synthetische native Fixtures und echte
TEMP-B1-Receipts. Sie beweisen Rechen-/Vertragsmechanik, nicht eine beobachtete
Sportwirkung. Kein synthetischer Fall wird als historischer Datensatz veröffentlicht.

## Eingefrorene Source-/Testbytes für unabhängigen Gegenlauf

SHA-256 vor abschließendem Commit (Auditdatei selbst ausgenommen):

```text
e61943527fd764d1017f3c78ae09cd5d1d8bc67db44e19961517bc4b329e6786 context_sources/outcomes.py
38e876e0e82f03290e3fbd76a72239893237ed70865987a63c86f639ac6f89ce context_models/training_contracts.py
13bdb7b4b73b85d3b522411e364577e65f4b2545336e87d7fd94d1ce55ff609e context_models/replay.py
ce05e30b6062a40d76d5b76715fd30375cdb3a582131333adb97a98acbf8eeb1 context_models/training_cases.py
fcf953d738b7f1249c68b65532f55142c8ad77e3b4a6de861c15bcab87efca6a context_models/training.py
09af0fb155011fce193ed76c15962bb713d6645944b730bbd5218c8c110e4cc4 tests/context_training_helpers.py
d378bc787948ead6ed56201f611c32fc9c6d2365bc3fc5ff0d633e346f263673 tests/test_context_training_contracts.py
937c0a2a5d8fd8f0ee84e80a6ac7e2bbcab8fcca4a4961d2e8459d2d8c1f2861 tests/fixtures/context/training/tennis-winner-family-v1.json
849161dcb97a8056a8e96127d68b8c858e261a4539e8ecf0bc600c0f723e8f69 tests/test_context_outcomes.py
c50d5f557a6239bd32c9090dfe0d2b630e8197d28a3255a9c5832420a75b27e5 tests/test_context_training_identity.py
4c71f947094d4b6f9ff6db3a8d92399c76472b7667a8ac222997bb0e741c2b06 tests/test_context_replay.py
bba6aeb14f39f1a9fecc2bcb2ee15a440efd8530196997b20a508a9182a35a4e tests/test_context_training_cases.py
6004affa24b580e8df44000cacf1ab603a61a82eb2317b31603dfd9d86756675 tests/test_context_training_fit.py
899d64f9697c4237d5108653deb5591b9e6c2d4ed19940c7da42cfbfbcde956b tests/test_context_training_reports.py
debc173076f64f2e54fe3051eb959119b0efe288bbf9647c063e46c3681ccac3 tests/test_context_training_tennis_math.py
```

Der damalige unabhängige Abschlussreview war noch ausstehend. Sein tatsächliches
Ergebnis und die begrenzte Nachkorrektur sind im folgenden Nachtrag dokumentiert.

## Reviewnachtrag: Identitätsbeleg bleibt bei legitimem Refresh gültig

Ausgangscommit der Korrektur: `b74e2abd759a952991559709833470b3c3b160c0`.
Der vollständig gelesene unabhängige Bericht
`.pytest_tmp/d1-independent-20260909/review-d1.md` hat SHA-256
`01f5e6535015e70afaa0f9459a12e877ac23c9b4ba9be9efb48c53cb5e08d787`.
Er fand genau **einen P2-Verfügbarkeitsfehler**, keine neue Freigabe- oder
numerische Modellbehauptung: Nach einem legitim späteren nativen Targetreceipt
suchte Replay den in der globalen Identitätsmap genannten ursprünglichen
Targetbeleg nur noch in den mathematisch neuesten Zeilen. Obwohl der alte
gültige Beleg weiter im vollständigen kausalen Eingabepool lag, ging die
Identitätsprüfung dadurch fälschlich von einem fehlenden Beleg aus.

Die Korrektur ändert ausschließlich das Argument der bestehenden
`resolve_identity_map`-Anwendung: Sie erhält nun den vollständigen `history`-
Receiptpool, **nachdem** `_selected_native_rows` sämtliche Receipts und
Quellenzeiten validiert hat. Recipe-Matching, aktuelle Target-/Team-/Schedule-
Prüfung, Native-Provenienz und mathematische Baseline verwenden unverändert
die streng neuesten ausgewählten `rows`. Keine alte Aufstellung, Spielerminute
oder Zielzahl wird dadurch zum aktuellen Modelleingang. Keine freie neue
Altersgrenze für Identitätsbelege: Alt ist nicht allein deshalb ungültig; fehlend,
fremd, nachträglich importiert, manipuliert oder mit aktuellem Event unvereinbar
bleibt ungültig. Nur der explizit angeforderte native Event wird aufgelöst;
der ursprüngliche globale Maphash bleibt gebunden.

Die 16 neuen permanenten Fälle in `tests/test_context_replay_identity_refresh.py`
verwenden synthetische Sportdaten und genuine lokale B1-Persistenz:

- Identischer Recheck und geänderte XI-Position, jeweils beide Reihenfolgen des
  Receiptpools; unveränderter globaler Identitätsbeleg wird akzeptiert.
- Spies belegen genau eine ursprüngliche Modell-/Native-Provenienzrechnung,
  ausschließlich aktuellen Targetreceipt, 26 eindeutige historische Spiele und
  unveränderte Raw-Mathematik; Inputs/Map/Recipe bleiben unverändert.
- Unangeforderter weiterer Map-Eintrag wird nicht aufgelöst und benötigt keine
  Öffnung seiner Receipts. Fehlender Receipt/Ref oder fremder Event bleibt zu.
- Eine ältere anders orientierte native Quelle, eine inzwischen veraltete
  Teammap und ein unpassender aktueller Termin erreichen weiterhin ihre
  konkreten bestehenden Identitäts-/Schedule-Guards.
- Ein nach dem Cutoff empfangener Beleg sowie manipulierte ältere Bytes werden
  abgelehnt, bevor der Identitätsresolver überhaupt erreicht wird.
- Ein altes Recipe oder der gesamte Revisionspool als mathematisches Recipe
  bleibt ungültig. Vollständige aktualisierte Caseassembly mit neuen tatsächlichen
  XI-Projektionen funktioniert dagegen bei unverändertem Identitätsmaphash.

### Eigener RED/GREEN-Gegenlauf der Korrektur

Alle Läufe mit demselben oben angegebenen Quality-Interpreter, `-B -m pytest -q
-p no:cacheprovider`, jeweils eigenem frischem Basetemp:

| Lauf | Ergebnis | Basetemp |
| --- | --- | --- |
| Beide unveränderten unabhängigen Reviewerdateien, vor Sourceänderung | **2 fehlgeschlagen, 23 bestanden**, 17,39 s | `d1-refresh-original-red-01` |
| Neue permanente Refreshregressionen, vor Sourceänderung | **9 fehlgeschlagen, 7 bestanden**, 14,67 s | `d1-refresh-permanent-red-01` |
| Neue Regressionen + beide Original-Reviewerdateien nach enger Korrektur | **41 bestanden**, 33,19 s | `d1-refresh-green-01` |
| Vollständiger D1-Fokus inklusive 34 unveränderter Splittests, 16 neuer Regressionen und 25 unabhängiger Gegenproben | **223 bestanden**, 123,32 s | `d1-refresh-focus-01` |
| Gesamte bestehende Testsuite einschließlich neuer permanenter Regressionen | **3.479 bestanden, 15 erwartete Windows-Skips, 97 Untertests bestanden**, 178,86 s | `d1-refresh-full-01` |

Die neun permanenten RED-Ausgänge sind nicht neun unabhängige Modellfehler:
Sechs sind gültige Refresh-/Assemblyfälle desselben P2; drei weitere verlangen
die konkret zuständigen nachgelagerten Identitäts-/Schedule-Guards, die zuvor
schon am falsch reduzierten Belegpool hängen blieben. Ihre Schutzwirkung wurde
nicht gelockert. Die beiden ursprünglichen Refreshreproduktionen und sämtliche
23 zusätzlichen unabhängigen Negativ-/Rechenfälle wurden unverändert ausgeführt.

### Eingefrorene Repro- und Korrekturbytes

```text
fb7e0d581f45144c1f1b0456f828e58a7cb16ac124c1ec9683dc4f2b43fae32d context_models/replay.py
cc3084075b601c211c632d50eab28b4b1a0f5e9134aa83cb1caae09de7f636b4 tests/test_context_replay_identity_refresh.py
01f5e6535015e70afaa0f9459a12e877ac23c9b4ba9be9efb48c53cb5e08d787 .pytest_tmp/d1-independent-20260909/review-d1.md
5c26c3bf49d2b4b4ab3b109ea73b8d5029a883d899deba0d2367f71dc7123a0c .pytest_tmp/d1-independent-20260909/test_d1_independent.py
4a52a1f59408818c06d3645fffc83c64c6ddae0c404d5d0faa34eaa76a219aea .pytest_tmp/d1-independent-20260909/test_d1_math_independent.py
```

Beide Reviewerdateien und deren Bericht bleiben unverändert. Bestehende
Trainings-/Case-/Outcome-/B1-Verträge und der bestehende Testhelper behalten ihre
vorherigen Bytes. Keine Tennis-/Participation-Freigabe, Schema- oder Source-
Erweiterung. Keine Root-, Provider-, Produktions-, Push- oder VPS-Schreibvorgänge.
Der Fix hebt keine der zuvor dokumentierten Daten-/Empirikgrenzen auf.
Unabhängige erneute Prüfung der Korrektur: noch ausstehend.
