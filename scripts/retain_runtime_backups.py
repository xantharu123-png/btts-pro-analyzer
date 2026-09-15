"""Conservative, separate retention for completed VPS backup archives.

The existing producer still owns the 14-day expiry. This job only removes
intraday duplicates and old *complete* deployment pairs. It never discovers
production databases, partial archives, QA recoveries or arbitrary paths.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from zoneinfo import ZoneInfo


DAILY_ROOT = Path("/var/backups/betboy")
DEPLOY_ROOT = Path("/var/backups/betboy-update")
LOCK = Path("/run/betboy-deploy/deploy.lock")
VERIFIER = Path("/usr/local/libexec/betboy-backup-runtime.py")
DAILY = re.compile(r"betboy-sqlite-(\d{8}T\d{6}Z)\.zip")
DEPLOY = re.compile(r"betboy-(online|preupdate)-(\d{8}T\d{6}Z)-([0-9a-f]{12})-(\d+)\.zip")
ZURICH = ZoneInfo("Europe/Zurich")


@dataclass(frozen=True)
class Plan:
    keep: tuple[str, ...]
    remove: tuple[str, ...]
    verify: tuple[str, ...]


def timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def select_archives(names, *, daily: bool, now: datetime) -> Plan:
    """Pure selection. Unknown/legacy, pinned and incomplete groups survive."""
    names = set(names)
    remove, verify = set(), set()
    groups = defaultdict(list)
    for name in sorted(names):
        match = (DAILY if daily else DEPLOY).fullmatch(name)
        if not match:
            continue
        instant = timestamp(match[1] if daily else match[2])
        if instant > now:
            continue
        key = instant.astimezone(ZURICH).date() if daily else (match[3], match[4])
        groups[key].append((instant, name, "daily" if daily else match[1]))
    if daily:
        for entries in groups.values():
            entries.sort()
            obsolete = {row[1] for row in entries[:-1] if row[1] + ".keep" not in names}
            if obsolete:
                remove.update(obsolete)
                verify.add(entries[-1][1])
    else:
        complete = []
        for entries in groups.values():
            if len(entries) != 2 or {row[2] for row in entries} != {"online", "preupdate"}:
                continue
            online = next(row for row in entries if row[2] == "online")
            offline = next(row for row in entries if row[2] == "preupdate")
            # A repeated PID months later must not manufacture a pair.
            if not 0 <= (offline[0] - online[0]).total_seconds() <= 86400:
                continue
            complete.append((offline[0], tuple(sorted(row[1] for row in entries))))
        complete.sort()
        for _, pair in complete[:-2]:
            if not any(name + ".keep" in names for name in pair):
                remove.update(pair)
        if remove:
            verify.update(name for _, pair in complete[-2:] for name in pair)
    return Plan(tuple(sorted(names - remove)), tuple(sorted(remove)), tuple(sorted(verify)))


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_uid, info.st_gid, info.st_mode, info.st_nlink)


def regular_identity(path: Path, owner: int):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != owner or info.st_mode & 0o022):
        raise RuntimeError(f"Unsafe archive or control file: {path}")
    return identity(info)


def check_directory(path: Path, owner: int):
    if path.resolve(strict=True) != path:
        raise RuntimeError(f"Directory alias forbidden: {path}")
    for current in (path, *path.parents):
        info = current.lstat()
        wanted = owner if current == path else 0
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != wanted or info.st_mode & 0o022:
            raise RuntimeError(f"Unsafe directory: {current}")


def inventory(root: Path, owner: int):
    check_directory(root, owner)
    names = tuple(sorted(item.name for item in root.iterdir()))
    # Unknown artifacts are kept; recognized ZIPs and pin markers must be safe.
    stamps = {name: regular_identity(root / name, 0 if name.endswith(".keep") else owner)
              for name in names if DAILY.fullmatch(name) or DEPLOY.fullmatch(name)
              or name.endswith(".zip.keep")}
    return names, stamps, (root.stat().st_dev, root.stat().st_ino)


def backup_idle():
    result = subprocess.run(
        ["/usr/bin/systemctl", "show", "betboy-backup.service", "--property=ActiveState", "--value"],
        check=True, text=True, capture_output=True, timeout=15,
    )
    return result.stdout.strip() in {"inactive", "failed"}


@contextmanager
def deploy_lock():
    import fcntl
    check_directory(LOCK.parent, 0)
    try:
        created = os.open(LOCK, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(created)
    expected = regular_identity(LOCK, 0)
    descriptor = os.open(LOCK, os.O_RDWR | os.O_NOFOLLOW)
    try:
        if identity(os.fstat(descriptor)) != expected:
            raise RuntimeError("Deployment lock changed")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            yield True
    finally:
        os.close(descriptor)


def verify_archive(path: Path):
    check_directory(VERIFIER.parent, 0)
    regular_identity(VERIFIER, 0)
    # Reuse the installed, reviewed verifier, including SQLite and ledger checks.
    result = subprocess.run(
        ["/usr/bin/python3", "-I", "-B", str(VERIFIER), "--verify-only", str(path)],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode:
        raise RuntimeError(f"Keeper failed restore verification: {path}")


def execute(plans, snapshots, owners, *, verifier=verify_archive, idle=backup_idle):
    """Verify every replacement before unlinking anything; then recheck identity."""
    if not idle():
        raise RuntimeError("Backup service became active; nothing removed")
    for root, plan in plans.items():
        for name in plan.verify:
            verifier(root / name)
            print(json.dumps({"verified_keeper": str(root / name)}), flush=True)
    if not idle():
        raise RuntimeError("Backup service became active; nothing removed")
    for root in plans:
        if inventory(root, owners[root]) != snapshots[root]:
            raise RuntimeError(f"Backup inventory changed; nothing removed: {root}")
    removed_bytes = 0
    removed_count = 0
    for root, plan in plans.items():
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != snapshots[root][2]:
                raise RuntimeError("Backup directory changed")
            for name in plan.remove:
                expected = snapshots[root][1][name]
                current = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if identity(current) != expected:
                    raise RuntimeError(f"Archive changed: {root / name}")
                print(json.dumps({"removing": str(root / name), "bytes": current.st_size}), flush=True)
                os.unlink(name, dir_fd=fd)
                removed_bytes += current.st_size
                removed_count += 1
            os.fsync(fd)
        finally:
            os.close(fd)
    return {"removed_archives": removed_count, "removed_bytes": removed_bytes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply the fixed VPS retention policy")
    args = parser.parse_args()
    import pwd
    if os.geteuid() != 0:
        parser.error("This fixed-path VPS maintenance command requires root")
    if args.apply and not os.environ.get("INVOCATION_ID"):
        parser.error("Apply must run via betboy-backup-retention.service for backup ordering")
    owners = {DAILY_ROOT: pwd.getpwnam("betboy-backup").pw_uid, DEPLOY_ROOT: 0}
    with deploy_lock() as locked:
        if not locked or not backup_idle():
            print(json.dumps({"skipped": "deployment or backup active"}))
            return
        now = datetime.now(timezone.utc)
        snapshots = {root: inventory(root, owner) for root, owner in owners.items()}
        plans = {root: select_archives(snapshots[root][0], daily=root == DAILY_ROOT, now=now)
                 for root in owners}
        print(json.dumps({"apply": args.apply, "plans": {
            str(root): {"remove": plan.remove, "verify": plan.verify,
                        "kept_entries": len(plan.keep),
                        "remove_bytes": sum(snapshots[root][1][n][2] for n in plan.remove)}
            for root, plan in plans.items()}}), flush=True)
        if args.apply:
            print(json.dumps(execute(plans, snapshots, owners)), flush=True)


if __name__ == "__main__":
    main()
