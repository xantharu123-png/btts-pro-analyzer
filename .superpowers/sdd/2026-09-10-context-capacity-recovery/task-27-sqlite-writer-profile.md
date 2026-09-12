# Task 27 — neues kontrolliertes SQLite-Writerprofil

Stand: 12. September 2026. Enger lokaler Implementierungsstand, keine native
C6-Abnahme, Produktionsfreigabe, Migration oder Änderung alter Writerpfade.

## Ergebnis und Besitzgrenze

Implementiert ist `fresh-single-main-v1` in der neuen Datei
`context_storage_v2/sqlite_profile.py`, mit eigenen Tests in
`tests/test_context_storage_sqlite_profile.py`. Keine bestehende Produktdatei,
TrackedConnection-Klasse, alte History-/Tennis-Datei, Git- oder Serveroperation
wurde durch diesen Task geändert. Die genehmigte C-Entscheidung, die exakten
refs-/snapshots-Anforderungen und Task 22 wurden vor der Umsetzung abgeglichen.
Das historische Freigabelabel in der C-Vorlage wurde nicht als Rücknahme der
explizit bereits erteilten Nutzerfreigabe behandelt.

Finaler lokaler Lauf: **359 bestanden, 0 Fehler, 0 übersprungen**, davon 93 neue
Profiltests sowie 99 refs-, 96 snapshots- und 71 ref_chunks-Tests. Konsole 30,66 s;
JUnit 30,632 s. Das sind funktionale lokale Tests, kein gemessener nativer
RSS-/CPU-/Platten-Höchststand und kein kompletter Corpuslauf.

## Abgestimmte Integrationsschnittstelle

```python
from context_storage_v2.sqlite_profile import SQLiteWriterPlan, open_fresh_writer

plan = SQLiteWriterPlan(main_cap_bytes=256 * 1024**2)
# Zuvor: NativeOwner/WorkspaceBudget reserviert ALLE Dateien/Inputs/Fehlversuche,
# setzt native Grenzen und stellt den privaten exklusiven Namespace her.
with open_fresh_writer(absolute_new_path, plan=plan, limits=limits) as writer:
    connection = writer.connection  # type(connection) is TrackedConnection
    # Bestehende C-Module nutzen die bereits gehaltene Transaktion/Savepoints.
    build_complete_private_output(connection)
    writer.check_profile()
    writer.commit_build()  # danach Cursor, Blobs, Verbindung und eigener FD zu
# Danach: vollständige äußere Coverage/Root-Seals/Publikation, nicht hier.
```

Der Handle hat `connection`, `path`, `plan`, `closed`, `committed`,
`check_profile()`, `commit_build()` und `close()`. `check_profile()` liefert eine
begrenzte `SQLiteProfileReadback`-Beobachtung mit Profil-/SQLite-Version,
TEMP_STORE-Compilewert, Transaktionsepoche, Seitenzahl, beobachteten logischen
Main-/Journal-Dateilängen und Cache-Spill-Schwelle. Dies ist kein B-/D2-/HMAC-,
Quellen-, Modell- oder Publikationsnachweis.

Der einzige erfolgreiche Build-Commit schließt anschließend tatsächlich die
normal erzeugten SQLite-Handles und die Verbindung. Ein zweiter Commit ist ein
Fehler. Kontextende ohne expliziten Commit rollt zurück; es gibt keinen implizit
erfolgreichen Kontext-Commit, Resume, Dateiersatz oder Lösch-/Cleanup-API.
Auch nach einem Fehler nach bereits beendetem Commit bleibt der Dateiinhalt
erhalten, aber der Handle meldet keinen Erfolg. Ein bereits unzulässig vom
Caller durchgeführter Commit ist nicht nachträglich rückgängig zu machen.

## Konfiguration und Bindung

