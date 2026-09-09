# C3 — independent-review corrections R1/R2

Date: 2026-09-09. Owning worktree:
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-c3-hockey-20260909`.
Correction base: `6b2473bef75f08c8d7452a71f69095e932001501`.

This is a narrowly scoped implementation-owner correction packet, not an
independent approval, newly qualified source, empirical effect or live release.
The original implementation audit remains historical evidence for its own
frozen bytes; this document identifies the subsequent changes and tests.

## Read and reproduced

Read the complete independent review and both preserved probe files under
`.pytest_tmp/c3-independent-20260909/`. Reproduced the original package before
any source change: **5 failed / 46 passed**, 5.07s. These are the review's two
expired/future-valid cancellation cases and three native team/game-type cases.
Neither original probe file nor the independent report was modified.

The controller explicitly authorized both bounded corrections. No additional
contract decision, source, coefficient, generic B1 change, prediction default,
Cricket, money, worker/UI, helper, server or provider work was introduced.

## R1: only a usable cancellation can withdraw participation

Previously `_selection` correctly classified the latest cancellation as stale
when its validity had expired or had not begun, but then skipped the uncertainty
branch solely because the raw status was cancelled. This could promote an older
match into a falsely exact latest-match recovery assertion.

The cancellation shortcut now additionally requires its owning state to be
`available`. An unusable latest cancellation enters the existing whole-event
uncertainty machinery exactly like any other unusable latest appearance. It
retains all old and newly named participants and all actual receipt proof. It
does not resurrect the prior completed revision, reinterpret the scheduled time
as actual end, or borrow an unavailable cancellation's terminal bound. Existing
uncertainty therefore prevents exact/minimum recovery and complete observed
load claims where that fact cannot be excluded.

An actually effective cancellation still legitimately withdraws participation.
The separate actual receipt cutoff remains causal: a cancellation received
one microsecond after cutoff does not suppress the earlier known completion.
No generic B1 validity/freshness rule or the half-open workload windows changed.

## R2: validate the original model's actual selected identities first

The original algorithm's `_team` has existing primary/fallback ID precedence.
The old guard checked only raw primary IDs, so a known positive native fallback
`team1_id`/`team2_id` could compute one team's model while the supplied Event
named another team. The revised guard inspects the actual selected original
`identity.home`/`identity.away` `id:<positive integer>` value before entering
the benign unavailable-reference catch. It preserves original precedence;
an unconsumed conflicting fallback does not displace a present primary ID.

This guard does not turn name matching, arbitrary aliases or the original
text normalization into verified roster provenance. Only the existing strict
native reference builder can establish its own reference, and matching ID
fallbacks with missing native metadata still keep the original distribution
with `reference_weights.kind == unavailable`.

The known actual original `identity.variant` is also compared to the declared
Event format's NHL game type before the catch. A known preparation/regular/
playoff model cannot be silently relabelled by a missing rule or missing scope.
Matching regular/playoff originals remain available with absent reference
metadata. Original model fitting, selected games, parameters, OT law, markets
and `model_hash` are not recomputed under a different formula.

## Permanent tests and evidence

One new permanent module contains **47 cases**, all using the existing quality
Python with `-B`, `pytest -p no:cacheprovider` and unique basetemps:

- Both team sides at `valid_until` and `valid_from` cutoff -1/equal/+1 microsecond.
  Invalid withdrawals retain all proof, no exact/minimum recovery, and no
  complete regulation/OT window claim for each 1/3/7-day window.
- Invalid cancellation with a changed participant binds uncertainty for both
  former teams and the newly named team; it does not invent an exclusion bound.
- Independent actual receipt -1/equal/+1 microsecond controls preserve effective
  cancellation versus future-receipt behavior.
- Actual SQLite -> owning feature -> genuinely fitted B2 recovery heads ->
  A1/B3 facade. Both unapproved and synthetic shape-approved paths stay
  `not_applied` with exact original markets/parameters when the consumed
  recovery is now unavailable. This CPU approval is not real D2 evidence.
- Known positive fallback identities with None/empty/zero/false primary fields,
  both sides; unconsumed fallback precedence and matching fallback controls;
  actual legacy output/model-hash and caller-byte preservation.
- Actual model types1/2/3 against both declared regular/playoff formats, with
  and without supplied scope. Each original is first shown to compute; known
  contradictory populations reject before fallback and matching ones retain
  exact original output.

| Run | Actual result |
| --- | --- |
| Unchanged original independent package, `c3-owner-rerepro-20260909-01` | 5 RED / 46 GREEN, 5.07s |
| New permanent cases before source changes, `c3-correction-permanent-red-20260909-01` | 30 genuine RED / 17 GREEN, 4.65s |
| New permanent plus unchanged independent cases, `c3-correction-green-20260909-01` | 98 GREEN, 7.88s |
| Shared C3/C2/A1/B1/B2/B3/default-prematch focus plus unchanged independent cases, `c3-correction-shared-20260909-01` | 1125 GREEN / 5 expected platform skips, 92.47s |

The five skips are one unavailable actual Windows symlink privilege and four
POSIX-only umask/permission cases. No correction, source, math, collection,
approval or legacy-output case was skipped. The shared run also re-executed all
15 frozen legacy output comparisons, including Cricket.

There were no setup/import errors or weakened assertions in these correction
runs. The earlier full 4,442/19/97 implementation result is not relabelled as a
new post-correction full-suite result. The independent reviewer will verify
this exact correction packet separately.

## Frozen byte inventory

Only one production file changes, plus the new permanent module and this audit.
Source/test hashes after corrections:

```text
f96869c1e38efc7a834d691693ce133d127de60d8d5789a588c1e40c67bd6275  context_models/ice_hockey.py
5aaa8e9d97e5101a377e61b1c70fcda0b51484d1cee06e8e1241e4aa60bb1a09  tests/test_ice_hockey_correction_boundaries.py
```

Unchanged owning boundaries and original independent evidence:

```text
b32f01b4fe6bd88eeeced71baade95a2d6e5215879c0e58ba097fdf2f72e1bf7  context_sources/ice_hockey.py
02f8b066319cab8e45a181e12a2ef8abf684c0dcd760c4f55a6244b9790edc34  context_models/contracts.py
414a7d198769546751e0407fd89a6e6edcd6892f9c86df83fdb3cc706955e8bb  context_snapshots.py
ef393f89ca54489bab28aae6c8d224012961795e387bc272d78ba7cad264a9df  sports_prematch.py
0e1cf6cba1875b68a2f810e46d938bcae50826a5308400e4db14ae15b391388b  .pytest_tmp/c3-independent-20260909/REVIEW.md
474455288448b7c356fb16407b6c87758bcf6969f7aa8a8345d0a796ea03efd0  .pytest_tmp/c3-independent-20260909/test_independent_c3.py
1719483eb41be5f42bc899d2390b1e81b395ff165f6fa54dff53fbc982ec6997  .pytest_tmp/c3-independent-20260909/test_c3_controls.py
```

The shared run completed on these exact source/test bytes; this packet is now
frozen for independent rereview. The containing scoped commit and this audit's
final hash are reported externally. No merge, push, deploy, new provider query or production
SQL operation was performed. Real hockey feed qualification, historical
corpus, owning D1/D2 empirical approval and D3/runtime integration remain open.
