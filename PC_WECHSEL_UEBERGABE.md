# BetBoy - Übergabe auf einen neuen PC

## Aktueller Fortsetzungsstand vom 10. September 2026 — 00:20 CEST

Root und gepushter Featurebranch stehen auf `6d03ca0`; GitHub main zuletzt
21:56 UTC weiterhin `2ba3931`. Kein Kontext-Deployment. Der frühere Ablauf
ist übernommen; bestehende Freigaben müssen nicht erneut erfragt werden.

- Ganze Root-Regression fertig: **6168 bestanden, 20 Windows-Skips,
  97 Untertests, 1206,62 Sekunden**, separat unveränderlich auf `6d03ca0`.
- Tatsächliche Linux-Root/App-Rechteprüfung bestanden: echte CLI-Resultate
  0/2/1, zwölf verweigerte Dateioperationen, positive Lese-/Schreibkontrollen,
  Timeout und begrenzte Ausgabe. Keine Produktionsdaten oder Schlüssel
  angerührt. Installierter vertrauenswürdiger Übergang A→B bleibt offen.
- Basketball/Hockey-Resolver P4b2 auf `ba73dc9` eingefroren; unabhängiges
  Review läuft jetzt gegen genau diesen Stand. Noch nicht integriert.
- Fußball-Original P5a `8691022`: Root fand vier echte Fehlerfälle für
  übergroße ungenutzte Kalibrier-Metadaten. Enger Fix in eigener Arbeitskopie;
  gültige Originalprognosen dürfen daran nicht scheitern. Noch nicht integriert.
- E-Sport: tatsächlich doppelte Elo-Rechnung im Logger und Scan nachgewiesen.
  Enger Same-call-Fix wird separat umgesetzt, ohne historische SQL-Werte,
  Modelle, First-observation oder Abrechnung zu verändern.

Die genannten Prüfungen belegen Softwaregrenzen, noch keine neue Wirkung von
Verletzungen/Müdigkeit. Reale gemeinsame Worker-/Consumeranbindung weiterer
Sportarten, Quellenlücken/Empirie, finale Browserprüfung und Main/VPS-Release
bleiben offen. Cricket bleibt ausgenommen. Fremde Dateien und gepinnter
Stagehelper bleiben unverändert. Neue Root-Berichte im SDD-Ledger sichern
Originalfehler, Ergebnisse und Quellenhashes separat.

## Aktueller Fortsetzungsstand vom 9. September 2026 — 21:53 UTC

Root-Code `4f49a8c86e98d56127f5419d0b63b629997e0712`. Neu übernommen sind
unabhängig geprüfter gemeinsamer Tennis-Consumer samt Korrektur `5a865e0`,
Basketball/Hockey-Originale samt ID-Reihenfolgefix `e284e7a`, echte bestehende
Antwort-Captures `b2b7d34` und Linux-Testfixture-Korrektur `2346846`.
Main/GitHub/VPS frisch21:08UTC weiterhin `2ba3931`, **kein Kontext-Deployment**.

- Tennis-Consumer: alle67 unveränderten ursprünglichen Gegenproben und98 eigene
  Tests bestanden; zusätzlich46 unabhängige Randfälle. Kein erneutes Fitten bei
  Kartenanzeige, keine Umdeutung kaputter Metadaten in normale Altprognosen.
- Basketball/Hockey: Root242 bestandene Original-/ID-Prüfungen, darunter alle
  acht ursprünglichen Fehlerfälle. Empfangs-Captures separat265+46 qualifiziert
  geprüft. Ganze Statushistorie vorhanden, aber noch kein vollständiger aktueller
  Alias-/Input-/Worker-Anschluss. Fehlende native Belege bleiben fehlend.
- Echte Linux-Prüfung:785 bestanden, keine Skips,55,61s auf privater Kopie als
  unprivilegierter Nutzer. Der alte negative Lauf bleibt erhalten. Reale
  Root/App-Dateirechte und installierte BridgeA→KontextB sind noch nicht belegt.
- Weiter aktiv: reiner Basketball/Hockey-ID-/Inputresolver (P4b2), exakte
  Fußball-Originalaufnahme (P5a), lokale Vorbereitung der getrennten Linux-
  Rechteprüfung. Keine dieser Teilaufgaben als Gesamtfreigabe melden.
- VPS App/Caddy/Healthcheck zuletzt gesund. Der bekannte alte Tennis-Refresh-
  HTTPError bleibt sichtbar, nicht kosmetisch zurückgesetzt. Timer rechnen;
  sie deployen keinen Code. NEXT=- während eines laufenden Jobs ist allein
  kein Nachweis eines Timerfehlers.

Alle ursprünglichen und neuen unabhängigen Reviewberichte bytegleich im SDD
gesichert. Noch offen: tatsächliche Worker-/Consumeranbindung weiterer Sportarten,
Quellenlücken und empirische Wirkung, neue Gesamtsuite/Browser, Main-Push und
vertrauenswürdiges VPS-Update. Cricket ausgenommen; keine Altprognosen, Tickets,
Geldbewegungen oder fremde Dateien verändern. Stagehelper SHA1441158 unverändert.

## Aktueller Fortsetzungsstand vom 9. September 2026 — 21:01 UTC

Root-Code `3dccf6b` integriert die unabhängig akzeptierten Domain-, Reader-,
Tennis-Producer-/Publikationsuhr-, D4-Tennis- und Updater-Parserpakete. Diese
Codeabnahme ist **noch kein Main-/VPS-Release**. Main/VPS zuletzt15:57UTC auf
`2ba3931`; der belegte Produktions-Tennis-Refreshfehler ist nicht zurückgesetzt.

- Domain-Typfix `53c9a88`: Root88/88, alle elf ursprünglichen echten Fehler
  behoben. Reader-Integration abgeschlossen:233 bestanden/1 Windows-Skip;
  die unten noch aktive Session12818 ist damit historisch überholt.
- Tennis-Publikationsuhr `b566da3` akzeptiert: Root184/184; owning Vollsuite
  5274 bestanden/19 erwartete Skips/97 Untertests. Tatsächlicher gespeicherter
  Originalzeitpunkt darf nicht nach der Shadow-Verbuchung liegen.
- D4-Tennis `5d5bab6` unabhängig PASS:375/3,57 qualifizierte Gegenproben,
  2 echte Mischstore-Prüfungen mit ungeöffneten D2-Labels. Das belegt die
  mechanische Original-/Quellenbindung, keine neue empirische Wirkung.
- Trusted-Updater `7ba4c97`: ursprünglicher Unicode-P2 nachgeprüft; Root367
  bestanden, nur alter Sourcehash-Pin explizit abgewählt. Owning Vollsuite
  4789/18/97. Echte Linux-Rechte und installierte BridgeA→KontextB noch offen.
- Gemeinsamer Tennis-Consumer ist im separaten `kontext-tennis-consumer-20260909`
  umgesetzt, noch nicht freigegeben/übernommen:242 Tests/26 Untertests sowie
  400 Integrationsprüfungen/1 Windows-Skip. Beide Ansichten beziehen denselben
  ungerundeten Winner und dieselbe Ref; Satzsimulation bleibt separat.
- Basketball/Hockey: P4a same-call Originalbuilder und P4b1 echte bestehende
  JSON-Antwort-Captures laufen getrennt. Noch kein vollständiger gemeinsamer
  Worker-/Normal-UI-Anschluss; unbekannte native Saison-/Rosterbelege bleiben
  unbekannt. Cricket ist ausdrücklich ausgenommen.

Nächste Schritte: Consumerfreeze/Independentreview, P4a/P4b-Anschluss, noch offene
Fußball-/E-Sport-Original-/Consumerpfade, Linux-Bridge-/Restorematrix, neue finale
Gesamtsuite/Browserprüfung und erst dann exakter Main-Push/VPS-Update. Kein
Timercodepull; keine Wett-/Kontohistorie umschreiben; gepinnten Stagehelper und
alle fremden WIP-/Outputdateien unverändert erhalten. Neue und ursprüngliche
Reviewberichte sind im SDD-Ledger bytegleich aufbewahrt.

## Aktueller Fortsetzungsstand vom 9. September 2026 — 16:24 UTC

Root-Code `ef1aea8`; nachfolgende Punkte ersetzen die älteren Lauf-/Offenangaben.
Main/GitHub/VPS zuletzt15:57UTC exakt `2ba3931`, kein neues Kontext-Deployment.
Der belegte Tennis-Refreshfehler bleibt offen bis zur tatsächlichen Auslieferung.

- Vollsuite auf separat eingefrorenem `d2809fc` abgeschlossen: **5.202 bestanden,
  19 Skips, 97 Untertests, 1.196,76 Sekunden**. XML SHA256
  `c368aa7c7b4e8eb6ab867f485cb7696910bec2b6d6d247d95f9c18ec24a151f0`.
  Enthält nicht die späteren Domain-/Reader-/Producer-/Updaterpakete.
- Readerfix `4011392` unabhängig von Root akzeptiert und in `ef1aea8` integriert:
  beide Originalfehler + unveränderte echte WAL-Kontrollen +10 neue Gegenchecks,
  74 bestanden/1 Windows-Skip. Originalnegative Berichte bleiben unverändert.
  Zusätzliche Root-Integrationssuite noch aktiv (Session12818).
- Basketball/Hockey same-call Anschluss in `ccefe85`: ungerundetes Original aus
  genau der Zielberechnung, optional durch den echten Risk-Adapter weitergegeben.
  727 bestanden/1 Windows-Skip; Cricket Vorher/Nachher inklusive Risk-IDs bytegleich.
  Noch kein tatsächlicher B3-Worker-/Normal-UI-Anschluss dieser Sportarten.
- Echter Tennis-Producer `32ac1d8` in eigenem WT eingefroren: 758 Fokusprüfungen,
  154 neue Fälle einschließlich48 Altcode-Paritäten. Eigene Vollsuite läuft;
  Root-Review sowie gemeinsamer Consumer und D4-Originanschluss noch erforderlich.
