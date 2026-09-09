# D4 – Kontextprüfung im bestehenden Trusted-Updater

09.09.2026. Begrenzter Implementierungsauftrag an `b3_shared_snapshots_20260909`, Basis `1daf72d7b582f684006bf2898e8ae3ebd6a4ab6f`, Branch `codex/kontext-updater-hook-20260909`.

## Ergebnis und ausdrücklich getrennte Freigaben

Der neue Hook prüft vor einem Codewechsel eine einzelne Kontextdatenbank aus dem bereits vollständig verifizierten Preupdatebackup. Ausschließlich der App-Benutzer führt den tatsächlichen unverändernden D4-Prüfer aus. Die Rootseite benutzt nur festen stdlib-Code im vorhandenen Trusted-Updater und geschlossene Ergebnis-/Pfadverträge. Sie importiert keine App, keine venv, kein NumPy und keinen Backuphelper. Der Hook verändert keine Live-Datenbank und erteilt keine empirische Wirkungsfreigabe.

Lokale Softwareprüfung nach dem unabhängigen P2-Gegenbeleg und engem Parserfix: **239 eigene fokussierte Tests plus18 unveränderte ursprüngliche Reviewerfälle bestanden**, tatsächliche Bash-Ausführung und reale SQLite/WAL-/D4-CLI-Prüfungen eingeschlossen. Zusätzlich388 bestehende/independent Regressionen bestanden,10 erwartete Plattformskips,39 Untertests. Vorfix-Vollsuite und erneuter Nachfixlauf sind unten strikt getrennt. **Unabhängiger Nachreview noch offen, keine frische Linux-DAC-Abnahme dieses Hooks und kein Produktionsaufruf.** Ein grüner Windows-Test emuliert keine Linux-Besitzerrechte.

Keine Änderung an Stagehelper, Backupunit, Bootstrap, Keys, 15K-Migrationspolitik, D1/D2-/D3-Prüfern, Modellen, Prognosen, Cricket, UI, Abfragen oder Quellenbudgets. Keine Provider-/VPS-Abfrage, kein Paketinstallieren, kein Roottoolmanuellinstallieren, kein Push, kein Restore und kein Deployment durch diesen Teilauftrag.

Zusätzlicher maschineller Gitblobvergleich gegen die Basis: **69 bestehende Bashfunktionen bytegleich**, nur `preflight` um Voraussetzungen und Aufruf erweitert; exakt vier neue Hookfunktionen. Insbesondere `recover_update`, `prepare_challenge_migration_boundary`, `create_fresh_backup`, `verify_backup_archive`, `as_betboy`, `target_payload_file` und `prepare_dependencies` blieben unverändert. `bash -n` und `git -c core.autocrlf=false diff --check` sind erfolgreich.

## Gelesene Grundlage

Der vorherige vollständige read-only Preflight liegt unverändert im Controller-Worktree unter `.pytest_tmp/d4-updater-preflight-20260909/REPORT.md`, SHA256 `0a747558167dd55aeba0fcab8bbdf27bf7a877096f0abf99f73ebc7ef3a928b3`. D4-Plan, Spezifikation, vorherige Runtime-/Restore-/Linux-Audits, bestehender Updater, Backupverträge, Pfadauflösung und CLI wurden dort vollständig geprüft; für die Umsetzung wurden die konkreten Funktionen erneut gelesen. D4-F1 ist in der hier verwendeten Basis bereits korrigiert; dessen unabhängige Nachprüfung bleibt eine eigene Evidenz.

Verbindliche zusätzliche Controllerentscheidungen:

