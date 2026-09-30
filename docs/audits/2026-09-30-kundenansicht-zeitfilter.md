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
`git diff --check` sauber. Zusätzlicher Vollsuite-Lauf ist noch offen.

Kein Backup, Cleanup, API-/Sport-/Modellscan oder Quotenabruf gestartet.
Produktionsnachweis wird nach Veröffentlichung ergänzt.

## Unveränderte fachliche Grenzen

Die Änderung repariert Anzeigen, nicht sportliche Modellwirkungen.
Empirisch belegte Verletzungs-/Wetter-/Müdigkeitseffekte und bessere
Wettqualität bleiben getrennte offene Aufgaben.