- Unabhängiger Review der Domain-Refs `9de9b52` jetzt aktiv. Danach Review des
  Basketball/Hockey-Anschlusses. Trusted-Updaterhook weiterhin in Regression.

Alle bestehenden Freigaben gelten weiter. Keine neue empirische Wirkung aktiviert,
kein Cricket-/Ticket-/Kontoeingriff; geschützten Helper und fremde Dateien erhalten.

## Aktueller Fortsetzungsstand vom 9. September 2026 — 15:59 UTC

- Root-Code `9de9b52`, letzter verifizierter GitHub-Featurestand `7201302`.
  Main/GitHub main und **frisch lesend geprüfter VPS** exakt `2ba3931`.
  Noch kein neues Kontext-Release. Timer führen weiterhin keinen Codepull aus.
- App/Caddy aktiv, Healthcheck `ok`, sieben Timer geplant, VPS-Code sauber.
  **Nicht alle Dienste sind fehlerfrei:** Tennisjob 07:17–07:18 CEST scheiterte
  im gemeinsamen Modellrefresh an HTTPError; anschließender Scan rc0/22 neue
  Prognosen nutzte den alten State. Kein kosmetisches Zurücksetzen des Fehlers.
- Originalevent-Bindung `da0ae34` unabhängig PASS: 831 bestandene Prüfungen,
  darunter alle50 unveränderten ursprünglichen Gegenproben. Berichte erhalten.
- D4-Semantik samt kausalem Referenzfix unabhängig nachgeprüft (13/13) und in
  `d2809fc` übernommen. Neue Gesamtsuite läuft separat unveränderlich auf diesem
  Stand in `kontext-integrated-qa-20260909`; nicht als abgeschlossen melden.
- Der D3-Leser `97cb672` ist **noch nicht freigegeben**: zwei unabhängige P2-
  Befunde (generierte Zusatzspalten, SHM-Hardlink) werden in `kontext-reader-fix-
  20260909` behoben. Normale SQLite-WAL-Synchronisationsdateien sind erlaubt;
  uncheckpointete echte Prognosen dürfen nicht zugunsten einer alten Kopie fehlen.
- Optionale unveränderliche Ref-Verträge für ModelSignal/RisikoBet und normale
  JSON-Leser sind in `9de9b52` eingefroren: 298 Tests/26 Untertests, unabhängiges
  Review noch ausstehend. Alte IDs/JSON ohne Ref und Storeeindeutigkeit unverändert.
- Echter ESPN-Tennis-Winner-Producer (gleicher Modellaufruf, native IDs, tatsäch-
  liches A1-Modell, Capture vor B1-Lesen, atomare Shadow-Ref) in eigener WT aktiv.
  Neuer Originalbeleg nach Entscheidung ist kein rückdatiertes Trainingsmodell.
- Trusted-Updaterhook in eigener WT aktiv; echte Linux-/WAL-/Restore-/Zwei-Commit-
  Abnahme steht aus. VPS hat derzeit keine Kontext-DB/keinen Runtimepfadoverride,
  vorhandene venv Python3.12.3/SQLite3.45.1 unterstützt deserialize; Roottools
  entsprechen den Pins. Vollständiges Backup/Schlüssel bleiben app-unlesbar.
- Cricket ausgenommen, keine erfundenen Verletzungs-/Müdigkeitskoeffizienten,
  keine reale >=200-Event-Freigabe. Gemeinsame tatsächliche Kartenanbindung aller
  fünf Sportarten, fehlende Original-/Quellenpfade, Browser und Release offen.

Ausführlicher aktueller Ledger: `.superpowers/sdd/2026-09-07-kontextmodell-
umsetzung/progress.md`. Vorhandene Freigaben nicht erneut erfragen. Alle fremden
WIP-/Outputdateien und den gepinnten Helper erhalten.

## Aktueller Fortsetzungsstand vom 9. September 2026 — 15:28 UTC

Root-Quellstand `da0ae34613fb030280aac3e8abc504d18ebca47e`, letzter verifizierter
GitHub-Featurestand `caa230f73705f5bf8aadcc25394cd136963e858d`. Main/GitHub main
weiter `2ba3931dd8cb35f31d2475ae5797d75b44be268e`; VPS früher in derselben
Fortsetzung dort geprüft, nicht durch diesen Vermerk neu abgefragt. Kein neues
Kontext-Release. Die Timer rechnen und deployen keinen Code. Alle bestehenden
Freigaben gelten; Cricket bleibt ausgenommen.

- C3-Eishockey samt Transport und C4-E-Sport samt nativer Korrekturhistorie sind
  unabhängig geprüft und übernommen. C4-Integration: 1.034 bestanden/1 Windows-
  Plattform-Skip. Das belegt die Software, keine reale Müdigkeitswirkung.
- Tennis-v3 bewahrt echte Status- und Belastungsbelege vorhandener Abrufe;
  unabhängig 978 bestanden, Root-Integration 523 bestanden. Übernommen in
  `d4312dd`. Native Spieler-/Tourmodellzuordnung und tatsächlicher Workeranschluss
  sind noch offen; keine Zeiten/IDs aus Namen oder Spielplan erfunden.
- Fußball-FT-Belege werden nur für bereits gespeicherte native Basisereignisse
  aus bestehenden Abrufen erhalten. Ein unabhängiger Befund zum vollständigen
  Belegbestand wurde korrigiert und erneut mit 510 Prüfungen bestätigt; übernommen
  in `ffb4005`. Ursprüngliche negative und neue Reviewberichte sind gesichert.
- Die neue D3-Prüfung bindet Originalteams und Spieltermin auch in Rückfall- und
  reinen Kartenlesepfaden für Basketball/Eishockey/E-Sport. 18 neue Fälle:
  14 ROT/4 GRÜN vor dem Fix, danach 134 Fokustests und alle 50 ursprünglichen
  unabhängigen Gegenproben grün. `da0ae34` wartet noch auf unabhängiges Nachreview.
- D4-Semantik separat `b56da33`: Vollsuite 4.533/18 Plattform-Skips/97 Untertests.
  Root-Gegenprüfung fand 2 Fehler bei fehlenden/zukünftigen expliziten Belegrefs
  in gültigen verwaisten Cases. Der enge Fix läuft; noch nicht übernommen.
- Der rein lesende D4-Updater-Preflight liegt vor. Noch kein Produktionshook.
  Vollständiges Backup/Schlüssel bleiben app-unlesbar, gepinnter Stagehelper
  bleibt unverändert. Ein neuer Hook braucht echte Snapshot-/Restoreprüfung und
  den bestehenden zweistufigen Trusted-Updater-Übergang.
- Reale D3-Worker-/Kartenanbindung bleibt offen. Vorhandene Basketball-/Hockey-
  Historienmodelle laufen im RisikoBet-Pfad, noch nicht im normalen Wettfinder;
  deren fehlende Spieler-Kontextquellen sind davon zu unterscheiden. Frische
  Gesamtregression, Linux-/Browser-/Releasebelege und echte empirische Abnahme
  bleiben ebenfalls offen. Frühere 4.449 Root-Tests gelten nicht für diese Merges.

Maßgeblich ist der oberste Ledgerabschnitt in der freigegebenen Arbeitskopie
`.worktrees/kontextmodell-20260907`. Alte Prognosen, Tickets, Konten, ungetrackte
Dateien und den gepinnten Helper erhalten. Kein erneutes Anfordern der bereits
erteilten Spezifikations-/Worktree-/Unteragentenfreigabe.

## Aktueller Fortsetzungsstand vom 9. September 2026 — integrierte Gegenprüfungen

Verbindlich ist der oberste aktuelle Abschnitt in
`.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/progress.md` der Arbeitskopie
`.worktrees/kontextmodell-20260907`. Nicht erneut um Spezifikation, Worktrees
oder Variante 1 bitten. Cricket bleibt ausgenommen.

- Root-Quellstand `c871ba1`; GitHub-Feature zuletzt `908667e` verifiziert.
  Main/GitHub main `2ba3931`; VPS früher in dieser Fortsetzung ebenfalls exakt
  dort verifiziert. Noch kein neues Kontext-Release. Timer rechnen, nicht pullen.
- Vollsuite vor den jüngsten Integrationen: 4.449 bestanden, 18 erwartete
  Plattform-Skips, 97 Untertests. Die neue Gesamtsuite steht noch aus.
- Exakter D3-Transportfix, Fußball-NS-Quellkorrektur und C3-Eishockeymechanik
  sind unabhängig geprüft und übernommen. Sechs Original-/Nachreviewberichte
  wurden gezielt gesichert. Die anschließende Eishockey-Transportanbindung
  besteht 550 Fokustests/1 Plattform-Skip und wartet auf unabhängiges Review.
- E-Sport bleibt separat: Ein weiterer Grenzfall bei unvollständiger nativer
  Saisonkorrektur wurde reproduziert; Fix besteht 1.012 gezielte Prüfungen,
  Vollsuite und unabhängige Nachprüfung stehen noch aus. Nicht als fertig melden.
- Tennis bewahrt jetzt in eigener Arbeitskopie echte Status-/Belastungsbelege
  aus vorhandenen Abrufen; noch nicht übernommen. D4 prüft separat tatsächliche
  gespeicherte Evaluator-Semantik, ohne ungeöffnete finale Ergebnisdaten zu lesen.
- Echte gemeinsame Worker-/Kartenanbindung, Produktions-Backupintegration,
  Browser-/Releaseprüfung und ausreichende reale empirische Daten bleiben offen.
  Eine funktionierende Prüfsoftware beweist keine Verletzungs-/Müdigkeitswirkung.

Alte Prognosen, Tickets und Konten sowie bekannte ungetrackte Dateien und den
gepinnten Staging-Helper unverändert erhalten. Nur gezielt committen/pushen;
Code, Daten, empirische Freigabe und VPS-Aktivierung getrennt nachweisen.

