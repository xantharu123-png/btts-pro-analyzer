"""Validated N1Bet browser-import payloads and strict quote matching.

The browser extension only transports prices that are visible in the user's
browser.  This module remains the trust boundary: malformed, stale, ambiguous
or incorrectly scoped observations never reach a Streamlit price widget.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
import unicodedata
from typing import Any, Mapping, MutableMapping, Optional, Sequence
from urllib.parse import urlparse


N1_IMPORT_SCHEMA_VERSION = 1
N1_IMPORT_MAX_RECORDS = 1200
N1_IMPORT_MAX_PAYLOAD_AGE_SECONDS = 24 * 60 * 60
N1_IMPORT_PREMATCH_MAX_AGE_SECONDS = 10 * 60
N1_IMPORT_LIVE_MAX_AGE_SECONDS = 60
N1_IMPORT_FUTURE_TOLERANCE_SECONDS = 120


class N1ImportError(ValueError):
    """Raised when an extension payload is not safe to consume."""


@dataclass(frozen=True)
class N1ImportTarget:
    key: str
    sport: str
    event_name: str
    market: str
    selection: str
    participants: tuple[str, ...] = ()
    line: Optional[float] = None
    scheduled_start: Optional[str] = None
    live: bool = False

    def to_component_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "sport": self.sport,
            "event": self.event_name,
            "market": self.market,
            "selection": self.selection,
            "participants": list(self.participants),
            "line": self.line,
            "scheduledStart": self.scheduled_start,
            "live": self.live,
        }


@dataclass(frozen=True)
class N1ImportedQuote:
    record_id: str
    decimal_odds: float
    event: str
    market: str
    selection: str
    context: str
    captured_at: datetime
    source_page: str
    live: bool = False
    line: Optional[float] = None


@dataclass(frozen=True)
class N1ImportSnapshot:
    captured_at: datetime
    quotes: tuple[N1ImportedQuote, ...]
    page_count: int
    scanned_elements: int


@dataclass(frozen=True)
class N1ImportMatch:
    target: N1ImportTarget
    quote: N1ImportedQuote
    score: int


@dataclass(frozen=True)
class N1WidgetBinding:
    target: N1ImportTarget
    widget_key: str
    value_kind: str = "number"


_SPACE_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"(?<!\d)(\d+(?:[.,]\d+)?)(?!\d)")
_EVENT_SPLIT_RE = re.compile(r"\s+(?:vs\.?|v\.?|gegen|@)\s+", re.IGNORECASE)
_GENERIC_NAME_TOKENS = frozenset(
    {
        "afc",
        "bc",
        "cf",
        "club",
        "fc",
        "fk",
        "hc",
        "sc",
        "team",
        "the",
        "women",
        "w",
        "u19",
        "u20",
        "u21",
        "u23",
    }
)


def normalize_text(value: Any) -> str:
    """Return a conservative ASCII comparison form for provider labels."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.casefold().replace("ß", "ss")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return _SPACE_RE.sub(" ", text).strip()


