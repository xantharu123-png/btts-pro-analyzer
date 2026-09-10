# P4b3(a): shared Basketball / NHL baseline, no invented price boundary

2026-09-10. Owning branch `codex/kontext-p4b3-baseline-20260910`, based exactly
on `898652bbd2343cef6d67e8573f32c14b891f1057`. This is the controller-approved
**(a)** split from the frozen P4b3 preflight, not completion of **(b)** or the
whole context-model specification. Seven implementation/test files plus this
audit are the complete package. No provider request, SSH, VPS, push, main edit,
full suite, additional implementer or privileged action was performed.

The approved specification and owning B3/C2/C3/D3/D4/preflight decisions were
read during the preceding task stages. Existing work survived both account
continuations and the controller's temporary write pause. The root UI worktree,
its separate fixes, raw pinned helper, source adapters and model cores were
not edited here. Taskwise TDD and independent review remain the agreed workflow.

## Outcome and exact open boundary

The actual existing BB/NHL acquisition now precedes both consumer catalogs. One
actual `PrematchPrediction`, its unrounded winner pair and the actual existing
`EventModelSnapshot` supply the normal highest-probability winner and the
separately labelled RisikoBet underdog projection. Identical source duplicates
are removed **before** calculation; contradictory duplicate sporting inputs
fail. No target fit or prediction is repeated to build, filter, read or price
the new baseline view.

The **four unchanged original visibility/clock tests pass**. The **two unchanged
original B3-reference tests still fail** because `context_ref is None`. They are
not renamed, disabled, xfailed or claimed complete. Two missing references are
not equal verified contextual references. Package (b), its source/features and
owning D3/D4 replay plus durable history deduplication, remains open.

No new A1 artifact, B3 publication, empirical approval, player feed, rule/TOI/
goalie inference or quote gate was introduced. The existing registered native
status receipt type is the only new B1 data the existing requests may capture.
The normal research forecast remains visible with `probability_haircut=None`,
`conservative_probability=None`, `minimum_odds=None`; no zero haircut, invented
minimum or substitute probability is used. These rows cannot become TipStore,
15K or money candidates through the new surface path.

## Implementation and checked contracts

- `team_sports_baseline.py` owns the closed version-1 view and batch. The view
  contains actual event/source identity, source observation, original snapshot,
  complete actual prediction (including evaluation metadata) and digest. Exact
  post-prediction replay binds snapshot input hash/model version/cutoff to that
  prediction and event. The home/away complement retains its exact float bytes.
  Unknown keys, bad types, missing references between row/view/batch, divergent
  snapshot/probability/clock, and `context_ref=None` inserted as a claimed field
  fail. This is **lightweight consistency**, not a fresh fit, source proof or
  protection against a coherently rewritten whole JSON file.
- Batch validation covers **all** stored entries, including those with no
  current visible row. Status/error consistency, exact target-day membership
  in Europe/Zurich, unique event identities and real model/check clocks are
  checked. The existing `MAX_AUTOMATED_OTHER_CANDIDATES_PER_SPORT` envelope is
  reused; no global capacity limit was increased or original history deleted.
- The only change to `riskobet_candidates.py` extracts its existing tail after
  `predict_prematch` into a pure projection. Actual parent-commit execution
  confirms unchanged BB/NHL/Cricket snapshot/candidate dictionaries, IDs and
  floating-point outputs for the same inputs. Default source paths outside an
  active owning worker retain their previous behavior.
- `run_wettfinder` prepares actual default BB/NHL sources once even with Risk
  disabled. A completely acquired/committed source phase precedes the new
  decision clock. Targets already started after schedule acquisition do not
  consume history budget; targets that start during history acquisition do not
  get calculated. Actual receipt clocks after the claimed decision fail rather
  than being backdated. Existing Cricket cadence and the three old model-source
  and strict money-source contracts remain separate.
- Before publication, complete actual Risk snapshot **and candidate content**
  must match the captured views. A caller cannot discard/change the Risk batch
  while the normal catalog still claims the old shared result.
- Successful batches are reused for strictly less than six hours, independent
  of Risk on/off. At exactly six hours the existing source is called once.
  Latest owning native B1 status/identity is rechecked on reuse, without another
  HTTP request or fit. The same filtered entries feed both current catalogs.
  Absence of qualified native scope preserves the legacy original; known
  cancellation/start, ambiguous/incomplete participants or schedule conflicts
  cannot be treated as a fresh scheduled target. Future corrections are not
  consumed; simultaneous contradictory receipts withdraw the current view.
- The controller-approved failure fallback uses only a previously fully
  validated same-day batch. Its **view, source-observation, model/history
  cutoff and prediction bytes remain unchanged**. Only the failed attempt's
  batch metadata is new: `partial` / `source_failed`, still retry-due on the
  next worker. Both catalogs apply the current native status filter to that
  one old base. No old data are relabelled as newly modeled. Without a valid
  old view the batch remains failed/empty. The generic Risk store was not edited.
- The existing publication file lock now surrounds read/acquire/publish, with
  a per-path thread RLock in addition. Actual simultaneous workers and a
  separate nonblocking child-process lock attempt prove exclusion while the
  first real history loader is held. The child acquires the same lock after
  completion; the two workers produce one target calculation and one identical
  shared batch. Tests use events/queues and real file locking, not sleeps as
  concurrency evidence.
- `ev_signal_sources.py` adds only the explicitly versioned BB/NHL research
  null-boundary contract. `app.py` changes only the seven lines necessary to
  render such a card without calling price/decision/money actions. The actual
  app loop and action function are executed by AST extraction with real surface
  objects; this is **not** a browser or visual acceptance claim. Surface copy
  no longer says a heuristic haircut was computed when it was not. Existing
  priced/numeric cards retain their prior text and behavior.
- New card detail comes from actual model factors, limitations and team-history
  counts. Null/status/source availability is not turned into a favorable
  sporting argument. With no qualified BB/NHL quote provider, a free matching
  candidate ID is not accepted as a price binding. High/low arbitrary quotes,
  filters and rendering do not change the prediction, rank, boundary or scope.

## What is deliberately not solved

1. The normal winner and Risk underdog share a **legacy model revision**, not a
   certified contextual B3 revision. No injuries/fatigue effects are activated
   by this packet. Both original required-B3 witnesses remain RED below.
2. Warm `CompletedHistoryStore` rows are still baseline inputs, **not** newly
   observed B1 results. An actual warm SQLite test confirms unchanged database
   bytes and no A1 artifact publication. A separate explicit negative-boundary
   control shows a B1-only historical cancellation does not silently rewrite
   an unchanged legacy history row; full P4b2 history replacement/qualification
   belongs to (b). This is not a complete native historical correction pipeline.
3. Current receipts still do not qualify missing neutral venue, real season/
   rules, regulation/OT exposure, rotations, injuries, fatigue or goalies. No
   newer NHL season or EuroLeague alias is invented. Missing native metadata
   retains the actual baseline with RESEARCH/no context reference.
4. The new JSON view is a compact latest-worker projection, not a new durable
   original/history archive. The earlier measured full-original + full-base
   duplication remains 132,014 B BB / 126,090 B NHL (~129 / 123 KiB) per sample
   before other transport/database overhead. Package (b) must resolve this
   storage design under the unchanged 64-MiB restore bound. D4 and the trusted
   hook do not learn an unknown artifact or capability from this packet.
5. No live source availability, betting profitability, independent empirical
   quality, full-suite integration, browser visual quality, deployment or
   production scheduling is proved by these synthetic CPU/SQLite tests.

## TDD and focused verification

Every named XML remains in this worktree's ignored `.pytest_tmp`. No original
RED XML or source probe was overwritten. Exit-1 evidence remains negative.

