# Fußball-Liveticker Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Öffnet ein berechtigter Zuschauer Fußball-Live, sieht er laufende Spiele und den dazugehörigen frischen Tipp ohne Scannen.

**Architecture:** Ein pro Streamlit-Prozess gemeinsamer Feed wird ausschließlich aus aktiven Live-Sitzungen angestoßen. Zwei getrennte Uhren steuern Spielsuche und Gruppenabrufe; der vorhandene Rechner bekommt validierte Daten, aber keinen eigenen Netzzugang. Der Klick auf Spiel oder Markt filtert den gemeinsamen Stand lokal.

**Tech Stack:** Python, Streamlit-Fragmente, API-Football über den vorhandenen Budget-Governor, pytest. Keine neuen Dependencies oder Dienste.

**Spec:** [Spieltag und Fußball-Liveansicht](../specs/2026-11-22-live-spieltag-design.md). Liga-Cache und Vorab-Anstoßgrenze sind schon in PR 154; hier nicht erneut implementieren.

## Global Constraints

- Entdeckung alle 300 s, maximal 20 IDs je Detailgruppe alle 60 s, höchstens 120 s alte Daten für Tipps. Kein Zuschauer: keine neuen Abrufe. Keine nachgeholten Takte, Preisabfragen, Backups oder unkontrollierten Einzelabrufe.
- Hintergrundreserve (Standard 2.500) wahren. Zusätzlich zunächst höchstens **500** Feed-Anfragen pro Anbieter-Tag (Vorschlag: am untersuchten Samstag blieben 3.011, davon 2.500 Reserve). Das ist eine Begrenzung, kein Verbrauchsziel. Sobald Budget oder Rate nicht reichen, kein Tipp aus alten Daten. Bereits laufende reguläre Jobs dürfen nicht verdrängt werden.
- Keine Modell- oder Marktregel ändern. Erfolgsbelege nur für tatsächlich gezeigte und zum Zeitpunkt der Anzeige aktuelle Tipps. Weltweite manuelle Rotsuche separat erhalten.

## Review Focus

1. Zwei offene Tabs oder ein Marktwechsel dürfen keine doppelten Abrufe auslösen.
2. Fehler oder eine fehlende Partie in der Gruppenantwort sind keine Nulltore und keine Bestätigung alter Tipps.
3. Ein Tor, eine VAR-Korrektur, eine rote Karte oder Spielende macht einen älteren Tipp sofort unbrauchbar.
4. Bei knappem Budget, Neustart oder geschlossenem Tab darf kein versteckter Abruf entstehen.
5. Wechselnde Sortierung darf einen Tipp weder dem falschen Spiel zuordnen noch mehrfach als sichtbar erfassen.

### Task 1: Gemeinsamer Takt und Budget

Dateien: `live_football_feed.py`, `api_budget.py` (falls für eine atomare Feed-Grenze nötig), `tests/test_live_football_feed.py`.

- [ ] Rote Tests mit injizierter Uhr und Transport: kein Aufruf vor erstem Tick; 0/1/20/21/80 Spiele, parallele Zuschauer, Pause über zwölf Minuten ohne Nachholen, Tagesgrenze und Fehler-Backoff.
- [ ] `LiveFootballFeed.tick(...)` stößt nur fällige Arbeit an; kein eigener regelmäßig laufender Thread. Je Konto/Anbieter eine gemeinsame Instanz, keine Geheimnisse in Ausgaben. Ein einzelner aktiver Abruf darf nach Verlassen des Tabs enden.
- [ ] Gruppenergebnisse getrennt je Spiel halten, alte Tipps bei Fehler/Änderung verwerfen. Bereitschaft zu weiteren Abrufen unmittelbar vor jedem Request mit der vorhandenen Reserve und Feed-Grenze prüfen. Prüfen mit `pytest tests/test_live_football_feed.py tests/test_api_budget.py -q`; committen.

### Task 2: Spielstand und Modell aus derselben Antwort

Dateien: `live_football_source.py`, `api_football.py`, `scanners/ultra_live_scanner_v3.py`, bestehender Rotkartenpfad, `tests/test_live_football_source.py`.

- [ ] Rote Tests: vertauschte/falsche Team- oder Spiel-ID, fehlende Statistik, widersprüchliche Tor-/Kartenereignisse, 90+ und Spielende. Keine Einzelabfragen bei fehlenden Pflichtdaten; ohne belegte Vorabgrundlage keine Behauptung strenger Modellqualität.
- [ ] `discover()` liest die gemeinsame Liste, `details(ids)` liefert nur exakt passende Gruppendaten. Bestehende Statistik- und Marktberechnung mit einem offline begrenzten Adapter wiederverwenden. Vorabwerte nur exakt passend zu Spiel, Seiten und Modellversion wiederverwenden. Ohne belastbare Details bleibt der belegte Spielstand sichtbar.
- [ ] Gegenprobe: alte und neue Rechnung bei identischen vollständigen Quellen gleich; Statuswechsel/VAR entwertet die vorige Rechnung. `pytest tests/test_live_football_source.py tests/test_live_tip_surface.py -q`; committen.

### Task 3: Anzeige und Freigabe

Dateien: `app.py:render_live`, `live_football_board.py`, `tests/test_live_football_board.py`, `STATUS.md`.

- [ ] Rote Oberflächentests: geschlossener Tab / keine Berechtigung → null Abrufe; Neuordnung → dieselbe Fixture-ID ausgewählt; leerer oder veralteter Stand → kein Tipp und kein Beleg.
- [ ] Fragment nur im aktiven, berechtigten Live-Bereich. Spielstände links, Tipp zum gewählten Spiel rechts, mobil untereinander. Keine ganze Seite neu laden, marktübergreifend denselben Feed lesen. Erneute Rechteprüfung bei längerer Sitzung; sichtbare Treffer über den bestehenden Belegpfad erfassen.
- [ ] Lokal mit zwei Tabs, simuliertem Tor/Spielende und auf Handybreite prüfen. PR-CI, hashgebundener Release ohne Backup oder Sonderlauf. Erst ein gültiger nativer Gruppenstand mit passender Zeit und Datenbasis darf im regulären Zuschauerbetrieb einen echten Tipp erzeugen. Betriebsnachweis getrennt von Softwaretests dokumentieren.
