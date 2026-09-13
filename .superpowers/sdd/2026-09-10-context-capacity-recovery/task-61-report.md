# Task61 implementation report

Status: READY_FOR_INDEPENDENT_REVIEW; code/tests frozen, final focused run green.
No native diagnostic/prefix execution, native approval or release claim.
Dispatch base: eaa60ac619f4c0900f5d44beefbb8ab79cd9e7c4.

## Interfaces declared before code

All JSON controls use ASCII canonical JSON (sorted keys, compact separators,
no float, duplicate key, nonfinite number or bool-as-integer). Paths are exact
absolute POSIX paths; file lists are sorted and unique. Hashes are lowercase
SHA256. No native input payload is returned by inventory.

- `inventory(archive_path, commit, *, manifest_path, retained_path,
  retained_sha256, registry_directory, job_directory) -> bytes`: read-only
  native manifest construction. The manifest path denotes the separate planned
  control slot and need not exist yet. Archive, retained control, exact fixed
  baseline, existing dependency installation and registry/job directories must
  exist. It neither authorizes admission nor writes/launches/imports product.
- `bootstrap_source(sources: dict[str, bytes]) -> bytes`: exact parent,
  new catalogue, old catalogue, Task60 and three pinned helper held members.
- `launcher(archive_path, archive_sha256, manifest_path, manifest_sha256)
  -> bytes`: reconstruct the exact reviewed stdin from held archive bytes.
- `validate_manifest(value, commit, *, retained_raw, runtime, installation)
  -> dict`: closed validation and independently recomputed identity/plan.
- `sample_exact_slots(root, slots, metadata_cap, *, previous=None) -> dict`:
  slots is a sorted mapping of relative paths to exact file caps; binds all
  observed files/directories without requiring not-yet-written slots to exist.
  Result keys `files`, `directories`, `logical`, `allocated`,
  `metadata_logical`, `metadata_allocated`. File records contain `path`,
  `identity`, `size`, `allocated`, `sha256`; directories contain `path`,
  `identity`, `size`, `allocated`. Epoch identity is seven integers in old
  catalogue order. Native allocated bytes use actual st_blocks*512; portable
  fallback is labeled by test scope, never native allocation evidence.
- `Progress(path)`: O_EXCL/no-follow held writer; `append(body) -> frame`;
  `close()`. `parse_progress(raw: bytes) -> dict`: keys `frames`, `head`,
  `complete_bytes`, `incomplete_tail_bytes`, `completed`, `last_phase`,
  `stack`, `terminal`. Frames/body are exactly the blueprint schemas.
- Parent `main(argv: list[str]) -> int`: only the seven ordered CLI pairs
  from the brief. One Task60 admission precedes all copy/fork; no recovery.
- Worker `run(mode: str) -> dict`: only `receipt-v1`; actual guard before
  catalogue/dependency/product load and actual corpus call exactly once.

## Closed retained and allocation controls

