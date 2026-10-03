"""Small publication receipts for selected UI inventories, never model pools.

The UI calls this only after its shared selection and known-price floor. A
receipt proves that the selections were made available in that surface; it
does not claim a customer read them or placed a bet. No account state, model
context, history lists or API responses are copied here.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
from typing import Mapping

from runtime_paths import RUNTIME_STATE_DIR

DEFAULT_HISTORY_DB = RUNTIME_STATE_DIR / "consumer_tips.db"
DEFAULT_FORECAST_DB = RUNTIME_STATE_DIR / "forecast_evidence.db"
_LOG = logging.getLogger(__name__)
_FIELDS = (
    "key", "candidate_id", "sport", "market_key", "selection", "selection_key",
    "selected_competitor", "scheduled_start", "starts_at", "probability",
    "model_probability", "modeled_at", "input_cutoff_at", "model_version",
    "policy_version", "fixture_id", "fixture_source", "provider_event_id",
    "quote_provider_event_id", "competitor_a", "competitor_b",
    "competitor_a_id", "competitor_b_id", "home_team", "away_team",
    "home_team_id", "away_team_id", "home_id", "away_id", "source",
    "event_label", "competition", "snapshot_id", "reference_quote",
)


def _get(row, name, default=None):
    return row.get(name, default) if isinstance(row, Mapping) else getattr(row, name, default)


def _clock(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("publication clock must be timezone-aware")
    return value.astimezone(timezone.utc)


def compact_signal_row(row, *, featured_role="catalogue"):
    """Copy an allowlist, not dataclasses.asdict's recursive context payload."""
    data = {name: _get(row, name) for name in _FIELDS if _get(row, name) is not None}
    sport = str(data.get("sport", "")).strip().casefold().replace("ß", "ss")
    if sport in {"fussball", "football"} and data.get("fixture_id"):
        data["event_key"] = f"football:{data['fixture_id']}"
    elif sport in {"tennis", "e-sport", "esports"}:
        provider = str(data.get("fixture_source", "")).strip().casefold()
        native_id = str(data.get("provider_event_id", "")).strip()
        allowed = {"tennis": {"espn", "sofascore"}, "e-sport": {"pandascore"}, "esports": {"pandascore"}}
        if native_id and provider in allowed[sport]:
            from riskobet_domain import stable_event_key
            data["event_key"] = stable_event_key("tennis" if sport == "tennis" else "esports", provider, native_id)
    # RiskBet's event/snapshot IDs already belong to its frozen domain.
    explicit_event = _get(row, "event_key") or _get(row, "event_identity")
    if explicit_event:
        data["event_key"] = explicit_event
    data["featured_role"] = featured_role
    return data


def _matching_forecast_id(connection, row, as_of):
    """Bind an existing immutable revision, never a name-only or winner join."""
    from forecast_evidence import _hash
    event, market = row.get("event_key"), row.get("market_key")
    selection = row.get("selection_key") or row.get("selected_competitor") or row.get("selection")
    candidate = row.get("candidate_id") or row.get("key")
    if any(row.get(alias) is not None and row.get(native) is not None and
           str(row[alias]) != str(row[native])
           for alias, native in (("home_team_id", "home_id"), ("away_team_id", "away_id"))):
        return None
    if not all((event, market, selection, candidate, row.get("modeled_at"), row.get("input_cutoff_at"))):
        return None
    start = _clock(row.get("scheduled_start") or row.get("starts_at"))
    modeled, cutoff = _clock(row["modeled_at"]), _clock(row["input_cutoff_at"])
    probability = row.get("probability", row.get("model_probability"))
    records = connection.execute(
        "SELECT * FROM forecast_rows WHERE event_key=? AND market_key=? AND selection=? "
        "AND starts_at=? AND decision_at<=? ORDER BY decision_at,forecast_id LIMIT 101",
        (event, market, selection, start.isoformat(), as_of.isoformat()),
    ).fetchall()
    if len(records) > 100:
        return None  # A capped revision search is not an honest exact binding.
    for record in records:
        payload = json.loads(record["payload_json"])
        if _hash({"run_id": record["run_id"], "forecast": payload}) != record["forecast_id"]:
            continue
        if any(payload.get(name) != record[name] for name in (
            "event_key", "sport", "market_key", "selection", "starts_at", "decision_at", "model_version", "policy_version",
        )):
            continue
        from selection_performance import _forecast
        run = connection.execute('SELECT * FROM forecast_runs WHERE run_id=?', (record['run_id'],)).fetchone()
        if run is None:
            continue
        try:
            _forecast(dict(record), dict(run))
        except (ValueError, TypeError, KeyError):
            continue
        if (payload.get("candidate_id") != candidate or payload.get("probability") != probability
                or not payload.get("causal_provenance_complete")
                or _clock(payload.get("modeled_at")) != modeled
                or _clock(payload.get("input_cutoff_at")) != cutoff
                or not cutoff <= modeled <= _clock(record["decision_at"]) < start
                or not _clock(payload.get("recorded_at")) <= as_of < start):
            continue
        if any(row.get(name) and row[name] != payload.get(name) for name in ("model_version", "policy_version")):
            continue
        identity = payload.get("quote_identity") or {}
        names = ("fixture_id", "fixture_source", "provider_event_id", "competitor_a", "competitor_b",
                 "selected_competitor", "home_team", "away_team", "competitor_a_id", "competitor_b_id")
        if any(row.get(name) is not None and str(row[name]).casefold() != str(identity.get(name)).casefold() for name in names):
            continue
        # Provider role IDs are not interchangeable after participant changes.
        if any((row.get(alias) is not None or row.get(native) is not None) and
               str(row.get(alias) if row.get(alias) is not None else row.get(native)) !=
               str(identity.get(native) if identity.get(native) is not None else identity.get(alias))
               for alias, native in (("home_team_id", "home_id"), ("away_team_id", "away_id"))):
            continue
        return record["forecast_id"]
    return None


