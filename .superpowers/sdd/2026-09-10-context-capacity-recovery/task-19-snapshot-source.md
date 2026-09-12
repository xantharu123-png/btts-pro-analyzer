# Task 19 — vollständiger Quelladapter für Snapshot-Teile

Stand: 2026-09-12. Lokaler, transportbezogener Implementierungsstand; kein
Produkt-/Modell-/B-/VPS-Freigabenachweis. Die Nutzerfreigabe von Entscheidung C
(`ja`) ist der Ausführungskontext; die ältere Nichtfreigabe-Formulierung der
Entscheidungsvorlage wurde dabei nicht als neue Sperre interpretiert.

## Enge Zuständigkeit und API

Neu: `context_storage_v2/snapshot_source.py` und
`tests/test_context_storage_snapshot_source.py`. Keine Änderung an den alten
Source-/Snapshot-/Modellbesitzern; keine eigenen Änderungen an den bestehenden
C2-Refs-/Snapshot-Teile-Modulen. Keine Git-, SSH-, Produktions- oder
Publikationsoperation.

`adapt_source_snapshots(source, output, expected_inventory: RawInventory, *, limits)`
liefert einen unveränderlichen `CoverageDescriptor`.
`validate_source_coverage(source, output, descriptor, *, limits)` prüft vollständig
neu und verändert die Verbindung nicht.

Der Aufrufer hält die exakte, unveränderte read-only `TrackedConnection` samt
Lesetransaktion und eine gesonderte private C2-Ausgabeverbindung samt Transaktion.
Refs-/Snapshot-Schemas müssen bereits existieren; Snapshot-Parts/-Header und ein
eventuell früheres Source-Ledger werden nicht als fortsetzbarer eigener Aufbau
interpretiert. Ein nicht frischer Zielstand wird ausdrücklich abgelehnt.

## Vollständigkeit und Bytevertrag

- Vor Ausgabe wird das komplette `inventory_raw` frisch ermittelt und mit dem
  erwarteten vollständigen Inventar verglichen: alle Tabellen, Typen, Schlüssel,
  Werte und Bytes, nicht nur Snapshot-Zahlen oder ausgewählte Touren.
- Jede wirkliche Snapshot-Zeile wird in der originalen logischen SQL-Reihenfolge
  abgearbeitet. Ihre drei Felder erhalten dieselbe getypte Framing-Folge wie im
  Inventar; der vollständige Tabellen-Digest einschließlich Count wird exakt
  gegen das Inventar geprüft. UTF-8, UTF-16le und UTF-16be sind abgedeckt.
- Jeder Payload läuft über `blobopen(..., readonly=True)`, auch kleine, leere
  oder nicht adaptierte Werte. Der Adapter baut weder eine vollständige
  Payloadkopie noch eine vollständige Referenzliste auf.
- Der schmale lexikalische Scanner erkennt ausschließlich die literale
  Top-Level-Liste `observation_refs`. Referenzen sind exakt 64 kleingeschriebene
  Hexzeichen, strikt aufsteigend und duplikatfrei. String-Escapes und verschachtelte
  Werte werden beim Abtrennen nicht als neue Referenzliste missverstanden.
- Der übrige Header ist höchstens 1 MiB und höchstens ein C-Block groß. Seine
  JSON-/Finite-/Kanonikprüfung bleibt beim bestehenden Snapshot-Header-Besitzer;
  für die kleine Kind-Erkennung wird ebenfalls dessen vorhandener kanonischer
  Decoder verwendet. Es wurde kein allgemeiner JSON-Decoder ergänzt.
- Für bekannte adaptierte Zeilen müssen vollständiger roher Payload-SHA,
  Bytezahl und bestehender Key-/Payload-Digest zur bytegenauen C2b-Rekonstruktion
  passen. Erkannte In-envelope-Kanonik-, Hash-, Mitgliedschafts- oder
  Versionsfehler brechen den gesamten Aufbau ab.

Die eigenen Tabellen heißen `v2_snap_source_rows` und
`v2_snap_source_manifest`. Das komplette Ledger bindet jede Quellzeile samt
getyptem Raw-Key-Digest, getyptem Payload-Digest-Feld-Digest, Raw-Row-Digest,
vollständigem Raw-Payload-SHA/Bytezahl und Adaptionsstatus. Große oder
NUL-enthaltende Rohschlüssel werden nicht als große Python-Strings geladen.
Die finale Prüfung bindet zusätzlich die exakte gesamte Output-Parts-Keymenge
und prüft jeden bekannten Parts-Satz intrinsisch. Selbst intrinsisch valide
zusätzliche oder gleichzählige fremde Parts reichen nicht als Coverage.

## Raw-only und Transaktionsgrenzen

Explizite interne Raw-only-Gründe:

- `unknown-header`: keine bekannte Header-Art;
- `header-limit`: Nichtreferenzteil benötigt einen getrennt geprüften Adapter;
- `invalid-key`: Rohschlüssel ist keine exakte bekannte lowercase64-Identität;
- `invalid-payload-digest`: Roh-Digestfeld ist keine exakte bekannte Identität.

