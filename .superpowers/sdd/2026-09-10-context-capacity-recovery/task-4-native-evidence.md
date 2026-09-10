# Task 4: shared-history native acceptance

## Start and preserved state (10 September 2026)

User explicitly approved the shared validated Tennis basis, without fewer data,
checks or higher limits. The actual task brief is `task-4-brief.md`; predecessor
diagnosis and failed exact b397 D4 remain preserved in
`task-1-fresh-profile-diagnosis-20260910.md` and `task-3-live-rollout-20260910.md`.
This is a capacity repair, not empirical injury/fatigue model approval.

Fresh remote check before implementation:

- repair branch `46380d598e02a5e1d78bb84cad50e4193ac6dcab`;
- GitHub main and actual VPS app `2dd1116b68f3d94e9c24338c6c9dff9b01799221`;
- installed updater `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`, root:root0755;
- app/Caddy active, all seven timers active/enabled and scheduled;
- internal/public HTTP200/ok; known `betboy-tennis.service` remains failed.

Fresh baseline: quality Python, `tests/test_context_runtime_capacity.py
tests/test_context_runtime_tennis_live.py -q -p no:cacheprovider
--basetemp=.pytest_tmp/shared-basis-baseline`: **171 passed, 9 skipped in92.70s**.
Those are existing baseline tests, not new shared-basis proof. No new worktree
was created; the existing linked repair worktree/branch and all WIP are retained.
The skill's Bash artifact scripts initially could not resolve basename/dirname
through their inherited PATH. The tools exist; a later explicit in-Bash PATH
resolved them. The exact Task4 brief was extracted with a read-only PowerShell
read plus `apply_patch`, not a hand-edited second contract. Future review-package
generation uses the repaired process-local PATH, with no global config change.

## New complete backup and isolated context copy

The unchanged reviewed `.pytest_tmp/check_live_task2_backup.py` ran again under
the existing deploy lock. Root executed only pinned stdlib operations/helper;
the online SQLite producer used actual app UID997. No app/venv import as root,
no service operation, live data edit, directory mode repeat or executable swap.

- Stage: `/var/lib/betboy-live-backup-pknwmr9p`.
- Archive: `private-backups/complete.zip`, root-private; **88 databases**.
- Archive SHA256: `30d255a29d7a6c62780d0888b0c343553994d300979140c109d7f78608f1d9f6`.
- Archive bytes:54563584; admission799694848bytes.
- Actual full isolated restore and applicable HMAC verification: **PASS**, exit0.
- Whole chain:28.39user+5.74system=34.13CPU seconds,34.74wall,382712KiB peakRSS.
- Root:betboy0440, single-link DELETE context: `context-current.db`,114929664bytes.
- Context SHA256: `d304c164b44a17cb4e7b90df14f87cbde8dbdd36852d7250911163f967f169b9`.
- The context bytes match the preceding failed-D4 input exactly; backup capture
  freshness is new, not a claim of newly changed observations.
- Installed updater and actual app revision independently unchanged afterward.

This is diagnostic backup/restore evidence. The installer's own final fresh
archive and measured acceptance are still required; no installer/deploy ran.

## Source boundaries

Before implementation the following exact bytes were rechecked; they remain
outside Task4 edits:

| File | SHA256 |
| --- | --- |
| scripts/stage_runtime_databases.py | 1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026 |
| scripts/backup_runtime_databases.py | b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604 |
| deploy/update_server.sh | 4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19 |
| deploy/repair_context_updater.sh | bdc9c700e646e610a07b22077d4b3d00a592b88e4f241a63f5e011642f7c631c |
| context_models/tennis_v3.py | ec6461b87656ecc5731992cc26f0ae69d20e878982706ebe3f1fd0599c43305c |
| context_sources/tennis_status.py | 696302d12822151105d2e2067d22d216d0071f47446799e462744271910b62a4 |
| context_runtime_inventory.py | a4f0f9a2833c5b5cc8eacc2a562cc2d2104a4aafcffe44dd0c7e7851b8ced707 |

## First exact Task4 attempt: native capacity FAILED

The versioned `7b6dcf5a7bd94e6bcd5ef27db3daa921ee9eeadf` archive contains
33747132 bytes, SHA256
`43e804ba34badc69487c1e7026de5e3e24d182563c203eb99fd6069f896492a9`.
It was transferred only to the authorized QA directory and extracted by the
reviewed stdlib-only stager to
`/var/lib/betboy-capacity-code-gstb14_y/source` (802 members, root-owned,
application-unwritable). No app import ran as root.

Exact uninstrumented CLI at application UID997, original AS2GiB/CPU300,
wall600/output1MiB, on the fresh sealed context copy above:

- child exit **-9**, supervisor `child_exit`, **no complete report**;
- CPU **299.992 s**, wall **300.651 s**, peak RSS **321848 KiB**;
- full input hash/stat unchanged, no SQLite companions;
- measured acceptance **FAILED**, not replaced by local unit-test results.

The subsequent `52189a6948338d82c96a7b11a7db989a78f90b18` change bounds
optional maximum-history preparation and adds strict size-only fallback.
It does not establish that this actual 28.4 MB fitting basis now passes CPU300.
Final report-only checkpoint: `fc7f0c78ecdfacf8b93349da970e2ac8ff4f8003`.
Final immutable focused tests: 200 passed, 9 Windows skips in114.95s.

## Diagnostic-only phase tracing

The first trace verified all ten original consumers, with one cold maximum
basis (58.779 CPU s), eight covering hits, two exact hits, one store,
28432021 encoded bytes and zero evictions. Physical observation verification
took28.998 CPU s; original verification including basis preparation83.027 s.
These nested timings must not be added twice.

That trace then failed in the **diagnostic wrapper**, before its first owning
feature invocation: `tennis_features_v3` has a cutoff keyword but no tour
keyword, while the wrapper accessed both together. This is not a product
integrity failure, feature timing or completed verification. Source and input
remained unchanged. The corrected observation-only wrapper checks keyword
presence independently; its new run is recorded separately. Neither trace is
the exact uninstrumented acceptance CLI.

## Acceptance still open

Corrected observation-only `7b6` trace (UID997, same sealed input): physical
observations28.730CPU s; one complete maximum cold basis60.699s; all ten
originals85.727s including that basis. Twenty history requests were reached:
sixteen covering hits, four exact hits, one store,28432021bytes,zero evictions.
Nine snapshot feature calls completed,12.859–14.178CPU s each; the tenth
owning feature call was interrupted by the intentional CPU275 diagnostic
timer. Total276.293CPU/275.674wall,321712KiB peakRSS,input unchanged.
This demonstrates the preserved per-snapshot feature cost, not a complete
run or extrapolated native acceptance. No call was skipped or substituted.

Independent Task4 review (`task-4-review.md`) approved the scoped code with
no actionable product-code findings; it explicitly retains the failed native
gate. Final `fc7f0c7` whole suite is running in the separate clean LF QA
worktree, with a new output name. Earlier b397 test artifacts remain intact.

## Final-source current input: measured PASS

Exact source/report checkpoint`fc7f0c78ecdfacf8b93349da970e2ac8ff4f8003`:
archive33751028bytes,
SHA256`1574c96360410265c76bf1980207d649f27e02125edfb061d3c7aebd1edde70f`,
803members, root-sealed`/var/lib/betboy-capacity-code-b38toqe5/source`.
Reviewed stagerSHA8200a5ca6e14dcaed0fd4c2d120bb3d4119869e3460860982dfac300194eca60;
exact measurement supervisorSHAb2a46f27dd6785d163e7e2cc98c57e4bcb508ca591632ecb0683122a23cee659.

Uninstrumented CLI under the unchanged application UID997 and original limits:
**285.297CPU s /285.388wall s /321584KiB peakRSS**, child exit2, supervisor
exit0, measured profile accepted. Input unchanged and no companions. Returned
counts exactly matched the independent inventory:12artifacts,48307contents,
48307observations,10snapshots,2manifests,0rollbacks. `status=incomplete`,
`verification_level=transport_only`, empirical approvalfalse, with exactly
the same two D1/D3 limitation strings as the predecessor. This is a completed
mechanical replay, not approval of the underlying historical model evidence.

The14.612s wall headroom is narrow. The earlier7b6 CPU300 failure remains valid
evidence for that run; the bounded-preparation fix is not claimed to explain
the timing difference or to guarantee future capacity. Receipt-plus-consumer
growth must still pass, and no repeated best-of timing selection is allowed.

Actual final-source UID997 DAC controls passed: three write/rename/SQL denials,
eight unsafe fixture classes rejected, exact small memory/sealed report parity.
Final source-focused Linux unit suite has been started as ordinary QA UID1000,
never root. The new synthetic working copy is
`/var/lib/betboy-task4-growth-mxqhafsc/synthetic-working/context.db`, copied
byte-for-byte from the sealed current input. It is app-owned0600 under an
app-owned0700 child of a root:betboy0750 stage; no live or old fixture changed.

## Final Linux tests, real DAC/races and D2 compatibility finding

Final fc7 source-focused Linux tests as ordinary UID1000 completed in171.42s:
**199 passed,10 skipped,14196 warnings**, exit0 (supervisor172.218wall s).
QA directory:`/tmp/betboy-context-qa.9xr68INa/shared-history-fc7f0c7-pc33otok`.
The skips are one non-Linux fail-closed test and nine tests requiring controller
root-staged fixtures not passed to ordinary UID1000. They are not counted as
passed. Separate actual UID997 tests on final root-sealed fixtures produced
the three write denials/eight unsafe classes/report parity recorded above.
Seven actual interleaved root-fixture races were also rejected, as UID997:
file/ancestor replacement, bytes mutation, sidecar, file/ancestor mode and
replacement before SQLite open. New fixture stage:
`/var/lib/betboy-capacity-races-kxs3sday`; no old or live file changed.

