# Task 47 — Unabhängige Prüfung der Pending-RSS-Pollplanung

Stand: 2026-09-12. Enger Review abgeschlossen: der konkrete selbst verursachte 50-ms-Wartefehler ist im geprüften Root-Fix geschlossen. Kein verbleibender konkreter Befund innerhalb dieses Poll-/Exitübergangs. Das ist weder eine neue native Ausführung noch eine Freigabe für C, B, größere Korpora oder Produktion.

## Scope und Identitäten

Vollständig gelesen: `context_preparation_supervisor.py`, seine Owner-Tests, `test_context_preparation_terminal_race.py`, `test_context_preparation_terminal_boundaries.py` und der vollständige native Versuch-2-Bericht. Der Reviewer änderte ausschließlich seine neue Testdatei und diesen Bericht. Keine Produkt-, vorhandenen Test-, Git-, SSH- oder VPS-Änderungen durch ihn.

| Gegenstand | SHA-256 |
| --- | --- |
| Supervisor vor Fix | `ae9fec1f9a7798455f21f5ac4588f714bc31803602ed51128686e3f9c17ea16d` |
| Geprüfter Supervisor nach Root-Fix | `c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8` |
| Eigene erste vier RED-/GREEN-Proben | `e0d374b2e730c6274f6c44502a80481455d72d4bf5d12b01e07367201194e3f3` |
| Finale eigene `tests/test_context_preparation_pending_poll.py` | `88acba31b5bb390d1ca6a48c1047b3f60458f9ae395105eb4255bb6ab55fb3d1` |
| Supervisor-Owner-Tests | `6ae1351218a228dde2752374403bb26dde9b106800616638f2f97607cf1afc38` |
| Terminal-Race-Tests | `d34e2ff4eb65f11eb9b73a8862b7840c2492f909aa9528a9404e8e6bbaa3b810` |
| Terminal-Boundary-Tests nach Root-Anpassung der vier Poll-Timeout-Erwartungen | `a8ad7be1458c61ead3df29699b86065445fe0ec70c6b26e72389faeaa349142a` |
| `evidence/task46-native-run2.json` | `a0a60f177a0dcce6a5a0acbeaf15d24b601f148d3ec426fbb63a31554e2619c1` |

Die gesamte aktuelle Supervisor-Datei wurde zusätzlich rein im Speicher auf den vorherigen Poll-Aufruf zurückgeführt: vier neue Kommentarzeilen und die bedingte lokale Poll-Variable samt Aufruf wurden durch den früheren direkten `selector.select(POLL_SECONDS)` ersetzt. Der SHA-256 des vollständigen Ergebnisses ist exakt der obige `ae9...`-Stand. Damit ist nicht nur der betrachtete Ausschnitt, sondern die Beschränkung der Produktänderung auf diesen Pollfix geprüft. Keine alte Produktdatei wurde geschrieben.

## Konkreter Befund und Reproduktion

Der echte native Bericht liefert einen positiven Worker mit Exit 0, `child_cpu_ns=1090847000`, `peak_rss_bytes=62951424`, 400 beobachteten Outputbytes und `maximum_sample_gap_ns=52799507`; trotzdem ist der Supervisor-Stop `rss_observation_lost`. Das reservierte Diagnosebudget bleibt vollständig verrechnet. Der Bericht enthält keinen vollständigen zeitgestempelten Syscalltrace; er beweist daher für sich allein nicht die genaue Reihenfolge von EOF, fehlendem VmHWM und terminaler Verfügbarkeit.

Die unabhängige Reproduktion ruft die echte `run_single_process()`-Funktion auf, ersetzt aber alle OS-, Zeit-, Kind-, Limit-, Readback-, Mess- und Signalwirkungen durch ausdrücklich modellierte Ereignisse. `select(timeout)` verbraucht den angefragten Timeout, wenn keine Pipe bereit ist — auch nach EOF beider Pipes und bei leerem Selector. Ein wirklich bereites EOF darf sofort wecken. Die terminale Verfügbarkeit folgt der Modellzeit, nicht der Nummer des `wait4`-Aufrufs. Modelluhren laufen nicht künstlich bei jedem Lesen weiter.

