# Auftrag: Dixon-Coles, Halbwertszeit und Niveau-Prior (vorregistrierte Hypothesen)

Stand 20.10.2026. Auftrag für eine eigene Session; aus dem Hauptcheckout
`C:\Projekt\BetBoy\betboy-app` starten und einen Worktree von Branch
`claude/audit-repairs-20261019` abzweigen (nicht von `main`). Ein Start aus einem
bestehenden Worktree heraus scheitert in der App am Git-Zustand.

## Ausgangslage

Auf `claude/audit-repairs-20261019` liegt ein Opt-in-Dixon-Coles-Modell
(`football_dixon_coles.py`, Schalter `goal_model="dixon_coles"` in
`challenge_engine.fixture_market_probabilities`), das Vergleichsskript
`scripts/compare_goal_models.py` und der Marktbenchmark (`market_benchmark.py`).
Ergebnis in `docs/audits/2026-10-19-dixon-coles-vergleich.md` (14 Ligen, 29 512
Spiele): 1X2 und Doppelte Chance klar besser als die Legacy-Mittelwerte (9 von 14
Ligen signifikant), Totals und BTTS in 13 bis 14 von 14 Ligen schlechter.
Arbeitshypothese: Die multiplikative Gegnerbereinigung verbessert die
Relativstärke, das zeitgewichtete Niveau (Intercept, Halbwertszeit 120 Tage,
effektiv rund eine Saison Gewicht) ist für das absolute Torniveau schlechter als
der Liga-Prior der Legacy-Mittelwerte.

Regeln: keine Quote als Modellinput, fail-closed, kein Schwellen-Tuning ohne
vorab definierte Hypothese (Bibel §3.5), Default `GOAL_MODEL_LEGACY` bleibt
byteidentisch (`tests/test_calibration.py` Golden-Tests). Siehe `AGENTS.md`.

Daten: `runtime_state/market_benchmark/` des genannten Worktrees (98 CSVs,
`scripts/download_market_benchmark_data.py` lädt sie bei Bedarf neu).

## Hypothesen, vor dem ersten Lauf festschreiben

- **H1 Halbwertszeit:** 240 und 365 Tage statt 120 (`half_life_days` in
  `fit_for_fixture`/`fit_dixon_coles` durchreichen, z. B. als Modulparameter oder
  `goal_model`-Variante).
- **H2 Niveau-Prior:** Intercept `mu` nicht frei fitten, sondern an das
  Liga-Tormittel aller Spiele im Fenster binden (wie `_league_goal_means`);
  Angriff, Abwehr, Heimvorteil und ρ bleiben frei.
- **H3 Hybrid:** DC-Verteilung nur für die Ergebnisfamilie (`result`,
  `double_chance`, `result_total`), Legacy-Matrix für Totals, BTTS und Teamtore.
  Prüfen, ob die gemeinsame Kalibrierung (`football_joint_calibration`) damit
  kohärent bleibt; sonst als nicht umsetzbar dokumentieren.

## Vorgehen

1. Jede Variante als eigener `goal_model`-Wert oder Parameter; Default unverändert.
2. Tests in `tests/test_football_dixon_coles.py` erweitern (Parität Default,
   Fail-closed, Normierung).
3. Walk-forward-Vergleich auf den gespeicherten 14 Ligen mit
   `scripts/compare_goal_models.py` (Variantenparameter ergänzen), gleiche Zellen,
   HAC und Benjamini-Hochberg wie bisher.
4. Bericht `docs/audits/2026-10-XX-dixon-coles-niveau.md` mit Tabelle je Variante:
   Brier Heimsieg, Auswärtssieg, Remis, Über/Unter 2,5, BTTS, jeweils gegen Legacy
   und gegen den Markt, Anzahl signifikanter Zellen.

## Fertig heisst

Bericht geschrieben; `python -m pytest tests/test_football_dixon_coles.py
tests/test_calibration.py tests/test_market_benchmark.py` grün; Default-Pfad
unverändert; keine Quote im Modell; WIP-Commit auf dem neuen Branch; kein Push,
kein Deploy, keine Änderung an Hauptcheckout oder Codex-Worktree.
