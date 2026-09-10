# Tennis B1: bounded read-only storage diagnosis

2026-09-10. Source inspection against Root commit
`2dd1116b68f3d94e9c24338c6c9dff9b01799221`. The inspected source files have an
empty diff against that commit. Root supplied the actual read-only VPS
aggregates below; this agent did **not** access the VPS or production database.
No tests, provider calls, source edits, Git mutation, deletion, retention or
storage migration were performed. This report is the sole newly authorized file.
The separate D4 size-limit investigation belongs to the other agent.

## Conclusion

The large B1 inventory is **not 47,227 distinct historical matches required by
two winner predictions**. It combines whole ESPN responses from the existing
old-prediction settlement loop with the current fixture requests. Capture occurs
before downstream date, singles, target-ID or prediction-selection filters.
Receptions repeatedly describe the same native events. New reception times are
embedded in the Tennis **content**, not only the generic B1 receipt, so unchanged
sporting facts received later also create new content rows.

This is not an import of the entire ATP/WTA training dataset into B1, nor one
copy of history per prepared prediction. The whole-response capture and the
reception-bound Tennis content contract explain the growth. Full source lineage
has a legitimate correction purpose, but its actual capture scope is much wider
than the participants of those two forecasts and their relevant prior events.

## Actual aggregates supplied by Root

| Inventory | Rows | Distinct events | Distinct receipt times |
| --- | ---: | ---: | ---: |
| Tennis `event_status` | 26,098 | 3,078 | 50 |
| Tennis `workload` | 21,000 | 1,305 | 50 |
| Tennis combined | **47,098** | **3,078** | **50** |
| Parallel Football availability | 84 | 15 | 1 for this kind |
| Parallel Football base fixture | 15 | 15 | 1 for this kind |
| Parallel Football confirmed lineup | 30 | 15 | 1 for this kind |
| Whole B1 inventory | **47,227** | **3,093** | **52** |

All 47,227 receipts have distinct content hashes. Root reports 50.65 MB of
content payload, total database 100.67 MB and zero free pages. The two Tour
artifacts together account for only 2.95 MB. Those are supplied measurements,
not a fresh integrity verification by this agent.

Receipt span: `09:59:08.864565Z` to `10:07:14.247866Z`. Four largest receipt
cohorts each contain 1,431 rows across 775 events; the fifth contains 1,349 rows
across 729 events. A single normalized response can therefore contribute far
more than the 27 fixture candidates or two prepared winner originals.

The status inventory averages about 8.48 revisions per Tennis event. The 21,000
workload rows represent 10,500 bilateral terminal-pair receptions, not 21,000
different matches or players. Repeated cohort sizes alone do not prove that
their exact event sets were identical; the supplied distinct-event aggregates
do prove substantial repeated event history. The supplied data do not identify
the precise request dates responsible for every reception.

## Exact write path and scope

1. `scripts/tennis_daily.py:1011-1017`: `main()` places the entire `_run_daily`
   body inside `capture_tennis_worker`, then calls `batch.finish()` only after
   the capture has drained. `:1031` calls `auto_settle_completed()` before
   fixture acquisition or prediction selection. Capture does not depend on how
   many originals will later be prepared; even zero prepared predictions would
   still drain the successfully received source facts.
2. `tennis/shadow.py:1201-1207`: `pending_predictions()` selects **all** unsettled
   rows, ordered by match date. `scripts/tennis_daily.py:526-559` retains every
   pre-today non-TBD row, without an age cutoff. It fetches results once per
   `(ESPN, match_date, tour)` in the current invocation, not once per pending
   prediction. `result_cache` is local to that invocation and is rebuilt on the
   next run. The pending target ID is matched only later at `:566-579`.
3. `scripts/tennis_daily.py:295-307`: every existing successful ESPN JSON reply
   is observed immediately, before its event list reaches downstream consumers.
   `fetch_results_espn` calls this at `:416`, then applies singles/status and
   exact match-date filters at `:419-468`. Fixture fetching also calls it at
   `:240`, before its own format/date/start filtering. The observer adds no GET,
   but it sees the complete returned competition inventory, not filtered tips.
4. `context_sources/tennis_capture.py:35-55`: every returned event, grouping and
   competition with a usable native match ID is normalized and buffered. There
   is no target-player, target-prediction, age or requested-match-date filter.
   Unknown/unsupported groupings may retain an explicit status withdrawal;
   they do not thereby become supported singles workload. Only normalized
   sporting records are stored, not raw response bodies, names or prices.
5. `context_sources/tennis_status.py:147-163`: each identifiable competition
   yields one event-status record. A supported completed singles competition
   adds exactly two opposite-player workload records from that same reception.
   `context_sources/tennis_capture.py:60-66,89-96` appends these individually at
   context-manager exit, status first. Its `refs` set deduplicates reported hash
   references; it does not limit capture to the selected predictions.

The legacy `shadow.workload_history()` read at `tennis/shadow.py:1184-1198`
returns settled rows for the existing predictor. The Tour model selection and
that legacy read do not append B1 content. The observed Tennis B1 writer in
this execution is the response-capture path above.