- Ein fehlendes File ist ausschließlich im belegten ersten Legacy-Übergang zulässig. `PREVIOUS_PAYLOAD` darf noch **keinen** `CONTEXT_MODEL_DB_PATH`-Vertrag enthalten; erkennbare teilweise neue Kontextpersistenz, Kontextpakete, Kontexttransporte, Tourstate oder Kontext-CLI machen diese Annahme ungültig. Live- und vollständig verifizierte Backupabwesenheit müssen exakt übereinstimmen.
- Ein kontextfähiger, aber noch nicht initialisierter Stand ist **kein** allgemeiner erlaubter Wartungsfall. Dafür wurde kein Opt-in und kein No-data-Bypass eingeführt.
- Exit0 bedeutet bekannte Struktur; Exit2 nur ausdrücklich zugelassene, einzeln benannte unvollständige Kontinuität. Beides bedeutet **nicht** geprüfte Modellwirkung. Unbekannte Schema-/Openingfähigkeit und beschädigte Referenzen werden nicht akzeptiert.
- Die bisherige Zwei-Commit-/Rootupdater-Vertrauensgrenze, Markerrecovery und Geld-/Backuprechte bleiben unverändert.

## Exakter Ablauf und Berechtigungen

1. Das unveränderte `prepare_dependencies` lehnt geänderte requirements vor Downtime ab; kein pip. Anschließend läuft `preflight_context_runtime`, ebenfalls vor `UPDATE_STARTED`, Timerstopp und Appstopp.
2. `context_hook_data configure` prüft den ganzen root-erzeugten `TARGET_PAYLOAD` und `PREVIOUS_PAYLOAD` gegen ihre echten Manifeste, reguläre Dateien, nlink1, Eigentum und Hash. Zusätzliche oder fehlende Importdateien scheitern. Alle ausführbaren Zielmodule bleiben root:betboy0640 in root:betboy0750-Verzeichnissen.
3. Die Pfadzuordnung ist an die tatsächlich gelesene normalisierte `runtime_paths.py`-Revision gebunden, SHA256 `710b8f8b1bfacf35397aad47d8df2fc9c28f6af60a4888540acfac4030331a8c`. Geänderte Resolverbytes erfordern erneute Prüfung und gegebenenfalls einen neuen Updater-Bridge; selbst vermeintlich harmlose Änderungen umgehen diesen geschlossenen Vertrag nicht.
4. Tatsächliche erlaubte Datenquelle für die Zuordnung ist nur `/etc/betboy/betboy.env` gemäß den sieben App-/Worker-Unitrecords, nicht die Backupunit. Die Env-Datei ist optional gemäß unverändertem Unitvertrag, falls vorhanden root:betboy0640 und höchstens64KiB. Ein gemeinsamer geschlossener Recorddecoder für Env und Units unterstützt ausdrücklich ASCII-LF, CRLF und Bare-CR; nur ASCII-Space/Tab sind Syntaxränder. U+0085/U+2028/U+2029 werden als nicht unterstützte Recordsemantik abgelehnt, niemals als weitere Zuweisung interpretiert. Unterstützt werden nur eindeutige einzeilige NAME=value-Records; doppelte, multiline, escaped oder widersprüchliche Varianten scheitern vor Downtime. Keine Shellauswertung, kein Echo von Werten. Zusätzliche/überschriebene EnvironmentFile-, PassEnvironment-, UnsetEnvironment- und Laufzeitpfadrecords scheitern auch bei Leerraumvarianten. Unverwandte Werte bleiben opaque; normale Unicodebuchstaben und innere Unicodeleerzeichen werden nicht umgeschrieben. Nur der tatsächlich gewählte Runtimewert wird bei Unicode-Randwhitespace ausdrücklich abgelehnt, statt die weitergehende Unicode-Normalisierung des Appresolvers zu erraten.
5. `BETBOY_RUNTIME_STATE_DIR` muss ein exakter absoluter POSIX-Pfad innerhalb `/opt/betboy/app` und innerhalb der bestehenden Backupdiscovery sein. Standard ist `/opt/betboy/app/runtime_state/context_models.db`. Relative, Expanduser-, Traversal-, Symlink-/fremdbeschreibbare oder ausgeschlossene Backupwege werden nicht neu interpretiert. Die Rootseite importiert den Resolver ausdrücklich nicht.
6. Die bestehende App-venv importiert als `betboy` die vollständigen Zielmodule und prüft echtes SQLite-serialize/deserialize gegen zwei rein interne Datenbanken. Aufruf mit `env -i`, `-I -B` und festem Timeout. Fehler oder zusätzliche Ausgabe erlauben keine Downtime. Dies ist ein Softwareabhängigkeitscheck, kein Daten- oder Modellqualitätscheck.
7. Bestehender Ablauf unverändert: Quiesce, Prozessfreiheit beider Serviceaccounts, vorherige Appbytes, dauerhafte Autostartdeaktivierung, bestehende Migrationsmarkergrenze und vollständig geprüftes frisches Backup.
8. **Neue konkrete Hauptcallsite:** `create_fresh_backup` → `verify_context_runtime_before_update` → `apply_trusted_payload`. Vor und nach dem bewusst gestarteten Prüfer wird `verify_no_betboy_processes` aufgerufen.
9. `stage` liest nur `MANIFEST.json` und das eine exakt konfigurierte DB-Mitglied aus dem root:root0600-Archiv. Die vollständige ZIP wird dem Appuser niemals zugänglich gemacht. Die vier tatsächlichen DB-Recordfelder `path`, `source_size`, `backup_size`, `sha256` sind geschlossen geprüft, einschließlich echter Integer, Größenabgleich und Hash. Alle Memberidentitäten werden vor Auswahl geprüft; kein extractall, kein frei gewählter Archivzielpfad. Die Integrity-Key-/Marker-Member werden nicht geöffnet. Das bestehende vorgelagerte Gesamtbackupverify bleibt verpflichtend.
10. Die Kopie wird neu O_EXCL/O_NOFOLLOW root0600 in `$STAGE_DIR/context-hook` angelegt. Nur diese Kopie wird mit stdlib-SQLite tatsächlich nach DELETE versiegelt (`trusted_schema=OFF`, feste PRAGMAs, quick_check, garantiertes Schließen auch bei Fehler). Kein Headerpatch, kein immutable-WAL, kein Filename-SQLite-Aufruf auf Live- oder Archivdatei. Höchstens64MiB; keinerlei WAL/SHM/Journal neben der versiegelten Prüfeingabe.
11. Die abgeschlossene Kopie ist **root:betboy0440/nlink1**, Verzeichnis root:betboy0750. Archivmitglied-Hash und versiegelter Hash werden getrennt gespeichert: echte SQLite-Journalumstellung darf physische Bytes ändern, nicht historische Zeilen/Identitäten. Root-eigene Konfigurations-, Staging- und Ausgabe-Receipts bleiben0600.
12. Der tatsächliche Aufruf als Appuser ist:

    ```bash
    as_betboy /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 \
      /usr/bin/timeout --signal=TERM --kill-after=10s 600s \
      "${VENV_DIR}/bin/python" -I -B \
      "${TARGET_PAYLOAD}/scripts/verify_context_runtime.py" \
      --database "${STAGE_DIR}/context-hook/context_models.db"
    ```

    Der rootseitige reine Ausgabekollektor hat zusätzlich `timeout --signal=TERM --kill-after=10s 610s /usr/bin/head -c 1048577`. Somit bleibt auch eine offen gehaltene Ausgabepipe begrenzt. Beide echten Pipeline-Exitcodes werden geprüft; Childstatus0/2 wird nicht durch `head` zu Erfolg umgeschrieben. Mehr als1MiB Ausgabe ist kein gültiges Ergebnis. Der Zeitdeckel ist fest, kein konfigurierbarer Umgehungsschalter.