Retained control format `betboy-receipt-diagnostic-retained-v1`, top keys
`format`, `roots`, `backup_rollback_reserve`. `roots` is a nonempty sorted list
of non-overlapping complete retained namespaces. Each root has exactly `path`,
`identity`, `membership_sha256`, `files`, `directories`, `symlinks`, `logical`,
`allocated`, `category`, `charged_cpu_ns`, `journals`. Membership is streamed
over sorted canonical typed records, each followed by LF, includes
the root directory as `.` and every descendant; no exclusions. Retained records
are exactly `path`, `kind`, `identity`, `size`, `allocated`, `sha256`. Kind is
`directory` (null sha256), `regular` (held no-follow full bytes, real nlink) or
`symlink` (hash of bounded raw target bytes <=4096, never dereferenced).
Directories are visited in sorted depth-first
order; in each directory emit its record then sorted children recursively.
The digest therefore binds every descendant's identity, bytes and allocation.
Per-root count <=200000, all roots <=500000, root count <=256, depth <=32,
per-directory children <=50000, path UTF-8 bytes <=2048, file cap 8GiB,
complete total <=64GiB. Per-path allocated totals are occupied upper bounds;
hardlinks may be counted twice, never claimed as unique disk use/future reserve.
Categories are
`historical-qa`, `backup`, `rollback`, `reused-input`. `charged_cpu_ns` is null
when unknown; otherwise exact nonnegative integer. `journals` is a sorted list
of exact `{path, identity, journal_head, ticket, state, charged_cpu_ns,
settled_cpu_ns, category}` records. Path is relative; identity is complete
BudgetIdentity; ticket is null or the actual Reservation mapping
(`identity_digest`, `reservation_digest`, `sequence`, `portion_digest`,
`cpu_ns`, `deadline_boot_ns`). State is stopped/pending/accounting-open;
category is historical-measurement/synthetic-protocol/unknown. Known journals
must match read-only replay, not inferred account settlement. Poisoned pending
evidence remains pending/fully charged. Empty journals means none known.
Historical labels are observations, never imported full-C settled costs.
`backup_rollback_reserve` is outstanding future bytes, not occupied history.

Manifest `retained` is exactly `{path, size, sha256}` for those complete
canonical bytes. New controls are outside all retained roots: this explicit
separation avoids a self-hashing inventory, not an implicit exclusion.

Manifest `allocation` has exactly `slots`, `metadata_cap`, `registry_slots`,
`registry_metadata_cap`, `inputs`, `input_metadata_cap`, `new_job_cap`,
`active_input_cap`, `free_reserve`, `backup_rollback_reserve`, `total`.
`slots` maps exact job-relative paths to file caps (including all code,
dependencies and timezone copies, archive/catalogue, baseline seal, corpus
main/journal/ledger, progress, output/report/failure/custody controls).
For this fixed first diagnostic the registry slots are exactly the registry
control and one identity-derived journal, each 1MiB. A nonempty registry is
refused, never erased/bypassed or imported as fresh work. `inputs` is a sorted list
of `{path, cap}` covering original archive, separate planned manifest control,
retained control, baseline, dependencies and timezone files; reserved manifest
cap is 8MiB and never hashed into its own identity. `metadata_cap`=128MiB,
`registry_metadata_cap`=1MiB, `input_metadata_cap`=128MiB.
`new_job_cap`=8GiB; `active_input_cap`=4GiB; `free_reserve`=4GiB.
`total` sums rounded job/registry slots and their metadata; occupied history
is independently rescanned and not subtracted twice from free bytes.

Identity execution hash binds `{code, dependencies, prefix}` where prefix is
`betboy-receipt-diagnostic-child-cpu-handoff-v1` and the parent member hash.
Runtime hash binds `{runtime, timezone_data}`. Installation hash binds
`{machine_id_sha256, executable, executable_sha256}` from actual native reads.
Other fields and acyclic plan/history hashes follow the brief exactly.

Native result format `betboy-native-receipt-diagnostic-result-v1`: keys
`format`, `plan_digest`, `baseline_sha256`, `generator_sha256`,
`driver_sha256`, `completed`, `corpus`, `phases`, `progress`, `cleanup`.
`corpus` contains the exact dataclass fields, with paths rendered as strings
and complete RawInventory dataclass data. `phases` is a list (<=64) of closed
`{phase, occurrence, inclusive_cpu_ns, inclusive_wall_ns, returned, call_count,
call_cpu_ns, call_wall_ns}` objects. The three call accumulators are null except
for append, whose attempted real calls are separately timed without generator
time; successful terminal call_count is1024. Inclusive nested timings are never
summed as exclusive CPU. `progress` is `{head, count}`; `cleanup` is
`{source_closed, worker_finished}`. Parent never sets native_pass true.

## Native test-only entry (Root clarification)

