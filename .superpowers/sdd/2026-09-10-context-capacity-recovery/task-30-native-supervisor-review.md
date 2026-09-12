# Task 30 — unabhängiges Supervisor-Review

Datum: 2026-09-12. Prüfer: `c_copy_review`. Arbeitsbereich: ausschließlich eigener ignorierter Probe-/Evidenzcode und dieser Bericht. Keine Produkt-, bestehenden Test-, Git- oder Serveränderung durch den Prüfer.

## Ergebnis und exakter Stand

Vier konkrete Fehlerklassen mit sieben roten Regressionen im gesicherten Erststand wurden von Root korrigiert. Auf dem unten gehashten aktuellen Stand sind diese Fälle geschlossen; im geprüften lokalen Decoder-/Protokoll-/Fehlerpfadumfang bleibt kein weiterer konkreter wichtiger Befund offen. **150 lokale Prüfungen bestanden: 39 unabhängige Probes und 111 Owner-Tests; 0,60 s.** Dies ist keine native Linux-Ausführung, keine B/C-Abnahme und keine globale Quota-Aussage.

| Datei / Evidenz | SHA256 |
| --- | --- |
| `context_preparation_supervisor.py` — final geprüft | `9714c596175798c981604e8e595c68d0ebce9453958fb782f243fcf8d5b40d5f` |
| `tests/test_context_preparation_supervisor.py` — 111 Owner-Tests | `0638b7060ca512639fd1df135a0912dabef7e33aa58cddf5de5d4bc099247528` |
| `.pytest_tmp/test_task30_supervisor_review_ccr01.py` — 39 unabhängige Probes | `6b1ef0d175f0e53bcbfeaaa3ecae52cbd4e9c240ff348b1c92edfa951c75c25e` |
| `.pytest_tmp/task30-supervisor-review-ccr01-baseline.py` — bytegleicher gesicherter Erststand | `786d36611d56f4c0eb034fda5ad46f101128ae15f71a9772a6859d99981d9c6c` |
| `.pytest_tmp/task30-supervisor-review-ccr01-green2.xml` — 150 grün | `e7556438bf08299e8f6b19b3aafb46c244e069b352a5911fd984870e5580b860` |
| `.pytest_tmp/task30-supervisor-review-ccr01-red.xml` — ursprüngliche 7 rot / 14 grün, 0,50 s | `4af5d24ee825deee5ec50fa24a019ef672885e32c2e9c01e7e179e4a2bcba52d` |
| `.pytest_tmp/task30-supervisor-review-ccr01-red2.xml` — dieselben sieben Regressionen, mit finalem Probe-Code erneut rot, 0,58 s | `aa2d6311b1e1f4ccd00c05d1e875225e05284ff3f5ce67ffdee61bf336c503c2` |

## Geschlossene Befunde

1. **STOP ohne begrenzten Reap-Übergang.** Im Erststand konnte eine gesetzte Wall-/Ressourcen-STOP-Ursache bei fortlaufend nichtterminalem `wait4` unbegrenzt weiter durch den normalen Select-Loop laufen. Erst der unabhängige Abbruch nach 80 modellierten Select-Aufrufen erreichte `finally` und damit den Cleanup-Timeout. Jetzt ruft ein normaler STOP unmittelbar die begrenzte `_cleanup` auf; ein Flag verhindert ihre zweite Invocation in `finally`. Geprüft für erfolgreichen Reap, unreapbares Kind sowie Signal-/Wait-Fehler.

