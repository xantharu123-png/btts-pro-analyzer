# BetBoy backup hash anchors

This file records externally reviewable hashes only. It never contains backup
contents, credentials, account identifiers, or restore secrets.

## 2026-08-17

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