## Neuester Fortsetzungsstand vom 9. September 2026 — D2 und Quellenbelege

Der oberste Abschnitt von `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/progress.md`
in `.worktrees/kontextmodell-20260907` ist verbindlich. Freigegebene Spezifikation,
isolierte Worktrees und Variante1 mit unabhängigen Unteragenten-Reviews gelten
weiter; nicht erneut nachfragen. Cricket bleibt ausgenommen.

- Root-Quellstand `ecf9200`; GitHub-Feature zuletzt `4d33224` verifiziert. Main/
  GitHub main `2ba3931`, VPS zuletzt in dieser Fortsetzung ebenfalls `2ba3931`.
  Noch kein Kontext-Release. Die Timer führen Berechnungen aus, keinen Pull.
- Tatsächlicher D2-Datensatz/Evaluator/Approval ist unabhängig geprüft und
  übernommen (`187dfa0`, Originalreview `526d988`); Root70 Tests grün471,59s.
  Dies belegt Prüfsoftware, keine empirisch erfolgreiche Kontextwirkung.
- D3-Kartentext ist geprüft. Der Transport-Bytefix ist separat unabhängig
  freigegeben `1a9fffa`, noch zu integrieren. Die vorhandene Vollsuite läuft
  unverändert weiter; neue Resultate nicht mit alten Testzahlen verwechseln.
- Neue Fußballbelege werden ausschließlich aus bereits vorhandenen Abrufen
  in automatischer Suche, Kontextrefresh und manueller Suche gespeichert.
  Paket `ecf9200`:397 Fokustests/32 Untertests grün, unabhängiges Review läuft.
  Keine neue Abfrage, keine erfundene Veröffentlichung, keine Quoten-Sperre.
- C3 Eishockey `6b2473b` im Review; C4 E-Sport-Korrektur `79763a1` im Nachreview.
  Die ursprünglichen Gegenproben und alten Quellbytes bleiben erhalten.
- Tennis-Capture ist in eigener sauberer Arbeitskopie vorbereitet, noch nicht
  implementiert. Statuskorrekturen müssen erhalten bleiben, nicht nur Finals.
  Gemeinsame echte Worker-/UI-Anbindung, D4-Semantik/Backup, Browser, Release
  und tatsächliche Quellen-/200-Event-Abnahme bleiben ausdrücklich offen.

Keine alten Prognosen, Tickets oder Geldbewegungen überschreiben. Bekannte
ungetrackte Audit-/Outputdateien und gepinnten Staging-Helper erhalten. Nur
gezielte Commits/Pushes; Push, VPS-Code, echte Daten und Modellwirkung trennen.

## Historischer Fortsetzungsstand vom 9. September 2026

Maßgeblich ist der oberste aktuelle Abschnitt in
`.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/progress.md` der Arbeitskopie
`.worktrees/kontextmodell-20260907`. Die ursprüngliche Spezifikation, Variante 1
mit Unteragenten und isolierte Worktrees sind freigegeben; nicht erneut fragen.
Cricket bleibt ausgenommen. Die älteren folgenden Statusabsätze sind Historie.

- Main/GitHub/VPS zuletzt in dieser Fortsetzung exakt auf `2ba3931` verifiziert,
  einschließlich des gesonderten Tennis-Terminabrechnungsfixes. Die früheren
  Widerspruchs-/Kartenerklärungsfixes sind darin enthalten. Kein neues Kontext-
  Deployment; funktionierende Timer sind keine automatische Codeauslieferung.
- Featurezweig: geprüfte C2-Basketballmechanik `23aa21c` übernommen, Original-
  und Nachreviews vollständig erhalten; C1-Endpunkt-Erholungskorrektur mit
  unabhängigen 283 Prüfungen in `a1f4969` committed. D1-Quellenreplay/Case/Fit
  `f4649c3` und D2-Verteilungsscorer/Vergleich sind ebenfalls übernommen.
- Letzter stabiler vollständiger Root-Test: 4.323 bestanden, 18 erwartete
  Plattform-Skips, 97 Untertests. Danach nur weiterer noch ungeprüfter D3-
  Übergabecode verfeinert; dessen letzter Fokus 265 bestanden. Kein Testlauf
  ist eine Freigabe realer Verletzungs-/Müdigkeitseffekte.
- Erhaltene aktive Arbeiten: C3 Eishockey in `kontext-c3-hockey-20260909`,
  D2 tatsächlicher Datensatz/Evaluator/Approval in `kontext-d2-evaluator-20260909`.
  C4 E-Sport `26e8910` ist separat eingefroren (4.154/18/97), noch unabhängig
  zu prüfen. Root-D3 `context_copy.py`/`context_transport.py` samt Tests sind
  noch WIP; Copy ist im Review. Keine dieser Arbeiten löschen/überschreiben.
- Weiter offen: tatsächliche Quellen- und gemeinsame Worker-Anbindung für
  fünf Sportarten, D1/D2 fehlende Familien/echte kausale Daten, verständliche
  gemeinsame Anzeige samt Browserprüfung, D4 semantische Restore-/Deploy-
  Verbindung und D5 Release. Neue Datenmodelle bleiben ohne echte Abnahme
  intern; vorhandene gültige Basisprognosen bleiben sichtbar.

Commit/push, main, VPS, echte Daten und empirische Wirkung getrennt nachweisen.
Bekannte ungetrackte Audit-/Output-Dateien und den gepinnten Deployment-Helper
unverändert erhalten. Keine historischen Prognosen, Tickets oder Geldbewegungen
umschreiben. Keine neuen kostenpflichtigen Quellen ohne eigene Zustimmung.

## Historischer früherer Umsetzungsstand vom 9. September 2026

Diese Zusammenfassung ersetzt die älteren Zwischenstände darunter. Fortsetzung
im Featurebranch `codex/kontextmodell-20260907`, Arbeitskopie
`.worktrees/kontextmodell-20260907`; Spezifikation, Unteragenten und isolierte
Arbeitskopien sind bereits ausdrücklich freigegeben.

- **Live:** Main/GitHub/VPS zuletzt identisch auf
  `a0fc89cdef1c3a7bebfb237e8aaed1ecb0ee1028`. Dieser Stand enthält zusätzlich
  den zentralen Widerspruchsschutz aus `acc5d72` für automatische und manuelle
  Fußball-Auswahl vor Abschnitts-/Seitentrennung. Der neue Merge übernimmt
  dessen exakte geprüfte Source-/Testblobs in den Kontextzweig; nur diese
  Übergabe hatte einen dokumentarischen Konflikt. Kontextcode bleibt separat
  und nicht produktiv aktiviert. Serverstatus wird bei Fortsetzung neu gelesen.
- **Geprüfte Kontext-Integration:** `d7294de65fcb71bbf011378a808316405929d185`
  vereint A1–A4, den realen ATP-Datenfix `2436dd4`, B1 `22164f`, B2 `a71d095`
  und den Live-Kartenstand. Eigener stabiler Abschlusslauf: **2.324 bestanden,
  15 erwartete Windows-Skips, 97 Untertests**, 88,56 Sekunden. B2 unabhängig
  ohne Findings geprüft (262 Tests plus separate mathematische Gegenproben).
  Nach dem konfliktfreien Merge stimmen alle 361 getrackten Dateien außerhalb
  von SDD/Übergabe exakt mit dem geprüften B2-Stand überein. Das frühere
  B1/UI-Integrationsreview war ebenfalls ohne Findings. Kein Kontext-Deploy.
- **Echte Daten-/Restoreprüfung:** Getrennte ATP/WTA-Modelle aus den vorhandenen
  historischen Seeds auf Windows und isoliert auf dem VPS erfolgreich gebaut.
  Linux-Backup/Restore mit identischen Registryzeilen, Modellen und kompletten
  Prognosen bestanden. Keine lokale DB hochgeladen, keine Produktions-DB
  geöffnet oder umgeschrieben. Daten reichen nur bis 26./27. Juli; aktueller
  Abruf und empirische Modellgüte sind damit ausdrücklich nicht bewiesen.
- **B2 abgeschlossen, B3 als Nächstes:** Die regularisierte Schätzung für
  Raten, binäre Chancen und reelle Änderungen lernt ihre Koeffizienten wirklich
  aus Daten; keine festen Verletzungs-/Müdigkeitsabschläge. Quellcommit
  `a71d0955a74884a152c90fddd9bfae2e20602b34`, Reviewpaket `b1bafce79731c516b640b6f07e6ea9f7dfb50892`.
  Nächster freigegebener Task ist **7 / B3**, gemeinsame revisionsfeste
  Vergleichssnapshots und Erhalt der Basis bei fehlendem/ungültigem Kontext.
  B3 wurde noch nicht gestartet. B3–D5, echte Sportanbindung und empirische
  Abnahme bleiben offen. Verletzungen und Müdigkeit verändern die produktive
  Prognose weiterhin nicht numerisch; nichts als fertig/live ausgeben.
- **Betrieb:** App/Caddy/Healthchecks funktionieren. Die sieben Timer rechnen,
  deployen aber keinen Code. Die bekannten Tennis-Rebuild- und
  Ergebnismehrdeutigkeitsfehler bleiben separat offen. Keine Ergebnisse raten,
  umschreiben oder Dienste nur für einen grünen Status zurücksetzen.

Verbindliches Aufgabenbuch: `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/progress.md`.
Echte Restorebelege: dort `tour-restore-proof-20260908.md`. Alle Quell-, Review-,
Git-/Test-/Servernachweise getrennt weiterführen. Bekannte ungetrackte
Audit-/Browser-/Output-Dateien und den unveränderten Helper-Pin erhalten.

