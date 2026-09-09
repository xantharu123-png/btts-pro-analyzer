# Independent C3 Hockey review — findings, no merge approval

Date: 2026-09-09. Reviewer: `/root/worker_failures_20260909`.
Target: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-c3-hockey-20260909`.
Frozen commit: `6b2473bef75f08c8d7452a71f69095e932001501`.
Base: `13b4dac7e7ef4eba2b235c78d3ad351cf71e456a`.

## Result

**Not approved yet. Two P2 defect classes are independently reproduced by
five RED tests.** The implementation's 197 dedicated tests and the broader
1,027-test shared run pass; these do not cover the defects below. No source,
owning test, tracked documentation, Git state, provider, VPS, money, settlement
or production database was changed by this review. Only ignored review files
and isolated test databases/XML were created. The original RED package is
preserved unchanged for the implementing agent and subsequent rereview.

## R1 — [P2] An unusable cancellation can manufacture exact long recovery

Location: `context_models/ice_hockey.py:348-351,373-380`; downstream
`_load_features` at 518-560.

`state(row)` correctly labels an expired or not-yet-valid cancelled appearance
as `stale`. The newest whole-event revision is then selected as unavailable.
However, the subsequent `status != 'cancelled'` condition bypasses `uncertain`
even when that cancellation is **not usable**. Consequently this event and all
its earlier participants disappear from the recovery/load uncertainty proof.
An unrelated older completed match is now incorrectly treated as the exact
last match. This is not merely omission of the old cancelled row: it converts
unresolved newer evidence into a positive numeric claim about the older row.

The real B1 SQLite reproduction contains:

- completed event `2025021777`, actual end 120 hours before cutoff;
- completed event `2025021888`, actual end 30 hours before cutoff;
- a later native cancelled revision of `2025021888`, with no performed fields,
  but either `valid_until == cutoff` or `valid_from == cutoff+1 second`;
- kickoff six hours after cutoff.

The owning reader returns the causal receipt lineage. The feature producer
returns `observed_recovery_exact_hours_home = 126.0`, state `available`, with
only the older game's reference. It must not claim 126 exact hours from a
withdrawal which its own validity policy rejects. Keeping the correction
unresolved must retain its proof and prevent an exact/complete assertion;
falling back to the former completed revision is not requested either.

RED tests in `test_independent_c3.py`:

- `test_nonusable_withdrawal_cannot_prove_older_exact_recovery[expired]`
- `test_nonusable_withdrawal_cannot_prove_older_exact_recovery[future-validity]`

Positive controls test an actually valid cancellation before/equal cutoff,
which legitimately leaves 126 hours, and the same cancellation received one
microsecond after cutoff, which correctly leaves the still-known 36 hours.
Equal-clock participant-conflict controls retain both receipt references.

The bad feature was also passed unchanged through an actual synthetic B2 fit
and the A1-envelope/B3 facade. The comparison was `experimental`, with rates
`1.2482566169651517 / 0.5710796819337401` instead of the original
`3.3067181705635584 / 1.5128296020422185`. No approval was supplied, so **used
rates stayed original**, and OT stayed `0.7972972972972973`. This demonstrates
numeric reachability without falsely claiming any live or empirical effect.

Smallest repair seam: only a usable effective cancellation may remove the
event's participation without uncertainty. An unusable latest cancellation
must preserve the existing whole-event/participant uncertainty contract and
its real bounds/proof; do not loosen B1 freshness or manufacture a new bound.

## R2 — [P2] Incomplete pre-fallback identity checks can relabel a valid base

Location: `context_models/ice_hockey.py:244-268`, particularly 248-256.

The export correctly checks known primary `home_team_id`/`away_team_id`, event
ID, schedule and status before the benign unavailable-reference fallback.
It does not check all native identities actually used by the unchanged legacy
model: `_team` also consumes `team1_id`/`team2_id`. A positive native fallback
ID can therefore compute the original team1/team8 model while the supplied
full Event names team99 on that side. `_make_reference` eventually rejects
its missing primary-ID or metadata, but the broad catch turns the contradiction
into `reference_weights.kind == 'unavailable'`, returning a basis attached to
the wrong Event. This is not an unresolved names-to-native alias case: the
exact positive numeric native ID used by the original computation is present.

The same missing pre-fallback binding exists for the known original game
type. Native target/history `game_type=2` can be exported against a declared
playoff `nhl_reg60_playoff_ot` Event and scope game type3. Missing rule metadata
again makes it benign `unavailable`, despite the already known regular-season
vs playoff contradiction. These separate populations must not be silently
interchanged even when new roster evidence is absent.

RED tests in `test_independent_c3.py`:

- `test_known_legacy_fallback_native_team_is_binding_before_missing_reference[home]`
- `test_known_legacy_fallback_native_team_is_binding_before_missing_reference[away]`
- `test_known_original_game_type_is_binding_before_missing_reference`

Each checks the old model first really computes. Both fallback-ID positive
controls use the matching Event and correctly retain that original forecast
with unavailable roster provenance. The owning tests already cover primary
ID/event/start/status contradictions; this review extends the same intended
rule, not a blanket native-reference requirement for ordinary predictions.

Smallest repair seam: before entering the unavailable-reference try/catch,
bind the actual native team identities and the known original variant used by
the unchanged legacy computation to the supplied Event. Preserve exact legacy
fallback precedence and reject contradictions; do not use names or accept a
new guessed alias. Genuinely absent metadata may still leave an available
baseline with unavailable context provenance.

## Independent evidence and bounded passed checks

All commands used the absolute quality interpreter,
`-B -m pytest -q -p no:cacheprovider` and fresh basetemp directories.

| Reviewer run | Result | Time |
| --- | --- | --- |
| Six dedicated C3 test modules | 197 passed, 1 skipped | 27.47s |
| Original independent attacks | 5 failed, 21 passed | 3.79s |
| Separate additional controls | 25 passed | 2.64s |
| C3 + C2 + B1/B2/B3 + original prematch + A1 | 1,027 passed, 5 skipped | 81.26s |

The first row is included in the shared row, not an extra independent event
count. The 51 new probe cases yield 46 GREEN and the same five concrete REDs.
There were no probe setup errors or changed assertions. One PowerShell-only
hash-list command had a foreach-pipeline parser error; it was corrected without
executing tests or writing source and has no bearing on test results.

Shared-suite skips were read from actual XML: one unavailable Windows symlink
privilege case and four POSIX-only umask/permission cases. No hockey source,
numeric, source-revision, hypothetical-scenario or approval calculation was
skipped. A new full repository run is not claimed: the owner's 4,442/19/97
report remains prior evidence rather than an independent result here.

Reproduce the RED package from the frozen worktree:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/c3-rereview-unique .pytest_tmp/c3-independent-20260909/test_independent_c3.py .pytest_tmp/c3-independent-20260909/test_c3_controls.py
```

