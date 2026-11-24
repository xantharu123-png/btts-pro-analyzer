# Live-Marktvergleich und Tagesprüfung – Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Pro Spiel höchstens einen konkret begründeten Modellvorschlag aus mehreren offenen Märkten auswählen; den alten Tagesbestand getrennt von jedem neuen Replay auswerten.

**Architecture:** Ein gemeinsamer Spielstand, eine Uhr, zwei Resttorverteilungen (mit/ohne Livebeobachtungen). Dieselbe Marktdefinition für Schätzung, Anzeige und spätere Abrechnung.

**Tech Stack:** Python, Streamlit, vorhandener Scanner und SQLite; kein neuer Dienst.

**Spec:** Erweiterung des [Live-Spieltag-Entwurfs](../specs/2026-11-22-live-spieltag-design.md) gemäß Owner-Auftrag vom 22.11. („machen und dann den Tag backtesten“). Nur der Live-Fußball-Ticker; keine manuelle Marktauswahl, Kundenbilanz oder Wettscheine.

**Ergänzung 24.11., vor Test und Umsetzung festgelegt:** Die Veröffentlichung wartet mindestens 15 reguläre Spielminuten ab (vorhandenes Mindestfenster für beobachtete Raten). Bei einem aktuellen, eindeutig zugeordneten Stand muss eine offene Auswahl mindestens 55 % erreichen und sich durch die beobachteten Torchancen bzw. bestätigten Platzverweise um mindestens **5 Prozentpunkte** von der gleichen Situation ohne diese Live-Beobachtungen abheben. Die fünf Punkte sind die vorab festgelegte Mindestgröße für die Anzeige, keine trainierte Grenze oder Renditeannahme. Vergleich und automatischer Spielfokus verwenden dieselbe Reihenfolge: größter Zugewinn, dann Modellchance. Kein Alibi-Tipp und keine künstliche Verteilung auf Wettarten. Prüffälle: tatsächlicher Cardiff-Stand bei 2′, neutrale und schwache spätere Beobachtungen, eine starke Halbzeitänderung und ein Abschlussmarkt mit mehr Zugewinn trotz geringerer Modellchance. Für einen zeitlich getrennten Qualitätsnachweis nur künftige, regulär erfasste Echtbelege nach diesem Release auswerten; im Archiv fehlen die vollständigen historischen Eingaben für einen fairen Replay-Test.

## Global Constraints

Keine zusätzlichen Sportabrufe im Ticker, keine Backups; keine Preise im Modell. Für die Tagesabrechnung wurden die fehlenden Endstände und Torfolgen separat autorisiert: ein Sammelabruf, keine Spielsuche. Die 55-%-Untergrenze und bisherigen Anforderungen an Identität, Frische und Beobachtungen bleiben. Kein Tuning an den Ergebnissen des 22.11.

## Review Focus

Ein frühes 0:0 allein darf kein Signal liefern. Ein 1:0 in Überzahl kann beim Schlusspfiff unverändert bleiben. Ein 1:1 entscheidet BTTS, nicht alle übrigen Märkte. Gleichwertige Handicap- und Sieg-Ausgänge sind keine unabhängigen Belege. Fehlende Live-Stände oder Resultate sind weder Gewinn noch Verlust.

### 1. Marktkatalog und Referenz

- [x] Rote Tests: Bei identischen Resttorverteilungen entsteht kein Zusatzsignal; bei 1:1 sind beide BTTS-Seiten geschlossen; Resultat und Halbtor-Handicap stimmen für äquivalente Ausgänge überein.
- [x] In einem separaten Modul die verbleibenden Tore auf das aktuelle Ergebnis addieren. Ergebnis, doppelte Chance, Handicap (Halbtorlinien), Gesamt-/Teamtore, Torbereiche, BTTS und weitere Tore identisch für beide Verteilungen bewerten. Bei „nächstes Team“ konkurrierende Raten inklusive „kein Tor“. Keine Schätzungen für Ecken/Karten aus Toren.
- [x] Referenz je Team = dokumentierte Vorab-Torerwartung × reguläre Restminuten / 90. Live-Raten aus dem Scanner, nicht aus den 0:0-Restwerten des bereits abgeschlossenen BTTS-Markts. Auswahl nur bei positiver Änderung gegenüber derselben Situation ohne Livesignal; größter Zugewinn in Prozentpunkten, dann Modellchance, dann stabiler Schlüssel. Kein Anspruch auf Rendite.

### 2. Anzeige und Abrechnung

- [x] Tests zuerst: Frist, Datenlücke, 1:0/Überzahl, schon entschiedene Märkte, Seitenverwechslung und stabile Erstbelege. In `app._assess_live_fixture` Ergebnis optional anzeigen, mit belegtem Grund; keine fremden oder abgelaufenen Signale.
- [x] `live_tip_surface` und `live_tip_ledger`: stabiler Markt-/Seitenschlüssel inklusive Linie, Erfolg am regulären Ergebnis; „nächstes Tor“ weiter mit verifizierter Zeitlinie. Bestehende Belege nicht umklassifizieren. Je Beobachtung nur die tatsächlich gerenderte Auswahl protokollieren.
- [x] Scanner-, UI-, Ledger- und Settlementtests: 717 bestanden, 1 Skip; zusätzlich die Teilmenge unter dem Produktionspreisvertrag: 176 bestanden. Gesamtlauf mit Stopp beim ersten Fehler: 99 bestanden, dann zuvor dokumentierter Eishockeyfehler `test_native_conflicting_role_ids_fail_before_any_request`.
- [ ] Produktionsfreigabe und eigener Release-Nachweis. Kein Deployment in diesem Auftrag.

### 3. Tagesprüfung (kein Modelltraining)

- [x] Alle echten Erstbelege nach `shown_at` im Zürcher Kalendertag lesen. Je Tipp Anzeigestand, Markt, Ergebnis/Quelle dokumentieren. Gewinnquote = gewonnen / (gewonnen + verloren); offene und ungültige gesondert. Ohne Istquoten keine Rendite.
- [x] Neue Regel nur für zeitgenössische, vollständige Modellinputs abspielen. Endstände ausschließlich zum Abrechnen; Abdeckung mit Zähler/Nenner sowie nicht wiederherstellbare Felder benennen. Weder die historische UI noch einen ungespeicherten Auswahlzeitpunkt erfinden.
