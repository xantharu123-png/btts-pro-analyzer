# Übergabe Claude → Codex, vollständig, Stand 13.11.2026

Codex übernimmt am **Montag, 16.11.2026**. Dieses Dokument steht für sich: Es fasst die Übergaben vom 11.11. und vom
13.11. zusammen und ergänzt den Stand vom Freitag, 13.11.2026, 10:33 CET. Die beiden älteren Dokumente
(`2026-11-11-claude-uebergabe-codex.md`, `2026-11-13-claude-uebergabe-codex.md`) bleiben als Verlauf stehen. Wo sie
abweichen, gilt dieses Dokument. Bei Widersprüchen gilt wie immer zuerst der Code, dann `AGENTS.md`.

**Nachtrag 13.11.2026, abends:** Der Owner macht vorerst mit Claude weiter („ich mache im Moment mit dir weiter“).
Die Übernahme durch Codex ist verschoben; dieses Dokument bleibt für den späteren Wechsel gültig. Seither neu: die
Nachtspiel-Abrechnung (`docs/audits/2026-11-13-nachtspiele-abrechnung.md`). Fussballspiele mit Anstoss vor 04:30 Uhr
werden schon im Lauf davor als Evidenz gespeichert, damit sie abgerechnet werden. Den Stand nennt `STATUS.md`.

Inhalt: 0 Kurzfassung · 1 Montag zuerst · 2 Stand · 3 Was die App zeigt · 4 Verlauf · 5 Arbeitsweise ·
6 Release-Verfahren · 7 Server-Zugriff · 8 Messungen und Termine · 9 Offene Aufgaben · 10 Risiken und Lehren ·
11 Regeln · 12 Owner · 13 Pfade · 14 Was nicht geprüft ist

## 0. Kurzfassung zum Einfügen

> Lies zuerst `AGENTS.md`, `STATUS.md` und `docs/handoffs/2026-11-13-claude-uebergabe-codex-komplett.md`.
>
> **Stand 13.11.2026, 10:33 CET:**
> - Produktion läuft auf `9aee28d` (live seit 12.11.2026 08:44 CET, Release 20261112-1).
> - `origin/main` steht auf `5c8000f` plus diesem Übergabe-PR. Nach `9aee28d` kamen nur Doku und das Messskript des
>   Fallenfilters dazu; das Messskript ist nicht live.
> - Offen ist nur PR #106 (Plan Google Play).
> - Alle Server-Dienste liefen am 13.11. mit Exit 0. Der letzte Alarm stammt vom 07.11.
>
> **Am Montag zuerst:** die Prüfliste in Abschnitt 1 (Stand, Wochenende, API-Verbrauch, Fallenfilter zählen).
>
> **Termin:** 30.11.2026, Auswertung von Fallenfilter, Formstärke/Hybrid und Liste ab 70 % (Abschnitt 8).
>
> **Regeln:**
> - Jeder Merge und jedes Release braucht ein ausdrückliches Owner-OK, das Release wörtlich „live stellen“.
> - Releases nur über den No-Backup-Fast-forward-Helfer (Abschnitt 6). Nie hinter `555797b` zurückrollen.
> - Fallenfilter bis zur Auswertung nur mit `--count-only`. Keine Trefferquoten ansehen.
> - Preisjagd gegen Buchmacher nicht messen, nicht bauen, nicht erneut vorschlagen (Owner 12.11.).
> - Der Owner will kurze, direkte Antworten in einfachem Deutsch, Kernaussage zuerst.

## 1. Montag, 16.11.2026: zuerst das

Alles hier ist nur lesend. Die Helfer liegen in `C:\Projekt\BetBoy\output\uebergabe-20261113\` (nicht in Git).

1. **Einstieg.** `git fetch origin`, eigenen Worktree anlegen (Abschnitt 5), `STATUS.md` lesen.
2. **Stand auf dem Server.** In der PowerShell:

   ```powershell
   $O = "C:\Projekt\BetBoy\output\uebergabe-20261113"
   scp -q "$O\stand.sh" "$O\stand_tag.sh" "$O\stand_heute.py" "$O\api_budget_stand.py" betboy-vps:/tmp/
   ssh betboy-vps "bash /tmp/stand.sh; bash /tmp/stand_tag.sh 2026-11-13"
   ```

   Erwartet wird:
   - `LIVE: 9aee28d`.
   - Jede Kerneinheit mit `success` und Exit 0: app (aktiv), wettfinder, quotes, tennis, esports, football-shadow,
     redcard-history, redcard-settlement, backup-retention.
   - Unter `FAILED` genau die 8 alten Einmal-Einheiten vom September (Abschnitt 2). Jede weitere ist neu.
   - Alarme: 14 Zeilen, die letzte vom 07.11. (`2026-11-07T19:52:16+00:00`, football-shadow). Mehr Zeilen heisst
     neuer Alarm; dann die neuen Zeilen in `runtime_state/ops_alerts.jsonl` lesen.
   - Platte um 51 %.
3. **Wochenende nachsehen.** Claude hat den 14. und 15.11. nicht beobachtet.
   - Nachtläufe vom 14., 15. und 16.11.: tennis 00:05, esports 03:10, wettfinder 03:35. Die Ausgabe von `stand.sh`
     zeigt nur den letzten Lauf je Einheit; ein Fehler an einem früheren Tag steht als Zeile in `ops_alerts.jsonl`.
   - **API-Verbrauch je Tag** steht in der Ausgabe von `stand_tag.sh` (Grenze, geschätzter Rest, Entscheide).
     - `api-football`: Grenze 7500 pro Tag. Es ist das erste Wochenende mit „Folgetag immer“ (PR #112). Für den
       14.11. listete der Lauf schon 204 Fussballzeilen.
     - `api-sports-ice_hockey`: Grenze 100 pro Tag. **Am 12.11. waren 83 verbraucht** (Abschnitt 10, Risiko 4).
       Prüfen, ob am Wochenende Abrufe mit `BLOCKED` stehen.
4. **Fallenfilter zählen, nur Anzahl** (Befehle in Abschnitt 8). Stand 13.11. 10:01: 58 abgerechnete Tipps, 3 Fallen,
   4 übrige mit Quote, 51 ohne Quote.
5. **Live-Seite ansehen:** `https://vps-a30a123f.vps.ovh.net/` (Streamlit braucht 10 bis 20 Sekunden). Wettfinder
   zeigt heute und morgen, Doublebet zeigt heute und die Vorschau für morgen, 15K lädt.
6. **Melden und nachziehen.** Dem Owner das Ergebnis in wenigen Sätzen melden. Am Ende der Sitzung den Abschnitt
   „Stand“ in `STATUS.md` ersetzen.

Bei Bedarf das Journal einer Einheit lesen:
`ssh betboy-vps "sudo -n journalctl -u betboy-wettfinder.service --since '2026-11-14' --no-pager | tail -60"`.

## 2. Stand am 13.11.2026 um 10:33 CET

### Code und Server

