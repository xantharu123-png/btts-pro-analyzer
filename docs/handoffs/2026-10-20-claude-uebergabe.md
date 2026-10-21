# Code-Übergabe: Claude-Audit-Reparaturen, Stand 20.10.2026

Für Codex, den Owner und jede weitere Session. Ergänzt `AGENTS.md` (Regeln, Stand) und
`docs/audits/2026-10-19-audit-reparaturen.md` (fachliches Protokoll mit Zahlen).

## 1. Wo der Code liegt

| Was | Wert |
|---|---|
| Branch | `claude/audit-repairs-20261019` (auf GitHub) |
| Worktree | `C:\Projekt\BetBoy\betboy-app\.worktrees\claude-audit-repairs-20261019` |
| Basis | `origin/main` @ `be5e441` (18.10.2026); `origin/main` ist seither unverändert |
| Pull Request | https://github.com/xantharu123-png/btts-pro-analyzer/pull/1 (offen, mergefähig) |
| Umfang | 16 Commits, 59 Dateien, +13 693 / −50 Zeilen |
| Nicht berührt | Hauptcheckout `betboy-app` (fremdes WIP, 60 Commits hinter `origin/main`), Codex-Worktree `.worktrees/audit-repairs-20261013` (18 ungesicherte Änderungen, 7 unveröffentlichte Commits) |
| Deployment | keines; VPS unverändert |

## 2. Commits in Reihenfolge

| Commit | Inhalt |
|---|---|
| `b959448` | Daily3-Preisgate bei der Vormerkung, Mindestquote auf der Karte, Shin/Power-De-Vig, Marktbenchmark-Pipeline |
| `9065df8` | Dixon-Coles-Modul, Engine-Schalter `goal_model`, Paritätstests |
| `d967e1f` | Daily3-Gate hinter Schalter, ρ-Projektion, `AGENTS.md`, Übergabeblöcke |
| `31ce080` | Marktbenchmark-Ergebnis 14 Ligen |
| `50b585a` | Dixon-Coles-Vergleich 14 Ligen |
| `7108b60` | Daily3-Gate standardmässig aktiv (Owner 20.10.) |
| `ffabfdc` | Karte bleibt (Owner 20.10.), Plan Dixon-Coles-Niveau |
| `cf31ddd` | Dixon-Coles-Varianten H1/H2, Hybrid H3 im Vergleich, Benchmark-Zeilen und Verdikt-Dokument |
| `f93f089` | Markt-Freigabebedingung (Default aus), Mischungsanalyse |
| `fd5fd70` | Rechtsfooter 18+/Spielsucht, Kundenzugang fail-closed bei Portal-Token |
| `8541d2e` | CI (quick/full), Ruff-Minimalkonfiguration, Lockfiles |
| `9f1bf00` | Doku Markt-Gate, Mischung, Varianten |
| `09c3040` | Benjamini-Hochberg über Ligen × Märkte, Engine-Gate akzeptiert Vielfaches des Katalogs |
| `f72e9ee` | Tennis-Kalibrierung auf gewetteter Population (Option), Mischungsbericht |
| `8410282` | Benchmark-Bericht neu erzeugt (identische Zellen) |
| `a222ac6` | Varianten-Ergebnisse, finale Übergabeblöcke |

## 3. Dateien nach Bereich

**Produktverhalten (Default geändert)**
- `daily3_selection.py`: `Daily3Choice.minimum_odds`, `offer_odds`, `price_blocked`;
  `reservation_minimum_enforced()`, `reservation_minimum_odds()`, `admitted_offer_odds()`.
  Auswahl bleibt preisblind (bestehende Invarianztests unverändert).
- `daily3_ui.py`: Hinweis je Auswahl, Vormerkung nur ab Mindestquote
  (`_require_reservation_price`, `_reservation_block_reason`), Regeltext.
- `wettfinder_surface.py`: Karte mit Zelle „Mindestquote“ und Zeile `se-price-status`.
- `editorial_theme.py`: vierspaltiges `.se-pick`, Styles für Schwelle und Status.
- `legal_notice.py` (neu), `app.py`: Footer mit 18+, Spielsucht-Hilfe, Rechtslinks aus Env
  oder ehrlicher Platzhalter, Modus-Hinweis „Persönlicher Modus“.
- `customer_access.py`: `access_mode()`; ohne Flag erzwungen, sobald
  `BETBOY_PORTAL_INTERNAL_TOKEN` gesetzt ist.
