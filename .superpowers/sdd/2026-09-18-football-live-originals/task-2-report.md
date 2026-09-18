# Task 2 — same-call native ORIGINAL publication

Status: implementation and affected verification complete, ready for root independent review. Automatic-worker ownership was released after bridge re-review; hooks and closed serializers are integrated. No activation, deployment, empirical approval or final broad-suite claim.

BASE: `5ff08a9605bb46835a7d86d5f6e2da1b74120852` (recorded before edits). Integration parent is `a322430` after independently reviewed bridge commits. Other agents' commits and WIP are preserved. Root explicitly granted this worker the scoped index after wrapper ownership release.

## Core API and authority

- `capture_football_worker(provider, path=..., baseline_enabled=False)` retains the default-disabled acquisition behavior. The opt-in source observer validates domestic `{team,last,status,timezone}` responses; it never issues a provider call.
- `_Capture.flush_baseline_receipts(tuple_of_actual_input_fixtures, max_new_payload_bytes=N)` retains original response clocks and every received matching native-event revision, before score matching. It returns exact per-input-record references, not a database search. Each processed fixture's baseline and other legitimate carried context/outcome observations are one bounded append; those observations are not discarded by marking it processed. CSV is unlinked. Same-worker domestic cache reads reuse the original observed response; outside-worker unlinked cache reads stay unavailable.
- `append_bounded_observation_batch` charges new unique content BLOBs AND canonical new receipt metadata inside its serialized writer. Repeated same content at a new observation clock costs receipt bytes. Exact retry costs zero. These are payload/metadata accounting units, not physical SQLite bytes.
- `freeze_named_receipts(path, tuple_of_unique_digests)` freezes only named rows in one read-only transaction, then verifies owning B1 hashes/indexes/clocks after release. Missing names/corruption fail integrity; empty references remain missing coverage. No B1 full inventory or source/kind prefilter.
- `FootballOriginalPublication(path, capture, max_publication_payload_bytes=N, max_worker_payload_bytes=N, max_source_payload_bytes=N)` requires finite nonnegative integer budgets. No implicit operational default exists. `freeze(input_scope)` precedes `model_kwargs(decision_at=actual_clock)`; these kwargs provide the selected-baseline-union resolver and same-call callback. No second model/matrix/calibrator invocation.
- The engine resolver receives only the exact unique selected union (target, scored league priors and selected venue/form series). Direct native provenance is still supported; both transports together are rejected. Named integrity errors escape the unavailable-provenance fallback.
- Publication stores the unchanged owning ORIGINAL-v2 via Task-1 preparation/publication APIs, a new versioned execution fingerprint and the closed B1 binding under one outer `BEGIN IMMEDIATE`. Selected named dependencies and actual artifact readback, including the complete ORIGINAL graph, verify before one commit. A late binding-trigger failure leaves no orphan original. Worker allowance decreases only after commit.
- The executed-code artifact records exact owner source-file SHAs separately from hashes of loaded Python executable bindings/defaults, numeric constants/tables and Python/NumPy/SciPy identities. It is explicitly `execution-fingerprint-not-replay-qualification`, not a transitive replay bundle. Recording source and loaded hashes does not claim that current disk source reproduces loaded objects. The old raw-law replay `_recipe` rejects this new artifact kind.
- Binding/report distinguish `source_state`, `code_state=execution-fingerprint-only`, and `empirical_state=not-evaluated`. `captured` means storage/source linkage only. Original bytes retain their own unchanged source declaration.
- `scan_daily_challenge(..., original_publication=session)` freezes after acquisition and only attaches the callback to the final model loop, not preliminary probes. `refresh_fixture_models(..., original_publication=session)` explicitly forwards through the nested scan; wrapper `__getattr__` is not observer ownership.
- `_default_football_scan(..., original_capture_limits=None)` and `_default_football_context_refresh(..., recompute_models=True, original_capture_limits=None)` own the real provider capture before any detail/history acquisition. Only explicit closed limits instantiate the session; no configured production caller is enabled. Context-only refresh ignores capture limits and publishes no ORIGINAL. Existing price/render/probe paths receive no session. Closed metadata survives discovery serialization and refresh merging.
- Computable legacy histories that cannot form native provenance (including naive timestamps) retain exact forecasts with an explicit `unavailable` capture status and no artifact, rather than treating missing source linkage as corruption.

## RED evidence

Executable used throughout: `C:/Projekt/BetBoy/betboy-app/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider` from the approved worktree. Initial sandbox process/patch startup failed with Windows deny-read ACL errors; read/test commands were escalated. Edits remained apply_patch-based, using the native `codex.exe --codex-run-as-apply-patch` entrypoint after its batch wrapper lost multiline arguments. No global Git configuration was changed.

Focused RED runs in `tests/test_football_original_publication.py` demonstrated:

1. 2 failures: real provider responses had no pre-exit baseline flush and no exact named receipt reader.
2. Missing `native_resolver` forwarding, then actual selected union duplicated 36 venue/form rows (165 versus 129 unique records).
3. Missing atomic publisher; later zero-budget same-body/new-clock source receipt incorrectly inserted a free metadata row.
4. Missing opt-in domestic response path and lost carried nonbaseline observations after baseline marking.
5. Missing explicit refresh session forwarding.
6. Missing distinct source/code/empirical states.
7. Real SQLite trigger changing a previously inserted ORIGINAL dependency's creation clock after binding insertion incorrectly committed.
8. A different ORIGINAL target could incorrectly reuse the selected-record callback state.
9. An unsupported native source projection raised instead of remaining partial.

Each was followed by focused GREEN before proceeding. Additional real SQLite regression tests cover correction/tie/late source authority, CSV/unlinked cache, decode after snapshot release, exact named queries, zero/aggregate budgets, idempotence and concurrent retry, corruption rollback, old replay rejection, and actual domestic cache HTTP counts.

## GREEN evidence

Final combined affected command: `tests/test_football_original_publication.py tests/test_context_football_capture.py tests/test_context_football_result_capture.py tests/test_wettfinder_automation.py tests/test_football_original_capture.py tests/test_football_original_storage.py tests/test_football_native_context.py tests/test_football_base_provenance.py tests/test_football_original_parity.py tests/test_challenge_15k.py tests/test_model_artifacts.py -q`: **590 passed, 4 skipped, 32 subtests passed in 35.08s**. This is not the root's final broad suite. `git diff --check` passed (only normal CRLF notices).

- `tests/test_football_original_publication.py`: 31 tests included in the final affected run (earlier core-only run: **26 passed in 6.86s**).
- New publisher plus `tests/test_context_football_capture.py tests/test_context_football_result_capture.py`: earlier **90 passed in 4.76s**; later core changes will be included in final affected rerun.
- New publisher plus `tests/test_football_original_capture.py tests/test_football_original_storage.py tests/test_football_native_context.py tests/test_football_base_provenance.py`: earlier **209 passed in 19.28s**.
- `tests/test_football_original_parity.py tests/test_challenge_15k.py`: **174 passed, 32 subtests passed in 12.44s**.

## Synthetic storage/CPU measurement

Real temporary SQLite, existing 380-row fixture, current ORIGINAL-v2, unlinked synthetic source rows. No real daily throughput/source qualification. Measured again after adding the source/capture owner identity fields:

| Metric | Goals | Goals + corners + yellow |
| --- | ---: | ---: |
| Expanded owning ORIGINAL bytes | 952331 | 1165291 |
| Initial newly inserted total payload bytes | 540227 | 753187 |
| Code fingerprint bytes (included above) | 115959 | 115959 |
| B1 binding bytes (included above) | 67837 | 67837 |
| Initial SQLite growth bytes | 548864 | 757760 |
| Changed-clock repeat payload bytes | 68108 | 68108 |
| Changed-clock repeat SQLite growth | 69632 | 69632 |
| Initial measured CPU/wall seconds | 0.371 | 0.507 |
| Repeat measured CPU/wall seconds | 0.373 | 0.461 |

The original transport itself still adds only its 271-byte new manifest. The concrete per-decision binding repeats the selected record-to-reference/unresolved map (~68 KiB here). Root explicitly retained this concrete design for Task 2 instead of adding a new deduplicated mapping artifact. All overhead is charged. No operational budget was selected from this synthetic result. Source clocks/contents are absent in this measurement, so this is not the full real B1/source family daily growth.

## Remaining limits / handoff

- Automatic worker hooks and scan/refresh serializer forwarding are complete; their explicit opt-in is available for later operational qualification only. Production scheduling/configuration remains unchanged and default OFF.
- Existing unprocessed prior-result watching still has its separately owned legacy full-history watch scan; this implementation does not claim that entire legacy worker is inventory-free. Processed baseline fixtures do not repeat it. No explicit prior-watch reference migration was attempted.
- Automatic-worker tests cover real source receipt capture and ORIGINAL publication, ownership, scan/model-refresh/context-only distinction, source clocks and one HTTP request, plus actual scan serializer and refresh merge metadata. Exact source/model call parity and disabled capture are covered by affected owning tests. No browser/device/release claim follows from these tests.
- A complete arbitrary transitive runtime/replay bundle, learned football effect, causal training qualification and untouched holdout evaluation are not provided by the execution fingerprint or capture.
- Task 3 production activation remains OFF pending measured operational throughput, source growth, backup/restore and capacity/reserve qualification. No production DB, network/VPS, money/price contract or Cricket changes.
- Root owns independent review, final broad suite, shared index and push.
