# Task 10 Tennis relevance selector: bounded same-semantics query

Canonical checkout: `C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013`.
Brief: `task-10-tennis-selector-20261014-brief.md`, read completely.
Evidence: `C:/Projekt/BetBoy/output/context-completion-20261014/tennis-selector`.

## Owned scope and implementation

Only the first relevance-key query in `context_models/tennis_training.py` changed.
An explicitly MATERIALIZED CTE selects DISTINCT `(content_digest,event_key)`
after the existing ESPN/kind/causal receipt-cutoff predicates, before the
unchanged JSON tour/player/opponent/all-participant membership predicates and
INNER JOIN. The indexed event key remains in the relation: identical content
under a second corrupt event index must still cause selected validation failure.

The target event remains unconditionally in the key set. The second physical
LEFT JOIN selection, per-receipt B1 decode and native validation, prospective
provenance, tour check, complete chronological tuple, receipt order and error
propagation are unchanged. No physical deduplication, latest-wins reduction,
global/future readiness index, participant position shortcut or cache was added.

New owning test file: `tests/test_tennis_relevant_receipts.py` (35 collected
cases in final focused+neighbor selection). No existing test or other source
owner was edited. This report is the third file created/changed by this task.
Inherited dirty/untracked work was preserved; no commit or shared ledger edit.

## Genuine RED and fixture correction

The first attempted counting fixture incorrectly reused a native STATUS record
at a different reception clock. The real native validator rejected it with
`ContextIntegrityError: native competition reception identity differs`
(`red.log`). This was a fixture error, NOT the optimization RED symptom.
Its failed evidence is retained; no production validator was weakened.

Corrected fixture uses valid repeated normalized legacy workload content (two
player records), plus one native target status. A test-local SQLite scalar
instrumentation function counts calls and delegates every scalar extraction to
REAL native SQLite JSON on a separate local in-memory connection; json_each,
planning, selection and all physical/native validators remain real. All other
semantic cases use entirely unmodified native JSON functions. SQL tracing also
checks one discovery statement plus both physical event history reads.

Against the ACTUAL old `relevant_receipts` (owner SHA256 below), the corrected
test fails at 25 receptions with:

- tour JSON calls: 51, expected 3;
- player JSON calls: 51, expected 3;
- opponent JSON calls: 26, expected 2;
- all 51 physical source receipts returned before the assertion.

At one reception, 3/3/2 calls and 3 physical receipts already satisfy the bound.
Thus `red2.log` is a deterministic repeat seam on actual production code, not
an assumed baseline, timing gate, candidate-only comparison or mocked selector.
The subsequent optimized run satisfies the same 3/3/2 bound at BOTH reception
counts, while preserving all 3/51 physical receipts.

Before the production patch, the other 32 equivalence cases passed against
actual old code and the fixed PRECHANGE SQL oracle (`baseline.log`). The oracle
is a closed literal copy of the prechange query, not imported optimized SQL;
physical selection uses the unchanged real B1/native validators.

## Equivalence, integrity and neighboring evidence

Actual tuple/dictionary/provenance/order and canonical bytes are compared, not
only event IDs. Error comparisons include actual exception class, message,
SQLite error code and every explicit cause in the chain. Query-only transaction
state and total_changes remain unchanged.

Coverage includes repeated shared content, absent target history, exact cutoff
and postcutoff exclusion, exact native IDs and ATP/WTA namespace separation,
empty participant retraction, cross-player transfers and simultaneous conflicts,
all four participant positions, selected/unselected content hash corruption,
selected/unselected event/subject/schedule/clock index corruption, identical
content under multiple event indexes, selected/unselected unknown native schema,
eligible selected/unselected malformed JSON, filtered other-source/outcome-kind/
postcutoff malformed JSON, discovery INNER JOIN versus target physical LEFT JOIN
missing contents, selected cross-tour index corruption, and actual SQLite
interruption during BOTH membership discovery and physical source reading.
No synthetic future-only association was admitted into an old causal scope.

The evaluator pin test builds and evaluates an actual stored synthetic Tennis
inventory, verifies it using the current exact implementation manifest, then
stores a correctly rehashed report bearing the old selector source hash. The
existing evaluator rejects that report with its exact-source-proof error;
read-only verification does not alter the database. No source hash waiver,
allowlist, source-version bridge or evaluator modification was introduced.

Neighbors cover complete read-only live training history, later participant
removal/future exclusion, D1 omission rejection, actual dataset evaluation with
no empirical approval, explicit unavailable training exclusion, complete feature
inventory versus samples, disjoint bounded readiness ranges, own-versus-foreign
SQL interruption, and existing exact causal/reconstruction replay constraints.

## Actual commands and results

Every pytest invocation ran from the canonical checkout with this prefix:

```powershell
$qaRoot='C:\Projekt\BetBoy\output\context-completion-20261014\tennis-selector'
$env:DJANGO_SETTINGS_MODULE='siteconfig.qa_settings'
$env:PYTHONPATH='C:\Projekt\BetBoy\betboy-app\.worktrees\audit-repairs-20261013\portal'
```

For each run below, a NEW dedicated directory `<run>-temp` was created using
`New-Item -ItemType Directory -Path "$qaRoot\<run>-temp" -Force | Out-Null`,
then `TMP` and `TEMP` were BOTH set to that directory. The exact launcher was:

```powershell
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\Scripts\python.exe' -B 'C:\Projekt\BetBoy\output\context-audit-20261011\pytest_final.py' <selection> -q -p no:cacheprovider <additional flags> --basetemp="$qaRoot\<run>-pytest" *> "$qaRoot\<run>.log"
$qaCode=$LASTEXITCODE
Get-Content -LiteralPath "$qaRoot\<run>.log"
exit $qaCode
```

