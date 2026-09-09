# P4b1 — existing Basketball/NHL native response capture

2026-09-09. Bounded implementation on
`codex/kontext-p4b1-capture-20260909`, base
`1b77286d06f9731c1ffa38ba3d408f20fff1b02e`.

## Disposition and exact scope

Mechanical implementation is ready for independent review. It is **not** a
claim that P4, the runtime consumer connection, native player data, or empirical
context effects are complete. No real provider request, VPS action, production
database mutation, dependency installation, merge or push was performed.
No full suite was run, per the controller's bounded assignment.

The full owning P3/P4 preflight was read before implementing. Its path is
`.worktrees/review-sports-original-20260909/.pytest_tmp/p3-p4-live-envelope-preflight-20260909/PREFLIGHT.md`
relative to the primary checkout; SHA256
`36bf0e24ae63cd6e0bf53128ff1eb69e3279d3e1d6dfa8cd32c9f0e7078a2f7e`.
Source comparisons use the actual newer base above, not the earlier preflight's
source hashes. B1 append/receipt and owning source-contract boundaries remain
unchanged.

## Four actual observer seams, zero new fetches

The only existing-source edits are the observer import and immediately-after-
`response.json()` observations in:

- `_get_upcoming_euroleague_games`: actual request season, season URL,
  `limit=500`, caller search dates, before `played`/date filtering.
- `_get_espn_upcoming_basketball_games`: actual NBA URL and requested day,
  `dates=YYYYMMDD`, `limit=100`, caller search dates, before status/dedup filters.
- `get_upcoming_nhl_games`: actual requested schedule cursor and search dates,
  before FUT/PRE filtering. A cursor does not invent a season or window end.
- `completed_history.fetch_page`: the existing successful JSON body, actual
  provider/key/URL/params, before the result-only parser. Reservation, cooldown,
  request limit, parser result, cache clock and existing error handling stay
  unchanged. Non-BB/NHL providers return before reading any new clock.

The inactive context-variable default returns without a new receipt clock,
database, altered model input, ID, query or callback. Capture is opt-in; this
package adds no worker-wide consumer scope. A capture samples its own UTC clock
after the actual JSON decode, before the lossy parser. It does not use the cache
clock, fixture date, source header or caller-provided historical cutoff as its
receipt time. It requires HTTP 200, the exact request endpoint/query, actual
response metadata and an empty redirect chain before accepting a response.
Unbound responses produce only a closed partial-capture reason, not native
evidence or a new legacy parser/provider error.

The owner drains accepted observations even if later worker code fails. B1
append failures propagate after leaving legacy network/parser catches; they
are not translated into a healthy cache or missing-source fallback. Capture
ownership resets before persistence, rejects nesting, and is thread-local.

## Closed native receipt contract

`source_schema=native-team-sport-status-v1`, `kind=event_status`,
`format=native_event_unqualified`, `complete=false` in every receipt.
The payload is exactly `{request, native, projection}`. This is an explicit
allowlisted native lifecycle/identity projection, **not an arbitrary raw JSON
archive**. Unknown values in known status/identity fields survive; malformed
shapes use a closed `invalid_shape` marker. Unreviewed extra fields, especially
prices/bookmakers and secrets, do not enter a model or receipt identity.

The request contains provider/source/sport/competition, exact endpoint/params,
schedule-or-history phase, actual history key, request-season when present in
the real EuroLeague URL, requested window and separate search window. The owning
validator reconstructs this entire closed request. No caller-supplied `verified`
flag or public hash qualifies an external source.

Native projection retains case and original JSON ID types in its explicit
aliases. Numeric ID spellings are not casefolded, NFKC-normalized, trimmed or
inferred from labels. Core event/team keys are source- and sport-namespaced:

- ESPN uses actual `competition.id`; outer `event.id` is a separate,
  actually co-occurring alias, not an assumed equal ID. A missing competition
  can retain an outer-ID-only correction, explicitly marked unresolved.
