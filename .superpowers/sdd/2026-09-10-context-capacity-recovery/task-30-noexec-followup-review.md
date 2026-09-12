# Task 30 — unabhängiger NoExec-Folgereview

Stand: 2026-09-12. Ergänzung zum unveränderten ursprünglichen Bericht `task-30-native-supervisor-review.md`; Prüfer `c_copy_review`. Nur eigene ignorierte Probes/Evidenz und dieser Bericht wurden geschrieben. Keine Produkt-, bestehenden Test-, Git-, Server- oder Hostkonfigurationsänderung.

## Ergebnis / Bindung

**173 lokale Prüfungen bestanden, 0 Fehler, 0 übersprungen, 2,06 s**: die bisherigen 39 unabhängigen Regressionen, 23 zusätzliche NoExec-Probes und 111 vollständige Owner-Tests. Kein konkreter neuer wichtiger Befund im schmalen Startvertrags-/Dispatcher-Diff. Die sieben ursprünglich roten Lifecycle-/FD-/Output-Fälle aus dem Erststand bleiben geschlossen. Keine native Linux-, Dumpable-, seccomp-, Apport-, B- oder globale Quota-Abnahme.

| Datei / Evidenz | SHA256 |
| --- | --- |
| `context_preparation_supervisor.py` — aktueller NoExec-Stand, vollständig gelesen | `4927e3b36d2af50eb169ce8ae672e13ed89e7cb2f241d8d649b6166a5a86c217` |
| `tests/test_context_preparation_supervisor.py` — vollständig gelesen / 111 Tests | `8d008ab07365e2145b01aeb763cba5c380b60edaf68ebec79b8140d6cd685dba` |
| `.pytest_tmp/test_task30_noexec_review_ccr01.py` — 62 unabhängige Fälle | `4281647a5a4540e3af1b250137b885c883135c1a5a82d008f95f1a8d7cf38ea6` |
| `.pytest_tmp/task30-noexec-dispatch-helper-ccr01.py` | `4b6364c218229f2b112d990ff4202329d26da716abcc10e9e38ad96ad12a821c` |
| `.pytest_tmp/task30-noexec-worker-ccr01.py` | `9e95bb3ca76806735bee92948cd359ad72d5739e121636be37c145e09ca46c2e` |
| `.pytest_tmp/task30-noexec-review-ccr01-run1.xml` — vorherige 39 + 111 grün | `6cd0ba8fc334d819f9085277d5086688977ce2c6380ce9ead88cd3ff19ee6db5` |
| `.pytest_tmp/task30-noexec-review-ccr01-run2.xml` — alle 173 grün | `aa3faa132af56a722f58b04afb29bdedc35096cb24988396b0648fe72115aae9` |

Die ursprünglichen ignorierten Task30-Probes und der ursprüngliche Reviewbericht bleiben als Evidenz des alten Stands erhalten. Für die NoExec-Fassung wurde eine eigene Probe-Datei angelegt. Bei den vorherigen Tests wurden ausschließlich gültige absolute `.py`-argv statt Interpreter-argv und die neuen ausdrücklich modellierten `sys.flags`-/`sys.modules`-Voraussetzungen ergänzt. Separater AST-Vergleich: alle **53 ursprünglichen Assert-Knoten in 17 parametrisierten Testfunktionen** sind unverändert. Auch die alten Exception-Erwartungen wurden nicht gelockert.

## Überprüfter Startvertrag

Der neue öffentliche Startwert ist ein absoluter Python-Workerpfad mit `.py`-Suffix und begrenzten Argumenten, kein allgemeines Executable-Kommando. Der native Coordinator verlangt `-I -S -B`, unverändert einen frischen einzelnen Root-Hauptthread und Default-SIGCHLD. Bereits geladene Nicht-stdlib-Module außerhalb der drei genannten Koordinatorbausteine werden zurückgewiesen. Neue Gegenproben verwerfen jede fehlende Flag sowie vorimportiertes SciPy, pytest oder ein Worker-Modul. Das ist eine Startbedingung, keine Authentifizierung beliebiger gleichnamiger Python-Module; Runtime-/Code-Closure und geschützter Importpfad bleiben dem Owner vorbehalten.

Der gelesene Child-Pfad enthält keinen anschließenden exec-Aufruf. Er leitet die eigenen Standard-FDs um, schließt zusätzliche FDs, setzt die neue Arbeitsumgebung, entfernt alte Umgebungsvariablen, konfiguriert feste Einthread-Librarywerte und führt erst dann Bounding-Drop, Gruppen-/GID-/UID-Drop, Guard und SIGSTOP aus. Erst nach Rückkehr vom STOP gelangt er zu runpy. Der Parent bleibt für den tatsächlichen Kernelreadback und das SIGCONT verantwortlich. Der bestehende Reap-/pidfd-/Output-/Terminal-RSS-Pfad bleibt im geprüften Verhalten erhalten. Ein gesonderter Test prüft das Flushen beider Coordinator-Ausgabestreams vor dem modellierten Fork.

