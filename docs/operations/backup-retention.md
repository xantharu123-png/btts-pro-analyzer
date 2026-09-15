# VPS backup retention

This maintenance job is independent of the pinned updater and backup producer.
It changes no app data, predictions, settlement rules or backup formats.

- Daily backups: keep the latest archive per **Europe/Zurich calendar day**.
  The existing backup producer continues its 14-day age retention.
- Deployment backups: keep at least the latest **two complete online/preupdate
  pairs**. Match by previous commit and deployment PID, not by identical time.
- Keep legacy deployment ZIPs without a PID (historical migration checkpoints),
  incomplete/ambiguous pairs, future-dated files, partial outputs, all unknown
  artifacts and all directories outside the two fixed backup roots.
- A root-owned `ARCHIVE.zip.keep` file protects that archive, or its complete
  deployment pair. It does not override the original producer's age expiry.
- Before removing any archive, restore-check its retained replacement using
  the installed backup verifier, including SQLite and ledger integrity checks.
  Failure or a changed inventory stops deletion. No automatic fallback to a
  smaller retention set. Kept historical archives are not recreated copies of
  the removed intermediate states: those intermediate states are discarded.

## Scheduling and deployment

Install the reviewed script as root:root 0755 at
`/usr/local/libexec/betboy-retain-backups.py`, and the two matching unit files
as root:root 0644 in `/etc/systemd/system`. Check `systemd-analyze verify`, reload
systemd, then enable only `betboy-backup-retention.timer`.

The timer runs at 04:20 Zurich time plus up to five minutes. It adds one
maintenance timer; it does not replace the seven application timers.
No existing pinned service, updater, backup helper or unit drop-in is changed.

The job takes the existing deployment lock nonblockingly and skips when the
backup service is running. `Before=betboy-backup.service` holds a newly requested
backup start until this oneshot finishes. Thus it cannot prune a deployment's
backup-tree snapshot or race a scheduled backup. If deployment holds the lock,
retention skips successfully and will retry on its next scheduled run.

Manual preview (no deletion):
`sudo /usr/bin/python3 -I -B /usr/local/libexec/betboy-retain-backups.py`

Manual apply: use `sudo systemctl start betboy-backup-retention.service`, not a
standalone `--apply` invocation: systemd supplies the backup-start ordering.
The journal records retained archive verification and each removed filename.

For rollback, disable the new timer and remove these three new installed files.
Existing backups/app scheduling are unchanged. Deleted obsolete snapshots are
not recoverable unless separately archived; the protected restore points remain.