`native_prefix_test(mode, *, root='/var/lib/betboy-receipt-prefix-task61-01')`
accepts only success/failure at that exact root. `PROBE_SOURCE` is the fixed
stdlib probe byte producer in the new parent module; Root separately provisions
its root-sealed probe.py plus fresh UID/GID65534 mode0700 success/failure slots.
No diagnostic CLI mode is added. The test-only entry uses the same prefix,
actual supervisor/guard/SIGSTOP/readback/wait4, parent hard60. Failure binds a
wrong expected parent PID and must terminally exit125 without unwinding.
Each test requires its own fresh env-i -I -S -B root interpreter; ordinary local
pytest never invokes sudo/SSH/native work automatically.

Probe bytes:1203; SHA256
`5818c8a838e817651c6bd0e9e76158df4f029eb0bb2bc6d5d74de1d189fa37be`.
The native test records actual owner-cleanup PIDs through an inherited pipe;
after actual reaping it requires exactly the parent PID, rather than supplying
an unobserved boolean assertion. Unexpected UnreapedChild enters the same
operator-stopped custody loop before propagating; failed report I/O never
discards that PID/pidfd. No parent-death auto-reaping claim.

`native-result.json` preserves every scalar NativeRunResult field plus exact
hex stdout prefix<=128KiB and stderr prefix<=8KiB. For each prefix it also records
`*_retained_size`, `*_retained_sha256`, `*_truncated` for the complete bytes
actually returned by the unchanged supervisor. Thus failed excessive output
cannot overflow the1MiB retained-result control or masquerade as a complete
successful log. The actual result is retained before success parsing/live
admission rechecks; `stdout.bin`/`stderr.bin` retain those same bounded prefixes.
The raw progress file is never repaired, overwritten or synthesized. Failure
reports include the validated prefix summary when parsing succeeded.

## Evidence

