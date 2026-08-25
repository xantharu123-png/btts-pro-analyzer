"""Persistent cent-accurate bankroll ledger for the 15K challenge."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import stat
from statistics import median
import time
from typing import Any
from zoneinfo import ZoneInfo

from challenge_engine import (
    CHALLENGE_MODEL_CONTRACT_SIGNATURE,
    DEFAULT_CHALLENGE_STAKE_FRACTION,
    KELLY_REFERENCE_CAP,
    MARKET_BY_KEY,
    MAX_CHALLENGE_STAKE_FRACTION,
    MIN_CHALLENGE_STAKE_FRACTION,
    MIN_LEG_EXPECTED_ROI,
    QuotedTicket,
    TARGET_BALANCE,
    TARGET_ODDS_MAX,
    TARGET_ODDS_MIN,
    candidate_is_credible,
    dependence_floor_probability,
    risk_managed_ticket_stake,
    ticket_stake_passes_log_growth_gate,
    ticket_dependency_factor,
)
from betting_math import BettingMathError, evaluate_market_price, validate_decimal_odds
from price_ledger import (
    BOOKMAKER,
    PRICE_LEDGER_SCHEMA_STATEMENTS,
    ZERO_HASH as PRICE_ZERO_HASH,
    PriceLedger,
    PriceLedgerError,
    PriceLedgerIntegrityError,
    PriceQuote,
)
from market_consensus import (
    MIN_REFERENCE_BOOKMAKERS,
    REFERENCE_FETCH_MAX_AGE,
    REFERENCE_QUOTE_MAX_AGE,
    REFERENCE_SOURCE,
)


DEFAULT_CHALLENGE_DB = Path(__file__).with_name("challenge_15k.db")
VALID_STATUSES = {"PENDING", "WON", "LOST", "VOID"}
MAX_QUOTE_AGE_SECONDS = 10 * 60
STAKE_POLICY_VERSION = 3
SETTLEMENT_RULE_VERSION = 2
TICKET_DEFINITION_VERSION = 3
CHALLENGE_TIMEZONE = ZoneInfo("Europe/Zurich")
CHALLENGE_TIMEZONE_NAME = "Europe/Zurich"
FINANCIAL_ANCHOR_KINDS = {"OPENING_BALANCE", "MIGRATION_SNAPSHOT"}
FINANCIAL_CHAIN_VERSION = 2
FINANCIAL_ZERO_HASH = "0" * 64
SETTLEMENT_CHAIN_VERSION = 1
SETTLEMENT_ZERO_HASH = "0" * 64
INTEGRITY_CHECKPOINT_VERSION = 2
LEDGER_HMAC_KEY_FILE_ENV = "BETBOY_LEDGER_HMAC_KEY_FILE"
LEDGER_HMAC_REQUIRED_ENV = "BETBOY_LEDGER_HMAC_REQUIRED"
LEDGER_CHECKPOINT_MIGRATION_ENV = "BETBOY_LEDGER_CHECKPOINT_MIGRATION"
LEDGER_MIGRATION_POLICY_FILE_ENV = "BETBOY_LEDGER_MIGRATION_POLICY_FILE"
LEDGER_MIGRATION_CONTRACT_VERSION = 1
LEGACY_V0_WRITER_BLOBS = frozenset(
    {"f96d8b6c340c184e90d644cc310efebf963de1ad"}
)
DEFAULT_LEDGER_HMAC_KEY_NAME = ".betboy-ledger-hmac.key"
PRODUCTION_LEDGER_HMAC_KEY_PATH = Path(
    "/etc/betboy/challenge-ledger-hmac.key"
)
PRODUCTION_LEDGER_MIGRATION_POLICY_PATH = Path(
    "/etc/betboy/challenge-ledger-v2-migrated.json"
)
LEDGER_HMAC_KEY_BYTES = 32
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
SETTLEMENT_ALLOWED_SOURCES = {
    "AUTO_PROVIDER_FT",
    "MANUAL_CONFIRMED",
    "MANUAL_HISTORY",
    "MANUAL_CORRECTION",
    "MANUAL_REVERSAL",
}
MIN_STAKE_FRACTION_BPS = int(MIN_CHALLENGE_STAKE_FRACTION * 10_000)
MAX_STAKE_FRACTION_BPS = int(MAX_CHALLENGE_STAKE_FRACTION * 10_000)


def _bounded_stake_fraction_bps(value: Any) -> int:
    """Fail safely to the minimum if persisted stake policy data is malformed."""
    if isinstance(value, bool):
        return MIN_STAKE_FRACTION_BPS
    try:
        basis_points = int(value)
    except (TypeError, ValueError, OverflowError):
        return MIN_STAKE_FRACTION_BPS
    return min(
        MAX_STAKE_FRACTION_BPS,
        max(MIN_STAKE_FRACTION_BPS, basis_points),
    )


def _money_to_cents(value: Any, *, allow_zero: bool = True) -> int:
    if isinstance(value, bool):
        raise ValueError("Money must be numeric, not boolean")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Money must be numeric") from exc
    if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
        raise ValueError("Money must be finite and non-negative")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _cents_to_money(value: int) -> float:
    return float(Decimal(int(value)) / Decimal(100))


def _utc_datetime(value: Any, label: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if timestamp.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return timestamp.astimezone(timezone.utc)


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _sqlite_integer(value: Any, label: str) -> int:
    """Accept only values SQLite actually returned with INTEGER storage class."""

    # SQLite's dynamic typing may retain N+0.5 as REAL even in an INTEGER
    # affinity column.  int() would silently collapse that tamper onto the old
    # authenticated value, so every signed/replayed integer is type-exact.
    if type(value) is not int:
        raise ValueError(f"{label} must use SQLite INTEGER storage")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _challenge_schema_manifest(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return every persistent schema row of this dedicated ledger DB."""

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
        # Include SQLite's own sequence table and NULL-SQL autoindexes too.
        # A raw writable_schema edit must never disappear behind a prefix
        # filter; dynamic sqlite_sequence contents are bound separately below.
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


def _challenge_sequence_state(connection: sqlite3.Connection) -> list[dict[str, Any]]:
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
        raise ValueError("challenge sequence inventory is invalid")
    state: list[dict[str, Any]] = []
    for row in rows:
        name = str(row["name"])
        sequence = _sqlite_integer(row["seq"], f"{name} sequence")
        if sequence < 0:
            raise ValueError(f"{name} sequence must be non-negative")
        quoted_name = name.replace('"', '""')
        maximum = _sqlite_integer(
            connection.execute(
                f'SELECT COALESCE(MAX(rowid), 0) FROM "{quoted_name}"'
            ).fetchone()[0],
            f"{name} maximum rowid",
        )
        if sequence < maximum:
            raise ValueError(f"{name} sequence is behind its table")
        state.append({"name": name, "sequence": sequence})
    return state


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _legacy_financial_record_hash(
    *,
    created_at: str,
    kind: str,
    amount_cents: int,
    balance_after_cents: int,
    ticket_id: int | None,
    note: str | None,
    previous_hash: str,
    chain_version: int = 1,
) -> str:
    """Recompute the unauthenticated v1 digest only for strict migration."""

    amount_cents = _sqlite_integer(amount_cents, "legacy amount_cents")
    balance_after_cents = _sqlite_integer(
        balance_after_cents,
        "legacy balance_after_cents",
    )
    ticket_id = (
        _sqlite_integer(ticket_id, "legacy ticket_id")
        if ticket_id is not None
        else None
    )
    chain_version = _sqlite_integer(chain_version, "legacy chain_version")

    return _sha256_text(
        _canonical_json(
            {
                "created_at": str(created_at),
                "kind": str(kind),
                "amount_cents": amount_cents,
                "balance_after_cents": balance_after_cents,
                "ticket_id": ticket_id,
                "note": str(note) if note is not None else None,
                "previous_hash": str(previous_hash),
                "chain_version": chain_version,
            }
        )
    )


def _hmac_hex(key: bytes, domain: str, payload: dict[str, Any]) -> str:
    message = _canonical_json({"domain": domain, "payload": payload})
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def _financial_record_mac(
    key: bytes,
    *,
    created_at: str,
    kind: str,
    amount_cents: int,
    balance_after_cents: int,
    ticket_id: int | None,
    note: str | None,
    previous_hash: str,
    chain_version: int = FINANCIAL_CHAIN_VERSION,
) -> str:
    """Authenticate every immutable field of one ordered money record."""

    amount_cents = _sqlite_integer(amount_cents, "financial amount_cents")
    balance_after_cents = _sqlite_integer(
        balance_after_cents,
        "financial balance_after_cents",
    )
    ticket_id = (
        _sqlite_integer(ticket_id, "financial ticket_id")
        if ticket_id is not None
        else None
    )
    chain_version = _sqlite_integer(chain_version, "financial chain_version")

    return _hmac_hex(
        key,
        "betboy.challenge.financial.v2",
        {
            "created_at": str(created_at),
            "kind": str(kind),
            "amount_cents": amount_cents,
            "balance_after_cents": balance_after_cents,
            "ticket_id": ticket_id,
            "note": str(note) if note is not None else None,
            "previous_hash": str(previous_hash),
            "chain_version": chain_version,
        },
    )


def _settlement_record_mac(
    key: bytes,
    *,
    ticket_id: int,
    created_at: str,
    action: str,
    previous_status: str | None,
    new_status: str,
    previous_payout_cents: int,
    new_payout_cents: int,
    settlement_odds: float | None,
    rule_version: int,
    source: str,
    reason: str,
    previous_hash: str,
    chain_version: int = SETTLEMENT_CHAIN_VERSION,
) -> str:
    """Authenticate the complete settlement provenance and predecessor."""

    ticket_id = _sqlite_integer(ticket_id, "settlement ticket_id")
    previous_payout_cents = _sqlite_integer(
        previous_payout_cents,
        "settlement previous_payout_cents",
    )
    new_payout_cents = _sqlite_integer(
        new_payout_cents,
        "settlement new_payout_cents",
    )
    rule_version = _sqlite_integer(rule_version, "settlement rule_version")
    chain_version = _sqlite_integer(chain_version, "settlement chain_version")

    return _hmac_hex(
        key,
        "betboy.challenge.settlement.v1",
        {
            "ticket_id": ticket_id,
            "created_at": str(created_at),
            "action": str(action),
            "previous_status": (
                str(previous_status) if previous_status is not None else None
            ),
            "new_status": str(new_status),
            "previous_payout_cents": previous_payout_cents,
            "new_payout_cents": new_payout_cents,
            "settlement_odds": (
                float(settlement_odds) if settlement_odds is not None else None
            ),
            "rule_version": rule_version,
            "source": str(source),
            "reason": str(reason),
            "previous_hash": str(previous_hash),
            "chain_version": chain_version,
        },
    )


def _integrity_checkpoint_mac(key: bytes, state: dict[str, Any]) -> str:
    return _hmac_hex(
        key,
        "betboy.challenge.current-state.v2",
        {
            "checkpoint_version": INTEGRITY_CHECKPOINT_VERSION,
            **state,
        },
    )


def _environment_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _is_lower_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _read_legacy_migration_policy(db_path: str | Path) -> dict[str, Any]:
    """Validate the root-published authorization for the one real v0 rollout."""

    configured = os.environ.get(LEDGER_MIGRATION_POLICY_FILE_ENV, "").strip()
    if not configured:
        raise RuntimeError("Controlled ledger migration policy is required")
    policy_path = Path(configured)
    if not policy_path.is_absolute() or policy_path.is_symlink():
        raise RuntimeError("Controlled ledger migration policy path is unsafe")
    production_policy = (
        os.environ.get(LEDGER_HMAC_KEY_FILE_ENV, "").strip()
        == str(PRODUCTION_LEDGER_HMAC_KEY_PATH)
    )
    if production_policy and policy_path != PRODUCTION_LEDGER_MIGRATION_POLICY_PATH:
        raise RuntimeError("Production ledger migration policy path is not trusted")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    try:
        descriptor = os.open(policy_path, flags)
    except OSError as exc:
        raise RuntimeError("Controlled ledger migration policy cannot be opened") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RuntimeError("Controlled ledger migration policy is not one file")
        if os.name != "nt":
            if production_policy:
                if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o640:
                    raise RuntimeError(
                        "Controlled ledger migration policy is not root-owned "
                        "mode 0640"
                    )
            elif (
                info.st_uid not in {0, os.geteuid()}
                or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                or not info.st_mode & stat.S_IRUSR
            ):
                raise RuntimeError("Local ledger migration policy is not trusted")
        raw = os.read(descriptor, 16_385)
        if len(raw) > 16_384 or os.read(descriptor, 1):
            raise RuntimeError("Controlled ledger migration policy is too large")
    finally:
        os.close(descriptor)
    try:
        policy = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Controlled ledger migration policy is invalid JSON") from exc
    required_keys = {
        "contract_version",
        "status",
        "mode",
        "application_root",
        "previous_head",
        "previous_writer_blob",
        "target_head",
    }
    if not isinstance(policy, dict) or set(policy) != required_keys:
        raise RuntimeError("Controlled ledger migration policy has an invalid shape")
    if (
        type(policy["contract_version"]) is not int
        or policy["contract_version"] != LEDGER_MIGRATION_CONTRACT_VERSION
        or policy["status"] != "in_progress"
        or policy["mode"] != "legacy-v0"
        or not _is_lower_hex(policy["previous_head"], 40)
        or policy["previous_writer_blob"] not in LEGACY_V0_WRITER_BLOBS
        or not _is_lower_hex(policy["target_head"], 40)
    ):
        raise RuntimeError("Controlled ledger migration policy is unauthorized")
    application_root = Path(str(policy["application_root"]))
    if not application_root.is_absolute():
        raise RuntimeError("Controlled ledger migration root must be absolute")
    try:
        Path(db_path).resolve(strict=False).relative_to(
            application_root.resolve(strict=True)
        )
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            "Challenge database is outside the controlled migration root"
        ) from exc
    return policy


