# Übergabe Claude → Codex, Stand 11.11.2026

Dieses Dokument übergibt den Stand vom 09. bis 11.11.2026 vollständig. Es ergänzt `AGENTS.md` (Regeln),
`STATUS.md` (eine Seite Stand) und die Protokolle unter `docs/audits/`. Bei Widersprüchen gilt wie immer zuerst der
Code.

## Nachtrag 11.11.2026, 14:15 CET

- Produktion läuft jetzt auf `4f00d0f` (PR #118, Release 20261111-3, Beleg `output/release-20261111-3/`).
- Doublebet nimmt das Eishockey-Modell auf (Policy v15, `DOUBLEBET_RESEARCH_SPORTS`); Basketball und alle anderen
  Flächen behalten den Ausschluss. Team-Quoten werden zuerst für Spiele mit Modell geholt. Details:
  `docs/audits/2026-11-11-doublebet-eishockey.md`.
- Die Regel „nie hinter `555797b` zurückrollen“ gilt weiter.
- Basketball (EuroLeague) bekommt nie eine Quote: Unsere Zeilen tragen Vereinskürzel, API-Sports volle Namen.
  Bewusst nicht behoben, weil das Modell schwach ist (29 Spiele, 51,7 % getroffen bei 67,6 % versprochen).

## 0. Kurzfassung zum Einfügen

> Lies zuerst `AGENTS.md`, `STATUS.md` und dieses Dokument (`docs/handoffs/2026-11-11-claude-uebergabe-codex.md`).
>
> **Stand:**
> - Produktion läuft auf `555797b` (live seit 11.11.2026 09:02 CET). `origin/main` steht auf `95d2a97` plus diesem
>   Übergabe-PR; die Commits nach `555797b` sind reine Doku.
> - Offen ist nur PR #106 (Plan Google Play).
> - Alle Server-Dienste liefen am 11.11. mit Exit 0. Der letzte Alarm stammt vom 07.11.
>
> **Termine:**
> - 12.11. morgens: Prüfen, dass der Nachtlauf Morgen-Zeilen für Eishockey, Basketball und E-Sport schreibt und die
>   App sie annimmt.
> - 30.11.: Auswertung von Fallenfilter, Formstärke/Hybrid und Liste ab 70 %, alles nach den Vorab-Regeln in
>   Abschnitt 4.
>
> **Regeln:**
> - Releases nur über den No-Backup-Fast-forward-Helfer (Abschnitt 3).
> - Jeder Merge und jedes Release braucht ein ausdrückliches Owner-OK. Für Releases heisst das wörtlich „live
>   stellen“, ein „alles jetzt“ hat der Auto-Mode-Klassifikator nicht als Freigabe akzeptiert.
> - **Nie hinter `555797b` zurückrollen**, solange der Nachtlauf Morgen-Zeilen anderer Sportarten schreibt
>   (Abschnitt 6, Risiko 1).

## 1. Stand am 11.11.2026 um 10:00

### Code und Server

| Bereich | Stand |
|---|---|
| Produktion (VPS `betboy-vps`, `/opt/betboy/app`) | `555797b`, sauber (kein geänderter getrackter Pfad), App-PID nach dem Release 1585223 |
| `origin/main` | `95d2a97` (#116, Protokoll) plus dieser Übergabe-PR |
| Offene PRs | #106 „Plan: BetBoy in den Google Play Store“ (nur Doku; Icon-Entscheid „Mittelkreis“ eingetragen) |
| Dienste 11.11. | alle `success`/Exit 0: app, wettfinder 03:48, quotes 09:15, tennis 00:12, esports 03:10, football-shadow 09:22, redcard-history 05:41, redcard-settlement 06:05, backup-retention 04:24 |
| Alarme | 14 Einträge in `runtime_state/ops_alerts.jsonl`, der letzte vom 07.11. 20:52; seither keiner |
| Platte | 38 GB, 51 % belegt |
| Backup-Timer | `disabled`/`inactive`, so vom Owner gewollt |
| Telegram-Alarm | Token und Chat-ID fehlen in `/etc/betboy/betboy.env` (Owner); Alarme landen nur im Journal und in `ops_alerts.jsonl` |

### Hauptcheckout und Worktrees

- **Hauptcheckout** `C:\Projekt\BetBoy\betboy-app`:
  - Steht auf `c5a6264 [main]`, trägt fremdes WIP und liegt hinter `origin/main`.
  - Getrackte Dateien nicht anfassen.
  - Die ungetrackten Kopien `STATUS.md` und `AGENTS.md` dort werden nach jedem Merge erneuert:
    `git show origin/main:STATUS.md > C:/Projekt/BetBoy/betboy-app/STATUS.md`, ebenso `AGENTS.md`.
- **Claude-Arbeitsworktree:** `.worktrees/claude-shadow-void-verschoben`, detached auf `origin/main`.
- **Subagent-Worktrees** unter `.claude/worktrees/` mit den gemergten Branches `claude/morgen-vorschau-20261111` und
  `claude/morgen-teamsport-esport-20261111`. Beide sind sauber und können weg.
- **Alte Worktrees unter `.worktrees/`:** über 25 Stück, Claude-Branches aus dem Oktober und Codex-Branches
  (`codex/audit-repairs-20261013`, `codex/context-capacity-recovery-20260910`, `codex/erklaerbare-karten-20260908`
  und weitere).
  - 113 Remote-Branches `claude/*` sind in `origin/main` gemergt.
  - Aufräumen nur mit Owner-OK (AGENTS: „nie fremde Worktrees anfassen“).

### Was die App jetzt zeigt

| Seite | Verhalten seit 09.–11.11.2026 |
|---|---|
| **Wettfinder** | Regler „Mindest-Modellchance“ startet bei **70 %** (#109). Liste **immer heute und morgen** (#112, #115): Fussball wie bisher über `football_next_day`; seit #115 auch Eishockey, Basketball, E-Sport. Tennis und Cricket nur heute. |
| **Doublebet** | Heute unverändert. Zusätzlich „Morgen (Vorschau)“ auf der Doublebet-Seite und in der Wettfinder-Spalte. Nur Anzeige, Vormerken erst am Spieltag (#114). |
| **15K** | „Morgen“ mit allen Ligen zeigt eine Vorschau aus dem Tageslauf: Karten ohne Ticketformular, ohne Scan-Knopf. Ein Ticket für morgen ist auch nach einer manuellen Suche gesperrt (#114). |
| **Eishockey-Quoten** | NHL-Spiele bekommen seit #111 Quoten (vorher nie). |
| **Ergebnisse** | Abrechnung im Nachtlauf **und in jedem Quotenlauf** (alle 3 h), neueste Spiele zuerst (#107). |

## 2. Was vom 09. bis 11.11.2026 geschah (chronologisch)

Owner-Entscheide stehen in Anführungszeichen. Releases laufen alle über den Helfer in Abschnitt 3.

1. **09.11., Quotenanalyse** (`output/quoten-20261109/`, nur gelesen, nicht in Git).
   - Die Trefferquote der App-Tipps folgt der Buchmacherquote: 1,20–1,30 → 71 %, 1,50–1,70 → 59 %, ab 2,00 → 32 %.
   - Wo das Modell mindestens 5 Punkte über 1/Quote liegt (566 Tipps), versprach es 61,3 %, getroffen haben 47,3 %,
     die Quote sagte 49,6 %.
   - Owner lehnt ab: eine höhere Mindest-Modellchance („dann kommst du mit geringen Quoten“) und eine Auswahl nach
     Quote („dann braucht es diese App nicht“). API-Football ist bezahlt („ich habe eine API gekauft“).
2. **09.11., Startelf-Test widerlegt.**
   - Vorab festgelegt in `output/aufstellungen-20261109/HYPOTHESE.md`. Nach Owner-OK „Ja, abrufen“: 486 Abrufe,
     9107 Ligaspiele, Daten in `/var/tmp/bb_lineups/lineups.db` auf dem VPS.
   - β +0,0063 (SE 0,0043), die Abbruchregel greift.
   - Protokoll `docs/audits/2026-11-09-aufstellungen-widerlegt.md` (PR #105).
3. **09.11., Fallenfilter vorab festgelegt** (PR #105, `docs/audits/2026-11-09-fallenfilter-vorab.md`, Messskript
   `scripts/trap_filter_measurement.py`, Tests `tests/test_trap_filter_measurement.py`). Details in Abschnitt 4.
4. **10.11., Quotenlücke analysiert** (`output/quotenluecke-20261110/ERGEBNIS.md`, nur gelesen).
   - Die Einstiegsquote speichert die App nur im Nachtlauf (`record_forecast_run`). Die Quotenläufe speichern nur
     Schlussquoten in der letzten Stunde.
   - 1666 von 4920 Tipps hatten keine Quote:
     - Fussball-Sondermärkte (689, z. B. `RESULT_TOTAL_*`, `MIXED_*`, `HOME/AWAY_RANGE_*`): Die Quelle bietet sie nicht
       als Einzelwette an. Treffer 52,2 % = Modell 52,1 %.
     - Ganzes Spiel ohne Quote im Nachtlauf (535, kleine Ligen).
     - Standardmarkt fehlt (133).
     - Andere Sportarten (309).
   - Idee „Nachquote“ (erste Quote aus dem Quotenlauf als eigene Art neben `entry`): Owner „Ja, warten“, erst nach dem
     30.11. und nur, wenn der Fallenfilter besteht.
5. **10.11., Ergebnisse auch im Quotenlauf** (PR #107, Release 20261110-1 um 11:43).
   - **Anlass:** Die Montagsspiele waren am Dienstag noch offen, weil der Nachtlauf `football:event_budget_reached`
     meldete (40 Spiele je Sportart, Rotation für einen 30-Minuten-Takt).
   - **Code:**
     - `forecast_evidence_settlement.py`: `RECENT_KICKOFF_WINDOW = 72 h`, `_rotated`, `_budgeted_events`.
     - `wettfinder_automation.py`: `_settle_forecast_evidence` für Nacht- und Quotenlauf, `_quotes_run_settlement`
       (kompakt, nur ein Absturz zählt als Betriebsfehler, läuft unter der Publikationssperre).
   - **Erster Quotenlauf 12:15:** 155 Ergebnisse.
   - Protokoll `docs/audits/2026-11-10-abrechnung-quotenlauf.md`.
6. **10.11., Liste ab 70 %** (PR #109, Release 20261110-2 um 14:32).
   - Owner „wie schaffen wir eine Trefferquote von min 70 %“ → „Liste ab 70 %“.
   - `app.py`: `WETTFINDER_MIN_CHANCE_DEFAULT = 70`.
   - **Rückblick 07.10.–09.11.:** ab 70 % 72,3 % Treffer, 40 Tipps pro Tag, Quote-Median 1,28; 60–70 % 64,8 %
     bei 1,42.
   - Skript `output/quoten-20261109/hit_by_model.py`, Protokoll `docs/audits/2026-11-10-liste-ab-70.md`.
7. **10.11., NHL-Spielplan ab Vortag** (PR #111, Release 20261110-3 um 16:32).
   - **Ursache:** `team_sport_prices.refresh_team_sport_prices` fragte `api-web.nhle.com/v1/schedule/{UTC-Datum}`. Die
     NHL führt Spiele unter dem nordamerikanischen Datum; Abendspiele nach 00:00 UTC fehlten
     (`native_identity_unbound`). 0 von 83 Eishockey-Tipps hatten je eine Quote.
   - **Prüfung im Quotenlauf 21:15:** 6 von 6 Spielen zugeordnet, 12 Quoten, je 9 Buchmacher.
   - **Sperre:** `REFRESH_AFTER = 3 h` je Spiel; der Lauf um 18:15 sprang deshalb noch über.
   - Protokoll `docs/audits/2026-11-10-nhl-spielplan-vortag.md`.
8. **10.11., Folgetag immer** (PR #112, Release 20261110-4 um 21:04).
   - Owner „bei allen Tipps heute und morgen“, Schritt 1.
   - `NEXT_DAY_MIN_GAMES` entfernt (vorher 30); `AGENTS.md`-Regel angepasst.
   - Kosten: API-Football 500–3700 von 7500 Abrufen pro Tag, mit Folgetag an vollen Tagen geschätzt +1000–2000.
   - Protokoll `docs/audits/2026-11-10-folgetag-immer.md`.
9. **11.11., Tennisquoten-Probe.**
   - Owner „alles machen“. Zwei freie Abrufe bei The Odds API (`/v4/sports`, `/v4/sports/{key}/events`), das
     Kontingent blieb bei 43/457.
   - Aktiv war nur `tennis_wta_finals`. Die ATP Stockholm Open deckt die Quelle nicht ab, die Zuordnung der App ist
     korrekt.
   - `output/tennisquoten-20261111/ERGEBNIS.md`.
10. **11.11., Doublebet/15K-Vorschau und morgen für Eishockey/Basketball/E-Sport** (PR #114 und #115, zusammen
    Release 20261111-2 um 09:02).
    - **PR #114:**
      - `daily3_selection.daily3_choices(target_day=…)`, `doublebet_preview_choices`.
      - `forecast_analysis.forecast_highlight_reason(match_day=…)`.
      - `daily3_ui.render_doublebet_preview`, `app._render_editorial_rail(preview_choices=…)`.
      - `wettfinder_automation.build_next_day_challenge_preview`.
      - `challenge_15k._render_next_day_challenge_preview`, `_render_model_challenge(preview=…)`.
      - Protokoll `docs/audits/2026-11-11-morgen-vorschau-doublebet-15k.md`.
    - **PR #115:**
      - `ev_signal_sources.NEXT_DAY_SOURCE_BY_SPORT`, `automated_next_day_sports`,
        `listed_next_day_signal(decided_at=…)`.
      - Im Lader `listed_next_day_row`: Eine ungültige Morgen-Zeile fällt einzeln weg, `_listed_day` ist entfernt.
      - Teamsport- und E-Sport-Morgen-Pfad in `wettfinder_automation.py`, Archivschutz in `tip_publication.py`.
      - Protokoll `docs/audits/2026-11-11-morgen-teamsport-esport.md`.
    - **Release:**
      - Das vorbereitete Release 20261111-1, nur mit #114, wurde nie ausgerollt; das Ausrollen blockte der
        Klassifikator.
      - Die lokale Offline-Prüfung fand ein veraltetes Assert auf `_listed_day`, korrigiert in `gen_deploy49.py`.
11. **10.–11.11., Google Play vorbereitet** (PR #106 offen, Plan `docs/superpowers/plans/2026-11-10-google-play-store.md`).
    - **Icon** „Mittelkreis“ (Owner-Wahl). Dateien unter `C:\Projekt\BetBoy\output\betboy-store-20261110\final\`
      (Play 512, Web 192/512 und maskierbar, Favicons, Apple 180, Android-Vordergrund 432 + `#16784B`, `betboy.svg`);
      Generator `make_icons.py` (Pillow).
    - **BetBoy-Eintrag** in `C:\Projekt\BmmeStudios\content\apps.mjs` (Projekt ohne Git, Sicherung in
      `backups/2026-11-10-vor-betboy/`):
      - Produktseite und Support sind gebaut, `npm run check` ok.
      - Datenschutz und Nutzungsbedingungen bleiben `status: "draft"` mit `waitingFor`.
      - **Nicht hochgeladen**; das macht der Owner mit `npm.cmd run deploy` (FTP-Passwort).
    - **Offen beim Owner:**
      - Serverstandort (Land des OVH-Rechenzentrums) nennen.
      - App-Adresse festlegen (Vorschlag `betboy.bmmestudios.com`).
      - journald auf 30 Tage begrenzen; Owner sagte „Später“.
      - Bilder von Drittservern: so nennen oder über den eigenen Server ausliefern.
      - Kontotyp im Play-Konto: privat bedeutet 12 Tester während 14 Tagen.
      - Alte API-Schlüssel sperren (Audit K1).
12. **Kleinere Prüfungen:**
    - Tipps vom 09.11. (`output/tipps-20261110/gestern.py`): 7 von 17, Eishockey 0/4, Tennis 2/2.
    - Diagnose „kein Doublebet am 10.11.“ (`output/doublebet-20261110/why_empty.py`): kein Fussball, Tennis ohne
      Quote, NHL nach Mitternacht.
    - Sechs erledigte Neben-Sessions archiviert.

## 3. Release-Verfahren (genau so, Schritt für Schritt)

**Voraussetzungen:** ausdrückliches Owner-OK für Merge und Release, ein grüner CI-Lauf des PR und `match-head-commit`
beim Merge (`gh pr merge N --merge --match-head-commit <sha>`).

1. **Ordner:** `C:\Projekt\BetBoy\output\release-YYYYMMDD-N\` anlegen.
   `release-files.txt` = `git diff --name-only <live-sha> <ziel-sha> | sort`.
2. **`make_gen.py`** leitet den Generator vom letzten Release ab (jetzt `release-20261111-2/gen_deploy49.py`). Es
   ersetzt nur:
   - `OUT`;
   - `PREV` (= live-sha, aktuell `555797bc937f25f45b9614bac41b90a3f05c3fbd`);
   - die Kommentarzeile (Owner-Wortlaut, PR, Datum);
   - bei Bedarf die Modulliste;
   - zusätzliche Asserts vor `print('OFFLINE_RELEASE_IMPORTS=ok')`.

   Es kopiert `run_release.tmpl` mit dem neuen Skriptnamen. Danach `python make_gen.py && python gen_deployNN.py`
   ausführen, das schreibt `deploy.sh`. Zum Schluss `sed "s/__TARGET__/<ziel-sha>/" run_release.tmpl > run_release.sh`.
3. **Asserts pflegen.** Die Asserts im PY-Block sammeln sich seit Oktober an.
   - Entfernt ein PR eine Funktion oder Konstante, muss das Assert ersetzt werden. Beispiele: `NEXT_DAY_MIN_GAMES`
     in -4, `WETTFINDER_MIN_CHANCE_DEFAULT = 50` in -2, `_listed_day` in 20261111-2.
   - Sonst bricht `deploy.sh` nach dem Fast-forward ab: Der Code ist dann neu, die App aber nicht neu gestartet.
4. **Offline-Prüfung lokal**, Pflicht vor dem Hochladen:
   - Temporären Worktree auf das Ziel legen: `git worktree add --detach <W> <ziel-sha>`.
   - PY-Block aus `deploy.sh` ziehen; `/opt/betboy/app` durch den Worktree-Pfad ersetzen,
     `runtime_state/wettfinder_latest.json` durch einen Stub `{"challenge_release_candidates": []}`.
   - Mit `../../.venv/Scripts/python.exe -B` und `PYTHONPATH=<W>` laufen lassen; erwartet wird `OFFLINE_RELEASE_IMPORTS=ok`.
   - Worktree wieder entfernen.
   - Den Python-Aufruf in einer Subshell `( cd $W && … )` starten. Sonst bleibt die Session im Worktree, und das
     Entfernen scheitert unter Windows.
5. **Hochladen:**
   - `tr -d '\r'` auf `deploy.sh` und `run_release.sh` (Kopien im Scratchpad), dann `sha256sum`.
   - Per PowerShell: `scp` nach `/tmp/deploy-YYYYMMDD-N.sh` und `/tmp/run_release-YYYYMMDD-N.sh`, `chmod 755`.
   - `sha256sum` auf dem Server muss gleich sein. Kein `sed` auf dem Server.
6. **Ausrollen:** `ssh betboy-vps "bash /tmp/run_release-YYYYMMDD-N.sh" *> <ordner>\deploy-01.log`.
   - **Wartefenster:** Das Skript wartet bis zu 15 Minuten auf ein Fenster: kein Job aktiv, nächster Shadow-Lauf
     200–560 s entfernt (`/tmp/shadow_gap.sh`, liegt auf dem Server).
   - **Prüfungen von `deploy.sh`:**
     - Root, Ziel-sha;
     - flock `/run/betboy-deploy/deploy.lock`;
     - Remote-URL, Branch `main`, HEAD = PREV, sauberer Baum, keine Hooks, keine ungetrackten `.py`;
     - alle Jobs inaktiv;
     - Backup-Timer inaktiv und disabled;
     - `fetch`, `origin/main` = Ziel, PREV ist Vorfahre;
     - Dateiliste exakt gleich, keine `deploy/systemd/`-, `.sh`- oder Requirements-Änderung;
     - Timer mehr als 150 s entfernt.
   - **Ablauf:** `merge --ff-only`, Offline-Importprüfung, `systemctl restart betboy-app`, Health lokal und öffentlich,
     Timer aktiv, Snapshot-Hashes vor und nach dem Lauf.
   - Erwartet werden am Ende `HEAD=<ziel>`, `NO_NEW_BACKUP=yes`, `UNITS_UNCHANGED=yes` und `DEPLOY_EXIT=0`.
   - Eine Zeile „NativeCommandError … From https://github…“ im Log ist nur `git fetch` auf stderr, das PowerShell
     einrahmt.
7. **Danach:**
   - Live-Seite prüfen (Browser-Pane, `https://vps-a30a123f.vps.ovh.net/`; Streamlit braucht etwa 10–20 s).
   - Wo nötig den nächsten Lauf abwarten. Wartescripte liegen in `output/release-*/verify-*.log` als Muster.
   - Protokoll-PR: `STATUS.md` (Zeilen „Produktion“ und „`origin/main`“) und ein Abschnitt „Release …“ im Audit-Dokument.
8. **Server-Zugriff:**
   - SSH und scp nur über die PowerShell (`ssh betboy-vps`). Inline-Python in PowerShell scheitert am Parser; deshalb
     Skriptdateien hochladen.
   - **Lesend ohne Env:** `sudo -n -u betboy /opt/betboy/venv/bin/python -I /tmp/x.py`.
   - **Mit Env (API-Schlüssel):**
     `sudo -n bash -c "set -a; . /etc/betboy/betboy.env; set +a; cd /opt/betboy/app && exec sudo -n -E -u betboy env PYTHONDONTWRITEBYTECODE=1 nice -n 19 /opt/betboy/venv/bin/python -B /tmp/x.py"`.
   - Schlüsselwerte nie ausgeben.

## 4. Laufende Messungen und Termine

| Wann | Was | Wie |
|---|---|---|
| **12.11. morgens** | Morgen-Zeilen Eishockey, Basketball und E-Sport im Nachtlauf | In `wettfinder_latest.json` prüfen: `next_day_search_date`, `sources.basketball|ice_hockey|esports.next_day.status == "listed"`, Zeilen mit Datum 13.11. in `model_candidates`. Live-Seite lädt (der Lader verwirft sonst das ganze Dokument). |
| bis 30.11. | Fallenfilter: **nur Anzahl ansehen**, keine Trefferquoten | Auf dem Server aus `/opt/betboy/app`: `sudo -n -u betboy /opt/betboy/venv/bin/python -I scripts/trap_filter_measurement.py --count-only` |
| **30.11.** | Fallenfilter auswerten | Dasselbe ohne `--count-only`. Vorab festgelegt (`docs/audits/2026-11-09-fallenfilter-vorab.md`): Fallen = Modell − 1/erste Einstiegsquote ≥ 0,05. Fenster ist die erste Veröffentlichung vom 10.11. bis vor dem 28.11. UTC. Bestanden nur mit **≥ 150 Fallen**, **A** z ≥ 1,645 (seltener als versprochen) **und B** z ≥ 1,645 (seltener als die übrigen). Unter 150: Fenster um je 7 Tage verlängern, nur mit `--count-only`, längstens bis 26.12., sonst unentschieden. Keine Varianten. Ändert sich das Modell, im Bericht nennen. |
| ~28.–30.11. | Formstärke und Hybrid | `scripts/form_strength_measurement.py --since 2026-11-06` (Formstärke gegen Legacy) und `--baseline legacy_form_strength_v1 --candidate dixon_coles_hl365_hybrid` |
| ab 30.11. | Liste ab 70 % auf neuen Tipps | `output/quoten-20261109/hit_by_model.py`, Fenster ab 10.11. setzen (im Skript fest eingetragen 07.10.–10.11.); `/tmp/bb_tfm.py` = `scripts/trap_filter_measurement.py` als Modul |
| nächster Europapokal-Spieltag nach der Pause | Ligastärke im Betrieb messen | `docs/audits/2026-11-05-ligastaerke-europapokal.md` |
| laufend | API-Verbrauch an Wochenenden mit Folgetag | `runtime_state/api_budget.db`, Tabelle `api_budget_events` (Grenzen: api-football 7500/Tag, hockey/basketball 100/Tag, the-odds-api 500/Monat + 20/Tag, oddspapi 250/Monat + 10/Tag) |

**Vorbehalte für die Auswertung am 30.11.:**

- Die App protokolliert beim Öffnen der Seite auch Morgen-Zeilen unter `wettfinder_automatic`. Für Fussball war das
  schon vor dem 10.11. so. Damit liegt die „erste Veröffentlichung“ mancher Tipps einen Tag vor dem Spiel. Das
  passt zur Regel, verschiebt aber die Vorlaufzeit; im Bericht nennen.
- Seit 10.11. gelten neue Regeln: Startwert 70 % beim Regler (das Protokoll bleibt ungefiltert), der Folgetag immer,
  dazu Teamsport und E-Sport morgen. Alles im Bericht nennen.
- Die Abrechnung prüft jetzt alle 3 Stunden. Spiele der letzten Tage sind deshalb am 30.11. weitgehend abgerechnet.

## 5. Offene Aufgaben

### Owner

- Alte API-Schlüssel beim Anbieter sperren oder neu ausstellen. Laut Audit K1 ist der Widerruf nicht belegt, und die
  alten Werte stehen in der öffentlichen Git-Historie.
- Telegram-Token und Chat-ID in `/etc/betboy/betboy.env`.
- **Google Play:**
  - Serverstandort, App-Adresse, journald-Frist und Drittbilder klären (siehe 2.11).
  - Entwicklerkonto: privat oder Organisation.
  - Rechtstexte fachlich prüfen lassen; sie sind keine Rechtsberatung.
  - Website hochladen.
- **Entscheide:**
  - Tennis-Zweitquelle: OddsPapi ist für E-Sport schon angebunden, Gratisplan.
  - Mehr E-Sport-Abdeckung für morgen (kostet PandaScore-Abrufe).
  - Nach dem 30.11.: die Nachquote.

### Codex/Claude (in sinnvoller Reihenfolge)

1. **12.11.: Nachtlauf und Morgen-Zeilen prüfen** (Abschnitt 4).
2. **Tennis morgen** (Schritt 3b, offen).
   - Der Tennis-Scan läuft um 00:05 nur für heute: `scripts/tennis_daily.py` → `_default_scan_date()`, ausgelöst
     über `run_daily_pipeline.py:144`.
   - Die Live-Vorbereitung hat 1800 s (`LIVE_SECONDS_LIMIT`, etwa 10–12 s pro Fall, also rund 150 Fälle) und
     512 MiB. `case_limit` liegt bei 400, `DAILY_SCAN_TIMEOUT_SECONDS` bei 39 Minuten.
   - Ein zweiter Tag braucht einen eigenen Lauf, etwa einen zweiten Timer mit Datumsargument. Das ändert eine Einheit:
     neue Pins in `deploy/bootstrap_server.sh` und `deploy/update_server.sh` und ein Eintrag in der Rekonstruktion
     von `tests/test_context_updater_repair.py`. Der Release-Helper verbietet Einheitsänderungen; dafür braucht es
     einen eigenen, geprüften Weg.
   - **Lader:**
     - `tennis_loader(today=target+1)` zusätzlich aufrufen, Zeilen mit `target_date=next_target` bauen.
     - `tennis_shadow` in `NEXT_DAY_SOURCE_BY_SPORT` aufnehmen, mit `sources.tennis.next_day`.
     - Die Tennisbox heisst heute nur „Heute“: `app.py`, `rail_label`.
   - **Wichtig:** Eine Tennis-Zeile für morgen verwirft heute das ganze Dokument.
3. **E-Sport morgen** deckt nur „die nächsten 6 Spiele je Titel“ ab (`scanners/esports_scanner.py`,
   `MAX_UPCOMING_MATCHES_PER_GAME`). Range-Modus mit nur 3 angereicherten Spielen je Titel. Mehr kostet PandaScore.
4. **Tests, die schon vor diesen Änderungen scheiterten.** Alle scheitern gleich auf dem unveränderten `main`, also
   vor #107–#115. Ursache prüfen, wahrscheinlich teils feste Daten von Sept./Okt. 2026 gegen die echte Uhr.
   - **Unter `gate`:**
     - `test_shared_quote_observations.py::test_active_15k_model_surface_obeys_bound_floor_before_slot_selection[1.2-True]`
     - `test_wettfinder_stage_diagnostics.py::test_production_stages_preserve_document_order_and_private_callbacks`
       (Folgetag-Suche in der erwarteten Reihenfolge)
     - `test_catalog_statistical_selection.py::test_ilves_catalog_survives_real_reader_cards_and_low_price_does_not_flip_direction[1.12]`
       und `[1.8]`
     - `test_team_sport_prices.py::test_forecast_consumer_reuses_exact_cached_price_without_network`
     - `test_api_hockey_prices.py::test_native_conflicting_role_ids_fail_before_any_request`
     - `test_wettfinder_match_context.py::test_normal_wettfinder_does_not_inherit_daily3_probability_floor`; scheitert
       schon auf `00cd65f`, also vor #109.
   - **Unter `BETBOY_TEST_PRICE_POLICY=floor`** zusätzlich 19:
     - `test_team_sport_prices` (6), `test_team_sport_forecasts` (5), `test_esports_prices` (5),
       `test_hockey_esports_clock` (2), `test_wettfinder_stage_diagnostics` (1);
     - dazu 2 in `test_sports_editorial` (`test_second_market_stays_visible_without_repeating_the_whole_match`,
       `test_card_first_level_shows_minimum_odds_and_price_status`).
   - Die CI-Teilmengen (ruff + schnelle Teilmenge, Lader/Publikation/Daily3/15K unter floor und gate) sind grün; sie
     enthalten diese Dateien nicht.
5. **Dauerhaft offene Ergebnisse:** 5 Fussballspiele vom 1. bis 8.11. und 26 Tennisspiele aus September und Oktober
   bekommen kein Ergebnis. Seit #107 belegen sie nur Restplätze. Eine Regel „nach X Tagen ungültig“ wäre eine
   Owner-Entscheidung.
6. **Morgen-Karten zeigen im Wettfinder „Modellstand nicht aktuell belegt“**, gesehen am 11.11. bei Türkei gegen
   Belgien. Ursache: `forecast_highlight_reason` gibt die tägliche Modell-Lebensdauer nur dem Spieltag; nur die
   Doublebet-Vorschau übergibt `match_day`. Prüfen, ob das für die Wettfinder-Liste gewollt ist.
7. **Die Doublebet-Vorschau bleibt oft leer.** Morgen bekommt nur die Kontextprüfungen, die heute übrig lässt
   (3 Nachläufe zu je 20 Spielen).
8. **Cricket-Zeilen verwerfen das ganze Dokument.** `expected_source` kennt Cricket nicht; das war schon so.
9. **Worktrees aufräumen** (Abschnitt 1), nur mit Owner-OK.
10. **Google-Play-Technik**, sobald der Owner die Punkte klärt (Plan PR #106):
    - Subdomain und Caddy;
    - `/.well-known/assetlinks.json` und Web-Manifest;
    - Trusted Web Activity mit Bubblewrap (`com.bmmestudios.betboy`);
    - Prüfung auf dem Handy;
    - Store-Texte.

## 6. Risiken und Lehren

1. **Rücksprung unter `555797b` ist gefährlich.**
   - Ab dem Nachtlauf am 12.11. schreibt der Worker Morgen-Zeilen für Eishockey, Basketball und E-Sport. Der alte
     Lader vor #115 verwirft ein solches Dokument komplett, und die Seite wäre leer bis zum nächsten Lauf.
   - Gilt auch für ein Teil-Release: App und Worker immer auf derselben Version.
2. **Release-Asserts veralten** (Abschnitt 3, Schritt 3). Die lokale Offline-Prüfung ist Pflicht.
3. **Der Auto-Mode-Klassifikator blockt Releases ohne klares „live stellen“.** Nicht umgehen, den Owner fragen.
4. **Folgetag und Kontingent.** API-Football hat Puffer. The Odds API (Tennis) liegt bei 500 pro Monat; bisher wurden
   etwa 250 verbraucht. Hockey und Basketball bei 100 pro Tag.
5. **Quote und Modell.**
   - Die Daten zeigen keinen Vorsprung auf den Buchmacher: Benchmark 0 von 112, Fallen 47 % gegen 61 % versprochen.
   - Getestet und widerlegt: Wetter, Ausfälle und Ruhetage, Startelf. Formstärke bringt einen kleinen Gewinn und ist
     live.
   - Der Owner will 70 % Treffer **und** gute Quoten. Ehrliche Antwort: nur über „ab 70 %“ mit Quoten um 1,28. Ein
     echter Vorsprung wäre erst noch zu finden („Vorsprung suchen“, vorab festgelegt).
6. **Unterbrochene Subagents** hinterlassen ungespeicherte Arbeit in `.claude/worktrees/agent-*`. Vor einem Neustart
   den Worktree prüfen.

## 7. Owner und Zusammenarbeit

- **Owner:** Miroslav, Alleinentwickler, Deutsch (Schweiz, CHF).
  - Er will **kurze, direkte Antworten**: Kernaussage zuerst, einfache Sprache ohne Fachjargon. Bei Rückfragen wie
    „erklär einfach“ noch einfacher.
  - Massstab für Ehrlichkeit ist die Bibel (`PROJEKTBIBEL.md`): keine Gewinnversprechen, Zahlen mit n.
- **Freigaben einzeln:** Merge, Release, API-Abrufe über das Übliche hinaus, Backups und DB-Kopien, Änderungen an
  Einheiten. Kleine, angekündigte API-Proben brauchen ein OK.
- **Regeln aus diesem Zeitraum, zusätzlich zu `AGENTS.md`:**
  - Keine Auswahl nach Quote und keine höhere Mindest-Modellchance als Lösung für die Trefferquote. Die Liste ab
    70 % ist der Startwert des Reglers; der Nutzer kann tiefer schieben.
  - Tipps werden nach Trefferquote und Kalibrierung bewertet, nicht nach ROI.
  - Nur bestehende Quellen nutzen; keine neuen bezahlten Tarife. API-Football ist bezahlt.
  - Open-Meteo nur privat; die App nutzt es nicht.
  - Die interne API von ybets7 nie scrapen.
  - `BETBOY_PRICE_POLICY=gate` nie in Produktion; `BETBOY_RELEASE_MARKET_BENCHMARK` nicht setzen.
  - Morgen-Zeilen sind nie Tipp, 15K-Eintrag, Doublebet-Wahl, Shadow, Evidenz oder Archiv vor ihrem Spieltag. Die
    Vorschauen zeigen nur an.
- **Commits** enden mit `Co-Authored-By: …`, PR-Texte mit der Generated-Zeile; Codex nutzt seine eigene Signatur.

## 8. Wichtige Pfade

| Wo | Was |
|---|---|
| `/opt/betboy/app/runtime_state/wettfinder_latest.json` | Tagesdokument: `model_candidates`, `candidates`, `football_next_day`, `next_day_search_date`, `sources.*.next_day`, `forecast_evidence.settlement` |
| `runtime_state/forecast_evidence.db` | `forecast_rows`, `forecast_quotes` (`entry`/`closing`), `forecast_results` |
| `runtime_state/consumer_tips.db` | `consumer_tip_publications`, `consumer_tips` (`payload_json`) |
| `runtime_state/team_sport_quotes.json` | NHL- und NBA-Quoten, `attempts` (3-h-Sperre), `identity_gaps` |
| `runtime_state/api_budget.db` | Verbrauch je Anbieter und Tag |
| `/var/tmp/bb_lineups/lineups.db` | Startelf-Daten des widerlegten Tests (9107 Spiele), nur für die Analyse |
| `C:\Projekt\BetBoy\output\` | Auswertungen und Release-Belege (nicht in Git): `quoten-20261109`, `aufstellungen-20261109`, `quotenluecke-20261110`, `tipps-20261110`, `doublebet-20261110`, `tennisquoten-20261111`, `betboy-store-20261110`, `release-20261110-1…4`, `release-20261111-1` (nie ausgerollt), `release-20261111-2` |
| `C:\Projekt\BmmeStudios` | Website `bmmestudios.com`, ohne Git; BetBoy-Eintrag in `content/apps.mjs` |
| Timer (Europe/Zurich) | tennis 00:05; esports 03:10; wettfinder 03:35; redcard-history 05:41; redcard-settlement 06:05; quotes 00/03/06/09/12/15/18/21:15; football-shadow alle 10 Minuten |
