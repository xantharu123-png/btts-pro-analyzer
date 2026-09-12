# Task 17 — unabhängiges C2b-Snapshotreview

12. September 2026. Enges, unabhängiges read-only Produktreview des neuen
Snapshottransports. Die C-Freigabe wurde gegen den Umsetzungsplan geprüft:
Das dort dokumentierte Nutzer-„ja“ gilt für Spezifikation
`08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba`.
Der unveränderte frühere Entscheidungsstatus im Spezifikationstext hebt die
im Umsetzungsplan dokumentierte Freigabe nicht auf.

## Aktueller Reviewabschluss nach Rootkorrektur

**Der unten dokumentierte P1-Befund ist an den abschließend gegengeprüften
Produkthashes geschlossen. 43 unveränderte unabhängige Gegenproben bestehen;
keine weiteren offenen Findings innerhalb dieses engen C2b-Transportreviews.**
Die vollständigen neuen Hashes, Wiederholung und Allokationsmessungen stehen im
abschließenden Abschnitt „Nachprüfung der Rootkorrektur“. Keine allgemeine C-/B-,
Quellcoverage-, Ressourcenprofil- oder Deploymentfreigabe.

## Historisches Ergebnis vor der Rootkorrektur

**Ein offener P1-Befund zur begrenzten Metadatenmaterialisierung. C2b ist an
den unten benannten Bytes deshalb nicht unabhängig abgeschlossen.**

Die vollständige `snapshots.py`, die vollständigen Snapshottests, die benötigten
gemeinsamen Refowner-/Lifecycle-/Ressourcenschnittstellen und die unveränderten
Owner für kanonische JSON-/Snapshotbytes wurden gelesen. Zusätzlich wurden
separate echte Laufzeitgegenproben erstellt; Produktdateien und bestehende
Owner-Tests wurden nicht geändert.

### P1 — SQL-TEXT-Längenschutz lässt große NUL-Suffixe vor der Materialisierung zu

Fundstellen:

- `context_storage_v2/snapshots.py:98-107`, besonders Zeile 105;
  anschließend Deskriptorlesen in Zeile 203 und Prüfung in Zeile 271.
- Gemeinsamer Fehler in `context_storage_v2/refs.py:210-237`, besonders
  die TEXT-Prädikate in Zeilen 215, 220-221, 227-228 und 233.

Die SQL-Vorprüfung verwendet `length(text_column)!=64` beziehungsweise `!=32`
als Schutz vor übergroßen Python-Werten. SQLite zählt bei TEXT mit eingebettetem
NUL jedoch nur bis zu diesem NUL. Ein Feld aus 64 ASCII-Zeichen, NUL und einem
beliebig langen Suffix besteht daher diese Prüfung. Die gespeicherte Zeile wird
danach vollständig in Python geladen; erst der folgende SHA256-Syntaxcheck
weist sie zurück.

Konkrete, wiederholte Gegenprobe mit den unveränderten Ownern:

1. Einen gültigen echten Workerpayload adaptieren.
2. Das gespeicherte `raw_payload_sha256` durch
   `"f" * 64 + "\x00" + "x" * (20 * 1024**2)` ersetzen.
3. `next(iter_snapshot_bytes(..., chunk_bytes=1))` ausführen.
4. Der Leser wirft zwar `StorageIntegrityError` und gibt kein Payloadbyte aus,
   erreicht aber zuvor **20.980.001 zusätzlich getracete Pythonbytes**.
   Der übergroße Inhalt ist ein eigentlich auf 64 Zeichen begrenztes
   Metadatenfeld, kein zugelassener Header oder Verarbeitungsblock.

Der gemeinsame Refpfad zeigt denselben Effekt bei
`v2_ref_sets.canonical_digest`: **20.978.086 getracete Pythonbytes** vor der
Ablehnung durch `iter_refset`. Acht weitere kleine SQL-Formgegenproben zeigen
den fehlenden Vorabfehler an Snapshot-Key-/Digestfeldern sowie Refset-, Block-,
Manifest- und Stagingfeldern. Für 64-Zeichen-Präfix + NUL + `extra` lauten die
gemessenen SQL-Längen `length(TEXT)=64`, `length(CAST(TEXT AS BLOB))=70`.

