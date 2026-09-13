## Task 61: Fixed native receipt diagnostic with durable phase evidence

**Placement and required design:** implement the concrete next native measuring
path, not a general growth/resume engine. Read the complete companion blueprint
`.superpowers/sdd/2026-09-10-context-capacity-recovery/task-61-driver-preflight.md`
(SHA6e96794d5a728a679f2868b55bc1ea3db9fdd8f09d2417700a6508f2fc8a2a66)
and Root's `task-61-root-native-preflight.md`; both were fully read by Root.
The decisions below resolve its open inputs and take precedence where narrower.
Task60 prerequisite is independently approved locally, not yet native-proven.
Task58 small ATP/WTA/late-cleanup acceptance remains closed and unchanged.

**Own exactly:** new `tests/native_context_receipt_diagnostic.py` (stdlib parent),
`tests/native_context_receipt_diagnostic_catalogue.py` (closed inputs/slots/progress
codec), `tests/native_context_receipt_diagnostic_worker.py` (guarded real owner
call), `tests/test_native_context_receipt_diagnostic.py` and `task-61-report.md`
in this plan's SDD workspace. No existing helper/product/test/generator edits,
source/price/model changes, Git/index, server/network/install/cleanup or subagents.
Root owns commit/review, catalogue/input provisioning and every native run.

**Unchanged global contract:** C SHA08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba;
B SHA498e63c5641adaccdd4d284fa9b57ad93c02ba834e9abd6bf4064636d6b12da1.
Active input4GiB, new complete QA/job8GiB, free4GiB plus outstanding allocations/
backup/rollback reserve; original per-value admission unchanged. One phase has
parent60CPU including its entire lifetime plus one worker240CPU/240wall,
AS2GiB,RSS<1GiB,combined diagnostic output<=1MiB,permanent300CPU charge. Original
kernel-start deadline<=3600s. This is diagnostic engineering evidence only;
full490000-growth preparation, global1800/3600 proof, C/B/restore/release remain.

### Exact input and held-code contract

Native baseline path `/var/lib/betboy-live-backup-ssfvf5xs/context-current.db`,
size270233600, SHA73ec16911c7d66e894a0f92c6600e3486e34b57c4176b30938638d3669146ffa.
Actual observed profile: page_size4096,page_count65975,encodingUTF-8,
journal_modedelete,auto_vacuum0,schema_version1,user_version0,application_id0.
Tables/counts: active_manifest1,artifacts33,context_contents100553,
context_observations100553,context_snapshots31,manifests2. No rollback table.
Artifacts: kind `tennis-live-winner-original-v1`31, `tennis-tour-state`2.
These are fixed metadata expectations; actual held bytes/header/profile/raw
inventory/old-row comparisons remain mandatory. No payload is exported to PC.

Fixed profile: kind `atp-heavy`, start0,stop1024, first_native_id
8000000000000000000,start_at `2026-09-12T00:00:00+00:00`, wta_fixture=null.
Check room for the complete490000-ID plan and all existing receipt event IDs/
clocks before appending, with bounded scalar iteration. No eager ID set or
collection of490000rows. Seed is explicitly synthetic native-format data:

```python
atp_fixture = {
    "competition": {
        "id": "8000000000000000000", "date": "2026-09-12T18:00:00Z",
        "surface": "Hard",
        "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False}},
        "competitors": [
            {"id": "1000000001", "athlete": {"displayName": "aaron t"}},
            {"id": "1000000002", "athlete": {"displayName": "aarts p"}},
        ],
    },
    "tournament_id": "189-2026", "surface": "Hard", "best_of": 3, "indoor": None,
}
```

The observed names do not resolve native identities; no predictor, History or
consumer is called in this diagnostic. The actual reviewed generator supplies
the1024 ordinary rows through its unchanged real normalizer. Successful physical
targets are101577receipts/contents, unchanged31Originals/31snapshots/2states;
not590553/199/199. Input range/clock expectations are rechecked, never imported
from the metadata report as authority.

Pins: Task60 admissionf0b0821195d6ebce89bc47e5d37f21dedc36fc8e223678816a932b1aae5d60ad,
generator584bd2c9c14aee3abe5b5dc2f537ebc25914cd7d63b7dabf6d0abb306798e2c9,
receipt_corpusfdbebbed9e0b14380d7226660f5f42ec9508ec2b04c727a856bb36747ae660d6;
all exact unchanged helper/old catalogue/worker/storage pins in the companion
blueprint bind reuse. Root loads only stdlib and the three existing registered
helpers. Compile reviewed admission/new catalogue/old catalogue as held
namespaces; no fourth helper import, hash-then-reopen execution or sys.path
fallback. Root never imports the worker, pytest or venv/product modules.

