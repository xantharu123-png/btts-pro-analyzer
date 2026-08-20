from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

import uefa_transfer_backtest as transfer


UTC = timezone.utc


def _fixture(
    fixture_id: int,
    kickoff: datetime,
    home_id: int,
    away_id: int,
    home_goals: int,
    away_goals: int,
    *,
    league_id: int,
    season: int = 2025,
    round_name: str = "Qualification",
) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": kickoff.astimezone(UTC).isoformat(),
            "referee": "Offline Referee",
        },
        "league": {
            "id": league_id,
            "season": season,
            "round": round_name,
        },
        "teams": {
            "home": {"id": home_id, "name": f"Team {home_id}"},
            "away": {"id": away_id, "name": f"Team {away_id}"},
        },
        "goals": {"home": home_goals, "away": away_goals},
    }


def _replay(
    index: int,
    *,
    kickoff: datetime | None = None,
    btts: bool = True,
    competition_id: int = 2,
    source_league_ids: tuple[int, int] = (39, 140),
    round_name: str = "Qualification",
) -> transfer.TransferReplayFixture:
    target_day = kickoff or datetime(2025, 7, 1, 18, tzinfo=UTC) + timedelta(days=index)
    fixture_offset = (competition_id - 2) * 1_000_000
    target = _fixture(
        100_000 + fixture_offset + index,
        target_day,
        101,
        202,
        1,
        1 if btts else 0,
        league_id=competition_id,
        round_name=round_name,
    )
    competition_history = (
        _fixture(
            200_000 + fixture_offset + index,
            target_day - timedelta(days=30),
            301,
            302,
            2,
            1,
            league_id=competition_id,
        ),
    )
    home_history = tuple(
        _fixture(
            300_000 + fixture_offset + index * 10 + sample,
            target_day - timedelta(days=20 + sample),
            101,
            401 + sample,
            2,
            0,
            league_id=source_league_ids[0],
        )
        for sample in range(5)
    )
    away_history = tuple(
        _fixture(
            400_000 + fixture_offset + index * 10 + sample,
            target_day - timedelta(days=20 + sample),
            402 + sample,
            202,
            1,
            2,
            league_id=source_league_ids[1],
        )
        for sample in range(5)
    )
    return transfer.TransferReplayFixture(
        fixture=target,
        competition_history=competition_history,
        home_team_history=home_history,
        away_team_history=away_history,
        competition_id=competition_id,
        cohort="qualification",
        source_league_ids=source_league_ids,
    )


def _fixed_prediction(probability: float = 0.65):
    def predict(_fixture, _history, calibration=None, *, team_history=None):
        assert calibration is None
        assert team_history is not None
        return {
            "probabilities": {
                "BTTS_YES": (probability, probability, probability),
                "BTTS_NO": (0.5, 0.5, 0.5),
            }
        }

    return predict


def _calibratable_prediction(fixture, _history, calibration=None, *, team_history=None):
    assert calibration is None
    assert team_history is not None
    index = fixture["fixture"]["id"] - 100_000
    probability = (0.1, 0.3, 0.5, 0.7, 0.9)[index % 5]
    return {
        "probabilities": {
            "BTTS_YES": (probability, probability, probability),
            "BTTS_NO": (0.5, 0.5, 0.5),
        }
    }


def _calibration_replays(
    count: int,
    *,
    competition_id: int = 2,
    source_league_ids: tuple[int, int] = (39, 140),
) -> list[transfer.TransferReplayFixture]:
    replays = []
    for index in range(count):
        probability = (0.1, 0.3, 0.5, 0.7, 0.9)[index % 5]
        bucket_index = index // 5
        # Each probability bucket has the requested long-run event rate, but
        # successes are spread over time rather than placed in one block.
        btts = (bucket_index * 17) % 50 < int(probability * 50)
        replays.append(
            _replay(
                index,
                btts=btts,
                competition_id=competition_id,
                source_league_ids=source_league_ids,
            )
        )
    return replays


