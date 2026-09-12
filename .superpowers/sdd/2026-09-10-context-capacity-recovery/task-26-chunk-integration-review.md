# Task 26 — independent snapshot chunk integration review

Date: 2026-09-12. Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.

## Verdict and exact scope

No new Critical/Important byte-transport, digest, transaction-lifetime or resource-PRAGMA regression was found in the reviewed narrow integration. **118 independent probes passed in 14.08 s, zero failures/errors/skips.** This is not native C acceptance, B authority, global disk accounting, whole-application release acceptance, or an independent review of the separate Task 23 costbook.

Reviewed current `context_storage_v2/snapshots.py` SHA256:
`f5dc0903874bede9fbbe3196146ba0b4b000d6a962916afd1d24efdb625f14ba`.

The old owner was loaded directly and read-only with `git show c5912a7:context_storage_v2/snapshots.py`, not reconstructed as a lookalike scalar loop. Its SHA256 is `75bfe759505d7b9a0719844ab397f2a86f0d05cf059d4a93a261f6a961539909`. A separate module name preserves the old exact descriptor class and functions. Test comparison verified that, after excluding the new import and `_payload_pieces`, the entire old and current snapshot-owner AST is identical.

The change imports `iter_canonical_ref_chunks` and yields its **complete** canonical reference array, capped by `min(65536, limits.block_bytes)`, in the same sorted JSON key position. There is no duplicate bracket/comma, omitted reference, scalar-interface change, decoder replacement, source opening or copied approval. The existing header, full payload byte count, raw-payload digest, legacy `{key,payload}` digest, complete pre-output verification, immutable-key rules, savepoint handling and outer transaction-generation checks remain intact.

No product/test source, checkout, index, server or original source file was changed by this reviewer. Only new ignored probe/evidence files and this report were created. The read-only `git show` was the specifically permitted baseline retrieval; no Git write/checkout operation occurred.

## Independent evidence

Probe: `.pytest_tmp/test_task26_chunk_integration_ccr01.py`.

- First run: `.pytest_tmp/task26-chunk-integration-ccr01-tests.xml`, 114 passed in 13.90 s.
- Final run: `.pytest_tmp/task26-chunk-integration-ccr01-final.xml`, 118 passed in 14.08 s.
- All basetemp and XML paths were new and never reused.

The probes compare actual old/current successful builds, exact serialized descriptor fields, stored snapshot rows, complete streamed bytes, materialization via the unchanged legacy decoder, raw SHA and legacy key/payload digest. Fixtures include the four real bounded worker outputs for tennis winner/serve with/without an effect, all three SQLite UTF encodings, and separate clearly synthetic Unicode/NUL/nested-`observation_refs` transport cases with 0, 1 and 79 references. The 79-reference case uses five real 512-byte-limited binary blocks and outer chunks of 1, 3, 67 and 512 bytes.

Both versions reject missing final blocks, reordered/extra members, changed header bytes and NUL-suffixed snapshot/reference metadata before the first payload byte. Both reject actual commit/rollback/close, writes, snapshot DDL, TEMP DDL, cache/mmap/max-page changes, row/text factory changes and changed limits at prefix, reference-body and terminal boundaries. Failed builds with incorrect source byte/digest/count expectations preserve the already committed snapshot.

The test also confirms `refs.py`, transaction tracking, `context_snapshots.py`, `context_transport.py` and `model_artifacts.py` are unchanged from the baseline (normalized line endings only for this comparison). Current old-source/model-facing hashes were stable before and after the performance run.

## Inherited boundary — do not overstate the integration

Four explicit old/current boundary observations execute a real `ATTACH DATABASE ':memory:'` after buffered reference output or after the last visible snapshot chunk. Both old and current outer snapshot readers can return the next already-buffered slice / successful terminal exhaustion without a new ATTACH admission check there. The new inner reader's fresh schema/footprint/ATTACH checks occur at **its** chunk boundaries; the outer reader keeps its pre-existing generation guard. This is not a new regression or authorization for mutation of the exclusively caller-owned connection, but it means the integration must **not** be described as fresh whole-footprint admission before every smaller outer snapshot slice or after every last outer byte. No global reservation/quota claim follows from either API.

## Actual complete snapshot timings

Result: `.pytest_tmp/task26-chunk-integration-ccr01-perf/result.json`.

Both sizes use actual separately built old/current SQLite refsets and snapshot parts, with sorted synthetic SHA-256 strings, the same finite known header and no sport/model-validity claim. `put_snapshot_parts` is measured as one complete fresh build on each already constructed refset. Reference creation is measured separately. Complete snapshot read timings each include fully exhausting the real public reader and joining every returned chunk; all three reads per case are then checked against every expected source byte and both full digests. Unlike Task 21's scalar-vs-byte API measurement, this comparison uses the same complete public snapshot byte API on both sides.

