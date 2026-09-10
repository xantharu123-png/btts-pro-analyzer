# Capacity repair: live backup and baseline evidence

10 September 2026; controller-operated evidence, not production remediation.

## Fresh actual state

- App checkout reread as `betboy`: `2dd1116b68f3d94e9c24338c6c9dff9b01799221`.
- Installed updater SHA256 remains `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`.
- Correct actual app unit is `betboy-app.service`, active/running. Initial query of nonexistent `betboy.service` was not evidence of an app outage; no service was changed to correct the query.
- Root Git query correctly hit ownership protection; repeated as the owning app user, without adding a safe.directory exception.
- Backup unit exact SHA256 `922352a5d3c883cc671da419c5d3fa589cbe9cd025f32d4c4d9f7b6a9648edb8`, no drop-ins.
- Installed trusted backup/helper SHA256s match fresh LF worktree: backup `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604`, stage `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`, marker `f22065efc2f321e4eaff20d9d8d006332ffe3a99c26931fc329dab7b8d62458b`.
- Existing Tennis service remains failed from the earlier provider/partial run. This is not repaired by healthy timers or a database-reader change.

## Fresh backup

The inactive unchanged `betboy-backup.service` was started once, nonblocking. Archive inventory was checked first: no archive eligible for its 14-day pruning policy was present.

- Archive: `/var/backups/betboy/betboy-sqlite-20260910T140039Z.zip`.
- SHA256: `0575541dde669d33c5284a3d98096326b49b44b8d3ea1eaf7aba9419b9e2c784`.
- Service exit 0/success; **88 databases staged, 88 verified, 0 pruned**.
- Existing frozen `verify_archive` actually extracts every database into an isolated temporary directory, checks SQLite and authenticates applicable Challenge ledgers with the separately archived key/marker. It does not substitute for D4 owning-context replay.
- Service reported 30.718 CPU seconds, 755.0M peak memory, 0B swap peak.
- Normal scheduled archives contain no `MANIFEST.json`; updater preupdate archives have one. The first preparation probe rejected the absent manifest before any stage or source mutation. Subsequent preparation pinned the exact complete archive hash instead. Do not conflate the two formats.

Only `runtime_state/context_models.db` was copied for benchmarking. Key and marker remained solely in the protected archive and were never displayed, copied to the model test stage, or downloaded.

## Isolated context copy

- Stage `/var/lib/betboy-capacity-preflight-fhlfmnkd`, root:betboy0750 beneath checked root-owned, non-app-writable ancestors.
- File `context_models.db`: root:betboy0440, one hard link, **104,202,240 bytes** (99.375 MiB).
- SHA256 `0a7103150e5724160ca789b59b6691eb9e274df0f8c090658217c6f16e926ae5`.
- ZIP member streamed with CRC validation, whole-archive hash pinned, FD/path metadata compared, output fsynced; SQLite header DELETE `[1,1]` and no companions.
- Only new private test artifacts were created. No live database, installed executable, service configuration or account state changed.

## Old-reader diagnostic baseline

Ran as `betboy`, never root, with the unchanged installed app's verifier. **Only this short-lived diagnostic process** set its in-memory input cap to 128 MiB to measure behavior beyond the existing 64-MiB production guard. This is not a fix, bypassed release, or approved production limit.

Process bounds: address space 2 GiB, CPU 300 seconds, timeout 360 seconds plus 10-second termination grace; numerical-library threads set to one, nice 10, isolated Python `-I -B`, sanitized environment. App health remained `ok` during and after the run.

| Evidence | Actual result |
| --- | --- |
| Verification completed | true |
| Artifacts / manifests | 6 / 2 |
| Contents / observations | 47,497 / 47,497 |
| Snapshots / rollbacks | 4 / 0 |
| Wall time | 173.319 seconds |
| CPU time | 173.251 seconds |
| Peak RSS | 836,908 KiB (about 817 MiB) |
| Input SHA/stat unchanged | true / true |
| New SQLite companions | none |

Report remained `transport_only`, with exactly `d1-original-replay-context-unavailable` and `d3-owning-source-feature-replay-unavailable`. D2 approval/case/dataset/evaluation/experiment/fit lists were empty. This is expected evidence of still-open empirical/source work, not a corruption claim and not model approval.

The new reader must reproduce these current counts and limitations, not the older four-artifact/two-snapshot inventory. Multiple-growth-generation, new-reader, Linux DAC/race, full-release and one-time-installer evidence are still pending. Production updater and app are unchanged.

Local diagnostic source files live under this worktree's ignored `.pytest_tmp/` and are preserved: `inventory_real_context_archive.py`, `prepare_real_context_capacity.py`, `measure_original_context_reader.py`. They are one-use diagnostics, not installed helpers.

## Provisional Task1 native test, before lifecycle fix

Exact Git archive of `59b001d`:102,256,640bytes, SHA256 `2b19493b1763b706ecba95ebb0a80f995698699b6b77d19ae2cffdeae8680746`. It was transferred into the existing private QA folder, then standard-library-only root byte staging produced `/var/lib/betboy-capacity-code-p_e43nuz/source` (765 validated members). No app/venv/model code was imported as root. Original archives and source remained unchanged; no existing path was overwritten.

A generated 24,576-byte synthetic fixture (SHA256 `ee932b44a72687ca85ce72329c8c8f4cd004f305b19da9e17b2e9171fa2269b3`) was prepared into eight private test variants at `/var/lib/betboy-capacity-code-p_e43nuz/fixtures`. The original Windows seed's owner-only ACL prevented elevated scp from reading it; an identical new transfer copy was used instead, without relaxing the original ACL.

As actual **betboy uid997**, not root, direct checks passed:

- OS overwrite denied, OS rename denied, SQLite DELETE denied:3.
- Hardlink, symlink, app-owned file, writable file mode, writable ancestor, companion, WAL header and over-budget input rejected:8.
- Positive 24-KiB memory and sealed-file reports were exactly equal.

These are direct native checks, not a claim that skipped Windows tests became Linux pytest passes. They do not include physical concurrent replacement races.

The same child then attempted the complete99.375-MiB real-copy replay with the new explicit sealed reader. At1:44 elapsed it used279,880KiB RSS; at4:36 it used263,744KiB, both approximately100%CPU. **The attempt ended without a final verification JSON; the command supervisor surfaced exit1.** The intended limits were2GiB AS/300CPU seconds/360wall seconds. The exit alone does not identify its exact terminating signal; do not call this a successful verification or an exact peak-RSS result. It clearly leaves runtime admission unproven.

Afterward the test input SHA256 was rechecked unchanged as `0a7103150e5724160ca789b59b6691eb9e274df0f8c090658217c6f16e926ae5`, root:betboy0440/one link/104202240bytes. Installed updater SHA remains74b1c4b1..., app health`ok`. No repair was installed.

The independent lifecycle defect in this pre-fix source was separately corrected by41067c0/3967778 and independently accepted. That does not explain away or close the observed performance problem.

## Completed targeted performance diagnosis

`profile_first_context_history.py` ran as betboy against the preserved pre-fix source and sealed real copy. It deliberately stopped after20CPU seconds of profiling the first history. This is a diagnostic, not a verification PASS. Complete diagnostic elapsed61.791s, peak189476KiB; schema0.493s, artifact types3.588s, manifests0.001s, physical observations34.376s, original phase started41.046s.

The first-history20.014s profile recorded12542544calls (12051088primitive). Of8615lazy receipt lookups,8614 reached owning Tennis selection and8541 typed selected-receipt validation. Cumulative times: selection11.543s, selected validation11.226s, observation normalization10.083s, lazy receipt lookup8.084s, receipt decode7.377s. These overlap and must not be added. Canonical serialization112375calls consumed4.764s cumulative.

The measured hot path is repeated whole-inventory owning decode and typed selection for original and snapshot replays. No check was removed and no process budget was increased in response. A bounded reuse proposal is under review before implementation.

Separate read-only structural inventory as betboy confirmed50880457physical content bytes. All four originals are ATP: two at2026-09-10T10:00:10.922492Z andtwo at2026-09-10T12:07:13.973931Z. Receipts span2026-09-10T09:59:08.864565Z through2026-09-10T13:37:06.249679Z. There are therefore exactly two distinct causal-history keys for eight original/snapshot consumers in this copy. These are measured properties, not an assumption that future inputs always share cutoffs.

## Prepared synthetic growth fixtures (not model evidence)

New private stage `/var/lib/betboy-capacity-growth-t8512i71` contains one app-owned synthetic working copy and three separate root:betboy0440/single-link/DELETE sealed copies. No existing source, live DB, artifact, snapshot or key was altered. Root performed only standard-library byte/permission staging; generation logic ran as actual betboy uid997 using unchanged owning source validators from the exact59b001d source archive.

Each generation adds the complete47098-receipt Tennis pool from the isolated real base, with explicitly artificial future reception clocks shifted by1/2/3days. The workload result clocks, status paired-receipt identities and competition-reception revisions were consistently rebound and every new row passed the unchanged owning typed Tennis validator before insertion. Original B1 rows, six A1 artifacts and four B3 snapshots remain byte-identical. These are capacity fixtures, never genuine received source data or a claim of improved predictions.

| Generation | Observations/contents | File bytes | SHA256 |
| --- | --- | --- | --- |
| 1 | 94595 | 198463488 | `de141b33142f4469de70f74263cd39035d1b562b90efb2878a471051d752305d` |
| 2 | 141693 | 292982784 | `6d7c10b8c1a6996b9b92e4eee7bf68d64b5d0d0c0fa5fd8895dd2e1355b33e9c` |
| 3 | 188791 | 387739648 | `3628dee7b82bcfadd320bfc9f28df8d770fc7e31692de690cdcb0ae0919cc953` |

Paths are `generation-1/context.db`, `generation-2/context.db`, `generation-3/context.db` below that private stage. Generation wall times77.444s/79.277s/78.767s; peakRSS38104/38244/38248KiB. Those are **fixture construction** measurements, not D4 capacity passes. All three fresh byte copies were streamed, fsynced, hash/identity-checked, and sealed separately with no SQLite companions. Current-source full D4 benchmarks and concurrent seal races remain pending.

## First full cache benchmark and independently corrected schema lifecycle

Exact `c3bac371dede2f7ac825fc8f38f22f75f69d7919` Git archive SHA256 `a0182b47bd895c8619d6cf3e4456cd2fa3e1df9ae890884a797ac17ae7cda13c`, root-staged at `/var/lib/betboy-capacity-code-21iqlrv_/source`,772members. The unmodified CLI ran as betboy uid997 against the real104202240-byte sealed copy with2GiBAS/300CPU/600wall/1MiBoutput bounds, numeric threads1. An app-user stdlib parent captured actual child return code and rusage; it did not patch model or verifier functions.

Result: **full verification completed**, exit2/`transport_only`,229.188s wall,228.438s CPU,350844KiBpeakRSS. Counts6artifacts/2manifests/47497contents/47497receipts/4snapshots/0rollbacks, unchanged two limitations and emptyD2 lists. Input SHA/stat unchanged; no companions. This provisional profile fits the measured current copy, but does not establish final-revision or growth acceptance.

Independent review then closed a real cache API defect: same-transaction DDL could leave the original transaction/write counters unchanged. Fix7d6595e/report4fad098 pins main and temp schema cookies as well. Scoped independent review APPROVED with16DDL countercases passed; author32cachetests and194adjacenttests passed/12skipped/1deselected. Owning source/model files remain unchanged.

Exact corrected source `4fad0983b7595d1be260b652b216fedb8b9fb8a1` archive SHA256 `ddab7d039d59e43bc397ff6619deebcd67d470f8dd98671867cd8a5df02bf777`,772members, lives separately at `/var/lib/betboy-capacity-code-y4z0hffl/source`. Production was not changed. Largest-generation exact-CLI benchmark is in progress; no outcome is claimed yet.

## Exact corrected source: native DAC and real interleavings

Against that4fad098source, actualbetboy uid997 checks reconfirmed3OS/SQLite write denials,8unsafe fixture classes rejected, and exact small memory/sealed-report equality.

Additionally seven real file-system interleavings were exercised in the newly created `/var/lib/betboy-capacity-races-0ag7o51n` only. Root ran standard-library fixture byte/permission operations; each child imported and executed the app reader **after runuser switched tobetboy**. A bounded stdin/stdout handshake paused the child at the actual read boundary; no source trust validator was disabled.

All seven were rejected with the expected trust error: same-path file replacement, ancestor-directory replacement, changed bytes on the held inode, new WAL sidecar, file permission change, ancestor permission change, and replacement between initial sealing and SQLite's own path open. Existing backups, source trees, input copies and production paths were untouched. These are actual native diagnostic results, not a relabeling of Windows-skipped pytest cases. Aggregate native profile/final release gates remain separate.

## Largest growth profile: cache-only reader still HOLD

Exact4fad098 CLI against generation3 (387739648bytes/188791receipts) ended with childreturncode**-9**, parentrecorded300.040CPU seconds/300.219wall seconds/312792KiBpeakRSS. No D4 report was produced. The measured profile was explicitly rejected. The supervisor's wall/output limits did not fire; its recorded failure is `child_exit`. The input's SHA/stat remained unchanged and no SQLite companions appeared.

This is not a memory-cap failure or permission to increase theCPU limit. The controller approved the narrowly specified completed-inventory/cutoff iteration refinement only after this measured failure. Full physical validation remains mandatory before any later-receipt decoding can be avoided during historical replay. Task2RED-only work is committed624280d (9expected new failures/1controlpass;239oldtests pass); its writer stopped before production changes so Task1 can be refined without concurrent code writers.

## Validation-owned cutoff refinement: correctness accepted, capacity still HOLD

Implementation8249c288d69337b50e1fde4209171836abba190f/report73e6abd preserves the complete physical pass before selective repeated decoding. Independent scoped review APPROVED with20targeted tests; author213focused pass/12skipped including the real protected-final case. The native archive is33573476bytes, SHA256`fdbba2c5ce81b480cf98c2ede449dda4514ebb38423b64702783e264d1a7e4d8`,776validated source members at`/var/lib/betboy-capacity-code-w4znixio/source`.

Its unmodified largest-generation CLI again failed: childreturncode**-9**,299.949CPU seconds,301.154wall seconds,352636KiBpeakRSS, no report. Input387739648bytes retained exact SHA/stat and no companions. The supervisor recorded`child_exit`, not its wall/output bound. This does **not** satisfy the supported profile; no updater/app deployment occurred and no budget was raised.

Additional read-only structural metadata on the real sealed copy: the first original cutoff includes47098rows, latest clock10:00:07.203791Z; the second includes47361rows, latest12:07:12.644064Z. The sport of the263-row difference has not yet been measured. Similar prefix sizes do not prove identical owning history tuples or cache reuse.

Task2 now owns the sole production-code writing slot for the already-approved streaming/online-preflight implementation. Task1 follow-up is observational profiling and a read-only proposal only. Task3 read-only decomposition is complete and waits for frozen reviewed Task2 algorithms; the unchanged archive helper already performs an actual isolated restore through`--verify-only`.

## Exact8249 source: observational current-copy phase/cache measurements

`observe_capacity_cache_api.py` ran against that unchanged source as betboy, with2GiBAS/300CPU/620wall and single numerical threads. Timing wrappers call the original functions unchanged; the constructor observer returns the original cache instance and only retains its counters. This is an observational full API run, not a substitute for the unmodified CLI profile. An initial local-script syntax error produced no verification or production mutation and was corrected before this run.

Full API verification completed:242.787wall/243.453processCPU seconds,352716KiBpeakRSS; exact6/2/47497/47497/4/0counts, two unchanged limitations, empirical approvalfalse, input SHA/stat unchanged and no companions. Phase wall times: physical observations32.651s; first cold history64.406s (66.107s including store); second cold history64.290s (65.835s including store); subsequent history hits0.603-0.758s. Original phase136.573s. Four unchanged owning feature calls13.600/14.686/14.700/13.602s; full snapshot phase66.567s. These phases nest and must not all be summed.

Actual cache:2misses,6hits,2stores,0evictions,0bypasses,2entries of28432021bytes each; current/peak total56864042bytes within67108864. No pending bytes. This disproves cache pressure as the cause of the two cold passes; their keys have different cutoffs.

The exact263-row interval is now measured: football injuries108, injury-coverage62, empty-lineups62, native-base31. No tennis rows. Given unchanged owning selector semantics, those new rows do not change the selected Tennis history. A narrowly bounded incremental completed-selection reuse proposal is under read-only review; no implementation is authorized while the Task2 writer is active, no check/model/budget has been changed by this diagnosis.

Reading with the exact Mapping's`SELECT digest FROM artifacts` order resolved another material detail:12:07,10:00,12:07,10:00. Therefore earlier-only incremental reuse would **not** remove the measured duplicate. The reviewed smaller proposal is a clock-bounded prefix of a successful later same-tour immutable cache entry, under the completed inventory/lifetime proof; owning selection is monotone and its added evidence fields depend only on row clocks. The controller incorporated this precise refinement and RED requirements into the plan, but Task2 retains the sole-writer slot until a coherent handoff. No arbitrary reordering of original verification or new trusted decoder is proposed.

Production rechecked after the observational run: exact appHEAD`2dd1116b68f3d94e9c24338c6c9dff9b01799221`, updaterSHA`74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`, internal health`ok`. These are current independent checks, not a new deployment.

## Task2 checkpoint Linux portability check

Exact8f42995Git archiveSHA`09483d2f9a9653d9d71a4ccc064a16557fe335eceea0dbd24cabe6a810bdc988` was extracted into a fresh private QA directory as ordinarySSHuid1000;779members, no root/app/prod changes. The existing QA venv was used unchanged. First attempt had an incorrect basetemp parent in the controller's runner; those setup failures are not product defects. Its directory`task2-hooks-8f42995-tslsl5to` remains preserved.

With a corrected fresh fixture directory`/tmp/betboy-context-qa.9xr68INa/task2-hooks-8f42995-pihu8jjs`, the unmodified262-test module produced **261passed,1failed in38.58s**,39.213s supervisedwall. Failure:`test_capacity_launcher_executes_only_fixed_bounded_target[backup-0]`, `SystemExit: invalid trusted backup child`. The unit fixture simulates uid0 but root-owned helper metadata only onWindows, while LinuxQA correctly runs as ordinaryuid1000. This is a portability defect in the unit boundary, not permission to run app tests asroot, change helperownership, or weaken actualDAC. It was delivered to the Task2writer for a portable fixture fix plus rerun.

Independent Task2 checkpoint review additionally records four static Important findings in`task-2-checkpoint-independent-review.md`, separate from the already acknowledged cross-phase configuration gap. They are not executed attack/native proofs and do not constitute release approval.

## Third refinement native staging

Exactcode`4db611853d76a98937c7221ad2d85dec38232797`/report`b389b2c`, local234adjacenttests pass/12skips,21newcoveringcases. Native Git archiveSHA`40a21d8e3ad651dcc765f18b59ea7ef3341f7cfd7aae882f4cbb08f4e52be0b5`,779members, separate root-staged code`/var/lib/betboy-capacity-code-pon_l3e5/source`. Only reviewed stdlib byte/permission operations ran asroot. Largestgeneration exactCLI is running asbetboyuid997 under unchanged2GiBAS/300CPU/600wall/1MiBoutput bounds. No new native result or deployment is claimed yet.

## Third refinement: largest native profile still HOLD

The exact4dbCLI completed neither report nor supported profile: child-9,300.342CPU/301.451wall seconds,354292KiBpeakRSS; input387739648bytes retained exactSHA/stat and no companions. Independent correctness review is separatelyAPPROVED with21fresh covering tests, not native/release acceptance. Archive size33594081bytes.

A subsequent observational API run directly on generation3 used a290CPU-second diagnostic soft stop and unchanged300hard/2GiBAS bounds. It intentionally stopped incomplete, not an exactCLI capacity pass. Timings: schema3.911s, artifacts3.820s, fullphysical147.192s, originals start161.226s; one cold76.698s (78.684includingstore), covering4.202s, exacthits0.769-0.916s; originals88.524s. Two completed snapshot features15.352/15.226s; diagnostic interrupted the third. Actualcache56864042bytes,2equalentries,0evictions,2exactmisses,1coveringhit,5exacthitsbeforestop;290.289CPU/288.049measuredAPIwall,352520KiBpeakRSS. This proves covering reuse occurs, but does not finish the whole verification. The incomplete diagnostic does not claim its usual final hash/stat comparison; the next profile independently rechecks the exact input hash before and after.

The bounded first-physical-receipt cProfile deliberately stopped after25CPU seconds of profiling, after the complete content phase. It began firstreceipt39.258s afterAPIstart and ended64.335s,66.419processCPU,174788KiBRSS. It observed23668receiptcalls and13484899functioncalls. Cumulative: `__getitem__`24.638s, unchangedowning`_decode_receipt`21.734s, normalize12.294s, price-name predicate6.261s, canonicalserialization5.731s, trackedconnection.execute2.256s including1.467sSQLiteexecute selftime. Timings overlap; do notsumthem. Input SHA matched both before and after. This is neither fullvalidation nor empiricalmodel evidence.

The controller is evaluating single-stream existing LEFTJOIN traversal for the complete receipt phase plus validation-owned SQL cutoff traversal for later causal reads, preserving every owning decoder, protected opaque receipt and fullphysicalfirst contract. No further reader implementation or resource-setting change is authorized while Task2 retains the sole-writer slot. The owning decoder dominates the measured cost, so eliminating dispatch alone is not represented as guaranteed capacity success.

## Fourth traversal and Task2 native follow-up

Task1 code `c4e20e01f90a9003114ec44655de7bf30dff55fa` was archived with SHA `08affa6e4a0bfd2f4a344e0c9861c4de880d261c1e2524d316c857f4cbecaa86`, 782 members at `/var/lib/betboy-capacity-code-yrnkbb3u/source`. Independent correctness review APPROVED; largest-generation unmodified CLI started as uid997 under unchanged budgets. No complete result claimed at this checkpoint.

Exact Task2 bdd5731 archive SHA `da27919646a109e2e023dd8fbf89562a15f777915c5ee69c824bd812452c945c`: Linux fixture suite **313 passed in37.60s**, 38.317s supervised, ordinary SSH uid1000, QA `/tmp/betboy-context-qa.9xr68INa/task2-hooks-bdd5731-n132frbn`. Root-sealed native source `/var/lib/betboy-capacity-code-jd77zoss/source`, 779 members.

Native synthetic full chain at `/var/lib/betboy-task2-native-90uadk50`: valid full three-DB backup/isolated restore/HMAC PASS; manifest-consistent wrong synthetic key rejected by actual authenticated financial chain. This proves helper authentication, not empirical context validation. Actual producer uid997 `/proc` showed AS2147483648/CPU300/FSIZE67108864, numerical threads1. Pinned root stdlib helper showed AS2147483648/CPU300 and threads1. Sampled process RSS is observational, not exact per-child peak; private copy/publication are bounded stdlib byte operations, not falsely described as having the verifier's RLIMIT_AS.

The subsequent real OS unsearchable subtree still produced a completed archive with hidden DB omitted. This independently corroborates final review; native Task2 remains HOLD until corrected. The installed updater stayed at the old exact SHA. See `task-2-final-discovery-review.md` for scope, explicit test-harness corrections and preserved artifacts.

## Fourth reader: completed exact profiles and renewed native trust checks

Unmodified c4e20e0 CLI completed the largest generation with child exit2 and the exact original transport-only report/limitations: **298.435 CPU / 298.846 wall seconds, 354128 KiB peak RSS**, 188791 contents and receipts, 6 artifacts/2 manifests/4 snapshots/0 rollbacks. Input SHA/stat unchanged, no SQLite companions; supervisor profile accepted. This is an observed pass with only about one second of wall-time headroom, NOT a guarantee for further growth or fluctuating server load. No limit was raised and no empirical model approval was manufactured.

The same exact CLI on the real 104202240-byte sealed copy completed **192.065 CPU / 192.209 wall / 348524 KiB**, 47497 contents/receipts. Generation1 (198463488 bytes) completed **227.083 CPU / 233.933 wall / 348100 KiB**, 94595 contents/receipts. Both retained all other counts, exact limitations, hashes/stat and no companions; profile accepted. Generation2 remains in progress at this checkpoint. Benchmarks themselves run sequentially; short isolated QA controls and existing scheduled services can still share this live host, so measured wall time is not an idle-machine guarantee.

Against exact c4 code, native uid997 DAC repeated **3 denials / 8 unsafe classes / equal small memory-vs-sealed reports**. Seven actual interleavings were again rejected at `/var/lib/betboy-capacity-races-d92gozc1`: file replacement, ancestor replacement, held-inode mutation, sidecar, file/ancestor permissions and before-SQLite-open replacement. Root only altered newly created synthetic fixtures; app imports remained uid997. Production unchanged.

## Task2 c2 discovery fix: native chain and fixed-launcher evidence

Exact code `c2cb1c98ee66fbda792ed2c339eff8aa8ceb0c87`, updaterSHA `1ef6bee0a75cd0005c5ee245ce83d3d65b6739da29689cfb59fbef100532a068`, archiveSHA `837440c84cca983cd4250a1140d81d8600511f5f372f027aa31a4f9e611ccb1e`, 782 members at `/var/lib/betboy-capacity-code-9uz7wry9/source`.

New native synthetic QA `/var/lib/betboy-task2-native-6pyy9gqp` completed: valid full three-DB chain, actual wrong-key HMAC rejection after successful inline transport, mixed-case `Historical.DB` full four-DB archive/restore, four actual app read/write denials on root archive/receipt, held app FD mutation-before-copy rejected without destination, mutation-after-copy left the independent root inode/hash unchanged, and actual EACCES rejected before archive publication. Per-case root-private logs/evidence retained. No existing production files changed.

Fixed literal launcher at `/var/lib/betboy-launcher-native-sgriygfp` executed QA probes as actual uid997 and reported AS2147483648/CPU300, all four numerical thread settings1. A real 3GiB virtual allocation was refused by the OS as MemoryError under that AS limit; the actual shell collector classified it as VerificationResourceError. Actual1048577-byte output was bounded and rejected. Root d4/dependency calls, app backup role, root backup-service and extra d4 argument were all refused. Correct backup-service uid995 executed only the pinned installed helper and authenticated/restored the synthetic three-DB archive. These are QA launcher controls, not empirical models or production data.

Independent c2 re-review closed the previous traversal/ASCII case groups but found one remaining P2: Python `casefold()` discovers `Historical.ſQLite` while GNU-find `-iname` does not (actual local byte-count and DAC/storage functions reproduced; no native claim for that finding). Task2 writer is replacing the three find-pattern consumers with one equivalent stdlib casefold enumeration; no helper change. Thus native c2 successes do not prematurely approve its remaining scope mismatch or the not-yet-measured next revision.

Generation2 subsequently completed unmodified c4 CLI: **256.521 CPU / 256.711 wall seconds, 348440 KiB peak RSS**, 292982784 input bytes, 141693 contents/receipts. Full original counts/limitations, input SHA/stat and no-companion check passed. This finishes the requested current-copy plus three synthetic growth profiles at the exact c4 reader revision. The very narrow largest-fixture headroom and need for a fresh real target-release preflight remain explicit.

Task2 Unicode follow-up code `690dd16c048db8c66a05936fffcb6aca55ab8a95`, report `0541080e7e9cfcfdb3969c58b03f26157541523f`, updater SHA `24a5366692abeda8c4bcab1157fbed8806b97a72822b0db992545bb62e3de6a5`:339 focused tests pass in47.57s; common fixed stdlib enumeration retains casefold/companion path spelling and complete traversal for byte and DAC lists. Independent/native acceptance still pending at this checkpoint. No helper/source/model/budget/production changes beyond the authorized updater files.
