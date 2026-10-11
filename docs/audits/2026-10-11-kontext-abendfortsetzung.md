# Kontextmodelle – Abendfortsetzung am 11.10.2026

## Ausgang und Umfang

Git lokal, GitHub-main und VPS am 11.10. um 19:38 CEST gemeinsam
`8dfabe964ad382ecc32a2a21ae4c48b926129458`; getrackter VPS-Stand sauber.
App/Caddy aktiv. Keine neue Sport-/API-Abfrage, kein Backup oder Löschen.
Die bereits veröffentlichte API-Hockey-Erweiterung bleibt erhalten; Cricket
unverändert. Dieser Bericht trennt Reparatur, Produktionsnachweis und fachliche
Effektvalidierung. Er ersetzt keine bessere Wettqualität durch Softwaretests.

## 1. Zwei Fußball-Kanten nach dem bereits behobenen Fremdteamfehler

### Tatsächlich verwendeter Kader

`context_models/football.py:football_features` besitzt genau bezeichnete,
native Modellhistorien und Komponentenreferenzen. Bisher konnten auch ältere
Spieler desselben Zielvereins aus völlig anderen Spielen eine aktuelle
Statusabdeckung verpflichtend machen. Eine solche fehlende Statuszeile
verdrängte alle ansonsten belegten Ausfallmerkmale.

Die Reparatur bestimmt die erwartete Spielergruppe aus den wirklich verwendeten
nativen Event-/Teamreferenzen plus sämtlichen aktuellen gemeldeten Spielern.
Die breitere Historie derselben Spieler bleibt für belegte Einsatzrollen
erhalten. Neue Spieler oder Transfers bleiben ohne Rollenbeleg unbekannt.
Alle Quellreceipts und der gesamte Originalvertrag werden vor dem Supportfilter
validiert; irrelevante beschädigte Daten werden nicht still akzeptiert.

### Nullgewicht ist kein mathematischer Support

Der Originalvertrag erlaubt Samplegewicht 0. Ein gültiger zusätzlich referierter
historischer Sample mit Gewicht 0 änderte keine Grundverteilung, konnte aber
ebenfalls einen ehemaligen Spieler verpflichtend machen und sämtliche Merkmale
auf unbekannt setzen. Solche Samples müssen sowohl bei der Kadergruppe als auch
bei der Komponenten-/Spieleraggregation aus dem tatsächlichen Support entfallen.
Die vollständige Quellenprüfung bleibt trotzdem unverändert.

### Versions- und Altartefaktschutz

Bestehende D2-Abnahmen binden die genaue `football.py`-Implementierung in
`context_models/evaluator.py:implementation_hashes`. `_verify_evaluation`
vergleicht aktuelle Quellhashes; `approved_effect` verwendet
`verify_approval` → `verify_evaluation`. Ein korrekt äußerlich gehashtes, aber
auf alter Fußballimplementierung bewertetes Artefakt darf nicht wiederverwendet
werden. Keine alte Abnahme, Prognose oder Koeffizientendatei wird umgeschrieben.

## 2. Tatsächliche Tennis-Revisionen statt Datenbankreihenfolge

`tennis.shadow.workload_history` enthält je Modell-/Policygeneration eigene
Eltern desselben nativen Spiels. Die Zeilen sind nicht chronologisch geordnet.
Die alte Anzeige behielt den ersten Satz pro Quelle/Event und konnte deshalb
für identische Daten 2 statt 3 Sätze, 80 statt 120 Minuten und einen veralteten
Ergebnisstand anzeigen.

`tennis/workload.py` löst nun zuerst die jüngste zum Stichtag bekannte Revision
pro Quelle/Event/Tour auf; erst danach werden Spieler und gespielte Endzustände
geprüft. Eine neuere geänderte Paarung, ein Walkover oder unbekannter Endzustand
darf keine alte gespielte Belastung reaktivieren. Widersprüche am gleichen
Empfangszeitpunkt werden nicht nach Zeilenreihenfolge entschieden; gleichwertige
Duplikate und umgedrehte Spielerorientierungen zählen einmal.

