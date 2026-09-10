# Task 3 independent review — chronological evidence

**Latest source status:** all confirmed findings below, including the historical
migration marker and legitimate empty environment file, are closed on
`4205db82bb234f0aa07a43510db0576811556090`. Its exact installer SHA256 is
`bdc9c700e646e610a07b22077d4b3d00a592b88e4f241a63f5e011642f7c631c`.
Source review is approved subject to the independent native and real-data
acceptance gates. The controller's separate
measurement harness is scope-approved at SHA256 `aa4860db9ded8c10eab0e893fc429bfb0f5425e4ce7d57654b4296aa79d1a038`.
Neither verdict claims production deployment or successful native execution.

10 September 2026. Reviewed range `9e97f2bda1bedbd7e61aeeddfc9b25b6a9992b40` →
`ce1021ee1f80e68b4a35c29e85fb70b857b27fa0`. Exact installer LF SHA256:
`8476a5a9a4956245ddb4026f5aff9bb1c8db980859d34fc129a28d453bf415f7`.

Independent read-only review of the complete plan, Task-3 brief/report, all
2,385 installer lines and the complete relevant test/README patch. No production
action, code edit, Git index operation, commit or push was performed. Only this
report and an ignored local reproduction script were added. Existing controller
and unrelated work was preserved.

## Verdict

**Not ready for the updater exchange.** One current production compatibility
failure and two acceptance/durability defects must be fixed and independently
rereviewed. The existing green test suite does not cover these cases.

## Findings

### P1 — Root-only ancestor check rejects the existing live installation

`deploy/repair_context_updater.sh:1962`, invoking `ancestors(app.parent)`.
The helper at lines 1897–1903 permits only UID 0 ancestors. The controller's
fresh read-only production metadata is `/opt = 0:0/0755`,
`/opt/betboy = 997:987/0750`, `/opt/betboy/app = 997:987/0750`.
Consequently the first `verify_repair_production` fails before any backup,
even though the existing app-owned parent is legitimate and Task2's live
configuration boundary supports that owner domain.

Independent reproduction executes the actual `ancestors` function with those
observed metadata records and yields `SystemExit: unsafe root-private ancestor`.
This is local metadata simulation, not a second live VPS observation.

Use a separate, explicitly scoped live-path/principal validation for this
existing parent. Do not loosen the root-only rule for the private source,
sealed input, executable parent, evidence or journal trees; do not chown the
live installation merely to satisfy the new guard. Add current-layout positive
coverage and foreign-owner, writable, symlink and replacement negative cases.

### P2 — Installer capacity accounting omits SQLite companions

`deploy/repair_context_updater.sh:2013–2021`.
The new capacity walk counts only paths whose final suffix is a database suffix.
It omits WAL, SHM and rollback journals, unlike the accepted Task2 enumerator.
It also lacks that enumerator's raising `onerror` and child-directory checks.
This is not a full-backup integrity bypass: the later producer still rejects
errors, but the initial byte admission is wrong and can reject a valid complete
online snapshot for the very growth pattern this repair is meant to support.

The reproduction creates a real valid SQLite WAL database with auto-checkpoint
disabled and 24 committed 4-MiB records. Actual files: main 4,096 B,
WAL 101,380,872 B, SHM 229,376 B. The actual installer capacity branch admits only
67,117,056 B; a normal complete SQLite backup is 100,782,080 B. The unchanged
DB-plus-companion contract would admit 270,337,552 B. No budget increase or row
pruning is required: reuse the accepted complete locale-independent inventory
semantics and derive the same fixed formula from its complete byte count.

The fixture uses real SQLite contents and backup; only root metadata, absolute
production paths and the free-space result are simulated. Test companion case
folding, traversal errors and unsafe directory/file entries as well as a real
WAL-heavy snapshot.

### P2 — Repeated recovery can publish rollback completion without syncing the rename

`deploy/repair_context_updater.sh:224–250`, specifically the current-old branch
which reaches `value["phase"] = "rolled_back"` without syncing the installed
parent directory.

Reproduction: interrupt the initial install after its replacement; run recovery;
interrupt that recovery immediately after the rollback `os.replace` and before
its parent fsync. In a fresh namespace, the next recovery sees the recognized
old rollback inode, writes/fsyncs the `rolled_back` journal and returns `old`.
The observed fsync sequence contains the private-state parent, the next journal
file and the private-state directory, but **not the installed executable's
parent**. Thus recovery declares the previously interrupted rename durable
without establishing the promised parent-directory barrier. A further crash
can leave a journal/target discrepancy on a filesystem that does not make the
other directory's fsync a substitute for this one.

This is an actual transaction-control reproduction on isolated real files using
the existing transparent Unix metadata/Windows directory-fsync fixture. It is
not a claim of an observed physical VPS power-loss failure. Before publishing
rollback completion for a recognized old inode, establish and verify the
installed-parent durability barrier as well. Test a fresh-process restart at
each rollback rename/fsync boundary and failure of this new barrier.

## Fresh verification

- `bash -n deploy/repair_context_updater.sh`: exit 0.
- `git diff --check` over the reviewed range: exit 0, no whitespace findings.
- Independent Task 3 run: **69 passed, 1 skipped in 4.38 s**.
- Independent integrated Task 3 + Task 2 run: **409 passed, 1 skipped in 60.50 s**,
  exit 0. The skip is the explicitly unavailable Windows real-flock test.
- `.pytest_tmp/installer_independent_repros.py`: exit 0; reproduces all three
  findings above. It makes no network/production request and imports no app
  code with root privileges.

The controller subsequently committed documentation while this review was in
progress. The reviewed installer/test/README files were unchanged; the verdict
is bound to the exact source revision/digest above, not a moving branch claim.

## Strengths and remaining native gates

The strict public request grammar, hardcoded trusted fetch target, root-private
independent old-byte copy, explicit full backup/restore/HMAC composition, app-UID
D4 execution and refusal to overwrite unknown installed hashes/inodes are
substantive safeguards. The seventeen reused Task2 seams are guarded by exact
source parity. No automatic application deployment path was found in the
installer. No new root import of app/venv/model code was found.

After the fixes, native acceptance is still necessary: actual invocation with
the existing live principals; independent root-private staging and app DAC;
real lock contention; exact fixed D4 process UID, descendant rusage accounting,
hard memory/CPU/output/wall termination with no surviving child; durable
replacement and repeated signal/crash recovery; and a brand-new full live
backup with actual isolated restore/HMAC plus measured exact-target D4 before
exchange. The current/growth Task1 measurements and prior Task2 native tests
do not substitute for this new supervisor/transaction's native evidence.

Keep the separately requested twelve-directory permission repair outside this
installer. Keep ordinary application deployment separate from updater-only
replacement, and distinguish both from the unfinished model/source work.

## Focused rereview — 27ceb8bd, still HOLD

Reviewed `ce1021ee1f80e68b4a35c29e85fb70b857b27fa0` →
`27ceb8bd814308deb0e0705eeb8d2bc171d2d32f`, installer SHA256
`eb2b1843a58c7b66171feaa832d9425429d6637cf9249992ab986cc4767bcf63`.
Read the entire relevant corrective diff, added tests and implementation report.

The original three corrections are present and appropriately scoped:

- `live_application_identity()` permits the app UID/primary GID only for the
  literal `/opt/betboy` and `/opt/betboy/app`, retains the root-only ancestor
  function for all protected domains, and checks both live identities again
  before writing/comparing the continuity proof.
- `enumerate_backup_sources()` is copied byte-for-byte from accepted Task2;
  actual Bash preparation aborts a failed enumeration before capacity/fetch.
  The capacity formula now uses its rounded-up full DB/companion KiB.
- A recognized already-old recovery path now synchronizes the executable parent
  before recording `rolled_back`. New restart cases cover interruptions after
  rollback rename/fsync and failure of the subsequent barrier.
- The controller's additional original-inode-reuse finding is addressed by
  comparing all nine original signature fields. The separate own rollback
  identity path is retained, rather than requiring the original inode after a
  legitimate atomic rollback.

### New P1 — The complete capacity program is missing its `re` import

`deploy/repair_context_updater.sh:2088` calls `re.fullmatch`, but the independent
`repair_guard` Python program's import block at lines 1941–1947 does not import
`re`. Imports in other shell heredocs run in other Python processes and cannot
supply this name. Consequently every ordinary preparation reaching the capacity
guard exits with `NameError: name 're' is not defined`, before source fetch or
backup.

The existing capacity AST test supplies `"re": re` in its synthetic namespace,
masking the missing production dependency. An independent reproduction executes
the **entire unchanged guard program** with only root UID, `pwd` and argument
fixtures; it does not inject `re`, alter production branches, or access any VPS
path. Result: the exact `NameError` above. Reproduction file:
`.pytest_tmp/installer_rereview_missing_import.py`.

Add the import to the actual program and a whole-program capacity regression
which preserves real imports. A passing AST fragment test alone is insufficient.

Fresh rereview verification: **90 Task3 tests passed, 1 Windows-flock skip in
5.65 s**, exact installer digest above confirmed, Bash syntax and scoped diff
whitespace checks passed. The new whole-program reproduction also completed
successfully by detecting the expected `NameError`. This is why the source
remains HOLD despite those green tests. Native gates listed above remain open.

## Closing source rereview — e2ae3f69

Reviewed the complete follow-up production/test/report diff from `27ceb8bd` to
`e2ae3f69ca01332586a644e8804ab6fc47a7e29e`. Production change is exactly one
`import re` inside the `repair_guard` program. The new four-case regression
executes the whole unmodified guard with its actual imports; it supplies only
isolated process arguments, paths, principal metadata and free-space fixtures.
It no longer injects an algorithm dependency that production might lack.
Valid inventory is accepted, and zero/partial/newline-bearing inventory strings
are rejected without capacity output.

Independent fresh verification: **94 Task3 tests passed, 1 Windows-flock skip in
5.52 s**; actual Bash syntax check passed; installer SHA256 confirmed as
`953e507bcc84760a5deb2028f668cf889bf90f9ca53cb06b2e5edfeb2711b176`.
The missing-import finding is closed. Together with the preceding focused
review, no confirmed source finding remains open in this exact installer.
Approval is for the reviewed source, not for bypassing any native acceptance
gate or for automatically deploying the app.

## Controller measurement harness scope review

Read all code in ignored `.pytest_tmp/check_native_repair_measurement.py` at
initial SHA256 `cbc8d6cd35ad38c9b1b0e6b080211aaf272205978148bfd64e3541897064fc08`.
Root executes only the pinned, previously reviewed stdlib supervisor and
filesystem/process transport. Synthetic probe code runs through the fixed
launcher as the real non-root app UID; it does not import app models or read
production runtime databases. New writes are confined to uniquely created
root-owned `/var/lib/betboy-context-update.<8>` trees. The installed updater
and pinned source are read and checked for unchanged identity/digest.

Two initial cleanup concerns were raised before any execution: a single
`/proc` pass could miss a concurrently appearing own child, and default
SIGTERM/SIGHUP would not invoke the Python exception cleanup. A deterministic
local execution of the actual old cleanup function demonstrated PID 10 killed
but a newly visible own PID 11 left alive. This was simulated process evidence,
not a signal to real local or production processes.

The controller corrected and froze the harness at SHA256
`aa4860db9ded8c10eab0e893fc429bfb0f5425e4ce7d57654b4296aa79d1a038`.
The entire corrected harness was reread. Cleanup now repeats only exact own
QA-path/UID/start-time/pidfd-bound matches until two empty passes, bounded to
five seconds; dead/zombie entries are not treated as live. TERM/HUP/INT enter
error handling and are ignored during the short bounded cleanup itself.
The same deterministic fork-race counterexample now kills both own PIDs and
leaves none; syntax compilation succeeds. Reproduction remains in ignored
`.pytest_tmp/installer_harness_cleanup_repro.py`.

**Harness verdict: scope-approved for the described isolated native probes.**
No broad application/process-group cleanup or production mutation was found.
Before the deliberate 1100-MiB RSS probe, check current host memory reserve;
do not overlap it with another memory-heavy VPS backup/model QA run. The short
harness cases themselves are serialized. CPU/wall probes retain the exact
300-second CPU and 600-second wall-plus-grace constraints. Their results must
still be observed; this review does not claim those native tests passed or
turn synthetic measurement output into real model/backup acceptance.

