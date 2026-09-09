# D4 Produktions-Updater-Hook – rein lesender Preflight

09.09.2026, unabhängiger Teilauftrag an b3. **Kein implementierter Hook und kein Deploymentnachweis.** Ausschließlich dieser ignorierte Bericht wurde angelegt. Keine SSH-/Providerabfrage, keine produktive DB, kein Git-/Quell-/Rechte-/Serviceeingriff. D4-Semantik auf `b56da33d7b4c447e6a50ff7ec600efc3b7b49f5f` bleibt separat im unabhängigen Review; dessen offenes F1 ist nicht durch diesen Preflight erledigt.

## Ergebnis

Der kleinste passende Einbau liegt im **bestehenden root-eigenen Updater**, nach `create_fresh_backup` und vor `apply_trusted_payload` (d4312dd: Zeilen 2666–2670). Der Updater erzeugt aus genau dem bereits verifizierten Backup eine **einzelne separate, versiegelte Kontext-DB-Kopie**. Die vollständigen Zielmodule liegen bereits im root-erzeugten `TARGET_PAYLOAD`. Nur der App-Benutzer `betboy` führt deren unverändernden Prüfer mit der bestehenden App-venv aus. Der Prüfer bekommt weder ZIP noch Schlüsselpfad. Der Backupdienst und der gepinnte Stagehelper bleiben vollständig unverändert.

Das ist ein konkreter Implementierungsvorschlag, kein bereits existierender Aufruf. `verify_context_runtime` kommt im geprüften Updater noch nicht vor. Ein Git-Push installiert oder startet ihn nicht. Die Timer rechnen/sichern; sie deployen keinen Code.

## Geprüfte Grundlage und Drifttrennung

Festgelegter Quellstand: `d4312dd6c63d7bcda1845f13af73c3c42b814513`. Während des Preflights ging Root unabhängig bis `b6a70c0d3216f5bf223705acd2052a8c26e6328e` weiter. Alle acht unten genannten gelesenen Dateien sind nach reiner CRLF/LF-Normalisierung semantisch bytegleich mit d4312dd. Die besonders geschützten Updater-/Bootstrap-/Backupunit-/Stagehelper-/CLI-Dateien sind auch **roh** bytegleich. Keine Normalisierung wurde geschrieben. Die vorgefundene lokale M-Markierung des Stagehelpers wurde nicht angefasst; dessen rohe Bytes stimmen trotzdem exakt mit dem d4312dd-Gitblob und dem Pin überein.

| Quelle | SHA256 des d4312dd-Gitblobs |
| --- | --- |
| `deploy/update_server.sh` | `a07ad24c92f207c9d1124acee37fb4b0e443dae39876dad6c1948b55bb725cbb` |
| `deploy/bootstrap_server.sh` | `eb2cec227d710156f960ba78a620c5bdfe4bd97cd95ba2deb33a3c120fd5dec6` |
| `deploy/systemd/betboy-backup.service` | `922352a5d3c883cc671da419c5d3fa589cbe9cd025f32d4c4d9f7b6a9648edb8` |
| `scripts/stage_runtime_databases.py` | `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` |
| `scripts/verify_context_runtime.py` | `c1dab7debf1d5e50df640d99f7de6871468cf3db8a80972aeef6e2d58045f410` |
| `runtime_paths.py` | `710b8f8b1bfacf35397aad47d8df2fc9c28f6af60a4888540acfac4030331a8c` |
| `deploy/README.md` | `d9f4a4e7edab436465653f50f4c793ce55552702e001619ae309694e99bea38d` |
| `deploy/VENV_MIGRATION.md` | `2c32f2965639220b81c789660c096359998fe250959233bf18f0be42fe62faeb` |

Vollständig gelesen: Updater, Backupunit, CLI, Runtime-Pfadvertrag, Backup-Hashanker, Venv-Runbook, relevante Restore-/Zwei-Commit-READMEabschnitte, beide D4-/Linux-Audits, Tourstate/Codec; dazu konkrete Bootstrap-Installations-/venv-Seams und vorhandene Deploymenttests. Historische Linux-/VPS-Berichte sind **keine frische Prüfung der jetzt installierten Besitzer, Python-Pakete oder Roottools**. Diese tatsächlichen Liveeigenschaften bleiben vor Rollout lesend zu bestätigen.

