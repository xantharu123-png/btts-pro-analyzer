# Task 2 broad-regression test port

Base: `54b4a37`; production code remains `4205db8`. Scope: only
`tests/test_server_jobs.py` and this report. No updater/helper/installer changes,
VPS actions, push, broad-suite rerun, or edits to other worktrees.

## Independently observed RED

The four requested tests failed on the untouched current test file:
**4 failed, 86 deselected, 1.58 s** (`.pytest_tmp/broad-port-red.xml`).

1. The old generic backup log no longer exists: separate online/quiesced
   wrappers use one full producer. The producer performs inline restore/SQLite
   verification and the bounded pinned helper before root archive publication.
2. The updater no longer discovers companions with GNU find: its actual
   stdlib casefold enumerator supplies a checked complete inventory to DAC.
   Bootstrap still uses its existing find path and keeps that assertion.
3. Scheduled archive verification now reaches `--verify-only` through the
   fixed backup-service launcher, not directly from the migration function.
   Later assertions in this same test also described the superseded capacity
   formula/df implementation and needed the same accounting-contract port.
4. Device/free-space accounting now executes Python stat/statvfs and sums
   concurrent reservations by device, including the actual recovery mount.

No missing production functionality was found in these four reports.

## Ported contracts

- Preserve the before-downtime main/preflight call graph; execute both real
  phase wrappers and check distinct archives/work paths/source-head binding.
  Preserve inline full-archive verification before pinned restore/HMAC helper
  and publication. Execute the real launcher against actual pinned helper
  bytes and require the root backup role's exact `--verify-only --recovery-mode`.
- Execute the real Unicode/casefold inventory and DAC shell loop. Assert every
  database, companion, parent, key, marker and environment check uses exactly
  `betboy-backup -g betboy-backup -G betboy`, with write access allowed only to
  the backup destination. A writable Unicode companion must abort acceptance.
- Preserve backup-tree update verification before scheduled archive verification;
  follow the fixed stdin launcher as the backup user. Execute its real command
  selection; enforce exact pinned-helper `--verify-only`, fixed resource limits,
  and rejection of root, another UID, and a caller-supplied recovery override.
- Execute real capacity arithmetic with supplied OS device/free-space facts.
  For 1 MiB backups and 1 MiB databases, independently calculated reservations
  are 519 / 517 / 388 MiB. Test exact admission and one-byte-under failure on
  each mount, summed 1424 MiB shared-device admission/boundary failure, and a
  full recovery mount despite a roomier `/var/backups` parent.

OS UID/stat/exec boundaries and runuser are explicitly simulated in portable
unit tests; real helper bytes, Python decisions, inventories and shell loops
execute. These tests do not claim native DAC proof. Existing actual archive,
restore and HMAC tamper tests were retained and included in the targeted run.

## GREEN and test sensitivity

Four ported cases: **4 passed, 86 deselected, 2.88 s**
(`.pytest_tmp/broad-port-green03.xml`). During port development the test fixture
needed three corrections: avoid its old shell extractor stopping inside a
Python dictionary, explicitly use UTF-8 for Unicode shell output, and supply
the Git Bash command PATH. Those fixture failures were not production REDs.

Four independent, read-time-only updater mutations each produced the expected
single failing test, without modifying production bytes on disk:

- Online producer role changed to quiesced: observed phase mismatch.
- Enumerator drops casefold normalization: observed missing Unicode/companions.
- Verifier command changed away from `--verify-only`: observed wrong argv.
- Shared-device sum changed to maximum: expected rejection did not occur.

Full requested targeted command:

```text
python -B -m pytest tests/test_server_jobs.py tests/test_context_update_hook.py tests/test_context_updater_repair.py -q -p no:cacheprovider --basetemp=.pytest_tmp/broad-port-integrated --tb=short --junitxml=.pytest_tmp/broad-port-integrated.xml
```

Result: **533 passed, 8 skipped, 76.14 s** on Windows/Git Bash.

- server jobs: 83 passed / 7 unavailable-symlink skips;
- context updater hook: 340 passed;
- repair installer: 110 passed / 1 native-Linux-flock skip.

`bash -n` succeeds for updater and repair installer; `git -c core.autocrlf=false
diff --check` succeeds. Updater SHA remains
`4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`;
stagehelper SHA remains
`1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

## Remaining gates

This closes the four obsolete-test contracts locally, not the broad Linux
suite or deployment gate. Root retains the failed e2 broad-run evidence and
must obtain the desired exact-LF Linux rerun/review. Native symlink/flock/DAC,
fresh production backup acceptance, permission approval, installer execution,
frontend/model acceptance and deployment remain separate evidence/authority
boundaries; this test-only change authorizes none of them.
