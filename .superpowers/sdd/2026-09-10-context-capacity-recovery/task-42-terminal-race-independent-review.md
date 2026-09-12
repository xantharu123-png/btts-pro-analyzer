# Task 42 — unabhängiger Review der terminalen RSS-Race

Stand 12. September 2026. Vollständiger Supervisor und seine Owner-Tests gelesen;
eigene davon unabhängige portable Ablaufproben erstellt. Kein Produktcode, kein
bestehender Owner-Test, Git, Server, Guard oder nativer Prozess wurde durch
diesen Task geändert/gestartet. Auf Roots ausdrücklichen Folgeauftrag wurden
die eigenen Regressionen zusätzlich in die **neue** normale Testdatei
`tests/test_context_preparation_terminal_boundaries.py` übernommen.

## Ergebnis

Zwei konkrete Abweichungen im ersten Fix wurden unabhängig reproduziert und
anschließend von Root korrigiert. Gegen den neuen unveränderten Freeze bestehen
**60 eigene Prüfungen**. Zusammen mit 16 terminalen Ownerfällen, 120
Supervisor-Ownerfällen und 74 vorherigen Task34-Regressionen:
**270 bestanden, 0 Fehler, 0 übersprungen, 3,04 s**; JUnit-Suitezeit 2,980 s.
Keine weiteren konkreten Findings in dieser engen terminalen Übergangsgrenze.

Das ist portable Logik-/Lifecycleevidenz, keine native Linux-/Kernelabnahme,
keine vollständige Prozesssandbox, physische Quote, globale Kostenautorität,
C-Korpus- oder B-Freigabe. Roots erster tatsächlicher Nativeversuch hatte laut
seiner Mitteilung eine erstellte 8192-Byte-SQLite-Datei, aber keinen vollständig
zurückgegebenen Terminalfall. Sein ganzer 60-s-Charge bleibt STOP; dieser Review
refundiert ihn nicht und hat den rootprivaten Bericht nicht selbst gelesen.

## Reproduzierte Findings und eng erfolgte Korrekturen

### 1. Terminales wait4 übersprang die erklärte Pendingfrist

Im ersten Fix `8554f912…` wurde die 50-ms-Frist nur ausgewertet, solange
`completed is None` blieb. Nach einem gültigen initialen Stop-Readback, einer
Statusprobe ohne VmHWM und später demselben tatsächlich modellierten terminalen
`wait4` waren 50.000.001 ns, 100.000.000 ns und 999.999.999 ns seit Beginn der
Pendingbeobachtung jeweils noch `stop_reason=None`.

Die terminale CPU-/RSS-Messung war dabei vollständig vorhanden. Der Befund war
daher präzise eine übersprungene behauptete **Pendingfrist**, nicht eine
erfundene RSS-Unterzählung oder fehlende terminale Messung.

Root prüft jetzt beim bestätigten terminalen Return unmittelbar nochmals
CLOCK_BOOTTIME gegen **dieselbe** Pendingstartzeit
(`context_preparation_supervisor.py:425`). Nur
`0 <= terminal_gap < 50_000_000` kann sie auflösen; eine gleich große,
größere oder rückwärts laufende Spanne bleibt `rss_observation_lost`.
Die ursprüngliche Worker-Wallfrist und die bestehenden Samplegapchecks bleiben
unverändert. Der tatsächlich terminale Child bleibt dabei reaped; es wird kein
lebender Prozess zur nachträglichen Erfolgserklärung umgedeutet.

Zusätzliche unabhängige Probes verschieben die Zeit **innerhalb** des
`wait4`-Aufrufs. Ein lediglich am Loopanfang gelesenes `now` genügt ihnen
nicht: Nach anfangs nur 10 ms und weiteren 40/40,000001/200 ms innerhalb des
Waits muss der tatsächliche Terminalreadback die Grenzverletzung erkennen.
Eine rückwärts laufende Terminaluhr wird ebenfalls verworfen.

### 2. Fehlendes VmHWM verdeckte bekannte zusätzliche Threads

Im ersten Fix führten `State=R`, `Threads=2` beziehungsweise `Threads=999`
und fehlendes VmHWM zum Pendingzweig. Die vorhandene Threadanzahlprüfung lag
nur im Zweig **mit** VmHWM. Ein anschließender gültiger Terminalfall wurde
deshalb als Erfolg ausgegeben, obwohl die konkrete beobachtete Threadzahl
bereits dem Einprozess-/Einthreadprofil widersprochen hatte.

