# Task 3 native evidence — release still HOLD

10 September 2026. Controller evidence, not a statement that the five-sport
model/source plan is complete. No production updater/application/permission,
key, marker, database or service change has occurred in these checks.

## Freeze and independent review

- Initial installer `ce1021ee` was rejected by independent review for the live
  app-owned parent assumption, incomplete WAL/SHM capacity accounting, and a
  missing installed-parent fsync on repeated rollback recovery.
- Exact native ordinary-user tests of that freeze found a fourth real failure:
  `test_recovery_rejects_external_same_hash_different_inode[OLD]` did not raise.
  Result: **409 passed, 1 failed in39.31s**, QA directory
  `/tmp/betboy-context-qa.9xr68INa/task3-hooks-ce1021e-2fu6lnq6`.
- `27ceb8bd` corrected the four cases but introduced a missing `re` import in
  the standalone guard. Independent whole-program reproduction rejected it
  despite430 passing fragment/unit tests. It was never installed.
- `e2ae3f69ca01332586a644e8804ab6fc47a7e29e` fixes that import and adds a complete
  standalone-program regression. Installer LF SHA256:
  `953e507bcc84760a5deb2028f668cf889bf90f9ca53cb06b2e5edfeb2711b176`.
  Author434 passed/1Windows-flock skip; independent94 Task3 passed/1skip.
  Task2 remains byte-identical:
  `4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`.

The user explicitly approved versioned repair archives to the existing private
QA destination. Exact e2 Git archive SHA256:
`9d0af8f8e0167c3fcc743a4734dc027e99b5acaccd5b567fa7f139f38aae09ba`.
793 archive members were independently checked/staged root-protected at
`/var/lib/betboy-capacity-code-jcogad28/source`. No local secrets or runtime
databases were added to this archive.

Actual ordinary SSH UID1000 e2 tests: **435 passed in41.89s**,
42.587s supervised, no skips/errors, directory
`/tmp/betboy-context-qa.9xr68INa/task3-hooks-e2ae3f6-_9ern2jl`.
These tests do not claim root DAC or native signal durability; those are below.

## Native transaction and principal checks

Controller fully read the independent QA harness before execution. It loads
only pinned `repair_data` stdlib and the fixed lock function, not an installer
main or app imports. Its four path globals point exclusively to a new
root:root0700 scratch tree. Expected old SHA stays the real installed old SHA;
the harmless new fixture is never executed. Installed old bytes are only read
and independently copied into the scratch fixture.

- Exact harness SHA256:
  `b0afaa604525179629580fcbc82a6b3708cfa362bf62a2745431be04fae4423a`.
- Root-private code copy: `/var/lib/betboy-repair-native-code-e5cq4xiq`.
- Actual fixture/evidence: `/var/lib/betboy-repair-transaction-qa-2awoht8p`.
- All nine checks PASS: successful atomic replacement/idempotence/independent
  old copy and actual app DAC; SIGKILL and SIGTERM after installation rename;
  SIGKILL and SIGTERM after rollback rename before parent fsync; third hash,
  external same-new-hash inode and external same-old-hash inode preservation;
  real contention on a scratch-only deploy lock.
- Recovery starts a fresh interpreter. Real fsync order is observed before
  publishing complete/rolled_back. App UID997 opens a directory FD before
  privilege drop: reading succeeds while write/create/rename fails on actual
  target/parent DAC, not merely on the outer private scratch wrapper.
- Installed updater bytes and full metadata remained unchanged before/after.

This is not physical power-loss proof, not outer Bash signal/trap acceptance,
not a full installer preflight, and not real backup/model acceptance. The QA
evidence is synthetic and cannot be used for the production installer.

## Native fixed measurement supervisor

Ignored controller harness `check_native_repair_measurement.py`, exact SHA:
`aa4860db9ded8c10eab0e893fc429bfb0f5425e4ce7d57654b4296aa79d1a038`,
was independently reviewed in full. A one-pass cleanup fork race was fixed
before execution; deterministic reviewer regression confirms the late fork is
also caught. TERM/HUP/INT enter bounded cleanup, with pidfd, exact new QA path,
UID/start-time checks, repeated enumeration and two empty passes. No broad
application/process stop is used. A SIGKILL of the controller itself is not
claimed recoverable by a Python handler.

The exact unmodified measurement function and fixed launcher are exercised.
Root runs stdlib supervision only; synthetic D4 code runs through the launcher
as actual UID997. Inputs and target manifests are root-owned/sealed in unique
new scopes. These are deliberately synthetic, not SQLite/model acceptance.

Short checks all PASS:

| Case | Stage suffix | Observed result |
| --- | --- | --- |
| UID, fixed limits, actual DAC and descendant accounting | `n29jch3h` | UID997; AS2GiB/CPU300; five numeric thread limits1; four real DAC denials;128MiB descendant yields143540224-byte peak and0.566023CPU seconds |
| Actual AS exhaustion | `w4jsq5qr` | 3GiB allocation raises MemoryError under unchanged2GiB AS; rejected |
| Actual peak-RSS rejection | `pz2d5uwu` | 1165754368-byte peak; rejected by unchanged strict1GiB admission |
| Aggregate output/descendant termination | `offwdjq0` | actual output exceeds1MiB; bounded report retained, process group killed and rejected |

All stage paths are `/var/lib/betboy-context-update.<suffix>`. Registrations
bind actual process UID/PID/start ticks; no live registered process remained.
Successful descendant accounting is proved by the waited128MiB child. Metrics
on killed groups are not represented as complete accounting of unwaited
descendants; those outcomes are rejected regardless.

Before the RSS test, available server RAM was2994368512bytes; no competing
memory-intensive VPS QA was running. Only synthetic CPU/wall probes now run:
CPU scope`902t4zyn`, wall scope`6mo65kij` subsequently both PASS:
actual CPU300 termination produced exit137 at300.178475CPU/300.300319wall;
actual wall600+10 termination produced exit137 at610.031500wall. Both were
correctly rejected as resource failures, and no live registered descendant
remained. No limits were shortened or raised for this native evidence.

## Newly discovered real marker-contract mismatch

The complete unmodified e2 standalone guard was next invoked against real
server principals using read-only live access and only new private QA output.
It rejected with `incomplete or mismatched production marker` before acceptance.
This is an installer integration defect, not evidence of an invalid live ledger.

Fresh read-only facts:

- Application HEAD remains`2dd1116b68f3d94e9c24338c6c9dff9b01799221`.
- Installed updater remains`74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`.
- Installed marker helper remains`f22065efc2f321e4eaff20d9d8d006332ffe3a99c26931fc329dab7b8d62458b`.
- Actual marker is complete, for`/opt/betboy/app`, previous
  `82101d33e0a06cd48867d06ebf28aa193a04225c`, historical target
  `e0240ef8e69549f0d904602909a4eb66accc4a98`, SHA256
  `0768f7ca1ca4570827d4a9fafad0edf6b56959ca6f1be5843cbfa2d5e5fcb14d`.
- The unchanged installed helper's actual`require-complete` returns0.
- Independent Git ancestry check confirms the migration target is an ancestor
  of the pinned current application HEAD.

The helper's`prepare_marker` and`complete_marker` deliberately preserve an
existing complete marker. The ordinary updater does not require historical
complete-marker target==new application HEAD. The repair installer incorrectly
conflated those two identities. R3 is correcting only that assumption with
separate exact historical target/hash pins, unchanged production HEAD pin and
full byte/metadata continuity. No marker rewrite, helper change or status-only
fallback is permitted. Independent rereview and fresh real guard check remain.

The original marker was read-only saved to an **ignored** local QA fixture,
with exact hash verified. It contains72 ledger paths/checkpoint MACs and MUST
NOT be committed, uploaded in code archives, or become an untracked CI
dependency. Reproducible tests use a synthetic marker and transparently adapt
only its expected literal hash, preserving real hashing/imports/control flow;
a separate test pins unchanged production literals. Actual real-byte guard
acceptance is a separate controller integration check.

## Broad-suite and production boundaries

### Final standalone production compatibility proof

`f438eeb2` separated the exact historical marker target/hash from the app HEAD.
Author446/1skip; independent106/1skip; native ordinary UID1000 **447 passed
in40.85s**,41.566s supervised, directory
`/tmp/betboy-context-qa.9xr68INa/task3-hooks-f438eeb-3_o0dkem`.
The real full production check then reached the existing environment file and
rejected it because that legitimate optional file is empty. Actual read-only
stat: `/etc/betboy/betboy.env` root:betboy0640, one link, zero bytes. Task2
accepts empty content as no override, distinguishing it from an absent file.
This was a further installer assumption, not a bad production configuration.

`4205db82bb234f0aa07a43510db0576811556090` permits empty content **only** at the
fixed environment read. Every other trusted read retains a nonempty default.
Actual key/marker/updater emptiness remains rejected; later env changes are
still detected without overwriting the earlier continuity proof.

- Final installer LF SHA256:
  `bdc9c700e646e610a07b22077d4b3d00a592b88e4f241a63f5e011642f7c631c`.
- Author450 passed/1Windows-flock skip in61.93s; independent110 passed/1skip
  in8.23s, plus a separate changed-after-first-check empty-env counterexample.
