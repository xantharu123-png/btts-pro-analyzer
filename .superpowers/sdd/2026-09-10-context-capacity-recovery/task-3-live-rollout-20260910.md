# Capacity repair: real approved execution and rollout evidence

## Scope and exact source freeze

10 September 2026. The user's latest yes explicitly authorizes only the twelve
documented mode corrections0775→0755 with metadata preservation. The earlier
one-time updater-only repair, versioned QA transfer, commit/push and subsequent
ordinary exact-revision app deployment approvals remain separate.

Release candidate: `b39789d54adf8c5c836a50782e276d3810349979`.
Product implementation remains4205db82 and Task2 updater6ba2c68. Full revision
comparison against2dd1116 contains context-reader/capacity/deployment changes,
their tests and documentation, not new model/market/UI changes. A0/P4b3 remain
unintegrated and the protected stagehelper remains1441158c in both worktrees.

Fresh initial checks: saved main, GitHub main and actual VPS2dd1116; repair
branch remote b39789d. Installed old updater74b1c4b1, root:root0755. Internal
and public HTTP200/ok, app/Caddy and seven timers active/enabled. The known
failed tennis service remains explicitly open.

## Approved directory correction

- Exact unchanged local ignored procedure SHA256:
  `8be3d721660d7438a251628ea58c3e61a64f760d96d69fee4d6a82d22ebfe304`.
- Actual durable metadata journal:
  `/var/lib/betboy-directory-mode-repair-fi_69l74/metadata.json`, root:root0600.
- All12 changes succeeded,0775→0755, sameUID997/GID987/inodes; post-stat confirms
  the exact twelve paths. No content, key, DB, executable or service change.
- The normal updater may later normalize actual DB-parent directories to0750;
  no return to0775 and no extra unapproved correction are implied.

## Fresh full live backup diagnostic

Ignored reviewed diagnostic `.pytest_tmp/check_live_task2_backup.py`, SHA256
`926f9f9171dedf80445a34126400de9dc51454d1953f599578cb091e83520e38`.
It uses exact Task2 source6ba2c68, existing deploy lock, real app UID997 producer
and the unchanged pinned stdlib restore/HMAC helper. No app imports as root.

| Evidence | Actual result |
| --- | --- |
| Root-private stage | `/var/lib/betboy-live-backup-j0co13x8` |
| Complete archive | `private-backups/complete.zip` within that stage |
| Database count | 88, complete MANIFEST and isolated restore/HMAC passed |
| Archive bytes | 54,550,967 |
| Archive SHA256 | `21bd2b529cf31451f336d1821ab00578ef8ff54beb377ca3494911edcfac39a4` |
| Measured full-chain CPU / wall | 41.48s /42.60s |
| Peak RSS | 382,684KiB |
| Child status | 0 |
| Sealed current context bytes | 114,929,664 |
| Context SHA256 | `d304c164b44a17cb4e7b90df14f87cbde8dbdd36852d7250911163f967f169b9` |

Production revision and installed updater were rechecked unchanged. This is a
successful fresh full diagnostic, not the actual final installer invocation.
The previous failed stage_w1996l5 and scheduled manifestless archive remain
preserved and are not relabelled as this acceptance evidence.

## Exact source staging for the fresh profile

Only versioned Git archive b39789d was transferred to the approved QA root:
`/tmp/betboy-context-qa.9xr68INa/capacity-release-b39789d.tar.gz`,33,721,850bytes,
SHA256`fd54700b0dfd0f32dff4735f6444e43fa2223e39b3e2c04686441c2f9c078972`.
The existing reviewed stdlib archive-stager was reused with only archive name,
digest and revision changed. New ignored controller copy SHA256
`5f9cda415fb4e7b40a261cd508a44682f38a8ff15aaa1c9a0c63c350a13ab324`.
It rejected links/unsafe members, checked bounded sizes and archive identity,
and created only new root-owned app-unwritable source/fixture files:
`/var/lib/betboy-capacity-code-hy_rb2ux/source`,798 members.

The fresh profile runs the actual b39789d CLI against the above sealed current
context as UID997 under unchanged2GiB-AS/300CPU/600wall/1MiB-output limits.
Its ignored diagnostic is `.pytest_tmp/measure_fresh_b397_capacity.py`, SHA256
`14baebc60b3aa5702fc2e5bd6f3498d5b0d585bf8bfa01dd51b92b977e8dfb8f`.
It additionally compares reported counts to physical rows in that same sealed
copy, requires unchanged input/no companions and retains the two explicit
transport-only limitations. This is not empirical model approval.

## Actual fresh D4 result — RELEASE HOLD

The uninstrumented exact-b397 CLI did not finish on the new current input:
child-9 at300.067CPU /300.163wall seconds, peakRSS362,972KiB, no report. The
sealed SHA and complete file signature remained unchanged; no companions.
This is a failed real profile, not an accepted limited report. No main push,
installed-updater exchange or application deployment was performed.

