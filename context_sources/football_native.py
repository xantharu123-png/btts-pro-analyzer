"""Join owning API receipts to exact BASE inputs without CSV identity guesses.

Input is internal material from ChallengeDataProvider. A public content hash
is not authentication of an arbitrary provider/user claim. D1 must load actual
secured receipts; this pure transport builder never supplies archive proof or
new quality approval, and cannot make late data available before its receipt.
"""
from __future__ import annotations

from datetime import datetime

from challenge_engine import football_base_history_record
from context_models.contracts import (
    ContextContractError, canonical_timestamp, digest, require_object,
)
from context_sources.football import _detail_event, normalize_football_context

_FIXED = ("fixture_id", "scheduled_start", "league_id", "season", "home_id", "away_id", "goals_home", "goals_away")


def _positive(value):
    if type(value) is not int or value <= 0:
        raise ContextContractError("native evidence requires actual positive integer identities")
    return value


def _material(receipt):
    require_object(receipt, {"detail", "observed_at"}, label="owning native fixture receipt")
    observed = canonical_timestamp(receipt["observed_at"])
    detail = receipt["detail"]
    try:
        event = _detail_event(detail)
        record = football_base_history_record(detail)
        for name in ("fixture_id", "league_id", "season", "home_id", "away_id"):
            _positive(record[name])
        for side in ("home", "away"):
            goal = detail["goals"][side]
            if goal is not None and (type(goal) is not int or goal < 0):
                raise ContextContractError("native result cannot coerce a score")
        records = normalize_football_context(event, injuries=[], lineups=[], appearances=[detail],
                                             observed_at=datetime.fromisoformat(observed))
        appearances = [{"fixture_id": record["fixture_id"],
                        "team_id": int(row["payload"]["team_id"].rsplit(":", 1)[1]),
                        "player_id": int(row["subject_id"].rsplit(":", 1)[1]),
                        "minutes": row["payload"]["minutes"], "started": row["payload"]["started"],
                        "role": row["payload"]["role"]}
                       for row in records if row["kind"] == "appearance" and row["subject_id"].startswith("api-football:player:")]
    except (KeyError, TypeError, OverflowError) as exc:
        raise ContextContractError("native fixture material is incomplete") from exc
    return {"schema": 1, "source": "api-football", "source_schema": "fixtures-v3",
            "observed_at": observed, **{key: record[key] for key in _FIXED},
            "appearances": sorted(appearances, key=lambda row: (row["team_id"], row["player_id"]))}


def football_native_provenance(baseline_fixtures: tuple[dict, ...], native_receipts: tuple[dict, ...], *, decision_at: datetime) -> dict:
    """Bind only causal, unambiguous, exactly matching native baseline rows.

    Native team/event/player linkage is NOT complete regulation exposure. Late,
    conflicting, CSV, missing or mismatched evidence leaves that base row
    unresolved; it never suppresses a computable baseline or changes its rates.
    Same-event corrections are resolved BEFORE matching an older base result.
    """
    if type(baseline_fixtures) is not tuple or type(native_receipts) is not tuple:
        raise ContextContractError("native provenance requires fixed baseline and receipt tuples")
    decision = canonical_timestamp(decision_at)
    latest = {}
    for receipt in native_receipts:
        require_object(receipt, {"detail", "observed_at"}, label="owning native fixture receipt")
        observed = canonical_timestamp(receipt["observed_at"])
        if observed > decision:
            continue
        material = _material(receipt)
        identity = material["fixture_id"]
        previous = latest.get(identity)
        if previous is None or observed > previous[0]["observed_at"]:
            latest[identity] = [material]
        elif observed == previous[0]["observed_at"] and digest(material) not in {digest(row) for row in previous}:
            previous.append(material)
    evidence = {}
    for fixture in baseline_fixtures:
        base_record = football_base_history_record(fixture)
        if base_record["source_marker"] not in {"unresolved", "api-football", "api-football-ft-tail"}:
            continue
        matches = latest.get(base_record["fixture_id"], [])
        if len(matches) != 1 or any(matches[0][key] != base_record[key] for key in _FIXED):
            continue
        reference = digest(base_record)
        envelope = {"kind": "football-base-native-evidence-v1", "payload": {**matches[0], "record_hash": reference}}
        evidence[reference] = {"digest": digest(envelope), **envelope}
    return {"schema": 1, "decision_at": decision, "records": {key: evidence[key] for key in sorted(evidence)}}
