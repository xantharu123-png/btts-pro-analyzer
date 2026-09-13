# Task 60 implementation report

Status: DONE_WITH_CONCERNS (native branch deliberately unexecuted on Windows;
independent Root spec/quality review and later native QA remain required).
The initial protocol declaration below was written before implementation.

## Declared API and closed format

Public signature: `admit_diagnostic(registry_directory, *, identity, purpose,
profile_kind, plan_digest, job_directory, retained_history_digest)`.
All seven arguments are required. `identity` is exactly the existing helper's
`BudgetIdentity`, copied internally; digest values are lowercase SHA256.
Purpose is `context-receipt-corpus-diagnostic-v1`; profile is `atp-heavy`.
Paths must be canonical absolute strings (or PathLike yielding such a string).
The public entry requires Linux effective UID 0 and never offers a test flag.

Return: `DiagnosticAdmission`, with `assert_admitted()` returning None,
`snapshot()` returning detached recursively read-only mappings of the first
admission and durable binding (data only), `close()` returning None, and context
manager methods. No raw budget, ticket object, descriptor, settle/refund,
reopen/retry/reset/repair/launch method is public.

Private portable seam: `_admit_protocol(namespace, *, identity, purpose,
profile_kind, plan_digest, retained_history_digest)` accepts a namespace adapter
whose real local file I/O is exercised by tests; this does not supply native
assurance and is never called by the public API with a portable adapter.

Registry name `diagnostic-admissions.jsonl`. Canonical ASCII JSONL envelopes
`{digest,record}`, digest SHA256 of canonical record. Record has exactly
`format,version,sequence,previous,event,body`; format
`betboy-native-diagnostic-admission-v1`, version integer 1, zero-based sequence,
previous SHA256 (64 zeroes initially). Bounds: 1MiB total, 256 records,
4096 bytes per complete newline-terminated record, exact integers (no bool,
float, noncanonical encodings, duplicate keys, unknown fields).

Three events per family: `admitting`, `admitted`, `closed`. `admitting` body
binds `family,identity,purpose,profile_kind,plan_digest,retained_history_digest,
job,registry,registry_file,process`; job and registry bind canonical `path,device,inode`;
`registry_file` binds the registry file's own `device,inode` (added after a
specific replacement RED test during self-review, before its implementation).
File identifiers are exact unsigned integers bounded by 2^128-1, supporting
portable Windows volume/file IDs; other integer bounds remain the helper's
signed 63-bit bounds. The parser rejects integer encodings longer than 39
characters. Paths are canonical absolute strings bounded to 1024 characters.
process binds `pid,start_ticks,ticks_per_second,start_boot_ns,boot_id,
deadline_boot_ns` from original kernel process start (deadline start+3600s).
Family is canonical SHA256 of purpose/profile_kind and the four identity
dimensions input/execution/runtime/installation, excluding profile_digest.
`admitted` body binds `family,journal,journal_device,journal_inode,journal_head,
ticket,deadline_boot_ns`; journal is complete-identity SHA256 + `.jsonl`;
ticket is the exact existing Reservation field mapping and reserves 300CPU.
`closed` body binds `family,journal_head`; its matching historical budget must
be stopped, retain the same pending ticket and full 300CPU, and have no
settlement. Membership is exactly registry plus journal names derived from
all first entries. Nonterminal prior entry blocks the whole registry.

Native preconditions: already-existing empty first-use registry and empty job
slot, full absolute ancestor chains root-owned and not group/world writable,
no symlinks; held no-follow FDs with FD/path rechecks at I/O boundaries; a
nonblocking exclusive flock on the registry directory held until owner close.
Historical journals are replayed as data, not reopened or renewed. Original
process/boot/deadline and unchanged live budget head/ticket are rechecked.
Effective deadline is min(original process start+3600s, actual budget deadline).
The fixed parent still must meter its entire 60CPU lifetime; one future worker
is capped at 240CPU; no launch or resource enforcement occurs here.

## Preimplementation concern sent to Root

An acknowledged fsync error after complete terminal bytes is indistinguishable
to a new process from a successful durable terminal record if those bytes
survive. Root ruling requested before claiming universal persistent rejection
of such ambiguous final-sync failures. Root resolved this explicitly before
implementation. No native guarantee is inferred from portable I/O, hashes, or
a supplied plan/history digest.

## Root ruling adopted

Root amended the brief during implementation; final brief SHA256 is
`3d3f2c767c5656c30aa0c3900324d41228cacc894a2c8a0833cad5f043dbdb56`.
The originally dispatched brief SHA256 was
`ef5f804de1d3e86e5b881d33e5035030904c89488f1c70b8c932702ffb9665fb`.