Use the companion's exact closed catalogue/profile/baseline/progress schemas.
New catalogue format `betboy-native-receipt-diagnostic-catalogue-v1`;
parent CLI is the exact ordered pairs `--manifest`, `--manifest-sha256`,
`--archive`, `--directory`, `--registry`, `--commit`, `--launcher-sha256`.
Worker argv is exactly `receipt-v1`; no selectable row count/tour/cap/retry mode.
Paths, commit and hashes must match the canonical manifest, not independently
select another source. Seed control<=64KiB; manifest/retained control<=8MiB each;
archive<=64MiB; member<=128MiB except explicitly streamed baseline/output slots.

Before coding declare exact signatures and closed result/allocation shapes in
the report for `inventory`, `bootstrap_source`, `launcher`, `validate_manifest`,
`sample_exact_slots`, progress append/parse, parent `main` and worker `run`.
Read-only inventory consumes the archive/commit, baseline and retained inventory,
exact existing registry/job paths; it does not create directories, copy code,
launch, import product or authorize a ticket. Parent reconstructs/rechecks the
exact Root-pinned stdin bytes against the same held archive/manifest members.

Define identity.input_digest as baseline.sha256; execution_digest binds the
complete code/dependency entries and explicit prefix identity; runtime_digest
binds actual interpreter/kernel/runtime-data identity; installation_digest
binds the bounded root-owned `/etc/machine-id` byte hash plus actual executable
identity (never the new job path, clock, profile, seed or attempt name).
Never output raw machine-id. profile_digest is the exact canonical profile hash.
plan_digest hashes the entire manifest excluding `admission`, avoiding a cycle;
retained_history_digest hashes the exact complete retained control bytes.
Recompute every mapping rather than trusting supplied hashes. Registry/job
paths must already exist under protected ancestors and be distinct. The job
must be empty; the registry must be empty on its first use, or contain only
the complete stopped cross-bound history admitted by the unchanged Task60
protocol. The fixed first diagnostic uses a fresh empty registry. Neither
the catalogue nor driver may erase or bypass retained registry history.

### Resource order and explicit child-only limit handoff

Use actual Task60 `admit_diagnostic(...)` once before any catalogue/code/baseline
copy or fork. Its snapshot is detached data with keys `admission` and `binding`;
binding contains `deadline_boot_ns` and the exact retained ticket. No raw budget
handle or self-refund. Recheck live admission around fallible phases. Respect
Task60's final crash-acknowledgement rule exactly; do not implement recovery.

Parent hardCPU60 is installed at startup and never raised; it counts setup,
all rechecks/output and cleanup. Parent FSIZE512MiB with smaller exact control
slots permits the needed worker inheritance. Only around the one actual
supervisor launch, install the companion's fixed trusted prefix on the exact
held `supervisor._child_run_python`, then restore it in the parent finally.
Original supervisor still forks and owns PID/pidfd/wait4. In its direct child,
before any capability/UID drop, verify fixed original callable/args/PID/PPID,
actual root IDs, inherited hard/softCPU60 and actual effective capability.
Set/read back CPU240, then call the saved original once with identical args.
Any prefix failure or unexpected original return must `os._exit(125)`, never
unwind into inherited parent admission/lock cleanup. No parent hard-limit raise,
timer substitute, arbitrary callback/worker or helper mutation is permitted.
This QA prefix is explicitly new executed code despite unchanged helper files.

Real native tests of this exact prefix must prove parent60 unchanged, child240
handoff followed by actual guard/SIGSTOP/readback, and prefix failure with
actual terminal reaping and no parent-owner cleanup. Portable tests may not
claim those kernel facts. Native test coordinators must be fresh secret-free
stdlib-only interpreters; do not run pytest/venv code as root. The test framework
may drive such fixed subprocesses, but no automatic sudo/SSH/native invocation
is allowed in ordinary local tests. Root explicitly provisions/runs native QA
after independent review, with bounded wall/CPU and retained terminal results.

