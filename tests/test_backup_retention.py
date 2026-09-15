from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import sys

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "retain_runtime_backups.py"
spec = importlib.util.spec_from_file_location("betboy_retention_tests", SOURCE)
retention = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = retention
spec.loader.exec_module(retention)
NOW = datetime(2026, 9, 15, 22, tzinfo=timezone.utc)


def daily(instant):
    return f"betboy-sqlite-{instant}.zip"


def pair(day, pid="123", commit="a" * 12):
    return (f"betboy-online-202609{day:02}T120000Z-{commit}-{pid}.zip",
            f"betboy-preupdate-202609{day:02}T120500Z-{commit}-{pid}.zip")


def select(names, daily=False, now=NOW):
    return retention.select_archives(names, daily=daily, now=now)


def test_daily_keeps_last_per_zurich_day_not_utc_day():
    old = daily("20260914T233325Z")  # Zurich September 15
    keep14 = daily("20260914T214342Z")
    keep15 = daily("20260915T190533Z")
    plan = select([old, keep14, keep15], daily=True)
    assert plan.remove == (old,)
    assert plan.verify == (keep15,)
    assert plan.keep == tuple(sorted([keep14, keep15]))


@pytest.mark.parametrize("before,after", [
    ("20260110T225900Z", "20260110T230100Z"),  # winter midnight
    ("20260710T215900Z", "20260710T220100Z"),  # summer midnight
])
def test_timezone_midnight_preserves_both_days(before, after):
    assert not select([daily(before), daily(after)], daily=True).remove


def test_dst_fallback_is_one_local_day():
    old, new = daily("20261025T003000Z"), daily("20261025T013000Z")
    now = datetime(2026, 10, 26, tzinfo=timezone.utc)
    assert select([old, new], daily=True, now=now).remove == (old,)


def test_retention_does_not_erase_distinct_old_days():
    names = [daily(f"202608{i:02}T120000Z") for i in range(1, 25)]
    assert not select(names, daily=True).remove  # producer owns age expiry


def test_keep_exactly_two_newest_complete_deploy_pairs():
    names = [name for day in range(10, 16) for name in pair(day, str(day))]
    plan = select(names)
    assert set(plan.keep) == set(pair(14, "14") + pair(15, "15"))
    assert set(plan.verify) == set(plan.keep)
    assert len(plan.remove) == 8


def test_no_deletion_with_fewer_than_three_complete_pairs():
    assert not select(pair(14) + pair(15, "456")).remove


def test_pair_groups_use_commit_and_pid_not_timestamp_only():
    names = pair(12, "1") + pair(14, "2") + pair(15, "3")
    assert set(select(names).remove) == set(pair(12, "1"))
    wrong = [pair(12, "1")[0], pair(12, "2")[1]]
    assert not select(wrong + list(pair(14, "3") + pair(15, "4"))).remove


@pytest.mark.parametrize("old", [
    [pair(10)[0]],
    [pair(10)[1]],
    [pair(10)[0], pair(11)[0], pair(11)[1]],
    [pair(10)[0], pair(12)[1]],
    [pair(12)[0], pair(10)[1]],
])
def test_incomplete_ambiguous_reused_pid_and_reversed_pairs_survive(old):
    plan = select(old + list(pair(14, "2") + pair(15, "3")))
    assert not plan.remove


def test_unknown_legacy_partial_and_future_are_preserved():
    extras = ["betboy-preupdate-20260825T000000Z-abcdef123456.zip",
              "migration", "foo.zip", pair(10)[0] + ".partial.123"]
    future = list(pair(16, "16"))
    plan = select(extras + future + list(pair(10, "10") + pair(14, "14") + pair(15, "15")))
    assert set(extras + future) <= set(plan.keep)
    assert set(plan.remove) == set(pair(10, "10"))


def test_pin_protects_entire_pair():
    pinned = pair(10, "10")
    plan = select(pinned + (pinned[0] + ".keep",) + pair(14, "14") + pair(15, "15"))
    assert not plan.remove


def test_daily_pin_protects_intermediate_snapshot():
    old, new = daily("20260915T080000Z"), daily("20260915T090000Z")
    assert not select([old, new, old + ".keep"], daily=True).remove


def test_invalid_recognized_date_fails_closed():
    with pytest.raises(ValueError):
        select([daily("20260999T000000Z")], daily=True)


def test_input_order_and_repetitions_do_not_change_plan():
    names = list(pair(10, "10") + pair(14, "14") + pair(15, "15"))
    assert select(names) == select(list(reversed(names)) + names)