No persisted acknowledgement oracle, external custody credential, or recovery
API was invented. Any live owner seeing a durability error is permanently
poisoned and reports close failure. Its held module also retains a poisoned
namespace set to deny later requests in that controller instance. Same-family
admission always remains consumed once admitting bytes exist. In a fresh
process, absent/partial/noncanonical/nonterminal or unbound data blocks every
family. Only a complete canonical terminal record, exact retained stopped
budget/head/ticket/charge, full membership/identity checks, and fresh fsync of
every retained journal plus registry and directory permit a genuinely different
reviewed family. Fresh sync establishes present durability; it does not say the
old caller observed successful close. No bytes are rewritten or repaired.

The tests run actual fresh portable subprocesses for this distinction. They
verify same-family denial, different-family refusal after admitting/admitted
sync failures, fresh-history-sync failure refusal, and different-family
admission only after complete stopped terminal history survives and re-syncs.
Old journal bytes and the full 300CPU charge remain unchanged.

## Implementation and self-review

- Added only the two assigned QA files and this report. No Git/index/commit/
  push, product/helper/old-test/guard/catalogue/spec edits, installation, server
  operation, network request, native diagnostic launch, or subagent dispatch.
- Public API has exactly the required parameters, no defaults or assurance
  flags. Unsupported OS/nonroot entry rejects before namespace acquisition.
- Actual `PreparationBudget.create` is used by the native adapter; the portable
  adapter uses actual `_FileJournal` and `PreparationBudget._attach` with real
  file writes/fsync, not a fabricated budget/ticket. The full 300CPU ticket is
  reserved before an admitted durable entry or owner return.
- Protected native ancestry is checked from `/` through both supplied paths;
  symlinks, writable ancestors, wrong UID, non-private files, link counts,
  changed inodes/paths, and excess membership are refused. Registry and job are
  distinct, non-nested slots. Neither directory is created/deleted by the API.
- Directory flock custody is checked against `/proc/self/fdinfo` for the actual
  held open file description, PID and device/inode. It is never silently
  reacquired after loss. All controlled FDs are non-inheritable and remain
  private implementation details, never snapshot fields or public handles.
- Reads and append boundaries recheck FD/path/ownership and byte/head identity.
  Historical stopped journals are replayed as historical data without opening a
  budget handle, renewing its expired clock, settling, or refunding.
- Clock samples retain boot/realtime continuity and original kernel process
  PID/start ticks/boot identity. Startup and post-sync deadline checks prevent
  admission work from restarting the original parent's 3600s deadline.
- Healthy close stops the actual pending budget, retains 300CPU and the exact
  ticket, and durably appends the final stopped head. Failure or uncertain
  descriptor cleanup is an exception and poison, not a successful close.
  Failed/corrupt files are retained; there is no reset, delete, repair, retry,
  reopen, settlement, refund, budget restart, launch, or authorization method.
- Snapshots are detached recursively read-only mappings. Identity input is
  copied. The owner serializes all operations with a nonblocking local lock,
  including construction of returned snapshot data.
- Self-review added genuine RED regressions for an identically copied but
  replaced registry inode, snapshot/close concurrency, and noncanonical stored
  job paths. All were fixed, then independently observed GREEN below.
- Additional concrete assertions cover complete membership, absent/replaced/
  hard-linked/same-count-different journals, foreign writes, truncated/reordered/
  duplicate/noncanonical JSON, nested bool/float/bad schemas, record/count/total
  byte bounds, startup deadline, and real budget init/reserve/stop write errors.
- Held-namespace execution works without registering this module in sys.modules
  or modifying the supervisor's unchanged imported-helper whitelist.

## Verification commands and actual terminal evidence

All commands ran in
`C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.
Interpreter: `.pytest_tmp/qa-python312-c-01/Scripts/python.exe`.
No copied invalid venv was used. Every pytest child was bounded to 60 seconds;
fresh-process tests individually bound their children to 15 seconds. Every run
disabled plugin autoload, bytecode and pytest cache. No full-repository suite
was run. Test-generated corruption fixtures and XML are retained under fresh
`.pytest_tmp/task60-*` names; no cleanup/reset command was performed.

Exact initial absence RED command:

```powershell
.pytest_tmp/qa-python312-c-01/Scripts/python.exe -B -c "import os,subprocess,sys; e=os.environ.copy(); e.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1'); r=subprocess.run([sys.executable,'-B','-m','pytest','tests/test_native_context_diagnostic_admission.py::test_admission_implementation_exists','-q','-p','no:cacheprovider','--basetemp=.pytest_tmp/task60-red-01','--junitxml=.pytest_tmp/task60-red-01.xml'],env=e,capture_output=True,text=True,timeout=60); print('CHILD_EXIT',r.returncode); print('STDOUT\n'+r.stdout); print('STDERR\n'+r.stderr); sys.exit(r.returncode)"
```

Actual terminal chunk `fcaa46`, outer exit 1, child exit 1, no ongoing session:

```text
CHILD_EXIT 1
STDOUT
F                                                                        [100%]
================================== FAILURES ===================================
____________________ test_admission_implementation_exists _____________________
    def test_admission_implementation_exists():
