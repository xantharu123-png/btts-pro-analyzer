# D4: Kontextgröße und Voraussetzungen eines neuen Recovery-Vertrags

Stand: 10.09.2026. Rein lesende Diagnose durch `worker_failures_20260909` auf dem lokal geprüften Root-Stand `2dd1116b68f3d94e9c24338c6c9dff9b01799221`. Dieser Bericht hält die abgeschlossene Quellenprüfung und die getrennt vom Controller erhobenen Livebefunde fest. Er autorisiert oder implementiert keine Reparatur.

## Ergebnis und unmittelbare Grenze

Die produktive Kontextdatenbank ist bereits größer als die fest eingebaute Grenze sowohl des installierten Updaters als auch des D4-Prüfers. Der nächste reguläre Updateversuch würde an der Größenprüfung des bereits installierten Updaters scheitern, bevor dieser den geprüften Nachfolger installieren könnte. Ein größerer Wert ausschließlich im Zielcommit löst diese Übergangslücke nicht.

Der Controller löst deshalb keinen weiteren Releaseversuch aus. Eine neue Roottool-/Recovery-Route benötigt eine eigene eng begrenzte Prüfung und **explizite Nutzerfreigabe**. Sie ist weder durch diesen Bericht noch durch die historische allgemeine Deploymentfreigabe als bereits verfügbar oder genehmigt zu behandeln.

Eine bloße Anhebung des Caps ist keine dauerhafte Lösung: Der neue Prüfpfad muss den vollständigen Bestand unverändert erhalten, mit wachsender Receipt-Historie skalieren und seine tatsächlich eingehaltenen Ressourcen- und Dateisystemgrenzen belegen. Diese Prüfung muss vor Auswahl und Freigabe eines produktiven Reparaturtargets unabhängig abgeschlossen sein.

## Tatsächlich bekannte produktive Daten

Die folgenden Werte wurden vom Controller getrennt auf dem VPS lesend erhoben und an diesen Reviewer übermittelt. Dieser Teilauftrag hat keine produktive Datenbank geöffnet und keine eigene SSH-, Provider- oder Serveraktion ausgeführt.

| Eigenschaft | Bestätigter Controllerbefund |
| --- | --- |
| Erfolgreich deployter Stand | `2dd1116b68f3d94e9c24338c6c9dff9b01799221` |
| Kontextdatei | `/opt/betboy/app/runtime_state/context_models.db` |
| Dateigröße | **100.671.488 Bytes = 96,0078125 MiB** |
| SQLite-Seiten | **24.578 × 4.096 Bytes** |
| Freelist | **0 Seiten** |
| Header-Journalmodus | Bytes `[1, 1]`, also DELETE |
| Begleitdateien | Keine WAL-/SHM-Dateien; keine Begleiter am erhobenen Stand |
| Dateiidentität/-rechte | `betboy:betboy`, Modus `0640`, `nlink=1` |
| Datenbankverzeichnis | Modus `0750` |
| Artefakte insgesamt | 4; Payloadsumme **2.956.392 Bytes** |
| Darin ATP-/WTA-Tourzustände | 2; zusammen **2.953.017 Bytes**, größter Payload **2.832.588 Bytes** |
| Darin Winner-Originale | 2; zusammen **3.375 Bytes** |
| Snapshots | 2; zusammen **3.065.937 Bytes**, größter Payload **1.572.163 Bytes** |
| B1-Contents | **47.227**; Payloadsumme **50.653.685 Bytes**, größter Payload **1.599 Bytes** |
| B1-Observation-Receipts | **47.227** |
| Manifeste | 2; zusammen **242 Bytes** |

Der Controller ordnet diesen Bestand dem ersten echten Tennisdurchlauf mit 27 Fixtures nach ATP-/WTA-Initialisierung zu. Der Größenbefund ist damit nicht durch riesige Tourtensors oder freie SQLite-Seiten erklärt. Er besteht überwiegend aus vielen tatsächlich gespeicherten B1-Inhalten, Receipts und ihren Indizes.

Der direkte Liveaufruf von `scripts/verify_context_runtime.py` meldete `RuntimeArtifactTrustError`. Wegen DELETE-Header, fehlender Begleiter und Größe über 64 MiB ist hier die Größenprüfung der konkrete erreichbare Abbruch. Das bedeutet nicht, dass eine wechselnde Live-Datenbank künftig direkt als versiegelte Prüfeingabe verwendet werden darf. Der normale geprüfte Weg bleibt eine eigenständige konsistente Online-Stage.

## Exakter Quellenfluss auf 2dd1116

