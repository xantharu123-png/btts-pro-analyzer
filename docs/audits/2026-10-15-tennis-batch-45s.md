# Tennis training batch: native performance gate remains failed

15 October 2026. Canonical worktree: `.worktrees/audit-repairs-20261013`.
Base/local committed source, GitHub main and VPS:
`4ece002b69eb5c96897d3471cc7320654608a903`.

## Result

The approved equivalent B1 batch was implemented and its causal selection
tested, but did **not** meet its defining native acceptance. It must not be
published as a solved training path or used to claim a qualified numerical
injury/weather/fatigue effect. No new full regression was started after this
native failure. Earlier QA04 results still belong only to their tested source.

| Native receipt | Source | Wall seconds | CPU seconds | Peak RSS KiB | Completed cases |
| --- | --- | ---: | ---: | ---: | ---: |
| `native-feature-01.log` | training `93f394f6` | 45.201842 | 18.356038 | 30336 | 0/4 |
| `native-trace-02.log` | same source, diagnostics only | 45.201075 | 24.331882 | 30488 | 0/4 |
| `native-feature-03.log` | training `67c83639` | 45.265937 | 26.622401 | 30464 | 0/4 |

All three returned Exit 1, unchanged total 45-second deadline and frozen four
originals/cutoffs/as-of. The diagnostic trace is not a separate performance
acceptance. Selected-byte/count limits remained 512 receipts / 2 MiB per case /
8 MiB total; CPU hard limit 50 s, address-space hard limit 2 GiB, actual RSS
recorded. No returned feature vectors, labels, scores, fits or provider calls.

Sources and runtime imports came from the isolated code-only directory
`/tmp/betboy-training-batch.hbmUkw`. The immutable original probe hash is
`58e031c070cda241575edd344505e4b08429fa3c873b0c9c288869a14fae0db1`.
The first archive was 1,366,055 bytes of Python source only; the second transfer
contained just the changed `context_models/tennis_training.py`. No secret,
runtime database or full source-data copy was transferred. The trace records
the actually imported training source, not the unimported readiness/evaluator
files; those other hashes were verified separately locally and in SSH preflight.

## Cause established / limits of the evidence

The actual trace completed all original/state admission and resolution in
0.449324 s. Query 73 was the one batch discovery, still active until timeout.
EXPLAIN (0.165 s, compilation only) showed materialized receipt candidates,
a full observation-table scan, temporary GROUP BY B-tree, and indexed content
lookups. The batch is not stalled in model fitting or outcome processing.

Read-only bounded metadata probes found 2,602,717 observations overall and
981,335 ATP-native observations. The WTA count did not finish in the shared
diagnostic deadline and is **unknown**, not zero. COUNT DISTINCT/GROUP BY also
hit its separate short diagnostic bound. These are metadata measurements, not
valid feature-cohort counts or complete per-source inventories.

The native status producer explicitly binds the actual observation clock in
`competition_revision` and `valid_from`; workload records can also include
the actual result receipt time. Consequently identical sporting status can
produce different content digests. Grouping by digest does not turn the
historical inventory into one compact record per match. Reducing the five
JSON projections to one did not remove that root reading cost.

An existing covering index can search native event-key ranges; it is not a
participant index. A blind prefix shortcut could additionally hide malformed
outer/inner identities. No such shortcut, new index, schema change, pruning,
new database or resource-limit increase was installed.

## Correctness work retained

The first seven owning modules passed 141 tests. The unchanged single-case
selector remains the valid-input differential oracle. An independent review
confirmed full admitted revisions, per-case cutoffs, separate tours, physical
decoding, no outcome discovery, one actual held reader, and real readiness use.

Review found a genuine test gap: an earliest-only request did not exercise
membership discovered between two case cutoffs. New real two-origin tests
check early/late admitted receipt counts `[7,13]`, later removal revisions,
single-case bytes/digests, and the actual readiness range. Removing only the
per-case cutoff in memory caused both regressions to fail. The single-JSON
projection test failed on the old five-extraction query. All nine focused
follow-up tests then passed (15.498 s). The final covering run is recorded
separately in the task report: seven modules, **144 passed**, no failures/skips,
369.59 s, Exit 0. Five frozen source/test hashes rechecked identical. This is
not a complete suite and does not close the native performance finding.

Frozen training source: `67c836391928091e467b4d688a0e1f2a06575b889f7f63097f4c180f22a13a34`.
Readiness: `470f069cd724b010f863140ec7064329abd86335344296e9138a4ba52fc0a64c`.
Evaluator: `d4bc546618cac78776df6322a513619a6f3119e653703df7fcd0ae00f818e150`.

## Next decision, not approved implementation

A persisted derived player/event membership lookup would avoid rereading the
global JSON inventory on every batch. It must be complete, tied to actual
receipts and cutoffs, built within explicit resource bounds, and updated
atomically with future ingestion. It would store only derived associations,
not another full copy of the evidence. The footprint and migration cost are
not yet measured; do not promise a size or build time.

This changes the approved no-schema/no-index batch design. It has **not** been
approved, specified, implemented, migrated or deployed. Obtain approval for
the design change before product edits. Do not widen the 45-second probe,
drop revisions, copy the 7.41-GB production database, or call a partial batch
successful. Cricket and original predictions/tickets/money remain untouched.

Production regular jobs on 15 October succeeded (Tennis 00:05–00:32:36;
Wettfinder 03:35–04:11:44). App/Caddy/health were healthy, backups disabled;
metadata-only inventory found eight new point-joint capture originals. None
of this proves an activated context effect or better betting quality.

Evidence outside Git: `C:/Projekt/BetBoy/output/tennis-batch-20261015`.
Task brief/report: `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-23-tennis-batch-20261015-*.md`.
