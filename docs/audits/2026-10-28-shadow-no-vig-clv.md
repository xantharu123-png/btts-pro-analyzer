# 28.10.2026 – Shadow: CLV gegen den fairen Schlusspreis (Audit S5, zweiter Teil)

Offener Rest aus Massnahme 2 des Gesamtaudits `AUDIT_BERICHT_2026-10-25_CLAUDE.md` (Befund S5),
Owner-Auftrag vom 28.10.2026. Reine Messung; Ledger, Policy (`shadow-model-first-v7`) und
Tippauswahl bleiben unverändert.

## Problem

Der Shadow misst CLV roh als Öffnungsquote / Schlussquote − 1. Beide Preise enthalten die Marge
des Buchmachers. Ändert sich nur die Marge (z. B. kurz vor Anpfiff), sieht das wie ein Vorsprung
oder Rückstand des Modells aus. Die Pläne zu Edge-Cap und Hybrid verlangen ein ehrliches Mass.

## Umgesetzt

- Neue Tabelle `shadow_closing_market` (`prediction_id`, `market_probability`, `recorded_at`) in
  `shadow_clv.db`. `step_closing` schreibt beim Erfassen der Schlussquote die faire Wahrscheinlichkeit
  der Tippseite aus der vollständigen Bet365-Partition derselben Antwort (Shin bei drei Ausgängen,
  Power bei zwei; Doppelte Chance als Summe zweier Seiten), dieselbe Funktion wie beim Edge-Cap
  (`_no_vig_market_probability`). Fehlt eine Seite der Partition, steht `NULL`. Kein zusätzlicher
  API-Aufruf.
- `_no_vig_clv_statistics()` im Shadow-Artefakt (`no_vig_clv`): je Kohorte (Legacy, Hybrid)
  `Öffnungsquote × p_Schluss,fair − 1` in Prozentpunkten mit HAC-Intervall (`_clv_interval`), dazu
  die Zahl der Schlussquoten ohne vollständige Partition und ohne neuen Marktstand; für Spiele mit
  beiden Kohorten die paarweise Differenz Hybrid − Legacy mit HAC-Intervall.
- Schlussquoten, die den Öffnungsstand wiederholen, zählen wie beim rohen CLV nicht
  (Regel vom 28.10.2026).
- Tests: `tests/test_shadow_no_vig_clv.py` (faire Wahrscheinlichkeit gespeichert, unvollständige
  Partition ohne Wert, Statistik je Kohorte und paarweise).

## Lesart

Ein positiver No-Vig-CLV heisst: Die Öffnungsquote war höher als der faire Schlusspreis, das
Modell hat also früher als der Markt richtig gelegen. Das ist die Grösse, an der Hybrid-Aktivierung
(`docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md`) und Edge-Cap gemessen werden sollen; die
rohe Grösse bleibt zum Vergleich im Artefakt. Werte entstehen ab dem ersten Shadow-Lauf nach dem
Release; Schlussquoten vor diesem Release haben keinen fairen Schlusswert.
