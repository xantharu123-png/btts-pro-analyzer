# Tour-Artefakt Backup/Restore: Linux-QA-Preflight

Stand: 2026-09-08. Eigenständige read-only Vorbereitung im Kontextmodell-Worktree. Gelesen: kompletter Task-19/D4-Brief, komplette A1/A3-Berichte einschließlich Reviewrunden, vollständige freigegebene Spezifikation sowie die unten genannten tatsächlichen Helper-/Testseams.

## Ergebnis und Grenze

Der unveränderte vorhandene SQLite-Backup-Pfad kann `runtime_state/context_models.db` mit echten ATP-/WTA-Artefakten erfassen, versiegelt stagen, archivieren und in eine neue isolierte Kopie wiederherstellen. Für diesen Nachweis ist keine Helperänderung, kein privilegierter Installer und keine neue Architektur nötig.

Dies ist **ein ausführungsbereiter Preflight, noch kein ausgeführter Linux-Nachweis**. In dieser Teilaufgabe wurden keine Tests, Tourbuilds, Backups, Restores, Git-/Netz-/Provider-/VPS-Aktionen oder Unteragenten ausgeführt. Nur dieser Bericht wurde geschrieben. Der Controller führt den echten Offline-Tourbuild und die Linux-QA getrennt aus.

**D4 bleibt offen:** `context_snapshots.py`, `context_observations.py`, `scripts/verify_context_runtime.py` und `tests/test_context_runtime_backup.py` sind im untersuchten Worktree nicht vorhanden; `model_artifacts.py` enthält kein `rollback_model_slots`. Beobachtungen, Snapshots, Effekt-/Approval-Kopplung und nicht-destruktives Slotrollback werden durch einen erfolgreichen Tour-only-Restore nicht nachgewiesen. Keine Produktionsaktivierung oder empirische Modellfreigabe folgt aus diesem Test.

## Vorhandene aufrufbare Schnittstellen

| Zweck | Exakter bestehender Aufruf | Tatsächliche Quelle |
| --- | --- | --- |
| Live-Inventar | `stage.discover_databases(live_root)` | `scripts/stage_runtime_databases.py:76-120` |
| Versiegelte SQLite-Snapshots | `stage.stage_databases(live_root, current_stage, expected_stage_identity=None, expected_uid=None, expected_gid=None)` | `scripts/stage_runtime_databases.py:258-361` |
| Archiv | `backup.create_archive(output_dir, root=stage_root, logical_root=live_root, stage_manifest_path=stage_root / 'manifest.json', now=None, integrity_key_path=None, migration_marker_path=None)` | `scripts/backup_runtime_databases.py:1816-2015` |
| Archivprüfung | `backup.verify_archive(archive, recovery_mode=False) -> int` | `scripts/backup_runtime_databases.py:2114-2305` |
| Aktiver Modellstand | `load_manifest(path, decision_cutoff=aware_datetime)` | `model_artifacts.py:302-321` |
| Einzelnes Artefakt | `load_artifact(path, digest)` | `model_artifacts.py:240-252`; Hash-/JSON-Prüfung `:219-237` |
| Vollständiger Tourdecode | `load_tour_state('ATP'/'WTA', path=path, allow_legacy=False, decision_cutoff=aware_datetime)` | `tennis/tour_state.py:177-192`; Wrapper-/Scope-Prüfung `:143-174` |
| Vergleich der echten Prognoseausgabe | `predict_match(state, player_a, player_b, 'Hard', best_of=3, tour=tour, indoor=False, as_of=decision)`; keine Quotenargumente | `tennis/predict.py:113-220` |

Die Dateigrenzen oben sind Quellcodeanker im Worktree, keine Behauptung über bereits installierte VPS-Bytes.

CLI nach erfolgreichem API-Staging, mit den tatsächlichen privaten QA-Pfaden:

```sh
"$QA_PYTHON" -I "$QA_SOURCE/scripts/backup_runtime_databases.py" \
  --root "$QA_STAGE/current" --logical-root "$QA_LIVE_APP" \
  --stage-manifest "$QA_STAGE/current/manifest.json" \
  --output-dir "$QA_ARCHIVES" --retention-days 14

"$QA_PYTHON" -I "$QA_SOURCE/scripts/backup_runtime_databases.py" \
  --verify-only "$QA_ARCHIVE"
```

