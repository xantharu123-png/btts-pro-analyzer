# Quoten und Vorschlagsfilter – 20.09.2026

## Belegt

- VPS: API-Football Pro aktiv, 7.500 Abfragen/Tag. Quoten sind im vorhandenen Zugang enthalten; kein neues Abo angelegt.
- Ursache der leeren Anzeige: Der Parser verwarf Anbieterstände nach 45 Minuten. API-Football dokumentiert ungefähr drei Stunden zwischen Pre-Match-Aktualisierungen.
- Echter Test mit dem neuen Import, drei Spiele: 40 exakt zugeordnete Marktquoten, davon acht unter 1,20; sämtliche Stände waren älter als das Ausführungsfenster.
- Derselbe Schlüssel liefert aktive Free-Zugänge für Basketball/Eishockey (je 100 Abfragen/Tag). Deren automatische Quotenanbindung ist damit noch nicht implementiert. The-Odds-API-Schlüssel für Tennis fehlt; E-Sport hat ebenfalls keine verifizierte automatische Quotenquelle.

## Änderung

- Letzte exakte Quoten bis 24 Stunden bleiben als Beobachtung erhalten. Alter/Anbieter werden angezeigt. Keine Verlängerung des 35-/45-Minuten-Fensters für automatisch bestätigte Preise.
- Unter 1,20: kein neuer Vorschlag, auch bei einem ausdrücklich als alt bezeichneten letzten Quotenstand. Fehlende, fremde oder ungültige Quoten gelten nicht automatisch als niedrig.
- Gilt für Wettfinder/Daily3, RisikoBet, 15K und die gemeinsamen manuellen/Live-Preisoberflächen. Bestehende Wettscheine, Buchungen und Abrechnungen bleiben unverändert.
- RisikoBet verwendet exakt passende Fußballquoten aus dem gemeinsamen Bestand. Die Zuordnung bindet Anbieter-Spiel-ID, Beginn, Markt, Auswahl und Abrechnungszeitraum.
- Fußball übernimmt alle modellierten, zuordenbaren Märkte je bereits abgefragtem Spiel; keine zusätzliche Anfrage je Markt.
- `wettfinder_automation.py --quotes-only` aktualisiert begrenzt Preise ohne Modellneuberechnung. Nur bei ruhendem Hauptdienst; ein geänderter Snapshot verhindert die Veröffentlichung. Modell-/Kontextzeitstempel bleiben erhalten, neue Echtgeldfreigaben werden nicht erzeugt.
- Wiederholte Preiserklärungen gekürzt. Eine niedrige manuelle Quote lässt die Eingabe zur Korrektur erreichbar.

## Grenzen

Lokale Regression: 1.079 Tests und 58 Untertests bestanden, einschließlich Streamlit-AppTest für Wettfinder, Daily3 und Tennis sowie Grenz-/Zuordnungsprüfungen aller fünf in Umfang befindlichen Sportarten. Dies ist keine Aussage über eine vollständige Gesamtsuite oder empirische Wettqualität.

Kein Nachweis besserer Prognosequalität durch diese Änderung. Verletzungs-/Müdigkeitseffekte, Tennis-Kontextfehler und vollständige Quotenquellen anderer Sportarten sind dadurch nicht erledigt. Cricket bleibt ausgenommen.

Quelle zum Abrufrhythmus: https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide
