# Task 31 — unabhängiger Review des Dumpable0/no-exec-Guards

Stand: 12. September 2026. Reviewer `c_source_adapter`, Produktowner
`c_snapshot_review`. Gegenstand ist ausschließlich der selbstbeschränkende,
frisch geforkte QA-Python-Worker, nicht Vollsandbox, Dateisystemquote,
Jobbudget, Publisher oder B-/C-Gesamtfreigabe.

## Ergebnis

**Kein verbleibender konkreter Produktbefund gegen den engen Task-28-Vertrag
am unten eingefrorenen Stand.** Die erzeugte Filterlogik und die modellierten
Übergänge passen zum neuen Dumpable0/no-exec-Pfad. Das ist ein abgeschlossener
portabler Code-/Policyreview, keine native Durchsetzungs- oder Crash-Evidenz.
Roots nächste kleine isolierte native Prüfungen bleiben erforderlich.

Eigene getrennte Probe: **65 bestanden**. Kombinierter Nachlauf mit unveränderten
Ownertests: **212 bestanden, 5 Linux-only übersprungen**, 1,25 s Konsole,
1,200 s JUnit. Kein Guard wurde nativ installiert; keine native Socket-,
Thread-, UID-/Capability-, SIGSYS-/Coredump- oder Ressourcenprobe ausgeführt.
Keine Produktdatei, Ownertestdatei, Git-/Serverdatei oder globale Konfiguration
wurde durch diesen Review geändert. Nur die eigene ignorierte Probe/XMLs und
dieser Bericht wurden angelegt.

Gelesen wurden der gesamte ursprüngliche und der gesamte endgültige Guard,
die vollständigen jeweiligen Ownertests sowie der vollständige aktualisierte
Task-28-Bericht. Das endgültige Urteil wurde erst nach dem neuen Owner-Freeze
gebildet. Die ältere exec-erlaubende Version wurde nicht freigegeben.

## Eingefrorene Identitäten

| Objekt | SHA-256 |
| --- | --- |
| `context_preparation_process_guard.py` | `62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4` |
| `tests/test_context_preparation_process_guard.py` | `3620436ea09686e32df8fc2457111ebc92ec5b779e9a093e8f141be50c8f9777` |
| `task-28-process-guard.md` | `14bbdf23eab1053ed484cb21a4815522099a8ffa8a0f30cf7b894474f29b8599` |
| 378 emittierte BPF-Instruktionen | `fa959325efde6e1ba9d73b893bf9a193173ec8cb99d91758ac5331beb99e8477` |
| Eigene Probe `test_guard_independent.py` | `5efe41fdf84d73631d0ac0e5665189dd89655a1d12ee36d51745b0ec2b200207` |
| Eigenes finales XML `task31-review-02.xml` | `4dd89e7a39f3727d6463b5359c4e87a7741e6ce13f94fd91c5587608e2617b7a` |

Probe liegt unter `.pytest_tmp/task31-review-20260912-01/`, XML unter
`.pytest_tmp/`. Die Produkt-/Testhashes wurden nach den Tests erneut gelesen
und stimmen mit dem Owner-Freeze überein.

## 1. Befunde mit Änderungsbedarf

Keine P0-/P1-/P2-Produktabweichung im geprüften engen Vertrag reproduziert.
Die folgenden drei Punkte sind ausdrücklich wichtige Claim-/Integrationsgrenzen,
keine verschwiegenen nativen Erfolge und keine Forderung nach neuer Infrastruktur.

### I-1 — Dumpable0 blockiert den Kernel-Core-Pipepfad, nicht alle Systemlogs

Am Produktpfad `context_preparation_process_guard.py:481` erfolgt zuerst der
vollständige unprivilegierte Zustandsabgleich. Zeilen 494/495 setzen Dumpable
auf 0 und lesen exakt 0 vor Installation des Filters; Zeile 505 bestätigt
danach erneut 0. Die Policy ab Zeile 229 erlaubt weder PR_SET_DUMPABLE noch
Exec-/UID-/GID-/Filesystem-ID-Setter.