Übergabelücke behoben: Mit `b4f7cdc` sind auch die bisher nur lokal ignorierten
20 Aufgabenbriefe, Quellzuordnung, Validierungsentscheidungen und bereinigten
Quellen-/Prüfnachweise versioniert. Alle 20 Aufgaben-Zuordnungen und die fünf
unveränderten ursprünglichen Plan-Git-Blobs wurden erneut kontrolliert.

## Gesicherter Main-Auswahlfix vom 8. September 2026
**Aktuelle Fortsetzung 8. September 2026 – widersprüchliche Auswahlen:** Der Screenshot mit gleichzeitigem Porto-Heim- und Auswärtssieg war eine echte Lücke der nutzerseitigen Auswahl. Der unabhängig freigegebene funktionale Fix `acc5d7200630c17ae23354226ef6857bbedae587` ist auf Main/GitHub/VPS identisch deployed. Ein zentraler Schutz prüft die gesamte angezeigte Auswahlmenge desselben Spiels vor Top-/Zusatzaufteilung, Seitenwechsel, manuellem Limit und Preisaufteilung. Keine Quoten- oder Marktverbote; alle 90 Fußballmärkte bleiben einzeln möglich, Rohmodelle und Preise unverändert. Root: 1.991 Tests bestanden, 11 erwartete Windows-Skips, 97 Untertests; unabhängige Gegenprüfung ohne Findings, einschließlich 8.100 Marktpaare, 400 vollständiger Pools und des Porto-Falls in beiden Auswahlpfaden. Die acht Source-/Testhashes stimmen auf dem VPS exakt mit dem Review überein. Zwei frische Backups mit je 87 Datenbanken verifiziert; App/Caddy und beide Healthchecks funktionieren, sieben Timer aktiv und geplant. Browserprüfung mit realem Renderer und klar markierter Porto-Reproduktion bei 1440/390/320 Pixeln sowie echte Produktionsseite getrennt geprüft. Produktions-Tennis/Wettfinder-Jobfehler bleiben ausdrücklich offen. Nachfolgende Dokumentationscommits ändern den geprüften funktionalen Stand nicht; bei jeder Fortsetzung den vollständigen aktuellen Main/GitHub/VPS-Hash neu prüfen. Maßgeblich: `docs/audits/2026-09-08-widerspruchsfreie-auswahl.md` und `docs/audits/2026-09-08-widerspruchsfreie-auswahl-review.md`. Die Freigabe umfasst nicht RisikoBet, Live, 15K oder den separaten manuellen Tennis-Preischeck.

**Aktueller separater Kontextstand:** `codex/kontextmodell-20260907` ist lokal und remote bei `0328fd70b893223822365621ef382693be51efee` gesichert. A1–A4 als Software geprüft; nach den ATP-Admission-Korrekturen reale statische ATP/WTA-Builds mit Juli-Startdaten unter Windows/Linux und Linux-Restore nachgewiesen. B1/B2 sind integriert; Kontextregression 2.324 bestanden / 15 Windows-Skips / 97 Untertests. B3 ist die nächste freigegebene Aufgabe, noch nicht begonnen. Aktuelle Quellenfrische, B3–D5, gelernte Verletzungs-/Müdigkeitswirkung, empirische Freigabe und Aktivierung sind weiter offen; kein Kontextcode deployed. Vor B3 den aktuellen Main-Fix kontrolliert in die Kontext-Arbeitskopie integrieren und erneut prüfen. Die dortige `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/progress.md` und `task-7-brief.md` sind maßgeblich; keine erneute Spezifikations-, Unteragenten- oder Worktreefreigabe erfragen. Cricket bleibt ausgenommen. Die nachfolgenden Absätze mit früheren Hashes und noch ausstehenden B1/B2 sind historische Momentaufnahmen, kein aktueller Auftrag.

Die zuvor verlangte Übernahme des Main-Fixes wird in dieser Fortsetzung vor B3
durchgeführt. Die folgenden älteren Modell-, Test- und Deploymentangaben bleiben
als datierte Nachweise erhalten, ersetzen aber nicht den aktuellen Aufgabenstand.

## Historische Nachweise bis zum früheren Karten-Release

**Fortsetzung 8. September 2026 – aktueller Nachweis 19:14 Uhr Zürich:** Die Nutzerfreigaben für Spezifikation, Unteragenten-Ausführung und isolierte Arbeitskopie liegen vor; nicht erneut abfragen. Der unabhängig geprüfte Karten-Quellstand `f82d7aeea2e42d81affa2c4389cb377f2293af5c` wurde mit Release `ce7b98ccf365a5db4303ed04291058acdbe6067b` auf Main/GitHub/VPS identisch bereitgestellt. Zwei Backups mit jeweils 87 Datenbanken verifiziert. Der reguläre 19:07-Lauf ergänzt jetzt auch die echte Porto-Karte: Torprognose 1,53/1,13, unverändert 46,4 % Heimsieg, direkt sichtbare Begründung und 53,6 % Gegenrisiko, ohne alte Aufklapp-Checkliste. Tatsächliche Produktionsdarstellung bei 1440/390/320 Pixeln geprüft, 0 Console-Fehler; neun bestehende Warnungen. Details: `docs/audits/2026-09-08-kartenanalyse.md` und `.superpowers/sdd/2026-09-08-kartenanalyse/independent-review.md` (1.795 Tests, 11 Skips, 97 Untertests; unabhängiger Fokus 313/26). App/Caddy und Healthchecks funktionieren. Die Timer deployen nicht. Tennis-Rebuild und Wettfinder-Ergebnisverarbeitung haben weiter eigene Fehler; der UI-Release behebt diese nicht. Nachfolgende Dokumentationscommits ändern diesen fachlichen Quellstand nicht; den aktuellen vollständigen Git/VPS-Hash bei jeder Fortsetzung neu prüfen.

**Separater Kontextausbau, weiterhin offen:** In `.worktrees/kontextmodell-20260907` sind A1–A4 als Software geprüft; A4-Fix `c8935c2` und Übergabe `6031e31` sind auf dem Featurebranch gesichert. Der reale Offline-Build deckte danach widersprüchliche ATP-Aufschlagstatistiken auf; die eng begrenzte Admission-Korrektur ist in Arbeit, echter Zwei-Tour-Build/Restore und Betriebsfreigabe stehen aus. B1 ist separat in `.worktrees/kontext-b1-20260908` mit `9a4e04f` implementiert (2.057 Tests, 15 Skips, 97 Untertests), aber noch im unabhängigen Review und nicht integriert/deployed. Maßgeblich sind `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/progress.md` und die aufgabenweisen Berichte der Kontext-Arbeitskopie. B2–D5, numerische Verletzungs-/Müdigkeitswirkung und empirische Freigabe sind nicht erledigt. Der Karten-Release enthält diesen unfertigen Ausbau nicht. Cricket bleibt ausgenommen. Die älteren folgenden Angaben „Wahl steht aus/alle Aufgaben offen“ sind historischer Planungsstand.

**Fortsetzung 7. September 2026:** Zuerst `docs/audits/2026-09-05-umsetzung.md` und `docs/audits/2026-09-07-release.md` lesen. Die nachfolgenden September-2-Hashes und Testzahlen sind historische Nachweise. Lokal funktioniert `.codex_test_venv/quality/Scripts/python.exe`; die alte `.venv` wurde erhalten. GitHub und VPS separat prüfen; die sieben Timer rechnen Daten und deployen keinen Code. Offene empirische Modell-/Kontextgüte nicht mit bestandenen Softwaretests gleichsetzen.

**Trainingsdaten:** `tennis/data` enthält versionierte Startdaten und darf durch automatische Downloads nicht verändert werden. Der veränderliche Trainingscache liegt unter `runtime_state/tennis/training_data` beziehungsweise dem konfigurierten Runtime-Root; der Modellstand unter `runtime_state/tennis/model_state.pkl`. Ein aktualisierter Rohdaten-Cache beweist keinen aktualisierten Gesamtmodellstand. Am 7. September verhinderte der WTA-Abruffehler die Veröffentlichung des neuen ATP/WTA-Modells; der alte Juli-Modellstand blieb erhalten.

**Fortsetzung 8. September 2026 – Kontextmodell ohne Cricket:** Spezifikation, Variante 1 (Unteragenten mit Aufgabenreview) und isolierte Arbeitskopie sind ausdrücklich freigegeben. Der 20-Aufgaben-Plan liegt unter `docs/superpowers/plans/2026-09-07-kontextmodell-umsetzung.md`. Verbindlicher Ausführungsstand: `.worktrees/kontextmodell-20260907/.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/progress.md` im Hauptcheckout beziehungsweise `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/progress.md` innerhalb der Arbeitskopie. A1–A4 sind als Software implementiert und unabhängig geprüft; A4 samt drei behobenen Reviewbefunden ist mit `c8935c22af0d4a5e5e03a575be8eb1b5d3f1dc40` auf dem Kontext-Featurebranch gepusht (voll 1.887 Tests/15 Skips; letzter unabhängiger Fokus 132/0). Ein echter Offline-Build mit den versionierten historischen Daten veröffentlichte WTA bis 26. Juli, ATP scheiterte jedoch am Integritätscheck „serve breaks cannot exceed return games“; Ursache wird untersucht, kein Schutz gelockert. B1 läuft getrennt in `.worktrees/kontext-b1-20260908`, danach Integration und unabhängiges Review. Fußballverletzungen, Tennisbelastung, reale Builds/Restore/Empirie und die weiteren B–D-Aufgaben sind nicht ausgeliefert. Keine produktive Aktivierung des Kontextmodells; Cricket bleibt ausgenommen.

