# Task 4: native synthetic growth-fixture design

## Decision and boundary

Use one app-owned working copy of the current sealed QA database and derive
three cumulative, separately root-sealed fixtures from it. First add one
complete coherent synthetic generation of the existing Tennis workload/status
pool. Then add one normal live-worker original plus one normal worker snapshot
at each of one, two and three new cutoffs. This is the smallest design that
grows receipt volume, replay-consumer count and distinct cutoff count together.

This is capacity QA only. The generated rows retain the real owning ESPN Tennis
schemas because the unchanged validators require them, but they are artificial
receptions in an isolated `synthetic-only` stage. They are never provider
evidence, training/evaluation evidence, production input or a deployment
candidate. Do not copy the generated database into any runtime or backup tree.
No source, model, selector, feature, predictor, limit or report schema changes
belong to this fixture work.

The pinned source input is the fresh root-sealed, single-link DELETE-mode copy
`/var/lib/betboy-live-backup-pknwmr9p/context-current.db`, 114929664 bytes,
SHA-256 `d304c164b44a17cb4e7b90df14f87cbde8dbdd36852d7250911163f967f169b9`.
Its required starting shape is 12 artifacts (10 live originals and 2 tour
states), 10 snapshots, 48307 contents/receipts, 2 manifests, 0 rollbacks and 5
distinct ATP original cutoffs. All ten originals refer to state
`5fb2d3778809470dcc5a0ad665117619ebd8a5e4a591112eb928335107a1bcf2`.
Fail construction if any pin or count differs.

## Minimal synthesis algorithm

### 1. Isolate without weakening the source

Root creates a new private `/var/lib/betboy-task4-growth-*` stage, stream-copies
the sealed input to `synthetic-working/context.db`, fsyncs it, and makes only
that working copy `betboy` UID 997/GID 987 mode 0600. The source inode, bytes,
mode, owner and timestamps are recorded before the copy and rechecked after all
fixture construction. The working file must be a regular single-link file in a
0700 app-owned directory, use SQLite DELETE journal mode and have no
`-wal`/`-shm`/`-journal` companion.

All database generation runs as actual UID 997 from the exact candidate source
archive. Root performs only byte staging and final sealing. The generator has
no network access and asserts UID 997. It applies the existing 2 GiB address
space boundary and a bounded CPU limit to each construction step; fixture-build
timing is recorded separately and is not a D4 acceptance result.

### 2. Add one coherent historical-volume generation

Reuse the narrow mechanics of ignored
`.pytest_tmp/build_synthetic_capacity_generation.py`, with two changes only:
bind its starting pins to this 48307-row input, and calculate a positive clock
translation rather than blindly adding one day.

Read the immutable base, not rows generated earlier. In a first pass copy every
`workload` row whose decoded source is Tennis `SOURCE_SCHEMA`; in a second pass
copy every Tennis `event_status` row using `STATUS_SCHEMA`. The measured input
contains exactly 21000 plus 26098 such rows, so the generation adds exactly
47098 receipts and contents. Reject any other count.

Choose the translation so the whole copied pool is strictly later than the
base pool but ends with a generous margin before the unchanged start of
`espn:tennis:ATP:match:182766` (`2026-09-11T23:00:00Z`). A concrete safe target
is to place the translated maximum at or before 21:30Z; compute one common
`delta = target_max - source_pool_max` and require `delta > 0`,
`source_pool_min + delta > base_pool_max`, and `target_max < 21:30Z`. Abort if
those assertions do not hold; never move or rewrite the real event schedule.

For every copied workload row, set its translated receipt clock,
`valid_from` and `payload.result_observed_at`, then recompute
`source_revision`, content digest and receipt digest. For each status row,
translate the same clocks, replace every `payload.workload_receipts` identity
through the complete workload old-to-new digest map, recompute
`competition_revision`, `source_revision`, content digest and receipt digest.
Run `normalize_observation` and then `validate_selected_tennis_receipt` on every
candidate before an exact `INSERT`; reject a pre-existing digest rather than
using `INSERT OR IGNORE`. Commit only after the expected 47098 rows and
`PRAGMA foreign_key_check=[]` are proven.

This differs materially from the old fixed-consumer fixture: the new replay
cutoffs below occur after this translated pool, so the added rows are causal
history for the new consumers rather than merely future physical inventory.

### 3. Add one real producer consumer pair per new cutoff

Use the still-scheduled event `espn:tennis:ATP:match:182766`; its stored start
remains `2026-09-11T23:00:00Z`. Derive its tournament, player IDs and player
display names from its validated existing event/original data. Build a
synthetic ESPN response that reproduces those identities and schedule with
native status `{state: "pre", name: "STATUS_SCHEDULED", completed: false}`.
Do not invent a state, probability, feature vector, artifact or snapshot.

Let `T` be the translated pool maximum. Use `D1=T+5 minutes`, `D2=T+10
minutes`, and `D3=T+15 minutes`; require all three to be distinct, later than
the previous decision and earlier than the unchanged scheduled start. For each
`Di`, run one ordinary producer batch against the app-owned QA copy:

1. Enter `tennis.live_context.live_worker(path=working_db)` and
   `context_sources.tennis_capture.capture_tennis_worker(path=working_db)`, and
   attach the capture.
2. At the provider-response observation boundary only, return the synthetic
   in-memory ESPN response and clock its new status receipt at `Di-1 second`.
   Keep `normalize_tennis_status` and `append_observation` unchanged.
