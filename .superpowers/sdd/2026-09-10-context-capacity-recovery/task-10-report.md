# Task10 implementation report

Date: 2026-09-11. Base HEAD: `40d40147c9468bbe874f3b1cc90873c20911f7c6`.
Only the two checking modules, the new check-dispatch test module and this
report are authored. Existing tests and every other tracked path are unchanged.
The complete Task10 brief, fresh30 analysis, Task9 brief/report and applicable
global/capacity constraints were read. No applicable on-disk AGENTS.md was
found at the checked ancestors or owned directories. No subagents, fullsuite,
push, SSH, deployment, data change or missing skill-tool claim by this worker.

## Outcome and authority boundary

Implemented recursive same-order loops with a fixed exact five-leaf-type tuple,
retaining literal `canonical_bytes(row) == raw`. Exact internal schema readers
use one short-lived tracked cursor for the same main and temp PRAGMAs. No
predicate, statement, schema cookie, proof boundary or feature call is removed.

The new 117-test module passes. Broad final-product focused regression passes
1223 tests with 12 platform skips, as recorded below. This is local checking evidence, not current-input resource
acceptance or release approval. Latest actual 30-snapshot evidence remains
FAILED at 299.978 CPU / 300.233 wall, child -9, until root obtains a new complete
exact-source native result. Prior fullsuite 7292 green does not override it.
Current-first native, meaningful distinct-query growth, historical profiles,
DAC/races, final whole-repository tests/review, fresh backup/actual restore/HMAC
and current-data recheck remain controller gates before publication/deployment.

## RED/GREEN commands and observations

Every pytest invocation used this exact executable/flag prefix:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe
  -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning
```

Environment: `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`, and
`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`,
`NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `BLIS_NUM_THREADS` all `1`.
Each command appends the modules/selection below and
`--basetemp=.pytest_tmp/<run-name>`. No elapsed-time test threshold is used.

| Run-name | Selection and exact source stage | Result |
| --- | --- | --- |
| task10-red-1 | New initial module, unchanged base product | 13 failed, 35 passed, 1.50s |
| task10-green-1 | New initial module + full existing receipt_witness; initial implementation | 166 passed, 21.45s |
| task10-new-2 | Expanded new module; initial implementation | 104 passed, 7.72s |
| task10-exact-focus-1 | 23 modules listed below; intermediate product before cleanup correction, 104 new tests collected | 1214 passed, 12 skipped, 673.42s; never final-product evidence |
| task10-cleanup-red-1 | New module `-k cleanup_after_connection_close --tb=short`; intermediate product | 6 failed, 104 deselected, 1.02s |
| task10-new-3 | New module including corrected cleanup/error lifetime matrix; final product | 113 passed, 8.50s |
| task10-exact-focus-2 | Same 23 modules; final product and 113-case new-module collection | 1223 passed, 12 skipped, 636.55s |
| task10-final-new-1 | Complete final new module including four late test-only actual-cookie/SQLite-interrupt cases; unchanged final product | 117 passed, 9.09s |

The initial RED was an honest allocation/performance contract, not a fabricated
semantic bug: the real two-row persisted fixture triggered 96 recursive
generator call/resume events, whereas the new guard requires zero. Both exact
schema boundaries created two actual tracked cursors, versus one required.
The ten explicit cursor-cleanup probes also fail on the old unclosed transient
cursor path. All 35 independent exact-type/recursive/canonical tests were
already green before product edits.

The four final actual-cookie/SQLite-interrupt tests were added after the final
broad cohort collected 113 new cases. The complete 117-case module was run
separately on the identical final product bytes. No skipped native/platform
case is relabeled a pass; full native acceptance remains with the controller.

During self-review a separate defect in the first optimization was reproduced:
after actual main PRAGMA, closing the connection and raising KeyboardInterrupt,
MemoryError or OperationalError caused `cursor.close()` to replace the primary
error. All six new tests failed. The final implementation preserves that exact
primary exception and chains a cleanup error explicitly as its cause. Ordinary
cleanup errors still propagate. Both errors remain available, not swallowed.

Final focused module list (not the whole repository):