def test_future_and_same_day_history_are_invisible(monkeypatch):
    target = _replay(1)
    kickoff = datetime.fromisoformat(target.fixture["fixture"]["date"])
    extreme_same_day = _fixture(
        900_001,
        kickoff.replace(hour=1),
        501,
        502,
        20,
        20,
        league_id=2,
    )
    extreme_future = _fixture(
        900_002,
        kickoff + timedelta(days=2),
        503,
        504,
        30,
        30,
        league_id=2,
    )

    def history_sensitive(_fixture, history, calibration=None, *, team_history=None):
        assert calibration is None
        total = sum(item["goals"]["home"] + item["goals"]["away"] for item in history)
        total += sum(
            item["goals"]["home"] + item["goals"]["away"]
            for item in team_history or []
        )
        probability = min(0.95, 0.1 + total / 100.0)
        return {"probabilities": {"BTTS_YES": (probability,) * 3}}

    monkeypatch.setattr(transfer, "fixture_market_probabilities", history_sensitive)
    baseline = transfer.run_transfer_backtest(
        [target], market_keys=["BTTS_YES"]
    ).predictions[0]
    noisy = replace(
        target,
        competition_history=(
            *target.competition_history,
            extreme_same_day,
            extreme_future,
        ),
    )
    replayed = transfer.run_transfer_backtest(
        [noisy], market_keys=["BTTS_YES"]
    ).predictions[0]

    assert replayed.raw_probability == baseline.raw_probability
    assert replayed.probability == baseline.probability


def test_same_day_targets_share_the_same_pre_day_baseline(monkeypatch):
    day = datetime(2025, 8, 5, 14, tzinfo=UTC)
    first = _replay(1, kickoff=day, btts=True)
    second = _replay(2, kickoff=day + timedelta(hours=5), btts=False)
    monkeypatch.setattr(transfer, "fixture_market_probabilities", _fixed_prediction())

    result = transfer.run_transfer_backtest(
        [first, second],
        market_keys=["BTTS_YES"],
    )

    assert len(result.predictions) == 2
    assert {item.baseline_probability for item in result.predictions} == {0.5}


@pytest.mark.parametrize(
    "failure_case",
    (
        "empty_home",
        "same_day_home",
        "future_away",
        "wrong_team_home",
        "four_home_venue_matches",
    ),
)
def test_replay_requires_usable_pre_target_day_history_for_both_teams(
    monkeypatch,
    failure_case,
):
    replay = _replay(1)
    kickoff = datetime.fromisoformat(replay.fixture["fixture"]["date"])
    if failure_case == "empty_home":
        replay = replace(replay, home_team_history=())
    elif failure_case == "same_day_home":
        same_day = []
        for item in replay.home_team_history:
            changed = deepcopy(item)
            changed["fixture"]["date"] = kickoff.replace(hour=1).isoformat()
            same_day.append(changed)
        replay = replace(replay, home_team_history=tuple(same_day))
    elif failure_case == "future_away":
        future = []
        for item in replay.away_team_history:
            changed = deepcopy(item)
            changed["fixture"]["date"] = (kickoff + timedelta(days=1)).isoformat()
            future.append(changed)
        replay = replace(replay, away_team_history=tuple(future))
    elif failure_case == "wrong_team_home":
        wrong_team = []
        for item in replay.home_team_history:
            changed = deepcopy(item)
            changed["teams"]["home"]["id"] = 901
            changed["teams"]["away"]["id"] = 902
            wrong_team.append(changed)
        replay = replace(replay, home_team_history=tuple(wrong_team))
    else:
        wrong_venue = list(deepcopy(replay.home_team_history))
        first = wrong_venue[0]
        first["teams"]["home"], first["teams"]["away"] = (
            first["teams"]["away"],
            first["teams"]["home"],
        )
        replay = replace(replay, home_team_history=tuple(wrong_venue))

    def should_not_model(*_args, **_kwargs):
        pytest.fail("invalid replay reached the model")

    monkeypatch.setattr(transfer, "fixture_market_probabilities", should_not_model)
    with pytest.raises(transfer.TransferBacktestError, match="history"):
        transfer.run_transfer_backtest([replay], market_keys=["BTTS_YES"])


