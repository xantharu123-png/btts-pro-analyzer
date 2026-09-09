# Independent B4 final review

Reviewer: `/root/worker_failures_20260909`. Date: 2026-09-09.

Disposition: **Approved for the reviewed B4 source/normalization/roster mechanics.
No new actionable finding reproduced.** This is not D1 training, D2 empirical
approval, D3 activation, medical completeness, deployment, or an assertion that
an injury effect has been learned.

## Frozen scope

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`.
The parent advanced HEAD from `ce7f0700049e8e75e7b01705ebdea7b93b52e44b`
to `3e9ce2c3e4e7a591a3b22a657fe6cc5cc9aeab06` while integrating B7 outside
the frozen B4 scope. All ten B4 source/test hashes below were checked at the
start and end of this review and remained identical. No reviewed source,
approved test, legacy fixture, helper, provider, or production state was edited.
Only this report and the separate independent test file were created.

Read the complete B4 plan section, the current controller decision document,
all reviewed source files and five new test modules, the source-provider seam
diff, the native binding/reference consumer in `challenge_engine.py`, the
original external source repros, previous own repros, and the parent B4 audit.

| File | SHA256 |
| --- | --- |
| context_sources/football.py | ef8af37ab0b2959cdb28c3e74f13f0783d6d39a60e969b4914913bf9155a06b7 |
| context_sources/football_provider.py | 6b2da088c60f08359b0e20150e660ecebcb4fb98c47561721c7bdf628f748b83 |
| context_sources/football_native.py | 880817e335480a463b912931065714ef8244764855ec4e4c497b65950883f127 |
| context_models/football.py | 0f38c93c3a4c38c21112aa22d7b04f7f61f1369dbdba71f319df81c191fbe1dc |
| challenge_15k.py | 12fd79cdf419806941f44cd0c068baded93d950694ba87e181fd2152114464ed |
| tests/test_football_context_sources.py | 31e913a2a34a81b4de1a3d002781f0cbfdb48b5103a68b63d980388bf547631b |
| tests/test_football_context_features.py | 4bbc1ef27b698cbc1296f651be16eed80e25ded92e332cd683dd878ac2b132c2 |
| tests/test_football_context_revisions.py | 5014f2fcce8d66b57657dea64195f8fdba8aa054c661af3c019498ba6227a698 |
| tests/test_football_context_provider.py | fd218fc07379c835b6487f85ebec6d2f0938113667bb23b09098ea786286ce0f |
| tests/test_football_native_context.py | f81893b6b73c9ba5ff1519ece55cbe6da0704124635dbce03735214c30eb8051 |

Additional inspected integration/evidence hashes:

- `challenge_engine.py`: a7222cf12187a600c709f67fcd9df9d13b92a891b6158261f9a0fbe8ab54ea12.
- `tests/test_football_base_provenance.py`: b66d2aea9c806a0aef744a56b3812ed336875fce8e9003ac9d2344ca15c96df4.
- `tests/fixtures/context/football/api-football-20260909.json`: 0b429c4b8f8aa840261a1557fabf22a4b3dab811d688948a8a800f1475a113fa.

## Own fresh execution

All runs used
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider`
from the reviewed worktree, with a distinct `--basetemp` below. There were no
network/provider calls; provider tests replaced the HTTP owner locally.

1. `b4-worker-final-focus-01`: **118 passed, 6.24 s**. The five B4 test
   modules, `tests/test_context_coverage.py`, own unchanged original six
   counterexamples, and the unchanged ten external source/provider repros.
2. `b4-worker-final-attacks-01`: **39 passed, 1.03 s**. New independent file
   `.pytest_tmp/b4-worker-final-review-code/test_independent_b4_final.py`.
3. `b4-worker-final-integration-01`: **459 passed, 7.45 s**. Base provenance,
   B5 football context model, B1 contracts/coverage/observations, native context,
   and the new independent file. These suites overlap; do not sum them into a
   unique-test count.

Parent separately reports full-suite `root-b4-b7-full-01`: 3281 passed,
15 expected Windows skips, 97 subtests, 70.60 s. That full-suite run is the
parent's evidence, not a full-suite rerun by this reviewer.

New independent test SHA256:
`ba9adce1d1a50929103e18d3c59db454c201ffc530f041dbdca97d56e8080266`.

Unchanged original packages:

- `.pytest_tmp/b4-worker-review-code/test_independent_football_review.py`:
  `5971403034e4ce2b698d773d353f34f90e20ef32cc390b3b327e4078700770d0`.
- `.pytest_tmp/b4-worker-rereview-code/test_revision_attacks.py`:
  `e9f20a46ca0c31dc86b0c8f4293bfdfe9a42ae46e6b980994c907fe19d7383b8`.
- External `.worktrees/kontext-b4-provenienz-20260909/.pytest_tmp/review-b4-source-20260909/test_b4_source_independent_findings.py`:
  `1bde39cde4bb071860802158e74cd29a8451b5bc85699bd231f199e462d4033a`.

The older second package assumed every appearance/lineup row was a player and
that identical members appeared only once (`len == 12`). Those are obsolete
setup assumptions after explicit empty-team markers/full-content hashes. The
file remained untouched. Its actual attacks were rebuilt separately: exactly
twelve UNIQUE players drawn from two authentic full-XI revisions, and two
authentic incompatible partial minute projections. Both remain conflicting,
not numerical rosters. This is not a relaxed acceptance criterion.

## Counterchecks and conclusions

- Current team selection is bound to the entire collection content and the
  latest actual team receipt. Missing player projections cannot be filled
  from older or simultaneous incompatible revisions. Twelve starting players
  from two eleven-player source lineups do not become one team.
- Explicit empty team markers withdraw old lineup/appearance data. They are
  excluded from player/minute identity extraction. A later empty native
  receipt likewise cannot borrow older players to certify a roster join.
- Native corrections are selected before matching baseline rows. Changed
  goals (including later unknown goals), orientation, kickoff, league, or
  season cannot certify an older matching baseline revision.
- Later null minutes remain null, not old numbers, zero, or 90. A native
  player linkage may legitimately remain verified with unknown minutes;
  that is not complete regulation exposure or permission for a numeric feature.
- Same-time changes to minutes, unknown minutes, complete withdrawal, or
  player role retain native-receipt ambiguity. Duplicate identical receipts
  remain idempotent. A correction at the exact cutoff is used; one microsecond
  after it cannot displace the earlier receipt.
- Actual bool/string/nonpositive IDs and bool/string/fractional/negative goals
  are rejected. Regulation minutes are not coerced or clipped: bool, string,
  negative, over-90, NaN and infinity fail the owning builder's boundary.
- Provider acceptance requires real HTTP 200 plus exact full-page count and
  native event binding. 206, redirects and error statuses do not create
  fresh fixture observations. Missing injury results remain incomplete.
- Source validity is bound to actual receipt; no provider timestamp creates
  archival publication proof. Full Event/Base reference v2 remains exact.
  Existing venue/form/prior/xG arithmetic and the pinned legacy baseline
  remain unchanged under the provenance opt-in tests.

## Explicit remaining boundaries

The saved live response shape is not historical prematch evidence. Public
content hashes establish internal transport consistency, not source truth.
Native evidence joins fixture/team/player identities; it does not certify
regulation minutes, medical coverage, a fitted coefficient, or the predictive
value of a scenario. Real secured receipt loading, causal TrainingRows/base
replay, fitted preprocessing/effects, independent empirical approval and
runtime snapshots still belong to the upcoming D1/D2/D3 work. No live/source,
model-quality, deployment or financial-operation claim follows from this review.
