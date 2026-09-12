# Task 54 — actual small Corpus / Source / Tennis consumer integration

## Status and scope

**DONE_WITH_CONCERNS for the authorized local Task54 acceptance.**  The real
small ATP and WTA paths pass from an independently authored legacy baseline,
through the actual three-receipt Corpus, fresh Source/D2/receipt ownership,
old-snapshot adaptation, History, real prediction/features and a separate new
consumer store.  No concrete product defect or missing product seam was found.

This is not native resource/custody closure, full growth, global C, B, restore,
deployment or release acceptance.  BASE was supplied by Root as
`726ba04212c2e3cb91a572d7e084cc419c2ebaf6`; approved Task51 product was supplied
as `4d538203d2b50c61b6dfba9e7681b7e0061e9f56`.  No Git/index/server/network,
dependency, cleanup or product-source operation was performed.

Only these files were written by this task:

- `tests/test_context_storage_corpus_consumer.py`
- `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-54-report.md`

The callable positive orchestration API for the guarded native follow-on is:

```python
run_small_corpus_consumer_acceptance(
    tmp_path, monkeypatch, tour, *, record_property=None
)
```

It accepts explicit `tmp_path`, an actual `pytest.MonkeyPatch`-compatible owner,
and `tour` equal to `ATP` or `WTA`.  It has no `pytest.main`, collection, fake
prediction or production-helper dependency.  The native follow-on must still
predeclare and charge this fixture phase, C phase, all retries, dependency/code
copies and parent costs under one guarded whole-job owner.

## Actual chain and lifetime

The baseline is created with real `configure`/`run_batch`, capture, artifact,
prediction, Original, snapshot and Shadow owners.  It contains both ATP and WTA
active states, two physical receipts, two Originals and two complete snapshots;
the non-selected tour therefore remains in every source inventory.  The sealed
baseline is copied byte-for-byte into an independent legacy oracle.

For each selected tour, two distinct ordinary normalized receptions are added
through actual `append_observation`.  A third distinct scheduled native match is
then received through `capture_tennis_worker`, predicted through the real live
worker and finished by the old producer.  The oracle inventory is captured only
after the capture context has persisted that third receipt and before
`LiveWorker.finish()` inserts the new Original/snapshot.  Thus the controlled
clocks are consistent and there are exactly three new receipts, not a hidden
fourth.  The new Corpus receives precisely the same three `(normalized_record,
observed_at)` pairs.  Complete `RawInventory` dataclasses and every typed table
row are compared against the independent oracle at that boundary.

After the Corpus writer commits/closes, a new profiled read-only
`TrackedConnection` holds the output transaction.  Actual
`VerifiedArtifactMapping`, validated stored creation timestamps,
`context_runtime._verify_artifact_types`, its returned
`semantics['protected_receipts']`, the actual `VerifiedReceiptMapping`
constructor and `validate_all()` establish Source/D2/receipt ownership.  The
observed small baseline has zero protected receipts and no semantic limitations;
the empty set was observed from the D2 owner, never supplied to the receipt
mapping.

Old snapshot coverage is authored into and committed in the separate fixed
`old-parts/snapshot-parts.sqlite` store.  A fresh read-only reopen validates the
complete source coverage and exact bytes of both baseline snapshots.  No new
consumer product is appended there.  History and real streaming Tennis features
use their own fixed stores.  Consumer Original/refs/snapshot parts are written
only to `new-consumers/consumers.sqlite`.

Before consumer commit, the same-call old/new comparison covers unrounded
prediction, complete canonical feature bytes, origin, selection reason, full
observation membership, canonical Original payload/hash, snapshot key, full
canonical bytes, raw SHA, legacy payload digest and consumer reference.  The
old oracle timestamp is checked against the controlled requested clock; the new
stored Original timestamp is not directly asserted by this integration test
(Task54-M1, retained for final validation).  The caller keeps the consumer
transaction open, then closes `prepared` (and its
feature owner), History and Source before `commit_build()`.  A real injected
late `PreparedTennisConsumer.close()` failure causes caller rollback; a cold
reopen sees no consumer tables while all prior private corpus/parts/history/
feature files remain.  Returned `PublishedTennisConsumer` data is never treated
as cleanup or commit authority.

