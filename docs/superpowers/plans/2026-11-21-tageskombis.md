# Tageskombis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Höchstens vier nachprüfbare Tageskombis bereitstellen, jede mit einem auf späteren Spielen geprüften Modellwert für den ganzen Schein.

**Architecture:** Eine reine Auswahlfunktion verarbeitet den bereits geprüften Tagesbestand der regulären Veröffentlichungen. Ein getrenntes kleines Belegarchiv friert die vier Größen vor Anpfiff ein. Die rechte Leiste liest ausschließlich freigegebene Originalscheine und löst weder Modell- noch Preisabrufe aus.

**Tech Stack:** Vorhandenes Python 3.12, SQLite und Streamlit; keine neuen externen Dienste.

**Spec:** [Tageskombis](../specs/2026-11-21-tageskombis.md). [Historische Machbarkeitsprüfung](../../audits/2026-11-21-tageskombis-datenlage.md).

## Global Constraints

- Originalmärkte und Ergebnisse zeitgerecht und exakt binden. Ein Buch pro Schein, jeder Preis ≥1,20, Abruf höchstens 35 Minuten, Anbieteruhr höchstens 45 Minuten. Preise nicht in Modellchance oder Sortierung. Keine neue Tarif-, Einsatz- oder Preisregel für den bestehenden Wettfinder.
- 3/4/5/6; maximal ein Markt desselben Spiels auf einem Schein, kein Teilnehmer zweimal. Maximal ein gemeinsames Ereignis je Scheinpaar und maximal zwei Verwendungen insgesamt, bei Wiederholung identische Auswahl. Bereits festgeschriebene Scheine nie ersetzen.
- Keine Geschäftsgeheimnisse, Preislisten-Kopien, zusätzlichen Anbieterabrufe, Backups, Timer, Echtgeldbuchungen oder erfundene Scheinwahrscheinlichkeiten.

## Review Focus

1. Gleicher Buchmachername ist bei zwei Datenquellen noch keine bestätigte Identität.
2. Eine Messung beim Abruf ist kein tatsächlicher Preiszeitstempel des Anbieters.
3. Parallele oder abgebrochene Veröffentlichungen dürfen weder Scheinrevisionen noch zusätzliche Überschneidungen erzeugen.
4. Ohne gemeinsame frühere Entscheidungsuhr ist eine nachträgliche Kombination nicht als gespielter Schein verwertbar.
5. Ein gewonnener Einzelmarkt, ein höherer Angebotspreis und eine Annul­lierung sind jeweils kein Beweis für einen gewonnenen Originalschein.

### 1. Quellenadapter und deterministische Tagesauswahl

- [ ] Zuerst rote Tests in `tests/test_daily_accumulators.py`: 1,19/1,20; falsches Team, falsche Linie, veraltete/futuristische Uhr, gleich klingende Bücher verschiedener Quellen, identische Teilnehmer unter Alias. Unabhängig vom sichtbaren Filter und dessen 20er-Seite.
- [ ] `daily_accumulators.py`: `eligible_combo_legs(signals, *, as_of, target_day)` auf Basis von `quote_matches_candidate`, exaktem `QuotePoint` und normaler Modellqualifikation. `select_combo_set(legs, *, frozen, policy)`: Kandidaten nach sportlichem Rang ordnen; deterministische begrenzte Suche, getestete Grenzen für Laufzeit und Speicher. Referenz: höchste zulässige Einzelchancen. Preise nur Eignungsbedingung; keine spätere Preisjagd.
- [ ] Reproduzierbarkeit, kein erzwungener Sechser, keine Widersprüche, Überschneidungsgrenzen, stabiles Ergebnis bei vertauschten Eingaben und Aktualisierungen; Tests unter beiden bestehenden Preisverträgen.

### 2. Prospektive Messung im regulären Betrieb

- [ ] In `tests/test_daily_accumulator_receipts.py` roten Test für zweimalige, parallele und teilweise Veröffentlichung schreiben. Originalentscheidung und Endergebnis dürfen nicht überschrieben werden.
- [ ] Eigener kleiner `daily_accumulator_receipts.py`-Speicher: transaktionale, idempotente Tagesbelege für getrennte Referenz-/Modellvarianten, eindeutige Größe/Tag/Version, kein Finanzkonto. Beim regulären heutigen Publikations-/Quotenschritt in `wettfinder_automation.py` einhängen, nachgelagert und fehlerisoliert. Keine DB-Kopie, kein Zusatzjob. Ohne Daten Grund und Auslassung knapp protokollieren.
- [ ] Jede Auswahl über exakte Forecast-ID und Kausalität prüfen. Ergebnisse `WIN/LOSS/VOID/OPEN/UNMATCHED` getrennt halten; eine offene oder unbelegte Auswahl niemals als gewonnen zählen. Zeitliche Verschiebungen / Stornos mit vorhandenen Regelwerken prüfen.

