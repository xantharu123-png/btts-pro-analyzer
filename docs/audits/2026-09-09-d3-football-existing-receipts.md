# D3 football: preserve actual existing context receipts — 9 September 2026

This bounded worker packet reuses the existing API-Football requests. It does
not qualify historical injury effects, add queries, resolve a new original
model family, change forecasts, or complete D3/shared consumer integration.

## Owning path

Only automatic football discovery, its context refresh, and the manual football
scan enable `capture_football_worker` around their existing provider work. The
default ChallengeDataProvider and 15K/render paths remain disabled. Existing
`_football_get` records the actual successful response envelope with the actual
receipt clock before returning legacy rows. Its capture-enabled HTTP call does
not follow redirects. There are no new requests, retries, source credentials,
quote dependencies or provider budgets here.

The observer accepts bounded explicitly requested native IDs. Already-fetched
native scheduled league discovery is joining material for those IDs only;
discovery alone writes no database and does not duplicate a league history.
Complete native envelope, HTTP 200, exact request scope, unique native fixtures
and event identity are checked. Missing requested fixture rows retain actual
valid rows with a partial administrative report. Failed envelopes make no source
assertion; successfully empty injuries still declare incomplete coverage.

Original native details may yield B1 base/lineup/appearance/result records only
where their owning existing normalizer permits it. Injuries require a complete
native event identity already received by the injury receipt clock. A later
detail cannot backdate that binding. Simultaneous event conflicts are not
resolved by array order. No receipt clock is replaced by flush time; no fetch
is given an invented publication time or historical availability proof.

Valid already-received records drain on a later worker exception; the observer
is always removed. Each response is normalized before any of its observations
are appended. Existing B1 append remains individually atomic/idempotent, not
a new all-source transaction. Partial append remains incomplete evidence.
Actual storage-integrity errors propagate and are not source-unavailable flags.

The closed optional `context_capture` report retains actual receipt references
and static capture issues in internal worker/state data. It does not enter
ordinary errors, operational counters, model ranking or tip eligibility. Old
snapshots without it retain exactly their existing fields, not a new null. The
report is detached and accepts no arbitrary free-text/provider metadata.

## Tests and exact freeze

28 new permanent cases in `tests/test_context_football_capture.py`. Actual GET
seams and all three real worker entries use synthetic native response envelopes
and real isolated SQLite; no real provider capture is claimed by those tests.

- Initial absent-module RED: 10 failed / 1 control passed; pure hook then38 green.
- Actual worker-entry assertions first had 3 fixture import errors (`app_config`
  vs actual `config_loader`); corrected fixture then3 genuine missing-capture
  REDs, resolved by the three narrowly scoped wrappers.
- Actual source gap polluting the legacy provider error list: 1 true RED, fixed
  by separate capture diagnostics. No model error rule was relaxed.
- Persisted report/closed metadata: 5 true REDs, then344 existing/new tests green
  with32 subtests in13.15s.
- Missing requested native detail: 1 true RED; valid returned receipts retained
  and report becomes partial. Final focus **397 passed /32 subtests**,13.95s,
  `context-capture-final-focus-20260909-01`.

Final focus includes existing source-provider, automatic/manual workflow,
challenge and market-scope tests. The integrated D2 evaluator's70 tests also
passed independently in Root in471.59s. A new Root full suite is running on
these frozen capture bytes; its result will be recorded separately, not assumed.

| File | SHA256 |
| --- | --- |
| context_sources/football_capture.py | 4cfc0500a823e8268d38baa11298e5db6029a6350aab3075a3e573d4de2cc748 |
| tests/test_context_football_capture.py | 15908bc9723ee16a862d7332022914cdd74319711b480889c6ec1b61e1060414 |
| challenge_15k.py | 7d7e217282c6e0a9d12aeb38f03340311aaa2895037a79c12226566769535433 |
| wettfinder_automation.py | 44812cd89fbf85bdf01237bb0b249e26832497441e31a83fe549e77b0bf4be36 |
| alternative_markets_tab_extended.py | 8856e23aeeecfda6e206d7db70652f3c4d9061a08360c8e336a29f7181cee1a0 |

Independent review, real worker/native capture, semantic D4 backup integration
and production publication remain outstanding. Existing native source
normalizers, protected privileged helper, all old records, Cricket, account/
ticket/effect rules and calibrated baseline probabilities were not modified.