Initial RED command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`,
`PYTHONDONTWRITEBYTECODE=1`, existing `.pytest_tmp/qa-python312-c-01/Scripts/python.exe`
`-B -m pytest tests/test_native_context_receipt_diagnostic.py -q -p no:cacheprovider
--basetemp=.pytest_tmp/task61-red-01 --junitxml=.pytest_tmp/task61-red-01.xml`.
Actual child/tool exit1, chunk7d5412, wall0.6209102s: `9 failed, 1 skipped in
0.23s`. All nine fail as intended on missing Task61 implementation paths.

First implementation run: same command with green-01 paths, actual exit1,
chunk5e40b5. `2 failed, 7 passed, 1 skipped in 1.00s`. Real owner exposed its
actual hash nested under writer_open, added that legal phase parent; killed
subprocess readiness comparison normalized only platform CRLF framing.

Further focused evidence (all commands use the same selected Python, disabled
plugins/bytecode/cache and fresh named basetemp/XML):

| Run | Actual exit | Actual result |
| --- | --- | --- |
| green-02, session53810/chunkb486ac | 0 | 9 passed,1 skipped,69.35s; actual1024 owner |
| red-02, chunkb9d59d | 1 | 1 failed,3 passed; missing declared-journal replay |
| green-03, chunk0b19d4 | 0 | 4 passed,10 deselected,0.58s |
| red-03, chunk5a15bc | 1 | 1 failed,13 passed; missing complete reserve calculation |
| green-04, chunka95277 | 0 | 14 passed,15 deselected,0.27s |
| red-04, chunk8174e2 | 1 | actual unchanged supervisor rejected str cwd; Path required |
| green-05, chunkcf3017 | 0 | 31 passed,2 skipped,1 deselected,1.66s |
| green-06, chunk5fdfa1 | 0 | 37 passed,2 skipped,1 deselected,2.70s |
| prior final-01, session87140/chunk1d2e2a | 0 outer and child | 38 passed,2 skipped,81.94s; outer82.281s; stderr empty |
| red-05, chunkf8b646 | 1 | missing close-source behavior; also test placement error, corrected without accepting this output |
| red-06, chunk0417ca | 1 | actual SQLite connection remained open after absent close-source path |
| green-07, chunke9a92f | 0 | 38 passed,2 skipped,1 deselected,1.73s |

The prior final-01 is superseded: source-close/progress refusal cleanup and
native-prefix-test UnreapedChild custody were tightened afterwards. These are
new QA changes only. No original owner/helper/generator file was edited.

## Frozen code hashes

Source SHA256s (actual readback chunkce3f80, exit0):

```text
tests/native_context_receipt_diagnostic.py
249aa84f12de528d0bbb268de794582ff44bcc6eb1330099793aa1de86a1feb5
tests/native_context_receipt_diagnostic_catalogue.py
c05241df7965b5b185f2df63945806eb89d5b4a37f3fa69c4bd400e17b8249d7
tests/native_context_receipt_diagnostic_worker.py
cb0977cc45319cd822d98535097827d9f73c8ab542a078e61b99abb7f62352c5
tests/test_native_context_receipt_diagnostic.py
63478773277900f73312111c55b47f34a79a516f457238e2e253fb9353a3a5c4
```

The same readback checked every PINS/HELPERS byte hash against the literal
unchanged reviewed hashes and printed `UNCHANGED_PINS True`. This includes
Task60 f0b082..., generator584bd2..., corpus fdbebb..., old chain/catalogue/
worker, storage copying/inventory/append/profile, supervisor, guard and budget.
Exact complete unchanged pins are in the new catalogue PINS/HELPERS mappings
and the required companion blueprint, not abbreviated executable checks.

## Self-review and scope limits

Covered locally: closed manifest/profile and acyclic identity recomputation;
rejected admission before copy/fork; exact original supervisor request types;
portable fixed-prefix field/callable/capability/raise/return rejection; actual
complete1024 generator/owner call with every fixture old table and17MiB opaque
old artifact; whole raw old inventories; source/table/ledger corruption failure;
actual append failure with wrapper restoration; real killed subprocess and
retained verified progress prefix; frame/hash/order/bounds/malformed/partial
write/fsync errors; actual SQLite source cleanup despite progress refusal;
>128MiB exact streamed slot; historical hardlink occupancy distinct from active
single-link admission; two actually replayed pending/stopped synthetic journals;
complete future ID endpoint/clock collision rejection; final-result rejection
on signal/nonzero/no-guard/stop; bounded failed-output retention.

Portable tests deliberately do not establish Linux no-follow/DAC/flock/fsync,
real historical symlink traversal/large-root throughput, privileged hard-limit
raising, seccomp/UID drop, PID/pidfd terminal custody, or actual native100553-row
baseline semantics. The two native tests are explicit skipped gates here; Root
must provision/run them in separate fresh stdlib root coordinators before the
single admitted diagnostic. Native full-baseline and complete retained scans
can still exceed parent60CPU/worker240CPU/wall; that is a measured STOP requiring
Root's next repair, not a promise of capacity or permission to shrink inputs.

The raw progress prefix is a completed-call lower bound, not a committed DB or
retrospective completion of an interrupted call. A constructor failure before
_Build.run may proceed to source_close but can never produce terminal progress.
The driver always reports native_pass=false and requires external terminal/
process/output observation. Full490000 preparation, global1800/3600 proof,
C/B, Source/D2, backup/restore, task58 acceptance and release remain unchanged.

Original baseline permissions are never changed: this fixed implementation
always reserves and makes one fresh root-owned0444 baseline copy, counting both
copies. Root must provide an existing empty root-owned searchable job (0755),
distinct existing empty protected registry, canonical manifest and complete
retained control, all separately bound input slots, archive/runtime dependencies
and the extra4GiB backup/rollback reserve chosen in the Root companion.
No Git/index/commit/push, server/network/install/cleanup or subagents were used.

## Final focused evidence and sole-writer return

Final command ran from the dispatch worktree in the existing selected Python.
Outer coordinator was `.pytest_tmp/qa-python312-c-01/Scripts/python.exe -B -c`
with this exact bounded subprocess program (whitespace expanded for reading):

```python
import os, subprocess, sys, json, time
env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1")
command = [sys.executable, "-B", "-m", "pytest",
    "tests/test_native_context_receipt_diagnostic.py", "-q", "-p", "no:cacheprovider",
    "--basetemp=.pytest_tmp/task61-final-02",
    "--junitxml=.pytest_tmp/task61-final-02.xml"]
