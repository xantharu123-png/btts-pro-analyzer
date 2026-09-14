# Kontextspeicher-Reparatur – 14. September 2026

## Auftrag und Freigabegrenze

Der Nutzer verlangt die Behebung der redundanten Datenhaltung und des RAM-
Verbrauchs samt Commit, Push und geprüftem VPS-Deployment. Cricket, Quoten,
Einsätze, Modellfreigaben und historische Dateninhalte bleiben unverändert.

Die automatische Aktionsprüfung hat eine neue Kopie der produktiven
`context_models.db` in den privaten QA-Ordner ausdrücklich abgelehnt: Die
frühere Archivfreigabe bezog sich auf Code, nicht auf Laufzeitdatenbanken.
Die ergänzende Zustimmung wurde angefragt und liegt noch nicht vor. Diese
Kopie wurde NICHT erstellt; keine alternative Kopierroute verwendet.
Kein Produktions-Deployment und keine produktive Kompaktierung behaupten.

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

## Noch vor Produktionsfreigabe erforderlich

1. Zustimmung zur echten Kontext-DB-Kopie im selben privaten VPS-QA-Ordner.
2. Begrenzte echte Volumen-/RAM-Prüfung mit
   `scripts/measure_context_memory.py` (1.400 MiB AS, 600 CPU-s), anschließend
   verlustfreie Kompaktierung an dieser Kopie und Deployment-/Restoreprüfung.
3. Erst nach diesem Nachweis Main übernehmen, pushen und regulären Updater
   ausführen. Produktive Umstellung nur mit geprüftem Backup und gestoppten
   Writern. Keine Backups oder fachlichen Historien löschen.
4. Einen echten Tennisabschluss und den überlappenden Wettfinderbetrieb prüfen;
   Softwaretests allein beweisen keinen behobenen Produktions-OOM.

Produktionsbasis bei dieser Fortsetzung: `442b60f`. Isolierte Code- und
synthetische Testkopien: `/tmp/betboy-memory.IzioJU/`. Die vorhandene
Testbibliothek unter `/tmp/betboy-tennis-completion.Jjafxs/test-libs` wurde
wiederverwendet; keine zusätzlichen Pakete im Produktionsvenv installiert.
WTA-Quellenfehler und empirische Verletzungs-/Müdigkeitsaktivierung sind
unabhängige offene Arbeiten, nicht durch diese Speicherreparatur erledigt.