Concrete test-only API clarification: `native_prefix_test(mode, *, root)` uses
only `/var/lib/betboy-receipt-prefix-task61-01`, with separately Root-provisioned
fresh `success`/`failure` subdirectories and one root-sealed stdlib-only
`probe.py`. Declare its immutable probe bytes/producer in the new QA module;
Root checks their reviewed hash before provisioning. No arbitrary probe source,
automatic sudo/SSH/install or extra diagnostic CLI mode. Each mode is a separate
fresh clean root interpreter with parent hard60. Positive test uses the actual
prefix and unchanged supervisor/guard/SIGSTOP/readback/reaping, argv exactly
`(sealed_probe, "receipt-v1")`; fixed small output then exit. Negative test may
bind the exact prefix to deliberately wrong expected parent PID solely within
this test entry, requiring actual child125 and reap without inherited owner
cleanup. No bypass flag is added inside the production prefix. Normal main
still binds its actual worker/admission and cannot choose the probe. Root
records these as isolated kernel protocol tests, not the1024-row execution,
real data authority, empirical proof or a new free preparation lifecycle.

M=512MiB main, M DELETE journal, L=1MiB two-bank ledger; reserve each in the
entire job before writes. Progress262144bytes, stdout128KiB, stderr8KiB, report/
failure/custody controls and allocation/metadata slack are separate exact slots.
Original sealed baseline may be unreadable by UID65534: if so the parent makes
one fresh root-owned0444 seal with protected searchable directories, counting
both copies. Never mutate permissions of the original. Stream per-slot files
above128MiB with that slot's explicit cap; do not widen the old archive/member
globals or use unbounded read_bytes/old walk for the large baseline/main.

Complete new job outputs/archives/copies/registry controls/journals/failures fit
8GiB; simultaneous actual admitted inputs fit4GiB. Prior QA/backup/rollback are
retained and freshly accounted against free4GiB plus outstanding allocations.
Do not double-count already occupied historical bytes as future growth or omit
them entirely. Retained manifest must enumerate a complete bounded namespace
or streamed per-root membership digest, with identities, logical/allocated
totals and honest accounting category/head/ticket where one exists. Bind
explicit new input/control slots separately to avoid a self-hashing inventory;
no implicit wildcard exclusions, unknown-file allowance or sparse savings.
Admission refuses missing/unstable/incomplete retained inventory or insufficient
reserve. Root's historical du totals are not this complete proof. No deletion.

**Retained-history input clarification after fresh native shape inspection:**
the preserved old QA root contains76236 entries including1932 intentional
symlinks and88 hardlinked regular entries. This is inert negative-test history,
not new code/source admission. Use a separate closed typed retained record:
`path`, `kind`, `identity`, `size`, `allocated`, `sha256`, where kind is exactly
`directory`, `regular` or `symlink`. Directory sha256 is null. Hash all regular
bytes through held no-follow identity, including exact nlink; for a symlink
hash its bounded raw link-target bytes (<=4096), lstat before/after and never
follow, open, import or authorize its destination. Other types reject.
Existing active input/code/job single-link/root-DAC rules stay unchanged.
No retroactive chmod or deletion of historical files. Bind complete ancestor
and membership epochs; historical writable metadata is not Source authority.
Root records count regular entries as `files`, directory entries as `directories`
and link entries as `symlinks`. Bound per-root total200000, all roots500000,
root count256, depth32, per-directory50000children and path2048UTF-8 bytes;
retain streamed hashing, fixed control/output/memory/CPU/file/64GiB aggregate
bounds. The old proposed30000 cap was an unimplemented QA-control choice,
not a product limit; it cannot require dropping preserved historical evidence.
Per-path allocated sums may conservatively count a hardlinked inode twice:
label this as occupied upper-bound bookkeeping, not unique physical usage or
future reserve. Fresh filesystem available bytes remains the free-space check.

Retained roots can contain multiple actual budgets: replace the companion's
single journal_head/ticket pair with exact root keys `path`, `identity`,
`membership_sha256`, `files`, `directories`, `symlinks`, `logical`, `allocated`,
`category`, `charged_cpu_ns`, `journals`. `journals` is a sorted unique list of
closed entries: `path` (relative), `identity` (complete BudgetIdentity),
`journal_head`, `ticket` (actual complete Reservation or null), `state`
(`stopped`, `pending`, `accounting-open`), `charged_cpu_ns`, `settled_cpu_ns`,
`category` (`historical-measurement`, `synthetic-protocol`, `unknown`). Root
explicitly declares known execution journals from retained evidence; similarly
named unit-test files are not presumed genuine executions. All descendants
still enter the complete byte/membership inventory. Replay each declared
journal read-only with the held pinned budget helper and compare its actual
identity/head/state/ticket; no historical reopen/reservation/settlement. A
poisoned pending journal stays pending and fully charged. Root charged_cpu_ns
is null if unknown unjournaled history prevents a complete cost total; even a
known total is historical accounting, never a full-C settled-cost claim.