>       assert SOURCE.is_file(), 'missing protected one-shot admission implementation'
E       AssertionError: missing protected one-shot admission implementation
E       assert False
tests\test_native_context_diagnostic_admission.py:22: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_native_context_diagnostic_admission.py::test_admission_implementation_exists
1 failed in 0.23s
STDERR
(empty)
```

The initial whole new protocol module was also exercised before implementation
with the same bounded wrapper, child args
`tests/test_native_context_diagnostic_admission.py -q --tb=no -p no:cacheprovider
--basetemp=.pytest_tmp/task60-red-protocol-01`.
Chunk `57dfec`, outer/child exit 1: `1 failed, 1 skipped, 44 errors in 0.23s`.
The single assertion established intentional missing implementation; the 44
dependent fixture errors were the same absence, not independent behavioral
RED proofs. All stderr streams in the commands below were empty.

For precise reconstruction of subsequent scoped commands, each used this same
bounded command wrapper (SELECTOR/BASENAME/options listed in the table are the
literal child arguments for that invocation):

```powershell
.pytest_tmp/qa-python312-c-01/Scripts/python.exe -B -c "import os,subprocess,sys; e=os.environ.copy(); e.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1'); r=subprocess.run([sys.executable,'-B','-m','pytest',SELECTOR,OPTIONS,'-q','--tb=short','-p','no:cacheprovider','--basetemp=.pytest_tmp/BASENAME'],env=e,capture_output=True,text=True,timeout=60); print('CHILD_EXIT',r.returncode); print('STDOUT\n'+r.stdout); print('STDERR\n'+r.stderr); sys.exit(r.returncode)"
```

| Run / terminal chunk | Selector/options, basetemp basename | Actual child/outer exits and output |
|---|---|---|
| Development `ba5c81` | module, `task60-green-dev-01` (no --tb=short) | 1/1; `43 failed, 2 passed, 1 skipped in 2.36s`; Windows unsigned volume ID exceeded the initially assumed signed range. Tool output was truncated; no claim of full retained transcript for this intermediate run. |
| Development `facf3d` | module, `task60-green-dev-02` | 1/1; `1 failed, 44 passed, 1 skipped in 3.02s`; portable `fsync` of rb handle returned Errno 9 on Windows. Portable sync seam changed to r+b; native behavior unchanged. |
| History GREEN `235515` | module::test_new_reviewed_family_preserves_expired_historical_charge, `task60-green-history-01` | 0/0; `1 passed in 0.26s` |
| Edges RED `1069e3` | module `-k 'registry_replaced or fresh_process or actual_fsync or invalid_public or live_replacement or missing_registry'`, `task60-red-edges-01` | 1/1; `1 failed, 16 passed, 48 deselected in 2.88s`; registry_replaced: `Failed: DID NOT RAISE Exception` |
| Edges GREEN `7a5867` | same edge selector, `task60-green-edges-01` | 0/0; `17 passed, 48 deselected in 2.75s` |
| Snapshot RED `7c9bbe` | module::test_snapshot_keeps_operation_custody_through_returned_data_construction, `task60-red-snapshot-01` | 1/1; `1 failed in 0.18s`; close during snapshot: `Failed: DID NOT RAISE AdmissionError` |
| Snapshot GREEN `f02f10` | same snapshot selector, `task60-green-snapshot-01` | 0/0; `1 passed in 0.14s` |
| Boundaries GREEN `730822` | module `-k 'nested_scalar or startup or real_budget_io'`, `task60-green-boundaries-01` | 0/0; `15 passed, 67 deselected in 2.02s` |
| Path RED `637d0a` | module `-k job_path`, `task60-red-path-01` | 1/1; `1 failed, 82 deselected in 0.20s`; relative stored job path: `Failed: DID NOT RAISE Exception` |
| Path GREEN `df21c6` | module `-k job_path`, `task60-green-path-01` | 0/0; `1 passed, 82 deselected in 0.16s` |

Here `module` means exactly `tests/test_native_context_diagnostic_admission.py`.
The table records observed results, including intermediate problems rather
than presenting the first attempted implementation as green. Additional
negative coverage that already passed existing validation is coverage, not
claimed as a separate newly failing behavioral TDD cycle.

Exact final focused command, run once after the final code change:

```powershell
.pytest_tmp/qa-python312-c-01/Scripts/python.exe -B -c "import os,subprocess,sys; e=os.environ.copy(); e.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1'); r=subprocess.run([sys.executable,'-B','-m','pytest','tests/test_native_context_diagnostic_admission.py','-q','--tb=short','-p','no:cacheprovider','--basetemp=.pytest_tmp/task60-final-01','--junitxml=.pytest_tmp/task60-final-01.xml'],env=e,capture_output=True,text=True,timeout=60); print('CHILD_EXIT',r.returncode); print('STDOUT\n'+r.stdout); print('STDERR\n'+r.stderr); sys.exit(r.returncode)"
```

Initial terminal chunk `b27ca6` returned actual session `78975` with no output;
completion polled via write_stdin returned chunk `39da2a`, actual outer exit 0:

```text
CHILD_EXIT 0
STDOUT
........................................................................ [ 86%]
.........ss                                                              [100%]
81 passed, 2 skipped in 9.52s

