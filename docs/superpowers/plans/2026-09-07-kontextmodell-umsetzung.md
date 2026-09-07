# BetBoy Kontextmodell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verletzungen, Besetzung und Belastung in fünf Sportarten mit messbarer, zeitkorrekter Modellwirkung berücksichtigen und ATP/WTA unabhängig aktualisieren.

**Architecture:** Vier Teilpläne liefern getrennt testbare Änderungen. Ein gemeinsamer append-only SQLite-Speicher hält typisierte Modellartefakte, Kontextbeobachtungen und Rechenrevisionen; atomare Manifeste veröffentlichen konkrete Versionen. Sportadapter erweitern bestehende Basisverteilungen; Aktivierung erfolgt erst nach dem vorab festgelegten Vergleich gegen die Basis.

**Tech Stack:** Bestehendes Python, SQLite, NumPy, SciPy, pandas, pytest und Streamlit; bestehende Provider, Runtime-Pfade, VPS-Worker und Deploymentwerkzeuge. Keine neue Laufzeitabhängigkeit.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), schriftlich freigegeben am 7. September 2026.

## Global Constraints

- Keine Quote, Buchmacheridentität, Mindestquote oder Preisfreigabe als Modell- oder Rankingmerkmal.
- Kein pauschales Wettartenverbot. Ein nicht aktivierbarer Kontextteil entfernt keine berechenbare Basisprognose.
- Cricket-Code, Konfiguration, Zugangsdaten und bestehendes Verhalten bleiben unverändert.
- Keine neue Echtgeldfunktion; 15K-Konto-, Einsatz-, Ticket- und Abrechnungsregeln bleiben unverändert.
- Alte Prognosen, authentisierte Tickets und Abrechnungen werden nicht umgeschrieben.
- Keine kostenpflichtige Quelle, neuer Vertrag oder Tarifwechsel ohne gesonderte Zustimmung.
- Nur der VPS schreibt produktive Daten; lokale Tests/Forschung verwenden isolierte Dateien.
- Mindestens 200 eindeutige Testevents über mindestens drei aufeinanderfolgende Zeitblöcke.
- Mindestens 2 % relative Verbesserung des innerhalb eines Events gemittelten primären Brier-Verlusts; Newey-West/HAC und Benjamini-Hochberg, FDR 5 %, über alle untersuchten Familien.
- Mittlerer Verteilungs-Logloss darf nicht steigen; bestehende marktspezifische Kalibrierungsprüfungen bleiben erforderlich.
- Frische Daten, funktionierende Software, empirische Freigabe, Push und VPS-Aktivierung sind unterschiedliche Nachweise.

## Ausgangspunkt und Arbeitsverzeichnis

Git-Root: `C:/Projekt/BetBoy/betboy-app`, Branch `main`, vertrauenswürdiger Remote `https://github.com/xantharu123-png/btts-pro-analyzer.git`. Funktionsstand vor dieser Erweiterung: `b3afc478a07fa0d67509e2bef0a9c05766bdb077`; Spezifikationscommit: `f2d7411e8e1d78179c053910ff30d865ef9fc37d`.

Die bisherigen ungetrackten Audit-/Browserdateien und `output/` gehören nicht in diese Commits. Kein `git add .`, Reset, Clean oder Zurücksetzen fremder Arbeit. Vor jeder Änderung aktuellen Status und betreffende Dateien lesen. Die alten Rohdaten-/Ergebnis-/Auswahlkorrekturen nicht erneut implementieren.

Testbefehle beziehen sich auf den Git-Root. Python: `.codex_test_venv/quality/Scripts/python.exe`; jeder pytest-Lauf erhält ein neues `--basetemp=.pytest_tmp/<paket>-<lauf>` und `-p no:cacheprovider`. Windows-Skips nicht als Linux-Nachweis zählen. Auf dem VPS kein pytest in die App-venv installieren.

## Teilpläne und Reihenfolge

| Reihenfolge | Teilplan | Eigenständig prüfbares Ergebnis |
| --- | --- | --- |
| A1–A4 | [Modellablage und ATP/WTA](2026-09-07-kontext-a-modelle-tennisrefresh.md) | Unabhängiger Tour-Refresh, echte getrennte Frische, wiederherstellbare Artefakte |
| B1–B7 | [Kontextkern, Fußballausfälle, Tennisbelastung](2026-09-07-kontext-b-verletzungen-belastung.md) | Beobachtungen, geschätzte Effekte, kohärente Vergleichsprognosen; noch keine unbelegte Aktivierung |
| C1–C4 | [Wetter und weitere Sportarten](2026-09-07-kontext-c-weitere-sportarten.md) | Quellenbelegte, sportartspezifische Erweiterungen ohne Cricket |
| D1–D5 | [Abnahme, Oberfläche und Release](2026-09-07-kontext-d-validierung-release.md) | Nachvollziehbare empirische Entscheidung, gemeinsame Karten, Backup und belegter Betrieb |

A ist unabhängig von neuen Kontexttrainingsdaten und kann separat veröffentlicht werden. B hat Vorrang vor C. Die begrenzten Quellenproben aus C dürfen früh laufen; sie rechtfertigen keinen Wechsel zu kostenpflichtigen Quellen. D1/D2 werden für die erste fertig trainierbare B-Familie ausgeführt, bevor auf C-Daten gewartet wird. D3–D5 können mehrere explizit benannte Teilreleases abschließen; eine fehlende Sportart bleibt dabei offen.

