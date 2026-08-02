# TENNIS — Phase 1 Bericht (Modellbau + Backtest)

**Datum:** 2026-07-29
**Status:** Phase 1 abgeschlossen. Modell kalibriert, Edge-Hypothese identifiziert, Live-Freigabe NICHT erteilt (Shadow-Pflicht wie beim Fußball).

---

## Audit-Nachtrag vom 2. August 2026

Die unten stehenden Phase-1-Zahlen sind Entwicklungsresultate, kein
Gewinnnachweis. Ein erneuter Lauf mit dem aktuellen Produktionscode, den
produktiven Gates und dem in der App tatsächlich verwendeten rohen
Probability-Edge ergab auf dem lokal verfügbaren Zeitraum 2019 sowie
2021–2024:

| Metrik | Aktueller Nachlauf |
|---|---:|
| ATP Hard, Edge ≥ 12 %, Serve- und Erfahrungs-Gate | 909 Wetten |
| Flat-Stake ROI | +8,2 % |
| Bootstrap-Intervall 95 % | −2,3 % bis +19,2 % |
| Jahres-ROI 2019 / 2021 / 2022 / 2023 / 2024 | +15,4 / +8,9 / −9,4 / −15,8 / +34,9 % |
| Brier Modell / de-viggter Pinnacle-Schlussmarkt | 0,2121 / 0,2014 |

Die Schwelle, Belagwahl, Decay- und Indoor-Logik wurden anhand dieses
Entwicklungszeitraums gewählt. Damit ist er **kein unangetasteter Holdout**.
Der lokale Quotencache endet 2024; der Abruf der 2025/2026-Dateien war beim
Audit nicht verfügbar. Die ausgewählte Edge-Stichprobe ist zudem deutlich
überkonfident: durchschnittlich 51,5 % Modellwahrscheinlichkeit bei 37,1 %
realisierter Trefferquote. Die große Sicherheitsmarge fängt einen Teil davon
ab, heilt aber keine falsche Wahrscheinlichkeit.

Zwei frühere Aussagen werden deshalb ausdrücklich korrigiert:

1. Ein größerer Buchmacher-Overround macht N1Bet nicht automatisch „weicher“
   oder günstiger. Mehr Marge ist zunächst ein schlechterer Preis. Nutzbar
   wäre nur ein tatsächlicher Preisfehler, der diese Marge überkompensiert.
2. Probability-Edge und erwarteter ROI sind nicht dieselbe Zahl:

```text
Probability-Edge = p - 1 / Quote
Erwarteter ROI = p * Quote - 1 = Quote * Probability-Edge
```

Der Shadow-Ansatz bleibt fachlich richtig, wurde aber technisch gehärtet:
Event-ID, Quelle und UTC-Startzeit werden gespeichert; gestartete oder zeitlich
nicht verifizierbare Spiele verschwinden aus Tennis und Wett-Check; rote
Modell-Gates können keine Empfehlung mehr persistieren; CLV zählt nur mit
einer zeitgestempelten N1Bet-Referenzquote aus den letzten 60 Minuten vor dem
angesetzten Start. Eindeutig normale ESPN-Finals werden automatisch
abgerechnet, Aufgaben und unklare Endstände bleiben manuell. Modell-Brier und
de-viggter Referenzmarkt-Brier werden auf derselben Stichprobe verglichen.

**Aktuelles Urteil:** interessante ATP-Hard-Hypothese, weiterhin Shadow. Weder
ROI noch CLV oder künftiger Gewinn sind bislang live bewiesen.

---

## 1. Datenarchitektur (zwei getrennte Ebenen)

| Ebene | Quelle | Inhalt | Regel |
|---|---|---|---|
| STATS (quoten-blind) | ManTennisData (GitHub, ATP 1999–2026, MIT) | Aufschlag/Return-Boxscores, Belag, Turnier-Level | Einzige Modell-Quelle, Allowlist ohne Buchmacher-Spalten |
| QUOTEN (nur Bewertung) | tennis-data.co.uk (ATP+WTA, 2000–2026) | Ergebnisse + Pinnacle-/Bet365-Schlussquoten | Darf niemals Feature werden, nur Backtest-Bewertung |

