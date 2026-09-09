# Tennis: existing-response capture and native status v3

Base: `ecf92007f46c5e8b85cb24b6f7208cb71240cac4`. Controller authorized this
bounded implementation on 9 September 2026. This first section was recorded
before implementation. No source, empirical or production acceptance follows
from this document.

## Source-owned rulings

- Observe only JSON responses of the already executed
  `scripts.tennis_daily._fetch_espn_events` calls, inside an explicit daily CLI
  worker scope. Do not add a query/retry/date/tour or enable capture during
  rendering or no-network pending refresh. Record the actual response-receipt
  clock, not a match date, issue time or an inferred actual end.
- Add closed `espn-tennis-event-status-v1` B1 records for actually identifiable
  native singles competitions. Preserve the actual ATP/WTA namespace, native
  match identity, known participant IDs, scheduled time and native status.
  Missing or malformed participant/schedule metadata remains explicitly unknown;
  a known match's newer defective revision must still retract old workload.
  No old player/schedule is copied into a defective newer revision.
- A price-free, normalized competition revision and the exact two workload
  receipt identities bind supported terminal projections from the same actual
  response. Equal timestamps alone cannot establish a matching pair. Partial
  persistence cannot borrow a missing opponent from an earlier revision.
  Raw provider bodies, names, prices and arbitrary status objects are not stored.
- Resolve full native event history before schedule/participant filtering.
  Newer nonterminal, unsupported or defective revisions retract earlier terminal
  facts. A later incomplete terminal status cannot revive them; only its own
  complete, consistent workload pair restores that revision. Equal-time
  contradictory revisions remain conflicting. Earlier cutoffs remain unchanged.
- Existing workload-v1 and B6 feature-v2 bytes/semantics remain unchanged and
  readable. New B6 feature-v3 has an explicit full Event/Base reference and
  status-aware coverage identity. Legacy-only facts remain old known facts;
  they do not gain a status receipt or fresh availability. B7 and D3 receive
  explicit v3 adapters; old v2 effects/approvals never transfer by relabeling.
- B1 storage shape, prediction/ticket/account history, baseline/calibrator,
  Cricket, provider budget and deployment machinery remain unchanged. Missing
  exact match end/duration stays missing. No numerical fatigue penalty is
  introduced. Synthetic fit tests establish mechanics, never D1/D2 approval.

## Implementation boundaries

`context_sources/tennis_status.py` normalizes closed native competition facts and
validates the source envelope plus exact bilateral workload receipt identities.
Its owning reader validates the actual B1 inventory before tour projection and
does not prune by current schedule, subject, source-status or participant. The
original B1 schema and generic reader are unchanged. Missing database stays
absent. The owning worker reader uses B1's existing trusted connection; it is not
the sealed, read-only D4 verifier.

This worker reader decodes inventory bodies for integrity before its final
tour/cutoff pruning. It is not a label-free D2 pre-opening reader and must not be
reused as one. No v3 D1/D2 dataset integration is part of this packet; that owning
path must retain its separate opaque-byte/index preflight and holdout opening.

The status payload records native status fields/classifications, actual known
participant slots (including null unknown slots), scheduled time or null, actual
grouping/tournament or explicitly unresolved scope, projection issues, exact two
workload receipt hashes or none, and a versioned competition-reception digest.
The latter binds the full price-free projection, native event and actual receipt
clock. Unknown/doubles groupings may retain a withdrawal for a native ID but
cannot supply singles workload. They do not claim a doubles effect. An invalid
native match ID cannot be replaced by a name; capture reports that limitation.

`context_sources/tennis_capture.py` uses a scoped ContextVar observer. The default
fetch caller reads no capture clock and creates no database. Daily CLI `main`
owns the observer around the pre-existing daily sequence; successful JSON replies
are observed before fixture/result downstream filters. There is no additional
request, changed URL/date/tour/header/timeout, retry or pending-refresh network
path. Only normalized sport records survive capture; no raw response is stored.
Finally drains received observations even when the worker body fails, then
restores the scope. Storage failures propagate outside the provider's old
ValueError handling. Status is persisted first: an interrupted multi-record write
leaves an explicitly incomplete pair. This is not falsely described as one
multi-row transaction; B1 receipt ingestion itself remains atomic/idempotent.
Normalization occurs at receipt, whereas publication occurs at scope exit. A
future same-run D3 assembly must therefore follow publication (or have an
explicitly reviewed publish boundary); an in-scope database read cannot claim
the still-buffered observations. Existing daily baseline calculations do not
consume a new context effect in this patch.