**Zusatzauftrag Kartenanalyse – separat veröffentlicht:** Der unabhängig freigegebene Kartenstand `f82d7ae` plus Nachweise ist als `ce7b98ccf365a5db4303ed04291058acdbe6067b` auf Main/GitHub und exakt auf dem VPS (Kontrolle 16:37 UTC). Normaler root-eigener Updater, zwei verifizierte Backups mit je 87 Datenbanken, App/Caddy und sieben Timer aktiv/enabled, beide Healthchecks `ok`. Reale Seite: 23 Karten mit 23 direkt sichtbaren Kurzanalysen statt Aufklapp-Checkliste; 0 Console-Fehler, 9 schon vorher vorhandene Warnungen. Der reguläre Lauf 16:37 ergänzte 17 Fußballanalysen und beließ Modell-/Inputzeitpunkte unverändert; Porto war wegen letzter Kontextprüfung 16:07 noch nicht erneut fällig. Dessen echter Detailtext und frische responsive Screenshots bleiben nach dem nächsten normalen Refresh zu prüfen. Modell, Reihenfolge, Preisregeln, 15K und Cricket bleiben unverändert. Der bekannte Ergebnisverarbeitungsfehler und Tennis-Rebuildfehler bleiben separat offen; ein UI-Release schließt die 20 Kontextaufgaben nicht ab.

**Frischer Betriebsbefund 8. September, ca. 15:56 UTC:** VPS sauber auf `b3afc478a07fa0d67509e2bef0a9c05766bdb077`; App, Caddy und sieben Timer aktiv/geplant, interner Healthcheck `ok`. Tennis- und Wettfinder-Dienst melden jedoch Fehler. Tennis: gemeinsamer Rebuild scheitert nach erfolgreicher ATP-Verarbeitung mit HTTPError, alter Gesamtstand bleibt erhalten. Wettfinder: Fußball abgeschlossen; operativer Fehler aus RisikoBet-Ergebnisverarbeitung (`ambiguous_settlement_revisions` / `event_snapshot_ambiguous`), außerdem bestehende Cricket-Teildaten. Keine historischen Ergebnisse geraten oder umgeschrieben. Funktionsfähige Seite ist kein Nachweis gesunder Hintergrundberechnung. Nur lesende Prüfung, kein Neustart oder Deployment an diesem Kontrollpunkt.

## 1. Ziel dieser Übergabe

Diese Anleitung bringt einen neuen Windows-PC in einen sicheren,
reproduzierbaren BetBoy-Arbeitsstand. Der laufende Produktionsserver hängt
nicht vom alten PC ab und arbeitet während des Wechsels weiter.

### Aktueller verifizierter Stand vom 2. September 2026

Die funktionale Codebasis ist
`7d6f0e8060534b3f4d420b3c556321c7f7d022c9`. Sie enthält den
RisikoBet-Revisionsfix
`049d079a8f15031dccab0285000dd549db1f2388` sowie den auf dem VPS
erforderlichen Git-HTTP/1.1-Transportfix. Der unmittelbar nachfolgende
Dokumentationscommit darf den Funktionsstand nicht verändern, muss aber wie
jeder Release erneut auf GitHub und dem VPS exakt identisch ausgerollt werden.

| Prüfung | Ergebnis |
|---|---|
| Regression | 1.423 Tests bestanden, 8 erwartete Skips, 97 Subtests; 182 versionierte Python-Dateien kompiliert |
| GitHub und VPS | Funktionsbasis per vollständigem 40-hex-Hash identisch; normaler root-eigener Updater erfolgreich |
| App und Proxy | `betboy-app.service` und Caddy aktiv/enabled; interner und öffentlicher Healthcheck `ok` |
| Scheduler | exakt sieben BetBoy-Timer aktiv/enabled; Timer rechnen Daten, sie pullen oder deployen keinen Code |
| RisikoBet-Lauf | `PARTIAL` nur wegen fehlender Cricket-Quelle; 48 Snapshots und 62 Szenarien aus 47 Events: Fußball 30, Tennis 31, E-Sport 1; Basketball und Eishockey regulär geprüft ohne Szenario |
| Revision/Settlement | 39 alte mehrdeutige Tennis-Kandidatengruppen mit konkurrierenden Revisionen isoliert und nicht geraten; 27 eindeutige Ziele weitergeführt, 5 terminale Settlements verarbeitet |
| Gerenderte UI | alle sechs Filter geprüft; 1440/1080/768/430/390/360/320 Pixel ohne horizontalen Überlauf, keine Console-Fehler oder -Warnungen |
| Backup | Pre-Update- und reguläres SQLite-Backup jeweils mit 86 Datenbanken verifiziert |

#### Aktueller Checkout-Vertrag: Wettfinder V2 und RisikoBet V1

- RisikoBet ist ein eigener Hauptbereich mit sechs Sportfiltern und höchstens
  zwei Szenarien je Event. Sport, Event, Auswahl, Modellwahrscheinlichkeit,
  vorsichtige Prognose, Pro, Contra, Kontext-/Evidenzstatus und Preisstatus sind
  auf den Hauptkarten ohne Aufklappen sichtbar.
- Wettpreis und Modell bleiben vollständig getrennt. Eine fehlende, zu niedrige
  oder alte Quote ändert weder Wahrscheinlichkeit noch Reihenfolge noch
  Sichtbarkeit. Ein RisikoBet-Szenario ist kein Tipp und erzeugt keinen
  Einsatzvorschlag.
- Das Öffnen oder Filtern der Seite ruft keinen Anbieter auf. Der vorhandene
  halbstündliche Wettfinder-Job erzeugt auch den atomaren RisikoBet-Snapshot;
  es gibt weiterhin keinen zusätzlichen achten Timer.
- `runtime_state/riskobet.db` ist die revisionsfeste Historie,
  `runtime_state/riskobet_latest.json` das atomar veröffentlichte
  Consumer-Artefakt. Beide liegen nur auf dem VPS; die Datenbank ist Teil des
  verifizierten SQLite-Backups, der daraus wiederherstellbare JSON-Snapshot
  keine zweite kanonische Wahrheit.
- Alte gleichzeitige Tennis-Kandidatengruppen mit konkurrierenden Revisionen
  werden nicht willkürlich aufgelöst oder umgeschrieben. Nur die exakt
  klassifizierte kandidatenspezifische Mehrdeutigkeit wird isoliert; andere
  Integritätsfehler bleiben fail-closed.
- Alle sechs RisikoBet-Sportadapter sind implementiert. Auf Produktion fehlen
  `RAPIDAPI_KEY` und `CRICKET_API_KEY` beziehungsweise ein gültiger
  Cricket-Datenzugang. Deshalb zeigt Cricket ehrlich Teildaten/leer und keine
  erfundene Wahrscheinlichkeit. Das ist eine externe Betriebsvoraussetzung,
  keine Quoten-, Markt- oder Modellnamensperre.

Der folgende Abschnitt ist ein historischer Nachweis vom 24. August und darf
den aktuellen Vertrag nicht überschreiben.

Am 24. August 2026 wurde vor dem damals aktuellen v14/v12-Härtungspaket der
folgende
**zuletzt unabhängig verifizierte Produktionsstand** festgehalten:

| Prüfung | Ergebnis |
|---|---|
| Letzter verifizierter Funktionscommit vor v14/v12 | `08778fdc29a7275c21fc23671d4763290273c435` (`Restore team under 1.5 eligibility`) |
| GitHub und VPS | Funktionscommit per vollständigem Hash identisch; ein späterer reiner Dokumentationscommit muss erneut per vollständigem Hash verglichen werden |
| `betboy-app.service` | `active` |
| Streamlit-Health | lokal und öffentlich `200 / ok` |
| BetBoy-Timer | exakt 7 aktiv und enabled; echter automatischer Wettfinder-Lauf `success / 0` |
| Fehlgeschlagene systemd-Units | 0 |
| Deploy-Recovery | Root-geschütztes `betboy-preupdate-20260824T094247Z-069033f2891f.zip` |
| Letzter verifizierter v13-Lauf | Lauf um 11:44 CEST: 17 Fußballspiele gefunden, 14 modelliert, 16 sichtbare Modellprognosen, 10 exakt zuordenbare Fußball-Preisprüfungen, 0 operative Fehler und korrekt 0 strikte Tipps |
| Team-Unter-1,5 | Drei normale Modellprognosen mit `is_basic_forecast: false`; der Markt kann Featured, Strict und Ticket erreichen. Aktuelle Bestquoten 1,18, 1,29 und 1,30 lagen lediglich konkret unter den jeweiligen Value-Grenzen. |
| Gerenderte Live-UI | `Oţelul - Arges Pitesti: Team 2 unter 1,5` als zweite hervorgehobene Auswahl; Bestquote 1,29 transparent gegen Value-Grenze 1,65; Desktop und Mobil 390 x 844 ohne Überlauf, 0 Konsolenfehler |

Dieser Produktionsbeleg gehört zum früheren Automationsartefakt v13 mit
Auswahlrichtlinie v11. Die damals dokumentierte QA umfasst 886 Python-Tests,
38 Subtests und 3/3 JavaScript-Tests; Syntax- und Diff-Prüfungen waren grün.
Commit, Push, VPS-Deploy, echter Automatiklauf und Produktions-Browserprüfung
dieses historischen Funktionsstands waren abgeschlossen. Die beiden
historischen Nachweise bleiben zur Ursachenanalyse erhalten; maßgeblich ist
der aktuelle Vertrag weiter oben, der nach jedem neuen Deploy erneut über
vollständigen Hash, Worker, Artefakt und Browser verifiziert werden muss.

### Historischer Checkout-Vertrag: Wettfinder und 15K v16/v13

Letzter produktiv verifizierter Basisnachweis vor v16/v13: Commit
`e341db828121cba7ad5a9d4ed2f6304b146a3591` (`Refine normal Wettfinder
featured markets`), 922 Python-Tests plus 50 Subtests und 3/3
JavaScript-Tests grün; Python-Kompilierung und `git diff --check` ebenfalls
grün. VPS-Revision, App, interner/öffentlicher Healthcheck, sieben Timer und
null fehlgeschlagene Units wurden am 24. August unabhängig bestätigt.

