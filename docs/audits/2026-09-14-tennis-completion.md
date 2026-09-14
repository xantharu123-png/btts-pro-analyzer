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

## Echter Abschlussversuch und notwendiger Nachfolgepatch

`151fe06` wurde regulär deployed. Tennis lief von 17:51:59 bis 18:07:30 CEST,
der eigentliche Tages-Scan wurde um 18:07:13 nach 900 Sekunden abgebrochen.
124 gefundene Spiele, 64 vorbereitete Prognosen; 33 neue Kontext-Snapshots
wurden gespeichert, bevor das Zeitlimit den vollständigen Abschluss verhinderte.
Der separate, zeitlich überlappende Wettfinderlauf 17:57:19–18:00:55 war
erfolgreich: 55 Modellkandidaten, keine SQLite-Locks. Die behobene Parallelität
ist somit belegt, ein vollständig reparierter Tennis-Tageslauf noch nicht.

149 Funktionsstichproben ohne lokale Variablen zeigten vor allem wiederholte
JSON-Serialisierung, Digestprüfungen und Sortierung der riesigen Referenzlisten.
Der Nachfolgepatch ändert weder das gespeicherte Format noch Prüfsummen:

- `context_json` speichert ausschließlich JSON-Bytes nach dem vollständigen
  unveränderlichen String-Tupel zwischen. Höchstens zwei Einträge, begrenzte
  Referenzzahl und Stringlänge; keine Quelle, Freigabe oder Schema-Prüfung wird
  gecacht. Jede geänderte Liste oder anderer Inhalt wird unabhängig geprüft.
- Streng sortierte Referenzlisten werden linear auf Dubletten/Reihenfolge
  geprüft und linear vereinigt, statt ihre Sortierung über große Sets zu
  zerstören und wiederherzustellen.
- Die bereits geprüften Eingaben liefern den ersten Schlüssel direkt; die
  abschließende unabhängige vollständige Eingangs-/Ergebnisprüfung bleibt.

CPU-Gegencheck auf einem echten Beleg mit 219.742 Referenzen / 14.824.862
Bytes: vorher 7,666/7,675 s, nachher 4,824/4,824 s. Der Vergleich umfasst
Schlüssel, Berechnung, Serialisierung, Payload-Hash, gespeicherte Dekodierung,
Identitätsvergleich und Consumer-Referenz. Cold-Cache je Wiederholung,
SQLite vor CPU-Arbeit geschlossen. Gesamte Veröffentlichung bytegleich.
Dies ist keine Aussage über einen fertiggestellten 64-Spiele-Lauf.

Nachfolgepatch: 1.313 lokale Tests bestanden, vier erwartete Skips, eine
pytest-XML-Warnung; 314 gezielte Linux-Tests bestanden. Unter anderem sind
Unicode/Escaping, Minusnull, sehr kleine Zahlen, veränderte Listen,
Cache-Begrenzung, ungültige Referenzen und unveränderte Identitäten geprüft.
Ergebnis: `.pytest_tmp/completion-json-20260914-broad.xml`, Linux
`/tmp/betboy-tennis-completion.Jjafxs/json-release.xml`.

Die sichere erneute Deployment-Reserve ist derzeit nicht vorhanden:
1.888.415.744 Datenbankbytes, 1.770.926.080 Backup-Inventarbytes, kombinierte
Reserve 16.617.177.088 Bytes, frei ca. 11.692.916.736 Bytes. Rund 4,93 GB fehlen
bereits vor zusätzlichem Code-Staging. Die bisherige Bereinigung umfasste nur
aus Git rekonstruierbare Codekopien (1.884.037.426 Bytes). Andere Testdatenbanken
oder Sicherungen wurden nicht gelöscht. Die alten inaktiven QA-Quellkopien und
Codearchive allein decken die Differenz nach der verbleibenden Inventur nicht.
Für den nächsten Deploy braucht es zusätzliche Kapazität oder eine ausdrücklich
freigegebene, verifiziert gesicherte Auslagerung alter QA-Testdaten. Das
Reserve-Gate wurde nicht verändert oder umgangen.

Zusätzlich bleibt langfristig die vollständige Referenzliste pro gespeichertem
Snapshot ein Wachstumsproblem. Der vorhandene opt-in `context_storage_v2`-
Adapter ist nicht automatisch im produktiven LiveWorker aktiv. Ein bloßer
Importwechsel ist keine freigegebene verlustlose Datenmigration.
