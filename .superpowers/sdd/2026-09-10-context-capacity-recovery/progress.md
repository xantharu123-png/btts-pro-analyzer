# Context capacity repair execution ledger

Base: `82ca31d4340ed2dabd2a9812eb6bcadfbd757a5a`; branch `codex/context-capacity-recovery-20260910`.
User approved the one-time updater-only replacement with independent review, fresh backup and rollback. No data deletion or unrelated deployment is authorized by this repair.

## Current checkpoint — 10 September 2026, 21:05 UTC: RELEASE HOLD

The explicitly approved12-directory mode procedure completed at20:35:36UTC;
all original UID/GID/inodes preserved, original metadata durably saved. Real
UID997 can still write all12 directories; UID995 with app supplementary group
cannot. Fresh full88DB backup/actual isolated restore/HMAC passed in42.60s.
See `task-3-live-rollout-20260910.md` for exact hashes/stages and evidence.

BUT the uninstrumented b397 CLI on the current114,929,664-byte sealed input
failed at300.067CPU/300.163wall seconds, child-9, no report,362,972KiBRSS.
Input remained unchanged. Main and VPS remain2dd1116 with old updater74b1c4b1;
no main push, exchange, deployment or resource-limit change took place.
The actual data now has10 originals/snapshots at5 cutoffs (previously4 at2),
despite only810 additional receipts. Phase tracing confirms repeated62–68CPU
second cold history builds, with28,432,021bytes per full cached copy. The
old synthetic growth fixture did not grow the number of replay consumers.

Independent final review explicitly says RELEASE HOLD. Shared-history-basis
architecture is proposed for discussion, not implemented. Its permission
question is pending. The whole exact-b397 Windows suite has now completed:
6897 passed,30 skipped,97 subtests passed in1704.03s, zero failures/errors;
tracked QA clean. XML SHA1596c19324d7535c4fd057a362f4aefa3cc5f4fe38b4b7956105bc7b3fef5fbe.
This is not a substitute for the failed real profile. The bounded trace
confirmed three complete cold builds, four evictions and a fourth cold
rebuild at original8; no snapshot feature call was reached. All native QA
and this Windows run are finished. Stagehelper/A0/P4b3/Cricket and all existing
histories/outputs remain untouched.

## Approved continuation — 10 September 2026, 20:27 UTC

The user explicitly answered yes to the exact twelve directory mode changes
0775 to 0755 documented in `directory-mode-preflight-20260910.md`. Preserve
owners, groups, contents, services, keys and databases, and durably save the
original metadata before changing a mode. The exact reviewed procedure SHA
`8be3d721660d7438a251628ea58c3e61a64f760d96d69fee4d6a82d22ebfe304`
is unchanged. Fresh read-only health confirms the old production HEAD/updater,
HTTP200/ok internally and publicly, seven active timers, and the still-failed
tennis service. Actual mode repair, fresh backup/restore and rollout results
must be recorded separately below; user approval alone is not execution.

## Previous checkpoint — 10 September 2026, 19:45 UTC

Code `4205db82bb234f0aa07a43510db0576811556090`, installer SHA
`bdc9c700e646e610a07b22077d4b3d00a592b88e4f241a63f5e011642f7c631c`.
Task1 current/three-growth native profiles and Task2 code/native controls passed;
largest-growth headroom remains about one second, not a future-growth promise.
Task3 independently rereviewed: final451 Linux tests passed; actual isolated
transaction/DAC/lock/SIGTERM/SIGKILL recovery and unchanged CPU300/wall600+10,
AS/output/RSS boundaries passed. Whole final production-check function now
passes read-only with the real historical complete marker and empty env.
See `task-3-native-evidence-20260910.md` for failures, fixes, hashes and limits.

Production remains `2dd1116` with installed updater `74b1c4b1...`; no repair
exchange, application deployment, marker/key/database edit or mode correction.
The user approved versioned QA archive transfer. Separate permission to change
exactly12 existing0775 directories to0755 is still pending; the complete real
backup producer fails closed until that boundary is resolved. Fresh full real
backup/restore/HMAC, measured exact-target D4 and final rollout remain open.
The broad exact-LF e2 run ended with4 failed,6877 passed,30 skipped and97
subtests passed in1647.97s. Its four old server-job contracts were ported with
actual phase/launcher/enumerator/device and error-propagation controls; the
independent review's additional test gap was closed. A later native old fixture
failure was proven to reuse a freed inode; e903 makes the intended distinct
identity deterministic, preserving the record-identical recycling limitation.
Final test-only freeze `e90320c`: independent APPROVED, fresh native Linux trio
541 passed / 0 skips in 46.73s. All product/helper bytes remain 4205/6ba.
The full clean exact-LF Windows suite at e74 completed: **6897 passed,
30 skipped, 97 subtests passed in 1607.26s**, no failures/errors. Every later
delta is tests/docs only; product code is identical. Root then advanced the
clean QA worktree to e903 and reran its only changed test file: **83 passed,
7 Windows skips in 14.28s**. The full suite was not rerun at e903; do not
mislabel the two executions. Both QA checkpoints remained tracked-clean.
See the native evidence and regression/triage reports for exact XML hashes,
preserved failures and explicit identity-generation limits.

