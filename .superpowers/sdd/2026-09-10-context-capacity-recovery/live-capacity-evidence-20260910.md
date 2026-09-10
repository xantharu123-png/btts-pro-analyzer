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
