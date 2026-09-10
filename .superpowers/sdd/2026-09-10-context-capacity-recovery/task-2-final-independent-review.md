# Task 2 final independent review and native boundary

Reviewed code: `6ba2c68acf474d24648a816eac7586fb41929349`.
Updater SHA256: `4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`.
Reviewer: independent `capacity_task2_checkpoint_review`; controller did not author the fixes.

## Verdict

The combined Task 2 code is **APPROVED**, with no remaining Critical or Important findings from this review series. This is code-review approval, not deployment or empirical model approval.

The final production change is one line in `snapshot_backup_source_metadata`: excluded directory components are matched exactly, not with a broader `.pytest_tmp` prefix. Thus an allowed `.pytest_tmp-keep` subtree receives the same rollback metadata protection as the files already admitted by the backup producer and immutable helper. The exact `.pytest_tmp` component remains excluded.

Fresh independent evidence:

- 14 targeted tests passed, 326 deselected, in 6.23 seconds.
- The new metadata regression was independently run against prior `690dd16` and failed with zero saved records. It passed against `6ba2c68` with all four expected records.
- Actual fixture rights were changed; verification failed as expected; restoration then made verification pass. Original file bytes stayed unchanged.
- Bash syntax, diff check and exact-version comparison passed. Both pinned helper hashes stayed unchanged.

The preceding Unicode correction was also accepted: source enumeration uses the same Python casefold semantics as the immutable backup helper, including the long-s SQLite extension case. This closes the prior traversal-error, ASCII-case and Unicode-case discovery findings; it does not discard their original reproductions.

## Native evidence and remaining gate

The controller completed native Linux tests for exact `690dd16` before this final one-line metadata correction:

- 339 tests passed in 37.16 seconds (37.838 seconds supervised), under ordinary SSH uid1000 in an isolated QA directory.
- Exact native source: `/var/lib/betboy-capacity-code-wpsy55_5/source`.
- Synthetic full-chain controls: `/var/lib/betboy-task2-native-f8habos7`. These included actual HMAC rejection, OS read/write denials, retained-file-descriptor mutation before/after private copying, unreadable-subtree rejection, and full restore of the five-database Unicode fixture.

The exact `6ba2c68` native metadata/340-test confirmation is still pending. Its Git archive has SHA256 `fae3a6bc586965e9a2e47d5ac0388976e1d3a3a0ead22b9298b3f0e037e3a0d1`; the attempted transfer to the existing private VPS QA directory was rejected by the approval reviewer. No alternative transfer was attempted. A narrow asynchronous user approval request was sent; local Task 3 implementation can continue without this transfer.

Neither the installed updater nor the application was changed by this review. Fresh real full-backup/restore, exact-target D4 and controlled updater-only exchange remain required.

## Exact final native confirmation and real-source hold

The user subsequently explicitly approved transferring this repair's versioned QA archives to the existing private VPS QA directory. The exact `6ba2c68` archive was transferred, with no change of destination or payload. Native source is `/var/lib/betboy-capacity-code-l32ocxk5/source` (788 members).

- Ordinary SSH uid1000: **340 passed in39.49s**, 40.28s supervised, no stderr; QA directory `task2-hooks-6ba2c68-28_dllr2`.
- Native full synthetic chain repeated successfully at `/var/lib/betboy-task2-native-6uwrbd3e`: real restore/HMAC, wrong-key rejection, Unicode and mixed-case databases, four private-file DAC denials, both retained-FD cases and actual EACCES rejection.
- The final prefix-metadata test used actual root/app/backup UID/GID and chmod operations, not stat/chown emulation. All four records were captured; real rights mutation caused the expected verify failure; restore and verify passed with unchanged original bytes. Exact `.pytest_tmp` remained excluded.

This closes the exact final **fixture/native metadata** gate. It does not close real-source backup acceptance: the next fresh real producer stopped on twelve existing app-owned0775 directories. A separate read-only review showed this is a legitimate second-writer concern, because the pinned backup unit grants its different UID the supplementary app group. No producer permission exception was implemented. Details and the additional user-approval boundary are recorded in `directory-mode-preflight-20260910.md`.
