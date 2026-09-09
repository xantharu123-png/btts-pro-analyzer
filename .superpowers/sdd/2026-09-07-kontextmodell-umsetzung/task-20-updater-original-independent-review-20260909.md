# Unabhängiger Review: D4 Trusted-Updater-Hook

09.09.2026, Reviewer `worker_failures_20260909`, enger Auftrag von `/root`.

## Disposition: REQUEST CHANGES, genau ein P2

Der eingefrorene Hook erhält noch **keine Freigabe**. Eine echte Konfigurationsmehrdeutigkeit kann eine vorhandene Kontextdatenbank einschließlich beschädigter A1-Referenz von der Prüfung ausnehmen. Die übrige unten ausgeführte begrenzte Mechanik ist grün. Weder vollständige Produktionsabnahme noch Linux-DAC, Installation, Bootstrap, VPS-Betrieb oder empirische Modellwirkung wurden geprüft oder behauptet.

Es wurden ausschließlich die fünf hier aufgeführten eigenen ignorierten Probe-Dateien, ihre temporären SQLite-/Archivfixtures, JUnit-Ausgaben und dieser Bericht angelegt. Keine Zielsource, Owning-Tests, Hauptaudits, Git-Refs, Installer, Produktionsdaten, Provider oder VPS wurden verändert. Kein eigener Commit/Push/Deployment. Alle ursprünglichen Witnesses bleiben erhalten, auch der unter Windows ungeeignete erste Fullverify-Harness.

