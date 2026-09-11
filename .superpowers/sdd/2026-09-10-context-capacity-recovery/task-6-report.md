# Task 6 implementation report

Date: 2026-09-11. Assigned worker scope only; BASE `b4ee364e4c2dfb7bf6a281ce7eed8a5384451402`, branch `codex/context-capacity-recovery-20260910`, worktree `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.

## Implemented contract

The original selected-receipt validator is preserved verbatim under `_validate_selected_tennis_receipt_cold`; an AST source-segment comparison against BASE (replacing only the function name) returned `COLD_BODY_VERBATIM True`. Its public signature and the feature signature are unchanged. The public wrapper accepts only the exact private witness implementation, otherwise calls the cold owner; arbitrary context objects have no methods invoked.

`_store` checks the original tree's exact builtin JSON types before encoding. Plain rows are independently cold-validated from their actual encoded/decoded representation. Nonplain originals go directly to the cold owner: rejected aliases remain rejected, while accepted metadata aliases remain accepted but make the entire entry unsealed. The physical inventory proof alone is never a selected-row seal. Only a fully completed fitting entry gets a monotonically fresh serial in bounded seal metadata. Replacement subtracts the old entry's bytes and removes its seal; eviction removes both bytes and seal.

The private context manager surrounds only the original full `tennis_features_v3` call in `verify_live_snapshot`; no-cache descriptors use `nullcontext`. Source-ref equality, feature equality, and the following transport replay are unchanged. No model result is cached, no input tuple is replaced with a capability, and every source field participates in each comparison.

## Lifetime and memory reasoning

- Entry, each attempted active row match (before and after encoding), and exit check the exact inventory, physical proof stamp, connection transaction generation, open transaction, write counter, and main/temp schemas. Revocation is a hard error, including empty scopes and mutation after the last checked row.
- `finally` deactivates each unique witness and resets its ContextVar token before the exit check. Nested scopes restore their predecessor, exception exits clean up, and copied inactive contexts use the cold owner. A witness is never reactivated by the implementation.
- Witness slots contain only cache/inventory references, key, serial, ordinal, and active flag. They hold no bytes, entries, decoded rows, index, or iterator. A match temporarily retrieves only one retained row; entry presence/serial and lifetime are rechecked after encoding. Eviction or same-key replacement yields a cold miss, never authority for old/new bytes. A reference-count regression confirms evicted bytes are not retained by the active witness.
- One aggregate 64 MiB default retained-plus-pending budget remains shared by both tours. There is no second encoded/decoded cache, no retained prefix pool, and seal metadata is removed with entries and remains within the existing 32-entry bound. Replacement byte accounting is explicitly exercised. Zero/oversize paths remain complete cold paths, not truncation or an admission change. The existing sealed consumer history budget remains 256 MiB; no admission code changed.
- The new fitting-basis seal is intentionally an extra cold pass. It removes repeated row-local derivation during snapshot features, not full physical validation, selector work, native/original/predictor replay, v2 checks, or event mathematics. Native runtime acceptance remains controller-owned.

## Tests and observed RED/GREEN

Every command below ran from the worktree above with `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`, `-B`, no pytest cache provider, warnings-as-errors for DeprecationWarning, and unique basetemp directories. Spies delegate to the actual owner; injected exceptions/mutations model interrupted work or real SQLite lifetime changes. No production validation was replaced by an accepting mock.

Initial RED, before any product edits:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_receipt_witness.py --basetemp=.pytest_tmp/task6-red1
```

Observed **4 failed in 3.18s**, exit 1:

- `test_repeated_full_snapshots_replace_only_cold_receipt_derivation`: only 10 native selected-row validations rather than 20 (selection plus independent seal).
- `test_store_cannot_launder_source_invalid_or_type_aliased_rows[source]`: source-invalid but rehashed B1 row did not raise in `_store`.
- Same test `[tuple]`: original nested tuple was laundered without rejection.
- `test_final_row_interrupted_owner_seal_publishes_nothing`: no final-row owner invocation, so the expected KeyboardInterrupt did not occur.

Initial GREEN after the three-file implementation:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_receipt_witness.py --basetemp=.pytest_tmp/task6-green1
```

Observed **4 passed in 3.12s**, exit 0. Additional boundary batches needed no further product change and passed as written (not claimed as separate preimplementation RED runs):

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_receipt_witness.py --basetemp=.pytest_tmp/task6-boundaries1
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_receipt_witness.py --basetemp=.pytest_tmp/task6-boundaries2
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_receipt_witness.py --basetemp=.pytest_tmp/task6-boundaries3
```

Observed **61 passed in 18.52s**, **88 passed in 21.04s**, **93 passed in 20.93s**, respectively, all exit 0. The final repeated-consumer test now runs three complete passes over the ten real snapshots: 30 full snapshot feature/transport replays, a single 10-row seal, and zero repeated cold selected-row derivations.