2. **Unbekannter Reap verlor eindeutige Custody unter Fehlern/FD-Knappheit.** Im Erststand propagierten ein Signalisierungsfehler, `ECHILD`, ein fehlgeschlagenes zusätzliches `dup(pidfd)` oder ein bereits anfänglich fehlgeschlagenes `pidfd_open` generische Fehler; der vorhandene Handle konnte anschließend geschlossen werden. Vier konkrete rote Varianten. Jetzt wird bei unbekanntem Reap `UnreapedChild` mit der bereits vorhandenen pidfd übertragen, ohne neue FD-Allokation; sie wird aus der internen Close-Menge entfernt. Wenn nie eine pidfd erworben wurde, lautet der explizite STOP `pidfd=None`, nicht Erfolg. Die Probe bestätigt bei vorhandenem Handle: genau diese pidfd bleibt als einziges eigenes FD offen. Falsche Cleanup-PID und nichtterminaler Cleanup-Status sind ebenfalls STOP.

3. **Echte FD-Leckage bei Selector-Konstruktionsfehler.** Der vor dem `try` konstruierte Selector konnte nach tatsächlichem `os.dup` fehlschlagen; das duplizierte FD blieb mit tatsächlichem `os.fstat` lesbar. Die Probe verwendet echte lokale `open`/`dup`/`fstat`/`close`, jedoch weder ein Linux-Verzeichnis-FD noch einen nativen Launch. Jetzt liegt die Konstruktion im geschützten Bereich; das tatsächliche Duplikat ist nach dem injizierten Konstruktorfehler geschlossen. Der rote Probe-Lauf beseitigte sein eigenes geleaktes Test-FD selbst.

4. **Output-Verbrauch über dem erlaubten Rest plus einem Erkennungsbyte.** Der Erststand las stets 65.536 Byte und drainte nach Überschreitung weiter. Jetzt werden stdout und stderr gemeinsam auf höchstens `Rest + 1` pro Read begrenzt; beim ersten Overrun wird der Select-Batch beendet und STOP/Reap statt unbeschränktem Weiterdrainen durchgeführt. Positive Gegenprobe mit beiden tatsächlich durch den Protokoll-Loop konsumierten modellierten Kanälen: zusammen genau 1.048.577 beobachtete Byte, höchstens 1.048.576 zurückbehaltene Byte. Das sind beobachtete Präfixbytes, keine Behauptung über alle vom Kind geschriebenen/ungezählten Pipebytes.

Diese vier Klassen sind auf `9714c596…` geschlossen. Der Review verändert keine festgelegten CPU-, Speicher-, Output- oder Freiraumgrenzen.

## Zusätzliche Gegenprüfungen und Messgrenzen

- Nur Default-`SIGCHLD` passiert den modellierten nativen Owner-Preflight; `SIG_IGN` und ein Handler stoppen vor Launch. Das vermeidet insbesondere stilles Auto-Reaping als Voraussetzung für den direkten Child-/pidfd-Besitz. Es ist kein echter Linux-Signaltest.
- Terminales `ru_maxrss` bei 1 GiB verwirft einen sonst harmlos gesampelten Lauf; fehlender, boolescher, nullwertiger oder negativer Peak liefert keinen Erfolg. Terminale CPU über dem reservierbaren Portionslimit stoppt ebenfalls; NaN/Infinity/negative/nichtnumerische CPU-Werte werden nicht als Nullkosten behandelt.
- Ein beobachteter Verlust der 4-GiB-Reserve bleibt STOP, auch wenn die nächste modellierte Beobachtung wieder ausreichend freien Platz meldet. Das ist Sampling, keine globale physische Schreibquota.
- Ein normaler STOP-Cleanup mit zusätzlich modellierten drei Sekunden wird in Parent-CPU, Elapsed und maximalem Sample-Abstand sichtbar; seine terminale Kind-CPU wird nicht verworfen.
- **Das Resultat endet vor der abschließenden Descriptor-Schließarbeit in `finally`.** Die konkrete Boundary-Probe fügt dort modellierte Arbeit hinzu und bestätigt, dass diese nicht in `parent_cpu_ns`/`elapsed_ns` enthalten ist. Auch Validierung/native Preflight/Guard-Import vor dem Startzeitpunkt und Arbeit des übergeordneten Jobs sind nicht vollständig abgedeckt. Der Modulvertrag verlangt bereits den äußeren Whole-Job-CPU-/Originaldeadline-Owner. Kein Refund oder vollständiger Jobnachweis darf allein aus dem hier zurückgegebenen Fenster abgeleitet werden. Das ist eine geprüfte deklarierte Grenze, kein behaupteter zusätzlicher Fehler.
- Bei Exception-/Unknown-Pfaden gibt es keinen vollständigen erfolgreichen Messdatensatz; ausbleibende Messung erlaubt keine Entlastung der vorher dauerhaft reservierten Kosten. Ein `UnreapedChild` überträgt weitere Kill-/Reap-Pflicht, keine Zulassung.
- Der kanalgerahmte Output-Digest hängt ausdrücklich von Read-Reihenfolge und Chunking ab. Er ist Diagnoseevidenz, nicht die kanonische Identität eines Outputs, einer Quelle oder einer Freigabe.

