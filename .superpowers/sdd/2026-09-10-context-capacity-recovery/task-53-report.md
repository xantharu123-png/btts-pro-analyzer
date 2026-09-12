# Task 53 — old large-row admission through bound History and Tennis

Implementation report, 2026-09-12. Task53 only; Task51 remains paused.

Final local result: **424 passed in 201.11s**, 0 failures/errors/skips and no
warnings, with final product/test hashes rechecked unchanged after execution.
Distribution: 21 large-row, 104 History, 117 Tennis, 93 SQLite-profile,
83 source-adapter and 6 integration tests.
No unresolved Task53 byte-equivalence or lifetime failure remains in this
scoped evidence. Native/global resource gates and independent review remain
open; this is not complete project or release approval.

## Scope and implementation

Product baseline supplied by Root: `a52b4b7ed46bb6e8c67d0b90c516163a7c2566fe`.
Root subsequently reported its independent docs-only `0a9ba29` commit. This
implementer ran no Git, stage, commit, push, server, dependency-install or
cleanup operations. No agents or reviewers were spawned. Existing WIP and
failed evidence remain in place.

The binding brief and Task52 real-owner audit were read before implementation.
TDD drove the real default-block RED, the chosen-workload RED, and two further
small lifecycle/framing REDs. Verification-before-completion requires the
recorded fresh results below; no inherited green test count is substituted.

Only these product/test files are changed:

- `context_storage_v2/history.py`
- `context_storage_v2/tennis.py`
- `tests/test_context_storage_history.py`
- `tests/test_context_storage_large_rows.py`

History's private format is now `context-complete-tennis-history-v3`.
Each row explicitly contains receipt digest, observed time, event key, content
digest, mode, full canonical size, full canonical SHA, and nullable payload.
`inline` requires a canonical payload within the processing-block budget.
`source` requires no payload, a size above that block, and an unprotected real
selected receipt. The full physical traversal, source-owner decode, `seen`,
opaque-final handling, source counts, selection, tour and cutoff rules precede
this representation decision exactly as before. No row cap was introduced.

One resolver serves build-end verification and every row-consuming History
path (repeat iteration, prefix, event/latest rows, chosen-receipt lookup).
Large resolution uses base `sqlite3.Connection.execute`, the original qualified
physical projection with the exact receipt key, actual
`VerifiedReceiptMapping._decode_row`, and actual source selection on the same
held Source. It checks complete reconstructed canonical length/SHA, receipt,
content, observed time, event key, tour and cutoff; it does not merely trust a
stored row hash. Source checks surround decoding and resolution; view checks
surround resolution, yields and resumption. No callback loader, reopen,
consumer-mutable decoded cache or caller proof flag is used.

Prefixes now retain their immediate parent handle, including when that parent
is itself nonowning. Closing or poisoning that parent invalidates the nested
child without incorrectly closing the otherwise intact owning root.

Selected-history digests still hash exactly the sequence
`uint64_be(len(canonical_row)) || canonical_row`. Build-end and prefix passes
charge full canonical bytes, not locator lengths. Both canonical bytes and
the framing prefix are fed through updates no larger than the configured
block. Old decoding/canonicalization still allocates actual complete objects;
chunked hashing does not undo those allocations. Large SQL logical index keys
are not claimed to be processing blocks and receive no new SQL value cap.

Tennis's private staging version is now `context-tennis-features-stream-v3`.
Its complete cold source validation still runs before participant projection.
The duplicate selected-row/block rejection is gone. Following Root's measured
pre-review ruling appended to the brief, the final representation is mixed:
bounded small chosen rows remain canonical inline BLOBs; actual over-block
chosen rows store a 64-character owning History reference with no payload.
Both use explicit mode and receipt identity. Sequence, side and association
bytes retain their previous ordering and meaning. Large rows resolve through
the same owning History; small rows use their bounded, already cold-validated
canonical staging bytes, with receipt/tour/cutoff and pre/post/yield lifetime
checks. No full cold validation or lifetime check was removed to gain time.
No feature, source, selection, math or historical code-hash version changed.

Removing the early row cap exposed a genuine downstream ref-budget failure
which left a suspended `_union_refs` cursor alive until after writer close.
A focused real RED demonstrated the actual unraisable SQLite error; explicit
closing of both generator layers now occurs before writer teardown, including
when a failed `put_refset` retains its iterator through an exception traceback.

