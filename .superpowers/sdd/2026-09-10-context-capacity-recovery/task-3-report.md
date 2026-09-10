# Task 3 implementation: review checkpoint, not deployment approval

10 September 2026. Base `9e97f2bda1bedbd7e61aeeddfc9b25b6a9992b40` on
`codex/context-capacity-recovery-20260910`. The earlier RED slice is committed
as `a435c653`. This implementer changed only the installer, its test file,
`deploy/README.md` and this report. Controller/reviewer progress and other WIP
were preserved and excluded from staging. No VPS, push, application deployment,
service operation or installed-helper change was performed.

## Implemented boundary

- Exact public arguments: reviewed 40-lowercase-hex target commit and
  64-lowercase-hex new updater SHA256. No path/remote/command/test override.
- Root-owned private installer invocation, the existing deploy lock, sanitized
  Git access to the hardcoded HTTPS repository, exact fetched main tip and
  exact updater blob, plus Bash syntax validation. Installed old updater SHA,
  source HEAD and complete marker must match the accepted production contract.
- The installed marker helper remains pinned. Production key, marker, config,
  application principal and old updater byte/inode metadata are recorded and
  rechecked across the online preflight and immediately before installation.
- The full fresh online backup uses the unchanged Task2 producer, independent
  root-owned copy, inline isolated SQLite restore and pinned helper's actual
  isolated restore/Challenge HMAC verification. No scheduled archive is
  relabeled, and no key/marker/permission/legacy fallback is created.
- Target payload/manifests and context transport use the existing audited
  source, configuration, receipt and sealed-file checks. D4 runs only as the
  actual `betboy` user. Existing limitation/report semantics remain unchanged.
- A new fixed stdlib-only root measurement supervisor launches only the
  existing fixed betboy D4 child. It records Linux wait4 descendant rusage,
  elapsed wall time and full bounded report bytes. The measured record binds
  target commit, new updater digest, sealed DB digest and exact report digest.
  Peak RSS must be strictly below 1 GiB; CPU and wall strictly below 300 seconds.
  Existing child AS2GiB/CPU300/output1MiB/hard-wall600 plus10-second grace stay
  fixed. This supervisor is not a general command runner.
- Accepted archive/stage/report/production/restore/inline/measurement hashes
  are persisted and copied into the durable transaction journal. The complete
  report and sealed snapshot/source bindings are rechecked before acceptance.
- Old executable bytes are independently copied/fsynced root-private. New
  bytes are prepared beside the installed target, intent is durably journaled,
  then exact identity is rechecked, replacement is atomic and parent-fsynced.
- Operational failures restore only the recognized own replacement. A new
  process recovers solely from strict disk journal/old-copy evidence. Unknown
  hashes, foreign same-hash inodes, malformed journals or a different release
  request are not overwritten. Completed matching requests are idempotent.
- The repair state directory's parent entry is fsynced even when the directory
  already existed; the rollback temporary entry is parent-fsynced before its
  exchange. No cleanup deletes preserved failed-recovery evidence.

Only `/usr/local/sbin/betboy-update` is the permanent executable installation
target. Backups and root-private repair records are intentionally retained.
The existing application's checkout, data, helper pins, units, keys, marker,
timer policy and running state are never changed by this installer.

## Reviewed reuse decision

Controller explicitly approved mechanical implementation-time duplication,
not runtime extraction/sourcing. Seventeen needed functions are byte-identical
to the independently accepted `6ba2c68` updater source, SHA256
`4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`:

`acquire_deploy_lock`, `as_betboy`, `root_git`, `git_betboy`, `trusted_file`,
`target_payload_file`, `verify_root_owned_file`, `parse_marker_state`,
`create_trusted_manifests`, `context_hook_data`, `context_hook_command`,
`verification_launcher_source`, `configure_context_phase`,
`prepare_verification_launcher`, `verify_backup_archive`,
`capture_root_verifier`, `produce_update_backup`.

