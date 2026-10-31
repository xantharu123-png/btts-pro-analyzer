# BetBoy - Übergabe auf einen neuen PC

## 31.10.2026 08:36 – Release 20261031-1 live: Shadow-Tipps ohne Quote, Policy v11 (PR #64)

Owner-Auftrag 31.10.2026 (`docs/audits/2026-10-31-shadow-tipps-ohne-quote.md`): Tipps unter der Mindestquote
bleiben draussen, Tipps ohne auffindbare Quote kommen trotzdem. Befund vorher: Freitag 30.10. 42 Shadow-Spiele,
3 Tipps; der Shadow prüfte nur 18 von 46 Tormärkten und verlangte immer eine Bet365-Quote. Regel v11: alle 46
Tormärkte; Bet365-Tipp ab 1,30 wie bisher; sonst bestplatzierter Kandidat ohne frische Quote unter 65 %
Modellwahrscheinlichkeit (`shadow_unpriced`, nur Treffer/Fehlschläge, nicht in Rendite und 1000er-Prüfstufe).

Nach Owner-Freigabe PR #64 gemergt und um 08:36 CET als **`472846d`** per No-Backup-Fast-forward von `caedd05`
ausgerollt (Helfer `output/release-20261031-1/deploy.sh`, abgeleitet vom Helfer 20261030-3, 10 Pfade, Code nur
`shadow_clv_automation.py`; Offline-Prüfung lokal und auf dem Server ok; nur App-Neustart PID 1415177→1421292;
Healthchecks ok, Snapshots unverändert, kein Backup, Einheiten unverändert). Prüfung danach (`verify-01.log`):
Shadow 08:42 `success`/Exit 0, Policy v11, Konstanten 24 h/24 h/v11/1,3/0,65, Tabelle `shadow_unpriced` angelegt,
Website HTTP 200, kein neuer Alarm. Der erste Lauf hatte 2 Spiele ohne Bet365-Quote (Liga 274), deren 8 bzw. 11
Kandidaten alle bei 65 % oder höher lagen: kein Tipp.

Messung danach (`price_by_probability.sh`, 9589 App-Fussballprognosen mit Bet365-Quote): Anteil Quote ≥ 1,30 bei
Modellwahrscheinlichkeit 55–60 % 93 %, 60–65 % 88 %, 65–70 % 75 % (Median 1,36), 70–75 % 46 % (Median 1,28),
75–80 % 31 %. Die 65-%-Grenze der App ist für 1,20 gesetzt; für 1,30 liegt der Median-Umschlag bei etwa 70 %.
Offen: Owner-Entscheid, ob die Modellgrenze im Shadow auf 70 % geht (neue Policy). Die Sonntagsprüfung
(1.11. 08:00) liest jetzt die aktuelle Policy (`output/release-20261031-1/check_shadow.sh`).

## 30.10.2026 20:47 – Release 20261030-3 live: Shadow-Altersgrenze 24 Stunden, Policy v10 (PR #62)

Owner-Entscheid 30.10.2026 (`docs/audits/2026-10-30-shadow-altersgrenze-24h.md`): Öffnungs- und Schlussquote dürfen
einen Bet365-Stand bis **24 Stunden** Alter tragen, weil viele Spiele nur den nächtlichen Stempel haben (am 30.10.
bei 6 von 8 Spielen ohne „aktuelle“ Quote 16 bis 18,5 Stunden alt); ein anderer Buchmacher hilft nicht, der Stempel
gilt je Spiel für alle. `results.by_opening_age` trennt abgerechnete Tipps nach bis 12 h / über 12 h / unbekannt.
Policy **`shadow-model-first-v10`**; die 1000 Tipps zählen unter v10 neu.

Nach Owner-Freigabe um 20:47 CET als **`caedd05`** per No-Backup-Fast-forward von `d43c81a` ausgerollt (Helfer
`output/release-20261030-3/deploy.sh`, abgeleitet vom Helfer 20261030-2, 14 Pfade, Code `clv_tracker.py` und
`shadow_clv_automation.py`; Offline-Prüfung 24 h/24 h/v10 ok; nur App-Neustart PID 1413458→1415177; Healthchecks ok,
Snapshots unverändert, kein Backup, Einheiten unverändert; Fenster 258 s vor dem nächsten Shadow-Lauf). Prüfung
danach (`verify-01.log`): Shadow 20:52 `success`/Exit 0, Policy v10, Urteil „Shadow-Evidenzaufbau: 0/1000“,
Konstanten 24 h/24 h/v10/1,3, Website HTTP 200, kein neuer Alarm.

Offen: erste v10-Tipps am Wochenende beobachten (Anzahl je Kohorte, Alter der Öffnung, `by_opening_age`).

## 30.10.2026 20:08 – Release 20261030-2 live: Bewertung nach Gewinn und Verlust zur geholten Quote (PR #60)

Owner-Entscheid 30.10.2026 abends (`docs/audits/2026-10-30-shadow-bewertung-ergebnis.md`): Die Quote wird einmal
geholt; bewertet wird, ob der Tipp zu dieser Quote gewinnt. Massgeblich sind `results` (abgerechnete Tipps ohne
Schlussquoten-Pflicht, Trefferquote, Rendite je Tipp mit HAC-Intervall, Vergleich mit der No-Vig-Wahrscheinlichkeit
zur Öffnung) und `verdict` (`_result_verdict`, Prüfstufe nach **1000** abgerechneten Tipps); Schlussquote und CLV
laufen im Hintergrund (`clv_verdict`). Hybrid gegen Legacy über `hybrid_cohort.paired_results`. Auswahl und Policy
`shadow-model-first-v9` unverändert.

Nach Owner-Freigabe um 20:08 CET als **`d43c81a`** per No-Backup-Fast-forward von `fd29323` ausgerollt (Helfer
`output/release-20261030-2/deploy.sh`, abgeleitet vom Helfer 20261030-1, 8 Pfade, Code nur
`shadow_clv_automation.py`; Offline-Prüfung ok; nur App-Neustart PID 1408795→1413458; Healthchecks ok, Snapshots
unverändert, kein Backup, Einheiten unverändert; Fenster 232 s vor dem nächsten Shadow-Lauf). Prüfung danach
(`verify-01.log`): Shadow 20:12 `success`/Exit 0 (Status `partial` nur durch Datenstatus), `evaluation`
`won_lost_at_opening_quote`, Urteil „Shadow-Evidenzaufbau: 0/1000“, Konstanten 12 h/12 h/v9/1,3, Website HTTP 200,
kein neuer Alarm.

Befund Tippmenge 30.10. (`output/release-20261030-1/verify-03-funnel.log`, `verify-04-hybrid.log`, nur lesend):
42 Shadow-Spiele in 26 Ligen (Wochentage 14–42, Wochenende 117–143); grösster Verlust sind Spiele mit glaubwürdigem
Kandidaten, aber ohne Bet365-Quote bei API-Football (mindestens 8 Spiele, je bis zu 5 Wiederholungen); die
1,30-Grenze griff wenige Male. Hybrid: Vorbereitung fehlerfrei (`builds_failed` 0, `fixtures_without_artifacts` 0),
seine Kandidaten lagen nur auf Spielen ohne Bet365-Quote; v9 bisher 2 Legacy-Tipps (1565519 Unter 3,5 zu 1,44,
1570442 Unter 4,5 zu 1,30), Hybrid 0.

Offen: Vorschlag an den Owner, bei fehlender Bet365-Quote die Quote eines anderen Buchmachers zu nehmen (neue
Policy); erste abgerechnete v9-Tipps in `results` beobachten.

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

## 18.10.2026 – Spezifikation freigegeben, Plan erstellt; noch kein Produktpatch

Aktuelle ausdrückliche Antwort: „Spezifikation freigegeben; Umsetzungsplan erstellen“.
`docs/superpowers/plans/2026-10-18-football-training-execution.md` enthält sieben
testbare Aufgaben und Root-Selbstprüfung. Nächster Schritt: Nutzer prüft diesen
Plan, dann bereits gewähltes Unteragenten-/Review-Verfahren anwenden; nicht erneut
nach der Ausführungsmethode fragen. Keine Produktcode-/Quell-/Datenänderung,
Effektaktivierung, API-Abfrage, zusätzlicher Scan oder Sicherung dieser Planphase.

## 18.10.2026 – neuer Fußball-Trainingsauftrag, noch kein Produktpatch

Nur lesende Scope-/Datenprüfung durchgeführt. Drei Code-Audits bestätigen neue
Ausführungsgrenze zusätzlich zum Speicherfix: gleiche DB für Originale und
Trainingswriter, zu frühes Lesen finaler Ergebniskörper und bisher gesamter
Quellspeicher als D2-Prüfbereich. Kein bloßes Destination-Flag oder Guard-Entfernen.
Frische VPS-Metadaten ergeben 124 Original-Bindungen und null der abgefragten
Trainings-/Dataset-/Effekt-/Öffnungs-/Freigabe- und V2-Inventararten; keine Belege
für 200 unabhängige Final-Kontextfälle zusätzlich zu Train/Tune. Bodies und großer
öffentlicher Tagesreport nicht geladen; keine API, DB-Kopie, Sicherung oder Änderung.
Vorschlag `docs/superpowers/specs/2026-10-18-football-training-execution-design.md`
ergänzt den Speichervertrag. Status ausdrücklich: schriftlich freigegeben,
Umsetzungsplan oben zur Nutzerprüfung mit bestehendem Unteragenten-/Review-Verfahren.
Keine Effekte aktivieren oder bessere Wettqualität behaupten. Externe Diagnostik:
`output/football-training-20261018/metadata-live-01.log` und `metadata-live-02.log`.

## 18.10.2026 – chronologische Spielanzeige live abgeschlossen

Quellcommit `22af00bb79a444c3ba741b936f9ed2b8d00778a1` auf main und VPS,
18.10.09:35 CEST: No-Backup-Fast-forward von `b57b646`, exakt zwölf Pfade,
beide Offline-Smokes bestanden, nur App neu gestartet (1236110 → 1240541).
App/Caddy aktiv, beide Healthchecks `ok`, acht Timer aktiv/aktiviert und
Backup-Timer weiter aus. Snapshots, neun Jobstartstempel und beide Indexowner
beim Deploy unverändert. Keine Sicherung, DB-Kopie/-Änderung oder Extra-Scan.
Receipt: `output/chronology-20261018/deploy-live-20261018-0935.log` außerhalb Git.

Neueste Freigabe: überall nächstes Spiel zuerst, vollständiger Beginn aufsteigend,
unbekannte Termine zuletzt. Marktauswahl/-priorität im Spiel unverändert.
Produktpatch ausschließlich `tip_display_order.py`/`app.py`, fünf Testmodule
angepasst/ergänzt. 167 gezielte Tests bestanden; unabhängiger Quellreview ohne
Befund. Vollsuite abgeschlossen: 15.459 PASS/3 alte Sortier-FAIL/98 gleiche SKIP.
Nur drei weitere Test-Owner an die freigegebene Reihenfolge angepasst, IDs,
Fixtures, Zahlen und Schutzprüfungen erhalten; ganze Owner 172 PASS/Exit 0.
Exakte Zusammenführung: 15.462 PASS/98 gleiche SKIP, alle 15.560 aktuellen IDs
und alle früheren erhalten, keine offene Fehler-ID. Kein neuer einzelner grüner
Gesamtlauf; ursprüngliche FAIL-Belege erhalten. 834-Dateien-Vergleich zeigt nur
diese drei Teständerungen, keine spätere Produktänderung. Owner-Pins ausdrücklich
nach dem Lauf erfasst. Abschluss `output/chronology-20261018/owner-union-01/`.
Echte lokale Desktop-/Mobil- und Accordionprüfung bestanden, eigene Vorschau
danach beendet, keine Produktionsdaten/API-Verbindungen.
Veröffentlichung oben nachgewiesen; Basis war `b57b646`. Externe Belege und
getesteter No-Backup-Deployhelper in `output/chronology-20261018/`.
Die zwölf eigenen Pfade wurden explizit committed/gepusht und source-only auf
VPS aktualisiert. Abschlussdokumentation separat ohne erneuten App-Neustart ziehen.
Fremde `debug.log` und `output/audit-repairs/` blieben unberührt.
Keine Backups, Extra-Scans, Produktionsdatenkopien oder Bereinigungen.
Nicht mit der noch ausstehenden Freigabe des schriftlichen Football-Dataset-v2-
Vertrags vermischen. Fachliche Effekte bleiben offen, siehe darunter.

## 18.10.2026, morgens – Accountfortsetzung verifiziert

Lokal/GitHub/VPS `e081662` frisch bestätigt, App/Caddy aktiv, Health `ok`.
Regulärer Wettfinder unter neuem Code erfolgreich 03:35:31–04:09:55 CEST,
Shadow 07:52 erfolgreich. Kein neuer Sport-/API-Scan, Backup oder DB-Eingriff.
Seit Quellrelease 1.184 gespeicherte native Fußball-Marktanhänge für 62 Events;
noch kein finaler Qualitätsnachweis dieser neuen Events. Rein lesender
Marktvergleich jetzt 54 kategoriale Marktsätze/26 Events inklusive sechs Hockey-
Closings, kein belegter Vorteil; neue binäre Auswertungsgruppen weiterhin leer.
`output/source-repair-20261017/native-market-proof-02-after-daily.json` extern.
Hockey-Teilfehler konkret `source_partial`, bewusst vom operativen Gesamtfehler
getrennt, kein nachgewiesener Crash; ursprüngliche Einzelursache öffentlich
bereinigt und aus dem Report nicht rekonstruierbar. Tennis-Volljob des neuen
Codes weiter erst 19.10.00:05 nachweisen, keinen zusätzlichen Lauf starten.

Produktdateien unverändert. Neue Football-Dataset-v2-Architektur als nächster
kleiner Umfang vorgeschlagen (gemeinsame Referenzen, exakte Fallmitgliedschaft,
sequenzielle physische Projektion, bestehende Mathematik/D2 unverändert).
Richtung vom Nutzer freigegeben. Schriftlicher Vertrag unter
`docs/superpowers/specs/2026-10-18-football-stream-dataset-design.md` erstellt und
selbst geprüft; dessen Prüfung/Freigabe noch offen. Zusätzliche produktive
Ausführungs-/Persistenzgrenze in Abschnitt 5 ausdrücklich benannt: Speicherpatch
allein erlaubt noch keinen neuen Real-Kohorten-D2-Lauf. Keine Offline-Sperre umgehen.
POINT-Tennis braucht danach eigenen Effektvertrag, keine alten Serve-Fits auf
neue Verteilung anwenden. Details/Nachweise ganz oben in TODO_AKTUELL.md.

## 18.10.2026 – Quellen-/Marktquellrelease live, fachliche Restarbeit offen

Quellcode `c6fe02fdce07eae1e13368e98612c8b6bf569657` auf main und VPS live seit
02:12:48 CEST. Kanonisch bleibt `.worktrees/audit-repairs-20261013`, kein anderer
Checkout wurde stillschweigend aktualisiert. No-Backup-FF von `2f62e5e`, 45 Pfade,
Offline-Smoke und beide Healthchecks `ok`, App-PID 1222039 → 1236110; App/Caddy
aktiv, acht Timer aktiv/aktiviert. Beide Indexowner rohbytegleich,
Prognose-Snapshots und neun Jobstartstempel beim Deploy unverändert. Keine DB-
Kopie, Migration, Installation, Bereinigung, neue Sport-/API-Abfrage oder Sicherung.
Receipt `output/source-repair-20261017/deploy-source-repair-01.txt` außerhalb Git.

Shadow getrennt beachten: schon vor dem Release um 02:02/02:12 `partial`/Exit 1,
fehlende frische Bet365-Providerbelege für 1550998/1550999 und zwei alte ungültige
CLV-Zeilen; bewusste Sperre alter/unvollständiger Evidenz, nicht neuer Appcrash.
Enge Nachprüfung: beiden Altzeilen (Fixtures 1528908/1495965) fehlen ausschließlich
Schlussquote und ihre drei Herkunftsfelder; übrige geprüfte Ergebnis-/Profitfelder
konsistent. „Malformed settlement“ beweist hier keine falsche Geldbuchung.
Keine alten Zeit-/Gegenquoten erfinden oder Historie zur Freischaltung löschen.

Nicht erledigt: numerisch qualifizierte Verletzungs-/Wetter-/Müdigkeitseffekte,
Mehrfall-Fußballdataset/-fitter, spätere PLAYER_LOAD-v3-Quellen und aktueller
POINT-Tennis-Effektvertrag. Native neue Gegenpreispaare und vollständiger neuer
regulärer Tennislauf am 19.10., 00:05 CEST, erst künftig nachweisen, ohne Extra-Scan.

### Chronologie der abgeschlossenen Prüfung vor dem Release

Abschluss 02:10 CEST: großer unveränderter 13-Modul-Lauf **381 PASS/0 SKIP**,
Exit 0, 3.490,58 s. Exakter Belegabgleich vollständig: **15.459 PASS/98 gleiche
SKIP**, alle 15.557 aktuellen und alle 15.495 ursprünglichen Haupt-IDs enthalten.
Das ist ursprüngliche Vollsuite plus spätere ganze Ownernachtests, kein frisch
wiederholter grüner Gesamtlauf. Der ursprüngliche Sourcepin-WholeSource-Wrapper
bleibt FAIL/INCOMPLETE; seine 103 Fälle gelten nur im separat geprüften Umfang.
`output/source-repair-20261017/followup-receipt-merge-final.json` außerhalb Git.
Finaler unabhängiger Quellreview: 834 Dateien bytegleich zur Abschluss-Collection,
45 Releasepfade, sechs Tennis-Kernmodule und zwei Indexdateien unverändert.
Anschließender Commit/Push/No-Backup-FF-Deploy ist oben tatsächlich belegt.
Fachliche Effekte weiterhin offen: Mehrfall-Fußballtraining,
PLAYER_LOAD-v3-Nationalteam-/Transferumfang und aktueller POINT-Tennisvertrag
fehlen zusätzlich zum ausreichenden unangetasteten Qualitätsnachweis.

Kanonischer Checkout unverändert `.worktrees/audit-repairs-20261013`, lokale
Quellen-/Marktbasis committed als `bc6e7f2`, GitHub/VPS zuletzt bestätigt
`2f62e5e4fe57ac233847a8dbb52e8c35584aff98`. Neue Basis noch nicht gepusht/deployed;
zusätzliche Tennis-Live-/Fußball-Headeranschlüsse in getrennter Integration. Aktuelle
Aufgaben ganz oben in TODO_AKTUELL.md; technische Grenzen in
`docs/audits/2026-10-17-source-repair-v2.md`. Besonders: neue v2-Speicherabrechnung
ist ein ausdrücklich anderer Umfang, kein Zurücksetzen alter Reservierungen;
frühere Tennis-Fallbackproben bleiben FAIL, nicht umbenennen. Bestehender
Indexbesitzer hat mit unveränderten Grenzen in Aufruf 32 tatsächlich READY
erreicht (Originaltail 2.639.584). Neuer expliziter Livepfad: 191 Ownertests und
alle 72 echten Originale im Quellen-/Feature-Replay bestanden (870.479 Zeilen,
120.207.043 Bytes Ausgabeheap unter 128 MiB, 621,740 Sekunden). Keine neue
Sportprognose/Publikation oder vollwertige A1-Zustandsverifikation aus diesem
reinen Replay behaupten. Beide Caller lokal explizit angeschlossen, deren
vollständige Ownerprüfung abgeschlossen; auf dem VPS noch nicht umgestellt.
Nachtrag: richtige Offline-Ownerprüfung abgeschlossen, 338 PASS/0 SKIP und
keine alten IDs entfernt. Echte lokale Indexfixtures statt READY-Mock. Die
gemeinsamen drei Sourcepin-Owner haben 103 PASS; ihr unveränderter äußerer
WholeSource-Wrapper bleibt wegen zweier separat getesteter Callerdateideltas
FAIL/INCOMPLETE, nicht als vollständig unveränderte Vollquelle umdeuten.
Finaler unabhängiger Review ohne neuen Produktbefund, Deployhelper 7 PASS und
exakte 45-Pfad-Allowlist. Finale Collection 15.557 eindeutige IDs, alle früheren
15.500 erhalten. Große13er-Fußballrunde und letzte Caller-Nachbarn abgeschlossen.
Alter regulärer Tageslauf erfolgreich 00:05:02–00:36:48/Exit 0, 72 verarbeitet,
64 neue Prognosen, unresolved_outcome_events=0; Kontext teilweise. Kein Beweis
für den noch unveröffentlichten neuen Code. QA03 komplett plus 439 Quoten-
Ownernachtests, zusammen 15.402 PASS/98 gleiche SKIP; Original fünf FAIL erhalten.
Neuer Fußball-Headerowner samt echtem Fit/D2 24 PASS und weitere vier ganze
Legacy-/Readiness-/Opponent-/LOAD-Owner 91 PASS; große13er-Runde 381 PASS.
Keine Effekte als empirisch fertig oder bessere Wettqualität darstellen.
Fremde ungetrackte `debug.log`, `output/audit-repairs/` erhalten. Keine Backups,
DB-Kopien, Bereinigungen oder zusätzliche Sport-/API-Scans. Erst verifizieren,
dann explizit committen/pushen/No-Backup-Deploy, keine pauschalen Git-Aktionen.

## 17.10.2026 – aktuelle Fortsetzung: Marktvergleich und Daten-Deduplizierung

Kanonisch bleibt `.worktrees/audit-repairs-20261013`. Quellcommit
`702f594ed22d0d6b18dff5f8946145f5f27f0898` auf main/VPS live am 17.10.
um 21:22:44 CEST. No-Backup-FF, Offline-Smoke, App-PID 1218486 → 1222039,
beide Healthchecks `ok`, App/Caddy aktiv, alle neun geprüften Jobstartstempel und
Prognose-Snapshots beim Deploy unverändert. Abschlussdoku danach ohne Neustart.
Neue Marktvergleich-/Closing-/Tennis-Final-Reparatur vollständig geprüft:
15.280 PASS/98 gleiche SKIP/147 Untertests, alle 15.318 alten IDs + 60 neue erhalten.
Initialer vollständiger FAIL mit 19 Fehlern/Exitcodes [0,1,1,1] bleibt erhalten.
Nur Quoten-Testdaten-Uhr korrigiert und Regression ergänzt; fünf ganze Owner
danach 521 PASS/3 gleiche SKIP. Produktquellen unverändert gegenüber Vollsuite.
Abschlussprüfer bestätigt exakt 15.378 JUnit-Haupt-IDs, keine Doppelungen/Lücken;
`output/context-effects-20261017/verification-summary.json`. Tatsächlicher Deploy:
`output/context-effects-20261017/deploy-market-context-01.txt`.
Gezielte 393 und 236 Tests sowie unabhängige Reviews grün; nicht addieren.
Aktuelle vollständige Aufgaben/Abgrenzung stehen ganz oben in TODO_AKTUELL.md.

Frischer rein lesender Produktionsvergleich 19:23:25 UTC: 48 Marktgruppen/20 Fußball-
spiele (v13: N=10, aktuelle v14: N=8, v12: N=2), null Closing-Beobachtungen und bisher keine
vergleichbaren Tennis-Gegenpaare. Kein robuster Qualitäts-/Renditebeleg. Neue
Erfassungszweige erst in künftigen regulären Läufen produktiv nachzuweisen.
Quelle: `output/context-effects-20261017/production-market-comparison-702f594.json`.

Wichtig: Effekte sind NICHT fertig. Fußball8 vollständigeOriginale,7 davon am
Quellenpoollimit; Lebenszeitreservierung128MiB erschöpft. Tennis1.000 native
Finals sind gemischteBaselinegenerationen, nur52 aktuellePOINT-Joint-Artefakte;
realeMerkmalsleser weiterhin blockiert. Bericht
`docs/audits/2026-10-17-context-activation-readiness.md` ist frisch produktiv
nachgewiesen. Keine frei erfundenen Effekte/Endzeiten oder gelockerten Gates.
NeueFinal-Deduplizierung wirkt nur mit bekanntem gebundenem Gewinner, nicht
auf sämtliche alteDraws; historischeZeilen bleiben unangetastet.
Noch keine Backups, Datenbankkopien, Bereinigungen oder zusätzlichenAPI-Scans.

## 17.10.2026 – aktueller Abschluss: Reparaturquellen live

Source `e8a32b83d6c0510adb798ab3c96c4a63704a4d5d` main/VPS am19:52:50CEST,
No-Backup-FF, Offline-Smoke, Apprestart1215661→1218486, beideHealthchecks`ok`.
Alle neun Jobstartstempel/Prognose-Snapshots beim Deploy identisch. Drei neue
Keys im tatsächlichen App-Prozess aktiviert/geprüft, keine Werte ausgegeben.
15.220PASS/98gleicheSkips/147Untertests inkl.expliziter106erCSS- und11erAST-
Whitespace-Owner-Rechecks; alle15.233altenIDs+85neuegenaueinmal.
Live-Kernansicht1440/390geladen,keinOverflow/relevanterAppfehler; vollständige
LiveNavigation/Accordion/5–10INCOMPLETE. Isolierter tatsächlicherRenderer mit
diesenInteraktionengrün. AbschlussdokumentationfolgtDocs-onlyohneNeustart.

Wichtig neuerVPS-Datenbefund(nurlesend):87.320Forecastzeilen für1.444Ereignisse,
5.306Ergebniszeilen,56.162Entryquotes,0Closings;Football779Ereignisse.
Tennis2.429Prognosen,0beidseitigeEntry-/Closingpaare. Nicht mitlokalenLeer-
beständenverwechseln. NächsterSchrittfachlich: vorhandeneEntrybelegekausal/
marktgebundenauswerten, fehlendevollständigeGegen-/Closingpreisegezieltschließen.
KeineRendite-/Kontexteffektfreigabeerfunden;79-ID-MatrixenthältechteRestarbeit.
KeineBackups/neuenSportscans/Migrationen/Bereinigungen. Fremdeungetrackte
`debug.log` und `output/audit-repairs/` erhalten. AktiverCheckoutunverändert.

## 17.10.2026 – Fortsetzung: vollständige QA abgeschlossen, Release folgt

Aktiv weiterhin `.worktrees/audit-repairs-20261013`; Stand18:25darunterhistorisch.
Gesamtnachweis15.220PASS/98gleicheSkips/147Untertests: Originalvollsuite hatte
einen alten CSS-nowrap-TestFAIL, alleinigeErwartungskorrektur+vollständiger
106er Owner-Recheck grün, alle Produktquellen bytegleich. Alle 15.318 IDs genau einmal,
alte15.233IDs vollständig+85neue. `output/claude-recheck-20261017/final-summary.json`.
Renderer1440/390/320mitMaus/Tastaturgeprüft; keinevolleLive-/Geräteabnahme.
VPS4f2af4e vorReleasegesund,regulärerShadow19:42Exit0; keinneuerScan/Backup.
No-Backup-Deployhelperneu+31Pfadallowlist+neunJobs; fehlenderoptionalLegacycache
istbisherigeStartlogik(lokaleML-PrüfungverwirftamGate), keinneuesFeature/Scan.
AlsNächstesQuellcommit/main/gezieltesVPS-FF/Neustart/Health/SHA/Livebrowser.
Alle79Audit-IDsmitoffenenModell-/Markt-/LaunchgrenzenbleibeninderAuditmatrix.

## 17.10.2026 – aktuelle Fortsetzung: beide Claude-Audits

**Accountwechsel, Stand 18:25 Europe/Zurich.** Keine weitere Implementierung
oder Veröffentlichung in diesem Turn. Vier Offline-Volltestgruppen laufen;
PC laufen lassen. Oberster TODO-Unterabschnitt enthält exakte Sessions,
Logpfade, Report-Befehl, ID-Abgleich, Testzahlen und Releasewarnungen.
Keine zweite Suite starten, bestehende Quellenhashes unverändert halten.
Sourceänderungen noch uncommitted; gesonderter Docscommit ist kein Code-Release.

Aktiver Checkout `.worktrees/audit-repairs-20261013`, Basis `044a06fb`.
Hauptcheckout weiterhin alte fremde WIP, nicht resetten/pauschal stagen.
Alle79Befunde abgeglichen: `docs/audits/2026-10-17-claude-gegenpruefung.md`.
Begrenzte Korrekturen im Arbeitsbaum: richtiger sichtbarer statistischer Lead,
Quellen/Zurich/Labels, Tennis-Watch-/Wochenreport-Vertrag, Awarded, FT-Guard,
separate Residuenmessung, Daily3-Kalender, gemeinsamer Legacy-Cache-Dateischutz.
Originale/aktive Modellversionen/Geld-/Quotenregeln bewusst nicht umdefiniert.

Alle drei vom Nutzer erneuerten Schlüssel lokal ignoriert und in VPS-Env/INI
eingesetzt; andere Einstellungen erhalten, keine Werte ausgegeben. Je Anbieter
ein Authcheck HTTP200. App-Env-Aktivierung erst Neustart. Widerruf alter Werte
nicht allein daraus beweisbar. Kein Backup/Scan. VPS-Quellstand noch4f2af4e.

Gezielte Tests/echtes RED+unabhängige Reviews vorhanden. **Vollsuite noch im Lauf**:
`C:/Projekt/BetBoy/output/claude-recheck-20261017/full-qa-02`,15.318IDs, vier
native Offline-Gruppen. Nicht als fertig ausgeben. VorherigerZwischenlauf01
nach echtem Reviewer-Folgefund beendet und ausdrücklich INCOMPLETE erhalten.
Erst finalen Exit-/ID-/Skip-/Quellenhash-Abgleich, dann explizite Dateiliste
commit/main/VPS ohne Backup. Keine Bereinigung/Sportscans/Modelldatenmigration.

Offene Modell-/Marktnachweise, Launch-/CI-/Persistenz-/UX-Schulden stehen mit
allen IDs in der Matrix und im obersten TODO. Nicht „alle79behoben“ behaupten.
Torzeitmärkte bleiben separater freigegebener Funktionsauftrag mit schriftlicher
Spezifikation zur Freigabe; dieses Audit ist kein stiller Zeitmarkt-Neubau.

## 17.10.2026 – neuer Zeitmarkt-Auftrag, noch kein Produktivcode

Nutzer genehmigt Torzeit-Profil und kumulative 15/30/60/75-Minuten-Tore,
Teamtore und BTTS: historisch prüfen, exakte Quoten, Tests/main/VPS, ohne Backups.
Schriftliche Architektur-Spezifikation liegt in
`docs/superpowers/specs/2026-10-17-football-time-markets-design.md` zur Freigabe.
Erst danach Implementierungsplan; vorhandene 96/v14/40/Ticket-Verträge unverändert.
3 begrenzte echte Anbieterdiagnosen: native144/Yes-No/WilliamHill belegt;
30/60/75-Gesamt-/Team-/BTTS-Quoten nicht nachgewiesen. Einzelsegmente und
Ergebnisquoten sind kein Ersatz. Receipt außerhalb Git unter
`C:/Projekt/BetBoy/output/time-markets-20261017/`.
Keine Produktivänderung, neuer Scanner, Backfill, Sicherung oder Datenbereinigung.
Bestehende Hauptmarkt-Anzeigelücke und Kontext-/NHL-Restarbeiten bleiben offen.

## 17.10.2026 – Multigoal-Quotenabruf: aktueller Zusatzauftrag

Kanonisch `.worktrees/audit-repairs-20261013`, Basis`6ff4d260`, kein Backup/
zusätzlicher Sportscan. PaidAPI-Football aktiv;14 begrenzte Quellenanfragen.
Drei native Spiele vollständig1/1 ohne1–3/1–4/2–4; fünf gültige Datum-/Markt-
Abfragen leer. Nichtglobal verallgemeinern; ungültige unscopedQueries keinBeweis.
Roma–Genoa lieferte nativ349 „2or3goals“2,00/Bet365 (Anbieter09:18UTC), bislang
nicht im95Katalog. Nicht fälschlich einem anderen Bereich zuordnen.
Fetch ignorierte Folgeseiten: repariert, bounded20/Fixture, Budget/Deadline,
echte per-pageReceipts, gemeinsamer unveränderter Exact-/BookmakerParser.
Teil-/Containerfehler nicht alsAbwesenheit. Persistenz nurvier boundedFakten.
Zwei Review-P2 Uhr/Shape mit RED→GREEN korrigiert, Re-Review freigegeben.
Erster Vollsuite-Zwischenlauf15.119 kontrolliertINCOMPLETE beendet, weilNutzer
weitereVarianten/Statistik explizitfreigab; Logsbleiben. Endstandjetzt96Runtime/
46Torprojektionen, alte90/40/v14/alle95Werteunverändert; native3492–3exakt.
Kompakte5/10-Häufigkeiten(gesamt1–3/1–4/2–3/2–4undSieg+Bereich) ausbereits
validiertenErgebnissen, keineZusatzmodellchance. Normal/Daily3/15K/manuell/RisikoBet,
einmalproSpiel, keineJSON/Prosaübernahme. RisikoBetneueFaktorenerstregulärerLauf;
Altsnapshotsnichtneuinterpretiert. Original90/95-Fit-/Tickethashesunverändert.
Finaler Offline-Nachweis: 15.135 PASS, 98 identische Skips; vier Exit-0-Gruppen.
Alle 15.076 alten IDs plus 157 neue genau einmal enthalten; 810 Quellen/Fixtures
und drei Shell-Hashes. Fünf verschobene Auto-IDs nur durch Parameterreihenfolge
stabilisiert; gesamtes Besitzermodul erneut 41 PASS, inverse Byte-Hash-Prüfung
bestätigt ausschließlich diese Testreihenfolge. Produktionsquellen unverändert.
Quellcommit `113744d6fa964de29644826465eba1c56dcc797a` auf main/VPS live,
17.10.2026 um 16:53:41 CEST, No-Backup-Fast-Forward, Offline-Smoke bestanden.
App-PID 1211028→1215661; App/Caddy aktiv, beide Healthchecks `ok`.
Prognose-Snapshots und fünf Scan-/Quoten-Startstempel beim Deployment unverändert.
Keine neuen Sportläufe/Backups/Migrationen. Nur Abschlussdokumentation folgt.
Kostenlose Quellen ohneexakte/verfügbareAbdeckung nichtangebunden.
ZusammengeführteIntegration748PASS. AlleproduktivenDiffsundReleasehelferread-only
freigegeben. LokaleRenderer(nichtLiveStreamlit) normal/RisikoBet mitTESTDATENbei
1280/390/320px, Maus/Tastatur5/10, keinÜberlauf/Consolefehler. KeineBrowserübernahme.
Test-ID-Abgleich abschließend unabhängig freigegeben. Nächster Schritt:
Abschlussdokumentation committen/main/VPS per Docs-only-Pull, ohne Neustart.
Aktueller Bericht `docs/audits/2026-10-17-multigoal-quotenabruf.md`, Belege
`C:/Projekt/BetBoy/output/multigoal-quotes-20261017/`.

## 17.10.2026 – aktueller Auswahlauftrag

Weiter im bestehenden `.worktrees/audit-repairs-20261013`, Basis `6c106d56`.
User autorisiert alle Fußballmarkt-Auswahlfehler inklusive Multigoal beheben,
testen, main-Push und VPS, ausdrücklich keine Backups. Kein neuer Sportscan.
Runtime95; alte90 ORIGINAL-/Kalibrierungs-/Ticketverträge unverändert.
Statistischer Hauptmarkt wird vor Wahrscheinlichkeitssortierung und Preisen
bestimmt; frühere Gesamtvergleichs-p-Unterdrückung ist reproduziert/korrigiert.
Manuelle Suche/15K fertig. Vollständiger nativer Offline-Testbestand mehrstufig
grün:14978PASS/98 identische Skips, alle15076 IDs genau einmal abgedeckt,
alle14680 alten IDs erhalten,806 Quell-/Fixture-Hashes. Drei vollständige
Updater-Besitzermodule nach einzigem Helperpin-Abgleich:572PASS/8Skips.
Quellcommit`725ccc28e9949528be53ca4c1d41396bfa397408` aufmain undVPS live,
17.10.10:42CEST ohne Backup/Scan/Migration; beide Healthchecks`ok`.
Echter Leser:95Runtime-Märkte,486Prognosen,237sichtbare Karten/64Spiele, jede
sichtbare Karte echte passendeQuote>=1,20. Statistische Hauptmärkte gemischt,
einschließlich5 Team-Multigoal im Hintergrund ohne passende Preisangebote.
Browser-Roma:58,3%-Heimsieg/Quote1,58 zuerst,78,9%-Unter-Markt sekundär;
Ilves öffnet/schließt, keinDC_X2 mehr. Keine neuen Fehler nach Restart.
Die gespeicherten Prognosedateien blieben unverändert. Abschließend folgen
nur dieser Dokumentationscommit/main/VPS-Pull, kein weiterer App-Restart.
Aktueller Belegpfad außerhalbGit:
`C:/Projekt/BetBoy/output/market-selection-20261017/`.
Quellenprobe186/223 heute ohne echte Angebote: keine synthetischen Quoten.
Öffentlich weiterhin genau passende Quote>=1,20. Kontext-/NHL-Vollmodell bleibt
separat offen. Endgültige Receipts folgen im
`docs/audits/2026-10-17-marktauswahl.md` und oben in`TODO_AKTUELL.md`.

## 16.10.2026 – NHL zuerst: native Erfassung, Vollmodell noch offen