Fixed writer plans/reservations, profile checks, free-space checks, one build
commit, RO publication, dependency identities, retained unpublished failures
and fail-closed exceptions remain in force.

## Differential and adversarial evidence

The default regression recreates Task52 through the real normalizer and old
append API: native scheduled name is exactly **16777217 bytes**, selected row
is exactly **16778570 bytes**, and the whole real old source remains below
64 MiB. The old actual cold replay and old `tennis_features_v3` run before the
new builder. Full canonical bytes, not approximate metrics or hashes alone,
are compared through repeat, prefix, event, latest and Tennis consumption.
Source file SHA, held transaction/generation and source `SQLITE_LIMIT_LENGTH`
remain unchanged. Consumer mutation cannot alter the next reconstructed row.

A separate real `normalize_tennis_workload` fixture uses a 3000-digit native
event ID under a tightened 2048-byte processing block. Its real source/event
index value exceeds the block; its old usable workload produces exactly 120
observed minutes for side A. Mixed inline/reference History, full ordering
and tie selection, chosen receipt staging and complete old feature bytes are
compared. This exercises the chosen-workload seam that a scheduled-status-only
fixture cannot reach.

Additional focused checks cover all indexed locator identity fields and mode,
ambiguous source payload, absent receipt, source/view close or generation drift
between yields and before/after resolution, nested-parent close, exact full
canonical tour-budget boundary, retained rollback before publication on a
build-end identity mismatch, and bounded hash updates including framing.
The incorrect historical `block` per-row admission expectation was replaced
with actual source-mode behavior at a one-byte processing block. Tour, input,
workspace and free-space failures remain separately tested.

## Exact commands and observed results

All commands ran in
`C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.
Every test invocation used the following environment and command prefix:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider
```

The exact arguments appended to that prefix, in execution order, were:

```text
tests/test_context_storage_large_rows.py --basetemp=.pytest_tmp/task53-red-bt-01 --junitxml=.pytest_tmp/task53-red-01.xml
tests/test_context_storage_large_rows.py --basetemp=.pytest_tmp/task53-focused-bt-02 --junitxml=.pytest_tmp/task53-focused-02.xml
tests/test_context_storage_large_rows.py -k 'not real_default and not chosen_large' --basetemp=.pytest_tmp/task53-lifetime-red-bt-03 --junitxml=.pytest_tmp/task53-lifetime-red-03.xml
tests/test_context_storage_large_rows.py tests/test_context_storage_history.py::test_tiny_processing_blocks_use_source_rows_without_new_payload_blobs --basetemp=.pytest_tmp/task53-focused-bt-04 --junitxml=.pytest_tmp/task53-focused-04.xml
tests/test_context_storage_large_rows.py -k 'framing or during_resolver or build_end' --basetemp=.pytest_tmp/task53-framing-red-bt-05 --junitxml=.pytest_tmp/task53-framing-red-05.xml
tests/test_context_storage_large_rows.py -k 'framing or during_resolver or build_end' --basetemp=.pytest_tmp/task53-focused-bt-06 --junitxml=.pytest_tmp/task53-focused-06.xml
tests/test_context_storage_large_rows.py tests/test_context_storage_history.py tests/test_context_storage_tennis.py tests/test_context_storage_sqlite_profile.py tests/test_context_storage_snapshot_source.py tests/test_context_storage_integration.py --basetemp=.pytest_tmp/task53-freeze-bt-07 --junitxml=.pytest_tmp/task53-freeze-07.xml
-o junit_family=xunit1 tests/test_context_storage_large_rows.py::test_reference_budget_failure_closes_live_ref_cursor_before_writer --basetemp=.pytest_tmp/task53-ref-close-red-bt-08 --junitxml=.pytest_tmp/task53-ref-close-red-08.xml
-o junit_family=xunit1 tests/test_context_storage_large_rows.py::test_reference_budget_failure_closes_live_ref_cursor_before_writer tests/test_context_storage_tennis.py::test_component_caps_fail_without_returning_partial_feature_result --basetemp=.pytest_tmp/task53-ref-close-green-bt-09 --junitxml=.pytest_tmp/task53-ref-close-green-09.xml
-o junit_family=xunit1 tests/test_context_storage_large_rows.py::test_chosen_large_workload_and_large_index_keep_old_features --basetemp=.pytest_tmp/task53-mixed-red-bt-10 --junitxml=.pytest_tmp/task53-mixed-red-10.xml
-o junit_family=xunit1 'tests/test_context_storage_tennis.py::test_full_legacy_vector_and_streamed_canonical_digest_are_exact[paired]' tests/test_context_storage_tennis.py::test_floating_sums_follow_original_python_sum_in_complete_event_order tests/test_context_storage_large_rows.py tests/test_context_storage_tennis.py::test_real_sqlite_full_keeps_uncommitted_tennis_file_and_original_inputs --basetemp=.pytest_tmp/task53-mixed-focused-bt-11 --junitxml=.pytest_tmp/task53-mixed-focused-11.xml
-o junit_family=xunit1 tests/test_context_storage_large_rows.py tests/test_context_storage_history.py tests/test_context_storage_tennis.py tests/test_context_storage_sqlite_profile.py tests/test_context_storage_snapshot_source.py tests/test_context_storage_integration.py --basetemp=.pytest_tmp/task53-final-bt-12 --junitxml=.pytest_tmp/task53-final-12.xml
```