### Bestehendes Backup und Online-Staging

- `scripts/stage_runtime_databases.py:181` — `_stage_database` erzeugt eine neue separate Zieldatei.
- `scripts/stage_runtime_databases.py:217` — tatsächliches SQLite-Onlinebackup, anschließend DELETE-Modus, `quick_check`, Schließen aller Handles und Ausschluss von Begleitdateien.
- `scripts/stage_runtime_databases.py:258` — `stage_databases` verarbeitet die vollständige entdeckte DB-Inventur und bindet deren Dateiidentitäten vor/nach dem Lauf.
- Der Stagehelper hat **kein 64-MiB-Limit für ein Datenbankbild**. Er verkleinert den Bestand nicht durch Retention oder Weglassen historischer Zeilen.
- `scripts/backup_runtime_databases.py:2055` bis zur anschließenden Hashprüfung — exakte vierfeldrige DB-Inventur mit Größen- und Payloadhashvergleich; kein entsprechendes 64-MiB-DB-Limit. Der dort gesonderte 16-MiB-Stage-Manifestdeckel ist keine Datenbankbildgrenze.
- `deploy/update_server.sh:1689` und folgende — der bestehende Gesamtbackup-Verifier materialisiert DB-Mitglieder blockweise und führt SQLite-`quick_check` aus. Das ist keine D4-Freigabe und keine Größenfreigabe des nachfolgenden Kontext-Hooks.

Ein gültiges vollständiges Backup kann folglich existieren, obwohl der nachfolgende D4-Kontextprüfpfad dieselbe DB nicht annimmt. ZIP-Kompression ändert daran nichts: Die Kontextgrenze bezieht sich auf die **unkomprimierte** Membergröße.

### Doppelte feste Grenze

1. `deploy/update_server.sh:1066` definiert im stdlib-only Inlinecode des **installierten** Updaters `MAX_IMAGE = 64 * 1024 * 1024`.
2. `extract_and_seal`, `deploy/update_server.sh:1395`, prüft bei `:1439` die tatsächliche ZIP-Membergröße gegen diesen Wert. Eine größere vorhandene Kontextdatei scheitert vor SQLite-Sealing und vor dem Target-Verifier.
3. Derselbe Hook begrenzt die Memberleseoperation bei `:1441` und den erneuten Read der versiegelten Kopie bei `:1463`.
4. `context_runtime.py:38` definiert unabhängig `MAX_CONTEXT_IMAGE_BYTES = 64 * 1024 * 1024`.
5. `_read_sealed_image`, `context_runtime.py:140`, verwirft bei `:143` die größere Datei über `fstat`, bevor es Header und Image in SQLite lädt.
6. `scripts/verify_context_runtime.py` bietet ausschließlich `--database` und den optionalen Backup-Lagecheck `--backup-root`, keinen Größenoverride. Fehler ergeben CLI-Code 1 und eine stabile Fehlerklasse.

64 MiB entsprechen 67.108.864 Bytes. Der bekannte Livebestand überschreitet diese Grenze um **33.562.624 Bytes**.

### Zeitpunkt und Recoveryfolge

`preflight_context_runtime` wird vor Downtime ausgeführt (`deploy/update_server.sh:3192`). Dieser frühe Schritt prüft Pfad-/Codekonfiguration, Imports und die tatsächliche Deserializefähigkeit anhand einer kleinen internen Testdatenbank. Er prüft **nicht** die komplette Größe und Semantik des echten Bestands.

Der tatsächliche Hauptfluss ab `deploy/update_server.sh:3195` lautet:

```text
Preflight
→ alten Dienst-/Rootdateizustand merken
→ alle Timer stoppen, Worker abwarten, App stoppen
→ Prozessfreiheit, dauerhafte Autostartdeaktivierung
→ bestehende Markergrenze und vollständiges frisches Backup
→ verify_context_runtime_before_update (Zeile 3224)
   → installierte 64-MiB-Membergrenze
   → erst danach Target-D4-Verifier
→ erst bei Erfolg Apppayload anwenden
→ install_trusted_root_files (Zeile 3237)
→ Migration/Prüfungen/Start
```

Damit kann ein neuer Updateversuch erst nach eingetretener Downtime am bekannten Größenmangel abbrechen.

`scripts/manage_challenge_migration_marker.py:279` gibt bei einem bereits gültigen `complete`-Marker diesen unverändert zurück. In diesem Fall kann der vorhandene `recover_update`-Pfad (`deploy/update_server.sh:2890` und folgende) bei dem frühen Kontextfehler alte Code-/Rootdateien und den gemerkten Dienstzustand wiederherstellen, **wenn sämtliche Wiederherstellungsprüfungen gelingen**. Das ist kein garantierter unterbrechungsfreier Fehler und kein erfolgreicher Release.

