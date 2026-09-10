# Task 2 broad-regression port — independent review

## Current narrow verdict — APPROVED (test-only port and fixture)

**Latest verdict: APPROVED for the cumulative test-only changes at
`e90320c02c40f152546b4b7b7c4bb3548fb4c9dc`.** The original P2 below was closed
by the fully reviewed `1fc2296907c139556a7d8559f9ddcc907b2653cf` and `067de6a3`
follow-ups; the separate deterministic-inode fixture review is at the end of
this report. Final test-file SHA256:
`abb5bb3d0f069be85e23743b388fded7119336aa094f424a2f764282b9c473e5`.
No confirmed scoped finding remains open. This is not native Linux, installer,
backup-data, product/model or deployment approval.
The original HOLD below is historical and resolved; it is not the current
verdict. The record-identical inode-generation limit remains explicitly stated.

Reviewed the complete two-file diff from
`54b4a37f007efcc1e5b961fe5605045e29586abd` to
`e74b51a7be7b272591b20921f7679eb8f38efbb1`: `tests/test_server_jobs.py` and
`task-2-broad-regression-port.md`. Test-file SHA256:
`64c824a796f84a48a12188d9d7240b50827a87b0c6e206c9295511b0b2673dd2`.

**Initial e74b51a verdict was HOLD: one P2 executable-regression gap.** The production code remains correct
for the reproduced case; this finding concerns the promised test contract, not
a newly introduced production defect. All other reviewed ported requirements
are preserved and meaningfully strengthened compared with their old literal
assertions. The narrow writer fix and independent rereview are documented at
the end of this report; the original evidence below is retained.

Production bytes were verified unchanged: updater SHA256
`4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`, repair
installer SHA256
`bdc9c700e646e610a07b22077d4b3d00a592b88e4f241a63f5e011642f7c631c`.
The controller's three separate handoff/evidence document edits were not
modified. This reviewer made no product/test edits, Git index operation, push
or VPS action; only this report and an ignored reproduction were written.

## P2 — Restore/HMAC failure is not exercised before archive publication

`tests/test_server_jobs.py:176–184` checks source ordering and the presence of
the helper failure message, then substitutes a print-only `produce_update_backup`
for the executable phase-wrapper checks. The launcher exercise establishes the
correct helper and arguments, but never supplies a failed helper outcome to
the real producer completion path.

Independent read-time-only mutation of the updater replaces exactly:

```bash
[[ "${CONTEXT_COMMAND_STATUS}" == 0 ]] || die "Full backup restore/authentication verification failed."
```

with `[[ true ]] || die` followed by the same message. The ported
`test_update_preflights_before_downtime_and_has_recovery_path` still passes.
The error-message ordering assertion cannot distinguish an effective failure
guard from an unreachable `die` branch.

The impact was independently reproduced by executing the actual producer's
closing shell segment, preserving inline-verifier/helper/condition/publication
ordering. Only external validation outcomes and the Python publication boundary
were simulated; the publication heredoc was consumed, never executed. For
helper exit status 1 and 137, the real source returns exit 1 without publication;
the mutant returns exit 0 and reaches both publication and continuation. Status
0 publishes successfully in the real source. No filesystem publication or real
service operation was performed.

Required correction: execute the real closing control flow with both success
and failed inline/helper outcomes and assert that failures cannot reach archive
publication or subsequent continuation. Retain the existing actual-main/hook
tests proving a failed online-backup boundary cannot reach downtime. A new
literal check for the status expression alone would not close the requested
executable test gap.

## Other independently verified contracts

- All four original test functions from `54b4a37` were executed against the
  current unchanged source and reproduced their obsolete assertions at base
  lines 166, 2310, 3091 and 3165. None was silently dropped.
- The new real phase wrappers distinguish online/quiesced work directories,
  archive destinations and source HEAD. The existing actual preflight/main
  ordering tests and real archive/restore/HMAC-tamper tests remain present.
- The DAC test runs the actual casefold enumerator and shell loop on real
  synthetic paths, including Unicode SQLite names and WAL/SHM companions. It
  checks the exact backup UID command with `-g betboy-backup -G betboy`, requires
  non-writability of all discovered sources/parents/auth/configuration paths,
  and aborts on a simulated writable companion. Bootstrap retains its unchanged
  GNU-find assertion. Native Linux DAC is not simulated into an acceptance claim.