## Brief-to-test map

| Binding requirement | Exact retained test evidence |
| --- | --- |
| Positive ATP/WTA, exact three receipts, complete typed pre-Original inventory, actual D2/receipt mapping, old parts, History/predict/features, exact bytes/refs/reopen | `test_actual_three_receipt_corpus_reaches_byte_identical_real_consumer[ATP/WTA]` |
| Source transaction/generation drift after Corpus | `test_source_transaction_drift_after_corpus_cannot_start_history` ends/restarts the actual held Source transaction; the already validated receipt mapping cannot start History and no history file appears. |
| Abort after completed private Corpus | `test_abort_after_completed_private_corpus_retains_it_without_final_generation` observes the completed main/ledger, aborts, retains them and verifies all downstream directories remain empty. |
| Late cleanup must precede commit | `test_real_late_prepared_cleanup_failure_rolls_back_consumer_before_commit` executes the complete real chain, makes genuine feature-owner close raise, and cold-checks the rolled-back output. |
| Altered full membership with the same count | Existing unchanged real owners: `test_terminal_exact_membership_rejects_real_sorted_ledger_corruption[same-count-member]`, `test_full_after_commit_scan_rejects_unauthorized_real_sql_mutation[same-count-member]`, `test_same_count_other_source_cannot_reuse_a_complete_coverage_descriptor`, and `test_complete_membership_rejects_actual_wrong_refset_even_with_valid_new_hashes[same-count-swapped]`. |
| Missing/extra native/full member | `test_prepare_rejects_unstored_or_different_native_and_history_scope[receipt-clock/native-participant]` rejects an unstored native identity; `test_complete_membership_rejects_actual_wrong_refset_even_with_valid_new_hashes[missing/additional]` exercises complete real C2 membership and rollback. |
| Failure after genuine prediction before complete Original/snapshot publication | `test_actual_sqlite_allocation_failure_does_not_return_partial_original_or_parts[full/toobig]` prepares through real prediction, then proves real output allocation failure returns no partial tables; `test_lifetime_or_late_iterator_failure_rolls_back_all_output_inside_savepoint[...]` additionally covers late source/history/feature/iterator loss. |
| Fixed plan counts journals/external input | `test_complete_plan_charges_future_main_journal_archive_and_directories` and `test_entire_active_input_includes_external_source_and_all_own_indices`. |

These unchanged lower-level cases were selected because they exercise the exact
owners used by the integrated route.  Their real descriptors, SQLite mutations,
Source lifetimes and prediction objects were not replaced by success validators.

## Fixed reservations and observed bytes

Legacy setup is a prior, separately enumerated allocation phase, not part of the
profiled single-writer C timing.  It is not a reset/new whole-job allowance: the
union remains charged.  Every slot below was declared before its phase writers.
All main/journal ceilings are page-aligned.

| Phase / slot | Reserved bytes | Observed final logical bytes (main / journal; same for ATP and WTA) |
| --- | ---: | ---: |
| Setup `context.db` + journal | 8,388,608 | 102,400 / absent |
| Setup `shadow.db` + journal | 8,388,608 | 57,344 / absent |
| Setup `legacy-oracle.sqlite` + journal | 8,388,608 | 131,072 / absent |
| Setup `oracle-shadow.sqlite` + journal | 8,388,608 | 49,152 / absent |
| Setup directory metadata | 1,048,576 | 4,096 charged by observation |
| C Corpus main + journal | 8,388,608 | 110,592 / absent |
| C two-bank receipt ledger | 1,048,576 | 524,553 |
| C old-parts main + journal | 8,388,608 | 90,112 / absent |
| C History main + journal | 8,388,608 | 45,056 / absent |
| C feature main + journal | 8,388,608 | 36,864 / absent |
| C new-consumer main + journal | 8,388,608 | 65,536 / absent |
| C directory metadata | 1,048,576 | 8,192 charged by observation |