def test_less_than_200_real_oos_predictions_never_validate(monkeypatch):
    monkeypatch.setattr(
        transfer,
        "fixture_market_probabilities",
        _calibratable_prediction,
    )
    replays = _calibration_replays(199)

    result = transfer.run_transfer_backtest(
        replays,
        market_keys=["BTTS_YES"],
    )

    market = result.markets["BTTS_YES"]
    assert market.validation.observations == 199
    assert market.validated is False


def test_validation_and_calibration_are_market_specific(monkeypatch):
    monkeypatch.setattr(
        transfer,
        "fixture_market_probabilities",
        _calibratable_prediction,
    )
    replays = _calibration_replays(250)

    result = transfer.run_transfer_backtest(
        replays,
        market_keys=["BTTS_YES", "BTTS_NO"],
    )

    good = result.markets["BTTS_YES"]
    bad = result.markets["BTTS_NO"]
    assert good.validation.observations == 250
    assert good.calibration is not None
    assert good.validated is True
    assert bad.validation.observations == 250
    assert bad.validated is False


@pytest.mark.parametrize(
    ("second_competition_count", "expected_validated"),
    ((199, False), (200, True)),
)
def test_each_declared_competition_requires_200_oos(
    monkeypatch,
    second_competition_count,
    expected_validated,
):
    monkeypatch.setattr(
        transfer,
        "fixture_market_probabilities",
        _calibratable_prediction,
    )
    replays = [
        *_calibration_replays(200, competition_id=2),
        *_calibration_replays(
            second_competition_count,
            competition_id=3,
            source_league_ids=(61, 78),
        ),
    ]

    market = transfer.run_transfer_backtest(
        replays,
        market_keys=["BTTS_YES"],
    ).markets["BTTS_YES"]

    assert dict(market.competition_observations) == {
        2: 200,
        3: second_competition_count,
    }
    assert market.validation.passed is True
    assert market.validated is expected_validated


@pytest.mark.parametrize("round_name", ("League Stage - 1", "Play-offs", ""))
def test_replay_cohort_must_match_an_unambiguous_fixture_round(round_name):
    replay = _replay(1, round_name=round_name)

    with pytest.raises(transfer.TransferBacktestError, match="round"):
        transfer.run_transfer_backtest([replay], market_keys=["BTTS_YES"])


def test_dataset_hash_is_deterministic_odds_blind_and_result_sensitive():
    replay = _replay(1)
    with_prices = deepcopy(replay.fixture)
    with_prices["bookmakers"] = [{"name": "must-not-cross-model-boundary", "odds": 9.99}]
    priced = replace(replay, fixture=with_prices)
    changed_result = deepcopy(replay.fixture)
    changed_result["goals"]["away"] = 0
    changed = replace(replay, fixture=changed_result)

    assert transfer.dataset_hash([replay]) == transfer.dataset_hash([priced])
    assert transfer.dataset_hash([replay]) != transfer.dataset_hash([changed])
    assert transfer.dataset_hash([replay, _replay(2)]) == transfer.dataset_hash(
        [_replay(2), replay]
    )


