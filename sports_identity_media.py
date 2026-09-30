"""Fail-closed public participant imagery, isolated from all sporting models.

Football crests use explicitly API-Football-native team IDs; NBA logos use
ESPN's NBA namespace. Other team logos and tennis portraits come only from
reviewed manifests; neither names nor provider IDs are searched on the network.
The browser loads each public image directly;
this module never downloads image bytes or writes a cache or database.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import unquote, urlsplit


_MANIFEST_PATH = Path(__file__).resolve().parent / "assets" / "identity" / "tennis-portraits.json"
_TEAM_MANIFEST_PATH = Path(__file__).resolve().parent / "assets" / "identity" / "team-logos.json"
_MAX_MANIFEST_BYTES = 256 * 1024
_MAX_TEAM_MANIFEST_BYTES = 128 * 1024
_MANIFEST_REFRESH_SECONDS = 24 * 60 * 60
_MAX_THUMBNAIL_WIDTH = 400
_COMMONS_HOSTS = frozenset({"upload.wikimedia.org", "thumb.wikimedia.org"})
_RASTER_FILE = re.compile(r".+\.(?:png|jpe?g|webp)$", re.IGNORECASE)
_TEAM_SPORT_PROVIDERS = {
    "basketball": frozenset({"espn", "euroleague"}),
    "ice_hockey": frozenset({"nhl"}),
    "cricket": frozenset({"cricbuzz", "cricketdata"}),
    "esports": frozenset({"pandascore"}),
}
# Exact, reviewed public team thumbnails, not a wildcard CDN grant.
_REVIEWED_ESPORT_IMAGE_URLS = frozenset({
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f5/Team_Spirit_new_em.svg/330px-Team_Spirit_new_em.svg.png",
    "https://img.navi.gg/teams/2025/10/teams-4028/thumbnail/58234/Team-Yandex_46x46.png",
    "https://static.tildacdn.net/tild6665-6161-4135-a464-323633633463/Frame_2091750347.png",
    "https://upload.wikimedia.org/wikipedia/commons/d/d6/Team_OG.png",
    "https://vitality.gg/cdn/shop/files/Vitality-logo-black-rgb_1_5c36a8d1-0cde-4aef-a074-2b4fafd5ec0b.png?height=100&v=1684483759",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/16/100_Thieves_logo.svg/330px-100_Thieves_logo.svg.png",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/3/3a/T1_esports_logo.svg/330px-T1_esports_logo.svg.png",
})


@dataclass(frozen=True)
class ParticipantImage:
    image_url: str
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


@dataclass(frozen=True)
class _TeamLogo:
    sport: str
    provider: str
    team_id: str
    names: tuple[str, ...]
    url: str
    source: str
    credit: str | None = None


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


def _safe_url_parts(url: object):
    if not isinstance(url, str) or not url or len(url) > 2048:
        return None
    if any(char.isspace() or ord(char) < 32 for char in url):
        return None
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
                or parsed.port is not None or parsed.query or parsed.fragment):
            return None
    except ValueError:
        return None
    return parsed


def safe_participant_image_url(url: object) -> str | None:
    """Allow only reviewed public team sources and small Commons thumbnails.

    Validation is entirely local. Originals, oversized thumbnails, arbitrary
    hosts, credentials and query strings are not granted to the browser. The
    only SVG exception is the official NHL logo path, used by callers as img
    (never inline SVG or an object/embed element).
    No HTTP preflight is performed; remote availability is a browser concern.
    """
    # A fixed small Vitality header URL contains a reviewed resize query; this
    # exact string is permitted, never arbitrary caller-supplied query values.
    if isinstance(url, str) and url in _REVIEWED_ESPORT_IMAGE_URLS:
        return url
    parsed = _safe_url_parts(url)
    if parsed is None:
        return None
    if parsed.netloc == "media.api-sports.io":
        match = re.fullmatch(r"/football/teams/([1-9][0-9]{0,18})\.png", parsed.path)
        return url if match and int(match.group(1)) <= 2**63 - 1 else None
    if parsed.netloc == "a.espncdn.com":
        match = re.fullmatch(r"/i/teamlogos/nba/500/([1-9][0-9]{0,18})\.png", parsed.path)
        return url if match and int(match.group(1)) <= 2**63 - 1 else None
    if parsed.netloc == "assets.nhle.com":
        return url if re.fullmatch(r"/logos/nhl/svg/[A-Z]{3}_light\.svg", parsed.path) else None
    if parsed.netloc == "mediacentre.euroleague.net":
        return url if re.fullmatch(r"/uploads/euroleaguecore/teams/logos/positive_[1-9][0-9]{0,9}\.png", parsed.path) else None
    if parsed.netloc == "static.cricbuzz.com":
        return url if re.fullmatch(r"/a/img/v1/152x152/i1/c[1-9][0-9]{0,9}/[a-z0-9][a-z0-9_-]{0,100}\.jpg", parsed.path) else None
    if parsed.netloc == "cdn.pandascore.co":
        return url if re.fullmatch(r"/images/team/image/[1-9][0-9]{0,18}/thumb_[A-Za-z0-9][A-Za-z0-9_.-]{0,180}\.(?:png|jpe?g|webp)", parsed.path) else None
    if parsed.netloc not in _COMMONS_HOSTS:
        return None
    if re.search(r"%(?![0-9a-fA-F]{2})", parsed.path):
        return None
    try:
        path = unquote(parsed.path, errors="strict")
    except UnicodeError:
        return None
    if (any(part in {".", ".."} for part in path.split("/")) or "\\" in path
            or any(ord(char) < 32 or ord(char) == 127 for char in path)):
        return None
    match = re.fullmatch(r"/wikipedia/commons/thumb/[0-9a-f]/[0-9a-f]{2}/([^/]+)/([1-9][0-9]{0,2})px-([^/]+)", path)
    if match is None:
        return None
    file_name, width, thumbnail_file = match.groups()
    if (int(width) > _MAX_THUMBNAIL_WIDTH or _RASTER_FILE.fullmatch(file_name) is None
            or thumbnail_file != file_name):
        return None
    return url


def participant_image_url_matches_kind(kind: str, url: object) -> bool:
    """Do not reuse a valid source URL in a different sport's image slot."""
    if safe_participant_image_url(url) is None:
        return False
    host = urlsplit(url).netloc
    if kind == "football":
        return host == "media.api-sports.io"
    if kind == "tennis":
        return (host in _COMMONS_HOSTS and url not in _REVIEWED_ESPORT_IMAGE_URLS
                and not any(row.url == url for row in _team_logos()))
    if kind == "basketball":
        return host in {"a.espncdn.com", "mediacentre.euroleague.net"}
    if kind == "ice_hockey":
        return host == "assets.nhle.com"
    if kind == "cricket":
        return host == "static.cricbuzz.com"
    if kind == "esports":
        return host == "cdn.pandascore.co" or url in _REVIEWED_ESPORT_IMAGE_URLS or any(
            row.sport == kind and row.url == url for row in _team_logos())
    return False


