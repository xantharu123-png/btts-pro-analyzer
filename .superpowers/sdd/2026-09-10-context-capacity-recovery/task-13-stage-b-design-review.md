# Task13: unabhängiges Review des Stufe-B-Entwurfs

Stand:12.September2026. **Befund: ein P2 vor Abschluss der Architekturprüfung
präzisieren.** Keine Implementierungs-, Betriebs- oder Releasefreigabe.

## Umfang und feste Belegstände

Vollständig gelesen: Spezifikation
`docs/superpowers/specs/2026-09-12-versionierte-pruefnachweise.md`, freigegebener
Kapazitätsplan, Task12-A1-Ergebnis und Task13-Wachstumsdimensionierung.
Zusätzlich relevante bestehende Runtime-/Tennis-/Auswahl-/Snapshotowners
abgeglichen; keine neue Wholebranchprüfung. Keine Codeänderung, Ausführung von
Tests/Diagnosehelfern, SSH, Indexänderung oder Subagenten.

SHA256 der geprüften Dokumentstände:

```text
Spezifikation 38171fee324b527a606dd2daa599f87a95e92364f8d68ce801ff923b1b814bdd
Kapazitätsplan 2cfce8b772ef93f52722fa0c9d8f312c8b4b790c63818ca06093af1398bb13cd
task-12-stage-a-result.md a386c2e8d15f24552ec62ccebb1da9db0d9ad03200d04a13505942608f25cbf6
task-13-growth-sizing.md e4e49e8ada5da8ac469b8463e15f7fe17cd3d6602f40c6a5d6bb57bf58a52489
```

Root bearbeitet parallel ausdrücklich die Größenpräzisierung. Dieses Review
bewertet den obigen festen Spezifikationsstand, nicht unbesehen spätere Texte.
Nur dieser neue Bericht wird vom Reviewer geschrieben.

## P2: Runtimeclosure vor Wiederverwendungsentscheidung festlegen

Ort: Spezifikation **Zeilen121–129**, besonders124–125, und zugehöriger
Versionsänderungstest in Abschnitt9/Punkt4.

Der Text bindet vollständige Produktquellen, danach aber nur die
„tatsächlichen geladenen Abhängigkeiten“. Das ist ohne zusätzliche Regel
mehrdeutig und für eine wiederverwendende Prüfung potenziell zirkulär:
Die gerade auszulassende Prüfeinheit könnte ihre transitive Bibliothek erst
beim Aufruf laden. Wenn die Entscheidung nur gegen den im aktuellen Lauf
beobachteten Importsatz fällt, wird eine geänderte, wegen Wiederverwendung
jetzt nicht geladene Bibliothek gerade nicht neu identifiziert. Root-Versiegelung
beweist Schreibschutz der gewählten Bytes, nicht deren Gleichheit mit dem
Ausführungsumfang des alten Nachweises.

Konkretes Design-Gegenbeispiel, kein ausgeführter Produkttest: GenerationN
enthält einen gültigen Nachweis für eine Prüfeinheit mit einem bedingt importierten
Paket/native Backend. FürN+1 ändern sich dessen installierte Bytes, während
Produktquellen und Daten identisch bleiben. Ein schneller Pfad lädt die
Prüfeinheit nicht und vergleicht nur aktuell beobachtete Module; dann könnte
erN wiederverwenden, obwohl nach Abschnitt5 vollständiger Neuaufbau erforderlich
ist. Dass der reale Code Imports innerhalb von Prüffunktionen besitzt, ist
direkt sichtbar, etwa `context_runtime_tennis.py:132` und`:212`; der Entwurf
darf seine Korrektheit nicht davon abhängig machen, dass dieselben Abhängigkeiten
zufällig vorher anderswo importiert wurden.

Korrigierbarer Vertrag:

- Vor jeder Aufgabenplanung/Wiederverwendung einen vollständigen, festen,
  root-versiegelten zulässigen Ausführungsbestand identifizieren und dessen
  aktuelle Bytes mit der im Nachweis gebundenen Identität vergleichen.
- Auch nur bedingt/lazy erreichbare Pythonpakete, native Erweiterungen und
  transitive dynamische Bibliotheken sowie semantisch gelesene Paketressourcen
  und erlaubte Konfiguration einbeziehen. FürV1 darf dies konservativ das
  gesamte erlaubte Runtimeabbild statt eines feinen dynamischen Graphen sein.
- Import-/Librarysuchpfade, Umgebungs-/Startparameter und spätere Nachladewege
  fixieren; nicht inventarisierte Zugriffe führen zum Abbruch, nicht zu einem
  nachträglich vertrauenswürdigen bereits wiederverwendeten Nachweis.
- Tatsächlich beobachtete Imports können diese Closure auf Einhaltung prüfen,
  dürfen sie aber nicht erst aus den verbleibenden ausgeführten Aufgaben
  definieren. Die alte inventarisierte Pfadliste neu zu hashen ist ebenfalls
  nur ausreichend, wenn neue/umgelenkte Auflösungswege ausgeschlossen sind.
- Abnahmetest ergänzen: reine Runtime-/Ressourcenänderung an einem im warmen
  Pfad nicht geladenen Zweig muss bereits vor Wiederverwendung entwerten;
  neu auflösbares gleichnamiges Modul außerhalb der Closure muss scheitern.

Dies ist eine Präzisierung der bereits beabsichtigten konservativen
Versionsbindung, keine Forderung nach neuem Modell-/Quellvertrag oder zusätzlicher
Implementierung im aktuellen Designauftrag.

## Geprüfte tragfähige Teile

- **Auftragsgrenze:** Entwurf verlangt explizite neue Entscheidung vorB-Code.
  „Ja alles machen“ für den Plan und bestehende Push-/Deployautorität werden
  nicht mit dem neuen persistenten Nachweisvertrag gleichgesetzt. A1 bleibt
  STOP; keine unbelegte weitere Mikrooptimierung wird daraus abgeleitet.
- **Gesamtbestand:** Physische/schemaweite Inventur, typisierte Rohwerte,
  Schlüsselvollständigkeit, Referenzen, Löschungen, andere Touren, Zukunft und
  unreferenzierte Daten sind erfasst. Opaque D2-Finaldaten bleiben opaque.
  Alte transaktionsgebundene Cacheflags werden nicht aus Dateien rekonstruiert.
- **Kausale Auswahl:** Der Text bindet nicht bloß positiv verwendete IDs,
  sondern ganze aktuelle Präfix-/Gruppenauswahlen einschließlich Leermenge,
  Gleichständen und spät eingefügten alten Beobachtungszeiten. Das entspricht
  der realen Originalauswahl und vollständigen Snapshot-Historienabhängigkeit.
  Entwertung betroffener alter Analysen ist ausdrücklich vorgesehen; eine
  append-only Datenbank wird nicht mit monotonen Ereigniszeiten verwechselt.
- **Original/Snapshot:** Tatsächlicher Vorentscheidungszustand, Quellrevision,
  Originalmodell, vollständige geordnete Tourhistorie, Features/Effekte/Freigaben
  und Transport bleiben zuständig. Neue Prognosen werden nicht aus alten
  Prüfergebnissen erzeugt; fachliche Einschränkungen werden nicht aufgewertet.
- **Proofauthority:** Isolierter Nicht-App-Prüfbenutzer, versiegelte Eingaben
  und Runtime, root-eigener Publisher ohne Produktimport, getrenntes proof-only
  Geheimnis und kompletter Aufgabenabschluss sind sachgerecht getrennt.
  Teilresultate bleiben pending; CAS/Generation/fsync/atomare Veröffentlichung
  und konkurrierende/veraltete Publisher sind als Abnahmepunkte enthalten.