`QA_*` sind explizit vom Controller gewählte isolierte Pfade, keine neuen Runtime-Defaults. Die Backup-CLI ist Standalone/Stdlib; ihre eigentliche Logik steht bei `:3537-3688`. Erwartete Erfolgszeilen: `Backup: ... | databases=1 | verified=1 | pruned=0` in einem frischen Archivordner; `Verified: ... | databases=1`. `--logical-root` und `--stage-manifest` sind zwingend gemeinsam anzugeben und bei `--verify-only` nicht erlaubt. Die API ist für einen Minimalnachweis vorzuziehen, wenn keine Retention ausgeübt werden soll.

**Keine beliebige Staging-CLI:** `stage_runtime_databases.py` akzeptiert keine Live-/Stage-Pfadargumente; `main` ruft ausschließlich `run_production_stage()` auf (`:542-548`). Für Linux-QA die vorhandene Python-API verwenden. Nicht Produktionskonstanten patchen, nicht den Produktions-Privilege-Drop nachbauen.

**Kein `restore_archive`-CLI:** `--restore-backup-tree SNAPSHOT DESTINATION` ist die andere vorhandene Funktion zur Wiederherstellung eines geschützten Backup-Verzeichnisbaums (`backup_runtime_databases.py:3264`, CLI `:3584-3589`). Sie ist kein SQLite-ZIP-Extractor und kein Modellslotrollback. Für diesen Nachweis nur den vorab verifizierten, exakt erwarteten SQLite-Member in einen neuen privaten Baum extrahieren; keinen bestehenden Runtime-Baum austauschen.

## Minimaler echter Testbaum

```text
<neues privates Linux-QA-Verzeichnis, Modus 0700, Eigentümer QA-UID>
├── live-app/                         0700
│   └── runtime_state/               0700
│       └── context_models.db        0600; echte ATP-/WTA-Artefakte
├── private-stage/
│   └── current/                     zuerst leer; nach Staging 0550
│       ├── manifest.json            0440
│       └── runtime_state/           0550
│           └── context_models.db    0440; DELETE, keine WAL/SHM/JOURNAL-Dateien
├── archives/                        außerhalb von live-app und Stage
│   └── betboy-sqlite-<UTC>.zip
└── restored-app/                    neu, 0700
    └── runtime_state/               0700
        └── context_models.db        frisch extrahiert, 0600
```

`runtime_paths.py:27-40` definiert `CONTEXT_MODEL_DB_PATH = RUNTIME_STATE_DIR / 'context_models.db'`; `BETBOY_RUNTIME_STATE_DIR` überschreibt den Standard `<PROJECT_ROOT>/runtime_state`. Für die QA jeden DB-Aufruf ausdrücklich mit `path=...` binden und bei CLI-Tourbuilds die Runtime-Umgebung **vor dem Import** auf den isolierten Baum setzen. Wenn bereits eine echte isolierte Build-DB vorhanden ist, sie entweder dort passend als `live_root` verwenden oder über SQLite `Connection.backup` in den Testbaum aufnehmen. Kein normales Kopieren einer möglicherweise WAL-aktiven `.db`.

Der Tour-only-Baum enthält mindestens die drei Registrytabellen `artifacts`, `manifests`, `active_manifest`, zwei echte `kind='tennis-tour-state'`-Artefakte und die Slots `tennis:ATP`/`tennis:WTA`. Bei einer frischen erfolgreichen sequenziellen `refresh_tours`-Veröffentlichung sind zwei historische Manifeste normal: erst ATP, dann ATP+WTA (`tennis/tour_state.py:251-296`). Nicht fälschlich genau ein Manifest erwarten. Bei wiederverwendeter Build-DB die tatsächlichen historischen Zählwerte aufnehmen und exakt gegen Restore vergleichen.

Als echte Quelle gilt der normale bereits geplante Offline-Build aus vorhandenen geprüften Caches, nicht `tests.state(...)`, nicht frei erfundene Ratings und nicht ein kombiniertes Legacy-Pickle. `refresh_tours` ist die normale Veröffentlichungsschnittstelle (`tennis/tour_state.py:236-310`). Wrapper, A2-State, Trainingsstichtag, tatsächliche Bau-/Publikationszeiten und reale Artifacthashes bleiben unverändert. Keine zusätzliche Netzwerkquelle für diesen Nachweis.

## Rechte und Produktionsvertrag

