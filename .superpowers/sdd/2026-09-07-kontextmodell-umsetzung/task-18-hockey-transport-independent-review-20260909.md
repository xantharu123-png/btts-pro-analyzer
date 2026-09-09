# Independent D3 hockey transport review — 9 September 2026

**PASS for the bounded pure transport/export change. No actionable finding
remained in the reviewed scope.** This is not source qualification, real D2
approval, complete shared-worker/UI integration, production or whole-project
acceptance. No source or original test was edited to obtain this result.

## Frozen target and reading

Root-authored commit `c871ba1203b66f8ba69adb5fed056e251d84c59b`, reviewed in
fresh clean worktree
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-d3-hockey-review-20260909`
at `caa230f73705f5bf8aadcc25394cd136963e858d`. The target four-file source/test/
audit bytes match the announced hashes and remained unchanged through all runs.
The later worktree HEAD does not change those target bytes.

Read completely: the approved full context specification, Task18 brief and
controller rulings, C3 controller rulings, the owning D3 hockey audit, complete
four-file change, full `context_transport.py`, owning hockey source including
original export/replay and comparison law, all eleven new tests, and relevant
B3 selection/conditional-approval and test-fixture paths. Current versus previous
owning export code was additionally loaded and compared by an independent test.

The only code changes being reviewed are the explicit Hockey family/version
adapter in `_feature_binding`, dispatch to the existing `apply_hockey_effect`,
and conversion of the known optimizer coefficient list to Python float scalars.
There is no new goal, overtime or conditional-mixture equation in transport.

## Actual reviewer test evidence

The first command on this freshly created worktree used a nested pytest basetemp
before `.pytest_tmp` existed. It produced **368 passed / 42 setup errors in
26.65 s**; every error was `FileNotFoundError [WinError 3]` while pytest attempted
to create that basetemp, before the affected test body. The JUnit output then
created the parent directory. This is disclosed reviewer setup error, not an
application finding or successful test run. No original assertion/source was
changed; the entire exact test selection was repeated with a new basetemp.

Successful independent runs:

1. **410 passed**, no skips, **28.47 s**: all eleven new D3 hockey cases,
   existing transport, B3 snapshots, owning hockey base/source/features/effects,
   and unchanged prematch regression.
2. **163 passed / one expected skip**, **21.12 s**: remaining hockey revision,
   numeric, correction-boundary and exact transport-byte tests, plus **23 new
   independent adversarial cases** in `test_independent_transport_hockey.py`.

Together these are **573 passed / one skip**, comprising the full 550 original
focused cases and 23 added independent cases. The only skipped case is
`test_owning_reader_keeps_existing_a1_path_contract[symlink]`, with actual reason
`Windows symlink privilege unavailable`. No new probe was skipped. This is not
a new complete repository test run; the owner's earlier counts are not used as
reviewer evidence.

The new probe file and all its assertions remained unchanged after the first
execution. It had no failing assertion, collection error or harness correction.

## Confirmed properties and adversarial boundaries

### Exact original law and coefficient transport

The independent probe loads the actual prior `context_models/ice_hockey.py`
source from `c871ba1^` into a separate in-memory module, without changing any
checkout bytes. On the same owning native-shaped original history it exports
both versions and verifies complete canonical BaseDistribution byte equality,
same original model hash, exact binary `.hex()` values for every parameter,
complete fitted optimizer canonical bytes and every coefficient's binary value.
All exported current coefficient entries are genuine Python floats and the
full original passes strict finite-JSON validation. Existing NumPy coefficients
are not replaced by refitting, clipping, rounding or generic JSON coercion.

Additional one-ULP changes to an original goal rate, original overtime chance,
original regulation market or original optimizer coefficient are rejected even
after rebinding the public feature reference hash. NumPy float64, int64 and
bool objects deliberately reinserted into the stored coefficient list are
rejected by the unchanged closed finite-JSON boundary.

All actual calculations use original rates and unchanged conditional OT through
the owning C3 law. Existing goalie-role and mathematical properties are covered
by the full owning focused tests; the new transport adds no parallel formula.

### Full publication/audit replay versus lightweight card identity

Rehashed comparison tampering was tested independently for both a goal rate and
the separately fixed overtime value. The old immutable consumer reference rejects
either altered payload. If a new public payload digest is deliberately constructed,
the lightweight reader can prove only that new identity, as explicitly documented;
it does not prove that the numbers are the actual learned-effect output. Even
a coherent owning-law distribution with such a changed parameter is rejected by
`replay_context_payload`, which reruns the actual effect and B3 selection.

This documented difference is not hidden or treated as source/approval evidence.
`context_consumer_reference` and full validation may replay the original fit at
the worker/audit boundary. Pure `project_context_market` does not. A new probe
patches the owning original fit, effect function, goal distribution, legacy
fit, B2 fit, SQLite connection, file open and socket connection to fail, then
successfully projects every stored market. Readout retains exact selected values
and complete used parameters. Mutating one returned card/ref does not mutate
the stored payload or the other returned card. Unknown, non-string or foreign
market names are rejected rather than mapped by a rounded card label.

### Approval and conditional scenarios

The transport preserves the owning B3 restriction: even a skater-only effect
derived from a whole unconfirmed-goalie lineup remains experimental and uses
the exact original central distribution. A separately fitted observed-recovery
effect on the same fixture can follow its matching synthetic approval; there
is no blanket goalie-context ban. This reproduces the intended observed versus
conditional separation through the full transport, not only bare C3 results.

Valid but mismatched approval coverage, base version, effect identity or a
post-cutoff evaluation remains experimental, with no used approval hash or
certified markets. An explicitly narrower synthetic approval certifies only its
named market, not every other coherent market in the complete distribution.
All synthetic approval envelopes in these tests are CPU fixtures, not actual
D2 evidence and not proof of a historically trained/qualified effect.

### Actual A1/B3 shared storage

The independent parallel case stores and reloads the effect using actual A1,
creates the full input key without first calculating a comparison, synchronizes
two threads with a barrier, and calls the real B3 `compute_once` on the same
temporary database and key. A spy on the owning `apply_hockey_effect` records
**exactly one comparison call**. Both results have identical canonical bytes;
two different market readers share the same immutable context ref and complete
used parameter bytes.

This proves the bounded B3 callback/owning comparison reuse. Original-reference
validation may internally replay its fit; this is not counted as globally once-only
source acquisition, feature preparation or worker work. No such upstream claim
is made by the packet or this review.

## Reproduction and immutable hashes

Run from the review worktree with
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`
using `-B -m pytest -q -p no:cacheprovider`, an existing `.pytest_tmp` parent and
a new basetemp for each execution. The independent probe file is under the
new directory named below. No target checkout or assertion needs modification.