started = time.monotonic()
result = subprocess.run(command, env=env, capture_output=True, timeout=240)
print(json.dumps({"command": command, "child_exit": result.returncode,
    "stdout": result.stdout.decode("utf-8", errors="replace"),
    "stderr": result.stderr.decode("utf-8", errors="replace"),
    "wall_seconds": time.monotonic()-started}, sort_keys=True))
sys.exit(result.returncode)
```

Actual execution session87658, launch chunk783b9f, terminal chunk12bd98:

```text
child_exit: 0
outer/tool exit: 0
stdout:
........ss...............................                                [100%]
39 passed, 2 skipped in 81.62s (0:01:21)
stderr: empty
outer wall_seconds: 81.96799999999712
```

Fresh XML `.pytest_tmp/task61-final-02.xml` SHA256:
`4c9e52df9fd576f1d31a76e93fe3672470d6b62f0406d02239f7608a014bcd33`.
Final post-run hash readback chunk8b4322, exit0, confirmed all four source/test
hashes above unchanged and this exact XML hash. No source/test changes followed
that run; only this evidence/handoff report was completed.

Sole-writer return: implementation ownership of the four new QA modules and
this report is now explicitly returned to Root. I will make no further writes
without a new dispatch. Root owns review, staging/commit, native input/control
provisioning, both separate prefix probes and any one admitted native diagnostic.

## Fix round1 declaration (I1-I4; sole writer reacquired)

Dispatch HEAD af01d8a4a52d1170c8139c253aae4a31dae04cac; complete review SHA
96af3f0bb785bfbfd39b5003116112801fefee84d8e481532b96223746c3507d read.
No manifest, retained or allocation public schema changes and no new native
provisioning slots are planned. Backup/rollback reserve is now an EXACT4GiB
policy constant in every closed admission/resource checker, not caller-selected.

I1 adds `hold_active_inputs(stack, plan)` and `sample_active_inputs(binding,
plan, *, previous=None)` in the new catalogue. The binding holds every explicit
input FD and the unique ancestor-directory FD union (no unrelated descendants
are crawled). Sampling returns the same six top-level fields as exact-slot
sampling, with absolute file/directory paths and observed full epochs,
logical/allocated sizes and hashes. Each file must fit its rounded explicit
physical slot; observed directory metadata must fit input_metadata_cap; the
actual measured active union plus complete new reservation must fit4GiB.
The existing plan.json control will now contain `{allocation, active_inputs}`;
parent report will additionally bind the active-input observation digest.

I2 adds a worker allocation checker at predetermined real phase BEGIN/END
boundaries, never per receipt/checkpoint. It scans the entire exact child work
slot with the new scanner. It conservatively keeps the COMPLETE reservation
for all other job/registry slots and metadata, including unreadable root
controls, rather than claiming credit from them. Required free space is
4GiB + complete job reservation - observed child allocated bytes +4GiB backup.
Every phase summary gains `allocation_before` and `allocation_after`, each
null only where a check was not reached due to failure; observed objects have
`logical`, `allocated`, `metadata_logical`, `metadata_allocated`, `free`,
`required_free`, `inventory_sha256`, `checker_cpu_ns`, `checker_wall_ns`.
Checker cost is included in phase-inclusive timings and separately reported;
the unchanged progress frame schema and helper limits remain unchanged.

I4 removes the unused admitted_run miniature. The named admission-order test
will drive actual main using explicit read-only/native-preflight fixtures,
reject the real admission call site, and fail if any real write/copy/launch
seam is reached. I1 physical overrun regressions also use this actual path.

RED/GREEN/final evidence and updated freeze pending; ownership not returned yet.

### Fix round1 implementation and covering evidence

I1 is implemented in the held-input binding/sampler and actual main. Logical
bytes, native st_blocks*512 per file and the unique explicit ancestor-directory
union are measured, not substituted with reservation values. Full native
epochs and physical allocation are compared again at parent rechecks. The
portable Windows branch explicitly lacks native physical-block authority;
its block values are allocation-shaped QA fixtures only. Membership is bounded
to 30000 files plus unique ancestors, depth32, without an unrelated crawl.

I2 is implemented by WorkerAllocation and PhaseRecorder at each actual phase
begin/end. Exact attempt-relative slots, directory metadata and complete
conservative outstanding reservation are checked, including at real copy
return before writer_open. No append checkpoint invokes the scanner. Checker
CPU/wall is included in inclusive phase time and separately reported. The
parent validates both non-null observations for every successful phase. Failed
checks produce failure progress; they cannot make success evidence. Existing
real writer/source cleanup remains attempted even when a checker refuses.

I3 now rejects any backup reserve other than exactly4294967296 bytes in the
closed retained-control validator, parent free-space checker and worker checker.
The regression recomputes retained hash, full allocation and plan digest for
0,4GiB-1,4GiB+1; none becomes acceptable through self-consistent rehashing.

I4 now exercises actual main with real temporary inputs/file descriptors and
explicit substituted native/read-only preflight. Actual Task60 rejection is
the boundary; write_new/copy_exact/launch_once are fail-on-reach traps, and the
real job directory remains empty. The unused admitted_run helper was removed.

T1 scope: only evidence/task61-native-prefix-run.ps1 was additionally changed.
It bounds template length to65536 before/after one ReadAllBytes, hashes that
held array against the unchanged literal pin, and strictly decodes that same
array with UTF8Encoding(false,true). Placeholder counts, stdin cap/hash and
all source/template pins are unchanged. T2 output-log hardening is explicitly
deferred; no SSH/native execution was performed. Root must mechanically repin
the final reviewed source/template artifacts before execution.

All focused commands below use the existing
`.pytest_tmp/qa-python312-c-01/Scripts/python.exe -B -m pytest`
`tests/test_native_context_receipt_diagnostic.py -q -p no:cacheprovider`, with
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and PYTHONDONTWRITEBYTECODE=1, and the shown
unique basename for both `--basetemp=.pytest_tmp/NAME` and
`--junitxml=.pytest_tmp/NAME.xml`.

- RED: NAME=task61-fix1-red-01; `-k 'rejected_admission or active_physical or fully_rehashed or actual_copy_phase'`.
  Actual chunk69ff99 exit1: `6 failed, 1 passed, 40 deselected in 0.56s`.
  I1 wrongly reached admission (both allocation cases), I3 did not raise, and
  I2 lacked WorkerAllocation (three cases). Actual-main I4 already passed,
  correctly demonstrating the existing production order, not a fabricated bug.
- GREEN: identical selector, NAME=task61-fix1-green-01. Actual chunkc55a89
  exit0: `7 passed, 40 deselected in 0.90s`, outer wall1.2588232s.
- Additional seams: NAME=task61-fix1-seams-01,
  `-k 'binding_rejects or transport_uses'`: actual exit1, four passed and one
  transport fixture invocation failed (PowerShell command arguments, not
  production). Corrected the fixture's subprocess argument delivery.
  NAME=task61-fix1-seams-02, same selector, actual chunkd82e2e exit0:
  `5 passed, 47 deselected in 1.13s`.
- T1 mutation RED: temporarily restored only the original hash/reopen lines
  with apply_patch, ran NAME=task61-fix1-t1-red-01 `-k transport_uses`, then
  restored the held-byte fix. Actual chunk66e699 exit1:
  `1 failed, 51 deselected in 1.00s`, real PowerShell child exit1 with
  `Ambiguous fixed prefix placeholders` after the fixture path changed.
  The test parses/executes actual acquisition and replacement statements,
  mutates only a temporary template after acquisition, and never reaches SSH.
- T1 prepare DryRun before QA source changes: actual chunk146037 exit0:
  `mode=prepare stdin_bytes=384409 stdin_sha256=d075f12fbc43c31c3dfda27ac001b7a0ceab2773d152531b450381d2e0416a59 dry_run=True`.
  Command: `& .superpowers/sdd/2026-09-10-context-capacity-recovery/evidence/task61-native-prefix-run.ps1 -Mode prepare -DryRun`.

The real-owner positive1024 regression now also uses the actual WorkerAllocation
checker, asserts two checks per phase (not per receipt), complete reserve and
visible included checker timings. Epoch/allocation regressions cover physical
drift still within its individual slot, input epoch, directory epoch and the
actual combined4GiB bound. These are portable evidence, not native approval.

Final focused source freeze, actual terminal exits and hashes follow below.

Self-review found no need to modify any existing owner/helper. Active binding
is also rechecked immediately after actual admission and before any preparation
write/copy. Workers retain full conservative reservation for unreadable parent
slots, which may reject an otherwise physically feasible run; this is deliberate
fail-closed accounting, not permission to reduce the backup/free reserve.
Repeated phase inventory/hash cost remains visible and inside unchanged CPU240
and wall240; native performance is still an unmeasured gate.

Full affected-module check (before final freeze), basename task61-fix1-check-01,
used the bounded subprocess command below with that basename. Session18979,
terminal chunke00333: actual child_exit1 and outer exit1, stderr empty,
`1 failed, 49 passed, 2 skipped in 98.36s (0:01:38)`, wall98.76599999999962.
The sole failure was a new test incorrectly requiring each Windows CPU-clock
delta to be positive. Actual1024, all phase checks and inventory assertions had
already completed. Corrected to nonnegative individual CPU deltas bounded by
inclusive time, with aggregate measured checker CPU strictly positive; positive
wall deltas are unchanged. This does not alter production timing or limits.

Post-change real prepare-DryRun is deliberately blocked by unchanged old Root
source pins: chunk811202 actual exit1, `Prefix held member pin differs:
tests/native_context_receipt_diagnostic.py`. No fallback/repinning or SSH was
attempted. This is the expected frozen-artifact gate, not T1 regression.

Frozen source SHA256 readback (before the final run):

| Owned file | SHA256 |
| --- | --- |
| tests/native_context_receipt_diagnostic.py | 22faafb79d08f956b11693106cf933f4e6c9869f755c6f3e23628b5f5cca17c1 |
| tests/native_context_receipt_diagnostic_catalogue.py | 8ebd29f82bd8c92a8601adf8a339f9eb27ddbdf7dcb02bcc0f61d56ea03012e8 |
| tests/native_context_receipt_diagnostic_worker.py | 0d7e1cce81e6b4395d249488df7bd8046d26e3d955e369f615733b212c50c902 |
| tests/test_native_context_receipt_diagnostic.py | 59db27907c2b2d9e33941a15410524b13cd1ea335b25f5bcb69503df9c04827f |
| evidence/task61-native-prefix-run.ps1 | 4ce1f3992b91f9f2b4ed2ba47d0ebc7183d2876060b63a20fa8e40306928315f |

Exact final command from the dispatch worktree:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& .pytest_tmp/qa-python312-c-01/Scripts/python.exe -B -c 'import os,subprocess,sys,json,time; env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",PYTHONDONTWRITEBYTECODE="1"); command=[sys.executable,"-B","-m","pytest","tests/test_native_context_receipt_diagnostic.py","-q","-p","no:cacheprovider","--basetemp=.pytest_tmp/task61-fix1-final-02","--junitxml=.pytest_tmp/task61-fix1-final-02.xml"]; start=time.monotonic(); result=subprocess.run(command,env=env,capture_output=True,timeout=240); print(json.dumps(dict(command=command,child_exit=result.returncode,stdout=result.stdout.decode("utf-8",errors="replace"),stderr=result.stderr.decode("utf-8",errors="replace"),wall_seconds=time.monotonic()-start),sort_keys=True)); sys.exit(result.returncode)'
```