def _team_name(value: object) -> str:
    """Exact full team label; abbreviations only when explicitly reviewed."""
    if (not isinstance(value, str) or not value.strip() or len(value) > 200
            or any(unicodedata.category(char).startswith("C") for char in value)):
        return ""
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _provider(value: object) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def _team_key(value: object, provider: str, sport: str) -> str | None:
    if isinstance(value, str) and ":" in value:
        prefix = f"{provider}:{sport}:team:"
        if not value.startswith(prefix):
            return None
        value = value[len(prefix):]
    if provider == "euroleague":
        return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value) else None
    if provider == "cricketdata":
        # Current CricketData receipts do not carry team IDs; explicit reviewed
        # country names may resolve only in this provider's blank-ID namespace.
        return "" if value is None or value == "" else None
    native = _native_team_id(value)
    return str(native) if native is not None else None


@lru_cache(maxsize=1)
def _read_team_manifest(path: str, modified_ns: int, bucket: int) -> tuple[_TeamLogo, ...]:
    """Bounded reviewed logo metadata only, never image bytes or network I/O."""
    del modified_ns, bucket
    try:
        data = Path(path).read_bytes()
        if len(data) > _MAX_TEAM_MANIFEST_BYTES:
            return ()
        manifest = json.loads(data)
        entries = manifest.get("entries") if isinstance(manifest, dict) else None
        if not isinstance(entries, list) or len(entries) > 256:
            return ()
        logos = []
        for row in entries:
            if not isinstance(row, dict):
                return ()
            sport, provider = row.get("sport"), _provider(row.get("provider"))
            names, url, source = row.get("names"), row.get("url"), row.get("source")
            credit = row.get("credit")
            team_id = _team_key(row.get("team_id"), provider, sport)
            if (sport not in _TEAM_SPORT_PROVIDERS or provider not in _TEAM_SPORT_PROVIDERS[sport]
                    or team_id is None or not isinstance(names, list) or not 1 <= len(names) <= 12
                    or any(not _team_name(name) for name in names)
                    or safe_participant_image_url(url) is None or _safe_url_parts(source) is None
                    or (credit is not None and (not isinstance(credit, str) or not credit.strip()
                        or len(credit) > 500 or any(ord(char) < 32 for char in credit)))):
                return ()
            host = urlsplit(url).netloc
            if ((sport == "basketball" and host != "mediacentre.euroleague.net")
                    or (sport == "ice_hockey" and host != "assets.nhle.com")
                    or (sport == "cricket" and host != "static.cricbuzz.com")
                    or (sport == "esports" and host not in _COMMONS_HOSTS and url not in _REVIEWED_ESPORT_IMAGE_URLS)):
                return ()
            logos.append(_TeamLogo(sport, provider, team_id, tuple(names), url, source,
                                   credit.strip() if credit is not None else None))
        return tuple(logos)
    except (OSError, ValueError, TypeError, UnicodeError):
        return ()


