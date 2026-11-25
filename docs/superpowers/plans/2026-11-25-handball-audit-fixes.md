# Handball Audit-Reparatur – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Spiel- und Marktbelege korrekt binden, einen fairen Marktvergleich
ermöglichen und Form/Remis getrennt messen, ohne die Produktion ungeprüft
umzustellen.

**Architecture:** Scanner und bestehender Tagesjob führen eine verbindliche
Empfangsuhr und separate Identitätsrevisionen. Unabhängige Auswertung benutzt
nur belastbare Vorabbelege; eine Offline-Studie benutzt nur Ligaspielstände.
**Tech Stack:** Python, NumPy, pytest; bestehende API-SPORTS-Anbindung.
**Spec:** [Audit-Reparatur](../specs/2026-11-25-handball-audit-fixes-design.md).

## Schritte

- [x] Rot/grün: Update zwischen Anfrage und Empfang wird akzeptiert; Quote
  nach Anwurf, künftig oder am Empfang abgelaufen wird nicht gespeichert.
  Verlegung mit gleicher ID bekommt neue Zeit/Prognose; die alte behält ihre
  Originalauswahl und Originalquote. Übergang V1–V3 ohne Mutationslauf.
- [x] Rot/grün: gepaarter Brier und Log Loss für belegten Vorabmarkt; spätere,
  fehlende, ungültige und alte Belege getrennt; kein Preisfeld als Modellinput.
- [x] Rot/grün: rollende Gewichte nach tatsächlichen Daten und separat aus der
  Kalibrierperiode erlernte Remis-Anpassung; chronologische Validierung ohne
  Quotes und ohne Daten aus dem Testfenster. Nur vorhandene Endstände lesen,
  Nachweisstatus getrennt von Softwaretests ausweisen.
- [ ] Gezielte Tests beider Preisregeln und CI; Prüfreport, gepinnter
  VPS-Deploy und Healthchecks, ohne Backup oder zusätzliche Scans.