Das ist **kein Nachweis akzeptierter verfälschter Payloads** und kein behaupteter
nativer 1-GiB-RSS-Verstoß. Es ist eine reproduzierte Umgehung des ausdrücklich
vor der Materialisierung vorgesehenen Einzelwertschutzes: die Pythonallokation
skaliert mit dem unzulässigen Suffix statt mit den festen Metadatenlängen.
Damit ist der begrenzte Arbeitsweg für beschädigte Daten nicht belegt.

Erforderliche Korrektur beim jeweiligen Owner: SQL-seitig eine tatsächlich
begrenzende kodierte Längen-/NUL-Prüfung für sämtliche festen TEXT-Identitäten
vor dem ersten SELECT dieser Werte in Python. Bei einer exakten BLOB-Bytezahl
die zugelassene SQLite-Zeichenkodierung berücksichtigen oder explizit binden.
Danach diese negativen Proben und beide vollständigen Owner-Suites erneut an
den neuen Hashes ausführen. Keine bloße Erweiterung von Pythonlimits oder
Verschiebung der Prüfung hinter `_from_row`.

## Weitere unabhängig bestätigte enge Eigenschaften

Die **24 übrigen unabhängigen Fälle** bestehen:

- Vier reale `calculate_context_payload`-Varianten für Tennis-Winner und
  Tennis-Serve, jeweils mit/ohne Effekt; je sieben vollständige Referenzen in
  vier physischen Refblöcken. Sämtliche alten Rohbytes und Payload-/Keydigests
  sowie `_decode_snapshot`-Rückgaben bleiben exakt. Stückelungen mit 1, 67 und
  4096 Bytes rekonstruieren denselben vollständigen Wert.
- Fehlender letzter Block, zusätzlicher Block, vertauschte gleich große
  Blöcke und falsche Refversion schlagen vor dem ersten Snapshotbyte fehl.
  Unvollständiges Staging und verwaiste Blöcke schlagen in `validate_all` fehl.
- Ein vollständig selbstkonsistenter anderer Refset mit gleicher Anzahl,
  neuem Snapshot-Deskriptordigest und unveränderten Original-Payloadidentitäten
  wird vor dem ersten Byte zurückgewiesen. Ein bloßer Countvergleich genügt
  dem Reader somit nicht.
- SQL-COMMIT/BEGIN, Isolation-Level-Wechsel, geänderte Textfabrik und
  zurückgerollte Savepointschreibversuche invalidieren den laufenden Reader.
- Der feste `StorageLimits.__post_init__(limits)`-Klassenowner weist die
  Kombination aus gefälschtem Blocklimit und überschriebenem
  Instanz-`__post_init__` vor Put, vor Read und nach dem ersten Chunk zurück.
  Die zuletzt angeforderte gemeinsame Guardkorrektur ist damit unabhängig
  für diese drei Grenzen bestätigt.
- Ein tatsächlicher SQLite-Hard-FULL (`sqlite_errorcode == SQLITE_FULL`,
  nicht Monkeypatch) erzeugt `StorageLimitError` mit der SQLite-Ursache.
  Der vorher committete Snapshot bleibt vollständig lesbar; kein neuer
  Snapshotteil wird freigegeben. Ein von SQLite beendeter uncommitteter Aufbau
  ist weiterhin durch den Aufrufer zu verwerfen.
- Die explizite optionale Materialisierung weist falsche Typen, nichtpositive
  Werte und mehr als 64 MiB ab. Diese 64 MiB sind nur die neue Helpergrenze;
  sie werden nicht zum historischen produktweiten Einzelwertvertrag erklärt.

Der Standardreader baut keine komplette Payloadliste oder komplette Refmenge
in Python. Der 1-MiB-Headeradapter ist ausdrücklich eng; unbekannte oder größere
Altstrukturen benötigen den separaten verlustfreien Inventarpfad/Adapter.
Diese bewusste Komponentengrenze ist kein weiterer Befund.