`context_models/tennis_v3.py` resolves whole-event lineage before invoking the
unchanged v2 performed-window arithmetic. Conflicting simultaneous revisions and
new defective/nonterminal/unpaired revisions withdraw the older claim. A new
complete pair restores only its own facts; unrelated new workload cannot refresh
an old status. Target-event started/cancelled/completed status is not applicable;
target schedule/participant mismatch is missing and requires upstream revision
reconstruction. A matching target schedule receipt is bound into usable feature
references. Unrelated native matches do not alter target-player coverage.

The new identities are `tennis-performed-load-v3`,
`tennis-context-reference-v3` (entire original Base and Event), and
`tennis-performed-load-coverage-v2`. Coverage keeps the existing exact/bounded/rest
and performed-window cases but explicitly prefixes `status-paired`, `legacy-only`,
`mixed-status-legacy`, `unavailable-status` or `no-history`. v3 does not silently
promote legacy-only facts into a fresh status proof. An unresolved newer relevant
history revision conservatively leaves that participant's context unknown; this
first variant does not infer temporal irrelevance for that defective revision.
Original observations and the visible basis are not deleted or invalidated.

B7 supports explicit `tennis-winner-status-load-antisymmetric-v1` and
`tennis-serve-status-load-mirrored-iidsets-holdproxy-tb7-strict-v1` variants with
the new feature/coverage binding. v2 variants retain their old law and identities;
no coefficient or approval is relabelled. Winner/serve, full Event/base, actual
best-of, tour, environment, completeness, mirror routing and zero-effect rules
remain. Pure D3 adds only the explicit v3 reference adapter and rejects unowned
preprocessing references. No B3, training policy, dataset or approval change.
The separately accepted D3 canonical-byte fix `1a9fffa` is not present in this
packet's starting commit. Its independent integration remains the controller's
responsibility; this patch neither duplicates it nor claims to repair that old
transport equality boundary.

## Evidence and remaining limits

Tests exercise exactly two previously sanitized real response examples received
on September 7; they remain dated source-shape evidence, not current matches or
new GETs. All other test source replies and B2 training signals are synthetic.
The real examples provide native IDs and set scores, but not actual start/end,
duration, verified availability, retirement diagnosis or complete career history.
Therefore paired ESPN-v3 inputs supply a result-receipt lower rest bound, not an
exact pause; set/game facts remain stored but cannot be placed in performed-load
windows without an actual end. A later paired recheck supplies its own valid
receipt bound; this packet does not claim it is the strongest conceivable bound
obtainable by further historical revision analysis.

No real >=200-event D1/D2 approval, native Tennis state resolver or empirical
improvement is claimed. Actual source capture and CPU v3 comparisons do not finish
the D3 consumer/worker coordinator or D4 source replay integration. The pure
transport accepts only resolved inputs and is not a provider/approval authority.
Without an actual approval the used parameters/markets remain exactly original;
the synthetic fitted comparison is explicitly experimental. No new 15K or public
market certification is created. Existing price, Cricket, ticket, ledger and
historical model paths remain unchanged. No merge, push, deployment or provider
call was performed.

## RED/GREEN execution ledger

- Initial new APIs: 50 RED in `tennis-capture-red-02.xml`; after implementation
  50 passed. The first attempted harness run lacked `.pytest_tmp` and yielded
  24 missing-API failures plus 26 directory setup errors; it is not clean RED
  evidence. Creating only the temporary parent resolved that harness issue.
- Explicit numerical/transport adapters: 3 RED / 7 controls; then 60 combined
  tests passed. The genuine B2 fit uses artificial signals and actual B1 receipt
  reconstruction; no artifact from this test is an empirical approval.
- Additional target-event/irrelevant-event lifecycle probes: 7 actual RED, then
  67 combined tests passed. Further source/timestamp/index/partial-write controls
  brought the scoped suite to 85 passed.
