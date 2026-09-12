# Task 48 — small actual copied receipt corpus owner

## Status and byte binding

Implemented the authorized small, one-call Copy → actual receipt append →
single commit/close → cold complete verification chain. Local owner QA is
complete; this stand is frozen for Root's independent review. It is not a
native/global C, source-truth, B, publication, restore or release acceptance.

Requirements: `task-48-brief.md`, with the previously approved scope and API
unchanged. Only the following implementation/test files and this report were
edited. No shared primitive, existing product owner, dependency, Git state or
server was changed by this task. Old QA artifacts were retained.

| File | SHA-256 of final tested bytes |
| --- | --- |
| `context_storage_v2/receipt_corpus.py` | `fdbebbed9e0b14380d7226660f5f42ec9508ec2b04c727a856bb36747ae660d6` |
| `tests/test_context_storage_receipt_corpus.py` | `54878ae031dbe30d1321923b8296f8372fcada8b0dec7372cf728b52dbec2c13` |

Unchanged linked primitives were freshly hashed before the final run:

| File | SHA-256 |
| --- | --- |
| `copying.py` | `15c031ad5727c69b218d3487bc981ad3126e9e285d254822e94597ade09f0b23` |
| `inventory.py` | `7e099cd9ed5e5b336519a23cc891e85c2136dda9fa6324c6f433f61bb37e967b` |
| `sqlite_profile.py` | `05898adf9782ff06e2edcf33d45c94dd6ecce232ddba1f81ffcfaf65fca3d8bc` |
| `receipt_append.py` | `e96b807b2b003b00b740b0b64ba48d86ac3fd5c930ce11bdf2a40b5436fa06e9` |

## Implemented contract

```python
build_receipt_corpus(source, observations, *, expected_source_sha256,
                     workspace, owned_directory, main_cap_bytes,
                     ledger_cap_bytes, limits=DEFAULT_LIMITS)
```

The only public operation performs its own actual `copy_legacy` into the fixed,
already private, empty direct-child directory. No writer escapes, no existing
or resumable main is admitted, and no `CopyReceipt` or raw path grants write
authority. The new private copied writer does not invoke or bypass the existing
fresh-writer constructor. Source-header 01/01 is checked before schema access,
so the actual checkpointed WAL rejection creates no WAL/SHM companions.

The new exact `TrackedConnection` uses effective MEMORY TEMP before all other
SQL; the compile-time TEMP_STORE override is checked before TEMP schema work.
It then binds DELETE/FULL, 8192-KiB cache, zero mmap/ATTACH/worker threads,
defensive/untrusted schema, disabled extension loading, fixed complete-page
main ceiling, no explicit TEMP objects and the actual source page size and
UTF-8/UTF-16 encoding. No page format, schema or source policy is rewritten.
The main write transaction is begun once; the owner has one commit point.
Normal cursor/blob APIs are tracked and closed before the connection/FD and
the cold read-only transition. The original source transaction/profile remains
unchanged on successful calls.

Each iteration normalizes only one `(record, observed_at)` pair. The unchanged
Task44 append performs canonical-byte/content/receipt identity, physical
readback and collision checks inside the held transaction. Idempotent inputs
and already existing source receipts are not counted as inserted members.
The public result is closed historical evidence, not a verified source mapping
or a token allowing reopening for writes.

The fixed `receipt-additions.bin` is created O_EXCL and retains its FD. It stores
a versioned 40-byte header and actual 41-byte `(table tag, signed rowid,
typed-row SHA-256)` entries obtained from the inserted physical rows. Capacity
is `floor((L - 40) / 82)`: both external-merge banks lie within the explicitly
reserved L-byte file. The written append stream is independently rehashed before
sorting; bounded initial runs and sequential two-way merge passes replace a
large Python set or millions of individual random membership seeks. At most
1 MiB of packed entry data per run/buffer is used, plus bounded Python object
overhead; this is not a measured RSS proof. The file may contain a sparse gap
between banks, which remains charged as part of its logical file extent.