```text
tests/test_context_runtime_check_dispatch.py
tests/test_context_runtime_coordinated_tennis.py
tests/test_context_runtime_original_projection.py
tests/test_context_runtime_receipt_witness.py
tests/test_context_runtime_shared_history.py
tests/test_context_runtime_capacity.py
tests/test_context_runtime_tennis_live.py
tests/test_context_runtime_backup.py
tests/test_context_runtime_semantics.py
tests/test_context_runtime_transport.py
tests/test_tennis_status_v3.py
tests/test_tennis_check_equivalence.py
tests/test_tennis_native_status_codes.py
tests/test_tennis_context_features.py
tests/test_tennis_v3_model_transport.py
tests/test_tennis_live_origin.py
tests/test_tennis_live_integrity.py
tests/test_tennis_live_publication_clock.py
tests/test_tennis_live_worker.py
tests/test_context_transport.py
tests/test_context_transport_bytes.py
tests/test_context_transport_hockey.py
tests/test_context_transport_esports.py
```

## Equivalence, dispatch and lifetime argument

- Dicts and lists are still accepted only at exact builtin type. Dict keys are
  checked before their values. Both loops visit in existing insertion/list
  order and return on the first False. Leaves remain precisely str, int, float,
  bool and NoneType; subclasses, tuples, bytes and arbitrary objects miss.
  Cyclic/deep recursion still raises RecursionError for the witness to defer
  to the unchanged cold owner. No retained traversal stack/pool is introduced.
- Nonfinite floats are still guard-eligible, not schema-accepted; actual
  canonical encoding/owning validation determines their rejection. Signed zero,
  bool/int/float encodings and key aliases are not compared by Python numeric
  or structural equality. Every actual canonical-byte comparison is retained.
- The cursor fast path requires exact inventory/cache/connection types,
  original captured class execute/cursor methods, no per-instance execute or
  cursor override, and default `row_factory=None`. Captured methods come from
  the internal class at module load, never from an arbitrary instance callback.
  Subclass/class-monkeypatch/instance/factory routes retain connection.execute.
  Existing 24 connection-seam race tests were deliberately left untouched;
  root declined the proposed seam port and required compatibility guards.
- Main executes and fetches first; temp executes and fetches second. Inventory
  generation and total_changes are evaluated before allocating the cursor, as
  before. The transaction owner itself is byte-identical. Both actual cookies,
  tracked statements and current transaction/write values remain authoritative.
  Dispatch/factory guards are checked again after the main fetch so reentrant
  changes receive the original second connection dispatch. Each nested exact
  boundary owns its own local cursor; no shared/persistent cursor exists.
- Success closes the local cursor before returning. Failure attempts cleanup
  before raising. If connection closure makes cleanup itself fail, the primary
  exception is re-raised with the cleanup exception as explicit cause. There is
  no retained exception cache; weakref tests observe cursor collection after
  exception references unwind. Normal cleanup SQLite errors revoke actual
  inventory/cache proof through the unchanged failure owners.
- New tests execute actual SQLite main/temp DDL (including a temp object named
  pragma_schema_version), verify unequal cookies (2,1), observe both literal
  statements in order, and trigger real SQLite interruption on the second
  statement via a progress handler. Additional delegated cursor races cover
  writes, main DDL, temp inventory shadowing, commit/rollback+restart and close
  before/after witness rows. Proof loss clears cache state and remains revoked.
- Existing witness/covering/coordinated/projection tests retain before/after,
  final/empty, exception deactivation, replacement/eviction, identical-byte
  replacement, complete histories, all receipt refs, actual cold source failure,
  original predictors, full snapshot features and transports. No existing test
  expectation was relaxed, and no proof success was supplied by a mock.

## Advisory measurements, not acceptance

The initial implementation, 100000 real in-memory checks, three wall-clock
repeats: inventory old 0.402832/0.402816/0.402847s versus guarded local cursor
0.378632/0.379910/0.380084s; cache old 0.385660/0.431260/0.384710s versus
0.369332/0.360350/0.362659s. All results and actual statements matched.

A final-product development-only comparison loaded the two exact base modules
using `git show 40d40147...` in an ephemeral interpreter (no committed Git
oracle/helper). It alternated 100000-call old/new CPU measurements three times,
while the focused tests were also running. Results are noisy and not a promised
native gain:

| Actual operation | Old/new CPU seconds, repeats 1 / 2 / 3 |
| --- | --- |
| Inventory stamp | 0.421875/0.375000; 0.421875/0.406250; 0.406250/0.375000 |
| Cache schema reader | 0.515625/0.515625; 0.406250/0.468750; 0.687500/0.640625 |
| Real status row 0 guard + canonical equality | 1.640625/1.140625; 1.421875/1.593750; 2.265625/1.609375 |
| Real status row 1 guard + canonical equality | 1.968750/1.562500; 2.015625/1.953125; 2.390625/1.859375 |

Rows were the two 1369-byte actual persisted status receipts in the final new
test fixture, opened read-only and passed through full physical and cold owner
validation. These timings include slower/tied new repeats without hiding them.
Only deterministic allocation/dispatch counts belong to the test contract.

