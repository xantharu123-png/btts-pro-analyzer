# Kontextspeicher-Reparatur – 14. September 2026

## Auftrag und Freigabegrenze

Der Nutzer verlangt die Behebung der redundanten Datenhaltung und des RAM-
Verbrauchs samt Commit, Push und geprüftem VPS-Deployment. Cricket, Quoten,
Einsätze, Modellfreigaben und historische Dateninhalte bleiben unverändert.

Die automatische Aktionsprüfung hat eine neue Kopie der produktiven
`context_models.db` in den privaten QA-Ordner ausdrücklich abgelehnt: Die
frühere Archivfreigabe bezog sich auf Code, nicht auf Laufzeitdatenbanken.
Die ergänzende Zustimmung wurde angefragt und anschließend vom Nutzer
ausdrücklich mit „ja“ erteilt. Erst danach wurde ausschließlich diese DB
in `/tmp/betboy-memory.IzioJU/data/context.db` kopiert: 2.246.602.752 Bytes,
29,10 s, SQLite `integrity_check=ok`. Keine Konten/Einsätze/Secrets kopiert.
Echte RAM-Prüfung, verlustfreie QA-Kompaktierung und operative Prüfung sind
bestanden. Die produktive Kompaktierung und der reguläre Updater wurden
ebenfalls abgeschlossen; der tatsächliche Tennis-Gesamtlauf ist davon getrennt.

## Implementierte Reparatur

- Der Live-Tennisreader friert die vollständigen SQL-Rohzeilen in einer
  privaten, automatisch geschlossenen temporären Datei ein. Die SQL-Verbindung
  ist vor der CPU-Validierung geschlossen. Jede Zeile wird weiterhin vor
  Tour-/Zeitfilterung geprüft, auch fremde Touren und spätere Korrekturen.
- Die Live-/Pending-Verbraucher bauen unmittelbar eine kompakte unveränderliche
  Tourprojektion. Es gibt keine gleichzeitig gehaltene vollständige Rohzeilen-
  und dekodierte Dictionary-Sammlung mehr. Die chronologische Sortierung betrifft
  nur kleine Zeit-/Hash-/Indexeinträge, nicht den gesamten SQL-Payload.
- Große `observation_refs` werden physisch ausgelagert. Der vollständige
  logische JSON-Inhalt, Snapshot-Key und bisherige Payload-Digest bleiben gleich.
  Alte Inline-Snapshots bleiben lesbar.
- Referenzen werden binär in höchstens 64-KiB-Blöcken gespeichert. Sortierte
  Historien benutzen stabile Hash-Präfixgruppen: Bei einem neuen Receipt werden
  unveränderte Gruppen gemeinsam weiterverwendet. Jede Liste besitzt eine
  inhaltsgebundene Blockbeschreibung; jeder Snapshot verweist darauf.
- Neue Tabellen: `context_snapshot_references` und
  `context_snapshot_reference_blocks`. Backup-/Schema-/Consumer- und
  Kopieinventurpfade berücksichtigen sie. Fehlende, umsortierte, beschädigte
  oder typveränderte Referenzen bleiben Fehler, niemals eine Neuberechnung.
- `scripts/compact_context_snapshots.py` konvertiert vorhandene Snapshots
  atomar und verifiziert jeden logischen Inhalt. Fehler rollen alle
  Konvertierungen zurück. `--vacuum` gibt danach ausschließlich ungenutzte
  SQLite-Seiten frei. Vor Einsatz: echte Sicherung prüfen und Writer stoppen.
- CPU-lastiges Dekodieren gespeicherter Pending-Snapshots bleibt außerhalb
  der SQL-Lesetransaktion. Die physische Referenzsammlung wird vorher eingefroren.

## Kompatibilitätsgrenze ausdrücklich erhalten

Der ältere C2-JSON-Adapter darf die neue physische Blockbeschreibung nicht
fälschlich als unverändertes altes JSON ausgeben. Er erfasst sie mit
`shared-reference-storage` als vollständig inventarisierten Rohtransport;
beide Referenztabellen gehören zur vollständigen Kopie. Der normale owning
Runtime-Decoder prüft weiterhin das identische logische Snapshot-Dokument.
Dies ist kein neuer empirischer Modellnachweis und kein C2-Semantik-Pass.
Die bisherigen Legacy-Adaptertests verwenden ausdrücklich Inline-Fixtures.