- **Rollbackbehauptung:** Der getrennte aktuelle Kopf schützt ausdrücklich
  gegen ein Zurücksetzen nur des App-/SQL-Bestands. Ein kompletter VM-/root-
  Rollback wird ohne externen Anker gerade nicht ausgeschlossen. Restore-Epoche,
  Neuprüfung und bestehende Kontointegrität bleiben getrennte Anforderungen.
- **Kosten:**1800CPU/3600Gesamtsekunden sind klar als vorgeschlagener neuer
  auftragsweiter Lebenszyklus benannt, nicht als bestandener alter300er-Volltest.
  Nachkommen, Neustarts, Reservierungen, unklarer Verbrauch und Deadline sind
  ausdrücklich bilanziert. Erstprüfung und Codewechsel werden nicht versteckt.
  Ein einzelner unveränderter Owner, der seine Grenze überschreitet, bleibt
  blockierend. Die Zahlen sind weder gemessen noch bereits genehmigt.
- **Bootstrap:** Der alte Reparaturinstaller mit seinem zu langsamen kalten
  Prüfer ist explizit als Einführungsfalle erkannt. Ein separat geprüfter
  versionierter Bootstrap mit frischem Restore/Backup, exakten Pins und
  Rückweg ersetzt weder den Check durch einen Marker noch Appdeployment durch
  bloßen Updateraustausch. Das ist ein offener Liefergegenstand, kein Erfolg.

## Sieben Tage und Speicher: zwingender offener Gate, kein weiterer Textfehler

Der geprüfte Stand behauptet bereits keine Sieben-Tage-Garantie. Er verlangt
Größenprüfung vorB-Implementierung und eine weitere Entscheidung bei Überschreiten
unveränderter Grenzen. Deshalb wird das inzwischen präzisere Task13-Sizing nicht
als erfundener zweiter Sicherheitsbefund dargestellt; es muss aber in die
bevorstehende Entscheidungsvorlage sichtbar einfließen.

Das vorläufige Profil ergibt589.776Belege/199Originale und Snapshots/114Cutoffs,
ist jedoch aus nur zwei Teilkalendertagen und ATP abgeleitet. Die unabhängigen
bedingten Szenarien ergeben etwa **1.152.584.353Dateibytes** gegen1.073.741.824
und **345.159.123kanonische ATP-Historienbytes** gegen268.435.456. Beides sind
Szenarien, keine erzeugten/abgenommenen Größen und keine kalendergenaue Prognose.
Die Snapshotreferenzen können die Durchschnittsrechnung weiter verschärfen.

Für Roots Präzisierung wichtig: Dateigröße und vollständige kanonische
Historiengröße sind **unabhängige** Zulassungsgrenzen. Verlustfreie kompaktere
Speicherung wiederholter Referenzlisten neuer Snapshots kann die Dateigröße
reduzieren, behebt aber nicht automatisch die256MiB einer vollständig expandierten
kausalen Historie für einen neuen unveränderten Owner. Ebenso sind Cache64MiB
und persistenter Proofindex256MiB keine zusätzlichen erlaubten Historienbudgets.
Wenn die vereinbarte Probe nicht passt, B nicht als alleinige CPU-Reparatur mit
erfülltem Sieben-Tage-Ziel freigeben und die Probe nicht stillschweigend verkleinern.

## Abgrenzung und nächste konkrete Entscheidung

Nach Präzisierung der vorausgehend vollständigen Runtimeclosure und Einordnung
der unabhängigen Speichergrenzen kann der Architekturentwurf erneut eng geprüft
und dem Nutzer zur ausdrücklichen Vertragsentscheidung vorgelegt werden.
VorB-Code bleiben tatsächliche Größenprobe, genaue Aufgabenbriefe und die
benannten Betriebs-/Nachweisgrenzen offen. Dieses Dokument bescheinigt keine
neue Laufzeit, keinen Volltest, keinen Größenpass und keine Installation.

