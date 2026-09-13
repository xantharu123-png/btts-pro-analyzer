# Task62 actual native RED/GREEN and independent readback

13 September 2026. Exact new source6eb267a294244bcb6375c5045cc5231c1109d611;
old source68c1ff89042d26a9c9454a308e3fe65defa8947a. This closes the selected
synthetic Linux walker tests only. No real retained-union timing, receipt
diagnostic, new admission, C/B capacity, restore or application release.

## Reviewed instrument and authority

Task62 implementation review892d53d942a5cd90aef328f6376e9fdce8586541d2a1b476ac60ad3606953998:
spec compliant / quality approved, no Critical/Important. Root read it fully.
The separate unit transport review found I1, missing outer wall deadline.
Root fixed only the remote-command wrapper and two comments: external GNU
timeout210s, TERM then KILL after5s, outside Python and under GNU time; no
foreground/preserve-status/retry. Native GNU9.4 availability/UID1000/fresh
target/interpreter preflightccfa3f exit0 and its actual help were read. Official
[GNU timeout documentation](https://www.gnu.org/software/coreutils/manual/html_node/timeout-invocation.html)
was also consulted; an initial fetch timed out, subsequent primary-source
search supplied the documented behavior. These are not substitutes for exit
and post-exit observation.

I1 scoped fix revieweed754246874c1cfd9470ad04dda5a89b2fd75990f656759959ed9d39063f59b:
approved, no new Critical/Important. Root read all of it and rehashed both
instrument files before execution:

- Entry3f290ec20e4a14c613e3866e0ae9ad92ac0dd70cc77599f66eb001a99f55c00e.
- Runner82376c096693bae729289e932d3a4b3f89ca3becd6983d558ab57bbcb97d65fd.
- Held stdin225215 bytes,
  0f7b6d5797ee8625df993a2ce7c5167f7d30507ec92134f35b2d678636236ddd.

CPU60/AS2GiB/file64MiB/core0 are per-process unit limits; each pytest call has
timeout90. These are not an aggregate60CPU or durable full-C lifecycle claim.
External controller group timeout covers setup, both tests and output. Generic
SSH log cap issue T2 remains deferred. No successful exit alone proves native
process disappearance; the separate check below supplies the observation.

## Actual execution

One fixed run f5caa6, session75927, terminalab5d1d. Ordinary UID/GID1000,
no sudo, no live database or production import. Remote result observed
2026-09-13T13:14:26Z. Actual SSH and outer tool exit0; external GNU time
`exit=0 wall=22.42 user=21.99 sys=0.24 rss_kib=49700`.
Controller CPU0.072824389s, measured children CPU22.151766s.

- RED uses the identical new test/helper with only old catalogue8ebd29f.
  Actual child1, one test/one failure/zero errors/skips in0.16s. Failure is
  exactly test_native_ancestor_open_scaling_and_complete_equivalence line173,
  the absolute-root-open assertion `assert 6 == 1`, not import/collection error.
- GREEN uses the reviewed new catalogue a17c62e and all43 new-module cases:
  **43 passed, zero skipped/failed/errors in21.41s**, actual child0, empty
  stderr. This includes actual Linux relative-FD/no-follow, replacement,
  alias full-read and descriptor-cleanup cases. The separate adjacent test in
  the44-case Windows run was deliberately not added to this minimal package.

No large retained scan was executed. No data corpus or diagnostic registry
was opened. No full-profile/source/empirical model completion follows.

## Exact outputs and separate post-exit readback

All files retained under fixed private
`/tmp/betboy-context-retained-task62-6eb267a-01`.
Independent read-only SSH816095 exit0 at13:15:50UTC confirmed root
ubuntu:ubuntu0700/inode1915, occupied60178432 bytes, and no UID1000 Python,
pytest, timeout or time process listed. No deletion or cleanup occurred.

| Retained file | SHA256 |
| --- | --- |
| new-source.tar,112640B | 817d2ed8a7f529881537d6007c136b829267c6452182cbc923c91a465ce04e6d |
| previous-source.tar,51200B | 69ee6d43caa2f1d95ed5af5ced9d3f4aeda79023c74bf27447f8baca75a6d1a0 |
| result.json | 936211163214324b35315af2822fc0a2883b84bd0aa0749f7ca7084b4e4e735d |
| red/result.xml,947B | feafb18d79425d95f95ad45aa503c97ad5542f1ea480e9e91c891e0063bae6e1 |
| green/result.xml,7191B | 4013c6fc5d97e8ff0b0262dcbf61a3ba3d92b13c08e1c0a1d2deff57675eb9e2 |
| green/tests/native_context_receipt_diagnostic_catalogue.py | a17c62e6fec58735974f74be59e16dfd2d7ac9061da58239eac35a4f3a202185 |
| green/tests/test_native_context_receipt_retained_walk.py | d71f669ded5272ef18e3907f7f1d5b628a72e1a35c4aa604d55cfe9a9438a68e |
| green/tests/native_context_chain_catalogue.py | 48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935 |
| red/tests/native_context_receipt_diagnostic_catalogue.py | 8ebd29f82bd8c92a8601adf8a339f9eb27ddbdf7dcb02bcc0f61d56ea03012e8 |

Local `.pytest_tmp/task62-native-unit-6eb267a-01.stdout.jsonl`:4058 bytes,
f9589f7210ffc9272dae33f811a54cbc3eeb102e20eec82c9cc39681eeef2854.
Local matching stderr.log:64 bytes,
d16746bb53bd69ba2675bc8f7f121bdd37e3f842547e60dd0d7bc8604546f15d.
Root retains the actual per-phase XML/stdout/stderr hashes in those logs and
the server result. Post-exit source/archive/XML hashes match the controller's
held pins/results. No old main/VPS code was deployed by this unit execution.

## Remaining start blocker

Before real data execution, Root separately measured NOFILE soft1024/hard1048576
in the exact intended root environment (967751 exit0). The current active-input
binding needs at least4546 file FDs, and reopens duplicate ancestor chains.
Metadata-derived arithmetic299047 gives5014 shared vs54876 old-chain FDs.
Task63 specifies a bounded shared held-input/soft-limit reservation, preserving
all original identities and lifetimes. This is a distinct pre-admission defect;
the native unit pass above neither fixes it nor consumes a300CPU admission.