## What B1 deduplicates, and why Tennis creates new content

`context_observations.py:98-135` computes:

```text
content_hash = digest(normalize_observation(record, observed_at=actual_receipt))
receipt_hash = digest({content_digest: content_hash, observed_at: actual_receipt})
```

`context_contents` has a primary key on content hash; `context_observations`
has a primary key on receipt hash (`:43-62`). Inserts are `INSERT OR IGNORE`,
followed by exact stored-byte/index validation. `(event_key, schedule_revision,
observed_at)` is an index, not a uniqueness/overwrite policy. Source, subject,
kind and all normalized fields participate in content identity.

- Same full content and same canonical receipt time: no additional rows.
- Same full content at a later receipt time: generic B1 adds one receipt and
  reuses its content. Existing `tests/test_context_observations.py:59-73`
  explicitly covers one content/two receipts; it was read, not rerun here.
- Different content for the same event/source/time: both revisions remain;
  selection may expose a conflict instead of overwriting evidence.
- Identical competition bytes fetched again at a later real time in this
  Tennis adapter: **different content and different receipt**. Status
  `valid_from` is the new reception (`context_sources/tennis_status.py:110`),
  `competition_revision` includes it (`:158-160`), and terminal status binds
  its two reception-specific workload hashes. ESPN supplies no real result
  publication clock here (`context_sources/tennis.py:124-130`), so workload
  `result_observed_at` becomes the actual reception (`:260-274`), also changing
  `source_revision` and `valid_from` (`:272-275`).

Thus the observed 1:1 content/receipt counts are consistent with the current
owning Tennis contract. Generic B1 is not failing its content-deduplication
rule; this source deliberately includes reception-dependent fields in content.
Exact duplicate records within the same reception remain idempotent.

## What the two actual predictions read and reference

`tennis/live_context.py:257-274` caches a read per `(tour, decision cutoff)`,
not per card. However, `context_sources/tennis_status.py:262-298` first decodes
the **whole** physical B1 inventory, then returns all eligible causal Tennis
receipts in that tour, without latest-event or player pruning. Each prepared
snapshot's `observation_refs` includes that entire returned tour inventory,
not merely its finally used feature refs (`tennis/live_context.py:274`).

The narrower sporting selection happens later:
`context_models/tennis_v3.py:36-54` groups complete native event lineage and
keeps only events whose historical participant union intersects the two target
players. Full lineage prevents a newer participant correction from reviving an
old player's match. Its subsequent newest status/bilateral-pair checks select
usable history before the 1/3/7-day load and recovery calculations in
`context_models/tennis.py:166-216`. This explains why whole-event correction
evidence matters, but does **not** make every other player's lifetime event or
every repeated whole-tour response a numeric input to each winner forecast.

This reception source still has unknown actual end/duration. Stored set/game
data are not invented into exact performed-load windows or injury/fatigue
effects. The current inventory/ref/replay contract cannot be reduced merely by
discarding apparently unused rows without an owning contract review.

## Next identical invocation

If the next invocation receives the **same normalized Tennis competition
inventory** at new actual receipt times, it adds another **47,098 Tennis
contents and 47,098 Tennis observations**, despite unchanged sporting values.
Starting from Root's mixed 47,227-row inventory, that conditional next Tennis
run alone would produce **94,325 rows per B1 table**. A repeated parallel
Football import is a separate condition and is not included in that number.
Physical database growth is not asserted byte-exact because page/index layout
and other writers are not reproduced here.

A real next run may fetch fewer historical date/tour buckets if this run
successfully settled their final pending predictions. Still-unsettled buckets
will be fetched again because `result_cache` is invocation-local. Therefore
"same date / same two tips" alone does not prove an identical request pool.
The shared original/compute-once mechanism does not prevent these earlier B1
inserts. Replaying the exact same already-normalized record **and original
receipt time** would be idempotent, but a fresh GET is not such a replay.

## Scope and source identities

No retention, deletion, limit increase, source-clock rewrite, existing-history
replacement or recovery path is authorized or implemented by this diagnosis.
The P4b3(a) worktree remains frozen after its separate independent Round1 HOLD;
no fix there was started. Root owns the next product/recovery decision.

SHA256 of inspected unchanged source bytes:

```text
114493ab3ac8411a35b0f194b7f9115e8e09ccb06f89180322fe550af477280d scripts/tennis_daily.py
918839283fd4bb446f01fbe34e32ef1e25fb690aa7d1e8f2627650506eef5fdc context_sources/tennis_capture.py
696302d12822151105d2e2067d22d216d0071f47446799e462744271910b62a4 context_sources/tennis_status.py
80f1621f60e0b3daecef8abb5e44efeebd2c2bc6bc0df8161032daab78ceb739 context_sources/tennis.py
dd204c3863dcd6712531213c05aeeb3a9551f6b0f8ec9a160e1375182958e033 context_observations.py
91416948aed90bbd503f83a2ecd330f22be6985562aea9a42f3b2f081f6bc8fd tennis/live_context.py
ec6461b87656ecc5731992cc26f0ae69d20e878982706ebe3f1fd0599c43305c context_models/tennis_v3.py
```