13. `finish` prüft Konfiguration, vollständigen Codepayload, Archivmetadaten/-hash, Live-Dateiidentitäten einschließlich Begleitern und versiegelte Eingabebytes/-metadaten erneut. Erst anschließend werden das tatsächlich erfasste JSON und der tatsächliche Exitcode bewertet. Keine unaufgelösten vertrauten Flags, kein `|| true`, keine Logausgabe frei gespeicherter Strings.

`-I` ist keine Behauptung root-immutabler Site-Packages: die bestehende venv kann `.pth`-/Sitecustomize-Verhalten enthalten. Deshalb wird sie niemals als root oder betboy-backup ausgeführt. `env -i` entzieht keine schon bestehenden Dateisystemrechte des Appaccounts. Der Hook erweitert weder solche Rechte noch Backupusergruppen oder Bindmounts. Diese vorhandene Vertrauensgrenze muss der unabhängige Linux-Test ausdrücklich kontrollieren.

## Geschlossene Exitpolicy v1

JSON erlaubt exakt die tatsächlichen CLI-Felder: status/schema/verification_level/empirical_approval_verified/limitations/d2_verified/counts/active_manifest/active_slots_hash/active_slot_count/tour_states. Schema und Zähler sind echte Integer, keine Bools; Hashlisten und Limits sortiert/eindeutig, keine unbekannten Keys, Duplicate-JSON-Keys oder NaN/Infinity. A1 darf mehrere Slots auf ein einziges Artefakt verweisen; diese tatsächliche Aliasfähigkeit wurde nicht durch erfundene Zählergrenzen gesperrt.

