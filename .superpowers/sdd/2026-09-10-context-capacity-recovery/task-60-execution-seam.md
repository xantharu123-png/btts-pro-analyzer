# Task60 — next executable C growth seam

13 September 2026. Read-only architecture recommendation; only this document
was written. No product/test changes, test execution, Git or native launch.
Task48 copy/append/cold verification, Task51 consumer and Task58 small native
ATP/WTA/late-cleanup acceptance remain closed in their reviewed scope.

## Decision: quantitative receipt-only native diagnostic first

Implement one narrowly versioned QA driver around the **unchanged actual**
`build_receipt_corpus`; do not implement a general existing-path/resume owner
before measuring its actual baseline copy, per-receipt work, ledger finish and
complete cold verification on Linux. Task55 Windows timings cannot decide
which boundary dominates. Task58 measured small fixtures, not this baseline.

The diagnostic has exactly one predeclared Task59 `atp-heavy` slice
`iter_receipts(start=0, stop=1024)`, one fresh private output and no automatic
retry. 1024 is a diagnostic sample count, never a payload limit or acceptance
profile. Do not increase it in response to observed speed during that run.
It deliberately does not build History, Original or snapshot additions.
If even the real full-baseline fixed work cannot finish, preserve its measured
phase/stop evidence; do not shorten old coverage or restart a timer.

## Exact call and observations

After Task59's interface has actually passed independent review, freeze its
baseline digest, UTC start, first native ID and ATP seed, then call:

```python
profile = build_growth_profile("atp-heavy", baseline_sha256=baseline_sha256,
    start_at=start_at, first_native_id=first_native_id,
    atp_fixture=atp_fixture, wta_fixture=None)
result = build_receipt_corpus(held_source,
    profile.iter_receipts(start=0, stop=1024),
    expected_source_sha256=baseline_sha256, workspace=whole_job,
    owned_directory=fresh_corpus_slot, main_cap_bytes=M,
    ledger_cap_bytes=L, limits=DEFAULT_LIMITS)
```

`held_source` is the real profiled read-only `TrackedConnection` with a held
transaction over a genuinely sealed server-side baseline, not the writable
live DB, a hash label or a `ReceiptCorpusResult` converted to authority.
Root currently reports 270233600 bytes, SHA256
`73ec16911c7d66e894a0f92c6600e3486e34b57c4176b30938638d3669146ffa`,
100553 receipts, 31 Originals, 31 snapshots, two tour states and six present
tables. The optional rollback table is absent: do not synthesize or require it.
These are Root-supplied current observations, not this document's new scan.

Proposed diagnostic slots are M=512MiB and L=1MiB, with actual source plus
M plus L checked against the 4GiB active-input envelope, M plus DELETE-journal
M plus L and allocation/metadata/control/code/dependency slots charged to the
whole 8GiB workspace. They are not full-growth size predictions. The ledger's
actual 40-byte header and 41-byte entries use **two** regions inside L; at
most two entries per submitted pair gives 167976 bytes of required reservation
for this sample. Actual ledger length may be larger because its second bank
starts at the capacity-based offset; reserve L, not that minimum. Native
FSIZE=M must be read back; old per-value readers retain their current limits.

Use a new fixed receipt-diagnostic command/result version, not `ATP` relabeled
inside the existing Task54 acceptance protocol. Preserve the irreversible
guard and real supervisor; the existing chain's 90CPU/4MiB, fixed sample slots,
`PROPERTY_KEYS`, callable pin, two tours and late-cleanup assertions remain
its own small acceptance contract. New catalogue admission must explicitly
include the sealed baseline's held file/copy identities and byte hash, generator,
driver and complete existing code/dependency/timezone closure. No remote data
or model keys are copied to this local workspace.

Collect real process CPU/monotonic phase deltas around `copy_legacy`, each
actual `_Build.append_one`, `_Ledger.finish`, commit/close,
`_Build.verify_complete` and terminal hash/cleanup. QA-only wrappers must call
the original exactly once, preserve exceptions/results and all checks, never
replace normalization, source/namespace/profile checks or capacity traversal.
Accumulate scalar counts/times only; bounded failure output includes phase and
completed-pair count, but never certifies uncommitted progress. Native parent
evidence separately includes actual child exit/reaping, CPU, wall, RSS,
AS/FSIZE readback, output, and whole-job logical/allocated/free observations.
Do not derive real completion from a timeout wrapper's exit or child JSON alone.

