# Task 17 — C2b: byteidentische Snapshotteile mit gemeinsamem Referenzsatz

12. September 2026. Separater enger Root-Auftrag nach dem C2-Referenzbaustein
innerhalb der angenommenen C-Spezifikation. Nur neue Snapshotdatei, eigene Tests
und dieser Bericht. Die gemeinsame C2-Lifecycle-Korrektur wurde separat von Root
freigegeben und ist in Task 16 dokumentiert. Kein Legacy-/Modell-/Quoten-/Git-/
SSH-/VPS-Eingriff, keine Migration oder Veröffentlichung.

## Gelieferte API und bewusst begrenzter Claim

`create_schema(connection)` setzt eine vorhandene private C2-Refdatenbank voraus
und erzeugt ausschließlich `v2_snapshot_headers`, `v2_snapshot_parts` und deren
Header-Lookupindex. Alle APIs verwenden die exakte private `TrackedConnection`,
aktive Aufrufertransaktion und dieselbe C2-Resourceadmission. Schreibaufrufe
besitzen einen eigenen SAVEPOINT, keinen Commit.

`put_snapshot_parts(connection, *, key, header_bytes, observation_refs,
expected_raw_payload_sha256, expected_payload_bytes, expected_payload_digest,
expected_observation_count, limits=...)` verlangt:

- Einen kanonischen finite-JSON-Header **ohne** Top-Level-`observation_refs`.
  Seine geschlossene Feldmenge kommt unmittelbar vom unveränderten
  `context_transport._INPUTS | {result}`. Nur `context-worker-snapshot-v1`,
  tatsächliches INTEGER-Schema 1 und exakt diese Feldmenge werden adaptiert.
- Den vollständigen bereits gespeicherten `RefSetDescriptor` für genau diese
  Top-Level-Liste; gleichnamige verschachtelte Felder werden nicht ausgegliedert.
- Alle vollständigen erwarteten Rohpayload-/alten Payload-/Schlüsselidentitäten
  sowie Byte- und Referenzzahl aus dem **separat gebundenen** Quellinventar.

Die Rückgabe `SnapshotPartsDescriptor` bindet Version, Key, Headerdigest/-größe,
den ganzen RefSetDescriptor, Rohpayload-SHA256, Payloadgröße, alten Payloaddigest
und einen vollständigen neuen Deskriptordigest. Gleiche kleine Header können
gemeinsam gespeichert werden. Ein bestehender Schlüssel wird nie überschrieben.

`iter_snapshot_bytes(...)` erzeugt frische begrenzte Byteströme. Vor dem ersten
Chunk werden **alle rekonstruierten Bytes** in alter kanonischer Reihenfolge
geprüft, nicht nur Count/Prefix: sowohl `sha256(raw_payload)` als auch der
unveränderte alte Digest von `{"key":key,"payload":payload}` müssen exakt
passen. Danach wird mit unveränderter Generation erneut gestreamt. Es entsteht
standardmäßig keine vollständige Liste oder Payload-Dictionary.

`materialize_snapshot(..., max_bytes=...)` ist ausschließlich ein **expliziter**
kleiner Vergleichs-/Adapterhelper, ohne Standardwert. Nur dieser Helper ruft
den unveränderten alten `_decode_snapshot` auf.

`validate_all(...)` prüft die intrinsische neue Speicherintegrität, einschließlich
aller gespeicherten Deskriptoren, Header, Refsets und unerreichbarer Header.
Der Root-/B-Owner muss zusätzlich die **gesamte erwartete Snapshot-Schlüsselmenge**
mit dem Quellinventar vergleichen. Ein intrinsisch leerer Store belegt keine
vollständige Migration; Public Hashes belegen keine Quelle, D2-Berechtigung oder
empirische Modellgültigkeit. Hier wird keine Modell-/Approval-/Quellenfunktion
nachgerechnet oder als bestanden markiert.

## Explizite neue Grenzen und erhaltene Altdaten

Der neue Headeradapter akzeptiert maximal **1 MiB**, zusätzlich niemals mehr als
das übergebene kleinere Blocklimit. Das ist eine erklärte neue Adaptergrenze,
kein historischer allgemeiner Einzelwertvertrag. Der optional benutzte
Materialisierungshelper akzeptiert maximal **64 MiB** als ausdrücklich geforderte
Bytegrenze; auch das ist seine neue Helpergrenze, **nicht** das frühere gesamte
64-MiB-Legacy-Memorybudget oder der getrennte Historycache und kein nativer
RAM-Nachweis.

Unbekannte Headerarten, zu große Nichtreferenzheader, zusätzliche/fehlende
Felder und nicht kanonische/nonfinite JSON werden typisiert abgelehnt. Der
übergebene Quellinput wird nicht verändert. Der ursprüngliche vollständige
Rohbestand bleibt beim separaten Inventarowner verlustfrei transport-only,
bis ein ausdrücklich passender Adapter besteht. Ein allgemeiner großer
Legacy-JSON-Parser oder eine echte Quellmigration gehören nicht zu diesem
Baustein und wurden hier nicht behauptet.