| Run | Actual result and interpretation |
| --- | --- |
| `original-red-01` | Four setup errors: missing new temp parent, not product RED. |
| `original-red-02` | Four genuine original visibility/clock failures before implementation. |
| `added-red-01` | Ten own functional failures before the new branch. |
| `progress-01` | Ten failures from this implementation's wrong constant import; repaired. |
| `progress-02` | One own fixture URL/query error, seven passed; fixed fixture to actual response URL. |
| `ui-red-01` | Four real null-boundary surface/app failures, eight passed. |
| `focus-01` | Twelve passed. |
| `bindings-red-01` | Twelve real failures: duplicate computation, divergent Risk batch, unchecked inactive/future batch. |
| `bindings-green-01` | Twenty-four passed. |
| `legacy-focus-01` | One real old runtime-clock regression, 246 passed / 26 subtests; narrowed extra clock sampling to actual BB/NHL acquisition. |
| `clock-legacy-02` | 105 passed, including that unchanged clock test. |
| `lifecycle-red-01` | Twelve failures / 22 controls: stale reused native lifecycle and unnecessary history budget. |
| `lifecycle-green-01` | Two cancellations still failed / 137 passed because reused event projection omitted original scheduled status. |
| `lifecycle-green-02` | 139 passed after exact scheduled comparison was retained. |
| `consumer-adverse-01` | Two real misleading-copy failures; five own fixture errors (wrong table name / absent explicit observed clock), 32 controls passed. No production failures inferred from those fixture errors. |
| `own-legacy-green-01` | 344 passed / 26 subtests. |
| `complete-batch-red-01` | Eight genuine status/error/day consistency failures / 18 controls. |
| `final-focus-01` | 370 passed / 26 subtests. |
| `fallback-red-01` | Six genuine common failed-refresh fallback failures. |
| `final-focus-02` | **376 passed / 26 subtests, 15.52 s** (129 own tests plus 247 legacy focused tests). |
| `original-acceptance-final` | **4 passed / 10 deselected, 3.20 s**; unchanged original visibility and post-acquisition clocks. |
| `original-b3-open-final` | **2 failed / 12 deselected, 2.80 s**; unchanged absent-B3 requirement, deliberately still open. |