- **Exit0:** `status=verified`, `verification_level=structural`, leere Limits und `empirical_approval_verified is False`.
- **Exit2:** `status=incomplete`, `verification_level=transport_only`, derselbe exakte False-Wert; nichtleere, sortierte, eindeutige Teilmenge ausschließlich folgender zwölf Controllerlimits.
- **Alles andere:** Fehler, einschließlich Timeout/Killsignal, Code1, falscher Form, unbekannter Fähigkeit, leeren Exit2-Limits und widersprüchlichen Werten.

Erlaubte Liste, keine Wildcards:

```text
d2-final-source-replay-not-opened
d1-participation-training-receipts-unresolved
d1-final-source-replay-unavailable
d1-fit-owning-replay-unavailable
d2-dataset-owning-experiment-unavailable
d1-case-owning-replay-unavailable
d1-original-replay-context-unavailable
d2-evaluation-opening-unavailable
d2-approval-evidence-resolution-unavailable
d3-owning-family-replay-unavailable
d3-owning-source-feature-replay-unavailable
d3-snapshot-input-binding-unavailable
```

Die reale alte D4-Fixture mit opaque Experiment/Report erhält zusätzlich `d2-report-experiment-schema-unavailable`. Sie wird **korrekt abgelehnt**, obwohl ihre Bytes restaurierbar sind. Der Test wurde nicht durch Umetikettierung dieser alten Artefakte grün gemacht: eine separate vor-experimentelle positive Kontrolle ohne erfundene Report-/Experimentartefakte und die unveränderte opaque Negativkontrolle werden beide ausgeführt. `unrecognized-artifact-schema`, `d2-unrecognized*`, `schema-unavailable` oder `opening-semantics-unavailable` sind niemals pauschal zulässig.

Logs heißen ausschließlich `Context continuity: structural/transport_only/not_present_legacy; no model/effect certification.` Sie stellen keine Quelle, kein Training und keine empirische Prognosequalität als erledigt dar.

## Resume und zweistufiger Produktionsübergang

Der vorhandene Resume-Code kann `PREVIOUS_PAYLOAD` aus `MIGRATION_MARKER_PREVIOUS_HEAD` beziehen, während der tatsächliche aktuelle Git-HEAD schon der Zielstand ist. Der Hook bindet deshalb **zwei verschiedene Identitäten**: `previous_head` an die echten alten Codepayloadbytes und `backup_head` an den tatsächlich frischen Archiv-source_head. Keine alte Codeidentität wird dem neuen Backup untergeschoben; keine Markerwerte werden geändert. Real ausgeführte Bash-Proben prüfen beide Fälle.

Erforderlicher Rollout bleibt beim Controller:

1. **CommitA:** Der noch installierte alte geprüfte Updater installiert über seinen bestehenden Ablauf einen reinen, kompatiblen Updater-Bridge. Keine neuen Kontextmodule vorab in den als Legacy zu prüfenden Appstand aufnehmen. Die hier neue Kontext-Testdatei gehört zum vollständigen Kontext-CommitB, nicht zu einer alten App, in der ihre D4-Imports noch fehlen. Kein manuelles Kopieren von Rootcode aus dem Appcheckout.
2. Tatsächlich installierten neuen Updater einschließlich root:root0755/nlink1 und Hash verifizieren. Der alte Updater selbst prüft noch keinen neuen D4-Hook; das wird nicht behauptet.
3. **CommitB:** Der nun installierte neue Updater prüft vollständige Kontextmodule/Daten nach diesem Vertrag und wendet erst danach den exakten autorisierten Mainstand an. Anforderungen/Unit-/Stagepins bleiben unverändert streng. Ein neuer unbekannter Pfadresolver oder unbekannte Verifierfähigkeit muss zuerst separat qualifiziert werden.

