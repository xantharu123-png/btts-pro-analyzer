# Approved exact QA retirement for release reserve

Scope: the user's renewed “alles” after the exact eight-target request and reserve explanation approves the eight named old QA/recovery components, protected local export, full restoration verification and only then their removal. No other path is authorized. This is operational cleanup, not application/model work. Root performs all remote execution after review.

## Global Constraints

- Current app/test source is frozen during the final whole suite. Only new helper/evidence files under `output/playwright/` and this plan/ledger may change.
- Preserve production databases, regular backups, the installed updater, maintenance runner/state, evidence and journals outside the exact target subtrees.
- Local recovery destination: `C:/Projekt/BetBoy/.private-vps-backups/20260918-qa-retirement`; access only the user, Administrators and SYSTEM. No public Git/archive/log payload leakage.
- Recheck all targets for inactivity, no mounts, no path aliases, no external hardlinks. Hold existing deployment lock while preparing/removing. Default is read-only; source deletion is a separate explicitly invoked phase only after full local integrity/readability/durable-flush/ACL proof and remote restore proof.
- The eight targets may no longer provide enough reserve. Never lower the updater reserve, delete another path, or claim deployment until freshly verified.

### Task 1: Prepare exact-path archive/removal helpers and reviewable evidence

Use the existing helpers `archive-approved-release-copies-20260918.py`, `remove-approved-release-copies-20260918.py` and fully pinned `archive-approved-context-qa-20260915.py` only as precedents; never execute their old target lists. Implement two separate new helpers under `output/playwright/`, preserve pinned-base validation and exact inventory/hash/metadata/hardlink/restore semantics. All bytes must be in one self-contained archive, without dependence on regular backup retention. No duplicate-specific assumptions from the old three-target helper apply.

Exact targets:

1. `/var/lib/betboy-context-qa-v2-job-02`
2. `/var/lib/betboy-context-chain-task58-588843d-01`
3. `/var/lib/betboy-native-probe-wu61odle`
4. `/tmp/betboy-context-dac-5zxtb2ij`
5. `/var/lib/betboy-context-verifier/memory-qa-so2swnkh`
6. `/var/lib/betboy-context-verifier/memory-maintenance-8jmzb2v5/backup`
7. `/var/lib/betboy-context-verifier/memory-maintenance-8jmzb2v5/code`
8. `/var/lib/betboy-updater-repair/backups`

Prepare uses a new root-private `/var/lib/betboy-qa-retirement-20260918-*` recovery directory. Stream-validate exact archive membership before safe extraction to its own restore-check subtree. Match all file bytes, ownership, modes, timestamps, xattrs and internal hardlink topology. Keep sources on any failure. Only verified temporary restore files may be removed by prepare; remove empty generated ancestors only within its exact restore root. Write/fsync root-private manifest and archive; report aggregate metadata, never content/secrets.

Remove requires exact recovery prefix, pinned manifest/archive digests, full unchanged source inventory, and an exact root-private offload receipt bound to the approved private local directory with archive/manifest hashes, durable flush, ACL and full local read verification. Remove only the eight exact targets and optionally the extra server transport archive after its verified independent local copy. Preserve recovery manifest/receipt. No '--keep' path that bypasses local offload proof. No broad recursive deletion.

Implementer must test validation/closed target set through non-mutating local checks and bounded disposable fixtures where available. Do not run on VPS, export data, delete sources, commit application files, touch tests, push or deploy. Report exact helper hashes, commands, assumptions, tests and remaining execution checklist. Root obtains independent review before remote execution and owns protected binary transfer, current activity/space checks and final deployment.