| Run | Actual result |
| --- | --- |
| RED 01 | 2 failed in 3.81s, both at the real previous `history.py:585` block rejection. |
| Focused 02 | 2 passed in 16.67s. |
| Lifetime RED 03 | 1 failed, 13 passed, 2 deselected in 2.16s; nested immediate-parent close did not raise. One unraisable-generator warning during failed-test teardown was retained. The test now explicitly closes its iterator in finally. |
| Focused 04 | 17 passed in 18.34s, no warnings. |
| Framing RED 05 | 1 failed, 3 passed, 16 deselected in 1.43s; actual maximum hash update was 8 with block=4. |
| Focused 06 | 4 passed, 16 deselected in 1.29s, no warnings. |
| First freeze 07 | 1 failed, 422 passed, 2 warnings in 475.32s. The all-reference format legitimately fit 24 matches in exactly 65536 bytes, contrary to the prior FULL assertion. Real 4096/32768 FULL cases passed. Warnings: actual `_union_refs` teardown error and unchanged source-adapter `record_property`/xunit2 mismatch. Retained, not reported as GREEN. |
| Ref-close RED 08 | 1 failed in 1.55s; actual suspended generator emitted SQLite `Cannot operate on a closed database`. |
| Ref-close GREEN 09 | 6 passed in 1.70s, no warnings; actual ref-budget failure plus all component caps. |
| Mixed-format RED 10 | 1 failed in 1.70s; previous all-reference schema lacked the required explicit mixed mode/nullable row columns. Old-byte differential still passed before the staging assertion. |
| Mixed focused 11 | 26 passed in 43.97s, no warnings; paired, summation, all 21 new tests, actual FULL at 4096/32768/65536. Final mixed allocation therefore preserves the unchanged 65536 FULL assertion; no Tennis test expectation was changed to force either result. |
| Final combined 12 | 424 passed in 201.11s; JUnit 201.086s, 0 failures/errors/skips, no warnings. Same final code/test hashes before and after this run. |

Every basetemp/XML was fresh and unused, and all remained retained. The final
regression intentionally excludes `test_context_storage_tennis_consumer.py`:
Root identified it as unfinished Task51 with an absent module. It is not a
Task53 regression result. No whole product suite was run.

## Byte identities

SHA256 values measured after the final product freeze (before report edits):

| Changed file | SHA256 |
| --- | --- |
| `context_storage_v2/history.py` | `d1d52b0c14dcd2614d81ba7371d2809d2d31e536c6d107f07a8ffa3520e4faf8` |
| `context_storage_v2/tennis.py` | `dcd337f36b58bfb316864c0e5e6c611d9f42ce3d968037bce1d5956120cf6e53` |
| `tests/test_context_storage_history.py` | `b14c38fa8400f867a34ea5efdfddc299192cd22a1ef4f5f9724d6f1ad641483d` |
| `tests/test_context_storage_large_rows.py` | `07a19b6407edee02276ef3a153248b08e4906558edf1488646f0f7ac39fcec6d` |

