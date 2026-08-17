# BetBoy backup hash anchors

This file records externally reviewable hashes only. It never contains backup
contents, credentials, account identifiers, or restore secrets.

## 2026-08-17

### Root-protected updater recovery snapshot, 10:45 UTC

- Archive:
  `betboy-preupdate-20260817T104548Z-239c9ea38a6e.zip`
- VPS path:
  `/var/backups/betboy-update/betboy-preupdate-20260817T104548Z-239c9ea38a6e.zip`
- Owner/mode: `root:root`, `0600`
- Size: `2733026` bytes
- SHA-256: `b95419a741ec61b7416b98b75b63ec265e77d7c7b248703950be3dee88854507`
- ZIP members: `82` SQLite databases plus `MANIFEST.json`
- Manifest source head:
  `239c9ea38a6e396c916ee7cf36fe7ed396d4b11f`
- Verification: the root updater created the archive only after all database
  writers were stopped and verified inventory, per-file hashes, ZIP CRC and
  SQLite `quick_check`. An independent post-deploy `zipfile.testzip()` returned
  no bad member and confirmed 83 total members.

### Root-protected runtime migration recovery copy, 10:43 UTC

- Directory: `/var/backups/betboy-migration-9171bdb`, `root:root`, `0700`
- Archive and external manifest are both `root:root`, `0600`.
- Archive SHA-256:
  `0a303a7a45d70fd293650bfb6677288184fc095076e0d27d5e24e44cb3f8b003`
- Manifest SHA-256:
  `00b0cc8d2095fd3c1a96aa56101b72bdb2c4c3cba27c2e97fb89e6eb5a0faf08`
- Verification: after every writer was quiesced, all 22 legacy artifacts again
  matched both the manifest and their migrated runtime destinations before any
  legacy duplicate was removed.

### SSH authorized-key recovery, 10:59 UTC

- Backup:
  `/var/backups/betboy-ssh/authorized_keys.pre-prune-20260817T105940Z-d861d647`
- Owner/mode: `root:root`, `0600`
- Size: `357` bytes
- SHA-256: `770369de3b59fab49778e360c971705a59cbbef0a118ccd0c061cca82138d265`
- Scope: public `authorized_keys` bytes immediately before removal of the two
  old keys; no private key or passphrase is present.
- Post-prune `authorized_keys` SHA-256:
  `8bd63630dcd79db8a4fd9e105ce2f52bccbe8869b2b770df297d3f5441aaa64e`.
  Exactly the new key remained and two fresh strict BatchMode logins succeeded.

### Pre-deployment SQLite snapshot, 09:16 UTC

- Archive: `betboy-sqlite-20260817T091614Z.zip`
- VPS path: `/var/backups/betboy/betboy-sqlite-20260817T091614Z.zip`
- Size: `2728021` bytes
- SHA-256: `0de41479d65e09cf91f47dc1bb5c71126192ad1c2fed4917c9a8e548c410dddf`
- ZIP entries: `82`
- Independently restored SQLite databases: `82`
- Verification: the systemd backup job finished with `Result=success` and
  `ExecMainStatus=0`. ZIP path-safety and CRC checks passed; every database
  restored into an isolated temporary directory returned exactly `ok` from
  `PRAGMA quick_check` in SQLite `mode=ro`/`query_only` mode. The temporary
  restore directory was removed afterwards.

### Runtime-artifact preservation, 09:07 UTC

- Archive: `betboy-runtime-artifacts-20260817T090739Z.tar.gz`
- VPS path:
  `/var/backups/betboy/runtime-artifacts/betboy-runtime-artifacts-20260817T090739Z.tar.gz`
- Size: `768831` bytes
- SHA-256: `0a303a7a45d70fd293650bfb6677288184fc095076e0d27d5e24e44cb3f8b003`
- Files: `22` changed or untracked runtime artifacts plus the embedded manifest
- External manifest SHA-256:
  `00b0cc8d2095fd3c1a96aa56101b72bdb2c4c3cba27c2e97fb89e6eb5a0faf08`
- Verification: every archived path was allowlisted, a regular non-symlink
  below `/opt/betboy/app`, and hash-bound before archiving. Archive members
  were checked against the exact expected list. The mutable model state,
  calibration watch, pipeline logs and weekly reports were also copied with
  matching hashes to their new ignored `runtime_state`/`runtime_reports`
  locations before repository cleanup.

### Scheduled SQLite snapshot, 01:17 UTC

- Archive: `betboy-sqlite-20260817T011714Z.zip`
- VPS path: `/var/backups/betboy/betboy-sqlite-20260817T011714Z.zip`
- Size: `2722256` bytes
- SHA-256: `b8d702ce218e9d9d0fd0728d81f1913dcc19389b03946d6bfb67e5f99762f976`
- ZIP entries: `82`
- Independently restored SQLite databases: `82`
- Verification: ZIP path-safety and CRC checks passed; every restored database
  returned exactly `ok` from `PRAGMA quick_check` while opened via SQLite URI
  `mode=ro` with `PRAGMA query_only=ON`.
- Isolation: extraction used a fresh `/tmp/betboy-restore-drill-*` directory as
  user `betboy`; the directory was removed after verification. No production
  database, service, timer, or application file was changed.

This proves that this archive can be extracted and its databases opened. It is
not a full bare-server or OVH account-loss recovery test. The OVH Standard
automatic backup was visible as active with a restore point from
2026-08-16 12:02 UTC; restoring that image was intentionally not triggered on
the production VPS.