Root prüft nun bei einem nicht als Z beobachteten Zustand `Threads == "1"`
vor beiden RSS-Zweigen (`context_preparation_supervisor.py:440`). Die
bekannte Verletzung bleibt `kernel_task_count`; das fehlende RSS-Feld kann sie
nicht entfernen. Die eigene Nachprüfung enthält zusätzlich 0, mehrere Werte,
unbekannten Text und ein fehlendes Threads-Feld. Die bestehende Behandlung
eines Z-Zustands wurde durch diesen engen Fix nicht erweitert oder neu als
allgemeiner Kernelbeweis ausgegeben.

## Unabhängiges Modell und geprüfter Lifecycle

Die eigenen Probes importieren keine Owner-Testfixtures. Ihr separates
Ereignismodell besitzt eigene wait-Statuskodierung, vorab bestimmte
Stop/Live/Terminalereignisse, FDs, Streams, Clockfortschritte und Fehlerpfade.
Alle OS-/Root-/pidfd-/Fork-/Pipe-/Guardgrenzen sind ausdrücklich modelliert;
sie starten keinen Linuxprozess. Reales `lstat` wird nur für das durch pytest
neu angelegte lokale Testverzeichnis verwendet.

Geprüft sind insbesondere:

- Ein akzeptierter laufender Pendingzustand folgt einem wirklich vom Modell
  bestätigten ersten SIGSTOP-/Kernelreadback. Kein initial fehlender RSS-Wert,
  kein fremder PID und kein zweiter Stop werden damit repariert.
- Nur terminales wait4 desselben direkten Kindes mit strengem rusage kann die
  RSS-Lücke auflösen. Eine später scheinbar gesunde /proc-Probe wird gar nicht
  zum Zurücksetzen von Pending gelesen.
- Ein zuvor beobachteter höherer VmHWM bleibt im Ergebnis erhalten. RSS exakt
  1 GiB und darüber bleibt STOP; ungültige/fehltypisierte terminale CPU-/RSS-Werte
  erzeugen einen Fehler, keinen Nullwert oder geratenen Peak.
- Vorhandenes, aber kaputtes VmHWM bleibt unmittelbar ein Fehler. Ein
  FileNotFound-/Permission-/I/O-Fehler beim Lesen von /proc wird nicht zur
  erlaubten spezifischen „Feld fehlt“-Race erweitert.
- Ursprüngliche Wallfrist, rückwärts laufende Uhr, maximaler Samplegap,
  tatsächliche beobachtete freie Reserve, Outputlimit und CPUlimit bleiben
  STOP-Bedingungen. Die Race gibt keinen zusätzlichen 300-s-Workerzeitraum.
- Output bleibt ein begrenzter gehashter Kanalprefix. Beim Grenzfall werden
  höchstens 1 MiB Prefix behalten und 1 MiB + 1 Bytes als Überschreitung
  beobachtet; das übrige Log wird nicht als vollständig ausgegeben.
- Cleanup darf auch einen bereits natürlich beendeten Child antreffen.
  Eine vorher bekannte RSS-/Frist-/Threadverletzung wird durch dessen Exit 0
  nicht gelöscht. Signal- und Nichtnull-Exits behalten ihre echten Ergebnisse.
- Bei unmessbarem, fremdem oder ausbleibendem Cleanupwait bleibt
  `UnreapedChild` mit **dem ursprünglichen** PID/pidfd bestehen. Der pidfd wird
  nicht geschlossen oder durch einen neuen FD ersetzt; übrige eigene
  Descriptoren werden geschlossen. Kein Erfolg/Refund entsteht.
- Das positive Ergebnismodell prüft alle Returnfelder: Kernelreadback-PID/
  UID/GID, terminale CPU, getrenntes Parent-CPUfenster, ursprüngliche Elapsedzeit,
  RSS-Peak, beobachtete Outputbytes samt gerahmtem Hash, Prefixe, tatsächliches
  Freiplatzminimum und maximalen Samplegap.

Die neue Probe behauptet nicht, Root könne mit einer Python-Selbstmessung seine
nachfolgenden eigenen Exitkosten terminal erfassen. Die unveränderte äußere
Kosten-/Custodyzuständigkeit aus Supervisor und Diagnoseowner bleibt bestehen.

## Erhaltene RED-Evidenz und eigener Harnessfehler

| Lauf | Tatsächliches Ergebnis | Einordnung |
| --- | --- | --- |
| `task42-terminal-independent-01.xml` | 43 grün / 6 rot, 0,56 s | Fünf konkrete Produktgegenfälle; ein weiterer Fehler ausschließlich im eigenen Testmodell. |
| `task42-terminal-independent-02.xml` | 44 grün / dieselben 5 Produktfälle rot, 0,50 s | Nur der eigene Harnessfehler korrigiert; Produkt weiterhin exakt `8554f912…`. |
| `task42-terminal-independent-03.xml` | 60 grün, 0,48 s | Beide Rootfixes geprüft, zusätzliche Terminalzeit-/Thread-/Pendingprobes enthalten. |
| `task42-terminal-combined-04.xml` | 270 grün, 0 übersprungen, 3,04 s | Neue normale eigene Tests plus bestehende Owner-/Task34-Regressionen. |