The independent rollout reviewer explicitly changed the release verdict to
HOLD. The prior code-scope approval does not override actual current-data
capacity. No resource boundary has been raised or suppressed.

Read-only physical inventory of this exact sealed copy found12 artifacts
(10 Tennis originals plus2 tour states),10 snapshots,48,307 contents/receipts,
2 manifests and0 rollbacks. Compared with the earlier104MB copy: only810
additional receipts, but4→10 originals and snapshots, and2→5 causal cutoffs.
The old388MB synthetic-growth fixture retained only4 replay consumers and
shifted added receipts into their future. Its PASS does not cover this shape.

The actual original order requests ATP histories at12:07,16:37,19:07,14:07,
10:00,12:07,14:07,19:07,10:00,16:37UTC. A bounded observational trace first
confirmed29.238CPU seconds for physical receipt validation and62.619CPU
seconds for the first cold history (64.385CPU including storage), encoded
28,432,021bytes. The second history independently costs67.941CPU seconds;
two stored copies occupy56,864,042bytes of the unchanged67,108,864-byte budget.
The third later cutoff starts another full cold history. This is measured
repeated work, not evidence that the underlying odds/models changed.

Ignored inventory script SHA256
`f9509229510668413b7e9aa7421b8ff87f7c5ff503c6ef54d1b267b59e199b14`;
ignored phase trace SHA256
`ba59ed9557bc65ba13b4eb3430403559b461fd26cd8ab01cb633e760087ab88f`.
Both run only as UID997 against the fixed root-sealed QA copy. The first
trace invocation accidentally used system Python and failed immediately on
missing pandas; it was not a product failure or acceptance. The same trace
was then run with the existing app venv as UID997. It preserves wrapped
functions/return values and has275CPU diagnostic stop/300CPU hard limit;
an instrumented run never substitutes for exact uninstrumented acceptance.

A separate read-only analysis is in `task-1-fresh-profile-diagnosis-20260910.md`.
The controller requested approval for a shared fully validated immutable
history basis with bounded historical views, retaining each owning feature
replay, complete data and all budgets. No such implementation has begun.

The trace completed its intentional diagnostic window at275.792wall seconds
(276.411CPU including setup/cleanup),360,448KiB peakRSS, input unchanged. Three
cold histories completed in62.619/67.941/68.279CPU seconds. Subsequent prefix
reuses each stored another full28,432,021-byte copy and caused more evictions.
At the eighth original the19:07 pool had been evicted and started a fourth
cold build; it was interrupted after16.740CPU seconds. End counters:
hits1,covering_hits3,misses7,stores6,evictions4,bytes56,864,042,
peak_bytes67,107,824,pending_bytes0. Original verification alone used239.528CPU
seconds. No snapshot feature call had yet been reached. Do not claim five
completed cold builds or measured timings for the ten snapshot consumers.

The real metadata postcheck also verified journal SHA256
`9309b326007e19b73b847f00efaaa638ae0d209633276dad667c99eded503b88`,
mtime1789072536.019322=20:35:36UTC, and all twelve exact original identities.
Actual app UID997 can write all12 directories; backup UID995 with explicit
app supplementary group cannot write any. Both identities are denied read
access to the root-private complete diagnostic archive. These were read-only
effective-DAC checks, not writes or deletion of live test files.

Final read-only server/remote check around21:01UTC: GitHub main and VPS still
`2dd1116b68f3d94e9c24338c6c9dff9b01799221`; installed updater still the old
`74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`.
App/Caddy and all seven enabled timers remain active, with planned next runs;
internal/public health bothHTTP200/ok. The failed tennis-service state remains
reported. All native QA processes from this turn have completed; no native
model/pytest ran as root and no deployment was started.

## Final full suite and remaining gates — 21:05 UTC

Fresh whole Windows suite at exact
`b39789d54adf8c5c836a50782e276d3810349979` completed successfully in the separate
clean LF QA worktree: **6897 passed,30 skipped,97 subtests passed in1704.03s**,
exit0. Tracked source and index remained unchanged. Unlike the earlier e74
run, this is a complete run of the final b397 tests, not an inferred delta pass.

XML at `context-capacity-final-qa-20260910/.pytest_tmp/final-b39789d-full.xml`,
SHA256`1596c19324d7535c4fd057a362f4aefa3cc5f4fe38b4b7956105bc7b3fef5fbe`.
The suite attributes report7024 entries including97 subtests,0failures,
0errors,30skips and1703.848s. Do not add those subtests again as ordinary tests.
All native diagnostic and local suite processes in this continuation finished.

The green regression suite cannot override the failed real capacity profile.
Resolve the actual capacity issue before main publication, actual installer
backup/D4/exchange, separate normal deployment and final server checks.
Nothing pending is inferred from earlier tests or the user's authorization.
