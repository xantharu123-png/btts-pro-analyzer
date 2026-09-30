# RisikoBet-Zeitfilter und Serienform – 30.09.2026

## Reproduktion

Vor Reparatur: lokaler/GitHub/VPS-Stand `4ecf96b`. Reine Produktionslesung
um 11:51:58 UTC: 70 gespeicherte RisikoBet-Szenarien, 60 mit bereits
erreichtem Spielbeginn. Live-Browser zeigt um 12:05 UTC noch Tsitsipas,
Gea und Djokovic als kommende Risiko-Szenarien. Kein neuer Sportscan.

Der Wettfinder zeigt bei E-Sport zahlreiche „Gegner nicht hinterlegt“-Zeilen,
obwohl die unveränderten Eingangsdaten nur geordnete S/N-Ergebnisse enthalten.

## Begrenzte Reparatur

- `riskobet_ui.py`: typisierte, zeitzonenbewusste Nur-Lese-Projektion vor
  Preisüberlagerung, Featured-Auswahl, Event-Cap und Pagination. Exakter
  Beginn wird nicht als kommende Auswahl behandelt. Bestehende gespeicherte
  Belege sowie Abrechnungen werden nicht geändert oder gelöscht.
- Kein Live-Ergebnis aus verstrichener Zeit abgeleitet. Eine Terminänderung
  braucht ihre regulär veröffentlichte neue Revision. Keine fremde aktuelle
  Terminangabe überschreibt einen alten unveränderlichen Modellbeleg.
- Filter wirkt beim Streamlit-Aufruf/Neurendern. Eine ohne Interaktion offen
  gelassene Seite bekommt keinen neuen Browser-Timer.
- `sports_form.py`: reine S/N-Eingänge behalten Plättchen und Bilanzen,
  erzeugen aber keine leeren Gegnerlisten. Ein kurzer Abdeckungshinweis.
  Gemischte Daten behalten alle tatsächlich vorhandenen Details, ohne
  unbekannte Gegner zu erfinden. Vollständige Fußball-/Tennislisten erhalten.

## Softwareprüfung

548 gezielte Integrationstests bestanden (RisikoBet-Domain/UI/Surface/Store/
Settlement, Sports-Editorial, Compact-Analyse, Wettfinder-Karten und Logos).
Unabhängiger Review ohne Befund; 150 eigene Gegenprüfungstests bestanden.
Weitere 221 Daily3-/Workflow-/Marktscope-/Quotenuntergrenzen-Tests bestanden:
insgesamt 769 unterschiedliche gezielte Tests. `git diff --check` sauber.
Vollsuite: 11.878 gesammelt, für das ausdrücklich begrenzte 30-Minuten-Fenster
bei 22 % durch uns beendet. Kein abschließendes Resultat; deshalb ausdrücklich
kein neuer Vollsuite-PASS. Ein zuerst versuchter Zusatzbefehl enthielt den nicht
vorhandenen Namen `tests/test_daily3.py`; mit realen Dateinamen wiederholt und
221 bestanden. Kein Programmfehler aus diesem Testbefehl abgeleitet.

Kein Backup, Cleanup, API-/Sport-/Modellscan oder Quotenabruf gestartet.
## Produktionsnachweis

Code `c9de1e96ddfaf1f8809eb20f72dab29a9f9f5f38` auf GitHub main und VPS.
Kontrollierter Fast-forward mit Deployment-Lock und inaktiven Modellschreibern;
App neu gestartet, ohne Sicherungs-/Migrations-/Bereinigungsweg.

- Reiner VPS-Leser: 70 ursprüngliche Kandidaten, 7 kommende, 63 ausgeblendet.
  Vitality/LOUD war während der Arbeit gestartet und verschwand ebenfalls
  ohne Sportscan. Die echten kommenden Karten umfassen sechs Events.
- Eigener Playwright-Browser: Tsitsipas, Gea, Djokovic und Vitality/LOUD im
  kommenden RisikoBet-Katalog nicht mehr vorhanden; 7 sichtbare Karten.
- Echte Spirit/1win-Wettfinder-Karte: keine leeren Gegnerzeilen, originale
  Bilanzen 5S/0N und 2S/3N. 10-Spiel-Toggle zeigt 20 echte S/N-Plättchen für
  beide Teams, Rückwechsel auf fünf wieder zehn Plättchen. Keine Ergebnisse
  oder Gegner hinzugefügt.
- 1440, 390 und 320 Pixel: Dokumentbreite jeweils exakt Viewportbreite.
  Desktop-/Mobilbilder visuell geprüft. Nach frischem Seitenaufruf keine
  Console-Fehler; zehn bekannte Streamlit-Iframe/Feature-Policy-Warnungen.
  Beim bewusst ausgeführten App-Neustart vorher kurzzeitige 502/Disconnect-
  Meldungen im alten offenen Browser, nach Reload nicht mehr vorhanden.
- App/Caddy aktiv, sieben Timer geplant; interner und öffentlicher Healthcheck
  `ok`. Keine Timer geändert.
- Wettfinder-Datei SHA-256 unverändert:
  `916beed520687a5304ef573fb2b8ac9a4fa624979cdebf0752816ff567bb8fdd`.
  RisikoBet-Datei SHA-256 unverändert:
  `bfba0310d9a1199abbac089f762830f97c97d1574cde9f252de51e3c0b347e18`.

Lokale Browserbelege unter `output/playwright/continue30-*` bleiben absichtlich
unversioniert. Abschließender Nachweiscommit enthält nur diese Dokumentation
und Übergabe, anschließend eigener codefreier Pull ohne App-Neustart.

## Unveränderte fachliche Grenzen

Die Änderung repariert Anzeigen, nicht sportliche Modellwirkungen.
Empirisch belegte Verletzungs-/Wetter-/Müdigkeitseffekte und bessere
Wettqualität bleiben getrennte offene Aufgaben.