The initially attempted final-01 (launch chunkb15fca/session24540, terminal
chunk1ee410) returned actual child/outer1, stderr empty, `1 failed, 49 passed,
2 skipped in 99.39s (0:01:39)`, wall99.86000000000058. Its only failure was the
same short-duration quantization in Windows monotonic_ns as well. The final
test now accepts nonnegative individual CPU AND wall samples, requires each
to fit inclusive time, and requires both accumulated checker times positive.
No production clock or accounting limit changed. Final test SHA above supersedes
the first freeze's 3dc7a81ad8e3160c8b5338ee7e4b0febbede28d3a9d14e5e9b90ec58d1598813.

Retained intermediate XML SHA256s (all `.pytest_tmp/`):

| XML | SHA256 |
| --- | --- |
| task61-fix1-red-01.xml | b726e419a47b57a293c1d8c73e02e10c70b4b8c977eb7d3300e8ca4a7ebf0fa9 |
| task61-fix1-green-01.xml | 33679e4c70664c5b781dc35a30e0f63b53c4b2d21c98e3d55b8a36279fc57c9a |
| task61-fix1-seams-01.xml | 3c9c709a38ac559a6591a089e3b74f821a1c4ee6a66632a992774b96b752bc8b |
| task61-fix1-seams-02.xml | c571ff2c2f611c32ae3c27d2675f22b64c5bdd998508e99a7a5bf350620feaba |
| task61-fix1-t1-red-01.xml | 7654caa9b2c8b51c4a96555f4c6469c15dbecd49f4cb2f88d266fb4b0918cdd1 |
| task61-fix1-check-01.xml | 9e9889aa8334373f71be5798f68b55eddce7567fe94156a8563bfe64c6b6a0a6 |
| task61-fix1-final-01.xml | 63c6ab78080856668341a4d700d7c09bdecc4406c298a1653e23408b92ae2807 |