ATP/WTA teilen keinen Eventnummernraum. Tourlose Altdaten werden nicht aus Namen
einer Tour zugeordnet und neben gebundenen Eltern nicht doppelt gezählt. Eine
neuere/gleichzeitige ungebundene Korrektur macht den betroffenen älteren Zweig
unbrauchbar, statt ihn als scheinbar gesichert weiterzuführen.

Diese Daten sind weiterhin reine beobachtete Belastungsfakten. Tatsächliches
Matchende oder Erholungsstunden werden daraus nicht behauptet;
`minimum_recovery_hours=None`, `probability_adjustment_applied=False`,
`adjustment_pp=0`. Regressionen prüfen echte persistierte Eltern und identische
Sieg-/Nebenmarktwahrscheinlichkeiten, Gates und Verdict des produktiven
`POINT_MODEL_VERSION`-Pfades. Keine bereits gespeicherten Eltern werden geändert.

Geltungsgrenze: `workload_history` liest abgeschlossene Shadow-Eltern
(`settled=1`), nicht die vollständige revidierbare B1-Quellhistorie. Der owning
Writer setzt Ergebniszeit und Abrechnung atomar und lässt keine zweite
Abrechnung desselben Elterns zu. Die Reparatur ersetzt keine B1-Tennis-
Revisionsauflösung und öffnet keine bislang ungeklärten Abrechnungen.

## 3. Strukturelle Restarbeiten – nicht nur mehr Daten

### Hockey und Basketball

Die unabhängige Code-/Callsiteprüfung bestätigt:

- `context_sources/team_sports_capture.py:capture_team_sports_worker` wird nur
  in Tests aufgerufen. Produktive NBA/EuroLeague/NHL-Observer sind ohne Besitzer
  inaktiv. `CompletedHistoryStore` bewahrt separat Ergebnissummaries, ersetzt
  aber keine originale native Antwort oder ihren damaligen Empfangsnachweis.
- Die NBA-Normalisierung verwirft vorhandene Saisonangaben; der native Binder
  meldet danach korrekt `raw-season-unavailable`. Fehlende Angaben nicht aus
  Kalenderdatum ableiten.
- `context_models/team_sports_live.py:build_hockey_live_original` hat ebenfalls
  keinen produktiven Aufrufer. Sein Original bleibt `source_resolution=unresolved`,
  ohne source-resolved history refs. `sports_prematch.OriginalPrematch` ist eine
  reale Same-call-Schnittstelle, gegenwärtig aber nur für Formdarstellung benutzt.
- Liveverträge `hockey-live-original-poisson-v1` /
  `hockey-live-poisson-origin-v1` sind nicht die qualifizierten Effektverträge
  `hockey-original-poisson-v1` / `hockey-original-poisson-reference-v1`.
  Umbenennen oder eine Checkbox ist keine Quellenauflösung.
- `context_models/training_contracts.py` erlaubt D1 nur Fußball/Tennis;
  Identitätsmap, Fit, Evaluator, Verteilungsverluste und Aktivierung fehlen für
  Basketball/Hockey. Der nichtfußballspezifische Brierpfad routet zu Tennis.
  Generisch unabhängig gefittete Hockeyheads würden die verlangte gemeinsame,
  gespiegelte Kopfstruktur verletzen.
- `context_sources/outcomes.py` und das owning Replay haben keinen vollständigen
  Hockey-/Basketball-Endergebnisvertrag für diese Effektabnahme.
- Gemessene Spieler-Einsatzzeiten, tatsächliche Matchzeiten, bestätigte
  Starttorhüter und projizierte Aufstellungen werden von den bestehenden
  Spielplanantworten nicht automatisch mitgeliefert.

