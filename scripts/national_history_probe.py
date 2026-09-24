"""Read-only, quota-governed Nations League history coverage diagnostic.

Run as the app user on the VPS.  Prints only aggregate counts, never secrets,
fixtures, team names or predictions.  It does not mutate the model cache.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys
from unittest.mock import Mock, patch

ROOT = Path(os.environ.get("BETBOY_PROBE_ROOT") or Path(__file__).resolve().parents[1])
CODE_ROOT = Path(os.environ.get("BETBOY_PROBE_CODE_ROOT") or ROOT)
sys.path.insert(0, str(CODE_ROOT))
if CODE_ROOT != ROOT:
    sys.path.append(str(ROOT))

import challenge_15k  # noqa: E402
from challenge_15k import ChallengeDataProvider  # noqa: E402
import challenge_engine  # noqa: E402
from challenge_engine import (  # noqa: E402
    CANDIDATE_PROFILE_WETTFINDER, MODEL_SCOPE_SENIOR_NATIONAL,
    _fixture_datetime, _fixture_model, _fixture_score, build_fixture_candidates,
    build_market_model_artifact,
)
from config_loader import load_app_config  # noqa: E402


def main() -> int:
    print("model_source=", challenge_engine.__file__)
    print("model_version=", challenge_engine.CHALLENGE_PREDICTION_VERSION)
    config = load_app_config(config_path=ROOT / "config.ini")
    if not config.api_football_key:
        print("api_key=missing")
        return 2
    now = datetime.now(timezone.utc)
    provider = ChallengeDataProvider(config.api_football_key, None)
    fixtures = provider.upcoming_fixtures_range(
        5, now.year, now.date(), (now + timedelta(days=7)).date(),
    )
    if fixtures is None:
        print("upcoming=unavailable", "errors=", len(provider.errors))
        return 2
    print("upcoming=", len(fixtures))
    if not fixtures:
        return 0
    history = provider.completed_history(5, now.year, fixtures)
    if history is None:
        print("history=unavailable", "errors=", len(provider.errors))
        return 2
    print("history=", len(history))
    print("by_league=", sorted(Counter(row["league"]["id"] for row in history).items()))
    print("venue_effect_unknown=", sum(
        row.get("challenge_venue_unknown") is True
        or row.get("challenge_neutral_venue") is True for row in history
    ))
    print("modeled_upcoming=", sum(_fixture_model(row, history) is not None for row in fixtures))
    # Exact walk-forward modelability before each calendar day; this is not a
    # quality score or a release claim.  Same-day outcomes never train a peer.
    ordered = sorted(history, key=_fixture_datetime)
    prior = []
    modelable = Counter()
    uncertain_venue_targets = 0
    for row in ordered:
        day = _fixture_datetime(row).date()
        earlier = [item for item in prior if _fixture_datetime(item).date() < day]
        if row.get("challenge_venue_unknown") is True or row.get("challenge_neutral_venue") is True:
            uncertain_venue_targets += 1
        elif _fixture_score(row) is not None:
            for minimum in (2, 3, 4, 5):
                challenge_engine.MIN_VENUE_MATCHES = minimum
                if _fixture_model(row, earlier) is not None:
                    modelable[minimum] += 1
        prior.append(row)
    print("nonneutral_modelable_oos_by_min_venue=", sorted(modelable.items()),
          "uncertain_venue_targets=", uncertain_venue_targets)
    validation, calibration = build_market_model_artifact(history)
    counts = sorted(Counter(metric.observations for metric in validation.values()).items())
    passed = sorted(key for key, metric in validation.items() if metric.passed)
    released = sorted(
        key for key, metric in validation.items() if metric.statistical_release_passed
    )
    print("validation_observation_counts=", counts)
    print("validation_passed=", passed)
    print("statistical_release_passed=", released)
    print("calibration_maps=", len(calibration))
    candidates = [
        candidate
        for fixture in fixtures
        for candidate in build_fixture_candidates(
            fixture, history, validation, calibration,
            model_scope=MODEL_SCOPE_SENIOR_NATIONAL,
            candidate_profile=CANDIDATE_PROFILE_WETTFINDER,
        )
    ]
    available = [candidate for candidate in candidates if candidate.base_eligible]
    print("upcoming_model_candidates=", len(candidates))
    print("upcoming_model_passed=", len(available),
          "fixtures=", len({candidate.fixture_id for candidate in available}))
    print("upcoming_passed_by_market=", sorted(Counter(
        candidate.market_key for candidate in available
    ).items()))
    print("top_model_blocks=", Counter(
        reason for candidate in candidates for reason in candidate.blocked_reasons
    ).most_common(5))
    replay_provider = Mock()
    replay_provider.errors = []
    replay_provider.upcoming_fixtures_range.return_value = fixtures
    replay_provider.upcoming_fixtures.return_value = fixtures
    replay_provider.completed_history.return_value = history
    replay_provider.coverage.return_value = {"injuries": False, "lineups": False}
    replay_provider.injuries_by_fixture.return_value = {}
    replay_provider.details_by_fixture.return_value = {
        row["fixture"]["id"]: row for row in fixtures
    }
    replay_provider.h2h.return_value = []
    replay_provider.weather.return_value = None
    with (
        patch.object(challenge_15k, "_cached_market_validation", return_value=validation),
        patch.object(challenge_15k, "_cached_market_calibration", return_value=calibration),
    ):
        snapshot = challenge_15k.scan_daily_challenge(
            replay_provider, [5], now.date(), 1200,
            search_end_date=(now + timedelta(days=7)).date(),
            candidate_profile=CANDIDATE_PROFILE_WETTFINDER,
        )
    print("replay_base=", snapshot["base_candidates"],
          "forecast=", snapshot["forecast_candidates"],
          "catalog=", len(snapshot["wettfinder_candidates"]),
          "approved=", snapshot["approved_candidates"])
    print("provider_errors=", len(provider.errors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
