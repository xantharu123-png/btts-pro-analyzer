# D4 Trusted-Updater – abgeschlossene Nachfix-Vollsuite

09.09.2026. Separater ignorierter Nachtrag; eingefrorene Quellen, Tests,
Hauptaudit und alle ursprünglichen unabhängigen Witnesses bleiben unverändert.

## Ergebnis

Der bereits vor der letzten Fortsetzungsnachricht gestartete Full26 wurde auf
ausdrückliche Controlleranweisung auslaufen gelassen, nicht neu gestartet:

- **4789 passed, 18 skipped, 97 subtests passed, 1004,62s (16:44), Exit0**.
- JUnit zählt4904 inklusive97 Untertests und18 Skips; errors=0, failures=0.
- Eigene Exec-Session54579 ist abgeschlossen. Keine weiteren Tests gestartet.

Tatsächlicher Befehl im owning Worktree:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/context-hook-fixed-full-26 --junitxml=.pytest_tmp/context-hook-fixed-full-26.xml
```

Der Lauf begann auf den noch uncommitteten, danach bytegleich eingefrorenen
Quellen. Der fertige genau dreidateilige Commit lautet
`7ba4c9746caf75e0dd6ab5881c8b7ed329a7e358`, Branch
`codex/kontext-updater-hook-20260909`, Basis
`1daf72d7b582f684006bf2898e8ae3ebd6a4ab6f`.
`git status --short` danach leer. Kein Push, Merge oder VPS-Eingriff.

## Exakte Nachweise

| Datei | SHA256 |
| --- | --- |
| `deploy/update_server.sh` | `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f` |
| `tests/test_context_update_hook.py` | `8e18e7e17622f357810a00211ce4e4bcf19944ce85777d39c3c37897f1fb860b` |
| `docs/audits/2026-09-09-d4-trusted-updater-hook.md` | `81114662615349eb03d833a61bf6f6b8db2c656936952d4bd9a704f1ed0d2b94` |
| `.pytest_tmp/context-hook-fixed-full-26.xml` | `ea9e41757d8c473ad8e83b31f474ae18ddb93bc541ca245b2860004b147ef90b` |
| `.pytest_tmp/context-hook-fixed-green-24.xml` | `b11a4eaf3c43e566c5e9e7342b3818f48102418633676373fc958bcb2593ef9a` |
| `.pytest_tmp/context-hook-fixed-regression-25.xml` | `29cff11b6aa5723ecd8c0b30da1c98b4cf790f7beaca5122406acc75aa7831e5` |
| Unverändertes `.pytest_tmp/updater-independent-20260909/REPORT.md` | `4dc77c150e82f9e76369cab76c7ec3ebd2fd44d990880aa3a9505ab32e303f80` |
| Unveränderter gepinnter `scripts/stage_runtime_databases.py` | `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` |
| Unveränderte `deploy/systemd/betboy-backup.service` | `922352a5d3c883cc671da419c5d3fa589cbe9cd025f32d4c4d9f7b6a9648edb8` |
| Unveränderter `deploy/bootstrap_server.sh` | `eb2cec227d710156f960ba78a620c5bdfe4bd97cd95ba2deb33a3c120fd5dec6` |

Vor dem Fix wurden die unveränderten Originalfälle mit12 funktionalen REDs
und6 grünen Kontrollen reproduziert. Nach Fix239 permanente+18 originale
Fälle grün; separat388 Regressionen/10 Skips/39 Untertests. Nur ein bekannter
historischer Reviewsourcepin wurde dort explizit deselected, niemals verändert.
Der erneute echte Vergleich der69 alten Bashfunktionen ist bytegleich;
`bash -n` und `git diff --check` erfolgreich.

## Skips und Grenzen

Alle18 JUnit-Skipgründe wurden direkt gelesen: fehlendes tatsächliches
Windows-Symlinkprivileg und POSIX-Owner/Mode/Umask-only-Prüfungen. Kein Skip
verbirgt einen fehlgeschlagenen Updater-Unicodefall. Ein Windowslauf und ein
Metadatenharness beweisen keine echte Linux-DAC-/runuser- oder installierte
CommitA→CommitB-Produktionskette.

Das eingefrorene Hauptaudit hält Full26 noch korrekt als „beim Dokumentfreeze
laufend“ fest. Dieser separate Nachtrag ergänzt den späteren Abschluss, ohne
die unabhängige Nachprüfung durch Audit-/Sourceänderungen zu stören.
Full20 bleibt unverändert **Vorfix**-Evidenz. Keine empirische Modellfreigabe,
kein Root-/Backup-/Key-/Marker-/Whitelistchange und kein abgeschlossener
unabhängiger Nachreview werden aus Full26 abgeleitet. Root führt den
unabhängigen Gegentest und alle etwaigen Linux-/Produktionsschritte getrennt.