## Tatsächliche bestehende Vertrauensgrenzen

- `verify_invocation` (514–537): ausschließlich `/usr/local/sbin/betboy-update`, root:root, regulär, nicht fremdbeschreibbar, genau ein 40-Hex-Ziel. Niemals `sudo` auf einen Skriptpfad im Appcheckout.
- `prepare_trusted_tree` (560ff.): feste HTTPS-Repositoryquelle, exakter autorisierter Main-Tip, bereinigte Gitumgebung ohne Hooks/Ersetzungen/Credentials. `$STAGE_DIR` root:betboy0750. Der Git-Quellbaum ist nicht der zugesicherte app-lesbare Transport.
- `create_trusted_manifests`/`target_payload_file` (632ff./282ff.): jede Ziel-Gitdatei manifestgebunden; `TARGET_PAYLOAD` samt Modulbaum root:betboy, Verzeichnisse0750, einzelne reguläre Dateien0640/nlink1. Das ist der geeignete Codeursprung. `APP_DIR` ist betboy-beschreibbar und keine privilegierte Codeautorität.
- `prepare_dependencies` (1036ff.) lässt unveränderte requirements ohne pip durch; geänderte requirements scheitern **vor Downtime**. Bootstrap erstellt und installiert die venv als betboy (960ff.), nicht als root. Es gibt derzeit keinen Beweis einer root-immutablen/gelockten Site-Packages-Installation. `-I` entfernt User-/CWD-/PYTHONPATH-Einfluss, verhindert aber nicht jede venv-interne `.pth`-/Sitecustomize-Ausführung. Deshalb niemals diese venv oder NumPy-/Appmodule als root oder betboy-backup ausführen.
- Vor `create_fresh_backup`: alle sieben Timer gestoppt, Worker abgewartet, App gestoppt, erneut keine Prozesse von betboy **oder** betboy-backup, vorherige Appbytes geprüft. Autostart ist dauerhaft deaktiviert. Danach darf ein eigener eng begrenzter Prüferprozess bewusst starten; nach seinem Ende erneut Prozessfreiheit prüfen.
- Das bestehende frische Backup (1158ff.) wird durch festes stdlib-only Inline-Python als betboy per SQLite-Onlinebackup erstellt, dann root-eigen abgeschottet. Vollständiges ZIP unter `/var/backups/betboy-update` root:root0700, Datei0600. Es enthält DBs **und** HMAC-Schlüssel/Marker. Sein temporärer SQLite-Stage wird gelöscht; danach ist kein geeigneter Einzel-DB-Pfad verfügbar. Das gesamte ZIP darf nicht app-lesbar gemacht werden.
- Backupservice: betboy-backup mit nur in dieser Unit geltender SupplementaryGroups=betboy; root-gepinnte stdlib-only Helpers; eigener read-only Bind-Mount für genau Schlüssel und Marker; `/etc/betboy` sonst unzugänglich. Archive betboy-backup0600/Verzeichnis0700, für betboy unlesbar. Kein neuer Mount, keine Gruppenerweiterung, kein Appmodul im Backupservice.
- `runtime_paths._trusted_owner_ids` akzeptiert `{root, effektive uid}`. Deshalb ist eine **root:betboy0440** Datei in root:betboy0750 Verzeichnissen bereits zulässig; betboy benötigt kein Eigentum und kann die Datei nicht per chmod schreibbar machen. Keine neue Lockerung des Dateivalidators erforderlich.
- D4 liest einen OS-Deskriptor, prüft Identitäten/Rechte/Hashes und lädt höchstens64MiB in SQLite `:memory:`. Keine Begleiter, DELETE-Header zwingend; kein Immutable-WAL-Bypass. Der Prüfer repariert/initialisiert keine Live-DB.

## Konkreter kleinster neuer Ablauf innerhalb des Updaters