Aktiv weiter im isolierten `.worktrees/audit-repairs-20261013`, Basis `cc93663`;
Nutzer erlaubt Tests/main-Push/VPS ausdrücklich ohne neues Backup.
`context_sources/nhl.py` liest echte native Boxscores mit Goalie-Starts/Saves,
Spieler-TOI/Schichten und echten Empfangszeiten. `nhl_capture.py` verbindet den
fälligen Tageslauf mit B1/der vorhandenen Request-DB; höchstens32/UTC-Tag und1MiB
neue Belege pro Aufruf. Keine neue DB, kein Kartenabruf/zusätzlicher Sportscan.
Source-Review PASS; täglicher Anschluss nach UTC-Fix ebenfalls unabhängig PASS;
438 fokussierte/angrenzende Tests grün. NHL-Nachtfenster durch tatsächlichen
gespeicherten Leser korrigiert,23 neue Fälle/503 angrenzende Tests PASS.
Unabhängiges Produkt- und No-Backup-Deploy-Code-Review PASS; Git-Abfragefehler
im Hilfsskript mit RED6→GREEN10 gehärtet. Voll-QA01 offline:14.680
Tests/all14.536 alten IDs fertig. Initiale Sandbox-FAILs behalten; alle betroffenen
ganzen Module und drei zusätzliche Hardlink-Skips mit gleichem Code nativ
nachgeprüft:1.465PASS/21Skips/85Untertests/Exit0. Zweistufiges Gesamtaggregat
14.582PASS/98 identische Baseline-Skips,797 unveränderte Quell-/Fixture-Hashes,
alle12 Abdeckungsguards wahr. Keine Tests/Assertions/Preisregeln gelockert.
Code **bd035b71cf02368b21b72bd4ef2e765329769e8e** auf main gepusht/VPS live.
Offline-Smoke PASS; AppPID1198478→1200874, App/Caddy und beide Healthchecks ok.
Erster Deploy nach Git-Pull vor Neustart am externen Smoke-Belegaufbau gestoppt;
reale Fixture-Empfangszeit ergänzt, Regression/Resume unabhängig PASS,18 Helfer-
Tests nativ PASS. FAIL01 und PASS02 erhalten; Produktcode unverändert geprüft.
Wettfinder-/RisikoBet-Snapshots exakt gleich; kein Scan/Backup/Migration/Cleanup.
Erster echter Erfassungslauf erst regulär17.10.03:35Zurich, noch nicht belegt.
Acht alte fehlgeschlagene September-Prüfdienste bewusst nicht zurückgesetzt;
App/Caddy aktiv, acht andere Timer geplant, Backup-Timer disabled/inactive.
Belege full-qa-01 und native-recheck-01 unter untenstehendem Ausgabepfad;
keinen neuen Scan/Backup starten. Source/Test/Fixture vollständig committed;
bekanntes ungetracktes output/audit-repairs/ und C3-Arbeitsprotokoll behalten.
Zwei frühere lokale Fixture-Reservierungen in ignorierter Worktree-Request-DB
offengelegt, nicht bereinigt; keine Resultat-/VPS-/Geldänderung daraus.
Voller numerischer Personal-/Belastungseffekt ist nicht fertig: aktuelle Vorab-
Ausfall-/Starterquelle und owning Hockey-Training/Replay/D1/D2 fehlen. Historische
Ganzspiel-TOI nicht als Regulation-Manpower umetikettieren. Keine Wahrscheinlichkeiten
erfinden und diese Erfassung nicht als bessere Wettqualität verkaufen.
Aktueller Bericht `docs/audits/2026-10-16-nhl-source-intake.md`, Arbeitsbelege
`C:/Projekt/BetBoy/output/nhl-context-20261016/`, C3-SDD bleibt erhalten.

## 16.10.2026 – Quellen-/QA-Patch live; voller Hockey-Kontext weiterhin offen

Nutzer erneuert All-5-Kontextauftrag plus Tests/Commit/main/VPS ohne Backup;
plant12MonateAPI. API-Hockeyv1 hat keine Player/Injury/Lineup/StartingGoalie-
Endpunkte; bezahltesAbo allein löst das nicht. Kaufwarnung und begrenzter
Primärquellenvergleich dokumentiert in`2026-10-16-hockey-quellen-und-api-abo.md`.
Nutzer bestätigt Abo noch nicht aktiviert; Empfehlung Jahresbindung abwarten.
Lokal433bb86 mit echter Default5-/nativer LigaSaison-Historienbegrenzung.
Mapping-Bridge-Fehler behoben mit1d3ca7a, sechs neue reale Verbraucherfälle;
757PASS/1Skip/37neueFälle insgesamt. Begrenztes unabhängiges Re-Review PASS.
Vollsuite`full-qa-02` fertig RED102 (14.299PASS/98Skips/147Untertests).
Ursachen:43 Updater-Inventar-/Pin-Fälle nach Quotes-Erweiterung und59 ältere
Verbraucher-Preisfixtures. Beide Ursachen begrenzt korrigiert; alte Test-IDs/
Kernassertionen erhalten.512PASS/6Skips,221PASS,137PASS gezielt bestätigt.
Zusätzlich23 Inventar-/Wartefälle,12 Gegenseitenfälle,2 Tennis-Preisgrenzenfälle.
Neues unabhängiges Release-Review PASS für frische QA, keine Full-C3-Freigabe.
`full-qa-03` komplett grün:14.438PASS/98unveränderteSkips/147Untertests;
beideExit0,787Quellhashes unverändert,14.536gesammelt. Keine der14.499QA02-
IDs entfernt, alle14.462früheren IDs erhalten.
Erste Vollsuite`full-qa-01` bewusst INCOMPLETE unterbrochen für Fix;
Receiptsnichtlöschen. Quellenpatch erst nach fertigerQA veröffentlichen.
Code42a5ae3cdedea0766440c9ce81c6dd62b59ee615 aufmaingepusht/VPSFFlive.
Offline-ImportPASS, AppPID1189206→1198478; App/CaddyundbeideHealthchecksok.
Wettfinder-/RisikoBet-JSON vor/nachNeustart exaktgleich. KeinBackup/Scan/DB-
Kopie/Cleanup/Paketinstallation. SeparaterreinerDocs-Commit brauchtkeinenNeustart.
ErsterDeploy nachGitFF imSmoke mit falschemCWD angehalten; Appprüf-CWDfix,
Resume nuraufexaktemZiel mit allenübrigenGuards, Exit0. FAIL-Receipt01und
PASS-Receipt02 behalten, nichtalsAppbugodergrünerErstversuchumdeuten.
Vollständige Goalies/Ausfälle/Müdigkeitnichtfertig.
Quellen-/QA-Reparatur abgeschlossen, keine TestsmehrimHintergrund. Nächster
fachlicherSchritt ist qualifiziertePersonalquelle/owningC3-Pfad, nichtnochmals
dieselbeQuellenreparatur oderungeprüfteEffektaktivierung.
WorktreeundignoriertesC3Arbeitsprotokollbehalten; nichtaltesRootcheckoutverwenden.
VPS-App/Caddy gesund; anfänglicherFootball-Shadow-Fehlstatus(Exit1) imregulären
21:22-Lauf vorDeploy wiedersuccess/inactive; nichtdiesemPatchzuschreiben.
Backupweiterdisabled/inactive,22GBfrei; keineBereinigungnötig.
Neue Anbietersuche: SportsDataIO(NHLConfirmedStarter/Injuries), BALLDONTLIE
(NHLGOAT39,99USD/Monat, keinConfirmedStarter), Enetpulse(Premium4Ligen,
SchweiznichtPremium). Kein verifizierter All-5-Komplettanbieter, nichts gebucht.

## 16.10.2026 – zuletzt historische Hockey-Stichprobe tatsächlich gerechnet

Nutzer erlaubt alte2022/2023Daten für historische Probe. Sechs Abrufe vorhandener
API,3.239Spiele/2,07MB, keine Bilder. Saison2023/24, vorab20Januar2024-Ziele je
Liga eingefroren; nur frühere Spiele abNov2023/48h-Abstand, unveränderte existente
Modellmathematik. **62/100richtig vs51/100immerHeimsieg**; NHL15,Swiss13,SHL11,
Liiga13,DEL10je20. >=70%-Modellklasse18/23, kein Renditenachweis/keine neue
Tippregel. Acht Offline-Schutztests PASS; echte2026Empfangszeiten bleiben erhalten,
kein vorgetäuschter kausaler Produktionsreplay. Torhüter/Verletzungen/Müdigkeit
dadurch nicht umgesetzt. Keine Modell-/Historien-/Geld-/Deployment-/Backupänderung;
nur bestehendes API-Kontingent hat sechs Anfragen verbucht. Unabhängige Prüfung
von100 Fällen/Training/Bindungen/Kennzahlen ohne kritischen Befund.
Bericht`docs/audits/2026-10-16-hockey-historische-stichprobe.md`, Daten/Analyse-
Artefakte`C:/Projekt/BetBoy/output/hockey-top5-20261016/`.

## 16.10.2026 – ursprüngliche Hockey-Ausgangsprüfung, vor Quellenpatch

Nutzer beauftragt echten Ausbau für NHL/National League/SHL/Liiga/DEL mit
Gegnerstärke, Form, Goalies, Ausfällen und Belastung, kostenlosen aktuellen
Quellen, Tests und VPS-Deploy ohne Backup. Damals kein neuer Produktcode/Deploy.
Damals geprüfter Produktstand `084d8d3`; kanonisches Worktree wie unten.
Frische Baseline1.046PASS/1Skip, kein empirischer Effektbeleg.
API-HockeyFree liefert Tagesplan, geprüfte Schweizer Saisonhistorie2026 jedoch
`plan`-Fehler. Cache read-only:1.528NHL2025/26+151NHL2026/27, keineAPI-Hockey-
Ergebnisrevisionen. Vier europäische Quellen teilweise technisch erreichbar,
aber Prematch-Personalabdeckung und passende Nutzungsrechte nicht vollständig.
Keinen Quellen-/Beobachtungszeitpunkt erfinden, keine Gebühren/Freigabeanfragen
oder Zugangsumgehung eigenmächtig auslösen. Owning Hockey-Trainings-/Outcome-/
Replay-/Evaluatorpfad fehlt trotz vorhandener synthetischer C3-Mathematik.
Konkrete Belege/Nächste Schritte in
`docs/audits/2026-10-16-hockey-top5-daten-und-modell.md` und TODO_AKTUELL.md.

## 16.10.2026 – jüngster aktiver Auftrag: Quoten und 1,20

Kanonisch weiter `.worktrees/audit-repairs-20261013`, nicht das alte schmutzige
Hauptcheckout. Nutzer autorisiert Reparatur, Tests, Commit, main-Push und
VPS-Deploy ausdrücklich ohne neue Sicherung. Öffentliche Tipps brauchen jetzt
überall echte exakt gebundene Quote>=1,20; früheres „fehlende Quote sichtbar“ ist
überholt. Modellbestand, Modellrichtung, Wahrscheinlichkeit und Reihenfolge
bleiben preisunabhängig. Neue billige Preise müssen auch alte manuelle/15K-
Sitzungen verdrängen. Quotenjob alle3h, keine neue Modell-/Sportsuche.

Produktreview abgeschlossen; finale betroffene QA2.493 PASS/7 bestehende Skips/
32 Untertests/Exit0. Alle14.350 alten IDs erhalten, jetzt14.462 gesammelt;
786 Quellhashes eingefroren. Keine erneute komplette14K-Vollsuite.
Codecommit`aab9fb2` auf main/VPS live. Reiner Quotenjob16:56CEST Exit0,
123 Quoten/0 Fehler; kein Sportscan/Backup. Dinamo exakt1,11 gespeichert und
verborgen,54 öffentliche Wettfinder-Auswahlen alle>=1,20. Daily3 aktuell1,58;
36 RisikoBet-Szenarien alle>=1,42. Vorher-/Nachher-Modell- und RisikoBet-
Fingerprints ausdrücklich identisch. App/Caddy/Healthchecks ok, Quoten-Timer
alle3h aktiv, nächste18:15CEST. Browser frisch geprüft; keine Geldaktion.
Aktuelle Test-/Prüfbelege außerhalb Git unter
`C:/Projekt/BetBoy/output/quote-refresh-20261016`; frühere FAIL-Receipts erhalten.
Verwendeter No-Backup-Deploypfad dort`deploy.sh`, **nicht** den bestehenden
backupfähigen Standard-Updater aufrufen. Produktionsbelege`deploy-01.log`,
`runtime-proof-02.json`, `consumer-proof-01.json`; erster Read-only-Prüfaufruf
scheiterte nur am absichtlich fehlenden ubuntu-Verzeichnisrecht, Wiederholung
als App-Benutzer erfolgreich. Keine Behauptung einer vollständigen14K-Neuprüfung.
Alle offenen fachlichen Aufgaben und zurückgestellte Schlüsselrotation bleiben.

## 16.10.2026 – jüngste Nutzerentscheidung zu API-Schlüsseln

Schlüsselrotation ausdrücklich nur als offenes To-do führen und vorerst
zurückstellen; App laut Nutzer momentan ausschließlich persönlich genutzt.
Die private Ersatzdatei enthält noch die drei historischen Werte, keine
verifizierten neuen Schlüssel. Nichts davon übertragen oder als rotiert melden.
Das Kontingent-/Missbrauchsrisiko bleibt unabhängig von der App-Nutzerzahl bestehen.
Weitere Marktvergleichsarbeit nicht auf die Rotation warten lassen; keine
Schlüssel-, Abo-, Zugriffs- oder Serveränderung durch diese Dokumentationsaufgabe.
Produktcode unverändert; VPS zuletzt in diesem Chat auf `aaafba5` geprüft.

## Einstieg16.10.2026 – aktuelle reale Position

Kanonisch `.worktrees/audit-repairs-20261013`, Branch `codex/audit-repairs-20261013`.
Indexcode `c110d8e` ganzeQA03 grün14.239/98Skips/147Untertests, auf main/VPS.
Aufbau vollständig2.616.120Belege, aber unveränderter echter Vier-Fall-Test
FAIL0/4:11.589.186Payloadbytes über2MiB/Fall und8MiB gesamt. Sofortiger
vorgesehener `disable` erfolgreich; kompatiblen Code behalten, Index invalid,
kein Altbinary-Rollback, keine Limits/Fälle/Revisionen umdeuten. Abnahmebericht
`docs/audits/2026-10-15-tennis-spielerindex-abnahme.md`; Task6 bleibt offen.
Alle79 vorher erfassten Finanzdateien unverändert, Nachherinventar80 wegen
zusätzlicher separat ausgewiesener Sitzung. App/Caddy/Healthchecks funktionieren.

Neu freigegebene begrenzte Sortierung separat: überall Modellwahrscheinlichkeit
absteigend je Markt und Spielblock. Daily3 nur Darstellung, Einsatzfolge und
ursprüngliche nächste Wette bleiben zeitgebunden. Sourcecommit0859468 auf
Arbeitsbranch,395gezielteTests/13neueIDs, Review sauber. **Als Produktivstand
38f73ed auf main/VPS live**, nach vollständiger QA02 und nur App-Neustart.
Vollständige Zwei-Shard-QA01 liegt unter
`C:/Projekt/BetBoy/output/probability-order-20261016/qa-final-01` am unveränderten
HEAD0859468: **14.250 PASS/2 FAIL/98 gleiche Skips/147 Untertests**;
alle14.350IDs genau einmal,771Quellhashes/RootWIP/45alteReceipts unverändert.
Freeze beendet. Zwei reine Prüfadapterlücken unabhängig diagnostiziert:
isolierter Navigationsnamespace ohne realen ordered_event_rows-Import und
alter Prematch-Test verlangt den absichtlich entfernten Startzeitumschalter.
Genau diese zwei Tests mit7fea742 korrigiert,432/432 betroffeneTests bestanden;
alle Navigations-/Quotenassertionen und altenIDs erhalten. Produktquellen bleiben
byte-identisch zu0859468. Begrenztes Nachreview ohne Befunde abgeschlossen;
neue ganze QA02 am unveränderten8c36095 vollständig PASS:14.252bestanden,
98identischeSkips,147Untertests; alle14.350IDs genau einmal,771Quellhashes/
RootWIP/118historischeReceipts unverändert. BeideExits0; finalePrüfung07:56:17UTC.
QA01 bleibt FAIL. Freeze beendet. Produktbereitstellung38f73ed abgeschlossen:
PID1159516→1175628, Modell-JSONs byte-identisch, Index bleibt deaktiviert,
App/Caddy/7Timer aktiv+aktiviert, Backups deaktiviert, beideHealthchecksok.
Echter internerBrowser: erste3Maxima85,7/84,1/81,3%,22sichtbareMärkte absteigend,
kein alterSortierumschalter; Spielblockzu/auf und Daily3rail→richtigeSeite→zurück
funktionieren,0neueKonsolenfehler/-warnungen. Daily3nur1Livekarte, Mehrkarten-
Ausführung/Ordnung softwareseitig geprüft; keineBudget-/Wettaktion ausgelöst.
Kein neuerLiveMobiltest oder Prüfung jedes eingeklapptenSpiels behauptet.
AbschließendeSynchronisierung nurvierMarkdowns perFastForward ohneNeustart;
finalerHEAD/App-PID im separatenAbschluss-Receipt. Produktbytes identisch zum
geprüften8c36095, keineSicherung/Scan/Index-Neuversuche.
Workerberichte/Review/QA außerhalbGit unter `output/probability-order-20261016`.
Index-native Belege unverändert unter `output/tennis-player-index-20261015`.
Nicht erledigte Verletzungs-/Wetter-/Müdigkeitswirkung bleibt ehrlich offen.

Frische Nur-Lese-VPS-Prüfung16.10.09:35CEST: weiterhinc110d8e, App/Caddy/
Healthchecks ok,7Timer geplant, Backups inaktiv. Shadow zuletzt09:32 Exit1:
fehlende frische Bet365-Providerzeitquote Fixture1622791 und2historische Zeilen
mit unvollständiger Quoten-/Abrechnungsprovenienz. Das ist separat offen, keine
behauptete grüne Gesamtlaufbilanz. Journale unter output/probability-order-20261016;
kein neuer Scan, Historienreset oder nachträgliches Erfinden von Nachweisen.

## Aktueller Einstieg 16.10.2026 00:11 – QA03 als nächster Gate

Kanonischer Branch unverändert `codex/audit-repairs-20261013`. Die drei QA02-
Prüfadapterfehler sind mit `e717936` korrigiert: 17 gezielt bestanden, echter
No-BEGIN-Sensitivitätsfehler, finale Nachbarprüfung 238 PASS/9 gleiche Skips,
unabhängiges Review sauber. Produktowner/Pins/Schutzassertionen unverändert.
QA02 und frühere Unterbrechungen behalten ihren ursprünglichen FAIL/INCOMPLETE-
Status; sie sind keine ganze Freigabe. Nächster Schritt nur neue vollständige
eingefrorene QA03 mit allen alten IDs und unveränderten 98 Skip-Identitäten.
Danach erst kompatibel deployen, explizit Index aufbauen, echte unveränderte
vier Fälle innerhalb insgesamt 45 Sekunden prüfen und operativ abschließen.
Main/VPS noch `4ece002`; keine Produktionsdatenbankkopien, Backups, Zusatzscans
oder neuen numerischen Effekte. Nicht Tasks 1–5 oder fertige Reviews neu starten.

## Aktueller Einstieg 15.10.2026 23:46 – QA02 vollständig, noch kein Release

Kanonisch weiter `.worktrees/audit-repairs-20261013`, Branch
`codex/audit-repairs-20261013`; Aufgaben 1–5 nicht neu starten. Ganze QA02 am
unveränderten HEAD `41e6a69`: 14.222 PASS, 98 unveränderte Skips, 3 FAIL,
147 PASS-Untertests. Alle 14.323 IDs genau einmal, 769 Quellhashes und Root-WIP
unverändert. Belege/Details im plan-eigenen SDD-Ledger und QA02-Verzeichnis.

Nur drei alte Prüfadapter sind betroffen: SQLite-Verbindungs-Factory im
Reader-Trust-Test sowie fehlende historische Receipt-Corpus/-Append-Quellfixtures
für die eingefrorenen nativen Manifestprüfungen. Produktquellen und alte Pins
nicht lockern; Adapter minimal korrigieren, RED/GREEN/Review und neue Vollabnahme.
Main/VPS bleiben `4ece002`, Arbeitscode `41e6a69`; nichts produktiv umgestellt.
Index-Aufbau und echter unveränderter nativer 4/4-/45-s-Test bleiben offen.
Keine neuen Sport-/API-Scans, Backups, DB-Kopien, Bereinigungen oder Effektfreigaben.

## Aktueller Einstieg 15.10.2026 – Planfreigabe und Ausführungsstart

„Umsetzungsplan freigegeben“ ist ausdrücklich erteilt. Weiterarbeiten in
`.worktrees/audit-repairs-20261013`, Branch `codex/audit-repairs-20261013`.
Aktuelle Aufgaben-/Reviewposition ausschließlich im plan-eigenen Ledger
`.superpowers/sdd/2026-10-15-tennis-spielerindex-umsetzung/progress.md` nachsehen;
keine fertigen Aufgaben erneut starten. Task 1 Schema/Projektion ist mit
`26b8f64`/`0d2849e` und sauberem Nachreview abgeschlossen; finale gezielte Prüfung
44 PASS, keine Gesamtsuite daraus behaupten. Task 2 Aufbau/CLI (`83f6c72`/`e872e39`,
72 PASS) und Task 3 normaler Append (`5cdcfe2`, 250 PASS) ebenfalls unabhängig
geprüft. Task 4 v2 (`3279be4`, 344 PASS) und Task 5 echter Leser (`7351b9d`,
174 PASS) sind inzwischen ebenfalls unabhängig ohne Befunde freigegeben.
Weiter ausschließlich mit Task 6: ganze Offline-Suite/identische Skip-IDs,
Branch-Review und erst danach kompatible Bereitstellung, expliziter Aufbau sowie
unveränderter echter Vier-Fall-/45-s-Nachweis. Noch kein neuer Main-/VPS-Release.
Abschlussreview inzwischen vollständig: Kontrollwert-Materialisierung durch
`c3e25a1` begrenzt, 163 gezielte Tests, sauberes unabhängiges Nachreview. Früherer
Vollsuite-Anlauf `qa-final-01` wurde dafür gezielt abgebrochen und ist KEIN PASS.
Neue vollständige Prüfung in `output/tennis-player-index-20261015/qa-final-02`;
keine Quelle/HEAD während dieses Laufs verändern. Danach erst Produktionsphasen.
Vorher 14.160 Test-IDs gesammelt, alle alten 14.133 und
27 Task-23-IDs erhalten. Das ist eine Collection, kein neuer vollständiger Testpass.
Separater Benfica/Celtic-Audit liest gespeicherte Produktionsdaten ohne Scan.
Keine neuen Backups, DB-Kopien oder Bereinigungen, keine numerische Effektfreigabe.

## Aktueller Einstieg 15.10.2026 – Umsetzungsplan zur Freigabe

Nutzer hat die schriftliche Spielerindex-Spezifikation ausdrücklich freigegeben.
Plan: `docs/superpowers/plans/2026-10-15-tennis-spielerindex-umsetzung.md`.
Sechs testbare Pakete, bestehende API-/Ressourcengrenzen und Originaldaten
unverändert. Für private v2-Kopien nur kontrollierte Indexinvalidierung mit
strikter Original-/Zuordnungsprüfung; kein allgemeines neues Änderungsledger.

Nächster Gate: Nutzer prüft/freigibt Plan. Ausführung wie früher gewählt mit
Unteragenten und Review je Aufgabe. Noch keine Umsetzung, Tests oder VPS-Aktion.
Spätere Reihenfolge: lokal vollständig prüfen → schemafähiger Vorbereitungs-
deploy → expliziter Aufbau → echter unveränderter 4/4-/45-s-Gate → Abschluss.
Vorbereitungsstand nicht als fertige Reparatur/Qualitätsverbesserung melden.

## Aktueller Einstieg 15.10.2026 – Spielerindex-Spezifikation zur Freigabe

Nutzer hat die Erstellung der kurzen Schriftfassung bestätigt, nicht deren
Umsetzung. Neuer Entwurf:
`docs/superpowers/specs/2026-10-15-tennis-spielerindex-design.md`.
Zwei abgeleitete Tabellen im bestehenden Kontextspeicher; atomare Pflege durch
beide Writer, begrenzter fortsetzbarer Aufbau, exakte optionale Schemafamilie
auch in v2-Inventur/Corpus. Keine Kopie der Quellen, kein neuer Anbieter/Dienst.
Gültige Nicht-Tennis-Daten und die Originalspeicherung dürfen nicht blockieren.

Nächster Gate: Nutzer liest/freigibt die Schriftfassung, danach Umsetzungsplan.
Kein Produktivcode/Testlauf/Migration/VPS-Pull in diesem Dokumentationsschritt.
`0ce0687` bleibt Batch-WIP auf Arbeitsbranch, nicht main/VPS. Historische
144 PASS beheben nicht das weiterhin rote Vier-Fall-/45-Sekunden-Leistungsgate.

## Aktueller Einstieg 15.10.2026 – Batch-WIP nicht deployen

Kanonisch weiterhin `.worktrees/audit-repairs-20261013`, nicht Root-WIP.
Produktionsstand heute frisch `4ece002b69eb5c96897d3471cc7320654608a903`.
Regulärer Tennis- und Wettfinderlauf erfolgreich, App/Caddy/Health gesund;
Backup abgeschaltet, keine zusätzlichen Sport-/API-Scans gestartet.

Task 23: freigegebener B1-Batch implementiert, erste 141 gezielte Tests grün;
nach Review echte Zwei-Stichtag-Gegenprobe und Ein-JSON-Projektion ergänzt,
neun fokussierte Tests grün; abschließend alle sieben betroffenen Module:
144 bestanden/Exit 0 in 369,59 s, fünf eingefrorene Hashes danach identisch.
Trotzdem realer identischer Vier-Fall-Gate zweimal
nach 45 s ohne Ergebnis abgebrochen. **Nicht als gelöst freigeben/deployen.**
Vorbereitung 0,449 s; globale Belegsuche bremst. Insgesamt 2.602.717 Belege,
981.335 ATP-Belege; WTA-Zähler unbekannt. Empfangszeit ist Teil der gespeicherten
Statusrevision, deshalb kollabiert Inhaltsgruppierung die Wiederholungen nicht.

Keine weitere Zufallsabfrage oder stille Grenzerhöhung versuchen. Abgeleitete
Spieler-Spiel-Zuordnung mit nachvollziehbarem vollständigem Aufbau wäre eine
Änderung des Entwurfs und benötigt Freigabe; noch kein Index-/Schemaumbau.
Aktueller Bericht `docs/audits/2026-10-15-tennis-batch-45s.md`, Brief/Report
`task-23-tennis-batch-20261015-*.md` und oberster TODO-Abschnitt sind maßgeblich.
Native FAIL-Logs außerhalb Git in `output/tennis-batch-20261015` erhalten.
Verletzungs-/Wetter-/Müdigkeitswirkung und Qualitätsnachweis weiterhin offen.

## Aktueller Einstieg 14.10.2026 – QA04 fertig, Quellen-Release

Kanonisch: `.worktrees/audit-repairs-20261013`, Branch
`codex/audit-repairs-20261013`. Root-WIP und ungetrackte Auditdateien erhalten.
Nutzerwahl: nur vorhandene/kostenlose Quellen; keine neuen Backups/API-Scans.

QA04 vollständig fertig: **14.035 PASS, 98 Skips, 147 PASS-Untertests**,
beide Exit 0. Alle 14.133 IDs exakt einmal, alle 13.922 alten + 211 neuen.
97 alte Skips identisch, ein neuer echter Windows-Symlinkskip (WinError 1314).
21 Source-/Testhashes und zehn geerbte Root-Codehashes unverändert nachgeprüft.
Sessions 96255/36580 beendet, nicht erneut als laufend behandeln.
Der reale breite Speichergate ist jetzt repariert; Originaltest/512-KiB-Grenze
unverändert. Kombinierter Originalmesslauf 7.720.933 → 30.604 Bytes.
POINT-Schutz und v3-Fußballquellen vollständig regressionsgeprüft;
gezielte unabhängige Reviews ohne offene Befunde. Kein numerischer Effekt daraus.

Quellenpaket `50ec01910c3ed4ed6a0caa2fb08bf48720a573b5` ist auf GitHub `main`
und seit 15:23 CEST auf dem VPS. Offline-Imports/Literalquellenfamilien bestanden,
genau ein App-Neustart (1131606 → 1136736), Modell-JSONs unverändert.
Keine DB-/Schemaänderung, Sicherung, Kopie, Bereinigung oder zusätzlicher Scan.
SSH-Wrapper erst nach erfolgreichen Prüfungen wegen Windows-CR-Trailer Exit127.
Echtes Ergebnis erhalten, nicht umetikettiert; separate korrigierte lesende
Nachprüfung15:24 Exit0: ZielHEAD/PID stimmen, beide Healthchecksok,
App/Caddy aktiv, sieben Timer enabled/geplant, Tagesbackupdisabled/inactive.
Anschließend docs-only FF-Pull ohne zweiten App-Neustart; Codebasis weiter50ec019.

**Nicht Gesamtabschluss:** realer begrenzter historischer Quellenleser noch offen
(Vier-Fall-Abfrage >45 s; tatsächliche Datei 7.35 GB > bestehendes C-4-GiB-Limit).
Keine Grenzerhöhung/retroaktive POINT-Umetikettierung. Roh-Finals 936 über alle
Winner-Generationen sind keine qualifizierten Trainings-/200-Testkohorten.
WTA-POINT-Modellgeneration bedeutet nicht Serve-Joint-Baseline. Vorhandene
Fußballminuten/Wetter und getrennte Tennis-Sätze/Games/Erholungsuntergrenzen
priorisieren; fehlende exakte Endzeiten oder Diagnosen nicht erfinden.
Numerische Verletzungs-/Wetter-/Müdigkeitswirkung, Qualität und öffentliche
Anwendungsbrücke bleiben offen. Aktuellste TODO und Audit haben Vorrang.

## Historischer Einstieg 14.10 – nachfolgende Laufstatus ersetzt

NeuesterOverride: NativeFootprint-Fix 9ACF8B54 undneueTests06F28CF6 final.
Identischer kombinierter RED/GREEN-Prefix:7.720.933→30.604Bytes, Original512KiB
Test unverändert. Finale54PASS/1neuerWinError1314Symlinkskip,Cold1/chunks71/
Nachbarn281PASS und unabhängigerReview ohneBefund. NochkeinVollsuitePASS.
QA04 A96255/B36580 läuft mit21Dateihashes/14.133IDs (alle13.922alten+211neue);
97alteSkip-IDs müssen erhalten, neueSymlinkplattform-Skip getrennt zählen.
AlleQA03-Sessionangaben unten sind beendet; keineCodeänderungen imQA04-Freeze.
Main/VPS noch242093f, keinPull/Restart/Backup/Scan. NeuerBrief/Report task21-
native-footprint; neuevollständigeBelege rootoutput/qa-final-04.

QA03 vollständig beendet:13.980PASS/1FAIL/97 identischeSkips/147PASSUntertests.
14.078Items exakt einmal, alle13.922 alten plus156 neue erhalten. Sessions
23235(AExit1) und34109(BExit0) beendet, nicht erneut als laufend pollend behandeln.
Originale512KiBMessung im breiten A-Prozess:7.720.876Bytes. Eine zusätzliche
voll gesammelte, ausdrücklich nur auf den einzelnen Knoten selektierte Diagnose
bestand mit461.173Bytes; das ist keine Suite-Abdeckung und widerlegt Sammlung
allein als Ursache. Neue begrenzte Vorläufer-/Allokationsdiagnose läuft außerhalb
Git. Kein mainPush/Deploy/Backup/Scan. Der unten stehende QA03-Laufstatus ist
historisch und wird durch diesen Abschluss ersetzt.

Anschließender kombinierter Diagnoseprefix hielt alle6.837 gesammelten Knoten
lebend und führte exakt1.544Prefix-Items aus:Originalpeak7.720.933FAIL. Größte
einzelne7.689.584ByteAllokation ist pathlib/sys.intern, CPythonIntern-Dict-
Neuanlage (nicht bewiesene Verdoppelung), MainThread. EngerTDD-Fix am realen
Footprint-Owner wird durchgeführt; keineWarmups/GC/Filter-/Grenzänderung.
Bestehende Path-Rückgabe für andere Leser, Fehlerpolitik und zweitesstat nach
exists sowie alleSQL/Ressourcenchecks müssen unverändert bleiben. NeuerBrief
task-21-native-footprint-20261014, Belege rootoutput/memory-full-causal.

Kanonisch weiterhin `.worktrees/audit-repairs-20261013`, committed74f8e0d plus
lokaler geprüfter sechs-Wert-Generationfix. OriginalCold512KiBTest1PASS,
vollständiges unverändertes Refchunksmodul71PASS, Nachbarn281PASS;
unabhängiger Review ohne Befund. Kein Warmup/GC/Testgrenzenwechsel.
Finaler Paketreview fand echte P1: POINT-D4 öffnete geschützt ungeöffnetes
Endergebnis. Eng repariert, final93PASS/26neueFälle; unabhängige ursprüngliche
Gegenprobe ohne Zugriff und ohne geänderteDBbytes. DirekteLeser unverändert.
QA02Sessions79653/83393 wurden dafür bei47%A/29%B beendet,
Exit1/kein AbschlussJUnit, nicht weiterpollend als laufend behandeln.
Collection14.052 enthält sämtliche13.922bisherigenIDs plus130neue.
ScopedGREEN/Gegenprüfung abgeschlossen; QA03Sessions23235/34109 laufen auf
20Source-/Testhashes und14.078Items (13.922alte+156neue) in qa-final-03.
Erst vollständiger exact-once Abschluss, dann standingautorisierten mainPush/
source-onlyVPSPull ohneBackup. Keine weiteren Sourceänderungen während QA03.

Echter Quellenpfad ist noch nicht gelöst: Training/Readiness haben keinen
lebenden CompletedC-Owner. Produktive Kontextdatei7350726656Bytes,
freelist0; C-Gesamteingabe4GiB. Keine freieSeiten-Vacuum-Lösung nachgewiesen,
keine still erhöhte Grenze, Löschung oder DBkopie. Weitere privateC-Arbeit
ist bereits genehmigt, aber ein bloßer ungenutzter Indexhelper wäre keinFix.
Quellendeklaration großer Fußballpools beweist nicht, dass alle Appearance-
Zeilen numerisch gebraucht werden; vollständige Altprüfung muss bleiben.
Numerische Wirkung/200Testkohorten/Qualität/öffentliche Anwendung offen.
Frische Winner-Rohinventur allerGeneration hat270ATP/666WTA passende normale
native Finals bei1045erstenEreignissen/5367Publikationen. Keine Gewinnselektion,
Merkmalsprüfung oder qualifizierteKohorte. PhysischerKatalog0 POINTcapture-
Publikationen;149/312frühereZahlen sind Winner einer POINTmodellGeneration,
nicht neueSameCallcaptures. Native B1-Suchindex ist ein erreichbarer separater
Kandidat, braucht aber exakteoptionaleSchemaannahme und begrenztenBuild/Rollback;
nichts installiert, keinANALYZE. C4GiB weiterunverändert.
Siehe neuesten TODO-Block und SDD task22diagnosis. Main/VPS frisch242093f,
App/Caddy und Healthchecksok, Tenniszuletzt success/Exit0. Kein neuer Deploy,
APIscan, Backup oder Datenverlust; RootWIP/ungetrackteAudits unverändert.

## Aktiver Einstieg – 14.10.2026: numerische Kontext-Restarbeit

Autoritative Arbeitskopie `.worktrees/audit-repairs-20261013`, Basis242093f.
Aktuelle lokale, noch nicht veröffentlichte POINT-Prerequisite472PASS+44PASS/
3Plattformskips mit unabhängigem Review; keine numerische Aktivierung oder
Vollsuitebehauptung. Fußball-v3 owning D4 benötigt die identische zusätzliche
Nationalteam-Spielerhistorie; zwei echte SQLite-RED/GREEN-Fälle, finale Runde71PASS
mit26neuen Grenztests, unabhängiger Review ohne Befund. Nicht Hauptcheckout-WIP
darüberkopieren. Numerischer Effekt weiterhin separat offen.

Frische VPS-Headerinventur: tatsächliche POINT-Generation149ATP/312WTA-Bo3,
134/248 matching Ergebnis-Header, keine qualifizierten200Testfälle. Vier feste
Merkmalsfälle scheiterten an der45sTeilnehmer-Abfrage; kein Vektor und kein
DBkorruptionsnachweis. Der lokal geprüfte Query-Kandidat scheiterte auch real
auf dem VPS vor dem ersten Vektor und ist NICHT im Veröffentlichungspaket;
Owner base-bytegleich, Kandidat außerhalb aktiver Tests als Diagnose erhalten.
Keine neue Freigabe oder Quellen-/Merkmalsabdeckung daraus. Keine neuen
Provider-Scans, Backups oder DBkopien. Vollständige numerische Freigabe und
öffentliche Anwendungsbrücke nicht mit den Prerequisite-Tests gleichsetzen.
Oberster TODO-Block und docs/audits/2026-10-14-kontextmodell-abschlusspruefung.md
haben Vorrang. Gemeinsame finale QA/Commit/Push/VPS-Veröffentlichung erst nach
dem implementierten und unabhängig geprüften begrenzten Paket.

Finalreview-P2 (optional POINT-Lesen >500 Ereignisse) tatsächlich reproduziert
und eng repariert: RED4+2, GREEN9 und owning131PASS/3alte Plattformskips;
unabhängiger Gegenreview ohne Befunde. Nur explizite finite Admission wird
vollständig intern declined, echte Integritätsfehler bleiben ablehnend.
Erster kombinierter Lauf deshalb gestoppt, kein PASS. Finale unveränderte
Source-Freeze/Collection14.038 (13.922 alte +116 neue) und Vollrunde laufen
in `output/context-completion-20261014/qa-final`. Noch kein neuer Push/Deploy.

Neuester Endgate: vollständige A-Gruppe wegen reproduziertem unverändertem
Cold-Speicher-Test bei47% angehalten, B-Gruppe bei65% danach kontrolliert beendet.
Beide Exit1/ohne abschließendesJUnit, keine neuenBFehler gemeldet, kein PASS.
Warmup-Testkorrektur
nicht akzeptiert: owning71PASS/1FAIL trotz unveränderter512KiB-Grenze; echte
1MiB-NegativkontrollePASS. Kandidat diagnostisch gespeichert, Basistest wieder
vollständig hergestellt. Kein Vollsuite-PASS, keine numerische Aktivierung und
kein neuer VPS-Release. Akzeptierte17Sourcehashes und Root10Hashes erhalten.
Scoped Branch-Checkpoint ist nur Arbeitsfortschritt; Main/VPS weiterhin242093f.

