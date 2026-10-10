"""The daily tennis batch checks late fixtures too, without model-price coupling."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from config_loader import AppConfig
import market_consensus as markets
from odds_api_client import request_cost
import wettfinder_automation as automation
from test_market_consensus import _gea_zhang_quote_fixture


NOW = datetime(2030, 9, 30, 2, tzinfo=timezone.utc)


def fixtures(count=16):
    rows, events = [], []
    for index in range(count):
        row, event = _gea_zhang_quote_fixture(NOW)
        first, second = f"Player {index} First", f"Player {index} Second"
        if index == 14:
            first, second = "Carlos Alcaraz", "Juan Manuel Cerundolo"
        start = (NOW + timedelta(hours=2, minutes=index * 10)).isoformat()
        row.update(
            key=f"tennis-{index}", candidate_id=f"tennis-{index}",
            event=f"{first} vs {second}", event_identity=f"event-{index}",
            competitor_a=first, competitor_b=second, selected_competitor=first,
            scheduled_start=start, fixture_source="ESPN", provider_event_id=str(1000 + index),
            probability=.9235 if index == 14 else .7, conservative_probability=.6,
            probability_haircut=.3235 if index == 14 else .1,
            evidence_stage="SHADOW", status="MODEL_SELECTION",
        )
        event.update(id=f"price-event-{index}", home_team=first, away_team=second,
                     commence_time=start)
        event["bookmakers"][0]["markets"][0]["outcomes"] = [
            {"name": first, "price": 1.02 if index == 14 else 1.5},
            {"name": second, "price": 15.0 if index == 14 else 2.7},
        ]
        rows.append(row)
        events.append(event)
    return rows, events


def test_tennis_price_pool_does_not_skip_fifteenth_fixture():
    rows, _ = fixtures()
    before = deepcopy(rows)
    selected = automation._tennis_price_check_candidates(
        rows, now=NOW, target_date=NOW.date(), previous_checks={},
    )
    assert len(selected) == 16
    assert selected[14]["selected_competitor"] == "Carlos Alcaraz"
    assert rows == before
    assert all(row["status"] == "PRICE_REQUIRED" for row in selected)


def test_single_sport_batch_prices_all_sixteen_and_filters_exact_alcaraz_price(tmp_path, monkeypatch):
    rows, events = fixtures()
    calls = []

    def provider(path, _key, **kwargs):
        calls.append((path, kwargs.get("params", {})))
        if path == "sports/":
            return [{"key": "tennis_atp_china_open", "active": True}], None
        if path.endswith("/events"):
            return events, None
        assert set(kwargs["params"]["eventIds"].split(",")) == {event["id"] for event in events}
        return events, None

    monkeypatch.setattr(markets, "_odds_api_json", provider)
    path = tmp_path / "wettfinder.json"
    path.write_text(json.dumps({"model_candidates": rows, "price_check_attempts": {}}))
    summary = automation.refresh_prices_only(
        state_path=path, config=AppConfig(odds_api_key="dummy"), now=NOW, quote_sport="tennis",
    )
    saved = json.loads(path.read_text())
    assert summary["checked"] == summary["quotes"] == 16
    assert summary["errors"] == 0
    assert len(calls) == 3  # Free sports/events discovery, exactly one paid price batch.
    assert sum(request_cost(p.rstrip("/"), params) for p, params in calls) == 1
    alcaraz = saved["model_candidates"][14]
    assert alcaraz["reference_quote"]["best_odds"] == 1.02
    assert markets.quote_below_publication_floor(alcaraz["reference_quote"], candidate=alcaraz, now=NOW)
    assert not markets.quote_below_publication_floor(
        saved["model_candidates"][0]["reference_quote"], candidate=saved["model_candidates"][0], now=NOW)
    assert all(after[field] == before[field] for before, after in zip(rows, saved["model_candidates"])
               for field in ("probability", "conservative_probability", "probability_haircut",
                             "selected_competitor", "scheduled_start"))
    assert 0 < len(saved["tennis_price_observations"]) <= markets.TENNIS_PRICE_MAX_SIDES
    assert tuple(tmp_path.iterdir()) == (path,)


@pytest.mark.parametrize("change", ["already_checked", "started", "tomorrow", "wrong_market", "missing_player"])
def test_larger_tennis_batch_preserves_admission_and_cooldown(change):
    rows, _ = fixtures(1)
    checks = {}
    if change == "already_checked":
        checks[rows[0]["key"]] = (NOW - timedelta(minutes=29)).isoformat()
    elif change == "started":
        rows[0]["scheduled_start"] = NOW.isoformat()
    elif change == "tomorrow":
        rows[0]["scheduled_start"] = (NOW + timedelta(days=1)).isoformat()
    elif change == "wrong_market":
        rows[0]["market_key"] = "TOTAL_OVER_2_5"
    else:
        rows[0]["competitor_b"] = ""
    assert automation._tennis_price_check_candidates(
        rows, now=NOW, target_date=NOW.date(), previous_checks=checks,
    ) == []


def test_tennis_price_pool_remains_bounded_by_existing_sport_catalog_limit():
    row = fixtures(1)[0][0]
    rows = [{**row, "key": f"tennis-{i}", "event_identity": f"event-{i}"}
            for i in range(automation.MAX_AUTOMATIC_OTHER_CANDIDATES_PER_SPORT + 1)]
    selected = automation._tennis_price_check_candidates(
        rows, now=NOW, target_date=NOW.date(), previous_checks={},
    )
    assert len(selected) == automation.MAX_AUTOMATIC_OTHER_CANDIDATES_PER_SPORT
