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

A fresh broad suite is running in the clean exact-LF e2 QA worktree with the
parent present. It is an intermediate source baseline, not yet a result and
not acceptance of the still-pending marker fix.

The previously documented twelve0775-to0755 directory corrections still need
their separate explicit user approval. No such production chmod was performed.
Until that permission boundary is resolved, the fresh real full-backup
producer continues to be blocked. Full real backup/isolated restore/HMAC,
measured exact-target D4, final independent release review, main publication,
updater-only exchange and separate application deployment remain open.
