# P5b-A0: opt-in capture from the final football calculation

10 September 2026. Owning implementation packet; independent review pending.
Parent: `887cb4713d996d2f6efc8b70fbb4cc71e867f13d`.
Branch: `codex/kontext-p5b-a0-20260910`.
Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-p5b-a0-20260910`.

## Approved scope and actual result

The controller's complete A0 brief was read at
Root `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-18-football-final-original-a0-brief-20260910.md`,
SHA256 `babdd1e633d75fc765d0c768f9fc273d42257b68e0b97183f87c8a9084015a08`,
including the subsequently approved narrow parity-test accommodation. The full
preserved P5b preflight (`cafcac20...`), actual P5a/model/builder and both worker
paths, and the relevant approved B3/B4/B5 clauses were read directly.

Exactly 14 additive production lines across three files implement:

```python
scan_daily_challenge(..., *, ..., original_capture=None) -> dict
_default_football_scan(..., *, original_capture=None) -> dict
_run_market_scan_worker(..., progress_cb=None, *, original_capture=None) -> dict
```

An explicitly supplied callable reaches only the final `fixture_candidates =
build_fixture_candidates(...)` invocation. The callback receives the already
existing immutable `FootballOriginal` from the executed P5a calculation. It is
not reconstructed from rounded candidates. Invalid callback arguments raise
`ValueError` before provider/model work. Callback exceptions propagate through
the existing worker failure path, without a completed result. The source
observer's existing `finally` cleanup remains intact.

`None` or omission passes no `original_capture` keyword to the old lower call,
and causes no new clock, provenance, input capture or model call. An empty but
callable sink is still honored; truthiness is not used as permission. No new
imports, DTO, global recorder, return fields, model gates or price decisions.
Both worker dictionary return shapes and manual positional arguments remain
unchanged. This is an opt-in seam, **not default production capture**.

No formula, calibration law, P5a payload, immutable 15K signature, ticket,
candidate ID, source budget, B1/A1/B3/D4 schema, deployment script or protected
stage helper was changed. The isolated checkout was created with
`git -c core.autocrlf=false worktree add ... 887cb47`. No install, live request,
VPS, push or full repository suite was performed.

## What the permanent tests actually execute

`tests/test_football_final_original_a0.py` contains **64 cases**. The primary
six scanner/automatic/manual x domestic/UEFA cases execute the real scanner,
real provider observer, existing P5a model and calibration functions, and real
temporary B1 SQLite persistence. HTTP responses, cached history/calibration
inputs and clocks are synthetic. No real source/fit adequacy is claimed.
An unexpected alternate HTTP path fails the test instead of reaching a server.

Expected worker functions are compiled from their actual `887cb47` Git blobs,
with the unchanged real dependencies. Comparisons retain the complete return
dictionary, ordering, IDs, eligibility and float hex values. A Python code-object
profile observes executed model, matrix, market-law, calibrator, provenance,
capture and clock calls, including aliases; expected final values come from
the actual parent calculation, not a reimplementation or rounded card.

Confirmed by these tests:

- Domestic: one original and one goal-model invocation. UEFA: four existing
  goal-model invocations (feasibility/fallback/probe/final), but exactly one
  original and one provenance/capture clock. No new model or calibrator call.
- The same five existing football HTTP calls, cached-history requests and
  manual price-loader invocation count are retained before/after. The manual
  price loader is an explicit external seam and runs after source cleanup.
- All 90 final unrounded calibrated triplets, raw triplets, active goal rates,
  original count rates and UEFA conservative source recipes are preserved.
  They are not relabeled as a new coherent joint distribution.
- Actual original capture clock is between the prior source receipts and the
  later injury receipt; logical kickoff remains separately stored. B1 contains
  24 lineup/bench rows and genuine per-receipt clocks from the synthetic response,
  never fabricated publication timestamps.
- No-model cases emit no original. Existing duplicate-fixture handling executes
  only one final calculation. Incomplete lineup evidence does not exclude the
  otherwise computed original or turn unresolved provenance into a verified join.
- Default and explicit `None` retain old explicit injected callable signatures.
  The 15K-default snapshot remains exact parent output and uncaptured.
- An actual background `scan_jobs` thread receiving a broken original sink ends
  in `error`, has no `result`, and writes no completed manual audit. Direct
  automatic/scanner failures also propagate; no unavailable/completed relabeling.
- Existing manual audit and automatic state projections contain no large original
  histories. The real automatic `write_state` is exercised against a temporary
  JSON file. No original payload is inserted into any returned worker dictionary.

## Exact parent-parity accommodation

The prior P5a whole-`challenge_15k.py` AST check accepted only its original
conservative-closure replacement. It correctly rejected this newly approved
scanner addition before its narrow update (see run 04).

Only four lines were added to that test. `strip_exact_a0_additions` first asserts
the exact last keyword-only parameter/default, first early callable guard and
single conditional keyword spread on the named **final assignment**, then
removes those three known additions. The full original module/parent/closure
comparison still runs. The old parent revision and engine assertions are unchanged.

New tests independently compare all three whole modules against `887cb47` after
this exact removal. Nine mutation cases reject an unrelated statement, changed
guard and relocated forwarding assignment. No entire function or unknown node
is discarded to make the comparison green.

## RED/GREEN ledger and preserved harness mistakes

All invocations use the existing quality Python and `-B -m pytest -q`
`-p no:cacheprovider -o 'pythonpath=. tests'`, unique `.pytest_tmp` basetemps
and JUnit files. No generated or original evidence was overwritten.

| Run | Actual result | Meaning |
| --- | --- | --- |
| `p5b-a0-baseline-01` | 62 passed, 39 setup errors, 6.93s | Missing `.pytest_tmp` parent in a fresh worktree; not a product RED. |
| `p5b-a0-baseline-02` | 101 passed, 7.91s | Corrected environment, unchanged parent source. |
| `p5b-a0-red-03` | 43 failed, 4 passed, 11.05s | Actual missing optional APIs/keyword-only contract; source not yet changed. Original test bytes retained. |
| `p5b-a0-first-green-04` | 4 failed, 44 passed, 70.13s | Three invalid synthetic UEFA setups plus old whole-module AST accommodation witness. |
| `p5b-a0-green-05` | 85 passed, 48.58s | Correct UEFA setup, original assertions retained; owning cases plus old P5a parity. |
| `p5b-a0-focus-06` | 558 passed, 32 subtests, 95.02s | Final 64 A0 cases and targeted existing suites; zero skips. |
| `p5b-a0-original-preflight-07` | 2 failed, 10 passed, 5.41s | Unchanged original P5b default-capture/B3 witnesses remain honestly open. |

Run 04's UEFA fixture mistakenly supplied an **empty** league history, which
cannot produce a goal rate even with a domestic team history. Parent and current
scans both correctly made only two source calls. The synthetic cache was corrected
to provide a full unrelated league-rate history, preserving the intended missing
target-team series and real UEFA fallback/probe path. Assertions were not weakened;
production code did not change. The initial test source and XML remain available.

The intentionally failing old whole-module AST comparison also produces a large
pytest diff. A scoped process-status diagnostic was denied by Windows; no escalation
or process termination was performed. A later interrupt/poll returned the completed
normal Exit1 result and intact XML. This is test-harness evidence, not an app failure.

Run 06 covers A0, P5a capture/parity, football capture/results, `challenge_15k`,
automatic Wettfinder, market scope, workflow integrity and scan jobs. It is not
the full repository or independent reviewer result.

## Original P5b boundaries remain open

The Root preflight and all original probes were byte-checked and re-executed
**without adding the new sink to them**. Default production still has no owning
original recipient and no new B3 snapshot publication. CANC/1H native withdrawal
capture is still absent; current legacy detail reconciliation remains separate.
No historic native roster exposure, exact fatigue timing, trained player impact,
empirical 200-event approval or injury/load application was created by A0.

Durable publication requires the separately closed calibrated live-original
type, actual native event/source and distinct original/context clocks, plus its
own D4 reader/restore. Raw zero-effect B5 must not replace the calibrated legacy
marginal. The next worker can supply the new local sink after those contracts;
silently recording and discarding a default batch is deliberately not implemented.

## Frozen source and evidence hashes

Raw SHA256 (not a cross-platform text-normalization claim):

```text
f230ed87b5f10777d95f59a55542bd0b568baf0e64b74ddeba483545609e78b2 challenge_15k.py
76e647b32d8c98a132e9b4ffad9440ec77e089b4a8b6a506e2cd49bc989b0fca wettfinder_automation.py
dd7b5dc2e1be49c94b79885715587bb49c94b9cac80e9ed4d523cc2eea436676 alternative_markets_tab_extended.py
d5c7facb7c78a52e814b8dff6ea27d556e34db86ebfafdd089003faed822d4ce tests/test_football_final_original_a0.py
b73e36d0572677a3be4b7f2fd2bdb23c42db133ce77c5b859181a0372f13469e tests/test_football_original_parity.py
1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026 scripts/stage_runtime_databases.py (unchanged)
9e3b35cc9c0aba5f611d334336beaccfd4e885b280d9173dd98dcd7c6740922e challenge_engine.py (unchanged)
138fbe5a6570995e7274741dde84e2d4ea1a9cedb7efbaecb2856d91be88af1d football_original.py (unchanged)
```

Own worktree evidence under `.pytest_tmp`:

```text
7421524545aa50aaa349436f1183ac3e5777fe9d8f9f0da688d1a3bc2f80425c p5b-a0-baseline-01.xml
96933e7d0b9ef1e5d78b2e3027b21f06c0623567d9b40ec1eb60dd5882d84707 p5b-a0-baseline-02.xml
9e8a7ecc16ccfd37ba8b47abf829bef110f63dcb762d376c1766adbb521ea287 p5b-a0-red-03.xml
b50e68fb1260488662c18b4a3c29268980caf3490ec2a91b4bcc5244d45969b3 p5b-a0-original-red-03.py
092a2547e321130ae7c19cd16af8e594939ee6d7637a9a9ef6f130cf7a871bd7 p5b-a0-first-green-04.xml
02dd0bb90d9e7c4c1cd31586f95c9827ba72c649df690e9e966d893249ad5475 p5b-a0-green-05.xml
8734e2ae519dc138e0bf88a8eb315ff1dcd24c4e9493f74325e6ac2455a2133d p5b-a0-focus-06.xml
d420a6528e476657a2c796d88c2bf0d3af6f71681de4faf6a1bd92f84f6b2d7f p5b-a0-original-preflight-07.xml
```

Root original evidence under `.pytest_tmp/p5b-preflight-20260910` (unchanged):

```text
cafcac20acaf6815f1b44343ee323efa7276bc1af5bd4870d54d81e8e947643a PREFLIGHT.md
10b6b99278bac5cf00d72fcce6463896253f626d939a926304f42e1c3cdb0c58 test_p5b_missing_connection.py
8632728a677ca13a85c109b33b0eb3a3ea81bfd4df304892286fdfd4b1fec737 test_p5b_qualified_connection.py
72f8eef13df36f552111a5a7cae0d84da1129070f258b3eb9bef530576b1b97b test_p5b_source_boundaries.py
```

Branch/worktree will be retained with a focused commit for controller-dispatched
read-only independent review. No merge, deployment or larger P5b completion is
authorized or claimed by this packet.