1. **Vor Downtime** Ziel-CLI und vollständige Zielmodule über das bestehende Manifest prüfen; als betboy prüfen, dass die vorhandene venv die benötigten Pakete und SQLite-`deserialize` tatsächlich unterstützt. Kein pip, kein Trainingsstart, keine Quelle. Noch keine Aussage über Datenqualität. Fehlende Capability beendet die Vorprüfung.
2. Den tatsächlich konfigurierten Kontextpfad bestimmen: `runtime_paths` verwendet `BETBOY_RUNTIME_STATE_DIR`, Standard `/opt/betboy/app/runtime_state`, plus `context_models.db`. Nicht einfach den Standard annehmen. Root liest höchstens die erlaubte Konfigurationszuordnung mit geschlossenem Parser aus den bestehenden vertrauenswürdigen Unit-/Environment-Dateien; niemals shell-`source` und keine Secretausgabe. Relative/außerhalb liegende oder nicht belegbare Zuordnungen stoppen, statt zusätzliche Leserechte/Discoveryroots zu eröffnen. Keine Appmodule als root importieren. Die genaue Konfigurationsauflösung braucht noch Implementierungs-/Integrationstests.
3. Bestehenden Quiesce-/Manifest-/Backupablauf unverändert ausführen. Nach `create_fresh_backup` feste relative Kontext-DB-Identität mit dem **vollständig bereits verifizierten Backupmanifest** vergleichen. Bei belegtem alten Stand ohne Kontextdatei ausdrücklich `not_present` protokollieren; nicht als verifiziert ausgeben und keine leere Datei anlegen. Vorhandene/falsch fehlende/außerhalb liegende Datei darf nicht als Legacy-Abwesenheit gelten.
4. In einem neuen Unterordner `$STAGE_DIR/context-verification` root:betboy0750 ausschließlich dieses exakte DB-Mitglied lesen. Keine `extractall`, kein beliebiger ZIP-Zielpfad, keine Integrity-Mitglieder. Prüfen: Manifestzuordnung, einmaliges Mitglied, echte Größe<=64MiB, CRC, SHA256, frische O_EXCL/O_NOFOLLOW-Datei, keine Links, keine bestehenden Nebenfiles. Der Rootprozess verwendet nur **festen Updater-stdLib-Code**, niemals die App-/venv-Module.
5. Archiv-SHA und DB-Mitglied-SHA bleiben unverändert dokumentiert. Falls die DB-Kopie einen WAL-Modusheader trägt, muss eine echte isolierte SQLite-Sealoperation am **neuen privaten Exemplar** dessen vollständige Onlinebackup-Daten nach DELETE überführen; SQL `trusted_schema=OFF`, geschlossenes festes SQL, Abschluss/quick_check und keine Begleiter. Kein Patchen der Headerbytes und kein `immutable=1`. Das Livefile/Archiv bleibt unangetastet. Der existierende Preupdate-Inlinebackuppfad sichert SQLite online, garantiert aber nicht ausdrücklich den von D4 geforderten DELETE-Header. Deshalb wäre schlichtes ZIP-Entpacken ohne diese Kontrolle nicht ausreichend. Dies ist eine neue eng gebundene Updaterfunktion, **keine Änderung des Stagehelpers**.
6. Die abgeschlossene Kopie root:betboy0440/nlink1 versiegeln. SHA256 der versiegelten Kopie separat vom Archiv-Mitglied erfassen, da eine echte Journalmoduskonversion die physischen Bytes ändern kann. Logische A1/B1/B3-/Tour-/Rollbackidentitäten müssen dieselben bleiben; diese Transformation samt Byte-/Zeilenvergleich ist ein erforderlicher Test, kein stiller Gleichheitsclaim. Root schließt alle SQLitehandles vor Übergabe.
7. Exakter vorgeschlagener Aufruf aus dem bereits vertrauenswürdigen Updater, CWD `/`:

   ```bash
   as_betboy /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 \
     /usr/bin/timeout --signal=TERM --kill-after=10s 600s \
     "${VENV_DIR}/bin/python" -I -B \
     "${TARGET_PAYLOAD}/scripts/verify_context_runtime.py" \
     --database "${STAGE_DIR}/context-verification/context_models.db"
   ```

   Der Zeitwert ist ein expliziter vorgeschlagener Budgetdeckel, vor Produktion an echten Größen zu messen, keine heutige bestehende Zusicherung. Timeout/Signal/ungültiges oder fehlendes JSON werden nie PASS. Kein `--backup-root /opt/betboy/app` für diese Kopie: sie liegt absichtlich nicht im Appbaum. Die ursprüngliche Mappingprüfung erfolgt in Schritt2/3. CLI nicht allein nach libexec kopieren, sonst stimmt der Elternpfad seiner Modulimports nicht mehr.

   Keine Secrets/Env-Dateien werden als Argumente oder Umgebung übernommen. Der Appuser besitzt bereits gruppenbasierte Leserechte auf den einzelnen HMAC-Schlüssel; `runuser` allein entzieht diese **nicht**. Der Vorschlag erweitert diese Rechte nicht und gibt dem Prüfer kein Archiv. Wer zusätzlich auch die vorhandenen App-Rechte abschotten will, benötigt einen separat getesteten begrenzten Sandbox-Aufruf innerhalb des Trusted-Updaters; `env -i` ist keine Dateisystem-Sandbox. Eine neue privilegierte Installation oder ein Backupuser-Import wäre kein erlaubter Ersatz.

