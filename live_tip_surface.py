"""Join the visible Live detail to its source snapshot; never turn scan rows into tips."""
import logging
import sqlite3

from football_recommendations import LIVE_MAX_AGE_SECONDS


LOGGER = logging.getLogger(__name__)


def _ordinary_fields(candidate, row):
    home, away = row.get("home_team"), row.get("away_team")
    if "live_comparison" in row:
        from live_market_comparison import market_open, selection_labels
        info = row["live_comparison"]
        if not isinstance(info, dict):
            return None
        market, side = info.get("market"), info.get("side")
        if (not all(isinstance(v, str) and v.strip() for v in (market, side, home, away, info.get("reason")))
                or home == away):
            return None
        labels = selection_labels(market, side, home, away)
        # Matching the two display strings to each other is not enough: both
        # might describe a different side or line than the internal receipt.
        if (labels != (candidate.market, candidate.selection)
                or labels != (info.get("market_label"), info.get("label"))
                or not market_open(market, side, row.get("home_score"), row.get("away_score"))):
            return None
    elif candidate.market == "Noch ein Tor" and candidate.selection == "Mindestens 1 weiteres Tor":
        market, side = "next_goal", "any"
    elif candidate.market == "BTTS" and candidate.selection == "Beide Teams treffen":
        market, side = "btts", "yes"
    elif candidate.market == "Team trifft noch" and home and away and home != away:
        market = "team_scores"
        side = {f"{home} trifft noch": "home", f"{away} trifft noch": "away"}.get(candidate.selection)
        if side is None:
            return None
    else:
        return None
    clock = row.get("phase_data") or {}
    if "extra" not in clock:
        return None  # an old snapshot never proves that there was no injury time
    return dict(fixture_id=row.get("fixture_id"), market=market, side=side,
                minute=row.get("minute"), phase=clock.get("status"), extra=clock["extra"],
                home_goals=row.get("home_score"), away_goals=row.get("away_score"),
                home_id=row.get("home_team_id"), away_id=row.get("away_team_id"))


def _red_fields(candidate, row):
    card = row.get("card") or {}
    match = card.get("match") or {}
    fixture = match.get("fixture") or {}
    clock = fixture.get("status") or {}
    teams = match.get("teams") or {}
    goals = match.get("goals") or {}
    home_id = (teams.get("home") or {}).get("id")
    away_id = (teams.get("away") or {}).get("id")
    if (candidate.market != "Nächstes Tor" or row.get("error")
            or clock.get("elapsed") != row.get("prediction_minute")
            or home_id is None or away_id is None or home_id == away_id):
        return None
    red_side = {home_id: "home", away_id: "away"}.get(card.get("team_id"))
    if red_side is None or red_side != row.get("red_side"):
        return None
    # The selection label is the exact outcome shown by red_card_candidate.
    # Bind the card team by its native ID (not by club-name similarity).
    labels = (card.get("team"), row.get("opponent"), "Kein weiteres Tor")
    if not all(labels) or len(set(labels)) != 3 or candidate.selection not in labels:
        return None
    side = dict(zip(labels, (red_side, "away" if red_side == "home" else "home", "none")))[candidate.selection]
    return dict(fixture_id=fixture.get("id"), market="red_next", side=side,
                minute=clock.get("elapsed"), phase=clock.get("short"), extra=clock.get("extra"),
                home_goals=goals.get("home"), away_goals=goals.get("away"),
                home_id=home_id, away_id=away_id)


def live_snapshot_fields(candidate, row, *, red):
    """Identify the outcome and baseline used both for display and its receipt."""
    if red and "live_comparison" in row:
        return None
    return (_red_fields if red else _ordinary_fields)(candidate, row)


def record_visible_analysis(candidate, row, *, snapshot_at, age_seconds, red=False):
    """Record the rendered detail for internal audit, without changing its UI."""
    if not candidate.forecast_available:
        return
    if age_seconds is None or not 0 <= age_seconds <= LIVE_MAX_AGE_SECONDS:
        return
    fields = live_snapshot_fields(candidate, row, red=red)
    if fields is None or not row.get("model_version"):
        return
    from live_market_comparison import LIVE_ONLY_MODEL_VERSION
    from live_tip_ledger import record_displayed_live_tip
    if row["model_version"] == LIVE_ONLY_MODEL_VERSION:
        if red or "live_comparison" not in row:
            return
        from live_tip_ledger import LIVE_ONLY_COMPARISON_POLICY_VERSION
        fields["policy_version"] = LIVE_ONLY_COMPARISON_POLICY_VERSION
    elif "live_comparison" in row:
        from live_tip_ledger import COMPARISON_POLICY_VERSION
        fields["policy_version"] = COMPARISON_POLICY_VERSION
    try:
        record_displayed_live_tip(**fields, probability=candidate.model_probability / 100.,
                                  snapshot_at=snapshot_at, model_version=row["model_version"])
    except ValueError:
        return
    except (OSError, sqlite3.Error) as exc:
        # Exception details may include internal filesystem paths.
        LOGGER.warning("Live audit write failed (%s)", type(exc).__name__)
