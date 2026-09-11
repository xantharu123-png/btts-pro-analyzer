# Task 8 implementation report

Date: 2026-09-11. Implementer scope: original-only complete-basis native projection.
Starting commit: `06db3bec8c7e7301847b5d06b4b9af521245f28c`.
Binding requirements: `task-8-brief.md` and the complete `task-8-design-analysis.md`, including the controller ruling and corrected owned-full fallback.

## Status

DONE for implementer scope. Final focused regression: **962 passed, 12 skipped in 556.58s (0:09:16)**, exit 0. No native resource acceptance, independent review, full-repository suite, push or deployment is claimed by this report.

The original-only tuple representation refinement is used exactly as authorized. Every snapshot still receives a complete fresh tuple. No original or snapshot predictor/feature/transport result is memoized.

## Changed scope

- `context_runtime_history_cache.py`: private validated-publication planning, fixed cold-owner preparation, entry-local owned-completeness markers, bounded scalar query folds during the independent seal, metadata accounting, original-only candidate lookup and pinned owned-full fallback.
- `context_runtime_original_projection.py`: small scalar query record/reservation/fold helper. No SQL, decoder, source selector, model calculation, encoded history alias or retained payload.
- `context_runtime_tennis.py`: original planning delegates to the cache owner; original history/native processing uses the projection or the exact owned-full/cold fallback. The one native predicate, native-event equality, actual state decoding, predictor call and recorded-result comparison remain shared/unchanged in meaning and replay order.
- `tests/test_context_runtime_original_projection.py`: 83 behavioral cases on actual persisted native source and original fixtures, real owning validators and builders.
- Existing shared/capacity tests: adjust only the actual new accounting/materialization contract. Original hits are no longer counted as full-history cache materializations; shared cache bytes include new charged metadata. Two overflow tests use 256 cache bytes instead of 1 so the newly charged fixed plan can exist and their intended overflow/mutation boundary is actually exercised.
- This exact report. Controller-owned progress/handoff/native helper files were not staged or edited by the implementer.

No edits to `_cold_replay_history`, `_replay_history`, `verify_live_snapshot`, source validators, inventory/transaction/input/runtime owners, v3/v2/math/predictor/CODE_PATHS, dataset/evaluator/training, schemas, data or deployment scripts/helper pins.

## Completeness and admission argument

1. `_prepare_originals` visits every supplied artifact and executes the unchanged `validate_original_publication(..., created_at=...)` for every actual original. Duplicate queries are deduplicated only for optional proof storage; original processing still visits all publications, including orphans and queries beyond capacity. Maximum tour cutoffs continue to advance when query capacity is exhausted. If even the fixed planning reservation cannot fit (including a zero cache), optional preparation is omitted; validation and complete per-original cold fallback remain mandatory.
2. Only an internally planned tour cutoff is eligible for `_prepare_original_basis`. Caller `_plan_bases` cutoffs alone cannot authorize that operation. It imports and invokes the fixed unchanged `_cold_replay_history` itself, with optional basis overflow distinct from integrity/admission failure. No selected-history argument, builder callback or trusted/completion flag exists on that operation.
3. The fixed operation passes its own complete history through `_store_encoded`, which performs the existing independent cold source seal on each canonical encoded row. The scalar fold uses that same freshly decoded, independently validated representation. It does not add another scan/decoder or filter target schemas/statuses.
4. For each retained query the fold stores whole-prefix canonical byte count, latest target clock, count saturated at two, and at most one ordinal. Every included tour row contributes bytes; every included matching target contributes to latest/uniqueness, including workload and equal-clock competitors. Therefore its absent/unique/ambiguous decision is the same as the complete tuple predicate.
5. Only after the fixed cold completion, complete independent seal, fresh inventory proof and matching completed serial can preparation publish an owned marker and activate drafts. Direct `_store` discards same-tour optional queries and can never publish a marker. Same-key replacement drops prior markers; byte equality cannot transfer completeness. Interrupted/failed preparation drops drafts and original authority. Reentrant replacement cancels the pending optional build instead of sharing/resetting its byte pool.
6. Projection lookup checks the current inventory proof and exact query/basis serial, applies the WHOLE prefix byte limit before native absence/ambiguity rejection, and decodes only a fresh unique candidate. It validates ordinal range and matching candidate event/clock and rechecks lifetime/serial after decode and on the empty/ambiguous final path.
7. A projection miss can materialize ONLY a particular owned-complete entry pinned by its actual key and serial. An unowned exact-key subset cannot shadow an owned covering entry. Reconstruction resolves that pinned entry at each row; there is no complete encoded tuple alias or iterator surviving the reconstruction call's lifetime checks. Pure replacement/eviction discards the attempted result; invalid inventory/proof/schema/transaction state is a hard error.
8. With no owned entry the original calls `_replay_history(..., cache=None)`, never an unrestricted generic cache fallback. A fresh post-cold cache proof check preserves the lifetime boundary formerly supplied by `_store`; that also covers empty cold results. The common native predicate then checks schema, digest, clock, competition revision, status/issues, native-event equality and the exact actual predictor capture.

