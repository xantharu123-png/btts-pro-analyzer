# Task10 synthetic consumer-growth harness review

Date: 2026-09-11. Read-only bounded harness review, not a product, full-branch,
native-performance or deployment review. No harness/product/test/index edit,
generator execution/import, SSH, native job or subagent by this reviewer.
Only this report is authored.

## Verdict: APPROVED for the described isolated QA generation

No blocking correctness/isolation finding in the reviewed helper or its delta
from the complete previously used Task4 helper. The one nonblocking stale
comment was corrected by the controller and independently verified below.
Approval is for construction of synthetic G1/G2/G3 controls;
it is not acceptance of their runtime, actual production data, provider truth,
model quality, future unbounded growth or release.

Reviewed file `.pytest_tmp/build_task10_consumer_growth.py`,25495bytes,
Final SHA256 `dd43d9a7b1ac2507f45e93699625dbdd2deff21230670326876346d2a5fcf856`.
Initial reviewed SHA256 was
`61351be4a718616f8c4e8c849de02570d85978e9460fbce410527f22048f5d85`.
Both hashes were independently checked and matched the controller's pins;
the sole intervening comment change was proven by reversing it in memory and
recovering the exact initial SHA256. Read the entire new helper and entire
`.pytest_tmp/build_task4_consumer_growth.py`, and their complete no-index diff.
Source-line references below refer to this exact reviewed helper unless a
product file is named explicitly.

## Delta and meaningful growth boundary

- Lines35-66 mechanically repin the source to exact1c65ada stage
  `/var/lib/betboy-capacity-code-iym7re_h/source`, source archive SHA
  `a3df9e45e9cc0c067197716b44930d6e7eea77557296193e6dab5ca011847e00`,
  base to `/var/lib/betboy-live-backup-onf6j2mg/context-current.db`,
  265793536bytes/SHA
  `77d3bd030fc10e15194e9255f560bcfa9a33ba39392aa7706c425ce67c08d031`,
  and the sole writable context target to
  `/var/lib/betboy-task10-growth-0cguwnz6/synthetic-working/context.db`.
- The translated47,098-receipt pool and its direct SQL inserts/rebinding code
  are completely removed. `ADDED_POOL_RECEIPTS=0` is reflected in expected
  counts; no old body, receipt clock, hash or source link is translated.
- Each call adds one status receipt and one actual original/snapshot pair.
  The clocks computed at lines522-524 are19:35,19:40,19:45 UTC on11September,
  before the fixed23:00 target. Receipt is decision-1second, publication+1,
  shadow append+2. New original validation and current native selection bind
  the actual receipt and cutoff, rather than manufacturing a saved report.
- Lines192-216 count distinct `(event_key,cutoff,tour)` keys as well as original,
  receipt and snapshot counts. Successful G1/G2/G3 necessarily contain31/32/33
  distinct query keys and99775/99776/99777receipts, with31/32/33snapshots and
  16/17/18distinct cutoffs. This crosses the actual30query cache boundary;
  counting snapshots alone would not have proved that.
- Baseline receipt-kind checks now use43322workload/53596status. All30 old
  originals/snapshots and all baseline rows remain subject to the complete
  preservation query. This does not claim an arbitrary workload-size envelope.

## Paths, no network and real owners

`validate_paths` (lines123-160) requires actual UID997, fixed absolute/resolved
source/base/target paths, root-owned unwritable source ancestors, one-link
root0440 base with exact bytes/hash and no companions, root-owned unwritable
stage, and app997/group987 parent0700 plus target0600/one link. Profile1 requires
the exact base hash; later profiles require the controller-supplied preceding
working-state hash and expected preceding counts. No code copies into or
updates a production source/database path. Each completed generation must
still be separately copied/root-sealed by the controller; that sealing is not
performed by this helper.

The only substitutions at lines348-354 are `daily.requests.get` and three
deterministic clock seams. The real HTTP callsite
`scripts/tennis_daily.py:295-307` calls that same requests module's `get`.
The fake returns one ATP scheduled response and an empty WTA response, and
raises on other requested targets; exact two-call ATP/WTA counts are checked.
It never invokes the original HTTP client. This is an inspected exact-callpath
guarantee, not a general OS socket sandbox for arbitrary future product code.

The explicit `live_worker(path=target)` and
`capture_tennis_worker(path=target)` are retained. Inspected real callchain:

- `scripts/tennis_daily.py:668-699` propagates the active worker's target path
  into actual `load_tour_state`; no default production context path or legacy
  state fallback is used by this invocation.
- `context_sources/tennis_capture.py:60-66,81-96` uses the real normalizer and
  append owner on the explicit target when the capture exits.
- `scripts/tennis_daily.py:889-977` invokes actual state loading/predictor and
  pending-original capture; `surfaces={}` and `workload_history=()` avoid
  external catalog/history reads while preserving the intended live original
  replay's empty-workload input. No owner/model is patched.