def test_artifact_provenance_hash_and_cutoff_fail_closed(monkeypatch):
    monkeypatch.setattr(transfer, "fixture_market_probabilities", _fixed_prediction())
    replay = _replay(1)
    kickoff = datetime.fromisoformat(replay.fixture["fixture"]["date"])
    cutoff = kickoff + timedelta(hours=1)
    artifact = transfer.build_transfer_artifact(
        [replay],
        model_signature="challenge-engine:test-v1",
        competition_ids=[2],
        cohort="qualification",
        training_cutoff=cutoff,
        market_keys=["BTTS_YES"],
    )
    with pytest.raises(transfer.TransferBacktestError, match="every declared"):
        transfer.build_transfer_artifact(
            [replay],
            model_signature="challenge-engine:test-v1",
            competition_ids=[2, 3],
            cohort="qualification",
            training_cutoff=cutoff,
            market_keys=["BTTS_YES"],
        )

    parsed = transfer.verify_transfer_artifact(
        artifact,
        expected_model_signature="challenge-engine:test-v1",
        expected_competition_id=2,
        expected_cohort="qualification",
        fixture_round="Qualification",
        expected_source_league_ids=(39, 140),
        fixture_kickoff=cutoff + timedelta(days=1),
        expected_dataset_hash=artifact["provenance"]["dataset_hash"],
        expected_artifact_id=artifact["artifact_id"],
    )
    assert parsed.release_authorized is False
    assert parsed.provenance.replay_count == 1
    assert parsed.validated_market_keys == ()

    for changed in (
        {"expected_model_signature": "challenge-engine:other-v1"},
        {"expected_competition_id": 3},
        {"expected_cohort": "main"},
        {"fixture_kickoff": cutoff},
        {"fixture_kickoff": cutoff + timedelta(hours=2)},
        {"fixture_round": "League Stage - 1"},
        {"expected_source_league_ids": (140, 39)},
        {"expected_source_league_ids": (39, 61)},
        {"expected_dataset_hash": "0" * 64},
    ):
        kwargs = {
            "expected_model_signature": "challenge-engine:test-v1",
            "expected_competition_id": 2,
            "expected_cohort": "qualification",
            "fixture_round": "Qualification",
            "expected_source_league_ids": (39, 140),
            "fixture_kickoff": cutoff + timedelta(days=1),
            "expected_dataset_hash": artifact["provenance"]["dataset_hash"],
            "expected_artifact_id": artifact["artifact_id"],
        }
        kwargs.update(changed)
        with pytest.raises(transfer.TransferBacktestError):
            transfer.verify_transfer_artifact(artifact, **kwargs)

    tampered = deepcopy(artifact)
    tampered["markets"]["BTTS_YES"]["validated"] = True
    with pytest.raises(transfer.TransferBacktestError, match="hash"):
        transfer.verify_transfer_artifact(
            tampered,
            expected_model_signature="challenge-engine:test-v1",
            expected_competition_id=2,
            expected_cohort="qualification",
            fixture_round="Qualification",
            expected_source_league_ids=(39, 140),
            fixture_kickoff=cutoff + timedelta(days=1),
            expected_dataset_hash=artifact["provenance"]["dataset_hash"],
            expected_artifact_id=artifact["artifact_id"],
        )


def test_artifact_scope_is_joint_and_rejects_cross_product(monkeypatch):
    monkeypatch.setattr(transfer, "fixture_market_probabilities", _fixed_prediction())
    first = _replay(1, competition_id=2, source_league_ids=(39, 140))
    second = _replay(1, competition_id=3, source_league_ids=(61, 78))
    cutoff = max(
        datetime.fromisoformat(first.fixture["fixture"]["date"]),
        datetime.fromisoformat(second.fixture["fixture"]["date"]),
    ) + timedelta(hours=1)
    artifact = transfer.build_transfer_artifact(
        [first, second],
        model_signature="challenge-engine:joint-scope-v1",
        competition_ids=[2, 3],
        cohort="qualification",
        training_cutoff=cutoff,
        market_keys=["BTTS_YES"],
    )

    scopes = artifact["provenance"]["scope_observations"]
    assert [
        (
            scope["competition_id"],
            scope["cohort"],
            scope["home_source_league_id"],
            scope["away_source_league_id"],
        )
        for scope in scopes
    ] == [
        (2, "qualification", 39, 140),
        (3, "qualification", 61, 78),
    ]
    assert all(scope["home_form_observations"] == 5 for scope in scopes)
    assert all(scope["away_form_observations"] == 5 for scope in scopes)
    assert all(scope["home_venue_observations"] == 5 for scope in scopes)
    assert all(scope["away_venue_observations"] == 5 for scope in scopes)

    common = {
        "expected_model_signature": "challenge-engine:joint-scope-v1",
        "expected_competition_id": 2,
        "expected_cohort": "qualification",
        "fixture_round": "Qualification",
        "fixture_kickoff": cutoff + timedelta(days=1),
        "expected_dataset_hash": artifact["provenance"]["dataset_hash"],
        "expected_artifact_id": artifact["artifact_id"],
    }
    parsed = transfer.verify_transfer_artifact(
        artifact,
        expected_source_league_ids=(39, 140),
        **common,
    )
    assert len(parsed.provenance.scope_observations) == 2

    with pytest.raises(transfer.TransferBacktestError, match="exact fixture scope"):
        transfer.verify_transfer_artifact(
            artifact,
            expected_source_league_ids=(61, 78),
            **common,
        )
