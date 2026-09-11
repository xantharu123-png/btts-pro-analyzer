# Task 5 report: D2 SQLite parameter compatibility

## Scope and baseline

- Branch: `codex/context-capacity-recovery-20260910`.
- Starting HEAD: `7cf1e94e2033f0075f0c1e21252deccc158555d2`.
- Owning requirement: `task-5-brief.md`.
- Production scope remained limited to `context_models/dataset.py`; the focused
  regression is in `tests/test_context_dataset.py`.
- No model mathematics, evaluator identity/hash allowlist, schema, deploy,
  Tennis source, or anonymous `?`/tuple key-enumeration query changed.
- Controller-owned changes in `progress.md`, `PC_WECHSEL_UEBERGABE.md`, and
  `docs/superpowers/plans/2026-09-10-context-capacity-recovery.md` were present
  before this task and were not edited or staged by Task 5.

## RED

The test uses a real `sqlite3.Connection` subclass. Every execution is first
delegated to SQLite; the subclass records emitted mapping parameters without
matching or inspecting SQL source text. A valid copied opaque-receipt database
must complete `_physical_receipt_preflight`, each physical payload must cross
the six-projection boundary as `{"opaque": <same BLOB bytes>}`, and a patched
`_decode_receipt` fails the test if any protected body decoder is called.

Command (production still unchanged):

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest tests/test_context_dataset.py::test_outer_projection_binds_each_opaque_receipt_by_named_mapping_without_decoding -q -p no:cacheprovider -W error::DeprecationWarning --basetemp=.pytest_tmp/task5-red-02
```

Exact failure result (exit 1):

```text
F                                                                        [100%]
================================== FAILURES ===================================
_ test_outer_projection_binds_each_opaque_receipt_by_named_mapping_without_decoding _
...
>           assert connection.named_bindings == [{"opaque": opaque} for opaque in expected]
E           assert [] == [{'opaque': b...:null}'}, ...]
E
E             Right contains 4732 more items, first extra item: {'opaque': b'{"competition":"39","complete":true,"event_key":"api-football:football:900000","format":"90min","kind":"b..."football","subject_id":"api-football:football:900000","valid_from":"2026-08-05T15:00:00.000000Z","valid_until":null}'}
E             Use -v to get more diff

tests\test_context_dataset.py:296: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_context_dataset.py::test_outer_projection_binds_each_opaque_receipt_by_named_mapping_without_decoding
1 failed in 45.93s
```

This Windows runtime did not emit the native warning. The fallback required by
the brief therefore failed on the actual emitted parameter boundary: all 4,732
valid opaque receipts used sequence binding and zero used a named mapping.

## Minimal fix

Only the six repeated numbered placeholders in the outer-header projection
changed from `?1` to `:opaque`, with binding changed from `(opaque,)` to
`{"opaque": opaque}`. The fixed six projections, BLOB value, all closed outer
keys, projected identities, and later physical/index checks are unchanged. The
separate `json_each(CAST(? AS TEXT))` anonymous-placeholder tuple binding is
unchanged.

## GREEN

New regression only:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest tests/test_context_dataset.py::test_outer_projection_binds_each_opaque_receipt_by_named_mapping_without_decoding -q -p no:cacheprovider -W error::DeprecationWarning --basetemp=.pytest_tmp/task5-green-unit-01
```

Exact output (exit 0):

```text
.                                                                        [100%]
1 passed in 46.22s
```

Required focused suite; evaluator files were discovered with `rg --files tests`
as `tests/test_context_evaluator.py` and
`tests/test_context_evaluator_cli.py`:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest tests/test_context_dataset.py tests/test_context_runtime_semantics.py tests/test_context_runtime_capacity.py tests/test_context_evaluator.py tests/test_context_evaluator_cli.py -q -p no:cacheprovider -W error::DeprecationWarning --basetemp=.pytest_tmp/task5-green-focused-01
```

Exact final output (exit 0):

```text
.                  [100%]
262 passed, 9 skipped in 886.04s (0:14:46)
```

Explicit fail-closed boundary confirmation:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest tests/test_context_evaluator.py::test_corrupt_final_outer_index_is_rejected_before_opening "tests/test_context_evaluator.py::test_rehashed_report_is_not_evidence_for_modified_sources_or_metrics[code]" -q -p no:cacheprovider -W error::DeprecationWarning --basetemp=.pytest_tmp/task5-green-boundaries-01
```

Exact output (exit 0):

```text
..                                                                       [100%]
2 passed in 84.16s (0:01:24)
```

Thus malformed final outer bytes/index remain rejected before any durable
opening, and a rehashed evaluation carrying a mismatched
`context_models/dataset.py` implementation hash remains rejected. The full
focused dataset file also retained its separate invalid-byte/index coverage and
the new test proved the successful valid-receipt path without decoder calls.

## Self-review

- `git diff --check -- context_models/dataset.py tests/test_context_dataset.py`
  completed without whitespace errors (Git only printed the existing Windows
  autocrlf advisory; staging uses `git -c core.autocrlf=false`).
- The regression asserts runtime behavior and exact bound BLOB values, not SQL
  source text or mock behavior.
- The mutation check is direct: restoring tuple binding makes named bindings
  empty and reproduces RED; changing the bound mapping key/value also fails.
- No source-hash allowlist was edited. Normal evaluator implementation hashing
  is intentionally allowed to reflect the changed dataset source.

## Concerns and remaining ownership

- No local product-code or test concern remains in the Task 5 diff.
- The nine skips are the established platform/controller-fixture skips; they
  are not counted as passes.
- Per the brief, the controller owns the native Linux warning-as-error replay,
  actual immutable-input D4 compatibility confirmation, and final full suite.
  Those gates are not claimed by this Windows-focused Task 5 report.
- No push, VPS access, deployment, or full repository suite was performed.
