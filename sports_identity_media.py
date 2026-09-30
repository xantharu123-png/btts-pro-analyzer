"""Fail-closed public participant imagery, isolated from all sporting models.

Football crests use explicitly API-Football-native team IDs. Tennis portraits
come only from the reviewed Commons manifest; neither names nor provider IDs
are searched on the network. There is no disk cache or database access.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
import json
import math
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import unquote, urlsplit
import warnings

import requests
from PIL import Image


_MANIFEST_PATH = Path(__file__).resolve().parent / "assets" / "identity" / "tennis-portraits.json"
_MAX_BYTES = 1024 * 1024
_MAX_MANIFEST_BYTES = 256 * 1024
_MAX_DIMENSION = 4096
_MAX_PIXELS = 4_000_000
_CACHE_SECONDS = 24 * 60 * 60
_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
_COMMONS_HOSTS = frozenset({"upload.wikimedia.org", "thumb.wikimedia.org"})
_RASTER_FILE = re.compile(r".+\.(?:png|jpe?g|webp)$", re.IGNORECASE)


@dataclass(frozen=True)
class ParticipantImage:
    data_uri: str
    source_url: str | None = None
    credit: str | None = None
    crop: tuple[float, float, float] | None = None


@dataclass(frozen=True)
class _Portrait:
    names: tuple[str, ...]
    url: str
    source: str
    credit: str
    crop: tuple[float, float, float] | None = None


def _full_name(value: object) -> tuple[str, ...]:
    """Whole words only: never initials, substrings, phonetics or fuzzy names."""
    if not isinstance(value, str) or len(value) > 200:
        return ()
    folded = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    words = tuple(folded.split())
    if len(words) < 2 or any(sum(char.isalpha() for char in word) < 2 for word in words):
        return ()
    # Keep punctuation and whole words significant, but reject control text.
    if any(unicodedata.category(char).startswith("C") for char in folded):
        return ()
    return words


def _safe_url(url: object, *, source: bool = False) -> bool:
    if not isinstance(url, str) or not url or len(url) > 2048:
        return False
    if any(char.isspace() or ord(char) < 32 for char in url):
        return False
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
                or parsed.port is not None or parsed.query or parsed.fragment):
            return False
    except ValueError:
        return False
    if source:
        return parsed.netloc == "commons.wikimedia.org" and parsed.path.startswith("/wiki/File:")
    if parsed.netloc == "media.api-sports.io":
        return re.fullmatch(r"/football/teams/[1-9][0-9]*\.png", parsed.path) is not None
    if parsed.netloc not in _COMMONS_HOSTS:
        return False
    path = unquote(parsed.path)
    if any(part in {".", ".."} for part in path.split("/")) or "\\" in path:
        return False
    match = re.fullmatch(r"/wikipedia/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/(.+)", path)
    if match is None:
        return False
    tail = match.group(1).split("/")
    if "/thumb/" in path:
        return (len(tail) == 2 and _RASTER_FILE.fullmatch(tail[0]) is not None
                and re.fullmatch(r"[1-9][0-9]{0,3}px-.+\.(?:png|jpe?g|webp)", tail[1], re.IGNORECASE) is not None)
    return len(tail) == 1 and _RASTER_FILE.fullmatch(tail[0]) is not None


@lru_cache(maxsize=1)
def _read_manifest(path: str, modified_ns: int, bucket: int) -> tuple[_Portrait, ...]:
    """Only a fixed, reviewed local manifest can grant a portrait URL."""
    del modified_ns, bucket
    try:
        data = Path(path).read_bytes()
        if len(data) > _MAX_MANIFEST_BYTES:
            return ()
        manifest = json.loads(data)
        entries = manifest.get("entries") if isinstance(manifest, dict) else manifest
        if not isinstance(entries, list) or len(entries) > 128:
            return ()
        portraits = []
        for row in entries:
            if not isinstance(row, dict):
                return ()
            names = row.get("names")
            file_name = row.get("source_file", row.get("file"))
            url, source, credit = (row.get(key) for key in ("url", "source", "credit"))
            crop = row.get("crop")
            if crop is not None:
                if (not isinstance(crop, list) or len(crop) != 3
                        or any(type(value) not in {int, float} for value in crop)
                        or not (0 <= crop[0] <= 100 and 0 <= crop[1] <= 100 and 1 <= crop[2] <= 3)
                        or not all(math.isfinite(value) for value in crop)):
                    return ()
                crop = tuple(float(value) for value in crop)
            if (not isinstance(names, list) or not names or len(names) > 8
                    or any(not _full_name(name) for name in names)
                    or not isinstance(file_name, str) or _RASTER_FILE.fullmatch(file_name) is None
                    or not _safe_url(url) or urlsplit(url).netloc not in _COMMONS_HOSTS
                    or not _safe_url(source, source=True)
                    or not isinstance(credit, str) or not credit.strip() or len(credit) > 500
                    or any(ord(char) < 32 for char in credit)):
                return ()
            source_file = unquote(urlsplit(source).path[len("/wiki/File:"):]).replace("_", " ")
            if source_file != file_name.replace("_", " "):
                return ()
            image_path = unquote(urlsplit(url).path).split("/")
            image_file = image_path[-2] if "thumb" in image_path else image_path[-1]
            if image_file.replace("_", " ") != file_name.replace("_", " "):
                return ()
            portraits.append(_Portrait(tuple(names), url, source, credit.strip(), crop))
        return tuple(portraits)
    except (OSError, ValueError, TypeError, UnicodeError):
        return ()


def _portrait(name: object, bucket: int) -> _Portrait | None:
    wanted = _full_name(name)
    if not wanted:
        return None
    try:
        stat = _MANIFEST_PATH.stat()
        if stat.st_size > _MAX_MANIFEST_BYTES:
            return None
        portraits = _read_manifest(str(_MANIFEST_PATH), stat.st_mtime_ns, bucket)
    except OSError:
        return None
    # Sorting retains multiplicity: "Li Li Zhang" cannot match "Li Zhang".
    matches = [row for row in portraits
               if any(wanted == _full_name(alias) or sorted(wanted) == sorted(_full_name(alias))
                      for alias in row.names)]
    return matches[0] if len(matches) == 1 else None


def _magic_matches(data: bytes, mime: str) -> bool:
    if mime == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _verified_data_uri(data: bytes, mime: str) -> str | None:
    if not data or len(data) > _MAX_BYTES or mime not in _FORMATS or not _magic_matches(data, mime):
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as picture:
                width, height = picture.size
                if (picture.format != _FORMATS[mime] or width < 1 or height < 1
                        or max(width, height) > _MAX_DIMENSION or width * height > _MAX_PIXELS
                        or getattr(picture, "n_frames", 1) != 1):
                    return None
                picture.verify()
            # JPEG verification alone does not decode the body or reject truncation.
            with Image.open(BytesIO(data)) as picture:
                picture.load()
        return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
    except (OSError, ValueError, SyntaxError, EOFError, OverflowError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        return None


@lru_cache(maxsize=128)
def _download_image(url: str, bucket: int) -> str | None:
    """Bounded memory-only cache includes unavailable or invalid responses."""
    del bucket
    if not _safe_url(url):
        return None
    try:
        # No .netrc credentials, API headers, cookies or environment proxies.
        with requests.Session() as session:
            session.trust_env = False
            with session.get(url, stream=True, timeout=(2, 3), allow_redirects=False,
                             headers={"User-Agent": "BetBoy/1.0 (public participant images)"}) as response:
                if response.status_code != 200 or not _safe_url(response.url) or response.url != url:
                    return None
                mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if mime not in _FORMATS:
                    return None
                length = response.headers.get("Content-Length")
                if length is not None and (not length.isdecimal() or not 0 < int(length) <= _MAX_BYTES):
                    return None
                chunks, received = [], 0
                started = time.monotonic()
                for chunk in response.iter_content(chunk_size=8192):
                    received += len(chunk)
                    if received > _MAX_BYTES or time.monotonic() - started > 8:
                        return None
                    if chunk:
                        chunks.append(chunk)
                return _verified_data_uri(b"".join(chunks), mime)
    except (requests.RequestException, OSError, ValueError, TypeError):
        return None


def _native_team_id(value: object) -> int | None:
    if type(value) is int:
        return value if 0 < value <= 2**63 - 1 else None
    if isinstance(value, str) and len(value) <= 19 and re.fullmatch(r"[1-9][0-9]*", value):
        try:
            parsed = int(value)
            return parsed if parsed <= 2**63 - 1 else None
        except ValueError:
            pass
    return None


def participant_image(kind: str, name: str, *, team_id: object = None,
                      fixture_source: str | None = None, context_evidence: object = None,
                      side: str = "a") -> ParticipantImage | None:
    """Return a verified identity image, otherwise preserve the caller's fallback.

    ``context_evidence`` and ``side`` are deliberately not used to guess names,
    URLs or cross-provider IDs. Callers bind the existing participant ID/name.
    """
    del context_evidence, side
    bucket = int(time.time() // _CACHE_SECONDS)
    if kind == "football":
        if not isinstance(fixture_source, str) or fixture_source.strip().casefold() not in {"api-football", "api_football"}:
            return None
        native_id = _native_team_id(team_id)
        if native_id is None:
            return None
        url = f"https://media.api-sports.io/football/teams/{native_id}.png"
        data_uri = _download_image(url, bucket)
        return ParticipantImage(data_uri, url) if data_uri else None
    if kind == "tennis":
        portrait = _portrait(name, bucket)
        if portrait is None:
            return None
        data_uri = _download_image(portrait.url, bucket)
        return ParticipantImage(data_uri, portrait.source, portrait.credit + " · Bildausschnitt", portrait.crop) if data_uri else None
    return None