## Eingefrorenes Ziel und gelesene Grundlage

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-updater-hook-20260909`.
HEAD/Basis während der gesamten Prüfung: `1daf72d7b582f684006bf2898e8ae3ebd6a4ab6f`; Branch `codex/kontext-updater-hook-20260909`. Beim Freeze liegt das Paket noch uncommittet vor. Genau `deploy/update_server.sh` ist geändert, genau neuer Owning-Test und Hauptaudit sind untracked. Eigene Probes sind ignoriert. Vor und nach den Tests wurden die rohen Zielbytes kontrolliert.

| Datei | Rohe SHA256 |
| --- | --- |
| `deploy/update_server.sh` | `3122364c1eb01fead043e555eab0b220080c639d9560b4304dbb8b40257a5ddd` |
| `tests/test_context_update_hook.py` | `12880ede3a331f624d61127fd78fa24f79f416ace9c89293c565f0157e4f7c31` |
| `docs/audits/2026-09-09-d4-trusted-updater-hook.md` | `74acec67d920d4e52eca717f394c97641894994124596e73235c9e26b1954c3d` |
| Unverändert `scripts/stage_runtime_databases.py` | `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` |
| Unverändert `deploy/systemd/betboy-backup.service` | `922352a5d3c883cc671da419c5d3fa589cbe9cd025f32d4c4d9f7b6a9648edb8` |
| Unverändert `deploy/bootstrap_server.sh` | `eb2cec227d710156f960ba78a620c5bdfe4bd97cd95ba2deb33a3c120fd5dec6` |
| Unverändert tatsächliche D4-CLI `scripts/verify_context_runtime.py` | `c1dab7debf1d5e50df640d99f7de6871468cf3db8a80972aeef6e2d58045f410` |

Vollständig gelesen: genehmigte maßgebliche Spezifikation/SDD-Kontext aus den vorhergehenden D3/D4-Reviews, Task19-Brief, `deploy/README.md`, der komplette aktuelle Hauptaudit, der konkret angegebene Root-Preflight `.pytest_tmp/d4-updater-preflight-20260909/REPORT.md` (SHA `0a747558167dd55aeba0fcab8bbdf27bf7a877096f0abf99f73ebc7ef3a928b3`), sämtliche 550 neuen Updater-Zeilen und der ganze neue Owning-Test. Zusätzlich direkt geprüft: tatsächliche alte `verify_backup_archive`, `create_fresh_backup`, Manifest-/Payload-Erzeugung, `prepare_dependencies`, Invocation/User-Seam, Hauptreihenfolge, Recovery-/Markerzweige und D4-CLI. Relevante unveränderte `backup_runtime_databases.verify_archive`-/Manifestverträge und `runtime_paths` wurden selbst gelesen.

Lokaler Git-Abgleich zusätzlich: `2ba3931dd8cb35f31d2475ae5797d75b44be268e` hat in seinem tatsächlichen Baum keine benannten neuen Kontextpersistenz-/Tourstate-/CLI-Dateien; sein Runtime-Modul enthält den alten Standardpfad, keinen neuen Kontextpfadvertrag. Das ist ein lokaler historischer Gitnachweis, **keine aktuelle VPS-Abfrage**.

## F1 / P2: Unicode-Normalisierung kann die tatsächliche Kontext-DB überspringen

Fundstelle: `deploy/update_server.sh:1159–1182`, insbesondere `runtime_override` mit `ord(c) >= 32`, anschließend `splitlines()` und unbeschränktem `strip()`. Weitergabe in `configuration:1351` und akzeptierter Abwesenheitspfad in `stage/finish:1483–1500`.

Python behandelt U+0085, U+2028 und U+2029 als Zeilengrenzen. Der vorgeschaltete Zeichencheck lässt sie durch. Damit wird aus **einer** EnvironmentFile-Zuweisung

`OTHER=harmless<U+2028>BETBOY_RUNTIME_STATE_DIR=/opt/betboy/app/custom`

im Hook ein zusätzliches scheinbares `BETBOY_RUNTIME_STATE_DIR`-Record. Außerdem normalisiert `strip()` etwa U+00A0/U+2003/U+202F vor einem Namen weg. Diese Zeichen sind keine gleichwertigen ASCII-Syntaxzeichen des systemd-EnvironmentFile-Parsers.

Die reale Grammatik wurde gegen zwei offizielle, explizit versionierte Primärquellen abgeglichen: [systemd v256 env-file.c](https://raw.githubusercontent.com/systemd/systemd/v256/src/basic/env-file.c) verarbeitet die Bytes in einem Zustandsautomaten; [string-util.h](https://raw.githubusercontent.com/systemd/systemd/v256/src/basic/string-util.h) beschränkt Zeilenende auf LF/CR und Syntax-Whitespace auf Space/Tab/LF/CR. U+2028 bleibt im ersten Beispiel Teil des Werts `OTHER` und erzeugt keinen neuen Runtime-Override. Es wurde **kein installiertes systemd ausgeführt und keine VPS-Version abgeleitet**. Der zusätzliche Abruf der offiziellen HTML-Manpage lieferte403 und wurde nicht als Evidenz verwendet. Keine Provider-Abfrage.

### Wirklich ausgeführte Kette, nicht nur Textassertion

1. Echte temporäre Default-Kontext-DB mit A1-Manifest und getrennten ATP-/WTA-Tourartefakten aufbauen.
2. Genau das referenzierte ATP-Artefakt entfernen; physisches SQLite bleibt konsistent. Keine Finanz-/15K-Daten im Fixture.
3. Vollständiges Archiv mit korrektem Vierfeld-DBinventar, SHA, Größen und **formal gültigem synthetischem**65-Byte-Key erzeugen. Kein wirklicher Schlüssel wird gelesen.
4. Beide bestehende vollständige Backupprüfungen laufen mit ihren tatsächlichen Prüfentscheidungen erfolgreich: Inline-`verify_backup_archive` und `scripts/backup_runtime_databases.py --verify-only ... --recovery-mode`. Der einzige Windows-Adapter ist weiter unten offen beschrieben.
5. Unveränderte tatsächliche D4-CLI gegen genau diese DB: **Exit1, status=failed**. Die Kontrollen derselben Quelle mit intaktem A1-Manifest liefern **Exit0, status=verified**.
6. Tatsächliches `configuration → stage → finish` erhält den Phantom-Override und meldet `custom/context_models.db`, `present=False`, danach `not_present_legacy` und den erfolgreichen Kontinuitätslog. Es wird **keine** Verifier-DBkopie erzeugt. Das echte Default-Mitglied bleibt im verifizierten Archiv, wird aber nicht ausgewählt.
7. Live-Fixture und Archivbytes bleiben exakt gleich. Gerade dadurch ist es keine nachträgliche Archivmanipulation und wird von der Hash-Rereadprüfung nicht entdeckt.

Drei separator-parametrisierte stärkere Fälle enden exakt am erwarteten `assert rejected` rot, nicht in einem Setupfehler. Der frühere Satz liefert zusätzlich sechs direkte Parser-REDs und drei einfachere Stage-REDs. Es handelt sich um **einen** gemeinsamen Befund, nicht zwölf verschiedene Bugs.

Voraussetzung/Schwere: Dies setzt eine entsprechend ungewöhnliche, root-eigene Konfiguration voraus. Kein Nachweis eines unprivilegierten Schreibzugriffs, keiner Privilegieneskalation und keines tatsächlichen Produktionsvorkommnisses. Trotzdem verletzt der erlaubte Eingabepfad die zentrale Aussage „nur belegte echte Legacy-Abwesenheit“. Für einen Installationsprüfer ist das ein zu behebender P2 vor Freigabe.

### Kleinste Reparaturgrenze

Nicht eine zweite komplexe systemd-Implementierung bauen. Die bereits geschlossene unterstützte Grammatik vor jeder `splitlines`-/`strip`-Normalisierung streng begrenzen: insbesondere nicht-ASCII-Whitespace/Zeilentrenner nicht als Syntax akzeptieren; mehrdeutige Eingaben vor Downtime ablehnen. Reguläre ASCII-Zeilen LF, CRLF/CR, gültige eindeutige Datensätze und normale Nicht-ASCII-Buchstaben in Werten müssen weiter nachvollziehbar bleiben. Keine neue beliebige Pfadsuche, kein pauschales Legacy-Verbot und keine Lockerung der Präsenz-/Hash-/Ownergrenzen.

Root/Owner sollen die unveränderten roten Witnesses erneut ausführen, permanente Regressionen ergänzen und erst danach einen neuen eingefrorenen Stand zur Nachprüfung geben. Dieser Reviewer hat keinen Quellfix vorgenommen.

## Sonstige geprüfte Mechanik

- **Fail-before-downtime:** Tatsächliche `preflight_context_runtime`-Bashfunktion mit jeweils fehlschlagendem Configure, Dependency-Child und Dependency-Outputvalidator. Keiner erreicht die nachfolgende Downtime-Markierung. Tatsächlicher `recover_update` im Preflightfehlerzweig berührt keine Dienste.
- **Wichtige Trennung:** Daten-/Referenzprüfung ist absichtlich **nach** Quiesce und frischem Backup, aber **vor** Apply. Nicht behauptet, dass jeder Datenfehler bereits vor Downtime auftritt. Ein vorhandener `in_progress`-Marker bleibt auf diesem Fehlerpfad fail-closed; keine Geld-DB wird automatisch restauriert.
- **Pipeline:** Echte Bashpipeline bewahrt die Child-Exitcodes. Neue separate Collectorfehler1/124/137 führen unabhängig vom gültigen Childtext zu Abbruch. Eine echte GNU-timeout/head-Pipeline mit lediglich verkürzten Testbudgets bestätigt Timeout124; die tatsächlichen festen Optionen600/610Sekunden und TERM/KILL werden davor im Wrapper geprüft. Kein600Sekunden-Dauertest und kein realer Linux-Accountwechsel behauptet.
- **Privileg-/Importseam:** Fester Root-Inlinecode nur stdlib; kein App-/venv-/NumPy-Import als root. Komplette manifestechte Module vor Childimport geprüft. Der tatsächliche Userwechsel ist `runuser -u betboy --`; `-I`/`env -i` sind keine behauptete Dateisystem-Sandbox. Venv-Sitecustomize und vorhandene Apprechte bleiben bestehende Grenzen.
- **Einzelmitglied/Seal:** Echte SQLite-/ZIPpfade, unveränderte Fullverify-vor-Publication-Reihenfolge, Zielmember nur nach exakter Zuordnung; der neue Hook öffnet Key-/Markerinhalt nicht. Eigene Inode-Replacementprobe mit identischen DBbytes wird nach dem Verifier abgelehnt. Der bestehende Owning-Lauf enthält zudem tatsächliche Live-WAL→Onlinebackup→DELETEseal→D4-CLI-Kontrollen; selbst erneut ausgeführt.
- **Resultpolicy:** Alle sechs Zählerfamilien werden mit Bool/Float/negativ/null/String/List/Dict angegriffen. Alle sechs D2-Digestlisten mit falschem Typ, doppelten/unsortierten/ungültigen Werten. Status und tatsächlicher Exit0/2 dürfen nicht vertauscht werden; unbekannte Exitcodes und nicht erlaubte Limits bleiben geschlossen. Die zwölf ausdrücklich freigegebenen Limits wurden vollständig geprüft, keine Wildcard.
- **Legacy/Resume/Recovery:** Echter Code-/Runtime-/Präsenzvertrag plus Hauptreihenfolge gelesen; ursprüngliche Resumeprobe mit unterschiedlichem Manifest-Previous und aktuellem Backup-HEAD im eigenen Owning-Lauf ausgeführt. Zusätzliche tatsächliche Recovery-Bashproben: vor Migrationsgrenze alte Code-/Rootfiles/Unitzustände; bei durable-in-progress bzw. neu gestarteter App keine automatische Wiederaufnahme und keine Stagevernichtung. Alte69Bashfunktionen einschließlich Backup, Marker und Recovery sind per unabhängiger Probe bytegleich, nur `preflight` plus vier neue Funktionen unterscheiden sich. `bash -n` erfolgreich.
- **Zwei-Commit-Grenze:** A installiert nur den kompatiblen Updater, B enthält den vollständigen Kontextcode. Der neue Hook verlangt im Ziel den vollständigen Verifier. Kein behaupteter laufender A→B-Installationsnachweis. Die echte Linuxmatrix muss insbesondere Fehler an der A/B-Installationsgrenze und gegebenenfalls nötige Recovery anhand des wirklichen Markers prüfen. Kein manuelles Rootcode-Kopieren oder erneutes Bootstrap wurde durchgeführt.

## Eigene Ergebnisse und erhaltene ungeeignete Harnessversuche

Alle pytest-Aufrufe: vorhandener Quality-Python, `-B -m pytest -q -p no:cacheprovider`, jeweils eigener unten benannter Basetemp/JUnit. Keine Tests oder Assertions wurden nach einem roten Ergebnis umgeschrieben.

| Eigen ausgeführter Lauf | Ergebnis |
| --- | --- |
| Unveränderte185Owning-Hooktests, `updater-independent-owning-01` | **185 passed**,20,48s |
| Neue unabhängige Ablauf-/Typ-/Pipeline-/Recovery-/Inodeproben, `updater-independent-probes-01` | **107 passed**,3,87s |
| Original Unicode-Parser/einfache Stagefälle plus Kontrollen, `updater-independent-unicode-01` | **9 funktionale REDs,6 passed**,0,85s |
| Erster unveränderter Fullverify-Witness, `updater-independent-qualified-01` | **3 Windows-/Harnessfehler**,1,11s; keine drei zusätzlichen Produktfindings |
| Separater portabler Wrapper des exakt unveränderten Fullverify-Witnesses, `updater-independent-portable-01` | **3 funktionale REDs**,5,02s |
| Vier neue echte intakte/defekte Fullverify→D4→Finish-Kontrollen plus `test_context_runtime_backup.py`, `updater-independent-controls-01` | **97 passed,3 Windows-Skips**,15,85s |
| `test_server_jobs.py -k 'update or recover or resume or rollback or migration'`, `updater-independent-server-01` | **33 passed,3 Windows-Skips,54 ausdrücklich scope-deselected**,4,00s |

Die ersten Fullverifyversuche scheiterten, nachdem die alten Inline-Checks durchgeführt wurden, am Windows-Unlink einer noch offenen SQLite-Connection im alten `TemporaryDirectory`-Cleanup. Dieses unter Linux anders behandelbare Dateiverhalten ist kein neu eingeführter Hookbug. Originaldatei und komplette JUnitfehler sind erhalten. Der separate portable Wrapper benutzt eine echte `sqlite3.Connection`-Unterklasse, deren `__exit__` nach dem unveränderten echten Commit/Rollback zusätzlich `close()` ausführt. Keine Rückgabewerte/Queries/Hashes/Schemata werden gefälscht oder übergangen. Damit laufen die beiden wirklichen Backup-Entscheidungspfade und der echte D4-Subprozess bis zu den maßgeblichen Assertions; es ist weiterhin **kein Linux-/DAC-Nachweis**.

Auch die wiederverwendete erste einfache Backupfixture (`test_unicode_environment_finding.py`) besitzt nur einen absichtlich unvollständigen Test-Key. Diese erste Kette beweist allein die vorhandenen Hookentscheidungen, nicht den vorgeschalteten Fullverify. Genau deshalb wurde der vollständig verifizierbare separate Witness hinzugefügt und nicht die alte Datei nachträglich verbessert. Der Owner meldete während der Prüfung denselben Unicodeverdacht zusätzlich; der Reviewer hatte ihn zuvor bei der eigenen Sourceprüfung notiert und führte die komplette stärkere Kette unabhängig aus.

Die sechs Skips der zwei Regressionen betreffen reale Symlink-Erstellung ohne Windows-Privilege bzw. POSIX-Owner/Mode. Sie sind weder bestanden noch still auf Mock-Symlinks umgestellt. 54 Serverjob-Deselections ergeben sich aus dem ausdrücklich begrenzten Namensfilter, nicht aus fehlschlagenden Fällen. Kein eigener Full-Repo-Lauf erforderlich oder durchgeführt. Der Owner meldete separat4735/18Skips/97Untertests; das bleibt **Owner-Evidenz**, keine Reviewer-Freigabe.

## Unveränderte eigene Witness-Dateien

Alle Pfade relativ zu `.pytest_tmp/updater-independent-20260909/`:

| Datei | SHA256 |
| --- | --- |
| `test_independent_updater.py` | `5713c18f62109e566da2a93d12e16b326ee9a12598c95ec78c1d262db7f8b1d5` |
| `test_unicode_environment_finding.py` | `6ea64de042564a7f7540fd4efc5a3615452f5767fff09aa29661a98254102133` |
| `test_unicode_full_backup_qualified.py` | `e434ed3c78978b5c31ce21a6d52ba9643d62469056f03a7de9a49c0e16755d4a` |
| `test_unicode_full_backup_portable.py` | `6839e61340b5db98a8f3ee8d8782e662031579fe2fa3c5dbd799e44afca29980` |
| `test_full_backup_controls.py` | `daed3c7eaaf93b63130996c916f086f764e2af990882a4da9cf6ea37d2e8bfbd` |

`test_independent_updater.py::test_exact_review_freeze_and_unmodified_old_functions` enthält absichtlich den **alten Review-SHA**. Nach einem legitimen Quellfix muss dieser unveränderte eingefrorene Bytepin als solcher separat beurteilt/deselektiert werden; er darf nicht in eine neue funktionale Regression oder heimlich umgeschriebene Erwartung verwandelt werden. Die roten Unicode-Witnesses enthalten keinen solchen Sourcepin.

## JUnit-Hashes

Alle Dateien relativ zur Worktree-`.pytest_tmp/`:

| JUnit | SHA256 |
| --- | --- |
| `updater-independent-owning-01.xml` | `95f824a48c913329d9f69f75d63d2d1262571f55f8da70b8b0d43f3c457bd699` |
| `updater-independent-probes-01.xml` | `3876ca61428fd6683a904a8451151e3bf510e39bda33c8d84bb2510c16f444c9` |
| `updater-independent-unicode-01.xml` | `6881edeae834243fae99fa73e644a8049845a9460750eedaf5cee882215fd44f` |
| `updater-independent-qualified-01.xml` | `bcaebcb1225698b02ddafe56b4ec092a0f809483f89683f0e3b2609cd4a54bd0` |
| `updater-independent-portable-01.xml` | `2f3002f57da7b10c2360710a6ba82834071d5f82d8e38e0a5e385e40d51738af` |
| `updater-independent-controls-01.xml` | `fbd03d2546b8bd0e1f9330a6a79946aca2406097ca6f155c903207dc1f136419` |
| `updater-independent-server-01.xml` | `27046612ca7a2fa41ddd082e51c2dd32b8fab94817cb844390d3cdc50f56f3ef` |

## Verbleibende getrennte Abnahmen

1. Enger Parserfix und unabhängiger Nachlauf der erhaltenen REDs vor Hookfreigabe.
2. Reale Linuxrollen/DAC mit root:betboy0750/0440: lesen erlaubt, Schreiben/chmod/Replace/Links nicht; kein zusätzlicher Archiv-/Keyzugriff. Existierende App-Dateirechte und Venv-Sitecode ehrlich berücksichtigen.
3. Tatsächliche installierte A→B-Updaterkette inklusive Marker-/Resume-/Recoveryfällen, Versionspins, vorhandener Python-/Deserializefähigkeit und festem Zeitbudget. Ein gitgleicher Shelltest ist keine Installation.
4. Realer VPS-/Produktions-/Providerzustand, D3-Worker/UI-Anbindung und empirische Kontextwirkung bleiben ausdrücklich außerhalb dieser Prüfung. Kein Price-Gate, Wettartenverbot, Cricket-/15K-/Ledger-/Snapshotumbau wurde eingeführt.
