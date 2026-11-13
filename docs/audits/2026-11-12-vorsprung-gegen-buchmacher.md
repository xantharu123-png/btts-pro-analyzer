# Vorsprung gegenüber Buchmachern? Analyse vom 12.11.2026

Owner-Frage am 12.11.2026: „schauen wir, ob wir gegenüber Buchmachern einen Vorsprung bauen können“, danach „du
musst doch eine Idee haben“. Alles nur gelesen: keine API-Abrufe, keine Änderung an Code, Server oder Daten.

## Ergebnis in Kürze

- **Kein belegter Vorsprung.** Wo das Modell vom Markt abweicht, behält der Markt recht.
- Sechs Ideen gerechnet, eine zeigt ein Plus: **Preisjagd ohne Modell** (bester Preis gegen die faire
  Pinnacle-Chance). Das Plus ist nur mit dem Bestpreis aus sehr vielen Buchmachern gesichert und in der laufenden
  Saison negativ.
- **Owner-Entscheid 12.11.2026: „Nein, lassen“.** Die Preisjagd wird nicht gemessen und nicht gebaut. Nicht erneut
  vorschlagen, ausser der Owner fragt danach. Das passt zu „Modell vor Preis“ und „keine Auswahl nach Quote“.

## Daten und Methode

| Quelle | Umfang |
|---|---|
| Eigene Tipps: `runtime_state/forecast_evidence.db` auf dem VPS | 6 365 abgerechnete Auswahlen mit Einstiegsquote, Anpfiff 07.09.–09.11.2026; je Spiel, Markt und Auswahl die früheste Prognose-Revision mit Einstiegsquote; 3 676 davon mit fairer Marktchance; 1 989 mit Pinnacle |
| Benchmark-Dateien: football-data.co.uk, lokal unter `.worktrees/claude-audit-repairs-20261019/runtime_state/market_benchmark/` | 98 Dateien, 14 Ligen, Saisons 2019/20–2025/26, 36 369 Spiele, 165 888 Auswahlen (1X2 und Tore 2,5) mit Pinnacle früh und Schluss; nur 1X2: 99 636 |

- **Faire Marktchance:** je Buchmacher entmargt (Shin ab drei Ausgängen, Power bei zwei,
  `betting_math.no_vig_market`), dann Median über die Buchmacher, wie `market_consensus.no_vig_market_probability`.
- **Pinnacle** in den eigenen Daten: `api-football:4`, `odds-api:pinnacle`, `oddspapi:pinnacle`.
- **Rendite** = Quote × Treffer − 1 je Wette, gleicher Einsatz. Bereiche sind 95 %. In `vorsprung.py` je Wette
  gerechnet, in den übrigen Skripten nach Spiel gebündelt, weil Auswahlen eines Spiels gemeinsam gewinnen oder
  verlieren.
