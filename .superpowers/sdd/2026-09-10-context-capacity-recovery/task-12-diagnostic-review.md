# Task12 Stage-A diagnostic helper review

Date: 2026-09-12. Verdict: **Approved for the specified isolated diagnostic run.**
No blocking finding. This approval is not product, capacity or release acceptance.

Reviewed complete new `.pytest_tmp/measure_stage_a_prefix_cost.py` and complete
already-reviewed comparator `.pytest_tmp/trace_task10_growth_g1_phases.py`.
Also checked actual `_verify_connection`, `verify_context_database`,
`_replay_history`, `LiveReplayDescriptor` and sealed-reader cleanup owners.
No whole-branch rereview or production execution was performed.

Verified SHA256:

```text
measure_stage_a_prefix_cost.py 9b0d84cfca526ff2d720d13ed3ed54d9de2422783d12358874c8fe690664ae54
trace_task10_growth_g1_phases.py b9964f19b5bdee574a2c3778befb34619379bcc4597dee8e04edaf5582ad4d74
```

## Safety and boundedness

- The helper requires nonoptimized Python and effective UID997 before importing
  product code, and installs AS2GiB / hard CPU300 limits. It uses the same exact
  root-owned source and sealed G1 input paths as the predecessor. Parent
  directories must be root-owned, non-group/world-writable, real directories,
  without resolved-path substitution. Input must be root-owned regular0440,
  singly linked, with exact expected SHA256 and no WAL/SHM/journal companions.
- Only `_verify_snapshots` is replaced, inside this throwaway process. The
  unchanged real physical/source seal and original verification owners run
  first, as confirmed by `_verify_connection` order. No product source/index
  mutation, production-database write, root app import, network call or
  credential loading is introduced by the helper. Sealed-reader mode retains
  actual read-only immutable/query-only SQLite admission and transaction setup.
- At most64 distinct original cutoff choices are admitted, at most8 are
  sampled, and each has3 repetitions: at most24 measurement records plus phase
  and final records. The explicit40-record/1MiB emitter limits are retained.
  Only cutoff/tour/count/timing/cache statistics, fixed revision/input hash and
  unchanged status are printed; receipt digests and decoded payloads remain
  internal. Histories are not accumulated across samples. Real tuples are
  deleted before optimistic decoding; comparison references survive only the
  current pair. Actual cache/input caps and AS limit remain unchanged.
- PROF265 / wall285 timers leave cleanup margin under CPU300. The planned
  outer timeout305 with kill-after10 and bounded stdout/stderr capture remain
  necessary: imports/input hashing occur before internal timers start, and
  final seal/hash cleanup occurs after timers are disabled. The helper's JSON
  emitter alone does not bound an unexpected traceback or dependency stderr.
- Completion deliberately raises `MeasurementsComplete`, so this hook never
  returns a snapshot count or permits a full verifier report. Timeout uses a
  separate diagnostic stop; unexpected exceptions still fail the process.
  `measurements_complete` must not be confused with verifier completion.
- The sealed reader's ExitStack closes SQLite and file descriptors on the
  deliberate BaseException unwind. Its normal post-yield verification is not
  reached on that unwind, but the helper's outer finally independently checks
  input full identity, exact SHA256 and absence of companions. A killed or
  failed cleanup cannot be labeled input-unchanged without a valid final
  record and the controller's ordinary post-run checks.

## Measurement validity and interpretation limits

The measured real branch invokes actual `_replay_history` with the descriptor's
receipts, cutoff, tour, history budget and cache. The optimistic branch consumes
the same owned sealed cache's first `count` encoded rows, with fresh owner
checks at entry/exit and identity/seal checks around each decode. Matching
ordered receipt digests and cutoff assertions detect the wrong prefix. It
returns no counterfactual rows to an actual snapshot/model owner.

The optimistic branch deliberately omits most per-row production checks. Its
results are a lower-work counterfactual, never an approved replacement proof
path. Existing snapshots, features, transports and rollbacks are not verified
by this run. Real physical/source/original timing remains included in process
cost; pair timings cover history reconstruction only.

Interpretation caveats are nonblocking for this diagnostic purpose:

- Fixed real-then-decode order favors warm execution of the second branch and
  may interact with allocation/GC/scheduling. Three repeats expose variation
  but do not establish a mathematically strict lower bound or speedup ceiling.
- Sampled original cutoffs are not a snapshot-weighted workload. Do not sum or
  multiply their deltas into a full-run capacity claim without actual consumer
  distribution and subsequent exact native acceptance.
- The literal `source_revision` field is a label, not a self-verifying source
  hash check. As with the predecessor, authorization of exact724 execution
  depends on root's separate staged-source/hash/seal validation and controlled
  interpreter/import environment. No verification of live VPS source state was
  performed by this local review.

## Local check and handoff

Read-only syntax check, working directory
`C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -c 'import ast, pathlib; p=pathlib.Path(".pytest_tmp/measure_stage_a_prefix_cost.py"); tree=ast.parse(p.read_bytes(),filename=str(p)); print("AST parse passed; top-level runtime execution not performed")'
```