No new model, probability, source identity, source-hash rule, data rejection policy or public report field/limitation string is introduced.

## Accounting and lifetime argument

- The existing `_bytes + _pending_bytes <= _max_bytes` bound includes new scalar metadata reservations. `_metadata_bytes` is included in `_bytes`, not another budget. Entry sizes continue to mean canonical row bytes for consumer admission.
- At most 30 optional query slots are retained, leaving room for two tour entries. Query admission also accounts for existing entry slots. Storage eviction enforces entries + queries <= 32. With no queries the existing 32-entry cap remains.
- Each query charges `len(canonical_bytes(key)) + 192 + 2*len(str(byte_limit)) + len(str(serial))`. The fixed allowance covers the two fixed-width clocks/tour representation, saturated count, nulls and punctuation; prefix bytes and ordinal are bounded by the basis-byte limit. Long keys are charged in full, and serial width is re-reserved before activation. No second encoded metadata copy is retained.
- Each possible tour plan reserves 128 bytes for both bounded cutoff-map representations. The relevant publication/current row is temporary owning work, not retained proof metadata. If query reservations obstruct the second tour plan they are dropped first. Completed basis-map state remains charged until removed.
- Each completeness marker charges its actual canonical key/serial representation plus 32 bytes in its entry's existing slot. If it cannot fit, preparation retains at most a row-sealed entry with no original authority and uses complete cold fallback. Query-cap-zero still supports a marker and exact owned-full fallback when fitting.
- During encoding, optional queries are dropped before sacrificing a fitting history. Planning can also be dropped, cancelling remaining optional tour preparation; then old entries are evicted if necessary. No partial/oversized history is published. Counters and ordinals stay bounded by the history budget; the tested large serial is `10**200`.
- Eviction/replacement removes marker charges and active query charges. Query records contain only keys, counters, clocks and serials: no decoded row, encoded row or encoded-entry tuple. Descriptors remain non-owning references to the verification-local cache/inventory, not histories.
- Lifecycle tests cover cold completion, final independent seal, publication, projected decode, owned full decode, empty/ambiguous completion and cold fallback completion. Write, main/temp DDL, commit/rollback/restart, proof revocation and closure remain hard failures. Pure cache changes become safe misses. This is the existing sequential transaction-stamp guarantee, NOT a stronger claim of atomic asynchronous DDL protection.

## TDD and focused commands

