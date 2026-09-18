# BetBoy – aktuelle To-dos und Account-Übergabe

## Übernahme 18.09.2026, 16:00 CEST – hat Vorrang vor alten Angaben

- **Nicht alles erledigt.** Funktionscommit `afc8a10` lokal und GitHub-main,
  **VPS weiterhin `9659c49`**. Spätere Dokumentationscommits sind kein Deployment.
- Das Update vom 16.09. wurde unterbrochen; App war gestoppt/deaktiviert.
  Nach Prüfung des unveränderten Git-Arbeitsbaums und vollständigen
  Migrationsmarkers wurde der alte Stand wieder gestartet/aktiviert.
  Beide Healthchecks `ok`, sieben reguläre App-Timer gestartet/aktiviert.
  Tennisfehler nicht zurückgesetzt, kein erfolgreicher Gesamtjob behauptet.
- Erneutes entkoppeltes Update brach vor App-Stopp an der unveränderten
  Kapazitätsprüfung ab: 21.264 GB Reserve nötig, 16.313 GB frei;
  rund **4.61 GiB fehlen**. Drei eigene verwaiste Prüfkopien inventarisiert,
  noch nicht gelöscht; genaue Freigabe angefragt. Keine produktive DB oder
  reguläre Sicherung löschen, keine Schutzgrenze lockern.
- `afc8a10`: Tennis-Ergebnisse auch bei belegten Terminrevisionen; ungültige
  Fußball-Spielerprojektion verwirft nicht mehr andere gültige Spiele im Batch.
  **Frisch 162 Tests bestanden**, Exit 0, 34.88 s, DeprecationWarnings als Fehler.
  Ältere 519/193-Läufe nicht addieren; keine neue Vollsuite behaupten.
- Inventur 18.09., 13:50:35 UTC: 986 Tennis-Originalartefakte, fünf Ergebnisbelege
  für nur ein eindeutiges Spiel. Fußball: 272 Spieler-Einsatzbelege / zehn Spiele;
  4.633 Ergebnisbelege / 235 Spiele. Belegzeilen sind keine unabhängigen Testfälle.

### Nächste konkrete Schritte

1. Reserve sicher herstellen, dann nur den installierten vertrauenswürdigen
   Updater nutzen, keinen produktiven Git-Pull. Funktionsziel `afc8a10`;
   bei weiterem Docs-Commit origin/main-Anforderung des Updaters prüfen.
2. Erst danach echte Tennis-Ergebnisprobe speichern und Original-/Event-/
   Terminbindung nachweisen. Entwurf `output/playwright/capture-context-outcomes-20260916.py`
   ist noch nicht ausführungsbereit: `inventory()` fragt fälschlich
   `context_observations.source_schema` ab; Schema liegt im Inhalts-Payload.
   Vor Ausführung korrigieren. Diese Übernahme schrieb keine Kontextdaten.
   Fußball-Probe muss API-Budget und 24h-Backoff respektieren.
3. Fußball-Live-Lücke schließen: `fixture_market_probabilities()` reicht
   `native_provenance` nicht weiter; Originale haben noch
   `unresolved-receipts-not-in-this-capture`. Replay ist bereits verbunden.
   Dieselbe Live-Berechnung mit echten B1-Belegen zum Stichtag verbinden,
   Referenzraten/Kalibrierung/Originale erhalten; danach kompatibler Snapshot-
   Anschluss. Separat kalibrierte Legacy-Marginalen nicht als kohärentes neues
   Torverteilungsmodell umetikettieren. Teilnahme-/Aufstellungsmischung offen.
4. Tennis-Zeitdaten: ESPN-Proben ohne tatsächliche Matchdauer/Endzeit. ATP-CSV
   enthält 8.980 Dauerwerte in 9.736 Zeilen, aber kein Matchdatum. Turnierbeginn
   oder Zeilenfolge sind kein Ersatz. Einzelne offizielle ATP-Seitenprobe war
   mit dem Browserwerkzeug nicht zugänglich; kein Beleg für fehlende Felder
   oder HTTP 403. Quellen-/Zeitsemantik vor versionierter Erweiterung prüfen.
