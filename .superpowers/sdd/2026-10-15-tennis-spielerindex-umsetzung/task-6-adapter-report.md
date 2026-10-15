# Task 6 acceptance adapters

Status: **DONE, scoped local verification PASS**. Final frozen covering run:
**238 passed / 9 unchanged skipped / 0 failures / 0 errors**. This is not a
whole-suite, privileged-native or production acceptance claim.

Base: `21725b0d7a5ae6d29996de44e24313c38f765442`, canonical
`C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013`, branch
`codex/audit-repairs-20261013`. This is test-adapter repair only. Product sources,
frozen catalogues, pins and validators are not amended. No whole-suite,
production, deployment, API, scan, backup, cleanup, dependencies or model changes.
Inherited `output/audit-repairs/` and prior FAIL/INCOMPLETE evidence are preserved.

## Root causes and changes

1. The original snapshot-interleaving test supplied `factory=InterleavedReader`
   while `_reader` already supplied `factory=_DatasetConnection`, causing a
   duplicate-keyword TypeError before SQL. Its interceptor now subclasses
   `dataset._DatasetConnection`, replaces `kwargs['factory']`, and forwards
   `**kwargs` exactly once. The original `.6` old-snapshot assertion, exactly one
   concurrent commit assertion, and fresh-read `ContextIntegrityError` assertion
   remain unchanged. Production BEGIN, factory, filesystem identity and
   authorizer behavior remain untouched.
2. The native V1/V2 catalogues correctly pin historical receipt owners, while
   the test-only source helper supplied today's changed owners. Two explicit
   `HISTORICAL` DATA mappings and exactly two LF attributes fix this mismatch.
   No dynamic Git lookup, source execution/import, runtime qualification,
   catalogue pin or validator change was added.
3. Added separate six-case V1 and six-case V2 negative tests: both receipt owners
   with current, historical-plus-newline and CRLF bytes. Each replaces the code
   member size/hash, recomputes admission identity, allocation and plan digest,
   then requires the actual `unchanged owner pin differs` rejection. Two
   independent fixture-size/SHA256/LF tests use literal requirements.

## Historical DATA provenance

Both blobs are from `7a099e36762fa3b9fd23d5ae550de08ba5fb9f8a` (`3279be4^`).
`git ls-tree` verifies their identities; read-only external `check-preservation.py`
independently compares fixture bytes with `git cat-file blob`, exact length,
literal SHA256 and absence of CR bytes. This is fixture provenance, not current
production qualification.

| Owner | Fixture under tests/fixtures | Git blob | Bytes | SHA256 |
| --- | --- | --- | --- | --- |
| `context_storage_v2/receipt_corpus.py` | `native_context_receipt_corpus_7a099e3.py` | `139e6ad629c8f01f379490981e727fcdc1945bb3` | 41,136 | `fdbebbed9e0b14380d7226660f5f42ec9508ec2b04c727a856bb36747ae660d6` |
| `context_storage_v2/receipt_append.py` | `native_context_receipt_append_7a099e3.py` | `d503bd2cdd497ac201a8e295ce7bba9eb8681e76` | 9,065 | `e96b807b2b003b00b740b0b64ba48d86ac3fd5c930ce11bdf2a40b5436fa06e9` |

## Exact test setup and receipts

All artifacts are under
`C:/Projekt/BetBoy/output/tennis-player-index-20261015/task6-adapters/` (`A` below).
Read-only commands run from canonical. Each pytest invocation uses existing
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/Scripts/python.exe -B`
and offline `C:/Projekt/BetBoy/output/context-audit-20261011/pytest_final.py`,
`DJANGO_SETTINGS_MODULE=siteconfig.qa_settings`,
`PYTHONPATH=<canonical>/portal`, fresh `TEMP=TMP=A/temp-<run>`,
`--basetemp=A/basetemp-<run>`, `-q -ra --junitxml=A/<run>.xml` and full
stdout/stderr `A/<run>.log`. `run-focused.ps1` refuses pre-existing receipt paths
and records exact targets, UTC times and exit in `<run>-result.json`.

The three original IDs (`OLD`) are:

```text
tests/test_context_reader_trust.py::test_one_reader_transaction_does_not_mix_live_schema_and_payload_revisions
tests/test_native_context_qa_coordinator.py::test_v2_manifest_accounts_external_controls_and_v1_refuses_it
tests/test_native_context_receipt_diagnostic.py::test_closed_manifest_recomputes_complete_acyclic_identity_and_slot_plan
```

Exact commands (PowerShell array arguments expanded in each `*-result.json`):

```powershell
& "$A/freeze.ps1" pre
& "$A/run-focused.ps1" -Run red -Targets $OLD
& "$A/run-focused.ps1" -Run green -Targets ($OLD + @(
  'tests/test_native_context_receipt_diagnostic.py::test_receipt_owner_historical_data_has_independent_exact_hash',
  'tests/test_native_context_receipt_diagnostic.py::test_closed_manifest_rejects_nonhistorical_receipt_owner_even_when_rehashed',
  'tests/test_native_context_qa_coordinator.py::test_v2_manifest_rejects_nonhistorical_receipt_owner_even_when_rehashed'))
