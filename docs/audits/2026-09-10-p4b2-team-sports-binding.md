# P4b2 — actual OriginalPrematch to native status binding

## Scope and status

Implemented on parent `4f49a8c86e98d56127f5419d0b63b629997e0712` in
`kontext-team-sports-binding-20260909`. This is a **pure owning resolver**, not
the remaining P4 worker, consumer, transport, restore, or empirical activation.
Only a new resolver, its tests, and this report changed. No source capture,
legacy model, C2/C3, rules, API budget, Cricket, money, or VPS change.

The implementation uses the approved full context-model specification and the
P4a/P4b1 contracts. The P4b1 independent report was read completely; its SHA-256
is `0077a6a06ac391bc5a7cf874fa2ad929d41efa74999f896928f4edadd5b240ca`.
It specifically requires whole causal alias history before exact-ID selection.

All new source-shaped test bodies are **synthetic mechanics fixtures**. They
are normalized and actually persisted through B1 SQLite, then read by the
existing owning reader. They are not authenticated live responses, new
historical source qualification, or measured evidence for an effect. Their
explicit September 5 test clocks are not today's events.

## Approved API and return contract

`context_sources.team_sports_binding.resolve_team_sport_original(original, rows)`
accepts the actual P3 `OriginalPrematch` and the entire already-read B1 team-sport
status pool. It returns detached `TeamSportOriginalBinding` fields:

- `event`: the current canonical native scheduled Event, or `None`.
- `receipt_binding`: unchanged closed P4a `team-sports-live-receipt-refs-v1`
  shape: schema 1, nullable `event_receipt`, `history_receipts` containing
  `{input_index, receipt}`, and empty `artifact_refs`.
- `input_bindings`: target first (`input_index=None`), then **every** original
  `raw_history` position in input order. Each item contains exactly
  `input_index`, `native_event_key`, `match_state`, `current_state`,
  `current_received_at`, `reasons`, `matching_receipt_refs`, and `lineage_refs`.

Version: `team-sports-original-native-binding-v1`. The old receipt, original,
base, C2 and C3 version identifiers and validators are unchanged.

`match_state` is `matched`, `missing`, `unknown`, `conflicting`, or
`not_applicable`. It means correspondence to the actual raw row, **not**
complete source, model-usage, roster, rules, or effect qualification.
`current_state` separately reports the newest full alias-component status as
`available`, `unknown`, `conflicting`, or `missing`. As in P4b1, `available`
means internally consistent reported status, not a freshness or tip approval.
No new TTL is invented. A known started/cancelled status may be available while
the original scheduled/completed raw row is superseded and cannot create an
Event. The real receipt time and explicit reason remain visible to the caller.

Old documentary matches are retained after a correction. They cannot restore
a previous status. A deterministic matching digest is used in each existing
receipt-binding slot; all matching/correcting receipts remain separately in
the whole lineage. References are actual receipt digests, never free
`verified`, source-approval, history-complete, or A1-artifact flags.

This pure function validates receipt bodies, closed outer metadata and digests;
it does not itself open the database or authenticate a caller-supplied pool's
storage origin. The caller must provide the existing owning reader's complete
inventory. A substituted partial pool cannot be detected without that owning
boundary. No consumer may promote this return value alone to D1/D2 evidence.

## Exact identity, revision and clock rules

1. Every claimed record is completely validated **before** source, ID or cutoff
   filtering, including unrelated and future records. Only real
   `observed_at <= original.as_of` receipts enter the causal graph. A future
   receipt never backdates an earlier decision. UTC counterpart and
   microsecond-boundary tests preserve the original clock representation.
2. Native aliases are joined only through actual co-occurrence and exact
   source/sport/field identity. Names, scores, temporal proximity, whitespace,
   casefold and NFKC are never alias evidence.
3. ESPN `competition.id` is primary; co-occurring outer `event.id` is an
   explicit alias. An outer-only withdrawal under another B1 key reaches the
   prior competition before selection. Multiple native competition claims in
   one component are ambiguous, not a default choice.
4. EuroLeague `id` and `identifier` stay distinct native fields. Multiple UUIDs
   behind a shared alias are ambiguous. `gameCode` is scoped to the actual
   request season; equal codes in different seasons cannot join. The B1-only
   season/gameCode composite, without a unique original join, stays unresolved;
   no `Eyyyy_code` identifier is invented.
5. Native status is selected event-wide by actual receipt time. Equal-time
   conflicting full native/projection revisions are conflicting. Equivalent
   native facts from two real request paths are not two events. Duplicates and
   reordered supplied rows produce identical results.
6. The Event keeps the original **selected raw ID**, not a normalized model ID
   or a rewritten native-primary ID. The separately returned primary and full
   lineage document the unique relationship. `schedule_revision` binds the
   complete current binding, native projection and current content, including
   all causal withdrawal/recheck references. Earlier cutoffs stay unchanged.
7. A later identical real recheck may bind today's decision using its actual
   receipt time. A cached `result_observed_at` is not rewritten and is not proof
   of historical availability. Even ignored/future-cache-time raw positions can
   have current documentary correspondence; the original model's independent
   inclusion rules are unchanged.

The resolver selects the same actual raw field priorities as the owning model:
target `starts_at` first, historical `start_time` first; a **present** final-score
alias takes precedence even when zero or null. Missing scores are not zero.
Provider/competition aliases are a finite declaration list of existing raw
forms, not general normalization. Native teams and known contradictions are
checked independently; an unknown team cannot conceal the known opponent's
contradiction.