## Native integration finding — completed migration marker is historical

The controller subsequently ran the complete root stdlib continuity guard
against actual production, read-only. App HEAD remained
`2dd1116b68f3d94e9c24338c6c9dff9b01799221`, but the guard rejected the valid
existing marker with `incomplete or mismatched production marker`. Observed
historical marker: status `complete`, target
`e0240ef8e69549f0d904602909a4eb66accc4a98`, previous
`82101d33e0a06cd48867d06ebf28aa193a04225c`, application root `/opt/betboy/app`,
SHA256 `0768f7ca1ca4570827d4a9fafad0edf6b56959ca6f1be5843cbfa2d5e5fcb14d`.
These live values are controller observations, not a second independent VPS
read by this reviewer.

Independent code verification confirms that this is a repair assumption error,
not a broken migration: the unchanged pinned marker helper SHA256 `f22065ef…`
returns an existing complete marker unchanged from both `prepare_marker`
(lines 290–291) and `complete_marker` (lines 326–327).
`require_complete_marker` validates completion/provenance, not equality to a
later app release. The ordinary updater requires target equality only in its
`in_progress` branch; its `complete` branch preserves the historical migration.
Local `git merge-base --is-ancestor e0240ef8… 2dd1116b…` returned exit 0.

An exact one-time repair pin for the historical marker target and complete
marker SHA is within the approved scope, provided the current app HEAD pin,
complete-state helper validation, byte/stat/key/principal continuity checks
remain intact. The historical predecessor must remain bound explicitly or by
that complete-marker SHA. Do not alter the marker, accept arbitrary complete
markers, weaken protected-directory ownership, or conflate migration identity
with current deployment identity. The implementation and its regressions still
require an exact independent rereview.

## Closing historical-marker rereview — f438eeb2

Read the complete frozen production/test/report diff from
`e2ae3f69ca01332586a644e8804ab6fc47a7e29e` to
`f438eeb2ed64202b35c5ee40f64200e81874f066` and independently confirmed the
installer digest `8331d9afa47149f888af6959d40f6b40134293c5a38ae05dc416a9f048ec4592`.
The only production changes introduce the exact historical marker SHA and
target pins inside the guard and use that historical target in the shell's
complete-state check. The current app HEAD remains independently fixed to
`2dd1116b68f3d94e9c24338c6c9dff9b01799221`. The full marker-byte pin also binds
its historical predecessor and migration receipt; arbitrary complete markers
are not accepted. The helper's unchanged validation and the existing
marker/key/environment/updater identity and digest continuity remain intact.

The transaction/recovery and measurement supervisor code is byte-for-byte
unchanged by this follow-up. The ordinary Task2 updater remains SHA256
`4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`, and the
marker helper remains SHA256
`f22065efc2f321e4eaff20d9d8d006332ffe3a99c26931fc329dab7b8d62458b`.
There is no marker rewrite, app deployment, widened directory-owner exception,
or modification to a model/DB/key/unit/helper in this fix.

The permanent regressions contain a synthetic one-database receipt only. Their
whole-guard fixture preserves real imports, file reads, digest algorithms and
control flow. It adapts the explicit expected marker digest literal to the
synthetic fixture's digest, alongside the pre-existing isolated OLD-updater
byte fixture pin; it does not replace hash functions or validation functions.
A separate test checks the exact unmodified production marker pins. All
negative marker mutations retain the originally expected fixture hash; changed
bytes after a successful continuity proof are rejected without replacing that
proof. Shell composition tests separately reject an in-progress marker,
foreign migration target and changed app HEAD. `git check-ignore` confirms the
real marker file is ignored, and `git ls-files` returns no entry for it. This
review did not read or copy its sensitive contents.

Independent fresh checks: **106 Task3 tests passed, 1 expected Windows-flock
skip in 8.04 s**. Actual Bash syntax and scoped Git diff whitespace checks
passed. No new confirmed finding remains open in this frozen source. The
controller's whole native helper/Git/guard composition, actual capacity
inventory, native timing/resource/transaction evidence, and fresh complete
backup with restore/HMAC plus exact-target D4 remain separate acceptance
evidence. This source approval does not assert those external results or
authorize any change beyond the already approved updater-only repair.

