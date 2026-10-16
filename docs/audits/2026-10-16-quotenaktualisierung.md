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
Vorherige Fehlreceipts bleiben erhalten und sind keine bestandene Vollsuite.
VPS vor Veröffentlichung aaafba5; Arbeitsbasis cc06421 enthält nur die
zusätzliche Dokumentation zur zurückgestellten Schlüsselrotation. Produktcode
als`aab9fb244bbdf6bfd9314d2ffd07704b8f5ef462` auf main gepusht und live.

Die Deploymentprüfung verlangt Fast-Forward, saubere versionierte Serverdateien,
inaktive Sportjobs und Abstand zu deren nächsten Timern. Sie installiert nur die
zwei geprüften Quotenunits, lädt die App neu und startet ausschließlich den
Preisjob. Modellneutrale und RisikoBet-Fingerprints vorher/nachher abgleichen;
beide Healthchecks, Timer, Jobabschluss und gerenderte Seite prüfen.

## Echte Produktionsabnahme

- Preisjob16:55:49–16:56:00CEST, Exit0/success:123 gespeicherte Quoten,
  keine Abruf- oder Betriebsfehler.107 Fußballangebote aus32 Preisfixtures,
  16 Team-Sport-Angebote aus14 Zielzeilen. Zwei Tennisziele ohne passende
  Angebote korrekt UNAVAILABLE; kein fälliger E-Sport-Bestand.
- 118 Modellzeilen erhalten.54 öffentliche Wettfinder-Karten alle>=1,20;
  Dinamo HOME_OVER_0_5 exakt1,11 von drei Anbietern, öffentlich verborgen.
  Originale Anbieterzeit12:00:24UTC erhalten, kein frischer Angebotszeitpunkt
  erfunden. Diagnose STALE_CLOCK bezeichnet die strengere45min-Preisprüfung,
  nicht eine erneute Modelländerung oder gelockerte Anzeigealtergrenze.
- Expliziter Vorher-/Nachhervergleich beider vor Deploy/Dispatch erfassten
  Fingerprints bestätigt identische Modellgrundlagen und RisikoBet-JSONs.
  Modellfingerprint195d8020fbb31d21b7e4fec2b1404a23cbaab1cca5e5c843f5f18b6d94017544;
  RisikoBet777cb06d565b526a9f36e619898aff3585eec5a0e56f935bf1d9dd2caaea900e.
- Read-only-Verbraucherprobe:Daily3 eine Auswahl mit1,58; RisikoBet36 veröffentlichte
  Szenarien, alle mit positiver exakter Zulassung, kleinste Quote1,42.
- Interner Browser frisch geladen:WettfinderersteQuote1,22 und kein Dinamo-
  Über0,5; Daily3 1,58;15K1,32/1,21/1,28; RisikoBet geladen. Keine Finanzaktion.
  Drei alte Browser-Disconnectmeldungen während des Appneustarts sind erhalten;
  nach dem frischen Reload keine neuen Fehler beobachtet.
- App/Caddy aktiv, beide Healthchecks ok. Neuer Quotentimer aktiv/aktiviert,
  nächster18:15CEST und danach3h. Backup-Timer deaktiviert. Keine Sicherung,
  Datenbankkopie, Bereinigung, Effektaktivierung oder Modellsuche.

Belege außerhalb Git:`deploy-01.log`, `runtime-proof-02.json`,
`consumer-proof-01.json` unter`C:/Projekt/BetBoy/output/quote-refresh-20261016`.
Der erste Read-only-Prüfversuch scheiterte an ubuntu-Zugriffsrechten, nicht an
der App; als App-Benutzer wiederholt und erfolgreich. Keine Berechtigungen gelockert.

Keine Behauptung besserer Wettqualität aus diesen Softwaretests. Anbieterabdeckung
ist nicht vollständig garantiert; fehlende Angebote ergeben keine öffentlichen
Tipps und werden konkret diagnostiziert.