| Unchanged binding or original owner | SHA256 |
| --- | --- |
| Approved C spec | `08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba` |
| `context_sources/tennis_status.py` | `8c2a8093aa2113564c34088227e5fb0a8c70faf9d52428e74c4995c505a57581` |
| `context_sources/tennis.py` | `80f1621f60e0b3daecef8abb5e44efeebd2c2bc6bc0df8161032daab78ceb739` |
| `context_observations.py` | `9fb1ec38ac12dd3b142ab1b23e9c49cf605e77cd931e38c503f69026d0cec226` |
| `context_runtime_inventory.py` | `2425653f02b1ff4b11fd6ec39f13bb9a3ca5061b3185af65cc41c44a816e36de` |
| `context_runtime_tennis.py` | `1bf3ebaf37b13cd0173ac795a2ddc5ea01918dafe6730881625322c6bf205bed` |
| `context_models/contracts.py` | `7b3c2a909fee790879d446ef2b95bc944d24951af4261c3296c36e6338518fa8` |
| `context_models/tennis.py` | `313ffafacc367e7370312f478327d6453860ac0bf17bbcaf8102acdda49e4bab` |
| `context_models/tennis_v3.py` | `ec6461b87656ecc5731992cc26f0ae69d20e878982706ebe3f1fd0599c43305c` |
| `model_artifacts.py` | `6cd072f4cf77a9405091fbdc166580cd403ba15e232c915414be493de9fd6d16` |

| Retained test artifact | SHA256 |
| --- | --- |
| `.pytest_tmp/task53-red-01.xml` | `7a0a7abcbcab83d351530c2eacb530904b1e3c5c4a2a2093c8802c696187ebe4` |
| `.pytest_tmp/task53-focused-02.xml` | `81d9728c6695f78c50d2d61c7d368360ffb37be067156ff0fd0b8a43a4124792` |
| `.pytest_tmp/task53-lifetime-red-03.xml` | `3a04f1ecaabffe886180d0ca49817536fc6c3e4af0c8b7761878e45a7a25648d` |
| `.pytest_tmp/task53-focused-04.xml` | `a9fabf6f93320e70924ef963fb38f0b7e3826fcdd25541933be103448c91ae20` |
| `.pytest_tmp/task53-framing-red-05.xml` | `f625c2157b158133ceab3ce8efdbdcea51f61d2b5e76991aba72666aeaefe963` |
| `.pytest_tmp/task53-focused-06.xml` | `5e059ba656f6430d6ae5d263ed64be49516aca4405e35bd5aa266a9d3da2503d` |
| `.pytest_tmp/task53-freeze-07.xml` | `129b8c99ff0f827845e21f0bf5cfd27d7c9a625566db904f4da384f9adcea45e` |
| `.pytest_tmp/task53-ref-close-red-08.xml` | `01096b0ee0205c7e6cf69d3570cd10e469d39b1f1db47497c65936c5f0070a28` |
| `.pytest_tmp/task53-ref-close-green-09.xml` | `09aed2acf5bcaa654f654f097ed6d52615bb23971c3291c67c2b3852f92dcd3f` |
| `.pytest_tmp/task53-mixed-red-10.xml` | `03ff7a31fe13d059f5b380146766d35b18cb0a298a5909399fb2a75349e25225` |
| `.pytest_tmp/task53-mixed-focused-11.xml` | `22e480ef043bed0b2a881f135db2354ddfbf8415e0cc5c308b4e3e67cd0c9dea` |
| `.pytest_tmp/task53-final-12.xml` | `60f081ba2e96af6abd26355fba1b8be780808c2d29e05cc557e4839ec8b82c8a` |

## Actual work-path timing evidence

All-reference freeze07 slowest actual JUnit cases (seconds):

| Existing or new test | Actual seconds |
| --- | ---: |
| `test_floating_sums_follow_original_python_sum_in_complete_event_order` | 70.005 |
| `test_large_single_event_uses_bounded_row_and_group_iteration` | 39.107 |
| `test_real_default_block_status_keeps_old_history_and_tennis_bytes` | 24.086 |
| `test_foreign_tour_future_backdated_and_same_time_rows_do_not_change_selected_order` | 19.888 |
| `test_unknown_end_window_boundary_and_latest_recovery_are_exact[1-7]` | 10.852 |
| `test_unknown_end_window_boundary_and_latest_recovery_are_exact[0-1]` | 10.087 |

