"""Small presentation-only PandaScore logo catalog; never stores image bytes.

The regular scanner supplies already received opponent metadata. Browser image
URLs use PandaScore's documented 200px thumbnail variant. This module performs
no network requests and cannot alter match, model or financial evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import stat
import threading
import unicodedata
from urllib.parse import urlsplit

from runtime_paths import RUNTIME_STATE_DIR, _assert_no_symlink_components, atomic_write_text


CATALOG_PATH = RUNTIME_STATE_DIR / "participant-logos.json"
MAX_ENTRIES = 256
MAX_BYTES = 128 * 1024
_SCHEMA = "participant-logos-v1"
_LOCK = threading.RLock()
_IMAGE_PATH = re.compile(
    r"/images/team/image/([1-9][0-9]{0,18})/([A-Za-z0-9_.-]{1,180}\.(?:png|jpg|jpeg|webp))\Z"
)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate catalog key")
        value[key] = item
    return value


def _identity(team_id: object, name: object) -> tuple[int, str] | None:
    if isinstance(team_id, str) and re.fullmatch(r"[1-9][0-9]{0,18}", team_id):
        team_id = int(team_id)
    if type(team_id) is not int or not 0 < team_id <= 2**63 - 1:
        return None
    if not isinstance(name, str):
        return None
    name = name.strip()
    if not name or len(name) > 160 or any(unicodedata.category(c).startswith("C") for c in name):
        return None
    return team_id, name


def _thumbnail_url(team_id: int, value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 512 or any(
        c.isspace() or unicodedata.category(c).startswith("C") for c in value
    ):
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme != "https" or parts.netloc != "cdn.pandascore.co" or parts.query or parts.fragment:
        return None
    match = _IMAGE_PATH.fullmatch(parts.path)
    if not match or int(match[1]) != team_id or ".." in match[2]:
        return None
    filename = match[2]
    if filename.startswith("normal_"):
        return None
    if not filename.startswith("thumb_"):
        filename = "thumb_" + filename
    return f"https://cdn.pandascore.co/images/team/image/{team_id}/{filename}"


def _read(path: Path) -> dict[int, dict] | None:
    """Bound reads and reject malformed whole catalogs rather than partial trust."""
    try:
        safe_path = _assert_no_symlink_components(path)
        metadata = safe_path.stat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_BYTES:
            return None
        with safe_path.open("rb") as handle:
            payload = handle.read(MAX_BYTES + 1)
    except FileNotFoundError:
        return {}
    except (OSError, RuntimeError, ValueError):
        return None
    if len(payload) > MAX_BYTES:
        return None
    try:
        data = json.loads(payload, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError):
        return None
    if not isinstance(data, dict) or set(data) != {"schema", "source", "teams"}:
        return None
    if data["schema"] != _SCHEMA or data["source"] != "pandascore":
        return None
    if not isinstance(data["teams"], list) or len(data["teams"]) > MAX_ENTRIES:
        return None
    rows: dict[int, dict] = {}
    for row in data["teams"]:
        if not isinstance(row, dict) or set(row) != {"id", "name", "image_url"}:
            return None
        identity = _identity(row["id"], row["name"])
        if identity is None or type(row["id"]) is not int or identity[1] != row["name"]:
            return None
        image_url = _thumbnail_url(identity[0], row["image_url"])
        if image_url is None or image_url != row["image_url"] or identity[0] in rows:
            return None
        rows[identity[0]] = row
    return rows


def remember_pandascore_logos(opponents: object, *, path: Path | None = None) -> bool:
    """Publish one bounded metadata batch; optional failure never blocks a scan.

    Cross-process publication is atomic. A simultaneous scanner can replace
    another batch's coverage, but cannot corrupt the file or its identity rows.
    """
    if not isinstance(opponents, (list, tuple)) or len(opponents) > 1000:
        return False
    incoming: dict[int, dict] = {}
    ambiguous: set[int] = set()
    for opponent in opponents:
        if not isinstance(opponent, dict):
            continue
        identity = _identity(opponent.get("id"), opponent.get("name"))
        if identity is None:
            continue
        image_url = _thumbnail_url(identity[0], opponent.get("image_url"))
        if image_url is None:
            continue
        row = {"id": identity[0], "name": identity[1], "image_url": image_url}
        if identity[0] in incoming and incoming[identity[0]] != row:
            ambiguous.add(identity[0])
        incoming[identity[0]] = row
    for team_id in ambiguous:
        incoming.pop(team_id, None)
    if not incoming:
        return False
    target = CATALOG_PATH if path is None else Path(path)
    with _LOCK:
        rows = _read(target)
        if rows is None:
            return False
        before = dict(rows)
        for team_id, row in incoming.items():
            if rows.get(team_id) == row:
                continue
            rows.pop(team_id, None)
            rows[team_id] = row
        rows = dict(list(rows.items())[-MAX_ENTRIES:])
        if rows == before:
            return True
        while True:
            payload = json.dumps(
                {"schema": _SCHEMA, "source": "pandascore", "teams": list(rows.values())},
                ensure_ascii=False, separators=(",", ":"),
            )
            if len(payload.encode("utf-8")) <= MAX_BYTES:
                break
            rows.pop(next(iter(rows)))
        try:
            atomic_write_text(target, payload)
        except (OSError, RuntimeError, ValueError):
            return False
    return True


def resolve_pandascore_logo(team_id: object, name: object, *, path: Path | None = None) -> str | None:
    """Resolve only an exact native team ID and complete provider name."""
    identity = _identity(team_id, name)
    if identity is None:
        return None
    rows = _read(CATALOG_PATH if path is None else Path(path))
    if rows is None:
        return None
    row = rows.get(identity[0])
    return row["image_url"] if row is not None and row["name"] == identity[1] else None
