# Freigegebene logische Entfernung von vier Tennis-Altfällen

Stand: 21.09.2026, nach Deployment um 08:24:14 CEST.
Funktionscommit: `66b0a727ab0772e8137b0eb21063712c46c30192`.

## Freigabe und exakt begrenzter Umfang

Der Nutzer bestätigte die Entfernung genau der vier historischen WTA-Fälle aus
der aktiven Auswertung. Historie, Prognosen und Geldbewegungen müssen unverändert
bleiben; Entfernung rückgängig machbar. Keine allgemeine Datenbereinigung.

| ESPN-WTA-Event | Eltern-ID | Originalbelege | Revisionen |
|---|---:|---:|---:|
| 183710 | 1441 | 2 | 2 |
| 183831 | 1419 | 5 | 1 |
| 183844 | 1414 | 18 | 18 |
| 183854 | 1409 | 5 | 1 |

Diese Fälle besitzen inzwischen geänderte Teilnehmerzuordnungen. Kein fremdes
Ergebnis darf nachträglich einer alten Prognose zugeordnet werden. An den vier
Eltern hängen keine Side-Bets. Keine Gewinne, Verluste oder Erstattungen erzeugt.

## Umsetzung und Reversibilität

- `tennis/forecast_retirements.py`: vier explizite Elternidentitäten und
  30 vorab auf dem kanonischen VPS validierte Original-Hashes. Kein Wildcard-
  oder Event-ID-Verbot neuer Prognosen; Quelle, Tour, ID und Erstellzeit gebunden.
- Aktive Leser nehmen die Eltern aus Refresh und automatischer Abrechnung.
  Historische Ansichten vor Freigabe und vollständige Auditansichten unverändert.
- Ergebnisaufnahme prüft weiter Inhalt, Uhrzeit, native Bindung und Modell vor
  der Ausnahme. Beschädigte Belege oder Revisionen bleiben Integritätsfehler.
- Ausgenommene Eventliste nur im administrativen Aufnahmebericht, keine neue
  technische Nutzeranzeige. Status-/Belastungsbeobachtungen bleiben erhalten.
- Rücknahme des Katalogs stellt aktive Verarbeitung ohne Daten-Restore wieder her.

## Tests und native Vorher-/Nachherprüfung

- Erste gezielte Runde: 158 bestanden.
- Breite betroffene Regression: **1.988 bestanden, 3 Plattform-Skips,
  26 Untertests bestanden**, Exit 0 nach 388,12 Sekunden.
- Danach zusätzliche Fremdprognosen-Absicherung: **16 gezielte Tests bestanden**.
  Runden überlappen, nicht addieren. Ältere Vollsuite 10.773/96/111 gilt für
  `7c805ae`, keine vollständige App-Suite für den neuen Commit behaupten.
- Getestet: exakte Identität, historische Sicht, Reversibilität, keine Abrechnung,
  unveränderte Belege, neue Veröffentlichungen desselben Events, fremde aktive
  Prognosen und weiterhin erkannte beschädigte Originale/Revisionen.

Dieselben nativen Antworten mit altem und neuem Collector: **540 Wettbewerbe**.
Vorher `native-outcome-conflicting` und `native-outcome-unavailable`, danach keine
dieser Fehler. Genau vier Events ausgenommen; **236 übrige Ergebniszuordnungen
identisch**. Das sind Batch-Zuordnungen, nicht 236 verschiedene Spiele.
Andere Aufnahmebeobachtungen bleiben unverändert. Keine Datenbankänderungen.

Nach Deployment erneut nativ bestätigt: vier aktive Eltern ausgeschlossen,
alle übrigen aktiven Prognosen identisch; 30 Originale durch ihren verantwortlichen
Leser validiert; 22 Revisionen unverändert; 540 Wettbewerbe, 236 Zuordnungen,
vier ausgenommene Events, keine Ergebnisaufnahmefehler, **0 DB-Schreiboperationen
der Probe**. Fingerabdruck der vier vollständigen Elternzeilen vor/nach identisch:
`86257768702d6102d9f6bc92a3721d5a8891e3e2a2310bd7f264c1264ddd6c03`.

## Veröffentlichung und Abgrenzung

Funktionscommit auf Worktree, lokalem main, GitHub main und VPS identisch.
Deployment unter bestehendem Lock nach Ende aktiver Schreibdienste. Appstart
08:24:14 CEST; interner und öffentlicher Healthcheck `ok`. App, Caddy und sieben
zuvor aktive Timer aktiv. Tagesbackup weiter aus. Keine Datenlöschung,
Schemaänderung, Bereinigung, neue Sicherung oder Geldänderung.

Regulärer Wettfinder bereits **08:07:29–08:15:29 CEST, Exit 0**, `completed`,
keine technischen oder Fußball-Aktualisierungsfehler. Der frühere Fußball-
Kontingentengpass ist im Nachhollauf erledigt, API-Reserve unverändert.
Tennis 359 geprüft, **0 fällig**: kein Beweis für die Behebung der separaten
früheren parallelen Abschlussausnahme. Kein zusätzlicher kompletter Tennis-
Tageslauf nach Entfernung. Sein letzter Exit 1 stammt von davor und wurde nicht
manuell zurückgesetzt. Gezielte native Ergebnisaufnahme jetzt erfolgreich;
keine pauschale Gesamtabnahme oder empirische Wettqualitätsfreigabe.
