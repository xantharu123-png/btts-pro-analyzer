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

Der Produktionscheck fand außerdem vier Eishockey-Snapshots mit dem bereits gültigen Feld `team_sport_forecast`, das der RisikoBet-Seitenleser noch ablehnte. Der Leser übernimmt jetzt den bestehenden geschlossenen Domain-Vertrag einschließlich Ereignisbindung und Snapshot-ID-Prüfung. Ungültige Zusatzfelder oder umgebundene Events bleiben abgewiesen.

Lokale Regression: 1.085 Tests und 58 Untertests bestanden, einschließlich Streamlit-AppTest für Wettfinder, Daily3 und Tennis sowie Grenz-/Zuordnungsprüfungen aller fünf in Umfang befindlichen Sportarten. Dies ist keine Aussage über eine vollständige Gesamtsuite oder empirische Wettqualität.

VPS-Preisaktualisierung um 12:40 CEST: 99 exakt passende Quoten aus zehn Spielen, keine Abruffehler. Der anschließend geladene Wettfinder zeigte 42 Quoten mit ihrem tatsächlichen älteren Stand; keine sichtbare Auswahl hatte eine passende beobachtete Quote unter 1,20. Modell- und Kontextzeiten wurden nicht vorverlegt.

Kein Nachweis besserer Prognosequalität durch diese Änderung. Verletzungs-/Müdigkeitseffekte, Tennis-Kontextfehler und vollständige Quotenquellen anderer Sportarten sind dadurch nicht erledigt. Cricket bleibt ausgenommen.

Quelle zum Abrufrhythmus: https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide
