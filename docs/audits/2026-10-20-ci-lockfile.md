# 2026-10-20 – CI, Lockfile und pytest/ruff-Konfiguration (Audit 16.10.2026, H8)

Branch `claude/audit-repairs-20261019`, Worktree `.worktrees/claude-audit-repairs-20261019`.
Nichts davon ändert Produktionsverhalten; es sind Werkzeugdateien.

## Angelegt

| Datei | Zweck |
|---|---|
| `pyproject.toml` | `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `pythonpath = ["."]`, damit `pytest` und `python -m pytest` gleich laufen (`tests/conftest.py` importiert Root-Module). `[tool.ruff]`: Regeln `E9`, `F63`, `F7`, `F82`, Ausschlüsse `.worktrees`, `.venv`, `.portal-venv`, `.codex_test_venv`, `output`, `runtime_state`, `.pytest_tmp`, `Backup`. |
| `requirements.lock` | 60 exakte Pins: `pip freeze` der App-venv (Python 3.12.10, Windows), reduziert auf die transitive Hülle von `requirements.txt`. Entfernt nur pytest, pytest-subtests, pluggy, iniconfig, Pygments, ruff. |
| `portal/requirements.lock` | 11 Pins aus `.portal-venv` plus den gunicorn-Pin aus `portal/requirements.txt` (auf Windows nicht installierbar, deshalb dessen Abhängigkeit `packaging` ungepinnt). Getrennt, weil beide venvs bei idna, urllib3, charset-normalizer und tzdata verschiedene Versionen tragen. |
| `.github/workflows/tests.yml` | Job `quick` (Push/PR): Ubuntu, Python 3.12, `requirements.txt` + pytest + ruff, `ruff check .`, dann sieben schnelle Testdateien. Job `full` (nur `workflow_dispatch`, 150 min): `python -m pytest tests -q`. Keine Secrets, kein Deploy. |

`tests/test_betting_math*.py` aus dem Auftrag existiert nicht und wurde weggelassen.

## Befund ruff (20.10.2026)

`ruff check .` prüft 817 Dateien, Exit 0. `F821` (undefinierter Name) meldet 114 Treffer,
alle in `tests/fixtures/tennis_normal_consumers_5d5bab6.py` und
`tests/fixtures/tennis_risk_consumer_5d5bab6.py`. Das sind eingefrorene Funktionsauszüge
aus Commit `5d5bab6` ohne eigene Imports; `tests/test_tennis_shared_consumer.py` führt sie
per `exec` mit den Globals des heutigen Moduls aus. Fehlend sind dort Standardnamen
(`json`, `datetime`, `timezone`, `math`, `Path`, `Optional`, `List`, `Union`, `Mapping`)
und Modul-Globals (`TENNIS_DB`, `TENNIS_MODEL_VERSION`, `WINNER_PROBABILITY_HAIRCUT`,
`RiskAdapterResult`, `_parse_datetime`, `_clean_text` usw.). Nicht repariert (fremder,
absichtlich wörtlicher Code); stattdessen `per-file-ignores` für `tests/fixtures/*_5d5bab6.py`.
Der Rest des Repos bleibt unter `F82`.

## Lokal nutzen

```powershell
# aus dem Checkout-Root (Worktree oder Hauptcheckout)
..\..\.venv\Scripts\python.exe -m ruff check .
..\..\.venv\Scripts\python.exe -m pytest tests/test_no_vig_methods.py tests/test_ev_calculator.py -q
..\..\.venv\Scripts\pytest.exe tests/test_no_vig_methods.py -q      # geht jetzt auch ohne -m
```

Frische Umgebung aus dem Lockfile: `python -m pip install -r requirements.lock`
(Portal: eigene venv, `python -m pip install -r portal/requirements.lock`).

Lockfile neu erzeugen, wenn `requirements.txt` sich ändert:

```powershell
..\..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\..\.venv\Scripts\python.exe -m pip freeze | Select-String -NotMatch '^(pytest|pytest-subtests|pluggy|iniconfig|Pygments|ruff)=='
```

Ergebnis hinter den Kopfkommentar von `requirements.lock` setzen, Datum und Python-Version
im Kommentar anpassen. Vor dem Kürzen prüfen, dass kein entferntes Paket von einem Eintrag
in `requirements.txt` gezogen wird (`pip show <paket>` → `Required-by`).

## Bewusst nicht gemacht

- Keine breite Ruff-Regelmenge (kein `F401`, `E501`, `I`, `B` …): Ziel war ein Lint, das
  heute grün ist und Syntax-/Namensfehler fängt. Erweiterung ist ein eigener Schritt mit
  eigenem Diff.
- Kein Umbau der Tests, keine gelockerten Fixtures, keine Reparatur der beiden
  Fixture-Dateien.
- `requirements.txt` und `portal/requirements.txt` unverändert.
- CI installiert wie beauftragt aus `requirements.txt`, nicht aus dem Lockfile. Die
  Umstellung auf `requirements.lock` ist ein Folgeschritt, nachdem der erste Lauf auf Linux
  gezeigt hat, dass die Windows-Pins dort installierbar sind.
- Kein Deploy-Schritt, keine Secrets im Workflow, kein Branch-Schutz.
- Die Vollsuite ist auf Linux noch nie in dieser CI gelaufen; dort laufen die 97/98
  `fcntl`-Fälle, die auf Windows übersprungen werden. Der erste manuelle Lauf ist der Beleg,
  nicht diese Notiz.
