"""A team card total cannot turn an explicitly off-field report into 11-v-10."""
from types import SimpleNamespace

import pytest

from live_football_source import analyze_detail
from red_card_bot import RedCardBotEnhanced
from test_live_football_source import native


@pytest.fixture(params=["Substitute", "On the bench", "Coach", "Red card for the assistant coach",
                        "Technical staff", "Substituted player", "Player already substituted off",
                        "Red card (bench)", "No red card", "Red card rescinded"])
def non_playing_card(request):
    row = native()
    row["events"][1]["comments"] = request.param
    return row


def manual_cards(row, monkeypatch):
    bot = RedCardBotEnhanced(api_key="offline", streamlit_mode=False)
    monkeypatch.setattr(bot, "_get", lambda *args, **kwargs: SimpleNamespace(
        status_code=200, json=lambda: {"errors": [], "response": row["events"]}))
    return bot.check_match_for_red_cards(row, include_seen=True)


def test_explicit_non_playing_card_cannot_adjust_either_automatic_model(non_playing_card):
    assert analyze_detail(non_playing_card) == (None, None)


def test_explicit_non_playing_card_is_not_a_manual_model_input(non_playing_card, monkeypatch):
    assert manual_cards(non_playing_card, monkeypatch) == []


def test_manual_scan_does_not_reclassify_a_conflicting_second_report_as_one_on_field_card(monkeypatch):
    row = native()
    row["events"].append(dict(row["events"][1], comments="Red card rescinded"))
    assert not any(card["source_dismissal_count"] == 1 for card in manual_cards(row, monkeypatch))


@pytest.mark.parametrize("comment", [None, "Professional foul last man", "Foul on a substitute",
                                     "Substitute entered at halftime; now sent off for a foul"])
def test_regular_dismissal_remains_a_single_model_input(comment, monkeypatch):
    row = native()
    row["events"][1]["comments"] = comment
    ordinary, red = analyze_detail(row)
    assert ordinary["red_cards"]["status"] == "AWAY_DISMISSED_ADJUSTED"
    assert red["red_side"] == "away"
    card, = manual_cards(row, monkeypatch)
    assert card["source_dismissal_count"] == 1
