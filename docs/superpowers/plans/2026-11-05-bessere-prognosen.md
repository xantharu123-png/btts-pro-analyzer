# Plan: bessere Prognosen – Ligastärke, Kalibrierung, Ausfälle, Wetter

Stand 05.11.2026. Owner-Auftrag: „bessere Berechnungen, Statistiken, Wahrscheinlichkeiten … neben Wetter und co“,
vorher ein Sicherungspunkt, damit wir zurückkönnen, falls es nach einer Änderung schlechter wird. Dieser Plan ändert
noch keinen Code.

## 0. Sicherungspunkt (erledigt)

- Git-Tag **`modell-sicherung-2026-11-05`** auf dem Live-Stand `03ce254` (Release 20261105-3), auf GitHub.
  Rückweg: Release-Helfer mit dem Tag als Ziel. Modelländerungen schreiben keine alten Daten um; eine
  Datenbankkopie ist dafür nicht nötig.
- Basiswerte zum Vergleich, abgerechnete Prognosen bis 04.11.2026 (`scripts/forecast_baseline_metrics.py`,
  Ausgabe `output/baseline-20261105/baseline_metrics.log`):

| Sport | Prognosen | versprochen | eingetroffen | Brier (Grundquote) | Log-Loss |
|---|---:|---:|---:|---:|---:|
| Fussball | 9180 | 60,7 % | 60,3 % | 0,1990 (0,2394) | 0,5824 |
| Tennis | 377 | 62,1 % | 60,7 % | 0,2253 (0,2385) | 0,6419 |
| E-Sport | 494 | 62,7 % | 59,5 % | 0,2351 (0,2409) | 0,6618 |
| Eishockey | 252 | 50,0 % | 50,0 % | 0,2398 (0,2500) | 0,6714 |
| Basketball | 40 | 50,0 % | 50,0 % | 0,2213 (0,2500) | 0,6279 |

  Fussball je Band: unter 40 % 28,3 → 26,1; 50–60 % 54,9 → 54,0; 70–80 % 74,9 → 74,9; 80–90 % 84,1 → 85,1.
- **Regel für jede Änderung:** Sie geht nur live, wenn sie im Walk-forward-Test (nur Daten vor dem jeweiligen Spiel)
  Log-Loss und Brier gegenüber diesen Basiswerten verbessert, die Kalibrierung in keinem Band um mehr als 2
  Prozentpunkte verschlechtert und danach im Betrieb nicht schlechter misst. Sonst Rückweg zum Tag.

## Ausgangslage

- Gerechnet wird ein Tormodell: Torerwartung aus 12 Heim-/Auswärtsspielen (75 %) und 6 Formspielen (25 %),
  zum Ligaschnitt geglättet, mit xG gemischt, Poisson-Ergebnistabelle, Kalibrierung je Liga und Markt.
- Wetter, Ausfälle, Aufstellung und H2H sind nur Sperren und ändern keine Prozentzahl
  (`_context_probability_integration_summary`: „für eine Änderung fehlen validierte Effektgrössen“).
- Europapokal-Spiele (`cross_competition_provisional_forecast`, 18 Spiele am 5.11.) liegen im Mittel 14,7
  Prozentpunkte neben dem Markt, Ligaspiele 7,3 (`output/check-20261104/scope_gap.log`). Dem Modell fehlt die
  Ligastärke.
- Marktmischung vom 20.10. (`docs/audits/2026-10-20-marktmischung.md`): Die Schlussquote sagt Ergebnisse besser
  voraus als das Modell (Log-Loss 0,6158 gegen 0,6346); der optimale Modellanteil war 0. Das ist die ehrliche
  Messlatte.
- Der Hybrid (`dixon_coles_hl365_hybrid`) war historisch in 148 Markt-Liga-Zellen besser, in 111 schlechter als
  das Live-Modell. Er läuft nur im Shadow; vor einer Aktivierung sind M2–M4 offen
  (`docs/superpowers/plans/2026-10-28-hybrid-vor-aktivierung.md`).

Vorhandene Daten (`context_models.db`, nur gezählt):