Für den **API-Nachweis** genügt dieselbe unprivilegierte Linux-QA-UID/GID für Live-DB, Stage und Restore. Neu angelegte private QA-Verzeichnisse explizit 0700; für den isolierten Prozess ist `umask 077` angemessen. `stage_databases` kann zusätzlich das vorher mit `lstat` erfasste `(st_dev, st_ino)`, `os.geteuid()` und `os.getegid()` erhalten; es prüft Identität/Eigentümer vor und nach dem Staging. Der Stage muss anfangs leer sein. Keine Symlinks/Junctions/Hardlinks, keine Dateien in fremden oder austauschbaren Elternverzeichnissen.

Registry-Vertrauen: Dateieigentümer root oder effektive UID; keine Gruppen-/Welt-Schreibrechte an DB und direktem Elternverzeichnis; jedes vorhandene Verzeichnis im Vorfahrenpfad vertrauenswürdig. Nur bei höheren Vorfahren gilt die trusted-owner+sticky-Ausnahme für `/tmp`; die direkte DB-Directory darf auch mit Sticky-Bit nicht fremdbeschreibbar sein (`runtime_paths.py:99-105`, `:142-259`). Das betrifft auch den restaurierten Baum. Bestehende fremde ACLs/Modes nicht lockern.

Der unveränderte **Produktions-Stager** hat einen wesentlich anderen, festen Vertrag:

- `/opt/betboy/app` nach `/tmp/betboy-backup-stage/current` (`stage_runtime_databases.py:31-35`).
- Anfangs alle UIDs 0, `NoNewPrivs=1`, ausschließlich `CAP_CHOWN|CAP_SETGID|CAP_SETUID` in permitted/effective/bounding, inheritable/ambient 0 (`:406-420`).
- Namensauflösung für unprivilegierte UID `betboy` und GID `betboy-backup`; keine erfundenen numerischen IDs (`:423-431`).
- Supplementärgruppen leer; reale/effektive/gespeicherte GID auf Backup-GID; `umask 027` (`:434-439`). `/tmp` root-owned 01777; outer root:backup-GID 0710; current zunächst live-UID:backup-GID 0750 (`:442-485`).
- Danach alle UIDs dauerhaft auf live-UID, Capabilities weg, dumpability 0; selbst Root-Regain wird erfolglos geprüft, **vor** dem ersten Live-DB-Zugriff (`:498-539`).
- Nach Staging Verzeichnisse 0550, Dateien/Manifest 0440; der Archivierer validiert am festen Produktions-Stage zusätzlich exact owner/GID/mode (`backup_runtime_databases.py:518-580`).
- Die vorhandene Servicefixture läuft beim Archivieren als `betboy-backup:betboy-backup`, supplementary `betboy`, `PrivateTmp=true`, `NoNewPrivileges=true`, AF_UNIX-only; Marker-Gate vor Staging. Der Stage-Prestart hat das vorhandene `!`-Präfix. Fixture: `tests/fixtures/betboy-backup-staged.service`.

Das unprivilegierte API-QA beweist echte Linux-Dateimodes/SQLite/Restore, **nicht** den Produktions-Credential-Drop oder eine tatsächlich installierte systemd-Unit.

**Runtime-Root vor Aktivierung separat feststellen:** Produktionsdiscovery ist rekursiv unter `/opt/betboy/app`, nicht automatisch unter dem Umgebungswert `BETBOY_RUNTIME_STATE_DIR`. Liegt die tatsächlich konfigurierte Context-DB außerhalb dieses Wurzelbaums oder unter einer ausgeschlossenen Komponente, wird sie durch diesen unveränderten Produktions-Stager nicht erfasst. Das wäre ein zu meldender Aktivierungsblocker; keine Symlink-Brücke oder zusätzliche `/etc/betboy`-Leserechte erfinden. `stage.discover_databases` unterstützt `.db/.sqlite/.sqlite3`, nicht beliebige externe Modelle (`:18-28`, `:76-120`). Die zwei Tourmodelle sind BLOBs **innerhalb derselben DB**, keine zusätzlichen JSON-Dateien für die Dateidiscovery.

## Marker und HMAC ohne Vertragslockerung

Im beschriebenen Tour-only-Baum gibt es weder `challenge_15k.db`, einen DB-Member unter `challenge_sessions/` noch Tabellen `challenge_settings`/`challenge_integrity_checkpoint`. Daher sind `integrity_key_path=None` und `migration_marker_path=None` der vorhandene korrekte Nicht-15K-Vertrag (`backup_runtime_databases.py:1795-1813`, `:1862-1922`). Keine Produktionsschlüssel lesen/kopieren, keine künstlichen Marker installieren. Das ist keine Umgehung eines Ledger-Gates.