Bei `in_progress`, bereits begonnener Migration/neuem Appstart oder fehlgeschlagener Recovery bleiben die bestehenden harten Stop-/Disable-Regeln maßgeblich. D4-PASS und Größendiagnose dürfen niemals einen Marker zurücksetzen oder einen Geld-/Datenrollback autorisieren.

## Herkunft des Caps und Grenzen der bisherigen Ressourcentests

Die reine Git-Historienprüfung zeigt:

- `3df419d16b6b53dd7567bb7449d2a6051977c0ce` führte die D4-Imagegrenze beim Wechsel zu einem ausschließlich in-memory geöffneten SQLite-Bild ein. Anlass war der nachgewiesene DELETE→WAL-Race eines früheren Dateipfad-Lesers mit möglicher SHM-Veränderung.
- `7ba4c9746caf75e0dd6ab5881c8b7ed329a7e358` übernahm denselben Zahlenwert in den späteren Trusted-Updater-Hook.

`docs/audits/2026-09-09-d4-kontext-restore.md:90` und `:234` dokumentieren die Grenze ausdrücklich als **Eingabebildgrenze, nicht Gesamt-RAM-Grenze**. Die gelesenen Herkunftsdokumente enthalten keine Herleitung von 64 MiB aus einem realistischen mehrlaufenden Tennis-Receiptbestand. Der dort dokumentierte konkrete Deserialize-Capabilityversuch umfasste 53.248 Bytes.

Die vorhandenen Tests beweisen enge mechanische Eigenschaften, nicht die nötige Produktionskapazität:

- `tests/test_context_runtime_backup.py:838`: kleine gültige DB, Testcap einmal exakt ihre Größe und einmal ein Byte darunter; darüber wird SQLite nicht geöffnet.
- `tests/test_context_update_hook.py:1030`: der Test bestätigt den festen 64-MiB-Wert, setzt ihn dann für die Abbruchprobe auf 100 Bytes herab.
- `tests/test_context_runtime_backup.py:1010`: `MemoryError`/SQLite-Fehler werden im Test gezielt ausgelöst; Handles schließen und Fehler bleiben typisiert.
- Der Hook begrenzt den tatsächlichen Childprozess auf 600 Sekunden und seinen Ausgabekollektor separat auf 610 Sekunden; die Ausgabe ist auf rund 1 MiB begrenzt (`deploy/update_server.sh:1533`). Das ist kein separater RAM-Hardlimit.

Zusätzlich zur Image-Bytearray und SQLite hält `_verify_connection` (`context_runtime.py:533`) die dekodierten A1-Artefakte. `_verify_observations` (`:379`) materialisiert die B1-Contents und Receipts in Python-Dictionaries. Begrenzte Leseblöcke machen diesen gesamten Pfad daher nicht zu einer speicherbeschränkten Streamingprüfung. Eine größere erlaubte Dateigröße allein belegt weder tragfähigen Speicherverbrauch noch Laufzeit bei weiter wachsender Historie.

## Kein vorhandener installierter In-place-Reparaturweg

Der Target-Verifier stammt zwar bereits aus dem vertrauenswürdig erzeugten Zielpayload. `extract_and_seal` und sein `MAX_IMAGE` werden davor jedoch vom aktuell installierten Root-Updater ausgeführt.

`install_trusted_root_files` (`deploy/update_server.sh:2627`) ersetzt den Updater erst beim Hauptaufruf `:3237`, also **nach** der unvermeidlichen alten Größenprüfung. Daraus folgt:

- Ein bloßer App-/D4-Fix im Zielcommit genügt nicht.
- Auch eine normale Commit-A-Updaterbrücke kann diese bestehende DB nicht durch den alten Hook bringen, bevor die Brücke installiert ist.
- Der bestehende Resumeweg durchläuft denselben Hook; er ist keine Größenexception.
- `verify_invocation` (`deploy/update_server.sh:527`) erlaubt exakt ein 40-Hex-Targetargument, keinen dokumentierten Skip-/Override-/Recovery-Only-Mode für dieses Problem.
- Die Legacy-Abwesenheit ist keine Alternative: Der vorhandene kontextfähige Vorgänger und die tatsächlich vorhandene DB müssen gemeinsam nachgewiesen werden. Datei oder Runtimepfad zu entfernen/umzudeuten wäre kein legitimer Diagnosefix.
- Bootstrap ist fresh-host-only und lehnt die existierende venv ab (`deploy/bootstrap_server.sh:910`). Es ist keine Reparaturroute für diesen produktiven Host.
- `deploy/README.md:174` verbietet manuelle Roottoolersetzung außerhalb des beschriebenen Übergangs. Die bei `:203` dokumentierte einmalige HTTP/1.1-Ausnahme darf ausdrücklich **nicht wiederholt oder auf diesen Fehler übertragen** werden.

