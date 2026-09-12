# Task 28: enger Single-Process-Guard für den C-QA-Worker

Stand: 2026-09-12. Owner: `c_snapshot_review`. Neuer stdlib-only Baustein,
keine Änderung an Task 23, bestehendem Produktcode, Modellen oder anderen
Owner-Dateien. Kein Git, SSH, Serverlauf, Dienst, cgroup oder neuer OS-Benutzer.

## Ergebnis und eingefrorene Bytes

Der Guard ist implementiert und lokal protokoll-/policygeprüft, aber auf diesem
Windows-Host **nicht nativ durchgesetzt oder freigegeben**. Er ist ein Baustein
für Roots separat entstehenden Launcher/Meter, kein vollständiger Sandbox-,
Kostenbuch-, Mess- oder C/B-Abnahmenachweis.

| Datei/Artefakt | SHA256 |
| --- | --- |
| `context_preparation_process_guard.py` | `62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4` |
| `tests/test_context_preparation_process_guard.py` | `3620436ea09686e32df8fc2457111ebc92ec5b779e9a093e8f141be50c8f9777` |
| `.pytest_tmp/task28-guard-run-20260912-4.xml` | `748335441c391eee3ad965895e7d97f93803e5a436b34714b6097e1bed6189c9` |
| Emittierte 378 BPF-Instruktionen, Little-Endian-Rohbytes | `fa959325efde6e1ba9d73b893bf9a193173ec8cb99d91758ac5331beb99e8477` |

## Begründete Verengung nach Hostaufnahme

