# Implementation Plan: Handball-Europa-Pilot

**Ziel:** Fünf nationale Herrenligen mit getrenntem 1X2-Nachweis. Grundlage:
`docs/superpowers/specs/2026-11-25-handball-europa-design.md`.

- [x] Adaptertests für exakte Ligabindung, Namenskonflikt und falsches Quotenland
  rot ausführen. `scanners/api_handball.py`: `HANDBALL_LEAGUES`, `league_games`
  und einmalige Katalogauflösung ergänzen; Deutschland-Schnittstelle erhalten.
- [x] `handball_pilot.py`: `run_europe` und Read-only-Bericht pro Liga; Dateipfade
  getrennt, Ligafehler isoliert und Preisplätze rotierend. Rot/Grün für
  gleiche Spiel-IDs in verschiedenen Ligen, Quotenbudget und Tagesgrenze auch
  nach Unterbrechung; bei globalem HTTP 429 keine weiteren Anfragen.
- [x] Historische Ergebnisse via unveränderter Prognose mit nur früheren Spielen
  gegen eine einfache Heim/Remis/Auswärts-Basis prüfen, soweit zugänglich.
  Keine Rendite ohne zeitlich passende vollständige Quoten behaupten.
- [x] Gezielte Regression, unabhängiges Review, Status und Kaufempfehlung.
  Nur Code und Doku auf Handball-Branch; VPS und Abos unverändert.
