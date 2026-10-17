# Context-effect readiness — 17 October 2026

## Football: verified production inventory

This is a bounded, read-only production inspection at code revision
`46f1fa8f6f690e15ae7045087e0bea762be79dd4`, not a completed fit or an effect
activation. No sports-provider request, database copy, backup, migration or
production write was performed.

The approved contract remains `../superpowers/specs/2026-09-07-kontextmodell-design.md`:
at least 200 independent untouched test events, additional train/tuning events,
three chronological test blocks, at least 2% paired Brier improvement, the existing
HAC/BH test and no distribution-logloss deterioration. Source observations and
many markets for one event do not substitute for independent test games.

### Actual stored records

Production `runtime_state/context_models.db` contains 115 native ORIGINAL
bindings. Eight bindings cover eight source-complete events. The other 107
bindings cover 51 events and explicitly retain incomplete source status.

| Stored artifact kind | Rows | Canonical payload bytes |
| --- | ---: | ---: |
| Executed code | 16 | 1,873,403 |
| ORIGINAL binding | 115 | 9,801,469 |
| ORIGINAL body | 115 | 20,817,439 |
| Shared JSON chunk | 243 | 22,363,387 |
| ORIGINAL manifest | 115 | 31,165 |
| **Total** | | **54,886,863** |

The latest of these artifacts was written on 15 October at 01:41:34 UTC. No
native post-context decision, context fit, effect or approval artifact exists
in this inventory.

The unresolved references recorded inside the bindings are:

- 32,965 `source-retention-budget-exhausted`;
- 528 `native-receipt-reference-unavailable`;
- 1,558 `football-source-provenance-invalid`.

These are reference counts, not game counts or API request counts.

### Two separate resource barriers

1. The original-collection admission file has permanently reached its existing
   lifetime reservation ceiling: `total_reserved=134217728` bytes (128 MiB),
   last reservation day 15 October. The unchanged code therefore refuses further
   ORIGINAL collection, even after midnight. The normal sport scanner is a
   separate path; this finding does not mean the scanner or app has stopped.
2. Running the existing read-only readiness checker against all eight complete
   ORIGINAL events reproduces the per-case source barrier: seven fail
   `joint_source_byte_bound_exceeded`. Only one reaches source/outcome resolution;
   none has complete values for the tested roster-exposure, reported seven-day
   player workload or city-temperature feature. The resolver accumulates every
   pre-decision revision of every event in the frozen league/team input pool into
   its existing 4 MiB / 4,096-receipt envelope.

The 54.9 MB of artifact payloads is not the physical SQLite size and is not
the complete charged source-byte total. Nor does subtracting it from 128 MiB
prove which reservations were unused, failed, crashed or in flight. The old
admission schema stores no per-permit completion ledger, and its tests
deliberately forbid refunding failed attempts. A blind counter reset or cap
increase would not be a validated repair.

### Consequence and narrowly defined next work

There are currently zero qualified football injury, weather or fatigue models
to activate. Eight complete original events, with only one resolvable source
pool and zero complete tested factor vectors, cannot satisfy a 200-event final
test in addition to training and tuning. This is an observed production data
gap, not a claim that no football results or statistics exist.

The next source repair needs an explicit, lossless consumed-branch projection
or streaming resolver: preserve native identities, frozen consumed/inspected
references, simultaneous conflicting revisions and first actual result-receipt
clocks, while avoiding one expanded all-league/all-revision body pool. Any
successful-completion budget accounting must retain crash reservations and
idempotent concurrency ownership. Historical partial bindings, timestamps,
probabilities and financial records must remain unchanged. More elapsed days
alone cannot resolve the exhausted collection counter or the current source
envelope barrier.

Evidence helpers outside Git:
`C:/Projekt/BetBoy/output/context-effects-20261017/football_commit_inventory.py`
and the existing bounded
`C:/Projekt/BetBoy/output/context-integration-20261013/production-readiness.py`.
The latter was executed unchanged against the current production store; the
three selected factor checks each inspected eight events, resolved one source
and outcome, and found zero complete factor vectors. Its test-window count is
diagnostic only and is not a frozen empirical qualification.

## Tennis: results exist, but the current effect cohort is not ready

The current read-only production inventory resolves 5,577 winner-original
publications to 1,127 unique events and 1,000 matching native finals: ATP 276,
WTA 724. Twenty late original publications were excluded. These counts mix
different baseline generations and are not 1,000 untouched test cases for one
current effect model. Only 52 actual POINT-joint original artifacts exist; an
artifact count is an upper bound on independent events, not a qualified cohort.
There are no fitted context-effect artifacts in the current production store.

The existing four-case v4 feature probe could not reconstruct its features
within 120 seconds. The previous fixed four-case indexed probe failed because
one selected source pool required 11,589,186 bytes, above its unchanged 2 MiB
per-case input envelope. The index had been built and explicitly disabled after
that failure. Neither missing final scores nor merely waiting another day
explains this reader barrier.

Two bounded native-event inspections found ten repeated status receipts each
with one unchanged normalized terminal status/workload fact set. The repair
reuses existing receipts atomically under the observation writer transaction
only when a normal final, both validated player workload records and the same
known native winner outcome are all present. Corrections, intervening statuses,
changed participants/schedules and unknown winner flags remain new observations.
Original rows and their first receipt times are never rewritten. Default B1
append behavior and the six frozen Tennis model sources remain unchanged.

This optimization does not suppress every historical repetition: games without
an original-bound winner outcome remain on the existing append path. Its share
of future saved storage has not been measured. It does not repair the existing
large historical pools or qualify a physical fatigue/injury effect. No precise
end times, injury diagnoses or numerical coefficients were inferred.

Tennis implementation receipts outside Git:
`C:/Projekt/BetBoy/output/tennis-terminal-qa03.xml` (236 targeted tests),
`C:/Projekt/BetBoy/output/context-market-20261017/tennis-terminal-red01.txt`
(the reproduced repeated-worker failure). Independent source review found no
remaining P1/P2 issue in this bounded repair.

## Completion boundary

The current market-evidence and repeated-terminal repairs are software fixes,
not completed injury, weather or fatigue activation. The existing data must
first pass lossless source reconstruction and a prospective collection budget
that can actually produce the approved train/tune/test cohort. Changing a
customer label or inserting fixed percentage deductions would not meet that
requirement. No model acceptance threshold or resource cap was loosened in
this release, and no additional paid source, backup or sports scan was started.
