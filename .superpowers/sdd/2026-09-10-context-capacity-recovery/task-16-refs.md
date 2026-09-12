# Task 16 — C2: vollständige disk-staged Referenzmengen

12. September 2026. Autoraufgabe innerhalb der ausdrücklich angenommenen
C-Spezifikation `08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba`.
Kein Legacy-, Modell-, Quoten-, Produktintegrations-, Git- oder VPS-Eingriff.
Dieser Baustein ist kein B-Prüfnachweis und keine Gesamtfreigabe.

## Gelieferte Schnittstelle

- `create_schema(connection)` erzeugt ausschließlich `v2_ref_blocks`,
  `v2_ref_sets`, `v2_ref_members`, `v2_ref_staging` und den Block-Lookupindex.
- `put_refset(connection, refs_iterable, *, limits=DEFAULT_LIMITS)` nimmt
  unsortierte **eindeutige** lowercase-SHA256-Strings an. Es sortiert normale
  private SQLite-Stagingzeilen auf Platte, ohne Python-Gesamtset/Referenzliste.
  Eine fachliche Union ist bewusst Sache des aufrufenden Owners; Duplikate hier
  werden nicht still entfernt.
- `RefSetDescriptor` ist eine frozen Dataclass mit `format_version`,
  `set_digest`, `canonical_digest`, `reference_count`, `canonical_bytes`,
  `binary_bytes`, `block_count`.
- `iter_refset(connection, descriptor, *, limits=...)` validiert den **gesamten**
  Satz vor dem ersten Wert; jeder Aufruf liefert einen neuen Iterator. Es liest
  anschließend begrenzte Blöcke und prüft die gebundene Transaktionsgeneration.
- `validate_all(connection, *, limits=...)` prüft alle Sätze/Blöcke, vollständige
  Mitgliedschaften sowie fehlende, verwaiste und unvollständige Generationen.

Es ist zwingend eine **exakte** `context_runtime_transaction.TrackedConnection`
zu verwenden. Vor BEGIN muss der Aufrufer `max_page_count` auf höchstens
`min(input_bytes, workspace_bytes) // page_size` begrenzen, `mmap_size=0`
konfigurieren und einen expliziten negativen Cache von höchstens 8192 KiB wählen.
Es wird kein vorhandener Tracecallback ersetzt und kein PRAGMA unter einer
fremden aktiven Transaktion still umgeschrieben. Tennisautor und Root sind über
diesen gemeinsamen Vertrag informiert.

## Form und Vollständigkeit

Jeder Block enthält ausschließlich feste 32-Byte-SHA256-Werte in strikt
aufsteigender, eindeutiger Reihenfolge. Seine Inhaltsadresse bindet Format und
gesamten BLOB. Wiederverwendbare gleiche Blöcke werden gemeinsam gespeichert.
Die geordnete Manifesttabelle bindet jeden Blockindex, Hash, Count und Bytewert;
der Setdigest bindet das vollständige kanonische Manifest einschließlich der
Gesamtmetadaten. Der separat berechnete Arraydigest ist **exakt**
`sha256(canonical_bytes(sorted(references)))` und nicht ein Ersatzformatdigest.

Die Prüfungen unterscheiden INTEGER/REAL/TEXT/BLOB/NULL tatsächlich, prüfen
große fremde Schlüssel-/Metawerte zuerst über SQL-Storage-Typ und Länge und
materialisieren einen BLOB erst nach geprüftem Blocklimit. Gleich gebliebene
Counts bei geänderter Mitgliedschaft, Lücken, zusätzliche/duplizierte Blöcke,
Reihenfolgenänderungen und falsche Versionen sind Fehler. Öffentliche Digests
belegen dabei **Gleichheit, keine Vertrauens- oder HMAC-Berechtigung**.

## Lebensdauer, Budget und Abbruch

Alle APIs verlangen eine bereits aktive Aufrufertransaktion. Schreibaufrufe
verwenden einen eigenen SAVEPOINT und committen nie. Normale Ausnahme- und
Prüflimitfehler rollen ihre eigenen Änderungen zurück. Ein echter SQLite-FULL-
oder I/O-Abbruch kann durch SQLite die **gesamte uncommittete** Transaktion
beenden; das wird nicht durch einen irreführenden Missing-SAVEPOINT-Fehler
verdeckt. Der Owner muss diesen unveröffentlichten Aufbau verwerfen. Bereits
committete/publizierte Daten bleiben unter dem SQLite-Rollbackvertrag erhalten.

