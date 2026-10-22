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
  bleibt“): Das Vormerk-Gate wurde zunächst als abschaltbare Option gebaut und dem
  Owner vorgelegt. **Entscheidung des Owners am 20.10.2026: Gate standardmässig
  aktiv.** `daily3_selection.reservation_minimum_enforced` liest
  `BETBOY_DAILY3_RESERVATION_MINIMUM`; nur der Wert `0` schaltet ab, dann werden
  Mindestquote und Angebot nur informativ angezeigt (Test
  `test_flag_zero_makes_the_minimum_informational_only`).
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

### 6. Nachtrag 20.10.2026: Markt-Freigabebedingung, Mischung, Varianten

- `market_release_gate.py`: optionale zweite Freigabebedingung. `build_fixture_candidates`
  fügt den Sperrgrund „Marktbenchmark gegen No-Vig-Closing nicht bestanden“ hinzu, wenn
  `BETBOY_RELEASE_MARKET_BENCHMARK=1` gesetzt ist und die Zelle im Verdikt-Dokument
  (`--gate-json` des Benchmarks, Pfad `BETBOY_MARKET_GATE_PATH`, höchstens 120 Tage alt)
  nicht als „Markt geschlagen“ steht. Default aus, weil die Nutzerregel vom 17.10. ein
  hartes Marktgate ablehnt und weil derzeit 0 von 112 Zellen bestehen: Aktivieren leert
  jeden Echtgeldpfad. Tests `tests/test_market_release_gate.py`.
- `betting_math.blended_decision_probability`, `market_blend.py`,
  `scripts/estimate_market_blend.py`: Entscheidungs-p als Log-Odds-Mischung, Gewicht per
  Log-Loss-Raster auf den ersten 70 % der Benchmarkzeilen, Bewertung auf den letzten 30 %;
  Replay der Policy mit Mischung und Edge-Cap 8 pp. Bericht
  `docs/audits/2026-10-20-marktmischung.md`. Tests `tests/test_market_blend.py`.
- Dixon-Coles-Varianten (`GOAL_MODEL_OPTIONS`): Halbwertszeit 240/365 Tage, Niveau-Prior
  (Momentenabgleich auf das ungewichtete Fenstermittel), Hybrid H3 im Vergleichsskript.
  Berichte `docs/audits/2026-10-20-dixon-coles-*.md`.

## Testläufe (Windows, Worktree)

