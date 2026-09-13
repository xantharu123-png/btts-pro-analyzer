# Task63 independent scoped review

## Spec Compliance

**Spec verdict: compliant at the implementation-review gate.** The change implements the explicitly approved process-local soft-NOFILE reservation, shared held input/ancestor ownership, fresh FD-based content sampling and ordered unwind/restoration. Required native descriptor/limit tests remain unexecuted gates, not passes inferred from Windows models.

**Review identity:** BASE `4e47314f06a68cbf2e3a3e30dd2e39d10bce4e3d`, HEAD `bb54ec58eadcab0e9c0ae065aa258cb7a8f337d6`.

- Actual complete package SHA256: `df1c76bb35661a5335a03a36fb19cebdad4bb905a69b78764ad7d8700c6827c2`.
- Actual report SHA256: `88408bfcf5efb641085ef4e163ef6f7e9538a3e2b142909e3e43095e58c6196f`.
- Both match the dispatch. The complete brief/report and full three-file diff were read in bounded contiguous chunks, once. A reference-only index supplied current line numbers. No changed source was reopened separately.

## Strengths and checked requirements

- **Exact reservation arithmetic:** `tests/native_context_receipt_diagnostic_catalogue.py:168-181` rejects malformed/bool/duplicate/high FD observations, derives B from the maximum observed descriptor number plus1, requires B<=128, F+U<=30000, original soft<=32768, existing hard>=required, and required=B+F+U+128<=32768. Desired soft is max(original soft,required); no existing hard limit is raised. Public input-count/depth checks remain before acquisition at `:321-330`.
- **Before bulk ownership:** `:192-212` observes actual `/proc/self/fd` entries with canonical numeric validation, computes the detached observation, changes only the soft component of the exact original tuple and immediately checks readback. Refusal restores/checks the original tuple without returning a partial binding. No admission, copying, worker launch or root product import is introduced.
- **Live process-bound owner:** `:190-225` retains private process identity and limit state. Samples require the actual owner type/PID/live limit state; returned `descriptors` is only a detached dict at `:395-399`. There is no JSON/control decoder that reconstructs ownership from this observation. The portable route explicitly uses `descriptors=null` and does not pretend to validate Linux limits.
- **Complete shared ancestor table:** `:227-259` opens the absolute root and unique ancestors parent-first, then every exact file relative to its held parent, with no-follow/CLOEXEC/nonblocking flags and directory type flags. Each successful open is registered as owned before fstat/checking. Named bindings use held parent FDs instead of reopening mutable absolute paths; full existing seven-field epochs, types/links and allocation agree with each opened FD.
- **Whole-set membership and fresh bytes:** `:343-353` checks the complete bound file list, plan paths and held directory list. `:363-381` freshly seeks each held regular FD to zero and hashes bounded reads through EOF on every sample; exact length, named/held epoch and allocation checks remain. There is no early closing, batching, cached file digest or per-sample pathname reopening. `:392-403` preserves actual logical/allocated metadata and4GiB union checks while adding only the descriptor observation.
- **Limit drift and complete unwind:** `:214-225,261-310` checks PID and actual limits; validates all named/held nodes while every parent FD is still present; closes nodes in reverse order; then restores the original tuple only after release is established. Hard-limit drift is not repaired by altering hard. Validation/close/restoration errors remain fatal, and uncertain release retains the larger soft reservation instead of lowering it beneath potentially live ownership.
- **Narrow close-error handling:** `:277-308` never retries an FD shown closed by EBADF. A single retry is limited to a still-live matching owned device/inode without a new FD allocation by this isolated unwind; the original close error remains fatal even if the retry releases it. Persistent/uncertain close failure is explicitly not claimed recoverable. The review treats this under the documented isolated single-threaded process contract, not as a general concurrent FD manager.
- **Original lifetime preserved:** `_held_active_linux` at `:313-319` keeps the owner under the caller's existing ExitStack, including failure during open_all or later caller exceptions. It does not return early-close tokens or serialize authority. The unchanged parent still carries the sample into plan.json and the report digest; no parent/worker/helper/prefix changes appear in this diff.
- **Focused model and actual-main adjacency:** `tests/test_native_context_active_descriptors.py:31-54,139-235` covers exact arithmetic, portable labeling, complete lifetime/fresh hashes, reserve-before-bulk refusal, open/stat/read/close/preclose/restore/limit drift, file/directory/allocation/caller failures and public count/depth refusal. The model explicitly substitutes directory descriptors and Windows ctime semantics; its restoration check requires all owned nodes already released. Reported adjacent active-input/main-order cases retain those existing integration regressions without repeating a broader suite.
- **Concrete native testability:** `:240-363` provides actual Linux shared-open counting and fresh isolated1100-file subprocess cases with initial soft1024. The old loops must actually reach EMFILE; the new route must hold every file/unique ancestor, repeatedly hash without os.open, preserve hard and restore after complete close with no FD leak. The closure case uses the pinned unchanged supervisor child function up to its actual descriptor-close boundary, observes inherited bounded NOFILE and terminal output, then exits before UID-drop/guard work. It is accurately not a guard/SIGSTOP/receipt acceptance test.
- **Native parity/refusal coverage:** `:368-454` uses real Linux file descriptors/full epochs plus an explicitly modeled limit provider to compare the complete previous sample (apart from descriptors), reject hardlinks/symlinks/edits/replacements and injected I/O/limit/restore failures, and check `/proc/self/fd` equality. It requires ordinary-user fixtures, not root pytest or a live input scan.