- `cross_league_fdr.py` (neu), `challenge_15k.py`: BH über alle Ligen eines Laufs
  (`_family_adjusted_validations`, Default an).
- `challenge_engine.py`: `_credible_statistical_release_validation` akzeptiert
  `tested_hypotheses` als ganzzahliges Vielfaches von `len(MARKET_SPECS)` (nötig für die
  Ligen-Familie); sonst nur Opt-in-Pfade (unten).

**Opt-in / Analyse (Default byteidentisch)**
- `challenge_engine.py`: `score_matrix(..., rho=0.0)`, `GOAL_MODEL_LEGACY`,
  `GOAL_MODEL_OPTIONS` (dixon_coles, _hl240, _hl365, _level, _hl240_level), Parameter
  `goal_model` in `_fixture_model`, `fixture_market_probabilities`,
  `_walk_forward_market_records`; Markt-Sperrgrund in `build_fixture_candidates`.
- `football_dixon_coles.py` (neu): zeitgewichtete DC-MLE, analytischer Gradient,
  `clamp_rho`, `fit_for_fixture` (Cache je Liga/Tag/Historie/Optionen), `last_fit`.
- `betting_math.py`: `shin_no_vig_market`, `power_no_vig_market`, `no_vig_market`,
  `NoVigMarket.method`, `blended_decision_probability`.
- `market_benchmark_history.py` (neu): Preisspalten der football-data-CSVs, getrennt vom
  quotenblinden Modell-Loader, Join über dieselbe Pseudo-Fixture-ID.
- `market_benchmark.py` (neu): Walk-forward-Spiegel des Release-Gate-Builders mit
  Fixture-IDs, Zellen (Brier/LogLoss/HAC/BH), Policy-Replay mit Bootstrap, Zeilen-Dump,
  Verdikt-Dokument.
- `market_release_gate.py` (neu): optionale Freigabebedingung aus dem Verdikt-Dokument.
- `market_blend.py` (neu): Mischungsgewicht per Log-Loss-Raster (70/30 chronologisch),
  Replays mit Mischung und Edge-Cap.
- `tennis/backtest.py`: `calibration_population="all"|"betting"`,
  `calibration_model="platt"|"covariate"`, Default Legacy.
- Skripte: `scripts/download_market_benchmark_data.py`, `scripts/market_benchmark_report.py`,
  `scripts/compare_goal_models.py`, `scripts/estimate_market_blend.py`.

**Technik**
- `pyproject.toml` (pytest-Optionen, Ruff `E9,F63,F7,F82`, per-file-ignore für zwei
  eingefrorene Tennis-Fixtures), `requirements.lock`, `portal/requirements.lock`,
  `.github/workflows/tests.yml` (Job `quick` bei Push/PR, Job `full` manuell).

**Tests (13 Dateien neu oder erweitert)**
`test_cross_league_fdr`, `test_customer_access`, `test_daily3_selection`, `test_daily3_ui`,
`test_football_dixon_coles`, `test_legal_notice`, `test_market_benchmark`, `test_market_blend`,
`test_market_release_gate`, `test_no_vig_methods`, `test_sports_editorial`,
`test_tennis_calibration_population`, `test_unified_navigation`.

**Dokumentation**
`AGENTS.md`, `README.md` (Verweis), `AUDIT_BERICHT_2026-10-16_CLAUDE.md` (ins Repo kopiert),
`docs/audits/2026-10-19-audit-reparaturen.md` (Protokoll), `docs/audits/2026-10-19-marktbenchmark.md`,
`docs/audits/2026-10-19-dixon-coles-vergleich.md`, `docs/audits/2026-10-20-dixon-coles-{hl240,hl365,level,hl240-level}.md`,
`docs/audits/2026-10-20-marktmischung.md`, `docs/audits/2026-10-20-fdr-ligen.md`,
`docs/audits/2026-10-20-rechtsseiten-kundenzugang.md`, `docs/audits/2026-10-20-tennis-kalibrierung-population.md`,
`docs/audits/2026-10-20-ci-lockfile.md`, `docs/legal/impressum-vorlage.md`, `docs/legal/datenschutz-vorlage.md`,
`docs/superpowers/plans/2026-10-20-dixon-coles-niveau.md`, `deploy/README.md` (Env-Abschnitt),
`TODO_AKTUELL.md` und `PC_WECHSEL_UEBERGABE.md` (oberster Block).

## 4. Schalter und Umgebungsvariablen

