from datetime import date, datetime, timedelta, timezone
import json
import sqlite3

import pytest

import forecast_evidence as evidence
from team_sport_prices import parse_game_quotes


DECISION = datetime(2030, 1, 2, 10, tzinfo=timezone.utc)
START = DECISION + timedelta(hours=9)


def freeze(path, monkeypatch, *, decision=DECISION, probability=.70, with_prices=False, mixed_revision=False):
    monkeypatch.setattr(evidence, "_now", lambda: decision)
    rows = [dict(candidate_id=f"team_sport_research:snapshot_102:{role}", event_identity="event-nhl-102", sport="Eishockey",
                 model_version="sports-prematch-research-v1", policy_version="team-sport-descriptive-v1",
                 source="team_sport_research", fixture_source="NHL", provider_event_id="102",
                 market_key="H2H", selection=side, selected_competitor=side, competitor_a="DET", competitor_b="VAN",
                 competitor_a_id="17", competitor_b_id="23", competition="NHL", probability=p,
                 scheduled_start=START.isoformat(), modeled_at=(decision-timedelta(minutes=3)).isoformat(),
                 input_cutoff_at=(decision-timedelta(minutes=4)).isoformat())
            for side, p, role in (("DET", probability, "home"), ("VAN", 1-probability, "away"))]
    if mixed_revision:
        rows[1]["modeled_at"] = (decision-timedelta(minutes=2)).isoformat()
    if with_prices:
        game = dict(id=1210, date=START.isoformat(), status={"short":"NS"}, league={"name":"NHL"},
                    teams={"home":{"name":"DET"}, "away":{"name":"VAN"}})
        native = [dict(game=game, bookmakers=[{"id":1,"name":"Book","bets":[
            {"id":2,"name":"Home/Away","values":[{"value":"Home","odd":"1.60"},{"value":"Away","odd":"2.40"}]}]}])]
        prices = parse_game_quotes(native, rows, game, fetched_at=decision)
        assert len(prices) == 2
        for row in rows:
            row["reference_quote"] = prices[row["candidate_id"]].to_dict()
    return evidence.record_forecast_run(dict(generated_at=decision.isoformat(), selection_policy_version="team-sport-descriptive-v1",
                                             model_candidates=rows), path, "sports-prematch-research-v1"), rows


def read(path):
    from nhl_top_review import build_nhl_review
    return build_nhl_review(path, first=date(2030,1,2), last=date(2030,1,2), cutoff=START+timedelta(days=1))


def test_exact_native_entry_has_one_game_and_complete_pair(tmp_path, monkeypatch):
    path = tmp_path/"evidence.db"
    freeze(path, monkeypatch, with_prices=True)
    # Removing the outcomes table proves the blind branch cannot ask for scores or settlements.
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE forecast_results")
    before = path.read_bytes()
    report = read(path)
    assert report["counts"]["first_nhl_forecasts"] == 1
    assert report["counts"]["paired_entries"] == 1
    assert report["coverage"] == {"tier_60":{"games":1,"zurich_days":1},"tier_70":{"games":1,"zurich_days":1}}
    assert report["evaluation"] is None
    assert report["market_probability_mean"] == pytest.approx(.60)
    assert before == path.read_bytes()


def test_later_entry_and_closing_do_not_turn_into_first_price(tmp_path, monkeypatch):
    path = tmp_path/"evidence.db"
    freeze(path, monkeypatch)
    at = START-timedelta(minutes=10)
    _, rows = freeze(path, monkeypatch, decision=at, probability=.80, with_prices=True)
    evidence.record_current_closing_quotes(dict(generated_at=at.isoformat(), model_candidates=rows,
        selection_policy_version="team-sport-descriptive-v1"), db_path=path, model_version="sports-prematch-research-v1")
    report = read(path)
    assert report["counts"]["raw_closing_games"] == 1
    assert report["counts"]["first_nhl_forecasts"] == report["counts"]["favorite_70"] == 1
    assert report["counts"]["paired_entries"] == 0
    assert report["counts"]["missing_first_pair"] == 1


def test_unverified_partition_does_not_enter_the_market_cohort(tmp_path, monkeypatch):
    path = tmp_path/"evidence.db"
    freeze(path, monkeypatch, with_prices=True)
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER IF EXISTS forecast_quotes_no_update")
        for key, raw in db.execute("SELECT quote_id,payload_json FROM forecast_quotes").fetchall():
            payload = json.loads(raw)
            payload["native_market_partition"]["period"] = "regulation_only"
            db.execute("UPDATE forecast_quotes SET quote_id=?,payload_json=? WHERE quote_id=?",
                       (evidence._hash(payload), evidence._json(payload), key))
    assert read(path)["counts"]["paired_entries"] == 0


def test_same_run_does_not_mix_sides_from_different_model_clocks(tmp_path, monkeypatch):
    path = tmp_path/"evidence.db"
    freeze(path, monkeypatch, with_prices=True, mixed_revision=True)
    result = read(path)
    assert result["counts"]["first_nhl_forecasts"] == result["counts"]["paired_entries"] == 0
    assert result["counts"]["missing_model_pair"] == 1


def test_open_cannot_be_requested_before_the_frozen_read_date(tmp_path):
    from nhl_top_review import main

    with pytest.raises(SystemExit) as error:
        main(["--db", str(tmp_path/"unused.db"), "--phase", "open"],
             now=datetime(2026,11,25,tzinfo=timezone.utc))
    assert error.value.code == 2


@pytest.mark.parametrize("rule,side_results,expected", [
    ("riskobet-settlement-v1", ("WIN", "LOSS"), 1),
    ("riskobet-settlement-v1", ("LOSS", "WIN"), 0),
    ("riskobet-settlement-v1", ("WIN", "WIN"), None),
    ("riskobet-settlement-v1", (None, "LOSS"), None),
    ("wrong-period-v1", ("WIN", "LOSS"), None),
])
def test_terminal_uses_only_native_final_rule_and_agreeing_side_proofs(tmp_path, monkeypatch, rule, side_results, expected):
    from nhl_top_review import MODEL, POLICY, _first_favorites, _settled
    from collections import Counter

    path = tmp_path/"evidence.db"
    freeze(path, monkeypatch, with_prices=True)
    cutoff = START+timedelta(hours=4)
    observed = START+timedelta(hours=3)
    monkeypatch.setattr(evidence, "_now", lambda: cutoff)
    proof = dict(provider="nhl", provider_event_id="102", source_record_id="nhl:event:102:final",
                 payload_sha256="a"*64, settlement_rule=rule)
    for selected, outcome in zip(("DET", "VAN"), side_results, strict=True):
        if outcome is not None:
            evidence.append_result("event-nhl-102", "H2H", selected, outcome,
                                   observed_at=observed, provenance=proof, db_path=path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        game, = _first_favorites(conn, (MODEL, POLICY, DECISION.isoformat(), cutoff.isoformat()), cutoff, Counter())
        assert _settled(conn, game, cutoff) == expected
