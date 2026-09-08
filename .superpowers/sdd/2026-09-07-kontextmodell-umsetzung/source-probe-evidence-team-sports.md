# Team-sports source probe evidence

Preparatory evidence only, not completed C2/C3 integration or empirical activation. Cricket untouched. Source code and the complete read-only source-readiness report were reviewed first.

Exactly two local public GET requests, no authentication headers, paid subscription, runtime cache/model writes, or retries. Raw responses were reduced to field paths for at most two completed events and one upcoming event. Dates come from existing source fixtures and are historical, not today's games. The diagnostic records the actual retrieval clock; it must never backdate observation time.

- NBA ESPN scoreboard for 2026-01-01 at 2026-09-07T15:23:43Z returned HTTP403. No retry, header spoofing or bypass. It supplies no player-coverage evidence.
- NHL official schedule for 2026-01-01 at 2026-09-07T15:23:44Z returned HTTP200 with 50 schedule events. Only native IDs 2025020632 and 2025020633 were inspected as completed samples. Both are OFF. No upcoming sample was present in this historical selection.
- NHL fields include native team IDs, periodDescriptor, gameOutcome.lastPeriodType and winningGoalie.playerId. The latter is post-result information, not a prior confirmed starter. Selected schedule payloads contain no skater/goalie time-on-ice rows or timestamped pregame starter confirmation. Presence of a winning goalie cannot justify a complete roster or goalie-confirmation capability.
- Sanitized diagnostic: basketball-nhl-schedule-probe-20260907.json. It preserves field paths and event IDs rather than complete raw payloads; it is not sufficient as a future parser-positive fixture for absent boxscore fields.

Remaining C2/C3 obligations: actual guarded context fetch/normalization, source coverage, as-of reference joins, learned offsets and validation. Schedule/result capability alone does not close them.

Additional documentation lookup: web open of the official NHL gamecenter boxscore URL for observed event 2025020632 returned the tool's non-retryable URL-safety error. No response fields were inspected, and no alternate-tool retry was made. This is not an NHL HTTP denial or evidence that boxscore data do not exist; capability remains unverified.