Setup reservation is **34,603,008 bytes** and observed setup is **344,064
bytes**.  C reservation is **44,040,192 bytes**.  C observations after Corpus,
old parts, History, features and final consumer are respectively **643,337**,
**733,449**, **778,505**, **815,369** and **880,905 bytes** for both tours.
The retained union is therefore **78,643,200 reserved bytes** and **1,224,969
observed bytes**, not two interchangeable allowances.  The C active-input
ceiling is 4,194,304 corpus bytes plus the actual 102,400-byte external source;
the final observed active inputs are 110,592 + 102,400 = **212,992 bytes**.
Final sampled free space was 1,540,408,229,888 bytes for ATP and
1,540,406,992,896 bytes for WTA.  `WorkspaceBudget` remains local accounting,
not a physical/native quota or an interval certificate.

## Frozen fixture, output and candidate hashes

Both tours began from the unchanged 102,400-byte sealed source:
`594464c51f0e251a5cb64d4ed959c361a299090961271f5b722d5e757b2dbf4e`.

| Evidence | ATP | WTA |
| --- | --- | --- |
| Corpus SQLite SHA-256 | `30506a6be59405535cedf540b76f605948374da3d6b11958d9e6a880bc68b9eb` | `d9d4cbff75aa73de8258f08ff2ebbcde31f1621908ec49d34a40a6e3f9a1766d` |
| Corpus ledger SHA-256 | `66ff31bb57b637bae138b625ce39234ab5e84e1a712ce3b6ef2e6ef4b47d687f` | `2d5cb0d9ea0e854fd9bed5f6dd3421064ed680da5b830ee77675673ec8bf46e9` |
| Receipt inventory digest | `776ee6cca86d56d3e8b77645e39c9139122875470a53d491ef152632ecf6d594` | `c77d434ccd50209df40f5f5017d3159425860f76552bc86bd6c22f77ba2213fd` |
| Old-parts SQLite SHA-256 | `e83882c7a34a7d0f36c9740aedf12936cb3b1ac70b48445b9d29d6978dee8868` | `e797d63d2d2943a79eaac875ad76ab454afac9d1d00245ff859cb22700af1a6d` |
| Old coverage digest | `aeca3782f516334d40874f46578e8c204c8fcd1b12f91594c2da3db602b7379d` | `67bead52e57a071cbb43ebf3d5542c943ddc8be04558697abd0e76e0fe065d61` |
| History SQLite SHA-256 | `c77e92cc5b3fe5c8cf4737213cdf9b30c3d0b74091dd4f9906049189d52b49e0` | `2b39a5f4380b777f60e6bdef5bac2591b20779e8926c1be7f264de276924f2b9` |
| Feature SQLite SHA-256 | `bec511df7f2704763615cbb688429f4b980051d40cf0c220001fd28e417f62d0` | `bec511df7f2704763615cbb688429f4b980051d40cf0c220001fd28e417f62d0` |
| Feature canonical SHA-256 | `eea4e47de450ac39262f498d7b9b3154fd65eaa3c9f60b4e093d458339db107a` | `ec27fa9bd60db916d308882c409fa4896070419705e8f91472975ce8c4e0029c` |
| Consumer SQLite SHA-256 | `5961daa6f60c769386e70739bae72656433658475e9832f48251d2d25935731a` | `a3bf43fe76b9be9bf6d254349cc846b5768cf1dfcc28312924869a0bb80c7448` |
| Snapshot key | `f9c5f679db4f0759cc6a978e0069cb8c0bd1f6289144d79bb1950534b2e47141` | `393d8cac62b4885cb9d9d98c68a8074c804a86f655bfc2ed3ad4702bb305f624` |
| Snapshot raw SHA-256 | `001046bcea8ddbabd531331f18bd05f1191468f41b55a5f2f37865196262a00d` | `eebc2e59ffbedd5b46ec7c03fce469f03901b44e703bfec380b0c50992f96826` |
| Legacy payload digest | `4acbe7a1bfb54b496f2e5e0ec764c0e7a4b4b5f910d1d09a65dd8138dd419611` | `b9ccc655293fdb646f60ea1497f57b067682ddf22c7622bad640e6001f6760a4` |
| Original artifact hash | `a57c52c4df50c9f288e20cfb95e59d3901f2579d8a78112a479ee94937955901` | `efcf387376c61de14ed13c17415b2df6c483ed7c1fbc89180ea659c18dbfad5a` |

