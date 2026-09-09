"""Cross-sport regression: known rest endpoint differs from half-open load windows."""
from datetime import timedelta

import pytest

from context_models.contracts import canonical_timestamp


@pytest.mark.parametrize("microseconds", [-1, 0, 1])
@pytest.mark.parametrize("side", ["home", "away"])
def test_football_observed_end_at_cutoff_affects_rest_not_half_open_load(tmp_path, microseconds, side):
    from test_football_weather_features import NOW, START, base, event, timeline, stored_load
    from context_models.football_load import football_schedule_features
    end = NOW + timedelta(microseconds=microseconds)
    older = timeline(90, 1, 2)
    latest = timeline(91, 1, 2, end=end)
    latest["result_observed_at"] = canonical_timestamp(end)
    rows = stored_load(tmp_path, [older, latest], observed=end)
    fv = football_schedule_features(event(), rows, cutoff=NOW, base=base())
    # Receipt of both synthetic rows is future in the +1 case: no past proof
    # is smuggled into the cutoff, including the older source payload.
    expected = (START-end).total_seconds()/3600 if microseconds <= 0 else None
    assert fv["values"][f"observed_recovery_exact_hours_{side}"] == expected
    assert fv["values"][f"observed_matches_1d_{side}"] == (1 if microseconds < 0 else None)


@pytest.mark.parametrize("microseconds", [-1, 0, 1])
@pytest.mark.parametrize("side", ["a", "b"])
def test_tennis_control_keeps_exact_end_but_half_open_performed_counts(tmp_path, microseconds, side):
    from test_tennis_context_features import NOW, event, base, native_row, stored
    from context_models.tennis import tennis_features
    end = NOW+timedelta(microseconds=microseconds)
    latest = native_row("20", "1", "2", hours=0,
        actual_start_utc=(end-timedelta(hours=2)).isoformat(),
        actual_end_utc=end.isoformat(), result_observed_at=end.isoformat())
    rows = stored(tmp_path, [latest], receipt=end)
    fv = tennis_features(event(), rows, base(), cutoff=NOW)
    expected = (NOW+timedelta(hours=6)-end).total_seconds()/3600 if microseconds <= 0 else None
    assert fv["values"][f"observed_recovery_exact_hours_{side}"] == expected
    assert fv["values"][f"observed_matches_1d_{side}"] == (1 if microseconds < 0 else None)
