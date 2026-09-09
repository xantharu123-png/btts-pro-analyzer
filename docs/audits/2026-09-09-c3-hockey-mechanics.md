# C3 Hockey — bounded source/model mechanics

Date: 2026-09-09. Owning worktree:
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-c3-hockey-20260909`.
Branch `codex/kontext-c3-hockey-20260909`; exact base
`13b4dac7e7ef4eba2b235c78d3ad351cf71e456a`.

Status: implementation, final focused tests and final full regression completed.
This packet is frozen for independent review. It is not an empirical/live
approval.

## 1. Authorization and actual boundaries

Read the full approved specification, Task14 brief, context-contract and
validation-contract decisions, controller `task-14-controller-rulings-20260909.md`
and the complete preserved Root C3 preflight. The controller's later rulings
replace the original proposed C2-module reuse: C3 owns the new
`context_models/ice_hockey.py`, not the reviewed basketball model.

No new provider/HTTP call, source budget change, paid source, credential read,
production database, worker/UI, money/15K/settlement change, SSH/VPS action or
push occurred. No helper/updater was changed. No agent was spawned by this
worker. The stored taskwise TDD/review contract was followed directly because
the former Superpowers skills are not installed in this session.

Only three inherited files have scoped additions: the optional original export
in `sports_prematch.py`, the hockey-only B1 family/reference routing, and the
hockey-only B3 comparison/conditional-scenario guard. Generic B1 storage and
freshness, B2 estimation, basketball source/math, D1/D2, Cricket and default
prediction behavior remain unchanged. No hockey D1 flat-row builder was added;
generic binomial fallthrough is explicitly refused for this family.

## 2. Source readiness — NOT an NHL player feed

Root's retained evidence is one historical schedule HTTP200 response, 50 event
summaries, two selected completed January event field-path summaries, **zero**
upcoming player samples and **zero** full player/TOI/starter/actual-end bodies.
It was received in September, not prospectively before those January games.
Winning goalie/scorer fields do not establish pregame starters or a roster.

The new normalizer therefore implements only a closed **internal owning
transport**, `hockey-internal-context-v1`. Its explicit test data are synthetic.
No constructed full hockey fixture is labelled a retained real provider body.
The old URL-safety failure on a documentation lookup is not an HTTP denial or
proof that an endpoint lacks these fields; this worker neither retried that
lookup nor replaced it with an unreviewed source.

The internal envelope is exactly:
`schema/source_schema/kind/event/scope/valid_from/valid_until/data`.
Kinds are `appearance`, `projection`, `starter`, and `availability`. Normalized
B1 payload also contains `status`, derived from its exact Event, because B1
requires a terminal status for workload. It is not a second free assertion.
The `starter` container's B1 kind does not itself certify confirmation: the
owning per-team `confirmed/unconfirmed/unknown` status and exact goalie ID are
always read. Roster, scorer and winning-goalie guesses are not accepted inputs.

Native IDs are exact positive NHL event/team/player IDs. Whole Event includes
participants, native competition, declared format and schedule revision. Scope
explicitly binds season `20252026`, gameType2/3, neutral truth, and the reviewed
`nhl-2025-26-rule84` version. Another season/rule needs its own declaration;
there is no name-based or later-season fallback.

Each appearance carries actual start/end or explicit null, real terminal
receipt, reported regulation and overtime seconds, phase, and both teams.
Three 20-minute regulation periods, regular-season at-most-five-minute OT and
playoff OT/SO distinctions stay separate. Elapsed play is never guessed from
a period label. A cancelled revision cannot contain performed exposure.

Complete usage requires full actual manpower/goalie-presence intervals whose
integrals equal the separately reported individual TOI. Empty-net intervals
are explicit; 5x60 skater minutes or 60 goalie minutes are not imposed. Missing
cells/intervals remain unavailable. Projection is a complete **expected
scenario**, never measured play; it contains no probability weight or OT load.

Public hashes establish consistency, not provider truth. The future owning
adapter must validate real source identities, timestamps, full collections and
the transport's second-resolution exposure before supplying it. This packet
does not prove licensed access, native historic goalie receipts or empirical
coverage.

## 3. Original model and exact reference

The original model is the unchanged penalized, box-constrained Poisson fit:
L-BFGS-B, team penalty5, no nuisance penalty, original bounds and initialization,
ordered home/away scoring rows, and the original fitted home designation term.
It is **not** the basketball Ridge mean/influence formula.

The opt-in `hockey_base_distribution(..., context_event=..., scope=...)` exports
the actual unrounded original parameters, exact five probabilities and the
unchanged old `input_hash` as `model_hash`. The original raw file prefix is
checked separately. Missing neutral/OT/source evidence retains the old model's
own absence behavior. Missing native reference evidence does not discard an
otherwise computed original forecast; the reference becomes `unavailable`.
However, known event/team/start/status contradictions are integrity errors,
even when another provenance field is missing.

The original reference records the explicitly price-free raw sport projection,
all selected native games, source-record hashes, actual fit/recipe and full
Event/scope. The validator reruns the exact original normalization/fit and
compares every reference/base parameter/market byte. A positive numeric ID alone
is not a roster join: the original `history_refs.roster_join` remains unresolved
until the separate owning context receipts establish the lineup link.

Reference variant `hockey-observed-contributing-exposure-v1` is deliberately
**composition**, not optimizer influence, a Hessian/KKT decomposition, causal
player value, or a statement that games influence the fitted strength equally.
For each target team, each distinct contributing native original game counts
once. Exact integer measured regulation seconds are summed before the single
division by game count and3600. A constant repeated exposure therefore has
exact zero current-reference difference rather than a floating-point residue.

Complete measured absence is measured zero; absence from a complete expected
projection is expected zero **in that scenario only**. Unknown cells, missing
reference teams/games and incomplete replacements never become zero. Native
season-scoped skater and goalie vocabularies remain distinct.

`hockey-context-reference-v1` binds `digest(validated original BaseDistribution)`,
`digest(validated full Event)` and the exact sorted preprocessing hash map.
This is separate from the legacy `base.model_hash`. Snapshot identity also
binds the entire FeatureVector, including unused states/refs and coverage.

## 4. Revision, cutoff and observed-load contracts

`hockey_observations_as_of(path, event_key, cutoff=..., schedule_revision=...)`
is the owning read seam. It uses the existing A1 path rules and an actual B1
SQLite snapshot. It retains all causal appearance lineage across old schedule
and participant revisions; current projection/starter/availability must match
the requested current schedule. Generic exact-schedule B1 selection is not a
substitute for this historical pool. The future D3 caller must use this seam.

Values come only from the latest **whole event/kind** revision. Equal-time
distinct revisions conflict. Latest unknown/expired/empty projections do not
resurrect an older healthy projection. A newer incomplete participant change
creates uncertainty for all previously/newly involved teams. Returning a team
in another incomplete revision cannot restore old players or complete rest.
A fully evidenced participant correction may withdraw the old participation.
Duplicate ingestion and later identical receipts never double-weight a game.

Observed workload windows are `[cutoff-Ndays, cutoff)` for N=1,3,7. An actual end
equal to cutoff belongs to the exact-rest timeline but not any performed-load
window. Unknown ends retain their actual terminal-receipt upper bound. A bound
strictly before a window can establish irrelevance there; equality remains
uncertain. A known latest end may establish exact rest only when every relevant
unknown upper bound permits it. Conflicting revisions require strict exclusion
and retain their evidence. These exclusions never repair a required original
roster-reference game. No complete career/team-history claim is made.

Regulation and OT, skater and goalie performed seconds are separate. Exact
rest and receipt-derived lower-bound rest are separate. Travel and medical
fatigue remain null. Raw availability is an observed count, not a hardcoded
injury penalty. The model consumes only declared measured/exposure features.

## 5. Fitted comparison and central selection

Family `ice_hockey:regulation_goals`; original version
`hockey-original-poisson-v1`; feature version `hockey-observed-exposure-load-v1`;
model variant `hockey-role-mirrored-poisson-context-v1`.

Two log-rate heads are exactly one role-mirrored B2 model with matching scales,
coefficients, alpha and sample count under the full feature permutation. The
home equation consumes home attacking skaters, away defending skaters and the
away conceding goalie; the complete role orientation mirrors for away. Own
goalie TOI is not a free own-attacking coefficient. The new synthetic tests
really call `fit_offset`; they do not substitute a fake fitted effect.

The two changed rates generate exactly `home_reg/draw_reg/away_reg` from one
Skellam law. `home_inclusive = home_reg + draw_reg * original_OT_probability`;
away-inclusive is its complement. Original OT is fixed, never independently
fitted, clipped, or averaged across scenarios. No totals/puckline/new settlement
markets or posthoc per-market calibration are introduced. Zero effects preserve
exact original parameter and market bytes. Numerical failure keeps the base.

Closed comparison reference binds the original Base, Event, full FeatureVector
and actual effect payload. B3 additionally compares the externally supplied
objects and verified A1 effect digest. Corrupt data/approval never becomes a
benign fallback. Scope, feature version, population, training cutoff, coverage,
reference, role permutation and operand/reference identities are checked.

Without genuine matching D2 approval the comparison stays experimental and the
central used forecast remains original. A matching **synthetic test envelope**
only exercises that selector; it is not real empirical approval. Conditional
unconfirmed-goalie exposure has the owning B3 experimental guard even with such
an envelope. Under the controller's final ruling, this v1 source is one whole
hypothetical lineup: consuming its skater exposure without its goalie columns
does not confirm the remaining scenario. Such skater-only effects also remain
experimental. A genuinely independently confirmed skater subset would need
its actual separate native source/coverage contract; this transport does not
invent one or reclassify such a future contract. Explicit candidates remain
separately keyed; no .5 mixture or
automatic candidate promotion exists. Observed-load-only effects with no
assumed starter features remain a distinct eligible mechanics path.

The hockey outcome/identity/case/scorer extension, real D1 data assembly,
frozen D2 trials/calibration and runtime activation are separate unfinished
work. The historical baseline's winning-goal subtraction is explicitly labelled
an old baseline assumption, **not** a new measured regulation-goal target.

## 6. RED/GREEN and independent local controls

All runs used the explicit quality Python, `-B`, `pytest -p no:cacheprovider`
and a fresh `.pytest_tmp/c3-*` basetemp. Only this worktree's isolated files were
used. These are implementation-owner tests; an independent agent review is
still required after this packet is frozen.

| Stage | Actual result |
| --- | --- |
| Distribution missing function | 13 RED; then13 GREEN, 0.84s |
| Additive original export | 12 RED/13 existing GREEN; then25 GREEN, 1.25s |
| Closed internal source | 26 RED; then51 combined GREEN, 1.33s |
| Owning feature function | 19 RED; first implementation2 RED/68 GREEN; then70 GREEN, 3.39s |
| Actual B2/B3 application | 27 RED; then27 GREEN, 9.92s |
| Native identity/nested types/no implicit D1 | 11 genuine RED/51 GREEN; then62 GREEN, 1.30s |
| Conceding-goalie role | 1 genuine RED; corrected actual-fit fixture and role guard; 61 math/effect GREEN,14.54s |
| Actual SQLite source/effect/snapshot and revision suite | 41 GREEN/1 Windows symlink skip,7.24s |
| Independent scalar Poisson/joint law and frozen-default controls | 32 GREEN,5.12s |
| Pre-final broad C3+C2+B1+B2+B3+prematch | 995 GREEN/1 Windows symlink skip,78.99s |
| Pre-final full regression | 4436 GREEN/19 skips/97 subtests,278.27s |
| Final whole-lineup guard + malformed routing | 5 genuine RED/1 existing GREEN before final corrections |
| Final broad C3+C2+B1+B2+B3+prematch | 1001 GREEN/1 Windows symlink skip,83.99s |
| Final full regression | 4442 GREEN/19 expected platform skips/97 subtests,303.23s |

The final full command was `python -B -m pytest tests -q -rs -p no:cacheprovider
--basetemp=.pytest_tmp/c3-full-final-20260909-01`. It completed with exit0 against
the exact source/test hashes below. The 19 skips are unavailable Windows symlink
privileges or POSIX owner/mode/umask cases; there are no hockey calculation,
source, revision or approval tests skipped. The one new hockey skip is the actual
symlink-path case; its non-symlink path and database-corruption controls ran.

The first feature round found two implementation edges: floating repeated means
produced a tiny nonzero difference, and an unspecified projection retained an
available state with no numeric value. Both were corrected; the numerical oracle
now independently uses exact Fractions rather than repeating unstable float
summation. The first SQLite command had a missing basetemp parent (42 setup
errors, no source execution); after creating `.pytest_tmp`, its sole initial
failure was the test's positional call to keyword-only A1 `payload`. Neither
harness setup mistake is reported as a source/model defect.

Additional controls include full orientation reversal of the actual original
nonlinear fit and context heads, independent double-Poisson score enumeration,
real fit rate movement, fixed OT and zero effects, full A1→B1→B2→B3→compute-once
roundtrip, same-time conflicts, leave/return participant changes, old schedule
lineage, actual WAL append-during-read, actual corrupted SQLite contents/index/
receipt clock/missing content (before future filtering), half-open microsecond
boundaries and unknown-cell nonzero protections. Direct B3 calls, not just the
friendly facade, reject altered outer/nested inputs and conditional promotion.

The pre-C2 frozen `sports_prematch_legacy_0d000f6.py` SHA256
`b4e44d03d09a6c8f22ce52568ea36f9af1c7e563d094af98c135703a0a204677`
is loaded independently. Fifteen actual prediction cases compare complete
canonical outputs for hockey/basketball/**Cricket**, including normal,
newly imported, neutral, insufficient history and arbitrary extra price data.
Fifty unknown nested price keys on every input record do not change the exact
new export either.

## 7. Exact byte inventory and remaining boundary

The original `sports_prematch.py` at the base commit is 24,369 bytes. Its entire
raw byte prefix is unchanged in the 24,703-byte new file, checked with binary Git
stdout against the actual file, not newline-normalized text. Its only change is
the 334-byte additive export. Existing Cricket and other default code paths are
also covered by the independent frozen-source output checks above.

The controller's fixed Task14 ruling file SHA256 is
`00171138c0d604021c1b0a706e05b3bf6cac1df0c2fb5071e8adfc563a4118ca`.
The later whole-hypothetical-lineup rule was explicitly issued by the controller
during implementation and is documented in section 5 and its paired regression.

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
```

Independent review remains pending. The scoped containing commit and final
report byte hash are reported externally; no push or integration is authorized
by this implementation-owner packet alone.

Unfinished data/empirical/runtime seams are explicit: qualified real NHL
skater/goalie/lineup/interval feed and causal history; hockey owning outcome/
identity/D1 cases and scorer; real D2 evaluation/approval; D3 use of the owning
historical reader, immutable snapshot and labelled scenarios; UI/runtime/VPS
integration. None is supplied by synthetic success, a public A1 content hash,
the old 24-point prequential statistic or a shape-valid test approval envelope.
