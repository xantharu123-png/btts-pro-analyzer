# Audit-Reparaturen 19.10.2026 (Claude), Branch `claude/audit-repairs-20261019`

Grundlage: `AUDIT_BERICHT_2026-10-16_CLAUDE.md`. Basis des Branches: `origin/main` @
`be5e441` (18.10.2026). Hauptcheckout und Codex-Worktree blieben unberührt. Alle
Änderungen liegen als WIP-Commits auf dem Branch; nichts wurde gepusht oder deployt.

## Umgesetzt

### 1. Daily3: Preisgate bei der Echtgeld-Vormerkung (Audit K4)

- `daily3_selection.py`: `Daily3Choice` trägt `minimum_odds` (= max(1,20; Risiko-
  Mindestquote der Prognose aus `ModelSignal.minimum_odds`)) und `offer_odds` (bestes
  aktuelles, exakt gebundenes Angebot aus dem Publikationsnachweis). `price_blocked`
  ist wahr ohne belastbares Minimum oder wenn das Angebot darunter liegt. Beides ist
  **keine Auswahl- oder Ranking-Eingabe**: die bestehenden Tests
  `test_prices_release_flags_and_pool_iteration_cannot_reorder_forecasts` und
  `test_defensive_profile_never_uses_an_unexplained_high_probability_or_haircut`
  verlangen eine preisblinde Auswahl; sie bleiben unverändert grün.
- `daily3_ui.py`: Je Auswahl Hinweis „Mindestquote für diese Auswahl: X · zuletzt
  beobachtet Y“. Liegt das beobachtete Angebot unter dem Minimum, erscheint eine
  Warnung und kein Vormerkformular (die Prognose bleibt sichtbar; nach Spielbeginn plant
  die Tagesfolge neu). Beim Absenden prüft `_require_reservation_price` die eingegebene
  Quote erneut gegen das Minimum der aktuell gültigen Auswahl; der globale 1,20-Boden
  bleibt im Store (`daily3_store`). Regeltext im Popover angepasst.
- Bewusst **nicht** umgesetzt: Preisfilter in der Auswahl selbst. Das hätte die
  getestete Invariante „Mindestquote/Haircut verändern die Auswahl nicht“ gebrochen.
  Folge bei aktivem Gate: Ist der früheste Slot preislich gesperrt, kann bis zu dessen
  Anpfiff keine Vormerkung erfolgen (fail-closed, dokumentiert im UI-Text).
- **Konflikt mit der Nutzerregel vom 17.10.2026** (`docs/audits/2026-10-17-claude-
  gegenpruefung.md`, A1/K4: „Daily3 ohne EV-/Echtgeld-Preisfreigabe; 1,20-Boden
  bleibt“): Das Vormerk-Gate ist deshalb nur mit `BETBOY_DAILY3_RESERVATION_MINIMUM=1`
  aktiv (`daily3_selection.reservation_minimum_enforced`). Ohne Flag gilt die
  Nutzerregel unverändert; Mindestquote und Angebot werden nur informativ angezeigt.
  Entscheidung des Owners: Flag setzen, Flag entfernen oder Gate verwerfen.
- Tests: `tests/test_daily3_selection.py` (+1), `tests/test_daily3_ui.py` (+3; die
  Flow-Fixtures setzen das Minimum nun explizit, damit ein Angebot 1,80 über dem
  Minimum liegt), bestehende Daily3-Module grün.

### 2. Karte: Mindestquote und Preisstatus auf erster Ebene (Audit K5/H10)

- `wettfinder_surface.render_editorial_card_html`: vierte Zelle „Mindestquote“
  (`value_threshold`, „–“ wenn unbekannt) und eine Statuszeile `se-price-status`
  (`price_label` + Preisnotiz, Tonklasse). Gilt für Wettfinder, Daily3 und 15K-
  Modellauswahl, weil alle dieselbe Karte rendern. Der 15K-Fall aus dem Audit (Quote
  1,27 bei Modell 76,4 %) zeigt jetzt „Unter Value · Quote unter Value.“ neben der
  Mindestquote.
- `editorial_theme.py`: `.se-pick` vierspaltig (Desktop und Mobil), Styles für
  `.se-number-threshold` und `.se-price-status`.
- Test: `tests/test_sports_editorial.py::test_card_first_level_shows_minimum_odds_and_price_status`;
  alle 11 Module, die die Karte rendern, grün (395 Tests).

### 3. Shin- und Power-De-Vig (Audit C2)

- `betting_math.py`: `shin_no_vig_market`, `power_no_vig_market`, `no_vig_market(odds,
  method)`; `NoVigMarket.method`. Proportional bleibt Default und unverändert.
- Test `tests/test_no_vig_methods.py`: Handwerte aus dem September-Anhang A4
  (1,30/5,50/10,0 → Aussenseiter fair 5,78 / ≈6,00 / ≈6,22) bestätigt.

### 4. Marktbenchmark: Modell gegen No-Vig-Closing (Audit K2, H5, H6)

- `market_benchmark_history.py`: liest die Preisspalten der football-data-CSVs in eine
  **getrennte** Tabelle (Pinnacle/Bet365/Max/Avg, 1X2 und Über/Unter 2,5, Closing
  bevorzugt, sonst als `closing=False` markiert), gejoint über dieselbe Pseudo-Fixture-ID
  wie `football_data_history.parse_history_csv`. Der Modell-Loader bleibt quotenblind
  (Test prüft, dass kein Preisfeld im Modell-Fixture auftaucht).
