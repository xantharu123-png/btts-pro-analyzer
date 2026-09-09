# Root independent D4 review — original finding

Frozen target `b56da33d7b4c447e6a50ff7ec600efc3b7b49f5f` in
`kontext-d4-semantic-20260909`, 9 September 2026. **NOT ACCEPTED pending F1.**
Full semantic helper, changed runtime branches and owning audit read. Existing
OS/SQLite/rollback boundaries were inspected separately from semantic replay.
No target source, existing tests, Git, live data or VPS was changed by review.

## F1, P2: orphan feature receipt references bypass physical availability checks

`context_runtime_semantics._case_shape` validates a standalone known v1 case's
base/replay/native map, outcome reference and preprocessing references, but
does not resolve the explicit receipt hashes in its FeatureVector. Without
the original experiment/configuration, later owning replay remains unavailable.
That legitimate capability limitation currently also conceals an impossible
explicit source reference, despite the stated invariant that missing actual
references remain errors rather than unknown-context gaps.

Two independent actual SQLite probes reproduce this on original source bytes:
remove only the experiment (a supported pre-freeze/orphan storage condition),
append an otherwise valid case with one existing feature's receipt list changed
to (a) a nonexistent digest, or (b) an actually stored receipt observed after
that case's decision. Both complete runtime checks incorrectly return an
incomplete report instead of rejecting the contradictory known reference.
The scope/causal claims are provably impossible without a guessed config or
opening any final result body. This is not an empirical approval bypass: the
overall report already remains `transport_only`, with no verified case/approval.
It is a missing known-reference integrity check in the proposed D4 contract.

Narrow remedy: inspect every explicit feature receipt with the existing physical
outer-reference validator, using the original feature/base cutoff as the latest
known receipt time. Do not decode final source bodies, invent an owning config,
promote historical availability, or treat this physical header check as a full
feature replay. The actual supported D1 case source class is prospective.

## Independent execution

Thirteen new unchanged probes: **2 failed, 11 passed, 0 skipped**, 89.46s.
Both failures are exactly missing expected `ArtifactIntegrityError`, not setup
errors. Controls reject bad case shape/version/outcome/replay/preprocessing,
preserve genuine incomplete orphans, detect unopened-final physical index and
BLOB type corruption, and verify a real already-opened D2 evaluation using
only one `:memory:` connection with the path resolver forbidden. Source bytes
and companion-free directory are unchanged after successful/failed checks.

Shared quality Python, `-B -m pytest -q --tb=short -p no:cacheprovider`,
`--basetemp=.pytest_tmp/d4-root-independent-run-20260909-01`,
JUnit `.pytest_tmp/d4-root-independent-20260909/results-01.xml`.
Probe `test_independent_d4.py` SHA256:
`c2972259269e8e119e7021ce7307ced0e5bc110fede03c609705bd8c22ddb0bf`.
Original probe and this negative report must be retained unchanged for review.

The owner's 4,533/18/97 whole suite is not independently rerun here and does not
disprove F1. No additional actionable finding has been reproduced yet. Final
fix rereview, integrated capabilities, fresh Linux restore and trusted VPS hook
are still separate obligations. All data are synthetic native-shaped mechanics,
never an actual sporting effect, new approval or >=200-event real corpus.