Controller-Nachricht 09.09.,15:57UTC (nicht durch diese Agentenarbeit frisch verifiziert): VPS-HEAD2ba3931, kein gesetztes BETBOY_RUNTIME_STATE_DIR, kein context_models.db, bestehender EnvFileweg, unveränderte Updater-/Stagepins, Appvenvdeserialize vorhanden. Der lokale 2ba3931-Gitbaum wurde zusätzlich read-only auf die neuen Kontext-/Tourstate-/CLI-Prefixe geprüft: keine Treffer. Das macht die erste Bridgevoraussetzung nachvollziehbar, ersetzt aber keine frische Prüfung direkt vor dem tatsächlichen Update. Die damalige separate Tennis-HTTP-Störung wird durch diesen Hook nicht behoben und nicht als gesund umetikettiert.

`prepare_challenge_migration_boundary` steht schon vor dem Hook. Bei vorhandenem `in_progress` darf selbst ein rein lesender D4-Fehler die ursprüngliche harte Recoverygrenze nicht zurücksetzen. Alte Code-/Rootfile-Recovery bleibt unverändert; **kein automatischer DB-/Geld-Rollback**. Ein manueller kompletter Restore braucht weiterhin passenden DBsatz+Key+Marker und zur beabsichtigten Codeversion passende unverändernde Prüfung. Dieser Commit fügt keine neue privilegierte Restore-CLI und keinen Live-Einzel-DB-Restore hinzu.

## Tatsächlich ausgeführte Tests und RED/GREEN

Auf allen lokalen Aufrufen: der vorhandene Quality-Python, `-B`, `pytest -p no:cacheprovider`, jeweils eigene `.pytest_tmp`-Basetemps. Keine Provider-/Netzwerk-/Produktionsdaten.

| Probe | Tatsächliches Ergebnis |
| --- | --- |
| Initiale echte Shell-Hauptreihenfolge | 2 funktionale REDs vor Hook. Die zugleich fehlenden Pythonfunktion-Fixtures waren Setupfehler, nicht23 zusätzliche Funktionsrepros. |
| Tatsächliche vierfeldrige Backupinventory + Env-Receipt-Reread | 2 RED vor Korrektur; danach grün. |
| Reale Shell-Resume-/Backup-HEAD-Trennung | 2 RED; erster Harnesslauf hatte fehlenden Git-Bash-PATH und zählt nicht als Produktrepro. Anschließend echte Assertions rot, danach grün. |
| Echte A1-Slotalias-CLI | 1 RED durch unzulässige eigene Slot<=Artefakt-Annahme; aktuelle echte CLI unverändert0, Hook danach grün. |
| Unit-Whitespace/Continuation in tatsächlichem Serviceabschnitt | 5 RED vor Korrektur, danach grün. Erster Testentwurf platzierte Records hinter Install und wurde vor dem maßgeblichen RED-Lauf korrigiert. Kein behaupteter installierter Pin-Bypass: der bestehende äußere Unitpin blieb zusätzlich wirksam. |
| Reale Shell-Kollektor-Timeout-Invocation | 1 RED vor eigenem Kollektordeckel; danach grün. |
| Fünf zusätzliche teilweise Kontext-Codeformen ohne Pfadvertrag | 5 RED/5 schon grün vor enger Legacyverschärfung; danach alle grün. |
| Hook-/Serverjobs-/D4-/Tenniscodec-/15K-Zwischenregression | 602 bestanden,10 erwartete Plattformskips,71 Untertests;55,06s. Stand vor den letzten Kollektor-/Teilcodegrenzen. JUnit `.pytest_tmp/context-hook-regression-14.xml`. |
| Eigener Vorfix-Fokus | **185 bestanden,18,56s**, `.pytest_tmp/context-hook-final-focus-19.xml`. |
| Vorläufiger Full17 | Absichtlich bei etwa10% über eigene Exec-Session abgebrochen, bevor die letzte Legacygrenze ergänzt wurde. Kein Full-PASS daraus. Read-only CIM-PIDinventar war nicht zugänglich, psutil nicht installiert; keine Eskalation/Installation/andere Prozessbeendigung. |
| Vorfix-Vollsuite Full20 | **4735 bestanden,18 erwartete Windows-/POSIX-Skips,97 Untertests,1211,31s**, Exit0. `.pytest_tmp/context-hook-final-full-20.xml`, SHA256 `5cc15b1a6911e9e55ea8ae912baac745ea905c4025103f508be5cd1952ee3b60`. Strikt Vorfix-Evidenz auf Updater3122364c…/Test12880ede…; keine Freigabe über den später gefundenen P2 hinweg. |
| Erneute Nachfix-Vollsuite Full26 | Beim Dokumentfreeze gestartet und noch nicht abgeschlossen; `.pytest_tmp/context-hook-fixed-full-26.xml`. Noch kein PASS daraus. Der Controller erhält das Ergebnis mit Hash separat, ohne dieses eingefrorene Dokument während des Nachreviews umzuschreiben. |

