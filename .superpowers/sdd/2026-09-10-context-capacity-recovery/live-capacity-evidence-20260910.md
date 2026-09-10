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

The independent lifecycle defect in this pre-fix source was separately corrected by41067c0/3967778 and independently accepted. That does not explain away or close the observed performance problem. `profile_first_context_history.py` is now a deliberately bounded diagnostic against this preserved pre-fix source, not another acceptance run. Its initial timings are schema0.493s, artifact types3.588s, manifests0.001s, physical observations34.376s; first complete tennis history profiling begins around41s.
