# Task 29 — vollständige lokale C-Vorstufenregression

Stand: 12. September 2026. Tatsächlich abgeschlossener Prozess, nicht aus
Fortschrittspunkten hochgerechnet: **8114 bestanden, 31 übersprungen,
97 Untertests bestanden, eine Warnung, 2052,78 Sekunden** (34:12).

JUnit: `.pytest_tmp/task29-full-suite-01.xml`, SHA-256
`f49d97c48366439f90f6e4b53b0c57efcb88b7763f58b9aae4a1de1c552e5d11`.

## Exakter Umfang

Der gesamte vorhandene `tests`-Baum wurde gesammelt, außer den drei damals
noch in Entwicklung befindlichen neuen Modulen:

- `tests/test_context_storage_sqlite_profile.py`
- `tests/test_context_preparation_process_guard.py`
- `tests/test_context_preparation_supervisor.py`

Die C-Vorstufe aus c5912a7 plus neue Referenzchunks, Vorbereitungskostenbuch,
globale Workspace-Buchhaltung und Snapshot-Chunkintegration war eingefroren.
Diese Bytes wurden während/nach dem Lauf erneut bestätigt:

| Produktdatei | SHA-256 |
| --- | --- |
| `context_storage_v2/snapshots.py` | `f5dc0903874bede9fbbe3196146ba0b4b000d6a962916afd1d24efdb625f14ba` |
| `context_storage_v2/ref_chunks.py` | `49c41fac294bb6255e083cb07afad592a1460c84215dfa98842e233d8ef6d63d` |
| `context_storage_v2/workspace_budget.py` | `b848a43d4d76bb30c0510909870046195d08b86b15a6b2d6b2d8d37aad353580` |
| `context_preparation_budget.py` | `fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478` |

Neue native Probe-/Workerdateien werden nicht von diesem Lauf abgedeckt.
Auch die nach Abschluss begonnene Writerprofil-Integration in History/Tennis
braucht neue gezielte sowie abschließende Gesamtregression. Dieser Bericht ist
kein Vollsuite-Pass für zukünftig veränderte Bytes.

## Tatsächliche Ausführung

Frische isolierte lokale QA-venv aus Task25; vorhandene Projektabhängigkeiten
über deren eigene feste `.pth` erreichbar, auch für wirkliche `-I`-Unterprozesse.
Keine Produkt-/Testanpassung zur Umgehung der ursprünglichen sechs SciPy-Fehler.
Jeder temporäre Pfad war vor diesem Start neu; nichts gelöscht/überschrieben.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& .pytest_tmp/qa-python312-c-01/Scripts/python.exe -B -m pytest tests -q --tb=short --ignore=tests/test_context_storage_sqlite_profile.py --ignore=tests/test_context_preparation_process_guard.py --ignore=tests/test_context_preparation_supervisor.py --basetemp=.pytest_tmp/task29-full-suite-01 --junitxml=.pytest_tmp/task29-full-suite-01.xml
```

Einzige Warnung: bestehendes `record_property` im Snapshot-Quelladaptertest ist
mit pytest-JUnit-Familie xunit2 nicht kompatibel. Kein Testfehler; Warnung nicht
unterdrückt. Der erste rote Gesamtlauf aus Task25 bleibt unveränderte Evidenz.

## Grenze / nächster Schritt

Lokale Windows-Regressionsabnahme der benannten Vorstufe, kein Linux-Guard-,
Ressourcen-, kompletter Wachstums-, B-Nachweis-, Wiederherstellungs- oder
Deployment-Pass. Keine produktive Aufrufroute, Modell-/Quotenänderung, kein
main-Push oder VPS-Pull daraus abgeleitet.
