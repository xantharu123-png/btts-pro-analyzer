# Linux: Berechtigungen positiver Kontext-Testfixtures

## Auftrag und Ausgangsbeleg

Basis: `a224d136d232ecc16e7f4b0a3341518efb54906a`.
Isolierter Branch: `codex/kontext-linux-fixtures-20260909`.

Der Controller meldete einen echten unprivilegierten Linuxlauf mit normaler
`umask 0002`: **14 fehlgeschlagen, 771 bestanden, 0 Skips**. Die positiven
Testdateien beziehungsweise App-Fixture-Verzeichnisse hatten dabei `0664`
beziehungsweise `0775`; die unveränderte Vertrauensprüfung brach deshalb vor
dem jeweils beabsichtigten negativen Fall ab. Original-JUnit-SHA256:
`f820d5e996f47dd00cd4fdf8d279ce55470824a6abdb5afcb622c618ad2df004`.
Dieser Linuxbeleg stammt vom Controller, wurde hier nicht erneut ausgeführt
und bleibt unverändert erhalten.

## Exakt begrenzte Änderung

- `configuration_fixture` erzeugt `app`, `target` und `previous` über dieselbe
  bestehende Schleife jetzt ausdrücklich mit `mkdir(mode=0o700)`.
- Sechs neue `chmod(0o600)`-Aufrufe setzen ausschließlich reguläre positive
  Datei-Fixtures vor den bestehenden Hardlink-/Identitätsprüfungen: Companion
  vor Open, Sentinel für echte WAL/SHM-Hardlinks, während Connect eingeführter
  Sentinel, bestehender Companion samt Ersatzdatei und Sentinel vor Return.
- Alle Testparametrisierungen, negativen Assertions, Ausnahmen und Skips bleiben
  gleich. Keine Änderung an Prozess-umask, Runtime, Reader-Vertrauensregeln,
  Updater oder gepinntem Stagehelper. Keine zusätzliche Testfunktion geändert.

Der Controller bestätigte den tatsächlichen Umfang ausdrücklich: sechs neue
chmod-Zeilen und eine geänderte mkdir-Zeile, nicht sieben chmod-Stellen.

## Eigene Windows-Regression

Identischer Fokus vor und nach dem Patch:

`python -B -m pytest -q -p no:cacheprovider tests/test_context_update_hook.py tests/test_context_reader_trust.py --tb=short -rs`

Beide Läufe verwendeten die bestehende Quality-Umgebung und jeweils einen neuen
Basetemp-/JUnit-Pfad unter der vorher angelegten `.pytest_tmp`. PowerShell
übernahm und prüfte jeweils ausdrücklich `$LASTEXITCODE`.

- Vorher: **271 bestanden, 1 Skip**, 26,27 s, Exitcode 0.
  JUnit `.pytest_tmp/linux-fixtures-windows-before-01.xml`, SHA256
  `d8b82cac77af69d0a8a57a7e1950a605835119bc3c7fc5df55791ecd19164294`.
- Nachher: **271 bestanden, 1 Skip**, 25,96 s, Exitcode 0.
  JUnit `.pytest_tmp/linux-fixtures-windows-after-01.xml`, SHA256
  `8309f1634d7dc96beb6ffb665b19031fd536f263ec772e7a5894ec87b50afc35`.
- Der identische Skip betrifft ausschließlich die auf diesem Windows-Host
  fehlende Berechtigung für echte Symlinks (WinError 1314).
- `git diff --check` ist sauber. Keine eigene Vollsuite; kein SSH, VPS oder Push.

Die Windowsläufe sind keine Linux-DAC-Abnahme. Den echten Linux-Nachlauf auf
einer neuen privaten Sourcekopie übernimmt der Controller separat.

## Eingefrorene Testdateien

- `tests/test_context_update_hook.py`: SHA256
  `cf711ac8438eef369500014298ad6c7c14ae2c5c0ae3b6ada526d9299b70e501`.
- `tests/test_context_reader_trust.py`: SHA256
  `89e2b95d23f74fff5fd7c79d38c4f46451dbaa0a7545de4fad6ad6bf1cf8ea85`.
