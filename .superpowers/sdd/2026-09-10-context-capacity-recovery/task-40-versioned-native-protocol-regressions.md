# Task 40 — Task37-Regressionsfälle als normale Tests erhalten

Stand: 12. September 2026. Owner: `c_copy_review`. Enger Implementierungsauftrag
von Root: ausschließlich neue normale Testdateien und dieser Bericht.

## Ergebnis

Die 94 eigenen Task37-Regressionsfälle sind jetzt unabhängig von ignorierten
Evidenzdateien als normale pytest-Tests erhalten. Dazu kommen drei Prüfungen
der isolierten Definitionslader und neun Archivprüfungen mit den tatsächlichen
fünf gepinnten Quelldateien. **106 neue Tests**, verteilt auf genau drei Dateien:

| Neue Datei | Fälle | SHA256 |
| --- | ---: | --- |
| `tests/test_native_preparation_protocol.py` | 58 | `072428015306bd2a1ecd3a21971312d308e95a431fb1aaace7c9b4d11e2685e8` |
| `tests/test_native_preparation_sealer_protocol.py` | 32 | `ce69dd7ec8d7cd6d7f23ca2b21dae9c6f2c5e05a64934ff6992d3728b2afbfd8` |
| `tests/test_native_preparation_worker_protocol.py` | 16 | `bf71eca0a302ebbb2578ebbb32ba3278a15fdf75b407c1f9ffc9f5da5d2ab0835` |

Zusammen mit den 17 unveränderten vorhandenen Sealer-Tests:
**123 passed, 0 skipped, 1,65 s** auf dem aktuellen gemeinsamen Root-Freeze.
Keine Produkt-, Probe-, Worker-, Sealer- oder bestehenden Testbytes durch
diesen Task geändert. Kein Git-/SSH-/Upload-/Root-/Linux-Start und keine
Behauptung eines Commits. Die drei neuen Dateien liegen zur normalen
Versionierung und Suite-Integration durch Root bereit.

## Wie die Portierung den nativen Start ausschließt

Die vorherigen eigenen Probes wurden vollständig gelesen. Die neuen Tests
importieren keines der drei nativen Skripte. Stattdessen lesen sie die
aktuellen Sourcebytes relativ zu `Path(__file__).resolve().parents[1]` und
kompilieren ausschließlich AST-Definitionen und ihre benötigten Konstanten.
Top-Level-Import und CLI-Entry werden nicht ausgeführt.

Der Parent-Controlflow heißt im isolierten Modell `coordinator_flow`, der
vor Quell-I/O abgebrochene Sealer-Controlflow `sealer_flow`. Eine echte
`main`-Schnittstelle wird im Testnamensraum nicht exponiert. Beim Worker werden
nur `require`, `emit`, `denials`, `fsize` und `address_space` geladen; weder
main, positive Numerik-Imports noch libc_handle sind verfügbar.

OS, Uhr, Signale, Root-Identitäten, libc und Ressourcen sind explizite lokale
Modelle. Nicht deklarierte Imports werden abgewiesen; ctypes/resource/mmap
werden nicht mehr global in `sys.modules` überschrieben. Der Parent besitzt
keinen echten os.open/fork-Pfad. Die isolierten Namensräume sind ein
Regressionstest-Harness, keine neue produktive Python-Sandboxbehauptung.

Echte kleine FD-, Anonymous-Pipe- und SQLite-Fixtures verwenden nur neue
`tmp_path`-Dateien. Eine Pipe-Öffnung wird modelliert, ihr tatsächlicher
FD-Typ wird danach real per fstat geprüft; das ist weiterhin kein natives
Linux-FIFO-Race- oder RLIMIT-Ergebnis. Im vorhandenen unveränderten
`test_native_preparation_seal.py` bleibt der bisherige Import der
Sealer-Definitionen erhalten; dessen CLI/main wird auch dort nicht gestartet.

Keine neue Testdatei enthält einen `.pytest_tmp`-Beweisdateipfad, einen alten
Worktree-/Laufzeitpfad oder eine Auswahlvariable für historische Sourcebytes.
Der Sealer-Pfad im Gate-Modell ist rein synthetisch und leitet das Testarchiv
aus seinen Modell-Parents ab; kein alter VPS-Pfad wird gelesen.

## Erhaltene und ergänzte Regressionen

- O_NONBLOCK vor fstat bei Regular→FIFO-Austausch; realer Pipe-/fremder
  Regular-FD wird vor Inhaltlesen verworfen und geschlossen.
- Alle neun Inhalts-/Dateiidentitätsfelder, bewusste atime-Ausnahme,
  kurze Reads, Maximum+1-Überlauf, Zero-Write/fsync-Fehler und O_EXCL-
  Nichtüberschreiben mit echten kleinen Host-Dateien.
- Spät zurückkehrendes Report/stdout/Directory-Close/Seals-Close darf trotz
  vorher guter Vor-Exit-Beobachtung keinen Erfolg liefern.
- Ein einziges ganzes Ticket vor allen sechs Starts, keine Kosten-/Deadline-
  Rücksetzung zwischen Modi, gesamte beobachtete Parent-CPU plus kumulierte
  zurückgegebene Kinderkosten, Vollcharge bei unbekannten Kosten/Fehlern.
- Unklare Signal-/wait4-/ECHILD-Zustände, falsche PID oder nichtterminales
  Kind bleiben in modellierter Operator-Custody ohne pidfd-Close. Nur das
  genau terminal gereapte eigene Kind schließt die übernommene FD einmal.
- Aktuelles root0711-Outputgate, komplette durchsuchbare Vorfahren,
  Ablehnung anderer Modes und belegter Outputnamen vor Bericht oder Start.