## Eng begrenzte Nachprüfung der Korrektur

Stand:12.September2026. **P2 behoben; der korrigierte Architekturentwurf ist
aus Reviewsicht zur ausdrücklichen Vertragsentscheidung geeignet.** Keine
B-Implementierungsfreigabe durch dieses Review.

Die erste gezielte Nachprüfung betraf ausschließlich Abschnitt5/8 des
Spezifikationsstands SHA256
`5cfe4ad5f59e4ebc984bea305f14e93eb1c2bde227c56a78926ae765d95b7f4e`.
Anschließend wurde ausschließlich der angekündigte ergänzte Abnahmepunkt9.4
einschließlich seines neuen Dokumenthashs gelesen. Abschließend geprüfter
Spezifikationsstand SHA256:
`498e63c5641adaccdd4d284fa9b57ad93c02ba834e9abd6bf4064636d6b12da1`.

- **Closurekorrektur bestätigt:** Abschnitt5 verlangt jetzt eine vorab
  deklarierte vollständige Abhängigkeits-/Ressourcenclosure, vollständig vor
  der ersten Wiederverwendungsentscheidung gehasht. Nicht aufgerufene Lazy-
  Zweige, native Bibliotheken, Paket-/Modellressourcen, Import-Suchpfade und
  transitive Abhängigkeiten sind explizit enthalten. Beobachtete Module sind
  nur ein zusätzlicher Gegencheck; unbekannte Imports/Ressourcen beenden die
  Wiederverwendung. Zusammen mit der fortbestehenden Entwertung bei geänderter
  Ausführungsidentität löst das die zirkuläre Definition des Erstbefunds.
- **Passendes Akzeptanzkriterium bestätigt:** Abschnitt9.4, nun Zeilen292–298,
  verändert eine lazy importierte Bibliothek, während alle ladenden Aufrufe
  als Wiederverwendungskandidaten geplant sind. Der vorgezogene Closurevergleich
  muss trotzdem entwerten. Native Bibliothek, Paketressource und Importpfad
  erhalten entsprechende Fälle; eine unbekannte Abhängigkeit ist kein Cachehit.
  Das ist das konkret fehlende Gegenbeispiel, nicht bloß ein allgemeiner
  Versionswechseltest. Es ist ein vorgeschriebener zukünftiger Test, kein
  bereits ausgeführtes Testergebnis.
- **Speicherpräzisierung bestätigt:** Abschnitt8 nennt die bedingten
 1.153GB-/345MB-Szenarien sichtbar als vorgeschalteten Größen-/Entscheidungsgate,
  nicht als erzeugte Zukunftsdaten oder Größenpass. Datei- und vollständige
  kanonische Historienzulassung sind explizit getrennt. Kompaktere Referenzspeicherung
  reduziert nicht die256MiB-Grenze der vollständigen Historie; deren Überschreitung
  verlangt einen gesonderten belegbar äquivalenten Eingabe-/Verarbeitungsvertrag.
  Keine Freigabe von Kompression als Umgehung, Datenpruning oder stiller
  Verkleinerung des vereinbarten Profils wird daraus abgeleitet.

Der ursprüngliche Befund und seine Belegidentität bleiben oben unverändert
erhalten. Es wurde keine zweite vollständige Reviewrunde und kein Code-/Test-/
Serverlauf durchgeführt. Nur dieser Bericht wurde ergänzt. Die übrigen
ursprünglichen Reviewaussagen gelten für ihren damaligen geprüften Umfang.
Offen bleiben ausdrückliche Nutzerentscheidung zuB, echte Größenprobe und
gegebenenfalls vorgelagerte Speicher-/Vertragsentscheidung, danach erst eng
beauftragte Implementierung und sämtliche bisher offenen Abnahme-/Releasegates.