This test output is NOT pristine. The warning was specifically reproduced
under `-W error::DeprecationWarning -x` in
`test_lazy_membership_does_not_decode_unopened_final`, after29 earlier passes.
The call stack locates the existing SQL in `context_models/dataset.py:169-174`:
repeated `CAST(?1 AS TEXT)` with sequence binding `(opaque,)`. It reaches the
tracked cursor through `_physical_receipt_preflight`; the runtime warns that
this named/sequence binding becomes an error under newer Python. Root verified
the dataset source has no changes in46380d5..fc7. The independent reviewer
classifies this as an Important pre-existing D2 compatibility issue, outside
Task4's frozen owning-source boundary. Do not suppress the warning, rewrite
the owning D2 source silently, or confuse this with a cache regression/current
live D4 failure. A separately authorized D2 repair remains open.

## Synthetic generation preparation

The fully reviewed generator SHA256 is
`3098f8ab9bf069e7a0d57b4d0546424e6642e8b6a4c38e508213731f1f831261`.
It is separately root-sealed as
`/var/lib/betboy-task4-growth-mxqhafsc/generator-3098f8ab.py` (30990bytes),
not inserted into the exact final source archive. Only app UID997 imports and
executes app code. Root sealing uses stdlib byte operations and exact hashes.
The first sealing attempt stopped before writing because its whole stat-tuple
comparison included access time; reading legitimately changed atime. The
corrected sealer retains exact hash/dev/inode/uid/gid/mode/nlink/size/mtime/ctime
checks, excluding only atime. The destination was new/O_EXCL; nothing replaced.

GenerationG1 completed solely in the new app-owned working copy. It uses a
translated coherent21000workload+26098status receipt pool and normal capture,
tour-state/predictor/feature/original/snapshot owners for one added consumer.
Only HTTP response and clock seams are synthetic. Construction took242.662CPU/
241.853wall seconds,682460KiB peakRSS; all source rows were preserved via
explicit-column EXCEPT checks, source bytes unchanged, target integrity_check
ok and no companions. Source/control clocks are intentionally synthetic; no
new fixture receipt is represented as real upstream evidence.

- G1:212172800bytes,13artifacts(11originals+2states),11snapshots,6cutoffs,
  95406contents/observations,2manifests,0rollbacks.
- Last synthetic cutoff2026-09-11T21:35:00Z; translated pool max21:30:00Z.
- Exact targetSHA256`01186c29cb6e31aef5815ae3f937d81401b9e72ddaaa30d934864bcf78daa966`.
- Root copied/sealed a NEW independent
  `/var/lib/betboy-task4-growth-mxqhafsc/generation-1/context.db` root:betboy0440
  with root:betboy0750 ancestors. Working copy unchanged. The stdlib sealer
  SHA256`2d0b2dae494c69cecdd8e5a98e38305722e762969f2030127005630a3f28a4f5`
  uses exact hash/stat/DELETE-header/companion checks, never imports app code.

The exact final uninstrumented D4 G1 benchmark **FAILED** under the unchanged
limits with independently asserted full counts: child-9, supervisorchild_exit,
**300.112CPU/300.233wall seconds**,472488KiB peakRSS,**no report**, input hash/
stat unchanged and no companions. Measurement harness SHA256
`2c64e15dd9b68b204224506e4b275563a9f5c7cb3de46e44ce35214e27ea3acd`.
Fixture generation success is not verification success. G2/G3 were not
constructed or measured after G1 already failed the required release gate;
they remain explicitly unproven, not assumed passes. The shared-basis code is
insufficient for the requested growth profile despite passing today's input.

Receipt AND consumer growth acceptance, D2 compatibility repair and the final
release chain remain open. All executed native processes completed; no
delayed rollout, updater replacement or data cleanup was scheduled.
Old growth fixture passes held four consumers fixed and cannot be used as
proof of ten/future consumer scaling. No resource limits are changed.

## Final immutable full regression and unchanged production

Separate clean LF QA worktree remained detached at exactfc7f0c7 throughout
the full run and is still tracked-clean afterward. Command:
`quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider
--basetemp=.pytest_tmp/final-fc7f0c7-full
--junitxml=.pytest_tmp/final-fc7f0c7-full.xml`.
**6926 passed,30 skipped,97 subtests passed in1631.90s**, exit0.
XML contains7053entries including subtests,0failures,0errors,30skips,
1631.750s. XML SHA256
`9ee9e3a322e6b15147aae44702b2398fdd8b593832d9a30da6843facefffde44`.
This is the final product-source full run, not the older b397 evidence or a
sum of earlier partial runs. It does not erase the separately observed native
SQLite warning or establish native growth acceptance.

Fresh read-only VPS snapshot22:23UTC: appHEAD remains
`2dd1116b68f3d94e9c24338c6c9dff9b01799221`, installed updater remains
`74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`
root:root0755/134237bytes. App/Caddy active/enabled; seven timers active,
waiting, enabled and have concrete next times. Internal/public HTTP200/ok.
The known`betboy-tennis.service` failed state remains reported, not reset or
claimed fixed. No main push/updater swap/app deployment occurred.