Reader verwerfen Write-, Rollback-, Commit+BEGIN-, SQL-COMMIT-, executescript-,
Isolation-, Close- und Factoryänderungen. Das Root-Review fand zusätzlich eine
DDL-Kante: `total_changes`/Transaktionsepoch reichen innerhalb derselben offenen
Transaktion nicht. Deshalb werden nun **main und temp schema_version vor jedem
einzelnen Yield** geprüft; zwei Regressionen verlangen Ablehnung bereits beim
unmittelbar nächsten `next()`, nicht erst am Blockende. Frozen Limits werden an
jeder Grenze erneut geprüft, auch gegen gezieltes `object.__setattr__`.
Das unabhängige C2-Review fand danach einen weiteren P2-Lebensdauerfehler:
Resource-PRAGMAs und nachträglich gefälschte Limits konnten nach dem ersten
Iteratorwert geändert werden. Die ausdrücklich von Root genehmigte Korrektur
bindet nun auch `max_page_count`, `cache_size`, `mmap_size` und die komplette
kopierte Limits-Signatur; `__post_init__` läuft erneut vor jedem einzelnen Yield.
Fünf Regressionen für Refstreams und dieselben fünf für Snapshotstreams verlangen
Ablehnung bereits beim nächsten `next()`. Close direkt am Blockende ist zusätzlich
ein typisierter Integritätsfehler statt eines rohen SQLite-Zugriffsfehlers.
Die unabhängige Folgeprüfung zeigte zusätzlich, dass ein gefälschtes
`limits.__post_init__` die dynamische Instanzprüfung ausschalten konnte. Nach
ausdrücklicher enger Root-Freigabe rufen **alle** C2-Eingangs-/Lebensdauerprüfungen
nun den festen Owner `StorageLimits.__post_init__(limits)` auf. Sechs Regressionen
(Referenz-/Snapshotpfad jeweils vor Put, vor Read und nach erstem Yield) weisen
die Kombination aus falschem Feldwert und überschriebenem Instanzcallback ab.
Die unverändert gebundene vollständige Feldsignatur bleibt zusätzlich erhalten.
Die Leser ändern die Datenbank nicht und
funktionieren auch in einer gehaltenen query-only-Transaktion.

Das Modul misst die **gesamte** private Datenbank (inklusive Staging, Indizes,
Freelist und physischer Größe), ihre WAL/SHM/Journaldateien sowie die aktuelle
4-GiB-Freiplatzreserve. Ein Manifest ist durch maximal 4096 Blockeinträge
begrenzt. Die globale Mehrdatei-/Backup-/Prozessbilanz, native RAM/CPU-Limits und
Publikationszuständigkeit bleiben beim separaten Root-/B-Owner. Einzelne lokale
Checks werden nicht als Nachweis der gesamten 4-/8-GiB-Hülle ausgegeben.

## Tatsächliche lokale Prüfung

Gebündelter Python:
`C:/Users/miros/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.
Pytest aus der bereits vorhandenen BetBoy-venv über explizites PYTHONPATH;
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; eindeutiges neues `--basetemp` im Worktree.

Finaler gemeinsamer Lauf nach beiden Lifecycle-Reviewkorrekturen:
**174 bestanden in 19,33 s**, davon **92 C2-Referenztests und 82 C2b-Snapshottests**,
Prozess Exit 0. Die früheren 83er-/168er-Läufe bezogen sich auf vorausgehende Bytes.

Enthalten sind vollständige kanonische Array-/Manifestvergleiche, Wiederholung,
Blocksharing, leere Menge, SQL-Typkanten, Nachhashen geänderter Mitgliedschaft,
erste-Ausgabe-nach-Gesamtprüfung, Transaktionsgeneration, explizite Admission,
Quotenrollback, SQLite-Hard-FULL, query-only und 100.000 tatsächlich verarbeitete
Referenzen. Die letzte Probe misst mit tracemalloc **Python-Allokationen unter
8 MiB bei 4-KiB-Blöcken**; das ist ausdrücklich kein nativer RSS-/VPS-Nachweis.

Ein erster Pytest-Aufruf scheiterte ausschließlich vor allen Testkörpern an den
ACLs des allgemeinen Windows-pytest-Tempverzeichnisses. Der anschließende Lauf
verwendete einen neuen workspace-eigenen Pfad; keine ACL-Änderung oder Löschung.

Geprüfte Dateien:

- `context_storage_v2/refs.py` SHA256
  `31726af247e0f1b9c4a7e1bdedf233478a758cfc817dda377135aa5c6947c755`
- `tests/test_context_storage_refs.py` SHA256
  `386ee1c4a15666669c63078b3cab316abc81da7b0833abda08b8933aa012ce67`

Offen: unabhängige Bestätigung der letzten C2-Reviewkorrektur, Gesamtintegration, vollständige native
Wachstums-/Ressourcenprobe und alle nachfolgenden C/B-/Deploymentgates.

## Anschließend separat beauftragter Baustein C2b

Root hat den folgenden Vorschlag anschließend als enges C2b ausdrücklich
beauftragt. Umsetzung und exakte Tests/SHA stehen in
`task-17-snapshot-parts.md`; dadurch ist noch keine Produktintegration erfolgt.

`snapshots.py` kann einen begrenzten kanonischen Header **ohne** das bekannte
Top-Level-Feld `observation_refs` sowie dessen `RefSetDescriptor` speichern.
`put_snapshot_parts(...)` müsste zusätzlich den alten Schlüssel, den bereits
gebundenen Rohpayload-SHA256, die Bytezahl und den alten `payload_digest`
verlangen. Ein frischer `iter_snapshot_bytes(...)` rekonstruiert die kanonischen
Bytes in exakt alter Schlüsselreihenfolge und vergleicht streaming sowohl den
Rohhash als auch `sha256({"key":key,"payload":<vollständiger JSON-Payload>})`.
Erst dieser vollständige Vergleich gestattet einen Transportgleichheitsclaim.
Ein explizit begrenzter Legacy-Adapter dient den `_decode_snapshot`-
Differentialfixtures; nicht standardmäßig den großen Historien.

Der Header bekommt eine eigene feste kleine Grenze innerhalb der C-Hülle.
Das ist kein allgemeiner unbeschränkter JSON-Parser: unbekannte/zu große
Altstrukturen bleiben verlustfrei beim transport-only Rohinventar, bis ihr
eigens geprüfter Adapter besteht. Feature-/D2-/Quell-/Modellgültigkeit wird
aus der Bytegleichheit nicht abgeleitet. Root entscheidet den nächsten engen
Schreibbereich nach der laufenden Gesamtintegration.
