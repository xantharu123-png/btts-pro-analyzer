from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import backup_runtime_databases as backup
from scripts import migrate_challenge_ledgers as challenge_migration
from scripts import manage_challenge_integrity_key as key_manager
from scripts import run_football_shadow_due as football_job
from challenge_store import FINANCIAL_ZERO_HASH, _legacy_financial_record_hash


EXPECTED_TIMERS = (
    "betboy-wettfinder.timer",
    "betboy-football-shadow.timer",
    "betboy-tennis.timer",
    "betboy-esports.timer",
    "betboy-redcard-settlement.timer",
    "betboy-redcard-history.timer",
    "betboy-backup.timer",
)


def _shell_function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index("\n}\n", start)
    return source[start:end]


def _shell_python_heredoc(source: str, function_name: str) -> str:
    function = _shell_function(source, function_name)
    start = function.index("<<'PY'\n") + len("<<'PY'\n")
    end = function.index("\nPY", start)
    return function[start:end] + "\n"


def _bash_executable() -> str | None:
    discovered = shutil.which("bash")
    if discovered:
        return discovered
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        candidate = Path(program_files) / "Git" / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    return None


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
    for source in (update, bootstrap):
        assert 'systemctl start "${BETBOY_TIMERS[@]}"' in source
        assert (
            'systemctl enable betboy-app.service "${BETBOY_TIMERS[@]}"'
            in source
        )
        assert 'systemctl enable --now "${BETBOY_TIMERS[@]}"' not in source


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
    assert '--verify-only "${work_archive}" --recovery-mode' in update
    assert '"database_count": len(inventory)' in update
    assert 'readonly RECOVERY_BACKUP_DIR=/var/backups/betboy-update' in update
    assert "FAIL-CLOSED: the target migration/app may have touched databases" in update


def test_resume_target_is_pinned_across_both_fixed_url_fetches():
    root = Path(__file__).resolve().parents[1]
    update = (root / "deploy" / "update_server.sh").read_text(encoding="utf-8")
    trusted = _shell_function(update, "prepare_trusted_tree")
    checkout = _shell_function(update, "prepare_app_checkout")

    first_snapshot = trusted.index('AUTHORIZED_MAIN_HEAD="${fetched_head}"')
    marker_check = trusted.index('if [[ -e "${LEDGER_MIGRATION_MARKER}"')
    resume_check = trusted.index('if [[ "${MIGRATION_MARKER_STATUS}" == in_progress ]]')
    exact_target = trusted.index('[[ "${REQUESTED_HEAD}" == "${marker_target}" ]]')
    ancestry = trusted.index('merge-base --is-ancestor', exact_target)
    tip_only = trusted.index('[[ "${fetched_head}" == "${REQUESTED_HEAD}" ]]')
    assert first_snapshot < marker_check < resume_check < exact_target < ancestry < tip_only

    second_fetch = checkout.index(
        'git_betboy fetch --no-tags "${REPOSITORY_URL}" refs/heads/main'
    )
    drift_gate = checkout.index(
        '[[ "${fetched_head}" == "${AUTHORIZED_MAIN_HEAD}" ]]', second_fetch
    )
    previous_head = checkout.index('PREVIOUS_HEAD=$(git_betboy rev-parse HEAD)')
    predecessor_or_target = checkout.index(
        '[[ "${PREVIOUS_HEAD}" == "${TARGET_HEAD}"', previous_head
    )
    assert second_fetch < drift_gate < previous_head < predecessor_or_target
    assert 'Migration is incomplete; explicitly resume ${marker_target}' in trusted
    assert "Migration resume target is not an ancestor of origin/main" in trusted