| Eigenschaft | Neuer Profilpfad |
| --- | --- |
| Anlage | Bestehender absoluter privater Elternpfad; Main und drei bekannte Sidecar-Namen müssen fehlen; O_CREAT/O_EXCL, Modus 0600, nicht vererbbarer FD, kein Überschreiben |
| Gehaltener FD | Von exklusiver Anlage bis Abschluss; fstat/lstat-Inode/Device/Größe, Elternidentitäten und gewöhnliche Dateiform werden wiederholt geprüft |
| Erste SQL | Ausschließlich `PRAGMA temp_store=MEMORY`; anschließend Readback 2 und genau ein Compilewert TEMP_STORE=1/2/3, noch vor jedem Öffnen des TEMP-Schemas |
| Main-Zuordnung | database_list muss den erwarteten Main-Pfad ohne ATTACH ausweisen; anfangs leer; nur leerer interner TEMP-Namespace zulässig |
| Atomizität | Normales DELETE-Journal, synchronous=FULL, cache_spill=ON, keine Atomizitätseinschränkung an Quell-/Alt-/publizierten Daten |
| Seiten | Explizite Zweierpotenz 512–65536; Main-Decke besteht aus ganzen Seiten; max_page_count exakt gelesen |
| Cache/Mappings | Explizit 1–8192 KiB negativer cache_size; mmap_size=0; Cache-Spill-Schwelle bleibt auf dem Erstreadback |
| Weitere Grenzen | SQLITE_LIMIT_ATTACHED=0, SQLITE_LIMIT_WORKER_THREADS=0, threads=0, busy_timeout=0 |
| Weitere Konfiguration | auto_vacuum=NONE, UTF-8, locking_mode=NORMAL, query_only=OFF, journal_size_limit=0; Defensive aktiv, Trusted Schema und Extension-Laden deaktiviert/geprüft |
| Transaktion | Explizites BEGIN IMMEDIATE vor jeder DDL; genau eine erfasste Build-Epoche; normale Modul-Savepoints erlaubt |
| Unterhandles | Höchstens 256 schwach registrierte normale Cursor-/Blob-Objekte; vor Abschluss über ihre echten SQLite-close-Methoden geschlossen |

Plan und Limits sind exakte Typen und werden mit festen Validatoren erneut
geprüft; auch nur enger gesetzte C-Limits müssen passen. Größere/gefälschte
Werte, geänderte Fabriken, Grenzen, Konfigurationen, explizite TEMP-Objekte,
beobachtete Pfad-/Journalwechsel oder verlorene Transaktion beenden den Handle.
Dateiverknüpfungen, Reparse-Punkte, unbrauchbare Null-Inodeidentität und
vorhandene Sidecars werden nicht als eigene neue Datei übernommen.

## Tatsächlich gefundene Grenzen und Korrekturen

1. **WAL-Testannahme:** Der erste Lauf hatte 77 bestandene Tests und einen roten
   Test. SQLite 3.53.1 liefert für den WAL-Wechsel in dieser gehaltenen
   Transaktion den unveränderten Readback `delete`, statt eine Ausnahme zu
   werfen. Der Test prüft jetzt genau dieses Verhalten. Eine erfolgreiche
   WAL-Umschaltung wurde nicht beobachtet oder akzeptiert. Das ursprüngliche
   XML `task27-profile-01.xml` bleibt erhalten.