- Dumpable0-SET/GET und terminaler GET, feste argv/Identitäten/Limits,
  strikte Resultat-/JSON-Grenzen, unterschiedliche CPU-/Output-Stopsemantiken.
- Worker-EPERM-Protokoll, ausschließlich ungültige Exec-Nullargumente,
  virtuelles mmap ohne Touch, FSIZE-Fehlerpfad, exakte begrenzte Kontrollbytes
  und kleine reale SQLite-Datei mit absolutem Namen sowie Close/reopen.
- Zusätzlicher vollständiger Archivabgleich mit tatsächlichen aktuellen
  Helper-/Parent-/Workerbytes. Fehlende, zusätzliche, doppelte, traversal-,
  symlink-, hardlink-, FIFO- und inhaltlich veränderte Mitglieder scheitern,
  ohne Extraktion oder Sourceimport.

Eine zusätzliche lesende AST-Differentialprüfung gegen die ursprünglichen
eigenen Task37-Probes fand **alle 36 bisherigen Testfunktionen und sämtliche
101 Assert-Ausdrücke unverändert**: Parent17/58, Sealer10/20, Worker9/23
(Funktionen/Asserts). Nur der Modellaufruf `model.main()` wurde für diesen
Vergleich zu `model.run_protocol()` normalisiert. Geänderte Lader/Fixtures
ersetzen globale Imports durch lokale Modelle; keine alte Sachassertion
wurde entfernt oder abgeschwächt. Die alten Evidenzdateien bleiben unverändert.

## Tatsächlich ausgeführte Läufe

Windows, vorhandene QA-Python3.12.14-Laufzeit, `-B`,
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 und `-p no:cacheprovider`. Jede Basetemp- und
XML-Adresse war neu; keine früheren Artefakte überschrieben.

| Lauf | Ergebnis | XML und SHA256 |
| --- | --- | --- |
| Neue drei Dateien | 106 passed / 1,60 s | `.pytest_tmp/task40-protocol-ccr01-run1.xml` — `dfc66d16545fb2b654d6cc4f54252922902749a3202e6794eafadc92402b0a65` |
| Anderes cwd `C:/Projekt/BetBoy`, plus bestehende Sealer-Tests | 123 passed / 1,82 s | `.pytest_tmp/task40-protocol-ccr01-cwd.xml` — `cf7b5572321d587460f1ce423425d81117bc9b7b21f66678f6e236b2c7497510` |
| Schlusslauf nach gemeinsamem Root-Pin-Fix | 123 passed / 1,65 s | `.pytest_tmp/task40-protocol-ccr01-final.xml` — `adb3813906aea53abf621611bee06c72d581cd4093052c0398eb9a92b8be3f2f` |

Ausgeführter Schlussbefehl als Beleg; bei Wiederholung neue Basetemp/XML wählen:

```powershell
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider tests/test_native_preparation_protocol.py tests/test_native_preparation_sealer_protocol.py tests/test_native_preparation_worker_protocol.py tests/test_native_preparation_seal.py --basetemp=.pytest_tmp/task40-protocol-ccr01-final-base --junitxml=.pytest_tmp/task40-protocol-ccr01-final.xml
```

Die ersten beiden Läufe prüften den damals noch tatsächlichen Supervisorpin
21c63e0c…, Parent3abe69fc… und Sealer10fbfee4…; sie werden nicht als Ergebnis
der späteren Root-Änderung umetikettiert. Der Schlusslauf bindet:

| Aktueller Source | SHA256 |
| --- | --- |
| `context_preparation_supervisor.py` | `8554f91216448b60c91979c0e2d1c768f5909f2277b68b5ed5d2c05d4f9ca87d` |
| `tests/native_preparation_probe.py` | `8192c45575af5cbcc5d6c9443376035ecee1abb04f35a31a57f1e008dba2df8e` |
| `tests/native_preparation_seal.py` | `50b41cb0104a06f3cb57c58793ef30d75a2236cde48d618b78652cb52494c2b0` |
| `tests/native_preparation_worker.py` | `22cfd8f16f8c047f298206e2f249d53fc3ef420dfbfff36f35a68c44ecc27d0e` |
| Vorhandene `tests/test_native_preparation_seal.py` | `8152134340f9f46b69a6e37a28d5351f3f64ca536ee52b5e3324760716160f7d` |

Eine bytegenaue Normalisierung ausschließlich des einen neuen Supervisorpins
ergibt bei Parent und Sealer wieder exakt die vorherigen SHA256. Der von Root
gemeldete reine Pin-Diff ist damit unabhängig geprüft. Die neuen Tests
hardcodieren diese Produkt-SHAs nicht, sondern vergleichen tatsächliche
Sourcebytes mit den jeweils aktuellen Codepins.

## Klare Abgrenzung

Root führte parallel einen getrennten nativen Diagnoseversuch aus und meldete
einen RSS-Terminalübergangsfehler mit erhaltenem vollständigem Charge. Diese
Hostausführung stammt nicht aus Task40. Die enge Supervisor-Korrektur und
ihre unabhängige native/inhaltliche Prüfung gehören Root bzw. Task42; unsere
Portierung beansprucht dafür keinen Linux-Pass.

Grüne Protokollmodelle sind weder ein sechsfacher nativer Diagnosedurchlauf
noch eine C-/B-/Quota-/Produktfreigabe. Worker-/Root-Isolation, echter Peak,
Kosten-/Exitmessung, äußere Deadline/Custody und globale physische Grenzen
werden durch die bloße normale Versionierung der Tests nicht neu bewiesen.