- Exact archive SHA256:
  `0ca67984a1db0e39ecc9322df8893abdcd4daa643e51268fc2d4ebacc3258d93`,793members.
- Root-sealed source: `/var/lib/betboy-capacity-code-8hqty23_/source`.
- Final actual UID1000 Linux tests: **451 passed in40.14s**,40.787s supervised,
  no skips/errors, `/tmp/betboy-context-qa.9xr68INa/task3-hooks-4205db8-sltnxb0c`.
- Actual **whole** production shell function plus unchanged installed helper,
  sanitized app-UID Git command, complete guard and complete byte inventory
  now PASS against the unchanged live server. The guard runs twice around
  capacity admission. QA proof `/var/lib/betboy-repair-guard-qa-4axit_c0`,
  receipt SHA256`0fc13cb0909b9a52bf3e4ca50ab5fadd60ed1769bdbb24827adc078cda7d17ee`.
  Complete byte-based archive admission792576000B; this is not an archive
  capture or backup acceptance. No live state changed.

The native transaction, measurement, launcher and lock evidence above remains
applicable to the final source because actual LF extraction compared their
bytes against the e2 test freeze, not merely their function names:

| Unchanged function | SHA256 |
| --- | --- |
| repair_data | `8a39c36533f6d119dacb29718c726805e9c65f0d8e83d270fa7fcc0c4caebf67` |
| measure_repair_d4 | `478d328f05c4b41089f2d7c06a023c582974d451903fa0f160ff233edf850328` |
| verification_launcher_source | `fdd3949d8ae53f3d27622a8d122306f5ea987672ef21793c8d499f0d7fe40a18` |
| acquire_deploy_lock | `52829b31efc0dbb8d471927e54a2fb563c7d027ca0c367dd13826cc8f474dc7a` |

This does not relabel synthetic evidence as a real complete backup/D4 run.
The two actual integration failures (historical marker and empty environment)
were preserved as failures before the final real program succeeded.

The first frozen27ceb8b broad run was stopped after its new guard defect was
identified. It also had an independent controller setup error: the fresh QA
worktree lacked the`.pytest_tmp` parent. A focused reproduction showed WinError3
at basetemp creation. This was corrected by creating that ignored directory;
none of its setup errors counts as a product test failure or test acceptance.

The broad suite completed in the clean exact-LF e2 QA worktree with the parent
present: **4 failed, 6877 passed, 30 skipped, 97 subtests passed in1647.97s**.
XML`.pytest_tmp/full-e2ae3f6-01.xml`, SHA256
`8679e0ad8fced68ab47099d0cab3ab539f90ebbcc11891098da85bceca7b8082`.
The worktree's tracked files remained clean. This is a failed intermediate
source baseline, not a final-source full-suite acceptance.

All four failures are in legacy`tests/test_server_jobs.py` contracts:

- `test_update_preflights_before_downtime_and_has_recovery_path` expects the
  old backup success string/direct invocation instead of phase-aware output
  and the fixed launcher.
- `test_deployers_verify_backup_unit_dac_with_its_supplementary_group` expects
  the superseded shell-find pattern instead of the exact Unicode-safe source
  enumerator used with the real backup principal and supplementary group.
- `test_updater_publishes_backup_snapshot_only_after_helper_success` expects
  a direct verify-only flag and the old capacity formula in the caller,
  instead of the fixed launcher and combined-device accounting.
- `test_backup_user_migration_is_updater_and_rollback_compatible` expects a
  shell-stat fragment instead of actual device accounting.

Task2's author is independently reproducing these REDs and porting exactly
those four tests to executable behavior checks. Before-downtime ordering,
real restore/HMAC, backup-UID DAC, role separation and complete combined-mount
accounting must remain asserted. No production source change is authorized
by that test-only port. Independent review and a fresh final frozen broad
run remain pending.

### Four-test port and additional native regression run

Test-only commit`e74b51a7be7b272591b20921f7679eb8f38efbb1` independently
reproduced the four old REDs, then passed533 tests/8Windows skips in76.14s.
The independent review reproduced one remaining test-sensitivity gap: ignoring
the real producer's failed restore/HMAC helper status was not rejected by the
ported preflight test. Actual original shell behavior does reject statuses1
and137 before publication; this is a test gap, not an observed production
bypass. A narrowly scoped executable closing-path test is being added.

Root started the full exact-LF Windows suite at frozen e74 at19:16 UTC in
`context-capacity-final-qa-20260910`; it is still running. No source in that
worktree is edited while it runs. The subsequent test-only review correction
must be verified separately; do not falsely label e74 as that later revision.