| Art | Quelle | Spiele | seit |
|---|---|---:|---|
| Ausfälle | API-Football | 1771 | 10.09. |
| bestätigte Aufstellung | API-Football | 1761 | 10.09. |
| Einsätze/Minuten | API-Football | 2160 | 14.09. |
| Belastung/Ruhetage | ESPN | 3236 | 10.09. |
| Wetter vor Anpfiff | OpenWeather | 1119 | 28.09. |

## Schritte, nach Nutzen geordnet

1. **Ligastärke für Europapokal-Spiele.** Champions League, Europa League und Conference League sind im
   Ligakatalog. Aus den Europapokal-Duellen der letzten Spielzeiten wird je Liga ein zeitgewichteter Stärkefaktor
   für Angriff und Abwehr geschätzt (Poisson-Regression mit Liga-Effekt). In Europapokal-Spielen wird die
   Torerwartung beider Teams damit umgerechnet. Prüfung: Walk-forward nur auf Europapokal-Spielen. Ziel: Log-Loss
   besser und Abstand zum Markt deutlich kleiner als 14,7 Punkte. Kein zusätzlicher API-Verbrauch.
2. **Kalibrierung reparieren (M2).** Die Kalibrierkurven wirken nur teilweise (Heimsieg 10,5 %, 1X2 33 %,
   Über/Unter 70 % des gefitteten Effekts), weil der Datenterm durch die Marktanzahl geteilt wird. Das betrifft
   alle Fussball-Prognosen. Prüfung gegen die Basiswerte je Band.
3. **Ausfälle und Aufstellung als Zahl.** Merkmal je Team: Anteil der fehlenden Stammspieler an Einsatzminuten
   und Toren (aus den gespeicherten Einsätzen). Der Effekt auf die Torerwartung wird über den vorhandenen
   gekoppelten Rechenweg `q(h,a) ∝ p(h,a)·exp(dh·h + da·a)` per Likelihood gelernt. Aktiviert wird er nur, wenn er
   im Walk-forward-Test belegt ist; sonst bleibt es bei der Sperre. Danach dasselbe für Ruhetage und Belastung.
4. **Hybrid aktivieren (Massnahme 8).** M3 (Unsicherheit statt Spread 0), M4 (ρ ehrlich) und M2 (Schritt 2), dann
   der Prüfplan. Jede der Schritte 1–3 verändert auch die Live-Prognosen und startet den Shadow-Vergleich neu.
5. **Wetter als Zahl.** 1119 Spiele reichen für Wind-/Regen-Effekte von wenigen Zehnteln Toren nicht. Zwei Wege:
   weiter sammeln (rund 1000 Spiele pro Monat), oder kostenloses historisches Wetter ohne Schlüssel
   (Open-Meteo-Archiv) für die Spiele der Historie nachladen. Der zweite Weg ist eine neue externe Quelle und
   braucht ein Owner-OK. Wetter vor Anpfiff ist eine Prognose, keine Stadionmessung.
6. **Marktinformation (Owner-Entscheid).** Den grössten messbaren Gewinn brächte es, die Wahrscheinlichkeit mit
   der Marktquote zu mischen. Quoten blieben in der App unsichtbar, aber die Auswahl würde sich dem Markt annähern.
   Nur auf ausdrücklichen Wunsch.
7. **Andere Sportarten später.** Tennis überschätzt im Band 50–60 % (55,1 versprochen, 48,1 eingetroffen,
   n=183), E-Sport liegt rund 3 Punkte zu hoch.

## Ablauf je Schritt

- Eigener Branch und PR, Offline-Walk-forward-Bericht mit Vergleich zu den Basiswerten, Owner-OK für Merge und
  Release, danach dieselbe Messung im Betrieb. Wird es schlechter: Release auf `modell-sicherung-2026-11-05`.
- Schritte 1–4 brauchen keine zusätzlichen API-Abrufe; neue Quellen nur mit Owner-OK, nur kostenlose
  (Entscheid vom 14.10.).

## Offene Entscheide des Owners

1. Reihenfolge 1 → 2 → 3 → 4 (Empfehlung) oder eine andere?
2. Historisches Wetter von Open-Meteo nachladen (Schritt 5)?
3. Marktinformation in die Wahrscheinlichkeit einbeziehen (Schritt 6)?