def test_resume_byte_verifier_accepts_only_predecessor_target_mix(tmp_path):
    root = Path(__file__).resolve().parents[1]
    update = (root / "deploy" / "update_server.sh").read_text(encoding="utf-8")
    verifier = _shell_python_heredoc(update, "verify_resume_app_bytes")
    app = tmp_path / "app"
    app.mkdir()

    previous_bytes = {
        "same.txt": b"same\n",
        "changed.txt": b"previous\n",
        "deleted.txt": b"deleted\n",
    }
    target_bytes = {
        "same.txt": b"same\n",
        "changed.txt": b"target\n",
        "added.txt": b"added\n",
    }

    def manifest(files: dict[str, bytes], absent: set[str]) -> dict[str, object]:
        return {
            "files": {
                name: {
                    "mode": "100644",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
                for name, payload in files.items()
            },
            "must_be_absent": sorted(absent),
        }

    previous_manifest = tmp_path / "previous.json"
    target_manifest = tmp_path / "target.json"
    previous_manifest.write_text(
        json.dumps(manifest(previous_bytes, {"added.txt"})),
        encoding="utf-8",
    )
    target_manifest.write_text(
        json.dumps(manifest(target_bytes, {"deleted.txt"})),
        encoding="utf-8",
    )
    (app / "same.txt").write_bytes(previous_bytes["same.txt"])
    (app / "changed.txt").write_bytes(previous_bytes["changed.txt"])
    (app / "added.txt").write_bytes(target_bytes["added.txt"])

    command = [
        sys.executable,
        "-I",
        "-",
        str(app),
        str(previous_manifest),
        str(target_manifest),
    ]
    accepted = subprocess.run(
        command,
        input=verifier,
        check=False,
        capture_output=True,
        text=True,
    )
    assert accepted.returncode == 0, accepted.stderr

    (app / "changed.txt").write_bytes(b"third-party bytes\n")
    rejected = subprocess.run(
        command,
        input=verifier,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode != 0
    assert "neither predecessor nor target" in rejected.stderr


def test_atomic_root_installer_is_identical_and_durable_in_both_paths():
    root = Path(__file__).resolve().parents[1]
    update = (root / "deploy" / "update_server.sh").read_text(encoding="utf-8")
    bootstrap = (root / "deploy" / "bootstrap_server.sh").read_text(
        encoding="utf-8"
    )
    update_installer = _shell_python_heredoc(update, "install_root_file_atomic")
    bootstrap_installer = _shell_python_heredoc(
        bootstrap, "install_root_file_atomic"
    )

    assert update_installer == bootstrap_installer
    assert "source_info.st_nlink != 1" in update_installer
    assert "os.O_EXCL" in update_installer
    assert "O_NOFOLLOW" in update_installer
    file_fsync = update_installer.index("os.fsync(temporary_fd)")
    publish = update_installer.index("os.replace(temporary, destination)")
    directory_fsync = update_installer.index("os.fsync(directory_fd)")
    cleanup = update_installer.index("temporary.unlink()")
    assert file_fsync < publish < directory_fsync < cleanup
    assert update.count("install_root_file_atomic \\") >= 10
    assert bootstrap.count("install_root_file_atomic \\") >= 7


def test_update_migrates_challenge_ledgers_offline_and_never_rolls_back_migrated_db():
    root = Path(__file__).resolve().parents[1]
    update = (root / "deploy" / "update_server.sh").read_text(
        encoding="utf-8"
    )
    main = update.index('preflight "$@"\nremember_unit_state')
    boundary = update.index("\nprepare_challenge_migration_boundary\n", main)
    backup = update.index("\ncreate_fresh_backup\n", boundary)
    target = update.index(
        'apply_trusted_payload "${TARGET_MANIFEST}" "${TARGET_PAYLOAD}"',
        boundary,
    )
    migration = update.index("\nmigrate_challenge_integrity_offline\n", target)
    backup_probe = update.index("\nverify_backup_service_migration\n", migration)
    app_started = update.index("\nNEW_APP_STARTED=1\n", backup_probe)
    start = update.index("systemctl start betboy-app.service", app_started)

    assert (
        boundary
        < backup
        < target
        < migration
        < backup_probe
        < app_started
        < start
    )
    assert '|| "${NEW_APP_STARTED}" == 1' in update
    assert "the target migration/app may have touched databases" in update
    assert "--offline-confirmed" in update
    assert "--migration-policy-file" in update
    assert "--verify-only" in update
    assert "scripts/migrate_challenge_ledgers.py" in update
    assert "challenge-ledger-v2-migrated.json" in update
    assert "manage_challenge_migration_marker.py" in update
    assert "complete" in update
    assert (
        "verify_no_betboy_processes\n"
        "verify_backup_service_migration\n\nNEW_APP_STARTED=1"
    ) in update
    boundary_body = update.split(
        "prepare_challenge_migration_boundary() {", 1
    )[1].split("\n}", 1)[0]
    prepare_marker = boundary_body.index("prepare \\")
    migration_flag = boundary_body.index("DATABASE_MIGRATION_STARTED=1")
    assert prepare_marker < migration_flag
    migration_body = _shell_function(update, "migrate_challenge_integrity_offline")
    every_run_flag = migration_body.index("DATABASE_MIGRATION_STARTED=1")
    migration_helper = migration_body.index("scripts/migrate_challenge_ledgers.py")
    assert every_run_flag < migration_helper
    stop_app = update.index("systemctl stop betboy-app.service", main)
    disabled = update.index("\ndisable_runtime_autostart\n", stop_app)
    assert stop_app < disabled < boundary < backup < target
    assert 'systemctl enable betboy-app.service "${BETBOY_TIMERS[@]}"' in update
    disable_body = _shell_function(update, "disable_runtime_autostart")
    assert "persist_runtime_autostart_disabled" in disable_body


def test_deploy_paths_persistently_disable_every_runtime_unit_fail_closed():
    import pytest

    root = Path(__file__).resolve().parents[1]
    bash = _bash_executable()
    if bash is None:
        pytest.skip("bash is required to exercise the deployment shell function")

    expected_units = (
        "betboy-app.service",
        *EXPECTED_TIMERS,
        *(timer.removesuffix(".timer") + ".service" for timer in EXPECTED_TIMERS),
    )
    for script_name in ("update_server.sh", "bootstrap_server.sh"):
        source = (root / "deploy" / script_name).read_text(encoding="utf-8")
        function = _shell_function(source, "persist_runtime_autostart_disabled")
        harness = f"""
set -u
exec 3>&1
BETBOY_TIMERS=({' '.join(EXPECTED_TIMERS)})
BETBOY_WORKERS=({' '.join(timer.removesuffix('.timer') + '.service' for timer in EXPECTED_TIMERS)})
declare -A states=()
for unit in betboy-app.service "${{BETBOY_TIMERS[@]}}" "${{BETBOY_WORKERS[@]}}"; do
    states["${{unit}}"]="enabled"
done
systemctl() {{
    local action="$1"
    shift
    if [[ "${{action}}" == disable ]]; then
        for unit in "$@"; do
            printf 'disable:%s\n' "${{unit}}" >&3
            if [[ "${{unit}}" != "${{BLOCK_UNIT:-}}" ]]; then
                if [[ "${{unit}}" == betboy-app.service || "${{unit}}" == *.timer ]]; then
                    states["${{unit}}"]="disabled"
                else
                    states["${{unit}}"]="static"
                fi
            fi
        done
        return 0
    fi
    if [[ "${{action}}" == is-enabled ]]; then
        printf 'check:%s\n' "$1" >&3
        [[ "$1" != "${{STATE_ERROR_UNIT:-}}" ]] || return 1
        printf '%s\n' "${{states[$1]}}"
        [[ "${{states[$1]}}" == enabled ]]
        return $?
    fi
    return 99
}}
durable_os_sync() {{ printf 'sync\n' >&3; }}
log() {{ printf 'log:%s\n' "$*" >&3; }}
{function}
}}
persist_runtime_autostart_disabled
"""
        completed = subprocess.run(
            [bash],
            input=harness,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        events = completed.stdout.splitlines()
        assert events[: len(expected_units)] == [
            f"disable:{unit}" for unit in expected_units
        ]
        assert events[len(expected_units)] == "sync"
        assert events[len(expected_units) + 1 :] == [
            f"check:{unit}" for unit in expected_units
        ]

        blocked = subprocess.run(
            [bash],
            input=harness,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "BLOCK_UNIT": expected_units[-1]},
        )
        assert blocked.returncode != 0
        assert f"check:{expected_units[-1]}" in blocked.stdout

        errored = subprocess.run(
            [bash],
            input=harness,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "STATE_ERROR_UNIT": expected_units[-1]},
        )
        assert errored.returncode != 0
        assert f"check:{expected_units[-1]}" in errored.stdout


def test_update_failure_and_success_paths_keep_enablement_fail_closed_until_last():
    root = Path(__file__).resolve().parents[1]
    update = (root / "deploy" / "update_server.sh").read_text(encoding="utf-8")
    recovery = _shell_function(update, "recover_update")

    critical_branch = recovery.index(
        '[[ "${DATABASE_MIGRATION_STARTED}" == 1'
    )
    persistent_disable = recovery.index(
        "persist_runtime_autostart_disabled", critical_branch
    )
    inspect_log = recovery.index("Inspect/restore", critical_branch)
    assert critical_branch < persistent_disable < inspect_log

    main = update.index('preflight "$@"\nremember_unit_state')
    app_started = update.index("\nNEW_APP_STARTED=1\n", main)
    app_start = update.index("systemctl start betboy-app.service", app_started)
    app_health = update.index('"${HEALTH_URL}" | grep -qx \'ok\'', app_start)
    timers_start = update.index('systemctl start "${BETBOY_TIMERS[@]}"', app_health)
    final_enable = update.index(
        'systemctl enable betboy-app.service "${BETBOY_TIMERS[@]}"', timers_start
    )
    durable_sync = update.index("durable_os_sync", final_enable)
    final_verify = update.index("\nverify_runtime\n", durable_sync)
    assert (
        app_started
        < app_start
        < app_health
        < timers_start
        < final_enable
        < durable_sync
        < final_verify
    )
    assert "systemctl enable --now" not in update[app_started:]
    verify_runtime = _shell_function(update, "verify_runtime")
    assert 'for worker in "${BETBOY_WORKERS[@]}"' in verify_runtime
    assert '[[ "${state}" == static ]]' in verify_runtime

    remember = _shell_function(update, "remember_unit_state")
    restore = _shell_function(update, "restore_unit_state")
    assert "read_unit_enablement_state" in remember
    assert "read_unit_activity_state" in remember
    assert "systemctl is-enabled --quiet" not in restore
    assert "systemctl is-active --quiet" not in restore
    assert '[[ "${state}" == "${expected}" ]] || return 1' in restore


def test_bootstrap_gates_legacy_units_before_marker_and_recovers_fail_closed():
    root = Path(__file__).resolve().parents[1]
    bootstrap = (root / "deploy" / "bootstrap_server.sh").read_text(
        encoding="utf-8"
    )

    lock = bootstrap.index("\nacquire_deploy_lock\n")
    trap = bootstrap.index("trap 'recover_bootstrap \"$?\"' EXIT", lock)
    early_gate = bootstrap.index("\nforce_runtime_fail_closed \\\n", trap)
    remote = bootstrap.index("\nREMOTE_MAIN=", early_gate)
    assert lock < trap < early_gate < remote

    install_units = bootstrap.index("\ninstall_trusted_units_and_tools\n")
    daemon_reload = bootstrap.index("\nsystemctl daemon-reload\n", install_units)
    verify_units = bootstrap.index("\nverify_no_unit_dropin_paths\n", daemon_reload)
    marker = bootstrap.index(
        '/usr/bin/python3 -I "${TRUSTED_MIGRATION_MARKER_HELPER}"', verify_units
    )
    assert install_units < daemon_reload < verify_units < marker

    recovery = _shell_function(bootstrap, "recover_bootstrap")
    assert "force_runtime_fail_closed" in recovery
    fail_closed = _shell_function(bootstrap, "force_runtime_fail_closed")
    assert 'systemctl stop "${BETBOY_TIMERS[@]}"' in fail_closed
    assert 'systemctl stop "${BETBOY_WORKERS[@]}"' in fail_closed
    assert "systemctl stop betboy-app.service" in fail_closed
    assert "persist_runtime_autostart_disabled" in fail_closed
    assert "check_no_betboy_processes" in fail_closed

    app_start = bootstrap.index("systemctl start betboy-app.service", marker)
    app_health = bootstrap.index("/_stcore/health | grep -qx 'ok'", app_start)
    timers_start = bootstrap.index(
        'systemctl start "${BETBOY_TIMERS[@]}"', app_health
    )
    final_enable = bootstrap.index(
        'systemctl enable betboy-app.service "${BETBOY_TIMERS[@]}"', timers_start
    )
    durable_sync = bootstrap.index("durable_os_sync", final_enable)
    complete = bootstrap.index("\nBOOTSTRAP_COMPLETE=1\n", durable_sync)
    assert app_start < app_health < timers_start < final_enable < durable_sync < complete


LEGACY_MAIN_SETTINGS_SQL = (
    "CREATE TABLE challenge_settings (\n"
    "                    id INTEGER PRIMARY KEY CHECK (id = 1),\n"
    "                    starting_balance_cents INTEGER NOT NULL CHECK (starting_balance_cents >= 0),\n"
    "                    current_balance_cents INTEGER NOT NULL CHECK (current_balance_cents >= 0),\n"
    "                    target_balance_cents INTEGER NOT NULL CHECK (target_balance_cents > 0),\n"
    "                    updated_at TEXT NOT NULL\n"
    "                , stake_fraction_bps INTEGER NOT NULL DEFAULT 10000\n"
    "                        CHECK (stake_fraction_bps BETWEEN 500 AND 10000))"
)
LEGACY_MAIN_TICKETS_SQL = (
    "CREATE TABLE challenge_tickets (\n"
    "                    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "                    analysis_date TEXT NOT NULL,\n"
    "                    created_at TEXT NOT NULL,\n"
    "                    quote_verified_at TEXT NOT NULL,\n"
    "                    settled_at TEXT,\n"
    "                    status TEXT NOT NULL CHECK (status IN ('PENDING', 'WON', 'LOST', 'VOID')),\n"
    "                    stake_cents INTEGER NOT NULL CHECK (stake_cents > 0),\n"
    "                    payout_cents INTEGER NOT NULL DEFAULT 0 CHECK (payout_cents >= 0),\n"
    "                    total_odds REAL NOT NULL CHECK (total_odds > 1),\n"
    "                    joint_probability REAL NOT NULL CHECK (joint_probability >= 0 AND joint_probability <= 1),\n"
    "                    expected_roi REAL NOT NULL,\n"
    "                    legs_json TEXT NOT NULL\n"
    "                )"
)
LEGACY_MAIN_INDEX_SQL = (
    "CREATE UNIQUE INDEX idx_challenge_daily_ticket\n"
    "                ON challenge_tickets(analysis_date)\n"
    "                WHERE status != 'VOID'\n"
    "                "
)

LEGACY_V0_SCHEMA_FIXTURES = json.loads(
    (Path(__file__).with_name("legacy_v0_schema_manifests.json")).read_text(
        encoding="utf-8"
    )
)


def _create_legacy_schema_from_manifest(
    path: Path,
    objects: list[list[object]],
    *,
    reverse_within_type: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    order = {"table": 0, "index": 1, "trigger": 2}
    executable = [item for item in objects if isinstance(item[3], str)]
    executable.sort(
        key=lambda item: (
            order[str(item[0])],
            str(item[1]) if not reverse_within_type else "",
        ),
        reverse=reverse_within_type,
    )
    if reverse_within_type:
        executable.sort(key=lambda item: order[str(item[0])])
    with sqlite3.connect(path) as connection:
        for _object_type, _name, _table, sql in executable:
            connection.execute(str(sql))


def _legacy_schema_digest(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        return challenge_migration._legacy_v0_schema_sha256(connection)


def _write_legacy_challenge_database(
    path: Path,
    *,
    settings_sql: str = LEGACY_MAIN_SETTINGS_SQL,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(settings_sql)
        connection.execute(LEGACY_MAIN_TICKETS_SQL)
        connection.execute(LEGACY_MAIN_INDEX_SQL)
        connection.execute(
            "INSERT INTO challenge_settings "
            "(id, starting_balance_cents, current_balance_cents, "
            "target_balance_cents, updated_at, stake_fraction_bps) "
            "VALUES (1, 10000, 10000, 1500000, 'legacy', 10000)"
        )
        connection.commit()


def test_legacy_fixture_matches_one_exact_production_v0_ddl(tmp_path):
    database = tmp_path / "challenge.db"
    _write_legacy_challenge_database(database)
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        digest = challenge_migration._legacy_v0_schema_sha256(connection)
    assert digest == "4f4bdd6c490d395ab7e5f0a0dd0ddacc97c1364103cdbef3e57df91c33c68727"


def test_all_five_observed_production_v0_manifests_are_exact_and_accepted(tmp_path):
    schemas = LEGACY_V0_SCHEMA_FIXTURES["schemas"]
    assert LEGACY_V0_SCHEMA_FIXTURES["observed_at"] == "2026-08-25"
    assert LEGACY_V0_SCHEMA_FIXTURES["production_database_count"] == 72
    assert len(schemas) == 5
    assert sum(int(schema["count"]) for schema in schemas) == 72
    assert {schema["sha256"] for schema in schemas} == (
        challenge_migration.LEGACY_V0_SCHEMA_SHA256
    )

    for index, schema in enumerate(schemas):
        database = tmp_path / f"schema-{index}.db"
        _create_legacy_schema_from_manifest(database, schema["objects"])
        assert _legacy_schema_digest(database) == schema["sha256"]
        with sqlite3.connect(database) as connection:
            connection.row_factory = sqlite3.Row
            challenge_migration._validate_legacy_v0_schema(connection)


def test_all_five_observed_v0_layouts_complete_the_offline_migration(tmp_path):
    for index, schema in enumerate(LEGACY_V0_SCHEMA_FIXTURES["schemas"]):
        root = tmp_path / f"app-{index}"
        database = root / "challenge_15k.db"
        _create_legacy_schema_from_manifest(database, schema["objects"])
        key = tmp_path / f"challenge-ledger-{index}.key"
        key.write_bytes((f"{index + 1:x}" * 64).encode("ascii") + b"\n")
        policy = _write_legacy_migration_policy(
            tmp_path / f"migration-{index}.json",
            root,
        )

        receipt = challenge_migration.migrate_challenge_ledgers(
            root,
            key,
            migration_policy=policy,
        )

        assert receipt["database_count"] == 1
        assert challenge_migration._preflight_database(
            database,
            allow_legacy_v0=False,
        ) == "v2"


def test_legacy_schema_digest_is_creation_order_independent(tmp_path):
    schema = LEGACY_V0_SCHEMA_FIXTURES["schemas"][0]
    normal = tmp_path / "normal.db"
    reversed_database = tmp_path / "reversed.db"
    _create_legacy_schema_from_manifest(normal, schema["objects"])
    _create_legacy_schema_from_manifest(
        reversed_database,
        schema["objects"],
        reverse_within_type=True,
    )
    assert _legacy_schema_digest(normal) == schema["sha256"]
    assert _legacy_schema_digest(reversed_database) == schema["sha256"]


def test_offline_migration_rejects_column_compatible_foreign_ddl(tmp_path):
    import pytest

    root = tmp_path / "app"
    database = root / "challenge_15k.db"
    poisoned = LEGACY_MAIN_SETTINGS_SQL.replace(
        "current_balance_cents >= 0",
        "current_balance_cents = 10000",
    )
    _write_legacy_challenge_database(database, settings_sql=poisoned)
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"ac" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)

    with pytest.raises(RuntimeError, match="DDL.*production v0 schema"):
        challenge_migration.migrate_challenge_ledgers(
            root,
            key,
            migration_policy=policy,
        )


def test_legacy_v0_allowlist_rejects_same_columns_with_changed_semantics(tmp_path):
    import pytest

    variants = {
        "default": LEGACY_MAIN_SETTINGS_SQL.replace(
            "DEFAULT 10000",
            "DEFAULT 9000",
        ),
        "collation": LEGACY_MAIN_SETTINGS_SQL.replace(
            "updated_at TEXT NOT NULL",
            "updated_at TEXT COLLATE NOCASE NOT NULL",
        ),
        "strict": LEGACY_MAIN_SETTINGS_SQL + " STRICT",
        "without-rowid": LEGACY_MAIN_SETTINGS_SQL + " WITHOUT ROWID",
    }
    for name, settings_sql in variants.items():
        database = tmp_path / f"{name}.db"
        _write_legacy_challenge_database(database, settings_sql=settings_sql)
        with sqlite3.connect(database) as connection:
            connection.row_factory = sqlite3.Row
            with pytest.raises(RuntimeError, match="DDL.*production v0 schema"):
                challenge_migration._validate_legacy_v0_schema(connection)


def test_legacy_v0_allowlist_does_not_hide_sqlitex_named_objects(tmp_path):
    import pytest

    database = tmp_path / "challenge.db"
    _write_legacy_challenge_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sqlitex_hidden (payload TEXT)")
        connection.row_factory = sqlite3.Row
        with pytest.raises(RuntimeError, match="DDL.*production v0 schema"):
            challenge_migration._validate_legacy_v0_schema(connection)


def test_offline_migration_rejects_application_root_through_symlink(tmp_path):
    import pytest

    actual_root = tmp_path / "actual-app"
    _write_legacy_challenge_database(actual_root / "challenge_15k.db")
    linked_root = tmp_path / "linked-app"
    try:
        linked_root.symlink_to(actual_root, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"ae" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", actual_root)

    with pytest.raises(RuntimeError, match="Application root.*symlink"):
        challenge_migration.migrate_challenge_ledgers(
            linked_root,
            key,
            migration_policy=policy,
        )


def test_offline_migration_rejects_schema_free_known_challenge_file_atomically(
    tmp_path,
):
    import pytest

    root = tmp_path / "app"
    database = root / "challenge_15k.db"
    poisoned = root / "challenge_sessions" / "poisoned.db"
    _write_legacy_challenge_database(database)
    poisoned.parent.mkdir(parents=True)
    with sqlite3.connect(poisoned) as connection:
        connection.execute("CREATE TABLE unrelated (payload TEXT)")
    before = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (database, poisoned)
    }
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"af" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)

    with pytest.raises(RuntimeError, match="missing challenge_settings"):
        challenge_migration.migrate_challenge_ledgers(
            root,
            key,
            migration_policy=policy,
        )

    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (database, poisoned)
    } == before


def test_production_legacy_path_inventory_fails_on_missing_or_extra_database(
    tmp_path,
    monkeypatch,
):
    import pytest

    root = tmp_path / "app"
    root.mkdir()
    database = root / "challenge_15k.db"
    canonical = json.dumps(
        ["challenge_15k.db"],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    monkeypatch.setattr(challenge_migration, "PRODUCTION_APPLICATION_ROOT", root)
    monkeypatch.setattr(challenge_migration, "PRODUCTION_LEGACY_V0_DATABASE_COUNT", 1)
    monkeypatch.setattr(
        challenge_migration,
        "PRODUCTION_LEGACY_V0_PATH_INVENTORY_SHA256",
        hashlib.sha256(canonical).hexdigest(),
    )

    challenge_migration._validate_production_legacy_path_inventory(
        root,
        [database],
    )
    with pytest.raises(RuntimeError, match="inventory changed"):
        challenge_migration._validate_production_legacy_path_inventory(
            root,
            [database, root / "challenge_sessions" / "extra.db"],
        )
    with pytest.raises(RuntimeError, match="inventory changed"):
        challenge_migration._validate_production_legacy_path_inventory(root, [])


def test_offline_migration_rejects_preseeded_legacy_sequence(tmp_path):
    import pytest

    root = tmp_path / "app"
    database = root / "challenge_15k.db"
    _write_legacy_challenge_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES('challenge_tickets', 999)"
        )
        connection.commit()
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"ad" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)

    with pytest.raises(RuntimeError, match="sequence is invalid"):
        challenge_migration.migrate_challenge_ledgers(
            root,
            key,
            migration_policy=policy,
        )


