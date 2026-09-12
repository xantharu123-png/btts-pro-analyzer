# Task 51 — actual C Tennis consumer bridge

## Scoped result and execution boundary

Implemented the approved two-phase, same-call consumer in the three-file scope.
Final changed-file coverage is **54 passed, 0 failed/errors/skipped**. The earlier
coupled scope is **704 passed**, on the separately pinned pre-rowid version below;
it is not relabeled as a 704-test run on the final product bytes. No native,
global-C, B, empirical model, production, or release approval follows from this.

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.
Task51 BASE is `9b7d779495fb38c22c62af957a680dc90c91d870`, freshly supplied by Root
at activation. Root reported Task53 implementation
`d787db43170ad2296a02640cdf6091db1f533f4a` independently approved and main `2dd1116`
unchanged. No Git command was used to restate these controller-owned facts.
The live History/Tennis v3 files were separately SHA256-bound before use.
The final brief, including Root's ordinary-table rowid ruling, hashes to
`9157416ea0cf7550cc91eb7fe63786b8d3aa173f942dfda501561b91e14fadc8`.

Only these files were created/modified by this implementation:

- `context_storage_v2/tennis_consumer.py` (new product module).
- `tests/test_context_storage_tennis_consumer.py` (inherited RED tests preserved
  and extended; accidental source `SQLITE_LIMIT_LENGTH=block_bytes` removed).
- `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-51-report.md` (this report).

Ignored pytest directories/XML remain in place, including all failed attempts.
No prior product module, source-owner policy, dependency, model rule, profile,
Git state, server, existing application database, or cleanup mechanism changed.
No subagent was started. TDD drove the missing-module and concrete regression
REDs; systematic debugging distinguished invalid fixture expectations from
actual product gaps; verification-before-completion required completed runs and
fresh byte pins before the freeze. Independent Task51 review remains Root-owned.

## Actual API and ownership

```python
prepare_tennis_consumer(history, *, native_competition, tournament_id,
    grouping_slug, observed_at, surface, best_of, indoor, cutoff,
    work_directory, owned_directory, main_cap_bytes)
put_tennis_consumer(connection, prepared, *, created_at)
```

Preparation requires the real live `HistoryView` of the reviewed v3 format and
the same canonical cutoff. The feature writer receives the mandatory, already
reserved, fixed empty `owned_directory` and the existing main-file cap. Its
writer is completed/closed before preparation returns; the resulting real
`StreamingTennisFeatures` remains live and source/history-bound. Preparation
owns only that feature lifetime. It neither closes the caller's Source/History
nor deletes any successful/failed file or releases any disk reservation.

`PreparedTennisConsumer` is not a public constructible digest ticket. Its bound
history, feature handle, immutable encoded header, metadata, code hashes and
once-only publication state are held by the actual object. Public Original,
prediction and metadata views are detached copies; the actual feature accessor
retains its guard. Closing preparation/features or losing an owning lifetime
cannot be repaired by re-entering the object or copying public hashes.
There is no claim of protection against arbitrary Python introspection or a
hostile code author executing inside the same process.

Publication uses the caller's already-active tracked output transaction, on a
different file from Source/History/features. It attempts publication only once,
under the existing C2 outer savepoint, and never opens or commits an output
connection. Original insertion, complete refsets, snapshot parts, collisions,
sidecar validation, final code reads and final input lifetime checks are inside
that rollback scope. Failures poison the preparation. SQLite FULL/TOOBIG can
also cause SQLite itself to roll back the entire caller transaction; no stronger
savepoint promise is made for such an automatic SQLite rollback.

Returned `PublishedTennisConsumer` is detached result data, not durability or
reuse authority. The caller must complete required cleanup, including
`prepared.close()`, before accepting/committing its whole build. The dedicated
late-close test closes the real feature handle and then raises; the enclosing
caller does not commit and all created files are retained. A result returned
earlier cannot certify the success of future cleanup or an outer commit.

## Source, prediction and legacy semantics

