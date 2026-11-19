# Übergabe Claude → Codex, vollständig, Stand 19.11.2026

Owner-Auftrag vom 19.11.2026: „detaillierte Übergabe an Codex machen“. Dieses Dokument steht für sich und ersetzt
die vollständige Übergabe vom 13.11. als Einstieg. Die älteren Dokumente (`2026-11-11-claude-uebergabe-codex.md`,
`2026-11-13-claude-uebergabe-codex.md`, `2026-11-13-claude-uebergabe-codex-komplett.md`) bleiben als Verlauf stehen.
Wo sie abweichen, gilt dieses Dokument. Bei Widersprüchen gilt wie immer zuerst der Code, dann `AGENTS.md`.

Stand: Donnerstag, 19.11.2026, 09:00 CET. Einen Termin für die Übernahme hat der Owner nicht genannt.

Inhalt: 0 Kurzfassung · 1 Zuerst das · 2 Stand · 3 Was die App zeigt · 4 Verlauf 13. bis 19.11. · 5 Lesungen vom
19.11. · 6 Arbeitsweise · 7 Release-Verfahren · 8 Server-Zugriff · 9 Messungen und Termine · 10 Offene Aufgaben ·
11 Risiken und Lehren · 12 Regeln · 13 Owner · 14 Pfade · 15 Was nicht geprüft ist

## 0. Kurzfassung zum Einfügen

> Lies zuerst `AGENTS.md`, `STATUS.md` und `docs/handoffs/2026-11-19-claude-uebergabe-codex.md`.
>
> **Stand 19.11.2026, 09:00 CET:**
> - Produktion läuft auf `87f2434` (live seit 18.11.2026 13:06 CET, Release 20261118-1).
> - `origin/main` steht auf `8b7de0a` plus diesem Übergabe-PR. Nach `87f2434` kam nur Doku dazu.
> - Kein offener PR ausser diesem.
> - Alle Server-Dienste liefen am 19.11. mit Exit 0. Der letzte Alarm stammt vom 07.11.
> - Die Ratenlimit-Reparatur hat ihre erste Nacht bestanden: kein HTTP 429, die Suche für morgen fand alle 66 Ligen.
>
> **Zuerst:** die Prüfliste in Abschnitt 1. Die Nacht auf Freitag, 20.11., sucht zum ersten Mal einen vollen
> Liga-Samstag als „morgen“; danach folgt das erste volle Liga-Wochenende mit Doppel-Scan (21./22.11.).
>
> **Termine:** 30.11. Fallenfilter, Formstärke/Hybrid und Liste ab 70 %; Mitte Dezember Länderspiel-Modell
> Kandidat 4; Ende Dezember Doublebet-Bandprüfung (Abschnitt 9).
>
> **Regeln:**
> - Jeder Merge und jedes Release braucht ein eigenes, ausdrückliches Owner-OK, das Release wörtlich „live stellen“.
> - Releases nur über den No-Backup-Fast-forward-Helfer (Abschnitt 7). Nie hinter `555797b` zurückrollen.
> - Fallenfilter bis zur Auswertung nur mit `--count-only`. Keine Trefferquoten ansehen.
> - Preisjagd gegen Buchmacher nicht messen, nicht bauen, nicht erneut vorschlagen (Owner 12.11.).
> - Der Owner will kurze, direkte Antworten in einfachem Deutsch, Kernaussage zuerst.

## 1. Zuerst das

Alles hier ist nur lesend. Die Helfer liegen in `C:\Projekt\BetBoy\output\uebergabe-20261119\` (nicht in Git, alle
mit LF-Zeilenenden):

| Datei | Zweck |
|---|---|
| `stand.sh` | Live-Commit, Timer, fehlgeschlagene Einheiten, letzter Lauf je Einheit |
| `stand_tag.sh`, `stand_heute.py`, `api_budget_stand.py` | Tagesdokument, Team-Quoten, Doublebet heute und morgen, API-Verbrauch je Tag, Alarme, Platte |
| `stufen.sh` (neu) | Stufenzeiten des Nachtlaufs aus dem Journal, gelungene und fehlgeschlagene Läufe des Tages |
| `nacht_lesen.py` (neu) | Suche für morgen, Warteliste der Team-Quoten, HTTP 429, Abrufe je Minute, Preisauffrischungen |
| `ergebnisse.py` (neu) | Tipp-Ergebnisse eines Tages: Hauptauswahl je Spiel, öffentliche Tipps, Doublebet, RisikoBet |
| `ausgabe-*.txt` | Ausgaben dieser Helfer vom 19.11. 08:55, zum Vergleich |

1. **Einstieg.** `git fetch origin`, eigenen Worktree anlegen (Abschnitt 6), `STATUS.md` lesen.
2. **Stand auf dem Server.** In der PowerShell:

   ```powershell
   $O = "C:\Projekt\BetBoy\output\uebergabe-20261119"
   scp -q "$O\stand.sh" "$O\stand_tag.sh" "$O\stand_heute.py" "$O\api_budget_stand.py" "$O\stufen.sh" "$O\nacht_lesen.py" "$O\ergebnisse.py" betboy-vps:/tmp/
   ssh betboy-vps "bash /tmp/stand.sh; bash /tmp/stand_tag.sh 2026-11-19"
   ```

   Erwartet wird:
   - `LIVE: 87f2434`.
   - Jede Kerneinheit mit `success` und Exit 0: app (aktiv), wettfinder, quotes, tennis, esports, football-shadow,
     redcard-history, redcard-settlement, backup-retention.
   - Unter `FAILED` genau die 8 alten Einmal-Einheiten vom September (Abschnitt 2). Jede weitere ist neu.
   - Alarme: 14 Zeilen, die letzte vom 07.11. (`2026-11-07T19:52:16+00:00`, football-shadow). Mehr Zeilen heisst
     neuer Alarm; dann die neuen Zeilen in `runtime_state/ops_alerts.jsonl` lesen.
   - Platte um 52 %.
3. **Die Nacht auf Freitag, 20.11. (Start 03:35).** Sie sucht zum ersten Mal einen vollen Liga-Samstag als „morgen“:

   ```powershell
   ssh betboy-vps "bash /tmp/stufen.sh 2026-11-20; sudo -n -u betboy nice -n 19 /opt/betboy/venv/bin/python -I /tmp/nacht_lesen.py 2026-11-19T12:00:00+00:00"
   ```

   Erwartet wird:
   - Exit 0, erstes Schreiben (`forecast_publication`) gegen 03:41.
   - `football_next_day`: `status = completed`, 66 Ligen, alle Fehlerzähler 0.
   - HTTP 429 gleich 0; Eishockey höchstens 9 Abrufe in 60 Sekunden.
   - Ende vor 04:35. Die Einheit hat 60 Minuten (`TimeoutStartSec=60min`).

   Zum Vergleich: Am 19.11. dauerte die Suche für morgen 696 s (62 Spiele gefunden), der ganze Lauf 24,5 Minuten.
   Die Fussball-Suche eines vollen Samstags und Sonntags dauerte am 7. und 8.11. 894 s und 1143 s. Daraus geschätzt
   sind rund 40 Minuten für den Lauf vom 20.11.; gemessen ist das nicht.

   Reisst der Lauf die Grenze, bleibt die Datei von heute stehen (`sources.football.next_day.status = pending`), und
   der Alarm schreibt eine Zeile in `ops_alerts.jsonl`. Dann dem Owner melden. Die „Zeitprüfung vor der Suche für
   morgen“ aus dem Audit ist nicht gebaut (Abschnitt 10).
4. **Wochenende 21./22.11.** Dieselbe Lesung für beide Nächte. Dazu der Verbrauch je Tag in der Ausgabe von
   `stand_tag.sh`: `api-football` hat 7500 pro Tag (der volle Samstag vom 07.11., noch ohne „Folgetag immer“,
   brauchte 3575), `api-sports-ice_hockey` hat 100 pro Tag (am 14.11. waren 82 verbraucht). Gesperrte Abrufe stehen
   mit `decision = BLOCKED` in `api_budget_events`.
5. **Wartende Eishockey-Spiele.** `nacht_lesen.py` druckt `minute_deferred`. Am 19.11. um 06:15 warteten sieben
   Spiele ohne Quote (Abschnitt 5). Prüfen, ob die Liste über den Tag leer wird und ob jedes NHL-Spiel vor dem
   Anstoss eine Quote hat.
6. **Fallenfilter zählen, nur Anzahl:**

   ```powershell
   ssh betboy-vps "sudo -n -u betboy bash -c 'cd /opt/betboy/app && /opt/betboy/venv/bin/python -I scripts/trap_filter_measurement.py --count-only'"
   ```

   Stand 19.11. 08:57: 430 abgerechnete Tipps, 46 Fallen, 152 übrige mit Quote, 232 ohne Quote.
7. **Live-Seite ansehen:** `https://vps-a30a123f.vps.ovh.net/` (Streamlit braucht 10 bis 20 Sekunden). Der
   Wettfinder zeigt heute und morgen als Karten zu zweit nebeneinander, Doublebet zeigt heute und die Vorschau für
   morgen, 15K lädt. Zwischen Mitternacht und dem Ende des Nachtlaufs ist die Liste leer; das ist bekannt.