Ein synthetischer Parameter-Gegentest beweist nur, dass interne Effektfunktionen
Parameter verändern können; er belegt keinen trainierbaren Produktionspfad.

### Kleinste vollständige NHL-Reihenfolge

1. Bereits stattfindende native Antwortaufnahme budgetiert einschalten; keine
   neue API-Abfrage. Reale Uhren und Revisionen erhalten, warmer Cache wird kein
   neuer B1-Receipt. Physisch begrenzte Speicherung verlangen.
2. Das tatsächliche Same-call-Original vor Anpfiff nativ an Quellen, Saison,
   Regulär-/OT-/Penaltyregeln, Heim/Neutral und alle verwendeten Inputs binden.
   Keine rückwirkende Originalveröffentlichung aus späteren Ergebnissen.
3. Native NHL-Regulärergebnisse aus echten Finalscores und
   `gameOutcome.lastPeriodType`/Periodenvertrag auflösen; Teilnehmerwechsel,
   Absagen und Endzustände kausal prüfen. Kein tatsächliches Matchende oder TOI
   aus Finalstatus raten.
4. Owning Case/Replay, NHL-native Identität, geschlossenen Fit mit gepoolten
   gespiegelten Heads und Torhüterconstraints, Targets, gemeinsame Verluste,
   Evaluator und Aktivierung gemeinsam implementieren und gegentesten.
5. Tatsächliche Spieler-/Torhüter-/Timingquellen anschließen, soweit verfügbar;
   keine erfundenen Einsatzminuten oder Gesundannahmen. Zunächst keine
   Übertragung dieser NHL-Verträge auf API-Hockey-Ligen.
6. Chronologische Trainings-/Abstimmungs-/unberührte Testkohorte nach genehmigter
   Spezifikation vollständig abnehmen, mindestens 200 unabhängige Testspiele
   zusätzlich. Erst dann darf ein gemessener Effekt aktiv sein.

Kein weiterer isolierter Stub wird als Erledigung dieses Ende-zu-Ende-Pfades
verkauft. Der nächste implementierbare Auftrag muss die zusammengehörigen
Source-/Original-/Ergebnis-/Fitteile besitzen.

### Tennis und Fußball

Reale zurückbehaltene Tennis-ESPN-Antworten enthalten Sätze/Games, aber keine
gemessenen Minuten oder echten Start-/Endzeiten. `normalize_tennis_workload`
bewahrt deren Fehlen korrekt; eine Parseränderung kann sie nicht erzeugen.
Zudem deaktiviert `tennis/live_context.py` die alte Siegerkorrektur im aktuellen
`serve-points-joint-v2`: Gewinnerlabels identifizieren nicht beide Serveparameter.
Die genehmigte Spezifikation verlangt point-kompatible Effekte; eine beliebige
Siegerkorrektur auf alle Sätze/Games wäre mathematisch inkonsistent.

Fußball besitzt echte Kader-/Wetterpfade, aber nur acht zuletzt geprüfte
vollständige Originalbindungen und keine eigene unabhängige 200-Testspielkohorte.
Neun Wetterreceipts sind keine Wettereffektabnahme. Fehlender aktiver Fit löst
einen Earlyreturn aus; daraus dürfen keine gemessenen Nullmerkmale behauptet
werden. Keine geratenen Wetter-/Ausfallkoeffizienten.

## 4. QA und Veröffentlichung

Final eingefrorene lokale Windows-QA-Dateihashes SHA256:

```text
context_models/football.py
f101a6d57645b365bfc7f6adb4004d93e769349d4841fbb80a7b8069a8de768d
tennis/workload.py
5e2b113f843f942a65fc71bf261fb337193aad81ae131b38156febecdc92c161
tests/test_football_context_features.py
938a2cf0224837b80f15fa993f995eac924fbc7084b07000cb662a98b44e0aa7
tests/test_tennis_workload_truth.py
f5d8424cae9bb385e2a19ec0322fef191d8f67865d3574e818a294f5781184eb
```

