# Doppelchance-Reparatur Implementation Plan

> Execution: test first, independently review the diff, deploy the exact reviewed tree.

**Goal:** Behaviors approved in the [audit](../../audits/2026-11-27-doppelchance-tippentstehung.md): exact result settlement, a market-specific explanation and no misleading primary selection when its underlying 1X2 row was lost.

**Architecture:** Reuse the same fitted 1X2 vector as the goal market. Transport it once per displayed directional market in validated optional football analysis evidence. Older artifacts need no rewrite. No new model, formula, odds rule, threshold, endpoint, backup or migration.

## 1. Settlement

- [x] Reproduce conflicting native FT `goals`/`score.fulltime` (and impossible extra time/shootout at FT), plus mismatched native/event/fixture IDs. Use the real evidence adapter and test persistence/absence, not only a parser result.
- [x] Reject conflicting packets before writing an ordinary pre-match outcome (all football markets sharing the parser, without changing legacy or live settlements). Preserve valid FT with and without redundant score, provider retry and existing fixtures. No additional API calls. Separate 15K/RisikoBet adapters remain unchanged.

## 2. Analysis and card

- [x] Keep `[home, draw, away]` exact and bounded, sum to one, match the selected marginal and same role/kickoff/model evidence; do not borrow a vector from another revision. Preserve intact evidence on deferred first admission as well as on refresh. No probability change. Typed optional evidence is backward compatible (snapshot validation updated; Challenge ticket payload shape unchanged).
- [x] Map `DC_1X`, `DC_X2`, `DC_12` canonically to team-or-draw/no-draw and show the matching individual chances where available. Old packets show the real complementary risk; never invent missing individual odds. Regress malformed display text, swapped roles, missing/stale/malformed vector, and home/away symmetry.

## 3. Ranking and release

- [x] A double chance excluding the uniquely most probable outcome of the same validated 1X2 vector remains a model alternative in the Overview, but is not a featured/game lead or a nominee in Best-by-market just because another market got filtered. Normal context/evidence vetoes stand; do not restore blocked markets or change probability order among admissible leads. Backward compatibility for unavailable vectors; no inferred missing outcome.
- [ ] Verify current and legacy fixture samples plus normal default/market views. Repair stale `target_search_date` in two existing Ilves test fixtures without weakening checks. Run targeted suites in both price modes, audit independent review, require green CI before merge. Deploy without backups or extra scans and check internal/public health.