## Issues

### Critical

- None identified in this scoped Task63 implementation.

### Important

- None identified in this scoped Task63 implementation.

### Deferred / separate

- T2 generic SSH log caps and M1 prior consumer created_at remain explicitly open and were not re-reviewed.
- The historical FIFO-v2 exception remains a separate unimplemented planning decision. Task63 does not modify retained traversal or broaden active/code/corpus special-file admission.

## Focused unchanged-code integration check

- **Named risk:** the unchanged parent's success/report ordering might hide a descriptor-release or soft-limit-restoration failure.
- **One focused check:** `tests/native_context_receipt_diagnostic.py:472-499` confirms it writes only diagnostic/external-observation-required report data, then returns through an unconditional `held.close()` in the outer finally. A new owner-finalizer error therefore propagates and prevents a successful outer return even if report.json was already written. No parent source change is needed for this Task63 integration. Root must continue to judge actual terminal exit and cleanup evidence, not an earlier report artifact alone.
- No other unchanged-code lookup or broader integration crawl was needed. The previously inspected old helper/child-close contracts remain the context for the scoped diff.

## Evidence and cannot-verify items

- **No execution repetition:** no tests, native subprocess, SSH/VPS/network command, Git operation, installation, cleanup or subagent was performed. Only this review report was written.
- **Reported final evidence:** `task-63-report.md:141-185` records actual chunk075728 child/outer0, `27 passed,16 skipped,45 deselected in1.11s`, empty stderr and outer wall1.563s. XML SHA256 `65f12e24226368d292283dab5fa7ed94d385d18c7fd6bb19ee708ca51197f76c`; Root separately reports fresh43cases/0errors/0failures/16skips and unchanged catalogue/test hashes. Source hashes are `69a7300536b81d78c38fd6a7d4701f451b1d1468f546ba892908896311dc7f7b` and `aeb378e3bf9bb79fdb8793ba382780724a7cc116c9eb682bb67c67c2cac6e69c`. This is inspected author/controller evidence, not a reviewer rerun. No warning noise appears in the reported final output.
- **Native execution remains required:** actual old-loop EMFILE/no-leak, new1100-file reservation/restoration, real baseline-FD observation, Linux dir_fd/O_NOFOLLOW/full epochs and failure cleanup must still be run under Root-controlled isolated ordinary-UID QA. Windows model passes and explicit native skips do not establish those facts. The native in-process test may deliberately skip original soft>32768; controlled fresh1024 subprocess cases remain the required independent success coverage.
- **Inherited child semantics remain required:** the closure test is present and statically targets the actual unchanged child-close code, but has not executed here. Even when run it proves only inherited NOFILE and that FD-closing boundary, not capability drop, seccomp, SIGSTOP/readback, full receipt work or terminal custody of the production diagnostic. Those remain their own native gates.
- **Actual full-input scale/availability remains unknown:** planning F4546/U468 and5146desired soft are metadata-derived, not fresh actual admission evidence. The full native input list, baseline B, available existing hard, every held identity/hash/allocation, actual system descriptor availability and runtime cost must be observed. EMFILE/ENFILE/resource refusal must stop; no dropped input or hard-limit increase is authorized.
- **Cleanup acceptance:** a persistent close or restoration failure remains external failure, potentially leaving the larger soft reservation in the still-live isolated coordinator. No success may be inferred from a report written before `held.close()`. No general guarantee of recovery from arbitrary kernel failure, external process death or concurrent FD reuse is made.
- **Broader gates unchanged:** CPU60/240/300, AS2GiB, all space/cap/deadline policies, original1800/3600 proof, completed Task62 walker code and all helper/prefix bytes remain unchanged. Full retained/control preparation, actual admitted baseline1024 execution, full490000 growth, C/B, Source/D2, restore/deployment and release are not established by this approval. Root owns subsequent approved pin/instrument updates and native runs; no implicit retry or new free lifecycle follows.

## Assessment

**Code-quality verdict: Approved at the scoped implementation-review gate.**

**Reasoning:** the change addresses the demonstrated descriptor-table bottleneck without dropping any held input or increasing the hard limit. Ownership, fresh sampling and restoration are explicitly tied to the original lifecycle and integrate with the unchanged parent's error propagation. Native tests and actual full-input resource measurements remain required before operational acceptance.