Diese Zeilen behalten ihren vollständigen Rohhash und ihre Rohcoverage. Sie
werden nicht zu validierten C2b-Snapshots umbenannt und nicht ausgelassen. Ihre
originale Rohquelle bleibt notwendig. Der Validierer liest und klassifiziert
auch diese Zeilen erneut; gespeicherte Raw-only-Gründe sind kein Freibrief.

Der Gesamtaufbau liegt in einem äußeren Savepoint. Jede einzelne nicht
adaptierbare Zeile rollt zuvor erzeugte Referenzteile separat zurück. Alle
übrigen Fehler rollen sämtliche Änderungen dieses Aufbaus zurück, ohne Commit.
Source-Commit/Rollback/Script, Datenänderung sowie Main-/Temp-DDL werden auch
zwischen Inventar und Payload-Lesen erkannt. Entsprechende Output-Wechsel
werden nicht als fortsetzbare Generation akzeptiert. Ein fremder expliziter
Caller-Commit kann technisch nicht nachträglich rückgängig gemacht werden;
der Adapter liefert in diesem Fall niemals einen erfolgreichen Descriptor.

## Frische Testevidenz

Runtime: gebündeltes Python unter
`C:/Users/miros/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`,
`-B -m pytest`, `PYTHONPATH=C:/Projekt/BetBoy/betboy-app/.venv/Lib/site-packages`,
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. Jeder Lauf nutzte einen zuvor nicht
existierenden Workspace-`--basetemp` und eine eigene JUnit-Datei; keine alten
QA-Verzeichnisse wurden dafür gelöscht oder wiederverwendet.

- Eigene vollständige Suite: **83/83 bestanden**, Pytest-Wanddauer **16,78 s**.
  Evidenz: `qa19-33dd1a28d62843f78c88fc8018fffc3e/results.xml`.
- Gemeinsame Suite `test_context_storage_refs.py`,
  `test_context_storage_snapshots.py`, `test_context_storage_inventory.py`,
  `test_context_storage_snapshot_source.py`: **315/315 bestanden**, **35,81 s**.
  Evidenz: `qa19-4721199c026e41789091974d977b5a74/results.xml`.
- Im gemeinsamen Lauf lag der Python-Allocator-Peak (`tracemalloc`) bei
  **352.801 Bytes** für 1.000 Referenzen und **428.699 Bytes** für 12.000
  Referenzen, mit 64-KiB-Blöcken. Beide Messwerte sind als JUnit-Properties
  gespeichert. Die Referenzarrays sind vollständig, nicht nur Stichproben.

Mit dem echten Legacy-`compute_once`-Owner erzeugte synthetische Vertragsfixtures
sind mit und ohne Effekt für die beiden Tennis-Familien geprüft. Zusätzliche
Fälle decken leere/fehlende optionale
Tabellen, UTF-16, Unicode/Escapes/Nesting, fehlende/zusätzliche/gleichzählige
fremde Quellen, physische große/NUL-Schlüssel, kaputte bekannte Referenzarrays,
Batch-Rollback, fremde valide Output-Parts, Metadaten-NUL-Suffixe, SQL-Funktions-
Overrides, Schema-/Transaktionswechsel und wiederholbare read-only-Prüfung ab.

Vorläufe, nicht als Produkt-PASS gezählt: Der erste Runner scheiterte an einem
noch fehlenden Elternverzeichnis von `--basetemp`; danach wurde dieses eigene
Elternverzeichnis explizit angelegt und ein neuer Basetemp verwendet. Ein
weiterer Vorlauf hatte 9 bestandene Fälle und einen Fixturefehler: Der alte
semantische Key-Owner war erst nach absichtlich synthetischem Austausch der
Referenzmenge aufgerufen worden. Die Fixture bindet ihren echten Ausgangs-Key
nun vor dieser rein transportbezogenen Veränderung. Kein Produktgate und keine
Altvalidierung wurde dafür gelockert.

## Festgehaltener Byte-Stand für unabhängiges Review

SHA-256:

- `context_storage_v2/snapshot_source.py`:
  `f080d605dbbaf45baae197f9f948539d8ff832a2b294327cdc845d4d6df31753`
- `tests/test_context_storage_snapshot_source.py`:
  `67662d8b7965620d18ef6b6a9e30fb006314b345b377805990da5f9c48379f34`
- Mitgeprüfter Ref-Owner: `e80492be96ea0aacd5bb2038018c90bf8201d3e4a616d2574c456d5f9899cb2b`
- Mitgeprüfter Snapshot-Parts-Owner: `75bfe759505d7b9a0719844ab397f2a86f0d05cf059d4a93a261f6a961539909`
- Mitgeprüfter Raw-Inventar-Owner: `7e099cd9ed5e5b336519a23cc891e85c2136dda9fa6324c6f433f61bb37e967b`

## Nicht bewiesen und nächster Schritt

Die Allocator-Probe ist kein nativer RSS-, AS-, CPU-, Platten- oder kompletter
C6-Sieben-Tage-Nachweis. Globale Mehrdatei-Ressourcenbilanz, private Kopier-
Integration, ursprüngliche Quellenautorität, D2, B-HMAC und Publikationsschutz
bleiben beim jeweiligen Besitzer. Dieser lokale Transportbefund validiert kein
Wettmodell und keine Einsatz-/Quotenentscheidung. Nächster Schritt ist das
unabhängige Review genau dieses Byte-Stands und die Root-eigene Integration.
