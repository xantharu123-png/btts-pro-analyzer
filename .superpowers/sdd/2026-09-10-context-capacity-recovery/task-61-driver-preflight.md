# Task61 — fixed receipt-diagnostic driver preflight

13 September 2026. Blueprint only. Read Task60's final public brief, not its
in-progress implementation. No code/test/native/Git/network action; only this
report was written. Root selects final native inputs and writes the task brief.

## Narrow deliverable and unchanged owners

Proposed implementation owns exactly these new files:

- `tests/native_context_receipt_diagnostic.py` — fresh stdlib root parent.
- `tests/native_context_receipt_diagnostic_catalogue.py` — fixed manifest,
  held-byte bootstrap, exact slot/allocation readers and progress codec.
- `tests/native_context_receipt_diagnostic_worker.py` — guarded real Task48 call.
- `tests/test_native_context_receipt_diagnostic.py` — focused portable wiring,
  real small-owner and explicit native-only cases, never a Task58 rerun.
- `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-61-report.md`.

Do not edit Task60, the old chain/catalogue/worker/tests, supervisor, guard,
budget helper, generator, storage owners, specifications or productive paths.
One worker; exactly `atp-heavy` `[0,1024)`; M=536870912 and L=1048576 bytes.
No History, model calculation, new Original/snapshot, B key or publisher.

Freshly read/hash-checked dependencies for this blueprint:

```text
tests/native_context_chain.py
73befce90e1087c27350258387c1454527838b7242b767227bafd69cb4f3fff7
tests/native_context_chain_catalogue.py
48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935
tests/native_context_chain_worker.py
210226b3fd40a9c9bbe8090c9c52a0a56840827e8e75bcd610e4544826d5b209
context_preparation_supervisor.py
c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8
context_preparation_process_guard.py
62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4
context_preparation_budget.py
fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478
context_storage_v2/receipt_corpus.py
fdbebbed9e0b14380d7226660f5f42ec9508ec2b04c727a856bb36747ae660d6
context_storage_v2/copying.py
15c031ad5727c69b218d3487bc981ad3126e9e285d254822e94597ade09f0b23
context_storage_v2/inventory.py
7e099cd9ed5e5b336519a23cc891e85c2136dda9fa6324c6f433f61bb37e967b
context_storage_v2/receipt_append.py
e96b807b2b003b00b740b0b64ba48d86ac3fd5c930ce11bdf2a40b5436fa06e9
context_storage_v2/sqlite_profile.py
05898adf9782ff06e2edcf33d45c94dd6ecce232ddba1f81ffcfaf65fca3d8bc
tests/context_growth_profile.py
584bd2c9c14aee3abe5b5dc2f537ebc25914cd7d63b7dabf6d0abb306798e2c9
```

Task60 implementation pin is deliberately unresolved until independent review.
Root reports reviewed/pushed Task59 commit `d4491d3`; this preflight did not run
Git to independently inspect that publication.

## Actual reuse, and exact old assumptions to avoid

Load the old pinned catalogue into a held compiled namespace with non-main
`__name__`; reuse `canonical`, `decode`/`pairs`, `sha`, `integer`, `relative`,
`records` for code/dependency records, `archive_members`, `opened`, `identity`,
`file_record(path, maximum=...)`, `data_bytes` for bounded control files,
`allocated_slot`, and exact timezone helpers when their literal paths match.
This is reuse of the actual functions, not changing their globals to pass a
different workload. Root executes only stdlib and pinned budget/supervisor/guard
helpers. Compile Task60 into its supported held namespace, not an extra
`sys.modules` import that violates supervisor `_require_native_owner`.

New fixed functions are required for manifest validation, bootstrap/launcher,
resource/retained-input plan, baseline copying if needed, exact-slot workspace
sampling, result parsing and the worker entry. Old `REQUIRED`, `TASK54_SHA`,
`ATTEMPTS`, `attempt_slots`, `resource_plan`, `original_input_plan`,
`validate_manifest`, `bootstrap_source`, `Window`, `accept_result`,
`invoke_cases`, `PROPERTY_KEYS` and late-cleanup/two-tour protocol are **not**
receipt-diagnostic interfaces. Keep their small90CPU/4MiB contract unchanged.