Source-Checkpoint291525211ab0e66591e878a6217b568a739293f8 committed und auf
origin/codex/audit-repairs-20261013. Frisch remoteMain/VPS242093f unverändert,
App/Caddy aktiv, zweiHealthchecksok, Tennisserviceletztmalsuccess/Exit0.
Kein neuerVPSPull/Restart/Backup/Sportscan. QA-Sessions54309/24558 sind beendet;
nicht als noch laufend pollend neu anfangen. OriginaleColdfehler und verworfene
CTE/NOT-INDEXED/Warmup/Cursor-Proben vollständig erhalten. Geerbtes ungetracktes
output/audit-repairs/ und RootWIPunangetastet. Erst Datenpfad+Speichergate
reparieren, dann kompletteQA, Integration/main/VPS und echte Modellqualifikation.

## Neuester Einstieg – 14.10.2026: Tennis-Ergebnisbrücke live

Autoritative Arbeitskopie `.worktrees/audit-repairs-20261013`, Ausgangscommit
`dd704ade`. Begrenzte reparierte Integration bestehender bestätigter Sieger in
ATP/WTA-Elo; keine zusätzlichen API-/Sportscans, Backups, historische Writes
oder erfundenen Serve-/Verletzungs-/Müdigkeitsdaten. Täglicher Cache-Aufbau,
striktes Download-/Seedingverbot bei Cachemiss und CAS-Stichtagsmonotonie ergänzt.
25 neue Schutzfälle; finale betroffene Runde 151 PASS und unabhängiger Review
145 überlappende Tests PASS. Echter VPS-Fall `184936` am alten Stichtag genau einmal
zugelassen, Original-/Shadow-/Revisionssignaturen unverändert. Fehlende neue
Quellenfamilie in `full3` reproduziert und mit zehn zusätzlichen Übergangs-/
Unknown-/Mixed-Owner-Tests korrigiert. Alte Pins unverändert; D2-Evaluation bleibt
fail-closed. Gemeinsame historische Runtime-/D1-/Brücken-/CLI-Runde: 364 PASS,
316,65 s. VPS hat keine aktive Kontextfreigabe. `full4` durch Unterbrechung bei
81 % ohne Abschluss-JUnit beendet, kein Vollsuite-PASS. Code-/Testdateihashes
unverändert. Beide vollständigen Dateigruppen `full5-A/B` am 14.10. abgeschlossen:
13.825 PASS, 97 unveränderte Plattform-Skips, 147 Untertests, null Fehler.
Alle 13.922 Hauptitems genau einmal nachgewiesen; acht eingefrorene Hashes gleich.
Codecommit `a3f465c673da2d4c3050bdd26203519181bcb882` auf main und VPS live,
14.10.2026 08:23 CEST verifiziert. Offline-Linux-Imports/Quellenfamilie bestanden;
App-PID 1116649 → 1131606, beide Healthchecks ok, sieben Timer aktiv/enabled.
Modell-JSONs bytegleich; keine neuen Backups oder Sport-/API-Scans.
Zehn geerbte Hauptcheckout-Codehashes gleich. Dokumentarischer Abschluss separat
als FF ohne weiteren Neustart. Reguläre Modellübernahme weiterhin
separat bestätigen. Siehe obersten Block TODO_AKTUELL.md und
`docs/audits/2026-10-13-tennis-ergebnisbruecke.md`.
Vorinstallation am 14.10. 07:01: VPS `dd704ade`, gesund; regulärer alter-Code-Tennisjob
erfolgreich. Nächster regulärer Aufbau **15.10.2026 00:05 Europe/Zurich**.

## Neuester Einstieg – 13.10.2026: Claude-Auditpaket live

Oberster TODO-Block hat Vorrang vor historischen Zwischenständen. Autoritative
Arbeitskopie: `C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013`,
Branch `codex/audit-repairs-20261013`, Basis `c5a6264`. Hauptcheckout enthält
frühere unveröffentlichte WIP: nicht resetten, breit stagen oder überschreiben.

Sechs freigegebene Reparaturen qualifiziert. Vollsuite auf eingefrorenem Index
`b879d8d75ececc72848a3a2917bfab79959c8e95`: 13781 PASS, 97 Plattform-Skips,
147 Untertests, 0 Fehler; exakt 13878 Hauptitems einmal abgedeckt. Letzter manueller
Tennis-Merken-Anschluss separat RED→GREEN: neun neue Fälle, alle acht betroffenen
Module 255/255 PASS. Finaler Code-/Testbaum: `0ca151db8eb99cbb058fd0891bfc09a492f13581`.
Überlappende Zahlen nicht addieren; die UI-Ergänzung ist eine eigene Abschluss-
qualifikation, keine nachträgliche Behauptung zur alten Vollsuite.

Codecommit `6636530267826fb37b3c834b8e94afa4ebc1b019` auf main und VPS live,
13.10.2026 um 20:33 CEST. Reparatur-Worktree, GitHub und VPS vor Dokumentationsnachtrag
exakt gleich. Offline-Linux-Imports bestanden, Kalibrierung legacy-v1 aktiv.
App/Caddy laufen; sieben Timer aktiv und enabled, beide Healthchecks ok.
Modell-JSONs bytegleich, 21 GiB frei, Backup-Timer und -Dienst inactive.
Interner Browser: 18 Merken-Buttons, erster sichtbar, keine Seitenexception und
keine neuen Warnungen/Fehler nach Wiederanlauf. Kurze Disconnect-/502-Logs während
des kontrollierten Neustarts bleiben korrekt als Restartartefakte dokumentiert.
Keine echten Produktions-Testmerker oder Geldbuchungen angelegt.
Dieser Nachtrag wird separat als Docs-only-FF ohne Appneustart veröffentlicht.
Historische PENDING-Blöcke darunter sind für dieses Paket ersetzt.

Kalibrierung v2 nicht aktiv: 304 reale Vergleiche schlechter. Keinen Rendite-,
Verletzungs-, Wetter- oder Müdigkeitsnachweis aus QA ableiten. Separate reale
Quellenpool- und Shadow-Preisprovenienzprobleme bleiben offen. Neue Arbeit dort
anschließen, nicht erneut die sechs abgeschlossenen Reparaturen oder alle
QA-Vorläufe starten.

## Aktiver Einstieg – 13.10.2026: freigegebene Claude-Auditreparaturen

Zuerst obersten Block TODO_AKTUELL.md und
docs/audits/2026-10-13-claude-audit-reparaturen.md lesen. Autoritativer
Reparaturarbeitsstand: C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013,
Branch codex/audit-repairs-20261013, Ausgang c5a6264. Hauptcheckout hält frühere
unveröffentlichte WIP; NICHT resetten, breit stagen oder mit dieser Releasekopie
überschreiben. GitHub/VPS aktuell noch c5a6264; diese neue Reparatur nicht live.

Sechs freigegebene Bereiche lokal umgesetzt und unabhängig scoped geprüft:
Payout-Zweitbestätigung, immutable settled Tipps/quotenfreie BOOKMARK-Merkliste,
Decimal-Korridor, Tennis-Finish-Kausalität und gemeinsame one_set-Abrechnung,
getrennte versionsgenaue Kalibrierungs-/Effektverträge. 304 echte chronologische
Cachevergleiche waren für stärkere Kalibrierung v2 SCHLECHTER; v1/v14 bleibt aktiv.
Keine numerische Verbesserung oder aktive Verletzungswirkung daraus behaupten.

Gesamtprojekt-QA läuft noch mit Django siteconfig.qa_settings, in-memory DB und
externen Netzverbindungen gesperrt. Erstes unkonfiguriertes Collection-Ergebnis
ist kein PASS. Zweiter Vorlauf bei ca.10%gezielt beendet, KEIN PASS. Cricket-QA-
Vertrag mit unverändertem Fixturehash/LF und Cricket-Pfadprojektion korrigiert;
gemeinsame Mathematik/Cricket-Routing/Guard-Mutationen abgewiesen,7/7 PASS.
Finaler Gesamtaufruf full-project-final.log/xml endete korrekt bei echtem Fehler:
3386pass/25skip/117Untertests/1Fehler,1665,38s. Point-Schema2-Livereplay nun über
exakte statische neue Loaderkennung/gerichtete kompatible Owner repariert,
162/162Modul+unabhängig9/9ManifestePASS. Originale bleiben read-only.
Weitere reineWindows-QA-Ursache beseitigt: BashstdintextmodeCRLF und2hartgepinnte
SkriptdateienCRLFstattkanonischesLF. Testadapter3Aufrufer/LF-Attribute geändert,
Produkt-/Backup-/Stageinhalte/erwarteteHashes/Nicht-Bash-Calls unverändert.
354HookPASS,112Updater/ServerPASS+1vorhandenerLinuxflockSkip,3AdapterfällePASS.
B1endete2891pass/8skip/85Untertests/1Fehler603,59s;A1bei22%gestoppt,keinPASS.
Auch A2/B2 fehlgeschlagen, keinPASS: A2 2771pass/19skip/32Untertests/1Fehler,
1913,86s; B2 4835pass/8skip/111Untertests/1Fehler,1479,91s. AltesDaily3fixture
behaupteteCHF120RückzahlungbeiCHF50/Quote1,20; nurTesterstquote2,40korrigiert,
Wächter/Verlustlimitunverändert.87betroffene+alle251Daily3TestsPASS. Native-
QA-QuellenmitbestehendenLinuxPinsnurexaktLFkanonisiert, keinePin-/Gitblobänderung;
vollesChainModul65PASS; ganze7Modul-Protokollrunde271PASS/54bestehendeLinux-root-
Skips/0Fehler,148,56s. Alle13LFQuellenroh==HEAD==Index,Pinsunverändert.
AuchB3vollständigFehlbericht:7124PASS/39Skips/111Untertests/9Fehler1201,19s.
Genau2weitereLF-Pinpfade (nativePreparationWorker+LegacyTennisFixture) korrigiert,
Hashes/Gitblobsunverändert;226/226ganzeModulePASS3,41s.
A3vollständig4Fehler/6644PASS/58Skips/36Untertests2894,95s;JSON-ProbeCRLFund
alteMocksohneexpliziteslaw_version/save_source. NurexakteJSON-LFFormatierung
und2Mock-Signaturenmitv1/Herkunftsassertskorrigiert,Produktcode/Pinsunverändert.
188+13ganzeModulprüfungenPASS;B4vollständig7133PASS/39Skips/111Untertests/
0Fehler946,85s. A4komplettfrisch,keinGesamtPASSvorseinemAbschluss.
FinalerCode/Testindexb879d8d75ececc72848a3a2917bfab79959c8e95;gegenb841nur
2QA-Testdouble-Dateien/LF-Metadaten,alleProdukt-/B4-Test-Gitblobsunverändert.
ErneuerteVollcollection13878Haupttests/367Module;
A4/B4mit184/183disjunktenModulen,ohneAuslassung/Failfast/neueDependency.
check_complete_qa.pyprüftjedesHaupttestitemgenaueinmalund0Fehler.
Abschluss zählt nur diese Vollqualifikation, nicht überlappende Vorläufe. Danach
Abschlussstatus/Commit/Push/VPS-Nachweis ergänzen. Output separat unter
C:/Projekt/BetBoy/output/audit-repairs-20261013. Neue Storeverträge erlauben nach
Appstart keinen ungeprüften Old-Code-Rollback. Kein neues Backup, DB-Kopie oder
zusätzlicher Sportscan. Reale Kontext-Quellenpoolprobleme bleiben separate Arbeit.

Letzter statischer UI-Check fand noch den fehlenden Merken-Anschluss der manuellen
Tennissuche. Patch außerhalb Git unter output/audit-repairs-20261013/
manual-tennis-bookmark.patch, unabhängig statisch PASS. Eingefrorene A4/B4-Dateien
NICHT während des Laufs ändern. Nach A4: zuerst neue 9 Tests RED, Produktteil
anschließen, betroffene UI-/Tennis-/Merkliste-Module vollständig GREEN.
Diese letzte UI-Ergänzung separat qualifizieren, nicht rückwirkend der Vollsuite
von Index b879 zuschreiben. Native Ereignis-ID und echtes storage_scope; keine
Preis-/EV-Freigabe, Neuberechnung, Quote oder Einsatzerfindung.

RO-Vorprüfung: bestehender Fußball-Shadow partial/exit1 mangels akzeptierter
aktueller Bet365-Quote mit Providerzeit für1497716. Zwei alte abgerechnete Zeilen
haben invalid_quote_provenance/malformed_settlement; kein gültiger CLV/ROI.
Unabhängig gegen unveränderten c5a6264-Code bestätigt; keine Regression dieses
Pakets. Regulären Lauf beobachten, alte Originalbelege getrennt prüfen, weder
Evidenz löschen noch fehlende Quoten/Herkunft/Erfolgsstatus erfinden.

## Aktiver Einstieg – 13.10.2026: Kontextanschlüsse und exakte Release-QA

Vorrang: oberster Block `TODO_AKTUELL.md` und
`docs/audits/2026-10-13-kontextanschluesse.md`. Ausgang main/VPS6f86b31;
Codecommit5f175889c4058e65995ca358709b7499d3582fd7 aufmain/VPSlive14:13CEST.

Gezielte21-Dateien-Fußball-Closure: v2-Kadermerkmale im Worker/Transport,
tatsächliche spätere Kontextentscheidung mit physischer ORIGINAL-Uhr,
physische Readiness-Deduplizierung/Finalstreaming bei unveränderten Caps.
Vier Codeprüfungen PASS, gefrorene25-Modul-QA **663/663 bestanden**,
0 Fehler/Skips,3136,79s. Indexcode `af0d4d4b007d2a3a90ea9cfdb66e48a9d09959fb`,
isolierte vorhandene QA `C:/Projekt/BetBoy/.qa-tmp/release-3dea2d3`.
Großer203-Test inzwischen bestanden (Fit/Evaluator/Verify/Legacy-Fit-Gleichheit,
2Train/1Tune/200Final,keine Aktivierung). Kein Gesamtapp-/Qualitäts-PASS.

Neue203-Regressionskonfiguration korrigiert: Spielermerkmal war tatsächlich
fehlend; Owner lehnte Fit korrekt ab. Test nun belegtes `schedule.gap_hours_home`,
kein numerischer Verletzungseffekt. Produktionscode/Math/Caps unverändert.
Alter37-Modul-Lauf interrupted, exit1, kein JUnit/PASS. Nicht nachträglich grün
nennen oder zu anderen überlappenden Läufen addieren. XML/Taskberichte außerhalb
Git unter `C:/Projekt/BetBoy/output/context-integration-20261013`.
Entscheidende XML `frozen-corrected.xml`; 203-Roundtrip1820,03s,
Train/Tune-Cap-Verweigerung118,99s. Linux-Import/Health/App/Caddy/7Timer bestätigt,
ModellJSONs SHA-identisch,21GiB frei,keinBackup/zusätzlicherSportscan.

NEUE REALE RESTARBEIT:RO-Readiness acht native ORIGINALs,aber7/8 fallen am
einzelnen4MiB-Quellenpoollimit aus; nur1Quellenfall/Ergebnis auflösbar. Die drei
ausdrücklich geprüften Merkmale (v2Rosterverlust/v3gemeldete7dMinuten/Temperatur)
jeweils0vollständig. Keine Fits/Effekte/Freigaben. Mehr Rohspiele allein löst
dieses Poolproblem nicht. Ursache physisch/revisionsbedingt/unbenutzte Zweige
quantifizieren und danach ohneCap-Anhebung/Quellenverlust korrigieren. Kein
"alleKontexteffektefertig" oder künstlichesAktivieren behaupten.
Headerdiagnose:6Fälle97–100MB/36–37kReceipts,weitererFall4.533.002B/3046,
kleinerFall197.155B/130. WiederholteContentDigests0,unverbrauchteRaw-IDs0;
großeFälle auchüber4096Receipts. Rollen-/Revisions-Semantiknichtdekodiert;
gezielter vollständiger Streaming-/Projektionspfad ist nächsteRestarbeit,
kein einfachesphysischesDeduplizieren,keineCap-Anhebung/Quellenkürzung.

Alle101 realen Bindings stammen VOR der heutigen Capture-Reparatur. Rein
lesend:8native Spiele captured/93partial. Alte83 globale Budgetlabels sind
keine belegten83 echten pro-ID-Ausschlüsse. Nächster regulärer14.10.,03:35-
Lauf muss neue Zielpriorität/Gründe/Entscheidungsbelege erst beweisen. Kein
200-Fälle-Versprechen, keine rückwirkenden Quellenuhren oder Geldänderungen.

Enrichment-,Tennis-,15K-/andere Alt-WIP ausdrücklich nicht veröffentlichen.
Keine Backups/DB-Kopien/API-Zusatzscans/Budgeterhöhung. QA/Commit/Push/FF-Deploy/
Linux-Import/Health/RO-Inventur erledigt; reale Poolreparatur und qualifizierte
numerische Wirkung bleiben offen.

## Neuester Einstieg – 13.10.2026: Shadow-Historie und echte Capture-Lücken

Erster Block `TODO_AKTUELL.md` und Audit
`docs/audits/2026-10-13-shadow-historie-und-capture.md` haben Vorrang.
Frühere95 zählen nur native ORIGINAL-Bindings. Echte Produktionsinventur:
662 Fußball-SHADOW-Spiele,588 mit Ergebnis,84.025 Revisionen. Wiederholungen
und mehrere Märkte zählen NICHT als unabhängige Fälle.101 native Bindings,
8 captured/93 partial; Shadow enthält keine volle kalibrierte Torverteilung.
Deshalb vorhandene Grundmodelle bewerten, aber keine Müdigkeitsfreigabe vortäuschen.

Gezielte6-Dateien-Reparatur: aktuelle native NS/TBD/PST-Ziele vor älterer
Historie im gleichen Quellenbudget; tatsächliche Budgetausschlüsse pro Flush/ID;
Qualitätsreport verarbeitet Forecast-Payloads einzeln im Read-only-Snapshot.
267 isolierte Release-/Nachbartests,47 korrekte Portaltests bestanden;
unabhängiges Review ohne Befunde. Kein Vollsuite-PASS: nach behobenen reinen
QA-Zeilenenden bleibt der vorbestehende Hockey-`_variant`-AST-Freeze-Konflikt;
Cricket-Replaywerte sind bitgleich. Keine Produktiv-/Testfixtureänderung.

Codecommitd47c9b09903b9445541745a583e12c98552bc6bf ist auf main und VPS live,
13.10.,11:02CEST. Linux-Offline-Import,App/Caddy,7Timer und beide Healthchecks ok;
Modell-JSONs vor/nach SHA256-identisch. Echter RO-Report11:02:56CEST in10,423s,
84,965MiB Prozess-Peak:131 Gruppen/129 mit Scores.662 Fußballspiele/588 Ergebnisse,
241 Tennis/213 Ergebnisse,365E-Sport/354 Ergebnisse,7Hockey/0 Ergebnisse.
Entscheidungen nach Modell/Markt/Policy getrennt; kein gemeinsamer ROI-/Qualitäts-
Nachweis. Native Kontextwirkung weiterhin0. Rohsummen außerhalb Git unter
`output/football-history-shadow-20261013/quality-report-summary.json` (20 größte
Gruppen). Nachweis-Dokucommit ändert keinen funktionalen Code/keine Modelle.
Alte Publisher-/Kontext-/Tennis-WIP-
Änderungen bleiben UNVERÖFFENTLICHT. Keine neuen Backups, DB-Kopien, Zusatzscans,
höheren Budgets oder historischen Prognose-/Geldänderungen. Nächster regulärer
Capture-Lauf,3MiB-Originalgrenze und200 qualifizierte Kontext-Testspiele bleiben
eigene Abnahmen;0 numerische Effekte aktiv.

## Neuester Einstieg – 12.10.2026: Vereins-/Nationalteam-Spielerbelastung

Nutzerauftrag „machen“ nach Dortmund-/Nationalteam-Erholung. Einstieg erster
Block `TODO_AKTUELL.md`. Native Spieler-ID verbindet gemeldete Minuten beider
Teamarten; Rollenminuten bleiben vereinsspezifisch. v3-Lade-/Trainings-/Worker-
Verbindung und zeitlich korrekte Erholungsgrenzen umgesetzt, keine erfundenen
Abschläge. Detailpriorität bleibt im vorhandenen20-ID-/Ein-GET-Budget.
Unabhängiges Diffreview ohne kritischen/wichtigen Funktionsbefund. Exakter
isolierter Release-/Nachbarlauf273/273 bestanden,0 Skips,229,94s. Erste Runde
scheiterte nur an Windows-Sandbox-Hardlinkrechten für die HMAC-Testdatei;
komplette unveränderte Runde mit normalen Rechten bestanden. Netzwerk gesperrt.
Keine Gesamtapp-/Qualitätsfreigabe daraus ableiten.

Codecommit **99e771baee4f2bc115cf12a1d2426f4ea9812e26** ist auf main und VPS.
Linux-Import, App/Caddy, sieben vorhandene Timer und beide Healthchecks geprüft.
Gespeicherte Wettfinder-/RisikoBet-JSONs unverändert. Veröffentlichung nach dem
regulären15:02-Lauf, keine neue Sicherung/API-/Sportabfrage. Ein PowerShell-CR
am Deployskriptende löste einmal einen code-only Rückfall aus; Übertragung danach
korrigiert und vollständig erfolgreich. Kein Daten-Rollback.
Reale Workerprobe15:06CEST: `effect-unavailable`, `not_applied`, kein Snapshot.
Anschließender Dokucommit ändert ausschließlich diesen Nachweis, keinen Code.

**Nicht als volle Müdigkeitswirkung verkaufen:** reine Serverprobe12:40UTC
hat0 Effekte/0 Freigaben und0 tatsächliche Fußball-Spielendzeiten gezeigt.
381/470 bekannte Minuten in11 Ereignisproben; nationale Gesamtdeckung daraus
nicht ableitbar. Große Quellen können weiterhin512KiB-Transportlimit erreichen.
95 Fußball-Bindings insgesamt;81 kleine gelesen,33 native Ereignisse davon7
`captured`. Damit sind200 unberührte Testspiele zusätzlich zu Training und
Abstimmung derzeit nicht möglich. Nicht durch Mehrfachversionen auffüllen.
Qualifizierter Fit/owning Freigabe und reale Abdeckung bleiben offene Abnahme.
Altes v2-/Entscheidungs-/Tennis-WIP ist erhalten und nicht Teil dieses Releases.
Keine neuen Backups, DB-Kopien, zusätzlichen Sport-/API-Scans oder neuen APIs.

## Neuester Einstieg – 12.10.2026: Spielblöcke und Daily3

Die vom Nutzer beanstandete Öffnungslogik und leere Daily3-Teilmenge sind
live repariert. Einstieg erster Block `TODO_AKTUELL.md` und
`docs/audits/2026-10-12-daily3-und-spielbloecke.md`.
Modellwahrscheinlichkeiten, CHF50-Regeln, echte Vetos und bekannte Quote<1,20
bleiben unverändert. Erste drei sichtbare Spielblöcke öffnen initial, Nutzerwahl
bleibt spielgebunden. Daily3 behält reale >=70%-Vergleichsvarianten ohne2pp-
Pflichtbonus, Original-Tageskontext24h, chronologische echte Spielabstände.

Produktivpatch `3dea2d327cc47bf0418a607fede229e38221d82c` auf main und VPS,
beide Healthchecks ok. Ein anschließender Dokucommit enthält nur diesen Nachweis.
Genau dieser saubere Commit ohne fremde WIP:500 Release-/Nachbartests grün.
Weitere überlappende Runden:325/407 sowie89/51 und Portal47; nicht addieren.
Browser: initial erste drei Partien geöffnet, explizit geschlossene Partie
bleibt nach Wahrscheinlichkeit/Startzeit-Wechsel und Navigation geschlossen.
Daily3: gleicher gespeicherter Pool jetzt eine Auswahl IF Elfsborg–Halmstad
um19:00, 78,3%, letzte passende Quote1,64; keine Neuberechnung/Zusatzabfrage.
Keine neuen Browserfehler nach dem notwendigen App-Neustart. Die kurzzeitigen
502/Disconnects während dieses Neustarts sind als Deployereignis dokumentiert.
Breitenlauf bei rund23% beendet, kein Gesamtapp-PASS. AST-Freeze-Altbefund
betrifft veröffentlichten Hockey-Season-Zweig, nicht die bitgleichen Cricket-
Replays. Alte im Lauf geladene Daily3-Erwartungen separat frisch nachgeprüft.
Nächster gemeinsamer Release benötigt nach Behandlung dieses Altbefunds einen
frischen Volllauf; nicht die abgebrochene Runde als vollständig grün ausgeben.

ALLE nachfolgend beschriebenen Kontextmodell-WIP-Dateien bleiben erhalten und
unveröffentlicht. Nicht breit stagen oder mit dieser UI-/Daily3-Reparatur deployen.
Keine neuen Backups, Bereinigungen oder Sport-/API-Scans.

## Vorrang – 11.10.2026, Tokenende während Kontext-Datenanbindung

Auf ausdrücklichen Nutzerwunsch nur Übergabe sichern; Umsetzung pausiert.
Start direkt mit erstem Block `TODO_AKTUELL.md` und
`docs/audits/2026-10-11-kontext-datenpfade-uebergabe.md`.
Kanonischer Checkout `C:/Projekt/BetBoy/betboy-app`; letzte in dieser Sitzung
geprüfte veröffentlichte Basis lokal/main/VPS
`e9eea811b85b124b797c0d995b6cdbbe8187c6b5`.
**Alle neuen Produktivänderungen sind dirty/untracked, nicht released.**
Ein eventuell folgender Dokucommit ist KEIN Code-/VPS-Deployment.

Neue Arbeiten: ≤4 gemeinsame native Fußball-Detail-GETs im bestehenden Lauf,
physisch echte kompakte spätere Entscheidung erst nach ALLEN Originalbatches,
zwingender späterer Trainingsproof, Offline-Readiness/Trainingvorbereitung,
eigene v2-Kaderverlust-/Zuwachs-Exposition (alte v1 unverändert), separate
same-call POINT-Tennisoriginale samt nativem Finalscore-Leser ohne neue
Ergebniszeilen. Originaluhren, sourcecomplete und Restbudgets abgesichert.

**Zuerst zwei offene Anschlussprobleme beheben:**

1. `football_joint_worker.py` und `context_transport.py` erkennen noch kein
   v2-Pooling; eindeutigem Fit seine eigene geprüfte Featureversion geben.
2. Readiness-64-MiB-Gesamtlimit/mehrfache große Originale und 128-MiB-D2-
   Quellenlimit können eine echte 200-Testspiel-Kohorte verhindern.
   Offline-Streaming/Reuse mit tatsächlichem Speicherbedarf prüfen.

Danach Sourcefreeze und gemeinsame volle betroffene Module. POINT 329/329,
Enrichment 106/106, Deferred zuletzt 16/16, unabhängige v2-Poolrunde 10/10
bestanden; überlappende Runden nicht addieren. Unified-Exec 87305 beendet:
34 bestanden, 1 fehlgeschlagen, 369,05 s, Exit 1; alte Testbytes (bekannter
inzwischen reparierter Fixturefehler), kein finales Grün. Nach Wechsel
gefroren neu prüfen. Keine neue Vollsuite oder bessere Wettqualität bestätigt.

Vor finaler Abnahme KEIN Release der Dirtyquellen. Nur explizit stagen,
kein Reset/Clean, inherited output/untracked erhalten. Danach bestehend
autorisierter Commit/Push/VPS-FF ohne Backup/zusätzlichen Sportscan;
alter Deployhelper hat falsche Whitelist/Imports und muss angepasst werden.
Wesentliche weitere Arbeit (numerisch qualifizierter öffentlicher Fußball-
Pfad, POINT-Fit, echte Tenniszeiten/Verletzungen, 200 Testspiele, Rollen- und
Ersatzqualität, Hockey/Basketball-Effektkette) bleibt ehrlich offen.

## Neuester Einstieg – 11.10.2026, Abendfortsetzung

Der erste Block in `TODO_AKTUELL.md` und
`docs/audits/2026-10-11-kontext-abendfortsetzung.md` haben Vorrang.
Verifizierter Ausgang lokal/GitHub/VPS am Abend gemeinsam
`8dfabe964ad382ecc32a2a21ae4c48b926129458`. Neue lokale Reparaturen:
Fußball-Kader an wirklich verwendete native Modellspiele binden, auch gültige
Nullgewicht-Samples aus mathematischem Support ausschließen; Tennis zeigt die
neueste bekannte Ergebniskorrektur pro Quelle/Event/Tour statt des zufällig
ersten Modell-Elternsatzes. ATP/WTA nicht vermischen, keine Erholung erfinden.
Keine Wahrscheinlichkeits-/Quote-/Geldänderung durch die Tennisanzeige.
Finale gemeinsame Offline-QA: **1.039 bestanden, keine Fehler/Skips** in 25
ganzen Modulen, 700,86 s, Exit 0. Quell-/Testhashes vor/nach QA identisch.
Unabhängiger Review grün; überlappende Agentenzahlen nicht addieren. Kein neuer
Vollsuite-PASS behauptet. Reparaturcommit
`dccef90a86491709988bc5adebedebf580ccb78b` auf main gepusht und am 11.10.
gegen 20:13 CEST auf dem VPS live. Ein reiner Dokumentationscommit enthält
diese Abschlussnachweise. Offlineimports, Server-Git-/Quellbyteabgleich,
App/Caddy, sieben reguläre Timer und beide Healthchecks bestätigt; beide
Prognose-JSONs während Deployment bytegleich. Kein Timer-/Jobabbruch.
Shadow zuletzt weiterhin `partial` wegen frischer Bet365-Quote, alte zwei
Evidenzprobleme weiterhin erkannt. Tageslaufalter Timeout nicht als neuer
Erfolg darstellen. Tatsächliche numerische Effekte sind weiterhin offen.
Keine zusätzlichen Scans, Backups, Bereinigungen oder alten Belegänderungen.

**Nicht wieder als bloße Datenwartezeit darstellen:** Die produktive
Hockey-/Basketball-Quellenaufnahme und Originalveröffentlichung sowie deren
quellengebundener Fit, Ergebnis-Replay, Evaluator und Aktivierung fehlen noch.
`capture_team_sports_worker` und `build_hockey_live_original` haben keine
produktiven Aufrufer; der Live-Originalvertrag bleibt `unresolved`. D1/D2 kann
gegenwärtig nur Fußball/Tennis qualifizieren. Synthetische Funktionstests oder
zusätzliche Liga-Scanner sind kein Nachweis tatsächlich aktiver Kontexteffekte.
Tennis braucht außerdem eine echte Timing-/Verletzungsquelle und
point-kompatible Effekte statt Siegerkorrekturen auf dem Serve-Modell.
Fußball benötigt zusätzlich ausreichende unabhängige Abnahmedaten.
Die genaue minimale Ende-zu-Ende-Reihenfolge steht im neuen Auditbericht.

## Neuester Einstieg – 11.10.2026, Ausfälle und weitere Hockeyligen

Dieser Block und der erste Block von `TODO_AKTUELL.md` haben Vorrang.
Ausgang gemeinsam lokal/GitHub/VPS `4bd5da446c8e19ebc9151e9df7b2cf68fef7134a`.
**Code `090cf93a03cdf329774e6caac2458cd69b1d28f9` auf main gepusht und am
11.10. gegen 14:23 CEST auf dem VPS live.** Folgender reiner Dokumentationscommit
enthält diesen Nachweis, keine weiteren Produktivänderungen.
Neue Anbindung: eigene API-Hockey-Quelle, National League/Swiss League
zuerst, zwanzig Name/Land-Kandidaten inklusive vorhandener NHL; dynamische
native IDs und echte Periodenscores, gemeinsame Tages-/Suchanbindung, native
Quotenbindung und nur lesender Ergebnis-Cacheadapter. Noch kein Beleg realer
Accountfreischaltung oder zusätzlicher Liga-Kalibrierung. Acht Historiencalls
pro Lauf fair verteilt; kleiner begrenzter Cache, keine neue Zeitplanung.
Fußball-Target-Kaderfehler behoben und in 490 ganzen Nachbarfällen geprüft;
fremde historische Teams können belegte Zielspieler-Ausfälle nicht mehr
verdecken. Kein aktiver Effektkoeffizient dadurch behauptet.
Tennis: zwölf Produktionsbelege geprüft, echte Sätze/Games, keine gemessenen
Matchzeiten/Minuten/Verletzungen; keine reine Parserreparatur kann diese
fehlenden Quellen ersetzen. Acht vollständige Fußballbindungen reichen
nicht für die unabhängige 200-Testspiel-Freigabe. Null Fit ist nicht gemessene
Nullmerkmale. Letzter Code-QA-/Push-/Deploystatus steht ausschließlich im ersten
TODO-Block. Keine neuen Scans, Backups oder Geld-/Ergebnisänderungen.
Finale lokale Regression dieser Reparatur: **1.088 bestanden, ein vorhandener
Skip** in 26 ganzen Modulen, 68,12 s, Exit 0 (`release-05.xml` im externen
Outputordner `hockey-context-20261011`). Echter vollständiger Tagesartefakt-
Gegentest schützt gegen alte Publikationsuhren, inzwischen gestartete Spiele
und während langer Ladezeiten veraltete gespeicherte Quotes; kein neuer Abruf,
keine rückdatierten Empfangszeiten. E-Sport-24h-Anzeigegrenze separat abgesichert,
keine E-Sport-Tippfreigabe durch Preise. Unabhängige Reviews fertig; Git/VPS-
Veröffentlichungsnachweis im ersten TODO-Block: Offlineimports, App/Caddy,
sieben Timer und beide Healthchecks bestätigt. Modell-/RisikoBet-JSONs während
des Deploys bytegleich. Kein Sportjob unterbrochen, kein Backup/zusätzlicher
Scan gestartet. Reale Hockey-Account-/Ligaabdeckung erst im regulären Lauf
12.10.03:35 CEST prüfen. Alte Tages-Timeout-/Shadow-Teilstatus nicht beschönigen;
Tennis letzter Lauf erfolgreich. Belastbare numerische Kontexteffekte bleiben
wegen der oben genannten Daten-/Validierungslücken ausdrücklich offen.
Details: `docs/audits/2026-10-11-ausfaelle-hockey-anbindung.md`.

## Neuester Einstieg – 11.10.2026, Fortsetzung ab 10:38 Uhr

Ausgang lokal/GitHub/VPS `d26c1346ad727f825bc6639aeef4d48e13d43937`.
**Reparaturen `6474a376bb1a1029f419c7d774ed6d463221169d` sind auf main gepusht
und am 11.10. gegen 13:12 CEST auf dem VPS live.** Der folgende reine
Dokumentationscommit enthält den Nachweis, keinen weiteren Produktivcode.
Produktionsbelege stehen im neuen ersten Block von `TODO_AKTUELL.md` und
`docs/audits/2026-10-11-kontext-fortsetzung.md`. Keine alten Ergebnisse,
Geldbuchungen, Backups oder ungetrackte fremde Dateien ändern.

Fertige lokale Änderungen: gleicher kanonischer Receiptvertrag schneller,
terminale Tennis-Draw-Echos nur innerhalb eines Batches dedupliziert; realer
Fußball-Gegnerstärkevergleich im same-call-Publisher mit eigener Rezeptidentität
und maximal 16 KiB; NHL 2026/27 strikt gebunden; unmögliche Hockey-Gesamtsieg-
verteilungen am owning Datenvertrag abgelehnt. Bestehende Kundenschätzungen
bleiben gleich. Alter Football-Abrechnungsbericht ist nicht der aktuelle Code.

Die **ungefilterte Offline-Sportsuite ist vollständig beendet**:
`C:/Projekt/BetBoy/output/context-audit-20261011/full-04.xml`, 13.191 bestanden,
drei fehlgeschlagen, 97 vorhandene Skips und 115 Untertests bestanden,
54:25 Minuten. Kein einzelner fehlerfreier Vollsuite-PASS. Alle drei Fehler
waren veraltete Testfixtures, keine Produktionsfehler: zwei gemischte alte
Identitäten/neue Faktenanhänge und eine Gesamtzahl aller Selectboxes statt
konkreter Spielauswahl. Nur die beiden Testdateien korrigiert; authentische alte
IDs/Ganzpayload-SHA-Pins und alle Sichtbarkeitsassertions erhalten.
Ganze owning Module danach acht plus 16 Tests bestanden. Alle übrigen 725
eingefrorenen Dateien einschließlich sämtlicher Produktionsquellen bytegleich.
Finale kombinierte Regression in 13 kompletten Modulen: **619 bestanden,
sieben vorhandene Plattform-Skips**, 176,15 s, Exit 0,
`C:/Projekt/BetBoy/output/context-audit-20261011/release-neighbors.xml`.
Drei beendete Vorversuche kein PASS. Frühere Testadapterkorrekturen und echte
15K-/RisikoBet-AppTest-Vorschau ohne Exceptions oder Netzwerk-/DB-Versuch geprüft.
Der Vergleich
nutzt erst nach allen Original-Batches übrige Bytes; der Zwei-Batch-Fehler ist
unabhängig geschlossen. 60-Minuten-Reserve und geprüfte Unit-Allowlisten sind
live installiert, Timeout `1h` und exakter Unit-Hash bestätigt. Alle 12.706
Snapshots sind hash-/ID-kompatibel; separater Portalrunner 47 Tests grün.
Unabhängige Schlussprüfung: 24 Tests bestanden, kein Releaseblocker.
VPS-Fast-forward und Offline-Imports Exit 0, App/Caddy und beide Healthchecks
grün; sieben reguläre Timer aktiv, tägliches Backup deaktiviert. Beide
gespeicherten Prognose-JSONs bytegleich. Kein Backup, zusätzliche API-/Sport-
Abfrage, Ergebnis-/Geldänderung oder `reset-failed`.
Frischer interner Browser-Reload 13:13:38 CEST: gerenderte sieben Hauptbereiche,
sechs Sportfilter, Startzeit-Standard, keine neue Console-Warnung/-Fehler.
Neustartmeldungen separat; noch keine neuen Tageskarten bestätigt.
Vorbereiteter begrenzter Helfer außerhalb Git:
`C:/Projekt/BetBoy/output/context-audit-20261011/deploy.sh`.

