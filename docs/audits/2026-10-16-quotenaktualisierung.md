# Quotenaktualisierung und öffentliche 1,20-Untergrenze – 16.10.2026

## Auftrag und Grenze

Begrenzte Reparatur, Tests, Commit, Push auf main und VPS-Deploy ohne neues
Backup. Keine Schlüsselrotation, neue Datenbank, Kontexteffektfreigabe,
Bereinigung, Geldbewegung oder zusätzliche Sport-/Modellsuche.

## Ursache und konkrete Datenprobe

Der tägliche Modelllauf allein aktualisierte die Tagespreise nicht. Fehlende
Quoten blieben öffentlich zulässig, und geöffnete Suchsitzungen konnten alte
Preise weiterverwenden. Zudem war eine geparste, aber nachträglich wegen
unpassender Spielbindung verworfene Quote teilweise als OBSERVED diagnostiziert.

API-Football lieferte bei der gezielten vorhandenen Abfrage für Fixture1565271
Dinamo–Botosani, HOME_OVER_0_5 drei exakt passende Angebote1,11/1,07/1,07.
Die gemeinsame Gesamtspiel-Über0,5-Quote1,02 ist ein anderer Markt. Die vom Nutzer
genannten1,01 sind nicht unabhängig bestätigt. Die damalige Morgenantwort fehlt;
keine genaue historische Ursache nachträglich erfinden.

## Reparatur

- Positive öffentliche Zulassung nur mit nativer exakter Spiel-/Start-/Markt-/
  Seiten-/Teilnehmerbindung, Anbieteridentität und originalen Preisuhren.
- Reale höchste zulässige Quote>=1,20; bestehende24h-Anzeigealtergrenze erhalten.
  Einzelanbieter zählt, aber fremde/ungültige/abgelaufene Angebote nicht.
- Modellrichtung zuerst. Preis darf nur entfernen, nicht Gegenseite wählen,
  Wahrscheinlichkeit ändern oder über der Untergrenze Rangfolge beeinflussen.
- Gemeinsame Zulassung in automatischer/manueller Suche, Tennis, Daily3, 15K,
  RisikoBet und öffentlichen Karten. Unbepreiste Liveanalyse ohne Tippaktion.
- Neuester exakt gebundener Preis ersetzt alte Sitzungspreise auch bei anderem
  Modellstand; Gleichzeitkonflikte bleiben verborgen, bis ein neuer Beleg folgt.
- Neuer reiner Preisjob alle3h: gespeicherter Bestand, vorhandene Governor/Caches,
  Laufzeitgrenzen, tägliche Veröffentlichungssperre und CAS vor atomarem Schreiben.
- Kandidatendiagnose mit sicheren skalaren Gründen statt Rohantwort/Secret-URLs.
  Zeitbindungsfehler wird IDENTITY_MISMATCH, nicht OBSERVED.
- Historische tatsächliche Verträge nicht umschreiben: Lesen, Wiederholen und
  Abrechnen bleiben möglich; nur neue niedrige Wetten werden abgewiesen.

## Prüfung und Veröffentlichung

Unabhängiges Review ohne verbleibenden Befund. Red/Green für native Parser,
Diagnose, Veröffentlichung, neuere niedrige Sitzungsquoten und Gleichzeitkonflikte
vorhanden. Test-IDs bleiben erhalten; Layout-/Auswahltests bekommen explizite
native Preisbelege, statt eine fehlende Quote weiterhin öffentlich zu erwarten.

Finaler betroffener Offline-Testlauf beendet:2.493 bestanden/7 bestehende Skips/
32 bestandene Untertests, Exit0 in124,08s. Vollständige Testcollection14.462,
alle14.350 bisherigen IDs erhalten.786 Quellhashes unverändert. Belege:
`output/quote-refresh-20261016/release-candidate-03.xml` außerhalb des Repos,
Collection unter`qa-02/`; die vorbereiteten Vollsuite-Shards wurden nicht gestartet.
Komplette14K-Vollsuite für diesen Patch nicht erneut ausgeführt.
Echter Produktionsnachweis steht noch aus. Vorherige Fehlreceipts bleiben
erhalten und sind keine bestandene Vollsuite.
VPS vor Veröffentlichung aaafba5; neue Arbeitsbasis cc06421 enthält nur die
zusätzliche Dokumentation zur zurückgestellten Schlüsselrotation.

Die Deploymentprüfung verlangt Fast-Forward, saubere versionierte Serverdateien,
inaktive Sportjobs und Abstand zu deren nächsten Timern. Sie installiert nur die
zwei geprüften Quotenunits, lädt die App neu und startet ausschließlich den
Preisjob. Modellneutrale und RisikoBet-Fingerprints vorher/nachher abgleichen;
beide Healthchecks, Timer, Jobabschluss und gerenderte Seite prüfen.

Keine Behauptung besserer Wettqualität aus diesen Softwaretests. Anbieterabdeckung
ist nicht vollständig garantiert; fehlende Angebote ergeben keine öffentlichen
Tipps und werden konkret diagnostiziert.
