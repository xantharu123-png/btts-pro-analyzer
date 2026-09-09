# Shared live Tennis winner consumer — 9 September 2026

Root-owned bounded packet on `kontext-tennis-consumer-20260909`, base5d5bab6.
No independent acceptance, main/VPS release or empirical effect approval is
asserted by this owning report. Existing Cricket and money/history are untouched.

## Actual integration

Both `ev_signal_sources.tennis_model_signals`/`tennis_signals` and
`riskobet_candidates.adapt_tennis_shadow` call one common stored-row reader.
There is no new source request, fit, prediction, approval, compute_once or
database creation on this read path. Genuine absent legacy context links do not
open the context database. Present invalid/missing links fail instead of falling
back to an older or rounded prediction; existing source-level error reporting
in the automation remains in charge of degraded coverage.

The internal generic reader extraction retains strict three-column table_xinfo,
bound input key/payload digest, the complete Event and original decision, and
the existing trusted main/WAL/SHM checks before and after one held transaction.
The public single-market API retains its exact output. The new Tennis reader
uses that same transaction for both A/B projections and the actual A1 original
and model-state artifacts; no model decoding/replay is needed to display cards.

The closed live sidecar must match the actual Shadow native provider, tour,
event ID, schedule, numeric decision clock, append clock, players, actual
executed surface/best-of/indoor inputs, model artifact and rounded original
raw/calibrated values. The real original publication must exist, match the
embedded original and be no later than Shadow append. Its tour state must exist
and have been published by the original decision. The new reader rejects views
or extra/generated artifact columns; the owning loader checks actual artifact
bytes/types/hash. These are identity checks, not a new historical alias resolver
or substitute for the producer/D4 source/model proof.

Both views receive the exact full-precision used winner probabilities and the
same immutable ContextReference. Normal model selection/minimum-price display
use that p; optional strict price-policy selection keeps its existing policy.
The automatic row serializer already preserves the optional reference and is
exercised directly. Actual legacy keys and money identities are not migrated.

RisikoBet still has one event snapshot (its existing equal-time consistency
contract), with explicitly winner-scoped reference/used probabilities in its
new input hash. The reference does NOT certify every market in the event.
Satzsimulation, its probability/orientation and SHADOW/PARTIAL stages stay
separate. A reversed winner projection cannot overwrite the set distribution;
an exactly balanced winner is not arbitrarily labelled an underdog. No new
context approval is inherited by a set scenario. Actual current live status-v1
has no qualified native court metadata, so no new fitted context effect is
activated by this packet: its real test fixture retains the original baseline.

Public context summary uses explicit owning workload (1/3/7 day) and recovery
(exact versus lower-bound) feature names, not substring inference or technical
admin limitations. Missing surface does not claim a surface-specific model.
Known incomplete recovery is not presented as an exact end/rest interval.
The normal quote-independent path and RisikoBet remain independent of missing,
low or extreme supplied prices; no new wager, stake or recommendation guarantee.

## Tests actually run

49 new owning cases: real temporary A1/B1/B3/Shadow with synthetic already-owned
ESPN responses, 20 exact-row/sidecar mismatch cases, original/state publication
identity and clocks, same-transaction A/B, call spies, price invariance, exact
legacy comparisons and isolated adapter winner-versus-set cases. The latter
substitute a projection to test adapter behavior only; they are explicitly NOT
real effect approval or proof that fabricated probabilities would pass B3.

Two test-only fixtures preserve exact prechange functions extracted from
Git5d5bab6 (normal functions plus their existing summary/clock helpers; Risk
adapter). They are executed with the owning module globals to compare complete
ModelSignal values and Risk JSON/IDs across nine p/quote combinations. Existing
fixtures/pins were not replaced. These fixtures do not require Git history at
test execution.

| JUnit in `.pytest_tmp` | Actual result | SHA256 |
| --- | --- | --- |
| `tennis-consumer-red-20260909-01.xml` | 33 temporary-directory setup errors; not product REDs | `66475422d0b81caa8bcac5a8868ae7809edcf657665c26e37a9bea9bf3f9a5c1` |
| `tennis-consumer-red-20260909-02.xml` | 33 missing-new-API assertions, before implementation; not 33 existing product defects | `02e7086e586679ed7ffec5c2d4db195b74be6c18c83752dee07c057d5a1ce29f` |
| `tennis-consumer-green-20260909-03.xml` | 59 passed,10.34s | `3a98d56bf377a5185eb751c608121eed53e575aac2339dd563042000bcfe452c` |
| `tennis-consumer-focus-20260909-05.xml` | 242 passed,26 subtests,14.27s | `1f7a7e23817a1d8a641db0944dfe3715da5d240669de5557b7a0c6961e6c0160` |
| `tennis-consumer-integration-20260909-06.xml` | 400 passed,1 Windows-symlink skip,29.20s | `600ba3d04342beb5cab6d1c90210c5b2cae5dc40d99aa26773b988e58d1e7726` |

An intervening04 invocation named a nonexistent reader test file and ran zero
tests. The correct existing `test_context_reader_trust.py` is included in06 and
the final post-LF07 round. Initial setup outputs remain preserved. After explicit
LF normalization of only these seven own files, all raw hashes were unchanged;
07 passed107 tests with one unchanged Windows-symlink skip in14.00s (XML SHA256
`0c1b74762c264b72d31f7b958d6858ef4a00c357fa93c1feed8ac13707c99c89`). No existing
failure was excluded or an assertion loosened. No fresh whole repository suite
or Linux/browser execution is claimed here; integrated acceptance remains open.

Postcommit whitespace-only cleanup removes one extra blank EOF line from each
new frozen fixture; no function bytes/semantics or production source changed.
The final49 owning cases passed in8.21s, zero skips/deselections;08 XML SHA256
`29bdb7162cb5108a307caf679f105a2e72cb0add0fca9712f3037a7cf4c48975`.
The fixture hashes below reflect this cleanup, not the earlier f09a0e6 versions.

## Frozen raw SHA256

```text
context_consumers.py 9b3515a8aa69cd6884b03622970318d1c77c10e73a5e9fb56f1563cf9f334b1c
tennis/context_consumer.py f79917b4162ce46607f3dd901644a5d90b906d1656833aff23eb3b73f4aaa20b
ev_signal_sources.py 26970cb596d38b0458fdb42b1d62c822c8d9bd2b080d2601ec23b3a8cd83e705
riskobet_candidates.py a28bbd628d6f410259b293f6675c87db698305c3a6dc09f0a9c80efca82ebb2c
tests/test_tennis_shared_consumer.py 389b7ed1dd792b10b97677d55b5d71d411d8a4c0b6d19048880eaf8a31097db9
tests/fixtures/tennis_normal_consumers_5d5bab6.py dde7cf898418c95484a08da747b5e772075bbd1c5c8b31f74066f428325d37c7
tests/fixtures/tennis_risk_consumer_5d5bab6.py be0a947b0d2de13c749a4283345e8d628ea3f27f100f526ff12a89055e4c9682
```

Future model/source changes, physiological effect evidence, further sport
workers, fresh integrated suite and real rendered/production behavior still
require their own verification. No source entitlement or >=200-event empirical
sample is invented; no missing quoted price changes an actual probability.