Diese vier Hashes belegen den unveränderten lokalen QA-Snapshot, nicht eine
plattformübergreifende Byteidentität: Git normalisiert hier Python-Zeilenenden
von Windows-CRLF auf LF. Der Servernachweis erfolgt deshalb über den exakten
Commit und zusätzlich dessen Git-Blob-/VPS-Quellbytes. Kein lokaler D2-Fit wird
auf den VPS übertragen; dessen Implementierungsbindung bleibt exakt.

- Eigene Fußballregression 31/31, Tennisregression 26/26.
- Finaler unabhängiger gemeinsamer Ownerlauf 57 bestanden, 11,16 s, Exit 0;
  dazu 26 separate Permutations-/Nullsupport-/Unbekannt-Korrekturoracles grün.
  `C:/Projekt/BetBoy/output/hockey-seasons-20261011/cohort-workload-final.xml`.
- Eingefrorene Tennis-Nachbarregression: 508 bestanden, keine Fehler/Skips,
  190,16 s; zehn ganze Module, kein Filter.
  `C:/Projekt/BetBoy/output/hockey-context-20261011/tennis-workload-final-neighbor06.xml`.
- Der frühere Fußball-Nachbarlauf ist **kein finaler Pass**: 527 bestanden,
  zwei Fehlfälle nach zwischenzeitlicher Sourceänderung. Genau zwei
  Evaluatortests lehnten korrekt den in ihrer früher erstellten Fixture
  gebundenen alten Implementierungshash ab. Er wird nicht durch Summieren mit
  Teilrunden beschönigt. Der neue gemeinsame Lauf erzeugt alle Fixtures erst
  auf den endgültig eingefrorenen Quellen.
- Der abschließende gemeinsame Offline-Lauf ist beendet: **1.039 bestanden,
  keine Fehler/Skips**, 700,86 s, Exit 0, 25 ganze Module. Externe
  Netzwerkverbindungen im Starter gesperrt, keine Testfälle ausgefiltert.
  Eine bestehende JUnit-`record_property`-Warnung, kein Lauf-/Modellfehler.
  `C:/Projekt/BetBoy/output/context-followup-20261011/release-01.xml`.
  Die vier oben angegebenen Quell-/Testhashes sind vorher/nachher identisch.

Die Agentenrunden überschneiden sich; ihre Fallzahlen werden nicht addiert und
sind keine neue Vollsuite. Der Deployment-Helfer ist unabhängig geprüft:
sieben erlaubte Pfade, exact base/main/Remote, Fast-forward, zwei natürliche
Idlechecks, keine Timerunterbrechung; maximal 336 s einschließlich Recovery
innerhalb des geforderten Zeitfensters über 360 s. Er stellt bei Fehlern App-
Gesundheit wieder her, garantiert keinen alten Code-/Datenrollback.

Aktueller separat gelesener VPS-Status 19:55:43 CEST, noch vor Veröffentlichung:
App/Caddy aktiv, interner Healthcheck `ok`. Fußball-Shadow letzter regulärer
Abschluss 19:52:26 CEST inzwischen Exit 0/Result success; der frühere Teilstatus
ist nicht mehr der letzte Dienstabschluss. Das zusätzlich gelesene echte
19:52-Berichtsartefakt meldet `completed`, zwei geprüfte Spiele, keine neuen
Prognosen/Schlussquoten/Abrechnungen und keine technischen Fehler. Die beiden
alten ungültigen Evidenzzeilen bleiben ausdrücklich erkannt
(`invalid_quote_provenance`, `malformed_settlement`); der Lauf ist kein neuer
Qualitäts- oder Renditenachweis. Tennis zuletzt Exit 0 um 00:32:29.
Tageslauf weiter alter Timeout/Exit 15 um 04:20:22; neues Laufzeitlimit erst beim
nächsten regulären Lauf bewertbar. Kein Dienst zusätzlich gestartet/zurückgesetzt.