Root meldete aus seiner tatsächlichen VPS-Lektüre eine Apport-Pipe als
core_pattern sowie suid_dumpable=2. Der von Root geprüfte Handler
`/usr/share/apport/apport`, SHA256
`1b8b5e2c53e8970dd2f47c9a0892030d1ebad57cae1f7242c43a6252f1f6dff2`,
erzeugt laut dieser Lektüre trotz core_ulimit=0 Crash/Info-Reports. Dieser Agent
hat den VPS/Handler nicht selbst gelesen oder ausgeführt. Allgemein wird
RLIMIT_CORE bei gepipten Cores nicht erzwungen.
[core(5)](https://man7.org/linux/man-pages/man5/core.5.html).

Deshalb beschloss Root den engeren rein-Python-Pfad: **kein OS-exec nach
UID-Drop und Guard**. Das bestehende Kind setzt Dumpable auf 0, liest 0 vor und
nach dem Filter zurück und bleibt im selben Interpreter. Beide Exec-Syscalls,
UID/GID-/Filesystem-ID-Setter und PR_SET_DUMPABLE fehlen in der installierten
Policy; nur PR_GET_DUMPABLE kommt als neue lesende Option hinzu. Die Bedeutung
und möglichen Credential-Resets sind in
[PR_SET_DUMPABLE(2)](https://man7.org/linux/man-pages/man2/PR_SET_DUMPABLE.2const.html)
und das direkte Rücklesen in
[PR_GET_DUMPABLE(2)](https://man7.org/linux/man-pages/man2/PR_GET_DUMPABLE.2const.html)
dokumentiert. Es gibt keinen Boolean/Schalter, der Exec oder Dumpable wieder
freigibt. Keine globale Hostkonfiguration wurde geändert.

## Abgestimmte Launcher-Schnittstelle

1. Der vertrauenswürdige ein-threadige Parent importiert das Guard-Modul vor
   seinem eigenen `os.fork()`.
2. Nur das direkte Kind gegenüber dieser tatsächlich beim Import beobachteten
   PID darf `drop_worker_capability_bounding_set()` aufrufen. Es muss reale,
   effektive und gespeicherte UID 0 sowie tatsächliches effektives
   `CAP_SETPCAP` haben. Die Funktion entfernt ausschließlich die Bounding-Bits
   des aufrufenden Kindes und liefert `BoundingSetReadback(pid, cap_last_cap,
   bounding_mask=0)` nach Rücklesen. Sie ändert weder Parent noch Host und
   behauptet nicht, bereits alle anderen Capability-Sets entfernt zu haben.
3. Root übernimmt danach `setgroups([])`, `setresgid(gid,gid,gid)` und
   `setresuid(uid,uid,uid)` mit einer bestehenden nichtprivilegierten Identität.
4. Das Kind ruft
   `install_single_process_guard(*, file_size_bytes: int, cpu_seconds: int=300)`
   auf, weiterhin vor Produktimporten. Die API liefert eine kleine
   `GuardReadback`-Dataclass einschließlich `dumpable=0`. `execve` und `execveat`
   sind danach verboten. Parent-`pidfd`/Stop/Rücklesen/Resume/`wait4` und Closure-
   Prüfung bleiben bei Root. Erst nach Guard und bestätigtem Parent-Readback
   lädt das unveränderte Python-Kind den versiegelten Worker über `runpy`.
5. Jede Exception bedeutet: **dieses möglicherweise bereits teilweise
   eingeschränkte Kind verwerfen, kein Workerstart**. Kein Rollback von Caps,
   Hard-Limits, `no_new_privs` oder Filter, kein alternativer ungeschützter Pfad.

Keine öffentliche API nimmt `root_verified`, `measurement_passed`, `complete`
oder einen vergleichbaren Assurance-Boolean an. Dataclasses und Digests sind
Beobachtungen und Identifikation, keine authentifizierte Start-/Messautorität.
Der direkte-PID-Abgleich verhindert versehentliche Parent-Nutzung im
vorgesehenen Launcher; er ersetzt keine geschützte Prozess-/Codeprovenienz.

## Native Prüfungen und Übergänge im Code

Der öffentliche Pfad verweigert andere Plattformen, CPU-Architekturen,
Endianness, Pointer-/Long-Breiten oder ELF-ABIs. Zulässig ist Linux x86_64 LP64
mit ELF64-Little-Endian und Machine 62; auch die `ctypes`-Strukturgrößen werden
geprüft. `/proc` bleibt per FD gehalten; gelesene Statusobjekte und Taskverzeichnis
müssen per `fstatfs` tatsächlich procfs sein. Das ist keine vollständige
Namespace-/Parent-Seal-Authentifizierung.

Statusdaten sind auf 64 KiB begrenzt, Taskauflistung stoppt nach dem zweiten
Eintrag, Capability-Obergrenze auf drei Bytes und 0..63. Fehlende oder doppelte
Felder, unpassende Kodierung, unbekannte Messformen und widersprüchliche
Rücklesungen werden abgewiesen. `Pid`, `Tgid`, `PPid`, `TracerPid`, genau eine
Task-ID, vier UID-/GID-Werte, Supplementärgruppen, fünf Cap-Sets sowie
`NoNewPrivs`, `Seccomp` und `Seccomp_filters` müssen passen. `/proc`-IDs werden
mit `getresuid/getresgid/getgroups`, drei Cap-Sets mit direktem `capget` V3 und
Bounding/Ambient-Bits mit `prctl` abgeglichen. Alle Capability-Sets müssen beim
unprivilegierten Guard null sein, einschließlich CapBnd. Die Semantik der
Kernel-Statusfelder ist in [proc_pid_status(5)](https://man7.org/linux/man-pages/man5/proc_pid_status.5.html)
beschrieben.

`cap_last_cap` wird frisch gelesen, jedes Bit abgefragt und die unmittelbar
nächste Nummer muss `EINVAL` ergeben. Der privilegierte Helper droppt jedes
bekannte Bit und liest danach die vollständige Nullmaske zurück. Unbekannt
größere Capability-Bereiche werden nicht still abgeschnitten.
[capabilities(7)](https://man7.org/linux/man-pages/man7/capabilities.7.html),
[PR_CAPBSET_DROP(2)](https://man7.org/linux/man-pages/man2/PR_CAPBSET_DROP.2const.html).

Zusätzlich muss nicht-reapendes
`waitid(P_ALL, WEXITED|WNOHANG|WNOWAIT|__WALL)` `ECHILD` ergeben; `None` ist kein
Erfolg, sondern ein möglicher lebender Kindprozess. Die frische Fork-Provenienz
bleibt Pflicht: Bereits früher entkommene/reparentete Prozesse werden hier
nicht nachträglich aus einem Scan ausgeschlossen. Auf `/proc/children` als
Baumvollständigkeitsbeweis wird ausdrücklich nicht vertraut, da dessen Liste
bei exitenden Kindern unvollständig sein kann.
[proc_tid_children(5)](https://man7.org/linux/man-pages/man5/proc_tid_children.5.html).

Während des Übergangs werden blockierbare Signale gesperrt und anschließend
die vorherige Maske wiederhergestellt. Die vorgefundene Dumpability muss als
echter Integer 0, 1 oder 2 messbar sein; nach Credential-Abgabe wird sie genau
einmal per PR_SET_DUMPABLE auf 0 gesetzt und vor/nach Filter direkt bestätigt.
Die Limits werden vor dem Filter gesetzt
und unmittelbar sowie nachher erneut exakt zurückgelesen:

| Limit | Soft und Hard |
| --- | --- |
| CPU | echter Integer 1..300 Sekunden; Default 300 |
| AS | exakt 2 GiB |
| CORE | exakt 0 |
| NPROC | exakt 0 |
| FSIZE | echter Integer 0..8 GiB, vom Launcher enger vorzugeben |

Niedrigere CPU-Werte dienen insbesondere kurzen nativen Faulttests. Boolean,
Float, String, negative oder zu große Eingaben werden vor nativen Änderungen
abgewiesen. Ein geerbtes niedrigeres Hard-Limit wird nicht angehoben oder
heimlich anders ausgelegt. NPROC ist nur eine Zusatzlage: Linux zählt dabei
Threads pro Real-UID und kennt privilegierte Ausnahmen; deswegen reichen
NPROC und eine effektive UID allein nicht. AS ist kein RSS-Meter; FSIZE betrifft
logische Dateierweiterung, nicht Gesamtbelegung, physische Extents, freie Platte
oder eine globale 8-GiB-Quota. Linux-RLIMIT_RSS wird nicht als wirksame Kontrolle
ausgegeben. Die Unterschiede folgen [getrlimit(2)](https://man7.org/linux/man-pages/man2/getrlimit.2.html).

## Feste seccomp-Policy

Nach `PR_SET_NO_NEW_PRIVS=1` und bestätigtem Rücklesen wird mittels
`seccomp(SECCOMP_SET_MODE_FILTER, SECCOMP_FILTER_FLAG_TSYNC, ...)` genau ein
Filter angehängt. Nur exakte Rückgabe 0 gilt; ein positiver nicht synchronisierter
Thread-ID-Rückgabewert ist Fehler. Danach müssen Filtermodus 2, Filteranzahl
vorher+1, NNP 1, dieselben IDs/Caps, genau eine Task und sämtliche Limits erneut
stimmen; zusätzlich muss PR_GET_DUMPABLE weiterhin 0 liefern. Die
unprivilegierte Rücklesung bestätigt Modus/Anzahl/Zustand, nicht
per privilegiertem Ptrace die einzelnen Kernel-BPF-Bytes; die emittierten
Programmbytes sind separat gehasht und lokal interpretiert geprüft.

Erste Regel ist `AUDIT_ARCH_X86_64`, danach x32-Ablehnung einschließlich
Syscall-Bit 30 und negativer Nummern. Die historischen x32-Aliase 512..547
werden ebenfalls getötet. Architekturverletzungen liefern `KILL_PROCESS`,
sonstige nicht aufgeführte Aufrufe `ERRNO(EPERM)`; kein ranges-basiertes Freigeben
künftiger Nummern. ARCH allein genügt nicht für x32. Die Auslegung folgt
[seccomp(2)](https://man7.org/linux/man-pages/man2/seccomp.2.html).

Die 166 unbedingten erlaubten Nummern/Namen sind unten vollständig festgehalten;
Quelle der ABI-Zuordnung ist die fest benannte
[Linux-v6.12-Syscalltabelle](https://raw.githubusercontent.com/torvalds/linux/v6.12/arch/x86/entry/syscalls/syscall_64.tbl).
Es gibt keine Laufzeit-Erweiterung anhand des Host-Kernels.

```text
0:read 1:write 2:open 3:close 4:stat 5:fstat 6:lstat 7:poll 8:lseek
9:mmap 10:mprotect 11:munmap 12:brk 13:rt_sigaction 14:rt_sigprocmask
15:rt_sigreturn 16:ioctl 17:pread64 18:pwrite64 19:readv 20:writev
21:access 22:pipe 23:select 24:sched_yield 25:mremap 26:msync 27:mincore
28:madvise 32:dup 33:dup2 34:pause 35:nanosleep 36:getitimer 37:alarm
38:setitimer 39:getpid 40:sendfile 60:exit 61:wait4 62:kill
63:uname 72:fcntl 73:flock 74:fsync 75:fdatasync 76:truncate 77:ftruncate
78:getdents 79:getcwd 80:chdir 81:fchdir 82:rename 83:mkdir 84:rmdir
85:creat 86:link 87:unlink 88:symlink 89:readlink 90:chmod 91:fchmod
95:umask 96:gettimeofday 97:getrlimit 98:getrusage 99:sysinfo 100:times
102:getuid 104:getgid 107:geteuid 108:getegid 110:getppid 111:getpgrp
115:getgroups 118:getresuid 120:getresgid 121:getpgid 124:getsid 125:capget
127:rt_sigpending 128:rt_sigtimedwait 130:rt_sigsuspend 131:sigaltstack
132:utime 137:statfs 138:fstatfs 140:getpriority 143:sched_getparam
145:sched_getscheduler 146:sched_get_priority_max 147:sched_get_priority_min
148:sched_rr_get_interval 158:arch_prctl 186:gettid 187:readahead 191:getxattr
192:lgetxattr 193:fgetxattr 194:listxattr 195:llistxattr 196:flistxattr
200:tkill 201:time 202:futex 204:sched_getaffinity 213:epoll_create
217:getdents64 218:set_tid_address 219:restart_syscall 221:fadvise64
228:clock_gettime 229:clock_getres 230:clock_nanosleep 231:exit_group
232:epoll_wait 233:epoll_ctl 234:tgkill 235:utimes 239:get_mempolicy
247:waitid 257:openat 258:mkdirat 261:futimesat 262:newfstatat 263:unlinkat
264:renameat 265:linkat 266:symlinkat 267:readlinkat 268:fchmodat
269:faccessat 270:pselect6 271:ppoll 273:set_robust_list 274:get_robust_list
280:utimensat 281:epoll_pwait 282:signalfd 283:timerfd_create 284:eventfd
286:timerfd_settime 287:timerfd_gettime 289:signalfd4 290:eventfd2
291:epoll_create1 292:dup3 293:pipe2 295:preadv 296:pwritev 309:getcpu
315:sched_getattr 316:renameat2 318:getrandom 324:membarrier
326:copy_file_range 327:preadv2 328:pwritev2 332:statx 334:rseq
436:close_range 437:openat2 439:faccessat2 441:epoll_pwait2 449:futex_waitv
452:fchmodat2
```

Zwei weitere Nummern haben eigene Argumentregeln: 302/prlimit64 nur für
`pid=0,new_limit=NULL`, beide Hälften der 64-Bit-Werte geprüft; 157/prctl nur
GET_DUMPABLE, GET_SECCOMP, GET_NO_NEW_PRIVS, CAPBSET_READ und CAP_AMBIENT/IS_SET. Setter,
Filteränderungen und Capability-Drops sind nach Installation nicht freigegeben.
clone/fork/vfork/clone3, execve/execveat, io_uring/AIO, unshare/setns, ptrace,
process_vm_writev, bpf, userfaultfd und künftige unbekannte Syscalls fehlen.

Das bleibt bewusst ein enger Prozess-/Thread-Guard: insbesondere offene FDs,
Dateipfade, `ioctl`, erlaubte Signal-/Dateiaufrufe und die Python-Ladeziele
brauchen die äußere Closure-/Namespace-Kontrolle. seccomp ist nicht allein eine
Sandbox, wie auch die [Kernel-Dokumentation](https://docs.kernel.org/userspace-api/seccomp_filter.html)
ausdrücklich klarstellt.

## Lokale QA und noch offene native Ausführung

Finaler Lauf im zugewiesenen Python-3.12-QA-Runtime, neues zuvor nicht existentes
Basetemp und separate XML-Datei:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -m pytest tests/test_context_preparation_process_guard.py -q -p no:cacheprovider -o junit_family=xunit1 --basetemp=.pytest_tmp/task28-guard-run-20260912-4 --junitxml=.pytest_tmp/task28-guard-run-20260912-4.xml
```

**147 passed, 5 skipped in 0,51 s.** Lokale Evidenz: geschlossene Decoder,
Grenzwerte, sämtliche Syscallnummern 0..4095 plus Hochbitfälle, BPF-Argument-
Halbwörter, deterministische native Strukturbytes, instrumentierte Übergangs-
reihenfolge und konsequente Verweigerung bei falschen Rücklesungen. Zusätzlich:
jede gültige initiale Dumpability wird auf 0 gebracht, unmessbare Zustände
werden verworfen, ein nur behauptetes SET-Ergebnis bzw. nachträglich verlorenes
Null-Readback liefert keinen Erfolg, beide Exec-Nummern und Dumpable-Setter
sind im emittierten BPF abgewiesen. Der SimulatedKernel ist ausdrücklich nur
ein Protokollmodell. Er ist weder reale
Cap-/UID-Abgabe noch Kernel-seccomp-, Ressourcen- oder CPU-Messevidenz.

Im Erstlauf überschritt die automatisch erzeugte Test-ID der 64-KiB-Negativprobe
die Windows-Grenze für `PYTEST_CURRENT_TEST` (32767 Zeichen). Test-IDs wurden
auf kurze Hashbezeichner begrenzt; der getestete Payload bleibt unverändert.
Das war Test-Setup/-Teardown, keine gelockerte Produktgrenze.

Die fünf separat übersprungenen Linux-Proben sind:

- `test_native_public_api_refuses_importing_parent_without_changes`.
- `test_native_linux_child_enforcement_and_parent_unchanged[denials]`:
  direkte EPERM-Resultate für clone/fork/vfork/clone3/execve/execveat/io_uring/unknown
  sowie PR_SET_DUMPABLE=1, fortbestehendes GET_DUMPABLE=0,
  fehlgeschlagener Python-Threadstart, tatsächliche 2-GiB-AS-Ablehnung und
  tatsächliche FSIZE-4096-Erweiterungsverweigerung; Parent-Caps unverändert.
- `[python]`: SQLite-Operationen im unveränderten Python/PID, weiterhin
  NNP 1/Threads 1/Dumpable 0, ohne OS-exec.
- `[numeric]`: NumPy/SciPy-Lösung plus derselbe SQLite-/Threadcheck, ausschließlich
  bei tatsächlich verfügbaren numerischen Abhängigkeiten.
- `[cpu]`: CPU=1-Hard-Limit mit ignoriertem SIGXCPU, erwartetes echtes SIGKILL;
  Parent-Caps unverändert.

Native Kindproben laufen in einem getrennten `-I -S -B`-Python-Testprozess, der
das genaue Guard-Modul explizit vor fork lädt. Nur sein wegwerfbares Root-Kind
droppt CapBnd, anschließend
Gruppen/GIDs/UIDs auf den schon vorhandenen `nobody`-Account. Pytest selbst wird
nicht eingeschränkt. Der numerische Same-Process-Lauf erhält die
Single-Thread-Variablen für OpenBLAS, OMP, MKL, NumExpr, GotoBLAS, BLIS und vecLib
vor den Imports. Explizite App-Site-Packages-Pfade werden ausschließlich nach
Guard in das unprivilegierte Kind eingefügt, nicht in den isolierten Parent.
Die Filter-/Ressourcenroutinen selbst importieren keine dieser Bibliotheken.
Diese numerische Kompatibilität bleibt bis zur echten Probe offen.

**Keine native ARCH/SIGSYS-/Crashprobe ist vorbereitet oder ausgeführt.** Root
hat die vorgeschaltete Aufnahme des tatsächlichen Host-Coredump-Verhaltens
übernommen; die oben dokumentierte Apport-Evidenz führte zur Dumpable0/no-exec-
Verengung. CORE0 allein begrenzt gepipte core_pattern-Handler nicht. Der neue
Null-Dumpability-Pfad ist noch nicht nativ geprüft und daraus wird hier keine
gemessene globale Crash-Disk-Garantie gemacht. Keine globale Kernelkonfiguration
wurde verändert.

## Erhaltene Erstentwurf-Evidenz, nicht aktueller Freigabestand

Vor Roots Apport-Aufnahme besaß der erste Entwurf noch OS-exec-Freigaben und
keine Dumpable0-Sperre. Seine Bytes bleiben exakt bezeichnet:

- Produkt-SHA256 `d936dbb7a7b65a28e5bfcf37f387f1cabf8426b6d7d382d0cb9f61435cb7291b`.
- Tests-SHA256 `187e4c051b9d69018d467cd9383f59c472d22c82a8e4ec38e09ed2a5a128697f`.
- 380-Instruktions-Policy `256e1314c667545844864056641fda1183d5cfb19a7c95eddb29aa7c6fcbcfda`.
- **130 passed, 5 skipped in 0,49 s** in
  `.pytest_tmp/task28-guard-run-20260912-3.xml`, SHA256
  `b2e8ea3ca1c64254c55b39f27ee7921928d574840bad497ddde75f711bc7bb95`.

Diese Artefakte wurden nicht überschrieben. Ihre grünen Protokolltests schließen
die später erkannte Coredump-/Exec-Integrationslücke nicht; native Ausführung
dieses Erstentwurfs erfolgte durch diesen Agenten nicht.

## Offene Integrations-/Abnahmegrenzen

Der neue unabhängige Review durch `c_source_adapter` muss vor jeder Verwendung
abgeschlossen werden; Root führt separat die Launcher-/Meter-Integration.
Danach sind die kleinen echten QA-VPS-Negativ-/Positivproben vor einem Korpuslauf
auszuführen. Ein fehlendes Kernel-Feature, eine fehlende Statusmessung oder ein
inkompatibles numerisches Runtime-Profil stoppt; es gibt kein stilles Allowlist-
Lernen oder Rückfallen auf nur NPROC.

CPU-/RSS-/Ausgabe-/Free-Space-Meter, elapsed Deadline, Budgetsettlement inklusive
Parentkosten, pidfd-/wait4-Lifetime, geschützter Publisher, Registry, Datei-/FD-
Namespace und transitive Runtime-/Python-Closure gehören ausdrücklich nicht zu
diesem Modul. Keine Ein-Prozess-Garantie für vor der vertrauenswürdigen frischen
Fork-Sequenz entkommene Prozesse, keine Modelländerung und keine Freigabe aus
den Windows-Testzahlen.

Verwendeter Skill: `security-best-practices`; dessen verfügbarer Python-Anteil
enthält Webframework-Leitfäden, keine native seccomp-Anleitung. Daher wurden
für die native Auslegung ausschließlich offizielle Kernel-/man-pages-Quellen
herangezogen. Der Skill beeinflusste die fail-closed Defaults und die explizite
Trennung zwischen Protokolltests, nativer Evidenz und äußerer Autorität.
