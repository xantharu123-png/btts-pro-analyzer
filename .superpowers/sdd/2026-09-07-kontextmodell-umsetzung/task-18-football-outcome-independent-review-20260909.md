# Independent review: existing football FT outcome capture

Date: 2026-09-09. Reviewer: `b6_tennis_load_20260909`, independent of the
controller who authored this packet. Decision: **NOT ACCEPTED pending the one
owning integrity correction below and an unchanged-probe re-review**.

## Frozen target and actual scope

- Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-football-outcome-capture-20260909`.
- Exact clean commit: `684865e583bcf4377df588aaa911b23832f23e57`.
- Three changed files and the whole diff read, including the full owning audit.
- Also read the existing B1 SQLite schema, `_SELECT`/`_decode_receipt`/append
  boundary, the actual dataset `_reader`, native football `_detail_event`, full
  owning base/result normalizers and validators, actual provider callback and
  current FT-tail/season callsites, D3 controller rulings and test-fixture helpers.
- Target source, permanent tests, audit and Git remained unchanged. The only
  authored files are this ignored review directory's probes/report. All database
  mutations happened in dedicated pytest temporary databases.
- No provider, VPS, push, merge, money, Cricket or runtime artifact action.

| Frozen file | Raw SHA-256 |
| --- | --- |
| `context_sources/football_capture.py` | `030d20c2114bffdea53c23556d8367181efa4c84df2257ec9761f63a61bff0ac` |
| `tests/test_context_football_result_capture.py` | `ba4bbd37a64829071266e91ccbf21ca306295917b04274b2c494b3f744856799` |
| `docs/audits/2026-09-09-football-ergebnis-capture.md` | `35580cacc3f6077bb6f5506cb057324d53151da0a83cfa0a9aada8026c6fe2e8` |

## F1 — P2: unverified source/kind indexes hide a corrupt native watch

Location: `context_sources/football_capture.py:76`, in
`_previous_prematch_observations`; downstream publication at `persist:169`.

The reader applies `WHERE r.source='api-football' AND r.kind='base_fixture'`
before `_decode_receipt` compares those index fields with the actual canonical
content. Changing only one of these two SQLite index columns on a genuinely
persisted prematch base receipt removes it from the validation inventory.
Neither the content nor receipt digest needs to be changed. The stored mismatch
is then mistaken for a missing watched event instead of propagating an integrity
error. The other tested index columns correctly reach `_decode_receipt` and fail.

Six independent repair-expectation tests fail on the frozen source:

1. Change only `source` to `espn` or `API-FOOTBALL`: expected integrity error is
   absent (two cases).
2. Change only `kind` to `match_outcome` or `other`: same failure (two cases).
3. Preserve a second valid prematch watch while hiding the first through either
   column: the corrupt database is still accepted and new rows are published
   (two cases).

Concrete damage is separately verified by two *positive defect witnesses*, not
misreported as green repair tests:

- Sole hidden watch: its authentic fetched FT is omitted. Report is
  `status='no_receipts'`, empty issues/refs, while the legacy source still returns
  the expected FT. Content/receipt counts remain **3/3 -> 3/3**. Nothing reports
  the already existing index corruption.
- A second valid watch: report is `status='captured'` with no issues. Four new
  receipts and contents are published: **4/4 -> 8/8**. Only native fixture `99`
  receives an outcome; the corrupted original fixture `1575469` is silently
  omitted. This disproves the claimed fail-before-publication boundary.

This does not manufacture an old prediction join or change a wager. It breaks
the new live ingestion integrity contract and can silently remove results from
the later evidence pool, including while reporting successful capture. The
controller has accepted this finding and will make the correction; this reviewer
has not changed the implementation.

Narrow remedy: validate the full actual B1 receipt inventory with the existing
index/body identity validator before selecting source/kind/schema. Do not turn
invalid stored rows into empty scope. This is explicitly an owning live reader,
not a D2 label-free pre-opening helper. No B1 schema or source entitlement change
is necessary. Repeat the six frozen repair-expectation probes unchanged after
the fix; the two defect witnesses should then stop observing the bad state.

## Independent controls and actual results

`test_independent_result_capture.py`: **6 failed / 56 passed**, 4.94 seconds,
no skips. There were no collection/setup failures or expectation rewrites.
The passing cases cover:

- strict complete envelope: missing/null/string errors, count bool/float/mismatch,
  invalid/null/extra-field/paginated paging, invalid row shapes;
- true integer HTTP 200, native ID/league/season types, goals null/bool/float/
  negative are not accepted as observed results;
- mixed FT responses containing unobserved AET/PEN/NS/TBD/PST/cancelled/started
  identities reject the entire response before appending the watched fixture;
- actual local date boundary (22:15 UTC belongs to the next Zurich date),
  malformed SQLite, missing B1 tables and corrupt watched BLOB propagation;
- actual fetched schedule/participant/league corrections can be retained by
  native watch ID, but the owning outcome validator rejects each against the old
  frozen prediction event;
- simultaneous differing terminal outcomes both remain append-only, original
  canonical receipt bytes remain unchanged;
- unobserved result-only runs create no database/file, and the successful
  read-only watch inspection leaves the prior database main-file bytes unchanged.

`test_damage_witness.py`: **2 passed**, 2.13 seconds, no skips. These are
diagnostic confirmations of the defect above. Their actual reports and counts
are retained in JUnit properties in `damage-01.xml`.

Existing affected regression files, executed by this reviewer on the same
frozen source: **426 passed**, 8.06 seconds, no skips:

```text
tests/test_context_football_result_capture.py
tests/test_context_football_capture.py
tests/test_context_observations.py
tests/test_context_outcomes.py
tests/test_football_context_provider.py
tests/test_football_context_sources.py
tests/test_workflow_integrity.py
tests/test_market_scope.py
tests/test_wettfinder_automation.py
```

The owning previous 426-green report was not used as a substitute for this run.
No full-suite run was requested or needed for this bounded independent packet;
the integrated full suite and eventual production evidence remain separate.

## Reproduction and frozen artifacts

Run from the exact target worktree with the shared quality Python:

```text
python -B -m pytest -q --tb=short -p no:cacheprovider
  .pytest_tmp/football-result-independent-20260909/test_independent_result_capture.py
  --basetemp=.pytest_tmp/football-result-independent-run-01
  --junitxml=.pytest_tmp/football-result-independent-20260909/results-01.xml
