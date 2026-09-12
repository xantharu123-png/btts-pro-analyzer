# Task 21 — separate canonical C2 reference chunks

Date: 2026-09-12. Bounded implementation delegated by Root under the explicitly approved C work and `docs/superpowers/plans/2026-09-12-kontextspeicher-gesamtintegration.md`, item 5.

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.

## Result and scope

Implemented only the new `context_storage_v2/ref_chunks.py` and its new `tests/test_context_storage_ref_chunks.py`. The new public API is:

```python
iter_canonical_ref_chunks(connection, descriptor, *, limits=DEFAULT_LIMITS, chunk_bytes=65536)
```

It yields exact `bytes` segments of the existing canonical reference JSON array. An exact positive integer chunk size is required, bounded by the passed C block limit. It never opens a database, writes data, changes PRAGMAs, commits, manufactures an authority/approval object, or calls the old scalar iterator. No caller, export, snapshot, tennis or legacy API was changed. This is ready for Root's independent review and subsequent explicit integration, not already integrated C2b transport.

The full C contract and integration plan were read. Existing `refs.py` and `snapshots.py` validation/lifetime ownership remain authoritative; their source bytes were verified unchanged.

## Read contract

1. Admission requires the exact existing tracked SQLite connection, caller-held transaction and validated non-widened C limits. Capture the transaction/schema/resource generation and descriptor values before full validation.
2. Reuse the existing complete schema, SQL type/octet-length shape, footprint, descriptor, ordered membership, block SHA, canonical SHA and manifest SHA validation **before even the opening bracket is yielded**.
3. Stream one independently read/verified binary block at a time into at most a 67-byte canonical reference token and a bounded chunk buffer. Do not construct the reference list or complete canonical array in the implementation.
4. Before resuming internal work and again before each new public chunk, run the existing full generation checks, validate the exact descriptor and its retained values, recheck the full reference table schema, and remeasure the existing local footprint. This includes ATTACH/TEMP exclusion, physical/logical database bytes, named companions, free-space reserve, max-page cap, bounded negative cache and disabled mmap. Recheck generation again after these operations.
5. On terminal resumption, repeat these boundary checks and compare the actually emitted byte count and SHA against the originally validated complete descriptor. A commit/change after the last visible chunk therefore fails instead of returning successful exhaustion. A failed or abandoned stream grants no completed-read receipt.

Whole validation deliberately remains the unchanged `refs._verify_set`; that existing function can transiently retain the preceding bounded block while loading the next. Only the new emission phase promises one retained binary block plus `O(chunk_bytes)` Python buffering. Caller-retained output chunks are outside the iterator's own buffer. This is not an RSS measurement or a new global reservation mechanism.

## Tests and preserved evidence

All runs used new, never-existing workspace-local basetemp/XML names. No earlier evidence was overwritten.

- Initial test-first RED: `.pytest_tmp/task21-ref-chunks-ccr01-red.xml` — one expected collection error because the new module did not yet exist.
- First implementation GREEN: `.pytest_tmp/task21-ref-chunks-ccr01-green1.xml` — 65 passed in 3.46 s.
- Expanded typed-close RED: `.pytest_tmp/task21-ref-chunks-ccr01-typed-red.xml` — 69 passed, 2 failed. Closing before admission or during the actual complete block scan leaked a `sqlite3.ProgrammingError`. The new module's admission wrapper was corrected; no old owner code was modified.
- Anschluss GREEN: `.pytest_tmp/task21-ref-chunks-ccr01-green2.xml` — 261 passed in 26.47 s.
- Final current-bytes GREEN: `.pytest_tmp/task21-ref-chunks-ccr01-final.xml` — **261 passed, zero failures/errors/skips, 25.91 s** (XML suite time 25.884 s): 71 new chunk tests, 99 existing ref tests, 91 existing snapshot tests.

New coverage includes full old-scalar canonical differentials for UTF-8/UTF-16le/UTF-16be, empty/single/multiple references, 1/2/7/64-byte chunks, positive multi-block fixtures, absent late blocks, reordered/extra/wrong-version/foreign membership, and large NUL-suffix metadata rejected before Python materialization. Actual SQL mutations, commit/rollback/script/close, main/TEMP DDL, attached DB, cache/mmap/page changes, row/text decoding changes, forged tightened/widened limits, descriptor changes and loss of free reserve are tested both between chunks and after the final visible chunk. Mutations during the real whole validation and the actual emitter block read must not escape as the next chunk. Empty-set terminal lifetime is also checked.

Separate memory-only tests, with timing disabled, verified traced Python peak below 512 KiB for the full 12,000-reference / 94-block stream (4,096-byte blocks; 1,024-byte chunks), and for the UTF-8/UTF-16 NUL metadata rejection cases. The fixture/reference list is created before tracing; this measures iterator/rejection Python allocations only, not whole-process RSS or native SQLite allocations.