`tracemalloc` and Python profiling/tracing are off for all timings. CPU is `process_time`; wall is `perf_counter`. Native process trees, native RSS and global concurrent resources are not measured. Root/shared-host work may affect timings. There is no seven-day or target-scale extrapolation.

| References | Complete snapshot operation | Old CPU / wall seconds | Current CPU / wall seconds |
| ---: | --- | ---: | ---: |
| 5,000 | Fresh `put_snapshot_parts` | 0.187500 / 0.1881515 | 0.031250 / 0.0272298 |
| 5,000 | Full read, mean of 3 actual runs | 0.187500 / 0.1788927 | 0.0260417 / 0.0221203 |
| 50,000 | Fresh `put_snapshot_parts` | 2.062500 / 2.0607541 | 0.218750 / 0.2299677 |
| 50,000 | Full read, mean of 3 actual runs | 2.156250 / 2.1623682 | 0.2395833 / 0.2432040 |

The unchanged reference-set construction was separately 0.0305593 / 0.0324681 s wall at 5k, and 0.3121731 / 0.4029149 s wall at 50k (old/current fresh workspace runs). That run-to-run variation is not a reference-code regression: the exact same unchanged function is used.

Fixed observed settings: SQLite 3.53.1; UTF-8; 4,096-byte pages; cache -4,096 KiB; mmap 0; max_page_count 1,048,576; DELETE journal; FULL synchronous; FILE temp_store; trusted_schema OFF; read query_only ON. Default C limits are unchanged and identical in all timing cases.

Exact data:

- 5k full snapshot: 335,376 bytes; raw SHA `41bd21c9ba4023e2295d4f501a408b3ef65291cdf31214d0b99fe2d8bafbba71`; key/payload digest `d1a8934bdb04607a034cf61d09272f44035e96c208b9319c2c2ebed940c84149`.
- 50k full snapshot: 3,350,376 bytes; raw SHA `00331419b58203a81b467609070c6d3b40c1e2e0e4e4b7acf9f7fc10b7442e63`; key/payload digest `8a7ea7a2b0357729d0fb8e2538fcebfa550c9997f3ab3f1384526d2fb5d49b46`.
- Full old/current descriptor dictionaries are equal at both sizes. Each old/current database is 880,640 bytes at 5k and 8,695,808 bytes at 50k. Their raw SQLite file digests are **not** claimed equal; canonical descriptor/payload identities are.
- Source, complete old output and complete current output were separately persisted for each size. The performance workspace has 11 named files totaling 30,219,825 bytes, including its 9,673-byte result JSON; this is finite workspace measurement, not native/global quota proof.

## Current identities and reproduction

| Artifact | SHA256 |
| --- | --- |
| Current snapshot owner | `f5dc0903874bede9fbbe3196146ba0b4b000d6a962916afd1d24efdb625f14ba` |
| Unchanged new chunk owner | `49c41fac294bb6255e083cb07afad592a1460c84215dfa98842e233d8ef6d63d` |
| Unchanged scalar ref owner | `e80492be96ea0aacd5bb2038018c90bf8201d3e4a616d2574c456d5f9899cb2b` |
| Reviewed permanent snapshot tests | `77639cc754b0ef35285ad80c41a684fa63106e8f4d4dffb494ff8916f4a33d1b` |
| Independent final probe | `31b6a71cdc22b4d497b91749fa52ee5afa242fd355225cd7bc4ff0ac32ba2525` |
| Final 118-test XML | `70bc35781913eefaab7ec5461243046591ea187378aded4077a707ffb8783e39` |
| Performance JSON | `3d63dba252033757566e6f087bf81113dc254b7337f47a0677abd8129e7bc87e` |

Commands used the configured bundled Python, `.venv/Lib/site-packages` in `PYTHONPATH` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`:

```powershell
python -m pytest -q .pytest_tmp/test_task26_chunk_integration_ccr01.py --basetemp=.pytest_tmp/task26-chunk-integration-ccr01-final --junitxml=.pytest_tmp/task26-chunk-integration-ccr01-final.xml
python .pytest_tmp/test_task26_chunk_integration_ccr01.py --perf-workspace=.pytest_tmp/task26-chunk-integration-ccr01-perf
```

Use different never-existing output paths for reruns. Root's broader cohort/full-suite evidence is separate and is not replaced by these 118 narrow old/new differentials.