## Exact bytes and frozen files

Final authored working-byte SHA256:

```text
context_runtime_history_cache.py b1bdc92fcdf6683a7b2b27793515743f137caa59a73e812a540c8a96235c1552
context_runtime_inventory.py 55d54c7db12e7ceae92d8833857584ee63f4a0aa9abec0b7db68a3c681d8d785
tests/test_context_runtime_check_dispatch.py bc0b8c2bcd3db78b88859f3be7a7b4e45a210ff734ee5cace33940af86773929
```

Read-only exact-base diff confirms all protected owner/source/math/helper paths
unchanged. Selected current frozen working-byte SHA256 values:

```text
context_observations.py 9fb1ec38ac12dd3b142ab1b23e9c49cf605e77cd931e38c503f69026d0cec226
context_runtime_transaction.py ecec258d9b67964da29b9da91859c5d80ed24100765b04e14db5269b8d4e8e5b
context_runtime_input.py 798fc7146410b214752e98a1fa86af27a33f837b3ce53e86146fcf79e8a3f228
context_runtime_original_projection.py ddc5632cc3e8f8ad9379799d0953f76e9d2d6cf733b6a0b5f9566c5c7302036b
context_models/contracts.py 7b3c2a909fee790879d446ef2b95bc944d24951af4261c3296c36e6338518fa8
context_models/tennis_live.py 5498d79266bf5b5a9e9ddc97610a2318f6abe292c164e8a0bf57b0adfcf09ed0
context_models/tennis_v3.py ec6461b87656ecc5731992cc26f0ae69d20e878982706ebe3f1fd0599c43305c
context_models/tennis.py 313ffafacc367e7370312f478327d6453860ac0bf17bbcaf8102acdda49e4bab
context_sources/tennis.py 80f1621f60e0b3daecef8abb5e44efeebd2c2bc6bc0df8161032daab78ceb739
context_runtime_semantics.py 0e93f4d40ac22f0d80fde6ae3dec7df57a24806951f332a72872fcd7040cf3cd
scripts/verify_context_runtime.py 67a1a23019d44c598c344925d342fff0e24342595b9cb2185b3e77b75efd2078
scripts/stage_runtime_databases.py 1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026
context_transport.py a47d980a4e528ef12917db39e47d025c4670070737901f6e8c9688dfe84a1a9e
model_artifacts.py 6cd072f4cf77a9405091fbdc166580cd403ba15e232c915414be493de9fd6d16
tennis/predict.py bd1c2c8f7666e3de5f32d754eac09967edde566c1d7b48c298635f2b3d989ecc
tennis/model_state.py 3512c7aa047d11f809402fe434fcaae6ebf0542e961174348d2e6972198d7134
tennis/elo.py 689c50cdd9cbb5489ff66fbcc10814683c18ebcc79c97b648ceea4db738083c6
tennis/serve_model.py dd76339957cc806e5bea14584c47c9467b242966bd531a6c03adf3b067e803aa
tennis/simulator.py 6f326fc84de6b705b762b9d9efaa2932daf0f4546c419d56f30e8c3f4644e29f
tennis/data_loader.py 521bb2525a8a874b64f4afe55c49e18c075bdc04348e38b1632c95af6aec4620
context_runtime.py 2425264c6f32cd6bb9b304fa1d1e3389b948f7476eb153ac09fd03b6458d9d21
context_runtime_tennis.py 1bf3ebaf37b13cd0173ac795a2ddc5ea01918dafe6730881625322c6bf205bed
context_sources/tennis_status.py 8c2a8093aa2113564c34088227e5fb0a8c70faf9d52428e74c4995c505a57581
```

No model/source hash whitelist, normalization, structural comparer, rolling
query batches, new helper, transaction-module edit or retained decoded pool.
Limits remain input 1GiB / history 256MiB / aggregate cache 64MiB / 30 queries /
32 slots; native UID997, AS2GiB, CPU300, wall600, output1MiB and measured
CPU/wall<300, RSS<1GiB. Above-30 distinct-query complete-prefix fallback remains
an explicit growth concern. This micro-optimization promises no arbitrary growth
capacity, fixes no daily Tennis HTTPError/timeout, and completes no Cricket,
A0/P4b3 or empirical five-sport work.

## Commit and handoff

Stage only the two product modules, new test module and this named ignored
report using `git -c core.autocrlf=false`; force-add only this report. Check
staged paths/diff, commit locally and return empty index. Commit SHA and final
index result are handed to root separately. No push or release by implementer.

