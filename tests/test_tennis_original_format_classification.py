"""Legacy WTA format errors remain originals, never fabricated settlements."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from scripts import tennis_daily as daily


def row(prediction_id=1, *, tour="WTA", best_of=5):
    return {"id": prediction_id, "match_date": "2026-09-04", "tour": tour,
            "best_of": best_of, "player_a": "Player A", "player_b": "Player B",
            "fixture_source": "ESPN", "provider_event_id": str(prediction_id)}


def result(prediction_id=1):
    return {"provider_event_id": str(prediction_id), "player_a": "Player A",
            "player_b": "Player B", "winner": "Player A", "winner_sets": 2,
            "loser_sets": 0, "termination": "normal",
            "result_observed_at": datetime(2026, 9, 5, tzinfo=timezone.utc)}


def test_invalid_originals_skip_fetch_and_settlement_without_mutating(monkeypatch, capsys):
    originals = [row(i) for i in range(1, 103)]
    before = deepcopy(originals)
    monkeypatch.setattr(daily.shadow, "pending_predictions", lambda: originals)
    monkeypatch.setattr(daily, "fetch_results_espn", lambda *args: pytest.fail("API requested"))
    monkeypatch.setattr(daily, "fetch_results_sofascore", lambda *args: pytest.fail("API requested"))
    monkeypatch.setattr(daily.shadow, "settle", lambda *args, **kwargs: pytest.fail("Original settled"))
    monkeypatch.setattr(daily.shadow, "settle_side_bet", lambda *args: pytest.fail("Money written"))
    assert daily.auto_settle_completed(today="2026-10-04") == 0
    assert originals == before
    message = json.loads(capsys.readouterr().out.split(": ", 1)[1])
    assert message == {"reason": "unscorable_original_format", "tour": "WTA",
                       "best_of": 5, "count": 102, "sample_prediction_ids": [1, 2, 3, 4, 5],
                       "originals_unchanged": True}


def test_valid_wta_original_still_settles_in_mixed_batch(monkeypatch):
    originals = [row(i) for i in range(1, 103)] + [row(103, best_of=3)]
    before = deepcopy(originals)
    calls, fetches = [], []
    monkeypatch.setattr(daily.shadow, "pending_predictions", lambda: originals)
    monkeypatch.setattr(daily, "fetch_results_espn",
                        lambda day, tour: fetches.append((day, tour)) or [result(103)])
    monkeypatch.setattr(daily.shadow, "settle", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(daily.shadow, "side_bets_for", lambda ids: [])
    assert daily.auto_settle_completed(today="2026-10-04") == 1
    assert fetches == [("2026-09-04", "WTA")]
    assert len(calls) == 1 and calls[0][0] == (103, "Player A")
    assert calls[0][1]["player_a_sets"] == 2
    assert originals == before


@pytest.mark.parametrize("tour,best_of", [("ATP", 5), ("WTA", 3), ("WTA", 5.0),
                                         ("WTA", "5"), ("WTA", True), ("WTA", None)])
def test_exclusion_is_exact_and_other_failures_stay_strict(monkeypatch, capsys, tour, best_of):
    original = row(tour=tour, best_of=best_of)
    calls = []
    monkeypatch.setattr(daily.shadow, "pending_predictions", lambda: [original])
    monkeypatch.setattr(daily, "fetch_results_espn", lambda *args: [result()])
    def rejected(*args, **kwargs):
        calls.append(args)
        raise ValueError("Other genuine result error")
    monkeypatch.setattr(daily.shadow, "settle", rejected)
    with pytest.raises(daily.SettlementBatchError) as raised:
        daily.auto_settle_completed(today="2026-10-04")
    assert calls == [(1, "Player A")]
    assert raised.value.issues == [{"prediction_id": 1, "reason": "settlement_rejected",
                                   "error_type": "ValueError"}]
    assert "unscorable_original_format" not in capsys.readouterr().out


def test_no_new_rows_or_empty_batches_are_classified(monkeypatch, capsys):
    monkeypatch.setattr(daily.shadow, "pending_predictions", lambda: [
        dict(row(), match_date="2026-10-04"), dict(row(2), player_a="TBD")])
    monkeypatch.setattr(daily, "fetch_results_espn", lambda *args: pytest.fail("API requested"))
    assert daily.auto_settle_completed(today="2026-10-04") == 0
    assert capsys.readouterr().out == ""


def test_provider_failure_remains_operational_in_mixed_batch(monkeypatch):
    monkeypatch.setattr(daily.shadow, "pending_predictions", lambda: [row(), row(2, best_of=3)])
    def failed(*args):
        raise daily.ProviderFetchError(["provider timeout"])
    monkeypatch.setattr(daily, "fetch_results_espn", failed)
    with pytest.raises(daily.SettlementBatchError) as raised:
        daily.auto_settle_completed(today="2026-10-04")
    assert raised.value.settled == 0
    assert raised.value.issues[0]["reason"] == "result_source_failed"