- EuroLeague preserves actual `id`, `identifier`, `gameCode` and request season.
  Per the explicit controller ruling, gameCode-only rows get the **B1-only** key
  `euroleague:basketball:season:E2025:game:406` when both season and code are
  actually present. The legacy ID is never changed; no `E2025_406` is invented.
  Composite-only identity stays explicitly unresolved for C2.
- NHL preserves actual ID, native season/gameType/schedule-state and both teams.
  Season or ID digits do not establish regulation/OT rules. Missing neutral
  remains null; an actual false value remains false.

All supported source fields of each event revision are bound together, including
participants, schedule, scores and status. Opposing equal-time revisions remain
conflicting. Unknown status, malformed participants, winner/score contradictions
and impossible terminal timing retain the event and withdraw an available
status claim; they do not reactivate an older valid-looking row. Cancellation
is a reported lifecycle value, never a healthy player/forecast claim. EuroLeague
`played=false` is only `not_completed`, not a made-up scheduled status.

No actual end, minutes, TOI, regulation exposure, injury, confirmed starter,
NBA season, complete historical coverage or empirical effect is invented.
An observed NHL winning-goalie field is merely retained result metadata; it
does not identify the next starter.

## Read and selection APIs; explicit P4b integration boundary

`capture_team_sports_worker(path=...)` returns a collector whose post-scope report
contains schema/scope/status, sorted receipt refs and closed reasons. `captured`
means receipt capture occurred, **not** all games/data/sports are complete or
fresh. Partial rows and unidentifiable events produce `partial`. Empty capture
does not certify missing-data health.

`team_sport_observations_as_of(path, cutoff=...)` uses the existing trusted live
readonly SQLite transaction. It decodes physical B1 rows and verifies actual
receipt/content hashes, SQL index identities and full owning reconstruction
before source/cutoff eligibility. Known malformed receipts fail typed integrity
validation. It returns the **whole causal native lineage across schedule and
participant changes**, not a destructively filtered latest-only pool. It does
not create an absent database or import old CompletedHistoryStore rows.
It is not the sealed offline restore verifier: trusted live WAL synchronization
retains the existing reader semantics.

`select_team_sport_status(rows, cutoff=..., event_key=...)` is only a pure
exact-native-key selector. It preserves equal-time conflicts and validates rows
before filtering. Its `available` means this reported native status is internally
consistent, not that a source is fresh, a fixture is eligible or an injury effect
is approved. No freshness or new staleness policy is invented here.

**Still owned by the P4b controller:** resolve the full pool to actual P4a raw
inputs, including cross-ID aliases, ESPN competition/outer-ID changes and known
case/normalization collisions. A shared EuroLeague alias under two native UUIDs
is preserved as two rows; this small selector does not certify a join between
them. The controller must not use it alone as a `resolved` source flag. Until
the owning alias/rules resolver is bound, P4a preserves `event=None`/unresolved
originals. `history_receipts.input_index` must refer to the original raw_history
index, including ignored/revised rows, not a normalized match index. This seam
and the composite-ID ruling were communicated directly to P4a's owner.

No generic B1 schema, model, B3 transport, D1/D2 approval, D4 capability list,
consumer, ranking, price, 15K, Cricket or updater code was changed.

## TDD and verification evidence

All provider-shaped fixtures here are synthetic mechanics inputs, reusing the
existing schema fixtures; they do not constitute new authenticated live-feed
or empirical evidence.

- First run `01` had ten **setup** errors from a missing `.pytest_tmp` parent;
  it is preserved but is not counted as functional RED evidence.
- `02`: six genuine existing-JSON capture assertions RED, four inactive/Cricket
  controls green, with executable normalizer stubs; `03`: ten green.
- `04`: ten genuine REDs/50 green for dropped malformed ESPN status,
  contradictory winners, and impossible finish/start timing; `05`: 70 green.
