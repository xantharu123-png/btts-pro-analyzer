# Task 22 — kontrollierter SQLite-Writer und globales Plattenbudget

Datum: 2026-09-12. Unabhängige Architekturprüfung durch `c_source_adapter`.
Auftrag: Punkte 1–4 des freigegebenen C/B-Gesamtintegrationspfads; keine
Produkt-, Server-, Git-, Quellbestands- oder Modelländerung. Diese Datei ist
das einzige neu geschriebene Artefakt dieses Reviews. Keine eigenen SSH-Aufrufe,
keine native Schreibprobe, kein Corpus-/Deploymentlauf und keine neue Infrastruktur.

## Ergebnis

**Ein enger, ausführbarer Kandidat ist vorhanden, die globale Integration aber
noch nicht implementiert oder abgenommen.** Empfohlen wird zunächst ein bewusst
konservatives Zwei-Datei-Profil je schreibendem Worker: genau eine neue private
SQLite-Hauptdatei, normales DELETE-Rollback-Journal, effektives
`temp_store=MEMORY` vor dem ersten Statement mit temporärem Bedarf, ein
Aufbau-Commit, hartes `RLIMIT_FSIZE` und vorab reservierte Main-/Journalslots.
Temporäre SQL-Arbeit bleibt damit unter den unveränderten Speichergrenzen;
Speichermangel ist ein fehlgeschlagener Lauf, kein Grund zur Grenzerhöhung.

Für dieses geschlossene Profil lässt sich eine obere Grenze der logischen
Dateilängen ohne Journal-Größenschätzung beweisen. Die Zulassung muss zusätzlich
die physische Allokationshülle des tatsächlichen Dateisystems und alle anderen
QA-Artefakte berücksichtigen. Ein beliebiger Sicherheitsaufschlag ohne
Herleitung ist noch kein Beweis dieser physischen Hülle.

Die echte freie Reserve wird **beobachtet und fail-closed geprüft**: vor jeder
Zulassung stehen vollständig reservierte zukünftige eigene Bytes plus 4 GiB
unter dem aktuell wirklich freien Platz; während des Laufs erfolgen erneute
Prüfungen. Jede beobachtete Unterschreitung, Messlücke oder ungebundene Datei
verhindert Freigabe. Daraus wird keine Garantie gegen beliebige fremde
Root-/VM-/Dateisystemschreiber zwischen Messpunkten abgeleitet. Eine solche
stärkere Allwriter-Garantie ist nicht implementiert und wird hier **nicht** als
neue zwingende Infrastrukturvoraussetzung in den C-Vertrag hineingelesen.

## 1. Gelesener Vertrag und tatsächlicher Ausgangsstand

Vollständig gelesen: C-Entscheidung, B-Prüfnachweisspezifikation, neuer
Gesamtintegrationsplan, C-Konstanten, `copying`, `refs`, `history`, `tennis`,
`snapshot_source` und `context_runtime_transaction`. Ergänzend gelesen:
Task-18-Copy-Review, vorheriger Kapazitätsplan und die Referenz-CLI.
Historische „noch nicht freigegeben“-Formulierungen ändern nicht die durch
Root übermittelte ausdrückliche C/B-Ausführungsfreigabe.

Unverändert gelten gemeinsam:

- maximal 4 GiB aktive C-Eingaben einschließlich benötigter eigener
  Indizes/Blöcke/Manifeste; kein 4-GiB-Budget pro Datei;
- maximal 8 GiB gesamte neue QA-/Build-/Output-/Spill-Belegung einschließlich
  Archive, fehlgeschlagene Versuche, noch benötigte Rückweg-/Generationsdateien;
- zusätzlich mindestens 4 GiB tatsächlich frei; belegte Reservefiles sind
  belegter Platz, nicht „freie Reserve“;
- pro Worker CPU 300 s hart, AS 2 GiB, RSS strikt unter 1 GiB, Ausgabe insgesamt
  höchstens 1 MiB; Vorbereitung insgesamt 1800 CPU-/3600 Gesamtsekunden über
  alle Teile und Versuche; finale Pflichtläufe jeweils höchstens 240 CPU/Wand;
- 1-GiB-Tourhistorie, 16-MiB-Blockhülle und bestehende Alt-/RAM-Verträge bleiben
  getrennte Gates. Bytes transportieren bedeutet keine D2-/Modell-/HMAC-Wahrheit.

### Lokale Bytebindung dieses Reviews

Hashes wurden lesend aus dem aktuellen Arbeitsbaum erhoben; parallele spätere
Änderungen erfordern einen erneuten Gegencheck.

| Gelesene Datei | SHA-256 |
| --- | --- |
| [C-Entscheidung](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/docs/superpowers/specs/2026-09-12-kontextspeicher-entscheidung.md) | `08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba` |
| [B-Prüfnachweise](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/docs/superpowers/specs/2026-09-12-versionierte-pruefnachweise.md) | `498e63c5641adaccdd4d284fa9b57ad93c02ba834e9abd6bf4064636d6b12da1` |
| [Gesamtintegrationsplan](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/docs/superpowers/plans/2026-09-12-kontextspeicher-gesamtintegration.md) | `6538438d64f5d9ba9a7ae66fd9bfcbcc1c24a2ff21266b4ec27361b638d94a67` |
| [contracts.py](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/context_storage_v2/contracts.py) | `d0c8d94c89a608fc7b3c59755cbe97c76ec79d66e53d2bb235608f341364fcf3` |
| [copying.py](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/context_storage_v2/copying.py) | `27d4c8887756aeeb8f8041744814b6c9d09e576427e8f62ef9ef09c64ba129be` |
| [refs.py](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/context_storage_v2/refs.py) | `e80492be96ea0aacd5bb2038018c90bf8201d3e4a616d2574c456d5f9899cb2b` |
| [history.py](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/context_storage_v2/history.py) | `aab750cefacbfcdd9c3165f08a8842d6f4dd378c7832bc1c44a8c170969e7c3e` |
| [tennis.py](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/context_storage_v2/tennis.py) | `aa94cd18b1280544f47e8c9e9a9a2b25ebf78c42a333c7e713a2db9b19c60d2d` |
| [snapshot_source.py](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/context_storage_v2/snapshot_source.py) | `f080d605dbbaf45baae197f9f948539d8ff832a2b294327cdc845d4d6df31753` |
| [context_runtime_transaction.py](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/context_runtime_transaction.py) | `ecec258d9b67964da29b9da91859c5d80ed24100765b04e14db5269b8d4e8e5b` |