Positive echte Datenpfade: tatsächliches SQLite-Onlinebackup bei aktivem WAL mit altem offenen Leser und neuem B1-Receipt → einzelner ZIP-Member → echtes DELETEseal → tatsächliche D4-CLI im eigenen Subprozess. Live-Main/WAL/SHM und Archiv bytegleich; A1-Manifeste/Artefakte, B1-Zeilen und ATP/WTA-Identitäten gleich. Eigenes B3-Result nach Seal bytegleich; owning compute_once wird nur an separater wieder schreibbarer Testrestorekopie aufgerufen, nie an der updaterseitigen Prüfeingabe.

Negative echte Datenpfade: unbekannter Artefaktkind → tatsächliches CLI2, vom Hook abgelehnt; gelöschte physische Manifestreferenz → tatsächliches CLI1. Keine neue Referenz-/Openingsemantik wurde dafür erfunden. Archivduplikate, Traversal, Symlink-Member, falsche Größen/Hashes, Präsenzwiderspruch, Sidecars, Postread-Änderungen, neue Codebytes, Envdrift, duplicateJSON, output>1MiB, Timeoutexitcodes und geheime Memberöffnungen sind permanent geprüft.

Reale Bashharnesses ersetzen ausschließlich die externen Account-/Stage-/Applyseams; echte Shellfunktionen/Hauptfragmente werden direkt aus dem Updater geladen. Der Child-/Kollektorstatus wird mit echten Pythonprozessen/Pipelines geprüft. Unter Windows wird der Unix-Accountwechsel im Harness nachvollziehbar abgefangen; er ist **keine** Linuxprivilegienprüfung. Für echte Datenreplays ersetzen fixture-interne Metadatenseams nur root-Eigentum/DAC, nicht SQLite, Hash-/Memberprüfung, Verifier oder Dateien. Unix-Metadatenentscheidungen werden zusätzlich mit exakten stat-Decisiontables geprüft. Das muss der unabhängige Linuxlauf mit echten Rollen ergänzen.

## Unabhängiger P2 und enger TDD-Nachfix

Der vollständige unabhängige Originalbericht `.pytest_tmp/updater-independent-20260909/REPORT.md`, SHA256 `4dc77c150e82f9e76369cab76c7ec3ebd2fd44d990880aa3a9505ab32e303f80`, wurde vor dem Fix vollständig selbst gelesen. Alle fünf Originalprobe-Dateien bleiben bytegleich. Genau ein bestätigter P2: Python-`splitlines()` erzeugte aus einem Unicodezeichen im Wert `OTHER` eine vermeintliche neue Runtimezuweisung; unbeschränktes `strip()` behandelte Unicodeleerraum vor Namen/Werten wie Syntax. So konnte eine wirklich vorhandene Default-Kontext-DB fälschlich als fehlend am erfundenen Custompfad gelten.