- Der Wettfinder-/15K-Pfad verwendet weiterhin Automationsartefakt v16,
  Auswahl-/Katalogpolicy v13 und Modellcache-Schema v2. RisikoBet ergänzt
  diesen Pfad, ohne seinen Echtgeldvertrag zu lockern.
- Seine Kandidaten entstehen aus einem eigenen vollständigen berechenbaren
  Marktpool. Der 15K-Wahrscheinlichkeitskorridor und die 15K-Ticketvorfilter
  werden nicht wiederverwendet; auch höhere Modellwahrscheinlichkeiten bleiben
  im normalen Finder zulässig.
- Es gibt kein Markt-Namensgate. Die Nutzwertsortierung entscheidet nur über
  die hervorgehobenen Karten; alle weiteren ausgewählten Märkte bleiben
  gruppiert sichtbar.
- Ein gemischter Oder-Markt darf ausschließlich im normalen Fußball-Finder
  einen freien Hauptkartenplatz auffüllen. Er verdrängt keine drei
  höherwertigen Karten; der Default für 15K und andere Sportarten bleibt aus.
- Fehlende oder zu niedrige Quoten ändern und löschen keine Prognose. Sie
  erscheinen als Preishinweis. Ein normaler `PLAYABLE`-Tipp verlangt dagegen
  exakte Ereignis-/Auswahlbindung, mindestens drei stabile provider-native
  Buchmacher-IDs, einen Preiszeitstempel je Punkt sowie ein reales,
  ausführbares Angebot eines konkret genannten Buchmachers.
- Der normale Q25-Konsens wird nur aus aktuellen, providergebundenen
  Einzelangeboten neu berechnet. Ein alter oder unvollständig identifizierter
  Punkt entwertet drei andere gültige Anbieter nicht.
- Auch 15K verwendet Q25 nur als konservative Schwelle. Ticketrechnung und
  Persistenz erhalten die tatsächlich beobachtete ausführbare Anbieterquote;
  Abruf und alle beitragenden Punkte müssen den 35-/45-Minuten-Vertrag erfüllen.
- Teilfehler sind quellenspezifisch: Fällt eine Sportquelle aus, bleiben
  unabhängig gesunde Sportarten sichtbar; der Lauf bleibt betrieblich
  `degraded`.
- Die Nutzeroberfläche zeigt Ergebnis, Tippdaten, Preis- und Kontextstatus,
  aber keine internen Liga-, Spiel-, Kandidaten-, Gate-, Modell-, Markt- oder
  Cachezähler. Diese Diagnose bleibt Admin und Logs vorbehalten.
- Jede Echtgeldfreigabe einschließlich 15K verlangt eine gepaarte
  Brier-Verlustverbesserung mit Newey-West-/HAC-Standardfehler, positivem
  einseitigem unteren Konfidenzrand, bestandenem einseitigem p-Wert und
  Benjamini-Hochberg-FDR-Korrektur über alle 90 Marktspezifikationen.
- Gegnerstärke ist bereits numerisch über eigene Offensive, gegnerische
  Defensive, Heim-/Auswärtseffekt, Form, Ligaprior und gegebenenfalls xG
  enthalten. Verletzungen, Aufstellungen und Wetter sind aktuell nur
  zeitbezogene Live-Kontext-, Abdeckungs- und Vetoachsen; mangels eines
  zeitgestempelten historischen Prematch-Datensatzes werden keine numerischen
  Effekte erfunden. Die prospektive, versionsgebundene Kontextsammlung ist der
  nächste ehrliche Schritt.
- Die normale Consumer-Freigabe bleibt auf höchstens drei Tipps begrenzt. 15K
  liest dagegen das getrennte, schema-validierte Feld
  `challenge_release_candidates` mit höchstens 15 Fußballmärkten. Jede Zeile
  erfüllt denselben `RELEASED`-, HAC/FDR-, Kontext-, Overlay- und
  Ausführungsvertrag; die normale Top-3-Grenze beschneidet diesen Pool nicht.
- Ein erfolgreicher Lauf ohne Prognose wird als abgeschlossener Snapshot mit
  null Prognosen und null Tipps gespeichert und angezeigt, nicht als noch
  laufende Prüfung. Fehlende oder niedrige Quoten löschen weiterhin keine
  Modellprognose.

Der historische echte v14-Lauf um 17:37 CEST endete `success / 0` mit 18
sichtbaren Modellprognosen, null operativen Fehlern und null preislich
freigegebenen Tipps. Die mobile Produktions-UI 390 x 844 zeigte
Team-Unter-1,5 als erste und eine gemischte Chance als zweite Hauptkarte;
fehlende beziehungsweise alte
Quoten änderten keine Prognose. Die Schreibweise `verfügbar` war korrigiert,
und die Browserkonsole hatte null Fehler.

Nach jedem Commit gilt ausschließlich der frisch mit `git ls-remote origin
refs/heads/main` abgefragte vollständige GitHub-Hash. Der lokale Tracking-Ref
und besonders der `origin/main`-Ref in `/opt/betboy/app` können absichtlich
älter sein und sind kein Remote-Nachweis. Nach einem Deploy werden lokaler
`HEAD`, frisch abgefragtes GitHub `main` und der VPS-`HEAD` erneut als vollständige Hashes
verglichen; alte Chatangaben sind keine Betriebswahrheit.

## 2. Was wo lebt

| Bestandteil | Kanonischer Ort | Muss auf den neuen PC? |
|---|---|---|
| Quellcode und Dokumentation | GitHub `xantharu123-png/btts-pro-analyzer` | Ja, per Clone |
| Produktions-App | `/opt/betboy/app` auf VPS `141.95.41.27` | Nein |
| Python-Venv Produktion | `/opt/betboy/venv` | Nein |
| Runtime-Datenbanken | VPS unter `/opt/betboy/app` | Nein |
| Planmäßige SQLite-Backups | `/var/backups/betboy` | Nein, aber unabhängige Offsite-Kopie empfohlen |
| Deploy-Recovery | `/var/backups/betboy-update` | Nein; Root-only, vor Updates erzeugt |
| Runtime-Migrationssicherung | `/var/backups/betboy-migration-9171bdb` | Nein; Root-only, bis zum bestätigten DR-Entscheid erhalten |
| SSH-Key-Recovery | `/var/backups/betboy-ssh` | Nein; Root-only, enthält nur öffentliche `authorized_keys`-Bytes |
| Produktions-Secrets | `/etc/betboy/betboy.env` und ignorierte `config.ini` | Nein |
| 15K-Integritätsanker | `/etc/betboy/challenge-ledger-hmac.key` und `/etc/betboy/challenge-ledger-v2-migrated.json` | Nein; nur zusammen mit verifiziertem DB-Backup restaurieren |
| Lokale Entwicklungs-Secrets | alter PC, ignorierte Dateien | Nur sicher neu beziehen oder verschlüsselt übertragen |
| Privater SSH-Schlüssel | altes Benutzerprofil `.ssh` | Besser neuen Schlüssel erzeugen |
| 15K-/Tipps-Browser-ID | `localStorage` des alten Browserprofils | Nicht automatisch |
| Alte Venvs und Caches | alter PC | Nein |

Der neue PC ist eine Entwicklungs- und Administrationsstation. Er ist nicht
der Scheduler. Die sieben produktiven Jobs laufen per systemd auf dem VPS.

## 3. Vor dem Abschalten des alten PCs

### Pflichtprüfungen

Im aktuellen Repository:

```powershell
Set-Location C:\Projekt\BetBoy\betboy-app
git status --short --branch
$local = (git rev-parse HEAD).Trim()
$github = ((git ls-remote origin refs/heads/main) -split '\s+')[0]
if ($local -notmatch '^[0-9a-f]{40}$' -or $github -ne $local) {
    throw 'Lokaler HEAD und frisch abgefragtes GitHub main weichen ab.'
}
```

Der direkte `ls-remote`-Wert ist maßgeblich; ein lokaler oder serverseitiger
`origin/main`-Tracking-Ref kann veraltet sein. Erwartete lokale Arbeitsartefakte
können weiterhin ungetrackt erscheinen:

```text
.playwright-cli/
AUDIT_BERICHT_2026-08-09.md
output/
```

Die validierten Inhalte des Auditberichts sind in den kanonischen Dokumenten
übernommen. Browserzustand und `output/` sind lokale QA-Artefakte. Keine dieser
Dateien ist für den Betrieb nötig. Nicht löschen, nicht mit `git add -A`
aufnehmen und nur bei ausdrücklichem Wunsch separat archivieren.

### Zugangsdaten sichern

Die folgenden Dinge gehören in einen Passwortmanager oder direkt in das
jeweilige Providerkonto, niemals in diese Dokumentation:

- GitHub-Zugang;
- OVH-Zugang inklusive 2FA-Recovery;
- API-Football-Zugang;
- OpenWeather-, PandaScore-, Telegram- und gegebenenfalls Cricket-Schlüssel;
- weitere aktive Providerzugänge.

Historisch im Chat oder in Git veröffentlichte Schlüssel gelten bis zu ihrer
Rotation als kompromittiert. Nicht einfach dieselben Werte in eine neue
Datei kopieren und damit die Rotation als erledigt betrachten.

### 15K-Konto und „Meine Tipps“

BetBoy besitzt noch kein Login. Das Browserprofil speichert eine zufällige
128-Bit-Konto-ID unter `betboy.account.v1`. Ein neuer PC oder Browser erzeugt
eine neue ID und zeigt deshalb ein neues Konto, obwohl die alte Datenbank auf
dem VPS weiterhin vorhanden ist.

Vor dem Löschen des alten Browserprofils eine Entscheidung treffen:

1. **Neues Konto beginnen:** Auf dem neuen PC die App öffnen und den aktuellen
   Stand bei Bedarf über `Einstellungen -> 15K-Konto` korrekt setzen.