Das ist die relevante Selektorsemantik: CPython 3.12.3 ruft bei `EpollSelector` auch ohne registrierte FDs `poll(timeout, max_ev)` auf und hält `max_ev` mindestens 1; positive Timeouts werden auf Millisekunden aufgerundet. [Primärquelle: CPython v3.12.3, Lib/selectors.py, EpollSelector.select](https://raw.githubusercontent.com/python/cpython/v3.12.3/Lib/selectors.py). Bereite Dateien können den Timeout abkürzen. [Python-Selektordokumentation](https://docs.python.org/3/library/selectors.html#selectors.BaseSelector.select).

Vier Originalproben kombinieren EOF vor bzw. nach Eintritt in Pending mit 0 bzw. 2.799507 ms Schedulerzugabe. Das Kind ist jeweils schon nach 1 ms terminal verfügbar. Auf `ae9...` verursacht der angefragte leere 50-ms-Select trotzdem eine erste terminale Beobachtung nach exakt 50 bzw. 52.799507 ms; alle vier Proben werden erwartungsgemäß RED. Die JUnit-Properties erhalten den tatsächlichen Produkt-SHA und die Modellereignisse. Die 2.799507-ms-Zugabe ist ein bewusst gewählter Modellparameter, kein nachträglich behaupteter nativer Schedulertrace.

Auf `c6c1...` bestehen dieselben vier unveränderten Proben. Pending verwendet nun einen angefragten 5-ms-Timeout; ohne sonstige Verzögerungen wird das verfügbare Kind nach 5 bzw. 7.799507 ms beobachtet. Der gewöhnliche gesunde 50-ms-Poll bleibt unverändert.

## Grenzen und Gegenfälle

Die auf 44 Fälle erweiterte Datei prüft zusätzlich:

- Mehrere echte, Zeit verbrauchende 5-ms-Polls bis zur terminalen Verfügbarkeit; der ursprüngliche Pending-Zeitpunkt bleibt unverändert, ein späterer scheinbar gesunder `/proc`-Read wird nicht zum Löschen der Unsicherheit verwendet.
- Sofort bzw. vor Timeout eintreffendes Pipe-EOF, sowie weiterhin volle 50-ms-Wartezeit ohne Pending.
- Erste terminale Beobachtung bei exakt 50 ms und darüber bleibt STOP. Insbesondere können terminale Verfügbarkeiten von 45.000001 bis 49.999999 ms erst beim nächsten 50-ms-Poll beobachtet werden und werden korrekt nicht akzeptiert.
- Schedulerzugaben und tatsächliche Zeit im terminalen `wait4` zählen vollständig. 49.999999 ms bleibt innerhalb, exakt 50 ms und 50.000001 ms bleiben außerhalb. Eine Messlücke oberhalb einer Sekunde wird weiterhin als `measurement_gap` gestoppt.
- Die ursprüngliche Worker-Wallfrist wird nicht durch Pending neu gestartet.
- Fehlende/abweichende Einthread-Angaben, exakte terminale 1-GiB-RSS-Grenze, fehlerhafte/typfremde terminale RSS-Werte und die unveränderte CPU-Grenze bleiben wirksam.
- Ein nicht eindeutig reapedes Kind bleibt `UnreapedChild` mit demselben ursprünglichen pidfd; sonstige eigene FDs schließen, der pidfd bleibt ausdrücklich in Custody. Kein Erfolg und kein erfundenes Terminalmaß.

Der Kombilauf enthält außerdem die vorhandenen Grenzen für Output, freien Speicher, Uhrrollback, fremde PIDs, erneuten Stop und weitere Messfehler. Deren Testdateien wurden vom Reviewer nicht verändert. Root änderte zuvor ausschließlich vier hartkodierte Poll-Timeout-Erwartungen von 50 auf 5 ms; die Fristerwartungen wurden nicht gelockert.

## Ausgeführte lokale QA

Runtime: `.pytest_tmp/qa-python312-c-01/Scripts/python.exe`; Windows, Python 3.12. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTHONDONTWRITEBYTECODE=1`, `-B -m pytest -q -p no:cacheprovider -o junit_family=xunit1`. Jeder Lauf verwendet ein eigenes zuvor nicht existierendes Basetemp und eigenes XML. Alle RED-Artefakte bleiben erhalten.

| Lauf / XML unter `.pytest_tmp/` | Ergebnis | XML-SHA-256 |
| --- | --- | --- |
| `task47-red-20260912-1.xml` | 4 erwartete Failures, 0 Errors; ursprünglicher Supervisor | `fd5f0ab9329fda4f8b15d97c46461f36339877f1193faea083ec32eab5544663` |
| `task47-original-green-20260912-1.xml` | Dieselben 4 Proben bestanden; Root-Fix | `b645fb7ade89ccf6398176423c51035aa6815535eec90a6c7629e6f89d78ba8f` |
| `task47-extended-20260912-1.xml` | 44 bestanden, 0 übersprungen | `d8c513f925790aa6514751f0c4caa1a8fe1d011945c5d9abe2deba56d3811f28` |
| `task47-combined-20260912-1.xml` | 240 bestanden, 0 übersprungen; 0.99 s CLI / 0.942 s JUnit | `e1be9d18ba4f200c951889abf3f757f1a68c517254510cbb2ac470404d6a2451` |

240 = 120 Supervisor-Owner + 16 Terminal-Race + 60 Terminal-Boundary + 44 eigene Pollproben. Finale Kombibasetemp: `.pytest_tmp/task47-combined-bt-20260912-1`.

## Begrenztes Urteil

Der Root-Fix schließt den reproduzierten selbst verursachten Pollfehler, ohne die 50-ms-Akzeptanzgrenze, die tatsächliche terminale Zeitmessung oder andere Produktchecks zu ändern. Im geprüften Umfang kein offener konkreter Produktbefund.

Nicht behauptet: garantierte Betriebssystem-Schedulinglatenz, garantierter Reap, native Wirksamkeit dieser Windowsmodelle, Behebung jeder möglichen nativen Ursache, neuer nativer Erfolg, globale Ressourcen-/Namespace-Autorität oder Gesamtfreigabe für C/B. Native Wiederholung mit exakt gepinnten Dateien und bisherigen äußeren Gates bleibt Aufgabe von Root. Eine spätere echte Überschreitung der ursprünglichen 50-ms-Frist muss weiterhin STOP bleiben.
