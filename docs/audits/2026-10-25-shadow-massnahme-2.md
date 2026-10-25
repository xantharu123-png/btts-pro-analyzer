# Vertragsänderung 25.10.2026: Shadow misst richtig – Trefferquote, Hybrid-Warm-up, veröffentlichte Tipps, HAC-Intervalle

Owner-Entscheidung vom 25.10.2026 (Massnahme 2 des Gesamtaudits `AUDIT_BERICHT_2026-10-25_CLAUDE.md`,
Befunde S2, S3, S5, D4). Betroffen ist nur der Shadow-Pfad (`shadow_clv_automation`, Timer
`betboy-football-shadow`): kein Modell, keine Freigabe, keine Veröffentlichung und keine Oberfläche
ändern sich; es gibt keinen neuen Schalter. Der Shadow sammelt die Evidenz für zwei vorregistrierte
Entscheidungen (Hybrid-Aktivierung, Edge-Cap) und hatte seit dem 22.10. strukturell nichts
Verwertbares geliefert.

## Vorher (bis PR #31)

- **Trefferquote immer 0 (S3).** `_edge_cap_statistics` und `_paired_cohort_statistics` verglichen
  `str(result).upper() == "WIN"`; `CLVTracker.settle_prediction` speichert `'Won'`, `'Lost'`,
  `'Push'`. Die Tests kodierten `"WIN"` und verdeckten den Fehler.
- **Hybrid-Kohorte strukturell leer (D4).** `_evaluate_hybrid_cohort` meldete bei fehlenden
  Artefakten `terminal: True`; `step_evaluate` hakte das Spiel ab (`evaluated = 1`), sobald Legacy und
  Hybrid terminal waren; `step_warm_hybrid` lief erst danach und nur über offene Zeilen. Jedes Spiel,
  das erstmals im Fenster vor Anpfiff geprüft wurde, war für den Hybrid verloren, bevor seine Liga
  gebaut war (`artifacts_warmed: 0` seit 22.10.).
- **Andere Population als veröffentlicht (S2).** Der Shadow protokolliert seinen eigenen
  Modell-zuerst-Tipp mit Bet365-Quote bis drei Stunden Alter; die App veröffentlicht freigegebene
  Zeilen in Ledger-Reihenfolge, auch unbepreist, mit Lead nach höchster Wahrscheinlichkeit. Was
  veröffentlicht wurde, stand nirgends als Datensatz.
- **Nur Mittelwerte (S5).** Beide Pläne verlangen HAC-Intervalle der CLV-Differenz; das Artefakt
  führte nur Mittelwerte.

## Nachher (ab PR #32)

- **Trefferquote.** `_is_win` (`Won`) und `_decided` (`Won`/`Lost`); Zähler laufen nur über
  entschiedene Tipps, ein `Push` schliesst (zählt für CLV), entscheidet aber nicht. Ein Grosscode
  `WIN` zählt nie.
- **Warm-up vor der Bewertung.** `run()` ruft `step_warm_hybrid` vor `step_evaluate`; Ligen mit dem
  frühesten offenen Anpfiff zuerst, Zeitbudget unverändert 240 s
  (`SHADOW_HYBRID_WARMUP_BUDGET_SECONDS`). Rückgabe ist jetzt `{"warmed", "cached", "failed",
  "pending"}`; das Run-Artefakt führt `artifacts_warmed`, `artifacts_cached`, `leagues_pending`,
  `builds_failed`. Ein fehlgeschlagener Bau wird für den Tag in `shadow_meta` markiert
  (`hybrid-build-failed:<Tag>:<Liga>:<Saison>`) und nicht wiederholt.
- **Fehlende Artefakte sind nicht terminal.** `_evaluate_hybrid_cohort` lässt das Spiel offen,
  solange die Liga noch gebaut werden kann; nach einem fehlgeschlagenen Bau bleibt es terminal. Die
  Legacy-Zeile wird unverändert sofort geschrieben und nie dupliziert; die bestehende
  Letztversuchsregel (`EVAL_FINAL_RETRY_MINUTES`, 30 min vor Anpfiff) schliesst jedes Spiel
  rechtzeitig. Abweichung vom Plan: Holt der Hybrid ein Spiel in einem späteren Lauf nach, stammt
  seine Öffnungsquote aus einer jüngeren Quotenantwort als die Legacy-Zeile; jedes offene Spiel
  kostet je Lauf einen weiteren Quotenabruf (Pro-Kontingent).
