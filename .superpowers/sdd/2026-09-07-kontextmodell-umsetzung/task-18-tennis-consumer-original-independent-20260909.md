# Independent shared Tennis consumer review — 9 September 2026

Disposition: **REQUEST CHANGES: two P2 findings and one smaller P3 regression.**

Reviewed clean worktree:
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-tennis-consumer-20260909`.
Frozen HEAD `3e415db63894ab6d206cf7b87ff0f804aded1ab0`, parent
`5d5bab6650df67bba653249e02f4c7a4e4691cdb`.
Reviewer `/root/worker_failures_20260909` is independent of the Root author.

No source, owning test, frozen legacy fixture, Git reference, provider or VPS was
changed. The reviewer created only ignored probes, temporary test stores, JUnit
evidence and this report. No full repository or browser run. Original probes and
all qualified negative assertions are retained unchanged; none were fixed,
deselected, weakened or relabelled as successful source tests.

## Findings

### F1 — P2: known A1 tour/schema header is not bound to the live original

Location: `tennis/context_consumer.py:112`.

The reader loads the actual `tennis-tour-state` artifact with the expected kind,
hash and predecision insertion clock but discards its payload without checking
the known wrapper/state version or state tour. All other public identities can
therefore be rebuilt around an ATP original that references an actual WTA state.
The reader returns a valid-looking ContextReference and probabilities for this
contradictory provenance. This is a cheap known-header identity contradiction,
not a request to replay the model, decode Elo/Serve tables, infer a historical
native player alias or enforce an invented latest-manifest rule.

The original two-case probe uses real temporary ATP and WTA A1 states published
by the existing fixture/worker. `_repoint_state` rebuilds the original artifact,
BaseDistribution, feature reference hash, B3 input key/payload digest and Shadow
sidecar/model-input reference. The ATP-to-ATP control passes; the ATP-to-WTA case
is accepted when it must fail. `tennis.tour_state._decode_wrapper` is spied to
ensure a fix does not turn a card read into model decoding.

The qualification uses the **actual stored Shadow `prediction_revisions`** and
the real `latest_predictions`, `tennis_model_signals`, `tennis_signals` and
`adapt_tennis_shadow`, not mocked loaders or a substituted projection. The
public revision hash is also recomputed. In that disposable SQL witness only,
the immutable-update trigger is temporarily removed and restored byte-identically;
the real revision decoder and remaining schema stay in place. Existing synthetic
model gates are set green solely to exercise the normal adapter, not to assert
real model QA. All three adapters accept the foreign-tour chain. Three otherwise
identical same-tour adapter controls pass.

Fifteen adjacent probes demonstrate the same absent header validation with
wrapper `schema` or nested state `schema` equal to Boolean/float/unknown integer/
null/string and state `tour` equal to null/list/object/Boolean/lowercase unknown
tour. These are manifestations of F1, not fifteen separate product findings.

Smallest repair: retain the already loaded artifact and validate its known
canonical header and scope before projection: explicit supported integer wrapper
and state versions, object shape needed to read the header, and an exact native
ATP/WTA state tour matching the original Event/Shadow tour. Use owning typed
integrity errors, without model decoding, prediction, fitting, new source calls,
whole-D4 execution, latest-manifest substitution or real-effect approval.

### F2 — P2: malformed false-valued context silently becomes legacy absence

Location: `tennis/context_consumer.py:51`, `json.loads(raw or "{}", ...)`.

Existing non-text `context_json=False`, `0`, `[]` or `{}` is converted to `{}`
before type validation. The loader returns `None` and the RisikoBet adapter takes
its legacy path. This contradicts the packet's distinction between genuine
optional absence and present malformed context.

Four direct reader negatives and four full real-Shadow/revision/RisikoBet
negatives reproduce acceptance. A subsequent read-only observation of all four
temporary affected stores confirms each produces one `match_winner` candidate
with `context_ref=null` and probability `0.12450000000000006`, instead of rejecting
the malformed row. No assumption that an empty output meant acceptance is used.

Four explicit legacy controls pass without opening/creating a context database:
the field is absent, is `None`, is the previously accepted empty string, or is
valid JSON `{}`. The other parser controls already reject malformed JSON text,
duplicate keys, non-finite constants, arrays/numbers/null in JSON and malformed
present `context_model` objects.

Smallest repair: distinguish the explicitly supported absent/legacy forms from
other values before parsing. Reject present unsupported non-text types instead
of using truthiness to replace them. Continue to allow genuine optional legacy
absence and valid legacy JSON objects. This is metadata integrity, not a price,
probability-zero, sport or market eligibility filter.

### F3 — P3: held-reader extraction leaks raw shape TypeError through generic API

Location: `context_consumers.py:70-71`.

The extracted transaction reader accesses `payload["base"]["cutoff"]` before
the original closed projection validator. A physically present, publicly
rehashed snapshot whose `base` is null/list/Boolean/integer now raises a raw
`TypeError` from this indexing rather than the existing `ContextContractError`
boundary. Four real temporary SQLite cases demonstrate that regression. Four
counter-runs execute the unmodified parent `5d5bab6:context_consumers.py` against
the same malformed shapes and produce the expected typed error.

No false probability is accepted here. The new Tennis wrapper already catches
these TypeErrors, so F3 is explicitly lower severity than F1/F2. The affected
contract is the still-public generic single-market API. A narrow structural
guard or typed conversion at the held-reader boundary is sufficient; do not add
an expensive recalculation or broaden corruption into an absence fallback.

## Positive controls and real integration observations

- The 49 owning cases independently pass on the frozen bytes. The wider reader,
  source/adapters, Risk store/UI, normal automation, workflow and legacy suite
  passes 631 tests plus 26 subtests, with one actual Windows symlink skip.
  This result does not cover the new negative witnesses or waive the findings.
- Twenty-four additional independent controls pass: duplicate/invalid JSON,
  closed artifact table including generated columns and BLOB storage, wrong
  original kind, publication before/at/after append, pure public wording and
  post-transaction trust failure propagation.
- A real WAL writer commits a changed original publication time between the A
  and B projections. The held read correctly returns one coherent earlier
  transaction; the next read sees the newly committed WAL time and rejects it.
  There is no immutable-main-file stale copy. Normal SQLite synchronization is
  permitted; this is not an absolute no-sidecar-write or race-proof VFS claim.
- Existing adapters retain the same unrounded used winner/reference. RisikoBet's
  reference is winner-scoped; set simulation, market orientation, SHADOW/PARTIAL
  states and its one-event snapshot contract are not promoted by the reference.
  Owning legacy fixtures compare original ModelSignal fields and Risk JSON/IDs.
- Source-level exceptions from the new loader are caught by the existing normal
  automation degraded-source path and RisikoBet source aggregator. No new source
  request is needed. F2 matters because it bypasses that exception path and
  becomes an ordinary legacy candidate instead.
- Actual UI and automation callsites were inspected, including reference
  serialization and public summary consumption; no new unrelated rendering
  failure was qualified. No rendered browser, live provider or VPS behavior is
  claimed from this inspection or the existing UI unit tests.

## Frozen source and owning artifact identities

Read the complete owning audit, all four source diffs, all 49 cases and both
frozen legacy fixtures. The eight-file diff is 973 insertions/24 deletions.
Raw SHA256 identities:

```text
context_consumers.py 9b3515a8aa69cd6884b03622970318d1c77c10e73a5e9fb56f1563cf9f334b1c
tennis/context_consumer.py f79917b4162ce46607f3dd901644a5d90b906d1656833aff23eb3b73f4aaa20b
ev_signal_sources.py 26970cb596d38b0458fdb42b1d62c822c8d9bd2b080d2601ec23b3a8cd83e705
riskobet_candidates.py a28bbd628d6f410259b293f6675c87db698305c3a6dc09f0a9c80efca82ebb2c
tests/test_tennis_shared_consumer.py 389b7ed1dd792b10b97677d55b5d71d411d8a4c0b6d19048880eaf8a31097db9
tests/fixtures/tennis_normal_consumers_5d5bab6.py dde7cf898418c95484a08da747b5e772075bbd1c5c8b31f74066f428325d37c7
tests/fixtures/tennis_risk_consumer_5d5bab6.py be0a947b0d2de13c749a4283345e8d628ea3f27f100f526ff12a89055e4c9682
docs/audits/2026-09-09-tennis-shared-consumer.md afebcad093874086b173039f97e3fe5c96a044a8574614c82f140342dd15406a
```

## Independent execution ledger

Python: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
All pytest runs use `-B -m pytest -q -p no:cacheprovider`, unique basetemps and
JUnit under `.pytest_tmp`. Ignored probes require
`-o 'pythonpath=. tests .pytest_tmp/tennis-consumer-independent-20260909'`.
No skips/deselections in the negative and control probe runs. No probe sources
or assertions were changed after their executions. Runs overlap; do not add
them as unique coverage.

| JUnit | Actual result | SHA256 |
| --- | --- | --- |
| `tennis-consumer-independent-owning-01.xml` | 49 passed, 8.49 s | `ea0bcb724e63264fa16b5a96f916e0c19d625615d5a974cdbf3a509d1f6542c7` |
| `tennis-consumer-independent-state-02.xml` | 1 qualified F1 RED / 1 control GREEN, 1.59 s | `47933abb7a3ba1d7768e36ef861861ee546be57a0e38c3d0092f48cc532c0afb` |
| `tennis-consumer-independent-state-03.xml` | 18 qualified F1 RED / 3 controls GREEN, 4.87 s | `04000c4e610d72519dfccd0fdc71b71e4a4d507cb75d5cb58c0db26aad462cea` |
| `tennis-consumer-independent-controls-04.xml` | 24 passed, 3.91 s | `b87bd349288892e0e2e98379e2396fdb4ba77050b76403bc209e7e71a6a14b2a` |
| `tennis-consumer-independent-regression-06.xml` | 631 passed, 1 skip, 26 subtests passed, 26.09 s | `4649f871f39df4de45df2cc94ca9a08040c588992f263ca6f7b56a79519d2f50` |
| `tennis-consumer-independent-falsey-07.xml` | 8 qualified F2 RED / 4 controls GREEN, 1.73 s | `60dd505c3cebf4806262cf68d0569428cc747b5a78083147908935e230b657df` |
| `tennis-consumer-independent-shape-08.xml` | 4 qualified F3 RED, 1.73 s | `3f9490bfc5fe666d5f910aca28deb196150d4abeaf40a34bbe0cad3655b2cd00` |
| `tennis-consumer-independent-shape-control-09.xml` | 4 parent-version controls passed, 1.83 s | `b77971f26f7ae9c835d17597cddf749d7190cf69544291fec7828a61dcbfde9f` |

Invocation05 named nonexistent `tests/test_context_domain.py` and ran zero tests
(0.07 s), a reviewer command mistake, not a source defect. Invocation06 uses the
actual `tests/test_context_domain_links.py`; no existing test was deselected.
The sole skip is `test_real_symlink_companion_is_rejected_if_host_supports_symlinks`
because this Windows host lacks real symlink privilege (1314). There is no new
Linux permission or deployment proof.

The 631-case file list: `test_tennis_shared_consumer`, `test_context_consumers`,
`test_context_reader_trust`, `test_context_domain_links`,
`test_context_domain_document`, `test_riskobet_candidates`, `test_riskobet_store`,
`test_riskobet_ui`, `test_tennis_live_legacy_parity`,
`test_context_runtime_tennis_live`, `test_context_transport`,
`test_context_transport_bytes`, `test_ev_signal_sources`,
`test_wettfinder_automation`, `test_workflow_integrity` (all under `tests/`).

## Original witness freeze

The following six files remain in this report's directory, including every
negative assertion. Run them together with a fresh basetemp and the import path
above to reproduce **31 qualified REDs / 36 passing controls** on frozen3e415db.
F3 parent controls intentionally read the exact parent source through a read-only
`git show`; Git history is therefore required for that independent control only.

```text
test_state_identity_candidate.py e562fb3c5ff9da21ac647e83309b8c4da49a9d0eb36aee64713589d615397973
test_state_identity_qualified.py 42adda1949e28f5362bb4e99ce456cad9991da7f6d542d962698562dba5e164f
test_falsey_context_candidate.py 8802ee37349b5d10cab037253e0a81e0867b6e0beb36fbccd261a2dec6c073bd
test_consumer_controls.py e8f4dc17e8e787c3e408fbb165590267a5800be256298f7c14d83e4a7ee24b4b
test_generic_shape_candidate.py c779fec0bd725f2210ec162c23df02ab727c3ef4f7da064ceccad72a0a1c4bbb
test_generic_shape_legacy_control.py fe0a17223aec7d65a16b90b374c873d739fd01b895419def844413d2a2a21c25
```

## Unchanged approval and deployment boundaries

All data is explicitly synthetic mechanics stored through real local APIs.
The findings concern direct reference/header and parser/exception contracts,
not proof that an attacker can forge an externally authenticated money ledger
or that these corruptions occurred in production. Consumer verification must
not be relabelled as D4 model/source replay, actual native historical ID/name
binding, empirical improvement or approval of a set family. Prices, Cricket,
15K, existing one-event snapshot identity, old rows and schema migrations are
outside any proposed repair. Main/GitHub/VPS state, browser acceptance, Linux
restoration and the whole integrated suite require separate verification.