@pytest.fixture
def real_archives(tmp_path, monkeypatch):
    root = tmp_path / "backups"
    root.mkdir()
    names = [daily("20260915T080000Z"), daily("20260915T090000Z")]
    for name in names:
        (root / name).write_bytes(b"test snapshot")
        (root / name).chmod(0o600)
    # Tests live below platform-specific temporary parents; production checks
    # are tested separately and remain mandatory in the actual command.
    monkeypatch.setattr(retention, "check_directory", lambda *args: None)
    if os.name != "posix":
        # Windows chmod has no POSIX group-write bits. Real ownership/link
        # validation runs unpatched in the Linux-only permission tests below.
        monkeypatch.setattr(retention, "regular_identity", lambda path, owner: retention.identity(path.lstat()))
    owner = (root / names[0]).stat().st_uid
    plans = {root: select(names, daily=True)}
    snapshots = {root: retention.inventory(root, owner)}
    return root, names, plans, snapshots, {root: owner}


def test_failed_keeper_leaves_everything_untouched(real_archives):
    root, names, plans, snapshots, owners = real_archives
    def fail(_):
        raise RuntimeError("corrupt")
    with pytest.raises(RuntimeError, match="corrupt"):
        retention.execute(plans, snapshots, owners, verifier=fail, idle=lambda: True)
    assert all((root / name).exists() for name in names)


def test_changed_inventory_aborts_before_deletion(real_archives):
    root, names, plans, snapshots, owners = real_archives
    def mutate(_):
        (root / names[0]).write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="inventory changed"):
        retention.execute(plans, snapshots, owners, verifier=mutate, idle=lambda: True)
    assert all((root / name).exists() for name in names)


@pytest.mark.parametrize("states", [[False], [True, False]])
def test_active_backup_aborts_without_deletion(real_archives, states):
    root, names, plans, snapshots, owners = real_archives
    states = iter(states)
    with pytest.raises(RuntimeError, match="became active"):
        retention.execute(plans, snapshots, owners, verifier=lambda _: None, idle=lambda: next(states))
    assert all((root / name).exists() for name in names)


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory-descriptor unlink")
def test_verified_apply_is_scoped_and_idempotent(real_archives):
    root, names, plans, snapshots, owners = real_archives
    proof = []
    result = retention.execute(plans, snapshots, owners, verifier=proof.append, idle=lambda: True)
    assert result == {"removed_archives": 1, "removed_bytes": 13}
    assert proof == [root / names[1]]
    assert not (root / names[0]).exists()
    assert (root / names[1]).exists()
    assert not select([p.name for p in root.iterdir()], daily=True).remove


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership and links")
@pytest.mark.parametrize("kind", ["symlink", "hardlink", "writable"])
def test_unsafe_recognized_file_is_rejected(tmp_path, kind):
    target = tmp_path / "file"
    target.write_bytes(b"data")
    path = tmp_path / "candidate"
    if kind == "symlink":
        path.symlink_to(target)
    elif kind == "hardlink":
        os.link(target, path)
    else:
        path.write_bytes(b"data")
        path.chmod(0o666)
    with pytest.raises(RuntimeError, match="Unsafe archive"):
        retention.regular_identity(path, os.getuid())


def test_service_serializes_backup_start_and_keeps_original_units_unmodified():
    base = SOURCE.parents[1] / "deploy" / "systemd"
    service = (base / "betboy-backup-retention.service").read_text()
    assert "Before=betboy-backup.service" in service
    assert "Type=oneshot" in service
    assert "RuntimeDirectoryPreserve=yes" in service
    assert "ProtectSystem=strict" in service
    assert "InaccessiblePaths=/opt/betboy /etc/betboy" in service
    assert "/usr/local/libexec/betboy-retain-backups.py --apply" in service
    assert "Europe/Zurich" in (base / "betboy-backup-retention.timer").read_text()


@pytest.mark.skipif(os.name != "posix", reason="flock is Linux-only")
def test_deploy_lock_exclusion_and_release(tmp_path, monkeypatch):
    lock = tmp_path / "deploy.lock"
    monkeypatch.setattr(retention, "LOCK", lock)
    monkeypatch.setattr(retention, "check_directory", lambda *args: None)
    # The server suite runs unprivileged; test flock without pretending to root.
    check = retention.regular_identity
    monkeypatch.setattr(retention, "regular_identity", lambda path, owner: check(path, os.getuid()))
    with retention.deploy_lock() as first:
        assert first is True
        with retention.deploy_lock() as second:
            assert second is False
    with retention.deploy_lock() as later:
        assert later is True