def test_legacy_v0_sequence_inventory_rejects_duplicates_and_negative_ids(tmp_path):
    import pytest

    duplicate = tmp_path / "duplicate.db"
    _write_legacy_challenge_database(duplicate)
    with sqlite3.connect(duplicate) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES('challenge_tickets', 0)"
        )
        connection.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES('challenge_tickets', 1)"
        )
        with pytest.raises(RuntimeError, match="sequence inventory is ambiguous"):
            challenge_migration._validate_legacy_v0_sequences(
                connection,
                {"challenge_tickets"},
            )

    negative = tmp_path / "negative.db"
    _write_legacy_challenge_database(negative)
    with sqlite3.connect(negative) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(
            """
            INSERT INTO challenge_tickets (
                id, analysis_date, created_at, quote_verified_at, settled_at,
                status, stake_cents, payout_cents, total_odds,
                joint_probability, expected_roi, legs_json
            ) VALUES (
                -1, '2026-08-25', 'legacy', 'legacy', NULL,
                'PENDING', 100, 0, 2.0, 0.6, 0.2, '[]'
            )
            """
        )
        with pytest.raises(RuntimeError, match="identifier state is invalid"):
            challenge_migration._validate_legacy_v0_sequences(
                connection,
                {"challenge_tickets"},
            )


