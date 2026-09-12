# Task25 — lokale Gesamtsuite und isolierte Python-Unterprozesse

12.September2026. Keine Produktkorrektur, kein VPS-Eingriff, keine abgesenkte
Testanforderung. Die bisherige Umgebung reicht für den pytest-Hauptprozess,
aber nicht für echte mit `-I` gestartete Unterprozesse.

## Erster vollständiger Lauf: kein PASS

Ausgangsbausteine c5912a7; diese alten Runtime-Dateien blieben während des Laufs
unverändert. Neue getrennte Task21/23/24-Module wurden nicht von dessen bereits
abgeschlossener Test-Collection aufgenommen. Ergebnis:

- 7897 bestanden, **6 fehlgeschlagen**, 30 übersprungen, 97 Untertests bestanden;
- 2103,71 Sekunden, eine bekannte record_property/xunit2-Warnung;
- JUnit `.pytest_tmp/task19-full-suite-01.xml`, SHA256
  `76cd619529924277c18d73d3786ca26bb5f22ec8f43dc86a223f706b8fe1fe88`.

Alle sechs Fehler liegen in `tests/test_context_update_hook.py`. Echte isolierte
CLI-Unterprozesse lieferten ModuleNotFoundError statt des erwarteten vollständigen
Reports; die gesonderte Dependencyprobe benennt ausdrücklich fehlendes `scipy`.
Auch ein vom Hauptprozess erwarteter absichtlicher Linux-Capabilityfehler konnte
dadurch gar nicht erreicht werden. Die Folgefehler `unknown context report shape`
und fehlende `limitations` sind nicht als unabhängige Produktbefunde gezählt.

Reproduktion mit demselben gebündelten Interpreter und vorhandenem PYTHONPATH:
`find_spec('scipy')` im normalen Prozess True, mit `-I` False. Der Paketbestand
unter `betboy-app/.venv/Lib/site-packages` wurde nicht verändert/installiert.

## Getrennte lokale QA-Umgebung

Neue, vorher nicht vorhandene Umgebung:
`.pytest_tmp/qa-python312-c-01`, erzeugt durch den gebündelten Python3.12.14
mit `-m venv --without-pip`. Genau eine neue QA-eigene `.pth`-Datei verweist auf
den bereits vorhandenen Projektpaketbestand. Keine globale Python-/venv-Änderung,
keine Paketinstallation, kein Netzwerkdownload und kein Produktions-Interpreter.

Echter isolierter Import in dieser QA-Umgebung: Python3.12.14, scipy1.18.0,
numpy2.5.2, pytest9.1.1. Das ist keine Gleichheitsbehauptung mit der VPS-Runtime.
Insbesondere B verlangt weiterhin deren eigene vollständige versiegelte Closure.

Alle bestehenden Hooktests unverändert erneut ausgeführt:

```
.pytest_tmp/qa-python312-c-01/Scripts/python.exe -B -m pytest tests/test_context_update_hook.py -q --tb=short --basetemp=.pytest_tmp/task25-hooks-01 --junitxml=.pytest_tmp/task25-hooks-01.xml
```

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1; Ergebnis **340 bestanden in42,10s**.
JUnit SHA256 `c369ca9ab5c1a139d80a630681f6362080f422b427d01ff2aa2544924671b41e`.
Die sechs Fehler sind damit im zuständigen gesamten Testmodul ohne Produkt-
oder Teständerung geschlossen. Die erste Vollsuite bleibt dokumentiert rot;
gezieltes Grün ist kein neuer vollständiger Suite-PASS. Nach den nun gesonderten
Chunk-/Budgetänderungen ist eine neue exakte Vollsuite erforderlich.

Fortsetzungen verwenden diese QA-Python-Exe auch für neue Vollsuite-Subprozesse,
jeweils neue noch nicht vorhandene Basetemp-/JUnit-Ziele. Keine alten Ergebnisse
oder Testverzeichnisse überschreiben. Dies ist lokale Entwicklung/Regression,
kein gestarteter nativer C-1800CPU-/3600Gesamtsekunden-Corpusauftrag.
