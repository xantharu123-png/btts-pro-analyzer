"""Offline, descriptive form and draw study; no odds, API, writes, or promotion."""

import argparse
from datetime import date, datetime, timedelta, timezone
from itertools import groupby
import json
from math import exp, fsum, log, log1p
from random import Random
from statistics import quantiles

from handball_pilot_model import predict_1x2

STUDY_SEASON = 2026
CALIBRATION_LAST_DAY = date(2027, 1, 31)
TEST_FIRST_DAY = CALIBRATION_LAST_DAY + timedelta(days=1)
TEST_LAST_DAY = date(STUDY_SEASON + 1, 6, 30)
FORM_HALFLIFE_DAYS = 90
MIN_CALIBRATION_N, MIN_CALIBRATION_WEEKS = 40, 4
MIN_TEST_N, MIN_TEST_WEEKS = 60, 6
_DRAW_PRIOR_PRECISION = 4.
_BOOTSTRAP_DRAWS = 5_000
_BOOTSTRAP_SEED = 20261125
_EPS = 1e-12
_MAX_BYTES = 1024 * 1024
_MAX_GAMES = 512
_SIDES = ("home", "draw", "away")
_MODELS = ("v1", "form_90d", "draw_calibrated")


def _utc(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        instant = datetime.fromisoformat(value)
        return instant if instant.utcoffset() == timedelta(0) else None
    except ValueError:
        return None


def _id(value):
    return type(value) is int and 0 < value < 2**63


def _parse_archive(study_input, *, as_of, season, league_clock):
    if (not isinstance(study_input, dict) or type(study_input.get("version")) is not int
            or study_input["version"] != 1 or season != STUDY_SEASON):
        return None
    observed = _utc(study_input.get("observed_at"))
    games = study_input.get("games")
    if observed is None or observed > as_of or not isinstance(games, list) or len(games) > _MAX_GAMES:
        return None
    rows = []
    seen = set()
    for row in games:
        if not isinstance(row, (tuple, list)) or len(row) != 6:
            return None
        fixture_id, stamp, home, away, home_goals, away_goals = row
        instant = _utc(stamp)
        if (not all(_id(value) for value in (fixture_id, home, away)) or fixture_id in seen or home == away
                or instant is None or not instant < observed
                or any(type(score) is not int or not 0 <= score <= 999 for score in (home_goals, away_goals))):
            return None
        day = instant.astimezone(league_clock).date()
        if not date(season, 7, 1) <= day <= TEST_LAST_DAY:
            return None
        seen.add(fixture_id)
        rows.append((day, instant, fixture_id, home, away, home_goals, away_goals))
    return observed, sorted(rows)


def _logit(probability):
    p = min(max(probability, _EPS), 1. - _EPS)
    return log(p) - log1p(-p)


def _logistic(value):
    if value >= 0:
        return 1. / (1. + exp(-value))
    odds = exp(value)
    return odds / (1. + odds)


def _fit_draw_offset(calibration):
    # Penalized Bernoulli log loss; strictly convex. The score is monotone
    # and bounded by ±n before adding the derivative of the Gaussian prior.
    samples = [(_logit(p["draw"]), outcome == "draw") for _, p, outcome in calibration]
    edge = len(samples) / _DRAW_PRIOR_PRECISION
    lo, hi = -edge, edge
    for _ in range(60):
        middle = (lo + hi) / 2.
        derivative = fsum(_logistic(logit + middle) - draw for logit, draw in samples)
        if derivative + _DRAW_PRIOR_PRECISION * middle > 0.:
            hi = middle
        else:
            lo = middle
    return (lo + hi) / 2.


def _recalibrate_draw(probability, offset):
    draw = _logistic(_logit(probability["draw"]) + offset)
    scale = (1. - draw) / (1. - probability["draw"])
    return {"home": probability["home"] * scale, "draw": draw, "away": probability["away"] * scale}


def _scores(rows):
    if not rows:
        return None
    n = len(rows)
    return {
        "brier_1x2": fsum(fsum((p[side] - (side == outcome))**2 for side in _SIDES) for p, outcome in rows) / n,
        "brier_draw": fsum((p["draw"] - (outcome == "draw"))**2 for p, outcome in rows) / n,
        "log_loss": -fsum(log(max(_EPS, p[outcome])) for p, outcome in rows) / n,
    }


def _weeks(days):
    return len({day.isocalendar()[:2] for day in days})


def _brier_1x2(p, outcome):
    return fsum((p[side] - (side == outcome))**2 for side in _SIDES)


def _paired_intervals(test, offset, *, sufficient):
    bands = {"form_90d_brier_1x2": None, "draw_calibrated_brier_draw": None}
    if not sufficient:
        return bands
    blocks = []
    for _, group in groupby(test, key=lambda row: row[0].isocalendar()[:2]):
        rows = list(group)
        form_total = fsum(_brier_1x2(base, outcome) - _brier_1x2(form, outcome)
                          for _, base, form, outcome in rows)
        draw_total = 0. if offset is None else fsum(
            (base["draw"] - (outcome == "draw"))**2
            - (_recalibrate_draw(base, offset)["draw"] - (outcome == "draw"))**2
            for _, base, _, outcome in rows
        )
        blocks.append((len(rows), form_total, draw_total))
    rng = Random(_BOOTSTRAP_SEED)
    form_draws, draw_draws = [], []
    for _ in range(_BOOTSTRAP_DRAWS):
        # Keep both models and outcomes paired inside each sampled ISO week.
        # Divide by the resampled match count, not the week count.
        sample = rng.choices(blocks, k=len(blocks))
        n = sum(block[0] for block in sample)
        form_draws.append(fsum(block[1] for block in sample) / n)
        if offset is not None:
            draw_draws.append(fsum(block[2] for block in sample) / n)
    for endpoint, estimates in zip(bands, (form_draws, draw_draws), strict=True):
        if estimates:
            cuts = quantiles(estimates, n=80, method="inclusive")  # 1.25% and 98.75%.
            bands[endpoint] = [cuts[0], cuts[-1]]
    return bands


def evaluate_study_input(study_input, *, as_of, season, league_clock):
    """Walk forward by league day, with frozen draw calibration and shared test rows."""
    parsed = _parse_archive(study_input, as_of=as_of, season=season, league_clock=league_clock)
    if parsed is None:
        return {"status": "unavailable", "reason": "invalid_or_future_study_input"}
    observed, rows = parsed
    limit_day = as_of.astimezone(league_clock).date()
    history, history_days = [], []
    calibration, test = [], []
    calibration_fixtures = test_fixtures = 0
    for day, group in groupby(rows, key=lambda row: row[0]):
        if day >= limit_day:
            break
        batch = list(group)
        is_test = day >= TEST_FIRST_DAY
        if is_test:
            test_fixtures += len(batch)
            weights = [2.**(-(day - previous).days / FORM_HALFLIFE_DAYS) for previous in history_days]
        else:
            calibration_fixtures += len(batch)
        for _, _, _, home, away, home_goals, away_goals in batch:
            incumbent = predict_1x2(history, home_id=home, away_id=away)
            if incumbent is None:
                continue
            outcome = "home" if home_goals > away_goals else "away" if home_goals < away_goals else "draw"
            if not is_test:
                calibration.append((day, incumbent, outcome))
                continue
            form = predict_1x2(history, home_id=home, away_id=away, weights=weights)
            if form is not None:
                test.append((day, incumbent, form, outcome))
        # Matches share a predictor history throughout the entire local day.
        history.extend(row[3:] for row in batch)
        history_days.extend([day] * len(batch))

    cal_weeks = _weeks(day for day, _, _ in calibration)
    test_weeks = _weeks(day for day, _, _, _ in test)
    cal_sufficient = len(calibration) >= MIN_CALIBRATION_N and cal_weeks >= MIN_CALIBRATION_WEEKS
    test_sufficient = len(test) >= MIN_TEST_N and test_weeks >= MIN_TEST_WEEKS
    offset = _fit_draw_offset(calibration) if cal_sufficient else None
    scores = {
        "v1": _scores([(baseline, outcome) for _, baseline, _, outcome in test]),
        "form_90d": _scores([(form, outcome) for _, _, form, outcome in test]),
        "draw_calibrated": (
            _scores([(_recalibrate_draw(baseline, offset), outcome) for _, baseline, _, outcome in test])
            if offset is not None else None
        ),
    }
    baseline_scores = scores["v1"]
    paired = {
        model: {metric: baseline_scores[metric] - value for metric, value in scores[model].items()}
        if baseline_scores is not None and scores[model] is not None else None
        for model in _MODELS[1:]
    }
    return {
        "status": "descriptive" if cal_sufficient and test_sufficient else "collecting",
        "input_games": len(rows),
        "observed_at": observed.isoformat(),
        "calibration": {
            "eligible": len(calibration), "fixtures": calibration_fixtures, "weeks": cal_weeks,
            "draws": sum(outcome == "draw" for _, _, outcome in calibration),
        },
        "test": {
            "eligible": len(test), "fixtures": test_fixtures, "weeks": test_weeks,
            "draws": sum(outcome == "draw" for _, _, _, outcome in test),
        },
        "draw_offset": offset,
        "scores": scores,
        "paired_improvement": paired,
        "paired_intervals_97_5": _paired_intervals(test, offset, sufficient=test_sufficient),
    }


def _file_study_input(path):
    if not path.is_file() or path.is_symlink():
        return None, "no_local_study_input"
    try:
        with path.open("rb") as handle:
            raw = handle.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            raise ValueError("snapshot_too_large")
        data = json.loads(raw)
    except (OSError, ValueError, RecursionError):
        return None, "unreadable_local_snapshot"
    if not isinstance(data, dict) or "study_input" not in data:
        return None, "no_local_study_input"
    return data["study_input"], None


def read_study(*, as_of, directory=None):
    """Read only compact score envelopes of the fixed study season."""
    from handball_pilot import HANDBALL_LEAGUES, _path

    if as_of.utcoffset() is None:
        raise ValueError("as_of_requires_timezone")
    anchor = datetime(STUDY_SEASON, 11, 1, tzinfo=timezone.utc)
    leagues = {}
    for league in HANDBALL_LEAGUES:
        study_input, reason = _file_study_input(_path(anchor, league.code, directory))
        if reason is not None:
            leagues[league.code] = {"status": "unavailable", "reason": reason}
        else:
            leagues[league.code] = evaluate_study_input(
                study_input, as_of=as_of, season=STUDY_SEASON, league_clock=league.clock,
            )
    statuses = {league["status"] for league in leagues.values()}
    return {
        "status": next(status for status in ("descriptive", "collecting", "unavailable") if status in statuses),
        "as_of": as_of.astimezone(timezone.utc).isoformat(),
        "season": STUDY_SEASON,
        "calibration_through": CALIBRATION_LAST_DAY.isoformat(),
        "test_from": TEST_FIRST_DAY.isoformat(),
        "test_through": TEST_LAST_DAY.isoformat(),
        "form_half_life_days": FORM_HALFLIFE_DAYS,
        "draw_prior_precision": _DRAW_PRIOR_PRECISION,
        "paired_bootstrap": {"block": "ISO_week", "draws": _BOOTSTRAP_DRAWS,
                             "seed": _BOOTSTRAP_SEED, "level": 0.975},
        "minimum": {
            "calibration_fixtures": MIN_CALIBRATION_N, "calibration_weeks": MIN_CALIBRATION_WEEKS,
            "test_fixtures": MIN_TEST_N, "test_weeks": MIN_TEST_WEEKS,
        },
        "limitations": [
            "provider_league_season_phase_unverified",
            "replay_uses_earlier_league_days_not_per_result_arrival_times",
            "descriptive_only_no_release_or_market_evidence",
        ],
        "leagues": leagues,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", metavar="ISO_UTC",
                        help="Use a UTC instant instead of the current time.")
    parser.add_argument("--directory", help="Read study envelopes from this local directory.")
    args = parser.parse_args()
    as_of = _utc(args.as_of) if args.as_of is not None else datetime.now(timezone.utc)
    if as_of is None:
        parser.error("--as-of must be an ISO 8601 instant in UTC")
    print(json.dumps(read_study(as_of=as_of, directory=args.directory),
                     allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