5. Unverändert mindestens 200 eindeutige unangetastete Testevents in drei
   Zeitblöcken zusätzlich zu Training/Tuning. **Keine freigegebene neue Wirkung
   und keine belegte bessere Wettqualität.** WTA, weitere Sportarten und
   Produktabnahme bleiben offen. Cricket bleibt ausgenommen.

Details: [Übernahmebericht](docs/audits/2026-09-18-kontext-fortsetzung.md).

## Historischer Stand 16.09.2026

Stand: **16.09.2026, 01:10 CEST**. Für die Fortsetzung zuerst dieses Dokument
lesen. Es aktualisiert den Arbeitsstatus, ersetzt aber weder die freigegebene
Spezifikation noch ältere Prüfbelege. Bei späterer Übernahme Git/VPS und letzten
Jobabschluss frisch prüfen; die Zahlen unten sind datierte Beobachtungen.

## Auftrag und feste Regeln

- An der App und ihrer fachlichen Qualität weiterarbeiten; die abgeschlossene
  Speicherbereinigung nicht wieder zum Hauptprojekt machen.
- Fußball und Tennis zuerst, danach Basketball, Eishockey und E-Sport.
  **Cricket bleibt ausdrücklich ausgenommen.**
- Verletzungen, Besetzung und Belastung sollen die Modellrechnung nachweisbar
  beeinflussen. Fehlende Daten sind nicht null; keine erfundenen Abschläge.
- Quoten verändern weder Prognose noch Modellreihenfolge und blenden keine
  berechenbare Prognose aus. Keine pauschalen Wettartenverbote; Preis separat.
- Keine gegensätzlichen Haupttipps für dasselbe Spiel. Kurze, belegte Begründung
  sichtbar statt interner Prüfbegriffe; keine erfundenen Vorteile.
- Spezifikation, Umsetzung und isolierter Worktree sind bereits freigegeben.
  Keine erneute Design-/Namens-/Arbeitskopie-Freigabeschleife. Geprüfte Änderungen
  wie beauftragt committen, pushen und kontrolliert deployen.
- Kein Echtgeld automatisch setzen, keine Kontohistorie ändern, keine neue
  kostenpflichtige Quelle ohne gesonderte Zustimmung.

## Erledigt / nicht erneut beginnen

- [x] Speicher-/Backupbereinigung und zugehörige Wartung: Funktionsstand `5069e75`.
  Keine Produktionsdatenbank und kein echtes Backup für weitere Reserve löschen.
- [x] Tennis-Live-Originale an Fallaufbau, Training, Evaluation, Transportprüfung
  und Live-Effektauswahl angebunden: `9d271c1` und `9659c49`.
  Typ: `tennis-live-winner-status-load-antisymmetric-v1`.
- [x] Dieser App-Code committed, auf GitHub-main gepusht und explizit deployed.
  Geprüfter App-Commit: `9659c49b2738d6a4c7b0fcc7442a9e8ecef3b665`.
- [x] Softwareprüfung: 545 Tests im breiteren Zwischenstand; nach zwei letzten
  Korrekturen 144 betroffene Tests unter Windows und dieselben 144 unter Linux,
  jeweils mit DeprecationWarnings als Fehler. **Keine finale Vollsuite behaupten.**
- [x] Nur die eigene temporäre Tennis-QA-Kopie und Transportarchive entfernt;
  Code/Testquellen sind über Git wiederherstellbar. Ältere QA-Bestände erhalten.

## Tatsächlicher Betrieb – nicht mit Modellqualität verwechseln

- VPS-Commit um 01:09 CEST erneut `9659c49…`, App und Caddy aktiv.
  Interner/öffentlicher Healthcheck und acht geplante Timer nach dem Release
  geprüft. Timer berechnen und warten, **sie pullen/deployen keinen Code**.
- Tennis 16.09., 00:35:59–00:50:22 CEST: Gesamtjob **Exit 1 / failed**.
  WTA-Refresh `HTTPError`, letzter Ergebnisstand 26.07.; ATP `retained_fresh`,
  Datenstand 14.09. Die Touren bleiben getrennt.
- Spielscan 850 Sekunden, also diesmal unter 900 Sekunden: 73 gefundene
  noch nicht gestartete Einzelspiele, 40 vorbereitete Abschlussfälle,
  26.283 gespeicherte Spielbeobachtungen, 23 neue Predictions.
  Ein WTA-Event `183854` blieb mit `FixtureIdentityConflict` teilweise offen.
  Kein `reset-failed` und kein weiterer manueller Lauf zur Verschleierung.
