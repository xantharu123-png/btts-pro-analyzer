# Vorregistrierung: Aktivierung des kohärenten Hybrids (Shadow mit beiden Basen)

Stand 22.10.2026. Owner-Entscheidung vom 22.10.2026: die Aktivierung des Hybrids
`dixon_coles_hl365_hybrid` wird vorbereitet (neue Prediction-Version, Pins/ORIGINAL für die
neue Basis, Shadow-Lauf mit beiden Basen), **ohne den Produktions-Default zu ändern**.
Bibel §3.5: Hypothese vorab, zeitlich getrennte Prüfung, keine Schwellenanpassung.

## Beobachtung (retrospektiv, kein Nachweis)

- Modellvergleich 20./21.10. (`docs/audits/2026-10-21-dixon-coles-hybrid.md`): der Hybrid
  (Dixon-Coles-Struktur je Torsumme, Legacy-Torsummengesetz) ist in 148 von 560 Zellen
  signifikant besser als Legacy, in 111 schlechter.
- Release-Gate-Validierung 22.10. (`docs/audits/2026-10-22-hybrid-validierung.md`): 262
  statt 224 glaubwürdige und 257 statt 224 freigegebene Liga×Markt-Zellen; kein Markt
  verliert Freigaben. Beides ist Basisraten-Skill; kein Modell schlägt den Closing-Markt
  (`docs/audits/2026-10-19-marktbenchmark.md`).

## Hypothese

H: Unter derselben Preispolicy hat die Hybrid-Kohorte prospektiv einen höheren CLV gegen
die Closing-Line als die Legacy-Kohorte auf denselben Spielen, und ihre Trefferquote liegt
nicht unter der implizierten Wahrscheinlichkeit ihrer Opening-Quoten. Die paarweise
Differenz (Hybrid − Legacy je Spiel) ist die Prüfgrösse.

## Pins (feste Vertragstoken der neuen Basis)

| Token | Legacy (Produktion) | Hybrid (Shadow) |
|---|---|---|
| Prediction-Version | `challenge-engine:coherent-joint-calibration-v14` | `challenge-engine:dc-hl365-hybrid-joint-calibration-v1` |
| Modell-Vertragssignatur | `challenge-engine:hac-fdr-executable-frechet-v11` | `challenge-engine:hac-fdr-executable-frechet-v11+dc-hl365-hybrid-v1` |
| Marktkatalog | unverändert `football-market-catalog:96-bounded-multigoal-v2` | gleich |
| Kalibriergesetz | `football-joint-settlement-projection-v1` | gleich (die Basis ändert die Rohverteilung, nicht die Projektion) |

Registrierung in `challenge_engine` (`prediction_version_for_goal_model`,
`model_contract_signature_for_goal_model`). Validierungsmetriken, Kandidaten und
Marktvergleiche einer Basis tragen deren Version; der Artefakt-Cache
(`challenge_model_cache`) und der Shadow-Dateicache sind dadurch getrennt. Die
Echtgeld-Freigaben (`candidate_is_15k_model_eligible`,
`candidate_is_wettfinder_release_credible`) verlangen weiterhin genau die
Legacy-Version: Hybrid-Kandidaten sind damit konstruktiv nie freigabefähig.

## ORIGINAL für die neue Basis

`capture_football_original` erfasst die Hybrid-Basis im bestehenden Schema v2: das
Feld `goal_model` trägt zusätzlich die Basis, Rho, den Dixon-Coles-Fit und die Legacy-
Raten des Torsummengesetzes; `goal_provenance.reference_weights` bekommt die Variante
`football-goals-hybrid-dc-v1` (Legacy-Köpfe wie bisher plus Fit-Fenster mit
Zerfallsgewichten). Replay (`replay_joint_calculation`) rechnet mit derselben Basis nach;
der Fit im Erfassungspfad startet kalt (kein Warmstart), damit die Nachrechnung
byteidentisch ist. Code-Identität (`executed_code_identity`) führt die Token je Basis.
Trainingsfälle (`football_training`) nehmen nur Legacy-ORIGINALs an; Hybrid-ORIGINALs
sind dort ausdrücklich `original_basis_not_trainable` (fail-closed).

## Shadow-Lauf mit beiden Basen

`shadow_clv_automation` bewertet jedes fällige Spiel zusätzlich mit der Hybrid-Basis
(eigene Validierung und Kalibrierung aus demselben Walk-forward, eigener Cache) und
protokolliert den Modell-zuerst-Tipp mit **derselben Quotenantwort** unter der
Hybrid-Modellversion. Die Legacy-Kohorte wird zuerst geschrieben und von Fehlern der
Hybrid-Kohorte nie berührt. Schalter `BETBOY_SHADOW_HYBRID_BASIS` (Default an, `0`
schaltet ab). Nationalteam-Spiele (Liga 5) haben keine Hybrid-Kohorte (fail-closed).
Die Hybrid-Artefakte entstehen **vor** der Bewertung in einer Walk-forward-Passage je Liga
mit Zeitbudget (Ligen mit dem frühesten offenen Anpfiff zuerst); die Bewertung nutzt nur fertige
Artefakte und lässt ein Spiel ohne Artefakte bis zum letzten Versuch (30 min vor Anpfiff) offen,
sofern der Bau der Liga nicht am selben Tag fehlgeschlagen ist. Holt der Hybrid ein Spiel in einem
späteren Lauf nach, stammt seine Öffnungsquote aus einer jüngeren Quotenantwort als die
Legacy-Zeile. Das Run-Artefakt enthält beide Kohorten, die paarweise Auswertung mit HAC-Intervall
der CLV-Differenz (`difference`) und die Trefferquote je Kohorte.

*Nachtrag 25.10.2026:* Bis dahin lief das Warm-up nach der Bewertung und fehlende Artefakte galten
als terminal, sodass die Hybrid-Kohorte strukturell leer blieb (Gesamtaudit D4); die Trefferquoten
verglichen gegen `WIN` statt des gespeicherten `Won` (S3). Behoben mit Massnahme 2
(`docs/audits/2026-10-25-shadow-massnahme-2.md`).

*Nachtrag 28.10.2026:* Bis zum 27.10. wurde keine Schlussquote erfasst (15-Minuten-Stempel gegen
Drei-Stunden-Takt von API-Football). Seit dem 28.10. ist die Schlussquote der letzte Marktstand vor
Anpfiff (höchstens drei Stunden alt); Paare zählen nur, wenn beide Kohorten einen neuen Marktstand haben
(`pairs_without_new_market_state`), Policy v7 (`docs/audits/2026-10-28-schlussquote-letzter-marktstand.md`).

## Prüfplan

1. Mindestens 300 abgerechnete Spiele mit gültigem Closing in **beiden** Kohorten
   (paarweise, gleiche Spiele).
2. Paarweise CLV-Differenz mit HAC-Intervall; Trefferquote je Kohorte gegen die
   implizierte Opening-Wahrscheinlichkeit; Brier je Kohorte.
3. Aktivierung nur, wenn die untere Konfidenzgrenze der paarweisen Differenz über 0 liegt
   und die Hybrid-Kohorte keine schlechtere Kalibrierung zeigt. Dann: Produktionsbasis
   umstellen (eine Owner-Entscheidung mit eigenem Commit), Cache-Neuaufbau, Pins für
   Tickets und ORIGINAL-Publikation auf die neue Version.

## Abbruchkriterien

Keine messbare Differenz nach 300 Paaren oder weniger als 50 Paare in 120 Tagen: der
Hybrid bleibt Shadow, die Hypothese wird als nicht bestätigt protokolliert.