## Prüfungen

- Gezielter finaler lokaler Abschlusslauf: 1.923 bestanden, 8 Plattform-Skips,
  keine Warnungen. Nachweis: `.pytest_tmp/memory-release-final.xml`.
- Finaler Linux-Gegenlauf: 827 bestanden, keine Warnungen,
  ausschließlich synthetische Daten. Nachweis auf dem VPS:
  `/tmp/betboy-memory.IzioJU/data/linux-release-final-027.xml`.
- Zusätzliche neue Regressionen: logische Byte-/Key-/Hash-Gleichheit,
  Idempotenz, gesamte Transaktion bei später Beschädigung zurückrollen,
  Parallelpublikation, Listenumordnung, falsche SQLite-Typen, entfernte Blöcke,
  begrenzte Lebensdauer dekodierter Inventarzeilen, Writer während CPU-Prüfung,
  fremde Tour/Future-Korrektur und inkrementelles Wachstum.
- Der früher gestartete Volltest auf einem Zwischenstand endete nach
  3.053 bestandenen Tests mit fünf Befunden. Vier betrafen die noch alte
  unabhängige Schema-Oracle; sie wurde um beide Tabellen ergänzt. Ein
  übernommener Test erwartete vorbestehende Producer-Lockdateien nicht.
  Er prüft jetzt korrekt, dass der Consumer keinerlei neue Datei erzeugt.
  Dieser Lauf ist KEIN grüner Vollsuitennachweis.
- Ein früher Linux-Versuch scheiterte am SSH-eigenen QA-Elternordner. Nur
  dieser neue Ordner wurde root-eigen gemacht; die Vertrauensprüfung blieb
  unverändert. Anschließend bestand der Linux-Gegenlauf.
- Die ergänzten Linux-Kopie-Fixtures müssen wie die Produktion mit umask 0027
  laufen. Die SSH-umask erzeugte gruppenschreibbare synthetische Dateien;
  diese wurden von der unveränderten Vertrauensprüfung korrekt abgelehnt.

## Echter Volumentest nach ergänzender Nutzerfreigabe

Private Quelle: `/tmp/betboy-memory.IzioJU/data/context.db`. SQLite-Backup
statt Dateikopie einer offenen WAL-Datenbank. 112 Snapshots, 454.405 Inhalte,
454.405 Beobachtungen, 117 Artefakte und drei Manifeste.

- WTA: 247.105 Referenzen, 346,50 s Wandzeit / 335,64 s CPU,
  490.336 KiB Peak-RSS, Referenzdigest
  `2b7db124d3caab9862c229b3f0c7aa8680aa2f2d6024f3510687f3921459fc22`.
- ATP: 181.572 Referenzen, 311,99 s Wandzeit / 309,81 s CPU,
  367.388 KiB Peak-RSS, Referenzdigest
  `946f4935daebd9309a7e03e0701789cae3c79cb114da54abf57db3f369edce59`.
- Beide vollständigen Readerläufe unter unveränderten 1.400-MiB-AS-/600-CPU-s-
  Grenzen beendet, keine Provideraufrufe. Das ist kein gemessener Peak des
  gesamten Tageslaufs; zwei Touren brauchen weiterhin mehrere CPU-Minuten.
- 112 Snapshots verlustfrei konvertiert. DB 2.246.602.752 → 938.500.096 Bytes.
  Logische Snapshot-Payloads 1.332.011.883 Bytes, physisch nun 12.085.628 Bytes
  plus 49.356 Bytes Listenbeschreibungen und 28.380.032 Bytes Referenzblöcke.
  Sechs Referenzmengen, 1.536 Blöcke. Jeder Snapshot wurde dekodiert, mit seinem
  bisherigen Key/Digest geprüft, rekonstruiert und logisch bytegleich verglichen.
- Zusätzlich vollständige vor/nach Inventur: alle anderen Tabellen samt echten
  SQLite-Wertetypen/Primärschlüsselreihenfolge und alle Snapshot-Keys/Digests
  unverändert. Keine Belege, Historien oder Ergebnisse entfernt.
- Die ursprüngliche Anschlussprüfung am app-eigenen QA-Pfad wurde korrekt
  durch den Root-Seal-Vertrag abgelehnt. Anschließend nur diese QA-Datei
  unter `/var/lib/betboy-context-verifier/memory-qa-so2swnkh/context.db`
  root-eigen/0440 bereitgestellt; Größe und SHA256 vollständig gleich.
  SHA256: `6b627b6d6d4279feae88b2d299d7d3fad90c9766ba87d7f5abbb14c2685f342c`.