- `tennis/live_context.py:245-299` reads the full causal tour history from the
  target, invokes real v3 features, builds exact full observation refs, and
  publishes through actual artifact/snapshot/transport owners.
- Shadow writes use only the explicitly supplied `shadow.db` inside a uniquely
  created `TemporaryDirectory` under the synthetic target parent. Automatic
  cleanup is limited to that helper-owned temporary directory.

The `finally` at line385 restores all four patched attributes. Capture can
have persisted some synthetic facts before a later failure, as the real owner
intentionally does; the helper does not falsely claim cross-database atomicity.
A failed construction must remain failed and unsealed, not be retried as the
same preceding input hash. It cannot print `ready_for_root_seal` after failure.

## Integrity and resource evidence boundaries

- Lines223-244 recheck base identity/hash/size and companions, attach it
  read-only+immutable, and use SQL `EXCEPT` over every declared column of each
  baseline table. Inspected `TABLE_COLUMNS` against current runtime schemas;
  primary identities prevent duplicate multiplicity from hiding a changed old
  row. Table presence parity, active-manifest count, foreign keys and exact
  aggregate counts are retained. There is no baseline Python row materialization.
- Lines407-444 check new publication digest, real publication/origin validator,
  actual state/native receipt, every current owning CODE_PATHS hash, unique
  newest target native receipt, snapshot decode/key and actual transport replay.
  Full history/features are produced by the real worker; subsequent complete
  D4 verification of each sealed generation remains separately mandatory.
- Lines465-475 retain single-thread numeric settings, AS2GiB, CPU300 and
  wall600 construction limits before importing application owners. Final checks
  require integrity_check, no companions, target ownership/mode/link count,
  size<=1GiB, RSS<1GiB and elapsed<600. These are construction checks, not the
  measured D4 CPU/wall<300 acceptance condition.
- Pre-import path/hash validation precedes the helper's local alarm/rlimits;
  inherited controller supervision must bound the whole invocation as before.
  `emit` bounds its own metadata output to1MiB; the external supervisor must
  bound aggregate stdout/stderr, including owner output and exceptions.
- Assertions are safety checks in this inherited development harness: run with
  normal assertions enabled, never `-O` or `PYTHONOPTIMIZE`. The actual source
  revision/archive metadata constants do not independently hash the whole
  source tree. Its exact root-sealed staging/archive evidence remains required;
  module ownership/path checks alone are not a substitute for that evidence.

Performed local non-executing validation: parsed helper source via stdin with
`ast.parse` (54top-level nodes), confirmed the only external attribute patches
are the HTTP and three clocks, and independently calculated expected profile
receipt/query counts. No helper import, application import, generated database
or performance claim resulted from that parse.

## Nonblocking minor: corrected and closed

Initial line130 said the exact source archive had803members instead of the
current pinned1c65ada archive's832members. The controller changed only that
comment to832. Reading final bytes, reversing that single text substitution
in memory and hashing recovered the exact initially reviewed SHA256 above;
the final file remains25495bytes. This establishes no other intervening change.
There was no803-member acceptance condition or changed extraction behavior.
Reviewer did not change the helper. No remaining actionable finding.

## Required controller follow-through

Transfer only the exact reviewed bytes, retain root-sealed source provenance
and isolated target identity, run each construction as UID997 under bounded
supervision, and seal completed G1/G2/G3 copies independently using their actual
returned hashes. Verify preserved baseline and actual counts/results, then run
complete uninstrumented D4 on the exact Task10 candidate against actual current
input and these stronger31/32/33query controls under unchanged native limits.
Construction success does not establish that any generation passes D4 or that
Task10 fixes fresh30. Keep historical largest, required final tests/review and
backup/restore/release gates separate.

## Addendum: bounded producer supervisor review

Reviewed complete ignored `.pytest_tmp/run_task10_growth_producer.py`, SHA256
`5af9db9b85bafee8803edc4b558ee105d518ea5ae416e4496f66fcead56c5944`,
independently hash-verified. Generator remains the approved unchanged `dd43...`
above. This addendum does not reopen the generator/product review. No supervisor
execution, edit, SSH, index operation or native job by reviewer.

**Supervisor verdict: CHANGES REQUIRED before execution**, limited to cleanup
ownership. Generator approval is unchanged.

### Important: process-group cleanup depends incorrectly on leader liveness

Lines87-98 issue `killpg` only when `process.poll() is None`. A producer can exit
while its descendant remains alive and retains the stdout pipe. The read loop
then reaches its wall/output stop, but both kill guards see a dead leader and
skip the still-existing owned process group. Waiting/reaping the leader does
not terminate the surviving descendant. This defeats the stated outer bound
for the complete owned process group even though each process inherited its
individual resource limits.