## Native integration finding — an empty environment file is valid

After the marker correction, the controller's read-only native composition
reached `/etc/betboy/betboy.env` and rejected it with `unsafe trusted file`.
Controller metadata: UID 0, GID 987, mode 0640, one link, zero bytes. No secret
contents were required or disclosed. These are controller observations, not
an independent VPS read by this reviewer.

**P1 compatibility finding on f438eeb2:** the shared `repair_guard.read` requires
`0 < before.st_size` at installer lines 1997–1999 and is called without an
environment-specific distinction at line 2056. It therefore stops every repair
attempt against this legitimate installation before reaching the acceptance
pipeline. Do not fill or otherwise modify the live environment file merely to
satisfy this new guard.

Independent inspection of the unchanged Task2 updater confirms the intended
contract: `read_file` at lines 1337–1353 permits a bounded zero-length file;
`configuration` at lines 1455–1464 treats missing configuration as `None`, but
an existing empty configuration as empty bytes, whose digest is still included
in the configuration receipt. `runtime_override` has no assignments to process
for empty input and returns `None`. The default context path is then
`runtime_state/context_models.db`.

The actual Task2 stdlib helper was freshly executed locally, without app/model
imports or file mutations. Assertions confirmed `configuration_lines(b'')`
returns `['']`, `runtime_override(b'')` returns `None`, and `runtime_relative`
selects the default path above. Task2 SHA256 remained
`4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`.

A narrowly explicit empty-file allowance for the fixed optional environment
read is compatible with this contract. It must preserve the absence/presence
distinction, empty-byte digest and repeated inode/metadata continuity. Key,
marker, updater, installer-self, candidate and evidence reads must remain
nonempty; file type, path, ownership, hardlink, size-upper-bound and DAC checks
must not be relaxed. The fix is not yet independently accepted in this section.

## Closing empty-environment rereview — 4205db82

Read the complete frozen production/test/report diff from `f438eeb2` to
`4205db82bb234f0aa07a43510db0576811556090`, then reread the whole guard. The
installer SHA256 was independently confirmed as
`bdc9c700e646e610a07b22077d4b3d00a592b88e4f241a63f5e011642f7c631c`.

The shared bounded reader now has keyword-only `allow_empty=False`; exactly
one call provides it, determined by `name == "environment"` in the literal
trusted-file tuple containing `/etc/betboy/betboy.env`. The caller cannot select
a path or enable this via CLI arguments. All other `read` calls retain the
nonempty default, including self, updater, candidate and structured evidence
reads. The separate evidence hashing loop is unchanged; its existing allowance
for zero-byte log files is not introduced or widened by this fix. Root-owner,
regular-file, one-link, no-write, nofollow, descriptor/path identity and maximum
size checks remain intact. Empty bytes are still hashed and their full file
signature participates in repeated continuity checks. Missing configuration is
not silently recreated or turned into an empty file.

Independent fresh verification: **110 Task3 tests passed, 1 expected Windows
flock skip in 8.23 s**, plus Bash syntax and scoped diff whitespace checks. The
whole-guard cases accept the empty environment twice with its actual empty-byte
digest, while rejecting empty key, marker and updater fixtures. All marker,
app HEAD and helper pins remain unchanged. Task2 remains SHA256 `4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`;
the helper remains SHA256 `f22065efc2f321e4eaff20d9d8d006332ffe3a99c26931fc329dab7b8d62458b`.

Additional independent ignored reproduction
`.pytest_tmp/installer_empty_env_independent_repro.py` passed against the exact
installer digest. It asserts the sole explicit `allow_empty` call in the actual
AST, runs the complete guard with synthetic marker bytes and the established
Unix-principal fixture, verifies the empty environment digest, then changes
that environment and confirms rejection without changing the original proof.
It also executes the real bounded reader to confirm the default rejects empty
bytes. These are local tests with ordinary quality Python, not native DAC proof.

The empty-environment compatibility finding is closed. No new confirmed source
finding remains open on this exact revision. Native production composition,
complete inventory, real backup/restore/HMAC, exact-target D4 and resource
measurements still require their own observed evidence; no production action,
Git index operation, commit, push or deployment was performed by this reviewer.