Exact final owned test bytes:

```text
tests/test_context_storage_corpus_consumer.py
5a59f75d0a3093238031159a813ce81b6c633c63105cab0338ed376a7bac7649
```

Freshly bound, unchanged product bytes:

```text
context_storage_v2/receipt_corpus.py
fdbebbed9e0b14380d7226660f5f42ec9508ec2b04c727a856bb36747ae660d6
context_storage_v2/workspace_budget.py
b848a43d4d76bb30c0510909870046195d08b86b15a6b2d6b2d8d37aad353580
context_storage_v2/history.py
d1d52b0c14dcd2614d81ba7371d2809d2d31e536c6d107f07a8ffa3520e4faf8
context_storage_v2/snapshot_source.py
f080d605dbbaf45baae197f9f948539d8ff832a2b294327cdc845d4d6df31753
context_storage_v2/tennis_consumer.py
6ccda0e62cb3325150df6b8b7c0bb2582be2835974b0c5839a3471c608ad99ce
context_storage_v2/refs.py
a2c5f99d5b455a1a6e4150a45008020f111eeeffa2e52e7916db728da59be0a8
```

## TDD/debug record and exact commands

Runtime: Python 3.12.14, SQLite 3.53.1, pytest 9.1.1, Windows 11 build 26200.
Every pytest execution used this prefix from the worktree root and a fresh,
retained basetemp/XML pair:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -o junit_family=xunit1
```

| XML | Exact suffix after common prefix | Result / XML time | SHA-256 |
| --- | --- | --- | --- |
| `task54-positive-red-01.xml` | `tests/test_context_storage_corpus_consumer.py --basetemp=.pytest_tmp/task54-positive-red-bt-01 --junitxml=.pytest_tmp/task54-positive-red-01.xml` | 2 failed, 0 errors/skips / 4.196s | `ab825a0224bd19beb504148bf6fb75647be925dd3e40c37070f0b8dfa9ef9bc2` |
| `task54-positive-green-02.xml` | `tests/test_context_storage_corpus_consumer.py --basetemp=.pytest_tmp/task54-positive-green-bt-02 --junitxml=.pytest_tmp/task54-positive-green-02.xml` | 2 failed, 0 errors/skips / 9.002s | `4f0f5b4bbf990441c0c274f2c2046417315f4fbda3b391b6a8f039f6bd0003f5` |
| `task54-positive-green-03.xml` | `tests/test_context_storage_corpus_consumer.py --basetemp=.pytest_tmp/task54-positive-green-bt-03 --junitxml=.pytest_tmp/task54-positive-green-03.xml` | 2 passed / 11.817s | `75ef16aba19131da9e8a566c043d6ed0b8846c73a29d5264eeaa4bba129657e0` |
| `task54-callable-green-04.xml` | `tests/test_context_storage_corpus_consumer.py --basetemp=.pytest_tmp/task54-callable-green-bt-04 --junitxml=.pytest_tmp/task54-callable-green-04.xml` | 2 passed / 11.607s | `3bfec93c51019118c1f422a4a2f62662990691c47aa945def5f609812f16cf1d` |
| `task54-boundaries-red-05.xml` | `tests/test_context_storage_corpus_consumer.py --basetemp=.pytest_tmp/task54-boundaries-red-bt-05 --junitxml=.pytest_tmp/task54-boundaries-red-05.xml` | 5 passed / 10.176s | `9d252183dc7924d371d38b29335d29d1e1f36caab85a78cc44ca7c062d594f84` |
| `task54-module-final-06.xml` | `tests/test_context_storage_corpus_consumer.py --basetemp=.pytest_tmp/task54-module-final-bt-06 --junitxml=.pytest_tmp/task54-module-final-06.xml` | 5 passed / 10.399s | `e98ae9a506f76eaf9fce2b75c06f18d9a463247e23c8b397aaab0adf12593289` |
| `task54-coupled-final-07.xml` | coupled suffix below, basetemp/XML `task54-coupled-final-bt-07` / `task54-coupled-final-07.xml` | 34 passed, 353 deselected / 28.139s | `cb1f699b74dfec1badde2e50a204e773e7a8f2683388aa5c5e5366c64193334a` |
| `task54-module-freeze-08.xml` | `tests/test_context_storage_corpus_consumer.py --basetemp=.pytest_tmp/task54-module-freeze-bt-08 --junitxml=.pytest_tmp/task54-module-freeze-08.xml` | **5 passed**, 0 failures/errors/skips / 18.198s | `40fbea9cb5d5dc62cf5d865d73d7c8437c12370138dc6f5d4e267902244efaea` |
| `task54-coupled-freeze-09.xml` | coupled suffix below, basetemp/XML `task54-coupled-freeze-bt-09` / `task54-coupled-freeze-09.xml` | **34 passed**, 353 deselected, 0 failures/errors/skips / 51.482s | `a862ee49768eb08c2818d8d0750b362e933d975602128ab6bd135917d8ac2907` |

The coupled suffix was exactly:

```text
tests/test_context_storage_corpus_consumer.py tests/test_context_storage_receipt_corpus.py tests/test_context_storage_snapshot_source.py tests/test_context_storage_history.py tests/test_context_storage_tennis_consumer.py tests/test_context_storage_workspace_budget.py -k 'actual_three_receipt_corpus or source_transaction_drift_after_corpus or abort_after_completed_private_corpus or real_late_prepared_cleanup or terminal_exact_membership_rejects or full_after_commit_scan_rejects or same_count_other_source or source_owner_changed_connection or complete_membership_rejects or prepare_rejects_unstored or lifetime_or_late_iterator_failure or actual_sqlite_allocation_failure or late_owned_feature_cleanup_error or complete_plan_charges or entire_active_input_includes'
```

The first RED was a test-helper defect: its generic read-only opener queried an
`artifacts` table even for the independent parts database.  The second RED was
an oracle-expectation defect: the test hard-coded `no-owning-approval`, while
both genuine old and new selectors returned `effect-unavailable`.  The helper
was made schema-neutral and the selection reason is now compared directly to
the actual old producer.  Neither RED identified a product defect.  The
historically named `boundaries-red-05` run was green on first execution because
the approved product already enforced those acceptance boundaries; it is not
misreported as a semantic RED.  No test was weakened to force green and no
failed artifact was removed.

## Remaining concerns and writer handback

- Full 590,553-receipt / 199-Original / 199-snapshot / 114-key growth profiles,
  all retries/failed artifacts, native AS/RSS/CPU/FSIZE/output/custody/reaping,
  dependency/code/root closure and cross-worker reopening remain unproved.
- The actual old A1/D2 validators and individual canonical rows may still
  materialize complete small values; this fixture cannot establish native heap
  behavior at production size.
- The local budget is accounting only.  Native follow-on must charge the union
  above plus dependencies, copied code, supervisor/parent and every retained
  retry under one whole-job owner; no allowance resets between setup and C.
- No positive empirical approval/effect was manufactured.  The observed real
  selection reason is `effect-unavailable`, with unresolved native-state
  identity preserved exactly.
- Task54-M1: canonical Original payload/hash parity is covered, but the new
  stored Original `created_at` column is not directly compared here.  Its exact
  timestamp remains a final-validation assertion gap; no timestamp defect was
  demonstrated by the independent review.
- No global manifest, B authenticity/reuse, restore, device/UI, VPS/deployment
  or release claim is made.

The test and report are frozen and handed back to Root for integration/indexing
and independent review.  This agent relinquishes sole-writer authority.  No
product edit, extra test run, artifact cleanup or external action remains
pending from this writer.