## Echte lokale Dispatcher-Ausführung und klare Modellgrenze

16 neue Fälle starten jeweils einen echten kurzlebigen **Windows-Python-Unterprozess**, rufen darin die tatsächliche private `_child_run_python`-Implementierung auf, führen den fest hinterlegten eigenen Worker tatsächlich mit `runpy.run_path` aus und beenden den Testprozess mit tatsächlichem `os._exit`. Runpy, stdout/stderr-Flush, SystemExit-Übersetzung, argv, bereinigte Prozessumgebung und PID sind dabei real.

**Nur die Linux-/Privileggrenze ist modelliert:** dup2/close-extra/chdir, Bounding-/GID-/UID-Drop, Guard-Install und SIGSTOP werden aufgezeichnet bzw. gezielt zum Fehler gemacht. Es wurde kein Linux-fork, nativer Capability-Drop, seccomp-Filter, echter STOP/CONT-Handshake oder Dumpable-Readback durchgeführt. Diese private Testnaht umgeht kein Produktionsgate zugunsten einer Abnahme.

Die tatsächliche Dispatcher-Ausführung bestätigt:

- Vorgeschriebene Reihenfolge: FD-Schritte, Umgebung, Bounding-Drop, leere Gruppen, vollständige GIDs/UIDs, Guard mit unveränderten 4096/300-Testgrenzen, STOP und erst anschließend Worker-Eintritt.
- Worker `__name__ == '__main__'`, exakt weitergereichte Script-Argumente und dieselbe tatsächliche PID beim modellierten STOP und im laufenden Worker.
- Vollständig entfernte geerbte Umgebungswerte; ausschließlich PATH, LANG, TMPDIR und die fünf festen Einthread-Libraryvariablen bleiben. Es wurden keine ursprünglichen Secret-/Umgebungswerte ausgegeben.
- Normaler Return sowie SystemExit None/0 liefern 0; 7 und 255 bleiben erhalten. Negative, zu große, boolesche und textuelle Exitwerte liefern 125. Eine gewöhnliche Python-Exception liefert 125 und nur die feste Fehlermeldung, keine native Crash-Probe.
- Fehler in jeder der sechs Phasen Bounding-Drop/Gruppen/GID/UID/Guard/STOP führen zu 125, ohne den tatsächlichen Worker auszuführen.

## Unveränderte Grenzen / nächste Handlung

Die NoExec-Verengung wurde von Root wegen seines separat beobachteten piped-Core-/Apport-Hosts eingeführt. Dieser Reviewer hat den Host nicht untersucht und erklärt keine Corefreiheit. Der separate Process-Guard einschließlich Dumpable0 sowie Verbot von exec/SET_DUMPABLE ist Gegenstand des getrennten Guard-Reviews/native Integrationsnachweises, nicht eines aus diesem Protokolltest abgeleiteten Pass.

Insbesondere deckt dieses Resultat keinen vollständigen Job-CPU-/Deadline-Zähler, keine Reservierungsregistry, keine Input-/Executable-/Namespace-Schließung, keine globale physische Write-Envelope und keine Publikation ab. Die im ursprünglichen Task30-Bericht gemessene Fenstergrenze vor den letzten FD-Schließschritten bleibt bestehen. Root darf keinen unbekannten Fehlerlauf allein aus diesen Rückgabewerten entlasten. Der nächste Schritt bleibt der getrennte kleine native Integrationsnachweis unter tatsächlich gebundenem NoExec-/Guard-/Core-/Namespaceprofil; kein Hostumbau oder Scope-/Limitwechsel wird hier autorisiert.

## Ausführung

QA-venv Python 3.12.14, Windows, `-B`, Plugin-Autoload aus, Cacheprovider aus; neue zuvor nicht existierende Basetemp-/XML-Namen. Die Dispatcher-Unterprozesse besitzen zusätzlich ein festes lokales 10-s-Testtimeout. Keine Signal-/Crashprobe außerhalb dieser eigenen Prozesse.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider .pytest_tmp/test_task30_noexec_review_ccr01.py tests/test_context_preparation_supervisor.py --basetemp=.pytest_tmp/task30-noexec-review-ccr01-run2 --junitxml=.pytest_tmp/task30-noexec-review-ccr01-run2.xml
```

Dies ist der ausgeführte Befehl; seine Artefakte existieren bereits. Für weitere Läufe neue Namen verwenden und nichts überschreiben.
