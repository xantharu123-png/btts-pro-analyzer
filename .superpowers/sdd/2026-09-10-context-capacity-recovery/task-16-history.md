# C3 — complete private disk-backed Tennis history

12 September 2026. Author: `c_history`. Specification C
`08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba`
and the current implementation plan were read in full. This is the author's
implementation record, **not independent approval of this author's C3 code**.
Root owns that review and every integration/publication decision.

## Exact authored files and local verification

- `context_storage_v2/history.py` SHA256
  `aab750cefacbfcdd9c3165f08a8842d6f4dd378c7832bc1c44a8c170969e7c3e`.
- `tests/test_context_storage_history.py` SHA256
  `b23a6a0b426abdd892151303ac9df5cef265788babda1c9c9e8894d77def28ce`.

Final selected run: **150 passed, 27.82 seconds, exit 0**. This comprises
68 C3 tests, 39 unchanged Tennis status-v3 tests, 42 root-owned raw-inventory
tests and root's unchanged TEMP-shadow integration regression. The inventory's
independently reviewed baseline below had 41 tests; root added a Limits-owner
test while this final run was prepared. No full product-suite, VPS or capacity claim.

Command, using existing dependencies without changing either virtualenv:

```powershell
$env:PYTHONPATH='C:/Projekt/BetBoy/betboy-app/.venv/Lib/site-packages'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& 'C:/Users/miros/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m pytest tests/test_context_storage_history.py tests/test_tennis_status_v3.py tests/test_context_storage_inventory.py tests/test_context_storage_integration.py::test_private_history_temp_schema_cannot_hide_complete_rows -q --disable-warnings --maxfail=3 --basetemp=.pytest_tmp/c3-history-012
```

Earlier setup failures were environmental: bundled Python has no standalone
pytest installation; the copied `.venv` executable names an absent Python;
the default per-user pytest temporary directory is inaccessible. The explicit
existing site-packages and unique workspace basetemp resolve these without
installation or dependency mutation. Earlier 8-MiB tracemalloc test exposed
unnecessary 16-MiB file-hash read buffers; the final code hashes in at most
1-MiB portions. The real 600-revision test now passes its stated bound.

## Interface and completeness boundary

`build_history(receipts, directory=..., cutoff=datetime, tour='ATP'|'WTA',
input_identity=<actual source-file SHA256>, limits=DEFAULT_LIMITS)` returns an
exact `HistoryView` only after the complete operation finishes.

Input must be the actual `VerifiedReceiptMapping`, with its completed physical
validation, exact `TrackedConnection`, original transaction generation and
validation stamp. The connection is query-only; the concrete file identity,
SHA256 and absence of SQLite companions are bound before/after construction.
No arbitrary iterator, callback argument, replacement connection, preselected
tuple or caller-provided `complete=True` flag can publish this view.

Every physical receipt is visited again without source-side SQL tour or cutoff
pruning. The unchanged decoder and `select_tennis_observations` run as their
actual owners: recognized causal source rows are validated before the owning
tour filter. The existing future exclusion remains the source owner's rule;
physical future corruption still fails complete physical validation. Unrecognized
sources are not promoted to Tennis history. D2-protected finals remain opaque:
only their closed outer receipt binding is inspected, not body or outcome.
Unknown protected references and protection of a non-final row fail closed.

This does **not** prove that the provider delivered every real match, authorize
D2 protection, replace the upstream artifact/physical checks, or grant HMAC
proof reuse. The parent owns those checks and the sealed input. Registrations
on the original source connection are the existing input owner's concern;
this adapter does not claim a new process-isolation boundary against arbitrary
Python execution or direct base-class bypasses. The later B code-closure and
root-controlled publisher remain mandatory.

The output is a fresh private SQLite allocation; no source rows are edited.
Its own writer closes before a private query-only held reader is opened. Binding
includes input identity, receipt/opaque counts, tour, source versions, selection
and ordering identities, maximum cutoff, selected count/canonical byte total,
length-framed ordered selected digest and actual spool digest. A public digest
is transport identity, not authority.

`HistoryView` exposes `.tour`, `.cutoff`, `.row_count`, `.canonical_bytes`,
`.binding`, `.assert_intact()`, `.iter_rows()`, `.iter_events(exclude_event=...)`
and `.event(event_key)`. Event handles expose `.event_key`,
`.latest_observed_at`, `.iter_rows()` and `.iter_latest_rows()`. The private
connection is not a public extension point; ordinary factory/callback/extension
installation is rejected and poisons further use. Source/view transaction end,
factory changes, changed file identity, replacement connection and interrupted
build cannot revive a completed view. A clean context-manager exit checks for
changes after the final read. Mutating returned dictionaries does not mutate
the retained bytes, and intentionally stopping one read is not failed publication.