## Ausführung und Artefakte

Separates Reviewmodul:
`.pytest_tmp/test_c2b_independent_review_20260912_1.py`
SHA256 `bc1edb4a1835a4659c18d649f52aaa3c26191dabc5ff52362a1fc960b4de6409`.

Letzter vollständiger unabhängiger Lauf:
**34 Fälle, 24 bestanden, 10 fehlgeschlagene Reproduktionen desselben Befunds,
0 sonstige Fehler, 4,111 s, Exit 1.**

JUnit: `.pytest_tmp/c2b-independent-run-20260912-2.xml`.
Einmaliger neuer Basetemp: `.pytest_tmp/c2b-independent-run-20260912-2`.
Der erste Lauf hatte 24 bestandene und fünf fehlgeschlagene Snapshotproben;
der zweite ergänzt die fünf Refowner-Reproduktionen. Beide Basetemps und
JUnitpfade waren vor der Ausführung nicht vorhanden und wurden nicht bereinigt
oder wiederverwendet.

Runtime: gebündelter Python
`C:/Users/miros/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`,
`PYTHONPATH=C:/Projekt/BetBoy/betboy-app/.venv/Lib/site-packages`,
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTHONDONTWRITEBYTECODE=1`,
`-p no:cacheprovider`, im zweiten Lauf `-o junit_family=xunit1`.
Die gemeldeten 174 kombinierten Ownerfälle wurden hier nicht als eigener Lauf
ausgegeben; Root besitzt deren erneute Integration und vollständige Suite.

## Exakt geprüfte und am Reviewende erneut bestätigte Hashes

- `context_storage_v2/snapshots.py`:
  `9fd555d0555df485e44136e800d290059fc1861bd7a12a189db8774d7aa42c63`
- `context_storage_v2/refs.py`:
  `31726af247e0f1b9c4a7e1bdedf233478a758cfc817dda377135aa5c6947c755`
- `tests/test_context_storage_snapshots.py`:
  `fbbb692f63120c924240b04a72812bfdf46e58420e225707f5c88694e954e0a7`
- `tests/test_context_storage_refs.py`:
  `386ee1c4a15666669c63078b3cab316abc81da7b0833abda08b8933aa012ce67`

## Nicht behauptet

Keine vollständige Quell-/Snapshot-Schlüssel-Coverage, keine externe Quellen-
oder D2-/Modellprüfung, keine HMAC-/Publisherberechtigung und keine allgemeine
C-/B-Abnahme. Der separate Quelladapterowner muss die ganze erwartete
Schlüsselmenge an sein gebundenes Inventar anschließen. Ein intrinsisch leerer
oder zusätzlich selbstkonsistenter Store beweist für sich keine Migration.
Public Hashes werden nicht zu Authority hochgestuft.

Keine native VPS-/4-/8-GiB-/RSS-/CPU-Abnahme, keine vollständigen
Sieben-Tage-Bestände, kein Backup-/Restore-/Vorwärtsreparaturnachweis und kein
Rollout. Keine Git-, SSH- oder Deploymentaktion. Die Produktbytes und bestehenden
Owner-Tests blieben durch diesen Reviewer unverändert.

## Ergänzende Kodierungskontrolle vor der Rootkorrektur

Das erste unabhängige 34-Fälle-Modul bleibt unverändert. Zusätzlich prüft
`.pytest_tmp/test_c2b_independent_encodings_20260912_1.py`
(SHA256 `80e94fc08dd781d39fb12cd822e1fa031db41bf6136d5378550e08f99d7b4579`)
alle drei tatsächlich angelegten SQLite-Datenbankkodierungen UTF-8, UTF-16le
und UTF-16be. An denselben ursprünglichen eingefrorenen Produkthashes bleiben
die drei echten Serve-/Effektpayloads byteidentisch rekonstruierbar.
Die sechs NUL-Formproben für Snapshot- und Refowner schlagen erwartungsgemäß
als fehlende Zurückweisung fehl: **9 Fälle, 3 bestanden, 6 fehlgeschlagen,
0 sonstige Fehler, 1,254 s**, JUnit
`.pytest_tmp/c2b-encodings-run-20260912-1.xml` und eigener gleichnamiger
Basetemp ohne `.xml`.

Root hatte den Befund anerkannt und eine kodierungsbewusste SQL-Oktettgrenze
für beide Owner angekündigt. Diese Absicht wurde nicht als Fixnachweis gezählt;
die tatsächliche nachfolgende Wiederholung ist separat unten dokumentiert.

## Nachprüfung der Rootkorrektur — P1 geschlossen

12. September 2026. Root übergab anschließend diese stabilen Produktidentitäten:

- `context_storage_v2/refs.py`:
  `e80492be96ea0aacd5bb2038018c90bf8201d3e4a616d2574c456d5f9899cb2b`
- `context_storage_v2/snapshots.py`:
  `75bfe759505d7b9a0719844ab397f2a86f0d05cf059d4a93a261f6a961539909`

Beide Hashes wurden vor und nach der unabhängigen Wiederholung tatsächlich
bestätigt. Der neue gemeinsame `_text_width` bindet die erlaubten
SQLite-Kodierungen an 1 beziehungsweise 2 Bytes pro erwarteten ASCII-Zeichen.
Die SQL-Formgrenzen prüfen zusätzlich zu `length` auch `octet_length` für alle
betroffenen festen TEXT-Identitäten. Der Reader lädt den NUL-Suffix dadurch
nicht mehr in Python. UTF-16 wird nicht pauschal verboten.

Die **beiden ursprünglichen Reviewmodule blieben byteidentisch**:
`bc1edb4a1835a4659c18d649f52aaa3c26191dabc5ff52362a1fc960b4de6409`
und `80e94fc08dd781d39fb12cd822e1fa031db41bf6136d5378550e08f99d7b4579`.
Gemeinsam mit frischem, vorher nicht existierendem Basetemp ausgeführt:
**43 Tests bestanden, 0 Fehler, 4,385 s, Exit 0**.

JUnit: `.pytest_tmp/c2b-independent-fixed-run-20260912-1.xml`.
Basetemp: `.pytest_tmp/c2b-independent-fixed-run-20260912-1`.
Runtime und isolierte Pytest-Konfiguration wie oben, einschließlich
`-o junit_family=xunit1`. Keine Installation oder Wiederverwendung eines
vorhandenen Basetemps.

Die exakt gleichen 20-MiB-Negativproben messen nun:

- Snapshotreader: **9.092 getracete Pythonbytes**, vorher 20.980.001.
- Refreader: **7.078 getracete Pythonbytes**, vorher 20.978.086.

Beide bleiben bei typisierter Zurückweisung vor dem ersten Wert/Byte.
Alle positiven echten Worker-Roundtrips und sechs NUL-Formgegenproben unter
UTF-8, UTF-16le und UTF-16be bestehen. Das ist begrenzte lokale
Pythonallokationsevidenz, keine native RSS-/VPS-Abnahme.

Zusätzlich wurde der im älteren Task-16-Bericht noch offene
Instanzcallback-Limitsbefund auf Rootauftrag direkt am endgültigen C2-Owner
gegengeprüft: **vier unabhängige Fälle bestanden in 0,818 s, Exit 0**.
Vor Put, vor Read, nach erstem Yield und in `validate_all` führt die exakte
Kombination aus `block_bytes=2**30` und überschriebenem Instanz-`__post_init__`
zu `StorageLimitError`, ohne vorhandene Refdaten oder die Aufrufertransaktion
zu verändern. Der feste Klassenowner wird nicht durch den Instanzcallback
ersetzt. Der genaue direkte Nachweis ist in
`task-16-refs-independent-review.md` ergänzt.

Diese Nachprüfung schließt nur die konkret reproduzierten C2/C2b-Reviewbefunde
an den genannten Produkthashes. Die inzwischen vom Root erweiterten
dauerhaften Ownerregressionen und die integrierte Vollsuite gehören zu dessen
gesondertem Nachweis; sie werden hier nicht als eigene Läufe ausgegeben.
