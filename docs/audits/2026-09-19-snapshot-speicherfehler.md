# Snapshot-Speicherfehler 19.09.2026

## Ursache und Umfang

Der reale VPS-Bestand enthielt Analyse-Snapshots mit 504.808
`observation_refs` und rund 33,99 MB pro Zeile. `pack_payload` nutzte nur
bis 500.000 Verweisen die vorhandene gemeinsame Blockablage. Oberhalb
dieser Grenze fiel der Code auf vollstaendiges Inline-JSON pro Analyse
zurueck. Bei der spaeteren Messung belegten 1.041 Snapshot-Zeilen
1.313.770.224 Nutzdatenbytes; die Kontextdatenbank insgesamt
3.323.097.088 Bytes. Das ist von normalen Datenabrufen, Git-Code und
Sicherungsarchiven zu unterscheiden.

Die Reparatur entfernt den Gesamtlisten-Grenzwert aus der Speicherwahl.
Einzelne SQLite-Blobs bleiben begrenzt; Datenbloecke bleiben maximal
64 KiB gross. Der Leser bindet die erwartete Gesamtlaenge an die
tatsaechliche Anzahl der Blockverweise und prueft Groesse, Reihenfolge,
Gesamtlaenge und Hashes. Alte JSON- und Blockformate bleiben lesbar.
Modellwahrscheinlichkeiten, Belege und logische Snapshot-Hashes werden
nicht geaendert. Die bereits vorhandene transaktionale Kompaktierung
kann nun auch die zuvor zu grossen Inline-Snapshots umpacken.

Das ist keine Behauptung, dass Beobachtungshistorien gar nicht mehr
wachsen oder dass alle wiederholten Tennis-Abrufe inhaltlich dedupliziert
wurden. Die tatsaechlichen Empfangszeitpunkte bleiben erhalten.

## Nachweise

- Vor der Korrektur: neue Grenzwert-/Kompaktierungstests ergeben
  3 Fehler und 1 Erfolg. Reproduziert mit 500.001 und 1.050.001
  Verweisen sowie einem alten grossen Inline-Snapshot.
- Nach der Korrektur und dem gezielten Inline-only-Wartungspfad:
  25 Speichertests unter Windows bestanden (17,42 Sekunden, Exit 0),
  dieselben 25 Tests isoliert auf dem VPS (57,89 Sekunden, Exit 0).
  Enthalten: unveraenderte logische Identitaeten, Wiederverwendung,
  atomarer Rollback und Korruptionsfaelle in beiden Wartungsmodi.
- Unabhaengiges Read-only-Review: kein Mergeblocker. Nichtblockierender
  P3-Hinweis: weitere gezielte Negativtests fuer manipulierte deklarierte
  Blocklaengen waeren sinnvoll; die gelesene Implementierung lehnt diese
  Faelle korrekt ab. Keine Aussage zu Live-Migration oder Wettqualitaet.
- Rein lesende Probe auf echten Daten: ein bislang inline gespeicherter
  Snapshot mit 33.924.263 Bytes wird zu 102.221 Header-Bytes plus einer
  gemeinsam nutzbaren Referenzliste. Noch keine Produktionsmutation daraus
  ableiten. Bereits geteilte Snapshots bleiben beim Inline-only-Lauf unberuehrt.
- Exakter Wartungsablauf mit synthetischer 500.001-Verweise-Datenbank auf
  Linux durchgespielt: 33.579.008 -> 16.199.680 Bytes; alle Tabellenidentitaeten
  und Snapshot-Hashes erhalten, SQLite-Pruefung ok, gespeicherte Analyse
  anschliessend ohne Neuberechnung identisch gelesen.
- Gesamtlauf auf finalen Quell-/Testbytes: 10.293 bestanden, 96 Skips,
  111 Untertests bestanden, 16 Setupfehler (1604,64 Sekunden, Exit 1).
  Alle 16 sind derselbe Windows-Git-Fehler `dubious ownership` beim Lesen
  historischer Referenzquellen in `tests/test_esports_live_original.py`.
  Anschliessend die gesamte betroffene Datei mit prozesslokaler
  `safe.directory`-Freigabe exakt dieses Worktrees erneut geprueft:
  56 bestanden, Exit 0, 3,32 Sekunden. Keine Code-/Testaenderung, keine
  globale Git-Freigabe und keine gelockerte Pruefung. Zusammen sind damit
  10.309 unterschiedliche Tests und 111 Untertests erfolgreich geprueft;
  dies ist ausdruecklich kein einzelner fehlerfreier Gesamtlauf.
- Produktquellbytes SHA256:
  `93012b39cb8eff09a885738359933e5132026c927fa61a51b4031cbf095c569b`;
  Testdatei SHA256:
  `66d9c09920e0a21c83bc1ffa47301be82ea435cf47fa8dcbc3d046cc57abab58`.
  Nach diesen Laeufen blieben beide Dateien unveraendert.
- Produktionsablauf ist noch vorbereitet, nicht bereits ausgefuehrt.
  Wartungsreview fordert fest gepinnte root-eigene Skripte, vollstaendige
  Schemaidentitaet sowie unveraenderten Aufbewahrungstimer; diese Kontrollen
  sind in der eng begrenzten Wartung enthalten. Keine neuen Archive.

## Betriebsentscheidung des Nutzers

Der Nutzer lehnt kuenftige Tages- und Update-Sicherungsarchive ab.
`betboy-backup.timer` wurde auf dem VPS auf `disabled/inactive` gesetzt;
App und Healthcheck blieben aktiv/ok. Vorhandene Archive wurden nicht
geloescht. Der Aufbewahrungs-/Bereinigungstimer blieb unveraendert.

Der alte installierte Updater erstellt weiterhin verpflichtende Archive
und aktiviert den Tagesbackup-Timer am Ende wieder. Er darf daher nicht
unveraendert fuer diese neue Betriebsentscheidung verwendet werden.
Eine reine Codebereitstellung darf keine Abhaengigkeiten, Root-Dienste,
Schluessel oder Geldkonten migrieren. Vor der bestehenden verlustfreien
Snapshot-Kompaktierung muessen saemtliche Schreiber stillstehen.
Keine neuen Sicherungsarchive erzeugen; SQLite-Transaktionsjournale sind
keine aufbewahrten Sicherung und werden fuer atomare Schreibvorgaenge
weiter benoetigt. Ohne externe Sicherung ist ein spaeterer Hardware- oder
Datendefekt nicht durch diesen Reparaturablauf wiederherstellbar.

## Abrufkosten und GitHub

Fussball nutzt `v3.football.api-sports.io`. Die oeffentliche direkte
API-Football-Preisliste nennt 19/29/39 USD pro Monat fuer Pro/Ultra/Mega;
der tatsaechlich gebuchte Kontotarif ist damit nicht nachgewiesen.
Quelle, abgerufen am 19.09.2026: https://www.api-football.com/pricing

Der beobachtete Tennis-Pfad fragt ESPN-Scoreboards ohne kostenpflichtigen
API-Schluessel ab. Vorhandene Historien liegen bereits auf dem VPS; neue
Spielstaende und Ergebnisse kommen weiterhin vom jeweiligen Anbieter.
Die fehlerhaften mehrfachen Snapshot-Listen entstehen danach lokal in
SQLite, nicht durch GitHub oder eine eigene bezahlte Anfrage pro Verweis.