Es wurde kein weiterer bereits dokumentierter und hier anwendbarer Übergangsmodus gefunden. Das ist eine konkrete Autorisierungs-/Migrationslücke des installierten Pfads, nicht ein Anlass, Prüfungen zu umgehen.

## Minimaler NEUER Recovery-Vertrag: vor Targetwahl erforderlich

Die folgenden Punkte sind **Prüf- und Freigabevoraussetzungen**, keine genehmigte Remediation, ausführbaren Installationsbefehle oder neue Betreiberautorität.

### 1. Dauerhaft tragfähiger Prüfer statt bloßer Capanhebung

- Vollständige unabhängige Prüfung eines streng lesenden, versiegelten und ressourcenbegrenzten Verifiers für die reale B1-Historienverteilung und weiteres Wachstum, bevor ein produktiver Reparaturtarget gewählt wird.
- Der vorhandene Online-Stagevertrag kann weiterhin die konsistente private Ein-DB-Kopie liefern. Das Livefile bleibt niemals ein `immutable=1`-Ersatz für vollständige WAL-Erfassung.
- Ein künftig dateibasierter oder gestreamter Privatkopie-Prüfer wäre eine **neue**, separat nachzuweisende D4-Fähigkeit. Er darf niemals still auf Live-Dateipfade zurückfallen. Root-private Herkunft, Unveränderbarkeit für den Appuser, No-follow/nlink/Owner-/Modegrenzen, Begleiterfreiheit und Vor-/Nachprüfung bleiben erforderlich.
- Real messen und begrenzen: unkomprimierte Eingabe, einzelne Payloadgröße, tatsächlich materialisierter Speicher, Gesamt-RSS, Laufzeit, Ausgabe und benötigter Stage-/Backupplatz. Alle Grenzen müssen Fehlzustände typisiert beenden; kein freier Environmentoverride und kein unbeschränkter Input.
- Vollständige semantische A1/B1/B3-/D2-/Tennisprüfung einschließlich historischer Referenzen und ungeöffneter D2-Labelgrenzen beibehalten. Keine Auswahl nur aktiver Artefakte oder der neuesten Receipts, um den Umfang künstlich zu reduzieren.
- Geschlossener versionierter Ressourcen-/Capabilityvertrag zwischen Root-Hook und Target-Verifier. Bestehende Reportfelder und zwölf Limitkategorien nicht heimlich erweitern: die installierte Ergebnisannahme prüft Keys und Schema exakt.

### 2. Neuer expliziter Roottool-Übergang

- Exakten tatsächlich installierten alten SHA und reguläre root-eigene Dateiidentität frisch prüfen; den neuen überprüften SHA samt vollständigem 40-Hex-Commit und Gitblob unabhängig festlegen.
- Bezugsquelle bleibt das feste vertrauenswürdige Repository mit expliziter Zielidentität, bereinigter Gitumgebung und TLS. Keine Übernahme aus dem appbeschreibbaren Checkout und kein Import von App-/venvcode als root.
- Ausschließlich den begrenzten erlaubten Übergang definieren; genaue Dateiallowlist, bestehender exklusiver Deploylock, Konkurrenz-/Prozess-/Rechteprüfungen, atomare Installation und fsync-Verhalten vorab reviewen.
- Exakte Vorgängerbytes und Metadaten root-privat dauerhaft sichern. Installation, Nachhashprüfung, Fehler an jeder Grenze und Wiederherstellung des **genauen** alten Roottools getrennt testen. Keine Zusicherung, dass alter Code neue Daten verstehen müsse.
- Prüfung, was vor Downtime sicher möglich ist, und Wiederprüfung nach Quiesce ausdrücklich trennen. Ein bekannter Kapazitätsmangel darf nicht erst beim Appstopp entdeckt werden.
- Diese Route braucht vor jeder produktiven Ausführung **explizite Nutzerfreigabe**. Die historische HTTP-Hilfsbrücke, ein erneutes Bootstrap oder eine beliebige Rootkopie sind keine wiederverwendbare Erlaubnis.

### 3. Daten- und Wiederherstellungsnachweis

