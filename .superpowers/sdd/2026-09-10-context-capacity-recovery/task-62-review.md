# Task62 independent bounded review

## Spec Compliance

**Spec verdict: compliant at the implementation/static-review gate.** The new Linux retained walker preserves the inventory contract while replacing repeated absolute ancestor opens with held-parent relative traversal. Required native RED/GREEN, native parity/error behavior and actual retained-union timing remain unexecuted acceptance gates, not passes inferred from portable tests.

**Review scope:** BASE `68c1ff89042d26a9c9454a308e3fe65defa8947a` to HEAD `6eb267a294244bcb6375c5045cc5231c1109d611`; only the retained-walker slice, its new focused test module and author report. The complete brief, report, prerequisite Task61 preparation evidence and complete34371-byte diff were read. Diff source was read once in contiguous bounded chunks; a reference-only index supplied current lines. No changed source was reopened separately, no broader code crawl or unrelated review was performed.

**Verified review inputs:** package SHA256 `bf03213f1a924ca0605527de85b5374a8342f9d4e88e4e80fcc35f8bdb27c3be`; report SHA256 `e98bf828a44944f903b1ec14192881bab902087d94e8c3dd3039c96e99a771c1`. Both match dispatch. Root separately verified catalogue SHA `a17c62e6fec58735974f74be59e16dfd2d7ac9061da58239eac35a4f3a202185`, test SHA `d71f669ded5272ef18e3907f7f1d5b628a72e1a35c4aa604d55cfe9a9438a68e` and final XML; those tests were not rerun by this reviewer.

## Strengths and checked requirements

- **Scope/parity:** `tests/native_context_receipt_diagnostic_catalogue.py:268-274,359` adds a platform dispatcher and the Linux implementation, routing other platforms to the previous body under `_retained_root_portable`. The diff adds that function boundary without modifying the old algorithm's body. No old helper, profile, parent/worker, budget, admission, archive pin, resource constant or second-pass code is changed.
- **One held absolute chain:** `:349-356` uses the unchanged reviewed `opened(path, directory=True)` once for the root. Every descendant is opened at `:298-312` by a single child name relative to the still-held parent descriptor, with O_NOFOLLOW/O_NONBLOCK/O_CLOEXEC and O_DIRECTORY for directory children. This removes the named source-level repeated-ancestor work without changing the old general helper.
- **Type and full epoch binding:** `:280-282,298-312` compares the complete existing seven-field identity plus physical allocation, checks the opened type, and verifies both held and no-follow named bindings after successful use. `:349-356` binds the initial root lstat to the held root and final named root. Original outer ancestor/root checks remain in the unchanged entry context.
- **Complete regular bytes:** `:335-345` checks the existing8GiB size bound, reads every file through EOF in bounded1MiB pieces, checks growth and final exact length, and hashes all returned bytes. There is no memoization for hardlink aliases or across observations; each regular path is independently opened/read/emitted. Filesystem atime is not added to the existing identity contract.
- **Inert symlinks and unsupported types:** `:325-336` uses no-follow stat, hashes bounded raw byte readlink results without opening the destination, and rechecks the named epoch before emission. Non-directory/non-symlink entries must be regular; FIFOs/devices/sockets are not silently opened or authorized. An actual type race at open is rejected by the held-type/epoch checks; O_NONBLOCK avoids treating a substituted FIFO as a blocking regular read.
- **Membership and deterministic digest:** `:283-297,313-348` keeps the same closed typed record shape, canonical encoding plus LF, sorted depth-first child order, per-path logical/allocated accounting and counts. It now re-enumerates sorted child names at each directory's completion and compares the directory held epoch/allocation. It does not use cached DirEntry stat data. Initial/final membership and named binding checks refuse detectable substitutions rather than publishing a partial successful result.
- **Bounds:** `:283-297,313-336` preserves entries200000, child count50000, depth32, path2048, file8GiB and aggregate64GiB. All unique path records, including hardlinks, remain individually counted. The held child FD stack follows bounded recursion depth rather than total regular-file count; content reads remain1MiB bounded. Added repeated directory enumeration is explicit checking work, not an unmeasured speed claim.
- **FD ownership/errors:** `:298-312` places held-file type checks, fstat, reads/recursive traversal and final named validation inside a `try/finally` that closes the child FD. The root context owns its absolute chain. Errors propagate, suppressing a successful return; there is no swallowed scan/read/stat/close exception or fallback result. A failing open transfers no returned FD to the child context. This is static control-flow evidence, not native leak-test completion.
- **Independent equivalence/scaling tests:** `tests/test_native_context_receipt_retained_walk.py:25-64` builds an independent path-based canonical oracle and a branching/deep fixture with empty/large/mixed-name files. `:138-174` compares complete canonical results and constrains exact root-entry/relative-descendant open behavior. The native test additionally runs the old implementation and covers hardlinks/inert symlinks; its fallback allows the same test to fail old code on excess absolute opens rather than a missing private symbol.
- **Explicitly modeled vs native evidence:** `:68-134` labels its directory-FD adapter and Windows ctime substitution honestly. `:187-280` exercises read/stat/scandir/close and epoch/membership/type/grow/shrink failure boundaries, with separate actual-Linux `/proc/self/fd` checks. `:285-317` performs actual file/directory/symlink/root replacements on Linux; `:321-337` counts per-alias bytes across fresh calls; `:341-395` exercises bounds and FIFO refusal. Native-only cases are explicitly skipped elsewhere, not enabled by merely faking sys.platform.

