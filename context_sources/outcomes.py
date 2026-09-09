"""Owning result receipts for offline context training, never feature history.

These adapters consume already received native envelopes. They perform no I/O
and cannot establish historical publication by hashing a newly imported result.
The serve contract is validated for experiments; there is deliberately no
invented ESPN serve adapter when bilateral service observations are absent.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from context_models.contracts import (
    ContextContractError, _sport_json, canonical_timestamp, digest, normalize_observation,
    require_list, require_object, require_text, validate_event,
)
from context_observations import _check_selected_row

FOOTBALL_OUTCOME = "football-regulation-ft-v1"
TENNIS_WINNER_OUTCOME = "tennis-completed-winner-v1"
TENNIS_SERVE_OUTCOME = "tennis-completed-serve-v1"
OUTCOME_SCHEMAS = {
    FOOTBALL_OUTCOME: ("api-football", "fixture-regulation-outcome-v1"),
    TENNIS_WINNER_OUTCOME: ("espn", "espn-tennis-winner-outcome-v1"),
    TENNIS_SERVE_OUTCOME: ("espn", "tennis-observed-serve-outcome-v1"),
}


def _count(value, label):
    if type(value) is not int or value < 0:
        raise ContextContractError(f"{label} requires an actual nonnegative integer")
    return value


def validate_outcome_payload(payload: dict, *, event: dict) -> dict:
    event = validate_event(event)
    require_object(payload, {"schema", "outcome_contract", "home_id", "away_id",
                             "scheduled_start", "terminal", "result"}, label="outcome payload")
    if type(payload["schema"]) is not int or payload["schema"] != 1:
        raise ContextContractError("unsupported outcome schema")
    for field in ("home_id", "away_id", "scheduled_start"):
        if payload[field] != event[field]:
            raise ContextContractError("outcome and original event binding differ")
    contract, result = require_text(payload["outcome_contract"], "outcome contract", code=True), payload["result"]
    if contract == FOOTBALL_OUTCOME:
        if event["sport"] != "football" or event["format"] != "90min" or payload["terminal"] != "FT":
            raise ContextContractError("goal target requires native regulation FT")
        require_object(result, {"goals_home", "goals_away"}, label="regulation result")
        for key in result:
            _count(result[key], key)
    elif contract in {TENNIS_WINNER_OUTCOME, TENNIS_SERVE_OUTCOME}:
        if (event["sport"] != "tennis" or event.get("tour") not in {"ATP", "WTA"}
                or event["format"] not in {"singles", "singles_best_of_3", "singles_best_of_5"}
                or payload["terminal"] != "completed"):
            raise ContextContractError("winner target requires completed native singles")
        fields = {"winner_id"}
        if contract == TENNIS_SERVE_OUTCOME:
            fields |= {"set_scores", "held_games_home", "service_games_home",
                       "held_games_away", "service_games_away"}
        require_object(result, fields, label="completed tennis result")
        if require_text(result["winner_id"], "native winner", code=True) not in {event["home_id"], event["away_id"]}:
            raise ContextContractError("winner is not an original native participant")
        if contract == TENNIS_SERVE_OUTCOME:
            if event["format"] not in {"singles_best_of_3", "singles_best_of_5"}:
                raise ContextContractError("serve outcome requires explicit best-of format")
            needed = 2 if event["format"] == "singles_best_of_3" else 3
            wins, games, breakers, non_tiebreak_wins = [0, 0], 0, 0, [0, 0]
            scores = require_list(result["set_scores"], "final set scores")
            for score in scores:
                if max(wins) == needed:
                    raise ContextContractError("observed set follows an already completed match")
                require_object(score, {"home", "away"}, label="final set")
                a, b = _count(score["home"], "home games"), _count(score["away"], "away games")
                hi, lo = max(a, b), min(a, b)
                if not (hi == 6 and lo <= 4 or hi == 7 and lo in {5, 6}):
                    raise ContextContractError("unsupported or incomplete final set contract")
                wins[int(b > a)] += 1
                games += a + b
                tiebreak = int(hi == 7 and lo == 6)
                breakers += tiebreak
                non_tiebreak_wins[0] += a - tiebreak * int(a > b)
                non_tiebreak_wins[1] += b - tiebreak * int(b > a)
            if max(wins) != needed or wins[0] == wins[1]:
                raise ContextContractError("set outcome does not complete the declared match")
            if result["winner_id"] != event["home_id" if wins[0] > wins[1] else "away_id"]:
                raise ContextContractError("winner and final set outcome disagree")
            for side in ("home", "away"):
                held = _count(result[f"held_games_{side}"], "observed held games")
                trials = _count(result[f"service_games_{side}"], "observed service games")
                if trials <= 0 or held > trials:
                    raise ContextContractError("invalid measured bilateral hold/trial target")
            if result["service_games_home"] + result["service_games_away"] != games - breakers:
                raise ContextContractError("service trials disagree with actual non-tiebreak games")
            for index, side, opponent in ((0, "home", "away"), (1, "away", "home")):
                reconstructed = result[f"held_games_{side}"] + result[f"service_games_{opponent}"] - result[f"held_games_{opponent}"]
                if reconstructed != non_tiebreak_wins[index]:
                    raise ContextContractError("bilateral holds/trials cannot produce the observed score")
            possible_trials = set()
            for first_server in (0, 1):
                service_counts, server = [0, 0], first_server
                for score in scores:
                    a, b = score["home"], score["away"]
                    total = a + b
                    ordinary = total - int(max(a, b) == 7 and min(a, b) == 6)
                    service_counts[server] += (ordinary + 1) // 2
                    service_counts[1-server] += ordinary // 2
                    # A tiebreak is not a hold trial but occupies one game in
                    # service rotation; its first receiver serves next set.
                    server = (server + total) % 2
                possible_trials.add(tuple(service_counts))
            if (result["service_games_home"], result["service_games_away"]) not in possible_trials:
                raise ContextContractError("observed service counts violate service alternation")
    else:
        raise ContextContractError("unsupported outcome contract")
    return deepcopy(payload)


def _record(event, result, contract, terminal, observed_at):
    if not isinstance(observed_at, datetime):
        raise ContextContractError("outcome ingestion requires an actual aware datetime")
    observed = canonical_timestamp(observed_at)
    if observed <= event["scheduled_start"]:
        raise ContextContractError("result cannot be received before the original start")
    payload = validate_outcome_payload({"schema": 1, "outcome_contract": contract,
        "home_id": event["home_id"], "away_id": event["away_id"],
        "scheduled_start": event["scheduled_start"], "terminal": terminal, "result": result}, event=event)
    source, schema = OUTCOME_SCHEMAS[contract]
    return normalize_observation({"event_key": event["event_key"], "sport": event["sport"],
        "competition": event["competition"], "format": event["format"],
        "subject_id": event["event_key"], "kind": "match_outcome", "source": source,
        "source_schema": schema, "source_revision": digest(payload),
        "schedule_revision": event["schedule_revision"], "published_at": None,
        "publication_proof": None, "valid_from": observed, "valid_until": None,
        "complete": True, "payload": payload}, observed_at=observed_at)


def normalize_football_outcome(event: dict, source: dict, *, observed_at: datetime) -> dict | None:
    from context_sources.football import _detail_event
    event = validate_event(event)
    native = _detail_event(source)
    for key in ("event_key", "sport", "competition", "format", "home_id", "away_id", "scheduled_start"):
        if event[key] != native[key]:
            raise ContextContractError("native football outcome differs from original event")
    if source["fixture"]["status"]["short"] != "FT":
        return None
    goals = source.get("goals")
    if type(goals) is not dict:
        raise ContextContractError("missing regulation goals are not zero")
    return _record(event, {"goals_home": goals.get("home"), "goals_away": goals.get("away")},
                   FOOTBALL_OUTCOME, "FT", observed_at)


def normalize_tennis_outcome(event: dict, source: dict, *, observed_at: datetime) -> dict | None:
    from context_sources.tennis import _espn, _id
    event = validate_event(event)
    if type(source) is not dict or source.get("source_schema") != "espn-scoreboard-v1":
        raise ContextContractError("only the reviewed native ESPN winner source is supported")
    native = _espn(source)
    if native is None or native["status"] != "completed":
        return None
    tour = native["tour"]
    prefix = f"espn:tennis:{tour}:player:"
    if (event["sport"] != "tennis" or tour != event.get("tour")
            or event["event_key"] != f"espn:tennis:{tour}:match:{native['event_id']}"
            or event["competition"] != f"espn:{tour}:tournament:{native['tournament_id']}"
            or event["scheduled_start"] != canonical_timestamp(native["scheduled_start"])
            or {event["home_id"], event["away_id"]} !=
               {prefix + native["player_a_id"], prefix + native["player_b_id"]}):
        raise ContextContractError("native tennis outcome differs from original event")
    competitors = source["competition"]["competitors"]
    flags = [c.get("winner") for c in competitors]
    if any(type(flag) is not bool for flag in flags) or sum(flags) != 1:
        raise ContextContractError("completed outcome needs exactly one actual winner flag")
    winner = next(c for c in competitors if c["winner"])
    return _record(event, {"winner_id": prefix + _id(winner["id"])},
                   TENNIS_WINNER_OUTCOME, "completed", observed_at)


def validate_outcome_record(row: dict, *, event: dict) -> dict:
    """Validate a selected B1 receipt; the receipt is not an A1 artifact hash."""
    _check_selected_row(row)
    event = validate_event(event)
    payload = validate_outcome_payload(row["payload"], event=event)
    for key in ("event_key", "sport", "competition", "format", "schedule_revision"):
        if row[key] != event[key]:
            raise ContextContractError("outcome receipt has a different event scope")
    contract = payload["outcome_contract"]
    if ((row["source"], row["source_schema"]) != OUTCOME_SCHEMAS[contract]
            or row["kind"] != "match_outcome" or row["subject_id"] != event["event_key"]
            or row["source_revision"] != digest(payload) or row["complete"] is not True
            or row["valid_from"] != row["observed_at"] or row["valid_until"] is not None
            or row["published_at"] is not None or row["publication_proof"] is not None
            or row["observed_at"] <= event["scheduled_start"]):
        raise ContextContractError("outcome source content and actual receipt binding disagree")
    expected = "api-football:football:" if event["sport"] == "football" else f"espn:tennis:{event['tour']}:match:"
    if not event["event_key"].startswith(expected):
        raise ContextContractError("outcome source cannot certify a foreign native event")
    return deepcopy(row)


def normalize_football_base_input(source: dict, *, observed_at: datetime) -> dict:
    """Keep one native detail receipt for raw-goal replay and native joins.

    The first recipe does not invent challenge_stats or old calibrators. Its
    native detail bytes remain available to the B4 provenance/roster adapters.
    Importing an old detail now does not make it a pre-decision receipt.
    """
    from context_sources.football import _detail_event, normalize_football_context
    require_object(source, {"fixture", "league", "teams", "goals"},
                   optional={"score", "lineups", "players", "statistics", "events"}, label="native base detail")
    detail = _sport_json(source, label="native base detail")
    event = _detail_event(detail)
    observed = canonical_timestamp(observed_at)
    if not isinstance(observed_at, datetime):
        raise ContextContractError("base ingestion requires an actual datetime")
    terminal = detail["fixture"]["status"]["short"]
    if terminal not in {"FT", "NS", "TBD", "PST"}:
        raise ContextContractError("raw-goal replay only supports native FT or scheduled inputs")
    require_object(detail["goals"], {"home", "away"}, label="native goal pair")
    if terminal == "FT":
        for value in detail["goals"].values():
            _count(value, "native FT goals")
        if event["scheduled_start"] >= observed:
            raise ContextContractError("completed base input precedes actual result receipt")
    elif any(value is not None for value in detail["goals"].values()):
        raise ContextContractError("scheduled base input cannot contain future target goals")
    if type(detail["league"].get("season")) is not int or detail["league"]["season"] <= 0:
        raise ContextContractError("native base input needs an actual season identifier")
    normalize_football_context(event, injuries=[], lineups=[], appearances=[detail], observed_at=observed_at)
    payload = {"schema": 1, "detail": detail}
    return normalize_observation({"event_key": event["event_key"], "sport": "football",
        "competition": event["competition"], "format": "90min", "subject_id": event["event_key"],
        "kind": "base_fixture", "source": "api-football", "source_schema": "native-football-base-detail-v1",
        "source_revision": digest(payload), "schedule_revision": event["schedule_revision"],
        "published_at": None, "publication_proof": None, "valid_from": observed,
        "valid_until": None, "complete": True, "payload": payload}, observed_at=observed_at)


def validate_football_base_input(row: dict) -> dict:
    _check_selected_row(row)
    require_object(row["payload"], {"schema", "detail"}, label="native base input payload")
    if type(row["payload"]["schema"]) is not int or row["payload"]["schema"] != 1:
        raise ContextContractError("unknown base input schema")
    expected = normalize_football_base_input(row["payload"]["detail"], observed_at=datetime.fromisoformat(row["observed_at"]))
    if any(row[key] != value for key, value in expected.items()):
        raise ContextContractError("native detail and B1 source receipt bindings disagree")
    return deepcopy(row)