Die stärkeren Originalfälle wurden unverändert selbst ausgeführt: Beide **echten** vollständigen Backupverifier akzeptieren das korrekte Testarchiv; die unveränderte **echte** D4-CLI lehnt seine vorhandene Datenbank wegen einer fehlenden A1-Referenz mitExit1 ab. Trotzdem erlaubte der Vorfixhook `not_present_legacy`. Das ist kein vorgetäuschter Hash-/Archivfehler. Voraussetzung ist eine ungewöhnliche root-eigene Konfiguration; kein unprivilegierter Zugriff, keine tatsächliche Produktionsausnutzung und keine Privilegieneskalation wurden behauptet.

Controllerfreigabe nach Lesen des Reports: nur ein gemeinsamer geschlossener ASCII-Recorddecoder, kein zweiter Systemdparser; Bare-CR ausdrücklich weiter unterstützen. Keine Unicode-Syntaxnormalisierung. Keine Interpretation/Änderung unverwandter Envwerte. Entsprechend wurde nur `configuration_lines` addiert und die vorhandenen `runtime_override`-/Unitrecord-Lesestellen darauf umgestellt; der gewählte Runtimepfad erhält einen gezielten Randwhitespacecheck. Kein Backup-/Rootaccount-/Key-/Marker-/Exitpolicy-/Pfadresolver-/Modellchange.

| Nachweis | Ergebnis und erhaltene JUnit-SHA256 |
| --- | --- |
| Unveränderte Original-REDs + Kontrollen vor Fix | **12 funktionale REDs,6 grün**,6,09s. `context-hook-owner-red-21.xml`, `46ccd71832c3d7d255c165d45fdfd834ed6d8cc3a9a8e521b3190fbf486b97fb`. |
|54 zusätzliche permanente Fälle vor Fix | **39 funktionale REDs,15 schon grün**,5,77s. `context-hook-permanent-red-23.xml`, `6b5c08db9542a84d505c136b06c6ea863de5026bb1d5121637595b8c13e12e76`. Der frühere eigene Red22 bleibt zusätzlich erhalten; die drei Unit-Kommentarfälle wurden vor diesem maßgeblichen Wiederlauf zu drei unterschiedlichen Separatoren präzisiert, keine Assertion abgeschwächt. |
|239 permanente +18 unveränderte Originalfälle nach Fix | **257 grün**,29,58s. `context-hook-fixed-green-24.xml`, `b11a4eaf3c43e566c5e9e7342b3818f48102418633676373fc958bcb2593ef9a`. |
|Independent Kontrollen + bestehende Serverjobs/D4/Tenniscodec/15K-Integrität | **388 grün,10 erwartete Plattformskips,39 Untertests**,28,62s. `context-hook-fixed-regression-25.xml`, `29cff11b6aa5723ecd8c0b30da1c98b4cf790f7beaca5122406acc75aa7831e5`. Genau ein explizites Deselect: der unveränderte historische Sourcepin-Test `test_exact_review_freeze_and_unmodified_old_functions`, der absichtlich3122364c… fordert. |

Der historische Sourcepin wurde weder umgeschrieben noch als neue funktionale Regression ausgegeben. Sein separater tatsächlicher Funktionsvergleich wurde nach dem legitimen Fix erneut ausgeführt:69 alte Bashfunktionen bytegleich, nur `preflight` ergänzt und exakt vier neue Top-Level-Funktionen; `bash -n` und `git diff --check` grün. Die vollständigen106 unabhängigen Funktions-/Typ-/Pipeline-/Recoverykontrollen ohne diesen alten Bytepin sind in der388er-Stufe enthalten.

Die54 neuen permanenten Fälle prüfen Separatoren in unquoted/quoted/comment-Records, Unicode vor dem Namen, Unicode an beiden Runtimepfadrändern mit/ohne beide Quotearten, ASCII-LF/CRLF/CR mit Nicht-ASCII-Buchstaben und unveränderten inneren Unicodeleerzeichen sowie dieselben echten Unitrecordflächen. Drei neue permanente echte Fullverify→D4-Fehlerfälle belegen Ablehnung bereits in `configuration`, ohne Daten/Archiv zu verändern oder Werte auszugeben.

