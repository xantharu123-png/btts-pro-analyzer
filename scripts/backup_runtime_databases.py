"""Create consistent compressed backups of BetBoy runtime SQLite databases."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_PARTS = {
    ".codex_test_venv",
    ".git",
    ".pytest_cache",
    ".pytest_tmp",
    "__pycache__",
    "backups_runtime",
}
DATABASE_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3"})
INTEGRITY_KEY_ARCHIVE_PATH = "integrity/challenge-ledger-hmac.key"
MIGRATION_MARKER_ARCHIVE_PATH = (
    "integrity/challenge-ledger-v2-migrated.json"
)
PRODUCTION_BACKUP_KEY_PATH = Path(
    "/run/betboy-backup/challenge-ledger-hmac.key"
)
PRODUCTION_BACKUP_MARKER_PATH = Path(
    "/run/betboy-backup/challenge-ledger-v2-migrated.json"
)
LOCAL_INTEGRITY_KEY_RELATIVE_PATH = Path(
    "challenge_sessions/.betboy-ledger-hmac.key"
)
FINANCIAL_CHAIN_VERSION = 2
FINANCIAL_ZERO_HASH = "0" * 64
SETTLEMENT_CHAIN_VERSION = 1
SETTLEMENT_ZERO_HASH = "0" * 64
INTEGRITY_CHECKPOINT_VERSION = 2
FINANCIAL_ANCHOR_KINDS = {"OPENING_BALANCE", "MIGRATION_SNAPSHOT"}
FINANCIAL_ACCOUNT_KINDS = {"BALANCE_ADJUSTMENT", "CHALLENGE_RESET"}
FINANCIAL_TICKET_KINDS = {
    "STAKE",
    "PAYOUT",
    "LOSS_SETTLED",
    "VOID_REFUND",
    "SETTLEMENT_CORRECTION",
    "SETTLEMENT_REVERSAL",
}
FINANCIAL_ALLOWED_KINDS = (
    FINANCIAL_ANCHOR_KINDS
    | FINANCIAL_ACCOUNT_KINDS
    | FINANCIAL_TICKET_KINDS
)
VALID_STATUSES = {"PENDING", "WON", "LOST", "VOID"}
SETTLEMENT_RULE_VERSION = 2
TICKET_DEFINITION_VERSION = 3
CHALLENGE_TIMEZONE_NAME = "Europe/Zurich"
CHALLENGE_MODEL_CONTRACT_SIGNATURE = (
    "challenge-engine:hac-fdr-executable-frechet-v11"
)
SETTLEMENT_ALLOWED_SOURCES = {
    "AUTO_PROVIDER_FT",
    "MANUAL_CONFIRMED",
    "MANUAL_HISTORY",
    "MANUAL_CORRECTION",
    "MANUAL_REVERSAL",
}
LEGACY_V0_WRITER_BLOBS = {
    "f96d8b6c340c184e90d644cc310efebf963de1ad",
}


def _challenge_market_definitions() -> dict[
    str,
    tuple[str, str | None, float | None, int | None, int | None],
]:
    """Mirror the immutable v3 settlement fields without importing app code."""

    definitions = {
        "RESULT_HOME": ("result", "home", None, None, None),
        "RESULT_DRAW": ("result", "draw", None, None, None),
        "RESULT_AWAY": ("result", "away", None, None, None),
        "DC_1X": ("double_chance", "1X", None, None, None),
        "DC_X2": ("double_chance", "X2", None, None, None),
        "DC_12": ("double_chance", "12", None, None, None),
        "BTTS_YES": ("btts", "yes", None, None, None),
        "BTTS_NO": ("btts", "no", None, None, None),
    }
    for threshold in (0.5, 1.5, 2.5, 3.5, 4.5):
        token = str(threshold).replace(".", "_")
        definitions[f"TOTAL_OVER_{token}"] = (
            "total",
            "over",
            threshold,
            None,
            None,
        )
        definitions[f"TOTAL_UNDER_{token}"] = (
            "total",
            "under",
            threshold,
            None,
            None,
        )
    for team_side in ("home", "away"):
        prefix = "HOME" if team_side == "home" else "AWAY"
        for threshold in (0.5, 1.5, 2.5):
            token = str(threshold).replace(".", "_")
            definitions[f"{prefix}_OVER_{token}"] = (
                "team_total",
                f"{team_side}_over",
                threshold,
                None,
                None,
            )
            definitions[f"{prefix}_UNDER_{token}"] = (
                "team_total",
                f"{team_side}_under",
                threshold,
                None,
                None,
            )
        definitions[f"{prefix}_RANGE_1_3"] = (
            "team_range",
            team_side,
            None,
            1,
            3,
        )
        definitions[f"{prefix}_RANGE_2_4"] = (
            "team_range",
            team_side,
            None,
            2,
            4,
        )
    definitions.update(
        {
            "RESULT_TOTAL_1X_UNDER_3_5": (
                "result_total",
                "1X_under",
                3.5,
                None,
                None,
            ),
            "RESULT_TOTAL_X2_UNDER_3_5": (
                "result_total",
                "X2_under",
                3.5,
                None,
                None,
            ),
            "RESULT_TOTAL_12_OVER_1_5": (
                "result_total",
                "12_over",
                1.5,
                None,
                None,
            ),
            "MIXED_BTTS_OR_OVER_2_5": (
                "mixed_or",
                "btts_yes_or_over",
                2.5,
                None,
                None,
            ),
            "MIXED_HOME_OR_OVER_2_5": (
                "mixed_or",
                "home_or_over",
                2.5,
                None,
                None,
            ),
            "MIXED_AWAY_OR_OVER_2_5": (
                "mixed_or",
                "away_or_over",
                2.5,
                None,
                None,
            ),
        }
    )
    for threshold in (5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5):
        token = str(threshold).replace(".", "_")
        definitions[f"CORNERS_OVER_{token}"] = (
            "corner_total",
            "over",
            threshold,
            None,
            None,
        )
        definitions[f"CORNERS_UNDER_{token}"] = (
            "corner_total",
            "under",
            threshold,
            None,
            None,
        )
    for team_side in ("home", "away"):
        prefix = "HOME_CORNERS" if team_side == "home" else "AWAY_CORNERS"
        for threshold in (2.5, 3.5, 4.5, 5.5):
            token = str(threshold).replace(".", "_")
            definitions[f"{prefix}_OVER_{token}"] = (
                "team_corners",
                f"{team_side}_over",
                threshold,
                None,
                None,
            )
            definitions[f"{prefix}_UNDER_{token}"] = (
                "team_corners",
                f"{team_side}_under",
                threshold,
                None,
                None,
            )
    for threshold in (1.5, 2.5, 3.5, 4.5):
        token = str(threshold).replace(".", "_")
        definitions[f"YELLOW_OVER_{token}"] = (
            "yellow_total",
            "over",
            threshold,
            None,
            None,
        )
        definitions[f"YELLOW_UNDER_{token}"] = (
            "yellow_total",
            "under",
            threshold,
            None,
            None,
        )
    for team_side in ("home", "away"):
        prefix = "HOME_YELLOW" if team_side == "home" else "AWAY_YELLOW"
        for threshold in (0.5, 1.5, 2.5):
            token = str(threshold).replace(".", "_")
            definitions[f"{prefix}_OVER_{token}"] = (
                "team_yellow",
                f"{team_side}_over",
                threshold,
                None,
                None,
            )
            definitions[f"{prefix}_UNDER_{token}"] = (
                "team_yellow",
                f"{team_side}_under",
                threshold,
                None,
                None,
            )
    return definitions


CHALLENGE_MARKET_DEFINITIONS = _challenge_market_definitions()


def _fsync_file(path: Path) -> None:
    """Persist one completed file before publishing its directory entry."""
    # Windows needs a writable descriptor for fsync; the archive is still
    # private and unpublished at this point.
    with path.open("rb+") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    """Persist directory-entry changes on platforms that support it."""
    if os.name == "nt":
        return
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validated_application_root(root: Path) -> Path:
    lexical = Path(os.path.abspath(os.fspath(root)))
    if lexical.is_symlink():
        raise RuntimeError("Backup root must not be a symlink")
    resolved = lexical.resolve(strict=True)
    if resolved != lexical:
        raise RuntimeError("Backup root must not traverse a symlink")
    root_info = os.lstat(resolved)
    if not stat.S_ISDIR(root_info.st_mode):
        raise RuntimeError("Backup root must be a real directory")
    return resolved


def discover_databases(root: Path = ROOT) -> list[Path]:
    resolved_root = _validated_application_root(root)
    databases: list[Path] = []
    for directory, dirnames, filenames in os.walk(
        resolved_root,
        topdown=True,
        followlinks=False,
    ):
        current = Path(directory)
        kept: list[str] = []
        for name in dirnames:
            child = current / name
            if name in EXCLUDED_PARTS:
                continue
            child_info = os.lstat(child)
            if stat.S_ISLNK(child_info.st_mode):
                raise RuntimeError("Backup database path must not traverse a symlink")
            if not stat.S_ISDIR(child_info.st_mode):
                raise RuntimeError("Backup traversal encountered a non-directory")
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            path = current / name
            if path.suffix.casefold() not in DATABASE_SUFFIXES:
                continue
            info = os.lstat(path)
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or info.st_nlink != 1
            ):
                raise RuntimeError(
                    "Backup database must be one regular, non-linked file"
                )
            try:
                path.resolve(strict=True).relative_to(resolved_root)
            except ValueError as exc:
                raise RuntimeError("Backup database escapes its application root") from exc
            databases.append(path)
    return sorted(databases)


def backup_database(source: Path, destination: Path) -> None:
    info = os.lstat(source)
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_nlink != 1
    ):
        raise RuntimeError("Backup database must be one regular, non-linked file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source.resolve().as_posix()}?mode=ro"
    with closing(
        sqlite3.connect(source_uri, uri=True, timeout=30)
    ) as source_conn:
        with closing(sqlite3.connect(destination)) as destination_conn:
            source_conn.backup(destination_conn)


def _read_integrity_key(path: Path) -> bytes:
    """Read one key without following symlinks or accepting loose formats."""

    if path.is_symlink():
        raise RuntimeError("Ledger integrity key must not be a symlink")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError("Ledger integrity key cannot be opened safely") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RuntimeError("Ledger integrity key must be one regular file")
        if (
            os.name != "nt"
            and Path(os.path.abspath(os.fspath(path)))
            == PRODUCTION_BACKUP_KEY_PATH
        ):
            import grp

            if (
                info.st_uid != 0
                or info.st_gid != grp.getgrnam("betboy").gr_gid
                or stat.S_IMODE(info.st_mode) != 0o640
            ):
                raise RuntimeError(
                    "Production ledger integrity key must be root:betboy mode 0640"
                )
        raw = os.read(descriptor, 1024)
        if os.read(descriptor, 1):
            raise RuntimeError("Ledger integrity key is unexpectedly large")
    finally:
        os.close(descriptor)
    _validate_integrity_key_bytes(raw)
    return raw


def _validate_integrity_key_bytes(raw: bytes) -> None:
    if (
        len(raw) != 65
        or not raw.endswith(b"\n")
        or any(byte not in b"0123456789abcdef" for byte in raw[:-1])
    ):
        raise RuntimeError("Ledger integrity key has an invalid format")


def _decoded_integrity_key(raw: bytes) -> bytes:
    _validate_integrity_key_bytes(raw)
    return bytes.fromhex(raw[:-1].decode("ascii"))


def _sqlite_integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise RuntimeError(f"{label} must use SQLite INTEGER storage")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _challenge_schema_manifest(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master"
    ).fetchall()
    manifest = [
        {
            "type": str(row["type"]),
            "name": str(row["name"]),
            "table": str(row["tbl_name"]),
            "sql": row["sql"],
        }
        for row in rows
    ]
    return sorted(
        manifest,
        key=lambda record: (
            str(record["type"]),
            str(record["name"]),
            str(record["table"]),
        ),
    )


def _challenge_schema_manifest_hash(connection: sqlite3.Connection) -> str:
    return hashlib.sha256(
        _canonical_json(_challenge_schema_manifest(connection)).encode("utf-8")
    ).hexdigest()


def _challenge_sequence_state(
    connection: sqlite3.Connection,
) -> list[dict[str, object]]:
    present = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
    ).fetchone()
    if present is None:
        return []
    autoincrement_tables = {
        str(row["name"])
        for row in connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table'"
        )
        if not str(row["name"]).startswith("sqlite_")
        and isinstance(row["sql"], str)
        and "AUTOINCREMENT" in str(row["sql"]).upper()
    }
    rows = connection.execute(
        "SELECT name, seq FROM sqlite_sequence ORDER BY name ASC"
    ).fetchall()
    names = [str(row["name"]) for row in rows]
    if len(names) != len(set(names)) or not set(names) <= autoincrement_tables:
        raise RuntimeError("challenge sequence inventory is invalid")
    state: list[dict[str, object]] = []
    for row in rows:
        name = str(row["name"])
        sequence = _sqlite_integer(row["seq"], f"{name} sequence")
        if sequence < 0:
            raise RuntimeError(f"{name} sequence must be non-negative")
        quoted_name = name.replace('"', '""')
        maximum = _sqlite_integer(
            connection.execute(
                f'SELECT COALESCE(MAX(rowid), 0) FROM "{quoted_name}"'
            ).fetchone()[0],
            f"{name} maximum rowid",
        )
        if sequence < maximum:
            raise RuntimeError(f"{name} sequence is behind its table")
        state.append({"name": name, "sequence": sequence})
    return state


def _hmac_hex(key: bytes, domain: str, payload: dict[str, object]) -> str:
    message = _canonical_json({"domain": domain, "payload": payload})
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def _require_timestamp(value: object, label: str) -> None:
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} must be an ISO-8601 timestamp") from exc
    if timestamp.tzinfo is None:
        raise RuntimeError(f"{label} must include a timezone")


def _normalized_timestamp(value: object, label: str) -> str:
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} must be an ISO-8601 timestamp") from exc
    if timestamp.tzinfo is None:
        raise RuntimeError(f"{label} must include a timezone")
    return timestamp.astimezone(timezone.utc).isoformat()


def _financial_record_mac(key: bytes, row: sqlite3.Row) -> str:
    ticket_id = (
        _sqlite_integer(row["ticket_id"], "financial ticket_id")
        if row["ticket_id"] is not None
        else None
    )
    return _hmac_hex(
        key,
        "betboy.challenge.financial.v2",
        {
            "created_at": str(row["created_at"]),
            "kind": str(row["kind"]),
            "amount_cents": _sqlite_integer(
                row["amount_cents"], "financial amount_cents"
            ),
            "balance_after_cents": _sqlite_integer(
                row["balance_after_cents"], "financial balance_after_cents"
            ),
            "ticket_id": ticket_id,
            "note": str(row["note"]) if row["note"] is not None else None,
            "previous_hash": str(row["previous_hash"]),
            "chain_version": _sqlite_integer(
                row["chain_version"], "financial chain_version"
            ),
        },
    )


def _settlement_record_mac(key: bytes, row: sqlite3.Row) -> str:
    return _hmac_hex(
        key,
        "betboy.challenge.settlement.v1",
        {
            "ticket_id": _sqlite_integer(
                row["ticket_id"], "settlement ticket_id"
            ),
            "created_at": str(row["created_at"]),
            "action": str(row["action"]),
            "previous_status": (
                str(row["previous_status"])
                if row["previous_status"] is not None
                else None
            ),
            "new_status": str(row["new_status"]),
            "previous_payout_cents": _sqlite_integer(
                row["previous_payout_cents"],
                "settlement previous_payout_cents",
            ),
            "new_payout_cents": _sqlite_integer(
                row["new_payout_cents"], "settlement new_payout_cents"
            ),
            "settlement_odds": (
                float(row["settlement_odds"])
                if row["settlement_odds"] is not None
                else None
            ),
            "rule_version": _sqlite_integer(
                row["rule_version"], "settlement rule_version"
            ),
            "source": str(row["source"]),
            "reason": str(row["reason"]),
            "previous_hash": str(row["previous_hash"]),
            "chain_version": _sqlite_integer(
                row["chain_version"], "settlement chain_version"
            ),
        },
    )


def _verify_financial_chain(connection: sqlite3.Connection, key: bytes) -> None:
    settings = connection.execute(
        """
        SELECT current_balance_cents, financial_chain_version,
               financial_anchor_hash
        FROM challenge_settings WHERE id=1
        """
    ).fetchone()
    rows = connection.execute(
        "SELECT * FROM challenge_transactions ORDER BY id ASC"
    ).fetchall()
    if settings is None or not rows:
        raise RuntimeError("Authenticated financial ledger has no anchor")
    if _sqlite_integer(
        settings["financial_chain_version"], "settings financial_chain_version"
    ) != FINANCIAL_CHAIN_VERSION:
        raise RuntimeError("Authenticated financial ledger has the wrong version")
    known_ticket_ids = {
        _sqlite_integer(row["id"], "ticket id")
        for row in connection.execute("SELECT id FROM challenge_tickets")
    }
    expected_previous = FINANCIAL_ZERO_HASH
    running_balance: int | None = None
    for index, row in enumerate(rows):
        row_id = _sqlite_integer(row["id"], "financial transaction id")
        kind = str(row["kind"])
        amount = _sqlite_integer(row["amount_cents"], "financial amount_cents")
        balance_after = _sqlite_integer(
            row["balance_after_cents"], "financial balance_after_cents"
        )
        ticket_id = (
            _sqlite_integer(row["ticket_id"], "financial ticket_id")
            if row["ticket_id"] is not None
            else None
        )
        chain_version = _sqlite_integer(
            row["chain_version"], "financial chain_version"
        )
        previous_hash = str(row["previous_hash"] or "")
        record_hash = str(row["record_hash"] or "")
        _require_timestamp(row["created_at"], "financial created_at")
        if (
            kind not in FINANCIAL_ALLOWED_KINDS
            or chain_version != FINANCIAL_CHAIN_VERSION
            or previous_hash != expected_previous
            or len(record_hash) != 64
            or any(character not in "0123456789abcdef" for character in record_hash)
            or not hmac.compare_digest(record_hash, _financial_record_mac(key, row))
        ):
            raise RuntimeError(
                f"Authenticated financial HMAC chain failed at record {row_id}"
            )
        if kind in FINANCIAL_ANCHOR_KINDS | FINANCIAL_ACCOUNT_KINDS:
            if ticket_id is not None:
                raise RuntimeError("Authenticated financial record has an invalid ticket")
        elif ticket_id is None or ticket_id <= 0 or ticket_id not in known_ticket_ids:
            raise RuntimeError("Authenticated financial record lacks its ticket")
        if (
            (kind == "STAKE" and amount >= 0)
            or (kind == "PAYOUT" and amount <= 0)
            or (kind == "LOSS_SETTLED" and amount != 0)
            or (kind == "VOID_REFUND" and amount <= 0)
            or (kind == "SETTLEMENT_REVERSAL" and amount > 0)
        ):
            raise RuntimeError("Authenticated financial record has invalid semantics")
        if index == 0:
            if (
                kind not in FINANCIAL_ANCHOR_KINDS
                or (kind == "OPENING_BALANCE" and amount != balance_after)
                or (kind == "MIGRATION_SNAPSHOT" and amount != 0)
            ):
                raise RuntimeError("Authenticated financial anchor is invalid")
        elif (
            running_balance is None
            or kind in FINANCIAL_ANCHOR_KINDS
            or balance_after != running_balance + amount
        ):
            raise RuntimeError("Authenticated financial balance chain is invalid")
        running_balance = balance_after
        expected_previous = record_hash
    if not hmac.compare_digest(
        str(settings["financial_anchor_hash"] or ""),
        str(rows[0]["record_hash"] or ""),
    ):
        raise RuntimeError("Authenticated financial anchor HMAC is invalid")
    if _sqlite_integer(
        settings["current_balance_cents"], "settings current_balance_cents"
    ) != running_balance:
        raise RuntimeError("Authenticated financial balance disagrees with settings")


def _verify_settlement_chain(connection: sqlite3.Connection, key: bytes) -> None:
    settings = connection.execute(
        """
        SELECT settlement_chain_version, settlement_anchor_hash
        FROM challenge_settings WHERE id=1
        """
    ).fetchone()
    if settings is None or _sqlite_integer(
        settings["settlement_chain_version"], "settings settlement_chain_version"
    ) != SETTLEMENT_CHAIN_VERSION:
        raise RuntimeError("Authenticated settlement ledger has the wrong version")
    known_ticket_ids = {
        _sqlite_integer(row["id"], "ticket id")
        for row in connection.execute("SELECT id FROM challenge_tickets")
    }
    rows = connection.execute(
        "SELECT * FROM challenge_settlement_events ORDER BY id ASC"
    ).fetchall()
    expected_previous = SETTLEMENT_ZERO_HASH
    for row in rows:
        row_id = _sqlite_integer(row["id"], "settlement event id")
        ticket_id = _sqlite_integer(row["ticket_id"], "settlement ticket id")
        action = str(row["action"])
        previous_status = row["previous_status"]
        new_status = str(row["new_status"])
        previous_payout = _sqlite_integer(
            row["previous_payout_cents"], "settlement previous_payout_cents"
        )
        new_payout = _sqlite_integer(
            row["new_payout_cents"], "settlement new_payout_cents"
        )
        rule_version = _sqlite_integer(
            row["rule_version"], "settlement rule_version"
        )
        source = str(row["source"])
        reason = str(row["reason"])
        chain_version = _sqlite_integer(
            row["chain_version"], "settlement chain_version"
        )
        previous_hash = str(row["previous_hash"] or "")
        record_hash = str(row["record_hash"] or "")
        _require_timestamp(row["created_at"], "settlement created_at")
        if (
            ticket_id <= 0
            or ticket_id not in known_ticket_ids
            or action not in {"SETTLE", "CORRECT", "REVERSE"}
            or previous_status not in {None, "PENDING", "WON", "LOST", "VOID"}
            or new_status not in VALID_STATUSES
            or previous_payout < 0
            or new_payout < 0
            or rule_version != SETTLEMENT_RULE_VERSION
            or source not in SETTLEMENT_ALLOWED_SOURCES
            or source != source.strip()
            or not reason.strip()
            or reason != reason.strip()
            or chain_version != SETTLEMENT_CHAIN_VERSION
            or previous_hash != expected_previous
            or len(record_hash) != 64
            or any(character not in "0123456789abcdef" for character in record_hash)
            or not hmac.compare_digest(record_hash, _settlement_record_mac(key, row))
        ):
            raise RuntimeError(
                f"Authenticated settlement HMAC chain failed at record {row_id}"
            )
        expected_previous = record_hash
    anchor = str(settings["settlement_anchor_hash"] or "")
    if rows:
        if not hmac.compare_digest(anchor, str(rows[0]["record_hash"] or "")):
            raise RuntimeError("Authenticated settlement anchor HMAC is invalid")
    elif anchor:
        raise RuntimeError("Empty authenticated settlement chain has an anchor")


def _validated_decimal_odds(value: object) -> float:
    if isinstance(value, bool):
        raise RuntimeError("Settlement odds must be numeric")
    try:
        odds = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Settlement odds must be numeric") from exc
    if not math.isfinite(odds) or odds <= 1.0:
        raise RuntimeError("Settlement odds must be finite and greater than one")
    return odds


def _verify_settlement_replay(connection: sqlite3.Connection) -> None:
    """Replay every v3 ticket against its events and money movements."""

    tickets = connection.execute(
        """
        SELECT * FROM challenge_tickets
        WHERE COALESCE(definition_version, 0) >= 3
        ORDER BY id ASC
        """
    ).fetchall()
    for ticket in tickets:
        ticket_id = _sqlite_integer(ticket["id"], "ticket id")
        stake_cents = _sqlite_integer(ticket["stake_cents"], "ticket stake_cents")
        payout_cents = _sqlite_integer(
            ticket["payout_cents"], "ticket payout_cents"
        )
        ticket_rule = _sqlite_integer(
            ticket["settlement_rule_version"],
            "ticket settlement_rule_version",
        )
        transactions = connection.execute(
            """
            SELECT * FROM challenge_transactions
            WHERE ticket_id=? ORDER BY id ASC
            """,
            (ticket_id,),
        ).fetchall()
        stake_rows = [row for row in transactions if row["kind"] == "STAKE"]
        settlement_rows = [row for row in transactions if row["kind"] != "STAKE"]
        bad_id = (
            _sqlite_integer(transactions[-1]["id"], "transaction id")
            if transactions
            else None
        )
        stake_amount = (
            _sqlite_integer(
                stake_rows[0]["amount_cents"], "stake transaction amount_cents"
            )
            if len(stake_rows) == 1
            else None
        )
        if (
            len(stake_rows) != 1
            or stake_amount != -stake_cents
            or str(stake_rows[0]["created_at"]) != str(ticket["created_at"])
        ):
            raise RuntimeError(
                f"Authenticated settlement replay has an invalid stake at {bad_id}"
            )
        events = connection.execute(
            """
            SELECT * FROM challenge_settlement_events
            WHERE ticket_id=? ORDER BY id ASC
            """,
            (ticket_id,),
        ).fetchall()
        if len(events) != len(settlement_rows):
            raise RuntimeError(
                f"Authenticated settlement replay count mismatch at {bad_id}"
            )
        entry_source = str(ticket["entry_source"] or "")
        if entry_source == "MODEL":
            state: str | None = "PENDING"
        elif entry_source == "MANUAL":
            state = None
        else:
            raise RuntimeError("Authenticated ticket has an invalid entry source")
        payout = 0
        latest_event: sqlite3.Row | None = None
        for event_index, (event, transaction) in enumerate(
            zip(events, settlement_rows)
        ):
            transaction_id = _sqlite_integer(transaction["id"], "transaction id")
            transaction_amount = _sqlite_integer(
                transaction["amount_cents"],
                "settlement transaction amount_cents",
            )
            _sqlite_integer(event["id"], "settlement event id")
            _sqlite_integer(event["ticket_id"], "settlement event ticket_id")
            action = str(event["action"])
            previous_status = event["previous_status"]
            new_status = str(event["new_status"])
            previous_payout = _sqlite_integer(
                event["previous_payout_cents"],
                "settlement event previous_payout_cents",
            )
            new_payout = _sqlite_integer(
                event["new_payout_cents"],
                "settlement event new_payout_cents",
            )
            event_rule = _sqlite_integer(
                event["rule_version"], "settlement event rule_version"
            )
            _sqlite_integer(event["chain_version"], "settlement event chain_version")
            if (
                event_rule != SETTLEMENT_RULE_VERSION
                or not str(event["source"] or "").strip()
                or not str(event["reason"] or "").strip()
                or previous_payout != payout
                or str(transaction["created_at"]) != str(event["created_at"])
            ):
                raise RuntimeError(
                    f"Authenticated settlement replay failed at {transaction_id}"
                )
            if action == "SETTLE":
                manual_first = (
                    event_index == 0
                    and entry_source == "MANUAL"
                    and state is None
                    and previous_status is None
                )
                if not manual_first and (
                    state != "PENDING" or previous_status != "PENDING"
                ):
                    raise RuntimeError(
                        f"Authenticated SETTLE transition failed at {transaction_id}"
                    )
                if new_status not in {"WON", "LOST", "VOID"}:
                    raise RuntimeError("Authenticated SETTLE status is invalid")
                expected_kind = {
                    "WON": "PAYOUT",
                    "LOST": "LOSS_SETTLED",
                    "VOID": "VOID_REFUND",
                }[new_status]
            elif action == "CORRECT":
                if (
                    state not in {"WON", "LOST", "VOID"}
                    or previous_status != state
                    or new_status not in {"WON", "LOST", "VOID"}
                ):
                    raise RuntimeError(
                        f"Authenticated CORRECT transition failed at {transaction_id}"
                    )
                expected_kind = "SETTLEMENT_CORRECTION"
            elif action == "REVERSE":
                if (
                    state not in {"WON", "LOST", "VOID"}
                    or previous_status != state
                    or new_status != "PENDING"
                    or new_payout != 0
                    or event["settlement_odds"] is not None
                ):
                    raise RuntimeError(
                        f"Authenticated REVERSE transition failed at {transaction_id}"
                    )
                expected_kind = "SETTLEMENT_REVERSAL"
            else:
                raise RuntimeError("Authenticated settlement action is invalid")
            settlement_odds = event["settlement_odds"]
            if new_status == "WON":
                effective_odds = _validated_decimal_odds(settlement_odds)
                calculated_payout = int(
                    (
                        Decimal(stake_cents) * Decimal(str(effective_odds))
                    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                )
                if abs(new_payout - calculated_payout) > 1:
                    raise RuntimeError("Authenticated won payout is invalid")
            elif new_status == "LOST":
                if new_payout != 0 or settlement_odds is not None:
                    raise RuntimeError("Authenticated lost payout is invalid")
            elif new_status == "VOID":
                if new_payout != stake_cents or settlement_odds is not None:
                    raise RuntimeError("Authenticated void payout is invalid")
            elif new_status == "PENDING":
                if new_payout != 0 or settlement_odds is not None:
                    raise RuntimeError("Authenticated pending payout is invalid")
            else:
                raise RuntimeError("Authenticated replay status is invalid")
            if (
                str(transaction["kind"]) != expected_kind
                or transaction_amount != new_payout - payout
            ):
                raise RuntimeError(
                    f"Authenticated settlement money row failed at {transaction_id}"
                )
            state = new_status
            payout = new_payout
            latest_event = event
        materialized_status = str(ticket["status"])
        if entry_source == "MANUAL" and latest_event is None:
            raise RuntimeError("Authenticated manual ticket lacks settlement history")
        if state is None or materialized_status != state or payout_cents != payout:
            raise RuntimeError("Authenticated materialized ticket state is inconsistent")
        if ticket_rule != SETTLEMENT_RULE_VERSION:
            raise RuntimeError("Authenticated ticket settlement rule is invalid")
        if state == "PENDING":
            if ticket["settled_at"] is not None or ticket["settlement_odds"] is not None:
                raise RuntimeError("Authenticated pending ticket is materialized as settled")
            if latest_event is None:
                if ticket["settlement_note"] is not None:
                    raise RuntimeError("Authenticated pending ticket has a stray note")
            elif (
                latest_event["action"] != "REVERSE"
                or str(ticket["settlement_note"] or "").strip()
                != str(latest_event["reason"] or "").strip()
            ):
                raise RuntimeError("Authenticated reversal note is inconsistent")
        elif latest_event is None or (
            str(ticket["settled_at"]) != str(latest_event["created_at"])
            or ticket["settlement_odds"] != latest_event["settlement_odds"]
            or str(ticket["settlement_note"] or "").strip()
            != str(latest_event["reason"] or "").strip()
        ):
            raise RuntimeError("Authenticated settled ticket snapshot is inconsistent")


def _verify_ticket_definitions(connection: sqlite3.Connection) -> None:
    for row in connection.execute("SELECT * FROM challenge_tickets ORDER BY id"):
        _sqlite_integer(row["id"], "ticket id")
        stake_cents = _sqlite_integer(row["stake_cents"], "ticket stake_cents")
        _sqlite_integer(row["payout_cents"], "ticket payout_cents")
        _sqlite_integer(
            row["settlement_rule_version"], "ticket settlement_rule_version"
        )
        definition_version = _sqlite_integer(
            row["definition_version"], "ticket definition_version"
        )
        if definition_version > TICKET_DEFINITION_VERSION:
            raise RuntimeError("Authenticated ticket definition version is unsupported")
        try:
            legs = json.loads(row["legs_json"])
            quote_evidence = json.loads(row["quote_evidence_json"] or "[]")
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Authenticated ticket JSON is corrupt") from exc
        if not isinstance(legs, list) or not isinstance(quote_evidence, list):
            raise RuntimeError("Authenticated ticket evidence shape is invalid")
        evidence_json = _canonical_json(quote_evidence)
        evidence_hash = row["quote_evidence_hash"]
        if evidence_hash and evidence_hash != hashlib.sha256(
            evidence_json.encode("utf-8")
        ).hexdigest():
            raise RuntimeError("Authenticated quote evidence hash failed")
        entry_source = str(row["entry_source"] or "")
        model_signature = row["model_contract_signature"]
        if definition_version < 3 and entry_source != "MANUAL":
            raise RuntimeError("Authenticated legacy ticket is not manual")
        if definition_version >= 3:
            if not row["ticket_definition_hash"] or stake_cents <= 0:
                raise RuntimeError("Authenticated ticket definition is incomplete")
            _require_timestamp(row["created_at"], "ticket created_at")
            if row["analysis_timezone"] != CHALLENGE_TIMEZONE_NAME:
                raise RuntimeError("Authenticated ticket timezone is invalid")
            if entry_source == "MODEL":
                if (
                    model_signature != CHALLENGE_MODEL_CONTRACT_SIGNATURE
                    or not evidence_hash
                    or len(quote_evidence) != len(legs)
                    or not all(isinstance(record, dict) and record for record in quote_evidence)
                ):
                    raise RuntimeError("Authenticated model ticket provenance is invalid")
            elif entry_source == "MANUAL":
                if model_signature is not None:
                    raise RuntimeError("Authenticated manual ticket claims a model")
            else:
                raise RuntimeError("Authenticated ticket entry source is invalid")
        reference_odds = float(row["total_odds"])
        played_odds = float(row["played_odds"] or reference_odds)
        payload: dict[str, object] = {
            "analysis_date": str(row["analysis_date"]),
            "legs": legs,
            "quote_evidence": quote_evidence,
            "reference_total_odds": reference_odds,
            "played_total_odds": played_odds,
            "joint_probability": float(row["joint_probability"]),
            "expected_roi": float(row["expected_roi"]),
            "definition_version": definition_version,
        }
        if definition_version >= 3:
            payload.update(
                {
                    "stake_cents": stake_cents,
                    "created_at": str(row["created_at"]),
                    "quote_verified_at": _normalized_timestamp(
                        row["quote_verified_at"], "ticket quote_verified_at"
                    ),
                    "analysis_timezone": CHALLENGE_TIMEZONE_NAME,
                    "entry_source": entry_source,
                    "model_contract_signature": model_signature,
                }
            )
        expected_hash = hashlib.sha256(
            _canonical_json(payload).encode("utf-8")
        ).hexdigest()
        if row["ticket_definition_hash"] and not hmac.compare_digest(
            str(row["ticket_definition_hash"]), expected_hash
        ):
            raise RuntimeError("Authenticated ticket definition hash failed")
        if entry_source == "MODEL" and not math.isclose(
            float(row["expected_roi"]),
            float(row["joint_probability"]) * played_odds - 1.0,
            abs_tol=5e-7,
        ):
            raise RuntimeError("Authenticated ticket ROI is inconsistent")
        if definition_version >= TICKET_DEFINITION_VERSION:
            for leg in legs:
                if not isinstance(leg, dict):
                    raise RuntimeError("Authenticated ticket leg is invalid")
                if leg.get("manual"):
                    if (
                        leg.get("market_key") != "MANUAL"
                        or leg.get("market_kind") != "manual"
                        or leg.get("settlement_rule_version")
                        != SETTLEMENT_RULE_VERSION
                    ):
                        raise RuntimeError(
                            "Authenticated manual ticket definition is invalid"
                        )
                    continue
                definition = CHALLENGE_MARKET_DEFINITIONS.get(
                    str(leg.get("market_key") or "")
                )
                if definition is None or (
                    leg.get("market_kind"),
                    leg.get("market_side"),
                    leg.get("market_threshold"),
                    leg.get("market_low"),
                    leg.get("market_high"),
                ) != definition or (
                    leg.get("settlement_rule_version")
                    != SETTLEMENT_RULE_VERSION
                ):
                    raise RuntimeError(
                        "Authenticated challenge market definition is invalid"
                    )


def _checkpoint_state(
    connection: sqlite3.Connection,
    ledger_scope: str,
) -> dict[str, object]:
    settings = connection.execute(
        "SELECT * FROM challenge_settings WHERE id=1"
    ).fetchone()
    if settings is None:
        raise RuntimeError("Authenticated challenge settings are missing")
    financial_tail = connection.execute(
        "SELECT record_hash FROM challenge_transactions ORDER BY id DESC LIMIT 1"
    ).fetchone()
    settlement_tail = connection.execute(
        "SELECT record_hash FROM challenge_settlement_events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    financial_count = _sqlite_integer(
        connection.execute("SELECT COUNT(*) FROM challenge_transactions").fetchone()[0],
        "financial row count",
    )
    settlement_count = _sqlite_integer(
        connection.execute("SELECT COUNT(*) FROM challenge_settlement_events").fetchone()[0],
        "settlement row count",
    )
    ticket_count = _sqlite_integer(
        connection.execute("SELECT COUNT(*) FROM challenge_tickets").fetchone()[0],
        "ticket row count",
    )
    financial_ids = [
        _sqlite_integer(row["id"], "financial transaction id")
        for row in connection.execute(
            "SELECT id FROM challenge_transactions ORDER BY id ASC"
        )
    ]
    settlement_ids = [
        _sqlite_integer(row["id"], "settlement event id")
        for row in connection.execute(
            "SELECT id FROM challenge_settlement_events ORDER BY id ASC"
        )
    ]
    price_rows = connection.execute(
        "SELECT id, record_hash FROM price_observations ORDER BY id ASC"
    ).fetchall()
    price_ids = [
        _sqlite_integer(row["id"], "price observation id")
        for row in price_rows
    ]
    tickets: list[dict[str, object]] = []
    for row in connection.execute(
        """
        SELECT id, analysis_date, analysis_timezone, created_at,
               quote_verified_at, settled_at, status, stake_cents,
               payout_cents, total_odds, played_odds, joint_probability,
               expected_roi, legs_json, entry_source, settlement_odds,
               settlement_rule_version, settlement_note,
               quote_evidence_json, quote_evidence_hash,
               ticket_definition_hash, model_contract_signature,
               definition_version
        FROM challenge_tickets ORDER BY id ASC
        """
    ):
        tickets.append(
            {
                "id": _sqlite_integer(row["id"], "ticket id"),
                "analysis_date": row["analysis_date"],
                "analysis_timezone": row["analysis_timezone"],
                "created_at": row["created_at"],
                "quote_verified_at": row["quote_verified_at"],
                "settled_at": row["settled_at"],
                "status": row["status"],
                "stake_cents": _sqlite_integer(row["stake_cents"], "ticket stake_cents"),
                "payout_cents": _sqlite_integer(
                    row["payout_cents"], "ticket payout_cents"
                ),
                "total_odds": row["total_odds"],
                "played_odds": row["played_odds"],
                "joint_probability": row["joint_probability"],
                "expected_roi": row["expected_roi"],
                "legs_json": row["legs_json"],
                "entry_source": row["entry_source"],
                "settlement_odds": row["settlement_odds"],
                "settlement_rule_version": _sqlite_integer(
                    row["settlement_rule_version"],
                    "ticket settlement_rule_version",
                ),
                "settlement_note": row["settlement_note"],
                "quote_evidence_json": row["quote_evidence_json"],
                "quote_evidence_hash": row["quote_evidence_hash"],
                "ticket_definition_hash": row["ticket_definition_hash"],
                "model_contract_signature": row["model_contract_signature"],
                "definition_version": _sqlite_integer(
                    row["definition_version"], "ticket definition_version"
                ),
            }
        )
    return {
        "ledger_scope": ledger_scope,
        "schema_manifest_hash": _challenge_schema_manifest_hash(connection),
        "sequences": _challenge_sequence_state(connection),
        "price_observation_count": len(price_ids),
        "price_observation_ids": price_ids,
        "price_observation_tail_hash": (
            str(price_rows[-1]["record_hash"] or "")
            if price_rows
            else "0" * 64
        ),
        "financial_count": financial_count,
        "financial_ids": financial_ids,
        "financial_tail_hash": (
            str(financial_tail["record_hash"] or "")
            if financial_tail is not None
            else FINANCIAL_ZERO_HASH
        ),
        "settlement_count": settlement_count,
        "settlement_ids": settlement_ids,
        "settlement_tail_hash": (
            str(settlement_tail["record_hash"] or "")
            if settlement_tail is not None
            else SETTLEMENT_ZERO_HASH
        ),
        "ticket_count": ticket_count,
        "settings": {
            "starting_balance_cents": _sqlite_integer(
                settings["starting_balance_cents"], "settings starting_balance_cents"
            ),
            "current_balance_cents": _sqlite_integer(
                settings["current_balance_cents"], "settings current_balance_cents"
            ),
            "target_balance_cents": _sqlite_integer(
                settings["target_balance_cents"], "settings target_balance_cents"
            ),
            "stake_fraction_bps": _sqlite_integer(
                settings["stake_fraction_bps"], "settings stake_fraction_bps"
            ),
            "stake_policy_version": _sqlite_integer(
                settings["stake_policy_version"], "settings stake_policy_version"
            ),
            "financial_chain_version": _sqlite_integer(
                settings["financial_chain_version"],
                "settings financial_chain_version",
            ),
            "financial_anchor_hash": settings["financial_anchor_hash"],
            "settlement_chain_version": _sqlite_integer(
                settings["settlement_chain_version"],
                "settings settlement_chain_version",
            ),
            "settlement_anchor_hash": settings["settlement_anchor_hash"],
            "updated_at": settings["updated_at"],
        },
        "tickets": tickets,
    }


def _verify_price_chain(connection: sqlite3.Connection) -> None:
    expected_previous = "0" * 64
    for row in connection.execute(
        "SELECT * FROM price_observations ORDER BY id ASC"
    ):
        payload = {
            "recorded_at": row["recorded_at"],
            "captured_at": row["captured_at"],
            "bookmaker": row["bookmaker"],
            "sport": row["sport"],
            "event_id": row["event_id"],
            "event_name": row["event_name"],
            "scheduled_start": row["scheduled_start"],
            "market_key": row["market_key"],
            "market_name": row["market_name"],
            "selection_key": row["selection_key"],
            "selection_name": row["selection_name"],
            "line_micros": row["line_micros"],
            "odds_micros": row["odds_micros"],
            "phase": row["phase"],
            "source": row["source"],
            "model_ref": row["model_ref"],
            "supersedes_id": row["supersedes_id"],
            "metadata_json": row["metadata_json"],
            "previous_hash": row["previous_hash"],
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        expected_hash = hashlib.sha256(encoded).hexdigest()
        if (
            str(row["previous_hash"] or "") != expected_previous
            or not hmac.compare_digest(
                str(row["record_hash"] or ""),
                expected_hash,
            )
        ):
            raise RuntimeError("Price observation hash chain failed")
        expected_previous = expected_hash


def verify_current_challenge_database(
    path: Path,
    integrity_key_bytes: bytes,
    *,
    ledger_scope: str,
) -> None:
    """Verify HMAC chains and the signed whole-ledger checkpoint read-only."""

    key = _decoded_integrity_key(integrity_key_bytes)
    uri = path.resolve(strict=True).as_uri() + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=30)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            _verify_price_chain(connection)
            _verify_financial_chain(connection, key)
            _verify_settlement_chain(connection, key)
            _verify_ticket_definitions(connection)
            _verify_settlement_replay(connection)
            rows = connection.execute(
                "SELECT * FROM challenge_integrity_checkpoint ORDER BY id"
            ).fetchall()
            if len(rows) != 1 or _sqlite_integer(rows[0]["id"], "checkpoint id") != 1:
                raise RuntimeError("Authenticated integrity checkpoint is ambiguous")
            checkpoint = rows[0]
            state = _checkpoint_state(connection, ledger_scope)
            expected_mac = _hmac_hex(
                key,
                "betboy.challenge.current-state.v2",
                {
                    "checkpoint_version": INTEGRITY_CHECKPOINT_VERSION,
                    **state,
                },
            )
            if (
                _sqlite_integer(
                    checkpoint["checkpoint_version"], "checkpoint version"
                )
                != INTEGRITY_CHECKPOINT_VERSION
                or _sqlite_integer(
                    checkpoint["financial_count"], "checkpoint financial_count"
                )
                != state["financial_count"]
                or str(checkpoint["financial_tail_hash"] or "")
                != state["financial_tail_hash"]
                or _sqlite_integer(
                    checkpoint["settlement_count"], "checkpoint settlement_count"
                )
                != state["settlement_count"]
                or str(checkpoint["settlement_tail_hash"] or "")
                != state["settlement_tail_hash"]
                or _sqlite_integer(
                    checkpoint["ticket_count"], "checkpoint ticket_count"
                )
                != state["ticket_count"]
                or not hmac.compare_digest(
                    str(checkpoint["record_mac"] or ""), expected_mac
                )
            ):
                raise RuntimeError("Authenticated integrity checkpoint HMAC failed")
    except sqlite3.Error as exc:
        raise RuntimeError("Authenticated challenge database cannot be verified") from exc


def _read_migration_marker(path: Path) -> bytes:
    if path.is_symlink():
        raise RuntimeError("Ledger migration marker must not be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError("Ledger migration marker cannot be opened safely") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RuntimeError("Ledger migration marker must be one regular file")
        if (
            os.name != "nt"
            and Path(os.path.abspath(os.fspath(path)))
            == PRODUCTION_BACKUP_MARKER_PATH
        ):
            import grp

            if (
                info.st_uid != 0
                or info.st_gid != grp.getgrnam("betboy").gr_gid
                or stat.S_IMODE(info.st_mode) != 0o640
            ):
                raise RuntimeError(
                    "Production migration marker must be root:betboy mode 0640"
                )
        raw = os.read(descriptor, 65_537)
        if len(raw) > 65_536 or os.read(descriptor, 1):
            raise RuntimeError("Ledger migration marker is unexpectedly large")
    finally:
        os.close(descriptor)
    _validate_migration_marker_bytes(raw)
    return raw


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _marker_root_is_absolute(value: str) -> bool:
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _ledger_scope_from_marker_root(
    application_root: str,
    relative: PurePosixPath,
) -> str:
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("Challenge archive member has an unsafe ledger scope")
    windows_root = PureWindowsPath(application_root)
    if windows_root.is_absolute() and not PurePosixPath(application_root).is_absolute():
        return str(windows_root.joinpath(*relative.parts))
    posix_root = PurePosixPath(application_root)
    if not posix_root.is_absolute():
        raise RuntimeError("Migration marker application root is not absolute")
    return str(posix_root.joinpath(*relative.parts))


def _validate_migration_marker_bytes(
    raw: bytes,
    *,
    allow_in_progress: bool = False,
) -> dict[str, object]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Ledger migration marker has invalid JSON") from exc
    base_keys = {
        "contract_version",
        "status",
        "mode",
        "application_root",
        "previous_head",
        "previous_writer_blob",
        "target_head",
    }
    complete_keys = base_keys | {"completed_at", "migration_receipt"}
    receipt = payload.get("migration_receipt") if isinstance(payload, dict) else None
    application_root = payload.get("application_root") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("status")
        not in ({"complete", "in_progress"} if allow_in_progress else {"complete"})
        or set(payload)
        != (complete_keys if payload.get("status") == "complete" else base_keys)
        or type(payload.get("contract_version")) is not int
        or payload["contract_version"] != 1
        or payload.get("mode") not in {"legacy-v0", "fresh-install"}
        or not isinstance(application_root, str)
        or not _marker_root_is_absolute(application_root)
        or not _is_lower_hex(payload.get("target_head"), 40)
    ):
        raise RuntimeError("Ledger migration marker is incomplete")
    if payload["mode"] == "legacy-v0":
        if (
            not _is_lower_hex(payload.get("previous_head"), 40)
            or payload.get("previous_writer_blob") not in LEGACY_V0_WRITER_BLOBS
        ):
            raise RuntimeError("Ledger migration marker predecessor is invalid")
    elif (
        payload.get("status") != "complete"
        or payload.get("previous_head") != "0" * 40
        or payload.get("previous_writer_blob") != "fresh-install"
    ):
        raise RuntimeError("Fresh-install migration marker is invalid")
    if payload["status"] == "in_progress":
        return payload
    if (
        not isinstance(receipt, dict)
        or set(receipt)
        != {"contract_version", "mode", "database_count", "databases"}
        or type(receipt.get("contract_version")) is not int
        or receipt.get("contract_version") != 1
        or receipt.get("mode") != payload.get("mode")
        or type(receipt.get("database_count")) is not int
        or receipt["database_count"] < 0
        or not isinstance(receipt.get("databases"), list)
        or receipt["database_count"] != len(receipt["databases"])
        or (payload["mode"] == "fresh-install" and receipt["databases"])
    ):
        raise RuntimeError("Ledger migration marker is incomplete")
    try:
        completed_at = datetime.fromisoformat(
            str(payload["completed_at"]).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise RuntimeError("Ledger migration completion time is invalid") from exc
    if completed_at.tzinfo is None:
        raise RuntimeError("Ledger migration completion time lacks a timezone")
    seen_paths: set[str] = set()
    for record in receipt["databases"]:
        if not isinstance(record, dict) or set(record) != {
            "path",
            "checkpoint_mac",
            "source",
        }:
            raise RuntimeError("Ledger migration receipt entry is invalid")
        relative = PurePosixPath(str(record["path"]))
        canonical = relative.as_posix()
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
            or canonical in seen_paths
            or not _is_lower_hex(record["checkpoint_mac"], 64)
            or record["source"] not in {"v0", "v2"}
        ):
            raise RuntimeError("Ledger migration receipt entry is unsafe")
        seen_paths.add(canonical)
    return payload


def _database_has_table(path: Path, table: str) -> bool:
    try:
        with closing(
            sqlite3.connect(
                path.resolve(strict=True).as_uri() + "?mode=ro",
                uri=True,
                timeout=30,
            )
        ) as connection:
            connection.execute("PRAGMA query_only=ON")
            return connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone() is not None
    except sqlite3.Error as exc:
        raise RuntimeError(f"Cannot inspect backup source {path}") from exc


def _completed_legacy_receipt_paths(
    marker_payload: dict[str, object] | None,
) -> set[str]:
    if (
        marker_payload is None
        or marker_payload.get("status") != "complete"
        or marker_payload.get("mode") != "legacy-v0"
    ):
        return set()
    receipt = marker_payload["migration_receipt"]
    if not isinstance(receipt, dict):
        raise RuntimeError("Completed migration receipt is invalid")
    records = receipt["databases"]
    if not isinstance(records, list) or any(
        not isinstance(record, dict) for record in records
    ):
        raise RuntimeError("Completed migration receipt is invalid")
    return {str(record["path"]) for record in records}


def _challenge_member_name(name: str) -> bool:
    relative = PurePosixPath(name)
    return (
        relative.as_posix() == "challenge_15k.db"
        or relative.parts[:1] == ("challenge_sessions",)
    )


def _challenge_path(path: Path, root: Path) -> bool:
    return _challenge_member_name(path.relative_to(root).as_posix())


def _challenge_databases_present(databases: list[Path], root: Path) -> bool:
    return any(
        _challenge_path(path, root)
        or _database_has_table(path, "challenge_settings")
        or _database_has_table(path, "challenge_integrity_checkpoint")
        for path in databases
    )


def create_archive(
    output_dir: Path,
    *,
    root: Path = ROOT,
    now: datetime | None = None,
    integrity_key_path: Path | None = None,
    migration_marker_path: Path | None = None,
) -> tuple[Path, int]:
    root = _validated_application_root(root)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    if output_dir.is_symlink():
        raise RuntimeError("Backup output directory must not be a symlink")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_info = os.lstat(output_dir)
    if not stat.S_ISDIR(output_info.st_mode):
        raise RuntimeError("Backup output path is not a directory")
    final_path = output_dir / f"betboy-sqlite-{stamp}.zip"
    if final_path.exists() or final_path.is_symlink():
        raise RuntimeError(f"Backup archive already exists: {final_path.name}")
    databases = discover_databases(root)
    if not databases:
        raise RuntimeError("No runtime databases were found to back up")
    if integrity_key_path is None:
        local_key = root / LOCAL_INTEGRITY_KEY_RELATIVE_PATH
        if local_key.exists() or local_key.is_symlink():
            integrity_key_path = local_key
    key_bytes = (
        _read_integrity_key(Path(integrity_key_path))
        if integrity_key_path is not None
        else None
    )
    if _challenge_databases_present(databases, root) and key_bytes is None:
        raise RuntimeError(
            "Challenge databases require their ledger integrity key in the backup"
        )
    marker_bytes = (
        _read_migration_marker(Path(migration_marker_path))
        if migration_marker_path is not None
        and (
            Path(migration_marker_path).exists()
            or Path(migration_marker_path).is_symlink()
        )
        else None
    )
    marker_payload = (
        _validate_migration_marker_bytes(marker_bytes)
        if marker_bytes is not None
        else None
    )
    if marker_payload is not None:
        marker_root = Path(str(marker_payload["application_root"]))
        if not marker_root.is_absolute() or marker_root != root:
            raise RuntimeError("Ledger migration marker names another application root")
    database_by_name = {
        path.relative_to(root).as_posix(): path for path in databases
    }
    receipt_paths = _completed_legacy_receipt_paths(marker_payload)
    missing_receipt_paths = receipt_paths - set(database_by_name)
    if missing_receipt_paths:
        raise RuntimeError(
            "Completed migration receipt is missing its original challenge database"
        )
    known_names = {
        name for name in database_by_name if _challenge_member_name(name)
    } | receipt_paths
    challenge_sources = [
        path
        for name, path in database_by_name.items()
        if name in known_names
        or _database_has_table(path, "challenge_settings")
        or _database_has_table(path, "challenge_integrity_checkpoint")
    ]
    if challenge_sources and key_bytes is None:
        raise RuntimeError(
            "Challenge databases require their ledger integrity key in the backup"
        )
    if challenge_sources and marker_payload is None:
        raise RuntimeError(
            "Current challenge databases require their completed migration marker"
        )
    for source in challenge_sources:
        if not _database_has_table(source, "challenge_settings"):
            raise RuntimeError(
                "Known challenge database is missing challenge_settings"
            )
        if not _database_has_table(source, "challenge_integrity_checkpoint"):
            raise RuntimeError(
                "Known legacy challenge database is missing its v2 integrity checkpoint"
            )

    with tempfile.TemporaryDirectory(prefix="betboy-backup-") as temp_dir:
        stage = Path(temp_dir)
        for source in databases:
            relative = source.relative_to(root)
            backup_database(source, stage / relative)
        if challenge_sources:
            if key_bytes is None or marker_payload is None:
                raise RuntimeError(
                    "Current challenge databases require authenticated backup inputs"
                )
            for source in challenge_sources:
                relative = source.relative_to(root)
                verify_current_challenge_database(
                    stage / relative,
                    key_bytes,
                    ledger_scope=_ledger_scope_from_marker_root(
                        str(marker_payload["application_root"]),
                        PurePosixPath(relative.as_posix()),
                    ),
                )
        if key_bytes is not None:
            staged_key = stage / PurePosixPath(INTEGRITY_KEY_ARCHIVE_PATH)
            staged_key.parent.mkdir(parents=True, exist_ok=True)
            staged_key.write_bytes(key_bytes)
            if os.name != "nt":
                staged_key.chmod(0o600)
        if marker_bytes is not None:
            staged_marker = stage / PurePosixPath(MIGRATION_MARKER_ARCHIVE_PATH)
            staged_marker.parent.mkdir(parents=True, exist_ok=True)
            staged_marker.write_bytes(marker_bytes)
            if os.name != "nt":
                staged_marker.chmod(0o600)

        partial_path = output_dir / f".{final_path.name}.partial"
        if partial_path.exists() or partial_path.is_symlink():
            raise RuntimeError(
                f"Partial backup archive already exists: {partial_path.name}"
            )
        published = False
        try:
            with zipfile.ZipFile(
                partial_path,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                for staged in sorted(
                    path
                    for path in stage.rglob("*")
                    if path.is_file()
                    and (
                        path.suffix.casefold() in DATABASE_SUFFIXES
                        or path.relative_to(stage).as_posix()
                        in {
                            INTEGRITY_KEY_ARCHIVE_PATH,
                            MIGRATION_MARKER_ARCHIVE_PATH,
                        }
                    )
                ):
                    archive.write(staged, staged.relative_to(stage).as_posix())
            _fsync_file(partial_path)
            if verify_archive(partial_path) != len(databases):
                raise RuntimeError("Partial backup member count is inconsistent")
            partial_path.replace(final_path)
            _fsync_directory(output_dir)
            published = True
        finally:
            if not published:
                try:
                    partial_path.unlink()
                    _fsync_directory(output_dir)
                except FileNotFoundError:
                    pass

    return final_path, len(databases)


def _validate_embedded_manifest(
    manifest: object,
    archive: zipfile.ZipFile,
    members: list[zipfile.ZipInfo],
    key_infos: list[zipfile.ZipInfo],
    marker_infos: list[zipfile.ZipInfo],
) -> None:
    base_keys = {
        "created_at",
        "source_head",
        "database_count",
        "databases",
        "integrity_key",
    }
    if not isinstance(manifest, dict) or frozenset(manifest) not in {
        frozenset(base_keys),
        frozenset(base_keys | {"migration_marker"}),
    }:
        raise RuntimeError("Backup manifest has an invalid shape")
    _require_timestamp(manifest["created_at"], "backup manifest created_at")
    if not _is_lower_hex(manifest["source_head"], 40):
        raise RuntimeError("Backup manifest source revision is invalid")
    records = manifest["databases"]
    if (
        type(manifest["database_count"]) is not int
        or manifest["database_count"] < 0
        or not isinstance(records, list)
        or manifest["database_count"] != len(records)
        or len(records) != len(members)
    ):
        raise RuntimeError("Backup manifest database inventory is inconsistent")
    member_by_name = {info.filename: info for info in members}
    seen: set[str] = set()
    for record in records:
        if (
            not isinstance(record, dict)
            or set(record)
            != {"path", "source_size", "backup_size", "sha256"}
            or not isinstance(record.get("path"), str)
            or record["path"] in seen
            or record["path"] not in member_by_name
            or type(record.get("source_size")) is not int
            or record["source_size"] < 0
            or type(record.get("backup_size")) is not int
            or record["backup_size"] < 0
            or not _is_lower_hex(record.get("sha256"), 64)
        ):
            raise RuntimeError("Backup manifest database entry is invalid")
        seen.add(record["path"])
        info = member_by_name[record["path"]]
        payload = archive.read(info)
        if (
            record["backup_size"] != info.file_size
            or len(payload) != info.file_size
            or not hmac.compare_digest(
                record["sha256"],
                hashlib.sha256(payload).hexdigest(),
            )
        ):
            raise RuntimeError("Backup manifest database digest is invalid")
    if seen != set(member_by_name):
        raise RuntimeError("Backup manifest omits a database member")

    integrity_record = manifest["integrity_key"]
    if (
        not isinstance(integrity_record, dict)
        or set(integrity_record) != {"path", "sha256"}
        or integrity_record.get("path") != INTEGRITY_KEY_ARCHIVE_PATH
        or not _is_lower_hex(integrity_record.get("sha256"), 64)
        or len(key_infos) != 1
        or not hmac.compare_digest(
            integrity_record["sha256"],
            hashlib.sha256(archive.read(key_infos[0])).hexdigest(),
        )
    ):
        raise RuntimeError("Backup manifest integrity key entry is invalid")

    if "migration_marker" not in manifest:
        if marker_infos:
            raise RuntimeError("Backup manifest omits its migration marker")
    else:
        marker_record = manifest["migration_marker"]
        if (
            not isinstance(marker_record, dict)
            or set(marker_record) != {"path", "sha256"}
            or marker_record.get("path") != MIGRATION_MARKER_ARCHIVE_PATH
            or not _is_lower_hex(marker_record.get("sha256"), 64)
            or len(marker_infos) != 1
            or not hmac.compare_digest(
                marker_record["sha256"],
                hashlib.sha256(archive.read(marker_infos[0])).hexdigest(),
            )
        ):
            raise RuntimeError("Backup manifest migration marker entry is invalid")


def verify_archive(archive_path: Path, *, recovery_mode: bool = False) -> int:
    """Restore every member independently and run SQLite's full quick check."""
    archive_path = Path(archive_path)
    if not archive_path.is_file():
        raise RuntimeError(f"Backup archive does not exist: {archive_path}")

    with tempfile.TemporaryDirectory(prefix="betboy-restore-check-") as temp_dir:
        stage = Path(temp_dir)
        try:
            with zipfile.ZipFile(archive_path) as archive:
                infos = archive.infolist()
                if any(info.is_dir() for info in infos):
                    raise RuntimeError(
                        "Backup archive contains an unexpected directory member"
                    )
                names = [info.filename for info in infos]
                if len(names) != len(set(names)):
                    raise RuntimeError("Backup archive contains duplicate members")
                for name in names:
                    pure = PurePosixPath(name)
                    if (
                        pure.is_absolute()
                        or not pure.parts
                        or any(part in {"", ".", ".."} for part in pure.parts)
                        or "\\" in name
                        or name != pure.as_posix()
                    ):
                        raise RuntimeError("Backup archive contains an unsafe member")
                bad_member = archive.testzip()
                if bad_member is not None:
                    raise RuntimeError(
                        f"Backup archive failed its CRC check: {bad_member}"
                    )
                members = [
                    info
                    for info in infos
                    if Path(info.filename).suffix.casefold()
                    in DATABASE_SUFFIXES
                ]
                if not members:
                    raise RuntimeError("Backup archive contains no SQLite databases")
                database_names = {info.filename for info in members}
                key_infos = [
                    info
                    for info in infos
                    if info.filename == INTEGRITY_KEY_ARCHIVE_PATH
                ]
                marker_infos = [
                    info
                    for info in infos
                    if info.filename == MIGRATION_MARKER_ARCHIVE_PATH
                ]
                manifest_infos = [
                    info for info in infos if info.filename == "MANIFEST.json"
                ]
                expected_names = database_names | (
                    {INTEGRITY_KEY_ARCHIVE_PATH} if key_infos else set()
                ) | ({MIGRATION_MARKER_ARCHIVE_PATH} if marker_infos else set()) | (
                    {"MANIFEST.json"} if manifest_infos else set()
                )
                if set(names) != expected_names:
                    raise RuntimeError("Backup archive contains an unexpected member")
                if len(manifest_infos) > 1:
                    raise RuntimeError("Backup contains duplicate manifests")
                if manifest_infos:
                    try:
                        manifest = json.loads(archive.read(manifest_infos[0]))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise RuntimeError("Backup manifest has invalid JSON") from exc
                    _validate_embedded_manifest(
                        manifest,
                        archive,
                        members,
                        key_infos,
                        marker_infos,
                    )
                key_bytes = archive.read(key_infos[0]) if key_infos else None
                if key_bytes is not None:
                    _validate_integrity_key_bytes(key_bytes)
                if len(marker_infos) > 1:
                    raise RuntimeError("Backup contains duplicate migration markers")
                marker_payload = (
                    _validate_migration_marker_bytes(
                        archive.read(marker_infos[0]),
                        allow_in_progress=recovery_mode,
                    )
                    if marker_infos
                    else None
                )
                receipt_paths = _completed_legacy_receipt_paths(marker_payload)
                missing_receipt_paths = receipt_paths - database_names
                if missing_receipt_paths:
                    raise RuntimeError(
                        "Completed migration receipt is missing its original challenge database"
                    )
                known_challenge_names = {
                    name for name in database_names if _challenge_member_name(name)
                } | receipt_paths
                if known_challenge_names and len(key_infos) != 1:
                    raise RuntimeError(
                        "Challenge backup is missing its ledger integrity key"
                    )
                if known_challenge_names and len(marker_infos) != 1:
                    raise RuntimeError(
                        "Current challenge backup is missing its migration marker"
                    )
                authenticated_challenge_present = False
                for index, info in enumerate(members):
                    restored = stage / f"database-{index}.db"
                    with archive.open(info) as source:
                        with restored.open("wb") as destination:
                            shutil.copyfileobj(source, destination)
                    uri = f"file:{restored.resolve().as_posix()}?mode=ro"
                    with closing(
                        sqlite3.connect(uri, uri=True, timeout=30)
                    ) as connection:
                        connection.execute("PRAGMA query_only=ON")
                        result = connection.execute("PRAGMA quick_check").fetchall()
                        challenge_table = connection.execute(
                            """
                            SELECT 1 FROM sqlite_master
                            WHERE type='table' AND name='challenge_settings'
                            """
                        ).fetchone()
                        is_current_challenge = connection.execute(
                            """
                            SELECT 1 FROM sqlite_master
                            WHERE type='table'
                              AND name='challenge_integrity_checkpoint'
                            """
                        ).fetchone() is not None
                    if result != [("ok",)]:
                        raise RuntimeError(
                            f"SQLite restore check failed: {info.filename}"
                        )
                    must_authenticate = (
                        info.filename in known_challenge_names
                        or challenge_table is not None
                        or is_current_challenge
                    )
                    if must_authenticate:
                        authenticated_challenge_present = True
                    if must_authenticate and challenge_table is None:
                        raise RuntimeError(
                            "Known challenge backup is missing challenge_settings"
                        )
                    recovery_legacy = (
                        recovery_mode
                        and marker_payload is not None
                        and marker_payload.get("status") == "in_progress"
                        and challenge_table is not None
                        and not is_current_challenge
                    )
                    if (
                        must_authenticate
                        and not is_current_challenge
                        and not recovery_legacy
                    ):
                        raise RuntimeError(
                            "Known legacy challenge database is missing its v2 integrity checkpoint"
                        )
                    if must_authenticate and key_bytes is None:
                        raise RuntimeError(
                            "Challenge backup is missing its ledger integrity key"
                        )
                    if must_authenticate and marker_payload is None:
                        raise RuntimeError(
                            "Current challenge backup lacks authentication material"
                        )
                    if must_authenticate and not recovery_legacy:
                        if key_bytes is None or marker_payload is None:
                            raise RuntimeError(
                                "Current challenge backup lacks authentication material"
                            )
                        relative = PurePosixPath(info.filename)
                        verify_current_challenge_database(
                            restored,
                            key_bytes,
                            ledger_scope=_ledger_scope_from_marker_root(
                                str(marker_payload["application_root"]),
                                relative,
                            ),
                        )
                if authenticated_challenge_present and len(marker_infos) != 1:
                    raise RuntimeError(
                        "Current challenge backup is missing its migration marker"
                    )
        except (OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
            raise RuntimeError(
                f"Backup archive is not restorable: {archive_path.name}"
            ) from exc
    return len(members)


def prune_archives(
    output_dir: Path,
    *,
    retention_days: int,
    now: datetime | None = None,
) -> int:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    removed = 0
    for archive in output_dir.glob("betboy-sqlite-*.zip"):
        try:
            stamp = archive.stem.removeprefix("betboy-sqlite-")
            created = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
        if created < cutoff:
            archive.unlink()
            removed += 1
    if removed:
        _fsync_directory(output_dir)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Application root containing the runtime SQLite databases",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "backups_runtime",
    )
    parser.add_argument("--retention-days", type=int, default=14)
    parser.add_argument(
        "--integrity-key",
        type=Path,
        help="Read-only path to the 15K ledger HMAC key",
    )
    parser.add_argument(
        "--migration-marker",
        type=Path,
        help="Read-only path to the completed root migration marker",
    )
    parser.add_argument(
        "--verify-only",
        type=Path,
        help="Verify an existing backup archive without creating a new one",
    )
    parser.add_argument(
        "--recovery-mode",
        action="store_true",
        help="Allow a root recovery archive captured during an in-progress v0 migration",
    )
    args = parser.parse_args()
    if args.retention_days < 1:
        parser.error("--retention-days must be at least 1")
    if args.verify_only is not None:
        verified = verify_archive(
            args.verify_only,
            recovery_mode=args.recovery_mode,
        )
        print(f"Verified: {args.verify_only} | databases={verified}")
        return 0
    if args.recovery_mode:
        parser.error("--recovery-mode requires --verify-only")

    archive, count = create_archive(
        args.output_dir,
        root=args.root,
        integrity_key_path=args.integrity_key,
        migration_marker_path=args.migration_marker,
    )
    try:
        verified = verify_archive(archive)
    except Exception:
        archive.unlink(missing_ok=True)
        _fsync_directory(archive.parent)
        raise
    if verified != count:
        raise RuntimeError(
            f"Backup member count mismatch: created={count}, verified={verified}"
        )
    removed = prune_archives(
        args.output_dir,
        retention_days=args.retention_days,
    )
    print(
        f"Backup: {archive} | databases={count} | "
        f"verified={verified} | pruned={removed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
