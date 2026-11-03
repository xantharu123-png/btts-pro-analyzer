"""Owner decision 03.11.2026: the 15K page shows at most five games and keeps one ticket per day."""
import inspect

import challenge_15k
import ev_signal_sources
import wettfinder_automation
from challenge_engine import MAX_TICKET_LEGS
from tests.test_challenge_15k import candidate


def test_caps_are_five_and_internal_bounds_unchanged():
    assert challenge_15k.CHALLENGE_PAGE_MAX_GAMES == 5
    assert ev_signal_sources.MAX_AUTOMATED_CHALLENGE_RELEASE_CANDIDATES == 5
    assert challenge_15k.MAX_PUBLIC_FORECASTS == 15
    assert MAX_TICKET_LEGS == 3


def test_display_selection_keeps_at_most_five_games():
    pool = [candidate(f"{index}:BTTS_YES", index, 0.80 - index / 200) for index in range(1, 13)]
    chosen = challenge_15k._challenge_display_selections(pool)
    assert len(chosen) == 5
    assert len({item.fixture_id for item in chosen}) == 5


def test_render_and_writer_use_the_five_game_caps():
    render = inspect.getsource(challenge_15k._render_model_challenge)
    assert "leads[:CHALLENGE_PAGE_MAX_GAMES]" in render and "MAX_PUBLIC_FORECASTS" not in render
    writer = inspect.getsource(wettfinder_automation.run_wettfinder)
    assert "challenge_release_candidates[:MAX_AUTOMATED_CHALLENGE_RELEASE_CANDIDATES]" in writer
    assert "[:MAX_AUTOMATED_CHALLENGE_RELEASE_CANDIDATES]" in inspect.getsource(
        wettfinder_automation._republish_floor_candidates)
