# Plan: Massnahme 8 – Hybrid vor der Aktivierung (M2, M3, M4)

Stand 28.10.2026. Massnahme 8 des Gesamtaudits `AUDIT_BERICHT_2026-10-25_CLAUDE.md`. Dieser Plan
ändert noch keinen Code. Grund: Jede der drei Korrekturen verändert die Hybrid-Prognosen selbst.
Der Shadow vergleicht Hybrid und Legacy seit dem 28.10.2026 mit Schlussquoten (Policy
`shadow-model-first-v7`, `docs/audits/2026-10-28-schlussquote-letzter-marktstand.md`). Eine
Änderung jetzt würde diesen Vergleich neu starten, bevor er das erste Ergebnis hat.

## Was der Hybrid ist (für den Owner)

BetBoy rechnet je Spiel eine Tabelle aller Ergebnisse (0:0, 1:0, …). Legacy schätzt die Tore aus
Durchschnitten (stark bei „wie viele Tore“), Dixon-Coles schätzt Angriff und Abwehr gegnerbereinigt
(stark bei „wer gewinnt“). Der Hybrid `dixon_coles_hl365_hybrid` nimmt die Torsumme von Legacy und die
Verteilung auf die Teams von Dixon-Coles. Historisch (29 512 Spiele, 14 Ligen) 148 Markt-Liga-Zellen
besser, 111 schlechter als Legacy; kein Modell schlägt den Markt. Der Hybrid läuft nur im Shadow;
öffentliche Tipps kommen von Legacy.

## Befunde, die vor einer Aktivierung zu lösen sind

| Befund | Stelle | Zahl | Folge |
|---|---|---|---|
| M3 Spread 0 | `challenge_engine.py` (`active = season = form = dc_rate`) | `spread_pp = 0` → Haircut immer 3 pp + Stichprobe/Frische, Einigkeitsscore immer 20/20, Sperre „Saison- und Formmodell widersprechen sich“ nie | Hybrid-Kandidaten sehen sicherer aus als Legacy-Kandidaten; die Validierung 262 statt 224 Zellen ist teilweise ein Scoring-Artefakt |
| M4 ρ | `football_dixon_coles.reweight_totals` | P(0:0) Poisson 0,0781, Dixon-Coles 0,0943, Hybrid 0,0781: rund 25 % der ρ-Korrektur bleiben | Der Hybrid beansprucht die Niedrigtor-Korrektur, setzt sie aber kaum um |
| M2 Kalibrierung | `football_joint_calibration.py` (Datenterm durch Marktanzahl ≈ 40 geteilt) | Kurve −5 pp auf Heimsieg: 10,5 % umgesetzt; 1X2 kohärent 33 %; Über/Unter ±4 pp: 70 % | Betrifft Legacy und Hybrid; die Kurven wirken schwächer als gefittet |

## Vorregistrierte Reihenfolge (erst ausführen, wenn der Prüfplan greift)

Auslöser: Der Prüfplan in `docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md` (300 Paare mit
gültigem Closing in beiden Kohorten, untere HAC-Grenze der paarweisen CLV-Differenz über 0) ist
erfüllt, oder der Owner entscheidet vorher ausdrücklich, den Vergleich neu zu starten.

1. **Unsicherheit statt Spread 0 (M3).** Parametrischer Bootstrap des Dixon-Coles-Fits je Liga und
   Tag (200 Ziehungen aus der inversen Hesse-Matrix der Log-Likelihood; Fallback: Fit auf 200
   Bootstrap-Stichproben der Spiele), daraus je Markt die Standardabweichung der Wahrscheinlichkeit.
   `spread_pp := 2 · SD · 100` ersetzt den Spread für Dixon-Coles und Hybrid; Haircut, Einigkeitsscore
   und die 12-pp-Sperre bleiben unverändert definiert. Hypothese vor dem Lauf: Der Median-Spread
   der Hybrid-Kandidaten liegt zwischen 2 und 8 pp (Legacy heute: Median aus dem Ledger erheben).
2. **ρ ehrlich (M4).** Entweder ρ unter der Hybrid-Likelihood schätzen (Torsumme fest, ρ und
   Verteilung je Summe frei) oder den Hybrid ausdrücklich ohne ρ-Anspruch führen (`rho = 0` im
   Hybrid, Doku und `goal_model_info`). Entscheid nach dem Vergleich der Log-Loss beider Varianten
   auf denselben Walk-forward-Fenstern; ohne signifikanten Gewinn gilt „ohne ρ“.
3. **Kalibrier-Restfehler (M2).** `projection_target_diagnostics` je Markt im Ledger ausgeben
   (Ziel- gegen erreichte Wahrscheinlichkeit). Erst messen, dann als Gate vorschlagen: Ein Markt
   mit Restfehler über 2 pp gilt als nicht kalibriert. Das Gate betrifft auch Legacy und braucht
   einen eigenen Owner-Entscheid, weil es öffentliche Tipps verringern kann.
4. **Neuvalidierung.** `scripts/compare_goal_models.py` und die Release-Gate-Validierung
   (`docs/audits/2026-10-22-hybrid-validierung.md`) mit den Änderungen 1–2 neu rechnen; Ergebnis mit
   n, Intervall und Stichprobe dokumentieren.
5. **Aktivierung.** Nur als eigener Owner-Commit: Produktionsbasis umstellen, neue
   Prediction-Version (Pins, ORIGINAL-Publikation, Tickets), Cache-Neuaufbau, Shadow-Kohorten neu
   beschriften.

## Abbruch

Wenn Schritt 4 den Vorsprung des Hybrids gegenüber Legacy nicht bestätigt (weniger Zellen
signifikant besser als schlechter), bleibt Legacy die Produktionsbasis und der Hybrid wird als
nicht bestätigt protokolliert.