| Lauf | Ergebnis |
|---|---|
| Daily3, Karte, Preisboden, Publikation, Vergleich, Kontext-Admission (15 Module) | 529 passed |
| Kartenrenderer und Konsumenten (13 Module) | 395 passed |
| No-Vig, Benchmark, Dixon-Coles | 18 passed |
| Engine-Module (Kalibrierung, Joint, Kontext, Replay, ORIGINAL) | 274 passed |
| Grosse Module (15K, Wettfinder-Automation, Workflow-Integrität, …) | 580 passed |
| GitHub Actions `quick` (Linux, Ruff + 180 Tests) | grün (PR #1 und PR #2) |
| GitHub Actions `full` (Linux, Vollsuite, 20.10.) | nach 27 min bei 36 % mit Exit 137 vom Runner beendet (Speicherlimit), bis dahin kein Fehlschlag |
| GitHub Actions `full-a`/`full-b` (Linux, zwei Hälften, 21.10.) | B: 7 660 bestanden, 21 fehlgeschlagen in 16:43 (`git show <sha>` im flachen Checkout, danach `fetch-depth: 0`; runner-spezifische Deskriptor-, Ressourcen- und Zeitzonen-Diagnostik in `test_native_context_*`, `test_team_form_transport`). A: erneut Exit 137 nach 8 min. Der 7-GB-Runner trägt die Suite nicht; der Linux-Vollnachweis bleibt die VPS-QA (Gruppen A/B). Keines der fehlgeschlagenen Module wurde in diesen Branches verändert |

## Ergebnisse der Läufe

### Marktbenchmark, 14 Ligen, Saisons 2019/20 bis 2025/26 (`docs/audits/2026-10-19-marktbenchmark.md`)

Datenbasis: 36 369 Spiele, 33 304 Walk-forward-Prognosen, 33 275 davon mit
Pinnacle-Closing (Closing-Anteil 100 %). Laufzeit 1355 s.

| Markt (14 Zellen je Markt) | n | Brier Modell | Brier Markt | Ø Vorteil Modell−Markt | Zellen Modell schlechter | Zellen Markt geschlagen |
|---|---:|---:|---:|---:|---:|---:|
| Heimsieg | 33 275 | 0,2272 | 0,2131 | −0,0142 | 14/14 | 0 |
| Remis | 33 275 | 0,1896 | 0,1875 | −0,0021 | 14/14 | 0 |
| Auswärtssieg | 33 275 | 0,1999 | 0,1879 | −0,0120 | 14/14 | 0 |
| Doppelte Chance (3 Zellen × 14) | 33 275 | wie Einzelmärkte | | | 42/42 | 0 |
| Über/Unter 2,5 | 33 206 | 0,2469 | 0,2405 | −0,0065 | 28/28 | 0 |

**Kein einziger Liga×Markt-Fall, in dem das Modell den No-Vig-Closing-Markt schlägt**
(HAC-Untergrenze > 0 und BH-q ≤ 0,05): 0 von 112. In allen 112 Zellen ist das Modell im
Mittel schlechter. Das bestätigt Audit K2: Der Basisraten-Skill des Release-Gates ist
kein Markt-Skill.

Replay der Preisgate-Policy (generischer Haircut 5 pp, 3 % Risiko-ROI, Boden 1,20,
bester Closing-Preis, Einsatz 1 Einheit):

| Teilmenge | Wetten | Trefferquote | ROI | ROI 90 %-Bootstrap | CLV | CLV 90 %-Bootstrap | Ø Modell−Markt | Anteil > 8 pp |
|---|---:|---:|---:|---|---:|---|---:|---:|
| alle | 34 484 | 26,3 % | −5,5 % | [−7,2; −3,6] | −1,0 % | [−1,2; −0,8] | +11,0 pp | 76 % |
| Heimsieg | 9 189 | 25,6 % | −4,2 % | [−7,3; −1,1] | +0,4 % | [−0,0; +1,1] | +11,9 pp | 79 % |
| Remis | 2 932 | 14,1 % | −6,8 % | [−13,9; +0,7] | −1,9 % | [−2,2; −1,6] | +8,7 pp | 56 % |
| Auswärtssieg | 11 946 | 18,2 % | −6,8 % | [−10,1; −3,1] | −1,4 % | [−1,5; −1,3] | +11,0 pp | 75 % |
| Über 2,5 | 4 537 | 43,2 % | −3,4 % | [−6,2; −0,6] | −1,3 % | [−1,3; −1,2] | +10,3 pp | 77 % |
| Unter 2,5 | 5 880 | 37,3 % | −6,0 % | [−8,7; −3,2] | −1,9 % | [−2,0; −1,8] | +11,5 pp | 82 % |

Lesart: Die Policy wettet im Mittel dort, wo das Modell den Markt um 11 Prozentpunkte
übertrifft; drei Viertel der Wetten liegen über der im Audit vorgeschlagenen 8-pp-Kappung.
Der realisierte ROI ist in jeder Teilmenge negativ, der CLV gegen die No-Vig-Closing-Line
ebenfalls (Ausnahme Heimsieg mit +0,4 % CLV bei dennoch −4,2 % ROI). Das ist das
Winner's-Curse-Muster aus Audit K3: Das Gate selektiert Modellfehler, keine Information.

Einschränkungen, die den Befund **nicht** aufheben, aber einordnen:
- Closing-Preise enthalten Aufstellungen und spätes Geld; ein reines Ergebnismodell
  liegt erwartungsgemäss dahinter. Die Produktpolicy gibt jedoch genau zum Closing frei
  (Audit B5 vom 02.09.).
- Historie hier ohne xG (football-data liefert keine); produktive Ligen mit xG-Blend
  könnten etwas besser sein. Erste Saison je Liga dient als Aufwärmphase.
- Wetten desselben Spiels auf mehreren Märkten sind korreliert; die Bootstrap-
  Intervalle sind deshalb eher zu schmal.
- Der generische 5-pp-Haircut ist die mildeste Fassung des Gates; produktive Haircuts
  (3 bis 20 pp) reduzieren die Wettzahl, ändern aber den Selektionsmechanismus nicht.
- „Bester Closing-Preis“ (Max) ist für die Ausführung optimistisch.

Konsequenz für den Freigabevertrag: Ohne einen Markt-Benchmark darf `RELEASED` keine
Marktaussage transportieren. Empfehlung bleibt wie im Audit: Marktbenchmark als
zusätzliche Bedingung in `_credible_validation`, Entscheidungs-p als Log-Odds-Mischung
mit dem Markt plus Edge-Kappung; beides nur mit vorab definierter Hypothese.

### Mischungsgewicht Modell/Markt (`docs/audits/2026-10-20-marktmischung.md`)

266 062 Benchmarkzeilen (14 Ligen, fünf Direktmärkte plus Doppelte Chance), Gewicht w per
Log-Loss-Raster auf den chronologisch ersten 70 %, Bewertung auf den letzten 30 %:

| Markt | Test-Zeilen | w* (Modellanteil) | LogLoss Modell | LogLoss Markt | LogLoss Mischung |
|---|---:|---:|---:|---:|---:|
| alle | 49 872 | **0,00** | 0,6346 | 0,6158 | 0,6158 |
| Heimsieg | 9 983 | 0,00 | 0,6465 | 0,6135 | 0,6135 |
| Remis | 9 983 | 0,00 | 0,5700 | 0,5647 | 0,5647 |
| Auswärtssieg | 9 983 | 0,00 | 0,5816 | 0,5525 | 0,5525 |
| Über/Unter 2,5 | 9 962 | 0,00 | 0,6875 | 0,6742 | 0,6742 |

**Das Modell trägt out-of-sample keine Information über den No-Vig-Closing-Markt hinaus
bei.** Das ist die schärfste Form des Befunds K2: Nicht nur schlägt das Modell den Markt
nicht, eine optimale Entscheidung ignoriert es vollständig.

Replays (Haircut 5 pp, 3 % Risiko-ROI, Boden 1,20, bester Closing-Preis):

| Variante | Wetten | ROI | ROI 90 % | CLV | CLV 90 % | Ø Modell−Markt |
|---|---:|---:|---|---:|---|---:|
| heutige Policy (w = 1) | 34 420 | −5,5 % | [−7,2; −3,8] | −1,0 % | [−1,2; −0,8] | +11,0 pp |
| + Edge-Cap 8 pp | 8 380 | +0,8 % | [−2,5; +3,9] | +1,5 % | [+1,0; +2,3] | +6,7 pp |
| Mischung w* = 0 (Markt-p) | 236 | +31,6 % | [+17,6; +46,1] | +44,1 % | [+26,7; +72,7] | −6,4 pp |
| Mischung w* = 0 ohne Haircut | 17 389 | +5,1 % | [+3,0; +7,2] | +6,4 % | [+6,1; +6,8] | −0,5 pp |

Lesart, ausdrücklich: Mit w* = 0 ist die „Entscheidungswahrscheinlichkeit“ der Pinnacle-
No-Vig-Preis selbst. Die positiven Replays sind deshalb **kein Modellvorteil**, sondern
Preis-Shopping: Es wird gewettet, wenn irgendein Buchmacher (Max-Spalte, Closing) deutlich
über dem fairen Pinnacle-Preis liegt. Solche Preise sind im echten Betrieb limitiert,
oft Minuten später weg, und Softbooks schliessen Konten, die so wetten. Als Produkt-
versprechen taugt das nicht; als Diagnose zeigt es, wo der einzige messbare Vorteil im
Datensatz liegt. Der Edge-Cap allein (8 pp) hebt die heutige Policy von −5,5 % auf
+0,8 % ROI, weil er die extremsten Modellfehler entfernt; das Intervall enthält 0.

### Tennis-Kalibrierung auf der gewetteten Population (`docs/audits/2026-10-20-tennis-kalibrierung-population.md`)

Hypothese H3 vorregistriert, Umsetzung als Option in `tennis/backtest.py`
(`calibration_population="betting"`, Default Legacy byteidentisch), 16 neue Tests.
Datenbefund: Turnier-Endtermine liegen erst ab 2024 vor, davor ist jeder Backtest
informationslos; prüfbar ist nur 2024 (674 gewettete Zeilen ab 22.07.). Mit den
Produktionsschwellen ist der Populationsfit nicht trainierbar; mit reduzierten
Schwellen ist der Brier-Unterschied zur Gesamtkalibrierung nicht von null verschieden
(−0,0027 [−0,0069; +0,0015] bei n = 174). Das rohe Modell ist auf der Wettpopulation
besser kalibriert als der Legacy-Kalibrator (Brier 0,2179 vs. 0,2200), Pinnacle 0,2050.
**Kein Vorteil nachweisbar, keine Produktionsänderung.** `predict.py`/`model_state.py`
blieben unangetastet (quellgepinnte Replay-Owner). Nebenbefund: `_devig` lässt
NaN-Preise durch (12 Zeilen 2024).

### FDR über Ligen × Märkte (`docs/audits/2026-10-20-fdr-ligen.md`)

`cross_league_fdr.apply_cross_league_fdr` korrigiert q-Werte und
`statistical_release_passed` einmal über alle Ligen eines Laufs (Default an,
`BETBOY_CROSS_LEAGUE_FDR=0` = alt); Einbau in `challenge_15k.scan_daily_challenge` nach der
Validierungsschleife, Cache bleibt je Liga. Das Engine-Gate verlangte genau 96 Hypothesen
und hätte mit der Familie Ligen × 96 jede Freigabe abgelehnt; es akzeptiert jetzt ein
ganzzahliges Vielfaches des Katalogs. Synthetik: 5 Ligen × 96 Zellen, Grenzfall-Ligen
verlieren ihre Freigaben (7 → 0), eine klar starke Liga behält sie (11 → 10).

### Dixon-Coles-Vergleich (`docs/audits/2026-10-19-dixon-coles-vergleich.md`)

14 Ligen, gleiche Saisons, 29 512 gemeinsam prognostizierte Spiele (Dixon-Coles fällt
bei Teams mit weniger als vier Spielen im 730-Tage-Fenster aus, z. B. Aufsteiger zu
Saisonbeginn; Legacy 33 304 Prognosen, DC 29 512). Beide Modelle roh (unkalibriert),
Halbwertszeit 120 Tage, Laufzeit 2388 s.

| Markt (14 Zellen) | Brier DC | Brier Legacy | Vorteil DC−Legacy | DC schlechter | DC signifikant besser (q ≤ 0,05) |
|---|---:|---:|---:|---:|---:|
| Heimsieg | 0,2223 | 0,2287 | +0,0064 | 2/14 | 9 |
| Remis | 0,1896 | 0,1898 | +0,0001 | 8/14 | 0 |
| Auswärtssieg / DC 1X | 0,1954 | 0,2007 | +0,0053 | 3/14 | 8 |
| BTTS Ja/Nein | 0,2526 | 0,2480 | −0,0046 | 14/14 | 0 |
| Über/Unter 2,5 | 0,2516 | 0,2469 | −0,0047 | 13/14 | 0 |
| Über 1,5 / Unter 3,5 | 0,1858 / 0,2067 | 0,1820 / 0,2026 | −0,0038 / −0,0041 | 13–14/14 | 0 |
| Teamtore (über 0,5, unter 1,5) | ≈ gleich | ≈ gleich | −0,001 bis +0,001 | 3–8/14 | 1–3 |

Alle 40 Tormärkte × 14 Ligen: 560 Zellen, DC in 52 signifikant besser, in 346 im Mittel
schlechter. Gefittete ρ je Liga zwischen −0,25 (Griechenland, Türkei, am Rand der
Schranke) und +0,06; Heimvorteil +0,11 bis +0,31 (log), plausibel.

Gegen den No-Vig-Closing-Markt (gleiche 29 487 Spiele): Heimsieg Legacy −0,0156,
DC −0,0093; Auswärtssieg Legacy −0,0132, DC −0,0079 (DC schliesst rund 40 % der Lücke
zum Markt); Über/Unter 2,5 Legacy −0,0065, DC −0,0113 (DC vergrössert die Lücke).
Beide Modelle bleiben in jeder Zelle hinter dem Markt.

Lesart: Die multiplikative Gegnerbereinigung mit ρ verbessert die **Relativstärke**
(Sieg/Niederlage) klar; für das **absolute Torniveau** (Totals, BTTS) ist die Basis-
Konfiguration schlechter als die Legacy-Mittelwerte. Dixon-Coles ist so kein Drop-in-Ersatz.

### Dixon-Coles-Varianten H1–H3 (20.10.2026, `docs/audits/2026-10-20-dixon-coles-*.md`)

Vorregistriert in `docs/superpowers/plans/2026-10-20-dixon-coles-niveau.md`; gleiche 14 Ligen,
29 487 bis 29 512 gemeinsame Spiele. Brier(Kandidat) − Brier(Legacy) über alle Ligen,
negativ = Kandidat besser; Klammern: Ligen schlechter / Ligen signifikant besser (von 14).

| Variante | Heimsieg | Auswärtssieg | BTTS Ja | Über 2,5 | Unter 3,5 | Heim unter 1,5 | Zellen sig. besser / schlechter (von 560) |
|---|---:|---:|---:|---:|---:|---:|---:|
| H0 hl120 (Basis) | −0,0064 (2/9) | −0,0053 (3/8) | +0,0046 (14/0) | +0,0047 (13/0) | +0,0041 (14/0) | −0,0013 (5/3) | 52 / 346 |
| H1 hl240 | −0,0074 (2/10) | −0,0062 (3/11) | +0,0029 (12/0) | +0,0021 (12/0) | +0,0020 (13/0) | −0,0031 (3/3) | 84 / 279 |
| H1 hl365 | −0,0073 (2/10) | −0,0061 (3/10) | +0,0026 (12/0) | +0,0017 (12/0) | +0,0016 (11/0) | −0,0033 (3/3) | 91 / 271 |
| H2 level120 | −0,0064 (2/9) | −0,0053 (3/8) | +0,0047 (14/0) | +0,0049 (14/0) | +0,0041 (14/0) | −0,0013 (5/3) | 50 / 348 |
| H2 hl240+level | −0,0074 (2/10) | −0,0062 (3/11) | +0,0030 (13/0) | +0,0023 (12/0) | +0,0021 (13/0) | −0,0031 (3/3) | 88 / 281 |
| H3 hybrid (hl365) | −0,0073 (2/10) | −0,0061 (3/10) | 0 | 0 | 0 | 0 | 56 / 32 |

Befunde:
- **H1 bestätigt:** Eine längere Halbwertszeit (240/365 Tage) verbessert 1X2 weiter und
  halbiert den Rückstand der Tormärkte, hebt ihn aber nicht auf (Totals/BTTS in 11 bis
  13 von 14 Ligen weiterhin schlechter).
- **H2 widerlegt:** Das Niveau ist nicht das Problem; der Momentenabgleich auf das
  ungewichtete Fenstermittel ändert praktisch nichts.
- **H3 bestätigt:** Der Hybrid (Dixon-Coles für Ergebnis-, Doppelte-Chance- und
  Ergebnis+Total-Märkte, Legacy-Matrix für Totals, BTTS, Teamtore) ist in 56 Zellen
  signifikant besser als Legacy und nur in 32 schlechter; er dominiert beide Einzelmodelle.
- Gegen den Markt (hl365, alle Ligen): Heimsieg-Lücke Legacy +0,0156, DC/Hybrid +0,0083;
  Auswärtssieg +0,0132 → +0,0071; Über 2,5 Legacy +0,0065, DC +0,0082, Hybrid +0,0065.
  Der Hybrid schliesst rund die Hälfte der 1X2-Lücke zum Closing-Markt und bleibt bei
  Totals auf Legacy-Niveau. Kein Modell schlägt den Markt.
- Gefittete ρ (hl365) zwischen −0,19 (Türkei) und +0,03; Heimvorteil +0,11 bis +0,28 (log).
- Der Tormarkt-Nachteil von Dixon-Coles liegt also weder am Niveau noch nur am Decay.
  Plausibler Mechanismus: Legacy nutzt venue-spezifische Serien (12 Heim-, 12 Auswärts-
  spiele je Team) und erfasst teamspezifische Heimtor-Profile, die ein einziger Liga-
  Heimvorteil nicht abbildet. Nächste vorregistrierbare Hypothese H4: venue-spezifische
  Angriffs-/Abwehrparameter im DC-Fit (oder Legacy-Venue-Faktor auf die DC-Summe).

Produktionsfolge: Für eine kohärente Umsetzung des Hybrids braucht der Engine-Pfad eine
Konstruktion, die beide Gesetze in einer gemeinsamen Verteilung vereint (die gemeinsame
Kalibrierung projiziert heute eine Matrix je Familie); bis dahin bleibt der Hybrid eine
Analyse und `GOAL_MODEL_LEGACY` der Default.

### Nachtrag 21.10.2026: kohärenter Hybrid und H4 (`docs/audits/2026-10-21-dixon-coles-*.md`)

Umsetzung des Hybrids als **eine** Score-Matrix (`football_dixon_coles.reweight_totals`):
Dixon-Coles-Aufteilung innerhalb jeder Torsumme, Legacy-Verteilung der Torsumme;
Engine-Variante `dixon_coles_hl365_hybrid` über `goal_matrix_override`. H4 als
`dixon_coles_venue` (getrennte Heim-/Auswärts-Angriffs- und Abwehrparameter, Halbwertszeit
365 Tage) und `dixon_coles_venue_hybrid`. Gleiche 14 Ligen, 29 486 bis 29 487 Spiele.

| Variante | Heimsieg | Auswärtssieg | BTTS Ja | Über 2,5 | Heim unter 1,5 | Zellen sig. besser / schlechter (560) |
|---|---:|---:|---:|---:|---:|---:|
| hl365 (Referenz) | −0,0073 (2/10) | −0,0061 (3/10) | +0,0026 (12/0) | +0,0017 (12/0) | −0,0033 (3/3) | 91 / 271 |
| **hl365_hybrid (kohärent)** | −0,0073 (2/11) | −0,0057 (3/9) | +0,0010 (10/0) | 0 (Legacy) | −0,0041 (2/7) | **148 / 111** |
| venue (H4) | −0,0018 (4/2) | −0,0013 (4/3) | +0,0086 (14/0) | +0,0076 (14/0) | +0,0019 (8/0) | 10 / 444 |
| venue_hybrid | −0,0014 (4/3) | −0,0011 (4/3) | +0,0031 (14/0) | 0 (Legacy) | −0,0014 (4/3) | 48 / 219 |

Befunde:
- **Kohärenter Hybrid bestätigt:** Eine einzige Matrix mit DC-Struktur und Legacy-Torsumme
  ist in 148 von 560 Zellen signifikant besser als Legacy und in 111 im Mittel schlechter
  (fast ausschliesslich BTTS mit kleinem, nicht signifikantem Nachteil). 1X2-Vorteil wie DC,
  Totals exakt Legacy, Teamtore besser als beide. Gegen den Markt: Heimsieg-Lücke 0,0083
  (Legacy 0,0156), Über 2,5 0,0065 (= Legacy). Das ist die beste Konfiguration im Datensatz.
- **H4 widerlegt:** Venue-spezifische Parameter verschlechtern alles, auch 1X2
  (−0,0018 statt −0,0073) und Totals deutlich (+0,0076, 14 von 14 Ligen); mit vier
  Parameterblöcken je Team reicht die Historie nicht, die Ridge-Schrumpfung 0,02 ist
  dafür zu schwach. Der Tormarkt-Nachteil von Dixon-Coles lag also nicht an fehlenden
  Venue-Effekten, sondern an der Torsummen-Verteilung selbst, die der Hybrid vom
  Legacy-Prior übernimmt.
- Kein Modell schlägt den Markt. Das ändert nichts am Freigabevertrag.

### Nachtrag 22.10.2026: Release-Gate-Validierung des Hybrids (`docs/audits/2026-10-22-hybrid-validierung.md`)

Gleicher Artefakt-Builder wie der Produktionscache (`build_market_model_artifact`, jetzt mit
`goal_model`): Walk-forward, Kalibrierung aus Vortagen, Brier gegen Laplace-Basisrate,
Kalibrierdiagnostik, HAC und Benjamini-Hochberg je Liga. 14 Ligen, Laufzeit 3738 s.

| Zellen (Märkte × Ligen) | Legacy | Hybrid `dixon_coles_hl365_hybrid` |
|---|---:|---:|
| `_credible_validation` bestanden | 224 | **262** |
| zusätzlich statistische Freigabe | 224 | **257** |
| Heimsieg: Ligen glaubwürdig / Brier / rel. Verbesserung | 10 / 0,2255 / +8,1 % | 13 / 0,2191 / +10,8 % |
| Auswärtssieg | 12 / 0,1988 / +7,8 % | 13 / 0,1932 / +10,3 % |
| Remis | 0 / 0,1890 / +0,5 % | 2 / 0,1883 / +0,9 % |
| Heim unter 1,5 | 12 / 0,2330 / +5,0 % | 12 / 0,2286 / +6,8 % |
| Auswärts unter 1,5 | 11 / 0,2175 / +4,0 % | 12 / 0,2130 / +5,7 % |
| Über/Unter 2,5, BTTS | 0 / 0,2464 / +0,6 % | 0 / 0,2458 / +0,8 % (Legacy-Torsumme, unverändert) |

Kein Markt verliert Freigaben (einzige Abweichung: Auswärtssieg 13 glaubwürdig, 12
freigegeben wie zuvor). Der Hybrid ist damit auch unter dem bestehenden Vertrag die bessere
Basis. Für eine Produktionsaktivierung fehlen: neue `CHALLENGE_PREDICTION_VERSION` und
Modell-Vertragssignatur, Pin-/ORIGINAL-Verträge und `capture_football_original` für die
neue Basis (heute ausdrücklich Legacy-gebunden), Cache-Schema und ein Shadow-Lauf mit
beiden Basen. Das bleibt eine Owner-Entscheidung; das Marktergebnis (kein Modell schlägt
den Closing-Markt) ändert sich dadurch nicht.

### Nachtrag 22.10.2026: No-Vig-Marktwahrscheinlichkeit aus Partitionen

`MarketConsensus.native_market_partitions` enthält bereits je Buchmacher alle Seiten eines
Marktes. `market_consensus.no_vig_market_probability` berechnet daraus den Median der
No-Vig-Wahrscheinlichkeit der gewetteten Seite (Shin ab drei, Power bei zwei Ausgängen;
Doppelte Chance als Summe). Die Edge-Kappung vergleicht gegen diesen Wert und nutzt den
Konsens-Proxy nur noch ohne Partitionen (`ReferencePriceStatus.market_probability`,
`market_basis`). Der Audit-Punkt „Quotenabruf aller Seiten“ ist damit ohne zusätzlichen
API-Aufruf erledigt; eine Mischung der Entscheidungswahrscheinlichkeit mit dem Markt bleibt
wegen w* = 0 und der Nutzerregel vom 17.10. nicht umgesetzt.

### Nachtrag 22.10.2026: Hybrid-Aktivierung vorbereitet (Pins, ORIGINAL, Shadow mit beiden Basen)

Owner-Entscheidung 22.10.2026; Vorregistrierung `docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md`.
Produktions-Default unverändert (Golden-Tests in `tests/test_calibration.py` grün).

| Baustein | Umsetzung |
|---|---|
| Pins je Basis | `challenge_engine.prediction_version_for_goal_model` / `model_contract_signature_for_goal_model`: Legacy behält `coherent-joint-calibration-v14` und `hac-fdr-executable-frechet-v11`; der Hybrid `dixon_coles_hl365_hybrid` trägt `challenge-engine:dc-hl365-hybrid-joint-calibration-v1` und die Signatur mit Suffix `+dc-hl365-hybrid-v1`. Analyse-Varianten leiten nie registrierte Token ab. |
| Validierung, Kandidaten, Cache | `ValidationMetrics.prediction_version`, `ChallengeCandidate.prediction_version` und `build_market_comparisons` tragen die Version der Basis (`build_fixture_candidates(goal_model=)`); eine Basis übernimmt nie die Validierung einer anderen (Sperrgrund Walk-forward-Gate); `challenge_model_cache` und der Shadow-Dateicache sind dadurch getrennt. Echtgeld-Freigaben verlangen weiterhin genau die Legacy-Version: Hybrid-Kandidaten sind nie freigabefähig (`tests/test_goal_basis_pins.py`). Nationalteams (Liga 5) liefern für eine Nicht-Legacy-Basis fail-closed kein Modell. |
| ORIGINAL | Schema v2 unverändert; `goal_model` trägt zusätzlich Basis, Rho, Fit-Zusammenfassung und Legacy-Raten; `reference_weights`-Variante `football-goals-hybrid-dc-v1` = Legacy-Köpfe plus Fit-Fenster mit Zerfallsgewichten (jede Zeile eine deklarierte Historienreferenz). Speicherung (`football_original_storage`, eigener Chunk für das Fenster), Vergleich (`compare_captured_joint` rekonstruiert die Hybrid-Rohmatrix) und Replay (`replay_joint_calculation`, kalter Fit `fit_for_fixture(cold_start=True)`) sind byteidentisch (`tests/test_hybrid_original.py`). `executed_code_identity` führt die Pins je Basis; Publikation prüft die Identität je Basis. Trainingsfälle und Gegnervergleich nehmen nur Legacy-ORIGINALs (`original_basis_not_trainable`, `original-basis-not-legacy`). |
| Shadow mit beiden Basen | `shadow_clv_automation`: zweite Kohorte unter `challenge-engine-dc-hl365-hybrid-joint-calibration-v1` auf demselben Spiel mit derselben Quotenantwort; Legacy-Zeile zuerst, Hybrid-Fehler landen nur in `errors`; `step_warm_hybrid` baut die Hybrid-Artefakte (höchstens drei Ligen je Lauf) ausserhalb des Bewertungsfensters; Run-Artefakt `hybrid_cohort` mit Statistik beider Kohorten und paarweiser Auswertung (`_paired_cohort_statistics`). Schalter `BETBOY_SHADOW_HYBRID_BASIS` (Default an, `0` aus). `tests/test_shadow_hybrid_cohort.py`. |

Prüfplan und Aktivierungskriterien stehen in der Vorregistrierung: mindestens 300 paarweise
abgerechnete Spiele, untere Konfidenzgrenze der paarweisen CLV-Differenz über 0, keine
schlechtere Kalibrierung. Erst dann wird die Produktionsbasis umgestellt (eigener Commit,
Cache-Neuaufbau, Pins für Tickets und Publikation).

### Nachtrag 22.10.2026: Edge-Cap-Protokoll im Shadow-Pfad

Prüfplan-Schritt 1 der Vorregistrierung `docs/superpowers/plans/2026-10-21-edge-cap.md`:
`shadow_clv_automation` hält je protokolliertem Tipp beider Kohorten fest, ob die
vorregistrierte Kappung von 8 pp bestanden wäre (`shadow_edge_cap`: Modell-p, No-Vig-Markt-p
aus derselben Bet365-Partition, Abstand, `passed`), und wertet im Run-Artefakt `edge_cap`
die Gruppen bestanden/nicht bestanden je Kohorte aus (CLV, Trefferquote, abgerechnete
Tipps). Kein Tipp wird gefiltert; `BETBOY_EDGE_CAP_PP` bleibt ungesetzt.
`tests/test_shadow_edge_cap.py`.

## Nicht umgesetzt (braucht den Owner)

- API-Schlüssel: laut Gegenabgleich am 17.10.2026 bereits ersetzt und auf dem VPS
  aktiv; der Widerruf der alten Werte beim Anbieter ist nicht bewiesen. Der veraltete
  Hauptcheckout trägt die alten Werte noch in `config.ini`.
- Backup-Timer: auf ausdrücklichen Nutzerwunsch deaktiviert (Gegenabgleich K6); das
  Wiederherstellungsrisiko zwischen Deploys bleibt.
- Kartenänderung (Mindestquote, Preisstatus): am 20.10.2026 vom Owner ausdrücklich
  bestätigt („behalten“); kein Widerspruch mehr zur UX-Entscheidung vom 17.10., da es
  eine Zahl und eine Zeile ohne Aktion ist.
- Impressum, Datenschutz, Altershinweis, Spielsucht-Link (Rechtstexte).
- Aktivierung von Dixon-Coles oder des Marktbenchmarks als Release-Bedingung: beides
  erst nach Lektüre der Berichte und mit vorab definierter Hypothese (Bibel §3.5).

## Verifikation für Codex

```powershell
cd C:\Projekt\BetBoy\betboy-app\.worktrees\claude-audit-repairs-20261019
..\..\.venv\Scripts\python.exe -m pytest tests/test_daily3_selection.py tests/test_daily3_ui.py tests/test_sports_editorial.py tests/test_no_vig_methods.py tests/test_market_benchmark.py tests/test_football_dixon_coles.py tests/test_calibration.py -q
```

Merge nach `main` erst nach Codex' laufender Arbeit und nach einem Linux-Volllauf.
