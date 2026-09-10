"""Shared legacy BB/NHL results, not a B3/source/effect certification.

The existing worker owns collection and publication. Its two consumers read a
closed snapshot + prediction revision, with no numeric uncertainty invented.
No live-original A1 artifact, new database or model replay belongs here.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import fields
from datetime import date, datetime, timedelta, timezone
from functools import wraps
import hashlib
import json
import math
from pathlib import Path
from threading import Lock, RLock
from zoneinfo import ZoneInfo

SPORTS = ("basketball", "ice_hockey")
LABELS = {"basketball": "Basketball", "ice_hockey": "Eishockey"}
VIEW_KIND = "team-sports-baseline-view-v1"
BATCH_KIND = "team-sports-baseline-batch-v1"
UNCERTAINTY = "team-sports-research-unknown-boundary-v1"
_CURRENT = ContextVar("team_sports_baseline_owner", default=None)
_LOCKS, _LOCKS_GUARD = {}, Lock()


class BaselineIntegrityError(ValueError):
    """A known baseline revision is inconsistent, not source-unavailable."""


def _need(condition):
    if not condition:
        raise BaselineIntegrityError("invalid team-sports baseline binding")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _shape(value, names):
    _need(type(value) is dict and set(value) == set(names.split()))
    return value


def _clock(value):
    _need(type(value) in (str, datetime))
    try:
        clock = datetime.fromisoformat(value) if type(value) is str else value
        _need(clock.tzinfo is not None and clock.utcoffset() is not None)
        return clock.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise BaselineIntegrityError("invalid team-sports baseline clock") from exc


def _number(value, *, probability=False):
    return type(value) in (int, float) and math.isfinite(value) and (
        not probability or 0 <= value <= 1)


def _prediction(raw):
    from sports_prematch import PrematchPrediction, PrequentialEvaluation, MODEL_VERSION
    _need(type(raw) is dict and set(raw) == {f.name for f in fields(PrematchPrediction)})
    _need(raw["sport"] in SPORTS and raw["model_version"] == MODEL_VERSION
          and raw["evidence_stage"] == "RESEARCH" and raw["risk_probability"] is None)
    for name in ("p_home", "p_away", "p_home_regulation", "p_draw_regulation"):
        _need(raw[name] is None or _number(raw[name], probability=True))
    _need((raw["p_home"] is None) == (raw["p_away"] is None))
    if raw["p_home"] is not None:
        _need(float(raw["p_away"]).hex() == float(1 - raw["p_home"]).hex())
    for name in ("training_games", "home_games", "away_games"):
        _need(type(raw[name]) is int and raw[name] >= 0)
    _need(max(raw["home_games"], raw["away_games"]) <= raw["training_games"])
    for name in ("factors", "missing", "limitations"):
        _need(type(raw[name]) is list and all(type(s) is str and s for s in raw[name]))
    _need(type(raw["input_hash"]) is str and len(raw["input_hash"]) == 64
          and all(c in "0123456789abcdef" for c in raw["input_hash"]))
    evaluation = raw["evaluation"]
    _need(type(evaluation) is dict and set(evaluation) == {f.name for f in fields(PrequentialEvaluation)})
    _need(type(evaluation["count"]) is int and 0 <= evaluation["count"] <= 24
          and evaluation["method"] == PrequentialEvaluation().method)
    for name in ("brier_score", "baseline_brier_score", "log_loss"):
        _need(evaluation[name] is None or (_number(evaluation[name]) and evaluation[name] >= 0))
    _need(raw["market_contract"] == "match_winner_including_ot")
    values = deepcopy(raw)
    values["evaluation"] = PrequentialEvaluation(**evaluation)
    values["latest_result_observed_at"] = _clock(raw["latest_result_observed_at"]) if raw["latest_result_observed_at"] else None
    for name in ("factors", "missing", "limitations"):
        values[name] = tuple(values[name])
    return PrematchPrediction(**values)


def validate_view(value):
    """Closed lightweight consistency, NOT an independent original/source fit."""
    from riskobet_candidates import _project_research_prediction, MIN_RESEARCH_TEAM_GAMES, RISKOBET_POLICY_VERSION
    _shape(value, "schema kind sport event snapshot prediction digest")
    _need(type(value["schema"]) is int and value["schema"] == 1 and value["kind"] == VIEW_KIND)
    _need(value["digest"] == _digest({k: v for k, v in value.items() if k != "digest"}))
    event = _shape(value["event"], "provider provider_event_id home away home_id away_id competition starts_at source_observed_at")
    _need(all(type(event[name]) is str and event[name] for name in
              ("provider", "provider_event_id", "home", "away", "competition")))
    _need(all(type(event[name]) is str for name in ("home_id", "away_id")))
    _need(event["home"].casefold() != event["away"].casefold())
    prediction = _prediction(value["prediction"])
    _need(prediction.sport == value["sport"])
    snapshot = value["snapshot"]
    _need(type(snapshot) is dict and "context_ref" not in snapshot)
    cutoff = _clock(snapshot.get("input_cutoff_at"))
    _need(cutoff == _clock(snapshot.get("modeled_at")))
    start, observed = _clock(event["starts_at"]), _clock(event["source_observed_at"])
    _need(observed <= cutoff < start)
    _need(prediction.latest_result_observed_at is None or prediction.latest_result_observed_at <= cutoff)
    expected = _project_research_prediction(prediction, sport=value["sport"],
        **{k: event[k] for k in ("provider", "provider_event_id", "home", "away", "home_id", "away_id", "competition")},
        starts_at=start, source_observed_at=observed, model_time=cutoff, cutoff=cutoff,
        minimum_team_games=MIN_RESEARCH_TEAM_GAMES, policy_version=RISKOBET_POLICY_VERSION)
    _need(_json(expected.snapshot.to_dict()) == _json(snapshot))
    return expected


def _view(original, result):
    from riskobet_candidates import _clean_text, _research_source_observed_at
    event = original.raw_event
    snapshot = result.snapshot
    selected = dict(provider=_clean_text(event.get("provider") or event.get("source")),
        provider_event_id=_clean_text(event.get("provider_event_id", event.get("event_id", event.get("game_id", event.get("match_id", event.get("id")))))),
        home=_clean_text(event.get("home_team", event.get("team1"))),
        away=_clean_text(event.get("away_team", event.get("team2"))),
        home_id=_clean_text(event.get("home_team_id", event.get("team1_id"))),
        away_id=_clean_text(event.get("away_team_id", event.get("team2_id"))),
        competition=snapshot.competition, starts_at=snapshot.starts_at.isoformat(),
        source_observed_at=_research_source_observed_at(event, starts_at=snapshot.starts_at,
            as_of=original.as_of).isoformat())
    value = dict(schema=1, kind=VIEW_KIND, sport=original.sport, event=selected,
        snapshot=snapshot.to_dict(), prediction=json.loads(_json(original.prediction.to_dict())))
    value["digest"] = _digest(value)
    validate_view(value)
    return value


def validate_batch(value, sport):
    from ev_signal_sources import MAX_AUTOMATED_OTHER_CANDIDATES_PER_SPORT
    _shape(value, "schema kind sport target_date checked_at status errors entries digest")
    _need(type(value["schema"]) is int and value["schema"] == 1 and value["kind"] == BATCH_KIND
          and value["sport"] == sport and sport in SPORTS)
    _need(value["digest"] == _digest({k: v for k, v in value.items() if k != "digest"}))
    _need(type(value["target_date"]) is str and date.fromisoformat(value["target_date"]).isoformat() == value["target_date"])
    checked = _clock(value["checked_at"])
    _need(value["status"] in ("completed", "partial", "failed"))
    _need(type(value["errors"]) is list and all(type(s) is str and s for s in value["errors"]))
    _need(bool(value["errors"]) == (value["status"] != "completed"))
    _need(type(value["entries"]) is list and len(value["entries"]) <= MAX_AUTOMATED_OTHER_CANDIDATES_PER_SPORT)
    seen = set()
    for entry in value["entries"]:
        result = validate_view(entry)
        _need(entry["sport"] == sport and result.snapshot.modeled_at <= checked
              and result.snapshot.event_key not in seen)
        _need(result.snapshot.starts_at.astimezone(ZoneInfo("Europe/Zurich")).date().isoformat() == value["target_date"])
        seen.add(result.snapshot.event_key)
    _need(value["status"] != "failed" or not value["entries"])
    return value


def batch_due(value, sport, *, now, target_date):
    if value is None:
        return True
    validate_batch(value, sport)
    elapsed = _clock(now) - _clock(value["checked_at"])
    _need(elapsed >= timedelta(0))
    return value["target_date"] != target_date.isoformat() or value["status"] != "completed" or elapsed >= timedelta(hours=6)


def _current_native_event(raw, sport, components, lookup):
    from context_sources.team_sports_binding import _resolve_input
    binding, latest = _resolve_input(raw, index=None, sport=sport, components=components, lookup=lookup)
    if binding["lineage_refs"] and (binding["current_state"] in ("conflicting", "unknown")
        or any(s.endswith("conflict") or s == "native-original-revision-superseded" for s in binding["reasons"])):
        return False
    return latest is None or latest["payload"]["projection"]["status"] in ("scheduled", "not_completed")


def current_batch(value, *, now):
    """One current selection for both views; historical bytes are untouched."""
    from riskobet_automation import RiskSourceBatch
    from context_sources.team_sports_status import team_sport_observations_as_of
    from context_sources.team_sports_binding import _components
    import runtime_paths
    validate_batch(value, value["sport"])
    components, lookup = _components(team_sport_observations_as_of(runtime_paths.CONTEXT_MODEL_DB_PATH, cutoff=_clock(now)))
    entries, results = [], []
    for entry in value["entries"]:
        event = entry["event"]
        raw = dict(provider=event["provider"], provider_event_id=event["provider_event_id"],
            competition=event["competition"], starts_at=event["starts_at"],
            home_team_id=event["home_id"], away_team_id=event["away_id"], status="scheduled")
        if (_clock(event["starts_at"]) > _clock(now)
            and _current_native_event(raw, value["sport"], components, lookup)):
            entries.append(entry)
            results.append(validate_view(entry))
    return entries, RiskSourceBatch(sport=value["sport"], snapshots=tuple(r.snapshot for r in results),
        candidates=tuple(c for r in results for c in r.candidates), errors=tuple(value["errors"]))


def baseline_row(value):
    """One main winner selection; opposite scenarios stay on RisikoBet."""
    from betting_math import BETTING_POLICY_VERSION
    result = validate_view(value)
    p, event, snapshot = value["prediction"], value["event"], result.snapshot
    if p["p_home"] is None or p["missing"] or snapshot.missing_core_data:
        return None
    side = "home" if p["p_home"] >= p["p_away"] else "away"
    selection = event[side]
    key = "wettfinder-baseline-" + snapshot.snapshot_id.removeprefix("snapshot_")
    return dict(key=key, candidate_id=key, sport=LABELS[value["sport"]], event=snapshot.event_label,
        event_identity=snapshot.event_key, label=f"{snapshot.event_label}: {selection}",
        market="Sieger inklusive Verlängerung", market_key="match_winner_including_ot",
        selection=selection, selection_key=side, competitor_a=event["home"], competitor_b=event["away"],
        selected_competitor=selection, competition=event["competition"],
        probability=p["p_" + side], probability_haircut=None, conservative_probability=None,
        minimum_odds=None, uncertainty_contract=UNCERTAINTY, baseline_view=deepcopy(value),
        evidence_stage="RESEARCH", policy_version=BETTING_POLICY_VERSION,
        modeled_at=snapshot.modeled_at.isoformat(), input_cutoff_at=snapshot.input_cutoff_at.isoformat(),
        model_version=snapshot.model_version, fixture_source=event["provider"],
        provider_event_id=event["provider_event_id"], competitor_a_id=event["home_id"] or None,
        competitor_b_id=event["away_id"] or None, scheduled_start=snapshot.starts_at.isoformat(),
        status="PRICE_REQUIRED", reference_price_status="UNAVAILABLE", source=value["sport"] + "_baseline",
        detail=f"Ergebnisbasiertes Modell aus {p['training_games']} abgeschlossenen Spielen.",
        context_summary=None)


def validate_row(row):
    _need(type(row) is dict and row.get("uncertainty_contract") == UNCERTAINTY)
    expected = baseline_row(row.get("baseline_view"))
    _need(expected is not None)
    expected["status"] = row.get("status")
    _need(expected["status"] in ("PRICE_REQUIRED", "MODEL_SELECTION"))
    _need(_json(expected) == _json(row))
    return row


def baseline_signal(row):
    from ev_signal_sources import ModelSignal
    validate_row(row)
    names = ("key", "label", "probability", "probability_haircut", "evidence_stage", "policy_version", "detail",
        "scheduled_start", "minimum_odds", "source", "sport", "market", "market_key", "selection", "candidate_id",
        "competitor_a", "competitor_b", "selected_competitor", "competition", "modeled_at", "input_cutoff_at", "model_version",
        "fixture_source", "provider_event_id", "competitor_a_id", "competitor_b_id", "uncertainty_contract", "baseline_view")
    return ModelSignal(**{name: deepcopy(row[name]) for name in names}, event_label=row["event"])


def validate_signal(signal):
    expected = baseline_row(signal.baseline_view)
    _need(expected is not None and signal.uncertainty_contract == UNCERTAINTY
          and signal.probability_haircut is None and signal.minimum_odds is None
          and signal.context_ref is None and signal.evidence_stage == "RESEARCH")
    for name in ("key", "label", "probability", "policy_version", "detail", "scheduled_start", "sport", "market",
        "market_key", "selection", "source", "candidate_id", "competitor_a", "competitor_b", "selected_competitor",
        "competition", "modeled_at", "input_cutoff_at", "model_version", "fixture_source", "provider_event_id",
        "competitor_a_id", "competitor_b_id"):
        _need(_json(getattr(signal, name)) == _json(expected[name]))
    _need(signal.event_label == expected["event"] and signal.statistical_release_passed is not True)


@contextmanager
def source_owner(clock):
    _need(_CURRENT.get() is None)
    owner = dict(clock=clock, entries=[], captured=False, errors=[])
    token = _CURRENT.set(owner)
    try:
        yield owner
    finally:
        _CURRENT.reset(token)


def active_owner():
    return _CURRENT.get()


def _unique_events(events):
    """Collapse identical sporting inputs before any target computation."""
    from riskobet_candidates import _clean_text
    inputs = "sport provider source competition_id league_id competition league tournament provider_event_id event_id game_id match_id id home_team_id away_team_id team1_id team2_id home_team away_team team1 team2 starts_at start_time scheduled_at source_observed_at fetched_at season game_type neutral_site context_rule_version context_rules status".split()
    seen, result = {}, []
    for event in events:
        if not isinstance(event, dict):
            result.append(event)
            continue
        key = (_clean_text(event.get("provider") or event.get("source")),
            _clean_text(event.get("provider_event_id", event.get("event_id", event.get("game_id", event.get("match_id", event.get("id")))))))
        projection = {key: event[key] for key in inputs if key in event}
        if key in seen:
            _need(_json(projection) == _json(seen[key]))
            continue
        seen[key] = projection
        result.append(event)
    return result


def acquire_baseline(sport, target_date, history_loader):
    """Only existing requests, followed by receipt flush and one calculation."""
    from scanners.basketball_scanner import BasketballScanner
    from context_sources.team_sports_capture import capture_team_sports_worker
    from context_sources.team_sports_status import team_sport_observations_as_of
    from context_sources.team_sports_binding import _components
    from riskobet_automation import RiskSourceBatch
    from riskobet_candidates import adapt_basketball_research, adapt_ice_hockey_research
    from wettfinder_automation import _scanner_completed_history_loader, _causal_completed_history, _parse_iso
    import runtime_paths
    owner = active_owner()
    _need(owner is not None and sport in SPORTS)
    owner["captured"] = True
    scanner = BasketballScanner()
    with capture_team_sports_worker() as capture:
        events = (scanner.get_upcoming_games("All", target_date, target_date) if sport == "basketball"
                  else scanner.get_upcoming_nhl_games(target_date, target_date))
        schedule_time = _clock(owner["clock"]())
        events = [raw for raw in events if isinstance(raw, dict) and
            (start := _parse_iso(raw.get("starts_at") or raw.get("start_time") or raw.get("scheduled_at"))) is not None
            and start > schedule_time]
        loader = history_loader or _scanner_completed_history_loader(scanner, sport, target_date=target_date)
        history = tuple(loader(sport=sport, events=tuple(events), as_of=None)) if loader is not None and events else ()
    decision = _clock(owner["clock"]())
    pool = team_sport_observations_as_of(runtime_paths.CONTEXT_MODEL_DB_PATH, cutoff=decision)
    # A received correction cannot be hidden behind an earlier decision clock.
    _need(all(_clock(received) <= decision for received, _ in capture.pending))
    history = _causal_completed_history(history, as_of=decision)
    components, lookup = _components(pool)
    errors = ["source_partial" for error in scanner.errors.values() if error]
    coverage = getattr(loader, "coverage", {})
    if coverage and coverage.get("status") != "complete":
        errors.append("history_partial")
    if capture.report()["issues"]:
        errors.append("native_status_partial")
    adapter = adapt_basketball_research if sport == "basketball" else adapt_ice_hockey_research
    results, seen = [], set()
    for raw in _unique_events(events):
        if not isinstance(raw, dict):
            errors.append("invalid_event")
            continue
        event = dict(raw)
        start = _parse_iso(event.get("starts_at") or event.get("start_time") or event.get("scheduled_at"))
        if start is None or start <= decision:
            continue
        if not _current_native_event(event, sport, components, lookup):
            continue
        if event.get("status", "scheduled") not in ("scheduled", "upcoming", "FUT", "PRE", "not_started"):
            continue
        if event.get("source_observed_at") in (None, "") and event.get("fetched_at") in (None, ""):
            event["source_observed_at"] = decision.isoformat()
        originals = []
        result = adapter(event, history, modeled_at=decision, original_capture=originals.append)
        _need(len(originals) == 1)
        view = _view(originals[0], result)
        if result.snapshot.event_key in seen:
            _need(any(_json(existing) == _json(view) for existing in owner["entries"]))
            continue
        seen.add(result.snapshot.event_key)
        owner["entries"].append(view)
        results.append(result)
    return RiskSourceBatch(sport=sport, snapshots=tuple(r.snapshot for r in results),
        candidates=tuple(c for r in results for c in r.candidates), errors=tuple(sorted(set(errors))))


def collected_batch(owner, sport, target_date, result):
    if not owner["captured"]:
        return None
    from riskobet_automation import RiskSourceBatch
    _need(isinstance(result, RiskSourceBatch) and result.sport == sport)
    expected = [validate_view(entry) for entry in owner["entries"]]
    _need(_json([r.snapshot.to_dict() for r in expected]) == _json([s.to_dict() for s in result.snapshots]))
    _need(_json([c.to_dict() for r in expected for c in r.candidates]) == _json([c.to_dict() for c in result.candidates]))
    value = dict(schema=1, kind=BATCH_KIND, sport=sport, target_date=target_date.isoformat(),
        checked_at=_clock(owner["clock"]()).isoformat(), status="partial" if result.errors else "completed",
        errors=list(result.errors), entries=deepcopy(owner["entries"]))
    value["digest"] = _digest(value)
    return validate_batch(value, sport)


def failed_batch(sport, target_date, now, *, previous=None):
    entries = []
    if previous is not None:
        validate_batch(previous, sport)
        _need(_clock(previous["checked_at"]) <= _clock(now))
        if previous["target_date"] == target_date.isoformat():
            entries = deepcopy(previous["entries"])
    value = dict(schema=1, kind=BATCH_KIND, sport=sport, target_date=target_date.isoformat(),
        checked_at=_clock(now).isoformat(), status="partial" if entries else "failed",
        errors=["source_failed"], entries=entries)
    value["digest"] = _digest(value)
    return validate_batch(value, sport)


def locked_worker(function):
    """Serialize read/acquire/publish together, including cross-process calls."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        from riskobet_store import _publication_lock
        from wettfinder_automation import STATE_PATH
        path = Path(kwargs.get("state_path", STATE_PATH)).resolve()
        with _LOCKS_GUARD:
            lock = _LOCKS.setdefault(str(path), RLock())
        with lock, _publication_lock(path):
            return function(*args, **kwargs)
    return wrapped
