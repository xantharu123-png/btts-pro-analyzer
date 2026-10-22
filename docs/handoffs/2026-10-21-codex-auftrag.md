# Auftrag an Codex: Claude-Audit-Reparaturen integrieren, prüfen, freigeben

Stand 21.10.2026. Dieser Auftrag ist so geschrieben, dass er direkt als Aufgabe an Codex
übergeben werden kann. Fachliche Details stehen in den verlinkten Dokumenten, nicht hier.

## Kurzfassung zum Einfügen

> Integriere den Branch `claude/audit-repairs-20261019` (PR #1 auf
> `xantharu123-png/btts-pro-analyzer`) in deine laufende Arbeit im Worktree
> `.worktrees/audit-repairs-20261013`. Lies zuerst `AGENTS.md`,
> `docs/handoffs/2026-10-20-claude-uebergabe.md` und
> `docs/audits/2026-10-19-audit-reparaturen.md` aus diesem Branch. Sichere dein WIP,
> merge, löse die erwarteten Konflikte wie unten beschrieben, führe die Prüfbefehle aus,
> und bereite das Release nach den Vorbedingungen in Abschnitt 5 vor. Ändere keine
> Defaults der Opt-in-Schalter und aktiviere weder das Markt-Gate noch Dixon-Coles.

## 1. Kontext in fünf Sätzen

Am 16.10.2026 wurde BetBoy aus vier Rollen auditiert (`AUDIT_BERICHT_2026-10-16_CLAUDE.md`).
Vom 19. bis 20.10. wurden die Reparaturen auf einem eigenen Branch umgesetzt, der von
`origin/main` @ `be5e441` abzweigt und deine Arbeit nicht berührt. Der Owner hat am 20.10.
entschieden: Daily3-Vormerk-Gate aktiv, Karte mit Mindestquote und Preisstatus bleibt,
alle offenen Punkte angehen, Push und PR. Die wichtigsten Messungen: Das Fussballmodell
schlägt den No-Vig-Closing-Markt in 0 von 112 Zellen, das optimale Mischungsgewicht
Modell/Markt ist 0,00, und der Hybrid aus Dixon-Coles für Ergebnismärkte und Legacy für
Tormärkte ist das beste Modell im Datensatz. Nichts wurde deployt.

## 2. Zuerst lesen (aus dem Branch, nicht aus deinem Worktree)

```powershell
git fetch origin
git show origin/claude/audit-repairs-20261019:AGENTS.md
git show origin/claude/audit-repairs-20261019:docs/handoffs/2026-10-20-claude-uebergabe.md
git show origin/claude/audit-repairs-20261019:docs/audits/2026-10-19-audit-reparaturen.md
```

`AGENTS.md` enthält die Regeln (Modell vor Preis, fail-closed, kein Schwellen-Tuning,
Secrets nur per Env, Nutzerentscheidungen vom 17.10. und 20.10.). Die Übergabe listet
alle 17 Commits, 60 Dateien, Umgebungsvariablen, Befehle und Risiken. Das Protokoll
enthält die Zahlen.

## 3. Integration

1. **Eigenes WIP sichern.** In `.worktrees/audit-repairs-20261013` alle 18 offenen
   Änderungen auf `codex/audit-repairs-20261013` committen. Kein `git stash`.
2. **Quelle wählen.** PR #1, PR #2 und PR #3 sind seit 22.10.2026 in `origin/main`
   (`08b7473`): `git fetch origin && git merge origin/main`. Nicht rebasen, die Commits
   sind referenziert. Es gibt keinen offenen Claude-Branch mehr; `STATUS.md` zeigt den
   jeweils aktuellen Stand.
3. **Erwartete Konflikte.**
   - `TODO_AKTUELL.md`, `PC_WECHSEL_UEBERGABE.md`: beide Seiten haben oben neue Blöcke
     eingefügt. Beide Blöcke behalten, der neuere Block steht oben; keinen Text
     verwerfen.
   - `challenge_15k.py`: der Branch fügt `CROSS_LEAGUE_FDR_FLAG`,
     `cross_league_fdr_enabled()` und `_family_adjusted_validations` ein und ruft die
     Funktion in `scan_daily_challenge` direkt nach der Schleife auf, die
     `validations[(league_id, season)]` füllt. Dieser Aufruf muss erhalten bleiben.
   - `challenge_engine.py`: nur dann, wenn du dort ebenfalls geändert hast. Der Branch
     ändert `score_matrix` (Parameter `rho=0.0`), `_fixture_model` und
     `fixture_market_probabilities` (Parameter `goal_model`),
     `_walk_forward_market_records`, `build_fixture_candidates` (Markt-Sperrgrund) und
     `_credible_statistical_release_validation` (Vielfaches des Katalogs). Alle
     Default-Pfade sind byteidentisch; die Golden-Tests in `tests/test_calibration.py`
     beweisen das.
   - `app.py`: Footer-Aufruf `render_legal_footer(st)` statt des alten Caption-Satzes.
   - `tennis/backtest.py`: neue optionale Parameter, Default unverändert.
4. **Nach dem Merge prüfen** (Abschnitt 4). Erst dann deine eigene Arbeit fortsetzen.

## 4. Prüfbefehle

Aus dem Checkout-Root, Windows:

```powershell
..\..\.venv\Scripts\python.exe -m ruff check .
..\..\.venv\Scripts\python.exe -m pytest tests/test_calibration.py tests/test_daily3_selection.py tests/test_daily3_ui.py tests/test_sports_editorial.py tests/test_legal_notice.py tests/test_customer_access.py tests/test_cross_league_fdr.py tests/test_challenge_15k.py tests/test_football_dixon_coles.py tests/test_market_benchmark.py tests/test_market_release_gate.py tests/test_market_blend.py tests/test_no_vig_methods.py tests/test_tennis_calibration_population.py tests/test_workflow_integrity.py -q
```

Erwartung: Ruff 0 Befunde, alle Tests grün. Vollsuite auf Linux: der GitHub-Job `full`
(`.github/workflows/tests.yml`, manuell) wurde vom Runner bei 36 % mit Exit 137
(Speicherlimit) beendet, ohne Fehlschlag bis dahin. Entweder den Job in zwei Hälften
teilen wie die bisherige Linux-QA (Gruppen A/B) oder die Vollsuite wie gewohnt auf dem
VPS-Launcher laufen lassen. Ein Windows-Lauf ersetzt den Linux-Nachweis nicht.

## 5. Release-Vorbedingungen

1. **Env auf dem VPS prüfen, bevor die neue App startet.** Steht
   `BETBOY_PORTAL_INTERNAL_TOKEN` in `/etc/betboy/betboy.env`, ohne dass das Portal
   live ist, sperrt die App fail-closed. Dann `BETBOY_CUSTOMER_ACCESS_REQUIRED=0` setzen
   oder den Token entfernen. Details in `deploy/README.md`, Abschnitt Secrets/Env.
2. **Daily3-Gate ist aktiv** (Owner-Entscheidung). Nur `BETBOY_DAILY3_RESERVATION_MINIMUM=0`
   schaltet es ab; nicht setzen.
3. **Rechtslinks:** `BETBOY_LEGAL_URL`, `BETBOY_PRIVACY_URL`, `BETBOY_TERMS_URL` erst setzen,
   wenn die Seiten existieren; bis dahin zeigt der Footer ehrlich „noch nicht
   veröffentlicht“.
4. **Nicht setzen:** `BETBOY_RELEASE_MARKET_BENCHMARK` (würde jeden Echtgeldpfad leeren),
   kein `goal_model` ausserhalb von Tests und Skripten.
5. Release wie gewohnt: geprüfter Fast-Forward, Smoke, App-Neustart, beide Healthchecks,
   sieben Timer. Keine Backups (Owner-Regel), keine zusätzlichen Sportscans.
6. Nach dem Start eine Stichprobe: Daily3-Seite zeigt je Auswahl „Mindestquote für diese
   Auswahl“; Wettfinder-Karte zeigt die Zelle „Mindestquote“ und die Statuszeile; Footer
   zeigt 18+ und die Spielsucht-Links.

## 6. Verbote

- Keine Default-Änderung an Opt-in-Schaltern, keine Aktivierung von Markt-Gate oder
  Dixon-Coles in Produktion.
- Keine Quote als Modellinput. Benchmark-Preise bleiben in `market_benchmark_history`.
- Keine Schlüsselwerte in Chat, Doku, Tests oder Git. Keine Backups, keine Kopien von
  Produktionsdatenbanken.
- Kein Zugriff auf fremde Worktrees oder den veralteten Hauptcheckout
  (`betboy-app`, 60 Commits hinter `origin/main`, fremdes WIP).
- Keine Lockerung von Gates oder Tests, um Zahlen zu verbessern (Bibel §3.5).

## 7. Offene fachliche Arbeiten, in Reihenfolge

1. **Linux-Vollnachweis** (Abschnitt 4).
2. **H4 Dixon-Coles:** erledigt am 21.10. (widerlegt, `docs/audits/2026-10-21-dixon-coles-venue.md`).
3. **Kohärenter Hybrid:** erledigt (21./22.10.): Hybrid als beste Basis, Release-Gate-
   Validierung, Pins, ORIGINAL und Shadow-Kohorte (`docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md`).
   Nicht anfassen: Produktionsbasis bleibt Legacy, bis der Prüfplan erfüllt ist.
4. **Quotenabruf aller Seiten:** erledigt am 22.10. (`market_consensus.no_vig_market_probability`
   aus den vorhandenen Partitionen).
5. **Edge-Cap als Produktregel prüfen:** Im Replay hebt eine Kappung von 8 pp die Policy
   von −5,5 % auf +0,8 % ROI (Intervall enthält 0). Als Hypothese vorregistrieren, dann im
   Preisgate (`market_consensus`/`build_fixture_candidates`) als Sperrgrund umsetzen.
6. **Nebenbefunde:** `tennis/backtest._devig` lässt NaN-Preise durch; `atp_tournaments.csv`
   hat Endtermine erst ab 2024; `cross_league_fdr` behandelt UEFA-Heimatligen ausserhalb
   der Familie (siehe `docs/audits/2026-10-20-fdr-ligen.md`).
7. **Owner-Aufgaben, nicht Codex:** Rechtstexte ausfüllen und prüfen lassen,
   Provider-Widerruf der alten API-Schlüssel bestätigen, Entscheidung zur
   Hybrid-Aktivierung (`docs/audits/2026-10-22-hybrid-validierung.md`).

## 8. Rückmeldung

Am Ende in `TODO_AKTUELL.md` und `PC_WECHSEL_UEBERGABE.md` einen neuen obersten Block
mit Commit-Hashes, Testzahlen, Deploy-Nachweis und offenen Punkten eintragen; keine
historischen Blöcke löschen. Berichte mit n, Intervall und Stichprobenherkunft.
