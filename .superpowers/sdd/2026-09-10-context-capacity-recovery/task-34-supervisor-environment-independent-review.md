# Task 34 — unabhängiges Review der secretfreien Parent-Umgebung

Stand 2026-09-12, Prüfer `c_copy_review`. Enger finaler Supervisor-Diff nach dem NoExec-Review. Vollständiger aktueller Supervisor und sämtliche Owner-Tests gelesen. Keine Produkt-, bestehenden Test-, Git-, Server-, Host- oder Kerneländerung. Keine native Linux-/Guard-Ausführung.

## Ergebnis und Stand

**194 lokale Prüfungen bestanden, 0 Fehler, 0 übersprungen, 2,58 s**: 62 vorherige unabhängige Fälle, 12 neue Gate-/Grenzfälle und 120 Owner-Tests. Kein konkreter neuer wichtiger Produktbefund im vereinbarten Umfang. Die bestehenden Lifecycle-, pidfd-, Terminal-RSS-, Output- und NoExec-Regressionen bleiben grün.

| Geprüfte Datei / Evidenz | SHA256 |
| --- | --- |
| `context_preparation_supervisor.py` | `21c63e0cdf47000c2d3c66e24851635b844a1feb30091d55521ed6dd311f31de` |
| `tests/test_context_preparation_supervisor.py` | `6ae1351218a228dde2752374403bb26dde9b106800616638f2f97607cf1afc38` |
| `.pytest_tmp/test_task34_supervisor_environment_review_ccr01.py` | `a44c65966d164ce75e52a7bd4594532fd0e8449268a729e5125ff2b4bed43191` |
| `.pytest_tmp/task34-supervisor-environment-review-ccr01-run1.xml` | `1deaa44be8b4ae6ca67667a362c6cb6c3ac70b3b20bf00ff76b756b9dd82aef9` |

Die frühere NoExec-Probe wurde in eine neue ignorierte Task34-Datei übernommen. In bestehenden Syscall-Modellen wurden ausschließlich explizit gültige Parent-Umgebungen ergänzt. AST-Vergleich bestätigt sämtliche **67 bisherigen Assert-Knoten in 21 parametrisierten Testfunktionen unverändert**. Die 16 bereits vorhandenen privaten Dispatcher-Unterprozesse bleiben reale lokale Windows-Python-Läufe mit modellierter Linux-/Privileggrenze; keine Aussage über einen Linux-Fork oder nativen Guard.

## Neues Gate unabhängig geprüft

`_require_clean_environment()` wird vor dem Module-/Thread-/Kernel-Readback und deutlich vor FD-Allokation oder Fork aufgerufen. Es vergleicht die Python-Umgebung exakt mit PATH `/usr/bin:/bin` und LANG `C.UTF-8`. Es setzt oder löscht keine Werte und macht eine unzulässige Umgebung nicht durch nachträgliches Scrubbing zulässig.

Die unabhängigen öffentlichen Eintrittsproben verwerfen fehlende Felder, Legacy-C, die nicht exakte Locale-Schreibweise `C.utf8`, einen zusätzlichen PATH-Leereintrag sowie zusätzliche LC_CTYPE-, LC_ALL-, leere TERM- und harmlose Secret-Fixture-Felder. Jede Ablehnung erfolgt, bevor ein beobachtetes FD-/Kind-/späteres Kernel-API benutzt wird; die Eingabeumgebung bleibt unverändert. Die exakt richtige Umgebung wird unabhängig von Einfügereihenfolge ohne Mutation angenommen.

Eine weitere ausdrückliche Grenzprobe entfernt eine harmlose Fixture aus der Environment-Mapping und behält eine Referenz darauf. Das Gate passiert danach; die Referenz bleibt erhalten. Dies bestätigt die dokumentierte Nicht-Zusage: aktueller sauberer Mapping-Zustand erbringt weder vergangene Secretfreiheit noch Heap-Löschung. Der Parent muss vor jeglicher Python-Ausführung frisch und secretfrei gestartet werden. Ein key-haltender Publisher-/App-/wiederverwendeter Interpreter bleibt unzulässig.

## CPython und zusätzliche Locale-Umgebungsfelder — nur Primärquellenprüfung

