# Live ohne Vorabprognose Implementation Plan

> For agentic workers: use test-driven development and independent review.

**Goal:** Compare supported open live football markets using only already fetched, verified live facts. UEFA games with proper details must not need a prematch row.

**Architecture:** Keep fixture/time/team, live xG, goals timeline, dismissal and freshness checks. A ticker-only adapter passes the verified match to a versioned remaining-goal law. Reuse the existing market catalog and settlement, with a separate receipt policy that preserves old rows. Do not change the manual scanner or public recommendations outside the automatic ticker.

**Contract (owner approved 26.11.2026):** No match-specific prematch estimates, no fallback read, no quotes as model inputs, no additional API call, backup, or timer. Preserve minute 15, 55% and +5 percentage points. A mere score, time, or equal xG cannot create a tip. Display a simple play-specific reason; never describe the estimate as calibrated or profitable.

**Live model:** Reference for both sides is `(home_xg + away_xg) / (2 × elapsed) × remaining`, at the same score/time. Actual per-side rate blends each team's observed xG with a symmetric pseudo-exposure of 30 minutes at that same in-match pooled xG rate. Use nominal regulation minutes for the rate: the clock stays at 45 during first-half added time and halftime, so an unchanged xG packet does not jump between those two phases. Validate the native phase and the elapsed wall time at receipt against the scheduled kickoff (−5/+60 minutes relative to the elapsed match clock). For a single confirmed dismissal, apply the existing score/time red-card adjustment only to the smoothed component, never again to the observed xG. Do not infer xG from score/shots or multiply correlated shots again. Current native shot counts, when available, support the readable explanation. With 11v11, the observed and neutral total goal rates are equal: total-only markets are compared but cannot pass the uplift rule on side dominance alone. No arbitrary fixed match-wide scoring rate is inserted.

## Work and verification

- [x] New versioned live-only comparison, evidence symmetry and red card tests, old catalog unchanged.
- [x] Source/UI: no prior lookup even when cached, verify UEFA and dismissal end-to-end with synthetic native detail, explain absent live data, remove prior display dependency.
- [x] Receipt/settlement: separate policy ID, old rows still settle, no duplicates across model versions, no new polling mechanism.
- [x] Focused regression: 733 passed, one skip, in each price contract. Independent review of fixture identity, kickoff and halftime checks complete.
- [ ] Release: CI, guarded no-backup deployment, and health checks without opening a live view.