- `06`: 101 green including actual GET/JSON/receipt/parser ordering, missing
  redirect metadata, exact response URL/query, warm cache, exception draining,
  existing failure budget and collector reset.
- `07`: one RED/108 green for huge invalid scores dropping known identity.
  `08`: four RED/106 green including a second numeric boundary and explicitly
  typed owning integrity errors. `09`: 223 focused/new-and-legacy green.
- `10`: 34 direct-parent controls green. The QA module loads the **actual**
  frozen Git source blobs. Whole-module AST equality after removing exactly the
  declared observer seams proves no other scanner/history semantics changed.
  Real old/new calls compare serialized outputs, native IDs, request args,
  cache clock counts and error dictionaries, both capture-enabled and disabled.
  Cricket's actual completed path is byte-identical in both modes.
- `11`: 262 focused green including real SQLite corruption and concurrent
  independent owners. Final malformed UTF-8/nonfinite selected-record probes
  first reproduced `12`: three RED/110 green.
- Final `13`: **265 passed, zero failed/skipped, 6.13 seconds**: 159 new permanent
  capture/status tests, 72 existing relevant history/model/original controls,
  and the 34 direct-parent QA cases. No full suite.

Final invocation, from the owning worktree:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests/test_team_sports_capture.py tests/test_team_sports_status.py tests/test_completed_sports_history.py tests/test_sports_prematch.py tests/test_sports_prematch_original_capture.py .pytest_tmp/p4b1-owner-20260909/test_actual_legacy_parity.py --basetemp=.pytest_tmp/p4b1-final-focus-13 --junitxml=.pytest_tmp/p4b1-final-focus-13.xml
```

## Frozen file SHA256

| File | SHA256 |
| --- | --- |
| context_sources/team_sports_capture.py | 7201d9d2596a7830485bb744407af9c8a35c5ecc422b0dd2a98c5acb1995c199 |
| context_sources/team_sports_status.py | 1a11dab252f7a028171f0f85504b00ffce2d42f581f38920e6d7bfa11a4cbb2c |
| scanners/basketball_scanner.py | faa71900c0c22f78c4aaffc75c8a10e61d16a0077427f1274c915915ea36bc6d |
| scanners/completed_history.py | cf9b7354226f0192d4e3fb6d5324bebc86d4e8541ca3ab4a71fe620fbe7ad96a |
| tests/test_team_sports_capture.py | b9c0a1db5184d704d3558adba03122b8c2a8e0b74963fceea78ecdfbdf38eaf4 |
| tests/test_team_sports_status.py | fee1d400a73c931336ac1a44c0ac0d811611897e9474a6c40b18d7861a896d04 |
| .pytest_tmp/p4b1-owner-20260909/test_actual_legacy_parity.py | d6b1d1a1c2ac99019de4f3154622ae8bfebfa0dd427606f3c8faebbc7ee487a3 |
| .pytest_tmp/p4b1-final-focus-13.xml | 655bc778a87ab95249543db6107abd4759fbe20b595019699f5319c39268354c |
| .pytest_tmp/p4b1-first-red-02.xml | b3dd93dbadefe751e09504c4ae64347329ba16c34bdf8b4debdb8411324d56d5 |
| .pytest_tmp/p4b1-status-red-04.xml | 416134034acbe1401b72787cd2666c79338d56b20790fae37404f3b12c1a2bae |
| .pytest_tmp/p4b1-typed-red-08.xml | 1c8428c8d7575458c9c23311bedb186c4ae830a8c9721fa99697dce5f5d3b55d |
| .pytest_tmp/p4b1-final-edge-red-12.xml | 4ab81bc0f9bb414bc11f311ea3c511e2939bd3a7100e2b53ee49d4ac7a745fc4 |

The audit's own hash and final scoped commit are reported separately to avoid a
self-referential hash. Original RED XML and direct-parent QA remain ignored and
preserved. Independent review, root integration and later production readiness
are separate gates, not claimed by these mechanical tests.
