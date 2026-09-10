# Real-source backup: exact directory-mode preparation

## User approval — 10 September 2026, 20:27 UTC

The user explicitly answered yes to the exact twelve modes0775→0755 listed
below, with original metadata saved first and ownership/content preserved.
This supersedes the earlier pending-approval wording, not any execution gate.
At this entry no production mode had yet been changed. The unchanged pinned
procedure must fresh-check every real target before saving/changing it.

10 September 2026. This is separate from the one-time **updater-only** installer. At this checkpoint no production permission, code, service, database or key was changed.

## Fresh real failure, preserved

The exact independently accepted Task2 source `6ba2c68`, updater SHA `4b814c500f5eb03fb7a28f576210f02759300aa5560ef273834c6eb3195e8c19`, ran the actual online producer under the existing deploy lock. It stopped **before archive acceptance/publication** with `unsafe database directory principal`.

New diagnostic stage: `/var/lib/betboy-live-backup-_w1996l5`. Private producer/error logs are preserved. Current production HEAD and installed-updater byte/metadata identity were verified unchanged. This is not a successful fresh backup and cannot be substituted by the earlier scheduled backup.

Read-only traversal as actual betboy uid997 found88 databases across45 directories, no walk errors and no failed DB-file principal checks. Twelve directories were uid997/gid987, mode0775:

```text
/opt/betboy/app/logs
/opt/betboy/app/tests
/opt/betboy/app/reports
/opt/betboy/app/runtime_state/tennis
/opt/betboy/app/runtime_state/logs
/opt/betboy/app/runtime_reports
/opt/betboy/app/runtime_reports/tennis
/opt/betboy/app/scanners
/opt/betboy/app/.streamlit
/opt/betboy/app/deploy
/opt/betboy/app/deploy/systemd
/opt/betboy/app/scripts
```

NSS listed no supplementary members in groupbetboy; only betboy used its primary GID987. **That did not prove an exclusive writer group.** Independent reviewer R2 found the installed, hash-pinned backup unit grants `SupplementaryGroups=betboy` to the different `betboy-backup` UID and has `ReadWritePaths=/opt/betboy/app`. Its actual installed SHA remains `922352a5d3c883cc671da419c5d3fa589cbe9cd025f32d4c4d9f7b6a9648edb8`.

Therefore no g+w exception was added to the producer and no directory was silently skipped. Task2 checks stay unchanged.

## Narrow additional approval requested

The controller asked for explicit authority to change **only these twelve directory modes0775→0755**, with all UIDs/GIDs, contents, services and keys unchanged. App ownership still permits normal app writing. Original metadata must be durably saved first and operational failures restored through the held exact directory descriptors. This is not an implicit extension of the updater-only installer.

At this checkpoint that asynchronous user answer is still pending. No production-mode command has run.

## Prepared, independently reviewed native procedure

Local ignored procedure: `.pytest_tmp/repair_live_directory_modes.py`.
Exact reviewed SHA256: `8be3d721660d7438a251628ea58c3e61a64f760d96d69fee4d6a82d22ebfe304`.

It requires the pinned old updater both before and after obtaining the existing deploy lock; rejects Python optimization; opens every target component without symlink traversal; validates each owner/group/mode and held-inode/path identity; saves complete original metadata before any fchmod; fsyncs the new journal-directory entry and journal; and refuses to alter unknown replacement inodes or unknown modes during rollback. No recursive chmod, chown, data edit or deletion is involved.

R2's independent review found and closed four concrete points before any production execution: parent-directory durability, transient journal publication recovery, post-rollback path identity, and pin revalidation under the lock. Final scoped code verdict: **APPROVED**, distinct from user authority and real-backup acceptance.

Native fixture runner: `.pytest_tmp/test_native_directory_modes.py`, using only newly generated synthetic roots. First preserved stage `/var/lib/betboy-directory-mode-qa-l59qn1az` exposed a harness assumption: actual `/opt/betboy` is app-owned997:987/0750, not root-owned. The harness now permits the existing app/root owner only for that fixed live parent, while retaining strict root-only private QA/recovery ancestors. No actual parent mode or owner was changed.

Final exact procedure passed all seven native cases at `/var/lib/betboy-directory-mode-qa-n7kx9j5y`:

1. All twelve expected changes complete, UIDs/GIDs/inodes retained.
2. Parent-entry fsync failure causes zero chmod calls.
3. fchmod failure restores original modes.
4. Target-directory fsync failure restores original modes.
5. Transient journal-file fsync failure restores original modes and publishes terminal recovery status.
6. Replacement after journal publication leaves the foreign inode untouched.
7. Replacement during rollback leaves the foreign inode untouched and records `rollback_conflict`.

The success fixture also used actual identities: uid997 could still create a file; backup uid995 with the explicit supplementary app group was denied. These are real Linux fixture observations, not emulated Windows DAC or physical power-cut tests.

## Actual approved execution — 10 September 2026, 20:35:36 UTC

The unchanged pinned procedure completed against all twelve real directories.
Original metadata was durably recorded before any fchmod at
`/var/lib/betboy-directory-mode-repair-fi_69l74/metadata.json`.
It finished with `status=complete`, twelve changes0775→0755, the same held
directory identities/UID997/GID987, and the installed old updater unchanged.
An independent subsequent stat call confirmed all twelve0755 modes and the
root:root0600 metadata journal. No source bytes, service, key or database
contents were edited by this procedure.

Further read-only checks bound all twelve current identities to that journal;
SHA256`9309b326007e19b73b847f00efaaa638ae0d209633276dad667c99eded503b88`.
Actual UID997 retains effective write access to all12 directories; backup
UID995 with the explicit app supplementary group has no effective write
access to any. Both lack read access to the private diagnostic archive.

The fresh full backup diagnostic then passed at
`/var/lib/betboy-live-backup-j0co13x8`:88 databases, complete MANIFEST and actual
isolated restore/HMAC verification, exit0. Archive SHA256
`21bd2b529cf31451f336d1821ab00578ef8ff54beb377ca3494911edcfac39a4`.
This resolves the earlier directory-principal blocker; it does not stand in
for the final installer's fresh exact-target backup/D4/evidence chain.

During the later separately authorized normal deployment, the pre-existing
`prepare_backup_storage_and_sources` contract may set DB-parent directories
to0750. Do not add another permission correction or claim that all twelve
must remain0755: both0750 and0755 preserve the intended absence of group write.

## Historical remaining gates at preparation time

Explicit user approval; exact procedure execution and post-check on the twelve real paths; a new full real backup/isolated restore/HMAC; target D4 with measured resources; installer independent/native acceptance; then the separately controlled updater exchange and ordinary exact-revision app release. None is inferred from the synthetic PASS results.
