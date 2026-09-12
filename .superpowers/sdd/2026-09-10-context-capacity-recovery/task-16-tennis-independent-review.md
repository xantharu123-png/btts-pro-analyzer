# Independent review — explicit streaming Tennis owner

12 September 2026. Reviewer: `c_history`; author: `c_tennis`.
Product and test files were read-only to this reviewer. The separately authored
C3 history remains subject to root's independent review; this document does not
self-approve C3, C2, the full application or a deployment.

## Final bounded result

The concrete P2 lifetime finding and its two residual binding cases are closed
on the Tennis bytes below. No further actionable numerical/reference finding
was found in this bounded comparison against the unchanged Tennis v2/v3 owners.
This is a component review, not proof of predictive quality, complete provider
data, calibrated fatigue coefficients, native capacity or publication authority.

Reviewed final identities:

- `context_storage_v2/tennis.py`:
  `aa94cd18b1280544f47e8c9e9a9a2b25ebf78c42a333c7e713a2db9b19c60d2d`
- `tests/test_context_storage_tennis.py`:
  `a114d7d75b8d68270c27d89c4cd12b82b34541cb23a4c0f5e95ef0dcf8cb1104`
- Shared C2 used in the final pinned regression:
  `31726af247e0f1b9c4a7e1bdedf233478a758cfc817dda377135aa5c6947c755`
- Shared C3 used in that regression:
  `aab750cefacbfcdd9c3165f08a8842d6f4dd378c7832bc1c44a8c170969e7c3e`

Freshly checked unchanged oracle/source identities:

- `context_models/tennis.py`:
  `313ffafacc367e7370312f478327d6453860ac0bf17bbcaf8102acdda49e4bab`
- `context_models/tennis_v3.py`:
  `ec6461b87656ecc5731992cc26f0ae69d20e878982706ebe3f1fd0599c43305c`
- `context_sources/tennis.py`:
  `80f1621f60e0b3daecef8abb5e44efeebd2c2bc6bc0df8161032daab78ceb739`
- `context_sources/tennis_status.py`:
  `8c2a8093aa2113564c34088227e5fb0a8c70faf9d52428e74c4995c505a57581`

## Reproduced P2 and correction

The first reviewed implementation retained its writable builder connection.
After a genuine source-normalized result, the following operations succeeded:

```python
connection.execute("PRAGMA query_only=OFF")
connection.execute("PRAGMA journal_mode=OFF")
connection.execute("CREATE TABLE unexpected(x TEXT)")
connection.execute("PRAGMA query_only=ON")
result.assert_intact()  # Incorrectly succeeded on the original version.
```

Actual independent output recorded `(total_changes, transaction_generation,
schema_version)` changing from `(44, 4, 8)` to `(44, 4, 9)`, with unchanged
reported values and an accepted lifetime. A read guard alone did not establish
immutable storage. The author changed publication to a genuinely read-only
SQLite reopening plus bound schema/journal state.

The next independent probe confirmed main DDL now failed as read-only and TEMP
DDL was rejected. It also found two remaining cases: `ATTACH ':memory:'` and
`PRAGMA temp.journal_mode=OFF` still let `assert_intact()`/`values` succeed with
unchanged counters. The author then bound the full database list, both journal
modes, main/TEMP schemas, resource PRAGMAs and the original copied limits.

Final independent replay tested eight operations after yielding only the first
`b"{"` canonical chunk: main DDL, a TEMP shadow view named `tennis_chosen`,
ATTACH, TEMP journal change, cache size, mmap size, max-page count and a
formally valid but changed limits object. **All eight were rejected before the
next chunk.** Main DDL also failed at SQLite's read-only boundary. Each case
retained the same `total_changes` and transaction generation; these were real
missing metadata bindings, not a disguised row-write or commit test.

This closes the reported lifetime issue for the stated private-owner boundary.
It is not a new protection claim against arbitrary Python code replacing class
definitions or the root publisher, and no public digest becomes HMAC authority.