Code-/Test-/Auditcommit `dccef90a86491709988bc5adebedebf580ccb78b` ist auf
main gepusht; VPS origin/main wurde nur vorbereitend gefetcht. Bei 20:07:02
bleibt der laufende VPS-Appcode auf dem Ausgang `8dfabe9`; das natürliche
sechsminütige Fenster ist vor 20:12 zu kurz. Kein Timer wird dafür angehalten.
Der reguläre 20:02-Lauf endete inzwischen mit Exit 1/`partial`: ein geprüfter
Kandidat ohne frische Bet365-Providerquote, regulärer Retry. Kein App-Absturz;
die zwei alten ungültigen Evidenzzeilen weiterhin unverändert erkannt.
19:52-Erfolg ist deshalb nicht der neueste vollständige Status. Alle Scans
waren bereits regulär geplant, nicht durch diese Prüfung zusätzlich ausgelöst.

**VPS-Veröffentlichung abgeschlossen gegen 20:13 CEST:** nach dem regulären
Shadow-Abschluss 20:12:17 waren alle Sportdienste inaktiv/failed und das nächste
natürliche Timerfenster über sechs Minuten entfernt. Beide Guards erfüllt;
kein Timer oder Job unterbrochen. Codecommit `dccef90a86491709988bc5adebedebf580ccb78b`
per geprüftem Fast-forward deployed, beide Offlineimports erfolgreich, getrackter
VPS-Stand sauber. App/Caddy und sieben reguläre Timer aktiv; tägliches Backup
weiter inaktiv. Beide Healthchecks `ok` am 11.10.20:13:47. Zwei kurzzeitige
Start-Verbindungs-Retries im Deployment, danach innerhalb des Budgets gesund.
Keine dauerhafte Verbindungsstörung oder Fehler-Recovery notwendig.

Die echten VPS-Quellbytes entsprechen ihren Git-Blobs SHA256:

```text
context_models/football.py
f101a6d57645b365bfc7f6adb4004d93e769349d4841fbb80a7b8069a8de768d
tennis/workload.py
60440fa4d0c0cbe3a09ec9bd09d87ec857fbf3f02505be8e12c184beb9babf04
```

Erste Hashleseprobe als unprivilegierter SSH-Nutzer hatte nur fehlende
Leseberechtigung; korrekt als Appnutzer wiederholt, keine Permissions geändert.
Wettfinder-JSON SHA256 vor/nach Deployment identisch:
`a51c9d865ab14db2d7d17971e469cbb029045a7107dd7417f2ff9da17af4298e`.
RisikoBet-JSON ebenso:
`acf24df6d14786a744b8fdf30a690bada1b34f84d54e32eb1e3915cdc3350ede`.
Keine neue Preisabfrage, Prognosepublikation, Effektaktivierung oder Geld-/Ergebnisänderung.

Letzter tatsächlicher regulärer Shadow-Bericht 20:12:17 weiterhin Exit 1/`partial`:
ein Kandidat zur erneuten Prüfung zurückgestellt, keine neue Prognose/Schlussquote/Abrechnung, keine
frische Bet365-Providerquote für Fixture 1638630; normaler weiterer Retry.
Die zwei alten ungültigen Provenienz-/Settlementzeilen bleiben erkannt.
Tageslauf weiterhin der alte Timeoutstatus, Tennis letzter regulärer Lauf
erfolgreich. Neues Tageslimit und echte zusätzliche Hockeyabdeckung erst beim
12.10.03:35-Lauf beweisbar. Ein Deploy/Healthcheck ist kein Sportlaufnachweis.

Der anschließende reine Nachweis-/Übergabecommit enthält nur diese drei
Dokumente und wird ohne Appneustart auf dem VPS fast-forwarded. Bereits
vorhandene ungetrackte Audit-/Browserdateien bleiben unberührt. Kein neuer
Sportscan, Backup, Löschen oder Geld-/Ergebnisänderung für diesen Nachweis.
