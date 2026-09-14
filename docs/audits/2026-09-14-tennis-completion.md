# Tennis-Abschluss und parallele Kontextspeicherung — 14.09.2026

## Verifizierter Ausgangspunkt

Lokale Hauptkopie, Reparaturzweig, GitHub main und VPS standen auf
`a1d15b6972f01ba617a62381bacf7bf08a168b1f`. Das vorige Deployment und die
echte Fußball-/Daily3-Neuberechnung waren erledigt. Der Tennisdienst war
weiterhin fehlgeschlagen: 900 Sekunden Timeout nach abgeschlossener
Beobachtungsspeicherung. Der separate Wettfinderlauf war erfolgreich.

## Ursachen und Reparatur

- `_inputs` erzeugte den vollständigen Referenz-Set erneut für jedes einzelne
  Feature. Ein echter gespeicherter Tennisbeleg enthält 192.385 Referenzen und
  12.997.913 Payload-Bytes. Derselbe Mitgliedschaftsindex wird jetzt einmal je
  Validierung verwendet; vollständige Referenzen und alle Prüfungen bleiben.
- Die gesamte B1-Historie wurde innerhalb einer SQLite-Lesetransaktion
  dekodiert. Jetzt werden konsistente rohe Zeilen gelesen, die Transaktion
  geschlossen und erst danach sämtliche Zeilen vor der Bereichsauswahl geprüft.
  Bereits dekodierte Rohzeilen werden freigegeben. Spätere Zugänge werden nicht
  mit dem laufenden Lesebild vermischt.
- `LiveWorker.finish` hielt die Datenbank während aller Kartenberechnungen
  offen und dekodierte denselben Modellzustand für jede Karte erneut.
  Modellprüfung erfolgt einmal je tatsächlich verwendetem Objekt und Tour,
  mit der frühesten Entscheidung als Zeitgrenze. Ein fremdes Objekt mit dem
  gleichen behaupteten Hash wird unabhängig geprüft. Kartenberechnung und
  Snapshot-Decodierung halten keine SQLite-Transaktion mehr offen.
- Pending-Vorprüfungen teilen ihre vollständige Tour-Historie; der Abschluss
  liest trotzdem ein neues vollständiges Bild und erkennt zwischenzeitliche
  Revisionen. Kein erneutes Ganzhistorien-Decodieren für jede Pending-Karte.
- `compute_once` hielt `BEGIN IMMEDIATE` auch während des CPU-Callbacks.
  Eine betriebssystemseitige Koordination serialisiert nun Snapshot-Produzenten;
  die SQL-Transaktionen umfassen nur Lesen bzw. atomare Veröffentlichung.
  Parallele Prozesse berechnen weiterhin genau einmal. Die leere Datei
  `context_models.db.compute.lock` enthält keine Daten und darf im Betrieb
  nicht gelöscht werden. Prozessende gibt die Sperre automatisch frei.
- Der Linux-Gegenlauf fand zusätzlich einen bereits auf dem unveränderten
  Server reproduzierbaren Summen-Rundungsfehler im experimentellen
  Aufschlagmodell. Nur eine obere Grenzüberschreitung um höchstens acht ULPs
  wird auf exakt 1 abgebildet. Bereits gültige Summen bleiben bitgleich;
  größere Überschreitungen, negative und nichtendliche Werte bleiben Fehler.
  Die Prüfung der zugrunde liegenden gemeinsamen Verteilung bleibt unverändert.

## Nachweise vor Deployment

Die Datenbanksperren und unnötigen Referenz-Neuberechnungen wurden zuerst
durch fehlschlagende Regressionstests reproduziert. Gegenfälle prüfen auch
geänderte Modellobjekte, frühere Cutoffs, parallele Erstberechnung in getrennten
Prozessen, unveränderte historische Zeilen und korrupten Inhalt.

Read-only-CPU-Vergleich auf dem echten VPS-Beleg: 10,207 Sekunden vorher,
5,185 Sekunden nachher unter cProfile. Payload-Bytes und Snapshot-Schlüssel
sind exakt gleich. Dies misst einen Beleg, noch keinen vollständigen Tageslauf.

Linux-QA im isolierten `/tmp/betboy-tennis-completion.Jjafxs`:
808 Tests bestanden, einschließlich der zuvor fehlgeschlagenen Rundungsprobe.
Die fehlende JSON-Testfixture wurde im QA-Paket ergänzt; dieser frühere
Paketierungsfehler ist kein Anwendungsfehler. Testabhängigkeiten wurden nur
unterhalb dieses QA-Verzeichnisses installiert, nicht in der Produktions-Venv.
Abschließende lokale Runde dieser Reparatur: 1.275 bestanden, 4 erwartete
Plattform-Skips, eine bekannte pytest-XML-Warnung. Keine vollständige
10.000er-Projektsuite behauptet. XML:
`.pytest_tmp/completion-release-20260914.xml`.

## Offene fachliche und externe Arbeit

Die tatsächlich verwendete öffentliche WTA-Adresse
`http://www.tennis-data.co.uk/2026w/2026.xlsx` lieferte beim VPS-Gegencheck
HTTP 200 mit einer IONOS-HTML-Seite statt XLSX; HTTPS scheiterte mit einem
TLS-Handshakefehler. Diese Antwort darf keinen vorhandenen Datenstand ersetzen.
Die alte WTA-Abdeckung bleibt ehrlich alt. Ein technisch erfolgreicher
Tennis-Scan ist nicht gleichbedeutend mit einem erfolgreichen WTA-Refresh.

Verletzungs-/Müdigkeitseffekte sind weiterhin nicht empirisch aktiviert.
Fußball-Effektverbraucher, passende Trainingsdaten und zusätzliche Sportadapter
bleiben offene Arbeit. Keine Quotenfilter, Marktverbote, erfundenen
Frischezeitpunkte oder Modellfreigaben ergänzt; Cricket unverändert.

Der tatsächliche nachfolgende Git-/Deployment-/Echtlaufstatus wird separat in
`output/playwright/tennis-completion-release-20260914.md` dokumentiert.
