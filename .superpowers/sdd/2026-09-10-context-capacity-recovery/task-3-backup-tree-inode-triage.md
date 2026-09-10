# Read-only triage: inherited backup-tree identical replacement test

## Current status: separately authorized fixture-only correction

After the read-only diagnosis below, the controller explicitly authorized one
test-only correction on base `067de6a31ebc9a3f13b267bf360eba7dd42802a4`.
Only `test_backup_tree_update_rejects_identical_replacement_and_two_archives`
now creates its same-byte replacement while the original inode remains alive,
outside the scanned tree. It preserves mode, asserts POSIX same-device and
distinct device/inode identity, then performs `os.replace`. Its Linux
`raises(...replaced)` expectation, Windows branch and two-archive check are
unchanged. No comparator, helper, installer or updater source is changed.

The historical sections saying "no test changes" and "not implemented here"
describe the initial read-only stage, not this subsequent authorized test fix.
The original failed native suite and 8/8 recycling observations remain evidence.
Record-identical recycled generations remain undetected; this fixture fix does
not create or imply a universal historical-replacement detection guarantee.

Fresh local Windows validation: targeted test **1 passed in 1.18s**; full
`tests/test_server_jobs.py` **83 passed, 7 skipped in 13.53s**, exit0. Both used
quality Python with `-B -m pytest -q -o pythonpath=. -p no:cacheprovider
--tb=short`; full-suite basetemp and JUnit output are
`.pytest_tmp/tree-replacement-fixture-server-jobs` and its `.xml` sibling.
Scoped `git -c core.autocrlf=false diff --check` passes. This does not replace
the controller's fresh final Linux archive run or independent fixture review.

Unchanged production-source hashes checked before and after the test edit:

- Backup helper: `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604`.
- Installer: `bdc9c700e646e610a07b22077d4b3d00a592b88e4f241a63f5e011642f7c631c`.
- Updater: `4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`.

## Initial read-only diagnosis (preserved)

10 September 2026. No product/test/helper changes, Git operations, SSH or VPS
execution by this investigator. The helper's local exact SHA256 remains
`b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604`.
Controller reported an ordinary-UID1000 native e74b51a run with 540 passes and
one failure in `test_backup_tree_update_rejects_identical_replacement_and_two_archives`.

## Source evidence and hypothesis

- `tests/test_server_jobs.py` creates `runtime.tar.gz`, snapshots the backup
  tree, then unlinks and recreates that file with the same bytes. On Linux it
  unconditionally expects a `replaced` RuntimeError. It neither holds the
  original inode open nor creates the replacement while the original exists,
  and does not assert different before/after device/inode identifiers.
- `_backup_tree_record` in `scripts/backup_runtime_databases.py` (line 2440)
  stores path, kind, UID, GID, mode, size, SHA256, origin device and origin inode.
  `_backup_tree_records_match` (line 2460) compares exactly those fields when
  `require_origin_identity=True`; neither generation nor ctime is persisted.
- `verify_backup_tree_update` (line 3418) uses that identity comparison for all
  retained entries on Linux, plus the exact new-archive and retention checks.
  Its scan hashes the actual open file and validates the descriptor/path, but
  this cannot recover an unrecorded identity generation between two scans.
- Therefore a recreated file with recycled inode, identical contents and
  matching saved metadata is observationally equal under this implemented
  contract. Changed ctime/mtime alone will not cause its rejection. The test's
  unconditional unlink/recreate rejection has an unsatisfied fixture premise.

At initial source-only triage the original trial's before/after stats were not
available. The subsequent controller-native results below confirm the exact
explanation with repeated original trials and independent controls.

## Bounded native diagnostic (prepared, not executed here)

Ignored `.pytest_tmp/diagnose_backup_tree_inode_reuse.py`, SHA256
`4c3c279925221100234a6b971094c8fe5fffea8612167c152d6b1cf68b426959`.
Syntax-only compilation passed locally. Run only as Linux UID1000 with system
Python `-I -B`; it rejects root and other UIDs. It checks the exact helper bytes
in `/tmp/betboy-context-qa.9xr68INa/repair-final-e74b51a-k33qbubp` before loading
that standalone stdlib helper. It imports no application/test module, changes
no helper globals and uses no monkeypatch. All writes are new synthetic fixtures
under a newly allocated `/tmp/betboy-inode-diagnosis-*` tree, retained for review.