Result: `AST parse passed; top-level runtime execution not performed`, exit0.
The Linux helper was not run on Windows. No missing skill tool, live timing,
native/DAC test or fullsuite is claimed. Helper hash was rechecked after review.
Only this named report is authored; root retains controller/index/VPS ownership.

Approval applies solely to the reviewed bytes under the planned UID/limits,
root-controlled staged source, sealed G1 input, outer timeout/kill and output
capture. All current/growth acceptance and release gates remain unchanged.

## Addendum: Stage-B live aggregate metadata helper

Date: 2026-09-12. Verdict: **Approved for the requested ordinary read-only live
metadata query, with the WAL filesystem qualification below.** No blocking
finding. Reviewed complete `.pytest_tmp/read_stage_b_growth_metadata.py`;
no execution, SSH, product/index changes or additional file authorship.

Reviewed helper SHA256:
`383c0eba1f02e6643e9fb86608377353ee5f9a092a2eb7ba49d510904c5bda25`.

Read/write and transaction assessment:

- Requires effective UID997 and nonoptimized Python, then establishes
  AS512MiB / CPU30 / wall alarm40. Only standard-library modules are imported;
  no application import, credential access or network operation exists.
- Opens only the fixed resolved live path using SQLite URI `mode=ro`, followed
  by `query_only=ON` and `trusted_schema=OFF`. It correctly does not assert
  `immutable=1` for a live WAL database. No DML, DDL, vacuum, checkpoint, attach,
  journal-mode change or repair SQL appears. Table names are a fixed internal
  tuple; the artifact-kind predicate is parameterized. `temp_store=MEMORY`
  affects this connection rather than persisting a database setting.
- BEGIN precedes all database measurements. The first SELECT establishes the
  read snapshot; subsequent aggregate/payload reads share that transaction.
  Rollback ends successful reading; finally closes the connection on ordinary
  Python failures. Default alarm/OS resource termination also releases its
  descriptors. Connection timeout2 and elapsed25 progress-handler interruption
  bound ordinary contention/query work without holding a writer transaction.
- WAL qualification: `mode=ro` and query-only prevent logical database writes,
  not every possible filesystem side effect. Normal live SQLite WAL reads can
  use/update shared-memory reader coordination, and SQLite may need companion
  setup depending on existing state and permissions. This is not an immutable
  filesystem snapshot or a guarantee that companions remain byte-identical.
  The helper correctly makes no file-unchanged claim and must not be reported
  as one. If zero companion interaction were required, this live-query method
  would not satisfy that different requirement.

Resource/output assessment:

- Main-file size and transaction-visible page_count times page_size are each
  checked against1GiB. Up to64 kind aggregates and1024 daily aggregates are
  fetched through explicit maximum-plus-one checks. Original publications are
  capped at4096, each raw payload at2MiB and cumulative raw bytes at64MiB;
  retained cutoff strings are at most64 characters with ATP/WTA-only tours.
- These checks bound admitted results, not SQLite's total scan/sort work.
  Aggregate queries may scan the full allowed database before fetchmany can
  reject excess groups. A large individual SQL value is also materialized
  before Python checks its length. AS/CPU/alarm/progress limits therefore
  remain the hard fail-closed resource containment. Failure is an incomplete
  diagnostic, not permission to enlarge the limits or report partial success.
- Successful output is exactly one JSON record capped at256KiB before print.
  Overall dictionary/list sizes are bounded by the aggregate and original
  caps above. Root should retain bounded outer stdout/stderr capture and a
  timeout/kill policy for the actual run; the JSON assertion does not limit
  incidental stderr on failure. No output is printed before all work succeeds.

Privacy and interpretation assessment:

- Actual original payloads are decoded internally to obtain only tour/cutoff;
  no event identifiers, participants, predictions, receipt references, source
  payloads, account data or credentials are printed. Outputs are counts, kind
  labels, day/tour aggregates, time ranges, sizes and process usage. This is
  appropriately minimized for the requested growth analysis. It remains
  internal operational metadata, not a public-report artifact.
- Kind labels and observation timestamps are database-derived, not independent
  validated claims. The fixed trusted live database is the scope; this helper
  is not a general sanitizer for hostile arbitrary databases. AS/output limits
  reject excessively large returned values rather than publishing them.
- `main_file_bytes_before` is a pretransaction filesystem observation; logical
  bytes and SQL aggregates belong to the read snapshot, which may include WAL
  state and concurrent-worker changes before its first SELECT. Their mismatch
  is not itself corruption. `measured_at` is observation-start time rather than
  proof of freshness through process exit.
- The output explicitly states diagnostic-only, verification-not-claimed and
  live-worker mutability. Counts and bytes alone establish neither D4/source
  correctness nor a consumer-growth capacity pass. Root must keep those gates
  separate and should run this only after the heavy diagnostic ends as planned.
