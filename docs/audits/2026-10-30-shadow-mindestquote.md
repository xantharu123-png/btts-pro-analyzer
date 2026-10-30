# Shadow-Mindestquote 1,30 (Policy `shadow-model-first-v9`)

Datum: 30.10.2026. Owner-Entscheid im Chat: Tipps zu Quoten um 1,15 bis 1,20 kann jeder blind setzen, sie sagen
nichts über das Modell; der Shadow soll Tipps erst ab einer Quote von **1,30** nehmen.

## Befund

- Der Shadow wählt je Spiel und Kohorte den Kandidaten mit dem besten Modellrang (`_model_first_observations`,
  `candidate_selection_rank`); die Höhe der Quote spielte bis Policy v8 keine Rolle.
- Folge unter v8 (29.10.2026 14:43 bis 30.10.2026 07:47 CET): 2 Tipps, beide `TOTAL_OVER_1_5`, zu 1,25
  (Fixture 1638114) und 1,17 (Fixture 1638115), beide Kohorte legacy; Hybrid 0 Tipps
  (`output/release-20261029-1/verify-03-morning.log`).

## Regel ab v9

- `SHADOW_MIN_ODDS = 1.30`: Ein Kandidat zählt nur, wenn seine Bet365-Öffnungsquote mindestens 1,30 beträgt
  (`_at_minimum_odds`). Unter den übrigen Kandidaten bleibt die Reihenfolge modellgeführt; das entspricht
  `AGENTS.md` („Quoten dürfen … Mindestquote … bestimmen, nie Modell-p oder Reihenfolge“). Beide Kohorten
  (legacy und hybrid) folgen derselben Regel.
- Liegen alle frischen Quoten eines Spiels unter 1,30, entsteht kein Tipp und kein Datenstatus; das Run-Artefakt
  zählt das je Kohorte (`actions.fixtures_below_minimum_odds`, `hybrid_cohort.fixtures_below_minimum_odds`). Das
  Spiel bleibt wie jedes Spiel ohne Tipp bis 30 Minuten vor Anpfiff offen, weil Kontext (etwa Aufstellungen)
  noch weitere Kandidaten freigeben kann.
- Das Run-Artefakt nennt die Grenze (`minimum_odds`).
- Unverändert: Altersgrenze zwölf Stunden für Öffnung und Schluss, Schlussregel, Ausschluss wiederholter
  Marktstände aus der CLV-Evidenz, Edge-Cap-Protokoll. Die 1,20-Grenze der App (Wettfinder, Daily3, RisikoBet)
  ist davon nicht berührt.

## Hypothese und Prüfung

Vor der ersten v9-Zeile festgelegt (Bibel §3.5): Gemessen wird weiterhin der CLV gegen die Bet365-Schlussquote;
eine Freigabediskussion gibt es erst nach 300 eindeutigen Paaren unter v9 (Prüfplan in
`docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md`). Zeilen unter v5 bis v8 bleiben in ihren Kohorten und
zählen nicht mit. Erwartung: weniger Tipps je Tag. Ob das Modell ab 1,30 den Markt schlägt, ist offen; der
Marktbenchmark vom 19.10.2026 fand keine Liga-Markt-Zelle, die den Closing-Markt schlägt (0 von 112).
