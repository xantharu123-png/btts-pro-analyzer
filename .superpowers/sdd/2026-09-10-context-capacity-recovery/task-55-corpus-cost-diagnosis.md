# Task55 — measured local corpus cost diagnosis

## Outcome

One unchanged, complete 100-addition owner call finished with **exit0**, followed
by fresh raw-inventory equality, physical validation of all100 receipts and
source/output/ledger hash checks. The measured local hotpath is repeated
ancestor/path observation, not hashing or the actual receipt SQL operation.
This is a capacity diagnosis, not a second Task48 correctness review, product
change, native failure/pass, growth, consumer, B or release acceptance.

The initial per-field hypothesis is **not supported for these small inputs**:
`inventory.py:181-200` only invokes the supplied guard for incremental large
fields. The profile records3000 `_field_hash` calls taking0.007266s cumulative,
with no caller edge from that function to `_Build.check`. All400 per-input
full checks come from the four explicit `append_one` boundaries
(`receipt_corpus.py:446,453,464,480`). Large incremental fields remain a
distinct, unmeasured case; no value cap or guard reduction follows.

## Execution and exact scope

From the existing worktree, once only:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B '.pytest_tmp/task55-profile-20260912-01.py'
```

Instrument: `.pytest_tmp/task55-profile-20260912-01.py`,8792B,
SHA256 `afc1a2e1751be5b92d23593e49329a747255b6b1a38e2bbcfb9e2a80e324371d`.
Fresh, never-reused attempt directory: `.pytest_tmp/task55-profile-20260912-bt-01`.
No product function was patched or replaced. The instrument creates the actual
seven-table old schema with an empty transport baseline, streams100 genuine
`normalize_tennis_status` records and profiles `build_receipt_corpus` from entry
through copy, all appends, ledger finish, commit/close, complete verification,
hashes and terminal closure. The caller then independently reopens and runs
`inventory_raw` and real `VerifiedReceiptMapping.validate_all`; this empty
transport fixture supplies no consumer source-truth or model authority.

| Observed phase | CPU seconds | Wall seconds |
| --- | ---: | ---: |
| Complete owner, cProfile enabled | 10.625 | 10.702274400 |
| Additional cold inventory/physical/hash validation, unprofiled | 0.015625 | 0.034772900 |
| Entire instrument through pre-summary measurement | 10.843750 | 11.076628700 |

The last row includes setup, imports, stat serialization and code-pin checks,
but excludes subsequent summary serialization/stdout/process exit. Exit0 is
separately observed; that row is not terminal native process accounting.
Runtime: Windows11 build26200, Python3.12.14, SQLite3.53.1. cProfile overhead is
included; there was no same-size unprofiled control, so its overhead is not
quantified. No native CPU/AS/RSS/output measurement was performed.

Root's earlier unprofiled1000-record diagnostic is separate supplied evidence:
87.125CPU/87.6031347wall for the owner, same61440B source/hash. It was not rerun.
Neither the difference in sample sizes nor these two timings establishes a
scaling law, native failure, native benefit or successful full-corpus fit.
This deeply nested Windows worktree repeatedly traverses long overlapping
ancestor chains; native QA uses a much flatter namespace and a different OS/
runtime. Its costs must be measured there later, not inferred here.

## Actual hotpaths

Stats contain6,333,836 calls (6,302,349 primitive),10.702s total. Cumulative rows
overlap/nest and must **not** be added as independent cost buckets.

| Function / location | Calls | Cumulative seconds |
| --- | ---: | ---: |
| `_Build.append_one`, receipt_corpus.py:445 | 100 | 9.585067 |
| `_Build.check`, receipt_corpus.py:396 | 404 | 7.826255 |
| `_Build.source_check`, receipt_corpus.py:216 | 2893 | 7.688323 |
| `_assert_no_symlink_components`, runtime_paths.py:67 | 11240 | 6.904326 |
| `_Build.capacity`, receipt_corpus.py:274 | 406 | 5.219267 |
| `_Build.namespace`, receipt_corpus.py:234 | 1233 | 3.745 |
| `_Build.check_profile`, receipt_corpus.py:364 | 406 | 2.640522 |
| `_workspace_bytes`, copying.py:79 | 410 | 1.789 |
| `_HeldRead._current`, inventory.py:66 | 3195 | 1.159 |
| Actual `append_observation_in_connection`, receipt_append.py:92 | 100 | 0.093 |
| `shutil.disk_usage` | 410 | 0.018466 |
| `_field_hash`, inventory.py:162 | 3000 | 0.007266 |

`nt.lstat` alone executed223580 times,5.334s own time (~49.8% of the profiled
owner); `nt.stat` added45699 calls/1.194s own time. The path guard traversed
components repeatedly;107416 `Path.is_junction` calls each reached a further
Windows junction readback. This follows the actual code at
`runtime_paths.py:75-95`: lstat for symlink mode, separate junction check, then
repeat for every parent. `_file_identity` and `_directory_identity` each invoke
that entire guard (`copying.py:57-76`), and workspace traversal invokes it
again for directories and entries (`copying.py:79-106`).

One ordinary `_Build.check` calls `check_profile` then `capacity`. In turn,
profile has before/after namespace checks; capacity has another namespace,
source-before and source-after checks around workspace/free-space observation
(`receipt_corpus.py:274-284,364-398`). The measured2893 source checks came from:
1233 namespace calls,812 direct capacity calls,635 ledger checks,202 complete-
verification calls,9 hashing callbacks and2 run-stage calls. `_HeldRead`'s
function-list readback is real but secondary:3195 fetchmany calls from
`_current`,0.406s cumulative, versus6.904s under ancestor validation.

The full late stages were executed, not omitted to time only the append loop:
`verify_complete`1 call/0.633526s; ledger `finish`1/0.068744s; `close_writer`
2/0.039680s (one real terminal close plus final no-op cleanup); ledger `digest`
1/0.017975s and `close`2/0.000125s. Five actual `inventory_raw` calls occurred
inside the profiled owner. Additional external validation is recorded above.

## Engineering option for Root's decision — not implemented

Investigate a **call-local namespace observation helper**, starting with
duplicate ancestor/path work *within one existing source-check invocation*.
For example, source/main/workspace/owned-directory paths share ancestors, yet
the current helpers independently reconstruct and traverse those chains.
An internal observation could enumerate each distinct required component and
reuse its complete non-following stat data only for the checks belonging to
that same observation. On Windows, any replacement for the separate junction
query must prove identical symlink/junction/reparse rejection and error
semantics; a mode-only or existence-only substitute is unacceptable.

This is **not** permission to remove three of four append checks, pool distinct
source/profile/capacity phases, retain observations across yields, or replace
opaque/data/permission checks with a transaction-generation comparison.
Keep all original externally mutable iterator entry/return, normalization and
decoder, actual append/readback, transaction, precommit/postcommit, writer-close/
reader-open, final source and late-close boundaries. Preserve meaningful
before/after observations around SQLite, ledger I/O, workspace scans and
free-space calls, and all deadline/quota/error/retained-artifact checks.

Even narrowly shared stat readback needs an explicit owner contract for the
uninterrupted observation: exact controlled functions, no reentrant callback/
signal/tracing mutation, no concurrent use of either connection, and genuinely
sealed/private ancestor and file namespaces where foreign rename/link/reparse
changes are excluded throughout that observation. A native closed caller with
verified ownership/permissions, exclusive directory/FD custody and its actual
worker catalogue would have to establish that; a Python object, path string,
current stat or documentation claim does not. Present timing evidence does not
establish this authority. No snapshot can survive a caller yield or distinct
phase without a separately approved lifetime/invalidation contract.

If authorized later, first compare the proposed internal observation against
the exact existing link/junction, replacement, source/connection drift and
error behavior before measuring a byte-bound new complete owner run. This
report proposes no relaxed cap, longer deadline, altered receipt normalization,
less complete verification or assumed speedup.

## Retained artifacts and binding

Paths below are relative to the fresh attempt directory:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| source.sqlite | 61440 | `490b2aaa48fdc5687fc043fdf9bc4fea2631b4d4c7703e8361ae5d9b332f47a9` |
| work/corpus/legacy-copy.sqlite | 266240 | `25c6ae263f91be67d9c27423cf35949871f4aac9ffd962d0e83db7ad19f24142` |
| work/corpus/receipt-additions.bin | 532507 | `9d37e7e657433dfb95062b8be88b09c8240d356e1bc694eb7d8222203efdea4d` |
| corpus.pstats | 58974 | `58f5e8701064bdc2719960fd8a3234d26a12b51b0f127b902472c5ceb0ca658a` |
| profile.txt | 17090 | `3a0571c196aab809d2b1626e5477d5201fb539d6285babece16b16d23f460e03` |
| stats.json | 284135 | `cab1e1f2cc3ddea9ce76883abbb9b7acbeeb83afeb33f484af8ff1ae6d43fd79` |
| summary.json | 4465 | `bef49b64efe1f0c1cd1a8fe665d63e326bb7cbbea2592d6a906d8d0dc5beb172` |

`summary.json.code_sha256` records all20 imported project Python modules plus
the instrument, checked unchanged after execution. Key owner remains
`receipt_corpus.py=fdbebbed9e0b14380d7226660f5f42ec9508ec2b04c727a856bb36747ae660d6`;
inventory=`7e099cd9ed5e5b336519a23cc891e85c2136dda9fa6324c6f433f61bb37e967b`;
copying=`15c031ad5727c69b218d3487bc981ad3126e9e285d254822e94597ade09f0b23`;
runtime_paths=`710b8f8b1bfacf35397aad47d8df2fc9c28f6af60a4888540acfac4030331a8c`.
The recorded Root diagnostic instrument separately hashes to
`4cafda81e617c4184df3fd3c877a79d853a2b137d3aeb71a23d3321fd8de666e`.

M=16777216B, L=1048576B; workspace ceiling35651584B, active-input
ceiling17887232B. Actual owned workspace observation802843B; all attempt files
before summary total1220386 logical bytes, then4465B summary. Instrument and
this report are additional retained QA artifacts, not included in that work
subdirectory observation. Observed initial/final free bytes were
1541194981376/1541193732096, not a physical quota or global minimum guarantee.
No product/test/Git/server/shared-source changes, suite rerun, native execution,
cleanup or additional agent dispatch occurred. Only the allowed profiling
instrument, its new outputs and this diagnosis report were created.