3. Let `scripts.tennis_daily.fetch_fixtures_espn` create and bind the normal
   fixture, then call `scan_fixtures` with `decision_at=Di`, `surfaces={}`,
   `workload_history=()`, the exact loaded ATP state from `working_db`, and a
   separate disposable Shadow DB. No request may reach the network.
4. Close the capture first so its receipt is durably appended, then call
   `LiveWorker.finish`. Supply only deterministic harness clocks for receipt,
   decision, publication (`Di+1 second`) and scratch-Shadow append
   (`Di+2 seconds`). These clock seams and the HTTP response boundary are the
   only substitutions.

The unchanged producer must therefore execute `load_tour_state`,
`predict_match(..., original_capture=...)`, `tennis_observations_as_of`,
`tennis_features_v3`, `validate_original_publication`, `put_artifact`,
`calculate_context_payload` and `compute_once`. Assert each batch is complete,
checked/prepared/stored exactly 1 with no errors, loaded the pinned ATP state,
captured exactly one new status receipt, and added exactly one immutable
original and one snapshot. The disposable Shadow database is not sealed or
counted as context evidence.

After each batch, seal a new cumulative profile. Expected shapes are:

| Profile | Receipts/contents | Originals | All artifacts | Snapshots | Distinct cutoffs | Replay history calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| G1 | 95406 | 11 | 13 | 11 | 6 | 22 |
| G2 | 95407 | 12 | 14 | 12 | 7 | 24 |
| G3 | 95408 | 13 | 15 | 13 | 8 | 26 |

`Replay history calls` counts both the original and snapshot consumer for every
publication. Manifests remain 2, rollbacks remain 0, the active manifest and
both tour-state rows remain byte-identical. If the normal producer emits a
different count or cannot use the stored event without altering its schedule,
fail the fixture; do not repair the database by hand.

## Preservation and real-validator checks

Before mutation, retain explicit baseline table identities. After every stage,
compare every baseline row byte-for-byte by its primary key across
`artifacts`, `manifests`, `active_manifest`, `context_contents`,
`context_observations`, `context_snapshots` and
`context_model_rollbacks` (a one-way baseline `EXCEPT` query with explicit
columns is sufficient). Assert no baseline row is missing or different and
that only the exact new keys account for the count deltas. This is stronger
than comparing counts. Also prove the original sealed source SHA/stat remained
unchanged.

For every new pair, load the artifact and snapshot through the owning decoders
and assert:

- the artifact digest is `digest({kind: ORIGINAL_ARTIFACT_KIND, payload: ...})`;
- `validate_original_publication`, `original_base` and
  `validate_live_winner_origin` accept its exact bytes and publication clock;
- the state hash is the pinned ATP state and the origin code hashes equal the
  unchanged owning `CODE_PATHS` bytes;
- its native receipt is the unique latest scheduled status for that event at
  its cutoff, and every returned history row has passed
  `validate_selected_tennis_receipt`;
- `observation_refs` equals the sorted digest set of the complete owning tour
  history, and a fresh `tennis_features_v3` call is canonically equal to the
  stored feature vector;
- `context_payload_key(payload)` equals the stored key and
  `replay_context_payload` accepts the decoded snapshot with its actual
  effect/approval fields (expected absent on this input).

These focused assertions diagnose fixture mistakes. Acceptance is still the
unchanged, uninstrumented `scripts/verify_context_runtime.py --sealed-file`
run, because it repeats complete physical inventory validation, all old and new
original numerical replays, and every old and new snapshot feature replay.

### Root seal and exact acceptance

After clean close, root stream-copies each G1/G2/G3 working state into its own
new directory, fsyncs file and directory, sets root:betboy 0440, and proves a
regular single-link DELETE-mode file with no companions. Record SHA-256 and
size, then run the exact candidate CLI as UID 997 with AS 2 GiB, CPU 300 s,
wall 600 s, output 1 MiB and all numerical thread settings 1. Require CPU and
wall below 300 s, peak RSS below 1 GiB, unchanged sealed SHA/stat, no companions,
exit 2/`transport_only`, `empirical_approval_verified=false`, the exact count
row above, unchanged active slots/tour states, and exactly the existing two
limitations:

`d1-original-replay-context-unavailable` and
`d3-owning-source-feature-replay-unavailable`.

Run G1 first. G2 and G3 are a small consumer-slope continuation, not permission
to weaken the G1 gate. Report each result independently; never replace a failed
profile with a smaller passing claim.

## Honest capacity interpretation

The shared-basis change removes redundant owning selection/encoding across
cutoffs; it does not remove consumer work. Every one of the 11/12/13 snapshots
must still receive a fresh complete tuple and execute the full unchanged
`tennis_features_v3` mathematical replay. The translated pool also makes the
largest basis roughly two current histories and may approach or exceed the
unchanged 64 MiB aggregate cache budget. Correct oversize behavior is a full
cold fallback, not truncation or a cap increase.

Consequently G1, G2 or G3 may inherently exceed CPU 300 even when the shared
basis is semantically correct. Such a result is a real capacity failure for
that profile and must be reported fail-closed; it is not grounds to skip
snapshots, memoize model results, reduce receipts, change limits, or claim
release readiness. Baseline actual-input acceptance and each growth profile
remain separate gates.