1. Normalize the real supplied native competition with the unchanged status
   owner. Resolve its actual stored receipt in the complete event history. The
   exact latest singleton, status/schema, receipt clock, revision, event/tour and
   cutoff must match. Missing, stale, conflicting same-time, wrong-tour and
   changed-native cases fail; a genuinely later receipt beyond the as-of cutoff
   remains excluded by the old as-of semantics.
2. Before the old in-connection artifact loaders, traverse physical metadata
   of all rows of the three actual closed-schema tables `artifacts`, `manifests`
   and `active_manifest`. Fetch only real integer `rowid`, `typeof` and
   `octet_length`, in deterministic rowid order. Hash length-framed canonical
   `[ordinal, rowid, ...physical fields]` incrementally and retain only three
   aggregate records (count, total bytes, largest value and digest). No payload,
   key list or unbounded metadata inventory is collected. Actual Source/History
   checks bracket the scan and every row. The ordinary schemas and rowid use
   were freshly checked against `context_runtime._SCHEMA`/`_verify_schema` and
   C `inventory._raw_rows`; no WITHOUT ROWID fallback/schema variant was added.
3. Load the actual active manifest/state through `_load_active`, `_artifact`
   and `_decode_wrapper` on that exact held source connection. These unchanged
   owners retain consumed storage-type, canonical JSON, digest, timestamp,
   training-cutoff and semantic admission. Metadata equality is only an
   observation, never content equality, D2 authority or receipt authentication.
   The held Source's complete file/input identity remains the byte binding.
4. Invoke real `tennis.predict.predict_match` exactly once with the actual
   loaded state, native participant names and decision arguments. The real
   callback runs only during this call and exactly once, with the precise
   `inputs`/`values` shape; it cannot overwrite owning state/native/code fields.
   Re-encode/check the real state, artifact reference, training cutoff, actual
   code files and source lifetime after prediction. Build the real old Original
   using its unrounded capture, not the rounded public prediction or a made-up
   `original_base` input. Preserve `native_state_identity="unresolved"`.
5. Use the unchanged `_Inventory` with its genuine recursive in-connection
   artifact/D2 checks, actual selector and existing pure eligibility,
   comparison, approval and result validators. The bridge neither invents an
   empty protected-receipt set nor constructs a replacement receipt validator.
   A Task48 descriptor is not taken as protected-original/receipt authority.
   Real approval absence, ambiguity, wrong-surface and invalid active approval
   remain distinct; the fixtures do not manufacture a positive empirical
   approval to make a model apply.
6. Build the actual v3 streaming feature artifact. Consume its complete
   canonical feature bytes only within the existing C2 one-MiB non-observation
   header envelope, including every feature ref and state. Legacy full-list
   feature/history APIs, provider/Daily/Shadow and path-based legacy writers
   are never entered by the new bridge. They remain only the independent test
   oracle before the source is pinned.

There is no added 16-MiB or 64-MiB artifact/row admission limit and no retuning
of the pinned Source. The default-block regression uses an **actual old-admitted
16,777,846-byte active state BLOB**, enlarged through an unrelated valid Elo key
without changing the predicted two participants or enlarging the native event
or feature header. The actual old publish/load/predict/finish and new consumer
both run. XML records source `SQLITE_LIMIT_LENGTH=1,000,000,000`, unchanged.
This proves this particular old-admissible value crosses the default 16-MiB
processing block; it does not prove all large values fit a native heap/RSS cap.

UTF-16LE and UTF-16BE sources are real SQLite databases. Unselected opaque
artifact payload bytes including NUL/non-JSON bytes remain unchanged and are
not subjected to a new JSON admission rule by the metadata pass. Deliberately
invalid physical types in a consumed active state are rejected by actual old
owners, without replacing validator results.

## Full membership and canonical byte transport