An exact-source parity test guards this deliberate duplication. No updater
main, app deployment, backup-service migration, unit installation or unrelated
rollback function was copied. The unused ordinary D4 orchestration function
was removed from the copied set once the measured repair-specific path existed.

## RED and fresh local verification

Initial RED: 35 explicit missing-installer failures, documented in the earlier
RED slice. Added measurement RED: **14 failures**, missing fixed measurement
function, before implementation. Added state-directory parent-entry RED:
**1 failure**, observing missing parent fsync for an existing state directory,
then fixed without changing byte/inode/identity contracts.

Final command:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest tests/test_context_updater_repair.py tests/test_context_update_hook.py -q -p no:cacheprovider --basetemp=.pytest_tmp/updater-repair-integrated-02 --junitxml=.pytest_tmp/updater-repair-integrated-02.xml --tb=short
```

Result: **409 passed, 1 skipped in 58.42s**, exit0. This comprises 69 Task3
passes, one Windows-only real-flock skip, and the unchanged 340 Task2 tests.
All embedded Python programs compile; actual Bash `-n` succeeds; scoped diff
whitespace validation succeeds. Installer raw LF SHA256:
`8476a5a9a4956245ddb4026f5aff9bb1c8db980859d34fc129a28d453bf415f7`.

Tests exercise real filesystem bytes/inodes/links, restart namespaces,
replacement and fsync failures (including every fsync in the successful path),
same-hash foreign inodes, corrupt recovery files, missing/wrong evidence,
request parsing, actual Bash main/gate ordering and exact fetch commit/blob
failures. Linux flock uses a real contending lock; only its separate root-DAC
precheck is simulated. Windows lacks flock and explicitly skips that case.

Unit principal/mode emulation is now transparent on both Windows and non-root
Linux, with only Windows directory-fsync and fd-ctime limitations separately
emulated. No test/app import runs as root. These tests do not relabel mocked
principals as actual Linux DAC or power-loss durability evidence.

## Open independent review and native gates

This is a review checkpoint, NOT production or release approval. The new
measurement supervisor and installer-specific full transaction still require
independent review and native role/process/rusage/crash testing. Local boundary
and composition tests are not a fresh real backup/restore/HMAC/D4 run.

Controller's newly attempted real producer correctly refused twelve existing
0775 source directories. The separate read-only investigation established an
additional effective backup-service writer through its supplementary group;
there is no safe permission-check relaxation. Task2 source remains unchanged.
Any narrowly approved 0775-to0755 controller preparation is outside this
installer and requires its own metadata backup/recovery and fresh full backup
rerun. No such preparation is claimed or performed here.

Fresh real backup/restore/HMAC, measured target D4, native Task3 resource and
transaction proof, independent release review and explicit controller rollout
remain open. The user already approved the updater-only replacement, but that
authorization is not substituted for these safety/evidence gates. The ordinary
application deployment remains a separate subsequent command.

Process used: TDD and verification-before-completion inside the controller's
subagent-driven plan. The controller owns independent review and deployment.

## Independent-review corrections (10 September, base 347c253)

Read the complete independent review and unchanged ignored reproduction
harness. All three reported problems reproduced locally before edits: the
legitimate app-owned live parent was rejected; a real WAL source admitted
67,117,056 bytes against a 100,782,080-byte SQLite snapshot; restart after
rollback rename recorded `rolled_back` without an installed-parent fsync.
Controller additionally reported actual Linux inode reuse defeating the
original six-field OLD identity comparison. No Linux failure was skipped or
masked by selecting a different inode.

New RED slice: **15 failed, 67 passed, 1 Windows-flock skip in 4.92s**.
This includes missing narrowly scoped live-path and copied-inventory seams,
two directly reproduced missing recovery barriers, and a deterministic
same-inode/different-time signature test. Fixes:

- Only `/opt/betboy` and `/opt/betboy/app` accept the existing betboy UID and
  primary GID, with no group/world write. The parent may alternatively be
  root:root. `/opt` and every private/auth/stage domain remain strictly root
  owned. Both live-directory identities are checked twice and included in the
  persistent production continuity comparison. Foreign UID/GID, writable
  parent/app, symlink, app-owned `/opt` and identity replacement are rejected.
- An eighteenth function, `enumerate_backup_sources`, is copied byte-for-byte
  from the unchanged accepted Task2 source. Its complete DB+WAL/SHM/journal,
  Unicode-casefold and fail-closed walk contract supplies rounded-up KiB to
  the existing archive/reservation formula. No CPU/AS/wall/output budgets change;
  only omitted source bytes are now counted, with at most 1023-byte upward
  inventory rounding. Actual Bash preparation tests show a failed partial
  inventory cannot reach capacity admission or fetch. Real SQLite WAL/backup
  tests verify capacity and combined-mount insufficient-space rejection.
- An untouched OLD executable must match all nine journaled signature fields,
  not only inode/principal fields. The separately journaled own rollback inode
  retains its rename-specific rule. Same inode with changed time is rejected
  without changing either bytes or journal.
- Every recovery path fsyncs the installed parent before signing `rolled_back`,
  including an already-old own rollback inode. Tests interrupt both immediately
  after rollback rename and after its fsync; on a fresh run a failed parent
  barrier preserves `replacing`, while a successful barrier permits completion.

The unchanged Task2 updater SHA remains
`4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`.
All eighteen copied functions are covered by exact-source parity. Unit tests
continue using transparent principal/DAC emulation; actual byte, inode, link,
timestamp and file I/O behavior is retained. No root app/test imports, VPS
actions, permission changes, pushes or edits to the reviewer's report occurred.

Fresh verification and immutable checkpoint details follow below. This remains
a review checkpoint, not deployment approval; controller native Linux rerun,
fresh full production backup/restore/HMAC and measured target D4 remain gates.

Final frozen-source command:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest tests/test_context_updater_repair.py tests/test_context_update_hook.py -q -p no:cacheprovider --basetemp=.pytest_tmp/repair-review-final --junitxml=.pytest_tmp/repair-review-final.xml --tb=short
```

