# Task 32 — unabhängiges Review des frischen SQLite-Writerprofils

Stand: 2026-09-12. Prüfer: `c_copy_review`. Keine Produkt-, bestehenden Test-, Git- oder Serveränderung. Geprüft wurden der vollständige Profilcode, alle Owner-Tests, Task 27, der C-Gesamtintegrationsplan, die einschlägigen Task-22-Anforderungen und die bestehende TrackedConnection-/Cursor-Implementierung.

## Ergebnis

**Kein konkreter neuer wichtiger Produktbefund im vereinbarten lokalen Profil-/Lifecycle-Umfang.** Final **393 bestanden, 0 Fehler, 0 übersprungen, 26,39 s**: 34 neue unabhängige Probes, 93 Profil-Owner-Tests und 266 bestehende refs-/snapshots-/ref_chunks-Prüfungen. Das Profil wurde nicht geändert. Dies ist keine native FSIZE-/AS-/RSS-/CPU-/globale Plattenabnahme und kein vollständiger C-/B-Abschluss.

| Geprüfte Datei / Evidenz | SHA256 |
| --- | --- |
| `context_storage_v2/sqlite_profile.py` | `05898adf9782ff06e2edcf33d45c94dd6ecce232ddba1f81ffcfaf65fca3d8bc` |
| `tests/test_context_storage_sqlite_profile.py` | `7cf07bfa2ae418b676e8a53bb074994c022c50fa65d364429903a37e5e159292` |
| `.pytest_tmp/test_task32_sqlite_profile_review_ccr01.py` | `ddd965c6838900b5f58b3a1e826857839dbea4acd55efe8a78aa2e49b8c32eae` |
| `.pytest_tmp/task32-sqlite-profile-review-ccr01-final.xml` — 393 grün | `38d7ca64eb0f68bb490d25e0e34208c8c217d48c3648cad957e1c44c470867f2` |
| `.pytest_tmp/task32-sqlite-profile-review-ccr01-run2.xml` — 127 grün, 2,66 s | `1998e8e6c2c0800915c4d8c5e4137605d88f4998f78ed41a891cebd70337432c` |
| `.pytest_tmp/task32-sqlite-profile-review-ccr01-run1.xml` — 126 grün / 1 Fehler in eigener Kontroll-Aufräumlogik | `4de3daeae3e1cc313b72fc8ac336942981b287359f12509ae7fe9f243878895d` |

## Tatsächlich unabhängig geprüft

1. **TEMP und vollständige Bytegleichheit.** Echte neue Profil-Main plus separate echte FILE-TEMP-Referenz; 4.096 Zeilen mit ganzen Zahlen, Unicode/NUL-Text und BLOBs. `EXPLAIN QUERY PLAN` bestätigt tatsächlich verwendeten TEMP B-TREE. Alle geordneten typisierten Bytes stimmen vollständig zwischen MEMORY-Profil, FILE-Referenz und unabhängig in Python berechnetem Soll überein. Nach Commit wurde der Profilstore erneut read-only gelesen und vollständig verglichen. Die Laufzeit meldet genau einen passenden `TEMP_STORE`-Compilewert und effektiven Readback 2; die Referenz hat Readback 1.

   Persistierte Sortierprobe aus `task32-sqlite-profile-review-ccr01-run2/test_real_memory_sort_all_rows0/profile.db`: 4.096 Zeilen, 479.146 kanonisch gerahmte Byte, SHA256 `a3409d65a7ffa0540e5d8860db107975d5bc977aa22082efc7001295674ab61c`; Main 475.136 Byte / 116 Seiten. Kein Sport-/Sieben-Tage-Profil und keine Mengenhochrechnung.

