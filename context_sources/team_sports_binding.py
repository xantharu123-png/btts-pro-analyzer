"""Pure source-owned P3/B1 identity binding, not fitted or empirical approval.

The caller supplies the complete already-read B1 status inventory. This module
does not fetch, read SQLite, refit, alter an OriginalPrematch, or certify roster
coverage. A matching old receipt remains documentary after a later withdrawal;
the separate current state controls whether a native scheduled Event exists.
"""
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import math
import re

from context_models.contracts import ContextContractError, canonical_timestamp, digest, validate_event
from context_models.ice_hockey import FORMATS as HOCKEY_FORMATS
from context_models.team_sports import FORMATS as BASKETBALL_FORMATS
from context_models.team_sports_live import MAX_RAW_HISTORY, RECEIPT_KIND
from context_sources.team_sports_status import _id, _selected

BINDING_VERSION = "team-sports-original-native-binding-v1"
_PROVIDERS = {"ESPN": "espn", "espn": "espn", "EuroLeague": "euroleague",
              "euroleague": "euroleague", "NHL": "nhl", "nhl": "nhl"}
_COMPETITIONS = {"NBA": "nba", "nba": "nba", "EuroLeague": "euroleague",
                 "Euroleague": "euroleague", "euroleague": "euroleague", "NHL": "nhl", "nhl": "nhl"}
_SOURCE_SCOPE = {"espn": ("basketball", "nba"), "euroleague": ("basketball", "euroleague"),
                 "nhl": ("ice_hockey", "nhl")}
_STATUS = {**dict.fromkeys(("upcoming", "scheduled", "not_started", "not started", "ns", "fut", "pre", "FUT", "PRE"), "scheduled"),
           **dict.fromkeys(("completed", "final", "finished", "closed", "ended", "FINAL", "OFF"), "completed"),
           **dict.fromkeys(("started", "live", "LIVE", "CRIT"), "started"),
           **dict.fromkeys(("cancelled", "canceled", "CANC"), "cancelled")}


@dataclass(frozen=True)
class TeamSportOriginalBinding:
    event: dict | None
    receipt_binding: dict
    input_bindings: tuple[dict, ...]


def _first(raw, names):
    return next((raw[name] for name in names if raw.get(name)), None)


def _clock(value):
    try:
        return canonical_timestamp(value) if type(value) in (str, datetime) else None
    except ContextContractError:
        return None


def _word(value):
    return value if type(value) is str else None


def _whole(value):
    if type(value) is int and value >= 0:
        return value
    if type(value) is str and re.fullmatch(r"0|[1-9][0-9]*", value):
        try:
            return int(value)
        except ValueError:
            return None
    if type(value) is float and math.isfinite(value) and value >= 0 and value.is_integer():
        return int(value)
    return None


def _aliases(row):
    payload = row["payload"]
    source = row["source"]
    for item in payload["projection"]["aliases"]:
        scope = payload["request"]["request_season"] if item["scope"] == "request-season" else None
        yield source, row["sport"], item["field"], scope, _id(item["value"], source)


def _components(rows):
    """Whole causal co-occurrence graph; never join by names/time/scores."""
    parent = list(range(len(rows)))
    def root(i):
        while i != parent[i]:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    tokens = {}
    for i, row in enumerate(rows):
        claims = [(row["source"], row["sport"], "native-key", None, row["event_key"]), *_aliases(row)]
        for claim in claims:
            if claim in tokens:
                parent[root(i)] = root(tokens[claim])
            else:
                tokens[claim] = i
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[root(i)].append(row)
    components = tuple(tuple(sorted(values, key=lambda row: (row["observed_at"], row["digest"])))
                       for _, values in sorted(groups.items()))
    lookup = defaultdict(set)
    for i, group in enumerate(components):
        for row in group:
            for source, sport, field, scope, value in _aliases(row):
                lookup[(source, sport, value)].add((i, field, scope))
    return components, lookup


def _primary(group):
    source = group[0]["source"]
    if source == "espn":
        fields = ("competition.id", "event.id")
    elif source == "euroleague":
        fields = ("id", "identifier")
    else:
        fields = ("id",)
    for field in fields:
        values = {value for row in group for _, _, name, _, value in _aliases(row) if name == field}
        if values:
            return (f"{source}:{group[0]['sport']}:{next(iter(values))}" if len(values) == 1 else None), len(values) > 1
    return None, False  # EuroLeague request-season/gameCode alone is B1-only.