Successful result must physically prove 1024 submitted/new receipts and
contents (otherwise the prevalidated namespace assumption was false), exact
source preservation, ledger membership, all old typed bytes and cold output
inventory/hash. Expected receipt target here is 101577, **not 590553**;
Originals/snapshots remain 31/31. Existing full cold comparison stays mandatory.
Root independently reads retained native terminal/results before accepting
even this diagnostic scope.

## Mandatory launch prerequisite: one job-wide admission owner

The current `native_context_chain.py` is not reusable global accounting:
`Window` starts a fixed 600-second diagnostic window, its identity includes a
new job directory/archive, `ReservedActions` insists on one 300CPU charge, and
completion calls `stop_unmeasured`. `PreparationBudget` is accounting only;
`settle_claim` does not authenticate measurements, and recovering a pending
ticket is permanently blocked. Creating another directory/journal does not
make another 1800CPU/3600wall allowance lawful.

Before any new native launch Root must establish protected registry admission
for the exact baseline/execution/runtime/profile lifecycle, original deadline,
retained previous attempts and remaining CPU/workspace. Task58 records 1500CPU
reserved across Task57/58 plus 270CPU Task50 diagnostics; these remain retained.
Their assignment to the precise new lifecycle cannot be inferred from the
numbers or silently discarded; neither a free 1800CPU nor a confirmed usable
30CPU is asserted here. An expired/stopped matching lifecycle is a STOP, not a
new name. Registry/accounting uncertainty blocks launch, not local QA coding.

Root additionally reports a fresh metadata diagnostic with CPU20 hard and
actual3.247CPU; record its20CPU reservation separately from the1770 engineering
diagnostic reservations. None establishes whole-C accounting and none refunds
an earlier journal. A genuinely different, explicitly declared baseline/profile/
execution diagnostic can be a new bounded job; changing a directory, slice,
attempt name or clock to retry the same job cannot. Engineering diagnostic
history and a full-C preparation certificate are distinct records and claims.

**Smallest prerequisite before launching this driver:** add a root-owned durable
diagnostic admission registry, not B signing keys, proof reuse or a publisher.
Its narrow proposed interface is `admit_diagnostic(registry_dir_fd,
request_identity, plan, *, existing_job_id=None)` returning a live held owner,
not a serializable permission token. `request_identity` binds diagnostic-purpose
version, actual baseline bytes, complete deterministic profile definition
(including seeds/clock/ID range), actual executing code/dependency/runtime
identities and fixed resource plan. The selected slice is bound in the plan,
but slice/attempt/output directory cannot become an alternate identity for
retrying an already admitted request. Registry request/attempt lineage must
make that explicit; Root reviews genuinely changed input/execution identities,
never auto-renames a stopped job.

Acquire a root-owned, non-group/world-writable ancestor chain, no-follow held
directory/file descriptors and an exclusive OS lock over registry lookup and
creation. Before work, fsync a bounded canonical entry binding the unique
request, actual job directory identity, immutable reservation plan, original
kernel/boot-inclusive start/deadline and exact `PreparationBudget` identity,
path and current head. On existing identity, open the existing journal only;
missing, replaced, truncated, stale, pending-recovered or stopped state denies
admission rather than regenerating it. Cross-bind updates crash-conservatively:
an ambiguous registry/journal transition stays charged and blocked, never
repairs/truncates. Hold the live registry lock/owner for the diagnostic. Record
the previous engineering diagnostics and this new job as separate immutable
entries with their retained charges and actual files; no need to import them
as a fabricated settled whole-C ticket. This supplies local root namespace/
anti-retry custody, not privileged whole-VM rollback protection or Source truth.

Before admission, the plan inventories **all** retained QA attempts, current
new-job outputs, controls/journals, original seals and required backup/rollback
reserve with logical and allocated sizes; reserve outstanding M/journal-M/L,
metadata and outputs in the fixed8GiB new-QA envelope and maintain free4GiB
throughout. Existing root-sealed immutable dependencies may be shared only
after fresh complete held read/hash/identity checks; their bytes remain in
active-input and retained-workspace accounting. Sharing avoids another copy,
not validation or a fictitious capacity release. This is the small registry/
admission work needed by the diagnostic, independent of future B proofs.

A single root owner must reserve the **whole possible next phase**, including
its own startup, catalogue/copy/check/report/cleanup work and all descendants,
before that phase's work. CPU300 is the worker ceiling, not permission to
reserve300 for a child and leave parent CPU uncharged; choose the child bound
inside the admitted complete-phase reservation. Maintain the job-start clock
including preparation before journal creation. Only actual trusted quiescent
whole-job measurement may settle a ticket; child-only CPU, QA JSON or public
digests cannot authorize refunds. If complete measurement is unavailable,
retain the full reservation and stop. Failed files and backup/rollback reserve
remain in the same fresh global disk accounting; no automatic cleanup.