8. Nach Prozessende Dateihash/Metadaten/Begleiter/Codepayload erneut prüfen, keine übrigen betboy-Prozesse. Nur bekannte strukturelle Statusfelder protokollieren. Erst dann `apply_trusted_payload`; neue Prüfkopien nur innerhalb ihres validierten eindeutigen Stagepfads behandeln. Auf Fehler alle vorhandenen Recoveryregeln beibehalten.

### Noch explizit zu entscheidende Exit-Policy

CLI0 = bekannte Struktur vollständig geprüft, **nicht** alle Prognosen empirisch freigegeben. CLI1 = Integrität/Pfad/Capabilityfehler: Deploy darf nicht weiterlaufen. CLI2 = absichtlich `transport_only`; z.B. unbekannte Legacytransporte, noch nicht belegtes Source-/FV-Replay. Ein blanket `|| true` wäre falsch, ein blanket Exit0-Zwang würde bekannte gültige alte DBs mit bewussten Capabilitylücken unbegründet von jeder Wartung ausschließen.

Empfehlung: exakte im Release festgelegte zulässige Legacy-/Capability-Limitmenge und typisierte Resultshape; Exit2 nur als ausdrücklich unvollständiger, nicht zertifizierter Wartungszustand zulassen, unbekannte zusätzliche Limits abbrechen. Die erlaubte Menge ist ein **Controller-/Releaseentscheid**, noch nicht hier implementiert oder pauschal genehmigt. Beschädigte bekannte Referenzen dürfen niemals in dieser Menge verschwinden; deshalb muss D4-F1 zuvor erledigt/reviewt sein.

## Vertrauensübergang und Restorekompatibilität

Der aktuell installierte alte Updater führt beim ersten Update noch **keinen neuen Hook** aus. Er kann einen geprüften CommitA mit kompatibler App-/Unit-/Helperbasis und dem neuen Updaterskript nach dem bestehenden Vertrag installieren. Erst ein nachweislich installierter/verifizierter neuer Updater kann beim exakten Main-CommitB den Hook erzwingen. Die alte historisch dokumentierte HTTP/1.1-Ausnahme darf nicht wiederholt werden. Keine manuelle Roottool-Kopie, kein erneutes Bootstrap auf bestehendem Host, kein `sudo python` aus Gitcheckout. Bleiben Unit-/Stagepins unverändert, braucht es kein neues Unit-Allowlist-Bridgeformat; die zeitliche Zwei-Commit-Übernahme des neuen Rootcodes bleibt trotzdem zu testen.