After writer commit/close, a new effectively profiled read-only connection is
bound to the same owned main inode and complete terminal identity. Actual full
source/output inventories and schema identity are checked. A second complete
rowid merge compares every old row and typed field, including unrelated future
rows, NULL, NUL-bearing TEXT/BLOB and values larger than a processing block.
Every non-source output row must match the next actual ledger entry exactly.
Strict ordered ledger membership and complete consumption reject duplicate,
missing, extra and same-count-other-member substitutions. Signed rowids do not
assume monotonic insertion after an existing INT64_MAX rowid. Source, output
and entire ledger hashes are then read from the actual files; terminal close,
path identities, original deadline and capacity checks precede success.

Before copying, local admission includes source + M + L active bytes and the
whole supplied workspace + remaining M + M + L + 64 KiB metadata. L must be at
most M, consistent with an external single FSIZE=M envelope. The operation
observes available reserve and fixed file sizes during processing; these are
not physical/global quota guarantees. One original 300-second cooperative wall
deadline spans this entire call and is checked again after potentially slow
terminal capacity observation. It is not a CPU meter or a hard interrupt of an
individual blocking kernel/Python call.

## Concrete RED → GREEN evidence

TDD and systematic-debugging workflow preserved the existing initial work and
used actual fixtures to expose failures before each corrective implementation
change. All artifacts below remain under `.pytest_tmp/`.

| Evidence XML | Actual observed result and disposition |
| --- | --- |
| `task48-corpus-ccr01-red.xml` | Initial test-first missing-module collection error, not a semantic reproduction. |
| `task48-corpus-ccr01-green1.xml` | Initial 11-test implementation checkpoint; not treated as completion. |
| `task48-corpus-ccr02-red1.xml` | Six real failures: L > M admitted; same-byte new-inode main replacement across writer-close/read-open; late main and ledger replacement accepted; ledger constructor fstat failure leaked its FD; failed tracked connection close left the real connection open. |
| `task48-corpus-ccr02-green1.xml` | All initial 17 tests passed after those fixes. |
| `task48-corpus-ccr02-red2.xml` | Three real failures: late final capacity work escaped the original deadline; actual WAL header admission created companions before rejection; a failed peer query left its already-created source cursor open. |
| `task48-corpus-ccr02-green2.xml` | All three corrected regressions passed. |
| `task48-corpus-ccr02-red3.xml` | Two failures and two passes: main/ledger OS-close errors before actual close leaked FDs; errors after actual close already stopped correctly. |
| `task48-corpus-ccr02-green3.xml` | All four OS-close cases passed after bounded identity-aware cleanup. Any reported close error still prevents success. |
| `task48-corpus-ccr02-membership.xml` | 13 genuine full-row/membership/bounded-merge cases passed. |
| `task48-corpus-ccr02-lifecycle.xml` | Eight passed, one test-harness NameError from a misplaced test edit; not a product RED claim. The test placement was corrected without weakening assertions. |
| `task48-corpus-ccr02-lifecycle-fixed.xml` | 13 actual allocation/commit/collision/handle-close cases passed, including all four OS-close regressions again. |
| `task48-corpus-ccr02-profile-io.xml` | 26 clock/idempotence/profile/deadline/slot/ledger-I/O cases passed. |
| `task48-corpus-ccr02-final.xml` | Final complete owner file: **72 passed in 44.22 s**, process exit 0. |

Concrete fixes bind complete path identity across final reopen and late close,
retry disposal only of a still-observed own FD after a close error, preserve
the original STOP on every such error, close a real connection after a failed
tracked-close boundary, and use paired query-cursor cleanup even if creating
the second cursor fails. No cleanup deletes a failed main or ledger.

The final 72 cases include:

- Actual legacy-path differential for three real Tennis receipts and all
  nine stored receipt fields, cold Tennis status validation, full raw inventories,
  UTF-8/UTF-16le/UTF-16be, pages 512/4096/8192/65536, large and NUL-bearing old
  data, all seven nonempty original tables, signed INT64_MAX and input reuse.
- A real 19-record/38-member 512-byte-chunk fixture that forces multiple initial
  runs and merge passes inside the one ledger reservation; actual read/write
  request bounds and final complete membership are checked.
- Actual old-row and new-member deletion/modification/addition, altered ledger
  membership, post-close same-byte inode replacement, source end/restart,
  iterator failure, already stored receipts, and equal content at distinct
  actual ingestion timestamps.
- Real SQLITE_FULL and SQLITE_TOOBIG, a denied COMMIT, an actual second SQLite
  reader causing SQLITE_BUSY at COMMIT, failures before and after a real
  COMMIT, and real source content/receipt collision rejection matching legacy.
- Actual normal cursor/blob lifetime, MEMORY-first/no-DDL writer SQL, unchanged
  source profile, commit/rollback/script epochs, TEMP/main DDL, factories,
  isolation/cache/mmap/query-only/config/ATTACH/thread drift, workspace/free
  reserve/limit changes and unexpected retained sidecar.
- Real short reads/writes, zero write progress, premature EOF, changed written
  ledger bytes, fsync error, constructor failure, and before/after-close errors.
  Fault injection is explicitly local error-path evidence, not native syscall
  fault or hostile Python containment certification.

Final command, from the worktree root:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider tests/test_context_storage_receipt_corpus.py --basetemp=.pytest_tmp/task48-corpus-ccr02-final-base --junitxml=.pytest_tmp/task48-corpus-ccr02-final.xml
```

Every run used a new base directory and XML. Local runtime: Python 3.12.14,
SQLite 3.53.1, pytest 9.1.1, Windows. Following Root's scope instruction, no
broad repository/native suite was run here. The complete owner file, not old
counts or only selected latest tests, is the final tested claim.

## Remaining boundaries for integration/review

1. The input source must actually be sealed and its exact held reader must have
   the external appropriate source policy. All source/worker namespaces must be
   private, exclusive and quiescent. SQLite opens paths, not this Python-held
   main FD. Foreign connections, adapters/converters, callbacks, raw-base-class
   bypass, concurrent FD allocation and ABA remain excluded by the native
   closed caller, not magically prevented by Python identity readback.
2. Normal allocation/I/O/transaction/close errors fail closed and retain files.
   An already performed unsupported commit cannot be undone; tests expressly
   retain its committed but unpublished main while refusing a result. If the
   operating system persistently refuses disposal or an identity readback is
   uncertain, STOP is not evidence of physical release; outer process custody
   and terminal reaping remain required. Cleanup never blindly closes a reused
   descriptor number and cannot claim a hard return from uninterruptible I/O.
3. M/M/L reservations, page ceilings and workspace/free-space observations do
   not enforce a physical disk quota or bound all hidden/foreign allocations.
   Physical metadata, other active inputs, runtime/QA/archives/failed attempts,
   all-job CPU, native FSIZE/AS/RSS, actual free reserve and the complete native
   namespace catalogue still belong to the later integrated owner.
4. A single input record is normalized/materialized at a time; its own size is
   an outer admitted input/memory condition. Full inventories, hashes and many
   repeated profile checks have real cost. No large-corpus timing, 490000-record
   fit, CPU-budget extrapolation, resumable portion, earlier-budget restart or
   existing-filled-main continuation was built or asserted.
5. Raw byte preservation and genuine receipt append do not validate the entire
   old/new corpus as source truth. No `VerifiedReceiptMapping`, protected-empty
   substitution, real Tennis consumer/predictor, empirical model acceptance,
   generation manifest, B, restore or release step is supplied by this result.

Next action is Root's independent review of these frozen bytes and the actual
small chain. Any broader source/History/consumer/native integration is a
separate task, not an implicit extension of this local completion.