2. **Erste SQL und eine Build-Epoche.** Tatsächlicher SQL-Trace zeigt MEMORY als erste SQL, Compile-Readback vor jedem Schema-Zugriff, genau ein BEGIN IMMEDIATE vor DDL und genau einen Commit. Die MEMORY-Umschaltversuche während der Transaktion und explizite TEMP-Objekte werden entsprechend tatsächlichem SQLite-Verhalten abgewiesen oder bei beobachteter Abweichung dauerhaft invalidiert. Compile-Override 0 kann trotz Laufzeit-Readback FILE erzwingen; die Annahme von nur 1/2/3 zusammen mit Readback 2 stimmt mit der offiziellen [SQLite-TEMP_STORE-Tabelle](https://www.sqlite.org/pragma.html#pragma_temp_store) überein. Keine Aussage über unbekannte VFS, zusätzliche Verbindungen oder physische Speicherpeaks.

3. **Savepoints und Fehleratomizität.** Echte verschachtelte Savepoints mit UPDATE/DELETE, vollständiges ROLLBACK TO/RELEASE und mehrzeiliges UNIQUE-Statement-ABORT erhalten exakt die ursprünglichen typisierten Reihen und die äußere Build-Epoche. Echte SQLITE_FULL-Fälle bei festen Main-Decken 16/32/64 KiB lösen Auto-Rollback aus; anschließend keine Teil-Commit-Zulassung, Connection/FD geschlossen und die neu erstellte Tabelle nicht persistiert.

4. **Commit-/Rollback-Fehler.** Echte zweite RO-Connection erzeugt SQLITE_BUSY am Commit; der komplette neue Schemaaufbau wird verworfen und der native Dateihandle freigegeben. Ein gezielt installierter Authorizer verweigert wahlweise COMMIT oder ROLLBACK, erzeugt somit echte SQLite-Fehler; beide Wege liefern keinen Erfolg und schließen die Verbindung/den gehaltenen FD. Diese Fehlerquelle ist ausdrücklich Test-Injektion und kein erlaubter Produktcallback. Zusätzlich lösen injizierte Fehler *nach tatsächlich ausgeführtem* Connection.close bzw. os.close keine fälschliche Erfolgsmarkierung aus; bereits committete Bytes bleiben vorhanden, aber unzugelassen.

5. **Reale Cursor-/Blob-Lebensdauer.** Normaler SELECT-Cursor, laufendes DML RETURNING, schreibender Blob und ein benutzerdefinierter TrackedCursor mit absichtlich unbrauchbarem Python-close-Override werden vor Connection.close über die tatsächlichen SQLite-Finalizer geschlossen — jeweils beim Commit und beim Abbruch. Danach schlagen Cursor-/Blob-Zugriffe fehl; die wirkliche Windows-Datei lässt sich trotz weiter vorhandener Python-Variablen umbenennen. Schreibende Blob-/RETURNING-Ergebnisse werden nach erfolgreichem Commit vollständig verglichen. Bereits explizit geschlossene registrierte Handles sind ebenfalls verträglich.

6. **close_v2-Negativkontrolle.** Bei einer separaten gewöhnlichen sqlite3-Connection führt Connection.close mit noch lebendem SELECT-Cursor tatsächlich zu WinError 32 beim Rename. Danach wirft selbst Cursor.close eine echte ProgrammingError wegen der bereits geschlossenen Connection. Erst die Destruktion dieses Kontroll-Cursors gibt die VFS-Datei frei. Der erste Probelauf hatte genau wegen der ursprünglich falschen Annahme, nach Connection.close noch Cursor.close zum Aufräumen nutzen zu können, einen Fehler. Nur diese Kontroll-Aufräumlogik wurde korrigiert; die positive Profilprüfung und der Produktcode blieben unverändert. Das entspricht der dokumentierten verzögerten Freigabe bei [SQLite close_v2](https://www.sqlite.org/c3ref/close.html). GC wird nicht als Produktionsfreigabe verlangt oder benutzt.

7. **Drift und Fremddateien.** Tatsächlich veränderte Plan-/Limitwerte, Fabriken und ein während des Readbacks commitierender Tracecallback werden nicht als unveränderte Build-Epoche akzeptiert. Ein Callback-Commit kann bereits persistierte Bytes nicht rückgängig machen; das Profil meldet korrekt keinen Erfolg. Vorhandene Main-/Journal-/WAL-/SHM-Fixtures bleiben byte- und inodegleich. Die reale Windows-Austauschprobe schließt als explizit injizierten FD-Verlust erst den gehaltenen Descriptor, ersetzt dann den Pfad und bestätigt null SQL und unveränderte Fremdbytes. Kein behaupteter Linux-Held-FD-ABA-Nachweis.

## Vertrag und verbleibende Grenzen

Die normale API liefert weiterhin exakt TrackedConnection, keine Wrapper-Sonderautorität. Der eigene Handle-Registry-Eingriff erfasst normale Cursor-/Blob-Erzeugung; Basis-C-Methoden direkt aufzurufen, andere Connections/Backups/Extensions zu verwenden, Methoden/Callbacks umzubauen oder einen Namespace-ABA auszulösen bleibt ausdrücklich außerhalb der zugelassenen Closure. Die vorliegenden Tests behaupten keine Python-Sandbox.

`max_page_count` begrenzt logische Main-Seiten. Der zusätzliche Journal-Slot M ist eine äußere Reservation und benötigt die tatsächliche native Dateigrenze. Normales DELETE/FULL bleibt erhalten; `temp_store=MEMORY` wird nicht mit `journal_mode=MEMORY` verwechselt. `journal_size_limit=0`, Named-File-Walks und beobachtete Dateilängen sind weder Journal-Peakbeweis noch physische/global-kumulative Quota. NativeOwner muss Eingaben, sämtliche Fehlversuche/Archive/Outputs, Allokation/Metadaten, freien 4-GiB-Abstand, ganze Jobkosten/Deadline sowie endgültigen Worker-Reap weiterhin binden. Fehler/unklare Schließung erlauben keine Slotentlastung allein aufgrund eines Python-Flags.

## Reproduktion und Übergabe

Runtime live verifiziert: QA-venv Python 3.12.14, SQLite 3.53.1, Windows. `-B`, Plugin-Autoload aus, Cacheprovider aus, pro Lauf neue zuvor nicht vorhandene Basetemps/XML. Keine SSH-/VPS-, Kernel- oder Hoständerung.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider .pytest_tmp/test_task32_sqlite_profile_review_ccr01.py tests/test_context_storage_sqlite_profile.py tests/test_context_storage_refs.py tests/test_context_storage_snapshots.py tests/test_context_storage_ref_chunks.py --basetemp=.pytest_tmp/task32-sqlite-profile-review-ccr01-final --junitxml=.pytest_tmp/task32-sqlite-profile-review-ccr01-final.xml
```

Dies ist der tatsächlich ausgeführte finale Befehl. Die Namen sind inzwischen belegt; Wiederholungen verwenden neue Namen und überschreiben keine Evidenz. Nächster Schritt ist die bewusste Root-Integration dieses lokalen Profils in den weiterhin separat nachzuweisenden Native-/Workspace-/Budget-Owner. Keine zusätzliche Nutzerfreigabe für den bereits genehmigten technischen Abschnitt wird behauptet oder angefordert; ebenso keine Gesamtzulassung.
