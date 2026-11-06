# Formstärke: umgesetzt als ausgeschalteter Rechenweg, Messung auf neuen Spielen

Stand 06.11.2026. Owner-Auftrag „Ja, umsetzen“ nach dem bestandenen Vorab-Test
(`docs/audits/2026-11-06-formstaerke-test.md`). Vorgabe: zunächst ausgeschaltet und nur im Hintergrund mitgemessen.

## Was gebaut ist

- **`football_form_strength.py`:** feste Rechnung, Version `form-strength-v1-20261106`.
  - κ = 0,11, Fenster 10 Ligaspiele, mindestens 5 Spiele.
  - Formwerte über ±10 Tore pro Spiel gelten als ungültig.
  - Die Annotation am Modell wird beim Lesen nachgerechnet und geprüft (`form_strength_factors`).
- **`challenge_engine.GOAL_MODEL_FORM_STRENGTH = "legacy_form_strength_v1"`:** ein zusätzlicher Rechenweg neben Legacy
  und den Dixon-Coles-Varianten.
  - Mit diesem Weg multipliziert `_fixture_model` Saison-, Form- und aktive Torerwartung mit
    exp(0,11 · (s_Heim − s_Gast)) bzw. exp(0,11 · (s_Gast − s_Heim)). Die Formwerte s stammen aus derselben
    Liga-Historie, die das Modell bekommt.
  - Hat ein Team weniger als 5 Ligaspiele, gibt es keinen Zuschlag.
  - Fail-closed in Champions League, Europa League und Conference League (`EXCLUDED_LEAGUE_IDS`), auf dem
    Heimatliga-Weg und bei Länderspielen, weil die Prüfung nur Ligaspiele abdeckt. Ebenso bei einer veränderten
    Annotation oder bei einer Torerwartung über 8.
  - Die Referenz-Herkunft der Rohrechnung wird für angepasste Raten als `unavailable` markiert.

## Warum er ausgeschaltet ist

- Kein Produktionsaufrufer wählt diesen Weg. Die App rechnet weiter mit Legacy (`GOAL_MODEL_LEGACY`), und deren
  Ausgabe ist unverändert.
- Die Vorhersage-Version des Wegs ist eine Analyse-Kennung
  (`challenge-engine:coherent-joint-calibration-v14+analysis:legacy_form_strength_v1`). Kandidaten dieses Wegs
  bestehen deshalb nie eine Freigabe. Caches, Validierungen und ORIGINAL-Erfassungen vermischen sich nicht mit Legacy.

## Messung im Hintergrund

- **Werkzeug:** `scripts/form_strength_measurement.py`.
  - Es liest auf dem Server die Liga-Historien, die die App ohnehin täglich in `.shadow_cache` speichert (62 Ligen,
    laufende und letzte Saison).
  - Beide Wege laufen über den unveränderten Validierungsweg `_walk_forward_market_records`, also mit
    Walk-forward-Kalibrierung je Liga.
  - Gezählt werden nur kalibrierte Tormarkt-Prognosen von Spielen ab `--since`, Standard 06.11.2026.
  - Bewertet wird nach denselben vier Bedingungen wie im Vorab-Test.
  - Keine Netzwerkzugriffe, keine Abrufe, nichts wird geschrieben.
- **Aufruf auf dem Server:** `nice -n 19 /opt/betboy/venv/bin/python -I scripts/form_strength_measurement.py`.
- **Entscheid:** Nach rund drei Wochen sollten genug neue Spiele vorliegen. Mit der Länderspielpause sind das etwa
  1000 Ligaspiele. Dann legt Claude die Zahlen vor, und der Owner entscheidet über die Aktivierung.
- **Für eine Aktivierung** braucht es danach noch:
  - eine registrierte Vorhersage-Version mit eigenem Namen (v15 ist für das verworfene Gesetz v2 vergeben),
  - den Wechsel der Produktionsbasis,
  - Pins, ORIGINAL-Rezept, Shadow-Kohorten und Cache-Neuaufbau.
  Das ist ein eigener Owner-Commit, wie beim Hybrid vorgesehen.

## Tests

`tests/test_football_form_strength.py` prüft:
- Registrierung und dass der Weg nie freigibt.
- Die Formwerte (nur Ligaspiele vor Anpfiff, Fenster und Minimum).
- Den Faktor auf allen drei Raten und dass ohne genug Spiele kein Zuschlag kommt.
- Fail-closed ausserhalb des Ligawegs und die Prüfung der Annotation.
- Die Herkunft der Raten.
- Die Gleichheit der Walk-forward-Ergebnisse mit dem gepatchten Studienweg.
- Das Messskript.

## Probelauf auf dem Server (06.11.2026, nur Funktionsnachweis)

Das Messskript lief mit dem Code dieses Branches aus einem temporären Verzeichnis. Grundlage waren die echten
Liga-Historien der App, gezählt ab 01.10.2026: 60 Ligen, 65 720 Prognosen.
- Brier −0,0015 (SE 0,0003), Log-Loss −0,0038 (SE 0,0008).
- 1X2-Log-Loss 1,024 → 1,009.
- Besser in 39 von 60 Ligen, also knapp unter zwei Dritteln.

Diese Spiele überschneiden sich mit den Daten, aus denen die Hypothese stammt. Sie sind deshalb kein Beleg. Der Lauf
hat auch Champions League und Europa League mitgerechnet; seither sind sie ausgeschlossen. Massgeblich ist erst die
Messung ab 06.11.2026.