def _team_logos() -> tuple[_TeamLogo, ...]:
    try:
        stat = _TEAM_MANIFEST_PATH.stat()
        if stat.st_size > _MAX_TEAM_MANIFEST_BYTES:
            return ()
        return _read_team_manifest(str(_TEAM_MANIFEST_PATH), stat.st_mtime_ns,
                                   int(time.time() // _MANIFEST_REFRESH_SECONDS))
    except OSError:
        return ()


def _team_logo(kind: str, name: str, team_id: object, provider: str,
               competition: object) -> ParticipantImage | None:
    if provider not in _TEAM_SPORT_PROVIDERS.get(kind, ()) or not _team_name(name):
        return None
    native_id = _team_key(team_id, provider, kind)
    if native_id is None:
        return None
    if kind == "basketball" and provider == "espn":
        # ESPN also has WNBA/NCAA IDs in the same basketball namespace; NBA
        # identity requires its competition even when the ID is namespaced.
        if _provider(competition) != "nba":
            return None
        url = f"https://a.espncdn.com/i/teamlogos/nba/500/{native_id}.png"
        return ParticipantImage(url, url)
    if kind == "esports" and provider == "pandascore":
        try:
            from participant_logo_catalog import resolve_pandascore_logo
        except ImportError:
            resolve_pandascore_logo = None
        if resolve_pandascore_logo is not None:
            url = resolve_pandascore_logo(native_id, name)
            if (safe_participant_image_url(url) is not None
                    and urlsplit(url).netloc == "cdn.pandascore.co"
                    and urlsplit(url).path.startswith(f"/images/team/image/{native_id}/thumb_")):
                return ParticipantImage(url, url)
    matches = [row for row in _team_logos() if row.sport == kind and row.provider == provider
               and row.team_id == native_id and any(_team_name(name) == _team_name(alias) for alias in row.names)]
    if len(matches) != 1:
        return None
    row = matches[0]
    return ParticipantImage(row.url, row.source, row.credit)


def _safe_url(url: object, *, source: bool = False) -> bool:
    if not source:
        return safe_participant_image_url(url) is not None
    parsed = _safe_url_parts(url)
    return (parsed is not None and parsed.netloc == "commons.wikimedia.org"
            and parsed.path.startswith("/wiki/File:"))


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
                      side: str = "a", competition: str | None = None) -> ParticipantImage | None:
    """Return a verified identity URL, otherwise preserve the caller's fallback.

    ``context_evidence`` and ``side`` are deliberately not used to guess names,
    URLs or cross-provider IDs. Callers bind the existing participant ID/name.
    """
    del context_evidence, side
    bucket = int(time.time() // _MANIFEST_REFRESH_SECONDS)
    if kind == "football":
        if not isinstance(fixture_source, str) or fixture_source.strip().casefold() not in {"api-football", "api_football"}:
            return None
        native_id = _native_team_id(team_id)
        if native_id is None:
            return None
        url = f"https://media.api-sports.io/football/teams/{native_id}.png"
        return ParticipantImage(url, url)
    if kind == "tennis":
        portrait = _portrait(name, bucket)
        if portrait is None:
            return None
        return ParticipantImage(portrait.url, portrait.source, portrait.credit + " · Bildausschnitt", portrait.crop)
    if kind in _TEAM_SPORT_PROVIDERS:
        return _team_logo(kind, name, team_id, _provider(fixture_source), competition)
    return None
