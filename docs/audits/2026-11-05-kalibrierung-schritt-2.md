# Plan „bessere Prognosen“, Schritt 2: stärkere Kalibrierung geprüft und verworfen

Stand 05.11.2026. Owner-Auftrag „alles machen“ (Plan `docs/superpowers/plans/2026-11-05-bessere-prognosen.md`,
Schritt 2, Befund M2 aus `docs/superpowers/plans/2026-10-28-hybrid-vor-aktivierung.md`).

## Frage

Die Kalibrierkurven je Markt wirken in der gemeinsamen Ergebnistabelle nur teilweise, weil die Projektion den
Datenterm durch die Zahl der Märkte teilt (`football_joint_calibration`, Gesetz v1). Das Gesetz v2 ohne diese
Teilung ist seit dem 13.10. als Kandidat im Code (`LAW_VERSION`, Vorhersage-Version v15). Es ist nicht aktiv, weil es
in einem Vergleich mit 304 Spielen aus 2 Ligen schlechter war (`docs/audits/2026-10-13-claude-audit-reparaturen.md`).
Jetzt wurde dieser Vergleich auf alle lokal vorhandenen Ligen ausgeweitet.

## Prüfung

- Werkzeug: dasselbe Offline-Replay wie am 13.10., `output/audit-repairs-20261013/compare_calibration.py`, hier
  ausgeweitet als `output/kalibrierung-20261105/compare_all.py`.
- Daten: je Liga der neueste vertrauensgeprüfte Cache in `.shadow_cache`, also 30 Ligen der Saison 2026 mit Stand
  Ende Juli bzw. 1. August.
- Ablauf: Die Kurven werden vor jedem Spieltag nur aus früheren Spielen gelernt. Beide Gesetze bekommen dieselbe
  Rohtabelle und dieselben Kurven.
- Keine Provider-Abrufe, keine Änderung an Caches, Laufzeit 151 Sekunden.
- Umfang: 3039 bewertete Spiele, 121 560 Marktprognosen (40 Tormärkte je Spiel).
- Standardfehler nach Liga gebündelt (`analyse_pool.py`, Ausgabe `analyse_pool.log`).

| Mass | v1 (live) | v2 | Differenz (SE) | v2 schlechter in |
|---|---:|---:|---|---:|
| Brier je Spiel | 0,19601 | 0,19661 | +0,00060 (0,00014) | 24 von 30 Ligen |
| Log-Loss je Markt | 0,57440 | 0,57590 | +0,00150 (0,00033) | 25 von 30 Ligen |
| Log-Loss des genauen Ergebnisses | 3,0138 | 3,6994 | +0,686 (0,095) | 26 von 30 Ligen |

Kalibrierung über alle Tormärkte (versprochen → eingetroffen):

| Band | v1 (live) | v2 |
|---|---|---|
| 10–20 % | 15,1 → 14,5 | 15,1 → 15,3 |
| 30–40 % | 35,0 → 35,1 | 34,8 → 35,1 |
| 50–60 % | 54,9 → 55,5 | 54,9 → 55,2 |
| 70–80 % | 74,3 → 74,3 | 74,5 → 74,3 |
| 80–90 % | 84,8 → 85,5 | 84,8 → 84,6 |

## Ergebnis

- Das heutige Gesetz v1 ist in jedem Band schon auf weniger als 1 Prozentpunkt kalibriert.
- v2 verbessert die Bänder kaum. Brier und Log-Loss werden aber deutlich schlechter, in mehr als vier von fünf Ligen.
  Das genaue Ergebnis verliert stark, weil die volle Zielwirkung Masse zwischen den Ergebnisfeldern verschiebt.
- Die Regel aus dem Plan ist nicht erfüllt. **Schritt 2 wird nicht umgesetzt**, v1 bleibt aktiv, und es gibt keine
  Code-Änderung.
- Die schwache Wirkung der Kurven ist kein Fehler, der Prognosen verschlechtert. Sie wirkt als Glättung.
- Grenzen der Prüfung:
  - Nur Tormärkte des Basismodells.
  - Saisons mit Kalenderjahr 2026, Stand Ende Juli.
  - Keine Ecken- oder Kartenmärkte.
  - Die europäischen Ligen ab August sind nicht im lokalen Bestand. Für sie bräuchte es einen Export vom Server.
