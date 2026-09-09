# D1 preflight: split review and proposed closed input boundaries

Date: 2026-09-09. Reviewer: `/root/worker_failures_20260909`.
Root HEAD: `4672c6a594d599143cf89115406daf63d13055a6` plus the two
untracked split files. READ-ONLY source review; only independent tests and
this note were created under `.pytest_tmp`. No provider, VPS, production DB,
source edit, commit, push, fitted model, or activation.

## 1. Split mechanics: approved

No new actionable finding reproduced within the declared normalized-input
split boundary. All heads of a native event retain one decision/split. Late
fitting results cannot migrate into tuning. Canonical UTC/half-open windows,
contiguous final blocks, duplicate-head rejection and detached output hold.
`block` remains an audited incoming label, not the computed split authority.
Source/alias verification and final evaluation time are explicitly outside
this pure function and remain mandatory at assembly/evaluation boundaries.

Fresh own runs:

- `d1-worker-preflight-focus-01`: **151 passed in 0.25 s** (new split tests + B1).
- `d1-worker-preflight-attacks-01`: **13 passed in 0.11 s** (independent cases).

Both use the trusted quality Python with `-B -m pytest -q -p no:cacheprovider`
and a new `.pytest_tmp/<run>` basetemp. New attacks include equivalent timezone
instants, every input permutation, nested mutation isolation, late train labels
known at tune_end, arbitrary incoming block labels, excluded malformed rows,
and different decision revisions hidden behind a coverage change.

Frozen hashes, checked before/after:

| File | SHA256 |
| --- | --- |
| context_models/training.py | 63ee69f7f3525bc51b97ba29e87d6dfab1de027e23b237366688047c43d3fc33 |
| tests/test_context_training.py | 203c403ebe5679b617d96428e2a46fb408749d795be6ca6c2dfd6b8507166f8d |
| .pytest_tmp/d1-worker-preflight-code/test_independent_d1_split.py | cbfb345f35f2b29aa33b0b74a96e055b5b11fe5b459505d54d70304f11983e06 |

Read completely: task-16-brief, approved context specification, complete D plan,
validation-contract-decisions, context-contract-decisions, B1 contracts, corpus
inventory, B5/B7 training interfaces and the reviewed split source/tests. Also
inspected the actual football provenance/feature/effect chain, B6 input schema,
B7 mirror/coverage guards and tennis predictor/tour-builder/rating/serve seams.

## 2. Why flat TrainingRows are not enough

The closed B1 row lacks the original Event, complete BaseDistribution and
FeatureVector, source outcome record, replay recipe and availability evidence.
Its hashes cannot reconstruct missing bytes. A scalar log/logit offset cannot
recreate legacy market calibration, joint outcomes or the v2 feature reference.
Consequently it cannot alone support the specified event-market Brier tuning.
B4 appearance records deliberately do not contain the target match result;
B6 workload records deliberately do not contain service games held/played.

Do not expand B1 TrainingRow or EffectArtifact with arbitrary free metadata.
Use a separate closed case/recipe/outcome transport. The following is a
controller proposal, not an already accepted implementation contract.

## 3. Minimal proposed decisions

### A. Own the source outcome registry, not generic target dictionaries

Normalize target results into B1-style immutable source observations with a
new explicit kind/schema, preserving actual observed_at/content/receipt hashes
and native source/event/participant/schedule binding. Resolve with the owning
source adapter, not `verified=True`, a self-issued hash, a bookmaker result or
name matching. Outcome payload fields are closed per schema:

- Football v1: regulation goals home/away as actual nonnegative integers,
  native fixture/teams, competition, scheduled_start, terminal status and the
  explicit regulation outcome contract. Initial causal adapter may consume
  unambiguous native FT receipts. AET/PEN need separately verified regulation
  scores; never use aggregate final goals or silently clamp them. Unknown,
  cancellation or ambiguous period is an exclusion, not a fabricated target.
- Tennis winner v1: exact native A/B/tour/tournament, actual terminal, known
  winner identity and observed result time. Normal completed singles first;
  retirement/walkover/default require an explicitly separate outcome rule,
  never implicit winner-by-injury inference.