All commands ran in `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910` with:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning <files and filters below> --basetemp=<unique directory below>
```

Before product edits:

```text
tests/test_context_runtime_original_projection.py
--basetemp=.pytest_tmp/task8-red-1
6 failed in 3.95s
```

Expected RED evidence: ten originals decoded 110 cached rows instead of 20 (ten independent seal rows plus ten unique candidates); direct stored valid older subsets were wrongly accepted despite actual newer/equal-time competitors; empty poisoning did not execute a complete cold fallback; metadata diagnostics did not exist. No source validators were mocked out.

Iteration evidence:

- New projection + shared suite (`task8-green-1`): 32 passed, 3 failed, 17.47s. Remaining failures were old raw-byte-only accounting and tiny-budget preparation expectations, updated only for the new actual metadata contract.
- Projection lifetime/native provenance (`task8-boundaries-1`): 45 passed, 37.62s.
- Budget/slot/serial filter (`task8-budget-1`): 7 passed, 52 deselected, 7.36s.
- Native matrix (`task8-native-1`): 13 passed and two fixture errors from deleting receipts but leaving orphan contents; fixture cleanup was corrected, retaining real inventory validation.
- Planning-charge RED (`-k planning_charge`, `task8-plan-red`): 1 failed, 74 deselected. Reservation 69 bytes was smaller than the actual two-map 77-byte canonical representation. Fixed to conservative 128 bytes per tour.
- Interrupted-marker RED (`-k interrupted_marker`, `task8-publish-red`): 1 failed, 75 deselected. Marker survived until the outer planner caught interruption; the fixed preparation now cleans authority before returning to its caller.
- Projection + shared (`task8-iteration-3`): 105 passed, 70.16s.
- Two-tour/excess filter (`task8-two-tour-1`): 4 passed, 76 deselected, 2.94s. All 45 actual original processing calls execute despite 30 query slots.
- Reentrant final-seal RED (`task8-reentrant-red`): 1 failed, 1 passed, 80 deselected. Nested direct storage could publish with the outer pending pool. Fixed by cancelling reentrant optional retention; the original still has the complete cold fallback.
- Self-review GREEN (`-k 'reentrant or planning_charge or interrupted_marker'`, `task8-selfreview-green`): 3 passed, 79 deselected, 4.00s.
- First broad focused run (`task8-focused-final`) was deliberately interrupted during further final-lifetime audit, around 57% completion. It had one obsolete capacity expectation (four full-history hits versus two snapshot-only hits) and platform skips. It is NOT a final acceptance run.
- Cold-fallback completion RED (`-k cold_original_fallback`, `task8-cold-final-red`): 1 failed, 82 deselected; mutation immediately after the complete cold owner was not rechecked. After restoring that explicit boundary (`task8-cold-final-green`): 1 passed, 82 deselected, 2.23s.
- Capacity contract isolation (`-k real_d4_shares`, `task8-capacity-contract-red`): 1 failed, 142 deselected, precisely `hits == 2` versus old `4`. Updated to two full snapshot hits plus two original queries.

Final complete focused regression command:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_original_projection.py tests/test_context_runtime_shared_history.py tests/test_context_runtime_capacity.py tests/test_context_runtime_receipt_witness.py tests/test_context_runtime_tennis_live.py tests/test_tennis_status_v3.py tests/test_tennis_context_features.py tests/test_tennis_v3_model_transport.py tests/test_context_runtime_transport.py tests/test_context_runtime_semantics.py tests/test_tennis_live_integrity.py tests/test_tennis_live_origin.py tests/test_tennis_live_publication_clock.py tests/test_tennis_native_status_codes.py tests/test_tennis_live_worker.py tests/test_context_tennis_capture.py tests/test_tennis_check_equivalence.py tests/test_context_runtime_backup.py --basetemp=.pytest_tmp/task8-focused-final-2
```

Result: `962 passed, 12 skipped in 556.58s (0:09:16)`, exit 0. All six final product/test hashes below were rechecked after this run and are unchanged.

An isolated skip-reason check added `-rs` and selected `linux_real_dac or linux_sealed_reader or symlink or world_writable_database` from capacity/backup, with `--basetemp=.pytest_tmp/task8-platform-skip-reasons`: 12 skipped, 227 deselected, 0.98s. Exact reasons: nine real Linux DAC/sealed-reader fixtures unavailable on Windows; two actual symlink fixtures unavailable with WinError 1314 (missing privilege); one POSIX owner/mode check skipped because Windows uses ACLs. These platform gaps remain native/controller gates, not passed cases.

