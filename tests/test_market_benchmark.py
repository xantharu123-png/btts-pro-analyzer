from datetime import datetime, timedelta, timezone
import math
import random

import pytest

from challenge_engine import _walk_forward_market_records
from football_data_history import parse_history_csv
from market_benchmark import (
    BenchmarkReport, benchmark_league, evaluate_cells, finalise, offered_odds, policy_bets,
    reference_probabilities, render_markdown, walk_forward_model_probabilities,
)
from market_benchmark_history import parse_benchmark_csv

START = datetime(2024, 8, 1, 15, tzinfo=timezone.utc)


def synthetic_league(*, teams=8, rounds=4, league_id=39, seed=3):
    """Deterministic round-robin history with plausible scores (no prices)."""
    generator = random.Random(seed)
    strength = {team: 1.0 + 0.12 * index for index, team in enumerate(range(teams))}
    fixtures = []
    day = 0
    for round_index in range(rounds):
        order = list(range(teams))
        for match_day in range(teams - 1):
            pairs = [(order[i], order[teams - 1 - i]) for i in range(teams // 2)]
            for home, away in pairs:
                if round_index % 2:
                    home, away = away, home
                home_rate = 1.45 * strength[home] / strength[away]
                away_rate = 1.1 * strength[away] / strength[home]
                played = START + timedelta(days=day, hours=generator.randrange(0, 5))
                fixtures.append({
                    "fixture": {"id": 1000 + len(fixtures), "date": played.isoformat(), "referee": None},
                    "league": {"id": league_id, "season": 2024, "name": "Synthetic"},
                    "teams": {"home": {"id": 10 + home, "name": f"Team {home}"},
                              "away": {"id": 10 + away, "name": f"Team {away}"}},
                    "goals": {"home": _poisson(generator, home_rate), "away": _poisson(generator, away_rate)},
                    "challenge_stats": {"corners_home": 5, "corners_away": 4,
                                        "yellow_cards_home": 2, "yellow_cards_away": 2},
                    "challenge_source": "football-data-results-only",
                })
            order = [order[0]] + [order[-1]] + order[1:-1]
            day += 3
    return fixtures


def _poisson(generator, rate):
    threshold, count, product = math.exp(-rate), 0, generator.random()
    while product > threshold:
        count += 1
        product *= generator.random()
    return count


def synthetic_benchmark(fixtures, *, seed=5):
    """Pinnacle/Max closing prices around the true scoring rates, with margin."""
    generator = random.Random(seed)
    rows = {}
    for fixture in fixtures:
        home_rate = 1.45 * (1 + 0.12 * (fixture["teams"]["home"]["id"] - 10)) / (1 + 0.12 * (fixture["teams"]["away"]["id"] - 10))
        away_rate = 1.1 * (1 + 0.12 * (fixture["teams"]["away"]["id"] - 10)) / (1 + 0.12 * (fixture["teams"]["home"]["id"] - 10))
        p_home, p_draw, p_away = _result_probabilities(home_rate, away_rate)
        margin = 1.03
        pinnacle = tuple(round(1 / (p * margin), 3) for p in (p_home, p_draw, p_away))
        best = tuple(round(price * (1 + generator.uniform(0.0, 0.04)), 3) for price in pinnacle)
        p_over = 1 - sum(math.exp(-(home_rate + away_rate)) * (home_rate + away_rate) ** k / math.factorial(k) for k in range(3))
        ou = (round(1 / (p_over * margin), 3), round(1 / ((1 - p_over) * margin), 3))
        rows[fixture["fixture"]["id"]] = {
            "schema": "test", "fixture_id": fixture["fixture"]["id"], "league_id": 39, "season": 2024,
            "date": fixture["fixture"]["date"], "home": "h", "away": "a",
            "result": {"pinnacle": pinnacle, "max": best}, "ou25": {"pinnacle": ou, "max": ou},
            "closing": {"result:pinnacle": True, "result:max": True, "ou25:pinnacle": True, "ou25:max": True},
        }
    return rows


def _result_probabilities(home_rate, away_rate, limit=12):
    def pmf(rate, k):
        return math.exp(-rate) * rate ** k / math.factorial(k)
    home = draw = away = 0.0
    for h in range(limit):
        for a in range(limit):
            p = pmf(home_rate, h) * pmf(away_rate, a)
            if h > a:
                home += p
            elif h == a:
                draw += p
            else:
                away += p
    total = home + draw + away
    return home / total, draw / total, away / total


def test_walk_forward_mirror_matches_the_release_gate_record_builder():
    fixtures = synthetic_league()
    predictions, raw, outcomes = walk_forward_model_probabilities(fixtures)
    records = _walk_forward_market_records(fixtures)
    assert predictions, "synthetic league must yield predictions"
    for key in ("RESULT_HOME", "TOTAL_OVER_2_5", "BTTS_YES"):
        mirrored = [markets[key] for markets in predictions.values() if key in markets]
        assert mirrored == records[key]["probabilities"]
        assert [outcomes[f][key] for f, markets in predictions.items() if key in markets] == records[key]["outcomes"]
        assert [raw[f][key] for f, markets in predictions.items() if key in markets] == records[key]["raw"]


def test_benchmark_rows_join_by_the_same_pseudo_fixture_id_and_stay_separate_from_the_model():
    csv = (
        "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,HC,AC,HY,AY,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,PC>2.5,PC<2.5,B365H,B365D,B365A\n"
        "E0,16/08/2024,Arsenal,Wolves,2,0,7,3,1,2,1.25,6.4,12.0,1.28,6.8,13.0,1.6,2.45,1.22,6.0,11.0\n"
        "E0,17/08/2024,Everton,Brighton,0,3,4,6,2,1,,,,2.6,3.3,2.9,,,2.5,3.2,2.8\n"
    ).encode()
    fixtures = parse_history_csv(csv, 39, 2024, [])
    benchmark = parse_benchmark_csv(csv, 39, 2024)
    assert {f["fixture"]["id"] for f in fixtures} == set(benchmark)
    for fixture in fixtures:  # The model loader still carries no price field anywhere.
        assert not any("PS" in key or "B365" in key or "Max" in key for key in fixture)
        assert not any("PS" in key or "B365" in key or "Max" in key for key in fixture["fixture"])
    arsenal = benchmark[[f for f in fixtures if f["teams"]["home"]["name"] == "Arsenal"][0]["fixture"]["id"]]
    assert arsenal["result"]["pinnacle"] == (1.25, 6.4, 12.0) and arsenal["closing"]["result:pinnacle"] is True
    assert arsenal["result"]["bet365"] == (1.22, 6.0, 11.0) and arsenal["closing"]["result:bet365"] is False
    assert arsenal["ou25"]["pinnacle"] == (1.6, 2.45)
    provider, probabilities, closing = reference_probabilities(arsenal)
    assert provider == "pinnacle" and closing["RESULT_HOME"] is True
    assert math.isclose(sum(probabilities[k] for k in ("RESULT_HOME", "RESULT_DRAW", "RESULT_AWAY")), 1.0, abs_tol=1e-9)
    assert math.isclose(probabilities["DC_1X"], probabilities["RESULT_HOME"] + probabilities["RESULT_DRAW"])
    assert math.isclose(probabilities["TOTAL_OVER_2_5"] + probabilities["TOTAL_UNDER_2_5"], 1.0, abs_tol=1e-9)
    assert offered_odds(arsenal)["RESULT_HOME"] == (1.28, "max")
    everton = benchmark[[f for f in fixtures if f["teams"]["home"]["name"] == "Everton"][0]["fixture"]["id"]]
    assert reference_probabilities(everton)[0] == "avg" or reference_probabilities(everton)[0] is None


def test_cells_fdr_policy_replay_and_report_on_a_synthetic_league():
    fixtures = synthetic_league(rounds=6)
    benchmark = synthetic_benchmark(fixtures)
    report = BenchmarkReport(haircut_pp=5.0)
    benchmark_league(report, league_id=39, fixtures=fixtures, benchmark=benchmark, seasons=[2024])
    finalise(report)
    keys = {cell.market_key for cell in report.cells}
    assert {"RESULT_HOME", "RESULT_DRAW", "RESULT_AWAY", "DC_1X", "TOTAL_OVER_2_5", "TOTAL_UNDER_2_5"} <= keys
    for cell in report.cells:
        assert cell.observations == report.leagues[39]["joined_with_benchmark"]
        assert 0 <= cell.brier_model <= 1 and 0 <= cell.brier_market <= 1
        assert cell.q_value is not None and 0 <= cell.q_value <= 1
        assert cell.closing_share == 1.0 and cell.provider == "pinnacle"
    # The synthetic market knows the true rates: an averages model should not beat it.
    assert not any(cell.market_beaten and cell.q_value <= 0.05 for cell in report.cells)
    for bet in report.bets:
        assert bet.offered_odds >= bet.minimum_odds >= 1.2
        assert bet.clv is not None and bet.roi in (bet.offered_odds - 1.0, -1.0)
    markdown = render_markdown(report)
    assert "Markt geschlagen" in markdown and "Replay der Preisgate-Policy" in markdown
    assert "Quoten fließen nicht in die Modellschätzung" in markdown


def test_policy_replay_only_bets_above_the_risk_adjusted_minimum():
    predictions = {1: {"RESULT_HOME": 0.80}, 2: {"RESULT_HOME": 0.55}}
    outcomes = {1: {"RESULT_HOME": 1}, 2: {"RESULT_HOME": 0}}
    row = {"result": {"pinnacle": (1.35, 5.0, 9.0), "max": (1.40, 5.2, 9.5)}, "ou25": {}, "closing": {"result:pinnacle": True}}
    benchmark = {1: row, 2: row}
    bets = policy_bets(predictions, outcomes, benchmark, league_id=39, haircut_pp=5.0)
    # p=0.80 → 0.75 after 5 pp → minimum 1.03/0.75 = 1.38 ≤ 1.40 (bet); p=0.55 → minimum 2.06 > 1.40 (no bet).
    assert [bet.model_probability for bet in bets] == [0.80]
    assert bets[0].offered_odds == 1.40 and bets[0].offer_provider == "max" and bets[0].won == 1
    assert math.isclose(bets[0].roi, 0.40)
    assert bets[0].clv is not None and bets[0].edge_pp is not None