`recover_update` stellt vor dem irreversiblen Punkt alte Code-/Rootdateien/Metadaten wieder her, **nicht automatisch alle Datenbanken**. Wichtig: `prepare_challenge_migration_boundary` steht schon **vor** dem vorgeschlagenen Hook. Hat es einen dauerhaften `in_progress`-Marker veröffentlicht, bleibt auch ein rein lesender D4-Fehler fail-closed; diesen bestehenden Marker darf der neue Hook nicht zurücksetzen. Nach tatsächlicher Migration oder Appstart gilt dieselbe harte Grenze.

Manueller kontrollierter Restore gemäß bestehendem Runbook: DB-Gesamtsatz, passender HMAC-Schlüssel und Marker zusammen, alle Dienste gestoppt/deaktiviert; altes vollständiges Archiv root-/backupseitig zuerst prüfen. D4 erhält erneut nur eine getrennte Kontextkopie und die **zur beabsichtigten restaurierten Version gehörenden** vertrauenswürdig bezogenen Module. Kein Import aus teilweise wiederhergestelltem Appcheckout. Es gibt derzeit keinen fertigen automatischen Restore-Hook im Updater; eine neue Recovery-CLI/Methode darf nicht aus diesem Preflight abgeleitet werden. Erst Root legt den passenden bestehenden Wartungspfad fest. Keine Live-Einzel-DB-Restaurierung und kein Modellslot-Rollback als Ersatz für Kontorecovery.

| Eingabe / Übergang | Erforderliches Verhalten |
| --- | --- |
| Belegt alte Installation ohne Kontext-DB | `not_present`, keine DBinitialisierung; sonstige Backup-/Ledgerprüfungen normal, keine erfundene Tourfreigabe |
| Bestehende leere Datei/fehlendes Schema | Fehler, nicht wie fehlende alte Capability behandeln |
| A1/B1 ohne neue Tabellen | Bestehende optionale Schemata korrekt; alle vorhandenen Zeilen/Referenzen prüfen |
| ATP/WTA-JSONartefakte + Manifest | Exakte Tour/Codec/Coverage/finite Predictions; aktive und historische Identitäten erhalten |
| Alte gemeinsame Pickledatei | Nicht öffnen/migrieren/als ATP oder WTA umetikettieren; separater bekannter Legacyzustand außerhalb dieses Checks |
| Noch keine getrennten Tourartefakte | Keine Builds/Providerläufe aus Verifier; Abwesenheit sichtbar, keine neue Freigabe |
| Bekannte D1/D2-Evaluation + final Inventoryopening | Tatsächliche owning Replays; keine finale Labelöffnung vor gebundener Öffnung; alle BH-Verlierer erhalten |
| Opaque/ältere B3-/unbekannte Capability | Exit2 mit genauer Limitmenge, niemals Full-/Empirikclaim |
| Orphan bekannter FV mit fehlendem/zukünftigem Receipt | Harter Integritätsfehler, auch ohne Config; Voraussetzung ist abgeschlossener D4-F1-Fix |
| Live-WAL mit noch uncheckpointetem Receipt | Bestehendes Onlinebackup, isolierte echte DELETE-Sealoperation, Snapshot enthält exakt vollständige Transaktion |
| WAL-/SHM-/Journal neben Prüfeingabe, >64MiB | Ablehnen, nicht löschen/ignorieren oder auf Livepfad ausweichen |
| Unbekanntes neues SQLschema/defekte Tour/Hash/Manifest | Harter Fehler; keine Legacy-Neusignierung/Schema-Migration |
| Geänderte requirements / fehlendes Deserialize | Vor Downtime ablehnen; separates bereits dokumentiertes Venv-Migrationsgate |
| Rollback auf früheren Code | Zu diesem Code passende Prüfung und echte DBkompatibilität nötig; nicht neuere Schemas still reparieren/abschneiden |
| `in_progress`-/v0-v2-Mixbackup | Nur bestehender Recoverymodus, kompletter Satz+Key+Marker, exakt ursprünglich gebundenes Ziel; niemals Dienste allein wegen D4-PASS starten |

