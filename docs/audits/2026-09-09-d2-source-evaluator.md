# D2: source-resolved offline dataset, evaluator and scoped approval

Date: 9 September 2026. Worktree base: `70d6ce1d8911e23465ac81726eb0aecd9f49d7a3`.
This is the bounded Task17 mechanism, not a real empirical model release.
No provider, runtime worker, UI, VPS, price, money or Cricket change is included.

## Status and exact ownership

New files only: `context_models/dataset.py`, `context_models/evaluator.py`,
`context_models/activation.py`, `scripts/evaluate_context_models.py`, the
`context_dataset_helpers.py` synthetic fixture and four associated test modules.
No existing B1 source normalizer, B2 fit, B3 approval/result contract, D1 replay,
paired scorer, registry, statistics helper, staged backup or privileged updater
was edited. No existing Python caller was found for the new public interfaces.

The complete approved specification, Task16/17, context/validation decisions,
corpus inventory and `task-17-evaluation-controller-rulings-20260909.md` were
read. The controller explicitly approved the dataset shape, failure-p=1 pass,
historical verifier interface and three subsequent integrity clarifications
documented below. No acceptance threshold was relaxed.

## Public boundaries

```python
prepare_dataset(path, experiment_hash, *, evaluated_at)
evaluate_experiment(path, experiment_hash, *, evaluated_at)
verify_evaluation(connection, report_hash)
verify_approval(connection, approval_hash)
approved_effect(path, *, effect_hash, event, features, base)
```

The evaluator consumes an A1 experiment reference to an actual A1/B1 dataset;
there is no public flat-results/loss-file, caller-verified or force substitute.
`evaluate_experiment` returns the immutable `context-evaluation-v1` envelope
and a list of eligible, separately persisted B3 approval envelopes. It never
publishes an active manifest. `approved_effect` returns exactly the existing
`{digest, kind: context-approval-v1, payload}` envelope, or `None` when absent
or inapplicable. Claimed corrupt evidence is an integrity error, not a scope
fallback. There is no synthetic 50-percent model or quote input.

`verify_approval(connection, approval_hash)` has no current-slot dependency,
does not open a database path and writes nothing. D4 can pass its already
verified read-only in-memory SQLite image. The active wrapper uses an existing
explicit trusted-path read transaction. This ordinary live read-only connection
is not the separate D4 sealed-stage verifier and does not claim to avoid SQLite
WAL/SHM behavior. D3 must resolve full historical evidence once per prepared
batch, outside CPU `compute_once`; full source/fit replay is not cheap per card.

## Actual storage and chronological replay

- Closed `context-dataset-v1` groups exactly cover frozen family configurations.
  The one full native identity map, ordered train/final case references, sorted
  physical B1 receipt pools and exact stored `context-fit-v1` are retained.
- Cases resolve existing A1 `context-training-case-v1` payloads and their
  original recipe, source hashes, global map, full Event/Base/FeatureVector,
  preprocessing and opaque owning outcome reference. All first-insertion and
  receipt clocks must precede the relevant owning case/fit/freeze boundary.
- Every family inventory is checked before any training/result body decoder.
  Native events cannot cross train/tune/final, even under another case hash.
  Final membership, decision, complete Event and contiguous block membership
  exactly match the pre-registered whole inventory.
- Training pools cannot contain a final event receipt or another event's label.
  A declared causal history cannot omit an already stored eligible revision for
  one of its native events. This is not a claim of complete league/provider
  history beyond the original declared replay recipe.
- The actual D1 assembler reconstructs train/tune rows. All five train-only
  alpha candidates, tuning scores, coefficients, scales, selected identity,
  exclusions and fit status are recomputed; complete canonical equality is
  required. One-ULP changes to an unused candidate or its tuning score fail.
- Only then does the existing registry durably open the entire fixed final
  inventory. The original opening survives all later failures and reruns.
  A second preparation plus evaluation runs in one writer transaction before
  immutable report insertion, preventing a source change during that step.
- Final cases use original source replay, source-normalized outcome, fitted
  effect and owning distribution scorer. Complete event market rows are
  appended atomically, not selectively after observing favorable targets.

The only `unavailable_final` reason currently accepted is the reproducible
`native_to_state_key_source_resolver_unavailable` Tennis replay capability.
It is derived from the exact population/Event and actual owning replay support;
the capability must still raise that exact reason. A caller's arbitrary
`provider_missing` or free missing-data flag cannot shrink the inventory.
No false Base/FeatureVector is fabricated for an unavailable case.

## Controller-approved integrity clarifications

### Physical/index check is label-free, not byte-unread

