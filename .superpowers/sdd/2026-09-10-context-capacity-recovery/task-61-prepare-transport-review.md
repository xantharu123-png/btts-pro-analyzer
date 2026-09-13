# Task61 native-input/control preparation transport review

## Verdict

**Spec/scope verdict: compliant for this fixed preparation instrument.**

**Code-quality verdict: Approved for this bounded instrument review.** No new Critical or Important defect was identified in the three reviewed scripts. This is approval of their fixed upload/control-preparation implementation, not an actual prepared-input seal, admission,1024-row diagnostic, full-C or release pass.

## Reviewed identity and scope

Read only these three instruments and used the previously reviewed1632072 catalogue/parent APIs as context:

- `evidence/task61-native-input-upload.py`, actual SHA256 `c118672160b6fdcd5f4699e0fd63c6b89d3affeafd28ecaaf62656dc807580f0`.
- `evidence/task61-native-catalogue-prepare.py`, actual SHA256 `97b605c2b29bcce2d9b401847cc5ea4fb942f591453122e59accddbabcc895e6`.
- `evidence/task61-native-prepare-run.ps1`, actual SHA256 `55152459a26fe5cc94cdd80fcb6ff38cd2c7f4d1b78cb4d5e62779ff58778c7b`.

Both Python template hashes match the dispatch and runner pins. Root reports syntax checks and both DryRuns exit0, with catalogue stdin474157bytes/SHA `88368cf0e0733fd54a94d7bddbe07ce2c30e08c3385da654f7de67845be2e76d`; this review did not regenerate or execute that program. No native/network/Git/test command, active data read, source mutation, broader crawl or subagent dispatch occurred. Only this report was written.

## Checked strengths and requirements

- **Fixed held-byte transport:** runner `:5-14` reads each template once into held bytes, applies size/hash validation to the same array and strictly decodes it. Upload `:15-19` separately holds the exact9533440-byte archive and expected SHA `daf6ac61183bb3a42f8401f7568b2020a0f4bdef07d07a72d295e61363bc4d4c`; the checked template is base64-embedded into the fixed remote command while stdin carries only archive bytes. Catalogue `:21-43` holds/hashes the exact seven source members and both fixed metadata controls, substitutes each fixed placeholder exactly once, and caps generated stdin at2MiB. No template hash-then-reopen execution seam remains.
- **Explicit root-only execution environment:** runner `:19,44` uses the fixed host/command, `sudo -n env -i`, fixed PATH/LANG and `/usr/bin/python3 -I -S -B`; both Python entries check exact UID/GID, flags and environment. Upload `:2-19` installs CPU15/AS256MiB/FSIZE16MiB/CORE0/alarm30; catalogue `:2-20` installs CPU60/AS2GiB/FSIZE8MiB/CORE0/alarm300. Those are separate preparation envelopes, not changed native diagnostic60/240/300 limits or a new free full-C lifecycle.
- **Only three new namespaces:** upload `:21-37` fixes the input, registry and job paths, checks their protected directory ancestors, requires all three absent before creation, and uses refusing mkdir with fixed0755/0700/0755 modes. Parent-directory fsync follows each creation. There is no deletion, chmod of inherited history, fallback name, resume or retry path.
- **Exact inert archive:** upload `:38-61` creates one O_EXCL/O_NOFOLLOW archive, streams with an exact9533440-byte limit, writes all bytes, validates full SHA/size before sealing0444, fsyncs file and directory, and reports bytes/hash/allocation. It neither imports nor extracts the archive. A short/long/wrong stream fails and retains partial new output; an existing root makes a rerun refuse rather than overwrite it.
- **Held preparation code, no diagnostic launch:** catalogue `:21-38` independently pins the exact seven held member bytes and compiles the parent under non-main `__name__`. It calls the previously reviewed `load_catalogue` and `load_helpers`: the former compiles the new/old held catalogues and the latter registers only the three existing helpers while compiling admission as an unregistered namespace. No parent `main`, `startup`, `admit_diagnostic`, `launch_once`, worker import or worker run is called. Calling `launcher` at `:102` constructs bytes only; those bytes are not executed here.
- **Refusal of partial/stale preparation:** catalogue `:48-58` requires protected exact input/registry/job directories, input-root membership containing only the fixed archive, empty registry/job, and the archive's full size/hash. Thus prior partial retained/catalogue output refuses a rerun. `:95,100` writes only the exact retained.json/catalogue.json controls through the previously reviewed bounded O_EXCL writer. Failures keep all files; no automatic cleanup or new names are introduced.
- **Complete selected retained namespaces:** catalogue `:40-47` pins the exact16-journal and prior85-root control bytes; prior metadata supplies required membership, not content/hash authority. `:60-78` implements the explicit previously selected filesystem prefixes and named omissions, includes all prior roots and requires Task60 plus the prefix root, excludes only the exact three new namespaces which are separately planned, and bounds directory enumeration/root count. Extra selected roots are included rather than silently ignored; unexpected types fail through the retained-root reader.
- **Fresh typed hashes and read-only journal replay:** catalogue `:79-94` calls the reviewed complete typed `retained_root` for every selected path, attaches sorted declared journals and replays each with `observe=True`. Symlink/hardlink treatment remains owned by that reviewed implementation. Top-level selector membership is rechecked; `inventory` at `:96-99` performs its independently reviewed retained-observation pass again, builds the fixed commit/profile/input allocation, and refuses changed/incomplete evidence. No old journal is opened for reservation, settlement or recovery.
- **Honest accounting labels:** catalogue `:83-94,103-114` retains root charged CPU as unknown/null, preserves each declared journal's actual category/state/charge, uses exactly4GiB backup reserve, and labels the sum of per-path allocated bytes as an occupied upper bound. It does not subtract that historical sum again as future growth or claim unique physical usage/settled full-C cost. Inputs/archive/new controls are explicitly separated from retained history, not hidden by wildcard exclusions.
- **Correct published API use:** catalogue `:96-102` passes the exact reviewed `inventory(archive, commit, *, manifest_path, retained_path, retained_sha256, registry_directory, job_directory)` arguments and then `launcher(archive_path, archive_sha256, manifest_path, manifest_sha256)`. The separately planned manifest path may be absent during inventory; it exists and is hashed before launcher construction. Current call shapes match the already reviewed API without changing its schema or policy.
- **Terminal transport and no retry:** runner `:49-83` exits DryRun before output creation/SSH, uses CreateNew stdout/stderr files, concurrently drains both channels, waits for actual SSH/stream completion and flushes retained output. `:84-90` reports actual SSH exit, output lengths/hashes and returns the actual exit. `/usr/bin/time` provides separate terminal exit/wall/CPU/RSS evidence. No remote diagnostic child/custodian is created by either entry, so their bounded preparation alarms do not abandon a diagnostic child.