Historical-label correction from fresh actual replay: the companion's1770CPU
is a conservative prior engineering allowance, comprising1680CPU in eight
primary journals plus90CPU of separate sealer allowances, not1770CPU journaled.
Two new Task60 protocol admissions each retain300CPU; six embedded older
roundtrip/recovery journal fixtures also remain and have explicitly synthetic
values. Exact16-journal readback and category distinctions are in
`task-61-known-journals-20260913.md`; these observations are not new lifecycle
credit and cannot replace the actual fresh retained inventory.

### Actual owner and persistent phase protocol

Open a genuinely sealed standalone read-only profiled TrackedConnection and
held transaction; inspect rollback header/companions before schema operations.
Use the actual `_configure_copy_reader` profile and unchanged actual
`build_receipt_corpus(source, profile.iter_receipts(0,1024), ...)` once.
No Source/D2 empty map, old-row subset or independent prediction substitute.
Preserve every actual normalization/profile/namespace/capacity/append/ledger/
commit/cold full typed-row comparison/hash/cleanup boundary.

Use the exact progress protocol and wrapper targets from the required blueprint.
One O_EXCL/no-follow held `progress.jsonl` lives OUTSIDE the corpus-owned
directory. Write-all/fsync frames before phase entry and after actual return;
creation also syncs the directory. Append calls are timed individually with
scalar counters but emit only predetermined0,64,...,1024 checkpoints. No
per-receipt frame/file inventory and no swallowed progress-I/O errors.
At most128frames,2048bytes/frame,262144bytes total; no raw receipt payloads.
Inclusive nested timings are not added as exclusive CPU. Real repeated cleanup
occurrences stay visible. Restore every instrumentation wrapper in finally.

After actual reaping, read/retain the one planned progress file and validate
the longest complete canonical/hash-linked legal prefix. An incomplete last
frame remains retained/diagnostic-only; a malformed complete frame rejects.
A prefix records a last phase/completed-call lower bound, not a committed
corpus or retrospective completion of an interrupted call. Stdout alone is
insufficient because the unchanged supervisor may stop without draining pipes.

Always retain actual NativeRunResult before success parsing. Accept complete
worker output only with actual exit0/no stop, exact counts/old inventories,
physical output/ledger hashes and terminal cleanup. Parent report stays
`native_pass=false`, external-terminal-observation-required. Root separately
checks complete native terminal/process/retained outputs. UnreapedChild retains
the same pidfd/custody/full charge with existing explicit stopped-operator path;
failed report/progress I/O must not lose custody. No parent-death auto-reaping
claim, automatic retry or marker/app publication.

### Focused TDD and handoff

- [ ] Declare interfaces/closed formats in report; write genuine missing-path
  RED tests and exact closed-input/guard-before-import/order tests. Include
  `test_rejected_admission_never_copies_or_forks`,
  `test_real_sample_calls_actual_corpus_once`,
  `test_native_prefix_failure_never_unwinds_parent_owner`, and
  `test_killed_worker_retains_only_verified_progress_prefix` as named behaviors.
- [ ] Implement the fixed pure codecs/catalogue and stdlib parent, then the
  guarded actual worker. Reuse the pinned old functions only where their
  actual contracts match, not through modified old globals or copied fake owners.
- [ ] Exercise real small source/owner fixtures, full old-row and corruption
  rejection, actual large-old-value compatibility, streaming>128MiB slots,
  complete logical/allocated/free/retained accounting and path/identity drift.
  Cover all fixed prefix fields and original callable, native-only success/
  failure/reaping, progress sequence/stack/hash/bounds/truncated/malformed tails,
  actual partial write/fsync failures, and no success on signal/nonzero/unreaped.
- [ ] Final focused new module once after changes, fresh XML/basetemp, existing
  `.pytest_tmp/qa-python312-c-01/Scripts/python.exe`, disabled plugins/bytecode/
  cache, bounded subprocess with actual child/outer exit/stdout/stderr/session.
  No unchanged Task58 or full repository suite; native-only tests explicitly
  skip without prepared root/environment, never silently pretend to run.
- [ ] Freeze/report exact source/test/XML hashes, APIs/schemas/TDD output,
  reused and unchanged pins, known native/whole-C limits and sole-writer return.
  Root commits exact files, reviews from dispatch BASE, then alone provisions
  and runs native checks/one admitted diagnostic. A native stop yields evidence
  and a concrete next repair, never a hidden reduced profile or new free budget.