Alle Datenbank-/Journal-/Free-Space- und Einzelblockchecks stammen vom C2-Owner.
Der globale Mehrdatei-/Backup-/Rollback-/Prozesshaushalt und die echte native
4-/8-GiB-/RAM-/CPU-Abnahme bleiben beim Root-/B-Owner.

## Reviewhärtung der gemeinsamen Lebensdauer

Vor dem Wiederaufnehmen eines inneren Iterators **und** vor jedem ausgegebenen
Chunk wird dieselbe gebundene Generation erneut geprüft: Tracked-Epoch,
Writes, Fabriken, main-/temp-Schema, Resource-PRAGMAs und ursprüngliche komplette
Limits-Signatur. Dadurch werden Commit+BEGIN, Rollback, executescript, DDL,
Close, Settingsänderungen oder gefälschte frozen Limits nicht erst am Ende eines
großen Blocks entdeckt. Keine PRAGMAs werden still zurückgesetzt oder fremde
Tracecallbacks ersetzt.

Die nachfolgende unabhängige Probe gegen einen gefälschten Instanzcallback wurde
nach konkreter Root-Freigabe ebenfalls geschlossen: Der gemeinsam benutzte
C2-Guard ruft nun stets `StorageLimits.__post_init__(limits)` als **festen
Klassenowner** auf, nicht ein austauschbares `limits.__post_init__`. Vor Put,
vor Read und nach erstem Yield weisen sowohl Referenz- als auch Snapshotpfad
die Kombination aus falschem Limitfeld und überschriebenem Callback ab; die
vollständige ursprünglich kopierte Limits-Signatur bleibt weiter gebunden.

Ein realer SQLite-Hard-FULL kann die uncommittete neue Gesamttransaktion beenden.
Die Regression bestätigt, dass ein **vorher committed** Snapshot vollständig
erhalten bleibt. Der Owner muss einen unvollständigen neuen Aufbau verwerfen,
statt einen Teilstand freizugeben.

## Tatsächlich ausgeführte Tests

Test-first: Der erste gezielte Lauf scheiterte wie erwartet am noch fehlenden
`snapshots`-Modul. Anschließend 60, dann 74 gezielte grüne Snapshotfälle.
Nach der gemeinsamen Ressourcen-Lifecycle-Korrektur:

**174 Tests bestanden in 19,33 s, Exit 0 — 92 Referenztests + 82 Snapshottests.**
Der vorausgehende 168er-Lauf gehörte zu den Bytes vor der festen Ownerkorrektur.

Gebündelter Python über die vorhandenen venv-Pytest-Abhängigkeiten,
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, neuer eindeutiger workspace-eigener
`--basetemp`. Keine Installation, kein ACL-Umbau, kein Serverlauf.

Die Snapshotfälle umfassen:

- Vier echte unveränderte `calculate_context_payload`-/`context_payload_key`-
  und `_decode_snapshot`-Differentials für Tennis-Winner/Serve mit/ohne Effekt;
  unveränderte Rohbytes, Payload-/Keydigests und Legacy-Rückgaben.
- Unicode, Escapes und verschachtelte gleichnamige Felder; leere/eine/viele
  vollständige Referenzen, wiederholbares query-only-Lesen, feste Chunkgrößen,
  identische Headerteilung, keine standardmäßige Legacy-Materialisierung.
- Sämtliche erwarteten Hashes/Counts/Bytetypen, SQL-REAL-/BLOB-/TEXT-Kanten,
  falsche/neue Versionen, gleiche Counts bei anderer Mitgliedschaft, fehlende/
  zusätzliche/unerreichbare Zeilen, fremde Deskriptoren und closed Headerform.
- Savepoint-/Commitverhalten, wirklicher SQLite-Hard-FULL, unverändert erhaltene
  vorherige Committeddaten, Lifecycle-Negative und fünf exakt-next-Resourcefälle.

Die zusätzlichen endlichen Legacy-JSON-Transportfixtures werden ausdrücklich
nicht als fachlich valide Workerprognosen ausgegeben. Ein Testzähler ist kein
Nachweis besserer Wetten, vollständiger C/B-Abnahme oder fertigen Deployments.

## Eingefrorene geprüfte Bytes

- `context_storage_v2/snapshots.py` SHA256
  `9fd555d0555df485e44136e800d290059fc1861bd7a12a189db8774d7aa42c63`
- `tests/test_context_storage_snapshots.py` SHA256
  `fbbb692f63120c924240b04a72812bfdf46e58420e225707f5c88694e954e0a7`
- Gemeinsamer `context_storage_v2/refs.py` SHA256
  `31726af247e0f1b9c4a7e1bdedf233478a758cfc817dda377135aa5c6947c755`
- Gemeinsame Referenztests SHA256
  `386ee1c4a15666669c63078b3cab316abc81da7b0833abda08b8933aa012ce67`

Offen bleiben unabhängiges C2b-Review und Bestätigung der letzten gemeinsamen
Guardkorrektur, bindende Quellinventar-/Snapshotkonvertierung, alle realen
Vollbestands-/Sieben-Tage-Ressourcenproben sowie sämtliche nachfolgenden
B-Nachweis-, Restore-, Regressions- und Deploymentgates.