```

Use a fresh basetemp/XML name for a rerun. Probe ROOT resolves from its actual
two-level relative location; if reviewing a separate fix worktree, copy these
probe bytes unchanged at exactly the same relative depth and verify the hashes.

| Review artifact | SHA-256 |
| --- | --- |
| `test_independent_result_capture.py` | `45f89ca10ff8d1a18ce134cbeea8b07f02ac68e89a730ecc7cbb25184547dc49` |
| `test_damage_witness.py` | `620fc493a4492bacc1bf113c1d10ce3c596bfa3d7ad2518d38b1406146053625` |
| `results-01.xml` | `15f956b9129b384c8c2971bcd4f69e97412c4fc6ea557f5ff959f7e8ee3cd27f` |
| `damage-01.xml` | `c3edb96d55c0d8a811a4b1a7bea0ae28f91ac552c20d3fe93d85d9e06cc4ee47` |
| `focus-01.xml` | `6e5d2c272f9fd85027528f49ed2bdc166cb6c3fed54a4d0850b714b9e4b9ddad` |

## Limits, not additional findings

The original sanitized NS detail supplies a preserved native source shape.
Every tested FT score, correction, malformed reply and clock scenario is
synthetic; no live FT response or empirical betting improvement was measured.
Watch identity intentionally limits capture only, not old schedule/participant/
model compatibility. Whole-history storage is not a new terminal-status polling
channel; only the already executed FT-tail/season requests are observed. No new
endpoint, watch table, historical-publication backdating or medical/match-duration
inference is claimed. Missing/unwatched source remains missing.

The default provider's raw-return behavior and the unchanged worker/money/model
tests remain separate from context capture validity. Passing those controls does
not erase F1. The six RED probes and both diagnostic witnesses are frozen as
authored and will not be rewritten to fit the repair.