Fresh read-only server check at 19:40–19:41 UTC: app remains `2dd1116`,
installed updater remains `74b1c4b1...`; app/Caddy and all seven timers are
active/enabled. Internal/public health, including a separate Windows client
request, returns HTTP200/ok. The known `betboy-tennis.service` failed state
remains visible; it was not cleared or represented as fixed. No service,
timer, application, key, marker, database or directory mode was changed.
Cricket and unfinished source/empirical model work remain outside this repair.

## Earlier chronological evidence (superseded where noted above)

- Task 1: initial code `b333c3c`; lifecycle fix `41067c0`, report `3967778`. Independent fix re-review APPROVED: stale Mapping revival is closed. Final targeted fix checks124 passed/12 skipped,22lifecycle cases and1actual protected-final guard. Real-data performance is still a separate HOLD; no release acceptance claimed.
- Task 2: waiting for Task 1 review; streaming normal updater and pre-downtime full capacity proof.
- Task 3: waiting for Tasks 1-2; narrowly pinned repair installer, Linux real-backup evidence and controlled release.
- Baseline: 332 passed / 3 skipped, 45.69s, exit 0; `.pytest_tmp/capacity-baseline-01.xml`.
- Production unchanged by repair so far. Existing main/VPS release `2dd1116`; installed updater SHA `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`.
- Frozen A0 and P4b3 branches, protected stage helper, existing keys, account data and all historical receipts remain out of scope.
- Fresh real backup: `betboy-sqlite-20260910T140039Z.zip`, 88 verified / 0 pruned. Old-reader diagnostic against isolated 99.375-MiB copy completed in173.319s, peak836908KiB; current inventory6artifacts/4snapshots/47497receipts. See `live-capacity-evidence-20260910.md`.
- Provisional pre-fix Task1 native BetBoy-user DAC checks:3write/rename/SQLite denials;8unsafe-fixture classes rejected; small memory/sealed reports equal. The bounded real-copy new-reader attempt ended without a final verification report (supervisor exit1). Targeted first-history profiling completed with an intentional20CPU-second diagnostic stop: repeated owning decoding/selection dominates. Four originals and four snapshots share two ATP cutoffs. A bounded reuse proposal is pending; this is not a successful capacity run. Input and installed updater hashes remain unchanged.
- Task2 integration preflight is complete and its narrow path/phase/legacy/resource clarifications are incorporated into the plan. Helpers/units remain unchanged.
- Task1 bounded immutable cachec3bac37 completed the exact real-copy CLI in229.188s/350844KiB, with complete unchanged counts/limitations. Schema-lifetime followup7d6595e/4fad098 is independentlyAPPROVED. Corrected-source nativeDAC3denials/8unsafeclasses and7actual interleaved filesystem changes all pass. Full corrected-source/growthcapacity gate remains open; largestfixture benchmark running.
- Task2 fresh implementer has completed read-only preparation and is authorized for REDtests only. No updater production edits yet. Task1 further performance investigations remain read-only while that test writer is active.
- Largest exact4fad098growth run failed at300.040CPU seconds (child-9),312792KiBpeak, noreport; sealed input unchanged. Task1 validation-owned cutoff-iteration refinement is approved inplan; do notraisebudgets. Task2RED-only slice624280d is committed and writerpaused; no updater implementation yet. Correctness/nativeDAC are distinct from this opencapacitygate.
- Current checkpoint: Task1 cutoff refinement8249c288/report73e6abd independentlyAPPROVED (20targeted independent pass;213focused author pass/12skips). Native generation3 still fails at299.949CPU/301.154wall/352636KiBRSS,child-9,noreport,input unchanged. Further Task1 work is read-only phase/cache diagnosis; capacity remainsHOLD.
- Task2 is now the sole implementation writer; streaming/phase-bound before-downtime preflight is in progress, not yet coherent/committed. Task3 read-only preparation complete, no edits or VPS actions. Production and installed updater remain unchanged.
- Task2 coherent **incomplete** checkpoint43bfd0d:262hooktests pass,syntax/diffclean. Cross-phase config binding and further producer/WAL/identity/resource/recovery coverage remainopen. Writer relinquished for Task1 covering-cache refinement; no Task2completion or deploymentclaim.
- Third Task1 refinement is specified inplan after exact current-copy phase/cache measurement and verified later-first original order. A completed later same-tour selection can provide its exact earlier clock-prefix under unchanged inventory proof; ownerfeatures/allphysicalchecks/budgets remainunchanged. Implementation and independent/nativeacceptance are pending.
- Third Task1code4db6118/reportb389b2c:234adjacentpass/12skips,21newcoveringcases, independentreview/nativegreatestgrowthrunning. Task2regainedsolewriter for remainingimplementation/REDcoverage+4independentcheckpointfindings. Linuxcheckpoint261pass/1unitDAC-portabilityfail; no productionmutation.
- Thirdrefinement correctnessindependentlyAPPROVED21freshcases, but4dblargestCLI stillHOLD at300.342CPU/301.451wall/354292KiBRSS,child-9,noreport,inputunchanged. Directgrowthphase/profilediagnosiscomplete:physical147.192s,onecold76.698s,covering4.202s; additional query-traversal proposalread-only. No budget/source/math changes or productiondeployment.
- Task2followupcodebdd5731/report23dac3b:313focusedhooktests pass in39.24s,syntax/diffclean; reviewer-candidate REDs anddirectWAL/recoverycoverage recorded. Independent/nativeacceptanceremainopen; solewriterrelinquished. FourthTask1traversalrefinement nowapprovedinplan withallownerchecks/LEFTJOIN/protectedproof preserved, implementationnext.
- FourthTask1 code c4e20e0/report0fbd757:264adjacentpass/12skips, actual final guard once; independent APPROVED with30streamed+20cutoff cases. Exact largest native CLI running, not yet accepted. No owner/math/cache/schema/budget changes.
- Task2 bdd5731 exact Linux QA:313passed in37.60s (38.317supervised), normal SSH uid1000, no production change. Final independent review nevertheless found two Important discovery groups (silent traversal errors, case-sensitive DB omissions); native real uid997/EACCES corroboration recorded in task-2-final-discovery-review.md. R2 regained sole implementation writer for scoped fixes only. Task3 remains preparation-only; production main/updater unchanged.
- Task1 c4 greatest/current/generation1 exactCLI profiles PASS with full unchanged reports and input. Largest298.846wall has verylittleheadroom; generation2stillrunning, nofuturegrowthguarantee. FinalreaderDAC3/8 and7nativeinterleavings pass.
- Task2 c2cb1c9/reportffce3c2:332focusedpass; nativefullchain/actualHMACnegative/mixedcase/OSDAC/retainedFD/EACCES PASS. Independentreview stillidentified Unicodecasefold-vs-find parityP2; R2aloneimplementing principledcommonenumeration. FixedlauncheractualASexhaustion/output/rolechecks separatelyPASS. No productionmutation.
- Task3 RED-only slice is prepared:35expectedmissing-installerfailures, no errors/skips; testfileandreport only, no installer. Writer relinquished while Task2 finalparityisclosed. Controllerreadtest/reportfully; Linuxunitmetadata portabiltynote delivered for laterwire-up. Do notmistakeREDcollectionforimplementation/recoveryacceptance.
- Task1 native current+all3growthprofiles nowcompletePASS atc4; generation2finished256.521CPU/256.711wall/348440KiB,fullreport/inputunchanged. Largestmarginremainsexplicit. Task2Unicodecode690dd16/report0541080:339focusedGREEN,independent/nativefinalchecksnext,writerreturned. Task3stillRED-only,notimplemented.
- Task2 final code `6ba2c68` / report `9e97f2b`: 340 local tests passed in48.90s; independent combined review APPROVED with14 fresh targeted tests and actual prior-version RED/current GREEN metadata reproduction. Native690 full-chain Unicode controls and339 Linux tests passed. Exact6ba native confirmation remains pending an explicit QA-upload approval after the approval reviewer rejected that transfer; no workaround attempted. See `task-2-final-independent-review.md`.
- Task3 now has the sole implementation writer. Its35-test RED slice was committed in `a435c65`; the installer, additional behavioral tests and independent release review are in progress. Required existing Task2 stdlib seams may be copied mechanically with byte-equality regression checks, not runtime-sourced from an updater main. Root performs only separate controller documentation/ignored diagnostics and will not stage or commit while that writer is active. Production remains unchanged.
- Task2 exact6ba native gate subsequently PASS: user approved QA archive transfer,340Linux tests passed in39.49s, actual root/app/backup metadata restoration and full synthetic archive/HMAC/Unicode/DAC/FD/EACCES controls repeated successfully. Fresh real producer then correctly refused twelve existing0775 directories; no archive acceptance and no source mutation. Separate extra mode-only authority is pending; no unsafe g+w exception was introduced. See `directory-mode-preflight-20260910.md`.
- Task3 review checkpoint `ce1021ee1f80e68b4a35c29e85fb70b857b27fa0`:409targeted passed/1Windows-flock skip in58.42s; installer and report committed, not pushed/deployed at this checkpoint. Author relinquished writer; independent full review and native tests are in progress. Frozen separate LF QA worktree `context-capacity-final-qa-20260910` now points toce1021e, no full-suite result yet. Current installer SHA8476a5a9a4956245ddb4026f5aff9bb1c8db980859d34fc129a28d453bf415f7. Whole-plan/model-source work remains separate and incomplete.
