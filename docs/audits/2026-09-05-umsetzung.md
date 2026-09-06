# Umsetzung des Auswahlqualitätsaudits

Auftrag: Nutzerfreigabe „alles machen“ am 05.09.2026 nach dem Audit
`2026-09-05-auswahlqualitaet.md`. Ausgangscommit: `511e1535e835c264c434db67663b769f63761232`.

## Unveränderte Produktregeln

- Preise verändern weder Wahrscheinlichkeit noch Sichtbarkeit oder Modellreihenfolge.
- Keine pauschalen Verbote einzelner Wettarten; Topauswahl ist Präsentation.
- 15K-Geld-/Ticketregeln bleiben getrennt und unverändert streng.
- Keine erfundenen Verletzungs-/Wetter-/Belastungseffekte, keine Profitabilitätsbehauptung aus Softwaretests.
- Nur der VPS schreibt produktive Daten. Lokale Tests verwenden isolierte Daten.
- Geprüfte Änderungen werden explizit committed, gepusht und revisionsgebunden deployed; fremde ungetrackte Audit-/Outputdateien bleiben unverändert.

## Arbeitspakete und Abnahme

| Paket | Umsetzung | Abnahme | Status |
| --- | --- | --- | --- |
| F1/F3/F6 | Normaler Kandidatenvertrag ohne 15K-Korridor, kontinuierliche Historie, aktueller Termin/Status | Grenzfälle, abgesagt/verschoben, strenge Ticketregeln | implementiert; Regression grün |
| F2/F11 | Vollständiger Modellpool, Topvielfalt vor Pagination, rotierende Preisabdeckung | Alternative hinter 15 gleichen Märkten bleibt; alle Preiszustände gleiche Modellreihenfolge; frischer Cache bleibt ausführbar | implementiert; Regression grün |
| F4/F5 | Reale historische Sportdaten, sportspezifische Modelle, konkrete Kontextfakten | Zeitbezug, Identität, fehlende Daten, kein erfundener Effekt | Anbindung implementiert; numerische Kontexteffekte und belastbare Modellgüte noch nicht nachgewiesen |
| F7 | Tennis Erstprognose plus aktuelle immutable Revision; Kontextrefresh nach Alter | Neue Prognose sichtbar; atomare Legacy-Erstmigration; keine künftigen Termindaten im historischen Lesen | implementiert; Regression grün |
| F8 | Evidenz-/Kontextpriorität vor Spielbeginn | Schlechter früher Kandidat verdrängt besseren späteren nicht; keine Preisdaten im Ranking | implementiert; Regression grün |
| F9/F10 | Ehrliche Unsicherheits-/Preisbegriffe; kausale Prognose-, Ergebnis- und Schlussquotenerfassung mit Auswertung | Kalibrierung/Preis-/Renditenachweis getrennt, zeitkorrekte Inputdaten | Infrastruktur implementiert; prospektiver Qualitäts-/Renditenachweis ausstehend |
| Release | Vollständige Regression, unabhängiges Review, Browser, Commit/Push/VPS | Exakter Hash, Backup, Health, Timer und echter Modelllauf | ausstehend |

Die numerische Freigabe neuer Kontextfaktoren benötigt historische oder prospektiv gesammelte, zeitgestempelte Ergebnisse. Implementierte Erfassung ist nicht bereits validierte Wirkung. Externe Zugangsdaten werden nicht erfunden oder durch einen neuen kostenpflichtigen Anbieter ersetzt.

Lokale Testumgebung: `.codex_test_venv/quality/Scripts/python.exe`, neu aus vorhandenem Python aufgebaut; Projektanforderungen plus pytest/pytest-subtests installiert. Die übernommene `.venv` wurde nicht gelöscht oder überschrieben.

## Fortsetzung und Gegenprüfung am 7. September 2026

- Ausgangsstand lokal, GitHub und VPS frisch identisch auf `511e1535e835c264c434db67663b769f63761232` geprüft. Übernommene Änderungen wurden fortgeführt, nicht verworfen.
- Der normale Fußballpool wird vor Präsentation erhalten (Ressourcenlimit 1.200 Spiele × 90 Märkte); andere Sportquellen sind auf 1.200 Modelle je Sport begrenzt. Drei Hauptkarten und 20 Zusatzkarten pro Seite sind ausschließlich Darstellung. Kein Marktname wurde gesperrt.
- Die gemeinsame historische Datenkorrektur und neue Cacheversion betreffen auch das 15K-Modell. Unverändert sind Einsatz-, Konto-, Ticket-, Authentisierungs- und Abrechnungsregeln. Alte authentisierte v11-Tickets bleiben prüfbar; neue Vorhersagen verwenden v12. Der separate strenge 15K-Pool bleibt begrenzt.
- Tennis aktualisiert bestehende zukünftige Modelle höchstens alle zwei Stunden vor beiden Verbrauchern. Erstprognose, aktuelle Revision, Statistikstichtag und Kontextbeobachtung bleiben getrennt. Fehlende frühere Metadaten werden niemals rückwirkend erfunden.
- Basketball-, Eishockey- und Cricketmodelle verwenden nur bereits beobachtete Ergebnisse mit passendem Wettbewerb/Format. Nachträglich korrigierte oder abgesagte Ergebnisse verdrängen alte Revisionen. Erstimporte werden nicht als schon vor dem Import bekannt zurückdatiert. Cricket unterstützt T20/ODI; ohne geeignete Daten bzw. für nicht unterstützte Formate wird keine Wahrscheinlichkeit erfunden.
- `runtime_state/forecast_evidence.db` speichert unveränderliche normale Prognosen, exakt zugeordnete Preisbeobachtungen und echte Resultate, getrennt von Echtgeldkonten. Der vorhandene Worker führt die begrenzte Ergebnissammlung und Schlussquotenerfassung aus. `scripts/selection_quality_report.py --db ...` liest den Bestand aus. Native Eventidentitäten verhindern Namens-/Tageskollisionen. Markt-, Modell- und Policykohorten werden nicht zu einem vermeintlichen globalen ROI vermischt.
- Erwartete Datenlücken, noch ausstehende Ergebnisse und Abrufbudgets bleiben Abdeckungshinweise. Tatsächliche Provider-, Payload- und Schreibfehler zählen als Betriebsfehler; ein fehlgeschlagener Nebenlauf löscht keine unabhängig gültige normale Prognose.
- Gerenderte lokale Prüfung verwendet isolierte synthetische Ereignisse und die tatsächlichen Renderer/CSS: Wettfinder und RisikoBet bei 1.440/390/320 Pixeln, Sportfilter, Seite 2, Detailöffnung und eigene Quote. Gefundener 320-Pixel-Überlauf des Preisdialogs korrigiert; erneute Browserabnahme im Release-Nachweis.

### Verbleibende fachliche Arbeit, nicht durch Softwaretests abkürzbar

F4 ist keine abgeschlossene numerische Kontextkalibrierung: Ausfälle, Wetter und Tennisbelastung sind konkrete Informationen, aber ihre individuellen Wahrscheinlichkeitsänderungen benötigen zeitkorrekt verfügbare Trainings- und unabhängige Testdaten. Bis dahin werden keine pauschalen Gewichte als belegte Effekte ausgegeben. F10 sammelt nun die nötige prospektive Evidenz; ein realisierbarer Vorteil gegenüber Buchmacherpreisen und Profitabilität sind weiterhin **nicht nachgewiesen**. Mehr sichtbare Prognosen sind kein Ersatz dafür.