def _write_legacy_migration_policy(path: Path, root: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "status": "in_progress",
                "mode": "legacy-v0",
                "application_root": str(root.resolve()),
                "previous_head": "1" * 40,
                "previous_writer_blob": (
                    "f96d8b6c340c184e90d644cc310efebf963de1ad"
                ),
                "target_head": "2" * 40,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_completed_migration_marker(path: Path, root: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "status": "complete",
                "mode": "legacy-v0",
                "application_root": str(root.resolve()),
                "previous_head": "1" * 40,
                "previous_writer_blob": (
                    "f96d8b6c340c184e90d644cc310efebf963de1ad"
                ),
                "target_head": "2" * 40,
                "completed_at": "2030-01-01T00:00:00+00:00",
                "migration_receipt": {
                    "contract_version": 1,
                    "mode": "legacy-v0",
                    "database_count": 1,
                    "databases": [
                        {
                            "path": "challenge_sessions/account.db",
                            "checkpoint_mac": "a" * 64,
                            "source": "v0",
                        }
                    ],
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_offline_challenge_migration_accepts_v0_and_reopens_without_operator_flag(
    tmp_path,
):
    root = tmp_path / "app"
    database = root / "challenge_sessions" / "account.db"
    _write_legacy_challenge_database(database)
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"ab" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)

    import pytest

    with pytest.raises(RuntimeError, match="migration policy|verify-only"):
        challenge_migration.migrate_challenge_ledgers(root, key)
    receipt = challenge_migration.migrate_challenge_ledgers(
        root,
        key,
        migration_policy=policy,
    )
    assert receipt["database_count"] == 1
    assert receipt["mode"] == "legacy-v0"

    with sqlite3.connect(database) as connection:
        version = connection.execute(
            "SELECT financial_chain_version FROM challenge_settings WHERE id=1"
        ).fetchone()[0]
        checkpoint_count = connection.execute(
            "SELECT COUNT(*) FROM challenge_integrity_checkpoint"
        ).fetchone()[0]
    assert version == 2
    assert checkpoint_count == 1
    assert "BETBOY_LEDGER_CHECKPOINT_MIGRATION" not in os.environ


def test_offline_challenge_migration_rejects_arbitrarily_named_trigger(tmp_path):
    import pytest

    root = tmp_path / "app"
    database = root / "challenge_sessions" / "account.db"
    _write_legacy_challenge_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TRIGGER poison AFTER UPDATE ON challenge_settings
            BEGIN
                UPDATE challenge_settings
                SET target_balance_cents=1 WHERE id=1;
            END
            """
        )
        connection.commit()
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"aa" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)

    with pytest.raises(RuntimeError, match="allowlisted legacy v0 schema"):
        challenge_migration.migrate_challenge_ledgers(
            root,
            key,
            migration_policy=policy,
        )


def test_integrity_key_is_published_once_and_reused_byte_for_byte(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    key = tmp_path / "challenge-ledger-hmac.key"
    marker = tmp_path / "migration-marker.json"

    first = key_manager.ensure_integrity_key(key, root, marker)
    first_info = key.stat()
    second = key_manager.ensure_integrity_key(key, root, marker)

    assert len(first) == 65 and first.endswith(b"\n")
    assert second == first
    assert key.stat().st_ino == first_info.st_ino


def test_integrity_key_is_never_recreated_beside_marker_or_v2_database(tmp_path):
    import pytest

    marker_root = tmp_path / "marker-case"
    marker_root.mkdir()
    marker = marker_root / "migration-marker.json"
    marker.write_text("{}\n", encoding="utf-8")
    marker_key = marker_root / "challenge-ledger-hmac.key"
    with pytest.raises(RuntimeError, match="restore the original key"):
        key_manager.ensure_integrity_key(marker_key, marker_root, marker)
    assert not marker_key.exists()

    database_root = tmp_path / "database-case"
    database_root.mkdir()
    database = database_root / "challenge_15k.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE challenge_settings (
                id INTEGER PRIMARY KEY,
                financial_chain_version INTEGER,
                financial_anchor_hash TEXT,
                settlement_chain_version INTEGER,
                settlement_anchor_hash TEXT
            )
            """
        )
        connection.execute(
            "CREATE TABLE challenge_integrity_checkpoint (id INTEGER PRIMARY KEY)"
        )
    database_key = database_root / "challenge-ledger-hmac.key"
    with pytest.raises(RuntimeError, match="HMAC-era|checkpoint"):
        key_manager.ensure_integrity_key(
            database_key,
            database_root,
            database_root / "absent-marker.json",
        )
    assert not database_key.exists()


def test_fresh_install_key_refuses_even_legacy_challenge_database(tmp_path):
    import pytest

    root = tmp_path / "app"
    _write_legacy_challenge_database(root / "challenge_15k.db")
    key = tmp_path / "challenge-ledger-hmac.key"

    with pytest.raises(RuntimeError, match="pre-existing challenge database"):
        key_manager.ensure_integrity_key(
            key,
            root,
            tmp_path / "absent-marker.json",
            fresh_install=True,
        )
    assert not key.exists()


def test_invalid_or_linked_existing_key_is_not_repaired(tmp_path):
    import pytest

    root = tmp_path / "app"
    root.mkdir()
    marker = tmp_path / "absent-marker.json"
    invalid = tmp_path / "invalid.key"
    invalid.write_bytes(b"broken\r\n")
    invalid.chmod(0o600)
    before = invalid.read_bytes()
    with pytest.raises(RuntimeError, match="invalid format"):
        key_manager.ensure_integrity_key(invalid, root, marker)
    assert invalid.read_bytes() == before

    source = tmp_path / "linked-source.key"
    source.write_bytes(b"ab" * 32 + b"\n")
    source.chmod(0o600)
    linked = tmp_path / "linked.key"
    os.link(source, linked)
    with pytest.raises(RuntimeError, match="one regular file"):
        key_manager.ensure_integrity_key(linked, root, marker)
    assert linked.samefile(source)


def test_key_no_replace_loser_preserves_concurrent_winner(tmp_path, monkeypatch):
    root = tmp_path / "app"
    root.mkdir()
    marker = tmp_path / "absent-marker.json"
    key = tmp_path / "challenge-ledger-hmac.key"
    winner = b"cd" * 32 + b"\n"

    def publish_winner(_source, destination, *, allow_link_fallback):
        assert allow_link_fallback is True
        Path(destination).write_bytes(winner)
        Path(destination).chmod(0o600)
        return False

    monkeypatch.setattr(key_manager, "_rename_no_replace", publish_winner)
    assert key_manager.ensure_integrity_key(key, root, marker) == winner
    assert key.read_bytes() == winner


def test_key_candidate_is_removed_after_interrupted_write(tmp_path, monkeypatch):
    import pytest

    root = tmp_path / "app"
    root.mkdir()
    key = tmp_path / "challenge-ledger-hmac.key"

    def interrupted_write(_descriptor, _payload):
        raise OSError("simulated interrupted key write")

    monkeypatch.setattr(key_manager.os, "write", interrupted_write)
    with pytest.raises(OSError, match="interrupted"):
        key_manager.ensure_integrity_key(
            key,
            root,
            tmp_path / "absent-marker.json",
        )
    assert not key.exists()
    assert not list(tmp_path.glob(".challenge-ledger-hmac.key.*.partial"))


def test_production_key_publication_never_uses_hardlink_fallback(
    tmp_path,
    monkeypatch,
):
    import pytest

    if os.name == "nt":
        with pytest.raises(RuntimeError, match="no-replace"):
            key_manager._rename_no_replace(
                tmp_path / "source",
                tmp_path / "destination",
                allow_link_fallback=False,
            )
        return

    class RenameUnavailable:
        argtypes = None
        restype = None

        def __call__(self, *_args):
            return -1

    class FakeLibc:
        renameat2 = RenameUnavailable()

    monkeypatch.setattr(key_manager.ctypes, "CDLL", lambda *_a, **_k: FakeLibc())
    monkeypatch.setattr(key_manager.ctypes, "get_errno", lambda: key_manager.errno.ENOSYS)
    with pytest.raises(RuntimeError, match="no-replace"):
        key_manager._rename_no_replace(
            tmp_path / "source",
            tmp_path / "destination",
            allow_link_fallback=False,
        )


def test_offline_challenge_migration_rejects_v2_without_checkpoint_even_with_flag(
    tmp_path,
):
    import pytest

    root = tmp_path / "app"
    database = root / "challenge_sessions" / "account.db"
    _write_legacy_challenge_database(database)
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"cd" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)
    assert challenge_migration.migrate_challenge_ledgers(
        root,
        key,
        migration_policy=policy,
    )["database_count"] == 1
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE challenge_integrity_checkpoint")
        connection.commit()

    with pytest.raises(RuntimeError, match="v2.*missing.*checkpoint"):
        challenge_migration.migrate_challenge_ledgers(root, key)


def test_offline_challenge_migration_preflights_every_db_before_first_write(
    tmp_path,
):
    import pytest

    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"ef" * 32 + b"\n")
    target_root = tmp_path / "target"
    untouched_legacy = target_root / "challenge_sessions" / "a-legacy.db"
    _write_legacy_challenge_database(untouched_legacy)

    prepared_root = tmp_path / "prepared"
    rolled_back = prepared_root / "challenge_sessions" / "z-rolled-back.db"
    _write_legacy_challenge_database(rolled_back)
    prepared_policy = _write_legacy_migration_policy(
        tmp_path / "prepared-migration.json",
        prepared_root,
    )
    assert challenge_migration.migrate_challenge_ledgers(
        prepared_root,
        key,
        migration_policy=prepared_policy,
    )["database_count"] == 1
    with sqlite3.connect(rolled_back) as connection:
        connection.execute("DROP TABLE challenge_integrity_checkpoint")
        connection.commit()
    moved = target_root / "challenge_sessions" / rolled_back.name
    with sqlite3.connect(rolled_back) as source, sqlite3.connect(moved) as target:
        source.backup(target)

    target_policy = _write_legacy_migration_policy(
        tmp_path / "target-migration.json",
        target_root,
    )
    with pytest.raises(RuntimeError, match="v2.*missing.*checkpoint"):
        challenge_migration.migrate_challenge_ledgers(
            target_root,
            key,
            migration_policy=target_policy,
        )

    with sqlite3.connect(untouched_legacy) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(challenge_settings)")
        }
    assert "financial_chain_version" not in columns


def test_offline_challenge_migration_semantically_preflights_every_v0_db(
    tmp_path,
):
    import pytest

    root = tmp_path / "app"
    valid = root / "challenge_sessions" / "a-valid.db"
    invalid = root / "challenge_sessions" / "z-invalid.db"
    _write_legacy_challenge_database(valid)
    _write_legacy_challenge_database(invalid)
    with sqlite3.connect(invalid) as connection:
        connection.execute(
            "UPDATE challenge_settings SET current_balance_cents=10000.5 WHERE id=1"
        )
        connection.commit()
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"fe" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)

    with pytest.raises(RuntimeError, match="SQLite INTEGER|[Ll]egacy"):
        challenge_migration.migrate_challenge_ledgers(
            root,
            key,
            migration_policy=policy,
        )

    with sqlite3.connect(valid) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(challenge_settings)")
        }
    assert "financial_chain_version" not in columns


def test_offline_challenge_migration_resumes_a_valid_v0_v2_mix(tmp_path):
    root = tmp_path / "app"
    legacy_path = root / "challenge_sessions" / "a-legacy.db"
    current_path = root / "challenge_sessions" / "z-current.db"
    _write_legacy_challenge_database(legacy_path)
    _write_legacy_challenge_database(current_path)
    legacy_copy = tmp_path / "legacy-copy.db"
    backup.backup_database(legacy_path, legacy_copy)
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"de" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)
    assert challenge_migration.migrate_challenge_ledgers(
        root,
        key,
        migration_policy=policy,
    )["database_count"] == 2
    backup.backup_database(legacy_copy, legacy_path)

    receipt = challenge_migration.migrate_challenge_ledgers(
        root,
        key,
        migration_policy=policy,
    )

    assert receipt["database_count"] == 2
    assert {entry["source"] for entry in receipt["databases"]} == {"v0", "v2"}


def test_offline_challenge_migration_rejects_public_sha_v1_downgrade(tmp_path):
    import pytest

    root = tmp_path / "app"
    database = root / "challenge_sessions" / "account.db"
    _write_legacy_challenge_database(database)
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"12" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)
    challenge_migration.migrate_challenge_ledgers(
        root,
        key,
        migration_policy=policy,
    )

    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("DROP TRIGGER challenge_transactions_no_update")
        connection.execute("DROP TRIGGER challenge_financial_anchor_immutable")
        row = connection.execute(
            "SELECT * FROM challenge_transactions WHERE id=1"
        ).fetchone()
        digest = _legacy_financial_record_hash(
            created_at=str(row["created_at"]),
            kind=str(row["kind"]),
            amount_cents=int(row["amount_cents"]),
            balance_after_cents=int(row["balance_after_cents"]),
            ticket_id=None,
            note=row["note"],
            previous_hash=FINANCIAL_ZERO_HASH,
            chain_version=1,
        )
        connection.execute(
            """
            UPDATE challenge_transactions
            SET chain_version=1, previous_hash=?, record_hash=? WHERE id=1
            """,
            (FINANCIAL_ZERO_HASH, digest),
        )
        connection.execute(
            """
            UPDATE challenge_settings
            SET financial_chain_version=1, financial_anchor_hash=? WHERE id=1
            """,
            (digest,),
        )
        connection.execute("DROP TABLE challenge_integrity_checkpoint")
        connection.commit()

    with pytest.raises(RuntimeError, match="v1|legacy financial version"):
        challenge_migration.migrate_challenge_ledgers(
            root,
            key,
            migration_policy=policy,
        )


def test_legacy_migration_never_signs_fractional_integer_storage(tmp_path):
    import pytest

    root = tmp_path / "app"
    database = root / "challenge_sessions" / "account.db"
    _write_legacy_challenge_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE challenge_settings SET current_balance_cents=10000.5 WHERE id=1"
        )
        assert connection.execute(
            "SELECT typeof(current_balance_cents) FROM challenge_settings WHERE id=1"
        ).fetchone()[0] == "real"
        connection.commit()
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"34" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)

    with pytest.raises(RuntimeError, match="SQLite INTEGER|[Ll]egacy"):
        challenge_migration.migrate_challenge_ledgers(
            root,
            key,
            migration_policy=policy,
        )
    with sqlite3.connect(database) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(challenge_settings)")
        }
    assert "financial_chain_version" not in columns