## Independent regression evidence

Final pinned run: **202 passed in 98.14 seconds, exit 0**: all 83 new Tennis
tests plus 119 unchanged status-v3/context-feature tests. Tennis, tests, C2 and
C3 hashes above were checked again after the run. An earlier 202-test run also
passed, but the final run was repeated after the concurrent C2 author freeze.

```powershell
$env:PYTHONPATH='C:/Projekt/BetBoy/betboy-app/.venv/Lib/site-packages'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& 'C:/Users/miros/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m pytest tests/test_context_storage_tennis.py tests/test_tennis_status_v3.py tests/test_tennis_context_features.py -q --disable-warnings --maxfail=3 --basetemp=.pytest_tmp/independent-tennis-final-002
```

Additionally, 24 seeded, genuinely source-normalized small source databases
were examined at three cutoffs each: NOW minus 30 minutes, minus 10 minutes,
and NOW. Each source was built into **one** maximum C3 spool and its three
earlier views shared that spool. These 72 cases compare full materialized
canonical bytes, complete canonical digest and concatenated streamed bytes
against `_cold_replay_history` followed by unchanged `tennis_features_v3`.
All comparisons matched; all 24 source-file SHA256 values remained unchanged.

The seed was `160912`. Inputs include mixed legacy/status receipts, corrected
or removed participants, tied and backdated observations, missing/extra pairs,
unknown duration/end times, future receipts, cancelled/started target events
and non-exact decimal durations. The preserved fixture root is
`.pytest_tmp/independent-tennis-cases-7n9kr57c`. Final replay's length-framed
aggregate expected/output digest was
`dd2aba64568b7062861b2a9bd1681f8dad1e2e3012450eb602c90c03ad66ea79`;
the ordered 24-source identity was
`4902f02df50edab1fa249f744f1219d29cf5e7f6caeb1de7f4897d2dd3a63584`.
These extra cases supplement, not replace, the final pinned 202-test run.

## Semantic and boundedness review

- Complete source validation precedes event/participant pruning. Every event
  revision remains available, including obsolete target participation.
- Event groups retain original first-occurrence ordering. All latest rows are
  examined; the bounded Legacy representative pair is formed only after whole
  joint-identity and bilateral-player checks. It is not a fake full-history
  tuple or arbitrary prefix. Different identities remain conflicts.
- The two-target-player relevance summary produces the same affected states as
  the legacy full participant union; complete later participant withdrawals do
  not revive earlier load. Missing/extra/conflicting status associations and
  target-state overrides match the old owner.
- Each floating-point total uses original Python `sum` in the same event/row
  order. SQL SUM and repeated `+=` are not substituted. Windows remain
  `[cutoff - days, cutoff)`, using actual end time rather than planned starts.
- v2 timing/coverage is determined before v3 unknown/conflicting overrides;
  receipt-bound recovery is not relabelled exact. Missing health/travel input
  remains missing, not zero, healthy or rested.
- Canonical reference expansion includes all required workload/status/target
  receipts and delta unions. The immutable small header plus C2 descriptors is
  explicitly a new result format, not a legacy vector with silently empty refs.
  Canonical chunking reconstructs the complete old representation.
- The optional 64-MiB materialization bound is accurately described as this
  new helper's limit, not a historic per-feature contract. Normal streaming does
  not construct a decoded whole-tour or whole-event-group container.

Per-output SQLite/page/block/reserve checks do not establish the aggregate
multi-file 4-GiB input / 8-GiB workspace / 4-GiB free reserve, native RSS/AS,
240-second release or 1,800-CPU-second preparation contract. These remain with
root's C/B integration. The adapter does not alter model coefficients, source
schemas, prices, rankings or empirical approval; current equality is not a
claim that the original model's predictions are profitable or complete.

No Tennis product/test file, old model/source file, Git state, remote or VPS
was changed by this reviewer. This report is the only independent-review file
written for the Tennis assignment. Snapshot-parts review is a separate task.