STDERR

```

This is actual child and terminal exit evidence, not an inference from XML.
The XML independently records tests=83, errors=0, failures=0, skipped=2,
time=9.455, timestamp `2026-09-13T10:55:44.408208+02:00`.

## Final file hashes

SHA256 computed after the final run, with no later code/test edits:

| File | Bytes | SHA256 |
|---|---:|---|
| tests/native_context_diagnostic_admission.py | 29270 | f0b0821195d6ebce89bc47e5d37f21dedc36fc8e223678816a932b1aae5d60ad |
| tests/test_native_context_diagnostic_admission.py | 28107 | 53ca8c1b23a455c71d59cf236c1b6f95e4d2fecdb442d457ae9859db5fa9094a |
| .pytest_tmp/task60-final-01.xml | 14499 | 144871b78857f9c3651d45807876d9de8e14203f71050820b77d465f4b6eb0a4 |
| .pytest_tmp/task60-red-01.xml | retained | 7e573dd22139bc48dd48f52e706da3d08fd83d7e8746e81d7c953f2a620d0fa5 |

This report's final SHA256 is supplied in the return message, avoiding a
self-referential hash embedded in its own bytes.

## Concerns, limits and remaining authority

1. Native Linux effective-root ancestry, DAC, no-follow, actual flock/fdinfo and
   directory-fsync branch is implemented but NOT executed here. The two native
   tests explicitly skip on Windows. They require an operator-supplied
   `BETBOY_ADMISSION_NATIVE_TEST_ROOT` under protected ancestors (e.g. an
   isolated disposable namespace under `/var/lib`, never default `/tmp`). It
   must supply empty `registry`/`job` directories; the negative test creates
   separate retained loss/writable/link fixtures under that disposable root.
   Do not run these against the real one-shot production diagnostic registry.
2. The parent must load only controlled stdlib/reviewed budget code and held
   registry source before root operations. This module does not authenticate
   its source, imports, installation, supplied hashes, complete baseline,
   closure, corpus size, or plan semantics. Root must independently validate
   the complete Task59 atp-heavy [0,1024) plan before any catalogue copy/worker.
3. The trusted controller owns private implementation state and descriptors;
   snapshots are not reusable capabilities. Host/root compromise, hostile
   mutation of Python private state, foreign privileged file edits, deliberate
   replacement/re-execution of the controller to evade its in-memory poison,
   whole namespace rollback, and VM rollback are outside the claim. There is
   no persisted oracle proving whether a previous fsync returned success.
4. The entire fixed parent's 60CPU lifetime (including admission startup,
   output and cleanup), the one worker's 240CPU ceiling, process-tree stopping,
   AS/RSS/output/disk/free-space/source/model enforcement remain the later
   fixed parent's responsibility. This module launches nothing and grants no
   worker permission. It retains a full 300CPU ticket without settlement.
5. Binding specs remain C SHA256
   `08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba`
   and B SHA256
   `498e63c5641adaccdd4d284fa9b57ad93c02ba834e9abd6bf4064636d6b12da1`.
   CPU300/portion, aggregate1800CPU/3600 boot-inclusive wall, AS2GiB,
   RSS<1GiB, output1MiB, active4GiB, new-QA8GiB/free4GiB are not changed.
   Historical1770CPU reservations and separate metadata diagnostic ceiling20CPU
   (measured3.247115605CPU, no durable ticket) stay separately recorded by Root;
   the retained-history digest is not a refund credential or fabricated settled
   C proof. C/B/empirical/release remain incomplete.
6. This is an implementation self-review, not the independent task-scoped
   spec/quality review. No native run, publication, deployment, proof reuse,
   catalogue import, repair, or release readiness is asserted.

## Sole-writer return

The final code and test hashes above are frozen for Root review. I explicitly
relinquish sole-writer authority over the two QA files and task-60-report.md on
return. Root alone owns staging/commit/integration and subsequent review.
