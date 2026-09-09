"""C4 internal, source-bound series comparisons. No feed, price or activation.

The base is the exact original post-IID-roundtrip winner probability. The
roster reference is observed equal-series participation, NOT Elo influence
weights. Synthetic fitting tests do not establish real source availability.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import math
from pathlib import Path
import re

import numpy as np
from model_artifacts import canonical_bytes

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    event_in_population, require_digest, require_list, require_number,
    require_object, require_text, validate_base_distribution, validate_event,
    validate_effect_artifact, validate_feature_vector,
)
from context_models.offset import ContextModelError, adjust_parameters, offset_delta

FAMILY = "esports:series:winner"
BASE_VERSION = "esports-original-post-iid-series-v1"
REFERENCE_KIND = "esports-observed-series-reference-v1"
FEATURE_VERSION = "esports-native-participation-load-v1"
MODEL_VARIANT = "esports-signed-series-logit-v1"
COMPARISON_VERSION = "esports-context-comparison-v1"
COMPARISON_KIND = "esports-series-comparison-reference-v1"
FORMATS = {f"series_best_of_{n}": n for n in (1, 3, 5)}
TITLES = {"csgo", "lol", "dota2", "valorant"}
_ROOT = Path(__file__).resolve().parents[1]
# Code is read once on module import, never downloaded or reconstructed from a
# forecast label. These are exact loaded source bytes, not predictive approval.
_CODE_HASHES = {name: hashlib.sha256((_ROOT / name).read_bytes()).hexdigest()
                for name in ("esports_elo.py", "multi_sport_recommendations.py")}


def _integer(value, label):
    if type(value) is not int or value <= 0:
        raise ContextContractError(f"{label} requires a positive native integer")
    return value


def native_identity(value, kind="event"):
    require_text(value, "native esports identity", code=True)
    prefix = "pandascore:esports:" + ("" if kind == "event" else kind + ":")
    tail = value[len(prefix):] if value.startswith(prefix) else ""
    if not re.fullmatch(r"[1-9][0-9]*", tail):
        raise ContextContractError("native esports identity namespace/type mismatch")
    return value


def esports_event(event):
    event = validate_event(event)
    if event["sport"] != "esports" or event["format"] not in FORMATS:
        raise ContextContractError("only explicit esports BO1/BO3/BO5 series are supported")
    native_identity(event["event_key"])
    for side in ("home_id", "away_id"):
        native_identity(event[side], "team")
    return event


def esports_scope(value, event):
    require_object(value, {"title", "title_id", "competition_id", "season_id", "rules"}, label="native esports scope")
    if type(value["title"]) is not str or value["title"] not in TITLES:
        raise ContextContractError("unknown native esports title")
    for key in ("title_id", "competition_id", "season_id"):
        _integer(value[key], key)
    if event["competition"] != f"pandascore:title:{value['title_id']}:competition:{value['competition_id']}":
        raise ContextContractError("native esports title/competition differs")
    rules = require_object(value["rules"], {"best_of", "starting_maps_a", "starting_maps_b", "forfeit"}, label="native series rules")
    if (type(rules["best_of"]) is not int or rules["best_of"] != FORMATS[event["format"]]
            or type(rules["forfeit"]) is not bool or rules["forfeit"]
            or any(type(rules[key]) is not int or rules[key] != 0 for key in ("starting_maps_a", "starting_maps_b"))):
        raise ContextContractError("only explicit normal unhandicapped non-forfeit series rules are supported")
    return deepcopy(value)


def _number(value, label):
    require_number(value, label)
    if type(value) is int and int(float(value)) != value:
        raise ContextModelError(f"{label} is not exactly representable in float64")
    return value


def series_probability(base_probability: float, signed_delta: float) -> float:
    """One strict B2 logit law; no independent map promotion or clipping."""
    _number(base_probability, "series base probability")
    _number(signed_delta, "signed series residual")
    return float(adjust_parameters(np.array([base_probability], dtype=float),
                                  np.array([signed_delta], dtype=float), link="logit")[0])


def _selected(observations, decision, kickoff):
    """Select whole native revisions after validating every actual B1 receipt.

    The B1 subject includes participant/scope identity. Old participants survive
    SQLite latest-selection as proof, but never supply old numeric values.
    """
    from context_observations import factor_state, freshness_policy
    from context_sources.esports import SCHEMA, validate_esports_receipt
    if type(observations) is not tuple:
        raise ContextContractError("esports requires actual selected B1 receipt tuples")
    groups, event_history = {}, {}
    stamp = canonical_timestamp(decision)
    for row in observations:
        if type(row) is not dict:
            raise ContextContractError("esports requires a B1 receipt object")
        state = factor_state((row,), cutoff=decision, scheduled_start=kickoff,
            policy=freshness_policy(row.get("kind"), schedule_revision=row.get("schedule_revision"), requires_complete=False))
        if row["sport"] != "esports" or row["source_schema"] != SCHEMA:
            continue
        payload = validate_esports_receipt(row)
        if row["evidence_class"] != "prospective" or row["observed_at"] > stamp:
            continue
        item = payload["data"].get("map_id") if payload["kind"] == "map" else None
        groups.setdefault((row["event_key"], payload["kind"], item), []).append((row, state))
        event_history.setdefault(row["event_key"], []).append(row)

    def identity(row):
        payload = row["payload"]
        return digest({"event": {key: value for key, value in payload["event"].items() if key != "status"},
                       "scope": payload["scope"]})

    selected, ambiguities = {}, []
    for key, history in groups.items():
        latest_time = max(row["observed_at"] for row, _ in history)
        latest = {row["content_digest"]: (row, state) for row, state in history if row["observed_at"] == latest_time}
        entries = list(latest.values())
        state = "conflicting" if len(entries) != 1 else entries[0][1]["state"]
        current = entries[0][0] if len(entries) == 1 and entries[0][0]["digest"] in entries[0][1]["usable_refs"] else None
        selected[key] = (current, state)
        if key[1] not in {"series", "map"}:
            continue
        prior = {row["payload"]["event"][side] for row, _ in history for side in ("home_id", "away_id")}
        prior_identities = {identity(row) for row, _ in history}
        # A complete correction can retire an old native identity or scope.
        # A partial replacement must retain that uncertainty even if filtering
        # its new season would otherwise leave an apparently empty history.
        if current is None or (not current["complete"] and prior_identities != {identity(current)}):
            proof = tuple({row["digest"]: row for row, _ in history}.values())
            upper = max((row["observed_at"] for row, state in entries), default=None)
            if any(row["digest"] not in state["usable_refs"] for row, state in entries):
                upper = None
            ambiguities.append({"kind": key[1], "teams": prior, "upper": upper, "proof": proof})
    # Different fact kinds share ONE native event revision. A later lineup
    # cannot leave an old result/map joined to former participants or season.
    # Normal started -> completed status evolution alone does not rewrite a
    # previously observed map. The reverse transition withdraws terminal series
    # facts, but does not invent a new end time from a completed individual map.
    for event_key, history in event_history.items():
        latest_time = max(row["observed_at"] for row in history)
        latest = [row for row in history if row["observed_at"] == latest_time]
        identities = {identity(row) for row in latest}
        statuses = {row["payload"]["event"]["status"] for row in latest}
        conflict = len(identities) != 1 or len(statuses) != 1
        newest = sorted(latest, key=lambda row: row["digest"])[0]
        applicable = newest["valid_from"] <= stamp and (newest["valid_until"] is None or stamp < newest["valid_until"])
        selected[(event_key, "event_revision", None)] = (newest if applicable else None, "conflicting" if conflict else "available" if applicable else "stale")
        withdrawn = not conflict and statuses == {"cancelled"} and applicable
        for key, (row, state) in list(selected.items()):
            if key[0] != event_key or key[1] == "event_revision" or row is None:
                continue
            # Only a new terminal fact after the actual retraction may restore
            # its own result/end. Later unrelated completed map/lineup metadata
            # cannot authenticate an older withdrawn series completion.
            terminal_retracted = key[1] in {"series", "observed_lineup"} and any(
                item["payload"]["event"]["status"] in {"started", "cancelled"} and item["observed_at"] > row["observed_at"]
                for item in history)
            # A refreshed series receipt still cannot end before an actually
            # completed native map belonging to the same event/participants.
            # Unknown times remain unknown; no map score is an inferred clock.
            series_end = row["payload"]["data"].get("actual_end") if key[1] == "series" else None
            inconsistent_end = series_end is not None and any(
                map_key[0] == event_key and map_key[1] == "map" and item is not None
                and identity(item) == identity(row) and item["payload"]["status"] == "completed"
                and item["payload"]["data"]["actual_end"] is not None
                and item["payload"]["data"]["actual_end"] > series_end
                for map_key, (item, _) in selected.items())
            if conflict or withdrawn or terminal_retracted or inconsistent_end or identity(row) not in identities:
                selected[key] = (None, "conflicting" if not withdrawn else "missing")
                if key[1] in {"series", "map"}:
                    # A cancellation retracts the measured fact; it does not
                    # establish zero activity or an older exact recovery time.
                    terminal = not withdrawn and not terminal_retracted and not inconsistent_end and all(item["payload"]["kind"] in {"series", "map"} and item["payload"]["status"] == "completed"
                                   and (key[1] != "series" or item["payload"]["event"]["status"] == "completed") for item in latest)
                    ambiguities.append({"kind": key[1], "teams": {item["payload"]["event"][side] for item in history for side in ("home_id", "away_id")},
                        "upper": max(item["observed_at"] for item in latest) if terminal else None, "proof": tuple(history)})
    return selected, ambiguities


def _legacy_projection(row):
    keys = {"match_id", "begin_at", "end_at", "opponent_id", "won", "number_of_games"}
    if type(row) is not dict or not keys <= set(row):
        raise ContextContractError("original native Elo history fields are missing")
    result = {key: deepcopy(row[key]) for key in keys}
    for key in ("match_id", "opponent_id", "number_of_games"):
        _integer(result[key], key)
    if result["number_of_games"] not in (1, 3, 5) or type(result["won"]) is not bool:
        raise ContextContractError("unknown historical series result/rules")
    for key in ("begin_at", "end_at"):
        if type(result[key]) is not str:
            raise ContextContractError("original Elo clocks must retain actual strings")
        canonical_timestamp(result[key])
    return result


def _constants():
    import esports_elo as elo
    return {key: getattr(elo, key) for key in ("ELO_BASE", "ELO_SCALE", "ELO_K_FACTOR", "ELO_BO1_K_MULTIPLIER", "ELO_ITERATIONS")}


def _replay(windows, event):
    from esports_elo import _subgraph_matches, expected_score, subgraph_ratings
    from multi_sport_recommendations import _map_probability_from_series_probability, _series_win_probability
    a, b = (int(event[key].rsplit(":", 1)[1]) for key in ("home_id", "away_id"))
    ratings = subgraph_ratings(windows["home"], windows["away"], a, b)
    maps_to_win = FORMATS[event["format"]] // 2 + 1
    p_map = _map_probability_from_series_probability(expected_score(*ratings[:2]), maps_to_win)
    return (_series_win_probability(p_map, 0, 0, maps_to_win), list(ratings),
            _subgraph_matches(windows["home"], windows["away"], a, b))


def _reference_rows(reference):
    event, stamp = reference["event"], reference["cutoff"]
    selected, ambiguities = _selected(tuple(reference["receipts"]), datetime.fromisoformat(stamp), datetime.fromisoformat(event["scheduled_start"]))
    by_digest = {row["digest"]: row for row in reference["receipts"]}
    target = by_digest.get(reference["event_receipt"])
    if target is None or target["payload"]["event"] != event or target["payload"]["scope"] != reference["scope"]:
        raise ContextIntegrityError("original native event receipt does not bind the full event/scope")
    key = (event["event_key"], target["payload"]["kind"], None)
    if selected.get(key, (None,))[0] != target:
        raise ContextIntegrityError("original native event receipt is not the selected causal revision")
    used, series = {target["digest"]}, {}
    for side in ("home", "away"):
        team = event[side + "_id"]
        seen = set()
        for item in reference["windows"][side]:
            item = _legacy_projection(item)
            key = f"pandascore:esports:{item['match_id']}"
            if key == event["event_key"] or key in seen:
                raise ContextIntegrityError("duplicate or target series in original team window")
            seen.add(key)
            row = selected.get((key, "series", None), (None,))[0]
            if row is None or row["payload"]["status"] != "completed":
                raise ContextIntegrityError("native series result receipt unresolved or conflicting")
            payload, historical = row["payload"], row["payload"]["event"]
            opponent = f"pandascore:esports:team:{item['opponent_id']}"
            data = payload["data"]
            target_scope = {key: value for key, value in reference["scope"].items() if key != "rules"}
            historical_scope = {key: value for key, value in payload["scope"].items() if key != "rules"}
            if (set((historical["home_id"], historical["away_id"])) != {team, opponent}
                or historical_scope != target_scope or payload["scope"]["rules"]["best_of"] != item["number_of_games"]
                or historical["scheduled_start"] != canonical_timestamp(item["begin_at"])
                or data["actual_end"] != canonical_timestamp(item["end_at"])
                or data["actual_end"] >= stamp or data["winner_id"] != (team if item["won"] else opponent)):
                raise ContextIntegrityError("original Elo row disagrees with native result/participants/clocks/scope")
            used.add(row["digest"])
            series[key] = row
    if used != set(by_digest) or len(by_digest) != len(reference["receipts"]):
        raise ContextIntegrityError("original native receipt inventory differs or contains duplicates")
    return series


def validate_esports_reference(value, history_refs):
    fields = {"schema", "kind", "event", "scope", "cutoff", "code_hashes", "model_version", "constants",
              "windows", "subgraph", "ratings", "receipts", "event_receipt", "participation"}
    require_object(value, fields, label="original native esports reference")
    if type(value["schema"]) is not int or value["schema"] != 1 or value["kind"] != REFERENCE_KIND:
        raise ContextContractError("unknown original esports reference")
    event = esports_event(value["event"])
    esports_scope(value["scope"], event)
    if (event["status"] != "scheduled" or type(value["cutoff"]) is not str
            or canonical_timestamp(value["cutoff"]) != value["cutoff"] or value["cutoff"] >= event["scheduled_start"]):
        raise ContextContractError("original esports reference is not a native prematch decision")
    if value["code_hashes"] != _CODE_HASHES or value["model_version"] != "subgraph-elo-v3" or canonical_bytes(value["constants"]) != canonical_bytes(_constants()):
        raise ContextIntegrityError("original Elo code/version/constants differ")
    require_object(value["windows"], {"home", "away"}, label="two original ordered team windows")
    from multi_sport_recommendations import esports_history_window
    for side in ("home", "away"):
        rows = require_list(value["windows"][side], "original team window")
        if len(rows) != 20 or any(_legacy_projection(row) != row for row in rows):
            raise ContextContractError("original Elo requires its exact twenty-row team windows")
    selected_windows = esports_history_window({"status": "upcoming", "begin_at": event["scheduled_start"],
        "team1_history": value["windows"]["home"], "team2_history": value["windows"]["away"]}, now=datetime.fromisoformat(value["cutoff"]))
    if list(selected_windows) != [value["windows"]["home"], value["windows"]["away"]]:
        raise ContextIntegrityError("original native history order or causal selection differs")
    require_list(value["receipts"], "original native receipts")
    require_digest(value["event_receipt"])
    series = _reference_rows(value)
    probability, ratings, subgraph = _replay(value["windows"], event)
    if canonical_bytes(value["subgraph"]) != canonical_bytes(subgraph) or canonical_bytes(value["ratings"]) != canonical_bytes(ratings):
        raise ContextIntegrityError("native Elo subgraph/carried second pass does not replay")
    expected = [{"ref": row["digest"], "source": "pandascore", "source_event_id": key.split(":", 2)[2],
                 "native_event_key": key, "event_join": "verified_native", "roster_join": "unresolved"}
                for key, row in sorted(series.items())]
    if history_refs != expected:
        raise ContextIntegrityError("native Elo original history reference inventory differs")
    participation = {"version": "observed-equal-unique-series-v1", "teams": {}}
    for side in ("home_id", "away_id"):
        team = event[side]
        refs = sorted(row["digest"] for row in series.values() if team in (row["payload"]["event"]["home_id"], row["payload"]["event"]["away_id"]))
        participation["teams"][team] = [{"ref": ref, "weight": 1. / len(refs)} for ref in refs]
    if value["participation"] != participation:
        raise ContextIntegrityError("measured equal-series reference is not the actual contributing series")
    return deepcopy(value)


def validate_esports_base(base):
    reference = base["reference_weights"]
    if reference["kind"] == "unavailable":
        return
    if reference["kind"] == COMPARISON_KIND:
        validate_esports_comparison(base)
        return
    probability, _, _ = _replay(reference["windows"], reference["event"])
    if (base["version"] != BASE_VERSION or base["event_key"] != reference["event"]["event_key"]
            or base["cutoff"] != reference["cutoff"] or base["params"] != {"p_a": probability}
            or base["markets"] != {"series_winner_a": probability, "series_winner_b": 1. - probability}
            or base["model_hash"] != digest({"version": BASE_VERSION, "reference": reference})):
        raise ContextIntegrityError("original unrounded post-roundtrip esports base does not replay")


def export_esports_base(match, *, event, observations, cutoff, windows, probability):
    """Called at the original pre-rounding calculation point, never a card read."""
    event = esports_event(event)
    stamp = canonical_timestamp(cutoff)
    if (event["status"] != "scheduled" or event["scheduled_start"] <= stamp
        or match.get("status") != "upcoming" or type(match.get("series_type")) is not int
        or match["series_type"] != FORMATS[event["format"]]
        or any(type(match.get(f"team{i}_score")) is not int or match[f"team{i}_score"] != 0 for i in (1, 2))
        or any(type(match.get(key)) is not int or match[key] <= 0 for key in ("id", "team1_id", "team2_id"))
        or event["event_key"] != f"pandascore:esports:{match['id']}"
        or event["home_id"] != f"pandascore:esports:team:{match['team1_id']}"
        or event["away_id"] != f"pandascore:esports:team:{match['team2_id']}"
        or event["scheduled_start"] != canonical_timestamp(match.get("begin_at"))):
        raise ContextIntegrityError("original esports candidate and requested native prematch event differ")
    original = {"version": BASE_VERSION, "model_hash": digest({"version": BASE_VERSION, "event": event, "cutoff": stamp, "probability": probability}),
                "event_key": event["event_key"], "cutoff": stamp, "family": FAMILY, "params": {"p_a": probability},
                "markets": {"series_winner_a": probability, "series_winner_b": 1. - probability}, "history_refs": [],
                "reference_weights": {"schema": 1, "kind": "unavailable", "reason": "native-series-scope-receipts-unavailable"}}
    selected, _ = _selected(observations, cutoff, datetime.fromisoformat(event["scheduled_start"]))
    targets = [row for (key, kind, _), (row, state) in selected.items() if row is not None and key == event["event_key"]
               and kind in {"lineup", "patch_veto"} and row["payload"]["event"] == event]
    if not targets:
        return validate_base_distribution(original)
    scopes = {digest(row["payload"]["scope"]) for row in targets}
    if len(scopes) != 1:
        return validate_base_distribution(original)
    target = sorted(targets, key=lambda row: (row["observed_at"], row["digest"]))[-1]
    scope = target["payload"]["scope"]
    cleaned = {side: [_legacy_projection(row) for row in rows] for side, rows in zip(("home", "away"), windows)}
    series_keys = {f"pandascore:esports:{row['match_id']}" for rows in cleaned.values() for row in rows}
    receipts = {target["digest"]: target}
    for key in sorted(series_keys):
        row = selected.get((key, "series", None), (None,))[0]
        if row is None:
            return validate_base_distribution(original)
        receipts[row["digest"]] = row
    p, ratings, subgraph = _replay(cleaned, event)
    if p != probability:
        raise ContextIntegrityError("optional original-base export changed winner bytes")
    reference = {"schema": 1, "kind": REFERENCE_KIND, "event": event, "scope": scope, "cutoff": stamp,
        "code_hashes": deepcopy(_CODE_HASHES), "model_version": "subgraph-elo-v3", "constants": _constants(),
        "windows": cleaned, "subgraph": subgraph, "ratings": ratings, "receipts": [receipts[key] for key in sorted(receipts)],
        "event_receipt": target["digest"], "participation": {"version": "observed-equal-unique-series-v1", "teams": {}}}
    # A missing native link is unavailable provenance, not a different price or
    # an invented baseline. Malformed selected receipt bytes already failed above.
    try:
        series = _reference_rows(reference)
    except ContextIntegrityError:
        return validate_base_distribution(original)
    for side in ("home_id", "away_id"):
        team = event[side]
        refs = sorted(row["digest"] for row in series.values() if team in (row["payload"]["event"]["home_id"], row["payload"]["event"]["away_id"]))
        reference["participation"]["teams"][team] = [{"ref": ref, "weight": 1. / len(refs)} for ref in refs]
    original["history_refs"] = [{"ref": row["digest"], "source": "pandascore", "source_event_id": key.split(":", 2)[2],
        "native_event_key": key, "event_join": "verified_native", "roster_join": "unresolved"} for key, row in sorted(series.items())]
    original["reference_weights"] = reference
    original["model_hash"] = digest({"version": BASE_VERSION, "reference": reference})
    return validate_base_distribution(original)


def esports_reference_hash(base, event, preprocessing_artifacts=None):
    preprocessing = {} if preprocessing_artifacts is None else preprocessing_artifacts
    if type(preprocessing) is not dict:
        raise ContextContractError("esports preprocessing needs exact named artifact refs")
    for name, value in preprocessing.items():
        require_text(name, "preprocessing name", code=True)
        require_digest(value, "preprocessing artifact")
    return digest({"version": "esports-context-reference-v1", "base_hash": digest(validate_base_distribution(base)),
                   "event_hash": digest(esports_event(event)), "preprocessing": sorted(set(preprocessing.values()))})


def _lineup(row):
    if row is None or not row["complete"] or row["payload"]["status"] == "cancelled":
        return None
    result = {}
    for team, data in row["payload"]["data"]["teams"].items():
        if not data["complete"] or not data["players"] or any(player["participated"] is None for player in data["players"]):
            return None
        result[team] = {player["player_id"]: int(player["participated"]) for player in data["players"]}
    return result


def _same_title_season(left, right):
    return {key: item for key, item in left.items() if key != "rules"} == {key: item for key, item in right.items() if key != "rules"}


def esports_features(event: dict, observations: tuple[dict, ...], base: dict, *, cutoff: datetime) -> dict:
    """Native lineup differences and observed load, never complete-career claims."""
    event, original = esports_event(event), validate_base_distribution(base)
    if not isinstance(cutoff, datetime):
        raise ContextContractError("esports feature cutoff requires an actual aware datetime")
    stamp, kickoff = canonical_timestamp(cutoff), datetime.fromisoformat(event["scheduled_start"])
    if (original["family"] != FAMILY or original["version"] != BASE_VERSION or original["event_key"] != event["event_key"]
            or original["cutoff"] != stamp):
        raise ContextIntegrityError("esports feature input is not its original event/base/cutoff")
    recipe = original["reference_weights"]
    if recipe["kind"] != "unavailable" and recipe["event"] != event:
        raise ContextIntegrityError("esports reference belongs to another full event revision")
    selected, ambiguities = _selected(observations, cutoff, kickoff)
    values, states, refs = {}, {}, {}
    target_revision, revision_state = selected.get((event["event_key"], "event_revision", None), (None, "missing"))
    target_terminal = target_revision is not None and target_revision["payload"]["event"]["status"] in {"cancelled", "completed", "started"}
    target_mismatch = revision_state == "conflicting" or (target_revision is not None and target_revision["payload"]["event"] != event)

    def put(name, value, rows=(), state=None):
        state = state or ("available" if value is not None else "missing")
        if event["status"] != "scheduled" or stamp >= event["scheduled_start"] or target_terminal:
            state = "not_applicable"
        elif target_mismatch:
            state = "conflicting"
        values[name] = value if state == "available" else None
        states[name] = state
        refs[name] = sorted({row["digest"] for row in rows}) if state == "available" else []

    current, current_state = selected.get((event["event_key"], "lineup", None), (None, "missing"))
    scope = None if recipe["kind"] == "unavailable" else recipe["scope"]
    if current is not None and (current["payload"]["event"] != event or current["payload"]["scope"] != scope):
        current, current_state = None, "missing"
    projected = _lineup(current)
    historical, rosters, complete = [], {}, scope is not None
    if complete:
        for historical_result in recipe["receipts"]:
            payload = historical_result["payload"]
            if payload["kind"] != "series":
                continue
            key = payload["event"]["event_key"]
            result, _ = selected.get((key, "series", None), (None, "missing"))
            row, _ = selected.get((key, "observed_lineup", None), (None, "missing"))
            measured = _lineup(row)
            if (result != historical_result or measured is None or row["payload"]["event"] != payload["event"]
                    or row["payload"]["scope"] != payload["scope"]):
                complete = False
            else:
                historical.extend((historical_result, row))
                rosters[historical_result["digest"]] = measured
    good = complete and projected is not None
    membership = set(player for team in (projected or {}).values() for player in team)
    for measured in rosters.values():
        for team in (event["home_id"], event["away_id"]):
            membership.update(measured.get(team, {}))
    if scope is not None:
        for player in sorted(membership):
            vocabulary = f"{scope['title_id']}/{scope['season_id']}/{player}"
            current_value = None if projected is None else projected[event["home_id"]].get(player, 0) - projected[event["away_id"]].get(player, 0)
            ref_value = None
            if complete:
                exposure = {}
                for side in ("home_id", "away_id"):
                    team = event[side]
                    exposure[side] = math.fsum(item["weight"] * rosters[item["ref"]][team].get(player, 0)
                                              for item in recipe["participation"]["teams"][team])
                ref_value = exposure["home_id"] - exposure["away_id"]
            put("participation_current/" + vocabulary, current_value, (current,) if current else ())
            put("participation_reference/" + vocabulary, ref_value, historical)
            put("participation_delta/" + vocabulary, current_value - ref_value if good else None,
                (current, *historical) if good else (), "conflicting" if current_state == "conflicting" else None)
    put("participation_complete", int(good) if current is not None else None, (current, *historical) if current else ())

    load = [row for (key, kind, _), (row, _) in selected.items()
            if row is not None and kind in {"series", "map"} and key != event["event_key"] and row["payload"]["status"] == "completed"
            and scope is not None and _same_title_season(row["payload"]["scope"], scope)
            and (row["payload"]["data"]["actual_end"] is None or row["payload"]["data"]["actual_end"] < stamp)]
    # Map IDs are global native identities, not repeatable per parent series.
    map_groups = {}
    for row in load:
        if row["payload"]["kind"] == "map":
            map_groups.setdefault(row["payload"]["data"]["map_id"], []).append(row)
    duplicates = {row["digest"] for group in map_groups.values() if len(group) > 1 for row in group}
    for group in map_groups.values():
        if len(group) > 1:
            ambiguities.append({"kind": "map", "teams": {row["payload"]["event"][side] for row in group for side in ("home_id", "away_id")},
                                "upper": max(row["observed_at"] for row in group), "proof": tuple(group)})
    load = [row for row in load if row["digest"] not in duplicates]
    roots, timing = [], []
    for side in ("home", "away"):
        team = event[side + "_id"]
        rows = [row for row in load if team in (row["payload"]["event"]["home_id"], row["payload"]["event"]["away_id"])]
        ambiguous = [item for item in ambiguities if team in item["teams"]]
        proof = [row for item in ambiguous for row in item["proof"]]
        for kind in ("series", "map"):
            subset = [row for row in rows if row["payload"]["kind"] == kind]
            known = [row for row in subset if row["payload"]["data"]["actual_end"] is not None]
            unknown = [row for row in subset if row["payload"]["data"]["actual_end"] is None]
            for days in (1, 3, 7):
                first = canonical_timestamp(cutoff - timedelta(days=days))
                conflict = any(item["kind"] == kind and (item["upper"] is None or item["upper"] >= first) for item in ambiguous)
                uncertain = any(row["observed_at"] >= first for row in unknown)
                window = [row for row in known if first <= row["payload"]["data"]["actual_end"] < stamp]
                incomplete = any(not row["complete"] for row in window)
                count = len(window) if subset and not uncertain and not conflict and not incomplete else None
                root = f"observed_{kind}_count_{days}d"
                put(root + "_" + side, count, (*subset, *proof), "conflicting" if conflict else None)
                put(root + "_complete_" + side, int(not uncertain and not conflict and not incomplete) if subset else None, (*subset, *proof), "conflicting" if conflict else None)
                if root not in roots:
                    roots.append(root)
        # Recovery is from observed SERIES completion, not from last map score,
        # planned start, medical fatigue or an asserted complete player schedule.
        series = [row for row in rows if row["payload"]["kind"] == "series"]
        known = [row for row in series if row["payload"]["data"]["actual_end"] is not None]
        unknown = [row for row in series if row["payload"]["data"]["actual_end"] is None]
        last = max((row["payload"]["data"]["actual_end"] for row in known), default=None)
        conflict = any(item["kind"] == "series" and (last is None or item["upper"] is None or item["upper"] >= last) for item in ambiguous)
        exact = last if last is not None and all(row["observed_at"] < last for row in unknown) and not conflict else None
        upper = max([row["observed_at"] for row in series] + [item["upper"] for item in ambiguous if item["kind"] == "series" and item["upper"] is not None], default=None)
        for label, instant in (("exact", exact), ("minimum", exact or upper)):
            root = "observed_recovery_" + label + "_hours"
            value = None if instant is None else (kickoff - datetime.fromisoformat(instant)).total_seconds() / 3600
            put(root + "_" + side, value, (*series, *proof), "conflicting" if conflict else None)
            if root not in roots:
                roots.append(root)
        put("history_complete_" + side, 0 if series else None, series)
        put("active_map_minutes_" + side, None)
        put("medical_fatigue_" + side, None)
        case = "no-history" if not series else "known-end-times" if not unknown else "bounded-receipt" if exact is None else (
            "bounded-irrelevant-end-times" if all(row["observed_at"] < canonical_timestamp(cutoff - timedelta(days=7)) for row in unknown)
            else "partial-exact-end-times")
        timing.append("conflicting" if conflict else case)
    for root in roots:
        left, right = root + "_home", root + "_away"
        state = "available" if states[left] == states[right] == "available" else "conflicting" if "conflicting" in (states[left], states[right]) else "missing"
        put(root + "_delta", values[left] - values[right] if state == "available" else None, state=state)
        if state == "available":
            refs[root + "_delta"] = sorted(set(refs[left]) | set(refs[right]))
    patch, patch_state = selected.get((event["event_key"], "patch_veto", None), (None, "missing"))
    if patch is not None and (patch["payload"]["scope"] != scope or patch["payload"]["event"] != event):
        patch, patch_state = None, "missing"
    patch_known = patch is not None and patch["payload"]["data"]["patch_id"] is not None
    put("patch_reported", int(patch_known) if patch else None, (patch,) if patch else (), "conflicting" if patch_state == "conflicting" else None)
    projection = current["payload"]["data"]["status"] if current else "missing"
    scope_hash = "unavailable" if scope is None else digest(scope)
    return validate_feature_vector({"version": FEATURE_VERSION, "event_key": event["event_key"], "cutoff": stamp,
        "values": values, "states": states, "refs": refs,
        "coverage": {"version": FEATURE_VERSION + ".coverage", "case": f"scope-{scope_hash}.lineup-{projection}.{'complete' if good else 'partial'}.observed-only.{timing[0]}.{timing[1]}.patch-{'reported' if patch_known else 'unknown'}"},
        "reference_hash": esports_reference_hash(original, event)})


def _prepare_effect(base, features, artifact, event):
    if type(base) is not dict or base.get("version") != BASE_VERSION:
        raise ContextModelError("esports requires its unadjusted original series base")
    original, event = validate_base_distribution(base), esports_event(event)
    features, artifact = validate_feature_vector(features), validate_effect_artifact(artifact)
    if original["family"] != FAMILY or artifact["family"] != FAMILY:
        raise ContextModelError("esports effect family differs")
    reference = original["reference_weights"]
    if reference["kind"] != REFERENCE_KIND:
        raise ContextModelError("native esports original reference unavailable")
    if (reference["event"] != event or original["event_key"] != event["event_key"] or features["event_key"] != event["event_key"]
        or original["cutoff"] != features["cutoff"]
        or features["reference_hash"] != esports_reference_hash(original, event, artifact["preprocessing_artifacts"])):
        raise ContextIntegrityError("esports full original event/base/features binding differs")
    if (artifact["preprocessing_artifacts"] or artifact["model_variant"] != MODEL_VARIANT
        or features["version"] != FEATURE_VERSION or artifact["feature_version"] != FEATURE_VERSION
        or artifact["coverage"] != features["coverage"] or features["coverage"]["version"] != FEATURE_VERSION + ".coverage"):
        raise ContextModelError("unsupported esports ordered feature/coverage/model variant")
    if (event["status"] != "scheduled" or event["scheduled_start"] <= original["cutoff"] or artifact["training_end"] > original["cutoff"]
        or not event_in_population(event, artifact["population"]) or artifact["population"]["competitions"] != [event["competition"]]
        or artifact["population"]["formats"] != [event["format"]]):
        raise ContextModelError("esports effect outside its exact predecision title/competition/format population")
    pieces = features["coverage"]["case"].split(".")
    timings = {"no-history", "known-end-times", "bounded-receipt", "bounded-irrelevant-end-times", "partial-exact-end-times", "conflicting"}
    if (len(pieces) != 7 or pieces[0] != "scope-" + digest(reference["scope"])
        or pieces[1] not in {"lineup-confirmed", "lineup-candidate", "lineup-missing"}
        or pieces[2] not in {"complete", "partial"} or pieces[3] != "observed-only"
        or pieces[4] not in timings or pieces[5] not in timings or pieces[6] not in {"patch-reported", "patch-unknown"}):
        raise ContextModelError("esports scope/season coverage differs")
    if artifact["feature_names"] != sorted(artifact["feature_names"]):
        raise ContextModelError("esports feature vocabulary must retain canonical artifact-wide order")

    def available(name):
        if features["states"].get(name) != "available" or not features["refs"].get(name):
            raise ContextModelError("esports effect cannot consume unavailable/unreferenced values")
        return _number(features["values"].get(name), "measured esports feature")

    allowed = {*(f"observed_{kind}_count_{days}d" for kind in ("series", "map") for days in (1, 3, 7)),
               "observed_recovery_exact_hours", "observed_recovery_minimum_hours"}
    x = []
    prefix = f"{reference['scope']['title_id']}/{reference['scope']['season_id']}/"
    for name in artifact["feature_names"]:
        if name.startswith("participation_delta/"):
            vocabulary = name.removeprefix("participation_delta/")
            if not vocabulary.startswith(prefix):
                raise ContextModelError("esports player vocabulary belongs to another title/season")
            native_identity(vocabulary[len(prefix):], "player")
            if available("participation_complete") != 1:
                raise ContextModelError("esports participation requires both complete native references")
            left, right = "participation_current/" + vocabulary, "participation_reference/" + vocabulary
        else:
            root = name.removesuffix("_delta")
            if not name.endswith("_delta") or root not in allowed:
                raise ContextModelError("unreviewed esports feature or medical/patch penalty")
            left, right = root + "_home", root + "_away"
            if "_count_" in root:
                for side in ("home", "away"):
                    if available(root + "_complete_" + side) != 1:
                        raise ContextModelError("observed esports count window is incomplete")
        value = available(name)
        if value != available(left) - available(right):
            raise ContextIntegrityError("esports signed feature does not match its measured components")
        if features["refs"][name] != sorted(set(features["refs"][left]) | set(features["refs"][right])):
            raise ContextIntegrityError("esports signed feature lost source component provenance")
        x.append(value)
    return original, features, artifact, event, np.array([x], dtype=float)


def _effect_values(original, features, artifact, event, x):
    delta = float(offset_delta(artifact["heads"]["winner"], x)[0])
    p = series_probability(original["params"]["p_a"], delta)
    params = deepcopy(original["params"]) if delta == 0 else {"p_a": p}
    markets = deepcopy(original["markets"]) if delta == 0 else {"series_winner_a": p, "series_winner_b": 1. - p}
    model_hash = digest({"version": COMPARISON_VERSION, "base_hash": digest(original), "event_hash": digest(event),
        "feature_hash": digest(features), "effect_hash": digest({"kind": "context-effect-v1", "payload": artifact})})
    return params, markets, model_hash


def validate_esports_comparison_reference(value, history_refs):
    require_object(value, {"schema", "kind", "original", "event", "features", "effect"}, label="esports comparison reference")
    if type(value["schema"]) is not int or value["schema"] != 1 or value["kind"] != COMPARISON_KIND:
        raise ContextContractError("unknown esports comparison contract")
    original, *_ = _prepare_effect(value["original"], value["features"], value["effect"], value["event"])
    if original["history_refs"] != history_refs:
        raise ContextIntegrityError("esports comparison changed its original source inventory")
    return deepcopy(value)


def validate_esports_comparison(base):
    ref = base["reference_weights"]
    prepared = _prepare_effect(ref["original"], ref["features"], ref["effect"], ref["event"])
    params, markets, model_hash = _effect_values(*prepared)
    if (base["version"] != COMPARISON_VERSION or base["event_key"] != prepared[0]["event_key"] or base["cutoff"] != prepared[0]["cutoff"]
        or base["params"] != params or base["markets"] != markets or base["model_hash"] != model_hash):
        raise ContextIntegrityError("esports comparison does not replay from actual original inputs")


def apply_esports_effect(base: dict, features: dict, artifact: dict, *, event: dict) -> dict:
    prepared = _prepare_effect(base, features, artifact, event)
    original, features, artifact, event, _ = prepared
    params, markets, model_hash = _effect_values(*prepared)
    return validate_base_distribution({**deepcopy(original), "version": COMPARISON_VERSION, "model_hash": model_hash,
        "params": params, "markets": markets, "reference_weights": {"schema": 1, "kind": COMPARISON_KIND,
            "original": original, "features": features, "effect": artifact, "event": event}})


def esports_context_result(base, features, effect_artifact, *, event, effect_hash, approval=None):
    """Explicit typed numerical fallback; no approval or hidden activation."""
    from context_snapshots import select_context_result
    require_object(effect_artifact, {"kind", "payload"}, label="actual A1 esports effect")
    require_digest(effect_hash)
    if effect_artifact["kind"] != "context-effect-v1" or digest(effect_artifact) != effect_hash:
        raise ContextIntegrityError("esports actual A1 effect identity differs")
    artifact = validate_effect_artifact(effect_artifact["payload"])
    original, event, features = validate_base_distribution(base), esports_event(event), validate_feature_vector(features)
    if features["reference_hash"] != esports_reference_hash(original, event, artifact["preprocessing_artifacts"]):
        raise ContextIntegrityError("esports fallback cannot reuse another original reference")
    try:
        comparison = apply_esports_effect(original, features, artifact, event=event)
        limitations = []
    except ContextModelError:
        comparison, limitations = None, ["esports-numerical-or-measured-comparison-unavailable"]
    return select_context_result(original, comparison, event=event, features=features, effect_artifact=effect_artifact,
        effect_hash=effect_hash, approval=approval, factor_roles={name: "applied" if name in artifact["feature_names"] else "not_applied" for name in features["values"]},
        factor_states=features["states"], limitations=limitations)