Sobald im selben Archiv ein echtes Challenge-Ledger enthalten ist, bleiben **beide** Pflicht: der passende HMAC-Key und der abgeschlossene, zum logischen ursprünglichen Application-Root passende Marker. Der Key ist genau 64 lowercase Hex-Bytes plus Newline, keine andere Länge/Form (`:601-654`). Am Produktions-Bindpfad `/run/betboy-backup/...` müssen Key und Marker root:`betboy` 0640 sein (`:619-633`, `:1612-1626`); feste Archivnamen unter `integrity/` stehen bei `:34-43`. Marker-Schema, Completion/Receipt, Vorgänger und Rootbindung werden bei `:1663-1754`, `:1889-1904` unverändert geprüft. `recovery_mode=True` ist für diesen normalen Tour-Nachweis unangebracht.

15K-Seitenregressionen separat unverändert ausführen; ein Tour-only-Archiv ersetzt sie nicht. Auch dessen Erfolg berechtigt nicht zur Entnahme privater Ledgerdaten in das QA-Verzeichnis.

## Minimaler Ablauf für den Controller

### 1. Baseline und WAL-Provenienz

Nach dem echten Build und vollständigem Publish eine gemeinsame bewusste `decision`-Zeit erfassen, die nach beiden tatsächlichen Publikationen liegt. Keine Uhr zurückdatieren. Während Baseline/Staging/Restorevergleich keine weitere Tourveröffentlichung in dieser isolierten DB starten.

Für einen kombinierten **echten Tour-im-WAL-Nachweis** am besten die neue QA-DB **vor** der normalen Artefaktveröffentlichung mit einer gehaltenen SQLite-Verbindung in WAL öffnen und `wal_autocheckpoint=0` setzen. Dann normale `refresh_tours`-Veröffentlichung der echten States; Keeper bis nach Staging/Archiv offen halten. Nicht mit einer uncommitted Schreibtransaktion stagen: SQLite-Backup soll den committed Stand sichern. Kein Checkpoint vor Staging. WAL-Datei/Modus und tatsächliche Publikation in diesem Zeitfenster dokumentieren.

Falls die echte Build-DB bereits abgeschlossen war, ist der statische Tour-Restore dennoch sinnvoll. Dann aber keine Behauptung, die Tourdaten seien bewiesenermaßen aus WAL rekonstruiert worden. Das vorhandene echte WAL-E2E und Concurrent-Writer-Test liefern getrennte allgemeine Konsistenzdeckung. Keine direkten No-op-Updates an immutable Artefakten oder erfundenen neuen Publikationen nur für eine schönere Erfolgsbeschreibung.

Baseline mit URI `mode=ro`, `PRAGMA query_only=ON` und einer Lesetransaktion aufnehmen:

- Vorhandene erwartete Registrytabellen; `PRAGMA quick_check` und optional zusätzlich `integrity_check` jeweils `ok`, `foreign_key_check` leer.
- Vollständig geordnete Rohreihen von `artifacts(digest,kind,payload,created_at)`, `manifests(digest,predecessor,payload,published_at)` und `active_manifest(id,digest)`. BLOBs bleiben echte Bytes. Diese Tupellisten können im QA-Prozess exakt verglichen werden, ohne Rohpayloads zu veröffentlichen.
- Aktiver Manifesthash/Slotmap, alle tatsächlichen Artifacthashes, Zeilenzahlen und ursprüngliche Metadaten als kompakte Ausgabe.
- `load_artifact` für jedes Artefakt zur strikten canonical-JSON/Hash-Prüfung; `load_manifest(..., decision_cutoff=decision)` für den aktiven Manifesthash/Publikationszeitpunkt; `load_tour_state` für ATP und WTA ohne Legacy-Fallback.
- Pro Tour ein festgehaltenes Paar **wirklich bekannter Spieler** aus genau diesem State (Mitgliedschaft prüfen), dieselben Matchargumente und dieselbe `as_of=decision` vor/nach Restore. `dataclasses.asdict(predict_match(...))` vollständig vergleichen; zusätzlich die kompakten `market_summary()`/unrundeten p-Werte speichern. Keine Quoten, kein Request, keine spätere reale Uhr im Vergleich.

