# Handball im Wettfinder – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Die fünf Handballligen im automatischen Wettfinder sichtbar machen,
sobald aktuelle spielgenaue 1X2-Daten und Modellwerte vorliegen.

**Architecture:** Der bestehende Pilot erstellt einen schlanken öffentlichen
Anzeigebeleg je geeigneter Partie; der UI-Pfad liest ihn abruffrei und hält ihn
von TOP, Archiv und Scheinlogik getrennt. **Tech Stack:** Python, pytest,
Streamlit; keine neue Abhängigkeit.
**Spec:** [Handball im automatischen Wettfinder](../specs/2026-11-25-handball-wettfinder-design.md).

## Prüfpunkte

- [ ] Rot/grün: echtes Quoteformat aus allen fünf Ligen und aktuelle Modelle
  erzeugen Anzeigebelege; fehlende, alte oder widersprüchliche Quote, gestartetes
  Spiel, Gleichstand oder Median <1,20 erzeugt keine Karte. Gültige Modelle
  bleiben unverändert. V1/V2, Ausfall oder defekte Liga-Datei bleiben abruffrei.
- [ ] Rot/grün: Handballfilter, passende Spielkarte, 1X2, gleiche Sortierung,
  kein Rapport-/Aktionspfad. Manuelle Sportauswahl bleibt unverändert.
- [ ] Gezielt Regressionen und GitHub-CI prüfen, exakt via PR in main
  integrieren, Netz-isolierten VPS-Smoke und Healthchecks ausführen.
  Kein Vollscan, keine Kopie, kein Backup; regulären ersten Datenstand offen
  ausweisen, wenn er vor dem Abschluss noch nicht vorliegt.