def _validate_key_file_descriptor(descriptor: int, path: Path) -> bytes:
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"Ledger HMAC key is not a regular file: {path}")
    if info.st_nlink != 1:
        raise RuntimeError("Ledger HMAC key must have exactly one hard link")
    if os.name != "nt":
        if info.st_uid != os.geteuid():
            # Production keys may deliberately be root-owned and group-readable.
            groups = set(os.getgroups()) | {os.getegid()}
            if info.st_gid not in groups:
                raise RuntimeError("Ledger HMAC key owner/group is not trusted")
        unsafe = (
            stat.S_IWGRP
            | stat.S_IRWXO
            | stat.S_IXUSR
            | stat.S_IXGRP
        )
        if info.st_mode & unsafe or not info.st_mode & stat.S_IRUSR:
            raise RuntimeError("Ledger HMAC key permissions are unsafe")
    raw = os.read(descriptor, 1024)
    if os.read(descriptor, 1):
        raise RuntimeError("Ledger HMAC key file is unexpectedly large")
    if (
        len(raw) != LEDGER_HMAC_KEY_BYTES * 2 + 1
        or not raw.endswith(b"\n")
        or any(byte not in b"0123456789abcdef" for byte in raw[:-1])
    ):
        raise RuntimeError(
            "Ledger HMAC key must be 64 lowercase hexadecimal characters "
            "followed by LF"
        )
    try:
        encoded = raw[:-1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise RuntimeError("Ledger HMAC key must contain lowercase hexadecimal") from exc
    return bytes.fromhex(encoded)


def _read_ledger_hmac_key(path: Path) -> bytes:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    # Atomic local publication uses a transient second hard link.  A concurrent
    # opener may observe that link for only the few instructions between link()
    # and unlink(); retry that narrow state, but fail closed on a persistent one.
    for attempt in range(50):
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise RuntimeError(
                f"Ledger HMAC key cannot be opened safely: {path}"
            ) from exc
        try:
            try:
                return _validate_key_file_descriptor(descriptor, path)
            except RuntimeError as exc:
                if "exactly one hard link" not in str(exc) or attempt == 49:
                    raise
        finally:
            os.close(descriptor)
        time.sleep(0.005)
    raise RuntimeError("Ledger HMAC key publication did not stabilize")


def _create_local_ledger_hmac_key(path: Path) -> None:
    """Atomically publish one local/test key without exposing partial bytes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(
        f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.partial"
    )
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    try:
        descriptor = os.open(temporary_path, flags, 0o600)
    except OSError as exc:
        raise RuntimeError(
            f"Ledger HMAC key cannot be staged safely: {path}"
        ) from exc
    try:
        if os.name != "nt":
            os.fchmod(descriptor, 0o600)
        encoded = secrets.token_hex(LEDGER_HMAC_KEY_BYTES).encode("ascii") + b"\n"
        written = 0
        while written < len(encoded):
            written += os.write(descriptor, encoded[written:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        try:
            # Hard-link publication is atomic and, unlike replace(), cannot
            # overwrite the key selected by a concurrent ledger initializer.
            os.link(temporary_path, path, follow_symlinks=False)
        except FileExistsError:
            pass
        except OSError as exc:
            raise RuntimeError(
                f"Ledger HMAC key cannot be published safely: {path}"
            ) from exc
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _load_ledger_hmac_key(db_path: str | Path) -> tuple[bytes, Path]:
    configured = os.environ.get(LEDGER_HMAC_KEY_FILE_ENV, "").strip()
    required = _environment_flag(LEDGER_HMAC_REQUIRED_ENV)
    if configured:
        key_path = Path(configured)
        if not key_path.is_absolute():
            raise RuntimeError("Configured ledger HMAC key path must be absolute")
        if not key_path.exists() or key_path.is_symlink():
            raise RuntimeError("Configured ledger HMAC key is missing or unsafe")
    else:
        if required:
            raise RuntimeError(
                f"{LEDGER_HMAC_KEY_FILE_ENV} is required in production"
            )
        key_path = Path(db_path).resolve().parent / DEFAULT_LEDGER_HMAC_KEY_NAME
        if key_path.is_symlink():
            raise RuntimeError("Ledger HMAC key must not be a symbolic link")
        if not key_path.exists():
            _create_local_ledger_hmac_key(key_path)
    return _read_ledger_hmac_key(key_path), key_path


def _market_definition(candidate: Any) -> dict[str, Any]:
    """Return and validate the immutable settlement definition of one leg."""
    spec = MARKET_BY_KEY.get(str(candidate.market_key))
    if (
        spec is None
        or str(candidate.market) != spec.market
        or str(candidate.selection) != spec.selection
    ):
        raise ValueError("Ticket market identity does not match its market key")
    return {
        "market_key": spec.key,
        "market_kind": spec.kind,
        "market_side": spec.side,
        "market_threshold": spec.threshold,
        "market_low": spec.low,
        "market_high": spec.high,
        "settlement_rule_version": SETTLEMENT_RULE_VERSION,
    }


def _definition_hash_payload(
    *,
    analysis_date: str,
    legs_json: str,
    quote_evidence_json: str,
    reference_total_odds: float,
    played_total_odds: float,
    joint_probability: float,
    expected_roi: float,
    definition_version: int,
    stake_cents: int | None = None,
    created_at: str | None = None,
    quote_verified_at: str | None = None,
    analysis_timezone: str | None = None,
    entry_source: str | None = None,
    model_contract_signature: str | None = None,
) -> str:
    payload = {
        "analysis_date": analysis_date,
        "legs": json.loads(legs_json),
        "quote_evidence": json.loads(quote_evidence_json),
        "reference_total_odds": reference_total_odds,
        "played_total_odds": played_total_odds,
        "joint_probability": joint_probability,
        "expected_roi": expected_roi,
        "definition_version": definition_version,
    }
    if definition_version >= 3:
        if (
            isinstance(stake_cents, bool)
            or not isinstance(stake_cents, int)
            or stake_cents <= 0
            or not str(created_at or "").strip()
            or not str(quote_verified_at or "").strip()
            or str(analysis_timezone or "") != CHALLENGE_TIMEZONE_NAME
            or str(entry_source or "") not in {"MODEL", "MANUAL"}
        ):
            raise ValueError("Version 3 ticket definition metadata is incomplete")
        payload.update(
            {
                "stake_cents": stake_cents,
                "created_at": str(created_at),
                "quote_verified_at": _utc_datetime(
                    quote_verified_at,
                    "quote_verified_at",
                ).isoformat(),
                "analysis_timezone": CHALLENGE_TIMEZONE_NAME,
                "entry_source": str(entry_source),
                "model_contract_signature": model_contract_signature,
            }
        )
    return _sha256_text(_canonical_json(payload))


def _legacy_market_definition(leg: dict[str, Any]) -> dict[str, Any]:
    """Best-effort, explicitly legacy-tagged enrichment for old tickets."""
    if leg.get("manual"):
        return {
            "market_key": "MANUAL_LEGACY",
            "market_kind": "manual",
            "market_side": None,
            "market_threshold": None,
            "market_low": None,
            "market_high": None,
            "settlement_rule_version": 0,
        }
    matches = [
        spec
        for spec in MARKET_BY_KEY.values()
        if spec.market == leg.get("market") and spec.selection == leg.get("selection")
    ]
    if len(matches) != 1:
        return {
            "market_key": "LEGACY_UNRESOLVED",
            "market_kind": "legacy_unresolved",
            "market_side": None,
            "market_threshold": None,
            "market_low": None,
            "market_high": None,
            "settlement_rule_version": 0,
        }
    spec = matches[0]
    return {
        "market_key": spec.key,
        "market_kind": spec.kind,
        "market_side": spec.side,
        "market_threshold": spec.threshold,
        "market_low": spec.low,
        "market_high": spec.high,
        "settlement_rule_version": 0,
    }


class ChallengeLedger:
    """Store challenge settings and settle one ticket per calendar day."""

    def __init__(self, db_path: str | Path = DEFAULT_CHALLENGE_DB):
        self.db_path = str(db_path)
        self._last_authenticated_price_state: dict[str, Any] | None = None
        self._integrity_key, self._integrity_key_path = _load_ledger_hmac_key(
            db_path
        )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        # SQLite has no per-table writer roles.  Mutation triggers therefore
        # require a function that exists only on connections opened by this
        # ledger.  Raw sqlite connections remain useful for read-only audits,
        # but cannot append money or rewrite settlement state accidentally.
        connection.create_function(
            "challenge_write_authorized",
            0,
            lambda: 1,
            deterministic=True,
        )
        return connection

    def _integrity_checkpoint_state(
        self,
        connection: sqlite3.Connection,
    ) -> dict[str, Any]:
        settings = connection.execute(
            "SELECT * FROM challenge_settings WHERE id=1"
        ).fetchone()
        if settings is None:
            raise RuntimeError("Challenge settings are missing")
        financial_tail = connection.execute(
            """
            SELECT record_hash FROM challenge_transactions
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
        settlement_tail = connection.execute(
            """
            SELECT record_hash FROM challenge_settlement_events
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
        financial_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM challenge_transactions"
            ).fetchone()[0]
        )
        settlement_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM challenge_settlement_events"
            ).fetchone()[0]
        )
        ticket_count = int(
            connection.execute("SELECT COUNT(*) FROM challenge_tickets").fetchone()[
                0
            ]
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
        price_tail_hash = (
            str(price_rows[-1]["record_hash"] or "")
            if price_rows
            else PRICE_ZERO_HASH
        )
        tickets = []
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
            FROM challenge_tickets
            ORDER BY id ASC
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
                    "stake_cents": _sqlite_integer(
                        row["stake_cents"], "ticket stake_cents"
                    ),
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
            # The external HMAC key is intentionally shared by account ledgers.
            # Bind the checkpoint to its canonical file slot so a valid signed
            # database cannot be replayed as another account's database.
            "ledger_scope": str(Path(self.db_path).resolve(strict=False)),
            "schema_manifest_hash": _challenge_schema_manifest_hash(connection),
            "sequences": _challenge_sequence_state(connection),
            "price_observation_count": len(price_ids),
            "price_observation_ids": price_ids,
            "price_observation_tail_hash": price_tail_hash,
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
                    settings["starting_balance_cents"],
                    "settings starting_balance_cents",
                ),
                "current_balance_cents": _sqlite_integer(
                    settings["current_balance_cents"],
                    "settings current_balance_cents",
                ),
                "target_balance_cents": _sqlite_integer(
                    settings["target_balance_cents"],
                    "settings target_balance_cents",
                ),
                "stake_fraction_bps": _sqlite_integer(
                    settings["stake_fraction_bps"], "settings stake_fraction_bps"
                ),
                "stake_policy_version": _sqlite_integer(
                    settings["stake_policy_version"],
                    "settings stake_policy_version",
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
            # Bind every field of every ticket.  Legacy tickets lack replayable
            # events, so authenticating their complete materialized snapshot is
            # the only fail-closed protection against same-count rewrites.
            "tickets": tickets,
        }

    def _verify_integrity_checkpoint(
        self,
        connection: sqlite3.Connection,
    ) -> tuple[bool, int | None]:
        row = connection.execute(
            "SELECT * FROM challenge_integrity_checkpoint WHERE id=1"
        ).fetchone()
        checkpoint_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM challenge_integrity_checkpoint"
            ).fetchone()[0]
        )
        if row is None or checkpoint_count != 1:
            return False, None
        try:
            version = _sqlite_integer(
                row["checkpoint_version"], "checkpoint version"
            )
            stored_financial_count = _sqlite_integer(
                row["financial_count"], "checkpoint financial_count"
            )
            stored_settlement_count = _sqlite_integer(
                row["settlement_count"], "checkpoint settlement_count"
            )
            stored_ticket_count = _sqlite_integer(
                row["ticket_count"], "checkpoint ticket_count"
            )
            stored_mac = str(row["record_mac"] or "")
        except (TypeError, ValueError, OverflowError):
            return False, None
        if version != INTEGRITY_CHECKPOINT_VERSION or len(stored_mac) != 64:
            return False, None
        try:
            price_chain_valid, _ = PriceLedger._verify_rows(connection)
            if not price_chain_valid:
                return False, None
            state = self._integrity_checkpoint_state(connection)
            expected_mac = _integrity_checkpoint_mac(self._integrity_key, state)
        except (TypeError, ValueError, OverflowError, RuntimeError):
            return False, None
        if (
            stored_financial_count != state["financial_count"]
            or str(row["financial_tail_hash"] or "")
            != state["financial_tail_hash"]
            or stored_settlement_count != state["settlement_count"]
            or str(row["settlement_tail_hash"] or "")
            != state["settlement_tail_hash"]
            or stored_ticket_count != state["ticket_count"]
            or not hmac.compare_digest(stored_mac, expected_mac)
        ):
            return False, None
        self._last_authenticated_price_state = {
            "sequences": [dict(item) for item in state["sequences"]],
            "price_observation_count": state["price_observation_count"],
            "price_observation_ids": list(state["price_observation_ids"]),
            "price_observation_tail_hash": state["price_observation_tail_hash"],
        }
        return True, None

    def _reconcile_authenticated_price_appends(
        self,
        connection: sqlite3.Connection,
        expected_new_receipts: list[dict[str, Any]],
    ) -> None:
        """Advance a checkpoint only across verified append-only price rows."""

        valid, _ = self._verify_integrity_checkpoint(connection)
        if valid:
            return
        previous = self._last_authenticated_price_state
        if previous is None:
            raise RuntimeError("Authenticated price checkpoint baseline is missing")
        current = self._integrity_checkpoint_state(connection)
        prior_state = dict(current)
        prior_state.update(
            {
                "sequences": [dict(item) for item in previous["sequences"]],
                "price_observation_count": previous["price_observation_count"],
                "price_observation_ids": list(previous["price_observation_ids"]),
                "price_observation_tail_hash": previous[
                    "price_observation_tail_hash"
                ],
            }
        )
        checkpoint = connection.execute(
            "SELECT * FROM challenge_integrity_checkpoint WHERE id=1"
        ).fetchone()
        if checkpoint is None or connection.execute(
            "SELECT COUNT(*) FROM challenge_integrity_checkpoint"
        ).fetchone()[0] != 1:
            raise RuntimeError("Authenticated integrity checkpoint is ambiguous")
        if (
            _sqlite_integer(
                checkpoint["checkpoint_version"], "checkpoint version"
            )
            != INTEGRITY_CHECKPOINT_VERSION
            or _sqlite_integer(
                checkpoint["financial_count"], "checkpoint financial_count"
            )
            != prior_state["financial_count"]
            or str(checkpoint["financial_tail_hash"] or "")
            != prior_state["financial_tail_hash"]
            or _sqlite_integer(
                checkpoint["settlement_count"], "checkpoint settlement_count"
            )
            != prior_state["settlement_count"]
            or str(checkpoint["settlement_tail_hash"] or "")
            != prior_state["settlement_tail_hash"]
            or _sqlite_integer(
                checkpoint["ticket_count"], "checkpoint ticket_count"
            )
            != prior_state["ticket_count"]
            or not hmac.compare_digest(
                str(checkpoint["record_mac"] or ""),
                _integrity_checkpoint_mac(self._integrity_key, prior_state),
            )
        ):
            raise RuntimeError("Authenticated price checkpoint baseline failed")

        old_sequences = {
            str(item["name"]): _sqlite_integer(
                item["sequence"], f'{item["name"]} sequence'
            )
            for item in previous["sequences"]
        }
        new_sequences = {
            str(item["name"]): _sqlite_integer(
                item["sequence"], f'{item["name"]} sequence'
            )
            for item in current["sequences"]
        }
        old_price_sequence = old_sequences.pop("price_observations", 0)
        new_price_sequence = new_sequences.pop("price_observations", 0)
        old_count = _sqlite_integer(
            previous["price_observation_count"], "previous price row count"
        )
        new_count = _sqlite_integer(
            current["price_observation_count"], "current price row count"
        )
        old_ids = [
            _sqlite_integer(value, "previous price observation id")
            for value in previous["price_observation_ids"]
        ]
        new_ids = [
            _sqlite_integer(value, "current price observation id")
            for value in current["price_observation_ids"]
        ]
        expected_receipts = [dict(receipt) for receipt in expected_new_receipts]
        expected_ids = [
            _sqlite_integer(receipt.get("id"), "expected new price observation id")
            for receipt in expected_receipts
        ]
        current_receipts = [
            PriceLedger._row_receipt(row)
            for row in connection.execute(
                "SELECT * FROM price_observations WHERE id>? ORDER BY id ASC",
                (old_ids[-1] if old_ids else 0,),
            )
        ]
        chain_valid, _ = PriceLedger._verify_rows(connection)
        if (
            old_sequences != new_sequences
            or new_count <= old_count
            or old_count != len(old_ids)
            or new_count != len(new_ids)
            or new_ids[:old_count] != old_ids
            or new_ids[old_count:] != expected_ids
            or current_receipts != expected_receipts
            or expected_ids
            != list(
                range(
                    old_price_sequence + 1,
                    old_price_sequence + 1 + len(expected_ids),
                )
            )
            or new_price_sequence
            != old_price_sequence + len(expected_ids)
            or not expected_ids
            or not chain_valid
        ):
            raise RuntimeError("Price observation sequence advance is invalid")
        if old_ids:
            old_tail = connection.execute(
                "SELECT record_hash FROM price_observations WHERE id=?",
                (old_ids[-1],),
            ).fetchone()
            if old_tail is None or not hmac.compare_digest(
                str(old_tail["record_hash"] or ""),
                str(previous["price_observation_tail_hash"]),
            ):
                raise RuntimeError("Authenticated price history prefix changed")
        elif previous["price_observation_tail_hash"] != PRICE_ZERO_HASH:
            raise RuntimeError("Authenticated empty price history is invalid")
        self._refresh_integrity_checkpoint(connection)

    def _refresh_integrity_checkpoint(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        state = self._integrity_checkpoint_state(connection)
        record_mac = _integrity_checkpoint_mac(self._integrity_key, state)
        connection.execute(
            """
            INSERT INTO challenge_integrity_checkpoint (
                id, checkpoint_version, financial_count,
                financial_tail_hash, settlement_count,
                settlement_tail_hash, ticket_count, record_mac
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                checkpoint_version=excluded.checkpoint_version,
                financial_count=excluded.financial_count,
                financial_tail_hash=excluded.financial_tail_hash,
                settlement_count=excluded.settlement_count,
                settlement_tail_hash=excluded.settlement_tail_hash,
                ticket_count=excluded.ticket_count,
                record_mac=excluded.record_mac
            """,
            (
                INTEGRITY_CHECKPOINT_VERSION,
                state["financial_count"],
                state["financial_tail_hash"],
                state["settlement_count"],
                state["settlement_tail_hash"],
                state["ticket_count"],
                record_mac,
            ),
        )

    def _verify_financial_rows(
        self,
        connection: sqlite3.Connection,
        *,
        require_checkpoint: bool = True,
    ) -> tuple[bool, int | None]:
        """Verify authenticated money/event chains and materialized state."""

        settings_row = connection.execute(
            """
            SELECT current_balance_cents, financial_chain_version,
                   financial_anchor_hash
            FROM challenge_settings WHERE id=1
            """
        ).fetchone()
        rows = connection.execute(
            "SELECT * FROM challenge_transactions ORDER BY id ASC"
        ).fetchall()
        if settings_row is None or not rows:
            return False, None
        try:
            if _sqlite_integer(
                settings_row["financial_chain_version"],
                "settings financial_chain_version",
            ) != FINANCIAL_CHAIN_VERSION:
                return False, None
        except (TypeError, ValueError, OverflowError):
            return False, None

        first = rows[0]
        first_id = _sqlite_integer(first["id"], "transaction id")
        known_ticket_ids = {
            _sqlite_integer(row["id"], "ticket id")
            for row in connection.execute("SELECT id FROM challenge_tickets")
        }
        expected_previous = FINANCIAL_ZERO_HASH
        running_balance: int | None = None
        for index, row in enumerate(rows):
            row_id = _sqlite_integer(row["id"], "transaction id")
            try:
                kind = str(row["kind"])
                amount = _sqlite_integer(
                    row["amount_cents"], "transaction amount_cents"
                )
                balance_after = _sqlite_integer(
                    row["balance_after_cents"],
                    "transaction balance_after_cents",
                )
                ticket_id = (
                    _sqlite_integer(row["ticket_id"], "transaction ticket_id")
                    if row["ticket_id"] is not None
                    else None
                )
                chain_version = _sqlite_integer(
                    row["chain_version"], "transaction chain_version"
                )
                previous_hash = str(row["previous_hash"] or "")
                record_hash = str(row["record_hash"] or "")
                _utc_datetime(row["created_at"], "transaction created_at")
            except (TypeError, ValueError, OverflowError):
                return False, row_id
            if (
                kind not in FINANCIAL_ALLOWED_KINDS
                or chain_version != FINANCIAL_CHAIN_VERSION
                or previous_hash != expected_previous
                or len(record_hash) != 64
                or any(character not in "0123456789abcdef" for character in record_hash)
                or not hmac.compare_digest(
                    record_hash,
                    _financial_record_mac(
                        self._integrity_key,
                        created_at=str(row["created_at"]),
                        kind=kind,
                        amount_cents=amount,
                        balance_after_cents=balance_after,
                        ticket_id=ticket_id,
                        note=row["note"],
                        previous_hash=previous_hash,
                        chain_version=chain_version,
                    ),
                )
            ):
                return False, row_id
            if kind in FINANCIAL_ANCHOR_KINDS | FINANCIAL_ACCOUNT_KINDS:
                if ticket_id is not None:
                    return False, row_id
            elif (
                ticket_id is None
                or ticket_id <= 0
                or ticket_id not in known_ticket_ids
            ):
                return False, row_id
            if (
                (kind == "STAKE" and amount >= 0)
                or (kind == "PAYOUT" and amount <= 0)
                or (kind == "LOSS_SETTLED" and amount != 0)
                or (kind == "VOID_REFUND" and amount <= 0)
                or (kind == "SETTLEMENT_REVERSAL" and amount > 0)
            ):
                return False, row_id

            if index == 0:
                if (
                    kind not in FINANCIAL_ANCHOR_KINDS
                    or (
                        kind == "OPENING_BALANCE"
                        and amount != balance_after
                    )
                    or (
                        kind == "MIGRATION_SNAPSHOT"
                        and amount != 0
                    )
                ):
                    return False, row_id
            else:
                if kind in FINANCIAL_ANCHOR_KINDS or running_balance is None:
                    return False, row_id
                if balance_after != running_balance + amount:
                    return False, row_id
            running_balance = balance_after
            expected_previous = record_hash

        if not hmac.compare_digest(
            str(settings_row["financial_anchor_hash"] or ""),
            str(first["record_hash"] or ""),
        ):
            return False, first_id
        if (
            running_balance is None
            or _sqlite_integer(
                settings_row["current_balance_cents"],
                "settings current_balance_cents",
            )
            != running_balance
        ):
            return False, _sqlite_integer(rows[-1]["id"], "transaction id")
        events_valid, bad_event_id = self._verify_settlement_event_chain(connection)
        if not events_valid:
            return False, bad_event_id
        reconciled, bad_record = self._verify_v3_settlement_rows(connection)
        if not reconciled:
            return False, bad_record
        if require_checkpoint:
            return self._verify_integrity_checkpoint(connection)
        return True, None

    def _verify_settlement_event_chain(
        self,
        connection: sqlite3.Connection,
    ) -> tuple[bool, int | None]:
        """Authenticate every event globally before per-ticket replay."""

        settings = connection.execute(
            """
            SELECT settlement_chain_version, settlement_anchor_hash
            FROM challenge_settings WHERE id=1
            """
        ).fetchone()
        rows = connection.execute(
            "SELECT * FROM challenge_settlement_events ORDER BY id ASC"
        ).fetchall()
        if settings is None:
            return False, None
        try:
            if _sqlite_integer(
                settings["settlement_chain_version"],
                "settings settlement_chain_version",
            ) != SETTLEMENT_CHAIN_VERSION:
                return False, None
        except (TypeError, ValueError, OverflowError):
            return False, None

        try:
            known_ticket_ids = {
                _sqlite_integer(row["id"], "ticket id")
                for row in connection.execute("SELECT id FROM challenge_tickets")
            }
        except (TypeError, ValueError, OverflowError):
            return False, None
        expected_previous = SETTLEMENT_ZERO_HASH
        for row in rows:
            try:
                row_id = _sqlite_integer(row["id"], "settlement event id")
                ticket_id = _sqlite_integer(
                    row["ticket_id"], "settlement event ticket_id"
                )
                action = str(row["action"])
                previous_status = row["previous_status"]
                new_status = str(row["new_status"])
                previous_payout = _sqlite_integer(
                    row["previous_payout_cents"],
                    "settlement event previous_payout_cents",
                )
                new_payout = _sqlite_integer(
                    row["new_payout_cents"],
                    "settlement event new_payout_cents",
                )
                settlement_odds = (
                    float(row["settlement_odds"])
                    if row["settlement_odds"] is not None
                    else None
                )
                rule_version = _sqlite_integer(
                    row["rule_version"], "settlement event rule_version"
                )
                source = str(row["source"])
                reason = str(row["reason"])
                chain_version = _sqlite_integer(
                    row["chain_version"], "settlement event chain_version"
                )
                previous_hash = str(row["previous_hash"] or "")
                record_hash = str(row["record_hash"] or "")
                _utc_datetime(row["created_at"], "settlement event created_at")
            except (TypeError, ValueError, OverflowError):
                try:
                    bad_id = _sqlite_integer(row["id"], "settlement event id")
                except (TypeError, ValueError, OverflowError):
                    bad_id = None
                return False, bad_id
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
                or not hmac.compare_digest(
                    record_hash,
                    _settlement_record_mac(
                        self._integrity_key,
                        ticket_id=ticket_id,
                        created_at=str(row["created_at"]),
                        action=action,
                        previous_status=previous_status,
                        new_status=new_status,
                        previous_payout_cents=previous_payout,
                        new_payout_cents=new_payout,
                        settlement_odds=settlement_odds,
                        rule_version=rule_version,
                        source=source,
                        reason=reason,
                        previous_hash=previous_hash,
                        chain_version=chain_version,
                    ),
                )
            ):
                return False, row_id
            expected_previous = record_hash

        anchor = str(settings["settlement_anchor_hash"] or "")
        if rows:
            if not hmac.compare_digest(anchor, str(rows[0]["record_hash"] or "")):
                return False, _sqlite_integer(
                    rows[0]["id"], "settlement event id"
                )
        elif anchor:
            return False, None
        return True, None

    @staticmethod
    def _verify_v3_settlement_rows(
        connection: sqlite3.Connection,
    ) -> tuple[bool, int | None]:
        """Replay v3 settlement events and reconcile every linked money row."""

        tickets = connection.execute(
            """
            SELECT * FROM challenge_tickets
            WHERE COALESCE(definition_version, 0) >= 3
            ORDER BY id ASC
            """
        ).fetchall()
        for ticket in tickets:
            try:
                ticket_id = _sqlite_integer(ticket["id"], "ticket id")
                ticket_stake_cents = _sqlite_integer(
                    ticket["stake_cents"], "ticket stake_cents"
                )
                ticket_payout_cents = _sqlite_integer(
                    ticket["payout_cents"], "ticket payout_cents"
                )
                ticket_settlement_rule_version = _sqlite_integer(
                    ticket["settlement_rule_version"],
                    "ticket settlement_rule_version",
                )
            except (TypeError, ValueError, OverflowError):
                return False, None
            transactions = connection.execute(
                """
                SELECT * FROM challenge_transactions
                WHERE ticket_id=? ORDER BY id ASC
                """,
                (ticket_id,),
            ).fetchall()
            stake_rows = [row for row in transactions if row["kind"] == "STAKE"]
            settlement_rows = [row for row in transactions if row["kind"] != "STAKE"]
            try:
                bad_id = (
                    _sqlite_integer(transactions[-1]["id"], "transaction id")
                    if transactions
                    else None
                )
                stake_amount = (
                    _sqlite_integer(
                        stake_rows[0]["amount_cents"],
                        "stake transaction amount_cents",
                    )
                    if len(stake_rows) == 1
                    else None
                )
            except (TypeError, ValueError, OverflowError):
                return False, None
            if (
                len(stake_rows) != 1
                or stake_amount != -ticket_stake_cents
                or str(stake_rows[0]["created_at"]) != str(ticket["created_at"])
            ):
                return False, bad_id

            events = connection.execute(
                """
                SELECT * FROM challenge_settlement_events
                WHERE ticket_id=? ORDER BY id ASC
                """,
                (ticket_id,),
            ).fetchall()
            if len(events) != len(settlement_rows):
                return False, bad_id

            entry_source = str(ticket["entry_source"] or "")
            if entry_source == "MODEL":
                state: str | None = "PENDING"
            elif entry_source == "MANUAL":
                state = None
            else:
                return False, bad_id
            payout = 0
            latest_event: sqlite3.Row | None = None
            for event_index, (event, transaction) in enumerate(
                zip(events, settlement_rows)
            ):
                try:
                    transaction_id = _sqlite_integer(
                        transaction["id"], "transaction id"
                    )
                    transaction_amount = _sqlite_integer(
                        transaction["amount_cents"],
                        "settlement transaction amount_cents",
                    )
                    _sqlite_integer(event["id"], "settlement event id")
                    _sqlite_integer(
                        event["ticket_id"], "settlement event ticket_id"
                    )
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
                    event_rule_version = _sqlite_integer(
                        event["rule_version"],
                        "settlement event rule_version",
                    )
                    _sqlite_integer(
                        event["chain_version"],
                        "settlement event chain_version",
                    )
                except (TypeError, ValueError, OverflowError):
                    return False, bad_id
                if (
                    event_rule_version != SETTLEMENT_RULE_VERSION
                    or not str(event["source"] or "").strip()
                    or not str(event["reason"] or "").strip()
                    or previous_payout != payout
                    or str(transaction["created_at"]) != str(event["created_at"])
                ):
                    return False, transaction_id

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
                        return False, transaction_id
                    if new_status not in {"WON", "LOST", "VOID"}:
                        return False, transaction_id
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
                        return False, transaction_id
                    expected_kind = "SETTLEMENT_CORRECTION"
                elif action == "REVERSE":
                    if (
                        state not in {"WON", "LOST", "VOID"}
                        or previous_status != state
                        or new_status != "PENDING"
                        or new_payout != 0
                        or event["settlement_odds"] is not None
                    ):
                        return False, transaction_id
                    expected_kind = "SETTLEMENT_REVERSAL"
                else:
                    return False, transaction_id

                settlement_odds = event["settlement_odds"]
                if new_status == "WON":
                    try:
                        effective_odds = validate_decimal_odds(settlement_odds)
                    except BettingMathError:
                        return False, transaction_id
                    calculated_payout = int(
                        (
                            Decimal(ticket_stake_cents)
                            * Decimal(str(effective_odds))
                        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    )
                    if abs(new_payout - calculated_payout) > 1:
                        return False, transaction_id
                elif new_status == "LOST":
                    if new_payout != 0 or settlement_odds is not None:
                        return False, transaction_id
                elif new_status == "VOID":
                    if (
                        new_payout != ticket_stake_cents
                        or settlement_odds is not None
                    ):
                        return False, transaction_id
                elif new_status == "PENDING":
                    if new_payout != 0 or settlement_odds is not None:
                        return False, transaction_id
                else:
                    return False, transaction_id

                if (
                    str(transaction["kind"]) != expected_kind
                    or transaction_amount != new_payout - payout
                ):
                    return False, transaction_id
                state = new_status
                payout = new_payout
                latest_event = event

            materialized_status = str(ticket["status"])
            if entry_source == "MANUAL" and latest_event is None:
                return False, bad_id
            if state is None or materialized_status != state:
                return False, bad_id
            if ticket_payout_cents != payout:
                return False, bad_id
            if ticket_settlement_rule_version != SETTLEMENT_RULE_VERSION:
                return False, bad_id
            if state == "PENDING":
                if (
                    ticket["settled_at"] is not None
                    or ticket["settlement_odds"] is not None
                ):
                    return False, bad_id
                if latest_event is None:
                    if ticket["settlement_note"] is not None:
                        return False, bad_id
                elif (
                    latest_event["action"] != "REVERSE"
                    or str(ticket["settlement_note"] or "").strip()
                    != str(latest_event["reason"] or "").strip()
                ):
                    return False, bad_id
            else:
                if latest_event is None:
                    return False, bad_id
                if (
                    str(ticket["settled_at"]) != str(latest_event["created_at"])
                    or ticket["settlement_odds"] != latest_event["settlement_odds"]
                    or str(ticket["settlement_note"] or "").strip()
                    != str(latest_event["reason"] or "").strip()
                ):
                    return False, bad_id
        return True, None

    def _require_financial_ledger(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        valid, bad_id = self._verify_financial_rows(connection)
        if not valid:
            location = (
                f" at record {bad_id}" if bad_id is not None else ""
            )
            raise RuntimeError(
                f"Challenge financial ledger integrity check failed{location}"
            )

    def verify_financial_ledger(self) -> tuple[bool, int | None]:
        with closing(self._connect()) as connection:
            return self._verify_financial_rows(connection)

    @classmethod
    def _require_ticket_definitions(
        cls,
        connection: sqlite3.Connection,
    ) -> None:
        rows = connection.execute(
            "SELECT * FROM challenge_tickets ORDER BY id ASC"
        ).fetchall()
        for row in rows:
            cls._row_to_ticket(row)

    @staticmethod
    def _validate_legacy_financial_rows(
        connection: sqlite3.Connection,
    ) -> None:
        """Validate an unsigned predecessor ledger before a one-time backfill."""

        settings = connection.execute(
            "SELECT current_balance_cents FROM challenge_settings WHERE id=1"
        ).fetchone()
        rows = connection.execute(
            "SELECT * FROM challenge_transactions ORDER BY id ASC"
        ).fetchall()
        if settings is None or not rows:
            raise RuntimeError("Legacy challenge financial ledger has no anchor")
        known_ticket_ids = {
            _sqlite_integer(row["id"], "legacy ticket id")
            for row in connection.execute("SELECT id FROM challenge_tickets")
        }
        running_balance: int | None = None
        for index, row in enumerate(rows):
            try:
                row_id = _sqlite_integer(row["id"], "legacy transaction id")
                kind = str(row["kind"])
                amount = _sqlite_integer(
                    row["amount_cents"], "legacy transaction amount_cents"
                )
                balance_after = _sqlite_integer(
                    row["balance_after_cents"],
                    "legacy transaction balance_after_cents",
                )
                ticket_id = (
                    _sqlite_integer(
                        row["ticket_id"], "legacy transaction ticket_id"
                    )
                    if row["ticket_id"] is not None
                    else None
                )
                _utc_datetime(row["created_at"], "transaction created_at")
            except (TypeError, ValueError, OverflowError) as exc:
                raise RuntimeError(
                    f"Legacy financial transaction {row_id} is invalid"
                ) from exc
            if kind not in FINANCIAL_ALLOWED_KINDS:
                raise RuntimeError(
                    f"Legacy financial transaction {row_id} has an unknown kind"
                )
            if kind in FINANCIAL_ANCHOR_KINDS | FINANCIAL_ACCOUNT_KINDS:
                if ticket_id is not None:
                    raise RuntimeError(
                        f"Legacy financial transaction {row_id} has an invalid ticket"
                    )
            elif (
                ticket_id is None
                or ticket_id <= 0
                or ticket_id not in known_ticket_ids
            ):
                raise RuntimeError(
                    f"Legacy financial transaction {row_id} lacks a ticket"
                )
            if (
                (kind == "STAKE" and amount >= 0)
                or (kind == "PAYOUT" and amount <= 0)
                or (kind == "LOSS_SETTLED" and amount != 0)
                or (kind == "VOID_REFUND" and amount <= 0)
                or (kind == "SETTLEMENT_REVERSAL" and amount > 0)
            ):
                raise RuntimeError(
                    f"Legacy financial transaction {row_id} has invalid semantics"
                )
            if index == 0:
                if (
                    kind not in FINANCIAL_ANCHOR_KINDS
                    or (kind == "OPENING_BALANCE" and amount != balance_after)
                    or (kind == "MIGRATION_SNAPSHOT" and amount != 0)
                ):
                    raise RuntimeError("Legacy challenge financial anchor is invalid")
            elif (
                running_balance is None
                or kind in FINANCIAL_ANCHOR_KINDS
                or balance_after != running_balance + amount
            ):
                raise RuntimeError(
                    f"Legacy financial transaction {row_id} breaks the balance chain"
                )
            running_balance = balance_after
        try:
            settings_balance = _sqlite_integer(
                settings["current_balance_cents"],
                "legacy settings current_balance_cents",
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("Legacy challenge settings are invalid") from exc
        if running_balance != settings_balance:
            raise RuntimeError("Legacy financial ledger disagrees with settings")

    def _migrate_financial_chain(self, connection: sqlite3.Connection) -> None:
        """Migrate only a complete, semantically valid v0 ledger to HMAC v2."""

        settings = connection.execute(
            """
            SELECT financial_chain_version, financial_anchor_hash
            FROM challenge_settings WHERE id=1
            """
        ).fetchone()
        if settings is None:
            raise RuntimeError("Challenge settings are missing")
        try:
            version = _sqlite_integer(
                settings["financial_chain_version"],
                "settings financial_chain_version",
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("Challenge financial chain version is invalid") from exc
        rows = connection.execute(
            "SELECT * FROM challenge_transactions ORDER BY id ASC"
        ).fetchall()
        if version == FINANCIAL_CHAIN_VERSION:
            try:
                complete = all(
                    _sqlite_integer(
                        row["chain_version"], "transaction chain_version"
                    )
                    == FINANCIAL_CHAIN_VERSION
                    and bool(row["previous_hash"])
                    and bool(row["record_hash"])
                    for row in rows
                )
            except (TypeError, ValueError, OverflowError):
                complete = False
            if not complete:
                raise RuntimeError("Challenge financial HMAC chain is incomplete")
            return
        if version != 0:
            raise RuntimeError("Challenge financial chain version is unsupported")
        try:
            unsigned = all(
                _sqlite_integer(row["chain_version"], "transaction chain_version")
                == 0
                and row["previous_hash"] is None
                and row["record_hash"] is None
                for row in rows
            )
        except (TypeError, ValueError, OverflowError):
            unsigned = False
        if settings["financial_anchor_hash"] is not None or not unsigned:
            raise RuntimeError("Partial financial migration requires manual review")
        self._validate_legacy_financial_rows(connection)

        # BEGIN IMMEDIATE makes the validated one-time rewrite atomic. Existing
        # append/anchor guards are restored by rollback if any statement fails.
        connection.execute("DROP TRIGGER IF EXISTS challenge_transactions_no_update")
        connection.execute("DROP TRIGGER IF EXISTS challenge_financial_anchor_immutable")
        previous_hash = FINANCIAL_ZERO_HASH
        anchor_hash: str | None = None
        for row in rows:
            row_id = _sqlite_integer(row["id"], "legacy transaction id")
            digest = _financial_record_mac(
                self._integrity_key,
                created_at=str(row["created_at"]),
                kind=str(row["kind"]),
                amount_cents=_sqlite_integer(
                    row["amount_cents"], "legacy transaction amount_cents"
                ),
                balance_after_cents=_sqlite_integer(
                    row["balance_after_cents"],
                    "legacy transaction balance_after_cents",
                ),
                ticket_id=(
                    _sqlite_integer(
                        row["ticket_id"], "legacy transaction ticket_id"
                    )
                    if row["ticket_id"] is not None
                    else None
                ),
                note=row["note"],
                previous_hash=previous_hash,
            )
            connection.execute(
                """
                UPDATE challenge_transactions
                SET chain_version=?, previous_hash=?, record_hash=?
                WHERE id=?
                """,
                (
                    FINANCIAL_CHAIN_VERSION,
                    previous_hash,
                    digest,
                    row_id,
                ),
            )
            if anchor_hash is None:
                anchor_hash = digest
            previous_hash = digest
        if anchor_hash is None:
            raise RuntimeError("Challenge financial chain has no anchor")
        connection.execute(
            """
            UPDATE challenge_settings
            SET financial_chain_version=?, financial_anchor_hash=?
            WHERE id=1
            """,
            (FINANCIAL_CHAIN_VERSION, anchor_hash),
        )

    @staticmethod
    def _validate_legacy_settlement_rows(
        connection: sqlite3.Connection,
    ) -> None:
        """Validate unsigned events globally before signing them once."""

        known_ticket_ids = {
            _sqlite_integer(row["id"], "legacy ticket id")
            for row in connection.execute("SELECT id FROM challenge_tickets")
        }
        rows = connection.execute(
            "SELECT * FROM challenge_settlement_events ORDER BY id ASC"
        ).fetchall()
        for row in rows:
            try:
                row_id = _sqlite_integer(row["id"], "legacy settlement event id")
                ticket_id = _sqlite_integer(
                    row["ticket_id"], "legacy settlement event ticket_id"
                )
                previous_payout = _sqlite_integer(
                    row["previous_payout_cents"],
                    "legacy settlement event previous_payout_cents",
                )
                new_payout = _sqlite_integer(
                    row["new_payout_cents"],
                    "legacy settlement event new_payout_cents",
                )
                rule_version = _sqlite_integer(
                    row["rule_version"],
                    "legacy settlement event rule_version",
                )
                _utc_datetime(row["created_at"], "settlement event created_at")
            except (TypeError, ValueError, OverflowError) as exc:
                raise RuntimeError(
                    f"Legacy settlement event {row_id} is invalid"
                ) from exc
            source = str(row["source"] or "")
            reason = str(row["reason"] or "")
            if (
                ticket_id <= 0
                or ticket_id not in known_ticket_ids
                or str(row["action"]) not in {"SETTLE", "CORRECT", "REVERSE"}
                or row["previous_status"]
                not in {None, "PENDING", "WON", "LOST", "VOID"}
                or str(row["new_status"]) not in VALID_STATUSES
                or previous_payout < 0
                or new_payout < 0
                or rule_version != SETTLEMENT_RULE_VERSION
                or source not in SETTLEMENT_ALLOWED_SOURCES
                or source != source.strip()
                or not reason.strip()
                or reason != reason.strip()
            ):
                raise RuntimeError(
                    f"Legacy settlement event {row_id} has invalid semantics"
                )
        valid, bad_id = ChallengeLedger._verify_v3_settlement_rows(connection)
        if not valid:
            location = f" at record {bad_id}" if bad_id is not None else ""
            raise RuntimeError(
                f"Legacy settlement reconciliation failed{location}"
            )

    def _migrate_settlement_chain(self, connection: sqlite3.Connection) -> None:
        """Authenticate the complete validated settlement history."""

        settings = connection.execute(
            """
            SELECT settlement_chain_version, settlement_anchor_hash
            FROM challenge_settings WHERE id=1
            """
        ).fetchone()
        if settings is None:
            raise RuntimeError("Challenge settings are missing")
        try:
            version = _sqlite_integer(
                settings["settlement_chain_version"],
                "settings settlement_chain_version",
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("Settlement chain version is invalid") from exc
        rows = connection.execute(
            "SELECT * FROM challenge_settlement_events ORDER BY id ASC"
        ).fetchall()
        if version == SETTLEMENT_CHAIN_VERSION:
            try:
                complete = all(
                    _sqlite_integer(
                        row["chain_version"], "settlement event chain_version"
                    )
                    == SETTLEMENT_CHAIN_VERSION
                    and bool(row["previous_hash"])
                    and bool(row["record_hash"])
                    for row in rows
                )
            except (TypeError, ValueError, OverflowError):
                complete = False
            if not complete:
                raise RuntimeError("Settlement HMAC chain is incomplete")
            if not rows and settings["settlement_anchor_hash"] is not None:
                raise RuntimeError("Empty settlement chain has an invalid anchor")
            return
        if version != 0:
            raise RuntimeError("Settlement chain version is unsupported")
        try:
            unsigned = all(
                _sqlite_integer(
                    row["chain_version"], "settlement event chain_version"
                )
                == 0
                and row["previous_hash"] is None
                and row["record_hash"] is None
                for row in rows
            )
        except (TypeError, ValueError, OverflowError):
            unsigned = False
        if settings["settlement_anchor_hash"] is not None or not unsigned:
            raise RuntimeError("Partial settlement migration requires manual review")

        self._validate_legacy_settlement_rows(connection)
        connection.execute("DROP TRIGGER IF EXISTS challenge_settlement_events_no_update")
        connection.execute("DROP TRIGGER IF EXISTS challenge_settlement_anchor_immutable")
        previous_hash = SETTLEMENT_ZERO_HASH
        anchor_hash: str | None = None
        for row in rows:
            row_id = _sqlite_integer(row["id"], "legacy settlement event id")
            digest = _settlement_record_mac(
                self._integrity_key,
                ticket_id=_sqlite_integer(
                    row["ticket_id"], "legacy settlement event ticket_id"
                ),
                created_at=str(row["created_at"]),
                action=str(row["action"]),
                previous_status=row["previous_status"],
                new_status=str(row["new_status"]),
                previous_payout_cents=_sqlite_integer(
                    row["previous_payout_cents"],
                    "legacy settlement event previous_payout_cents",
                ),
                new_payout_cents=_sqlite_integer(
                    row["new_payout_cents"],
                    "legacy settlement event new_payout_cents",
                ),
                settlement_odds=(
                    float(row["settlement_odds"])
                    if row["settlement_odds"] is not None
                    else None
                ),
                rule_version=_sqlite_integer(
                    row["rule_version"],
                    "legacy settlement event rule_version",
                ),
                source=str(row["source"]),
                reason=str(row["reason"]),
                previous_hash=previous_hash,
            )
            connection.execute(
                """
                UPDATE challenge_settlement_events
                SET chain_version=?, previous_hash=?, record_hash=?
                WHERE id=?
                """,
                (
                    SETTLEMENT_CHAIN_VERSION,
                    previous_hash,
                    digest,
                    row_id,
                ),
            )
            if anchor_hash is None:
                anchor_hash = digest
            previous_hash = digest
        connection.execute(
            """
            UPDATE challenge_settings
            SET settlement_chain_version=?, settlement_anchor_hash=?
            WHERE id=1
            """,
            (SETTLEMENT_CHAIN_VERSION, anchor_hash),
        )

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing_tables = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            settings_preexisted = "challenge_settings" in existing_tables
            checkpoint_preexisted = (
                "challenge_integrity_checkpoint" in existing_tables
            )
            preexisting_setting_columns: set[str] = set()
            preexisting_ticket_columns: set[str] = set()
            preexisting_transaction_columns: set[str] = set()
            preexisting_financial_chain_version = 0
            if settings_preexisted:
                preexisting_setting_columns = {
                    str(row["name"])
                    for row in connection.execute(
                        "PRAGMA table_info(challenge_settings)"
                    )
                }
                if "financial_chain_version" in preexisting_setting_columns:
                    preexisting_settings = connection.execute(
                        "SELECT financial_chain_version "
                        "FROM challenge_settings WHERE id=1"
                    ).fetchone()
                    if preexisting_settings is not None:
                        try:
                            preexisting_financial_chain_version = _sqlite_integer(
                                preexisting_settings["financial_chain_version"],
                                "preexisting financial_chain_version",
                            )
                        except (TypeError, ValueError, OverflowError) as exc:
                            raise RuntimeError(
                                "Challenge financial chain version is invalid"
                            ) from exc
            if "challenge_tickets" in existing_tables:
                preexisting_ticket_columns = {
                    str(row["name"])
                    for row in connection.execute(
                        "PRAGMA table_info(challenge_tickets)"
                    )
                }
            if "challenge_transactions" in existing_tables:
                preexisting_transaction_columns = {
                    str(row["name"])
                    for row in connection.execute(
                        "PRAGMA table_info(challenge_transactions)"
                    )
                }
            preexisting_hmac_artifacts = bool(
                preexisting_setting_columns
                & {
                    "financial_chain_version",
                    "financial_anchor_hash",
                    "settlement_chain_version",
                    "settlement_anchor_hash",
                }
                or preexisting_ticket_columns
                & {
                    "analysis_timezone",
                    "settlement_odds",
                    "settlement_rule_version",
                    "settlement_note",
                    "quote_evidence_json",
                    "quote_evidence_hash",
                    "ticket_definition_hash",
                    "model_contract_signature",
                    "definition_version",
                }
                or preexisting_transaction_columns
                & {"chain_version", "previous_hash", "record_hash"}
                or "challenge_settlement_events" in existing_tables
            )
            controlled_migration_authorized = False
            if (
                settings_preexisted
                and _environment_flag(LEDGER_HMAC_REQUIRED_ENV)
                and _environment_flag(LEDGER_CHECKPOINT_MIGRATION_ENV)
            ):
                _read_legacy_migration_policy(self.db_path)
                controlled_migration_authorized = True
            if checkpoint_preexisted:
                self._require_ticket_definitions(connection)
                precheck_valid, precheck_bad_record = self._verify_financial_rows(
                    connection,
                    require_checkpoint=False,
                )
                if not precheck_valid:
                    location = (
                        f" at record {precheck_bad_record}"
                        if precheck_bad_record is not None
                        else ""
                    )
                    raise RuntimeError(
                        "Challenge financial ledger HMAC chain is incomplete"
                        + location
                    )
                checkpoint_valid, _ = self._verify_integrity_checkpoint(connection)
                if not checkpoint_valid:
                    raise RuntimeError(
                        "Challenge financial ledger integrity checkpoint "
                        "precheck failed"
                    )
            elif settings_preexisted and (
                preexisting_financial_chain_version != 0
                or preexisting_hmac_artifacts
            ):
                # No committed/deployed BetBoy predecessor ever wrote v1. Any
                # non-zero chain without the checkpoint introduced alongside
                # v2 is therefore deletion/downgrade, never legacy input.
                raise RuntimeError(
                    "Challenge database has an unsupported chain or is missing "
                    "its integrity checkpoint"
                )
            elif (
                settings_preexisted
                and _environment_flag(LEDGER_HMAC_REQUIRED_ENV)
                and not controlled_migration_authorized
            ):
                raise RuntimeError(
                    "Existing challenge database requires the controlled "
                    "integrity-checkpoint migration"
                )
            if not checkpoint_preexisted:
                # Fresh and explicitly authorized v0 databases receive the
                # co-located price schema before their first whole-DB HMAC.
                # Existing v2 databases were verified above and are never
                # mutated before that precheck.
                for statement in PRICE_LEDGER_SCHEMA_STATEMENTS:
                    connection.execute(statement)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS challenge_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    starting_balance_cents INTEGER NOT NULL CHECK (starting_balance_cents >= 0),
                    current_balance_cents INTEGER NOT NULL CHECK (current_balance_cents >= 0),
                    target_balance_cents INTEGER NOT NULL CHECK (target_balance_cents > 0),
                    stake_fraction_bps INTEGER NOT NULL DEFAULT 500
                        CHECK (stake_fraction_bps BETWEEN 500 AND 2500),
                    stake_policy_version INTEGER NOT NULL DEFAULT 3
                        CHECK (stake_policy_version >= 1),
                    financial_chain_version INTEGER NOT NULL DEFAULT 0,
                    financial_anchor_hash TEXT,
                    settlement_chain_version INTEGER NOT NULL DEFAULT 0,
                    settlement_anchor_hash TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            setting_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(challenge_settings)")
            }
            if "stake_fraction_bps" not in setting_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_settings
                    ADD COLUMN stake_fraction_bps INTEGER NOT NULL DEFAULT 500
                        CHECK (stake_fraction_bps BETWEEN 500 AND 10000)
                    """
                )
            if "stake_policy_version" not in setting_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_settings
                    ADD COLUMN stake_policy_version INTEGER NOT NULL DEFAULT 1
                    """
                )
            if "financial_chain_version" not in setting_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_settings
                    ADD COLUMN financial_chain_version INTEGER NOT NULL DEFAULT 0
                    """
                )
            if "financial_anchor_hash" not in setting_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_settings
                    ADD COLUMN financial_anchor_hash TEXT
                    """
                )
            if "settlement_chain_version" not in setting_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_settings
                    ADD COLUMN settlement_chain_version INTEGER NOT NULL DEFAULT 0
                    """
                )
            if "settlement_anchor_hash" not in setting_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_settings
                    ADD COLUMN settlement_anchor_hash TEXT
                    """
                )
            connection.execute(
                """
                UPDATE challenge_settings
                SET stake_fraction_bps=?, stake_policy_version=?
                WHERE stake_policy_version<?
                """,
                (
                    int(DEFAULT_CHALLENGE_STAKE_FRACTION * 10_000),
                    STAKE_POLICY_VERSION,
                    STAKE_POLICY_VERSION,
                ),
            )
            connection.execute(
                """
                UPDATE challenge_settings
                SET stake_fraction_bps=CASE
                    WHEN stake_fraction_bps<? THEN ?
                    WHEN stake_fraction_bps>? THEN ?
                    ELSE stake_fraction_bps
                END
                """,
                (
                    MIN_STAKE_FRACTION_BPS,
                    MIN_STAKE_FRACTION_BPS,
                    MAX_STAKE_FRACTION_BPS,
                    MAX_STAKE_FRACTION_BPS,
                ),
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS challenge_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_date TEXT NOT NULL,
                    analysis_timezone TEXT NOT NULL DEFAULT 'Europe/Zurich',
                    created_at TEXT NOT NULL,
                    quote_verified_at TEXT NOT NULL,
                    settled_at TEXT,
                    status TEXT NOT NULL CHECK (status IN ('PENDING', 'WON', 'LOST', 'VOID')),
                    stake_cents INTEGER NOT NULL CHECK (stake_cents > 0),
                    payout_cents INTEGER NOT NULL DEFAULT 0 CHECK (payout_cents >= 0),
                    total_odds REAL NOT NULL CHECK (total_odds > 1),
                    played_odds REAL CHECK (played_odds IS NULL OR played_odds > 1),
                    joint_probability REAL NOT NULL CHECK (joint_probability >= 0 AND joint_probability <= 1),
                    expected_roi REAL NOT NULL,
                    legs_json TEXT NOT NULL,
                    entry_source TEXT NOT NULL DEFAULT 'MODEL',
                    settlement_odds REAL CHECK (settlement_odds IS NULL OR settlement_odds > 1),
                    settlement_rule_version INTEGER NOT NULL DEFAULT 2,
                    settlement_note TEXT,
                    quote_evidence_json TEXT NOT NULL DEFAULT '[]',
                    quote_evidence_hash TEXT,
                    ticket_definition_hash TEXT,
                    model_contract_signature TEXT,
                    definition_version INTEGER NOT NULL DEFAULT 3
                )
                """
            )
            ticket_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(challenge_tickets)")
            }
            if "played_odds" not in ticket_columns:
                connection.execute(
                    "ALTER TABLE challenge_tickets ADD COLUMN played_odds REAL"
                )
            if "entry_source" not in ticket_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_tickets
                    ADD COLUMN entry_source TEXT NOT NULL DEFAULT 'MODEL'
                    """
                )
            ticket_migrations = {
                "analysis_timezone": (
                    "ALTER TABLE challenge_tickets ADD COLUMN "
                    "analysis_timezone TEXT NOT NULL DEFAULT 'Europe/Zurich'"
                ),
                "settlement_odds": (
                    "ALTER TABLE challenge_tickets ADD COLUMN settlement_odds REAL"
                ),
                "settlement_rule_version": (
                    "ALTER TABLE challenge_tickets ADD COLUMN "
                    "settlement_rule_version INTEGER NOT NULL DEFAULT 0"
                ),
                "settlement_note": (
                    "ALTER TABLE challenge_tickets ADD COLUMN settlement_note TEXT"
                ),
                "quote_evidence_json": (
                    "ALTER TABLE challenge_tickets ADD COLUMN "
                    "quote_evidence_json TEXT NOT NULL DEFAULT '[]'"
                ),
                "quote_evidence_hash": (
                    "ALTER TABLE challenge_tickets ADD COLUMN quote_evidence_hash TEXT"
                ),
                "ticket_definition_hash": (
                    "ALTER TABLE challenge_tickets ADD COLUMN ticket_definition_hash TEXT"
                ),
                "model_contract_signature": (
                    "ALTER TABLE challenge_tickets "
                    "ADD COLUMN model_contract_signature TEXT"
                ),
                "definition_version": (
                    "ALTER TABLE challenge_tickets ADD COLUMN "
                    "definition_version INTEGER NOT NULL DEFAULT 0"
                ),
            }
            for column, statement in ticket_migrations.items():
                if column not in ticket_columns:
                    connection.execute(statement)
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_challenge_daily_ticket
                ON challenge_tickets(analysis_date)
                WHERE status != 'VOID'
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS challenge_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    balance_after_cents INTEGER NOT NULL
                        CHECK (balance_after_cents >= 0),
                    ticket_id INTEGER,
                    note TEXT,
                    chain_version INTEGER NOT NULL DEFAULT 0,
                    previous_hash TEXT,
                    record_hash TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES challenge_tickets(id)
                )
                """
            )
            transaction_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(challenge_transactions)"
                )
            }
            if "chain_version" not in transaction_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_transactions
                    ADD COLUMN chain_version INTEGER NOT NULL DEFAULT 0
                    """
                )
            if "previous_hash" not in transaction_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_transactions ADD COLUMN previous_hash TEXT
                    """
                )
            if "record_hash" not in transaction_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_transactions ADD COLUMN record_hash TEXT
                    """
                )
            connection.execute(
                "DROP TRIGGER IF EXISTS challenge_transactions_v1_insert_contract"
            )
            connection.execute(
                "DROP TRIGGER IF EXISTS challenge_transactions_v2_insert_contract"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS challenge_settlement_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    action TEXT NOT NULL CHECK (
                        action IN ('SETTLE', 'CORRECT', 'REVERSE')
                    ),
                    previous_status TEXT,
                    new_status TEXT NOT NULL CHECK (
                        new_status IN ('PENDING', 'WON', 'LOST', 'VOID')
                    ),
                    previous_payout_cents INTEGER NOT NULL DEFAULT 0,
                    new_payout_cents INTEGER NOT NULL DEFAULT 0,
                    settlement_odds REAL,
                    rule_version INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    chain_version INTEGER NOT NULL DEFAULT 0,
                    previous_hash TEXT,
                    record_hash TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES challenge_tickets(id)
                )
                """
            )
            settlement_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(challenge_settlement_events)"
                )
            }
            if "chain_version" not in settlement_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_settlement_events
                    ADD COLUMN chain_version INTEGER NOT NULL DEFAULT 0
                    """
                )
            if "previous_hash" not in settlement_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_settlement_events ADD COLUMN previous_hash TEXT
                    """
                )
            if "record_hash" not in settlement_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_settlement_events ADD COLUMN record_hash TEXT
                    """
                )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS challenge_integrity_checkpoint (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    checkpoint_version INTEGER NOT NULL,
                    financial_count INTEGER NOT NULL CHECK (financial_count >= 0),
                    financial_tail_hash TEXT NOT NULL,
                    settlement_count INTEGER NOT NULL CHECK (settlement_count >= 0),
                    settlement_tail_hash TEXT NOT NULL,
                    ticket_count INTEGER NOT NULL CHECK (ticket_count >= 0),
                    record_mac TEXT NOT NULL
                )
                """
            )
            # The financial and settlement audit trails are append-only. Current
            # ticket state remains a materialized summary that can be corrected
            # only by appending a new event and balancing transaction.
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS challenge_transactions_no_update
                BEFORE UPDATE ON challenge_transactions
                BEGIN SELECT RAISE(ABORT, 'challenge transactions are append-only'); END
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS challenge_transactions_no_delete
                BEFORE DELETE ON challenge_transactions
                BEGIN SELECT RAISE(ABORT, 'challenge transactions are append-only'); END
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS challenge_settlement_events_no_update
                BEFORE UPDATE ON challenge_settlement_events
                BEGIN SELECT RAISE(ABORT, 'settlement events are append-only'); END
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS challenge_settlement_events_no_delete
                BEFORE DELETE ON challenge_settlement_events
                BEGIN SELECT RAISE(ABORT, 'settlement events are append-only'); END
                """
            )
            model_signature_sql = CHALLENGE_MODEL_CONTRACT_SIGNATURE.replace(
                "'", "''"
            )
            connection.execute(
                "DROP TRIGGER IF EXISTS challenge_ticket_v3_insert_contract"
            )
            connection.execute(
                "DROP TRIGGER IF EXISTS challenge_ticket_v3_definition_immutable"
            )
            connection.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS challenge_ticket_v3_insert_contract
                BEFORE INSERT ON challenge_tickets
                WHEN NEW.definition_version >= 3 AND (
                    challenge_write_authorized() != 1
                    OR NEW.ticket_definition_hash IS NULL
                    OR NEW.ticket_definition_hash = ''
                    OR NEW.entry_source NOT IN ('MODEL', 'MANUAL')
                    OR (
                        NEW.entry_source = 'MODEL' AND (
                            NEW.quote_evidence_hash IS NULL
                            OR NEW.quote_evidence_hash = ''
                            OR NEW.model_contract_signature
                                IS NOT '{model_signature_sql}'
                        )
                    )
                    OR (
                        NEW.entry_source = 'MANUAL'
                        AND NEW.model_contract_signature IS NOT NULL
                    )
                )
                BEGIN
                    SELECT RAISE(ABORT, 'v3 ticket integrity contract failed');
                END
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS challenge_ticket_v3_definition_immutable
                BEFORE UPDATE OF
                    analysis_date, analysis_timezone, created_at,
                    quote_verified_at, stake_cents, total_odds, played_odds,
                    joint_probability, expected_roi, legs_json, entry_source,
                    quote_evidence_json, quote_evidence_hash,
                    ticket_definition_hash, model_contract_signature,
                    definition_version
                ON challenge_tickets
                WHEN OLD.definition_version >= 3 AND (
                    NEW.analysis_date IS NOT OLD.analysis_date
                    OR NEW.analysis_timezone IS NOT OLD.analysis_timezone
                    OR NEW.created_at IS NOT OLD.created_at
                    OR NEW.quote_verified_at IS NOT OLD.quote_verified_at
                    OR NEW.stake_cents IS NOT OLD.stake_cents
                    OR NEW.total_odds IS NOT OLD.total_odds
                    OR NEW.played_odds IS NOT OLD.played_odds
                    OR NEW.joint_probability IS NOT OLD.joint_probability
                    OR NEW.expected_roi IS NOT OLD.expected_roi
                    OR NEW.legs_json IS NOT OLD.legs_json
                    OR NEW.entry_source IS NOT OLD.entry_source
                    OR NEW.quote_evidence_json IS NOT OLD.quote_evidence_json
                    OR NEW.quote_evidence_hash IS NOT OLD.quote_evidence_hash
                    OR NEW.ticket_definition_hash IS NOT OLD.ticket_definition_hash
                    OR NEW.model_contract_signature
                        IS NOT OLD.model_contract_signature
                    OR NEW.definition_version IS NOT OLD.definition_version
                )
                BEGIN
                    SELECT RAISE(ABORT, 'v3 ticket definition is immutable');
                END
                """
            )
            # Legacy rows stored ROI against the reference ticket even when the
            # user entered different played odds. Repair the derived value once.
            connection.execute(
                """
                UPDATE challenge_tickets
                SET expected_roi = joint_probability
                    * COALESCE(played_odds, total_odds) - 1.0
                WHERE entry_source = 'MODEL'
                  AND COALESCE(definition_version, 0) = 0
                """
            )
            # Unsigned pre-v3 rows remain available as historical records, but
            # must never claim current MODEL provenance.
            connection.execute(
                """
                UPDATE challenge_tickets
                SET entry_source='MANUAL', model_contract_signature=NULL
                WHERE COALESCE(definition_version, 0) < 3
                """
            )
            legacy_rows = connection.execute(
                """
                SELECT id, analysis_date, total_odds, played_odds,
                       joint_probability, expected_roi, legs_json,
                       quote_evidence_json, quote_evidence_hash,
                       ticket_definition_hash, definition_version
                FROM challenge_tickets
                WHERE COALESCE(definition_version, 0) < 3
                """
            ).fetchall()
            for legacy_row in legacy_rows:
                try:
                    legs = json.loads(legacy_row["legs_json"])
                    if not isinstance(legs, list):
                        continue
                    changed = False
                    for leg in legs:
                        if not isinstance(leg, dict):
                            continue
                        if "market_key" not in leg:
                            leg.update(_legacy_market_definition(leg))
                            leg["actual_leg_odds_verified"] = False
                            changed = True
                    evidence_json = legacy_row["quote_evidence_json"] or "[]"
                    evidence = json.loads(evidence_json)
                    if not isinstance(evidence, list):
                        evidence = []
                        evidence_json = "[]"
                        changed = True
                    canonical_legs = _canonical_json(legs)
                    canonical_evidence = _canonical_json(evidence)
                    definition_version = int(legacy_row["definition_version"] or 0)
                    played_total = float(
                        legacy_row["played_odds"] or legacy_row["total_odds"]
                    )
                    definition_hash = _definition_hash_payload(
                        analysis_date=str(legacy_row["analysis_date"]),
                        legs_json=canonical_legs,
                        quote_evidence_json=canonical_evidence,
                        reference_total_odds=float(legacy_row["total_odds"]),
                        played_total_odds=played_total,
                        joint_probability=float(legacy_row["joint_probability"]),
                        expected_roi=float(legacy_row["expected_roi"]),
                        definition_version=definition_version,
                    )
                    evidence_hash = (
                        _sha256_text(canonical_evidence) if evidence else None
                    )
                    if (
                        changed
                        or legacy_row["ticket_definition_hash"] is None
                        or legacy_row["quote_evidence_hash"] != evidence_hash
                    ):
                        connection.execute(
                            """
                            UPDATE challenge_tickets
                            SET legs_json=?, quote_evidence_json=?,
                                quote_evidence_hash=?, ticket_definition_hash=?
                            WHERE id=?
                            """,
                            (
                                canonical_legs,
                                canonical_evidence,
                                evidence_hash,
                                definition_hash,
                                int(legacy_row["id"]),
                            ),
                        )
                except (TypeError, ValueError, json.JSONDecodeError):
                    # Corrupt legacy evidence remains readable only through the
                    # fail-closed integrity check; never invent market semantics.
                    continue
            now = datetime.now(timezone.utc).isoformat()
            default_cents = _money_to_cents(100.0)
            target_cents = _money_to_cents(TARGET_BALANCE, allow_zero=False)
            connection.execute(
                """
                INSERT OR IGNORE INTO challenge_settings (
                    id, starting_balance_cents, current_balance_cents,
                    target_balance_cents, stake_fraction_bps,
                    stake_policy_version, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?)
                """,
                (
                    default_cents,
                    default_cents,
                    target_cents,
                    int(DEFAULT_CHALLENGE_STAKE_FRACTION * 10_000),
                    STAKE_POLICY_VERSION,
                    now,
                ),
            )
            transaction_count = connection.execute(
                "SELECT COUNT(*) FROM challenge_transactions"
            ).fetchone()[0]
            if transaction_count == 0:
                settings_row = connection.execute(
                    """
                    SELECT current_balance_cents
                    FROM challenge_settings WHERE id = 1
                    """
                ).fetchone()
                ticket_count = connection.execute(
                    "SELECT COUNT(*) FROM challenge_tickets"
                ).fetchone()[0]
                current_cents = int(settings_row["current_balance_cents"])
                if ticket_count:
                    kind = "MIGRATION_SNAPSHOT"
                    amount_cents = 0
                    note = "Legacy balance captured during ledger migration"
                else:
                    kind = "OPENING_BALANCE"
                    amount_cents = current_cents
                    note = "Challenge opening balance"
                connection.execute(
                    """
                    INSERT INTO challenge_transactions (
                        created_at, kind, amount_cents,
                        balance_after_cents, note
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (now, kind, amount_cents, current_cents, note),
                )
            self._migrate_financial_chain(connection)
            self._migrate_settlement_chain(connection)
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_challenge_transaction_hash
                ON challenge_transactions(record_hash)
                WHERE record_hash IS NOT NULL
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_challenge_settlement_hash
                ON challenge_settlement_events(record_hash)
                WHERE record_hash IS NOT NULL
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS challenge_transactions_no_update
                BEFORE UPDATE ON challenge_transactions
                BEGIN
                    SELECT RAISE(ABORT, 'challenge transactions are append-only');
                END
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS challenge_settlement_events_no_update
                BEFORE UPDATE ON challenge_settlement_events
                BEGIN
                    SELECT RAISE(ABORT, 'settlement events are append-only');
                END
                """
            )
            zero_hash_sql = FINANCIAL_ZERO_HASH.replace("'", "''")
            connection.execute(
                f"""
                CREATE TRIGGER challenge_transactions_v2_insert_contract
                BEFORE INSERT ON challenge_transactions
                WHEN challenge_write_authorized() != 1
                  OR NEW.chain_version != {FINANCIAL_CHAIN_VERSION}
                  OR NEW.previous_hash IS NULL
                  OR NEW.record_hash IS NULL
                  OR length(NEW.previous_hash) != 64
                  OR length(NEW.record_hash) != 64
                  OR NEW.previous_hash GLOB '*[^0-9a-f]*'
                  OR NEW.record_hash GLOB '*[^0-9a-f]*'
                  OR NEW.previous_hash IS NOT COALESCE(
                        (SELECT record_hash FROM challenge_transactions
                         ORDER BY id DESC LIMIT 1),
                        '{zero_hash_sql}'
                     )
                BEGIN
                    SELECT RAISE(ABORT, 'financial HMAC-chain contract failed');
                END
                """
            )
            connection.execute(
                "DROP TRIGGER IF EXISTS challenge_settlement_events_insert_authorized"
            )
            connection.execute(
                f"""
                CREATE TRIGGER challenge_settlement_events_insert_authorized
                BEFORE INSERT ON challenge_settlement_events
                WHEN challenge_write_authorized() != 1
                  OR NEW.chain_version != {SETTLEMENT_CHAIN_VERSION}
                  OR NEW.previous_hash IS NULL
                  OR NEW.record_hash IS NULL
                  OR length(NEW.previous_hash) != 64
                  OR length(NEW.record_hash) != 64
                  OR NEW.previous_hash GLOB '*[^0-9a-f]*'
                  OR NEW.record_hash GLOB '*[^0-9a-f]*'
                  OR NEW.previous_hash IS NOT COALESCE(
                        (SELECT record_hash FROM challenge_settlement_events
                         ORDER BY id DESC LIMIT 1),
                        '{SETTLEMENT_ZERO_HASH}'
                     )
                BEGIN
                    SELECT RAISE(ABORT, 'settlement HMAC-chain contract failed');
                END
                """
            )
            connection.execute(
                "DROP TRIGGER IF EXISTS challenge_ticket_settlement_update_authorized"
            )
            connection.execute(
                """
                CREATE TRIGGER challenge_ticket_settlement_update_authorized
                BEFORE UPDATE OF
                    settled_at, status, payout_cents, settlement_odds,
                    settlement_rule_version, settlement_note
                ON challenge_tickets
                WHEN OLD.definition_version >= 3
                 AND challenge_write_authorized() != 1
                BEGIN
                    SELECT RAISE(ABORT, 'unauthorized ticket settlement update');
                END
                """
            )
            connection.execute(
                "DROP TRIGGER IF EXISTS challenge_financial_anchor_immutable"
            )
            connection.execute(
                f"""
                CREATE TRIGGER challenge_financial_anchor_immutable
                BEFORE UPDATE OF financial_chain_version, financial_anchor_hash
                ON challenge_settings
                WHEN OLD.financial_chain_version = {FINANCIAL_CHAIN_VERSION} AND (
                    NEW.financial_chain_version IS NOT OLD.financial_chain_version
                    OR NEW.financial_anchor_hash IS NOT OLD.financial_anchor_hash
                )
                BEGIN
                    SELECT RAISE(ABORT, 'financial chain anchor is immutable');
                END
                """
            )
            connection.execute(
                "DROP TRIGGER IF EXISTS challenge_settlement_anchor_immutable"
            )
            connection.execute(
                f"""
                CREATE TRIGGER challenge_settlement_anchor_immutable
                BEFORE UPDATE OF settlement_chain_version, settlement_anchor_hash
                ON challenge_settings
                WHEN OLD.settlement_chain_version = {SETTLEMENT_CHAIN_VERSION}
                 AND NOT (
                    challenge_write_authorized() = 1
                    AND OLD.settlement_anchor_hash IS NULL
                    AND NEW.settlement_chain_version
                        IS OLD.settlement_chain_version
                    AND NEW.settlement_anchor_hash IS (
                        SELECT record_hash FROM challenge_settlement_events
                        ORDER BY id ASC LIMIT 1
                    )
                 )
                 AND (
                    NEW.settlement_chain_version
                        IS NOT OLD.settlement_chain_version
                    OR NEW.settlement_anchor_hash
                        IS NOT OLD.settlement_anchor_hash
                 )
                BEGIN
                    SELECT RAISE(ABORT, 'settlement chain anchor is immutable');
                END
                """
            )
            valid, bad_record = self._verify_financial_rows(
                connection,
                require_checkpoint=False,
            )
            if not valid:
                location = (
                    f" at record {bad_record}"
                    if bad_record is not None
                    else ""
                )
                raise RuntimeError(
                    "Challenge integrity migration precheck failed" + location
                )
            self._require_ticket_definitions(connection)
            checkpoint_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM challenge_integrity_checkpoint"
                ).fetchone()[0]
            )
            if checkpoint_count == 0:
                if checkpoint_preexisted:
                    raise RuntimeError(
                        "Challenge integrity checkpoint cannot be recreated"
                    )
            elif checkpoint_count != 1:
                raise RuntimeError("Challenge integrity checkpoint is ambiguous")
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS challenge_checkpoint_insert_authorized
                BEFORE INSERT ON challenge_integrity_checkpoint
                WHEN challenge_write_authorized() != 1
                BEGIN
                    SELECT RAISE(ABORT, 'unauthorized integrity checkpoint insert');
                END
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS challenge_checkpoint_update_authorized
                BEFORE UPDATE ON challenge_integrity_checkpoint
                WHEN challenge_write_authorized() != 1
                BEGIN
                    SELECT RAISE(ABORT, 'unauthorized integrity checkpoint update');
                END
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS challenge_checkpoint_no_delete
                BEFORE DELETE ON challenge_integrity_checkpoint
                BEGIN
                    SELECT RAISE(ABORT, 'integrity checkpoint cannot be deleted');
                END
                """
            )
            if checkpoint_count == 0:
                self._refresh_integrity_checkpoint(connection)
            self._require_financial_ledger(connection)
            connection.commit()

    def settings(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            self._require_ticket_definitions(connection)
            self._require_financial_ledger(connection)
            row = connection.execute(
                "SELECT * FROM challenge_settings WHERE id = 1"
            ).fetchone()
            external_funding_cents = connection.execute(
                """
                SELECT COALESCE(SUM(amount_cents), 0)
                FROM challenge_transactions
                WHERE kind IN (
                    'OPENING_BALANCE',
                    'BALANCE_ADJUSTMENT',
                    'CHALLENGE_RESET'
                )
                """
            ).fetchone()[0]
        if row is None:
            raise RuntimeError("Challenge settings are missing")
        return {
            "starting_balance": _cents_to_money(row["starting_balance_cents"]),
            "current_balance": _cents_to_money(row["current_balance_cents"]),
            "target_balance": _cents_to_money(row["target_balance_cents"]),
            "stake_fraction": (
                _bounded_stake_fraction_bps(row["stake_fraction_bps"])
                / 10_000.0
            ),
            "stake_policy_version": int(row["stake_policy_version"]),
            "financial_chain_version": int(row["financial_chain_version"]),
            "financial_anchor_hash": row["financial_anchor_hash"],
            "settlement_chain_version": int(row["settlement_chain_version"]),
            "settlement_anchor_hash": row["settlement_anchor_hash"],
            "net_external_funding": _cents_to_money(external_funding_cents),
            "updated_at": row["updated_at"],
        }

    def _record_transaction(
        self,
        connection: sqlite3.Connection,
        *,
        created_at: str,
        kind: str,
        amount_cents: int,
        balance_after_cents: int,
        ticket_id: int | None = None,
        note: str | None = None,
    ) -> None:
        normalized_kind = str(kind)
        if normalized_kind not in FINANCIAL_ALLOWED_KINDS:
            raise ValueError("Financial transaction kind is invalid")
        amount_cents = _sqlite_integer(amount_cents, "financial amount_cents")
        balance_after_cents = _sqlite_integer(
            balance_after_cents,
            "financial balance_after_cents",
        )
        ticket_id = (
            _sqlite_integer(ticket_id, "financial ticket_id")
            if ticket_id is not None
            else None
        )
        tail = connection.execute(
            """
            SELECT record_hash FROM challenge_transactions
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
        previous_hash = tail["record_hash"] if tail is not None else FINANCIAL_ZERO_HASH
        if not previous_hash:
            raise RuntimeError("Challenge financial hash chain has no valid tail")
        digest = _financial_record_mac(
            self._integrity_key,
            created_at=created_at,
            kind=normalized_kind,
            amount_cents=amount_cents,
            balance_after_cents=balance_after_cents,
            ticket_id=ticket_id,
            note=note,
            previous_hash=str(previous_hash),
        )
        connection.execute(
            """
            INSERT INTO challenge_transactions (
                created_at, kind, amount_cents, balance_after_cents,
                ticket_id, note, chain_version, previous_hash, record_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                normalized_kind,
                amount_cents,
                balance_after_cents,
                ticket_id,
                note,
                FINANCIAL_CHAIN_VERSION,
                str(previous_hash),
                digest,
            ),
        )

    def _record_settlement_event(
        self,
        connection: sqlite3.Connection,
        *,
        ticket_id: int,
        created_at: str,
        action: str,
        previous_status: str | None,
        new_status: str,
        previous_payout_cents: int,
        new_payout_cents: int,
        settlement_odds: float | None,
        source: str,
        reason: str,
        rule_version: int = SETTLEMENT_RULE_VERSION,
    ) -> None:
        normalized_reason = str(reason or "").strip()
        normalized_source = str(source or "").strip()
        if (
            not normalized_reason
            or normalized_source not in SETTLEMENT_ALLOWED_SOURCES
        ):
            raise ValueError("Settlement source and reason are required")
        ticket_id = _sqlite_integer(ticket_id, "settlement ticket_id")
        previous_payout_cents = _sqlite_integer(
            previous_payout_cents,
            "settlement previous_payout_cents",
        )
        new_payout_cents = _sqlite_integer(
            new_payout_cents,
            "settlement new_payout_cents",
        )
        rule_version = _sqlite_integer(rule_version, "settlement rule_version")
        tail = connection.execute(
            """
            SELECT record_hash FROM challenge_settlement_events
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
        previous_hash = (
            str(tail["record_hash"])
            if tail is not None
            else SETTLEMENT_ZERO_HASH
        )
        if not previous_hash:
            raise RuntimeError("Settlement HMAC chain has no valid tail")
        digest = _settlement_record_mac(
            self._integrity_key,
            ticket_id=ticket_id,
            created_at=created_at,
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            previous_payout_cents=previous_payout_cents,
            new_payout_cents=new_payout_cents,
            settlement_odds=settlement_odds,
            rule_version=rule_version,
            source=normalized_source,
            reason=normalized_reason,
            previous_hash=previous_hash,
        )
        connection.execute(
            """
            INSERT INTO challenge_settlement_events (
                ticket_id, created_at, action, previous_status, new_status,
                previous_payout_cents, new_payout_cents, settlement_odds,
                rule_version, source, reason,
                chain_version, previous_hash, record_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                created_at,
                action,
                previous_status,
                new_status,
                previous_payout_cents,
                new_payout_cents,
                settlement_odds,
                rule_version,
                normalized_source,
                normalized_reason,
                SETTLEMENT_CHAIN_VERSION,
                previous_hash,
                digest,
            ),
        )
        if tail is None:
            connection.execute(
                """
                UPDATE challenge_settings
                SET settlement_anchor_hash=? WHERE id=1
                """,
                (digest,),
            )

    def set_balance(self, balance: Any, *, reset_start: bool = False) -> dict[str, Any]:
        cents = _money_to_cents(balance)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_ticket_definitions(connection)
            self._require_financial_ledger(connection)
            pending = connection.execute(
                "SELECT COUNT(*) FROM challenge_tickets WHERE status = 'PENDING'"
            ).fetchone()[0]
            if pending:
                connection.rollback()
                raise ValueError("Open tickets must be settled before correcting the balance")
            current_row = connection.execute(
                """
                SELECT current_balance_cents
                FROM challenge_settings WHERE id = 1
                """
            ).fetchone()
            if current_row is None:
                connection.rollback()
                raise RuntimeError("Challenge settings are missing")
            previous_cents = int(current_row["current_balance_cents"])
            now = datetime.now(timezone.utc).isoformat()
            if reset_start:
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET starting_balance_cents = ?, current_balance_cents = ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (cents, cents, now),
                )
            else:
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET current_balance_cents = ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (cents, now),
                )
            self._record_transaction(
                connection,
                created_at=now,
                kind="CHALLENGE_RESET" if reset_start else "BALANCE_ADJUSTMENT",
                amount_cents=cents - previous_cents,
                balance_after_cents=cents,
                note=(
                    "Explicit challenge restart"
                    if reset_start
                    else "Manual balance correction"
                ),
            )
            self._refresh_integrity_checkpoint(connection)
            connection.commit()
        return self.settings()

    def set_stake_fraction(self, stake_fraction: Any) -> dict[str, Any]:
        if isinstance(stake_fraction, bool):
            raise ValueError("Stake fraction must be numeric")
        try:
            fraction = Decimal(str(stake_fraction))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("Stake fraction must be numeric") from exc
        if (
            not fraction.is_finite()
            or fraction < Decimal(str(MIN_CHALLENGE_STAKE_FRACTION))
            or fraction > Decimal(str(MAX_CHALLENGE_STAKE_FRACTION))
        ):
            raise ValueError("Stake fraction must be between 5% and 25%")
        basis_points = int(
            (fraction * Decimal("10000")).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_ticket_definitions(connection)
            self._require_financial_ledger(connection)
            connection.execute(
                """
                UPDATE challenge_settings
                SET stake_fraction_bps = ?, stake_policy_version = ?, updated_at = ?
                WHERE id = 1
                """,
                (basis_points, STAKE_POLICY_VERSION, now),
            )
            self._refresh_integrity_checkpoint(connection)
            connection.commit()
        return self.settings()

    @staticmethod
    def _ticket_legs(
        ticket: QuotedTicket,
        quote_observation_ids: list[int | None],
        played_leg_odds: list[float],
        quote_evidence_hashes: list[str],
    ) -> list[dict[str, Any]]:
        legs: list[dict[str, Any]] = []
        for index, leg in enumerate(ticket.legs):
            market_definition = _market_definition(leg.candidate)
            actual_odds = played_leg_odds[index]
            is_n1_observation = leg.quote_source == BOOKMAKER
            payload = {
                "candidate_id": leg.candidate.candidate_id,
                "fixture_id": leg.candidate.fixture_id,
                "kickoff": leg.candidate.kickoff,
                "match": f"{leg.candidate.home_team} vs {leg.candidate.away_team}",
                "market": leg.candidate.market,
                "selection": leg.candidate.selection,
                "model_probability": leg.candidate.probability,
                "conservative_probability": leg.candidate.conservative_probability,
                "evidence_score": leg.candidate.evidence_score,
                "odds": leg.odds,
                "expected_roi": leg.expected_roi,
                "played_odds": actual_odds,
                "played_expected_roi": (
                    leg.candidate.conservative_probability * actual_odds - 1.0
                ),
                "actual_leg_odds_verified": True,
                "quote_observation_id": quote_observation_ids[index],
                "quote_evidence_hash": quote_evidence_hashes[index],
                "quote_source": leg.quote_source,
                "quoted_at": leg.quoted_at,
                "fetched_at": leg.fetched_at,
                "bookmaker_count": 1 if is_n1_observation else leg.bookmaker_count,
                "reference_odds": leg.odds if is_n1_observation else leg.quote_low,
                "best_observed_odds": leg.odds if is_n1_observation else leg.quote_high,
            }
            payload.update(market_definition)
            legs.append(payload)
        return legs

    def _verified_reference_quote_evidence(
        self,
        ticket: QuotedTicket,
        evidence_by_candidate: dict[str, Any],
        *,
        now: datetime,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Validate and canonicalize the individual offers behind each leg."""
        records: list[dict[str, Any]] = []
        hashes: list[str] = []
        for leg in ticket.legs:
            candidate = leg.candidate
            raw = evidence_by_candidate.get(candidate.candidate_id)
            if leg.quote_source == BOOKMAKER:
                # The append-only PriceLedger provides the proof for N1 quotes;
                # its observation is copied into the evidence snapshot later.
                records.append({})
                hashes.append("")
                continue
            if not isinstance(raw, dict):
                raise ValueError("Individual reference quote evidence is required")
            if (
                str(raw.get("candidate_id") or "") != candidate.candidate_id
                or str(raw.get("market_key") or "") != candidate.market_key
                or raw.get("fixture_id") != candidate.fixture_id
                or str(raw.get("source") or "") != leg.quote_source
            ):
                raise ValueError("Reference quote evidence does not match the ticket leg")
            fetched_at = _utc_datetime(raw.get("fetched_at"), "evidence fetched_at")
            leg_fetched_at = _utc_datetime(leg.fetched_at, "ticket fetched_at")
            fetched_age = now - fetched_at
            if (
                fetched_age.total_seconds() < -60
                or fetched_age > REFERENCE_FETCH_MAX_AGE
            ):
                raise ValueError("Reference quote evidence is stale or from the future")
            points = raw.get("points")
            if not isinstance(points, list) or len(points) != leg.bookmaker_count:
                raise ValueError("Reference quote evidence has an invalid provider count")
            normalized_points: list[dict[str, Any]] = []
            provider_ids: set[str] = set()
            for point in points:
                if not isinstance(point, dict):
                    raise ValueError("Reference quote evidence contains an invalid offer")
                bookmaker = str(point.get("bookmaker") or "").strip()
                provider_id = str(point.get("bookmaker_id") or "").strip()
                if not bookmaker or not provider_id or provider_id in provider_ids:
                    raise ValueError("Every reference offer needs a unique provider ID")
                try:
                    odds = validate_decimal_odds(point.get("odds"))
                except BettingMathError as exc:
                    raise ValueError("Reference quote evidence contains invalid odds") from exc
                observed_at = _utc_datetime(
                    point.get("observed_at"), "evidence observed_at"
                )
                age = now - observed_at
                if age.total_seconds() < -60 or age > REFERENCE_QUOTE_MAX_AGE:
                    raise ValueError("A reference provider offer is stale or from the future")
                fetch_delta = fetched_at - observed_at
                if (
                    fetch_delta.total_seconds() < 0
                    or fetch_delta > REFERENCE_QUOTE_MAX_AGE
                ):
                    raise ValueError(
                        "A reference provider offer is inconsistent with its fetch time"
                    )
                provider_ids.add(provider_id)
                normalized_points.append(
                    {
                        "bookmaker": bookmaker,
                        "bookmaker_id": provider_id,
                        "odds": odds,
                        "observed_at": observed_at.isoformat(),
                    }
                )
            if fetched_at != leg_fetched_at:
                raise ValueError(
                    "Ticket quote summary does not match its raw evidence"
                )
            executable = raw.get("executable_quote")
            if not isinstance(executable, dict):
                raise ValueError("Reference quote evidence lacks an executable offer")
            executable_bookmaker = str(
                executable.get("bookmaker") or ""
            ).strip()
            executable_id = str(executable.get("bookmaker_id") or "").strip()
            try:
                executable_odds = validate_decimal_odds(executable.get("odds"))
            except BettingMathError as exc:
                raise ValueError("Executable reference odds are invalid") from exc
            executable_observed_at = _utc_datetime(
                executable.get("observed_at"),
                "executable observed_at",
            )
            matching_executable_points = [
                point
                for point in normalized_points
                if point["bookmaker"] == executable_bookmaker
                and point["bookmaker_id"] == executable_id
                and math.isclose(
                    float(point["odds"]), executable_odds, abs_tol=5e-7
                )
                and _utc_datetime(point["observed_at"], "point observed_at")
                == executable_observed_at
            ]
            if (
                not executable_bookmaker
                or not executable_id
                or len(matching_executable_points) != 1
                or not math.isclose(executable_odds, float(leg.odds), abs_tol=5e-7)
            ):
                raise ValueError("Ticket odds are not the evidenced executable offer")
            ordered_odds = sorted(float(point["odds"]) for point in normalized_points)
            q25_position = (len(ordered_odds) - 1) * 0.25
            q25_lower = math.floor(q25_position)
            q25_upper = math.ceil(q25_position)
            conservative_odds = (
                ordered_odds[q25_lower]
                if q25_lower == q25_upper
                else ordered_odds[q25_lower] * (q25_upper - q25_position)
                + ordered_odds[q25_upper] * (q25_position - q25_lower)
            )
            expected_executable = min(
                (
                    point
                    for point in normalized_points
                    if float(point["odds"]) + 1e-9 >= conservative_odds
                ),
                key=lambda point: (float(point["odds"]), point["bookmaker_id"]),
            )
            try:
                leg_quote_low = validate_decimal_odds(leg.quote_low)
                leg_quote_high = validate_decimal_odds(leg.quote_high)
                summary_checks = (
                    raw.get("bookmaker_count") == len(normalized_points),
                    leg.bookmaker_count == len(normalized_points),
                    math.isclose(
                        float(raw.get("lowest_odds")), ordered_odds[0], abs_tol=5e-6
                    ),
                    math.isclose(
                        float(raw.get("conservative_odds")),
                        conservative_odds,
                        abs_tol=5e-6,
                    ),
                    math.isclose(
                        float(raw.get("consensus_odds")),
                        float(median(ordered_odds)),
                        abs_tol=5e-6,
                    ),
                    math.isclose(
                        float(raw.get("best_odds")), ordered_odds[-1], abs_tol=5e-6
                    ),
                    math.isclose(
                        leg_quote_low,
                        executable_odds,
                        abs_tol=5e-7,
                    ),
                    math.isclose(
                        leg_quote_high,
                        ordered_odds[-1],
                        abs_tol=5e-7,
                    ),
                    math.isclose(
                        float(expected_executable["odds"]),
                        executable_odds,
                        abs_tol=5e-7,
                    ),
                    expected_executable["bookmaker_id"] == executable_id,
                    expected_executable["bookmaker"] == executable_bookmaker,
                    _utc_datetime(
                        expected_executable["observed_at"],
                        "expected executable observed_at",
                    )
                    == executable_observed_at,
                )
            except (BettingMathError, TypeError, ValueError) as exc:
                raise ValueError(
                    "Reference quote summary does not match its offers"
                ) from exc
            if not all(summary_checks):
                raise ValueError("Reference quote summary does not match its offers")
            aggregate_quote_time = _utc_datetime(
                raw.get("quoted_at"), "evidence quoted_at"
            )
            leg_quote_time = _utc_datetime(leg.quoted_at, "ticket quoted_at")
            if aggregate_quote_time != leg_quote_time:
                raise ValueError(
                    "Ticket quote summary does not match its raw evidence"
                )
            latest_point_time = max(
                _utc_datetime(point["observed_at"], "point observed_at")
                for point in normalized_points
            )
            if abs((aggregate_quote_time - latest_point_time).total_seconds()) > 1.0:
                raise ValueError("Reference quote aggregate clock is inconsistent")
            scheduled_start = _utc_datetime(
                raw.get("scheduled_start"), "evidence scheduled_start"
            )
            expected_start = _utc_datetime(candidate.kickoff, "kickoff")
            if scheduled_start != expected_start:
                raise ValueError("Reference quote kickoff does not match the ticket leg")
            record = {
                "candidate_id": candidate.candidate_id,
                "fixture_id": candidate.fixture_id,
                "market_key": candidate.market_key,
                "source": leg.quote_source,
                "provider_event_id": raw.get("provider_event_id"),
                "scheduled_start": scheduled_start.isoformat(),
                "quoted_at": aggregate_quote_time.isoformat(),
                "fetched_at": fetched_at.isoformat(),
                "executable_quote": {
                    "bookmaker": executable_bookmaker,
                    "bookmaker_id": executable_id,
                    "odds": executable_odds,
                    "observed_at": executable_observed_at.isoformat(),
                },
                "points": sorted(
                    normalized_points,
                    key=lambda point: (point["bookmaker_id"], point["odds"]),
                ),
            }
            canonical = _canonical_json(record)
            records.append(record)
            hashes.append(_sha256_text(canonical))
        return records, hashes

    def _verified_quote_observation_ids(
        self,
        ticket: QuotedTicket,
        *,
        quote_time: datetime,
        now: datetime,
        connection: sqlite3.Connection,
        ledger: PriceLedger | None,
    ) -> tuple[list[int | None], list[dict[str, Any]]]:
        has_n1_price = any(leg.quote_source == BOOKMAKER for leg in ticket.legs)
        if has_n1_price and ledger is None:
            raise ValueError("N1Bet price ledger is unavailable")
        if ledger is not None:
            chain_valid, bad_id = PriceLedger._verify_rows(connection)
            if not chain_valid:
                raise PriceLedgerIntegrityError(
                    f"price hash chain is invalid at observation {bad_id}"
                )
        observation_ids: list[int | None] = []
        new_observation_receipts: list[dict[str, Any]] = []
        for leg in ticket.legs:
            candidate = leg.candidate
            if leg.quote_source != BOOKMAKER:
                if (
                    leg.quote_source != REFERENCE_SOURCE
                    or leg.quote_observation_id is not None
                    or leg.bookmaker_count < MIN_REFERENCE_BOOKMAKERS
                    or leg.quoted_at is None
                    or leg.fetched_at is None
                    or leg.quote_low is None
                    or leg.quote_high is None
                    or leg.quote_low > leg.quote_high
                    or not math.isclose(
                        leg.odds,
                        leg.quote_low,
                        rel_tol=0.0,
                        abs_tol=5e-7,
                    )
                ):
                    raise ValueError("Ticket reference price evidence is invalid")
                reference_time = _utc_datetime(leg.quoted_at, "quoted_at")
                fetched_time = _utc_datetime(leg.fetched_at, "fetched_at")
                reference_age = now - reference_time
                fetch_age = now - fetched_time
                if (
                    reference_age.total_seconds() < -60
                    or reference_age > REFERENCE_QUOTE_MAX_AGE
                    or fetch_age.total_seconds() < -60
                    or fetch_age > REFERENCE_FETCH_MAX_AGE
                ):
                    raise ValueError("Ticket reference price is stale or from the future")
                observation_ids.append(None)
                continue
            if ledger is None:
                raise ValueError("N1Bet price ledger is unavailable")
            try:
                n1_summary_invalid = (
                    isinstance(leg.bookmaker_count, bool)
                    or not isinstance(leg.bookmaker_count, int)
                    or leg.bookmaker_count != 1
                    or (
                        leg.quote_low is not None
                        and not math.isclose(
                            validate_decimal_odds(leg.quote_low),
                            leg.odds,
                            rel_tol=0.0,
                            abs_tol=5e-7,
                        )
                    )
                    or (
                        leg.quote_high is not None
                        and not math.isclose(
                            validate_decimal_odds(leg.quote_high),
                            leg.odds,
                            rel_tol=0.0,
                            abs_tol=5e-7,
                        )
                    )
                    or (
                        leg.quoted_at is not None
                        and abs(
                            (
                                _utc_datetime(leg.quoted_at, "quoted_at")
                                - quote_time
                            ).total_seconds()
                        )
                        > 1.0
                    )
                    or (
                        leg.fetched_at is not None
                        and abs(
                            (
                                _utc_datetime(leg.fetched_at, "fetched_at")
                                - quote_time
                            ).total_seconds()
                        )
                        > 1.0
                    )
                )
            except (BettingMathError, TypeError, ValueError):
                n1_summary_invalid = True
            if n1_summary_invalid:
                raise ValueError("Ticket N1Bet quote summary is invalid")
            observation_id = leg.quote_observation_id
            if observation_id is None:
                spec = MARKET_BY_KEY.get(candidate.market_key)
                observation = ledger.append(
                    PriceQuote(
                        sport="FOOTBALL",
                        event_id=str(candidate.fixture_id),
                        event_name=(
                            f"{candidate.home_team} vs {candidate.away_team}"
                        ),
                        scheduled_start=candidate.kickoff,
                        market_key=candidate.market_key,
                        market_name=candidate.market,
                        selection_key=candidate.candidate_id,
                        selection_name=candidate.selection,
                        decimal_odds=leg.odds,
                        phase="ENTRY",
                        source="MANUAL",
                        captured_at=quote_time,
                        line=spec.threshold if spec is not None else None,
                        model_ref=CHALLENGE_MODEL_CONTRACT_SIGNATURE,
                        metadata={
                            "candidate_id": candidate.candidate_id,
                            "league_id": candidate.league_id,
                        },
                    ),
                    now=now,
                    connection=connection,
                )
                observation_id = observation.id
                new_observation_receipts.append(
                    ledger.append_receipt(observation_id)
                )
            observation_row = connection.execute(
                "SELECT * FROM price_observations WHERE id=?",
                (observation_id,),
            ).fetchone()
            if observation_row is None:
                raise ValueError("Ticket price observation does not exist")
            observation = PriceLedger._observation(observation_row)
            expected_start = _utc_datetime(candidate.kickoff, "kickoff")
            observed_start = _utc_datetime(
                observation.scheduled_start,
                "scheduled_start",
            )
            observed_capture = _utc_datetime(
                observation.captured_at,
                "captured_at",
            )
            if (
                observation.bookmaker != BOOKMAKER
                or observation.model_ref != CHALLENGE_MODEL_CONTRACT_SIGNATURE
                or observation.sport != "FOOTBALL"
                or observation.event_id != str(candidate.fixture_id)
                or observation.event_name
                != f"{candidate.home_team} vs {candidate.away_team}"
                or observation.market_key != candidate.market_key
                or observation.selection_key != candidate.candidate_id
                or observation.phase != "ENTRY"
                or not math.isclose(
                    observation.decimal_odds,
                    leg.odds,
                    rel_tol=0.0,
                    abs_tol=5e-7,
                )
                or observed_start != expected_start
                or abs((observed_capture - quote_time).total_seconds()) > 1.0
            ):
                raise ValueError(
                    "Ticket price does not match its append-only N1Bet observation"
                )
            observation_ids.append(observation_id)
        return observation_ids, new_observation_receipts

    def place_ticket(
        self,
        analysis_date: str,
        ticket: QuotedTicket,
        stake: Any,
        quote_verified_at: str,
        *,
        played_odds: Any | None = None,
        played_leg_odds: Any | None = None,
        reference_quote_evidence: dict[str, Any] | None = None,
    ) -> int:
        # Authenticate the pre-call state before preparing evidence. Any new
        # price row is appended later on the same BEGIN IMMEDIATE connection as
        # ticket, stake movement and refreshed HMAC checkpoint.
        with closing(self._connect()) as precheck_connection:
            self._require_ticket_definitions(precheck_connection)
            self._require_financial_ledger(precheck_connection)
            precheck_settings = precheck_connection.execute(
                "SELECT current_balance_cents, stake_fraction_bps "
                "FROM challenge_settings WHERE id=1"
            ).fetchone()
            precheck_pending_count = _sqlite_integer(
                precheck_connection.execute(
                    "SELECT COUNT(*) FROM challenge_tickets WHERE status='PENDING'"
                ).fetchone()[0],
                "precheck pending ticket count",
            )
            precheck_date_count = _sqlite_integer(
                precheck_connection.execute(
                    "SELECT COUNT(*) FROM challenge_tickets "
                    "WHERE analysis_date=? AND status!='VOID'",
                    (str(analysis_date),),
                ).fetchone()[0],
                "precheck analysis date ticket count",
            )
            if precheck_settings is None:
                raise RuntimeError("Challenge settings are missing")
            precheck_balance_cents = _sqlite_integer(
                precheck_settings["current_balance_cents"],
                "precheck current balance",
            )
            precheck_stake_fraction_bps = _bounded_stake_fraction_bps(
                precheck_settings["stake_fraction_bps"]
            )
        stake_cents = _money_to_cents(stake, allow_zero=False)
        if not ticket.legs or len(ticket.legs) > 3:
            raise ValueError("A challenge ticket must contain one to three legs")
        try:
            analysis_day = datetime.fromisoformat(str(analysis_date)).date()
        except (TypeError, ValueError) as exc:
            raise ValueError("analysis_date must be an ISO calendar date") from exc
        if str(analysis_day) != str(analysis_date):
            raise ValueError("analysis_date must be an ISO calendar date")

        now_dt = datetime.now(timezone.utc)
        quote_time = _utc_datetime(quote_verified_at, "quote_verified_at")
        quote_age = (now_dt - quote_time).total_seconds()
        quote_age_limit = (
            int(REFERENCE_FETCH_MAX_AGE.total_seconds())
            if any(leg.quote_source == REFERENCE_SOURCE for leg in ticket.legs)
            else MAX_QUOTE_AGE_SECONDS
        )
        if quote_age < -60 or quote_age > quote_age_limit:
            raise ValueError("The verified quote is stale or from the future")
        if any(not candidate_is_credible(leg.candidate) for leg in ticket.legs):
            raise ValueError("Ticket contains an unverified candidate")
        for leg in ticket.legs:
            _market_definition(leg.candidate)

        try:
            leg_odds = [validate_decimal_odds(leg.odds) for leg in ticket.legs]
        except BettingMathError as exc:
            raise ValueError("Ticket contains invalid decimal odds") from exc
        derived_total_odds = math.prod(leg_odds)
        dependency_factor = ticket_dependency_factor(
            leg.candidate for leg in ticket.legs
        )
        derived_joint_probability = (
            math.prod(leg.candidate.conservative_probability for leg in ticket.legs)
            * dependency_factor
        )
        derived_dependence_floor = dependence_floor_probability(
            leg.candidate for leg in ticket.legs
        )
        derived_stress_probability = (
            derived_dependence_floor
            if len(ticket.legs) > 1
            else derived_joint_probability
        )
        derived_expected_roi = derived_joint_probability * derived_total_odds - 1.0
        derived_stress_roi = (
            derived_stress_probability * derived_total_odds - 1.0
        )
        derived_leg_rois = [
            leg.candidate.conservative_probability * odds - 1.0
            for leg, odds in zip(ticket.legs, leg_odds)
        ]
        if any(value < MIN_LEG_EXPECTED_ROI for value in derived_leg_rois):
            raise ValueError("Every ticket leg must clear the value gate")
        try:
            leg_roi_consistent = all(
                math.isclose(float(leg.expected_roi), value, abs_tol=5e-7)
                for leg, value in zip(ticket.legs, derived_leg_rois)
            )
        except (TypeError, ValueError):
            leg_roi_consistent = False
        if not leg_roi_consistent:
            raise ValueError("Ticket leg ROI does not match its probability and odds")
        try:
            derived_metrics = evaluate_market_price(
                derived_stress_probability * 100.0,
                derived_total_odds,
                probability_haircut=0.0,
                kelly_fraction=0.25,
                kelly_cap=KELLY_REFERENCE_CAP,
            )
        except BettingMathError as exc:
            raise ValueError("Ticket mathematics are invalid") from exc
        try:
            ticket_fields = (
                ticket.total_odds,
                ticket.joint_probability,
                ticket.expected_roi,
                ticket.model_dependency_factor,
                ticket.dependence_floor_probability,
                ticket.stake_fraction,
            )
            if any(isinstance(value, bool) for value in ticket_fields):
                raise ValueError
            consistency_checks = (
                math.isclose(float(ticket.total_odds), derived_total_odds, abs_tol=5e-5),
                math.isclose(
                    float(ticket.joint_probability),
                    derived_joint_probability,
                    abs_tol=5e-7,
                ),
                math.isclose(
                    float(ticket.expected_roi),
                    derived_expected_roi,
                    abs_tol=5e-7,
                ),
                math.isclose(
                    float(ticket.model_dependency_factor),
                    dependency_factor,
                    abs_tol=5e-7,
                ),
                math.isclose(
                    float(ticket.dependence_floor_probability),
                    derived_dependence_floor,
                    abs_tol=5e-7,
                ),
                math.isclose(
                    float(ticket.stake_fraction),
                    derived_metrics.kelly_fraction,
                    abs_tol=5e-7,
                ),
            )
        except (TypeError, ValueError, OverflowError):
            consistency_checks = (False,)
        if not all(consistency_checks):
            raise ValueError("Ticket fields do not match the underlying legs")
        if not TARGET_ODDS_MIN <= derived_total_odds <= TARGET_ODDS_MAX:
            raise ValueError("Ticket odds are outside the challenge corridor")
        if derived_expected_roi < MIN_LEG_EXPECTED_ROI:
            raise ValueError("Ticket expected ROI is below the challenge gate")
        if derived_stress_roi < MIN_LEG_EXPECTED_ROI:
            raise ValueError("Ticket Fréchet stress ROI is below the challenge gate")

        if played_leg_odds is None:
            actual_leg_odds = list(leg_odds)
        elif (
            not isinstance(played_leg_odds, (list, tuple))
            or len(played_leg_odds) != len(ticket.legs)
        ):
            raise ValueError("Every ticket leg needs its actual played odds")
        else:
            try:
                actual_leg_odds = [
                    validate_decimal_odds(value) for value in played_leg_odds
                ]
            except BettingMathError as exc:
                raise ValueError("A played leg contains invalid decimal odds") from exc
        actual_total_odds = math.prod(actual_leg_odds)
        if played_odds is not None:
            try:
                submitted_total_odds = validate_decimal_odds(played_odds)
            except BettingMathError as exc:
                raise ValueError("The played ticket odds are invalid") from exc
            if not math.isclose(
                submitted_total_odds,
                actual_total_odds,
                rel_tol=0.0,
                abs_tol=5e-5,
            ):
                raise ValueError(
                    "The played total odds must equal the product of the played leg odds"
                )
        actual_leg_rois = [
            leg.candidate.conservative_probability * odds - 1.0
            for leg, odds in zip(ticket.legs, actual_leg_odds)
        ]
        if any(value < MIN_LEG_EXPECTED_ROI for value in actual_leg_rois):
            raise ValueError("Every played ticket leg must clear the value gate")
        # Persist the ROI against the exact probability and odds that are also
        # persisted, not the higher precision pre-rounding intermediate.
        actual_expected_roi = float(ticket.joint_probability) * actual_total_odds - 1.0
        actual_stress_roi = (
            derived_stress_probability * actual_total_odds - 1.0
        )
        if not TARGET_ODDS_MIN <= actual_total_odds <= TARGET_ODDS_MAX:
            raise ValueError("The played ticket odds are outside the challenge corridor")
        if actual_expected_roi < MIN_LEG_EXPECTED_ROI:
            raise ValueError("The played ticket odds do not clear the value gate")
        if actual_stress_roi < MIN_LEG_EXPECTED_ROI:
            raise ValueError(
                "The played ticket odds do not clear the Fréchet stress gate"
            )

        fixture_ids = [leg.candidate.fixture_id for leg in ticket.legs]
        if len(set(fixture_ids)) != len(fixture_ids):
            raise ValueError("Ticket legs must use different fixtures")
        team_ids = [
            team_id
            for leg in ticket.legs
            for team_id in (
                leg.candidate.home_team_id,
                leg.candidate.away_team_id,
            )
        ]
        if len(set(team_ids)) != len(team_ids):
            raise ValueError("Ticket legs must not reuse a team")
        if any(
            _utc_datetime(leg.candidate.kickoff, "kickoff") <= now_dt
            for leg in ticket.legs
        ):
            raise ValueError("Every ticket leg must still be pre-match")

        # Do every deterministic account/risk rejection before the atomic write.
        # The same gates remain inside BEGIN IMMEDIATE to close concurrency races.
        if precheck_pending_count:
            raise ValueError(
                "An open ticket must be settled before a new ticket can be placed"
            )
        if precheck_date_count:
            raise ValueError("For this date, a challenge ticket already exists")
        if stake_cents > precheck_balance_cents:
            raise ValueError("Stake exceeds the available balance")
        if (
            stake_cents
            > precheck_balance_cents * precheck_stake_fraction_bps // 10_000
        ):
            raise ValueError("Stake exceeds the configured challenge limit")
        if stake_cents > _money_to_cents(
            risk_managed_ticket_stake(
                ticket,
                _cents_to_money(precheck_balance_cents),
                decimal_odds=actual_total_odds,
            )
        ):
            raise ValueError("Stake exceeds the risk-managed ticket limit")
        precheck_fraction = (
            stake_cents / precheck_balance_cents
            if precheck_balance_cents
            else 1.0
        )
        if not ticket_stake_passes_log_growth_gate(
            ticket,
            precheck_fraction,
            decimal_odds=actual_total_odds,
        ):
            raise ValueError("Stake does not pass the positive log-growth gate")

        try:
            reference_records, quote_evidence_hashes = (
                self._verified_reference_quote_evidence(
                    ticket,
                    reference_quote_evidence or {},
                    now=now_dt,
                )
            )
            price_ledger = (
                PriceLedger(self.db_path)
                if any(leg.quote_source == BOOKMAKER for leg in ticket.legs)
                else None
            )
        except (PriceLedgerError, PriceLedgerIntegrityError) as exc:
            raise ValueError(str(exc)) from exc
        created_at = now_dt.isoformat()
        normalized_quote_verified_at = quote_time.isoformat()
        now = created_at

        authenticated_price_baseline = self._last_authenticated_price_state
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                checkpoint_valid, _ = self._verify_integrity_checkpoint(connection)
                if not checkpoint_valid:
                    raise RuntimeError(
                        "Challenge financial ledger integrity checkpoint precheck failed"
                    )
                self._require_ticket_definitions(connection)
                self._require_financial_ledger(connection)
                pending_count = connection.execute(
                    "SELECT COUNT(*) FROM challenge_tickets WHERE status = 'PENDING'"
                ).fetchone()[0]
                if pending_count:
                    # Challenge sizing assumes sequential roll-over tickets;
                    # concurrent tickets would silently stack bankroll exposure.
                    raise ValueError(
                        "An open ticket must be settled before a new ticket can be placed"
                    )
                date_count = connection.execute(
                    "SELECT COUNT(*) FROM challenge_tickets "
                    "WHERE analysis_date=? AND status!='VOID'",
                    (str(analysis_date),),
                ).fetchone()[0]
                if date_count:
                    raise ValueError("For this date, a challenge ticket already exists")
                row = connection.execute(
                    """
                    SELECT current_balance_cents, stake_fraction_bps
                    FROM challenge_settings WHERE id = 1
                    """
                ).fetchone()
                if row is None or stake_cents > row[0]:
                    raise ValueError("Stake exceeds the available balance")
                max_stake_cents = (
                    int(row[0])
                    * _bounded_stake_fraction_bps(row[1])
                    // 10_000
                )
                if stake_cents > max_stake_cents:
                    raise ValueError("Stake exceeds the configured challenge limit")
                risk_cap_cents = _money_to_cents(
                    risk_managed_ticket_stake(
                        ticket,
                        _cents_to_money(int(row[0])),
                        decimal_odds=actual_total_odds,
                    )
                )
                if stake_cents > risk_cap_cents:
                    raise ValueError("Stake exceeds the risk-managed ticket limit")
                actual_fraction = stake_cents / int(row[0]) if int(row[0]) else 1.0
                if not ticket_stake_passes_log_growth_gate(
                    ticket,
                    actual_fraction,
                    decimal_odds=actual_total_odds,
                ):
                    raise ValueError("Stake does not pass the positive log-growth gate")
                try:
                    (
                        quote_observation_ids,
                        new_quote_observation_receipts,
                    ) = self._verified_quote_observation_ids(
                        ticket,
                        quote_time=quote_time,
                        now=now_dt,
                        connection=connection,
                        ledger=price_ledger,
                    )
                except (PriceLedgerError, PriceLedgerIntegrityError) as exc:
                    raise ValueError(str(exc)) from exc
                self._reconcile_authenticated_price_appends(
                    connection,
                    new_quote_observation_receipts,
                )
                for index, observation_id in enumerate(quote_observation_ids):
                    if observation_id is None:
                        continue
                    observation_row = connection.execute(
                        "SELECT * FROM price_observations WHERE id=?",
                        (observation_id,),
                    ).fetchone()
                    if observation_row is None:
                        raise ValueError("Ticket price observation does not exist")
                    observation = PriceLedger._observation(observation_row)
                    record = {
                        "candidate_id": ticket.legs[index].candidate.candidate_id,
                        "fixture_id": ticket.legs[index].candidate.fixture_id,
                        "market_key": ticket.legs[index].candidate.market_key,
                        "source": BOOKMAKER,
                        "price_observation_id": observation_id,
                        "price_hash": observation.record_hash,
                        "model_contract_signature": observation.model_ref,
                        "bookmaker": observation.bookmaker,
                        "odds": observation.decimal_odds,
                        "observed_at": observation.captured_at,
                    }
                    reference_records[index] = record
                    quote_evidence_hashes[index] = _sha256_text(
                        _canonical_json(record)
                    )
                legs_json = json.dumps(
                    self._ticket_legs(
                        ticket,
                        quote_observation_ids,
                        actual_leg_odds,
                        quote_evidence_hashes,
                    ),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                quote_evidence_json = _canonical_json(reference_records)
                quote_evidence_hash = _sha256_text(quote_evidence_json)
                definition_hash = _definition_hash_payload(
                    analysis_date=analysis_date,
                    legs_json=legs_json,
                    quote_evidence_json=quote_evidence_json,
                    reference_total_odds=float(ticket.total_odds),
                    played_total_odds=actual_total_odds,
                    joint_probability=float(ticket.joint_probability),
                    expected_roi=actual_expected_roi,
                    definition_version=TICKET_DEFINITION_VERSION,
                    stake_cents=stake_cents,
                    created_at=created_at,
                    quote_verified_at=normalized_quote_verified_at,
                    analysis_timezone=CHALLENGE_TIMEZONE_NAME,
                    entry_source="MODEL",
                    model_contract_signature=CHALLENGE_MODEL_CONTRACT_SIGNATURE,
                )
                cursor = connection.execute(
                    """
                    INSERT INTO challenge_tickets (
                        analysis_date, analysis_timezone, created_at,
                        quote_verified_at, status, stake_cents, total_odds,
                        played_odds, joint_probability, expected_roi, legs_json,
                        entry_source, model_contract_signature,
                        settlement_rule_version, quote_evidence_json,
                        quote_evidence_hash, ticket_definition_hash,
                        definition_version
                    ) VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, 'MODEL',
                              ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis_date,
                        CHALLENGE_TIMEZONE_NAME,
                        now,
                        normalized_quote_verified_at,
                        stake_cents,
                        ticket.total_odds,
                        actual_total_odds,
                        ticket.joint_probability,
                        actual_expected_roi,
                        legs_json,
                        CHALLENGE_MODEL_CONTRACT_SIGNATURE,
                        SETTLEMENT_RULE_VERSION,
                        quote_evidence_json,
                        quote_evidence_hash,
                        definition_hash,
                        TICKET_DEFINITION_VERSION,
                    ),
                )
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET current_balance_cents = current_balance_cents - ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (stake_cents, now),
                )
                balance_after_cents = int(row[0]) - stake_cents
                self._record_transaction(
                    connection,
                    created_at=now,
                    kind="STAKE",
                    amount_cents=-stake_cents,
                    balance_after_cents=balance_after_cents,
                    ticket_id=int(cursor.lastrowid),
                    note=f"Ticket #{int(cursor.lastrowid)} placed",
                )
                self._refresh_integrity_checkpoint(connection)
                connection.commit()
                return int(cursor.lastrowid)
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                self._last_authenticated_price_state = authenticated_price_baseline
                raise ValueError("For this date, a challenge ticket already exists") from exc
            except Exception:
                connection.rollback()
                self._last_authenticated_price_state = authenticated_price_baseline
                raise

    def record_manual_result(
        self,
        analysis_date: str,
        description: str,
        stake: Any,
        total_odds: Any,
        status: str,
        *,
        actual_payout: Any | None = None,
        reason: str = "User-confirmed historical ticket",
    ) -> int:
        """Record a real past bet that was not saved before kickoff."""
        stake_cents = _money_to_cents(stake, allow_zero=False)
        normalized = str(status).upper()
        if normalized not in {"WON", "LOST", "VOID"}:
            raise ValueError("Settlement status must be WON, LOST, or VOID")
        label = str(description or "").strip()
        if not label or len(label) > 300:
            raise ValueError("Description must contain 1 to 300 characters")
        try:
            analysis_day = datetime.fromisoformat(str(analysis_date)).date()
        except (TypeError, ValueError) as exc:
            raise ValueError("analysis_date must be an ISO calendar date") from exc
        if str(analysis_day) != str(analysis_date):
            raise ValueError("analysis_date must be an ISO calendar date")
        if analysis_day > datetime.now(CHALLENGE_TIMEZONE).date():
            raise ValueError("A settled ticket cannot be recorded for a future date")
        try:
            actual_total_odds = validate_decimal_odds(total_odds)
        except BettingMathError as exc:
            raise ValueError("The played ticket odds are invalid") from exc

        if actual_payout is not None:
            payout_cents = _money_to_cents(actual_payout)
        elif normalized == "WON":
            payout_cents = int(
                (Decimal(stake_cents) * Decimal(str(actual_total_odds))).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
        elif normalized == "VOID":
            payout_cents = stake_cents
        else:
            payout_cents = 0
        if normalized == "LOST" and payout_cents != 0:
            raise ValueError("A lost ticket cannot have a payout")
        if normalized == "VOID" and payout_cents != stake_cents:
            raise ValueError("A void ticket must refund the exact stake")
        if normalized == "WON":
            expected_payout_cents = int(
                (Decimal(stake_cents) * Decimal(str(actual_total_odds))).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            if abs(payout_cents - expected_payout_cents) > 1:
                raise ValueError("Actual payout and played odds do not reconcile")

        now = datetime.now(timezone.utc).isoformat()
        legs_json = _canonical_json(
            [
                {
                    "manual": True,
                    "label": label,
                    "market_key": "MANUAL",
                    "market_kind": "manual",
                    "market_side": None,
                    "market_threshold": None,
                    "market_low": None,
                    "market_high": None,
                    "played_odds": actual_total_odds,
                    "actual_leg_odds_verified": True,
                    "settlement_rule_version": SETTLEMENT_RULE_VERSION,
                }
            ]
        )
        quote_evidence_json = "[]"
        definition_hash = _definition_hash_payload(
            analysis_date=analysis_date,
            legs_json=legs_json,
            quote_evidence_json=quote_evidence_json,
            reference_total_odds=actual_total_odds,
            played_total_odds=actual_total_odds,
            joint_probability=0.0,
            expected_roi=0.0,
            definition_version=TICKET_DEFINITION_VERSION,
            stake_cents=stake_cents,
            created_at=now,
            quote_verified_at=now,
            analysis_timezone=CHALLENGE_TIMEZONE_NAME,
            entry_source="MANUAL",
            model_contract_signature=None,
        )
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._require_ticket_definitions(connection)
                self._require_financial_ledger(connection)
                pending_count = connection.execute(
                    "SELECT COUNT(*) FROM challenge_tickets WHERE status = 'PENDING'"
                ).fetchone()[0]
                if pending_count:
                    raise ValueError(
                        "An open ticket must be settled before a past ticket can be recorded"
                    )
                row = connection.execute(
                    """
                    SELECT current_balance_cents
                    FROM challenge_settings WHERE id = 1
                    """
                ).fetchone()
                if row is None or stake_cents > row["current_balance_cents"]:
                    raise ValueError("Stake exceeds the available balance")

                cursor = connection.execute(
                    """
                    INSERT INTO challenge_tickets (
                        analysis_date, analysis_timezone, created_at,
                        quote_verified_at, settled_at, status, stake_cents,
                        payout_cents, total_odds, played_odds, joint_probability,
                        expected_roi, legs_json, entry_source,
                        model_contract_signature, settlement_odds,
                        settlement_rule_version, settlement_note,
                        quote_evidence_json, quote_evidence_hash,
                        ticket_definition_hash, definition_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, 'MANUAL',
                              NULL, ?, ?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        analysis_date,
                        CHALLENGE_TIMEZONE_NAME,
                        now,
                        now,
                        now,
                        normalized,
                        stake_cents,
                        payout_cents,
                        actual_total_odds,
                        actual_total_odds,
                        legs_json,
                        actual_total_odds if normalized == "WON" else None,
                        SETTLEMENT_RULE_VERSION,
                        str(reason).strip(),
                        quote_evidence_json,
                        definition_hash,
                        TICKET_DEFINITION_VERSION,
                    ),
                )
                ticket_id = int(cursor.lastrowid)
                balance_after_stake = int(row["current_balance_cents"]) - stake_cents
                self._record_transaction(
                    connection,
                    created_at=now,
                    kind="STAKE",
                    amount_cents=-stake_cents,
                    balance_after_cents=balance_after_stake,
                    ticket_id=ticket_id,
                    note=f"Manual ticket #{ticket_id} recorded",
                )
                final_balance = balance_after_stake + payout_cents
                self._record_transaction(
                    connection,
                    created_at=now,
                    kind={
                        "WON": "PAYOUT",
                        "LOST": "LOSS_SETTLED",
                        "VOID": "VOID_REFUND",
                    }[normalized],
                    amount_cents=payout_cents,
                    balance_after_cents=final_balance,
                    ticket_id=ticket_id,
                    note=f"Manual ticket #{ticket_id} settled {normalized}",
                )
                self._record_settlement_event(
                    connection,
                    ticket_id=ticket_id,
                    created_at=now,
                    action="SETTLE",
                    previous_status=None,
                    new_status=normalized,
                    previous_payout_cents=0,
                    new_payout_cents=payout_cents,
                    settlement_odds=(
                        actual_total_odds if normalized == "WON" else None
                    ),
                    source="MANUAL_HISTORY",
                    reason=reason,
                )
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET current_balance_cents = ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (final_balance, now),
                )
                self._refresh_integrity_checkpoint(connection)
                connection.commit()
                return ticket_id
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError(
                    "For this date, a challenge ticket already exists"
                ) from exc
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _settlement_values(
        row: sqlite3.Row,
        status: str,
        *,
        settlement_odds: Any | None,
        actual_payout: Any | None,
    ) -> tuple[int, float | None]:
        stake_cents = int(row["stake_cents"])
        if status == "WON":
            try:
                effective_odds = validate_decimal_odds(
                    settlement_odds
                    if settlement_odds is not None
                    else row["played_odds"] or row["total_odds"]
                )
            except BettingMathError as exc:
                raise ValueError("The settlement odds are invalid") from exc
            calculated = int(
                (Decimal(stake_cents) * Decimal(str(effective_odds))).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            payout_cents = (
                calculated
                if actual_payout is None
                else _money_to_cents(actual_payout, allow_zero=False)
            )
            if abs(payout_cents - calculated) > 1:
                raise ValueError(
                    "Actual payout and reduced settlement odds do not reconcile"
                )
            return payout_cents, effective_odds
        if settlement_odds is not None:
            raise ValueError("Settlement odds are only valid for a won ticket")
        payout_cents = (
            (stake_cents if status == "VOID" else 0)
            if actual_payout is None
            else _money_to_cents(actual_payout)
        )
        if status == "VOID" and payout_cents != stake_cents:
            raise ValueError("A void ticket must refund the exact stake")
        if status == "LOST" and payout_cents != 0:
            raise ValueError("A lost ticket cannot have a payout")
        return payout_cents, None

    def settle_ticket(
        self,
        ticket_id: int,
        status: str,
        *,
        settlement_odds: Any | None = None,
        actual_payout: Any | None = None,
        source: str = "MANUAL_CONFIRMED",
        reason: str = "User-confirmed settlement",
    ) -> dict[str, Any]:
        ticket_id = _positive_integer(ticket_id, "ticket_id")
        normalized = str(status).upper()
        if normalized not in {"WON", "LOST", "VOID"}:
            raise ValueError("Settlement status must be WON, LOST, or VOID")
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_ticket_definitions(connection)
            self._require_financial_ledger(connection)
            row = connection.execute(
                """
                SELECT status, stake_cents, payout_cents, total_odds, played_odds
                FROM challenge_tickets WHERE id = ?
                """,
                (ticket_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ValueError("Ticket does not exist")
            if row["status"] != "PENDING":
                connection.rollback()
                raise ValueError("Ticket has already been settled")

            payout_cents, effective_odds = self._settlement_values(
                row,
                normalized,
                settlement_odds=settlement_odds,
                actual_payout=actual_payout,
            )
            settings_row = connection.execute(
                """
                SELECT current_balance_cents
                FROM challenge_settings WHERE id = 1
                """
            ).fetchone()
            if settings_row is None:
                connection.rollback()
                raise RuntimeError("Challenge settings are missing")
            connection.execute(
                """
                UPDATE challenge_tickets
                SET status = ?, payout_cents = ?, settled_at = ?,
                    settlement_odds = ?, settlement_rule_version = ?,
                    settlement_note = ?
                WHERE id = ?
                """,
                (
                    normalized,
                    payout_cents,
                    now,
                    effective_odds,
                    SETTLEMENT_RULE_VERSION,
                    str(reason).strip(),
                    ticket_id,
                ),
            )
            connection.execute(
                """
                UPDATE challenge_settings
                SET current_balance_cents = current_balance_cents + ?, updated_at = ?
                WHERE id = 1
                """,
                (payout_cents, now),
            )
            balance_after_cents = (
                int(settings_row["current_balance_cents"]) + payout_cents
            )
            transaction_kind = {
                "WON": "PAYOUT",
                "LOST": "LOSS_SETTLED",
                "VOID": "VOID_REFUND",
            }[normalized]
            self._record_transaction(
                connection,
                created_at=now,
                kind=transaction_kind,
                amount_cents=payout_cents,
                balance_after_cents=balance_after_cents,
                ticket_id=ticket_id,
                note=f"Ticket #{ticket_id} settled {normalized}",
            )
            self._record_settlement_event(
                connection,
                ticket_id=ticket_id,
                created_at=now,
                action="SETTLE",
                previous_status="PENDING",
                new_status=normalized,
                previous_payout_cents=0,
                new_payout_cents=payout_cents,
                settlement_odds=effective_odds,
                source=source,
                reason=reason,
            )
            self._refresh_integrity_checkpoint(connection)
            connection.commit()
        return self.get_ticket(ticket_id)

    def correct_settlement(
        self,
        ticket_id: int,
        status: str,
        *,
        settlement_odds: Any | None = None,
        actual_payout: Any | None = None,
        reason: str,
    ) -> dict[str, Any]:
        """Append a balancing correction while preserving prior settlement history."""
        ticket_id = _positive_integer(ticket_id, "ticket_id")
        normalized = str(status).upper()
        if normalized not in {"WON", "LOST", "VOID"}:
            raise ValueError("Settlement status must be WON, LOST, or VOID")
        normalized_reason = str(reason or "").strip()
        if len(normalized_reason) < 5 or len(normalized_reason) > 500:
            raise ValueError("A correction reason of 5 to 500 characters is required")
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._require_ticket_definitions(connection)
                self._require_financial_ledger(connection)
                row = connection.execute(
                    """
                    SELECT status, stake_cents, payout_cents, total_odds, played_odds
                    FROM challenge_tickets WHERE id=?
                    """,
                    (ticket_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("Ticket does not exist")
                if row["status"] == "PENDING":
                    raise ValueError("A pending ticket must be settled, not corrected")
                new_payout_cents, effective_odds = self._settlement_values(
                    row,
                    normalized,
                    settlement_odds=settlement_odds,
                    actual_payout=actual_payout,
                )
                old_payout_cents = int(row["payout_cents"])
                delta = new_payout_cents - old_payout_cents
                settings_row = connection.execute(
                    "SELECT current_balance_cents FROM challenge_settings WHERE id=1"
                ).fetchone()
                if settings_row is None:
                    raise RuntimeError("Challenge settings are missing")
                corrected_balance = int(settings_row["current_balance_cents"]) + delta
                if corrected_balance < 0:
                    raise ValueError("The correction would make the balance negative")
                connection.execute(
                    """
                    UPDATE challenge_tickets
                    SET status=?, payout_cents=?, settled_at=?, settlement_odds=?,
                        settlement_rule_version=?, settlement_note=?
                    WHERE id=?
                    """,
                    (
                        normalized,
                        new_payout_cents,
                        now,
                        effective_odds,
                        SETTLEMENT_RULE_VERSION,
                        normalized_reason,
                        ticket_id,
                    ),
                )
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET current_balance_cents=?, updated_at=? WHERE id=1
                    """,
                    (corrected_balance, now),
                )
                self._record_transaction(
                    connection,
                    created_at=now,
                    kind="SETTLEMENT_CORRECTION",
                    amount_cents=delta,
                    balance_after_cents=corrected_balance,
                    ticket_id=ticket_id,
                    note=(
                        f"Ticket #{ticket_id} corrected {row['status']} -> {normalized}: "
                        f"{normalized_reason}"
                    ),
                )
                self._record_settlement_event(
                    connection,
                    ticket_id=ticket_id,
                    created_at=now,
                    action="CORRECT",
                    previous_status=str(row["status"]),
                    new_status=normalized,
                    previous_payout_cents=old_payout_cents,
                    new_payout_cents=new_payout_cents,
                    settlement_odds=effective_odds,
                    source="MANUAL_CORRECTION",
                    reason=normalized_reason,
                )
                self._refresh_integrity_checkpoint(connection)
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError("Settlement correction conflicts with the ledger") from exc
            except Exception:
                connection.rollback()
                raise
        return self.get_ticket(ticket_id)

    def reverse_settlement(self, ticket_id: int, *, reason: str) -> dict[str, Any]:
        """Re-open a settled ticket through an append-only payout reversal."""
        ticket_id = _positive_integer(ticket_id, "ticket_id")
        normalized_reason = str(reason or "").strip()
        if len(normalized_reason) < 5 or len(normalized_reason) > 500:
            raise ValueError("A reversal reason of 5 to 500 characters is required")
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._require_ticket_definitions(connection)
                self._require_financial_ledger(connection)
                row = connection.execute(
                    "SELECT status, payout_cents FROM challenge_tickets WHERE id=?",
                    (ticket_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("Ticket does not exist")
                if row["status"] == "PENDING":
                    raise ValueError("Ticket is already pending")
                other_pending = connection.execute(
                    """
                    SELECT COUNT(*) FROM challenge_tickets
                    WHERE status='PENDING' AND id != ?
                    """,
                    (ticket_id,),
                ).fetchone()[0]
                if other_pending:
                    raise ValueError("Another ticket is already pending")
                settings_row = connection.execute(
                    "SELECT current_balance_cents FROM challenge_settings WHERE id=1"
                ).fetchone()
                if settings_row is None:
                    raise RuntimeError("Challenge settings are missing")
                old_payout = int(row["payout_cents"])
                reversed_balance = int(settings_row["current_balance_cents"]) - old_payout
                if reversed_balance < 0:
                    raise ValueError("The reversal would make the balance negative")
                connection.execute(
                    """
                    UPDATE challenge_tickets
                    SET status='PENDING', payout_cents=0, settled_at=NULL,
                        settlement_odds=NULL, settlement_note=?
                    WHERE id=?
                    """,
                    (normalized_reason, ticket_id),
                )
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET current_balance_cents=?, updated_at=? WHERE id=1
                    """,
                    (reversed_balance, now),
                )
                self._record_transaction(
                    connection,
                    created_at=now,
                    kind="SETTLEMENT_REVERSAL",
                    amount_cents=-old_payout,
                    balance_after_cents=reversed_balance,
                    ticket_id=ticket_id,
                    note=f"Ticket #{ticket_id} settlement reversed: {normalized_reason}",
                )
                self._record_settlement_event(
                    connection,
                    ticket_id=ticket_id,
                    created_at=now,
                    action="REVERSE",
                    previous_status=str(row["status"]),
                    new_status="PENDING",
                    previous_payout_cents=old_payout,
                    new_payout_cents=0,
                    settlement_odds=None,
                    source="MANUAL_REVERSAL",
                    reason=normalized_reason,
                )
                self._refresh_integrity_checkpoint(connection)
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError("Settlement reversal conflicts with the ledger") from exc
            except Exception:
                connection.rollback()
                raise
        return self.get_ticket(ticket_id)

    @staticmethod
    def _row_to_ticket(row: sqlite3.Row) -> dict[str, Any]:
        if row["analysis_timezone"] != CHALLENGE_TIMEZONE_NAME:
            raise RuntimeError("Challenge ticket uses an unknown calendar timezone")
        reference_odds = float(row["total_odds"])
        played_odds = float(row["played_odds"] or reference_odds)
        try:
            legs = json.loads(row["legs_json"])
            quote_evidence = json.loads(row["quote_evidence_json"] or "[]")
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Challenge ticket JSON is corrupt") from exc
        if not isinstance(legs, list) or not isinstance(quote_evidence, list):
            raise RuntimeError("Challenge ticket evidence has an invalid shape")
        evidence_json = _canonical_json(quote_evidence)
        evidence_hash = row["quote_evidence_hash"]
        if evidence_hash and evidence_hash != _sha256_text(evidence_json):
            raise RuntimeError("Challenge quote evidence integrity check failed")
        definition_version = int(row["definition_version"] or 0)
        if definition_version > TICKET_DEFINITION_VERSION:
            raise RuntimeError("Challenge ticket uses an unsupported definition version")
        entry_source = str(row["entry_source"] or "")
        model_contract_signature = row["model_contract_signature"]
        if definition_version < 3 and entry_source != "MANUAL":
            raise RuntimeError("Legacy challenge tickets are manual-only")
        if definition_version >= 3:
            if not row["ticket_definition_hash"]:
                raise RuntimeError("Challenge ticket definition hash is required")
            try:
                _utc_datetime(row["created_at"], "created_at")
            except ValueError as exc:
                raise RuntimeError("Challenge ticket creation time is invalid") from exc
            if entry_source == "MODEL":
                if model_contract_signature != CHALLENGE_MODEL_CONTRACT_SIGNATURE:
                    raise RuntimeError("Challenge model contract signature is invalid")
                if (
                    not evidence_hash
                    or len(quote_evidence) != len(legs)
                    or not all(
                        isinstance(record, dict) and bool(record)
                        for record in quote_evidence
                    )
                ):
                    raise RuntimeError("Challenge model quote evidence is required")
            elif entry_source == "MANUAL":
                if model_contract_signature is not None:
                    raise RuntimeError("Manual ticket must not claim a model contract")
            else:
                raise RuntimeError("Challenge ticket entry source is invalid")
        expected_definition_hash = _definition_hash_payload(
            analysis_date=str(row["analysis_date"]),
            legs_json=_canonical_json(legs),
            quote_evidence_json=evidence_json,
            reference_total_odds=reference_odds,
            played_total_odds=played_odds,
            joint_probability=float(row["joint_probability"]),
            expected_roi=float(row["expected_roi"]),
            definition_version=definition_version,
            stake_cents=int(row["stake_cents"]),
            created_at=str(row["created_at"]),
            quote_verified_at=str(row["quote_verified_at"]),
            analysis_timezone=str(row["analysis_timezone"]),
            entry_source=entry_source,
            model_contract_signature=model_contract_signature,
        )
        if row["ticket_definition_hash"] and (
            row["ticket_definition_hash"] != expected_definition_hash
        ):
            raise RuntimeError("Challenge ticket definition integrity check failed")
        if entry_source == "MODEL":
            derived_roi = float(row["joint_probability"]) * played_odds - 1.0
            if not math.isclose(
                float(row["expected_roi"]), derived_roi, abs_tol=5e-7
            ):
                raise RuntimeError("Stored challenge ROI does not match played odds")
        if definition_version >= TICKET_DEFINITION_VERSION:
            for leg in legs:
                if leg.get("manual"):
                    if (
                        leg.get("market_key") != "MANUAL"
                        or leg.get("market_kind") != "manual"
                        or leg.get("settlement_rule_version")
                        != SETTLEMENT_RULE_VERSION
                    ):
                        raise RuntimeError(
                            "Stored manual challenge definition is invalid"
                        )
                    continue
                spec = MARKET_BY_KEY.get(str(leg.get("market_key") or ""))
                if (
                    spec is None
                    or leg.get("market_kind") != spec.kind
                    or leg.get("market_side") != spec.side
                    or leg.get("market_threshold") != spec.threshold
                    or leg.get("market_low") != spec.low
                    or leg.get("market_high") != spec.high
                    or leg.get("settlement_rule_version")
                    != SETTLEMENT_RULE_VERSION
                ):
                    raise RuntimeError("Stored challenge market definition is invalid")
        return {
            "id": row["id"],
            "analysis_date": row["analysis_date"],
            "analysis_timezone": row["analysis_timezone"],
            "created_at": row["created_at"],
            "quote_verified_at": row["quote_verified_at"],
            "settled_at": row["settled_at"],
            "status": row["status"],
            "stake": _cents_to_money(row["stake_cents"]),
            "payout": _cents_to_money(row["payout_cents"]),
            "total_odds": played_odds,
            "reference_total_odds": reference_odds,
            "played_odds": played_odds,
            "joint_probability": float(row["joint_probability"]),
            "expected_roi": float(row["expected_roi"]),
            "legs": legs,
            "entry_source": entry_source,
            "model_contract_signature": model_contract_signature,
            "settlement_odds": (
                float(row["settlement_odds"])
                if row["settlement_odds"] is not None
                else None
            ),
            "settlement_rule_version": int(row["settlement_rule_version"]),
            "settlement_note": row["settlement_note"],
            "quote_evidence": quote_evidence,
            "quote_evidence_hash": evidence_hash,
            "ticket_definition_hash": row["ticket_definition_hash"],
            "definition_version": definition_version,
        }

    def get_ticket(self, ticket_id: int) -> dict[str, Any]:
        ticket_id = _positive_integer(ticket_id, "ticket_id")
        with closing(self._connect()) as connection:
            self._require_ticket_definitions(connection)
            self._require_financial_ledger(connection)
            row = connection.execute(
                "SELECT * FROM challenge_tickets WHERE id = ?", (ticket_id,)
            ).fetchone()
        if row is None:
            raise ValueError("Ticket does not exist")
        return self._row_to_ticket(row)

    def tickets(
        self,
        limit: int | None = None,
        *,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if limit is not None and (
            isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
        ):
            raise ValueError("limit must be a positive integer or None")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        with closing(self._connect()) as connection:
            self._require_ticket_definitions(connection)
            self._require_financial_ledger(connection)
            if limit is None:
                rows = connection.execute(
                    "SELECT * FROM challenge_tickets ORDER BY id DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM challenge_tickets
                    ORDER BY id DESC LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()
        return [self._row_to_ticket(row) for row in rows]

    def ticket_count(self) -> int:
        with closing(self._connect()) as connection:
            self._require_ticket_definitions(connection)
            self._require_financial_ledger(connection)
            return int(
                connection.execute("SELECT COUNT(*) FROM challenge_tickets").fetchone()[0]
            )

    def pending_tickets(self) -> list[dict[str, Any]]:
        return [ticket for ticket in self.tickets() if ticket["status"] == "PENDING"]

    def transactions(
        self,
        limit: int | None = None,
        *,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if limit is not None and (
            isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
        ):
            raise ValueError("limit must be a positive integer or None")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        with closing(self._connect()) as connection:
            self._require_ticket_definitions(connection)
            self._require_financial_ledger(connection)
            if limit is None:
                rows = connection.execute(
                    "SELECT * FROM challenge_transactions ORDER BY id ASC"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM challenge_transactions
                    ORDER BY id ASC LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()
        return [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "kind": row["kind"],
                "amount": _cents_to_money(row["amount_cents"]),
                "balance_after": _cents_to_money(row["balance_after_cents"]),
                "ticket_id": row["ticket_id"],
                "note": row["note"],
                "chain_version": int(row["chain_version"]),
                "previous_hash": row["previous_hash"],
                "record_hash": row["record_hash"],
            }
            for row in rows
        ]

    def transaction_count(self) -> int:
        with closing(self._connect()) as connection:
            self._require_ticket_definitions(connection)
            self._require_financial_ledger(connection)
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM challenge_transactions"
                ).fetchone()[0]
            )

    def settlement_events(
        self,
        ticket_id: int | None = None,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if ticket_id is not None:
            ticket_id = _positive_integer(ticket_id, "ticket_id")
        if limit is not None and (
            isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
        ):
            raise ValueError("limit must be a positive integer or None")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        where = "WHERE ticket_id=?" if ticket_id is not None else ""
        parameters: list[Any] = [ticket_id] if ticket_id is not None else []
        suffix = ""
        if limit is not None:
            suffix = " LIMIT ? OFFSET ?"
            parameters.extend((limit, offset))
        with closing(self._connect()) as connection:
            self._require_ticket_definitions(connection)
            self._require_financial_ledger(connection)
            rows = connection.execute(
                f"""
                SELECT * FROM challenge_settlement_events
                {where} ORDER BY id ASC{suffix}
                """,
                parameters,
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "ticket_id": int(row["ticket_id"]),
                "created_at": row["created_at"],
                "action": row["action"],
                "previous_status": row["previous_status"],
                "new_status": row["new_status"],
                "previous_payout": _cents_to_money(row["previous_payout_cents"]),
                "new_payout": _cents_to_money(row["new_payout_cents"]),
                "settlement_odds": row["settlement_odds"],
                "rule_version": int(row["rule_version"]),
                "source": row["source"],
                "reason": row["reason"],
                "chain_version": int(row["chain_version"]),
                "previous_hash": row["previous_hash"],
                "record_hash": row["record_hash"],
            }
            for row in rows
        ]


__all__ = [
    "ChallengeLedger",
    "DEFAULT_CHALLENGE_DB",
    "SETTLEMENT_RULE_VERSION",
    "STAKE_POLICY_VERSION",
    "TICKET_DEFINITION_VERSION",
]
