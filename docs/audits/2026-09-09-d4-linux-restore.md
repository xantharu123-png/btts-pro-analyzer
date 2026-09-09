# D4: tatsächlicher Linux-Gegenlauf

9. September 2026. Nur isolierte temporäre QA-Dateien auf dem BetBoy-VPS.
Kein Deployment, keine produktiven Datenbankänderungen, keine Modellaktivierung.

## Exakte Grundlage

- Geprüftes Git-Archiv: `dfcc6d357c536e4390322c1267bc26957663ddbd`.
- Archiv-SHA256: `0aa49b85d519aeb6f4dd55f18dc65c14ad8a279f211f9b8ed060c4fac1fe4b41`;
  lokal und nach SCP identisch. Keine lokalen Modell-/Kontodaten übertragen.
- Privater QA-Root `/tmp/betboy-context-qa.9xr68INa`, real aufgelöst,
  Besitzer `ubuntu`, Rechte0700; neue Unterordner vor Anlage auf Nichtexistenz
  geprüft. Vorherige QA-Nachweise blieben erhalten.
- Originalauspackung `d4-20260909`, separate korrigierte Testkopie
  `d4-green-20260909`. Beide liegen ausschließlich unter diesem QA-Root.
- Nicht-root-Ausführung als `ubuntu`, tatsächliche gewöhnliche `umask0002`.
  Python3.12.3, SQLite3.45.1, `Connection.deserialize` vorhanden, pytest9.1.1.
- Eigene bestehende QA-venv. Nur dort wurden dieselben zuvor lesend verifizierten
  Rechenpaket-Versionen wie auf dem VPS installiert: numpy2.5.1, scipy1.18.0,
  pandas3.0.5, requests2.34.2, scikit-learn1.9.0, joblib1.5.3,
  openpyxl3.1.5, xlrd2.0.2. Normale verifizierte Wheel-Downloads, keine TLS-Ausnahme.
  App-venv, Secrets, Dienste und deren Dateirechte blieben unverändert.

Die erste direkte, nicht privilegierte Abfrage der App-venv meldete
`Permission denied`; die Versionen wurden anschließend lesend mit dem bereits
vorgesehenen App-Benutzer abgefragt. Es wurden keine App-Verzeichnisrechte
gelockert und keine Tests als root oder in der App-venv ausgeführt.

## Reproduzierbare RED/GREEN-Runde

Beide Läufe verwendeten dieselben acht vollständigen Testdateien:

```text
tests/test_context_runtime_backup.py
tests/test_model_artifacts.py
tests/test_context_snapshots.py
tests/test_backup_stage.py
tests/test_backup_stage_archive.py
tests/test_backup_stage_e2e.py
tests/test_tennis_state_codec.py
tests/test_tennis_tour_state.py
```

Aufruf in der jeweiligen privaten Quellkopie:

```text
env PYTHONDONTWRITEBYTECODE=1 /tmp/betboy-context-qa.9xr68INa/venv/bin/python
  -B -m pytest -q -rs -p no:cacheprovider --basetemp=EXAKTER_NEUER_QA_ORDNER
  DIE_OBIGEN_ACHT_DATEIEN
```

- Original: `d4-tests-20260909-01`, **5 fehlgeschlagen,429 bestanden**,11.94s.
- Korrigierte Testkopie: `d4-tests-20260909-02`, **434 bestanden,0 Skips**,12.63s.
- Lokaler Gegenlauf der beiden geänderten Testdateien:
  `.pytest_tmp/d4-linux-fixture-windows-20260909-01`,142 bestanden,
  3 erwartete Windows/POSIX-Skips,7.48s.

Die fünf ursprünglichen Fehler waren gültige Ablehnungen zu offen angelegter
Testdateien: der manuell erzeugte Restorebaum, drei leere Begleitdateien und
eine gültig gemeinte Legacy-Picklefixture. Bei den drei Begleitdateien scheiterte
die erwartete Fehlermeldung bereits am früheren Berechtigungsschutz.

Nur Fixtures wurden korrigiert: beide neuen Restoreverzeichnisse explizit0700,
die neue Datei mit `O_CREAT|O_EXCL` und0600; leere Begleiter und die gültige
Legacy-Picklefixture0600. Negative Berechtigungstests und Schutzlogik bleiben
unverändert. Kein neuer Skip, keine reduzierte Assertion, kein großzügigeres
Fehlermuster und keine geänderte umask wurden benutzt.

## Exakte GREEN-Bytes

| Datei | SHA256 |
| --- | --- |
| `context_runtime.py` (unverändert) | `c470d35fd60e413c8371aa22baa9097dedc2385a5eee5644ca56e0930b6c10c2` |
| `tests/test_context_runtime_backup.py` | `71dc37951bed4e6fc576e842829f7b0af08b692243bd6c353423237c9cddef62` |
| `tests/test_tennis_state_codec.py` | `e422a1cc4dba16706c98d149a3fe1b72bf226b2d2299ffbfe27b2ed777d7d246` |
| gepinnter `scripts/stage_runtime_databases.py` (unverändert) | `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` |

Die GREEN-Hashes wurden lokal und unmittelbar vor dem Linux-Test abgeglichen.
Das Originalarchiv und die ursprünglichen RED-Dateien wurden nicht überschrieben.

## Bedeutung und offene Grenzen

Der tatsächliche Stage-/Archiv-/Restore-Test hält eine alte SQLite-Lesetransaktion
offen, während ein neuer Receipt im nichtleeren WAL liegt. Er prüft unveränderte
Hauptdateibytes, die über den unveränderten Stage-/Backupcode gesicherte neue
Receiptidentität, beide typisierten Tourzustände samt Prognosen, vollständige
Referenzen und unveränderte B3-Snapshotbytes nach Wiederherstellung.

Zusätzlich wurden tatsächliche Linux-Dateirechte, Symlinks/Hardlinks,
Multithread-/Prozess-Snapshots und atomare, nichtdestruktive Modellzeigerwechsel
geprüft. Die vorherige unabhängige D4-Quellfreigabe von3df419d bleibt auf ihren
begrenzten mechanischen Umfang beschränkt. Bericht:
`task-19`-Worktree `.pytest_tmp/review-d4-independent-20260909/rereview-d4.md`,
SHA256 `a83032678406783c9084b357b7cc708006cc415f1d7437875b12d00a6cfb4bed`.

Diese Plattformprüfung schließt nicht die noch fehlende D2-Evaluationssemantik,
den vollständigen D3-Worker-Eingabeumschlag, die produktive Backup-/Deployeinbindung
oder empirische Verletzungs-/Belastungsfreigabe. Die beiden Fixturekorrekturen
sind nun unabhängig freigegeben:150 eigene Tests grün,3 unveränderte Windows-
Skips; acht neue AST-/Dateiaufruf-/Pinned-Bytechecks. Vollständiger Bericht
byteidentisch unter `task-19-linux-fixture-review-20260909.md` im SDD-Verzeichnis,
SHA256 `e7c900b3db148b0af746bf25a08b10c2d46605633fb0f59faed944f8bfbae63f`.
Der darin genannte frühere Hash dieses Controllerberichts bezeichnet die Fassung
vor diesem reinen Nachreview-Nachtrag. Kein Public-Hash wird
als Schutz vor einer vollständig neu geschriebenen Datenbank dargestellt.