def bind_forecast_ids(rows, *, as_of, db_path=DEFAULT_FORECAST_DB):
    """Read-only optional linkage; missing evidence remains an explicit gap."""
    instant, path = _clock(as_of), Path(db_path)
    bound = [{key: value for key, value in row.items() if key != 'forecast_id'} for row in rows]
    if not path.is_file() or not bound:
        return bound
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.5)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            for row in bound:
                forecast_id = _matching_forecast_id(connection, row, instant)
                if forecast_id:
                    row["forecast_id"] = forecast_id
    except (OSError, sqlite3.Error, TypeError, ValueError, KeyError):
        _LOG.warning("Tip history: existing forecast linkage unavailable; no results inferred")
    return bound


def record_selected_tips(surface, rows, *, as_of, source_run_id=None, policy_version=None,
                         db_path=None, forecast_db_path=None):
    """Best-effort receipt, with failures logged internally, never user prose."""
    from consumer_tip_history import record_tip_publication
    try:
        selected = bind_forecast_ids(rows, as_of=as_of, db_path=forecast_db_path or DEFAULT_FORECAST_DB)
        result = record_tip_publication(db_path or DEFAULT_HISTORY_DB, surface=surface,
            rows=selected, as_of=as_of, source_run_id=source_run_id, policy_version=policy_version)
    except (OSError, sqlite3.Error, TypeError, ValueError, KeyError):
        result = {'status': 'unavailable', 'recorded_tips': 0, 'skipped_tips': 0}
    if result.get("status") not in {"recorded", "unchanged"} or result.get("skipped_tips"):
        _LOG.warning("Tip publication receipt incomplete: surface=%s status=%s stored=%s skipped=%s",
                     surface, result.get("status"), result.get("recorded_tips"), result.get("skipped_tips"))
    return result


def record_signal_catalog(surface, signals, *, as_of, featured_keys=(), source_run_id=None,
                          policy_version=None, db_path=None, forecast_db_path=None):
    featured = set(featured_keys)
    rows = [compact_signal_row(signal, featured_role="featured" if _get(signal, "key") in featured else "catalogue")
            for signal in signals]
    return record_selected_tips(surface, rows, as_of=as_of, source_run_id=source_run_id,
        policy_version=policy_version, db_path=db_path, forecast_db_path=forecast_db_path)


def record_riskobet_catalog(catalog, candidates, snapshots, *, as_of, source_run_id=None,
                           db_path=None, forecast_db_path=None):
    """Record selected frozen scenarios, not rejected or hidden run candidates.

    Model metadata comes from that candidate's exact frozen snapshot. Current
    stage changes and private manually entered quotes are never copied.
    """
    featured = {card.candidate_id for card in catalog.featured}
    rows = []
    for card in catalog.cards:
        candidate = candidates[card.candidate_id]
        snapshot = snapshots[candidate.snapshot_id]
        row = compact_signal_row(candidate,
            featured_role="featured" if card.candidate_id in featured else "catalogue")
        row.update(selection=candidate.selection_label, starts_at=candidate.starts_at,
                   modeled_at=snapshot.modeled_at, input_cutoff_at=snapshot.input_cutoff_at,
                   model_version=snapshot.model_version)
        rows.append(row)
    return record_selected_tips("riskobet_catalogue", rows, as_of=as_of,
        source_run_id=source_run_id, db_path=db_path, forecast_db_path=forecast_db_path)


def record_automatic_publication(state_path, *, as_of=None, db_path=None, forecast_db_path=None):
    """Archive the default available inventory after the normal worker publishes.

    No customer visit or account-specific ready-to-bet plan is implied. This
    reads the already written model artifact and never calls a data provider.
    """
    from ev_signal_sources import automated_wettfinder_snapshot
    from wettfinder_surface import build_wettfinder_card, compose_wettfinder_catalog
    from daily3_selection import daily3_choices, POLICY_VERSION
    try:
        instant = _clock(as_of or datetime.now(timezone.utc))
        snapshot = automated_wettfinder_snapshot(state_path, now=instant)
        if snapshot.status is None:
            return {'status': 'source_unavailable'}
        signals = {signal.key: signal for signal in snapshot.forecasts}
        cards = [build_wettfinder_card(signal, quote=signal.reference_quote, now=instant)
                 for signal in snapshot.forecasts]
        catalog = compose_wettfinder_catalog(cards, sport_filter='Alle')
        source = snapshot.status.generated_at.isoformat()
        automatic = record_signal_catalog('wettfinder_default_inventory',
            (signals[card.key] for card in (*catalog.featured, *catalog.additional)),
            as_of=instant, featured_keys=(card.key for card in catalog.featured),
            source_run_id=source, db_path=db_path, forecast_db_path=forecast_db_path)
        daily = record_signal_catalog('daily3_default_plan',
            (choice.signal for choice in daily3_choices(snapshot.forecasts, now=instant)),
            as_of=instant, source_run_id=source, policy_version=POLICY_VERSION,
            db_path=db_path, forecast_db_path=forecast_db_path)
        complete = all(item.get('status') in {'recorded', 'unchanged'}
                       and not item.get('skipped_tips') for item in (automatic, daily))
        return {'status': 'completed' if complete else 'partial', 'automatic': automatic, 'daily3': daily}
    except (OSError, sqlite3.Error, TypeError, ValueError, KeyError):
        _LOG.warning('Default selection inventory could not be archived; model artifact unchanged')
        return {'status': 'unavailable'}
