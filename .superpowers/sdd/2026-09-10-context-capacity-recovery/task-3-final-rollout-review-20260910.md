# Task 3 — independent final rollout-chain review

10 September 2026. Reviewed checkout:
`b39789d54adf8c5c836a50782e276d3810349979`.

## Current verdict — release HOLD, source/diagnostic scope only approved

**RELEASE HOLD: the fresh exact-b397 D4 run on the current 114,929,664-byte
sealed input failed at the CPU300 boundary and produced no report. No main
push, updater installation or application deployment is permitted by this
review.** The controller confirms none of those release actions occurred.

The earlier bounded GO is superseded. No new scoped source defect was found
by this review, and the source/diagnostic-scope approvals remain valid only
for those scopes. They do not establish actual current-data capacity. The
fresh full suite is a separate gate; even a successful result cannot override
this real profile failure. Details and exact measurements are recorded below.

The twelve-directory preparation and the subsequent real backup diagnostic
are now reported successful by the controller. They close the previously
observed source-directory admission failure for that run. They do not replace
the installer's new full archive, exact-target measured D4, continuity checks
or durable transaction evidence. Any failure of those steps remains a real
stop; neither a prior successful backup nor this review overrides it.

The previously reviewed deployment sequence below is suspended until the
actual capacity failure is resolved and fresh applicable release evidence is
accepted. No limit increase, permission exception, helper replacement, model
contract change or additional directory repair is proposed by this review.

## Independently verified local inputs

Read the current capacity-recovery plan, prior independent installer and
regression reports, complete native evidence report, directory-preflight
record, both controller procedures and relevant installer/deployment paths.
Current file SHA256 values were recalculated:

| File | SHA256 |
| --- | --- |
| `deploy/repair_context_updater.sh` | `bdc9c700e646e610a07b22077d4b3d00a592b88e4f241a63f5e011642f7c631c` |
| `deploy/update_server.sh` | `4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19` |
| `scripts/backup_runtime_databases.py` | `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604` |
| `.pytest_tmp/repair_live_directory_modes.py` | `8be3d721660d7438a251628ea58c3e61a64f760d96d69fee4d6a82d22ebfe304` |
| `.pytest_tmp/check_live_task2_backup.py` | `926f9f9171dedf80445a34126400de9dc51454d1953f599578cb091e83520e38` |

Git comparison confirms that installer/updater/backup-helper bytes remain
unchanged from 4205 to b397. The e74-to-b397 changes are confined to the
already reviewed test file and documentation. The older full Windows result
6897 passed / 30 skipped / 97 subtests belongs to e74, not b397. The controller's
541-test native Linux result belongs to the e903 three-file regression run,
not a complete Linux application suite. Prior closed findings are not reopened
solely because these hashes or the release document commit are unchanged.

## Exact twelve-directory procedure

The separate user grant is limited to the documented twelve existing
directories, 0775 to 0755, with ownership and contents preserved. The pinned
procedure checks all targets before changing any, holds the deploy lock and
open no-follow directory descriptors, durably publishes original metadata,
and validates identity before/after each fchmod. Operational rollback only
touches its recognized original objects. Unknown replacement inodes are
preserved and reported. It is not a recursive chmod/chown operation.

This twelve-object change is not an all-or-nothing transaction across power
loss or SIGKILL: a durable nonterminal journal requires inspection/recovery of
the exact recorded targets. Do not delete it or blindly rerun the old-state
procedure. A completed run must not be repeated as though all modes were still
0775. No wider signal-recovery or physical-power-cut claim is made.

Controller-reported actual result: **PASS**, all twelve UID/GID/inodes retained,
with durable journal
`/var/lib/betboy-directory-mode-repair-fi_69l74/metadata.json`.
This reviewer did not perform a second VPS observation or any chmod.

## Fresh real backup diagnostic — accepted only as diagnostic evidence

The pinned diagnostic invokes the actual reviewed online producer, isolated
restore/HMAC verifier and complete source enumeration under the deploy lock.
Root uses pinned standard-library file/transport operations; application
backup production runs through the fixed lower-privilege launcher. It checks
the old production HEAD and installed-updater identity again afterward.
Its source-revision label is 6ba2c68; its actually used updater and helper bytes
are pinned. It does not execute D4 or claim a final release payload verification.

Controller-reported real result, independently read as evidence rather than
executed again by this reviewer:

- Archive:
  `/var/lib/betboy-live-backup-j0co13x8/private-backups/complete.zip`.
- All 88 databases; full manifest/isolated restore/HMAC completed with exit 0.
- Archive 54,550,967 bytes; SHA256
  `21bd2b529cf31451f336d1821ab00578ef8ff54beb377ca3494911edcfac39a4`.
- Sealed context copy 114,929,664 bytes; SHA256
  `d304c164b44a17cb4e7b90df14f87cbde8dbdd36852d7250911163f967f169b9`.
- Whole diagnostic chain: 41.48 CPU seconds, 42.60 wall seconds,
  382,684 KiB peak RSS. These are **not D4 measurements**.
- Application/main still 2dd1116; installed updater still the pinned old
  74b1c4b1 bytes at this checkpoint. No installer exchange/application action.

Do not copy these diagnostic acceptance flags into an installer receipt. The
actual installer must produce and authenticate its own then-current archive
and bind its own exact target, sealed input and report/resource measurements.

## Fresh b397 diagnostic and planned installer source

After the backup completed, the controller supplied the exact b397 code
archive SHA256
`fd54700b0dfd0f32dff4735f6444e43fa2223e39b3e2c04686441c2f9c078972`,
798 members, staged at `/var/lib/betboy-capacity-code-hy_rb2ux/source`.
Those archive/staging facts are controller evidence, not a second SSH run by
this reviewer.

Read the complete `.pytest_tmp/measure_fresh_b397_capacity.py` and its previous
`measure_exact_capacity_cli.py` implementation; independently confirmed the
new diagnostic SHA256
`14baebc60b3aa5702fc2e5bd6f3498d5b0d585bf8bfa01dd51b92b977e8dfb8f`.
**Scoped diagnostic review APPROVED** for the stated UID997 invocation with
`-I -B`, without Python optimization, and the independently archive-verified
staged source. Its assertions bind the exact b397 revision label, fresh sealed
input path/hash and root-owned, nonwritable ancestors. Source revision/bytes
are independently bound by the controller's stager and exact invocation, not
by a new source-hash validator inside this diagnostic.

The diagnostic supervisor also runs as UID997. Its added physical row counts
use only the fixed sealed copy, SQLite `mode=ro&immutable=1` and `query_only`;
no live SQLite path or application import by root is introduced. Its child is
the actual unchanged CLI, with the existing AS/CPU/wall/output boundaries.
Acceptance compares the complete reported counts to the independently read
physical counts, checks unchanged input/no companions, the exact two existing
transport-only limitations and explicit absence of empirical approval.
Reported child resource measurements do not include the supervisor's prior
physical-count query. This remains a diagnostic, not an installer receipt or
a generalized descendant/signal-supervisor verification.

The proposed actual installer path is
`/var/lib/betboy-capacity-code-hy_rb2ux/source/deploy/repair_context_updater.sh`.
The controller reports root:betboy0440 and root-owned nonwritable ancestors.
This is compatible with the unchanged self guard (`repair_context_updater.sh:2037`):
it requires a nonempty, single-link, root-owned, non-group/world-writable file
with no symlink traversal, not an executable bit when invoked through Bash.
The exact installer SHA must still be rechecked immediately before invocation.
The controller's intended target is b397 for both installer and later ordinary
deployment, after b397 is the verified main tip; post-release evidence commits
must not silently change either invocation's target.

### Subsequent real current-data result — failed; release stopped

The controller subsequently reported the completed diagnostic outcome for
exact `b39789d54adf8c5c836a50782e276d3810349979`:

- Sealed input: 114,929,664 bytes; SHA256
  `d304c164b44a17cb4e7b90df14f87cbde8dbdd36852d7250911163f967f169b9`.
- Child exit **-9**, after **300.067 CPU seconds / 300.163 wall seconds**.
- Peak RSS **362,972 KiB**.
- **No D4 report**; the measured profile is rejected.
- Input SHA and full metadata identity unchanged; no SQLite companions.

This is a real current-data capacity failure, not a passing limited report,
an empirical/model approval, or an issue to bypass using the earlier smaller
104-MB or synthetic-growth passes. Source code/installer pins remain unchanged
at the previously reviewed implementation. Main and production remain old;
the controller performed no main push, updater exchange or app deployment.
The CPU/resource limits remain unchanged. Investigation and any narrowly
approved remediation must precede a new exact-source/current-data acceptance.
The b397 invocation described above was a plan, not an executed release, and
is now suspended by this failed profile.

## Directory permissions during the later ordinary deployment

`apply_trusted_payload`, `deploy/update_server.sh:886`, only replaces tracked
files. Existing real parent directories are retained without chmod; new
parents are created with a non-group-writable requested mode. The following
Git `update-ref`/`read-tree` operations update repository metadata, not the
working-tree directories. There is no broad checkout/copy of directory modes.

An independent local execution of the **unchanged SHA-pinned Python payload
body** exercised all twelve existing directory paths: 12 tracked files
replaced, 12 synthetic runtime files retained, all twelve original directory
identities/modes retained, zero directory chmod calls, obsolete tracked file
removed. Ignored reproducible harness:
`.pytest_tmp/check_rollout_directory_preservation.py`; quality Python,
`-I -B`, exit 0. This Windows execution proves the code path and absence of
directory chmod calls; it is not native Linux DAC evidence.
Reproduction SHA256:
`100ac5e7bd863cec8d9bdea334e010e878f9dbfd4b7bacb82679b314e22340ba`.

Importantly, ordinary deployment then calls the existing
`prepare_backup_storage_and_sources` (`update_server.sh:2955`), which sets
database ancestors to **0750** using `chmod u=rwx,g=rx,o=`. Consequently the
correct post-deployment expectation is preserved 0755 where untouched, or
0750 where this existing backup-source policy applies, **never a return to
0775**. The backup identity includes its supplementary betboy group when DAC
is subsequently verified. Do not claim all twelve must remain numerically
0755, and do not issue another speculative chmod after deployment.

## Required exact release order

**Suspended by the current-data CPU300 failure above.** These are the reviewed
ordering requirements after the blocker has been resolved, not authorization
to publish or deploy the failed b397 capacity profile.

1. Finish and record the fresh b397 frozen full-suite result. Freeze the final
   reviewed integration commit and publish it to the verified trusted
   repository's main branch. Verify the actual remote 40-hex tip and unchanged
   product hashes; a later documentation commit is a different target identity.
2. Place/verify the exact LF bdc9 installer in its approved root-owned private
   stage with trusted ancestors. Use the documented clean-environment Bash
   invocation and exactly two arguments: that final 40-hex main commit and
   updater digest 4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19.
   Do not invent or reuse an unverified stage path.
3. The unchanged installer first obtains the deploy lock and resolves any
   durable recovery state. `fetch_repair_source:2210` accepts only the fixed
   repository's **current main tip equal to the requested commit**. As long as
   main is still 2dd1116, passing feature b397 cannot succeed. Keep this check.
4. Let its own production/key/config/marker/helper/DAC continuity and complete
   capacity inventory pass, then its newly produced full archive and actual
   restore/HMAC, then exact-target D4 as betboy on the sealed archive copy.
   Require bound report/input/target/digest evidence, positive RSS below 1 GiB
   and CPU/wall below 300 seconds. Preserve the 2 GiB AS / 300 CPU / 600 wall
   plus grace / 1 MiB output enforcement unchanged. Exit 2 is acceptable only
   with the existing validated limitation report, never for a resource error.
5. Only then allow its candidate/continuity/receipt checks and durable atomic
   updater exchange. Verify root:root0755, one link, exact 4b814 digest and
   complete journal/old-copy/backup evidence. Confirm the app is still 2dd1116
   and no service/timer/application deployment was performed by the installer.
6. Separately invoke the now verified ordinary installed updater for the same
   exact reviewed release. Its own online and quiesced backup/context checks,
   controlled downtime, tracked-payload application, DAC checks, root-helper
   installation, marker handling, health checks and rollback remain in force.
   Keep the existing complete historical marker contract; its target is not
   required to be rewritten to every later app HEAD.
7. Independently verify server/app HEAD, installed source/helper identities,
   complete marker, app/Caddy, all seven active/enabled/planned timers, worker
   failures and internal/public health. Explicitly retain the known failed
   tennis-service state until an actual successful relevant run proves it
   resolved. Timer activity alone does not establish this. Preserve evidence
   and record exact directory post-modes without another speculative repair.

## Remaining limits and scope

The historical largest synthetic growth profile had about one second of wall
headroom. It is not a future-growth or busy-server guarantee; the new real
target preflight is mandatory. The pinned backup-tree comparator's documented
record-identical inode-generation blind spot remains unchanged and must not be
relabelled as universal historical replacement detection.

The capacity repair is not completion of the five-sport injury/fatigue models,
empirical validation, A0 or P4b3; Cricket remains excluded. No claim about more
profitable bets, complete model quality or changed UX follows from this review.

This reviewer made no product/test edit, Git index/HEAD operation, commit,
push, SSH, service action or production mutation. Only this report and the
ignored local payload-path reproduction were added; controller WIP was kept.
