# Task62: bounded retained-tree traversal, unchanged inventory contract

Approved continuation of C after the one Task61 preparation STOP. Root owns
Git/index, controller documents and all native operations. Implementer owns
only the new retained-walker slice and its focused tests/report. One writer,
then independent scoped spec/quality review, then native measurement. No
change to the user-approved C/B contract and no new product-model work.

## Evidence and objective

Read task-61-native-preparation-evidence.md and the existing reviewed Task61
retained contract. Actual first preparation stopped with SIGKILL near CPU60,
before retained.json existed. Thus no measured last root, complete scan,
actual diagnostic admission or receipt worker. No automatic retry is permitted.

Concrete source-level inefficiency: retained_root invokes old opened() for
every regular file; opened reopens, checks and closes every absolute ancestor
for each one. The old general helper remains pinned and unchanged. This task
may optimize only the NEW retained walker, preserving its exact canonical
inventory/counts/identity/allocation/bytes contract and refusal behavior.

## Owned files / scope

- tests/native_context_receipt_diagnostic_catalogue.py: retained_root and
  tightly local private support only.
- tests/test_native_context_receipt_retained_walk.py: new focused tests.
- task-62-report.md under this controller directory.

Do not change the previous catalogue, process guard, admission, supervisor,
budgets, diagnostic parent/worker, corpus/Source/model owners, seed/profile,
existing test expectations, runtime dependencies, Root instruments or pins.
Do not create children/subagents, touch the VPS or stage/commit/push. Return
writer ownership with actual test exits and hashes for Root review dispatch.

## Required implementation boundary

1. On Linux, hold the protected no-follow absolute ancestor/root chain once
   using the existing reviewed opened(..., directory=True) entry, then traverse
   with bounded held directory FDs. Open each child relative to its held parent
   with O_NOFOLLOW and correct type/nonblocking/CLOEXEC flags. No full absolute
   ancestor reopen per descendant; no following symlinks or silently trusting
   directory entry cached stat data.
2. Bind each entry's actual no-follow stat to its opened FD where applicable;
   compare complete file epochs before/after the full read and named binding
   after the read. Compare directory membership/identity/epoch before and after
   its complete traversal and its named binding while parent FD remains held.
   Original absolute ancestor protection and final root binding still apply.
   Root/child substitution, unlink/rename, truncation/growth, type changes and
   metadata drift must reject. Every FD closes on every error path.
3. Every regular file is still fully SHA256-hashed on every fresh observation,
   including copied files and hardlink aliases. No digest memoization across
   paths, calls or processes; no identity-only substitute for content proof.
   Reusable bounded read buffer on Linux is permitted; same exact full EOF/
   length validation and hashing. Buffer must never become a retained output.
4. Symlinks remain inert: hash bounded raw link-target bytes, never follow;
   recheck their exact named epoch. Every path remains individually counted,
   including conservative allocated-byte double counting of hardlinks.
5. Preserve exact record shape, canonical serialization/order, directory/file/
   symlink counts, metadata sizes, st_blocks allocation, root/aggregate bounds,
   depth32/path2048/file8GiB/total64GiB/entries200000 and child count50000.
   Deterministic output for unchanged native input must match the previous
   implementation byte for byte, not just counts.
6. Preserve portable Windows behavior or explicitly route the unchanged old
   algorithm there. Portable fixture equivalence is not native dir_fd proof.
   Add native-only tests for actual dir_fd/openat/no-follow/error cleanup.
7. No catalogue builder reuse token, cross-pass caching, removal of the second
   scan, timer/limit increase, alternate namespace or admission behavior here.
   This is only the smallest traversal optimization. Runtime success remains
   unknown until measured on the exact native retained union after review.

## Required focused test evidence

RED against current code for actual ancestor-open scaling (instrument call
bound/call path, not a wall-time assertion). A deep, branching tree with regular,
empty/large files, mixed names, hardlinks and inert symlinks has exact old/new
canonical result equality on native Linux. Preserve existing relative ordering
and unsupported-type refusal. Simulate controlled named/FD epoch and directory
replacement, grow/shrink, symlink swap, read/stat/scandir/close errors and show
no leaked descriptors; no false successful result on an error. Native tests may
skip on Windows but must remain explicit for actual Linux execution. Do not
fake sys.platform alone and label it native execution.

Run only focused tests and adjacent cheap retained/catalogue cases initially;
do not rerun Task58 or the full suite. Root will arrange one versioned Linux QA
transport and measurement after review. Record actual commands/exit/counts,
skips/limitations and new code hashes. No capacity or release pass claim.

All existing native artifacts and costs stay retained. The current diagnostic
registry/job remain empty. Failed preparation does not earn a fresh free full-C
1800/3600 lifecycle; Root must keep separate engineering costs explicit.
