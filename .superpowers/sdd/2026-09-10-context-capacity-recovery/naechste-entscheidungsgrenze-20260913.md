# Nächste Entscheidungsgrenze nach dem tatsächlich abgeschlossenen QA-Lauf

Stand13.09.2026,13:45UTC. Dies ist ein Entscheidungsvermerk, kein neuer
freigegebener Modell-, Budget- oder Implementierungsvertrag.

## Was jetzt wirklich abgeschlossen ist

Task58 kleiner nativer Datenpfad, Task60 Zulassungsprotokoll und Task61
Kindprozess-Protokoll waren bereits abgeschlossen; sie wurden nicht erneut
ausgeführt. Task62 Dateileser ist unabhängig geprüft und mit43 echten Linux-
Tests bestätigt. Der neue Task63 Fix für gleichzeitig gehaltene Dateien ist
unabhängig geprüft und mit35 echten Linux-Tests plus genau einem reinen
Windows-Test-Skip bestätigt. Alle Prozesse dieser Messungen sind beendet;
Quellen, Fehlerbelege und Ergebnisse sind erhalten.

## Konkreter verbleibender Engpass

Der größte alte QA-Ordner wurde jetzt einmal vollständig gelesen:
56895 Dateien,17409 Verzeichnisse,1932 Links,7,60GB logische Daten.
Das dauerte47,56CPU-Sekunden. Die echte Aufrufkette verlangt aber zwei solche
Vollprüfungen je60CPU-begrenztem Prozess und zwei Prozesse, also vier insgesamt.
Weitere alte Ordner und die eigentliche Datenprüfung kommen hinzu.

Zweimal47,56 sind rechnerisch95,12CPU-Sekunden. Das ist eine Hochrechnung bei
gleichem Aufwand, keine gemessene zukünftige Untergrenze. Es rechtfertigt
keinen weiteren unveränderten großen Versuch und keinen Erhöhungsautomatismus.
Die belegten Aufrufstellen stehen in task-62-retained-cost-review.md.

## Empfohlene nächste Entscheidung, noch nicht umgesetzt

Den Prüfablauf gezielt neu entwerfen: vollständige historische Vor- und
Nachprüfungen explizit als eigene Arbeit eines gemeinsam budgetierten
Prüfkoordinators behandeln. Der gesamte Aufwand muss vorab begrenzt und
laufübergreifend nachvollziehbar verrechnet werden; kein neues freies Konto
pro Prozess, kein Zurücksetzen alter Kosten. Der eigentliche Modell-/Daten-
Worker darf dadurch nicht still mehr Zeit, RAM oder Datenfreigaben erhalten.

Vor Codeänderung muss der kurze konkrete Vertrag festlegen:

1. Welche bisherigen Prozessgrenzen sich ändern und wie ein gemeinsames
   CPU-/Wandzeitkonto alle Vorprüfung-, Worker-, Nachprüfung- und Fehlerkosten
   bindet, einschließlich der schon dokumentierten Versuche und offenen Kosten.
2. Wie die Vor- und Nachprüfung den vollständigen identischen Bestand prüfen,
   ohne alte Hashes als neue Prüfung auszugeben oder mutierbare Daten zu übersehen.
3. Wie Abbruch, unvollständige Ausgabe, Restprozesse und unverbrauchte Reserven
   nachgewiesen werden; ein Teilbericht bleibt ein Teilbericht.
4. Welche vorher bestätigten numerischen Grenzen unverändert bleiben und
   welche konkret neu freigegeben werden müssen. Keine Zahlen durch Rateversuch.

Dieses Vorgehen ändert den bisherigen Prozess-/Ressourcenvertrag und braucht
daher eine ausdrückliche Entscheidung. Bestehende C-/B-/Commit-/Push-/Deploy-
Freigaben werden nicht nochmals zur Disposition gestellt. Kein weiterer
großer Messlauf, keine stille Grenzwerterhöhung und kein Deployment vor der
Entscheidung und anschließender erfolgreicher Abnahme.

## Separater historischer Testknoten

Der aufbewahrte Task62 Linux-Negativtest enthält absichtlich genau einen FIFO:
`/tmp/betboy-context-retained-task62-6eb267a-01/green/fixtures/test_native_fifo_refused_witho0/fifo`.
Die aktuelle historische v1-Vollprüfung lehnt ihn korrekt ab. Kein Löschen,
Auslassen des Knotens/Ordners oder Öffnen des FIFO, um einen Test zu bestehen.
Ein späterer historischer v2-Vertrag muss eine endliche, exakt pfad-/epoch-
gebundene Metadata-only-Erfassung definieren; reguläre Inhalte bleiben voll
gehasht. Default retained_root und aktive/code/corpus-FIFO-Ablehnung bleiben
unverändert. Das ist dokumentiert, aber weder implementiert noch freigegeben.

## Nicht mit erledigt verwechseln

Die große reale Datenprüfung, kompletter C-Speichervertrag, B-Nachweisbesitz,
Restore, aktuelle Vollsuite und kontrollierter main-/VPS-Rollout sind offen.
Auch fertige empirische Verletzungs-/Müdigkeitsmodelle oder bessere Wettqualität
sind damit nicht nachgewiesen. Cricket/A0/P4b3 bleiben wie zuvor ausgenommen.
T2 generische Transport-Logkappen und M1 created_at-Nachweis bleiben offen.

Live13:45UTC: main und VPS2dd1116; App/Caddy und Healthchecks funktionieren,
aber Wettfinder- und Tennis-Jobs stehen auf Fehler. Sieben Timer sind geplant;
sie führen Berechnungen aus, keinen Git-Pull und kein Deployment. Der frühere
konkrete Wettfinder-Fehler wird nicht ohne neue Artefaktprüfung automatisch
als Ursache jedes späteren Fehlers ausgegeben. Kein reset-failed/Neustart.