A new dataset-local preflight hashes opaque stored B1 BLOB bytes and verifies
content and receipt identities. Fixed SQLite JSON projections inspect only
the existing outer event/revision/source/subject/kind fields and outer keys,
then compare them with every receipt index. There is no Python `json.loads`
of final bodies, arbitrary JSON path, `payload.result` projection, bespoke
parser, owning result decoder or label logging in this preflight. SQLite JSON
capability is explicitly checked; absence fails rather than weakening checks.

Raw bytes are necessarily read to hash them, and SQLite parses JSON to project
the outer fields. The claim is **no final label inspection/use**, not no byte
access. Full canonical and semantic body validation remains the later owning
B1/source decoder. A forged event-key index can no longer hide a known native
correction outside the selected revision pool. A corrupt final outer index
fails before opening, while an invalid but physically intact result body fails
after opening and cannot erase the already-durable inventory.

### Original train/tune result revisions

For each eligible frozen training label, the evaluator audits actual terminal
receipts of the same native event/source/schema/scope only through its original
`train_end` or `tune_end`. A later or simultaneous differing normalized result
within that phase invalidates the stored fit before opening or any write.
Identical rechecks are harmless and their actual refs are retained. A receipt
after the original phase is not decoded by this audit and cannot retroactively
refit or replace an old label. D1's existing late-original-result exclusion is
preserved. The report separately records `training_outcome_revision_refs`.

### Opened final result revisions

After opening, the same audit is bounded by the report's original `evaluated_at`.
Same-source terminal corrections are compared by normalized terminal facts,
not different fetch hashes/timestamps. A same-time conflict or newer changed
result invalidates the frozen claim; no more favorable result is substituted.
Affected ready hypotheses retain their status and fail at p=1. The immutable
original outcome and actual consulted `outcome_revision_refs` remain recorded.
A correction first received after a historical report does not rewrite it.

## Statistics, report and active lookup

The existing paired cohort helper, exact common event/target intersection,
owning distribution loss, calibration, contiguous-block/HAC and whole-registry
BH formulas are unchanged. A numerical failure in a ready hypothesis adds an
explicit failure and sets its inferential p to 1 **before** rerunning BH across
every registered hypothesis. Raw metrics, their original inferential values,
all successful rows, exclusions and failed variants remain in the report.

The minimum 200 distinct native events, at least three test blocks, at least
2-percent relative Brier improvement, positive HAC lower bound, BH 5-percent
criterion and no-worse distribution/calibration policy remain unchanged.
Baseline controls and unsupported/nonready variants cannot gain approval.

The closed report binds the exact experiment/dataset/map, case/config/fit and
all candidate effect references, all declared and revision-audit receipts,
original opening, actual evaluation clock, full metrics and explicit failures.
It also hashes the implementation source files. Reverification replays the
original sources/fits/calculations and requires exact canonical report equality.
Rehashing a modified probability, metric, result status, receipt inventory or
opening/code claim is not sufficient. The report never contains its own hash
or a circular approval reference.

The existing closed B3 approval payload is unchanged. Historical verification
resolves the complete linked report and requires the exact policy-produced
approval, not a passed flag. Active lookup also requires an active actual effect,
matching approval/effect scope, evaluation and manifest publication before the
new decision, scheduled event, original Base version, feature version/coverage,
referenced consumed inputs and the owning full Event/Base reference identity.

## Offline CLI

Required: absolute `--model-db`, `--experiment`, absolute `--output-dir`.
No automatic data discovery, provider access, default production database or
active model publication. Configured production state input/output is refused.
Missing input never creates a database or report directory. The CLI uses the
actual UTC runner clock, limits an invocation to 10,000 stored case artifacts
(a resource bound, not an empirical threshold), and writes an immutable
digest-named canonical report file. Success says `evaluated_not_activated`.

## Test evidence and remaining boundaries

All source-backed mechanics tests use a real temporary SQLite A1/B1 database
with seven deliberately synthetic native-shaped football events, actual
source normalizers, 26 historical fixtures per case, actual feature/base replay
and actual five-alpha fitting. Only three final events span the three blocks;
these always produce **zero approvals**. No real historical corpus, new fetch,
native Tennis alias qualification or provider provenance was invented.

Separate 210-row CPU helper tests exercise multiplicity/failure math, not
source qualification. The active-scope positive unit tests explicitly replace
the historical verifier with a stand-in; they test scope routing only and do
not count as empirical approval. The CLI positive test runs the real offline
three-event evaluation under its explicitly synthetic fixture clock and checks
that no active slots appear.

Observed RED to GREEN evidence before final freeze:

- Dataset absent: 3 failed; actual replay implementation: 3 passed.
- Evaluator absent: 4 failed; activation absent: 3 failed.
- Final label smuggled into training pool: 1 failed, then 1 passed with decoder
  spy and original whole-inventory boundary preserved.
- Rehashed unused-alpha score/coefficient/status attacks remain rejected.
- Corrupted kind index hiding an omitted known correction: 1 failed plus
  3 controls passed; corrected focus: 5 passed.
- Changed event-key index hiding an omitted correction: 1 failed; combined
  fixed outer-projection/final-decoder/phase controls: 10 passed.
- Final terminal revision audit: 6 failed before implementation; seven actual
  SQLite before/equal/after/identical/historical controls passed afterwards.
- Original train/tune terminal revision audit: 4 failed and 4 controls passed;
  after implementation all 8 passed. Before/equal failures leave DB bytes and
  opening inventory unchanged; after-phase labels are guarded against decode.
- An earlier own combined run passed 39 tests; this predates the extra revision
  and scope regressions and is not the final acceptance count.

Final own focused runs: **62 passed** in 430.84s (`d2-own-green-03`), plus
**8 passed** in 60.09s (`d2-scope-cli-green-02`). Together these cover all 70
current own tests. The first scope-only test run had two fixture mistakes
(omitted preprocessing identity and treating dict coverage as a string); those
were corrected in the fixture, not by changing any runtime contract.

Frozen full integration: **4,093 passed, 18 skipped, 97 subtests passed** in
643.57s (`.pytest_tmp/d2-full-01`; JUnit: `.pytest_tmp/d2-full-01-report.xml`).
All nine source/test SHA256 identities below were rechecked unchanged after
that run. The skips were verified from JUnit: 13 unavailable Windows symlink
privilege cases and five POSIX owner/mode/umask cases. This is not Linux proof.
No existing tracked file changed. The exact invocation was:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/d2-full-01 --junitxml=.pytest_tmp/d2-full-01-report.xml
```

### Frozen SHA256 source/test identities

| File | SHA256 |
| --- | --- |
| `context_models/dataset.py` | `3b87304d86684bb0cae8e72b9cae6fe7f3fc5610e770b84b3a0568bb2b3e59e7` |
| `context_models/evaluator.py` | `b9fbb815f2cbccbb14055a23fa3da97d32dbec198053fca98fbb805a3607baa1` |
| `context_models/activation.py` | `887090c03a7107eb16946dd214a5ae7235b4e6cc3ea714a462c5c0e2f1ffd0c3` |
| `scripts/evaluate_context_models.py` | `ec46ccda1557e2e19744f8ed83ab5db2b87e6dd7344a699e8d063ee86683c120` |
| `tests/context_dataset_helpers.py` | `b26c961d81fc572814679ce9abc70583a00b1dcd8bb61c8193fd0a8f9b13a817` |
| `tests/test_context_dataset.py` | `e21a07a69e7554850fe8de8691cb3054181447ccd4c962155476b9a1d3fd9261` |
| `tests/test_context_evaluator.py` | `7289488c502abcfe246e75a768acca885e4a86ab5ad7e3097956009ce27cf38a` |
| `tests/test_context_activation.py` | `90f309c2c9df8785398ed71cb77007bc9387ffb854a62d5829fe9e3681860106` |
| `tests/test_context_evaluator_cli.py` | `dba1f8a94eac1bd4999711649d3a0d457cbce374b8cdb2ee490bb2ebac72b39e` |

### Explicitly still open

This packet proves local stored-byte, chronological workflow and computation
consistency. Hashes are not proof that provider data is true, that nobody has
seen a final result outside this process, or that an attacker controlling code
and all storage could not fabricate a fresh corpus. The declared 40-hex code
revision is bound to the experiment/recipe; exact implementation bytes are
checked separately, not authenticated against a remote Git host.

There is no real 200-event source-resolved successful approval, external archive
qualification, current provider-source expansion, D3 worker activation or
production publication in this worktree. Tennis's unresolved native state-key
source replay remains an explicit gap. Approved source versions cannot be
silently reinterpreted after future code changes: historical replay requires
the original source implementation, or an explicitly separate reviewed upgrade.
The report contains the existing frozen family/coverage cohorts and block
metrics, but not a new high-load/injury/confirmed-versus-uncertain drill-down
registry. Additional cohort thresholds, including any training-derived high-load
cut, must be pre-registered and source-replayed separately before those original
Task17 reporting bullets can be marked complete.
This evaluator alone is not a complete user-facing release or finished context
model rollout. Independent packet review and parent integration remain required.