Root's subsequent independent P2 reproduction found that `mode=ro` alone did
not stop a TEMP view named `history` from hiding main rows: no main-file bytes,
`total_changes` or transaction generation needed to change. The repair binds
main/TEMP schema versions, both journal modes and the attached database set at
publication and checks them before/after each consumption step. All actual
source/spool table references are schema-qualified (SQLite's CREATE INDEX
syntax qualifies the index, thereby choosing its table schema). Twelve new
negative cases exercise TEMP shadow views/tables, unrelated TEMP DDL, CREATE
then DROP, ATTACH, TEMP journal policy and all row/event/prefix consumers.
Root's originally failing integration test is unchanged and now green. The
first added CREATE/DROP test encountered SQLite's own table lock while a read
cursor was open; its corrected case closes that cursor before reverted DDL
and verifies that the next new read still fails. Parent re-review remains
required; this author's repair is not independent self-approval.

## One complete spool, multiple earlier cutoffs

`.as_of(cutoff)` constructs a non-owning immutable prefix view on the **same**
file, never another whole-tour copy. It cannot widen beyond its parent's cutoff.
Its own complete prefix pass validates selected source rows and recomputes
count, canonical bytes and ordered digest before returning the prefix. This is
not cached semantic proof reuse or a performance claim.

The equivalence is narrow and explicit: after a successful complete maximum
build, the old owner retains a row exactly when `observed_at <= cutoff` and its
validated tour matches. Filtering the complete maximum spool on the same
observation clock therefore yields the same canonical total order. All revisions,
ties and rows unrelated to current players remain. The earliest event occurrence
is unchanged when inside the prefix; the latest event clock is recalculated
within that prefix. No old "latest" metadata is reused for an earlier decision.
Parent closure invalidates all prefixes; closing a prefix leaves its parent open.

The implementation never constructs a decoded complete-history list, tuple or
event dictionary. The SQL spool stores all selected revisions and a disk index
for event first/latest observation. Iteration yields one decoded row at a time.
The reference tests may collect tiny expected tuples solely for byte-for-byte
comparison with the unchanged cold owner.

## Resources and explicit limits

- Every selected canonical row and cumulative tour byte is charged; one row
  must fit the 16-MiB block cap and the entire selected tour the 1-GiB cap.
- Limits use the fixed class validation owner, not a shadowable instance
  method. The exact allowed field set and values are bound at construction
  and rechecked during consumption. Two regressions reject a forged instance
  validation callback and a later formally valid but changed resource contract.
- The private reader additionally binds cache size, mmap size, max-page count
  and temporary-store mode. Its main page cap is reinstalled after read-only
  reopening and temporary storage is explicitly FILE. Three new mutation
  tests reject changed cache/mmap/page policies before the next yielded row;
  the fourth proves SQLite itself rejects a TEMP-store switch inside the
  held transaction. It is not reported as a successfully performed change.
- Before creating the schema, actual SQLite `max_page_count` is installed and
  checked against `min(input_bytes, workspace_bytes) // page_size`. This was
  added in response to root's independent review: periodic size measurement
  alone could otherwise overallocate between checks.
- A real `SQLITE_FULL` regression with an 8-KiB output limit proves rejection
  before periodic measurement, no returned partial view, and file size <=8 KiB.
- Local private allocation and free-space checks remain bounded. Root still
  owns the aggregate 4-GiB entire input set, every QA/backup/journal allocation,
  8-GiB preparation workspace and continuous 4-GiB free reserve. This adapter's
  per-allocation admission is not a substitute for aggregate accounting.
- A synthetic genuine-source-normalized event with 600 distinct revisions is
  read repeatedly and as a single event group without retaining its rows;
  traced Python peak is asserted below 8 MiB. This is not a native RSS/AS,
  complete seven-day corpus, 240-second release or 1,800-CPU-second preparation
  result. All those measurements and the B lifecycle remain outstanding.

Failed isolated build files remain for the parent's bounded cleanup policy;
there is no silent old-data deletion or automatic reuse of partial databases.

## Independent review of root's raw inventory

Read complete `inventory.py` and its tests twice, including the final correction.
Independently reviewed baseline identities (before root's later isolated
Limits-owner hardening included in the 150-test run):

- `context_storage_v2/inventory.py` SHA256
  `8cbc2dd6f12b1f9f602162f05491788aacd63fd3172913c85593808f2d7946c7`.
- `tests/test_context_storage_inventory.py` SHA256
  `209c306b16bdbb75b259034f7680e6bb96a824387bf1eaf79e4bb234ec85205b`.

Finding raised and now closed: calling the old schema owner directly would let
its `PRAGMA foreign_key_check.fetchall()` allocate every broken foreign-key row
on an invalid large input. Root added a bounded first-error preflight before the
old owner. A real 10,000-invalid-reference test asserts failure before that owner
is invoked. The final combined run includes all 41 inventory regressions.

No further actionable finding in this bounded raw-inventory review. The typed
NULL/integer/text/blob framing, complete sorted logical keys, old raw bytes,
UTF-8/UTF-16 inline/incremental equivalence, image/metadata limits, changed-input
rejection and comparison across held transactions are coherently covered.
This result is not independent approval of the separate C3 code authored above,
nor approval of unbuilt migration, snapshot assembly, source validation, backup,
protected proof publication, full runtime closure or deployment.

## Handoff

Only the two owned new code/test files and this report were edited by this
author. No old model/source/runtime module, index, commit, remote, VPS or service
was changed. Root can now perform the independent C3 diff review and integrate
the separate streaming Tennis owner against the interface above.