## Ausführung / Wiederholung

Windows, gebündeltes Python, `-B`, Plugin-Autoload aus; frische, zuvor nicht vorhandene Basetemps/XML pro Lauf. CPU-/Zeitwerte der Syscall-Simulation sind keine Performance-Messung und kein nativer Benchmark. Der laufende Root-QA-Kohort wurde nicht verändert.

```powershell
$env:PYTHONPATH='C:/Projekt/BetBoy/betboy-app/.venv/Lib/site-packages'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:TASK30_REVIEW_TARGET='C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/context_preparation_supervisor.py'
& 'C:/Users/miros/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m pytest -q .pytest_tmp/test_task30_supervisor_review_ccr01.py tests/test_context_preparation_supervisor.py --basetemp=.pytest_tmp/task30-supervisor-review-ccr01-green2 --junitxml=.pytest_tmp/task30-supervisor-review-ccr01-green2.xml
```

Das ist der tatsächlich ausgeführte GREEN-Befehl, nicht zum Überschreiben seiner bestehenden Artefakte bestimmt. Bei einer Wiederholung neue Namen verwenden. Für die sieben ursprünglichen RED-Fälle das Target auf die gesicherte Baseline setzen und im eigenen Probe-Modul die vier Testfunktionen `test_stop_enters_bounded_reaping_without_external_probe_cutoff`, `test_unknown_cleanup_paths_remain_explicit_stop_with_existing_ownership` (vier Parameterfälle), `test_selector_constructor_failure_closes_actual_duplicated_fd` und `test_output_reads_respect_combined_remaining_plus_one_not_64k_overshoot` auswählen. Der zweite rote Lauf tat genau dies mit dem finalen Probe-SHA; keine Erfolgsbedingung wurde für Grün abgeschwächt. Das OS-Testdouble wurde lediglich um die neuen terminalen Statusprädikate erweitert.

## Unverändert offen / Übergabe

Hier wurde kein echter Linux-Root-Koordinator, Capability-Drop, seccomp-Install/Exec, pidfd-Signalisierung, `wait4`, nativer Kernel-Peak oder vollständiger Namespace-Schreibabschluss ausgeführt. Der separat entstehende Process-Guard wurde auf die erwartete Supervisor-Aufrufreihenfolge gelesen, nicht als unabhängige native Zulassung übernommen. Kernel-/Core-/Apport-Risiken einer späteren nativen Crash-Probe sind hier nicht freigeprüft.

Eine dauerhaft verbuchte Reservation, der vollständige und gegen Austausch geschlossene Namespace-/Executable-/Input-Seal-Vertrag, die ganze ursprüngliche Job-Deadline/CPU, Root-/Registry-Bindung und eine globale physische Write-Envelope bleiben externe Voraussetzungen. Dieser Befund ergänzt C/Task-22, ersetzt sie nicht. Nächster Schritt ist der getrennte native Integrationsnachweis unter konkret gebundenem Profil; keine Produktionsintegration, Limitlockerung, neue OS-Dienste oder globalen Kerneländerungen werden durch diesen Bericht autorisiert.
