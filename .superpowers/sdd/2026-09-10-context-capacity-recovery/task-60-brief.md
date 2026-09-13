## Task 60: One-shot durable admission for the fixed native receipt diagnostic

**Placement:** Implement the missing narrow admission prerequisite identified
in `task-60-execution-seam.md`, not B proof reuse/publishing or a general resume
engine. Task59 provides only synthetic data; Task58's successful small chain
stays unchanged. After this task's independent review, a separate fixed driver
will measure actual Task48 copy/append/ledger/cold-verification on the real
baseline using Task59 `atp-heavy` slice `[0,1024)`. This task launches nothing.

**Own only:** new `tests/native_context_diagnostic_admission.py`, new
`tests/test_native_context_diagnostic_admission.py`, and this plan workspace's
`task-60-report.md`. No product/helper/old test/guard/catalogue/spec changes,
Git/index/server/network/install/cleanup or subagents. Root owns integration.

**Approved binding:** C spec SHA
08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba;
B spec SHA498e63c5641adaccdd4d284fa9b57ad93c02ba834e9abd6bf4064636d6b12da1.
CPU300 per portion, aggregate1800CPU/3600boot-inclusive wall, AS2GiB,
RSS<1GiB,output1MiB,active4GiB,new-QA8GiB/free4GiB remain unchanged. The new
fixed diagnostic will tighten the one-phase split to root parent60CPU plus
one guarded worker240CPU, full300CPU permanently retained; it does not settle
or refund costs. Historical1770CPU reservations plus the separate metadata
diagnostic (20CPU enforced ceiling, measured3.247115605CPU, no durable ticket)
stay separately recorded, not converted into
a fabricated settled C proof or discarded. C/B/empirical/release incomplete.

**Required public interface (declare exact shapes in report before coding):**
`admit_diagnostic(registry_directory, *, identity, purpose, profile_kind,
plan_digest, job_directory, retained_history_digest)` returns a live
`DiagnosticAdmission` context owner. `identity` is the actual unchanged
`context_preparation_budget.BudgetIdentity`; all hashes are lowercase SHA256.
Purpose is exactly `context-receipt-corpus-diagnostic-v1`, profile_kind exactly
`atp-heavy`. `plan_digest` binds the fixed entire input/seed/clock/namespace,
slice, allocation and execution plan. The future parent independently proves
its complete contents; a supplied digest is never baseline/closure/size truth.
`retained_history_digest` binds Root's complete retained-diagnostic inventory,
not a cost-refund credential. `job_directory` must already be root-protected,
empty, canonical, single owned job slot; this API neither creates nor deletes it.

**No fresh budget by renaming:** the stable family key is the canonical hash of
purpose/profile_kind plus identity.input_digest,execution_digest,runtime_digest,
installation_digest. The complete identity.profile_digest, plan_digest, retained
history digest and exact job path/identity are bound in the first durable entry
but DO NOT create another family when clocks/seeds/slice/output path change.
Any existing family entry, whether completed, failed, partial or merely started,
denies a second admission; no reopen/resume/retry/overwrite/reset/delete API.
A genuinely different reviewed input/execution/runtime identity is a different
engineering request, never automatic retry inside this module. Raw hashes do
not establish trust against root/VM rollback, which stays outside the claim.

**Native ownership:** public admission is Linux-only and real effective UID0;
no public test/assurance bypass. Traverse the full canonical absolute registry/
job ancestor chains without symlinks, root-owned and not group/world writable;
hold no-follow directory/file FDs and recheck FD/path identity at fallible
boundaries. Use an exclusive nonblocking OS lock held for the entire owner
lifetime; contention must fail before a competing write. Caller retains custody
of the registry namespace; root/host compromise and foreign privileged edits
are outside the claim. Do not import app/venv/product code as root. Only stdlib
and the already reviewed `context_preparation_budget` helper may be used.
The new registry module must also work from a held compiled namespace, without
requiring registration as a new imported helper in the supervisor's whitelist.
No change to that whitelist, no dependency or new server identity/key/service.

**Durable closed format:** one bounded append-only registry (at most1MiB,
at most256records, at most4096bytes/record; canonical duplicate-key-free JSON,
integers exact/no bool/float, explicit version/order/previous digest) plus
existing identity-derived budget journals in the same protected registry.
Registry creation is explicit first-use only within the already supplied empty
registry directory; a nonempty directory with missing registry never recreates
it. Do not use family filenames alone as existence authority. Include bounded
complete known journal membership and reject missing/replaced/unexpected files.
Membership may be derived from the bounded registry records; no repeated giant
list is required inside each4096byte record. A prior nonterminal/ambiguous
admission blocks the entire registry, even for a different identity. A different
reviewed family can proceed only when prior entries are complete and cross-bound
to their retained stopped budgets. Historical journals are read/checked as
historical data without renewing their expired deadlines or reopening permission.
Persist an `admitting` entry and fsync file+directory BEFORE creating the budget;
then use actual `PreparationBudget.create` and reserve the full300CPU ticket,
then persist the exact journal identity/head/ticket binding as `admitted` and
fsync BEFORE returning any live owner. A crash or I/O error between these
steps leaves the family permanently consumed and failed files retained. No
registry/journal repair, truncation, roll-forward or optimistic re-admission.