Important actual file-size coupling: old `copy_file` and `walk` default to
MEMBER_CAP=128MiB; `workspace_sample` calls that `walk`. They reject the
270233600-byte baseline/copy even when a slot is512MiB. Do not raise old globals
or general archive-member caps. New `sample_exact_slots` must stream each
declared file with `file_record(path, maximum=that_slot_cap)` and bind every
directory, file type/link, logical/allocated size and full hash. A new baseline
copy, if needed, similarly uses an explicit baseline-sized streaming limit,
O_EXCL/no-follow held inputs and all retained failure bytes. Never `data_bytes`
the baseline or reuse Task54 `_sha256`/`_table_rows`, which materialize data.

Reuse the exact `run_single_process((absolute_worker, "receipt-v1"), uid=65534,
gid=65534, cwd=attempt, workspace_fd=held_attempt_fd,
file_size_bytes=536870912, cpu_seconds=240, wall_seconds=240)` once. The parent
must leave enough of the original job deadline for that240-second window plus
bounded cleanup/readback; insufficient remainder is STOP, not a fresh deadline.
Do not change output/reaping/guard internals or suppress their stop reasons.

Worker guard-before-product, clean assertion-enabled `-I -S -B`, capability/
UID/GID/thread/no-new-privileges/seccomp/dumpability readbacks and exact sealed
timezone/source-only import restrictions follow the real existing worker.
Its `require_guard` constants and `run`/`invoke_cases` cannot be called unchanged.
If dependencies/timezone files are reused from another root seal, explicitly
bind those exact roots in new audit/reader functions; old functions assume
`seal/dependencies` and `seal/runtime-data`. No ambient venv/fallback path.

## Closed inputs and identities to freeze before implementation acceptance

Use a new catalogue format `betboy-native-receipt-diagnostic-catalogue-v1`.
Its exact top-level keys are `format`, `commit`, `archive`, `code`,
`dependencies`, `dependency_root`, `packages`, `timezone_data`, `runtime`,
`baseline`, `profile`, `retained`, `allocation`, `admission`. Bind canonical
bytes and reject unknown/duplicate keys, malformed integers, path aliases,
unordered/duplicate members and floats/nonfinite JSON. Seed booleans/null are
allowed only by their explicit schema; integers never accept bool.

Keep archive/code/dependency/timezone/runtime record shapes and bounded counts
from the old catalogue where applicable. Add all new executable files and
reviewed admission/generator/Task48 pins; bootstrap contains exactly new
parent/catalogue, reused old catalogue, reviewed admission and three unchanged
helpers. Root verifies all literal sources equal archive bytes and hashes the
reconstructed exact stdin. Worker code is never imported by root.

`baseline` has exactly `path`, `size`, `sha256`, `page_size`, `page_count`,
`encoding`, `journal_mode`, `present_tables`, `expected_counts`. Path is the
exact absolute sealed server-side file; source bytes never leave the server.
Root's current size/hash are270233600 and
`73ec16911c7d66e894a0f92c6600e3486e34b57c4176b30938638d3669146ffa`.
Expected counts bind100553receipts,31Originals,31snapshots and2tour states.
Present table names are the actual six, not invented here; optional rollback
table is absent. Page profile and exact named count selectors remain Root
inputs. They are metadata expectations, not permission to skip real inventory.
Native held FD/path epochs and root DAC are observed/bound at admission rather
than copied from an old stat report as current evidence.

`profile` has exactly `kind`, `baseline_sha256`, `start_at`, `first_native_id`,
`atp_fixture`, `wta_fixture`, `start`, `stop`; fixed kind=`atp-heavy`, start=0,
stop=1024, wta_fixture=null. `start_at` is canonical aware UTC, first_native_id
an exact positive signed64 integer with room for the entire490000-ID plan.
ATP seed is the reviewed Task59 **mapping**, not a bare competition:

```text
atp_fixture = {
  competition: actual native scheduled-singles fixture,
  tournament_id: nonempty string,
  surface: Hard|Clay|Grass|Carpet|null,
  best_of: 3|5,
  indoor: boolean|null
}
```

Pin seed/control bytes inside the manifest allowance; an explicit64KiB QA-seed
limit is acceptable for this fixed synthetic control, never for old DB values.
The unchanged generator performs actual normalization. This slice consists of
ordinary filler rows: native IDs first_native_id..+1023, ATP, tournament189-2026,
observations start_at..+1023microseconds, schedules start_at+18hours. The required
seed still gets validated and binds the full future plan; no consumer descriptor
is executed. Root must choose the actual seed/namespace/clocks and substantiate
their noncollision with the held baseline, without eagerly collecting490000IDs.

`retained` binds an exact reviewed inventory path/hash and its bounded canonical
content: retained job/file identity, logical and allocated bytes, CPU accounting
category, journal head/ticket where actually present. Historical1770CPU durable
reservations are distinct from CPU20-hard/3.247115605CPU metadata observation
which had no journal. Unknown unjournaled historical cost stays labeled unknown,
not imported as a settled full-C cost.

`allocation` binds the complete exact file slots, metadata/slack slots, original
seals and physical totals described below. `admission` binds registry_directory,
job_directory, purpose, profile_kind, complete BudgetIdentity, plan_digest and
retained_history_digest. Define the acyclic plan_digest as the canonical hash
of the full manifest excluding its `admission` field; identity.profile_digest
binds the exact profile, while other identity fields bind actual input,
execution/runtime/installation. Validator recomputes those mappings; supplied
hashes are data, not a Source seal or execution authority.

## One-shot order, whole storage, and the unresolved inherited-limit issue

Parent starts fresh env-i with original `/proc/self/stat` kernel-start tick,
boot ID and boot clock; preserve start+3600 and Task60's effective minimum
deadline. Root prepares the empty protected registry/job slots as required;
account their setup/metadata, do not create another job on admission failure.
Hold/read/hash existing manifest/archive/baseline/retained seals for identity
and capacity admission before writes. All root startup work counts toward its
whole60CPU lifetime. Then call reviewed `admit_diagnostic` exactly once with
the final bound plan/history. Only after its durable300CPU ticket and live
`assert_admitted` may catalogue/code/input copies or worker launch occur.
No raw budget access, settlement, refund, reopen or retry. Assertions surround
subsequent fallible phases; close must retain300 and cross-bind terminal stopped
history. Partial close does not become success. Follow the exact Task60 crash-
acknowledgement ruling; this driver must not implement a competing recovery API.

**Exact reviewed prefix needed:** unchanged guard `_install` refuses an
inherited hard limit lower than the requested child limit. Parent
RLIMIT_CPU=(60,60) before the unchanged supervisor's fork therefore makes
worker240 impossible after UID drop. Old90/90 did not expose this. Likewise
old parentFSIZE128MiB blocks child512MiB. ParentFSIZE can be512MiB with separate
small control-file slots; that does not raise the child's512MiB plan.
Choose a narrowly pinned QA prefix around actual supervisor._child_run_python,
not around os.fork. Before the one launch, save the exact held original function
and install the new parent's fixed wrapper; restore the original in the parent
finally. Original supervisor still calls original os.fork and retains its normal
PID/pidfd/wait4 path. ONLY its direct child enters this wrapper, before the
original drop/guard routine. Verify PID differs from the recorded parent and
PPID matches, actual root IDs, fixed argv/UID/GID/limits, and inherited CPU
(60,60); call resource.setrlimit(RLIMIT_CPU,(240,240)) and read back exactly.
Then call the saved original _child_run_python exactly once, without altering
arguments. Any prefix exception or unexpected original return must os._exit(125),
never unwind into inherited parent admission/lock/context cleanup. Do not
release inherited registry FDs before the original's existing close-all path.
Parent hardCPU remains60 for its whole lifetime; no parent-side limit raise or
timer substitute. ParentFSIZE512MiB is the simpler fixed inheritance choice.

This is an explicit execution change in new QA parent code despite unchanged
helper file bytes; bind prefix bytes/version in manifest execution identity and
test the exact executed wrapper, not an equivalent stand-in. Raising a hard
limit requires effective CAP_SYS_RESOURCE in the initial user namespace, not
merely numeric UID0. Root's08:47:04UTC ordinary sudo observation showed UID/GID0,
CapPrm/Eff/Bnd=000001ffffffffff, NoNewPrivs0/Seccomp0; it is not the future exact
parent or initial-namespace proof. Mandatory tiny native tests under that exact
launch environment establish parent60 unchanged, successful child240 raise,
subsequent actual unchanged capability drop/guard/SIGSTOP/readback, and failed
raise -> exit125 -> actual parent reaping with no inherited owner cleanup.
Also test wrong PID/PPID, args/limits, altered original callable and forced
prefix exception. Portable mocks alone cannot establish this capability seam.
If exact kernel permission is absent, STOP; do not relax60/240/300 or substitute
an unreviewed privileged launcher. No such native test was run by this preflight.