Eight original unlink/write trials report full before/after stats, actual saved
record equality, and the real verifier outcome. Three controls exercise a
guaranteed different inode (candidate created while original remains linked),
same-inode changed content, and two new archives. Each control must reject via
the actual verifier. No test skip, inode allocator forcing, privileged write,
helper pin change or fixture cleanup is used to obtain a favorable result.

## Relevance and present disposition

The updater-only installer never calls backup-tree snapshot/update verification.
This finding does not directly exercise its new updater transaction, its fresh
DB archive/restore/HMAC path or D4 replay. It is not evidence of a new Task3
backup-corruption or D4 defect. The helper bytes are unchanged and remain pinned.

The ordinary updater DOES call `snapshot_backup_archives` and later
`verify_backup_service_migration`, whose service probe invokes this helper's
tree verifier. Thus its inherited identity-generation limitation is relevant
to that later deployment acceptance path; it must not be described as proving
that every historical unlink/recreate event is detected.

If the native harness confirms same saved fields/recycled inode accepted and
distinct inode/content/two-archive controls rejected, classify the reported
test failure as nondeterministic fixture construction under the existing
implemented contract, not a changed helper contract or newly introduced product
regression. Separately retain the pre-existing limitation: device/inode equality
is not a proof that an inode was never freed and reallocated. A requirement to
detect EVERY such event would need a separately authorized helper/contract
change, not a hidden pin replacement in this repair.

The broad suite's failed run must remain reported as failed until the controller
records the diagnostic and decides the test/acceptance treatment. Neither a
skip nor a blanket release approval is justified by this source-only triage.

## Native confirmation and final classification

Controller constrained the diagnostic fixture root to the already authorized
QA directory and added UID1000/mode0700 checks. The inspected revised harness
SHA is `2d0796370218b23697ad1492e93b1dcede2096861c806ac6b19d61a279187a8f`.
Controller executed it as UID1000 under
`/tmp/betboy-context-qa.9xr68INa/inode-diagnosis-f5_kjhy9`, using the exact
e74 QA helper bytes. Reported observed results:

- All 8 original unlink/write trials reused the original device/inode pair
  and were accepted. Only mtime_ns and ctime_ns changed; all nine stored record
  fields stayed identical and the actual comparator returned equal.
- Guaranteed different-inode replacement, with all content/metadata otherwise
  equal, was rejected with `changed or replaced`.
- Same-inode changed content was also rejected with `changed or replaced`.
- Two newly created archives were rejected as an unexpected entry set.

This confirms a nondeterministic test-fixture premise, not a new helper/runtime
regression. It ALSO confirms the pre-existing generation-observation limit:
fully record-identical inode recycling is not detected. Both statements are
necessary; the latter must not be erased by a passing repaired fixture.

### Normative language versus the observable contract

The test name `rejects_identical_replacement` and Linux `raises(...replaced)`
read broadly. The runtime error `changed or replaced an existing backup entry`
describes detected record differences; it does not add a persisted generation
field. The concrete version-1 record schema and comparator define the actual
observable contract. Crucially, this same inherited test explicitly accepts
known identical-content replacement on Windows, where origin identity checking
is disabled. This supports interpreting its Linux assertion as detection of
a different device/inode identity, not a general event-history proof.

The inspected deployment README's explicit no-replacement statement concerns
the APP account's DAC exclusion from the protected backup directory; the
diagnostic runs as the directory's owner and does not refute that DAC statement.
No stronger generation-tracking promise was found in the inspected current
capacity plan, Task3 brief or deployment README. Nevertheless, a separately
required guarantee against EVERY intervening unlink/recreate would exceed this
existing record contract and would remain an unresolved product requirement.

### Permissible deterministic fixture repair (not implemented here)

Yes: create the same-byte replacement while the protected original still
exists, on the same test filesystem and outside the scanned backup tree;
preserve its UID/GID/mode, assert distinct `(st_dev, st_ino)` pairs, then use
`os.replace` onto the protected path. Keep the existing Linux rejection and
Windows behavior assertions, the two-archive control, and all helper bytes/pins
unchanged. This makes the intended identity mutation real and deterministic;
it does not relax a runtime check, skip a failure or alter accepted records.
Retain this generation-limit disclosure rather than describing that repaired
test as detecting every possible same-byte unlink/recreate event.

Updater-only transaction/real DB restore/HMAC/D4 are not directly blocked by
this unused backup-tree API. The ordinary deployment service-probe path does
use it, so the bounded interpretation above must accompany that gate. The
failed 540-pass/1-fail run remains historical evidence; only a fresh authorized
run after a narrowly reviewed fixture correction can clear that regression
test gate. No helper change is justified or authorized by this diagnosis.
