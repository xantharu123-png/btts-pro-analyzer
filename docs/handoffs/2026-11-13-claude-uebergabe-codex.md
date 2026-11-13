# Übergabe Claude → Codex, Stand 13.11.2026

Dieses Dokument schliesst an `docs/handoffs/2026-11-11-claude-uebergabe-codex.md` an und nennt nur, was seit dem
11.11.2026 dazukam. Aus der Übergabe vom 11.11. gelten unverändert weiter: das Release-Verfahren (Abschnitt 3), die
Risiken (6), Owner und Zusammenarbeit (7) und die Pfade (8). Bei Widersprüchen gilt wie immer zuerst der Code.

## 0. Kurzfassung zum Einfügen

> Lies zuerst `AGENTS.md`, `STATUS.md`, dieses Dokument (`docs/handoffs/2026-11-13-claude-uebergabe-codex.md`) und
> danach die Übergabe vom 11.11.
>
> **Stand 13.11.2026, 08:32 CET:**
> - Produktion läuft auf `9aee28d` (live seit 12.11.2026 08:44 CET, Release 20261112-1). `origin/main` steht auf
>   `2ff5528` plus diesem Übergabe-PR; die Commits nach `9aee28d` sind reine Doku.
> - Offen ist nur PR #106 (Plan Google Play).
> - Alle Server-Dienste liefen am 13.11. mit Exit 0. Der letzte Alarm stammt vom 07.11.
>
> **Neu seit 11.11.:**
> - Doublebet nimmt Eishockey (Policy v15) und A-Länderspiele ohne Verletzungsdaten (Policy v16) auf.
> - Vorsprung-Analyse vom 12.11.: kein belegter Vorsprung gegenüber Buchmachern. Der Owner hat die Preisjagd
>   abgelehnt („Nein, lassen“); nicht erneut vorschlagen.
>
> **Achtung:** Der Fallenfilter zählt bisher 0 Tipps mit Quote (Abschnitt 3). Vor der Auswertung am 30.11. braucht
> es einen Owner-Entscheid.
>
> **Regeln:** wie am 11.11. Releases nur über den No-Backup-Fast-forward-Helfer, Merge und Release nur mit
> ausdrücklichem Owner-OK (Release wörtlich „live stellen“), nie hinter `555797b` zurückrollen.

## 1. Stand am 13.11.2026 um 08:32 CET