```text
153aadec4306ae726fd1283249ca3cd9589ed87001b475212d0979aa654e1816  context_transport.py
5b27b2fc84c354e87e7842e5191658f9aea9f0213f4a9e5e2136270c4f1280d4  context_models/ice_hockey.py
cc28f733b8370ca363b73ae7a534895e5b4fd0abef55140249334b35d31f0a37  tests/test_context_transport_hockey.py
1608711b06af7d507cbb058d19c5398086d3d72a889547f21d48ab2a97dc8bf9  docs/audits/2026-09-09-d3-hockey-transport.md
bc76bf99fed257d3b880a58a9393e13b89f281a56a58932d094cb700d755623b  .pytest_tmp/d3-hockey-independent-20260909/test_independent_transport_hockey.py
2f65002e5022041be1a2312c8a18322d3cfb3828fa01d2f34184661a4c1b801c  .pytest_tmp/d3-hockey-review-focus-01.xml (initial missing-directory setup errors)
d73b29579cb687884b31f471f9b8385b7e05e73f672198fe97e8cd6e9a6c6a14  .pytest_tmp/d3-hockey-review-focus-02.xml (410 passed)
68651772a948ac988e1ea767e812d40db55ce4c1a1161c40211e867cba4eced1  .pytest_tmp/d3-hockey-independent-20260909/probes-01.xml (163 passed / one platform skip)
ef393f89ca54489bab28aae6c8d224012961795e387bc272d78ba7cad264a9df  sports_prematch.py (read only, unchanged)
414a7d198769546751e0407fd89a6e6edcd6892f9c86df83fdb3cc706955e8bb  context_snapshots.py (read only, unchanged)
```

Source/test hashes and clean Git state were rechecked after all runs.
No Git commit/merge/push, provider request, production database mutation,
VPS action, UI change, actual model approval or release action was performed.

## Remaining external boundaries

Native NHL collection and identity/source clocks, actual B1/FV reconstruction,
D1/D2 historical populations, real read-only D2 approval verification, runtime
capture, both actual worker/tab consumers and rendered browser behavior are
outside this isolated pure-transport packet. Existing models, Cricket, prices,
ranking, 15K, money, snapshots and tickets were neither changed nor reclassified.
A successful source/CPU test does not establish a beneficial real betting effect.
