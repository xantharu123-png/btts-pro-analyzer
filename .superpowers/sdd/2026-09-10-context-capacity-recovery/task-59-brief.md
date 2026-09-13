## Task 59: Deterministic bounded seven-day QA profile inputs

**Scope and placement:** Task58's actual isolated small ATP/WTA/rollback chain
passed on reviewed588843d; see task-58-native-evidence-20260913.md. The next
full C build needs concrete input and consumer scheduling, not another small
guard review. Build only its pure, explicitly synthetic QA input generator in
`tests/context_growth_profile.py`, tests in `tests/test_context_growth_profile.py`,
and `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-59-report.md`.
No product source, existing tests, filesystem owners, guard, catalogue, limits,
frozen specs or other reports may change. No Git/index/server/network/install/
cleanup/subagents; Root owns commit/review/native integration.

**Binding contract:** C spec SHA08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba
and B spec SHA498e63c5641adaccdd4d284fa9b57ad93c02ba834e9abd6bf4064636d6b12da1
are approved. This generator is DATA ONLY: it does not establish a sealed
baseline, collision freedom against old rows, model-state binding, Source/D2
authority, a finished corpus, native capacity, B or empirical approval. Those
are subsequent integration owners. No receipt/Original/snapshot count is
claimed merely from an iterator or descriptor.

**Required interface:** expose `build_growth_profile(kind, *, baseline_sha256,
start_at, first_native_id, atp_fixture, wta_fixture)` returning a bounded
immutable/repeatable profile with `iter_receipts(start=0, stop=None)` yielding
actual `(normalized_record, observed_at_datetime)` pairs; `iter_schedule()`
yielding inexpensive metadata for all planned additions; and `consumers()`
returning at most168 immutable descriptors with ordinal, tour, native fixture,
tournament/grouping, observed_at, cutoff, created_at, surface/best_of/indoor.
Declare precise seed/descriptor types and shapes in the module/report before
coding. Tour seed data describes a scheduled native singles competition and
explicit prediction inputs; use real status normalization to reject malformed
seeds, not hand-written substitute validation. Freeze/copy nested inputs so
caller mutations and returned-object mutation cannot change later emissions.
Keep atp_fixture/wta_fixture optional only for tours absent from the selected
new profile; a required tour's missing fixture is an explicit error.

**Exact full plan, not customizable reduced acceptance:** kinds `atp-heavy`,
`mixed`, `burst`; seven days,70000 additions/day,490000 additions total. Each
day24 new consumer statuses INSIDE its70000, not70024, on14tour/cutoff keys.
ATP-heavy and burst: all new rows ATP, ten double-consumer groups plus four
singles per day. Mixed:35000 rows and12 consumers per tour/day, seven keys per
tour/day (five doubles plus two singles). Existing baseline/WTA rows are never
removed by this generator. With the actual baseline this is590553receipts,
199Originals and separately199snapshots,114tour/cutoff keys; the generator
must label these final values as targets, not observed stored counts.

**Deterministic identifiers/clocks:** require a valid SHA256 baseline label,
aware UTC start_at and positive integral first_native_id with room for all
490000 distinct sequential numeric competition IDs inside signed64-bit range.
No random source or current-clock reads. Each ordinal owns exactly one unique
new native event. Root later verifies the complete chosen namespace and clock
range against the actual held baseline; no such claim here. `start_at` is
already chosen after the baseline by that future owner. Derive all dates from
it, never the earlier hardcoded September test clocks. Preserve supplied seed
player IDs/names for consumers; ordinary filler participants may use bounded
deterministic synthetic identities but must remain genuinely normalizable.
Do not change any legacy native-ID/parser bounds.

Non-burst observations are in deterministic chronological insertion order;
consumer rows may occupy each day's final24 positions. Put their reception
before their owning cutoff and schedule after it: observed_at <= cutoff <
scheduled_start and created_at >= cutoff. Every day/tour has the exact distinct
key/group multiplicities above, with no collision across days/tours. In mixed,
globally distinct clock values are preferable so timestamp count is not
mistaken for tour/cutoff count. Multiple consumers at one cutoff have different
event IDs, not an ambiguous same-event revision.

Burst must implement a real distinct receive/insertion sequence: ten7000-row
receive-time buckets per day with equal clocks inside each bucket, inserted
in the fixed bucket order(0,2,1,4,3,6,5,8,7,9). This produces actual backward
clock transitions and ties, not just a profile label. Its24 consumer rows
remain within the final bucket, and fourteen distinct cutoffs follow that
bucket's receive time but precede those consumers' scheduled starts. Document
the exact generated schedule; equal clocks never create duplicate receipts.

**Actual records and bounds:** call unchanged `normalize_tennis_status` for
every emitted status and require exactly one scheduled status (no fabricated
hash envelope or omitted paired terminal data). No odds, injury weights,
provider calls or model approvals. No eager list/set/tuple of490000 rows or
IDs, no cached receipt history. Store only bounded seeds and the168consumer/
98key schedule, or derive those arithmetically. A start/stop slice is an
explicit diagnostic subset and must never label itself full completion.
Bad kinds, bool/noninteger indices, noncanonical IDs, missing required seeds,
naive/non-UTC clocks, arithmetic overflow and malformed status/participants
must fail before receipts are partially produced when prevalidation can know
the error. Existing old payload/value limits are not modified.

**TDD and verification:** red before implementation; use real normalization
and actual physical `_decode_receipt`/source validator on emitted bytes for
representative boundaries and all168consumer statuses of each profile.
Independently enumerate the cheap complete schedule for all three profiles
with bounded counters: exact daily/tour/consumer/key multiplicities, sequential
unique ordinal/native ID mapping, actual burst ties/backward transitions,
consumer membership inside total, deterministic repetition, correct slices,
mutation isolation, invalid inputs and clock overflow. Do not normalize all
1.47million rows merely for the unit suite; cheap schedule enumeration is not
a full stored/native-profile pass. Tests must clearly distinguish these claims.
Use existing QA Python; no new packages. One final focused module run with
plugin autoload/bytecode/cache disabled, fresh basetemp/XML and a bounded
subprocess timeout; capture actual exit AND stdout/stderr/session metadata.
Do not lose the outer exit as in the older Task58 local run. No unchanged
whole-suite rerun. Report RED/GREEN commands/results, exact changed-file/XML
hashes, interfaces, known limits and explicit return of sole-writer authority.
