from __future__ import annotations

import hashlib
import re
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from scripts import backup_runtime_databases as backup
from scripts import run_football_shadow_due as football_job


EXPECTED_TIMERS = (
    "betboy-wettfinder.timer",
    "betboy-football-shadow.timer",
    "betboy-tennis.timer",
    "betboy-esports.timer",
    "betboy-redcard-settlement.timer",
    "betboy-redcard-history.timer",
    "betboy-backup.timer",
)


def test_wettfinder_timer_is_installed_and_enabled_by_deploy_scripts():
    root = Path(__file__).resolve().parents[1]
    service = (
        root / "deploy" / "systemd" / "betboy-wettfinder.service"
    ).read_text(encoding="utf-8")
    timer = (
        root / "deploy" / "systemd" / "betboy-wettfinder.timer"
    ).read_text(encoding="utf-8")
    update = (root / "deploy" / "update_server.sh").read_text(encoding="utf-8")
    bootstrap = (root / "deploy" / "bootstrap_server.sh").read_text(
        encoding="utf-8"
    )

    assert "wettfinder_automation.py" in service
    assert "OnCalendar=*-*-* *:07,37:00" in timer
    for expected in EXPECTED_TIMERS:
        assert update.count(f"    {expected}\n") == 1
        assert bootstrap.count(f"    {expected}\n") == 1
    assert 'systemctl enable --now "${BETBOY_TIMERS[@]}"' in update
    assert 'systemctl restart "${BETBOY_TIMERS[@]}"' in update
    assert 'systemctl enable --now "${BETBOY_TIMERS[@]}"' in bootstrap


def test_update_preflights_before_downtime_and_has_recovery_path():
    root = Path(__file__).resolve().parents[1]
    update = (root / "deploy" / "update_server.sh").read_text(
        encoding="utf-8"
    )

    main = update.index('preflight "$@"\nremember_unit_state')
    trusted_fetch = update.index(
        'root_git -C "${TRUSTED_TREE}" fetch --quiet --no-tags'
    )
    app_fetch = update.index(
        'git_betboy fetch --no-tags "${REPOSITORY_URL}" refs/heads/main'
    )
    stop_timers = update.index(
        'systemctl stop "${BETBOY_TIMERS[@]}"',
        main,
    )
    stop_app = update.index("systemctl stop betboy-app.service", main)
    post_stop_manifest = update.index(
        'verify_app_bytes "${PREVIOUS_MANIFEST}"', stop_app
    )
    backup = update.index("\ncreate_fresh_backup\n", stop_app)
    apply_payload = update.index(
        'apply_trusted_payload "${TARGET_MANIFEST}" "${TARGET_PAYLOAD}"',
        backup,
    )
    update_ref = update.index(
        'git_betboy update-ref refs/heads/main "${TARGET_HEAD}" "${PREVIOUS_HEAD}"',
        apply_payload,
    )

    assert trusted_fetch < app_fetch < main
    assert main < stop_timers < stop_app < post_stop_manifest < backup
    assert backup < apply_payload < update_ref
    assert "git pull" not in update
    assert "git merge" not in update
    assert "reset --hard" not in update
    assert 'root_git -C "${TRUSTED_TREE}" merge-base --is-ancestor' in update
    assert "Untracked or ignored files would be overwritten" in update
    assert "ls-files --others --ignored --exclude-standard" in update
    assert "target adds or modifies protected runtime path" in update
    assert "untracked executable/code file is forbidden" in update
    assert "trap 'recover_update \"$?\"' EXIT" in update
    assert 'verify_app_bytes "${PREVIOUS_MANIFEST}"' in update
    assert 'systemctl stop "${BETBOY_WORKERS[@]}"' in update
    assert "restore_unit_state" in update
    assert "wait_for_workers" in update
    assert "verify_runtime" in update
    assert "requirements.txt unchanged; skipping pip completely" in update
    assert "requirements.txt changed; use the separately reviewed" in update
    assert "pip install" not in update
    assert "Fresh root-protected backup verified" in update
    assert "PRAGMA quick_check" in update
    assert '"database_count": len(inventory)' in update
    assert 'readonly RECOVERY_BACKUP_DIR=/var/backups/betboy-update' in update
    assert "FAIL-CLOSED: new app code may have touched databases" in update


