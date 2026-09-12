# Task 23 — independent preparation accounting review

Date: 2026-09-12. Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.

## Verdict and reviewed identities

No reproducible new Critical/Important finding was found within the explicitly narrow **accounting/claim protocol and portable held-FD I/O** scope. The current module and complete author test file were read and their supplied freeze hashes freshly confirmed before and after review. No product, author-test, Git or server changes were made. Task 26's separate snapshot review is not part of this verdict.

| Reviewed artifact | SHA256 |
| --- | --- |
| `context_preparation_budget.py` | `fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478` |
| `tests/test_context_preparation_budget.py` | `91f820410422a1a8d21b419d901488c6d33264583a367abcb4f5925e7fc5e43b` |
| Independent `.pytest_tmp/test_task23_budget_independent_ccr01.py` | `2e840f71c4992a1ae0b25ae0ef057b155ffd9e68a82a809ae5534755e7ef286d` |
| Final combined XML | `c6754cbbe0e38e7438c6a880f95609f7e40dd4d7b6271bcca1be4ec685a73b72` |

**Final current-bytes run: 91 passed, 3 native-Linux skips, zero failures/errors, 6.39 s** (94 cases including skips; XML suite time 6.304 s). This does **not** close native Linux acquisition/durability, native subtree measurement, global accounting-owner integration, C acceptance or B verification.

## Protocol review

- The 1,800 CPU-second total, 300 CPU-second maximum reservation and original 3,600 elapsed-second deadline are fixed exact integer-nanosecond constants in init/replay. There is no caller-supplied wider limit. Reopening a settled journal retains the original init-derived boot deadline and cumulative settled claims.
- A new ticket is returned only after the complete reservation append, file sync, read-back verification and post-sync clock check. The pending amount is fully charged before a ticket is exposed. Only one pending reservation is admitted.
- A settlement is explicitly a once-only **cumulative CPU claim** against the exact current ticket, with a nondecreasing total and a delta no larger than that reservation. Measurement digests are consumed once across replay. Public values/hashes are not authenticated measurements or refund authority; the future complete-job owner must establish quiescent authentic process-tree cost before calling this API.
- Recovered pending reservations retain their entire outstanding charge and permanently refuse reserve/settlement/stop-as-refund in V1. Successive reopens do not manufacture a fresh usable ticket. A stopped journal stays stopped; stop records do not release unknown CPU charge.
- Boot identity, ordered boot-inclusive samples, realtime ordering/offset continuity and bounded sample width are validated. The original boot deadline is not rebased on reserve, settle, retry or reopen. Post-sync observations are retained within the live handle; durable replay plus the original deadline governs a new handle. Historical `snapshot()` is deliberately not a current execution permission.
- The journal is bounded to 256 records / 4,096 bytes per record / 1 MiB total; exact JSON keys, integer types, canonical bytes, record sequence, previous hash, identity dimensions and event rules are rechecked. Public hashes detect inconsistency but are not authenticated anti-rollback authority.
- Held local FD checks reject nonregular or multiply linked files and device/inode replacement. Expected complete bytes are retained by length/SHA and rechecked before/after append. Short writes loop; no-progress or write/sync failure returns no ticket and fails that handle. Partial tails are not truncated or repaired. The in-process owner set and per-handle nonblocking operation lock prevent the tested duplicate-owner/reentrant overlap.
- Static inspection and an independent AST test confirm stdlib-only imports. Public `create` is explicit O_EXCL creation; `open_existing` has no implicit-create path. There is no reset/truncate/repair/source-root opener or product import in this module. The Windows public entrypoints fail closed instead of selecting the private portable test path.

## Independent real local evidence

The independent probe uses explicit simulated `ClockSample` observations and integer CPU claims, and the private `_FileJournal` / `_attach` seam only to exercise real local file descriptors. It does **not** substitute fake native locks or pretend that private portable construction is native Linux acquisition.

24 independent portable cases passed, covering:

- Six fully charged 300-second reservations/claims across sequential closes/reopens, exact final 1,800-second exhaustion and unchanged first deadline.
- A 125-second settled claim followed by an unknown 300-second reservation: 425 seconds remain booked over four reopens, with every attempted new reserve, recovered settlement or stop-as-refund refused without journal changes.
- Once-only tickets and measurement digests across reopen; stale and reused claims leave the pending generation intact.
- Original-deadline rejection at reserve, settlement and reopen; a clock uncertainty interval crossing the deadline; unreadable, backward, changed-boot and discontinuous realtime observations followed by restored clocks still yield a permanently stopped journal.
- Actual 1-, 17- and 127-byte short writes followed by real fsync and complete replay, and an actual no-progress return that exposes no ticket or erased prior bytes.
- A real `os.dup2` replacement of the held file descriptor rejects before writing the foreign file; both original and foreign bytes remain unchanged. A real extra hardlink rejects the single-link contract. A real pipe FD is rejected as nonregular without reading/blocking.
- A real second descriptor cannot create another in-process owner; ownership is released on close. An actual same-length foreign write is not silently adopted.
- Three actual child-process `os._exit(73)` cases: after a returned reservation, before reservation fsync, and after a real 19-byte partial append plus actual fsync. The first two recover as fully charged unknown pending work; the torn tail cannot reopen and is preserved exactly. Explicit create cannot overwrite any of these retained files.

These process-exit checks are **not power-loss/VM-crash durability experiments**. The before-fsync case observes the actual post-process-exit filesystem bytes; it does not claim those bytes survive a machine power failure. Native measurement, native crash supervision and protected external registry semantics remain separate.

## Runs and skips

All output paths were new and never reused:

| Run | Result | Evidence |
| --- | --- | --- |
| Fresh author suite | 67 passed, 1 Linux skip; 5.06 s | `.pytest_tmp/task23-budget-independent-ccr01-baseline.xml` |
| Independent probes | 24 passed, 2 Linux skips; 1.46 s | `.pytest_tmp/task23-budget-independent-ccr01-probes.xml` |
| Final combined current bytes | 91 passed, 3 Linux skips; 6.39 s | `.pytest_tmp/task23-budget-independent-ccr01-final.xml` |

The three real Linux gates were not run on this Windows host:

1. Author test: native flock, held-directory/file fsync, boot clock and cross-process exclusion roundtrip.
2. Independent native FIFO acquisition test using actual Linux O_NONBLOCK/native owner acquisition.
3. Independent native held-directory entry replacement test, preserving the old journal and rejecting redirection to replacement bytes.

The portable real-pipe and real-FD tests above do not turn these skipped native cases into passes.

The final command used the configured bundled Python, `.venv/Lib/site-packages` in `PYTHONPATH`, and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`:

```powershell
python -m pytest -q tests/test_context_preparation_budget.py .pytest_tmp/test_task23_budget_independent_ccr01.py --basetemp=.pytest_tmp/task23-budget-independent-ccr01-final --junitxml=.pytest_tmp/task23-budget-independent-ccr01-final.xml
```

Use different never-existing output paths when rerunning. No existing artifact was deleted or overwritten.

## Still outside this result

The absence of a protected durable lifecycle registry, trusted native complete-job/subtree meter, DiskSupervisor/global allocation accounting, root-namespace binding and anti-rollback coordination is an explicitly declared integration boundary, not something this hash chain proves. CPU values in the protocol tests are test claims, not measured consumption. A caller-supplied valid-looking identity/digest/dataclass is not authority to launch, release money/resources, refund unknown work, or produce B proof. The module cannot prevent privileged journal/VM rollback or deletion followed by a separately authorized new create.

Next bounded acceptance step is to run the still-skipped cases through the actual Linux native path under the separately authorized job owner and integrate authenticated complete-job accounting without widening these limits. The current review clears only the bounded primitive's tested accounting semantics, not those missing native/whole-system gates.