Fix narrowly: after creation owns the new session/group, terminate that owned
group on failure/exception regardless of leader liveness; tolerate
`ProcessLookupError` when the group has already disappeared. Reap the direct
child using bounded waits. Final cleanup should also ensure no residual group
survives a nominal leader exit. Retain `start_new_session=True`, fixed arguments
and existing UID/resource limits. Do not target the supervisor's own group.

### Important: cleanup ownership begins too late after spawning

Lines65-70 print progress, construct/register a selector and allocate state
before entering `try` at71. A broken stdout pipe, selector initialization or
registration error can unwind with the producer already running but no cleanup
handler. The child has CPU/AS limits, but may survive its supervisor and outer
wall ownership, especially on blocked I/O.

Fix narrowly: enter a whole-postspawn `try/finally` immediately after successful
Popen, with nullable/conditionally closed selector and pipe state; include
progress output and selector setup inside that ownership. Cleanup must survive
already-exited-child/group races without a second cleanup exception masking
reaping. No change to the generator or product is needed.

### Other inspected boundaries

- Root phase imports only standard-library modules, has its30second alarm,
  validates exact stage/root ancestors, fixed generator mode/owner/link/size/SHA,
  absent output-generation path and available disk. It then clears supplementary
  groups to987 and permanently sets all real/effective/saved UID/GID to997/987
  before Popen. No application code is imported as root by this script.
- Child command is fixed isolated Python `-I -B`, fixed source/base/target and
  restricted profile/hash arguments. Fresh session, AS2GiB/CPU300, clean
  single-thread environment, stdin/devnull, outer600wall and aggregate merged
  stdout/stderr1MiB are present. Resource failure does not become construction
  acceptance. It performs no source/database/production write itself.
- The output selector bounds retained bytes and does not directly forward logs.
  The final marker filter returns the complete matching child dictionary, not a
  closed-field schema sanitizer. Its disclosure safety currently relies on the
  exact approved generator's fixed metadata-only emitter. Do not describe this
  as sanitizing arbitrary owner JSON; constructing a closed allowlisted final
  metadata object would strengthen that claim. No additional blocking finding
  is asserted against the fixed reviewed generator output here.
- Missing report/nonzero child/resource measurements fail acceptance. A CPU,
  wall or output kill can leave a partial synthetic working DB, which must not
  be sealed/reused as successful input. Full D4 acceptance remains separate.

Controller was informed of the two cleanup findings before execution. Review
of corrected exact supervisor bytes is required to close this addendum.

### Supervisor correction rereview: APPROVED

Read the complete corrected wrapper and verified SHA256
`3b1c8011fdcd8b2707f9c9031f469756310874112e508cab33b95a47ff16e59a`.
Compared its cleanup/control flow against the previously inspected complete
wrapper. Local stdin-only AST parsing passed; no wrapper import/execution or
native child was started by this reviewer.

Both Important findings are closed:

- New lines90-101 unconditionally signal the owned fresh-session process group
  on exit, regardless of leader liveness, including normal leader completion.
  A vanished group is tolerated via `ProcessLookupError`; the direct child is
  reaped with a bounded10second wait. Descendants retaining stdout no longer
  escape wall/output cleanup merely because their leader exited first.
- Progress printing, selector construction/registration and the complete read
  loop are now within the postspawn `try/finally` (lines68-101). Exceptions in
  those operations enter the same unconditional group cleanup. Selector/stdout
  are closed after the bounded reap. Failed construction remains unaccepted
  and must remain unsealed.

The root-only standard-library preflight, permanent UID997/GID987 drop, fixed
isolated interpreter/generator/source/base/target, generator `dd43...` pin,
single-thread environment, session ownership and resource/output/acceptance
limits are unchanged. No new blocking finding. Approval is for this exact
supervisor plus the unchanged reviewed generator in the described isolated QA
workflow; it is not evidence that construction or D4 has executed successfully.

As with ordinary bounded subprocess supervisors, a kernel-level inability to
reap within the final timeout raises and cannot produce an acceptance report;
this is not a promise of recovery from uninterruptible kernel I/O or external
SIGKILL of the supervisor. The previous note that final-report disclosure relies
on the pinned generator's fixed metadata emitter still applies.

### Final supervisor pin: APPROVED, initializer-only refinement

Final independently verified supervisor SHA256:
`b67c500137b6fe72aec17996068e3d5857173c417dc1a50bf01b8e5d62cbff44`.
Only `selector=None`, `output=bytearray()` and `failure=None` moved ahead of
Popen. Reversing exactly that block movement in memory reproduces the preceding
approved `3b1c8011fdcd8b2707f9c9031f469756310874112e508cab33b95a47ff16e59a`
SHA256, proving no other byte change. This additionally puts allocation failure
before any child exists, and leaves the postspawn try/finally immediate.
Approval and limitations above remain unchanged; generator remains `dd43...`.
No execution or helper/index edit by reviewer.