Die Verengung ist sachlich notwendig: Auch ein gewöhnliches Exec setzt die
Dumpability normalerweise wieder auf 1; allein NNP/CORE0 reicht dafür nicht.
[execve(2)](https://man7.org/linux/man-pages/man2/execve.2.html).
Änderungen effektiver oder Filesystem-IDs können sie auf den Hostwert
suid_dumpable zurücksetzen. Diese Syscalls sind im neuen Filter ausgeschlossen.
[PR_SET_DUMPABLE(2)](https://man7.org/linux/man-pages/man2/PR_SET_DUMPABLE.2const.html).

In der tatsächlich gelesenen offiziellen Linux-v6.8-Quelle liegt die
Dumpable0-Abweisung in `do_coredump` vor Formatierung des core_pattern und vor
`call_usermodehelper_setup/exec`. **Inferenz aus Quelle plus geprüfter Policy:**
Nach bestätigtem Dumpable0 startet dieser Kernel-Coredump-Pfad für das Kind
keinen Pipehelper, sofern die äußere Trusted-Worker-/Kernelgrenze gilt.
`audit_core_dumps` liegt allerdings bereits vor dieser Abweisung. Daraus folgt
keine Zusage, dass Audit/Journald oder andere fremde Prozesse keine Bytes
schreiben. Der aktuelle VPS-Kernel/Apport wurde von Root aufgenommen, nicht
von diesem Reviewer; dies ersetzt keine echte native Prüfung des Zielsystems.
[Linux v6.8 fs/coredump.c](https://raw.githubusercontent.com/torvalds/linux/v6.8/fs/coredump.c).

### I-2 — Child-Dumpability-Readback ist nicht Parent-proc-Readback

`GuardReadback.dumpable` ist das direkte GET-Ergebnis im kontrollierten Kind.
PR_GET_DUMPABLE adressiert nur den aufrufenden Prozess. Ein entsprechender
Parent-Aufruf liest also den Parent, nicht das gestoppte Kind.
[PR_GET_DUMPABLE(2)](https://man7.org/linux/man-pages/man2/PR_GET_DUMPABLE.2const.html).

Insbesondere bedeutet `CoreDumping: 0` in `/proc/<pid>/status` nur, dass gerade
kein Core-Dump läuft, nicht Dumpable0. Roots Parent-SIGSTOP-/pidfd-Readbacks
von IDs, Caps, Threads, Limits und Seccomp sind davon getrennt auszuweisen;
das Child-Feld darf nicht als unabhängige Parent-Kernelmessung umetikettiert
werden. Das Modul selbst nennt seine Rückgaben bereits Beobachtungen statt
Startautorität. [proc_pid_status(5)](https://man7.org/linux/man-pages/man5/proc_pid_status.5.html).

### I-3 — Socket- und Threadgrenze bleibt eng

Die sämtlichen x86_64-Socket-Entry-Points 41..55 sowie accept4, recvmmsg und
sendmmsg sind symbolisch abgewiesen. Das ist keine vollständige Netzsperre:
allgemeine read/write/ioctl/dup-Aufrufe auf schon offenen FDs sind erlaubt.
Inherente Geräte-, Socket-, Async- und Dateideskriptoren sowie externe Helfer
vor dem vertrauenswürdigen Fork bleiben äußere Closure-Pflicht.

Die neuen direkten Fork-/Clone-/Threadpfade sind abgewiesen; die feste Policy
verweigert außerdem io_uring/AIO-, Namespace- und einschlägige alternative
Credential-/Limitpfade. Eine Aussage über vorher entkommene/reparentete
Prozesse, schon bestehende asynchrone Kernelarbeit oder beliebige ioctl-
Seiteneffekte wird daraus nicht hergeleitet. Das passt zur expliziten engen
Modulbeschreibung und zur [Kernel-Seccomp-Dokumentation](https://docs.kernel.org/userspace-api/seccomp_filter.html),
die Seccomp allein nicht als Sandbox ausgibt.

## 2. Unabhängige Policyprüfung

Eigene Probe ab Zeile 134: Ein eigener Decoder liest die erzeugten
Little-Endian-Instruktionsbytes. Eine getrennte Intervallausführung partitioniert
alle 16 unsigned 32-Bit-Wörter eines vollständigen seccomp_data-Inputs. Bei jedem
JEQ/JGE werden die exakten positiven und negativen Bereiche getrennt; alle
erreichbaren Endpfade müssen terminieren. Erwartete Allow-/Deny-Mengen stammen
aus einer separat festgehaltenen, gegen die offizielle Tabelle geprüften
Zahlenmenge, nicht aus `guard._ALLOWED_SYSCALLS` oder Owner-Testhelfern.
[Linux v6.12 syscall_64.tbl](https://raw.githubusercontent.com/torvalds/linux/v6.12/arch/x86/entry/syscalls/syscall_64.tbl).

Ergebnis: 185 symbolische Endpfade, davon 172 ALLOW, 10 EPERM und 3 KILL.
166 Syscallnummern sind unbedingt zugelassen; prctl und prlimit64 haben
ausschließlich die unten aufgeführten Argumentregeln. Diese Ausführung ist
ein portabler Nachweis über die emittierte Filterfunktion, kein vom Kernel
akzeptiertes/ausgeführtes Filterabbild.

| Prüfung | Ergebnis |
| --- | --- |
| Architektur | ALLOW nur bei exakt AUDIT_ARCH_X86_64 |
| x32/Legacy | Alle 512..547 und Bit-30-/negative Nummern KILL; auch i386/andere ARCHs zuerst KILL |
| Unbekannte Nummern | Kein weiterer ALLOW-Pfad im vollständigen 32-Bit-Nummernraum; zusätzliche konkrete Grenz-/Zufallswerte abgewiesen |
| prlimit64 | pid-Wörter an Offsets 16/20 und new_limit-Wörter an 32/36 jeweils exakt 0; alle 128 Einzelbit-Abweichungen abgewiesen |
| prctl | Gesamtes Optionswort nur 3/21/23/39/47; bei 47 nur vollständige Suboption 1; High-Word-Abweichungen und Setter abgewiesen |
| Getter-Restargumente | Unbenutzte/getter-eigene Argumente dürfen zu Kernel-EINVAL führen, eröffnen aber keinen schreibenden Optionspfad |
| Reset-/Erzeugungspfade | Exec59/322, clone/fork/vfork/clone3, UID/GID/FS-ID-/Cap-/Limitsetter haben für keine Argumente einen ALLOW-Pfad |
| Konkreter Gegenvergleich | 600 deterministische vollständige Zufallsargumentfälle treffen je genau eine symbolische Partition und denselben separaten Interpreterentscheid |

Die Architektur-/Argumentprüfung berücksichtigt, dass Seccomp volle
Registerwörter sieht, bevor manche Syscalls Argumente abschneiden; nur das
Low-Word oder nur AUDIT_ARCH zu prüfen wäre unzureichend. Die historischen
x32-Aliase werden auch unabhängig von der neueren Kernelbehandlung blockiert.
[seccomp(2)](https://man7.org/linux/man-pages/man2/seccomp.2.html).

## 3. ABI und Übergänge

Die vollständige ABI-Abweisung ab Produktzeile 220 wurde mit ELF32/x32,
falscher Maschine, Endianness, OS-/ELF-Kennung, falschen Pointer-/Long-Breiten
und falscher Headerlänge geprüft. Eigene ctypes-Probes vergleichen BPF-Feld-
Offsets 0/2/3/4, SockFprog-Offsets 0/8 und die vollständigen emittierten Bytes.
Ein **Python-Callable als künstliche syscall-Grenze**, kein Kernelaufruf,
bestätigt die übergebenen seccomp-Nummer/Operation/TSYNC-Werte 317/1/1 und den
korrekten Programmzeiger/Inhalt. Die Linux-LP64-Statfs-/Libc-Laufzeitgrenze
bleibt wie im Produkt geschlossen; Windows-Strukturprobes werden nicht als
Linux-Systemaufruf ausgegeben.

Ein eigener `KernelProtocol`, ohne Import des Owner-SimulatedKernel, prüft:

- Vorbedingung gleiche nichtprivilegierte Real-/Effektiv-/Saved-/Filesystem-IDs,
  keine Supplementärgruppen, keine relevanten Cap-/Tracer-Abweichungen.
- Initial Dumpable 0/1/2 wird genau einmal auf 0 gebracht; fehlende/falsche
  SET-Wirkung, Boolean/ungültige GET-Werte und Verlust nach Filter sind Fehler.
- Dumpable-SET und direkte Vorab-Rücklesung liegen vor Filter; sämtliche
  Limitänderungen ebenso; danach bleibt nur der zulässige lesende Pfad.
- Filterinstallation und endgültige Messwerte müssen übereinstimmen;
  teilweiser Fehler erzeugt keinen erfolgreichen Rückgabepfad.
- `no_children` ab Produktzeile 364 akzeptiert nur tatsächliches ECHILD-
  Ergebnis seines nativen Wrappers. Simuliertes None/Exitobjekt/anderes errno
  sind keine leere Kindmenge; WNOWAIT und __WALL müssen gesetzt sein.
- Die Signalmasken-/FD-Abschlussfolge von `_run` bleibt nach einem simulierten
  Teilfehler erhalten, ohne ungeschützten Fallback.

Diese Doubles prüfen das Protokoll und den Kontrollfluss. Insbesondere
simuliertes EPERM oder Dumpable0 ist ausdrücklich keine native Enforcement-
Evidenz. Rückgaben und Policyhash sind weiterhin keine vom Caller unabhängig
authentifizierte Start- oder Budgetautorität.

## 4. Reproduktion und ausstehende native Gates

Finaler lokaler Befehl mit neuem Python-3.12-QA-venv:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider `
  .pytest_tmp/task31-review-20260912-01/test_guard_independent.py `
  tests/test_context_preparation_process_guard.py `
  --basetemp=.pytest_tmp/task31-review-bt-02 --junitxml=.pytest_tmp/task31-review-02.xml
```

Die genannten Basetemp-/XML-Pfade existieren bereits. Wiederholungen benötigen
neue Namen; weder die erste 59-Test-Probe noch andere Evidenz wurde gelöscht.
Alle fünf Ownertests für echte Linux-Ausführung blieben auf Windows skipped.

Nach diesem portablen Review kann Root den bereits vorgesehenen isolierten
nativen Negativ-/Positivprüfschritt ausführen: echter gleicher PID/Interpreter,
Dumpability vor/nach Arbeit, Exec-/Fork-/Thread-/Limit-/Socket-Ablehnung,
CPU-/AS-/FSIZE-Reaktion, unveränderter Parent und numerische/SQLite-
Kompatibilität. Die vorhandenen nativen Ownerfälle enthalten noch keinen
nativen Socket-Aufruf oder ARCH/SIGSYS-/Crashfall; aus ihren Namen/Zahlen ist
ein solcher Nachweis nicht abzuleiten. Ein geplanter zusätzlicher Crash-/ABI-
Fall muss zuerst Roots isolierte Guard-/Supervisor-Voraussetzungen erfüllen;
dieser Reviewer hat keinen solchen Lauf gestartet oder freigegeben.

RSS, Ausgabe, echte freie Reserve, globale Kosten/Deadlines, Datei-Closure,
physische Allokation, Parent-custody und spätere B-/C6-Abnahme bleiben offen.
Es gibt keine Forderung nach neuer VM, neuem Dienst, globalem sysctl oder
neuem Quotensystem und keine Lockerung des genehmigten Ressourcenvertrags.

Skill: `security-best-practices` wurde vollständig gelesen. Seine vorhandenen
Python-Referenzen behandeln Webframeworks, nicht diesen stdlib-/Seccomp-Pfad;
es wurde daher keine unpassende Framework-Regel übertragen. Der Skill
strukturierte den getrennten Befund-/Restgrenzenbericht; die konkrete native
Auslegung stützt sich ausschließlich auf die verlinkten offiziellen Primärquellen.