Nicht als fertig darstellen: aktive neue Fußballrechnung, numerisch geprüfte
Verletzungs-/Wetter-/Müdigkeitseffekte, Top-20/Schweizer Hockeyabdeckung und
erfolgreicher nächster Gesamtlauf. Alter Tageslauf bleibt `failed/timeout`,
Shadow weiterhin ohne passenden aktuellen Providerpreis. Die frische Nutzerseite
zeigt deshalb noch kein automatisches Ergebnis; Deploy ist keine neue Berechnung.
Nur acht native vollständige Football-
Ereignisse; Tennis-Merkmalsprobe fehlen Zeit-/Dauergrenzen, Empfangszeit ist
kein Belastungseffekt. Reguläre nächste Jobs 12.10.00:05/03:35 CEST, keine
zusätzlichen API-Scans. Detaillierte Abnahmebedingungen sind genehmigt und
werden nicht durch erfundene Koeffizienten oder Softwaretests ersetzt.

## Neuester Einstieg – 11.10.2026, Abschluss 10 Uhr

**Code `5467b888b38fe0ed3b350471511d8bf2245351cc` ist gepusht und live.**
Ein folgender Dokumentationscommit ändert keinen Produktivcode. Hauptcheckout
`C:/Projekt/BetBoy/betboy-app`, main; vorhandene ungetrackte Arbeit erhalten.
Kein Backup, Zusatzscan, Löschen alter Prognosen oder Geldänderung.

Startzeit/optionale Wahrscheinlichkeit in den Empfehlungssichten umgesetzt,
Spielgruppen zusammen und Auswahlidentitäten bei Sortierwechsel unverändert.
Daily3 bleibt chronologisch; rohe Spielpläne bieten nur Startzeit. Hockey- und
Basketball-Erklärung exportiert Komponenten **eines** vorhandenen Fits; alte
Originalpakete/Modellwerte bleiben gleich, keine drei unabhängigen Belege.
Fußball-Terminrevisionen jetzt native ID/Teams/Start doppelt gebunden; verspätete
Modell- und Inputzeit werden abgelehnt. Zehn echte Tennislücken sind geänderte
Teilnehmer, getrennte Diagnose statt fremder Ergebniszuordnung. `partial`
bleibt sichtbar im Adminbericht, Originale/Geldbuchungen unverändert.
Readiness-SQL-Deadline und Rollback-Handler korrigiert.

Frisch kombiniert **1.517 bestanden, 36 Untertests, ein erwarteter Skip** in
34 Modulen, Exit 0; kein Vollsuite-PASS. Unabhängige Schlussreviews ohne weitere
konkrete Blocker. Interner Browser Desktop/390/320 und Sortierwechsel grün;
frische Produktionsseite mit Startzeit-Standard ohne Consolefehler geladen.
Fast-forward-Deploy Exit 0, App/Caddy und beide Healthchecks grün,
gespeicherte Wettfinder-/RisikoBet-Dateien bytegleich, sieben Timer aktiv.

**Nicht alles fertig:** heutiger Wettfinder hatte Timeout und die Live-Seite
zeigt keine neuen automatischen Ergebnisse. Nächster regulärer Vollscan
12.10.03:35 CEST; Tennis 12.10.00:05, inklusive getrenntem Teilnehmerkonflikt-
Zähler prüfen. Shadow weiter fehlende frische Bet365-Providerzeit und zwei
alte ungültige Evidenzzeilen; nicht löschen oder rückwirkend gültig machen.
Aktive Fußball-Gegnerstärke/qualifizierte Kontexteffekte weiter offen; heutige
VPS-Artefaktzählung enthält null Effect-/Approval-Artefakte. Schweiz/Top20-Hockey
und aktueller Saison-Kontextvertrag fehlen. Keine neue Liga oder Wirkung raten.

Fortsetzung über obersten [TODO-Block](TODO_AKTUELL.md) und
[Abnahmebericht](docs/audits/2026-10-11-sortierung-und-begruendung.md).

## Neuester Einstieg – 11.10.2026, fachlicher Gegnervergleich und Timeout

Ausgang lokal/GitHub/VPS `02943e9`. Heutiger Wettfinderlauf endete nach
45 Minuten mit Timeout, obwohl App/Healthchecks gesund sind. Neue echte
Formanhänge und beide Lader geprüft (129 Snapshots, 43 Kontextverweise, zwei
Formanhänge). Nicht den alten vollständigen Tageslauf als heutigen Erfolg melden.

Begrenzter fehlender Ergebnisindex und interne Phasenzeiten repariert;
199 direkte und 519 breitere Tests grün, sieben Windows-Symlink-Skips.
Keine Daten/Abrechnung/Modellkriterien verändert, kein Backup oder Zusatzscan.
Vollständigen Nachtlauf-Nachweis erst am normalen 12.10.03:35-Termin erheben.
**Codecommit `be1ecb3` gepusht und live**, Index auch in vorhandener VPS-DB
angelegt. Vier Tabellen-Zeilenzahlen und acht Schutztrigger unverändert;
Prognose-Dateien bytegleich, App/Timer/Healthchecks gesund. Nach abschließendem
CR-Transportfehler des Helfers tatsächlichen Zustand separat rein lesend geprüft;
Exit 127 deshalb nicht als fehlerfreien Helferlauf ausweisen.
Bei erneutem PowerShell-stdin-Transport `.TrimEnd([char[]]"`r`n")` verwenden.
Folgender Dokumentationscommit ändert keinen Produktivcode.

User lehnt künstliches Zählen von zwei positiven Argumenten ab. Neues
`football_opponent_strength.py` ist ein isolierter **Offline-Vergleich**, kein
aktivierter Forecast und keine nachgewiesene bessere Wettqualität. Fußball
braucht echten historischen Gegnervergleich; Hockey verwendet Angriff,
Defensive und Spielort bereits als gemeinsame Modellbasis. Alte 75/25- und
50/50-Rezepte nicht mit neuen Torwerten falsch weiterverwenden.
Native Liga-Belege 274/333 lokal für retrospektiven Vergleich vorhanden,
158 KB Spiel-/Ergebnisdaten, keine Secrets oder DB-Kopie. Individuelle
historische Ergebnis-Empfangszeiten fehlen: keine prospektive Qualität behaupten.
49 neue Modelltests und final 248 kombinierte Tests grün; zwei unabhängige
Reviews ohne offene Offline-Blocker. Echte Paarprobe: 72 aus 100 versuchten
Spielen, 28 mangels acht früherer Teamspiele ausgelassen. Brier/Logloss in
beiden vorhandenen Ligen niedriger; kein Beweis verbesserter aktiver Tipps.

Aktuellen Abschluss-/Veröffentlichungsstand im obersten TODO-Block und
[Prüfbericht](docs/audits/2026-10-11-auswahl-und-nachtlauf.md) nachlesen.
Verletzungs-/Müdigkeits-/Wetterwirkung, zehn Tennis-Ergebnisfälle, RisikoBet-
Abrechnungsmehrdeutigkeit, Sortierung und weitere Hockeyligen weiterhin offen.

## Aktueller Einstieg – strukturierte Teamsport-Form, 11.10.2026

Formrelease `fa42917` und Kontext-Laderfix `55f35e7` auf GitHub und VPS
(11.10.00:42 CEST). Ein nachfolgender Dokumentationscommit ändert keinen Code.
Der begrenzte Fix bewahrt echte
bereits verbrauchte Basketball-/Eishockey-Spiele bis zu den 5/10-Formkacheln.
Maximal zehn je Team, tatsächliche Endstände statt bereinigter Modelltorzahl,
exakte Quelle/Identität/Zeiten/Modellhash. Alter UI-Test hatte den Producerweg
umgangen; reale Adapter-/SQLite-/JSON-/Kartenregression jetzt vorhanden.
Neue Anzeigeanhänge erzeugen neue Revisionen; alte IDs und Payloadbytes bleiben
unverändert. 266 betroffene Tests + vier Untertests, 47 Portaltests und acht
unabhängige Transport-Gegentests grün. Interner Browser mit isolierten Testdaten
Desktop/390/320, Umschaltung und Gegnerliste ohne Fehler geprüft.

Vollsuite mit 13.015 gesammelten Tests beim 60-Sekunden-Faulthandler-Dump nativ
abgestürzt (`0xC0000005`), nicht als PASS gezählt. Exakter Einzeltest gleich
reproduziert; ohne rein diagnostischen Dump-Timer vollständig grün (103,31 s).
Kompletter Wiederholungslauf ohne periodischen Dump beendet: 12.909 bestanden,
neun Testaufbaufehler, 97 Skips, 115 Untertests, Exit 1 (52:13 min). Alle neun
Quelle-/Wettbewerbsmutationen behielten den ursprünglich gebundenen Anhang;
korrekte frühzeitige Domain-Ablehnung. Nur die absichtlich fremde Fixture
korrigiert, neun zusätzliche frühe Ablehnungsfälle ergänzt; Produktionscode und
Guards unverändert. Ganze geänderte Testdatei + betroffene Module frisch:
586 bestanden, Exit 0 (20,04 s); unabhängiger Review ohne weiteren Befund.
Keinen einteiligen Vollsuite-PASS aus diesen getrennten Läufen behaupten.
Formrelease veröffentlicht ohne Backup/API-Scan/Migration; regulärer Tennisjob
beendete sich 11.10.00:32:29 CEST erfolgreich, Exit 0. App/Caddy aktiv und beide
Healthchecks `ok`; veröffentlichte Prognosedateien bytegleich.
Zusätzlicher echter Snapshotcheck fand einen bereits im Vorgänger enthaltenen
Fehler: `riskobet_automation.snapshot_from_dict` übernahm `context_ref` nicht;
die korrekte ID-Prüfung lehnte dadurch gespeicherte Daten ab. Zwei Codezeilen
ergänzt, keinerlei Lockerung der Integritätsprüfung. 13 neue Regressionen
zuerst neun rot/vier grün; frisch 728 betroffene Offline-Tests bestanden
(83,26 s), danach nichtleerer Faktor-Roundtrip ergänzt und ganze geänderte
Testdatei erneut 32 bestanden. Ergänzung gepusht/deployt; echter reiner Lesecheck
über beide Lader auf allen 151 gespeicherten Snapshots bestanden, davon 38 mit
Kontextverweis. IDs und veröffentlichte Prognose-Dateien unverändert. Kein behaupteter
einteiliger grüner Vollsuite-Lauf nach diesem zusätzlichen Codefix.
Neue Formdaten erst nach dem
normalen Modelllauf. Keine rückwirkende BOS-Historie erfinden. Aktuellen Status
im obersten [TODO-Block](TODO_AKTUELL.md) und im
[Prüfbericht](docs/audits/2026-10-10-teamsport-formtransport.md) nachlesen.
Alle geerbten ungetrackten Dateien unverändert erhalten.

Letzter echter Nachcheck 00:42:56 CEST: App/Caddy aktiv, beide Healthchecks `ok`,
sieben reguläre Timer aktiv/aktiviert, Backup inaktiv/deaktiviert. Tennis
82/82 verarbeitet, 74 neue Prognosen, Exit 0; zehn native Ergebnislücken bleiben.
Shadow 00:42:09–00:42:10 Exit 0 (kein Nachweis, dass alte Preislücke nachgeholt).
Älterer Wettfinderlauf weiter `degraded`: RisikoBet-Abrechnung
`football:event_snapshot_ambiguous`, 136 terminal/272 ungelöst. Separat klären,
nicht als Form-/Kontextladerfehler behandeln oder Ergebnisse erfinden.
Aktuelle publizierte Snapshots haben noch keinen neuen Formanhang (0/151),
denn seit Release lief kein neuer Modellscan. Nächster regulärer Wettfinder:
11.10.03:35 CEST, kein zusätzlicher Scan gestartet.
Frischer interner Browsercheck nach Unterbrechung nicht bestätigt: Webview
nicht anbinden, Panelöffnung nur `queued`. Frühere isolierte UI-QA gilt separat.

## Aktueller Einstieg – Eishockey-Kurzcheck / BOS–PHI, 10.10.2026

Der alte Stand 04:12 CEST hatte Eishockeypreise vor dem Producer-Fix ausgeschaltet.
Ein ausdrücklich begrenzter Preis-only-Check für NHL-Ereignis `2026020070` lieferte
Boston 1,75 / Philadelphia 2,25 ohne Fehler. Kein Modell-/Sportscan; gespeicherte
Wettfinder-/RisikoBet-Prognosen bytegleich. Neuer Kurzcheck erklärt ausgewählte
Seite und Gegner: 3,09 gegenüber 2,60 erwarteten Toren in regulärer Spielzeit,
Abstand 0,49; Gesamtsiegerchance unverändert 57,7 %, Gegenseite 42,3 %.
Exakt gebundene NHL-Vollnamen nur in der Anzeige, Originalidentitäten/Quoten-
Zuordnung unangetastet. Keine zusätzlichen Verletzungs-/Formvorteile behaupten.
Auch `St. Louis Blues` darf nicht am Abkürzungspunkt abgeschnitten werden.
677 frische Tests plus vier Untertests bestanden; unabhängiger finaler Review
ohne konkrete P1/P2. Code `8d97a61` auf main und VPS live (10.10. 13:12 CEST),
beide Healthchecks ok, App/Caddy aktiv; Prognose-Dateien bytegleich.
Frischer interner Produktionsbrowser bestätigt beide Vollnamen, 57,7 %, Quote
1,75, Kurzcheck und Gegenargument 42,3 %. 1280/390/320 Pixel ohne Seitenüberlauf,
keine neuen Konsolefehler nach Reload; Restart-Verbindungsfehler separat.
Ergänzende Sportsuite außerhalb der Windows-Sandbox bei 8 % ohne ausgegebenen
Fehler gestoppt; keine QA-Prozesse mehr aktiv. Erster Dateirechtefehler dort
isoliert grün. Portal-Gesamtsammlung wegen fehlender Django-Abhängigkeit
blockiert, keine grüne Vollsuite behaupten. Dieser reine Dokumentationsnachtrag
kann einen neueren HEAD als Code `8d97a61` haben.
Separate offene Formpersistenz für Eishockey/Basketball und vorherige Sortier- /
Ligaabdeckungsanfrage im obersten TODO-Block dokumentiert. Kein neues Backup,
keine Bereinigung, Migration oder Geldbewegung.

## Aktueller Einstieg – Quotenversorgung, 10.10.2026

Nach Hauptnavigation/Preisfiltern den wirklichen Abruf repariert: voller
zuordenbarer Fußballpool statt zehn Fixtures; native Tennis-Gegenpreise für
1.200 Ereignisse statt zehn; manuelle Tennis-Suche mit realem einmaligem H2H-
Batch und Sitzungsfenster; DC-Aliase 1X/X2/12; tatsächliche Empfangs-/Abschluss-
uhren; bestehende E-Sport-/Teamsport-Preisproducer wieder verbunden. Kein
Modell-/Richtungs-/Konteneingriff, Cricket unverändert, keine Secret-Ausgabe.
Nach allen Änderungen 724 frische Tests bestanden (39,30 s); unabhängiger
Abschlussreview ohne offene konkrete P1/P2, zehn getrennte Gegenchecks grün.
Code `92cb4d2` auf main und VPS live (10.10. 12:43 CEST). App/Caddy,
beide Healthchecks ok, sieben Timer geplant, gespeicherte Modell-/RisikoBet-
Artefakte bytegleich. Interner Produktionsbrowser mit Tennis und aktivem
Preisfilter per Tastatur geprüft; kein neuer Fehler nach Seitenaufbau.
Native Mausbedienung nicht bestätigt. Dokumentations-HEAD kann neuer sein.
Keine neue Sicherung, Produktions-Sport-/API-Abfrage, Migration oder Bereinigung.
Die gespeicherten alten Preise werden beim Code-Deploy nicht plötzlich frisch.
Echte neue Providerantworten erst im normalen Lauf / expliziter manueller Suche.
Zehn Fußballdefinitionen ohne verifiziertes Mapping und Anbieter ohne aktuelles
exaktes Angebot bleiben offene Abdeckung, niemals erfundene Ersatzquoten.
Geerbte Vollsuite beendet: 12.810 bestanden / zwei UI-Testaufbaufehler /
97 Skips / 143 Untertests. Beide Originalfälle in frischer 724er-Runde grün;
keine grüne Vollsuite des finalen veränderten Checkouts behaupten.
Altfehler aus alter Funktionszeile exakt per identischem Skripthash nachgewiesen:
gemischter Quelltext, nicht Produktivcode. Nächster Wettfinder 11.10. 03:35 CEST.
Zuerst obersten [TODO-Block](TODO_AKTUELL.md) und
[Quoten-Prüfbericht](docs/audits/2026-10-10-quotenversorgung.md) lesen.

## Aktueller Einstieg – Hauptmenüs / Manuelle Suche, 10.10.2026

Neueste Freigabe: sichtbare Hauptmenüs statt „Bereich“-Dropdown. Wettfinder,
Manuelle Suche, RisikoBet, 3 a day, 15K, Live, Meine Tipps; Mobil dieselbe
einzeilige scrollbare Navigation. Ältere Bereichsauswahl unten ist überholt.
Manuelle Suche filtert vorhandene Modellprognosen nach Prozent und Wettart,
optional nach exakt gebundener tatsächlicher Quote ab 1,20. Fehlende/fremde/alte
Preise sind bei aktivem Quotenfilter keine Treffer. Filter ändern keine Modelle,
Richtungen, Rangfolge, Prognosen oder Konten und starten keine neuen Scans.
382 frische Tests und unabhängiger Abschlussreview ohne offene konkrete P1/P2;
echter interner Browser 1440/390/320 und Tastatur/Filter geprüft. Vollsuite läuft.
Code `f01e83e` auf main und VPS live; Produktionsseite 1440/390/320, Tastatur,
Rückwechsel und neue Filtercontrols geprüft, keine neuen Browserfehler nach Reload.
App/Caddy und beide Healthchecks ok, sieben Timer geplant. Gespeicherte
Wettfinder-/RisikoBet-Prognosen bytegleich. Kein zusätzlicher Sportscan/Backup.
Die ergänzende Vollsuite läuft am 10.10. um 12:09 bei 24 % ohne ausgegebenen
Fehler weiter; Log `C:/Projekt/BetBoy/output/manual-navigation-20261010/fullsuite.log`.
Nicht als grüne Vollsuite darstellen; 382 frische betroffene Tests sind grün.
Vorhandene Wettfinder-/Football-Shadow-Fehlzustände separat offen. Dieser
Dokumentationsnachtrag darf einen neueren HEAD als den Codecommit haben.
Zuerst obersten [TODO-Block](TODO_AKTUELL.md) und
[Prüfbericht](docs/audits/2026-10-10-hauptnavigation-manuelle-filter.md) lesen.
Kein neues Backup, Produktionsscan, Migration oder Bereinigung für diesen Patch.
Alle geerbten ungetrackten Dateien erhalten; separate fachliche Aufgaben offen.

## Aktueller Einstieg – Gemeinsames Dach, 10.10.2026

Freigegeben: eine gleichrangige Bereichsauswahl für Automatisch, Eigene Suche,
RisikoBet, 3 a day, 15K, Live und Meine Tipps. Navigation und eindeutige
Gegenrisiken implementiert; angrenzende TOP-Prüfungen erhalten Modellrichtung,
Original-Kontextzeiten und tatsächliche exakte Preisversuche. Offene Aufstellungen
allein sperren nicht. Wahrscheinlichkeiten und Geldlogik unverändert.

Unabhängiger finaler Review ohne offene konkrete P1/P2; lokaler interner Browser
1440/390/320 ohne Überlauf, alle sieben Bereiche und Tastatur geprüft.
Vollsuite beendet: 12.683 bestanden, 50 ursprüngliche Fehler, 97 Skips,
143 Untertests. Alle 50 Fehlerfälle gemeinsam nachgeprüft und grün (46 falscher
Windows-Bash, vier Test-Schnittstellen/Belege präzisiert; Produktionscode stabil).
Veröffentlichung und echte Produktionsbrowserprüfung abgeschlossen:
Hauptcode `ea4c6a9`, finale Beschriftung `548b283` auf GitHub main und VPS.
Alle sieben Bereiche besucht, genau eine „Bereich“-Auswahl; persönlicher
Sammlungsfilter heißt „Tippquelle“. Echte Renderer-Regression: 116 bestanden,
unabhängiger Nachreview ohne konkrete P1/P2. Desktop/Mobil 1440/390/320 und
Tastatur ohne Seitenüberlauf geprüft, keine neuen Browserfehler nach Reload.
App/Caddy und alle sieben Timer aktiv, beide Healthchecks ok; gespeicherte
Wettfinder-/RisikoBet-Prognosen während Deployments unverändert. Dokumentations-
Fast-forward darf einen neueren HEAD haben, ohne erneuten Appneustart.
Vorhandener Wettfinder-Dienstfehlstatus bleibt eine separate offene Datenaufgabe.
Zuerst obersten [TODO-Block](TODO_AKTUELL.md) und
[Prüfbericht](docs/audits/2026-10-10-gemeinsame-bereiche.md) lesen.
Kein zusätzlicher Sport-/Modellscan, Backup oder Bereinigung für diesen Patch.
Geerbtes WIP und separate fachliche/Domain-/Stripe-/Store-Aufgaben bleiben erhalten.

## Aktueller Einstieg – Tennis-Quotenfilter, 10.10.2026

Der unterbrochene Alcaraz-Fix ist abgeschlossen: Code `097f4fa` auf main und
BetBoy-VPS live. Ursache war das Zehn-Ereignis-Limit im Tennis-Preisabruf;
Alcaraz war Spiel 15 von 16. Jetzt voller begrenzter Tagesbatch und Erhalt
exakter alter Niedrigquoten bei erfolglosen/fremden neuen Antworten.
352 betroffene Tests bestanden, unabhängiger Review und Linux-Offline-Replay.
Echter einmaliger Quotenlauf um 08:43 Europe/Zurich: acht bevorstehende Spiele,
acht Preise, null Fehler, nur ein Credit; Alcaraz-Bestquote 1,05 korrekt unter
1,20 ausgefiltert. Tatsächlicher Katalog und interner Browser/Daily3-Kurzliste
bestätigt; Modelle und Originalzeiten unverändert, keine Geldbuchung.
App/Caddy und beide Healthchecks ok. Keine neuen Backups/Scans/Bereinigungen.
[Aktuelle To-do-Liste](TODO_AKTUELL.md) und
[Produktionsnachweis](docs/audits/2026-10-10-tennis-quotenfilter.md) zuerst lesen.
Separater Wettfinder-Fehlstatus, Daily3-Zeitplanung, Kontextmodelle, Domainumzug,
Stripe und Store-Release bleiben offen. Geerbtes ungetracktes WIP erhalten.

## Aktueller Einstieg – 15K Sports Editorial, 09.10.2026

15K-Karten sind an den gemeinsamen Wettfinder-Renderer angeschlossen:
Vereinslogos, kurze Fakten und gespeicherte letzte 5/10 Spiele mit Gegnern.
Geld-/Ticketlogik unverändert; Originalbelege bleiben spiel-/markt-/modellgebunden.
Maßgeblich: oberster [TODO-Block](TODO_AKTUELL.md) und
[15K-Prüfbericht](docs/audits/2026-10-09-15k-editorial.md).
UI-Code `a96a932` ist auf main und VPS veröffentlicht. **460 Tests und 85
Untertests** bestanden; unabhängiger Review ohne offene Befunde im UI-Scope.
Echte Produktionskarten mit sechs geladenen Vereinslogos und vorhandener
5-/10-Spiele-Form geprüft; Moreirense hat im bestehenden Beleg keine gültige
Ergebnisliste. 1440/390/320 ohne horizontalen Überlauf, keine Browserfehler;
Healthchecks ok. Keine neuen Sportscans/Backups oder Prognoseänderungen.
Abschlussbelege im verlinkten Prüfbericht; Dokumentations-Fast-forward erfordert
keinen weiteren Appneustart, da der UI-Code bereits geladen ist.
Domain-/Stripe-/Modell-/Scanner-Aufgaben unten nicht pauschal als erledigt ansehen.

## Aktueller Einstieg Domainumzug und Accountwechsel 07.10.2026

Zuerst [vollständige aktuelle Übergabe](docs/handoffs/2026-10-07-domainumzug.md)
und den obersten [TODO-Block](TODO_AKTUELL.md) lesen. Enthalten sind Kostenvergleich,
echter netcup-Warenkorb, Bestand und verbindliche Reihenfolge der Fortsetzung.
Der Umzug ist vorbereitet, **nicht gekauft oder durchgeführt**. Lokale Inventur
und [Umzugs-To-do](<C:/Projekt/BetBoy/output/domain-migration-20261006/TODO_AKTUELL.md>)
liegen außerhalb von Git unter `C:\Projekt\BetBoy\output\domain-migration-20261006`;
bei Accountwechsel auf diesem PC weiter verfügbar, bei PC-Wechsel separat beachten.

Keine App-/VPS-Änderung, Datenkopie, DNS-Umstellung, Kündigung oder neues Backup
in dieser Übergabe. Stripe-/Landingpage-/Scanner-/Store-Aufgaben darunter bleiben
separat offen; die alten Produktionsnachweise sind keine frische Serverprüfung.

## Aktueller Einstieg – Stripe-Live-Katalog und Billing, 06.10.2026

BetBoy-Live-Konto aktiv; drei bestätigte Monatsabos CHF 9.90 / 19.90 / 29.90
im **internen** Browser angelegt und je Preis inklusive Steuer geprüft.
Produktsteuerkategorie `txcd_10103000` ausdrücklich freigegeben. IDs und Belege:
[Stripe-Einrichtung](docs/audits/2026-10-06-stripe-live-setup.md).
Keine erneute externe OAuth-Anmeldung oder neue Produkte doppelt erzeugen.

Billing unterstützt passende Restricted Keys, dynamische Zahlungsmethoden,
stabilen Flow-Tag und v2-Idempotenz. **47 Portaltests** bestanden; unabhängiges
Review ohne offene P0–P2 im Patch. Das ist keine Live-Zahlungs-/Mail-Abnahme.

Verkauf bleibt geschlossen: Portalservice/geschützte Konfiguration fehlen;
Domain und SMTP im Chat erfragt. Nutzer muss neuen Schlüssel selbst erstellen/
geschützt speichern. Keine Secrets im Chat/Git, keine neue Sicherung/Sportscans.
Pre-Payment-Länderschutz, Steuersituation, Recht und deployed E2E/Reconciliation
noch offen; keine scheinbare Reparatur mit Versandfilter oder Länder-Dropdown.
Maßgeblich ist der oberste [TODO-Block](TODO_AKTUELL.md).

Code-/Einrichtungscommit `47a5580` wurde auf `main` gepusht und auf dem VPS
unter Deploylock exakt per Fast-forward übernommen. App/Caddy und beide
Healthchecks danach gut; kein Dienstneustart/Scan/Backup. Portalservice weiterhin
fehlend, Kundenverkauf/Landingpage nicht öffentlich aktiviert. Nachfolger nur Docs.

## Aktueller Einstieg – Landingpage umgesetzt, 06.10.2026

Der kombinierte Entwurf wurde vom Nutzer ausdrücklich freigegeben und im
vorhandenen Django-Portal umgesetzt. Produktcode `a8188f8` auf `main` gepusht.
DE/EN inklusive Bildbeschriftungen, drei Schritte, Monatsbilanz vor drei CHF-Abos,
natürliches Smartphone; keine bedienbare Gratis-Produktdemo.

43 Portaltests frisch grün; Desktop/Tablet/Mobil 1440 bis 320 px, Navigation,
Sprachwechsel, Menü/Fokus und Tarif-/Login-GETs geprüft. Voller Nachweis:
[Design-QA](design-qa.md), [Umsetzung/Assets/lokaler Start](docs/design/landingpage-20261006/implementation.md).
Neue Laufzeitassets insgesamt 1.128.615 Bytes, responsive WebPs und lokale Fonts.
Vorschau <http://127.0.0.1:8010/de/> / <http://127.0.0.1:8010/en/>.

**Nicht auf dem VPS deployed, Verkauf weiterhin Pre-launch.** Keine echten
Zahlungen/Kundenregistrierungen, Scans oder Backups; bestehendes WIP erhalten.
Letzter VPS-Status darunter ist historisch, nicht durch diese Tests bestätigt.
Monatsbilanz ohne belegte Zahlen; Stripe/SMTP/Recht/Proxy/E2E/Reconciliation,
native Stores und Modell-/Scanner-Restarbeiten separat offen.
Aktuelle Prioritäten in [TODO_AKTUELL.md](TODO_AKTUELL.md) und
[Claude-Übergabe](CLAUDE_UEBERGABE_2026-10-06.md). Keine erneute Designfreigabe nötig.

## Aktueller Einstieg – Übergabe an Claude, 06.10.2026

Historischer Vor-Freigabe-Stand; der neue oberste Abschnitt ersetzt seinen
Landingpage-Status.

**Zuerst lesen:** [Claude-Übergabe mit Zusammenfassung/To-do](CLAUDE_UEBERGABE_2026-10-06.md)
und den neuen obersten [TODO-Block](TODO_AKTUELL.md).
Ältere Abschnitte darunter bleiben historische Belege; nicht alte Worktrees,
Test-PIDs oder angebliche offene Releases blind wiederaufnehmen.

Vor dem reinen Übergabecommit lokal/GitHub-main/VPS frisch identisch:
`5a5e1b1a6b18d93211164b96193c7d909564af8b`; App/Caddy und Healthchecks funktionieren.
**Heutiger Wettfinderlauf Exit 1**, Tennis/E-Sport technisch Exit 0; nicht alle
Scanner pauschal als erfolgreich melden. Portalservice und Portal-Konfiguration
fehlen auf VPS, also kein live geschalteter Stripe-Kundenverkauf.

Aktueller Designauftrag: **Variante 1 Sports Editorial**, Handy-Proportionen
repariert; danach Drei-Schritte-Abschnitt aus Variante 3 → Monatsbilanz September
2026 → drei Abos. [Kombinierter Entwurf](docs/design/landingpage-20261006/selected-remix.png)
ist vorhanden/gezeigt, **noch nicht abschließend bestätigt oder umgesetzt**.
Keine bedienbare kostenlose Landingpage-Vorschau, statische Produktbilder erlaubt.
Keine belegte 74-%-Monatsquote; diese war ein Beispiel, keine verwendbare Kennzahl.

Drei Bilder dauerhaft im Repository unter `docs/design/landingpage-20261006/`,
zusammen 5.485.849 Bytes. Nutzerpreise CHF 9.90 / 19.90 / 29.90 monatlich bestätigt;
gleiche Modellqualität. Native Apps/Store-Billing/Signierung/Abnahme weiterhin offen.

Speicherbereinigung vom 05.10. beendet: 70 genehmigte alte VPS-ZIPs und 56
synthetische lokale Testdateien entfernt; neueste reguläre Sicherung erhalten,
keine Produktions-DB gelöscht. Details/negative Befunde in Claude-Übergabe und
`output/storage-audit-20261005/`. Keine neue Sicherung/Scan/Bereinigung starten.

In diesem Übergabeschritt nur Dokumente und Bildreferenzen, kein App-/VPS-Update.
Nach einem Dokumentations-Push kann der VPS weiterhin `5a5e1b1` sein, ohne dass
App-Code fehlt. Nicht allein für diese Übergabe Dienste stoppen oder deployen.

## Aktueller Einstieg – Wiederaufnahme, 04.10.2026 ab 10:32 CEST

Der Nutzer hat die Weiterarbeit freigegeben; die reine Übergabepause unten ist
beendet. Maßgeblich ist wieder der oberste [TODO-Block](TODO_AKTUELL.md).
Alte Vollsuite vollständig beendet: 12.358 pass, 97 skip, ein Timeout-Fail,
111 erfolgreiche Untertests. Kein noch laufender Test unter den unten genannten PIDs.
SQL-Fristlücke mit expliziten Zwischenprüfungen und deterministischen Tests repariert;
129 betroffene Tests plus unabhängiges Gegenreview grün (überlappende Mengen).
NHL-Belege sind vorhanden, aber ihre Identität ging auf dem Weg zur Archivkarte
verloren. Enger Snapshot-/Publisherfix verbindet neue Veröffentlichungen, ohne
Altarchive umzuschreiben. Basketball-ESPN-Provider im Bericht korrekt ergänzt.
Der eigene Hockey-/Basketball-Endergebnispfad bleibt trotzdem separat offen.
Neuer Codefreeze `ecda9e9f053e44429810d7da53e2ce74a5e7785b`; Vollsuite
vollständig abgeschlossen mit Exit 0: **12.474 bestanden, 97 unveränderte
Skips, 111 Untertests bestanden**, 2.908,24 Sekunden. Abschluss-XML
`output/playwright/full-continuation-20261004.xml`, SHA256
`6e6edf1a1299920306e877eb49cb7149a33391e7689556effb564c4351af2bd5`.
12.571 eindeutige Haupt-IDs unabhängig bestätigt, alter Timeoutfail jetzt PASS.
Session `9885`/PIDs `410372`/`414600` beendet; keinen weiteren Lauf starten.
Produktiv-/Testcode während der Suite unverändert, Nachfolger nur Dokumentation.
250/237 gezielte Tests überlappen; Releasehülle offline und unabhängig geprüft.
**VPS-Deployment abgeschlossen, 04.10. etwa 11:36 CEST:**
`e14deea2911369124e291020f140763df6226d57`, ff-only unter Deploylock und mit
Linux-Offline-QA vor App-Stopp; App/Caddy aktiv, beide Healthchecks `ok`.
Modellartefakte beim Pull bytegleich, kein neues Backup. Anschließende
Dokumentationsnachfolger enthalten keinen neuen Produktiv-/Testcode.
Echte NHL-Sourcebindung für beide eingefrorenen Prognosen read-only bestätigt;
sichtbarer Spielblock bleibt eine Auswahl, kein Altarchiv-Backfill. Live-Kurzcheck
Greece/Germany zeigt die passende Torbedingung 5/5 · 7/10 plus korrekte
12/12-A-Länderspiel-Basis. 10-Spiele-Umschaltung und Schließen wirklich geprüft;
1280/390/320 px ohne horizontalen Überlauf, keine neuen Browserfehler nach
frischem Reload. Eigener interner Tab geschlossen, Viewport zurückgesetzt.
Der nächste Ergebnisadapter kann den vorhandenen
Cache nutzen (55 EuroLeague-/1.620 NHL-Versionen auf VPS), nicht neue APIs/DBs.
Keine Zusatz-API-Scans, Cleanup, Modell-Neurechnung oder Geldänderungen.

Aktueller Produktions-Gegencheck: Die heutigen fehlgeschlagenen Jobs liefen
noch auf `25e79a5`. Erst 09:25:30 CEST wurde `7e5ef87` gepullt. Der alte Reader
scheiterte am tatsächlichen Schema-2-Zusatzfeld `market_model_version`; alle
acht damals geeigneten ATP-Siegerrows werden vom aktuellen Headervertrag
read-only akzeptiert. Kein neu offener Fix dafür, aber auch kein neuer grüner
Tageslauf. Heute 25 neue Tennisoriginale versus 84 Modellrevisionen, nicht
109 Tipps. Die vollständigen Tennis-Abschlussfehler/`unresolved_outcome_events`
sind wegen 2.500-Zeichen-Logtail nicht nachweisbar; Detail im obersten TODO.

## Aktueller Einstieg – Accountwechsel, 04.10.2026, 10:06 CEST

Der Nutzer hat den geplanten Zweistundenblock vorzeitig für diese Übergabe
unterbrochen. Nicht als vollständig abgearbeitet oder als fertige App melden.
Oberster
[TODO-Block](TODO_AKTUELL.md) und der
[exakte Replaybericht](docs/audits/2026-10-04-greece-germany-replay.md) sind
maßgeblich; die unteren Abschnitte sind historische Momentaufnahmen.

Codefreeze lokal: **`00b43693b7e0261147e5b75d69ea06f26860bd7d`**.
GitHub main und VPS beim frischen Übergabeabgleich noch
**`7e5ef8718839073b4c496f1066ecd10f4f9c82fe`**. Code und Übergabe danach als
`2c49c3a62378090857b4c8e5f259436ea21b5039` gepusht und Remote frisch bestätigt;
der nächste reine Dokumentationsnachfolger ergänzt diese Abschlussnotiz.
**Nicht deployed**; VPS bleibt `7e5ef87`.
VPS-Readerrelease am 04.10. 07:25 UTC übernommen; App/Caddy aktiv und beide
Healthchecks `ok`. Neue Korrekturen also noch nicht live. SHA immer neu abgleichen.

**Vollsuite läuft weiter**, seit 09:49:30 CEST, letzter Stand 23 %, kein PASS:
Session `96947`, Windows-PIDs `266900`/`269476`, JUnit-Abschlussdatei
`output/playwright/full-00b4369-20261004.xml` noch nicht vorhanden.
Keine zweite Suite starten oder getestete Dateien ändern, solange dieser Lauf
aktiv ist. PC weiterlaufen lassen; Prozessidentität neu prüfen. Bei Accountwechsel
ist die Session eventuell nicht zugänglich, deshalb PID/JUnit verwenden.
240 gezielte Integrationstests und unabhängige Reviews (192/188) grün;
überlappende Mengen nicht addieren, keine vollständige Suite daraus ableiten.

Greece/Germany tatsächlich gerechnet, 71,9733 % und 1,8571 Germany-Tore exakt
nachvollzogen. Die Fünferansicht allein zeigt nicht alle 12/6-Modelleingänge.
Neue marktbezogene Formfakten, Historien-Revisionsschutz und unveränderte
WTA-Altoriginal-Klassifikation sowie begrenzte Capturediagnostik sind committed
und unabhängig geprüft. Lokale Karten 320/390/1440 px ohne Überlauf; echte
10-Spiele-Umschaltung funktioniert. Vollsuite/VPS-Release bleiben offen.
238 alte WTA-Bo5/102 offen ohne
Geldbindung; nicht zu Gewinnen/Verlusten oder Bo3 umschreiben. Letzte reguläre
Tennis-/Wettfinderläufe waren Exit 1, keine erfolgreichen Scans erfinden.