- **Veröffentlichte Tipps mitprotokolliert.** Neue Tabelle `shadow_published` (Schlüssel
  `candidate_id`, `kind` ∈ {`public_tip`, `challenge_15k`}, `zurich_date`). `step_record_published`
  liest in jedem Lauf `runtime_state/wettfinder_latest.json` (nur das Dokument des heutigen
  Zieldatums, nur Fussballzeilen) und speichert je veröffentlichter Zeile Spiel, Markt, Auswahl,
  Modellwahrscheinlichkeit, Preisstatus, bei `PLAYABLE` die ausführbare Öffnungsquote und den
  Buchmacher, Modell- und Policy-Version, Dokument-Uhr, Erstsichtung und Anpfiff. Erste Sichtung
  gewinnt (`INSERT OR IGNORE`); eine später gefundene Quote überschreibt den Datensatz nicht.
  `step_settle_published` rechnet im täglichen Abrechnungsblock (ab 09:00, einmal je Tag) die
  Tormärkte aus dem Endstand ab (`challenge_engine.market_outcome`: 1X2, Doppelte Chance, BTTS,
  Totals, Teamtore, Kombinationen); Ecken- und Kartenmärkte bleiben offen, weil die Abrechnung keine
  Zählwerte lädt. Das Run-Artefakt führt `published_tips` je Art: erfasst, mit Quote, abgerechnet,
  gewonnen/verloren, mittlere Öffnungsquote, Trefferquote; `steps` zählt `published_recorded`,
  `published_recorded_with_quote`, `published_settled`.
- **HAC-Intervalle.** `_clv_interval` nutzt `model_loss_statistics.paired_advantage_statistics`
  (Newey-West, chronologisch nach Protokoll-ID) und liefert `n`, `mean`, `hac_standard_error`,
  `lower_bound`, `p_value` in Prozentpunkten. Edge-Cap: je Kohorte `passed_clv` und `failed_clv`;
  Hybrid: `difference` der paarweisen CLV-Differenz (Hybrid minus Legacy), also genau die Grösse,
  deren untere Grenze der Prüfplan verlangt.

## Was das bedeutet

- Rückwirkend ist nichts zu korrigieren: Unter Policy v6 war bis zum 25.10. kein Shadow-Tipp
  abgerechnet, die falschen Trefferquoten hatten keinen Datenbestand.
- Die Hybrid-Kohorte kann erstmals wachsen. Die 300-Paare-Schwelle und das Kriterium (untere
  HAC-Grenze der Differenz über 0, keine schlechtere Kalibrierung) bleiben; der Prüfplan nennt
  zusätzlich Brier je Kohorte, das steht noch aus.
- `shadow_published` beginnt leer und füllt sich mit dem ersten Lauf nach dem Release; die erste
  Abrechnung folgt im 09:00-Block des Folgetags. Damit lässt sich die veröffentlichte Regel selbst
  bewerten und der Anteil mit und ohne Quote ausweisen; eine Closing-Quote wird für veröffentlichte
  Zeilen nicht erfasst.
- Offen aus S5: der CLV bleibt roh (Opening/Closing − 1, verviggt); No-Vig-CLV und Intervalle in
  `clv_tracker.get_clv_statistics` sind nicht Teil dieser Massnahme.

## Umsetzung

`shadow_clv_automation` (`_is_win`, `_decided`, `_clv_interval`, `_hybrid_build_marker`,
`_hybrid_build_failed`, `step_warm_hybrid`, `_evaluate_hybrid_cohort`, `_connect` mit
`shadow_published`, `step_record_published`, `step_settle_published`, `_published_statistics`,
`_edge_cap_statistics`, `_paired_cohort_statistics`, `run`). Tests: `tests/test_shadow_edge_cap.py`
(Tracker-Codes, Push, HAC je Gruppe), `tests/test_shadow_hybrid_cohort.py` (Zurückstellen ohne
Artefakte, Nachholen im Folgelauf, fehlgeschlagener Bau terminal und nicht wiederholt, Reihenfolge
nach Anpfiff, Warm-up-Zähler, HAC der Differenz), neu `tests/test_shadow_published.py`
(Erfassung, Erstsichtung, Fremdtag, defekte Datei, Abrechnung nur Tormärkte, Schonfrist,
Kennzahlen).