The focused command (use new basetemp/XML names on every rerun) was:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -p no:cacheprovider -o "pythonpath=. tests" tests/test_team_sports_baseline.py tests/test_wettfinder_automation.py tests/test_ev_signal_sources.py tests/test_wettfinder_surface.py tests/test_riskobet_candidates.py tests/test_riskobet_automation.py tests/test_sports_prematch_original_capture.py tests/test_completed_sports_history.py --basetemp=<NEW> --junitxml=<NEW>.xml -q
```

Original acceptance and open boundary, from this worktree, respectively:

```text
... -B -m pytest -p no:cacheprovider --rootdir=. -o "pythonpath=. tests" ../kontextmodell-20260907/.pytest_tmp/p4b3-worker-preflight-20260910/test_worker_seams.py -k "required_actual_worker_preserves_model or required_actual_worker_decision_not_before" --basetemp=<NEW> --junitxml=<NEW>.xml -q
... -B -m pytest -p no:cacheprovider --rootdir=. -o "pythonpath=. tests" ../kontextmodell-20260907/.pytest_tmp/p4b3-worker-preflight-20260910/test_worker_seams.py -k required_actual_worker_publishes_shared_context_reference --basetemp=<NEW> --junitxml=<NEW>.xml -q
```

The test corpus includes actual requests-to-scanner-to-existing-model-to-Risk
SQLite paths, real B1 normalizers/store and a real CompletedHistoryStore.
GETs are **synthetic native-shaped responses**, never live feed qualification.
The original witness profiles the real target fit and prediction code frames;
its 24 legitimate historical evaluation fits are retained, not suppressed.
The new parent-Gitshow comparison executes the actual base commit code, not a
manually copied substitute. `git diff --check` is clean.

## Frozen SHA256

Changed source and test bytes, before audit-only commit creation:

```text
66b6b4b9fac02a468a1a3c01d1fbaefcc2056417cd4491f5ea9c9d624123aed3 team_sports_baseline.py
6304452e570eb1634ece3f2d55d68f7eadd1411b79d89119cee37f37c3e91be7 tests/test_team_sports_baseline.py
df4ccb1175a654561b35eeb3d44df75e35f0a4215824a33e7f6e89ed2863bb4a wettfinder_automation.py
514d8f0fd734af350c73c04ccd215db5aacb47d439e430fa400cb493baac2dc6 riskobet_candidates.py
cb49d54afa7a5dec0ec4d41051b5913e167085712a7d53895fcfae5e3df37750 ev_signal_sources.py
a599879b07334587b5b7897980ad25e930bf361040b22c9998163ea1d6543a1f wettfinder_surface.py
fea9ed2f9f4b105b32a76e96213242d276f355a34ad834d469dcf371c17abc81 app.py
```

Unchanged original preflight/probe and key preserved evidence:

```text
9e11831ea49abdcea66205d951271331d6ddf3df5e0f14bc0fce39ec2f6facf2 ../kontextmodell-20260907/.pytest_tmp/p4b3-worker-preflight-20260910/PREFLIGHT.md
853783250150050c6029552a8d59efc0461c33b3c60c437cb8a55425ca6954be ../kontextmodell-20260907/.pytest_tmp/p4b3-worker-preflight-20260910/test_worker_seams.py
f9f28c4801ec50df632c79db2dc7c6b8a9afc11b481d5d710e19475503c146b8 .pytest_tmp/p4b3-original-red-02.xml
a3b6e3744965cb6788ca13a1f23cd17120ba9873ecbbce75892cd7640c02dd74 .pytest_tmp/p4b3-bindings-red-01.xml
7490361fc76790cb753d9ef5f6b96072dadaea9e1976e1ced8dab509fbc933c5 .pytest_tmp/p4b3-lifecycle-red-01.xml
cbba73e29813e07c06ed41a48b84c1338b19c0dd117fc882b606f4216fa84580 .pytest_tmp/p4b3-complete-batch-red-01.xml
19ebce585bdc1c5b0914f7d8c5c766da1a52dacc142b4dd4af978ce32b3bb139 .pytest_tmp/p4b3-fallback-red-01.xml
bf3500dc36cb96b5ae848892ac880c68e8804a9f276607992cdf6b5180daac9b .pytest_tmp/p4b3-final-focus-02.xml
518aede620d067973f0cc0414518a16e273fa4d52b4678abd3c14658d8f4572e .pytest_tmp/p4b3-original-acceptance-final.xml
87451d71ed02967c2d4977baf95e7f59f3bddf39866e92906eb0746231a4c928 .pytest_tmp/p4b3-original-b3-open-final.xml
```

Selected unchanged owning source boundaries (also empty Git diff):

```text
1d908a32d4decdd508477526af9802f3a81bd9054f93636e4df8c63675b9a07d sports_prematch.py
64d9324c2cb7296666018aadaa867ca601ce9cae32c52fc33b1a940a6dd30948 riskobet_store.py
7201d9d2596a7830485bb744407af9c8a35c5ecc422b0dd2a98c5acb1995c199 context_sources/team_sports_capture.py
1a11dab252f7a028171f0f85504b00ffce2d42f581f38920e6d7bfa11a4cbb2c context_sources/team_sports_status.py
204bf8e3f836a5ebbc2644ebf7da29afeab8a8ae8c0b8a53c09b62794faf08d9 context_sources/team_sports_binding.py
faa71900c0c22f78c4aaffc75c8a10e61d16a0077427f1274c915915ea36bc6d scanners/basketball_scanner.py
cf9b7354226f0192d4e3fb6d5324bebc86d4e8541ca3ab4a71fe620fbe7ad96a scanners/completed_history.py
dcb571b6aaef03a1e18638a8aedfd47841c1317d324f5c0561eab67da8646b8d context_models/team_sports_live.py
de9d8146917f568e1567cd8a92b92b64af1b33157f2afadf3c91c27a153de1da context_snapshots.py
a47d980a4e528ef12917db39e47d025c4670070737901f6e8c9688dfe84a1a9e context_transport.py
974917709b8e292b9621c6bef17112794a0724c4885f04f97052bde3799eab3e context_runtime.py
```

Source bytes are frozen for a different review agent. The audit hash and scoped
commit are reported separately to avoid self-referential hashes. Branch and
worktree are retained; integration and any wider verification belong to Root.