Both focused cohort processes completed and were reaped. Final frozen-product
diff check passed; every tracked path outside the two authorized product
modules is unchanged from the base. Before staging, index was empty. No open
test failure remains; native/platform skips and all release gates remain open.

## Task10 P2 correction after independent review

Date: 2026-09-11. Correction base is
`4a27fb98f2379866a90abf3031082ab9a0fd4bf4`. The earlier final-product hashes and
1223-test cohort above describe that original Task10 commit, not this corrected
candidate. Root read and accepted the real P2 in the complete independent
`task-10-review.md` (SHA256
`987e9633286070970aaee160cb6459f8aaa93649829dadcefb04ec2d07cef75c`).
The reviewer report is not edited by this implementer.

A real SQLite trace callback can change the connection's `__class__` to a
layout-compatible TrackedConnection subclass during the actual main PRAGMA.
The prior second-cookie guard checked methods, instance overrides and factory,
but not the current connection type. It could bypass the new subclass execute
override, including an OperationalError veto. The only production correction
adds `type(connection) is TrackedConnection` to that second guard in each of
the two already authorized modules. Every other production line is unchanged.
Changed types now take original connection.execute dispatch for temp. Ordinary
exact connections still use one local tracked cursor, with existing cleanup.

Four new tests use the actual SQLite trace callback to perform the class
transition, for inventory/cache and delegating/veto-producing execute overrides.
There is no product monkeypatch or fabricated query result. A delegating Python
profile observes actual constructed cursors; assertions retain actual SQL order,
override dispatch, veto propagation and closure of the initial local cursor.
All previous 117 cases and all preexisting test modules remain unmodified.

Same quality executable, Python flags and fixed single-thread environment as
above. Exact correction run arguments appended to that prefix:

```text
tests/test_context_runtime_check_dispatch.py
  -k trace_callback_connection_class_transition
  --basetemp=.pytest_tmp/task10-p2-red-1 --tb=short

tests/test_context_runtime_check_dispatch.py
  tests/test_context_runtime_receipt_witness.py
  --basetemp=.pytest_tmp/task10-p2-green-1

tests/test_context_runtime_capacity.py
  -k "inventory or schema or failed_pass_never_reseals or failure_revokes_existing_warm_cache or rejects_mutation_and_started_iterators"
  --basetemp=.pytest_tmp/task10-p2-inventory-green-1
```

| Run | Result |
| --- | --- |
| RED on unmodified 4a27fb9 product | 4 failed, 117 deselected, 0.99s: both delegating cases omitted the override call; both veto cases failed to raise |
| Corrected full dispatch + witness modules | 239 passed, 28.76s: all 121 dispatch cases plus 118 unchanged witness cases |
| Corrected narrow inventory/schema/lifecycle/cleanup controls | 56 passed, 87 deselected, 8.43s |

Both GREEN processes completed and were reaped. No new skipped or failed case.
Read-only development comparison additionally executed the review reproducer
against the original immutable `40d40147...` modules (loaded via git show into
ephemeral namespaces) and the corrected current source. Both boundaries and
both subclass behaviors match exactly: delegating returns inventory `(1,0,0,0)`
or cache `(0,0)` with exactly one temp override call; veto raises the identical
OperationalError message with exactly that same call. No development oracle
or helper was saved into product/tests.

Corrected working-byte SHA256 values:

```text
context_runtime_history_cache.py 2f13f3064222a5ee9e7fa5a432ff47b36e611322ccede3e31217c2400e8178cc
context_runtime_inventory.py 2425653f02b1ff4b11fd6ec39f13bb9a3ca5061b3185af65cc41c44a816e36de
tests/test_context_runtime_check_dispatch.py 56f4f697b6a4e89b692afc9364f79539f2bc17ce73618c9d74bf690f5bae4848
context_runtime_transaction.py ecec258d9b67964da29b9da91859c5d80ed24100765b04e14db5269b8d4e8e5b
scripts/stage_runtime_databases.py 1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026
```

Frozen owner/model/source/helper diffs and whitespace checks remain clean.
No additional full 23-module cohort was run: root explicitly requires fresh
corrected native current-input acceptance first, then the final fullsuite.
The prior 1223-test evidence stays attached to 4a27fb9. No new performance or
resource-capacity claim accompanies this two-predicate correction. All limits,
source/feature/predictor/proof obligations and release gates remain unchanged.
Only the original exact four paths are staged/committed for this correction;
root progress/handoff/native/QA WIP remains untouched. No push, SSH, fullsuite,
deployment, subagents or additional scope by the implementer.