| Variable | Default | Wirkung | Ort |
|---|---|---|---|
| `BETBOY_DAILY3_RESERVATION_MINIMUM` | aktiv (nur `0` schaltet ab) | Daily3-Vormerkung nur ab Mindestquote der Auswahl | `daily3_selection.reservation_minimum_enforced` |
| `BETBOY_CUSTOMER_ACCESS_REQUIRED` | nicht gesetzt = erzwungen, wenn `BETBOY_PORTAL_INTERNAL_TOKEN` gesetzt; `0` persönlich; `1` erzwungen | Kundenzugang | `customer_access.access_mode` |
| `BETBOY_LEGAL_URL`, `BETBOY_PRIVACY_URL`, `BETBOY_TERMS_URL` | leer = Platzhaltertext | Rechtslinks im Footer (alle drei nötig, https oder relativ) | `legal_notice.legal_links` |
| `BETBOY_CROSS_LEAGUE_FDR` | `1` | BH über Ligen × Märkte; `0` = je Liga wie bisher | `challenge_15k.cross_league_fdr_enabled` |
| `BETBOY_RELEASE_MARKET_BENCHMARK` | `0` | Sperrgrund, wenn Liga×Markt den Closing-Markt nicht geschlagen hat; `1` leert derzeit jeden Echtgeldpfad | `market_release_gate` |
| `BETBOY_MARKET_GATE_PATH` | `runtime_state/market_benchmark/market_gate.json` | Verdikt-Dokument (höchstens 120 Tage alt) | `market_release_gate.gate_path` |
| `goal_model=` (Funktionsparameter) | `legacy` | DC-Varianten nur per expliziter Übergabe; kein Produktionsaufrufer setzt ihn | `challenge_engine` |

**Vor dem nächsten Deploy prüfen:** Steht `BETBOY_PORTAL_INTERNAL_TOKEN` bereits in
`/etc/betboy/betboy.env`, ohne dass das Portal live ist, sperrt die App fail-closed. Dann
`BETBOY_CUSTOMER_ACCESS_REQUIRED=0` setzen oder den Token entfernen (`deploy/README.md`).

## 5. Datenartefakte (nicht in Git)

`runtime_state/market_benchmark/` im Worktree: 98 football-data-CSVs (14 Ligen,
2019/20–2025/26, ≈17 MB), `rows.jsonl` (266 062 Zeilen), `market_gate.json` (112 Zellen),
`bench_full.json`, `legacy_raw*.json` (Caches der Variantenläufe). Neu erzeugen:

```powershell
cd C:\Projekt\BetBoy\betboy-app\.worktrees\claude-audit-repairs-20261019
..\..\.venv\Scripts\python.exe scripts\download_market_benchmark_data.py
..\..\.venv\Scripts\python.exe -W ignore scripts\market_benchmark_report.py --output docs\audits\2026-10-19-marktbenchmark.md --rows runtime_state\market_benchmark\rows.jsonl --gate-json runtime_state\market_benchmark\market_gate.json   # ≈ 23 min
..\..\.venv\Scripts\python.exe scripts\estimate_market_blend.py --rows runtime_state\market_benchmark\rows.jsonl --output docs\audits\2026-10-20-marktmischung.md   # ≈ 3 min
..\..\.venv\Scripts\python.exe -W ignore scripts\compare_goal_models.py --variant dixon_coles_hl365 --legacy-cache runtime_state\market_benchmark\legacy_raw.json --output docs\audits\2026-10-20-dixon-coles-hl365.md   # ≈ 60–90 min
```

## 6. Prüfbefehle

```powershell
..\..\.venv\Scripts\python.exe -m ruff check .
..\..\.venv\Scripts\python.exe -m pytest tests/test_daily3_selection.py tests/test_daily3_ui.py tests/test_sports_editorial.py tests/test_no_vig_methods.py tests/test_market_benchmark.py tests/test_football_dixon_coles.py tests/test_market_release_gate.py tests/test_market_blend.py tests/test_cross_league_fdr.py tests/test_legal_notice.py tests/test_customer_access.py tests/test_tennis_calibration_population.py tests/test_calibration.py -q
```

## 7. Testnachweise