## Erforderliche Implementierungs- und Wiederherstellungstests

1. Bestehende Shellreihenfolgentests erweitern: Quiesce/Bytecheck/Backup < Hook < Codeupdate < Appstart, Fehler vor/nach Marker, Timeout/Kill und Boot-Recovery; beide Accounts nach Prüfung prozessfrei. Tatsächliche Shellharness-Ausführung, nicht nur Substringtests.
2. Echte Linux-DAC-Prüfung mit root:betboy0750/0440: betboy liest Kopie und Zielmodule, kann nicht schreiben/chmod/ersetzen; App kann vollständiges Backup nicht lesen; Backupunit-Pins/Bindmounts/DAC bleiben exakt gleich. Kein Ausführen von App-/venvcode als root/betboy-backup. Linux hier nicht erneut ausgeführt.
3. Neue Stage-Quelle exakt Manifestmember, doppelte/Traversal-/Symlink-/Hardlink-/race-/Größen-/SHA-/CRC-Fälle, unbekannter extern konfigurierter Pfad; keine Integrity-Mitglieder im Übergabebaum.
4. Echte WAL-DB mit altem offenen Leser, neuer vollständiger Transaktion und eigener DBfremdsentinel: Preupdatebackup → einzelner Seal → readonlyverify. Quelle/ZIP/Sentinel bytegleich; Zeilen/A1/B1/B3/Tourprognosen identisch. Headerkonversion nur an Kopie; Journal-/Permissionsrace hart ablehnen.
5. Exit0/1/2/Timeout/invalidJSON als echte Subprozesse; Limits unbekannt/erweitert/entfernt. Rootparser niemals Resultflag vertrauen, um verletzte Referenzprüfung zu übergehen. Quelle-/D2-Fehler dürfen keine geldbezogene Rollbackautorität eröffnen.
6. Alte Tour-/A1-/B1-/B3-/D2-Matrix oben plus alle vorhandenen D4-/Stage-/15K-/Serverjobs-/Rollbackregressionen. Tatsächliches Restorearchiv, keine bloß synthetische PASS-Ersetzung. Alte gemeinsame Pickle bleibt bytegleich und wird nie vom Rootprozess importiert.
7. Zweistufiger Installed-Updater-Test: CommitA installiert nur den neuen vertrauenswürdigen Hookcode über Alttool; CommitB wird durch diesen Hook geprüft; Targets/Mainpins/requirements/Units/StageSHA unverändert strikt. Fehler inA/B erhalten jeweils passende Recoverygrenze.

## In diesem Preflight tatsächlich ausgeführt / Autorität

Nur lokale lesende Quell-/Gitblob-/SHA- und Reihenfolgechecks. Alle acht relevanten Quellen normalisiert identisch, rohe fünf Schutzdateien identisch, tatsächliche Hauptreihenfolge Marker<Backup<Apply<Appstart bestätigt, CLIzweige0/1/2 bestätigt, Hookabsenz bestätigt. Ein zunächst falsch formulierter reiner Textassert (`2 if` statt tatsächlichem `else 2`) wurde an der echten CLI korrigiert; kein Produktfehler. Keine pytest-/Linux-/VPS-/Shell-End-to-end-Runde in diesem rein lesenden Teilauftrag.

Ohne neue Produktionsautorität ausführbar: diesen Vorschlag prüfen, nach Rootauftrag eng implementieren, lokale echte temporäre DB-/Shell-/Restoretests, unabhängiger Review und fokussierter Commit. Nicht aus diesem Bericht autorisiert: Roottoolmanuellinstallation, neuer Bootstrap, Paketinstallation/venvtausch, Rechte- oder Keyzugriffserweiterung, SSH/Liveprobe, produktiver Hookaufruf, Restore oder Deployment. Diese bleiben beim Controller mit den bereits bestehenden und konkret zu prüfenden Rolloutrechten. Ein frischer VPS-Abgleich von installiertem Roottoolsha, Unit/Dropins, actual Runtimepfad, Eigentum und venvcapabilities ist vor Produktiveinsatz weiterhin nötig.