| Bereich | Stand |
|---|---|
| Produktion (VPS `betboy-vps`, `/opt/betboy/app`) | `9aee28df1b6efc9b9bfe097cb0598a4c7f53e765`, live seit 12.11.2026 08:44 CET |
| `origin/main` | `2ff5528` (PR #121, Protokoll) plus dieser Übergabe-PR |
| Offene PRs | #106 „Plan: BetBoy in den Google Play Store“ (nur Doku) |
| Dienste 13.11. | alle `success`/Exit 0: tennis 00:11, esports 03:10, wettfinder 03:51, backup-retention 04:21, redcard-history 05:41, redcard-settlement 06:05, quotes 06:15, football-shadow 08:22; app aktiv |
| Alarme | 14 Einträge in `runtime_state/ops_alerts.jsonl`, der letzte vom 07.11. 20:52; seither keiner |
| Fehlgeschlagene Einheiten | 8 alte Einmal-Einheiten vom 14.–19.09.2026 (`betboy-release-*`, `betboy-storage-repair-20260919`, `codex-*`); keine Kerneinheit, Altlast |
| Platte | 38 GB, 51 % belegt |
| Tagesdokument 13.11. | Fussball 66 Zeilen heute und 204 morgen; Basketball 6 heute, ohne Quote; Eishockey 6 Zeilen morgen (3 NHL-Spiele, mit Quote); E-Sport 5 heute und 1 morgen; Team-Quoten ohne Fehler und ohne Lücken |
| Doublebet 13.11. | heute Serbien gegen Deutschland, Team-2-Gesamttore Unter, Median-Quote 1,85, Modell 70 %; Vorschau morgen Norwegen gegen Wales, Team-1-Gesamttore Unter, 1,91, 75 % |

- **Claude-Arbeitsworktree:** `.worktrees/claude-shadow-void-verschoben`, nach dem Merge wieder detached auf
  `origin/main`.
- **Hauptcheckout** `C:\Projekt\BetBoy\betboy-app`: unverändert veraltet mit fremdem WIP. Nur die ungetrackten
  Kopien `STATUS.md` und `AGENTS.md` nach jedem Merge erneuern (`git show origin/main:STATUS.md > …`).
- **Auf dem Server unter `/tmp`** liegen alte Leseskripte früherer Sitzungen (rund 90 `.py`), harmlos.
  `/tmp/shadow_gap.sh` braucht das Release-Verfahren; nicht löschen.

## 2. Was seit dem 11.11.2026 geschah

1. **11.11., 14:15: Doublebet mit Eishockey** (PR #118, Release 20261111-3, `4f00d0f`, Policy v15).
   - Nur das Doublebet nimmt das Eishockey-Forschungsmodell auf (`DOUBLEBET_RESEARCH_SPORTS`). Team-Quoten werden
     zuerst für Spiele mit Modell geholt.
   - Protokoll `docs/audits/2026-11-11-doublebet-eishockey.md`, Protokoll-PR #119.
2. **12.11., 08:44: Doublebet mit A-Länderspielen** (PR #120, Release 20261112-1, `9aee28d`, Policy
   `doublebet-odds-around-2-most-probable-v16`). Owner „Ja, zulassen“, „Ja, live stellen“.
   - **Anlass:** Am 12.11. war das Doublebet leer. API-Football liefert für Nationalteams keine Verletzungsdaten
     (`availability = not_covered`, `coverage_available = False`), und die Kontextregel verlangt sie.
   - **Code:**
     - `forecast_analysis.football_context_highlight_reason(…, uncovered_injuries_ok=False)` überspringt nur die
       ausdrückliche Meldung „nicht abgedeckt“. Ein fehlgeschlagener oder fehlender Abruf und jedes andere Veto
       sperren weiter.
     - `daily3_selection._explanation` setzt den Schalter nur für `model_scope == NATIONAL_SCOPE`
       (`senior_national_pooled`).
   - **Unverändert:** Vereinsspiele und alle anderen Flächen (Wettfinder, 15K, Tipps).
   - **Tests:** `tests/test_doublebet_laenderspiele.py`, 12 Fälle.
   - **Zurücknehmen:** `uncovered_injuries_ok=False` im Aufruf in `daily3_selection._explanation`.
   - Protokoll `docs/audits/2026-11-12-doublebet-laenderspiele.md`, Protokoll-PR #121 (`2ff5528`).
3. **12.11.: Nachtlauf geprüft.** Die Morgen-Zeilen für Eishockey, Basketball und E-Sport kommen an, die App nimmt
   sie an. Punkt 1 der Aufgabenliste vom 11.11. ist damit erledigt.
4. **12.11.: Vorsprung-Analyse** (nur gelesen, `docs/audits/2026-11-12-vorsprung-gegen-buchmacher.md`).
   - Das Modell ist in jeder Marktart schlechter als die faire Marktchance, nur bei Ecken gleichauf. Wo das Modell
     „Wert“ sieht, verlieren die Wetten 10 bis 17 %.
   - Sechs Ideen gerechnet. Nur die Preisjagd ohne Modell zeigt ein Plus (Bestpreis gegen faire Pinnacle-Chance,
     1X2, 7 Saisons: 18 686 Wetten, +3,5 % [+1,2; +5,9]). Es ist nur mit sehr vielen Buchmachern gesichert und in
     der Saison 2025/26 negativ.
   - **Owner: „Nein, lassen“.** Keine Messung, kein Bau. Nicht erneut vorschlagen.
   - Skripte und Ausgaben: `C:\Projekt\BetBoy\output\vorsprung-20261112\` (nicht in Git).
5. **13.11.: Fallenfilter gezählt und die Zuordnung geprüft** (Abschnitt 3).

## 3. Achtung: Der Fallenfilter zählt keine Tipps mit Quote

**Befund am 13.11., 08:32** (`scripts/trap_filter_measurement.py --count-only`, 3,3 Tage im Fenster):
58 abgerechnete Tipps, davon 0 Fallen, 0 übrige mit Quote und 58 ohne Quote. Nötig sind mindestens 150 Fallen.

Geprüft wurde nur die Struktur (`output/vorsprung-20261112/fallen_diag.py`). **Trefferquoten nach Falle oder
Nicht-Falle hat niemand angesehen.**

148 Erstveröffentlichungen im Fenster seit 10.11.:

| Sportart | Liste | Wann | Anzahl | `forecast_id` | Einstiegsquote |
|---|---|---|---|---|---|
| Fussball | `wettfinder_automatic` | am Vortag | 61 (27 abgerechnet) | fehlt | über die `forecast_id` nie; 7 der abgerechneten hätten eine über dieselbe Auswahl |
| Fussball | `wettfinder_default_inventory` | am Spieltag | 41 (alle offen) | vorhanden | 11 mit, 30 ohne |
| Eishockey | `wettfinder_default_inventory` | am Vortag | 17 (14 abgerechnet) | vorhanden | keine |
| E-Sport | `wettfinder_default_inventory` | am Spieltag | 19 (11 abgerechnet) | vorhanden | 1 mit |
| Tennis | Inventar und `riskobet_catalogue` | am Spieltag | 7 (4 abgerechnet) | teils | keine |
| Basketball | `wettfinder_default_inventory` | am Spieltag | 3 (2 abgerechnet) | vorhanden | keine |

**Zwei Ursachen:**

1. **Morgen-Zeilen tragen keine `forecast_id`.** Die App veröffentlicht einen Fussballtipp seit PR #112
   (10.11., „Folgetag immer“) meist schon am Vortag unter `wettfinder_automatic`. Morgen-Zeilen sind nach Regel nie
   Evidenz, deshalb fehlt die `forecast_id`. Das Messskript ordnet die Quote aber über `payload.forecast_id` zu
   (`tip_records`, `quotes.get(payload.get("forecast_id"))`). Jeder Tipp, der zuerst am Vortag erscheint, bleibt
   damit für immer „ohne Quote“.
2. **Länderspielpause.** Einstiegsquoten je Abruftag: 06.11. 164 Prognosen, 07.11. 508, 08.11. 556, 09.11. 12,
   10. und 11.11. keine, 12.11. 21, 13.11. 20. Die anderen Sportarten haben fast nie eine Einstiegsquote.

**Folge:** Mit der Regel, wie sie steht, entstehen Fallen nur aus Tipps, die erst am Spieltag erscheinen und eine
Quote haben (bisher 11, alle offen). 150 Fallen bis 28.11. sind unwahrscheinlich. Die Vorab-Regel erlaubt dann nur
die Verlängerung um je 7 Tage bis längstens 26.12., sonst lautet das Urteil „unentschieden“.

**Der Owner muss entscheiden, bevor jemand Trefferquoten ansieht:**

- **A, Regel lassen.** Vermutlich „unentschieden“.
- **B, Zuordnung vorab berichtigen.** Die Quote über die Auswahl suchen (`event_key`, `market_key`, `selection`):
  die erste Einstiegsquote irgendeiner Prognose-Revision dieser Auswahl. Alles andere bleibt gleich. Die Änderung
  mit Datum und Grund in `docs/audits/2026-11-09-fallenfilter-vorab.md` nachtragen, Test in
  `tests/test_trap_filter_measurement.py`, und erst danach auswerten.
- **Empfehlung Claude: B.** Die Regel scheitert sonst an einer Nebenwirkung von PR #112, nicht an den Daten. Es
  ist eine Änderung an einer vorab festgelegten Messung und braucht deshalb das ausdrückliche Owner-OK.

Bis dahin gilt weiter: nur `--count-only`.

## 4. Termine

| Wann | Was | Wie |
|---|---|---|
| 14./15.11. | API-Verbrauch am ersten Liga-Wochenende mit „Folgetag immer“ | `runtime_state/api_budget.db`, Tabelle `api_budget_events`; Grenze api-football 7500 pro Tag. Für den 14.11. listet der Lauf schon 204 Fussballzeilen |
| laufend | Doublebet v15/v16 beobachten | Anzahl Auswahlen und Trefferquote gegen 50 %; Länderspiele ohne Verletzungsdaten sind ein bewusstes Risiko (`docs/audits/2026-11-12-doublebet-laenderspiele.md`) |
| bis 30.11. | Fallenfilter: nur Anzahl | `sudo -n -u betboy bash -c 'cd /opt/betboy/app && /opt/betboy/venv/bin/python -I scripts/trap_filter_measurement.py --count-only'` |
| **vor dem 30.11.** | Owner-Entscheid zur Zuordnung im Fallenfilter | Abschnitt 3 |
| **30.11.** | Fallenfilter, Formstärke und Hybrid, Liste ab 70 % auswerten | Übergabe vom 11.11., Abschnitt 4 |
| nächster Europapokal-Spieltag | Ligastärke im Betrieb messen | `docs/audits/2026-11-05-ligastaerke-europapokal.md` |

## 5. Offene Aufgaben

Die Listen der Übergabe vom 11.11. (Abschnitt 5) gelten weiter. Änderungen:

- **Erledigt:** Punkt 1 (Nachtlauf und Morgen-Zeilen am 12.11. geprüft).
- **Teilweise entschärft:** Punkt 7 (leere Doublebet-Vorschau). An Länderspieltagen gibt es seit v16 eine Auswahl.
  Für Vereinsspiele hängt die Vorschau weiter an den übrigen Kontextprüfungen.
- **Neu, Owner:** Entscheid zum Fallenfilter (Abschnitt 3).
- **Neu, bewusst offen:**
  - Basketball (EuroLeague) bekommt nie eine Quote: Die Zeilen tragen Vereinskürzel, API-Sports volle Namen. Nicht
    behoben, weil das Modell schwach ist (29 Spiele, 51,7 % getroffen bei 67,6 % versprochen).
  - E-Sport hat fast nie eine Einstiegsquote (1 von 19 im Fenster).
  - Tennis-Zweitquelle bleibt ein Owner-Entscheid.
- **Neu, klein:** Die 8 fehlgeschlagenen Einmal-Einheiten vom September könnten mit `systemctl reset-failed`
  verschwinden. Das ändert den Server und braucht ein Owner-OK.

## 6. Für das nächste Release

- Letzter Generator: `C:\Projekt\BetBoy\output\release-20261112-1\gen_deploy51.py`, abgeleitet durch `make_gen.py`
  im selben Ordner.
- `PREV` für das nächste Release: `9aee28df1b6efc9b9bfe097cb0598a4c7f53e765`.
- Die Asserts im PY-Block prüfen jetzt auch die Policy v16 und `uncovered_injuries_ok`. Ändert ein PR die Policy
  oder diese Funktion, die Asserts mitziehen (Übergabe vom 11.11., Abschnitt 3, Schritt 3).
- `release-files.txt` muss in C-Reihenfolge sortiert sein (Grossbuchstaben zuerst), sonst bricht `deploy.sh` beim
  Vergleich der Dateiliste ab.
- Lehren aus dem 12.11.:
  - Commit-Texte aus einer Datei übergeben (`git commit -F datei`). Ein Here-String in der PowerShell scheiterte
    und liess einen leeren Branch zurück.
  - Nach `cd` in einen Ordner ausserhalb des Repos scheitert `gh`. Vor `gh` zurück in den Worktree.

## 7. Regeln, die seit dem 11.11. dazukamen

- **Preisjagd nicht erneut vorschlagen** (Owner 12.11.2026). BetBoy behauptet keinen Vorsprung.
- **Länderspiele im Doublebet:** Nur die ausdrückliche Meldung „nicht abgedeckt“ zählt als Ausnahme, nur für
  A-Nationalteams, nur im Doublebet. Nicht auf Vereinsspiele oder andere Flächen ausdehnen.
- Alles andere wie in `AGENTS.md` und in Abschnitt 7 der Übergabe vom 11.11.