- `market_benchmark.py`: `walk_forward_model_probabilities` spiegelt
  `_walk_forward_market_records` (Tagesgruppierung, Kalibrier-Refit nach Tagesende) und
  behält Fixture-IDs; Paritätstest gegen den Engine-Builder. Zellen je Liga×Markt mit
  Brier/LogLoss Modell vs. Markt, gepaartem Vorteil (HAC) und BH über die gesamte
  Familie. Replay der Preisgate-Policy (generischer Haircut 5 pp, 3 % Risiko-ROI, Boden
  1,20) gegen den besten Closing-Preis mit Bootstrap-Intervallen für ROI und CLV.
- Skripte: `scripts/download_market_benchmark_data.py` (98 Dateien, 14 Ligen,
  Saisons 2019/20 bis 2025/26, ≈17 MB unter `runtime_state/market_benchmark/`),
  `scripts/market_benchmark_report.py`.
- Erster Lauf Premier League 2023–2024 (628 Spiele, Closing-Anteil 100 %): Modell in
  allen acht Zellen schlechter als der Markt (z. B. Heimsieg Brier 0,2265 vs. 0,2049).
  Policy-Replay: 830 Wetten, Ø Modell−Markt +12,0 pp, 82 % der Wetten über 8 pp,
  CLV −0,6 % [−0,9; −0,4], ROI −2,7 % [−13,9; +8,8]; Heimsieg-Wetten ROI −23,5 %
  [−42,0; −4,3] bei Trefferquote 19,6 %. Das ist das Winner's-Curse-Muster aus K3.
- Vollständiger Lauf über 14 Ligen: `docs/audits/2026-10-19-marktbenchmark.md`
  (siehe Abschnitt „Ergebnisse“ unten).

### 5. Dixon-Coles-MLE als Opt-in (Audit H1)

- `football_dixon_coles.py`: Angriff/Abwehr multiplikativ, Heimvorteil, ρ (Grenzen
  ±0,25), exponentieller Zeitdecay (Halbwertszeit 120 Tage, Historie 730 Tage), milde
  Ridge-Schrumpfung, analytischer Gradient (Finite-Differenzen-Test), L-BFGS-B.
  Fail-closed unter 40 Spielen oder 4 Spielen je Team. Kein Import aus
  `challenge_engine` (kein Zyklus).
- `challenge_engine.py`: `score_matrix(..., rho=0.0)` (ρ=0 byteidentisch),
  `GOAL_MODEL_LEGACY`/`GOAL_MODEL_DIXON_COLES`, Parameter `goal_model` in
  `_fixture_model`, `fixture_market_probabilities`, `_walk_forward_market_records`. Im
  DC-Pfad ersetzen die gefitteten Raten alle drei Legacy-Varianten (Spread 0); kein
  ORIGINAL-Capture, kein Rückfall. Kein Produktionsaufrufer setzt den Schalter.
- Tests `tests/test_football_dixon_coles.py`: Parameter-Rückgewinnung auf exakt
  DC-verteilten Stichproben (Heim ±0,08, ρ ±0,06, Stärken r > 0,9), Gradient,
  ρ=0-Parität, Default-Pfad unverändert, Opt-in fail-closed. Die byte-exakten
  Golden-Tests in `tests/test_calibration.py` bleiben grün (274 Tests der
  Engine-Module).
- Vergleich: `scripts/compare_goal_models.py` →
  `docs/audits/2026-10-19-dixon-coles-vergleich.md`.

## Testläufe (Windows, Worktree)

| Lauf | Ergebnis |
|---|---|
| Daily3, Karte, Preisboden, Publikation, Vergleich, Kontext-Admission (15 Module) | 529 passed |
| Kartenrenderer und Konsumenten (13 Module) | 395 passed |
| No-Vig, Benchmark, Dixon-Coles | 18 passed |
| Engine-Module (Kalibrierung, Joint, Kontext, Replay, ORIGINAL) | 274 passed |
| Grosse Module (15K, Wettfinder-Automation, Workflow-Integrität, …) | siehe Nachtrag |

## Ergebnisse der Läufe

Wird nach Abschluss der beiden Terminal-Läufe ergänzt (Marktbenchmark 14 Ligen,
Dixon-Coles-Vergleich).

## Nicht umgesetzt (braucht den Owner)

- API-Schlüssel: laut Gegenabgleich am 17.10.2026 bereits ersetzt und auf dem VPS
  aktiv; der Widerruf der alten Werte beim Anbieter ist nicht bewiesen. Der veraltete
  Hauptcheckout trägt die alten Werte noch in `config.ini`.
- Backup-Timer: auf ausdrücklichen Nutzerwunsch deaktiviert (Gegenabgleich K6); das
  Wiederherstellungsrisiko zwischen Deploys bleibt.
- Kartenänderung (Mindestquote, Preisstatus) gegen die UX-Entscheidung „keine
  Badge-Wand, keine Preisfreigabe-Aktion“ (Gegenabgleich U1/H10) abwägen: es ist eine
  Zahl und eine Zeile, keine Aktion; zurücknehmen ist ein Revert von
  `wettfinder_surface.render_editorial_card_html` und `editorial_theme.py`.
- Impressum, Datenschutz, Altershinweis, Spielsucht-Link (Rechtstexte).
- Aktivierung von Dixon-Coles oder des Marktbenchmarks als Release-Bedingung: beides
  erst nach Lektüre der Berichte und mit vorab definierter Hypothese (Bibel §3.5).

## Verifikation für Codex

```powershell
cd C:\Projekt\BetBoy\betboy-app\.worktrees\claude-audit-repairs-20261019
..\..\.venv\Scripts\python.exe -m pytest tests/test_daily3_selection.py tests/test_daily3_ui.py tests/test_sports_editorial.py tests/test_no_vig_methods.py tests/test_market_benchmark.py tests/test_football_dixon_coles.py tests/test_calibration.py -q
```

Merge nach `main` erst nach Codex' laufender Arbeit und nach einem Linux-Volllauf.
