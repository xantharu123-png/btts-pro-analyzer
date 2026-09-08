# Bounded real-source evidence, 2026-09-07

These are controller-run schema/coverage probes, not completed B4/B6 integration, historical as-of evidence, training or empirical approval. No model, snapshot, prediction, ticket or settlement was changed. No new provider, paid plan or TLS bypass.

## Football

- Existing VPS config and the real shared budget were used; only configuration presence was printed. Read-only budget observation at 14:43:51Z: remaining 6688 of 7500, safely above the BACKGROUND reserve.
- Native IDs were read from /opt/betboy/app/shadow_clv.db with query_only/mode=ro. Future 1593305 at 2026-09-07T15:00Z; completed 1570343 at 2026-08-22T15:00Z, actually settled at 17:07:28Z that day. The completed sample is not a current-day match.
- Exactly two governed BACKGROUND calls, not a scan: one fixtures?ids=1593305-1570343 at 14:46:05Z and one injuries?ids=1593305-1570343 at 14:47:03Z. Both HTTP 200, no provider errors, paging 1/1. The normal API budget reservations/completions are the only production writes.
- The single batched detail call already supplied nested players; no additional player endpoint was called. Completed fixture: FT, two teams, 11 starters and 12 bench players per team; 23 player-stat records per team, 16 with non-null minutes each. Samples include native team/player IDs, minutes, substitute flag, position and performance fields. Null minutes remain missing, not zero.
- Future fixture: NS, no lineups and no player details in this response. Do not infer healthy players or complete lineup coverage.
- Injury response contains 10 rows; the six preserved structural samples have native fixture/team/player IDs, type and reason. Missing Fixture includes injury reasons but also Coach's decision and Inactive. Do not label every row an injury or infer participation probabilities.
- The preserved injury samples expose only fixture date/timestamp, not injury publication time. Receipt on September 7 must not be backdated to August 22 for historical predictive validation.
- Artifacts: football-source-probe-20260907.json and football-injuries-probe-20260907.json, sanitized structural subsets only.

## Tennis

- Three total local public-source requests, no runtime writes: SofaScore scheduled-events/2026-09-06 at 14:39:47Z returned 403 and was not retried; existing ESPN ATP source at 14:40:15Z returned 200 but the diagnostic initially selected the wrong top-level competitions shape; one corrected ESPN request at 14:41:09Z used the existing groupings[].competitions[] contract. No more tennis probes were issued.
- Corrected ESPN response: one tournament, 239 men's-singles competitions, 228 completed. This does not mean 228 matches on the requested date: the two samples are August 24 matches. Existing date filters must stay strict.
- Samples supply native competitor.id (athlete.id absent in these examples), per-set linescores.value and tiebreak values. statistics is empty and no match-level duration/end field is present in the sampled competition keys.
- date and startDate are equal in the samples, not proof of actual start. Tournament event.endDate is not a match end.
- format.regulation.periods=5 appears even alongside 2:0 qualifying finals; it is not sufficient proof of an individual match's best-of format.
- Artifact: espn-source-probe-20260907.json. These are structural samples, not complete workload histories or contemporaneous pre-match observations.

## Additional read-only training-source checks

- Exactly three VPS GETs at 17:27Z using existing source URLs, no redirects/retries, 12MiB maximum per response, production data-loader validators, processing only in memory with Python -B. No cache/model/database writes and no model publication. Metadata is preserved in training-source-probe-20260907.json and the tracked source audit.
- ATP tournaments.csv: HTTP200, 1858008 bytes, SHA2561483ae267c77bddefb35025f730dc54e63e81a27efdf315b8ae2d484b574ae36; current-year coverage229 tournaments through tournament-start proxy2026-09-07, receipt17:27:31.162784Z.
- ATP matches_2026.csv: HTTP200, 4182140 bytes, SHA2567a0cdeaa42ada513f4dbbfaadd35ff24d96b70047c0e63171dabb2c56b952c54; current-year validated coverage11680 result rows through the same proxy, receipt17:27:33.212927Z. Season count, not today's games or the final tour-level training population.
- Existing WTA2026w/2026.xlsx GET: HTTP503 at17:27:33.292200Z. Not parsed or saved, not retried. This supersedes the earlier HEAD-only availability limitation with one actual GET failure, not a claim of permanent source failure.
- These checks establish source availability/schema only; an actual separated build including calibration, activation and forecast use remain separate A4/release evidence. Initial fixture-schema probes above are unchanged.

## Isolated Linux validation environment

- /tmp/betboy-context-qa.9xr68INa is ubuntu-owned mode 0700 under root-owned sticky /tmp mode 01777.
- A separate venv contains pytest 9.1.1, iniconfig 2.3.0, packaging 26.3, pluggy 1.6.0, pygments 2.21.0. The app venv was not modified.
- Real app directories /opt/betboy, /opt/betboy/app and runtime_state are betboy-owned mode 0750, root and /opt root-owned 0755. Read-only stat required sudo -u betboy for the protected app directory.
- Exact d292c216d90ecc4872cf99d2261eb566893fc204 was transferred as a three-file Git archive; SHA256 882bbd2d7fb8f5da3b620211de7563e2c43ce21017d14a6bd875442b34b3d745 matches on both hosts. Actual Linux A1 result: 3 failed, 24 passed in 0.60s. Two first-install tests create a mode0775 parent under the observed umask0002 and then fail the trust check; a positive sticky-directory test double trusts only ubuntu UID and rejects the real root-owned /tmp. These are not passing Linux results and must be fixed before A1 completion.
- Superseding fix evidence: e41458d4f8a3127a3687678ec454fc9bfbdba6fe, archive SHA256 a9b7c5f7cf054bd097b23d33bed059a5b9824fbe581314aed4e81306135e9876 verified on both hosts, actual Linux suite 29 passed in0.55s without skips/warnings. New parents are explicitly private; existing directory modes are not changed. Scoped code re-review remains pending. Production app and venv were not changed.