## Issues

### Critical

- None identified within this instrument scope.

### Important

- None identified within this instrument scope.

### Previously deferred Minor

- General SSH stdout/stderr log cap issue T2 remains deferred as directed. Runner `:64-65,85-86` retains the existing unbounded transport-drain/readback pattern. This review does not reopen or silently close T2, and identifies no distinct new material log/custody breakage in this no-diagnostic-child preparation path.

## Cannot verify / required Root follow-through

- **Actual absence/seals:** Root reports the three names absent in ccc8e6 and prefix root16384allocated bytes. Those observations were not repeated here. The scripts must succeed against fresh actual state, and Root must independently retain terminal exit/output and verify created namespace/archive/control identities and hashes after completion. A successful DryRun proves none of that.
- **Actual retained union:** the two pinned JSON control files and live85+Task60+prefix namespaces were not opened in this review. Their exact original contents, declared16-journal completeness, actual typed inventory, protected ancestors, allocation totals and selector stability remain native observations. The code binds and replays supplied declarations; a planning/root-classification error cannot be ruled out merely by script syntax.
- **Reserve/admission distinction:** upload's `:29-30` free-space check is a bounded upload-preparation check, not the complete diagnostic outstanding-allocation proof. Catalogue preparation records the exact reservation and backup policy but does not itself admit the actual live active-input physical union or prove current available reserve. The reviewed diagnostic main must still perform those actual held-input/allocation/free-space rechecks and obtain its permanent300CPU ticket before any diagnostic copies/fork. These output controls are expectations/snapshots, never admission authority.
- **Preparation costs and partials:** actual CPU/wall/allocation of full retained hashing, repeated verification, archive/control output and partial failure files must remain retained/accounted separately. CPU60/alarm300 can stop catalogue preparation before completion; a partial retained/catalogue write cannot be promoted to success or silently retried. No settled full-C budget claim follows from the printed preparation CPU value or `/usr/bin/time` line.
- **Freshness before diagnostic execution:** successful preparation is not a lock over live history. Root must freshly verify the exact manifest/bootstrap/archive/control bytes and retained identities when using the diagnostic's existing admission/recheck protocol; later data/namespace changes must reject rather than inherit the preparation snapshot as authority.
- **Native prefix status:** Root now reports actual success/failure prefix tests plus terminal post-readback passed. This review accepts that as controller-provided status only and did not reopen its evidence; it does not invalidate or re-prove those earlier results. Actual full-baseline1024/admission remain unexecuted per dispatch.
- **Release scope:** full490000 growth, original global1800/3600 proof, complete C/B, Source/D2, backup/restore, deployment and release remain open. No application, service, secret or live database mutation is authorized by this preparation-only approval.

## Assessment

**Approved for the fixed preparation instrument.** Held bytes, fixed new paths, refusing writes and the reviewed inventory/launcher calls are coherent and do not introduce a hidden admission or worker launch. Root must judge the actual native terminal/readback evidence separately and preserve every preparation failure/unknown cost; the resulting controls are inputs to later admission, not a diagnostic pass.