def _signature(row):
    return digest({key: row["payload"][key] for key in ("native", "projection")})


def _latest(group):
    newest = group[-1]["observed_at"]
    current = tuple(row for row in group if row["observed_at"] == newest)
    if len({_signature(row) for row in current}) != 1:
        return "conflicting", current
    if current[0]["payload"]["projection"]["issues"]:
        return "unknown", current
    return "available", current


def _raw_identity(raw, sport, index):
    reasons = set()
    provider = _first(raw, ("provider", "source"))
    source = _PROVIDERS.get(_word(provider))
    if source is None or _SOURCE_SCOPE[source][0] != sport:
        return None, None, {"raw-source-unavailable"}
    if any(_PROVIDERS.get(_word(raw[key])) not in (None, source) for key in ("provider", "source") if raw.get(key)):
        reasons.add("raw-source-conflict")
    competition = _COMPETITIONS.get(_word(_first(raw, ("competition_id", "league_id", "competition", "league", "tournament"))))
    if competition is None:
        reasons.add("raw-competition-unavailable")
    elif competition != _SOURCE_SCOPE[source][1]:
        reasons.add("raw-competition-conflict")
    if any(_COMPETITIONS.get(_word(raw[key])) not in (None, competition) for key in
           ("competition_id", "league_id", "competition", "league", "tournament") if raw.get(key)):
        reasons.add("raw-competition-conflict")
    if raw.get("sport") not in (None, "", sport):
        reasons.add("raw-sport-conflict")
    keys = ("provider_event_id", "event_id", "game_id", "match_id", "id") if index is None else ("provider_event_id", "event_id", "id")
    native = _id(_first(raw, keys), source)
    if native is None:
        reasons.add("raw-native-id-unavailable")
    return source, native, reasons


def _season(row):
    source, projection = row["source"], row["payload"]["projection"]
    values = projection["season"]
    if source == "espn":
        years = [data.get("year") for data in values.values() if type(data) is dict and "year" in data]
        valid = [str(year) for year in years if type(year) is int and year > 0]
        if len(valid) != len(years) or len(set(valid)) > 1:
            return None, "native-season-conflict"
        return (valid[0], None) if valid else (None, "native-season-unavailable")
    if source == "euroleague":
        return values["request"], None
    year = values.get("event")
    return (str(year), None) if type(year) is int and year > 0 else (None, "native-season-unavailable")


def _compare(raw, row, *, index):
    """Compare actual raw claims; missing metadata is not a canonical default."""
    source, projection = row["source"], row["payload"]["projection"]
    reasons, conflicts, missing_core = set(), set(), set()
    for side in ("home", "away"):
        team = _id(_first(raw, (side + "_team_id", "team1_id" if side == "home" else "team2_id")), source)
        native = projection[side + "_id"]
        if team is None or native is None:
            missing_core.add("native-participants-unavailable")
        elif native != f"{source}:{row['sport']}:team:{team}":
            conflicts.add("native-participants-conflict")
    start_fields = ("starts_at", "start_time", "scheduled_at") if index is None else ("start_time", "starts_at")
    start = _clock(_first(raw, start_fields))
    if start is None or projection["scheduled_start"] is None:
        missing_core.add("native-schedule-unavailable")
    elif start != projection["scheduled_start"]:
        conflicts.add("native-schedule-conflict")
    lifecycle = _STATUS.get(_word(raw.get("status")))
    actual = projection["status"]
    if lifecycle is None:
        missing_core.add("raw-status-unavailable")
    elif not (source == "euroleague" and lifecycle == "scheduled" and actual == "not_completed") and lifecycle != actual:
        conflicts.add("native-status-conflict")
    if index is None and actual != "scheduled":
        reasons.add("native-scheduled-status-unconfirmed")
    for side in ("home", "away"):
        # Preserve the exact original alias priority: present null is unknown,
        # present zero is zero; neither may fall through to another score.
        score = raw.get(side + "_score_final", raw.get(side + "_score"))
        if score is not None or lifecycle == "completed":
            expected = _whole(score)
            actual_score = projection["scores"][side]
            if expected is None or actual_score is None:
                missing_core.add("native-score-unavailable")
            elif expected != actual_score:
                conflicts.add("native-score-conflict")
    winner = raw.get("winner_side")
    if winner is not None:
        home, away = projection["scores"]["home"], projection["scores"]["away"]
        if winner not in ("home", "away") or home is None or away is None or home == away:
            missing_core.add("native-winner-unavailable")
        elif winner != ("home" if home > away else "away"):
            conflicts.add("native-winner-conflict")
    raw_neutral, native_neutral = raw.get("neutral_site"), projection["neutral_site"]
    if type(raw_neutral) is not bool:
        reasons.add("raw-neutral-unavailable")
    if native_neutral is None:
        reasons.add("native-neutral-unavailable")
    elif type(raw_neutral) is bool and raw_neutral != native_neutral:
        conflicts.add("native-neutral-conflict")
    native_season, season_problem = _season(row)
    if season_problem:
        (conflicts if season_problem.endswith("conflict") else reasons).add(season_problem)
    raw_season = raw.get("season")
    if raw_season is None:
        reasons.add("raw-season-unavailable")
    elif native_season is not None and (type(raw_season) not in (str, int) or str(raw_season) != native_season):
        conflicts.add("native-season-conflict")
    if source == "nhl":
        game_type = projection["game_type"]
        if type(game_type) is not int:
            reasons.add("native-game-type-unavailable")
        elif raw.get("game_type") is not None and (type(raw["game_type"]) not in (str, int) or str(raw["game_type"]) != str(game_type)):
            conflicts.add("native-game-type-conflict")
        period = raw.get("last_period_type")
        if period:
            outcome = row["payload"]["native"].get("gameOutcome")
            native_period = outcome.get("lastPeriodType") if type(outcome) is dict else None
            if native_period is None:
                missing_core.add("native-result-period-unavailable")
            elif period != native_period:
                conflicts.add("native-result-period-conflict")
    reasons.add("native-rules-unavailable")  # No supported status receipt carries rule/TOI evidence.
    return reasons, conflicts, missing_core


