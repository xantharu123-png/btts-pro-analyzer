# Task8: football v3 detached-source parity — implementation report

Status: DONE for the bounded source/ownership prerequisite; 71 focused tests
passed with 0 failures, 0 errors and 0 skips. Not empirical qualification,
fit, activation, full-suite completion or production/UI acceptance.

Canonical worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013`.
HEAD remains `242093feda28a31bb8729e31529032ee059b570a`, with the reviewed
uncommitted POINT package preserved. No index, commit, root-checkout, API, VPS,
production-data or backup operation performed. No subagents were spawned.

## Owning implementation and approved scope adjustment

The initial real SQLite RED demonstrated two separate owning failures:

- `dataset.resolve_case` omitted player-history expansion and rejected a genuine
  national event as `joint case omits or adds a causal native revision`.
- Complete `verify_context_database` failed earlier at `_case_shape`: the joint
  ORIGINAL binding was treated as `context-base-replay-v1`, giving
  `resolved artifact has a different kind`.

The controller inspected and explicitly approved the fifth owner,
`context_runtime_semantics.py`, to dispatch known joint bases through their real
`joint_case_artifacts` contract. The original case creation clock, physical
receipt clock, preprocessing and outcome checks remain intact. Unknown bases
keep the previous strict raw-replay path. An orphan joint case remains explicitly
uncertified (`d1-case-owning-replay-unavailable`); it is not promoted to a verified
case or empirical approval.

Task8 changed-file manifest (only these implementation/test files):

| File | Change |
| --- | --- |
| `context_models/football_training.py` | Closed exact-version `joint_source_scope_kwargs` shared by all four callers; build uses it. |
| `football_joint_worker.py` | Worker uses the same dispatch. |
| `context_models/football_readiness.py` | D1 uses the same dispatch; later-v3 guard retained. |
| `context_models/dataset.py` | Detached D4 resolves the same complete v3 native pool. |
| `context_runtime_semantics.py` | Approved known-joint structural ownership dispatch. |
| `tests/test_football_v3_detached_scope.py` (new) | 26 real SQLite positive/negative owning-boundary tests. |

The dispatch accepts only the three exact existing feature-version strings.
v1/v2 use their prior defaults/kwargs; v3 passes `include_player_load=True` to the
existing whole-pool resolver. Non-string and unknown values fail closed. The
helper resides in an already evaluator-pinned source file, not a new unpinned
helper. No evaluator pin list, signature waiver, effect schema, default model,
numerical engine or fit recipe was changed.

Complete pools, source ordering, collection conflict/withdrawal law and earliest
terminal ownership are unchanged. The 4096-receipt / 4 MiB source caps and
64/128 MiB physical ledgers remain unchanged. The explicit
`player_load_requires_original_decision` guard survives in construction and D1.
An old nonexpanded postdecision proof is not treated as evidence for national
history.

## Actual proof and test design

The new tests exercise real source publication, actual ORIGINAL binding,
real detached `resolve_case`, and complete `verify_context_database`, not a
mocked argument or `assemble_training_cases` alone. Independently written
source inventory is target 9000 plus historical IDs 901000–901023 and national
event 777001. The national appearance for native player 1 is included exactly
once and appears in the v3 feature refs. Late, other-event outcome and unrelated
player sources remain excluded.

Full D4 rejects omitted negative receipts, omitted whole national pools, added
unrelated sources, malformed binding kind, rehashed mismatched binding event,
case-before-binding time and foreign outcome. Whole expanded pool admission is
rejected rather than truncated at count/byte boundaries. Tests also preserve
both known capture laws with v1/v2 nonexpanded sources, unknown-base strictness,
the genuine old later-decision guard and unique physical accounting.

The successful v3 fixture freezes a baseline-control plan with `fit_ref=None`,
no candidate and no final inventory. Full D4 verifies its source case/experiment
without creating effect, fit or approval artifacts; verification leaves SQLite
bytes unchanged. D1's single source-complete/feature-complete event is not a
200-event qualification: minimum remains 200, test events 0, qualification
`not_evaluated`. No numerical benefit is claimed.

## Executed QA, including failures and interrupted attempts

All completed pytest runs used Python `-B`, the provided offline launcher,
canonical workdir, `DJANGO_SETTINGS_MODULE=siteconfig.qa_settings`, canonical
portal `PYTHONPATH`, dedicated workspace TMP/TEMP and fresh unique basetemp.
The final selected run used the controller-authorized escalation only for owned
offline QA (known AppContainer hardlink restriction), not external access.
Commands with full paths and final exact selectors are in `commands.txt`.

| Evidence | Actual outcome |
| --- | --- |
| `red-detached.xml` / `.txt` | 2 failed in 41.77s; real omitted-pool and structural binding failures above. |
| `green-detached.xml` / `.txt` | 2 passed in 39.83s after the five owning fixes. |
| `green-boundaries.xml` / `green-boundaries-attempt.txt` | 6 passed, 14 setup errors in 31.84s; NOT a pass. |
| `green-boundaries-fixed.xml` / `.txt` | 20 passed in 74.75s after correcting the owning fixture. |
| `interrupted-expanded-command.txt` | Session 66977 interrupted with exit 1, no result; controller requested minimal nodes instead of broad 12-file/203-event duplication. |
| `interrupted-neighbor-command.txt` | Session 75563 interrupted with exit 1 before completion (24 progress dots); no pass claimed. |
| `final-owning-neighbors.xml` / `.txt` | Session 81002 exit 0; **71 passed in 262.22s**, 0 failures/errors/skips. |

The 14 setup errors were a new test-fixture error, not inherited baseline:
`ORIGINAL differs from executed code/model identity`. The eager two-law fixture
executed candidate law v2 while retaining the default v14 runtime fingerprint.
It now uses the established actual offline candidate execution pattern in
`test_football_joint_variant_binding.py`: temporarily select the literal v15
prediction version only while that candidate publisher executes, then restore
it. Actual ORIGINAL/code ownership, identity and evaluator pins were not weakened
or replaced with an arbitrary code dict. Failed JUnit and console evidence are
preserved unchanged. Final source hashes are recorded; no separate pre-fixture-
correction source snapshot is claimed.

The second interruption was scope/latency reduction. Its original association
with the no-new-backup rule was mistaken and the note was corrected: that rule
concerns production/user-data backups, not existing synthetic temp WAL
stage/restore tests. The controller's final full suite retains all baseline
tests, including that fixture, with no new skips/exclusions. Neither interrupted
attempt was restarted. The final already-selected command was allowed to finish.

Final JUnit breakdown:

- 26 new detached/D4 boundary tests;
- 10 existing decision-binding tests;
- 5 exact capture-law/config/candidate-owner tests;
- 20 selected real D4 semantics/schema/orphan checks;
- 2 whole-national-pool integration tests;
- 2 player-load terminal/conflict tests;
- 2 native-player collection withdrawal/conflict tests;
- 4 physical-ledger/admission tests (not the 203-event qualification fixture).

`git diff --check` passed; HEAD unchanged. A read-only manifest check initially
had a PowerShell empty-pipe parser error, then succeeded after assigning the
foreach output before formatting; no source change resulted. All 14 hashes in
the prior POINT/cache/shadow evidence match current files, including every frozen
POINT owner/test; saved in `frozen-point-verification.txt`.

## Evidence and handoff

Evidence directory: `C:/Projekt/BetBoy/output/context-completion-20261014/football-v3`.

- `implementation.patch`: scoped five-owner diff plus the new test file.
- `changed-file-manifest.txt`: full paths and SHA256 for all six owning files,
  patch, initial RED/fixture-error JUnit and final JUnit.
- `commands.txt`: completed offline command invocations and final exact nodes.
- All RED, failed-fixture, GREEN and interrupted evidence remains available.

Source-frozen complete regression, independent package review/integration,
shared index/commit, empirical fit/200-test qualification, activation and all
production/UI gates remain controller-owned/open. No such gate was dropped or
substituted by these 71 focused passes. Controller owns the progress ledger and
records the approved fifth-owner dispatch gap there.