### Warum die jetzigen Einzelprüfungen nicht genügen

| Pfad | Tatsächliches Verhalten | Erforderliche Integration |
| --- | --- | --- |
| C1-Copy | Gehaltene rohe FDs, begrenzte Kopierblöcke; `capacity_check` rechnet Restkopie plus benannte Workspace-Dateien. Fehlerkopien bleiben erhalten. | Kopie **vor** Anlage global reservieren; auch außerhalb dieses Unterverzeichnisses liegende Archive und frühere Versuche zählen. Diskwalk ist Reconciliation, keine Durchsetzung. |
| C2-Refs | Caller-Transaktion, verschachtelte Savepoints, Main-Staging-PK und nachfolgendes Staging-DELETE; `max_page_count`, Cache und `mmap=0` werden geprüft. | Neuer kontrollierter Verbindungsowner; dieselben globalen Slots statt eigener 4-/8-GiB-Hülle je Verbindung. Temp-/Journalprofil muss vor Beginn feststehen. |
| C3-History | Eigene neue Main-DB, DELETE und `temp_store=FILE`; Schema/Indizes werden **vor** dem expliziten `BEGIN` erstellt; ein Daten-Commit. | Für den streng ersten Aufbau-Commit muss auch Schemaaufbau in dessen Transaktion liegen. Gegenwärtiger Schema-Altumfang ist nicht null. Neue, gesondert geprüfte Factory erforderlich. |
| C3-Tennis | Neue Main-DB, DELETE/FILE, Tabellen im `BEGIN`; ein Commit; Refsets in verschachtelten Savepoints. `_union_refs` verwendet UNION, DISTINCT, ORDER BY. | Diese Ausdrücke können echte temporäre Arbeit erzeugen. Effektives MEMORY oder ein separat bewiesenes anderes Profil; keine Folgerung „Index vorhanden, also niemals Spill“. |
| C2b-Source | Äußerer Build-Savepoint, Zeilen-/Ref-/Snapshot-Savepoints; caller-owned Output-Transaktion; kein Commit. | Bereits vor `initialize` und Source-Inventur eingerichteter Owner. Vollständige Raw-Abdeckung und unbekannte Raw-Abhängigkeiten bleiben erhalten und aktiv budgetiert. |
| Reader | History/Tennis öffnen eigene RO-Verbindungen; SQL-Abfragen können trotzdem temporäre Arbeit brauchen. | MEMORY auch an **allen** zulässigen Reader-Verbindungen vor dem Pinning; readonly der Hauptdatei beweist nicht readonly aller SQLite-Temporärpfade. |