Whole storage includes original sealed baseline S, fresh Task48 main M,
rollback journal M, ledger L, progress journal, every retained failure,
archive/code/dependency/timezone originals and copies, manifest/launcher/
output/admission/registry journals, directory allocation and backup/rollback
reserve. Reuse a root-sealed immutable baseline/dependency tree when exact
fresh held complete reads/hashes/DAC prove it; sharing eliminates a copy, not
active bytes or verification. If a new baseline seal is required reserve both
original S and copy S. Never count per-file FSIZE as a physical quota.

Check the entire NEW preparation-job QA/build/output allocation against8GiB,
including all of that job's retained failed attempts, not8GiB per child. Check
simultaneous admitted input against4GiB, and fresh free bytes against4GiB plus
all still-outstanding allocations and backup/rollback reserve. Prior engineering
jobs/backups remain physically accounted in the fresh retained inventory and
available/reserved-space calculation; do not reclassify all historical QA as
newly allocated by this job, or count already occupied bytes twice as future
growth. Existing reused seals remain active inputs even when not newly copied.
Root's fresh read-only aggregate observations were7747723264allocated bytes in
`/tmp/betboy-context-qa.9xr68INa`, about1263595520 across five chain jobs and
12530085888free bytes. These aggregates are neither a complete per-job plan nor
an8GiB pass; exact retained membership/allocation and reserve are still required.
No per-child3GiB proxy, reset of failed files, automatic deletion or assumed
sparse savings. Root/worker quiescent samples use the new exact-slot scanner;
unchanged Task48 per-input capacity checks remain. Full retained inventory/hash
scans and rechecks consume actual parent60; if they exceed it, stop rather than
skip expensive validation. This report does not establish current available
space or promise that the whole retained union fits.

## Worker call, phase instrumentation and kill-safe diagnostic prefix

After guard/import admission, open the exact sealed source with a profiled
read-only TrackedConnection and held transaction; check standalone rollback
header/companions and actual page/encoding profile before unsafe SQLite reads.
Call unchanged build_receipt_corpus once with unchanged limits and exact
Task59 iterator. C1 copy, held-source/inode/namespace checks, normalization,
SQLite profile, per-item checks, append owner, cumulative ledger sort/strict
membership, single commit, complete old typed-row/cold-output comparisons and
all terminal hashes/cleanup remain mandatory. No16MiB old-value limit, SQL
length override, fabricated table, protected-empty map or Source/D2 ticket.

Wrap actual functions only in the worker, with original callables pinned before
wrapping: `receipt_corpus.copy_legacy`, `_Build.open_copied_writer`,
`_Build.append_one`, `_Ledger.finish`, `_Build.close_writer`,
`_Build.verify_complete`, `_hash_file`, and `_Build.run` as the outer boundary.
Every entered original is called exactly once with original args; return and
exception semantics are preserved, wrappers restored in finally. Count an
append only after original append_one returns; finalize/hash/cleanup wrappers
may repeat because real failure cleanup does, and occurrence numbers must
record that rather than assuming a fabricated single happy path. Instrument
generator production separately if needed; do not confuse time fetching a
normalized item with time inside append_one.

An exact finite phase protocol can use `worker_setup`, `profile`, `source_open`,
`corpus_run`, `copy`, `writer_open`, `append`, `ledger_finish`, `writer_close`,
`cold_verify`, `hash`, `source_close`, `worker_finish`; stack depth<=8 and
occurrence<=16. Nested inclusive timings are labeled, never summed as exclusive
CPU. Predeclare append checkpoints at0,64,...,1024; no frame per receipt.
Phase wrappers emit begin before original entry, end only after actual return,
or fail while preserving the original exception. Append_one wrappers instead
collect scalar timing/counts for every real call but emit only those fixed64-row
checkpoints, one append-phase begin/end and one bounded failure frame; no
per-row begin/end frames. Hash occurrences inside copy remain nested records
with a prevalidated bounded event count. A progress-I/O error prevents
normal acceptance and retains files; it may not be ignored to finish a run.

**Stdout alone cannot preserve the last phase on SIGKILL:** actual supervisor
may kill/reap and unregister pipes without fully draining on a stop reason.
Keep its interface unchanged. Add one fixed `progress.jsonl` **outside the
corpus-owned directory**, since `_Build.namespace` rejects extra files inside.
Create it O_EXCL/no-follow in the one private child work slot, hold its FD and
identity, append bounded canonical frames with write-all and fsync before
entering each phase/checkpoint; fsync its directory after creation. No overwrite,
truncation, alternate path, log repair, resume authority or receipt payloads.

