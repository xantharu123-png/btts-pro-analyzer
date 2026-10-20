# Tennis: Platt-Kalibrator auf der gewetteten Population (Audit H3)

Stand 20.10.2026, Branch `claude/audit-repairs-20261019`. Antwort auf Audit
16.10.2026 H3 und Gegenabgleich 17.10. (T4/H3, „produktionsgleiche
Kalibratorpopulation" offen). Keine Produktionsartefakte geschrieben, keine
API-Aufrufe (Loader auf `tennis/data/` gezwungen, `requests.get` blockiert).
Softwaretests sind kein Beleg für Wettvorteil; die Zahlen unten sind
Kalibrierkennzahlen einer einzigen Saison.

## Hypothesen (vorab definiert)

- **H3-1:** Ein Platt-Kalibrator, der nur auf Zeilen gefittet wird, die den
  Produktionsfilter erfüllen (Belag in `ALLOWED_SURFACES`, Serve-Schätzung
  vorhanden, beide Spieler ≥ `MIN_ELO_MATCHES`/`MIN_SERVE_GAMES`), senkt im
  zeitlichen Walk-forward ECE, Brier und Log-Loss **auf genau dieser
  Population** gegenüber dem Legacy-Fit auf allen ATP-Zeilen.
- **H3-2:** Belag und Serve-Verfügbarkeit als Kovariaten eines gemeinsamen
  Kalibrators (Steigung und Achsenabschnitt je Gruppe) erreichen dasselbe mit
  der vollen Stichprobe.

Erfolgskriterium: paarweise Bootstrap-Differenz (Brier, Log-Loss; 4 000
Resamples, Seed 20261020) auf der gewetteten Population mit 95-%-Intervall
vollständig unter 0; ECE (10 gleich breite Bins, zusätzlich 5 Quantil-Bins)
als Zusatzmass.

## Ist-Zustand: Fit, Zeitfenster, Auswahlfilter (`tennis/backtest.py`)

Zeilenangaben beziehen sich auf den Stand dieses Branches (die Audit-Zitate
663-690/766-767/111-170 sind die Vorgängerzeilen).

| Schritt | Ort | Verhalten |
|---|---|---|
| Platt-Fit | `WalkForwardCalibrator` :152-199, `_fit` :186 | 2-Parameter-Logit auf `logit(p)`, Newton, Grenzen a∈[0,2; 8], b∈[−3; 3]; Identität bis `min_samples` (Default 1500), Refit alle `refit_every` (Default 500) |
| Kausaler Stats-Zeiger | `run_backtest` (Block „1) advance the causal stats pointer") | Stats-Zeile (Elo + Serve, nur Tour-Level) betritt den Zustand erst, wenn `stats_available_at` < Entscheidungs-Cutoff der Marktzeile |
| Vorhersage | Block „2) predict" | `p_elo` immer; `p_serve` nur wenn beide Spieler ≥ `MIN_SERVE_GAMES` (60); `p_model` = Blend mit `serve_weight` |
| Experience-Gate | direkt nach `p_model` | `gated` = beide ≥ `min_elo_matches` (20) |
| Warm-up-Fenster | `score_from` | Zeilen davor füttern nur den Zustand |
| Walk-forward-Anwendung | `cal.predict(p_alpha_raw, ...)` | ausschliesslich früher gefittete Parameter |
| Lernen | Block „4) only now may anything learn" | `cal.add(...)` erst **nach** der Vorhersage; bisher für jede nicht-abnormale Zeile: alle Beläge, Elo-only-Zeilen, Zeilen unter dem Experience-Gate |
| Wettauswahl (Replay) | `policy_summary` | filtert `gated` ∧ `surface ∈ ("Hard",)` ∧ `p_serve` vorhanden, dann Haircut/EV |
| Wettauswahl (Produktion) | `tennis/predict.py` :43 (`ALLOWED_SURFACES`), :197 (`have_serve`), :299-312 (Gates „Belag", „Erfahrung", „Aufschlag-Daten") | dieselben Konstanten |

Vor dieser Arbeit (Audit-Zeilen): Fit 111-170, Lernen 809-810 für jede
Zeile, Gate 766-769 nur für die Wettauswahl, nie für den Fit.

Produktionsfit (`tennis/tour_state.py` :123-140): `run_backtest(...,
calibration_only=True, recalibrate=False)` liefert rohe `CalibrationRow`s
(bisher ohne Belag/Serve/Gate-Marker); `WalkForwardCalibrator(1500, 250)`
lernt aus **allen** Zeilen. Legacy-Builder `tennis/model_state.py` :187-202
analog, zusätzlich inklusive Retirement-Zeilen (der In-Loop-Fit schliesst
`abnormal` aus, der Legacy-Builder nicht; unverändert, dokumentiert).

Konsequenz: Der Kalibrator lernt eine Mischverteilung (Elo-only-Zeilen sind
flacher als Serve-Blend-Zeilen; Clay/Grass haben andere Elo-Trennschärfe),
gewettet wird eine Teilmenge. Der 15-pp-Abschlag (`predict.py` :48) ist davon
entkoppelt und bleibt in dieser Arbeit unverändert.

## Umsetzung (Default = bisheriges Verhalten; nur `tennis/backtest.py`)

- `backtest.BETTING_SURFACES = ("Hard",)` (Test sichert Gleichheit mit
  `predict.ALLOWED_SURFACES`).
- `backtest.in_betting_population(surface, p_serve, gated)` = Produktionsfilter.
- `run_backtest(calibration_population="all"|"betting",
  calibration_model="platt"|"covariate")`. `betting`: der In-Loop-Kalibrator
  lernt nur aus Filterzeilen; alle Zeilen werden weiterhin vorhergesagt und
  berichtet; im `calibration_only`-Modus werden nur Lernzeilen zurückgegeben.
  `covariate`: `CovariateWalkForwardCalibrator`, Features
  `[x, x·serve, x·hard, 1, serve, hard]`, nur mit voller Population zulässig,
  nicht persistierbar (experimentell).
- `BacktestRow.betting_population`, `BacktestRow.calibrator_trained`,
  `CalibrationRow.surface/has_serve/gated/betting_population` (Defaults, alte
  Konstruktoren unverändert).
- `BacktestReport.population_calibration(population, trained_only, since,
  bins)`: ECE/Brier/Log-Loss auf einer Population.
- `backtest.fit_platt_calibrator(rows, calibration_population, min_samples,
  refit_every)`: der Builder-Fit (add alle, dann `_fit`) mit Populationsfilter;
  liefert Kalibrator und Anzahl gefitteter Zeilen (= künftiges `cal_samples`).
- **Bewusst nicht geändert:** `tennis/predict.py`, `tennis/model_state.py`,
  `tennis/tour_state.py`, `tennis/calibration_watch.py`. `predict.py` und
  `model_state.py` sind quellgepinnte Replay-Owner
  (`context_runtime_tennis.CODE_PATHS`, geprüfte Manifeste
  `_REVIEWED_*`): jede Byteänderung lässt 38 Tests in
  `tests/test_tennis_live_training.py` mit „original calculation has no
  supported exact source replay" fallen, bis ein neues geprüftes Manifest
  eingetragen ist. Ein erster Versuch mit `build_state(calibration_population)`
  und `ALLOWED_SURFACES = BETTING_SURFACES` wurde deshalb zurückgenommen.
- Tests: `tests/test_tennis_calibration_population.py` (16 Tests: Filter ≙
  `predict_match`-Gates und `policy_summary`-Modellgates; Default reproduziert
  Legacy-Walk-forward; `betting` lernt nur aus Filterzeilen, Vorhersage jeder
  Zeile nur aus Fits strikt vor ihrem Datum; `calibration_only`-Teilmenge;
  Builder-Fit Default/`betting`; Pin-Wächter für `predict.py`/`model_state.py`;
  Kovariaten-Kalibrator kausal und gruppentreu; Metrikfunktion).

## Datenlage (bestimmt, was prüfbar ist)

`tennis/data/atp_tournaments.csv` trägt `finish_dtm` nur für 2024, 2025 und
2026 (276/320/304 Turniere); 2015-2023 haben **keine** Endtermine. Das kausale
Protokoll lässt deshalb vor 2024 keine Stats-Zeile zu: im Backtest 2019-2023
ist `p_elo` = 0,5 in jeder Zeile, `p_serve` fehlt, Experience-Gate immer rot
(0 gewettete Zeilen in 2019/2021/2022/2023). Ein Lauf über 2019-2024 füttert
den Legacy-Kalibrator also mit rund 10 000 informationslosen Zeilen (logit 0)
— ein eigener Befund für `scripts/tennis_decay_ab.py` und
`scripts/tennis_matchup_measurements.py`, die ältere Saisons laden.

Lokal gecachte ATP-Preisjahre: 2019, 2021-2024; 2025 fehlt (kein Download
erlaubt). Prüfbar ist damit genau die Saison 2024 (Stats 2023-2024 wie das
Produktionsfenster; 2023 trägt nichts bei, Elo startet kalt):

| Zeilen 2024 (ATP, Pinnacle-Closing) | n |
|---|---:|
| Marktzeilen gesamt | 2 701 |
| davon normal beendet | 2 608 |
| Hard | 1 518 |
| Serve-Schätzung vorhanden | 1 918 |
| Experience-Gate | 1 334 |
| **gewettete Population** (alle drei) | **700** (674 normal beendet; erste am 22.07.2024, weil das Experience-Gate mit kaltem Elo erst dann öffnet) |

Mit `min_samples=1500` kann ein Kalibrator auf der gewetteten Population
innerhalb einer Saison **nicht trainieren** (674 < 1500); er bleibt Identität.
Der Vergleich wird deshalb zusätzlich mit reduzierten Schwellen (500/100 und
300/100) geführt. Das ist eine Protokolländerung für den Test, keine
Empfehlung für Produktionsschwellen. Alle Läufe: `serve_weight` 0,3,
Halbwertszeit 365 d, Indoor-Split, `market_model_version`
`serve-points-joint-v2` (Produktion); `hold-proxy-v1` liefert dieselben
Schlüsse (Steigungen 0,695/0,914 statt 0,703/0,930, Differenzen ±0,001).

## Ergebnis 1: Produktionsschwellen (1500/500)

Legacy-Kalibrator („all") trainiert ab 26.06.2024 (a = 0,703, b = −0,031 am
Saisonende, n = 2 608). Wettpopulation ab 22.07.2024, n = 674 (669 ohne die
NaN-Preiszeilen, siehe Nebenbefund):

| Wahrscheinlichkeit | n | Brier | Log-Loss | ECE10 |
|---|---:|---:|---:|---:|
| roh (`p_alpha_raw`) | 669 | 0,2179 | 0,6251 | 0,0504 |
| Legacy-kalibriert (`p_alpha`) | 669 | 0,2200 | 0,6297 | 0,0487 |
| Pinnacle no-vig (Referenz) | 669 | 0,2050 | 0,5963 | 0,0425 |
| Fit auf Wettpopulation | — | nicht trainierbar (674 < 1 500) | | |

Reliabilität auf den 674 Wettzeilen, 5 Quantil-Bins à 135 (SE je Bin ≈ 0,04),
alphabetische Orientierung, Lücke = Mittel p − Trefferquote:

| Bin | roh p̄ → Treffer (Lücke) | kalibriert p̄ → Treffer (Lücke) |
|---|---|---|
| 1 | 0,22 → 0,19 (+0,04) | 0,29 → 0,19 (+0,11) |
| 2 | 0,37 → 0,35 (+0,02) | 0,41 → 0,35 (+0,06) |
| 3 | 0,47 → 0,50 (−0,03) | 0,47 → 0,51 (−0,04) |
| 4 | 0,58 → 0,61 (−0,03) | 0,55 → 0,62 (−0,07) |
| 5 | 0,75 → 0,67 (+0,08) | 0,67 → 0,66 (+0,01) |

Lesart: Auf der gewetteten Population ist das rohe Modell nahezu kalibriert
(Fit nur auf ihr: a = 0,930, b = −0,076, n = 674). Der Legacy-Kalibrator mit
a = 0,70 staucht diese Zeilen und macht sie im Bereich 0,55-0,70 **unter**-,
an den Rändern (Bin 1/2 ≙ Gegenseite 0,6-0,8) **über**konfident. Die
pauschale Überkonfidenz-Diagnose aus H3 trifft 2024 nur den obersten rohen
Bin (+0,08, ≈ 2 SE); der Rest liegt im Rauschen.

## Ergebnis 2: reduzierte Schwellen (Walk-forward, beide Kalibratoren trainiert)

Bewertungsfenster = Wettzeilen ab dem Tag, an dem **alle** Varianten trainiert
sind. Differenzen sind Variante − Vergleich mit 95-%-Bootstrap-Intervall.

| Schwellen | Fenster ab | n | roh Brier / LL / ECE10 | all | betting | covariate |
|---|---|---:|---|---|---|---|
| 500/100 | 18.10.2024 | 174 | 0,2144 / 0,6180 / 0,043 | 0,2172 / 0,6246 / 0,072 | 0,2145 / 0,6182 / 0,058 | 0,2160 / 0,6218 / 0,066 |
| 300/100 | 20.09.2024 | 374 | 0,2130 / 0,6147 / 0,047 | 0,2162 / 0,6220 / 0,069 | 0,2177 / 0,6239 / 0,061 | 0,2159 / 0,6210 / 0,060 |

| Differenz | 500/100 (n = 174) Brier [KI] | Log-Loss [KI] | 300/100 (n = 374) Brier [KI] | Log-Loss [KI] |
|---|---|---|---|---|
| betting − all (H3-1) | −0,0027 [−0,0069; +0,0015] | −0,0063 [−0,0167; +0,0043] | +0,0015 [−0,0025; +0,0056] | +0,0019 [−0,0075; +0,0118] |
| covariate − all (H3-2) | −0,0012 [−0,0027; +0,0004] | −0,0028 [−0,0065; +0,0012] | −0,0003 [−0,0014; +0,0009] | −0,0010 [−0,0037; +0,0019] |
| all − roh | +0,0029 [−0,0034; +0,0088] | +0,0065 [−0,0101; +0,0222] | +0,0032 [−0,0012; +0,0075] | +0,0074 [−0,0045; +0,0188] |
| betting − roh | +0,0002 [−0,0024; +0,0027] | +0,0002 [−0,0065; +0,0064] | +0,0047 [+0,0014; +0,0080] | +0,0092 [+0,0016; +0,0166] |

Kovariaten-Fit am Saisonende (n = 2 608): effektive Steigung/Achsenabschnitt
Hard + Serve 0,793/−0,051, Hard ohne Serve 0,531/+0,124, Clay + Serve
0,763/−0,115. Das bestätigt den Mechanismus hinter H3: Elo-only-Zeilen
brauchen starke Stauchung (0,53), Serve-Blend-Zeilen kaum (0,79); der
Legacy-Wert 0,70 ist der Kompromiss über beide.

Preisreplay (`policy_summary`, Haircut 15 pp, min. ROI 3 %, Fenster ab
18.10.): all 20 Wetten/7 Treffer, ROI +35,7 % [−72; +143]; betting 22/7,
−16,8 % [−71; +37]; covariate 21/6, +14,5 % [−88; +117]. Fenster ab 20.09.:
all 63/17, +5,3 % [−48; +58]; betting 65/18, −21,0 % [−59; +17]. Ohne Haircut
(ab 18.10.): all 151 Wetten −0,4 % [−27; +26], betting 135 Wetten −6,0 %
[−31; +19]. Keine Aussage möglich.

## Mindestquoten (`betting_math.minimum_recommendation_odds`, min. ROI 3 %, Floor 1,20)

| Eingang | p_kal | ohne Abschlag | mit 15 pp |
|---|---:|---:|---:|
| p_kal = 0,60 (kalibratorunabhängig) | 0,600 | 1,72 | 2,29 |
| p_kal = 0,80 (kalibratorunabhängig) | 0,800 | 1,29 | 1,59 |
| roh 0,60 → Legacy (a 0,703) | 0,563 | 1,83 | 2,50 |
| roh 0,60 → Wettpopulation (a 0,930) | 0,575 | 1,80 | 2,43 |
| roh 0,60 → Kovariaten (Hard + Serve) | 0,567 | 1,82 | 2,47 |
| roh 0,80 → Legacy | 0,720 | 1,44 | 1,81 |
| roh 0,80 → Wettpopulation | 0,771 | 1,34 | 1,66 |
| roh 0,80 → Kovariaten | 0,741 | 1,40 | 1,75 |

Ein Populationsfit würde die geforderten Quoten für Favoriten senken (1,81 →
1,66 bei roh 0,80 mit Abschlag). Der 15-pp-Abschlag käme dann zusätzlich zu
einem Kalibrator, der kaum noch staucht — das wäre vor einer Aktivierung aus
der Kalibrier-Unsicherheit der Wettpopulation neu abzuleiten (Audit K3/H2),
nicht additiv beizubehalten.

## Schlussfolgerung

- **H3-1 nicht bestätigt.** Mit Produktionsschwellen ist der Populationsfit
  in einer Saison nicht trainierbar. Mit reduzierten Schwellen ist die
  Richtung uneinheitlich (n = 174: Brier −0,003; n = 374: +0,002), jedes
  95-%-Intervall enthält 0; bei 300/100 ist der Populationsfit sogar
  signifikant schlechter als das rohe Modell (+0,0047 [+0,0014; +0,0080]),
  weil 300 Zeilen für zwei Parameter zu laut sind. Kein Vorteil nachweisbar.
- **H3-2 richtungstreu, aber klein.** Der Kovariaten-Kalibrator ist nie
  schlechter als Legacy (−0,0012/−0,0003 Brier), nie signifikant besser.
- **Härtester Befund:** Auf der 2024er Wettpopulation ist das rohe Modell die
  bestkalibrierte Variante (Brier 0,2179 gegen 0,2200 kalibriert; alle Bins
  innerhalb 2 SE). Der Legacy-Kalibrator lernt die Stauchung der Elo-only-
  Mehrheit (Steigung 0,53) und überträgt sie auf Serve-Zeilen (benötigt ≈
  0,8-0,9). Das ist das Populationsproblem aus H3 — nur mit umgekehrtem
  Vorzeichen zur Annahme „überkonfident": der Kalibrator macht die gewettete
  Mitte unterkonfident.
- **Keine Produktionsänderung.** Option bleibt Default-aus (`all`). Eine Saison
  mit 674 Zeilen trägt keine Gate-Änderung (Bibel §3.5).

## Was für eine Aktivierung in Produktion fehlt

1. **Daten:** mindestens zwei Saisons mit Endterminen und Closing-Preisen
   (2024 + 2025; `finish_dtm` für 2025/2026 liegt vor, die 2025er Preisdatei
   nur im VPS-Cache). Wiederholung dieses Protokolls mit vorab fixierten
   Schwellen (Vorschlag 500/100 für den Populationsfit, da ≈ 700 Wettzeilen
   je Saison) und demselben Erfolgskriterium.
2. **Quellpins:** `tennis/predict.py` und `tennis/model_state.py` sind
   Replay-Owner in `context_runtime_tennis.CODE_PATHS`. Jede Änderung dort
   (auch `ALLOWED_SURFACES = BETTING_SURFACES`) braucht ein neues geprüftes
   `_REVIEWED_*`-Manifest mit Übergangsregel, sonst verlieren alle
   historischen Originale ihre exakte Replay-Freigabe (38 Tests).
3. **Artefakt-/Zustandsverträge:** `ModelState` und `state_codec`
   (`_STATE_KEYS`, Schema 1/2) kennen keinen Populationsmarker; ein Subset-Fit
   wäre vom Legacy-Fit nicht unterscheidbar, `cal_samples` änderte still
   seine Bedeutung. Nötig: Schema 3 mit `calibration_population` in
   `state_codec`, `tour_state._decode_wrapper`, `context_consumer._STATE_KEYS`,
   Manifest-Bindung in `model_artifacts`; `daily3_tennis_comparison` verlangt
   `cal_samples ≥ 200` und wäre gegen die Subset-Grösse zu prüfen.
4. **Produktionsbuilder:** `tour_state.build_tour_state` müsste
   `run_backtest(calibration_population="betting")` plus
   `fit_platt_calibrator(..., calibration_population="betting")` aufrufen (die
   `CalibrationRow`-Marker liegen jetzt vor).
5. **Wächter:** `calibration_watch` prüft nur Satzmärkte mit `hold-proxy-v1`
   und meldet v2 als `unavailable`; den Gewinner-Platt überwacht niemand.
   Nötig: wöchentliche `population_calibration` (ECE/Brier, Bins, n) auf der
   Wettpopulation mit Drift-Grenzen, bevor ein neuer Fit live geht.
6. **Haircut:** bei Aktivierung aus der Kalibrier-SE der Wettpopulation neu
   herleiten (siehe Mindestquoten), nicht 15 pp zusätzlich.
7. **Kovariaten-Variante:** bräuchte sechs persistierte Koeffizienten und
   einen `predict`-Pfad mit Belag/Serve-Flag — nur sinnvoll, falls zwei Saisons
   einen Vorteil zeigen.

## Nebenbefunde (nicht geändert, um Default-Parameter nicht zu verschieben)

- `backtest._devig` lässt NaN-Preise durch (`nan <= 1.0` ist falsch): 2024
  tragen 12 Zeilen (7 in der Wettpopulation) NaN-Quoten, bleiben im
  Kalibrator, machen `calibration()["brier_market"]` zu NaN und fallen im
  Preisreplay still heraus. Fix `if not (ow > 1.0 and ol > 1.0): return None`
  — verschiebt die Kalibratorpopulation um 12 Zeilen, deshalb vorab zu
  registrieren.
- `model_state.build_state` fittet Retirement-Zeilen mit, `tour_state` nicht.
- Vor 2024 liefern alle Backtests informationslose Vorhersagen (Datenlage).

Reproduktion: Vergleichsskript lag im Session-Scratchpad
(`compare_2024.py`, Loader auf `tennis/data/`, Netz blockiert); Kennzahlen
sind mit `run_backtest(..., calibration_population=..., calibration_model=...)`
und `BacktestReport.population_calibration()` nachrechenbar.