Der eigene Harness hatte irrtümlich angenommen, nach jedem SIGKILL müsse
sofort der Cleanup-Wait ohne WUNTRACED erfolgen. Bei Outputüberschreitung
signalisiert der Supervisor aber bereits innerhalb des Readloops; der nächste
normale nichtblockierende Wait darf diesen Child zuerst reapen. Die Probe
akzeptiert deshalb in diesem modellierten Übergang die beiden tatsächlichen
Waitvarianten. Dieser Harnessfehler war kein Produktfinding und wurde nicht
durch eine Änderung an Produktcode behoben.

Die erste eigene Grenzhypothese ließ **exakt** 50 ms noch zu. Root entschied
explizit die strengere `>= 50 ms`-STOP-Grenze; die entsprechende eigene
Grenzprobe wurde darauf umgestellt. Keiner der ursprünglichen fünf roten
Produktfälle wurde abgeschwächt oder entfernt.

Der rote Quellstand wurde als eigene ignorierte Datei erhalten. Die exakte
Rückführung der beiden eng bezeichneten Rootdiffs reproduziert bytegenau den
zuvor gelesenen SHA `8554f912…`; nicht bloß ein ähnlicher Pseudocodefall.
Auch der unveränderte eigene Teststand von Lauf 02 ist separat erhalten.
Kein altes XML, Testartefakt oder fehlgeschlagener Arbeitsordner wurde gelöscht.

## Gefrorene Dateien und Hashes

| Datei | SHA256 |
| --- | --- |
| Finales Produkt `context_preparation_supervisor.py` | `ae9fec1f9a7798455f21f5ac4588f714bc31803602ed51128686e3f9c17ea16d` |
| Roots finale `tests/test_context_preparation_terminal_race.py` | `d34e2ff4eb65f11eb9b73a8862b7840c2492f909aa9528a9404e8e6bbaa3b810` |
| Neue normale eigene `tests/test_context_preparation_terminal_boundaries.py` | `d9a3ebc946e103c6852ed94653c6cea3112fe6c6bd795e45be85c0f6763281e8` |
| Eigene finale `.pytest_tmp/test_task42_terminal_review_csa01.py` | `c128f3a628ac8b0cea6f36138122d7e9cbbfb5c7664672e0aa10b42c7d5e9b0f` |
| Rote Produktbytes `.pytest_tmp/task42-supervisor-8554-before.py` | `8554f91216448b60c91979c0e2d1c768f5909f2277b68b5ed5d2c05d4f9ca87d` |
| Ursprüngliche eigene Probe 02 `.pytest_tmp/task42-test-original02-csa01.py` | `4c3cfd374ba7affa590e0f949444aa7190920fe371c49fbd4afaab6412b100f2` |
| RED-XML 02 | `49b2302ab7cf783270eb1bda8b040fa38e90c869e55c7e749b6966c452db7951` |
| GREEN-XML 03 | `27c3c3c79d13580fb968de1e514ab47982b83e03f49af912de703d04c7bbed35` |
| Kombiniertes GREEN-XML 04 | `2c2aeeb9fbe7b79767ce63ef00a986733bf89e7f9817419cc72b92ab14ad6ced` |

Der kombinierte tatsächliche lokale Befehl:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider tests/test_context_preparation_terminal_boundaries.py tests/test_context_preparation_terminal_race.py tests/test_context_preparation_supervisor.py .pytest_tmp/test_task34_supervisor_environment_review_ccr01.py --basetemp=.pytest_tmp/task42-terminal-combined-bt-04 --junitxml=.pytest_tmp/task42-terminal-combined-04.xml
```

Alle Basetemp-/XML-Namen waren vor dem betreffenden Lauf neu. Dieser Befehl
startet lokale portable QA; einige unverändert mitgeführte Task34-Tests nutzen
echte **Windows-Python**-Dispatcher mit modellierter Privileggrenze. Sie sind
keine Linux-Forks oder native Seccomp-Ausführung. Produkt- und vorhandene
Owner-Testhashes wurden nach dem kombinierten Lauf frisch unverändert geprüft.

Abschluss: enger Review lokal abgeschlossen. Root behält Native-Transfer,
Closure-/Helperpins, tatsächlichen erneuten Diagnoseaufruf und alle
Kosten-/STOP-Artefakte; Task35/Task38 und der noch fehlende globale C-Aufbau
bleiben davon getrennt.