def split_event_participants(event_name: str) -> tuple[str, ...]:
    base = str(event_name or "").split("|", 1)[0].strip()
    parts = tuple(part.strip() for part in _EVENT_SPLIT_RE.split(base) if part.strip())
    return parts if len(parts) == 2 else ()


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _finite_odds(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or not 1.0 < number <= 1000.0:
        return None
    return round(number, 4)


def _finite_line(value: Any) -> Optional[float]:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0.0 or number > 1000.0:
        return None
    return round(number, 3)


def _is_n1_page(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold().rstrip(".")
    return parsed.scheme == "https" and (host == "n1bet.com" or host.endswith(".n1bet.com"))


def _clean_text(value: Any, *, limit: int) -> str:
    text = _SPACE_RE.sub(" ", str(value or "")).strip()
    return text[:limit]


def parse_import_snapshot(
    payload: Mapping[str, Any],
    *,
    now: Optional[datetime] = None,
) -> N1ImportSnapshot:
    """Validate an extension snapshot and drop individual malformed records."""
    if not isinstance(payload, Mapping):
        raise N1ImportError("Importer-Antwort ist kein Objekt")
    if payload.get("version") != N1_IMPORT_SCHEMA_VERSION:
        raise N1ImportError("Importer-Version wird nicht unterstuetzt")
    if str(payload.get("bookmaker") or "").casefold() != "n1bet":
        raise N1ImportError("Importer-Quelle ist nicht N1Bet")

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    captured_at = _parse_datetime(payload.get("capturedAt"))
    if captured_at is None:
        raise N1ImportError("Importer-Zeitstempel fehlt oder ist ungueltig")
    age = (current - captured_at).total_seconds()
    if age < -N1_IMPORT_FUTURE_TOLERANCE_SECONDS:
        raise N1ImportError("Importer-Zeitstempel liegt in der Zukunft")
    if age > N1_IMPORT_MAX_PAYLOAD_AGE_SECONDS:
        raise N1ImportError("Importer-Daten sind veraltet")

    raw_records = payload.get("records")
    if not isinstance(raw_records, list):
        raise N1ImportError("Importer enthaelt keine Quotenliste")
    if len(raw_records) > N1_IMPORT_MAX_RECORDS:
        raise N1ImportError("Importer enthaelt zu viele Quoten")

    quotes: list[N1ImportedQuote] = []
    seen: set[tuple[Any, ...]] = set()
    for index, raw in enumerate(raw_records):
        if not isinstance(raw, Mapping):
            continue
        odds = _finite_odds(raw.get("odds"))
        source_page = _clean_text(raw.get("sourcePage") or payload.get("pageUrl"), limit=1000)
        record_time = _parse_datetime(raw.get("capturedAt")) or captured_at
        if odds is None or not _is_n1_page(source_page):
            continue
        record_age = (current - record_time).total_seconds()
        if (
            record_age < -N1_IMPORT_FUTURE_TOLERANCE_SECONDS
            or record_age > N1_IMPORT_MAX_PAYLOAD_AGE_SECONDS
        ):
            continue
        event = _clean_text(raw.get("event"), limit=500)
        market = _clean_text(raw.get("market"), limit=300)
        selection = _clean_text(raw.get("selection"), limit=300)
        context = _clean_text(raw.get("context"), limit=4000)
        if not context or not (event or market or selection):
            continue
        record_id = _clean_text(raw.get("id"), limit=160) or f"record-{index}"
        line = _finite_line(raw.get("line"))
        fingerprint = (
            normalize_text(event),
            normalize_text(market),
            normalize_text(selection),
            odds,
            line,
            source_page,
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        quotes.append(
            N1ImportedQuote(
                record_id=record_id,
                decimal_odds=odds,
                event=event,
                market=market,
                selection=selection,
                context=context,
                captured_at=record_time,
                source_page=source_page,
                live=raw.get("live") is True,
                line=line,
            )
        )

    diagnostics = payload.get("diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    page_count = diagnostics.get("pages", 1)
    scanned_elements = diagnostics.get("scannedElements", len(raw_records))
    try:
        page_count = max(0, int(page_count))
    except (TypeError, ValueError, OverflowError):
        page_count = 0
    try:
        scanned_elements = max(0, int(scanned_elements))
    except (TypeError, ValueError, OverflowError):
        scanned_elements = 0
    return N1ImportSnapshot(
        captured_at=captured_at,
        quotes=tuple(quotes),
        page_count=page_count,
        scanned_elements=scanned_elements,
    )


def _name_tokens(value: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in normalize_text(value).split()
        if token not in _GENERIC_NAME_TOKENS and len(token) >= 2
    )


def _participant_present(participant: str, haystack: str) -> bool:
    normalized = normalize_text(participant)
    if not normalized:
        return False
    if re.search(rf"(?:^| ){re.escape(normalized)}(?: |$)", haystack):
        return True
    tokens = _name_tokens(participant)
    if not tokens:
        return False
    if len(tokens) == 1:
        return len(tokens[0]) >= 4 and re.search(
            rf"(?:^| ){re.escape(tokens[0])}(?: |$)", haystack
        ) is not None
    return all(re.search(rf"(?:^| ){re.escape(token)}(?: |$)", haystack) for token in tokens)


def _market_family(text: str) -> Optional[str]:
    normalized = normalize_text(text)
    if not normalized:
        return None
    if any(token in normalized for token in ("gemischte chance", "mixed chance")) or (
        any(token in normalized for token in (" oder ", " or "))
        and any(token in normalized for token in ("uber", "over"))
    ):
        return "mixed"
    if any(
        token in normalized
        for token in (
            "resultat gesamttore",
            "result total",
            "result and total",
            "double chance and total",
            "doppelte chance und gesamttore",
        )
    ):
        return "result_total"
    if any(token in normalized for token in ("beide teams treffen", "both teams to score", "btts")):
        return "btts"
    if any(token in normalized for token in ("doppelte chance", "double chance")):
        return "double_chance"
    if any(token in normalized for token in ("ecken", "corner", "corners")):
        return "corners"
    if any(token in normalized for token in ("karten", "card", "cards", "bookings")):
        return "cards"
    if any(token in normalized for token in ("team 1 gesamttore", "team 2 gesamttore", "team total")):
        return "team_total"
    if any(token in normalized for token in ("gesamttore", "total goals", "goals over under")):
        return "total"
    if any(
        token in normalized
        for token in (
            "endergebnis",
            "match winner",
            "moneyline",
            "full time result",
            "winner",
            "sieger",
            "1x2",
        )
    ):
        return "winner"
    return None


def _target_family(target: N1ImportTarget) -> Optional[str]:
    return _market_family(f"{target.market} {target.selection}")


def _extract_numbers(value: str) -> tuple[float, ...]:
    numbers: list[float] = []
    for match in _NUMBER_RE.finditer(str(value or "")):
        try:
            number = float(match.group(1).replace(",", "."))
        except ValueError:
            continue
        if math.isfinite(number):
            numbers.append(round(number, 3))
    return tuple(numbers)


def _contains_token(text: str, token: str) -> bool:
    return re.search(rf"(?:^| ){re.escape(token)}(?: |$)", text) is not None


def _selection_matches(target: N1ImportTarget, quote: N1ImportedQuote) -> bool:
    target_selection = normalize_text(target.selection)
    quote_selection = normalize_text(quote.selection)
    quote_market = normalize_text(quote.market)
    raw = f"{quote_selection} {quote_market}".strip()
    participants = target.participants or split_event_participants(target.event_name)
    family = _target_family(target)

    if family == "result_total":
        compact = raw.replace(" ", "")
        connector_ok = " und " in f" {raw} " or " and " in f" {raw} " or "&" in quote.selection
        target_numbers = _extract_numbers(target.selection)
        number_ok = bool(target_numbers) and any(
            math.isclose(target_numbers[0], actual, abs_tol=0.001)
            for actual in _extract_numbers(raw)
        )
        side = next((token for token in ("1x", "x2", "12") if token in target_selection.replace(" ", "")), None)
        direction_ok = (
            ("uber" in target_selection and ("uber" in raw or "over" in raw))
            or ("unter" in target_selection and ("unter" in raw or "under" in raw))
        )
        return bool(connector_ok and number_ok and side and side in compact and direction_ok)

    if family == "mixed":
        connector_ok = " oder " in f" {raw} " or " or " in f" {raw} "
        target_numbers = _extract_numbers(target.selection)
        number_ok = bool(target_numbers) and any(
            math.isclose(target_numbers[0], actual, abs_tol=0.001)
            for actual in _extract_numbers(raw)
        )
        over_ok = "uber" in raw or "over" in raw
        if "btts" in target_selection or "beide teams treffen" in target_selection:
            first_leg_ok = (
                "btts" in raw
                or "both teams to score" in raw
                or "beide teams treffen" in raw
            ) and ("yes" in raw or "ja" in raw)
        elif "team 1" in target_selection:
            first_leg_ok = "team 1" in raw or "home" in raw or (
                len(participants) == 2 and _participant_present(participants[0], raw)
            )
        else:
            first_leg_ok = "team 2" in raw or "away" in raw or (
                len(participants) == 2 and _participant_present(participants[1], raw)
            )
        return bool(connector_ok and number_ok and over_ok and first_leg_ok)

    if target_selection in {"ja", "yes"}:
        return _contains_token(raw, "ja") or _contains_token(raw, "yes")
    if target_selection in {"nein", "no"}:
        return _contains_token(raw, "nein") or _contains_token(raw, "no")
    if target_selection in {"unentschieden", "draw", "x"}:
        return raw in {"x", "draw", "unentschieden"} or any(
            _contains_token(raw, token) for token in ("draw", "unentschieden")
        )
    if target_selection in {"heimsieg", "home", "1"}:
        return raw in {"1", "home", "heimsieg"} or (
            len(participants) == 2 and _participant_present(participants[0], raw)
        )
    if target_selection in {"auswartssieg", "away", "2"}:
        return raw in {"2", "away", "auswartssieg"} or (
            len(participants) == 2 and _participant_present(participants[1], raw)
        )
    if target_selection in {"1x", "x2", "12"}:
        compact = raw.replace(" ", "")
        return target_selection in compact

    direction = None
    if "uber" in target_selection or "over" in target_selection:
        direction = "over"
    elif "unter" in target_selection or "under" in target_selection:
        direction = "under"
    if direction:
        direction_ok = (
            ("over" in raw or "uber" in raw)
            if direction == "over"
            else ("under" in raw or "unter" in raw)
        )
        expected_numbers = _extract_numbers(target.selection)
        actual_numbers = _extract_numbers(f"{quote.selection} {quote.market}")
        return direction_ok and bool(expected_numbers) and any(
            math.isclose(expected_numbers[0], number, abs_tol=0.001)
            for number in actual_numbers
        )

    target_numbers = _extract_numbers(target.selection)
    if len(target_numbers) >= 2:
        quote_numbers = _extract_numbers(f"{quote.selection} {quote.market}")
        return all(any(math.isclose(value, actual, abs_tol=0.001) for actual in quote_numbers) for value in target_numbers)

    if _participant_present(target.selection, raw):
        return True
    return bool(target_selection) and target_selection == quote_selection


def _market_matches(target: N1ImportTarget, quote: N1ImportedQuote) -> bool:
    participants = target.participants or split_event_participants(target.event_name)
    target_market = normalize_text(target.market)
    quote_market = normalize_text(quote.market)
    target_team_index = 0 if "team 1" in target_market else (1 if "team 2" in target_market else None)
    quote_team_indexes = {
        index
        for index, participant in enumerate(participants[:2])
        if _participant_present(participant, quote_market)
    }
    if target_team_index is not None:
        explicit_team = f"team {target_team_index + 1}" in quote_market
        if not explicit_team and target_team_index not in quote_team_indexes:
            return False
        if quote_team_indexes and target_team_index not in quote_team_indexes:
            return False
    elif quote_team_indexes:
        return False

    target_family = _target_family(target)
    quote_family = _market_family(f"{quote.market} {quote.context}")
    if target_family is None or quote_family is None:
        return bool(target_market and quote_market and target_market == quote_market)
    if target_family == quote_family:
        return True
    if target_team_index is not None and {target_family, quote_family} == {
        "team_total",
        "total",
    }:
        return True
    return {target_family, quote_family} <= {"winner"}


def _event_matches(target: N1ImportTarget, quote: N1ImportedQuote) -> bool:
    participants = target.participants or split_event_participants(target.event_name)
    event_haystack = normalize_text(f"{quote.event} {quote.context}")
    if len(participants) == 2:
        return all(_participant_present(participant, event_haystack) for participant in participants)
    target_event = normalize_text(target.event_name.split("|", 1)[0])
    return bool(target_event and target_event in event_haystack)


def _line_matches(target: N1ImportTarget, quote: N1ImportedQuote) -> bool:
    if target.line is None:
        return True
    if quote.line is not None:
        return math.isclose(float(target.line), quote.line, abs_tol=0.001)
    quote_numbers = _extract_numbers(f"{quote.market} {quote.selection}")
    return any(math.isclose(float(target.line), number, abs_tol=0.001) for number in quote_numbers)


def _start_matches(target: N1ImportTarget, quote: N1ImportedQuote) -> bool:
    target_start = _parse_datetime(target.scheduled_start)
    if target_start is None:
        return True
    quoted_start_match = re.search(
        r"\b(20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2}))\b",
        quote.context,
    )
    if not quoted_start_match:
        return True
    quoted_start = _parse_datetime(quoted_start_match.group(1))
    return quoted_start is not None and abs((target_start - quoted_start).total_seconds()) <= 30 * 60


def _match_score(
    target: N1ImportTarget,
    quote: N1ImportedQuote,
    *,
    now: datetime,
) -> Optional[int]:
    max_age = N1_IMPORT_LIVE_MAX_AGE_SECONDS if target.live else N1_IMPORT_PREMATCH_MAX_AGE_SECONDS
    age = (now - quote.captured_at).total_seconds()
    if age < -N1_IMPORT_FUTURE_TOLERANCE_SECONDS or age > max_age:
        return None
    if target.live and not quote.live:
        return None
    if not target.live and quote.live:
        return None
    if not _event_matches(target, quote):
        return None
    if not _market_matches(target, quote):
        return None
    if not _selection_matches(target, quote):
        return None
    if not _line_matches(target, quote) or not _start_matches(target, quote):
        return None

    score = 100
    if normalize_text(quote.event):
        score += 20
    if normalize_text(quote.market):
        score += 10
    if normalize_text(quote.selection):
        score += 10
    if target.line is not None and quote.line is not None:
        score += 5
    if target.scheduled_start:
        score += 2
    return score


def match_imported_quotes(
    targets: Sequence[N1ImportTarget],
    snapshot: N1ImportSnapshot,
    *,
    now: Optional[datetime] = None,
) -> dict[str, N1ImportMatch]:
    """Return only unique, exact event/market/selection matches."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    matches: dict[str, N1ImportMatch] = {}
    for target in targets:
        ranked: list[tuple[int, N1ImportedQuote]] = []
        for quote in snapshot.quotes:
            score = _match_score(target, quote, now=current)
            if score is not None:
                ranked.append((score, quote))
        ranked.sort(key=lambda item: (item[0], item[1].captured_at), reverse=True)
        if not ranked:
            continue
        best_score, best_quote = ranked[0]
        conflicting = [
            quote
            for score, quote in ranked[1:]
            if score == best_score
            and not math.isclose(quote.decimal_odds, best_quote.decimal_odds, abs_tol=1e-9)
        ]
        if conflicting:
            continue
        matches[target.key] = N1ImportMatch(target, best_quote, best_score)
    return matches


def apply_imported_widget_value(
    state: MutableMapping[str, Any],
    binding: N1WidgetBinding,
    match: N1ImportMatch,
) -> bool:
    """Apply a quote without overwriting a user's manual edit."""
    tracking_key = "_n1_imported_widget_values"
    tracked = state.get(tracking_key)
    if not isinstance(tracked, dict):
        tracked = {}
        state[tracking_key] = tracked
    previous = tracked.get(binding.widget_key)
    current = state.get(binding.widget_key)
    can_replace = current in (None, "", 0, 0.0)
    if previous is not None:
        if isinstance(current, str):
            try:
                can_replace = math.isclose(float(current.replace(",", ".")), float(previous), abs_tol=1e-9)
            except ValueError:
                can_replace = False
        elif isinstance(current, (int, float)) and not isinstance(current, bool):
            can_replace = math.isclose(float(current), float(previous), abs_tol=1e-9)
    if not can_replace:
        return False
    value: Any = match.quote.decimal_odds
    if binding.value_kind == "text":
        value = f"{match.quote.decimal_odds:.2f}"
    state[binding.widget_key] = value
    tracked[binding.widget_key] = match.quote.decimal_odds
    return True


__all__ = [
    "N1ImportError",
    "N1ImportedQuote",
    "N1ImportMatch",
    "N1ImportSnapshot",
    "N1ImportTarget",
    "N1WidgetBinding",
    "N1_IMPORT_LIVE_MAX_AGE_SECONDS",
    "N1_IMPORT_PREMATCH_MAX_AGE_SECONDS",
    "apply_imported_widget_value",
    "match_imported_quotes",
    "normalize_text",
    "parse_import_snapshot",
    "split_event_participants",
]