## Immutable baseline equivalence

Development-only oracle used `git show 17cfbbc3a2786190482b001f40361bf8e7667152:context_runtime_history_cache.py` and the corresponding `context_runtime_tennis.py`. Both were compiled into temporary in-process modules with the real workspace path for unchanged CODE_PATHS resolution. No baseline file was written or restored over product code; committed tests have literal fixture expectations and no Git runtime dependency.

On 12 persisted native matrix fixtures from `task8-iteration-3` plus the ten-original/ten-snapshot fixture from `task8-green-1`, the current and immutable baseline produced:

```json
{"oracle":"17cfbbc3a2786190482b001f40361bf8e7667152","fixtures":13,"reports":3,"errors":10,"canonical_equal":true}
```

Canonical full-outcome SHA-256: `11ad207d7cbdd8569d5fad1743f2407f82b6d04552f21c6dde490b9ecfa43742`.

A second oracle called actual `verify_live_originals` directly using `TrackedConnection`, actual artifact mapping, completed receipt validation and original creation clocks, so the runtime's outer generic error wrapper could not conceal a native difference:

```json
{"oracle":"17cfbbc3a2786190482b001f40361bf8e7667152","fixtures":13,"accepted_originals":12,"native_errors":[["error","ArtifactIntegrityError","live original native current input was absent or revised"]],"equal":true}
```

Committed tests additionally compare canonical reports, full ten-row snapshot tuples, all ten predictor calls and all ten feature calls with projections disabled, query capacity zero, basis eviction and cache capacity bypass. Native status/workload/absent/ambiguous/future cases compare exact original errors and predictor counts against complete cold selection.

Additional development lifetime check on an actual owned ten-original basis: after `_evict`, a held encoded row had `sys.getrefcount(raw) == 2`, the owned/query maps were empty, and only the explicitly charged 128-byte cutoff plan remained. The descriptor retained no hidden encoded-row alias.

AST-extracted function source was compared with starting commit 06db3be and remained identical:

| Function | SHA-256 of unchanged source segment |
| --- | --- |
| `_cold_replay_history` | `7e8475da8af8094d6edc331d1128e7f73a01a76b735592abe47c548597bf324d` |
| `_replay_history` | `da04d81792e4f853483b4c56ad594f9c0f500f399dc1edd670b0894162b9a22d` |
| `verify_live_snapshot` | `50222694f07b4d30c666d0d34a0c54ef1a4d7d2c02d8c0ed1a78fb694b9768b8` |

## Frozen hashes

SHA-256 of final implementer product/test files (raw workspace bytes):

| File | SHA-256 |
| --- | --- |
| `context_runtime_history_cache.py` | `8387bc930b957a8983de8a330c6372a64c4b08c5daf4e7ef8b1a07f2cdf84d76` |
| `context_runtime_tennis.py` | `61c6ffce8ef4837329a18792d465660e9de91cdddd69051207fe22eb7bee98cd` |
| `context_runtime_original_projection.py` | `ddc5632cc3e8f8ad9379799d0953f76e9d2d6cf733b6a0b5f9566c5c7302036b` |
| `tests/test_context_runtime_original_projection.py` | `c0262942b2357080ba415e317e9921cf7e05b33b91eb1124c74a0210e57a63ef` |
| `tests/test_context_runtime_shared_history.py` | `e2469580e2fa66ff43fc3a7316714329c08049893d97fd9a0601bc1f42b60b8f` |
| `tests/test_context_runtime_capacity.py` | `c07e0ce16fa202e832495bacc3be6300a4bce3933742032abae3e13329adbe70` |

Unchanged protected owner hashes:

| File | SHA-256 |
| --- | --- |
| `context_runtime_inventory.py` | `a4f0f9a2833c5b5cc8eacc2a562cc2d2104a4aafcffe44dd0c7e7851b8ced707` |
| `context_runtime_transaction.py` | `ecec258d9b67964da29b9da91859c5d80ed24100765b04e14db5269b8d4e8e5b` |
| `context_runtime_input.py` | `798fc7146410b214752e98a1fa86af27a33f837b3ce53e86146fcf79e8a3f228` |
| `context_models/tennis_v3.py` | `ec6461b87656ecc5731992cc26f0ae69d20e878982706ebe3f1fd0599c43305c` |
| `context_sources/tennis_status.py` | `348c48489abcadad8c10939ee6f76ac5ffe19d5c2684385a283d534944a669a2` |
| `context_sources/tennis.py` | `80f1621f60e0b3daecef8abb5e44efeebd2c2bc6bc0df8161032daab78ceb739` |
| `tennis/predict.py` | `bd1c2c8f7666e3de5f32d754eac09967edde566c1d7b48c298635f2b3d989ecc` |
| `tennis/model_state.py` | `3512c7aa047d11f809402fe434fcaae6ebf0542e961174348d2e6972198d7134` |
| `tennis/elo.py` | `689c50cdd9cbb5489ff66fbcc10814683c18ebcc79c97b648ceea4db738083c6` |
| `tennis/serve_model.py` | `dd76339957cc806e5bea14584c47c9467b242966bd531a6c03adf3b067e803aa` |
| `tennis/simulator.py` | `6f326fc84de6b705b762b9d9efaa2932daf0f4546c419d56f30e8c3f4644e29f` |
| `tennis/data_loader.py` | `521bb2525a8a874b64f4afe55c49e18c075bdc04348e38b1632c95af6aec4620` |

`git -c core.autocrlf=false diff --check` passed for the assigned files. A scoped diff from 06db3be for `context_sources`, `context_models`, `tennis`, runtime inventory/transaction/input/main, dataset/training/transport and scripts was empty. Existing controller documentation WIP was left untouched.

## Self-review and remaining gates

The self-review explicitly checked direct valid subset poisoning, caller cutoff authority, actual entry binding of full fallback, missing/ambiguous budget precedence, final/empty proof checks, serial replacement, marker publication interruption, pending-pool reentrancy, both-tour and metadata pressure, long actual query keys, and exact unchanged owner calls. Discovered defects were recorded RED and corrected rather than waived.

No known local completeness/admission/lifetime defect is intentionally left open. The native performance hypothesis remains unproved: saving repeated original materialization does not itself establish CPU/RSS acceptance on the actual input or growth profiles. Independent scoped review and whole-branch review remain controller-owned, as do the entire repository suite and exact native jobs.

Unchanged resource contracts: input 1GiB; sealed history 256MiB; encoded cache 64MiB including new scalar metadata; 32 aggregate metadata slots; native UID997/AS2GiB/CPU300/wall600/output1MiB; measured CPU/wall below 300 and RSS below 1GiB. No bounds were relaxed.

Actual current/G1/G2/G3 native profiles are still required. So are the fresh complete 88DB backup, actual restore/HMAC verification, updater-only exact transition and later separate normal exact app deployment. Quote/Cricket/A0/P4b3, histories/tickets/ledger/keys/markers/protected helpers remain outside implementer scope. No SSH/VPS/native execution, push, main/updater/app mutation or release approval was performed.

Skills used: test-driven-development (real RED/GREEN contract tests, real owners retained) and verification-before-completion (fresh scoped verification and exact evidence before commit). The requested using-superpowers skill was read; its subagent-stop rule applies to this dispatched task.

## Commit/index handoff

The index was verified empty before exact staging. Only the six assigned product/test files above and this force-added report enter the Task8 commit, using `git -c core.autocrlf=false`. The controller's progress/handoff/native documents are excluded. Final commit identity and post-commit empty-index evidence are returned to the controller in the final handoff, avoiding a self-referential commit hash inside this report.

## Review fix round 1 of 5 — dropped scalar-draft lifetime