- Replay the complete selected History through its real v3 resolver, including
  source-backed rows. Check count, total canonical size and the original
  length-framed full-row SHA against `History.binding.selected_digest`. Hash
  updates are bounded; no whole-tour observation list is retained. Decoding
  and canonicalizing an individual old row can still allocate its full value.
- Stage the actual digest stream with C2 `put_refset`. After full replay, use a
  key-only ordered projection of the same guarded v3 History spool and compare
  every key against the actual stored C2 set. Check the complete count and
  ordered membership, not only a count/digest or feature-selected subset.
  Missing, additional, same-count-swapped and duplicate key cases fail.
- Check all real feature refs and the actual native receipt are members of
  that full set. Only this required subset is retained in a Python set, bounded
  by the complete one-MiB header, not by tour size.
- Incrementally reproduce the old input-descriptor digest, sorted union of
  complete context refs, snapshot key, raw canonical payload SHA/length and
  legacy `{"key": key, "payload": full_payload}` digest. The existing bounded
  ref-chunk owner emits the complete observation array. No fake list is passed
  into `calculate_context_payload` and no whole-payload 64-MiB helper is used.
- Write the actual Original artifact and complete snapshot parts together;
  validate immutable collisions and actual stored Original publication time.
  A caller may reopen committed parts and obtain byte-identical old full
  snapshot decoding and consumer-reference data.

The actual small old capture/predict/persist/finish sequence is the independent
oracle for ATP/WTA, unrounded Original data/hash, all features, full snapshot
bytes/key/payload digest and catalog outcomes. Nonempty completed-match cases
cover both known real end times and unknown end times/lower-bound recovery.
Thirteen-row full-membership cases intentionally include observations unused
by the feature vector. Reversed incoming ref order still produces the exact
old canonical ordering; replacing one same-count member does not.

## Retained REDs and their interpretation

The inherited five tests were RED because the module did not exist. Their
accidental SQL value cap was removed before the resumed five-test RED. Twelve
additional real behavior tests were also RED before the first implementation;
the first implementation passed all 17.

`boundaries-04` had 8 test-fixture/expectation failures, not 8 product findings:
four cases incorrectly expected one feature ref where the actual old empty
history feature vector has zero; three consumed physical-type corruptions were
already rejected by genuine RawInventory before the fixture reached the
consumer; one lifetime test expected the new error subclass but the actual
Source correctly raised `RuntimeArtifactTrustError`. The physical-type tests
now explicitly assert that early raw rejection and separately exercise the
actual History/consumer boundary; they never represent invalid raw admission
as successful. Existing valid 16-MiB-boundary and other cases already passed.

`gaps-red-05` then established **two actual product defects**, independently of
those fixture corrections:

- A wrapper around the real predictor added a top-level `state_hash` to its
  genuine capture. Unchecked `**capture` could override the actual owning state
  identity. The callback now accepts exactly `inputs` and `values`.
- The real final code-file read was followed by an actual feature close. The
  final lifetime check raised only after savepoint release, leaving seven new
  output tables alongside the caller's existing marker. The final check is now
  after that file I/O **inside** the publication savepoint. The unchanged probe
  verifies rollback leaves only the preexisting caller marker.

Both original genuine RED probes pass in the final run.

`selected-07` had four further test-oracle setup failures: the old unknown-end
case legitimately yields `None` for observed sets rather than two; three
latest-revision tests invoked an old path loader while the actual Source was
pinned, and its schema writer hit a real SQLite lock. The old oracle was moved
before source pinning, not enabled within the product bridge; a separate
actual-known-end case retains the three-set/exact-recovery expectation. No
source profile, lock, end-time rule or validator was relaxed to fix a test.

After the 704-test coupled run completed, Root's final rowid ruling was applied
with a new genuine RED: move only real artifact rowids by +1000 or manifest
rowids by -1000, leaving every stored field/type/length, real Original and full
old snapshot unchanged. Source file hashes already differed, but the previous
ordinal-only metadata hashes incorrectly remained equal. Both cases failed
at that exact assertion. Final metadata now frames the actual signed integers
in deterministic rowid traversal. This repairs the observation binding only;
the full Source identity was never replaced by that metadata hash. Only this
narrow product change and its two tests followed coupled scope 09.