Automatische Veröffentlichung heute real belegt: 82 eindeutige Auswahlen,
Daily3 **0**, kleines Inventararchiv 221.184 Bytes. 81 Forecastbindungen korrekt,
eine NHL-Herkunftslücke (`2026020035`) offen. 25 neue Tennisprognosen sind nicht
mit 84 Modellrevisionen/84 Kontextoriginalen zu verwechseln. Keine abgeschlossene
Gewinnbilanz oder nachgewiesene Wetter-/Verletzungs-/Müdigkeitswirkung.
E-Sport-TOP RED Canids/KT (LOL `1694355`) stammt aus tatsächlich gebundenem
Elo/Form-Fit; ursprüngliche 20er-Fenster und Verbindung der Gegnergruppen nicht
erhalten/belegt. Dieser verbleibende fachliche Herkunftsnachweis steht im TODO.

**Nächste Aktion:** laufende Vollsuite abschließen und Fehler prüfen; erst danach
sicherer VPS-ff-only-Pull mit Linux-Offline-QA. Der vorhandene ignorierte Helfer
`output/playwright/selection-history-deploy-20261003.sh` muss vorher die neuen
Dateipfade und Prüfungen aufnehmen. Keine Produktionsdatenmigration. Anschließend
reguläre Dienste am 05.10. 00:05/03:35 Europe/Zurich auf echten Erfolg prüfen,
nicht zusätzlich scannen. Restarbeiten und genaue Prüfreihenfolge im obersten TODO.

Keine Backups, Bereinigung, zusätzlichen API-Scans oder Geldänderungen.
Geerbte ungetrackte Dateien erhalten; nie pauschal `git add .` oder Reset/Cleanup.
Eigene Vorschau/Prüftabs beendet; nur die Vollsuite läuft weiter.

## Aktueller Einstieg – Auswahlbilanz, 03./04.10.2026

Letzter verifizierter Stand 00:19 CEST: Reader-Code `6c62100` auf GitHub main,
VPS noch `25e79a5`, regulärer Tennisjob aktiv ohne Endzeit; App/Caddy aktiv.
Zusätzliche gemeinsame Integration am Reader-Fix: 225 Tests bestanden.
Erst nach normalem Jobende sicher per ff-only übernehmen; nicht neu scannen.

Oberster [TODO-Block](TODO_AKTUELL.md) und
[Bilanzbericht](docs/audits/2026-10-03-auswahlbilanz.md) sind maßgeblich.
Neue kleine prospektive Auswahlinventare statt nachträglicher Kundentipp-Erfindung;
read-only Ergebnisberichte trennen interne Kandidaten und tatsächlich angebotene
Auswahlen. RisikoBet-Kohärenz inklusive Best-of-1 korrigiert. Preisfilter kann keine
Gegenposition nachrücken lassen; Quoten beeinflussen die Modellchance nicht.
0,561 Sekunden für echte VPS-Bilanz, 181/107/71/3 unverändert. Kein Profit- oder
Kontextwirkung-Nachweis daraus. Automatische Inventarerfassung erst durch den
nächsten normalen Wettfinderlauf real bestätigen; keine Zusatzscans starten.
Auswahl-/Historien-Code `25e79a5c71bcd763fd0d5b66e7bb937c98aef427` ist auf main
und VPS live; reine Linux-QA, App/Caddy, beide Healthchecks und sieben Timer geprüft.
Modellartefakte unverändert. Frische Integration: 510 bestanden; breite Runde
12.256 bestanden/97 Skips/111 Untertests und zwei vorab importierte alte Testfixtures,
deren aktuelle Dateien separat mit 70 Tests grün sind. Keine vollständige neue
grüne Vollsuite behaupten. UI-Historie 20.480 Bytes, drei tatsächlich erfasste
Oberflächen, aktuell null Tipps. Kein alter Kundentipp-/Renditenachweis.
Zusätzlicher enger Tennis-Schema-1/2-Leserfix liegt getestet vor (229, unabhängig
54 überlappende Tests), beim Eintrag wegen seit 00:05:12 CEST aktivem Tennisjob
noch nicht deployed. Nächste Aktion: dessen echten Abschluss lesen, dann sicheren
ff-only Pull des Folgecommits und Healthchecks; keine zusätzlichen API-Scans.
24 sichtbare alte WTA-Best-of-5-Fälle bleiben separat ungeklärt, keine Geld- oder
Historienumschreibung. Exakte aktuelle SHA-Differenz vor Wiederaufnahme prüfen.
Keine Backups oder Bereinigung.

## Aktueller Einstieg – Daily3-Tagesfolge, 03.10.2026

Oberster [TODO-Block](TODO_AKTUELL.md) ist maßgeblich für den neuen engen Fix.
Daily3 berücksichtigt Tageskapazität und chronologische 3-/4-Stunden-Puffer;
21:00-Fußball nie als erste Wette. Nur ein neues Erfassungsformular und eine
offene Vormerkung/Wette gleichzeitig; nächste nach echter Abrechnung.
Alte Kontohistorien, Wiederholungen und CHF-Geldrechnung unverändert.
539 betroffene Tests, unabhängig 481 überlappende Tests grün; lokale interne
Browserfolge geprüft. Keine neue Vollsuite oder bessere Wettqualität behauptet.
Codefix `2c4f38db2e093f2e5492bab4fb4c6aa3b127017c` auf main und VPS live;
Offline-Linux-QA grün, App/Caddy aktiv, beide Healthchecks `ok`, Ergebnissnapshots
unverändert. Wrapper nach Abschluss wegen SSH-CR Exit 1; direkter Live-Nachcheck
Exit 0 erfolgreich. Dokumentationsabschluss wird separat ohne Neustart gezogen.
Alle sieben Timer enabled, aber reguläre Tennis-, Wettfinder- und Shadow-Dienste
heute mit Fehlstatus: als getrennte Restarbeit im TODO dokumentiert, nicht behoben
oder zurückgesetzt. Keine pauschale Scanner-Gesundheitsmeldung ableiten.
Keine Backups, Zusatzscans, Cleanup oder historischen Buchungsänderungen.

## Aktueller Einstieg – Scanner-Reparaturstand, 02.10.2026

Oberster [TODO-Block](TODO_AKTUELL.md) und
[Reparaturbericht](docs/audits/2026-10-02-scanner-reparaturen.md) sind maßgeblich.
Alle 16 Befunde implementiert, mit Regressionen und unabhängigen Reviews.
Zwischenfreeze war `ce6e07e3881df61696dd15e54cbb38ec8fda175f` nach zusätzlicher
Rotkarten-Periodenprüfung und korrigierter historischer Tennis-Replayintegration;
Runtime-/Trainingsvertrag und POINT-Workergrenze vollständig integriert;
450 Integrations-/254 unabhängige Tests bestanden. Eine gemeinsam verwendete
Testhelper-Uhrregression separat reproduziert und korrigiert (976 betroffene
Tests/neun Skips; unabhängig 1.120/neun), kein Produktions-/Speicherfehler.
Beide Tennisparser erhalten ausdrücklich vorhandene Formatmetadaten; 18 neue
Parser→Scan-Fälle, 121 Tests grün, keine reale Feed-Abdeckung erfunden.
Finale Vollsuite auf Code-/Testfreeze
`7e8ba9149269a909a08a802a7bddd1a8009191c0`: dauerhafter Erstlauf 13:37–14:12
CEST mit einem lokalen WSL-Alias-Umgebungsfehler, Git-Bash-Shelltests bestanden.
Seit 14:32:55 konservativer Restlauf mit PowerShell 7/Git-Bash: 105 vollständig
grüne Dateien/4.844 IDs übernommen, 198 Dateien/7.339 IDs vollständig neu.
Restlauf 14:45:23 CEST Exit 0; finaler Aggregator belegt alle 12.183 IDs genau
einmal: 12.086 bestanden/97 Skips/null Fehler, dazu 111 Untertests.
Vollständige Testabdeckung in zwei disjunkten Dateigruppen, kein einzelner
erfolgreicher Vollsuite-Aufruf. Sourcefreeze/Fingerprint unverändert.
Release `e233ac4b99e3ad3a014c35148d61b322b3c13f80` ca.14:53 CEST
lokal/GitHub/VPS identisch, explizit ff-only deployed. Reine Linux-QA grün,
App/Caddy aktiv, sieben Timer geplant, beide Healthchecks `ok`, Ergebnissnapshots
unverändert. Nachfolgend nur dieser Abschluss-Dokumentationsstand commit/push/pull,
kein weiterer Codeeingriff/Appneustart nötig.
Keine Backups, Pakete, Cleanup, SQL-Migration oder Extra-Sport-/API-Scans.
Tennis-v2-Aufbau beim regulären Rebuild 03.10., 00:05 Zürich vorgesehen;
Aktivierung und Produktionsnachweis erst nach erfolgreichem Lauf bestätigen.
alte Prognosen/Geldbelege nicht überschreiben. Fachlicher Kontext-/Qualitätsnachweis
und fünf ungeklärte Tennis-Ergebnisse bleiben getrennte offene Grenzen.

## Aktueller Einstieg – Scanner-Tiefenaudit, 02.10.2026

Maßgeblich: oberster [TODO-Block](TODO_AKTUELL.md) und
[Auditbericht mit 16 Repros](docs/audits/2026-10-02-scanner-tiefenaudit.md).
Vor diesem Dokumentations-Commit lokal/GitHub/VPS `bfb9344`, Code `1ae37d9`
unverändert. App/Healthchecks gesund; Tennis/Wettfinder/E-Sport heute Exit 0.
Gegenpreis-Nachweis abgeschlossen: 16 reale Seitenpreise/acht Events, fünf exakt
gebundene RisikoBet-Overlays. Kein Extraabruf. Jetzt fünf ungeklärte Tennisfälle.
58 Worktrees ohne neu verlorenes aktuelles WIP abgeglichen, Altdateien erhalten.
**8 P1-/8 P2-Befunde noch unrepariert:** zuerst falscher Tennis-Tag, maskierte
Provider-/Shadow-Fehler; danach falsche Abrechnungs-/Format-/Neutral-/Live-Inputs.
Details und kleine Reparaturreihenfolge im Audit, keine pauschale Fertigmeldung.
Gezielte Gruppen 356/194/166/19/9 grün, teils überlappend; Vollsuite bleibt vom 01.10.
Kontexteffekt-/Wettqualitätsnachweis weiterhin offen. Keine Code-, Backup-, Cleanup-,
Migrations-, Timer- oder API-Scanänderung durch diesen Audit. Nicht ungefragt
implementieren; für Reparaturen zuerst Regressionsfall, dann enger Patch/Review.

## Accountwechsel – 01.10.2026, 20:29 CEST

Maßgeblich ist der neue oberste [TODO-Block](TODO_AKTUELL.md).
Frisch geprüft: lokal/GitHub/VPS `01a79b4`, Code `1ae37d9` live;
App/Healthchecks gesund, sieben Timer geplant, heutige Tennis-/Wettfinderläufe
mit Exit 0 beendet. Nächster Nachweis nach den regulären Läufen am 02.10.
(Tennis 00:05, Wettfinder 03:35 CEST), ohne Extra-Scan. Gegenpreis-Befüllung,
qualifizierte Kontexteffekte und vier Tennis-Ergebnisse bleiben offen.
Nur Dokumentationsübergabe; keine neuen Backups, Bereinigungen oder Migrationen.

## Aktueller Einstieg – Gegenquoten und Kontextanschluss, 01.10.2026

