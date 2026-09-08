# Bounded read-only corpus inventory

Controller checks from the VPS used app Python with -B and SQLite URI mode=ro, PRAGMA query_only=ON, a 20-second query deadline, aggregate counts and field names only. No provider requests, model builds, account/odds values, database mutations or historical evidence promotion. This is not a complete discovery of every legacy database and does not certify canonical event identity or D2 eligibility.

## 2026-09-07T17:58:27.016020+00:00

`/opt/betboy/app/runtime_state/forecast_evidence.db`:

| Sport | forecast_rows | Distinct stored event_key values | Decision-time range (UTC) |
| --- | ---: | ---: | --- |
| football | 5878 | 19 | 2026-09-06T22:57:02.916006 to 2026-09-07T17:37:33.428226 |
| tennis | 116 | 5 | 2026-09-06T22:57:02.916006 to 2026-09-07T17:37:33.428226 |
| esports | 84 | 8 | 2026-09-07T06:37:10.855725 to 2026-09-07T17:37:33.428226 |

No basketball or hockey rows were returned by the approved-five-sports aggregation. Only four distinct stored event keys in those sports had forecast_results. These are raw stored-key counts, not yet deduplicated/verified canonical native matches. Repeated runs or markets are not independent test events.

The latest 300 football/tennis payloads comprised 293 football and seven tennis rows. All had a causal_provenance_complete field; presence alone does not validate its claim. All football rows had context_checked_at. Football context included availability/status/checked fields for injuries, lineups, weather and a probability_integration object. Of 293 football rows, 197 also included reported/unassessed player fields and 277 had numeric weather fields. Tennis context contained observed_at, player/coverage/limitation objects and existing surface/indoor/model-clock inputs, but not the football top-level context_checked_at field. No source-native complete player evidence was inferred from those names.

`/opt/betboy/app/tennis/data/tennis_shadow.db`: 1239 prediction rows; 1175 each with provider_event_id and fixture_source; 104 with result_observed_at and termination; 73 each with player_a_sets/player_b_sets. The settled + result receipt + event identity subset had 104 rows, receipt range 2026-09-02T05:17:07.223363Z to 2026-09-07T05:18:42.948131Z. There were 375 immutable revisions across 63 prediction IDs. The latest 150 revision contexts exposed the existing model-input/coverage shape. This does not establish 104 independent native matches, exact recovery, or a usable untouched three-block population.

## 2026-09-07T18:05:21.634784+00:00

Corrected the earlier diagnostic column spelling: the real optional field is `match_duration_minutes`, not `duration_minutes`. The live tennis table **does contain** match_duration_minutes, but all 1239 rows have NULL there. It has no ended_at/player_a_id/player_b_id columns. result_observed_at remains populated in 104 rows. A missing exact end/duration cannot be replaced with the result receipt or a tournament date. The source receipt may support a separately labelled conservative recovery bound, subject to B6's complete-history and native-identity requirements.

`/opt/betboy/app/shadow_clv.db` contains one prediction and one distinct fixture_id with a result. Created 2026-08-22T13:53:31.547963Z, kickoff 2026-08-22T15:00:00Z, settled 2026-08-22T17:07:28.616222Z. Its predictions schema contains the existing result/model/price-tracking fields, but no context_json or metadata_json context archive. No price values were read.

## Consequence for D1/D2

The inspected forecast archive cannot by itself demonstrate the required 200 canonical, causal, untouched test events over three consecutive blocks. D1 must still inventory relevant historical result/appearance/archive sources, validate native identities and pre-decision availability, report actual exclusions and preserve prospective accumulation. Raw row volume, newly fetched retrospective context, model-input field presence, or an older result database are not substitutes for this evidence. No numerical acceptance rule is relaxed and no unavailable context removes a valid runtime baseline.
