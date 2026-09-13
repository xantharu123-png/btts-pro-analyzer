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