Result: **430 passed, 1 skipped in 56.12s**, exit0: 90 Task3 passes, one
Windows-only real-flock skip, unchanged 340 Task2 passes. Bash `-n` and
`git -c core.autocrlf=false diff --check` also pass. Installer exact LF SHA256:
`eb2b1843a58c7b66171feaa832d9425429d6637cf9249992ab986cc4767bcf63`.
The reviewer report and ignored independent repro remained untouched and
excluded from the scoped installer/tests/README/implementation-report commit.

## Standalone guard import correction (base 27ceb8b)

Independent re-review found a P1 missed by the earlier AST branch tests: the
standalone `repair_guard` program used `re.fullmatch` but did not import `re`.
The 430-test result above therefore did not establish standalone guard
execution. The unchanged reviewer reproduction produced the exact
`NameError: name 're' is not defined` before capacity admission/fetch.

A new test executes the entire unmodified guard program with no injected
algorithm globals. Only process arguments, OS/principal/platform facilities
and paths are safely isolated; directory metadata comes from real temporary
directories with transparent unit UID emulation. Four cases (valid inventory,
zero, partial text, trailing newline) first failed with the missing-import
NameError. The sole production change adds `import re` to that guard.

After that fix, a Windows test-path adapter initially failed to redirect
`/var/tmp`; this was corrected in the test, not production. The intermediate
full run (433 passed, 1 failed, 1 skip) had loaded that old adapter and is not
final evidence. The corrected full-program cases passed 4/4 without supplying
`re` or any other missing algorithm import to the executed namespace.

