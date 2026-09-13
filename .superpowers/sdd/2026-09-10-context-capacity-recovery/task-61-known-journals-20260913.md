# Known historical QA journals — exact read-only replay

Root resolved the exact known journal paths through a bounded read-only find,
chunkb22176, exit0. No filename-based authorization: roots are the previously
recorded native experiments, and embedded unit-protocol files are explicitly
distinguished from diagnostic execution journals.

Instrument `evidence/task61-known-journals-read.py` compiles the unchanged held
budget helper SHAfb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478.
It checks actual protected ancestor/path/FD/file identity, streams at most1MiB
per selected journal, calls only the pure `_replay(...).snapshot()` and returns
closed journal metadata, full BudgetIdentity and actual Reservation or null.
No PreparationBudget.open_existing/create/reserve/settle or native admission
was called; no protected runtime database/key was accessed or transferred.

Actual execution09:48:35UTC/chunk448c67, SSH/tool exit0, tool wait1.859129s,
reported CPU0.117310958s. LimitsCPU10/AS512MiB/FSIZE0/CORE0/alarm20;
fresh env-i PATH/LANG and Python-I-S-B. No durable ticket for this metadata read.
Exact16-journal JSON retained at `.pytest_tmp/task61-known-journals-01.json`.

| Group | Journals | Actual current state / charge |
| --- | ---: | --- |
| Task57/58 primary chain diagnostics | 5 | stopped, each300CPU charged /0settled |
| Task41/46/50 primary minimal diagnostics | 3 | stopped, each60CPU charged /0settled |
| Task60 isolated protocol admissions | 2 | one stopped, one intentionally pending; each300CPU charged /0settled |
| Embedded old recovery fixtures | 3 | deliberately pending, each1CPU synthetic claim |
| Embedded old roundtrip fixtures | 3 | accounting-open, no pending ticket, each1nanosecond synthetic settled claim |

The first eight primary journals total1680CPU; with Task60's two deliberately
synthetic admissions the selected primary reservations total2280CPU. The earlier
1770/2370 figures additionally included3x30CPU conservative sealer allowances
outside the journals. Calling all of those figures durable reservations was too
broad; this readback corrects that label without changing retained history,
releasing a reservation or hiding the additional synthetic fixtures.

The full retained-root manifest must list all known records with their exact
categories, identities, heads, pending tickets and states. Per-root cost remains
unknown where unjournaled history prevents a complete total. Synthetic settled
nanoseconds are test data, not measured/reusable execution credit. The file
membership hash covers every other descendant too; unknown test files are not
silently classified as real native runs by their name.

This is input metadata for Task61, not full retained content hashing or current
admission/source/closure authority. Actual input readback must remain fresh at
admission; no real1024-row diagnostic or full C/B/release pass follows.