- Kontextspeicher nach dem Lauf: **450 Tennis-Originalartefakte, 0 native
  Tennis-Endergebnisbelege**. Artefakte sind nicht gleich unabhängige Testspiele.
  Die separat abgerechneten 39 ESPN-Finals im bisherigen Shadow-Store beweisen
  keine Ergebnisanbindung des neuen Kontexttrainings.
- Peak des Tennisdienstes 2,7 GB RAM; CPU-Zeit 13 min 51,6 s. Kein allgemeiner
  Performance-Erfolg aus einem Lauf knapp unter dem Zeitlimit ableiten.
- Wettfinder 00:07–00:17: 59 Modellprognosen, Gesamtstatus `degraded` wegen
  Cricket. Fußball erfolgreich, Tennis-Refresh ohne operativen Fehler in diesem
  Wettfinderlauf. Cricket bleibt unverändert; kein Alle-Sportarten-Erfolg.

## Offene To-dos – in dieser Reihenfolge

- [ ] **P0 – echte Tennis-Ergebnisbelege nutzbar machen.** Zuerst nachvollziehen,
  warum trotz gespeicherter Originale und Shadow-Finals null passende
  `match_outcome`-Belege vorliegen. Der Erfassungscode existiert bereits; nicht
  blind neu bauen. Nachweisen, dass genau passende, normal beendete native
  Spiele mit tatsächlich vor Spielbeginn gespeicherten Originalen verbunden
  werden. Keine nachträglichen Originale, keine erfundenen Zuordnungen und
  keine Retirement-/Walkover-Labels als normale Siegergebnisse.
- [ ] **P0 – WTA-Datenabruf reparieren.** HTTP-/Inhaltsfehler reproduzieren,
  gültige aktuelle Quelldaten beziehen und Tour-Frische beweisen. ATP darf
  unabhängig weiterlaufen; alten WTA-Stand nicht als frisch ausgeben.
- [ ] **P0 – Spielzuordnung WTA `183854` klären.** Native Revisionen/Teilnehmer
  gegen das unveränderliche Original vergleichen. Nur belegte Korrekturpfade
  zulassen; keine Historie überschreiben und Identitätsprüfung nicht abschalten.
  Danach echten Gesamtjob mit klar ausgewiesenem Ergebnis prüfen.
- [ ] **P1 – Laufzeitreserve belegen.** Die 850/900 Sekunden sind zu knapp.
  Teure Abschluss-/Historienabschnitte messen und gezielt verbessern, ohne
  Datenbelege wegzulassen. Parallelität mit Wettfinder auf SQLite-Locks/OOM
  prüfen; keine bloße Zeitlimit-Erhöhung als Reparatur verkaufen.
- [ ] **P1 – Fußball-Verletzungswirkung fertigstellen.** Vorhandene Erfassung
  für Spieler, Minuten, Rolle, Ersatz, Rotation und Erholung auf echte nutzbare
  Kohorten prüfen; Wirkung auf Tor-/Stärkeverteilung schätzen und alle betroffenen
  Märkte konsistent neu ableiten. Ausfallliste allein ist keine Modellwirkung.
- [ ] **P1 – Tennisbelastung vervollständigen.** Sätze, tatsächliche Dauer und
  Endzeit, Erholung sowie belegte Ausfälle und Umgebungsdaten anbinden, soweit
  die Quelle sie tatsächlich liefert. Der aktuelle ESPN-Kontext belegt keine
  echten Matchminuten/Endzeiten. Beobachtete Erholungs-Untergrenzen nicht als
  gemessene Fünfsatz-Müdigkeit ausgeben. Native historische Namens-/ID-Zuordnung
  bleibt ungeklärt; der neue Live-Pfad ersetzt diesen Nachweis nicht.
- [ ] **P1 – empirische Wirkung nachweisen und erst dann aktivieren.** ATP/WTA
  und Modellfamilien getrennt; mindestens 200 eindeutige Testevents in drei
  Zeitblöcken, unverändert vereinbarte Brier-/HAC-/BH-, Verteilungs- und
  Kalibrierungsprüfungen. Kleine synthetische Tests oder hohe Trefferquoten
  reichen nicht. Bis zum Nachweis bleibt die Basisprognose unverändert.