def _entry(index):
    return dict(input_index=index, native_event_key=None, match_state="missing", current_state="missing",
                current_received_at=None, reasons=[], matching_receipt_refs=[], lineage_refs=[])


def _resolve_input(raw, *, index, sport, components, lookup):
    result = _entry(index)
    if not isinstance(raw, Mapping):
        result.update(match_state="not_applicable", reasons=["raw-row-not-an-object"])
        return result, None
    source, native_id, reasons = _raw_identity(raw, sport, index)
    if source is None or native_id is None or any(word.endswith("conflict") for word in reasons):
        result.update(match_state="conflicting" if any(word.endswith("conflict") for word in reasons) else "unknown", reasons=sorted(reasons))
        return result, None
    candidates = set()
    composite_only = False
    for group, field, season in lookup.get((source, sport, native_id), ()):
        if field == "gameCode" and raw.get("season") != season:
            composite_only = True
            continue
        candidates.add(group)
    if not candidates:
        result["reasons"] = sorted(reasons | ({"native-season-composite-unresolved"} if composite_only else {"native-receipt-missing"}))
        return result, None
    relevant = tuple(row for number in sorted(candidates) for row in components[number])
    result["lineage_refs"] = sorted({row["digest"] for row in relevant})
    result["current_received_at"] = max(row["observed_at"] for row in relevant)
    if len(candidates) != 1:
        result.update(match_state="conflicting", current_state="conflicting", reasons=sorted(reasons | {"native-alias-ambiguous"}))
        return result, None
    primary, ambiguous = _primary(relevant)
    result["native_event_key"] = primary
    if ambiguous:
        result.update(match_state="conflicting", current_state="conflicting", reasons=sorted(reasons | {"native-alias-ambiguous"}))
        return result, None
    current_state, current = _latest(relevant)
    result["current_state"] = current_state
    if current_state != "available":
        reasons.add("native-current-" + current_state)
    if primary is None:
        reasons.add("native-season-composite-unresolved")
    by_clock = defaultdict(list)
    for row in relevant:
        by_clock[row["observed_at"]].append(row)
    matched, conflicts, missing_core = [], set(), set()
    for row in relevant:
        missing, different, unavailable = _compare(raw, row, index=index)
        if row["payload"]["projection"]["issues"] or len({_signature(other) for other in by_clock[row["observed_at"]]}) != 1:
            # Partial/ambiguous facts remain unusable, but a separately known
            # wrong participant must not disappear behind the unknown side.
            known_identity_conflict = different & {"native-participants-conflict"}
            conflicts.update(known_identity_conflict)
            missing_core.update(unavailable & {"native-participants-unavailable"})
            if row["observed_at"] == current[0]["observed_at"]:
                reasons.update(known_identity_conflict)
            continue
        conflicts.update(different)
        missing_core.update(unavailable)
        if not different and not unavailable:
            matched.append(row)
    if matched:
        result["match_state"] = "matched"
        result["matching_receipt_refs"] = sorted({row["digest"] for row in matched})
        for row in matched:
            reasons.update(_compare(raw, row, index=index)[0])
    else:
        result["match_state"] = "conflicting" if conflicts else "unknown"
        reasons.update(conflicts | missing_core | {"native-raw-revision-unmatched"})
    selected = None
    if current_state == "available":
        missing, different, unavailable = _compare(raw, current[0], index=index)
        reasons.update(missing | different | unavailable)
        if not different and not unavailable and primary is not None and result["match_state"] == "matched":
            selected = current[0]
        elif matched:
            reasons.add("native-original-revision-superseded")
    result["reasons"] = sorted(reasons)
    return result, selected