| Lauf | Ergebnis |
|---|---|
| Daily3, Karte, Preisboden, Publikation, Kontext-Admission (15 Module) | 529 passed |
| Kartenrenderer und Konsumenten (13 Module) | 395 passed |
| 15K, Wettfinder-Automation, Workflow-Integrität, Joint-Worker u. a. (13 Module) | 580 passed |
| Engine-Module inkl. byteexakter Golden-Tests | 274 passed |
| FDR, 15K, Kalibrierung, Statistik, DC, Gate | 264 passed |
| Rechtshinweise, Kundenzugang, Navigation, Workflow | 181 passed |
| Tennis (Populationsfit, Policy, Predict, Live-Training) | 74 passed |
| No-Vig, Benchmark, Dixon-Coles, Gate, Mischung | 31 passed |
| Ruff (817 Dateien) | 0 Befunde |
| GitHub Actions `quick` (Linux, Ruff + 180 Tests) | grün |
| GitHub Actions `full` / `full-a`+`full-b` (Linux) | Einzelprozess: Exit 137 bei 36 %. Zwei Hälften (21.10.): B 7 660 bestanden / 21 runner-spezifische Fehlschläge, A erneut Exit 137. Der Linux-Vollnachweis bleibt die VPS-QA (Gruppen A/B); siehe Protokoll. |

Alle Windows-Läufe aus dem Worktree mit `..\..\.venv\Scripts\python.exe -m pytest`.

## 8. Ergebnisse in einem Absatz

Walk-forward-Modell gegen No-Vig-Pinnacle-Closing über 14 Ligen und 33 275 Spiele: 0 von
112 Zellen schlagen den Markt; Replay der Preispolicy 34 484 Wetten, ROI −5,5 % [−7,2; −3,6],
CLV −1,0 %. Mischungsgewicht Modell/Markt out-of-sample 0,00 in allen Märkten. Edge-Cap 8 pp
hebt die Policy auf +0,8 % ROI (Intervall enthält 0). Dixon-Coles: Halbwertszeit 240/365 Tage
bestätigt, Niveau-Prior widerlegt, Hybrid (DC Ergebnismärkte + Legacy Tormärkte) dominiert
(56 Zellen signifikant besser, 32 schlechter, von 560); kein Modell schlägt den Markt. Tennis-
Populationsfit ohne nachweisbaren Vorteil (nur 2024 prüfbar). FDR über Ligen: Grenzfall-Ligen
verlieren Freigaben, starke behalten sie.

## 9. Offen, Entscheidungen, Risiken

1. **Merge:** PR #1 ist CI-grün und mergefähig. Codex hat im Reparatur-Worktree 7
   unveröffentlichte Commits und 18 ungesicherte Änderungen; nach einem Merge muss Codex
   `main` einmergen (Konflikte zu erwarten in `TODO_AKTUELL.md`, `PC_WECHSEL_UEBERGABE.md`,
   evtl. `challenge_15k.py`). Owner-Entscheidung: jetzt mergen oder auf Codex warten.
2. **Deploy-Vorbedingung:** Env auf dem VPS prüfen (Abschnitt 4). Release über den
   geprüften No-Backup-Weg; keine Backups laut Owner.
3. **Rechtstexte:** Vorlagen ausfüllen, juristisch prüfen, als Seiten veröffentlichen,
   die drei URL-Variablen setzen. Vorher ist der Footer ehrlich „noch nicht veröffentlicht“.
4. **Modellpolitik:** Markt-Gate aktivieren = keine Freigaben; Mischung mit Markt-p braucht
   den vollständigen No-Vig-Markt aller Seiten im Quotenabruf (heute nur die gewettete Seite).
   Nächste Hypothese H4: venue-spezifische Parameter im DC-Fit; kohärente Konstruktion des
   Hybrids für die gemeinsame Kalibrierung.
5. **Linux-Vollnachweis:** siehe Abschnitt 7.
6. **Nicht umgesetzt, weil Nutzerentscheidung vom 17.10.:** Bottom-Navigation,
   marktdefinierter Aussenseiter, Sortierung nach Evidenz, Einstellungen in der Navigation,
   Backup-Timer. Grosse Umbauten (Importzyklen, Logging, DB-Konsolidierung, Token-Set,
   Währung, Formatter) bleiben technische Schuld.
7. **Nebenbefunde:** `tennis/backtest._devig` lässt NaN-Preise durch (12 Zeilen 2024);
   `atp_tournaments.csv` hat Endtermine erst ab 2024.

## 10. Owner-Entscheidungen, die in diesem Branch gelten

- 17.10.2026 (`docs/audits/2026-10-17-claude-gegenpruefung.md`): keine Backups, obere
  Navigation, keine Badge-Wand, Einstellungen nicht in der Kundennavigation.
- 20.10.2026: Daily3-Vormerk-Gate aktiv; Karte mit Mindestquote und Preisstatus bleibt;
  alle offenen Audit-Punkte angehen; Push und PR.