Base: `7bab03c481a7d6053ef53ad796527bad259adfd4`. Binding independent review: `task-8-review.md`. This amendment supersedes the initial report's no-known-accounting-defect assessment: the reviewer found an Important retained-reference defect not covered by counter-only checks.

The review was confirmed against the actual seal loop. Python kept the last `query` loop local alive in `_store_encoded` across later `_make_room` calls. Removing that record from `_queries` and subtracting its reservation therefore did not release the record. With the exact 13,690-byte fixture history budget, pending canonical history could fill the budget while an uncharged query draft still existed.

The initial correction moved only the unchanged per-row scalar loop into `_fold_original_queries`. Its frame and loop local are released when the call returns, before the existing later proof checks and before the next row's pressure/accounting operations. The same already decoded and independently cold-owner-validated row, tour, canonical byte length and ordinal are passed through. The related enclosing-frame findings and final corrections are recorded separately below. No scan, decoder, metadata reservation, query predicate, seal boundary, completeness/fallback authority or model/native behavior is changed.

The new regression observes actual record lifetime, not only counters. A test-only subclass adds weak-reference support to the real `_OriginalQuery`; its initialization, reservation and fold logic remain real, and the observer keeps weak references only. On the real persisted ten-original fixture, the test inspects the existing final seal boundary when pending bytes equal the entire cache budget and retained query/metadata counts are zero. All ten removed records must already be dead, and the complete encoded entry must still be retained. No source/inventory validator or owning builder is replaced.

Exact RED command, before the product correction:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_original_projection.py -k dropped_query_records --basetemp=.pytest_tmp/task8-fix1-red
```

Result: `1 failed, 83 deselected in 2.46s`, exit 1. Assertion: `dropped query record outlived its metadata charge`; actual live weak-reference count was `1`, expected `0`, despite zero charged metadata/queries.

The same targeted command with `--basetemp=.pytest_tmp/task8-fix1-green` after correction: `1 passed, 83 deselected in 2.28s`, exit 0.

Complete requested covering regression, no broader/native suite:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -rs -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_original_projection.py tests/test_context_runtime_shared_history.py tests/test_context_runtime_receipt_witness.py tests/test_context_runtime_capacity.py --basetemp=.pytest_tmp/task8-fix1-covering
```

Fold-only covering result: `365 passed, 9 skipped in 186.99s (0:03:06)`, exit 0. Nine skips were exactly the real Linux DAC/sealed-reader fixtures unavailable on Windows (one real-DAC case and eight sealed-reader variants). This completed run belongs ONLY to the initial fold-helper hashes below; it was not interrupted or represented as final coverage of later enclosing-frame changes.

Initial fold-only SHA-256 values (raw workspace bytes):

- `context_runtime_history_cache.py`: `3daade89708a2caf97757bc2daab37895d8a3bcd1ec5de987f06af6245f8fe22`.
- `tests/test_context_runtime_original_projection.py`: `0ffdc5585d49952da9163613193bde690d31dcdc004afb45f7e357ee2b73033e`.
- Unchanged `context_runtime_original_projection.py`: `ddc5632cc3e8f8ad9379799d0953f76e9d2d6cf733b6a0b5f9566c5c7302036b`.
- Unchanged `context_runtime_tennis.py`: `61c6ffce8ef4837329a18792d465660e9de91cdddd69051207fe22eb7bee98cd`.

### Related enclosing-frame checks requested by the controller

While the fold-only covering run continued, the controller identified two related possible aliases in the same accounting/lifetime class: `_store`'s final `query_key` and `_prepare_originals`' final `key` plus validated publication temporaries. They were reproduced before further product edits, after the earlier covering run had completed.