def _event(raw, row, binding, sport):
    if row is None or binding["current_state"] != "available":
        return None
    source, native_id, problems = _raw_identity(raw, sport, None)
    if problems:
        return None
    projection = row["payload"]["projection"]
    if projection["status"] != "scheduled":
        return None
    if sport == "basketball":
        format_code = next((name for name, declaration in BASKETBALL_FORMATS.items()
                            if declaration[:2] == (source, row["competition"])), None)
    else:
        season, _ = _season(row)
        game_type = projection["game_type"]
        format_code = next((name for name, kind in HOCKEY_FORMATS.items() if type(game_type) is int
                            and kind == game_type and season == "20252026"), None)
    if format_code is None:
        binding["reasons"] = sorted(set(binding["reasons"]) | {"native-format-unreviewed"})
        return None
    event_key = f"{source}:{sport}:{native_id}"
    revision = digest(dict(version=BINDING_VERSION, event_key=event_key,
        binding=binding, projection=projection, current_content=row["content_digest"]))
    return validate_event(dict(event_key=event_key, sport=sport, competition=row["competition"], format=format_code,
        home_id=projection["home_id"], away_id=projection["away_id"], status="scheduled",
        scheduled_start=projection["scheduled_start"], schedule_revision=revision))


def resolve_team_sport_original(original, rows):
    """Bind the actual raw inventory, using only receipts at original.as_of.

    match_state is row correspondence, NOT complete source/model qualification.
    Its reasons retain unresolved metadata. current_state independently records
    the newest whole alias component; matched older facts never restore it.
    A1 artifact_refs stay empty. Every returned object is detached.
    """
    from sports_prematch import OriginalPrematch
    if not isinstance(original, OriginalPrematch) or original.sport not in ("basketball", "ice_hockey"):
        raise ContextContractError("binding requires an actual basketball/hockey OriginalPrematch")
    if type(original.as_of) is not datetime or not isinstance(original.raw_event, Mapping) or type(original.raw_history) is not tuple:
        raise ContextContractError("original raw inventory or decision clock is malformed")
    if len(original.raw_history) > MAX_RAW_HISTORY:
        raise ContextContractError("original raw inventory exceeds the owning bound")
    cutoff = canonical_timestamp(original.as_of)
    # Validate the entire claimed inventory BEFORE cutoff, source or ID pruning.
    try:
        checked = tuple(deepcopy(_selected(row)) for row in rows)
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        raise ContextContractError("invalid claimed native receipt inventory") from exc
    eligible = tuple(sorted({row["digest"]: row for row in checked if row["observed_at"] <= cutoff}.values(),
                            key=lambda row: (row["observed_at"], row["digest"])))
    components, lookup = _components(eligible)
    results, selected = [], None
    for index, raw in [(None, original.raw_event), *enumerate(original.raw_history)]:
        binding, latest = _resolve_input(raw, index=index, sport=original.sport, components=components, lookup=lookup)
        results.append(binding)
        if index is None:
            selected = latest
    event = _event(original.raw_event, selected, results[0], original.sport)
    links = dict(schema=1, kind=RECEIPT_KIND,
        event_receipt=results[0]["matching_receipt_refs"][0] if results[0]["matching_receipt_refs"] else None,
        history_receipts=[dict(input_index=row["input_index"], receipt=row["matching_receipt_refs"][0])
                          for row in results[1:] if row["matching_receipt_refs"]], artifact_refs=[])
    return TeamSportOriginalBinding(deepcopy(event), deepcopy(links), tuple(deepcopy(results)))