- Tennis serve v1: same binding plus observed **service games held/played for
  each player**, strict legal successes/trials, actual best-of and final set
  score needed by the declared distribution outcome. Point wins are not hold
  wins; total games/set scores cannot infer who served or how often they held.

Read newer revisions before matching the candidate; equal-time conflicting
results remain excluded. Frozen outcome records stay immutable after fit/test
opening. D1 attaches results only after feature construction; target records
must not enter the same event's feature/base history.

### B. Keep reconstruction metadata outside BaseDistribution

The B1 base contract does not allow `reconstructed_at` or
`logical_training_cutoff`. Return a separate closed replay envelope containing:

`schema, base, event_hash, recipe_hash, input_refs_hash, event_identity_hash,
logical_training_cutoff, reconstructed_at, evidence_class`.

Its A1-style envelope hash binds all fields. `base.cutoff` is the logical
decision; reconstruction/build time is the actual execution time. The recipe
binds code revision, exact baseline version/config/calibration references and
the canonical ordered source inventory. Actual secured receipts/proof
resolutions must be resolved before the input enters this pure calculation.
The evidence class is derived by that resolver, not trusted from the caller.
No `ignore_freshness` option or rewriting ModelState.built_at.

`replay_base_distribution` therefore needs an explicit recipe/model-state
input in addition to its proposed history tuple, and a closed wrapper return.
The existing plan signature cannot faithfully encode those facts on its own.

### C. Bind one price-free training case alongside the scalar rows

Proposed closed case payload:

`schema, event, base, features, replay_ref, outcome_ref,
event_identity_hash, family_config_hash, preprocessing_refs`.

The source-resolved case registry supplies the bytes behind those references;
do not accept unresolved digest strings as proof. Event/base/feature cutoff,
full v2 reference, source participant orientation, outcome identity, exact
feature order/coverage and every consumed causal receipt must agree.
`preprocessing_refs` maps the exact verified causal preprocessing envelopes
used for this case, not a freely supplied numeric probability.

TrainingRows remain their current closed form, derived from cases. Return or
persist a separate assembly report with accepted cases/rows, excluded native
events/reasons and immutable inventories; never report an empty row list as
an actually trained family. Original outcome-source references remain separate
from feature refs. Canonical alias inventory is bound by event_identity_hash.
Self-identity within one verified owning native source is allowed; unresolved
cross-source joins are not repaired using participant names or kickoff.

### D. Fit and tune need the full cases, and a separate report

Minimal interface extension: training receives `rows`, frozen `config` and a
keyword-only **case registry**, with explicit train/tune membership derived
through split_rows. The first implementation must never receive final-test
labels; freeze/open them via the separate reviewed inventory path.

Config is a closed family-specific recipe: sport/family/population/coverage,
feature version and exact order, model variant, base versions, head links,
reference recipe, preprocessing/grouping references, target markets,
outcome contract, train_end/tune_end and the approved alpha grid. No executable
callback or arbitrary family wildcard inside config.

Return a closed **fit-result wrapper** containing the selected unchanged B1
EffectArtifact plus all per-alpha event-mean tuning scores, chosen alpha,
row/case/config hashes and failure/coverage report. Alternatively introduce a
new report-returning function and keep train_family as its artifact-only
projection. Do not hide tuning diagnostics inside EffectArtifact or mutate a
caller-owned config as an output channel. This return choice needs controller
confirmation before implementation.

Train-only scales/coefficients remain frozen after tune selects alpha; ties
prefer larger alpha. No train+tune refit. Tuning uses B5/B7 comparisons against
the original full cases and exact declared market outcomes, not per-head loss,
ROI, price, or only winner accuracy.

Tennis serve must fit one shared law on A observations plus mirrored B
observations, then derive the other head by the exact signed permutation of
the same coefficient/scale/alpha/count. Two independent fits followed by
averaging fail B7's mirror contract. The 2N head observations are still N
events for splitting, tuning and empirical counts. Winner-only consumes only
signed delta features with no free intercept.