- With the query weak-reference count already zero at the full-pending-budget boundary, a known single key probe still had reference count 3 instead of the expected 2 (the probe plus `getrefcount`'s argument). The remaining reference was in the planning parent frame.
- Before `_store_encoded` began, the key probe likewise had reference count 3 rather than 2 because `_store` retained its final dropped key.
- Immediately before cold-basis preparation, weak references still saw the final validated publication and its origin copy (2 live temporaries, expected 0). The observing validator wrapper always calls the complete real publication validator; it adds only weak-reference-capable dictionary wrappers to the validated returned copies.

The first reference-count assertion exposed pytest's temporary expression reference as well; measurement was moved to a preceding assignment so assertion rewriting does not own a key. The corrected, still-RED run was:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_original_projection.py -k 'dropped_query_records or direct_store_releases or planning_releases' --basetemp=.pytest_tmp/task8-fix1-related-red-2
```

Result: `3 failed, 83 deselected in 4.40s`, exit 1, with the exact 3-versus-2, 3-versus-2 and 2-versus-0 observations above. The earlier instrumentation run (`task8-fix1-related-red`) also had three failures; it is not used for the corrected key-reference count.

The unchanged planning loop now executes in `_plan_original_publications`, whose local key/publication/origin/envelope references end before basis preparation. The unchanged same-tour drop loop now executes in `_drop_original_tour_queries`, whose key references end before encoded construction starts. The existing cache owner still performs all real publication validation and the fixed full cold preparation; there is no new caller authority, changed numerical/model code or altered gate/order. The same three targeted tests passed with `task8-fix1-related-green`: `3 passed, 83 deselected in 4.08s`, exit 0.

Both key-lifetime cases now also cover actual valid planning identities with 4,096-digit event identifiers. A single explicitly observer-owned key reference is subtracted from the lifetime measurement; weak record/publication observers retain no strong references. The long-ID fixtures deliberately test planning and retention only, not native acceptance of a changed event. Broader targeted planning/pressure/caller-key/serial/two-tour/excess/subset coverage then ran:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_original_projection.py -k 'dropped_query_records or direct_store_releases or planning_releases or planning or pressure or caller_cutoffs or large_serial or both_tour or all_excess or direct_store_cannot' --basetemp=.pytest_tmp/task8-fix1-related-final
```

Result: `22 passed, 66 deselected in 16.91s`, exit 0.

Final owner-coverage command explicitly requested by the controller for the final changed planning/drop state:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -rs -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_original_projection.py tests/test_context_runtime_shared_history.py tests/test_context_runtime_capacity.py::test_encoded_history_real_d4_shares_original_snapshot_cache --basetemp=.pytest_tmp/task8-fix1-final-owner-covering
```

Final owner-coverage result: `118 passed in 85.15s (0:01:25)`, exit 0, with no skips. The earlier four-file run and this final targeted coverage remain separately attributed; the 962-test/full-repository/native suites were not repeated in this round.

Final fix-round SHA-256 values:

- `context_runtime_history_cache.py`: `ae30feb5624797fd32e00541d748c0ba6a18acf62fa04c623b1ea0b29cf7b06a`.
- `tests/test_context_runtime_original_projection.py`: `94b9467aaa586da49db99c2bb998fe22472d630d0cb79ca5a509aba83a930cf8`.
- `context_runtime_original_projection.py` and `context_runtime_tennis.py` retain the unchanged hashes listed in the fold-only subsection. Scoped diff checks also show no change to source/model/native owners, inventory, transaction or input modules.

Self-review: the fold helper has no pressure/accounting operations, does not return or retain query/row references, and ends on every successful fold before the seal advances. The planning and drop work-frame locals now end before their next construction phase. The lifetime tests distinguish a dead query record from a still-owned key and directly inspect the validated publication copies' lifetime. Existing proof checks, interrupted/reentrant seal cancellation, post-cold lifetime checks, and pinned owned/full fallback code are untouched. This round changes only the cache file, its projection regression file, and this report. Receiving-code-review, TDD and verification-before-completion skills informed the verification and fix.

No independent re-review, native performance, broader final-suite or release acceptance is claimed by this fix round. The prior 7bab QA archive was uploaded by the controller but never staged/executed; this fix requires a new exact pin. Controller-owned documentation/native-preparation WIP remains unstaged. Exact commit identity and empty-index evidence follow in the implementer handoff.