## Issues

### Critical

- None identified within this bounded Task62 change.

### Important

- None identified within this bounded Task62 change.

### Deferred / outside scope

- T2 generic transport log caps and M1 prior consumer created_at remain deferred as instructed. Neither was revisited or cleared by this walker review.

## Evidence and cannot-verify items

- **No test repetition or native action:** no tests, VPS/network command, Git operation, source edit, installation, cleanup or subagents were used. Only this report was written. No additional unchanged-code lookup was required: the exact old opened/identity/file-record contract was already examined in the preceding task review, and the diff preserves that helper.
- **Reported final focused run:** `task-62-report.md:119-173` records final session75112, actual child/outer0, `23 passed, 21 skipped in11.23s`, empty stderr, outer wall11.906s and XML SHA `89da0b0cfbd71566930355f95a28d3836eae6ef024d2fc699e1906bbfeda5846`. Root reports fresh44cases/0failures/0errors/21skips with matching source/XML hashes. This is inspected author/controller evidence, not a regenerated reviewer run. No warning noise appears in the reported final output.
- **Native RED/GREEN remains required:** the portable RED demonstrated a missing modeled relative-FD implementation, while the native old-code open-scaling RED was not run. Root must run the compatible scaling/equivalence test against the reviewed old and new catalogues under a separately controlled Linux QA environment; no executed native before/after result exists in this review.
- **Actual Linux semantics remain required:** real dir_fd/openat/O_NOFOLLOW behavior, repeated FD-based directory enumeration, raw symlink target handling, named/held epoch drift, actual root/child replacement and terminal FD counts must be established by the21native cases. The implementation and tests are present, but Windows/model passes cannot prove these kernel facts.
- **Close errors are calibrated:** the test's close fault deliberately releases the descriptor and then raises; it proves propagation and unwinding of remaining owned descriptors, not recovery from an arbitrary OS operation that permanently fails without releasing an FD. The author explicitly documents this limit. No retry-close or unsafe descriptor reuse assumption was added to production.
- **Exact live union and performance remain unknown:** the optimized walker still hashes all historical bytes and checks membership afresh on every observation, including the existing second scan. Native retained-union cardinality/identities/hashes, the actual reduction in ancestor opens/CPU, whether complete preparation fits parent60CPU, and effects of extra membership enumeration have not been measured here. The Task61 prior SIGKILL around CPU60 is retained STOP evidence, not an executed timing baseline for this new code.
- **No automatic retry/authority expansion:** source approval does not authorize an unlabelled rerun, a new namespace, cache token, dropped scan, relaxed60/240/300 or1800/3600 limit, deletion, budget credit/refund or a settled full-C claim. Root owns any separately prepared native QA/measurement, input/instrument pins and terminal readback. Actual diagnostic admission/full-baseline1024, full490000 growth, C/B, Source/D2, restore/deployment and release remain separate open gates.

## Assessment

**Code-quality verdict: Approved at the bounded implementation-review gate.**

**Reasoning:** the change is local, preserves full-byte inventory semantics and bounds, and explicitly owns descriptor lifetime while reducing the repeated absolute-open work identified in the STOP diagnosis. Its focused tests cover parity, operation scaling and refusal paths without claiming that portable execution proves native correctness or performance. Native tests and actual retained-union measurement are still required before accepting the operational repair.