## Commands and complete retained QA record

Runtime observed locally: Python **3.12.14**, Windows AMD64, SQLite **3.53.1**.
This is local execution, not Linux/native supervisor evidence. Each run used a
fresh retained basetemp and XML. Common resumed command prefix, from the above
worktree (no dependency or pytest-cache mutation):

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -o junit_family=xunit1
```

For runs 01–08, the test file was `tests/test_context_storage_tennis_consumer.py`.
Suffixes below omit only the common `.pytest_tmp/` prefix. The old inherited
20260912-1 XML is retained historical evidence, not a newly repeated run.
All rows have zero errors and zero skips; elapsed time is the XML suite time.

| Run / XML | Tests / failures | Seconds | Basetemp suffix | Extra selection |
| --- | ---: | ---: | --- | --- |
| `task51-red-20260912-1.xml` | 5 / 5 | 1.458 | inherited run | module absent |
| `task51-resume-red-01.xml` | 5 / 5 | 1.855 | `task51-resume-red-bt-01` | none |
| `task51-behavior-red-02.xml` | 17 / 17 | 1.671 | `task51-behavior-red-bt-02` | none |
| `task51-first-impl-03.xml` | 17 / 0 | 11.225 | `task51-first-impl-bt-03` | `-x` |
| `task51-boundaries-04.xml` | 35 / 8 | 51.383 | `task51-boundaries-bt-04` | none |
| `task51-gaps-red-05.xml` | 2 / 2 | 6.447 | `task51-gaps-red-bt-05` | `-k 'capture_cannot_replace or final_code_read'` |
| `task51-boundaries-06.xml` | 37 / 0 | 54.645 | `task51-boundaries-bt-06` | none |
| `task51-selected-07.xml` | 10 / 4 | 32.201 | `task51-selected-bt-07` | selector A below |
| `task51-selected-08.xml` | 7 / 0 | 10.544 | `task51-selected-bt-08` | selector B below |
| `task51-final-scope-09.xml` | 704 / 0 | 398.540 | `task51-final-scope-bt-09` | coupled command below |
| `task51-rowid-red-10.xml` | 2 / 2 | 10.267 | `task51-rowid-red-bt-10` | `-k physical_metadata_binds_actual_rowids` |
| `task51-final-consumer-11.xml` | 54 / 0 | 40.596 | `task51-final-consumer-bt-11` | none |

Selector A: `-k 'nonempty_performed or latest_complete or actual_utf16 or does_not_enter or reconstructed_from_public or existing_original_creation'`.
Selector B: `-k 'nonempty_performed or latest_complete or actual_feature_reference or header_serializer'`.
Every resumed command also supplied `--basetemp=.pytest_tmp/<listed suffix>`
and `--junitxml=.pytest_tmp/<listed XML>`.

The final relevant coupled invocation, chosen for actual History/Tennis/C2 and
legacy consumer/predict/capture/publication coupling rather than a broad project
rerun, appended exactly:

```text
tests/test_context_storage_tennis_consumer.py tests/test_context_storage_history.py tests/test_context_storage_tennis.py tests/test_context_storage_refs.py tests/test_context_storage_snapshots.py tests/test_context_transport.py tests/test_context_transport_bytes.py tests/test_tennis_live_worker.py tests/test_tennis_live_origin.py tests/test_tennis_live_integrity.py tests/test_tennis_consumer_binding.py --basetemp=.pytest_tmp/task51-final-scope-bt-09 --junitxml=.pytest_tmp/task51-final-scope-09.xml
```

Session `71276` finished Exit 0, pytest summary **704 passed in 398.56s**.
No code/test edits occurred during that run. After its completion the rowid
regression was added and reproduced on the same product; session `85741`
finished Exit 1, **2 failed, 52 deselected in 10.27s**. The sole following
product delta was the metadata doc/query/integer/rowid-frame change. Root
explicitly requested changed-file covering tests rather than repeating the
unchanged broad scope for that frame change. The final invocation appended:

```text
tests/test_context_storage_tennis_consumer.py --basetemp=.pytest_tmp/task51-final-consumer-bt-11 --junitxml=.pytest_tmp/task51-final-consumer-11.xml
```

Session `17703` finished Exit 0, **54 passed in 40.60s**, with no warnings
reported. It includes the unchanged true capture/savepoint REDs, the actual
16,777,846-byte A1 state, UTF-16/opaque-byte cases, full-membership differentials,
real SQLite FULL/TOOBIG, actual known/unknown match ends, source/epoch/feature
lifetime failures, collision/once-only, late cleanup, reopened full decoding,
and the two new positive/negative-rowid regressions.

### XML SHA256 evidence

```text
task51-red-20260912-1.xml  f3c8285686424151cc0947b81d42c556e1f77ffd641f79f5a996e77865eabb77
task51-resume-red-01.xml  890643c63487e09a318b8920ca961c31ef08043fa296aaee56571f74307b8ed5
task51-behavior-red-02.xml c0ad38510bc55e951cab0715d74a0dca8c2175ccdd9dada0e097424362e75496
task51-first-impl-03.xml   b7d4458708bfe159f841960a32027d32ca865328c5c27cb1b0572289955c96ce
task51-boundaries-04.xml   875ee57b6d5b079744e26f1881b33cc2808349f507ee21bb9b1efb2a2465bc17
task51-gaps-red-05.xml     11c37855a2a28e507f3e0a5ffc1d75bff6b4c1d281c10317aec766ad1e23b519
task51-boundaries-06.xml   c4099872b08a456e713f8fdf815c73f150e0c465ffda9abf952e9652055c6d10
task51-selected-07.xml     d5fb8242bff148d174c1c0a63ac50fed876d8ae2171dace0c8eac37e7bedbbce
task51-selected-08.xml     dd828310946262b5c62c635c628de1556796f107d71c5331ac55b1ef7facfc5a
task51-final-scope-09.xml  a219b9a209bb6610c495c62f13125cbd84cab5a5b853102a66e90314523cdbab
task51-rowid-red-10.xml    bd504039f2fc65347210b67cb4d795287b5b97f3763035acb2d1632771be2ff1
task51-final-consumer-11.xml 21f3e3f4fdf155d814cd4f1519d7e95f900d83135539b6a7fd460807ea1099e7
```

### Exact product/test version separation

```text
Inherited five-test file before resumed edits:
16e55793cfb2f4566241b5f5a97115dfee096c8fa2b10c183e9821aa42e404cb