Confirmed in own source inspection and executed owning/independent controls:

- Exact replay of the original nonlinear constrained Poisson fit, original OT
  sample/estimate, source-oriented native history and explicit measured
  equal-contributing-game exposure (not a Hessian/Ridge influence claim).
- Actual integer seconds and whole-interval accounting, skater/goalie and
  regulation/OT separation. Null goalie TOI remains unknown through SQLite;
  an explicit fully measured REG result has available zero overtime.
- Half-open 1/3/7-day windows, strict unknown-receipt upper-bound exclusions,
  exact-end recovery versus receipt minimum, no complete-history/medical or
  travel claim. Exact event end at cutoff remains rest-only.
- Whole participant leave/return and current-schedule lineage, equal-clock
  conflict, real reader WAL snapshot, corruption before future/kind filtering.
  The R1 cancellation exception remains the diagnosed uncovered seam.
- Actually fitted mirrored B2 heads, correct opponent-only goalie role, direct
  B3 full original/FV/event/effect binding, unknown whole-lineup skater and goalie
  scenarios experimental even with shape-valid synthetic approval, and an
  independently observed-load-only path not automatically blocked.
- Exact derived operand checks reject +/-9e-13 edits; zero and representationally
  neutral nonzero effects copy original parameter/market bytes. Finite extreme
  Skellam cases preserve mass, complement and fixed OT conversion.
- Unapproved used distribution stays byte-identical to the original; external
  price keys and caller objects do not change the sport computation.
- All 15 frozen legacy output cases, including Cricket, passed in the actual
  owning/shared run. Raw `sports_prematch.py` original 24,369-byte Git prefix
  independently compared identical to the current 24,703-byte file. No old
  algorithm, C2 model, generic B1 policy, settlement or ticket code was edited.

## Read set, hashes and freeze