Jeder Teilplan erbt alle Global Constraints dieses Plans und liest die gesamte Spezifikation. Seine Aufgaben sind die Review-/Commitgrenzen. Unter den Aufgaben stehen kleine RED-/GREEN-Schritte; größere Implementierungsblöcke werden in den genannten Funktionen nacheinander durchgeführt, nicht als ein unkontrollierter Gesamtpatch.

## Gemeinsame Datei- und Datenverantwortung

- `model_artifacts.py`: kanonische JSON-Artefakte, Hashprüfung, append-only Manifeste und atomare aktive Referenz; **keine** Sportberechnung.
- `runtime_paths.py`: neuer `CONTEXT_MODEL_DB_PATH = RUNTIME_STATE_DIR / "context_models.db"`.
- `context_observations.py`, `context_snapshots.py`: Beobachtungen und unveränderliche Eventrechnungen in derselben Datenbank; keine Preis- oder Kontodaten.
- `context_models/`: Merkmalsverträge, Offset-Schätzung, sportartspezifische Anpassung und Validierung; neue Koeffizienten als JSON, nicht als ausführbare Pickles.
- `tennis/state_codec.py`, `tennis/tour_state.py`: explizite Tour-Serialisierung und unabhängige Builds/Publikation. Legacy-Pickles bleiben nur im bestehenden vertrauensgeprüften Lesepfad.
- `context_sources/`: begrenzte Abrufe und Normalisierung; keine geschätzte Wirkung im Provideradapter.
- `scripts/train_context_models.py`, `scripts/evaluate_context_models.py`: isolierte, reproduzierbare Trainings-/Abnahmeläufe.
- Bestehende Worker und Tabs: konsumieren gemeinsame Rechenrevision; Quotenverarbeitung bleibt anschließend separat.
- `docs/audits/2026-09-07-kontext-daten.md`, `docs/audits/2026-09-07-kontext-abnahme.md`: reale Daten- und Ergebnisnachweise, ausdrücklich nicht mit synthetischen Testergebnissen verwechseln.

Alle neuen Artefakte liegen als typisierte JSON-Nutzlasten in `context_models.db`. Das erfüllt getrennte Modellidentitäten und atomare Veröffentlichung, ohne ein zweites dateibasiertes Backupformat einzuführen. Die Backup-Aufgabe prüft dennoch ausdrücklich Entdeckung, Konsistenz, Wiederherstellung und Rollback; „SQLite wird schon gefunden“ ist kein Abnahmenachweis.

## Fortschrittsvertrag

Pro Paket werden genau diese vier Angaben aktualisiert: **Software**, **verwendbare Daten**, **empirischer Status**, **produktive Aktivierung**. `Tests grün` genügt nur für Software. Ein Quellenfehler blockiert die betroffenen Merkmale, nicht die unabhängigen Pakete. Experimentelle Ergebnisse bleiben intern; die Basis bleibt sichtbar.

Aktueller Stand bei Planerstellung: Spezifikation freigegeben, alle nachfolgenden Implementierungsaufgaben offen. Keine neue Verletzungs-/Belastungswirkung implementiert, trainiert oder aktiviert.

## Selbstprüfung gegen die Spezifikation

| Spezifikationsabschnitt | Umsetzung |
| --- | --- |
| 1–3: Produktziel, Grenzen | Alle Global Constraints; B5/B7, D3/D5; Cricket-Vergleich C2/D5 |
| 4: Herkunft, Status, Revisionen | A1, B1/B2/B3, D3 |
| 5: Schätzung, Referenz, Kohärenz | B2/B4/B5/B6/B7, C1–C4, D1/D2 |
| 6.1: Ausfälle, Ersatz, Unsicherheit | B4/B5; D1-Kohorten/Ablationen |
| 6.2: Tennisbelastung und Erholung | B6/B7; A2–A4 |
| 6.3–6.4: Basketball, Hockey, E-Sport | C2/C3/C4 |
| 7: Echte Beschaffung, Zeit-/Lizenzgrenzen | B1/B4/B6, C1–C4, D1 |
| 8: Unabhängiger Tour-Refresh | A1–A4, D4/D5 |
| 9: Unangetasteter Test und Aktivierung | D1/D2; B2/B3 verhindern verfrühte Anwendung |
| 10: Flache UI, Scheduler, Backup | A4, B3, D3/D4/D5 |
| 11: Regression und Nachweise | Sämtliche RED-/GREEN-Aufgaben, abschließend D5 |
| 12–13: Reihenfolge, Freigabe, ehrlicher Abschluss | Dieser Index, Teilreleasevertrag, Übergabe |

Die Quellenabdeckung und ausreichende zeitstrenge Testevents sind bewusst **zu prüfende Ergebnisse**, keine vorab behaupteten Tatsachen. Für unerreichbare Daten wird das betroffene Paket mit konkretem Quellenbefund offen ausgewiesen; eine reine Adapterhülle darf es nicht auf abgeschlossen setzen.