Coupled 704-test run 09, before actual-rowid change:
context_storage_v2/tennis_consumer.py
8102695ad7b1b457ed1a6cb96308f06b610171f7ec8f3050e254762b4accefe7
tests/test_context_storage_tennis_consumer.py
5d960f12be1ab0bcd4a06bb4ba038ad38570e11325a0af14e8da21261f1b7612

Final 54-test run 11 (also test bytes of rowid RED 10), frozen:
context_storage_v2/tennis_consumer.py
fcd05c52f7c550510ee82c110efe1559f07bc9495b20dbedd874b018ac6e0de5
tests/test_context_storage_tennis_consumer.py
bd0a496008ba6e671b562f433a5c27226784e9f77a8404fb061498e239c9bc2c
```

Existing directly coupled owner bytes, freshly rechecked and not edited here:

```text
context_storage_v2/history.py d1d52b0c14dcd2614d81ba7371d2809d2d31e536c6d107f07a8ffa3520e4faf8
context_storage_v2/tennis.py dcd337f36b58bfb316864c0e5e6c611d9f42ce3d968037bce1d5956120cf6e53
context_storage_v2/refs.py e80492be96ea0aacd5bb2038018c90bf8201d3e4a616d2574c456d5f9899cb2b
context_storage_v2/snapshots.py f5dc0903874bede9fbbe3196146ba0b4b000d6a962916afd1d24efdb625f14ba
context_storage_v2/ref_chunks.py 49c41fac294bb6255e083cb07afad592a1460c84215dfa98842e233d8ef6d63d
context_transport.py a47d980a4e528ef12917db39e47d025c4670070737901f6e8c9688dfe84a1a9e
tennis/live_context.py 91416948aed90bbd503f83a2ecd330f22be6985562aea9a42f3b2f081f6bc8fd
model_artifacts.py 6cd072f4cf77a9405091fbdc166580cd403ba15e232c915414be493de9fd6d16
```

## Remaining boundaries and handoff

No remaining concrete scoped implementation finding is known from these tests
and the implementer's final inspection. This is not independent approval.
Root owns Task51 review, Task54 actual fresh Corpus/copy/D2/protected-receipt/
History/consumer integration, indexing/commits and subsequent native work.

The following are explicitly **not proved or implemented by this bridge**:

- Native AS2GiB/RSS<1GiB, per-worker CPU300s/output1MiB and total CPU1800s/
  elapsed3600s accounting, custody/reaping or actual platform syscall behavior.
  Old A1/D2 recursive loaders and individual row/state JSON operations still
  allocate complete objects. This may require a native resource STOP; it does
  not authorize truncating input or silently declaring a smaller closure.
- Protected root namespace/sealed input/dependency/code closure, global input
  <=4GiB, total job/retries/QA workspace <=8GiB and free reserve >=4GiB. Main M
  plus journal M are the existing logical writer slots, not this module's
  physical quota proof. Failed files remain accounted for by the outer owner.
- The actual runtime closure for `tennis.predict` and its transitive
  `tour_state`/backtest/data-loader/pandas/requests dependencies. Legacy
  `CODE_PATHS` file hashes preserve the Original format; they do not authenticate
  already-imported bytecode, native libraries or a privileged publisher.
- Full 590553-receipt/199-consumer growth, fresh complete-source corpus
  reconstruction, empirical fatigue/injury acceptance, authenticated B
  verification/reuse/restore, Daily/Shadow integration, deployment or release.

Product and tests are frozen at the hashes above. After this report's final
readback/hash, this agent relinquishes the sole writer role to Root. No extra
implementation, test rerun, cleanup or Git/server action is pending from this
agent without a new scoped assignment.

## Independent review fix round 1 of 5 — final post-footprint lifetime

This append supersedes the earlier no-known-finding handback for the specific
P1 found independently after that handback. The earlier report, failed tests,
successful tests and version distinctions above are retained, not rewritten.
FIX_BASE supplied by Root is `f777e9ea2b6313e187d911877f5669a832ee5786`.
The complete independent review was read before changes and matched SHA256
`946b0b6ababe6ca5426ef8236f66c7983d3b93c0acf847ca5ce0e0fc04d12af6`.
The updated brief with Root's exact private-owner seam ruling matched
`67b7c5ae159f4fb02c393db0f81702e7fdcc44f5af06e0b924b4ceee7aecd88c`.

### Finding, genuine RED and minimal correction

The reviewer identified that the last body-level `prepared.assert_intact()`
still preceded `refs._atomic`'s own post-yield `_check_footprint`. That existing
helper performs real path/companion stats and `shutil.disk_usage`, then releases
the savepoint without checking the consumer's actual input owners again.
Thus a genuine feature/history/source lifetime loss during that later I/O
could return a Published result. A check after RELEASE would not repair the
required rollback behavior.

The new retained consumer regression was run **before either product edit**.
It invokes the actual old oracle, actual new preparation and output writer.
A wrapper executes both actual code-file reads. After the second, a wrapper
executes the real `disk_usage` and closes the actual held feature owner before
returning the real measured values. At that point the actual output already
contains one Original and one snapshot header. There is no fake validator
return, replacement footprint result, skipped owner or invented native proof.
The original product returned normally: **DID NOT RAISE StorageIntegrityError**.
That is the independent review's actual failure boundary, not an assumed one.

Only two narrow product edits followed:

- Private `refs._atomic(connection, limits, *, final_validate=None)` calls the
  optional live validator immediately after its existing post-yield footprint
  check and before its existing RELEASE, within the same `try`/rollback/error-
  conversion scope. It adds no second transaction owner or extra footprint
  operation after the validator. No validator is called on an earlier body or
  footprint failure. Return values are not a proof/token or authorization.
- The consumer's outer invocation supplies the bound real
  `prepared.assert_intact`. Existing body/code-file guards remain. All other
  existing `_atomic` callers retain the default no-validator path unchanged.
  There is no new caller Boolean, format/schema/limit change or source policy.

The unchanged genuine RED now requires a raised lifetime error, no Published
result, rollback of Original/refs/parts, the caller transaction still active
with only its prior marker table and `('keep',)` row, and no prepared reuse.
Seven direct shared-owner cases additionally exercise both default/validator
success, actual footprint ordering, exactly one final validation, no implicit
commit, input-lifetime and ordinary exceptions, a real SQLite query error with
unchanged conversion/cause, and absence of validation after body/footprint
failure. The test hooks perform real measurements and real SQLite work; their
call-order assertions serve the final-check ordering contract rather than
replace it with a mocked success condition.

The old code-file-read regression is unchanged and passes too. The fix was
review-reception/root-cause/TDD driven: verify the supplied control flow, retain
the concrete RED, implement only the adjudicated seam, then run fresh coupled
verification. No unrelated guard, source loader or native capability was added.

### Scope and exact execution record

This round changes exactly five authorized files: the original consumer,
consumer test and appended report, plus the explicitly authorized `refs.py`
and `tests/test_context_storage_refs.py`. Root retains the brief/review/ledger
and Git. No Git/index/server/dependency/cleanup action or subagent occurred.
No files or failed artifacts were removed. The 704-test/project suite was not
repeated for this narrow shared-owner change.

All commands use the common PowerShell environment/runtime/pytest prefix
recorded above, `junit_family=xunit1`, and fresh retained paths. Exact suffixes:

```text
tests/test_context_storage_tennis_consumer.py -k final_footprint_disk_usage --basetemp=.pytest_tmp/task51-fix1-consumer-red-bt-12 --junitxml=.pytest_tmp/task51-fix1-consumer-red-12.xml