2. **Echter close_v2-Rest-FD:** Eine zusätzliche kleine Probe hielt nach einem
   SELECT noch einen Cursor, commitierte und rief Connection.close auf. Die
   Python-Verbindung war geschlossen; eine anschließende Dateiumbenennung
   scheiterte aber tatsächlich mit Windows WinError 32. Der offene Cursor ließ
   den nativen SQLite-FD weiterleben. Der neue Profilpfad registriert deshalb
   normale Cursor-/Blob-Erzeugung pro eigener exakter TrackedConnection und
   schließt diese zuerst. Keine bestehende Klasse wurde geändert. Die echten
   Rename-Proben nach Commit und Rollback bestehen jetzt auch mit noch von
   Caller-Variablen gehaltenem Cursor/Blob und einem benutzerdefinierten
   TrackedCursor-close-Override. Die allgemeine Deferred-Close-Eigenschaft ist
   auch im offiziellen [SQLite-Close-Vertrag](https://www.sqlite.org/c3ref/close.html)
   beschrieben. Die anfängliche Probe bleibt unter
   `.pytest_tmp/task27-fd-probe-omz1m5kt/` erhalten.
3. **Pfadöffnung ist kein FD-gebundenes SQLite-Öffnen:** Der O_EXCL-FD wird nicht
   geschlossen, um anschließend unbeobachtet den Pfad erneut zu öffnen.
   Trotzdem nimmt stdlib sqlite3 einen Pfad/URI, nicht diesen FD. database_list
   liefert keinen VFS-FD. Somit gilt ausdrücklich keine race-free-/ABA-Zusage.
   Die negative echte Austauschprobe vor erster SQL schließt wegen Windows'
   DELETE-Sharing ausdrücklich den gehaltenen FD als injizierten Fehler,
   tauscht dann den Pfad tatsächlich gegen Fremdbytes aus und weist null SQL
   sowie unveränderte Fremdbytes nach. Separate deklarierte lstat-Fixtures
   prüfen Inode/Device/Linkzahl/Reparse-Abweichungen bei weiter gehaltenem FD.
   Sie werden nicht als echte Linux-Mount-/ABA-Probe ausgegeben.

## Logische Planung, ausdrücklich nicht native Quote

Für `M = plan.main_cap_bytes` liefert der Plan `max_page_count = M/page_size`,
`journal_cap_bytes = M` und `logical_reserved_bytes = 2*M`. Der Main-Slot wird
als aktiver Input, der Journal-Slot als zusätzliche QA-Datei reserviert. Alle
anderen Inputs, Indizes, Fehlversuche, Archive, Ausgaben und Metadaten kommen
global zusätzlich dazu. Ein allein bereits 8-GiB-großer Slotplan lässt daher
keine Reserve für diese anderen Dateien und ist global nicht automatisch
zulassungsfähig.

Die Journal-Decke ist **nur eine Deklaration für den NativeOwner**: Diese Datei
installiert kein RLIMIT_FSIZE. max_page_count begrenzt Main-Seiten, nicht das
Journal. journal_size_limit=0 ist keine Spitzenallokationsquote. Normaler
Cache-Spill bleibt aktiv; es wird kein frisch erzeugtes 512-Byte-Journal als
bewiesener universeller Journal-Höchstwert ausgegeben. Die Unterscheidung der
SQLite-Pragmas steht im offiziellen [PRAGMA-Vertrag](https://www.sqlite.org/pragma.html).

Ebenso beweisen Dateilängen keine physische ext4-Allokationshülle, keinen
Metadatenbedarf, keine Zahl aller künftig erzeugten Dateien und keine
Freigabe unlinked/offener Dateien. Die vollständige reservierte zukünftige
Eigennutzung plus 4 GiB muss vor neuer Zulassung gegen tatsächlichen freien
Platz passen; laufend neu beobachteter Reserveverlust bedeutet Test-STOP. Der
neue Profilcode führt diese globale Zulassung/Überwachung nicht selbst durch.

Der äußere Owner muss weiterhin native CPU 300 s, AS 2 GiB, RSS <1 GiB,
Ausgabe 1 MiB und globale Kosten/Deadlines durchsetzen/messen. Sortierung und
Statement-/Savepoint-Arbeit in MEMORY sind kein höheres RAM-Budget: OOM ist
Fehler, kein Anlass für FILE-Fallback oder Lockerung. Die vorhandenen
History-/Tennis-FILE-Verbindungen bleiben unverändert; dieser Task integriert
sie nicht. Auch weitere Source-Verbindungen müssen im späteren geschlossenen
Native-Workflow gesondert korrekt konfiguriert werden.

## Geschlossener Caller bleibt äußere Pflicht

Ein offengelegtes Python-Objekt ist keine geschützte Capability. Der Caller
kann Methoden/Callbacks ersetzen, Basis-C-Methoden direkt aufrufen, zusätzliche
Verbindungen öffnen, backup/serialize/Extension-/Dateioperationen anstoßen oder
private Felder verändern. Es wird kein gegenteiliges Schutzversprechen gemacht.
Die normale API und ihre erfassten Epochen werden geprüft; eine kurzzeitige
Manipulation mit anschließender Rückänderung ist dadurch nicht generell
ausgeschlossen. NativeOwner muss deshalb den tatsächlich ausgeführten SQL-/
Writerpfad, Einzelwriter und exklusiven Namespace schließen und prüfen.
Insbesondere sind zusätzliche Commits, ATTACH/Superjournal, VACUUM/INTO, WAL,
unregistrierte Cursor/Blobs/Backups und zusätzliche Dateipfade keine erlaubte
Profilnutzung. SQLite erlaubt manche Operationen während BEGIN nicht; diese
Differentiale ersetzen keine vollständige Closure. Der offizielle
[Python-sqlite3-Vertrag](https://docs.python.org/3.12/library/sqlite3.html) beschreibt
die normalen mutierbaren APIs und Transaktionssteuerung, keine Python-Sandbox.

Der Profilcode löscht keine Main-/Alt-/Fremddatei. SQLite darf bei normalem
DELETE-Journal-Commit/Rollback sein eigenes Journal entfernen; das ist keine
forensische Journal-Aufbewahrungszusage. Der neue fehlgeschlagene Main bleibt
erhalten und erhält kein neues Budget durch erneuten Versuch.

## Lokale Evidenz und Reproduktion

Runtime: neues QA-venv `.pytest_tmp/qa-python312-c-01/Scripts/python.exe`,
Python 3.12.14, SQLite 3.53.1, pytest 9.1.1, Windows. Keine SSH-/VPS-Ausführung.
Keine Übertragung von Laufzeitdatenbanken oder Schlüsseln. Die kleinen
SQL-/Snapshot-Fixtures sind lokal erzeugte Testdaten.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider `
  tests/test_context_storage_sqlite_profile.py tests/test_context_storage_refs.py `
  tests/test_context_storage_snapshots.py tests/test_context_storage_ref_chunks.py `
  --basetemp=.pytest_tmp/task27-profile-bt-05 --junitxml=.pytest_tmp/task27-profile-05.xml
```

Diese Pfade sind **bereits belegt**; eine Wiederholung braucht neue,
nie zuvor existierende Basetemp-/XML-Namen. Keine Evidenz wurde gelöscht.

Der finale Lauf umfasst unter anderem FIRST-SQL/BEGIN/COMMIT-Trace, zwölf
Page-/Cache-Kombinationen, falsche Limits/Build-Compilewerte, fremde initiale
Dateien/Sidecars, verspätetes Eintreffen vor O_EXCL, falsches SQLite-Main,
echte Hardlinks, registrierte Handle-Abschlüsse, komplette normale
Savepoint-Rollbacks und mehrzeilige UNIQUE-Statement-Rücknahme, einen echten
SQLITE_FULL mit vollständigem Auto-Rollback, Commit-BUSY sowie Fehler nach
Commit. Ein 6000-Zeilen-Sortiervergleich benutzt tatsächlich TEMP B-TREE und
vergleicht vollständige geordnete Bytes gegen einen eigenen FILE-Temp-
Referenzlauf. Named-file-Checks sind ausdrücklich kein Nachweis über native
RSS oder unsichtbare/unlinked Tempdateien. Bestehende owner-erzeugte
Snapshot-/Ref-Byte-Differentiale funktionieren in derselben neuen Build-Epoche.

SHA-256 des eingefrorenen Stands:

- `context_storage_v2/sqlite_profile.py`:
  `05898adf9782ff06e2edcf33d45c94dd6ecce232ddba1f81ffcfaf65fca3d8bc`
- `tests/test_context_storage_sqlite_profile.py`:
  `7cf07bfa2ae418b676e8a53bb074994c022c50fa65d364429903a37e5e159292`
- `.pytest_tmp/task27-profile-05.xml`:
  `80d52a3e42f9a0c6108d320fdd4cc80581460129e19b6c5894638d90392fda97`

Nächster ausführbarer Schritt: unabhängiges Review dieses begrenzten neuen
Profils und bewusste Root-Integration mit globalem WorkspaceBudget und
Native-Prozess-/Dateiowner. Danach erst die in Task 22 genannten nativen
SQLite-/Datei-/RSS-Grenzprofile und vollständige C6-Bestände. Keine zusätzliche
Nutzerentscheidung ist für diesen bereits genehmigten technischen Schritt
erforderlich; kein Gesamtabschluss oder Rollout wird daraus abgeleitet.