Other missing launch inputs: reviewed Task59 bytes; complete arithmetic ID
range and clocks checked against the actual held baseline; valid ATP seed;
fresh original schema/page profile; closed baseline catalogue admission and
actual available disk/allocation plan. Required model-state/Source/D2 consumer
binding is intentionally deferred, not fabricated for this receipt diagnostic.

## What this measurement decides, and the next ownership boundary

The current `_Build` owns one source guard, one fresh copied main, one active
transaction generation, one append ledger, and one original 300-second
deadline. `run` finishes/sorts the ledger once, commits once, cold scans all
old/new rows and closes everything. Recalling the API for slices recopying a
previous result does not implement durable cumulative membership or resume.

Use measured phase costs only to decide the next **specific** change: if
append work is the limiting phase, design a private ordinal-range append
checkpoint over that one cumulative ledger; if cold baseline comparison is
already limiting, its bounded traversal/checkpoint is the prerequisite instead.
Do not extrapolate 1024 rows into a claimed full-profile pass.

Holding `_Build` live between Python callbacks preserves its authority but
does not reset its deadline or native RLIMIT_CPU: the unchanged guarded child
still cannot execute more than300CPU across all phases. A live root job owner
can preserve registry, sealed inputs and custody across multiple guarded
children, but the current code has no authoritative writer transfer. Cold
reopen needs an explicitly reviewed owner binding the exact prior committed
main, cumulative ledger and ordinal prefix under the original job/costbook;
it must reject gaps/replay/reordering, ambiguous commit/ledger crash states,
substitution, stale epoch and budget restart. A public result/hash/checkpoint
cannot provide that authority. This diagnostic does not add that interface.

After a genuinely complete receipt corpus exists, use the already-real
`build_history` -> `prepare_tennis_consumer` -> `put_tennis_consumer` APIs;
Task59 descriptors supply their exact tour/cutoff/native/input arguments.
Keep the real Source/D2 and History lifetimes, separate active output writer,
once-only prepared consumer and cleanup-before-commit discipline. Same-key
consumers may share a still-live verified History only; cold workers cannot
deserialize its authority or skip required whole-source checks. Preserve the
31 old Originals/snapshots byte-for-byte and generate168 new owner-produced
pairs, yielding targets199/199; 114 tour/cutoff keys are a target, not a cache
size exemption. Retaining every History/feature file must fit the same actual
8GiB plan; no unapproved deletion or free reservation release is assumed.

## Focused implementation/test expectations

The next implementation scope is the new fixed QA driver/catalogue adapter,
its narrow portable orchestration tests, and report; no core owner rewrite.
Tests cover guard-before-import, actual sample iterator reaching the real
corpus call, all original checks still executing, exact result/old-row/ledger
validation, native-stop nonacceptance, missing/bad baseline admission, retained
failed output, M/journal-M/L accounting, unchanged old large values, expired or
recovered budget refusal and no retry/new-journal fallback. Small portable
tests may validate wiring but must not label local timings native evidence.
Follow independent review with one Root-admitted native execution only when
all launch prerequisites above are established. If admission cannot be made,
report that concrete blocker; no completion/capacity/B/restore/release claim.

## Root precision correction — metadata observation and later physical growth

This append corrects the earlier Root-supplied description of the metadata
diagnostic as a "20CPU reservation"; that text remains above as historical
context, not the current accounting claim. Root now confirms CPU20 hard,
reported actual CPU3.247115605 and SSH exit0, but **no PreparationBudget durable
ticket or journal reservation**. It is a bounded, measured, unjournaled
engineering observation and must be recorded as such. It is not another
durable reservation added to the actual1770CPU retained diagnostic reservations,
does not settle or refund them, and establishes no whole-C costbook coverage.

The proposed1024-receipt diagnostic quantifies only its receipt-owner seam.
Sorted SHA references use fixed content-addressed blocks; insertion of unique
hashes can change block boundaries/membership and sharing across cutoffs.
Neither114keys,199Originals/199snapshots nor duplicate consumer pairs proves
deduplication savings or compliance with4GiB active input and8GiB total retained
workspace. The later full profile must measure actual reference blocks,
snapshots, indices, all retained files and journal reservations physically.
No implementation, test or native action accompanied this correction.
