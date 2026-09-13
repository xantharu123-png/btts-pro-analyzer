# Task63: explicit bounded descriptor reservation and shared held input ancestors

Continuation of approved C, not a different product or data contract. Root owns
Git/index, evidence/instruments and native execution. One implementer, then
independent review. Task62 code6eb267a is frozen and independently approved;
its actual native old-code RED/new43-case GREEN completed successfully. Do
not edit its retained walker or repeat those tests as Task63 acceptance.

## Actual failure established before an expensive run

Read-only native967751 exit0 in the exact root env-i Python environment:
UID0, RLIMIT_NOFILE soft1024/hard1048576, four entries observed in /proc/self/fd
(including the observation descriptor). Current hold_active_inputs holds one
complete absolute ancestor chain for each input and each unique ancestor.
4540 dependency files plus controls/baseline/TZ require4546 file FDs alone.
This cannot fit1024 and fails before admission/copies/fork.

Independent local arithmetic299047 exit0 from preserved Task58 dependency
metadata SHA13007f35071d4bc2653969059297e8c2a29b229f3cfa0ae6c95d8d90ec3dd857
plus the exact planned Task61 control paths: F4546, U468 unique ancestors,
shared retained demand5014 versus54876 complete-chain descriptors. This is
metadata-derived planning evidence, not a fresh native input inventory.

## Root's explicit process-local FD ruling

The existing C/B CPU, RAM, file/input/output/space, deadline and admission
contracts are unchanged. NOFILE was an inherited host soft limit, not a
specified smaller data-acceptance budget. This task explicitly reserves a
bounded descriptor table for this isolated QA process only; no systemd,
shell-profile, PAM, global server or application limit change.

- Derive F and U from the exact complete validated input path list; retain
  existing F+U<=30000 and path-depth limits. Every file and unique ancestor
  stays held for the entire original lifecycle. No batching/early close.
- Before opening the input mass, observe actual current FD numbers using a
  bounded native observation. B is max observed number+1 (not merely count),
  allowing the temporary observation FD conservatively. Require B<=128.
- Reserve128 additional working descriptors beyond B+F+U for temporary hashing
  chains, admission, traversal, pipes/selector/pidfd and error output. Require
  required=B+F+U+128 <=32768, original soft<=32768 and existing hard>=required.
- Desired soft=max(original soft, required). Only this process's soft limit
  may change, never hard. Verify exact immediate readback; refusal or any drift
  stops before opening the input mass and before admission/copy/fork. No silent
  fallback to fewer inputs or temporarily closed identities.
- The unchanged child path inherits that bounded soft value and unchanged
  hard limit. This is explicitly a parent-and-child inherited reservation,
  NOT a false parent-only claim. The existing helper still closes inherited
  descriptors before worker execution. CPU60/240/300, AS2GiB and all other
  guard limits stay unchanged. Do not change the reviewed prefix or helpers.
- Record the actual original/desired/hard, B, F, U, required/ceiling/reserve in
  a bounded runtime observation associated with the held binding. Check its
  unchanged actual NOFILE values at samples; include it in the retained active
  input observation written to plan.json/report identity. It is observation,
  not serialized authority to reconstruct an owner.
- Close all newly owned file/directory FDs on success and every error; restore
  the original soft/hard tuple only after that ownership has fully unwound.
  Never swallow a restoration failure or restore soft while still relying on
  the larger table. Any such failure invalidates external success.

This is the only newly specified engineering resource reservation. The old
hard ceiling is not increased; the live App and all seven timers are untouched.

## Implementation scope

Own only:

1. tests/native_context_receipt_diagnostic_catalogue.py: held-active-input
   binding/sampling and tightly local private descriptor support. No Task62
   retained walker, manifest/profile format, allocation caps or journal changes.
2. tests/test_native_context_active_descriptors.py: focused new tests.
3. task-63-report.md in this directory.

The parent currently persists sample_active_inputs in plan.json and hashes it
in the final report; prefer that existing path rather than a new public result
schema. Do not modify parent/worker/helper files without first reporting a
concrete unavoidable interface conflict to Root. All old source/owner pins
remain unchanged. No root product import, subprocess, Git, VPS, new native
attempt, subagent, credential, migration or deployment by the implementer.

## Held input semantics which must remain complete

On Linux open the absolute root and every unique ancestor once, then each
file relative to its already held parent with O_NOFOLLOW/CLOEXEC, correct type
checks and nonblocking regular open. Bind actual named and FD identities before
use, never cached DirEntry metadata. Preserve full actual content hashes,
logical/st_blocks allocation checks, input metadata accounting, complete
seven-field file/directory epochs and all named ancestor bindings at samples
and final unwind. Maintain callback/FD ownership until original held.close().
No proof reuse, hidden FD reopening through mutable absolute ancestors, early
closing, source-hash cache, altered rejection contract or dropped file.

Reuse the held file FD for fresh complete hashing where coherent: seek it to
start, stream bounded bytes, check length plus before/after named/held epochs
and allocation; the output must remain equivalent to previous complete sample
except the explicitly added descriptor observation. Subsequent fresh samples
must still read/hash every input. No file content or directory entry may be
omitted for speed. Keep portable Windows semantics explicit; it does not
pretend to perform Linux resource/openat validation.

## Focused test and review requirements

- Prove the old multi-chain descriptor scaling failure and new single unique
  ancestor/file ownership with actual Linux tests; no wall-time-only test.
- Fresh subprocess native fixture with initial soft1024 and >1024 actual
  files: exact admitted whole set, every file held, bounded desired soft,
  unchanged hard, restoration after complete close, no FD leak. Root will
  execute native cases separately; local skips are not acceptance.
- Fail before bulk open/admission on insufficient hard, too many paths, high
  baseline FD number, invalid observation, denied setrlimit, bad readback or
  changed limits. No partial binding returned as successful.
- Compare complete hashes/physical metadata with old sampler on a small
  unchanged fixture; same-size edits, aliases/symlinks, file/directory/ancestor
  replacement, allocation drift, read/stat/open/close/restore faults refuse.
- Samples and complete unwind retain and check named/FD identity, even after
  caller exceptions; every created descriptor has explicit ownership cleanup.
- Demonstrate inherited bounded NOFILE without leaking input FDs through the
  existing child closure semantics; preserve all helper/prefix bytes. If a
  native-only test needs Root control, mark it explicitly and report it.

Run focused new and cheap adjacent active-input tests, not Task58, Task62 full
suite, full repository, real retained scan or baseline workload. Record exact
commands, actual terminal exits, skips, hashes and returned writer ownership.
No capacity/B/restore/release pass follows from a local implementation.
