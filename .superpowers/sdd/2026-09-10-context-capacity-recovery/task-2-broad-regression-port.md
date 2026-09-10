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

This closes the four obsolete-test contracts locally, not the broad exact-LF Windows
suite or deployment gate. Root retains the failed e2 broad-run evidence and
must obtain the desired exact-LF Windows rerun/review. Separate Linux QA is
bounded native testing, not a Linux full-suite result. Native symlink/flock/DAC,
fresh production backup acceptance, permission approval, installer execution,
frontend/model acceptance and deployment remain separate evidence/authority
boundaries; this test-only change authorizes none of them.

## Independent review follow-up: producer failure completion

The reviewer found one P2 coverage gap in the first port: replacing the full
backup helper's `CONTEXT_COMMAND_STATUS == 0` guard with `[[ true ]]` still let
the before-downtime test pass. Independently reproduced against e74b51a:
**1 passed, 89 deselected, 1.48 s** with this read-time-only mutation. This was
a test omission, not a production defect.

Only that test now additionally executes the original producer's closing shell
segment, from `verify_backup_archive` through publication and its final log.
The external inline verifier and bounded helper are controlled process-result
boundaries. The exact publication heredoc remains unchanged but a Bash function
named `/usr/bin/python3` consumes it and records invocation: no root Python or
archive mutation is executed on the developer machine.

- Helper status 0 must reach publication, verified logging and continuation.
- Helper status 1 (verification failure) and 137 (aborted helper) must stop with
  the real restore/authentication error, without publication, success log or
  continuation.
- The identical guard-bypass mutation now produces genuine RED:
  **1 failed, 89 deselected, 1.66 s**. Its observed output wrongly contained
  `publication-boundary`, `verified` and `continued` with exit 0. The test
  rejected that result. No updater bytes were modified for the mutation.

Original production source GREEN: complete `tests/test_server_jobs.py`,
**83 passed, 7 unavailable-symlink skips, 14.13 s**
(`.pytest_tmp/broad-port-review-green.xml`). AST syntax and
`git -c core.autocrlf=false diff --check` pass. Updater SHA remains
`4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`.
The earlier three-file results remain evidence for the initial port; this
follow-up did not rerun the broad suite or claim new native/HMAC acceptance.

### Final inline-failure control and fresh trio

The same actual closing segment also now runs with inline-verifier status 1:
only `inline-boundary` may be observed, with nonzero exit; the helper,
publication, success log and continuation must all remain unreachable.

Fresh read-time mutations against this final test both give RED:

- Bypassed helper-status guard: 1 failed / 89 deselected / 1.62 s.
- Inline verifier call changed to `... || true`: 1 failed / 89 deselected /
  0.78 s. The observed mutant incorrectly ran the helper and published before
  continuing with exit 0; the actual test rejected this behavior.

Final original-source targeted trio:
**533 passed, 8 platform skips, 80.82 s**
(`.pytest_tmp/broad-port-review-final-green.xml`). Counts remain server jobs
83/7, context hook 340/0, updater repair 110/1. Both shell syntax checks and
the scoped diff check pass. The production updater was not edited; native
acceptance and the root-controlled exact-LF broad Windows suite remain
separate. The independent reviewer has also inspected the new closing segment
read-only and is binding their final verdict to the forthcoming exact commit.
