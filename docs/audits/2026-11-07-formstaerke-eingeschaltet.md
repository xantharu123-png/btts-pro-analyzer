# Formstärke eingeschaltet: neue Produktionsbasis der Fussball-Prognosen

Stand 07.11.2026. Owner-Entscheid „Jetzt einschalten“ (Frage vom 07.11.: „Messung abwarten“ oder „Jetzt einschalten“).
Damit weicht der Owner bewusst von der Vorab-Regel ab. Diese hatte nach dem bestandenen Test
(`docs/audits/2026-11-06-formstaerke-test.md`) noch rund drei Wochen Messung auf neuen Spielen vorgesehen. Die Messung
läuft trotzdem weiter und wird vorgelegt.

## Was sich ändert

- **Produktionsbasis:** `challenge_engine.PRODUCTION_GOAL_MODEL = GOAL_MODEL_FORM_STRENGTH` (`legacy_form_strength_v1`).
  - Gerechnet wird die Legacy-Torerwartung mal exp(0,11 · (s_eigen − s_gegner)). s ist die Tordifferenz pro Spiel der
    letzten 10 Ligaspiele, mit mindestens 5 Spielen.
  - Die Rechnung ist unverändert gegenüber dem Test (`football_form_strength.py`, κ fest).
- **Kein Zuschlag** (die Torerwartung bleibt wie bei Legacy):
  - in Champions League, Europa League und Conference League,
  - auf dem Heimatliga-Weg (dort gilt die Ligastärke),
  - bei Länderspielen,
  - bei Teams mit weniger als 5 Ligaspielen.

  Der Test hat nur Ligaspiele abgedeckt. Ein Zuschlag ausserhalb davon wäre nicht belegt. Ein Sperren dieser Spiele
  hätte zum Beispiel die Länderspiele der Pause vom 9. bis 17.11. ganz aus der App genommen.
- **Versionen:**
  - Die Prognose-Version ist neu: `CHALLENGE_PREDICTION_VERSION = challenge-engine:legacy-form-strength-joint-calibration-v1`.
  - Die bisherige Version `challenge-engine:coherent-joint-calibration-v14` gehört weiter zur Legacy-Basis
    (`LEGACY_PREDICTION_VERSION`), zu ihren Caches und zu den eingefrorenen ORIGINALs.
  - Die Vertragssignatur der Tickets (`CHALLENGE_MODEL_CONTRACT_SIGNATURE`) bleibt gleich. Offene 15K-Tickets bleiben
    damit gültig.
- **Aufrufer:** Die Produktionsaufrufer nennen die Basis ausdrücklich:
  - `challenge_15k.scan_daily_challenge` an vier Stellen und `_cached_market_artifact`. Das umfasst Wettfinder, 15K,
    Doublebet und Modell-Refresh.
  - Der Shadow mit `build_fixture_candidates` und den Validierungs- und Kalibrier-Caches.
  - Die Engine-Funktionen selbst behalten Legacy als Standard, für Nachrechnung, Replay und Analysen.
- **Caches:** Validierungen und Kalibrierungen (`challenge_model_cache`, Shadow-Dateicache) tragen die Version. Sie
  werden beim ersten Lauf mit der neuen Basis neu gerechnet. Dafür braucht es nur Rechenzeit, keine zusätzlichen
  Abrufe. Die Shadow-Historien werden einmal neu geladen.
- **Shadow:** `SHADOW_MODEL_VERSION` folgt der Produktionsversion. Die Evidenzzählung (1000 Tipps derselben
  Modell-/Policy-Version) beginnt für die neue Basis bei null.
- **ORIGINAL-Erfassung:**
  - Wo die Formstärke wirkt, ist die Herkunft der angepassten Raten nicht modelliert
    (`reference_weights.kind = unavailable`). Die Erfassung wird dann als „partial“ gespeichert, wie bei der
    Ligastärke.
  - Das Kontext-Training nimmt weiterhin nur Legacy-ORIGINALs an. Es ist derzeit ohne qualifiziertes Modell.

## Hybrid (Plan-Schritt 4)

Owner-Entscheid vom selben Tag: Die Prüfung des Hybrids wird umgestellt. Statt 300 bzw. 1000 Shadow-Paaren (am 07.11.:
0) gilt dieselbe Messung wie bei der Formstärke:
```
scripts/form_strength_measurement.py --baseline legacy_form_strength_v1 --candidate dixon_coles_hl365_hybrid
```
Gemessen werden kalibrierte Tormärkte auf neuen Spielen, nach denselben vier Bedingungen. Der Hybrid wird dabei gegen die
neue Produktionsbasis gemessen.

## Rückweg

Release auf den Stand davor (`c207b86`). Gespeicherte Daten werden nicht umgeschrieben. Die Caches der alten Version
sind noch vorhanden.

## Messung

- **Formstärke gegen Legacy:**
  `scripts/form_strength_measurement.py --since 2026-11-06` (Standard `--baseline legacy
  --candidate legacy_form_strength_v1`).
- **Hybrid gegen Produktion:** wie oben.
- **Termin:** in rund drei Wochen, etwa 1000 neue Ligaspiele.