The exact versioned e74 archive was transferred under the user's QA approval:
SHA256`b8888f3138bed728ebdeac91f762b38146a713f5e9e22549cffe2c16a49a8b05`,
33,709,730bytes,796members. Only ordinary QA UID1000 executes its tests.
The broader native run includes server-jobs, updater hook and repair tests:

- First controller setup lacked an explicit QA import path under Python`-I`:
  one collection error, no test acceptance. Directory`repair-final-e74b51a-tjtr40k8`.
- Second setup reached old synthetic migration fixtures, but SSH umask0002
  created their policy files0664. Read-only stat confirmed ubuntu:ubuntu0664;
  the local policy trust check correctly rejected them. Three failures/17pass
  before maxfail; directory`repair-final-e74b51a-8gl74ycy`.
- The QA-only runner now sets umask0077 before creating new fixtures and
  `-o pythonpath=.`. No existing file, production permission or trust rule was
  changed. This run completed **540passed/1failed in46.36s**,47.017supervised,
  directory`/tmp/betboy-context-qa.9xr68INa/repair-final-e74b51a-k33qbubp`.
- The remaining native failure is the unchanged old
  `test_backup_tree_update_rejects_identical_replacement_and_two_archives`:
  unlinking and recreating identical content did not trigger the expected
  replacement rejection. Linux inode reuse is a hypothesis under independent
  read-only triage, not yet a proven harmless fixture error. The pinned backup
  helper remains unchanged; no full native-green claim is valid.

### Final scoped regression closure — e90320c

The status-propagation test gap was closed by test-only commits`1fc22969` and
`067de6a3`: actual producer completion rejects inline-verifier failure and
helper statuses1/137 before publication, success logging or continuation.
Six independent read-time fault variants are now rejected. Independent final
server-jobs83pass/7Windows skips15.21s; author's final trio533pass/8skips80.82s.
Neither result is relabelled as a new full-suite or real backup run.

The inode diagnostic ran as ordinary UID1000 against the unchanged pinned
backup helper in a new QA fixture tree:
`/tmp/betboy-context-qa.9xr68INa/inode-diagnosis-f5_kjhy9`.
Revised ignored harness SHA256
`2d0796370218b23697ad1492e93b1dcede2096861c806ac6b19d61a279187a8f`.
All8 unlink/recreate cases reused the original dev/inode and matched all9
stored fields; only mtime/ctime changed. Distinct-inode same-byte replacement,
same-inode changed bytes, and two new archives were all rejected. Thus the old
test failed to guarantee the identity change it claimed to test. Fully
record-identical inode recycling remains undetected by that unchanged helper;
this is not a universal historical-replacement detection guarantee.

Test-only`e90320c02c40f152546b4b7b7c4bb3548fb4c9dc` creates its replacement
while the original exists, asserts a distinct POSIX identity on the same
filesystem, then replaces it. The Linux rejection, Windows behavior and
two-archive expectation remain unchanged. Comparator/helper/installer/updater
bytes and all pins are untouched. Independent fixture review APPROVED with
83server-jobs passes/7Windows skips13.86s and actual-record fault sensitivity.
See`task-3-backup-tree-inode-triage.md` and
`task-2-broad-regression-independent-review.md` for the explicit bounds.

Root's fresh final three-file native Linux run now passes **541tests,0skips,
0errors in46.73s**,47.439supervised, ordinary UID1000:

- Exact e903 Git archive SHA256
  `c70530ec62e73e1aae76f973fea7c69aaa3600ea8746836e7f2c4b706c4426e9`,
  33,715,644bytes,797members.
- QA result/fixtures
  `/tmp/betboy-context-qa.9xr68INa/repair-final-e90320c-fqnjbo05`.
- JUnit `repair-final-linux.xml`: UID/GID1000:1000, mode0600,81,868bytes;
  SHA256`e2c4ef7d1645c513e3e9705086bac4db21fe12e603ba5e2d4b326192df3e5cbe`.
- All of`test_server_jobs.py`,`test_context_update_hook.py`, and
  `test_context_updater_repair.py`; no root pytest/application import.
- This is a bounded native regression run, not the full application suite,
  a production backup, measured real-data D4 acceptance or a deployment.

The clean e74 exact-LF Windows full suite is still running. Root checked that
every e74-to-e903 delta is confined to one test file and two reports; all
production code is identical. Do not claim that full suite ran at e903 or
that the historical540pass/1fail run was green.

The previously documented twelve0775-to0755 directory corrections still need
their separate explicit user approval. No such production chmod was performed.
Until that permission boundary is resolved, the fresh real full-backup
producer continues to be blocked. Full real backup/isolated restore/HMAC,
measured exact-target D4, final independent release review, main publication,
updater-only exchange and separate application deployment remain open.