& "$A/run-focused.ps1" -Run sensitivity -NoBegin -Targets @($OLD[0])
& "$A/freeze.ps1" frozen
& "$A/run-focused.ps1" -Run covering -Targets $COVERING
& "$A/run-focused.ps1" -Run covering-escalated -Targets $COVERING
& "$A/freeze.ps1" post
```

- Fresh pre-amendment RED: **3 failed / exit 1 / 7.97s**. Exactly the three old
  failure IDs and original TypeError/two owner-pin failures; no unrelated errors.
- Exact old IDs plus all 14 added cases GREEN: **17 passed / exit 0 / 3.02s**.
- Genuine sensitivity negative: **1 failed / exit 1 / 5.21s**. External plugin
  `no_begin_mutation.py` AST-removes precisely one `connection.execute('BEGIN')`
  from the in-memory `_reader`, preserving every other statement. It never
  writes product source. The repaired *original* test fails at its old-snapshot
  `.6` read because actual concurrent `b'not-json'` bytes reach `_decode_snapshot`,
  which raises `ContextIntegrityError: invalid persisted context snapshot`.
  This is actual SQLite snapshot sensitivity, not a setup/factory failure.
  A fresh process in the covering run restores the untouched source path.

## Final covering scope and preservation

Narrow `rg -l 'native_context_chain_fixtures' tests -g '*.py'` identifies only
`test_native_context_chain.py`, `test_native_context_qa_coordinator.py` and
`test_native_context_receipt_diagnostic.py` as direct helper users.
`COVERING` is exactly the entire following six modules, no deselection:

```text
tests/test_context_reader_trust.py
tests/test_context_consumers.py
tests/test_tennis_player_index_consumers.py
tests/test_native_context_qa_coordinator.py
tests/test_native_context_receipt_diagnostic.py
tests/test_native_context_chain.py
```

`freeze.ps1 pre/frozen/post` records SHA256 for **1,102 tracked non-test owners**,
including every original product owner, and all tracked/new test files plus
`.gitattributes`. Pre/frozen non-test equality is required; post also requires
all frozen test bytes/membership identical. The only non-test amendment is the
two explicitly permitted LF attributes (excluded from product-owner hashes).
Report creation occurs after the test/source freeze and is documentation only.

External `check-preservation.py` (exit 0, `preservation.json`) AST-compares every
original test/decorator in both native modules against BASE: all **31 + 12**
test function bodies and parametrizations unchanged. All **13** original reader
test functions/IDs/decorators remain, and every original snapshot-test assert
and `pytest.raises` context is identical. The only reader changes are its
interceptor base and factory forwarding. Existing inventory-negative test IDs
remain exactly as before.

The first default-sandbox covering attempt completed once: **14 failed / 224
passed / 9 skipped / exit 1 / 546.38s**. `covering.log/.xml/-result.json` are
retained, not overwritten or recast as a pass. The exact failures were:

- `test_main_and_every_existing_companion_must_be_singly_linked_before_open`
  for `[]`, `[-wal]`, `[-shm]`, `[-journal]` (reader-trust).
- `test_actual_wal_shm_hardlink_never_overwrites_unrelated_file` (reader-trust).
- `test_invalid_member_introduced_during_connect_is_rejected_and_connection_closed`
  for `[]`, `[-wal]`, `[-shm]`, `[-journal]` (reader-trust).
- `test_successful_read_rechecks_new_companion_trust_before_return` (reader-trust).
- `test_historical_hardlink_occupancy_is_inert_but_active_slots_reject_it`
  (native receipt diagnostic).
- `test_timezone_real_held_copies_and_rechecks[hardlink-source]` and
  `test_linked_input_is_rejected_without_creating_copy` (native chain).
- `test_real_sample_calls_actual_corpus_once` (native receipt diagnostic).

The first 13 are explicit `os.link` `PermissionError: [WinError 5]` failures in
the restricted Windows token. The last is the unchanged production
`StorageLimitError: corpus exceeded its original single-call deadline` after
the slower sandbox execution; QA02 had completed this same test in 158.943s.
No budget, assertion, skip or source was relaxed. Consistent with the brief and
the original QA02 execution context, the identical frozen six-module command
is run once under normal `require_escalated` execution, with separate fresh
temp/basetemp and receipts. All original repaired IDs and 14 new cases had
already passed even in the default-sandbox attempt.

The authoritative final frozen covering run completed once under normal
escalation: **238 passed / 9 skipped / 0 failures / 0 errors / exit 0 / 300.77s**,
UTC `2026-10-15T22:01:25.0336420Z` to `22:06:27.9730150Z`.
The unchanged corpus test completed in **147.141s**, below its original
single-call deadline, with its original real-corpus assertions intact.
No warning summary was emitted. `covering-escalated.log/.xml/-result.json`
hold the complete result. Original snapshot test is restored GREEN in this
fresh unmutated process after the sensitivity failure.

`summarize.py` exit 0 reconciles JUnits against both full QA02 shards: **all 233
original IDs retained exactly, 14 added, 247 total, zero missing, identical nine
skip IDs**. The nine skips are one unavailable real Windows symlink privilege,
six Linux root fork/pidfd/wait4 cases, and two explicitly prepared Linux native
coordinator cases. They are inherited capability gates, not new/forced skips.
Full failure IDs from the default attempt and all receipt hashes remain in
`summary.json`. `freeze.ps1 post` exit 0 proves every one of **1,102 original
non-test owner hashes unchanged**, and every frozen test byte/membership
unchanged through both covering runs. No product source changed at any point.

Final frozen hashes (SHA256):

| Receipt or owner | SHA256 |
| --- | --- |
| `product-pre.json` = `product-frozen.json` = `product-post.json` | `66cb221fe004ff1c76568c4414def70e593291dde1fce21889d942a4c3111d7f` |
| `tests-frozen.json` = `tests-post.json` | `34233c7cfa708d80525f361a98b57cd0f1ed5dd1de1681c45249a223928bd0f7` |
| `covering-escalated.log` | `c17e701af78847701e7c8aa656dc525f7a9f2a1d0d26f98a471b35b5ee2b7179` |
| `covering-escalated.xml` | `d7f1f002b6209df3e869d06f51cf3b07fbd800f7d0c80638a70819e66339bd6b` |
| preserved default `covering.log` | `77b63d934e658e9e32ab3a91ac1b519fd1e7a9986b23d53aa1040e08b10e0007` |
| preserved default `covering.xml` | `32128038d78003a4413e1b713a20e42e244cd3979c14112d80a5c19e602efeef` |
| `.gitattributes` | `2137d210de9239c395e4457485e63d39f806306edd4ec54b6940ad83343b1b39` |
| `tests/native_context_chain_fixtures.py` | `caca202d6653c7d7ff3b83f8baa773534d305f5e69c03d81c7cb09ca5495d7eb` |
| `tests/test_context_reader_trust.py` | `6315a87fae2888f174776912dbb3da10a50e8417812f4a981af35567c0a25881` |
| `tests/test_native_context_qa_coordinator.py` | `559a7552ace6c8bc6ed958b573148bf1996ef9d178b591a44bcd0ec40a5512e7` |
| `tests/test_native_context_receipt_diagnostic.py` | `3d307288170534437e466386fb3b71dc6b93b3c2c36062d0f61f780fa6b0ae85` |

Both fixture hashes are independently recorded in the provenance table above.
`summary.json` additionally records exact RED, GREEN, sensitivity and execution
helper hashes; no failed receipt was deleted or overwritten.

## Self-review and remaining concerns

Reviewed the exact owned diff and `git diff --check`; no assertion weakening,
old parametrization expansion, product source amendment, pin replacement or
unknown fixture mapping. Fixtures remain inert DATA, never imported/executed.
Independent scoped review and fresh whole offline QA belong to the controller;
this report does not claim whole-suite or native/production/release acceptance.

Commit scope is exactly the seven owned test/fixture/attribute paths above plus
this report (eight files total), on `codex/audit-repairs-20261013` only. No push.
The containing exact-file commit identifies this report and its tested adapter
bytes together; its hash is returned to the controller. The inherited untracked
`output/audit-repairs/` is excluded. No remaining adapter concern is known;
independent scoped review and fresh whole offline QA remain open controller gates.