Geprüft wurden die offiziellen CPython-Quellen 3.12.3 und 3.12.14; der relevante Ablauf stimmt in beiden überein. Es wurde dafür kein Linux-Interpreter gestartet und keine Host-Locale als vorhanden behauptet.

1. Die CLI-Vorkonfiguration setzt zunächst die LC_CTYPE-Locale aus der Umgebung, bevor sie über Legacy-Locale-Coercion entscheidet. Bei einer erfolgreich akzeptierten expliziten `LANG=C.UTF-8` ist die resultierende Locale nicht `C`; die Coercion wird nicht aktiviert. **Unter dieser Voraussetzung fügt dieser geprüfte Startpfad kein LC_CTYPE-Environmentfeld hinzu.** Das ist eine Ableitung aus der Quelle, kein gemessener Host-Pass. [CPython 3.12.14 preconfig.c](https://raw.githubusercontent.com/python/cpython/v3.12.14/Python/preconfig.c).

2. Bleibt die tatsächliche Locale dagegen `C`, kann CPython einen verfügbaren UTF-8-Ersatz wählen und explizit `setenv("LC_CTYPE", …)` ausführen. Die feste Zwei-Felder-Prüfung würde ein solches zusätzliches Feld korrekt ablehnen. Daher dürfen fehlende Host-Locale-Unterstützung oder ein Wrapper mit zusätzlichen Feldern nicht still durch ein erweitertes Gate kompensiert werden. [CPython 3.12.14 pylifecycle.c](https://raw.githubusercontent.com/python/cpython/v3.12.14/Python/pylifecycle.c).

3. CLI-`-I` unterdrückt Python-Umgebungsoptionen, ist aber keine generelle Zusage gegen Locale-Konfiguration oder native libc-Umgebungsnebenwirkungen. Ein davor tatsächlich leer gesetzter und nur um die zwei festen Felder ergänzter Start sowie die konkret funktionierende Host-Locale bleiben äußere Voraussetzungen. Der Prüfbericht empfiehlt keine zusätzliche Variable und keine Limit-/Profiländerung. [CPython 3.12.14 preconfig.c](https://raw.githubusercontent.com/python/cpython/v3.12.14/Python/preconfig.c).

Präzisionsgrenze: `dict(os.environ)` liest **Pythons Environment-Mapping**, nicht zwangsläufig ein frisches libc-environ. Die Mapping wird beim Import erfasst; direkte `os.putenv`-Aufrufe ändern sie nicht. Folglich ist dieses Gate eine enge Missbrauchserkennung im bereits geschlossenen Parent-Vertrag, kein natives Environment-Attestat und keine Sandbox. Dieser dokumentierte Sprach-/API-Sachverhalt ist kein neuer frei erfundener Closure-Bug. [Python 3.12: os.environ](https://docs.python.org/3.12/library/os.html#os.environ).

## Reproduktion und offene Grenzen

QA-venv Python 3.12.14, Windows, `-B`, Plugin-Autoload und Cacheprovider aus; neue zuvor nicht vorhandene Basetemp-/XML-Namen. Keine echten Secrets gelesen/gedruckt. Die neuen Environmentfälle arbeiten mit ausdrücklich modellierten Dictionaries und harmlosen Fixturetexten.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider .pytest_tmp/test_task34_supervisor_environment_review_ccr01.py tests/test_context_preparation_supervisor.py --basetemp=.pytest_tmp/task34-supervisor-environment-review-ccr01-run1 --junitxml=.pytest_tmp/task34-supervisor-environment-review-ccr01-run1.xml
```

Das ist der ausgeführte Befehl. Seine Namen sind belegt; Wiederholungen benötigen neue Namen. Vorherige Reviewartefakte bleiben unverändert erhalten.

Kein Nachweis für die reale Linux-Locale, native Dumpable-/Apport-/seccomp-Wirkung, vollständige Jobkosten/Originaldeadline, Namespace-/Import-/Input-Schließung, globale physische Quota oder B-Publikation. Der frische secretfreie Parent-Start und seine Historie bleiben äußere Verantwortung; das neue Gate löst diesen Vertrag nicht durch einen gegenwärtigen Dict-Vergleich ab. Task34 ist lokal abgeschlossen; der nächste separat beauftragte Schritt ist die unabhängige Prüfung der Task33-Probe.