## Rules and partial-data paths

- Existing basketball formats only: `nba_reg48_including_ot` and
  `euroleague_reg40_including_ot`. These are routing constants, not new proof of
  regulation minutes or a competition-wide rules release.
- Existing NHL scope only: actual native season `20252026` with actual integer
  type 2 (`nhl_reg60_regular_ot_so`) or 3 (`nhl_reg60_playoff_ot`). Preseason,
  2026/27, missing season/type, boolean and floating type declarations cannot
  borrow the old routing. Original data and probabilities survive.
- EuroLeague `played=false` proves only `not_completed`, **not scheduled**.
  Its raw/receipt relationship can be matched and retained, but `event=None`
  with `native-scheduled-status-unconfirmed`. This real legacy partial-information
  path is explicitly tested as original-preserving, not a league/market ban.
- Status receipts do not contain measured regulation rotation, actual minutes,
  TOI, injuries, confirmed goalies, availability, rulebook provenance, or complete
  historical coverage. Matched records retain `native-rules-unavailable`.
  Missing neutral/season facts remain separate from legacy defaults and any
  raw declaration. No missing actual end is estimated.
- Missing receipts from a warm legacy cache yield explicit missing bindings.
  They do not destroy or alter the existing original/model probability.

The output can already be passed to existing P4a builders. Tests execute actual
P3 prediction/capture, resolve actual persisted B1 rows, then build P4a using the
same captured fit. Target `_fit` and `_predict` are forbidden during binding and
construction. Exact original probabilities remain unchanged. An unavailable
model remains unavailable, never 50%. P4a correctly still says
`source_resolution='unresolved'`; this packet does not bypass that existing
boundary or manufacture an empirical approval.

## TDD and focused verification

Commands use the existing quality Python with `-B -m pytest -q -p
no:cacheprovider`, a distinct `.pytest_tmp` base directory and JUnit per run.
Every command explicitly captured and returned `$LASTEXITCODE`.

- `p4b2-initial-red-01`: 20 failed / 32 passed / exit 1, because the new resolver
  API did not yet exist. These are implementation REDs, not 20 legacy defects.
- `p4b2-first-green-02`: 52 passed / exit 0 after the initial implementation.
- `p4b2-alias-red-03`: 9 failed / 79 passed / exit 1. Six actual zero/null final
  score cases and three historical field-priority cases found mistakes in the
  **new** resolver. The persisted native source facts were correct; the new
  reader chose the wrong raw alias.
- Only the new reader was corrected. The same nine tests were unchanged.
  `p4b2-alias-green-04`: 88 passed / exit 0.
- `p4b2-scope-controls-05`: 157 passed / exit 0 after identity, rules, clock,
  data-null, model-null, duplicate, no-IO, price-independence and tamper controls.
- Final focused `p4b2-focused-final-06`: **804 passed, 0 skipped, 36.37s, exit 0**.
  Exactly 139 new permanent binding cases; existing P4a, P4b1 capture/status,
  original-capture/Cricket parity, legacy prematch, C2/C3 and context contracts
  all included. No full-suite claim.
- Separate `p4b2-history-regression-07`: **19 passed, 0 skipped, 0.63s, exit 0**
  against the unchanged completed-history path. In total 823 disjoint final
  focused cases, including 139 new ones, not a production acceptance metric.

Final JUnit SHA-256:
`256c687cb127917e94eb1594f47d300d7304dab069f65544ff738b382049ba26`.
The actual 9-RED JUnit is retained unchanged with SHA-256
`814ae8f76eb3c56a5b4a7959687afec12f91f58287456d672f9905e951d9f98d`.

## Frozen source checks and remaining work

New source SHA-256:
`context_sources/team_sports_binding.py`
`8cce9d9e4b333ecc48bbf289264c5f7e1e5fc305c725b8728a0c025b3eaeee97`.
New test SHA-256:
`tests/test_team_sports_binding.py`
`951bee6afeaca9013bf7f9d2b4702f2aca80ba7dca857d1eba937ebfdd022a78`.

All owning parent source hashes stayed exact, including:

- `sports_prematch.py`:
  `1d908a32d4decdd508477526af9802f3a81bd9054f93636e4df8c63675b9a07d`.
- P4a `context_models/team_sports_live.py`:
  `dcb571b6aaef03a1e18638a8aedfd47841c1317d324f5c0561eab67da8646b8d`.
- P4b1 status:
  `1a11dab252f7a028171f0f85504b00ffce2d42f581f38920e6d7bfa11a4cbb2c`;
  capture: `7201d9d2596a7830485bb744407af9c8a35c5ecc422b0dd2a98c5acb1995c199`.
- C2 `6d93c2b77ce5f0085cb1861edcc9524d3064b84faa772b501bf8481fedfb7228`;
  C3 `5b27b2fc84c354e87e7842e5191658f9aea9f0213f4a9e5e2136270c4f1280d4`;
  contracts `7b3c2a909fee790879d446ef2b95bc944d24951af4261c3296c36e6338518fa8`.

Independent review is still required. The real worker must commit its complete
source-receipt phase, choose a real decision clock after those receipts, freeze
the actual same-call Original, and invoke this pure resolver with the complete
owning B1 inventory. This resolver invents no worker clock and cannot fix a
producer that captures data after an already frozen original cutoff. A1
publication, shared normal/Risk once-only use, Consumer/Transport/D4 known kinds,
real source/rules/player coverage and D1/D2 acceptance remain distinct work.
No provider requests, secrets, push, deployment or server state checks occurred.
