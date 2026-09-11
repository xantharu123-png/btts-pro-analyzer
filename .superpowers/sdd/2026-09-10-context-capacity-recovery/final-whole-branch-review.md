# Final whole-branch SPEC / CODE QUALITY integration review

Date: 2026-09-11. Reviewer: `/root/capacity_whole_branch_review`.

## Verdict

**APPROVED for code/spec integration, with one nonblocking Minor test finding.**
Critical: none. Important: none. This is the independent whole-branch integration
review, not another Task9-only review and not a production-release approval.

The pending native growth, final full-suite and fresh-backup gates must still
pass. No model/empirical approval, successful production update, universal
future capacity, or repaired daily Tennis worker is inferred.

## Immutable scope and method

- BASE: `2dd1116b68f3d94e9c24338c6c9dff9b01799221` (actual pre-repair main/VPS).
- Review HEAD: `194155d7b86f0ef6c8f64bd53608f9a9c706aa6b`.
- Product/tests: `1c65adae1e9de85a6d457cf452f21c4d9cbb589e`; the next checkpoint
  changes controller documentation only.
- Package: `review-2dd1116..194155d.diff`, 64 commits, 1,594,867 bytes;
  independently checked SHA256
  `5896f0e34944cd9127cd755f5d1c59332ca515411d423de480dbd18bf6f55f80`.
- Complete changed-path inventory: 96 files. Review used the immutable net
  executable changes, binding recovery plan and amendments, current ledger,
  relevant implementation/design/review/native evidence, unchanged owning
  validators/callers, and integration regression tests. Historical SDD prose
  was treated as dated context, not proof that its earlier candidate still
  passes or that a proposed rollout happened.
- The disappeared superpowers package was not executed or represented as
  available. This review uses the dispatched manual immutable-Git workflow.
  No new subagent, product/test edit, index operation, commit, push, SSH/VPS
  action or full repository test run was performed.

## Actionable finding

### Minor / P3: compare opaque bindings without inventing SQL row order

Location: `tests/test_context_dataset.py:291-296` in the reviewed HEAD.

The expected `SELECT payload FROM context_contents` and the production
`SELECT content_digest,payload FROM context_contents` have no `ORDER BY`, but
the assertion compares their results as ordered lists. A planner/index change
can therefore fail the test despite exact correct named bindings. This is the
deferred Task5 finding, independently reproduced rather than rubber-stamped.

Real SQLite reproduction, with no repository file changes: create
`context_contents(content_digest TEXT PRIMARY KEY,payload BLOB NOT NULL)`,
insert `('a', b'z'), ('b', b'a')`, and create an index on `payload`. The first
query returns `[b'a', b'z']` using the covering index; the second returns
`[b'z', b'a']` using the table scan. `EXPLAIN QUERY PLAN` confirms those two
plans. The assertion's order premise is false even though both exact BLOB
multisets are identical.

Practical fix: separately assert that every captured mapping has exactly the
`opaque` key, then compare `Counter(binding['opaque'] ...)` with
`Counter(expected)`, retaining multiplicity. Add a real covering-index control
that demonstrates RED with the old ordered assertion. Do not add sorting to
the production query or change the physical/D2 contract to satisfy this test.

Importance: test robustness only; the current immutable focused test passes,
and no incorrect data acceptance, opened final label, changed mathematical
result or deployment defect follows. A narrowly reviewed test-only follow-up
does not require reopening the frozen product repair. This report does not
claim that follow-up has already been implemented or verified.

## Cross-task integration assessment

| Boundary | Independently inspected conclusion |
| --- | --- |
| Memory reader -> sealed reader -> CLI | Default remains explicit bounded 64-MiB in-memory input, with no size/error-driven fallback. Only explicit `sealed_file` selects the Linux root-owned, single-link, app-unwritable ancestor/file contract. Held FD/path identity, complete streamed SHA, DELETE header and no companions remain checked across SQLite's separate immutable/read-only open. The 1-GiB input and 256-MiB complete-history budgets do not replace AS/CPU/runtime admission. |
| Tracked transaction -> lazy inventory -> rollback | Generation tracking covers normal connection/cursor calls, scripts, commit/rollback, context exit, property setters and deserialize/close. Completed receipt proof binds total changes and both main/temp schemas. Complete content, every unfiltered receipt and orphan checks precede proof publication; failure revokes it. The unchanged rollback writer consumes returned manifest/chain/table data while its transaction is held and constructs a new verification after its authorized writes; it does not reuse stale receipt authority. |
| D2 dataset / protected finals -> physical/source traversal | The dataset change is only the repeated named SQL binding. Fixed outer projection and physical byte/index checks stay intact; no final body decoder is introduced. The lazy D2 subset retains identities rather than decoded inventories. Protected receipts remain opaque even at unrelated cutoffs, while future/unreferenced/other-tour ordinary corruption still receives complete physical checking. |
| Physical co-owner -> source seal -> cache authority | Exact same-connection/generation artifact mapping and persisted publication clocks own planning. The real unchanged physical receipt decoder immediately precedes the shared complete source tail, before exposure. Both-tour union eligibility is checked before own-tour retention. Domain cancellation clears optional work and returns to actual cold rejection; physical/resource/lifecycle failures cannot become cache misses. The independent fresh-decoded full cold seal remains separate, and only the completed owning operation binds completeness to exact entry serials. |
| Encoded pool -> original projection -> snapshots | One 64-MiB retained/pending pool owns both tours plus charged planning/query/completeness metadata, with 32 aggregate slots and at most 30 optional queries. Direct stores/physical stamps/caller cutoffs do not grant aggregate completeness. Queries include every target row and full-prefix byte admission before native absence/ambiguity. Missing/evicted/unowned entries cold-fallback; replacement loses authority. Original native/state/code/predictor checks remain, and every snapshot still receives its complete fresh real tuple, exact refs, actual feature call and actual transport replay. Current canonical bytes/type checks guard witness reuse; model results are not cached. |
| Online backup -> fresh quiesced backup -> normal updater | Separate archive variables, work paths, phase receipts and seals preserve the recovery checkpoint. Complete discovery includes Unicode casefold, companions and other filesystems; traversal failure is fatal. Resource admission sums same-device reservations. Producer completion, retained-FD risk, new root-owned archive copy, full restore/HMAC helper, bounded extraction and complete D4 all precede downtime on the online route. Quiesced verification is repeated before payload application, with strict no-writer/live-signature checks. Only genuinely keyless AND proved contextless legacy retains its explicit older route. |
| Installer -> installed updater -> application release | The installer uses the fixed trusted HTTPS remote, exact main tip/blob, existing deployment lock, old updater/production/authentication pins and fresh full backup/restore/measured D4 evidence. Root executes reviewed stdlib byte/transport operations, while app/model code runs as betboy. Durable old copy/journal, fsync barriers and exact recognized inode/hash states constrain recovery; unknown replacements are preserved. Its sole permanent executable exchange is the updater. Application update remains a separate ordinary exact-commit operation with its existing failure rollback and post-health checks. |