- The real fixed launcher checks the actual pinned helper bytes and selects
  precisely root `--verify-only --recovery-mode` or backup-service
  `--verify-only`. Wrong scheduled UID, root reuse and extra recovery arguments
  are rejected. The 2-GiB address-space and 300-second CPU limits and numerical
  thread environment are asserted at the controlled process boundary.
- The actual capacity program executes with explicit OS device/free-space
  facts. Independent arithmetic confirms 519/517/388 MiB for 1 MiB existing
  backups and databases, 1424 MiB when all reservations share a device, exact
  boundary admission, one-byte-under rejection on each mount and rejection of
  a full real recovery mount despite space on its parent.

Independent sensitivity checks rejected wrong online phase, omitted backup
supplementary group, altered `--verify-only` and replacing shared-device addition
with `max`. The restore/HMAC guard mutation above was the one surviving case.
All reproduction code is in ignored
`.pytest_tmp/broad_port_independent_mutations.py`; updater bytes are asserted
unchanged before and after execution.

## Fresh verification and platform boundaries

- Four ported cases: **4 passed, 86 deselected in 2.86 s**.
- Full requested targeted trio (`test_server_jobs`, `test_context_update_hook`,
  `test_context_updater_repair`): **533 passed, 8 skipped in 76.19 s**, exit 0.
  JUnit: ignored `.pytest_tmp/broad-port-independent-integrated.xml`.
- Scoped Git diff whitespace check passed; exact production hashes above
  confirmed. The green count does not override the surviving fault mutation.

These runs used ordinary local Windows quality Python and Git Bash. They are
neither root pytest nor a Linux full-suite result. The controller's separate
clean exact-LF broad-suite worktree is also Windows; the author's wording about
an outstanding exact-LF "Linux rerun" must not be read as evidence that such a
full Linux run occurred or was scheduled. The controller's separately scoped
native Linux checks are distinct evidence. Native symlink/flock/DAC, real
backup/restore/HMAC, installer acceptance, model quality and production
deployment remain separate gates and are not certified by this test-only port.

## Closing review — 1fc22969 and 067de6a3

Read both complete follow-up diffs and their report additions. The change is
still limited to the ported server-jobs test and the author's own report. The
final test-file hash matches the bytes independently exercised before the
commit was frozen. Updater `4b814c50...` and installer `bdc9c700...` remain
byte-for-byte unchanged; scoped Git diff whitespace checks pass.

The new harness executes the original producer completion from its inline
archive validator through the helper, its actual status guard, the original
publication heredoc and final success log. The inline/helper process outcomes
are explicit doubles. The absolute Python publication command is a Bash
function that only consumes the unchanged heredoc and records its invocation;
it executes no root Python and publishes no archive on the reviewer host.

- Inline 0, helper 0: exact publication, verified log and continuation.
- Inline 0, helper 1 or 137: exact real rejection, no publication, verified log
  or continuation.
- Inline 1: only the inline boundary is reached; no helper, publication,
  verified log or continuation.

The unchanged real preflight/main tests separately establish that failure at
the online-backup boundary cannot reach service stops or state writes. Real
archive, restore, authentication-tamper and producer-byte tests remain in the
suite. Together these executable checks close the status-propagation gap
without substituting another source-string assertion or modifying a production
acceptance rule.

Independent fault sensitivity was rerun on the final exact test bytes: all six
mutants were rejected. In addition to the original four controls, both the
helper `[[ true ]]` bypass and inline `|| true` suppression now fail the actual
test. The separate actual-closing counterexample still demonstrates why the
bypasses are unsafe, without changing any installed or repository product file.

Independent fresh final-file verification: **83 server-jobs tests passed,
7 expected Windows symlink skips in 15.21 s**, exit 0; JUnit is ignored
`.pytest_tmp/broad-port-independent-final-serverjobs.xml`. The earlier
independent integrated trio was **533 passed, 8 skipped in 76.19 s** on e74;
it is not relabelled as a final-commit full rerun. The author's final trio
**533 passed, 8 skipped in 80.82 s** is separately reported evidence, not a
second independent execution by this reviewer.

