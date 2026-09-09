# C3 implementation rulings — controller, 9 September 2026

The controller read the complete Task14/spec reference, actual C2 interfaces and
the hockey preflight `f2dec7561f3e0c503557774c8ec7530091863f08aa2ebce6db21b7d6b1ebe968`.
This defines the initial CPU model/transport, not a live NHL player adapter.

## Original distribution and populations

Own `ice_hockey:regulation_goals` with positive finite `home_lambda`,
`away_lambda` and separately fixed `overtime_home_probability` in [0,1]. Two
role-mirrored B2 log-rate heads derive exactly `home_reg`, `draw_reg`, `away_reg`,
`home_inclusive`, `away_inclusive` through the existing Skellam/OT formula.
Context does not refit or replace the original OT estimate. No total, puckline,
shootout or live family is certified merely by these five markets.

Initial formats distinguish `nhl_reg60_regular_ot_so` and
`nhl_reg60_playoff_ot`, explicit native gameType 2/3 respectively. Bind actual
season, explicit nonneutral/neutral truth, native competition and source rule
version in the owning scope, never new free Event fields. Unknown gameType,
neutral metadata or rules do not acquire a default in the new reference. Preserve
the old model's own inapplicable-neutral/missing-OT behavior.

The official [2025–26 rulebook, Rule84](https://media.nhl.com/site/asset/public/ext/2025-26/2025-26Rules.pdf)
identifies three 20-minute regulation periods, regular-season five-minute
three-skater sudden-death OT and a following shootout; playoffs use successive
20-minute sudden-death periods. Bind this as the known version, not as proof of
unexamined later seasons or actual player TOI. An unknown/new rule version needs
its own owning declaration and tests; it cannot silently inherit a known season.

Export the original unrounded parameters/market bytes additively, including
the exact ordered native selected history, original actual fit/penalty/bounds,
code recipe and original OT computation. Replay the unchanged constrained
Poisson baseline; do not reconstruct rates from rounded factor descriptions.
Its legacy OT winning-goal subtraction remains an explicitly legacy *baseline
assumption*, never a measured regulation outcome. New training requires actual
regulation period totals, native phase and winner/result evidence. No guessed
goal subtraction or result-history rewrite for context targets.

## First roster reference: observed exposure, not optimizer sensitivity

Choose a deliberately explicit measured-reference variant:
`hockey-observed-contributing-exposure-v1`. For each target team, take each
distinct native contributing game in the replay-verified original fit once and
compute equal-game average **measured regulation** skater and goalie exposure.
It is a historical composition feature anchored to the actual baseline sample,
not a decomposition of the nonlinear Poisson fit and not a claim that all games
have equal influence on fitted strength. Label and bind that distinction.

Do NOT use basketball Ridge weights, unconstrained Poisson inverse-Hessian
weights, positive normalization of signed influences or invented optimizer
stationarity. This initial variant chooses an observed-reference definition;
an analytical constrained-Poisson sensitivity variant would require its own
mathematical contract, bounds/KKT treatment, tests and D2 comparison later.

Use current scenario minus measured historical exposure with separate attacking
skater, defending skater and conceding-goalie roles, in native season-scoped
player vocabulary. Mirror the full role orientation when exchanging teams;
the two rates must exchange and the unchanged OT chance complement. B2 learns
the residual contributions, never imports another sport's coefficients.
Persistent absent exposure can be zero only in complete measured/current
projections; missing player/role/history cannot be filled with zero. A current
projection describes that scenario, not certain future participation or health.

## Source and feature identity

Implement a closed INTERNAL source projection. Required scope is full native
Event/participants, actual season/rules, exact receipt/revision and whole joint
collection. Preserve old participant lineage through real B1 selection while
using only the latest event revision for values; no partial roster stitching.

Measured skater/goalie TOI, current expected exposure, starter confirmation and
unknown participation are distinct records/states. Use regulation seconds/60
or consistently versioned minutes, separately from inclusive observed workload.
Complete exposure needs actual full-interval manpower/goalie-presence accounting
whose integrals match all reported player TOI (including explicit empty-net
intervals). Never impose basketball's 5x60 total or infer full usage from a free
complete flag/roster count. Unknown cells or missing intervals stay unavailable.

Unknown goalie: only explicitly sourced candidate goalie/lineup scenarios with
central base unchanged, unless a real fitted participation artifact exists.
No roster-to-confirmed conversion, winning-goalie-to-starter inference, assumed
60 goalie minutes or invented .5 mixture. Overtime exposure and actual play
duration must be reported, not guessed from scheduled start or period labels.

Observed 1/3/7-day workload/recovery uses strict causal actual ends and half-open
windows; distinguish exact rest from receipt-derived lower-bound rest. Keep
revisions, conflicts and proof refs. A conflict is irrelevant only with all
usable end bounds strictly before that window or separately known latest end.
It cannot heal a missing historical rotation needed for the roster reference.
No forecast schedule becomes performed load, travel or medical fatigue.

## Infrastructure and acceptance

`hockey-context-reference-v1` binds full original Event/Base and actual sorted
preprocessing refs. Require keyword-only Event at application. A narrow owning
hockey comparison/B3 dispatch may replay the nested original/FV/effect binding,
as C2 does; no generic free callback/verified flag or new approval/database.
Without matching actual D2 approval, used parameters and markets stay baseline.
Zero effects preserve their exact original bytes, including the fixed OT value.

Prove real B2 fits and joint distribution movement on explicit synthetic cases.
The closed native hockey outcome/D1-case/identity/scorer extension is a separate
next packet, not football namespace reuse or free flat training rows. No actual
empirical activation follows from CPU tests or the retained schedule-only probe.

Scope: source/model modules, additive old-model export, narrow own-family B1/B3
dispatch, dedicated tests and audit only. Preserve source/default Cricket bytes,
all old outputs, forecasts, tickets, money and settlements. No new HTTP/provider,
UI/worker/VPS or deployment-helper writes. Require RED/GREEN, actual B1-to-B3
roundtrips, partial/current/reference mutations, orientation/OT/score/time
negatives, actual trained residual movement, source replay and default parity,
full regression, exact hashes and independent review before merge.