- Operative Prüfung mit dem Produktionsvenv bestanden: 17,43 s,
  149.768 KiB Peak-RSS. Schema, SQLite, Referenzen, aktive ATP-/WTA-Modelle
  und Manifestkette intakt. Report: `data/real-deployment-report.json`.
  Der erste Aufruf mit System-Python hatte kein pandas; kein Paket installiert
  und kein Prüfer gelockert, sondern den vorhandenen Produktionsvenv verwendet.
- Zusätzlicher Vollsuitenlauf: 3.192 bestanden, 21 Skips, 71 Untertests;
  drei veraltete Testinventur-Annahmen über bestehende leere Producer-Locks.
  Die exakt zwei erlaubten Pfade wurden vorab deklariert; unbekannte Lockdateien
  bleiben abgelehnt. Alle sechs betroffenen Tests bestanden danach.
- Eine spätere Teilrunde zeigte eine weitere alte Testannahme zum ausdrücklich
  veröffentlichten Helper-Pin aus `442b60f`. Der Test prüft nun sowohl den exakten
  aktuellen Updater/Helper-Hash als auch die bytegleiche Rekonstruktion seines
  eingefrorenen Vorgängers durch Rücknahme ausschließlich dieses einen Pins.
  Produktionscode unverändert; 111 Tests bestanden, ein Linux-spezifischer Skip.
- Breite disjunkte Dateirunden endeten zunächst mit 2.172 / 2.064 / 2.385
  bestandenen Tests und jeweils einem Fehler. Ein Fußball-Paritätstest bezog
  die bereits veröffentlichte Orchestrierungsänderung `a1d15b6` nicht ein.
  Nur diese Funktion wird jetzt gegen genau diesen echten Commit geprüft;
  Engine und übrige Mathematik bleiben gegen den ursprünglichen Parent fixiert.
  Alle 26 betroffenen Paritätstests bestanden.
- Die beiden anderen Befunde betreffen eingefrorene Native-C-Auditprofile:
  zwei deklarierte Producer-Lockslots benötigen 8.192 zusätzliche Bytes;
  außerdem stimmen die alten unabhängig geprüften Owner-Hashes nicht mehr.
  Die Profile wurden NICHT durch pauschales Aktualisieren der Pins freigegeben.
  Nachfolgende Nicht-Native-Dateirunden: 748 / 1.539 / 772 bestanden,
  3 / 14 / 7 Skips. Diese Teilrunden sind KEIN grüner Vollsuitennachweis.

## Produktionsumstellung vor dem regulären Updater

23:21 CEST App/Timer gestoppt und vorübergehend deaktiviert; 23:26 Backup
aller 89 Datenbanken verifiziert, keine Bereinigung vorhandener Archive.
23:30 produktive Umstellung vollständig und verlustfrei beendet:
2.246.610.944 → 938.508.288 Bytes, dieselben 112 Snapshots und logischen Bytes
wie in QA. Backup/Status: `/var/lib/betboy-context-verifier/memory-maintenance-8jmzb2v5/`.
Der erste anschließende Updater-Vorcheck benötigte zusätzlich seine eigene
Code-Staging-Reserve und brach vor Codeinstallation ab. Deshalb auch die zweite,
ausschließlich von dieser Reparatur erzeugte QA-Datei verlustfrei komprimiert:
230.812.793 Bytes, vollständiger Rücklese-SHA256 gleich dem bereits geprüften
Root-Seal. 707.687.303 zusätzliche Bytes frei; Produktionsdaten und alle echten
Backups unverändert. Beide QA-Archive bleiben wiederherstellbar erhalten.
Keine erneute produktive Kompaktierung nötig. Der reguläre root-eigene Updater
endete am 14.09. um 23:46:18 CEST erfolgreich auf
`1ec38a9f6f4530f85260ee57877e155a176e2ad6`; GitHub main und lokaler Main waren
exakt gleich. App und sieben Timer aktiv/aktiviert, beide Healthchecks `ok`.
Online- und Stillstandsbackup jeweils mit 89 DBs verifiziert:
`/var/backups/betboy-update/betboy-online-20260914T213653Z-442b60fe6804-372885.zip`
und `betboy-preupdate-20260914T214007Z-442b60fe6804-372885.zip`.
Der zusätzliche Backupdienst endete 23:45:21 ebenfalls erfolgreich.