2. **Historie exakt behalten:** Das alte Browserprofil vorerst erhalten. Eine
   sichere Account-Transfer-/Login-Funktion muss implementiert oder die
   Zuordnung administrativ migriert werden, bevor das Profil gelöscht wird.

Die rohe Browser-ID ist praktisch ein Bearer-Identifier für dieses lokale
Konto. Sie gehört nicht in Chat, Git oder Screenshots. Browser-Synchronisierung
ist kein verlässlicher Transfer für `localStorage`.

Das Kontobuch selbst ist unabhängig von dieser Browserzuordnung HMAC-geschützt.
Der externe Key und der root-eigene Migrationsmarker liegen auf dem VPS unter
`/etc/betboy`, beide `root:betboy` mit Modus `0640`. Sie dürfen weder in Git noch
separat von den zugehörigen Datenbanken übertragen oder neu erzeugt werden. Ein
Restore verwendet ausschließlich ein zuvor mit
`/usr/local/libexec/betboy-backup-runtime.py --verify-only` geprüftes Archiv und
restauriert Datenbanken, Key und Marker gemeinsam bei gestoppten und
deaktivierten BetBoy-Units. Der vollständige Ablauf steht in
`deploy/README.md`.

## 4. Empfohlene Software auf dem neuen PC

Installieren:

- Git for Windows;
- Python 3.12 x64;
- Microsoft Edge oder Google Chrome;
- optional Visual Studio Code;
- optional Node.js LTS für den stillgelegten Browserimport-Test;
- Codex Desktop beziehungsweise das gewünschte Entwicklungswerkzeug.

Python 3.12 entspricht dem Produktionsserver. Ein neueres lokales Python kann
funktionieren, ist aber kein besserer Kompatibilitätsbeweis.

Kontrolle in PowerShell:

```powershell
git --version
py -3.12 --version
```

## 5. Repository neu einrichten

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Desktop\BetBoy" | Out-Null
Set-Location "$env:USERPROFILE\Desktop\BetBoy"
git clone https://github.com/xantharu123-png/btts-pro-analyzer.git betboy-app
Set-Location .\betboy-app
git switch main
git pull --ff-only
git status --short --branch
git log -3 --oneline
```

Für spätere Pushes verwendet das Repository weiterhin HTTPS. Git for Windows
öffnet beim ersten authentifizierten Push den Git Credential Manager. Keine
Tokens in die Remote-URL schreiben.

## 6. Lokale Python-Umgebung

```powershell
Set-Location "$env:USERPROFILE\Desktop\BetBoy\betboy-app"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pytest pytest-subtests
```

Lokale App starten:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit zeigt anschließend die lokale URL, normalerweise
`http://localhost:8501`.

Der Kompatibilitäts-Shim `btts_pro_app.py` bleibt vorhanden, aber der echte
Einstieg ist `app.py`.

## 7. Lokale Konfiguration und Secrets

Für reine Tests ist keine produktive Secret-Datei nötig. Für lokale Live-
Providerprüfungen kann eine ignorierte Konfiguration angelegt werden:

```powershell
Copy-Item config.ini.example config.ini
```

Zulässige Konfigurationswege, in steigender Priorität:

1. `config.ini`;
2. Umgebungsvariablen;
3. `.streamlit/secrets.toml`.

Unterstützte Umgebungsvariablen:

```text
FOOTBALL_DATA_API_KEY
API_FOOTBALL_KEY
OPENWEATHER_API_KEY
SUPABASE_DB_URL
ODDS_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
PANDASCORE_KEY
RAPIDAPI_KEY
CRICKET_API_KEY
BETBOY_FREEMODE
```

Nicht alle Variablen sind im aktuellen Produktionspfad erforderlich. Der
alte Supabase-Zugang und football-data.org sind keine Pflicht für den
kanonischen Single-VPS-Betrieb.

Vor jedem Commit:

```powershell
git status --short
git check-ignore -v config.ini .streamlit\secrets.toml
```

Beide Secret-Dateien müssen ignoriert bleiben.

## 8. SSH-Zugang zum VPS

### Empfohlener Weg: neuer Schlüssel

Auf dem neuen PC:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
$stamp = Get-Date -Format yyyyMMdd-HHmmss
$newKey = "$env:USERPROFILE\.ssh\betboy_ovh_ed25519_$stamp"
if (Test-Path -LiteralPath $newKey) { throw "Schlüsseldatei existiert bereits: $newKey" }
ssh-keygen -t ed25519 -a 100 -f $newKey -C "betboy-new-pc"
Get-Content "$newKey.pub"
```

Nur den Inhalt der `.pub`-Datei auf dem VPS unter
`/home/ubuntu/.ssh/authorized_keys` ergänzen. Solange der alte PC noch
verfügbar ist:

```powershell
ssh betboy-vps
nano ~/.ssh/authorized_keys
```

Im Editor den **öffentlichen** Schlüssel des neuen PCs als neue Zeile
einfügen. Den alten Eintrag erst entfernen, nachdem der neue Zugang in einem
separaten Terminal erfolgreich getestet wurde.

Auf dem neuen PC den normalen ED25519-Hostfingerprint beim ersten Kontakt
**out-of-band** gegen
`SHA256:YiFROIss/l4MjHP8y5+zYmjBiN8dxJVZXRVQ7SU6Rgo` vergleichen. Nur bei
exakter Übereinstimmung die OpenSSH-Frage mit `yes` bestätigen:

```powershell
ssh -F NUL -o IdentitiesOnly=yes `
  -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no `
  -o StrictHostKeyChecking=ask -o HostKeyAlgorithms=ssh-ed25519 `
  -i $newKey ubuntu@vps-a30a123f.vps.ovh.net "hostname"
```

Danach den später in allen Runbooks verwendeten Alias einrichten. Einen bereits
vorhandenen Alias nicht überschreiben, sondern zuerst manuell prüfen:

```powershell
$sshConfig = "$env:USERPROFILE\.ssh\config"
if (Test-Path -LiteralPath $sshConfig) {
    if (Select-String -LiteralPath $sshConfig -Pattern '^\s*Host\s+betboy-vps\s*$' -Quiet) {
        throw 'Host betboy-vps existiert bereits; vorhandenen Block zuerst prüfen.'
    }
}
$identityForConfig = $newKey.Replace('\', '/')
@"
Host betboy-vps
    HostName vps-a30a123f.vps.ovh.net
    User ubuntu
    IdentityFile $identityForConfig
    IdentitiesOnly yes
    BatchMode yes
    StrictHostKeyChecking yes
    HostKeyAlgorithms ssh-ed25519
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    ForwardAgent no
"@ | Add-Content -LiteralPath $sshConfig -Encoding utf8
```

Damit der Alias mit `BatchMode yes` und einem verschlüsselten Schlüssel
funktioniert, den Windows-OpenSSH-Agent einmalig in einer als Administrator
geöffneten PowerShell aktivieren und den Schlüssel anschließend in einer
normalen PowerShell laden. Die Passphrase nur am sichtbaren OpenSSH-Prompt
eingeben:

```powershell
# Einmalig als Administrator:
Set-Service ssh-agent -StartupType Automatic
Start-Service ssh-agent

# Danach als normaler Benutzer:
ssh-add $newKey
ssh betboy-vps "id -un"
```

Erwartete Ausgabe: `ubuntu`.

Falls der alte PC nicht mehr verfügbar ist, den Zugang über die OVH-Konsole
beziehungsweise KVM/Recovery wiederherstellen. Der Server darf dafür nicht neu
installiert werden.

### Auf diesem PC verifizierter Zugang am 17. August 2026

- Aktiver verschlüsselter Schlüssel:
  `C:\Users\miros\.ssh\betboy_ovh_ed25519_20260814`; Fingerprint
  `SHA256:AIawx5EsF/j6XhvIdmueox2yqSDQurgWSXB8e/RlRms`.
- Der öffentliche Schlüssel wurde per OVH-Rescue zusätzlich und atomar in
  `/home/ubuntu/.ssh/authorized_keys` eingetragen. Nach erfolgreichem Deploy
  wurden die zwei alten, unbeschränkten Schlüssel atomar entfernt. Ein
  Root-only-Backup aller drei vorherigen Einträge liegt unter
  `/var/backups/betboy-ssh/authorized_keys.pre-prune-20260817T105940Z-d861d647`
  (`root:root`, Modus `0600`, SHA-256
  `770369de3b59fab49778e360c971705a59cbbef0a118ccd0c061cca82138d265`).
- Zwei unabhängige, streng gepinnte Batch-Logins als `ubuntu` bestanden nach
  der Entfernung. Der normale
  Server-Hostfingerprint ist
  `SHA256:YiFROIss/l4MjHP8y5+zYmjBiN8dxJVZXRVQ7SU6Rgo`.
- Der Alias `betboy-vps` verwendet ausschließlich den neuen Schlüssel,
  `StrictHostKeyChecking yes`, `BatchMode yes`, nur Public-Key-Authentifizierung
  und kein Agent-Forwarding. `ssh-agent` läuft automatisch.
- OVH zeigt wieder `Aktiv` und Boot `LOCAL`. Das temporäre Rescue-Passwort wurde
  weder in Dateien noch in Git oder in diese Dokumentation übernommen.
- `authorized_keys` enthält genau noch den neuen Schlüssel; Dateihash
  `8bd63630dcd79db8a4fd9e105ce2f52bccbe8869b2b770df297d3f5441aaa64e`.
  Er sperrt Agent-, Port- und X11-Forwarding, behält aber bewusst administrativen
  Shell-/Command-Zugang.

### Nicht empfohlen: privaten Schlüssel kopieren

Der derzeit allein autorisierte private Schlüssel liegt auf diesem PC unter
`C:\Users\miros\.ssh\betboy_ovh_ed25519_20260814`. Für einen weiteren PC ist
ein neuer, separat autorisierter Schlüssel sicherer als eine Kopie. Falls eine
Kopie ausnahmsweise unvermeidlich ist, nur über einen verschlüsselten,
kontrollierten Datenträger; niemals per E-Mail, Chat, GitHub oder
unverschlüsseltem Cloudordner.