Final command, with the configured bundled Python and `.venv/Lib/site-packages` in `PYTHONPATH`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`:

```powershell
python -m pytest -q tests/test_context_storage_ref_chunks.py tests/test_context_storage_refs.py tests/test_context_storage_snapshots.py --basetemp=.pytest_tmp/task21-ref-chunks-ccr01-final --junitxml=.pytest_tmp/task21-ref-chunks-ccr01-final.xml
```

## Actual finite performance differential

Instrument is the opt-in `run_performance` in the new test file; it is not collected as a pytest benchmark. Both real C2 sets were built from reverse-delivered synthetic 64-lowercase-hex integer references. They are **not a sport, tennis, target-volume or seven-day profile**.

Final retained result: `.pytest_tmp/task21-ref-chunks-ccr01-perf2/result.json`. The earlier single-run `.pytest_tmp/task21-ref-chunks-ccr01-perf/result.json` is also preserved. Its short 5k chunk call returned a coarse process-time delta of zero; that does not mean zero CPU work. The final five-call series avoids relying on that single delta.

Five complete calls per API and size used the same held transaction/settings, alternating API order after the first call. Timed calls fully drain `iter_refset` into a list of scalar strings or the new iterator into a list of chunks. Complete old canonical encoding and the exact byte/hash comparison are outside both timing intervals; new chunks themselves are already canonical. This is an API-level comparison, not an integrated snapshot benchmark. `tracemalloc` was asserted **off** for every timed call. `time.process_time` and `time.perf_counter` were recorded separately; CPU deltas retain the host's visible quantization. Root's parallel suite/shared host may affect wall time.

| Synthetic references | Old scalar mean CPU / wall (s) | New chunks mean CPU / wall (s) | Bytes, each source/output | Output chunks |
| ---: | ---: | ---: | ---: | ---: |
| 5,000 | 0.087500 / 0.08934348 | 0.015625 / 0.01121914 | 335,001 | 6 |
| 50,000 | 1.131250 / 1.13015798 | 0.118750 / 0.11966960 | 3,350,001 | 52 |

Means are each the persisted sum of five actual measurements divided by five, not target-scale extrapolations. Every round compared **all** old bytes, new bytes and expected source bytes, with exact canonical SHA equality. Arrays were persisted independently as `source-5000.json`/`output-5000.json` and `source-50000.json`/`output-50000.json`.

- 5k canonical SHA256: `05a47d9dfa379d83e53fdcd7fad3ccf9610a1a061eee5e47ed4248f209ad41d2`.
- 50k canonical SHA256: `9eaf3f5b63f1328d33d9b07f83e9fc38ac9862d98bc9cb5f108f66888977434f`.
- Real SQLite database files: 868,352 and 8,683,520 bytes; one reference block per default-limit performance set, 160,000 and 1,600,000 binary reference bytes respectively. Tiny multi-block semantics are covered by the separate tests.
- The final performance workspace contains 7 named files totaling 16,930,673 bytes, including its 8,797-byte result JSON. This is measurement of that finite workspace, not a global quota proof.
- Fixed observed settings: SQLite 3.53.1; UTF-8, 4,096-byte pages, cache -4,096 KiB, mmap 0, max_page_count 1,048,576, temp_store FILE, journal_mode DELETE, synchronous FULL, trusted_schema OFF, query_only ON. Default limits remain input 4 GiB, tour 1 GiB, block 16 MiB, workspace 8 GiB, free reserve 4 GiB, 4,096 blocks/set. No limit relaxation occurred.

A **separate untimed trace observer** completely read each API again and checked the full bytes. Actual SQL statement counts were 30,064 old versus 409 new for 5k, and 300,064 old versus 2,709 new for 50k. The new counts include repeated complete table-schema and fresh footprint checks; generation PRAGMAs now occur at public chunk boundaries rather than each scalar. Trace callback overhead is excluded from the baseline timing records.

Reproduction into another new directory:

```powershell
python -c "import runpy; runpy.run_path('tests/test_context_storage_ref_chunks.py', run_name='__main__')" --perf-workspace=.pytest_tmp/task21-ref-chunks-NEW-unique-perf
```

## Exact current identities

| File | SHA256 |
| --- | --- |
| New `context_storage_v2/ref_chunks.py` | `49c41fac294bb6255e083cb07afad592a1460c84215dfa98842e233d8ef6d63d` |
| New `tests/test_context_storage_ref_chunks.py` | `01ac74ca49a06745beaf988a4e1e33284d299feaae181eea6b9ae063636c063f` |
| Unchanged `context_storage_v2/refs.py` | `e80492be96ea0aacd5bb2038018c90bf8201d3e4a616d2574c456d5f9899cb2b` |
| Unchanged `context_storage_v2/snapshots.py` | `75bfe759505d7b9a0719844ab397f2a86f0d05cf059d4a93a261f6a961539909` |
| Unchanged `context_storage_v2/tennis.py` | `aa94cd18b1280544f47e8c9e9a9a2b25ebf78c42a333c7e713a2db9b19c60d2d` |
| Final XML | `599632a0535a8c5a67828400400ceee0536aba1182c3c6715a1f887e0c3c2a09` |
| Final performance JSON | `23bf87d1b5c0c7ff5057f0d63e5ac426b6facd61cdee8a0d0d6310282d865bfc` |

## Remaining boundary

No native Windows/Linux C acceptance, complete active-generation 4-GiB budget, all-QA/build/output 8-GiB budget, continuously reserved 4-GiB disk guarantee, B proof, target-profile CPU/RSS/time outcome or deployment is established here. No Git/server operation was performed. Per-connection checks and named-file measurements still do not account for every global concurrent allocation or open-unlinked native temporary file.

Next bounded step after independent review: Root may explicitly integrate this **separate** byte interface into the snapshot owner while retaining the snapshot header, payload/key digest, whole-validation and terminal lifetime checks. `iter_refset` must remain unchanged; no trusted shortcut or copied approval is implied by chunk transport.