Final run launch chunkf2ded0/session58858, terminal chunk0f1a82:

```text
child_exit: 0
outer/tool exit: 0
stdout:
........ss..........................................                     [100%]
50 passed, 2 skipped in 97.67s (0:01:37)
stderr: empty
outer wall_seconds: 98.07800000000134
```

Final XML `.pytest_tmp/task61-fix1-final-02.xml` SHA256:
`a177500a9d45be51616361f96b425caa08828dc9e5f961e039459def69185419`.
Post-run readback chunkbcc254, actual exit0, confirmed all five frozen
source/test/transport hashes above unchanged plus this exact XML. No source
or test edits followed that run; only this report was completed.

Fix round1 status: I1-I4 and T1 implemented and locally verified; independent
review remains Root's next gate. No native provisioning/execution or native
acceptance is claimed. Both native tests are intentionally skipped without
Root's prepared Linux protocol; physical st_blocks, UID/capability/DAC/guard,
child240/parent60, native reap/custody and full-baseline performance remain
separate. No full C/B, Source/D2, restore/deployment/release claim follows.
Transport T2 remains deferred Minor and stale pins deliberately refuse use.

Sole-writer return: I explicitly return ownership of the four Task61 QA modules,
this report AND evidence/task61-native-prefix-run.ps1 to Root. I will perform
no further writes without a new dispatch. Root owns independent review,
mechanical approved pin updates, Git/index and all native operations. No
Task58/full-repository suite, Git/index, network/server, install, cleanup or
subagent operation was performed in this fix round.