def test_root_deploy_tools_do_not_trust_betboy_writable_checkout():
    root = Path(__file__).resolve().parents[1]
    update = (root / "deploy" / "update_server.sh").read_text(
        encoding="utf-8"
    )
    bootstrap = (root / "deploy" / "bootstrap_server.sh").read_text(
        encoding="utf-8"
    )

    for script, trusted_path in (
        (update, "/usr/local/sbin/betboy-update"),
        (bootstrap, "/usr/local/sbin/betboy-bootstrap"),
    ):
        assert trusted_path in script
        assert "Refusing sudo execution from a writable checkout" in script
        assert "root:root" in script
        assert "^[0-9A-Fa-f]{40}$" in script
        assert (
            "https://github.com/xantharu123-png/btts-pro-analyzer.git"
            in script
        )
        assert "GIT_CONFIG_GLOBAL=/dev/null" in script
        assert "GIT_NO_REPLACE_OBJECTS=1" in script
        assert "core.hooksPath=/dev/null" in script
        assert "/usr/bin/python3 -I -" in script
        assert "cd /" in script
        assert "refs/heads/main" in script
        assert "Requested commit is not the current origin/main tip" in script
        assert 'trusted_file "deploy/systemd/${timer}"' in script
        assert '"${APP_DIR}"/deploy/systemd/*.service' not in script
        assert "git pull" not in script
        assert "expected_unit_sha256" in script
        assert "differs from its reviewed byte allowlist" in script
        assert "DropInPaths" in script
        assert "FragmentPath" in script
        assert "/run/systemd/system.control" in script
        assert "/run/systemd/generator.early" in script
        assert "pgrep -u betboy" in script

    assert (
        '"$(trusted_file deploy/update_server.sh)" "${TRUSTED_UPDATER}"'
        in update
    )
    assert (
        '"$(trusted_file deploy/update_server.sh)" "${TRUSTED_UPDATER}"'
        in bootstrap
    )
    assert "chown -R betboy:betboy" not in bootstrap
    assert "Initial checkout must already equal the authorized target" in bootstrap
    assert "target tracks protected runtime path" in bootstrap


def test_dependency_changes_have_an_explicit_fail_closed_gate():
    root = Path(__file__).resolve().parents[1]
    update = (root / "deploy" / "update_server.sh").read_text(encoding="utf-8")
    runbook = (root / "deploy" / "VENV_MIGRATION.md").read_text(encoding="utf-8")

    assert "requirements.txt changed" in update
    assert "pip install" not in update
    assert "--require-hashes" in runbook
    assert "/opt/betboy/venvs/<lock-sha256>" in runbook
    assert "atomic" in runbook.lower()


def test_every_root_installed_betboy_service_drops_privileges():
    root = Path(__file__).resolve().parents[1]
    systemd = root / "deploy" / "systemd"
    expected_services = {
        "betboy-app.service",
        *(timer.removesuffix(".timer") + ".service" for timer in EXPECTED_TIMERS),
    }

    assert {path.name for path in systemd.glob("betboy-*.service")} == expected_services
    for name in expected_services:
        service = (systemd / name).read_text(encoding="utf-8")
        assert service.count("User=") == 1
        assert "User=betboy" in service
        assert service.count("Group=") == 1
        assert "Group=betboy" in service
        assert service.count("NoNewPrivileges=true") == 1
        for line in service.splitlines():
            if line.startswith("Exec"):
                command = line.split("=", 1)[1].lstrip("-@:^|")
                assert not command.startswith(("+", "!"))

    for timer in EXPECTED_TIMERS:
        timer_text = (systemd / timer).read_text(encoding="utf-8")
        explicit_units = [
            line for line in timer_text.splitlines() if line.startswith("Unit=")
        ]
        assert explicit_units in ([], [f"Unit={timer.removesuffix('.timer')}.service"])