Frame envelope has exactly `format`, `sequence`, `previous`, `body`, `sha256`;
format=`betboy-receipt-diagnostic-progress-v1`; body exactly `event`, `phase`,
`occurrence`, `depth`, `completed`, `cpu_ns`, `wall_ns`, `phase_cpu_ns`,
`phase_wall_ns`, `submitted`, `new_contents`, `new_receipts`, `exception`.
Counters/times are bounded exact nonnegative integers, completed<=1024;
exception is null or bounded class name, not a traceback or old payload.
Sequence starts0, previous starts64zeroes, hash covers canonical envelope
without sha256. Use at most128frames,2048bytes/frame and262144bytes/file.
Terminal output slot is bounded128KiB, stderr8KiB; reserve/logically count
progress plus stdout/stderr under the unchanged1MiB output envelope even
though the supervisor itself measures pipe bytes only. No per-row filesystem
inventory or output; at most16 append checkpoints and bounded phase events.

After actual child terminal/reap, parent reads the **one planned** progress
file under held no-follow identity with262144-byte bound, retains exact raw
bytes and parses its longest complete canonical/hash-linked legal prefix.
A truncated final frame is retained and labeled incomplete; malformed complete
frames, sequence gaps or an impossible phase path reject the diagnostic.
No frame is inferred if killed before its durable write. The last prefix gives
last recorded phase and completed-pair lower bound only: SQLite commit may not
have happened, and a kill after an original returned but before end emission
does not retrospectively prove that phase completed. Both file and pipe bytes
are observations from a child, not native truth or reusable authorization.

Normal stdout contains one closed `betboy-native-receipt-diagnostic-result-v1`
record: exact plan/baseline/generator/driver identities; completed1024; actual
ReceiptCorpusResult scalar counts and source/output/ledger inventories/hashes;
phase scalar summary and progress head/count; source/worker cleanup status.
No raw rows, features, library-map dump or giant file inventory. Require actual
new contents=new receipts=submitted=1024, final receipts101577, unchanged
31Originals/31snapshots and old bytes; no590553/199 claim. Parent reads/hash-
checks actual output files after reap, rather than trusting this JSON alone.

## Terminal evidence and focused acceptance tests

Always retain NativeRunResult before attempting success parsing: actual exit,
stop_reason, stopped-kernel readback, childCPU, supervisor-parentCPU interval,
wall, peakRSS, minimumfree, maximumsamplegap and exact bounded stdout/stderr
prefix/hash. Overall parentCPU is its actual whole process lifetime, not merely
NativeRunResult.parent_cpu_ns. Normal report says external-terminal-observation-
required and native_pass=false; admission terminal entry is not a native pass.
Root additionally observes actual launcher/SSH/process terminal, full output
hash/readback and no live child before accepting this diagnostic only.

On UnreapedChild, preserve same pidfd custody and permanently retain charge;
disable a wall alarm before report/journal I/O as in the existing custody seam.
Do not abandon the child because progress/report writing failed. A hard parent
death cannot run Python cleanup: external Root custody/readback remains required;
do not claim parent-death auto-reaping not provided by current supervisor/guard.

Focused RED/GREEN tests must prove: closed manifest/seed/full-profile ID arithmetic;
correct held bootstrap/pins and no forbidden root imports; rejected admission
precedes copy/fork; exact single child; true Task48 call/unchanged per-input checks;
source/table/ledger mutation failure; real old large-value read remains allowed;
baseline>128MiB streaming slot path (not globally widened archive caps);
logical/allocated/retained/free accounting; ignored or extra file rejection;
one-shot failure/close semantics through reviewed Task60 API; progress bounds,
partial write/fsync failure, legal truncated tail and illegal complete frames;
real child termination leaving a prior durable progress prefix; no final-only
success on signal/nonzero/unknown reap; complete outer exit evidence. Portable
fixtures test orchestration, not native costs or Linux root/lock proof. Native
tests for the exact60/240 inherited-limit ruling are mandatory before launch.
Do not repeat Task58 small consumer acceptance or a whole-suite run for this QA
driver. All failed artifacts remain retained in its actual resource accounting.

Remaining concrete inputs: final reviewed Task60 pin/snapshot schema; Root's
CPU fork-time ruling; exact sealed baseline path/page/table/count contract;
UTC clock/ID/ATP seed; reviewed source archive/runtime/sealed dependency roots;
fresh complete retained inventory and8GiB/free4GiB plan; empty protected registry/
job slots; exact manifest/bootstrap hashes and external terminal procedure.
No capacity, B, full-profile deduplication, restore or release claim follows.