### E. Do not fabricate dense player features or earlier preprocessing

B4 produces player/component-specific columns whose names differ by roster.
The first supported recipe must explicitly freeze the feature vocabulary and
require complete numeric support for its consumed names. Absent columns are
not zero/healthy players. A pooled role/side design needs its own explicit
feature recipe/version and tests; it cannot be silently inserted by D1.

Participation effects fitted at outer train_end cannot be applied to earlier
training events as though they were known then. Earlier cases require earlier
fitted/verified preprocessing (rolling/inner windows) with their own references;
final train-only preprocessing is used for later tune/test events. Keep this
distinct from the final EffectArtifact's frozen preprocessing references.

Run strict split/fit assembly per declared comparable cohort. Unsupported or
pretest-failed hypotheses remain in the experiment registry with null candidate
and p=1; do not feed missing unrelated variants into one combined event group
and erase a supported cohort. All canonical versions still share one logical
decision/window in the global identity inventory.

## 4. What is actually replayable now

| Family | Pure numerical route | Current causal evidence boundary |
| --- | --- | --- |
| Football regulation goals | Existing _fixture_model/score_matrix and exact opt-in reference weights; preserve original rate/market calibration version | Only with the exact target/history/previous calibration inputs whose results were actually available before decision, plus native roster receipts. Existing arithmetic is replayable; the read inventory does not yet prove a real eligible injury-training cohort. |
| Tennis winner, ATP/WTA separately | Stored immutable predecision tour state and original calibrated winner path; or causally rebuilt SurfaceElo/serve blend and prior calibrator through a separate pure seam | Current historical builders use names and tourney_date/result_date sources, not native event/result-receipt proof. Today-built state cannot be passed to yesterday's predict_match; its explicit guard rejects that. Unproven aliases/import clocks remain retrospective. |
| Tennis serve | Existing genuine hold parameters and the explicitly versioned strict B7 simulator base | Never promote a legacy calibrated winner/Elo blend to a coherent serve base. Requires actual bilateral hold outcomes and native identities/clocks. B6 workload/legacy shadow lacks these; WTA source has no serve feed. Not a currently demonstrated causal fit. |
| Basketball/hockey/e-sport | Existing legacy calculators only | Their context family contracts/adapters are not implemented in this B5/B7 packet; do not claim D1 support through a generic fallback. |

Legacy tennis winner calibration must be preserved by its winner-only replay.
The new strict serve base is a separate declared version, not byte-parity with
legacy clipped/rounded/independently calibrated side outputs. Football raw
pre-market rates and legacy calibrated market values need separate exact
provenance; no discarded calibrator may be called an unchanged replay.

## 5. Real corpus barriers, not a new live inventory claim

The bounded inventory is dated September 7, not refreshed here: 5878 football
rows represented 19 stored keys, 116 tennis rows five, 84 e-sport rows eight;
only four stored result-bearing keys across the inspected forecast archive.
104 settled tennis receipt rows were not proven 104 canonical matches.
All 1239 inspected tennis durations were NULL, with no native A/B ID or actual
end columns. The shadow CLV record did not have a context archive.

The September 9 native football probe demonstrates source shape (46 players,
32 known minutes in one completed fixture) but not their August prematch
availability. B6's fresh ESPN result supplies neither actual match end nor
service successes/trials. No currently inspected evidence establishes 200
canonical causal untouched events over three consecutive blocks for any new
context family. This is not proof that every other legacy archive is empty;
the later authorized inventory must check actual saved source receipts and
state identities rather than blindly reuse these dated aggregate counts.

## 6. Smallest next implementation packet

After controller agreement on A-D, implement closed outcome/replay/case
validators and their negative cases first; then actual football row assembly
and numerical replay on supplied verified receipts; then winner-only tennis
from truly bound predecision snapshots; then fit/tuning/report wrappers. Keep
serve assembly unavailable until its genuine target source is resolved.
No synthetic case or descriptor-only dataset can satisfy the real training/
200-event acceptance. Report insufficient_data/unsupported in the frozen
hypothesis registry and continue independent D2/D4 work without loosening it.