def test_root_installers_pin_every_systemd_unit_to_reviewed_bytes():
    root = Path(__file__).resolve().parents[1]
    systemd = root / "deploy" / "systemd"
    pattern = re.compile(
        r"deploy/systemd/([^\)]+)\) printf '%s\\n' ([0-9a-f]{64})"
    )
    expected_names = {path.name for path in systemd.glob("betboy-*")}

    mappings = []
    for script_name in ("update_server.sh", "bootstrap_server.sh"):
        script = (root / "deploy" / script_name).read_text(encoding="utf-8")
        mapping = dict(pattern.findall(script))
        assert set(mapping) == expected_names
        mappings.append(mapping)
        for name, expected_hash in mapping.items():
            actual = hashlib.sha256((systemd / name).read_bytes()).hexdigest()
            assert actual == expected_hash
    assert mappings[0] == mappings[1]


def test_esports_broad_discovery_runs_once_daily():
    root = Path(__file__).resolve().parents[1]
    timer = (
        root / "deploy" / "systemd" / "betboy-esports.timer"
    ).read_text(encoding="utf-8")

    assert timer.count("OnCalendar=") == 1
    assert "OnCalendar=*-*-* 08:23:00" in timer


def test_football_job_skips_when_no_work_is_due(monkeypatch, capsys):
    called = False

    def fake_run(_ctx):
        nonlocal called
        called = True

    monkeypatch.setattr(football_job.shadow, "should_fire", lambda _ctx: False)
    monkeypatch.setattr(football_job.shadow, "run", fake_run)

    assert football_job.main() == 0
    assert called is False
    assert '"status": "idle"' in capsys.readouterr().out


def test_football_job_runs_due_work(monkeypatch, capsys):
    received = {}

    def fake_run(ctx):
        received.update(ctx)
        return {"artifact": {"status": "ok"}}

    monkeypatch.setattr(football_job.shadow, "should_fire", lambda _ctx: True)
    monkeypatch.setattr(football_job.shadow, "run", fake_run)

    assert football_job.main() == 0
    assert received["input"]["max_fixtures"] == 60
    assert '"status": "ok"' in capsys.readouterr().out


def test_sqlite_backup_is_consistent_and_prunes_old_archives(tmp_path):
    root = tmp_path / "app"
    source = root / "tennis" / "data" / "tennis_shadow.db"
    source.parent.mkdir(parents=True)
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE picks (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO picks (name) VALUES ('Alpha')")

    output = tmp_path / "backups"
    now = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    archive, count = backup.create_archive(output, root=root, now=now)

    assert count == 1
    assert backup.verify_archive(archive) == 1
    assert archive.name == "betboy-sqlite-20300102T030405Z.zip"
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(tmp_path / "restored")
    restored = tmp_path / "restored" / "tennis" / "data" / "tennis_shadow.db"
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT name FROM picks").fetchone()[0] == "Alpha"

    old = output / "betboy-sqlite-20291201T000000Z.zip"
    old.write_bytes(b"old")
    old_timestamp = datetime(2029, 12, 1, tzinfo=timezone.utc).timestamp()
    old.touch()
    import os

    os.utime(old, (old_timestamp, old_timestamp))
    assert backup.prune_archives(output, retention_days=14, now=now) == 1
    assert not old.exists()


def test_backup_verifier_rejects_an_invalid_sqlite_member(tmp_path):
    archive = tmp_path / "invalid.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("runtime_state/api_budget.db", b"not a database")

    import pytest

    with pytest.raises(RuntimeError, match="not restorable"):
        backup.verify_archive(archive)