Oberster [TODO-Block](TODO_AKTUELL.md) und die
[Fortsetzung des Prüfberichts](docs/audits/2026-09-30-wetter-tennis-preiszuordnung.md#fortsetzung-01102026)
sind maßgeblich. Code `1ae37d9` auf main/VPS live, um 08:45 CEST kontrolliert
gezogen. Vollsuite: 11.929 bestanden, 97 Skips, 111 Untertests, Exit 0; Quellcode
und Tests unverändert. Beide Healthchecks `ok`, sieben Timer geplant, Modell-/
RisikoBet-Dateien bytegleich. Echte Tennis-
Gegenpreise aus derselben vorhandenen Antwort separat begrenzt gespeichert;
Football-Jointanschluss nach Capture am tatsächlichen späteren Stichtag,
experimentell und ohne Änderung der öffentlichen Grundwahrscheinlichkeit.
Zwei konkret veraltete Editorial-Testverträge korrigiert, keine Skips ergänzt.
Alte Vollsuite-Fehlerursache nicht nachträglich erfunden. Numerisch qualifizierte
Verletzungs-/Müdigkeits-/Wetterwirkung weiterhin offen, keine Qualitätsbehauptung.
Keine Sicherung, Bereinigung, Migration oder zusätzlichen API-/Sportscan.
Bestehende Gegenpreise werden nicht nachträglich erfunden: regulärer Abruf
02.10., 03:35 CEST übernimmt die dann tatsächlich verfügbaren Anbieterbelege.
Eigener frischer Produktionsbrowser: sichtbare Karten bei 1440/390/320 ohne
Überlauf oder Console-Fehler geprüft; keine echte neue Gegenquote behauptet.

## Aktueller Einstieg – Wetterzeitpunkt und Tennispreise, 30.09.2026

Oberster TODO-Block und [neuer Prüfbericht](docs/audits/2026-09-30-wetter-tennis-preiszuordnung.md)
sind maßgeblich. Code `707e2f8` auf main/VPS live, Wettercache pro genauem
Anpfiff korrigiert; streng exakter Tennis-Siegerpreisjoin und 1,20-Filter.
Keine neuen Abrufe, Sicherungen, Migrationen oder Bereinigungen. Modelle/Preise
bytegleich; beide Healthchecks `ok`, sieben Timer unverändert. Gezielte Tests,
unabhängige Reviews sowie Desktop-/Mobilprüfungen bestanden; Vollsuite meldete
Fehler und wurde für das Zeitfenster bei 90 % angehalten. Benachbarte Gruppen
einzeln grün; ursprüngliche Ursache offen. Als Nächstes kurzer Basetemp und
`-x --tb=short`, keine Fehler blind überspringen. Gegenpreise für RisikoBet werden im
regulären Tennisabruf bislang nicht gespeichert: nächste konkrete Reparatur,
ohne Extra-API. Fachliche Kontexteffekte bleiben getrennt offen.

## Aktueller Einstieg – RisikoBet-Zeitfilter und Serienform, 30.09.2026

Oberster TODO-Block ist maßgeblich. Bereits gestartete RisikoBet-Szenarien
werden ausschließlich aus der kommenden Kartenansicht entfernt; Historie,
Modelle, Quoten und Geldbelege bleiben erhalten. Filter beim Aufruf/Neurendern,
keine neuen Scans/Timer. E-Sport zeigt reale S/N-Serienbilanz statt leerer
Gegnerlisten. 769 gezielte Tests und unabhängiger Review grün. Code `c9de1e9`
auf main/VPS live; echte Karten bei 1440/390/320, 5↔10 und unveränderte
Modell-/RisikoBet-Dateien geprüft. Beide Healthchecks `ok`, sieben Timer geplant.
Vollsuite aus Zeitgründen bei 22 % beendet, nicht als bestanden behauptet.
Kein Backup oder zusätzlicher API-/Sportscan. Fachliche Kontexteffekte bleiben
getrennt offen; keine Behauptung verbesserter Wettqualität aus diesen UI-Tests.

## Aktueller Einstieg – Teamlogos aller Sportarten, 30.09.2026

Oberster TODO-Block und letzter Schildbilder-Bericht sind maßgeblich. E-Sport,
NBA, NHL, zwei EuroLeague-Teams und zwei Cricket-Nationalteams erhalten echte
externe Teamgrafiken in der bestehenden Schildform. Keine Bilddatei-/DB-Kopien,
kein API-/Sportscan, kein Backup oder Cleanup. Kleine deduplizierte E-Sport-
URL-Metadaten aus ohnehin empfangenen Antworten, höchstens 128 KiB / 256 Teams.
Provider-ID/Namensraum strikt gebunden; NBA nicht mit WNBA/NCAA verwechselt.
Unbekannte Teams bleiben Initialen; NAVIs falsches `1w`-Dota-Spielicon entfernt.
Modelle/Preise/Geld unverändert; Fußball/Tennis-Pfade bleiben erhalten.
Code `778434a` auf main und VPS live. 674 Tests, ein erwarteter Windows-Skip;
Spirit/Vitality/LOUD live bei 1440/390/320, andere Sportgrafiken lokal und
VPS-Resolver. Keine neuen produktiven Sportkarten erfunden. Modell-/Preisdatei
bytegleich, beide Healthchecks `ok`, sieben Timer geplant. Nachweiscommit ist
reine Dokumentation, kein weiterer funktionaler App-Stand.

## Aktueller Einstieg – direkte CDN-Bilder, 30.09.2026

Code `d4274a3` auf main und VPS ersetzt den nachfolgend beschriebenen RAM-Cache:
Clublogos und Spielerfotos laden direkt im Browser beim Anbieter. Nur Links/
geprüfte Quellenmetadaten auf BetBoy, keine Bildkopien oder Binär-Bildcaches.
330-px-Tennisbilder, 150-px-Wappen tatsächlich geladen; bestehende Schildform
und Zuschnitte erhalten. Fehlende Bilder zeigen Initialen. 464 Tests,
unabhängiger Review, 404-Fallback und lokale/produktive 1440/390/320-Prüfung
bestanden. UI-Neurender geprüft; Modelle/Preise/Geld unverändert, kein Backup,
keine Bereinigung, kein zusätzlicher Scan. Oberster TODO-Block und letzter
Abschnitt des [Produktionsnachweises](docs/audits/2026-09-30-schildbilder.md)
sind maßgeblich; frühere Cache-Beschreibung ist historisch, nicht aktueller Code.

## Aktueller Einstieg – Originalbilder in den Schildkarten, 30.09.2026

Code `4e87ca2` auf main und VPS: Originalvereinswappen sowie eindeutig
zugeordnete Spielerfotos in der vorhandenen Schildform, Wettfinder/Daily3.
13 geprüfte Spielerfotos; neue/unbekannte Spieler behalten Initialen.
442 Tests, unabhängiger Review und echte Browserprüfung bei 1440/390/320 px
bestanden. Modell-/Preisdatei bytegleich, keine Geldänderung, Sicherung,
Bereinigung oder zusätzlicher Sportscan. Oberster TODO-Block und
[Produktionsnachweis](docs/audits/2026-09-30-schildbilder.md) sind maßgeblich;
ältere offene Tennis-Quotenhinweise weiter unten sind bereits überholt.

## Aktueller Einstieg – Tennisquoten und RisikoBet-Kurzform, 30.09.2026

Zuerst den obersten Block in [TODO_AKTUELL.md](TODO_AKTUELL.md) lesen.
Tennisquoten wieder aktiv; Namensreihenfolge Zhang/Zhizhen und separater
Preiszeitpunkt korrigiert. Echte Gea-Karte zeigt 1,28 bei unveränderten 79,4 %.
RisikoBet hat kurze Spielerbilanzen statt der beanstandeten Protokollabsätze.
767 Tests plus 26 Untertests sowie lokale/produktive Drei-Breiten-Prüfung grün.
Code `7b60496` auf main/VPS; nachfolgender Nachweiscommit nur Dokumentation.
Keine neuen Sicherungen, zusätzlichen Sportscans oder Geld-/Modelländerungen.
Numerische Kontexteffekte und Gesamt-Wettqualität bleiben gesondert offen.
Die damals offene RisikoBet-Zeitprojektion ist im obersten Block repariert.
Ungetrackte Artefakte erhalten.

## Aktueller Einstieg – Kundenkarten ohne interne Modellnotizen, 30.09.2026

Zuerst den obersten Block in [TODO_AKTUELL.md](TODO_AKTUELL.md) lesen.
Technische Footer, heuristischer Sicherheitswert und Evidenz-Badges aus den
Kundenkarten entfernt; tatsächliche Form-/Gegner-/Ergebnisdaten bleiben.
Interne Belege und signierte Wettsnapshots unverändert, keine neuen Kopien.
611 Tests und neun lokale Browserkombinationen bestanden; unabhängiges Review
ohne Befund. Git-/VPS-Veröffentlichungsstand direkt prüfen, nicht aus älteren
Designnotizen ableiten. Tennis-Quotenanbindung bleibt eine separate offene
Aufgabe; kein zusätzlicher Scan oder neues Backup gestartet.

## Aktueller Einstieg – Sports-Editorial-Korrektur, 30.09.2026

Die erste Designumsetzung wurde vom Nutzer ausdrücklich als nicht vorlagentreu
beanstandet. Sie war technisch geprüft, aber nicht visuell abgenommen. Jetzt
Desktop-Aufbau, Form-/Gegnerlisten und bebilderte Daily3-/Tennisspalte korrigiert;
Mobil-/Tablet-Stapelung und vorhandene fünfteilige Navigation erhalten.
Zuerst den obersten Block in [TODO_AKTUELL.md](TODO_AKTUELL.md) und den
[Korrekturbericht](docs/audits/2026-09-30-sports-editorial-korrektur.md) lesen.
Final 531 Tests und 31 Browserkombinationen grün, inklusive nachgestellter
Produktions-Kontobrücke. Finaler UI-Commit `c6b66c3` gepusht und auf dem VPS;
sieben Live-Breiten, Coverbilder, 23 RisikoBet-Karten und Desktop-/Mobilrückweg
bestätigt. Beide Healthchecks `ok`, sieben Timer aktiv. Folgender Nachweiscommit
nur Dokumentation, getesteter UI-Code identisch. Keine Zusatzscans; Tageslauf 03:35.
Veröffentlichungsstatus steht im Korrekturbericht; nicht aus alten Hashes ableiten.
Keine Backups, zusätzlichen Sportscans, Modell- oder Finanzänderungen.
Bekannte ungetrackte Output-/Audit-Dateien bewahrt. Keine native Store-App,
physische Geräteprüfung oder bessere Wettqualität durch dieses UI-Paket behaupten.

## Vorheriger Einstieg – Sports Editorial, 30.09.2026 (Historie)

Desktop-Design 2 und Mobil-Mix 2+5 sind als responsive Streamlit-Oberfläche
umgesetzt. Zuerst den obersten Block in [TODO_AKTUELL.md](TODO_AKTUELL.md) und
den [Abnahmebericht](docs/audits/2026-09-30-sports-editorial.md) lesen.
526 betroffene Tests und 29 Browser-/Randfallkombinationen bestanden; echte
Maus-/Tastatursteuerung sowie Touch-Emulation geprüft. Alte Vollsuitezahlen
darunter beziehen sich nicht auf diesen neuen Patch. Bestehende WIP-/Output-
Dateien erhalten; kein neues Backup, zusätzlicher Sportscan oder Bereinigung.
Native Apps, echte Geräte, Kundenbetrieb und numerisch belegte Kontexteffekte
bleiben separat. Veröffentlichungsstatus steht im Abnahmebericht, nicht aus
den historischen Hashes unten ableiten.
UI-Code `f673c8d` gepusht und auf dem VPS live; Produktionsbrowser inklusive
Desktop-/Mobilrückweg bestanden, beide Healthchecks `ok`, sieben Timer aktiv.
Tennis regulär Exit 0 am 30.09. um 00:24:27; Tages-Wettfinder um 03:35 geplant.
Der folgende reine Nachweiscommit verändert keine getesteten Programmdateien.

## Aktueller Einstieg – Accountwechsel 28.09.2026

Zuerst den obersten Accountwechsel-Block in [TODO_AKTUELL.md](TODO_AKTUELL.md)
lesen; darunterstehende Stände sind Historie. Codepatch `42054e3` live, letzte
Statusfortschreibung `2155d06` am 28.09. um 20:29 CEST identisch lokal/GitHub/VPS
bestätigt. 11.277 Tests und 111 Untertests bestanden, 96 Skips. App/Caddy aktiv,
Healthcheck `ok`, Tennis Exit 0. Kein neues Backup oder zusätzlicher Sportscan.
Numerisch belegte Kontexteffekte, reale UI-/Geräteabnahme und Kunden-/Storebetrieb
bleiben offen; konkrete Schritte und Grenzen stehen im neuen To-do-Einstieg.
Diese Übergabefortschreibung ändert keinen Produktivcode.

## Aktueller Einstieg — Kontext-/Daily3-Fortsetzung 21.09.2026

Zuerst den obersten Block in [TODO_AKTUELL.md](TODO_AKTUELL.md) und den
[Kontext-/Daily3-Bericht](docs/audits/2026-09-21-kontext-daily3-fortsetzung.md) lesen.
RisikoBet-Textveröffentlichung aus dem vorherigen Lauf jetzt bestätigt.
ATP-Daily3, Tennis-v4 und begrenzte Fußball-Quellwiederverwendung als c936310
auf main/GitHub/VPS; 2.585 plus 115 Tests grün. Echter Scan 951 Sekunden,
82 gespeicherte v4-Revisionen, 16 ATP-Vergleiche. Ein tatsächlicher WTA-
Gegnerwechsel mit 30f31ed live behoben: echter Gesamtlauf 15:05:20 Exit 0,
86 Prognosen fertig, neue WTA-Linie 1637 aktiv statt 1585. Anzeigeschutz für
bekannte native Rücknahmen als ebfb69d live. Statusnachtrag 3201537 ebenfalls
auf main/GitHub/VPS: bestätigte geänderte/offene Teilnehmer sind Teildaten,
keine beschädigten Originale; echte Belegfehler werden weiterhin gemeldet.
1.908 Tests, drei Skips, 26 Untertests. Die reale lesende Probe 15:36 bestätigt
beide früher fehlgeschlagenen Fälle (1588 geänderte Paarung, 1573 Teilnehmer
offen). Regulärer Lauf 15:37:05–15:43:08 CEST ebenfalls Exit 0, `completed`,
null technische Fehler. Beide Tennisfälle bleiben explizite Teildaten; daraus
keine erfundenen neuen Tennisprognosen oder vollständige Abdeckung ableiten.
Keine numerische Effektfreigabe: aktualisierte Zählung 15:13 CEST ergibt
144 passende native Endresultate insgesamt
vor Aufteilung, mindestens 200 unberührte Testevents erforderlich. Fußball-
Live-Jointmodell-Anbindung und weitere Daily3-Sportadapter bleiben offen.
Keine neuen Backups, Bereinigungen oder Finanzänderungen. Untere Stände Historie.

## Aktueller Einstieg – Produktreparatur 21.09.2026

Zuerst [TODO_AKTUELL.md](TODO_AKTUELL.md) und den
[Reparaturbericht](docs/audits/2026-09-21-produkt-reparaturen.md) lesen.
Funktionsstand `8543fcce91374ed15547380e36b587bd77d98cab` auf main/GitHub/VPS.
15K-Kohärenz, unbekannte Ausfälle, Daily3-Priorität, Erklärungstexte und
Ergebnisqueue repariert. 1.676 abschließende Tests plus 32 Untertests grün.
Native E-Sport-Abnahme: 15 von 15 echte Ergebnisse, keine Providerfehler,
alle Originalprognosen und 305 Altzeilen ohne Team-IDs unverändert.
Keine Bereinigung oder neue Backups; App und beide Healthchecks gesund.
Die Altzeilen nicht nachträglich mit heutigen Teilnehmern anreichern.
F02/F07 und Daily3-Vergleiche außerhalb Fußball bleiben offen: keine
qualifizierte Verletzungs-/Müdigkeitswirkung oder bessere Wettqualität behaupten.
Cricket bleibt ausgenommen. Frühere Blöcke unten sind historische Stände.

## Aktueller Einstieg – 21.09.2026, 08:24 CEST

Zuerst den obersten Block in [TODO_AKTUELL.md](TODO_AKTUELL.md) und den
[Abnahmebericht](docs/audits/2026-09-21-tennis-altfaelle.md) lesen.
Funktionscommit **`66b0a727ab0772e8137b0eb21063712c46c30192`** ist auf
Worktree/main/GitHub/VPS live. Vier WTA-Altfälle 183710, 183831, 183844, 183854
nach ausdrücklicher Nutzerfreigabe aus aktiver Verarbeitung entfernt, nicht
physisch gelöscht. 30 Originale, 22 Revisionen und vier Elternzeilen unverändert;
keine Geldbuchungen geändert. Exakter reversibler Katalog, keine Eventsperre.
Native 540er-Gegenprobe ohne bisherige Ergebnisfehler, 236 übrige Zuordnungen
identisch. Betroffene Regression 1.988 bestanden/3 Skips/26 Untertests; danach
16 gezielte Tests einschließlich zusätzlicher Fremdprognose grün (überlappend).

Regulärer Wettfinder 08:07:29–08:15:29 CEST Exit 0, keine technischen oder
Fußballfehler. Tennis 359 geprüft, 0 fällig: separate frühere parallele
Abschlussausnahme weiterhin nicht als behoben bewiesen. Kein zusätzlicher
Tennis-Gesamtlauf nach Entfernung; älteren Exit-1-Status nicht zurücksetzen.
App, Caddy, sieben Timer aktiv, beide Healthchecks `ok`, Tagesbackup aus.
Keine Bereinigung, neuen Backups, Schema- oder Geldregeländerung.
Verletzungs-/Müdigkeitsqualifikation bleibt offen. Nicht erneut nach der
bereits erteilten Vier-Fälle-Freigabe fragen. Ältere Abschnitte sind Historie.

## Historischer Einstieg – 21.09.2026, vor der freigegebenen Entfernung

Zuerst [TODO_AKTUELL.md](TODO_AKTUELL.md) und den
[Refresh-Bericht](docs/audits/2026-09-20-football-tennis-refresh.md) lesen.
Funktionscommit `7c805ae` enthält sämtliche vorherigen Reparaturen und ist auf
main/GitHub/VPS live. Vollsuite: **10.773 bestanden, 96 Skips, 111 Untertests**.
Die ursprünglichen Fußball-/Tennis-Terminfehler, WTA-Import und falschen
Doppel-/TBD-Aufnahmefehler sind behoben und nativ geprüft.

**Nicht alles erledigt:** Tennis-Neulauf endete 00:50:26 CEST mit Exit 1,
trotz 74/74 abgeschlossener Berechnungen und erfolgreicher Montagsprüfung.
Es bleiben vier historische Ergebniszuordnungen mit geänderten Teilnehmern
(WTA 183710, 183831, 183844, 183854). Native Gegenprobe bestätigt diese Fälle.
Nutzer wurde gefragt, ob diese unverändert separat als nicht auswertbar geführt
werden sollen; entsprechende neue Statusregel noch nicht implementiert.
Keine alten Prognosen, Gewinner oder Kontobuchungen umschreiben.

Zusätzlich endete der parallele reguläre Wettfinderlauf 00:56:30 mit einem
neuen Tennis-Refresh-`ContextIntegrityError`. Die genaue Stelle wurde bisher
verschluckt. `e8f0faf` ergänzt sichere Serverdiagnostik und ist auf main/GitHub/VPS,
147 betroffene Tests grün. Read-only: vollständige physische Historie und eine
Prognose bis vor Veröffentlichung erfolgreich geprüft (651.445 WTA-Verweise,
487 s). Kein reproduzierter Fehler, aber keine Abnahme des fehlgeschlagenen
parallelen Batches. Folgelauf 01:16 ohne Tennisfehler hatte **0 fällige Refreshes**.

Separat blockierte beim Fußball die geschützte API-Reserve den Tagesabruf;
Reset 02:00 CEST, regulärer Nachholtermin 02:07. Erfolg noch prüfen, Reserve
nicht einfach absenken. Keine Bereinigung/Backupaktivierung erfolgt, fachliche
Verletzungs-/Müdigkeitsqualifikation bleibt offen. Ältere Statusblöcke sind Historie.

## Aktueller Einstieg – E-Sport-Quoten 20.09.2026

Zuerst [TODO_AKTUELL.md](TODO_AKTUELL.md) und den
[E-Sport-Anschlussbericht](docs/audits/2026-09-20-esports-quoten.md) lesen.
OddsPapi-Free-Zugang installiert; Funktionscommit `696635d` auf main/GitHub/VPS.
Gemeinsame echte Serien-Sieg-Preise für Wettfinder/Daily3/RisikoBet, 1,20-Filter,
keine Modelländerung durch Quoten. 1.358 Tests plus 111 Untertests bestanden.
Nativer Abruf: sieben Spiele, circa 9 KB Cache. Erneuter regulärer E-Sport-Lauf
erfolgreich, acht neue Modelle; zwei exakt bepreiste Modelle nativ gerendert.
Nachprüfung 20:43–20:45 CEST: echte Veröffentlichung von 20:16 in der Website
sichtbar, Team Liquid 1,267 im Wettfinder und FlyQuest 3,80 in RisikoBet.
Map-Markt bleibt korrekt ohne Serienquote; Daily3 derzeit ohne Auswahl.
Quoten-Nachweisfehler (verlorene Disziplin) in `94fa36f` korrigiert und auf main
gepusht und 20:55 CEST auf VPS deployed; 421 Tests plus 142 main-Anschlusstests.
Native Gegenprobe mit echter LoL-Quote erfolgreich, kein DB-/Anbieteraufruf.
App/Caddy und Wettfinder-Timer aktiv; beide Healthchecks `ok`.
Gemeinsamer Lauf bleibt degraded: 16 Fußball-Fehlermeldungen sowie Tennis-
Sammelfehler mit acht `ContextIntegrityError`. Nicht als Modellreparatur melden.
Keine neuen Backups, Bereinigungen, Timer oder persönlichen Browserzugriffe.

## Aktueller Einstieg – Fortsetzung 20.09.2026

Zuerst den obersten Block in [TODO_AKTUELL.md](TODO_AKTUELL.md) und den
[aktuellen Datenlaufbericht](docs/audits/2026-09-20-fortsetzung-datenlauf.md) lesen.
`2758619` war vor der Reparatur überall synchron. Die über Nacht aufgenommenen
23 Fußballoriginale zu 19 Events sind alle partiell; keine Effektqualifikation.
Die neue Korrektur `bc6fef3` löst einen reproduzierten SQLite-Lesekonflikt zwischen
Fußball und Tennis und ist auf main/GitHub/VPS live. 578 Tests/4 Skips, weitere
125 auf main und beide Linux-Schreibkonkurrenzproben bestanden. Echter
Tennis-Neulauf 09:31:57: Modellaufbau erfolgreich, Tages-Scan 09:45:42 jedoch
erneut mit Schreibkonflikt gescheitert. Folgeursache gemessen: physische
Bestandskopie braucht 21,626 s Lesesperre, bisheriges Schreibbudget nur 5 s.
Gemeinsame endliche Wartezeit auf 60 s angepasst; Journal/Schema unverändert.
980 Tests/5 Skips grün; Nachtrag `9c579fe` auf main/GitHub/VPS live, 67 main-
Tests/5 Skips und Linux-Probe hinter 22-s-Lesesperre bestanden. Vollständiger
Tennis-Neulauf endete 10:19:32 mit 900-s-Timeout: Empfang gespeichert, History
bereit, Vorbereitung von 48 Prognosen nicht abgeschlossen. Als Nächstes die
CPU-Anteile des echten Abschlusslaufs messen, nicht Limits blind erhöhen.
Letzter Wettfinder vor Codewechsel erneut degraded. Verletzungs-, Müdigkeits-
und Wetterwirkung weiterhin nicht als erledigt melden. Keine neue Bereinigung
oder Backupaktivierung. Die genannten älteren Account-Commits sind alle enthalten.

## Aktueller Einstieg – Kontextanschluss und spielbezogener Vergleich 19.09.2026

Nachtrag `362a4a6` am 20.09. um 00:04 CEST auf main/GitHub/VPS verifiziert;
1.526 Tests, 210 main-Anschlusstests und Linux-Smoke grün. Neuer echter
Aufnahmebeleg und vollständige numerische Kontextwirkung weiterhin offen.
Zuerst den obersten Block von [TODO_AKTUELL.md](TODO_AKTUELL.md) und den
[neuen Reparaturbericht](docs/audits/2026-09-19-kontextanschluss-und-spielvergleich.md)
lesen. Daily3 vergleicht zusätzliche Formwirkung innerhalb derselben Begegnung;
die frühere bloße Abweichung von einer Ligahäufigkeit genügt nicht mehr.
Vorhandene Fußball-Originalaufnahme wird im kanonischen Worker endlich mit
einem endlichen persistenten Aufnahmebudget angeschlossen. Kein erfundener
numerischer Verletzungs-/Müdigkeits-/Wettereffekt und keine empirische Freigabe.
Nicht gesendete API-Abfragen nicht mit 24-Stunden-Fehlerbackoff bestrafen.
Keine neue Bereinigung oder Backupaktivierung, keinen externen Browser nutzen.
Funktionscommit `39bd0eb` auf main/GitHub/VPS; 1.522 Tests plus 202 main-
Anschlusstests grün. Ersten neuen Worker und fachliche Wirkung weiterhin
gesondert prüfen. Releasebelege im Bericht; alte Abschnitte unten historisch.
Nachtrag: Übergrößen dürfen Prognosen nicht verwerfen, und mehrere Gruppen
teilen ein einziges endliches Aufnahmebudget. Abschließend 1.526 Tests grün.
Erster echter Lauf endete degraded und zeigte noch keine Fußballoriginale;
die darin gefundene Gruppenlücke wurde repariert. Nicht als fertige
Verletzungs-/Müdigkeitswirkung oder erfolgreiche Datengesamtprüfung melden.

## Aktueller Einstieg – Daily3-Vergleich und echter Refresh-Befund 19.09.2026

Funktionscommits `0a54313` und `533a98f` auf main/GitHub/VPS: Daily3 nicht mehr
nach größter Rohwahrscheinlichkeit; echte Spiel-/Saison-/Formwerte werden mit
derselben historischen Markthäufigkeit verglichen. Keine Wettartenverbote oder
Quotenfilter. Zusätzlich wird eine Aktualisierungsgruppe nicht mehr komplett
verworfen, wenn ein einzelnes Spiel kein neues Modell erhält.
1.090 Tests/111 Untertests jeweils Worktree/main grün. Echter normaler VPS-Lauf
15:26:36 CEST beendet: 51 Spiele neu modelliert, 9 unmodelliert/Teildaten.
Ausgabevergleich mit identischem frischen Bestand bestätigt; neue Daily3-
Auswahl verändert, aber weiterhin zwei erlaubte Team-Über-0,5-Märkte.
Zuerst [TODO_AKTUELL.md](TODO_AKTUELL.md) und
[Reparaturbericht](docs/audits/2026-09-19-daily3-auswahlvergleich.md) lesen.
Keine erneute Speicherbereinigung/Backupaktivierung; keine erfundenen Vorteile
für fehlende Sportvergleiche und keine behauptete fertige Kontextwirkung.
Interner Browser blockiert durch ACL-Fehler; keinen externen Browser verwenden.

## Aktueller Einstieg – gemeinsame Spielblöcke 19.09.2026

Funktionscommit `1e918b9` gepusht und auf VPS bestätigt. Automatischer
Wettfinder: ein auf-/zuklappbarer Block pro Spiel, alle Märkte gemeinsam,
stabile Zustände bei Filter-/Seitenwechseln innerhalb der Sitzung.
907 Tests plus 26 Untertests jeweils in Worktree/main grün; lokale und echte
Browserprüfung abgeschlossen. Zuerst [TODO_AKTUELL.md](TODO_AKTUELL.md) und
[Abschlussbericht](docs/audits/2026-09-19-spielbloecke.md) lesen.
Keine Änderungen an Modell, Geld oder Datenbanken; Tagesbackup bleibt aus.
Bestehenden Worktree und fremde ungetrackte Prüfdateien bewahren.

## Aktueller Einstieg – kompakte Prognosekarten 19.09.2026

Funktionscommit `763c741` gepusht und live. Wettfinder und Daily3 zeigen kurze
Fakten; Ausfallnamen und Herleitung sind einzeln aufklappbar. Altdatenstatus
nicht erfinden, fehlende Modellwirkung weiterhin sichtbar. 713 Tests plus
26 Untertests jeweils in Worktree/main grün, reale Website/Health geprüft.
Zuerst [aktuelles To-do](TODO_AKTUELL.md) und
[UI-Abschlussbericht](docs/audits/2026-09-19-kompakte-prognosekarten.md) lesen.
Keine neue Bereinigung, Sicherung oder Modellverbesserung daraus ableiten.
Reparaturworktree und fremde ungetrackte Dateien unverändert bewahren.

## Aktueller Einstieg — Daily3 19.09.2026, 12:09 CEST

Zuerst den obersten Block von [TODO_AKTUELL.md](TODO_AKTUELL.md) und den
[Daily3-Bericht](docs/audits/2026-09-19-daily3-defensiv.md) lesen.
Funktionscommit `1985407` ist gepusht und live. Defensive Modellpräferenz
ab70%, kompaktere Oberfläche; tatsächliche Sicherheit damit nicht nachgewiesen.
344 betroffene Tests zweimal grün, reale Browseransicht/Healthchecks bestätigt.
Keine neue Datenmigration, Sicherung oder Bereinigung. Speicherreparatur unten
bleibt abgeschlossen. Alte Datenjobfehler/Kontextwirkung bleiben separate Aufgaben.
Bestehenden Reparaturworktree und fremde ungetrackte Dateien bewahren.

## Aktueller Einstieg — Speicherreparatur 19.09.2026

Zuerst den obersten Abschnitt in [TODO_AKTUELL.md](TODO_AKTUELL.md) und den
[Speicherbericht](docs/audits/2026-09-19-snapshot-speicherfehler.md) lesen.
500.000-Verweise-Speichergrenze im vorhandenen Worktree repariert und mit
Funktionscommit `8caf022b562c561c7d23b4b8363791bb0869d9d3` auf VPS ausgeliefert.
Produktivdatenbank verlustfrei 3,33 -> 2,09 GB verkleinert; sämtliche logischen
Identitäten erhalten, großer echter Lesetest und Healthchecks ok. Wartungsunit
`betboy-storage-repair-20260919-b.service` Exit 0, sechs Rechentimer aktiv.
Windows-/Linux-Tests und Gesamtprüfung samt Windows-Git-Nachlauf abgeschlossen.
Keine alten Aufgaben erneut ausführen, keine Kompaktierung wiederholen.
Nutzerentscheidung: keine neuen Tages-/Updatearchive. Tagesbackup disabled;
vorhandene Archive und Retentionpolitik nicht ändern. Alten Updater nicht
unverändert benutzen, da er Backups erneut aktiviert. Quoten/Geldregeln,
Cricket und empirische Modellfreigaben unverändert.
Vorherige fehlgeschlagene Datenjobs und fachliche Wirkungslücken bleiben
separate Aufgaben; kein neuer erfolgreicher Gesamttageslauf behauptet.

## Aktueller Einstieg — Produktreparatur 19.09.2026 committed und gepusht

**Veröffentlicht:** Reparaturpaket `2cd0a982a96331996955779a8dfff0466ecfb2fd` auf lokalem main und GitHub-main bestätigt; nachfolgende Commits dokumentieren nur den Abschluss. Vollsuite auf Funktions-/Teststand `d0759b1`:10303 bestanden,96 Skips,111 Untertests,Exit0. Hauptcheckout auf `2cd0a98`:625 bestanden,79 Untertests,Exit0. Alle Reviews abgeschlossen; keine Quell-/Teständerung danach. Logs im obersten TODO-Abschnitt. Keine neue VPS-/Linux-/Produktionsabnahme oder empirische Verbesserung daraus ableiten.

Zuerst den **obersten** Abschnitt von [TODO_AKTUELL.md](TODO_AKTUELL.md) und [Produktreparatur](docs/audits/2026-09-18-produktreparatur.md) lesen. Alte Statusblöcke unten sind historisch. Vorhandener Worktree `.worktrees/context-capacity-recovery-20260910` samt fremden/ungetrackten Dateien bleibt erhalten. Alle Reparaturcommits ab `f844f05` sind nach main integriert und gepusht. VPS wurde in dieser Runde nicht verändert; Timer deployen keinen Code.

Auswahl-/Preis-/Erklärungsreparaturen, kohärente Fußballverteilung, Tennis-Dauererhaltung samt allen drei Reviewkorrekturen, konsistente Finanz-Lesevorprüfung und Basketball-/Eishockey-Brücke sind unabhängig geprüft. Browser-Rundungskorrektur `a322430` und tatsächliche Desktop-/Mobilrenderer geprüft. Kausale Fußball-Originalanbindung `f6f62a5` technisch unabhängig geprüft; standardmäßig ausgeschaltet bis Betriebsprüfung, Ausführungsfingerabdruck ausdrücklich kein qualifiziertes C1-Replaypaket. Vollständige Verletzungs-/Müdigkeitswirkung und empirische Verbesserung nicht erledigt. Alle Taskstände in den jeweiligen SDD-Ledgern prüfen; keine erledigten Aufgaben oder frühere Speicherbereinigungen wiederholen. Nutzer hat Commit/Push bereits verlangt; Timer deployen keinen Code.

## Historischer Einstieg 18. September 2026 — früheres Releasepaket

Zuerst den obersten Abschnitt von [TODO_AKTUELL.md](TODO_AKTUELL.md) und den [Reparaturbericht](docs/audits/2026-09-18-context-repair-release.md) lesen. Funktionscode `c44684d` ist lokal auf `main` und auf GitHub-main. Finale Gesamtsuite: 10.065 bestanden, 96 Skips, 97 Untertests; Hauptcheckout zusätzlich 346 bestanden, 12 Skips. Alle genannten Code-/QA-Reviews ohne offene Befunde. Die Testläufe sind beendet, nicht erneut starten.

Die acht zusätzlich genehmigten QA-Kopien sind geschützt exportiert, vollständig wiederhergestellt/geprüft und entfernt. Lokale Recovery `C:/Projekt/BetBoy/.private-vps-backups/20260918-qa-retirement`; Details und Hashes im To-do-Dokument. Frühere Drei-Kopien-Bereinigung ebenfalls abgeschlossen. Nicht wieder beginnen und keine weiteren Datenbestände aus dieser Freigabe ableiten.

Der nächste tatsächliche Deploymentabschluss wird in `output/playwright/context-repair-deployment-20260918.md` festgehalten und muss mit VPS/Git/Health frisch abgeglichen werden. Vor diesem Abschluss VPS zuletzt `f3c2b60`; 22.581 GB frei gegen 22.400 GB Grundreserve, zusätzliche Codebereitstellung noch zu berücksichtigen. Kein direkter produktiver Pull und keine Reserveabsenkung. Vollständige Verletzungs-/Müdigkeitswirkung, Fußball-Live-Anschluss, native Neuqualifikation und empirische Qualität bleiben ausdrücklich offen; Cricket bleibt ausgenommen. Keine neue Design-/Pushfreigabeschleife.

## Historischer Einstieg 18. September 2026, 19:43 CEST

Zuerst den obersten Abschnitt in [TODO_AKTUELL.md](TODO_AKTUELL.md) und den [Reparaturbericht](docs/audits/2026-09-18-context-repair-release.md) lesen. Lokal `c44684d`, GitHub-main/VPS zuletzt `f3c2b60`; neue Reparaturen noch nicht gepusht/deployed. Finaler Gesamttest seit 19:40 CEST in Sitzung `65907`; dessen Log und unabhängigen QA-Review prüfen, nicht neu starten oder währenddessen Code ändern. Historische native QA-Fälle sind repariert, **aktuelle native Neuqualifikation und fachliche Effektabnahme bleiben offen**.

Der frühere geschützte Drei-Kopien-Export ist abgeschlossen. Für acht zusätzliche genaue alte QA-/Recovery-Ziele fehlt weiterhin die gesonderte Freigabe; deren Umfang genügt nach neuestem Reservecheck möglicherweise nicht mehr für den gesamten Release. Keine Datenbank/Sicherung löschen und keinen Updater umgehen. Vollständige Verletzungs-/Müdigkeitswirkung nicht behaupten: Fußball-Live-Anschluss und weitere Daten-/Qualifikationsaufgaben sind noch offen. Cricket und Geldkonten unverändert. Alle erledigten Taskreviews/Commits erhalten, keine erneute Design-/Pushfreigabeschleife.

## Historischer Einstieg 18. September 2026, 18:41 CEST

Zuerst den obersten Abschnitt in [TODO_AKTUELL.md](TODO_AKTUELL.md) lesen. VPS/GitHub-main weiterhin `f3c2b60`, gesonderte Reparaturkopie inzwischen weiter; neue lokale Reparaturen nicht mit einem Deployment verwechseln. Karten-Leser-Fix, Quellenpfad-Fix und deduplizierter Fußballspeicher sind implementiert/geprüft; eng begrenzte historische Tennis-Replay-Kompatibilität gerade in Arbeit. Nur dieser Follow-up und die Gesamtprüfung laufen, erledigte Tasks nicht erneut beginnen. Fußball-Liveanschluss und fachliche Effektqualifikation bleiben offen.

Voriger Drei-Kopien-Export abgeschlossen. Weitere acht genaue QA-/Recovery-Bestände sind nur zur Freigabe angefragt; noch kein Export/Entfernen. Zusätzlicher Reserveverlust ist als temporäre offene Prüfdatei des laufenden Wettfinders geklärt; natürlichem Abschluss folgen und Reserve neu lesen, nichts dafür löschen/beenden. Keinen produktiven Pull/Updater umgehen. Alle verlässlichen Testergebnisse, echten 101 unterschiedlichen Tennis-Outcomes und Daten-/Wirkungslücken stehen im obersten To-do-Block. Cricket, Preise und Geldkonten unverändert.

## Aktuelle Fortsetzung 18. September 2026, 17:50 CEST

Zuerst [TODO_AKTUELL.md](TODO_AKTUELL.md) lesen. Release `f3c2b60` ist inzwischen lokal/GitHub/VPS identisch; App und Healthchecks funktionieren. Genehmigte Bereinigung und geschützte Archivübertragung sind abgeschlossen, nicht erneut ausführen. 151 Tennis-Ergebnisbelege für 101 unterschiedliche Spiele sind an echte frühere Originale gebunden; keine empirische Effektfreigabe daraus ableiten.

Aktuell im vorhandenen Reparatur-Worktree: Datenbank-Lesetransaktionen von CPU-Prüfung trennen (reproduzierbarer echter Consumer-Konflikt), danach geänderten WTA-Downloadpfad reparieren und Fußball-Live-Originalanbindung fortsetzen. Pläne vom 18.09. und jeweilige `.superpowers/sdd/`-Ledger prüfen; erledigte Tasks nicht erneut dispatchen. Cricket bleibt ausgenommen. Keine erneute Design-/Worktree-Freigabe erforderlich. Weitere fachliche Restarbeiten stehen vollständig in der To-do-Liste; nicht alles erledigt.

## Historische Übernahme 18. September 2026, 16:00 CEST

Zuerst [TODO_AKTUELL.md](TODO_AKTUELL.md) und
[Übernahmebericht](docs/audits/2026-09-18-kontext-fortsetzung.md) lesen.
Funktionscode `afc8a10` lokal/GitHub, **VPS weiterhin `9659c49`**. App nach
unterbrochenem Update wieder gestartet/aktiviert; Healthchecks `ok`, sieben
Timer aktiv/aktiviert. Update blockiert vor App-Stopp an rund 4.61 GiB Reserve.
Drei eigene Prüfkopien noch nicht bereinigt, Freigabe angefragt. 162 Tests frisch
grün; vollständige Kontextwirkung und empirische Abnahme bleiben offen.
Ältere Statusblöcke sind historische Nachweise, keine aktuelle Vollabnahme.

## Account-Wechsel 16. September 2026 – verbindlicher Einstieg

**Zuerst [TODO_AKTUELL.md](TODO_AKTUELL.md) lesen.** Dort stehen die aktuelle
Reihenfolge, erledigte Arbeiten, Abnahmekriterien und vollständige Restliste.
Die folgenden älteren Statusblöcke sind historische Nachweise; sie dürfen
nicht erneut als aktuelle Blocker oder unerledigte Deployments übernommen werden.

App-Code lokal/GitHub-main/VPS: `9659c49b2738d6a4c7b0fcc7442a9e8ecef3b665`;
VPS und GitHub am 16.09. um 01:09 CEST erneut geprüft. Spätere reine
Dokumentationscommits ändern diesen produktiven Funktionsstand nicht.
Speicherbereinigung ist abgeschlossen (`5069e75`), Tennis-Live-Trainingsanbindung
ist implementiert und live (`9d271c1`, `9659c49`). Keine empirisch freigegebene
Verletzungs-/Müdigkeitswirkung daraus ableiten.

Echter Tennisjob 00:35:59–00:50:22: **Exit 1**, Scan 850 s, 23 neue Predictions,
40 zusätzliche Originalartefakte. WTA-Abruf weiterhin `HTTPError`, Datenstand
26.07.; WTA-Event `183854` mit `FixtureIdentityConflict`. Im Kontextspeicher
450 Tennis-Originale, aber 0 native Tennis-Endergebnisbelege. Die 39 separat
abgerechneten Shadow-Finals sind kein Beleg für diesen neuen Trainingspfad.
App/Caddy laufen; Healthchecks und acht geplante Timer nach Release geprüft.
Timer deployen keinen Code. Kein neuer manueller Lauf gestartet.

Nächstes: fehlenden Ergebnisübergang reproduzieren, WTA-Abruf/Spielzuordnung
reparieren, dann echte Kontextwirkung und Auswahlqualität nachweisen.
Cricket ausgenommen. Keine erneute Spezifikations-/Worktree-Freigabe nötig.
Quoten, Geldkonten und Einsatzregeln nicht verändern.

Tests: 545 breiterer Zwischenstand; final 144 betroffene Tests jeweils auf
Windows und Linux. Kein finaler Gesamtsuiten- oder Modellqualitätsnachweis.
Details: `docs/audits/2026-09-15-tennis-live-training.md`; tatsächlicher
Releaseabschluss: `output/playwright/tennis-live-training-release-20260916.md`
(bewusst ungetrackt im Reparatur-Worktree; Kernergebnisse in der To-do-Liste).

## Fortsetzung 15. September 2026 – echten Tennis-Timeout reparieren

Der echte Lauf auf `ab27535` endete nach 900 Sekunden unvollständig.
Nicht erneut als vollständig repariert melden. Die nachfolgende CPU-
Reparatur und ihre lokalen Nachweise stehen in
`docs/audits/2026-09-15-tennis-cpu-repair.md`. Linux-Leistung und vollständiger
Produktionslauf müssen separat bestätigt werden; siehe den jeweils neuesten
Releasebericht unter `output/playwright/`. Historische Berichte unten sind
keine aktuellen Deployment- oder Gesamterfolgsnachweise.

## Aktueller Auftrag 14./15. September 2026 – Speicher und Tennis-Abschluss

Die Speicherreparatur ist auf dem VPS live: regulärer Updater für
`1ec38a9f6f4530f85260ee57877e155a176e2ad6` am 14.09. um 23:46:18 CEST
erfolgreich beendet. App, interner/öffentlicher Healthcheck und sieben Timer
anschließend geprüft. Keine erneute Migration/Kompaktierung ausführen und
keinen alten Inline-only-Code starten.

Produktive Kontext-DB nach geprüftem 89-DB-Backup verlustfrei von
2.246.610.944 auf 938.508.288 Bytes reduziert; 112 Snapshots und sämtliche
logischen Inhalte/Hashes unverändert. Die beiden eigens freigegebenen QA-
Kopien liegen komprimiert als `context.db.gz` vor, nicht mehr als `.db`.
Historische Produktionsdaten, Geldbewegungen und echte Backups nicht gelöscht.
Wartungsbeleg/Backup: `/var/lib/betboy-context-verifier/memory-maintenance-8jmzb2v5/`.
QA-Reader: WTA 490.336 KiB, ATP 367.388 KiB Peak-RSS; dies sind ausdrücklich
keine Peaks des vollständigen Dienstes.

Echter Paralleltest: Wettfinder 23:46–23:55 ohne OOM/SQLite-Lock, aber Teildaten
wegen eines geänderten Tennis-Gegners. Tennis-Tageslauf 23:48:45–00:00:17
erreichte die Speicherung nach 691 s, ohne 900-s-Timeout/OOM; Abbruch an
`tennis revision cannot change player identity or orientation`.
Provider-Event WTA 183831 war zwischenzeitlich einem anderen Gegner zugeordnet.
Das ist KEIN vollständig erfolgreicher Tennislauf.

Enger Nachfolgepatch: eigener `FixtureIdentityConflict`, bestehende Historie
bleibt unveränderbar; nur dieser Konflikt wird je Karte berichtet, unabhängige
Karten werden weiter gespeichert. Abschlussfehler bleiben sichtbar und der
Tageslauf liefert bei Teildaten weiterhin Exit 1. Andere Integritätsfehler
werden nicht verschluckt. 214 gezielte lokale und 188 synthetische Linux-Tests
bestanden. Den echten Nachfolge-Deploy/-Lauf ausschließlich im Releasebericht
prüfen, nicht aus diesen Tests ableiten.

Keine grüne Vollsuite behaupten: eingefrorene Native-C-Auditprofile passen
nicht mehr zu den geänderten Owner-Dateien/Slotgrößen; ihre Pins wurden nicht
pauschal umgeschrieben. WTA-Quelldownload weiterhin HTTPError, Modellstand
26.07.; empirische Verletzungs-/Müdigkeitsaktivierung separat offen.
Cricket, Quoten, Einsätze und Modellfreigaben unverändert.

Aktuellen tatsächlichen Abschluss in
`output/playwright/context-memory-release-20260914.md` lesen.
Details: `docs/audits/2026-09-14-context-memory-storage.md`.

## Vorheriger Zwischenstand 14. September 2026 — Tennis-Abschluss und Parallelität

Abendstand: `151fe06` wurde regulär deployed, 89 DBs jeweils in Online- und
Stillstandsbackup verifiziert. Echter Wettfinder-Parallellauf 17:57–18:00 CEST
erfolgreich, Tennis-Abschluss jedoch erneut bei 900 s abgebrochen (64
vorbereitete Prognosen, 33 neue Kontext-Snapshots veröffentlicht). NICHT als
vollständig behoben übernehmen. Der Nachfolgepatch serialisiert vollständige
Referenzlisten bytegleich mit begrenztem Inhaltscache; echte CPU-Kette
7,67 → 4,82 s pro großem Beleg, 1.313 lokale und 314 Linux-Tests bestanden.
Noch kein vollständiger Echtlauf dieses Nachfolgepatches. Der Nutzer hat die
zusätzliche QA-Auslagerung ausdrücklich freigegeben. Ausschließlich
`/tmp/betboy-context-qa.9xr68INa` wurde nach voller lokaler Archivprüfung
entfernt (76.236 Einträge); Recovery liegt dauerhaft in
`.pytest_tmp/qa-recovery-20260914T1703/` der Reparatur-Arbeitskopie. Keine
Produktivdatenbank und kein echtes Backup gelöscht. Rund 18,9 GB frei.
Der anschließende Updater brach vor jeder App-Abschaltung an einer zweiten
konkreten Ursache ab: `archive.read(info)` lud die 1,4-GB-Datenbank komplett
in RAM. Streaming-Fix und exakte neue Helper-Prüfsumme sind vorbereitet.
Das echte 89-DB-Archiv besteht mit dem Fix alle Restore-/Authentisierungs-
prüfungen in 44,85 s / 32.904 KiB RSS unter unveränderten 2-GiB/300-s-Limits.
Für den Übergang muss ausschließlich der exakte Helper-Pin des installierten
Updaters atomar aktualisiert werden; Altdatei bleibt root-privat gesichert.
Keine anderen Updaterregeln ändern. Danach normaler Updater und echter
Tennis-Abschluss erforderlich; nicht vorzeitig als live übernehmen.
Aktueller Ergebnisbericht: `output/playwright/qa-offload-deploy-20260914.md`.

Ausgangspunkt `a1d15b6` auf allen Checkouts/GitHub/VPS bestätigt. Gezielte
Reparatur der redundanten Referenz- und Modellprüfungen, der langen SQLite-
Transaktionen und des Pending-Historienzugriffs; zusätzliche begrenzte
Rundungskorrektur für einen auf Linux reproduzierten Altfehler.
Nachweise: `docs/audits/2026-09-14-tennis-completion.md` und der tatsächlich
folgende Live-Abschluss `output/playwright/tennis-completion-release-20260914.md`.
WTA-Quelldownload liefert derzeit HTML bzw. TLS-Fehler. Verletzungs-/Müdigkeits-
training und weitere Sportadapter bleiben offen. Keine neue Freigabeschleife,
keine Behauptung, dass diese Reparatur das gesamte Kontextprojekt abschließt.

## Aktueller Auftrag 14. September 2026 – Tagesauswahl wirklich aktualisieren

Die aktuelle Ausgabe enthielt 69 für Daily3 zu alte Modelle trotz frischem
Ausgabezeitpunkt. Gezielte echte Fußball-Neuberechnung, begrenzte atomare
Kontextspeicherung und Übernahme ohnehin gelieferter Spieler-Einsatzdaten sind
implementiert; 945 gezielte Tests plus 32 Untertests bestanden. Keine Quote-
oder empirische Modellfreigabe gelockert, Cricket bleibt ausgenommen.
Vor-Deploy-Befunde: `docs/audits/2026-09-14-selection-refresh.md`.
Den tatsächlich folgenden Live-Abschluss immer separat in
`output/playwright/selection-refresh-release-20260914.md` prüfen; noch offene
Kontexteffekt-/Trainings-/Sportadapterarbeit nicht als erledigt übernehmen.

## Aktueller Auftrag 14. September 2026 — vereinfachter Updateweg ausdrücklich freigegeben

Nutzerfreigabe: „behebe doch einfach das verdammte problem ja du darfst“,
bezogen auf die Trennung historischer Vollanalysen vom Deployment.
Umgesetzt: explizite operative DB-Prüfung mit Schema-/SQLite-/Referenzprüfung,
Manifestkette und ladbaren aktiven Modellen; keine historische Nachberechnung
beim Update. Backup, echte Wiederherstellung, Konto-HMAC und Modellaktivierung
bleiben unverändert. Alte QA-Journale und Budgets bleiben erhalten.
Der bisher fehlende Pfad-Modul-Pin für den Windows-Temporärnamenfix ist korrigiert;
der tatsächlich installierte Vorgänger bleibt exakt gehasht akzeptiert.
Release-/VPS-Nachweise werden in
`docs/audits/2026-09-14-operational-deployment.md` geführt.
Die folgenden älteren Statusblöcke sind historische Nachweise, keine erneute
Freigabeaufforderung.

## Neuester Stand 14. September 2026 — Tennis-Laufzeitfix, noch kein VPS-Release

Neue gezielte Reparatur: vollständige Tennis-Historie pro Tour/Entscheidung
indexieren, je Karte alle relevanten Event-Revisionen statt erneut die gesamte
Tour verarbeiten; vollständige Snapshot-Referenzen unverändert. Begrenzter
Feldnamen-Cache und erhaltene Diagnoseausgabe bei Pipeline-Timeout.
917 gezielte Tests bestanden/1 Plattform-Skip. Echter 1000-Receipt-VPS-Vergleich:
zehn Featureberechnungen 2,5638 → 0,3489 CPU-s bei identischen Werten/Referenzen.
Das ist weder eine Gesamtperformanceabnahme noch ein Deployment.
Frische Produktion weiter 2dd1116/Updater74b1; Datenbank jetzt600219648 Byte.
Tennis-Timeout/WTA-HTTP503 und Fußball-Resultatzuordnung bleiben betrieblich offen.
Keine Quotenregeln, Datenhistorie, QA-Budgets oder Freigaben verändert.
Details: `docs/audits/2026-09-14-tennis-runtime-repair.md`.
Kein dritter großer QA-Lauf. Eine Vereinfachung des festgefahrenen Updatevertrags
ist als separate Entscheidung nötig, nicht stillschweigend umgesetzt.

## Neuester Stand 14. September 2026 — zweiter Serverprüflauf beendet, kein Deployment

Der zweite explizit genehmigte 900-s-Auftrag mit A400/B300/C200 lief auf
`9d92ed862d16d08596fd8f5c33c7e033462b0326`. A1 und A2 bestanden; anschließend
SIGKILL/Exit137 am 60-CPU-Limit des Steuerprozesses, noch vor A3/B/C.
Die alte A2-Ursache ist nachgewiesen und korrigiert: root:betboy 0440/0750
der exakt eingefrorenen Datenbasis war fälschlich als unsicher abgelehnt worden.
Kein Serverrecht oder ursprünglicher Datenbestand wurde verändert.

Zusätzliche lokale Korrektur `b9da5a3b9d183a7359b69056936eeeafe03a81f2`:
unveränderte Journalbytes werden bei jeder Kontrolle weiter vollständig gelesen,
aber nicht tausendfach unnötig nachgespielt. Neue Buchungen behalten fsync,
Readback und vollständigen Replay; alle ursprünglichen Budget-/Frischegrenzen bleiben.
124 gezielte lokale Tests bestanden/15 Plattform-Skips; echt Linux81/6Root-Skips.
Große Repository-Suite beendet: 9630 bestanden, 2 Fehler, 91 Skips, 97 Untertests.
Beide Fehler anschließend reproduziert und mit `dfe6068c6fc69bd9b2e8da17c8bc748d0fece583`
behoben: veralteter Daily3-Verifier-Testpin und zu langer temporärer Windows-
Berichtsname. Danach141/2Skips und223/3Skips in den betroffenen Tests bestanden.
Keinen grünen finalen Vollsuiten- oder nativen Gesamtlauf daraus ableiten.

**Kein dritter großer Lauf, keine Wiederverwendung eines verbrauchten Kontos.**
Die Parent-Korrektur beweist weder ausreichende A-Reserve noch abgeschlossene
C/B-/Restore-/Releaseprüfung. Beide Fehleraufträge und alle `qa19-*` bleiben erhalten.
Produktion frisch weiterhin `2dd1116`, App/Caddy/Health erreichbar. Sieben Timer
geplant; Tennis und Wettfinder weiterhin Result=exit-code/Status1. Daily3 nicht live.
Alle eigenen lokalen Testprozesse beendet; kein dritter großer VPS-Prüfauftrag.
Git-Pushstand anhand des echten Remotes prüfen, kein Main-/VPS-Erfolg aus Commit ableiten.
Exakte Daten und offene Grenzen:
[`docs/audits/2026-09-13-second-qualification.md`](docs/audits/2026-09-13-second-qualification.md).

## Aktueller Stand 13. September 2026 — Daily3 lokal implementiert; VPS-Freigabe offen

Diese Fortsetzung ersetzt die Statusaussagen der älteren Abschnitte darunter.
Keine neue Planungs-/Namens-/Budgetfreigabe einholen: Der Nutzer verlangt die
Umsetzung samt Commit, Push und kontrollierter Serverübernahme.

- Reparatur-Worktree: `.worktrees/context-capacity-recovery-20260910`, Branch
  `codex/context-capacity-recovery-20260910`. Daily3-Code: `aca7256d474a2f144fb08e53c13a71a09ff726d3`;
  begrenzte Scanner-Fehlerdiagnose: `de6b12b`. Den späteren Dokumentations-/Pushstand mit Git prüfen.
- Daily3 enthält die CHF-50-Tagesrechnung, höchstens drei verschiedene Events,
  manuell bestätigte echte Einsätze/Rückzahlungen, keine erwarteten Gewinngutschriften,
  keinen Nachschuss, Übernachtregel und flache Karten. Nicht live, keine Buchmachertransaktionen.
- Schlussregression: **869 bestanden, 21 Plattform-Skips, 97 Untertests bestanden**.
  Das ist die unten im Audit bezeichnete gezielte Kombination, keine Vollsuite/Produktionsabnahme.
- Browser mit isolierten Testdaten: 20 CHF bei Quote 1,12 reserviert/als platziert
  bestätigt, Rückzahlung 22,40 CHF: verfügbar 52,40 CHF, netto 2,40 CHF. Kein Geld bewegt.
  Kein DOM-Überlauf bei 1440/1080/760/320 px. Mobil keine pixelgenaue Designabnahme.
  Eigener Testserver beendet, temporärer Tab geschlossen und Viewport zurückgesetzt.
- Der echte einmalige 900-CPU-/900-Wandsekunden-V2-Auftrag ist **fehlgeschlagen**:
  A1 107,575990 CPU-s, A2 Exit 125 nach 108,389114 CPU-s; Daten-Worker B nicht gestartet.
  Alte Exception wurde im Kind verschluckt; genaue Ursache weiterhin unbekannt.
  Diagnosecode verbessert, kein neuer Vollversuch gestartet und kein Budget zurückgesetzt.
- Rund 216 CPU-s für zwei A-Scans lassen nur rund 84 s der A-Reserve. Ein dritter
  ähnlich teurer Scan passt voraussichtlich nicht. Kein unautorisiertes Umverteilen
  der 300/300/300-Teilreserven oder neuer 900-s-Auftrag. Vollständige C/B-, Restore-
  und Updaterabnahme sowie Deployment bleiben offen.
- Letzter frischer VPS-Abgleich dieser Fortsetzung: HEAD `2dd1116b68f3d94e9c24338c6c9dff9b01799221`,
  `betboy-app.service`/Caddy aktiv, lokaler Healthcheck `ok`; Tennis Exit 1,
  Wettfinder zuletzt Result=success. Keine Servercode-/Timeränderung. GitHub main `f84d9a6`.

Ehrlicher Funktionsumfang und offene Modellarbeit stehen im
[`docs/audits/2026-09-13-daily3-implementation-native-qa.md`](docs/audits/2026-09-13-daily3-implementation-native-qa.md).
Basketball-/Hockey-Begründungsadapter, empirische Kontextwirkung und sportübergreifende
Prognosequalität sind dadurch nicht erledigt. Cricket bleibt ausgenommen.
Alle übernommenen `qa19-*`-Ordner und historischen Serverprüfdaten bleiben erhalten.

## Fortsetzung 13. September 2026 — Reparatur tatsächlich implementiert, native Prüfung folgt

Der Nutzer verlangt jetzt ausdrücklich die Umsetzung, keine weitere Planungsrunde.
Der V2-Koordinator, sein gemeinsames A/B/C-Konto und der eng begrenzte historische
FIFO-Leser sind als Code vorhanden. Vier Vollbeobachtungen und der bisherige
240-CPU-Daten-Worker bleiben erhalten. V1-Einstiege bleiben getrennt. Lokale
enge Regression: 89 bestanden, 15 Linux-Skips, 7 langsame Fälle abgewählt;
vorherige breitere Runde: 111 bestanden/30 Plattform-Skips. Noch kein nativer
V2-Gesamtnachweis, keine C/B-Abnahme, keine Daily3-Funktion und kein Deployment.
Die nächsten Aktionen sind kleine native Gegenproben und die begrenzte gemeinsame
Qualifikation. Alte QA-Dateien und fehlgeschlagene Läufe werden nicht bereinigt.
Frischer VPS-Abgleich 19:06 UTC: App/Caddy aktiv; Tennis und Wettfinder failed.
HEAD separat als App-UID bestätigt: weiterhin 2dd1116. Kein Servercode verändert.

## Neueste Fortsetzung 13. September 2026 — Prüfkoordination ausgearbeitet, noch kein Code

Der Nutzer hat die Ausarbeitung der erforderlichen Prüfablaufänderung bestätigt.
Konkreter Plan: `docs/superpowers/plans/2026-09-13-updateweg-pruefkoordination.md`.
Er trennt die produktive 64-MiB-Grenze von den vier historischen QA-Vollscans,
behält alle vier Beobachtungen und den 240-CPU-Daten-Worker bei. Neu vorgeschlagen:
ein gemeinsamer V2-Koordinator mit drei gebundenen Teilreserven, insgesamt einmalig
zusätzlich höchstens 900 CPU-/900 Wandsekunden für eine Diagnosequalifikation;
kein Gratisbudget aus alten Journals oder ein behaupteter 1800/3600-C/B-Pass.
Genau bekannter historischer FIFO soll im neuen V2-Format nur metadatengebunden
erfasst werden, nie geöffnet/ausgelassen. Diese neuen Details brauchen noch
Umsetzungsfreigabe, keine bereits erteilten C/B-/Git-/Releasefreigaben erneut holen.

Keine Produktivcode-, Test-, QA-Daten-, Server- oder Timeränderung in diesem Schritt.
Die offene C/B-Integration samt Restore/Updater-Einführung bleibt Voraussetzung
des angeforderten VPS-Pulls. Daily3-Regeln einschließlich Übernachtregel bleiben
bestätigt; seine Dokumentation liegt inzwischen auf main `f84d9a6`. Letzter
VPS-Abgleich 18:12 UTC: `2dd1116`, App/Caddy/Health erreichbar; Tennis-Dienst failed.
Kein aktueller VPS-Zustand aus diesem Plan abgeleitet, kein neuer SSH-Lauf.

## Neueste Fortsetzung 13. September 2026, 18:04 UTC — Übernachtregel angenommen; VPS-Pull offen

Der Nutzer bestätigte „ja passt und vps pullen“. Daily3-Übernachtregel ist
damit freigegeben, nicht erneut abfragen. Spezifikation und Rechenprüfnotiz
sind aktualisiert; Daily3 ist noch nicht implementiert. Für die Übernahme
werden ausschließlich diese Dokumente betrachtet, kein C/B-Code-Merge.

Frisch per SSH: VPS main `2dd1116`, App/Caddy und beide Healthchecks `ok`;
sieben Timer geplant, Tennis-/Wettfinder-Dienste dennoch `failed`.
Installierter Updater weiterhin SHA `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`:
64-MiB-Grenze, echte Datenbank 499855360 Byte (rund 477 MiB). Er stoppt die
App vor der vollständigen Größenprüfung. Deshalb kein absehbar scheiternder
Updateaufruf, kein direkter Git-Pull als Umgehung, kein Serverneustart.
Aktueller Nachweis: `docs/audits/2026-09-13-daily3-vps-preflight.md`.
Der beauftragte VPS-Pull bleibt offen; eine Dokumentationsfreigabe ersetzt
keine ausstehende C/B-Prüfarchitekturentscheidung. Vorherige QA-Daten erhalten.

## Neueste Fortsetzung 13. September 2026 — Daily3-Spezifikation, keine Implementierung

Aktueller Nutzerauftrag ist der neue Bereich `3 a day keeps the job away`.
Bestätigt: CHF 50 eigenes Tagesbudget, höchstens drei Einzelwetten auf
unterschiedliche Events, abgerechnete Gewinne am selben Tag weiterverwenden,
kein Nachschuss und höchstens CHF 50 netto Verlust gegenüber Tagesstart.
Kein automatisches All-in, keine automatische Wettplatzierung und keine
Garantie von CHF 150 Gewinn. Cricket bleibt ausgenommen.

Schriftlicher Entwurf: `docs/superpowers/specs/2026-09-13-daily3-design.md`.
Codeabgleich und begrenzte Rechenprüfung:
`docs/audits/2026-09-13-daily3-spec-check.md`. Die Rechenprüfung ist kein
App-Test und kein Echtgeld-Release. Produktivcode, main und VPS unverändert;
Dokumentation wird ausschließlich im bestehenden Reparaturbranch gesichert.
Den tatsächlichen Commit-/Push-Stand anhand Git prüfen.

Damals noch offen, inzwischen oben bestätigt: Übernachtregel ohne neues
Budget bei offenen Vorgängerwetten. Genaue Rangfolge, reale Ergebnisbestätigung
und erste UI-Skizze sind weiterhin auszuarbeiten. Bereits bestätigte
CHF-/Budget-/Namensregeln nicht erneut abfragen. Keine Daily3-Antwort als
Freigabe der älteren C/B-CPU-Vertragsänderung auslegen. Der vorherige
Reparaturstand und alle erhaltenen QA-Dateien bleiben davon unberührt.

## Neueste Fortsetzung 13. September 2026,13:45UTC — zwei Fixes nativ geprüft; Vertragsentscheidung offen

Task62 Dateileser und Task63 begrenzte Dateiverwaltung sind unabhängig geprüft
und tatsächlich unter Linux bestätigt:43Tests sowie35Tests/1benannter
Windows-Skip. Task63 Source `bb54ec58eadcab0e9c0ae065aa258cb7a8f337d6`;
letzten Dokumentations-/Push-Commit anhand Git prüfen. Keine Testprozesse übrig.
Keine Task58-/Task60-/Task61-Protokollwiederholung.

Der vollständige größte Alt-QA-Ordner benötigt gemessen47,56CPU-Sekunden.
Die bestehende Kette liest jeden alten Ordner viermal, zweimal pro Prozess
mit jeweils60CPU-Gesamtlimit. Ein weiterer unveränderter großer Lauf ist
nicht begründet. Kein neues Task61-Ticket verbraucht, kein entsprechender
Worker gestartet, keine stille
Grenzwerterhöhung. Jetzt zuerst explizite Prüfarchitektur-/Budgetentscheidung
gemäß `naechste-entscheidungsgrenze-20260913.md` im aktuellen SDD-Verzeichnis.
Der historische FIFO-Negativtest bleibt erhalten; seine v2-Erfassung ist
noch nicht implementiert. Größeres C/B, Restore, Vollsuite und Rollout offen.

Frisch580c22: VPS/main `2dd1116`, App/Caddy aktiv, beide Healthchecks `ok`,
sieben Timer geplant; Wettfinder und Tennis dennoch fehlgeschlagen. Die Timer
berechnen, pullen/deployen keinen Code. Reparatur bisher nur im Reparaturbranch,
kein main-Push oder Produktivdeployment und kein Beleg für fertige empirische
Kontexteffekte. Alle alten Kosten/Fehler/WIP bleiben erhalten.

## Frühere Fortsetzung 13. September 2026,13:16UTC — historischer Zwischenstand

Nachtrag13:16UTC: Task62-Code `6eb267a` ist unabhängig freigegeben; echter
Linux-Gegenvergleich bestanden: Altcode scheitert am erwarteten Fehler,
Neucode43 Tests bestanden/keine Skips, SSH0, Ergebnisse separat zurückgelesen,
keine Testprozesse übrig. Noch keine Messung des gesamten großen Altbestands.
Vor dem Datenlauf wurde zusätzlich das echte1024-FD-Limit erkannt; mindestens
4546 Dateien sollen gleichzeitig gehalten werden. Task63 regelt dafür die
begrenzte prozesslokale Reservierung und einmalig gehaltene Vorfahren, ohne
die bisherigen Identitätsprüfungen zu reduzieren. Siehe aktuellen SDD-Ledger.

Der Accountwechsel ist abgeglichen; der bereits bestandene kleine native
Task58-Test und die beiden Task61-Prozessprotokolle werden nicht wiederholt.
Reparaturbranch `codex/context-capacity-recovery-20260910` ist bis
`68c1ff89042d26a9c9454a308e3fe65defa8947a` committed und remote bestätigt.
GitHub main und VPS stehen dagegen weiterhin auf
`2dd1116b68f3d94e9c24338c6c9dff9b01799221` — kein Produktivdeployment.

Das geprüfte Codearchiv1632072 wurde erfolgreich in den isolierten VPS-Bereich
übertragen. Der anschließende einzige Kontrolllauf wurde nach74,12Wandsekunden
mit Signal9 beendet, passend zur festen60CPU-Sekunden-Grenze. Noch vor der
ersten vollständigen Bestandsdatei; kein Datenlauf, kein neuer Beleg und keine
300CPU-Zulassung. Archiv unverändert, Job/Registry leer, kein Testkind übrig.
Alle Kosten und Fehlbelege bleiben erhalten; kein unveränderter Neustart.
Task62 optimiert ausschließlich wiederholtes Öffnen der Verzeichnispfade,
ohne Datei-/Hash-/Vollständigkeitsprüfungen oder Grenzwerte wegzulassen.
Autor arbeitet daran; Review und tatsächliche Linux-Messung bleiben offen.
Details/Writer im SDD-Ledger, Task61-native-preparation-evidence und Task62-Brief.

Frisch12:48/12:49UTC: betboy-app und Caddy aktiv, interne/öffentliche Healthchecks
`ok`, sieben Timer geplant. Wettfinder- und Tennis-Dienst bleiben fehlgeschlagen.
Timer berechnen, sie pullen/deployen keinen Code. Vollständiges C, B, Restore,
Vollsuite, Betriebsabnahme und kontrollierter main-/VPS-Rollout bleiben offen.
Das ist weiterhin kein Beleg für fertig validierte Verletzungs-/Müdigkeitseffekte
oder bessere Wetten. Die schon erteilten C-/B-/Commit-/Push-/Deploymentfreigaben
gelten weiter. Keine erneute Freigabe wegen alter eingefrorener Überschriften.

## Fortsetzung 13. September 2026 — Abbruch abgeglichen

Aktueller Abschluss dieses Schritts: Der echte kleine VPS-Test ist nach der
Fortsetzung nun BESTANDEN. Source588843d, Reparaturbranch-Checkpoint1ce94c8
vorher gepusht/frisch bestätigt. Tatsächlicher Exit0 nach75,44s; ATP und WTA
inklusive Rückrollfall und vollständiger Nachprüfung erfolgreich. Alle neuen
QA-Daten bleiben isoliert/erhalten, keine Testprozesse übrig. Ausführlicher
Beleg: `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-58-native-evidence-20260913.md`.
Task58/kleine native Kette nicht wieder neu beginnen. Jetzt folgt die vollständige
C-Integration, dann B-/Restore-/Vollsuite-/Release-Prüfung. App/main unverändert;
kein Nachweis einer bereits fertigen Verletzungs-/Müdigkeits- oder Wettqualität.

Task58-Code `588843d` ist lokal committed und unabhängig ohne Befunde
freigegeben. Review und vollständiges Prüfpaket sind erhalten. Der angekündigte
neue VPS-Test war vor dem Abbruch noch NICHT gestartet: frische Prüfung um
07:10:46UTC bestätigt fehlende neue QA-Pfade und keine Testprozesse. Auch lokal
laufen keine Python-/SSH-/Git-Prozesse und keine Unteragenten mehr.
App/VPS bleiben `2dd1116`, App und Caddy laufen, interner Healthcheck `ok`.
Der nächste Schritt ist der Push des geprüften Reparaturstands und danach der
isolierte native Test, kein Produktivdeployment. Die frühere Verlustmeldung
zum äußeren Test-Exit bleibt dokumentiert; XML73/0/0/0 ersetzt diesen Beleg nicht.
Gesamt-C, B, Restore, Vollsuite und main/VPS-Abschluss bleiben ausdrücklich offen.

## Aktuell 12. September 2026 — C freigegeben, verlustfreier Speicherumbau läuft

Neuester verifizierter Checkpoint: `0aa6e23c684ea9bb87c9bead6132f4bc8f2226e0`
ist auf `codex/context-capacity-recovery-20260910` gepusht und frisch bestätigt;
GitHub main und VPS-App bleiben `2dd1116`. Nicht alles ist erledigt.
FIX5-Code `bc6305c` hat60 gezielte Tests und ein unabhängiges sauberes Review.
Der vierte tatsächliche kleine VPS-Kettenlauf scheitert trotzdem noch VOR dem
Datentest: Pandas benutzt zusätzlich dateutil für UTC. Das ist durch einen
begrenzten tatsächlichen Import mit vollständigem Aufruferpfad belegt, keine
vermutete Ursache. Beide Original-/Kopie-Zeitzonendateien sowie sämtliche440
Code- und4540 Abhängigkeitsdateien sind separat vollständig nachgeprüft.
Alle Fehlversuche/Reservierungen bleiben erhalten; keine Testprozesse übrig.
Task58 ergänzt gerade als enges Vorhaben den zweiten tatsächlichen Leser und
sperrt dessen alternative gebündelte Zeitzonendaten. Anforderungen, Bytepins,
Prüfbefunde und aktueller alleiniger Writer stehen im SDD-Ledger/Task58-Brief.
Keine Wiederholung einer sechsten blinden Task57-Fixrunde, keine neue
Systemordnerberechtigung, keine Modell-/Quoten-/Produktivdatenänderung.
Offen bleiben der echte native Kettenpass, vollständige590553/199/199/114-Profile,
globale C-Bilanz, B-Nachweise/Restore, Vollsuite und endgültiger main/VPS-Rollout.
Die schriftlichen C-/B-Verträge sind freigegeben; alte "noch nicht freigegeben"-
Überschriften in den eingefrorenen Entwürfen verlangen keine erneute Zustimmung.

Historischer Zwischenstand:120814a ist gepusht/frisch remote bestätigt; FIX4-Code df874ba ist
mit36 gezielten Tests unabhängig freigegeben. Der tatsächliche dritte kleine
VPS-Lauf ist jedoch gestoppt: nun konkret fehlende Zeitzonendatei UTC, weiterhin
vor Task54-Aufbau, kein WTA-Lauf. Alle drei Fehlerstände/Reservierungen bleiben
erhalten, keine Testprozesse übrig. Nächster enger FIX5: die tatsächlich
benötigten öffentlichen UTC-/Zürich-Dateien exakt katalogisieren und im
isolierten Prüfpaket bereitstellen, keine Systemordnerfreigabe. Anforderungen,
Rohbelege und Fortsetzung stehen im Task57-Ledger/FIX5-Brief. Kein Gesamt- oder
Appabschluss; main/App weiterhin2dd1116, keine alten Daten verändert.

Neuester Nachtrag19:03UTC: Reparaturbranch48425b6 ist gepusht; der erste echte
isolierte Task57-VPS-Kettenlauf ist NICHT bestanden. ATP brach beim Import mit
`unplanned Python file read` ab, WTA wurde nicht gestartet. Alle Dateien und
die vollständige300CPU-Reservierung bleiben erhalten; kein Testprozess läuft
weiter. Reale alte/neue Quellkopien wurden bytegenau unverändert nachgeprüft.
Lokal ist der Auslöser reproduziert: Python sucht trotz `-B` zuerst eine
Bytecode-Cachedatei. Der enge Quellcode-Fallback ist als97e3bb6 lokal committed,
mit32 bestandenen Tests und unabhängigem Review freigegeben; kein Bytecode
oder ganzer Ordner wird freigegeben. Ein zusätzlicher lokaler Gesamttest kam
nicht bis zur Ausführung; neuer nativer Lauf fehlt noch. Details und Rohbelege:
`.superpowers/sdd/2026-09-10-context-capacity-recovery/task-57-native-preparation.md`.
App/main bleiben2dd1116, App/Caddy und beide Healthchecks funktionieren,
sieben Timer sind geplant; der separate tägliche Tennisfehler bleibt offen.
Die folgenden älteren Fortschritte sind Baustein-Nachweise, kein Gesamtabschluss.

Neuester unabhängig geprüfter Code-Commit:
`4d538203d2b50c61b6dfba9e7681b7e0061e9f56`, auf dem Reparaturbranch gepusht
und frisch mit GitHub abgeglichen. Main bleibt `2dd1116`, kein Appdeployment.
Task51 ist damit im engen Scope abgeschlossen: echter gleicher Tennisaufruf,
vollständige Referenzen/Analysebytes und atomare Speicherung. Der unabhängige
Reviewbefund zum letzten Abschluss-/Rückrollpfad ist nach echter RED-Probe
behoben und unabhängig nachgeprüft; keine offenen Befunde aus diesem Teil.
Finaler gekoppelter Lauf:411 bestanden in84,95s. Die früheren704 Tests sind
separat als Vor-Rowid-Stand dokumentiert, nicht als kompletter neuer Produktlauf.
Task53 (`d787db4`):424 Tests bestanden und unabhängiges Review freigegeben.
Task48 (vollständige echte Kopie plus neue Belege) ist mit72 bestandenen Tests
und unabhängigem Review abgeschlossen, nicht der gesamte C-/B-Pfad.
Task52 hat eine echte alte/neue Einzelwert-Zulässigkeitslücke nachgewiesen:
die neue History sperrte große bisher akzeptierte Zeilen. Task53 behebt das
mit gebundenem Altlesepfad in History UND Tennis; vollständige alte Bytes
werden verglichen, keine neue Einzelwertgrenze. Der ebenfalls geprüfte Task51
baut darauf den echten Tennis-Consumer auf. Anforderungen/Befunde liegen im SDD-Verzeichnis.
Main weiterhin `2dd1116`. Feste Rohkopie mit
begrenztem Reader unabhängig geprüft (197 bestanden, zwei Windows-Skips).
Der dritte isolierte VPS-Nachtest hat jetzt alle sechs Diagnosefälle bestanden:
Exit0 und2,61s tatsächliche äußere Wallzeit. Der geprüfte enge Pollfix besteht
zusätzlich437 kombinierte lokale Tests. Task50 enthält den vollständigen
bytegleichen nativen Report samt eigener Reichweite; dessen unabhängiger
Ergebnisabgleich bestätigt die Konsistenz, kein C-Gesamtpass.
Die ersten beiden roten Versuche bleiben vollständig erhalten, alle drei
Versuche konservativ mit insgesamt270CPU-s belastet. Neuer letzter VPS-Read:
Apprevision `2dd1116`, App/Caddy aktiv, interner Healthcheck `ok`, keine
Test-UID-Prozesse übrig. Der echte einzelne Receiptappend ist unabhängig
geprüft (316 bestanden, keine Skips) und nach Accountwechsel gepusht/frisch
remote bestätigt; nochmals136 gezielte Tests bestanden. Task48 verbindet Kopie
und neue Receipts und ist nun unabhängig geprüft. Task54 ist jetzt mit
`cac8db725b4c9ffac6bbcb4f81817d90da2823c9` lokal committed und unabhängig
freigegeben: durchgehender echter ATP-/WTA-Alt-/Neu-Vergleich, genau drei neue
Belege, vollständige Rohdaten/Analysebytes und Rücklesen nach dem Speichern.
Finale lokale Läufe:5 neue Tests sowie34 gezielt gekoppelte Tests bestanden.
Ein kleiner fehlender Testvergleich des neuen Original-Zeitstempels ist als
Task54-M1 dokumentiert; kein Produktfehler nachgewiesen. Der Reportanspruch
wurde entsprechend präzisiert. Code samt Review/Übergabe ist als `ca663ec`
gepusht und frisch remote abgeglichen; main unverändert `2dd1116`.
Task57 ist als Prüftreiber abgeschlossen:eddc926 lokal committed,28 Tests
bestanden in10,123s; beide wichtigen Reviewbefunde behoben und unabhängig
nachgeprüft. Tatsächliche Originalbelegung wird erfasst, ein Start ohne vorherige
Reservierung ist abgesichert. Ein plattformspezifischer Testhinweis bleibt für
die abschließende Linux-Prüfung dokumentiert. Das ist noch kein nativer Erfolg.
Der geprüfte Stand wird jetzt separat auf dem Reparaturbranch gesichert;
erst danach folgen tatsächliche Paketaufnahme und isolierter VPS-Kettenlauf.
Task56 und die bisherigen Paketnamenaufnahmen sind nur lesende Vorbereitung.
Der neue Treiber hält die genau geprüften Startbytes selbst; derselbe begrenzte
Prozess verbucht Kopie, Isolation und beide Testläufe, ohne versteckte
Vorinstallation. App/main werden dadurch nicht verändert.
Aktueller rein lesender VPS-Check17:49UTC:weiterhin2dd1116, App/Caddy aktiv,
interner Healthcheck ok, sieben nächste Timertermine, keine Test-UID-Prozesse.
Der bekannte tägliche Tennisdienst bleibt fehlgeschlagen und ist nicht behoben.
Nachtrag native Vorbereitung:geprüfter Zwischenstanda339a82 gepusht; genaues
Codearchiv isoliert übertragen,4540 tatsächliche Paketdateien lesend erfasst.
Noch kein eigentlicher Prüflauf:der lokale Windows-Starter scheiterte am festen
Linux-Pfadformat. Minimal behoben alsba9c88f lokal (30 bestandene Tests),
unabhängiges Nachreview jetzt sauber abgeschlossen. Keine Normalisierung fremder Pfade, keine
Rootausführung des leeren fehlgeschlagenen Starters und kein Appdeployment.
VPS-Platzaufnahme16:16UTC:14125256704Bytes frei, keine Ressourcenabnahme.
Native Speicher-/CPU-Werte sind durch lokale Tests nicht belegt.
Der kleine lokale Kettenvergleich ist abgeschlossen. Native Kette, vollständige
Größenprofile, globale Ressourcenbilanz und B sind noch nicht fertig.
Keine C-Produktivaufrufroute, kein main-Push oder Appdeployment daraus ableiten.

Der Nutzer hat die konkrete Speicherfrage mit **„ja“** beantwortet.
C-Spezifikation `08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba`
ist freigegeben; die darunter archivierte Angabe „Speicherentscheidung offen“
ist überholt. B bleibt ebenfalls freigegeben. Nicht nochmals danach fragen.
Ausführungsplan: `docs/superpowers/plans/2026-09-12-kontextspeicher-umsetzung.md`.

Isolierter Worktree `context-capacity-recovery-20260910`, Start `b2e811a`.
Neue, noch nicht produktiv aufgerufene Module unter `context_storage_v2`:
vollständiges typisiertes Rohinventar, gemeinsame Referenzblöcke, vollständige
plattengestützte Tourhistorie und rechnerisch identischer Tennis-Lesepfad.
Zusätzlich umgesetzt: durchgehend FD-gebundene vollständige Rohkopie und
Snapshot-Quelladapter mit vollständigem Coveragevergleich, Rücklesen nach
Schließen/Öffnen und explizitem Erhalt unbekannter Rohobjekte. Unabhängige
Reviews fanden und schlossen Dateitausch-, WAL- und NUL-Metadatenfälle;
Tests/RED-Belege bleiben dokumentiert, nicht vom späteren Grün überschrieben.
Ein Autor pro Bereich; Root besitzt Index/Integration/VPS. Die unabhängigen
Bausteinreviews sind abgeschlossen. Der erste Gesamtlauf ist beendet; genaue
Einordnung und korrigierte lokale QA-Umgebung stehen weiter unten.
Bausteine sind KEIN C-/B-/Releaseabschluss.
Alte Modell-/Quell-/Feature-/Verifierdateien bleiben in diesem Abschnitt gleich.

Neue explizite Grenzen: Eingabesatz4GiB, kanonische Tourhistorie1GiB,
Verarbeitungsblöcke16MiB, gesamter neuer QA-/Aufbau-/Ausgabebereich8GiB,
freie Reserve4GiB. Unveränderte WorkerCPU/RAM- und gesamte B-Vorbereitungsgrenzen.
Noch kein neuer nativer C-Vorbereitungsauftrag, keine C-Migration und kein Rollout.
Frischer lesender VPS-Check dieser Ausführung: Apprevision `2dd1116`, App/Caddy
aktiv, interner Healthcheck `ok`; Wettfinderlauf09:07:28–09:13:57CEST erfolgreich,
nächster Timer09:37. Updaterhash `74b1c4b1` stammt weiterhin aus voriger Prüfung.
Bausteinstand `c5912a7cb8ae095b7e7f63a0b3ce6ae2aaf9052a` ist committed und
auf `codex/context-capacity-recovery-20260910` gepusht; GitHub danach lesend
exakt bestätigt. GitHub main bleibt `2dd1116b68f3d94e9c24338c6c9dff9b01799221`.
Nachfolgender geprüfter Bausteinstand `d643f4884bbfa6dcf88b292c6f6fbd1c666a9867`
ist ebenfalls auf diesem Reparaturbranch gepusht und frisch remote bestätigt.
Danach Diagnosecode `c79bb10` und geprüfte History-/Tennis-Integration
`898398295056aabd68d35da3ab58441c5c46f34a` ebenfalls auf dem Reparaturbranch
gepusht, letzter Stand frisch remote bestätigt. Kein main-Push und kein
behaupteter aktueller Server-C-Stand.
Separate bekannte Tagesjob- und empirische Modell-/Quellenarbeit sowie Cricket
bleiben außerhalb C/B.

Fortsetzung ohne Lücke: `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-16-controller.md`
enthält die aktuellen Testläufe, Findings, Besitzgrenzen und konkrete nächste
Arbeit. Globale Mehrdatei-/TEMP-/Budgetkontrolle, echter kompletter Wachstumsbestand,
B-Nachweise/Bootstrap, native Messungen/Restore und Rollout stehen noch aus.
Der erste Gesamtlauf auf c5912a7 ergab 7897 bestanden, 6 fehlgeschlagen,
30 Skips und 97 Untertests. Alle sechs Fehler gehörten zum Update-Hook: seine
echten isolierten CLI-Kinder sahen SciPy nicht, obwohl der Elternprozess es
über PYTHONPATH fand. Keine Test-/Produktänderung dafür. Eine neue lokale
QA-venv bindet den vorhandenen Dependency-Pfad auch unter `-I`; danach bestehen
alle 340 unveränderten Tests dieses Moduls. Der erste rote Gesamtlauf bleibt
rote Evidenz und ist kein nachträglich behaupteter Gesamtsuiten-Pass.
Details/Hashes: task-25-local-qa-runtime.md. Neue spätere Module sind vom alten
Gesamtlauf nicht abgedeckt; ein vollständiger Lauf des nächsten eingefrorenen
Standes bleibt erforderlich.

Task21/26: eigene Chunk-Schnittstelle in den neuen Snapshot-Leser integriert;
355 verbundene Tests plus 118 unabhängige Alt/Neu-Proben bestanden. Wirkliche
vollständige 5k-/50k-Snapshot-Reads lokal etwa acht-/neunmal schneller, sämtliche
Bytes/Digests gleich. Kein nativer Größen-/CPU-Pass. Task24: globaler fester
Accountingplan plus unabhängiger Device-Fix geprüft (90 pass, drei echte
Windows-Symlink-Skips); weder native Quota noch atomarer Filesystemsnapshot.
Task23 Vorbereitungskostenbuch unabhängig geprüft: 91 bestanden, drei native
Linux-Skips; öffentliche Journalhashes sind keine Authentisierung. Task29 ist
nun abgeschlossen: 8114 bestanden, 31 Skips, 97 Untertests, 2052,78 Sekunden.
Die drei neuen SQLite-/Guard-/Supervisor-Testmodule waren ausdrücklich nicht
in diesem Vollsuitenlauf; Details/Bytebindung: task-29-full-prelude-regression.md.
SQLite-Profil separat unabhängig 393 grün, NoExec-Guard 212 grün/fünf native
Skips; Supervisor-Erstreview fand und schloss sieben reale Lifecycle-Probleme.
NoExec-Folgereview 173 grün, zusätzlicher enger Parent-Umgebungsreview194 grün.
Task33/36 kleiner nativer Diagnosepfad und Root-Sealer sind fertig und in
Task37 unabhängig mit134 portablen Prüfungen gegengeprüft. Danach tatsächliches
neues QA-Sealing auf dem VPS erfolgreich (12,54s), erster nativer Diagnose-
versuch RED (1,59s): beim Beenden fehlte VmHWM vor Zombie-State. Voller Charge
und alle Artefakte erhalten, nichts an App/alten Dateien/Diensten verändert.
Task41/42 korrigieren genau diese Exit-Messrace;270 Gegenprüfungen grün.
Zweiter nativer Start noch offen, vollständige genaue Evidenz in Task41.
Task35 verbindet nur die neuen C-History-/Tennis-Builder mit dem geprüften
SQLite-Profil (580 lokal grün, Root-Integration6 grün); Task38 abgeschlossen,
359 unabhängige/kombinierte Tests grün. Task40 erhält106 native Protokoll-
regressionen als normale Tests. Task39 benennt weiterhin fehlenden vollständigen
Corpus-/Consumer-/Reopen-Datenfluss. Task43 fester Copy-/Readeranschluss und
Task44 echte transaktionsgebundene Receiptoperation in Arbeit; kein fertiger
Gesamtaufbau. Weiterhin keine Produktionsaufrufroute.
Der neue Coordinator muss frisch und geheimnisfrei starten: Fork kopiert
Arbeitsspeicher; ein B-Schlüsselpublisher darf nicht als Worker-Parent dienen.
VPS rein lesend: Linux6.8, gepipter Apport-Absturzhandler, Python3.12.3. Daher
Dumpable0 vor Workerarbeit und kein anschließendes exec; keine Host-/sysctl-
Änderung, kein absichtlich ausgelöster Crash. Keine globale Core-/Logfreiheit
aus einer lokalen Simulation behaupten.

## Neuester Abschluss 12. September 2026 — B0 gemessen, Speicherentscheidung offen

Die Freigabe „ja maxhrn“ für B wurde ausgeführt: zuerst frisches Backup/Restore/
Kontointegrität (88 DBs), dann die unabhängige geprüfte native Größenprobe.
Quelle72421d3 blieb unverändert. Echte versiegelte Kontextdatei73ec1691:
100553Belege,31Snapshots,270233600Bytes; volle ATP-Historie58390805Bytes,
WTA75669070Bytes. Rund92.496Prozent der Ist-Snapshotbytes sind Referenzlisten.

**B0 StorageSTOP:**146782tatsächlich neu erzeugte/normalisierte/dekodierte/
ausgewählte synthetische ATP-Belege ergeben268435847kanonische Historybytes,
391über256MiB. Zwei70000er-Portionen vollständig, dritte nach6782Zeilen beendet.
Das ist eine notwendige synthetische Größenprüfung, kein künftiger Echtspielplan,
kein prognostizierter Ausfalltag, kein199Snapshot-/D4-/Sieben-Tage-PASS.
Keine alte Zeile verändert, keine Wachstumskopie oder neuen Snapshots geschrieben.

Alle vier Messlogs unverändert/Exit0, unabhängig vollständig gegengeprüft.
Native Kosten mit Backup332.16CPU/333.21Wandsekunden; konservative gesamte
Auftragszeit1631Sekunden (23:19:00–23:46:11UTC). Keine weiteren nativen Tests
nach dem tatsächlichen Größenfehler, keine neue Produktvollsuite oder B-Code.
Helper und8Owner-Gegentests samt exakten Bytes im Evidencearchiv erhalten.

Aktueller Ergebnisbericht:
`.superpowers/sdd/2026-09-10-context-capacity-recovery/task-14-sizing-result.md`.
Rohlogs/Hashes und ausführliche Reviewbelege stehen im gleichen SDD-Bereich.
Neue noch NICHT freigegebene Entscheidungsvorlage:
`docs/superpowers/specs/2026-09-12-kontextspeicher-entscheidung.md`.
Fester VorschlagSHA08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba;
unabhängig als Entscheidungsvorlage geprüft, Review185d45dc272d611c636f64bd34fcbec00965a84fe11cc7f3aec75ca9192f0f0f.
Sie schlägt verlustfreie versionierte Speicherung und vollständige blockweise
Verarbeitung vor; neue explizite Gesamtgrenzen müssen genehmigt werden.
Die bereits gegebene B-/Commit-/Push-/kontrollierte Rolloutfreigabe gilt weiter,
ersetzt aber nicht diese im B-Vertrag ausdrücklich getrennte Speicherentscheidung.

GitHub main und VPS2dd1116 unverändert, alter Updater74b1c4b1. App/Caddy/7Timer
aktiv+enabled, beide Healthchecks200ok; separater Tennis-Tagesjob failed bleibt
offen. A0/P4b3, Cricket und empirische Kontextabnahmen bleiben außerhalb dieses
Schritts. Kein App-/Updaterrollout, keine Schlüssel-/Benutzer-/Dienstinstallation.
Root besitzt weiter Index/VPS; andere Worktrees und bekannte ungetrackte Dateien
bleiben unverändert. Der nachfolgende Zwischenstand „B0 läuft“ ist überholt.

## Neueste Freigabe12.September2026 — B angenommen, B0 läuft zuerst

Auf die konkrete Frage nach isoliertem Prüfer, geschützten Nachweisen und
maximal1800CPU-/3600Gesamtsekunden Vorbereitung antwortete der Nutzer
„ja maxhrn“. Der B-Vertrag498e63c5 ist damit freigegeben; nicht erneut fragen.
B0 beginnt mit einer frischen echten Backup-/Restore-/HMAC-Kette und versiegelter
Kontextkopie. Danach begrenzte Messung ausgewählter kanonischer Historiemaße,
vorhandener Snapshotreferenzen und sourcegültig generierter ATP-Größenprobe.
Keine volle7Tage-Abnahme aus einer Hochrechnung ableiten. Bei tatsächlicher
Größenüberschreitung gemäß Vertrag erst separate Speicher-/Eingabeentscheidung;
keine stillen Grenzerhöhungen, Kürzung oder historischen Umschreibungen.
Noch kein B-Produktpatch oder Server-Rollout. Ausgangspunkt6a0ba81 sauber,
Produktbytes72421d3; Root besitzt Index, Integration und VPS-Ausführung.
Die nachfolgende alte „B-Entscheidung offen“-Angabe ist damit überholt.

## Aktuell12.September2026 — A1 beendet, konkrete B-Entscheidung offen

Die jüngste Freigabe „ja alles machen“ zum Kapazitätsplan05f7e6f wurde bis zur
darin ausdrücklich vorgesehenen Architekturentscheidung ausgeführt. **A1 STOP:**
kleine Wiederverwendung spart zu wenig; kein neuer A-Produktpatch. Unabhängige
Traceauswertung und12vollständige native Diagnosepaare dokumentiert. Der neue
Diagnoselauf endet ordentlich nach184,453215CPU-/183,117809Wandsekunden mit
unveränderter G1-Eingabe; er ist ausdrücklich kein D4-/Kapazitätspass.

Echte Live-Metadaten22:12UTC:99776Belege,31Originale/Snapshots,16ATP-Cutoffs,
268824576DBBytes. Nicht mit der synthetischen G1-Datei verwechseln. Das
vorläufige7Tage-Profil589776/199/114ist nicht abgenommen; bedingte Größenrechnung
warnt vor1GiB-Eingabe und256MiB-kanonischer Historie. B-Prüfreuse löst diese
Speichergrenzen nicht. Keine Datenkürzung, höhere Limits oder kleinergerechnete
Probe verwenden, um einen Pass zu erhalten.

Entscheidungsvorlage:
`docs/superpowers/specs/2026-09-12-versionierte-pruefnachweise.md`,
SHA498e63c5641adaccdd4d284fa9b57ad93c02ba834e9abd6bf4064636d6b12da1.
Unabhängig geprüft; einziger P2(Closure vor Reuse, auch lazy/native/resources)
gezielt behoben und nachgeprüft. Konditioneller Ablauf:
`docs/superpowers/plans/2026-09-12-versionierte-pruefnachweise-umsetzung.md`.

**Nächster Schritt:** Nutzer entscheidet den konkret neuen B-Nachweis-/
Betriebsvertrag: eigener isolierter Prüfer, root-geschützter Proofbestand,
eigener Proofschlüssel, explizite1800CPU-/3600Gesamtsekunden-Vorbereitung bei
unverändert begrenztem Abschlusscheck. Nicht erneut nach Commit/Push fragen.
Danach zuerst echte Größenprobe; bei Überschreitung separate Speicher-/
Eingabevertragsentscheidung vor B-Code. B nicht durch alte „alles“-Antworten
als schon genehmigt behandeln; der freigegebene Plan verlangte diese konkrete
neue Entscheidung ausdrücklich. Kein Produkt-/Serverpatch bis dahin.

Sämtliche Produkt-/Testbytes weiterhin72421d3. Dokumente/Metadaten werden normal
auf dem Reparaturbranch gesichert; kein main-Push/Updateraustausch/Appdeployment.
GitHubmain/VPS frisch2dd1116, alterUpdater74b1c4b1root:root0755/134237Bytes.
App/Caddy aktiv+enabled, siebenTimer aktiv+enabled+geplant; beideHealth200/ok.
Separaterbetboy-tennis.serviceweiterhinfailed, nicht zurückgesetzt. Keine neue
Vollsuite; alte7292+97Untertests gehören weiterhin1c65ada, nicht724 oder B.
Keine laufenden QA-Prozesse. Root besitzt Integration, bekannte alte Ausgaben
und andere Worktrees unangetastet. Cricket/A0/P4b3/empirische Modelle separat.

Belege: SDDtask-12-stage-a-result.md, task-12-stage-a-feasibility.md,
task-12-diagnostic-review.md, task-13-growth-sizing.md,
task-13-stage-b-design-review.md und evidence/task12*/task13*.
Die folgenden „aktuell/läuft/nur planen“-Abschnitte sind ältere Historie.

## Aktuelle Ausführung — Plan mit „ja alles machen“ freigegeben

Der neue Kapazitätsplan ist zur Ausführung freigegeben. Zuerst läuft ein
begrenzter Machbarkeitsnachweis für A gegen240Sekunden Reserve und einen
aus echten Wachstumsdaten abzuleitenden7Tage-Horizont. Kein blinder A-Umbau,
wenn schon die Ersparnisgrenze nicht reicht; dann konkret B ausarbeiten.
Die gespeicherten G1-Phasen werden unabhängig ausgewertet. Root besitzt Index
und Integration. Noch kein neuer Produktpatch oder Release; ursprüngliche
Produktbytes72421d3 und bisherige Freigabegrenzen gelten bis zur konkreten
Umsetzung. Ausgangs-HEAD05f7e6f ist sauber geprüft. Alte „nur planen“-Abschnitte
darunter sind durch die neue Nutzeranweisung abgelöst.

## Neueste Nutzeranweisung — nur planen, noch keinen Code schreiben

Der Nutzer verlangt einen Lösungsplan zum Kapazitätsfehler. Er ist unter
`docs/superpowers/plans/2026-09-11-pruefarchitektur-kapazitaet.md` gespeichert:
begrenzte Wiederverwendung innerhalb eines Prüflaufs (A), klare Kosten-/Abnahme-
Stoppregel und separat freizugebende dauerhafte Prüfarchitektur (B).
Dies ist keine Umsetzungsfreigabe für A oder B. Produktcode bleibt unverändert
auf den in `72421d3` enthaltenen Bytes; keine neuen Tests oder VPS-Aktionen.
Der letzte vor dieser Planung bestätigte Reparaturbranch-Checkpoint ist
`f2763b2`. Die nachfolgenden Fehlerbefunde und Release-Sperre bleiben gültig.

## Verbindlicher Fortsetzungsstand — 11. September 2026, Wachstumstest gescheitert

Der geprüfte Reparaturcode ist `72421d3bdbec4ab15a3d2953cb153e867e7e340a`.
Er ist samt Review und bisheriger Dokumentation auf dem Reparaturbranch
`codex/context-capacity-recovery-20260910` gepusht (Checkpoint `0f074a2`).
Nicht mit einer Veröffentlichung auf `main` oder dem VPS verwechseln.

Die echte Kopie mit 30 Analysen besteht die vollständige Serverprüfung:
288,095 CPU-/288,261 Wandsekunden, 485440 KiB Spitzen-RAM.
Die größere Kopie mit 31 verschiedenen Analyseabfragen scheitert dagegen:
299,975 CPU-/300,165 Wandsekunden, Prozess beendet, kein vollständiger Report.
Alle Eingabedaten blieben unverändert. Die vorbereiteten 32-/33er-Kopien
wurden noch nicht als D4 geprüft. Deshalb bleibt die Veröffentlichung gestoppt.

Die anschließende begrenzte Messung ist abgeschlossen, kein Test läuft mehr.
Der einzelne zusätzliche Originalabruf kostet nur 1,36 CPU-Sekunden.
Erneute Historienrekonstruktion und vollständige Feature-Prüfungen dominieren.
Der untersuchte nächste Ansatz würde die Wiederholungsfrequenz interner
Prüfungen ändern; das ist nicht stillschweigend durch die Zusage
„unveränderte Prüfungen“ gedeckt. Task11 ist nur Analyse, kein neuer Code.
Vor einer solchen Änderung ist eine ausdrückliche Vertragsentscheidung nötig.
Keine Grenzerhöhung, Kürzung, Modelländerung oder künstliche Freigabe.

`main`, GitHub-`main` und VPS stehen weiterhin auf `2dd1116`; installierter
Updater unverändert. Frisch lesend geprüft: App und Caddy aktiv, alle sieben
Timer aktiv und geplant, interne/öffentliche Healthchecks jeweils `200/ok`.
Der separate Tennis-Tagesjob bleibt `failed` und wurde nicht zurückgesetzt.
Die letzte große Vollsuite (7292 + 97 Untertests) gehört zu `1c65ada`,
nicht zu `72421d3`. Der neue Gesamt-Testlauf wurde nach G1-Fail zurückgestellt.

Exakte Belege/Fortsetzung: SDD `progress.md`, `task-10-native-evidence.md`,
`task-11-growth-analysis.md`. Code/Testbytes bleiben eingefroren; Root besitzt
Index und Integration. Bekannte Worktrees und alte Ausgaben sind erhalten.
Cricket, A0/P4b3 und die empirische Fünfsport-Abnahme bleiben offen/ausgenommen.
Die nachfolgenden „läuft“-Abschnitte sind ältere, nicht aktuelle Checkpoints.

## Aktuell — Korrektur72421d3 geprüft; echter Serverdaten-Test läuft

Task10 und sein gefundenerCallbackfehler sind committed. Die gezielte Korrektur
bestand239Dispatch/Witness- und56Inventurtests; unabhängiges Nachreview24Fälle
und ursprünglicher Fehlervergleich grün. Alle bisherigen Prüfregeln/Grenzen
und mathematischen Modelle unverändert. Root besitzt wieder Index/Integration.
Exaktes Archiv841Datei-/Verzeichniseinträge nach Hashprüfung aufVPS versiegelt:
`/var/lib/betboy-capacity-code-5es6n672/source`. Vollständige CLI-Prüfung dieser
72421d3Bytes auf echter30Analyse-Kopie läuft alsUID997 Kind206801. Noch kein
neues Kapazitätsergebnis; früheres Scheitern nicht durch lokaleTests ersetzt.
Zusätzliche31/32/33Analyse-Kopien fertig/versiegelt, ihreD4Prüfung noch offen.
Root sichert/pusht den Reparaturstand samt Belegen, nochkeinmain/VPSRollout.
Code/Testbytes bleiben724; aktuelleAnweisungen/Nachweise inSDD`progress.md`,
`task-10-native-evidence.md`, `task-10-p2-rereview.md`. Main/VPS2dd1116 und
alterUpdater unverändert; App/Caddy/sevenTimersaktiv, Healthbeideok, separater
Tennisjob weiterhinfailed. KeineCricket/A0/P4b3/empirischeFünfsport-Abnahme.

## Fortsetzung — Task10-Code eingefroren, neue Server-Testkopien entstehen

Die beiden freigegebenen Prüfroutinen sind geändert;117neue Grenzfälle grün.
Der größere gezielte Lauf auf exakten Produktbytes läuft noch. Implementierer
besitzt Index/zweiCodefiles/neuenTest/Report; Root nur Controllerdoku undQA.
Unabhängig geprüfter Generator samt äußerer Begrenzung ist auf dem VPS im
isolierten Testbereich versiegelt. Er ergänzt echte31/32/33Testanalysen über
unveränderte Modellbesitzer auf einer Kopie des gesamten frischen30erBestands.
G1 läuft; noch keine neue D4-Abnahme. Produktionsdaten, main/VPS2dd1116 und
installierterUpdater unverändert. Kein lokales Grün ersetzt die fehlgeschlagene
reale Kapazitätsprüfung. GenauerFortsetzungspunkt: SDD`task-10-native-evidence.md`
und`task-10-brief.md`; kein erneutes Fragen nach derselben Rolloutfreigabe.

## Fortsetzung — Task10 vorbereitet, gleiche Prüfregeln und Grenzen

Zwischenstand06ab4af ist auf dem Reparaturbranch gepusht und remote bestätigt.
Die begrenzte Messung ist beendet: fast alle Feature-Prüfkosten entfallen auf
Wiederholungen von Typ-/Byte-/SQLite-Prüfungen, nicht auf die Modellrechnung.
Task10-Brief/Plan erlaubt nur deren unveränderte Ausführung mit weniger
Generator-/Cursor-Verwaltung in zwei Prüfroutinen. Keine abgeschwächte Regel,
keine höheren Grenzen, keine Daten-/Modelländerung. Ein frischer Implementierer
mit RED und unabhängigem Delta-Review folgt; noch kein Task10-Produktcode.
Alle bisherigen Jobs sind beendet. Finaler SQL-Test auch Linux3Fälle bestanden;
der vorherige breite Linuxmodul-Timeout bleibt gesondert dokumentiert.
Der frische30Analyse-Bestand scheitert weiterhin; main/VPS2dd1116 unverändert.
Aktuelle Anweisungen: SDD`task-10-brief.md`, `fresh30-capacity-analysis.md`,
`progress.md`, `task-9-native-evidence.md`. Gleich erteilte Freigaben gelten,
aber nur echte neue Serverabnahme erlaubt den freigegebenen Rollout.

## AKTUELL — frischer30-Analyse-Bestand scheitert, noch kein Deployment

Die letzte echte Serverprüfung ist fehlgeschlagen: aktuelles Vollbackup
enthält30statt26gespeicherte Analysen,99774Belege/32Artefakte,265793536Bytes.
Exakter1c65ada-Lauf wurde nach299,978CPU-/300,233Wandsekunden beendet, kein
vollständiger Report; Daten unverändert. Frühere kleinere Profile bestanden,
belegen aber diesen gewachsenen Bestand nicht. Grenzen werden nicht erhöht.
Vollbackup aller88DBs samt tatsächlichem Restore/HMAC bestanden41,49s.
Lokale exakte Vollsuite:7292Tests und97Untertests bestanden,30Skips1792,20s.
Gesamtreview und gezieltes Nachreview sind freigegeben, letzter SQL-Testfix
bc9d268ohneProduktänderung; das ersetzt den fehlgeschlagenen Serverlauf nicht.
Main/GitHubmain/VPS bleiben2dd1116, alterUpdater unverändert. Reparaturstand
wird auf seinem Branch gesichert/gepusht, noch nicht als fertig deployed.
Nur lesende Anschlussanalyse der übrigen Prüfkosten läuft. Mathematische
Modelle/Quellfeatures/Cricket/A0/P4b3/Daten/Budgets bleiben unverändert; der
separate Tennis-Tagesfehler und empirische Modellarbeiten bleiben offen.
Aktuelle genaue Nachweise: SDD`progress.md` und`task-9-native-evidence.md`.

## Neuester Stand — Task9 besteht Serverprofile, Veröffentlichung noch offen

Alle fünf exakten1c65ada-Serverprofile sind bestanden: aktueller Bestand
262,838s; G1/G2/G3 je149,913/158,686/170,665s; historische größte Kopie mit
188791Belegen136,809s. Grenzen, Mathematik und vollständige Prüfungen bleiben
unverändert. Echte UID997-Berechtigungsprüfungen und sieben Dateirennen grün;
Linux-Tennis-Kohorte75Tests bestanden. Vollsuite und Linuxintegration laufen.
Das einmalige Gesamtabschlussreview ist APPROVED ohne schwere Findings;
eine instabile SQL-Reihenfolgeannahme im Test wird separat mit echtem RED
und gezieltem Nachreview korrigiert. Produktdateien bleiben dabei identisch.
Noch fehlen frisches Vollbackup mit Restore/HMAC, Bestätigung der aktuellen
Daten und tatsächliche Veröffentlichung. Main/GitHubmain/VPS bleiben2dd1116;
kein Updateraustausch oder Appdeployment erfolgt. Die erteilte Freigabe gilt.
Bekannter Tennis-Tagesfehler und empirische Modellabnahme bleiben gesondert.
Neueste Details stehen in SDD`progress.md` und`task-9-native-evidence.md`.
Darunterstehende Laufzustände sind ältere, absichtlich erhaltene Nachweise.

## Aktueller Stand — Task9 geprüft, aktueller VPS-Test läuft

07d975f ist auf dem Reparaturbranch gepusht und scoped korrekt, besteht den
aktuellen vollständigen Datenbestand aber noch nicht unter300CPU-Sekunden.
26/26Original-Projektionen greifen, keine Query-/Cache-Verdrängung; spätere
vollständige Snapshots kosten rund9CPU-Sekunden statt4. Task9-Design/Plan/Brief
begrenzen die nächste interne Prüfroutinenänderung: echter physischer Decoder
und komplette Tennis-Quellprüfung direkt im selben Besitz-/Aufrufrahmen,
separate vollständige Gegenprüfung bleibt. Root-Ruling unter vorhandener
Prüfreparaturfreigabe dokumentiert; keine Mathematik-/Daten-/Limitänderung.
Task9-Code ist mit `1c65adae1e9de85a6d457cf452f21c4d9cbb589e` lokal committed
und unabhängig APPROVED ohne offene Findings. Exakter Produktlauf1109Tests
bestanden/12Plattform-Skips; finale75neue Fälle und spätere Zählerverstärkung
separat grün. Reviewer365+32Tests und12zusätzliche gespeicherte Quellfälle grün.
Der reale Regressionstest zeigte vorher20statt10physische Decodierungen.
Root besitzt wieder den Index; Produkt-/Testdateien bleiben eingefroren.
Exaktes Archiv33907914Bytes, SHAa3df9e45...847e00, geprüft übertragen und
unter`/var/lib/betboy-capacity-code-iym7re_h/source` root-versiegelt.
Aktueller vollständiger CLI-Lauf auf99521Belegen/26Analysen läuft alsUID997,
Kind203242, mit unveränderten Grenzen. Noch kein Mess-/Abnahmeergebnis.
Vollsuite/Gesamtreview/aktuellerVPS-PASS und Deployment fehlen weiterhin.
Main/GitHubmain/VPS bleiben2dd1116; bekannterTennisjob-Fehler nicht als behoben
melden. Task8-Diagnosen und Linux-Prüfungen sind beendet; nur der neue aktuelle
Task9-CLI-Lauf ist aktiv. Task9 muss zuerst diesen Bestand bestehen, danach
Wachstum/Vollsuite/Review/Backup und die getrennten Deployment-Schritte.
Gleiche Commit-/Push-/Deploymentfreigabe nicht nochmals abfragen.
Verbindliche aktuelle Details: SDD`progress.md`, `task-9-brief.md`,
`task-9-design-analysis.md` und `task-9-native-evidence.md`.
Die darunterstehenden Zwischenstände bleiben historische Nachweise.

Der bestehende Tennis-Tagesfehler ist inzwischen konkret aus dem Systemjournal
bestätigt (nur feste Statusfelder gelesen): ATP `retained_fresh`, WTA
`failed`/`HTTPError`, Neuaufbau rc1 nach17s; anschließender Tages-Scan nach900s
abgebrochen. Weder Providerursache noch erfolgreicher neuer Tageslauf sind
damit belegt. Kein Reset/Restart oder geändertes Job-Zeitlimit durchgeführt.

## Historischer Zwischenstand — Task8-Fix committed, Serverabnahme offen

NEUESTE ABNAHME:07d975f besteht den aktuellen Serverbestand weiterhin NICHT:
300.046CPU/300.135wall Sekunden,486572KiBRSS,kein vollständiger Report.
Eingabe unverändert. Scoped-Nachprüfung hat alle drei Referenzfindings bestätigt
geschlossen; das ersetzt den fehlgeschlagenen Ressourcentest nicht.07d975f
ist auf Reparaturbranch gepusht; Main/VPS/Updater unverändert. Vollsuite und
finales Gesamt-Review noch nicht gestartet. Begrenzte Phasendiagnose läuft.

Reparaturcode `07d975fb54a62ecb976c8040823e16fe45d9f16f`. Unabhängiges Review
fand zuvor eine echte versteckte Referenz außerhalb der Cache-Abrechnung;
Fixrunde1 behebt sie samt verwandten Schlüssel-/Publikationsreferenzen.
118gezielte Tests auf dem finalen Fix sind bestanden. Frische unabhängige
Nachprüfung läuft; noch kein neuer vollständiger oder nativer Abnahmelauf.
Exaktes07d975f-Archiv nur in die freigegebene isolierte VPS-QA übertragen.
Main/VPS bleiben2dd1116, Reparatur-Upstream06db3be. Keine erneute Freigabe
für denselben Commit-/Push-/Deploymentumfang nötig; tatsächliche bestandene
Abnahme bleibt Voraussetzung. Task7-CPU-Fehler ist bis dahin nicht aufgehoben.
Alle Details im aktuellen SDD-progress.md und task-8-report.md/-review.md/
-native-evidence.md. Frühere Zwischenstände darunter bleiben historisch.

## Aktueller Zwischenstand — 11. September 2026: geprüft, aber noch kein Deployment

Reparaturbranch `codex/context-capacity-recovery-20260910`, Produktcode `17cfbbc`.
Task5 D2-Binding korrigiert und echte Linux-Warnung-als-Fehler-Prüfung bestanden.
Task6/7 Tennis-Prüfkostenkorrekturen sind separat unabhängig geprüft, ohne neue
Code-Findings. Vollsuite auf8992386:7020bestanden/30Skips/97Untertests; Task7
auf17cfbbc:887gezielte Tests bestanden/12Plattform-Skips und202finale
Witness-/Äquivalenztests. Keine neue komplette17cfbbc-Vollsuite behaupten.

Echter Releaseblocker bleibt: aktuelle253333504Byte-Kontextkopie mit99521Belegen
und26Analysen scheitert auch bei17cfbbc nach300.063CPU/300.141wall Sekunden,
kein vollständiger Report. Eingabe unverändert. Ältere13-Analyse-G3-Kopie
bestand899 in283.876wall Sekunden, ersetzt aber nicht den aktuellen Bestand.
Backup aller88Datenbanken samt tatsächlichem Restore/HMAC ist geprüft.

GitHub-Reparaturbranch wurde bis06db3be normal gepusht, einschließlich
Task8-Plan/Brief und Design. Main/VPS bleiben2dd1116, Updater74b1c4b1; kein Main-Push,
Updateraustausch oder Appdeployment. App/Caddy und7Timer aktiv, Healthchecksok;
bekannter betboy-tennis.service-Fehler bleibt sichtbar. Keine Daten/Limits,
Modelle, Schlüssel/Marker oder geschützten Helper geändert.

Task8 wird jetzt von `/root/tennis_check_task8` abBASE06db3be umgesetzt:
Eine intern vollständig erzeugte und unabhängig geprüfte Historybasis liefert
den vollständigen spielbezogenen Originalnachweis, ohne für jedes Original
die gesamte History erneut zu materialisieren. Jede Snapshot-Berechnung erhält
weiterhin ihre vollständige frische History. Die exakte17cfbbc-Diagnose misst
41.658CPU Sekunden allein für die26Original-Historyrekonstruktionen; das ist
kein Nachweis, dass Task8 die Ressourcengrenze bereits besteht. Vollständige
Herleitung, unveränderte Rechen-/Prüfgrenzen und unabhängige/native Abnahme
bleiben verbindlich. Keine Originaldaten werden entfernt. Nachweise liegen in
`.superpowers/sdd/2026-09-10-context-capacity-recovery/progress.md`,
`task-6-native-evidence.md`, `task-7-report.md`, `task-7-review.md` und
`task-7-native-evidence.md` und `task-8-design-analysis.md`/`task-8-brief.md`.
Bestehende Worktrees/WIP/A0/P4b3/Cricket bleiben
unberührt. Dieselbe erteilte Commit-/Push-/Deploymentfreigabe nicht erneut abfragen.

## Fortsetzung freigegeben — 11. September 2026, 16:42 CEST

Die neu angefragte Freigabe liegt jetzt vor: Tennis- und D2-Prüfroutinen reparieren, danach committen, pushen und kontrolliert auf dem VPS deployen. Keine erneute Freigabefrage für denselben Umfang. Rechenergebnisse, Daten/Historien und Prüf-/Ressourcengrenzen bleiben unverändert. Der darunter dokumentierte Wachstumstest bleibt ein echter Releaseblocker, bis der neue Stand ihn besteht.

Reparaturworktree unverändert übernommen auf `7cf1e94`; keine neuen Produktiv-/VPS-Änderungen zum Start. Plan/SDD führen Task5 (D2-SQL-Kompatibilität) und anschließend die gezielte Tennis-Prüfkostenreparatur. Bestehende Worktrees und ungetrackte Nachweise bleiben erhalten. Main/VPS werden erst nach bestandener frischer Abnahme über den bereits freigegebenen Updater-Reparatur- und normalen Deploymentpfad aktualisiert.

## Aktueller Abschluss — 11. September 2026, 00:25 CEST: NICHT deployen

Task4 gemeinsame Historybasis umgesetzt/geprüft: Produkt52189a6,
Berichts-HEADfc7f0c7, unabhängiges Scoped-Review ohne neue Code-Findings.
Finale ganze Windows-Suite6926bestanden/30übersprungen/97Untertests,
1631.90s; QA-Worktreefc7unverändert. XML9ee9e3a3...fffde44.
Finale Linux-Tests199bestanden/10übersprungen, ABER14196SQLitewarnungen.
Ursache separat bestätigt: alteD2-Routinecontext_models/dataset.py:169-174,
?1-Binding mit Tupel; unterWarnung-als-Fehler reproduziert. Nicht unterdrücken.

Echter aktueller Datenstand bestanden:285.297CPU/285.388wall Sekunden,
48307Belege/10Snapshots,Eingabe unverändert. Größerer korrekter G1Testbestand
mit95406Belegen/11Snapshots/6Cutoffs scheitert jedoch nach300.112CPU/
300.233wall Sekunden,keinReport,472488KiBRSS. DamitweiterRELEASEHOLD.
G1versiegelt212172800B unter`/var/lib/betboy-task4-growth-mxqhafsc/generation-1/context.db`,
SHA01186c29cb6e31aef5815ae3f937d81401b9e72ddaaa30d934864bcf78daa966.
Alle Originaldaten erhalten. G2/G3 nicht ausgeführt/nicht belegt.

Neue weitergehende Freigabe nötig: verbleibende wiederholte Validierung in
der eigentlichen Tennis-Featureanbindung und D2SQL-Kompatibilität bearbeiten.
Diese Owner sind im bestätigtenTask4ausdrücklich eingefroren; nicht still
ändern und keinesfalls Daten/Prüfungen/Limits reduzieren. AktuelleModelle
sind dadurch nicht empirisch freigegeben; fünfSport-Kontextarbeit bleibtoffen.

KeinMain-Push/Updateraustausch/Appdeployment. Frisch22:23UTC bestätigt:
VPS/Main2dd1116,alterUpdater74b1c4b1,App/Caddy/7Timeraktiv,Healthintern/externok;
bekannterTennis-Dienstfehler bleibt. Alle Prüfprozesse dieserRunde beendet.
Berichte/SHAs/Befehle in`.superpowers/sdd/2026-09-10-context-capacity-recovery/`:
`task-4-native-evidence.md`,`task-4-review.md`,`task-4-report.md`,`progress.md`.
Ursprüngliche Worktrees/WIP/Outputs/A0/P4b3/Cricket/Stagehelper1441158,
alle alten Historien/Keys/Marker unverändert. Zwölf Ordnerrechte NICHT erneutändern.

## Fortsetzung — 11. September 2026: gemeinsame Historybasis in Abschlussprüfung

Die zuletzt angefragte Architekturfreigabe liegt ausdrücklich vor. Task4 ist
lokal umgesetzt: Code52189a6, Bericht-HEADfc7f0c7 auf dem bestehenden separaten
Reparaturbranch. Eine vollständig validierte kanonische Basis pro Tour wird
geteilt; alle Originale, historischen Zeitstände und Snapshot-Berechnungen
werden weiterhin einzeln geprüft. Keine Modell-/Quellprüfer-/Helperänderung.
Finale gezielte Tests200bestanden/9Windows-Skips; unabhängiges Scoped-Review
ohne Produktcode-Findings. Das ist keine vollständige Releasefreigabe.

Der erste exakte7b6-Linuxlauf scheiterte weiter amCPU300-Limit. Der Trace zeigt
jetzt nur einen statt wiederholterHistoryaufbauten, aber zusätzlich13–14CPU
Sekunden pro einzelner Snapshot-Featureberechnung. Finale native Messung bei
fc7 bestanden:285.297CPU/285.388wall Sekunden,321584KiBRSS,alle10Snapshots/
48307Belege geprüft,Eingabe unverändert. Nur14.6s Reserve. Ganze Windows-Suite
und finale Linux-Regressionsrunde laufen noch; Wachstum mit mehrBelegen UND
mehrPrognoseprüfungen ist offen. Nicht alte Tests als neuen Gesamterfolg zählen.

Neues vollständiges88DB-Backup/isolierterRestore/HMAC erfolgreich34.74s unter
`/var/lib/betboy-live-backup-pknwmr9p`; Contextkopie unverändertd304c164...169b9.
Finaler versiegelter QA-Code:`/var/lib/betboy-capacity-code-b38toqe5/source`,
Archiv1574c963...dde70f. App/VPS/Main weiterhin2dd1116, alter Updater74b1c4b1;
noch KEIN neuer Main-Push/Updateraustausch/Deployment. Keine erneuten chmods.
Aktuelle Belege:`task-4-report.md`,`task-4-review.md`,`task-4-native-evidence.md`
und`progress.md` in`.superpowers/sdd/2026-09-10-context-capacity-recovery/`.
Die eigentliche fünf-Sport-Verletzungs-/Belastungsfreigabe bleibt getrennt und
offen. Cricket sowie alle übernommenen WIP/Daten/Schlüssel/Marker bleiben erhalten.

## Fortsetzung — 10. September 2026, 23:05 CEST: Release weiterhin HOLD

Die zusätzlich freigegebenen zwölf Ordner wurden erfolgreich0775→0755 gesetzt;
Eigentümer/Gruppe/Inodes/Inhalte blieben erhalten. Metadatenjournal liegt
root-privat unter `/var/lib/betboy-directory-mode-repair-fi_69l74/metadata.json`.
Realer App-Schreibzugriff erhalten; Backup-Benutzer hat dort keinen
Schreibzugriff. Frisches vollständiges88DB-Backup samt isoliertem Restore/HMAC
bestanden: `/var/lib/betboy-live-backup-j0co13x8`,42.60s. Nicht erneut chmoden.

Neuer echter Blocker: exakter Leserb39789d scheitert auf aktueller114,929,664B
Kontextkopie bei300.067CPU/300.163wall Sekunden,child-9,keinReport. Eingabe
unverändert,keineCompanions,RSS362,972KiB. DeshalbKEIN Main-Push/Updateraustausch/
App-Deployment. Main/VPS weiter2dd1116, installierter Updaterweiter74b1c4b1.

Ursache eingegrenzt: nur810neueReceipts, aber4→10Tennisoriginale/Snapshots und
2→5historischeCutoffs. JeCutoff wird~28.4MBHistorykopie gespeichert; reale
Cold-Neuprüfung kostet62–68CPU Sekunden. Der alte388MBWachstumstest hatte die
Anzahl der Prognoseprüfungen nicht erhöht. Nicht Grenzen erhöhen oder Daten
löschen. Architekturvorschlag: gemeinsame vollständig validierte immutable
Historybasis mit historischenViews, unveränderte Einzel-/Featureprüfungen;
Freigabe dafür angefragt, noch keine Umsetzung. Frische exakte b397Vollsuite
abgeschlossen:6897bestanden,30übersprungen,97Untertests,1704.03s,keineFehler.
QA-Tracked-Diff leer; XML1596c193. Der reale CPU-Abbruch bleibt trotzdemHOLD.
Der Trace belegt3fertigeColdaufbauten/4Evictions/4.Coldstart beim8.Original;
keineSnapshotfeatureprüfung wurde erreicht. Alle QA-Prozesse dieser Runde
sind abgeschlossen. Server-/Remotecheck21:01UTC unverändert2dd1116,Healthok,
App/Caddy/siebenTimer aktiv; bekannter Tennis-Dienstfehler weiteroffen.

Aktuelle Belege in `.superpowers/sdd/2026-09-10-context-capacity-recovery/`:
`task-3-live-rollout-20260910.md`, `task-3-final-rollout-review-20260910.md`,
`task-1-fresh-profile-diagnosis-20260910.md` und `progress.md`.
Original-WIP/A0/P4b3/geschützterStagehelper1441158/Cricket unverändert. Keine
Behauptung, Verletzungs-/Müdigkeitsmodelle seien dadurch insgesamt erledigt.

## Kapazitätsreparatur — 10. September 2026, 21:45 CEST

Aktiver separater Worktree:`.worktrees/context-capacity-recovery-20260910`,
Branch`codex/context-capacity-recovery-20260910`, Codecommit`4205db82`.
Die ausdrückliche Freigabe zum einmaligen Updater-Austausch und zur Übertragung
versionierter QA-Archive liegt vor. Noch KEIN Austausch/Deployment ausgeführt:
Produktions-App weiter`2dd1116`, installierter Updater weiter`74b1c4b1...`.

Finaler Installer unabhängig nachgeprüft;451native Linux-Tests bestanden.
Echte isolierte Austausch-/Wiederanlauf-/Rechte-/Locktests sowie unveränderte
CPU300/Wall600+10-/Speicher-/Ausgabelimits bestanden. Die komplette finale
Produktionsprüfung läuft read-only gegen echte Benutzer, historischen
Migrationsmarker und leere Konfiguration erfolgreich. Diese beiden legitimen
Serverzustände werden jetzt korrekt behandelt, nicht auf dem Server umgeschrieben.

NOCH OFFENE ZUSÄTZLICHE FREIGABE: exakt zwölf dokumentierte Serverordner von
0775 auf0755 setzen. App-Eigentümer/Gruppe/Inhalte bleiben gleich; ein eng
geprüftes Verfahren mit Metadatenbackup/Rollback ist vorbereitet. Ohne diese
Freigabe keinen chmod ausführen. Der echte vollständige Backup-Producer lehnt
die bisherigen gruppenschreibbaren Ordner korrekt ab. Danach erforderlich:
frisches komplettes Backup/Restore/HMAC, exakt gemessener neuer D4-Lauf und
kontrollierter Updater-Austausch; normale App-Veröffentlichung erst separat.

Alle Details, Native-SHAs und erhaltenen Fehlerreproduktionen stehen in
`.superpowers/sdd/2026-09-10-context-capacity-recovery/` (`progress.md`,
`directory-mode-preflight-20260910.md`, `task-3-native-evidence-20260910.md`).
Die breite e2-Zwischenstandssuite endete mit 4 fehlgeschlagenen alten
Serverjob-Testverträgen, 6877 bestanden / 30 übersprungen / 97 Untertests. Testport
und zusätzlicher Fehlerabbruch-Gegentest sind unabhängig angenommen. Ein
alter Linux-Test konnte einen Inode wiederverwenden; der enge Fixture-Fix
erhält Comparator/Produktivcode und dokumentiert die Erkennungsgrenze.
Finaler Testfreeze `e90320c`: 541 Linux-Tests ohne Skips bestanden. Vollständige
saubere Windows-LF-Suite bei e74 mit identischem Produktivcode abgeschlossen:
6897 bestanden, 30 übersprungen, 97 Untertests bestanden, 1607.26s. Anschließend
bei e903 die einzige geänderte Testdatei frisch nachgeprüft: 83 bestanden,
7 Windows-Skips, 14.28s. Folgeänderungen betreffen nur Tests/Berichte. Diese
zwei Läufe nicht als einen neuen Vollsuite-Lauf bei e903 ausgeben.
Frischer Servercheck: weiterhin `2dd1116` / alter Updater; App, Caddy und sieben
Timer aktiv/aktiviert, Health intern und öffentlich auch vom PC HTTP200/ok.
Der bekannte fehlgeschlagene Tennis-Dienstlauf bleibt ausdrücklich offen.
Noch keine Produktiv- oder Gesamtmodellfreigabe behaupten.
Reale72-Ledger-Markerfixture
bleibt ausschließlich ignored, niemals committen/mitarchivieren. Geschützter
Stagehelper, alte WIP/Outputs und getrennte A0/P4b3-Stände bleiben erhalten.
Cricket unverändert; empirisch qualifizierte Verletzungs-/Belastungseffekte und
die übrigen offenen Modell-/Quelldatenarbeiten sind dadurch nicht abgeschlossen.

## Live-Release und neuer Größenbefund — 10. September 2026, 12:25 CEST

Die geprüfte Brücke655e7a6 und danach2dd1116 wurden tatsächlich in dieser
Reihenfolge über den installierten betboy-update veröffentlicht. Lokal, GitHub
main und VPS sind2dd1116; App/Healthchecks und sieben Timer laufen. Echte
Produktionskarten und Desktop-/Mobile-Geometrie geprüft. Timer deployen nicht.
Der neue SDD-Bericht task-20-live-release-and-storage-20260910.md enthält die
exakten Hashes, A/B-Backups, Browsergrenzen und unveränderten Ausgangsbelege.

ATP wurde unabhängig neu gebaut; WTA-Frischabruf scheitert weiter. Der geprüfte
vorhandene WTA-Cache wurde ausdrücklich als alter Stand26.07.2026 veröffentlicht,
ohne ATP zu verändern. Der ursprüngliche Tennis-Dienstlauf war partial/exit1;
dies wurde nicht kaschiert. Frisches normales Backup:88Datenbanken verifiziert.

NEUER OFFENER UPDATEBLOCKER: echte Kontextdatenbank100671488B mit47227
Beobachtungen, aber D4-Prüfer und installierter Updater begrenzen auf64MiB.
Weiteren Deploy bis sicherer Reparatur-/Migrationsklärung nicht auslösen.
Keine Daten löschen, Grenzen umgehen oder installierten Root-Code ersetzen.
Lesende Reviews bestätigen: der installierte Updater blockiert seine eigene
Reparatur; es braucht eine neue ausdrückliche Freigabe für einen eng geprüften
Roottool-Übergang. Tennis erfasst auch vollständige alte Abrechnungsantworten:
47098Tennisbelege plus129parallele Fußballbelege. Kein generischer B1-Dedupfehler.
P4b3(a)-Round1 ist im unabhängigen Review HOLD (widersprüchliche Terminrevision
kann Absage aufheben); Fußball-A0 ist separat angenommen. Beide unintegriert.
Empirisch qualifizierte Verletzungs-/Belastungseffekte bleiben offen; Cricket
unverändert. Geschützten Stagehelper und übernommene Outputs weiter bewahren.

## Historischer main-Nachtrag 13. September 2026 — Daily3-Dokumentation

`3 a day keeps the job away`: CHF 50 eigenes Tagesbudget, höchstens drei
Einzelwetten auf unterschiedliche Events, abgerechnete Gewinne wiederverwendbar,
kein Nachschuss, maximal CHF 50 Nettoverlust gegenüber Tagesstart. Der Nutzer
hat jetzt auch die Übernachtregel angenommen: kein neues Tagesbudget, solange
der vorherige Lauf noch offene Wetten, Reservierungen oder Korrekturen enthält.
Diese Regeln nicht erneut abfragen. Kein garantierter Tagesgewinn und keine
automatische Wettplatzierung; Daily3 ist noch nicht implementiert.

Spezifikation: `docs/superpowers/specs/2026-09-13-daily3-design.md`.
Rechenprüfung: `docs/audits/2026-09-13-daily3-spec-check.md`.
Frische VPS-Vorprüfung: `docs/audits/2026-09-13-daily3-vps-preflight.md`.
Diese Übernahme nach main enthält ausschließlich die drei Daily3-Dokumente
und diesen Übergabenachtrag. Kein Code-Merge aus dem Reparaturbranch
`codex/context-capacity-recovery-20260910` (Dokumentationscheckpoint `0296b09`).
Ältere dortige C/B-Arbeit, QA-Verzeichnisse und Freigabegrenzen bleiben erhalten.

VPS am 13.09.2026 ab 18:04:48 UTC frisch geprüft: main `2dd1116`, App/Caddy
aktiv und beide Healthchecks `ok`, sieben Timer geplant. Tennis-/Wettfinder-
Dienste bleiben `failed`. Der installierte Updater hat eine 64-MiB-Grenze;
die Kontextdatenbank ist bereits 499855360 Byte (rund 477 MiB) groß. Er stoppt
die App vor dieser Prüfung. Deshalb kein Updateversuch, kein direkter Git-Pull
als Umgehung und keine Serveränderung. Der beauftragte VPS-Pull bleibt offen,
bis die separat laufende Updater-Reparatur fertig geprüft ist. Der aktuelle
Dokumentationscommit auf main ist kein funktionales Daily3-Deployment.
## Releaseprüfung am 10. September 2026 — 11:49 CEST

Vollsuite im frischen LF-Checkout286601b abgeschlossen:6552bestanden,
20Windows-Skips,97Untertests,1279.19s. XML9dd05fc2, unveränderte Quellhashes
und leeres QA-Tracked-Diff belegt. Root887cb47 unterscheidet sich nur in zwei
Prüfberichten. Unabhängiger abschließender Deployment-Deltareview ohne neuen
technischen Blocker; echter UI-Preis-/Mobile-Nachweis liegt separat vor.

GitHub main und VPS frisch2ba3931, noch keine Brücke installiert. Nächster
Schritt: exaktA655e7a6 auf main und über den alten installierten Updater
deployen; dessen neue root-eigene Bytes prüfen; erst dann den dokumentierten
finalen B-Stand auf main veröffentlichen und über denselben installierten
Einstieg deployen. Keine Timer-Pull-Funktion, kein Root-Bootstrap-Ersatz.

P4b3(a) separat2aecc10 eingefroren und im unabhängigen Review; nicht Bestandteil
dieses Releases. Fußball-P5b-A0 ist ein genehmigter optionaler Final-Original-
Callback, als alleinige Implementierungsarbeit isoliert begonnen. Dauerhafte
B3-Verknüpfung und empirisch qualifizierte Verletzungs-/Belastungseffekte
bleiben offen. Cricket unverändert. Bestehende REDs, Outputs und geschützter
Stagehelper werden nicht überschrieben oder als erledigt umgedeutet.

## UI-Nachprüfung am 10. September 2026 — etwa 11:26 CEST

Root74d714a enthält den angenommenen UI-Fixacf6b8e: echtes Startguthaben100.00,
leere/ungültige Eingaben nicht ersetzt, jede Entscheidung bindet ihre konkreten
Eingaben.195Fokustests und18Originalgegenproben grün. Unabhängiger Nachreview
ohne neue wichtige Codefehler; ungenaue ältere Testzuordnung korrigiert.
Der echte neue Browserlauf beweist jetzt auch zwei gleichzeitig gespeicherte
Quotenprüfungen: Änderungen an A lassen B unverändert. Modelltexte/Sortierung
bleiben gleich. Beide Ansichten passen1440–320px; mobiles Prüffenster lesbar.
Quotenwechsel in RisikoBet ändert nur die separate Preisanzeige.

Noch keine neue Vollsuite für diesen integrierten Stand, kein Main-/VPS-Release.
P4b3(a) separat wieder in Arbeit; Fußball-P5b und tatsächliche qualifizierte
Verletzungs-/Belastungsanbindungen bleiben offen. Cricket weiterhin ausgenommen.
Frühere Outputs/REDs/geschützter Stagehelper unverändert. Details im neuen
SDD-Bericht task-19-manual-price-browser-round1-20260910.md.

## Accountfortsetzung am 10. September 2026 — Vormittag

Spezifikation, Plan, Agenten-/Worktree- und Releasefreigaben übernommen, nicht
erneut angefordert. Root/Remote-Feature898652b, GitHub main und tatsächlicher
VPS frisch2ba3931. App/Caddy und Healthchecks aktiv; sieben Timer geplant,
heutiger Tennis-Lauf07:17–07:18 CEST wieder Exit1. Noch kein neues Deployment.

UI-C0c0a83f1: echter Quotenwechsel1.12→4.00 invalidiert die alte Bewertung;
Karten/Sortierung unverändert. Zwei unabhängige Restbefunde werden eng korrigiert:
Guthaben100 ist im Browser nicht sichtbar, ungültige explizite Prüfungen nennen
ihre geprüften Eingaben nicht. Ein textbasiertes Guthabenfeld mit erhaltenen
Zahlen-/Min1-/Preisregeln ist dafür genehmigt; keine Finanzregeländerung.
Finder/Risk bei1440/1024/761/760/390/320 ohne horizontalen Dokumentüberlauf;
sechs synthetische Sportfilter funktionieren. Das ist keine echte Sportdaten-
oder Wirkungsvalidierung. Root-Browserbericht/Originalreview im SDD gesichert.

P4b3(a) ist isolierter uncommitteter WIP: vier Original-Visibility-/Clockfälle
grün, zwei dauerhafte B3-Referenzfälle noch rot. Während UI-Fix kurz pausiert.
Fußball-P5b-Preflight abgeschlossen: tatsächlicher Final-Capture/B3-Anschluss
fehlt; gespeicherte CANC/1H-Korrekturen fehlen, obwohl Legacy-Live-Reconcile
wirkt. Kalibrierte Legacywerte nicht als Raw-B5 ausgeben. Berichtcafcac20 bleibt
byte-identisch erhalten. Sourcehashes, geschützter Helper1441158 und fremde
Outputs unangetastet. Fortsetzen mit UI-Nachreview, neuem eingefrorenem
Gesamtteststand und geprüftem A→B-Deployment; übrige Modellpakete bleiben offen.

## Fortsetzung am 10. September 2026 — nach dem vollständigen B-Test

Root-Code `f058517011c9841a0650c767c301822b2d29a3c5`: Fußball-Original samt
Metadatenkorrektur, Basketball/Hockey-Nativebinding samt F1 und einmalige
E-Sport-Originalaufnahme unabhängig angenommen und integriert. Neuer Root-Stand
noch nicht als Main-/VPS-Release behandeln; letzter bestätigter Main/VPS `2ba3931`.

- Vollsuite des eingefrorenen Teilrelease-Kandidaten `f2f7611`: **6255 bestanden,
  20 Windows-Skips, 97 Untertests, 1354,13s**. Deckt spätere P4b2/P6a/UI-Fixes
  nicht ab. XML3217c046 und eigener Bericht im SDD-Ledger.
- P5a Root-Nachreview105/0, inklusive aller vier unveränderten Fehlerzeugen.
  P4b2-F1 unabhängig541 Fokus +71 Gegenproben grün, keine neuen Findings.
  P6a unabhängig382 Fokus/26 Untertests +2 Originalzeugen +32 Gegenproben grün.
- E-Sport berechnet im echten Logger/Scan Elo nur einmal. Alte SQL-Werte,
  First-observation und Settlement bleiben gleich. Alte C4-Karten bleiben lesbar;
  voller alter numerischer Replay unter neuem Gesamtdateihash bleibt ausdrücklich
  eine separate Kompatibilitätsgrenze, kein umgeschriebenes Gütesiegel.
- A655e7a6 ist ausschließlich der geprüfte Updater-Brückencommit. Bf2f7611 enthält
  dessen Ancestry. Unabhängiges technisches A→B-Review277/0 bestanden, kein echter
  installierter Übergang. A erst über alten Updater vollständig installieren und
  dessen neue Bytes verifizieren, **danach erst** B auf Main veröffentlichen.
- Echter lokaler Browser: gegensätzliche Porto-Vorschläge werden nicht zusammen
  angezeigt; Analysen sind offen, Filter-/Preiswechsel ändern die Karten nicht.
  Neuer echter Fehler: bearbeitete Quote zeigt bis zum Submit noch alte Meldung.
  Separater UI-Fix in `kontext-manual-price-ui-20260910`; A/Main/VPS bleiben bis
  dessen Prüfung zurückgehalten. Synthetische QA-Daten nur im neuen B-Worktree.
- Reale Fußball- und Basketball/Hockey-Workeranschlüsse werden anhand konkreter
  fehlender Seams geprüft; insbesondere keine alten C2/C3-Originalversionen über
  neue P4a-Daten legen. Keine zusätzliche Empirie- oder Verletzungswirkung behaupten.

Weiterhin gültig: Freigaben übernommen, Cricket ausgeschlossen, kein pauschales
Markt-/Quotenverbot, keine Echtgeld-/Altprognosenänderung. Geschützter Stagehelper
SHA1441158 unverändert; sein geerbter Phantomstatus bleibt unangetastet.
Alle vorherigen Fehlerberichte und neuen Reviews wurden bytegleich erhalten.
Timer rechnen und deployen keinen Code. Neue Endfreigabe/Gesamtsuite/Browser,
Main-Push, VPS-Installation, echter Lauf und Quellen-/Wirkungsnachweis getrennt halten.

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
