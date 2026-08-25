#!/usr/bin/env python3
"""Migrate legacy 15K ledgers while every runtime writer is stopped."""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from challenge_store import (  # noqa: E402
    FINANCIAL_CHAIN_VERSION,
    LEDGER_CHECKPOINT_MIGRATION_ENV,
    LEDGER_HMAC_KEY_FILE_ENV,
    LEDGER_HMAC_REQUIRED_ENV,
    LEDGER_MIGRATION_POLICY_FILE_ENV,
    ChallengeLedger,
    _read_legacy_migration_policy,
    _sqlite_integer,
)
from scripts.backup_runtime_databases import (  # noqa: E402
    _read_integrity_key as _read_backup_integrity_key,
    verify_current_challenge_database,
)


DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
PRODUCTION_APPLICATION_ROOT = Path("/opt/betboy/app")
PRODUCTION_LEGACY_V0_DATABASE_COUNT = 72
# SHA-256 over compact canonical JSON of the 72 sorted relative database paths
# observed read-only on 2026-08-25. Account identifiers are deliberately not
# embedded in source, while deletion/rename/injection before the one-time
# production migration still fails closed.
PRODUCTION_LEGACY_V0_PATH_INVENTORY_SHA256 = (
    "60691abde97905cb24632f7cad79ae1944f2709a04c6be3a151093a581f30bf0"
)
LEGACY_V0_SETTINGS_LAYOUTS = {
    (
        "id",
        "starting_balance_cents",
        "current_balance_cents",
        "target_balance_cents",
        "updated_at",
    ),
    (
        "id",
        "starting_balance_cents",
        "current_balance_cents",
        "target_balance_cents",
        "updated_at",
        "stake_fraction_bps",
    ),
    (
        "id",
        "starting_balance_cents",
        "current_balance_cents",
        "target_balance_cents",
        "stake_fraction_bps",
        "updated_at",
        "stake_policy_version",
    ),
    (
        "id",
        "starting_balance_cents",
        "current_balance_cents",
        "target_balance_cents",
        "stake_fraction_bps",
        "stake_policy_version",
        "updated_at",
    ),
    (
        "id",
        "starting_balance_cents",
        "current_balance_cents",
        "target_balance_cents",
        "updated_at",
        "stake_fraction_bps",
        "stake_policy_version",
    ),
}
# Exact SHA-256 values of the complete allowlisted sqlite_master object set
# observed read-only across all 72 production v0 challenge ledgers on
# 2026-08-25. The invariant sqlite_sequence DDL is verified separately and
# omitted; the one legitimate implicit price-observation autoindex is included
# verbatim as a null-SQL object. These five layouts cover the historical main
# ledger plus all browser-account generations. A column-compatible table with
# different CHECK/default/collation/trigger/index semantics is deliberately not
# migrated.
LEGACY_V0_SCHEMA_SHA256 = {
    "0a8e123e65760609c42dc49c7edd46e88a9724f2223c4a117f9cec428b3d2f8d",
    "4f4bdd6c490d395ab7e5f0a0dd0ddacc97c1364103cdbef3e57df91c33c68727",
    "79e007c15a995b56d4437bccad44e5424f59c4f8eb408052b36ca1b2e8429ca2",
    "f0f4bd4429e091c5d066d4c0f447513a7ea4d22bbff1d34f2b5edc52301c6754",
    "f83d540c4cf176897cfb99cea06b1fab12ffe9fd4895c6c20ee17584e62615df",
}
LEGACY_SQLITE_SEQUENCE_OBJECT = [
    "table",
    "sqlite_sequence",
    "sqlite_sequence",
    "CREATE TABLE sqlite_sequence(name,seq)",
]
LEGACY_PRICE_AUTOINDEX_OBJECT = [
    "index",
    "sqlite_autoindex_price_observations_1",
    "price_observations",
    None,
]
LEGACY_AUTOINCREMENT_TABLES = {
    "challenge_tickets",
    "challenge_transactions",
    "price_observations",
}
LEGACY_V0_TICKET_LAYOUTS = {
    (
        "id",
        "analysis_date",
        "created_at",
        "quote_verified_at",
        "settled_at",
        "status",
        "stake_cents",
        "payout_cents",
        "total_odds",
        "joint_probability",
        "expected_roi",
        "legs_json",
    ),
    (
        "id",
        "analysis_date",
        "created_at",
        "quote_verified_at",
        "settled_at",
        "status",
        "stake_cents",
        "payout_cents",
        "total_odds",
        "played_odds",
        "joint_probability",
        "expected_roi",
        "legs_json",
        "entry_source",
    ),
    (
        "id",
        "analysis_date",
        "created_at",
        "quote_verified_at",
        "settled_at",
        "status",
        "stake_cents",
        "payout_cents",
        "total_odds",
        "joint_probability",
        "expected_roi",
        "legs_json",
        "played_odds",
        "entry_source",
    ),
}
LEGACY_V0_TRANSACTION_LAYOUT = (
    "id",
    "created_at",
    "kind",
    "amount_cents",
    "balance_after_cents",
    "ticket_id",
    "note",
)
LEGACY_V0_TABLES = {
    "challenge_settings",
    "challenge_tickets",
    "challenge_transactions",
}
LEGACY_V0_INDEXES = {"idx_challenge_daily_ticket"}