def test_root_migration_marker_is_monotonic_and_binds_first_rollout(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    marker = tmp_path / "challenge-ledger-v2-migrated.json"
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "mode": "legacy-v0",
                "database_count": 1,
                "databases": [
                    {
                        "path": "challenge_15k.db",
                        "checkpoint_mac": "a" * 64,
                        "source": "v0",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "manage_challenge_migration_marker.py"
    )
    common = [
        sys.executable,
        str(script),
        "--marker",
        str(marker),
        "--application-root",
        str(root),
    ]
    prepared = subprocess.run(
        [
            *common,
            "prepare",
            "--previous-head",
            "1" * 40,
            "--previous-writer-blob",
            "f96d8b6c340c184e90d644cc310efebf963de1ad",
            "--target-head",
            "2" * 40,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert prepared.returncode == 0, prepared.stderr
    assert json.loads(prepared.stdout)["status"] == "in_progress"

    blocked_start = subprocess.run(
        [*common, "require-complete"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert blocked_start.returncode != 0
    assert "not complete" in blocked_start.stderr

    resumed = subprocess.run(
        [
            *common,
            "prepare",
            "--previous-head",
            "3" * 40,
            "--previous-writer-blob",
            "4" * 40,
            "--target-head",
            "2" * 40,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(resumed.stdout)["status"] == "in_progress"

    completed = subprocess.run(
        [
            *common,
            "complete",
            "--target-head",
            "2" * 40,
            "--receipt",
            str(receipt),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    completed_payload = json.loads(marker.read_text(encoding="utf-8"))
    assert completed_payload["status"] == "complete"
    assert completed_payload["previous_head"] == "1" * 40
    assert completed_payload["migration_receipt"]["databases"][0][
        "checkpoint_mac"
    ] == "a" * 64
    allowed_start = subprocess.run(
        [*common, "require-complete"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert allowed_start.returncode == 0, allowed_start.stderr
    assert json.loads(allowed_start.stdout)["status"] == "complete"

    repeated = subprocess.run(
        [
            *common,
            "prepare",
            "--previous-head",
            "3" * 40,
            "--previous-writer-blob",
            "f96d8b6c340c184e90d644cc310efebf963de1ad",
            "--target-head",
            "4" * 40,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert repeated.returncode == 0, repeated.stderr
    assert json.loads(repeated.stdout)["status"] == "complete"
    assert json.loads(marker.read_text(encoding="utf-8")) == completed_payload


def test_fresh_install_marker_refuses_any_preexisting_challenge_database(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    marker = tmp_path / "challenge-ledger-v2-migrated.json"
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "manage_challenge_migration_marker.py"
    )
    command = [
        sys.executable,
        str(script),
        "--marker",
        str(marker),
        "--application-root",
        str(root),
        "fresh",
        "--target-head",
        "2" * 40,
    ]
    created = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    assert created.returncode == 0, created.stderr
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert payload["mode"] == "fresh-install"
    assert payload["migration_receipt"]["database_count"] == 0

    marker.unlink()
    _write_legacy_challenge_database(root / "challenge_15k.db")
    refused = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    assert refused.returncode != 0
    assert "pre-existing challenge database" in refused.stderr
    assert not marker.exists()

    (root / "challenge_15k.db").unlink()
    sqlite3.connect(root / "challenge_15k.db").close()
    schema_free = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    assert schema_free.returncode != 0
    assert "pre-existing challenge database" in schema_free.stderr
    assert not marker.exists()

    (root / "challenge_15k.db").unlink()
    with sqlite3.connect(root / "runtime.db") as connection:
        connection.execute("CREATE TABLE challenge_tickets (id INTEGER PRIMARY KEY)")
    partial = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    assert partial.returncode != 0
    assert "pre-existing challenge database" in partial.stderr
    assert not marker.exists()


def test_migration_marker_cli_rejects_symlinked_marker_and_receipt(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    marker = tmp_path / "challenge-ledger-v2-migrated.json"
    marker_link = tmp_path / "marker-link.json"
    receipt = tmp_path / "receipt.json"
    receipt_link = tmp_path / "receipt-link.json"
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "manage_challenge_migration_marker.py"
    )
    common = [
        sys.executable,
        str(script),
        "--marker",
        str(marker),
        "--application-root",
        str(root),
    ]
    prepared = subprocess.run(
        [
            *common,
            "prepare",
            "--previous-head",
            "1" * 40,
            "--previous-writer-blob",
            "f96d8b6c340c184e90d644cc310efebf963de1ad",
            "--target-head",
            "2" * 40,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert prepared.returncode == 0, prepared.stderr
    receipt.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "mode": "legacy-v0",
                "database_count": 0,
                "databases": [],
            }
        ),
        encoding="utf-8",
    )
    try:
        marker_link.symlink_to(marker)
        receipt_link.symlink_to(receipt)
    except (OSError, NotImplementedError):
        import pytest

        pytest.skip("file symlinks are unavailable")

    status = subprocess.run(
        [
            sys.executable,
            str(script),
            "--marker",
            str(marker_link),
            "--application-root",
            str(root),
            "status",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert status.returncode != 0
    assert "unsafe" in status.stderr

    completed = subprocess.run(
        [
            *common,
            "complete",
            "--target-head",
            "2" * 40,
            "--receipt",
            str(receipt_link),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "cannot be opened safely" in completed.stderr or "unsafe" in completed.stderr
    assert json.loads(marker.read_text(encoding="utf-8"))["status"] == "in_progress"


def test_migration_marker_gate_rejects_symlinked_application_root(tmp_path):
    import pytest

    actual_root = tmp_path / "actual-app"
    actual_root.mkdir()
    linked_root = tmp_path / "linked-app"
    try:
        linked_root.symlink_to(actual_root, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")
    marker = _write_completed_migration_marker(
        tmp_path / "challenge-ledger-v2-migrated.json",
        actual_root,
    )
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "manage_challenge_migration_marker.py"
    )
    gated = subprocess.run(
        [
            sys.executable,
            str(script),
            "--marker",
            str(marker),
            "--application-root",
            str(linked_root),
            "require-complete",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert gated.returncode != 0
    assert "symlink" in gated.stderr


def test_migration_marker_gate_rejects_mismatched_complete_receipt_mode(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    marker = _write_completed_migration_marker(
        tmp_path / "challenge-ledger-v2-migrated.json",
        root,
    )
    payload = json.loads(marker.read_text(encoding="utf-8"))
    payload["migration_receipt"] = {
        "contract_version": 1,
        "mode": "fresh-install",
        "database_count": 0,
        "databases": [],
    }
    marker.write_text(
        json.dumps(payload, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "manage_challenge_migration_marker.py"
    )

    gated = subprocess.run(
        [
            sys.executable,
            str(script),
            "--marker",
            str(marker),
            "--application-root",
            str(root),
            "require-complete",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert gated.returncode != 0
    assert "receipt mode" in gated.stderr


def test_legacy_migration_marker_rejects_fresh_install_receipt(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    marker = tmp_path / "challenge-ledger-v2-migrated.json"
    receipt = tmp_path / "receipt.json"
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "manage_challenge_migration_marker.py"
    )
    common = [
        sys.executable,
        str(script),
        "--marker",
        str(marker),
        "--application-root",
        str(root),
    ]
    prepared = subprocess.run(
        [
            *common,
            "prepare",
            "--previous-head",
            "1" * 40,
            "--previous-writer-blob",
            "f96d8b6c340c184e90d644cc310efebf963de1ad",
            "--target-head",
            "2" * 40,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert prepared.returncode == 0, prepared.stderr
    receipt.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "mode": "fresh-install",
                "database_count": 0,
                "databases": [],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            *common,
            "complete",
            "--target-head",
            "2" * 40,
            "--receipt",
            str(receipt),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "mode" in completed.stderr
    assert json.loads(marker.read_text(encoding="utf-8"))["status"] == "in_progress"


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
        assert 'for account in betboy betboy-backup' in script
        assert 'pgrep -u "${account}"' in script
        assert "scripts/backup_runtime_databases.py" in script
        assert "/usr/local/libexec/betboy-backup-runtime.py" in script
        assert "scripts/manage_challenge_migration_marker.py" in script
        assert "/usr/local/libexec/betboy-challenge-migration-marker.py" in script
        assert "/run/betboy-deploy/deploy.lock" in script
        assert "/run/lock/betboy-deploy.lock" not in script
        assert "os.mkdir(parent, 0o700)" in script
        assert "stat.S_IMODE(parent_info.st_mode) != 0o700" in script
        assert "base_info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)" in script
        assert "flock -n" in script
        assert "os.O_EXCL" in script
        assert "O_NOFOLLOW" in script

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
        expected_user = "betboy-backup" if name == "betboy-backup.service" else "betboy"
        assert f"User={expected_user}" in service
        assert service.count("Group=") == 1
        assert f"Group={expected_user}" in service
        assert service.count("NoNewPrivileges=true") == 1
        for line in service.splitlines():
            if line.startswith("Exec"):
                command = line.split("=", 1)[1].lstrip("-@:^|")
                assert not command.startswith(("+", "!"))

        conditions = [
            line for line in service.splitlines() if line.startswith("ExecCondition=")
        ]
        assert len(conditions) == 1
        assert "betboy-challenge-migration-marker.py" in conditions[0]
        assert conditions[0].endswith(" require-complete")
        expected_marker = (
            "/run/betboy-backup/challenge-ledger-v2-migrated.json"
            if name == "betboy-backup.service"
            else "/etc/betboy/challenge-ledger-v2-migrated.json"
        )
        assert f"--marker {expected_marker}" in conditions[0]

    backup_service = (systemd / "betboy-backup.service").read_text(
        encoding="utf-8"
    )
    app_service = (systemd / "betboy-app.service").read_text(encoding="utf-8")
    assert "Environment=BETBOY_LEDGER_HMAC_REQUIRED=1" in app_service
    assert (
        "Environment=BETBOY_LEDGER_HMAC_KEY_FILE="
        "/etc/betboy/challenge-ledger-hmac.key"
    ) in app_service
    assert "BETBOY_LEDGER_CHECKPOINT_MIGRATION" not in app_service
    assert "SupplementaryGroups=betboy" in backup_service
    assert "ProtectSystem=strict" in backup_service
    assert "ReadOnlyPaths=/opt/betboy/app" in backup_service
    assert "ReadWritePaths=/var/backups/betboy" in backup_service
    assert "InaccessiblePaths=/etc/betboy" in backup_service
    assert "RuntimeDirectory=betboy-backup" in backup_service
    assert (
        "BindReadOnlyPaths=/etc/betboy/challenge-ledger-hmac.key:"
        "/run/betboy-backup/challenge-ledger-hmac.key"
    ) in backup_service
    assert (
        "BindReadOnlyPaths=/etc/betboy/challenge-ledger-v2-migrated.json:"
        "/run/betboy-backup/challenge-ledger-v2-migrated.json"
    ) in backup_service
    assert "--integrity-key /run/betboy-backup/challenge-ledger-hmac.key" in backup_service
    assert (
        "--migration-marker "
        "/run/betboy-backup/challenge-ledger-v2-migrated.json"
    ) in backup_service
    assert "CapabilityBoundingSet=" in backup_service
    assert "RestrictAddressFamilies=AF_UNIX" in backup_service
    assert "/usr/bin/python3 -I /usr/local/libexec/betboy-backup-runtime.py" in backup_service

    for name in expected_services - {"betboy-backup.service"}:
        service = (systemd / name).read_text(encoding="utf-8")
        assert "UMask=0027" in service

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
        expected_block = script.split("expected_unit_sha256() {", 1)[1].split(
            "\n}", 1
        )[0]
        mapping = dict(pattern.findall(expected_block))
        assert set(mapping) == expected_names
        mappings.append(mapping)
        for name, expected_hash in mapping.items():
            actual = hashlib.sha256((systemd / name).read_bytes()).hexdigest()
            assert actual == expected_hash
    assert mappings[0] == mappings[1]

    updater = (root / "deploy" / "update_server.sh").read_text(encoding="utf-8")
    assert "legacy_unit_sha256" not in updater
    assert "ALLOW_LEGACY_UNIT_HASHES" not in updater
    assert "bridge_source_unit_sha256" not in updater
    validate_target = _shell_function(updater, "validate_trusted_unit")
    verify_installed = _shell_function(updater, "verify_installed_unit")
    verify_previous = _shell_function(updater, "verify_installed_previous_unit")
    assert 'expected=$(expected_unit_sha256 "${relative}")' in validate_target
    assert '[[ "${actual}" == "${expected}" ]]' in validate_target
    assert 'check_installed_unit "${name}"' in verify_installed
    assert 'expected=$(sha256sum -- "${reference}"' in verify_previous
    assert 'check_installed_unit "${name}" "${expected}"' in verify_previous


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


def test_backup_discovers_and_archives_all_supported_sqlite_suffixes(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    expected = []
    for name in ("one.db", "two.sqlite", "three.sqlite3"):
        database = root / name
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE evidence (value INTEGER)")
        expected.append(database)

    assert backup.discover_databases(root) == sorted(expected)
    archive, count = backup.create_archive(
        tmp_path / "backups",
        root=root,
        now=datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )
    assert count == 3
    assert backup.verify_archive(archive) == 3
    with zipfile.ZipFile(archive) as zipped:
        assert set(zipped.namelist()) == {
            "one.db",
            "two.sqlite",
            "three.sqlite3",
        }


def test_challenge_backup_preserves_external_hmac_key(tmp_path):
    root = tmp_path / "app"
    database = root / "challenge_sessions" / "account.db"
    _write_legacy_challenge_database(database)
    external_key = tmp_path / "challenge-ledger-hmac.key"
    expected_key = b"ab" * 32 + b"\n"
    external_key.write_bytes(expected_key)
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)
    challenge_migration.migrate_challenge_ledgers(
        root,
        external_key,
        migration_policy=policy,
    )
    marker = _write_completed_migration_marker(
        tmp_path / "challenge-ledger-v2-migrated.json",
        root,
    )

    archive, count = backup.create_archive(
        tmp_path / "backups",
        root=root,
        integrity_key_path=external_key,
        migration_marker_path=marker,
        now=datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )

    assert count == 1
    assert backup.verify_archive(archive) == 1
    with zipfile.ZipFile(archive) as zipped:
        assert set(zipped.namelist()) == {
            "challenge_sessions/account.db",
            backup.INTEGRITY_KEY_ARCHIVE_PATH,
            backup.MIGRATION_MARKER_ARCHIVE_PATH,
        }
        assert zipped.read(backup.INTEGRITY_KEY_ARCHIVE_PATH) == expected_key
        assert json.loads(
            zipped.read(backup.MIGRATION_MARKER_ARCHIVE_PATH).decode("utf-8")
        ) == json.loads(marker.read_text(encoding="utf-8"))


def test_current_challenge_backup_fails_closed_without_migration_marker(tmp_path):
    import pytest

    root = tmp_path / "app"
    database = root / "challenge_sessions" / "account.db"
    _write_legacy_challenge_database(database)
    external_key = tmp_path / "challenge-ledger-hmac.key"
    external_key.write_bytes(b"ab" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)
    challenge_migration.migrate_challenge_ledgers(
        root,
        external_key,
        migration_policy=policy,
    )

    with pytest.raises(RuntimeError, match="completed migration marker"):
        backup.create_archive(
            tmp_path / "backups",
            root=root,
            integrity_key_path=external_key,
        )


def test_completed_marker_rejects_a_rolled_back_v0_challenge_database(tmp_path):
    import pytest

    root = tmp_path / "app"
    database = root / "challenge_sessions" / "account.db"
    _write_legacy_challenge_database(database)
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"ac" * 32 + b"\n")
    marker = _write_completed_migration_marker(
        tmp_path / "challenge-ledger-v2-migrated.json",
        root,
    )

    with pytest.raises(RuntimeError, match="legacy challenge database"):
        backup.create_archive(
            tmp_path / "backups",
            root=root,
            integrity_key_path=key,
            migration_marker_path=marker,
        )


def test_root_challenge_database_requires_integrity_key(tmp_path):
    import pytest

    root = tmp_path / "app"
    root.mkdir()
    _write_legacy_challenge_database(root / "challenge_15k.db")

    with pytest.raises(RuntimeError, match="integrity key"):
        backup.create_archive(tmp_path / "backups", root=root)


def test_backup_verifier_rejects_repacked_hmac_tamper(tmp_path):
    import pytest

    root = tmp_path / "app"
    database = root / "challenge_sessions" / "account.db"
    _write_legacy_challenge_database(database)
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"bc" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)
    challenge_migration.migrate_challenge_ledgers(
        root,
        key,
        migration_policy=policy,
    )
    marker = _write_completed_migration_marker(
        tmp_path / "challenge-ledger-v2-migrated.json",
        root,
    )
    archive, _ = backup.create_archive(
        tmp_path / "backups",
        root=root,
        integrity_key_path=key,
        migration_marker_path=marker,
        now=datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )
    unpacked = tmp_path / "unpacked"
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(unpacked)
    restored = unpacked / "challenge_sessions" / "account.db"
    with sqlite3.connect(restored) as connection:
        connection.execute("DROP TRIGGER challenge_transactions_no_update")
        connection.execute(
            "UPDATE challenge_transactions SET amount_cents=amount_cents + 1 WHERE id=1"
        )
        connection.commit()
    repacked = tmp_path / "tampered.zip"
    with zipfile.ZipFile(repacked, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(unpacked.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(unpacked).as_posix())

    with pytest.raises(RuntimeError, match="HMAC|integrity|authenticated"):
        backup.verify_archive(repacked)


def test_recovery_verifier_accepts_only_explicit_in_progress_v0_v2_mix(tmp_path):
    import pytest

    root = tmp_path / "app"
    legacy = root / "challenge_sessions" / "a-legacy.db"
    current = root / "challenge_sessions" / "z-current.db"
    _write_legacy_challenge_database(legacy)
    _write_legacy_challenge_database(current)
    legacy_copy = tmp_path / "legacy-copy.db"
    backup.backup_database(legacy, legacy_copy)
    key = tmp_path / "challenge-ledger-hmac.key"
    key.write_bytes(b"bd" * 32 + b"\n")
    policy = _write_legacy_migration_policy(tmp_path / "migration.json", root)
    challenge_migration.migrate_challenge_ledgers(
        root,
        key,
        migration_policy=policy,
    )
    backup.backup_database(legacy_copy, legacy)
    archive = tmp_path / "recovery.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.write(legacy, "challenge_sessions/a-legacy.db")
        zipped.write(current, "challenge_sessions/z-current.db")
        zipped.write(key, backup.INTEGRITY_KEY_ARCHIVE_PATH)
        zipped.write(policy, backup.MIGRATION_MARKER_ARCHIVE_PATH)

    with pytest.raises(RuntimeError, match="marker|incomplete"):
        backup.verify_archive(archive)
    assert backup.verify_archive(archive, recovery_mode=True) == 2


def test_backup_verifier_rejects_even_directory_only_zip_traversal(tmp_path):
    archive = tmp_path / "directory-traversal.zip"
    database = tmp_path / "runtime.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE evidence (value INTEGER)")
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.write(database, "runtime.db")
        zipped.writestr("../../escape/", b"")

    import pytest

    with pytest.raises(RuntimeError, match="directory|unsafe"):
        backup.verify_archive(archive)


def test_challenge_backup_fails_closed_without_hmac_key(tmp_path):
    import pytest

    root = tmp_path / "app"
    challenge_dir = root / "challenge_sessions"
    challenge_dir.mkdir(parents=True)
    with sqlite3.connect(challenge_dir / "account.db") as connection:
        connection.execute("CREATE TABLE evidence (value INTEGER)")

    with pytest.raises(RuntimeError, match="require.*integrity key"):
        backup.create_archive(tmp_path / "backups", root=root)


def test_backup_verifier_rejects_invalid_integrity_key(tmp_path):
    archive = tmp_path / "invalid-key.zip"
    database = tmp_path / "account.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE evidence (value INTEGER)")
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.write(database, "challenge_sessions/account.db")
        zipped.writestr(backup.INTEGRITY_KEY_ARCHIVE_PATH, b"not-a-key\n")

    import pytest

    with pytest.raises(RuntimeError, match="invalid format"):
        backup.verify_archive(archive)


def test_backup_fsyncs_archive_publication_and_pruning(tmp_path, monkeypatch):
    root = tmp_path / "app"
    root.mkdir()
    with sqlite3.connect(root / "runtime.db") as connection:
        connection.execute("CREATE TABLE evidence (value INTEGER)")
    synced_files = []
    synced_directories = []
    monkeypatch.setattr(
        backup,
        "_fsync_file",
        lambda path: synced_files.append(path),
    )
    monkeypatch.setattr(
        backup,
        "_fsync_directory",
        lambda path: synced_directories.append(path),
    )
    output = tmp_path / "backups"
    now = datetime(2030, 1, 20, tzinfo=timezone.utc)

    archive, _ = backup.create_archive(output, root=root, now=now)

    assert synced_files == [output / f".{archive.name}.partial"]
    assert synced_directories == [output]
    old = output / "betboy-sqlite-20291201T000000Z.zip"
    old.write_bytes(b"old")
    assert backup.prune_archives(output, retention_days=14, now=now) == 1
    assert synced_directories == [output, output]


def test_backup_refuses_symlink_output_directory(tmp_path):
    import pytest

    root = tmp_path / "app"
    root.mkdir()
    with sqlite3.connect(root / "runtime.db") as connection:
        connection.execute("CREATE TABLE evidence (value INTEGER)")
    actual_output = tmp_path / "actual"
    actual_output.mkdir()
    linked_output = tmp_path / "linked"
    try:
        linked_output.symlink_to(actual_output, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks are unavailable")

    with pytest.raises(RuntimeError, match="must not be a symlink"):
        backup.create_archive(linked_output, root=root)


def test_backup_refuses_symlinked_application_root(tmp_path):
    import pytest

    actual_root = tmp_path / "actual-app"
    actual_root.mkdir()
    with sqlite3.connect(actual_root / "runtime.db") as connection:
        connection.execute("CREATE TABLE evidence (value INTEGER)")
    linked_root = tmp_path / "linked-app"
    try:
        linked_root.symlink_to(actual_root, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")

    with pytest.raises(RuntimeError, match="Backup root.*symlink"):
        backup.create_archive(tmp_path / "backups", root=linked_root)


def test_backup_refuses_linked_database_sources(tmp_path):
    import pytest

    root = tmp_path / "app"
    root.mkdir()
    external = tmp_path / "external.db"
    with sqlite3.connect(external) as connection:
        connection.execute("CREATE TABLE evidence (value INTEGER)")
    linked = root / "linked.db"
    try:
        os.link(external, linked)
    except OSError:
        pytest.skip("hard links are unavailable")

    with pytest.raises(RuntimeError, match="link|regular"):
        backup.create_archive(tmp_path / "backups", root=root)


def test_backup_tree_snapshot_round_trips_nested_runtime_artifacts(tmp_path):
    source = tmp_path / "backups"
    runtime = source / "runtime-artifacts"
    runtime.mkdir(parents=True)
    old_archive = source / "betboy-sqlite-20300101T000000Z.zip"
    old_archive.write_bytes(b"old-archive")
    manifest = runtime / "runtime.manifest.json"
    payload = runtime / "runtime.tar.gz"
    manifest.write_bytes(b"original-manifest")
    payload.write_bytes(b"original-payload")
    snapshot = tmp_path / "rollback" / "backup-tree"

    backup.snapshot_backup_tree(source, snapshot)

    old_archive.unlink()
    manifest.unlink()
    manifest.write_bytes(b"replaced-manifest")
    (runtime / "unexpected.bin").write_bytes(b"unexpected")
    (source / "betboy-sqlite-20300102T000000Z.zip").write_bytes(b"new")

    backup.restore_backup_tree(snapshot, source)

    assert old_archive.read_bytes() == b"old-archive"
    assert manifest.read_bytes() == b"original-manifest"
    assert payload.read_bytes() == b"original-payload"
    assert not (runtime / "unexpected.bin").exists()
    assert not (source / "betboy-sqlite-20300102T000000Z.zip").exists()


def test_backup_tree_snapshot_failure_is_not_published(tmp_path):
    import pytest

    source = tmp_path / "backups"
    source.mkdir()
    (source / "betboy-sqlite-20300101T000000Z.zip").write_bytes(b"archive")
    linked = source / "runtime-artifacts"
    try:
        linked.symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks are unavailable")
    snapshot = tmp_path / "rollback" / "backup-tree"

    with pytest.raises(RuntimeError, match="symlink"):
        backup.snapshot_backup_tree(source, snapshot)

    assert not snapshot.exists()
    assert not snapshot.with_name(f".{snapshot.name}.partial").exists()


def test_backup_tree_update_allows_only_one_new_root_archive(tmp_path):
    import pytest

    source = tmp_path / "backups"
    runtime = source / "runtime-artifacts"
    runtime.mkdir(parents=True)
    (runtime / "runtime.tar.gz").write_bytes(b"runtime")
    verification_time = datetime(2030, 1, 2, 0, 5, tzinfo=timezone.utc)
    old_archive = source / "betboy-sqlite-20000101T000000Z.zip"
    old_archive.write_bytes(b"old")
    snapshot = tmp_path / "rollback" / "backup-tree"
    backup.snapshot_backup_tree(source, snapshot)

    old_archive.unlink()
    created = source / "betboy-sqlite-20300102T000000Z.zip"
    created.write_bytes(b"new")

    assert (
        backup.verify_backup_tree_update(
            snapshot,
            source,
            now=verification_time,
        )
        == created
    )

    (runtime / "unexpected.bin").write_bytes(b"unexpected")
    with pytest.raises(RuntimeError, match="unexpected backup entry"):
        backup.verify_backup_tree_update(snapshot, source, now=verification_time)


def test_backup_tree_snapshot_rejects_overlap_before_creating_parent(tmp_path):
    import pytest

    source = tmp_path / "backups"
    source.mkdir()
    sentinel = source / "keep.txt"
    sentinel.write_bytes(b"keep")
    snapshot = source / "rollback" / "backup-tree"

    with pytest.raises(RuntimeError, match="overlap"):
        backup.snapshot_backup_tree(source, snapshot)

    assert sentinel.read_bytes() == b"keep"
    assert not snapshot.parent.exists()


def test_backup_tree_restore_rejects_overlap_without_mutation(tmp_path):
    import pytest

    source = tmp_path / "source"
    source.mkdir()
    (source / "archive.zip").write_bytes(b"archive")
    snapshot = tmp_path / "rollback" / "backup-tree"
    backup.snapshot_backup_tree(source, snapshot)
    sentinel = tmp_path / "keep.txt"
    sentinel.write_bytes(b"keep")

    with pytest.raises(RuntimeError, match="overlap"):
        backup.restore_backup_tree(snapshot, tmp_path)

    assert sentinel.read_bytes() == b"keep"
    assert snapshot.is_dir()


def test_backup_tree_snapshot_copy_failure_leaves_no_publication(
    tmp_path, monkeypatch
):
    import pytest

    source = tmp_path / "backups"
    source.mkdir()
    (source / "one.zip").write_bytes(b"one")
    (source / "two.zip").write_bytes(b"two")
    snapshot = tmp_path / "rollback" / "backup-tree"
    real_copy = backup._copy_open_descriptor_to_new_file
    calls = 0

    def fail_second_copy(descriptor, destination_path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected copy failure")
        return real_copy(descriptor, destination_path)

    monkeypatch.setattr(
        backup,
        "_copy_open_descriptor_to_new_file",
        fail_second_copy,
    )
    with pytest.raises(RuntimeError, match="could not be published"):
        backup.snapshot_backup_tree(source, snapshot)

    assert not snapshot.exists()
    assert not snapshot.with_name(f".{snapshot.name}.partial").exists()


def test_backup_tree_restore_rejects_tampered_manifest_before_mutation(tmp_path):
    import pytest

    source = tmp_path / "backups"
    source.mkdir()
    original = source / "archive.zip"
    original.write_bytes(b"original")
    snapshot = tmp_path / "rollback" / "backup-tree"
    backup.snapshot_backup_tree(source, snapshot)
    manifest = snapshot / "manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["records"][0]["path"] = "../escape"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    original.write_bytes(b"live")

    with pytest.raises(RuntimeError, match="unsafe"):
        backup.restore_backup_tree(snapshot, source)

    assert original.read_bytes() == b"live"


def test_backup_tree_restore_rejects_live_symlink_without_mutation(tmp_path):
    import pytest

    source = tmp_path / "backups"
    source.mkdir()
    live = source / "archive.zip"
    live.write_bytes(b"original")
    snapshot = tmp_path / "rollback" / "backup-tree"
    backup.snapshot_backup_tree(source, snapshot)
    live.unlink()
    outside = tmp_path / "outside.zip"
    outside.write_bytes(b"outside")
    try:
        live.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("file symlinks are unavailable")

    with pytest.raises(RuntimeError, match="symlink"):
        backup.restore_backup_tree(snapshot, source)

    assert live.is_symlink()
    assert outside.read_bytes() == b"outside"


def test_backup_tree_restore_build_failure_preserves_live_tree(tmp_path, monkeypatch):
    import pytest

    source = tmp_path / "backups"
    source.mkdir()
    live = source / "archive.zip"
    live.write_bytes(b"original")
    snapshot = tmp_path / "rollback" / "backup-tree"
    backup.snapshot_backup_tree(source, snapshot)
    live.unlink()
    live.write_bytes(b"current-live")

    def fail_copy(*_args, **_kwargs):
        raise OSError("injected restore copy failure")

    monkeypatch.setattr(backup, "_copy_open_descriptor_to_new_file", fail_copy)
    with pytest.raises((OSError, RuntimeError)):
        backup.restore_backup_tree(snapshot, source)

    assert live.read_bytes() == b"current-live"


def test_backup_tree_restore_validation_failure_exchanges_live_tree_back(
    tmp_path, monkeypatch
):
    import pytest

    source = tmp_path / "backups"
    source.mkdir()
    live = source / "archive.zip"
    live.write_bytes(b"original")
    snapshot = tmp_path / "rollback" / "backup-tree"
    backup.snapshot_backup_tree(source, snapshot)
    live.unlink()
    live.write_bytes(b"current-live")
    real_scan = backup._scan_backup_tree
    source_scans = 0

    def fail_post_exchange_scan(root, **kwargs):
        nonlocal source_scans
        result = real_scan(root, **kwargs)
        if Path(root) == source:
            source_scans += 1
            if source_scans == 3:
                return {}
        return result

    monkeypatch.setattr(backup, "_scan_backup_tree", fail_post_exchange_scan)
    with pytest.raises(RuntimeError, match="does not match"):
        backup.restore_backup_tree(snapshot, source)

    assert live.read_bytes() == b"current-live"
    assert not list(tmp_path.glob(".backups.restore-*"))


def test_backup_tree_update_rejects_identical_replacement_and_two_archives(tmp_path):
    import pytest

    source = tmp_path / "backups"
    runtime = source / "runtime-artifacts"
    runtime.mkdir(parents=True)
    protected = runtime / "runtime.tar.gz"
    protected.write_bytes(b"runtime")
    verification_time = datetime(2030, 1, 2, 0, 5, tzinfo=timezone.utc)
    snapshot = tmp_path / "rollback" / "backup-tree"
    backup.snapshot_backup_tree(source, snapshot)

    protected.unlink()
    protected.write_bytes(b"runtime")
    (source / "betboy-sqlite-20300102T000000Z.zip").write_bytes(b"new")
    if os.name == "nt":
        assert backup.verify_backup_tree_update(
            snapshot,
            source,
            now=verification_time,
        ).name == (
            "betboy-sqlite-20300102T000000Z.zip"
        )
    else:
        with pytest.raises(RuntimeError, match="replaced"):
            backup.verify_backup_tree_update(
                snapshot,
                source,
                now=verification_time,
            )

    backup.restore_backup_tree(snapshot, source)
    shutil.rmtree(snapshot)
    second_snapshot = tmp_path / "rollback-second" / "backup-tree"
    backup.snapshot_backup_tree(source, second_snapshot)
    (source / "betboy-sqlite-20300102T000000Z.zip").write_bytes(b"new")
    (source / "betboy-sqlite-20300102T000100Z.zip").write_bytes(b"second")
    with pytest.raises(RuntimeError, match="unexpected backup entry"):
        backup.verify_backup_tree_update(
            second_snapshot,
            source,
            now=verification_time,
        )


def test_backup_tree_update_rejects_external_link_for_pruned_archive(tmp_path):
    import pytest

    source = tmp_path / "backups"
    source.mkdir()
    old_archive = source / "betboy-sqlite-20000101T000000Z.zip"
    old_archive.write_bytes(b"old")
    snapshot = tmp_path / "rollback" / "backup-tree"
    backup.snapshot_backup_tree(source, snapshot)
    outside = tmp_path / "outside-link.zip"
    snapshot_archive = snapshot / "files" / old_archive.name
    os.link(snapshot_archive, outside)
    old_archive.unlink()
    if snapshot_archive.stat().st_nlink == 0:
        pytest.skip("hard-link counts are unavailable")
    (source / "betboy-sqlite-20300102T000000Z.zip").write_bytes(b"new")

    with pytest.raises(RuntimeError, match="unsafe link count"):
        backup.verify_backup_tree_update(
            snapshot,
            source,
            now=datetime(2030, 1, 2, 0, 5, tzinfo=timezone.utc),
        )


def test_backup_tree_update_rejects_recent_history_deletion_and_bad_timestamp(
    tmp_path,
):
    import pytest

    verification_time = datetime(2030, 1, 2, 0, 5, tzinfo=timezone.utc)
    source = tmp_path / "backups"
    source.mkdir()
    recent = source / "betboy-sqlite-20300101T235900Z.zip"
    recent.write_bytes(b"recent")
    snapshot = tmp_path / "rollback" / "backup-tree"
    backup.snapshot_backup_tree(source, snapshot)
    recent.unlink()
    created = source / "betboy-sqlite-20300102T000000Z.zip"
    created.write_bytes(b"new")

    with pytest.raises(RuntimeError, match="removed a protected"):
        backup.verify_backup_tree_update(
            snapshot,
            source,
            now=verification_time,
        )

    backup.restore_backup_tree(snapshot, source)
    shutil.rmtree(snapshot)
    malformed_snapshot = tmp_path / "rollback-malformed" / "backup-tree"
    backup.snapshot_backup_tree(source, malformed_snapshot)
    malformed = source / "betboy-sqlite-99999999T999999Z.zip"
    malformed.write_bytes(b"bad")
    with pytest.raises(RuntimeError, match="unexpected backup entry"):
        backup.verify_backup_tree_update(
            malformed_snapshot,
            source,
            now=verification_time,
        )


def test_backup_tree_update_requires_every_expired_archive_to_be_pruned(tmp_path):
    import pytest

    verification_time = datetime(2030, 1, 2, 0, 5, tzinfo=timezone.utc)
    source = tmp_path / "backups"
    source.mkdir()
    expired = source / "betboy-sqlite-20000101T000000Z.zip"
    expired.write_bytes(b"expired")
    snapshot = tmp_path / "rollback" / "backup-tree"
    backup.snapshot_backup_tree(source, snapshot)
    created = source / "betboy-sqlite-20300102T000000Z.zip"
    created.write_bytes(b"new")

    with pytest.raises(RuntimeError, match="configured retention"):
        backup.verify_backup_tree_update(
            snapshot,
            source,
            now=verification_time,
        )


def test_backup_tree_update_allows_retention_boundary_race(tmp_path):
    service_archive_time = datetime(2030, 1, 2, 0, 0, tzinfo=timezone.utc)
    verification_time = service_archive_time + timedelta(seconds=2)
    source = tmp_path / "backups"
    source.mkdir()
    boundary = source / "betboy-sqlite-20291219T000001Z.zip"
    boundary.write_bytes(b"boundary")
    snapshot = tmp_path / "rollback" / "backup-tree"
    backup.snapshot_backup_tree(source, snapshot)
    created = source / "betboy-sqlite-20300102T000000Z.zip"
    created.write_bytes(b"new")

    assert backup.verify_backup_tree_update(
        snapshot,
        source,
        now=verification_time,
    ) == created

    boundary.unlink()
    assert backup.verify_backup_tree_update(
        snapshot,
        source,
        now=verification_time,
    ) == created


def test_backup_tree_manifest_requires_sorted_unique_strict_records(tmp_path):
    import pytest

    source = tmp_path / "backups"
    source.mkdir()
    (source / "a.zip").write_bytes(b"a")
    (source / "b.zip").write_bytes(b"b")
    snapshot = tmp_path / "rollback" / "backup-tree"
    backup.snapshot_backup_tree(source, snapshot)
    manifest = snapshot / "manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["records"].reverse()
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="not sorted"):
        backup.restore_backup_tree(snapshot, source)


def test_backup_tree_manifest_rejects_boolean_version_and_duplicate_keys(tmp_path):
    import pytest

    source = tmp_path / "backups"
    source.mkdir()
    (source / "archive.zip").write_bytes(b"archive")

    boolean_snapshot = tmp_path / "rollback-one" / "backup-tree"
    backup.snapshot_backup_tree(source, boolean_snapshot)
    boolean_manifest = boolean_snapshot / "manifest.json"
    boolean_manifest.write_text(
        boolean_manifest.read_text(encoding="utf-8").replace(
            '"version":1',
            '"version":true',
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="contract"):
        backup.restore_backup_tree(boolean_snapshot, source)
    shutil.rmtree(boolean_snapshot)

    duplicate_snapshot = tmp_path / "rollback-two" / "backup-tree"
    backup.snapshot_backup_tree(source, duplicate_snapshot)
    duplicate_manifest = duplicate_snapshot / "manifest.json"
    duplicate_manifest.write_text(
        duplicate_manifest.read_text(encoding="utf-8").replace(
            '"version":1',
            '"version":1,"version":1',
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="duplicate"):
        backup.restore_backup_tree(duplicate_snapshot, source)


def test_updater_publishes_backup_snapshot_only_after_helper_success():
    root = Path(__file__).resolve().parents[1]
    update = (root / "deploy" / "update_server.sh").read_text(encoding="utf-8")
    snapshot = _shell_function(update, "snapshot_backup_archives")
    helper = snapshot.index("--snapshot-backup-tree")
    publish = snapshot.index('BACKUP_ARCHIVE_INVENTORY="${candidate}"')

    assert helper < publish
    assert "scripts/backup_runtime_databases.py" in snapshot
    assert "manifest.json" in snapshot[helper:publish]

    restore = _shell_function(update, "restore_backup_archives")
    assert '[[ -z "${BACKUP_ARCHIVE_INVENTORY}" ]] && return 0' in restore
    assert "--restore-backup-tree" in restore
    assert '${TRUSTED_TREE}/scripts/backup_runtime_databases.py' in restore

    verify = _shell_function(update, "verify_backup_service_migration")
    assert "--verify-backup-tree-update" in verify
    assert "--verify-only" in verify

    preflight = _shell_function(update, "preflight")
    assert "du -skx --apparent-size /var/backups/betboy" in preflight
    assert "database_apparent_kib * 5 + 524288" in preflight
    assert "independent backup snapshot and restore" in preflight

    root_snapshot = _shell_function(update, "snapshot_root_files")
    assert "backup_parent_mode=$(stat -c '%a' /var/backups)" in root_snapshot
    assert "Backup parent is writable by a non-root account" in root_snapshot
    assert "Backup destination must share its parent filesystem" in root_snapshot
    assert "mountpoint -q /var/backups/betboy" in root_snapshot
    assert "df -Pk /var/backups" in preflight


def test_caddy_frame_policy_is_installed_by_bootstrap_and_updater():
    root = Path(__file__).resolve().parents[1]
    expected = (
        'Content-Security-Policy "frame-ancestors \'self\'"',
        'X-Frame-Options "SAMEORIGIN"',
    )
    for path in (
        root / "deploy" / "Caddyfile.example",
        root / "deploy" / "bootstrap_server.sh",
        root / "deploy" / "update_server.sh",
    ):
        source = path.read_text(encoding="utf-8")
        for header in expected:
            assert source.count(header) == 1


def test_backup_user_migration_is_updater_and_rollback_compatible():
    root = Path(__file__).resolve().parents[1]
    update = (root / "deploy" / "update_server.sh").read_text(
        encoding="utf-8"
    )
    bootstrap = (root / "deploy" / "bootstrap_server.sh").read_text(
        encoding="utf-8"
    )

    for source in (update, bootstrap):
        assert "ensure_backup_principal" in source
        assert "User=betboy-backup" not in source  # unit bytes stay separately pinned
        assert "-o betboy-backup -g betboy-backup" in source
        assert "--groups betboy" not in source
        assert "--append --groups" not in source
        assert "must not have persistent supplementary groups" in source
        assert "refusing to adopt it" in source
        assert "chmod u=rw,g=r,o=" in source
        assert "chmod u=rwx,g=rx,o=" in source
        assert "Runtime database is not owned by betboy" in source
        assert "ensure_ledger_hmac_key" in source
        assert "/etc/betboy/challenge-ledger-hmac.key" in source
        assert "scripts/manage_challenge_integrity_key.py" in source
        assert "install_root_file_atomic" in source
        assert "os.fsync(directory_fd)" in source
        assert "source_info.st_nlink != 1" in source
    key_helper = (
        root / "scripts" / "manage_challenge_integrity_key.py"
    ).read_text(encoding="utf-8")
    assert "os.O_EXCL" in key_helper
    assert "O_NOFOLLOW" in key_helper
    assert "os.fchown(descriptor, 0, group_id)" in key_helper
    assert "os.fchmod(descriptor, 0o640)" in key_helper
    assert "secrets.token_hex(32)" in key_helper
    assert "verify_installed_previous_unit" in update
    assert "snapshot_backup_source_metadata" in update
    assert "apply_backup_source_metadata restore" in update
    assert "snapshot_backup_archives" in update
    assert "restore_backup_archives" in update
    assert 'stat -c \'%d\' /var/tmp' in update
    assert 'chown "${BACKUP_DIR_UID}:${BACKUP_DIR_GID}"' in update
    assert "restore_backup_principal_state" in update
    assert "BACKUP_HELPER_WAS_PRESENT" in update
    assert "verify_backup_service_migration" in update
    assert "systemctl start betboy-backup.service" in update
    assert "--verify-only" in update
    assert "/usr/bin/test ! -r /etc/betboy/betboy.env" in update
    assert "verify_public_proxy" in update
    assert '--resolve "${PUBLIC_HOST}:443:127.0.0.1"' in update
    assert 'caddy reload --config /etc/caddy/Caddyfile' in update
    assert "integrity/challenge-ledger-hmac.key" in update
    assert '"integrity_key": {' in update


def test_backup_verifier_rejects_an_invalid_sqlite_member(tmp_path):
    archive = tmp_path / "invalid.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("runtime_state/api_budget.db", b"not a database")

    import pytest

    with pytest.raises(RuntimeError, match="not restorable"):
        backup.verify_archive(archive)