Source/validation equivalence was assessed against the real unchanged physical
decoder, workload validator, canonical-byte contract, native original predicate
and full feature/transport callers; prior review verdicts were not substituted
for code inspection. SQL traversal order inside the physical receipt phase is
explicitly amended, not misrepresented as preservation of an unspecified first
malformed-row ordering. Default reader admission and opaque-final behavior are
covered by actual integrated runtime tests, not just new cache unit tests.

The installer deliberately carries copied trusted preflight seams instead of
sourcing updater main. The executed parity regression checks those complete
function bodies against the frozen updater and checks its exact digest.

## Independent execution evidence

All commands used the quality executable
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`
with `-B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning`.

1. `tests/test_context_update_hook.py tests/test_context_updater_repair.py
   tests/test_context_dataset.py`
   with `--basetemp=.pytest_tmp/whole-branch-independent-deploy-20260911`:
   **482 passed, 1 skipped, 267.56s**, exit 0. The skipped actual flock test
   requires Linux; local simulated-principal/ordering/transaction tests do not
   claim native DAC or a real production exchange.
2. `tests/test_context_runtime_capacity.py tests/test_context_runtime_backup.py
   tests/test_context_runtime_coordinated_tennis.py`
   with `--basetemp=.pytest_tmp/whole-branch-independent-runtime-20260911`:
   **302 passed, 12 skipped, 128.92s**, exit 0. Platform-sensitive real Linux
   DAC/POSIX/symlink controls remain separate native evidence, not local passes.
3. Independent in-memory SQLite covering-index reproduction above: confirmed
   both differing orders and their real query plans; no fixture/product edit.
4. Working product/test/deploy paths remained byte-identical to review HEAD.
   Explicit BASE-to-HEAD checks found no changes to physical decoder, generic
   contracts, live CODE_PATHS, v3/v2 model code, evaluator, workload owner,
   transport, model-artifact/rollback implementation, `tennis/`, or protected
   staging/backup helper sources.
5. Exact working-byte SHA256 checks matched:
   stage helper `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`;
   installer `bdc9c700e646e610a07b22077d4b3d00a592b88e4f241a63f5e011642f7c631c`;
   updater `4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`.
6. Executable `.py`/`.sh` BASE-to-HEAD `git diff --check` passed. The unrestricted
   check reports six Markdown hard-break lines in archived A0/P4b3 reviews and
   two historical brief EOF blanks. Those are recorded, not falsely called a
   globally clean diff, and do not warrant changing frozen archival evidence.

Total new independent pytest evidence: **784 passed, 13 skipped, no failures**.
These are not the author's 1109 cases, prior Task9 reviewer counts, root's
whole-suite run, or native production/data measurements relabeled as reruns.

## Operational disposition at handoff

Controller-reported exact `1c65ada` actual-current verification passed with
99,521 receipts / 28 artifacts / 26 snapshots / 2 manifests / 0 rollbacks,
262.690 CPU / 262.838 wall seconds and 486,420 KiB peak RSS. Controller also
reported G1 PASS: 95,406 receipts / 13 artifacts / 11 snapshots, 149.837 CPU /
149.913 wall seconds, 473,360 KiB RSS. Both retain the full unchanged
transport-only report, the existing D1/D3 limitations, empirical false,
unchanged input full identity/SHA, and no companions. These native runs were
not executed by this reviewer.

G2/G3, retained historical-largest acceptance, final exact-LF whole-repository
suite and fresh complete runtime backup/actual restore/HMAC remain controller
gates at this review handoff. Later evidence must name its exact source/input;
older passes cannot certify changed data. Native UID997/AS2GiB/CPU300/wall600/
output1MiB and measured CPU/wall below300/RSS below1GiB remain unchanged.

After those gates, the approved normal main publication, updater-only exchange
and separate exact application deployment still require actual execution and
post-state verification. Preserve full journals/backups and fail-closed
recovery. Confirm server revision, updater/helper pins, complete historical
marker, app/Caddy, seven timers and internal/public health independently.
The separately recorded Tennis refresh HTTPError/scan timeout is not repaired
merely because D4 passes. Cricket, A0/P4b3 and broader five-sport empirical
work remain outside this repair.

Final code/spec status: **APPROVED WITH ONE NONBLOCKING MINOR**.