SQLite dokumentiert mehrere Arten temporärer Dateien; Sortierung,
Materialisierung und Statement-Rollback sind nicht auf `main-journal`
beschränkt. Kleine Läufe können in Cache bleiben und beweisen daher keinen
spillfreien Großlauf. Die Details temporärer Dateien sind zudem kein für alle
Versionen zugesicherter API-Vertrag. [SQLite: Temporary Files](https://www.sqlite.org/tempfiles.html).

`max_page_count` begrenzt die betreffende Datenbank, nicht den Gesamtauftrag.
[SQLite: Limits](https://www.sqlite.org/limits.html).
`journal_size_limit` begrenzt verbleibende Journalgröße nach Abschluss/Reset,
nicht deren aktiven Peak. Cachegrößen sind kein Gesamt-RAM-Limit;
`cache_spill=OFF` kann schmutzige Mainseiten im RAM festhalten und ist hier
keine Lösung. [SQLite: PRAGMA](https://www.sqlite.org/pragma.html).

## 2. Vorschlag: geschlossenes Profil `fresh-single-main-v1`

Dies ist ein Implementierungsvorschlag, kein bereits vorhandener API-Aufruf.

1. Root-Coordinator bindet Eingaben, Implementierung, Interpreter,
   SQLite-Binary/Source-ID/Compile-Optionen, VFS, Writer-SQL/API-Katalog,
   Dateisystem und Budgetzustand **vor** dem Workerstart. Root importiert dabei
   kein Produkt. Der Worker ist unprivilegiert, ohne Netzwerk/App-Secrets;
   Runtime und Eingaben bleiben root-versiegelt und nur lesbar.
2. Pro Worker genau ein neuer privater, noch nie benutzter Mainpfad. Keine
   Übernahme vorhandener Hot-Journals, keine Wiederaufnahme eines halben Stores,
   keine zweite schreibende Connection und keine Datenbank-Attachments. Andere
   Eingaben sind eigenständige exakt gebundene RO-Verbindungen.
3. Vor erstem SQL-Workload: Main-Pagegröße fest, `journal_mode=DELETE`,
   `synchronous=FULL` oder strenger, `temp_store=MEMORY`, begrenzter negativer
   Cache, `mmap_size=0`, `auto_vacuum=NONE`, SQLite-Workerthreads 0,
   Attach-Limit 0. Alle relevanten Werte tatsächlich zurücklesen; fehlende
   Optionen/unerwartete Compile-Overrides sind STOP. Auf den Quell- und
   publizierten Dateien werden keine Persistenz-/Journalmodi verändert.
4. SQLite-Limit `max_page_count = floor(main_cap / page_size)`; Kernel
   `RLIMIT_FSIZE=(file_cap,file_cap)` gilt bereits vor Produktimport/Dateianlage.
   `main_cap <= file_cap`. `file_cap` ist eine Worker-Profilgröße, niemals
   automatisch der gesamte 8-GiB-Workspace. Kein Privileg zum Wiederanheben.
5. Ein explizites `BEGIN` **vor** den ersten Schema-DML/DDL-Schreibvorgängen;
   genau ein abschließender Commit nach vollständig erfolgreichem Aufbau.
   Vorhandene Savepoints/Statement-Rollbacks bleiben semantisch erhalten.
   Kein `executescript`, keine impliziten Teilcommits durch Contextmanager,
   `autocommit`-/`isolation_level`-Änderung oder Wiederöffnung. Nach Fehlern
   keine Weiterarbeit mit einem automatisch zurückgerollten Epochzustand.
6. Nach Commit: sämtliche Cursor/BLOB-/Connectionhandles schließen, Worker
   beenden und vollständig reapen; erst anschließend Owner-Reconciliation,
   vollständige RO-Validierung und B-Publikationsvoraussetzungen prüfen.
   Persistierende Ausgabe ist weiterhin unpubliziert. Kein selbst gesetztes
   Cache-/Besitzflag und keine Teilfreigabe.

Python-Transaktionsdetails sind relevant: `executescript()` kann unter Legacy-
Transaktionssteuerung vorab committen; `setconfig()` betrifft DBCONFIG, nicht
beliebige globale SQLite-Konfiguration. Deshalb weder eine versteckte
`SQLITE_CONFIG_STMTJRNL_SPILL`-Python-API erfinden noch bestehende
Lifecycle-Garantien durch eine ungeprüfte Wrapperklasse umgehen.
[Python 3.12: sqlite3](https://docs.python.org/3.12/library/sqlite3.html).

### MEMORY schließt Statement-/Sortierspill hier tatsächlich ein — mit Bindung

Die offizielle SQLite-3.45.1-Quelle verbindet Compile-Option und
`temp_store`: bei `TEMP_STORE=1` und Readback 2 ist
`sqlite3TempInMemory()` wahr. Die Funktion benennt ausdrücklich transiente
Pager und Statementjournale. [SQLite 3.45.1: main.c](https://raw.githubusercontent.com/sqlite/sqlite/version-3.45.1/src/main.c).

Der Btree-Transaktionsstart reicht genau diesen Wert an
`sqlite3PagerBegin()` weiter. [SQLite 3.45.1: btree.c](https://raw.githubusercontent.com/sqlite/sqlite/version-3.45.1/src/btree.c).
Der Pager erzwingt für neue Subjournale bei diesem Flag den In-Memory-Pfad;
ein schon vorher offenes Subjournal ist eine ausdrückliche Ausnahme.
Deshalb muss das Profil an einer neuen Connection vor jeder Temp-Arbeit
stehen, nicht nachträglich auf einen laufenden Writer aufgesetzt werden.
[SQLite 3.45.1: pager.c](https://raw.githubusercontent.com/sqlite/sqlite/version-3.45.1/src/pager.c).

Auch der Sorter aktiviert seinen Disk-PMA-Schwellwert nicht im effektiven
In-Memory-Modus. Das ist ein versionsgebundener Gegencheck, kein allgemeines
Versprechen über unbekannte VFS/Extensions/SQLite-Builds.
[SQLite 3.45.1: vdbesort.c](https://raw.githubusercontent.com/sqlite/sqlite/version-3.45.1/src/vdbesort.c).

**Wichtig:** `temp_store=MEMORY` ist nicht `journal_mode=MEMORY`. Die
dauerhafte Main-Transaktion behält ihr normales Disk-Rollback-Journal und
ihre Synchronisation. Explizite Stagingtabellen bleiben in `main` auf Platte.
Lediglich interne temporäre Strukturen/Statement-Rollbacks liegen im RAM.
Bestehende 64-MiB-Altmaterialisierung und andere RAM-Verträge werden nicht
erhöht. Große UNION-/DISTINCT-Arbeit oder tiefe/lange Savepoints können deshalb
ehrlich an Speichergrenzen scheitern.

### Gegenfälle, die das Profil ausschließen muss

| Gegenfall | Ausschluss/Abbruchbedingung |
| --- | --- |
| `VACUUM`, `VACUUM INTO` | Im geschlossenen SQL-Katalog nicht erlaubt; nicht auf das Scheitern innerhalb einer Transaktion als einzige Barriere verlassen. VACUUM kann zusätzliche Datenbankkopien erzeugen. [SQLite: VACUUM](https://www.sqlite.org/lang_vacuum.html). |
| `ATTACH`/`DETACH`, Superjournal | Attach-Limit 0, Authorizer-DENY, `database_list` und feste Connectionanzahl gegenprüfen. Keine multi-database Schreibtransaktion. |
| WAL/SHM/Checkpoint | Kein WAL-Mainstore; keine PRAGMA-Modusänderung, kein checkpointfähiger separater Writer. Standalone RO-Inputs bereits vor SQLite-Öffnung prüfen. |
| Weitere Commits oder neue Mainpfade | Owner-Zustandsautomat und vollständiger Callgraph; verbotene Methoden/SQL brechen ab. Ein vorhandener Schema-Commit ist ein tatsächlich anderer Initialzustand, nicht wegzudokumentieren. |
| Backup-/Restore-Ziel, `serialize`/`deserialize`, zweite Connection | Nicht durch SQL-Authorizer vollständig erfasst; aus diesem Worker-API-Katalog ausgeschlossen. Separate benötigte Kopien erhalten vorher eigene vollständige Slots. |
| Virtuelle Tabellen, Extensions, UDFs mit Nebenwirkungen | Nicht registrieren/laden; Schema-/Funktionskatalog schließen; unbekannte Pfade STOP. `trusted_schema=OFF` allein ersetzt diese Schließung nicht. |
| Beliebiges Python-/Bibliotheks-I/O, Logdateien, Bytecode, Dumps | Versiegelter Import-/API-Closure, `-B`, keine freien Log-/Tempziele, stdout/stderr nur kontrollierte Pipes, keine Coredateien. Nicht „alles unter /tmp“ als zulässig erklären. |
| Benutzer-Temp-Verzeichnis/Umgebungsvariable | Kein Mengenbeweis und bei SQLite mit Ausweichpfaden kein sicherer vollständiger Pfadbeweis. Nicht als Quote zählen. |
| Open-unlinked, Rename/Reopen, IPC-FD-Übergabe | Keine Freigabe/Slotwiederverwendung solange ein Prozess den alten Inode halten kann; keine FD-Weitergabe. Unbekannte Lebensdauer bleibt voll reserviert. |

Der SQL-Authorizer ist eine zusätzliche Schranke beim Vorbereiten von
Statements, kein Hook vor jedem ausgeführten Schreibvorgang. Eine dynamische
Commit-Zählung allein im Authorizer ist wegen vorbereiteter/gecachter
Statements unzureichend; Profile/Methodenzustand separat erzwingen. Keine
Callback-Registrierung nach einem bereits gebundenen Reader-Pin.
[SQLite: Authorizer](https://www.sqlite.org/c3ref/set_authorizer.html).

Landlock kann später die erlaubten Pfade zusätzlich einschränken, ist aber
keine Byte-/Dateianzahlquote. Eine Regel, die `MAKE_REG` im Jobverzeichnis
zulässt, erlaubt dort nicht nur zwei Dateinamen. DELETE-Journale brauchen
Erstellen/Löschen; eine reine Verzeichnisregel ersetzt deshalb die
Writer-Schließung nicht. Bereits geöffnete FDs sowie ABI-abhängige
Truncate-Rechte müssen gesondert berücksichtigt werden. Landlock-Verfügbarkeit
oder eine eingerichtete Policy wurde hier nicht gemessen.
[Linux: Landlock](https://docs.kernel.org/userspace-api/landlock.html).

Auch `RLIMIT_NOFILE` begrenzt nicht die kumulativ erzeugte Dateianzahl: ein
Prozess kann nacheinander sehr viele Dateien öffnen, schließen und behalten.
`RLIMIT_FSIZE` begrenzt dagegen das Verlängern einer einzelnen Datei; bei
Überschreitung entstehen EFBIG/SIGXFSZ, nicht zwingend SQLITE_FULL.
[Linux man-pages: getrlimit](https://man7.org/linux/man-pages/man2/getrlimit.2.html).

Core-Dumps benötigen einen eigenen Gegencheck: `RLIMIT_CORE=0` reicht bei
einem an einen Collector gepipeten Core nicht als allgemeiner Beweis.
Dumpbarkeit im tatsächlichen Worker nach exec/Privilegwechsel wirksam
unterbinden und prüfen; keine hostweite Coredump-Konfiguration verändern.
[Linux man-pages: core](https://man7.org/linux/man-pages/man5/core.5.html),
[PR_SET_DUMPABLE](https://man7.org/linux/man-pages/man2/PR_SET_DUMPABLE.2const.html).

## 3. Reservierungsbeweis und seine genaue Reichweite

Bezeichnungen für einen zugelassenen Worker:

```text
P = feste SQLite-Seitengröße
M = floor(main_cap / P) * P
F = Kernel-Dateilimit, F >= M
L = M + F                       # logische Main-/Journalhülle
Phi(profile, filesystem)        # vorher hergeleitete Allokations-/Metadatenhülle
D = L + Phi                    # zu reservierender physischer QA-Slot
```

Unter dem geschlossenen Profil gibt es höchstens die beiden benannten
schreibbaren SQLite-Diskdateien. Die Mainlänge liegt unter M, das Journal
unter F. Damit ist ihre Summenlänge vor dem ersten Byte durch L begrenzt;
SQLite-interne Reihenfolge, Statementdauer und ein zwischenzeitlicher
`unlink` ändern diese Reservierung nicht. Der erste Implementierungsschritt
darf einfach `F=M` und somit `L=2*M` verwenden. Bei zu kleinem Journalslot
scheitert der Worker vor Überschreitung; das ist keine Kapazitätsfreigabe.

Dies ist kein Schutz gegen beliebigen Python-Code, der zusätzliche Dateien
erzeugt. Der Beweis hat einen konkreten, versiegelten Programmkatalog als
Prämisse. Fehlt diese Schließung, ist der Zwei-Datei-Beweis nicht anwendbar;
ein Directory-Diskwalk oder eine vermeintliche Landlock-Quote repariert ihn
nicht. Root-/VM-Manipulation ist keine hier hinzugenommene Bedrohungsannahme.

### Kleineres Journal aus einer frischen Ersttransaktion?

Das ist eine mögliche **spätere Optimierung**, nicht die vorgeschlagene erste
Zulassung. Der Pager unterscheidet vor Transaktionsbeginn vorhandene Seiten
von neu angehängten Seiten; außerdem können Cache-Spills weitere
Journalheader erzeugen. Aus „frisch“ allein folgt deshalb kein bewiesener
konstanter Journalwert. Zu prüfen wären tatsächliches N0, Header-/Sektor-
Alignment, Fehler-/Seitenbewegungspfade, Savepoint-Rollbacks und sämtliche
impliziten Commitmöglichkeiten. [SQLite: Atomic Commit](https://www.sqlite.org/atomiccommit.html),
[SQLite 3.45.1: pager.c](https://raw.githubusercontent.com/sqlite/sqlite/version-3.45.1/src/pager.c).

Ein kleinerer Journalslot als F müsste durch diesen versionsgebundenen
Beweis oder eine echte separate Schreibbegrenzung abgesichert werden.
`RLIMIT_FSIZE` ist pro Prozess/Datei gleich und bietet **keine** unabhängigen
Main-/Journalquoten. Ein gemessener 512-Byte-Journalpeak wäre allein kein
universeller Obergrenzenbeweis. Falls konservative 2*M-Slots nicht in die
globalen Grenzen passen, wird nicht automatisch auf den unbewiesenen
kleineren Wert umgeschaltet.

### Physische Belegung ist nicht nur `st_size`

Für bestehende Artefakte mindestens `max(st_size, st_blocks*512)` erfassen;
Dateisystem-/Mountidentität, feste Datei-/Verzeichniszahl, Allocation- und
Preallocationverhalten gehören zur Profilbindung. FSIZE begrenzt nicht von
sich aus sämtliche physischen Blöcke oder Metadaten. KEEP_SIZE-
Preallocation ist ein gesonderter Gegenfall. [Linux: fallocate](https://man7.org/linux/man-pages/man2/fallocate.2.html).

ext4 verwendet auch spekulative und verzögerte Allokation. Der Eintrag
„ext4“ plus ein erfolgreicher kleiner Lauf beweist daher noch keinen frei
gewählten pauschalen Phi-Wert. [Kernel: ext4 allocation policy](https://docs.kernel.org/filesystems/ext4/allocators.html).
Im gebundenen SQLite-Unix-VFS sind insbesondere Chunk-Size/Size-Hint und
Mmap-Expansion zu prüfen; kein eigener VFS oder ungebundener File-Control-
Aufruf darf diese Prämisse ändern. [SQLite 3.45.1: os_unix.c](https://raw.githubusercontent.com/sqlite/sqlite/version-3.45.1/src/os_unix.c).

Konkrete Folge: Der Budget-API-Typ muss eine bestätigte `physical_envelope_id`
verlangen, nicht einen willkürlichen vom Caller gewählten „64 KiB Reserve“-Wert.
Bis die physische Hülle hergeleitet und nativ gegengeprüft ist, sind die
2*M-Bytes eine bewiesene **logische** Hülle und keine schon nachgewiesene
physische 8-GiB-Gesamtgarantie. Das ist eine noch auszuführende lokale/native
Profilprüfung, keine Aufforderung, einen neuen Dienst oder ein Quotasystem
einzuführen.

### Globale zwei Mengen und echte Reserve

```text
A = gebundene aktive Eingaben + maximale aktive Ableitungen
Q = behaltene neue QA-Artefakte/Archive/Fehlläufe + volle offene Disk-Slots
R = noch nicht physisch verbrauchte, aber weiterhin reservierte Maximalbytes
G = aktuell f_bavail * f_frsize des tatsächlich betroffenen Dateisystems

Admit nur wenn:
    A <= 4 GiB
    Q <= 8 GiB
    G >= 4 GiB + R
    freie Inodes, vollständiger Owner-/Dateikatalog und Kostenlease gültig
```

Kopien, Generationen, Blöcke, Indizes, History-/Tennis-Staging, Raw-only-
Abhängigkeiten, B-Proofdateien, Publikationsteile, begrenzte Logs, Ledger-
Update-Dateien, Restorekopien und deren Journalbedarf zählen. Ein Dateiname,
der in zwei Manifestrollen vorkommt, ist kein Freibrief zur Unterzählung:
identische Inodes eindeutig identifizieren, physische Doppelkopien getrennt
zählen und den logischen Eingabevertrag zusätzlich erfüllen. Hardlinks dürfen
nicht zur Umgehung der bestehenden Seal-/Copy-Verträge eingesetzt werden.

Volle Slots bleiben beim schreibenden oder unbekannt beendeten Worker in Q.
Für R nur nachgewiesene bereits belegte Bytes vom jeweiligen Maximalwert
abziehen; beim Zweifel volle Resthülle ansetzen. Nach dem Schließen darf der
Owner auf tatsächlich behaltene, inventarisierte Artefakte umstellen. Löschen,
Archivieren oder „neuer Versuch“ erneuern das Gesamtbudget nicht. Archive
außerhalb des aktuellen Arbeitsunterverzeichnisses bleiben im selben Q.
Maximal zwei komplette B-Proofgenerationen plus ein begrenzter Workzustand
sind zudem keine Erlaubnis, die globale 8-GiB-Bilanz zu überschreiten.

Eine neue Phase erhält nur die **verbliebene** globale Hülle. Beispielsweise
ist ein Maincap von 1 GiB mit 2 GiB logischen Main-/Journalreservierungen zu
veranschlagen, nicht mit 1 GiB; zusätzlich bleiben bereits gehaltene Eingaben
und alte Fehlläufe belegt. Reicht die Bilanz nicht, ist vor Start STOP oder
eine bereits erlaubte, nachgewiesen sichere Phasenfreigabe nötig.

`f_bavail` ist die für unprivilegierte Prozesse verfügbare Menge, nicht die
größere, Root-Reserve einschließende `f_bfree`-Menge.
[Linux: statvfs](https://man7.org/linux/man-pages/man2/statvfs.2.html).
Der ext4-Statfs-Pfad berücksichtigt dabei auch seine Dirty-Cluster-Zählung;
das ist aussagekräftiger als allein die Summe sichtbarer Dateilängen.
[Linux 6.8: ext4_statfs](https://raw.githubusercontent.com/torvalds/linux/v6.8/fs/ext4/super.c).

Der Owner liest G vor/nach kontrollierten Schritten, der native Monitor
zusätzlich während langer SQLite-Aufrufe. Messintervall, maximale Messlücke
und Reaktionsregel gehören in den versiegelten Report. Verliert ein Lauf
die Reserve oder die Messbarkeit, wird er beendet und nicht publiziert.
Ein zwischen Messpunkten unbemerkter Fremdverbrauch wird nicht als unmöglich
behauptet. Nachgewiesene Reserveunterschreitung bleibt ein Test-STOP, auch
wenn ein späteres Löschen wieder Platz schafft.

Bei mehreren tatsächlichen Dateisystemen wird jede jeweilige G/R-Bilanz
separat geführt; freie Bytes auf einem anderen Volume gleichen ein Defizit
nicht aus. Keine neue Reservedatei, Mount-/Quota-/VM-Lösung wird vorausgesetzt.

## 4. Konkreter API- und Lifecycle-Vorschlag

Die Namen unten beschreiben die nächste lokale Implementierung. Kein zweites
CPU-/Deadline-Kostenbuch neben Roots parallel gebautem Baustein anlegen.

```python
@dataclass(frozen=True)
class WriterProfile:
    profile_id: str
    implementation_root: str
    runtime_root: str
    sqlite_source_id: str
    compile_options_digest: str
    sql_api_catalog_digest: str
    filesystem_identity: str
    physical_envelope_id: str
    page_size: int
    main_cap: int
    file_cap: int
    physical_cap: int
    max_writable_main_connections: int  # exactly 1
    max_persistent_sqlite_files: int    # exactly 2, including journal
    max_build_commits: int             # exactly 1

def reserve_disk(job, profile, active_input_charge, retained_inventory,
                 *, cost_lease) -> DiskLease: ...

def launch_reserved_worker(job, disk_lease, cost_lease,
                           *, sealed_inputs) -> WorkerHandle: ...

def finish_reserved_worker(job, handle, *, exit_evidence,
                           complete_artifact_inventory) -> RetainedState: ...
```

Die API akzeptiert ausschließlich bekannte Profile/Enums und exakt geprüfte
Integer, keine beliebigen Caller-Werte oder schwächer überschriebenen Limits.
Root prüft Disk- und Kostenlease derselben Job-/Input-/Runtimeidentität unter
einem exklusiven Job-Lock. Die gesamte Reservierung wird dauerhaft gebucht,
**bevor** mkdtemp, DB-Anlage, Copy, Produktimport oder ein Workerstart erfolgen.
Auch die begrenzten Ledger-/Manifest-Replace-Dateien sind bereits budgetiert;
kein unbeschränkt appendendes Ereignislog.

Zustände:

```text
RESERVED -> RUNNING -> REAPED_UNVALIDATED -> RETAINED_VALIDATED
                 \-> FAILED_OR_UNKNOWN -> RETAINED_FAILED
```

Nur ein Owner darf weitere Slots zulassen. Atomare, synchronisierte
Metadatenaktualisierung bindet Zustand und Kostenlease; ein fehlender,
beschädigter oder unpassender Zustand erlaubt keinen neuen Start.
Crash zwischen Reservierung und Launch darf höchstens überreservieren.
Crash nach Launch ohne vollständigen Exit-/FD-/Kostenbeleg bleibt konservativ
belastet. Boot-/Uhrwechsel, anderes Arbeitsverzeichnis oder neuer Teilname
setzen Kosten und behaltene Plattenbelegung nicht zurück.

`finish` benötigt: alle Worker/Nachkommen beendet, alle Output-/Blob-/Reader-
Handles geschlossen, keine fremden Besitzer/Hardlinks/Symlinks/Sonderdateien,
vollständige Pfad-/Inode-/Größeninventur, statvfs-Erfolg, keine offene
Reservierungsverletzung. Das bloße Fehlen eines Pfadnamens genügt nicht:
ein unlinked Inode bleibt bis zum letzten offenen FD erhalten.
[Linux: unlink](https://man7.org/linux/man-pages/man2/unlink.2.html).

Ein erfolgreicher `finish` ist noch keine Veröffentlichung. Vollständige
RawInventory-/Keyset-Abdeckung, Feature-/D2-Wahrheit, Implementation-Closure,
B-Proof-CAS/HMAC/Generation, Restore und C6 bleiben eigene Gates. Vorhandene
Quellen/Backups/Belege werden nicht gelöscht, um eine Reserveprüfung grün zu
machen. Component-`TemporaryDirectory.cleanup()` darf globalen Besitz erst
nach nachgewiesenem Ende aller Handles entlasten.

## 5. Worker-Ressourcen ohne versteckte Erhöhung

| Größe | Durchsetzung und Nachweis |
| --- | --- |
| CPU 300 s je Worker | Kernel-Limit vor Import; Parent kontrolliert den gesamten zugelassenen Prozessbaum. Ein Kindprozess mit eigenem frischem Limit ist kein zusätzlicher freier 300-s-Topf. |
| Gesamt 1800 CPU/3600 Gesamtzeit | Roots persistentes Kostenbuch vor jedem Start reservieren. Alle Nachkommen/Versuche und unbekannte Crashkosten konservativ erfassen; nicht nur erfolgreiche SQLite-Zeit messen. |
| AS 2 GiB | Hartes RLIMIT_AS vor Import/Allokation; wird bei Kindern geerbt, ist aber pro Prozess, nicht automatisch ein gemeinsames 2-GiB-Poollimit. Keine zusätzliche Speicherfreigabe für MEMORY. |
| RSS unter 1 GiB | Native vollständige Peak-/Exitmessung, aktiver Monitor und STOP bei Verletzung. `RLIMIT_RSS` ist unter modernem Linux keine wirksame RSS-Schranke. |
| Ausgabe 1 MiB | stdout und stderr zusammen an bounded Pipes; Parent liest höchstens Restkontingent plus ein Erkennungsbyte. Kein unbounded `communicate()` und keine vorher unbeschränkt geschriebene Logdatei. Überschreitung beendet/invalidiert den Lauf. |
| SQL-Heap | Optional zusätzlich konservativ begrenzen, nur nach realem Funktionsnachweis; dies deckt weder Python-Objekte noch alle nativen Bibliotheken ab. |

Die prozessbezogenen RLIMITs und die wirkungslose moderne RSS-Option sind
getrennt zu betrachten. [Linux: getrlimit](https://man7.org/linux/man-pages/man2/getrlimit.2.html).
Linux `ru_maxrss` wird in KiB geliefert. `RUSAGE_CHILDREN.ru_maxrss` ist der
größte einzelne Kindpeak, nicht der gleichzeitige Peak des gesamten Baums;
Descendant-CPU setzt außerdem passende Wait-/Reaping-Ketten voraus.
[Linux: getrusage](https://man7.org/linux/man-pages/man2/getrusage.2.html).

Die von Root gemeldeten bestehenden cgroup2-Fähigkeiten bieten einen
technischen Folgeschritt für gruppenweite CPU-Zählung und Speicherbegrenzung,
sind aber noch kein eingerichteter Workercontainer. `cpu.max` begrenzt
Bandbreite, nicht ein kumulatives Sekundenbudget. `memory.max` kann bei Druck
OOM auslösen und kurzzeitig überschritten werden; `memory.peak` ist ein
Gruppen-Memorywert, nicht identisch mit Prozess-RSS. Insbesondere gemeinsam
genutzte/anderswo belastete Seiten verbieten einen ungeprüften Gleichschluss.
AS bleibt zusätzlich erforderlich. Keine neue systemd-Unit/cgroup wurde in
diesem Review angelegt. [Linux 6.8: cgroup v2](https://raw.githubusercontent.com/torvalds/linux/v6.8/Documentation/admin-guide/cgroup-v2.rst).

Ein `hard_heap_limit` ist nur eine weitere SQLite-Schranke; PRAGMA kann den
Wert nur senken. Seine tatsächliche Wirkung und die SQLite-Memory-Konfiguration
müssen vor Verwendung geprüft werden. Es ersetzt keine RSS-Messung.
[SQLite: PRAGMA hard_heap_limit](https://www.sqlite.org/pragma.html#pragma_hard_heap_limit).
Weder fehlende native Messbarkeit noch OOM wird durch einen größeren Cache,
mehr AS/RSS oder eine Rückkehr zu ungezähltem FILE-Spill „gelöst“.

## 6. Bereits vorhandene Belege und nächste ausführbare Prüfungen

### Tatsächlich ausgeführt in diesem Review

Nur lesende lokale Dateiprüfungen/Hashes sowie eine ausschließlich
In-Memory-stdlib-Probe mit dem gebündelten Python, `-I -S -B`.
Ergebnis: Windows `win32`, Python 3.12.14, SQLite 3.53.1,
`TEMP_STORE=1`, `temp_store`-Readback 2, Attach-Limit 0,
SQLite-Workerthreadlimit 0. Source-ID:
`2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9`.
Exit 0. Das ist **kein** Beleg für Linux-3.45.1-Dateiverhalten oder native
CPU/AS/RSS-/Plattenpeaks. Keine pytest-/Corpusläufe in diesem Review.

Root meldete unabhängig eine rein lesende VPS-Capabilityprobe:
Linux 6.8.0-138-generic, ext4 (`rw,relatime,discard,errors=remount-ro,commit=30`),
systemd 255, unified cgroup2 mit unter anderem cpu/memory/pids;
SQLite 3.45.1 mit `TEMP_STORE=1` und Readback 2; CLOCK_BOOTTIME vorhanden;
14 814 339 072 Bytes tatsächlich frei zum dortigen Messzeitpunkt.
Eine stdlib-Probe lief als UID 997 mit `-I -S -B`; UID 1000 konnte den
App-Interpreter nicht lesen. Diese Werte sind **von Root übermittelte
Capabilitydaten**, keine durch diesen Reviewer selbst ausgeführte Serverprobe,
keine Ressourcenfreigabe und keine Vollständigkeitsbestätigung der Runtime.
Vollständige Source-ID/Binary-/Compile-Closure und Dateisystem-Envelope sind
vor dem schreibenden Profiltest nochmals exakt zu binden.

### P1 — sofort ausführbarer, nicht persistierender API-Gegencheck

Im gewählten Python kann folgende stdlib-Probe mit `-I -S -B -c` ausgeführt
werden. Sie legt keine Diskdatenbank an und ist kein FSIZE-/Spillbeweis:

```python
import sqlite3
c = sqlite3.connect(":memory:", isolation_level=None)
c.execute("PRAGMA temp_store=MEMORY")
assert c.execute("PRAGMA temp_store").fetchone() == (2,)
c.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
c.setlimit(sqlite3.SQLITE_LIMIT_WORKER_THREADS, 0)
assert c.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED) == 0
assert c.getlimit(sqlite3.SQLITE_LIMIT_WORKER_THREADS) == 0
try:
    c.execute("ATTACH ':memory:' AS forbidden")
except sqlite3.DatabaseError:
    pass
else:
    raise AssertionError("ATTACH escaped profile")
c.close()
```

### P2 — lokale Owner-/Ledgertests vor einem nativen Corpusjob

Als neue kleine Tests des anschließend implementierten Budget-Owners ausführen;
hier werden keine noch nicht vorhandenen Testnamen als existierende Befehle
ausgegeben. Alle Dateianlagen müssen bereits in die gemeinsame QA-Bilanz
eingehen, auch pytest-Basetemp/JUnit/Crashausgaben.

- Exakte Grenzen und jeweils ein Byte darüber: A=4 GiB, Q=8 GiB,
  G=4 GiB+R; negative/bool/float/überlaufende/fremde Werte ablehnen.
- Zwei konkurrierende Zulassungen, gleiche/leere/gefälschte Job-ID,
  Profil-/Runtime-/Inputwechsel, Archive außerhalb des jüngsten Unterordners;
  niemals zwei separat gültige Zusagen für dieselben Restbytes.
- Crash vor/nach Reservierungs-fsync, vor/nach Launch, während Commit und vor
  `finish`; unbekanntes Ende bleibt belastet, kein Budgetreset beim Neustart.
- Fehlversuch mit Main+Journal, verweigerter Cleanup, gehaltenem Reader-FD,
  unlinked File und anschließend gleichem Pfad mit neuem Inode: alte und neue
  Belegung nicht verwechseln; Slot nicht verfrüht wiederverwenden.
- Fälschung des Dateikatalogs, unzulässige Symlinks/Hardlinks/Sonderdateien,
  Owner-/Mountwechsel, fehlendes statvfs, fallende Reserve und erneutes
  späteres Ansteigen: alle zugehörigen Läufe bleiben ungültig.
- Metadata-/Manifest-Replace inklusive alter und neuer Datei sowie eigener
  Fehlerbelege in Q; begrenzte Anzahldimension, kein unbegrenztes Logwachstum.

### P3 — begrenzte native Writerprobe, erst durch Roots kontrollierten Launcher

Nur neue private Testdateien, vorab kleine feste Slots und unveränderte
Workergrenzen. Nicht als bloßes ungeschütztes `python script.py` starten.
Der Test muss auch beim Fehler sämtliche tatsächlichen Pfade/FDs/Signale,
Kosten und Peakwerte belegen. Native Schreibproben wurden hier nicht ausgeführt.

| Probe | Konkrete Ausführung im zugelassenen Worker | Erwartung |
| --- | --- | --- |
| Main-SQLite_FULL | Neue DB, Pagegröße 4096, `max_page_count=256`, Parameter-Inserts mit 4096-Byte-BLOB bis zum Fehler. | Main wächst nicht über 1 MiB; kein Commit/Resultat nach Fehler; Source unverändert. |
| Kernel-Dateicap | Separate neue Test-DB, Main-Pagegrenze größer als bewusst kleines FSIZE; bis zur ersten EFBIG-/SIGXFSZ-/IOERR-Reaktion schreiben. | Kein Regular-File überschreitet FSIZE; gesamter Fehllauf weiter budgetiert. Nicht nur SQLITE_FULL als erfolgreichen Testpfad akzeptieren. |
| Untertransaktionen | Viele Einzelinserts, dann verschachtelte Savepoints, mehrzeilige UPDATE/DELETE mit bewusstem Constraintfehler und ROLLBACK TO. | Byte-/Zeilenrollback korrekt, keine Disk-Subjournale; RAM bleibt innerhalb des echten Workerprofils oder der Lauf endet als OOM/STOP. |
| Sortierung/Materialisierung | Nicht indexgedecktes `ORDER BY`, `DISTINCT`, `UNION`, `GROUP BY` auf zunehmend vielen begrenzten Werten, mindestens bis klar oberhalb des Cachevolumens. | Im gepinnten MEMORY-Profil keine Temp-Dateioperation; korrekte vollständige Resultate oder sauberer Speicher-STOP, niemals FILE-Fallback. |
| Verbotene Ausnahmen | ATTACH, beide VACUUM-Formen, WAL-Umschaltung, zweite DB, Backup-Ziel, Extension-/UDF-Dateischreiben, zusätzlicher Commit/executescript. | Vor Wirkung abgewiesen oder als Profilbruch invalidiert; kein veröffentlichter Teil. |
| Journal/Physik | Größere Ersttransaktion mit kleinem Cache, wiederholte Mainseitenänderungen und Savepoint-Rollbacks; Stat-/FD-/Syscallgegencheck auch über Fehlerpfade. | Nur erlaubte Main-/Journaldateien; beobachtete st_blocks/Preallocation innerhalb der zuvor hergeleiteten Phi-Hülle. Sampling allein beweist deren Universalität nicht. |
| Fremdplatz/Monitor | Kontrolliert gefälschte statvfs-Antworten lokal; native echte Fremdbelegung nur separat ausdrücklich zugelassen, nie Live-Disk absichtlich füllen. | Vor Start keine Überbuchung; jeder Reserveverlust oder Monitorausfall stoppt/invalidiert. |
| Prozess/Ausgabe | Kindprozess-/FD-Fluchtversuch, sehr viel stderr/stdout, CPU- und Speichererschöpfung in kleinem Probeprofil. | Gesamte Prozessgruppe beendet/reaped, Ausgabe 1 MiB nicht überschritten, Kosten vollständig/conservativ gebucht. |

Ein vorhandener Syscall-Tracer kann in einer gesondert budgetierten Probe
Dateierzeugung/-unlink/-truncate/-fallocate bis zum Exit sichtbar machen.
Tracer-Ausgabe selbst strikt begrenzen und abrechnen. Ist kein solcher
Mechanismus vorhanden, nicht ungefragt installieren und nicht aus einem
unvollständigen Directory-Snapshot einen Spill-Ausschluss ableiten. Die
statische versionsgebundene Schließung und dynamische Fehlergegenprobe
ergänzen einander.

### P4 — tatsächliche C-Pfade und vollständige Regression

Erst nach P2/P3 die echten C-Ownerpfade mit neuem Writerprofil betreiben:
Copy, History, Tennis, Refs, Snapshot-Source einschließlich der Owner-erzeugten
Legacy-Snapshots und Raw-only-Fälle. Dabei komplette Alt-Neu-Byte-/Identitäts-,
Schema-/Keyset-, Transaction-/DDL-/Callback-/FD-Lifetime-Regressionsgruppen
ausführen; keine Tests durch anderes Profil überspringen oder Altregeln lockern.

Jeder pytest-Lauf bekommt einen neuen, nie existierenden Workspace-Basetemp
und eine eigene JUnit-Datei; diese persistenten QA-Bytes werden **vorher**
zugelassen. Gebündeltes Python:
`C:/Users/miros/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`;
Projektabhängigkeiten:
`C:/Projekt/BetBoy/betboy-app/.venv/Lib/site-packages`;
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `-B -m pytest`.
Die lokalen Windows-Ergebnisse ersetzen keine native Linux-Messung.

Anschließend gelten unverändert die echten Mengen-/ATP-/Mixed-/Burstprofile,
globalen Vorbereitungskosten, drei finalen Pflichtläufe je Profil und
Restore samt inzwischen hinzugekommenen Daten. Dieser Review bestätigt davon
keine Durchführung.

## Abschluss und nächster ausführbarer Schritt

Kein verbleibender theoretischer Grund wurde gefunden, der **innerhalb der
beobachteten fail-closed C-Reservegrenze** zwingend einen neuen Dienst, eine VM
oder ein Quotasystem verlangen würde. Das Zwei-Datei-Profil ist ein konkreter
lokal implementierbarer Kandidat mit überprüfbaren Prämissen.

Als Nächstes den globalen Disk-Owner an Roots Kostenlease anbinden, das
versiegelte Single-Main-Profil als neues internes C-Writerprofil einführen
und seine physische Dateisystemhülle nachweisen; dann die kleinen Fehlerproben
P2/P3 ausführen. Bis Writer-Schließung, Allokationshülle, Ressourcenmonitor
und echte C6-Profile nachgewiesen sind: **keine globale Budget-/Kapazitäts-,
B-Publikations- oder Produktionsabnahme**.
