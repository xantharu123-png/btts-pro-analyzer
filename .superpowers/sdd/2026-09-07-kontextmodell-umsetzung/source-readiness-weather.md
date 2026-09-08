# C1 source readiness — football weather and complete schedule load

Status: read-only source preparation on 2026-09-07. No provider-data/API probe,
credential read, subscription, production edit, VPS action or C1 implementation was
performed. **C1 is not complete.**

## Existing source path and timestamp semantics

- `ChallengeDataProvider.weather()` reads the scheduled kickoff, but identifies the
  weather location only as API-Football `fixture.venue.city` plus
  `league.country` (`challenge_15k.py:1199-1215`). It geocodes the first city hit,
  requests OpenWeather 5-day/3-hour forecast with `units=metric`, and selects the
  closest `list.dt` within +/-4 hours (`challenge_15k.py:1219-1303`). The returned
  fields are temperature C, wind m/s, rain/snow mm per 3 h and description
  (`challenge_15k.py:1304-1325`).
- OpenWeather's published 5-day/3-hour documentation defines `list.dt` as the
  **time of data forecasted** (valid time), not issue/publication or receipt time:
  https://openweathermap.org/api/forecast5 . Current code renames that value
  `forecast_at` (`challenge_15k.py:1300,1316-1324`), provides no `issued_at`,
  `valid_from`, `valid_until`, `fetched_at` or true `observed_at`, and later folds
  `forecast_at` into an `observed_at` provenance slot
  (`challenge_15k.py:1731-1741`). Therefore a forecast cannot currently prove it
  existed at the decision cutoff; its effective interval is also only inferred by
  nearest-distance rather than recorded.
- Context `checked_at` is the application evaluation time, added after the weather
  payload is consumed (`challenge_engine.py:2754-2760,2894-2901`); it is not a
  provider issue time or HTTP receipt. The planned shared policy says weather
  receipts expire after 3 hours and their valid interval must include kickoff
  (`docs/superpowers/plans/2026-09-07-kontext-b-verletzungen-belastung.md:87-88`),
  but the legacy weather payload cannot enforce either part.

## Venue identity and indoor handling

- Fixture reconciliation binds fixture ID, home/away native team IDs, league and
  revised kickoff/status (`challenge_15k.py:292-340`), but weather lookup discards
  the venue ID/name and does not retain coordinates, geocoder identity, coordinate
  source/revision or response coordinate. A same-city stadium can therefore be
  mapped only to a city centroid; exact venue coverage is unproved.
- No inspected football weather path reads roof, retractable-roof, indoor/outdoor
  or enclosure state. Unknown roof/venue must remain `missing` coverage; nothing
  supports `not_applicable`. The shadow workflow duplicates the city geocode and
  nearest forecast logic and likewise has no roof or provenance clock
  (`shadow_clv_automation.py:395-462`).

## Cache, governor and consumers

- Main scanning has only a per-`ChallengeDataProvider` in-memory cache keyed by
  `(city,country,kickoff-hour)` (`challenge_15k.py:685-695,1215-1217,1325`). It has
  no TTL, issue/receipt clock, persistent revision, payload hash or exact fixture /
  venue identity. The shadow provider has no weather cache. Both weather paths use
  direct `requests.get`; the shared SQLite/WAL API-budget governor wraps only
  `api_football_get` (`api_budget.py:151-216,572-635`). Thus weather calls do not
  consume/protect a shared OpenWeather budget.
- Operational bounding exists only around consumers: at most 20 immediate context
  fixtures, a five-day weather horizon, and browser auto-rechecks every 180 s with
  a 12-minute minimum gap (`challenge_15k.py:111-133,1557-1590,1930-1985`). A new
  provider object is created for refreshes (`challenge_15k.py:2054-2055,2111-2113`),
  so its weather cache does not survive runs. Weather feeds the context veto and UI
  (`challenge_15k.py:2617-2633,2683-2696,4241-4267`) and the shadow evaluator
  (`shadow_clv_automation.py:846-879`). Existing tests cover secret redaction and
  hand-built values/extreme-veto behavior, not issue-vs-valid time, units metadata,
  exact venue/roof, staleness/reschedule, archive kind or persistence
  (`tests/test_challenge_15k.py:1561-1582,2231-2275`).

## Forecast history and published archive terms

- No weather DB/table/archive writer exists in the inspected paths; the only live
  source is OpenWeather's current 5-day/3-hour endpoint. Consequently there is no
  historical forecast source suitable for strict pre-decision training today.
- Open-Meteo's published Previous Runs API exposes fixed lead-time offsets 1-7 days
  and says most model archives begin January 2024:
  https://open-meteo.com/en/docs/previous-runs-api . Its Single Runs API preserves
  a run selected by initialization time, but explicitly warns initialization is
  **not** public availability (typically 1-6 hours later depending on model):
  https://open-meteo.com/en/docs/single-runs-api . Availability-at-decision must
  therefore be derived from documented model update timing or a prospectively
  captured receipt, never equated to `run`.
- Published terms: free API is non-commercial and limited to 10,000/day,
  5,000/hour, 600/minute; paid subscriptions cover commercial use
  (https://open-meteo.com/en/terms). API data require CC BY 4.0 attribution,
  including a nearby Open-Meteo link when displayed
  (https://open-meteo.com/en/licence). Pricing currently lists Previous Runs and
  Single Runs under free/open access and Professional/Enterprise, but not Standard;
  commercial access uses a paid customer endpoint
  (https://open-meteo.com/en/pricing). These are verified published terms only.
  BetBoy's account entitlement, approved commercial/non-commercial purpose,
  remaining quota, exact model/variable history, stadium coverage and lawful
  retention/display are **not verified** and no subscription is authorized.

## Complete schedule-load gap

- `_bounded_completed_history()` accepts only causal FT rows before cutoff and
  de-duplicates native fixture IDs, then event tuples
  (`challenge_15k.py:201-257`). However `completed_history()` is called per league
  and filters to that league (`challenge_15k.py:809-869`).
- The existing team fallback fetches a mixed recent team list but deliberately
  selects one current domestic league and returns only that league's fixtures
  (`challenge_15k.py:871-915,918-1013`). `_continental_team_history()` combines
  those two domestic profiles for a continental target and de-duplicates fixture
  IDs (`challenge_15k.py:377-429`); it does not build each team's shared domestic +
  international completed timeline. There are no recovery/load features, known
  completion bounds, actual player-minute joins or incomplete-appearance states.

## Smallest future probe and unresolved dependencies

After explicit probe/budget authorization, use one known native fixture whose
API-Football detail contains fixture ID, schedule revision and venue ID/name/city;
make one location resolution plus one current forecast request, recording sanitized
raw payload hash, HTTP receipt time, returned coordinates/units, valid interval and
whether an issue/publication time truly exists. Separately, one bounded
`fixtures?team=<native-id>&last=N&status=FT` response for a team known to have one
domestic and one international completion can test shared native de-duplication and
result-observation bounds. Do not infer 90 minutes, roof state or publication time.

Until those probes and archive entitlement/licensing/attribution decisions are
resolved, strict forecast-history coverage, exact venue coordinates/roof status,
prospective issue-time evidence, cross-competition load coverage and numeric C1
activation remain open. Current/reanalysis weather must remain distinct from prior
forecast evidence, and prospective collection is the safe fallback if no authorized
archive can prove prior availability.