- **Auswahl:** Die eigenen Daten enthalten nur Auswahlen, die das Modell vorgeschlagen hat.
- **Skripte und Ausgaben** (nicht in Git): `C:\Projekt\BetBoy\output\vorsprung-20261112\` mit `vorsprung.py`,
  `ideen.py` (beide auf dem Server, `sudo -n -u betboy nice -n 19 /opt/betboy/venv/bin/python -I /tmp/x.py`),
  `ideen_frueh.py`, `ideen_frueh2.py` (lokal, `python -I <skript> <datenordner> <projektordner>`) und den
  `*.out.txt`.
- **Hinweis zur Datenbank:** `forecast_quotes` hat keinen Index auf `forecast_id`. Quoten in einem Durchgang lesen;
  Abfragen mit `EXISTS` je Zeile hängen über zehn Minuten.

## 1. Modell gegen Markt (eigene Tipps)

Brier-Unterschied Modell minus Markt, mal 1000. Positiv heisst: das Modell ist schlechter.

| Markt | Auswahlen | Brier Modell − Markt | „Modell sieht Wert“: Wetten, Rendite |
|---|---|---|---|
| Teamtore | 3 498 | +6,4 [+3,1; +9,8] | 1 009, −13,2 % [−18,9; −7,5] |
| Ecken | 1 017 | +1,6 [−5,3; +8,5] | 246, −9,7 % [−23,2; +3,8] |
| Doppelte Chance | 681 | +11,1 [+2,6; +19,5] | 152, −16,6 % [−32,7; −0,6] |
| 1X2 | 670 | +17,4 [+8,5; +26,3] | 222, +3,0 % [−21,0; +26,9] |
| Tore gesamt | 320 | +10,2 [+2,7; +17,6] | 76, −13,6 % [−34,4; +7,2] |

- „Modell sieht Wert“ heisst Modellchance × Median-Quote > 1.
- 1X2 ist nicht stabil: erste Hälfte des Zeitraums +15,6 %, zweite Hälfte −7,0 % (Teilung am 24.10.2026).
- Tennis (90 Auswahlen) hat keine Marktchance in den Daten.

Je weiter das Modell über dem Markt liegt, desto klarer liegt der Markt richtig:

| Modell minus Markt | Auswahlen | Modell | Markt | getroffen |
|---|---|---|---|---|
| unter 0 Punkte | 2 246 | 68,8 % | 76,0 % | 74,8 % |
| 0 bis 3 | 433 | 66,5 % | 65,1 % | 64,4 % |
| 3 bis 6 | 337 | 65,8 % | 61,4 % | 57,3 % |
| 6 bis 10 | 290 | 62,7 % | 54,9 % | 51,4 % |
| über 10 | 370 | 63,1 % | 47,3 % | 50,0 % |

Schlussquoten sind fast nie gespeichert (96 Zeilen, keine auswertbar). Ob frühe Preise besser sind als die Preise
kurz vor Anpfiff, lässt sich in den eigenen Daten nicht messen. Alle Einstiegsquoten liegen höchstens 24 Stunden
vor Anpfiff.

## 2. Sechs Ideen

| Idee | Daten | Ergebnis |
|---|---|---|
| Preisvergleich ohne Modell (bester Preis × Median-Marktchance > 1) | eigene | Teamtore 373 Wetten, −1,3 % [−5,4; +2,8]; Tore gesamt 70, +2,8 % [−7,0; +12,6]; Ecken 125, −17,2 % [−30,3; −4,2] |
| Langsamer Buchmacher (bester anderer Preis × faire Pinnacle-Chance > 1) | eigene | 252 Wetten, +0,9 % [−10,7; +12,5]; ab 2 % Vorteil 53 Wetten, −14,3 % [−41,2; +12,6]; zu wenig Fälle |
| Nischen mit wenigen Buchmachern | eigene | Bei 1–3 Buchmachern ist das Modell gleichauf mit dem Markt (Brier −0,4 [−9,0; +8,1], 698 Auswahlen), blind zum besten Preis aber −5,2 % [−10,0; −0,4]; ab 8 Buchmachern Brier +15,8 [+7,8; +23,9] |
| Preisvorteil und Modell einig | eigene | 132 Wetten, +0,5 % [−16,8; +17,8]; Modell dagegen: 475 Wetten, −3,7 % [−8,2; +0,7] |
| Nur Favoriten, blind zum besten Preis | eigene | Marktchance 70–80 %: 848 Wetten, −5,8 % [−9,9; −1,7]; 80–90 %: 740, −4,0 % [−7,3; −0,6]; ab 90 %: 395, −2,3 % [−5,5; +0,8] |
| Gegen das Modell wetten (Gegenseite, wenn das Modell 3–10 Punkte über dem Markt liegt) | eigene | 501 Wetten, +3,5 % [−8,8; +15,7]; über 10 Punkte: 293, −13,9 % [−26,6; −1,1] |

- Pinnacle ist in den eigenen Daten nicht genauer als der Median aller Buchmacher (Brier × 1000: Modell 228,2,
  Median 217,7, Pinnacle 217,9 auf 1 989 Auswahlen; Modell minus Pinnacle +10,3 [+5,1; +15,4]).
- Eine Auswertung nach Liga ging nicht: Die Prognose-Zeilen tragen keine Liga, nur die `fixture_id` in
  `quote_identity`.

## 3. Preisjagd in den Benchmark-Dateien

Regel: Wette nur, wenn Preis × faire Pinnacle-Chance > 1 + t. Vorteile über 15 % gelten als Datenfehler und
zählen nicht.

Blind, jede Auswahl: Bet365 früh −6,4 % [−6,7; −6,1], Bet365 Schluss −6,5 % [−6,8; −6,2], Bestpreis früh −2,1 %
[−2,5; −1,8], Bestpreis Schluss −1,1 % [−1,5; −0,8], Pinnacle Schluss (1X2) −4,6 % [−5,1; −4,1].

| Regel (Schluss gegen Pinnacle Schluss, 1X2) | t = 0 | t = 0,02 | t = 0,04 |
|---|---|---|---|
| Bestpreis aller Buchmacher | 39 081 Wetten, +2,5 % [+1,1; +3,9] | 18 686, +3,5 % [+1,2; +5,9] | 9 010, +5,5 % [+1,6; +9,4] |
| Bester von 12 namentlichen Buchmachern, ohne Wettbörse | 13 490, +1,4 % [−1,2; +4,0] | 5 351, +2,9 % [−1,7; +7,5] | 2 381, +4,3 % [−3,2; +11,8] |
| Bet365 allein | – | 1 444, +4,1 % [−5,5; +13,6] | – |

- Mit Tore 2,5 dazu, Bestpreis Schluss: t = 0 → 60 866 Wetten, +2,3 % [+1,3; +3,3]; t = 0,02 → 27 353, +3,7 %
  [+1,9; +5,4]; t = 0,04 → 12 156, +5,6 % [+2,6; +8,7].
- Ohne die 15-%-Grenze, t = 0,02: 19 176 Wetten, +4,1 % [+1,7; +6,5].
- Nach Quotenbereich, t = 0,02: Quote 1–2 → +4,1 % [+0,9; +7,4]; 2–3,5 → +4,5 % [+1,4; +7,6]; 3,5–7 → +3,0 %
  [−1,1; +7,0]; ab 7 → +1,3 % [−13,7; +16,3].
- Früh gegen früh, Bestpreis, t = 0,02: 10 470 Wetten, Rendite +0,6 % [−2,7; +3,9], gegen den Schlusskurs +2,7 %
  [+2,5; +2,9]. Bet365 früh: 1 387 Wetten, +7,2 % [−3,8; +18,2], gegen den Schlusskurs +1,2 % [+0,6; +1,8].

Je Saison, Bestpreis Schluss, 1X2, t = 0,02:

| Saison | Wetten | Rendite |
|---|---|---|
| 2019/20 | 2 805 | +9,5 % [+2,7; +16,2] |
| 2020/21 | 3 354 | +4,0 % [−1,9; +9,9] |
| 2021/22 | 4 268 | +3,7 % [−1,0; +8,4] |
| 2022/23 | 3 063 | +4,3 % [−1,5; +10,1] |
| 2023/24 | 2 703 | −0,7 % [−6,5; +5,1] |
| 2024/25 | 1 906 | +4,3 % [−3,1; +11,8] |
| 2025/26 | 587 | −15,4 % [−26,7; −4,1] |

## Vorbehalte

- **„Bestpreis“ ist das Maximum sehr vieler Buchmacher** aus dem Quotenportal der Quelle. Niemand hat bei allen
  ein Konto. Mit 12 namentlichen Buchmachern ist das Plus nicht gesichert, mit einem einzelnen gar nicht (rund
  200 Wetten pro Saison).
- **Laufende Saison negativ**, auch mit den namentlichen Buchmachern (476 Wetten, −18,4 % [−30,8; −6,0]). Die 2025/26
  neu geführten Buchmacher zeigen auffällig schlechte Werte (BMGM 171 Wetten, −36,7 %; BV 197, −30,9 %). Die Ursache
  ist nicht geklärt; möglich ist, dass die Pinnacle-Schlussquote der Quelle seit 2025/26 weniger frisch ist. Nicht
  belegt.
- **Buchmacher begrenzen oder sperren** Kunden, die so wetten.
- **Mehrfaches Testen:** sechs Ideen, eine positiv. Für sie sprechen die grosse Fallzahl und der Anstieg mit der
  Schwelle, gegen sie die laufende Saison.
- Die eigenen Quoten sind Sammelstände von API-Football, oft Stunden alt. Ein Preisvorteil darin ist nicht sicher
  noch zu haben.

## Einordnung

Das Ergebnis passt zum Benchmark vom 19.10.2026 (`docs/audits/2026-10-19-marktbenchmark.md`: 0 von 112 Zellen
schlagen den Schlussmarkt) und zur Quotenanalyse vom 09.11.2026 (Fallen 47 % getroffen bei 61 % versprochen).
BetBoy bleibt eine Prognose-App ohne Vorsprungsbehauptung.