**Wichtige API-Grenze:** `load_manifest` und `load_artifact` sind keine strikt read-only Datenbankprüfer: `_connect` macht `BEGIN IMMEDIATE` und `CREATE TABLE IF NOT EXISTS` (`model_artifacts.py:131-176`). Daher zuerst Existenz/Tabellen mit `mode=ro` prüfen, damit ein kaputtes/leeres Restore nicht durch Schemaerzeugung kaschiert wird. Öffentliche Reader nur auf der ursprünglichen isolierten QA-DB und der privaten restaurierten Kopie verwenden; nicht auf dem versiegelten 0440/0550-Stage und nicht als Ersatz für das noch fehlende D4-`verify_context_database` ausgeben.

### 2. Exakte bestehende Staging-/Archiv-API

Der folgende Kern setzt die bereits vorhandene echte QA-DB und neue private Verzeichnisse voraus; `live_root`/`qa_root` sind explizite `Path`-Variablen des Controllers:

```python
from pathlib import Path
import os, stat, hashlib, sqlite3, zipfile
from contextlib import closing
from scripts import stage_runtime_databases as stage
from scripts import backup_runtime_databases as backup

db = live_root / "runtime_state" / "context_models.db"
assert db.is_file() and not db.is_symlink()
assert stage.discover_databases(live_root) == [db]
(qa_root / "private-stage").mkdir(mode=0o700)
current = qa_root / "private-stage" / "current"
current.mkdir(mode=0o700)
identity = current.lstat()
staged_manifest = stage.stage_databases(
    live_root, current,
    expected_stage_identity=(identity.st_dev, identity.st_ino),
    expected_uid=os.geteuid(), expected_gid=os.getegid(),
)
staged = current / "runtime_state" / "context_models.db"
assert staged_manifest["database_count"] == 1
assert [r["path"] for r in staged_manifest["databases"]] == [
    "runtime_state/context_models.db"]
record = staged_manifest["databases"][0]
assert record["size"] == staged.stat().st_size
assert record["sha256"] == hashlib.sha256(staged.read_bytes()).hexdigest()
assert stat.S_IMODE(current.stat().st_mode) == 0o550
assert stat.S_IMODE(staged.stat().st_mode) == 0o440
assert stat.S_IMODE((current / "manifest.json").stat().st_mode) == 0o440
assert all(not Path(str(staged) + s).exists() for s in ("-wal", "-shm", "-journal"))
with closing(sqlite3.connect(staged.as_uri() + "?mode=ro", uri=True)) as con:
    con.execute("PRAGMA query_only=ON")
    assert con.execute("PRAGMA journal_mode").fetchone() == ("delete",)
    assert con.execute("PRAGMA quick_check").fetchall() == [("ok",)]
archive, count = backup.create_archive(
    qa_root / "archives", root=current, logical_root=live_root,
    stage_manifest_path=current / "manifest.json",
)
assert count == backup.verify_archive(archive) == 1
```

Alle Pfade vorher absolut und symlinkfrei auflösen; `live_root` und `qa_root` müssen private, isolierte QA-Pfade sein. Archiv/Stage/Restore außerhalb des durchsuchten `live_root` halten. Kein Cleanup gegen berechnete breite Wurzeln; QA-Evidenz zunächst aufbewahren.

### 3. Nur erwarteten Member frisch extrahieren und vergleichen

Nach `verify_archive` zusätzlich exakt `zipped.namelist() == ['runtime_state/context_models.db']` fordern. Frischen `restored-app/runtime_state`-Baum 0700 anlegen, `context_models.db` mit `open('xb')` und privaten Rechten erzeugen. Nur diesen literal erwarteten Member lesen/kopieren, nicht blind `extractall` auf einen bestehenden Baum. Der Member ist jetzt ein selbstständiger geprüfter SQLite-Snapshot; sein Kopieren ist kein unzulässiges Kopieren der Live-WAL-DB.

Archiv-SHA256 und SHA256 des Member-Payloads aufnehmen; Member-Bytes müssen vor dem Öffnen exakt der extrahierten Datei entsprechen. SQLite-Checks und vollständiges geordnetes Registryinventar gegen Baseline wiederholen. Erst danach öffentliche Artifact-/Tourreader verwenden und sämtliche Baseline-Hashes, Zeilenzahlen, States/Metadaten und vollständigen Forecastausgaben vergleichen. Source-/Restore-Inventare erneut lesen, um ungewollte fachliche Mutation beim Prüflesen auszuschließen.

**Drei verschiedene Hashbegriffe nicht vermischen:**