Exact executions (no hidden pytest flags):

1. `run=red`, selection
   `tests/test_tennis_relevant_receipts.py::test_repeated_membership_json_is_bounded_by_distinct_content_event_pairs`;
   no additional flags. Exit 1: 1 failed in 2.00s, invalid native status fixture.
2. `run=red2`, same selection/flags. Exit 1: 1 failed in 2.32s, genuine old-function
   repeat count 51/51/26 versus 3/3/2 (same old source hash).
3. `run=baseline`, selection `tests/test_tennis_relevant_receipts.py`, additional
   `-k 'not repeated_membership_json'` (placed before `-q`). Exit 0: 32 passed,
   1 explicitly deselected known RED seam in 0.60s; production still unchanged.
4. `run=green`, selection `tests/test_tennis_relevant_receipts.py`; no additional
   flags. Exit 0: 33 passed in 0.62s, initial optimized source.
5. `run=neighbors`, exact final selection below, additional
   `--junitxml="$qaRoot\neighbors.xml"`. Exit 0: 54 passed in 111.56s,
   zero failures/errors/skips. Includes the two final added cases.
6. `run=final`, SAME exact selection below, additional
   `--junitxml="$qaRoot\final.xml"`. Final source has the conditional comment
   "When receptions share content"; implementation semantics unchanged.
   Exit 0: 54 passed in 117.57s, zero failures/errors/skips. JUnit `final.xml`
   confirms 54 tests; log `final.log` is the complete console result.

Exact selection for executions 5 and 6 (all positional selectors in this order):

```text
tests/test_tennis_relevant_receipts.py
tests/test_tennis_live_training.py::test_builder_is_read_only_and_uses_complete_relevant_revisions
tests/test_tennis_live_training.py::test_later_revision_removing_player_is_kept_and_future_revision_is_not
tests/test_tennis_live_training.py::test_stored_dataset_rejects_omitted_or_added_history_before_fitting
tests/test_tennis_live_training.py::test_live_dataset_reaches_real_evaluation_but_small_synthetic_corpus_never_approves
tests/test_tennis_live_training.py::test_unavailable_context_is_preserved_as_an_explicit_training_exclusion
tests/test_context_readiness.py::test_complete_feature_inventory_does_not_confuse_a_sample_with_coverage
tests/test_context_readiness.py::test_complete_inventory_can_run_in_disjoint_bounded_ranges_without_faking_full_coverage
tests/test_context_readiness.py::test_sql_interrupt_is_a_timeout_only_when_this_diagnostic_cancelled_it
tests/test_context_replay.py
```

Runs 1-6 used the normal workspace sandbox; no os.link/AppContainer/temp error
recurred, so no escalation was needed. Offline launcher rejects external network.
No pytest failure was omitted. Read-only discovery commands had two harmless
unmatched Windows `rg` filename-glob diagnostics, missing pytest.ini, and denied
CIM process inventory; none changed tests/source/runtime or QA admission.

`git diff --check -- context_models/tennis_training.py`: exit 0.
Runtime check command:
`python.exe -B -c 'import sqlite3,sys; print(sys.version); print("SQLite="+sqlite3.sqlite_version)'`
using the exact QA interpreter above: Python 3.12.14, SQLite 3.53.1.
VPS SQLite 3.45.1 compatibility was supplied by the parent/brief's verified
read-only check, not independently probed by this implementer.

## Source hashes

- PRECHANGE `context_models/tennis_training.py`:
  `28a94651d30d1a226c14a349255b498fa2fd0c006af05925bc52e0e9fbb9cceb`.
- Initial GREEN / neighbors source (before conditional-comment correction):
  `39641da13e5cbef833bd945958485292c28adc5b84d600fad4cfc71158604ba2`.
- FINAL `context_models/tennis_training.py`:
  `5c34e547d68799bf6a443e005cff21441aaf6d945770abae3854bba683dbb8c1`.
- FINAL `tests/test_tennis_relevant_receipts.py`:
  `4356f42ddd4fb7aa039b4570fb86b6b1eacf828ddfbeb89ae6bd19b8ba630756`.

Hashes read with `Get-FileHash -Algorithm SHA256` from actual canonical files.

## Applicability limitation and remaining gates

The repeat-work RED proves the query seam ONLY WHEN multiple physical receptions
share identical content/event pairs. It does NOT establish that current native
polls share content. Native status competition_revision incorporates reception
clock; paired native workload normalization normally also uses the observed
clock as result_observed_at. Therefore repeated CURRENT native polls may produce
unique contents, making dedup inapplicable to the observed production timeout
and adding materialization overhead in that case. The actual production reuse
ratio and speedup remain UNKNOWN. The header-only 15s-interrupted diagnostic
does not prove either. Synthetic repeated legacy workload must not be reported
as real new-native throughput or a solved production bottleneck.

Parent owns the inclusion decision, one unchanged-budget read-only candidate SQL
diagnostic against the SAME four existing cases before deployment, complete final
regression, publication, and the identical four-case 45s installed-code probe.
No larger budget, alternate cohort, future coarse index or new architecture is
authorized by this package. Do not claim the real timeout fixed until that gate.

Not certified or performed: full suite, VPS feature probe, provider/API calls,
backup, migration, schema/index changes, source capture/pruning, persistent cache,
model law/fit/cohort changes, root edits, POINT/football edits, commit/push/deploy,
budget or active effect/approval change. No invented availability/fatigue
coefficients, test-event counts or numerical empirical effect; 200 qualified
untouched events, time blocks and all existing statistical gates remain unmet.

Await parent review; no further task work is authorized here.