8. **Melden und nachziehen.** Dem Owner das Ergebnis in wenigen Sätzen melden. Am Ende der Sitzung den Abschnitt
   „Stand“ in `STATUS.md` ersetzen.

Fragt der Owner „wie waren die Ergebnisse?“, meint er die Tipp-Ergebnisse vom Vortag (so verstanden am 19.11., er
hat nicht widersprochen):
`ssh betboy-vps "sudo -n -u betboy nice -n 19 /opt/betboy/venv/bin/python -I /tmp/ergebnisse.py 2026-11-19"`.

## 2. Stand am 19.11.2026 um 09:00 CET

### Code und Server

| Bereich | Stand |
|---|---|
| Produktion (VPS `betboy-vps`, `/opt/betboy/app`) | `87f24343f3d3c3d926f5df0b4ad60cddc22d6191`, live seit 18.11.2026 13:06 CET, Release 20261118-1 |
| `origin/main` | `8b7de0ac3c205db252dd51827d47a3ab12304c56` (PR #142) plus dieser Übergabe-PR |
| Unterschied Produktion → `main` | nur Doku (`STATUS.md`, `AGENTS.md`, `docs/`). Kein App-Code |
| Offene PRs | keiner ausser diesem |
| Dienste 19.11. | alle `success`/Exit 0: tennis 00:12, esports 03:10, wettfinder 03:59, backup-retention 04:20, redcard-history 05:41, redcard-settlement 06:05, quotes 06:15, football-shadow 08:52; app aktiv seit dem Neustart vom 18.11. 13:06 |
| Alarme | 14 Einträge in `runtime_state/ops_alerts.jsonl`, der letzte vom 07.11. 20:52 CET; seither keiner |
| Fehlgeschlagene Einheiten | 8 alte Einmal-Einheiten vom 14. bis 19.09.2026: `betboy-release-afc8a10-20260918`, `-20260918b`, `betboy-release-context-c64218b-20260918`, `betboy-release-product-53f2e2c-20260919`, `betboy-storage-repair-20260919`, `codex-context-memory-repair-20260914`, `codex-tennis-cpu-check-20260915`, `codex-tennis-identity-check-20260915`. Keine Kerneinheit, Altlast |
| Platte | 38 GB, 20 GB belegt, 52 % |
| Backup-Timer | `disabled`/`inactive`, so vom Owner gewollt. Nur `backup-retention` läuft |
| Telegram-Alarm | Token und Chat-ID fehlen in `/etc/betboy/betboy.env` (Owner). Alarme landen nur im Journal und in `ops_alerts.jsonl` |
| Geplante Claude-Aufgaben | keine aktiv (eine alte Einmal-Aufgabe vom 01.11. ist ausgeschaltet) |

### Daten des Tages (19.11., 08:55)

| Bereich | Stand |
|---|---|
| Tagesdokument | Fussball 12 Zeilen heute und 256 morgen (41 Spiele am 20.11.); Basketball 12 Zeilen heute und 8 morgen, ohne Quote; Eishockey 24 Zeilen für die NHL-Nacht auf den 20.11. (12 Spiele); E-Sport 4 heute |
| Team-Quoten | 28 Quoten (16 NHL, 12 API-Hockey), keine Fehler, keine Identitätslücken; 7 Spiele warten in `minute_deferred` |
| Doublebet heute | keine Auswahl |
| Doublebet Vorschau morgen | zwei Auswahlen (ein NHL-Spiel mit Median-Quote 2,12 bei Modell 58 %, ein Fussballspiel mit 1,91 bei 72 %) |
| Fallenfilter (08:57, nur Anzahl) | 430 abgerechnete Tipps: 46 Fallen, 152 übrige mit Quote, 232 ohne Quote. Nötig sind 150 Fallen |

### API-Verbrauch (abgeschlossene Abrufe je Tag)

| Tag | api-football (7500) | davon HTTP 429 | Eishockey (100) | Basketball (100) | The Odds API (20/Tag) | OddsPapi (10/Tag) |
|---|---:|---:|---:|---:|---:|---:|
| Sa 14.11. | 1609 | 12 | 78 (+4 fehlgeschlagen), Rest 18 | 0 | 0 | 5 |
| So 15.11. | 768 | 6 | 55 (+3), Rest 42 | 4 | 5 | 5 |
| Mo 16.11. | 617 | 0 | 18, Rest 82 | 7 | 6 | 4 |
| Di 17.11. | 454 | 0 | 60 (+2), Rest 38 | 11 | 5 | 6 |
| Mi 18.11. | 411 | 40 | 54 (+4), Rest 42 | 9 | 6 | 5 |
| Do 19.11. bis 06:15 | 731 | 0 | 22 (+4), Rest 74 | 3 | 1 | 0 |

- „Rest“ ist der geschätzte Rest des Tages aus `api_budget_state`.
- Monatskontingente im November, Stand 19.11.: The Odds API 417 von 500 übrig, OddsPapi rund 175 von 250 übrig.
- HTTP 429 davor: 11.11. 12, 12.11. 14, 13.11. 25. Die Ursache ist seit 18.11. repariert (Abschnitt 4).
- Die 3 bis 4 fehlgeschlagenen Eishockey-Abrufe je Tag sind Abrufe `games` mit `ValueError` bei HTTP 200. Es gibt sie
  mindestens seit 12.11.; untersucht sind sie nicht.

### Checkouts

- **Hauptcheckout** `C:\Projekt\BetBoy\betboy-app`: steht auf `c5a6264 [main]`, trägt fremdes WIP und liegt hinter
  `origin/main`. Getrackte Dateien nicht anfassen. Nur die Kopien `STATUS.md` und `AGENTS.md` dort nach jedem Merge
  aus `origin/main` erneuern (Abschnitt 6).
- **Claude-Arbeitsworktree:** `.worktrees/claude-shadow-void-verschoben`. Codex nimmt einen eigenen.
- **Codex-Worktree** `.worktrees/audit-repairs-20261013`: 7 unveröffentlichte Commits und ungesicherte Änderungen;
  muss `main` einmergen (`docs/handoffs/2026-10-21-codex-auftrag.md`).
- **Übrige Worktrees:** 12 Einträge in `git worktree list`, 186 lokale und 152 Remote-Branches, davon 149 in
  `origin/main` gemergt. Aufräumen nur mit Owner-OK.
- **Lokaler Speicher:** Am 15.11. schrumpfte `C:\Projekt\BetBoy` nach zwei Owner-Aufträgen von 199 auf 20 GB
  (422 168 Test-Datenbanken, 68 638 pytest-Temp-Ordner, 70 saubere Worktrees). Logs, Berichte und Skripte blieben,
  weil die Doku viele als Beleg zitiert. Testläufe mit festem `--basetemp` hinterlassen je Lauf mehrere GB.
- **Auf dem Server unter `/tmp`:** rund 330 Einträge, darunter alte Leseskripte. Harmlos.
  **`/tmp/shadow_gap.sh` braucht das Release-Verfahren; nicht löschen.** Fehlt die Datei nach einem Neustart des
  Servers, liegt eine Kopie in `C:\Projekt\BetBoy\output\release-20261112-1\upload\`.

## 3. Was die App zeigt

| Seite | Verhalten |
|---|---|
| **Wettfinder** | Jedes Spiel ist eine offene Karte, zu zweit nebeneinander (auf dem Handy untereinander). Jeder Markt ist eine Zeile im RisikoBet-Stil mit Sport, Liga, Anstoss, Auswahl, Modell und Grundlage/Contra; der Kontext steht einmal je Spiel als kleine Zeile. Darunter: Tabelle „Multigoal & Sieg-Kombis“, Form als Textzeile je Team, geschlossene Schublade „Analyse anzeigen“. Der Regler „Mindest-Modellchance“ startet bei 70 %. Die Liste zeigt heute und morgen: Fussball, Eishockey, Basketball, E-Sport; Tennis und Cricket nur heute |
| **Doublebet** | Bis zu drei Wetten mit Median-Quote 1,80 bis 2,20, gewählt nach der höchsten Summe der Modellwahrscheinlichkeiten (Policy `doublebet-odds-around-2-most-probable-v16`), mit Eishockey und mit A-Länderspielen ohne Verletzungsdaten. Dazu „Morgen (Vorschau)“, nur Anzeige |
| **15K** | Höchstens fünf Spiele, je Spiel der wahrscheinlichste Markt mit Leg-Quote ab 1,25. „Morgen“ zeigt eine Vorschau ohne Ticketformular |
| **Tipps** | Öffentlich höchstens drei gleichzeitig. Sie rücken nach jedem Quotenlauf nach. Tennis-Siegertipps erst ab 60 % Modellchance |
| **Kleinstaaten** | In A-Länderspielen gegen genau einen Kleinstaat zeigt die App keine Unter-Tor-Tipps (seit 16.11.) |
| **Quoten** | Die App zeigt keine Buchmacherquoten. Im Hintergrund gilt nur die 1,20-Grenze (dreistufig, Median der Buchmacher) |
| **Ergebnisse** | Abrechnung im Nachtlauf und in jedem Quotenlauf, also alle 3 Stunden. Fussballspiele mit Anstoss vor 04:30 werden schon im Lauf davor als Evidenz gespeichert (seit 13.11.) |
| **Eishockey** | Ein NHL-Spiel des Folgetags gehört bis 06:00 Uhr zum laufenden Tag (seit 15.11.). Quoten für höchstens 8 Spiele je Lauf und höchstens 9 Abrufe je Minute (seit 18.11.). Basketball (EuroLeague) bekommt nie eine Quote, bewusst offen |

**Morgen-Zeilen** sind nur Anzeige: nie Tipp, 15K-Eintrag, Doublebet-Wahl, Shadow oder Archiv vor ihrem Spieltag.
Einzige Ausnahme sind die Nachtspiele vor 04:30 als Evidenz.

**Ablauf:** Der Worker (`wettfinder_automation.py`, Einheit `betboy-wettfinder`, 03:35) schreibt das Tagesdokument
`runtime_state/wettfinder_latest.json` seit 17.11. in drei Schritten: zuerst heute mit den Tipp-Belegen
(`forecast_publication`, `tip_receipts`), dann Fussball für morgen (`forecast_publication_next_day`), zuletzt der
Hintergrundschritt `football_appearances` (`forecast_publication_final`). Die App (`app.py`, Streamlit, `betboy-app`)
lädt das Dokument über den Lader. Der Quotenlauf (`betboy-quotes`, alle 3 Stunden) prüft Preise, lässt Tipps
nachrücken und rechnet ab. Mehr in `ARCHITECTURE.md`.

## 4. Verlauf vom 13. bis 19.11.2026

### Merges und Releases

Alle Releases liefen über den Helfer aus Abschnitt 7. Owner-Freigaben stehen in den Protokollen.

| Merge (CET) | PR | Commit | Inhalt | Live |
|---|---|---|---|---|
| 13.11. 10:30 | #123 | `5c8000f` | Fallenfilter: Einstiegsquote über die Auswahl | mit Release 20261113-1 |
| 13.11. 11:25 | #124 | `8a2baad` | Vollständige Übergabe vom 13.11. | – |
| 13.11. 11:30 | #106 | `dbf9388` | Plan Google Play | – |
| 13.11. 22:04 | #125 | `7efa8f5` | Nachtspiele vor 04:30 als Evidenz | Release 20261113-1, 22:12 |
| 14.11. 07:58 | #126 | `9fbf238` | Protokoll | – |
| 15.11. 14:34 | #127 | `d19e755` | NHL-Spiele des Folgetags bis 06:00 zum laufenden Tag | Release 20261115-1, 14:36 |
| 15.11. 14:49 | #128 | `4d21720` | Protokoll | – |
| 15.11. 21:59 | #129 | `7f35c23` | Wettfinder im RisikoBet-Stil | Release 20261115-2, 22:02 |
| 16.11. 00:32 | #130 | `2b572e0` | Kontext als kleine Zeile je Spiel | Release 20261116-1, 00:33 |
| 16.11. 07:03 | #131 | `b559abd` | Protokoll; Tennis-Test mit Zürcher Datum | – |
| 16.11. 09:08 | #133 | `fb38329` | Kleinstaaten-Sperre | Release 20261116-2, 09:15 |
| 16.11. 09:51 | #132 | `70969b3` | Kleinstaaten: Vorab-Hypothese und Ergebnis | – |
| 16.11. 09:51 | #134 | `7843a6c` | Protokoll Sperre, Reparaturkandidaten 1 bis 3, Plan bis März | – |
| 16.11. 13:53 | #135 | `c591afe` | Doublebet-Prüfungen | – |
| 17.11. 08:00 | #137 | `d321d74` | Nachtlauf „heute zuerst“ (Audit H5) | Release 20261117-1, 13:44 |
| 17.11. 14:55 | #138 | `1d0c186` | Protokoll | – |
| 17.11. 17:32 | #136 | `cca0c95` | Gesamtaudit vom 16.11. (nur Doku) | – |
| 17.11. 20:03 | #139 | `b85e2d9` | Wettfinder: Karte und Raster wie RisikoBet | Release 20261117-2, 21:17 |
| 17.11. 22:01 | #140 | `80c3824` | Protokoll | – |
| 18.11. 12:23 | #141 | `87f2434` | Ratenlimit der Nebensportarten | Release 20261118-1, 13:06 |
| 18.11. 13:20 | #142 | `8b7de0a` | Protokoll | – |

### Wo der Code dazu liegt

- **Nachtspiele (#125):** `wettfinder_automation.NIGHT_GAME_KICKOFF_BEFORE = (4, 30)`, `_night_game_rows`,
  `_record_night_game_evidence`. Fussballzeilen des Folgetags mit Anstoss vor 04:30 Zürcher Zeit werden im Lauf
  davor als Evidenz gespeichert, weil ihr eigener Spieltag-Lauf erst nach dem Anstoss speichert. Am 15.11. belegt:
  beide Nachtspiele haben Prognose und Ergebnis. Protokoll `docs/audits/2026-11-13-nachtspiele-abrechnung.md`.
- **NHL-Spätspiele (#127):** `team_sport_forecasts.NHL_NIGHT_UNTIL = (6, 0)`, `_nhl_horizon` in
  `automatic_team_sport_day`. Am 18.11. belegt: die beiden Spiele um 04:00 haben Prognose und Ergebnis. Protokoll
  `docs/audits/2026-11-15-nhl-spaetspiele.md`.
- **Wettfinder im RisikoBet-Stil (#129, #130, #139):** `wettfinder_surface.render_wettfinder_row_html`
  (`show_context` für die Kontextzeile), `app._with_wettfinder_risk_rows` (kopiert den RisikoBet-Abschnitt des
  Stylesheets), `app._render_wettfinder_game`, `app._render_wettfinder_game_details`, Container
  `wettfinder_game_grid`, `sports_form.render_goal_history_html`, `forecast_compact.compact_form_lines` und
  `compact_analysis_lines`, `ev_signal_sources.row_competition` (Liga aus `league_id`). Tests
  `tests/test_wettfinder_risikobet_rows.py`. Protokoll `docs/audits/2026-11-15-wettfinder-risikobet-stil.md`.
  Vergleichsbilder (RisikoBet neben Wettfinder, Handy und Desktop) in
  `C:\Projekt\BetBoy\output\wettfinder-vergleich-20261117\`.
- **Kleinstaaten-Sperre (#133):** `ev_signal_sources.SMALL_NATIONS` (15 Verbände), `small_nation_under_blocked`,
  `without_small_nation_unders` am Ende von `automated_wettfinder_forecasts`. Evidenz und Abrechnung bleiben.
  Protokoll `docs/audits/2026-11-16-kleinstaaten-sperre.md`.
- **Nachtlauf „heute zuerst“ (#137):** `wettfinder_automation.run_wettfinder` mit `publish_today`, den Stufen
  `forecast_publication`, `tip_receipts`, `football_discovery_next_day`, `forecast_publication_next_day`,
  `football_appearances`, `forecast_publication_final` und `_log_held_receipts_failure`. Drei Uhren-Regeln stehen in
  `AGENTS.md`. Protokoll `docs/audits/2026-11-16-nachtlauf-heute-zuerst.md`.
- **Ratenlimit (#141):** `api_budget.APIBudgetGovernor.recent_request_count`;
  `team_sport_prices.SIDE_REQUESTS_PER_MINUTE = 9`, `_minute_allowance`, Warteliste `minute_deferred` in
  `refresh_team_sport_prices`; `challenge_15k.RATE_LIMIT_RETRY_DELAY_SECONDS = 30.0`,
  `ChallengeDataProvider.enable_rate_limit_retry`, keine Einzelabrufe in `details_by_fixture` nach einem 429;
  `wettfinder_automation._worker_football_provider` (vier Aufrufstellen),
  `riskobet_settlement_automation._default_loader`. Tests `tests/test_api_rate_limit.py` (28, im CI-Job
  `price-policy`). Protokoll mit Release-Abschnitt `docs/audits/2026-11-18-ratenlimit-suche-morgen.md`.

### Analysen ohne App-Änderung

- **Gesamtaudit 16.11.** (`AUDIT_BERICHT_2026-11-16_CLAUDE.md`, acht Rollen mit Gegenprüfung): 142 Befunde,
  0 kritisch, 14 hoch.
  - Kern: Das Fussballmodell trifft so oft, wie es sagt (61,6 % bei 61,7 %, 11 493 Wetten), verliert zur
    gespeicherten Quote aber 7,7 %. Wo das Modell mehr sieht als die Quote, trifft es 49,0 % statt 60,2 %.
    Doublebet und 15K wählen genau dort.
  - Der Massnahmenplan hat 15 Punkte (Abschnitt 7 des Berichts). Punkt 1 ist im Kern umgesetzt (#137). Die Punkte
    2 bis 15 warten auf Owner-Entscheide; die acht offenen Fragen stehen in Abschnitt 9 des Berichts.
  - Die Rohbefunde liegen lokal unter `C:\Projekt\BetBoy\output\audit-20261116\`. **Der volle Anhang gehört nicht
    ins öffentliche Repo:** Er zeigt auf alte Schlüssel-Commits in der Git-Historie.
- **Kleinstaaten** (16.11.): Die Vorab-Prüfung bestätigte, dass das Modell dem Favoriten gegen Kleinstaaten zu
  wenige Tore gibt. Die Reparaturkandidaten 1 bis 3 erfüllten ihre Regel nicht (Kandidat 3, multiplikativ, war
  insgesamt besser). Owner: „Bis März planen“. Plan
  `docs/superpowers/plans/2026-11-16-laenderspiel-modell-bis-maerz.md` (Abschnitt 9).
- **Doublebet-Prüfungen** (16.11., `docs/audits/2026-11-16-doublebet-*.md`):
  - D1 (Modell gegen Markt im Band 1,80 bis 2,20): nicht prüfbar, 54 statt 100 Zeilen ab 65 % Modellchance.
  - D2 (Rangfolge bei gleicher Quote): nicht bestätigt. Die obere Hälfte der Modellchance gewinnt nicht öfter als
    die untere (−1,5 Punkte, 95-%-Intervall −6,3 bis +3,3, 2061 Wetten).
  - Märkte: kein Kandidat. Form der letzten 10 Spiele: trennt nicht (−3,0 Punkte).
  - Am Doublebet ist nichts geändert. Dieselbe Regel läuft im Band auf Prognosen ab 16.11. erneut, etwa Ende
    Dezember.
- **Erste Nacht „heute zuerst“** (18.11.): Reihenfolge wie entworfen, erstes Schreiben 03:41:30 statt 03:49:15.
  Die Suche für morgen verlor aber 34 von 66 Ligen an HTTP 429. Daraus entstand PR #141.
- **Ursache der 429** (18.11., aus `api_budget_events`): In 12 von 19 Minuten seit 08.11., in denen die
  Preisauffrischung zehn oder mehr Eishockey-Abrufe schickte, lehnte der Anbieter die nächsten Fussball-Abrufe ab;
  nach neun oder weniger nie (0 von 15). Der Gratis-Tarif erlaubt zehn Abrufe je Minute.

## 5. Lesungen vom 19.11.2026 (nur gelesen)

### Erste Nacht mit der Ratenlimit-Reparatur

| | Nacht 18.11. (vorher) | Nacht 19.11. |
|---|---|---|
| HTTP 429 auf Fussball-Abrufe | 40 | 0 (960 Abrufe seit dem Release) |
| Suche für morgen | 0 Spiele, 34 Betriebsfehler | 66 Ligen, 62 Spiele gefunden, 41 gelistet, 0 Betriebsfehler |
| Erstes Schreiben „heute“ | 03:41:30 | 03:40:57 |
| Dauer der Suche für morgen | 47 s | 696 s |
| Ende des Laufs | 03:48:20 | 03:59:34 (24,5 von 60 Minuten) |

- Seit dem Release endeten 6 Quotenläufe, der Nachtlauf und 112 Shadow-Läufe mit Exit 0, kein Alarm.
- Eishockey blieb bei höchstens 9 Abrufen in 60 Sekunden. Der nächste Fussball-Abruf nach jeder Preisauffrischung
  ging durch.
- Die Suche für morgen dauert länger, weil sie jetzt alle Ligen durchläuft und 54 Spiele modelliert.
- Die Preisauffrischung der Nacht prüfte 7 statt 8 Eishockey-Spiele (`ice_hockey:minute_limit`).
- **Nach dem Lauf von 06:15 standen 7 Eishockey-Spiele in `minute_deferred`, alle ohne Quote** (3 europäische am
  Abend des 19.11., 4 NHL in der Nacht auf den 20.11.). Der Engpass ist die alte Obergrenze von 8 Spielen je
  Sportart und Lauf bei 22 Spielen im Fenster. Die Reparatur kostete in der Nacht einen Platz. Wer wartet, kommt im
  nächsten Lauf innerhalb seiner Klasse zuerst dran.

### Tipp-Ergebnisse vom 18.11.

Schlichte Zählung aus `forecast_evidence.db`, `consumer_tips.db` und `riskobet.db`. Sie ist kein Beleg für einen
Vorteil und keine der vorab festgelegten Messungen.

- **Öffentliche Tipps:** 3 von 3 (zwei E-Sport, ein Tennis). Alle 25 gelisteten Wettfinder-Auswahlen: 15 gewonnen.
- **Hauptauswahl je Spiel** (die Auswahl mit der höchsten Modellchance):

  | Sportart | 18.11. | 12. bis 18.11. |
  |---|---|---|
  | Fussball | 1 von 1 | 79 von 90 |
  | Tennis | 2 von 2 | 6 von 7 |
  | Eishockey | 5 von 11 | 19 von 43 |
  | E-Sport | 3 von 9 | 21 von 38 |
  | Basketball | 0 von 1 | 11 von 18 |

  Die hohe Fussball-Quote sagt nichts über Gewinn: Die Hauptauswahl ist dort meist ein sehr wahrscheinlicher Markt
  mit kleiner Quote. Eishockey und Basketball speichern beide Seiten eines Spiels; nur die Hauptauswahl sagt dort
  etwas.
- **Doublebet seit 03.11.:** 7 von 19 (37 %) bei Quoten um 2,0, jede gezeigte Auswahl einmal gezählt. Am 18. und
  19.11. gab es keine Auswahl. Die Zahl „6 von 20“ vom 16.11. lässt sich mit dieser Zählung nicht nachstellen; im
  Archiv sind es bis dahin 6 von 16.
- **RisikoBet am 18.11.:** 13 von 20 abgerechneten Auswahlen gewonnen (E-Sport 13 von 18, Fussball 0 von 2).

## 6. Arbeitsweise

1. **Eigener Worktree, eigener Branch.** Zum Beispiel
   `git worktree add .worktrees/codex-<thema> -b codex/<thema> origin/main`. Nie im Hauptcheckout arbeiten, nie
   fremde Worktrees anfassen, nie `git stash` ohne Tag.
2. **Python.** Die venv liegt im Hauptcheckout: `..\..\.venv\Scripts\python.exe` aus dem Worktree (Python 3.12).
   Das System-Python hat weder pytest noch ruff.
3. **Tests.** Zuerst ein roter Test, dann grün. Gezielt laufen lassen:
   `..\..\.venv\Scripts\python.exe -m pytest tests/<datei>.py -q -p no:cacheprovider`, dazu
   `..\..\.venv\Scripts\python.exe -m ruff check .`. Die Vollsuite braucht auf Windows rund 1,5 Stunden; nie
   nebenbei starten. Unter der Produktionsregel laufen die Tests mit `BETBOY_TEST_PRICE_POLICY=floor`.
4. **CI** (`.github/workflows/tests.yml`) läuft bei jedem Push und bei jedem PR (jeder Job erscheint deshalb
   doppelt):
   - „ruff + schnelle Teilmenge“;
   - „Lader/Publikation/Daily3/15K“ unter `floor` und unter `gate`, seit 18.11. mit `tests/test_api_rate_limit.py`;
   - „Vollsuite Hälfte A/B“ nur von Hand über `workflow_dispatch`.

   Die automatischen Jobs prüfen rund 35 von 460 Testdateien (Stand Audit 16.11.). Grüne CI heisst also nicht, dass
   die Tests einer geänderten Datei gelaufen sind. Die betroffenen Testdateien deshalb immer lokal laufen lassen.
5. **Alte Testfehler ausserhalb der automatischen Jobs,** gleich auf `main`:
   - Stand 18.11., in den 32 von PR #141 betroffenen Testdateien, unter `gate` drei:
     `test_forecast_consumer_reuses_exact_cached_price_without_network` (`tests/test_team_sport_prices.py`),
     `test_native_conflicting_role_ids_fail_before_any_request` (`tests/test_api_hockey_prices.py`),
     `test_active_15k_model_surface_obeys_bound_floor_before_slot_selection[1.2-True]`
     (`tests/test_shared_quote_observations.py`). Unter `floor` 25 in denselben drei Dateien (6, 1 und 18).
   - Stand 17.11., breiterer Lauf unter `floor`: 38 in sieben Dateien (`test_shared_quote_observations` 18,
     `test_team_sport_prices` 6, `test_esports_prices` 5, `test_team_sport_forecasts` 5, `test_hockey_esports_clock`
     2, `test_selection_performance` 1, `test_forecast_evidence` 1).
   - Bei einem breiten Lauf die Fehlermenge gegen den Stand von `main` vergleichen (eigener Checkout von
     `origin/main`), nicht die Zahl.
6. **Commit und PR.** Commit-Text aus einer Datei (`git commit -F datei`), PR mit `gh pr create --body-file datei`.
   Nach `cd` in einen Ordner ausserhalb des Repos scheitert `gh`.
7. **Merge** erst nach grüner CI und Owner-OK: `gh pr merge N --merge --match-head-commit <sha>`.
8. **Nach dem Merge:**
   - `git fetch origin`, Worktree auf `origin/main` setzen.
   - Die Kopien im Hauptcheckout erneuern, in Git Bash aus dem Worktree:
     `git show origin/main:STATUS.md > C:/Projekt/BetBoy/betboy-app/STATUS.md`, ebenso `AGENTS.md`, danach die
     sha256 vergleichen. Nicht mit `>` in der PowerShell 5.1; die schreibt UTF-16.
9. **`STATUS.md`** am Anfang lesen und am Ende den Abschnitt „Stand“ ersetzen, nicht anhängen.
10. **Berichte** nach `docs/audits/<datum>-<thema>.md`, Zahlen immer mit n, Intervall und Herkunft. Vor jeder
    Messung die Regel vorab festlegen und committen.
11. **Werkzeuge unter Windows:**
    - Bash-Heredocs halbieren Backslashes. Skripte mit Backslashes als Datei schreiben, nicht als Heredoc.
    - Die Arbeitskopie ist CRLF (`core.autocrlf=true`), der Index LF. Beim Bearbeiten das vorhandene Zeilenende
      behalten. Alles, was auf den Server geht, muss LF haben.
    - Git und die Shell können minutenlang hängen. `timeout` davorsetzen, lange Befehle im Hintergrund starten.
    - Lokale Vorschau der Wettfinder-Karten: Eintrag in `C:\Projekt\BetBoy\.claude\launch.json` (Streamlit über die
      venv mit Testdaten aus `tests/test_sports_editorial.py`).

## 7. Release-Verfahren (genau so, Schritt für Schritt)

**Voraussetzungen:** ausdrückliches Owner-OK für Merge und Release („live stellen“), ein grüner CI-Lauf des PR und
`--match-head-commit` beim Merge.

**Für das nächste Release:**

- Letzter Ordner: `C:\Projekt\BetBoy\output\release-20261118-1\` mit `make_gen.py`, `gen_deploy59.py`, `deploy.sh`,
  `release-files.txt`, `build_offline_check.py`, `offline_check.py`, `assert_discrimination.py`,
  `run_release.tmpl`, `run_release.sh`, `upload\`, `deploy-01.log`.
- **`PREV` ist `87f24343f3d3c3d926f5df0b4ad60cddc22d6191`.** Der nächste Generator heisst `gen_deploy60.py`.
- Die Prüfzeilen im Python-Block prüfen unter anderem die Policy v16, die Stufenfolge „heute zuerst“, die Karten
  des Wettfinders und das Ratenlimit. Zwei Zeilen zählen genau: `_worker_football_provider(` kommt fünfmal in
  `wettfinder_automation.py` vor, `_minute_allowance(sport, api_key, governor)` zweimal in
  `refresh_team_sport_prices`. Bringt ein PR eine Stelle dazu, die Zeile anpassen.

**Schritte:**

1. **Ordner** `C:\Projekt\BetBoy\output\release-YYYYMMDD-N\` anlegen, mit `offline_runtime_state\` und `upload\`.
   `release-files.txt` = `git diff --name-only <live-sha> <ziel-sha> | LC_ALL=C sort`. Die Liste muss in
   C-Reihenfolge sortiert sein (Grossbuchstaben zuerst), sonst bricht `deploy.sh` beim Vergleich ab.
2. **`make_gen.py`** leitet den neuen Generator vom letzten ab. Es ersetzt nur `OUT`, `PREV`, die Kommentarzeile
   (Owner-Wortlaut, PR, Datum), bei Bedarf die Modulliste und zusätzliche Prüfzeilen vor
   `print('OFFLINE_RELEASE_IMPORTS=ok')`. Jede Ersetzung ist mit `assert s.count(old) == 1` gesichert. Es kopiert
   `run_release.tmpl` und `build_offline_check.py` mit der neuen Kennung. Danach `make_gen.py`, `gen_deployNN.py`
   und `build_offline_check.py` ausführen (mit dem Python der venv); das schreibt `deploy.sh` und
   `offline_check.py`. Zum Schluss `sed "s/__TARGET__/<ziel-sha>/" run_release.tmpl > run_release.sh` (lokal).
3. **Prüfzeilen pflegen.** Sie sammeln sich seit Oktober an. Entfernt oder ändert ein PR eine Funktion oder
   Konstante, muss die Zeile ersetzt werden. Sonst bricht `deploy.sh` nach dem Fast-forward ab: Der Code ist dann
   neu, die App aber nicht neu gestartet.
4. **Offline-Prüfung lokal, Pflicht vor dem Hochladen:**
   - Temporären Worktree auf das Ziel legen: `git worktree add --detach <W> <ziel-sha>`.
   - `offline_check.py` ist der Python-Block aus `deploy.sh` mit dem Worktree-Pfad statt `/opt/betboy/app` und einem
     Stub `{"challenge_release_candidates": []}` statt des Tagesdokuments.
   - Aus dem Worktree mit `PYTHONPATH=<W>`, `PYTHONDONTWRITEBYTECODE=1` und `..\..\.venv\Scripts\python.exe -B`
     laufen lassen. Erwartet wird `OFFLINE_RELEASE_IMPORTS=ok`, und `git status --porcelain` im Worktree bleibt
     leer.
   - Worktree wieder entfernen.
5. **Gegenproben:**
   - `assert_discrimination.py`: Die neuen Bedingungen gelten auf dem Ziel und scheitern auf `PREV`.
   - `diff` des neuen `deploy.sh` gegen das zuletzt ausgeführte: nur die gewollten Stellen weichen ab.
   - Seit 17.11. üblich: eine unabhängige Gegenprüfung des Helfers (Helfer selbst, Prüfzeilen auf dem Linux-Server,
     erste Läufe auf altem Datenstand) vor dem Hochladen.
6. **Hochladen:**
   - `deploy.sh` und `run_release.sh` nach `upload\deploy-YYYYMMDD-N.sh` und `upload\run_release-YYYYMMDD-N.sh`
     kopieren, auf CR prüfen (`grep -c $'\r'` muss 0 sein), `bash -n`, `sha256sum`.
   - In der PowerShell `scp` nach `/tmp/`. `sha256sum` auf dem Server muss gleich sein. Kein `sed` auf dem Server.
   - Dabei den Server lesen: HEAD = `PREV`, alle Jobs `inactive`, nächste Timer.
7. **Ausrollen:**
   `ssh betboy-vps 'date +%T; bash /tmp/run_release-YYYYMMDD-N.sh 2>&1' | Tee-Object -FilePath <ordner>\deploy-01.log`
   - **Wartefenster:** Das Skript wartet bis zu 15 Minuten auf ein Fenster: kein Job aktiv, nächster Shadow-Lauf
     200 bis 560 Sekunden entfernt (`/tmp/shadow_gap.sh` auf dem Server).
   - **Prüfungen von `deploy.sh`:** Root und Ziel-sha; flock `/run/betboy-deploy/deploy.lock`; Remote-URL, Branch
     `main`, HEAD = `PREV`, sauberer Baum, keine Hooks, keine ungetrackten `.py`; alle Jobs inaktiv; Backup-Timer
     inaktiv und disabled; `fetch`, `origin/main` = Ziel, `PREV` ist Vorfahre; Dateiliste exakt gleich; keine
     Änderung unter `deploy/systemd/`, an `.sh` oder an den Requirements; Timer mehr als 150 Sekunden entfernt.
   - **Ablauf:** `merge --ff-only`, Offline-Importprüfung, `systemctl restart betboy-app`, Health lokal und
     öffentlich, Timer aktiv, Hashes der veröffentlichten Dokumente vor und nach dem Lauf.
   - **Erwartet am Ende:** `HEAD=<ziel>`, `NO_NEW_BACKUP=yes`, `UNITS_UNCHANGED=yes`, `DEPLOY_EXIT=0`.
   - „Auto packing the repository in background“ im Log ist nur die Aufräumroutine von Git.
   - Bleibt der Helfer zwischen „Fast-forward“ und `OFFLINE_RELEASE_IMPORTS=ok` stehen, nicht blind erneut starten
     (HEAD ist dann nicht mehr `PREV`). Mit dem Owner entscheiden: App von Hand neu starten oder zurück.
8. **Danach:**
   - Server lesen (HEAD, sauberer Baum, App, Caddy, 7 Timer, Journal der App, erster Shadow-Lauf), Live-Seite
     ansehen. Wo nötig den nächsten Lauf abwarten.
   - Protokoll-PR: `STATUS.md` (Überschrift, Zeilen „Produktion“ und „`origin/main`“, die Zeile des Themas),
     `AGENTS.md` (ein Satz „Live seit …“ im Regelabsatz) und ein Abschnitt „Release …“ im Audit-Dokument des PR.

**Grenzen des Helfers:** Er verbietet Änderungen an Einheiten, an `.sh` und an den Requirements. Dafür braucht es
einen eigenen, geprüften Weg und ein eigenes Owner-OK (`AGENTS.md`, „Betrieb seit 25.10.2026“).

## 8. Server-Zugriff

- **Nur über die PowerShell:** `ssh betboy-vps`, `scp … betboy-vps:/tmp/`. Skriptdateien mit LF hochladen.
- **Anführungszeichen:** Ein Fernbefehl in doppelten Anführungszeichen darf innen einfache tragen (wie in
  Abschnitt 1). In einem einfach gequoteten Fernbefehl verschluckt die PowerShell innere doppelte Anführungszeichen;
  dort ohne sie schreiben (`date +%T`, `grep -E a\|b`).
- **Lesend ohne Upload:**
  `Get-Content skript.py | ssh betboy-vps 'sudo -n -u betboy /opt/betboy/venv/bin/python - 2>&1'`.
- **Lesend mit Upload:** `sudo -n -u betboy nice -n 19 /opt/betboy/venv/bin/python -I /tmp/x.py`. Braucht das Skript
  Module der App, im Skript `sys.path.insert(0, "/opt/betboy/app")` setzen; `-I` ignoriert `PYTHONPATH` und das
  Arbeitsverzeichnis. Datenbanken mit `sqlite3.connect("file:…?mode=ro", uri=True)` öffnen.
- **Der ssh-Benutzer kann nicht nach `/opt/betboy/app` wechseln.** Stattdessen
  `sudo -n -u betboy git -C /opt/betboy/app …` oder `sudo -n -u betboy bash -c 'cd /opt/betboy/app && …'`.
- **Journal:** `sudo -n journalctl -u betboy-wettfinder.service --since 03:34 --no-pager`. Die Stufenzeiten stehen
  als Zeilen `wettfinder_stage` darin (`stufen.sh`).
- **Mit Env (API-Schlüssel), nur mit Owner-OK für den Abruf:**
  `sudo -n bash -c "set -a; . /etc/betboy/betboy.env; set +a; cd /opt/betboy/app && exec sudo -n -E -u betboy env PYTHONDONTWRITEBYTECODE=1 nice -n 19 /opt/betboy/venv/bin/python -B /tmp/x.py"`.
- **Schlüsselwerte nie ausgeben**, auch nicht gekürzt.
- **`forecast_quotes` hat keinen Index auf `forecast_id`.** Quoten in einem Durchgang lesen, nie `EXISTS` je Zeile.
- **Nichts ändern ohne Auftrag:** keine Backups, keine Kopien der Produktions-Datenbanken, keine API-Scans, kein
  `systemctl`-Eingriff, kein `sed` auf dem Server.

## 9. Messungen und Termine

| Wann | Was | Wie |
|---|---|---|
| Fr 20.11. früh | Nachtlauf mit vollem Samstag als „morgen“ | Abschnitt 1, Punkt 3 |
| Sa 21. und So 22.11. | erstes volles Liga-Wochenende mit Doppel-Scan: Laufzeit, HTTP 429, Verbrauch | Abschnitt 1, Punkt 4 |
| laufend | Warteliste der Eishockey-Quoten, Eishockey-Verbrauch je Tag | `nacht_lesen.py`, `stand_tag.sh` |
| laufend | Doublebet beobachten | `ergebnisse.py`; Stand 7 von 19 seit 03.11. |
| nach dem 22.11. | Fallenfilter zählen, nur Anzahl | unten |
| nächster Europapokal-Spieltag | Ligastärke im Betrieb messen | `docs/audits/2026-11-05-ligastaerke-europapokal.md` |
| ~28. bis 30.11. | Formstärke und Hybrid | `scripts/form_strength_measurement.py --since 2026-11-06` (Formstärke gegen Legacy) und `--baseline legacy_form_strength_v1 --candidate dixon_coles_hl365_hybrid`. Regeln in `docs/audits/2026-11-06-formstaerke-umsetzung.md` und `2026-11-07-formstaerke-eingeschaltet.md`. Nicht vorher laufen lassen |
| **30.11.** | Fallenfilter auswerten | unten |
| ab 30.11. | Liste ab 70 % auf neuen Tipps | `output/quoten-20261109/hit_by_model.py`; das Fenster ist im Skript fest auf 07.10. bis 10.11. eingetragen und muss auf „ab 10.11.“ gesetzt werden |
| nach dem 30.11. | Nachquote, nur wenn der Fallenfilter besteht | Owner „Ja, warten“ (`output/quotenluecke-20261110/ERGEBNIS.md`) |
| Mitte Dezember | Länderspiel-Modell: Daten neu holen (13 API-Abrufe, nur mit Owner-OK), Diagnose nur auf Entwurfsdaten bis 30.06.2025, Vorab-Regel für Kandidat 4 (gegnerbereinigt) committen | `docs/superpowers/plans/2026-11-16-laenderspiel-modell-bis-maerz.md` |
| Ende Dezember | Doublebet-Bandprüfung: dieselbe Regel wie D1/D2 im Band 1,80 bis 2,20 auf Prognosen ab 16.11. | `docs/audits/2026-11-16-doublebet-pruefung-vorab.md`, `-rangfolge-vorab.md` |
| Ende Januar 2027 | Prüfung Kandidat 4 auf 01.07.2025 bis 18.11.2026, Bericht, Owner-Entscheid | Plan bis März |
| Ende Februar 2027 | Release, falls bestanden; dann fällt die Kleinstaaten-Sperre | Plan bis März |

### Fallenfilter

**Regel** (`docs/audits/2026-11-09-fallenfilter-vorab.md`, mit Nachtrag vom 13.11.2026):

- **Falle:** Modellwahrscheinlichkeit der ersten Veröffentlichung minus 1 / Einstiegsquote ≥ 0,05.
- **Einstiegsquote seit 13.11.** (Owner „B“): die früheste gespeicherte Quote mit `kind = entry` über alle Prognosen
  mit demselben `event_key`, `market_key` und `selection`.
- **Fenster:** erste Veröffentlichung vom 10.11.2026 00:00 UTC bis vor 28.11.2026 00:00 UTC.
- **Bestanden** nur mit mindestens 150 abgerechneten Fallen, **A** z ≥ 1,645 (Fallen treffen seltener als
  versprochen) **und B** z ≥ 1,645 (Fallen treffen seltener als die übrigen Tipps mit Quote).
- **Keine Varianten**, egal wie der Test ausgeht.

**Zählungen bisher** (Befehl in Abschnitt 1, Punkt 6):

| Wann | abgerechnet | Fallen | übrige mit Quote | ohne Quote |
|---|---:|---:|---:|---:|
| 13.11. 10:01 | 58 | 3 | 4 | 51 |
| 13.11. 22:13 | 60 | 3 | 4 | 53 |
| 19.11. 08:57 (9,3 Tage) | 430 | 46 | 152 | 232 |

Von den 198 Tipps mit Quote haben 125 ihre Quote nur über die Auswahl. Die Fallen sind fast alle Fussball (45 von
46). Bei rund 5 Fallen pro Tag reicht das Fenster bis 28.11. voraussichtlich nicht; die Verlängerung ist in der
Regel vorgesehen.

**Auswertung am 30.11., in dieser Reihenfolge:**

1. **Zuerst nur zählen** (`--count-only`).
2. **150 Fallen oder mehr:** einmal ohne `--count-only` auswerten. Das Ergebnis mit allen Zahlen nach
   `docs/audits/` schreiben.
3. **Weniger als 150 Fallen: nicht auswerten.** Das Skript druckt ohne `--count-only` auch dann Trefferquoten. Das
   Fenster um 7 Tage verlängern (`--until 2026-12-05T00:00:00+00:00`, dann `12-12`, `12-19`, `12-26`) und nach
   jedem neuen Fensterende wieder nur zählen.
4. **Am 26.12. immer noch unter 150:** Der Test ist unentschieden, der Filter kommt nicht.

**Im Bericht nennen:** den Nachtrag vom 13.11. und die Zahl der Tipps mit Quote nur über die Auswahl; dass die
erste Veröffentlichung vieler Fussballtipps am Vortag liegt; die Änderungen im Fenster (Regler-Startwert 70 %,
Folgetag immer, Teamsport und E-Sport morgen, Nachtspiele als Evidenz, Kleinstaaten-Sperre, neue Wettfinder-Karten,
Nachtlauf „heute zuerst“, die an 429 verlorene Suche vom 18.11.); dass die anderen Sportarten fast nie eine
Einstiegsquote haben.

**Folgen:** Besteht der Filter, ist er ein Kandidat und kommt nur mit Owner-OK in einem eigenen PR, als Sperre im
Hintergrund. Besteht er nicht, ist er verworfen.

## 10. Offene Aufgaben

### Codex, in sinnvoller Reihenfolge

1. **Prüfliste** aus Abschnitt 1, mit der Nacht auf den 20.11. und dem Wochenende 21./22.11.
2. **Ergebnis in die Doku:** Nach der Nacht auf den 20.11. den Abschnitt „Offen“ in
   `docs/audits/2026-11-18-ratenlimit-suche-morgen.md` und die Zeilen in `STATUS.md` nachführen.
3. **Messungen am 30.11.** (Abschnitt 9): Fallenfilter, Formstärke/Hybrid, Liste ab 70 %.
4. **Länderspiel-Modell** bis Mitte Dezember, **Doublebet-Bandprüfung** Ende Dezember (Abschnitt 9).
5. **Eishockey-Quoten:** beobachten, ob die Obergrenze von 8 Spielen je Lauf bei vollen NHL-Tagen Spiele ohne
   Quote in den Anstoss schickt. Eine Änderung wäre App-Code mit eigenem PR; die Tagesgrenze von 100 Abrufen lässt
   wenig Raum (8 Läufe zu je 9 Abrufen plus Scanner).
6. **Bekannt und nicht repariert:**
   - Die manuelle Eishockey-Suche in der App über 14 Tage schickt 16 Abrufe ohne Pause und kann die Sperre weiter
     auslösen. Der Eishockey-Scanner (`scanners/api_hockey.py`) ist nicht begrenzt.
   - Die „Zeitprüfung vor der Suche für morgen“ (Audit-Plan Punkt 1) ist nicht gebaut.
   - Die täglichen fehlgeschlagenen Eishockey-Abrufe `games` sind nicht untersucht.
7. **Tennis morgen** (Schritt 3b, offen). Der Tennis-Scan läuft um 00:05 nur für heute
   (`scripts/tennis_daily.py`). Ein zweiter Tag braucht einen eigenen Lauf, also eine geänderte Einheit mit neuen
   Pins in `deploy/bootstrap_server.sh` und `deploy/update_server.sh`; der Release-Helfer verbietet das. Eine
   Tennis-Zeile für morgen verwirft heute das ganze Dokument. Details in der Übergabe vom 13.11., Abschnitt 9.
8. **E-Sport morgen** deckt nur die nächsten 6 Spiele je Titel ab (`scanners/esports_scanner.py`). Mehr kostet
   PandaScore-Abrufe und braucht ein Owner-OK.
9. **Alte Testfehler** (Abschnitt 6, Punkt 5): Ursache prüfen, wahrscheinlich teils feste Daten gegen die echte
   Uhr.
10. **Dauerhaft offene Ergebnisse:** 5 Fussballspiele vom 1. bis 8.11. und 26 Tennisspiele aus September und
    Oktober bekommen kein Ergebnis; Spiele mit Verlängerung bleiben offen (Audit-Plan Punkt 8). Die 12 Tipps auf
    Rotherham–Crawley und Walsall–Barnet (14.11., verschoben) bleiben bis zum Nachholspiel offen.
11. **Nicht erneut geprüft seit dem 13.11.:** Morgen-Karten mit „Modellstand nicht aktuell belegt“; die
    Doublebet-Vorschau bleibt bei Vereinsspielen oft leer; Cricket-Zeilen verwerfen das ganze Dokument.
12. **Google-Play-Technik**, sobald der Owner seine Punkte klärt
    (`docs/superpowers/plans/2026-11-10-google-play-store.md`).
13. **Ältere Punkte:** `AGENTS.md`, Abschnitt „Offen“, und die Massnahmen 5, 6, 8 und 10 aus
    `AUDIT_BERICHT_2026-10-25_CLAUDE.md`.

### Nur mit Owner-OK

- Worktrees und gemergte Branches aufräumen.
- Die 8 alten fehlgeschlagenen Einheiten mit `systemctl reset-failed` entfernen.
- Jede Änderung an einer Einheit, jedes Backup, jede Kopie einer Produktions-Datenbank, jeder API-Abruf über das
  Übliche hinaus.

### Owner

- **Rückmeldung zur Live-Seite des Wettfinders** (seit 17.11. 21:17): Bleibt die rechte Spalte mit Doublebet und
  Tennis?
- **Audit vom 16.11.**, Punkte 2 bis 15 und die acht Fragen in Abschnitt 9 des Berichts: Telegram-Token; 15K-Regel
  und Ziel; Doublebet „immer auffüllen“ und Eishockey unter 60 %; Bilanz in der App; leere Liste nach Mitternacht;
  Schutz der Daten ohne Backup; Live und Platzverweis; Ungültig-Regel für RisikoBet; Kundenzugang erzwingen.
- **Bezahlter Tarif für Eishockey und Basketball:** würde die Grenze von zehn Abrufen je Minute und 100 je Tag
  heben. Nötig ist er nicht.
- Alte API-Schlüssel beim Anbieter sperren oder neu ausstellen. Der Widerruf ist nicht belegt, und die alten Werte
  stehen in der öffentlichen Git-Historie.
- Impressum, Datenschutz und AGB ausfüllen, prüfen lassen, URLs setzen.
- **Google Play:** Serverstandort, App-Adresse, Kontotyp, Rechtstexte (Plan vom 10.11.).
- **Entscheide, die warten:** Tennis-Zweitquelle, mehr E-Sport-Abdeckung für morgen, Nachquote (erst nach dem
  30.11.), Regel für dauerhaft offene Ergebnisse.

### Bewusst offen gelassen

- **Basketball (EuroLeague) bekommt nie eine Quote.** Die Zeilen tragen Vereinskürzel, API-Sports volle Namen.
- **E-Sport hat fast nie eine Einstiegsquote.**
- **Tennis und E-Sport auf den neuen Wettfinder-Karten** hat Claude live noch nicht angesehen.

## 11. Risiken und Lehren

1. **Rücksprung unter `555797b` ist gefährlich.** Der Worker schreibt Morgen-Zeilen für Eishockey, Basketball und
   E-Sport. Der Lader davor verwirft ein solches Dokument komplett. App und Worker immer auf derselben Version.
2. **Release-Prüfzeilen veralten** (Abschnitt 7, Schritt 3). Die lokale Offline-Prüfung ist Pflicht.
3. **Ratenlimits wirken über Sportarten hinweg.** Der zehnte Eishockey-Abruf einer Minute sperrte Fussball für rund
   20 Sekunden und kostete am 18.11. die halbe Suche für morgen. Neuer Code mit Eishockey- oder Basketball-Abrufen
   geht über `team_sport_prices._json_get`, damit er im Abrufprotokoll mitzählt. Die Grenze von neun nicht ohne
   Beleg aus `api_budget_events` anheben.
4. **Nichts für morgen vor das erste Schreiben legen.** Stirbt der Nachtlauf nach dem ersten Schreiben, bleibt
   heute stehen. Jeder Schritt davor verzögert heute; die Wartezeit nach einem 429 kann im schlechtesten Fall rund
   drei Minuten vor dem ersten Schreiben kosten.
5. **Laufzeit an vollen Liga-Tagen.** Der Lauf hat 60 Minuten. Mit allen Ligen dauerte die Suche für einen Freitag
   696 s. Für Samstag und Sonntag gibt es noch keine Messung mit Doppel-Scan.
6. **API-Hockey läuft nahe an der Tagesgrenze von 100** (12.11. 83, 14.11. 82). Gesperrte Abrufe brechen den
   Quotenlauf nicht ab; es fehlen dann Quoten für Eishockey, und das Doublebet hat weniger Kandidaten.
7. **Quote und Modell.** Die Daten zeigen keinen Vorsprung auf den Buchmacher (Benchmark 0 von 112 Zellen,
   Vorsprung-Analyse vom 12.11., Gesamtaudit vom 16.11.). Getestet und widerlegt sind Wetter, Ausfälle und
   Ruhetage, Startelf, Rangfolge bei gleicher Quote, Märkte, Form. Die Formstärke bringt einen kleinen Gewinn und
   ist live.
8. **Vorab festgelegte Messungen** scheitern leicht an Umbauten daneben. Nach jedem Umbau an Listen oder Evidenz
   die laufenden Messungen mit `--count-only` gegenprüfen.
9. **Grüne CI deckt nicht alles** (Abschnitt 6, Punkt 4).
10. **Oberfläche „wie Seite X“:** Der Owner sah am 17.11. „massive Unterschiede“, obwohl die erste Runde fertig
    gemeldet war. Seither gilt: beide Seiten live nebeneinander vergleichen, in Handy- und Desktop-Breite, und dem
    Owner Bilder zeigen.
11. **Ein Timer-Neustart ohne Stempel** feuerte am 25.10. die Tagesscans sofort. Einheiten nur über den geprüften
    Weg ändern.
12. **Öffentliches Repo.** Keine Schlüsselwerte, keine persönlichen Daten, kein Audit-Anhang mit Verweisen auf alte
    Schlüssel-Commits.

## 12. Regeln

`AGENTS.md` ist massgeblich und enthält jeden Owner-Entscheid mit Datum. Hier die Regeln, die im Alltag am
häufigsten greifen:

- **Modell vor Preis.** Keine Quote fliesst in eine Modellschätzung oder in die Reihenfolge. Die Marktmischung hat
  der Owner abgelehnt.
- **Keine Auswahl nach Quote** und keine höhere Mindest-Modellchance als Lösung für die Trefferquote.
- **Kein Schwellen-Tuning.** Regeln nur mit vorab festgelegter Hypothese und zeitlich getrennter Prüfung ändern.
- **Die App zeigt keine Buchmacherquoten.** Die 1,20-Grenze bleibt im Hintergrund.
- **`BETBOY_PRICE_POLICY=gate` nie in Produktion.** `BETBOY_RELEASE_MARKET_BENCHMARK` nicht setzen.
- **Tipps werden nach Trefferquote und Kalibrierung bewertet**, nicht nach ROI. Keine Gewinnversprechen.
- **Nur bestehende Quellen**, keine neuen bezahlten Tarife ohne Owner-Entscheid.
- **Freigaben einzeln:** Merge, Release, API-Abrufe über das Übliche hinaus, Backups und DB-Kopien, Änderungen an
  Einheiten. Die Zahl der Abrufe vorher nennen.
- **Releases** nur über den No-Backup-Fast-forward-Helfer, nie hinter `555797b`.
- **Morgen-Zeilen** sind nie Tipp, 15K-Eintrag, Doublebet-Wahl, Shadow oder Archiv vor ihrem Spieltag.
- **Nachtlauf:** nichts für morgen und keinen Hintergrundschritt vor das erste Schreiben legen.
- **Ratenlimit:** höchstens neun Abrufe je Minute und Sportart; App-Seiten, manuelle Suchen und Preispfade warten
  nie auf einen 429.
- **Kleinstaaten-Sperre** bleibt, bis das reparierte Modell seine eigene Prüfung besteht.
- **Preisjagd** nicht messen, nicht bauen, nicht erneut vorschlagen (Owner 12.11.2026).
- **Fallenfilter und Formstärke-Messung:** bis zum Termin nur zählen, keine Varianten.
- **Doublebet:** keine Vorschläge zum Text der Seite, wenn der Owner etwas anderes verlangt hat (Owner 16.11.).
- **Schlüsselwerte** nie in Chat, Doku, Tests oder Git.
- **Checkout-Disziplin:** eigener Worktree, kein `git stash` ohne Tag, fremde Worktrees und der Hauptcheckout
  bleiben unberührt.

## 13. Owner und Zusammenarbeit

- **Owner:** Miroslav, Alleinentwickler, Deutsch (Schweiz, CHF).
- **Antworten:** kurz und direkt, Kernaussage zuerst, einfache Sprache ohne Fachjargon, „ss“ statt „ß“.
- **Entscheide vorlegen:** eine Frage, höchstens zwei Wege, mit Empfehlung. Kürzel wie `forecast_id` im Gespräch
  mit ihm vermeiden.
- **Kurze Fragen des Owners:** „wie sieht es aus?“ meint den Stand der Läufe und der Seite; „wie waren die
  Ergebnisse?“ die Tipp-Ergebnisse vom Vortag. Antwortet er mit „Ja, mergen“ oder „Ja, live stellen“, gilt das nur
  für den gerade gefragten PR oder das gerade gefragte Release.
- **Ehrlichkeit:** Massstab ist `PROJEKTBIBEL.md`. Zahlen mit n, keine Gewinnversprechen, Unsicheres als unsicher
  nennen. Sagen, was nicht geprüft ist.
- **Commits** von Claude enden mit `Co-Authored-By: …`, PR-Texte mit der Generated-Zeile. Codex nutzt seine eigene
  Signatur.

## 14. Pfade

| Wo | Was |
|---|---|
| `/opt/betboy/app/runtime_state/wettfinder_latest.json` | Tagesdokument: `model_candidates`, `candidates`, `football_next_day`, `next_day_search_date`, `sources.*.next_day`, `team_sport_prices`, `generated_at`, `decision_at` |
| `runtime_state/forecast_evidence.db` | `forecast_rows` (Prognosen mit `event_key`, `market_key`, `selection`, `starts_at`, `payload_json`), `forecast_quotes` (`kind` = `entry` oder `closing`), `forecast_results` (`outcome` = `WIN`, `LOSS`, `VOID`) |
| `runtime_state/consumer_tips.db` | `consumer_tip_publications` (`surface`: `wettfinder_automatic`, `wettfinder_default_inventory`, `daily3_rail`, `daily3_default_plan`, `daily3_plan`, `riskobet_catalogue`), `consumer_tips` (`payload_json`, öffentliche Tipps tragen `featured_role = featured`) |
| `runtime_state/riskobet.db` | `settlements` (`result` = `WON`, `LOST`, `VOID`), `candidates`, `runs` |
| `runtime_state/team_sport_quotes.json` | NHL-, Eishockey- und Basketball-Quoten, `attempts` (3-Stunden-Sperre), `identity_gaps`, `budget_deferred`, seit 18.11. `minute_deferred` (Warteliste) |
| `runtime_state/api_budget.db` | `api_budget_state` (Grenze und Rest je Anbieter und Tag; Monatszeilen mit `:month`), `api_budget_events` (jeder Abruf mit `started_at`, `endpoint`, `http_status`, `decision`) |
| `runtime_state/ops_alerts.jsonl` | Alarme der Kerneinheiten |
| `/etc/betboy/betboy.env` | Umgebung mit Schlüsseln; nie ausgeben |
| `C:\Projekt\BetBoy\output\` | Auswertungen und Release-Belege, nicht in Git. Neu seit 13.11.: `uebergabe-20261119` (Helfer für Abschnitt 1), `release-20261113-1` bis `release-20261118-1` (Generatoren `gen_deploy52.py` bis `gen_deploy59.py`), `audit-20261116` (Rohbefunde, nicht veröffentlichen), `wettfinder-vergleich-20261117` (Bilder) |
| `C:\Projekt\BetBoy\betboy-app\.worktrees\claude-audit-repairs-20261019\runtime_state\market_benchmark\` | 98 CSV von football-data.co.uk für Marktvergleiche |
| Timer (Europe/Zurich) | tennis 00:05; esports 03:10; wettfinder 03:35 (60 Minuten); backup-retention gegen 04:20; redcard-history 05:41; redcard-settlement 06:05; quotes 00/03/06/09/12/15/18/21:15 (12 Minuten); football-shadow alle 10 Minuten |
| Live-Seite | `https://vps-a30a123f.vps.ovh.net/` |

## 15. Was nicht geprüft ist

- **Die Nacht auf den 20.11. und das Wochenende 21./22.11.:** Laufzeit mit einem vollen Liga-Tag als „morgen“,
  Verbrauch, HTTP 429. Die Schätzung von rund 40 Minuten ist nicht gemessen.
- **Die sieben wartenden Eishockey-Spiele vom 19.11.:** ob sie vor dem Anstoss eine Quote bekamen. Der Quotenlauf
  von 09:15 ist nicht mehr gelesen.
- **Die Ursache der täglichen fehlgeschlagenen Eishockey-Abrufe `games`.**
- **Die Vollsuite** lief für keinen PR dieser Woche, weder lokal noch in der CI. Gelaufen sind die betroffenen
  Testdateien lokal und die automatischen CI-Jobs.
- **Die Doublebet-Zählung:** 7 von 19 aus dem Tipp-Archiv gegen „6 von 20“ vom 16.11. Der Unterschied ist nicht
  erklärt.
- **Die Live-Seite nach dem Release 20261118-1** über die erste Wettfinder-Karte hinaus. An der Oberfläche änderte
  das Release nichts.
- **Die Wartezeit nach einem 429 im Betrieb:** Seit dem Release gab es keinen 429, also auch keinen Lauf, der
  gewartet hat.
- **Die alten Testfehler** (Abschnitt 6, Punkt 5) sind nicht erklärt.