- Die gesamten aktuell bekannten **100.671.488 Bytes logisch vollständig erhalten**: alle 47.227 Contents und Receipts, Artefakte, beide Tourzustände, Originale, Snapshots, Manifeste und ihre Referenzen. Physische Byteänderung ausschließlich durch bereits genau qualifiziertes separates Online-Sealing; logische Identitäten unverändert.
- Vor produktiver Mutation ein **frisches vollständiges 88-DB-Backup** des dann aktuellen Inventars samt passendem HMAC-Schlüssel und Marker erstellen und unabhängig wiederherstellungsprüfen. Ein älteres Backup vor Tennisinitialisierung reicht nicht. Diese Zeile ist eine erforderliche Recoveryvoraussetzung, kein durch diesen Reviewer frisch ausgeführter 88-DB-Nachweis.
- Inventar-/Member-/Hash-/CRC-/SQLite-Prüfung und tatsächlichen Restore in einen neuen isolierten Zielbereich belegen; der Appuser erhält niemals das gesamte Archiv mit den Integrity-Mitgliedern.
- Aktuelle und historische A1/B1/B3-Identitäten sowie Prognosen vor/nach der getrennten Restoreprüfung vergleichen. Keine Nachberechnung als Ersatz für erhaltene Snapshotbytes.
- Keine automatische Retention, Löschung, Trunkierung, Neuinitialisierung, Einzel-DB-Ersetzung, Markt-/Quotenänderung oder Modellfreigabe. Kein Geld-/Settlement-/Markerrollback aufgrund eines Kontextprüfergebnisses.
- Tests müssen echte große gültige Bestände, Grenzen darunter/darüber, weitere Receiptgenerationen, unterbrochene Reads, WAL-/Journalwechsel, Links/Ersetzung, RSS-/Timeoutabbrüche und genaue Installed-old→reviewed-new→Rollbackfolgen enthalten. Ein runtergepatchtes Testcap allein genügt nicht.

## Eingefrorene gelesene lokale Bytes

Rohe SHA256 auf dem lokal geprüften Rootstand; keine Aussage über neue, ungeprüfte Fixbytes:

| Datei | SHA256 |
| --- | --- |
| `context_runtime.py` | `974917709b8e292b9621c6bef17112794a0724c4885f04f97052bde3799eab3e` |
| `scripts/verify_context_runtime.py` | `c1dab7debf1d5e50df640d99f7de6871468cf3db8a80972aeef6e2d58045f410` |
| `deploy/update_server.sh` | `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f` |
| `scripts/stage_runtime_databases.py` | `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` |
| `scripts/backup_runtime_databases.py` | `1bf9228efd1de9adc0786c0788ed1759d0154f9a7448091c29eba13f598742e7` |
| `tests/test_context_runtime_backup.py` | `71dc37951bed4e6fc576e842829f7b0af08b692243bd6c353423237c9cddef62` |
| `tests/test_context_update_hook.py` | `cf711ac8438eef369500014298ad6c7c14ae2c5c0ae3b6ada526d9299b70e501` |

Der Stagehelper hatte bereits die bekannte Git-M-Markierung, blieb aber roh exakt auf dem geschützten `1441158c…`-Pin. Diese Markierung und sämtliche Bytes wurden nicht angefasst.

## Durchgeführter Umfang und offene Freigabe

Ausgeführt wurden ausschließlich lokale Quell-/Audit-/Git-Historien-/Hashlesevorgänge; keine neue Testsuite und kein eigener Serverzugriff. Die genannten Testfälle wurden gelesen, nicht in diesem Diagnoseauftrag neu ausgeführt. Zwei Windows-rg-Aufrufe hatten unpassende Pfadglobs; die maßgeblichen konkreten Dateien wurden anschließend gezielt gelesen. Eine zu breite Suchausgabe wurde nicht als vollständiger Größen-/Lastnachweis verwendet.

Dieser anschließend ausdrücklich angeforderte Bericht ist die einzige neue Datei. Keine Produktquellen, Testquellen, Git-Referenzen, Dienste, Backups, Datenbanken oder Grenzwerte wurden verändert. Die P5b-A0-Quelle auf `ecff029f3c8b0601495547b60ba3941c41cf38ac` und alle früheren Originalproben bleiben eingefroren.

**Offen:** unabhängig qualifizierter skalierbarer Prüfer, exakter neuer Recovery-/Roottool-Vertrag, explizite Nutzerfreigabe und erst danach kontrollierte produktive Umsetzung. Keine davon wird durch diesen Diagnosebericht als erledigt ausgegeben.