- [ ] **P1 – Auswahlqualität im echten Nutzerfluss abnehmen.** Wettfinder,
  RisikoBet und Daily3 auf aktualisierte Modelle, Marktvielfalt, keine
  widersprüchlichen Hauptkarten sowie kurze sachliche Pro-/Contra-Begründung
  prüfen. Fehlende/kleine Quoten dürfen den Modellpool nicht verändern.
  Keine Mindestzahl an Tipps erzwingen und keine Profitabilität behaupten.
- [ ] **P2 – Basketball/Eishockey/E-Sport vervollständigen.** Vorhandene Adapter
  und die früheren Teilreviews zuerst inventarisieren; fehlende Aufstellungs-,
  Spieler-/Torhüter-, Belastungs- und Kaderbelege gezielt schließen. Implementierte
  Hüllen nicht als empirisch aktive Sportmodelle abhaken. Cricket nicht anfassen.
- [ ] **P2 – abschließende Regression/Produktabnahme.** Historische Native-/QA-
  Pins und offene Teilplanbefunde gegen den heutigen Code prüfen; keine Pins
  pauschal umschreiben. Für jedes Teilrelease getrennt Software, verwendbare
  Daten, empirischen Status, tatsächliche Aktivierung und Browser/VPS belegen.

Daily3 ist technisch live; Name **„3 a day keeps the job away“**, höchstens
CHF 50 eigenes Geld pro Tag, Gewinne können weiterverwendet werden,
kein Nachschuss über dieses Tagesbudget hinaus.
Die Qualität/Verfügbarkeit der Auswahlen bleibt Teil der offenen Abnahme. Keine
Gewinngarantie oder Behauptung täglich sicherer CHF 150.

## Einstieg für den nächsten Account

1. Git-Root `C:/Projekt/BetBoy/betboy-app`; aktiver Arbeitsstand in
   `.worktrees/context-capacity-recovery-20260910`, Branch
   `codex/context-capacity-recovery-20260910`. Main enthält denselben App-Code.
   Dokumentationsfolgecommits sind kein neuer produktiver Funktionsstand.
2. [Übergabe](PC_WECHSEL_UEBERGABE.md), [freigegebene Spezifikation](docs/superpowers/specs/2026-09-07-kontextmodell-design.md),
   [20-Aufgaben-Plan](docs/superpowers/plans/2026-09-07-kontextmodell-umsetzung.md),
   [Tennis-Vertrag](docs/audits/2026-09-15-tennis-live-training.md) und
   [Datenpfad](docs/audits/2026-09-15-kontext-datenpfad.md) lesen.
3. Konkrete Startdateien: `context_models/tennis_training.py`,
   `tennis/live_context.py`, `context_models/tennis_live.py`,
   `scripts/tennis_daily.py`, `scripts/run_daily_pipeline.py` und zugehörige Tests.
4. Ausführlicher lokaler Abschlussbeleg:
   `output/playwright/tennis-live-training-release-20260916.md` im Worktree.
   Bewusst ungetrackt; die entscheidenden Zahlen stehen deshalb auch hier.
5. Nur VPS `betboy-vps` schreibt/schedult produktiv; App `/opt/betboy/app`.
   Deployment ausschließlich über den vorhandenen vertrauenswürdigen Updater,
   nicht durch direkten produktiven Git-Pull. Bei einem späteren Deployment
   auch `activating`-Worker beachten, nicht nur `is-active`.
6. Vorhandene ungetrackte Audits, `.playwright-cli/`, `output/playwright/` und
   `qa19-*` erhalten. Kein `git add .`, Reset/Clean oder pauschales Löschen.
   Python lokal: `C:/Projekt/BetBoy/betboy-app/.venv/Scripts/python.exe`.
   Tests isoliert, kein pytest in die produktive VPS-venv installieren.

**Nächster konkreter Arbeitsschritt:** read-only den fehlenden Tennis-
Endergebnisübergang vom bestehenden Quellenempfang zum Kontextspeicher
reproduzieren; danach gezielter Regressionstest und kleinster belegter Fix.