Read the complete approved specification, Task14 brief, C3 controller ruling,
context/validation decisions, readiness report, preserved C3 preflight and
the entire 12-file packet including all source/test modules and the owner audit.
Also inspected the actual B1 selection/freshness implementation and scoped
three inherited-file diffs. Required preflight SHA is
`f2dec7561f3e0c503557774c8ec7530091863f08aa2ebce6db21b7d6b1ebe968`.
Final status is clean, HEAD unchanged; all twelve hashes match both initial
freeze and the final recheck:

```text
ab82354b4a4a6deb35cbfd33b6056c0b326842848aed3edeadd3ff71bb083ccf  context_models/ice_hockey.py
b32f01b4fe6bd88eeeced71baade95a2d6e5215879c0e58ba097fdf2f72e1bf7  context_sources/ice_hockey.py
02f8b066319cab8e45a181e12a2ef8abf684c0dcd760c4f55a6244b9790edc34  context_models/contracts.py
414a7d198769546751e0407fd89a6e6edcd6892f9c86df83fdb3cc706955e8bb  context_snapshots.py
ef393f89ca54489bab28aae6c8d224012961795e387bc272d78ba7cad264a9df  sports_prematch.py
e0b7d5992a55607c8b981200b654245b911946bfcf8c061cc205ff1ef98b467c  tests/test_ice_hockey_context.py
98672417b15f51be503ea61f1607418ef0e9c8141b726cf35614a62780808c6a  tests/test_ice_hockey_sources.py
637ce17532b5fd37200a65ea7f954948cb877c574b63cd96d7238d32b9c45ad3  tests/test_ice_hockey_features.py
ab73fd478da902b232916eba14cbc2af79a556a7f67b8a670f469e4bf0b13147  tests/test_ice_hockey_effects.py
13ff68752fc268b781a07210248e3fb87611badf5c1de6c353b64cc9a5208edf  tests/test_ice_hockey_revisions.py
458682d506cbaf5d093144c224a4f43ac8d894d37070a4354a8de27df90782b0  tests/test_ice_hockey_numerics.py
02d3a12972895dfe3ce28201bd4c73ecf666c778c7ef3b5a1b3ea0d387bd891d  docs/audits/2026-09-09-c3-hockey-mechanics.md

474455288448b7c356fb16407b6c87758bcf6969f7aa8a8345d0a796ea03efd0  .pytest_tmp/c3-independent-20260909/test_independent_c3.py
1719483eb41be5f42bc899d2390b1e81b395ff165f6fa54dff53fbc982ec6997  .pytest_tmp/c3-independent-20260909/test_c3_controls.py
c5e6495f7564613f81e2b54ac7728274b7ea1fb151faeefbe2c9e74df04ee4c0  .pytest_tmp/c3-independent-owning-01.xml
0701e5d387ee31293c9663691d41d511ed7c25e26c94dff2478986de84dbfbe6  .pytest_tmp/c3-independent-attacks-01.xml
c39046d2e4c0303daf2d9b5649703ba0dedb6b4c035ded13c9e5976779e29279  .pytest_tmp/c3-independent-controls-01.xml
9c5d46244a8173bd226efabc81c1c2e52ee69f91edf458b8ca4dca1196fba120  .pytest_tmp/c3-independent-shared-01.xml

fc1253fbeb0888870715c21238d4da78de2c0cbe19fee910da67ebfd35b756d7  original sports_prematch.py Git bytes at base
b4e44d03d09a6c8f22ce52568ea36f9af1c7e563d094af98c135703a0a204677  tests/fixtures/context/basketball/sports_prematch_legacy_0d000f6.py
```

The report's own hash is delivered separately; no self-referential hash claim.

## Explicitly still outside this review/packet

No qualified real NHL roster/TOI/starter/end/interval adapter or historical
corpus is demonstrated. The retained schedule-only sample does not become
prospective player evidence. The internal transport explicitly rejects
nonterminal appearances; it is not a live NHL status-capture adapter.
No hockey D1 outcome/identity/case assembly or D2 scorer/real evaluation/approval
exists in this packet, and no actual >=200-event/three-block success is claimed.
Future D3 must use the owning full-lineage reader, not generic latest-schedule
projection. Worker/UI capture, browser appearance, prospective live sampling,
runtime/backup/activation, main merge, push and VPS deployment remain separate.
Neither green synthetic tests nor a valid public content hash establish those
gates. Fix and independently rereview R1/R2 before accepting this frozen packet.