tests/test_context_storage_refs.py -k atomic_final_validator --basetemp=.pytest_tmp/task51-fix1-seam-red-bt-13 --junitxml=.pytest_tmp/task51-fix1-seam-red-13.xml

tests/test_context_storage_tennis_consumer.py tests/test_context_storage_refs.py -k 'final_footprint_disk_usage or atomic_final_validator or final_code_read' --basetemp=.pytest_tmp/task51-fix1-focused-green-bt-14 --junitxml=.pytest_tmp/task51-fix1-focused-green-14.xml

tests/test_context_storage_tennis_consumer.py tests/test_context_storage_refs.py tests/test_context_storage_snapshots.py tests/test_context_storage_ref_chunks.py tests/test_context_storage_snapshot_source.py --basetemp=.pytest_tmp/task51-fix1-final-scope-bt-15 --junitxml=.pytest_tmp/task51-fix1-final-scope-15.xml
```

| XML | Result / exit | Console time | XML suite time |
| --- | --- | ---: | ---: |
| `task51-fix1-consumer-red-12.xml` | 1 failed, 54 deselected / 1 | 2.30s | 2.299s |
| `task51-fix1-seam-red-13.xml` | 6 failed, 1 passed, 99 deselected / 1 | 0.47s | 0.400s |
| `task51-fix1-focused-green-14.xml` | 9 passed, 152 deselected / 0 | 3.07s | 3.068s |
| `task51-fix1-final-scope-15.xml` | 411 passed / 0 | 84.95s | 84.937s |

All four runs have zero errors and zero skips. The seam RED's six failures are
the absent `final_validate` keyword before its implementation; the unchanged
default path already passed. These are distinguished from the one genuine
late-I/O publication failure in consumer RED 12. Final session `72641` completed
Exit 0 without any product/test edits during execution and no warnings reported.
The five complete test-file counts are consumer **55**, refs **106**, snapshots
**96**, ref chunks **71**, source adapter **83**, totaling **411**. These are the
approved genuinely coupled files, not an assertion about unrerun legacy suites.
The final run still records actual old state BLOB size **16,777,846** and
unchanged source SQLite length limit **1,000,000,000**.

```text
task51-fix1-consumer-red-12.xml
83be17c2afc36a51d3941566d0816d7bf37b85b8e7cb05147d4af8f2661598aa
task51-fix1-seam-red-13.xml
734d78aa4663be7526d88c5c39dfde91ff5c105483ef1aafb1c9c7fd06c638b6
task51-fix1-focused-green-14.xml
5de4d8e1340c9c7e72d657704a129684a530937c568e9b96f59ac0b021977c43
task51-fix1-final-scope-15.xml
64cd5582a4c4a734c9a3c8cefec66cfce968f810d054dc029f0dd0a573a184fb
```

### Fix freeze byte pins and remaining boundaries

Before product changes, consumer/refs hashes were respectively
`fcd05c52f7c550510ee82c110efe1559f07bc9495b20dbedd874b018ac6e0de5` /
`e80492be96ea0aacd5bb2038018c90bf8201d3e4a616d2574c456d5f9899cb2b`.
Before this round's test additions, consumer/refs test hashes were respectively
`bd0a496008ba6e671b562f433a5c27226784e9f77a8404fb061498e239c9bc2c` /
`0b8d9d7b52834b0fa6f51a7deffb8db5dc1912413bad213b1fd47199b7d16e83`.
The following four final hashes were measured before and after final scope 15,
and the tested bytes did not change:

```text
context_storage_v2/tennis_consumer.py
6ccda0e62cb3325150df6b8b7c0bb2582be2835974b0c5839a3471c608ad99ce
context_storage_v2/refs.py
a2c5f99d5b455a1a6e4150a45008020f111eeeffa2e52e7916db728da59be0a8
tests/test_context_storage_tennis_consumer.py
aa09fb9c249ff136ae1f40d31842e3ae7d19e6e1aeb93c768ba813cc0ccd4ff8
tests/test_context_storage_refs.py
e13831a8af9672dea0ff0044c05469f04b7ecff20f4ea99dbe8cabfa055f5a8b
```

Unedited coupled modules remain snapshots
`f5dc0903874bede9fbbe3196146ba0b4b000d6a962916afd1d24efdb625f14ba`, ref chunks
`49c41fac294bb6255e083cb07afad592a1460c84215dfa98842e233d8ef6d63d`, and source
adapter `f080d605dbbaf45baae197f9f948539d8ff832a2b294327cdc845d4d6df31753`.
Their test hashes are respectively
`77639cc754b0ef35285ad80c41a684fa63106e8f4d4dffb494ff8916f4a33d1b`,
`01ac74ca49a06745beaf988a4e1e33284d299feaae181eea6b9ae063636c063f`, and
`67662d8b7965620d18ef6b6a9e30fb006314b345b377805990da5f9c48379f34`.

The specific independently identified P1 is addressed by the retained real
regression and final coupled run. Scoped independent re-review is still needed;
this implementer's fix report is not that approval. All earlier native
AS/RSS/CPU/disk/custody, code/dependency/root-seal, complete Corpus/D2, global
growth, empirical, B/restore and production boundaries remain unchanged and
unproved here. No general hostile-Python or asynchronous-owner guarantee is
invented by the new private callback. After this append's final readback/hash,
the agent hands all five files back to Root and relinquishes the sole writer
role; no further edits, tests, cleanup or external actions are pending.