- Additional native cancellation-code probes: 3 actual RED / 2 controls. An
  arbitrary note containing "not canceled" could override native `STATUS_FINAL`,
  and a recomputed envelope could contradict its native cancellation code. The
  source now recognizes cancellation only by actual `STATUS_CANCELED` or
  `STATUS_CANCELLED` and validates that identity. These are owning adversarial
  tests, not an independent review.
- The earlier broad context/tennis/artifact/runtime focus passed 2,039 tests with
  10 skips in 658.97 seconds, before the final native-code correction and final
  counterpart controls. It is not evidence for the final frozen bytes.
- Final frozen focus: 583 passed, no skips, in 11.89 seconds. This includes 92
  newly authored tests plus unchanged B6/B7/B3/D3 regression files. JUnit:
  `.pytest_tmp/tennis-capture-final-focus-01.xml`.
- Full regression on exactly the frozen source/test identities below: 4,541
  passed, 18 skipped, 97 subtests passed in 753.46 seconds. JUnit:
  `.pytest_tmp/tennis-capture-full-01.xml`. The 18 explicit Windows skips are 13
  unavailable real-symlink tests and 5 POSIX permission/umask tests, not source,
  model or empirical approvals. This run does not replace Linux QA.
- All ten frozen source/test hashes and the six unchanged legacy identities
  were rechecked. `git -c core.autocrlf=false diff --check` passed. The packet is
  handed off for independent review; the owning green suite alone is not that
  review or a production release.

## Frozen source and test identities

Raw SHA-256 values for this actual Windows worktree; these do not assert portable
line-ending-independent recipe identity.

| File | SHA-256 |
| --- | --- |
| `context_sources/tennis_status.py` | `021ee5c234bf7a01166ee82dd21025154af1c48b81e5303c0963d2760166424f` |
| `context_sources/tennis_capture.py` | `918839283fd4bb446f01fbe34e32ef1e25fb690aa7d1e8f2627650506eef5fdc` |
| `context_models/tennis_v3.py` | `ec6461b87656ecc5731992cc26f0ae69d20e878982706ebe3f1fd0599c43305c` |
| `context_models/tennis_effect.py` | `ab556ac6bc5258332ab3e7b7faf5406d960f426541a7afef3974b4baf8fcb675` |
| `context_transport.py` | `e6969923e0b5bb81055cec7e33febe4224ce7d9c086676e26b53f5ab87c2195f` |
| `scripts/tennis_daily.py` | `96099d53717f1a5b869826dadf4b3d5818ff89b9e8b372e069f693c0c3c50280` |
| `tests/test_context_tennis_capture.py` | `9bb53101f6731724453f3a1dd546d55108bd373ca9a478477d23507eb348f67d` |
| `tests/test_tennis_status_v3.py` | `cf8533ff8d3bc68c016f270478776acc321cf9b5c46a80376d4f4297b036fdfd` |
| `tests/test_tennis_v3_model_transport.py` | `45c344840170f002c9f5d01745608532677be80dc8b5a1cab358630a277891aa` |
| `tests/test_tennis_native_status_codes.py` | `612c9f953dfd57e576cb158df09399ded71853ec3570d45675af221421589e6c` |

Unchanged legacy raw SHA-256 values were verified before and after this work:

| File | SHA-256 |
| --- | --- |
| `context_sources/tennis.py` | `80f1621f60e0b3daecef8abb5e44efeebd2c2bc6bc0df8161032daab78ceb739` |
| `context_models/tennis.py` | `313ffafacc367e7370312f478327d6453860ac0bf17bbcaf8102acdda49e4bab` |
| `tennis/predict.py` | `f92d9451d3e7c0612832101ab1d6298cb99baeeaaa4f2d7c89cb8e9fe0526c7c` |
| `tennis/simulator.py` | `6f326fc84de6b705b762b9d9efaa2932daf0f4546c419d56f30e8c3f4644e29f` |
| `sports_prematch.py` | `fc1253fbeb0888870715c21238d4da78de2c0cbe19fee910da67ebfd35b756d7` |
| `tests/fixtures/tennis_context_espn_20260907.json` | `17c3140266883b4bd561f1432b698d66df7f07a09b50b344cf922123e65812bb` |