Echte Browserseite nach frischem Laden geprüft: 0 Console-Fehler, 9 Warnungen,
keine Streamlit-Ausnahme. Desktop 1440 Pixel und Mobil 390 Pixel;
Dokumentbreite bei Mobil exakt 390 Pixel, kein horizontaler Überlauf.
Die Ausgabe zeigte Teildaten/0 Modelle am Tagesende; daraus wird keine neue
Prognosequalität oder vollständig erfolgreiche Datenpipeline abgeleitet.

## Echter Paralleltest und nachgewiesener Folgefehler

Wettfinder 23:46:15–23:55:44, 1.840.050.176 Bytes Dienst-MemoryPeak, kein OOM
oder SQLite-Lock. Exit 1/Teildaten wegen Pending-Tennisprognose 1419:
`ContextIntegrityError`. Der eng begrenzte read-only-Belegvergleich bestätigte
für WTA-Event 183831 einen tatsächlich ausgetauschten Gegner, später auch einen
neuen Termin. Alte Prognose nicht auf das neue Teilnehmerpaar umschreiben.

Tennis-Rebuild: ATP frisch beibehalten, WTA weiterhin HTTPError/Stand 26.07.
Eigentlicher Tageslauf 23:48:45–00:00:17: 691 Sekunden, 117 Spiele, 57 vorbereitete
Prognosen, 25.743 Empfangsbeobachtungen gespeichert. Kein Timeout/OOM;
Dienst-MemoryPeak 1.623.814.144 Bytes. Danach Abbruch bei der Speicherung an
`ValueError: tennis revision cannot change player identity or orientation`.
Die Speicherreparatur beseitigt somit nicht automatisch sämtliche Ablaufprobleme.

Der enge Nachfolgepatch erhält das vollständige Überschreibverbot, verwendet
dafür aber einen eigenen `FixtureIdentityConflict`. `LiveWorker.finish` fängt
ausschließlich diesen Konflikt je Karte ab, meldet ihn strukturiert als
Teildaten und speichert unabhängige weitere Karten. Andere Integritätsfehler
bleiben Fehler. Der CLI-Abschluss berücksichtigt jetzt auch erst während
`finish` entstandene Fehler und bleibt dann Exit 1, statt Erfolg vorzutäuschen.
Regressionen beweisen unveränderte frühere Revisionen, Speicherung des nächsten
unabhängigen Spiels, korrekten Teildaten-Exit und Weiterreichen fremder Fehler.
214 gezielte lokale / 188 Linux-Tests bestanden. Linux ausschließlich im
vorhandenen privaten QA mit synthetischen Daten; keine Pakete installiert.
Zusätzliche breite Tennis-/Snapshot-/Transport-Runde auf dem Nachfolgepatch:
1.872 bestanden, drei Skips, 7.882 nicht ausgewählte Tests; 208,50 s.
Nachweis: `.pytest_tmp/memory-identity-broad.xml`. Dies ersetzt keine
Neuqualifizierung der eingefrorenen Native-C-Auditprofile.

## Verbleibende Nachweise

Den Nachfolgepatch nach den Tests committen, pushen und regulär deployen;
danach echten vollständig abgearbeiteten Tennislauf prüfen. Teildaten wegen
Quellen-/Identitätskonflikten nicht mit gesundem Gesamtbetrieb gleichsetzen.
Der konkrete nachfolgende Hash und Laufstatus stehen im Releasebericht.
Die alten Native-C-Prüfprofile bedürfen einer eigenen Neuqualifizierung;
kein impliziter C2-Semantik- oder empirischer Modell-Pass.

Produktionsbasis bei dieser Fortsetzung: `442b60f`. Isolierte Code- und
synthetische Testkopien: `/tmp/betboy-memory.IzioJU/`. Die vorhandene
Testbibliothek unter `/tmp/betboy-tennis-completion.Jjafxs/test-libs` wurde
wiederverwendet; keine zusätzlichen Pakete im Produktionsvenv installiert.
WTA-Quellenfehler und empirische Verletzungs-/Müdigkeitsaktivierung sind
unabhängige offene Arbeiten, nicht durch diese Speicherreparatur erledigt.