The original parent kernel process-start/boot identity and fixed deadline must
be recorded; registry setup may not start a fresh3600seconds after preparation.
Use actual Linux `/proc/self/stat`, boot clock and boot ID. The later fixed
parent must meter its entire60CPU lifetime, including admission startup, and
all output/cleanup; reserve durably before catalogue copies or worker launch.
The effective deadline is the minimum of the original process start+3600s and
the unchanged actual budget deadline. Boot/clock discontinuity, changed schema/
entry/head/owner/path, uncertain cleanup or exhausted bounds permanently poison
the live owner. Source/model/resource enforcement remains the caller's job.

The owner exposes `assert_admitted()` and a read-only data `snapshot()`;
each rechecks original identity/head/ticket/deadline/lock custody. It never
exposes settlement/refund or a raw reusable budget handle. `close()` and context
exit stop the actual pending budget without refund and append a terminal record
cross-binding the final stopped journal head. Failure before terminal durability
retains the entire charge and consumed family; do not claim successful cleanup.
No `pass`/native-success/C/B authorization is produced by a registry entry.

**Crash-acknowledgement precision:** no persisted format can prove that an old
caller received the final fsync acknowledgement. A failed write/sync permanently
poisons that live owner, and any incomplete/nonterminal/noncanonical or
non-cross-bound historical state blocks the whole registry. The same consumed
family always remains denied. A later fresh process may consider a genuinely
different reviewed family only if the complete canonical terminal entry and
complete retained journal already agree on the exact stopped head/identity/
charge, and it freshly syncs both existing files and their directories before
any new admission. Failure of that read/check/sync denies admission. This proves
present durability of stopped historical data, NOT success of the former
close call; no repair, truncation, roll-forward, retry, reset or refund occurs.
An in-process known-failed owner is never revived by reading those same bytes.

**TDD steps and concrete assertions:**

- [ ] Add RED tests for absent admission implementation, then the real protocol:
  `first.assert_admitted()` succeeds only after durable registry and real budget
  reserve; a second identical family fails even with a different job path,
  profile_digest, plan_digest, clock or seed. None creates another journal.
- [ ] Exercise real local file I/O through a private portable protocol seam
  (not a public native bypass) and actual existing budget `_attach` test pattern.
  Inject failures at each registry write/fsync/directory-fsync, budget create/
  reserve, admitted update and close boundary: no owner/ticket escapes before
  durability, raw partial bytes stay, and the same-family next admission always
  denies. Incomplete or unbound terminal history blocks all families. Separately
  test full terminal bytes left by a final-sync failure: current owner stays
  poisoned; only a fresh process's complete historical checks and fresh syncs
  may establish stopped history for a genuinely different reviewed family.
- [ ] Exact clock/deadline/boot change, duplicate/noncanonical JSON, bad scalar
  types, overlarge records/index, reordered/truncated registry, absent/replaced/
  linked/same-count-different journal, inode/path changes, unknown files and
  lock contention have explicit failure assertions, not count-only positives.
- [ ] New reviewed input/execution identities can be admitted while existing
  family/charges remain intact; snapshot and returned-object mutation do not
  alter internal ownership. Close failure poisons; no automatic cleanup/reset.
- [ ] Test actual Linux root/DAC/flock branch with explicit environment skips
  elsewhere, and public Windows/nonroot rejection. Portable protocol tests
  cannot claim native permission/locking proof. Later Root native QA is separate.
- [ ] Add a focused held-namespace execution test so no unapproved helper import
  is needed. Use the existing QA Python; final focused module run once, fresh
  XML/basetemp, plugin autoload/bytecode/cache disabled, bounded timeout, actual
  exit and stdout/stderr/session retained. No unchanged full-suite rerun.

Full report: exact APIs/formats/native preconditions, RED/GREEN commands/output,
file/XML hashes, known limits and explicit sole-writer return. Root reads the
report, commits exact owned files and dispatches independent spec/quality review
before the first native use. A failed or unmeasured registry is never a reason
to bypass the existing guards or start the large profile without accounting.

**Native API references checked by Root13September:** lock custody is tied to
the open file description, including duplicated descriptors, not just a path
or a Python flag; controlled owners must not expose or leak the held descriptors.
[Linux flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html),
[Python3.12 fcntl](https://docs.python.org/3.12/library/fcntl.html).
Durability of a newly named file requires the directory's separate sync as well
as the file sync. [Linux fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html).
These APIs are technical prerequisites, not proof of whole-C admission or of
arbitrary foreign/root/VM behavior.