| Bereich | Stand |
|---|---|
| Produktion (VPS `betboy-vps`, `/opt/betboy/app`) | `9aee28df1b6efc9b9bfe097cb0598a4c7f53e765`, live seit 12.11.2026 08:44 CET, Release 20261112-1 |
| `origin/main` | `5c8000f` (PR #123) plus dieser Übergabe-PR |
| Unterschied Produktion → `main` | nur Doku, dazu `scripts/trap_filter_measurement.py` und `tests/test_trap_filter_measurement.py` (PR #123). Kein App-Code |
| Offene PRs | #106 „Plan: BetBoy in den Google Play Store“ (nur Doku) |
| Dienste 13.11. | alle `success`/Exit 0: tennis 00:11, esports 03:10, wettfinder 03:51, backup-retention 04:21, redcard-history 05:41, redcard-settlement 06:05, quotes 09:15, football-shadow 10:32; app aktiv |
| Alarme | 14 Einträge in `runtime_state/ops_alerts.jsonl`, der letzte vom 07.11. 20:52 CET; seither keiner |
| Fehlgeschlagene Einheiten | 8 alte Einmal-Einheiten vom 14. bis 19.09.2026: `betboy-release-afc8a10-20260918`, `-20260918b`, `betboy-release-context-c64218b-20260918`, `betboy-release-product-53f2e2c-20260919`, `betboy-storage-repair-20260919`, `codex-context-memory-repair-20260914`, `codex-tennis-cpu-check-20260915`, `codex-tennis-identity-check-20260915`. Keine Kerneinheit, Altlast |
| Platte | 38 GB, 20 GB belegt, 51 % |
| Backup-Timer | `disabled`/`inactive`, so vom Owner gewollt. Nur `backup-retention` läuft |
| Telegram-Alarm | Token und Chat-ID fehlen in `/etc/betboy/betboy.env` (Owner). Alarme landen nur im Journal und in `ops_alerts.jsonl` |
| Geplante Claude-Aufgaben | keine aktiv (eine alte Einmal-Aufgabe vom 01.11. ist ausgeschaltet) |

### Daten des Tages

| Bereich | Stand 13.11., 10:33 |
|---|---|
| Tagesdokument | Fussball 66 Zeilen heute und 204 morgen; Basketball 6 heute, ohne Quote; Eishockey 6 Zeilen morgen (3 NHL-Spiele, mit Quote); E-Sport 2 heute und 1 morgen |
| Team-Quoten | 32 Quoten (26 über API-Hockey, 6 über NHL), keine Fehler, keine Lücken, nichts zurückgestellt |
| Doublebet heute | Serbien gegen Deutschland, Team-2-Gesamttore Unter, Median-Quote 1,86, Modell 70 % |
| Doublebet Vorschau morgen | Norwegen gegen Wales, Team-1-Gesamttore Unter, Median-Quote 1,91, Modell 75 % |
| Fallenfilter (10:01, nur Anzahl) | 58 abgerechnete Tipps: 3 Fallen, 4 übrige mit Quote, 51 ohne Quote. Nötig sind 150 Fallen |

### API-Verbrauch (abgeschlossene Abrufe je Tag)

| Tag | api-football (7500) | Eishockey (100) | Basketball (100) | The Odds API (20/Tag) | OddsPapi (10/Tag) |
|---|---:|---:|---:|---:|---:|
| Sa 07.11. | 3575, dazu 156 gesperrt | 7 | 1 | 3 | 5 |
| So 08.11. | 2240 | 22 | 4 | 4 | 4 |
| Mo 09.11. | 1055 | 7 | 0 | 0 | 0 |
| Di 10.11. | 223 | 16 | 0 | 3 | 3 |
| Mi 11.11. | 395 | 47 (+2 fehlgeschlagen) | 5 | 6 | 5 |
| Do 12.11. | 809 | **79 (+4 fehlgeschlagen), Rest 17** | 8 | 6 | 4 |
| Fr 13.11. bis 09:15 | 534 | 34 (+4 fehlgeschlagen), Rest 62 | 2 | 2 | 5 |

- Monatskontingente im November, Stand 13.11.: The Odds API 444 von 500 übrig, OddsPapi rund 200 von 250 übrig.
  Die Angabe „etwa 250 verbraucht“ in der Übergabe vom 11.11. war falsch.
- Der 07.11. war der letzte volle Liga-Samstag, noch vor „Folgetag immer“. Die 156 gesperrten Abrufe an diesem Tag
  hat Claude nicht untersucht.

### Checkouts

- **Hauptcheckout** `C:\Projekt\BetBoy\betboy-app`: steht auf `c5a6264 [main]`, trägt fremdes WIP und liegt hinter
  `origin/main`. Getrackte Dateien nicht anfassen. Nur die Kopien `STATUS.md` und `AGENTS.md` dort nach jedem Merge
  aus `origin/main` erneuern (Abschnitt 5).
- **Claude-Arbeitsworktree:** `.worktrees/claude-shadow-void-verschoben`, nach dem Merge detached auf `origin/main`.
- **Übrige Worktrees:** 82 Einträge in `git worktree list`, 133 Remote-Branches, davon 129 in `origin/main` gemergt.
  Aufräumen nur mit Owner-OK.
- **Auf dem Server unter `/tmp`:** rund 340 Einträge, darunter alte Leseskripte früherer Sitzungen. Harmlos.
  **`/tmp/shadow_gap.sh` braucht das Release-Verfahren; nicht löschen.**

## 3. Was die App zeigt

| Seite | Verhalten |
|---|---|
| **Wettfinder** | Regler „Mindest-Modellchance“ startet bei 70 % (#109); der Nutzer kann tiefer schieben. Die Liste zeigt immer heute und morgen (#112, #115): Fussball über `football_next_day`, dazu Eishockey, Basketball und E-Sport. Tennis und Cricket nur heute |
| **Doublebet** | Bis zu drei Wetten mit Median-Quote 1,80 bis 2,20, gewählt nach der höchsten Summe der Modellwahrscheinlichkeiten (Policy `doublebet-odds-around-2-most-probable-v16`). Seit v15 mit Eishockey, seit v16 mit A-Länderspielen ohne Verletzungsdaten. Dazu „Morgen (Vorschau)“, nur Anzeige; Vormerken erst am Spieltag (#114) |
| **15K** | Höchstens fünf Spiele, je Spiel der wahrscheinlichste Markt mit Leg-Quote ab 1,25. „Morgen“ zeigt eine Vorschau ohne Ticketformular (#114) |
| **Tipps** | Öffentlich höchstens drei gleichzeitig. Sie rücken nach jedem Quotenlauf nach. Tennis-Siegertipps erst ab 60 % Modellchance |
| **Quoten** | Die App zeigt keine Buchmacherquoten. Im Hintergrund gilt nur die 1,20-Grenze (dreistufig, Median der Buchmacher) |
| **Ergebnisse** | Abrechnung im Nachtlauf und in jedem Quotenlauf, also alle 3 Stunden, neueste Spiele zuerst (#107) |
| **Eishockey-Quoten** | NHL-Spiele bekommen seit #111 Quoten. Basketball (EuroLeague) bekommt nie eine, bewusst offen (Abschnitt 9) |

**Morgen-Zeilen** sind nur Anzeige: nie Tipp, 15K-Eintrag, Doublebet-Wahl, Shadow, Evidenz oder Archiv vor ihrem
Spieltag.

**Ablauf in einem Satz:** Der Worker (`wettfinder_automation.py`, Einheit `betboy-wettfinder`) schreibt nachts das
Tagesdokument `runtime_state/wettfinder_latest.json`. Die App (`app.py`, Streamlit, `betboy-app`) lädt es über den
Lader. Der Quotenlauf (`betboy-quotes`, alle 3 Stunden) prüft Preise, lässt Tipps nachrücken und rechnet ab. Mehr in
`ARCHITECTURE.md`.

## 4. Verlauf vom 09. bis 13.11.2026

### Merges und Releases

Alle Releases liefen über den Helfer aus Abschnitt 6. Owner-Freigaben stehen in den Protokollen.

| Merge | PR | Commit | Inhalt | Live |
|---|---|---|---|---|
| 09.11. 13:10 | #105 | `5b14359` | Startelf-Test widerlegt; Fallenfilter vorab festgelegt, mit Messskript | Messung, keine App-Änderung |
| 10.11. 11:41 | #107 | `5c3ada9` | Ergebnisse auch im Quotenlauf | Release 20261110-1, 11:43 |
| 10.11. 12:36 | #108 | `00cd65f` | Protokoll | – |
| 10.11. 14:27 | #109 | `fa7205f` | Liste ab 70 % | Release 20261110-2, 14:32 |
| 10.11. 15:06 | #110 | `09a45bd` | Protokoll | – |
| 10.11. 16:30 | #111 | `bae99ee` | NHL-Spielplan ab Vortag | Release 20261110-3, 16:32 |
| 10.11. 21:03 | #112 | `544c299` | Folgetag immer | Release 20261110-4, 21:04 |
| 10.11. 21:47 | #113 | `c835ec4` | Protokoll | – |
| 11.11. 08:40 | #114 | `88b70d5` | Morgen-Vorschau für Doublebet und 15K | mit #115 |
| 11.11. 08:57 | #115 | `555797b` | Morgen für Eishockey, Basketball, E-Sport | Release 20261111-2, 09:02 |
| 11.11. 09:13 | #116 | `95d2a97` | Protokoll | – |
| 11.11. 09:44 | #117 | `a7e6000` | Übergabe vom 11.11. | – |
| 11.11. 14:13 | #118 | `4f00d0f` | Doublebet mit Eishockey, Policy v15 | Release 20261111-3, 14:15 |
| 11.11. 14:43 | #119 | `da2224d` | Protokoll | – |
| 12.11. 08:43 | #120 | `9aee28d` | Doublebet mit A-Länderspielen, Policy v16 | Release 20261112-1, 08:44 |
| 12.11. 09:22 | #121 | `2ff5528` | Protokoll | – |
| 13.11. 08:47 | #122 | `2b032aa` | Übergabe vom 13.11., Vorsprung-Analyse | – |
| 13.11. 10:30 | #123 | `5c8000f` | Fallenfilter: Einstiegsquote über die Auswahl | **nicht live** |

Das vorbereitete Release 20261111-1 (nur #114) wurde nie ausgerollt.

### Wo der Code dazu liegt

- **Ergebnisse im Quotenlauf (#107):** `forecast_evidence_settlement.py` (`RECENT_KICKOFF_WINDOW = 72 h`, `_rotated`,
  `_budgeted_events`); `wettfinder_automation.py` (`_settle_forecast_evidence`, `_quotes_run_settlement`). Protokoll
  `docs/audits/2026-11-10-abrechnung-quotenlauf.md`.
- **Liste ab 70 % (#109):** `app.py`, `WETTFINDER_MIN_CHANCE_DEFAULT = 70`. Rückblick 07.10. bis 09.11.: ab 70 %
  trafen 72,3 %, bei 40 Tipps pro Tag und Quote-Median 1,28. Protokoll `docs/audits/2026-11-10-liste-ab-70.md`.
- **NHL-Spielplan (#111):** `team_sport_prices.refresh_team_sport_prices`. Die NHL führt Spiele unter dem
  nordamerikanischen Datum; vorher fehlten Abendspiele nach 00:00 UTC. Sperre `REFRESH_AFTER = 3 h` je Spiel.
  Protokoll `docs/audits/2026-11-10-nhl-spielplan-vortag.md`.
- **Folgetag immer (#112):** `NEXT_DAY_MIN_GAMES` entfernt. Protokoll `docs/audits/2026-11-10-folgetag-immer.md`.
- **Morgen-Vorschau (#114):** `daily3_selection.daily3_choices(target_day=…)`, `doublebet_preview_choices`;
  `forecast_analysis.forecast_highlight_reason(match_day=…)`; `daily3_ui.render_doublebet_preview`;
  `wettfinder_automation.build_next_day_challenge_preview`; `challenge_15k._render_next_day_challenge_preview`.
  Protokoll `docs/audits/2026-11-11-morgen-vorschau-doublebet-15k.md`.
- **Morgen für Teamsport und E-Sport (#115):** `ev_signal_sources.NEXT_DAY_SOURCE_BY_SPORT`,
  `automated_next_day_sports`, `listed_next_day_signal(decided_at=…)`; im Lader `listed_next_day_row` (eine
  ungültige Morgen-Zeile fällt einzeln weg); Archivschutz in `tip_publication.py`. Protokoll
  `docs/audits/2026-11-11-morgen-teamsport-esport.md`.
- **Doublebet mit Eishockey (#118, v15):** `DOUBLEBET_RESEARCH_SPORTS`,
  `forecast_highlight_reason(admit_research_sports=)`. Team-Quoten werden zuerst für Spiele mit Modell geholt.
  Protokoll `docs/audits/2026-11-11-doublebet-eishockey.md`.
- **Doublebet mit A-Länderspielen (#120, v16):**
  `forecast_analysis.football_context_highlight_reason(…, uncovered_injuries_ok=False)` überspringt nur die
  ausdrückliche Meldung „nicht abgedeckt“. `daily3_selection._explanation` setzt den Schalter nur für
  `model_scope == NATIONAL_SCOPE` (`senior_national_pooled`). Tests `tests/test_doublebet_laenderspiele.py` (12).
  Zurücknehmen: `uncovered_injuries_ok=False` im Aufruf in `_explanation`. Protokoll
  `docs/audits/2026-11-12-doublebet-laenderspiele.md`.
- **Fallenfilter-Zuordnung (#123):** `scripts/trap_filter_measurement.py` (`selection_entry_quotes`; `load` gibt
  jetzt vier Werte zurück; `tip_records(…, forecast_quotes)`), Tests `tests/test_trap_filter_measurement.py` (8).
  Nachtrag in `docs/audits/2026-11-09-fallenfilter-vorab.md`.

### Analysen ohne Code-Änderung

- **09.11., Quotenanalyse** (`output/quoten-20261109/`): Die Trefferquote der Tipps folgt der Buchmacherquote
  (1,20 bis 1,30 → 71 %, 1,50 bis 1,70 → 59 %, ab 2,00 → 32 %). Wo das Modell mindestens 5 Punkte über 1/Quote lag
  (566 Tipps), versprach es 61,3 % und traf 47,3 %.
- **09.11., Startelf-Test widerlegt** (`docs/audits/2026-11-09-aufstellungen-widerlegt.md`): 9107 Ligaspiele,
  β +0,0063 (SE 0,0043), die Abbruchregel griff.
- **10.11., Quotenlücke** (`output/quotenluecke-20261110/ERGEBNIS.md`): Die Einstiegsquote speichert nur der
  Nachtlauf (`record_forecast_run`). Die Quotenläufe speichern nur Schlussquoten in der letzten Stunde. 1666 von
  4920 Tipps hatten keine Quote. Die Idee „Nachquote“ wartet bis nach dem 30.11. (Owner „Ja, warten“).
- **11.11., Tennisquoten-Probe** (`output/tennisquoten-20261111/ERGEBNIS.md`): The Odds API deckte nur die WTA
  Finals ab. Die Zuordnung der App ist korrekt.
- **12.11., Vorsprung-Analyse** (`docs/audits/2026-11-12-vorsprung-gegen-buchmacher.md`): Auf 6365 abgerechneten
  Auswahlen ist das Modell in jeder Marktart schlechter als die faire Marktchance, nur bei Ecken gleichauf. Von
  sechs Ideen zeigt nur die Preisjagd ohne Modell ein Plus (18 686 Wetten, +3,5 % [+1,2; +5,9]), in der Saison
  2025/26 aber ein Minus. **Owner: „Nein, lassen“.**
- **13.11., Fallenfilter:** Die Messung fand keinen Tipp mit Quote. Ursache und Berichtigung in Abschnitt 8.
- **10./11.11., Google Play vorbereitet** (PR #106 offen): Icon „Mittelkreis“ unter
  `output/betboy-store-20261110/final/`; BetBoy-Eintrag in `C:\Projekt\BmmeStudios\content\apps.mjs`, nicht
  hochgeladen.

## 5. Arbeitsweise

1. **Eigener Worktree, eigener Branch.** Zum Beispiel
   `git worktree add .worktrees/codex-<thema> -b codex/<thema> origin/main`. Nie im Hauptcheckout arbeiten, nie
   fremde Worktrees anfassen, nie `git stash` ohne Tag.
2. **Python.** Die venv liegt im Hauptcheckout: `..\..\.venv\Scripts\python.exe` aus dem Worktree (Python 3.12).
   Das System-Python hat weder pytest noch ruff.
3. **Tests.** Zuerst ein roter Test, dann grün. Gezielt laufen lassen:
   `..\..\.venv\Scripts\python.exe -m pytest tests/<datei>.py -q`, dazu
   `..\..\.venv\Scripts\python.exe -m ruff check .`. Die Vollsuite braucht auf Windows rund 1,5 Stunden.
4. **CI** (`.github/workflows/tests.yml`) läuft bei jedem Push:
   - „ruff + schnelle Teilmenge“ (neun Testdateien);
   - „Lader/Publikation/Daily3/15K“ unter `floor` und unter `gate`;
   - „Vollsuite Hälfte A/B“ nur von Hand über `workflow_dispatch`.

   Grüne CI heisst also nicht, dass die Tests einer geänderten Datei gelaufen sind. Die Tests des Fallenfilters
   zum Beispiel laufen in keinem der automatischen Jobs.
5. **Commit und PR.** Commit-Text aus einer Datei (`git commit -F datei`), PR mit `gh pr create --body-file datei`.
   Ein Here-String in der PowerShell scheiterte am 12.11. und liess einen leeren Branch zurück. Nach `cd` in einen
   Ordner ausserhalb des Repos scheitert `gh`.
6. **Merge** erst nach grüner CI und Owner-OK:
   `gh pr merge N --merge --match-head-commit <sha>`.
7. **Nach dem Merge:**
   - `git fetch origin`, Worktree auf `origin/main` setzen, lokalen Branch löschen.
   - Die Kopien im Hauptcheckout erneuern, in Git Bash aus dem Worktree:
     `git show origin/main:STATUS.md > C:/Projekt/BetBoy/betboy-app/STATUS.md`, ebenso `AGENTS.md`. Nicht mit `>`
     in der PowerShell 5.1; die schreibt UTF-16.
8. **`STATUS.md`** am Anfang lesen und am Ende den Abschnitt „Stand“ ersetzen, nicht anhängen.
9. **Berichte** nach `docs/audits/<datum>-<thema>.md`, Zahlen immer mit n, Intervall und Herkunft.
10. **Zeilenenden.** Im Arbeitsbaum stehen manche Dateien mit CRLF (`STATUS.md`), das Repo speichert LF. Beim
    Bearbeiten das vorhandene Zeilenende behalten. Alles, was auf den Server geht, vorher mit `tr -d '\r'` säubern.

## 6. Release-Verfahren (genau so, Schritt für Schritt)

**Voraussetzungen:** ausdrückliches Owner-OK für Merge und Release („live stellen“), ein grüner CI-Lauf des PR und
`--match-head-commit` beim Merge.

**Für das nächste Release:**

- Letzter Generator: `C:\Projekt\BetBoy\output\release-20261112-1\gen_deploy51.py`, abgeleitet durch `make_gen.py`
  im selben Ordner. Dort liegen auch `run_release.tmpl`, `build_offline_check.py` und `offline_check.py`.
- `PREV` ist `9aee28df1b6efc9b9bfe097cb0598a4c7f53e765`.
- Die Dateiliste enthält dann auch `scripts/trap_filter_measurement.py` und
  `tests/test_trap_filter_measurement.py` aus PR #123. Damit kommt das berichtigte Messskript auf den Server.
- Die Asserts im PY-Block prüfen die Policy v16 und `uncovered_injuries_ok`. Ändert ein PR die Policy oder diese
  Funktion, die Asserts mitziehen.

**Schritte:**

1. **Ordner** `C:\Projekt\BetBoy\output\release-YYYYMMDD-N\` anlegen.
   `release-files.txt` = `git diff --name-only <live-sha> <ziel-sha> | LC_ALL=C sort`. Die Liste muss in
   C-Reihenfolge sortiert sein (Grossbuchstaben zuerst), sonst bricht `deploy.sh` beim Vergleich ab.
2. **`make_gen.py`** leitet den neuen Generator vom letzten ab. Es ersetzt nur `OUT`, `PREV`, die Kommentarzeile
   (Owner-Wortlaut, PR, Datum), bei Bedarf die Modulliste und zusätzliche Asserts vor
   `print('OFFLINE_RELEASE_IMPORTS=ok')`. Es kopiert `run_release.tmpl` mit dem neuen Skriptnamen. Danach
   `python make_gen.py && python gen_deployNN.py` ausführen; das schreibt `deploy.sh`. Zum Schluss
   `sed "s/__TARGET__/<ziel-sha>/" run_release.tmpl > run_release.sh` (lokal, nicht auf dem Server).
3. **Asserts pflegen.** Sie sammeln sich seit Oktober an. Entfernt ein PR eine Funktion oder Konstante, muss das
   Assert ersetzt werden. Sonst bricht `deploy.sh` nach dem Fast-forward ab: Der Code ist dann neu, die App aber
   nicht neu gestartet.
4. **Offline-Prüfung lokal, Pflicht vor dem Hochladen:**
   - Temporären Worktree auf das Ziel legen: `git worktree add --detach <W> <ziel-sha>`.
   - PY-Block aus `deploy.sh` ziehen; `/opt/betboy/app` durch den Worktree-Pfad ersetzen,
     `runtime_state/wettfinder_latest.json` durch einen Stub `{"challenge_release_candidates": []}`.
   - Mit `../../.venv/Scripts/python.exe -B` und `PYTHONPATH=<W>` laufen lassen. Erwartet wird
     `OFFLINE_RELEASE_IMPORTS=ok`.
   - Den Python-Aufruf in einer Subshell `( cd $W && … )` starten. Sonst bleibt die Sitzung im Worktree, und das
     Entfernen scheitert unter Windows.
   - Worktree wieder entfernen.
5. **Hochladen:**
   - `tr -d '\r'` auf Kopien von `deploy.sh` und `run_release.sh`, dann `sha256sum`.
   - In der PowerShell: `scp` nach `/tmp/deploy-YYYYMMDD-N.sh` und `/tmp/run_release-YYYYMMDD-N.sh`, `chmod 755`.
   - `sha256sum` auf dem Server muss gleich sein. Kein `sed` auf dem Server.
6. **Ausrollen:** `ssh betboy-vps "bash /tmp/run_release-YYYYMMDD-N.sh" *> <ordner>\deploy-01.log`.
   - **Wartefenster:** Das Skript wartet bis zu 15 Minuten auf ein Fenster: kein Job aktiv, nächster Shadow-Lauf
     200 bis 560 Sekunden entfernt (`/tmp/shadow_gap.sh` auf dem Server).
   - **Prüfungen von `deploy.sh`:** Root und Ziel-sha; flock `/run/betboy-deploy/deploy.lock`; Remote-URL, Branch
     `main`, HEAD = PREV, sauberer Baum, keine Hooks, keine ungetrackten `.py`; alle Jobs inaktiv; Backup-Timer
     inaktiv und disabled; `fetch`, `origin/main` = Ziel, PREV ist Vorfahre; Dateiliste exakt gleich; keine Änderung
     unter `deploy/systemd/`, an `.sh` oder an den Requirements; Timer mehr als 150 Sekunden entfernt.
   - **Ablauf:** `merge --ff-only`, Offline-Importprüfung, `systemctl restart betboy-app`, Health lokal und
     öffentlich, Timer aktiv, Snapshot-Hashes vor und nach dem Lauf.
   - **Erwartet am Ende:** `HEAD=<ziel>`, `NO_NEW_BACKUP=yes`, `UNITS_UNCHANGED=yes`, `DEPLOY_EXIT=0`.
   - Eine Zeile „NativeCommandError … From https://github…“ im Log ist nur `git fetch` auf stderr, das die
     PowerShell einrahmt.
7. **Danach:**
   - Live-Seite prüfen. Wo nötig den nächsten Lauf abwarten; Muster für Wartescripte liegen in
     `output/release-*/verify-*.log`.
   - Protokoll-PR: `STATUS.md` (Zeilen „Produktion“ und „`origin/main`“) und ein Abschnitt „Release …“ im
     Audit-Dokument des PR.

**Grenzen des Helfers:** Er verbietet Änderungen an Einheiten, an `.sh` und an den Requirements. Dafür braucht es
einen eigenen, geprüften Weg und ein eigenes Owner-OK (`AGENTS.md`, „Betrieb seit 25.10.2026“).

## 7. Server-Zugriff

- **Nur über die PowerShell:** `ssh betboy-vps`, `scp … betboy-vps:/tmp/`. Inline-Python in der PowerShell
  scheitert am Parser. Deshalb Skriptdateien hochladen, vorher ohne `\r`.
- **Lesend ohne Env:** `sudo -n -u betboy nice -n 19 /opt/betboy/venv/bin/python -I /tmp/x.py`. Im Skript
  `sys.path.insert(0, "/opt/betboy/app")` setzen; `-I` ignoriert `PYTHONPATH` und das Arbeitsverzeichnis.
  Datenbanken mit `sqlite3.connect("file:…?mode=ro", uri=True)` öffnen.
- **Der ssh-Benutzer kann nicht nach `/opt/betboy/app` wechseln.** Stattdessen
  `sudo -n -u betboy git -C /opt/betboy/app …` oder `sudo -n -u betboy bash -c 'cd /opt/betboy/app && …'`.
- **Mit Env (API-Schlüssel), nur mit Owner-OK für den Abruf:**
  `sudo -n bash -c "set -a; . /etc/betboy/betboy.env; set +a; cd /opt/betboy/app && exec sudo -n -E -u betboy env PYTHONDONTWRITEBYTECODE=1 nice -n 19 /opt/betboy/venv/bin/python -B /tmp/x.py"`.
- **Schlüsselwerte nie ausgeben**, auch nicht gekürzt.
- **`forecast_quotes` hat keinen Index auf `forecast_id`.** Quoten in einem Durchgang lesen, nie `EXISTS` je Zeile.
- **Nichts ändern ohne Auftrag:** keine Backups, keine Kopien der Produktions-Datenbanken, keine API-Scans, kein
  `systemctl`-Eingriff, kein `sed` auf dem Server.

## 8. Messungen und Termine

| Wann | Was | Wie |
|---|---|---|
| Mo 16.11. | Wochenende nachsehen: Dienste, Alarme, API-Verbrauch | Abschnitt 1 |
| Mo 16.11., dann wieder nach dem 22.11. | Fallenfilter zählen, nur Anzahl | unten |
| laufend | Doublebet v15/v16 beobachten | Anzahl Auswahlen und Trefferquote gegen 50 % (`docs/audits/2026-11-03-doublebet.md`). Länderspiele ohne Verletzungsdaten sind ein bewusstes Risiko |
| laufend | API-Hockey nahe an der Tagesgrenze | Abschnitt 10, Risiko 4 |
| nächster Europapokal-Spieltag nach der Pause | Ligastärke im Betrieb messen | `docs/audits/2026-11-05-ligastaerke-europapokal.md` |
| ~28. bis 30.11. | Formstärke und Hybrid | `scripts/form_strength_measurement.py --since 2026-11-06` (Formstärke gegen Legacy) und `--baseline legacy_form_strength_v1 --candidate dixon_coles_hl365_hybrid`. Regeln in `docs/audits/2026-11-06-formstaerke-umsetzung.md` und `2026-11-07-formstaerke-eingeschaltet.md` |
| **30.11.** | Fallenfilter auswerten | unten |
| ab 30.11. | Liste ab 70 % auf neuen Tipps | `output/quoten-20261109/hit_by_model.py`; das Fenster ist im Skript fest auf 07.10. bis 10.11. eingetragen und muss auf „ab 10.11.“ gesetzt werden |
| nach dem 30.11. | Nachquote, nur wenn der Fallenfilter besteht | Owner „Ja, warten“ (`output/quotenluecke-20261110/ERGEBNIS.md`) |

**Zur Länderspielpause:** Sie dauert laut Vorab-Dokument bis etwa 17.11. Das Wochenende 14./15.11. ist deshalb kein
volles Liga-Wochenende; das erste liegt voraussichtlich am 21./22.11. In `STATUS.md` und in der Übergabe vom 13.11.
stand dazu „erstes Liga-Wochenende“ für den 14./15.11.; das war ungenau.

### Fallenfilter

**Regel** (`docs/audits/2026-11-09-fallenfilter-vorab.md`, mit Nachtrag vom 13.11.2026):

- **Falle:** Modellwahrscheinlichkeit der ersten Veröffentlichung minus 1 / Einstiegsquote ≥ 0,05.
- **Einstiegsquote seit 13.11.** (Owner „B“): die früheste gespeicherte Quote mit `kind = entry` über alle Prognosen
  mit demselben `event_key`, `market_key` und `selection`. Vorher zählte nur die `forecast_id` des Tipps; Tipps vom
  Vortag tragen keine, deshalb fand die Messung 0 Tipps mit Quote.
- **Fenster:** erste Veröffentlichung vom 10.11.2026 00:00 UTC bis vor 28.11.2026 00:00 UTC.
- **Bestanden** nur mit mindestens 150 abgerechneten Fallen, **A** z ≥ 1,645 (Fallen treffen seltener als
  versprochen) **und B** z ≥ 1,645 (Fallen treffen seltener als die übrigen Tipps mit Quote).
- **Keine Varianten**, egal wie der Test ausgeht.

**Zählen, solange auf dem Server das alte Skript liegt** (es zeigt weiter 0 Tipps mit Quote). In der PowerShell:

```powershell
$O = "C:\Projekt\BetBoy\output\uebergabe-20261113"
scp -q "$O\tfm_new_20261113.py" "$O\tfm_count_20261113.py" betboy-vps:/tmp/
ssh betboy-vps "sha256sum /tmp/tfm_new_20261113.py; sudo -n -u betboy nice -n 19 /opt/betboy/venv/bin/python -I /tmp/tfm_count_20261113.py"
ssh betboy-vps "rm -f /tmp/tfm_new_20261113.py /tmp/tfm_count_20261113.py"
```

- `tfm_new_20261113.py` ist `scripts/trap_filter_measurement.py` von `origin/main` `5c8000f`, sha256
  `54e972b16fca8dbf3459c44aabc36829779f76878f6733cbdbb7a3309673b1ec`. Ändert sich das Skript auf `main`, die Kopie
  in Git Bash neu ziehen: `git show origin/main:scripts/trap_filter_measurement.py > <datei>`.
- Der Starter `tfm_count_20261113.py` ruft `main(["--count-only"])` für das Fenster auf und danach eine Gegenprobe
  für 07.10. bis 09.11., ebenfalls nur mit Anzahlen.
- **Nach dem nächsten Release** reicht:
  `ssh betboy-vps "sudo -n -u betboy bash -c 'cd /opt/betboy/app && /opt/betboy/venv/bin/python -I scripts/trap_filter_measurement.py --count-only'"`.

**Zählungen bisher:**

| Wann | abgerechnet | Fallen | übrige mit Quote | ohne Quote |
|---|---:|---:|---:|---:|
| 13.11. 08:32, alte Zuordnung | 58 | 0 | 0 | 58 |
| 13.11. 10:01, neue Zuordnung | 58 | 3 | 4 | 51 |
| Gegenprobe 07.10. bis 09.11., neue Zuordnung | 5012 | 643 | 2802 | 1567 |

**Auswertung am 30.11., in dieser Reihenfolge:**

1. **Zuerst nur zählen** (`--count-only`).
2. **150 Fallen oder mehr:** einmal ohne `--count-only` auswerten. Das Ergebnis mit allen Zahlen nach
   `docs/audits/` schreiben.
3. **Weniger als 150 Fallen: nicht auswerten.** Das Skript druckt ohne `--count-only` auch dann Trefferquoten. Das
   Fenster um 7 Tage verlängern (`--until 2026-12-05T00:00:00+00:00`, dann `12-12`, `12-19`, `12-26`) und nach
   jedem neuen Fensterende wieder nur zählen.
4. **Am 26.12. immer noch unter 150:** Der Test ist unentschieden, der Filter kommt nicht.

**Im Bericht nennen:**

- den Nachtrag vom 13.11. und wie viele Tipps ihre Quote nur über die Auswahl haben (das Skript druckt die Zahl);
- dass die erste Veröffentlichung vieler Fussballtipps am Vortag liegt und die Quote danach gespeichert wurde;
- die Änderungen seit 10.11.: Regler-Startwert 70 % (das Protokoll bleibt ungefiltert), Folgetag immer, Teamsport
  und E-Sport morgen;
- dass die anderen Sportarten fast nie eine Einstiegsquote haben.

**Ob 150 Fallen bis 28.11. zusammenkommen, ist offen.** Im Rückblick waren es rund 19 pro Tag bei vollem
Ligabetrieb. Im Fenster liegt nach der Pause nur ein volles Liga-Wochenende. Eine Verlängerung ist wahrscheinlich
und in der Regel vorgesehen.

**Folgen:** Besteht der Filter, ist er ein Kandidat und kommt nur mit Owner-OK in einem eigenen PR, als Sperre im
Hintergrund. Besteht er nicht, ist er verworfen.

## 9. Offene Aufgaben

### Codex, in sinnvoller Reihenfolge

1. **Prüfliste vom Montag** (Abschnitt 1).
2. **API-Hockey-Verbrauch** ansehen und dem Owner melden, wenn Abrufe gesperrt werden (Abschnitt 10, Risiko 4).
3. **Fallenfilter** zählen und am 30.11. auswerten; dazu Formstärke/Hybrid und Liste ab 70 % (Abschnitt 8).
4. **Tennis morgen** (Schritt 3b, offen).
   - Der Tennis-Scan läuft um 00:05 nur für heute: `scripts/tennis_daily.py` → `_default_scan_date()`, ausgelöst
     über `run_daily_pipeline.py:144`.
   - Die Live-Vorbereitung hat 1800 s (`LIVE_SECONDS_LIMIT`, etwa 10 bis 12 s pro Fall) und 512 MiB. `case_limit`
     liegt bei 400, `DAILY_SCAN_TIMEOUT_SECONDS` bei 39 Minuten.
   - Ein zweiter Tag braucht einen eigenen Lauf, etwa einen zweiten Timer mit Datumsargument. Das ändert eine
     Einheit: neue Pins in `deploy/bootstrap_server.sh` und `deploy/update_server.sh` und ein Eintrag in der
     Rekonstruktion von `tests/test_context_updater_repair.py`. Der Release-Helfer verbietet das.
   - Lader: `tennis_loader(today=target+1)` zusätzlich aufrufen, Zeilen mit `target_date=next_target` bauen,
     `tennis_shadow` in `NEXT_DAY_SOURCE_BY_SPORT` aufnehmen (`sources.tennis.next_day`). Die Tennisbox heisst
     heute nur „Heute“ (`app.py`, `rail_label`).
   - **Wichtig:** Eine Tennis-Zeile für morgen verwirft heute das ganze Dokument.
5. **E-Sport morgen** deckt nur die nächsten 6 Spiele je Titel ab (`scanners/esports_scanner.py`,
   `MAX_UPCOMING_MATCHES_PER_GAME`). Mehr kostet PandaScore-Abrufe und braucht ein Owner-OK.
6. **Tests, die schon vor dem 10.11. scheiterten.** Alle scheitern gleich auf dem unveränderten `main` vor #107.
   Ursache prüfen, wahrscheinlich teils feste Daten von September/Oktober gegen die echte Uhr.
   - Unter `gate`:
     - `test_shared_quote_observations.py::test_active_15k_model_surface_obeys_bound_floor_before_slot_selection[1.2-True]`
     - `test_wettfinder_stage_diagnostics.py::test_production_stages_preserve_document_order_and_private_callbacks`
     - `test_catalog_statistical_selection.py::test_ilves_catalog_survives_real_reader_cards_and_low_price_does_not_flip_direction[1.12]`
       und `[1.8]`
     - `test_team_sport_prices.py::test_forecast_consumer_reuses_exact_cached_price_without_network`
     - `test_api_hockey_prices.py::test_native_conflicting_role_ids_fail_before_any_request`
     - `test_wettfinder_match_context.py::test_normal_wettfinder_does_not_inherit_daily3_probability_floor`
   - Unter `BETBOY_TEST_PRICE_POLICY=floor` zusätzlich 19: `test_team_sport_prices` (6), `test_team_sport_forecasts`
     (5), `test_esports_prices` (5), `test_hockey_esports_clock` (2), `test_wettfinder_stage_diagnostics` (1), dazu
     2 in `test_sports_editorial`.
   - Die automatischen CI-Jobs enthalten diese Dateien nicht und sind grün.
7. **Dauerhaft offene Ergebnisse:** 5 Fussballspiele vom 1. bis 8.11. und 26 Tennisspiele aus September und Oktober
   bekommen kein Ergebnis. Seit #107 belegen sie nur Restplätze. Eine Regel „nach X Tagen ungültig“ wäre eine
   Owner-Entscheidung.
8. **Morgen-Karten zeigen im Wettfinder „Modellstand nicht aktuell belegt“** (gesehen am 11.11.).
   `forecast_highlight_reason` gibt die tägliche Modell-Lebensdauer nur dem Spieltag; nur die Doublebet-Vorschau
   übergibt `match_day`. Prüfen, ob das für die Wettfinder-Liste gewollt ist.
9. **Die Doublebet-Vorschau bleibt bei Vereinsspielen oft leer.** Morgen bekommt nur die Kontextprüfungen, die heute
   übrig lässt (3 Nachläufe zu je 20 Spielen). An Länderspieltagen gibt es seit v16 eine Auswahl.
10. **Cricket-Zeilen verwerfen das ganze Dokument.** `expected_source` kennt Cricket nicht; das war schon so.
11. **Google-Play-Technik**, sobald der Owner seine Punkte klärt (Plan in PR #106): Subdomain und Caddy,
    `/.well-known/assetlinks.json`, Web-Manifest, Trusted Web Activity mit Bubblewrap (`com.bmmestudios.betboy`),
    Prüfung auf dem Handy, Store-Texte.
12. **Ältere Punkte:** `AGENTS.md`, Abschnitt „Offen“, und die Massnahmen 5, 6, 8 und 10 aus
    `AUDIT_BERICHT_2026-10-25_CLAUDE.md`.

### Nur mit Owner-OK

- Worktrees und gemergte Branches aufräumen.
- Die 8 alten fehlgeschlagenen Einheiten mit `systemctl reset-failed` entfernen.
- Jede Änderung an einer Einheit, jedes Backup, jede Kopie einer Produktions-Datenbank, jeder API-Abruf über das
  Übliche hinaus.

### Owner

- Alte API-Schlüssel beim Anbieter sperren oder neu ausstellen. Laut Audit K1 ist der Widerruf nicht belegt, und die
  alten Werte stehen in der öffentlichen Git-Historie.
- Telegram-Token und Chat-ID in `/etc/betboy/betboy.env`.
- Impressum, Datenschutz und AGB ausfüllen, prüfen lassen, URLs setzen.
- **Google Play:** Serverstandort nennen, App-Adresse festlegen (Vorschlag `betboy.bmmestudios.com`), journald auf
  30 Tage begrenzen (Owner „Später“), Bilder von Drittservern klären, Kontotyp wählen (privat heisst 12 Tester
  während 14 Tagen), Rechtstexte fachlich prüfen lassen, Website mit `npm.cmd run deploy` hochladen.
- **Entscheide, die warten:**
  - Tennis-Zweitquelle (OddsPapi ist für E-Sport schon angebunden, Gratisplan).
  - Mehr E-Sport-Abdeckung für morgen.
  - Nachquote, erst nach dem 30.11.
  - Regel für dauerhaft offene Ergebnisse.

### Bewusst offen gelassen

- **Basketball (EuroLeague) bekommt nie eine Quote.** Die Zeilen tragen Vereinskürzel, API-Sports volle Namen. Nicht
  behoben, weil das Modell schwach ist (29 Spiele, 51,7 % getroffen bei 67,6 % versprochen).
- **E-Sport hat fast nie eine Einstiegsquote** (1 von 19 im Fenster des Fallenfilters).

## 10. Risiken und Lehren

1. **Rücksprung unter `555797b` ist gefährlich.** Der Worker schreibt Morgen-Zeilen für Eishockey, Basketball und
   E-Sport. Der Lader vor #115 verwirft ein solches Dokument komplett, und die Seite wäre leer bis zum nächsten
   Lauf. Das gilt auch für ein Teil-Release: App und Worker immer auf derselben Version.
2. **Release-Asserts veralten** (Abschnitt 6, Schritt 3). Die lokale Offline-Prüfung ist Pflicht.
3. **Der Auto-Mode-Klassifikator blockt Releases ohne klares „live stellen“.** Nicht umgehen, den Owner fragen.
4. **API-Hockey läuft nahe an der Tagesgrenze von 100.** Verbrauch 10.11. 16, 11.11. 49, 12.11. 83. Am 13.11.
   entfielen bis 09:15 schon 25 Abrufe auf `odds` und 12 auf `games`.
   - Vermutlich kommt der Anstieg von den Morgen-Zeilen für Eishockey (#115) und davon, dass Team-Quoten zuerst für
     Spiele mit Modell geholt werden (#118). Geprüft ist die Ursache nicht.
   - An einem Samstag mit vielen NHL-Spielen kann die Grenze erreicht werden. Gesperrte Abrufe stehen mit
     `decision = BLOCKED` in `api_budget_events`. Der Quotenlauf bricht deshalb nicht ab; es fehlen dann Quoten für
     Eishockey, und das Doublebet hat weniger Kandidaten. Dieser Fall ist für Eishockey noch nicht beobachtet.
   - Eine Änderung am Abrufverhalten wäre App-Code und braucht einen PR und ein Release.
5. **Folgetag und Kontingent bei API-Football.** Am 07.11., einem vollen Liga-Samstag vor „Folgetag immer“, waren es
   3575 Abrufe. Mit Folgetag wurden am 10.11. zusätzlich 1000 bis 2000 an vollen Tagen geschätzt. Das erste volle
   Liga-Wochenende mit der neuen Regel ist voraussichtlich der 21./22.11.
6. **Quote und Modell.** Die Daten zeigen keinen Vorsprung auf den Buchmacher (Benchmark 0 von 112 Zellen,
   Vorsprung-Analyse vom 12.11.). Getestet und widerlegt sind Wetter, Ausfälle und Ruhetage, Startelf. Die
   Formstärke bringt einen kleinen Gewinn und ist live. Der Owner will 70 % Treffer und gute Quoten; ehrlich geht das
   nur über „ab 70 %“ mit Quoten um 1,28.
7. **Vorab festgelegte Messungen** scheitern leicht an Umbauten daneben. Der Fallenfilter zählte drei Tage lang
   nichts, weil PR #112 die erste Veröffentlichung auf den Vortag schob. Nach jedem Umbau an Listen oder Evidenz
   die laufenden Messungen mit `--count-only` gegenprüfen.
8. **Grüne CI deckt nicht alles** (Abschnitt 5, Punkt 4).
9. **Unterbrochene Subagents** hinterlassen ungespeicherte Arbeit in `.claude/worktrees/agent-*`. Vor einem
   Neustart den Worktree prüfen.
10. **Ein Timer-Neustart ohne Stempel** feuerte am 25.10. die Tagesscans sofort. Einheiten deshalb nur über den
    geprüften Weg ändern.

## 11. Regeln

`AGENTS.md` ist massgeblich und enthält jeden Owner-Entscheid mit Datum. Hier die Regeln, die im Alltag am
häufigsten greifen:

- **Modell vor Preis.** Keine Quote fliesst in eine Modellschätzung oder in die Reihenfolge. Die Marktmischung hat
  der Owner abgelehnt.
- **Keine Auswahl nach Quote** und keine höhere Mindest-Modellchance als Lösung für die Trefferquote.
- **Kein Schwellen-Tuning.** Regeln nur mit vorab festgelegter Hypothese und zeitlich getrennter Prüfung ändern.
- **Die App zeigt keine Buchmacherquoten.** Die 1,20-Grenze bleibt im Hintergrund.
- **`BETBOY_PRICE_POLICY=gate` nie in Produktion.** `BETBOY_RELEASE_MARKET_BENCHMARK` nicht setzen.
- **Tipps werden nach Trefferquote und Kalibrierung bewertet**, nicht nach ROI. Keine Gewinnversprechen.
- **Nur bestehende Quellen**, keine neuen bezahlten Tarife. API-Football ist bezahlt. Open-Meteo nur privat. Die
  interne API von ybets7 nie scrapen.
- **Freigaben einzeln:** Merge, Release, API-Abrufe über das Übliche hinaus, Backups und DB-Kopien, Änderungen an
  Einheiten. Kleine, angekündigte API-Proben brauchen ein OK.
- **Releases** nur über den No-Backup-Fast-forward-Helfer, nie hinter `555797b`.
- **Morgen-Zeilen** sind nie Tipp, 15K-Eintrag, Doublebet-Wahl, Shadow, Evidenz oder Archiv vor ihrem Spieltag.
- **Länderspiele im Doublebet:** Nur die ausdrückliche Meldung „nicht abgedeckt“ zählt als Ausnahme, nur für
  A-Nationalteams, nur im Doublebet. Nicht auf Vereinsspiele oder andere Flächen ausdehnen.
- **Preisjagd** nicht messen, nicht bauen, nicht erneut vorschlagen (Owner 12.11.2026). BetBoy behauptet keinen
  Vorsprung.
- **Fallenfilter:** bis zur Auswertung nur `--count-only`; keine Varianten.
- **Schlüsselwerte** nie in Chat, Doku, Tests oder Git.
- **Checkout-Disziplin:** eigener Worktree, kein `git stash` ohne Tag, fremde Worktrees und der Hauptcheckout
  bleiben unberührt.

## 12. Owner und Zusammenarbeit

- **Owner:** Miroslav, Alleinentwickler, Deutsch (Schweiz, CHF).
- **Antworten:** kurz und direkt, Kernaussage zuerst, einfache Sprache ohne Fachjargon, „ss“ statt „ß“. Bei
  Rückfragen wie „erklär einfach“ noch einfacher.
- **Entscheide vorlegen:** eine Frage, höchstens zwei Wege, mit Empfehlung. Kürzel wie `forecast_id` im Gespräch
  mit ihm vermeiden.
- **Ehrlichkeit:** Massstab ist `PROJEKTBIBEL.md`. Zahlen mit n, keine Gewinnversprechen, Unsicheres als unsicher
  nennen.
- **Commits** von Claude enden mit `Co-Authored-By: …`, PR-Texte mit der Generated-Zeile. Codex nutzt seine eigene
  Signatur.

## 13. Pfade

| Wo | Was |
|---|---|
| `/opt/betboy/app/runtime_state/wettfinder_latest.json` | Tagesdokument: `model_candidates`, `candidates`, `football_next_day`, `next_day_search_date`, `sources.*.next_day`, `forecast_evidence.settlement` |
| `runtime_state/forecast_evidence.db` | `forecast_rows` (Prognosen mit `forecast_id`, `event_key`, `market_key`, `selection`, `payload_json`), `forecast_quotes` (`kind` = `entry` oder `closing`), `forecast_results` |
| `runtime_state/consumer_tips.db` | `consumer_tip_publications` (`surface`, `first_observed_at`), `consumer_tips` (`payload_json`) |
| `runtime_state/team_sport_quotes.json` | NHL-, Eishockey- und Basketball-Quoten, `attempts` (3-Stunden-Sperre), `identity_gaps`, `budget_deferred` |
| `runtime_state/api_budget.db` | `api_budget_state` (Grenze und Rest je Anbieter und Tag; Monatszeilen mit `:month`), `api_budget_events` (jeder Abruf mit `decision`) |
| `runtime_state/ops_alerts.jsonl` | Alarme der Kerneinheiten |
| `/var/tmp/bb_lineups/lineups.db` | Startelf-Daten des widerlegten Tests, nur für die Analyse |
| `/etc/betboy/betboy.env` | Umgebung mit Schlüsseln; nie ausgeben |
| `C:\Projekt\BetBoy\output\` | Auswertungen und Release-Belege, nicht in Git. Neu: `uebergabe-20261113` (Helfer für Abschnitt 1 und 8), `fallenfilter-20261113`, `vorsprung-20261112`, `release-20261112-1` |
| `C:\Projekt\BetBoy\betboy-app\.worktrees\claude-audit-repairs-20261019\runtime_state\market_benchmark\` | 98 CSV von football-data.co.uk (14 Ligen, 7 Saisons, 36 369 Spiele) für Marktvergleiche |
| `C:\Projekt\BmmeStudios` | Website `bmmestudios.com`, ohne Git; BetBoy-Eintrag in `content/apps.mjs` |
| Timer (Europe/Zurich) | tennis 00:05; esports 03:10; wettfinder 03:35; backup-retention gegen 04:20; redcard-history 05:41; redcard-settlement 06:05; quotes 00/03/06/09/12/15/18/21:15; football-shadow alle 10 Minuten |
| Live-Seite | `https://vps-a30a123f.vps.ovh.net/` |

Pinnacle-Kennungen in den Quoten: `api-football:4`, `odds-api:pinnacle`, `oddspapi:pinnacle`. Die Einstiegsquoten
stammen fast immer von `api-football:11`.

## 14. Was nicht geprüft ist

- **Das Wochenende 14./15.11.** hat niemand beobachtet. Das ist Punkt 3 der Prüfliste.
- **Die Vollsuite** lief für PR #123 und für diese Übergabe weder lokal noch in der CI. Gelaufen sind lokal die
  8 Tests des Messskripts und ruff, dazu die automatischen CI-Jobs.
- **Die Ursache des Anstiegs bei API-Hockey** ist eine Vermutung.
- **Die 156 gesperrten API-Football-Abrufe vom 07.11.** sind nicht untersucht.
- **Die Trefferquote des Doublebet seit v15/v16** ist nicht ausgewertet; es sind erst wenige Auswahlen.
- **Die Gegenprobe des Fallenfilters** zeigt 5012 abgerechnete Tipps, der Rückblick vom 09.11. zeigte 4668. Der
  Grund ist vermutlich, dass seither weitere Tipps dieses Zeitraums abgerechnet sind; einzeln geprüft ist das nicht.
- **Die alten Testfehler** (Abschnitt 9, Punkt 6) sind nicht erklärt.