The author corrected the exact-LF broad-suite wording to Windows and explicitly
distinguished bounded native Linux QA. During this review the controller
reported a separate Linux targeted result of 540 passes and one failing old
backup-tree identical-replacement/inode-reuse case. That case is being triaged
separately and is not closed, retested or represented as native green by this
review. Test-port approval does not override any resulting ordinary-updater or
release gate.

## Separate deterministic-inode fixture review — e90320c0

**APPROVED for this narrow fixture-only delta**, with no confirmed scoped
finding. Reviewed the complete two-file diff from
`067de6a31ebc9a3f13b267bf360eba7dd42802a4` to
`e90320c02c40f152546b4b7b7c4bb3548fb4c9dc`, including the entire 168-line
`task-3-backup-tree-inode-triage.md`. The preceding port's test SHA was
`9a85608075ad7a6d70012a6d8caeca9babff2c454cb30b3074c61a83e3c4581f`; final
test SHA is `abb5bb3d0f069be85e23743b388fded7119336aa094f424a2f764282b9c473e5`.

The only test change allocates a same-byte replacement outside the scanned
backup tree while the protected original remains linked. It preserves the
file mode, asserts equal devices and different `(device, inode)` pairs on
POSIX, then uses `os.replace`. Consequently the intended identity mutation
cannot disappear through allocator reuse of a just-freed original inode. It
does not create another entry in the scanned inventory. The existing Linux
rejection, Windows behavior and two-new-archive rejection are unchanged. No
skip, comparator mock, relaxed expectation or production pin modification was
introduced into that test.

Independently read `_backup_tree_record`, `_backup_tree_records_match` and
`verify_backup_tree_update` in the unchanged helper and checked the relevant
deployment README, current capacity plan and Task3 brief. The backup-tree
contract compares stored path/kind/UID/GID/mode/size/hash and, on POSIX, device
and inode. It does not persist an inode generation or ctime/mtime. A byte- and
record-identical recycled generation is therefore still observationally equal.
The README's app-account prohibition against replacing protected archives is
a DAC statement, not owner-event-history monitoring. The newer updater-only
transaction has its own full-signature/recovery rules; neither that transaction
nor its source is being relaxed by this backup-tree fixture change.

The triage explicitly retains both facts: the old test made a nondeterministic
fixture assumption, AND the existing helper does not detect every possible
intervening unlink/recreate event. It distinguishes the installer, which does
not call backup-tree update verification, from the ordinary updater's service
probe, which does. This is the required bounded interpretation, not a universal
replacement-detection claim or hidden change to an acceptance contract.

Independent sensitivity check in ignored
`.pytest_tmp/tree_inode_independent_sensitivity.py` used real new local files
and the actual record/comparator functions. The physical replacement changed
exactly `origin_inode`, not content or any other saved field. With identity
required, the real comparator rejected it; an isolated in-memory comparator
mutation omitting origin checks accepted it. A same-state/same-inode control
was correctly equal, making the old fixture's missing premise explicit;
changed content on the same inode was rejected even without identity checking.
No helper globals or source file were changed. This local record comparison is
not relabelled as an independent native Linux filesystem run.

Fresh independent Windows/Git-Bash server-jobs run: **83 passed, 7 expected
symlink skips in 13.86 s**, exit 0; JUnit is ignored
`.pytest_tmp/tree-inode-independent-final.xml`. Scoped diff whitespace check
passed. Reconfirmed all unchanged product hashes:

- Updater: `4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`.
- Installer: `bdc9c700e646e610a07b22077d4b3d00a592b88e4f241a63f5e011642f7c631c`.
- Backup helper: `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604`.

The controller subsequently reported a fresh final **541 passed, zero skips or
failures in 46.73 s** native targeted trio as UID1000 at this exact e90320c0
archive, archive SHA256
`c70530ec62e73e1aae76f973fea7c69aaa3600ea8746836e7f2c4b706c4426e9`.
That is explicitly controller-run evidence, not an execution by this reviewer
or a full Linux suite. It supersedes the earlier native fixture regression
result for that scoped trio without erasing its historical 540/1 result or
the observed eight-of-eight record-identical recycling limitation. The separate
broad exact-LF Windows run, real production-data acceptance, updater-only
exchange and application/model/deployment verification remain separate claims.
