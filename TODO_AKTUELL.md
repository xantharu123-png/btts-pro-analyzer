# BetBoy – aktuelle To-dos und Account-Übergabe

## 30.10.2026 09:22 – Release 20261030-1 live: Shadow-Mindestquote 1,30, Policy v9 (PR #58)

Owner-Entscheid 30.10.2026 (`docs/audits/2026-10-30-shadow-mindestquote.md`): Ein Shadow-Tipp braucht eine
Bet365-Öffnungsquote von mindestens **1,30** (`SHADOW_MIN_ODDS`), weil Favoriten zu 1,17/1,25 nichts über das Modell
sagen. Unter den übrigen Kandidaten bleibt die Reihenfolge modellgeführt, beide Kohorten folgen derselben Regel;
liegen alle frischen Quoten darunter, entsteht kein Tipp und kein Datenstatus (`fixtures_below_minimum_odds` je
Kohorte, Grenze im Artefakt als `minimum_odds`). Policy **`shadow-model-first-v9`**; die 300 Paare zählen neu.

Nach Owner-Freigabe um 09:22 CET als **`fd29323`** per No-Backup-Fast-forward von `0d9a4e8` ausgerollt (Helfer
`output/release-20261030-1/deploy.sh`, abgeleitet vom Helfer 20261029-1, 11 Pfade, Code nur
`shadow_clv_automation.py`; Offline-Prüfung v9/1,30 ok; nur App-Neustart PID 1399656→1408795; Healthchecks ok,
Snapshots unverändert, kein Backup, Einheiten unverändert; Fenster 550 s vor dem nächsten Shadow-Lauf).
Prüfung danach (`verify-01.log`): Shadow 09:32 `success`/Exit 0 (`idle`, noch kein Spiel fällig), geladene
Konstanten 12:00:00/12:00:00/`shadow-model-first-v9`/1,3, Website HTTP 200, kein neuer Alarm (letzter 27.10., Tennis).

Offen: erste v9-Tipps beobachten (Anzahl je Kohorte, `fixtures_below_minimum_odds`, Schlussquoten mit neuem
Marktstand, No-Vig-CLV); Owner-Frage später: ob ein unveränderter Schlussstand als „Markt unverändert“ in die
CLV-Evidenz gehört.

## 30.10.2026 – Morgenprüfung: erste v8-Tipps und Schlussquoten

Prüfung 30.10. 07:47 CET, nur lesend (`output/release-20261029-1/check_closing_v8.sh`, `fixtures_today.sh`,
Ausgabe `verify-03-morning.log`). **2 v8-Tipps, beide Kohorte legacy; Hybrid-Kohorte weiterhin 0 Tipps.**

- Fixture 1638114, `TOTAL_OVER_1_5`, Anpfiff 29.10. 16:00 UTC: Öffnung 1,25 (Stempel 12:04 UTC), Schlussquote
  **erfasst** 1,25 um 15:52 UTC, Stempel 12:04 UTC, Alter 228 min (Grenze 720), **kein neuer Marktstand**
  (`new_state` False); rechnerischer No-Vig-CLV −2,94 pp (faire Schlusswahrscheinlichkeit 0,7765), zählt nicht als Evidenz.
- Fixture 1638115, `TOTAL_OVER_1_5`, Anpfiff 29.10. 17:00 UTC: Öffnung 1,17 (Stempel 12:04 UTC), Schlussquote
  **erfasst** 1,17 um 16:52 UTC, Stempel 12:04 UTC, Alter 288 min, **kein neuer Marktstand**; rechnerischer No-Vig-CLV
  −2,01 pp (0,8375), zählt nicht als Evidenz.
- Shadow-Spiele 29.10.: 15, davon 15 bewertet. Keine Datenstatus-Meldungen („älter als zwölf Stunden“, „Details
  fehlen“, „Retry“) in der Ausgabe.

Betrieb seit 29.10. 14:43: 0 fehlgeschlagene Shadow-Läufe (28 `completed`, 69 `idle`, 5 `partial`), 2 erfasste
Schlussquoten; Quotenläufe 30.10. 00:15, 03:15, 06:15 erfolgreich; Platzwächter ok (19,7 GB frei, DB 8,65 GB);
letzter Alarm weiterhin 27.10. (Tennis); App aktiv, Website HTTP 200, Produktion `0d9a4e8`.

Befund: Beide Schlussstände wiederholen den Öffnungsstand (gleicher Bet365-Stempel 12:04 UTC), damit gibt es
weiterhin **keine CLV-Evidenz**. Keine Aussage über Gewinn; eine Freigabediskussion braucht 300 eindeutige Paare
derselben Policy. Offen: weiter beobachten; Owner-Frage, ob ein unveränderter Schlussstand als „Markt unverändert“
in die CLV-Evidenz gehört, wird mit diesem Muster dringlicher.

## 29.10.2026 14:43 – Release 20261029-1 live: Shadow-Altersgrenze 12 h, Policy v8 (PR #55)

Owner-Entscheid B aus `docs/audits/2026-10-29-bet365-zeitstempel.md`: Öffnungs- und Schlussquote im Shadow dürfen
einen Bet365-Stand bis **zwölf Stunden** Alter tragen (`CLVTracker.OPENING_QUOTE_MAX_AGE`,
`CLOSING_QUOTE_MAX_AGE`), Policy **`shadow-model-first-v8`**. Abruf (Öffnung 20–75 min vor Anpfiff, Schluss in
den letzten 15 min), gespeichertes Alter und der Ausschluss wiederholter Marktstände aus der CLV-Evidenz bleiben;
das Run-Artefakt nennt zusätzlich `closing_quote_max_age_seconds`. Regressionstest für den Fall 1638113.

Nach Owner-Freigabe um 14:43 CET als **`0d9a4e8`** per No-Backup-Fast-forward von `8c28a34` ausgerollt (Helfer
`output/release-20261029-1/deploy.sh`, abgeleitet vom Helfer 20261028-3, 13 Pfade, Code nur `clv_tracker.py`
und `shadow_clv_automation.py`; Offline-Prüfung 12 h/12 h/v8 ok; nur App-Neustart PID 1384218→1399656;
Healthchecks ok, Snapshots unverändert, kein Backup, Einheiten unverändert; Fenster 529 s vor dem nächsten
Shadow-Lauf). Prüfung danach (`verify-01.log`): Shadow 14:52 `success`/Exit 0 (`idle`, noch kein Spiel fällig),
geladene Konstanten 12:00:00/12:00:00/`shadow-model-first-v8`, Website HTTP 200, kein neuer Alarm.

Offen: erster aktiver v8-Lauf ab etwa 15:45 CET (Anpfiff 16:00 UTC), dann Anzahl v8-Tipps je Kohorte,
Schlussquoten mit neuem Marktstand und No-Vig-CLV beobachten; Owner-Frage später: ob ein unveränderter
Schlussstand als „Markt unverändert“ in die CLV-Evidenz gehört.

## 29.10.2026 12:20 – Bet365-Zeitstempel geklärt: 3-Stunden-Grenze hat keinen Puffer

Owner-Auftrag: nur lesend klären, warum der Bet365-Stand von Spiel 1638113 nach 12:04 UTC nicht erneuert wurde
(`docs/audits/2026-10-29-bet365-zeitstempel.md`, Protokoll `output/release-20261028-3/verify-04-zeitstempel.log`).

- API-Football setzt das Feld `update` **je Spiel in Sammelläufen** (am 29.10. um 00:00, 04:01, 06:00 und
  08:00–08:21 UTC, also 2 bis 4 Stunden auseinander), nicht je Quote. Der Shadow liest es ohne Zwischenspeicher.
- Vergleich der Quotenläufe 09:15 und 12:15 CET: 7 von 8 Spielen bekamen einen neuen Stempel, alle mit geänderten
  Preisen; das achte behielt seinen Stempel von 00:00 UTC ohne jede Preisänderung. Der Stempel wandert also mit
  Preisänderungen; ob der Anbieter unveränderte Spiele trotzdem neu abfragt, ist von aussen nicht beweisbar.
- 1638113: Bis zum einzigen Schlussabruf um 15:52 UTC kam kein Stand nach 12:52 UTC, sehr wahrscheinlich galt noch
  12:04 UTC (3 h 48 min) und wurde verworfen. Beim Abruf 11:15 UTC am 29.10. waren 7 von 8 Stempeln älter als drei
  Stunden, obwohl sich sechs dieser Spiele erst um 08:00–08:04 UTC bewegt hatten.
- Folge: Die Grenze von drei Stunden für Öffnung und Schluss entspricht dem Abstand der Sammelläufe und lässt
  keinen Puffer; daher 0 Hybrid-Tipps und keine Schlussquoten. Optionen A (so lassen), B (Grenze z. B. 12 h, Alter
  weiter gespeichert), C (Schluss ohne Altersgrenze), jeweils Policy v8; Empfehlung Claude: B. Entscheid beim Owner.

Betrieb 10:01 CET: Quotenläufe 00:15–09:15 ok, Shadow ohne Fehlschlag, Platzwächter `ok` (19,8 GB frei), kein
neuer Alarm, Produktion `8c28a34`, Website HTTP 200. Der v7-Tipp 1638113 ist abgerechnet (0:0, verloren).

## 29.10.2026 – Morgenprüfung: Schlussquoten und Tennis-Lauf

Prüfung am 29.10. 07:30 CET (nur lesend, `output/release-20261028-3/verify-03-morning.log`).

Schlussquoten: Unter Policy `shadow-model-first-v7` gibt es **1 Tipp**, Legacy-Kohorte, Spiel 1638113,
`TOTAL_OVER_1_5`, Anpfiff 28.10. 16:00 UTC, protokolliert 14:52 UTC mit Öffnungsquote 1,20 (Bet365-Stand
12:04 UTC). **Keine Schlussquote erfasst**: Der letzte Bet365-Stand vor Anpfiff war der Öffnungsstand von
12:04 UTC und damit beim Anpfiff älter als drei Stunden; der Shadow verwarf ihn regelkonform („Bet365-Quote/
Zeitstempel TOTAL_OVER_1_5 älter als drei Stunden“). Abrufzeit, Alter, neuer Marktstand, faire
Schlusswahrscheinlichkeit und No-Vig-CLV sind deshalb leer; `shadow_closing_market` hat 0 Zeilen; `predictions.result` des
Tipps ist noch leer. Hybrid-Kohorte weiterhin 0 Tipps.

Shadow-Läufe seit 28.10. 07:13: 145, davon 0 Fehlschläge (35 `completed`, 18 `partial`, 92 `idle`); summiert über
die `completed`-Läufe: 15 Spiele geplant, 15 bewertet, 44 zurückgestellt, Legacy 2 glaubwürdige Kandidaten,
1 Tipp, 0 Schlussquoten, 1 Abrechnung; Hybrid 49 Kandidatenmeldungen, alle ohne Bet365-Quote jünger als drei Stunden, 0 Tipps.
`shadow_published` erfasste 16 veröffentlichte Tipps mit Quote, 9 abgerechnet. Tipps pro Tag: 26.10. 2 (v6),
27.10. 1 (v6), 28.10. 1 (v7).

Tennis: Lauf 29.10. 00:05–00:16 CET, Result `success`, ExecMainStatus 0; eine übergrosse Partie mit
`live_case_raw_admission_exceeded` ausgeschlossen („nur diagnostizierte Fallausschlüsse; der Lauf gilt als
erfolgreich“). Kein `retention exceeded`, kein neuer Alarm in `ops_alerts.jsonl` seit 28.10. 23:00 UTC (letzte
Alarme 26./27.10.). Der Exit-Fix (PR #43) ist damit belegt.

Betrieb: Quotenläufe 29.10. 00:15, 03:15, 06:15 ohne Fehlschlag; Platzwächter 05:15 `ok`, 19,8 GB frei,
Laufzeitdatenbanken 8,59 GiB; Produktion `8c28a34`, App aktiv, Website HTTP 200.

Befund: Die neue Schlussregel greift, liefert aber noch keinen CLV-Beleg. Bei Tipps, die Stunden vor Anpfiff mit
einem älteren Bet365-Stand öffnen, und Bet365-Aktualisierungen nur etwa alle drei Stunden bleibt die Schlussquote
oft leer. Zusammen mit einem Tipp pro Tag sind 300 Paare für den Hybrid-Prüfplan nicht in Sicht; der Entscheid
zur Öffnungs- und Schlussbedingung bleibt beim Owner.

## 28.10.2026 15:32 – Schlussquoten-Prüfung: noch kein Beleg, weil der Shadow heute keinen Tipp protokolliert hat

Prüfung nach dem ersten Schlussfenster (nur lesend, `output/release-20261028-3/verify-02-closing.log`): unter Policy
`shadow-model-first-v7` gibt es **0 Tipps**, also auch keine Schlussquote. Die neuen Spalten (`closing_captured_at`,
`closing_quote_age_seconds`) und die Tabelle `shadow_closing_market` sind angelegt. Seit dem Release 07:13 liefen 50
Shadow-Läufe ohne Fehlschlag (6 `completed`, 44 `idle`); summiert über die aktiven Läufe: 15 Spiele geplant,
2 bewertet, 4 zurückgestellt, Legacy 0 glaubwürdige Kandidaten, Hybrid 5 Kandidatenmeldungen, alle ohne
Bet365-Quote jünger als drei Stunden. 28 Spiele des Tages stehen in `shadow_fixtures`, die meisten am Abend.
Tipps pro Tag zuletzt: 25.10. 7, 26.10. 2, 27.10. 1, 28.10. bis 15:32 0. `shadow_published` erfasste 14 veröffentlichte
Tipps mit Quote, 9 abgerechnet.

Betrieb: alle sechs Quotenläufe heute Exit 0; Platzwächter erstmals um 15:15 CET: `ok`, 19,8 GB frei,
Laufzeitdatenbanken 8,52 GiB; kein neuer Alarm seit 27.10.; Produktion `8c28a34`, Website HTTP 200.

Befund für den Hybrid-Prüfplan: Bei ein bis zwei Tipps pro Tag und Kohorte sind 300 Paare mit gültigem Closing in
absehbarer Zeit nicht erreichbar; das Abbruchkriterium (weniger als 50 Paare in 120 Tagen) wird wahrscheinlicher.
Ursache ist die Quote-Bedingung beim Öffnen (Bet365 ≤ 3 h) zusammen mit wenigen glaubwürdigen Kandidaten. Nächste
Prüfung: Schlussquoten der Abendspiele und der Tennis-Lauf 29.10. 00:05.

## 28.10.2026 – Release 20261028-3 live: Massnahmen 4, 7, 9 und No-Vig-CLV (PR #47–#50)

Owner-Auftrag am Vormittag: „mach bitte alles, was du von deiner Seite machen kannst“. Umgesetzt, gemergt und
nach Owner-Freigabe um 11:02 CET als **`8c28a34`** per No-Backup-Fast-forward von `94d0812` ausgerollt (Helfer
`output/release-20261028-3/deploy.sh`, 43 Pfade, Offline-Prüfungen für jede Änderung, nur App-Neustart PID
1378779→1384218, Healthchecks ok, Snapshots unverändert, kein Backup, Einheiten unverändert).

- **Massnahme 4** (PR #47, `docs/audits/2026-10-28-massnahme-4-preisregel-ci.md`): `BETBOY_TEST_PRICE_POLICY=floor`
  und Marker `price_policy`; CI-Job `price-policy` prüft Lader, Publikation, Karte, Bet-Finder, Daily3 und 15K bei
  jedem Push unter beiden Preisregeln; CI installiert `requirements.lock`, `betboy-update` stoppt auch bei
  geändertem Lockfile. Dabei fünf Fehler im Produktionspfad `floor` behoben: 15K-Ticket brach an einem älteren
  höheren Punkt ab bzw. liess sich nicht buchen; Karten-Aktionen „provenance mismatch“; Lauf ohne jede
  Buchmacherquote hätte die Website geleert; 15K-Snapshot fiel nach dem Nachtscan aus (Diagnose nach der Kopie);
  `publication_quote` (Daily3, RisikoBet, Manuelle Suche, 15K) prüfte den besten Preis statt des Medians.
- **Massnahme 7, Teil** (PR #49): Manuelle Suche ohne Buchmacherquote und ohne Quotenfilter unter `floor`;
  Multi-Sport-Anpfiff und Scan-Zeit in Zürcher Zeit statt Server-UTC. Gestaltungsfragen (Zahlenformat, Begriffe,
  Raster, 15K-Währung, Daily3-Slogan) stehen in `docs/audits/2026-10-28-massnahme-7-oberflaeche.md`.
- **Massnahme 9** (PR #48): `runtime_disk_guard.py` nach jedem Quotenlauf, `runtime_state/disk_status.json`,
  Alarm unter 5 GiB oder 10 % frei, löscht nichts. Messung 28.10.: 20 GB frei von 38 GB, `context_models.db`
  8,23 GB (+60–90 MB/Tag), seit 14.10. kein Sperrfehler; Aufbewahrung, WAL und `user_version` sind Owner-Entscheide.
- **No-Vig-CLV** (PR #50, Audit S5): `shadow_closing_market` mit fairer Schlusswahrscheinlichkeit, Artefakt
  `no_vig_clv` je Kohorte und paarweise mit HAC-Intervall; Ledger und Policy v7 unverändert.
- **Massnahme 8**: nur Plan (`docs/superpowers/plans/2026-10-28-hybrid-vor-aktivierung.md`); ein Umbau jetzt würde
  den Shadow-Vergleich neu starten, der seit heute Schlussquoten misst.

Probe vor dem Release (neuer Code gegen das Live-Dokument, nur lesend): Lader nimmt an, 0 zurückgehaltene Zeilen,
dieselben 3 Tipps, 193 Prognosen, 15K-Liste 10, Daily3 1; Angebote mit öffentlicher Freigabe 92→87 (Medianregel).
Nach dem Release: Shadow 11:12 `success`/`idle` (Tabelle `shadow_closing_market` entsteht beim ersten aktiven Lauf),
Website HTTP 200, deployter Lader liefert dasselbe Bild, kein neuer Alarm. Die zwei leeren App-Unterchats
(„Hybrid-Shadow“, „Dixon-Coles“) sind auf Owner-Wunsch archiviert.

Offen: Schlussquoten-Beleg heute ab 14:45 CET; Tennis-Exit-Beleg in der Nacht auf den 29.10.; erster
`disk_status.json` mit dem Quotenlauf 12:15; Owner: Telegram-Token/Chat-ID, Sperrung der alten API-Schlüssel beim
Anbieter bestätigen, Gestaltungsfragen aus Massnahme 7, Aufbewahrung der Kontextquittungen.

## 28.10.2026 – Shadow-Schlussquote: letzter Marktstand vor Anpfiff live (PR #45, Policy v7)

Owner-Entscheidung nach dem Befund, dass der Shadow seit dem 25.10. in 119 Läufen keine Schlussquote erfasst hat:
API-Football aktualisiert Vorspielquoten etwa alle drei Stunden, der verlangte Bet365-Stempel aus den letzten 15
Minuten vor Anpfiff traf nie. Vertragsänderung `docs/audits/2026-10-28-schlussquote-letzter-marktstand.md`: Abruf
weiter in den letzten 15 Minuten, gültig ist der letzte Stand vor Anpfiff mit höchstens drei Stunden Alter, Abrufzeit
und Alter werden gespeichert (`closing_captured_at`, `closing_quote_age_seconds`), ein wiederholter Öffnungsstand ist
keine CLV-Evidenz (`closing_without_new_market_state`), Policy `shadow-model-first-v7`. Quellcommit **`94d0812`** um
07:12 CET per No-Backup-Fast-forward von `a0747a4` ausgerollt (Helfer `output/release-20261028-2/deploy.sh`, 12 Pfade,
nur App-Neustart PID 1375208→1378779, Healthchecks ok, Snapshots unverändert). Der erste Shadow-Lauf danach (07:22)
war `idle`; die zwei neuen Spalten legt der Tracker beim ersten aktiven Lauf an. Erste fällige Schlussquote heute
etwa 14:45–15:00 CET (erstes Spiel 15:00 CET); prüfen mit
`sqlite3 shadow_clv.db "SELECT fixture_id, closing_quoted_at, closing_captured_at, closing_quote_age_seconds FROM
predictions WHERE policy_version='shadow-model-first-v7'"` (nur lesend, als `betboy`).

## 28.10.2026 – Stand nach drei Nächten, Tennis-Exit live (PR #43)

Stand vor dem Release: Produktion `ff8f0df` seit 25.10. stabil. Nachtscans 26./27.10. erfolgreich (92 und 113
Modellzeilen, je drei öffentliche Tipps), Quotenlauf in 16 Läufen ohne Fehlschlag, Shadow ohne Fehlschlag oder
Fehlalarm, Hybrid-Kohorte protokolliert erstmals (5 Tipps), die dreistufige Preisprüfung trägt im Dokument vom 27.10.
sieben abgeleitete Schranken. Bilanz `shadow_published` bis 28.10.: öffentliche Tipps 6 von 10 abgerechneten gewonnen
(mittlere Öffnungsquote 3,17), 15K-Liste 17 von 20 (1,39); Stichprobe viel zu klein für ein Urteil.

Tennis: Die Nacht auf den 28.10. speicherte erstmals seit dem 23.10. wieder Prognosen (56), der Fallausschluss nahm
eine übergrosse WTA-Partie mit Diagnose heraus, das Rückhaltlimit trat nicht auf. `tennis_daily.py` endete trotzdem
mit 1 (Einheit `failed`, Alarm). PR #43: ein diagnostizierter Fallausschluss allein ist ein erfolgreicher Lauf
(`operational_final_errors`, `DIAGNOSED_EXCLUSION_REASONS`). Quellcommit **`a0747a4`** um 00:32 CET per
No-Backup-Fast-forward von `ff8f0df` ausgerollt (Helfer `output/release-20261028-1/deploy.sh`, 6 Pfade, nur
App-Neustart PID 1352259→1375208, Healthchecks ok, Snapshots unverändert). Beleg folgt mit dem Tennis-Lauf in der
Nacht auf den 29.10.

Offen: (1) Shadow erfasst keine Schlussquote (0 in 119 Läufen seit 25.10.; `step_closing` verlangt einen
Bet365-Providerstempel in den letzten 15 Minuten vor Anpfiff und überspringt sonst stumm), dadurch wächst die
CLV-Evidenz für Hybrid und Edge-Cap nicht – Owner-Entscheid zur Regel nötig; (2) Telegram-Token und Chat-ID in
`/etc/betboy/betboy.env`; (3) Degradationspfad des Tennis-Scans auf Batch-Ebene (Rückhaltlimit 128 MB);
(4) die zwei App-Unterchats „Hybrid-Shadow: Artefakte werden nie gewärmt“ und „Dixon-Coles: Halbwertszeit und
Niveau-Prior“ starten im Ordner `C:\Projekt\BetBoy`, der kein Git-Repository ist, und scheitern daran; der erste ist
durch Massnahme 2 erledigt.

## 25.10.2026 abends – Release 8 (Massnahme 3, Einheiten) und Release 9 (Shadow-Exit) live

Owner-Freigabe um 23:20 CET; Release 8 um 23:22–23:25 per No-Backup-Fast-forward `49d43ef` → `68235ec` (Helfer
`output/release-20261025-8/deploy.sh`, 32 Pfade, 12 Dateien byte-geprüft installiert: zehn Einheiten, Vorlage
`betboy-alert@.service`, Helfer `/usr/local/libexec/betboy-alert.py`). Der Helfer brach nach der Installation an
seiner Namensprüfung ab (Exit 23: `%n` enthält schon `.service`, die Instanz heisst
`betboy-alert@<unit>.service.service`); `finish.sh` erledigte Property-Prüfungen, Neustart der vier Timer und der App,
Healthchecks ok, Snapshots unverändert. Alarm-Probelauf `betboy-alert@probe.service.service`: Eintrag in
`runtime_state/ops_alerts.jsonl`, Telegram `skipped` (Token und Chat-ID fehlen in `/etc/betboy/betboy.env`).
`OnFailure` auf allen sechs Kerneinheiten, `Persistent=yes` auf vier Timern.

**Zwischenfall:** Der Neustart der drei Tagestimer ohne Nachhol-Stempel feuerte Wettfinder-, Tennis- und E-Sport-Scan
sofort (23:24:56, seriell über `After=`). Der Wettfinder-Scan lief sauber (8,5 min CPU, 1,1 GB), ersetzte aber das
Tagesdokument des 25.10. durch eine fast leere Fassung (4 Modellzeilen, 0 Tipps) bis zum Nachtscan 03:35; der
E-Sport-Scan lief sauber; der Tennis-Scan scheiterte um 23:54 und erneut regulär um 00:20 (26.10.) an
`live tennis output/reference retention exceeded` (Batch-Rückhalt 128 MB nach 72 bzw. 112 vorbereiteten Fällen).
Der neue Fallausschluss greift nur beim Rohzeilen-Limit einzelner Partien; D3 bleibt zur Hälfte offen. Der Alarm
protokollierte beide Tennis-Fehlschläge und den Shadow-Fehlalarm um 23:32. Die Stempel existieren jetzt; ein weiterer
Neustart holt nur echte Ausfälle nach.

**Release 9** (PR #41, `ff8f0df`): Der Shadow-Runner endet nur noch bei `operational_errors` mit Exit 1 (Marker
`; Retry`, `-Quote/Zeitstempel`, `: Details fehlen` sind Datenstatus). Um 23:58 CET per No-Backup-Fast-forward von
`68235ec` ausgerollt (Helfer `output/release-20261025-9/deploy.sh`, 5 Pfade, nur App-Neustart PID 1348428→1352259,
Healthchecks ok; der erste Anlauf wurde vom Helfer wegen des laufenden Tennis-Scans abgelehnt). Nachtprüfung:
Shadow-Läufe 00:02/00:12/00:32 `idle`, 00:25 `completed` ohne Fehler und Exit 0, kein Shadow-Alarm mehr; Quotenlauf
00:15 Exit 0 mit `side_operational_errors 0` und `identity_gaps []`, die Einheit `betboy-quotes` ist nicht mehr
`failed`. `origin/main` = `ff8f0df`.

## 25.10.2026 abends – Massnahme 3 gemergt (PR #39), Release mit Unit-Installation ausstehend

*Erledigt um 23:25 CET, siehe Block oben.*

Owner-Entscheidung „alles machen“ zu den offenen Teilen von Massnahme 3 (D2, D3, D5). Betriebsänderung
`docs/audits/2026-10-25-betrieb-massnahme-3.md`: Budget und Identitätslücken der Team-/E-Sport-Quoten sind Datenstatus
und entscheiden den Exit-Code nicht mehr; der Tennis-Tagesscan schliesst einen Fall über dem Rohzeilen-Limit mit
Diagnose aus statt den Tag zu verlieren; die Timer `wettfinder/tennis/esports/quotes` holen verpasste Läufe nach;
die sechs Kerneinheiten alarmieren über `betboy-alert@%n.service` (Helfer `scripts/betboy_alert.py`, Telegram erst
nach Eintrag von `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` in `/etc/betboy/betboy.env`). Zehn Unit-Pins in Bootstrap und
Updater erneuert, eigener Pin für die Vorlage, Rekonstruktion in `tests/test_context_updater_repair.py` ergänzt.
`origin/main` = `b0356ac`.

**Release ausstehend.** Der Helfer `output/release-20261025-8/deploy.sh` (ausserhalb Git, Generator daneben) liegt
geprüft auf dem VPS unter `/tmp/deploy-20261025-8.sh`. Er macht den No-Backup-Fast-forward `49d43ef` → `b0356ac`, prüft
die Importe offline, kopiert die zehn geänderten Einheiten, die Alarm-Vorlage und den Helfer byte-geprüft nach
`/etc/systemd/system` bzw. `/usr/local/libexec`, lädt systemd neu, prüft `OnFailure`, `Persistent` und Drop-ins, startet
nur die vier Timer und die App neu. Der Auto-Modus dieser Session hat den Aufruf als Produktions-Rollout gesperrt;
Owner-Befehl (PowerShell, in einer Lücke von > 150 s vor dem nächsten Shadow-Lauf, Ausgabe nach
`output/release-20261025-8/deploy-01.log`):
`ssh betboy-vps "sudo -n bash /tmp/deploy-20261025-8.sh b0356ac6e62e9484e6a453d20ff167e38458ce77"`.
Danach: `systemctl list-timers 'betboy-*'`, `systemctl show -p OnFailure betboy-tennis.service`, Website, und einmal
`sudo systemctl start betboy-alert@probe.service` als harmloser Probelauf des Alarms (Eintrag in
`runtime_state/ops_alerts.jsonl`).

## 25.10.2026 abends – Quotenlauf-Fälligkeit mit Toleranz live (PR #37)

Owner-Entscheidung nach dem Befund, dass der Quotenlauf heute um 12:15 und 18:15 null Fussballzeilen prüfte
(Gesamtaudit D2: Versuchsstempel rund 30 Sekunden nach dem Timer, Fälligkeit exakt drei Stunden). Betriebsänderung
`docs/audits/2026-10-25-quotenlauf-toleranz.md`: fällig ab 2 h 45 min (`SCHEDULED_PRICE_DUE_GAP`) für Fussball,
Tennis und den Team-/E-Sport-Zweig; manuelle Läufe weiter ungedrosselt; etwa doppelt so viele Quotenabrufe am Tag.
Quellcommit **`49d43ef`** um 20:24 CET per No-Backup-Fast-forward von `45b66e9` ausgerollt (Helfer
`output/release-20261025-7/deploy.sh`, 7 Pfade, nur App-Neustart PID 1339155→1343024, Healthchecks ok, Snapshots
unverändert, Beleg `deploy-01.log` ausserhalb Git). Der Quotenlauf lädt den Code je Lauf neu; der Lauf um 21:15 ist
der erste mit der Toleranz, erwartbar mit null Fussballzeilen, weil alle heutigen Spiele dann begonnen haben;
der erste Beleg für die Toleranz ist der Lauf um 00:15 (Stempel 21:15, Abstand 3 h minus Jitter).

## 25.10.2026 abends – Dreistufige Preisprüfung live (PR #34)

Übernahme nach dem Account-Wechsel: Der andere Account hatte nichts ausgerollt (kein Branch, kein PR, VPS
unverändert auf `ff5f5a0`). Quellcommit **`45b66e9`** (`main` nach Protokoll-PR #35, Code aus PR #34) um 19:12 CET
per No-Backup-Fast-forward von `ff5f5a0` ausgerollt (Helfer `output/release-20261025-6/deploy.sh`, 14 Pfade, nur
App-Neustart PID 1335323→1339155, Healthchecks ok, Snapshots unverändert, Beleg `deploy-01.log` ausserhalb Git).
Prüfung mit dem ausgerollten Code gegen das Live-Dokument um 19:15: wie im Trockenlauf erwartet 12 gespeicherte
`PLAYABLE`-Zeilen zeilenweise zurückgehalten (Median unter 1,20); Website zeigt das Tagesprogramm, 2 öffentliche
Tipps, 21 Fussballkarten sichtbar, 13 wegen Marktquote unter 1,20 ausgeblendet, keine Hauptauswahl ohne Quote ab
65 %. Der Quotenlauf 18:15 (noch alter Code) prüfte 0 Spiele; abgeleitete Schranken (`reference_price_bound`)
entstehen erst mit dem nächsten Quotenlauf, der Fussball prüft, spätestens mit dem Nachtscan um 03:35.

## 25.10.2026 abends – Übergabe: dreistufige Preisprüfung gemergt, NICHT ausgerollt

*Erledigt um 19:12 CET, siehe Block oben.*

Stand bei der Übergabe an den anderen Claude-Account (Owner hat den Release-Schritt angehalten):

- **Produktion** läuft weiter `ff5f5a0` (Massnahme 2, seit 16:28 CET). Nichts von PR #34 ist auf dem VPS.
- **`origin/main` = `a2864ac`** (Merge von PR #34, Quick-CI grün). Owner-Entscheidung und Vertragsnotiz:
  `docs/audits/2026-10-25-preispruefung-dreistufig.md`. Kurz: (1) direkte Quote: Median der Buchmacher statt
  Bestpreis; (2) Tor-Bereiche ohne Quote über die Über/Unter-Linien desselben Spiels (`reference_price_bound`,
  Marge 6 %); (3) ohne jeden Preisbeleg nur unter 65 % Modellwahrscheinlichkeit. Anlass: Hauptauswahlen
  „Hammarby 1–4 Tore“ (Buchmacher 1,15) und „Ajax über 2,5 Ecken“ ohne geprüfte Quote.
- **Geprüft:** `tests/test_price_floor_policy.py` 29 grün, Preis-/Kartenpfade 1993 grün, weitere Wettfinder-,
  15K-, RisikoBet-, Daily3-, Shadow-Suiten und Quick-CI 1609 grün, `ruff check .` grün. Trockenlauf auf dem VPS
  (Module unter `/tmp/newcode`, Live-Dokument nur gelesen): bis zum nächsten Quotenlauf hält der neue App-Lader
  12 gespeicherte `PLAYABLE`-Zeilen zeilenweise zurück (Median unter 1,20, Zähler `price_inconsistent_rows`),
  danach 0; 3 öffentliche Tipps; 15K-Liste 15 → 10; 49 Bereichsmärkte mit Schranke (21 belegt, 28 gesperrt).
- **Release-Helfer liegt bereit, noch nicht auf den VPS kopiert:** `output/release-20261025-6/deploy.sh`
  (ausserhalb Git; vorheriger Stand `ff5f5a0`, Ziel `a2864ac`, 14 Pfade in `release-files.txt`, Offline-Asserts
  für `FLOOR_UNPRICED_MAX_PROBABILITY`, `derive_range_price_bound`, `_attach_floor_price_bounds`,
  `_floor_withheld`, `ModelSignal.reference_price_bound`; Generator `gen_deploy14.py` im selben
  Ordner).

Nächste Schritte für den Release (nur mit Owner-Freigabe; PowerShell, Windows-OpenSSH):

1. `scp C:\Projekt\BetBoy\output\release-20261025-6\deploy.sh betboy-vps:/tmp/deploy-20261025-6.sh`
2. Lücke abwarten: Shadow-Timer läuft alle 10 Minuten (`:02`), der Helfer verlangt > 150 s Abstand zu allen
   Timern und keine laufenden Jobs; `/tmp/shadow_gap.sh` auf dem VPS gibt die Sekunden bis zum nächsten
   Shadow-Lauf aus. Quotenlauf alle 3 Stunden (18:15, 21:15, …).
3. `ssh betboy-vps "sudo -n bash /tmp/deploy-20261025-6.sh a2864ac6a9310be030093de975cd13864435dfac"`, Ausgabe nach
   `output/release-20261025-6/deploy-01.log`; erwartet `OFFLINE_RELEASE_IMPORTS=ok`, Healthchecks `ok`,
   `HEAD=a2864ac…`, nur App-Neustart.
4. Website prüfen (bis zum nächsten Quotenlauf ~12 zurückgehaltene Zeilen sind erwartet).
5. Nach dem nächsten Quotenlauf das Tagesdokument prüfen: Zeilen mit `reference_price_bound`,
   `price_inconsistent_rows` = 0, öffentliche Tipps vorhanden, keine Hauptauswahl ohne Preisbeleg ab 65 %.
6. Protokoll in `TODO_AKTUELL.md`, `PC_WECHSEL_UEBERGABE.md`, `STATUS.md` (Produktionszeile) nachtragen.

Aufräumen optional: `/tmp/newcode` auf dem VPS enthält die Trockenlauf-Module (kein Einfluss auf Produktion).

## 25.10.2026 – Massnahme 2 des Gesamtaudits live: Shadow misst Trefferquote, Hybrid und veröffentlichte Tipps

Owner-Entscheidung: Massnahme 2 umsetzen. Vertragsänderung `docs/audits/2026-10-25-shadow-massnahme-2.md` (PR #32):
Trefferquoten zählen den Tracker-Code `Won` (vorher `WIN`, immer 0), das Hybrid-Warm-up läuft vor der Bewertung
(früheste Anpfiffe zuerst), fehlende Hybrid-Artefakte lassen ein Spiel bis zum letzten Versuch offen (fehlgeschlagener
Bau je Tag markiert), die neue Tabelle `shadow_published` protokolliert je Lauf die veröffentlichten Tipps und die
15K-Liste und rechnet Tormärkte aus dem Endstand ab, Edge-Cap-Gruppen und die paarweise Hybrid-Differenz tragen
HAC-Intervalle. Trockenlauf vor dem Release auf dem VPS (neues Modul unter `/tmp/newcode`, Live-Dokument nur gelesen,
leere Temp-Datenbank): 18 veröffentlichte Zeilen erfasst (3 Tipps, 15 15K-Zeilen, alle mit Quote), 0,7 s, Spitzen-RSS
291 MB. Quellcommit **`ff5f5a0135893b9db68bfde8b9d950c74bdef6d8`** um 16:28 CET per No-Backup-Fast-forward von `5f467d3` ausgerollt (Helfer
`output/release-20261025-5/deploy.sh`, 11 Pfade inkl. Protokoll-PR #31, nur App-Neustart PID 1332194→1335323,
Healthchecks ok, Snapshots unverändert). Erster Shadow-Lauf mit neuem Code um 16:32 CET: Status `completed`, keine Fehler, 18 veröffentlichte Zeilen in `shadow_published` (alle mit Quote, mittlere Öffnungsquote 15K 1,37, Tipps 4,58), Hybrid mit 17 Liga-Artefakten im Cache, keine offene Liga, kein Fehlbau, HAC-Felder im Artefakt, Spitzenspeicher 240 MB. Der Shadow protokolliert seit dem 25.10. wieder (5 Legacy-Tipps, 1 Hybrid-Tipp offen). Grenze: Läufe ohne fällige Shadow-Arbeit enden weiter als `idle` und erfassen dann nichts; jedes veröffentlichte Fussballspiel der Shadow-Ligen löst aber vor Anpfiff einen Bewertungslauf aus.

Offen (Owner-Entscheid, Befund 25.10. abends nach Beschwerde zu den Karten Mjällby–Hammarby und Sparta–Ajax): Die
Hauptauswahl je Spiel nach höchster Modellwahrscheinlichkeit (Entscheid 23.10.) wählt systematisch die sicherste
Auswahl. Im Tagesdokument vom 25.10. hatten 42 von 46 Fussball-Hauptauswahlen eine faire Modellquote unter 1,50, und
16 hatten keine Marktquote, weil Teamtor-Bereiche, Ergebnis-plus-Tore- und Oder-Märkte nie bepreist werden (heute 0
von 104 Zeilen); dort greift die 1,20-Grenze nicht (Hammarby 1–4 Tore 79,7 %, Buchmacher 1,15; Ajax über 2,5 Ecken
87 %, ohne Quote). Vorschlag: Hauptauswahl nur aus Auswahlen mit gefundener Marktquote ab einem Mindestwert; mit 1,50
hätten 41 von 46 Spielen eine Hauptauswahl (Median-Quote 1,70), mit 1,20 wären es 43 (Median 1,32).

## 25.10.2026 – Massnahme 1 des Gesamtaudits live: Lader je Zeile, Quotenlauf und 15K mit Zeilen-Uhr

Gesamtaudit `AUDIT_BERICHT_2026-10-25_CLAUDE.md` (PR #29, fünf Prüfstränge). Owner-Entscheidung: Massnahme 1 sofort
umsetzen. Vertragsänderung `docs/audits/2026-10-25-lader-je-zeile.md` (PR #30): Der App-Lader hält bei Preis- oder
Statusabweichungen nur die betroffene Zeile und ihre veröffentlichten Kopien zurück (Zähler
`price_inconsistent_rows`, Log-Warnung), Struktur- und Identitätsfehler bleiben fail-closed fürs Dokument; behaltene
Quoten im Quotenlauf werden unter `floor` klassifiziert und bekommen ihre Preis-Uhr; der 15K-Snapshot bewertet jede
Zeile mit ihrer Preis-Uhr und dem Floor-Status (`_challenge_release_quote`) und überspringt nicht ausführbare Zeilen
statt des ganzen Snapshots; das Nachrücken prüft `sources.football.operational_error_count` wie der Lader; der
Fussball-Quotenlauf zählt Budgetmeldungen nicht mehr als Betriebsfehler. `gate` unverändert. Quellcommit
**`5f467d33184ce54cfe52caf60c2221ca6a2de521`** um 13:23 CET per No-Backup-Fast-forward von `8e4d06f` ausgerollt (Helfer
`output/release-20261025-4/deploy.sh`, 8 Pfade inkl. Protokoll-PR #28 und Audit-PR #29, nur App-Neustart
PID 1329633 → 1332194, Healthchecks ok, Snapshots unverändert). Vor dem Release Trockenlauf der neuen Module gegen das echte Dokument (Lader ok, 0 zurückgehaltene Zeilen, 15K-Snapshot 15 Einträge statt None); nach dem Release um 13:27 CET bestätigt: Lader lädt 304 Prognosen und 3 öffentliche Tipps, 15K-Snapshot liefert 15 Einträge.

## 25.10.2026 – Hotfix App-Lader: neu veröffentlichte Tipps mit ihrer Preis-Uhr bewerten (live)

Der Quotenlauf um 09:15 CET veröffentlichte erstmals per Nachrücken 3 Tipps und 15 Einträge der 15K-Liste, deren
Quoten nach dem Nachtscan (03:53 CET) beobachtet waren. Der App-Lader rechnete die strikten Zeilen mit der Scan-Uhr
(`generated_at`) nach, erhielt im 24-Stunden-Fenster `UNPRICED` statt `PLAYABLE` und verwarf das ganze Dokument; die
Website war von 09:15 bis 12:02 CET leer (Befund beim Gesamtaudit, Belege `output/release-20261025-3/`,
`strict_probe.py`). Fix in PR #27: strikte Zeilen werden wie die Modellzeilen mit ihrer `reference_price_evaluated_at`
bewertet (`generated <= evaluated <= now`); ohne diese Uhr bleibt eine nach dem Scan beobachtete Quote fail-closed.
Quellcommit **`8e4d06fb64bc89d07fa543fe5338d33e637c06d2`** um 12:02 CET per No-Backup-Fast-forward von `2d4a01c` ausgerollt (Helfer
`output/release-20261025-3/deploy.sh`, 5 Pfade inkl. Protokoll-PR #26, nur App-Neustart PID 1326823 → 1329633,
Healthchecks ok, Snapshots unverändert). Prüfung um 12:05 CET: Der Lader lädt das Dokument von 09:15 wieder (339 Prognosen, 3 öffentliche Tipps), die Website zeigt 52 Spiele mit „Ergebnisstand heute 03:53“. Lehre: Der Lader verwirft bei jeder Abweichung das ganze
Dokument; jede Änderung an der Veröffentlichung braucht einen Lader-Test mit realitätsnahen Uhren (Scan, Quoten,
Abruf) und vor dem Release einen Trockenlauf auf dem echten Dokument mit den echten Uhren.

## 25.10.2026 – Öffentliche Tipps rücken nach jedem Quotenlauf nach (live)

Owner-Entscheidung (Chat, 25.10.): Entfernt der Quotenlauf einen öffentlichen Tipp wegen Marktquote unter 1,20,
rückt die nächste freigegebene Auswahl nach derselben Auswahlregel nach. Vertragsänderung
`docs/audits/2026-10-25-tipp-nachruecken.md` (PR #25): Bisher leerte jeder Quotenlauf (alle drei Stunden) die
öffentlichen Tipps und die 15K-Liste vollständig, bis zum nächsten Nachtscan gab es keinen öffentlichen Tipp mehr.
Jetzt läuft nach jedem Quotenlauf die Auswahlregel des Scans erneut über das Modell-Ledger
(`wettfinder_automation._republish_floor_candidates`): freigegebene Zeilen verifizierter Spiele in Ledger-Reihenfolge
ohne Marktquote unter 1,20 und ohne begonnene Spiele, die ersten drei je ein Spiel; die 15K-Liste wird mit ihrem
`PLAYABLE`-Korridor neu besetzt. Begleitkorrekturen im selben Vertrag: Der App-Lader macht unter `floor` auch
unbepreiste veröffentlichte Zeilen zu öffentlichen Tipps und begrenzt sie auf das Alter des Modelldokuments statt
150 Minuten; die Karte blendet nur noch Prognosen mit Marktquote unter 1,20 aus (vorher jede ohne Quote, deshalb
44 statt 84 Spiele). Quellcommit **`2d4a01c3973521a7a38b71a2167da402bf5fbc6d`** um 08:05 CET per No-Backup-Fast-forward von `ae3bd2f`
ausgerollt (Helfer `output/release-20261025-2/deploy.sh`, 10 Pfade, nur App-Neustart PID 1325818 → 1326823,
Healthchecks ok, Snapshots unverändert). Trockenlauf um 08:08 CET auf einer Kopie des Tagesdokuments (nichts geschrieben): Der nächste Quotenlauf veröffentlicht 3 öffentliche Tipps (Viking–Tromsø, Molde–Fredrikstad, Lecce–Juventus, alle PLAYABLE, Ledger-Reihenfolge) und 15 Einträge der 15K-Liste; der App-Lader lädt die Kopie mit 3 Signalen. Website um 08:09 CET: 60 statt 44 Spiele sichtbar, weil Prognosen ohne Quote wieder angezeigt werden; die öffentlichen Tipps erscheinen mit dem Quotenlauf um 09:15 CET.

## 25.10.2026 – Website leer wegen E-Sport-Preisstatus; Fix live

Nachtcheck 25.10. (Belege `output/nightcheck-20261025/` ausserhalb Git): Tagesscan 03:35–03:59 CET `completed`
(107 Spiele gefunden, 84 modelliert, 690 zugelassene Kandidaten, 373 Modellprognosen, 3 öffentliche Tipps), aber die
Website blieb ab 06:15 leer. Ursache: Der Quotenlauf hängte erstmals seit dem Pro-Tarif E-Sport-Quoten an, die
E-Sport-Anbindung speicherte den alten Code `OBSERVED`, der App-Lader rechnete unter `floor` `PLAYABLE` und verwarf
das ganze Dokument (eine DOTA2-Zeile; damit fehlten auch alle Fussball-Prognosen). Fix in PR #23 (Nachtrag in
`docs/audits/2026-10-23-preisregel-1-20.md`): E-Sport-Status folgt der aktiven Preisregel inkl. Ausführungsfelder bei
`PLAYABLE`; der Lader akzeptiert Altzeilen mit `OBSERVED` ohne Ausführungsfelder. Quellcommit
**`ae3bd2f56775b61ea5f2b73ab18a7310f0ef23c9`** um 07:28 CET per No-Backup-Fast-forward von `87d334a` ausgerollt (Helfer
`output/release-20261025-1/deploy.sh`, 8 Pfade, nur App-Neustart PID 1313890 → 1325818, Healthchecks ok, Snapshots
unverändert). Website um 07:31 CET geprüft: „Dein Spieltag“ zeigt wieder 44 Spiele (350 Fussball-, 11 E-Sport-, 8 Eishockey-Prognosen), kein Leerhinweis; öffentliche Tipps 0 (siehe unten).
Weitere Befunde der Nacht: Die 3 öffentlichen Tipps von 03:59 fielen um 06:15 wegen Marktquote unter 1,20 weg, und es
rückt nichts nach (Obergrenze 3, Auswahl nur im Nachtscan, obwohl 166 von 353 Zeilen die statistische Freigabe bestehen).
Tennis-Tagesscan scheitert seit 22.10. an „live tennis per-case raw admission exceeded“ (`context_models/tennis_live_source.py`,
Codex). Shadow protokolliert weiter 0 Tipps (je Lauf höchstens ein glaubwürdiger Kandidat ohne frische Quote); die
Hybrid-Kohorte wärmt keine Artefakte (`artifacts_warmed: 0`). Quotendienst beendet jede zweite Ausführung mit Exit 1
(E-Sport-Quotenbudget 10/Tag, Eishockey-ValueError), Fussballquoten fehlerfrei. App-Neustart am 24.10. 06:40 kam von den
Ubuntu-Sicherheitsupdates.

## 23.10.2026 – Keine 1,20-Hinweise und keine Buchmacherquoten bei eigener Quoteneingabe (live)

Owner-Entscheidung (Chat, 23.10. spätabends): Auch die Hinweise an den Stellen, an denen der Nutzer selbst
eine Quote eingibt, fallen weg; die 1,20-Sperre selbst bleibt. Nachtrag in
`docs/audits/2026-10-23-hauptauswahl-wahrscheinlichkeit.md` (PR #21): unter `floor` keine Caption und kein
Regeltext-Satz zur Mindestquote in der Daily3-Vormerkung, keine Caption „Deine Mindestquote …“ in der Manuellen
Suche und auf der Tennis-Karte, keine Kennzahl „Mindestquote“ in „Meine Tipps“; dazu zeigen Tennis-Tab
(„Letzte Quote“) und Multi-Sport-Suche („Quote“) keine Buchmacherquote mehr, was der Preisregel vom Nachmittag
entgangen war. Ablehnungen unter 1,20 bleiben begründet. Quellcommit
**`87d334a9145b18c4ea19f59282ce127feb1953e9`** um 21:27 CEST per No-Backup-Fast-forward von `6946e3b`
ausgerollt (Helfer `output/release-20261023-7/deploy.sh`, 12 Pfade inkl. Protokoll-PR #20, nur App-Neustart
PID 1309177 → 1309930, Healthchecks ok, Snapshots unverändert). Website um 21:31 CEST geprüft: Wettfinder, Daily3 und „Meine Tipps“ zeigen weder das Wort „Mindestquote“ noch eine Buchmacherquote; Tennis- und Modellansicht sind durch die neuen Tests abgedeckt (heute keine Tennis-Auswahl).

## 23.10.2026 – Hauptauswahl nach Wahrscheinlichkeit, Karte ohne Mindestquote live

Owner-Entscheidung (Chat, 23.10. abends): Die Hauptauswahl je Spiel ist die angezeigte Auswahl mit
der höchsten Modellwahrscheinlichkeit, und die Karte nennt keine Mindestquote mehr; die 1,20-Grenze
wirkt nur im Hintergrund. Vertragsänderung `docs/audits/2026-10-23-hauptauswahl-wahrscheinlichkeit.md`
(PR #19): `forecast_selection.select_event_leads` vergleicht innerhalb derselben Teilnehmerbindung
und Modellrevision nach Modellwahrscheinlichkeit (Gleichstand: stabiler Marktschlüssel), `selection_rank`
ordnet weiter Katalog und 15K-Liste; der Wettfinder-Katalog erfindet ohne vergleichbare Revision keinen
Lead (`require_comparable`); gilt für Wettfinder, Manuelle Suche und 15K-Modellauswahl. Quellcommit
**`6946e3bec226444f602e8b7711719874447a7ec3`** um 21:04 CEST per No-Backup-Fast-forward von `dcc8b55`
ausgerollt (Helfer `output/release-20261023-6/deploy.sh`, 14 Pfade inkl. Protokoll-PR #18, nur
App-Neustart PID 1306676 → 1309177, Healthchecks ok, Snapshots unverändert, Offline-Smoke prüft die
neue Lead-Signatur und die Karte ohne Mindestquote-Zelle). Website um 21:06 CEST geprüft: Independiente del Valle–U. Católica führt jetzt „Team 2 Gesamttore Unter 1,5“ (72,1 %) vor „Auswärtssieg“ (24,3 %) unter „Weitere Märkte“; das Wort „Mindestquote“ kommt auf der Seite nicht mehr vor.
Hinweise bei eigener Quoteneingabe (Daily3-Vormerkung, Manuelle Suche, Tennis) bleiben, weil sie die
1,20-Sperre erklären.

## 23.10.2026 – Preisregel 1,20 live: Buchmacherquoten kein Gate mehr

Owner-Entscheidung (Chat, 23.10.): Buchmacherquoten gehören nicht in die App; sie sichern im
Hintergrund nur die 1,20-Grenze. Vertragsänderung `docs/audits/2026-10-23-preisregel-1-20.md`
(PR #14): Tipps erscheinen nach Modell- und Kontextgates, `UNPRICED` bleibt sichtbar, nur
`BELOW_FLOOR` sperrt; Karte nur „Mindestquote 1,20“; Daily3 und Preisentscheidung nur 1,20;
`BETBOY_PRICE_POLICY=gate` hält den alten Vertrag für Vergleiche vor (nicht setzen).
Quellcommit **`74fd7e4e670e346cee5d27ad579c96cbcfb730cc`** um 19:23 CEST per No-Backup-Fast-forward
von `aa4baa9` ausgerollt (Helfer `output/release-20261023-3/deploy.sh`, 18 Pfade, nur App-Neustart
PID 1295384 → 1301953, Healthchecks ok, Snapshots unverändert, Offline-Smoke bestätigt die aktive
Preisregel). Hintergrund: seit 10.10. null öffentliche Fussball-Tipps, weil die 45-Minuten-Frische
beim Drei-Stunden-Takt von API-Football nie erreichbar war (57 Quotenläufe ohne spielbaren Preis).
Danach zeigte der Scan weiter null Tipps: der Freigabekontext verlangte bestätigte Aufstellungen (zum
Scanzeitpunkt nie vorhanden) und die Freigabeprüfungen genau 96 Hypothesen (seit FDR über Ligen 864).
Fix in PR #15 (`context_release_eligible`, `hypothesis_count_is_catalog_multiple`), als
**`e00ff6e032ea8ea81d696d4144839ddc71f6af35`** um 19:45 CEST ausgerollt (6 Pfade, PID 1301953 → 1303949,
Healthchecks ok, Snapshots unverändert).
Scan um 19:47 CEST: 3 öffentliche Fussball-Tipps (RELEASED, PLAYABLE) für die Abendspiele, 1 Kandidat in der 15K-Freigabeliste, 23 Spiele, 253 zugelassene Kandidaten, 0 Betriebsfehler. Die ersten öffentlichen Fussball-Tipps seit dem 10.10.
Die App zeigte diese Tipps zunächst nicht („Aktuell ist noch kein automatisches Ergebnis verfügbar“):
`ev_signal_sources._load_automated_wettfinder_document` verwarf das ganze Dokument, weil freigegebene
Zeilen ohne bestätigten Preis (`UNPRICED`/`UNAVAILABLE`) unter dem alten Vertrag ungültig waren. Fix in
PR #17 (Lader akzeptiert unbepreiste öffentliche Tipps unter `floor` ohne Ausführungsfelder; die
15K-Freigabeliste bleibt `PLAYABLE`), als **`dcc8b559a7d4c329f388e943c9d1262c2b322b4d`** um 20:26 CEST
ausgerollt (Helfer `output/release-20261023-5/deploy.sh`, 7 Pfade, PID 1303949 → 1306676, Healthchecks
ok, Snapshots unverändert). Website um 20:31 CEST geprüft: „Dein Spieltag“ zeigt fünf Spiele
(Widzew Łódź–Górnik Zabrze, Stuttgart–Gladbach, Bolton–Middlesbrough, Independiente del Valle–U. Católica,
PHI–ANA Eishockey) mit Modellwahrscheinlichkeit und „Mindestquote 1,20“, Daily3 mit einer Auswahl.
Beobachtung, unverändert gelassen: Die Hauptauswahl je Spiel ist der statistische Lead des Produzenten
(`selection_rank`, `forecast_selection.select_event_leads`), nicht die höchste Wahrscheinlichkeit;
bei Stuttgart–Gladbach führt deshalb der Auswärtssieg (16,6 %) vor „Unter 4,5“ (78,3 %).
Scan um 20:27–20:35 CEST unter allen drei Fixes: `completed`, 23 Spiele, 253 zugelassene Kandidaten, 2 öffentliche Fussball-Tipps (RELEASED, PLAYABLE) für die Abendspiele, 15K-Liste leer; der App-Lader lädt das Dokument (14 Prognosen, 1 Signal). Beleg ausserhalb Git: `output/release-20261023-5/scan-result-01.log`. Die Wochenend-Tipps entstehen mit den Tagesscans um 03:35 am 24.10. und 25.10.

## 23.10.2026 – Pro-Tarif wieder aktiv, Zähler-Fix live, Tagesscan nachgeholt

Owner hat den API-Football-Pro-Tarif um 14:50 CEST bezahlt (7 500/Tag, bis 23.10.2027; der Tarif
war am 19.10. abgelaufen). Der lokale Budgetzähler hielt für den 23.10. am 100er-Limit fest;
Fix in PR #12 (`api_budget`: höheres Providerlimit ersetzt die Schätzung) plus
`scripts/api_budget_resync.py`, als **`aa4baa9848c859719cb6ff86a440dfa816068845`** um 15:04 CEST
per No-Backup-Fast-forward von `4fdeba9` ausgerollt (Helfer `output/release-20261023-2/deploy.sh`,
9 Pfade, nur App-Neustart PID 1291312 → 1295384, Healthchecks ok, Snapshots unverändert).
Resync um 15:08: Zähler 100/99 → 7 500/7 499. Tagesscan dreimal manuell gestartet (15:08
teilweise blockiert, 15:27 Wiederholungssperre, 15:54 vollständig): Stand 16:07 CEST
`completed`, 23 Spiele mit verifiziertem Kontext, 269 Basis-/254 zugelassene Kandidaten, 144
Fussball-Modellkandidaten (SHADOW), 0 Betriebsfehler, 583 API-Aufrufe verbraucht. Öffentlich
freigegebene Tipps entstehen mit der Quotenaktualisierung (18:15) und dem Kontext vor Anpfiff.
Belege ausserhalb Git: `output/release-20261023-2/`.

## 23.10.2026 – Frischeregel der Öffnungsquote (Policy v6) auf dem VPS live

Quellcommit **`4fdeba90319b6429d05158e45f1f35ac4578f1ab`** (main nach PR #8–#10) am 23.10.2026
um 07:25 CEST per No-Backup-Fast-forward von `fd45176` auf dem VPS ausgerollt (Owner-Freigabe
im Chat; ausgeführt von Claude per `ssh betboy-vps`, Root-Helfer
`output/release-20261023/deploy.sh` nach dem bisherigen Muster). Exakter Dateisatz 14 Pfade
(`clv_tracker.py`, `shadow_clv_automation.py`, vier Testdateien, Doku), keine Unit-, Updater-
oder Requirements-Änderung; alle Jobs im Leerlauf, Backup-Timer inaktiv/deaktiviert.
Offline-Import-Smoke von 27 Modulen `ok`, nur App neu gestartet (PID 1285025 → 1291312),
lokaler und öffentlicher Healthcheck `ok`, acht Timer aktiv. Prognose-Snapshots vor und nach
dem Release byteidentisch. Kein Backup, kein Scan, kein DB-Eingriff. Die Ledger-Spalte
`opening_quote_age_seconds` legt der Tracker beim ersten fälligen Shadow-Lauf selbst an
(`ALTER TABLE`, alte Zeilen `NULL`). Belege ausserhalb Git: `output/release-20261023/deploy-01.log`,
`post-release-01.log`.
Erster Shadow-Lauf mit der neuen Policy um 07:32 CEST sauber beendet (Exit 0, `idle`: kein fälliges Spiel); Spielpläne und Kohorten bleiben vom API-Kontingent (100 je Tag) abhängig.

## 22.10.2026 – Audit-Reparaturen und Shadow-Kohorten auf dem VPS live

Quellcommit **`fd4517629bbb517402147173f66cf1ea011476bc`** (main nach PR #1–#7) am
22.10.2026 um 20:02 CEST per No-Backup-Fast-forward von `be5e441` auf dem VPS ausgerollt
(Freigabe des Owners im Chat; ausgeführt von Claude per `ssh betboy-vps`, Root-Helfer
`output/hybrid-shadow-20261022/deploy.sh` nach dem bisherigen Muster). Exakter Dateisatz
86 Pfade, keine Unit-, Updater- oder Requirements-Änderung; alle Jobs im Leerlauf,
Backup-Timer inaktiv/deaktiviert. Offline-Import-Smoke der 26 geänderten Module `ok`,
nur App neu gestartet (PID 1271293 → 1285025), lokaler und öffentlicher Healthcheck `ok`,
acht Timer aktiv. Prognose-Snapshots (`wettfinder_latest.json`, `riskobet_latest.json`)
vor und nach dem Release byteidentisch. Kein Backup, kein Scan, kein DB-Eingriff.
Env: kein Portal-Token gesetzt (persönlicher Modus bleibt), keine Shadow-/Edge-Cap-Flags
(Defaults: Hybrid-Kohorte an, Kappung nur protokolliert). Belege ausserhalb Git:
`output/hybrid-shadow-20261022/deploy-01.log`, `post-release-01.log`.
Erster Shadow-Lauf mit dem neuen Code um 20:12 CEST sauber beendet (Exit 0, `idle`: kein fälliges Spiel im Fenster); die Hybrid- und Edge-Cap-Protokolle füllen sich mit den nächsten fälligen Spielen.

## 19.10.2026 – Claude-Audit-Reparaturen auf Branch `claude/audit-repairs-20261019`

Eigener Worktree `.worktrees/claude-audit-repairs-20261019` von `origin/main` @ `be5e441`;
Hauptcheckout und Codex-Worktree unberührt, nichts gepusht oder deployt. Protokoll:
`docs/audits/2026-10-19-audit-reparaturen.md`; Einstieg für Agenten: `AGENTS.md`;
Code-Übergabe: `docs/handoffs/2026-10-20-claude-uebergabe.md`; Auftrag an Codex:
`docs/handoffs/2026-10-21-codex-auftrag.md` (Kopie `CODEX_UEBERGABE_2026-10-21.md` im Hauptcheckout).
Umgesetzt: Daily3-Mindestquote und Angebot je Auswahl (Vormerk-Gate standardmässig
aktiv, Owner-Entscheidung 20.10.2026; `BETBOY_DAILY3_RESERVATION_MINIMUM=0` schaltet ab), Mindestquote
und Preisstatus auf der gemeinsamen Karte, Shin/Power-De-Vig, Marktbenchmark Modell vs.
No-Vig-Closing (`scripts/market_benchmark_report.py`, Bericht
`docs/audits/2026-10-19-marktbenchmark.md`), Dixon-Coles-MLE als Opt-in
(`goal_model="dixon_coles"`, Default byteidentisch; Vergleich
`docs/audits/2026-10-19-dixon-coles-vergleich.md`). Tests: 529 + 395 + 580 + 274 + 19
gezielt grün (Windows); kein Linux-Volllauf. **Marktbenchmark-Ergebnis:** 14 Ligen,
33 275 Spiele mit Pinnacle-Closing, 0 von 112 Liga×Markt-Zellen schlagen den No-Vig-Markt;
Preisgate-Replay 34 484 Wetten, ROI −5,5 % [−7,2; −3,6], CLV −1,0 % [−1,2; −0,8],
Ø Modell−Markt +11 pp (Winner's Curse, Audit K2/K3). **Dixon-Coles-Vergleich:** 29 512 Spiele,
1X2 klar besser, Totals/BTTS schlechter; Varianten 20.10.: Halbwertszeit 240/365 d hilft, Niveau-Prior
nicht, Hybrid (DC Ergebnis + Legacy Tore) dominiert (56 sig. besser/32 schlechter von 560), kein Drop-in.
Mischungsgewicht Modell/Markt out-of-sample 0,00; Edge-Cap 8 pp hebt Policy auf +0,8 % ROI (KI enthält 0).
FDR über Ligen×Märkte aktiv (Engine-Gate angepasst). Rechtsfooter 18+/Spielsucht, Kundenzugang fail-closed bei
gesetztem Portal-Token (VOR DEPLOY ENV PRÜFEN, deploy/README.md). CI quick/full, Lockfiles. Tennis-Populationsfit
ohne nachweisbaren Vorteil (nur 2024 prüfbar). PR #1 auf GitHub, CI grün.
Owner am 20.10.2026: Daily3-Gate aktiv, Karte mit Mindestquote/Preisstatus bleibt. Offen:
Merge nach Codex' laufender Arbeit, Linux-Volllauf. Folgeauftrag Dixon-Coles-Niveau:
`docs/superpowers/plans/2026-10-20-dixon-coles-niveau.md`.

## 18.10.2026 – Fußball-Trainingsvertrag freigegeben; Umsetzungsplan zur Prüfung

Nutzer hat ausdrücklich bestätigt: „Spezifikation freigegeben; Umsetzungsplan
erstellen“. [Plan mit sieben testbaren Aufgaben](docs/superpowers/plans/2026-10-18-football-training-execution.md)
erstellt und gegen beide Spezifikationen selbst geprüft. Reihenfolge: kanonische
Mitgliedschaft → kompakte physische Projektion → dauerhaftes Register → echter
Zwei-Speicher-/D2-Pfad → V4-Merkmale → eingefrorener Spielerumfang → Runtime/QA/Release.
Bestehendes Unteragenten-/Review-Verfahren bleibt gewählt. Planprüfung durch Nutzer
steht noch aus; kein Produktpatch, Training, zusätzlicher API-/Sportscan, Backup
oder Aktivierung. Dokumentations-Commit/Push/VPS-Pull sind von Codefreigabe getrennt.

## 18.10.2026 – vollständiger Fußball-Trainingsauftrag: Ausführungslücke konkretisiert

Neuer Auftrag: Trainingspfad und Verletzungs-/Wetter-/Müdigkeitseffekte fertigstellen,
vorhandene/kostenlose Daten, keine Backups. Bisher **nur lesend geprüft**, kein
Produktpatch, Testlauf, API-/Sportscan oder Datenbankschreibvorgang dieses Pakets.

- Drei unabhängige Codeprüfungen bestätigen: Speicher-Schema 2 allein reicht
  nicht. Readiness/Dataset/Assembler/Fitter behalten Vollfälle; außerdem sind
  Quellen und erzeugte Trainingsartefakte derzeit an dieselbe DB gekoppelt.
- Zusätzliche konkrete Lücke: Readiness/Prepare lesen schon finale Ergebniskörper;
  im neuen Vertrag muss dies bis zur dauerhaften Testöffnung unterbleiben.
- D2 prüft bisher den ganzen Quellspeicher. Ein neues leeres Ziel darf diese
  Prüfung nicht umgehen; ein begrenzter vollständiger Quellabhängigkeitsbereich
  ist ein ausdrücklich neuer Vertrag, keine versteckte Lockerung.
- Frische VPS-Metadaten: 124 Original-Bindungen; null Artefakte der geprüften
  Dataset-/Fall-/Effekt-/Experiment-/Öffnungs-/Freigabearten und null native
  V2-Headerinventare. Höchstens 124 verschiedene Originalspiele, nicht 124
  vollständige Fälle. Das genügt noch nicht für 200 unabhängige Finalspiele
  zusätzlich zu Training/Tuning. Keine Kausalitäts-/Merkmalsqualität daraus ableiten.
  Original-Bodies wegen Mengenadmission nicht gelesen; 25.201.233-Byte-Tagesreport
  ebenfalls nicht geladen. Externe Belege: `output/football-training-20261018/`.
- Normale spätere V1/V2-Kader-/Wettererfassung ist bereits im Worker integriert;
  keine neue API oder weiterer Scanner nötig. Spätere V3-Belastung bleibt getrennt
  gesperrt, bis ihr zusätzlicher Spieler-/Eventumfang tatsächlich gebunden ist.
- [Ergänzende freigegebene Spezifikation](docs/superpowers/specs/2026-10-18-football-training-execution-design.md):
  Originalquelle read-only, genau ein kleines dauerhaftes Trainingsregister ohne
  Quellkopien, definierter Prüfbereich, sichere Testöffnung und gemeinsame eigene
  V4-Kader-/Wetter-/Belastungsprojektion. **Schriftlich freigegeben am 18.10.2026**;
  Umsetzungsplan oben zur Prüfung. Nicht als fertige Effekte oder Codefreigabe ausgeben.

## 18.10.2026 – nächste Spiele zuerst: geprüft und auf dem VPS live

- Quellcommit **`22af00bb79a444c3ba741b936f9ed2b8d00778a1`** auf GitHub main
  und am 18.10. um 09:35 CEST per geprüftem Fast-forward auf dem VPS ausgerollt.
  Offline-Chronologie-/Kontext-Smoke bestanden; nur App neu gestartet,
  PID 1236110 → 1240541. App/Caddy aktiv, beide Healthchecks `ok`.
  Acht Timer aktiv/aktiviert geprüft; Backup-Timer weiter inaktiv/deaktiviert.
  Prognose-Snapshots, neun Jobstartstempel und beide Indexowner-Hashes beim
  Deploy unverändert. Kein Backup, Scan, DB-Eingriff, Installation oder Cleanup.
  Beleg: `output/chronology-20261018/deploy-live-20261018-0935.log` außerhalb Git.

- Neueste Nutzerfreigabe: Spielblöcke überall nach vollständiger Startzeit
  aufsteigend; unbekannte/ungültige oder zeitzonenlose Termine zuletzt. Die
  bestehende Auswahl und Marktpriorität innerhalb eines Spiels bleiben erhalten.
  Alte gespeicherte Wahrscheinlichkeitssortierung darf dies nicht überschreiben.
- Kleiner Produktpatch nur in `tip_display_order.py` und `app.py`; angebunden
  sind Automatisch, eigene Suche, RisikoBet, Daily3, 15K und Live. Keine Änderung
  an Wahrscheinlichkeiten, Quoten, Einsätzen, Buchungen oder gespeicherten Tipps.
- TDD: ursprüngliche falsche Reihenfolge vor dem Patch reproduziert. Anschließend
  **167 Tests aus fünf vollständigen Modulen bestanden**. Drei neue Schutzfälle:
  alte Sortierpräferenz, Mitternacht/fehlende Zeit und fehlende Zeit am Hauptmarkt
  trotz bekanntem Spielbeginn eines weiteren Markts. Unabhängiger Quellreview
  ohne Befund. Alle bisherigen Test-IDs bleiben erhalten.
- Vollsuite vollständig: **15.560 IDs / 422 Module**, 15.459 PASS, drei FAIL,
  98 unveränderte SKIP, null Errors; 834 Dateien über 122 Kontrollpunkte stabil.
  Die drei FAIL verlangten noch die alte Wahrscheinlichkeitssortierung in
  `sports_editorial`, `manual_statistical_selection` und
  `wettfinder_statistical_leads`. Nur Reihenfolge-Erwartungen/Kommentare geändert,
  keine Fixtures, Zahlen, IDs, Slot-/Lead-/Unverändertheitsprüfungen entfernt.
  Ganze drei Module anschließend **172 PASS**, Exit 0, unabhängiger Diffreview
  ohne Befund. Alle drei ursprünglichen Fehlbelege bleiben unverändert erhalten.
- Exakter Abschlussabgleich: **15.462 PASS / 98 gleiche SKIP / 0 offene Fehler**,
  alle 15.560 aktuellen, 15.557 zuvor belegten und 15.495 ursprünglichen IDs
  enthalten. Vollsuite plus ganze Owner-Nachprüfung, **kein frisch wiederholter
  einzelner vollständig grüner Gesamtlauf**. Nur die drei Testdateien unterscheiden
  sich vom Vollsuite-Quellstand; Produktcode/übrige Tests/Config unverändert.
  Owner-Pins wurden nach dem Ownerlauf erfasst, nicht rückwirkend davor behauptet.
  Beleg: `output/chronology-20261018/owner-union-01/summary.json` außerhalb Git.
- Echte lokale Browserprüfung mit dem bestehenden Renderer und isolierten
  Testspielen: 1440×1000 und 390×844, Reihenfolge samt Datum/fehlendem Termin,
  bestehender Hauptmarkt sowie Auf-/Zuklappen nach erneutem Rendern bestanden.
  Kein horizontaler Überlauf/Browserfehler; bekannte Streamlit-iframe-Warnungen
  separat protokolliert. Erster QA-Klick auf das überdeckte native Checkboxfeld
  bleibt als Fehlbeleg erhalten; normale sichtbare Beschriftung danach bestanden.
  Headless mit bereits installiertem Playwright; keine Browserinstallation,
  keine Produktionsdaten/API-Verbindung. Eigene Vorschau danach beendet.
  Belege: `output/chronology-20261018/browser-verified-02/` außerhalb Git.
- Veröffentlichung wie oben abgeschlossen, Ausgangsbasis `b57b646`.
  Exakte Release-Allowlist: zwei Produktdateien, acht Testdateien, zwei Übergaben.
  Externe Prüfbelege/No-Backup-Deployvorbereitung: `output/chronology-20261018/`.
  Kein zusätzlicher Sport-/API-Scan, keine Sicherung, DB-Kopie oder Bereinigung.
- Diese Freigabe betrifft ausschließlich die Anzeige. Der schriftliche
  Football-Dataset-v2-Vertrag darunter wartet weiterhin auf eigene Freigabe;
  keine neue Modellwirkung oder bessere Wettqualität aus UI-Tests ableiten.

## 18.10.2026, morgens – Accountfortsetzung und echter Tageslauf geprüft

- Lokal/GitHub/VPS frisch abgeglichen: `e0816622836a7b4d4755d5b0616c09084dd9253a`.
  App/Caddy aktiv, öffentlicher Healthcheck `ok`. Regulärer Wettfinder mit neuem
  Code 03:35:31–04:09:55 CEST erfolgreich/Exit 0; letzter Shadow 07:52 erfolgreich.
  Der letzte Tennis-Volljob 00:05–00:36 nutzte noch die alte Version; neuer
  vollständiger Tennisjob weiterhin erst 19.10., 00:05 CEST, ohne Extra-Scan.
- Gespeicherter Tagesbericht: 473 Modellkandidaten. Seit dem Quellrelease 1.225
  neue Fußball-Entryquotenzeilen für 64 Events, davon 1.184 Zeilen mit nativem
  Marktanhang für 62 Events. Das ist ein Speicher-/Anschlussnachweis, noch kein
  finaler Qualitätsvergleich dieser neuen Ereignisse. Tennis: 20 neue Entry-
  zeilen für ein Event, ohne neuen nativen Marktanhang.
- Rein lesender Marktvergleich nach Tageslauf: 54 vergleichbare kategoriale
  Marktsätze aus 26 Events, darunter erstmals sechs Hockey-Closingereignisse.
  Hockey-Modell-Brier 0,224713 gegenüber Markt 0,223732; sechs Events belegen
  keinen Vorteil. Aktuelle Fußball-v14-Vergleichskohorte weiterhin acht Events,
  neue binäre `selection_groups` noch leer. Keine Wirkung/Renditefreigabe.
  Beleg: `output/source-repair-20261017/native-market-proof-02-after-daily.json`
  außerhalb Git, Exit 0, 8,344 Sekunden, keine Sport-/API-Abfrage oder DB-Änderung.
- Hockey-Unterbericht `operational_error_count=1` bedeutet hier einen
  gespeicherten `ice_hockey: source_partial`, nicht einen verschluckten Crash.
  Der Gesamtstatus trennt Teilabdeckung bewusst von `source_failed`/unavailable;
  bestehender Regressionstest verlangt dafür Exit 0. Der öffentliche Fehler ist
  absichtlich bereinigt; die ursprüngliche Einzelursache ist daraus nicht
  bewiesen. Cricket `source_unconfigured` bleibt wie freigegeben ausgenommen.
  Sieben API-Hockey-Snapshots haben 0 Trainingsspiele/keine Teamhistorie und
  deshalb keine Basiswahrscheinlichkeit; zwei NHL-Snapshots besitzen diese.
  NHL-Kontext separat mit neun gespeicherten Receipts erfolgreich. Abdeckung
  und ursprünglichen Teilfehler nicht als dieselbe bewiesene Ursache ausgeben.
- Nächster begrenzter Architekturumfang vorgeschlagen: Football-Dataset v2,
  einmaliger Quellenkatalog plus exakte Fallmitgliedschaft, physische Prüfung
  eines Falls nach dem anderen, nur kleine numerische Projektionen behalten.
  Legacy-Datasets, Modellformeln und D2-Grenzen unverändert. Richtungsfreigabe
  erhalten. [Schriftlicher Vertrag](docs/superpowers/specs/2026-10-18-football-stream-dataset-design.md)
  selbst geprüft und zur Nutzerprüfung bereit; **noch kein neuer Produktcode**.
  Zusätzlich geklärt: Ein neuer echter Real-Kohorten-D2-Lauf benötigt eine eigene
  Ausführungs-/Persistenzlösung, weil bestehende Offline-Sperren und Keine-Kopie-
  Vorgaben nicht durch den Speicherfix aufgehoben werden. Abschnitt 5 trennt
  vollständige Offline-Abnahme ausdrücklich von reiner Produktions-Leseprobe.
  Separater POINT-Tennis-Effektvertrag folgt nicht automatisch aus diesem Schritt.

## 18.10.2026 – Quellen-/Marktreparatur live; Effekte weiterhin nicht fertig

**Quellrelease `c6fe02fdce07eae1e13368e98612c8b6bf569657` ist auf main und seit
02:12:48 CEST auf dem VPS.** Fast-forward von `2f62e5e`, exakt 45 geprüfte Pfade,
Offline-Smoke erfolgreich, App-PID 1222039 → 1236110. App/Caddy aktiv und beide
Healthchecks `ok`; acht Timer aktiv/aktiviert. Prognose-Snapshots, neun
Jobstartstempel und beide rohen Index-Quelldateihashes beim Deploy unverändert.
Kein Backup, keine Migration/Installation, keine DB-Kopie, Bereinigung oder
zusätzlicher Sport-/API-Scan. Beleg außerhalb Git:
`output/source-repair-20261017/deploy-source-repair-01.txt`.

Separater alter Datenfehler, bereits **vor** dem Deploy: reguläre Shadow-Läufe
02:02/02:12 `partial`/Exit 1. Für Fixtures 1550998/1550999 fehlt eine hinreichend
frische Bet365-Quote samt Providerzeit. Zwei alte CLV-Zeilen haben ungültige
Quotenprovenienz/Abrechnungsbelege. Das ist bewusstes Fail-closed im unveränderten
Shadow-Code, kein Appabsturz; „malformed settlement“ allein beweist keine falsche
Geldabrechnung. Die enge lesende Nachprüfung ist abgeschlossen: Zeile 2,
Fixture 1528908 (Romania–Bosnia, gewonnen), und Zeile 3, Fixture 1495965
(Strommen–Sandnes, verloren), haben jeweils NULL in `closing_odds`,
`closing_bookmaker`, `closing_source`, `closing_quoted_at`. Öffnungs-, Ergebnis-
und Profitfelder passieren die übrigen bestehenden Prüfungen. Keine gültige
CLV-Aussage; damalige Schlussbelege nicht erfinden und nicht „alle Dienste
erfolgreich“ behaupten. Nur zwei Zeilen/400 Bytes Skalardaten lesend geprüft.

Nächste fachliche Schritte bleiben Mehrfall-Fußballdataset/-fitter, späterer
PLAYER_LOAD-v3-Nationalteam-/Transferumfang und eigener POINT-Tennis-Effektvertrag.
Danach ausreichender unangetasteter zeitgetrennter Modell-/Marktvergleich. Bessere
Wettqualität und numerische Verletzungs-/Wetter-/Müdigkeitswirkung sind **nicht**
belegt. Neue native Gegenpreispaare sowie der erste reguläre neue Tennisjob
(19.10., 00:05 CEST) sind noch produktiv nachzuweisen, ohne zusätzlichen Scan.

### Abgeschlossene Prüfung und frühere Vorbereitungsstände

Abschluss 02:10 CEST: Die unveränderte große Fußballrunde ist mit **381 PASS**,
null Fehlern/Skips in 3.490,58 Sekunden beendet. Zusammen mit den vollständigen
Nachtests sind **alle 15.557 aktuellen Haupt-IDs** belegt: **15.459 PASS und 98
unveränderte ursprüngliche SKIP**, keine offene Fehler-ID, alle 15.495 ursprünglichen
IDs erhalten. Das ist die exakte Zusammenführung der ursprünglichen Vollsuite
mit späteren ganzen Ownernachtests, **kein frisch wiederholter vollständig grüner
Gesamtlauf**. Der äußere Sourcepin-Wrapper bleibt wie unten dokumentiert
FAIL/INCOMPLETE; seine 103 bestandenen eigenen Fälle werden nur in ihrem geprüften
Umfang verwendet. Originalfehler und alle Nachtestbelege bleiben erhalten.
Abgleich: `output/source-repair-20261017/followup-receipt-merge-final.json`.
Unabhängiger letzter Review: alle 834 aktuellen Source-/Test-/Configdateien
bytegleich zur akzeptierten Abschluss-Collection; exakte 45-Pfad-Release-Allowlist,
sechs unveränderte Tennis-Kernmodule und beide unveränderten Indexdateien.
Source-Paket anschließend wie oben belegt committed/gepusht/ohne Backup deployed.
**Numerische Effekte nicht fertig:**
Mehrfall-Fußballtraining, zusätzlicher PLAYER_LOAD-v3-Umfang und eigener aktueller
POINT-Tennis-Effektvertrag bleiben technische Restarbeit, danach empirische Prüfung.

Zwischenstand 18.10. nach Mitternacht: regulärer Tennisjob unter dem bisherigen
Live-Commit erfolgreich (00:05:02–00:36:48 CEST, Exit 0), 72 verarbeitet/64 neu
gespeichert, `unresolved_outcome_events=0`. Kontext dennoch teilweise: 14
Identitätskonflikte, ein nativ nicht verfügbarer Fall und drei Aufgaben nach
Matchaufgabe. Das ist kein Nachweis des noch unveröffentlichten Source-Pakets.
Beleg: `output/tennis-regular-final-20261018.json` außerhalb des Repos.
Die ursprüngliche QA03 ist vollständig beendet: 15.392 PASS, 98 unveränderte
SKIP und fünf FAIL. Drei Fehler betrafen einen echten JSON-Containerunterschied
der neuen Quotenbelege, zwei die alten Ganzobjekt-Hashfixtures. Korrigiert und
alle 13 betroffenen vollständigen Module separat nachgeprüft: 439 PASS. Die
zusammengeführte Abdeckung enthält 15.402 PASS/98 gleiche SKIP, alle 15.495
ursprünglichen IDs plus fünf neue. Das ist kein vollständig wiederholter
grüner Gesamtlauf nach der Korrektur; beide Original- und Nachtestbelege bleiben
erhalten unter `output/source-repair-20261017/` außerhalb des Repos.
Der Tennisindex ist seit Rebuild-Aufruf 32 tatsächlich READY: 2.639.584
Originalzeilen abgedeckt, 1.303.491 logische Indexbytes. Aufruf 13 hatte den
2-Sekunden-Writerrahmen knapp überschritten und bleibt als FAIL dokumentiert.
Die vorhandenen Originaltabellen wurden durch den Rebuild nicht verändert.

Aktiv `.worktrees/audit-repairs-20261013`. Quellen-/Marktbasis lokal committed
als `bc6e7f2`; GitHub und VPS zuletzt bestätigt weiterhin
`2f62e5e4fe57ac233847a8dbb52e8c35584aff98`. Noch kein Push/Deployment des
neuen Pakets. Zusätzliche Tennis-Live- und Fußball-Headeranschlüsse werden
getrennt integriert und geprüft; keine entsprechende Produktionsfreigabe aus
dem alten erfolgreichen Tageslauf ableiten. Keine Sicherung, Bereinigung,
DB-Kopie oder zusätzlicher Sport-/API-Scan.

- [x] Marktvergleich erweitert: native Gegenpreise, getrennte binäre
  `selection_groups`, Doppelte Chance aus echtem vollständigem 1X2; vorhandene
  kategoriale `groups` nicht vermischen. Basketball/Hockey-Ergebnisse aus
  vorhandenem Final-Cache und kanonischem Settlement. Typ-/Byte-/Konfliktprüfung
  vor Körperlesen, einschließlich Korrektur zwischen zwei Lesern.
- [x] Fußball-Abrechnung v2 implementiert: vorhandene eigene Artefaktbytes plus
  künftige tatsächliche Schreibmengen statt jeden gelungenen Miniversuch dauerhaft
  mit 4 MiB zu belasten. Expliziter neuer Umfang, kein Zurücksetzen des alten
  Ledgers. Neue abgebrochene Versuche bleiben voll belastet. Unabhängiger Test
  fand/fixte Zukunftsdatum-Umgehung beim ersten v2-Aufruf; 24 Tests bestanden.
- [x] Kanonischer Fußballlauf teilt eine Reservierung und bestätigt tatsächlichen
  Abschluss; 156 Automations-/Quoten-/Admissiontests bestanden.
- [x] Fußball: vollständige physische Quellenrekonstruktion, kompakte Zweige,
  Schema-v2-Fall und bestehender Fitter/D2 geprüft. Native Quelle 36.111
  Belege/108.341.418 expandierte Bytes in 82,687 Sekunden bestanden. Noch keine
  numerische Kader-/Wetterwirkung: aktueller ursprünglicher Stichtag zu früh.
- [x] Tennis: expliziter verlustloser Offline-Quellenstream und Batchanschluss
  geprüft. Alte globale Fallback-FAILs bleiben erhalten; der gültige Index wird
  jetzt tatsächlich verwendet. Vier native Trainingsfälle haben den physischen
  Quellenpfad durchlaufen; kombinierter Livepfad wird separat geprüft.
- [x] Ursprüngliche Vollsuite und anschließende vollständige Quoten-Ownermodule
  abgeschlossen, siehe Zahlen oben. Runden 01/02 bleiben unvollständig erhalten.
- [x] Fußball: späteren tatsächlichen Kader-/Wetterstichtag als eigenes kompaktes
  `frozen-unresolved`-Headerinventar anbinden. Externer Owner 23 PASS, unabhängiger
  Review ohne bestätigte Blocker; canonical integriert. Neuer Owner samt echtem
  Fit/Freeze/Evaluate/Verify-D2 und Bodymanipulationsprüfung 24 PASS; vier weitere
  ganze Owner (Deferred, Opponent, Readiness, LOAD-v3) 91 PASS. Die 13 großen
  Legacy-/Seammodule abgeschlossen: 381 PASS/0 SKIP, Exit 0 in 3.490,58 Sekunden.
  Das Inventar allein bestätigt keinen Quellkörper und aktiviert keinen Effekt.
- [x] Tennis: neuer expliziter v4-Livequellenpfad ohne riesigen globalen Spool.
  191 vollständige Owner-/Nachbartests bestanden. Alle 72 echten heutigen
  Originale im begrenzten Quellen-/Feature-Replay jetzt vollständig PASS:
  870.479 tatsächliche Zeilen/930.892.969 Bytes, 72 bytegleiche Originale,
  120.207.043 Bytes Ausgabeheap unter 128 MiB, 621,740 Sekunden Wall und
  610,244 Sekunden CPU, RSS 370.968 KiB. Keine neue Wahrscheinlichkeit, Outcomes,
  API oder Veröffentlichung. Dieser Replay ersetzt nicht den vollständigen
  A1-Modellzustands-/Publikationsbesitzer; dessen eigene Tests sind separat.
  Die sieben Tennis-/Historien-/Indexbesitzer sind bytegleich zum Replay. Seine
  älteren dataset/evaluator-Ganzdateihashes bleiben korrekt abgegrenzt: spätere
  Änderungen dort betreffen ungenutzte Fußball-Seams bzw. additive Pins.
  Beide Tages-/Refreshcaller sind jetzt lokal explizit angeschlossen; neue
  echte Callertests und ganze Tages-/Refresh-/Live-Owner **338 PASS** mit dem
  bisherigen `.codex_test_venv`/Offline-Launcher, alle bisherigen 338 IDs erhalten.
  Zehn vorhandene Canonical-Tests brauchten erstmals ihre echte lokale READY-
  Indexvoraussetzung; diese wird nun explizit aufgebaut, nicht gefälscht. Die
  erste abweichende Interpreterrunde 328 PASS/10 FAIL bleibt erhalten. Weitere
  Importcaller abgeschlossen: 327 IDs, zusammengeführt 324 PASS/3 gleiche
  Windows-Symlink-Skips. Initiale 13 Temp-/Hardlink-Berechtigungsfehler vor
  Produktlogik bleiben erhalten; beide ganzen Module unverändert mit regulären
  QA-Rechten/Projekt-TEMP nachgeprüft: 60 PASS/3 SKIP, dieselben 63 IDs. Keine
  Produktkorrektur oder primitive Abschwächung dafür. Produktiv weiterhin alte
  Version, kein neuer Scan zur bloßen Bestätigung gestartet.
- [x] Gemeinsame Aktivierungs-/Consumer-/Runtime-Owner **103 PASS**, 509,32 s,
  ohne Fehler/Skip. Äußerer ursprünglicher Wrapper bleibt **FAIL/INCOMPLETE**:
  währenddessen wurden ausschließlich die zwei separat getesteten Daily-/
  Callerpfade geändert. Tatsächliche drei Owner und ihre ausgeführten Produkte
  blieben byteidentisch und rufen diese beiden Pfade nicht auf. Kein Waiver,
  keine rückwirkende Vollquellen-Behauptung. Belege `scoped-owner-summary.json`
  und `caller-exclusion-review.md` im externen `final-sourcepin-recheck-01/`.
- [x] Unabhängiger finaler Caller-/Fixture-/Quellenreview ohne neuen Produktbefund;
  bestehende Legacy/v3-/Invalidindex-Tests unverändert. Deployhelper mit exakter
  45-Pfad-Allowlist und 7 PASS; unveränderte Index-Quelldateibytes vor/nach Pull
  und Apprestart vergleichen. Keine Umgehung des READY-Vertrags.
- [x] Abschlussreview, explizite Quellpfade committen, main pushen und auf VPS
  ohne Backup/zusätzlichen Scan fast-forwarden: `c6fe02f`, beide Healthchecks `ok`.
- [ ] Numerische Effekte bleiben bis zum tatsächlichen ausreichenden zeitgetrennten
  Qualitätsnachweis offen. Quellenleser-Tests sind keine bessere Wettqualität.
  Zusätzlich fehlen technische Teile, nicht nur Wartezeit: Football-Mehrfall-
  Dataset/Fitter hält noch Vollfälle und wiederholt Quellenverweise; späterer
  PLAYER_LOAD-v3-Nationalteam-/Transferumfang ist nicht implementiert. Aktuelle
  POINT-Tennisoriginale erhalten ausdrücklich keinen alten Serve-Effekt; ihr
  eigener gemeinsamer Effektvertrag fehlt noch. Diese drei Punkte nicht als
  bloßes Sammeln weiterer Ergebnisse oder schon aktivierte Wirkung darstellen.

Abgrenzung/Byteeinheiten:
[Quellenreparatur v2](docs/audits/2026-10-17-source-repair-v2.md).
Neue vollständige native Quotensätze/Schlussbeobachtungen entstehen nur bei
regulären künftigen Abfragen; keine alten Gegenpreise erfinden. Cricket hat im
vorhandenen Zugang keinen nativen Preisadapter; Multigoal/Kombis weiterhin ohne
vollständige ausschließende native Partition nicht benchmarkfähig.
VPS lesend 17.10. 23:34/23:35 CEST: App/Caddy aktiv, öffentliche Health `ok`,
letzte reguläre Wettfinder-/Tennis-/Shadow-Dienste `success`/Exit 0, rund 22 GB frei.
Historische fehlgeschlagene einmalige Prüf-/Releasedienste bleiben unverändert.
Endgültige Collection 15.557 eindeutige Haupt-IDs; alle 15.500 der vorherigen
korrigierten Basis erhalten. Große 13-Modul-Fußballrunde abgeschlossen; die oben
belegte Zusammenführung ist weiterhin kein frisch wiederholter Vollsuite-PASS.

Nachtrag 18.10., laufend: endgültige Fußball-Ownerprüfung 26 PASS einschließlich
echtem Schema-v2-/Fitter-/Dataset-/D2-Wiederprüfpfad, Legacy-Nachbarn 31 PASS;
aktuelle native lesende Quellenprobe Exit 0/82,687 s, 36.111 Belege. Nur drei
Terminmerkmale verfügbar, keine numerischen Effekte aktiviert. Unabhängige sechs
aktuelle Paritätsfälle bestanden. Tennis endgültiger Codec-/Historienbesitzer
56 PASS, Trainings-/Batch-/Live-Nachbarn 65 PASS. Globale native Fallback-Probe
nach 600 s FAIL erhalten: 1.091.503 Belege geprüft, globale Vollständigkeit nicht
abgeschlossen. Keine Wirkung/Produktionsabnahme aus diesen Tests erfinden.

Der vorhandene Tennisindex wird jetzt durch seinen **bestehenden** begrenzten
Rebuild-Owner erneuert: gleichbleibende geprüfte Codehashes, maximal 45 Sekunden
je Aufruf/2 Sekunden je Transaktion, maximal 40 sequenzielle Aufrufe, Abbruch bei
Integritätsfehler oder drei Aufrufen ohne Fortschritt. Ausschließlich abgeleitete
7580 Mitgliedschaftszeilen/Indexstatus werden neu aufgebaut. Ein SQLite-
Schreibschutz verbietet Originaltabellenänderungen/ATTACH. Kein DDL, API, Backup
oder DB-Kopie. Tatsächliche Zwischenstände unter
`C:/Projekt/BetBoy/output/tennis-stream-index-rebuild-20261017/`.
Index jetzt READY; die früheren FAIL-Proben bleiben unverändert erhalten.
Expliziten neuen Quellen-/Livevertrag mit diesem verifizierten Index prüfen,
nicht den alten 512-/2-MiB-Vertrag als bestanden umlabeln.

Wichtig verbleibend beim Fußball: Originalstichtag liegt vor späteren Kader-/
Wetterabfragen; der neue Headeranschluss wird oben separat abgenommen. Zwei
aktuelle große vollständig expandierte Trainingsfälle überschreiten bereits
den neuen 128-MiB-Batchrahmen. Das ist **nicht** durch bloßes Warten erledigt.
Der kleinste nächste Entscheidungs-/sequenzielle Fitterpfad ist im neuen Bericht
benannt, hier nicht implementiert. Keine Aussage „alle Effekte fertig“.

## 17.10.2026 – Marktvergleich und Kontext-Datenpfad: Teilpaket live

Aktiver Checkout unverändert `.worktrees/audit-repairs-20261013`, Ausgang
`46f1fa8f6f690e15ae7045087e0bea762be79dd4`.
**Quellcommit `702f594ed22d0d6b18dff5f8946145f5f27f0898` auf main und VPS.**
No-Backup-FF am 17.10. um 21:22:44 CEST, Offline-Smoke bestanden,
App-PID 1218486 → 1222039. App/Caddy aktiv, beide Healthchecks exakt `ok`;
um 21:24 nochmals bestätigt. Prognose-Snapshots und alle neun geprüften
Jobstartstempel beim Deploy identisch. Keine Migration/zusätzlichen Scans.
Die nachfolgende Abschlussdokumentation wird separat ohne Neustart gezogen.

- [x] Tatsächlicher Marktvergleich implementiert: vollständige gleiche native
  Märkte/Buchmacher/Zeitpunkte, proportionale Margenbereinigung, getrennte
  Entry-/Closing-Kohorten und ereignisgewichtete Brier-/Log-Loss-Messung.
  Keine Auswahl-, Preisfreigabe- oder Modellwahrscheinlichkeitsänderung.
- [x] Bereits geladene Tennis-Gegenpreise unveränderlich in vorhandenen
  Quotenbelegen speichern. Keine synthetische Gegenprognose/neue Tabelle/API.
- [x] Separaten Preis-Worker an bestehende Closing-Erfassung angeschlossen;
  erster kausaler Modellstand unabhängig vom alten EV-Flag, bisherige erste
  ausführbare Revision für CLV/Rendite unverändert. Kein Entry-Backfill/Modellscan.
- [x] Identische, vollständig gebundene normale Tennis-Finals inklusive bekanntem
  Gewinner transaktional wiederverwenden. Jede Korrektur, Status-/Teilnehmer-
  Änderung und unbekannte Gewinnerlage erhalten; keine alten Zeilen gelöscht.
  Ohne ursprünglichen Ergebnisbeleg greift diese Optimierung ausdrücklich nicht.
- [x] Gezielt Quoten-/Markt-Nachbarn 393 PASS, Tennis-Pakete 236 PASS;
  unabhängige Reviews ohne verbleibende P1/P2 im begrenzten Paket. Zahlen
  überlappen und sind kein addierter Vollsuite-Nachweis.
- [x] Gesamtabdeckung verifiziert: **15.280 PASS, 98 identische SKIP,
  147 bestandene Untertests**; alle 15.318 vorherigen IDs plus 60 neue erhalten.
  Jede der 15.378 aktuellen Haupt-IDs genau einmal im zusammengeführten JUnit.
  Der ursprüngliche vollständige Lauf unter `output/context-effects-20261017/
  full-qa-01/` bleibt mit seinen 19 FAIL und Exitcodes `[0,1,1,1]` erhalten:
  14 Subprozess-Timeouts, ein Prozess ohne JSON, ein Lock-Zeitlimit und drei
  korrekt als veraltet abgelehnte, bei Collection erzeugte Testquoten.
  Nur die Testdatei `tests/test_bet_finder_ui.py` wurde danach korrigiert:
  Ausführungsuhr statt Collection-Uhr, identische Quote für Provenienz sowie
  ein neuer RED→GREEN-Regressionsfall. Kein Produkt-TTL/Limit gelockert.
  Alle fünf betroffenen vollständigen Module danach sequenziell **521 PASS,
  3 gleiche SKIP**, ohne weitere Produktänderung. Die ursprünglichen Prozess-
  und Lock-Fehler reproduzierten sich dort nicht; ihre historische Ursache ist
  nicht als allgemeiner Speicher-/CPU-Mangel bewiesen. Maßgeblicher Abschluss:
  `C:/Projekt/BetBoy/output/context-effects-20261017/verification-summary.json`.
- [x] Explizit committen/main pushen, No-Backup-VPS-FF und Betriebsprüfung.
- [x] Echten Produktions-Marktbericht am 17.10. um 19:23:25 UTC rein lesend erzeugt:
  56.162 Entry-Beobachtungen, null Closing-Beobachtungen, 48 vergleichbare
  Marktgruppen aus 20 einzigartigen Fußballspielen. v13: N=10/Brier 0,114133 gegenüber
  Markt 0,134223; aktuelle v14: N=8/0,129125 gegenüber 0,138586; v12: N=2/0,059302
  gegenüber 0,045494. Keine robuste Qualitäts-/Rendite-/Effektfreigabe aus dieser
  kleinen gemischten Abdeckung; bisher keine vergleichbaren Tennis-Gegenpaare.
  Tatsächlicher JSON-Beleg außerhalb Git:
  `C:/Projekt/BetBoy/output/context-effects-20261017/production-market-comparison-702f594.json`.
  Neue native Gegenpreise/Closing-Erfassung müssen sich in regulären künftigen
  Läufen noch produktiv belegen; dafür wurde kein zusätzlicher Scan gestartet.

**Nicht abgeschlossen: numerische Verletzungs-, Wetter- und Müdigkeitseffekte.**
Frisch produktiv geprüft: Fußball 115 Original-Bindings, davon nur acht vollständige
Spiele; sieben davon scheitern am bestehenden 4-MiB-Quellenpool. Die Original-
Erfassung steht seit 15.10. am 128-MiB-Lebenszeit-Reservierungslimit. Einfach
weitersammeln funktioniert deshalb nicht. Es fehlen keine bloßen Textlabels.
Tennis hat 1.000 native passende Finals älterer gemischter Generationen, aber
nur 52 aktuelle POINT-Joint-Artefakte und weiterhin blockierte tatsächliche
Merkmalsrekonstruktion. Keine Effekte aktiviert oder Zahlen erfunden.
Konkrete Befunde und die verbleibende verlustfreie Quellen-/Budgetreparatur:
[Kontext-Abnahmebereitschaft](docs/audits/2026-10-17-context-activation-readiness.md).
[Paketabgrenzung](docs/audits/2026-10-17-market-context-release.md).

Weitere Marktvergleichs-Abnahme bleibt offen: kein Benchmark für sämtliche
öffentlichen Tipps. Doppelte Chance/Multigoal/überlappende Kombinationen und
Hockey/Basketball sind nicht abgedeckt. Fußball benötigt vollständige konsistente
Original-Märkte; Closing bezeichnet nur die letzte tatsächlich beobachtete Quote
in der letzten Stunde. Der Drei-Stunden-Quotenjob garantiert diese Fenster nicht.
Aus fehlender Abdeckung folgt weder „guter“ noch „schlechter“ Tipp.

Regulärer Shadow am 17.10. um 21:22:16 CEST erfolgreich/Exit 0, noch vor dem Deploy;
Quotenjob 21:15:28 → 21:15:36 ebenfalls erfolgreich. Der ältere 18:12-UTC-Lauf war
partial/Exit 1. App/MainPID 1222039 seit dem gezielten Neustart, keine zusätzlichen
Sport-/API-Scans, Sicherungen, Bereinigungen oder Datenbankkopien durchgeführt.
Die älteren Abschnitte unten behalten ihre datierten Nachweise.

## 17.10.2026 – Reparaturpaket live, tatsächlicher Endstand

**Quellcommit `e8a32b83d6c0510adb798ab3c96c4a63704a4d5d` auf main und VPS.**
No-Backup-Fast-Forward am17.10. um19:52:50CEST; Offline-Smoke bestanden,
App-PID1215661→1218486. Beide Healthchecks exakt`ok`, App/Caddy aktiv.
Prognose-Snapshots und Startstempel aller neun geprüften Dienste beim Deploy
unverändert. Kein Backup, keine Migration, kein zusätzlicher Sportscan.
Neue Schlüssel im laufenden App-Prozess mit Environment und INI identisch;
nur Ja/Nein ausgegeben. Abschlussdokumentation danach separat ohne Neustart.

- [x] Reparaturquellen explizit committed/gepusht/deployed; fremde Logs und
  `output/audit-repairs/` erhalten/uncommitted. Gesamt-QA15.220PASS/98identische
  SKIP/147Untertests mit den unten exakt dokumentierten Owner-Rechecks.
- [x] Produktions-Kernansicht1440/390px mit geladenen Spielblöcken und sichtbarer
  Quotenquelle/Zeit geprüft, mobil kein horizontalerÜberlauf. Keine relevanten
  App-/Seitenfehler beobachtet; zehn Ressourcenfehler waren absichtlich
  blockierte externe Bilder/Icons. Vollständige produktive Navigation/
  Accordion-/5–10-Abnahme bleibt INCOMPLETE wegen DOM-Rerun/Zeitgrenze.
  Diese Interaktionen wurden separat im echten isolierten Renderer bestanden.
- [x] Aktuelle Produktionsdaten nur lesend gezählt: Forecast-Evidence87.320
  Zeilen/1.444verschiedeneSportereignisse,5.306Ergebniszeilen,56.162Entry-
  Quoten, **0Closing-Quoten**. Fußball779verschiedeneEreignisse. Das sind
  keine87.320unabhängigenTests und keine Renditebelege. DBca419MiB.
  Tennis2.429Prognosen/6.495Revisionen, **0beidseitigeEntry-/Closingpaare**.
  Lokale Leerbestände aus vorherigen Abschnitten sind nicht aktuellerVPS-Stand.
- [ ] Nächste fachliche Priorität: diese vorhandenen Produktions-Entrydaten
  zeit-/quell-/marktgebunden auswerten und fehlende vollständige Preisgruppen/
  Closings gezielt schließen; keine Marktwahrscheinlichkeit aus Einzelseiten
  erfinden. Kein neuer Pflicht-EV-Block oder Marktblend ohne Produktentscheidung.
- [ ] Offen bleiben die in der79-ID-Matrix konkret benannten Modell-/Kontext-
  und Launchschulden. **Nicht alle79Punkte behoben, keine bessere Rendite belegt.**
  Torzeitmärkte sind weiterhin nur spezifiziert, kein stiller Produktivcode.

Abschlussbelege außerhalbGit unter `C:/Projekt/BetBoy/output/claude-recheck-20261017/`:
`final-summary-02.json`, `deploy-01.txt`, `ui-production-01/acceptance-status.txt`.
Der Abschnitt „Release vorbereitet“ direkt darunter ist damit historisch.

## 17.10.2026 – Fortsetzung nach Accountwechsel: QA abgeschlossen, Release vorbereitet

Dieser Abschnitt ersetzt den Übergabestatus18:25 direkt darunter.

- [x] Bestehende vier Volltestgruppen vollständig beendet und gelesen. Original:
  15.219PASS/1FAIL/98SKIP plus147 bestandene Untertests. Einziger Fehler war die
  alte CSS-Testforderung nach `white-space:nowrap` am absichtlich vergrößerten
  Bildnachweis; kein verschwiegenes Modell-/Buchhaltungsproblem.
- [x] Nur diese Test-Erwartung auf lesbare12px und begrenzten Umbruch korrigiert,
  gesamtes Besitzermodul106PASS erneut geprüft. Produktionsquellen seit Voll-
  suite bytegleich. Expliziter kombinierter Endnachweis: **15.220PASS,98 gleiche
  Skips,147 Untertests**,15.318 eindeutige Fälle, alle15.233 vorigen Fälle plus85neue.
  UrsprünglicherFAIL/B-Exit1 bleiben erhalten. Nicht „vier ursprüngliche Exit0“ behaupten.
- [x] Voriger Auto-ID-Reorder bei Multigoal sauber aufgelöst: maßgebliche alte
  id-collection statt überholter Collection. Keine Fälle entfernt/umetikettiert.
- [x] Echter Renderer mit synthetischen Daten bei1440/390/320px:12pxLabels,
  unveränderte Wappen, keine Überläufe, Haupt-/Nebenmarkt, Quelle/Zeit und
  Maus-/Tastatur5/10-Umschaltung. Kein Benutzerbrowser übernommen.
- [x] VPS vor Release weiterhin4f2af4e, App/Caddy/Health ok,8Timer geplant,
 21GiB frei. Regulärer Shadowlauf19:42 erfolgreich, Exit0 (kein zusätzlich gestarteter Lauf).
- [x] Neuer No-Backup-Releasehelfer mit exakter31-Pfadliste, neun Jobzuständen,
  ruhigem Timerfenster, deaktivierten Git-Hooks, Offline-Smoke und exakten
  Health/PID/Snapshot-/Scanstart-Prüfungen. Bash-Syntax und lokaler Smoke geprüft.
- [ ] Reparaturquellen explizit committen/main pushen und No-Backup-VPS-FF,
  App-Neustart, SHA-/Health-/Umgebungsabgleich. Noch kein Releaseerfolg behauptet.
- [ ] Frische produktive Browserprüfung nach Deployment; Rendererprüfung allein
  ersetzt diese nicht. Bessere Wettqualität/alle79Befunde weiterhin nicht behaupten.

Endbelege: `C:/Projekt/BetBoy/output/claude-recheck-20261017/final-summary-02.json`
(zusätzlich AST-identische leere EOF-Zeile entfernt,11erWatch-Owner erneut grün),
`shield-recheck.xml`, `ui-closeout-01/summary.json`. Untenstehender18:25-Laufstatus
ist historisch. Alle fremden WIP/debug.log/output bleiben erhalten.

## 17.10.2026 – beide Claude-Audits: frische Gegenprüfung und Reparatur

**Accountwechsel auf Nutzerwunsch, Stand 18:25 Europe/Zurich.** Code eingefroren,
vier Testprozesse laufen noch. Nicht neu implementieren oder parallel eine
zweite Vollsuite starten. Es gibt noch keinen Codecommit/Deploy dieser Runde.
Eine separate Dokumentationsübergabe ist kein Code-Release.

### Nächster Account: genaue Fortsetzung

1. Aktiver Checkout und Belege wie unten. Laufende Sessions: A28077/B72753/
   C74874/D78656. IDs können accountübergreifend ungültig sein; maßgeblich sind
   `full-qa-02/full-A.log` bis `full-D.log`, jeweilige Result-JSONs und JUnit-XMLs.
   Um18:25 alle vier noch laufend, kein gemeldeter Test-Assertion-Fehler.
   A enthält ausschließlich den langen `test_football_readiness_scale.py`;
   wenige Punkte allein sind kein Beleg für Stillstand. PC laufen lassen.
2. Nach vier Exit0 den bestehenden Runner `output/market-selection-20261017/full_qa.py`
   mit Argument `report` starten, Environment `BETBOY_SELECTION_QA_RUN` auf
   `C:/Projekt/BetBoy/output/claude-recheck-20261017/full-qa-02` setzen.
   Interpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe`.
   Zusätzlich alle15.233 Vorläufer-IDs aus `multigoal-quotes-20261017/full-qa-02/collection.log`
   gegen15.318 aktuelle IDs abgleichen, nicht nur gegen die alte14.680-Basis.
   Quellenhashes/Skip-IDs prüfen; CJS-Fontprobe separat hashen.
3. Gezielt grün: UX592, Mathematik437, Daily3-Modul20, Cache33, Watch/Caller34.
   Tennisbreitlauf588PASS+12Sandbox-Hardlinkfehler/3Skips; beide unveränderten
   betroffenen Module nativ24PASS/3Skips. Überlappende Zahlen nicht addieren.
   Unabhängige Gesamt-/Cache-Reviews ohne verbleibenden wichtigen Patchbefund.
4. Eigene29 Code-/Test-/Doc-Dateien explizit prüfen/stagen, nie `git add -A`.
   `debug.log` entstand durch Tests; `output/audit-repairs/` ist geerbter
   ungetrackter Bestand. Weder committen noch pauschal löschen. Vor Push echte
   private Ersatzschlüssel gegen den Index prüfen, ohne Werte auszugeben.
5. Erst danach Sourcecommit/main-Push und neu geprüftes No-Backup-Deployskript.
   VPS-Basis `4f2af4e8e6e8a2eb4b92d94d12b7fc219611caf9`. Alter Helfer
   `output/multigoal-quotes-20261017/deploy-quotes.sh` hat falsche Basis/Dateiliste;
   nicht unverändert ausführen. `update_server.sh` erstellt Backups: ungeeignet
   ohne gezielte Anpassung. Ruhiges Timerfenster, FF auf exakten Zielcommit,
   Offline-Smoke, App-Neustart, beide Healthchecks und SHA/Snapshot/Scanstart-Abgleich.
   Keine Migration, Backups oder zusätzlichen Sport-/Modellscans.
6. Neue vollständige Produktions-Browserprüfung steht noch aus. Tatsächlichen
   Abschluss und Restlücken dokumentieren, nicht alle79Befunde als behoben melden.

Letzter gelesener Shadowlauf18:12: Exit1/partial, zwei fehlende Quoten bei zwei
zurückgestellten Kandidaten; keine Schlüssel-Fehlerkategorie mehr. Kein App-
Absturz, aber auch kein bestätigter fehlerfreier Shadowlauf. Acht Timer geplant,
21GiB frei. API-Konfiguration neuer als VPS-Code; App-Env-Aktivierung erst Neustart.
Lokale Marktdatensuche fand keinen vollständigen kausalen Fußball-Gegenpreis-
Datensatz. Das ist keine neue VPS-Datenprüfung; alte Summary vom13.10 nicht
als aktuelle Rohdaten behandeln. Erst aktuelle Produktionsabdeckung lesend prüfen.

Dieser Abschnitt ist aktuell; ältere Freigaben darunter sind historische
Nachweise. Nutzerauftrag: beide Audits abgleichen, offene Fehler beheben,
testen, main-Push/VPS, ausdrücklich **keine neuen Backups**.

- [x] Beide vollständigen Berichte gelesen, alle **79 IDs** einzeln eingeordnet:
  `docs/audits/2026-10-17-claude-gegenpruefung.md`. Nicht alle Empfehlungen sind
  heutige Fehler; Preisgates/Marktblend/Bottomnav/Backup teils durch spätere
  ausdrückliche Nutzerregeln überholt. Offene Modellschulden nicht als fertig markiert.
- [x] Alle drei bekannten exponierten API-Schlüssel laut Nutzer erneuert;
  gegen Git-Expositionen verschieden. Lokale ignorierte INI/Streamlit-Datei
  und beide VPS-Secretdateien ersetzt, fremde Einstellungen erhalten.
  API-Football/football-data/OpenWeather je genau einmal HTTP200/akzeptiert.
  Werte nie ausgegeben oder in Git aufgenommen; keine Sicherung. App-Umgebung
  wird erst durch den Release-Neustart neu geladen. Alte Provider-Widerrufe
  sind nicht unabhängig durch diesen Authentifizierungsnachweis belegt.
- [x] Sichtbarer Hauptmarkt/Fallback nach exakter nativer Quell-/Teilnehmer-/
  Modellrevision und vorhandenem statistischen Rang, nicht nach Prozentwert
  oder Quotenhöhe. Entfernte Richtung nicht als prominenter Ersatz wiederbelebt.
- [x] Quotenherkunft ohne Hover, Zürcher UI-Zeiten, neutrale alte Quellen,
  Live „Berechnet“, fünf wichtige kleine Labels >=12px in echtem Chromium.
- [x] Tennis-Wächter/Formatvertrag korrigiert. Fehlende v2-Originale heißt
  unavailable, nicht stabil; Wochenreport macht daraus weder Drift noch
  Produktionszertifizierung. Tatsächlicher v2-Wächter bleibt mangels Original-
  /Anchor-Anbindung unvollständig. Awarded nicht normal abgerechnet.
- [x] Explizite Nicht-FT-Endstände abgewehrt, alte statuslose Originalreplays
  erhalten. Separate rein lesende Projektions-Residualdiagnostik, keine neue
  Kalibrierungsvariante/Gates/Originalfelder. Daily3-Kalender statt ISO-Text,
  keine geratene Sommerzeitstunde. Legacy-Pickle-Lesen/-Schreiben an bestehende
  lokale Dateivertrauensgrenze angeschlossen, **keine** Signatur behauptet.
- [x] Unabhängiges Gesamt- und separates Cache-Review ohne verbleibenden
  wichtigen Befund im jeweiligen Patch. Echter Wochenreport-Folgefehler und
  Security-Helfer-INI/Env-Kanten zuvor reproduziert/behoben; Belege erhalten.
- [ ] Finaler vollständiger Testlauf `output/claude-recheck-20261017/full-qa-02`
  läuft: **15.318 eingesammelte Fälle**, vier native Offline-Gruppen. Noch
  kein Pass. Der unterbrochene erste Zwischenlauf ist INCOMPLETE, nicht grün.
- [ ] Nur nach erfolgreicher Endprüfung gezielt committen, main pushen und
  No-Backup-Fast-Forward auf VPS, Offline-Smoke/Neustart/Healthchecks.
  VPS-Code bei letzter Prüfung weiterhin `4f2af4e` (API-Konfiguration neuer).
- [ ] Keine bessere Wettqualität belegt: produktionsgleiche Kalibrierung,
  Gegnerstärke-/Unsicherheitsmodelle, echte Verletzungs-/Wetter-/Müdigkeitseffekte,
  vollständige kausale Gegen-/Closingpreise und Markt-/Renditenachweis offen.
- [ ] Weitere offene Software-/Launchschulden bleiben vollständig in der
  79-ID-Matrix: Live-/manuelle Teamsportpfade, einzelne Formate/Zeitlogik,
  CI/Lock/Linux-Gesamtabnahme, persistente manuelle Scanworker, Geldübersicht/
  Währungsentscheidung, Kundenzugang/korrekte Rechtsangaben vor bezahltem Start.

Gezielte QA außerhalb Git: `C:/Projekt/BetBoy/output/claude-recheck-20261017/`.
Keine Sport-/Modellscans, Datenmigrationen, Backups oder pauschale Bereinigung.
Torzeit-/15/30/60/75-Minuten-Auftrag darunter bleibt ein **separates** Paket.

## 17.10.2026 – neuer Auftrag: Torzeit-Profil und Zeitmärkte

Nutzer hat 15-/30-/60-/75-Minuten-Gesamt-/Team-Tore und BTTS samt historischer
Prüfung, exakten Quoten, Tests/main/VPS freigegeben; ausdrücklich keine Backups.
Architektur-Erweiterung, kein bloßer weiterer 90-Minuten-Markt. Schriftlicher
Entwurf: `docs/superpowers/specs/2026-10-17-football-time-markets-design.md`.
Funktionsfreigabe liegt vor; schriftliche Spezifikation/Umsetzungsplan noch
nicht freigegeben. Bisher nur Quellenprüfung und drei begrenzte API-Diagnosen,
kein Produktivcode, kein historischer Backfill, kein Modell-/Sportscan.

- [x] Existierende Endstände/Platzverweisfälle nicht als vollständige Torzeit-
  Historie missverstanden; validierte FT-0:0 können ohne Ereignisabruf zählen.
- [x] Echte Zeitquote belegt: native 144, William Hill, „Goal in 1-15 minutes“
  mit Yes/No in zwei vollständigen Spielantworten. Anbieterzeiten beibehalten.
- [ ] Exakte kumulative Gesamt-/Team-/BTTS-Preise für 30/60/75 nachweisen.
  Separate Abschnitts-, Halbzeit- oder Ergebnisquoten nicht dafür verwenden.
- [ ] Schriftliche Spezifikation prüfen/freigeben, danach Implementierungsplan.
- [ ] Implementierung/chronologische historische Prüfung/Regression/UI-QA/Release.

Belege: `C:/Projekt/BetBoy/output/time-markets-20261017/capability-01.json`.
Die zuvor bestätigte Auswahl-/Darstellungslücke bei verstecktem Hauptmarkt
bleibt separat offen; neue Zeitmärkte allein beheben sie nicht.

## 17.10.2026 – bezahlte Multigoal-Quoten gezielt geprüft

Aktiver Zusatzauftrag: echte fehlende Angebote von Abruffehlern unterscheiden;
kostenlose Zusatzquelle nur bei nachgewiesener exakter Abdeckung. Kein Backup,
kein zusätzlicher Sport-/Modellscan. Kanonischer Worktree unverändert,
Ausgangscommit lokal/GitHub/main/VPS `6ff4d260`.

- [x] Aktiver bezahlter API-Football-Zugang verifiziert. 14 begrenzte echte
  Status-/Katalog-/Quotenanfragen, normale Budgetbuchung, keine Schlüsselausgabe.
- [x] Drei vollständige native Spielantworten und fünf gültige Datum-/Markt-
  Abfragen: keine passenden 1–3-/1–4-/2–4-Gesamt-/Teamangebote. Ungültige
  Abfragen ohne Datum/Spiel ausdrücklich nicht als Abwesenheitsnachweis gezählt.
- [x] Tatsächliches zusätzliches Angebot gefunden: Roma–Genoa, Bet365,
  native349 „2 or 3 goals“ zu2,00, Anbieterstand09:18:17UTC. Nicht mit einem
  vorhandenen anderen Bereich verwechseln; vorheriger Katalog hatte 95 Märkte.
- [x] Echter Fetchfehler reproduziert/repariert: Folgeseiten wurden ignoriert.
  Jetzt höchstens20 native Seiten/Spiel innerhalb vorhandener Budget-/Zeitgrenzen,
  gemeinsamer Parser, unveränderte genaue Markt-/Anstoß-/Buchmacherbindung.
- [x] Teilfehler/kaputte Seitencontainer beweisen keine Markt-Abwesenheit.
  Gültige Angebote bleiben erhalten; begrenzte Diagnosefakten bleiben gespeichert.
- [x] Unabhängiges Review fand Seiten-Uhrkante; mit echten RED-Fällen behoben.
  Spätere fremde Angebote erneuern keine früheren Quoten. Re-Review ohne P1/P2.
- [x] 407 betroffene Tests vor der letzten Uhr-/Container-Erweiterung bestanden;
  zusätzlich final350 fokussierte Tests grün (Agent; nachgelagerter Sandbox-
  Temp-Cleanup-Fehler bei Exit0 dokumentiert, nicht als Produktfehler versteckt).
- [x] Vollständiger nativer Offline-Endstand: 15.135 PASS, 98 identische Skips,
  vier Gruppen mit Exit 0. Alle 15.076 bisherigen IDs und 157 zusätzliche Fälle
  im Endabgleich genau einmal enthalten; 810 Quell-/Fixture- und drei Shell-Hashes.
  Fünf automatisch nummerierte Test-IDs waren durch neue Parameter verschoben:
  nur deren Reihenfolge korrigiert, vollständiges Besitzermodul erneut 41 PASS;
  exakte Rücktransformation rekonstruiert den vollständig getesteten Dateihash.
  Produktionsquellen unverändert. Erster Zwischenlauf 15.119 bleibt INCOMPLETE.
- [x] Quellcommit `113744d6fa964de29644826465eba1c56dcc797a` auf main gepusht
  und am 17.10.2026 um 16:53:41 CEST per geprüftem Fast-Forward auf VPS deployed.
  Offline-Smoke: 96 Märkte, unveränderte 40 Fit-Ziele, exakte 2–3-Wahrscheinlichkeit,
  native 349 auf Seite 2 und historische gemeinsame Treffer bestätigt.
  App-PID 1211028→1215661; App/Caddy aktiv, beide Healthchecks `ok`.
  Beide Prognose-Snapshot-Hashes und alle fünf Scan-/Quoten-Startstempel während
  des Deployments identisch. Kein Backup, zusätzlicher Scan oder Migration.
  Dieser abschließende Nachweis wird separat dokumentiert und per Docs-only-Pull
  veröffentlicht; dabei kein weiterer App-Neustart.
- [x] Kostenlose Alternativen geprüft: keine verfügbare, exakt nachgewiesene
  Bereichsquelle; deshalb kein erfundener/spekulativer Zusatzadapter.
- [x] Nutzerfreigabe für Bereiche/Sieg-Torbereich-Statistik übernommen.
  TOTAL_RANGE_2_3 ergänzt:96 Runtime/46 Torprojektionen, bisherige90/40/v14
  und sämtliche bisherigen95 Wahrscheinlichkeiten/Abrechnungen bleiben gleich.
  Neuer Markt wird separat validiert; alte95-Nachweise nicht als96 ausgegeben.
- [x] Native349 „2 or 3 goals“ exakt angebunden; kein disjunktes „1 or 3“,
  keine Über/Unter-/Halbzeit-/Teamquote als Gesamtbereich umetikettiert.
- [x] Kompakte historische5/10-Treffer für Gesamtbereiche1–3/1–4/2–3/2–4
  und jeweiliger Team-Sieg plus Bereich: gemeinsame Treffer gezählt, nicht
  Einzelhäufigkeiten multipliziert. Keine neue Modellchance daraus behauptet.
  Gemeinsam in normalen Karten, Daily3,15K und manueller Suche; nur einmal/Spiel.
- [x] RisikoBet: eigene snapshotgebundene DISPLAY_ONLY-Zähler, keine Rate-/Rank-
  Wirkung, kein Prosa-Parsen, kein JSON im Kundentext. Altstände ohne strukturierte
  Daten werden nicht umgeschrieben; neue Faktoren erst im regulären Lauf.
- [x] Zusammengeführte21-Modul-Integration748PASS/Exit0. Registry211PASS+6
  Untertests nativ; vorausgegangene11 Sandbox-Berechtigungsfehler erhalten.
- [x] Unabhängige Registry-/Parser-/UI-/RisikoBet-Reviews ohne offenen Blocker.
  Zusätzlich manuellen Mehrfachblock mit echtem RED8→GREEN4 korrigiert.
- [x] Echte Renderer mit isolierten TESTDATEN bei1280/390/320px im vorhandenen
  Headless-Playwright geprüft: normale Karten und RisikoBet,5/10 per Maus/Tastatur,
  keine Console-/Pagefehler/Überläufe. Kein Benutzerbrowser übernommen.
  Das ist Renderer-QA, kein vollständiger Produktions-Streamlit-Nachweis.

Nur der tatsächlich bepreiste2–3-Bereich wird als neue Modell-Marktdefinition
ergänzt. Sieg/Bereich-Kombinationen stehen als beobachtete Spielstatistik da;
ohne belegten exakten Anbieterpreis wird daraus kein zusätzlicher Tipp.
Neue2–3-Prognosen entstehen beim nächsten regulären Modelllauf oder einer
bewusst gestarteten manuellen Suche; keine zusätzlichen Scans dafür gestartet.

Echte Preisuntergrenze1,20 und statistische Auswahl bleiben unverändert;
keine künstliche Marktvielfalt und kein Renditeversprechen durch Softwaretests.
[Befunde und Abschlussnachweise](docs/audits/2026-10-17-multigoal-quotenabruf.md).
Receipts außerhalbGit: `C:/Projekt/BetBoy/output/multigoal-quotes-20261017/`.

## 17.10.2026 – statistische Auswahl vor Sortierung, Multigoal

Aktiver Auftrag: alle unterstützten Fußballmärkte korrekt prüfen/auswählen,
danach sortieren; testen, main pushen, VPS deployen, **keine Backups**.
Kanonisch weiterhin `.worktrees/audit-repairs-20261013`, Basis `6c106d56`.

- [x] Verlust der modalen Resultatrichtung gegen breitere Doppelte Chance im
  echten gespeicherten Ilves-Lauf und unabhängig offline reproduziert.
- [x] Statistische Marktgüte statt roher Trefferchance für marktübergreifende
  Auswahl; ein statistischer Hauptmarkt je Spiel vor Anzeige-/Preisfiltern.
- [x]95 Runtime-Märkte einschließlich Gesamt-/Team-Multigoal; alte90 Originale,
  Kalibrierung und Tickets behalten ihre unveränderten Verträge.
- [x] Separater95-Katalog für Cache/Discovery; keine Modellversions-Umetikettierung.
- [x] Manuelle Suche und15K behalten den vollständigen Kandidatenpool bis zur
  gemeinsamen Auswahl; kein Ersatz-Haupttipp durch einen anderen Preis.
- [x] Vollständiger nativer Offline-Testbestand mehrstufig geprüft:14978PASS,
 98 unveränderte Skips, alle14680 alten IDs erhalten,396 neue Fälle. Alle15076
  IDs sind im Endaggregat genau einmal enthalten;806 Quell-/Fixture-Hashes.
  572PASS/8Skips im vollständigen Drei-Modul-Nachlauf des einen Helperpins.
  Unabhängige Schlussreviews ohne offenen Blocker.
- [x] Quellcommit`725ccc28e9949528be53ca4c1d41396bfa397408` aufmain gepusht
  und17.10. um10:42CEST per Fast-Forward aufVPS deployed. Offline-Smoke und beide
  Healthchecks`ok`; App-PID1200874→1211028. Kein Backup, Scan oder Migration.
- [x] Echter gespeicherter Katalog:486 gelesene Prognosen,237 sichtbare Karten
  aus64 Spielen, alle exakt bepreist>=1,20. Hauptmärkte nach Statistikkriterium:
  18Resultat,17Teamtore,12DC,10Teamecken,5Team-Multigoal,2Resultat+Tore,2Gesamttore.
  Sichtbare Hauptmärkte darunter7Resultat/9DC/10Teamtore/10Teamecken/2Gesamttore;
  nicht bepreiste Hauptmärkte werden nicht durch andere Richtungen ersetzt.
- [x] Interner Browser: Seitenwechsel, Ilves öffnen/schließen, Roma-Heimsieg
  als Hauptmarkt58,3% vor den78,9%-Nebenmärkten und echte Quote1,58 geprüft.
  Keine neuen Browserfehler nach dem App-Neustart; gespeicherte Dateien unverändert.

Quotenprobe heute: API-Football kennt186/223, liefert aber in beiden begrenzten
Tagesproben keine echten Bereichsangebote. Nicht mit anderen Märkten ersetzen.
Öffentliche Tipps weiterhin nur mit exakt passender Quote ab1,20. Keine weiteren
Scans/Backups/Cleanups. NHL-Personal-/Kontexteffekte bleiben separat offen.
Neue fünf Marktprojektionen entstehen erst bei regulärer Neuberechnung;
bestehende alte90-Prognosen wurden nicht umgeschrieben. Der unabhängige
Nur-Lese-Prozess brauchte1,5GiB virtuellen Adressraum (408MiB tatsächliche
Spitze); die anfängliche640MiB-Testgrenze scheiterte vor JSON-Auswertung.
Keine App-/Server-Speichergrenze wurde verändert.
Details: [Auswahlbericht](docs/audits/2026-10-17-marktauswahl.md).

## 16.10.2026 – NHL-Erfassungsanschluss live, noch kein vollständiges Personalmodell

Kanonisch `.worktrees/audit-repairs-20261013`, Ausgangscommit `cc93663`.
Aktueller Nutzerauftrag: NHL zuerst, Tests/Commit/main/VPS, **kein Backup**.

- [x] Echter nativer NHL-Boxscore-Adapter und platzsparender bestehender
  B1-Speicher: native IDs, historische Goalie-Starts/Saves/Schüsse, Eiszeiten,
  Schichten, echte Empfangszeit, REG/OT/SO-Unterscheidung. Kein neuer Datenspeicher.
- [x] Zwei begrenzte echte kostenlose Quellenproben; kleine ausdrücklich
  unvollständige echte Testfixture eingecheckt, keine API-Football-Anfragen.
- [x] Opt-in an den fälligen Produktions-Tageslauf; dieselben entdeckten Spiele
  und geladenen Resultate, maximal32 native Abrufe/UTC-Tag und1MiB neue Belege
  je Aufruf. Keine Karten-/Importabfrage, keine zweite Sportsuche.
- [x] Erste unabhängige Source-Prüfung PASS; OT-Restzeitgrenze300Sekunden in
  der regulären Saison korrigiert, Playoffs bleiben getrennt.
- [x] Zweite unabhängige Prüfung: UTC-Tageslimit bei nicht-UTC-Testuhr korrigiert,
  echtes Speicher-RED2→GREEN2;438 Anschluss-/Nachbartests grün, Re-Review PASS.
- [x] NHL-Nachtfenster korrigiert:03:35-Tageslauf berücksichtigt native nächste
  Nacht bis24 verstrichene Stunden. Durch Suche/Modell/Katalog/gespeicherten Leser
  geprüft; andere Sportarten/manuelle Tagesgrenzen unverändert.23 neue Fälle,
 503 angrenzende Tests grün. Unabhängiges Produkt-Code-Review PASS.
- [x] Zweistufige vollständige Offline-Prüfung:14.680 Fälle, alle14.536 früheren
  IDs erhalten. Initiale Windows-Sandbox-FAILs unverändert dokumentiert; ganze
  betroffene Module plus drei zusätzliche Hardlink-Skips nativ mit identischem
  Code nachgeprüft:1.465PASS/21 bestehende Skips/85 Untertests/Exit0.
  Aggregat **14.582PASS/98 unveränderte Skips**, alle12 Abdeckungsprüfungen wahr,
  797 Quell-/Fixture-Hashes unverändert. Kein Test/keine Assertion entfernt.
- [x] Unabhängige Produkt-/Deploy-Code-Prüfung PASS. Drei fehleroffene Git-
  Inventarabfragen im externen No-Backup-Helfer RED6→GREEN10 korrigiert;
  Dokumenten-Pull separat drei Offline-Prüfungen PASS, ebenfalls reviewed.
- [x] Code **bd035b71cf02368b21b72bd4ef2e765329769e8e** committed, auf GitHub
  main gepusht und auf dem VPS per Fast-Forward gezogen. Offline-Smoke PASS,
  App-PID1198478→1200874; App/Caddy aktiv, beide Healthchecks `ok`.
- [x] Erster Deploy stoppte nach dem Git-Pull vor dem App-Neustart: Der externe
  Smoke-Helfer übergab Inhaltsdaten statt eines vollständigen Empfangsbelegs.
  Korrigiert mit der echten Fixture-Empfangszeit, kein Produktcodefehler/-umbau.
  Regression RED→GREEN und begrenzte Resume-Prüfung unabhängig PASS;18 Helfer-
  Tests nativ PASS. Originaler FAIL und erfolgreicher Resume bleiben erhalten:
  `deploy-nhl-01.log` / `deploy-nhl-02.log` im unten genannten Ausgabepfad.
- [x] Wettfinder-/RisikoBet-Snapshotfingerprints vor/nach Neustart unverändert.
  Kein neuer Sportscan, Backup, DB-Kopie, Migration, Cleanup oder Paketinstallation.
  Backup-Timer disabled/inactive; acht bestehende andere Timer geplant. Acht alte
  fehlgeschlagene September-Prüfdienste bleiben als historische Belege erhalten;
  sie sind keine neuen NHL-Laufabbrüche und wurden nicht zurückgesetzt.
- [ ] Erster tatsächlicher regulärer NHL-Erfassungslauf nach Veröffentlichung:
  **17.10.2026 03:35 Europe/Zurich**. Deploy-Smoke ist kein Produktions-Sportlauf;
  dessen Quellenzähler und Ergebnis sind noch nicht nachgewiesen. Nicht extra starten.
- [ ] **Voller NHL-Modelleffekt weiterhin offen:** Vorab-Ausfall-/Starterquelle,
  owning Training/Fallbau/Replay/Verlustprüfung und D1/D2-Abnahme fehlen.
  Ganze Spiel-Eiszeiten sind keine vollständigen Manpower-Intervalle. Historischer
  Starter ist kein bestätigter nächster Starter. Kein erfundener Müdigkeitsabschlag.

Eine frühe isolierte QA schrieb zwei synthetische `NHL-context`-Abrufreservierungen
in die ignorierte lokale Worktree-Historien-DB. Keine Ergebnisrevision, B1-Daten,
VPS- oder Geldänderung. Ursache explizite Pfadbindung korrigiert; lokale Belege
bewusst nicht gelöscht. Details und Prüfverweise:
[NHL-Erfassungsbericht](docs/audits/2026-10-16-nhl-source-intake.md).

## 16.10.2026 – Quellen-/QA-Reparaturen live; voller Hockey-Kontext bleibt offen

Nutzer verlangt vollständigen Fünf-Ligen-Ausbau, historische Prüfung, Tests,
Commit/main-Push/VPS-Deploy ohne Backups und plant zwölf Monate API-Zugang.

- [x] Offizielle API-Hockey-v1.0.1-Felder geprüft:15 Endpunkte, **keine**
  dokumentierten Spieler-/Aufstellungs-/Verletzungs-/Starttorhüter-Endpunkte.
  `games/events` hat Ereignisnamen, keine vollständigen Spieler-Eiszeiten.
  Ein Jahresabo ist kein Nachweis dieser fehlenden Funktionen; Nutzer vor Kauf
  ausdrücklich darauf hingewiesen. Keine Bestellung/Accountänderung.
- [x] Drei Alternativen anhand Primärquellen geprüft: kein vollständig belegter
  All-5-Feed für Vorab-Goalies/Ausfälle. Sportradar Global unterscheidet `starter`
  nicht von `played`; Goalserve nennt DEL/Schweiz ohne LiveStats/Lineups;
  SportsDataIO-Injury-/Starterdokumentation betrifft NHL, nicht alle fünf.
- [x] Nutzer bestätigt: API-Hockey-Abo **noch nicht aktiviert**. Empfehlung:
  mit der Jahresbindung warten, weil sie die fehlenden Personalendpunkte nicht
  ergänzt. Keine Buchung veranlasst; Quellenkorrektur ist davon unabhängig.
- [x] Unabhängig sinnvolle Quellenkorrektur lokal committed **433bb86**:
  Default native NHL plus NationalLeague/SHL/Liiga/DEL; Historie nur benötigte
  native Liga/Saisonpaare; explizit leere/ungültige Scopes ohne Abrufausweitung;
  fehlende Katalogziele intern teilweise statt falsches erfolgreiches Nullergebnis.
- [x] Release-Review fand reproduzierten Mapping-Runner-Fehler: dessen Brücke
  verlor `run.errors`. Korrektur lokal committed **1d3ca7a**, sechs neue echte
  Verbraucherfälle: RED2FAIL/4PASS, GREEN6PASS. Abschließende angrenzende QA
  **757PASS/1 bestehender Windows-Skip**. Insgesamt37 neue Fälle; kein alter
  Test entfernt. No-Backup-Deploy-Allowlist und fehlersichere Git-Inventarprüfung
  mit drei Offline-Gegentests geprüft. Unabhängiges begrenztes Re-Review PASS.
- [x] Ganze QA`full-qa-02` auf1d3ca7a fertig: **14.299 PASS/98 bestehende
  Skips/147 bestandene Untertests, aber102 FAIL**, beide Shards Exit1.
  14.499 gesammelt, alle14.462 alten IDs erhalten. Kein grüner Vollnachweis.
  Erste QA`full-qa-01` bleibt separat bewusst INCOMPLETE; alle Receipts erhalten.
- [x] Fehlerursachen getrennt:43 Update-/Inventar-/Pin-Fälle nach Hinzunahme
  des Quotendiensts;59 ältere Verbraucherfälle erwarteten unbepreiste Tipps
  oder reichten vorhandene Preisbelege nicht an Karten weiter. Keine neue
  Hockey-Modellrechnung dafür verantwortlich. Keine Preisregel zurückgenommen.
- [x] Updatepfad jetzt mit exaktem Acht-Dienste-Inventar einschließlich Quotes;
  unbekannte/fehlende/ersetzte Dienste abgewiesen. Historische Algorithmus-Pins
  durch Rekonstruktion nur des geprüften Deltas erhalten, nicht blind erneuert.
  **512 PASS/6 bestehende Plattform-Skips** in allen drei betroffenen Modulen.
- [x] Verbraucherfixtures verwenden für Kontext-/Richtungsprüfungen echte exakt
  gebundene aktuelle Testquoten. Alle bisherigen IDs/Kernassertionen behalten;
  zwölf zusätzliche Gegenrichtungs- und zwei echte Tennis-Preisgrenzenfälle.
  221 Kontext-/Preisprüfungen und137 weitere Verbraucher-/Preisprüfungen PASS.
- [x] Unabhängiges Review dieses zusätzlichen Reparaturdeltas ohne offene
  Critical/Important-Befunde. Ganze Offline-QA`full-qa-03` fertig:
  **14.438 PASS/98 unveränderte Skips/147 bestandene Untertests, beide Exit0**.
  14.536 gesammelt; keine der14.499 IDs aus QA02 entfernt; alle14.462 früheren
  IDs erhalten.787 Quellstände durchgehend unverändert, keine neuen Skips.
  Bestehender No-Backup-Helper erlaubt nur explizit geprüfte Pfade;
  dessen zusätzliche Gate-Prüfung RED1/3PASS zu GREEN4PASS erhalten.
- [x] Codecommit **42a5ae3cdedea0766440c9ce81c6dd62b59ee615** samt433bb86/
  1d3ca7a auf GitHub main gepusht und VPS per Fast-Forward gezogen.
  Offline-Import mit nativer NHL plus genau vier API-Ligen erfolgreich;
  App-PID1189206→1198478, App/Caddy aktiv, interner/öffentlicher Healthcheck ok.
  Wettfinder-/RisikoBet-Fingerprints vor/nach Neustart exakt identisch.
  Keine Modell-/Preis-/Geldwerte geändert, kein zusätzlicher Sportscan, kein
  Backup, keine Datenbankkopie, keine Bereinigung oder Paketinstallation.
- [x] Erster Deploy hielt nach erfolgreichem Git-Pull vor dem Neustart an:
  Smoke-Prozess erbte ein für betboy nicht lesbares Ubuntu-Arbeitsverzeichnis.
  Prüf-Arbeitsverzeichnis explizit auf App gesetzt; Fortsetzung erlaubte nur
  den bereits gepullten exakten Zielcommit, behielt alle übrigen Grenzen und
  endete Exit0. Beide Receipts bleiben erhalten:deploy-source-01.log (FAIL),
  deploy-source-02.log (PASS) außerhalb Git. Zusätzlicher harmloser Einzeilen-
  Diagnoseaufruf scheiterte an Shell-Quoting; keine Produktivwirkung daraus.
- [x] Der zuvor separat beobachtete Football-Shadow-Fehlstatus war schon im
  regulären Lauf21:22CEST vor diesem Deploy wieder success/inactive. Diesen
  Erfolg nicht der Hockey-Korrektur zuschreiben; kein Shadow-Lauf gestartet.
  Backup-Timer weiter disabled/inactive, rund22GB frei; keine Bereinigung nötig.
- Diese abschließende Dokumentation ist ein separater reiner Docs-Commit:
  für deren Pull kein App-Neustart nötig. Produktquellen bleiben exakt auf
  dem vollständig getesteten Code von42a5ae3; keine Tests mehr im Hintergrund.
- [ ] **Voller Hockey-Kontext nicht fertig:** reale Goalies/Ausfälle/Eiszeiten
  sowie owning Trainings-/Replay-/Abnahmepfad fehlen weiterhin. Quellenfix und
  historische Grundmodell-Stichprobe ersetzen das nicht. Keine Effekte erfinden.

Details: [API-Abdeckung](docs/audits/2026-10-16-hockey-quellen-und-api-abo.md).
Neuer Anbieter-Gegenvergleich: SportsDataIO NHL mit bestätigten Startern;
BALLDONTLIE NHL GOAT USD39,99/Monat mit Verletzungen/TOI, aber ohne belegten
bestätigten Starterfeed; Enetpulse Premium für vier der fünf Ligen, Schweizer
National League nicht Premium. Kein vollständiger All-5-Ersatz verifiziert,
keine Anmeldung/Probe mit Folgekosten/Bestellung ausgelöst.
Arbeitsprotokoll/Brief/Implementerbericht unter
`.superpowers/sdd/2026-09-07-kontext-c-weitere-sportarten/`.

## 16.10.2026 – historische Hockey-Stichprobe auf neuen Nutzerwunsch

- [x] Nutzer erlaubt ausdrücklich alte Daten2022/2023 für eine rückblickende
  Stichprobe. Über vorhandenen Zugang sechs kontingentgesteuerte Abrufe:
  3.239 Spiele der Saison2023/24, nur2.066.388Bytes lokal; keine Bilder.
- [x] Vor Ergebnislauf eingefroren:20 Termine je Liga im Januar2024, getrennte
  frühere Trainingssätze abNovember2023 und48h-Embargo. Unveränderte vorhandene
  Poisson-/Gegnerstärke-/OT-Mathematik; keine rückdatierten Empfangszeiten.
- [x] Ergebnis: **62/100 richtig**, immerHeimsieg51/100. NHL15/20,
  NationalLeague13/20, SHL11/20, Liiga13/20, DEL10/20. DEL schlechter als
  Heimsieg-Basis12/20; kleine Stichprobe nicht als Liga-Rangliste verkaufen.
- [x] Festes Modell>=70%-Segment18/23richtig; keine nachträgliche neue Tippregel.
  Brier0,229629vs0,251900; keine historischen Quoten und daher keine Rendite.
- [x] Acht Offline-Schutztests inklusive realem Ziel-/Zukunfts-Leckagetest PASS.
- [x] Unabhängige Gegenprüfung von100 Ziel-/Ergebnisbindungen, Quell-/Modellhashes,
  früheren Trainingssätzen und Kennzahlen ohne kritischen Befund.
- [ ] Vollständiger Fünf-Ligen-Kontextausbau bleibt offen: Historische
  Grundmodell-Treffer prüfen keine echten Goalie-/Ausfall-/Müdigkeitseffekte.

Keine Produktivmodelle, Historien oder Geldbuchungen geändert; normale sechs
API-Budgetreservierungen, kein zusätzlicher automatischer Lauf/Deploy/Backup.
Bericht: [Historische Stichprobe](docs/audits/2026-10-16-hockey-historische-stichprobe.md).

## 16.10.2026 – ursprüngliche Hockey-Top-5-Ausgangsprüfung vor Quellenpatch

NHL, National League, SHL, Liiga, DEL mit Gegnerstärke, Form, Torhütern,
Ausfällen und Belastung; nur vorhandene/kostenlose Quellen, keine Backups.

- [x] Code- und Quellenprüfung sowie frische Ausgangsregression:
  1.046 PASS/ein bestehender Skip/71,56 s/Exit0. Keine neue Effektfreigabe.
- [x] Produktionscache nur lesend gezählt: NHL1.528 Ereignisse2025/26 und151
  für2026/27; keine API-Hockey-Ergebnisrevisionen in diesem Cache.
- [x] Konto geprüft: API-Hockey Free100/Tag; aktueller Tagesplan funktioniert,
  geprüfte Schweizer Saisonhistorie2026 wird mit `plan` verweigert.
- [ ] Kostenlose aktuelle Historien-/Starter-/Ausfallabdeckung und zulässigen
  privaten/öffentlichen Quellenumfang für alle fünf Ligen vervollständigen.
  Technisch erreichbare offizielle Statistik ist keine pauschale Produktlizenz.
- [ ] Echte Quellenadapter und vollständigen Hockey-Trainings-/Outcome-/Replay-/
  Evaluationspfad implementieren; numerische Wirkungen zeitgetrennt abnehmen.
  Gegnerbereinigung besteht bereits; Form/Goalies/Ausfälle/Belastung sind nicht
  durch die jetzige Prüfung zusätzlich produktiv geworden.
- [ ] Erst die abgenommene Implementierung committen, main pushen und ohne
  Backup deployen. Kein neuer Hockey-Code oder Deploy in dieser Prüfung.

Details und Quellen: [Top-5-Hockey-Prüfung](docs/audits/2026-10-16-hockey-top5-daten-und-modell.md).
Damals geprüfter Produktstand `084d8d3`; keine zusätzlichen Dienste, bezahlten Zugänge,
Sicherungen, Datenbankkopien oder Bereinigungen.

## 16.10.2026 – Quotenaktualisierung und verbindliche 1,20-Untergrenze

Aktueller begrenzter Reparaturauftrag: testen, committen, main pushen und auf
dem VPS veröffentlichen, **ohne neues Backup**. Diese neue ausdrückliche Regel
ersetzt frühere Anforderungen, unbepreiste Modell-Auswahlen öffentlich zu zeigen.

- [x] Öffentliche Tipps in Wettfinder, eigener Suche, Tennis, Daily3, 15K,
  RisikoBet und den gemeinsamen Karten brauchen eine echte, exakt zugeordnete
  Anbieterquote **ab 1,20**. Nicht passende, fehlende, ungültige oder abgelaufene
  Preisbelege bleiben im Modellbestand, aber nicht als öffentliche Tipps.
- [x] Modellrichtung und Widerspruchsprüfung kommen vor der Preiszulassung;
  kein billiger/unbepreister Hauptausgang wird durch seine Gegenseite ersetzt.
  Quoten über der Grenze verändern weder Wahrscheinlichkeit noch Reihenfolge.
- [x] Auch offene manuelle Suchergebnisse und beide 15K-Darstellungen übernehmen
  den neuesten exakt passenden Preisbeleg. Neuer niedriger Preis schlägt alten
  höheren; gleichzeitige widersprüchliche Belege werden nicht wiederbelebt.
- [x] Begrenzter Quotenlauf alle drei Stunden, unabhängig vom täglichen Modelllauf:
  gespeicherten Spielbestand wiederverwenden; vorhandene Kontingentsteuerung,
  Quellen-Caches, Zeitlimits, Dateisperre und konkurrierende Veröffentlichungen
  berücksichtigen. Keine neue Sport-/Modellsuche, Datenbank oder Sicherung.
- [x] Kandidatenbezogene sichere Diagnose unterscheidet fehlendes Spiel, Markt,
  Auswahl, Identitätsfehler, Anbieterzeit, Kontingent und Transportfehler.
  Keine Schlüssel, kompletten Anbieterantworten oder Fehler-URLs speichern.
- [x] Neue tatsächliche Wetten unter der Grenze abweisen; alte echte Verträge
  bleiben lesbar, idempotent wiederholbar und normal abrechenbar. Live ohne
  exakt passenden Livepreis bleibt Analyse, ohne neue Tipp-/Geldaktion.
- [x] Unabhängiges Produktreview: keine offenen Befunde; Sitzungs-Refresh und
  fälschliches OBSERVED bei verworfener Zeitbindung korrigiert und nachgeprüft.
- [x] Finale betroffene Offline-Regression:2.493 PASS/7 bestehende Skips/
  32 bestandene Untertests, Exit0. Alle14.350 alten Test-IDs erhalten,
  jetzt14.462 gesammelt;786 relevante Quellhashes während QA unverändert.
  Komplette14K-Vollsuite für diesen Patch nicht erneut ausgeführt.
- [x] Codecommit`aab9fb2` auf main gepusht und per Fast-Forward auf VPS live.
  Reiner Preisjob16:55:49–16:56:00CEST abgeschlossen, Exit0:123 Quoten,
  0 Abruf-/Betriebsfehler.32 Fußball-Preisfixtures,2 Tennis ohne passende
  Angebote,14 Team-Sport-Zielzeilen; kein fälliger E-Sport-Bestand.
- [x] Echte Abnahme:118 unveränderte gespeicherte Modelle,54 öffentliche
  Wettfinder-Auswahlen, kleinste echte Quote1,20. Dinamo HOME_OVER_0_5 mit
  Bestquote1,11/drei Anbietern gespeichert und öffentlich verborgen.
  Beide Vorher-Fingerprints von Modell und RisikoBet ausdrücklich gegen
  Nachher geprüft:identisch. Keine Modellzeit oder Wahrscheinlichkeit erneuert.
- [x] Weitere echte Verbraucherprüfung:Daily3 eine Auswahl mit1,58; RisikoBet
  36 Szenarien mit kleinster tatsächlich gebundener Quote1,42. Interner Browser
  nach Reload:Wettfinder1,22, Daily3 1,58,15K1,32/1,21/1,28; RisikoBet lädt.
  Keine Geld-, Reserve-, Speicher- oder Abrechnungsaktion betätigt.
- [x] App/Caddy aktiv, beide Healthchecks ok; Quoten-Timer aktiv/aktiviert,
  nächster Termin18:15CEST, danachalle3h. Backup-Timer weiter deaktiviert;
  kein neues Backup, keine neue Datenbank und keine Bereinigung erstellt.
  Historische Fehlreceipts und bekannte separate Shadow-Probleme nicht gelöscht
  oder als gelöst umgedeutet.

Konkreter Originalfall: Dinamo Bucuresti – FC Botosani, Fixture1565271,
HOME_OVER_0_5. Ein gezielter vorhandener API-Football-Abruf lieferte tatsächlich
1,07–1,11 bei drei Anbietern, nicht die nutzerseitig genannten1,01. Alle liegen
unter1,20. Die Originalantwort vom Morgen wurde nicht archiviert; ihre damalige
fehlende Speicherung kann daher nicht nachträglich exakt rekonstruiert werden.
Der abgeschlossene reine Preisrefresh bestätigt Bestquote1,11 und Ausblendung.

Abgrenzung: Verletzungs-/Müdigkeits-/Wetterqualität und Marktvergleich sind damit
nicht nachgewiesen; Schlüsselrotation bleibt ausdrücklich zurückgestellt.
Vorherige vollständige14K-QA ist historisch, kein Vollsuite-Nachweis dieses Patches.
Details: [Quoten-Audit](docs/audits/2026-10-16-quotenaktualisierung.md).

## 16.10.2026 – API-Schlüsselrotation auf Nutzerwunsch zurückgestellt

- [ ] Die drei historisch veröffentlichten Schlüssel bei API-Football,
  football-data.org und OpenWeather erneuern, aktive lokale/VPS-Konfigurationen
  auf die Ersatzschlüssel umstellen und alte Schlüssel beim Anbieter widerrufen.
  **Vorerst ausdrücklich zurückgestellt:** BetBoy wird nach Nutzerangabe aktuell
  nur persönlich verwendet. Nicht als erledigt oder sicher markiert; die Rotation
  soll die weitere Arbeit am Marktvergleich jetzt nicht blockieren.
- Die private Ersatzdatei wurde geprüft: alle drei Felder sind gefüllt, enthalten
  aber noch dieselben Werte wie die historischen Git-Versionen. Keine Werte in
  diese Dokumentation übernehmen; nichts davon wurde neu auf den VPS übertragen.
- Rest-Risiko: Persönliche App-Nutzung verhindert nicht, dass veröffentlichte
  Schlüssel von Dritten zum Verbrauch des API-Kontingents verwendet werden.
- Keine Schlüssel, Anbieter-Abos, Zugriffsregeln oder Serverkonfigurationen
  geändert. Marktvergleich bleibt beauftragt; keine neue Quoten-/Tippsperre aus
  dieser Zurückstellung ableiten. Vor einem Kundenzugang erneut aufgreifen.

## 16.10.2026 – Wahrscheinlichkeitssortierung geprüft und live

- [x] Indexcode `c110d8e` lokal vollständig geprüft:14.239 PASS/98 unveränderte
  Skips/147 Untertests, alle14.337IDs erhalten; Fast-Forward auf main/VPS.
  Nur kompatible Vorbereitung, kein abgeschlossener Index-Release.
- [x] Index vollständig aufgebaut:2.616.120Belege, ready,1.256.552 logische
  Bytes/1.429.504 physische Tabellenseitenbytes. Originaldaten geschützt.
- [ ] **Nativer Vier-Fall-Nachweis FAIL0/4/Exit1:** gewählter historischer
  Payloadumfang11.589.186Bytes überschreitet2MiB/Fall und8MiB gesamt.
  Keine Quelle/Fälle/Belegrevisionen/Grenzen still ändern. Native Testdauer
  2,410s ist kein erfolgreicher Merkmalsnachweis.
- [x] Vorgesehener Fehlerfall ausgeführt: Index ausdrücklich deaktiviert,
  kompatibler Code behalten; keine alte schemaunverträgliche Version einspielen.
  Originalzahlen seit Resume unverändert; alle79 alten Finanzdateien unverändert,
  zusätzlich eine neue Sitzungsdatei separat ausgewiesen. Beide Healthchecks ok.
- [x] Neu ausdrücklich freigegeben: Modelltipps innerhalb eines Spiels und
  Spielblöcke überall nach Modellwahrscheinlichkeit absteigend; bei Gleichstand
  echte Startzeit/stabile Ordnung. Keine Quoten-/Modell-/Auswahländerung.
- [x] Sortierpatch `0859468` auf Arbeitsbranch committed/gepusht,395 gezielte
  Tests/13 neue IDs, unabhängiges Review ohne Befunde. Daily3-Anzeige sortiert,
  echte zeitliche Einsatzfolge und nächste ausführbare Auswahl unverändert.
- [x] Ganze Sortier-QA01 tatsächlich beendet: **14.250 PASS, 2 FAIL,
  98 unveränderte Skips, 147 Untertests**. Alle 14.350 IDs genau einmal,
  771 Quellhashes, Root-WIP und 45 frühere Receipts unverändert. Kein Vollpass.
- [x] Zwei unabhängig eingegrenzte Prüfadapter mit `7fea742` korrigiert: Der isolierte
  Navigations-Namespace muss die real vorhandene Sortierfunktion importieren;
  der Prematch-Test darf den bewusst entfernten Startzeitumschalter nicht mehr
  verlangen. Nur zwei Testdateien, keine Produktänderung oder gelockerten
  Navigations-/Quoten-/Berechtigungsassertionen. 432/432 betroffene Tests und
  alle bisherigen IDs erhalten, alle Produktquellen byte-identisch zu0859468.
- [x] Begrenztes unabhängiges Nachreview ohne Befunde; Produktquellen,
  Berechtigungen, Navigation und quotenunabhängige Sichtbarkeit unverändert.
- [x] QA02 am unveränderten `8c36095` vollständig PASS: **14.252 bestanden,
  98 identische Skips, 147 bestandene Untertests**, beide tatsächlichen Exits0.
  Alle14.350IDs genau einmal,771Quellhashes/RootWIP/118frühereReceipts unverändert.
  Finale Reconciliation07:56:17UTC bestätigt; QA01 bleibt historischer FAIL.
- [x] Produktivstand `38f73ed` nach Vollsuite-PASS auf main gepusht und per
  Fast-Forward auf VPS live; nur App-Neustart PID1159516→1175628. Offlineimport,
  numerische Quellenfamilie und weiterhin deaktivierter Index bestätigt;
  gespeicherte Wettfinder-/RisikoBet-Modell-JSONs byte-identisch.
- [x] App/Caddy und sieben Timer aktiv und aktiviert, Backup-Timer deaktiviert,
  beide Healthchecks ok. Das ist keine Behauptung fehlerfreier Shadow-Daten.
- [x] Interner Browser: frischer Reload, erste3 Spielmaxima85,7/84,1/81,3%,
  alle22 darin sichtbaren Märkte absteigend; alter Reihenfolgeumschalter weg,
  Spielblock geschlossen/geöffnet, Daily3 aus Seitenkarte geöffnet und zurück.
  Null neue Konsolenwarnungen/-fehler. Daily3 hatte nur1Livekarte; Mehrkarten-
  Ordnung und unveränderte Einsatzautorität sind softwareseitig geprüft.
  Kein Live-Mobilnachweis, nicht sämtliche eingeklappten Spiele einzeln geöffnet.
- [ ] Separat neu geprüft16.10.09:32CEST: Fußball-Shadow Exit1/partial,
  Fixture1622791 ohne frische Bet365-Quote mit Providerzeit; zusätzlich zwei
  historische Abrechnungszeilen mit invalid_quote_provenance/malformed_settlement.
  App/Caddy und beide Healthchecks ok; sieben Timer geplant, aber nicht alle
  letzten Jobstatus grün. Keine Quoten/Abrechnungen nacherfinden, kein Reset/
  Zusatzscan und keine Produktänderung während der Sortier-Vollprüfung.

Keine neuen Sicherungen, Datenbankkopien, Bereinigungen, manuellen Sport-/API-
Scans oder numerischen Effektfreigaben. [Index-Abnahme](docs/audits/2026-10-15-tennis-spielerindex-abnahme.md).
Die Benfica-Erstkarte war technische Marktfolge, keine begründete Hauptempfehlung;
die neue ausdrücklich gewünschte Wahrscheinlichkeitssortierung ist davon
getrennt getestet. Marktbezogene Begründung/Modellqualität bleiben eigene Themen.

Fortsetzung: Sortier-QA unter `C:/Projekt/BetBoy/output/probability-order-20261016/qa-final-02`,
Quelle `.worktrees/audit-repairs-20261013`, Branch `codex/audit-repairs-20261013`.
Keine abgeschlossenen Indexaufgaben/Reviews neu starten; Task6 bleibt wegen des
echten Eingabebudget-FAIL offen. Beide Freezes sind vollständig erfasst und beendet.
Abschließende Synchronisierung ausschließlich dieser vier Markdown-Dokumente
per Fast-Forward, ohne App-Neustart oder Produktänderung; finaler HEAD und
unveränderte App-PID werden im separaten Abschluss-Receipt festgehalten.
Produktbytes entsprechen weiterhin der geprüften QA02-Quelle8c36095. Kein
Index-Neuversuch oder numerischer Effekt-PASS daraus. Vollständige Belege unter
output/probability-order-20261016.

## 16.10.2026 00:11 – Prüfadapter korrigiert und unabhängig geprüft

- [x] `e717936`: ausschließlich Prüfadapter, zwei exakte historische DATA-
  Fixtures/LF-Einträge und zusätzliche Negativtests; Produktquellen unverändert.
  Ursprüngliche 3 Fehler RED reproduziert, danach 17/17 GREEN. Ein isolierter
  No-BEGIN-Gegentest scheitert am echten Snapshot-Verhalten, nicht am Testaufbau.
- [x] Eingefrorene Nachbarprüfung im regulären Windows-Berechtigungskontext:
  **238 bestanden, dieselben 9 Skips**, alle 233 alten IDs und 14 neue Fälle.
  Vorheriger Sandbox-FAIL mit 13 Dateiverknüpfungsfehlern und einer unveränderten
  Zeitgrenze bleibt dokumentiert. Kein Limit/Pin/Schutzassertion gelockert.
- [x] Unabhängiges begrenztes Review: Spezifikation und Qualität PASS, keine
  Critical-/Important-/Minor-Befunde. 1.102 Original-Produktowner hash-identisch.
- [ ] Jetzt frische vollständige Abnahme `qa-final-03`; alle 14.323 QA02-IDs,
  ältere Baselines und genau dieselben 98 Skip-Identitäten erhalten. Keine
  Quelle/HEAD während des neuen eingefrorenen Laufs verändern.
- [ ] Main-/VPS-Release, abgeleiteter Aufbau und echter unveränderter nativer
  4/4-/45-s-Nachweis weiterhin erst nach erfolgreicher Gesamtabnahme.

QA02 bleibt ein abgeschlossener FAIL, nicht nachträglich grün. `main`/VPS bleiben
`4ece002`. Keine neue API-/Sportabfrage, Sicherung, Produktionsdatenbankkopie,
Bereinigung, numerische Effektfreigabe oder Änderung an Tickets/Geldbewegungen.

## 15.10.2026 23:46 – vollständige QA02 mit drei Testadapter-Fehlern

- [x] Beide eingefrorenen Läufe vollständig beendet: **14.222 bestanden,
  98 unveränderte Skips, 3 Fehler, 147 bestandene Untertests**. Alle 14.323
  gesammelten Haupt-IDs genau einmal; keine entfernten/doppelten/neuen Skips.
  HEAD `41e6a69`; alle 769 Quellhashes und Root-WIP-Hashes unverändert.
- [x] Ursachen unabhängig rein lesend eingegrenzt: SQLite-Test injiziert neben
  dem neuen Verbindungs-Untertyp einen zweiten `factory`-Parameter; die native
  Manifest-Fixture reicht aktuelle Receipt-Owner statt ihrer unverändert
  eingefrorenen historischen Quellbytes ein.
- [ ] Task 6: ausschließlich diese Prüfadapter anpassen, Schutz-Assertions/
  historische Pins/Produktquellen unverändert lassen; gezielt RED/GREEN und
  unabhängig prüfen. Danach neue eingefrorene Vollsuite in frischem Verzeichnis.
- [ ] Kompatibler Main-/VPS-Deploy, expliziter Indexaufbau und unveränderter
  echter 4/4-/45-s-Nachweis bleiben blockiert, bis die Abnahme besteht.

Kein vollständiger Test-PASS. GitHub `main` und VPS weiterhin `4ece002`;
Code-Arbeitsbranch `41e6a69`. Keine Produktionsänderung, Sicherung, Datenbankkopie,
Bereinigung oder zusätzliche Sport-/API-Abfrage. QA01-Unterbrechungen und QA02-
Fehlerbelege erhalten; keine Wiederholung schon abgeschlossener Aufgaben 1–5.

## 15.10.2026 – Umsetzungsplan freigegeben, Ausführung begonnen

- [x] Nutzerfreigabe: „Umsetzungsplan freigegeben“; keine weitere Designrunde erforderlich.
- [x] Bestehende isolierte Arbeitskopie/Branch bestätigt; Root-WIP und alte Ausgaben unangetastet.
- [x] Vor Änderungen offline 14.160 eindeutige Tests gesammelt (47,95 s, Exit 0):
  alle ursprünglichen 14.133 QA04-IDs plus sämtliche 27 Task-23-IDs enthalten.
- [x] Task 1 Schema/Projektion mit TDD und unabhängigem Review abgeschlossen:
  `26b8f64` und `0d2849e`. Reviewfund Content-REPLACE-Invalidierung geschlossen;
  finale gezielte Schema-/Transportprüfung 44 PASS. Früherer Nachbarlauf 108 PASS
  plus ein Windows-ACL-Fall, separat auf identischem Code erfolgreich geprüft.
- [x] Task 2 fortsetzbarer Aufbau/CLI geprüft: `83f6c72`/`e872e39`, finale
  gezielte Prüfung 72 PASS; COMMIT-Restbudget und TEXT-Payload-Vorabprüfung korrigiert.
- [x] Task 3 normaler Schreibweg atomar angebunden: `5cdcfe2`, 250 PASS,
  unabhängiges Review ohne Befunde. Bekannter ungültiger Index wird nicht repariert/
  freigegeben; Zusatzbudgetfehler bewahren gültige Originalbelege.
- [x] Task 4 private v2-Kopien/Inventur: `3279be4`, finale gezielte Nachbarprüfung
  344 PASS; unabhängiges Review ohne Befunde. Jede Spielerzuordnung bleibt in der
  Kopie unverändert, genau eine Kontrollzeile wird gegen das Originalledger geprüft.
- [x] Task 5 tatsächlicher Leser: `7351b9d`, 174 gezielte Tests bestanden,
  unabhängiges Review ohne Befunde. Gleiche Stichtage und Belegmengen wie beim
  Einzelpfad; Fallgrenzen gelten bereits vor dem Lesen der Mitgliedschaftsbelege.
  Der echte schreibgeschützte Zugriff ist geprüft; kein stiller Legacy-Fallback.
- [ ] Task 6: Vollsuite, vollständiges Branch-Review, nativer Vier-Fall-Nachweis
  und koordinierte Produktionsumstellung weiterhin offen. Vorher kein Main-Release.

Abschlussreview: Ein zu spät begrenzter Kontrollwert-Leser wurde mit `c3e25a1`
korrigiert; 163 gezielte Tests bestanden, begrenztes unabhängiges Nachreview ohne
Befunde. Schema/Trigger unverändert. Damit ist das Source-Review abgeschlossen,
aber **noch keine Vollsuite-/Produktionsfreigabe** erteilt.
`qa-final-01`: 14.280 IDs gesammelt, alle alten IDs erhalten; beide laufenden
Shards nach dem Reviewfund gezielt abgebrochen. Kein Test-PASS daraus, keine JUnits.
Frische Vollabnahme ausschließlich unter `output/tennis-player-index-20261015/qa-final-02`.

Verbindlicher Wiederaufnahmeort:
`.superpowers/sdd/2026-10-15-tennis-spielerindex-umsetzung/progress.md`.
Keine neuen APIs, Sportscans, Backups, Datenbankkopien oder Bereinigungen.
Noch kein Leistungs-/Produktionsabschluss und keine neuen numerischen Kontexteffekte.
Zusätzliche Benfica/Celtic-Diagnose abgeschlossen:
`docs/audits/2026-10-15-benfica-hauptkarte.md`. X2 steht in der großen ersten Karte
wegen technischer Marktkennzeichen-Reihenfolge bei gleichem Spielbeginn, nicht
wegen nachgewiesener Haupttippqualität. Kein Markt dieses Spiels ist hervorgehoben.
Offen: Darstellung/marktbezogene Erklärung korrigieren; kein Fußball-Fix aus einer
bloßen Vermutung. 53,3 % X2 sind rechnerisch plausibel (Remis zählt mit), die Quote
4,05 ist korrekt zugeordnet, aber historisch. Keine zusätzliche Sportabfrage.

## 15.10.2026 – Spezifikation freigegeben, Umsetzungsplan zur Prüfung

- [x] Nutzerfreigabe der schriftlichen Spielerindex-Spezifikation dokumentiert.
- [x] Plan erstellt und gegen die Spezifikation selbst geprüft:
  `docs/superpowers/plans/2026-10-15-tennis-spielerindex-umsetzung.md`.
  Sechs Pakete: Schema/Projektion, Aufbau, Live-Append, v2-Verträglichkeit,
  tatsächlicher Leser, vollständiger Nachweis/koordinierte Umstellung.
  v2-Kopien bleiben ausdrücklich index-invalid; kein neues allgemeines Ledger.
- [ ] Nutzer prüft/freigibt den Plan; die zuvor gewählte Ausführung mit
  Unteragenten und Review je Aufgabe bleibt erhalten.
- [ ] Danach erst Umsetzung/Migration. Ein erforderlicher schemafähiger
  Vorbereitungsdeploy ist vom abschließenden echten 4/4-/45-s-Erfolg zu trennen.

Nur Plan, Freigabestatus und Übergabe geändert. Keine Produktivcodeänderung,
Tests, Sport-/API-Läufe, Backups, Migration oder VPS-Veröffentlichung.
Der technische/fachliche Gesamtabschluss bleibt offen; frühere Statusblöcke
sind historisch. Main/VPS werden durch diesen Planungsschritt nicht verändert.

## 15.10.2026 – Spielerindex schriftlich entworfen, wartet auf Prüfung

- [x] Nach Nutzer-„Ja“ die Spezifikation erstellt:
  `docs/superpowers/specs/2026-10-15-tennis-spielerindex-design.md`.
  Empfohlen sind zwei abgeleitete Tabellen in derselben Datenbank, keine
  weitere Kopie der Statistiken. Einmaliger fortsetzbarer Aufbau, danach
  atomare Pflege durch beide vorhandenen Schreibwege.
- [x] Gegen den tatsächlichen Code abgeglichen: geschlossene Schemakataloge
  und v2-Corpus-Abrechnung ausdrücklich berücksichtigt, gültige NBA-Belege
  blockieren den Tennisindex nicht; Zusatzbudgetfehler dürfen gültige neue
  Originaldaten nicht dauerhaft blockieren. Reviewhinweise eingearbeitet.
- [ ] Nutzer prüft die schriftliche Spezifikation; danach erst Umsetzungsplan
  und dessen Freigabe. Das Gesprächs-„Ja“ war nur der Auftrag zur Schriftfassung.
- [ ] Umsetzung, Initialaufbau, unveränderter Vier-Fall-/45-Sekunden-Nachweis,
  vollständige Regression und Veröffentlichung bleiben offen.

Nur Dokumentation verändert. Kein Produktivcode, keine Tests/Migration/API-
Scans/Backups und kein VPS-Pull. Der darunter dokumentierte Batch-WIP `0ce0687`
bleibt nicht releasefähig; `main`/VPS werden durch diesen Dokumentationsschritt
nicht verändert. Keine numerischen Kontexteffekte oder Qualitätsgewinne daraus.

## 15.10.2026 – Tennis-Batch: korrektheitsgeprüft, Leistungsziel nicht erreicht

Dieser Abschnitt hat Vorrang vor den älteren Statusangaben. Kanonisch bleibt
`.worktrees/audit-repairs-20261013`; GitHub `main` und VPS wurden heute auf
`4ece002b69eb5c96897d3471cc7320654608a903` bestätigt. Kein neuer Produktionscode.

- [x] Reguläre Läufe auf diesem Produktionsstand: Tennis 00:05–00:32:36,
  Wettfinder 03:35–04:11:44, jeweils Erfolg/Exit 0; App/Caddy und Healthcheck
  funktionieren. Tagesbackup bleibt abgeschaltet. Kein Zusatzscan/Backup.
- [x] Tatsächliche Metadatenprüfung: acht neue
  `tennis-point-joint-original-v1`-Publikationen und 5.423 ältere Winner-Originale.
  Keine Ergebnislabels geöffnet; das ist kein ausreichender Trainingsbestand.
- [x] Freigegebenen Batch-Entwurf implementiert: ein gehaltener B1-Leser,
  gemeinsame Spielersuche, ursprüngliche Einzelstichtage und sämtliche
  zugelassenen Korrekturen. Reale Readiness nutzt denselben Pfad. Zusätzliche
  Regression belegt die zuvor mögliche Übernahme späterer Spielerzuordnungen.
- [x] Gezielter erster Lauf 141 Tests bestanden. Nach unabhängigem Review zwei
  echte unterschiedliche Batch-Stichtage zusätzlich geprüft; reine
  Cutoff-Mutation führt reproduzierbar zu zwei Fehlern. Abfrageprojektion auf
  einen JSON-Zugriff je Kandidat reduziert; neun fokussierte Tests bestanden.
  Abschließender Lauf aller sieben betroffenen Module auf dem neuen Freeze:
  **144 bestanden, null Fehler/Skips**, 369,59 s, Exit 0; alle fünf Dateihashes
  danach identisch. Das ist keine vollständige Suite und kein Leistungs-PASS.
- [ ] **Leistungsgate ausdrücklich fehlgeschlagen:** unveränderte vier echte
  ATP-/WTA-Fälle, ursprüngliche Belege/Stichtage und insgesamt 45 Sekunden.
  Erster Versuch 45,202 s, zweiter nach Projektion 45,266 s; jeweils null fertige
  Fälle. Keine Grenzen erhöht und keine Vergangenheit abgeschnitten.
- [x] Ursache eingegrenzt: Vorbereitung 0,449 s; danach die globale
  Kontextsuche. 2.602.717 Kontextbelege insgesamt; ATP allein 981.335.
  WTA-Zählung blieb innerhalb des begrenzten Diagnoselaufs unvollständig.
  Statusrevision und Gültigkeitsbeginn enthalten den Empfangszeitpunkt:
  gleiche sportliche Lage bedeutet daher nicht gleiche gespeicherte Inhalte.
  Gruppieren der Inhaltskennungen beseitigt diese Lesemenge nicht.
- [ ] Nächste fachliche Entscheidung: dauerhaft gespeicherte abgeleitete
  Spieler-Spiel-Zuordnung statt erneuter globaler JSON-Suche. Noch **nicht**
  freigegeben, spezifiziert oder implementiert. Kein stiller neuer Index,
  keine Schemaänderung und keine Übernahme unvollständig geprüfter Zuordnungen.

Die Batch-Änderungen sind **WIP, nicht releasefähig**. Keine neue Vollsuite
gestartet, solange das entscheidende reale Leistungsgate rot ist; die frühere
vollständige QA04 bleibt ein Nachweis nur ihres eigenen unveränderten Standes.
Kein Deployment, keine Modellaktivierung und kein behaupteter Qualitätsgewinn.
Verletzungs-, Wetter- und Müdigkeitswirkungen sind weiterhin nicht abgeschlossen.
Details: `docs/audits/2026-10-15-tennis-batch-45s.md` und Task-23-Bericht im SDD.
Geerbtes Root-WIP sowie ungetracktes `output/audit-repairs/` bleiben unberührt.

## 14.10.2026 – finaler lokaler Release-Nachweis

Dieser Abschnitt ersetzt sämtliche nachfolgenden gleichdatierten Laufstatus.
Autoritativ: `.worktrees/audit-repairs-20261013`, nicht der geerbte schmutzige
Hauptcheckout. Nutzerentscheidung: ausschließlich vorhandene und kostenlose
Datenquellen, keine neuen Tarife. Cricket bleibt ausgenommen.

- [x] Vollständige Offline-Regressionsrunde QA04 abgeschlossen: **14.035 Tests
  bestanden, 98 Skips, 147 bestandene Untertests, null Fehler**. A: 6.915 PASS /
  60 Skips / 62 Untertests, Exit 0, 2.938,93 s. B: 7.120 PASS / 38 Skips /
  85 Untertests, Exit 0, 3.010,35 s. Beide Sitzungen beendet.
- [x] Strenger JUnit-/Collection-Abgleich: alle **14.133 IDs genau einmal**,
  sämtliche 13.922 bisherigen IDs und 211 neue erhalten. Keine fehlenden,
  doppelten oder unerwarteten Fälle. 97 alte Skip-IDs unverändert; einziger
  zusätzlicher Skip ist der neue reale Windows-Symlinktest, WinError 1314.
  Keine OS-Einstellungen geändert, kein synthetischer Symlink-PASS behauptet.
- [x] Alle 21 eingefrorenen Source-/Testhashes und zehn geerbten Root-Codehashes
  nach beiden Läufen erneut identisch geprüft. Originaler 512-KiB-Speichertest,
  Grenzen und alte Tests unverändert. Nativer Pfadfix besteht auch im echten
  kombinierten Prozess: 30.604 statt 7.720.933 Bytes gemessener Peak.
- [x] POINT: echte gemeinsame Marktberechnung, vollständiger Winner-Replay,
  geschlossene Quellenfamilien, Prüfung aller Belege und geschützte ungeöffnete
  Endergebnisse. Fußball: identische Club-/Nationalteam-Spielerquellen in allen
  v3-Ownern. Die gezielten unabhängigen Reviews sind ohne offene Befunde.
- [x] Quellenpaket `50ec01910c3ed4ed6a0caa2fb08bf48720a573b5` auf `main`
  gepusht und 14.10. um 15:23 CEST per Fast-Forward auf den VPS gezogen.
  Linux-Syntax und Offline-Imports/Literalquellenfamilien bestanden. Genau ein
  App-Neustart: PID 1131606 → 1136736. Modell-JSONs vor/nach identisch; keine
  Sicherung, Datenbankkopie, Schemaänderung, Bereinigung oder zusätzlicher Scan.
  App/Caddy aktiv, sieben Timer enabled/geplant, Tages-Backup disabled/inactive,
  beide Healthchecks `ok`. SSH-Wrapper erst nach erfolgreichen Prüfungen mit
  Exit127 wegen letzter Windows-CR-Leerzeile; nicht als Exit0 umetikettiert.
  Separate korrigierte lesende Nachprüfung15:24 Exit0: ZielHEAD/PID/Health/Timer
  stimmen, kein zweiter Neustart. Abschlussdokumentation nur docs-only FF-Pull;
  ausführbarer Code bleibt der voll geprüfte Stand von `50ec019`.

### Fachlich weiterhin offen – keine numerische Aktivierung behaupten

- [ ] Tatsächlich erreichbarer begrenzter Trainingsleser. Der bestehende
  Vier-Fall-Pilot schafft innerhalb 45 s noch keinen Merkmalsvektor. Der
  verworfene Query-Kandidat ist **nicht** im Release. Die reale 7.35-GB-Datei
  überschreitet den bestehenden 4-GiB-C-Gesamteingang; keine stille Grenzerhöhung.
  Ein normaler B1-Suchindex ist ein separater unimplementierter Kandidat, kein
  C-Nachweis; atomarer begrenzter Build und derselbe reale Gegentest fehlen.
- [ ] Vorhandene Fußball-Spielminuten und vor Anpfiff empfangene Stadtprognosen
  zuerst nutzen. Große vollständige Quellenpools müssen validiert bleiben;
  kompakte geprüfte Fitprojektion und numerische Abhängigkeiten fehlen noch.
- [ ] Tennis nutzt bereits gespeicherte ATP-/WTA-Matchdauer, wo vorhanden.
  Sie besitzt aber nicht automatisch individuelle Endzeit, damalige
  Veröffentlichungszeit oder native ESPN-Spielerbindung. Für getrennte vorhandene
  Merkmale (Sätze, Games, belegte Erholungsuntergrenzen) keine exakten Endzeiten
  erfinden. Ausfallursachen und bestätigte akute Verletzungen sind nicht vollständig
  vorhanden. Eine Aufgabe beweist keine Verletzungsdiagnose.
- [ ] Rohinventur nicht als Testkohorte ausgeben: 936 passende native Finals
  über alle Winner-Generationen (270 ATP / 666 WTA). Tatsächliche neue
  POINT-Capture-Publikationen waren vor Release null. Ältere 149 ATP / 312 WTA
  sind Winner-Belege einer POINT-Modellgeneration; WTA hat dort keine belegte
  Serve-Joint-Baseline. Alte Belege nicht rückwirkend umetikettieren.
- [ ] Mindestens 200 unangetastete Testspiele zusätzlich zu Training/Tuning,
  drei Zeitblöcke, statistischer Qualitätsnachweis und anschließende echte
  öffentliche Anwendung. Verletzungs-, Wetter- und Müdigkeitseffekte sind
  **nicht abgeschlossen oder aktiviert**; bessere Wettqualität nicht belegt.

Der bestehende Tennis-v4-Winner-Pfad kann getrennte belegte Belastungsmerkmale
ohne erfundene Endzeiten untersuchen, verändert aber nur Siegerwahrscheinlichkeiten.
Aktuelle POINT-Zustände deaktivieren diesen alten Effekt ausdrücklich
(`point-winner-law-needs-own-effect-contract`). Den Guard nicht löschen oder
einen Winner-Fit als konsistente Serve-/Satz-/Game-Wirkung ausgeben. Zuerst den
vorhandenen begrenzten Quellen-/Merkmalsvergleich durchführen; eine neue
POINT-Effektfamilie wäre ein eigenständiger Modellvertrag, noch nicht umgesetzt.

Belege außerhalb Git: `C:/Projekt/BetBoy/output/context-completion-20261014/qa-final-04`
und `native-footprint/parent-combined.xml`. Vorangegangene Fehlerläufe bleiben
erhalten und werden nicht nachträglich zu PASS erklärt. Geerbtes
`output/audit-repairs/` unberührt. Nächster fachlicher Arbeitsschritt ist der
echte begrenzte Quellenanschluss, nicht ein weiterer unaufgerufener Adapter.

## Historischer Zwischenstand 14.10.2026 – durch obigen Abschluss ersetzt

Dieser Block hat Vorrang vor früheren gleichdatierten Zwischenständen.
Autoritative Arbeitskopie bleibt `.worktrees/audit-repairs-20261013`;
Main/VPS zuletzt frisch lesend `242093f`, gesund. Kein neuer Deploy/Backup/Scan.

Neuerer Abschlussgate: nativer Footprint-Fix final eingefroren, ursprünglicher
kombinierter Sammlungs-/Ausführungs-Gegentest jetzt GREEN:Peak30.604Bytes
statt7.720.933 bei unveränderterGrenze524.288,1.536PASS/8bestehendeSkips und
32PASSUntertests;5.293Suffix-Items nur diagnostisch deselektiert, keineVollsuite.
Finale neue54PASS/1echterWinError1314Symlinkskip, OriginalCold1PASS/chunks71PASS/
Nachbarn281PASS; unabhängiger Review ohne offeneBefunde, realeWAL/SHM-Prüfung.
QA04 läuft als abschließende vollständige Regression auf21Source-/Testhashes:
14.133Items (sämtliche13.922alten +211neue), A96255/B36580. Alte97Skip-IDs
müssen identisch bleiben; allein der neue nativeSymlinktest kann einen explizit
ausgewiesenen zusätzlichenWindows-Skip liefern. NochkeinVollsuitePASS/Deploy.
Keine weiterenCode-/Teständerungen während dieses Freeze;10RootWIP-Hashes gleich.

Konkreter Quellenbefund: ATP-CSV und WTA-TennisAbstract behalten bereits
Matchdauer, aber keine garantierte nativeESPN-ID-/individuelleSpielendzeit-/
damaligePublikationsbindung. Nicht pauschal behaupten, es gebe keinerlei
Tennisdauerdaten. GeplanteZeit/Ergebnisempfang bleiben keine tatsächlicheErholung.
NativeFußballminuten und vorAnpfiff empfangeneStadtprognosen sind im bestehenden
Zugang vorhanden; diese Teilmengen zuerst auswerten statt neueAdapter zu erfinden.
Die noch fehlende kompletteQuellenanbindung und zeitlich unabhängigeEmpirie
bleiben offen. Nutzerwahl zu weiterenAnbietern ohneBuchung ist eingeblendet.

Aktuelle Einschränkung: QA03 hat den unveränderten 512-KiB-Speichertest im
breiten Prozess erneut als FAIL gemeldet. Die nachstehende lokale Allokations-
korrektur ist deshalb noch kein belastbar abgeschlossener Speicherfix. Ein
gesonderter Kausaltest beobachtet die unveränderte ursprüngliche Messung;
keine Warmups, GC-Erleichterungen, Testkürzungen oder Grenzanhebungen. QA03 ist
vollständig beendet:13.980PASS/1FAIL/97 unveränderteSkips/147PASSUntertests.
Alle14.078Items exakt einmal, keine fehlenden oder neuen Skip-IDs. Original-
peak7.720.876Bytes, Grenze524.288 unverändert; dies ist größer als die bislang
diagnostizierten Tuple-Caches. Ursache inzwischen mit echtem kombinierten
Sammlungs-/Ausführungsprefix reproduziert:7.720.933Bytes, eine neue7.689.584Byte-
Allokation aus pathlib/sys.intern. Belegt ist die Neuanlage einer Intern-Dict-
Tabelle, nicht zwingend deren Verdoppelung. Enger nativer Footprint-Pfadfix ist
in TDD-Umsetzung; alte Path-Rückgabe/alle Fehler- und Raceprüfungen bleiben.
Kein neuer Gesamt-PASS oder Release daraus. Der kurz
vermutete Player-Load-Stillstand war aus der Punktanzeige falsch lokalisiert;
ein echter Stillstand oder eine neue Rekursion sind nicht nachgewiesen.

- [x] Reale Speicherursache statt verworfener Warmups repariert: interne
  Zustandsprüfung erfasst dieselben sechs Grenzwerte ohne wiederholte
  Zwischentupel. Grenzen, Persistenzformat und ursprünglicher Test unverändert.
  Echte neue RED1/13, GREEN14, unveränderter Coldtest1PASS, komplettes
  Refchunksmodul71PASS; Nachbarn281PASS nach erhaltenem Windows-Hardlink-
  Zugriffsfehler. Unabhängiger Review ohne Befund; kein numerischer Effekt.
- [x] Neuer abschließender Paketreview-P1: POINT-D4 konnte ein geschütztes,
  noch nicht geöffnetes Endergebnis lesen. Mit tatsächlichem normalisiertem
  altem Ergebnis, aktuellem Status und echtem ungeöffnetem Experiment belegt.
  Enger owning-D4-Fix abgeschlossen: finale93PASS einschließlich26neuer Fälle;
  unabhängiger Review und ursprüngliche Gegenprobe ohne geschützten Zugriff.
  Physische Datenbankbytes gleich, direkte Ergebnisleser unverändert.
  Keine Unterdrückung des Decoders und kein behaupteter Freigabenachweis.
- [ ] QA02 mit unveränderter Collection14.052 (alle13.922 bisherigen +130neue)
  bei47%A/29%B für diesen Quellenfix beendet. BeideExit1, keine Abschluss-JUnit,
  keinVollsuitePASS. ScopedGREEN/Review abgeschlossen; eingefrorene QA03 läuft
  nun mit14.078Items (13.922bisherige +156neue),20Source-/Testhashes.
- [ ] Tatsächlicher historischer Quellenanschluss: Training/Readiness benutzen
  noch plainSQLite, keinen bereits vollständigen C-Owner. Ein weiterer
  unaufgerufener Indexhelper würde das Problem nicht lösen.
  Die bestehende Produktionsdatei misst7350726656Bytes, freiesSeiteninventar0;
  dies ist nicht JSON-Payloadgröße oder ein Beweis gegen jede Fragmentierung.
  Vorhandener C-Gesamteingabegrenzwert4GiB passt nicht auf diese Datei.
  Keine Daten gelöscht, kopiert oder Grenze still erhöht. Genehmigte private
  C-Engineeringarbeit ist erlaubt; ein aktueller vollständiger Inputowner und
  explizite Ressourcen-/Rechenbilanz müssen tatsächlich angeschlossen werden.
- [ ] Große Fußballpools: vollständige Quellendeklaration ist nicht identisch
  mit numerischer Nutzung jedes Liga-Spielerbelegs. Altprüfungen müssen bleiben;
  kompakte geprüfte Fitprojektion/Abhängigkeitsmessung fehlen noch.
- [x] Frische native Winner-Inventur aller vorhandenen Generationen, ohne
  neuen API-Scan:5367Publikationen,1045erste native Ereignisse,936passende
  normale Ergebnisbindungen (ATP270/WTA666),17,129s am14.10.10:36:53UTC.
  Vorab keine Testplan-/Experiment-/Dataset-Artefakte vorhanden; keine
  geschützten Labels geöffnet, Gewinner oder Renditen nicht ausgewertet.
  Das ist Rohinventur, keine qualifizierte Training-/200Testkohorte.
  Physischer Katalog hat noch0 POINT-Capture-Publikationen. Frühere149/312
  beziehen sich auf Winner-Belege einer POINT-Modellgeneration, nicht neue
  Same-call-Capture-Belege. Fußball107Bindingpublikationen sind eine neue
  Obergrenze;8 war früher nur die geprüfte Teilmenge, nicht der Gesamtbestand.
- [ ] Erreichbarer alternativer B1-Suchindex: unveränderte Trainingsabfrage
  könnte über den bestehenden Schreibowner beschleunigt werden. Kandidat noch
  nicht implementiert/installiert; optionale exakte Schemaannahme, begrenzter
  Indexbau samt Rollback und derselbe reale45sGegentest erforderlich.
  Keine automatische unboundedDDL/ANALYZE oder behauptete Covering-Garantie.
- [ ] Verletzungs-/Wetter-/Müdigkeitswirkung,200unberührte Testfälle pro
  geeigneter Domäne, tatsächliche Qualitätsprüfung und zukünftige öffentliche
  Anwendung weiterhin nicht abgeschlossen. Keine Matchzeiten oder Verletzungen
  erfunden; Ergebnisheader sind keine qualifizierten Testkohorten.

Aktuelle briefs/reports liegen im bestehenden SDD-Verzeichnis. Diagnose des
wirklich erreichbaren Datenpfads: `task-22-history-owner-20261014-diagnosis.md`.
QA/Produktionsbelege außerhalbGit: root`output/context-completion-20261014`.
Kausalbeleg: `memory-full-causal/REPORT.md`; neuer Brief im SDD:
`task-21-native-footprint-20261014-brief.md`.
Geerbte Root-Codehashes und `output/audit-repairs/` bleiben unangetastet.

## 14.10.2026 – Verletzungs-, Wetter- und Müdigkeitseffekte: aktuelle Fortsetzung

Dieser Block ersetzt keine empirischen Lücken durch Software-PASS.
Ausgang lokal/GitHub/VPS `242093f`; autoritative Arbeitskopie weiterhin
`.worktrees/audit-repairs-20261013`. Geerbte Hauptcheckout-Änderungen erhalten.

- [x] Unveröffentlichte Tennis-POINT-Arbeit gezielt integriert: echte gemeinsame
  Berechnung, volle Sieger-Nachrechnung, geschlossene Quellenfamilien und D4-
  Prüfung sämtlicher POINT-Artefakte. Kein rückwirkendes Umetikettieren alter
  Siegerbelege. 472 gezielte Tests PASS; getrennt Cache/Shadow 44 PASS/3 bestehende
  Skips. Unabhängiger Review ohne Befund. Das ist noch keine vollständige Suite.
- [x] Fußball-v3-Quellenparität: tatsächliche Club-/Nationalteam-Historie in
  Worker, Training, Bereitschaftsprüfung und detached D4 identisch auflösen.
  Zwei echte SQLite-Fälle zunächst RED, danach vollständiger owning D4 GREEN.
  Fünfter Owner korrigiert die Verwechslung mit einem alten Modelltyp. Finale
  begrenzte Runde 71 PASS/0 Fehler/0 Skips, davon 26 neue Fälle; unabhängiger
  Review ohne Befund. Keine Freigabe eines numerischen Effekts daraus ableiten.
- [x] Frische read-only Tennis-Generationsinventur: 149 ATP-/312 WTA-Ereignisse,
  134/248 passende native Ergebnis-Header. Keine alten Modellgenerationen,
  Doppelpolls oder ATP/WTA vermischen; Header sind noch keine qualifizierten
  Training-/Abstimmungs-/200-Test-Fälle. Keine Ergebnis-/Gewinnselektion.
- [ ] Tennis-Historienabfrage: identische Vier-Fall-Merkmalsrekonstruktion
  überschritt 45s vor dem ersten Vektor. Der lokal geprüfte Query-Kandidat
  scheiterte auch im tatsächlichen begrenzten VPS-Test vor dem ersten Vektor
  und wurde ausdrücklich NICHT übernommen. Owner ist wieder bytegleich mit
  `242093f`; Kandidat und Tests nur diagnostisch außerhalb aktiver Collection.
  Merkmalsabdeckung und tatsächliche Reparatur bleiben offen. Ein zusätzlicher rein
  metadatenseitiger 15s-Zählversuch wurde begrenzt abgebrochen; kein bekannter
  Deduplikationsfaktor daraus und keine bewiesene DB-Korruption.
- [ ] Große Fußballquellen und später v3-Zeitpunkt: bestehende Gesamt-I/O-Caps
  und vollständige native Herkunft müssen bewahrt bzw. ausdrücklich versioniert
  werden. Nicht nur Limit erhöhen, alte v3-Entscheidungssperre entfernen oder
  Quellen unangekündigt wegfiltern.
- [ ] Empirische Wirkung: kein reales qualifiziertes Modell/keine numerische
  Aktivierung aus diesen Reparaturen ableiten. Ein POINT-Sieger-Kontextmodell
  braucht eigene geprüfte Training-/Testkohorten; Aufschlag-, Satz-/Game- und
  Verletzungswirkungen sind damit nicht automatisch identifiziert.
- [ ] Fußball-Anwendungsbrücke erst auf der tatsächlich qualifizierten
  Modell-/Quellendomäne: dieselbe gelesene Freigabe, unveränderlicher gemeinsamer
  zukünftiger Prognosebeleg und eigener Consumer. Nicht neue p-Werte in alte
  Challenge-Validierung/Sicherheitsabschläge/15K-Freigaben hineinsplicen.
- [x] Abschlussreview-P2 repariert: optionales Tennis-Ergebnislesen bei mehr
  als 500 erfassten Ereignissen darf fertige Prognosen nicht abbrechen. Nur
  explizite endliche Admission kann intern vollständig abgelehnt werden;
  Integritäts-/Quellen-/Zeitfehler bleiben strikt. Sechs echte RED-Fälle,
  danach 9 PASS; owning Nachbarn 131 PASS/3 bestehende Skips. Unabhängig
  nachgeprüft, keine offenen Befunde. Keine Kürzung, Cap-Erhöhung oder Kundentexte.
- [ ] Eine finale vollständige Regression, dokumentierter scoped Commit/Push,
  anschließender begrenzter VPS-Pull ohne neues Backup. Aktuelle Pakete lokal
  noch unveröffentlicht. Alte Tipps/Geld/Quoten-/Einsatzregeln unverändert.
  Erste kombinierte Runde wegen des obigen echten P2 gezielt abgebrochen, kein
  PASS. Neue finale Collection: 14.038 Items, alle 13.922 alten genau erhalten
  plus 116 neue; Source-Freeze und zwei disjunkte Dateigruppen in `qa-final`.
  Die vollständige Endrunde läuft; ein Teilfortschritt ist kein Vollsuite-PASS.

### Aktueller Endgate – kein Gesamtabschluss

- Die A-Vollgruppe wurde nach einem realen unveränderten Speichergrenzen-FAIL
  bei 47 % angehalten. B danach bei 65 % kontrolliert beendet, ohne neue
  Fehlermeldung, aber ebenfalls ohne Abschluss-JUnit. Beide Exit 1; kein PASS.
- Der einzelne Cold-Speicherfall wurde unverändert mehrfach reproduziert:
  645.510 / 641.969 / 641.984 Python-Bytes bei Grenze 524.288. Sammlung vor
  Messung allein und ein Diagnose-Cursor-Schließungsproxy beheben ihn nicht.
- Ein fest begrenzter kleiner Warmup bestand isoliert, scheiterte aber im
  ganzen owning Modul: 71 PASS/1 FAIL, 993.124 Bytes. Echte 1-MiB-Negativkontrolle
  erkannte den Puffer korrekt. Kandidat deshalb NICHT akzeptiert; owning Test
  wieder vollständig auf Basis, ursprüngliche IDs/512-KiB-Grenze unverändert.
  Diagnosekopie/RED-Bericht erhalten; kein Wiederholen bis zufällig grün.
- Akzeptierte POINT-/Fußballcodehashes weiterhin unverändert. Der Arbeitsstand
  darf als scoped Branch-Checkpoint gesichert werden, nicht als fertige
  Modellwirkung oder erfolgreicher Hauptrelease. Kein neuer VPS-Pull/Restart.
- Fachlich zuerst die reale Teilnehmerfindung und große vollständige native
  Quellenpools reparieren, dann echte Merkmals-/Training-/Zeit-Test-Abdeckung
  bestimmen. Tennis hat im geprüften Adapter keine gemessenen Matchzeiten oder
  bestätigten akuten Verletzungsmerkmale. Ergebnisheader allein ersetzen dies
  nicht. Numerische Freigabe und öffentliche Anwendung bleiben offen.

Verifizierter Checkpoint: `291525211ab0e66591e878a6217b568a739293f8`, committed
und auf `origin/codex/audit-repairs-20261013` gepusht, kein main-Release.
GitHub-main und read-only VPS weiterhin `242093feda28a31bb8729e31529032ee059b570a`;
App/Caddy aktiv, beide Healthchecks `ok`, letzter Tennisservice Result success/
ExecMainStatus0. Kein neuer Pull, Restart, Backup oder Sport-/API-Scan.
Alle 17 eingefrorenen Code-/Testhashes sowie 10 geerbten Root-Codehashes gleich.
Fortsetzungsreihenfolge: realer Quellen-/Abfragepfad, unverändertes Speichergate
kausal reparieren, komplette Regression, danach Integration/Veröffentlichung;
erst qualifizierte numerische Modelle an künftige Marktwerte anbinden.

Bericht: `docs/audits/2026-10-14-kontextmodell-abschlusspruefung.md`.
Belege: `C:/Projekt/BetBoy/output/context-completion-20261014`.
Keine neue Sport-/API-Abfrage, Produktionsdatenbankkopie oder Bereinigung.

## 13.10.2026 – Tennis-Ergebnisbrücke nach Hurkacz–Davidovich

- [x] Der belegte Datenbruch ist in ATP/WTA reproduziert und begrenzt repariert:
  bestätigte, fehlende Ergebnisse aus bestehenden Original-/Status-/Siegerbelegen
  gelangen einmal in die Elo-Modellbasis. Keine erfundenen Serve-/Kontexteffekte.
- [x] Schutz gegen zukünftige Ergebnisse, spätere Rücknahmen/unklare Sieger,
  widersprüchliche Originalbindungen und mögliche CSV-Doppelzählung.
  Alte Prognosen, Abrechnungen, Guthaben und Preise unverändert.
- [x] Täglicher Cache-Aufbau auch bei frischen Tourmodellen; keine zusätzlichen
  Downloads oder Cache-Seeding, auch nicht bei fehlenden Dateien. Älterer
  paralleler Trainingsstichtag kann keinen neueren Zustand überschreiben.
- [x] 25 neue Schutzfälle; finale betroffene Vier-Modul-Runde 151 PASS,
  unabhängiger Review 145 PASS (überlappend, nicht addieren), keine offenen P1/P2.
- [x] Echte read-only VPS-Probe: fehlendes Davidovich–Tiafoe-Spiel `184936`
  am damaligen Stichtag genau einmal als Davidovich-Sieg zugelassen.
  23 native Belege, 4 Originale und bestehende Shadow-/Modellrevisionen unverändert.
- [x] Neue exakt gepinnte Cache-only-Quellenfamilie erhält historische Replay-
  Identitäten. Zehn zusätzliche Übergangs-/Unknown-/Mixed-Owner-Schutzfälle;
  ursprüngliche Pins unverändert, keine D2-Evaluation oder Aktivierung umgangen.
  VPS read-only: null aktive Kontextfreigaben, nur ATP/WTA-Modellslots.
- [x] Gemeinsame Abschlussrunde mit historischen Runtime-/D1-Replays:
  364 PASS, 316,65 s (`source-family-green.xml`). Überlappende Zahlen nicht addieren.
  Unabhängiger Quellenfamilien-Review ebenfalls ohne Befund, 213 Replaytests PASS.
- [x] Autoritative vollständige Dateigruppen `full5-A` und `full5-B` abgeschlossen:
  **13.825 PASS, 97 unveränderte Plattform-Skips, 147 Untertests, null Fehler**.
  Beide Exit 0; A: 6.419/66/79 in 3.811,57 s, B: 7.406/31/68 in 3.598,25 s.
  `complete-qa5-check.log`: alle 13.922 Hauptitems genau einmal, keine fehlenden,
  doppelten oder unerwarteten IDs. Acht eingefrorene Code-/Testhashes identisch;
  die 97 Skip-IDs sind exakt dieselben wie in der vorherigen vollständigen Suite.
  Belege:
  `C:/Projekt/BetBoy/output/tennis-result-bridge-20261013`. Frühere begonnene
  Vollrunden abgebrochen; `full3` fand Quellenidentitätsfehler, begrenzt korrigiert.
  Keine dieser Vorprüfungen als bestandene Vollsuite zählen.
  `full4` durch Unterbrechung bei 81 % ohne Abschluss-JUnit beendet, kein PASS.
  Eigene temporäre Verzeichnisse, `partition5.json` und strikter Vereinigungsabgleich.
- [x] Codecommit `a3f465c673da2d4c3050bdd26203519181bcb882` nach Vollsuite
  auf main gepusht und per begrenztem source-only VPS-Fast-forward veröffentlicht.
  Am 14.10.2026 08:23 CEST: kanonischer Worktree, GitHub und VPS identisch.
  Offline-Linux-Imports/Quellenfamilie PASS; App-PID 1116649 → 1131606,
  App/Caddy aktiv, sieben Timer aktiv/enabled, beide Healthchecks `ok`.
  Modell-JSONs bytegleich; Backupdienst/-timer inactive, kein neues Backup,
  Zusatzscan oder Neuaufbau alter Tipps. Berechnungsdienste/Timer nicht neu gestartet.
  Zehn geerbte Hauptcheckout-Codehashes unverändert. Abschlussbelege:
  `deploy-code.log`, `production-code-final.log`, `root-wip-preservation.log`.
  Rein dokumentarischer Abschluss separat per FF ohne weiteren Appneustart.
- [ ] Produktionsübernahme in neue Modellartefakte beim nächsten **regulären**
  Touraufbau bestätigen; installierter Code allein ist kein neuer Modelllauf.
  Vorinstallation 14.10. 07:01: VPS `dd704ade`, regulärer alter-Code-Tennisjob
  erfolgreich. Nächster Termin **15.10.2026 00:05 Europe/Zurich**; keinen Zusatzscan.
  Echter Nachtlauf: Exit 0, 45 verarbeitet/35 neue Prognosen, keine ungelösten
  Ergebnisse. Kontext weiterhin partiell: 14 Identitätskonflikte + 1 nativ
  fehlendes Ergebnis; nicht als volle sportliche Datenabdeckung bezeichnen.

Details: `docs/audits/2026-10-13-tennis-ergebnisbruecke.md`.
Diese Reparatur beweist weder eine bessere Rendite noch aktivierte numerische
Verletzungs-, Wetter- oder Müdigkeitseffekte. Autoritative Arbeitskopie weiterhin
`.worktrees/audit-repairs-20261013`; Hauptcheckout-WIP unberührt lassen.

## 13.10.2026 – Claude-Auditpaket: geprüft, gepusht und auf dem VPS live

Dieser Abschlussblock ersetzt die darunterstehenden historischen Zwischenstände.
Autoritative Arbeitskopie: `C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013`.
Der Hauptcheckout hält unveröffentlichte frühere WIP; nicht resetten oder breit stagen.

- [x] Die sechs freigegebenen Reparaturen sind umgesetzt: Auszahlungsbestätigung,
  unveränderliche abgerechnete Tippdaten, Decimal-Korridor, kausale Tennisdaten,
  gemeinsame one_set-Abrechnung und quotenfreie persönliche Merkliste.
- [x] Kalibrierungskandidat v2 geprüft, aber bewusst nicht aktiviert: 304 echte
  chronologische Cachevergleiche sind schlechter. Aktive v1/v14 unverändert;
  bekannte Modell-/Original-/Fitversionen bleiben geschlossen gebunden.
- [x] Vollprüfung des eingefrorenen Index `b879d8d75ececc72848a3a2917bfab79959c8e95`:
  **13781 bestanden, 97 bestehende Plattform-Skips, 147 Untertests, 0 Fehler**.
  A4: 6648/58 Skips/36 Untertests, 2775,93s; B4: 7133/39/111, 946,85s.
  `check_complete_qa.py` bestätigt alle **13878 Haupttest-Items genau einmal**,
  keine fehlenden/doppelten Haupttests und keine Fehler.
- [x] Letzte separate UI-Ergänzung: „Tipp merken“ auch in der manuellen Tennissuche.
  Neun Regressionen zuerst RED (6 Fehler/3 PASS), danach alle acht betroffenen
  Module **255/255 PASS**, 10,16s. Native Ereignis-ID, echter dauerhafter Accountscope,
  beide Favoritenseiten, fehlende Quote und geschützte Settled-Snapshots geprüft.
  Diese Delta-Prüfung NICHT zur überlappenden Vollsuite addieren oder rückwirkend
  dem vorherigen eingefrorenen Index zuschreiben. Finaler Code-/Testindex:
  `0ca151db8eb99cbb058fd0891bfc09a492f13581`.
- [x] Codecommit `6636530267826fb37b3c834b8e94afa4ebc1b019` auf GitHub-main
  gepusht und am 13.10.2026 um 20:33 CEST per begrenztem Fast-forward vom
  bisherigen `c5a6264` auf dem VPS veröffentlicht. Reparatur-Worktree/GitHub/VPS
  vor dem rein dokumentarischen Nachtrag exakt identisch; Hauptcheckout-WIP erhalten.
- [x] Offline-Linux-Imports einschließlich Tennisrenderer erfolgreich; aktive
  Kalibrierung ausdrücklich legacy-v1. App/Caddy aktiv, alle sieben Timer aktiv
  und enabled, letzte Dienste success/inactive, beide Healthchecks `ok`.
  Backupdienst/-timer weiterhin inactive, 21GiB frei.
- [x] Wettfinder-/RisikoBet-JSONs vor und nach dem Deploy bytegleich:
  `f20422a802fd61461d8f8ab548f85228a1d083bdba92c51a0615bf9364a81bd4` /
  `6f0c5f3158fb2bbe08bc8b7692636a0f16847e90c32742a7f7497346b644e8f1`.
- [x] Interner Browser nach Reload: 18 „Tipp merken“-Buttons, erster sichtbar,
  keine Seitenexception und keine neuen Warnungen/Fehler seit dem Wiederanlauf.
  Erwartete Verbindungs-/502-Meldungen während des kurzen kontrollierten Neustarts
  nicht als permanente Appfehler oder als vollständig fehlerfreien Neustart ausgeben.
  Keine echte Produktions-Merkliste oder Geldbuchung testweise angelegt.

Produktionsbelege: `deploy-code.log` und `production-code-final.log` im Belegordner.
Dieser dokumentarische Nachtrag wird separat ohne Appneustart per FF nachgezogen;
Code- und QA-Stand ändern sich dadurch nicht. Alle historischen PENDING-Blöcke
darunter sind überholt und keine offenen Aufgaben dieses abgeschlossenen Pakets.

Keine neuen Backups, Produktions-DB-Kopien, Sport-/API-Scans oder Preis-/EV-Gates.
Kein historisches Geld/Prognoseumschreiben; Cricket und Mindestquote 1,20 unverändert.
Nach Appstart kein ungeprüfter Rückfall auf alte Code-/Storeverträge.
**Separate Restarbeit:** Verletzungs-/Wetter-/Müdigkeitswirkung und reale 4MiB-
Quellenpoolgrenze weiterhin nicht gelöst. Bestehende Fußball-Shadow-Preisprovenienz
liefert keinen gültigen CLV-/ROI-Nachweis; Software-PASS belegt keine bessere Rendite.
Belege: `C:/Projekt/BetBoy/output/audit-repairs-20261013` und
`docs/audits/2026-10-13-claude-audit-reparaturen.md`.

## 13.10.2026 – freigegebene Claude-Auditreparaturen: lokaler Abschluss

Dieser neueste Block hat Vorrang. Autorisierter Umfang: Auszahlungsplausibilität,
abgeschlossene Tippdaten, exakte Quotenprodukte, Tennis-Kausalität/Ein-Satz-Regel,
Kalibrierungsprüfung und persönliche Merkliste. Kein neuer Kontextmodellauftrag.

- [x] Isolierter Reparatur-Worktree
  `C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013`,
  Branch `codex/audit-repairs-20261013`, Ausgang `c5a6264`.
  Alte dirty/untracked WIP im Hauptcheckout vollständig unberührt lassen.
- [x] Neue ungewöhnliche Daily3-/15K-Gutschriften benötigen konkrete Begründung
  und separate Bestätigung; UI-Bestätigung ist an Betrag/Quote/Ticket gebunden.
  Alte signierte Abrechnungen bleiben unverändert lesbar.
- [x] Abgeschlossene gespeicherte Tipps unveränderbar. „Tipp merken“ funktioniert
  ohne Quote/EV-Freigabe: BOOKMARK, Einsatz 0, unbekannte Quote NULL.
  Atomare nullable Migration bewahrt alte Werte, IDs und AUTOINCREMENT-Zähler.
- [x] Decimal-exakter Quoten-Korridor einschließlich 1,50×1,60×1,25=3,00;
  riesige ungültige Kombinationen verhindern keine normalen gültigen Tickets.
- [x] Tennisstatistiken nicht mehr anhand Turnierstart/geratener Turnierdauer
  vorzeitig zulassen. Reale Finish-Verfügbarkeit oder konservative Datumsgrenze.
  Backtest und neue manuelle/automatische Shadow-Abrechnung teilen one_set;
  fehlende Abrechnungsbelege bleiben nicht auswertbar, keine erfundenen Voids.
  Alte Abrechnungen werden nicht neu bewertet; RisikoBet-Vertrag bleibt separat.
- [x] Explizite stärkere Kalibrierung v2 technisch testbar, aber **NICHT aktiviert**:
  304 reale historische Spiele in zwei bestehenden Caches zeigen schlechteren
  Brier und gemeinsamen Logloss. Produktion und Primitive bleiben v1/v14.
  Bekannte Original-/Rezept-/Fit-/Kontrastversionen geschlossen paaren;
  gemischte Gesetze und alte Fits auf Kandidat-v2-Basis ablehnen.
- [x] Unabhängige begrenzte Reviews aller Reparaturbereiche PASS; echte Merkliste
  per Streamlit-AppTest bis SQLite/Meine Tipps geprüft. Überlappende Testzahlen
  NICHT addieren; Details im neuen Auditbericht.
- [ ] Gemeinsame konfigurierte Offline-Gesamtprojektprüfung läuft noch.
  Erster Aufruf scheiterte ausschließlich an fehlender Portal-QA-Konfiguration;
  zweiter Aufruf nutzt siteconfig.qa_settings/In-memory-DB.
  Zweiter Vorlauf wegen bereits bekannter Fixture/AST-Prüfung bei circa 10%
  gezielt beendet (exit -1, KEIN PASS). Cricket-QA-Vertrag inzwischen repariert:
  exakt unveränderte Fixture auf LF, gemeinsam genutzten/Cricket-Pfad weiter
  einfrieren und Hockey-only-Pfad getrennt behandeln. 7 gezielte Tests PASS,
  einschließlich Mutationen der gemeinsamen Mathematik/Cricket-Routing/Guards.
  Kein Cricket-Produkt-/Fixturehashwechsel oder Testdeselektion. Finale komplette
  Prüfung gestartet 13.10.,16:42CEST, korrekt bei erstem echten Fehler beendet:
  3386 bestanden,25 Skips,117 Untertests,1 Fehler,1665,38s. Kein Gesamt-PASS.
  `test_context_runtime_tennis_live::test_schema2_point_live_original_replays_read_only_without_rebuild[ATP]`:
  neuer Tennis-Loader ändert Codehash, die Point-Schema2-Kennung unterstützte
  nur alte Ownerbytes. Exakte statische neue LF/CRLF-Kennung und gerichtete
  Kompatibilität repariert:162/162 betroffenes vollständiges Modul PASS,
  unabhängig9/9 Manifest-Gegentests PASS. Alte Point-Originale (ATP/WTA,LF/CRLF)
  replayen read-only; unbekannte/gemischte Owner und Reverse bleiben abgelehnt.
  Kein dynamisches Hash-Bypass, keine historische Umschreibung.
  Weitere Gesamt-QA fand Windows-TESTaufbaufehler (B2891pass/8skip/85Untertests/
  1Fehler,603,59s; A bei22%gezielt beendet,kein PASS): text=True machte Bashstdin
  CRLF; zwei hartgepinnte Python-Dateien lagen lokal CRLF vor,Git/LINUXbytes LF.
  Nur Testadapter+3Aufrufermodule/LF-Attribute korrigiert; Nicht-Bash-Aufrufe,
  Backup-/Stage-Inhalte und ihre erwarteten Hashes unverändert. UTF8-Inputbytes
  exakt, Ausgabe behält alteTextsemantik, lokalesGitBash stattWindowsWSLalias.
  354/354Hooktests PASS,112Updater/Servertests PASS+1vorhandenerLinuxflockSkip.
  3neue Adapter-Regressionen PASS. Keine Testauslassung oderProdukt-/Backupänderung.
  A2/B2 ebenfalls KEIN PASS: A2 endete2771pass/19skip/32Untertests/1Fehler
  in1913,86s, B2 endete4835pass/8skip/111Untertests/1Fehler in1479,91s.
  A2: altes Sequenzfixture behauptete CHF120Rückzahlung bei CHF50/Quote1,20;
  neuer Wächter lehnte korrekt ab. Nur tatsächliche Erstquote im Test2,40,
  Zweitbestätigung/Verlustlimit NICHT gelockert.87betroffene und alle251Daily3-
  Tests PASS. B2: weitere rohe QA-Owner lokalCRLF statt bestehendemLinuxLF.
  Alle exakt belegten Pfade über LF-Attribute kanonisieren, keine Pinänderung;
  HEAD-/Index-Gitblobs der Helfer unverändert. Voller Native-Chain-Modul65PASS.
  Vollständige7Modul-Protokollrunde:271PASS/54bestehendeLinux-root-Skips/
  0Fehler,148,56s. Alle13formatiertenQuellen roh==HEAD==Index; bestehendePins
  unverändert,inventory.pyunberührt. Keine neuenSkips oderGit-Codeinhaltänderung.
  B3 vollständig beendet:7124PASS/39Skips/111Untertests/9Fehler in1201,19s.
  Genau2weitere rohe LF-Pins betroffen (native_preparation_worker.py und
  eingefrorene Tennis-Simulator-Fixture); bestehendeHashes/Gitblobs unverändert,
  nur2exakteLFAttribute undFormatierung. BeideganzenModule226/226PASS,3,41s.
  B4 abgeschlossen:7133PASS/39Skips/111Untertests/0Fehler,946,85s.
  A3 vollständig4Fehler/6644PASS/58Skips/36Untertests,2894,95s: JSON-Probe
  lokalCRLFstattbestehendemOriginalhash; alteMocksnahmenlaw_version/save_source
  nichtan. NurexakteJSON-LF-Attribute/Formatierung und2expliziteTestdouble-
  Signaturen korrigiert, aktivev1/Save-Herkunft zusätzlichassertiert.
  Produktcode/Pins/alteSortier-/Familienasserts unverändert.188+13betroffene
  ganzeModultestsPASS. A4 prüft diegesamteersteHälfte frisch.
  Erneuerte Vollcollection:13878 Haupttests/367Module. A4/B4 mit184/183
  disjunkten Modulen laufen ohne Testabwahl und ohne Fail-fast, damit alle
  verbleibenden Fälle geprüft werden. Abschluss über final-shard-A4/B4.log/xml
  und check_complete_qa.py: jedes gesammelte Haupttest-Item genau einmal,0Fehler.
  Finaler Code-/Testindex `b879d8d75ececc72848a3a2917bfab79959c8e95`.
  Gegen b841 nur2QA-Testdouble-Dateien und exakteLF-Metadaten;
  alleProdukt-Gitblobs/B4-Testblobs unverändert.
  Keine Dependencyinstallation.
- [ ] Nach tatsächlichem QA-Abschluss explizite Dateien committen, main pushen
  und VPS per begrenztem FF deployen. Noch NICHT veröffentlicht.
  Aktueller RO-Abgleich: GitHub/VPS c5a6264, App/Caddy/7 Timer und Healthchecks ok.
- [ ] Letzter Anschlusscheck fand: Manuelle Suche → Tennis hat noch keinen
  persönlichen Merken-Button. Enger Patch außerhalb des eingefrorenen Worktrees:
  `C:/Projekt/BetBoy/output/audit-repairs-20261013/manual-tennis-bookmark.patch`.
  Unabhängig statisch PASS; 9 neue Fälle im bestehenden Bookmark-Testmodul.
  Nach A4 zuerst Tests RED, danach Produktanschluss und vollständige betroffene
  UI-/Merkliste-/Tennis-Prüfung. Keine Neuberechnung, Quoten-/EV-/Einsatzfreigabe;
  native Ereignisbindung und dauerhafter Accountscope, geschützte Settled-Snapshots.
  A4/B4 qualifizieren den eingefrorenen Index b879; diese letzte UI-Ergänzung
  anschließend separat und ausdrücklich als Delta qualifizieren, nicht als
  bereits vollständig getesteten Bestandteil der alten Vollsuite ausgeben.
- [ ] Separate vorhandene Fußball-Shadow-Evidenzlücke: Vorprüfung meldet
  betboy-football-shadow.service partial/exit1. Für Fixture1497716 gibt es keine
  akzeptierte aktuelle Bet365-Quote mit Providerzeit; vorhandene Retrylogik
  verschiebt wahrheitsgemäß. Zwei bereits alte abgerechnete Belege haben
  invalid_quote_provenance/malformed_settlement; kein gültiger CLV-/ROI-Nachweis.
  Unabhängig gegen unveränderten produktiven c5a6264-Code bestätigt; keine
  Regression dieses noch unveröffentlichten Pakets. Nächsten regulären Lauf
  beobachten, Originalbelege getrennt prüfen; keine Zusatzabfrage/Altzeilen-
  Löschung, erfundene Provenienz oder künstliche Erfolgsstatuskorrektur.
- [ ] Nach Appstart KEIN blinder Old-Code-Rollback: neue BOOKMARK/nullable Felder
  und Sondergutschriftverträge können bereits benutzt sein. Vor Appstart nur
  source-only Recovery erlaubt; kein Geld löschen/umsignieren/zurückübersetzen.

Keine neuen Backups/Produktions-DB-Kopien/Sport-/API-Scans. Keine neuen Preis-/EV-
Gates, kein Wechsel der 1,20-Regel, keine rückwirkenden Prognose-/Geldänderungen.
Verletzungs-/Wetter-/Müdigkeitsnachweis weiterhin separat offen; die darunter
beschriebene reale 4MiB-Quellenpoolgrenze wird durch dieses Paket NICHT gelöst.
Belege: `C:/Projekt/BetBoy/output/audit-repairs-20261013`,
`docs/audits/2026-10-13-claude-audit-reparaturen.md`.

## 13.10.2026 – Kontextanschlüsse live; reale Einzelquellengrenze bleibt offen

Auf ausdrückliches „machen“: bestehende v2-Kadermerkmale im Worker/Transport
anschließen, anschließend D1-Kohorte ohne mehrfach gehaltene Finalspieldaten
vorbereiten. Kein neuer Modellvertrag oder numerisches Freigabesiegel.

- [x] Inherited native Owner-Baseline52/52,136,39s; alte WIP-Dateien erhalten.
- [x] Erneute reine Serverinventur:101 Originalbindings,8 captured/93 partial;
  keine Fits/Effekte/Approvals. Zahlreiche Beobachtungszeilen sind vorhanden,
  aber nicht automatisch vollständige verknüpfte Vergleichsspiele.
- [x] Neue19 echte native SQLite-Tests bestanden164,68s; v2-Verbindung und
  versionsgenaue Coverage auch ohne Effekt geprüft.6 neue Verhaltensfehler plus
  ein falscher Coverage-Return vorher reproduziert. Setup-/Envelope-Tippfehler
  separat dokumentiert und nicht als erfolgreiche Runden dargestellt.
- [x] Unabhängiges v2-Taskreview PASS. Gemeinsame Release-QA bleibt unten separat.
- [x] D1-Code: eindeutige physische Original-/Quellenbytes einmal zählen; Finalfälle
  streamen statt alle Originals halten; Train/Tune separat begrenzen.64/128MiB-
  Offlinegrenzen und1/3MiB-Produktionserfassung nicht bloß erhöhen.
- [x] D1-Review PASS; physische Daten nicht mit RAM-Garantie verwechseln.
- [x] Tatsächliche Post-Kontext-Entscheidung mit Quellenhash/-anzahl separat
  festhalten. ORIGINAL-Batches haben Vorrang; höchstens32 kompakte Belege/32KiB
  aus dem bestehenden Restbudget. Keine erfundene frühere Empfangszeit.
- [x] Reviewbefund: logische Entscheidung konnte vor der physischen ORIGINAL-
  Veröffentlichung liegen. Gemeinsamen Resolver repariert;6 echte SQLite-
  Regressionen und48 Nachbarn bestanden, unabhängige Nachprüfung PASS.
- [x] Exakte21-Dateien-Fußball-Veröffentlichung vorbereitet; Enrichment-/Tennis-/
  15K-WIP ausdrücklich NICHT enthalten. Finales Integrationsreview PASS.
- [x] Korrigierter203-Fall-Test mit echtem Fit/Evaluator/Verify und gleichem
  Legacy-Fit bestanden;203 Fälle,2Train/1Tune/200Final,keine Aktivierung.
  Das bleibt synthetische Softwaremechanik, kein Verletzungs-/Qualitätsnachweis.
- [x] Vollständige begrenzte Release-QA:663 Tests in25 Modulen bestanden,
  0 Fehler/Skips,3136,79s. Exakter isolierter Codeindex
  `af0d4d4b007d2a3a90ea9cfdb66e48a9d09959fb`; keine fremde WIP im Teststand.
  `frozen-corrected.xml` außerhalb Git.203-Roundtrip1820,03s, Retained-Cap-
  Negativtest118,99s. Ursprüngliche203-Fall-Testkonfiguration
  verlangte ein tatsächlich fehlendes Spielermerkmal. Das Modell lehnte korrekt
  ab (unsupported,0/0). Nur neue Testkonfiguration auf belegtes Spielplanmerkmal
  korrigiert; physische Quellen140.424.440B vorherige Mehrfachzählung gegenüber
  44.576.281B eindeutig. Kein Verletzungs-/Gesamtkadernachweis daraus ableiten.
  Erster37-Modul-Lauf abgebrochen, KEIN PASS; nicht zu663 addieren.
- [x] Nur explizit geprüfte Voraussetzungen/Dateien vorbereitet;
  Tennis-/Enrichment-/andere Alt-WIP nicht unbeabsichtigt mitnehmen.
- [x] Codecommit **5f175889c4058e65995ca358709b7499d3582fd7** committed,
  auf main gepusht und13.10.,14:13CEST kontrolliert per FF auf dem VPS live.
  Linux-Offline-Import,App/Caddy,beideHealthchecks und7aktivierteTimer bestätigt.
  Zwei anfängliche lokale Verbindungsmeldungen während Neustart durch normale
  Retrylogik beendet; finalerDeployexit0.21GiB frei; Backupdienst/-timer inactive.
  ModellJSON-SHA vor/nach gleich:Wettfinderf20422a8…,RisikoBet6f0c5f31….
- [x] Neue tatsächliche RO-Merkmalsinventur ohne Kopie/API/Fit/Aktivierung:
  8native ORIGINAL-Katalogspiele geprüft. **7/8 scheitern weiterhin an der
  einzelnen4MiB-Quellenpoolgrenze**,1Quellenfall mit Ergebnis auflösbar.
  Für die ausdrücklich geprüften Einzelmerkmale v2-Kaderverlust,v3gemeldete
  7-Tage-Belastung undWettertemperatur jeweils0verfügbar. Kein Audit sämtlicher
  möglicher Merkmale/Populationen;0Fits/Effekte/Freigaben aktiv.
- [ ] NächstePriorität:4MiB-Poolursache erklären und Quelle/Revision/
  tatsächlich konsumierten Zweig sauber aufteilen,ohne Cap-Anhebung oder
  Quellenverlust/Umdeutung. Mehr Spiele sammeln beseitigt diese Sperre NICHT.
- [x] Ursache rein lesend weiter eingegrenzt:6große Fälle je36.105–37.092
  Receipts/97.105.011–99.654.909B; weiterer Fall3046Receipts/4.533.002B;
  kleiner Fall130/197.155B. Jeweils ALLE Content-Digests verschieden,
  alle Raw-IDs Teil der Goal-/Prior-/Binding-Closure,unverbrauchteIDs0.
  Sechs große Fälle zusätzlich latent über4096Receipts. Baseline34,39–35,34MB
  plusAppearance62,07–63,64MB. VerschiedeneHashes beweisen keine verschiedenen
  sportlichenWerte; Body-/Rollen-/Revisionsabhängigkeit noch NICHT dekodiert.
  ReineDeduplikation/EntfernenunverbrauchterRaw-IDs löst diese sieben Fälle nicht.
- [ ] Nächster konkreterCodepfad:branch-/rollenbezogene vollständige Quellen-
  auflösung mit Streaming/Projektion entwerfen und invariantengetreu testen.
  Originalconsumed/inspectedRefs,sameclockKonflikte,ersteResultatbelege und
  tatsächlicheUhren behalten; kein willkürlicheslatest-only/kleineresKollektiv.
  Kein kleiner sichererFix ist durch reineHeaderstatistik bereits bewiesen.
- [ ] Tatsächliche Quellen-/Wirkungsabnahme bleibt separat. Keine Prozentabschläge
  erfinden, keine alten Empfangszeiten/Prognosen/Geldbuchungen ändern.

Ausgang6f86b31; funktionaler,testverifizierterCode5f17588 jetztlive.
Ein folgender reinerDokucommit hält diesen Produktionsnachweis fest.
Arbeitsberichte `C:/Projekt/BetBoy/output/context-integration-20261013` außerhalbGit.

## 13.10.2026 – vorhandene Historie/Shadow wirklich auswerten

Nutzerauftrag: vorhandene History und Schattendaten nutzen, nicht nur auf neue
Belege warten. Die früher genannten95 betreffen ausschließlich native ORIGINAL-
Bindings, NICHT den gesamten Prognose-/Shadow-Bestand. Dieser Block hat Vorrang.

- [x] Rein lesende Produktionsinventur:84.025 Fußball-SHADOW-Revisionen,
  **662 unterschiedliche Spiele,588 davon mit Ergebnis**,4.396 Event-/Markt-/
  Auswahl-Ergebnisse. Wiederholte Läufe/Märkte sind keine unabhängigen Spiele.
  Legacy `shadow_clv.db` enthält dagegen nur3 Prognosen;3.387 Fixtures darin
  sind Spieltermine und keine Prognosebelege. Inventur13.10.,08:38–08:49CEST.
- [x] Native ORIGINAL-Bestände getrennt:101 Bindings,8 vollständig captured,
  93 partial. Die588 auswertbaren Shadow-Spiele belegen Grundmodell-Ergebnisse,
  aber keine200 vollständigen unabhängigen Verletzungs-/Müdigkeits-Testfälle.
  Shadow speichert skalare Wahrscheinlichkeiten, nicht die ursprüngliche volle
  kalibrierte Torverteilung samt sämtlichen konsumierten Quellen.
- [x] Reproduzierter Speicherfehler: Quellenflush verbrauchte sein gleiches
  Bytebudget zuerst für ältere Historie und verlor später empfangene aktuelle
  Spiele. Jetzt native NS/TBD/PST-Ziele und sämtliche empfangenen Revisionen
  stabil zuerst; Budget, Quelluhren, Korrekturfolge und historische FT-Reuse gleich.
- [x] Irreführender globaler Sperrgrund repariert: nur tatsächlich am Budget
  gescheiterte native IDs heißen Budgetausschluss. CSV-/nie empfangene Quellen
  bleiben fehlende native Belege, keine erfundene Budgetursache.
- [x] Bestehende Qualitätsauswertung streamt Forecast-Payloads in EINEM Read-only-
  SQLite-Snapshot statt sie vollständig zu materialisieren. Gleiche kausale
  Erstentscheidung, Ergebnis-/Preisregeln, Brier/Log-Loss/Kalibrierung. Synthetischer
  Python-Payload-Peak137MB→221KB; Quote-Payload17MB→32KB. Das sind tracemalloc-
  Messungen, KEINE allgemeine Prozess-RAM-Garantie; Identitäts-/Ergebnis-/
  Quotenindizes und SQLite-Puffer wachsen weiterhin mit den echten Daten.
- [x] Exakter isolierter Indexstand:267 Release-/Nachbartests bestanden.
  Abschließende LF-materialisierte Runde267/267 in32,35s,0 Skips/Fehler.
  Frischer unabhängiger Review:keine Critical/Important/Minor-Befunde.
  Portal mit vorgesehenen `siteconfig.qa_settings`:47 Tests bestanden, keine
  externen Netzverbindungen. Runden überlappen; nicht zu einer Vollsuite addieren.
- [ ] Vollsuite bleibt offen: erster Kernlauf224 bestanden/6 Skips/1 Failure.
  Die eingefrorene Fixture war durch Windows-Archiv-Zeilenenden CRLF statt LF;
  QA-Materialisierung korrigiert, ohne Produktiv-/Testfixtureänderung. Danach
  Cricket-Replays numerisch bitgleich, aber vorbestehender Hockey-`_variant`-
  AST-Freeze-Konflikt bleibt. Kein Gesamtapp-PASS; Cricket unverändert/ausgenommen.
- [x] Codecommit **d47c9b09903b9445541745a583e12c98552bc6bf** auf main gepusht
  und13.10.,11:02CEST per Fast-forward auf dem VPS live. Nur6 gezielt gestagte
  Code-/Testdateien plus Doku; fremdes WIP erhalten. Linux-Offline-Import ok,
  App/Caddy aktiv,7 Timer aktiviert,beide Healthchecks ok. Beide Modell-JSONs
  SHA256-identisch vor/nach Deploy. Kein Backup oder zusätzlicher Sportlauf.
- [x] Bestehenden Qualitätsreport am echten VPS-Bestand rein lesend ausgeführt,
  Stichtag13.10.,11:02:56CEST:131 Modell-/Markt-/Policy-Gruppen,129 mit gescorten
  Ergebnissen;662 Fußballspiele/588 mit Ergebnis,241 Tennis/213 mit Ergebnis,
  365 E-Sport/354 mit Ergebnis,7 Hockey/0 mit Ergebnis.10,423s,84,965MiB
  Gesamtprozess-Peak-RSS (Linux; keine allgemeine RAM-Grenze),90s Timeout,
  Providerverbindungen blockiert. Gespeicherte Historie wurde tatsächlich benutzt.
  Vergleichsbeispiele:Brier v14 Heimmannschaft U2,5=0,132524 (175 Entscheidungen),
  Tennis-H2H=0,217468 (206),E-Sport-H2H=0,231311 (345). KEINE gemeinsame Rangliste,
  kein kausaler Kontextvorteil. Modellversionen/Märkte nicht blind zusammenlegen.
  Exakte Ausgabe `output/football-history-shadow-20261013/quality-report-summary.json`
  außerhalb Git;20 größte Gruppen,keine Behauptung vollständiger Rohdatenexport.
  Preis-/ROI-Stichproben meist0,vereinzelt2–4; kein belastbarer Gewinnnachweis.
- [ ] Neue Capture-Priorität erst beim nächsten REGULÄREN Lauf produktiv belegen.
  Separate3MiB-ORIGINAL-Grenze und Readiness-Streaming/Reuse bleiben offen.
- [ ] Numerische Kontextwirkung weiterhin0 aktiv. Vorhandene ehrliche Quellen
  mit Ergebnissen verbinden, zeitgetrennte Trainings-/Abstimmungs-/Testkohorten
  schaffen; erst den freigegebenen200-Testspiel-Vertrag erfüllen und qualifizieren.
  Alte spätemfangene Spielerlisten nicht in frühere Prognosen zurückdatieren.

Ausgang lokal/main/VPS47fe15ab7524ac34216ec8322c88384b31e4a115. Kein neues
Backup, keine DB-Kopie, Bereinigung, Migration, externe Sportabfrage oder höhere
API-/Speichergrenze. Details `docs/audits/2026-10-13-shadow-historie-und-capture.md`.
Ein anschließender Dokucommit hält ausschließlich den Produktionsnachweis fest;
funktionaler,testverifizierter Code bleibtd47c9b0.

## 12.10.2026 – Spielerbelastung Verein + Nationalteam: Datenverbindung

Fortsetzung auf ausdrückliches „machen“ nach der Dortmund-/Länderspiel-Frage.
Der freigegebene Kontextmodellvertrag bleibt maßgeblich; keine erfundenen
Müdigkeitsabschläge, neuen Datenbanken, Zusatzscans oder Backups.

- [x] Ursache geprüft: native Spieler-ID ist vorhanden, Vereinspfad begrenzt
  Belastung bisher aber auf Vereins-/Grundmodell-Historie.
- [x] Gemeldete Minuten derselben nativen Spieler-ID aus Verein und Nationalteam
  verbinden. Vereinsrolle ausschließlich aus Vereinsauftritten; unbekannte
  Minuten bleiben unbekannt, wiederholte Abrufe zählen kein zusätzliches Spiel.
- [x] Ganze zusätzliche Ereignis-/Revisionspools begrenzt lesen, Grundmodell-
  Historie unverändert lassen; Training und Worker lesen identische Quellen.
- [x] Eigene Merkmalsversion `football-native-player-load-v3` angeschlossen;
  alte v1-Modelle und veröffentlichte Prognosen bleiben unverändert.
- [x] Erholungsgrenze aus erstem tatsächlichem Ergebnisempfang, nicht Anpfiff
  plus erfundener Spielzeit. Später beendete ältere Termine berücksichtigt.
- [x] Detailabruf priorisiert jüngste 14 Tage innerhalb derselben bestehenden
  Grenze: maximal20 native IDs / ein gemeinsamer GET; kein Zusatzscan.
- [x] Unabhängiges Quell-/Diffreview ohne kritischen/wichtigen Funktionsbefund.
  Früherer77/78-Lauf ist KEIN PASS: ein synthetischer26-Fixture-Fall überschritt
  die512KiB-Transportgrenze. Neuer vollständiger24-Fixture-/22-Spieler-Fall
  (reale Liga-Mindeststichprobe) bestand5/5. Grenze/Validator nicht gelockert.
- [x] Exakter isolierter Stand ohne fremdes WIP: **273 Release-/Nachbartests
  bestanden**,229,94s,0 Skips, `output/player-load-20261012/release-final.xml`
  außerhalb Git. Netzwerk während QA gesperrt. Erste Runde272/273, einziger
  Fehler Sandbox-Verbot für atomare HMAC-Testdateiverknüpfung; kompletter
  unveränderter Lauf mit normalen Dateirechten danach273/273. Keine Tests entfernt.
- [x] Codecommit **99e771baee4f2bc115cf12a1d2426f4ea9812e26** committed,
  auf main gepusht und auf dem VPS veröffentlicht; Branch main, App/Caddy aktiv,
  sieben bestehende Timer aktiviert, interner/öffentlicher Healthcheck `ok`.
  Offline-Import auf Linux bestanden. Gespeicherte Wettfinder-/RisikoBet-JSONs
  vor/nach Deployment SHA256-identisch; keine historischen Prognosen/Buchungen
  geändert. Nach regulärem15:02-Lauf veröffentlicht, kein Extra-Lauf/Backup.
  Erster Deploy wurde wegen PowerShell-CR am Skriptende nach erfolgreichem
  Healthcheck code-only zurückgestellt; Übertragung korrigiert, Wiederholung
  vollständig erfolgreich. Keine DB-Rücksetzung oder verlorenen Daten.
- [x] Echte rein lesende Workerprobe15:06CEST bestätigt `effect-unavailable`,
  `not_applied`, kein neuer Snapshot;95 echte `football-original-b1-binding-v1`.
  Die Datenverbindung ist live, numerische Müdigkeitswirkung weiterhin NICHT aktiv.
- [ ] Reale zeitgetrennte Wirkung prüfen und erst dann aktivieren. Lesende VPS-
  Prüfung12.10.,12:40UTC: **0 Effekte /0 Freigaben**. Probe11 Ereignisse:
  381/470 Spielerlisten mit bekannten Minuten,89 unbekannt,0 echte Spielendzeiten.
  Nur Vereinswettbewerbe in dieser Probe; Nationalteam-Abdeckung nicht belegt.
  Das ist keine Vollinventur und keine nachgewiesene numerische Müdigkeitswirkung.
  Ergänzende begrenzte Binding-Prüfung12:50UTC:95 Bindings insgesamt,81 gelesen
  (5,61MiB;14 größere ausgelassen),33 native Ereignisse,7 `captured`,26 `partial`.
  Alle gelesenen Bindings `not-evaluated`. Selbst95 unabhängige Bindings wären
  weniger als200 unberührte Testspiele zusätzlich zu Training/Abstimmung.

Offen vor Aktivierung: vollständige echte Spieler-/Personalfakten, qualifizierter
zeitgetrennter Fit, owning Freigabe, große Capture-/Readiness-Transportgrenzen
und performant begrenzter Spielerzugriff (Produktionsindex bisher nur ereignis-
führend). Keine synthetischen Koeffizienten auf dem Server veröffentlichen.
V2-Pool-, spätere Entscheidungs-, Tennis-POINT- und weitere alte WIP-Dateien
bleiben separat uncommitted/unveröffentlicht. Daily3-Release unten bleibt separat.
Ein anschließender Dokucommit enthält ausschließlich diesen Veröffentlichungs-
nachweis; funktionaler/testverifizierter Code bleibt99e771b.

## 12.10.2026 – Spielblöcke und Daily3: begrenzte Reparatur

Dieser aktuelle Block hat für die Nutzeranfrage zu geöffneten Spielen und leerer
Daily3 Vorrang. Kanonischer Checkout `C:/Projekt/BetBoy/betboy-app`.

- [x] Initial die ersten drei sichtbaren Spiele der geordneten Seite öffnen;
  Nutzerwahl pro Partie durch Sortierung/Filter/Pagination erhalten.
- [x] Daily3: reale qualifizierte Varianten weiterhin alle >=70 %, aber kein
  pauschaler +2pp-Form-/Belagbonus. Normale TOP-Regel unverändert.
- [x] Daily3: Originalkontext des automatischen Tageslaufs bis24h nutzen;
  keine neuen Uhren, Daten oder Effekte, echte Vetos/Missing/Conflicts erhalten.
- [x] Früheste qualifizierte Partie zuerst, nur echte Spiele mit Zeitpuffer
  bis Tagesende einplanen; keine Pflichtzeit für unbekannte Restwetten.
- [x] Neutrale Leermeldung, ehrliches Vorzeichen bei Modellvergleich.
- [x] Root 325 Integrationsprüfungen, unabhängig407, Preisnachbarn89,
  isolierte Kontextgrenzen51, Portal47 bestanden; überlappende Runden.
- [x] Produktivpatch `3dea2d327cc47bf0418a607fede229e38221d82c` committed,
  auf GitHub-main gepusht und auf dem VPS veröffentlicht. Beide Healthchecks ok.
- [x] Genau den committeden Quellstand ohne fremde WIP-Dateien geprüft:
  **500 Release-/Nachbartests bestanden**, 21,18s, `release-clean.xml`.
- [x] Frische reine Produktions-Poolauswertung und Browser-Abnahme:
  derselbe unveränderte Tagespool liefert jetzt **eine** Daily3-Auswahl,
  IF Elfsborg–Halmstad um19:00, 78,3%, letzte exakt passende Quote1,64.
  Im internen Browser sichtbar, Aufklappung und Sortierwechsel bestanden;
  seit Abschluss des Neustarts keine neuen Browserfehler.
- [x] Breiten Offline-Kernversuch begrenzt ausgewertet und bei rund23%
  beendet, **kein Vollsuite-PASS**. Vorbestehender Cricket-AST-Freeze-Befund
  separat reproduziert. Zwölf vor der Vertragsaktualisierung geladene alte
  Daily3-Erwartungen durch frische51 Kontextgrenztests und sauberen500er-Lauf
  nachgeprüft. Abgebrochener Breitenlauf ersetzt keinen finalen Volllauf.
- [ ] Separat: vorbestehenden Hockey-/Cricket-AST-Vertragskonflikt fachlich
  auflösen und danach finalen Volllauf am gemeinsamen nächsten Release ausführen.

Details und QA-Abgrenzung:
`docs/audits/2026-10-12-daily3-und-spielbloecke.md`.

WICHTIG: Die nachfolgenden dirty/untracked Kontextmodell-Arbeiten vom11.10.
sind erhalten, aber NICHT Bestandteil dieses Releases. Sie benötigen weiterhin
die dort beschriebene Implementierung und gemeinsame Releaseprüfung. Insbesondere
werden Verletzungs-/Wetter-/Müdigkeitseffekte nicht als erledigt oder besser
validiert bezeichnet. Keine neue Sicherung, Bereinigung oder API-/Modellrunde.

## 11.10.2026 – Accountwechsel: Kontext-Datenpfade, NICHT veröffentlicht

**Dieser Block ist die offene, separat pausierte Kontextmodell-Arbeit.**
Kanonischer Checkout: `C:/Projekt/BetBoy/betboy-app`.
Ausgangscommit lokal/GitHub-main/VPS in dieser Sitzung geprüft:
`e9eea811b85b124b797c0d995b6cdbbe8187c6b5`.
Die folgenden Produktivänderungen sind **dirty/untracked, noch nicht committed,
gepusht oder deployed**. Ein anschließender Dokumentationscommit veröffentlicht
nur diese Übergabe, nicht die Reparaturen. Keine zusätzlichen Sport-/API-Scans,
Backups, Bereinigungen, Migrationen oder alten Prognose-/Geldänderungen.

### Implementiert, aber gemeinsame Releaseprüfung fehlt

- [x] Fußball: begrenzte native Spieler-Detailanbindung im bestehenden,
  bereits reservierten Lauf. Gemeinsames Budget höchstens vier 20-ID-GETs
  (80 historische Spiele) für alle Batches zusammen; keine Einzel-Retries,
  keine zusätzlichen Jobs. Auswahl nur aus tatsächlich verwendeter Torhistorie,
  höchstens 730 Tage. Alte echte Belege behalten ihren Empfangszeitpunkt.
  Neue tatsächliche GETs werden vom bestehenden Beobachter aufgenommen.
- [x] Original-only Modellrefresh ohne aktiven Capture bleibt kompatibel;
  fremde/nicht aktive Capture-Verbindungen werden weiterhin abgelehnt.
- [x] Spätere Ausfall-/Wetterentscheidung als eigener kompakter nativer Beleg:
  nur echte Prematch-Uhr, Quellhash/Zeilenzahl und Originalbindung.
  Originalveröffentlichungen haben volle Speicherpriorität; erst nach ALLEN
  Batches dürfen maximal 32 Entscheidungen/32 KiB aus dem vorhandenen
  Restbudget gespeichert werden. Readback und tatsächliche Uhr vor Insert
  sowie vor Commit geprüft; kein Rückdatieren, kein Abschneiden späterer Daten.
  Früher echter Proof wird nicht von späterem unknown überschrieben.
- [x] Training verlangt bei späterem Stichtag genau diesen physisch geprüften
  Entscheidungsbeleg; beliebige Caller-Cutoffs und alte mutable Snapshotrefs
  sind keine Nachweise. Alte vierteilige Originalfälle bleiben unverändert.
- [x] Offline Fußball-Readiness/Case-/Fit-/Experiment-Vorbereitung ergänzt,
  explizite Eingabeliste, keine Providerzugriffe oder Aktivierung.
  Produktive Laufzeitdatenbank und bestehende/aliased Outputpfade abgelehnt.
  **Ihr Kohorten-/Speichervertrag muss noch geprüft werden; siehe P1 unten.**
- [x] Gemeinsame Kaderkoordinaten statt nur konkreter Spieler-IDs:
  getrennte gewichtete `loss_exposure_v1`/`gain_exposure_v1`, Ersatzspielerwechsel
  heben sich nicht auf, jede Quelle muss verfügbar und referenziert sein.
  Eigener neuer Featurevertrag `football-native-context-exposure-v2`;
  Standard-v1 bleibt exakt unverändert. Builder, Replay, Readiness, Config und
  reine Effektanwendung unterscheiden beide Versionen. **Worker/Transport
  sind für v2 noch nicht verbunden.** Das ist ein Expositionsproxy, kein
  gemessener individueller Qualitätsverlust und keine automatische Freigabe.
- [x] Tennis: separate tatsächliche POINT-Originalverteilung aus demselben
  Modellaufruf, echte Hold-Parameter und sämtliche Märkte, immutable Tour-State
  und Winneranker geprüft. Beide täglichen Predict-Aufrufer angeschlossen.
  Bestehende Winner-v1-Belege unverändert. Echter Writerclock erst nach
  aufwendiger Vorbereitung; bei überschrittenem Beginn nur POINT auslassen.
- [x] Tennis: vorhandene native Final-Status-/bilaterale Satzdaten plus
  Winnerbeleg nur lesend verbinden, ohne doppelte Ergebniszeilen. Keine
  geratenen Matchzeiten, Aufschlag-Trials, Verletzungen oder natives Best-of.

### Sofortige Fortsetzung / offene technische Fehler

1. **P1: v2 im internen numerischen Football-Pfad verbinden.**
   `football_joint_worker.py::_active_fits` akzeptiert noch ausschließlich v1;
   beide `joint_features`-Aufrufe dort wählen noch Standard-v1.
   `context_transport.py::_feature_binding` erkennt ebenfalls nur v1.
   Beide geprüften Featureversionen mit EXAKTER jeweiliger Coverage zulassen;
   nach Populationsprüfung nur bei eindeutigem Fit dessen Version wählen,
   gespeicherten Pointer mit derselben Version replayen. Kein automatisches
   Approval, keine Änderung der ausgewählten Wahrscheinlichkeit. Dieser Auftrag
   an den Tennisagenten wurde vor seinen Änderungen unterbrochen; Quellen sind
   laut aktuellem Gitstatus noch unverändert. Neuen owning Test ergänzen.
2. **P1: Readiness-Kohorte tatsächlich durchführbar machen.**
   `context_models/football_readiness.py` hat insgesamt nur 64 MiB Input und
   zählt expandiertes Original PLUS Quellen erneut je Event. Gemessene große
   Originale liegen bereits bei ca. 1,16 MiB, dazu native Historien. Damit kann
   ein echtes 200-Testspiel-Set zusätzlich Training/Tuning unmöglich passen.
   Viable begrenzten Offline-/Streamingvertrag und gemeinsame Quellenreuse
   prüfen, nicht einfach Runtimebudget aufblasen. Auch 128-MiB-D2-Admit und
   das Halten aller expandierten Cases gleichzeitig berücksichtigen.
   Dieser Befund ist offen, nicht durch synthetische Sechs-Case-Tests gelöst.
3. Sourcefreeze, vollständige betroffene Module gemeinsam offline testen;
   keine Produktionsbytes während D2-/Hash-/Replaytests ändern. Launcher:
   `C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py` blockiert
   externes Netz. Frisches Basetemp im Projekt; XML speichern.
4. Unabhängiger Abschlussreview, nur explizite Taskdateien stagen,
   commit/push und kontrollierter VPS-Fast-forward ohne Backup/zusätzlichen
   Scan. Altes `output/context-followup-20261011/deploy.sh` NICHT unverändert
   benutzen: dessen Whitelist/Imports sind für die vorige Reparatur.

### Tatsächlich geprüfte QA – keine neue Vollsuite / kein Release-PASS

Runden überschneiden sich, nicht addieren:

- POINT abschließend 329/329, 39,11 s:
  `C:/Projekt/BetBoy/output/context-followup-20261011/point-neighbors13.xml`.
- Native Enrichment 106/106:
  `C:/Projekt/BetBoy/output/hockey-seasons-20261011/enrichment-own05.xml`.
- Letzter Deferred-Owner 16/16 inklusive tatsächlicher Uhren und Same-Key-Fix:
  `C:/Projekt/BetBoy/output/context-readiness-20261011/deferred-04.xml`.
  Unabhängiger finaler Review danach ohne weitere Befunde.
- Readiness vorher 17/17, 216,41 s; vor letzter v2-Vertragsänderung:
  `C:/Projekt/BetBoy/output/context-readiness-20261011/owning-05.xml`.
- Alte Rootintegration/Original-only 60/60, vor v2-Isolation:
  `C:/Projekt/BetBoy/output/context-effects-20261011/root-pool-01.xml`.
- Aktuelle v2-Pool-Owner unabhängig 10/10, 31,82 s:
  `C:/Projekt/BetBoy/output/context-followup-20261011/review-version15.xml`.
- **Unified-Exec 87305 ist beim Sichern beendet: 34 bestanden, 1 fehlgeschlagen,
  369,05 s, Exit 1**, keine Freigabe daraus:
  Rootpool/jointtraining/decisionbinding, Ausgabe
  `C:/Projekt/BetBoy/output/context-effects-20261011/root-pool-02.xml`.
  Meldete einen Fixturefehler (Loopvariable `name` überschrieben). Bereits
  im Test repariert und unabhängige aktuelle 10er-Runde grün; dieser Prozess
  hatte jedoch alte Testbytes geladen. Vollständig gefroren neu ausführen.
- Frühere 80/82 Nachbarrunde hatte zwei mittlerweile reparierte Fakebudget-
  Fixtures. Frühere 102/105 hatte zusätzlich den reparierten capture=None-
  Fallback. Diese Runden ausdrücklich NICHT als bestanden darstellen.

### Reale Produktions- und fachliche Grenze

Nur lesend in dieser Sitzung auf dem VPS bestätigt: 88 Fußball-Originalbindungen,
8 vollständig / 80 teilweise; 4.983 alte Tennis-Winner-Originale. Keine
`context-effect-v1`, `context-approval-v1`, `context-training-case-v1` oder neuen
nativen Decision-/POINT-Artefakte vorhanden (neuer Code ist noch nicht live).
Tennis zuletzt Exit 0; letzter Fußballtageslauf noch alter Exit 15 vom Morgen.

**NICHT erledigt / nicht als bloße Datenwartezeit beschönigen:**
öffentlich eingesetzte qualifizierte Fußballverteilung samt Neukalibrierung/
Auswahlmetadaten; POINT-kompatibler Tennis-Fit/Ergebnis-/Abnahmepfad;
echte native Tennis-Start-/Endzeiten und Verletzungsquelle; ausreichende
unberührte Fußball-Testdaten (mindestens 200 zusätzlich zu Train/Tune);
individuelle Spieler-/Ersatzqualität. Hockey-/Basketball-Ende-zu-Ende-
Kontexteffektpfade bleiben gemäß vorigem Audit offen. Null Effekte aktiviert;
keine bessere Wettqualität aus den Tests behaupten. Cricket bleibt ausgenommen.

Dateiliste, Quellenbegründung und sichere Fortsetzungsdetails:
`docs/audits/2026-10-11-kontext-datenpfade-uebergabe.md`.

## 11.10.2026 – Abendfortsetzung: tatsächlicher Kader und Tennis-Korrekturen

Dieser Block hat Vorrang vor früheren Fertigmeldungen. Verifizierter Ausgang
lokal/GitHub-main/VPS um 19:38 CEST gemeinsam:
`8dfabe964ad382ecc32a2a21ae4c48b926129458`. **Code auf main gepusht und am
11.10. gegen 20:13 CEST auf dem VPS live:**
`dccef90a86491709988bc5adebedebf580ccb78b`. Der folgende reine
Dokumentationscommit hält diese Nachweise fest, keine weitere Codeänderung.
Keine zusätzlichen API-/Sportscans, Backups,
Bereinigungen, Migrationen oder Änderungen alter Prognosen/Geldbuchungen.

- [x] Zweite Fußballursache reproduziert: Auch ein früherer Spieler des
  richtigen Vereins blockierte die Kaderberechnung, obwohl dessen Spiel nicht
  zur tatsächlich verwendeten Modellhistorie gehörte. Der native Zielkader
  wird nun an die verwendeten Spiel-/Teamreferenzen gebunden; die breitere
  Rollenhistorie der wirklich verwendeten und aktuell gemeldeten Spieler bleibt.
  Neue Spieler/Transfers ohne belegte Rolle bleiben unbekannt. Alle Quellen
  werden weiterhin vor dieser Einschränkung vollständig geprüft.
- [x] Zusätzliche Nullgewicht-Kante korrigiert und unabhängig geprüft:
  Ein gültiger historischer Sample mit Gewicht 0 darf weder einen fremden
  ehemaligen Spieler verpflichtend machen noch vorhandene Merkmale blockieren.
  Nullgewicht ist keine Erlaubnis, fehlerhafte Quellen zu akzeptieren.
  Owning-Datei 31 Tests bestanden; unabhängige gemeinsame Ownerprüfung
  57 Tests und 26 zusätzliche Gegenproben bestanden. Diese Runden überlappen.
- [x] Tennis-Belastungsanzeige aus echter SQLite-Historie repariert:
  mehrere Modell-/Policy-Eltern desselben Events verwenden die neueste zum
  Stichtag bekannte Ergebniskorrektur, unabhängig von Zeilenreihenfolge.
  Zurückgenommene Paarung/Spielausgang darf keine alte Belastung reaktivieren;
  ATP/WTA-Eventnummern sind getrennt, tourlose Altdaten werden nicht geraten.
  Keine Beobachtungszeit als Erholung, keine Wahrscheinlichkeitskorrektur.
- [x] Finale gemeinsame Offline-Regression und unabhängigen Review beendet:
  **1.039 bestanden, keine Fehler/Skips**, 700,86 s, Exit 0, 25 ganze Module.
  `C:/Projekt/BetBoy/output/context-followup-20261011/release-01.xml`.
  Eingefrorene Quell-/Testhashes vorher/nachher identisch. Keine neue Vollsuite;
  Agentenrunden überlappen und werden nicht addiert.
- [x] Sieben explizite Dateien als
  `dccef90a86491709988bc5adebedebf580ccb78b` committed und auf main gepusht.
- [x] Nach regulärem Shadow-Abschluss 20:12:17 ein natürliches freies Fenster
  mit über sechs Minuten Reserve genutzt; kein Timer/Job unterbrochen.
  Kontrollierter Fast-forward auf Codecommit, Offlineimports Exit 0,
  App/Caddy und alle sieben regulären Timer aktiv. Beide Healthchecks `ok`;
  während Startup zwei erwartete Verbindungs-Retries, danach erfolgreich.
  Getrackter VPS-Stand sauber; die beiden Serverquellhashes stimmen genau mit
  den kanonischen Git-Blobs überein, nicht nur mit Windows-Arbeitsdateien.
  Wettfinder-JSON vor/nachher bytegleich:
  `a51c9d865ab14db2d7d17971e469cbb029045a7107dd7417f2ff9da17af4298e`;
  RisikoBet-JSON ebenso:
  `acf24df6d14786a744b8fdf30a690bada1b34f84d54e32eb1e3915cdc3350ede`.
  Kein Backup, zusätzlicher Sportscan, Aktivieren eines Effekts oder Löschen.

Separater tatsächlicher Produktionsstatus um 20:13:47 CEST: App gesund;
letzter Shadow-Lauf 20:12:17 Exit 1/`partial`, ein Kandidat ohne frische
Bet365-Providerquote und zwei weiterhin erkannte alte ungültige Evidenzzeilen.
Kein App-Absturz, keine rückwirkende Preis-/Ergebnisreparatur behauptet.
Tennis zuletzt Exit 0; Tageslauf noch alter Timeout. Neues Tageslimit und
neue Hockey-Ligaabdeckung erst im regulären Lauf 12.10.03:35 nachweisbar.

**Wichtige Korrektur der bisherigen Übergabe:** Hockey-/Basketball-Kontexteffekte
sind nicht nur wegen fehlender Daten offen. Ihre produktive, quellengebundene
Trainings-/Ergebnis-/Bewertungs-/Aktivierungskette ist noch nicht implementiert.
Bestehende interne Effektfunktionen und synthetische Tests ersetzen sie nicht.

- [ ] Bestehende NBA/EuroLeague/NHL-Antwortbeobachter tatsächlich in den
  produktiven Ladepfad einbinden, mit explizitem Speicherbudget und ohne
  zusätzliche Abfragen. `capture_team_sports_worker` hat derzeit nur Tests als
  Aufrufer; im normalen Lauf bleibt der Beobachter inaktiv. NBA-Normalisierung
  verwirft zudem vorhandene Saisonwerte. Alte Cachezeilen nicht als neue
  native Empfangsbelege ausgeben.
- [ ] Originalverteilung desselben echten Modellaufrufs vor Spielbeginn
  veröffentlichen und nativ an Quellen, Uhr, Saison/Regeln und Historie binden.
  `build_hockey_live_original` ist nicht produktiv aufgerufen und liefert ein
  `unresolved`-Original; es ist kein abnahmefähiger NHL-Fit. Die vorhandenen
  Live-/Fit-Vertragsversionen sind nicht austauschbar.
- [ ] NHL-Regulär-Ergebnisadapter, quellengebundenen Replay, geschlossenen
  saisongebundenen Fit mit gepoolten gespiegelten Heads sowie passende
  Verlust-/Abnahme-/Aktivierungspfade vollständig gemeinsam ergänzen.
  Aktuelle D1/D2-Fit-Verträge und Evaluator unterstützen nur Fußball/Tennis.
  Keine NHL-Freigabe auf API-Hockey-Ligen übertragen.
- [ ] Echte gemessene Einsatzzeiten, Torhüter-/Aufstellungsstatus und
  tatsächliche Spielzeiten für Belastung erfassen, wo Quellen sie wirklich
  liefern. Vorhandene NHL/NBA-Spielpläne belegen diese Angaben nicht.
- [ ] Tennis: point-kompatible Kontextparameter und echte Zeit-/Verletzungsdaten
  fehlen. Der produktive `serve-points-joint-v2`-Pfad nimmt die alte
  Siegerkorrektur absichtlich nicht an: ein Siegerlabel identifiziert nicht
  zwei Aufschlagparameter. Keine Siegerkorrektur auf alle Wettmärkte umdeuten.
- [ ] Fußball: eigene Trainings-/Abstimmungsdaten und mindestens 200 unberührte
  Testspiele zusätzlich, zeitlich getrennt, nach genehmigter Spezifikation.
  Acht vollständige Bindungen reichen nicht; kein geratenes Wetter-/Ausfallplus.

Details und konkrete Fortsetzungsreihenfolge:
`docs/audits/2026-10-11-kontext-abendfortsetzung.md`.

## 11.10.2026 – Fortsetzung: Ausfall-Kaderbindung und zusätzliche Hockeyligen

Dieser neueste Block hat Vorrang. Ausgang lokal/GitHub/VPS gemeinsam
`4bd5da446c8e19ebc9151e9df7b2cf68fef7134a`. **Code committed, auf main gepusht
und am 11.10. gegen 14:23 CEST auf dem VPS live:**
`090cf93a03cdf329774e6caac2458cd69b1d28f9`. Der folgende reine
Dokumentationscommit hält diesen Nachweis fest; keine weitere Codeänderung.
Keine neuen Backups, zusätzlichen Sport-/API-Scans, Datenbereinigungen,
Prognose-/Ergebnis-Umschreibungen oder Geldänderungen. Cricket unverändert.

- [x] Echter Fußballfehler behoben: historische Spieler fremder Ligateams
  blockierten belegte Zielkader-Faktoren. Alle Quellen weiterhin validieren,
  erwarteten Kader erst danach auf native Zielteam-IDs begrenzen. Fehlende
  Status eigener Spieler bleiben unbekannt; kein Gesundstatus erfunden.
  Eigene Regression 23 bestanden; 13 ganze Nachbarmodule 490 bestanden.
- [x] Eigene API-Hockey-Datenquelle implementiert, Schweizer National League
  und Swiss League zuerst; 20 Name/Land-Kandidaten insgesamt inklusive NHL.
  Native Liga-/Saison-IDs erst aus echtem Katalog, keine geratenen IDs.
  NHL bleibt beim vorhandenen freien Feed, keine doppelte Erfassung.
- [x] Automatischer Tageslauf und manuelle Suche angeschlossen. Getrennte
  Regulär-/OT-/Penaltyscores, eigener Modellvertrag und Saisonpartition,
  native Preisbindung/Publikation, nur lesender Ergebnis-Cacheadapter.
  Keine Übertragung von NHL-Kontexteffekten oder Liga-Kalibrierung.
- [x] Historienbudget acht Saisonabfragen/Lauf, faire statt permanent
  verhungernde Liga-Reihenfolge; kleiner gemeinsamer Katalog-/Tagescache.
  Reale Empfangszeit bleibt, keine rückdatierte historische Genauigkeit.
- [x] Letzte native Rücknahme-Regressionsrunde: 222 bestandene Fälle. Finale
  gemeinsame Regression in 26 ganzen Modulen: **1.088 bestanden, ein vorhandener
  Skip**, 68,12 s, Exit 0; `C:/Projekt/BetBoy/output/hockey-context-20261011/release-05.xml`.
  Runden überschneiden sich; keine neue Vollsuite und keine bessere Wettqualität
  daraus behauptet.
- [x] Reale Daten-/Modell-/Publikationsuhren und Anbieterisolation abgesichert.
  Ganzer Tageslauf mit echtem Kundenleser und Prognosenachweis akzeptiert vier
  Hockeyzeilen. Lange Ladezeiten: bereits gestartete Fußballspiele entfernen,
  gespeicherte Preise neu bewerten, abgelaufene Strict-Overlays entfernen,
  Beobachtungszeiten unverändert lassen. E-Sport-Beobachtungsquote auch nach
  Überschreiten ihrer 24h-Anzeigefrist korrekt neu bewertet, ohne Tippfreigabe.
  Keine zweite Quotenabfrage; ursprüngliche Abrufzähler sind keine neuen Checks.
- [x] Unabhängiger letzter Diff-Abschluss: drei Reviewpfade plus echte ganze
  Owner-/Artefakt-Gegenfälle; gefundene Uhr-/Overlay-Grenzen alle korrigiert.
- [x] Code committen/pushen und ohne Backup/zusätzlichen Scan auf VPS deployen.
  Commit lokal/GitHub/VPS exakt `090cf93a03cdf329774e6caac2458cd69b1d28f9`;
  Offlineimports erfolgreich, getrackter VPS-Stand sauber. App/Caddy aktiv,
  sieben reguläre Timer weiter aktiv, interne/öffentliche Healthchecks `ok`.
  Natürliches freies Fenster nach dem regulären Shadow-Abschluss 14:22:42
  genutzt; keinen Sportjob oder Timer unterbrochen/zusätzlich gestartet.
  Wettfinder-JSON SHA256 vorher/nachher unverändert:
  `a51c9d865ab14db2d7d17971e469cbb029045a7107dd7417f2ff9da17af4298e`;
  RisikoBet-JSON ebenso:
  `acf24df6d14786a744b8fdf30a690bada1b34f84d54e32eb1e3915cdc3350ede`.
  Deployment-Helfer unabhängig geprüft: maximal 336 s einschließlich
  Fehler-Recovery innerhalb des geprüften 360-s-Fensters; kein Datenrollback
  oder Wiederherstellen des vorherigen Codes behauptet.
- [ ] Beim regulären Lauf 12.10.03:35 CEST echte Liga-/Saisonauflösung,
  Accountberechtigung und verwertbare Spiel-/Historienabdeckung prüfen.
  Synthetische Schweizer Test-IDs sind keine echten IDs/Live-Abdeckung.
- [ ] Belastbare numerische Verletzungs-/Wetter-/Müdigkeitseffekte bleiben
  datenabhängig: nur acht vollständig gebundene Fußballereignisse, keine eigene
  200-Spiel-Testkohorte und keine aktive Freigabe. Joint-Worker-Earlyreturn
  bedeutet nicht gemessene Nullmerkmale. Keine Koeffizienten geraten.
- [ ] Zwölf echte Tennisbelege geprüft: Sätze/Games vorhanden, echte
  Dauer/Anfang/Ende fehlen; jüngste Matches nur scheduled/completed, keine
  laufenden Zeitgrenzen. Echte Zeit-/Verletzungsquelle und point-kompatiblen
  Fit samt unabhängiger Abnahme benötigen; keine Receiptzeit als Erholung.

Details: `docs/audits/2026-10-11-ausfaelle-hockey-anbindung.md`.

Aktueller separater Produktionsstatus nach diesem Deployment, 14:23:21 CEST: Der alte
Tageslauf steht noch auf Timeout; neues 60-Minuten-Limit erst beim nächsten
regulären Lauf bewertbar. Fußball-Shadow zuletzt 14:22:42 CEST weiterhin Exit 1;
die bereits geprüften Vorläufe waren `partial`: fehlende frische Bet365-Preise
und zwei alte ungültige Provenienz-/Settlementzeilen. Nicht als erfolgreicher
Gesamtlauf darstellen; alte Belege nicht ändern oder durch Löschen beschönigen.
Tennis letzter regulärer Abschluss erfolgreich (Exit 0, 00:32:29 CEST).
App-/Healthchecks separat `ok`. Der Deploymenterfolg belegt keine aktive
Verletzungs-/Wetter-/Müdigkeitswirkung oder bessere Wettqualität.

## 11.10.2026 – Fortsetzung ab 10:38 Uhr: Inventur, Vergleichsmodell, NHL

Dieser Block hat Vorrang. Ausgang lokal/GitHub/VPS gemeinsam
`d26c1346ad727f825bc6639aeef4d48e13d43937`. **Reparaturen committed, auf main
gepusht und am 11.10. gegen 13:12 CEST auf dem VPS live:**
`6474a376bb1a1029f419c7d774ed6d463221169d`. Ein anschließender reiner
Dokumentationscommit hält diesen Nachweis fest und ändert keinen Produktivcode.
Kein Backup, zusätzlicher Sport-/API-Scan, Löschen alter Belege oder Geldänderung.

- [x] Tages-Timeout näher belegt: 2.547.645 physische Receipts; direkter
  kanonischer Decoder ohne doppelte Baumkopie/Serialisierung, gleiche Verträge,
  Hashes und volle Inventur. Begrenzte VPS-Leseprobe rund 19 % schneller;
  4.550 unabhängige Oraclefälle ohne Akzeptanz-/Ergebnisunterschied.
- [x] Identische abgeschlossene Tennis-Draw-Wiederholungen innerhalb genau
  eines Capture-Batches nicht erneut speichern. Erste tatsächliche Empfangszeit
  bleibt; echte Revisionen, Live-Timing und neue Drains bleiben getrennt.
  Fehlerhafte Siegerflags führen nicht mehr zum Hashabbruch, kein geratener Sieg.
- [x] Eigene gegnerbereinigte Fußballrechnung im Original-Publisher angebunden:
  alle 40 Tormärkte aus einer Verteilung, Quellen/Uhren/Revisionen gebunden,
  eigener Modellhash, etwa 3 KB statt kopierter Historie, maximal 16 KiB,
  vorhandenes Bytebudget: alle Original-Batches zuerst, danach versiegelter
  Worker und optionale atomare Vergleiche ausschließlich aus Restbytes. Der
  unabhängig gefundene Zwei-Batch-Budgetfehler ist damit behoben; 84 betroffene
  und 44 unabhängige Fälle bestanden. Spätes Original wird
  nicht durch den optionalen Vergleich blockiert. **Vergleich, nicht aktiv**.
- [x] NHL-Saisonvertrag 2026/27 belegt und strikt getrennt von 2025/26.
  Keine alte Effektfreigabe übertragen; weitere Liga-IDs nicht geraten.
- [x] Mathematischer Speicherfehler behoben: Hockey-Gesamtsieg muss zwischen
  Regulationssieg und Regulationssieg plus Remis liegen. Native Chancen bleiben
  unverändert. 227 Tests + vier Untertests; unabhängiger Review 126 Tests und
  10.000 Grenzfälle, kein verbleibender Befund. Alle 12.706 gespeicherten
  Snapshots hash-/ID-geprüft, kein Konflikt mit dem neuen Guard.
- [x] Alte `football:event_snapshot_ambiguous`-Meldung konkret geprüft:
  Fixture 1565480, dieselben Teams, verschobener Start. Bereits deployter
  `5467b88` behandelt dies. Vier Kandidaten und 35 Run-Mitgliedschaften
  unverändert valide; kein weiterer Quellcodefix oder geratene Abrechnung.
- [x] Separater Portal-QA-Runner: 47 Tests grün, keine echten externen Aufrufe.
- [x] Begrenzte Laufzeitreserve 60 statt 45 Minuten anhand echter Fortschritte
  und Vortage 27/36/44 Minuten. Start 03:35 einmal täglich, API-/Byte-/Spielgrenzen
  gleich. 84 Serverjobtests bestanden, sieben vorhandene Skips; Unit auf VPS
  installiert, `TimeoutStartUSec=1h`, exakter geprüfter SHA256 bestätigt.
  Kein Erfolg des nächsten Gesamtlaufs vorwegnehmen.
- [x] **Vollsuite vollständig ausgeführt:** `full-04.xml`, ungefiltert und mit
  blockiertem externem Netzwerk: **13.191 bestanden, drei fehlgeschlagen,
  97 vorhandene Skips, 115 Untertests bestanden**, 54:25 Minuten. Kein einzelner
  fehlerfreier Vollsuite-PASS. Die drei verbleibenden Fehler waren veraltete
  Testfixtures: zwei mischten alte Kartenhashes mit dem neuen Faktenanhang;
  vollständige historische Payloads und alte IDs sind nachweislich unverändert.
  Der dritte zählte den neuen Sortierfilter als zusätzliche Spielauswahl.
  Nur diese zwei Testdateien korrigiert, alte Pins/Assertions erhalten und
  vollständige historische Payload-SHA-Pins ergänzt. Owning Module danach
  **acht plus 16 Tests grün**. Alle 725 übrigen eingefrorenen Quell-/Testdateien
  sind bytegleich, insbesondere sämtliche Produktionsquellen.
  Drei beendete Vorversuche zählen nicht als PASS. Frühere veraltete
  Decoderzähler, Unit-Hash-Pins, Anzeige-Mocks und RisikoBet-Renderadapter sind
  bereits erklärt und vollständig geprüft; keine Fälle ausgefiltert,
  keine Produktionsprüfung gelockert.
- [x] Abschließende kombinierte Nachbarregression auf dem endgültigen Teststand:
  **619 bestanden, sieben vorhandene Plattform-Skips**, 176,15 s, Exit 0,
  13 vollständige Module, `release-neighbors.xml`, externes Netz blockiert.
- [x] Finalen Diff und Testkorrekturen unabhängig geprüft: 24 weitere Tests
  bestanden, alte komplette Payloads unabhängig reproduziert. Ausschließlich
  eigene Code-/Test-/Auditdateien committed und gepusht; VPS-Fast-forward,
  Offline-Imports und App-Neustart Exit 0 ohne Backup, Migration oder Zusatzscan.
  App/Caddy aktiv, beide Healthchecks `ok`, alle sieben regulären Timer aktiv;
  tägliches Backup weiterhin deaktiviert. Wettfinder-/RisikoBet-JSON bytegleich.
  Der alte Tageslauf bleibt korrekt `failed/timeout`, der Shadowlauf weiterhin
  ohne aktuellen passenden Providerpreis. Kein `reset-failed`/Schönrechnen.
- [x] Frischer interner Browser-Reload 13:13:38 CEST vollständig gerendert:
  sieben Hauptbereiche, sechs Sportarten, Startzeit-Standard; null neue
  Warnungen/Fehler seit Reload. Kurze Neustart-Verbindungsfehler separat
  belassen. Noch keine neuen Tagesauswahlen, kein Kartenqualitäts-PASS behauptet.
- [ ] Nach Veröffentlichung regulären Tennislauf **12.10.00:05 CEST** und
  Wettfinder **12.10.03:35 CEST** prüfen. Kein erfolgreicher neuer Gesamtlauf
  allein aus der 512-Receipt-Beschleunigungsprobe ableiten.
- [ ] Aktiver Fußball-Modellwechsel/Qualitätsnachweis weiterhin offen:
  **88 Originalbindungen, nur acht vollständig quellengebundene einzigartige
  Ereignisse**; keine neue Kalibrierung/Freigabe, keine 200-Ereignis-Testkohorte.
- [ ] Verletzungs-/Müdigkeits-/Wettereffekte nicht numerisch fertig: kein
  Effekt-/Freigabeartefakt. Tennis hat 805 passende Endergebnisereignisse,
  aber zwei echte Merkmalsproben ohne ausreichend abgegrenzte Satz-/Minutenlast;
  dritte Probe lief ins 100-Sekunden-Budget. Keine Gesamtabdeckung behaupten,
  Empfangszeitdifferenzen nicht als körperliche Erholung verwenden.
- [ ] Schweizer/weitere Top-20-Hockeyligen und echte Shadow-Schlusspreise
  weiterhin Daten-/Adapterabhängigkeit. Idle-Exit 0 ersetzt keinen Preisnachweis.

[Genaue Belege und Abnahmegrenzen](docs/audits/2026-10-11-kontext-fortsetzung.md).
Ungetrackte fremde Audit-, Browser-, Landing- und Stripe-Arbeit bleibt erhalten.

## 11.10.2026 – Abschluss 10 Uhr: Sortierung, Erklärung und Ergebnisidentität

Dieser Block hat Vorrang. **Codecommit `5467b888b38fe0ed3b350471511d8bf2245351cc`
ist committed, auf main gepusht und auf dem VPS live.** Ausgang war
`8052ff916add24b27f5e517513b610490b5dae62`. Ein folgender Dokumentationscommit
ändert keinen Produktivcode. Keine neue Sicherung oder zusätzlicher Sport-/API-Scan.

- [x] Startzeit aufsteigend als Standard in den Empfehlungssichten; optional
  Wahrscheinlichkeit. Spielgruppen bleiben zusammen, ganze Spielblöcke werden
  paginiert. Auswahlpool, Modellwerte und bestätigte Linien bleiben unverändert.
  Daily3 behält die chronologische Einsatzfolge. Reine Spielpläne bieten keine
  erfundene Wahrscheinlichkeitssortierung.
- [x] Hockey/Basketball: Angriff/gegnerische Defensive/Spielort beziehungsweise
  Gegnerstärke/Spielort aus **demselben bereits gefitteten Modell** als kurze
  Begründung transportiert; echte Gegenargumente sichtbar. Kein zusätzliches
  Fitten, keine neue Wahrscheinlichkeit und keine künstliche Mehrfachabstimmung.
  Alte Originalpakete bleiben zweifaktorig und unverändert; der zusätzliche
  Faktenanhang gehört nur zu neuen, quellengebundenen Snapshots. Alte Karten
  erhalten keine nachträglich erfundene Begründung.
- [x] Fußball-Terminrevisionen: natives Ergebnis muss Spiel-ID, Heim/Gast und
  einen eingefrorenen Anstoß belegen. Der Runner prüft dies erneut. Modellzeit
  **und** Datenstichtag müssen vor dem tatsächlichen nativen Start liegen;
  ein später gebautes Modell wird nicht rückwirkend als Gewinn abgerechnet.
- [x] Zehn Tennislücken konkret diagnostiziert: geänderte Teilnehmer unter
  derselben nativen ID. Eigene `identity_conflict_outcome_events`-Diagnose,
  weiterhin `partial`, ohne Zuordnung des fremden Gewinners. Originale,
  Ergebnisbelege und Geldbuchungen werden nicht gelöscht oder umgeschrieben.
  Erst der nächste normale Lauf veröffentlicht diese neue Diagnose.
- [x] Eigener Readiness-SQL-Zeitbudgetabbruch korrekt als Timeout statt als
  beschädigte Datenbank klassifiziert. Fremde SQL-Interrupts bleiben Fehler;
  abgelaufener Handler kann nicht mehr den Rollback unterbrechen.
- [x] Gemeinsame Abschlussrunde: **1.517 Tests + 36 Untertests bestanden,
  ein erwarteter Windows-Symlink-Skip**, 106,24 s, Exit 0, externes Netzwerk
  gesperrt. 34 betroffene/Nachbarmodule, kein neuer Vollsuite-PASS.
  Unabhängige Reviews fanden Prozent-/Bruchsortierung und verspätete
  Forecast-Abrechnung; beide reproduziert und korrigiert, Abschluss ohne
  weiteren konkreten Blocker.
- [x] Interner Browser: tatsächliche Sortierumschaltung mit markierten
  Testdaten, Desktop/390/320 px ohne Überlauf; keine Console-Warnungen/-Fehler.
  Frische Produktionsseite lädt mit Startzeit-Standard ohne Browserfehler.
  Heute zeigt sie weiterhin kein neues automatisches Ergebnis, siehe unten.
- [x] Deployment ohne Datenmigration/Backup/Zusatzscan, Fast-forward Exit 0.
  App/Caddy aktiv, interner und öffentlicher Healthcheck `ok`; beide gespeicherten
  Prognose-Dateien vor/nach Deploy bytegleich. Sieben Timer bleiben aktiv.
- [ ] Vollständigen Wettfinderlauf **12.10.03:35 CEST** nachprüfen. Der heutige
  Lauf hatte Timeout; ein reparierter Lookupindex und grünes Software-QA sind
  noch kein erfolgreicher Tageslauf oder Nachweis neuer heutiger Auswahlen.
- [ ] Tennis **12.10.00:05 CEST**: Modellfehler, gespeicherte Prognosen,
  `unresolved_outcome_events` und getrennte `identity_conflict_outcome_events`
  prüfen. Exit 0 darf trotz Teilnehmerkonflikten nicht als volle Abdeckung gelten.
- [ ] Fußball-Shadow: reguläre Läufe weiterhin Exit 1 wegen fehlender aktueller
  Bet365-Quote mit Providerzeit. Zwei alte Shadow-Zeilen haben ungültige
  Quoten-/Abrechnungsprovenienz und bleiben vom Qualitätsnachweis ausgeschlossen.
  Keine Abrufzeit als Providerzeit erfinden und keine alten Zeilen schönrechnen.
- [ ] Aktiver neuer Fußball-Gegnerstärkevertrag und empirisch geprüfte
  Verletzungs-/Müdigkeits-/Wettereffekte fehlen weiterhin. Heutiger rein lesender
  VPS-Bestand enthält **keine `context-effect-v1`- oder `context-approval-v1`-
  Artefakte**. Bereits vorhandener Quell-/Training-/Registrypfad ersetzt keine
  echte zeitgebundene Kohorte. Keine Koeffizienten oder Qualität erfinden.
- [ ] Weitere Hockeyligen/Schweiz/Top20: weiterhin nur NHL-Discovery und
  Ergebnis-/Preisadapter. Kontextverträge auf `20252026` gebunden; aktuellen
  Saison-/REG-/OT-/SO-Vertrag und native Liga-IDs vor jeder Erweiterung belegen.

[Abnahme, Grenzen und genaue Nachweise](docs/audits/2026-10-11-sortierung-und-begruendung.md).
Vorhandene ungetrackte Audit-/Browser-/Stripe-Arbeit bleibt unberührt.

## 11.10.2026 – Fortsetzung 09 Uhr: fachliche Auswahl und Nachtlauf

Dieser Block hat Vorrang. Ausgang lokal/GitHub/VPS gemeinsam `02943e9`.
Keine künstliche „zwei Argumente“-Abstimmung: Strategie und tatsächliche
mathematische Grundlage müssen passen; drei abgeleitete Torzahlen sind kein
dreifacher Nachweis.

- [x] Echter Nachtlauf nach Accountwechsel geprüft: Wettfinder heute
  **45-Minuten-Timeout**, kein vollständiger neuer veröffentlichter Tageslauf.
  App/Healthchecks trotzdem gesund. Nicht aus alten Übergaben Erfolg ableiten.
- [x] Neue echte Formdaten über beide Lader geprüft: 129 Snapshots,
  43 Kontextverweise, zwei strukturierte Formanhänge; IDs/Payloads unverändert.
- [x] Fehlender Ergebnis-Lookupindex ergänzt; alte/neue DB und identische
  Queue-/Ergebnisdaten geprüft. Interne stderr-Zeiten für ausgewählte Phasen,
  ohne Providertexte, Tokens oder Änderungen der Kundendokumente.
- [x] Direkt betroffene Runde 199 grün. Breitere identische 526 Fälle nach
  Windows-Umgebungskorrektur **519 bestanden, sieben bestehende Skips**;
  unabhängiger Review ohne blockierenden Befund. Kein neuer Vollsuite-PASS.
- [x] Codecommit **`be1ecb3`** auf main gepusht und per geprüftem Fast-forward
  auf den VPS übernommen. Fehlender Ergebnisindex dort ausdrücklich angelegt:
  86.300 Prognosen, 52.441 Quotenbelege, 4.628 Ergebnisse und 816 Läufe
  unverändert; alle acht Immutabilitätstrigger identisch.
- [x] App/Caddy, sieben reguläre Timer und beide Healthchecks nach Deploy
  gesund; Backup weiter deaktiviert. Prognose-Dateien bytegleich. Ein
  nachgelagerter CR-Zeilenumbruchfehler im Helfer ergab Exit 127, **nachdem**
  Fast-forward, Index und Healthprüfungen abgeschlossen waren. Separater
  Nur-Lese-Nachcheck bestätigt den echten Zustand; nicht als völlig fehlerfreien
  Helferlauf zählen. Transport künftig `.TrimEnd([char[]]"`r`n")` vor stdin.
- [x] Final kombiniert 248 Tests grün (49 Modell- + 199 Betriebsfälle).
  Zwei unabhängige Reviews inklusive Nullwahrscheinlichkeits-Grenzfall fertig.
  Neuer Modellbaustein bleibt ausschließlich offline, aktive Auswahl unverändert.
- [ ] Nächsten normalen Wettfinderlauf **12.10.03:35 CEST** nachprüfen.
  Der Index behebt einen bestätigten inneren Vollscan, noch keinen belegten
  Gesamtlauf-Timeout. Fußball-Spielereinsatzhistorie bleibt weiterer Verdacht.
- [x] Aktives Fußball-Grundmodell fachlich geprüft: historische Gegnerstärke
  fehlt systematisch. Hockey hat bereits Angriff/Defensive/Spielort gemeinsam;
  Torerwartung ist kein eigenständiger Beweis neben daraus berechneter Siegchance.
- [x] Neuer isolierter API-FT-Gegnervergleich: 49 Softwaretests grün,
  historische Gegnerstärke statt bloßer Tor-/Siegzählung. 730-Tage-Grenze,
  exakt gleiche Eingabepräfixe und keine späteren Ergebnis-/xG-Revisionen.
- [x] Echte retrospektive Paarprobe aus vorhandenen Liga-Belegen: 72 von
  100 versuchten Zielspielen, 28 mangels acht vorheriger Teamspiele ausgelassen.
  Brier/Logloss in beiden Ligen niedriger, unveränderte Parameter.
  Individuelle Empfangszeiten fehlen: **kein prospektiver Qualitätsnachweis**.
  **Noch kein aktiver Modellwechsel**, keine besseren Tipps versprechen.
- [ ] Eigenen nachvollziehbaren Fußball-Modellvertrag integrieren; alte
  `football-goals-v1`-Gewichte/Prognosebelege nicht mit neuen Torwerten vermischen.
  Qualität getrennt prüfen, statt bloß Auswahltexte ausführlicher zu machen.
- [ ] Numerisch nachgewiesene Verletzungs-/Müdigkeits-/Wettereffekte,
  zehn Tennis-Ergebnislücken und alte RisikoBet-Ergebnismehrdeutigkeit offen.
  Sortierung/weitere Eishockeyligen ebenfalls nicht erledigt.

[Prüfbericht und genaue Abnahmegrenzen](docs/audits/2026-10-11-auswahl-und-nachtlauf.md).
Vorhandene ungetrackte Arbeit erhalten; zusätzliche Rohdaten nur unter
`C:/Projekt/BetBoy/output/winner-audit-20261011/`, kein Datenbankarchiv.
Ein folgender reiner Dokumentationscommit aktualisiert diesen Nachweis, keine
weitere App-/Datenänderung. Codebasis der Reparatur ist `be1ecb3`.

## 11.10.2026 – echte Teamsport-Formkarten und Abschlussprüfung

Fortsetzung des Boston-Fixes; Formrelease `fa42917` und ergänzender
Kontextreferenz-Fix **`55f35e7` live** (11.10.00:42 CEST), GitHub/main und VPS
abgeglichen. Dieser Block hat Vorrang vor älteren Ständen. Ein nachfolgender
reiner Dokumentationscommit kann einen neueren HEAD haben; Produktivcode bleibt
`55f35e7d9767be33eddfe9cff1eb93c3ad8094c1`.

- [x] Ursache der fehlenden Formkarten reproduziert: bereits vom Modell
  verbrauchte Spielzeilen gingen im Adapter verloren; alter UI-Test umging
  den Producer. Jetzt begrenzter strukturierter Anhang mit höchstens zehn
  echten Spielen pro Team, ohne zusätzliche Abfrage oder Prognoseberechnung.
- [x] Adapter → SQLite → JSON → beide Lader → Formkacheln für Basketball und
  Eishockey geprüft. Gegner, tatsächlicher Endstand, Datum und Sieg/Niederlage;
  NHL-Namen nur exakt quellen-/liga-/ID-gebunden. Keine Prosa-Rekonstruktion.
- [x] Sport/Quelle/Wettbewerb/Teilnehmer/Zeiten/Modellhash strikt gebunden;
  beide Speicherprüfer gegen den im Review gefundenen Bindungsfehler gehärtet.
  Originalprognosen und alte Snapshot-IDs bleiben unverändert. Neue Anhänge
  sind neue unveränderliche Revisionen, keine rückwirkenden Änderungen.
- [x] Nach allen Korrekturen 266 betroffene Tests + vier Untertests bestanden;
  separater korrekter Django-Runner: 47 Portaltests. Unabhängiger finaler
  Code-Gegentest: acht Transporttests grün, keine verbleibenden Findings.
- [x] Interner Browser mit klar markierten isolierten Testdaten: 5/10-Spiele-
  Umschaltung, Gegnerliste, Desktop/390/320 Pixel ohne horizontalen Überlauf
  und ohne Warnungen/Fehler. Kein zusätzlicher Produktions-Sport-/API-Lauf.
- [x] Vollständige Sportsuite beendet und alle gemeldeten Fehler nachgeprüft:
  12.909 bestanden, neun Testaufbaufehler, 97 Skips, 115 Untertests, Exit 1
  (52:13 min). Die neun fremden Quellen-Fixtures behielten einen unpassend
  gebundenen Formanhang; korrekte frühzeitige Domain-Ablehnung. Nur Testaufbau
  repariert, keine Produktionsguards gelockert und kein Produktionscode geändert.
  Alle neun Originalfälle plus neun neue Frühablehnungsfälle und die gesamten
  betroffenen Module frisch: 586 bestanden (20,04 s), Exit 0; unabhängiger Review
  ohne weiteren Befund. Getrennte Läufe, kein einteiliger Vollsuite-PASS.
- [x] Diagnose des vorangegangenen Runnerabbruchs: 13.015 Tests gesammelt.
  Lauf mit 60-Sekunden-Faulthandler
  bei ~22 % nativ abgestürzt (`0xC0000005`), kein PASS. Exakter Einzeltest
  reproduziert den Crash beim Dump, ohne Dump bestanden (103,31 s).
  Vollständiger Lauf ohne periodischen Diagnose-Dump abgeschlossen wie oben;
  keine Tests ausgeschlossen. Logs unter
  `C:/Projekt/BetBoy/output/team-form-20261010/`.
- [x] Formrelease `fa42917` per Fast-forward ohne Backup/Scan/Migration live;
  App/Caddy aktiv, beide Healthchecks `ok`, Wettfinder-/RisikoBet-Artefaktbytes
  unverändert. Regulärer Tennisjob vorher 00:32:29 CEST mit Exit 0 beendet;
  kein laufender Sportdienst unterbrochen. Backup weiterhin abgeschaltet.
- [x] Echte gespeicherte Snapshots deckten einen bereits in `2ad2ba6`
  vorhandenen separaten Ladefehler auf: Automationslader ließ `context_ref`
  weg und rekonstruierte dadurch die falsche Snapshot-ID. Zwei Codezeilen
  stellen die Referenz strikt wieder her; ID-/Schema-Prüfungen unverändert.
  13 neue Regressionen: zunächst neun Fehler/vier bestanden, danach breiter
  Offline-Lauf **728 bestanden (83,26 s)**. Review-Testlücke durch nichtleeren
  kausalen Faktor geschlossen; ganze geänderte Datei erneut **32 bestanden**.
  Kein einteiliger grüner Vollsuite-Lauf nach diesem zusätzlichen Codefix.
- [x] Kontextreferenz-Ergänzung gepusht und per geprüftem Fast-forward ohne
  Backup/Scan/Migration deployt. Beide Lader auf **allen 151 gespeicherten
  Snapshots** geprüft: 104 Fußball, 38 Tennis, sechs E-Sport, drei Eishockey;
  **38 Kontextverweise** erhalten, alle ursprünglichen IDs unverändert.
  Prognosedateien bytegleich, App/Caddy aktiv, beide Healthchecks `ok`.
  Sieben reguläre Timer aktiv/aktiviert; Backup-Timer inaktiv/deaktiviert.
- [ ] Frischer Produktions-Browsercheck nach Unterbrechung: bestehender
  interner Tab konnte nicht an seine Webview angebunden werden; erneute Bindung
  ebenso fehlgeschlagen. Öffnen im Codex-Panel nur `queued`, nicht ausgeführt.
  Daher keinen frischen Browser-PASS behaupten. Vorheriger isolierter
  Desktop-/390-/320- und Formbedienungscheck bleibt separat belegt.
- [ ] Neue echte Formanhänge aus dem nächsten regulären Modelllauf in
  Produktion nachweisen. Alte BOS/PHI-Daten enthalten diesen Anhang nicht und
  werden nicht aus Text oder fremden Historien nachträglich ergänzt.
- [ ] Separater Shadow-Preisnachweis: 11.10.00:02-Lauf auf altem `2ad2ba6`
  meldete Teilabschluss, weil Ereignis 1550985 keine frische Bet365-Quote mit
  Providerzeit hatte. Wiederholung regulär, kein Crash, kein Zusammenhang zum
  Formpatch. Fehlenden Preis nicht erfinden; nicht alle Dienste als erfolgreich
  darstellen, nur weil App/Healthchecks gesund sind.
- [x] Späterer regulärer Shadow-Lauf 00:42:09–00:42:10 CEST mit Exit 0 beendet;
  dieser Exit allein belegt keinen nachgeholten frischen Preis für 1550985.
- [ ] Ältere RisikoBet-Abrechnungsmehrdeutigkeit separat klären: letzter
  Wettfinderlauf 10.10.03:35–04:19 Exit 1 / `degraded`, operativer Fehler
  `football:event_snapshot_ambiguous`; 136 terminale Abrechnungen, 272 ungelöste
  Kandidaten. Nicht durch den Kontext-Laderfix oder Formtransport verursacht;
  keine Ergebnisse/Geldbuchungen raten oder bestehende Belege löschen.
- [x] Echter Tennisabschluss 11.10.00:32:29 CEST direkt im vorhandenen Journal
  bestätigt: **82/82 verarbeitet, 74 neue Prognosen, Scan/Gesamt OK, Exit 0**.
- [ ] Tennis-Ergebnisabdeckung weiter offen: Kontextaufnahme `partial`,
  `native-outcome-unavailable`, **zehn unresolved_outcome_events**. Erfolgreicher
  technischer Runner ist nicht gleich vollständige Ergebnisabdeckung.

Keine Änderungen an Modellchance, Marktlogik, Reihenfolge oder Geldkonten.
Sortierung, zusätzliche Eishockeyligen und empirische Kontexteffekte bleiben
getrennte offene Arbeiten. [Prüfbericht](docs/audits/2026-10-10-teamsport-formtransport.md).

## 10.10.2026 – BOS/PHI: echter Preis und nachvollziehbarer Kurzcheck

- [x] Produktionsursache belegt: Tagesstand 04:12 CEST stammt vor dem
  Preisproducer-Fix; Eishockey meldete dort `disabled_for_model_only_tips`.
  Der alte Teamsport-Cache enthielt keinen BOS/PHI-Preis. Code-Deploy allein
  erneuert gespeicherte Preise nicht.
- [x] Genau ein Preis-only-Check des bestehenden BOS/PHI-Modellereignisses
  `2026020070`: korrektes API-Sports-Spiel, Sieger inklusive Verlängerung und
  Penaltyschießen, Boston **1,75**, Philadelphia **2,25**, keine Abruffehler.
  Wettfinder-/RisikoBet-Prognosedateien bytegleich; kein neuer Modell-/Sportscan.
- [x] NHL-Vollnamen ausschließlich aus geprüftem Manifest und exakter nativer
  NHL-ID-/Quellen-/Liga-/Aliasbindung, keine unscharfe Identitätszuordnung.
  Vollnamen sind reine Renderfelder; Original-IDs, BOS/PHI, Auswahl, Modellchance
  und Quotenbindung bleiben unverändert.
- [x] Auswahlgebundene kurze Begründung: Boston 3,09 erwartete Tore in regulärer
  Spielzeit gegenüber Philadelphia 2,60, Abstand 0,49. Die unveränderten 57,7 %
  betreffen den Gesamtsieger; Philadelphias Gegenchance beträgt 42,3 %.
  Kein erfundener Verletzungs-, Torhüter-, Wetter- oder Formvorteil.
- [x] Gegenseite, Gleichstand, ungültige Faktoren, fremde Ereignisse sowie
  `St. Louis Blues` auf beiden Seiten regressionsgeprüft. Punkt im Teamnamen
  darf den sichtbaren Kurzcheck nicht abschneiden.
- [x] Nach allen Codeänderungen **677 Tests und vier Untertests bestanden**
  (16,97 s). Unabhängiger Abschlussreview: kein verbleibender konkreter P1/P2.
- [x] Codecommit `8d97a61` auf main gepusht und am 10.10. um 13:12 CEST
  auf dem VPS per Fast-forward veröffentlicht. App/Caddy aktiv; beide Healthchecks
  `ok`, Wettfinder-/RisikoBet-Artefakte bytegleich. Vorabcheck wartete auf den
  normalen Shadow-Termin statt einen laufenden Dienst zu unterbrechen.
- [x] Frischer interner Produktionsbrowser: Boston Bruins / Philadelphia Flyers,
  Sieger inklusive Verlängerung/Penaltyschießen, 57,7 %, echte Quote 1,75 und
  vollständige Begründung sichtbar. Gegenargument geöffnet: Philadelphia 42,3 %.
  Bei 1280, 390 und 320 Pixeln kein horizontaler Seitenüberlauf. Screenshots
  außerhalb Git unter `C:/Projekt/BetBoy/output/hockey-card-20261010/`.
  Keine neuen Konsolefehler nach Reload; Verbindungsfehler während des Neustarts
  sind getrennt und nicht als nachträglicher Seitenfehler gewertet.
- [ ] Ergänzende Sportsuite nicht abgeschlossen, daher kein Vollsuite-PASS:
  `C:/Projekt/BetBoy/output/hockey-card-20261010/sports-fullsuite-unrestricted.log`.
  Der erste Sandboxfehler war WinError 5 beim Test einer temporären SQLite-
  Prüfkopie; derselbe Einzeltest außerhalb der Sandbox bestanden. Repositoryweite
  Sammlung zusätzlich durch fehlendes Django im Portal-Testumfeld blockiert.
  Wiederholung außerhalb der Sandbox bei 8 % ohne ausgegebenen Fehler gestoppt;
  keine Testprozesse dieses QA-Laufs mehr aktiv. Frische 677er-Regression ist
  vollständig grün; der Anzeige-Fix ist keine Freigabe der gesamten App.
- [x] Separate strukturierte Eishockey-/Basketball-Formlücke im Code behoben;
  aktueller Nachweis und noch offene Veröffentlichung im obersten Block.
  Keine Spiele aus Prosa zurückparsen oder erfinden.

Vorige Anfrage weiterhin offen: globale Sortierung Startzeit aufsteigend oder
Modellchance absteigend sowie Eishockey-Ligaabdeckung über NHL hinaus. NHL ist
angebunden; Schweizer National League/Top-20-Ligen nicht als erledigt darstellen.
Der zuvor vorgelegte Sortierentwurf ist noch nicht ausdrücklich freigegeben.
Keine Sicherung, Migration, Bereinigung, Modelländerung oder Kontobuchung hier.

## 10.10.2026 – Quotenabruf statt Kaschieren fehlender Preise

Die neue manuelle Filterung war keine vollständige Preisversorgung. Ursachen
mit Originalreproduktionen belegt und begrenzt repariert:

- [x] Automatischer Fußball und Preis-only-Helfer prüfen den vollständigen
  zuordenbaren Modellpool (maximal 1.200 Fixtures), statt nur zehn Spiele.
  Ein Request pro Spiel, bestehender Kontingentschutz unverändert.
- [x] Tennis behält beide tatsächlich gelieferten Siegerseiten für bis zu
  1.200 native Ereignisse / 2.400 Seiten / 8 MiB, statt zehn Ereignissen.
  Einmaliges Batch-Merge; zu große Pools melden die Grenze vor HTTP.
- [x] Explizite manuelle Tennis-Suche holt reale H2H-Preise nach dem Modelllauf
  und bewahrt sie im passenden Job-/Sitzungsfenster. Kein Request bei Filter-
  oder Navigationsänderung, kein Secret im Ergebnis, keine Globalcache-Mutation.
- [x] Fußball-Doppelte-Chance-Aliase 1X/X2/12 exakt zugeordnet, Halbzeit-/
  falsche Ereignis-/Seitenangebote weiterhin abgelehnt.
- [x] Tatsächliche Antwortzeiten statt Batchbeginn; Preis-only bewertet erst
  bei Abschluss. Rendern erneuert keine Original-Beobachtungsuhr.
- [x] Vorhandene E-Sport-/Basketball-/Eishockey-Preisproducer wieder angebunden,
  nur Produktion + Key + Modell/Snapshot, bestehende Cache-/Budgetgrenzen.
  Keine erfundenen nativen Preisversuchszähler durch Cacheübernahme.
- [x] Nach allen Änderungen **724 frische Regressionstests bestanden (39,30 s)**.
- [x] Unabhängiger finaler Review ohne offene konkrete P1/P2; zehn separate
  In-Memory-Gegenprüfungen bestanden.
- [x] Codecommit `92cb4d2` auf main und VPS live, Deployment 12:43 CEST.
  App/Caddy und beide Healthchecks ok, sieben Timer geplant. Wettfinder-/
  RisikoBet-Dateien bytegleich; kein Backup oder neuer Scan/API-Lauf.
- [x] Interner Produktionsbrowser: Hauptmenü, Manuelle Suche, Tennis und
  Preisfilter per Tastatur geprüft; bestehende exakte Quote 1,32 sichtbar,
  fehlende Preise bei aktivem Filter kein Treffer. Keine neuen Konsolefehler
  nach dem Aufbau; Verbindungsmeldungen während des Neustarts getrennt.
  Native Mausbedienung nicht bestätigt. Screenshot außerhalb Git im Prüfbericht.
- [ ] Echte neue Preisantworten im nächsten regulären Lauf prüfen; kein
  zusätzlicher Produktionsscan/API-Lauf für diese QA. Gespeicherte alte
  Tagesquoten werden durch Code-Deployment allein nicht aktualisiert.

**Nicht als universelle Preisgarantie darstellen:** Zehn der 90 Fußball-
definitionen haben kein verifiziertes direktes Provider-Mapping; tatsächliche
Ereignis-/Marktangebote sind Anbieterabhängig. Keine Preise aus Modellchance,
Nachbarlinien oder Einzelkomponenten erfinden. Cricket unverändert. Modelle,
Richtung, Rangfolge und Geldkonten bleiben unabhängig vom Preis.
Vorhandener Teamsport-Preisrahmen bleibt acht Ereignisse je Sport / 35 Sekunden;
auch darüber keine vollständige Preisversorgung behaupten.

Die geerbte Vollsuite ist beendet: 12.810 bestanden / zwei UI-Testaufbaufehler /
97 Skips / 143 Untertests; kein finaler Vollsuite-PASS (Checkout änderte sich
im Lauf). Beide Originalfälle im frischen 724er-Lauf bestanden. Vorhandene
Wettfinder-/Football-Shadow-Datenfehlzustände bleiben separat offen.
Altfehler-Skripthash exakt aus alter Zeile 100 rekonstruiert: gemischter
Quelltext statt Appdefekt. Nächster normaler Wettfinder 11.10. 03:35 CEST.
Dokumentationsnachtrag kann einen neueren HEAD haben als Code `92cb4d2`.

[Quoten-Prüfbericht](docs/audits/2026-10-10-quotenversorgung.md).

## 10.10.2026 – Hauptmenüs und echte manuelle Filter

Die letzte Nutzerentscheidung ersetzt die darunter dokumentierte Bereichsauswahl:
sichtbare Hauptmenüs **Wettfinder, Manuelle Suche, RisikoBet, 3 a day, 15K,
Live, Meine Tipps**. Auf Mobilgeräten dieselbe einzeilige, horizontal scrollbare
Navigation; keine zusätzliche Bereichsauswahl oder doppelte Mobile-Navigation.

- [x] Navigation und bestehende Abo-/Sammlungs-/Rückwechselprüfungen verbunden.
- [x] Manuelle Suche: Sport, Zeitraum, Liga/Wettart, Modellwahrscheinlichkeit
  von/bis und optional tatsächlich beobachtete Quote von/bis (mindestens 1,20).
- [x] Filter vor der Ausgabegrenze anwenden. Keine Änderung an Modellchance,
  Modellrichtung, Rangfolge, gespeicherten Prognosen oder Geldbuchungen.
- [x] Aktiver Quotenfilter akzeptiert weder fehlende noch fremde/veraltete Preise.
  Tennis und E-Sport lesen vorhandene exakt gebundene Preisbelege. Fußball lädt
  Preise einmal innerhalb der ausdrücklich gestarteten manuellen Suche;
  Filteränderungen und Navigation lösen keine zusätzliche Abfrage aus.
- [x] Basketball/Eishockey ohne vorhandenes Modell liefern keine erfundenen
  Treffer für Prozentfilter. Cricket bleibt fachlich unverändert.
- [x] Test-first-Reproduktionen, unabhängiger Abschlussreview ohne offene
  konkrete P1/P2 und **382 frische Regressionstests bestanden** (36,82 s).
- [x] Echter interner Browser: 1440/390/320 Pixel, einzeilige 48-Pixel-Menüpunkte,
  mobile interne Scrollleiste statt Seitenüberlauf, Tastatur, kombinierte Filter,
  fehlender Preis und ungültiger Quotenbereich geprüft. Lokale Beispieldaten
  ausdrücklich markiert; keine Produktions-Sportabfrage.
- [ ] Ergänzende Vollsuite läuft weiter: am 10.10. um 12:09 bei 24 %, bislang
  keine Fehler ausgegeben. Log außerhalb Git: `C:/Projekt/BetBoy/output/manual-navigation-20261010/fullsuite.log`.
  Der Lauf begann vor dem letzten CSS-/Vergleichsfix; diese sind in der frischen
  gemeinsamen 382er-Runde enthalten. Keine grüne Vollsuite behaupten.
- [x] Code `f01e83e` committed, auf main gepusht und VPS-fast-forward live ohne
  neues Backup. Produktionsbrowser 1440/390/320, Hauptmenü, Tastatur-Rückwechsel,
  Filtercontrols und eine Navigation ohne Seitenüberlauf bestätigt. Nach Reload
  keine neuen Browserfehler. Kein „Tipps finden“-Klick oder zusätzlicher Scan.
- [x] App/Caddy aktiv, sieben Timer aktiv/geplant, beide Healthchecks `ok`.
  Wettfinder-/RisikoBet-Schnappschüsse bytegleich. Vorhandene Wettfinder- und
  Football-Shadow-Dienstfehlzustände separat offen, nicht durch UI-Deploy behoben.

[Prüfbericht](docs/audits/2026-10-10-hauptnavigation-manuelle-filter.md).
Vorhandene Sportdienst-Datenfehlzustände, Daily3-Zeitfolge, empirische Kontexteffekte,
Domainumzug, Stripe und Stores bleiben separate offene Aufgaben.

## 10.10.2026 – Gemeinsames Wettfinder-Dach

Nutzerfreigabe: **Gemeinsames Dach mit einer Bereichsauswahl**. Freigegebener
Patch umfasst Navigation und die angrenzenden Gegenrisiko-/TOP-Prüfungen;
keine neue Modellfamilie, Zahlung, Datenbereinigung oder zusätzliche Sportabfrage.

- [x] Eine Bereichsauswahl für Automatisch, Eigene Suche, RisikoBet, 3 a day,
  15K, Live und Meine Tipps. Doppelte Haupt-/Mobile-/Modusmenüs entfernt;
  Rückwechsel, Abo- und persönliche Speicherprüfungen bleiben erhalten.
- [x] Gegenrisiko nennt das genaue Gegenereignis. Parma über 5,5 Ecken:
  81,4 % bezeichnet höchstens fünf Parma-Ecken, nicht ein Parma-Tor.
  Sechs Resultat-/Tore-Kombimärkte mit korrekter UND-/ODER-Negation.
- [x] Kontext- und Preisprüfungen kommen nach der modellseitigen Richtungswahl:
  kein Wechsel auf den Gegenmarkt, weil ihm eine Quote oder besserer Kontext vorliegt.
  Fehlende/alte relevante Prüfbelege verhindern TOP, nicht zusätzliche Karten.
  Eine offene Aufstellung allein sperrt nicht; ausdrücklich negative Befunde bleiben
  auch nach Serialisierung ohne gültigen Prüfzeitstempel erhalten.
- [x] Tatsächliche exakte Preisversuche getrennt übernommen; keine Frische durch
  Seitenaufruf. Bekannte Quoten unter 1,20 bleiben gefiltert; ein echter Versuch
  ohne lieferbare Quote ändert weder Modellchance noch Rangfolge.
- [x] RisikoBet prüft Original-Kontextfristen und genaue Snapshotbindung beim
  Rendern; eigene Anzeigequote erzeugt weder Abrufnachweis noch fremden Zeitstempel.
  Neue typisierte Belege entstehen erst beim regulären Lauf, keine Migration.
- [x] Unabhängiger finaler Diffreview: keine offenen konkreten P1/P2 im Patch.
  Originalreproduktionen und lokaler interner Browser (1440/390/320 px) bestanden.
- [x] Vollregression abgeschlossen: 12.683 bestanden / 50 ursprüngliche Fehler /
  97 Skips / 143 Untertests. Alle 50 Originalfehler danach gemeinsam grün:
  46 falscher Windows-Bash, vier präzisierte Test-Schnittstellen/Belege.
  Keine Produktionsänderung oder aufgeweichte Prüfung zur Fehlerbereinigung.
- [x] Narrow Commit/Push und VPS-Fast-forward ohne neues Backup:
  Code `ea4c6a9`, finale Beschriftung `548b283` live. Echte Produktionsseite
  mit allen sieben Bereichen, Tastatur und 1440/390/320 Pixeln geprüft;
  genau ein globaler Selector, keine Doppelmenüs oder Seitenüberläufe.
- [x] „Meine Tipps“-Sammlungsfilter heißt „Tippquelle“, nicht ebenfalls
  „Bereich“. Echter Renderer-Test zuerst rot; Navigation und Workflow danach
  116 bestanden, unabhängiger Nachreview ohne konkrete P1/P2.
- [x] App/Caddy und sieben Timer aktiv, beide Healthchecks ok. Gespeicherte
  Wettfinder-/RisikoBet-Prognosen während Deployments bytegleich; kein
  zusätzlich gestarteter Scan, Backup, Migration oder Datenbereinigung.
  Vorhandener Wettfinder-Dienstfehlstatus ausdrücklich nicht als behoben ausgeben.

[Prüfbericht](docs/audits/2026-10-10-gemeinsame-bereiche.md).
Separat offen bleiben vorhandener Wettfinder-Datenfehlstatus, Daily3-Zeitfolge,
empirische Verletzungs-/Wetter-/Müdigkeitswirkung, Domainumzug, Stripe und Stores.
Softwaretests beweisen keine bessere Wett-Rendite. Geerbtes ungetracktes WIP erhalten.

## 10.10.2026 – Alcaraz-Quotenabruf und 1,20-Filter repariert

- [x] Konkrete Ursache am VPS belegt: 16 Tenniszeilen, nur zehn Preisprüfungen;
  Alcaraz/Cerundolo war als 15. Spiel unbepreist und wurde deshalb nicht gefiltert.
- [x] Tennis-Sammelabfrage prüft jetzt den vorhandenen begrenzten Tageskatalog.
  Gleiches Ereignis-/Spieler-/Markt-/Startmatching, bestehende Kontingente und
  Cooldown; keine Beeinflussung der Modellwahrscheinlichkeit durch Quoten.
- [x] Erfolgloser oder fremder neuer Preisabruf löscht einen alten exakt gebundenen
  Niedrigpreis nicht mehr. Originalzeitstempel bleiben erhalten; daraus keine
  neue Ausführungsfreigabe. Zusätzliche Gegenpreisbelege weiterhin 10 Events/20 Seiten.
- [x] 352 betroffene Tests frisch bestanden; unabhängiger Abschlussreview ohne
  blockierende Befunde. Linux-Gegentest im Arbeitsspeicher: 16 statt 10 exakte
  Prüfungen, 1,02 erreicht den Filter, keine Netzwerk-/Datenbankoperationen.
- [x] Code `097f4fa` auf GitHub main und VPS live, App/Caddy aktiv, beide
  Healthchecks ok. Ein einmaliger **Quotenlauf**, kein Sport-/Modellscan:
  acht noch bevorstehende Spiele / acht exakte Preise / null Abruffehler.
- [x] Echte Alcaraz-Bestquote um 08:43 Europe/Zurich **1,05**, ebenfalls unter
  1,20; aus tatsächlichem Katalog und Daily3-Kurzliste ausgefiltert. Interner
  Browser nach Reload bestätigt; erlaubte 1,46 bleibt sichtbar.
- [x] Nur ein Zusatzcredit verbraucht (offizieller Anbieterstand 490 → 489).
  Originalmodellzeit und alle Modellwerte unverändert; RisikoBet-JSON unverändert.
  Keine Geldbuchung, Sicherung, Bereinigung oder Schlüsseloffenlegung.

[Prüfbericht](docs/audits/2026-10-10-tennis-quotenfilter.md).
Nur dieser Preisabruf-/Filterfix abgeschlossen. Daily3-Zeitplanung, vorhandener
Wettfinder-Fehlstatus, Kontextmodelle und Domain-/Stripe-/Store-Aufgaben nicht
als erledigt ausgeben. Fehlende echte Preise bleiben nach bisheriger Produktregel
offen; keine geschätzte Quote als Buchmacherangebot ausgeben.

## 09.10.2026 – 15K an die Wettfinder-Darstellung angeglichen

- [x] 15K-Modellauswahlen verwenden dieselben Sports-Editorial-Karten wie
  Wettfinder: Vereinslogos, Markt/Modellchance, kurze Begründung, letzte 5/10
  Spiele mit Ergebnissen und Gegnerlisten, kompakte Ausfallinformationen.
- [x] Automatischer Tagesbestand reicht seine bestehenden Originalbelege nur
  im Arbeitsspeicher durch. Spiel-/Markt-/Modellbindung, ursprüngliche Modellzeit
  und veralteter Kontext bleiben erhalten. Keine zusätzliche API-Abfrage,
  Bilderdatei, persistierte Statistikduplizierung oder erfundene Historie.
- [x] „1 Auswahl“ und deutsche Ticketauswahl statt „Choose options“.
  Einsatzrechnung, Ticketgrenzen, Geldbuchungen und 1,20-Untergrenze unverändert.
- [x] Finale lokale Regression: **460 Tests und 85 Untertests bestanden**;
  unabhängiger Abschlussreview ohne offene Befunde im 15K-UI-Scope.
- [x] Tägliche Originalprognosen verwenden dieselbe Modellstand-Anzeige wie
  im automatischen Wettfinder. Manuelle/ungebundene Daten behalten das kürzere
  Zeitfenster; drei deterministische Regressionen sichern die Unterscheidung.
- [x] Interner Browser: Desktop 1440, Mobil 390/320 ohne horizontalen Überlauf,
  vier Vereinslogos geladen, Formumschaltung, vollständige Gegnerliste und
  Spielblock per Tastatur geprüft; Gegenprobe ohne Historie erfindet keine Form.
- [x] Veröffentlicht: UI-Code `a96a932` auf main und VPS, App/Caddy aktiv,
  interner/öffentlicher Healthcheck `ok`. Drei echte 15K-Karten geprüft;
  alle sechs Vereinslogos geladen. Brann/Viking und Libertad/Leones zeigen
  je zehn gespeicherte Ergebnisse pro Team; Moreirense ohne gültige Ergebnisliste
  im vorhandenen Beleg, daher keine erfundene Form.
- [x] Frische Produktionssitzung: 1440/390/320 px ohne horizontalen Überlauf,
  10→5→10 und vollständige Gegnerliste tatsächlich bedient, keine
  Streamlit-Ausnahme oder Browserfehler. Linux-Belegprüfung mit gesperrten APIs
  und Datenbanken bestätigt unveränderte Wahrscheinlichkeiten/Originalzeiten.
  Wettfinder-/RisikoBet-JSON vor und nach Veröffentlichung identisch.

[Prüfbericht](docs/audits/2026-10-09-15k-editorial.md).
Nur 15K-Präsentation: Daily3-Zeitfolge und bestehender Wettfinder-Fehlstatus
bleiben separate offene Aufgaben; kein Modellqualitätsnachweis aus diesen Tests.
Kein neuer Sportscan, Backup oder Bereinigung; geerbtes ungetracktes WIP erhalten.

## 07.10.2026 – Accountübergabe und Domainumzug

Aktuell beauftragt: To-do und Übergabe sichern, keine Migration ausführen.
**Nächster Account zuerst:** [Domainumzug und getrennte Apprestarbeiten](docs/handoffs/2026-10-07-domainumzug.md).
[Lokale Umzugs-To-do-Liste](<C:/Projekt/BetBoy/output/domain-migration-20261006/TODO_AKTUELL.md>) und Bestandsbelege liegen außerhalb des App-Repositories.

- [x] Gleicher Umfang neu verglichen: zehn Domains, zwei Websites, zehn getrennte
  Postfächer. Dynadot/Spaceship/netcup ca. CHF 124.09 jährlich; Infomaniak-Domains
  plus netcup ca. CHF 199.81; optimiertes Voll-Infomaniak ca. CHF 396.20.
- [x] netcup-Zusammenfassung: EUR 29.32 Jahresrechnung, ein Webhosting 1000 NUE.
  Nutzeradresse gespeichert, beide Vertragskästchen zuletzt gesetzt. Kein
  Bestell-/Zahlungs-/Aktivierungsnachweis; ältere Angaben „ungesetzt“ überholt.
- [ ] Umzug vollständig offen: Zielaktivierung, Dateien/IMAP/Regeln, unabhängiges
  DNS/DNSSEC, Zieltests, finale Differenz, **Registrartransfer zuletzt**, Kündigung.
- [ ] Konkrete weitere Verträge/Zahlungen und Daten-/DNS-Übertragung freigeben;
  keine pauschale neue Freigabe aus dem bloßen To-do-Auftrag ableiten.

Nur Dokumentation. Kein Appcode, neuer Scan, Backup, Bereinigung oder explizites
VPS-Deployment. App-/Stripe-/Store-/Modellaufgaben unten bleiben erhalten;
historische Produktionsnachweise wurden am 07.10. nicht neu geprüft.

## 06.10.2026 – Stripe-Live-Katalog eingerichtet, Billing-Anschluss repariert

Dieser Abschnitt ergänzt/ersetzt den Stripe-Status der älteren Blöcke.
Nutzer: Einrichtung korrigieren; ausschließlich bestehenden **internen Browser**
verwenden. Keine neue MCP/OAuth-Verbindung nach Abbruch gestartet.

- [x] BetBoy-Live-Konto geprüft: Zahlungen/Auszahlungen aktiv, keine Pflichtaufgaben.
- [x] Drei aktive separate Produkte mit bestätigten CHF-Monatspreisen 9.90 / 19.90 /
  29.90 gespeichert; Standardpreise einzeln geprüft, Steuerverhalten **Inklusive**.
  SaaS-Personal-Use `txcd_10103000` ausdrücklich vom Nutzer bestätigt. Keine
  automatische Steuerregistrierung oder Änderung anderer Stripe-Konten.
- [x] Runtime akzeptiert Restricted Keys der richtigen Test-/Live-Umgebung;
  Publishable/falsche Umgebung/Leerwerte weiter abgelehnt. Dynamische Stripe-
  Zahlungsarten statt erzwungener Karte; stabiler Flow-Tag, v2-Idempotenz.
- [x] Test-first und finale **47 Portaltests**, Exit 0; unabhängiges Abschlussreview
  ohne P0–P2 im Patch. Prüfungen mit simuliertem Stripe, keine echte Zahlung.
- [ ] Vollständiger Kundenverkauf noch nicht bereit: geschützter Serverkey/Webhook,
  SMTP, bestätigte öffentliche Adresse, Recht/Verkaufsländer/Steuerregistrierungen,
  separater Portalservice/Proxy, deployed Sandbox-E2E und Reconciliation.
- [ ] Echter Schutz vor Zahlung außerhalb freigegebener Länder. Checkout bietet
  keine Billing-Country-Allowlist; Versandfilter/Dropdown nicht als Lösung behaupten.
  Heute wird das Land erst bei der bezahlten Rechnung geprüft. Nicht durch
  Entfernen dieser Prüfung oder kostenpflichtige Radar-Aktivierung umgehen.

Frischer VPS-Vorcheck: `5a5e1b1`, getrackter Checkout sauber; App/Caddy aktiv;
Portalservice und `portal.env` fehlen. Portalcode-Pull allein ist kein Verkaufsstart.
Domain-/SMTP-Fragen sind im Chat gestellt; Serverkey wird geschützt und mit
minimalen Rechten eingerichtet, **nicht im Chat/Git**. Keine neuen Backups,
Sportscans, Bereinigungen, Zahlungen oder Kundendatenmigrationen.

**Veröffentlichung bestätigt:** Code-/Einrichtungscommit `47a5580` auf `main`
gepusht und exakt auf dem VPS per Fast-forward unter Deploylock übernommen.
Getrackter Servercheckout sauber, App/Caddy aktiv, beide Healthchecks `ok`.
Kein Dienstneustart; Portalservice weiterhin nicht installiert. Nachfolger nur
Dokumentation. Nicht „Landingpage/Kundenverkauf live“ daraus ableiten.

[Einrichtungsbeleg mit Produkt-/Preis-IDs und Fortsetzungsreihenfolge](docs/audits/2026-10-06-stripe-live-setup.md).
Die Modell-/Scanner-/Store-Restarbeiten darunter bleiben separat offen.

## 06.10.2026 – freigegebene Sports-Editorial-Landingpage umgesetzt

Dieser Block ersetzt den früheren Freigabe-/Umsetzungsstatus darunter.
Nutzerfreigabe: „ja genau so bitte umsetzten diese landigpage passt“.

- [x] **LAND-01:** `selected-remix.png` ausdrücklich bestätigt. Nicht erneut
  fünf Varianten erzeugen oder die gleiche Designfreigabe verlangen.
- [x] **LAND-02:** vorhandenes Django-Portal originalnah umgesetzt: Creme/
  Dunkelgrün/Lime, schmale zweizeilige Headline, natürliches vollständiges Handy,
  drei Schritte → Monatsbilanz September → Starter/Plus/Pro → Stadion/Footer.
  DE/EN inklusive lokalisierter Bildmotive; keine kostenlose interaktive Demo.
- **Codecommit `a8188f800ceaa7fd4655ea7d40ca93d9c7216e6e` auf `main` gepusht.**
  Nachfolgende Übergabeänderungen sind Dokumentation, nicht weiterer Appcode.
- **43 Portaltests frisch bestanden**, davon 15 neue Verhalten-/Renderverträge.
  Desktop 1440/1024, Breakpoints 901/900 und 761/760, Mobil 390/320 geprüft;
  kein horizontaler Überlauf, Menü/Fokus/Sprachwechsel/Abo-/Login-GETs geprüft.
  Browserwarn-/Fehlerlog leer; unabhängiges Review ohne offene P1/P2 im Landing-Scope.
  [Design-QA](design-qa.md), [Umsetzung/Assets/Startbefehl](docs/design/landingpage-20261006/implementation.md).
- Lokale interne Vorschau: <http://127.0.0.1:8010/de/> und
  <http://127.0.0.1:8010/en/>. Server nur Loopback; Tab bleibt als Ergebnis offen.
  Die geerbten venv-Launcher sind nicht portabel; der verifizierte Python-
  Fallback mit vorhandenen Abhängigkeiten steht im Umsetzungsdokument.
- Gesamtes neues Laufzeit-Assetverzeichnis **1.128.615 Bytes**, einschließlich
  DE/EN, Fonts, SVGs und Lizenzen. Responsive WebPs statt Laufzeit-Quell-PNGs.
  Quell-/Prompt-/Browserbelege lokal unter `output/landing-20261006/`, ungetrackt.
- **Kein VPS-Pull/Deployment und kein Verkaufsstart in diesem Auftrag.**
  Der Portalservice/Stripe-/SMTP-Aufbau bleibt offen. Letzter VPS-Nachweis
  `5a5e1b1` um 07:11 ist historisch; in dieser Designarbeit nicht neu überprüft.
- Keine Sport-/API-Scans, neuen Backups, Datenbankmigrationen, Kundenregistrierungen
  oder echten Zahlungen; geerbtes ungetracktes WIP unverändert erhalten.

**Weiterhin offen:** LAND-03 echte Monatsbilanz (keine erfundenen 74 %; sichtbarer
Status „Noch keine veröffentlichte Monatsbilanz.“), WEB-01/02 Verkauf/Recht/
Länder/Stripe/SMTP/Proxy/E2E/Reconciliation, STORE-01 native Builds/Abnahme,
MODEL-01–04 und OPS-01. Keine Behauptung besserer Wettqualität aus Portaltests.
Nächster Schritt nach separatem Auftrag: Kundenportal bereitstellen und seine
echten Zahlung-/Mail-/Zugangsabläufe prüfen; nicht die Landingpage neu planen.

## 06.10.2026 – aktuelle Übergabe an Claude: Landingpage, Verkauf und Restarbeiten

Historischer Stand vor der anschließenden ausdrücklichen Freigabe; maßgeblich
ist der neue oberste Block.

Maßgeblicher neuer Einstieg: [Claude-Übergabe](CLAUDE_UEBERGABE_2026-10-06.md).
Diese Aktualisierung betrifft nur Dokumentation und drei Designreferenzen.
Keine Produktivcodeänderung, kein Zusatzscan, kein Backup oder Deployment.
Die älteren Abschnitte unten bleiben als historische Belege erhalten.

### Frisch geprüfter Stand

- Vor dem Übergabecommit lokal/GitHub-main/VPS identisch auf
  `5a5e1b1a6b18d93211164b96193c7d909564af8b`; `main`, keine getrackten WIP-Änderungen.
  Geerbte ungetrackte Audits/Browser-/Storage-Belege unverändert erhalten.
- 06.10., ungefähr 07:11 CEST: App/Caddy aktiv, beide Healthchecks `ok`.
  **Wettfinder 03:35:02–04:02:17 Exit 1**, nicht repariert oder zurückgesetzt.
  Tennis 00:05:31–00:30:21 und E-Sport 03:10:31–03:10:45 technisch Exit 0.
  Shadow zuletzt 07:02:21 Exit 0; nächster Termin 07:12, aktuell zehnminütlich.
  Technischer Erfolg ist kein Qualitäts-/Kontexteffekt-Nachweis.
- Sieben Timer geplant. `betboy-portal.service` fehlt,
  `/etc/betboy/portal.env` fehlt: Stripe-/Kundenverkauf **nicht live**.
- Keine neue Vollsuite gestartet. Der historische Nachweis vom 04.10. bleibt
  12.474 Haupttests bestanden / 97 Skips / 111 bestandene Untertests, nicht addieren.

### Aktueller Designauftrag

- Nutzer wählte **Variante 1, Sports Editorial** (Creme/Dunkelgrün), nicht die
  blaue Variante 3. Handy natürlich proportionieren und vollständig zeigen.
- Reihenfolge: Hero → **„In drei Schritten zu deinem Überblick.“**
  (Spiele entdecken / Form vergleichen / Auswahl verstehen) →
  **„Monatsbilanz · September 2026“** → Abos → Abschluss/ Footer.
- [Kombinierter Bildentwurf](docs/design/landingpage-20261006/selected-remix.png)
  gezeigt, aber noch nicht abschließend freigegeben. **Noch keine Umsetzung.**
  Ausgangsvariante 1 und Strukturreferenz 3 liegen neben dem Remix; alle drei
  zusammen 5.485.849 Bytes, hashgleich kopiert, keine Laufzeitbilder ersetzt.
- Werbeseite mit statischer Produktabbildung, **keine bedienbare Gratisvorschau**.
  Keine neue Designrunde mit fünf Varianten beginnen.
- 74 % Monatsquote war ein Beispiel. Keine verifizierte September-Kundenbilanz;
  Entwurf nutzt gekennzeichnete Platzhalter. Interne Dreitagesprobe 181/107/71/3
  nicht als Monats- oder veröffentlichte Kunden-Tippbilanz vermarkten.

### Neue kompakte Fortsetzungsliste

- [ ] **OPS-01 / P0:** heutigen Wettfinder-Exit 1 aus bestehenden Logs/Berichten
  diagnostizieren; keine Zusatzscans/Statusresets zur vermeintlichen Bestätigung.
- [ ] **LAND-01:** kombinierten Entwurf vom Nutzer bestätigen lassen.
- [ ] **LAND-02:** danach vorhandenen Django-Landing-/CSS-/DE/EN-Pfad umsetzen,
  responsive 390/320 px und Desktop, Navigation/Buttons/Fokus prüfen.
- [ ] **LAND-03:** echte Monatsbilanz veröffentlichter Auswahlen belegen oder
  Zahlenwerbung weglassen; keine erfundenen 74 %, Bewertungen oder Kundenzahlen.
- [ ] **WEB-01/02:** vorhandenes Pre-launch-Portal mit Stripe/SMTP/Recht/Domain/
  Ländern/Proxy, echtem E2E und Reconciliation fertigstellen. `sales_open`-Banner
  ist derzeit allein von REGISTRATION_OPEN/LEGAL_READY abhängig, kein Launchbeweis.
- [ ] **MODEL-01/02:** nativen Basketball-/Hockey-Ergebnisadapter und vollständige
  begrenzte Abschlusszähler statt nur 2.500-Zeichen-Logtail ergänzen.
- [ ] **MODEL-03/04:** tatsächliche Verletzungs-/Wetter-/Müdigkeitswirkung und
  unabhängigen Qualitätsnachweis sowie E-Sport-Fenster-/Gegnerstärkebelege schließen.
  Cricket bleibt ausgenommen; keine willkürlichen Modellaufschläge.
- [ ] **STORE-01:** aktuelle Zulässigkeit/Länder/Billing, native Builds/Signierung,
  Geräte, Kontolöschung und Store-Unterlagen getrennt nachweisen. Noch kein AAB/IPA.

Bestätigte Abos: Starter CHF 9.90, Plus CHF 19.90, Pro CHF 29.90 monatlich;
gleiche Modellqualität. Jahrespreise nur Vorschlag, kein Gratis-Testabo.
DE/EN-Portal ist nicht gleich vollständig englischer Analyse-Workspace.

### Speicherarbeit vom 05.10. abgeschlossen

56 synthetische lokale Testdateien / 3.758.096.468 Bytes und 70 konkret genehmigte
alte VPS-Backup-ZIPs / 5.190.707.355 Bytes entfernt. Neueste reguläre Sicherung
vom 19.09. behalten/restoregeprüft; keine Produktionsdatenbank gelöscht.
Belege: `output/storage-audit-20261005/`; keine weitere Bereinigung beauftragt.
Tagesbackup disabled, Retention enabled. Frisch frei am VPS: 23.508.914.176 Bytes.
Große Worktree-/DB-Mengen sind kein Store-Paket; native Downloadgröße noch unbekannt.

**Nächster Account:** zuerst Claude-Übergabe und Remix ansehen, den kombinierten
Entwurf gezielt freigeben lassen; technischen Fehlstatus ehrlich offen halten.
Jetzt endet die Arbeit nach Dokumentationsprüfung und -veröffentlichung.

## 04.10.2026 – Fortsetzung ab 10:32 CEST: Abschlussprüfung und Release

- Übernahme tatsächlich geprüft: lokaler/GitHub-Stand `811588b`, VPS `7e5ef87`.
  App/Caddy aktiv und beide Healthchecks `ok`. Keine geerbten Dateien entfernt.
- Die zuvor laufende Vollsuite ist um 10:30:52 CEST beendet: **12.358 bestanden,
  97 Skips, ein Fehlschlag, 111 erfolgreiche Untertests**. JUnit ist vollständig,
  mit 12.456 eindeutigen Haupttest-IDs; Untertests nicht als Haupttests addieren.
  Beleg `output/playwright/full-00b4369-20261004.xml`, SHA256
  `9c5f12ddc802117efbb18b6576397352f2b5e6deff28085e9f3d29bb16b43c7f`.
  Die alten PIDs/Session unten sind damit keine laufende Prüfung mehr.
- Echte Lücke repariert: `selection_performance` prüfte die SQL-Frist nur nach
  je 1.000 SQLite-VM-Schritten. Kurze Statements konnten diesen Callback umgehen.
  Jetzt zusätzliche explizite Fristprüfungen zwischen den Lesephasen, kein
  Teilbericht bei Ablauf; VM-Interrupt weiterhin zu Timeout übersetzt. Der alte
  Picosekunden-Test ist wegen grober Windows-Uhrauflösung nun deterministisch.
  129 betroffene Tests und unabhängig dieselben 129 plus drei Phasen-Gegenproben
  grün; DB-Hash unverändert. Mengen überlappen, keine komplette grüne Suite daraus.
- NHL-Herkunftslücke konkret eingegrenzt: Spiel `2026020035` besitzt tatsächlich
  beide eingefrorenen Forecasts unter
  `event_803d6de802e85d2a668593561ebb0f7c951dfcf64a276505200f17ad9d38aaa5`,
  Modellstand 01:56:25.085199 UTC. Der Publisher verlor bei TeamSport-ModelSignal
  die native Snapshot-Event-ID und erzeugte im Archiv einen anderen Ersatzschlüssel.
  Enger Fix übernimmt Event-/Snapshot-ID ausschließlich aus dem bereits vollständig
  validierten Basketball-/Hockey-Snapshot; native Provider/ID, Sport, Wettbewerb,
  Seite, Uhr und widersprechende Aliasse werden geprüft. ESPN/NBA wird wie der
  vorhandene Producer im read-only Bericht als Basketballquelle unterstützt;
  ESPN-Hockey bzw. NHL-Basketball bleiben unzulässig. Kein Modell neu gerechnet.
- Die früheren NHL-Archive werden **nicht umgeschrieben oder rückdatiert**.
  Neue reale Veröffentlichungen sollen korrekt binden. Der separate Ergebnis-
  Sammler `forecast_evidence_settlement` unterstützt Hockey/Basketball bisher
  nicht: dieses Ergebnisproblem ist **nicht** durch den Publisherfix erledigt.
- Releasehülle prüft die geänderten Zielmodule aus Git im Speicher, bevor die
  laufende App gestoppt wird; kein zusätzlicher Codebaum/Backup. Offline-QA
  sperrt Netzwerk und DB-Zugriffe außerhalb ihres privaten synthetischen Tempordners.
  Enger ff-only Pull erst nach grüner neuer Vollsuite und sicherem Timerfenster.
- Finaler Codefreeze `ecda9e9f053e44429810d7da53e2ce74a5e7785b` committed;
  **vollständige Suite abgeschlossen, Exit 0** (etwa 10:44–11:33 CEST,
  2.908,24 Sekunden): **12.474 Haupttests bestanden, 97 unveränderte Skips,
  111 erfolgreiche Untertests**. Unabhängig vollständiges JUnit bestätigt:
  12.571 ordinale eindeutige Haupttest-IDs, null Failures/Errors; aggregierte
  12.682 XML-Reports enthalten die 111 Unterreports und sind keine 12.682
  unabhängigen Haupttests. Alter SQL-Timeoutfail jetzt ausdrücklich PASS.
  Beleg `output/playwright/full-continuation-20261004.xml`, SHA256
  `6e6edf1a1299920306e877eb49cb7149a33391e7689556effb564c4351af2bd5`.
  Session `9885` und PIDs `410372`/`414600` sind beendet. Während des Laufs
  keine Produktiv-/Teständerungen, anschließend nur Dokumentationsnachfolger.
  Die 250/237 gezielten Integrationsprüfungen überlappen; nicht dazuaddieren.
- Releasehülle abschließend unabhängig geprüft, lokaler Target-Smoke und
  `bash -n` grün; SHA256
  `3521d524ff9ea1996670bf6c38e3272000d64d81360b5e9632f869e71b89d0f8`.
  Genau 16 zulässige Diff-Pfade, Schreiber/Timerreserve vor und nach QA geprüft;
  weder lokaler Smoke noch Scriptreview ist ein Linux-/VPS-Releasebeweis.
- **Release auf dem VPS abgeschlossen, 04.10. etwa 11:36 CEST:**
  `e14deea2911369124e291020f140763df6226d57` per kontrolliertem ff-only Pull,
  davor Linux-Offline-QA auf den exakten Zielmodulen grün. App/Caddy aktiv,
  beide Healthchecks `ok`. Dokumentationsnachfolger ändern den Codefreeze nicht.
  Keine neuen
  Sport-/API-Scans, Backups, Bereinigungen oder Geldänderungen gestartet.

### Live-Abschlussnachweise dieser Fortsetzung

- Deploylock, genau 16 zulässige Diff-Pfade, ruhende Schreiber und mehr als fünf
  Minuten Timerreserve vor **und** nach Offline-QA tatsächlich geprüft.
  Die App wurde erst danach kurz gestoppt, gepullt und gestartet. Die zwei frühen
  lokalen Curl-Verbindungsversuche vor abgeschlossenem Start wurden regulär
  wiederholt; beide abschließenden Healthchecks erfolgreich, Helfer Exit 0.
- Gespeicherte Modellartefakte beim Release bytegleich:
  `wettfinder_latest.json` SHA256
  `998d2b8dd5e3286802054a615ba4414e7e085bd4e23ec4054bdec410c5178d08`;
  `riskobet_latest.json`
  `b241fbdecd1e710f07f07b8bbdb784ba385f5481905f589d840eb6367c606f37`.
  Kein neuer Modellfit, Ergebnis-Backfill, Daten-Rollback oder Geldschreiben.
- NHL `2026020035` am 04.10. 09:38:32 UTC rein lesend auf dem echten VPS
  geprüft: beide bestehenden Source-Prognosen werden exakt ihren ursprünglichen
  Forecast-IDs zugeordnet, nicht per Teamname/Spielausgang geraten. Netzwerk
  gesperrt, ausschließlich `mode=ro/query_only`; Artefakte und Forecast-DB
  unverändert. Keine zwei gegensätzlichen UI-Tipps daraus: der sichtbare
  Spielblock bleibt **eine** ausgewählte NHL-Prognose. Der Nachweis aktualisiert
  keine früheren Veröffentlichungseinträge und beweist noch kein NHL-Ergebnis.
- Echter frischer Reload ausschließlich im eigenen internen Prüftab: Greece vs
  Germany U2,5 weiter 72,0 %, letzte Quote 1,33; Kurzcheck jetzt
  **höchstens 2 Tore: 5/5 zuletzt · 7/10**, getrennte Torprognose 1,86,
  Greece-Gegentore 5/5 · 9/10, Basis korrekt **12 / 12 A-Länderspiele**.
  10-Spiele-Ansicht wirklich geklickt, einschließlich des sechsten Germany-
  Spiels 7:1 gegen Curaçao; Spielblock danach wieder geschlossen (`details.open`
  false). Keine Marktchance oder Reihenfolge hierfür neu gerechnet.
- Live-Layout 1280, 390 und 320 px: Dokument-/Bodybreite entspricht Viewport,
  kein horizontaler Überlauf. WebSocket-Abbrüche während des kontrollierten
  Neustarts waren sichtbar; **nach frischem Reload keine neuen Console-Fehler**.
  Native Geräte-/physische Mausfreigabe nicht daraus ableiten. Viewport
  zurückgesetzt und nur der eigene Prüftab geschlossen.
- Alle sieben Timer weiterhin aktiv/geplant. Alte fehlgeschlagene Tagesjobs
  bleiben ehrlich fehlgeschlagen; reguläre neue Nachweise folgen am 05.10.
  Tennis 00:05, E-Sport 03:10, Wettfinder 03:35 CEST. Keine Jobs manuell gestartet.

### Reguläre Produktionsläufe richtig zeitlich zuordnen

Rein lesend gegen Journald, `runtime_state/logs/pipeline_2026-10-04.log`,
Wettfinder-Artefakt und Git-Reflog geprüft: Tennis 00:05:12–00:27:41 CEST und
Wettfinder 03:35:30–04:02:36 CEST endeten am 04.10. mit Exit 1. Beide liefen
noch auf `25e79a5`; der bereits veröffentlichte Readerfix wurde mit `7e5ef87`
erst um **09:25:30 CEST** übernommen. Nicht diese alten Exitstatus zurücksetzen
oder einen neuen erfolgreichen Gesamtlauf behaupten.

Der Tennis-Refresh selbst aktualisierte 42/42 Revisionen ohne Refreshfehler.
Danach scheiterte der alte Kartenreader an innerem State-Schema 2 und genau
einem zusätzlichen Feld `market_model_version=serve-points-joint-v2`.
Alle acht damals geeigneten Siegerprognosen beziehen dasselbe ATP-Artefakt
`f2e13fd7…` in `context_models.db`; der aktuelle unveränderte 7e5-/ecda-Reader
akzeptiert dessen echte Header vollständig, ohne fehlende/zusätzliche Keys.
WTA nutzt dieselbe geschlossene Schema-2-Keymenge. Kein weiterer Sourcefix
für diesen konkreten alten Schemafehler nötig, kein Modell neu gerechnet.

Heute entstanden 25 ursprüngliche Tennisprognosen (5 ATP / 20 WTA).
Je 42 Modellrevisionen/Kontextoriginale im Tennis- und im Wettfinderlauf sind
zusammen 84 Revisionen, **nicht 84 weitere unabhängige Tipps**. Die vollständige
Tagesliste von `unresolved_outcome_events` und Modellfehlern ist nicht mehr
nachweisbar: Der Pipeline-Helfer erhält nur `out[-2500:]`; 24 sichtbare alte
WTA-Bo5-Ablehnungen sind deshalb keine Gesamtfehlerzahl. 102 offene WTA-Bo5-
Originale unverändert. Ein begrenzter vollständiger Abschlusszähler bleibt
als Diagnostikaufgabe offen; keinen vollständigen Bericht aus dem Rest ableiten.

Wettfinder meldete drei operative Fehler; Fußball-Refresh null, sein separater
Kontext-Capture weiterhin `partial/native-projection-unavailable`. Forecast-
Abrechnung: 131 terminal / 26 offen, darunter Hockey-Natividentität. RisikoBet-
Abrechnung: 146 terminal / 299 offen / ein operativer Fehler. Diese getrennten,
überlappenden Kohorten nicht addieren. Der nächste reguläre Gesamtlauf am 05.10.
bleibt der tatsächliche Produktionsnachweis; keine Zusatzläufe gestartet.

### Konkret vorbereiteter nächster Ergebnispfad (noch nicht implementiert)

`forecast_evidence_settlement.py` lässt native Basketball-/Hockeyidentitäten noch
nicht zu; ebenso fehlen Default-Resultloader in `riskobet_settlement_automation.py`.
Kanonische Regeln in `riskobet_settlement.py` bestehen bereits: Basketball H2H
inkl. Verlängerung, Hockey H2H inkl. Verlängerung/Penaltyschießen. Ein nativer
Endscore darf nicht als 60-Minuten-Spielstand verwendet oder ein vermeintliches
Siegtor künstlich abgezogen werden.

Vorhandene Quelle: `runtime_state/sports_completed_history.db`, Tabelle
`history_result_revisions(provider,event_id,observed_at,digest,payload)`.
VPS schreibgeschützt geprüft: 55 EuroLeague- und 1.620 NHL-Resultversionen;
für das heutige noch zukünftige NHL-Spiel `2026020035` keine Ergebnisrevision.
Keine vorhandenen ESPN/NBA-Ergebnisse daraus behaupten. Constructor
`CompletedHistoryStore()` initialisiert/schreibt und ist kein read-only Adapter.

Kleinste Anschlussaufgabe: nach diesem Release vorhandene Cachezeile per
`mode=ro/query_only` lesen, native Provider-/Spiel-/Sport-/Wettbewerbs-/Team-IDs,
Start, Inhaltshash und tatsächliche Empfangszeit prüfen; korrekte kanonische
H2H-Regel nutzen und nur Forecast-Ergebnisbelege ergänzen. Fehlende Resultate,
Rücknahmen oder Konflikte bleiben offen. Kein `fetch_page`/neuer API-Aufruf,
keine neue DB, keine Wetten-/Geldhistorie; Empfangszeit nie durch Spielende oder
Dateidatum ersetzen. Dies ist ein konkreter Restpunkt, keine fertige Abrechnung.

Vollsuite, Code-/Remote-Abgleich, kontrollierter Release und interne Browser-/
Forecastbindungsprüfung sind abgeschlossen. Nächste Reihenfolge: regulären
Tageslauf am 05.10. auswerten → nativen Basketball-/Hockey-Ergebnisadapter
aus dem vorhandenen Cache anschließen → begrenzten vollständigen Abschlusszähler
statt allein abgeschnittenem Pipeline-Logtail ergänzen.
Die numerischen Verletzungs-/Müdigkeits-/Wetterwirkungen und belastbare
Qualitätssteigerung bleiben separate offene Aufgaben, keine Fertigmeldung daraus.

## 04.10.2026 – verbindliche Account-Übergabe, 10:06 CEST

Der Nutzer hat den ab 09:23 CEST geplanten Zweistundenblock wegen Accountwechsel
unterbrochen. Nicht als zwei Stunden abgeschlossen oder als fertige App melden.
Dieser oberste Block ersetzt ältere Momentaufnahmen; historische Abschnitte bleiben
als Belege erhalten. Jetzt nur Übergabe aktualisieren, keine weiteren Appänderungen.

### Git, Produktion und laufende Prüfung

- Codefreeze lokal: `00b43693b7e0261147e5b75d69ea06f26860bd7d`
  (`Explain goal picks with bound form and reject conflicted history`). Fünf
  Produktionsdateien, vier neue Regressionstestdateien und drei Dokumente committed.
- Frischer Remote-/VPS-Abgleich bei Übergabe: beide noch
  `7e5ef8718839073b4c496f1066ecd10f4f9c82fe`. App und Caddy aktiv, interner und
  öffentlicher Healthcheck `ok`. Die neue Korrektur `00b4369` ist **nicht live**.
  Code und Übergabe inzwischen unter `2c49c3a62378090857b4c8e5f259436ea21b5039`
  auf GitHub main gepusht und durch `ls-remote` bestätigt. Der Nachfolger ergänzt
  nur diese Abschlussnotiz und den E-Sport-Befund; **kein VPS-Deployment**.
  Bei Wiederaufnahme `git rev-parse HEAD`, `git ls-remote origin refs/heads/main`
  und VPS-HEAD frisch lesen, nicht ältere SHA-Angaben übernehmen.
- Vollsuite des eingefrorenen Codes seit 09:49:30 CEST noch aktiv; letzter
  gelesener Fortschritt 23 %, bisher keine sichtbaren Fehlermarker, **kein PASS**.
  Unified-Exec-Session `96947`; Windows-Prozesse `266900` (venv-Launcher) und
  `269476` (Python-Runtime). Prozessidentität vor jeder Aktion erneut prüfen.
  Erwarteter Abschlussbeleg: `output/playwright/full-00b4369-20261004.xml`;
  diese JUnit-Datei existierte bei der Übergabe noch nicht. Session-Ausgabe ist
  nicht zwingend im nächsten Account verfügbar; PID und XML dienen der Fortsetzung.
  **Keine zweite Vollsuite starten und keine Test-/Produktivdateien ändern,
  solange die vorhandene Runde läuft.** PC laufen lassen; nach Absturz ist dies
  ein abgebrochener Lauf, kein bestandener Test.
- Aufruf zur eindeutigen Identifikation, nicht zum parallelen Neustart:
  `.codex_test_venv/quality/Scripts/python.exe -m pytest tests -q --tb=short
  --durations=15 --basetemp=.pytest_tmp/full-00b4369-20261004
  --junitxml=output/playwright/full-00b4369-20261004.xml`.
- Gezielt 240 Darstellungs-/Integrationstests bestanden; unabhängige Abschluss-
  prüfungen 192 und 188 bestanden, Historienprüfung 233 plus 32 Untertests,
  Tennis 182 und Capture 111 bestanden. Mengen überlappen: **nicht addieren**.
  Unabhängige Reviews ohne reproduzierten neuen P1/P2-Befund. Das ersetzt
  weder den ausstehenden Vollsuite-Abschluss noch einen Erfolgsnachweis des VPS-Jobs.
- Lokale synthetische Karten bei 320, 390 und 1440 px ohne horizontalen Überlauf;
  10-Spiele-Umschaltung tatsächlich geklickt und angezeigt. Kein Live-UI-Beweis
  für `00b4369`, keine native Maus-/Gerätefreigabe daraus ableiten.
- Geerbte ungetrackte Audit-/Browser-/Preview-Dateien unverändert, nicht pauschal
  `git add .`, löschen oder resetten. Eigene QA-Helfer unter `output/playwright/`
  bleiben unversioniert; kein neues Backup, Cleanup, Sport-/API-Scan oder Geldänderung.
- Eigene lokale Vorschau auf Port 8514 beendet; ihre Prozesse nicht mehr aktiv.
  Temporäre interne Prüftabs geschlossen, Viewport zurückgesetzt. Vollsuite bleibt aktiv.

### Erledigte Codekorrekturen und belegte Grenzen

- Reader-Folgecommit und bisherige Übergabe `7e5ef8718839073b4c496f1066ecd10f4f9c82fe`
  am 04.10. 07:25 UTC mit Deploylock, inaktiven Schreibern, Timerreserve und
  ff-only Pull tatsächlich auf dem VPS übernommen. Linux-Offline-QA, App/Caddy
  und beide Healthchecks bestanden. Gespeicherte Wettfinder-/Risikoartefakte
  bytegleich; kein Modell-Neulauf und keine Produktionsdatenmigration.
- Greece/Germany 1528939 unabhängig aus 652 vorhandenen A-Länderspielen und
  dem owning Kalibrationscache exakt rekonstruiert: Germany U2,5 = 71,9733 %,
  erwartete Tore 1,8571. 12/6-Spiele-Modell, nicht nur sichtbare Fünferbilanz;
  sechstes Germany-Spiel ist 7:1 gegen Curaçao. Kein Team-/Scoretausch.
  Siehe [Replaybericht](docs/audits/2026-10-04-greece-germany-replay.md).
- Neuer Kurzcheck für belegte Tor-Märkte zeigt tatsächliche 5-/10-Erfüllungen
  der gewählten Torbedingung und Gegentore des Gegners. Gefittete Torzahl bleibt
  getrennt; keine Änderung von Modellchance, Quotenfilter, Rangfolge oder Einsatz.
  Nationale Stichprobe wird als A-Länderspiele, nicht fälschlich als Heim/Gast
  bezeichnet. Automatisch, Daily3 und manuelle gemeinsame Kundenfakten nutzen
  denselben gebundenen Beleg; keine Ecken-/Kartenfakten aus Torresultaten.
- Historiengrenze: widersprüchliche native Revisionen und widersprüchliche
  exakte Event-Aliasse dürfen nicht nach Listenreihenfolge gewinnen. Identische
  Duplikate deterministisch, native/CSV-Identitäten erhalten. Gegenprüfung fertig;
  Konfliktprüfung vor Zeit-/Statusfilter und Quarantäne auch wiederkehrender Aliasse.
- Historische WTA-Originalformatfehler vollständig gezählt: 238 Best-of-5,
  davon 102 offen. In 78 Geldbüchern und Shadow-Side-Bets keine Geldbindung;
  keine Bindung im Forecast-Archiv oder den 4.167 Kontextoriginalen. Enger Fix
  klassifiziert exakt WTA + Ganzzahlformat 5 vor Ergebnisabfragen als nicht
  auswertbares Original. Kein Originalformat, Ergebnis oder Geld umgeschrieben.
- Getrennter Fußball-Capturefehler: 16 von 24 abgerechneten FT-Events dieses
  vorhandenen Laufs besitzen keinen vollständigen Detail-Capture. Ergebnis-Tore
  wurden gespeichert, aber damaliger abgelehnter Detailbody/Vertragsfehler wurde
  nicht erhalten. Ursache deshalb nicht nachträglich erfunden. Enger interner
  Logfix ergänzt höchstens fünf ID-/Typ-/Reasonhash-Belege, ohne Providerbody,
  Secrets, neue Datenbank oder gelockerte Validierung. Nächster regulärer Lauf
  muss die konkrete Ursache liefern; keine Zusatz-API-Abfrage dafür.
- Letzte reguläre Dienste vor den neuen Fixes: Tennis 00:27:41 CEST Exit 1,
  Wettfinder 04:02:36 CEST Exit 1. App erreichbar; ein Code-Pull macht diese
  vergangenen Läufe nicht erfolgreich. Kontextwirkungen, explizite nationale
  Gegnerstärke-Anpassung und verbesserte Wettqualität bleiben unbelegt.

### Tatsächliche Tagesveröffentlichung, nicht mit Modellmenge verwechseln

- Automatischer normaler Lauf veröffentlichte am 04.10. um 02:02:34 UTC
  **82 Auswahlen**, aus `source_run` 01:56:25 UTC; Daily3 hat tatsächlich **0**.
  `runtime_state/consumer_tips.db` nur 221.184 Bytes, Schema 1, sieben geprüfte
  Manifeste/Hashes. Nicht künstlich auf drei Daily3-Plätze auffüllen.
- Zwei erfasste Ansichten enthalten 162 Zeilen, aber nur 82 eindeutige
  Event/Sport/Markt/Seite-Kombinationen. 160 Zeilenvorkommen entsprechen
  **81** eindeutig korrekt gebundenen Forecasts; die übrigen beiden sind
  derselbe NHL-Fall `2026020035`, H2H, `sports-prematch-research-v1`, ohne
  zugehörige `forecast_rows`. Diese Herkunftslücke bleibt offen, nicht doppelt zählen.
  Greece/Germany: alle sechs Alternativen korrekt an Modellstand 01:38:28 UTC
  gebunden; keine sechs unabhängigen Bestätigungen oder Kombiwette daraus machen.
- Tennis heute: 25 neu angelegte Prognosen (5 ATP/20 WTA), 84 Modellrevisionen
  und 84 Kontextoriginale. Das bedeutet **nicht 84 neue Wetten**. Aktuelle ATP-/
  WTA-Artefakte wurden zuletzt am 02.10. gebaut; tägliche Prognosen sind kein
  täglicher Modell-Neuaufbau. Reader-Kompatibilität ist bereits deployed.
- Die aktuellen Belege sind noch nicht als geschlossene, vollständige Tagesbilanz
  auswertbar. Keine Tagesrendite, Kundengewinne oder bessere Wettqualität behaupten.
- E-Sport-TOP eng geprüft: LOL `1694355`, RED Canids (161) gegen KT Rolster (63),
  Beginn 04.10. 09:00 UTC, Modellstand 01:10:24.985923 UTC. Elo 1485,419 gegen
  1421,223, RED-Auswahl 59,13 %; Identität, Uhr und Quellhash stimmen zwischen
  Shadow und Forecast. Beide 3/5 Siege; letzte zehn RED 5/10, KT 3/10.
  Ursprüngliche 20er-Fenster nicht dauerhaft erhalten und keine E-Sport-
  Kontextoriginale im geprüften Bestand. Gemeinsame/verknüpfte Gegnergruppen
  dieses konkreten Fits daher **nicht belegt**. Unbekannte Teams starten bei
  Elo 1500, zwei Durchläufe; eine globale Stärke-Rangfolge zwischen getrennten
  Gruppen darf daraus nicht als bewiesen ausgegeben werden. Keine Prognose umgeschrieben.

### Nächste Schritte – genau in dieser Reihenfolge

1. Bestehende Vollsuite über Prozess/JUnit/Session bis zum echten Ende prüfen.
   Fehlschläge konkret reproduzieren; nicht als erwartete Skips umdeuten.
2. Bei grünem Stand `00b4369` mit dem Dokumentationsnachfolger sicher per ff-only
   auf den VPS übernehmen, **ohne neue Sicherung, Scan oder Datenmigration**.
   Ignorierter Helfer `output/playwright/selection-history-deploy-20261003.sh`
   unterstützt die neuen Dateipfade noch nicht: Whitelist und reine Linux-Offline-
   QA zuerst gezielt anpassen. Deploylock, inaktive Schreiber und Timerreserve
   prüfen; App nur begrenzt stoppen, danach Commit, App/Caddy und beide Healthchecks.
   Nicht ungeprüft den alten Helfer mit neuem SHA ausführen.
3. Neue Kurzerklärung im internen Browser prüfen; gespeicherte Modell-/Risiko-
   artefakte dürfen durch den bloßen Release nicht verändert werden.
4. Nächste reguläre Dienste am **05.10.2026: Tennis 00:05 und Wettfinder 03:35
   Europe/Zurich** lesen. Keine Zusatz-API-Läufe starten. WTA-Altoriginal-
   Klassifikation, konkreten Capturefehler und Ende/Exitstatus tatsächlich belegen.
5. Herkunftslücke des einen NHL-Falls prüfen. Für E-Sport beim regulären Lauf
   ausschließlich die tatsächlich verbrauchten 20er-Fenster kompakt belegen und
   gemeinsame Gegner/Spiele prüfen, keine alten Fits mit heutigen Daten nachbauen.
   Gegnerstärke/verbundene Vergleichsgruppen nicht erfinden; keine zweite große
   Rohdatenablage oder Zusatz-API-Suche für diesen Herkunftsnachweis.
6. Numerische Verletzungs-, Wetter- und Müdigkeitsanbindungen und unabhängigen
   Qualitätsvergleich weiterführen. Diese bisherigen Produktlücken sind nicht
   durch bessere Erklärungstexte oder Softwaretests erledigt. Keine neuen
   pauschalen Marktverbote, keine Quotenabhängigkeit der Modellwahrscheinlichkeit.

Bekannte Quoten unter 1,20 bleiben ausgefiltert; fehlende Quoten bleiben offen.
Historische Prognosen, Abrechnungen und Geldbuchungen nicht nachträglich umschreiben.
Weitere ältere Produkt-To-dos unten bleiben gültig, soweit nicht ausdrücklich erledigt.

## 03./04.10.2026 – Auswahlkohärenz und echte Veröffentlichungsbilanz

- Abschlussstand um 04.10. 00:19 CEST: Tennis-Leser-Code
  `6c62100b33fe44e4bb31a510f200b96b33f86a00` committed und auf main gepusht,
  zusätzliche gemeinsame Integration am finalen Stand: 225 Tests bestanden.
  VPS weiter `25e79a5c71bcd763fd0d5b66e7bb937c98aef427`; planmäßiger Tennisjob
  noch `activating/start` ohne Endzeit. App/Caddy aktiv. Kein erfolgreicher Job-
  Abschluss behauptet und Reader-Folgecommit noch nicht auf den VPS gepullt.
  Nächster konkreter Schritt bleibt der sichere Pull nach dem regulären Jobende.
- RisikoBet: gemeinsam unmögliche Fußball-Ergebnisse und der Best-of-1-Map-
  Sonderfall reproduziert und repariert. Kohärenz vor Preisfilter/Kartenlimit;
  bestätigte Evidenz vor dem Zwei-Szenarien-Limit. Keine Wettart pauschal verboten,
  kein Quote-bedingter Wechsel auf die Gegenposition, keine geänderte Modellchance.
- Neu: kompakte prospektive Inventar-Historie `runtime_state/consumer_tips.db`.
  Normaler Wettfinder-Veröffentlichungsablauf zeichnet Standardinventar und
  anonymen Daily3-Plan auf. UI zeichnet ihre ausgewählte Wettfinder-, Daily3-
  und RisikoBet-Ansicht auf. Kein Beleg eines Kundenbesuchs/echter Wettplatzierung.
  Keine großen Kontextlisten oder Kontodaten; identische Neuladungen dedupliziert.
  Keine Rückdatierung alter Tipps, keine neue Sicherung oder zusätzliche API-Abfrage.
- Neue reine Leseberichte für interne Modelle versus archivierte Auswahlen,
  Sport/Markt/Modell/Policy getrennt; offene Ergebnisse, Stornos, Quotenlücken und
  Integritätsabweichungen getrennt. Tatsächlicher Anpfiff und Teilnehmerwechsel
  geprüft. Renditerechnung nur mit frischer exakter Quote ab 1,20; beim Publikations-
  bericht deren Capturequote statt früherem Modellpreis. Keine Renditezusage.
- Bestehende VPS-Belege 30.09.–02.10.: 181 Prognosen aus 91 Spielen,
  107 gewonnen/71 verloren/3 offen; kein damaliger Kundentipp-Nachweis.
  12 frische Quoten, davon 11 abgerechnet: hypothetisch −2,00 Einheiten anhand
  vorab definierter jüngster Anbieterquote. Keine echten Daily3-Kundengewinne.
  Optimierte Abfrage auf VPS in 0,561 Sekunden, Bilanz identisch, 0 Integritätsfehler.
- Gezielte Gegenläufe: RisikoBet 455, neue Kernmodule 101, Bericht 38,
  vorherige UI-Integration 298 bestanden. Überlappende Mengen nicht addieren.
  Abschließende betroffene Integration: 506 bestanden; zusätzlich beide CLI-
  Schutzfälle gegen Modellpool-Fallback und ungebundene Surfacefilter grün
  (24 Publisher-Tests). Unabhängige Abschlussrunde: 127 bestanden. Breite Suite
  läuft noch; nicht als abgeschlossen oder als neue Wettqualitätsmessung zählen.
  Finale Codefreeze-Integration für `25e79a5`: 510 bestanden. Breite Runde:
  12.256 bestanden, 97 Skips, 111 Untertests; 2 Fehler in vor deren Korrektur
  importierten Testfixtures (Quotenuhr und Fußball-Testanpfiff). Beide Dateien
  frisch erneut geprüft: 70 bestanden. Dies ist keine neue komplett grüne
  Vollsuite des letzten Standes; überlappende Mengen nicht addieren.
- Auswahl-/Historien-Release `25e79a5c71bcd763fd0d5b66e7bb937c98aef427`
  auf GitHub main und am 03.10. 21:53 UTC per ff-only auf dem VPS live.
  App/Caddy aktiv, App und sieben Timer enabled, beide Healthchecks `ok`.
  Vorab Deploylock/Schreiber-/Timerreservecheck und reine Linux-Offline-QA;
  erster Versuch korrekt am nahen Timer zurückgehalten, App nicht gestoppt.
  Keine Sicherung, Bereinigung, Zusatzscans oder Produktionsdatenbankmigration.
  Modell-/Risikoartefakte bytegleich; Browser nach frischem Reload ohne neue
  Fehler (während Apprestart erwarteter WebSocket-Abbruch separat protokolliert).
  Echte UI-Inventare nach Reload: drei Oberflächen, derzeit null aktuelle Tipps,
  neue Datenbank 20.480 Bytes. Kein angeblicher Nachweis alter Kundentipps.
- Neuer enger Tennis-Folgefix: `tennis/context_consumer.py` akzeptierte nur
  Schema 1, beide aktuellen ATP-/WTA-Produzenten liefern Schema 2 mit
  `market_model_version=serve-points-joint-v2`. Exakte geschlossene Headerprüfung
  für beide Varianten ergänzt; unbekannte Keys/Versionen weiterhin abgelehnt.
  Keine Modellrekonstruktion, Wahrscheinlichkeit, API oder historischen Daten
  geändert. 229 Tests, unabhängig 54 Tests bestanden (überlappend).
  Beim Eintrag noch nicht auf dem VPS: planmäßiger Tennisjob läuft seit
  04.10. 00:05:12 CEST. Nicht stoppen/neustarten; erst nach seinem echten Ende
  und sicherem Timerfenster den Folgecommit per ff-only übernehmen und prüfen.
- Scannerdiagnose: letzter Wettfinder hatte genau zwei operative Meldungen,
  beide am oben genannten Tennisformat; Fußball hatte null operative Fehler.
  Separater alter Tennis-Abschlussfehler: mindestens 24 im gekürzten Log belegte
  WTA-Prognosen vom 04.–11.09. sind fälschlich Best-of-5. Nicht nachträglich zu
  Gewinnen/Verlusten erklären oder Format/Geldbücher umschreiben. Gesamtzahl wegen
  gespeichertem 2.500-Zeichen-Logtail unbekannt. Die Altformatfälle müssen sauber
  als nicht auswertbare ursprüngliche Prognosen behandelt werden; Geldbindungen
  vorher prüfen. Der laufende neue Job ist noch kein erfolgreicher Abschluss.
- Maßgeblich: [Reparatur- und Bilanzbericht](docs/audits/2026-10-03-auswahlbilanz.md).
  Herkunfts-/Teilnehmer-/Alias-, Zeitfenster- und Query-Laufzeitkanten wurden durch
  unabhängige Gegenprüfung gefunden und abgesichert. Historische Geldbücher bleiben
  unverändert. Bekannte ungetrackte Audit-/Browserdateien nicht aufräumen/committen.
- Weiter offen: tatsächliche Verletzungs-/Wetter-/Müdigkeitswirkung und unabhängiger
  Qualitätsnachweis; qualifizierte weitere Daily3-Sportvergleiche. Keine neue
  Modellkalibrierung auf den nur drei betrachteten Tagen. RisikoBet-Snapshot-
  Abrechnungen sind im neuen Publikationsbericht noch explizite Verknüpfungslücken;
  manuelle Sport-Suchen haben noch kein eigenes Inventarprotokoll. Nächster regulärer
  Wettfinderlauf muss den automatischen neuen Publikationspfad real bestätigen.
  Scanner-Endstatus nicht durch Deployment oder Testzahlen gesundreden.

## 03.10.2026 – Daily3 als zeitlich geordnete Tagesfolge

- Neuer enger Produktfix: Tageskapazität für die restlichen Slots, danach
  chronologische Folge mit Planungsabstand. Fußball/Basketball/Eishockey drei
  Stunden, Tennis/E-Sport vier Stunden einschließlich Abrechnungspuffer.
  Dies sind deklarierte Planungsregeln, keine nachgewiesenen Spieldauern.
  Ein Fußballspiel um 21:00 ist nur als dritter Slot geeignet, nie als Einstieg.
- Nur die erste aktuell geplante Auswahl hat ein Erfassungsformular. Eine
  offene/vorgemerkte Wette verhindert atomar eine weitere Vormerkung, auch wenn
  Restbudget vorhanden ist. Erst tatsächliche Abrechnung oder Verwerfen der
  nicht platzierten Vormerkung erlaubt die nächste Auswahl. Verzögerungen
  können die angezeigte Folge verkürzen; verpasste Spiele werden nicht gewettet.
- Neue Regeln nur für neue Befehle, nicht beim historischen Replay oder
  idempotenten Wiederholungen. Geldrechnung, max. CHF 50 Eigenverlust,
  Modellwahrscheinlichkeiten, Qualitätsgrenzen und 1,20-Quotenfilter unverändert.
  Es wird nicht auf drei aufgefüllt oder global maximale Routenzahl versprochen.
- 539 betroffene Integrations-/UI-/Buchhaltungstests bestanden; unabhängiger
  Gegenlauf 481 bestanden (überlappend, nicht addieren). 36 neue zeitliche,
  konkurrierende und historische Regressionsfälle enthalten. Erste Runde
  isolierte Temp-Verzeichnisrechte und eine echte spätere-Folge-Filterkante;
  beides korrigiert. Anschließend Quoten-/Uhrfixtures zur Morgenplanung gebunden.
  Keine neue Vollsuite behauptet. Ergebnis:
  `output/playwright/daily3-sequence-integration-final-20261003.xml`.
- Interner Browser mit rein lokalen Testdaten: Folge 11:00 → 14:00 → 17:00,
  nur erstes Formular; nach Vormerkung CHF 10 bleiben CHF 40, Folgeformulare
  fehlen bis Abrechnung. Checkbox per Tastatur geprüft; Browser-Locator-Maus-
  Checkbox funktionierte nicht, daraus keinen Mausnachweis ableiten.
- Codefix `2c4f38db2e093f2e5492bab4fb4c6aa3b127017c` committed, auf main
  gepusht und am 03.10. ca. 15:22 CEST per ff-only Pull auf den VPS übernommen.
  Deploylock, sieben nicht laufende Schreiber, mehr als fünf Minuten Timerreserve,
  App gestoppt/vor Start reine Linux-QA grün; keine API-/DB-Schreibaktionen.
  App/Caddy danach aktiv, lokale/öffentliche Healthchecks `ok`; separat erneut
  mit Exit 0 geprüft. Der SSH-stdin-Transport erzeugte nach allen abgeschlossenen
  Schritten einen überzähligen CR und damit Exit 1 im Wrapper (`stage=completed`);
  kein ignorierter QA- oder Appfehler, kein zweites Deployment behauptet.
  Danach Server-HEAD/sauberes Git/Healthchecks direkt erfolgreich nachgeprüft.
  Ergebnissnapshots bytegleich vor/nach Release:
  Wettfinder `17f8d60e04caeda9e8d09e4879e742c42dbf292f765a91f9ab1c22160d33c0cf`,
  RisikoBet `c669c09792f08185c3080c75039659c408fa2bf308840376405cc07d1ba3ac19`.
  Alle sieben Timer weiterhin enabled/geplant, 18 GB frei.
  Abschließender Dokumentations-Commit wird danach separat gezogen; kein Code-
  oder weiterer Appneustart nötig.
  Keine Backups, Extra-Sport-/API-Scans, historischen Geldänderungen oder Cleanup.
- Weiterhin getrennt offen: echte Kontext-/Wettqualitätsnachweise sowie
  zusätzliche qualifizierte Daily3-Sportvergleiche. Die frühere Quoten-Anzeige-
  Empfehlung ist in diesem Daily3-Zeitfix nicht umgesetzt; noch kein kompletter
  UI-Umbau. Tennis-v2-Aktivierung nach dem regulären Lauf hier nicht neu geprüft.
- **Neu aktuell verifiziert, getrennt offen:** Reguläre Dienste Tennis
  (00:28:29), Wettfinder (04:06:52) und Fußball-Shadow (15:22:28) haben heute
  Exit 1/failed. Keine laufenden Prozesse beim Deployment, Fehlerstatus nicht
  zurückgesetzt. Shadow meldet eine alte ungültige Abrechnungs-/Quotenprovenienz
  sowie fehlende frische Bet365-Providerzeiten für 1495960/1495966.
  Gründe der übrigen beiden Lauf-Endstatus hier nicht vollständig diagnostiziert.
  Nicht behaupten, dass alle Scanner gesund oder Tennis-v2 bestätigt sind.
  Kein zusätzlicher Scan und keine Umschreibung der betroffenen Historie.

## 02.10.2026 – alle 16 Scanner-Befunde im Code repariert

**Alle 16 Scanner-Befunde repariert, vollständige Testabdeckung und unabhängiger
Abschlussabgleich bestanden; committed, gepusht und auf dem VPS deployed.**
Code-/Testfreeze: `7e8ba9149269a909a08a802a7bddd1a8009191c0`.
Maßgeblich ist der [Reparaturbericht](docs/audits/2026-10-02-scanner-reparaturen.md);
der darunterstehende Auditblock dokumentiert den früheren, unreparierten Stand.

- T1–T5, S1, L1, B1, H1, R1/R2, F1–F3, J1 und E1 implementiert, Regressionen
  und unabhängige Gegenprüfungen abgeschlossen. Zwei zusätzliche Reviewkanten
  (SofaScore-Ergebnisfehler und erschöpfte Shadowversuche) red-first repariert.
- Root 97, Tennis 372, Live/Rotkarten 309, E-Sport/Context 225 Tests bestanden;
  überlappende Gruppen nicht addieren. Die breite Runde fand eine echte
  historische Tennis-Replayintegration; exakte gerichtete Quellfreigabe und
  Schema-2-Abgrenzung korrigiert (149 Kontext-/196 Versionsprüfungen, unabhängig
  149). Nachprüfung der Rotkarten-Perioden ebenfalls integriert. Die breite
  Runde auf `ce6e07e` wegen reproduzierter Testhelfer-Publikationsuhrfehler
  unterbrochen; keine Produktions-/Speicherfehler. Ursprüngliche Helferdefaults
  wiederhergestellt, vier neue Policyfälle explizit zeitgebunden; 976 betroffene
  Tests/neun Skips, unabhängig 1.120 Tests/neun Skips bestanden. Die folgende
  Runde ohne beobachteten Fehler bei ca. 18 % wegen zusätzlicher T2-Transport-
  korrektur beendet: Beide Parser erhalten ausdrücklich vorhandene Format-
  metadaten (18 Parser→Scan-Matrixfälle, 121 Tests grün; synthetische Metadaten,
  kein tatsächlicher Feed-Abdeckungsnachweis). Der folgende Lauf auf `7e8ba91`
  bei Tool-/Prozessverbindungsverlust ohne vollständiges JUnit beendet (ca. 34 %,
  kein beobachteter Fehler, kein PASS). Dauerhafter Lauf 13:37–14:12 CEST:
  4.884 bestanden/26 Skips/ein WSL-Alias-Umgebungsfehler. Beide Shell-Hooks mit
  Git-Bash bestanden, kein Codepatch/Skip. Konservative dateiweise Fortsetzung
  seit 14:32:55 CEST (PowerShell 7, Git-Bash): 105 vollständig grüne Dateien/
  4.844 Primärfälle übernommen, 198 Dateien/7.339 Fälle vollständig neu;
  12.183 eindeutige Gesamt-IDs unabhängig geprüft. Hook-Datei komplett wiederholt.
  Restlauf 14:45:23 CEST Exit 0: 7.268 bestanden/71 Skips/26 Untertests.
  Aggregator: alle 12.183 IDs exakt einmal, **12.086 bestanden, 97 Skips,
  null Fehler/Errors**, 303 Dateien; Codefreeze/Fingerprint unverändert.
  Vollständige Testabdeckung in zwei disjunkten Dateigruppen, kein einzelner
  erfolgreicher Vollsuite-Aufruf. 111 Untertests zusätzlich, nicht als Primär-IDs
  gezählt. JUnit-/Coverage-/Exit-Hashes stehen im Reparaturbericht.
  Vier CLI-Altfixtures plus echte Legacy-Upgrades/V1-Builder-Reject abgesichert;
  450 Integrations-/254 unabhängige Tests bestanden. POINT-Worker übernimmt
  keine alte Kontexteffekt-Freigabe (29 Endstandtests, statisch unabhängig),
  Grundprognose und Belege bleiben normal veröffentlicht. Policytest ist kein
  empirischer Nachweis. Vorherige breite Runde 62 Fehler, alle drei Gruppen
  genau eingegrenzt; nicht als grün oder finale Vollsuite ausgegeben.
- Release `e233ac4b99e3ad3a014c35148d61b322b3c13f80` ca. 14:53 CEST
  identisch lokal/GitHub/VPS: ff-only Pull unter Deploylock/inaktiven Schreibern,
  kontrollierter Appneustart, reine netzwerkgesperrte Linux-QA bestanden,
  beide Healthchecks `ok`, App/Caddy aktiv, sieben Timer geplant. Wettfinder-
  und RisikoBet-Snapshots per SHA-256 unverändert; 18 GB frei.
  Dieser abschließende Dokumentationsstand wird danach separat ohne
  Codeänderung/Appneustart auf main und VPS übernommen.
  Keine neuen Backups, Pakete, Bereinigungen,
  SQL-Migrationen, Timeränderungen oder zusätzlichen Sport-/API-Scans.
- Aufbau der neuen Tennisverteilung `serve-points-joint-v2` beim regulären
  Rebuild **03.10., 00:05 Zürich** mit eigener Kalibrierung und Schema 2 vorgesehen;
  Aktivierung und Produktionsnachweis erst nach erfolgreichem Lauf bestätigen.
  Vorhandene v1-Artefakte/Prognosen bleiben exakt replaybar und unverändert.
  Nach v2-Publikation ist bloßer Rücksprung auf alten Code nicht schemafähig.
- Historische falsche WTA-Bo5-Belege und abgeschlossene Rotkartensignale
  nicht umgeschrieben. Aktive Historienrücknahmen nur nach tatsächlicher nativer
  Korrektur; kein Löschen von Geld-/Prognosehistorie. Fünf ungeklärte Tennisfälle
  bleiben ohne passenden neuen Ergebnisbeleg offen.
- Verletzungs-/Müdigkeits-/Wettereffekte und unabhängige bessere Wettqualität
  weiterhin nicht nachgewiesen; WTA-/weitere Daily3-Vergleiche offen.
  Cricket bleibt ausgenommen. Keine künstliche Besetzung von Auswahlplätzen.

## 02.10.2026 – Account übernommen und Scanner tief auditiert

**Audit abgeschlossen, Reparaturen daraus noch nicht begonnen.** Maßgeblich:
[Scanner-Tiefenaudit mit Repros und Reparaturreihenfolge](docs/audits/2026-10-02-scanner-tiefenaudit.md).

- Frisch abgeglichen vor diesem Dokumentations-Commit: lokal/GitHub-main/VPS
  `bfb934422e960dd18128cb7e1519b1301c098cdc`, funktionaler Code `1ae37d9`,
  keine Pythonquellen-Differenz. App/Caddy aktiv, beide Healthchecks `ok`, sieben
  Timer geplant. Keine durch Tokenabbruch verlorene aktuelle Codeänderung entdeckt.
  58 Worktrees geprüft; drei Dirty-Meldungen nur gleiche Blobinhalte/leerem Diff.
  Nicht behauptet, dass sämtliche historischen Branches integriert sind.
- Reguläre Produktion heute: Tennis 00:05:17–00:26:56, Wettfinder
  03:35:03–04:03:08, E-Sport 03:10:11–03:10:27 CEST jeweils Erfolg/Exit 0.
  Wettfinder meldet null technische Aktualisierungsfehler. Shadow 07:02 war
  erfolgreich idle, kein neuer Sportscan. Exit 0 allein beweist wegen T3/S1 unten
  nicht generell erfolgreiche Anbieteraufnahme.
- **Gegenpreis-Nachweis erledigt:** 16 tatsächlich gelieferte Tennis-Seitenpreise
  aus acht Events gespeichert. Reiner RisikoBet-Leser bindet fünf vorhandene
  Siegerpreise exakt; keine andere Seite/Satzmarkt-Verwechslung. Kein Extraabruf.
  Morgenprüfung ist abgeschlossen; nicht weiter als fehlenden Nachweis führen.
- Snapshot: 87 Modellkandidaten, davon 68 im reinen zukünftigen Kunden-Auswahl-
  und 1,20-Filterpfad. Das ist kein neuer Browsernachweis. Accountlose Daily3-
  Modellvorschau leer. Altes streng gefiltertes Feld `candidates=0` ist nicht
  gleichbedeutend mit null sichtbaren Modellprognosen.
- **16 neue reproduzierte Befunde (8 P1, 8 P2):** P1 zuerst:
  T1 Tennis-00:05-Lauf entdeckt morgen statt heute;
  T3 kompletter Tennis-Providerfehler kann erfolgreicher Null-Lauf werden;
  S1 Shadow-Spielplanfehler schreibt Fertigmarker und verhindert Wiederholung;
  R1 Rotkarten-Torabruf HTTP-Fehler kann fälschlich `no_goal` abrechnen;
  T2 WTA-Grand-Slam-Format übernimmt Bo5 und blockiert korrekte 2:0-Abrechnung;
  H1 explizit zurückgezogene Finals bleiben im Sporthistorien-Cache;
  B1 Basketball-Neutralflag geht verloren; L1 Live-Restzeit endet starr bei 93.
  Offline-Repros, nicht pauschal nachgewiesene aktuelle Produktionsschäden.
  R1 betrifft Shadow-/Kalibrierungsbelege, kein belegter Echtgeldbuchungsfehler.
- P2 danach: Count-Marktfrische aus falscher Torhistorie (F1), globaler
  Familien-Kalibrierungsfehler (F2), verspätete Scan-Persistierung (J1),
  E-Sport-Rohduplikate vor Stichprobengrenze (E1), Tiebreak-Halte-/Punktproxy
  (T4), getrennte Sieger-/Satzwahrscheinlichkeiten (T5), fehlende Expositions-
  minuten im Rotkarten-Phasenbericht (R2), dauerhaft veraltete Live-Torgrundlage
  im Analyzer-Saisoncache (F3). Jeweiliger Repro im Auditbericht. Der separate
  aktive BTTS-Live-Prior wurde ebenfalls geprüft; dessen RF-Wert wird nicht
  als Live-Torwert genutzt. Kein taggleicher Trainings-Leakage-Befund.
- Tennis jetzt **fünf**, nicht vier ungeklärte Ergebnisse: ATP 183397/183448/186254,
  WTA 184266/186216. ATP 183448 neu gegenüber der Übergabe; nichts gelöscht.
  Kalibrierungswatch bleibt der datierte Driftbericht vom 28.09., keine heutige
  Neukalibrierung. Shadow null Benchmarkfälle, kein ROI-/Qualitätsbeleg.
- Verletzungs-/Müdigkeits-/Wetterwirkung und unabhängiger Qualitätsnachweis
  weiterhin offen. Bestehender experimenteller Anschluss ist keine qualifizierte
  öffentliche Modellverbesserung. WTA-/weitere Sport-Daily3-Vergleiche offen;
  Cricket bleibt von Implementierung ausgenommen. Keine Plätze künstlich füllen.
- Heute gezielt: 356 Auswahl-/Daily3-/Preis-/Jobtests, 194 weitere Sport-/History-
  Tests, 166 Tennistests, 19 Rotkarten-Logtests und 9 BTTS-Inputtests bestanden. Gruppen überlappen,
  nicht addieren. Vollsuite 11.929/97 Skips/111 Untertests ist vom 01.10.,
  nicht neu ausgeführt; JUnit-Hash nochmals bestätigt. Neue Fehler-Repros sind
  noch keine eingebauten Regressionstests und wurden nicht repariert.
- Kein zusätzlicher API-/Sport-/Modell-/Quotenscan, Backup, Cleanup, Migration,
  Timer- oder Produktionscodeänderung. Nur Audit/TODO/Übergabe dokumentieren
  und unter bestehender Freigabe committen/pushen sowie auf dem VPS ziehen.
  **Nächster Implementierungsschritt erst bei Reparaturauftrag:** kleine Tests
  für T1/T3/S1, dann gezielte Korrekturen; keine neue Generalplattform.

## Accountwechsel – verifiziert am 01.10.2026, 20:29 CEST

**Technische Reparaturen veröffentlicht; fachliche Kontexteffekte noch offen.**

- Frischer Abgleich vor diesem Dokumentations-Commit: lokal, GitHub `main`
  und VPS exakt `01a79b40bc3526b0b3ab7e6b42be200dd56bb21a`, VPS tracked-clean.
  Funktionaler Code: `1ae37d9`; App/Caddy aktiv, beide Healthchecks `ok`,
  alle sieben Timer geplant. Die Tests unten sind der abgeschlossene Morgenlauf,
  kein neuer Testlauf dieser Übergabe: 11.929 bestanden / 97 Skips / 111 Untertests.
- Letzte reguläre Läufe heute: Tennis 00:05:12–00:28:52 und Wettfinder
  03:35:06–03:58:51 CEST, jeweils `Result=success`, Exit 0, inzwischen inaktiv.
- **Als Nächstes:** regulären Tennis-Lauf am 02.10. um 00:05 und Wettfinder um
  03:35 CEST abwarten. Danach vorhandene Produktionsberichte und
  `tennis_price_observations` read-only prüfen: tatsächlich gelieferte Gegenpreise,
  exakte Spiel-/Seiten-/Zeit-/Marktbindung und 1,20-Filter. Die neue Speicherung
  ist getestet; ihre Befüllung im nächsten echten Lauf ist noch nicht nachgewiesen.
  Keine zusätzliche Sport-, Modell-, Quoten- oder API-Abfrage starten.
- **Offen:** numerisch qualifizierte Verletzungs-, Müdigkeits- und Wettereffekte
  samt unabhängigem Qualitätsnachweis. Der Football-Jointanschluss bleibt ein
  interner Vergleich, keine aktivierte Verbesserung des öffentlichen Modells.
  Morgenprüfung: null freigegebene Kontext-Effekt-Slots. Inventur vom 28.09.
  ist historische Evidenz, nicht eine aktuelle Datenabdeckung. Nächster enger
  Messschritt: WTA-Erholungsuntergrenze mit vorhandenen Belegen; Hypothese und
  zeitlich getrennte Training-/Abstimmungs-/Testpartition vor Auswertung einfrieren.
  Bei zu wenigen unabhängigen Testfällen konkrete Lücke dokumentieren; keine
  erfundenen Effekte, gelockerten Qualitätskriterien oder neue Generalplattform.
  Cricket bleibt ausgenommen. Bessere Wettqualität ist noch nicht belegt.
- Vier ungeklärte Tennis-Ergebnisse weiter verfolgen: ATP 183397/186254 und
  WTA 184266/186216. Kein Löschen von Prognosebelegen oder Geldbuchungen.
- Abschlusscheck: tatsächlicher App-Dienst `betboy-app.service` aktiv, Health `ok`.
  Fünf alte Wartungsunits stehen weiterhin auf `failed`: `betboy-release-afc8a10-20260918`,
  `betboy-release-afc8a10-20260918b`, `betboy-release-context-c64218b-20260918`,
  `betboy-release-product-53f2e2c-20260919`, `betboy-storage-repair-20260919`
  (jeweils `.service`). Historische Fehlstatus, kein Nachweis eines heutigen
  App-Ausfalls; nicht zurückgesetzt oder erneut ausgeführt. Bei späterem
  Wartungsaudit die ursprünglichen Journale prüfen, nicht blind neu starten.
- Übergabe verändert nur diese Dokumentation: keine Sicherung, Bereinigung,
  Migration, Timeränderung oder neuer Scan. Bestehende ungetrackte Audit-/Browser-
  Dateien erhalten. Produktionswriter ausschließlich auf dem VPS; keine lokalen
  produktiven Worker starten. Details und Prüfnachweise stehen im Block darunter.

## 01.10.2026 – Tennis-Gegenquoten und Kontextanschluss live, Vollsuite grün

- Funktionaler Code `1ae37d9ac0736bfeaf76e511c9602ab32b1c4d37` auf GitHub-main
  und um 08:45 CEST auf dem VPS veröffentlicht; lokal identische getestete Basis.
- Beide tatsächlich gelieferten Tennis-Siegerpreise werden aus derselben
  vorhandenen Antwort separat im bestehenden Wettfinder-Schnappschuss bewahrt.
  Keine zusätzliche HTTP-Abfrage, Modellkarte, Datenbank oder Preisberechnung.
  RisikoBet liest nur exakt gebundene native Spiel-/Seiten-/Zeit-/Marktbelege;
  kein Favoritenpreis für den Gegner und keine Siegerquote für Satzmärkte.
  Höchstens zehn Ereignisse / 20 Seiten / 256 KiB, Originalzeit, maximal 24 h.
- Football-Jointvergleich nach persistiertem regulärem Capture angeschlossen:
  echte spätere Vor-Anpfiff-Uhrzeit, unverändertes Grundmodell, nur interner
  experimenteller Vergleich. Ohne vorhandenen passenden Fit keine neuen
  Speicherzeilen. Wiederverwendung und abgelehnte Größen-Vorprüfung reservieren
  nichts; neue/teilweise Veröffentlichungen maximal 512 KiB/Event / 1 MiB/Lauf.
- Vollsuite-Diagnose passierte die früher verdächtigen 40–44-/76-%-Bereiche;
  bei 97 % zwei veraltete Editorial-Testverträge konkret gefunden und korrigiert.
  Kundenansicht, interne Belege, Modellwerte und genaue Quotenbindung bleiben
  abgesichert; keine Appänderung oder zusätzliche Skips aus dieser Testkorrektur.
  Alte Fehlerursache ohne Originaltrace nicht bewiesen. Diagnose: 11.615
  bestanden / 97 Skips / 111 Untertests, ein Fehler; ausdrücklich kein PASS.
- Vollsuite auf eingefrorenem `1ae37d9`: 12.026 gesammelt, **11.929 bestanden,
  97 Skips, 111 Untertests bestanden**, Exit 0 in 37:26. JUnit null Fehler /
  Failures, neun Metadatenwarnungen. Die beiden zuvor gezielt gestoppten
  Freeze-Läufe sind STOPPED, nicht bestanden. 95 Integrationsprüfungen vor der
  letzten Korrektur und zuletzt 54 Helper-/Integrationstests grün; nicht addieren.
- Eigener Offline-Browser: echte Gegenpreis-Fixture 1,12 ausgeblendet,
  1,20/2,70 sichtbar bei unverändert 36 %; 1440/390/320 ohne Überlauf.
- Noch offen: empirisch qualifizierte Verletzungs-/Müdigkeits-/Wetterwirkung.
  Aktiver Produktionsmanifest enthält nur ATP/WTA, null Kontext-Effekt-Slots.
  Der Anschluss ersetzt keine fehlenden Daten oder unabhängigen Qualitätstests.
  Keine behauptete Verbesserung der Trefferquote/Rendite. Vollständige
  Merkmalsinventur bleibt die datierte 28.09.-Auswertung, nicht neu gescannt.
- Regulärer Tennislauf 01.10. 00:05–00:28 CEST und Wettfinder 03:35–03:58:
  erfolgreich, Exit 0. Vier ungeklärte Tennis-Ergebnisse bleiben separat offen.
  Heute vor Veröffentlichung null gespeicherte reine Gegenpreis-Belege:
  Befüllung erst durch nächste reguläre Anbieterantwort, keine Extraabfrage.
- Keine Sicherung, Bereinigung, Migration, zusätzlicher Sport-/API-/Modellscan
  oder Timeränderung. Ungetrackte Audit-/Browserdateien erhalten.
- Deployment unter bestehendem Lock: acht geprüfte Code-/Testdateien, alle
  Writer inaktiv und >120 s bis nächstem Termin, nur App neu gestartet.
  Beide Healthchecks `ok`, App/Caddy aktiv, sieben Timer geplant. Modell- und
  RisikoBet-JSON vor/nach Deployment bytegleich. VPS-Offline-Fixture bestätigt
  beide real gelieferten Beispielpreise, ohne Netzwerk oder Datenbankschreiben.
- Frischer Produktionsbrowser nach vollständigem Rendern: 63 kommende
  Szenarien / 38 Events; 1440/390/320 ohne Überlauf, null Console-Fehler.
  Zehn bekannte Framework-/Iframe-Warnungen. Erste zu frühe Screenshots zeigten
  nur den Kopf; zustandsgebunden mit sichtbaren Karten wiederholt und geprüft.
- Nachweis: [Fortsetzung im bestehenden Prüfbericht](docs/audits/2026-09-30-wetter-tennis-preiszuordnung.md#fortsetzung-01102026).

## 30.09.2026 – weitere 60 Minuten: Wetterzeitpunkt und Tennis-Preiszuordnung

- Code `707e2f802f9d14a849bd1d3ad74fb5e23e722f3f` committed, auf main gepusht
  und um 19:09 CEST exakt auf dem VPS fast-forwarded. Keine Sicherung,
  Bereinigung, Migration oder zusätzliche Sport-/API-Abfrage. Sieben Timer
  unverändert; App/Caddy aktiv, beide Healthchecks `ok`.
- Wettercache repariert: Spiele derselben Stadt und UTC-Stunde wählen ihren
  eigenen nächsten Vorhersagepunkt aus derselben bereits empfangenen Antwort.
  Empfangszeit bleibt original; keine zusätzlichen Abrufe. Antwort-RAM begrenzt,
  ungültige Zeiten und unvollständige Punkte werden nicht passend erfunden.
- RisikoBet übernimmt vorhandene Tennis-Siegerquoten nur bei exakt gleichem
  nativen Spiel, Anpfiff, Spielerreihenfolge, gewählter Seite und Wettvertrag.
  Bekannte Quoten unter 1,20 erreichen jetzt auch dort den bestehenden Filter.
  Niemals Favoritenquote auf Außenseiter oder Siegerquote auf Satzmarkt übertragen.
- Wichtige offene Datenlücke: normaler Bestand 11 Tennis-Auswahlen / 3 Quoten;
  RisikoBet wählt bei denselben drei Spielen jeweils den Gegner. Somit heute
  **0 passende RisikoBet-Tennispreise**. Gegenpreise werden beim regulären Abruf
  bislang verworfen. Der Preisjoin allein behebt diese Abdeckung nicht.
- Nächste begrenzte Reparatur: beide tatsächlich gelieferten H2H-Seiten aus dem
  ohnehin geplanten Abruf als separaten, begrenzten Preisbereich im bestehenden
  Schnappschuss speichern; keine zusätzlichen Modellkarten, Dateien oder APIs.
  Konkrete Integrationspunkte/Tests im neuen Prüfbericht. Kein neuer Designprozess.
- Gezielte Tests und zwei unabhängige Codeprüfungen bestanden. Vollsuite mit
  11.940 Fällen meldete Fehler bei etwa 40–44 %, anschließend für das begrenzte
  Zeitfenster bei 90 % angehalten: **kein Vollsuite-PASS**. Weitere Fehler um
  76 %; die zuletzt gepufferten Ausgaben wurden beim Stop noch nachgeliefert.
  Benachbarte Gruppen
  einzeln grün (479 Tests; Updater 111 plus ein Windows-Skip; unabhängiger Hook
  351). Ursache der ursprünglichen Fehler noch ungeklärt, nicht wegklassifiziert.
  Nächste Prüfung: Vollsuite `-x --tb=short` mit kurzem neuen Basetemp, ersten
  konkreten Trace sichern; keine Tests blind ändern/überspringen.
- Eigener Browser: Preisbeispiele 1,12 ausgeblendet / 1,20 und 1,52 sichtbar,
  Prognose unverändert, 1440/390/320 ohne Überlauf. Live nur zwei kommende
  Basketball-Szenarien; keine begonnenen Tennis-/E-Sport-Spiele. Keine Browserfehler.
- Weiter offen: modelllose Basketball-Karten mit redundanten Datenlückentexten;
  Daily3-Seitenleiste kennt verbrauchte Slots/gespielte Events nicht und ist nur
  Modellvorschau, nicht Kontostand. Kein Geld-/Ledgerfehler daraus nachgewiesen.
- Tennislauf 30.09. 00:05–00:24 CEST: Exit 0, Scan/Gesamt OK, 33 neue Prognosen;
  drei alte Ergebnisfälle ungeklärt, ein natives Ergebnis nicht verfügbar.
  Die frühere Tennis-Nachprüfung ist bereits PAUSED, unverändert belassen.
- Numerisch qualifizierte Verletzungs-/Wetter-/Müdigkeitseffekte und bessere
  Wettqualität bleiben offen. Wetterquellenkorrektur ist keine Effektfreigabe.
- Aktuelles Aktivierungsmanifest enthält nur ATP/WTA, keine Kontext-Effekt-Slots.
  Letzte vollständige Merkmalsinventur weiterhin 28.09., nicht heute. Nächster
  vorhandener Anschluss: Football-Jointvergleich nach persistiertem Capture am
  echten späteren Vor-Anpfiff-Stichtag; keine neuen Datenabfragen oder Gewichte.
- [Prüfbericht](docs/audits/2026-09-30-wetter-tennis-preiszuordnung.md).

## 30.09.2026 – RisikoBet-Zeitfilter und kompakte Serienform

- Reproduziert am echten Bestand: 70 RisikoBet-Szenarien, davon 60 bereits
  nach angesetztem Beginn. Der reine Leser behält alle Originalbelege; nur
  kommende Vorschlagskarten werden vor Katalog, Preisen und Seiteneinteilung
  nach `starts_at > now` gefiltert. Kein Ergebnis aus der Uhrzeit erfunden.
- Alle sechs Sportarten, exakter Beginn, Zeitzonen/DST, gültige neue
  Terminrevision und unveränderter alter Kontext getestet. Die Ansicht wird
  beim Aufruf/Neurendern aktualisiert; kein zusätzlicher Browser-/Sporttimer.
- E-Sport-Form: Sieg/Niederlage-Plättchen und Bilanzen bleiben erhalten,
  leere Gegner-/Ergebniszeilen entfallen. Ein kurzer Hinweis statt vielfacher
  Leertexte. Tatsächlich vorhandene Gegner, Resultate und Termine bleiben.
- 769 betroffene Integrationstests bestanden (548 Karten/RisikoBet/Logos plus
  221 Daily3/Auswahl/Untergrenze); unabhängiger Gegenreview ohne Befund.
  Vollsuite mit 11.878 gesammelten Tests bei 22 % für das ausdrücklich
  begrenzte 30-Minuten-Fenster abgebrochen, nicht als Vollsuite-Erfolg gewertet.
- Code `c9de1e9` committed, gepusht und per kontrolliertem Pull auf VPS live.
  Live 7 kommende Szenarien aus 6 Events; 63 gestartete Szenarien ausgeblendet.
  Tsitsipas/Gea/Djokovic und inzwischen gestartete Vitality/LOUD nicht mehr im
  kommenden Katalog. Reale E-Sport-Form ohne leere Gegnerzeilen, 5↔10 funktioniert.
  1440/390/320 ohne horizontalen Überlauf. Beide Healthchecks `ok`, sieben Timer
  geplant; Modell-/RisikoBet-Dateien bytegleich. Keine API-Abfrage, Modell-/
  Geldänderung, Sicherung oder Bereinigung.
- [Prüfbericht](docs/audits/2026-09-30-kundenansicht-zeitfilter.md) enthält
  Reproduktion, Software- und sichtbare Produktionsbelege sowie klare Grenzen.
- Empirische Kontexteffekte und bessere Wettqualität bleiben eigene offene
  Aufgaben; diese Darstellungsreparatur belegt keine Verbesserung der Modelle.

## 30.09.2026 – Teamlogos für die weiteren Sportarten

- E-Sport, NBA, NHL, EuroLeague und Cricket nutzen jetzt dieselben externen
  Bild-Schildkarten wie Fußball/Tennis. Keine gespeicherten Bildbytes oder
  Bildkopien auf BetBoy. Provider-ID, Sport und vollständiger Teamname gebunden;
  bei NBA zusätzlich ausdrücklich NBA statt WNBA/NCAA. Fehlende Zuordnungen
  behalten Initialen. Modelle, Preise und Geldbelege bleiben unverändert.
- Kuratiert: 32 aktive NHL-Teams, zwei EuroLeague-Teams, neun E-Sport-Teams,
  Indien/Australien für zwei Cricket-Provider. NBA über native ESPN-ID plus NBA.
  Visuell falsches `1w`-Bild (Dota-Spielicon) ausdrücklich verworfen.
- Künftige E-Sport-Logolinks werden aus ohnehin empfangenen Antworten übernommen;
  Metadaten maximal 256 Teams / 128 KiB, identische Daten ohne Neuschreiben.
  Keine zusätzliche API-Abfrage, kein Sportscan, keine Sicherung/Bereinigung.
- Lokale Software-, Desktop-/Mobil-, Fehlerfall- und Produktionsnachweise stehen
  im letzten Abschnitt von [Schildbilder](docs/audits/2026-09-30-schildbilder.md).
  Basket-/Hockey-/Cricket-Logos sind keine nachträgliche Modellfreigabe oder
  Garantie, dass für diese Sportarten aktuell produktive Auswahlen vorliegen.
- Code `778434a` auf main und VPS live, 674 Tests und ein erwarteter Windows-Skip.
  Live geprüft: Spirit, Vitality und LOUD mit korrekten Logos, 1win bei Initiale.
  Modelle/Preisbestand bytegleich, beide Healthchecks `ok`, sieben Timer geplant;
  1440/390/320 ohne Überlauf oder Browserfehler. Weitere Sportgrafiken lokal und
  per VPS-Resolver geprüft, aktuell keine entsprechenden Produktivkarten.

## 30.09.2026 – Bilder direkt beim Anbieter, ohne BetBoy-Bildcache

- Die Anschlussänderung ersetzt den RAM-Bildcache der unten dokumentierten
  Erstumsetzung: Browser lädt Vereinswappen und Spielerfotos direkt über HTTPS
  beim Anbieter. Server speichert nur vorhandene Bildlinks/Quellenmetadaten,
  keine Bildbytes, Bilddatei-Kopien oder Bilddatenbanken. Normales Browsercaching
  ist möglich. Bestehende dekorative Editorial-Banner bleiben unverändert.
- Wappen: API-Sports-CDN mit eindeutig gebundener API-Football-Teamkennung;
  Spieler: kuratiertes Commons-Manifest, derzeit 330-px-Vorschaubilder. Keine
  Original-/Hochauflösungs-URLs; Grenze 400 px. Schildform, Bildausschnitt und
  Quellen-/Lizenznachweis erhalten. Fehlende Bilder zeigen Initialen.
- Code `d4274a3981601ed724fd1d6651cf376b4ad1ce10` committed, gepusht und per
  kontrolliertem Pull auf dem VPS live. 464 betroffene Tests bestanden;
  unabhängiger Review ohne Befund. Eigener Browser: 8 Direktabrufe mit HTTP 200,
  gezielter 404-Fallback, Wiederherstellung und neue DOM-Knoten geprüft;
  Desktop 1440 und Mobil 390/320 ohne horizontalen Überlauf.
- Echte Djokovic-/Borges-Karte: zwei direkte 330-px-Fotos, unverändert 75,9 %
  und letzte Quote 1,42. Moduswechsel und Neurender funktionieren. App/Caddy
  aktiv, beide Healthchecks `ok`, sieben Timer weiter geplant.
- Keine Modell-/Preis-/Geldänderung, kein Backup, keine Bereinigung und kein
  zusätzlicher Sport-/API-Scan. Gespeicherter Modell-/Preisbestand bytegleich.
  [Prüf- und Produktionsnachweis](docs/audits/2026-09-30-schildbilder.md#direktabruf-ohne-server-bildcache-30092026).

## 30.09.2026 – Originalbilder in der bestehenden Schildform

- Wettfinder und Daily3: Fußball zeigt Originalwappen über die vorhandenen
  API-Football-Teamkennungen; Tennis zeigt überprüfte, frei lizenzierte
  Spielerfotos. Die bestehende Schildkontur bleibt unverändert. Wappen werden
  vollständig eingepasst, Spieleraufnahmen passend auf Gesicht/Oberkörper
  fokussiert. Herkunft und Lizenz bleiben über das kleine `© Foto` erreichbar.
- Die kuratierte Fotoliste enthält derzeit 13 eindeutig identifizierte Spieler,
  einschließlich aller sechs zum Prüfzeitpunkt anstehenden Tennis-Teilnehmer.
  Unbekannte Spieler oder nicht verfügbare Originalbilder behalten Initialen;
  keine erfundenen Gesichter oder Wappen. Neue Fotos benötigen eine geprüfte
  Namens-, Quellen- und Lizenzzuordnung in `assets/identity/tennis-portraits.json`.
- Ausschließlich Darstellung: keine Modell-, Auswahl-, Preis-, Einsatz- oder
  Abrechnungsänderung. Bilder werden begrenzt im Arbeitsspeicher zwischengespeichert;
  keine neue Datenbank, Bilddatei-Kopie, Sicherung oder zusätzlicher Sportscan.
- Prüfung vor Veröffentlichung: 442 betroffene Tests bestanden. Originalbilder
  für zwei Vereine und sechs Tennis-Spieler tatsächlich geladen; Desktop sowie
  390/320 px ohne horizontalen Überlauf oder Page-/Console-Fehler geprüft.
  Unabhängiges Review; abschließender Produktionsnachweis im Aufgabenbericht.
- Code `4e87ca2` auf main und VPS veröffentlicht; echte Gea-/Zhang-Bilder im
  Wettfinder und in Daily3 geladen. Healthchecks `ok`, sieben Timer geplant,
  gespeicherter Modell-/Preisbestand vor/nach Veröffentlichung bytegleich.
  [Produktionsnachweis](docs/audits/2026-09-30-schildbilder.md).

## 30.09.2026 – Tennisquoten live, RisikoBet-Kurzform korrigiert

- Tennis-Quotenabruf im Produktionslauf wieder angeschlossen; expliziter
  Quotenlauf aktualisiert nur Preise zu vorhandenen Modellen. Gemeinsamer
  Budgetschutz und bekannte 1,20-Untergrenze unverändert. Keine Modell-/
  Ranglisten-/Geldänderung, kein zusätzlicher Sportscan oder neues Backup.
- Zusätzlich real gefunden und repariert: `Zhang Zhizhen` / `Zhizhen Zhang`
  sowie der Reader-Fehler, der nach neuer Quote den gesamten Katalog verwarf.
  Namensbindung verlangt alle vollständigen Wörter; Preisprüfzeit ist separat
  validiert, Modellzeit wird nicht erneuert. Kein lockeres fuzzy Matching.
- Echter VPS-Nachabruf 30.09.2026, 09:44 CEST: drei anstehende Auswahlen geprüft,
  drei Preise, null Abruffehler. Arthur Gea 1,28 aus 20 Buchmachern; Sakamoto
  1,73 aus 16; Djokovic 1,42 aus 20. Modellwerte/-reihenfolge unverändert,
  `generated_at` weiterhin 01:52:46 UTC. Tatsächlicher Leser wieder gültig,
  zehn aktive Prognosen. Gea-Karte zeigt 79,4 % und Quote 1,28 im Livebrowser.
- RisikoBet-Nutzerfall: kurzes Belagfeld, getrennte 5-/10-Spielerquotienten,
  keine Serve-/Erholungsprotokolle, isolierten Satzbeobachtungen, langen
  Formmetadaten, leeren Analysefelder oder identischen doppelten Markttexte.
  Originalbelege unverändert; echte Sportfakten und Gegenargumente erhalten.
- Finale betroffene Integration: 767 Tests und 26 Untertests bestanden;
  unabhängige Namens-/Preiszeit-/UI-Reviews ohne offene P1/P2-Befunde.
  Lokale und echte RisikoBet-Karte sowie reale Gea-Quotenkarte bei
  1440/390/320 px geprüft, kein horizontaler Überlauf oder neuer Browserfehler.
- Codecommits `bf62ab7` und `7b60496` auf GitHub main und per geprüftem
  Fast-forward auf dem VPS veröffentlicht; App/Caddy aktiv, beide Healthchecks
  `ok`. Folgender Nachweiscommit ist nur Dokumentation; keine Neuerstellung
  von Sicherungen, Datenbereinigung oder weiteren API-Abfragen.
- [Ursachen, Reparatur und Produktionsnachweis](docs/audits/2026-09-30-tennisquoten-riskobet-kurzform.md).
  Separat offen bleiben empirisch belegte Kontexteffekte und Gesamt-Wettqualität.
  Damals führte RisikoBet bereits begonnene Tagesszenarien noch im Katalog;
  diese separat behandelte Lücke ist durch den obersten Zeitfilter-Block behoben.

## 30.09.2026 – Modellnotizen intern, Sportfakten für Kunden

- Kundenkarten zeigen keine wiederholten `Statistik & Details`-Modellabsätze,
  `Berechnet`-Footer, heuristischen Sicherheitswerte oder Evidenz-Badges mehr.
  Gilt für Wettfinder, Daily3 einschließlich gespeicherter Wetten, manuelle
  Suche und RisikoBet einschließlich seiner separaten Detailausgaben.
- Echte Form-/Belag-/Gegner-/Ergebnisdaten, Kaderfakten und Gegenargumente bleiben
  erreichbar. Fehlende oder veraltete Sportdaten werden nicht als vollständig
  oder aktuell umdeklariert. Keine Änderung an Modellen, Auswahl, Quoten oder Geld.
- Originalbelege bleiben in Prognosen und RisikoBet-Snapshots, den
  `analysis_*`-Feldern/`CompactAnalysis.explanation` und signierten Daily3-
  Wettsnapshots erhalten. Keine zusätzliche Datenbank oder Nachweiskopie nötig.
- Prüfung: 611 betroffene Tests bestanden; unabhängiges Randfallreview mit 80
  Tests ohne Befund. Neun lokale Browserkombinationen (Wettfinder/Daily3/
  RisikoBet bei 1440/390/320 px), Formwechsel 5/10 und zehn echte Ergebniszeilen
  geprüft. Keine Page-/Console-Fehler; bekannte iframe-Warnungen unverändert.
- Separat weiterhin offen: Der automatische Tennis-Quotenpfad ist im aktuellen
  Tageslauf ausdrücklich deaktiviert (`disabled_for_model_only_tips`, 0 geprüft).
  Die Anzeige `Quote –` bei Gea/Zhang kommt nicht aus dieser UI-Korrektur;
  seine Anbindung wurde in dieser Aufgabe nicht verändert.
- UI-Code `d62d5d998d978aa96e00129fa88b118215aa2d0b` auf GitHub main und
  per geprüftem Fast-forward auf dem VPS veröffentlicht. Produktionsnachweis
  am 30.09. gegen 08:32 CEST: echte Gea/Zhang-Karte bei 1440/390/320 px ohne
  Techniktexte, zehn Gegnerergebnisse erreichbar, Daily3 (eine Auswahl) und
  RisikoBet (23 Karten) ebenfalls geprüft. Keine neuen Page-/Console-/Request-
  Fehler, beide Healthchecks `ok`, App/Caddy und sieben Timer aktiv.
  Folgender Nachweiscommit nur Dokumentation; kein neues Backup, zusätzlicher
  Sport-/API-Scan oder Finanzvorgang.

## 30.09.2026 – Sports Editorial nach Nutzerbeanstandung korrigiert

- Der Nutzer hat die erste Oberfläche als nicht vorlagentreu beanstandet.
  Vorheriges „abgenommen“ war keine visuelle Nutzerabnahme. Design 2 Web / 2+5
  Mobil bleibt der verbindliche Auftrag; Originalreferenzen unverändert erhalten.
- Jetzt strukturell korrigiert: Begegnung und Auswahl nebeneinander, Formvergleich
  mit drei sichtbaren Gegnerzeilen; weitere Märkte im selben Spielblock.
  Lokale Stadion-/Tennisbilder und Daily3-/Tennisspalte auch bei leerem Spieltag.
  Kompakter Kopf, Magazinfarben und native fünfteilige Mobilnavigation.
- Final 531 betroffene Tests nach letzter Produktions-Wrapper-Korrektur bestanden.
  31 Layout-/Randfallkombinationen geprüft,
  einschließlich tatsächlicher Spalten-/Covergeometrie, 5/10 und Navigation.
- [Korrekturbericht und aktueller Veröffentlichungsstatus](docs/audits/2026-09-30-sports-editorial-korrektur.md).
  Kein neues Backup, zusätzlicher Scan, Finanzvorgang oder Modellumbau.
  Native Apps, reale Geräte und numerische Kontexteffekte bleiben separat.
  Finalen visuellen Zuspruch des Nutzers nicht aus Tests ableiten.
- Finaler UI-Commit `c6b66c3` auf main und VPS. Frisch im Produktionsbrowser bei
  sieben Breiten geprüft, beide Bilder geladen, 23 RisikoBet-Karten und direkter
  Desktop-/Mobilrückweg bestätigt. Keine Page-/Console-/Request-Fehler, neun
  bekannte iframe-Warnungen. Beide Healthchecks `ok`, App/Caddy und sieben Timer
  aktiv. Folgender Nachweiscommit nur Dokumentation, keine Codeänderung.
  Für den neuen Tag noch kein automatisches Ergebnis vor 03:35; kein Scan erzwungen.

## 30.09.2026 – erste Sports-Editorial-Umsetzung (Historie, technisch geprüft)

- Nutzerwahl: **Design 2 für Webbrowser; Mischung aus Design 2 und 5 für Mobil/App**.
- Referenzbilder und knapper Umsetzungsvertrag:
  [Sports Editorial](docs/ux/sports-editorial/DESIGN.md).
- Responsive Oberfläche umgesetzt: lokale Sporttypografie, horizontale
  Desktopnavigation, feste fünfteilige Mobilnavigation und gemeinsame Spielkarten.
  Echte 5/10-Ergebnisfelder mit Gegnern, Spielständen und erreichbaren Details;
  identische Formdaten innerhalb einer Spielgruppe nur einmal anzeigen.
- Wettfinder, Daily3 und vorhandene manuelle Formanzeigen verbunden; RisikoBet
  ebenfalls gestaltet. Keine zusätzlichen Datenabfragen beim 5/10-Wechsel.
- 526 betroffene Tests bestanden; 29 Browser-/Randfallkombinationen bei
  320/390/760/1024/1440 px sowie Maus, Tastatur und Touch-Emulation bestanden.
  Daily3-Vorschau berücksichtigt die bestehenden Abo-Rechte; Budget, gespeicherte
  Wetten, Modelle, Auswahlregeln und bekannte 1,20-Untergrenze bleiben unverändert.
  Mobilnavigation auch auf Abo-Hinweisseiten erreichbar; kein Rechte-Bypass.
  Desktop-/Mobilsteuerung in gemeinsamen Callbacks synchronisiert; kein
  konkurrierendes verstecktes Navigationswidget. Drei direkte Rückwege geprüft.
- [Abnahme und Veröffentlichungsstatus](docs/audits/2026-09-30-sports-editorial.md).
  Kein neues Backup, Sport-/API-Scan oder Bereinigung. Native Apps und echte
  Mobilgeräte sind damit nicht abgenommen. Numerische Kontexteffekte sowie
  Kunden-/Storebetrieb bleiben die separat unten beschriebenen Restarbeiten.
- UI-Code `f673c8d` auf GitHub und per Fast-forward auf dem VPS veröffentlicht;
  um 00:39 CEST identische Codehashes, beide Healthchecks `ok`, App/Caddy und
  sieben Timer aktiv. Frische Produktionsprüfung einschließlich 23 RisikoBet-
  Karten und Desktop-/Mobilrückweg bestanden. Der folgende reine Nachweiscommit
  ändert keinen Python-Code. Tages-Wettfinder erst regulär um 03:35 CEST;
  kein zusätzlicher Scan erzwungen. Tennis zuvor regulär Exit 0 um 00:24:27.
- Alte V2-Abschlussnotiz ist historisch, nicht die Abnahme dieses neuen Designs.

## 29.09.2026 – Quotenabruf für die bekannte 1,20-Untergrenze

- Regulärer produktiver Fußballlauf nutzt wieder den vorhandenen API-Football-
  Quotenadapter nach der Modellberechnung: höchstens zehn Spiele pro Lauf,
  eine Anfrage pro Spiel für mehrere exakt zugeordnete Märkte, bestehendes
  API-Budget bleibt wirksam. Kein neuer Anbieter oder kostenpflichtiger Tarif.
- Isolierte Tests/Replays starten weiterhin keinen impliziten Quotenabruf.
  Modellwerte und Rangfolge bleiben unverändert; bekannte passende Quoten
  unter 1,20 werden durch die vorhandenen Verbraucherfilter ausgeblendet.
  Fehlende Anbieterabdeckung bleibt möglich; keine Quote erfinden.
- Geprüft: 196 Tests für Tageslauf, gemeinsame Quoten, Mindestquote und Daily3.
  Kein Modell-/Datenbankumbau, kein neues Backup. Veröffentlichungsnachweis
  separat anhand Git/VPS prüfen; diese Notiz allein bestätigt kein Deployment.

## Accountwechsel 28.09.2026, 20:29 CEST – hier fortsetzen

Diese Aktualisierung betrifft nur die Übergabe, nicht Programmcode oder Modelle.
Die datierten Abschnitte darunter sind Historie; deren damalige offene Punkte
nicht ungeprüft wieder als aktuell ausgeben.

### Erledigt und verifiziert

- Codepatch `42054e35d8ce855ef80c6c74cc9bdccb8467e451` live; anschließender
  Nachweiscommit `2155d06cd8d741300cbdec8be72c2aa0c60a3281` am 28.09. um
  20:29 CEST erneut identisch lokal, auf GitHub `main` und auf dem VPS bestätigt.
  Die folgende reine Übergabefortschreibung verändert diesen Programmstand nicht.
- Vollsuite des unveränderten Codepatches: **11.277 bestanden, 96 Skips,
  111 Untertests bestanden**. Beide disjunkten JUnit-Berichte stehen unter
  `output/playwright/customer-final-a-20260928.xml` und `customer-final-b-20260928.xml`.
  Keine erneute Vollsuite nur wegen dieser Dokumentationsänderung nötig.
- Fußball-Fünfer-/Zehnerbilanzen aus bereits geladener Historie, je Team echte
  Gegner/Ergebnisse aufklappbar; Wettfinder, Daily3, manuelle Suche und RisikoBet
  verbunden. Tennis und die vorhandenen weiteren Sportadapter sind im Code
  enthalten. Kurzform nicht als erfundenen Grund für die gewählte Seite verkaufen.
- App/Caddy jetzt aktiv, öffentlicher Healthcheck `ok`; letzter Tennisdienst
  `Result=success`, Exit 0. Tagesbackup weiterhin deaktiviert. Keine neue Sicherung,
  zusätzliche Sportabfrage oder Speicherbereinigung für diese Übergabe.
- UI-Nachweis im Bericht: interne Browserprüfung, lokale 1280-/390-/320-px-Karten,
  Live-Spielblock per Tastatur auf/zu. Mausbedienung des nativen Streamlit-
  Expanders und echte Mobilgeräte nicht als erfolgreich getestet behaupten.

### Offen – nächste konkrete Arbeiten

1. **Kontextwirkung fertig verbinden:** produktive Fußball-Vergleichs-Snapshots
   mit vollständigem Quellen-Replay an den vorhandenen gemeinsamen Trainings-/
   Auswertungs-/Aktivierungspfad anschließen; bestehende freigegebene Spezifikation
   und Pläne weiterverwenden, keinen neuen Modellneubau beginnen.
2. **Echte Daten und Wirkungsprüfung:** Verletzungen, Wetter und Müdigkeit sind
   weiterhin nicht vollständig numerisch belegt oder aktiviert. Bestandsprüfung
   vom 28.09.: 72 ATP-/289 WTA-Endresultat-Ereignisse, keine nutzbaren akuten
   Verletzungsmerkmale oder gemessenen Matchdauern; nur zwei vollständige WTA-
   Drei-Tage-Satzpaare. Fußball: vier vollständig quellgebundene Originale,
   neun Wetterantworten. 250 WTA-Erholungsuntergrenzen sind eine mögliche eng
   abgegrenzte Studie, keine bestätigten Fitnesswerte. Tours/Kohorten nicht
   zusammenzählen; mindestens 200 unabhängige Testevents zusätzlich zu Training/
   Abstimmung und drei Zeitblöcke bleiben Voraussetzung. Erst den vorhandenen
   Vollbestandsbericht nutzen, nicht dieselbe teure Inventur nochmals wiederholen.
3. **Veröffentlichte Formkarten nachprüfen:** beim nächsten regulären Modelllauf
   kontrollieren, ob neue Fußball-5/10-Fakten wirklich gespeichert und gerendert
   werden. Alte Karten nicht mit späteren Ergebnissen anreichern; keinen extra
   API-/Sportscan nur für diese Prüfung starten. Basketball-/Hockey-/E-Sport-
   Produktionsbelege und verbleibende Daily3-Sportvergleiche separat nachweisen.
4. **UI-Restprüfung:** native Mausbedienung der Spielgruppen und echte Mobilgeräte
   prüfen. Lokale Darstellungstests nicht als Geräte-/Storefreigabe melden.
5. **Kundenbetrieb bleibt separat offen:** DE/EN-Portalcode vorhanden, Paywall
   nicht aktiv; echte Stripe-/SMTP-/Kauf-/Kündigungs- und Mehrkontentests sowie
   rechtliche/Domainangaben fehlen. Native iOS-/Android-Apps und Storeeinreichung
   fehlen. Bestätigte Monatsabos: CHF 9.90 / 19.90 / 29.90; kein Händlerkonto
   oder Live-Verkauf ohne nötige Einrichtung/Freigaben aktivieren.

### Für die Fortsetzung beibehalten

- Repository `C:\Projekt\BetBoy\betboy-app`, `main`; SSH `betboy-vps`, Apprepo
  `/opt/betboy/app`. Test-Python `.codex_test_venv\Scripts\python.exe`.
- Kein neues Backup, zusätzlicher Sport-/API-Scan oder ungefragte Bereinigung.
  Cricket ausgenommen; internen Browser statt persönlichem Browser verwenden.
- Quote verändert weder Prognose noch Reihenfolge. Nur bekannte exakt passende
  gültige Quote unter 1,20 ausblenden, ohne Gegentipp nachzufüllen. Historische
  Prognosen, Wetten und Geldbuchungen unverändert; Daily3 CHF 50 ohne Nachschuss.
- Nur eigene, geprüfte Änderungen committen/pushen und ausdrücklich auf den VPS
  ziehen. Timer berechnen Daten, deployen keinen Code. Bekannte ungetrackte
  Audit-/Browser-/Output-Dateien und vorhandene Worktrees erhalten.
- Maßgebliche Belege: [Kundenbegründungen](docs/audits/2026-09-28-kundenbegruendungen.md),
  [Fußballform und vollständiger Kontextbestand](docs/audits/2026-09-28-fussball-form-kontextbestand.md),
  [Kontextanbindung](docs/audits/2026-09-27-kontexteffekte.md).

## 28.09.2026 – Fortsetzung: Fußballform und vollständiger Kontextbestand

- Fußball-Fünfer-/Zehnerlisten implementiert: kleine Anzeigeprojektion aus der
  bereits geladenen Modellhistorie, keine weitere Datenabfrage. Ergebnisse,
  Gegner, Heim/Gast und Wettbewerb je Team einzeln aufklappbar. Weniger als fünf
  oder zehn vorhandene Spiele werden nicht zu einer vollständigen Bilanz erklärt.
- Wettfinder/Daily3, manuelle Suche und RisikoBet erhalten dieselben exakt an
  Spiel, Teilnehmer, Termin und Berechnungszeit gebundenen Fakten. Bereits
  gespeicherte Prognosen werden nicht rückwirkend mit neueren Spielen ergänzt.
  Gleichnamige Teams werden in der normalen Karte nach Heim/Gast unterschieden.
- Keine Formdaten als neue Ranking-/Modellmerkmale; RisikoBet-Faktoren sind
  `DISPLAY_ONLY`. Quotenuntergrenze, Geldregeln und Cricket bleiben unverändert.
- 752 betroffene Tests und 85 Untertests sowie 120 abschließende Text-/Hash-/
  Installerprüfungen bestanden (überlappende Läufe). Unabhängiges Abschlussreview
  ohne offenen Befund. Die erste unveränderte Vollsuite fand zwei Altformat-
  Abstürze der manuellen Zusatzstatistik (11.272 bestanden, 96 Skips, 111 Untertests).
  Fehlende native Team-IDs oder Termine lassen nun nur diese Zusatzstatistik
  aus; die Karte bleibt erhalten. Fünf Fälle vorher rot, danach 115 betroffene
  Tests bestanden. Die erneute Vollsuite ist grün: 11.277 bestanden, 96 Skips,
  111 Untertests bestanden. Alle 11.373 gesammelten Tests in zwei disjunkten
  Gruppen erfasst; 15 Produkt-/Testdateien währenddessen per SHA-256 unverändert.
  Codecommit `42054e35d8ce855ef80c6c74cc9bdccb8467e451` auf `main` gepusht und
  per geprüftem Fast-forward auf dem VPS deployed. App/Caddy aktiv, beide
  Healthchecks `ok`; kein Serverbackup und kein zusätzlicher Sport-/API-Scan.
  Die folgende Dokumentationsfortschreibung ändert den getesteten Code nicht.
- Live-Seite frisch geladen: richtige URL/Titel, vollständiger Wettfinder,
  kein Fehleroverlay und keine neuen Konsolenfehler nach dem Neustart. Spielblock
  Georgia/Ukraine per Tastatur geöffnet und geschlossen. Neue Fußball-5/10-
  Listen entstehen beim nächsten regulären Modelllauf; heutige alte Karten
  behalten ihre originalen Belege. Mausbedienung der nativen Streamlit-Expander
  im internen Browser nicht zuverlässig bestätigt; lokale Kartenbedienung und
  responsive Darstellung separat geprüft, keine Behauptung echter Gerätetests.
- Reale Tennis-Vollbestandsprüfung: 72 ATP- und 289 WTA-Ereignisse mit passend
  gebundenem Endergebnis. Kein ATP-Fall mit gemessener Dauer; WTA nur zwei Fälle
  mit vollständiger beidseitiger Drei-Tage-Satzabdeckung. Keine nutzbare akute
  Verletzungswirkung. 250 WTA-Fälle haben eine beobachtungsgebundene Erholungs-
  untergrenze; daraus weder vollständige Fitness noch einen geprüften Effekt
  ableiten. ATP/WTA nicht zusammenzählen, um die Abnahmegrenze zu erreichen.
- Fußball: 26 verschiedene native Ereignisse, vier vollständig quellgebundene
  Originale; neun tatsächlich gespeicherte Wetterantworten. Keine freigegebenen
  Effekt-/Experimentartefakte. Der vollständige numerische Wirkungsnachweis und
  verbleibende Trainings-/Aktivierungsanbindungen bleiben offen.
- [Prüfbericht, Datenzahlen und Abnahmegrenzen](docs/audits/2026-09-28-fussball-form-kontextbestand.md).

## 28.09.2026 – Auswahlbegründung und echte Fünfer-/Zehnerbilanzen

- Tennis: tatsächlichen längerfristigen Vergleich und gegebenenfalls verwendete
  Aufschlag-/Rückschlagkomponente erklären, nicht eine kleine Ergebnisbilanz als
  angebliche Begründung einsetzen. Bessere gegnerische Kurzform ist Gegenargument;
  die letzten fünf und zehn erfassten Belagsspiele werden getrennt gezeigt.
- Bereits vorhandene ATP-/WTA-Trainingsdateien rein lesend nutzen, keine
  zusätzlichen Sport-/API-Abfragen. Maximal zehn kleine Ergebniszeilen pro
  Spieler, höchstens 365 Tage; keine neuen Trainings-/Prognosekopien. Gegner und
  Ergebnis aufklappbar, historische Weltranglistenplätze nur wenn tatsächlich
  vorhanden. ATP bleibt ausdrücklich Turnierdatum, nicht exakter Spieltag.
- Cache muss vor der Prognose bestanden haben. Keine Anreicherung alter Karten
  mit später geladenen Ergebnissen, keine Änderung historischer Prognosen.
  Umfang der Cache-Bilanz: abgeschlossene K.-o.-Runden inklusive Qualifikation;
  ungeordnetes Round-Robin wird nicht als erfundene jüngste Reihenfolge gezeigt.
- Fußball: markt- und seitenrichtige Tor-/Zählprognose plus konkretes
  Gegenargument. Die gespeicherten Formspielzahlen sind keine S/U/N-Bilanzen;
  fehlende Gegnerlisten werden nicht erfunden. Für vollständige Fußball-5/10-
  Listen fehlt weiterhin eine gespeicherte historische Detailprojektion.
- Basketball/Eishockey: echte zuletzt konsumierte Ergebnisse in bestehenden
  reinen Anzeigefaktoren; Gegenargument bei besserer gegnerischer Kurzform.
  Hockey-Endstände inklusive Verlängerung/Penaltyschießen bleiben von den
  erwarteten Toren der regulären Spielzeit getrennt. E-Sport: echte zuletzt
  konsumierte fünf/zehn Serien, keine aus IDs erfundene Gegnerstärke.
- Gemeinsame Karten (Wettfinder/Daily3), Tennis und RisikoBet angeschlossen.
  Alte RisikoBet-Elo-Zahlen am öffentlichen Formatter bereinigt. Neue Adapter-
  Darstellungen getrennt versioniert, historische Inhalte nicht überschreiben.
- Cricket, Modellwahrscheinlichkeiten, Auswahlreihenfolge, Quote und Geldregeln
  bleiben unverändert. Keine neue Verletzungs-/Müdigkeitsfreigabe oder behauptete
  bessere Wettqualität. Kundenportal/Paywall weiterhin nicht aktiviert.
- Veröffentlicht: Code-Commits `e7d2205` und `00ef419` auf `main` gepusht und
  auf dem VPS per Fast-forward gezogen, ohne neue Sicherung oder zusätzlichen
  Sport-/API-Scan. App aktiv; interner und öffentlicher Healthcheck `ok`.
- **356 betroffene Tests, 26 Untertests bestanden**; unabhängige Reviews des
  Anzeigen- und abschließenden Cache-Diffs ohne offene Befunde. Die zusätzliche
  Vollsuite wurde nach rund 32 Minuten unterbrochen; kein Vollsuite-PASS behauptet.
- Live Rublev/Jacquet: Rublev 3/5 und 4/10, Jacquet 4/5 und 6/10 echte erfasste
  Hartplatzsiege. Längerfristiger Vergleich als Begründung, bessere gegnerische
  Kurzform als Gegenargument; Gegner und Ergebnisse aufklappbar.
- Wiederholte Statistikabfragen auf dem VPS: vorher 0,353 s, jetzt 0,0003–0,0005 s;
  einmaliger Tagesindex im Arbeitsspeicher, keine zusätzliche Datenbankhistorie.
  Desktop und 390×844 Mobil geprüft; kein horizontaler Überlauf.
- Bereits gespeicherte RisikoBet-Anzeigefaktoren bleiben historisch unverändert;
  die neuen Fünfer-/Zehnerfakten entstehen dort beim nächsten regulären Lauf.
  Basket-/Hockey-Anbindungen sind regressionsgeprüft, mangels heutiger Karten
  nicht als echte aktuelle Produktionsspiele bestätigt.
- [Audit und Abnahmegrenzen](docs/audits/2026-09-28-kundenbegruendungen.md).

## 27.09.2026 – Mindestquote bei Vorschlägen wiederhergestellt

- Die Ausnahme **bekannte exakt passende Quote unter 1,20 ausblenden** gilt
  wieder für Wettfinder, Daily3, manuelle Fußballsuche, RisikoBet und den aktiven
  15K-Modellpfad. Genau 1,20 bleibt zulässig. Kein pauschales Wettartenverbot,
  keine Änderung der berechneten Wahrscheinlichkeiten oder Modellreihenfolge.
- Erst widerspruchsfreie Modellauswahl, dann Preisuntergrenze, dann Plätze:
  Eine ausgeblendete Auswahl darf nicht durch ihren Gegentipp ersetzt werden.
  Fehlende, fremde oder außerhalb der bestehenden Gültigkeit liegende Quoten
  bleiben unbekannt. Modellchance/Torprognose sind keine Buchmacherquote.
- Bereits gespeicherte, identitäts- und zeitgebundene Quoten werden wieder
  gelesen; kein Quotenrefresh, zusätzlicher API-/Sportscan oder neue Sicherung.
  Wo keine verwendbare Quote gespeichert ist, kann der Filter nichts erkennen.
- Fußballkarten zeigen z. B. **Azerbaijan: 1,12 erwartete Tore**; die Torzahl
  wird nicht mehr als freistehende Dezimalzahl hinter „Torprognose“ dargestellt.
- Nur Auswahl-/Anzeigekorrektur. Historische Wetten, Einsätze und Auszahlungen
  bleiben unverändert; kein neuer Verletzungs-/Müdigkeits- oder Qualitätsnachweis.
- Integrationsfund: Daily3 verlangte nach dem Entfernen pauschaler Tennis-
  Warntexte weiterhin einen nichtleeren Warnsatz beim Speichern. Ein leerer
  Hinweistext ist jetzt zulässig; fehlende/falsch typisierte Felder und andere
  Buchungsprüfungen bleiben strikt. Keine Fülltexte, Migration oder Altumschreibung.
- Verifiziert: **1.141 Tests und 58 Untertests** in 24 betroffenen Testdateien.
  Kein vollständiger 11k-Lauf. Veröffentlichung per bestehendem Code-only-Pull;
  VPS-Hash, Healthchecks und gerenderte Torbeschriftung separat prüfen.

## 27.09.2026 – Kontext-Einschränkungen nur in aufklappbaren Details

- Methodische Standardhinweise zu Verletzungen/Kader/Belastung stehen nicht
  mehr als eigene Warnzeile auf jeder Karte. Die konkrete Einschränkung bleibt
  unter „Statistik & Details“; kein zusätzlicher pauschaler Satz ohne Beleg.
- Auch alte Kartenobjekte mit den früheren Kurztexten folgen beim Rendern
  dieser Regel. Gespeicherte Daily3-Wetten zeigen ihre damalige Einschränkung
  ebenfalls aufklappbar; historische Prognosen/Geldbuchungen bleiben unverändert.
- Echte Aktualitäts-/Datenprobleme und Ausfallzahlen bleiben sichtbar. Keine
  neue Effektfreigabe, Modelländerung, API-Abfrage oder Sicherung.

## 27.09.2026 – verständliche Tennis-Statistik statt Modelljargon

- Kundenansicht in Wettfinder/Daily3, Tennis und RisikoBet: keine Belag-Elo-
  Erläuterung, kein Trainingsstichtag/Modellaufbau und kein langer Standardabsatz
  über numerisch nicht belegte Vorteile. Der gemeinsame Detailknopf heißt
  **„Statistik & Details“**. Sportdatenstand und Berechnungszeit bleiben getrennt;
  ein Turnierstart wird nicht als Datum des letzten Matches ausgegeben.
- Der reguläre Tennislauf speichert kleine Ergebnisbilanzen für beide Spieler:
  höchstens zehn erfasste Spiele der letzten 90 Tage, bevorzugt auf dem Belag.
  Der Kunde sieht z. B. `7/10 Siege`; Zeitraum/Stichprobe stehen bei den Details.
  Fehlende Belagergebnisse werden ausdrücklich als „alle Beläge“ bezeichnet.
- Keine aus Elo abgeleiteten Siegesserien: ohne gespeicherte Bilanz nur die
  belegte Spielzahl. Keine pauschale „ungeschlagen“-Behauptung. Doppelte,
  widersprüchliche, abgebrochene und nach der Prognose bekannte Ergebnisse
  werden nicht als Siege gezählt. ATP und WTA bleiben getrennt.
- Bestehende Prognosen werden **nicht rückwirkend mit späteren Ergebnissen
  angereichert**. Neue Bilanzen entstehen erst beim regulären Lauf aus den
  ohnehin geladenen Ergebnissen. Keine neue API-Abfrage/Datenbankmigration.
- Modellkern/Quoten/Einsatzlogik unverändert. Der erste Integrationsversuch
  berührte den versiegelten Modellcode; die Replaytests erkannten dies. Er wurde
  verworfen und die Erfassung in den nachgelagerten Speicherablauf verschoben.
- Verifiziert: **508 Tests** einschließlich historischer Tennis-Replays;
  zusätzlich **148 Karten-/Integrationsprüfungen und 26 Untertests** (teilweise
  überlappend). Kein vollständiger 11k-Lauf, kein neuer Sportscan/Backup.
- Diese Textarbeit belegt weder bessere Wettqualität noch neue Verletzungs-,
  Wetter- oder Müdigkeitseffekte. Die offenen Modellarbeiten bleiben offen.
- Veröffentlichung ist ein Code-only-Pull; Kundenportal/Paywall bleiben
  deaktiviert, native Apps und Zahlungsanbieter werden nicht live geschaltet.

## 27.09.2026 – Kundenportal, Abos und englische Landingpage

- Nutzer hat **Starter CHF 9.90 / Plus CHF 19.90 / Pro CHF 29.90 monatlich**
  bestätigt und Stripe gewählt. Internationaler Vertrieb und eine englische
  Website sind gewünscht; ein Stripe-Händlerkonto besteht noch nicht.
- Neu implementiert: deutsche/englische responsive Landingpage, Preisübersicht,
  Registrierung mit E-Mail-Bestätigung, Login, Passwort-Reset, Kundenbereich und
  Stripe-Checkout-/Webhook-Code. Eine Zahlungsrückkehr allein gibt keine Rechte.
- Separate kleine Kundendatenbank. Optionaler serverseitiger Streamlit-Zugang
  samt Funktionsrechten; alte browserlokale Wettkonten werden nicht übernommen.
  Logout/anderes Konto/Aboablauf dürfen keine alten Daily3-Callbacks weiter nutzen.
- Lokal: **28 Portaltests plus 300 Bestands-/Integrationstests und 32 Untertests**
  bestanden. Stripe-Antworten sind simuliert (einschließlich echter SDK-Typen),
  kein echter Zahlungs- oder E-Mail-Zustellnachweis. Kein kompletter 11k-Testlauf.
- Browser: DE/EN-Landingpage, Abo-Auswahl, Registrierung, Sprachwechsel und
  Formularvalidierung im internen Browser geprüft; 320-/390-px-Ansichten ohne
  horizontalen Überlauf. Lokale Vorschau: `http://127.0.0.1:8010/de/`.
- **Nicht live geschaltet:** neuer Kundenbetrieb/Paywall, Stripe, E-Mail-Versand,
  Domain-/Proxy-Umstellung. VPS rein lesend geprüft: bisheriger Stand `5251c00`,
  App aktiv, interner Healthcheck `ok`. Keine neue Sicherung und kein Sportscan.
- **Native iOS-/Android-Apps sind noch nicht implementiert.** Responsive Webansicht
  nicht als native App oder Store-Release melden. Gemeinsame Konten sind vorgesehen;
  Store-Verifikation, native Projekte, Geräte-/Storetests und Einreichung fehlen.
- Vor Verkauf: Nutzer-Domain und öffentlicher Anbietername (asynchron gefragt),
  SMTP, rechtliche Texte/Vertriebsländer/Steuern und Stripe-Aktivierung; echte
  Sandbox-Kauf-/Kündigungsnachweise, Abgleich verpasster Zahlungsereignisse sowie
  veröffentlichte Mehrkonten-/Zugriffsprüfung. Keine allgemeinen Store-Zusagen.
- [Bestätigte Spezifikation](docs/specs/2026-09-27-kundenportal.md) und
  [Start-/Test-/Cutover-Anleitung](portal/README.md) enthalten die Liefergrenzen.
  Die bisherigen Modell-/Kontextrestarbeiten darunter bleiben offen.

## 27.09.2026 – Fortsetzung: gemeinsames Fußballmodell an Training und Auswertung angeschlossen

- Die kalibrierte gemeinsame Torverteilung kann jetzt aus gespeicherten,
  quellgebundenen Originalen in den **bestehenden** Trainings-/Auswertungspfad
  überführt werden. Kein zweites Datensystem, keine duplizierten Originalpakete.
- Gekoppeltes Training, getrennte Abstimmung und spätere Testspiele verwenden
  dieselbe Verteilung; der CPU-Worker kann denselben Vergleich berechnen.
  Ohne belegte Effektfreigabe bleibt seine verwendete Prognose das Original.
- Später empfangenes Wetter benötigt einen späteren Vor-Spiel-Vergleich;
  Originalmodell und tatsächliche Empfangszeit bleiben erhalten. Fehlende
  Merkmale werden nicht mit null oder „gesund“ ersetzt. Spielabstände sind
  ausdrücklich nur Terminabstände, keine gemessene körperliche Erholung.
- Rein lesende VPS-Probe: Zwei vollständige Quellenbindungen ausgewertet.
  Jeweils drei Terminabstandsmerkmale verfügbar, zwölf Kadermerkmale und sechs
  Wettermerkmale fehlend. Dritte Probe durch das gesetzte Zeitbudget beendet.
  Keine Vollbestandsaussage und kein belegter Verletzungs-/Wettereinfluss.
- **Weiter offen:** produktiver Anschluss neuer Vergleichs-Snapshots samt
  vollständigem Quellen-Replay, ausreichende echte Trainings-/Testfälle sowie
  deren empirische Prüfung. Tennis und die anderen Sportarten dadurch nicht
  als fertig melden. Keine Live-Effektaktivierung, kein zusätzlicher API-Scan,
  keine neue Sicherung und keine Datenbankmigration.
- Einzelheiten und Test-/Veröffentlichungsgrenzen stehen im bestehenden
  [Kontextbericht](docs/audits/2026-09-27-kontexteffekte.md#fortsetzung-quellgebundenes-training-am-2709).

## 27.09.2026 – konkrete Kontextlücken repariert; Wirkungsnachweis bleibt offen

- Tatsächliche Wetterantworten werden nun im vorhandenen Fußballworker mit
  originaler Empfangszeit gespeichert. Keine zusätzlichen API-Anfragen, keine
  neue Sicherung. Stadtprognose bleibt von exaktem Stadionwetter getrennt.
- Neuer numerischer Fußball-Kontextpfad erhält die aktive kalibrierte gemeinsame
  Torverteilung. Nulleffekt ist exakt identisch; alle Torwetten werden konsistent
  berechnet. Gekoppelte Likelihood statt Wiederverwendung alter Poisson-Fits.
  Fünf echte gespeicherte Originale auf dem VPS exakt numerisch reproduziert.
- **Nicht abgeschlossen:** Dieser Rechenweg ist noch kein vollständig
  quellgebundener Trainings-/Aktivierungspfad. Keine numerischen Verletzungs-,
  Wetter- oder Müdigkeitseffekte als empirisch belegt oder live aktiviert melden.
- Frische Bestandsprüfung: 64 ATP- und 282 WTA-Spiele mit passendem Ergebnis;
  nur 3 von 45 Fußballpaketen vollständig quellgebunden, bislang 0 Wetterbelege.
  Zwölf untersuchte Tennisfälle ohne nutzbare Minutendifferenzen. Keine Aussage
  über den gesamten WTA-Merkmalsbestand aus dieser kleinen Stichprobe ableiten.
- [Belege, Änderungen und konkrete Restarbeiten](docs/audits/2026-09-27-kontexteffekte.md).
  Die nächste Tennis-Dienstnachprüfung ersetzt diese fachliche Arbeit nicht.

## 27.09.2026 – 15K-Modellauswahl ohne Aufstellungs-Pflicht

- Der heutige gespeicherte Fußballlauf fand und modellierte 14 Spiele. Alle
  114 Kontextkandidaten hatten noch keine bestätigten Startaufstellungen;
  die bisherige 15K-Freigabebedingung machte daraus trotz vorhandener
  Modellwerte 0 Auswahlen. Eine fehlende Quote war nicht der Grund.
- Der neue 15K-Modellpfad verlangt weiterhin die bestehende statistische
  Marktvalidierung, den 15K-Wahrscheinlichkeitskorridor und kein bekanntes
  Kontextveto. Fehlende Startaufstellungen, Wetter- oder Ausfallabdeckung
  sperren die Modellauswahl nicht mehr. Die Prognose wird nicht wegen einer
  Buchmacherquote geändert oder sortiert; tatsächliche Quoten werden erst
  beim Erfassen der gespielten Wette benötigt. Automatische Preis-/Release-
  und andere Wettfinder-Verträge bleiben unverändert.
- Produktionsnachweis: Code-Commit `12614bf` ist auf GitHub `main` und dem
  VPS identisch; App und sechs Rechentimer sind aktiv, interner Healthcheck
  `ok`. Die Vollsuite ergab 11.066 bestandene Tests, 96 erwartete Skips und
  111 bestandene Untertests. Der bereits gespeicherte Tagesstand enthält
  zwei nach den 15K-Modellregeln zulässige Märkte für **dasselbe** Spiel;
  nach Spiel-Deduplikation ist genau eine aktuelle 15K-Auswahl sichtbar.
  Kein neuer Sportscan und keine neue Sicherung.
- Nicht behaupten, dass fehlende Kontextdaten numerisch eingerechnet oder
  eine höhere Trefferquote nachgewiesen wurden. Der nächste reguläre Lauf
  muss die Veröffentlichung neuer Tagesdaten weiterhin separat bestätigen.

## 27.09.2026 – täglicher Tennis-Scan und Ergebnislücken

- Der planmäßige Lauf um 00:05 CEST nutzte `ed27f7a`, bereitete 15
  Prognosen vor und speicherte 11 neu. Der zuvor behobene WTA-Paarungswechsel
  183992 blieb korrekt ohne fremdes Ergebnis; eine neue fehlende
  Satz-/Belastungsangabe für WTA 186197 hat keine zugehörige rechtzeitige
  ursprüngliche Prognose und wurde als Datenlücke ausgewiesen.
- Trotzdem endete der Lauf um 00:22 mit Exit 1: mindestens ein anderer
  vorhandener Originalbeleg konnte keinem belastbaren nativen Siegerbeleg
  zugeordnet werden. Das ist **kein** erfolgreicher Produktionslauf. Die
  bisherigen Logs nannten nur `native-outcome-unavailable`, nicht die
  konkrete Event-ID. Alte Prognosen und Geldbuchungen wurden nicht umgeschrieben.
- Die zweite Korrektur führt die unaufgelösten Event-IDs getrennt im
  Admin-Bericht. Fehlende Sieger bleiben ausdrücklich unbelegt und werden
  nicht abgerechnet; solche Datenlücken allein machen den gesamten Tageslauf
  nicht mehr zu einem technischen Fehlstatus. Konkurrierende native Antworten,
  widersprüchliche Ersatzrevisionen, Speicherintegritätsfehler und echte
  Modell-/Publikationsfehler bleiben hart fehlerhaft. Bei Modellfehlern werden
  künftig Event-ID, Grund und Fehlertyp im Dienstlog angezeigt.
- Die zweite Korrektur wurde als `d2a76e1` auf GitHub und den VPS gebracht;
  lokal, GitHub `main` und VPS waren nach dem Code-only-Deploy identisch.
  11.063 Tests und 111 Untertests bestanden, 96 Tests wurden übersprungen;
  App, Timer und beide Healthchecks meldeten `ok`. Kein zusätzlicher API-Lauf,
  keine neue Sicherung und keine Datenbankmigration am 27.09.
- Der reale Nachweis dieser zweiten Korrektur steht erst mit dem regulären
  Lauf am 28.09. um 00:05 CEST an. Eine Nachprüfung ist für 02:00 CEST in
  diesem Chat eingeplant; sie darf keinen zusätzlichen Sportscan starten.
- Die fehlenden unabhängigen Outcome-/Kontextbelege verhindern weiterhin
  eine Freigabe numerischer Verletzungs-, Wetter- oder Müdigkeitseffekte sowie
  eine Behauptung besserer Wettqualität.

## 26.09.2026 – Tennis-Tageslauf, belegter Status und verbleibende Abnahme

- Der Stand `7a75ab3` war lokal, auf GitHub und auf dem VPS identisch, aber der
  automatische Tennis-Lauf vom 26.09. endete trotzdem mit Exit 1. Vorhandene
  Beobachtungen und Prognosen wurden gespeichert; die Capture-Diagnose meldete
  `native-outcome-unavailable` und `terminal-workload-unavailable`.
- Die erste Meldung betrifft WTA 183992: vor dem Beginn wurde eine neue
  Spielerpaarung erfasst. Die vor dem Beginn publizierten alten Prognosen
  dürfen **kein** Ergebnis dieser Ersatzpaarung bekommen. Der Collector
  erkennt diese nachgewiesene Ersetzung nun auch bei mehrfachen Finalmeldungen
  ohne eindeutige Sieger-Flags als sichtbare Nichtauswertbarkeit, statt den
  gesamten Lauf abzubrechen. Unbelegte Paarungswechsel bleiben Fehler.
- Bei WTA 184101 fehlten Satz-/Belastungsdaten, aber es existiert keine
  zugehörige ursprüngliche Tennis-Prognose. Der Statusbeleg bleibt mit seiner
  Datenlücke gespeichert; die Lücke wird gesondert gemeldet. Liegt eine
  ursprüngliche Prognose vor, bleibt ein fehlendes Ergebnis ein Lauf-Fehler.
- Die Korrektur wurde als `ed27f7a` auf GitHub und den VPS gebracht;
  11.060 Tests, 111 Untertests und die gespeicherten Problemfälle wurden
  geprüft. Der nächste automatische Lauf am 27.09. blieb dennoch aus einem
  anderen Ergebnisdaten-Grund fehlerhaft (siehe oben). Kein zusätzlicher
  API-Scan und keine neue Sicherung für die Prüfung.
- Weiterhin offen: empirisch belegte Verletzungs-, Wetter- und
  Belastungseffekte, sportartenübergreifende Daily3-Qualitätsvergleiche und
  ein unabhängiger Nachweis besserer Wettqualität. Softwaretests allein
  belegen keinen Wettvorteil.

## 24.09.2026 – Tagesmodell versus kurzlebige Ausführungsquote

- Der tägliche automatische Modell-Snapshot ist für Auswahlen bis zu 24 Stunden
  lesbar. Für ein bevorstehendes Spiel am aktuellen Zürcher Spieltag kann die
  Modell-Highlightprüfung denselben Tagesstand verwenden. Modellzeit und
  fehlende kurzfristige Kader-/Aufstellungsdaten bleiben sichtbar.
- 15K-Modellauswahlen werden ebenfalls aus dem aktuellen Tagesmodell ohne
  Buchmacherquote angezeigt. Erst beim Erfassen einer realen Wette werden
  Buchmacher, exakte Einzelquoten und Einsatz eingegeben; diese Angaben sind
  als Nutzereingabe markiert und keine unabhängig bestätigte Anbieterquote.
  Die bestehende Ticket-/Einsatzrechnung und authentisierte Buchung bleiben.
- Tagesbestand 24.09., 17:24 CEST: 40 Nationalteam-Modellkandidaten, 15 über
  70 Prozent, aber kein gespeicherter Same-Match-Formvergleich für Daily3.
  Der Nationalteam-Vergleich wird nun aus dem bereits geladenen, markierten
  A-Länderspielpool der letzten 730 Tage aufgebaut. Club- und U23-Daten,
  ältere Resultate und abweichende Spiel-/Markt-/Modellbelege qualifizieren
  nicht. Wettfinder und Daily3 können damit einen echten Formvergleich
  verwenden; die 2-Prozentpunkte-Regel bleibt. Wie viele heutige Auswahlen
  sie erfüllen, muss der nächste echte Scan zeigen. Die gepoolte Prüfung ist
  weiterhin kein eigener Nations-League-Qualitätsnachweis.

## 24.09.2026 – Tippfindung ohne Buchmacherpreise

- Wettfinder (automatisch und eigene Suche), RisikoBet, Daily3 und aktive
  Sportansichten sollen Prognosen ausschließlich nach Modell- und Datenlage
  auswählen. Fehlende, veraltete oder niedrige Buchmacherquoten ändern weder
  Sichtbarkeit noch Reihenfolge; Preisbestätigung und Value-Grenze verschwinden
  aus diesen Tippkarten.
- Die feste Nutzer-Mindestquote 1,20 bleibt für eine tatsächlich erfasste
  Daily3-Wette bestehen. Historische Echtgeldquoten und Auszahlungen werden
  nicht verändert.
- 15K ist ebenfalls quotenfrei in der Tippfindung. Die tatsächliche Quote wird
  dort erst beim Speichern eines gespielten Tickets benötigt, weil Auszahlung
  und Risiko sonst nicht berechnet werden können. Alte Ticketbelege bleiben lesbar.
- Der produktive Tageslauf fragt dafür keine Fußball-Buchmacherquoten mehr ab.
  Explizit injizierte Quotenloader bleiben nur für historische Replay-Tests;
  sie ändern die Modellliste nicht.
- Alte E-Sport-/Teamsport-Preis-Caches werden vom normalen Prognoseleser nicht
  mehr geladen; deren automatischer Quotenrefresh ist deaktiviert. Historische
  Preisadapter bleiben für bestehende Daten und separate Prüffunktionen erhalten.
- Code-, GitHub- und VPS-Stand bei einer Übergabe getrennt anhand der Hashes
  prüfen; ein grüner Test allein belegt kein Deployment oder bessere Treffer.

## 24.09.2026 – Wettentscheidung liegt beim Nutzer

- Wettfinder, eigene Suche, Daily3 und Sportansichten bezeichnen Modell- und
  Quotenstatus als Informationen, nicht als Erlaubnis zum Wetten. Eine fehlende
  oder niedrige Quote verändert die Prognose nicht und blendet sie nicht aus.
- Interne Kriterien für optionale Einsatzvorschläge und die bestehende
  TipStore-Speicherung bleiben unverändert. Das ist eine Funktionsgrenze der
  App, keine Entscheidung über extern platzierte Wetten.
- Keine Modellwahrscheinlichkeiten, Preisgrenzen oder CHF-50-Budgetregeln
  geändert.

## 24.09.2026 – Wetter, Form, Ausfälle und Tennis-Belag

- Tennis: Das bestehende Elo nutzt bei mindestens acht Belagspielen **je Spieler**
  den Belaganteil (65 %) plus Gesamt-Elo (35 %). Der Tageslauf speichert jetzt
  beide tatsächlichen Belag-Elo-Werte, Stichproben und den Datenstand neben
  der unveränderten Prognose. Wettfinder/Daily3, Tennis und RisikoBet zeigen
  den Beleg kompakt; bei zu kleiner Stichprobe steht ausdrücklich
  „Gesamt-Elo verwendet“. Alte Prognosen erhalten keine nacherfundenen Werte.
  Historische Replay-Quellen tennis/predict.py und tennis/elo.py bleiben
  unverändert; 680 betroffene Integrations-/Replaytests bestanden, danach
  113 Speicher-/Anzeige-/Adaptertests nach der letzten Eingabegrenze.
- Fußball-Form wirkt schon als 25-%-Anteil der erwarteten Tore; Tennis
  verarbeitet jüngste Ergebnisse chronologisch im Elo, E-Sport jüngste
  Serien im Elo. Keine zusätzliche willkürliche Formkorrektur.
- Ausfälle/Wetter: Der Fußball-Kontext zeigt verifizierte Daten und kann
  extreme Gegenindikatoren prüfen, ändert aber die Modellchance **nicht**
  numerisch. Auch Tennis-Belastung/Verletzung ist kein freigegebener
  Wahrscheinlichkeitszu-/abschlag. Das ist in der UI als Grenze kenntlich.
- Produktionsinventur (rein lesend): 0 B1-Wetterbelege und 0 veröffentlichte
  Effektfreigaben. Vor numerischer Aktivierung fehlen echte, rechtzeitig
  erfasste Wetter-/Kaderbelege und eine unabhängige, zeitlich getrennte
  Qualitätsprüfung. Keine Wetterwirkung oder Gewinnverbesserung behaupten.
  Clay/Grass und WTA-Tipps bleiben von ihrer separaten Modellvalidierung
  abhängig; die Belag-Anzeige ist keine Freigabe.
- Keine neuen API-Läufe, Sicherungen, Datenbankmigrationen oder
  Quoten-/Wahrscheinlichkeitsänderungen für diesen Schritt.

## Form-Audit 23.09.2026

- Fußball, Tennis und E-Sport verwenden jüngste bekannte Ergebnisse bereits numerisch; keine zweite willkürliche Formkorrektur aufschlagen.
- Basketball: im produktiven Ergebnisspeicher aktuell keine verwertbaren Zeilen. Form erst mit kausaler Historie und unabhängigem Test.
- NHL: 1.535 gespeicherte Ergebnisse, davon nur 7 Spielstarts in den letzten 30 Tagen. Alte Saisonwerte nicht als aktuelle Form ausgeben; Forschungsversion erst bei ausreichender aktueller Stichprobe prüfen.
- Cricket: kein gespeicherter Ergebnisbestand; letzter Quellenversuch fehlgeschlagen. Keine Form erfinden.
- E-Sport: Die fünf zuletzt im Elo verwendeten Serien werden ab neuen Shadow-Einträgen zeitlich gebunden mitgespeichert und im RisikoBet offen angezeigt. Alte Einträge bleiben ohne nachträglich erfundene Form.
- Details: docs/audits/2026-09-23-sportarten-form.md. Betroffene Modell-/UI-Gruppen: 236 Tests bestanden; die lang laufende Vollsuite wurde nicht abgeschlossen. Kein Nachweis besserer Wettqualität.

## Fortsetzung 23.09.2026 – Code live, fachliche Abnahme offen

- GitHub `main` und VPS stehen auf `f5c0971c0bc3a09017b70b259f6b875efeeb149a`.
  Der VPS wurde ohne Datenmigration und ohne neues Backup-Archiv per
  Code-Fast-Forward aktualisiert. App/Caddy-Healthcheck `ok`, sieben
  Rechentimer aktiv, täglicher Backup-Timer weiter deaktiviert.
- Regression: vor einem fehlerhaften E-Sport-Test-Doppelgänger 6.999 Tests
  bestanden; nach Korrektur ausschließlich dieser Testdatei alle restlichen
  Module mit 4.061 bestandenen Tests abgeschlossen. Der echte E-Sport-
  Konstruktor war korrekt; zwei `__new__`-Tests brauchten `errors = {}`.
  Der reine Test-Fix gehört zu diesem Abschlussnachtrag.
- Automatischer Wettfinderlauf 01:37–01:44 CEST auf dem neuen Commit:
  `completed`, null technische Fehler. Die RisikoBet-ID-Wiederverwendung
  ist als Abdeckungsdiagnose sichtbar, 229 Kandidaten blieben offen und
  keine Wette wurde irrtümlich abgerechnet.
- Einmaliger regulärer Tennis-Tageslauf 01:44–02:01 CEST: Exit 0, Scan und
  Pipeline OK, 41 neue Prognosen. ESPN-WTA 183992 steht ausdrücklich als
  `partial`/nicht auswertbare alte Paarung, null technische Capture-Issues.
  Der Wettfinder-Timer wurde für den speicherintensiven Scan kurz angehalten,
  danach wieder aktiviert; die einmalige Rückfall-Sicherung ist entfernt.
  Der nächste automatische Wettfinderlauf um 02:07 CEST prüfte die inzwischen
  neu gespeicherten Tennis-Endergebnisse erfolgreich.
- Automatische Gegenprobe 02:07–02:13 CEST: `completed`, null technische
  Fehler, **29 andere RisikoBet-Kandidaten terminal abgerechnet**. Die neun
  Snapshots der wiederverwendeten Tennis-Event-ID haben weiterhin null
  terminale Abrechnungen. Der frühere Nullwert war vom Datenzeitpunkt
  abhängig, keine dauerhafte Blockade aller anderen Fälle.
- Rein lesende neue Tennis-Inventur nach dem Scan: 296 eindeutige rechtzeitige
  ORIGINAL-Events, davon 222 mit exakt passendem normalem Finale (+59 zum
  vorherigen Stand). Das sind 222 insgesamt, **nicht** 200 unangetastete
  Testspiele zusätzlich zu Training/Tuning. Effektfreigabe weiter offen.

- Maßgeblich: [Prüfbericht 22.09.](docs/audits/2026-09-22-kontext-daily3-status.md).
  Ausgangsstand lokal/GitHub/VPS `c784195`; App, Caddy und Timer aktiv,
  lokaler Healthcheck `ok`, rund 20 GB VPS-Speicher frei. Kein automatischer
  Code-Pull durch die Timer. Nutzerwunsch: keine neuen Tages- oder Updatearchive.
- Nach dem erfolgreichen Lauf vom 21.09. scheiterten am 22.09. der Tennis-
  Tagesdienst (74 verarbeitet, 13 neu gespeichert, Exit 1) und der Wettfinder
  (Fußball selbst fehlerfrei, Gesamt-Exit 1 wegen RisikoBet-Abrechnung).
- Tennis-Ursache: WTA 183992 wechselte nativ die Teilnehmer; eine neue
  Prognose erschien erst nach dem vorverlegten Beginn. Der veröffentlichte enge Fix
  klassifiziert nur eine exakt bestätigte Ersatzpaarung als sichtbare
  Nichtauswertbarkeit der alten Prognose. Kein fremdes Ergebnis, keine
  Geld- oder Settlementmutation. 300 gemeinsame Tennis-/Fußball-Regressionen
  bestanden; die produktive Nachprüfung läuft noch.
- RisikoBet: ESPN 183996 enthält alte und neue Spielerpaarung unter einer
  Event-ID. Der veröffentlichte Fix isoliert genau die nachweislich wiederverwendete
  Tennis-ID ereignisbezogen; beide Paarungen bleiben unabgerechnet, andere
  Spiele können weiterlaufen. Die Produktionsdaten bestätigen sieben alte
  und zwei neue Snapshots. 234 RisikoBet-Tests bestanden. Für eine sichere
  Abrechnung der neuen Paarung benötigen Ergebnisrouter **und Kandidaten-ID-/
  Terminal-Store-Vertrag** einen revisionsgebundenen
  Inkarnationsschlüssel und einen dauerhaft gebundenen Provider-Finalbeleg,
  bevor einzelne Szenarien dieser Event-ID gefahrlos abgerechnet werden.
  Im beobachteten alten Lauf: 227 fällige Kandidaten offen, null abgerechnet.
- Neuer reiner Fußball-ORIGINAL-v2-Settlementvergleich lokal getestet;
  weder Projektions-/Code-Replay noch empirische Wirkung freigegeben.
  Tennis vor dem neuen Scan: 163 eindeutig passende Finale bei 256
  rechtzeitigen Originalevents; aktueller Stand oben. WTA
  historisch negativ; Basketball/Eishockey/E-Sport ohne qualifizierte
  Same-Market-Variante für Daily3. Cricket bleibt ausgenommen.
- **Noch nicht behaupten:** erfolgreicher neuer Tennis-Gesamtlauf,
  abgeschlossene RisikoBet-Inkarnationsabrechnung oder belegte bessere
  Wettqualität. Diese Punkte erst nach gesondertem Nachweis abhaken.

## Kontext-/Daily3-Fortsetzung 21.09.2026 — 3201537 live, fachliche Abnahme offen

- Maßgeblich: [Kontext-/Daily3-Bericht](docs/audits/2026-09-21-kontext-daily3-fortsetzung.md).
- Der unten noch offene 11:37-Lauf ist erfolgreich beendet. Neue RisikoBet-
  Begründungen sind veröffentlicht, keine technische Störung dieses Laufs.
- ATP-Daily3-Vergleich aus dem tatsächlichen Modellstand implementiert;
  vollständiger Speicher-/Signalanschluss getestet, keine Preissteuerung.
- Tennis-v4: korrekt begrenzte Belastungsfenster, stabile Erholungs-Untergrenzen,
  kompakte vollständig revisionsgebundene Spielersnapshots. Kein Effekt
  automatisch aktiviert; alte v3-Snapshots bleiben unverändert reproduzierbar.
- Erste native Messung: 205 rechtzeitige unabhängige erste Originalevents, 125
  passende Endresultate vor jeglicher Train-/Tune-/Testtrennung. Null
  qualifizierte Effektartefakte. Sechs zeitlich verteilte Fälle weiterhin
  ohne vollständige Belastungsfenster; Mindestpausen messbar, nicht exakt.
- Abschlussregression: 2.585 bestanden, 15 erwartete Skips, 26 Untertests;
  zusätzlich 115 Fußballtests grün. Keine finale Vollsuite daraus behaupten.
- Fußball-Speicherbudget: vollständige unveränderte historische FT-Bündel
  werden mit alten Uhren wiederverwendet. Korrekturen bleiben eigene Belege;
  Folgeläufe können fehlende Quellen ergänzen, ohne Limits zu erhöhen.
- `c9363109c44d3560717353c624130574fc592d43` wurde auf main/GitHub/VPS
  veröffentlicht und ist im späteren Stand enthalten. Keine neue Sicherung,
  Bereinigung oder Datenmigration.
- Echte Tennisprüfung 13:51–14:08 CEST: Scan 951 Sekunden statt altem
  2100-Sekunden-Timeout; 82 gespeicherte v4-Revisionen, 16 ATP-Vergleiche.
  Exit dennoch 1: ESPN ersetzte bei WTA 183996 Julia Avdeeva durch Ayla Aksu.
  Alte Prognose nicht überschrieben. Generische unveränderliche Nachfolgelinie
  mit exakter Ergebnisbindung lokal fertig: 1.461 Tests bestanden, drei Skips;
  danach 92 überlappende UI-/Fixturetests grün. Die spätere Live-Abnahme ist
  unten mit dem tatsächlich erfolgreichen 15:05-Lauf dokumentiert.
- Regulärer Lauf 14:07–14:26 CEST: Fußball abgeschlossen, insgesamt degraded.
  Drei Tennis-Refreshfehler; zwei nativ belegte offene Teilnehmerplätze
  (IDs 1588/1573), 1562 beim späteren lesenden Bindungstest wieder gültig.
  Kein erfolgreicher Gesamtlauf oder erfundener Teilnehmer behaupten.
- Nachtrag `30f31ed1944c6c7e879fc30224377b9548a527ab` auf main/GitHub/VPS.
  Echter Tennislauf 14:50:33–15:05:20 CEST: Exit 0, Scan OK, Gesamt OK;
  86 fertig verarbeitete Prognosen. Neue WTA-Linie 1637 korrekt mit 1585
  verknüpft; ausschließlich Ayla Aksu/Yuki Naito aktiv. Altdaten unverändert.
- Zusätzlicher Anzeigeschutz: bekannte Rücknahmen, offene Teilnehmerplätze,
  Starts und geänderte Termine werden in Wettfinder/RisikoBet/Tennis gemeinsam
  geprüft. Historie und manuelle Abrechnung bleiben getrennt zugänglich.
  Finale 55 betroffene Module: 1.897 bestanden, drei Skips, 26 Untertests.
  Dieser Anzeigeschutz ist als `ebfb69d85b2ff1aa1660c0e860a7a840d1617488`
  auf main/GitHub/VPS. Native Leserprobe 15:22 CEST: 1585/1588/1573 nicht
  aktuell sichtbar, korrekte neue WTA-Linie 1637 vorhanden. Historie erhalten.
- Statusnachtrag `3201537565a50f15daa96f5a4d049b8ca708d4d3` auf main/GitHub/VPS:
  bestätigte spätere Teilnehmer-/Statusänderungen sind getrennte Teildaten,
  kein pauschaler Programmfehler. Fehlende Originalbelege, beschädigte Quellen,
  fremde Wettbewerbe und gleichzeitige Widersprüche bleiben echte Fehler.
  **1.908 Tests, drei erwartete Skips, 26 Untertests** im betroffenen Abschlusslauf;
  keine gesamte App-Vollsuite und keine empirische Modellfreigabe behaupten.
  Rein lesende native Probe 15:36 CEST: 1588 `participants_changed`, 1573
  `participants_unconfirmed`; keine Neuberechnung oder Datenbankmutation.
  Regulärer Lauf **15:37:05–15:43:08 CEST, Exit 0**, `completed`, null technische
  Fehler. Fußball 25 Modellkarten, E-Sport sechs; Tennis null aktuelle Karten,
  zwei ausdrücklich gemeldete nicht berechenbare Paarungen, keine Refreshfehler.
  Keine zusätzliche Ausführung erzwungen. Vorheriger 15:07-Lauf war degraded.
- Lesende Zählung 15:13 CEST: 244 rechtzeitige unabhängige Originalevents,
  144 passende normale Endresultate insgesamt vor Train-/Tune-/Testteilung;
  weiterhin null Effekt- und Freigabeartefakte. Die frühere 125er-Zahl ist Historie.
- Weiter offen: echte empirische Wirkung, Fußball-Live-Jointmodell-Anbindung,
  WTA-/Basketball-/Eishockey-/E-Sport-Daily3-Vergleiche. Cricket ausgenommen.
  Fehlende Daten nicht durch erfundene Werte oder rückdatierte Belege ersetzen.

## Produkt-Auditreparatur 21.09.2026 — 8543fcc live

- F01/F04: 15K-Kohärenz und typisierte Ausfallanzeigen repariert; keine
  Gegensätze als gemeinsame Vorschläge, keine unbekannten Daten als 0/0.
- F03/F06: faire E-Sport-Ergebnisqueue, begrenzter Halb-Stunden-Ergebnislauf,
  echte Providerfehler getrennt, keine Schreibsperre beim Netzaufruf;
  verifizierte Fußball-Terminänderungen mit FT-Endergebnis auflösbar.
- Native Zusatzursache: 305 alte E-Sport-Zeilen ohne gespeicherte Team-IDs
  dürfen kein Abrufbudget blockieren. Sie bleiben unverändert erhalten;
  Queue-Nachtrag 8543fcc auf main/GitHub/VPS. Native zweite Probe:
  15 von 15 Endresultaten korrekt zugeordnet, null Providerfehler, alle
  ursprünglichen Prognosen und vollständigen Altzeilen unverändert.
- F05/F08: Defensive Daily3-Priorität korrigiert, 15K-Spielgruppen,
  kompaktere RisikoBet-Details und revisionssichere Modellgrundlagen.
- Abschließende betroffene Regression: 1.676 Tests und 32 Untertests grün;
  lokale Desktop-/320-Pixel-Browserprobe grün. Hauptreparatur d6fff68 plus
  Nachtrag 8543fcc auf main/GitHub/VPS. Gesamtsuite 10.811 bestanden/96 Skips/111 Untertests;
  sieben alte Text-/Reihenfolge-Erwartungen im Nachlauf exakt angepasst und
  grün. Keine einzelne komplett grüne finale Vollsuite behaupten.
  Maßgeblicher aktueller Reparaturbericht:
  [Produktreparaturen](docs/audits/2026-09-21-produkt-reparaturen.md).
- Zuerst den regulären Lauf ab 11:37:04 prüfen: um 11:49:41 aktiv rechnend,
  noch keine neue Veröffentlichung. Alte RisikoBet-Begründungen bis dahin
  noch aus dem 11:07-Datensatz. Kein neuer erfolgreicher Tennis-Tageslauf
  behauptet. Keine bereits erledigten Tests/Deploys/Bereinigungen wiederholen.
- Weiter offen: qualifizierte numerische Verletzungs-/Müdigkeitswirkung,
  echte empirische Verbesserung und Daily3-Vergleiche außerhalb Fußball.
  Keine Aktivierung ohne Datenbeleg. Cricket unverändert ausgenommen.

## Aktueller Stand – Fußball/Tennis, 21.09.2026

- **Nachtrag 08:24 CEST:** Die vier vom Nutzer freigegebenen historischen
  Tennisfälle sind aus aktiver Ergebnisaufnahme, Refresh und Abrechnung entfernt.
  Funktionscommit **`66b0a727ab0772e8137b0eb21063712c46c30192`** auf Worktree,
  lokalem main, GitHub main und VPS bestätigt. Vier Elternzeilen, 30 Originale
  und 22 Revisionen unverändert; keine Geldbuchungen geändert. Keine physische
  Löschung, Rücknahme des exakt begrenzten Katalogs stellt Verarbeitung wieder her.
  [Abnahmebericht](docs/audits/2026-09-21-tennis-altfaelle.md).
- Frische betroffene Regression: **1.988 bestanden, 3 Plattform-Skips,
  26 Untertests**. Danach ergänzter Fremdprognosen-Test in gezielter 16er-Runde
  grün (überlappende Zählung, nicht addieren). Native Vorher-/Nachherprobe mit
  540 Wettbewerben: bisherige Zuordnungsfehler beseitigt, 236 übrige Ergebnis-
  zuordnungen identisch. Nach Deployment Originalbelege erneut validiert,
  Eltern-Fingerabdruck unverändert, keine DB-Schreiboperation durch die Probe.
- Regulärer Wettfinder **08:07:29–08:15:29 CEST, Exit 0**: `completed`, keine
  technischen oder Fußball-Aktualisierungsfehler. Fußball-Kontingentengpass damit
  im Nachhollauf erledigt. Tennis 359 geprüft, **0 fällig**; dies bestätigt nicht
  die Behebung der separaten parallelen Abschlussausnahme. Kein zusätzlicher
  Tennis-Gesamtlauf nach Entfernung, alten Exit-1-Status nicht zurückgesetzt.
- App, Caddy und sieben Timer aktiv, beide Healthchecks `ok`; Tagesbackup bleibt
  aus. Keine Bereinigung, neuen Backups, Schema- oder Geldregeländerung.
  Verletzungs-/Müdigkeitsqualifikation und bessere Wettqualität bleiben offen.

### Historie vor der inzwischen freigegebenen Entfernung

Die unten angefragte Nutzerentscheidung liegt inzwischen vor; Umsetzung und
Abnahme siehe oben. Diese früheren Zwischenstände nicht als aktuell ausgeben.

- Funktionsstand **`7c805aeae0df6b85e68178adc7f40756cf99a06f`** auf Worktree,
  lokalem main, GitHub main und seit 00:17 CEST auf VPS. Vorige Reparaturen
  `e292b10`, `eea0703`, `f6b7c66` und der E-Sport-Anschluss sind enthalten.
  [Bericht und Reproduktionen](docs/audits/2026-09-20-football-tennis-refresh.md).
- Behoben: ursprüngliche 16 Fußball-Historienfehler, acht native Tennis-
  Terminänderungen, WTA-Import einer leeren Ergebnis-Platzhalterzeile,
  wiederholte Historienprüfungen und Wiederverwendung oberhalb 500.000 Verweisen.
  WTA-Ergebnisse reichen wieder bis 20.09. statt 12.09.
- Neue Korrektur: bekannte fremde Spielarten und explizite TBD-Turnierplätze
  verursachen keinen falschen Aufnahmefehler. Sie werden weiter unverändert
  als nicht modellierbar gespeichert. Native Gegenprobe mit 500 Wettbewerben:
  identische Beobachtungen/Abrechnungsquellen, alte Falschmeldung beseitigt.
- **Vollständige Testsuite: 10.773 bestanden, 96 plattformbedingte Skips,
  111 Untertests bestanden**, Exit 0, 33:33 min. Neun reine JUnit-Formatwarnungen.
  XML: `output/playwright/tennis-refresh-20260921-final-junit.xml`.
- Echter Tennis-Gesamtlauf 00:17:10–00:50:26: Modellaufbau, alle **74/74**
  Berechnungen, Montags-Kalibrierungsprüfung und Wochenreport abgeschlossen.
  Kein Timeout. 74 neue Prognose-Originale, **0 neue Shadow-Prediction-Zeilen**
  (die Spiele waren bereits vorhanden), nicht 74 neue Tipps.
- **Noch nicht grün:** Ergebnisaufnahme meldet zwei Konflikte und zwei nicht
  zuordenbare Altfälle wegen geänderter Teilnehmer: WTA 183831, 183854,
  183710, 183844. Der Gesamtlauf bleibt daher Exit 1. Read-only Gegenprobe
  mit 540 nativen Wettbewerben bestätigt exakt diese vier Fälle; 118 Events
  bekommen passende Ergebnisbeobachtungen. Keine alten Originale umschreiben,
  fremde Gewinner zuordnen oder einen Fehlerstatus nur zurücksetzen.
- Nutzerentscheidung angefragt: diese vier alten Prognosen unverändert als
  „nicht auswertbar – Teilnehmer geändert“ separat führen statt jeden neuen
  Tageslauf daran scheitern zu lassen. Noch keine entsprechende Vertrags- oder
  Statusänderung implementiert; keine Gewinne/Verluste automatisch ändern.
- Zusätzliche Nachprüfung: der parallele Wettfinderlauf 00:37–00:56:30 meldete
  beim Tennis-Refresh erneut `ContextIntegrityError`. Der bestehende Catch
  speicherte nur den Typ, keinen Fehlerort; damit noch keine genaue Ursache
  bewiesen. Diagnosecommit `e8f0faf` ergänzt begrenzte Codepositionen/Fehlerketten
  nur im Serverlog (keine Meldungstexte/Secrets in Log oder Nutzerartefakt),
  auf main/GitHub/VPS. 147 betroffene Regressionstests grün; Vollsuite oben
  gehört zu `7c805ae`. Read-only Gegenprobe mit vollständiger physischer
  Historie und 651.445 WTA-Verweisen: eine aktuelle Prognose in 487 s bis vor
  Veröffentlichung vollständig vorbereitet. Kein reproduzierter Integritäts-
  fehler; Ursache des parallelen Fehlversuchs noch offen. Diesen neuen Befund
  nicht mit den vier historischen Ergebnisfällen gleichsetzen.
- Folgelauf 01:07:04–01:16:07: Tennis ohne Fehler, aber **0 fällige Refreshes**,
  somit keine erneute Abschluss-/Race-Abnahme. Zwölf Fußball-API-Reservefehler.
- Separater Fußball-Engpass: 00:07–00:16 CEST 13 Abrufe an der API-Reserve
  gestoppt (Restschätzung 2.443, Background-Reserve 2.500). Keine Rückkehr der
  alten Identitätsfehler. Direktes Tageskontingent erneuert 02:00 CEST;
  Wiederholpfad/Timer vorhanden, regulär 02:07. Erfolgreichen Nachhollauf noch
  prüfen. Reserve und Tarif unverändert lassen.
- App/Healthchecks funktionieren, sieben Timer aktiv, tägliche Sicherung
  weiterhin deaktiviert. Keine Bereinigung, neuen Backups, Quoten-/Geldregel-
  oder UI-Änderungen. Verletzungs-/Müdigkeitswirkung und bessere Wettqualität
  sind dadurch weiterhin nicht empirisch nachgewiesen.
- Die älteren Statusblöcke darunter sind Historie, keine aktuelle Gesamtabnahme.

## E-Sport-Quoten – Anbindung 20.09.2026

- OddsPapi-Schlüssel geschützt übergeben; native Kontoprüfung: aktiver kostenloser
  Tarif, 250 Anfragen, keine automatische Verlängerung. Erste echte CS2-Preise
  von identifizierten Buchmachern bestätigt, keine Modellquote als Anbieterpreis.
- Gemeinsamer Serien-Sieg-Cache für CS2, Dota 2, LoL und Valorant implementiert:
  Wettfinder, Daily3 und RisikoBet benutzen dieselben Preise. Exakte Disziplin,
  Teams, Spielbeginn, PandaScore-Ursprung und Marktbindung; keine Map-Übernahme.
- Beste passende Quote unter 1,20 entfernt nur den Vorschlag, nicht das Modell.
  Fehlende Angebote bleiben unbekannt. Abrufbeobachtung ist keine Einsatzfreigabe.
- Freies Kontingent: höchstens sieben reservierte Anfragen täglich, 25 Monats-
  reserve; maximal fünf Turniere pro Anfrage, ein Buchmacher pro Anfrage.
  Kleinere vollständige Pakete alle zwölf Stunden, größere einmal täglich.
  Vor jedem Abruf aktive Free-Subscription prüfen; kein kostenpflichtiger Wechsel.
- Kein neuer Timer, kein Historienwachstum: ein begrenzter ersetzbarer Quotencache,
  Budget im vorhandenen Zähler. Keine neue Bereinigung oder Backupaktivierung.
- Funktionscommit `696635d` auf main/GitHub/VPS; Schlüssel root:betboy 0640,
  App neu gestartet, interner/öffentlicher Healthcheck `ok`. 1.358 Tests plus
  111 Untertests und 218 zusätzliche main-Anschlusstests bestanden.
- Vollständiger VPS-Quotenabruf: sieben kommende Spiele, fünf Anfragen,
  keine Fehler, Cache 8.987 Bytes. E-Sport-Worker um 18:46 CEST erfolgreich:
  30 Spiele geprüft, acht neue Modelle. Zwei exakte Modell-/Preiszuordnungen
  bestätigt. Veröffentlichung 20:16 CEST inzwischen tatsächlich sichtbar:
  Wettfinder Team Liquid 1,267; RisikoBet FlyQuest 3,80. Der Map-Markt bekommt
  keine Serienquote. Daily3 hat derzeit keine passende Auswahl.
- Nachprüfung: Disziplin ging beim Speichern der Quoten-Nachweise verloren.
  Korrektur `94fa36f` bewahrt sie für neue E-Sport-Daten; bestehende andere
  Sportarten und E-Sport-Altdaten ohne Disziplin bleiben unverändert.
  421 gezielte Tests bestanden; Quotenbeobachtung bleibt ohne Einsatzfreigabe.
  Code auf GitHub main und VPS (20:55 CEST); native read-only Gegenprobe mit
  echter LoL-Quote 1,267 bestanden, falsche Disziplin abgewiesen. Weitere
  142 Tests auf lokalem main grün. App und beide Healthchecks `ok`.
- Der gemeinsame Lauf ist weiterhin fachlich/technisch nur teilweise gelungen:
  16 Fußball-Fehlermeldungen und ein Tennis-Sammelfehler mit acht nicht
  aktualisierten Prognosen (`ContextIntegrityError`). Nicht durch den
  E-Sport-Anschluss als repariert melden; Verletzungs-/Müdigkeitswirkung offen.
- Release-/VPS-Nachweis in
  [E-Sport-Anschlussbericht](docs/audits/2026-09-20-esports-quoten.md).
  Ältere Angaben unterhalb dieses Blocks sind historische Zwischenstände.

## E-Sport-Quoten – frühere Zugangsvoraussetzung 20.09.2026

- FieldFunded erneut im getrennten Browser geprüft: Free-Anmeldung scheitert
  weiterhin am CORS-Preflight auf `/api/stripe/free-key`; kein Schlüssel erhalten.
- Bestehende The Odds API: echte kostenlose Katalogabfrage erfolgreich,
  179 Sport-/Turniereinträge einschließlich inaktiver, kein E-Sport-Eintrag;
  Kontingent unverändert 499. Kein Ersatz durch eine errechnete Modellquote.
- Alternative OddsPapi: tatsächliches Registrierungsformular bestätigt Free,
  alle Sportarten/Buchmacher und 250 Anfragen/Monat. Anmeldung erfordert eigenes
  Passwort und hCaptcha; dem Nutzer im internen Browser bereitgestellt.
  Schlüsselübergabe außerhalb von Git im geschützten Verzeichnis vorbereitet.
- Nächster Schritt nach Schlüsselübergabe: tatsächlichen Free-Tarif und
  E-Sport-Katalog prüfen, exakte Spiel-/Disziplin-/Serienmarktbindung testen,
  gemeinsame Preisversorgung für Wettfinder, Daily3 und RisikoBet anbinden.
  Auch Katalogabfragen zählen bei OddsPapi zum Kontingent; Abrufe bündeln,
  Monat-/Tagesbudget begrenzen, keine automatisch kostenpflichtige Erweiterung.
- Noch keine OddsPapi-Registrierung abgeschlossen, keine Produktivcode- oder
  VPS-Änderung und kein erfolgreicher E-Sport-Quotenabruf behaupten.
  Details: [Weitere Sportquoten](docs/audits/2026-09-20-weitere-sportquoten.md).

## Quotenanbindung 20.09.2026 – weitere Sportarten

- Tennis-Zugang inzwischen eingerichtet und auf dem VPS aktiviert.
  Funktionscommit `8e2581e` auf main/GitHub/VPS; 753 betroffene Tests und
  32 Untertests bestanden. Monatsbudget 500 Credits mit 25 Reserve,
  höchstens 16 reservierte Credits/Tag; mehrere Spiele eines Turniers gebündelt.
  Schlüssel ausschließlich in geschützter Konfiguration, nicht im Repository.
- Echte VPS-Probe: WTA Singapore Open, sechs kommende Events; Kasatkina gegen
  Sasnovich mit sieben Buchmachern pro Seite bepreist, keine Abruffehler.
  Ein Credit verbraucht, 499 verbleiben. Nur Quotenprüfung, kein Modell/Tipp erzeugt.
- Erster Quotenrelease `f4677e2`: damals main/GitHub/VPS abgeglichen, 1.122 Tests plus 58 Untertests
  grün. Nativer Abruf: vier NHL-Spiele zugeordnet, zwei Quoten ohne Fehler;
  Cache rund 3 KB. Das NHL-Modell liefert derzeit noch keine gewählte Seite.

- Fußballquoten und der übergreifende 1,20-Filter waren bereits mit `66161eb`
  live. Aktuell ergänzt: zentrale API-Sports-Quoten für NBA/Euroleague/NHL,
  Wiederverwendung in Wettfinder/Daily3/RisikoBet, inklusive RisikoBet-Spielen
  ohne vollständige Modellprognose. Zeitangabe ist ausdrücklich Abrufzeit,
  keine erfundene Buchmacherzeit und keine neue Einsatzfreigabe.
- Bestehender Worker/Budgetzähler, begrenzter Cache ohne Historienwachstum.
  Keine neue Bereinigung, Datenbank, Sicherung oder Timer.
- E-Sport bleibt offen: FieldFunded-Free-Anmeldung scheiterte im Anbieterformular
  an CORS/„Network error“; kein bestätigter Schlüssel. Details und Nachweise in
  [Weitere Sportquoten](docs/audits/2026-09-20-weitere-sportquoten.md).
- Bestehende Tennis-/Kontext-/Workerfehler sind dadurch nicht behoben.
- Die ältere Regel unten ist zeitlich enger formuliert: seit `d94c5bc`
  gilt der Filter auch für eindeutig als älter markierte letzte Angebote
  bis 24 Stunden. Fehlende oder fremde Quoten bleiben unbekannt.

## Neue Nutzerregel 20.09.2026 – bekannte Quoten unter 1,20 aussortieren

- Diese ausdrückliche Nutzerentscheidung ersetzt die bisherige ausnahmslos
  quotenunabhängige Sichtbarkeit: automatischer Wettfinder, eigene Fußballsuche
  und Daily3 entfernen Vorschläge, deren beste exakt passende aktuelle
  Anbieterquote unter 1,20 liegt. Genau 1,20 ist erlaubt. Fehlende/veraltete/
  fremde Quoten bleiben unbekannt; weder Modellchance noch Rechenpreis werden
  als angebotene Quote ausgegeben. Keine neuen kostenpflichtigen API-Abfragen.
- Reihenfolge: erst widerspruchsfreie Modellrichtung, danach Preisfilter,
  danach Platzvergabe. Der Filter darf nicht auf die Gegenseite umschalten.
  Alle gespeicherten Prognosen und Wahrscheinlichkeiten bleiben unverändert.
- Daily3 lehnt neue Vormerkungen mit manuell eingegebener Quote unter 1,20
  transaktional ab. Historische Buchungen, deren Wiederholungsbestätigung,
  Platzierung/Abrechnung und Nachträge tatsächlich externer Wetten bleiben
  lesbar und gültig. Keine Schemaänderung oder Umschreibung der Historie.
- 811 Tests plus 26 Untertests bestanden. Grenzwert ohne Aufrundungsloch,
  einzelne Anbieter, veraltete Hochquoten, falsche Zuordnungen, Tennis,
  echte UI-Eingabe und vorhandene Altverträge separat abgesichert.
- Rein lesende VPS-Probe 11:15 CEST: 619 Eingangssignale, 336 kohärente
  Auswahlen unverändert; in diesem Bestand keine aktuelle exakt passende
  Quote unter 1,20. Daher nicht behaupten, jetzt seien dort massenhaft
  Auswahlen entfernt worden. Ohne Quote lässt sich dieser Filter nicht prüfen.
- Nur Produkt-/Preisfilter, kein Nachweis besserer Wettqualität. Unveränderte
  Restarbeiten an Tennis-Laufzeit sowie Verletzungs-/Müdigkeits-/Wetterwirkung.

## Hervorhebungen 20.09.2026 – spielbezogener Vergleich auch im Wettfinder

- Fehler am echten Bestand reproduziert: Corinthians–Fluminense, Auswärtsteam
  unter 2,5, wurde mit 89,8628 % hervorgehoben, obwohl die Saisonbasis schon
  91,655 % und die Formvariante nur 81,8378 % ergaben. Bisher prüfte nur Daily3
  den zusätzlichen spielbezogenen Formvergleich; im Wettfinder fehlte er.
- Fußball-Hervorhebungen nutzen jetzt denselben exakt gebundenen Vergleich
  und werden nach seinem Formkontrast geordnet. Die vorhandene Zwei-Prozent-
  punkte-Relevanzregel ist kein Sicherheits-/Valuebeweis. Keine Wettarten-
  verbote, keine Quotenfilter, keine Daily3-Wahrscheinlichkeitsschwelle im
  normalen Wettfinder. Eine kurze Formangabe erklärt die Hervorhebung.
- Richtungs-/Widerspruchsprüfung bleibt davor: Ein positiver Formkontrast
  eines Außenseiters darf die wahrscheinlichere Ergebnisrichtung nicht verdrängen.
- 706 Tests plus 26 Untertests bestanden; 19 neue Regressionen sichern den
  gemeldeten Fall, weiterhin erlaubte breite Märkte, Quotenunabhängigkeit,
  Belegbindung und Ergebnisrichtung. Streamlit: 23 Spielblöcke, keine Exception.
- Rein lesender Vorher-/Nachher-Lauf am VPS um 10:47 CEST: 621 Eingangssignale,
  dieselben 338 kohärenten Prognosen samt Wahrscheinlichkeiten; Fluminense
  unter 2,5 nicht mehr hervorgehoben. Keine Produktionsdatei dafür verändert.
- Nur Auswahlpräsentation korrigiert, keine neue Modellqualität nachgewiesen.
  Tennis-Laufzeit und vollständige Verletzungs-/Müdigkeits-/Wetterwirkung bleiben offen.

## Nutzeransicht 20.09.2026 – Diagnosebanner entfernt

- Automatischer Wettfinder: kein globaler Auswahlzähler und kein Banner
  „Suche unvollständig“ mehr, auch kein Ersatzabsatz oder leerer Rahmen.
- Datenstand, Sportfilter, Spielblöcke, sämtliche Auswahlen und wichtige
  Hinweise an einzelnen Karten bleiben erhalten. Interne Fehler-/Abdeckungs-
  daten werden nicht verändert oder als erfolgreich umgeschrieben.
- 243 betroffene Tests bestanden; zusätzlich echter Streamlit-Testlauf mit
  23 Spielblöcken, erhaltenem Datenstand und ohne Exception. Interner Browser
  wegen Sandbox-Startfehler nicht verfügbar; kein externer Browser verwendet.
- Reine UI-Korrektur. Die folgenden Tennis-/Kontext-Restarbeiten bleiben offen.

## Fortsetzung 20.09.2026 – Datenlauf-Konflikt

- Übergabe gegen echte Daten geprüft: `2758619` war lokal/GitHub/VPS identisch.
  Über Nacht sind 23 Fußball-Originale zu 19 Spielen gespeichert worden; alle
  sind partiell, also noch kein vollständig quellgebundener Trainingsfall.
- Tennis brach um 07:18:15 mit einer Datenbank-Lesesperre des Fußballlaufs ab.
  Ergebnisprüfung jetzt auf die empfangenen Events begrenzt; Ergebnis-/Spieler-
  historie gibt das konsistente SQL-Lesebild vor CPU-Validierung frei.
- 578 betroffene Tests bestanden, 4 Skips. Rein lesende VPS-Probe: selbst für
  1.096 Fußball-Events nur 2,207 s SQL-Lesephase; Spielerinventur 0,650 s.
  `bc6fef3` auf main/GitHub/VPS live; nochmals 125 Tests auf main und beide
  Linux-Schreibkonkurrenzproben bestanden. App/Healthchecks/Rechentimer aktiv.
  Echter Tennis-Neulauf 09:31:57: Modellaufbau erfolgreich, WTA publiziert;
  WTA-Ergebnisstand 12.09. Tages-Scan aber 09:45:42 erneut mit Schreibkonflikt
  abgebrochen. Nicht als erfolgreicher Gesamtlauf melden.
- Zweite Ursache gemessen: physisches Lesen der Tennis-Historie hält die
  Sperre 21,626 s, bisheriges Schreibbudget nur 5 s. Gemeinsame endliche
  Wartezeit jetzt 60 s, Journal/Schema/Prüfinhalte unverändert. 980 Tests,
  5 Skips grün. `9c579fe` auf main/GitHub/VPS live; 67 main-Tests/5 Skips
  und Linux-Probe mit echter 22-s-Lesesperre bestanden. Neuer Tennis-Lauf
  endete aber 10:19:32 mit 900-s-Timeout: Empfang gespeichert, History bereit,
  dann Vorbereitung von 48 Prognosen nicht abgeschlossen. Kein erfolgreicher
  Gesamtlauf und keine 48 veröffentlichten Tipps behaupten. Letzter Wettfinder
  vor Codewechsel ebenfalls degraded, nicht mit vollständiger Datenabdeckung.
- Nächste technische Aufgabe: CPU-Anteile von History, Spielerprojektion,
  Feature-Vorbereitung und Schlüsselbildung am selben Bestand messen und den
  tatsächlichen Engpass beheben. Synthetischer 500k-Grenzvergleich allein
  erklärt den Timeout nicht; keine blind erhöhten Laufzeit-/Speichergrenzen.
- Vollständige Verletzungs-/Müdigkeits-/Wetterwirkung bleibt unerledigt.
  Weder Aufnahmebudget noch Qualitätskriterien wurden gelockert. Keine neue
  Sicherung/Bereinigung, keine Finanz- oder Cricketänderung.
- [Prüfbericht und konkrete Restarbeiten](docs/audits/2026-09-20-fortsetzung-datenlauf.md).
  Ältere Abschnitte unten sind datierte Zwischenstände, keine aktuellen Freigaben.

## Kontextanschluss und Daily3-Spielvergleich – 19.09.2026, Code live

- Nachtrag `362a4a6` am 20.09. um 00:04 CEST auf VPS bestätigt; 1.526 Tests,
  nochmals 210 auf main und Linux-Smoke grün. Tatsächliche Originalaufnahme
  nach diesem Nachtrag bleibt offen; nächster normaler Worker 00:07 CEST.
- Nicht als vollständig fertig melden: numerische Verletzungs-/Müdigkeits-/
  Wetterwirkung ist weiterhin nicht trainiert und empirisch freigegeben.
  Die vorhandenen Prognosen sind echte Berechnungen, aber ohne diese Wirkung.
- Daily3 v4 vergleicht aktive/Form-Variante mit der Saison-/Heim-Auswärtsbasis
  derselben Begegnung. Favoritenstärke allein reicht nicht. Die zusätzlichen
  zwei Prozentpunkte sind eine Relevanzregel, kein Sicherheits-/Valuebeweis.
  Keine Marktverbote oder Quotenfilter; normale Prognosen bleiben erhalten.
- Kanonischer Fußballworker erhält die vorhandene Originalaufnahme mit
  dauerhaftem Aufnahmebudget: 4 MiB/Sitzung, 8 MiB/UTC-Tag, 128 MiB insgesamt
  an zusätzlicher JSON-Nutzlast. Keine neue Sicherung oder Bereinigung.
- Nicht gesendete Spielerhistorienabfragen wegen API-Budgetreserve lösen
  keine neue 24-Stunden-Wartefrist mehr aus; echte Fehlantworten weiterhin.
- Nachtrag abgesichert: Eine übergroße optionale Originalaufnahme darf die
  unveränderte normale Prognose nicht verwerfen; strenge Speicherung bleibt.
- Der erste Live-Lauf deckte den Mehrgruppenfehler auf: leere erste Gruppe,
  danach keine Aufnahme mehr. Nun teilen sämtliche Gruppen dasselbe endliche
  Kontingent; keine Vervielfachung, auch nicht bei parallelen Veröffentlichungen.
- Tatsächliche Lücken: keine Fußball-Originale oder trainierten Effekte im
  geprüften VPS-Bestand; Tennis nur 112 unterschiedliche Ergebnisereignisse.
  Neue Originalaufnahme ersetzt weder native Zuordnung noch Replayfreigabe.
- Funktionscommit `39bd0eb` gepusht und auf VPS deployed; 1.522 Tests grün,
  weitere 202 Anschlusstests auf main grün. Healthchecks und Rechentimer
  bestätigt. Erster Datenlauf 23:42:16 beendet, weiterhin degraded/16 Daten-
  probleme und noch keine Originale; API-Aufschub live korrekt. Aufnahme nach
  Mehrgruppen-Nachtrag weiterhin tatsächlich nachweisen, nicht als fertig melden.
- Prüf-/Releasebelege im [Reparaturbericht](docs/audits/2026-09-19-kontextanschluss-und-spielvergleich.md).
  Nachtrag mit Größen- und gemeinsamem Gruppenbudget ist separat live bestätigt;
  keine durchgehende Daten- oder Kontextqualifikation daraus ableiten.
  Cricket, Echtgeldregeln, alte Archive und deaktiviertes Tagesbackup erhalten.

## Daily3 19.09.2026 – Auswahlregel und Teil-Refresh repariert

- `0a54313`: keine Sortierung allein nach höchster Rohwahrscheinlichkeit mehr.
  Versions- und spielgebundener Vergleich zur historischen Markthäufigkeit,
  mindestens 70 Prozent in allen drei vorhandenen Modellvarianten. Keine
  pauschalen Wettartenverbote und kein Quotenfilter; normale Prognosen erhalten.
- `533a98f`: echter VPS-Befund behoben – ein nicht modellierbares Spiel verwirft
  nicht mehr die erfolgreichen Berechnungen seiner ganzen Gruppe. Alte Daten
  fehlgeschlagener Spiele werden weder gelöscht noch als frisch umetikettiert;
  ihr Fehler bleibt über weitere Gruppen hinweg sichtbar.
- Beide Commits auf main/GitHub und VPS; 1.090 Tests/111 Untertests jeweils im
  Worktree und main bestanden. App/Healthchecks bestätigt. Normaler Datenlauf
  um 15:26:36 CEST beendet: 51 Spiele neu modelliert, 9 weitere weiterhin
  unmodelliert (deshalb ehrlich Teildaten/Exit1). Gründe dieser neun offen.
  Echter Vorher-/Nachher-Vergleich bestätigt: alte Regel liefert exakt die
  beanstandeten drei Tipps; neue Regel Reykjavík-Gesamtüber2,5, Siriusüber0,5,
  Santosüber0,5. Zwei einfache Märkte bleiben erlaubt, kein Marktverbot.
  Kein zusätzlicher vollständiger 10k-Testlauf.
- Vergleichsproduzent bislang nur Fußball; ohne passenden Vergleich keine
  Daily3-Auswahl anderer Sportarten, deren normale Prognosen bleiben sichtbar.
  Kein empirischer Nachweis besserer Treffer-/Gewinnqualität. Verletzungs- und
  Müdigkeitswirkung bleibt separat offen; Cricket unverändert.
- Nur Streamlit-AppTests: interner Browser scheitert schon beim Start an
  Windows-ACLs. Keinen externen Browser übernehmen. Keine neue visuelle
  Desktop-/Mobile-Abnahme behaupten. Keine weitere Speicherbereinigung oder
  Sicherung; Tagesbackup bleibt aus.
- [Reparaturbericht und ehrliche Grenzen](docs/audits/2026-09-19-daily3-auswahlvergleich.md).

## Spielblöcke 19.09.2026 – gemeinsames Auf-/Zuklappen live

- Funktionscommit `1e918b9` auf main/VPS: automatischer Wettfinder zeigt jedes
  Spiel nur einmal, mit sämtlichen bisher sichtbaren Auswahlen im selben Block.
  Hervorgehobene Spiele zunächst offen, weitere zunächst geschlossen.
- Zustand bleibt innerhalb der Browsersitzung bei Sportfilter-/Seitenwechseln
  erhalten. Seiten enthalten ganze Spiele, keine zerschnittenen Marktgruppen.
- 907 betroffene Tests plus 26 Untertests jeweils in Worktree und main grün.
  Lokal Desktop/Tablet/Mobil und echter VPS-Browser geprüft; Beispiel
  Brommapojkarna–Göteborg mit allen zehn Auswahlen gemeinsam geschlossen.
- Keine Modell-, Quoten-, Geld-, Datenbank- oder Backupänderungen. Bekannte
  fachliche Restarbeiten bleiben offen. Keine erneute Speicherbereinigung.
- [Abschluss und Grenzen](docs/audits/2026-09-19-spielbloecke.md).

## Prognosekarten 19.09.2026 – kompakte Fakten und Ausfalldetails live

- Funktionscommit `763c741` auf main/VPS. Kurze Torprognose und Faktenfelder
  statt langer sichtbarer Absätze, Einzelheiten per Klick/Tastatur; Wettfinder
  und aktuelle Daily3-Karten. Keine Änderung von Wahrscheinlichkeit oder Geld.
- Spielerstatus ehrlich getrennt: alte gemischte Listen nicht als gesicherte
  Ausfälle bezeichnen. Neue Läufe speichern getrennte Namen; kein Zusatzabruf.
  Nicht eingerechnete Ausfallwirkung bleibt direkt sichtbar.
- 713 Tests und 26 Untertests jeweils im Worktree und main bestanden;
  Desktop/Mobil, Tastatur und echte Website geprüft. Health/Timer bestätigt.
- Keine Speicherbereinigung/Migration/Sicherung wiederholen. Tagesbackup aus.
  Vollständige Modellwirkung und empirische Qualität bleiben offen.
- [Abschluss und Grenzen](docs/audits/2026-09-19-kompakte-prognosekarten.md).

## Daily3 19.09.2026 — defensives Modellprofil und kompakte UI live

- Funktionscommit `1985407c176e4cf5ecc4a9d5b2a93636b8634673` auf main/VPS.
  Mindestens 70% Modellschätzung, höhere Modellchance vor Vielfalt, ein Spiel
  pro Slot. Kein Gewinnziel-/Quotenfilter, keine Änderung der normalen Rangfolge.
- 344 betroffene Tests im Worktree und nochmals in main bestanden. Desktop,
  Mobil, leer/gefüllt und die echte Website geprüft. Kein zusätzlicher Gesamttest.
- Hauptansicht gekürzt; allgemeine Regeln optional, konkrete Unsicherheiten
  weiterhin sichtbar. Echtgeld-/Budget-/Abrechnungslogik unverändert.
- VPS-Codewechsel und Healthchecks bestätigt. Keine neue Speicherbereinigung,
  Datenmigration oder Sicherung. Tagesbackup bleibt disabled, Retention unverändert.
- Offen bleiben empirische Qualität, vollständige Verletzungs-/Müdigkeitseffekte
  und die vorher bestehenden Teildaten-/Datenjobfehler. Höhere Roh-Modellchancen
  sind keine nachgewiesene Sicherheit und kein CHF150-Einkommensversprechen.
- Details und ehrliche Abgrenzung der SSH-Nachlaufkante:
  [Releasebericht](docs/audits/2026-09-19-daily3-defensiv.md).

## Speicherreparatur 19.09.2026 — live, ca. 11:29 CEST verifiziert

- **Erledigt:** Funktionscommit `8caf022b562c561c7d23b4b8363791bb0869d9d3`
  gepusht und auf VPS bereitgestellt; nachfolgende Abschlussdokumentation
  aendert keinen Produktcode. Vorherige Produktreparaturen damit ebenfalls
  ausgeliefert. Wartungsauftrag `betboy-storage-repair-20260919-b.service`
  erfolgreich (Exit 0). Keine bereits erledigte Speicherbereinigung wiederholen.
- Produktivdatenbank **3.326.431.232 -> 2.092.552.192 Bytes**, rund 1,23 GB
  weniger. 36 aufgeblähte Snapshots umgepackt; alle 1.041 Analyseidentitäten,
  926.502 Inhalts-/Empfangsbelege und übrige Tabellen-/Schemaidentitäten
  erhalten. SQLite/Fremdschlüssel ok, große Inline-Restfälle 0. Frischer
  normaler Lesetest mit 504.808 Verweisen und unverändertem Hash bestanden.
- App/Caddy aktiv, lokale und öffentliche Healthchecks ok; sechs Rechentimer
  wieder aktiv. Tagesbackup disabled/inactive; Aufbewahrungstimer unverändert.
  Kein neues Tages-/Updatearchiv; alte Archive und Root-Updater nachweislich
  unverändert. Nur eigene temporäre synthetische QA-Daten (~114 MB) entfernt.
- **Nicht daraus ableiten:** vorher fehlgeschlagene/degraded Tennis-/Wettfinder-
  Läufe, vollständige Verletzungs-/Müdigkeitswirkung oder empirische Qualität
  seien erledigt. Normale Beobachtungshistorien dürfen weiter wachsen; behoben
  ist die unbeabsichtigte Vollkopie jeder großen Nachweisliste pro Analyse.

- Konkreter Defekt behoben: ab 500.001 Nachweisverweisen wurden rund 34 MB
  pro Analyse erneut inline gespeichert. Gemeinsame Blockspeicherung und
  Leser funktionieren nun auch oberhalb dieser Grenze; Inhalte/Hashes und
  Prognosen bleiben unverändert. Keine Statistiken oder Wetthistorien löschen.
- 25 gezielte Tests jeweils Windows und VPS-Linux bestanden. Gesamtlauf:
  10.293 bestanden, 96 Skips, 111 Untertests, 16 Windows-Git-Setupfehler;
  die vollständige betroffene Testdatei anschließend mit exakt scoped
  safe.directory: 56 bestanden. Zusammen 10.309 unterschiedliche Tests
  erfolgreich, keine Quell-/Teständerung danach. Nicht als einzelnen grünen
  Gesamtlauf ausgeben. Details: [Speicherbericht](docs/audits/2026-09-19-snapshot-speicherfehler.md).
- Nutzer will keine neuen Tages-/Updatearchive. Tagesbackup auf VPS bereits
  disabled/inactive. Vorhandene Archive und Aufbewahrungspolitik unverändert.
  Alten Updater nicht unverändert starten: er erzwingt Archive und aktiviert
  Tagesbackups erneut. Dieser Release verwendet einen geprüften Code-only-
  Ablauf ohne Root-/Dependency-/Finanzmigration und danach die bestehende
  verlustfreie Inline-Snapshot-Kompaktierung bei stillstehenden Schreibern.
  Dies ist kein Auftrag, den alten Updater oder die Kompaktierung erneut
  auszuführen. Fachliche Modelllücken bleiben separat offen.

## Produktreparatur 19.09.2026 — committed und gepusht, VPS separat

**Veröffentlicht:** Reparaturpaket `2cd0a982a96331996955779a8dfff0466ecfb2fd` ist im Hauptcheckout auf main und auf GitHub-main, nach regulärem Push per `ls-remote` bestätigt. Nachfolgende Änderungen ergänzen nur diese Abschlussdokumentation. Funktions-/Teststand `d0759b1`. Alle unabhängigen Task-/Gesamtreviewbefunde geschlossen. Keine Produktions-/VPS-Änderung oder Speicherbereinigung in dieser Runde.

**Tests abgeschlossen:** Vollsuite auf `d0759b1`:10303 bestanden,96 Skips,111 Untertests,Exit0,1545.58s; neun reine JUnit-Berichtshinweise. Anschließend Hauptcheckout auf `2cd0a98`:625 bestanden,79 Untertests,Exit0,90.16s. Keine Quell-/Teständerung während oder nach diesen Läufen. Logs im Worktree `output/playwright/product-full-suite-20260919-d0759b1.{log,xml}` und im Hauptcheckout `output/playwright/product-main-checkout-20260919-2cd0a98.log`. Vorige Fixture-/Ownershipfehler im Reparaturbericht erklärt; keine Schutzregeln/Pins gelockert. Erledigte Tests nicht erneut als laufend übernehmen.

Dieser Abschnitt ersetzt die darunterstehenden historischen Statusmeldungen. Nutzerauftrag: bestätigte Produktfehler beheben, committen und pushen; Cricket unverändert. Keine weitere Speicherbereinigung und keine automatische Codeauslieferung durch Timer.

- Ausgangsstand des geprüften Produkt-Audits: lokal/GitHub/VPS `c64218b`. Audit [2026-09-18-produktqualitaet.md](docs/audits/2026-09-18-produktqualitaet.md); Reparaturfortschritt [2026-09-18-produktreparatur.md](docs/audits/2026-09-18-produktreparatur.md).
- Arbeit im bereits genehmigten Worktree `.worktrees/context-capacity-recovery-20260910`, Branch `codex/context-capacity-recovery-20260910`; Hauptcheckout per Fast-forward aktualisiert, VPS unverändert. Bestehender Worktree und fremde/ungetrackte Prüfdateien bleiben erhalten. Kein erneutes Worktree/Design/Push-Permission-Pingpong.
- Lokal erledigt und unabhängig geprüft: `f844f05` Preiswarnung/keine erfundene Erholung; `c953d46`+`9467148` gemeinsame widerspruchsfreie Auswahl, belegte Hervorhebung/Analyse, keine pauschalen Marktverbote; `f42e264` gemeinsame konsistente Fußballverteilungen mit eigener Validierungsversion und alter Ticket-/ORIGINAL-Kompatibilität. 709 betroffene Tests plus97 Untertests für den mathematischen Stand; **keine neue Gesamt-Suite** daraus ableiten.
- WTA-Dauererhaltung `534d27d` + `2d92eb9` ist unabhängig nachgeprüft: alle drei Reviewbefunde geschlossen, echte historische Laufzeit-/Trainingsreplays erhalten; 360 betroffene Tests und 92 numerische Tests bestanden, 3 Skips. Keine Müdigkeitswirkung daraus ableiten.
- Basketball-/Eishockey-Brücke `fdd04bf`+`423e888` unabhängig abgeschlossen: dieselbe vorhandene Berechnung wird im normalen Wettfinder konsumiert, Belege unveränderlich übernommen. Daily3 erklärt gemeinsamen Bestand und tatsächliche Anzahl. 468 Tests plus26 Untertests; Fixrunde275 plus26 Untertests. Finanz-Lesevorprüfung `5ff08a9` unabhängig geprüft:217 Tests plus85 Untertests; Geld-/Integritätsregeln unverändert. Browser-Rundungsfehler mit `a322430` behoben: kein gerundetes100% bei Wahrscheinlichkeit kleiner1;160 betroffene Tests bestanden.
- Kausale Fußball-Originalanbindung `f6f62a5` ist implementiert und unabhängig geprüft: 590 Tests, 4 Skips, 32 Untertests. Endliche ausdrückliche Opt-in-Budgets; standardmäßig keine Zusatzspeicherung. Ausführungsfingerabdruck ist **kein** replay-fähiges C1-Codepaket oder eine Effektqualifikation. Originalquelle, Codeidentität und empirischen Stand getrennt berichten. Echte Aktivierung/Tageszuwachs-/Kapazitätsprüfung bleibt offen.
- Desktop-/Mobilrenderer mit klar synthetischen Daten tatsächlich geprüft: konsistente Richtung, unveränderte Prognosen bei Quote1.12, Daily3 mit0/1/3 Events, neutrale Basketball-/Eishockeykarten, kein Überlauf bis320px und frische Konsole ohne Fehler. Bericht `docs/audits/2026-09-18-product-ui-check.md`. Keine Freigabe der vollständigen Produktionsseite oder Vorhersagequalität daraus ableiten.
- Git-Integration, Hauptcheckout-Prüfung und regulärer Push sind erledigt. VPS-Deployment und neue Linux-/Betriebsabnahme separat; Timer liefern keinen Code aus. Eine neue Produktionsfreigabe nicht allein aus Windows-Tests oder GitHub-Hash ableiten.
- **Fachlich weiterhin offen:** tatsächliche angewendete/empirisch belegte Verletzungs-/Müdigkeitseffekte; Aktivierung des kausalen Fußball-Live-/B1-Anschlusses und neuer versionsgleicher Wirkungs-/Trainingspfad; tatsächliche Tennis-Endzeiten/native Zuordnung; ausreichende unbenutzte echte Testevents. Neue Verteilungsregel braucht eigene Qualifikation. 101 gebundene Tennis-Spiele sind keine200 geeigneten Holdout-Events. Keine bessere Wettqualität behaupten.

Konkrete Wiederaufnahme aus den jeweiligen `.superpowers/sdd/2026-09-18-*/progress.md` und tatsächlichem Git; bereits vollständige Tasks nicht neu implementieren. Fremde/ungetrackte Prüfdateien erhalten. Der neue Fußball-Liveanschluss ist technisch unabhängig geprüft, aber nicht aktiviert; sein Code und Speicherbaustein sind kein fachlicher Effektbeleg.

## Historisches Releasepaket 18.09.2026 — neuerer Stand steht oben

- **Funktionsstand `c44684d` ist lokal auf `main` und auf GitHub-main.** Die folgenden Dokumentationsänderungen gehören zum selben Releasepaket. VPS zuletzt weiterhin `f3c2b60`; ein Push ist kein Deployment. Abschließende Serverbelege werden separat in `output/playwright/context-repair-deployment-20260918.md` festgehalten. Falls diese Datei fehlt, keinen erfolgreichen neuen Release annehmen; Git/Health/Jobstatus frisch lesen.
- Vollständige finale Suite: **10.065 bestanden, 96 Skips, 97 Untertests bestanden**, Exit 0, 1608.90 s. Danach im fast-forwardeten Hauptcheckout nochmals **346 bestanden, 12 Skips**, Exit 0. Alle Funktionsreviews, der Gesamtdiffreview und die QA-Korrektur sind ohne offene Befunde. Quellen-/Testdateien blieben während des finalen Gesamtlaufs eingefroren. Logs: `full-suite-final-20260918-39b5c281.log`, `main-checkout-20260918-031b438d.log` unter `output/playwright/`.
- Fertig: kürzere Consumer-Lesesperren, korrigierter Tennis-Saisonpfad, eng begrenzter historischer Tennis-Replay-Übergang, deduplizierte verlustfreie Fußball-Originalspeicherung. Sieben vorbestehende native QA-Fehler sind durch ehrliche Trennung historischer Prüffälle und aktueller Ausführung korrigiert; keine Pins, Ressourcen- oder Modellregeln gelockert. **Aktuelle native Neuqualifikation bleibt separat offen.**
- Die nach erneuter Freigabe zusätzlich übernommenen acht alten QA-/Recovery-Ziele sind nach vollständiger Linux-Wiederherstellung, geschütztem SSH-Export und kompletter lokaler Archivleseprüfung entfernt. Wiederherstellung: `C:/Projekt/BetBoy/.private-vps-backups/20260918-qa-retirement`, Archiv 1.632.517.697 Bytes; SHA256 `44d6f5202513b96156b4b33e0724561b30186a71da0ce32039d89a549d5b9366`. Manifest SHA256 `a025bce3460cfa83bb8148499d56907b77c1e76c9c32471adb13baeea987bc95`. Rund 2.43 GB dauerhaft frei; zusätzliche Server-Transportkopie ebenfalls entfernt. Runner, Wartungszustand und installierter Updater sind hashgleich; Produktionsdatenbanken und reguläre Backups unangetastet. Alte Drei-Kopien-Bereinigung ebenfalls erledigt, keine Bereinigung erneut starten.
- Frischer Reservecheck nach Bereinigung: 22.581.014.528 Bytes frei, 22.399.551.488 Bytes unveränderte Grundreserve nötig. **Codebereitstellung muss zusätzlich passen**; 181 MB Abstand sind keine garantierte Releasefreigabe. Nur den vorhandenen vertrauenswürdigen Updater verwenden; nicht direkt in Produktion pullen, keine Grenze reduzieren. Acht gelöschte Ziele/Prüfbelege stehen im neuen Retirement-Plan und den SDD-Berichten. Keine weitere Datenkopie ist durch diesen konkreten Acht-Ziele-Schritt freigegeben.
- **Fachlich nicht fertig:** Fußballplan Tasks 2/3 (kausaler Live-/B1-Anschluss und Aktivierung), Spieler-/Ersatz-/Belastungsdaten und Kohorten, echte Tenniszeitdaten, durchgängige Spielinkarnationen bei wiederverwendeten Provider-IDs, weitere Sportarten außer Cricket sowie empirische und Nutzerabnahme. 101 unterschiedliche exakt gebundene Tennis-Spiele sind keine 200 geeigneten unangetasteten Testevents. Keine neue Verletzungs-/Müdigkeitswirkung oder bessere Wettqualität freigegeben. Preise und Geldkonten unverändert.

Details: [Reparaturbericht](docs/audits/2026-09-18-context-repair-release.md). Die erneute allgemeine Design-/Worktree-/Pushfreigabe ist nicht erforderlich; erledigte Tasks nicht wieder beginnen. Timer berechnen, sie deployen keinen Code.

## Historischer Arbeitsstand 18.09.2026, 19:43 CEST

- **Nicht alles abgeschlossen.** Lokal `c44684d`, GitHub-main und VPS zuletzt `f3c2b60`. Sechs lokale Reparaturcommits noch nicht gepusht/deployed. Server um 19:36 CEST: App/Caddy aktiv, interner Healthcheck `ok`; letzter Wettfinderlauf 19:07–19:15 CEST erfolgreich. Kein neuer erfolgreicher Tennis-Gesamtlauf behauptet.
- Software fertig: Consumer-Lesetransaktion verkürzt (`185812e`), WTA/ATP-Quellenpfad repariert (`b342b02`), exakte historische Tennis-Replays erhalten (`0b529cf`), verlustfreie deduplizierte Fußball-Originalspeicherung samt inklusiver Grenze (`49ad632`, `0df6707`). Alle Funktionstasks und ihr Gesamtdiff unabhängig ohne Befund geprüft. Zahlen/Belege im [Reparaturbericht](docs/audits/2026-09-18-context-repair-release.md).
- Sieben Gesamtregressionsfehler waren bereits am exakten vorherigen Stand reproduzierbar: historische native Pins wurden mit inzwischen geänderten QA-Eigentümerdateien vermischt. `c44684d` trennt historische Prüffälle von der echten aktuellen Ausführung. 337 betroffene Tests bestanden, 54 Skips; native Pins, Eigentümer und Grenzen unverändert. **Aktuelle native Neuqualifikation bleibt offen**, kein anderer Name für einen zugelassenen aktuellen Lauf.
- Finaler Gesamttest läuft seit 19:40:14 CEST auf eingefrorenen Quellbytes, ohne `maxfail`: Sitzung `65907`, Log `output/playwright/full-suite-final-20260918-39b5c281.log`, isolierter Testpfad `C:/Projekt/BetBoy/.qa-final-20260918-39b5c281`. Gleichzeitig unabhängiger QA-Review unter `.superpowers/sdd/2026-09-18-native-qa-portability/task-1-review.md`. Noch keinen grünen Gesamtabschluss ableiten; keine Source-Änderung während des Laufs.
- Bereits genehmigter Drei-Kopien-Export und deren Bereinigung sind erledigt, nicht wiederholen. **Zusatzfreigabe durch „alles“ am 18.09., etwa 19:48 CEST:** die acht zuvor genau angefragten QA-/Recovery-Ziele geschützt archivieren, vollständig wiederherstellen/prüfen, lokal sichern und erst dann entfernen. Plan `2026-09-18-approved-qa-retirement.md`; privater lokaler Zielordner bereits angelegt, noch kein Transfer/Löschen. Letzter Reservefehlbetrag 2.239 GB vor Codebereitstellung; die acht Ziele garantieren noch keine ausreichende Reserve. Keine produktive Datenbank, reguläre Sicherung oder weitere Kopie entfernen.
- Nach grünem Gesamtlauf und abgeschlossenem Review: nur eigene Quell-/Test-/Plan-/Handoffdateien committen, unverändertes GitHub-main prüfen, `main` fast-forwarden und regulär pushen. Keine erneute allgemeine Push-/Worktree-/Designfreigabe nötig. Neues Deployment erst bei ausreichender echter Reserve über den installierten vertrauenswürdigen Updater. Timer deployen nicht.
- Fachlich offen: Fußballplan Tasks 2/3 (echter Live-/B1-Anschluss und Aktivierungsprüfung), Spieler-/Ersatz-/Belastungsdaten und Kohorten, tatsächliche Tenniszeitdaten, durchgängige Spielinkarnationen bei wiederverwendeten Provider-IDs, weitere Sportarten außer Cricket und empirische/nutzersichtbare Abnahme. Es gibt 101 verschiedene exakt gebundene Tennis-Ergebnisse, keine 200 geeigneten unbenutzten Testevents. **Keine neue Verletzungs-/Müdigkeitswirkung oder bessere Wettqualität nachgewiesen.**

## Historischer Zwischenstand 18.09.2026, 18:41 CEST

- **Nicht alles erledigt; neue Reparaturen noch nicht deployed.** Produktivstand und GitHub-main weiterhin `f3c2b60`; aktive Reparaturkopie `codex/context-capacity-recovery-20260910` ist weiter. App/Caddy und interner Healthcheck zuletzt 18:28 CEST erfolgreich gelesen. Keine Produktionsänderung durch die folgenden lokalen Tasks.
- `185812e`: tatsächlicher Karten-Leser-Konflikt repariert; unveränderliche Leseabbilder verlassen die SQLite-Transaktion vor CPU-Prüfung. 472 betroffene Tests bestanden/5 Skips; unabhängiger Taskreview ohne Befund. Andere lange Inventurleser bleiben separat offen.
- `b342b02`: WTA/ATP-Saisonquelle auf veröffentlichten HTTPS-Pfad korrigiert, 159 betroffene Tests bestanden/3 Skips. Ein echter isolierter WTA-Aufbau mit vorhandenen öffentlichen Daten funktioniert: 1110 Spielerinnen, Ergebnisstand12.09.2026,7025 bestehende Kalibrierungsbeobachtungen,5.95s. Keine Veröffentlichung, kein Wirkungstest; vier offene openpyxl-Hinweise dokumentiert.
- Wichtiger Nachfolgefehler vor Deployment entdeckt: `tennis/data_loader.py` gehört zur gespeicherten Original-Codeidentität. Alte Originale würden allein wegen der URL-Änderung scheitern. Exakte historische ATP/WTA-Fälle reproduziert; eng begrenzter vollständiger Sechsdatei-Versionsübergang gerade in Implementierung, Plan WTA Task2. Keine alte Prognose umschreiben und keine Hashprüfung pauschal lockern.
- `49ad632` plus `0df6707`: verlustfreie deduplizierte Fußball-Originalspeicherung fertig, inklusive korrigierter exakter4MiB-Grenze. Betroffener Erstlauf356passed/4skip, Fixlauf93passed/4skip; unabhängiges Nachreview SPEC/QUALITY PASS. Synthetischer380-Zeilen-Fall:826589Bytes expandiert,230689Bytes einmaliger Nutzinhalt, unveränderte Folgeberechnung271Bytes. Das ist ein Speicherbaustein, **noch keine Live-Scanneranbindung oder aktivierte Verletzungswirkung**. Fußballplan Task1 abgeschlossen,Tasks2/3 offen.
- Frische Tennis-Ergebnisinventur:995 Originalpublikationen,122 unterschiedliche native Paarungsidentitäten,101 verschiedene exakt outcome-gebundene Spiele(2ATP/99WTA). Keine weiteren abgeschlossenen Fälle aus vorhandenen normalisierten Statusdaten sicher nachbindbar. Fehlende Gewinnerbelege und wiederverwendete Provider-IDs bleiben explizit ungeklärt; kein künstliches Hochzählen wiederholter Originale. Weitere elf Identitäten zuletzt geplant/laufend.
- Die bereits genehmigte Drei-Kopien-Bereinigung und der geschützte Export sind abgeschlossen; nicht wiederholen. Acht **zusätzliche** alte QA-/Recovery-Ziele (2.432.557.056 Bytes) wurden zur geschützten Archivierung/Wiederherstellungsprüfung/Entfernung angefragt, noch keine Antwort. Reserve während laufendem Wettfinder: 22.314.248.192 Bytes nötig, 18.987.212.800 frei, 3.327.035.392 fehlend plus Codebereitstellung. Der zusätzliche Verlust ist read-only geklärt: PID560381 im Wettfinder hält fd3 einer bereits entlinkten temporären Datei, 1.182.539.776 Bytes. Kein neuer dauerhafter Bestand; kein Pfad zum Löschen, keinen Prozess für Speicher beenden. Nach natürlichem Abschluss Reserve erneut prüfen. Acht Ziele noch nicht verarbeitet, keine Schutzgrenze verändert.
- Nächster Softwareabschluss: historische Replay-Kompatibilität fertigstellen/reviewen, einmalige volle aktuelle Suite, Gesamtreview, dann gezielter Commit/Push. Serverrelease erst mit ausreichend echter Reserve und vollständiger Freigabe. Nochmalige ursprüngliche Spezifikations-, Worktree- oder allgemeine Push-Freigabe nicht erforderlich.
- Fachlich weiter offen: Fußball-Live-Original/B1-Anschluss, ursprüngliche Spieler-/Ersatz-/Belastungsdaten und Kohorten, tatsächliche Tenniszeit-/Belastungsdaten, durchgängiger Fixture-Inkarnationsvertrag, weitere Sportarten außer Cricket, eigenständige Effektqualifikation und Nutzerabnahme. Mindestens200 unabhängige unangetastete Testevents in drei Zeitblöcken plus getrenntes Training/Tuning bleiben erforderlich;101 Spiele sind kein Qualitätsnachweis. Keine Gesamtfertigmeldung.

Belege lokal: jeweilige `.superpowers/sdd/2026-09-18-*/`-Ledger, `output/playwright/wta-isolated-build-20260918.md`, `tennis-replay-locator-compatibility-20260918.md`, `tennis-outcome-coverage-inventory-20260918.md`, `release-reserve-inventory-20260918.md`. Alte ungetrackte Ausgaben/QA-Verzeichnisse unverändert erhalten.

## Fortsetzung 18.09.2026, 17:50 CEST – hat Vorrang vor alten Angaben

- Release abgeschlossen: Lokal, GitHub-main und VPS auf `f3c2b6083b8bcf78014a26302beb3afd97b8aaf9` (Funktionsstand `afc8a10`). App/Caddy aktiv, interner und öffentlicher Healthcheck geprüft; sieben reguläre App-Timer plus separater Retention-Timer geplant. Frische VPS-Leseprüfung um 17:44 CEST bestätigt Commit und internen Healthcheck. Alte fehlgeschlagene Dienste nicht zurückgesetzt.
- Die drei ausdrücklich freigegebenen verwaisten Prüfkopien wurden nach vollständiger Archiv-/Wiederherstellungsprüfung entfernt. Geschützte lokale Wiederherstellung: `C:/Projekt/BetBoy/.private-vps-backups/20260918-release-recovery`; Archiv und Manifest geprüft. Nur die zusätzliche Server-Transportkopie wurde anschließend entfernt. Produktionsdatenbanken und reguläre Backups blieben erhalten. Diese Bereinigung nicht wieder beginnen.
- Nach dem Release: 489 neue Belege, davon 151 Tennis-Ergebnisbelege für 101 verschiedene Spiele (2 ATP, 99 WTA); 338 Status-/Belastungsbelege separat. 850 frühere Originalpublikationen gebunden, **nicht** 850 unabhängige Testspiele. Probe bleibt fachlich teilweise vollständig; Bindungsprüfung ohne Fehler, kein kompletter Quellen-/Replay-/Qualitätsnachweis.
- Echter Wettfinderlauf 17:08 bis etwa 17:19 CEST erfolgreich, 81 Modellprognosen, 0 vollständig bestätigte Tipps. Keine neue Verletzungs-/Müdigkeitswirkung freigegeben.
- Konkurrierender Ergebnisschreibversuch scheiterte zuvor an `database is locked`; ruhender Wiederholungsversuch erfolgreich. Ursache im echten Karten-Leser reproduziert: CPU-Prüfung/Projektion hält eine Lesetransaktion. Bootstrap allein zu überspringen behebt es nicht. Reparatur läuft im vorhandenen Worktree; Plan `docs/superpowers/plans/2026-09-18-context-consumer-lock.md`. Weitere Langleser und physische Snapshot-Dauer bleiben separat zu prüfen.
- WTA-Ursache frisch geklärt: alter Downloadpfad 404; Upstream veröffentlicht einen neuen HTTPS-Prefix. Aktueller Payload: 2075 Zeilen bis 12.09., bestehende Inhalts-/Regressionsprüfungen bestanden. Noch kein Codefix/Produktivrefresh aus dieser reinen Quellenprüfung. Plan `docs/superpowers/plans/2026-09-18-wta-source-locator.md`.
- Fußball-Live-Original-/Provenienzanschluss wird konkretisiert; noch keine zusätzliche Wirkung aktiv. Tennis Abstract enthält tatsächliche Dauer für eine Teilmenge, der bestehende Loader verwirft sie. Keine tatsächliche Endzeit daraus ableiten. ATP-Turnierdatum bleibt kein Matchdatum.
- WTA `183854` ist als tatsächliche Provider-ID-Wiederverwendung geklärt: zuerst native Teilnehmer `2731/6769`, später `2731/2441`. Kein bloßer Terminwechsel. Die alte Prediction 1409 und ihre Revision blieben korrekt unverändert/offen; kein falsches Endergebnis zugeordnet. Eine durchgängige neue interne Spiel-Inkarnation für die Ersatzpaarung ist noch zu implementieren (Shadow, Refresh, Originale, Outcome, Settlement gemeinsam), nicht die Identitätsprüfung lockern. Diagnose `output/playwright/wta-183854-identity-20260918.md`.
- Consumer-Lock-Fix `185812e` lokal committed, unabhängig ohne Befund geprüft; 472 betroffene Tests bestanden, 5 bestehende Skips. Noch nicht gepusht/deployed. Gesamte aktuelle Testsammlung: 10062 Tests erfolgreich gesammelt; Sammlung ist kein bestandener Testlauf.
- WTA-Locator-Fix `b342b02` ebenfalls lokal committed und unabhängig ohne Befund geprüft; 159 betroffene Tests bestanden, 3 bestehende Skips. Echte isolierte HTTPS-Probe erfolgreich mit 2075 Zeilen bis 12.09.2026. Noch kein Produktivrefresh/Training und kein Deployment daraus ableiten.
- Der nächste sichere Release benötigt beim frischen Reservecheck rund 2,14 GB mehr freien Platz plus Codebereitstellung. Keine erneute alte Bereinigung oder pauschale Backup-Löschung; weitere alte Prüfkopien werden nur inventarisiert. Live-Kontextdatenbank: 1.939.492.864 Bytes. Neuer Fußball-Originalpfad muss feste Inhaltsblöcke wiederverwenden; vollständige Historienkopien pro Berechnung würden erhebliche vermeidbare Datenmengen erzeugen.
- Acht konkrete weitere Prüf-/Recovery-Bestände (2.432.557.056 Bytes) sind inventarisiert; geschützter Export, vollständige Wiederherstellungsprüfung und anschließende genaue Entfernung wurden angefragt, **noch nicht freigegeben oder ausgeführt**. Details `output/playwright/release-reserve-inventory-20260918.md`. Alte drei Ziele und altes Exportarchiv nicht verwechseln. Selbst nach Freigabe Reserve frisch prüfen, nicht trotz zu wenig Platz deployen.
- Fußball-Originalspeicherung wird als verlustfreier fester Inhaltsblock-Speicher implementiert; Plan `docs/superpowers/plans/2026-09-18-football-live-originals.md`, Task 1 im zugehörigen SDD-Ledger. Live-Scanneranbindung und Budget-/Aktivierungsprüfung folgen separat; noch keine neue Original-Publikation auf dem VPS aktiv.
- Weiter offen: vollständige Konkurrenz-/Tageslaufprüfung, WTA-Identitätsfall, Fußball-Live-Integration und verwendbare Spieler-Kohorten, echte Zeit-/Belastungsdaten, weitere Sportarten außer Cricket, empirische und Nutzerfluss-Abnahme. Basisprognosen bleiben unabhängig vom Preis sichtbar. Keine Gesamtfertigmeldung.

Aktuelle Arbeitsbasis: `output/playwright/context-outcome-release-20260916.md`, `output/playwright/context-lock-rootcause-20260918.md`, `output/playwright/tennis-data-coverage-20260918.md`. Ungetrackte Diagnosen erhalten; verbindliche Restliste unten bleibt offen, soweit hier nicht ausdrücklich als erledigt belegt.

## Historische Übernahme 18.09.2026, 16:00 CEST

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
