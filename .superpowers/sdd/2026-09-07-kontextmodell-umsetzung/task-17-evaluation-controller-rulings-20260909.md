# D1/D2 owning dataset and evaluator seam — controller, 9 September 2026

The approved source/case/fit, freeze/open, paired cohort and approval contracts
remain authoritative. The controller read the complete current D1 case/fit
implementation, Task16/17, registry and validation decisions. This clarification
does not change any quality threshold, permit backdating or prove real data.
It is not yet an implemented or independently reviewed dataset/evaluator packet.

## Free loss rows are not activation evidence

`compare_registered_losses` remains a pure CPU helper. Its synthetic/free result
rows cannot become the public empirical authority merely by placing them in a
JSON file. The owning `evaluate_experiment` must resolve the actual frozen D1
case inventory, reconstruct original features/bases and fitted candidates,
compute market targets and owning distribution losses itself, then use that
helper. A CLI loss file, if retained for audit compatibility, is only an exact
equality assertion against those recomputed rows; never a substitute source.
No `force`, caller `verified`, free coefficients or caller `passed` path.

## One A1 dataset; no second storage subsystem

Use immutable A1 `context-dataset-v1`, with closed payload:

```
schema = 1
event_identity_hash = full global native identity map artifact hash
groups = ordered list of {
  family_config_hash,
  training_cases: ordered list of {case_ref, observation_refs},
  final_cases: ordered list of {case_ref, observation_refs},
  unavailable_final: ordered list of {event_key, decision_at, reason},
  fit_ref
}
```

Groups are sorted by unique family-config hash and exactly cover the experiment
configs. Case refs resolve existing `context-training-case-v1` payloads, never
free event/base/feature substitutes. Observation refs are sorted unique actual
B1 receipt digests and resolve the entire declared causal revision pool plus
the one owning result. No duplicate case/event within one family. The case
already names its replay, global map, preprocessing and own outcome; each is
resolved from A1/B1, not from an unverified external envelope. All hashes retain
their owning kind/payload/content conventions. No raw provider credentials,
prices or separate private source database copied into the artifact.

`fit_ref` resolves immutable A1 `context-fit-v1`, containing the exact closed
D1 FitResult. It is required when that config has a non-control hypothesis;
null is allowed only for a baseline-control-only config. Each non-control
hypothesis must match the actual fit status and selected effect: fitted maps
to ready; fit_failed/unsupported/insufficient_data stay exact. Control entries
do not inherit or activate a fitted effect. Ablation changes need the actual
owning config/feature change, not just a success-dependent label.

Training cases have decisions strictly before tune_end; final cases have their
exact original Event/decision/block in the frozen unlabeled test inventory.
No native event may cross train/tune/final anywhere in the dataset's families.
For each config, final cases plus explicitly unavailable_final entries exactly
partition all matching frozen events, once each. A missing field/case is not an
implicit exclusion. Unavailable reasons are limited to actual pretest input
unavailability, not unfavorable predictions, outcomes or prices; persist them
before opening. They do not create fake valid Base/FeatureVector objects.

Opaque final case/result references may already exist before evaluation. Header
validation may read the closed case payload (Event/Base/features and opaque
refs) but must not resolve a final outcome body before whole-inventory opening.
As with the existing registry, this is a local workflow guard, not proof nobody
has inspected a result outside this process. Actual first A1 creation times
and source receipt times stay unchanged; dataset/fit/effects must predate the
frozen experiment's creation and cannot be added after its opening.

## Full recomputation and failed-ready semantics

1. Load/hash-check the experiment, dataset, config/global identity, fit and all
   label-free case headers. Check their exact inventories and actual A1 clocks.
   Guard all train/final decision boundaries before any source/outcome lookup.
2. Resolve only train/tune cases, rebuild rows through the one D1 assembler,
   rerun all five train-only alphas and full tuning evaluation, and compare the
   complete FitResult/candidate identities with their stored versions. Do not
   silently substitute new coefficients or numerical tolerances. A backend
   reproducibility gap is a reported gap until separately resolved.
3. Persist/open the entire already-frozen final inventory with the existing
   `open_test_inventory` before resolving final source/result payloads. Exact
   reruns retain its first clock; failure retains the opening record.
4. Resolve each final case and receipt pool through owning D1. Its native
   identity, original full Event/Base/FeatureVector, config, replay source
   hashes, outcome contract and actual result receipt at/before evaluated_at
   must match. Derive targets with `case_market_targets`; calculate each
   candidate from original parameters; score with the owning distribution law.
5. Retain every declared case/hypothesis and every explicit exclusion/failure.
   Missing causal context may exclude a case with the owning reason. A ready
   numerical/prediction/scoring failure must additionally fail that hypothesis
   and set its inferential p=1 before the joint BH pass. It cannot become a
   harmless favorable coverage subset or a new pretest unsupported label.
6. Use the exact comparable ready intersections for Brier, distribution,
   calibration and block counts. Store their full metrics and input identities.
   Reuse unchanged policy constants and statistical formulas. No empirical
   approval from less than200 unique events or synthetic mechanics fixtures.

The exact public evaluator/CLI argument transport may replace the insufficient
old flat-loss sketch with the above dataset reference. Record this interface
clarification and caller search; do not create two competing evaluators. The
CLI remains explicit-path, bounded, offline research; no default production
data writes or active manifest publication.

## Immutable report and later resolver

Use `context-evaluation-v1` for a closed full report that binds experiment,
dataset, global identity, all config/fit/effect/case/observation identities,
original opening, actual evaluated_at, computed price-free losses, complete
paired/calibration/block/cohort/multiplicity results and explicit exclusions.
No report may refer to its own hash or to an approval that in turn contains
that report hash. Construct report first; approvals are separate A1 artifacts
using the already approved closed payload and unchanged scope rules.

`approved_effect` resolves actual active `context-approval:<effect_hash>`, the
linked report, experiment, dataset and effect; verifies their exact immutable
bindings and recomputes policy decisions, never trusts a passed flag. Pure
statistical reports or unknown kinds cannot be promoted. The resolver must
check the current event/base/feature scope and evaluation-before-decision.
Missing/inapplicable approval returns no new effect while preserving the normal
baseline. Corruption/mismatched claimed evidence is an integrity error.

Historical receipts, reports, predictions, snapshots, tickets and settlements
remain immutable. Publication is a separate exact-hash manifest operation
after verification. Existing reports do not automatically migrate to a newer
source implementation or gain a different sport/market/coverage certification.