- **97,2 % Namens-Matching** zwischen den Ebenen (Normalizer mit Partikel-Logik: „de Minaur", „O'Connell", „van de Zandschulp", Mittelnamen-Drop „Roman Andres Burruchaga" → „burruchaga r").
- Jeff Sackmanns Referenz-Repos wurden von GitHub entfernt → ManTennisData ist unser Ersatz (aktueller: 2026 läuft, 9.736 Matches allein 2026).

## 2. Modell-Stack

1. **Surface-Elo** (FiveThirtyEight-K: 250/(n+5)^0,4): Overall + pro Belag. Sieht ALLE Matches inkl. Challenger (Elo ist per Konstruktion gegner-adjustiert).
2. **Serve/Return-Modell**: Hold%/Break% pro Belag, **nur Tour-Level** (GS/1000/500/250/OG/Finals), Gegnerstärke-Adjustierung in Odds-Form (Faktor gedeckelt 0,7–1,4), Shrinkage zum Tour-Schnitt (Prior 60 Games), log5-Matchup-Formel (liga-adjustiert, identisch bei Durchschnitts-Gegner).
3. **Exakter Punkt-Simulator** (kein Monte Carlo): liefert ALLE Märkte — Sieger, Satz-Totals (über 3,5 in Bo5 = dein Djokovic-Alcaraz-Case), Game-Totals, Handicaps, exakte Satzergebnisse, Tiebreak-Ja/Nein. Mathematisch verankert (Symmetrie = exakt 50/50, bekannte Grenzfälle getestet).
4. **Walk-forward-Platt-Rekalibrierung** (2-Parameter logistisch auf logit(p), nur Vergangenheit): Rohwahrscheinlichkeiten waren systematisch zu flach (Favoriten unterschätzt, Underdogs überschätzt — Bias-Tabelle im Audit).

## 3. Audit-Trail: gefundene & behobene Fehler

| # | Fehler | Folge | Fix |
|---|---|---|---|
| 1 | Elo/Serve-Key-Mismatch (rohe vs. normalisierte Namen) | Serve-Pfad lief komplett leer | Normalisierung im Tracker |
| 2 | Kalibrierung gegen „Winner-Spalte" (y≡1, degeneriert) | Brier wertlos | Alphabetische Kodierung mit stochastischem y |
| 3 | Aufgabe-Matches (RET) in Training & Wertung | Verfälschte Ratings/ROI | RET = kein State-Update, Void in Wertung |
| 4 | log5 ohne Liga-Normierung | ALLE Holds → 0,85–0,96, Matches Münzwurf | Liga-adjustierte Odds-Form |
| 5 | Challenger-Boxscores in Serve-Ratings | „Squire-Effekt" (Journeyman sieht aus wie Top-10) | Tour-Level-Filter + Gegner-Adjustierung |
| 6 | Keine Erfahrungs-Gate | Wetten auf unbekannte Spieler | Min. 20 Elo-Matches pro Spieler |
| 7 | Kalibrierungs-Test mit konstantem x (singuläre Hessesche) | Falscher Test | Variierende p im Test |

## 4. Backtest-Ergebnisse (Walk-forward, ATP 2019–2024, 5 Jahre, Pinnacle-Schluss)

| Metrik | Modell | Markt (Pinnacle) |
|---|---|---|
| Brier (kalibriert) | **0,2125** | 0,2014 |
| Log-Loss | 0,6143 | 0,5854 |
| Sieger-Trefferquote | 65,5 % | ~70 % |

**ROI nach Edge-Schwelle (Flat-Stake, vs. PINNACLE-SCHLUSS):**

| Schwelle | ROI gesamt | ROI Hard | ROI Clay | ROI Grass |
|---|---|---|---|---|
| ≥ 5 % | −3,0 % | +1,4 % | −8,5 % | −7,9 % |
| ≥ 10 % | +0,1 % | +6,5 % | −7,0 % | −5,6 % |
| ≥ 12 % | +2,8 % | **+10,6 %** (n=1.353) | −5,2 % | −4,3 % |

Jahres-Stabilität Hard ≥12 %: 2019 +16,4 % · 2021 +11,9 % · 2022 −5,3 % · 2023 −3,1 % · 2024 +31,7 %

## 5. Ehrliches Fazit (Wettexperten-Urteil)

1. **Die Kalibrierung wurde deutlich verbessert, bleibt aber schwächer als der
   Markt.** Ein Verhältnis der beiden Brier Scores ist kein belastbares Maß
   für „95 % Markt-Schärfe“.
2. **Breakeven bis leicht positiv gegen Pinnacle-SCHLUSSquoten** auf Hard bei hohem Edge. Gegen die schärfste Linie der Welt ist das ein respektables Ergebnis — aber es ist NICHT stabil über die Jahre (2022/23 negativ). Keine Gewinn-Garantie.
3. **Die zu prüfende Preis-These:** Historische N1Bet-Linien existieren nicht.
   Eine höhere N1Bet-Marge ist zunächst ein Nachteil und kein Edge. Nur live
   dokumentierte Fehlpreise und startzeitnahe Referenzquoten können zeigen, ob
   N1Bet trotz Marge schlagbare Preise anbietet.
4. **Empfohlene Live-Gates v1 (ALLE müssen grün sein):** Hard-Court only · Edge ≥ 12 % (kalibriert) · beide Spieler ≥ 20 Elo-Matches + ≥ 60 Service-Games · kein RET-verletzter Spieler zuletzt · CLV-Tracking Pflicht.
5. **Clay & Grass bleiben No-Bet**, bis die Samples besser sind — Disziplin vor Volumen.

## 6. Offen für Phase 2 (Live-Integration)

- [ ] **N1Bet-Aufgabe-Regel recherchieren** (1 Satz gespielt = Wette gültig? oder Void?) — entscheidet über Settlement-Logik
- [ ] Tägliche Tennis-Pipeline: ESPN/SofaScore-Fixtures (bereits gebaut) → Modell → Vergleich mit manuellen N1Bet-Preisen → nur bei allen Gates: Freigabe
- [ ] **Shadow-Bet-Phase** wie Fußball: 4–6 Wochen Tennis-Predictions ohne Geld, CLV messen — erst dann Echtgeld-Freigabe
- [ ] Satz-/Game-Totals und Handicaps live nutzbar (Simulator liefert sie); Backtest dagegen nicht möglich (keine historischen Totals-Quoten) → Shadow-Phase misst sie
- [ ] WTA: Elo-only möglich (Ergebnisse+Quoten vorhanden), Serve-Stats fehlen (keine freie Quelle) → später
- [ ] Optional später: tennis-api.com (~29 $/Mo) für Live-H2H/Rankings — NUR falls Shadow-Phase Edge beweist