def _sqlite_uri(path: Path) -> str:
    return path.resolve(strict=True).as_uri() + "?mode=ro"


def _absolute_lexical_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _validated_application_root(path: Path) -> Path:
    lexical = _absolute_lexical_path(path)
    if lexical.is_symlink():
        raise RuntimeError("Application root must not be a symlink")
    resolved = lexical.resolve(strict=True)
    if resolved != lexical:
        raise RuntimeError("Application root must not traverse a symlink")
    if not stat.S_ISDIR(os.lstat(resolved).st_mode):
        raise RuntimeError("Application root must be a real directory")
    return resolved


def _regular_single_link(
    path: Path,
    label: str,
    *,
    allow_root_owner: bool = False,
) -> None:
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RuntimeError(f"{label} must be one regular, non-linked file")
    trusted_owners = {os.geteuid()} if hasattr(os, "geteuid") else set()
    if allow_root_owner:
        trusted_owners.add(0)
    if trusted_owners and info.st_uid not in trusted_owners:
        raise RuntimeError(f"{label} is not owned by the migration account")


def discover_challenge_databases(
    root: Path,
    *,
    require_known_schema: bool = False,
) -> list[Path]:
    """Return only databases that already contain challenge settings."""

    resolved_root = _validated_application_root(root)
    candidates: list[Path] = []
    default_database = resolved_root / "challenge_15k.db"
    if os.path.lexists(default_database):
        candidates.append(default_database)

    sessions = resolved_root / "challenge_sessions"
    if os.path.lexists(sessions):
        session_info = sessions.lstat()
        if sessions.is_symlink() or not stat.S_ISDIR(session_info.st_mode):
            raise RuntimeError("challenge_sessions must be a real directory")
        for directory, dirnames, filenames in os.walk(
            sessions,
            topdown=True,
            followlinks=False,
        ):
            current = Path(directory)
            kept_directories = []
            for name in dirnames:
                child = current / name
                child_info = child.lstat()
                if child.is_symlink() or not stat.S_ISDIR(child_info.st_mode):
                    raise RuntimeError(
                        "Challenge database path must not traverse a symlink"
                    )
                kept_directories.append(name)
            dirnames[:] = kept_directories
            for name in filenames:
                path = current / name
                if path.suffix.casefold() not in DATABASE_SUFFIXES:
                    continue
                candidates.append(path)

    challenge_databases: list[Path] = []
    for path in sorted(set(candidates)):
        _regular_single_link(path, "Challenge database")
        with closing(
            sqlite3.connect(_sqlite_uri(path), uri=True, timeout=30)
        ) as connection:
            connection.execute("PRAGMA query_only=ON")
            table = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type='table' AND name='challenge_settings'
                """
            ).fetchone()
        if table is not None:
            challenge_databases.append(path)
        elif require_known_schema:
            raise RuntimeError(
                "Known challenge database is missing challenge_settings"
            )
    if require_known_schema and not challenge_databases:
        raise RuntimeError("Legacy migration requires at least one challenge database")
    return challenge_databases


def _validate_production_legacy_path_inventory(
    root: Path,
    databases: list[Path],
) -> None:
    if root != PRODUCTION_APPLICATION_ROOT:
        return
    relative_paths = sorted(path.relative_to(root).as_posix() for path in databases)
    canonical = json.dumps(
        relative_paths,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    if (
        len(relative_paths) != PRODUCTION_LEGACY_V0_DATABASE_COUNT
        or digest != PRODUCTION_LEGACY_V0_PATH_INVENTORY_SHA256
    ):
        raise RuntimeError(
            "Production legacy challenge database inventory changed; "
            "refusing the one-time migration"
        )


def _column_layout(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    if not rows or str(rows[0]["name"]) != "id" or int(rows[0]["pk"]) != 1:
        raise RuntimeError(f"Legacy {table} primary key is invalid")
    for row in rows:
        declared_type = str(row["type"] or "").upper()
        name = str(row["name"])
        if name.endswith("_cents") or name in {
            "id",
            "stake_fraction_bps",
            "stake_policy_version",
            "ticket_id",
        }:
            expected_type = "INTEGER"
        elif name in {
            "total_odds",
            "played_odds",
            "joint_probability",
            "expected_roi",
        }:
            expected_type = "REAL"
        else:
            expected_type = "TEXT"
        if declared_type != expected_type:
            raise RuntimeError(f"Legacy {table}.{name} has an invalid type")
    return tuple(str(row["name"]) for row in rows)


def _legacy_v0_schema_sha256(connection: sqlite3.Connection) -> str:
    rows = connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_master
        ORDER BY type, name, tbl_name
        """
    ).fetchall()
    objects: list[list[object]] = []
    for row in rows:
        item: list[object] = [
            str(row["type"]),
            str(row["name"]),
            str(row["tbl_name"]),
            row["sql"],
        ]
        if item[1] == "sqlite_sequence":
            if item != LEGACY_SQLITE_SEQUENCE_OBJECT:
                raise RuntimeError("Legacy sqlite_sequence DDL is invalid")
            continue
        if str(item[1]).startswith("sqlite_"):
            if item != LEGACY_PRICE_AUTOINDEX_OBJECT:
                raise RuntimeError("Legacy schema contains an unknown internal object")
        elif not isinstance(item[3], str):
            raise RuntimeError("Legacy schema contains an object without exact SQL")
        objects.append(item)
    canonical = json.dumps(
        objects,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_legacy_v0_sequences(
    connection: sqlite3.Connection,
    tables: set[str],
) -> None:
    rows = connection.execute(
        "SELECT name, seq FROM sqlite_sequence ORDER BY name, rowid"
    ).fetchall()
    names = [str(row["name"]) for row in rows]
    if len(names) != len(set(names)):
        raise RuntimeError("Legacy challenge sequence inventory is ambiguous")
    sequence_rows = {str(row["name"]): row["seq"] for row in rows}
    expected = tables & LEGACY_AUTOINCREMENT_TABLES
    if not set(sequence_rows) <= expected:
        raise RuntimeError("Legacy challenge sequence inventory is invalid")
    for table in sorted(expected):
        minimum, maximum, count = connection.execute(
            f"SELECT COALESCE(MIN(id), 0), COALESCE(MAX(id), 0), COUNT(*) "
            f"FROM {table}"
        ).fetchone()
        if (
            type(minimum) is not int
            or type(maximum) is not int
            or type(count) is not int
            or minimum < 0
            or maximum < 0
            or count < 0
            or (count > 0 and minimum < 1)
        ):
            raise RuntimeError(f"Legacy {table} identifier state is invalid")
        sequence = sequence_rows.get(table)
        if sequence is None:
            if count:
                raise RuntimeError(f"Legacy {table} sequence is missing")
            continue
        if (
            type(sequence) is not int
            or sequence < maximum
            or sequence - maximum > 4
        ):
            raise RuntimeError(f"Legacy {table} sequence is invalid")


def _validate_legacy_v0_schema(connection: sqlite3.Connection) -> None:
    objects = connection.execute(
        "SELECT type, name, tbl_name FROM sqlite_master"
    ).fetchall()
    all_tables = {
        str(row["name"])
        for row in objects
        if row["type"] == "table" and not str(row["name"]).startswith("sqlite_")
    }
    challenge_table_names = {
        str(row["name"])
        for row in objects
        if row["type"] == "table" and str(row["name"]).startswith("challenge_")
    }
    relevant = [
        row
        for row in objects
        if str(row["name"]).startswith(("challenge_", "idx_challenge_"))
        or str(row["tbl_name"]) in challenge_table_names
    ]
    tables = {str(row["name"]) for row in relevant if row["type"] == "table"}
    indexes = {str(row["name"]) for row in relevant if row["type"] == "index"}
    other_objects = {
        (str(row["type"]), str(row["name"]))
        for row in relevant
        if row["type"] not in {"table", "index"}
    }
    if (
        "challenge_settings" not in tables
        or not tables <= LEGACY_V0_TABLES
        or not indexes <= LEGACY_V0_INDEXES
        or other_objects
    ):
        raise RuntimeError("Challenge database is not an allowlisted legacy v0 schema")
    if _legacy_v0_schema_sha256(connection) not in LEGACY_V0_SCHEMA_SHA256:
        raise RuntimeError(
            "Challenge database DDL is not an allowlisted production v0 schema"
        )
    _validate_legacy_v0_sequences(connection, all_tables)
    if _column_layout(connection, "challenge_settings") not in LEGACY_V0_SETTINGS_LAYOUTS:
        raise RuntimeError("Challenge settings are not an allowlisted legacy v0 schema")
    if "challenge_tickets" in tables and (
        _column_layout(connection, "challenge_tickets")
        not in LEGACY_V0_TICKET_LAYOUTS
    ):
        raise RuntimeError("Challenge tickets are not an allowlisted legacy v0 schema")
    if "challenge_transactions" in tables and (
        _column_layout(connection, "challenge_transactions")
        != LEGACY_V0_TRANSACTION_LAYOUT
    ):
        raise RuntimeError(
            "Challenge transactions are not an allowlisted legacy v0 schema"
        )


def _preflight_database(path: Path, *, allow_legacy_v0: bool) -> str:
    """Classify a strict v0 source or a complete current v2 database."""

    with closing(
        sqlite3.connect(_sqlite_uri(path), uri=True, timeout=30)
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(challenge_settings)")
        }
        version: int | None = None
        if "financial_chain_version" in columns:
            row = connection.execute(
                "SELECT financial_chain_version FROM challenge_settings WHERE id=1"
            ).fetchone()
            if row is None:
                raise RuntimeError("Challenge settings row is missing")
            try:
                version = _sqlite_integer(
                    row["financial_chain_version"],
                    "challenge financial_chain_version",
                )
            except (TypeError, ValueError, OverflowError) as exc:
                raise RuntimeError("Challenge financial version is invalid") from exc
        checkpoint_table = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='challenge_integrity_checkpoint'
            """
        ).fetchone()
        if checkpoint_table is not None:
            checkpoint_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM challenge_integrity_checkpoint"
                ).fetchone()[0]
            )
            if version != FINANCIAL_CHAIN_VERSION or checkpoint_count != 1:
                raise RuntimeError(
                    "Existing integrity checkpoint is incomplete or rolled back"
                )
            return "v2"
        if version == 1:
            raise RuntimeError(
                "Legacy financial version v1 was never a deployed BetBoy predecessor"
            )
        if version == FINANCIAL_CHAIN_VERSION:
            raise RuntimeError(
                "HMAC v2 challenge database is missing its integrity checkpoint"
            )
        if version is not None:
            raise RuntimeError("Unsupported legacy challenge financial version")
        if not allow_legacy_v0:
            raise RuntimeError(
                "Legacy v0 challenge database requires a root migration policy; "
                "verify-only mode cannot sign it"
            )
        _validate_legacy_v0_schema(connection)
        return "v0"


def _copy_database_for_semantic_preflight(source: Path, destination: Path) -> None:
    """Create one consistent SQLite clone without touching the source file."""

    with closing(
        sqlite3.connect(_sqlite_uri(source), uri=True, timeout=30)
    ) as source_connection, closing(
        sqlite3.connect(destination, timeout=30)
    ) as destination_connection:
        source_connection.execute("PRAGMA query_only=ON")
        source_connection.backup(destination_connection)


def migrate_challenge_ledgers(
    root: Path,
    integrity_key: Path,
    *,
    migration_policy: Path | None = None,
) -> dict[str, object]:
    if integrity_key.is_symlink() or (
        migration_policy is not None and migration_policy.is_symlink()
    ):
        raise RuntimeError("Migration paths must not be symbolic links")
    root = _validated_application_root(root)
    _regular_single_link(
        integrity_key,
        "Ledger integrity key",
        allow_root_owner=True,
    )
    integrity_key = integrity_key.resolve(strict=True)
    policy: dict[str, object] | None = None
    if migration_policy is not None:
        _regular_single_link(
            migration_policy,
            "Ledger migration policy",
            allow_root_owner=True,
        )
        migration_policy = migration_policy.resolve(strict=True)
        previous_policy_environment = os.environ.get(
            LEDGER_MIGRATION_POLICY_FILE_ENV
        )
        previous_key_environment = os.environ.get(LEDGER_HMAC_KEY_FILE_ENV)
        try:
            os.environ[LEDGER_MIGRATION_POLICY_FILE_ENV] = str(migration_policy)
            os.environ[LEDGER_HMAC_KEY_FILE_ENV] = str(integrity_key)
            policy = _read_legacy_migration_policy(root / "challenge_15k.db")
        finally:
            if previous_policy_environment is None:
                os.environ.pop(LEDGER_MIGRATION_POLICY_FILE_ENV, None)
            else:
                os.environ[
                    LEDGER_MIGRATION_POLICY_FILE_ENV
                ] = previous_policy_environment
            if previous_key_environment is None:
                os.environ.pop(LEDGER_HMAC_KEY_FILE_ENV, None)
            else:
                os.environ[LEDGER_HMAC_KEY_FILE_ENV] = previous_key_environment
        policy_root = Path(str(policy["application_root"]))
        if not policy_root.is_absolute() or policy_root != root:
            raise RuntimeError("Ledger migration policy names another application root")

    databases = discover_challenge_databases(
        root,
        require_known_schema=policy is not None,
    )
    if policy is not None:
        _validate_production_legacy_path_inventory(root, databases)

    # Scan all databases before touching any one of them.  In particular, a
    # v2 database with a deleted checkpoint is an attack/rollback state and is
    # never accepted as a migration source, even with the operator flag.
    classifications = {
        path: _preflight_database(
            path,
            allow_legacy_v0=policy is not None,
        )
        for path in databases
    }

    if policy is None:
        key_bytes = _read_backup_integrity_key(integrity_key)
        receipt_databases: list[dict[str, str]] = []
        for path in databases:
            verify_current_challenge_database(
                path,
                key_bytes,
                ledger_scope=str(path.resolve(strict=False)),
            )
            with closing(
                sqlite3.connect(_sqlite_uri(path), uri=True, timeout=30)
            ) as connection:
                connection.execute("PRAGMA query_only=ON")
                checkpoint = connection.execute(
                    """
                    SELECT record_mac FROM challenge_integrity_checkpoint
                    WHERE id=1
                    """
                ).fetchone()
            if checkpoint is None or not isinstance(checkpoint[0], str):
                raise RuntimeError("Challenge checkpoint receipt is missing")
            receipt_databases.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "checkpoint_mac": checkpoint[0],
                    "source": "v2",
                }
            )
        return {
            "contract_version": 1,
            "mode": "verify-only",
            "database_count": len(databases),
            "databases": receipt_databases,
        }

    previous_environment = {
        LEDGER_HMAC_KEY_FILE_ENV: os.environ.get(LEDGER_HMAC_KEY_FILE_ENV),
        LEDGER_HMAC_REQUIRED_ENV: os.environ.get(LEDGER_HMAC_REQUIRED_ENV),
        LEDGER_CHECKPOINT_MIGRATION_ENV: os.environ.get(
            LEDGER_CHECKPOINT_MIGRATION_ENV
        ),
        LEDGER_MIGRATION_POLICY_FILE_ENV: os.environ.get(
            LEDGER_MIGRATION_POLICY_FILE_ENV
        ),
    }
    try:
        os.environ[LEDGER_HMAC_KEY_FILE_ENV] = str(integrity_key)
        os.environ[LEDGER_HMAC_REQUIRED_ENV] = "1"
        if policy is not None:
            os.environ[LEDGER_CHECKPOINT_MIGRATION_ENV] = "1"
            os.environ[LEDGER_MIGRATION_POLICY_FILE_ENV] = str(migration_policy)
        else:
            os.environ.pop(LEDGER_CHECKPOINT_MIGRATION_ENV, None)
            os.environ.pop(LEDGER_MIGRATION_POLICY_FILE_ENV, None)

        # Exercise every source on disposable SQLite clones outside the app
        # checkout. A killed preflight therefore cannot leave an untracked DB
        # that a later deploy or backup might mistake for account data.
        key_bytes = _read_backup_integrity_key(integrity_key)
        with tempfile.TemporaryDirectory(
            prefix="betboy-challenge-ledger-preflight-",
        ) as temporary:
            preflight_root = Path(temporary)
            legacy_root = preflight_root / "legacy-root"
            legacy_root.mkdir()
            legacy_key = preflight_root / "ledger-hmac.key"
            legacy_key.write_bytes(key_bytes)
            if os.name != "nt":
                legacy_key.chmod(0o600)
            legacy_policy = preflight_root / "migration-policy.json"
            if policy is not None:
                temporary_policy = {
                    **policy,
                    "application_root": str(legacy_root.resolve(strict=True)),
                }
                legacy_policy.write_text(
                    json.dumps(
                        temporary_policy,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n",
                    encoding="utf-8",
                )
                if os.name != "nt":
                    legacy_policy.chmod(0o600)
            for index, path in enumerate(databases):
                clone_parent = (
                    legacy_root
                    if classifications[path] == "v0"
                    else preflight_root / "current"
                )
                clone_parent.mkdir(parents=True, exist_ok=True)
                clone = clone_parent / f"database-{index}{path.suffix}"
                _copy_database_for_semantic_preflight(path, clone)
                try:
                    if classifications[path] == "v2":
                        verify_current_challenge_database(
                            clone,
                            key_bytes,
                            ledger_scope=str(path.resolve(strict=False)),
                        )
                    else:
                        os.environ[LEDGER_HMAC_KEY_FILE_ENV] = str(legacy_key)
                        os.environ[LEDGER_MIGRATION_POLICY_FILE_ENV] = str(
                            legacy_policy
                        )
                        ledger = ChallengeLedger(clone)
                        if ledger.verify_financial_ledger() != (True, None):
                            raise RuntimeError(
                                "Challenge ledger semantic preflight did not verify"
                            )
                except (RuntimeError, TypeError, ValueError, OverflowError) as exc:
                    relative = path.relative_to(root).as_posix()
                    raise RuntimeError(
                        f"Challenge ledger semantic preflight failed for {relative}: {exc}"
                    ) from exc

        # Restore the real, root-published authorization before the first write.
        os.environ[LEDGER_HMAC_KEY_FILE_ENV] = str(integrity_key)
        if policy is not None:
            os.environ[LEDGER_MIGRATION_POLICY_FILE_ENV] = str(migration_policy)

        for path in sorted(
            databases,
            key=lambda candidate: (classifications[candidate] == "v0", candidate),
        ):
            ledger = ChallengeLedger(path)
            if ledger.verify_financial_ledger() != (True, None):
                raise RuntimeError("Migrated challenge ledger did not verify")

        # Prove every migrated database also opens in normal production mode;
        # the one-shot migration authorization must not leak into app runtime.
        os.environ.pop(LEDGER_CHECKPOINT_MIGRATION_ENV, None)
        os.environ.pop(LEDGER_MIGRATION_POLICY_FILE_ENV, None)
        receipt_databases: list[dict[str, str]] = []
        for path in databases:
            ledger = ChallengeLedger(path)
            if ledger.verify_financial_ledger() != (True, None):
                raise RuntimeError("Challenge ledger failed post-migration reopen")
            with closing(
                sqlite3.connect(_sqlite_uri(path), uri=True, timeout=30)
            ) as connection:
                connection.execute("PRAGMA query_only=ON")
                checkpoint = connection.execute(
                    """
                    SELECT record_mac FROM challenge_integrity_checkpoint
                    WHERE id=1
                    """
                ).fetchone()
            if checkpoint is None or not isinstance(checkpoint[0], str):
                raise RuntimeError("Challenge checkpoint receipt is missing")
            receipt_databases.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "checkpoint_mac": checkpoint[0],
                    "source": classifications[path],
                }
            )
    finally:
        for name, previous in previous_environment.items():
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous
    return {
        "contract_version": 1,
        "mode": "legacy-v0" if policy is not None else "verify-only",
        "database_count": len(databases),
        "databases": receipt_databases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--integrity-key", type=Path, required=True)
    parser.add_argument(
        "--offline-confirmed",
        action="store_true",
        help="Confirm that the app, timers, and workers are already stopped",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="Require every discovered ledger to be current and authenticated",
    )
    mode.add_argument(
        "--migration-policy-file",
        type=Path,
        help="Root-published in-progress policy for the one legacy v0 rollout",
    )
    args = parser.parse_args()
    if not args.offline_confirmed:
        parser.error("--offline-confirmed is required")
    receipt = migrate_challenge_ledgers(
        args.root,
        args.integrity_key,
        migration_policy=args.migration_policy_file,
    )
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