Die neue permanente Archivhelperfixture hat einen formal gültigen **synthetischen**65-Byte-Key. Sie führt den unveränderten Inline-Gesamtverifier und die unveränderte `--verify-only --recovery-mode`-CLI aus. Ausschließlich unter Windows schließt eine tatsächliche `sqlite3.Connection`-Unterklasse beim Contextausstieg die Connection zusätzlich, damit der alte Tempcleanup nicht an Windows-Unlinkregeln scheitert. Queries, Daten, Commit/Rollback, Rückgabewerte und Prüfentscheidungen bleiben echt. Der originale erste Windows-Harnessfehler des Reviewers und dessen separat erklärter portabler Wrapper bleiben unverändert erhalten; kein Linux-DAC-PASS wird daraus abgeleitet.

Erhaltene maßgebliche Originalprobes:

- `test_unicode_environment_finding.py`: `6ea64de042564a7f7540fd4efc5a3615452f5767fff09aa29661a98254102133`.
- `test_unicode_full_backup_qualified.py`: `e434ed3c78978b5c31ce21a6d52ba9643d62469056f03a7de9a49c0e16755d4a`.
- `test_unicode_full_backup_portable.py`: `6839e61340b5db98a8f3ee8d8782e662031579fe2fa3c5dbd799e44afca29980`.
- `test_independent_updater.py`: `5713c18f62109e566da2a93d12e16b326ee9a12598c95ec78c1d262db7f8b1d5`.
- `test_full_backup_controls.py`: `daed3c7eaaf93b63130996c916f086f764e2af990882a4da9cf6ea37d2e8bfbd`.

Nachfix-Source/Test werden mit diesem Bericht für denselben unabhängigen Reviewer eingefroren. Ein freigegebener Parserfix ist keine Linux-, Produktions- oder empirische Gesamtfreigabe.

## Noch erforderlicher unabhängiger Review / Linuxmatrix

- Tatsächlich root:betboy0750/0440: betboy liest genaue Kopie und Manifestmodule; Schreib-, chmod-, Replace-, Hardlink-/Symlinkversuche schlagen fehl. Weder Appzugriff auf gesamtes ZIP noch zusätzlicher Key-/Backupservicezugriff.
- Tatsächliche Root-Inlinefunktionen nur mit stdlib und den festgelegten Systemprogrammen; App-/venvimports nur per runuser betboy. Keine pytest-/Appausführung mit Root oder betboy-backup zum Testen des Guards.
- Reales bestehendes Appvenv, vollständige Zielmodule, echte Deserializefähigkeit, isolierte Umgebungsvariablen, ausreichend Platz und Produktionsdaten <=64MiB; tatsächliche Prüfung kann Timeout erreichen und muss dann abbrechen.
- Alter installierter Updater→BridgeA→neuer installierter Updater→KontextB, inklusive Marker-/Resume-/Recoveryfehlern. Das ist hier spezifiziert und im lokalen Ablauf geprüft, **noch nicht installiert ausgeführt**.
- Bisherige Ledger-/Backup-/Stage-/Unitpins unverändert. Ein freigegebener mechanischer Hook ist keine globale D3-/D2-/Empirik- oder Benutzeroberflächenabnahme.

## Eingefrorene SHA256

| Datei | Rohe SHA256 |
| --- | --- |
| `deploy/update_server.sh` | `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f` |
| `tests/test_context_update_hook.py` | `8e18e7e17622f357810a00211ce4e4bcf19944ce85777d39c3c37897f1fb860b` |
| Unverändert `scripts/stage_runtime_databases.py` | `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` |
| Unverändert `deploy/systemd/betboy-backup.service` | `922352a5d3c883cc671da419c5d3fa589cbe9cd025f32d4c4d9f7b6a9648edb8` |
| Unverändert `deploy/bootstrap_server.sh` | `eb2cec227d710156f960ba78a620c5bdfe4bd97cd95ba2deb33a3c120fd5dec6` |

Nur drei eigene Dateien gehören zum fokussierten Commit: Updater, neue Tests und dieser Bericht. Dieses Dokument kann nicht seinen eigenen finalen Hash enthalten; der wird nach Abschluss zusammen mit der Commit-ID an den Controller geliefert.