Task2/helper bytes and reviewer artifacts remain unchanged. No VPS, push or
production action occurred. Final rerun command uses the same two test files
and flags, with `--basetemp=.pytest_tmp/repair-import-final` and
`--junitxml=.pytest_tmp/repair-import-final.xml`. Installer LF SHA256 is
`953e507bcc84760a5deb2028f668cf889bf90f9ca53cb06b2e5edfeb2711b176`.

Final fresh result: **434 passed, 1 skipped in 57.56s**, exit0 (94 Task3
passes plus unchanged 340 Task2 passes; only the existing Windows real-flock
skip). Bash `-n` and scoped `diff --check` pass. This corrects the standalone
import gap but remains a review checkpoint with native/production gates open.

## Historical complete marker correction (base e2ae3f6)

Controller's actual live continuity run found another integration error:
the installer incorrectly required the completed migration's target commit
to equal the currently deployed application commit. Reading the pinned
helper confirmed that both `prepare_marker` and `complete_marker` deliberately
return an existing complete marker unchanged. Ordinary application updates
therefore do not advance this historical migration target. Earlier statements
in this report that implied equality of these identities were incorrect.

This exact one-time repair now binds three independent facts:

- App HEAD remains exactly `2dd1116b68f3d94e9c24338c6c9dff9b01799221`.
- Historical complete marker target is exactly
  `e0240ef8e69549f0d904602909a4eb66accc4a98`.
- Marker bytes must match SHA256
  `0768f7ca1ca4570827d4a9fafad0edf6b56959ca6f1be5843cbfa2d5e5fcb14d`.

The guard still requires complete status, exact application root, safe
principals and unchanged file/stat/hash continuity. The shell production
composition independently checks the pinned historical target, then calls
the full guard. There is no generic complete-only fallback, marker rewrite,
new migration, changed key, application operation or changed helper.

RED evidence: the actual shell production-verifier composition, including its
real marker-state parser, rejected the legitimate historical complete target
(1 failed, 3 negative controls passed). The full guard using the ignored exact
real marker bytes also rejected it with `incomplete or mismatched production
marker` before the fix. Afterwards the full guard accepted these exact marker
bytes and successfully rechecked its persisted continuity evidence twice.
That local full-program test retains only the explicit OLD executable fixture
pin and unit OS/DAC isolation; marker digest and algorithms remain real.
The controller's unchanged actual-VPS principal/executable run remains separate.

Permanent whole-guard tests use a synthetic complete marker. Per controller
direction, their AST changes only `EXPECTED_MARKER_SHA` to that synthetic
fixture's digest plus the existing OLD executable fixture pin; no imports,
functions, hash algorithms or control flow are substituted. A separate test
asserts the unchanged production SHA/target/AppHEAD literals. Negative tests
keep the synthetic expected hash fixed while mutating status, target, root or
bytes, and verify a changed marker cannot overwrite existing continuity proof.
Wrong App HEAD remains rejected. The actual shell composition additionally
rejects in-progress markers and foreign marker/app commits.

The real 72-ledger fixture remains strictly ignored: it is not committed,
embedded in tests or added to any QA archive. Only its digest is published.
Task2's updater SHA remains `4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`.
Installer LF SHA256 is `8331d9afa47149f888af6959d40f6b40134293c5a38ae05dc416a9f048ec4592`.

Final frozen-source verification: **446 passed, 1 skipped in 62.62s**, exit0
(106 Task3 passes plus unchanged 340 Task2 passes; existing Windows flock
skip only). Command used both `tests/test_context_updater_repair.py` and
`tests/test_context_update_hook.py`, `-q -p no:cacheprovider --tb=short`,
`--basetemp=.pytest_tmp/repair-marker-final` and
`--junitxml=.pytest_tmp/repair-marker-final.xml`. Bash `-n` and
`git -c core.autocrlf=false diff --check` pass. No push/VPS/helper/Task2 edit.
All reviewer/controller artifacts remain outside this three-file commit.