### 3. Ticketmodell und Freigabe je Größe

- [ ] `scripts/daily_accumulator_review.py` + Tests: vorab definierte Vergleichsregel, chronologische Trainings-/Testtage, gemeinsame Entscheidungsuhren, keine Nutzer-Klickauswahl. Für den tatsächlichen Schein identische IDs und höchstens vor diesem Zeitpunkt bekannte Eingaben. Register nach Policyversion, Scheingröße und zulässigem Sport-/Quellenumfang.
- [ ] Einfaches Kandidatenmodell gegen Unabhängigkeitsreferenz: Produkt der kalibrierten Einzelchancen nur Ausgangswert; gemeinsame historische Modellfehler bei ähnlichen Märkten prüfen. Zuerst endgültige Modellform und Abnahmekriterien festschreiben, dann Testdaten öffnen. Trefferkalibrierung plus Brier-Differenz auf gemeinsamen späteren vollen Spieltagen einschließlich Unsicherheitsintervall; Coverage, Gleichstand, Verluste und ausgelassene Tage ebenfalls berichten. Fehlen brauchbare Daten oder ist die Variante schlechter/nicht ausreichend belegt, keine Freigabe und kein nachträgliches Schwellentuning.
- [ ] Pro Größe gültiges versioniertes Freigabeartefakt prüfen; bei fehlendem, abgelaufenem oder falsch gebundenem Artefakt keine öffentliche Prozentzahl und kein Kundenschein dieser Größe. Keine 15K-Heuristik als Ersatz.

### 4. Kundenanzeige, Tests und Veröffentlichung

Vorab-Messvertrag für Aufgabe 3: Für den Vergleich der Wahrscheinlichkeiten müssen Kandidat und Unabhängigkeitsreferenz **denselben** Originalschein bewerten. Den Nutzen einer anderen Scheinauswahl separat auf denselben Tagespools bewerten, einschließlich ausgelassener Tage; keine Brier-Differenzen zwischen verschiedenen Zielereignissen. Als vorab zu genehmigende, konservative Erstschwelle je Größe und freizugebendem Sportumfang: zumindest 100 spätere, unabhängig vom Training ausgewählte Originalscheine an verschiedenen Spieltagen; obere Grenze eines 95-%-Intervalls der gepaarten Brier-Differenz (Kandidat minus Referenz) unter 0 und 95-%-Intervall der mittleren Differenz prognostiziert minus beobachtet innerhalb ±10 Prozentpunkten. Kalenderwochen als Resampling-Blöcke, gleiche Indexzüge für Kandidat/Referenz, mindestens 20 Wochen und Korrektur für parallel geprüfte Freigaben. Das ist keine behauptete heutige Modellleistung; Regeln vor Öffnung registrieren, nicht an den späteren Test anpassen.

- [ ] Erst roter UI-Integrationstest: bestehende Doublebet-/Tennisbox unverändert, keine unberechtigte Anzeige, kurze leere Ansicht, echte Modellchance als Prozent und zugänglicher Balken (0–100) für 3er bis Jackpot 6er; Reihenfolge nach Beginn; keine Wetteingabe. Nur echte Freigaben und weiterhin passende frische Preise. Als isolierte UI-Funktion in `daily_accumulator_ui.py`, Aufruf aus `app.py::_render_editorial_rail`.
- [ ] Projekttests einschließlich Preisverträge, gezielter Replay, UI auf Desktop/Mobil und CI. Code-Fast-forward auf VPS nach bestandenem Release-Check ohne neue Sicherung, keinen Sportscan starten. SHA, Dienste, Fenster bis zur nächsten normalen Veröffentlichung, beide Healthchecks und sichtbare/verweigerte Größen auf echtem Datenstand nachprüfen. Ein rein technischer Probeaufbau ist kein Beleg für den Jackpot-Start.