The summation fixture is concrete and small: 78 real normalized matches,
156 receipts/contents, 78 chosen side-A rows. Its retained source is 352256
bytes; content payloads sum to 150528 bytes (963..965 each). Selected History
contains 156 inline rows totaling 198888 canonical bytes (1273..1275 each),
and occupies 839680 bytes. All-reference chosen receipt text totals 4992
bytes and association bytes total 5304; the all-reference feature DB occupies
155648 bytes. These counts were queried on the retained actual RO databases,
not inferred from a synthetic timing-only workload.

Root's retained old35/38 XML comparison in the brief reports paired
1.406/1.470s and summation 16.861/18.388s. Those historical walltimes are not a
controlled causal/native benchmark. The chosen-row lookup was, however, an
actual new repeated work path. One bounded work-path change was authorized:
small inline rows, large owning references, with the same checks and math.
Focused mixed run11 measured paired **2.123s** and summation **22.355s**, with
full old canonical bytes preserved; default >16MiB measured **14.036s**.
Its summation source and History files stayed at the same 352256/839680 bytes;
the mixed feature file is 303104 bytes versus all-reference 155648 bytes, a
measured 147456-byte storage cost of preserving bounded small inline rows.
No flaky timing assertion, speculative second optimization, removed source
check, or native-fit claim was introduced.

Final combined run12 slowest actual cases (seconds):

| Test | Seconds |
| --- | ---: |
| Original floating-sum order, 78 matches / 156 receipts | 24.118 |
| Single event, 600 revisions, including tracemalloc | 15.144 |
| Default-block >16MiB status differential | 14.906 |
| 125 equal-time conflict revisions, bounded pair handling | 6.191 |
| Foreign/future/backdated/tied order over three cutoffs | 6.187 |
| Source adapter unknown kind / oversized nonref header | 3.027 |
| Complete inventory / earlier source generation, shift=0 | 3.009 |
| Source adapter complete known ref array across chunks | 2.707 |

The requested paired differential measured **1.799s** in final combined run12
(focused mixed 2.123s; first all-reference freeze 6.439s).

Variation between all-reference, focused mixed and combined mixed runs is
visible even in unchanged tests. The observed work-path improvement therefore
does not establish a controlled native causal benchmark or old-baseline parity.
The mixed summation case still takes 22.355/24.118s versus Root's historical
16.861/18.388s; further native performance admission remains an explicit gate,
not a reason to silently remove validation or stack speculative optimizations.

After run12, read-only enumeration of all retained `task53-*` basetemp trees
found **1836 files / 223600454 bytes**; all 12 XML artifacts add **205161 bytes**
(combined **223805615 bytes**). Observed C-drive free space was
**1541741146112 bytes**, above the unchanged 4GiB reserve. These figures cover
this task's retained QA/retry artifacts, not the caller's entire active C/B
workspace, code checkout, runtime or input inventory. No artifact was removed
to improve those counts. Full outer <=8GiB accounting remains Root-owned.

## Remaining limits on claims

This is a bounded local correction of old admission compatibility within C3,
C4 and C6. It is not Task51, the complete small producer chain, measured growth,
global preparation admission, B, empirical injuries/fatigue approval, restore,
rollout, production data validation or release approval.

Old actual JSON decoding, source validation and canonicalization can hold one
large object plus temporary copies; the fixed two-row Tennis pair summaries
can hold two such objects. SQLite logical-key allocation is also not a bounded
reference block. No new decoded whole history/event group is collected, but
this task does not measure or certify native allocation/performance.

The unchanged later native gates remain worker CPU300s / AS2GiB / RSS<1GiB /
output1MiB and global preparation CPU1800s / elapsed3600s. Active full inputs
remain <=4GiB, full selected canonical history <=1GiB/tour, new encoded
reference/processing blocks <=16MiB, total new workspace/QA/retries <=8GiB,
and free reserve >=4GiB. This task never widens those limits or equates the old
64MiB whole-image boundary with a per-value cap. Outer resource accounting,
Source lifetime/sealing, independent review and integration remain Root's
responsibility.