## 9. Tests auf dem neuen PC

Vollständiger Python-Testlauf:

```powershell
New-Item -ItemType Directory -Force .pytest_tmp | Out-Null
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .pytest_tmp\full
```

Erneut verifizierter Ausgangswert am 17. August 2026 in einer isolierten Kopie
ohne Secrets, Laufzeitdatenbanken und Logs. Provider-Umgebungsvariablen waren
entfernt und ausgehende Python-TCP-Verbindungen im Testprozess blockiert; das
war keine betriebssystemweite Netzwerksandbox:

```text
730 passed, 5 subtests passed
3/3 JavaScript tests passed
```

Optionaler JavaScript-Test mit installiertem Node.js:

```powershell
node --test tests\n1_import_shared.test.cjs
```

Dieser Test schützt Rollback-Code. Die N1Bet-Erweiterung ist kein aktiver
Produktpfad.

Zusätzliche Basiskontrollen:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py challenge_15k.py challenge_engine.py challenge_store.py market_consensus.py
git diff --check
git status --short
```

## 10. Produktionskontrolle vom neuen PC

Öffentliche App:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "https://vps-a30a123f.vps.ovh.net/_stcore/health"
```

Erwarteter Inhalt: `ok`.

Serverprüfung mit dem auf diesem PC verifizierten Alias:

```powershell
ssh betboy-vps
```

Auf dem VPS:

```bash
sudo -u betboy git -C /opt/betboy/app rev-parse HEAD
systemctl is-active betboy-app.service
systemctl list-timers --all 'betboy-*'
systemctl --failed
sudo ls -lt /var/backups/betboy | head
sudo ls -lt /var/backups/betboy-update | head
sudo ls -lt /var/backups/betboy-ssh | head
```

Erwartung:

- der vollständige VPS-`HEAD` entspricht dem unmittelbar davor vom PC mit
  `git ls-remote origin refs/heads/main` abgefragten GitHub-Hash; der
  serverseitige Tracking-Ref `origin/main` ist hierfür absichtlich irrelevant;
- App-Service ist `active`;
- sieben BetBoy-Timer sind vorhanden;
- keine fehlgeschlagene Unit;
- tägliche Backups werden fortgeschrieben.

## 11. Normaler Entwicklungs- und Deployablauf

Auf dem neuen PC:

```powershell
git pull --ff-only
git status --short
# Dateien bearbeiten und Tests ausführen
git diff --check
git add -- <bewusst-ausgewählte-Dateien>
git commit -m "Kurze sachliche Beschreibung"
git push origin main
```

Ein Push aktualisiert den VPS **nicht** automatisch. Die sieben systemd-Timer
starten nur Daten-/Modelljobs und führen weder `git pull` noch ein Deployment
aus. Jede Codeversion wird anschließend ausdrücklich über den root-eigenen
Updater mit ihrem vollständigen 40-hex-Commit ausgerollt.

Auf diesem VPS pinnen die beiden root-eigenen Git-Wrapper Zugriffe auf das
öffentliche feste HTTPS-Repository mit `http.version=HTTP/1.1`. Grund ist ein
reproduzierbarer Git-2.43/libcurl-Fehler im HTTP/2-Smart-HTTP-Pfad, der
irreführend nach Zugangsdaten fragte. Das ist kein Authentifizierungsproblem:
keinen PAT oder Deploy-Key hinzufügen, TLS nicht deaktivieren und den
HTTP/1.1-Pin nicht entfernen, solange der Server-Stack nicht separat
nachweislich korrigiert ist.

Danach den gepushten vollständigen Hash erneut gegen GitHub prüfen. Die
Migration und die einmalige HTTP/1.1-Bridge dieses VPS sind abgeschlossen;
künftige Releases verwenden ausschließlich den bereits installierten
root-eigenen Updater. Nur ein tatsächlich noch nie migrierter oder vollständig
neu aufgebauter Host folgt den Abschnitten `Initial installation` oder
`One-time migration of an existing VPS` in `deploy/README.md`.

```powershell
$target = (git rev-parse HEAD).Trim()
$remote = ((git ls-remote origin refs/heads/main) -split '\s+')[0]
if ($target -notmatch '^[0-9a-f]{40}$' -or $remote -ne $target) {
    throw 'Lokaler HEAD und GitHub main sind nicht exakt identisch.'
}
ssh betboy-vps "sudo /usr/local/sbin/betboy-update $target"
```

Niemals `sudo /opt/betboy/app/deploy/update_server.sh` ausführen. Checkout und
`.git` sind absichtlich durch den unprivilegierten Dienstbenutzer beschreibbar
und deshalb keine Root-Vertrauensquelle. Details stehen in `deploy/README.md`.

Anschließend Hash, Service, Health und betroffene Nutzeroberfläche erneut
prüfen. Ein lokaler Test oder erfolgreicher Push ist noch kein verifiziertes
Deployment.

## 12. Was nicht auf dem neuen PC gestartet werden darf

Nicht reaktivieren:

- alte KIMI-BetBoy-Automationen;
- Windows Task Scheduler für BetBoy Tennis oder Scanner;
- lokale Dauerschleifen für Football Shadow, Wettfinder, Tennis, E-Sport oder
  Rotkarten;
- ein zweiter schreibender Server gegen kopierte SQLite-Datenbanken.

Der VPS ist die einzige kanonische schreibende Instanz. Lokale manuelle
Entwicklungsläufe dürfen nicht als paralleler Produktionsscheduler laufen.

## 13. Backup und Notfall

### PC defekt, VPS gesund

Kein Produktionsausfall. Neuen PC wie in dieser Anleitung einrichten. Die
öffentliche App und Timer laufen weiter.

### App-Service gestört

```bash
sudo systemctl status betboy-app.service --no-pager
sudo journalctl -u betboy-app.service -n 100 --no-pager
sudo systemctl restart betboy-app.service
```

Falls der Start mit „migration is not complete“ aussetzt, nicht umgehen und
keinen Worker manuell starten. Alle Units gestoppt lassen, den Markerstatus
prüfen und ausschließlich den darin festgehaltenen Zielcommit über
`sudo /usr/local/sbin/betboy-update <marker-target>` fortsetzen. Selbst wenn
`main` inzwischen weiter ist, wird der neuere Tip bis zum Abschluss abgelehnt.

### Worker gestört

```bash
systemctl --failed
sudo journalctl -u betboy-wettfinder.service -n 100 --no-pager
sudo systemctl start betboy-wettfinder.service
```

Den betroffenen Servicenamen entsprechend ersetzen.

### VPS-Verlust

Die ZIP-Dateien unter `/var/backups/betboy` liegen auf demselben VPS und sind
allein kein Disaster-Recovery. Für vollständigen Serververlust wird ein
externes OVH-/Offsite-Backup benötigt. Vor breiter Nutzung muss ein Restore auf
eine frische Maschine praktisch getestet werden.

## 14. Dokumente für die nächste Person oder KI

In dieser Reihenfolge lesen:

1. `PROJEKTBIBEL.md`
2. `PC_WECHSEL_UEBERGABE.md`
3. `PROJECT_HANDBUCH.md`
4. aktuelle Git-Diffs und Tests
5. ältere Auditberichte nur bei historischer Ursachenanalyse

Geeigneter Übergabeprompt:

```text
Arbeite im Repository betboy-app auf main. Lies zuerst PROJEKTBIBEL.md,
PC_WECHSEL_UEBERGABE.md und PROJECT_HANDBUCH.md. Verifiziere anschließend
git status, lokalen HEAD gegen frisch mit git ls-remote abgefragtes GitHub main
und anschließend den VPS-HEAD, bevor du Änderungen machst. Ein Tracking-Ref
origin/main ist kein Remote-Nachweis. Modellwahrscheinlichkeit und
Buchmacherpreis müssen getrennt bleiben.
RESEARCH/SHADOW dürfen nicht als Echtgeldtipps veröffentlicht werden. Der VPS
ist die einzige schreibende Automationsinstanz. Bestehende ungetrackte Dateien
nicht löschen oder committen. Behauptungen aus alten Chats nur nach Code- und
Testnachweis übernehmen.
```

## 15. Abschlusscheckliste

- [x] GitHub-Zugang und Schreibberechtigung wurden per Credential Manager und
  erfolgreichem Push-Dry-Run geprüft; kein Token liegt in der Remote-URL.
- [x] Repository wurde als `betboy-app` geklont.
- [x] Ausgangs-`HEAD`, frisch abgefragtes GitHub `main` und VPS waren vor dem
  Härtungscommit identisch.
- [x] Python 3.12 und lokale Venv funktionieren.
- [x] Tests sind grün oder Abweichungen sind dokumentiert.
- [x] Neuer SSH-Schlüssel wurde autorisiert und zweimal getestet.
- [x] Zwei alte Server-Schlüssel wurden nach Root-only-Backup entfernt; zwei
  neue strikt gepinnte Logins bestanden anschließend.
- [x] Privater Schlüssel wurde nicht unsicher übertragen.
- [x] Produktions-Health liefert `ok`.
- [x] App-Service und sieben Timer sind aktiv.
- [x] Backup-Aktualität und jüngstes ZIP per CRC wurden geprüft.
- [ ] Secrets liegen nur in sicheren, ignorierten Speicherorten.
- [ ] Entscheidung zur alten Browser-/15K-Identität wurde getroffen.
- [x] Keine lokale BetBoy-/KIMI-Aufgabe im Windows-Aufgabenplaner und kein
  lokaler BetBoy-Python-Runner aktiv; der VPS bleibt die einzige schreibende
  Instanz.
- [x] `PROJEKTBIBEL.md` und `PROJECT_HANDBUCH.md` wurden gelesen.