1. `current/manifest.json` ist der versiegelte **Stagingmanifest**, mit DB-Dateihash, Größe und ursprünglichem Device/Inode. Er wird vor und nach der SQLite-Archivkopie validiert (`backup_runtime_databases.py:1836-1843`, `:1938-1945`), aber von `create_archive` **nicht in die ZIP eingebettet** (`:1987-2000`). Manifestbytes/Hash als separate QA-Evidenz aufbewahren; kein neues Archivformat hinzufügen.
2. Der **Modellmanifesthash** liegt in der DB und bindet `predecessor`, Slots und `published_at` (`model_artifacts.py:287-299`, `:352-366`). Dieser und alle Artifacthashes müssen beim Restore exakt identisch bleiben. Artifacthash bindet `{kind, payload}`, nicht `created_at` (`:193-205`); trotzdem original `created_at` zusätzlich vergleichen.
3. **SQLite-Dateibytes** dürfen sich bei der Online-Backup-Erzeugung ändern; Original-Live-DB-Hash ist kein Ersatz für WAL-/Transaktionskonsistenz. Unveränderte Modellinhalte und Quellmetadaten sind der semantische Vergleich. Dagegen müssen ZIP-Member und frisch extrahierte Datei selbstverständlich byteidentisch sein.

Erwartete kompakte Erfolgsausgabe erst nach tatsächlicher Ausführung: `discovered=1 staged=1 archived=1 verified=1`, `sqlite=ok foreign_keys=ok`, tatsächliche `{artifacts, manifests, active_manifest}`-Counts, exakter aktiver Manifesthash, tatsächliche ATP-/WTA-Artifacthashes, `registry_rows_equal=true`, `forecast_outputs_equal=true`, Archive-/Member-SHA256 und realer UID/GID/Mode-Nachweis. Keine vorgegebenen Beispielhashes als Ergebnis ausgeben.

## Unveränderte relevante Tests für die Linux-Ausführung

- `tests/test_backup_stage_e2e.py:12-52`: echter WAL-Keeper, Staging, Archivverify, frische Extraktion, DELETE/quick_check und committed Inhalt.
- `tests/test_backup_stage.py:40-98`: exakte Manifestbytes/-inventare und reale Modes; `:221-270`: weiter commitender WAL-Writer und lückenlos konsistente Zeilen; `:273-322`: Hot-DELETE-Journal; `:101-168`: Reihenfolge des Credential-Drops (gemockte Ablaufdeckung, kein echter Systemservice).
- `tests/test_backup_stage_archive.py:146-175`, `:196-332`: falscher logischer Root, Digest-/Größenänderung, doppelte JSON-Keys, unsichere/unsortierte/bool Records, Extra-Dateien/Verzeichnisse, Symlink/Hardlink, erneute Manifestprüfung nach der Kopie.
- `tests/test_server_jobs.py:2248-2271`: alle unterstützten SQLite-Suffixe; `:2292-2318`: Backup-DAC inklusive Supplementärgruppe; `:2321-2381`: unveränderte Key-/Marker-Kopplung; `:2493-2533`: Traversal und fehlender/ungültiger Key; `:3182-3190`: ungültiger SQLite-Member. Vollständige bestehende Server-/15K-Regressionen bleiben der umfassendere Gate.
- `tests/test_model_artifacts.py`: canonical JSON/Hash/CAS/korruptes Artefakt/fehlende Referenz; die A1-Linux-Rechtefälle bei `:421`, `:594`, `:608`, `:618` sind auf Linux nicht als Windows-Skips zu zählen.
- `tests/test_tennis_tour_state.py`: unabhängige Touren, strenge Wrapper, Clock-/Coverage-/Scope-Grenzen und valide tatsächliche Consumerzustände. Synthetische Tests allein ersetzen nicht den oben beschriebenen echten Artefakt-Restore.

Vorgeschlagener unveränderter vorbereitender Linux-Testaufruf im isolierten Source-Checkout (frischer Basetemp):

```sh
"$QA_PYTHON" -B -m pytest \
  tests/test_backup_stage.py tests/test_backup_stage_archive.py \
  tests/test_backup_stage_e2e.py tests/test_server_jobs.py \
  tests/test_model_artifacts.py tests/test_runtime_paths.py \
  tests/test_tennis_tour_state.py tests/test_tennis_state_codec.py \
  -q -p no:cacheprovider --basetemp="$QA_NEW_BASETEMP"
```

Diese Vorbereitung reproduziert keinen Helperdefekt und verlangt keine Helperänderung. Die echten Tour-/WAL-/Restore-Ergebnisse, aktuelle Produktions-Rootbindung und später der vollständige D4-Verifier/Slotrollback müssen getrennt nachgetragen werden.