Explicit process-local mutation RED checks (no file edits or persistent monkeypatches):

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -c "import contextlib,pytest; import context_runtime_history_cache as hc; hc.EncodedHistoryCache._selected_receipt_scope=lambda *a,**k: contextlib.nullcontext(); raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','-W','error::DeprecationWarning','tests/test_context_runtime_receipt_witness.py::test_repeated_full_snapshots_replace_only_cold_receipt_derivation','--basetemp=.pytest_tmp/task6-mutation-scope']))"
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -c "import pytest; import context_runtime_history_cache as hc; hc._plain_json=lambda value: True; raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','-W','error::DeprecationWarning','tests/test_context_runtime_receipt_witness.py','-k','current_value_and_type','--basetemp=.pytest_tmp/task6-mutation-type']))"
```

The missing-scope mutation failed the repeated-work test with **300 extra cold owner calls**, **1 failed in 3.23s**, exit 1. The untyped-equality mutation produced **9 failed, 9 passed, 75 deselected in 6.89s**, exit 1: participants/workload/issues tuples, dict/list/string aliases, alias keys, accepted metadata alias, and top-level key alias. Invalid aliased inputs stopped raising; the accepted metadata alias incorrectly bypassed its cold owner. These prove why untyped canonical equality and omission of the scope are not equivalent implementations.

Final focused matrix (run once; controller runs the whole repository suite):

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_receipt_witness.py tests/test_context_runtime_capacity.py tests/test_context_runtime_shared_history.py tests/test_context_runtime_tennis_live.py tests/test_context_runtime_semantics.py tests/test_tennis_status_v3.py tests/test_tennis_context_features.py tests/test_tennis_v3_model_transport.py tests/test_tennis_live_worker.py tests/test_tennis_live_integrity.py tests/test_workflow_integrity.py --basetemp=.pytest_tmp/task6-focused-final --junitxml=.pytest_tmp/task6-focused-final.xml
```

Observed **657 passed, 9 skipped in 568.42s (0:09:28)**, exit 0. JUnit: `.pytest_tmp/task6-focused-final.xml`. No product or test files changed during this run; process-local mutation checks ran in separate interpreters and did not affect it.

## Coverage and self-review

New tests exercise direct storage poisoning, final-row interruption/mutation, exact nested tuple/list/dict/string/key/integer/float types, bool and nonfinite values, missing/extra fields, unchanged hashes over changed bodies, rehashed source-invalid data, accepted-but-ineligible metadata, valid reordered/duplicate/changed fallback, fresh nested consumer ownership, encoding failure, entry eviction and same-key replacement before/during comparison, both tours, byte accounting, bounded empty entries, tuple container rejection, arbitrary context objects, nested/exception/copied contexts, and lifecycle changes at entry/comparison/exit/empty scope.

Complete canonical feature outputs are compared cold/scoped for paired, legacy, mixed, unavailable, conflicting, revised participant/schedule, target started/cancelled/participant/schedule/defective/matching states at four cutoff boundaries. Malformed future/unrelated/opposite-tour direct tuple rows fail before projection. Existing shared tests retain original/predictor calls for all ten original publications, safe orphan replay, source refs, full report equality, optional oversized basis fallback, and complete eligible opposite-tour checks. The real unopened-final capacity test now enters an empty witness scope while the existing actual-final decoder guard is active. Existing physical-inventory/transaction/future/unreferenced corruption and integrity suites remain in the focused matrix.

Only three product files and assigned tests/report are changed by this worker. Inventory, transaction, input, dataset/evaluator/training, schemas, deploy/helper files, v3/v2 mathematics and the six predictor/state CODE_PATHS are untouched. Controller ledger/native-harness WIP is explicitly excluded from staging. No subagents, push, VPS action, generated native fixture, or native performance profile was used by this worker.

## Source hashes (SHA-256 of exact local bytes)

Changed source:

| File | SHA-256 |
| --- | --- |
| context_runtime_history_cache.py | 260eb2f2ed1808ddc3307a9047d555a4ea9e2145c7e4b4fe1424c4e4658ecd6f |
| context_runtime_tennis.py | b3f09a86f11bdb7c76101d3ed881568a424e3a54e17b04761a375363d8d8d2f6 |
| context_sources/tennis_status.py | 8fc6018f827874d429495c9717496e9cbdaad837c64865113c866948ae5e56ab |

All following files were compared byte-for-byte with BASE and are unchanged:

| File | SHA-256 |
| --- | --- |
| context_models/tennis_v3.py | ec6461b87656ecc5731992cc26f0ae69d20e878982706ebe3f1fd0599c43305c |
| context_models/tennis.py | 313ffafacc367e7370312f478327d6453860ac0bf17bbcaf8102acdda49e4bab |
| tennis/predict.py | bd1c2c8f7666e3de5f32d754eac09967edde566c1d7b48c298635f2b3d989ecc |
| tennis/model_state.py | 3512c7aa047d11f809402fe434fcaae6ebf0542e961174348d2e6972198d7134 |
| tennis/elo.py | 689c50cdd9cbb5489ff66fbcc10814683c18ebcc79c97b648ceea4db738083c6 |
| tennis/serve_model.py | dd76339957cc806e5bea14584c47c9467b242966bd531a6c03adf3b067e803aa |
| tennis/simulator.py | 6f326fc84de6b705b762b9d9efaa2932daf0f4546c419d56f30e8c3f4644e29f |
| tennis/data_loader.py | 521bb2525a8a874b64f4afe55c49e18c075bdc04348e38b1632c95af6aec4620 |

## Remaining gates / concerns

No native runtime, release, model evidence, or deployment acceptance is claimed. The ContextVar dependency and independent cold seal deserve the planned independent review. The controller must measure the committed code against newest actual current input (controller reports 99,521 receipts/26 snapshots) and G1/G2/G3 under the unchanged UID/resource/output contracts; unit call-count gains do not prove CPU/RSS acceptance. Full repository suite, independent code review, backup/restore release evidence and publication/deployment remain controller-owned. Historical implementation hashes are not whitelisted or normalized.

Exact local commit message: `Seal selected Tennis receipt checks against shared encoded history`. Stage only `context_runtime_history_cache.py`, `context_runtime_tennis.py`, `context_sources/tennis_status.py`, `tests/test_context_runtime_receipt_witness.py`, and `tests/test_context_runtime_capacity.py` with `git -c core.autocrlf=false add -- ...`; force-add only this exact ignored report path. The commit hash and post-commit empty-index verification are returned in the worker handoff. Controller changes to `progress.md`, `task-5-review.md`, and `task-6-native-evidence.md` remain unstaged and untouched by this worker.
